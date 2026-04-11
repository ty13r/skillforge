"""Live atomic evolution end-to-end test (gated).

Runs the FULL v2.0 atomic pipeline against the real Anthropic API:

  POST /api/evolve (atomic mode)
    -> Taxonomist classifies the spec into Domain → Focus → Language
    -> persists VariantEvolution rows for the proposed dimensions
    -> run_evolution dispatcher delegates to run_variant_evolution
    -> per-dimension mini-evolution: design_variant_challenge ->
       spawn_variant_gen0 -> Competitor (real SDK) -> judging pipeline
    -> Engineer assembles the composite via assemble_skill
    -> stub integration check (validate_skill_structure)
    -> evolution_complete

Spends real money. Gated behind ``SKILLFORGE_LIVE_TESTS=1``. Budget cap
is set to $5 to stay inside Matt's authorized live-test budget.

Failure mode: any of the LLM-bound stages can return malformed output that
the parsers don't tolerate, prompts can drift, the Engineer can produce
structurally invalid composites — this test is the ONLY thing that catches
those classes of failure. Expect to find 1-3 bugs the first time it runs.
"""

from __future__ import annotations

import asyncio

import pytest

from skillforge.config import LIVE_TESTS
from skillforge.db import (
    get_run,
    get_taxonomy_tree,
    get_variant_evolutions_for_run,
    get_variants_for_family,
    init_db,
    list_families,
    save_run,
)
from skillforge.engine.events import clear_all
from skillforge.engine.evolution import run_evolution
from skillforge.models import EvolutionRun

pytestmark = pytest.mark.asyncio


@pytest.mark.skipif(
    not LIVE_TESTS, reason="Live SDK test — set SKILLFORGE_LIVE_TESTS=1"
)
async def test_atomic_evolution_minimal_live():
    """Run a real atomic evolution end-to-end against the actual API.

    Cost: ~$2-4 (within the authorized $5 live-test budget). Wall time:
    ~5-15 minutes depending on model latency.

    The test does NOT go through ``POST /api/evolve`` — it constructs the
    EvolutionRun + classifies + persists VariantEvolution rows manually
    so we can be precise about the budget cap and avoid the FastAPI test
    client adding noise. The pipeline being exercised is identical:
    everything from the Taxonomist call onward goes through the real
    code path.
    """
    # Clear any leftover event queues from earlier tests
    clear_all()
    await init_db()

    spec = (
        "A skill that generates pytest unit tests for Python data validation "
        "functions, with focused fixtures and parametrized inputs."
    )

    run = EvolutionRun(
        id="run-atomic-live-test",
        mode="domain",
        specialization=spec,
        population_size=2,
        num_generations=1,
        max_budget_usd=5.0,
        evolution_mode="atomic",
    )
    await save_run(run)

    # Step 1: Run the Taxonomist for real and persist VariantEvolution rows
    from datetime import UTC, datetime
    from uuid import uuid4

    from skillforge.agents.taxonomist import classify_and_decompose
    from skillforge.db import save_variant_evolution
    from skillforge.models import VariantEvolution

    taxonomy = await get_taxonomy_tree()
    families = await list_families()
    result = await classify_and_decompose(spec, taxonomy, families)

    print(f"\n[live] Taxonomist returned: family={result.family.slug} "
          f"mode={result.evolution_mode} "
          f"dimensions={[d.name for d in result.variant_dimensions]}")

    # Stamp the family on the run (mirrors what routes.py would do)
    run.family_id = result.family.id

    # If the Taxonomist picked molecular, the test still validates the
    # dispatcher fallback path. If atomic, persist variant_evolutions.
    if result.evolution_mode == "atomic" and result.variant_dimensions:
        for dim in result.variant_dimensions:
            await save_variant_evolution(
                VariantEvolution(
                    id=f"vevo_live_{uuid4().hex[:8]}",
                    family_id=result.family.id,
                    dimension=dim.name,
                    tier=dim.tier,
                    parent_run_id=run.id,
                    population_size=2,
                    num_generations=1,
                    status="pending",
                    created_at=datetime.now(UTC),
                )
            )
    else:
        # Force atomic mode anyway with at least one synthetic dimension so
        # the dispatcher exercises the variant_evolution code path. This
        # makes the test reliable even if the Taxonomist returns molecular.
        print("[live] Taxonomist returned molecular; injecting synthetic "
              "variant_evolution row to force atomic dispatch")
        run.evolution_mode = "atomic"
        await save_variant_evolution(
            VariantEvolution(
                id=f"vevo_live_{uuid4().hex[:8]}",
                family_id=result.family.id,
                dimension="primary-strategy",
                tier="foundation",
                parent_run_id=run.id,
                population_size=2,
                num_generations=1,
                status="pending",
                created_at=datetime.now(UTC),
            )
        )

    await save_run(run)

    # Step 2: Run the dispatcher — this is the actual integration test.
    # Wraps in a 25-minute hard timeout (much longer than expected) so the
    # test fails loudly instead of running for 30+ minutes if something hangs.
    out = await asyncio.wait_for(run_evolution(run), timeout=1500.0)

    print(f"\n[live] run_evolution returned: status={out.status} "
          f"cost=${out.total_cost_usd:.2f} "
          f"best_skill={out.best_skill.id if out.best_skill else None}")

    # The contract: the run must not have failed catastrophically, must
    # have spent some money, must have a best_skill, and must be under
    # budget.
    assert out.status == "complete", (
        f"atomic run did not complete: status={out.status} "
        f"failure_reason={out.failure_reason}"
    )
    assert out.best_skill is not None, "atomic run produced no best_skill"
    assert out.total_cost_usd > 0.0, "no cost recorded — did the LLM actually run?"
    assert out.total_cost_usd < 5.0, (
        f"atomic run blew budget: ${out.total_cost_usd:.2f} >= $5.00"
    )

    # The variant evolutions for this run should all be terminal
    vevos = await get_variant_evolutions_for_run(run.id)
    assert vevos, "no variant_evolutions persisted for the run"
    for vevo in vevos:
        assert vevo.status in {"complete", "failed"}, (
            f"vevo {vevo.id} ({vevo.dimension}) stuck in status={vevo.status}"
        )

    # The family should now have a best_assembly_id
    refetched_run = await get_run(run.id)
    assert refetched_run is not None
    families_after = await list_families()
    family = next(
        (f for f in families_after if f.id == result.family.id), None
    )
    assert family is not None, "family disappeared after the run"

    # Variants persisted for the dimensions we processed
    variants = await get_variants_for_family(result.family.id)
    print(f"[live] Variants persisted: {len(variants)} "
          f"({[(v.dimension, v.tier, round(v.fitness_score, 3)) for v in variants]})")
    assert variants, "no variants persisted for the family after the run"

    # Note on family.best_assembly_id: the assembly engine sets this on the
    # family object passed to it, but only when assemble_skill is called
    # (not the capability-only fallback). For a single-foundation run with
    # no capabilities, the orchestrator's _real_assembly takes the
    # capability-only fallback path which doesn't update the family — so
    # this assertion is conditional.
    if any(v.tier == "foundation" for v in variants) and any(
        v.tier == "capability" for v in variants
    ):
        assert family.best_assembly_id is not None, (
            "family.best_assembly_id not stamped after assembly with foundation+capabilities"
        )
        print(f"[live] family.best_assembly_id={family.best_assembly_id}")
