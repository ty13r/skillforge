"""Variant evolution orchestrator (v2.0 Wave 3-1).

Atomic-mode entry point. When ``run.evolution_mode == "atomic"`` the
parent ``run_evolution`` dispatcher delegates to ``run_variant_evolution``
(re-exported below). The orchestrator runs one mini-evolution per
variant dimension recorded against the parent run, then calls the
Engineer to assemble the winners into a composite skill.

Submodule layout:

  _helpers.py   shared constants + small pure helpers
  dimension.py  per-dimension mini-evolution (challenge -> spawn ->
                compete -> score -> judge -> breed -> pick winner)
  assembly.py   composite assembly via the Engineer
  main.py       top-level run_variant_evolution orchestrator

The mini-evolutions reuse existing helpers (Spawner, Competitor,
judging pipeline) directly rather than recursing into ``run_evolution``
itself — recursion would force a second event loop and complicate the
parent run's event stream.
"""

from __future__ import annotations

from skillforge.engine.variant_evolution._helpers import _aggregate_fitness, _tier_sort_key
from skillforge.engine.variant_evolution.main import run_variant_evolution

__all__ = [
    "run_variant_evolution",
    # Private helpers re-exported for test access.
    "_aggregate_fitness",
    "_tier_sort_key",
]
