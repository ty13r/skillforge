"""Spawner — creates gen 0 populations and breeds next generations.

Gen 0: reads the golden template from ``config.GOLDEN_TEMPLATE_DIR`` and
``bible/patterns/*.md``, generates ``pop_size`` diverse Skills varying content
while preserving structure.

Gen 1+: takes parent genomes + breeding instructions from the Breeder and
produces child Skills. The Spawner MUST enforce all authoring constraints
from ``engine.sandbox.validate_skill_structure``.

Uses the Anthropic Messages API directly (NOT the Agent SDK's query()) because
this is a pure generation task with no tool use. The Agent SDK's query() is
for agentic loops with tools and hung the overnight live test.
"""

from __future__ import annotations

import json
import re
import uuid

from anthropic import AsyncAnthropic

from skillforge.config import ANTHROPIC_API_KEY, BIBLE_DIR, GOLDEN_TEMPLATE_DIR, model_for
from skillforge.engine.sandbox import validate_skill_structure
from skillforge.models import SkillGenome

# JSON schema for spawner responses
_SPAWN_SCHEMA_DESCRIPTION = """[
  {
    "name": "kebab-case-name",
    "skill_md_content": "---\\nname: ...\\n---\\n\\n# Skill\\n\\n...",
    "supporting_files": {"scripts/validate.sh": "#!/bin/bash\\n..."},
    "traits": ["imperative-phrasing", "tests-first"],
    "meta_strategy": "plan-first TDD"
  }
]"""

_BREED_SCHEMA_DESCRIPTION = """[
  {
    "name": "kebab-case-name",
    "skill_md_content": "---\\nname: ...\\n---\\n\\n# Skill\\n\\n...",
    "supporting_files": {"scripts/validate.sh": "#!/bin/bash\\n..."},
    "traits": ["imperative-phrasing", "tests-first"],
    "meta_strategy": "plan-first TDD",
    "parent_ids": ["uuid-1", "uuid-2"],
    "mutations": ["changed-meta-strategy", "added-examples"],
    "mutation_rationale": "Switched to TDD-first based on parent attribution data"
  }
]"""


def _read_bible_patterns() -> str:
    """Concatenate all .md files under BIBLE_DIR/patterns in sorted order.

    Returns empty string if the directory doesn't exist or is empty.
    """
    patterns_dir = BIBLE_DIR / "patterns"
    if not patterns_dir.exists():
        return ""

    parts: list[str] = []
    for p in sorted(patterns_dir.glob("*.md")):
        try:
            parts.append(p.read_text())
        except (OSError, UnicodeDecodeError):
            continue

    return "\n\n---\n\n".join(parts)


def _extract_json_array(text: str) -> list[dict]:
    """Extract a JSON array from text.

    Handles three cases robustly:
      1. Whole response is a raw JSON array
      2. Response is wrapped in ``` json ... ``` fences (greedy match of
         the outermost fence — SKILL.md content can contain nested fences
         that a non-greedy match would trip over)
      3. JSON array embedded in prose, extracted via bracket-depth scanning
         that respects string literal state (handles `[` and `]` inside
         string values like Python list comp examples)

    Raises:
        ValueError: if no valid JSON array can be extracted.
    """
    candidate = text.strip()

    # 1. Try the whole text as JSON (ideal case)
    if candidate.startswith("[") and candidate.endswith("]"):
        try:
            result = json.loads(candidate)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # 2. Strip outer ```json ... ``` fence greedily (matches LAST ```).
    #    Non-greedy would stop at the first nested ``` inside string values.
    fence_match = re.search(r"```(?:json)?\s*\n?(.*)\n?```", text, re.DOTALL)
    if fence_match:
        fenced = fence_match.group(1).strip()
        try:
            result = json.loads(fenced)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            # Fall through to bracket scanning on the fenced content
            text_to_scan = fenced
        else:
            text_to_scan = fenced
    else:
        text_to_scan = text

    # 3. Bracket-depth scan that respects JSON string literal state
    array = _scan_outermost_array(text_to_scan)
    if array is not None:
        try:
            result = json.loads(array)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    raise ValueError("No valid JSON array found in response text")


