"""L5 — Trait attribution (the novel SkillForge contribution).

Reads each Skill's SKILL.md alongside its execution trace and output. For each
discrete instruction or trait:
- If followed (trace evidence): correlate with L1-L4 scores → ``trait_contribution``
- If ignored: diagnose *why* (too vague? contradicted? irrelevant?) → ``trait_diagnostics``

Produces the causal signal the Breeder uses for reflective mutation.
"""

from __future__ import annotations

from skillforge.models import CompetitionResult, SkillGenome


async def run_l5(result: CompetitionResult, skill: SkillGenome) -> CompetitionResult:
    """Populate ``trait_contribution`` and ``trait_diagnostics`` on the result."""
    raise NotImplementedError
