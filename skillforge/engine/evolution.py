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

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from skillforge.agents.breeder import breed, publish_findings_to_bible
from skillforge.agents.challenge_designer import design_challenges
from skillforge.agents.competitor import run_competitor
from skillforge.agents.judge.pipeline import run_judging_pipeline
from skillforge.agents.spawner import spawn_from_parent, spawn_gen0
from skillforge.config import COMPETITOR_BACKEND
from skillforge.db.database import init_db
from skillforge.db.queries import save_run
from skillforge.engine.events import emit
from skillforge.engine.sandbox import cleanup_sandbox, create_sandbox
from skillforge.models import EvolutionRun, Generation, SkillGenome

# Module-level registry: run_id -> parent SkillGenome when the run was started
# via fork-and-evolve (seed or upload). Looked up at gen 0 spawn time.
PENDING_PARENTS: dict[str, SkillGenome] = {}

# --- Budget tracking ---------------------------------------------------------
# MVP: estimate cost from trace length. Each SDK turn is ~$0.02 for Sonnet 4.6
# (very rough). Real tracking would read token counts from message metadata;
# for now we use a turn-count approximation plus a flat per-call surcharge.
_COST_PER_TURN_USD = 0.02
_COST_PER_JUDGE_CALL_USD = 0.005


async def _gated_competitor(
    *,
    semaphore: asyncio.Semaphore,
    run_id: str,
    generation: int,
    competitor_idx: int,
    skill,
    challenge,
    env_id: str | None = None,
):
    """Wrap _run_one_competitor in a semaphore acquire/release.

    The semaphore is passed in explicitly rather than closed-over from the
    enclosing loop, so ruff's B023 doesn't flag loop-variable capture and
    the behavior is deterministic even if the engine is refactored to
    interleave generations in the future.

    ``env_id`` is the per-run Managed Agents environment id (only set
    when ``COMPETITOR_BACKEND == "managed"``); ignored by the SDK path.
    """
    async with semaphore:
        return await _run_one_competitor(
            run_id=run_id,
            generation=generation,
            competitor_idx=competitor_idx,
            skill=skill,
            challenge=challenge,
            env_id=env_id,
        )


