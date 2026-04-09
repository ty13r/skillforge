"""L3 — Trace-based behavioral analysis.

Parses the Agent SDK execution trace to answer:
- Did Claude actually load the Skill?
- Which SKILL.md instructions were followed vs. ignored?
- Which supporting scripts were executed?
- What is the Skill's behavioral signature (ordered sequence of actions)?

Populates: ``skill_was_loaded``, ``instructions_followed``, ``instructions_ignored``,
``ignored_diagnostics``, ``scripts_executed``, ``behavioral_signature``.
"""

from __future__ import annotations

from skillforge.models import CompetitionResult, SkillGenome


async def run_l3(result: CompetitionResult, skill: SkillGenome) -> CompetitionResult:
    """Analyze the execution trace and populate L3 fields in place."""
    raise NotImplementedError
