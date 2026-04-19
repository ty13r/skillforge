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

from fastapi import APIRouter, HTTPException
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


DEMO_RUN_ID = "demo-live"
_demo_task: asyncio.Task | None = None


@router.post("/demo")
async def ensure_demo() -> dict:
    """Ensure the permanent demo run is active.

    If the demo is already running, returns immediately. Otherwise starts
    a fresh one. The frontend calls this on mount so the demo is always warm.
    """
    global _demo_task
    if _demo_task is not None and not _demo_task.done():
        return {"run_id": DEMO_RUN_ID, "status": "already_running"}

    async def _loop_demo() -> None:
        """Run the demo on repeat with a pause between iterations."""
        while True:
            await _drive_fake_run(
                run_id=DEMO_RUN_ID,
                population_size=2,
                num_generations=1,
                num_challenges=1,
                speed=0.5,
            )
            await asyncio.sleep(5)  # pause between loops

    _demo_task = asyncio.create_task(_loop_demo())
    return {"run_id": DEMO_RUN_ID, "status": "started"}


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
    "Elixir Phoenix LiveView — component-forward architecture with verified "
    "routes, HEEx, streams, forms, and real-time patterns"
)

# Sample output code for the demo — one per competitor type per dimension.
# The baseline uses old Phoenix idioms; seed uses modern ones; spawn tries alternatives.
def _demo_output(dim: str, variant: str) -> dict[str, str]:
    """Return realistic Elixir code for a demo competitor output."""
    module = dim.replace("-", "_").title().replace("_", "")
    filename = f"lib/my_app_web/live/{dim.replace('-', '_')}_live.ex"

    if variant == "baseline":
        return {filename: f'''\
defmodule MyAppWeb.{module}Live do
  use MyAppWeb, :live_view

  def mount(_params, _session, socket) do
    items = MyApp.Repo.all(MyApp.{module})
    {{:ok, assign(socket, :items, items)}}
  end

  def render(assigns) do
    ~H"""
    <div>
      <%%= for item <- @items do %>
        <div><%%= item.name %></div>
      <%% end %>
    </div>
    """
  end
end
'''}
    if variant == "seed":
        return {filename: f'''\
defmodule MyAppWeb.{module}Live do
  use MyAppWeb, :live_view

  def mount(_params, _session, socket) do
    {{:ok,
     socket
     |> assign_async(:items, fn ->
       {{:ok, %{{items: MyApp.{module}.list_items()}}}}
     end)}}
  end

  def render(assigns) do
    ~H"""
    <div :if={{@items.loading}}>Loading...</div>
    <div :if={{@items.ok?}}>
      <div :for={{item <- @items.result}} id={{item.id}}>
        <%%= item.name %>
      </div>
    </div>
    """
  end
end
'''}
    # spawn
    return {filename: f'''\
defmodule MyAppWeb.{module}Live do
  use MyAppWeb, :live_view

  def mount(_params, _session, socket) do
    {{:ok, stream(socket, :items, MyApp.{module}.list_items())}}
  end

  def render(assigns) do
    ~H"""
    <div id="items" phx-update="stream">
      <div :for={{{{id, item}} <- @streams.items}} id={{id}}>
        <.link navigate={{~p"/items/#{{item}}"}}>
          <%%= item.name %>
        </.link>
      </div>
    </div>
    """
  end
end
'''}


import random as _random  # noqa: E402  (placed after scripted narrative blocks)