async def _run_one_competitor(
    run_id: str,
    generation: int,
    competitor_idx: int,
    skill,
    challenge,
    env_id: str | None = None,
):
    """Run a single (skill, challenge) competitor end-to-end.

    Extracted as a module-level function (not a closure) so that parallel
    asyncio.gather over a list comprehension doesn't share loop variables
    across coroutines.

    Branches on ``COMPETITOR_BACKEND``:
      - "sdk":     creates a local sandbox dir, runs the SDK competitor,
                   cleans up the sandbox.
      - "managed": passes the per-run Managed Agents ``env_id`` (no
                   sandbox needed — the cloud container is the sandbox).
    """
    await emit(
        run_id,
        "competitor_started",
        generation=generation,
        competitor=competitor_idx,
        skill_id=skill.id,
        challenge_id=challenge.id,
    )

    if COMPETITOR_BACKEND == "managed":
        if env_id is None:
            raise RuntimeError(
                "managed backend requires a per-run env_id, got None"
            )
        result = await run_competitor(skill, challenge, env_id)
        await emit(
            run_id,
            "competitor_finished",
            generation=generation,
            competitor=competitor_idx,
            skill_id=skill.id,
            challenge_id=challenge.id,
            trace_length=len(result.trace),
        )
        return result

    # SDK path (default)
    sandbox_path = create_sandbox(
        run_id, generation, competitor_idx, skill, challenge
    )
    try:
        result = await run_competitor(skill, challenge, sandbox_path)
        await emit(
            run_id,
            "competitor_finished",
            generation=generation,
            competitor=competitor_idx,
            skill_id=skill.id,
            challenge_id=challenge.id,
            trace_length=len(result.trace),
        )
        return result
    finally:
        cleanup_sandbox(sandbox_path)


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

    # Ensure DB schema exists. init_db is idempotent (CREATE TABLE IF NOT EXISTS).
    # Makes the engine self-contained regardless of caller — tests don't call
    # init_db; the FastAPI lifespan handler does in production but calling it
    # again here is a no-op.
    try:
        await init_db()
    except Exception as exc:  # noqa: BLE001
        print(f"evolution: init_db failed: {exc}")

    await emit(run.id, "run_started", specialization=run.specialization)

    # --- Managed Agents environment (one per run, shared across competitors) -
    # Created up-front when COMPETITOR_BACKEND=managed and torn down in the
    # finally clause. The id is threaded through _gated_competitor → run_competitor
    # so every session in this run uses the same cloud container.
    env_id: str | None = None
    managed_client = None
    if COMPETITOR_BACKEND == "managed":
        from skillforge.agents import managed_agents

        try:
            managed_client = managed_agents.make_client()
            env_id = await managed_agents.create_environment(
                managed_client, run_id=run.id
            )
            await emit(
                run.id,
                "managed_environment_ready",
                environment_id=env_id,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"evolution: failed to create managed environment: {exc}")
            run.status = "failed"
            run.failure_reason = f"managed environment creation failed: {exc}"
            await emit(run.id, "run_failed", reason="env_create_failed")
            await _persist(run)
            return run

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
                seed_parent = PENDING_PARENTS.pop(run.id, None)
                if seed_parent is not None:
                    skills = await spawn_from_parent(seed_parent, run.population_size)
                else:
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

            # --- Competitor execution (semaphore-gated) ---------------
            # Each (skill, challenge) pair runs in its own coroutine, but the
            # total number of concurrent competitors is gated by a semaphore
            # with size config.COMPETITOR_CONCURRENCY.
            #
            # SDK backend default = 1 (sequential) because the Claude Agent
            # SDK's query() wraps a local `claude` CLI subprocess, and N>1
            # causes subprocess file/pipe/auth contention producing "Command
            # failed with exit code 1" on every competitor.
            #
            # Managed Agents backend default = 5 — sessions run in isolated
            # cloud containers with no shared local state, so concurrency
            # is effectively free (parallelism doesn't increase session-hour
            # billing). Both defaults are overridable via
            # SKILLFORGE_COMPETITOR_CONCURRENCY.
            from skillforge.config import COMPETITOR_CONCURRENCY

            semaphore = asyncio.Semaphore(COMPETITOR_CONCURRENCY)

            competitor_tasks = [
                _gated_competitor(
                    semaphore=semaphore,
                    run_id=run.id,
                    generation=gen_num,
                    competitor_idx=competitor_idx,
                    skill=skill,
                    challenge=challenge,
                    env_id=env_id,
                )
                for competitor_idx, skill in enumerate(skills)
                for challenge in run.challenges
            ]
            results = list(await asyncio.gather(*competitor_tasks))

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
        dump_run_json(run)
        await emit(
            run.id,
            "evolution_complete",
            best_skill_id=run.best_skill.id if run.best_skill else None,
            total_cost_usd=run.total_cost_usd,
            generations_completed=len(run.generations),
        )
        return run

    except asyncio.CancelledError:
        # User hit "Cancel" on the arena page. Mark the run cancelled, emit
        # a terminal event so the WebSocket consumer tears down cleanly, and
        # persist whatever generations completed before the cancel.
        import contextlib

        run.status = "cancelled"
        run.failure_reason = "cancelled by user"
        run.completed_at = datetime.now(UTC)
        with contextlib.suppress(Exception):
            await emit(run.id, "run_cancelled", reason="cancelled by user")
        with contextlib.suppress(Exception):
            await _persist(run)
        with contextlib.suppress(Exception):
            dump_run_json(run)
        # Don't re-raise — cancellation is a clean terminal state, not an error
        return run

    except Exception as exc:  # noqa: BLE001
        import contextlib

        run.status = "failed"
        run.failure_reason = f"unhandled error: {exc}"
        await emit(run.id, "run_failed", reason=str(exc))
        with contextlib.suppress(Exception):
            await _persist(run)
        with contextlib.suppress(Exception):
            dump_run_json(run)
        raise

    finally:
        # Tear down the per-run Managed Agents environment + close the
        # shared client. Best-effort: never raise from cleanup.
        if env_id is not None and managed_client is not None:
            import contextlib as _contextlib

            from skillforge.agents import managed_agents as _ma

            with _contextlib.suppress(Exception):
                await _ma.archive_environment(managed_client, env_id)
            with _contextlib.suppress(Exception):
                await managed_client.close()


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


def dump_run_json(run: EvolutionRun) -> Path | None:
    """Write the full run state as a JSON file to ``RUN_DUMPS_DIR/{run_id}.json``.

    This is the user-facing inspection artifact — a human-readable dump of
    every Challenge, Generation, Skill, and CompetitionResult in the run,
    including all traces, scores, and trait attributions. Lives alongside
    (not instead of) the SQLite DB.

    Returns the path written, or ``None`` on failure (non-fatal).
    """
    import json

    from skillforge.config import RUN_DUMPS_DIR

    try:
        RUN_DUMPS_DIR.mkdir(parents=True, exist_ok=True)
        path = RUN_DUMPS_DIR / f"{run.id}.json"
        path.write_text(json.dumps(run.to_dict(), indent=2, default=str))
        return path
    except Exception as exc:  # noqa: BLE001
        print(f"evolution: run JSON dump failed: {exc}")
        return None
