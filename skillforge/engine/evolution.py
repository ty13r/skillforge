"""Core evolution loop orchestration.

For each generation:
    1. Spawn/breed competitor Skills
    2. For each Skill × each Challenge: run the competitor in an isolated sandbox
    3. Run the 6-layer judging pipeline (L1 → L5; L6 v1.1)
    4. Breed next generation from the ranked results + learning log
    5. Emit WebSocket events throughout
    6. Persist to SQLite
    7. Check budget

Built up incrementally in Step 7.
"""

from __future__ import annotations

from skillforge.models import EvolutionRun


async def run_evolution(run: EvolutionRun) -> EvolutionRun:
    """Execute a full evolution run end-to-end.

    Returns the updated ``EvolutionRun`` with status, generations, Pareto front,
    and best_skill populated. Implemented in Step 7.
    """
    raise NotImplementedError