def _scan_outermost_array(text: str) -> str | None:
    """Find the outermost JSON array substring via bracket-depth scanning.

    Properly tracks string literal state so brackets inside string values
    don't throw off the depth counter. Returns the substring (including the
    outer ``[`` and ``]``), or ``None`` if no balanced array is found.
    """
    start = text.find("[")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _extract_response_text(response) -> str:
    """Extract text from an Anthropic Messages API response.

    The response's ``content`` is a list of content blocks; extract any
    that have a ``.text`` attribute.
    """
    if not response.content:
        return ""
    parts: list[str] = []
    for block in response.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _save_debug_response(label: str, text: str) -> None:
    """Write the last raw LLM response to /tmp for post-hoc debugging.

    Non-fatal — any write error is silently swallowed. This is for diagnosing
    parse failures during live runs; in production the text is ephemeral.
    """
    try:
        from pathlib import Path

        path = Path("/tmp") / f"sf-{label}.txt"
        path.write_text(text)
    except OSError:
        pass


def _parse_genomes(
    raw: list[dict],
    generation: int,
    parent_ids: list[str] | None = None,
) -> list[SkillGenome]:
    """Convert raw dicts from Claude's response into SkillGenome objects."""
    genomes: list[SkillGenome] = []
    for item in raw:
        genome = SkillGenome(
            id=str(uuid.uuid4()),
            generation=generation,
            skill_md_content=item.get("skill_md_content", ""),
            supporting_files=item.get("supporting_files", {}),
            traits=item.get("traits", []),
            meta_strategy=item.get("meta_strategy", ""),
            parent_ids=parent_ids or item.get("parent_ids", []),
            mutations=item.get("mutations", []),
            mutation_rationale=item.get("mutation_rationale", ""),
            maturity="draft",
        )
        genomes.append(genome)
    return genomes


