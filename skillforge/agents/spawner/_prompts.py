"""Spawner prompt-string builders.

Pure string templating — no I/O, no LLM calls. The four entry points
(``gen0``, ``breed``, ``from_parent``, ``variant``) feed the strings
produced here into ``_helpers._generate``.

The embedded JSON schema descriptions (``_SPAWN_SCHEMA_DESCRIPTION``
etc.) double as prompt-documentation for Claude and as the contract the
Spawner validates against on the way back in.
"""

from __future__ import annotations

from skillforge.models import SkillGenome

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
        f"Return ONLY a JSON array of exactly {pop_size} objects. The "
        "``skill_md_content`` field MUST contain the FULL SKILL.md — "
        "starting with ``---`` (YAML frontmatter), then the body. Do NOT "
        "separate frontmatter into its own field; it must be embedded in "
        "``skill_md_content`` as the validator expects a complete SKILL.md.\n\n"
        "Schema:\n"
        '```json\n[\n  {\n'
        '    "name": "kebab-case-name",\n'
        '    "skill_md_content": "---\\nname: ...\\ndescription: >-\\n  ...\\n---\\n\\n# Display Name\\n\\n## Quick Start\\n...",\n'
        '    "supporting_files": {"scripts/score.py": "...", '
        '"scripts/validate.sh": "..."},\n'
        '    "traits": ["trait1", "trait2"],\n'
        '    "meta_strategy": "one-liner approach description"\n'
        "  }\n]\n```\n"
        "No prose before or after — ONLY the JSON array."
    )

