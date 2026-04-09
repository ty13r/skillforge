"""Core evolution loop orchestration.

For each generation:
    1. Spawn (gen 0) or breed (gen N+1) competitor Skills
    2. For each Skill × each Challenge: run the Competitor in an isolated sandbox
    3. Run the judging pipeline (L1 -> L5)
    4. Breed the next generation from the ranked results + learning log
    5. Emit WebSocket events throughout
    6. Persist to SQLite
    7. Check budget; abort if exceeded

Phased implementation per PLAN.md §Step 7:
    Phase 1 — single-generation hardcoded
    Phase 2 — multi-generation loop
    Phase 3 — event queue emission
    Phase 4 — DB persistence
    Phase 5 — budget tracking

All five phases are landed in this one module. The engine is fully async and
emits events via skillforge.engine.events; it never touches WebSockets directly.
"""

from __future__ import annotations

from datetime import UTC, datetime

from skillforge.agents.breeder import breed, publish_findings_to_bible
from skillforge.agents.challenge_designer import design_challenges
from skillforge.agents.competitor import run_competitor
from skillforge.agents.judge.pipeline import run_judging_pipeline
from skillforge.agents.spawner import spawn_gen0
from skillforge.db.queries import save_run
from skillforge.engine.events import emit
from skillforge.engine.sandbox import cleanup_sandbox, create_sandbox
from skillforge.models import EvolutionRun, Generation

# --- Budget tracking ---------------------------------------------------------
# MVP: estimate cost from trace length. Each SDK turn is ~$0.02 for Sonnet 4.6
# (very rough). Real tracking would read token counts from message metadata;
# for now we use a turn-count approximation plus a flat per-call surcharge.
_COST_PER_TURN_USD = 0.02
_COST_PER_JUDGE_CALL_USD = 0.005


def _estimate_generation_cost(generation: Generation) -> float:
    """Rough USD estimate for a completed generation's API spend."""
    turn_cost = sum(len(r.trace) for r in generation.results) * _COST_PER_TURN_USD
    # L2 (1/skill) + L3 (1/result diagnosis) + L4 (1 global) + L5 (1/result)
    n_skills = len(generation.skills)
    n_results = len(generation.results)
    judge_calls = n_skills + n_results + 1 + n_results
    judge_cost = judge_calls * _COST_PER_JUDGE_CALL_USD
    return turn_cost + judge_cost


# --- Main entry point --------------------------------------------------------