def _demo_scores(variant: str, base_fitness: float) -> dict:
    """Generate realistic per-competitor composite score breakdowns."""
    if variant == "baseline":
        # Raw Sonnet: good L0, often compiles, weak behavioral
        return {
            "composite": round(base_fitness - 0.08 + _random.uniform(-0.03, 0.03), 3),
            "l0": round(0.85 + _random.uniform(-0.1, 0.1), 3),
            "compile": _random.random() > 0.3,
            "ast": round(0.15 + _random.uniform(0, 0.2), 3),
            "behavioral": round(0.05 + _random.uniform(0, 0.1), 3),
            "template": round(0.5 + _random.uniform(0, 0.3), 3),
            "brevity": round(0.8 + _random.uniform(0, 0.2), 3),
        }
    if variant == "seed":
        # Seed skill: strong across the board
        return {
            "composite": round(base_fitness + _random.uniform(-0.02, 0.04), 3),
            "l0": round(0.9 + _random.uniform(-0.05, 0.05), 3),
            "compile": _random.random() > 0.1,
            "ast": round(0.4 + _random.uniform(0, 0.3), 3),
            "behavioral": round(0.3 + _random.uniform(0, 0.4), 3),
            "template": round(0.8 + _random.uniform(0, 0.2), 3),
            "brevity": round(0.85 + _random.uniform(0, 0.15), 3),
        }
    # spawn
    # Spawn: variable, sometimes beats seed
    return {
        "composite": round(base_fitness - 0.04 + _random.uniform(-0.05, 0.08), 3),
        "l0": round(0.8 + _random.uniform(-0.1, 0.15), 3),
        "compile": _random.random() > 0.2,
        "ast": round(0.3 + _random.uniform(0, 0.35), 3),
        "behavioral": round(0.15 + _random.uniform(0, 0.5), 3),
        "template": round(0.7 + _random.uniform(0, 0.3), 3),
        "brevity": round(0.75 + _random.uniform(0, 0.25), 3),
    }


# Atomic demo: dimension-by-dimension evolution, not generation-based.
# Modeled after the real elixir-phoenix-liveview seed run.
DIMENSION_SCRIPT = [
    {"dimension": "architectural-stance", "tier": "foundation", "fitness": 0.54,
     "challenge": {"difficulty": "hard", "prompt": "The fixture has DB queries in mount/3 causing double-execution. Refactor to use assign_async/3 and handle the loading/ok?/failed states."}},
    {"dimension": "heex-and-verified-routes", "tier": "capability", "fitness": 0.45,
     "challenge": {"difficulty": "medium", "prompt": "Convert a Phoenix 1.6 template using Routes.*_path helpers and live_link to 1.7+ verified routes with ~p sigil and <.link> components."}},
    {"dimension": "function-components-and-slots", "tier": "capability", "fitness": 0.45,
     "challenge": {"difficulty": "medium", "prompt": "Extract a status badge into a function component with attr declarations. Support a named :actions slot. Validate with render_component/2 test."}},
    {"dimension": "live-components-stateful", "tier": "capability", "fitness": 0.56,
     "challenge": {"difficulty": "hard", "prompt": "Build a filter panel as a stateful LiveComponent. All prop-to-assign mapping must happen in update/2. Parent communicates via send_update/2."}},
    {"dimension": "form-handling", "tier": "capability", "fitness": 0.52,
     "challenge": {"difficulty": "hard", "prompt": "Implement nested forms with cast_assoc, <.inputs_for>, and sort_param/drop_param for adding/removing child rows. Handle validate and save events."}},
    {"dimension": "mount-and-lifecycle", "tier": "capability", "fitness": 0.55,
     "challenge": {"difficulty": "medium", "prompt": "Refactor a LiveView that calls Repo.all in mount/3 to use assign_async/3. Handle loading, ok?, and failed states in the template."}},
    {"dimension": "event-handlers-and-handle-info", "tier": "capability", "fitness": 0.48,
     "challenge": {"difficulty": "hard", "prompt": "Implement an Action struct funnel: handle_event parses params into %Action{}, delegates to handle_action/2. Route handle_info through the same funnel."}},
    {"dimension": "streams-and-collections", "tier": "capability", "fitness": 0.48,
     "challenge": {"difficulty": "medium", "prompt": "Replace an @messages assign holding 500+ items with stream/3. Support stream_insert for new messages from PubSub and stream_delete for removal."}},
    {"dimension": "pubsub-and-realtime", "tier": "capability", "fitness": 0.56,
     "challenge": {"difficulty": "hard", "prompt": "Wire PubSub broadcasts through the Ecto context (not handle_event). Subscribe in mount with connected? guard. Handle message_created, message_updated, message_deleted."}},
    {"dimension": "navigation-patterns", "tier": "capability", "fitness": 0.45,
     "challenge": {"difficulty": "medium", "prompt": "Implement sort/filter via push_patch with handle_params. Use push_navigate for cross-LiveView transitions. No deprecated helpers."}},
    {"dimension": "auth-and-authz", "tier": "capability", "fitness": 0.46,
     "challenge": {"difficulty": "hard", "prompt": "Build an on_mount hook that authenticates the user AND authorizes access to params[\"id\"]. Use live_session scoping. No re-fetching in mount/3."}},
    {"dimension": "anti-patterns-catalog", "tier": "capability", "fitness": 0.53,
     "challenge": {"difficulty": "medium", "prompt": "Given a LiveView with 5 anti-patterns (DB in mount, unguarded PubSub, Routes._path, bare changeset in form, large list in assigns), fix all 5 with detectors."}},
]


