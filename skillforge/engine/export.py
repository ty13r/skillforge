"""Export the evolved Skill as a zip, Agent SDK config, or raw SKILL.md.

Real implementations land in Step 9.
"""

from __future__ import annotations

from skillforge.models import SkillGenome


def export_skill_zip(genome: SkillGenome) -> bytes:
    """Package the genome as an installable Skill directory zip.

    Includes SKILL.md, supporting files, and a META.md with lineage + fitness.
    """
    raise NotImplementedError


def export_agent_sdk_config(genome: SkillGenome) -> dict:
    """Produce a ``ClaudeAgentOptions``-style JSON config derived from the Skill."""
    raise NotImplementedError


def export_skill_md(genome: SkillGenome) -> str:
    """Return the raw SKILL.md text for the genome."""
    raise NotImplementedError
