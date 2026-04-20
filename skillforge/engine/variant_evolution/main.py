"""Top-level atomic-mode orchestrator.

Reads the run's variant_evolutions rows, runs one mini-evolution per
dimension, then assembles the winners via the Engineer.
"""

from __future__ import annotations

import logging

from skillforge.db.queries import (
    get_variant_evolutions_for_run,
    save_run,
    save_variant_evolution,
)
from skillforge.engine.events import emit
from skillforge.engine.variant_evolution._helpers import (
    DEFAULT_VARIANT_GENS,
    DEFAULT_VARIANT_POP,
    _tier_sort_key,
)
from skillforge.engine.variant_evolution.assembly import _real_assembly
from skillforge.engine.variant_evolution.dimension import _run_dimension_mini_evolution
from skillforge.models import SkillGenome
from skillforge.models.run import EvolutionRun

logger = logging.getLogger("skillforge.engine.variant_evolution")


async def run_variant_evolution(run: EvolutionRun) -> EvolutionRun:
    """Top-level atomic-mode orchestrator.

    Reads the ``variant_evolutions`` rows for ``run.id``, processes each
    dimension in tier order, and stamps ``run.best_skill`` with the
    assembled composite. Falls back to molecular mode and logs a warning
    if no dimensions are recorded against the run (defensive — the
    Taxonomist should always create them at submission time for atomic).
    """
    all_rows = await get_variant_evolutions_for_run(run.id)

    # Filter to rows that actually need work. Rows already in a terminal
    # state (complete/failed) from prior runs must NOT be re-processed —
    # that was causing 4x API spend on re-runs because the live test's
    # hardcoded run_id accumulates stale rows across test invocations.
    # "running" is included because a previous crash may have left a row
    # stuck mid-processing; we let the orchestrator retry it.
    pending = [
        v for v in all_rows if v.status not in {"complete", "failed"}
    ]
    skipped = len(all_rows) - len(pending)
    if skipped:
        logger.info(
            "run=%s atomic mode: skipping %d terminal variant_evolutions "
            "(%d pending)",
            run.id[:8],
            skipped,
            len(pending),
        )

    if not pending:
        logger.warning(
            "run=%s atomic mode requested but no pending variant_evolutions; "
            "falling back to molecular pipeline",
            run.id[:8],
        )
        # Caller (run_evolution dispatcher) will handle the fallback
        run.evolution_mode = "molecular"
        return run

    pending.sort(key=_tier_sort_key)
    foundation_winner: SkillGenome | None = None
    capability_winners: list[SkillGenome] = []

    # --- Managed Agents environment (shared across all dimensions) ---
    from skillforge.config import COMPETITOR_BACKEND

    env_id: str | None = None
    managed_client = None
    if COMPETITOR_BACKEND == "managed":
        from skillforge.agents import managed_agents

        try:
            logger.info("run=%s creating managed environment...", run.id[:8])
            managed_client = managed_agents.make_client()
            env_id = await managed_agents.create_environment(
                managed_client, run_id=run.id
            )
            logger.info("run=%s managed environment ready: %s", run.id[:8], env_id)
            await emit(run.id, "managed_environment_ready", environment_id=env_id)
        except Exception as exc:  # noqa: BLE001 — managed-env boundary: any SDK failure must be captured
            logger.exception("run=%s managed environment creation failed", run.id[:8])
            run.status = "failed"
            run.failure_reason = f"managed environment creation failed: {exc}"
            await save_run(run)
            return run

    logger.info(
        "run=%s atomic mode: %d variant_evolutions queued",
        run.id[:8],
        len(pending),
    )

    try:
        for vevo in pending:
            # Apply default population size if the row was created without one
            if vevo.population_size <= 0:
                vevo.population_size = DEFAULT_VARIANT_POP
            if vevo.num_generations <= 0:
                vevo.num_generations = DEFAULT_VARIANT_GENS

            vevo.status = "running"
            await save_variant_evolution(vevo)
            await emit(
                run.id,
                "variant_evolution_started",
                variant_evolution_id=vevo.id,
                dimension=vevo.dimension,
                tier=vevo.tier,
                population_size=vevo.population_size,
            )

            try:
                _variant, winner_genome = await _run_dimension_mini_evolution(
                    run=run,
                    vevo=vevo,
                    foundation_winner=foundation_winner,
                    env_id=env_id,
                )
            except Exception as exc:  # noqa: BLE001 — one bad dimension must not crash the whole atomic run
                logger.exception(
                    "run=%s dimension %s mini-evolution failed",
                    run.id[:8],
                    vevo.dimension,
                )
                vevo.status = "failed"
                await save_variant_evolution(vevo)
                await emit(
                    run.id,
                    "variant_evolution_complete",
                    variant_evolution_id=vevo.id,
                    dimension=vevo.dimension,
                    tier=vevo.tier,
                    status="failed",
                    error=str(exc),
                )
                raise

            await emit(
                run.id,
                "variant_evolution_complete",
                variant_evolution_id=vevo.id,
                dimension=vevo.dimension,
                tier=vevo.tier,
                winner_variant_id=vevo.winner_variant_id,
                status="complete",
            )

            if vevo.tier == "foundation":
                foundation_winner = winner_genome
            else:
                capability_winners.append(winner_genome)

        composite = await _real_assembly(run, foundation_winner, capability_winners)
        run.best_skill = composite
    finally:
        # Tear down managed environment
        if env_id is not None and managed_client is not None:
            try:
                from skillforge.agents import managed_agents as _ma
                await _ma.archive_environment(managed_client, env_id)
                logger.info("run=%s managed environment archived: %s", run.id[:8], env_id)
            except Exception:  # noqa: BLE001
                logger.warning("run=%s managed environment cleanup failed", run.id[:8])
    return run