async def _drive_fake_run(
    *,
    run_id: str,
    population_size: int,
    num_generations: int,
    num_challenges: int,
    speed: float,
) -> None:
    """Push a scripted atomic evolution sequence into the event queue.

    Simulates dimension-by-dimension evolution: for each dimension, design a
    challenge, spawn 2 variants, compete them, judge, and pick a winner.
    """

    async def step(seconds: float) -> None:
        await asyncio.sleep(seconds / speed)

    total_cost = 0.0

    # --- run_started ---
    await emit(run_id, "run_started", specialization=SPECIALIZATION)
    # Wait for the WebSocket to connect before emitting structural events.
    # Uses max(2s, step(2s)) so tests run fast but live demos give the
    # browser enough time to navigate + load JS + open the WebSocket.
    await asyncio.sleep(max(2.0, 2.0 / speed))

    # --- taxonomy + decomposition ---
    family_id = f"fam_{uuid.uuid4().hex[:12]}"
    dim_names = [d["dimension"] for d in DIMENSION_SCRIPT]
    await emit(
        run_id,
        "taxonomy_classified",
        family_id=family_id,
        family_slug="elixir-phoenix-liveview",
        domain_slug="web-frameworks",
        focus_slug="full-stack",
        language_slug="elixir",
        evolution_mode="atomic",
        created_new_nodes=[],
    )
    await step(0.8)
    await emit(
        run_id,
        "decomposition_complete",
        dimension_count=len(dim_names),
        dimensions=[
            {"name": d["dimension"], "tier": d["tier"],
             "description": f"Focused on {d['dimension'].replace('-', ' ')}",
             "evaluation_focus": d["challenge"]["difficulty"]}
            for d in DIMENSION_SCRIPT
        ],
        reuse_recommendations=[],
    )
    await step(1.0)

    # --- per-dimension mini-evolution ---
    for _dim_idx, dim in enumerate(DIMENSION_SCRIPT):
        vevo_id = f"vevo_{uuid.uuid4().hex[:12]}"

        await emit(
            run_id,
            "variant_evolution_started",
            variant_evolution_id=vevo_id,
            dimension=dim["dimension"],
            tier=dim["tier"],
            population_size=2,
        )
        await step(0.5)

        # Design one challenge
        ch_id = f"ch-{uuid.uuid4().hex[:8]}"
        await emit(run_id, "challenge_design_started")
        await step(1.0)
        await emit(
            run_id,
            "challenge_designed",
            challenge_id=ch_id,
            difficulty=dim["challenge"]["difficulty"],
            prompt=dim["challenge"]["prompt"],
        )
        await step(0.4)

        # Generation 0: 3 competitors — baseline (raw Sonnet), seed (V1), spawn (V2)
        await emit(run_id, "generation_started", generation=0)
        await step(0.5)

        baseline_id = f"sk-baseline-{uuid.uuid4().hex[:6]}"
        seed_id = f"sk-seed-{uuid.uuid4().hex[:6]}"
        spawn_id = f"sk-spawn-{uuid.uuid4().hex[:6]}"

        competitors = [
            (baseline_id, "baseline", "Raw Sonnet — no skill (SKLD-bench baseline)"),
            (seed_id, "seed", "Pre-existing seed skill (V1)"),
            (spawn_id, "spawn", "Spawned alternative (V2)"),
        ]

        for comp_idx, (sk_id, mutation, strategy) in enumerate(competitors):
            await emit(
                run_id,
                "competitor_started",
                generation=0,
                competitor=comp_idx,
                skill_id=sk_id,
                challenge_id=ch_id,
                mutations=[mutation],
                traits=[dim["dimension"]],
                meta_strategy=strategy,
                skill_md_content="",
            )
            for turn in range(1, 4):
                await asyncio.sleep(0.2 / speed)
                await emit(
                    run_id, "competitor_progress",
                    generation=0, competitor=comp_idx,
                    skill_id=sk_id, challenge_id=ch_id,
                    turn=turn, tool_name=["Read", "Write", "Bash"][turn - 1],
                )
            await step(0.8)
            comp_scores = _demo_scores(mutation, dim["fitness"])
            await emit(
                run_id,
                "competitor_finished",
                generation=0, competitor=comp_idx,
                skill_id=sk_id, challenge_id=ch_id,
                trace_length=8 + comp_idx * 3,
                output_files=_demo_output(dim["dimension"], mutation),
                competitor_scores=comp_scores,
            )
            comp_cost = 0.12 + 0.04 * comp_idx
            total_cost += comp_cost
            await emit(
                run_id, "cost_update",
                total_cost_usd=round(total_cost, 4),
                incremental=True,
            )
            await step(0.2)

        # Judge
        await emit(run_id, "judging_started", generation=0)
        await step(0.3)
        for layer in range(1, 6):
            await asyncio.sleep(0.3 / speed)
            await emit(run_id, "judging_layer_complete", layer=layer, generation=0)

        # Scores
        await emit(
            run_id, "scores_published",
            generation=0,
            best_fitness=dim["fitness"],
            avg_fitness=dim["fitness"] - 0.04,
            pareto_front=[seed_id],
        )
        await step(0.3)

        await emit(run_id, "generation_complete", generation=0)
        await step(0.2)

        # Mark dimension complete
        winner_id = f"var_{uuid.uuid4().hex[:12]}"
        await emit(
            run_id,
            "variant_evolution_complete",
            variant_evolution_id=vevo_id,
            dimension=dim["dimension"],
            tier=dim["tier"],
            status="complete",
            winner_variant_id=winner_id,
            best_fitness=dim["fitness"],
        )
        await step(0.6)

    # --- Assembly ---
    await emit(run_id, "assembly_started", capability_count=len(dim_names), mode="atomic")
    await step(2.0)
    composite_id = f"gen_composite_{uuid.uuid4().hex[:8]}"
    await emit(
        run_id,
        "assembly_complete",
        composite_skill_id=composite_id,
        capability_count=len(dim_names),
        integration_passed=True,
        mode="atomic",
    )
    await step(0.5)

    # --- Done ---
    await emit(
        run_id,
        "evolution_complete",
        best_skill_id=composite_id,
        total_cost_usd=round(total_cost, 3),
        generations_completed=1,
    )


