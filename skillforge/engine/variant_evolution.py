"""Variant evolution orchestrator (v2.0 Wave 3-1).

Atomic-mode entry point. When ``run.evolution_mode == "atomic"`` the parent
``run_evolution`` dispatcher delegates here. The orchestrator runs one
mini-evolution per variant dimension recorded against the parent run, then
calls a stub assembly step that returns the winning foundation as the
composite skill (Phase 4 will replace the stub with the real Engineer).

Per-dimension flow:

  1. Read all ``variant_evolutions`` rows for ``run.id``, sorted so
     foundation dimensions come before capability dimensions.
  2. For each dimension, run a tiny mini-evolution:
       a. Mark the row ``status="running"``, emit
          ``variant_evolution_started``.
       b. Design ONE focused challenge via
          ``challenge_designer.design_variant_challenge``.
       c. Spawn ``population_size`` variants via
          ``spawner.spawn_variant_gen0`` — capability variants receive the
          winning foundation as grounding context.
       d. Run each spawned variant through the Competitor against the
          single focused challenge.
       e. Run the judging pipeline against the gathered results.
       f. Pick the highest-fitness variant as the winner. Persist it as a
          ``Variant`` row tied back to the family + the
          ``VariantEvolution`` id.
       g. Mark the ``VariantEvolution`` row ``status="complete"`` with
          ``winner_variant_id`` and ``completed_at``. Emit
          ``variant_evolution_complete``.
  3. After every dimension is done, call the assembly stub.
     The Phase 4 Engineer will replace this stub.
  4. Set ``run.best_skill`` to the assembled composite, persist, and let
     the parent ``run_evolution`` finalize.

The mini-evolutions reuse existing helpers (Spawner, Competitor, judging
pipeline) directly rather than recursing into ``run_evolution`` itself.
Recursion would force a second event loop and complicate the parent run's
event stream — direct helper calls keep the event order deterministic and
the wall-clock budget bounded.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from skillforge.db.queries import (
    get_variant_evolutions_for_run,
    get_variants_for_family,
    save_challenge,
    save_genome,
    save_run,
    save_variant,
    save_variant_evolution,
)
from skillforge.engine.events import emit
from skillforge.models import (
    Generation,
    SkillGenome,
    Variant,
    VariantEvolution,
)
from skillforge.models.run import EvolutionRun

logger = logging.getLogger("skillforge.engine.variant_evolution")

# Atomic-mode defaults — small populations because the per-dimension
# challenge is narrow. Wave 1 of Phase 3 keeps gen=1 (no breeding loop yet);
# Wave 4 will introduce per-dimension breeding.
DEFAULT_VARIANT_POP = 2
# Post-v2.0 item 4: multi-generation breeding loops are now supported inside
# _run_dimension_mini_evolution. Bumped to 2 so the default produces one
# round of breeding after gen 0. Existing VariantEvolution rows with
# ``num_generations=1`` still work — the loop collapses to a single pass.
DEFAULT_VARIANT_GENS = 2
DEFAULT_VARIANT_CONCURRENCY = 3


def _tier_sort_key(ve: VariantEvolution) -> tuple[int, str]:
    """Sort foundation dimensions before capability dimensions."""
    order = {"foundation": 0, "capability": 1}
    return (order.get(ve.tier, 99), ve.dimension)


def _aggregate_fitness(skill: SkillGenome) -> float:
    """Compute a single fitness number for ranking variants."""
    if skill.pareto_objectives:
        vals = list(skill.pareto_objectives.values())
        return sum(vals) / max(1, len(vals))
    if skill.deterministic_scores:
        vals = list(skill.deterministic_scores.values())
        return sum(vals) / max(1, len(vals))
    return 0.0


async def _run_dimension_mini_evolution(
    *,
    run: EvolutionRun,
    vevo: VariantEvolution,
    foundation_winner: SkillGenome | None,
    env_id: str | None = None,
) -> tuple[Variant, SkillGenome]:
    """Run one mini-evolution and return the winning variant + its genome.

    Imports the Spawner / Challenge Designer / Competitor / judge pipeline
    locally so the orchestrator stays import-cheap and tests can monkeypatch
    each stage independently.
    """
    from skillforge.agents.breeder import breed
    from skillforge.agents.challenge_designer import design_variant_challenge
    from skillforge.agents.judge.pipeline import run_judging_pipeline
    from skillforge.agents.spawner import spawn_variant_gen0
    from skillforge.db.queries import get_family
    from skillforge.engine.evolution import _gated_competitor
    from skillforge.engine.scorer import score_competitor, scores_to_pareto_objectives
    from skillforge.engine.transcript_logger import log_competitor_dispatch

    dimension_spec = {
        "name": vevo.dimension,
        "tier": vevo.tier,
        "description": "",  # Phase 3 stub — Phase 4 stores full dimension
        "evaluation_focus": "",
    }

    # 1. Design the focused challenge for this dimension and persist it
    # so the FK on variant_evolutions.challenge_id resolves.
    await emit(
        run.id,
        "dimension_phase",
        dimension=vevo.dimension,
        phase="designing_challenge",
        detail="Designing a focused challenge for this dimension...",
    )
    challenge = await design_variant_challenge(
        specialization=run.specialization,
        dimension=dimension_spec,
    )
    await save_challenge(challenge, run.id)
    vevo.challenge_id = challenge.id
    await save_variant_evolution(vevo)

    # 2. Multi-generation mini-evolution loop (post-v2.0 item 4):
    #    gen 0: spawn → compete → judge → score
    #    gen 1..N-1: breed from previous gen → compete → judge → score
    #    pick best across ALL generations as the winning variant
    #
    # When vevo.num_generations <= 1 this collapses to a single spawn/score
    # pass, matching the Phase 3 behavior.
    semaphore = asyncio.Semaphore(DEFAULT_VARIANT_CONCURRENCY)
    generation: Generation | None = None
    best_genome: SkillGenome | None = None
    best_fitness_seen: float = -1.0
    num_gens = max(1, vevo.num_generations)

    for gen_num in range(num_gens):
        # Spawn gen 0 from scratch; breed gen 1+ from the previous generation
        if gen_num == 0:
            await emit(
                run.id,
                "dimension_phase",
                dimension=vevo.dimension,
                phase="spawning_variants",
                detail=f"Spawning {vevo.population_size} skill variants (this takes 1-2 minutes)...",
            )
            current_skills = await spawn_variant_gen0(
                specialization=run.specialization,
                dimension=dimension_spec,
                foundation_genome=foundation_winner,
                pop_size=vevo.population_size,
            )
        else:
            assert generation is not None
            try:
                children, _lessons, _report = await breed(
                    generation=generation,
                    learning_log=list(run.learning_log),
                    specialization=f"{run.specialization} [{vevo.dimension}]",
                    target_pop_size=vevo.population_size,
                )
                current_skills = children if children else generation.skills
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "run=%s dimension %s breeding failed at gen %d: %s — "
                    "keeping previous generation",
                    run.id[:8],
                    vevo.dimension,
                    gen_num,
                    exc,
                )
                current_skills = generation.skills

        # Persist genomes so the save_variant FK to skill_genomes resolves
        for genome in current_skills:
            genome.generation = gen_num
            await save_genome(genome, run.id)

        # Add a baseline competitor (raw model, no skill) for comparison.
        # The baseline genome has no skill_md_content, so the agent runs
        # the challenge without any skill guidance — pure model capability.
        baseline_genome = SkillGenome(
            id=f"baseline_{uuid.uuid4().hex[:8]}",
            generation=gen_num,
            skill_md_content="",
            supporting_files={},
            traits=["baseline", "no-skill"],
            meta_strategy="Raw model baseline — no skill guidance",
            mutations=["baseline"],
        )

        # Compete: baseline first (idx 0), then skill variants (idx 1+)
        all_competitors = [baseline_genome] + list(current_skills)
        competitor_tasks = [
            _gated_competitor(
                semaphore=semaphore,
                run_id=run.id,
                generation=gen_num,
                competitor_idx=idx,
                skill=skill,
                challenge=challenge,
                env_id=env_id,
            )
            for idx, skill in enumerate(all_competitors)
        ]
        results = list(await asyncio.gather(*competitor_tasks))

        # Separate baseline result from skill results for scoring/selection.
        # The baseline is idx 0; skill variants are idx 1+.
        skill_results = results[1:]

        # --- Composite scoring (Phase 6) ---
        # Resolve family slug for the scorer
        family_slug = None
        family = await get_family(vevo.family_id) if vevo.family_id else None
        if family:
            family_slug = family.slug

        if family_slug:
            # Build challenge data dict for the scorer (challenge is in-memory, not on disk)
            challenge_data = {
                "id": challenge.id,
                "prompt": challenge.prompt,
                "difficulty": challenge.difficulty,
                "evaluation_criteria": challenge.evaluation_criteria if hasattr(challenge, "evaluation_criteria") else {},
            }

            # Score ALL competitors (including baseline) with the composite scorer
            all_genomes = [baseline_genome] + list(current_skills)
            for result in results:
                if not result.output_files:
                    continue
                try:
                    scores = await score_competitor(
                        family_slug=family_slug,
                        challenge_id=challenge.id,
                        challenge_data=challenge_data,
                        output_files=result.output_files,
                        run_behavioral=True,
                    )
                    # Merge composite objectives into the matching genome
                    objectives = scores_to_pareto_objectives(scores)
                    for genome in all_genomes:
                        if genome.id == result.skill_id:
                            genome.pareto_objectives = objectives
                            genome.deterministic_scores = {
                                "composite": scores.get("composite", 0.0),
                                "l0": scores.get("l0", {}).get("score", 0.0) if isinstance(scores.get("l0"), dict) else 0.0,
                                "compiles": scores.get("compile", {}).get("compiles", False) if isinstance(scores.get("compile"), dict) else False,
                            }
                            break

                    # Log the dispatch transcript
                    from skillforge.config import model_for
                    await log_competitor_dispatch(
                        run_id=run.id,
                        family_slug=family_slug,
                        challenge_id=challenge.id,
                        skill_id=result.skill_id,
                        model=model_for("competitor"),
                        result=result,
                        scores=scores,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "run=%s composite scoring failed for skill %s: %s",
                        run.id[:8], result.skill_id, exc,
                    )
        else:
            logger.warning(
                "run=%s dimension %s: family_slug not resolved, skipping composite scoring",
                run.id[:8],
                vevo.dimension,
            )

        # Judge — only skill variants, not the baseline (baseline is for
        # comparison only and should not participate in winner selection)
        generation = Generation(
            number=gen_num, skills=current_skills, results=skill_results
        )
        generation = await run_judging_pipeline(
            generation, [challenge], run_id=run.id
        )

        # Track cost for this generation — atomic mode used to skip this,
        # which made total_cost_usd stuck at 0.0. Fixed in item 1 of the
        # post-v2.0 polish pass.
        from skillforge.engine.evolution import _estimate_generation_cost

        gen_cost = _estimate_generation_cost(generation)
        run.total_cost_usd += gen_cost
        # Persist the updated cost immediately so budget checks see real
        # numbers and the frontend can read the in-flight total. Without
        # this, the cost only lands in the DB when run_evolution returns.
        await save_run(run)
        await emit(
            run.id,
            "cost_update",
            generation=gen_num,
            dimension=vevo.dimension,
            generation_cost_usd=round(gen_cost, 4),
            total_cost_usd=round(run.total_cost_usd, 4),
        )

        # Budget enforcement — atomic mode used to skip this. If the
        # accumulated cost exceeds max_budget_usd, mark the run failed
        # and bail out of the remaining dimensions.
        budget = getattr(run, "max_budget_usd", 10.0)
        if run.total_cost_usd >= budget:
            logger.warning(
                "run=%s atomic mode: budget exceeded ($%.2f >= $%.2f), "
                "aborting remaining dimensions",
                run.id[:8],
                run.total_cost_usd,
                budget,
            )
            run.status = "failed"
            run.failure_reason = (
                f"budget exceeded: ${run.total_cost_usd:.2f} >= ${budget:.2f}"
            )
            await emit(
                run.id,
                "run_failed",
                reason="budget_exceeded",
                total_cost_usd=run.total_cost_usd,
            )
            # Save the winner we have so far as the result, then bail
            vevo.status = "failed"
            await save_variant_evolution(vevo)
            raise RuntimeError("atomic: budget exceeded during mini-evolution")

        # Track the best genome across all generations so far
        if generation.skills:
            gen_best = max(generation.skills, key=_aggregate_fitness)
            gen_best_fitness = _aggregate_fitness(gen_best)
            if gen_best_fitness > best_fitness_seen:
                best_genome = gen_best
                best_fitness_seen = gen_best_fitness

    if best_genome is None:
        raise RuntimeError(
            f"variant evolution {vevo.id}: no skills produced for dimension {vevo.dimension}"
        )

    winner_genome = best_genome
    winner_fitness = best_fitness_seen

    # Deactivate any existing active variants in this (family, dimension)
    # before stamping the new winner as active. Without this, re-running an
    # evolution on the same family leaves the previous winner active too,
    # violating the "exactly one active variant per (family, dimension)"
    # invariant — which swap-variant and the frontend rely on.
    existing_in_dim = await get_variants_for_family(
        vevo.family_id, dimension=vevo.dimension
    )
    for existing in existing_in_dim:
        if existing.is_active:
            existing.is_active = False
            await save_variant(existing)

    variant = Variant(
        id=f"var_{uuid.uuid4().hex[:12]}",
        family_id=vevo.family_id,
        dimension=vevo.dimension,
        tier=vevo.tier,
        genome_id=winner_genome.id,
        fitness_score=winner_fitness,
        is_active=True,
        evolution_id=vevo.id,
        created_at=datetime.now(UTC),
    )
    await save_variant(variant)

    # Stamp variant_id back on the genome row for round-trip
    winner_genome.variant_id = variant.id
    await save_genome(winner_genome, run.id)

    # 6. Mark the variant evolution complete
    vevo.status = "complete"
    vevo.winner_variant_id = variant.id
    vevo.completed_at = datetime.now(UTC)
    if vevo.tier == "capability" and foundation_winner is not None:
        vevo.foundation_genome_id = foundation_winner.id
    await save_variant_evolution(vevo)

    return variant, winner_genome


async def _real_assembly(
    run: EvolutionRun,
    foundation_winner: SkillGenome | None,
    capability_winners: list[SkillGenome],
) -> SkillGenome:
    """Phase 4 real assembly — invoke the Engineer agent + integration test.

    Falls back to a "use the highest-fitness winner as-is" path when no
    foundation variant exists (some atomic decompositions only have
    capability dimensions). Otherwise runs the full Engineer flow:
    weave → validate → optionally refine → persist composite.
    """
    if foundation_winner is None:
        if not capability_winners:
            raise RuntimeError("assembly: no winners to assemble from")
        # Edge case: no foundation tier in this decomposition. Use the
        # highest-fitness capability as the de facto skeleton and emit
        # a stub assembly_complete. Wave 4 polish will extend the
        # Engineer to handle capability-only assemblies.
        await emit(
            run.id,
            "assembly_started",
            capability_count=len(capability_winners),
            mode="capability_only_fallback",
        )
        composite = max(capability_winners, key=_aggregate_fitness)
        await emit(
            run.id,
            "assembly_complete",
            composite_skill_id=composite.id,
            capability_count=len(capability_winners),
            integration_passed=True,
            mode="capability_only_fallback",
        )
        return composite

    # Resolve the family for the Engineer call
    from skillforge.db.queries import get_family

    family = await get_family(run.family_id) if run.family_id else None
    if family is None:
        # Defensive fallback — synthesize a minimal SkillFamily so the
        # Engineer call still has metadata to work with. The orchestrator
        # logs a warning but doesn't block.
        from skillforge.models import SkillFamily

        logger.warning(
            "run=%s atomic assembly: no family found for family_id=%s; "
            "using a synthesized SkillFamily for the Engineer call",
            run.id[:8],
            run.family_id,
        )
        family = SkillFamily(
            id=run.family_id or "fam_unknown",
            slug="composite",
            label="Composite",
            specialization=run.specialization,
        )

    from skillforge.engine.assembly import assemble_skill

    composite, _report = await assemble_skill(
        run, family, foundation_winner, capability_winners
    )
    return composite


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
        except Exception as exc:  # noqa: BLE001
            logger.error("run=%s managed environment creation failed: %s", run.id[:8], exc)
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
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "run=%s dimension %s mini-evolution failed: %s",
                    run.id[:8],
                    vevo.dimension,
                    exc,
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
