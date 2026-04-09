"""Debug routes — local-only fake event injection for visual UI testing.

POST /api/debug/fake-run spawns a background task that pushes a realistic
sequence of evolution events into the in-process event queue. The frontend
WebSocket consumer reads them as if they came from a real evolution run.

This lets you verify the entire frontend animation surface (sidebar
ProcessFlow diagram, CompetitorCard breathing borders, JudgingPipelinePill
shimmer, LiveFeedLog slide-in, status pulses, fitness chart updates, score
tweens, breeding report) without spending real Anthropic API budget.
"""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from skillforge.engine.events import emit

router = APIRouter(prefix="/api/debug", tags=["debug"])


class FakeRunRequest(BaseModel):
    run_id: str | None = None
    population_size: int = 3
    num_generations: int = 2
    num_challenges: int = 2
    # speed multiplier — 1.0 = real-ish timing, 5.0 = 5x faster
    speed: float = 1.0


class FakeRunResponse(BaseModel):
    run_id: str
    ws_url: str
    detail: str


@router.post("/fake-run", response_model=FakeRunResponse)
async def fake_run(req: FakeRunRequest) -> FakeRunResponse:
    """Spawn a background task that pushes fake events into the queue.

    Returns immediately with the run_id. The frontend should then navigate
    to /runs/{run_id} to watch the WebSocket stream play out.
    """
    run_id = req.run_id or f"fake-{uuid.uuid4().hex[:8]}"
    asyncio.create_task(
        _drive_fake_run(
            run_id=run_id,
            population_size=req.population_size,
            num_generations=req.num_generations,
            num_challenges=req.num_challenges,
            speed=max(0.1, req.speed),
        )
    )
    return FakeRunResponse(
        run_id=run_id,
        ws_url=f"/ws/evolve/{run_id}",
        detail=(
            f"Fake run scheduled. Open http://localhost:5173/runs/{run_id} "
            f"in your browser to watch the animations play."
        ),
    )


# ----------------------------------------------------------------------------
# Fake event generator
# ----------------------------------------------------------------------------


async def _drive_fake_run(
    *,
    run_id: str,
    population_size: int,
    num_generations: int,
    num_challenges: int,
    speed: float,
) -> None:
    """Push a realistic sequence of evolution events into the queue."""

    async def step(seconds: float) -> None:
        """Sleep for `seconds / speed` (realistic-ish pacing)."""
        await asyncio.sleep(seconds / speed)

    challenge_ids = [f"ch-{uuid.uuid4().hex[:8]}" for _ in range(num_challenges)]
    skill_ids_per_gen = [
        [f"sk-g{g}-{uuid.uuid4().hex[:6]}" for _ in range(population_size)]
        for g in range(num_generations)
    ]

    total_cost = 0.0

    # --- run_started ---
    await emit(
        run_id,
        "run_started",
        specialization="(fake demo) Python list comprehensions for data transformation",
    )
    await step(0.5)

    # --- challenge design ---
    await emit(run_id, "challenge_design_started")
    await step(2.5)
    for ch_id in challenge_ids:
        await emit(
            run_id,
            "challenge_designed",
            challenge_id=ch_id,
            difficulty="medium",
            prompt=f"Fake challenge {ch_id[:4]}: write something interesting",
        )
        await step(0.2)

    # --- per-generation loop ---
    for gen_num in range(num_generations):
        await emit(run_id, "generation_started", generation=gen_num)
        await step(0.3)

        # Spawn or breed
        if gen_num == 0:
            # Sit in spawn for a moment so the user sees the active phase
            await step(2.0)
        else:
            await emit(run_id, "breeding_started", generation=gen_num)
            await step(2.5)
            await emit(
                run_id,
                "breeding_report",
                generation=gen_num,
                report=(
                    f"(fake) Generation {gen_num - 1} surfaced strong "
                    f"pipeline-composition traits; carrying forward 2 elites, "
                    f"running diagnostic mutation on the bottom scorer, and "
                    f"spawning 1 wildcard."
                ),
                new_lessons=[
                    f"Fake lesson #{gen_num}.1 — imperative phrasing wins",
                    f"Fake lesson #{gen_num}.2 — bundle helper scripts",
                ],
            )
            await step(0.5)

        # Competitors run sequentially-ish (matches semaphore=1 mode)
        skills = skill_ids_per_gen[gen_num]
        for comp_idx, sk_id in enumerate(skills):
            for ch_id in challenge_ids:
                await emit(
                    run_id,
                    "competitor_started",
                    generation=gen_num,
                    competitor=comp_idx,
                    skill_id=sk_id,
                    challenge_id=ch_id,
                )
                # ~3s "writing/running tests" feels alive without dragging
                await step(3.0)
                await emit(
                    run_id,
                    "competitor_finished",
                    generation=gen_num,
                    competitor=comp_idx,
                    skill_id=sk_id,
                    challenge_id=ch_id,
                    trace_length=12 + comp_idx,
                )
                await step(0.2)

        # Judging pipeline
        await emit(run_id, "judging_started", generation=gen_num)
        await step(3.0)

        # Climbing fitness across generations
        best = 0.45 + 0.12 * gen_num
        avg = best - 0.04
        await emit(
            run_id,
            "scores_published",
            generation=gen_num,
            best_fitness=round(best, 3),
            avg_fitness=round(avg, 3),
            pareto_front=[skills[0], skills[1]] if len(skills) >= 2 else skills,
        )
        await step(0.3)

        gen_cost = 1.2 + 0.4 * gen_num
        total_cost += gen_cost
        await emit(
            run_id,
            "cost_update",
            generation=gen_num,
            generation_cost_usd=round(gen_cost, 3),
            total_cost_usd=round(total_cost, 3),
        )
        await step(0.3)

        await emit(run_id, "generation_complete", generation=gen_num)
        await step(0.5)

    # --- final state ---
    final_skill = skill_ids_per_gen[-1][0]
    await emit(
        run_id,
        "evolution_complete",
        best_skill_id=final_skill,
        total_cost_usd=round(total_cost, 3),
        generations_completed=num_generations,
    )