async def _generate(prompt: str) -> str:
    """Streaming Anthropic API call. Returns the full assistant text response.

    The Spawner generates structured JSON output containing multiple SKILL.md
    files (up to ~5KB per skill × pop_size = 25KB+ at pop_size=5). Non-streaming
    requests get server-disconnected around the 3-4 minute mark on prompts this
    size. Streaming keeps the connection alive via incremental chunks and handles
    long generations reliably.

    ``max_tokens`` is set to 32000 to fit a full population of rich SKILL.md
    files with supporting scripts. Claude Sonnet 4.6 supports up to 64K output
    tokens in streaming mode; 32K is plenty for realistic populations while
    keeping a sane ceiling.
    """
    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY, timeout=600.0)
    parts: list[str] = []
    async with client.messages.stream(
        model=model_for("spawner"),
        max_tokens=32000,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for text in stream.text_stream:
            parts.append(text)
    return "".join(parts)


def _validate_genomes(
    genomes: list[SkillGenome],
) -> tuple[list[SkillGenome], dict[int, list[str]]]:
    """Validate each genome; returns (valid_genomes, {idx: violations})."""
    valid: list[SkillGenome] = []
    invalid: dict[int, list[str]] = {}
    for i, genome in enumerate(genomes):
        violations = validate_skill_structure(genome)
        if violations:
            invalid[i] = violations
        else:
            valid.append(genome)
    return valid, invalid


def _build_spawn_system_prompt(
    specialization: str,
    pop_size: int,
    template: str,
    bible_patterns: str,
) -> str:
    """Build the system prompt for gen 0 spawn."""
    bible_section = (
        f"\n\n## Validated Patterns (apply these)\n\n{bible_patterns}"
        if bible_patterns
        else ""
    )
    return (
        f"You are a Skill author for the Claude Agent SDK. Your task is to generate "
        f"{pop_size} DIVERSE candidate Skills for the following specialization:\n\n"
        f"SPECIALIZATION: {specialization}\n\n"
        "Each Skill must:\n"
        "1. Follow the exact YAML frontmatter + markdown structure of the template below\n"
        "2. Include 'Use when' in the first 250 chars of the description\n"
        "3. Have a name matching the regex ^[a-z0-9]+(-[a-z0-9]+)*$\n"
        "4. Contain at least 2 example blocks (**Example or ## Example)\n"
        "5. Keep the body under 500 lines\n"
        "6. Have a description under 1024 characters\n"
        "7. NOT use 'anthropic' or 'claude' in the name\n"
        "8. Only reference paths in ${CLAUDE_SKILL_DIR}/... that are included in supporting_files\n\n"
        "## Golden Template\n\n"
        f"{template}"
        f"{bible_section}\n\n"
        f"Return ONLY a JSON array of exactly {pop_size} skill objects. "
        "No prose before or after — ONLY the JSON array. Use this schema:\n"
        f"{_SPAWN_SCHEMA_DESCRIPTION}\n"
        "Vary the approach, strategy, instruction style, and examples across all skills "
        "while preserving the template structure."
    )


def _build_breed_system_prompt(
    parents: list[SkillGenome],
    learning_log: list[str],
    breeding_instructions: str,
    bible_patterns: str,
) -> str:
    """Build the system prompt for next-gen breeding."""
    bible_section = (
        f"\n\n## Validated Patterns\n\n{bible_patterns}" if bible_patterns else ""
    )

    parents_section = "\n\n".join(
        f"### Parent {i + 1} (id: {p.id})\n"
        f"**Traits**: {p.traits}\n"
        f"**Meta-strategy**: {p.meta_strategy}\n"
        f"**Trait attribution**: {p.trait_attribution}\n"
        f"**Trait diagnostics**: {p.trait_diagnostics}\n\n"
        f"**SKILL.md content**:\n```\n{p.skill_md_content}\n```"
        for i, p in enumerate(parents)
    )

    learning_section = (
        "\n".join(f"- {entry}" for entry in learning_log)
        if learning_log
        else "(no entries yet)"
    )

    return (
        "You are a Skill evolutionary breeder for the Claude Agent SDK.\n\n"
        "## Breeding Instructions (from Breeder agent)\n\n"
        f"{breeding_instructions}\n\n"
        "## Parent Skills\n\n"
        f"{parents_section}\n\n"
        "## Learning Log (failures and lessons from all prior generations)\n\n"
        f"{learning_section}"
        f"{bible_section}\n\n"
        "## Rules for child Skills\n"
        "1. Follow YAML frontmatter + markdown structure of the parents\n"
        "2. Include 'Use when' in first 250 chars of description\n"
        "3. Name must match ^[a-z0-9]+(-[a-z0-9]+)*$ and NOT contain 'anthropic' or 'claude'\n"
        "4. At least 2 example blocks (**Example or ## Example)\n"
        "5. Body under 500 lines, description under 1024 characters\n"
        "6. Only reference ${CLAUDE_SKILL_DIR}/... paths that are in supporting_files\n\n"
        "Return ONLY a JSON array of child skill objects. Use this schema:\n"
        f"{_BREED_SCHEMA_DESCRIPTION}"
    )


def _build_repair_prompt(
    original_prompt: str,
    violations_by_idx: dict[int, list[str]],
    genomes: list[SkillGenome],
) -> str:
    """Build a reprompt asking Claude to fix specific violations."""
    violation_lines: list[str] = []
    for idx, viols in violations_by_idx.items():
        genome_name = genomes[idx].skill_md_content[:50].replace("\n", " ")
        violation_lines.append(
            f"Skill index {idx} ({genome_name!r}): {'; '.join(viols)}"
        )
    violations_str = "\n".join(violation_lines)

    return (
        "Your previous response contained invalid Skills. "
        "Fix the following violations and return a corrected JSON array:\n\n"
        f"{violations_str}\n\n"
        "Return ONLY the complete corrected JSON array — all skills, not just the fixed ones."
    )


async def spawn_gen0(specialization: str, pop_size: int) -> list[SkillGenome]:
    """Generate ``pop_size`` diverse gen 0 Skills for the specialization.

    Args:
        specialization: Description of the Skill domain.
        pop_size: Number of candidate Skills to generate.

    Returns:
        A list of ``pop_size`` validated SkillGenome objects at generation 0.

    Raises:
        ValueError: if Skills remain invalid after 1 retry.
    """
    template = (GOLDEN_TEMPLATE_DIR / "SKILL.md").read_text()
    bible_patterns = _read_bible_patterns()

    system_prompt = _build_spawn_system_prompt(
        specialization, pop_size, template, bible_patterns
    )

    # Attempt 1
    text = await _generate(system_prompt)
    _save_debug_response("spawn_gen0_attempt1", text)

    try:
        raw = _extract_json_array(text)
        genomes = _parse_genomes(raw, generation=0)
        valid_genomes, invalid = _validate_genomes(genomes)
        first_attempt_failed = False
    except ValueError:
        # JSON parse failure — treat as if everything was invalid so the
        # retry path runs.
        genomes = []
        valid_genomes = []
        invalid = {}
        first_attempt_failed = True

    if not first_attempt_failed and not invalid:
        return valid_genomes

    # Attempt 2 — retry. Use the same prompt if JSON parse failed (Claude
    # just didn't follow instructions), or a targeted repair prompt if
    # the skills parsed but failed validation.
    if first_attempt_failed:
        retry_prompt = (
            system_prompt
            + "\n\nCRITICAL: Your previous response did not contain a valid JSON "
            "array. You must respond with ONLY a JSON array — no prose, no "
            "markdown before or after the array. The array must start with [ "
            "and end with ]. No explanations."
        )
    else:
        retry_prompt = _build_repair_prompt(system_prompt, invalid, genomes)

    text = await _generate(retry_prompt)
    _save_debug_response("spawn_gen0_attempt2", text)

    try:
        raw2 = _extract_json_array(text)
    except ValueError as exc:
        raise ValueError(
            f"spawner failed to produce valid JSON on retry: {exc}. "
            f"See /tmp/sf-spawn_gen0_attempt2.txt for the raw response."
        ) from exc

    genomes2 = _parse_genomes(raw2, generation=0)
    valid_genomes2, still_invalid = _validate_genomes(genomes2)

    if still_invalid:
        all_violations = [
            f"skill {i}: {'; '.join(v)}" for i, v in still_invalid.items()
        ]
        raise ValueError(
            "spawner produced invalid skills after retry: "
            + "; ".join(all_violations)
        )

    return valid_genomes2


async def breed_next_gen(
    parents: list[SkillGenome],
    learning_log: list[str],
    breeding_instructions: str,
) -> list[SkillGenome]:
    """Produce a child population from parents + Breeder's instructions.

    Args:
        parents: Parent SkillGenome objects (with trait_attribution populated).
        learning_log: Accumulated lessons from all prior generations.
        breeding_instructions: Free-text directives from the Breeder agent.

    Returns:
        A list of validated child SkillGenome objects at generation+1.

    Raises:
        ValueError: if children remain invalid after 1 retry.
    """
    bible_patterns = _read_bible_patterns()
    parent_ids = [p.id for p in parents]
    next_generation = (parents[0].generation + 1) if parents else 1

    system_prompt = _build_breed_system_prompt(
        parents, learning_log, breeding_instructions, bible_patterns
    )

    # Attempt 1
    text = await _generate(system_prompt)

    try:
        raw = _extract_json_array(text)
    except ValueError as exc:
        raise ValueError(
            f"spawner breed_next_gen failed to produce valid JSON: {exc}"
        ) from exc

    # Parse with generation and parent_ids from raw (each child should specify its own parent_ids)
    children: list[SkillGenome] = []
    for item in raw:
        child = SkillGenome(
            id=str(uuid.uuid4()),
            generation=next_generation,
            skill_md_content=item.get("skill_md_content", ""),
            supporting_files=item.get("supporting_files", {}),
            traits=item.get("traits", []),
            meta_strategy=item.get("meta_strategy", ""),
            parent_ids=item.get("parent_ids", parent_ids),
            mutations=item.get("mutations", []),
            mutation_rationale=item.get("mutation_rationale", ""),
            maturity="draft",
        )
        children.append(child)

    valid_children, invalid = _validate_genomes(children)

    if not invalid:
        return valid_children

    # Attempt 2 — repair
    repair_prompt = _build_repair_prompt(system_prompt, invalid, children)
    text = await _generate(repair_prompt)

    try:
        raw2 = _extract_json_array(text)
    except ValueError as exc:
        raise ValueError(
            f"spawner breed_next_gen failed to produce valid JSON on retry: {exc}"
        ) from exc

    children2: list[SkillGenome] = []
    for item in raw2:
        child = SkillGenome(
            id=str(uuid.uuid4()),
            generation=next_generation,
            skill_md_content=item.get("skill_md_content", ""),
            supporting_files=item.get("supporting_files", {}),
            traits=item.get("traits", []),
            meta_strategy=item.get("meta_strategy", ""),
            parent_ids=item.get("parent_ids", parent_ids),
            mutations=item.get("mutations", []),
            mutation_rationale=item.get("mutation_rationale", ""),
            maturity="draft",
        )
        children2.append(child)

    valid_children2, still_invalid = _validate_genomes(children2)

    if still_invalid:
        all_violations = [
            f"skill {i}: {'; '.join(v)}" for i, v in still_invalid.items()
        ]
        raise ValueError(
            "spawner produced invalid skills after retry: "
            + "; ".join(all_violations)
        )

    return valid_children2


# ---------------------------------------------------------------------------
# spawn_from_parent — gen 0 from an existing Skill (seed fork or upload)
# ---------------------------------------------------------------------------

async def spawn_from_parent(
    parent: SkillGenome,
    pop_size: int,
) -> list[SkillGenome]:
    """Generate a gen 0 population using an existing Skill as the seed parent.

    The parent itself is carried forward as the elite (slot 0) and ``pop_size - 1``
    diverse mutations are synthesized around it. Used by the Registry fork-and-
    evolve flow and the upload-and-evolve flow — both just hand us an existing
    genome to evolve forward instead of spawning from the golden template.

    Args:
        parent: The seed SkillGenome to evolve from (untouched in the output).
        pop_size: Total population size including the elite parent.

    Returns:
        A list of ``pop_size`` SkillGenome objects at generation 0. The first
        entry is the parent (re-id'd, elite); the rest are mutations.
    """
    if pop_size < 1:
        raise ValueError(f"pop_size must be ≥ 1, got {pop_size}")

    bible_patterns = _read_bible_patterns()

    # The elite: clone the parent with a fresh id, retain content + traits
    elite = SkillGenome(
        id=str(uuid.uuid4()),
        generation=0,
        skill_md_content=parent.skill_md_content,
        frontmatter=dict(parent.frontmatter),
        supporting_files=dict(parent.supporting_files),
        traits=list(parent.traits),
        meta_strategy=parent.meta_strategy,
        parent_ids=[parent.id],
        mutations=["elite-carry"],
        mutation_rationale="Seed parent carried forward as elite.",
        maturity=parent.maturity or "draft",
    )

    if pop_size == 1:
        return [elite]

    num_mutants = pop_size - 1
    system_prompt = f"""You are evolving an existing Claude Agent Skill by producing {num_mutants} diverse mutations.

The parent Skill is below. Your job is to produce {num_mutants} variant Skills that preserve the parent's core capability but explore different:
- Description phrasing + trigger expansion
- Instruction structure (more/fewer numbered steps, different section ordering)
- Trait emphasis (lean harder into some traits, introduce new ones)
- Example diversity (different I/O pairs)

Each mutation must still satisfy every constraint in the bible (≤250 char description, "Use when" + "NOT for" clauses, ≤500 line body, 2-3 diverse examples, valid YAML frontmatter, unique name matching `^[a-z0-9]+(-[a-z0-9]+)*$`).

## Bible patterns (non-negotiable)

{bible_patterns}

## Parent Skill

```
{parent.skill_md_content}
```

Parent traits: {", ".join(parent.traits) if parent.traits else "(none)"}
Parent strategy: {parent.meta_strategy}

## Output

Return a JSON array of exactly {num_mutants} skills. Each entry is a JSON object with fields:
- `skill_md_content`: the full SKILL.md (YAML frontmatter + body)
- `traits`: list of trait strings
- `meta_strategy`: 1-2 sentences
- `mutations`: list of mutation-type strings (e.g. ["description-expansion", "example-swap"])
- `mutation_rationale`: why these mutations were made

Do NOT modify the parent. Do NOT return fewer or more than {num_mutants} entries. Each mutation must have a UNIQUE `name` field in its frontmatter.
"""

    text = await _generate(system_prompt)

    try:
        raw = _extract_json_array(text)
    except ValueError:
        # If the LLM refused or produced garbage, fall back to elite-only
        # (graceful degradation — evolution can still proceed with just the parent)
        return [elite]

    mutants: list[SkillGenome] = []
    for item in raw[:num_mutants]:
        mutants.append(
            SkillGenome(
                id=str(uuid.uuid4()),
                generation=0,
                skill_md_content=item.get("skill_md_content", ""),
                supporting_files=item.get("supporting_files", {}),
                traits=item.get("traits", []),
                meta_strategy=item.get("meta_strategy", ""),
                parent_ids=[parent.id],
                mutations=item.get("mutations", []),
                mutation_rationale=item.get("mutation_rationale", ""),
                maturity="draft",
            )
        )

    # Drop any mutants that fail validation — keep the elite always
    valid_mutants, _ = _validate_genomes(mutants)
    return [elite, *valid_mutants][:pop_size]


# ---------------------------------------------------------------------------
# v2.0 — focused per-dimension variant spawner
# ---------------------------------------------------------------------------


def _build_variant_spawn_prompt(
    specialization: str,
    dimension: dict,
    foundation_genome: SkillGenome | None,
    pop_size: int,
    template: str,
) -> str:
    """System prompt for spawning N focused mini-SKILL.md variants for one dimension."""
    name = dimension.get("name", "")
    tier = dimension.get("tier", "")
    description = dimension.get("description", "")
    evaluation_focus = dimension.get("evaluation_focus", "")

    foundation_block = ""
    if foundation_genome is not None and tier == "capability":
        # Capability variants get the winning foundation as grounding so they
        # plug into a consistent skeleton during Engineer assembly later.
        foundation_block = (
            "\n## Foundation context (capability variants must plug into this)\n\n"
            "The following foundation variant has already won its tier. Your "
            "capability variants will be assembled with it later, so they "
            "MUST be compatible with its directory layout, naming, and fixture "
            "philosophy. Reference the foundation's scripts and conventions "
            "in your workflow steps.\n\n"
            "```markdown\n"
            f"{foundation_genome.skill_md_content[:2000]}\n"
            "```\n"
        )

    return (
        f"## Specialization\n\n{specialization}\n\n"
        f"## Variant dimension you are spawning for\n\n"
        f"- Name: `{name}`\n"
        f"- Tier: {tier}\n"
        f"- Description: {description}\n"
        f"- Evaluation focus: {evaluation_focus}\n"
        f"{foundation_block}\n"
        f"## Your job\n\n"
        f"Spawn {pop_size} DIVERSE mini-skill packages that each take a "
        f"DIFFERENT angle on the dimension above. Gen 0 exists to explore — "
        f"do not produce N near-duplicates and do not kitchen-sink one "
        f"variant with every approach.\n\n"
        "**One dimension, one angle per variant.** Each variant's SKILL.md "
        "body must focus on the single dimension named above and avoid "
        "drifting into adjacent dimensions.\n\n"
        "## Golden template\n\n"
        f"```markdown\n{template}\n```\n\n"
        "## Hard rules (validator-enforced)\n\n"
        "- `name`: kebab-case, matches `^[a-z0-9]+(-[a-z0-9]+)*$`\n"
        "- `description`: ≤250 chars, pushy routing pattern\n"
        "- Body: ≤500 lines\n"
        "- 2-3 diverse I/O examples mandatory\n"
        "- The body MUST mention the dimension name somewhere\n"
        "- All scripts/references referenced from SKILL.md use the\n"
        "  `${CLAUDE_SKILL_DIR}/...` path convention\n\n"
        "## Output format\n\n"
        f"Return ONLY a JSON array of exactly {pop_size} objects matching:\n\n"
        '```json\n[\n  {\n'
        '    "frontmatter": {"name": "kebab-case", "description": "...", '
        '"allowed-tools": "Read Write"},\n'
        '    "skill_md_content": "# Display Name\\n## Quick Start\\n...",\n'
        '    "supporting_files": {"scripts/score.py": "...", '
        '"scripts/validate.sh": "..."},\n'
        '    "traits": ["trait1", "trait2"],\n'
        '    "meta_strategy": "one-liner approach description"\n'
        "  }\n]\n```\n"
        "No prose before or after — ONLY the JSON array."
    )


async def spawn_variant_gen0(
    specialization: str,
    dimension: dict,
    foundation_genome: SkillGenome | None,
    pop_size: int = 2,
) -> list[SkillGenome]:
    """Spawn ``pop_size`` focused mini-skill variants for a single dimension.

    Args:
        specialization: The parent skill family's specialization string.
        dimension: A dict with at minimum ``name`` and ``tier`` keys; may
            include ``description`` and ``evaluation_focus``. Matches the
            shape of ``TaxonomistOutput.variant_dimensions``.
        foundation_genome: For capability variants, the winning foundation
            genome to use as grounding context. Pass ``None`` for foundation
            variants.
        pop_size: How many variants to spawn (default 2 for atomic mode).

    Returns:
        A list of ``pop_size`` SkillGenome objects at generation 0. Each is
        validated against the standard authoring constraints. Invalid
        variants are dropped — the caller may receive fewer than
        ``pop_size`` if the model produces malformed output, but never more.

    Raises:
        ValueError: if no valid variants survive validation after one retry.
    """
    if pop_size < 1:
        raise ValueError(f"pop_size must be ≥ 1, got {pop_size}")

    template = (GOLDEN_TEMPLATE_DIR / "SKILL.md").read_text()
    system_prompt = _build_variant_spawn_prompt(
        specialization, dimension, foundation_genome, pop_size, template
    )

    text = await _generate(system_prompt)
    _save_debug_response(f"spawn_variant_gen0_{dimension.get('name', 'unknown')}", text)

    try:
        raw = _extract_json_array(text)
    except ValueError:
        # One retry with a stricter formatting reminder
        retry_prompt = (
            system_prompt
            + "\n\nCRITICAL: Your previous response did not contain a valid "
            "JSON array. Respond with ONLY a JSON array — no prose, no "
            "markdown fences."
        )
        text = await _generate(retry_prompt)
        raw = _extract_json_array(text)

    genomes = _parse_genomes(raw, generation=0)
    valid_genomes, invalid = _validate_genomes(genomes)

    if not valid_genomes:
        violations = [f"skill {i}: {'; '.join(v)}" for i, v in invalid.items()]
        raise ValueError(
            "spawn_variant_gen0 produced no valid variants: "
            + "; ".join(violations)
        )

    # Stamp dimension metadata into the frontmatter so the Reviewer knows
    # how to scope L3/L4 evaluation. Validator doesn't require it but it's
    # the right shape for downstream consumers.
    for genome in valid_genomes:
        genome.frontmatter["dimension"] = dimension.get("name", "")
        genome.frontmatter["tier"] = dimension.get("tier", "")

    return valid_genomes[:pop_size]
