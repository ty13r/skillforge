"""Orchestrates the 6-layer judging pipeline in order.

L1 → L2 → L3 → L4 → L5 → (L6 if enabled). Each layer's outputs populate
specific fields on the ``CompetitionResult`` objects and the ``Generation``.
Implemented in Step 6d.
"""

from __future__ import annotations

from skillforge.models import Challenge, Generation


async def run_judging_pipeline(
    generation: Generation,
    challenges: list[Challenge],
) -> Generation:
    """Execute all judging layers in order; return the enriched generation."""
    raise NotImplementedError
