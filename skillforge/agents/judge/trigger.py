"""L2 — Trigger accuracy via single batched Anthropic API call per Skill.

Given the Skill's description and a list of should_trigger / should_not_trigger
eval queries, makes ONE Messages API call that asks the model which queries
would trigger the Skill. Computes precision and recall from the result.

This avoids the naive "spawn an Agent SDK query per eval query" approach
(~150 extra SDK calls per generation). Batched call is ~30× cheaper.
"""

from __future__ import annotations

from skillforge.models import SkillGenome


async def run_l2(
    skill: SkillGenome,
    should_trigger: list[str],
    should_not_trigger: list[str],
) -> tuple[float, float]:
    """Return ``(precision, recall)`` for the Skill's description."""
    raise NotImplementedError
