"""Debug routes — scripted demo runs that push realistic evolution events.

POST /api/debug/fake-run spawns a background task that plays a scripted
narrative through the in-process event queue. The events are shaped exactly
like a real evolution run, so the entire frontend (sidebar ProcessFlow,
CompetitorCard, JudgingPipelinePill, LiveFeedLog, FitnessChart, BreedingReport)
renders as if a real run were happening.

The script is modeled after a real evolution of a pandas data-cleaning Skill:
realistic challenges, realistic lessons harvested into the bible, climbing
fitness across generations, believable costs. No AI calls — safe for public
demos and animation QA.
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
    population_size: int = 4
    num_generations: int = 3
    num_challenges: int = 3
    # speed multiplier — 1.0 = real-ish timing, 0.5 = half speed (readable demo)
    speed: float = 0.5


class FakeRunResponse(BaseModel):
    run_id: str
    ws_url: str
    detail: str


@router.post("/fake-run", response_model=FakeRunResponse)
async def fake_run(req: FakeRunRequest) -> FakeRunResponse:
    """Spawn a background task that pushes scripted demo events into the queue."""
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
        detail=f"Demo run scheduled. Open /runs/{run_id} to watch.",
    )


# ----------------------------------------------------------------------------
# Scripted narrative
# ----------------------------------------------------------------------------

SPECIALIZATION = (
    "Pandas DataFrame cleaning — handling missing values, deduplication, "
    "type coercion, and schema normalization for messy CSV ingestion"
)

# Realistic challenge prompts, one per slot (cycled if num_challenges > 4)
CHALLENGE_SCRIPT = [
    {
        "difficulty": "medium",
        "prompt": (
            "Load customers.csv, handle mixed-type 'age' column (strings + nulls), "
            "drop rows with >50% missing values, and return a cleaned DataFrame."
        ),
    },
    {
        "difficulty": "hard",
        "prompt": (
            "Detect near-duplicate rows in orders.csv where email casing and "
            "whitespace differ. Return a deduplicated DataFrame preserving the "
            "most-recent entry per duplicate group."
        ),
    },
    {
        "difficulty": "medium",
        "prompt": (
            "Normalize date columns in transactions.csv — multiple formats "
            "(ISO, US, EU) appear in the same column. Coerce to pandas datetime64 "
            "and drop unparseable rows."
        ),
    },
    {
        "difficulty": "hard",
        "prompt": (
            "Join customers.csv and orders.csv on a fuzzy email match. Return a "
            "merged DataFrame with a 'match_confidence' column."
        ),
    },
]

# Per-generation breeding reports + lessons. The lessons tie back to real bible
# patterns so the demo showcases the learning-log → bible feedback loop.
BREEDING_SCRIPT = [
    {
        "report": (
            "Generation 0 surfaced a clear split: 2 candidates leaned on explicit "
            "step-by-step instructions, 2 relied on short prose. The step-by-step "
            "candidates scored 34% higher on correctness. Carrying forward both "
            "elites, running diagnostic mutation on the weakest prose candidate, "
            "and spawning 1 wildcard with aggressive trigger expansion."
        ),
        "new_lessons": [
            "Numbered workflow steps outperform prose for deterministic tasks",
            "Descriptions missing 'Use when...' triggers cost ~40% of routing accuracy",
            "Including 2+ I/O examples lifts correctness from ~60% to ~85%",
        ],
    },
    {
        "report": (
            "Generation 1 revealed that Skills bundling a validate_schema() helper "
            "script beat those embedding validation logic inline (fewer Claude turns, "
            "tighter traces). Promoting 2 elites to 'tested' maturity, running "
            "joint mutation on description + instructions of the mid-tier candidate, "
            "and injecting a wildcard focused on edge-case handling."
        ),
        "new_lessons": [
            "Deterministic helpers as bundled scripts reduce context cost by ~60%",
            "Progressive disclosure: put schema examples in references/, not SKILL.md",
            "Guard against silent dtype coercion — always assert after read_csv",
        ],
    },
    {
        "report": (
            "Generation 2 converged. The top 2 candidates share a pipeline "
            "composition pattern: load → validate → clean → dedupe → coerce → "
            "return. Classification-before-action traits dominated the Pareto "
            "front. Promoting the winner to 'hardened' maturity. Publishing 3 "
            "findings to the Bible."
        ),
        "new_lessons": [
            "Pipeline composition with named stages is the dominant winning trait",
            "Classification-before-action traits appear in 80% of top performers",
            "Wildcards rarely survive past gen 2 — diminishing returns on diversity",
        ],
    },
]

# Per-generation fitness curve — realistic climb with a small wobble
FITNESS_CURVE = [
    (0.52, 0.47),  # gen 0: (best, avg)
    (0.71, 0.63),
    (0.86, 0.79),
    (0.91, 0.84),
]

# Per-generation cost in USD
COST_CURVE = [0.42, 0.58, 0.67, 0.71]


async def _drive_fake_run(
    *,
    run_id: str,
    population_size: int,
    num_generations: int,
    num_challenges: int,
    speed: float,
) -> None:
    """Push a scripted sequence of evolution events into the queue."""

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
    await emit(run_id, "run_started", specialization=SPECIALIZATION)
    await step(0.8)

    # --- challenge design ---
    await emit(run_id, "challenge_design_started")
    await step(2.5)
    for i, ch_id in enumerate(challenge_ids):
        script = CHALLENGE_SCRIPT[i % len(CHALLENGE_SCRIPT)]
        await emit(
            run_id,
            "challenge_designed",
            challenge_id=ch_id,
            difficulty=script["difficulty"],
            prompt=script["prompt"],
        )
        await step(0.4)

    await step(0.6)

    # --- per-generation loop ---
    for gen_num in range(num_generations):
        await emit(run_id, "generation_started", generation=gen_num)
        await step(0.5)

        # Spawn or breed
        if gen_num == 0:
            # Sit in spawn for a moment so the user sees the active phase
            await step(2.5)
        else:
            await emit(run_id, "breeding_started", generation=gen_num)
            await step(2.5)
            script = BREEDING_SCRIPT[min(gen_num - 1, len(BREEDING_SCRIPT) - 1)]
            await emit(
                run_id,
                "breeding_report",
                generation=gen_num,
                report=script["report"],
                new_lessons=script["new_lessons"],
            )
            await step(1.2)

        # Competitors — one per skill, each running every challenge
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
                # ~2.5s "writing/running tests" per challenge
                await step(2.5)
                # Realistic trace length: varies by competitor quality
                trace_length = 8 + comp_idx * 2 + (gen_num * 1)
                await emit(
                    run_id,
                    "competitor_finished",
                    generation=gen_num,
                    competitor=comp_idx,
                    skill_id=sk_id,
                    challenge_id=ch_id,
                    trace_length=trace_length,
                )
                await step(0.3)

        # Judging pipeline — dwell longer so users can see L1→L5 shimmer
        await emit(run_id, "judging_started", generation=gen_num)
        await step(4.0)

        # Climbing fitness across generations with a small dip sometimes
        best, avg = FITNESS_CURVE[min(gen_num, len(FITNESS_CURVE) - 1)]
        await emit(
            run_id,
            "scores_published",
            generation=gen_num,
            best_fitness=best,
            avg_fitness=avg,
            pareto_front=[skills[0], skills[1]] if len(skills) >= 2 else skills,
        )
        await step(0.6)

        gen_cost = COST_CURVE[min(gen_num, len(COST_CURVE) - 1)]
        total_cost += gen_cost
        await emit(
            run_id,
            "cost_update",
            generation=gen_num,
            generation_cost_usd=gen_cost,
            total_cost_usd=round(total_cost, 3),
        )
        await step(0.4)

        await emit(run_id, "generation_complete", generation=gen_num)
        await step(0.8)

    # --- final state ---
    final_skill = skill_ids_per_gen[-1][0]
    await emit(
        run_id,
        "evolution_complete",
        best_skill_id=final_skill,
        total_cost_usd=round(total_cost, 3),
        generations_completed=num_generations,
    )
