"""Spawner entry points.

Four top-level coroutines:
- ``spawn_gen0``          fresh population from a specialization string
- ``breed_next_gen``      child skills from ranked parents + instructions
- ``spawn_from_parent``   fork-and-evolve from a single seed genome
- ``spawn_variant_gen0``  per-dimension atomic variants

All four share the same generate/parse/validate/repair loop, differ
only in the prompt they feed the LLM and their retry cadence.
"""

from __future__ import annotations

import uuid

from skillforge.agents._json import extract_json_array
from skillforge.agents.spawner._helpers import (
    _parse_genomes,
    _save_debug_response,
    _validate_genomes,
)
from skillforge.agents.spawner._prompts import (
    _build_breed_system_prompt,
    _build_repair_prompt,
    _build_spawn_system_prompt,
    _build_variant_spawn_prompt,
)
from skillforge.config import GOLDEN_TEMPLATE_DIR
from skillforge.errors import ParseError
from skillforge.models import SkillGenome


async def _generate(prompt: str) -> str:
    """Dispatch to the real ``_generate`` via the package namespace.

    Tests patch ``skillforge.agents.spawner._generate`` to intercept LLM
    calls. Binding the helper at import time would shadow that patch;
    this indirection resolves the attribute on the package root at call
    time so the patch takes effect.
    """
    from skillforge.agents import spawner as _pkg

    return await _pkg._generate(prompt)


def _read_bible_patterns() -> str:
    """Same lazy-lookup pattern as ``_generate`` — tests sometimes patch
    ``skillforge.agents.spawner._read_bible_patterns``."""
    from skillforge.agents import spawner as _pkg

    return _pkg._read_bible_patterns()


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
        raw = extract_json_array(text)
        genomes = _parse_genomes(raw, generation=0)
        valid_genomes, invalid = _validate_genomes(genomes)
        first_attempt_failed = False
    except (ValueError, ParseError):
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
        raw2 = extract_json_array(text)
    except (ValueError, ParseError) as exc:
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
        raw = extract_json_array(text)
    except (ValueError, ParseError) as exc:
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
        raw2 = extract_json_array(text)
    except (ValueError, ParseError) as exc:
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
        raw = extract_json_array(text)
    except (ValueError, ParseError):
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
        raw = extract_json_array(text)
    except (ValueError, ParseError):
        # One retry with a stricter formatting reminder
        retry_prompt = (
            system_prompt
            + "\n\nCRITICAL: Your previous response did not contain a valid "
            "JSON array. Respond with ONLY a JSON array — no prose, no "
            "markdown fences."
        )
        text = await _generate(retry_prompt)
        raw = extract_json_array(text)

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
