"""Isolated per-competitor sandbox directories.

Each competitor runs in ``{SANDBOX_ROOT}/skillforge-{run_id}-gen{N}-competitor{M}/``
with structure::

    .claude/skills/evolved-skill/
        SKILL.md
        scripts/
        references/
    challenge/
        starter_code.py
        test_suite.py
    output/

Real implementation lands in Step 5. The ``validate_skill_structure`` signature
is fixed now so the Spawner (Step 6b) and sandbox share a single source of truth
for constraint enforcement.
"""

from __future__ import annotations

from pathlib import Path

from skillforge.models import Challenge, SkillGenome


def create_sandbox(
    run_id: str,
    generation: int,
    competitor_idx: int,
    skill: SkillGenome,
    challenge: Challenge,
) -> Path:
    """Create a temp project directory with the Skill and challenge files.

    Returns the path to the sandbox root (the ``cwd`` for the Agent SDK query).
    """
    raise NotImplementedError


def cleanup_sandbox(path: Path) -> None:
    """Remove a sandbox directory after evaluation completes."""
    raise NotImplementedError


def validate_skill_structure(skill: SkillGenome) -> list[str]:
    """Return a list of authoring-constraint violations (empty = valid).

    Enforces (per SPEC.md §Skill Authoring Constraints + docs/skills-research.md):
    - Directory/name regex ``^[a-z0-9]+(-[a-z0-9]+)*$``
    - SKILL.md present with parseable YAML frontmatter
    - ``description`` ≤1024 chars; first 250 chars contain capability + "Use when"
    - SKILL.md body ≤500 lines
    - ≥2 I/O examples in body
    - All reference paths resolve (no broken refs — 73% of audited skills fail this)
    - Scripts use ``${CLAUDE_SKILL_DIR}``, are executable
    - ``name`` field matches directory name exactly
    """
    raise NotImplementedError
