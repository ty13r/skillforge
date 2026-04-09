"""Competitor — runs a single candidate Skill against a single Challenge.

Invokes the Claude Agent SDK ``query()`` with:
- ``cwd`` pointing at the sandbox directory
- ``setting_sources=["project"]`` so the Skill loads from ``.claude/skills/``
- ``permission_mode="dontAsk"`` (never ``bypassPermissions`` — that's a trap)
- ``allowed_tools=["Skill", "Read", "Write", "Edit", "Bash"]``
- ``max_turns=config.MAX_TURNS``

Collects the full execution trace + written files for the judging pipeline.
Implemented in Step 6c.
"""

from __future__ import annotations

from pathlib import Path

from skillforge.models import Challenge, CompetitionResult, SkillGenome


async def run_competitor(
    skill: SkillGenome,
    challenge: Challenge,
    sandbox_path: Path,
) -> CompetitionResult:
    """Run one Skill against one Challenge in an isolated sandbox."""
    raise NotImplementedError
