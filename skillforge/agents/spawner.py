"""Spawner — creates gen 0 populations and breeds next generations.

Gen 0: reads the golden template from ``config.GOLDEN_TEMPLATE_DIR`` and
``bible/patterns/*.md``, generates ``pop_size`` diverse Skills varying content
while preserving structure.

Gen 1+: takes parent genomes + breeding instructions from the Breeder and
produces child Skills. The Spawner MUST enforce all authoring constraints
from ``engine.sandbox.validate_skill_structure``.

Implemented in Step 6b.
"""

from __future__ import annotations

import json
import re
import uuid

from claude_agent_sdk import ClaudeAgentOptions, query

from skillforge.config import BIBLE_DIR, GOLDEN_TEMPLATE_DIR, model_for
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

    Tries fenced ```json ... ``` blocks first, then falls back to finding
    the first ``[`` and its matching ``]``.

    Raises:
        ValueError: if no valid JSON array can be extracted.
    """
    # 1. Try fenced block
    fence_match = re.search(r"```json\s*(.*?)```", text, re.DOTALL)
    if fence_match:
        candidate = fence_match.group(1).strip()
        try:
            result = json.loads(candidate)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass  # fall through to bracket search

    # 2. Fall back to first [ ... ] pair
    start = text.find("[")
    if start != -1:
        end = text.rfind("]")
        if end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                result = json.loads(candidate)
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

    raise ValueError("No valid JSON array found in response text")


def _collect_text(messages: list) -> str:
    """Collect all text from assistant messages into a single string.

    Handles real AssistantMessage objects (content blocks with TextBlock)
    as well as duck-typed test fakes that expose .content with objects
    having a .text attribute.
    """
    parts: list[str] = []
    for msg in messages:
        content = getattr(msg, "content", None)
        if content is None:
            continue
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                text_val = getattr(block, "text", None)
                if text_val is not None:
                    parts.append(text_val)
    return "\n".join(parts)


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


async def _run_query(system_prompt: str) -> list:
    """Run a query with spawner options and collect all messages."""
    options = ClaudeAgentOptions(
        permission_mode="dontAsk",
        allowed_tools=[],
        model=model_for("spawner"),
    )
    collected_msgs: list = []
    async for msg in query(prompt=system_prompt, options=options):
        collected_msgs.append(msg)
    return collected_msgs


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
    collected_msgs = await _run_query(system_prompt)
    text = _collect_text(collected_msgs)

    try:
        raw = _extract_json_array(text)
    except ValueError as exc:
        raise ValueError(
            f"spawner failed to produce valid JSON on first attempt: {exc}"
        ) from exc

    genomes = _parse_genomes(raw, generation=0)
    valid_genomes, invalid = _validate_genomes(genomes)

    if not invalid:
        return valid_genomes

    # Attempt 2 — repair
    repair_prompt = _build_repair_prompt(system_prompt, invalid, genomes)
    collected_msgs = await _run_query(repair_prompt)
    text = _collect_text(collected_msgs)

    try:
        raw2 = _extract_json_array(text)
    except ValueError as exc:
        raise ValueError(
            f"spawner failed to produce valid JSON on retry: {exc}"
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
    collected_msgs = await _run_query(system_prompt)
    text = _collect_text(collected_msgs)

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
    collected_msgs = await _run_query(repair_prompt)
    text = _collect_text(collected_msgs)

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
