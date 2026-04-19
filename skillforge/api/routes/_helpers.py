"""Shared helpers for the routes submodules.

Kept out of ``__init__.py`` so the barrel stays focused on wiring the
router hierarchy, and out of the route modules so both ``evolve.py``
and ``runs.py`` can import the same classifier implementation.
"""

from __future__ import annotations

import logging

from skillforge.models import EvolutionRun

logger = logging.getLogger("skillforge.api")


async def classify_run_via_taxonomist(
    run: EvolutionRun, requested_mode: str | None
) -> None:
    """Best-effort: classify the run, persist family + new nodes, stamp the run.

    Sets ``run.family_id`` and ``run.evolution_mode`` in place. If
    ``requested_mode`` is "atomic" or "molecular" the explicit value wins
    over whatever the Taxonomist returns. If the Taxonomist call fails for
    any reason — missing API key, network error, JSON parse failure — we
    log it, leave ``family_id`` as None, default ``evolution_mode`` to
    "molecular", and let the run proceed.
    """
    from skillforge.config import ANTHROPIC_API_KEY
    from skillforge.db import get_taxonomy_tree, list_families
    from skillforge.engine.events import emit

    # No API key → skip classification entirely
    if not ANTHROPIC_API_KEY:
        run.evolution_mode = requested_mode or "molecular"
        return

    # Skip the LLM call when the caller explicitly forced a mode AND specified
    # no specialization that needs classification (the autoclassify is the
    # whole point of running the agent — if mode is forced, just stamp it).
    if requested_mode in {"atomic", "molecular"} and not run.specialization:
        run.evolution_mode = requested_mode
        return

    try:
        from skillforge.agents.taxonomist import classify_and_decompose

        taxonomy_tree = await get_taxonomy_tree()
        existing_families = await list_families()
        result = await classify_and_decompose(
            run.specialization,
            taxonomy_tree,
            existing_families,
        )
    except Exception:  # noqa: BLE001 — taxonomist best-effort; fall back to molecular
        logger.exception(
            "run=%s taxonomist classification failed — defaulting to molecular",
            run.id[:8],
        )
        run.evolution_mode = requested_mode or "molecular"
        return

    run.family_id = result.family.id
    # Caller's explicit mode wins over the Taxonomist's recommendation
    run.evolution_mode = requested_mode or result.evolution_mode

    await emit(
        run.id,
        "taxonomy_classified",
        family_id=result.family.id,
        family_slug=result.family.slug,
        domain_slug=result.domain.slug,
        focus_slug=result.focus.slug,
        language_slug=result.language.slug,
        evolution_mode=run.evolution_mode,
        created_new_nodes=result.created_new_nodes,
    )

    if result.evolution_mode == "atomic":
        await emit(
            run.id,
            "decomposition_complete",
            dimension_count=len(result.variant_dimensions),
            dimensions=[d.to_dict() for d in result.variant_dimensions],
            reuse_recommendations=[
                r.to_dict() for r in result.reuse_recommendations
            ],
        )

    # Persist a VariantEvolution row per dimension ONLY if the run will
    # actually execute in atomic mode (the final stamped mode, which may
    # have been overridden by the caller). The variant_evolutions FK
    # requires the parent run to exist, so we save_run first.
    if (
        run.evolution_mode == "atomic"
        and result.evolution_mode == "atomic"
        and result.variant_dimensions
    ):
        from datetime import UTC as _UTC
        from datetime import datetime as _dt
        from uuid import uuid4 as _uuid4

        # Insert the parent run row first so the FK on
        # variant_evolutions.parent_run_id is satisfied. save_run is
        # idempotent (INSERT OR REPLACE) so the second save_run later in
        # the route handler is a no-op refresh.
        from skillforge.db import save_run as _save_run
        from skillforge.db import save_variant_evolution
        from skillforge.models import VariantEvolution

        await _save_run(run)

        for dim in result.variant_dimensions:
            await save_variant_evolution(
                VariantEvolution(
                    id=f"vevo_{_uuid4().hex[:12]}",
                    family_id=result.family.id,
                    dimension=dim.name,
                    tier=dim.tier,
                    parent_run_id=run.id,
                    population_size=2,
                    num_generations=1,
                    status="pending",
                    created_at=_dt.now(_UTC),
                )
            )