# ----------------------------------------------------------------------------
# Admin diagnostic endpoint
# ----------------------------------------------------------------------------


@router.get("/status")
async def debug_status(token: str = "") -> dict:
    """Admin diagnostic endpoint for debugging deployed environments.

    Gated by SKILLFORGE_ADMIN_TOKEN. Returns active runs, recent failures,
    leaked skills, and current configuration. Use ``?token=<admin-token>``
    as a query parameter.
    """
    from skillforge.config import (
        ADMIN_TOKEN,
        COMPETITOR_BACKEND,
        COMPETITOR_CONCURRENCY,
        MODEL_DEFAULTS,
    )

    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="admin token not configured")
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="invalid admin token")

    from skillforge.db.queries import list_leaked_skills, list_runs
    from skillforge.engine.run_registry import registry

    # Active runs
    active = [
        {"run_id": run_id, "done": task.done(), "cancelled": task.cancelled()}
        for run_id, task in registry.iter_tasks()
    ]

    # Recent failed runs
    all_runs = await list_runs(limit=20)
    recent_failed = [
        {
            "id": r.id,
            "reason": r.failure_reason,
            "specialization": r.specialization[:60],
        }
        for r in all_runs
        if r.status == "failed"
    ][:5]

    # Leaked skills
    leaked = await list_leaked_skills()

    return {
        "active_runs": active,
        "active_run_count": len(active),
        "recent_failed_runs": recent_failed,
        "leaked_skills_count": len(leaked),
        "competitor_backend": COMPETITOR_BACKEND,
        "competitor_concurrency": COMPETITOR_CONCURRENCY,
        "models": MODEL_DEFAULTS,
    }