async def run_evolution(run: EvolutionRun) -> EvolutionRun:
    """Execute a full evolution run end-to-end.

    Returns the updated EvolutionRun with status, generations, Pareto front,
    and best_skill populated. Emits events on the per-run queue throughout.

    Failure mode: any unhandled exception sets status='failed', emits a
    run_failed event, persists the partial run, and re-raises.
    """
    run.status = "running"
    run.created_at = run.created_at or datetime.now(UTC)

    await emit(run.id, "run_started", specialization=run.specialization)

    try:
        # --- Phase 1: design challenges -----------------------------------
        await emit(run.id, "challenge_design_started")
        run.challenges = await design_challenges(run.specialization, n=3)
        for ch in run.challenges:
            await emit(
                run.id,
                "challenge_designed",
                challenge_id=ch.id,
                difficulty=ch.difficulty,
                prompt=ch.prompt[:200],
            )
        await _persist(run)

        # --- Phase 2: generation loop -------------------------------------
        parent_generation: Generation | None = None
        for gen_num in range(run.num_generations):
            await emit(run.id, "generation_started", generation=gen_num)

            # --- Spawn or breed ---------------------------------------
            if gen_num == 0:
                skills = await spawn_gen0(run.specialization, run.population_size)
            else:
                assert parent_generation is not None
                await emit(run.id, "breeding_started", generation=gen_num)
                children, new_lessons, breeding_report = await breed(
                    generation=parent_generation,
                    learning_log=run.learning_log,
                    specialization=run.specialization,
                    target_pop_size=run.population_size,
                )
                skills = children
                run.learning_log.extend(new_lessons)
                parent_generation.breeding_report = breeding_report
                parent_generation.learning_log_entries = new_lessons
                # Publish new findings to the Bible (fire-and-forget; never raises)
                publish_findings_to_bible(new_lessons, run.id, gen_num)
                await emit(
                    run.id,
                    "breeding_report",
                    generation=gen_num,
                    report=breeding_report,
                    new_lessons=new_lessons,
                )

            # --- Competitor execution (sequential for MVP) ------------
            results = []
            for competitor_idx, skill in enumerate(skills):
                for challenge in run.challenges:
                    await emit(
                        run.id,
                        "competitor_started",
                        generation=gen_num,
                        competitor=competitor_idx,
                        skill_id=skill.id,
                        challenge_id=challenge.id,
                    )
                    sandbox_path = create_sandbox(
                        run.id, gen_num, competitor_idx, skill, challenge
                    )
                    try:
                        result = await run_competitor(skill, challenge, sandbox_path)
                        results.append(result)
                        await emit(
                            run.id,
                            "competitor_finished",
                            generation=gen_num,
                            competitor=competitor_idx,
                            skill_id=skill.id,
                            challenge_id=challenge.id,
                            trace_length=len(result.trace),
                        )
                    finally:
                        cleanup_sandbox(sandbox_path)

            # --- Judging pipeline -------------------------------------
            generation = Generation(number=gen_num, skills=skills, results=results)
            await emit(run.id, "judging_started", generation=gen_num)
            generation = await run_judging_pipeline(generation, run.challenges)
            await emit(
                run.id,
                "scores_published",
                generation=gen_num,
                best_fitness=generation.best_fitness,
                avg_fitness=generation.avg_fitness,
                pareto_front=generation.pareto_front,
            )

            # --- Budget tracking --------------------------------------
            gen_cost = _estimate_generation_cost(generation)
            run.total_cost_usd += gen_cost
            await emit(
                run.id,
                "cost_update",
                generation=gen_num,
                generation_cost_usd=round(gen_cost, 4),
                total_cost_usd=round(run.total_cost_usd, 4),
            )

            run.generations.append(generation)
            parent_generation = generation

            await _persist(run)
            await emit(run.id, "generation_complete", generation=gen_num)

            # --- Budget abort ----------------------------------------
            # Use the max_budget_usd attribute if it's been wired through
            # (schema has it but dataclass may not — see Step 3 flagged mismatch).
            budget = getattr(run, "max_budget_usd", 10.0)
            if run.total_cost_usd >= budget:
                run.status = "failed"
                run.failure_reason = f"budget exceeded: ${run.total_cost_usd:.2f} >= ${budget:.2f}"
                await emit(
                    run.id,
                    "run_failed",
                    reason="budget_exceeded",
                    total_cost_usd=run.total_cost_usd,
                )
                await _persist(run)
                return run

        # --- Finalization ------------------------------------------------
        # Pick the best Skill: highest aggregate fitness from the last generation's
        # Pareto front (or simply the highest-fitness Skill if the front is empty).
        final_gen = run.generations[-1] if run.generations else None
        if final_gen and final_gen.skills:
            pareto_skills = [
                s for s in final_gen.skills if s.is_pareto_optimal
            ] or final_gen.skills
            run.pareto_front = pareto_skills
            run.best_skill = max(
                pareto_skills,
                key=lambda s: sum(s.pareto_objectives.values())
                / max(1, len(s.pareto_objectives)),
            )

        run.status = "complete"
        run.completed_at = datetime.now(UTC)
        await _persist(run)
        await emit(
            run.id,
            "evolution_complete",
            best_skill_id=run.best_skill.id if run.best_skill else None,
            total_cost_usd=run.total_cost_usd,
            generations_completed=len(run.generations),
        )
        return run

    except Exception as exc:  # noqa: BLE001
        import contextlib

        run.status = "failed"
        run.failure_reason = f"unhandled error: {exc}"
        await emit(run.id, "run_failed", reason=str(exc))
        with contextlib.suppress(Exception):
            await _persist(run)
        raise


# --- Persistence helper ------------------------------------------------------


async def _persist(run: EvolutionRun) -> None:
    """Save the current run state to SQLite. Errors are logged but not raised.

    The DB layer's save_run cascades to challenges, generations, skills, and
    competition_results automatically.
    """
    try:
        await save_run(run)
    except Exception as exc:  # noqa: BLE001
        # DB persistence failures are non-fatal during a run — the Progress
        # Tracker event stream is the primary truth; DB is a durable backup.
        print(f"evolution: DB persistence failed: {exc}")
