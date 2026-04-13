"""REST API routes."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime

logger = logging.getLogger("skillforge.api")

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from skillforge.api.schemas import (
    EvolveRequest,
    EvolveResponse,
    ExportFormat,
    LineageEdge,
    LineageNode,
    Mode,
    RunDetail,
)
from skillforge.api.uploads import clear_upload, get_upload
from skillforge.config import invite_code_valid
from skillforge.db.database import init_db
from skillforge.db.queries import get_lineage, get_run, list_runs, save_run
from skillforge.engine.evolution import PENDING_PARENTS, run_evolution
from skillforge.engine.export import export_agent_sdk_config, export_skill_md, export_skill_zip
from skillforge.models import EvolutionRun, SkillGenome

router = APIRouter(prefix="/api")

# Module-level registry: run_id -> background task
_active_runs: dict[str, asyncio.Task] = {}


async def _classify_run_via_taxonomist(
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
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "run=%s taxonomist classification failed: %s — defaulting to molecular",
            run.id[:8],
            exc,
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

        from skillforge.db import save_variant_evolution
        from skillforge.models import VariantEvolution

        # Insert the parent run row first so the FK on
        # variant_evolutions.parent_run_id is satisfied. save_run is
        # idempotent (INSERT OR REPLACE) so the second save_run later in
        # the route handler is a no-op refresh.
        from skillforge.db import save_run as _save_run

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


@router.post("/evolve", response_model=EvolveResponse)
async def start_evolution(req: EvolveRequest) -> EvolveResponse:
    """Start a new evolution run and return its ID + WebSocket URL.

    Validates the request, creates an EvolutionRun, persists it, and spawns
    a background task that runs the evolution loop. Returns immediately —
    the client subscribes to the WebSocket to watch progress.
    """
    # Invite gating — returns True if gating is disabled OR the code is valid
    if not invite_code_valid(req.invite_code):
        raise HTTPException(
            status_code=403,
            detail="This platform is invite-only. Enter a valid invite code or request one.",
        )

    # Mode-specific validation
    if req.mode == Mode.domain and not req.specialization:
        raise HTTPException(status_code=400, detail="domain mode requires 'specialization'")
    if req.mode == Mode.meta:
        raise HTTPException(status_code=501, detail="meta mode is v1.1, not yet supported")

    # Ensure DB is initialized (idempotent)
    await init_db()

    run = EvolutionRun(
        id=str(uuid.uuid4()),
        mode=req.mode.value,
        specialization=req.specialization or "",
        population_size=req.population_size,
        num_generations=req.num_generations,
        max_budget_usd=req.max_budget_usd,
        status="pending",
        created_at=datetime.now(UTC),
    )

    # v2.0 — Taxonomist classification before evolution starts. Best-effort:
    # the run still proceeds in molecular mode if the LLM call fails or no
    # API key is available, so we never block submission on classification.
    await _classify_run_via_taxonomist(run, req.evolution_mode)

    await save_run(run)

    # Spawn background task — store reference so it isn't GC'd
    task = asyncio.create_task(run_evolution(run))
    _active_runs[run.id] = task
    logger.info("run=%s started: spec=%s pop=%d gens=%d",
                run.id[:8], run.specialization[:60], run.population_size, run.num_generations)

    # Cleanup callback removes the task from the registry when it finishes
    def _cleanup(t: asyncio.Task) -> None:
        _active_runs.pop(run.id, None)
        exc = t.exception() if not t.cancelled() else None
        if exc:
            logger.error("run=%s task failed: %s", run.id[:8], exc)
        else:
            logger.info("run=%s task completed", run.id[:8])

    task.add_done_callback(_cleanup)

    return EvolveResponse(run_id=run.id, ws_url=f"/ws/evolve/{run.id}")


# ---------------------------------------------------------------------------
# Fork-and-evolve: start a run from an existing Skill (registry seed or upload)
# ---------------------------------------------------------------------------


class EvolveFromParentRequest(BaseModel):
    parent_source: str = Field(..., description='"registry", "upload", or "generated"')
    parent_id: str = Field("", description="skill_id (registry) or upload_id (upload)")
    specialization: str | None = None
    population_size: int = 5
    num_generations: int = 3
    max_budget_usd: float = 10.0
    invite_code: str | None = None
    # For parent_source="generated" — inline skill content
    skill_md_content: str | None = None
    supporting_files: dict[str, str] | None = None


@router.post("/evolve/from-parent", response_model=EvolveResponse)
async def start_evolution_from_parent(req: EvolveFromParentRequest) -> EvolveResponse:
    """Start a new evolution run using an existing Skill as the gen-0 parent.

    Supports two parent sources:
      - ``registry``: ``parent_id`` is a skill_id inside the seed-library run
        (or any other run's skill). Resolved via get_run(seed-library).
      - ``upload``: ``parent_id`` is an upload_id from POST /api/uploads/skill.
        Resolved via the in-memory upload cache.

    The parent is stashed in the ``PENDING_PARENTS`` registry keyed by the new
    run's id. The evolution engine picks it up at gen 0 spawn time and routes
    through ``spawner.spawn_from_parent()`` instead of ``spawn_gen0()``.
    """
    if not invite_code_valid(req.invite_code):
        raise HTTPException(
            status_code=403,
            detail="This platform is invite-only. Enter a valid invite code or request one.",
        )

    # Resolve the parent genome
    if req.parent_source == "registry":
        # Search the seed-library run first, then fall back to any run
        parent = None
        seed_run = await get_run("seed-library")
        if seed_run:
            for gen in seed_run.generations:
                for sk in gen.skills:
                    if sk.id == req.parent_id:
                        parent = sk
                        break
                if parent:
                    break
        if parent is None:
            raise HTTPException(
                status_code=404,
                detail=f"registry skill {req.parent_id!r} not found",
            )
        effective_spec = req.specialization or (
            parent.frontmatter.get("description", "")[:200]
            if isinstance(parent.frontmatter, dict)
            else ""
        )
    elif req.parent_source == "upload":
        parent = get_upload(req.parent_id)
        if parent is None:
            raise HTTPException(
                status_code=404, detail=f"upload {req.parent_id!r} not found or expired"
            )
        effective_spec = req.specialization or "User-uploaded Skill (evolved)"
    elif req.parent_source == "generated":
        if not req.skill_md_content:
            raise HTTPException(
                status_code=400,
                detail="generated source requires skill_md_content",
            )
        parent = SkillGenome(
            id=str(uuid.uuid4()),
            generation=0,
            skill_md_content=req.skill_md_content,
            supporting_files=req.supporting_files or {},
            frontmatter={},
            traits=[],
            maturity="draft",
        )
        effective_spec = req.specialization or "AI-generated skill"
    else:
        raise HTTPException(
            status_code=400,
            detail=f"parent_source must be 'registry', 'upload', or 'generated', got {req.parent_source!r}",
        )

    await init_db()

    run = EvolutionRun(
        id=str(uuid.uuid4()),
        mode="domain",
        specialization=effective_spec,
        population_size=req.population_size,
        num_generations=req.num_generations,
        max_budget_usd=req.max_budget_usd,
        status="pending",
        created_at=datetime.now(UTC),
    )
    await save_run(run)

    # Stash the parent so the engine's gen-0 spawn picks it up
    PENDING_PARENTS[run.id] = parent

    # Clear the upload cache so we don't leak memory
    if req.parent_source == "upload":
        clear_upload(req.parent_id)

    task = asyncio.create_task(run_evolution(run))
    _active_runs[run.id] = task

    def _cleanup(t: asyncio.Task) -> None:
        _active_runs.pop(run.id, None)

    task.add_done_callback(_cleanup)

    return EvolveResponse(run_id=run.id, ws_url=f"/ws/evolve/{run.id}")


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str) -> dict:
    """Cancel an in-progress evolution run.

    Finds the backing asyncio task in ``_active_runs``, cancels it, and
    marks the run status as ``cancelled`` in the DB. The engine catches
    ``CancelledError`` in its main loop, emits a ``run_cancelled`` event,
    and persists the partial state before exiting.
    """
    task = _active_runs.get(run_id)
    if task is None or task.done():
        # Maybe already done, maybe never existed — either way nothing to cancel
        raise HTTPException(
            status_code=404, detail=f"no active run {run_id!r} to cancel"
        )
    task.cancel()
    return {"run_id": run_id, "cancelled": True}


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run_detail(run_id: str) -> RunDetail:
    run = await get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")

    # Compute baseline_fitness from benchmark_results if this run has a family
    baseline_fitness = None
    family_id = getattr(run, "family_id", None)
    if family_id:
        from skillforge.db.queries import _connect

        async with _connect() as conn:
            # Look up the family slug
            cursor = await conn.execute(
                "SELECT slug FROM skill_families WHERE id = ?", (family_id,)
            )
            fam_row = await cursor.fetchone()
            if fam_row:
                family_slug = fam_row[0]
                # Average composite score of raw Sonnet on this family's challenges
                cursor = await conn.execute(
                    "SELECT AVG(json_extract(scores, '$.composite')) "
                    "FROM benchmark_results "
                    "WHERE family_slug = ? AND model = 'claude-sonnet-4-6' "
                    "AND scores != '{}'",
                    (family_slug,),
                )
                avg_row = await cursor.fetchone()
                if avg_row and avg_row[0] is not None:
                    baseline_fitness = round(avg_row[0], 4)

    return RunDetail(
        id=run.id,
        mode=run.mode,
        specialization=run.specialization,
        status=run.status,
        population_size=run.population_size,
        num_generations=run.num_generations,
        total_cost_usd=run.total_cost_usd,
        best_fitness=(
            max(run.best_skill.pareto_objectives.values())
            if run.best_skill and run.best_skill.pareto_objectives
            else None
        ),
        best_skill_id=run.best_skill.id if run.best_skill else None,
        family_id=family_id,
        evolution_mode=getattr(run, "evolution_mode", "molecular"),
        learning_log=list(run.learning_log),
        baseline_fitness=baseline_fitness,
    )


@router.get("/runs/{run_id}/events")
async def get_run_events(run_id: str) -> list[dict]:
    """Return the full event history for a run (for post-mortem debugging)."""
    from skillforge.db.queries import _connect

    async with _connect() as conn:
        cursor = await conn.execute(
            "SELECT event_type, payload, timestamp FROM run_events WHERE run_id = ? ORDER BY id",
            (run_id,),
        )
        rows = await cursor.fetchall()
    return [{"event": row[0], "payload": json.loads(row[1]), "timestamp": row[2]} for row in rows]


@router.get("/runs/{run_id}/report")
async def get_run_report(run_id: str) -> dict:
    """Return the post-run report JSON for a completed run.

    Generated by ``skillforge.engine.report.generate_run_report`` as a detached
    task after ``evolution_complete``. If the report does not exist yet (e.g.,
    a run that was inserted via a seed loader rather than through the engine),
    we lazy-generate it on the first call so the frontend never has to poll.
    """
    from skillforge.engine.report import generate_run_report, get_report

    report = await get_report(run_id)
    if report is None:
        # Lazy generation. Safe: generate_run_report is read-only against
        # the run tables and writes to data/reports/. Returns None on error
        # so we can still 404 cleanly.
        report = await generate_run_report(run_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"report not generated yet for run_id={run_id}",
        )
    return report


@router.get("/runs")
async def list_all_runs():
    """List recent runs (most recent first)."""
    runs = await list_runs(limit=50)
    return [
        {
            "id": r.id,
            "mode": r.mode,
            "specialization": r.specialization,
            "status": r.status,
            "best_fitness": (
                max(r.best_skill.pareto_objectives.values())
                if r.best_skill and r.best_skill.pareto_objectives
                else None
            ),
            "total_cost_usd": r.total_cost_usd,
        }
        for r in runs
    ]


@router.get("/runs/{run_id}/export")
async def export_run(run_id: str, format: ExportFormat = ExportFormat.skill_dir):
    run = await get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    if run.best_skill is None:
        raise HTTPException(status_code=400, detail="run has no best_skill to export")

    if format == ExportFormat.skill_dir:
        zip_bytes = export_skill_zip(run.best_skill)
        # Prefer the composite's own skill name from the frontmatter (kebab-case
        # slug) for the download filename — that's what the user is actually
        # deploying. Fall back to the run id with any legacy "mock" marker
        # scrubbed so the filename never says "mock" to an end user.
        name = ""
        if run.best_skill.frontmatter:
            name = str(run.best_skill.frontmatter.get("name", "")).strip()
        if not name:
            name = run_id.replace("mock-v", "v").replace("mock", "seed")
        filename = f"{name}.zip"
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    elif format == ExportFormat.skill_md:
        md = export_skill_md(run.best_skill)
        return Response(content=md, media_type="text/markdown")
    elif format == ExportFormat.agent_sdk_config:
        config = export_agent_sdk_config(run.best_skill)
        return Response(content=json.dumps(config, indent=2), media_type="application/json")
    else:
        raise HTTPException(status_code=400, detail=f"unknown format: {format}")


@router.get("/runs/{run_id}/lineage")
async def get_run_lineage(run_id: str) -> dict:
    """Return lineage tree data: nodes (genomes) + edges (parent→child).

    Nodes are built from ``run.generations[].skills[]`` for molecular runs,
    and fall back to a direct ``skill_genomes`` query for atomic runs where
    ``run.generations`` is always empty. Edges are always sourced from
    ``get_lineage``, which reads ``skill_genomes.parent_ids`` directly, so
    it's already atomic-compatible.
    """
    run = await get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")

    # Pre-fetch the child genomes' meta_strategy so we can infer mutation_type
    # for atomic-mode composite edges. In atomic mode the Engineer assembles
    # 12+ parents into a single composite — that's an "assembly" edge, not a
    # mutation. Without this inference every edge defaults to "unknown".
    child_meta_strategy: dict[str, str] = {}
    if getattr(run, "evolution_mode", "molecular") == "atomic":
        from skillforge.db.queries import _connect

        async with _connect() as conn, conn.execute(
            "SELECT id, meta_strategy FROM skill_genomes WHERE run_id = ?",
            (run_id,),
        ) as cur:
            for row in await cur.fetchall():
                child_meta_strategy[row["id"]] = row["meta_strategy"] or ""

    def _infer_mutation_type(edge: dict) -> str:
        child_id = edge.get("child_id", "")
        strategy = child_meta_strategy.get(child_id, "")
        if strategy == "engineer_composite":
            return "assembly"
        if strategy in {"seed_pipeline_winner", "mock_pipeline_winner", "gen0_seed"}:
            return "selection"
        return edge.get("mutation_type", "unknown")

    edges_data = await get_lineage(run_id)
    edges = [
        LineageEdge(
            parent_id=e.get("parent_id", ""),
            child_id=e.get("child_id", ""),
            mutation_type=_infer_mutation_type(e),
        )
        for e in edges_data
    ]

    # Build nodes from all genomes across all generations
    nodes = []
    seen_ids: set[str] = set()
    for gen in run.generations:
        for skill in gen.skills:
            if skill.id in seen_ids:
                continue
            seen_ids.add(skill.id)
            fitness = (
                sum(skill.pareto_objectives.values()) / len(skill.pareto_objectives)
                if skill.pareto_objectives
                else 0.0
            )
            nodes.append(
                LineageNode(
                    id=skill.id,
                    generation=skill.generation,
                    fitness=fitness,
                    maturity=skill.maturity,
                    traits=skill.traits,
                )
            )

    # Atomic-mode fallback: genomes are linked via skill_genomes.run_id
    # without nesting under run.generations. Query the table directly for
    # any genomes not already captured above.
    if not nodes or getattr(run, "evolution_mode", "molecular") == "atomic":
        from skillforge.db.queries import _connect, _row_to_genome

        async with _connect() as conn, conn.execute(
            "SELECT * FROM skill_genomes WHERE run_id = ? ORDER BY generation, id",
            (run_id,),
        ) as cur:
            rows = await cur.fetchall()
        for row in rows:
            genome = _row_to_genome(row)
            if genome.id in seen_ids:
                continue
            seen_ids.add(genome.id)
            fitness = (
                sum(genome.pareto_objectives.values()) / len(genome.pareto_objectives)
                if genome.pareto_objectives
                else 0.0
            )
            nodes.append(
                LineageNode(
                    id=genome.id,
                    generation=genome.generation,
                    fitness=fitness,
                    maturity=genome.maturity,
                    traits=genome.traits,
                )
            )

    return {
        "nodes": [n.model_dump() for n in nodes],
        "edges": [e.model_dump() for e in edges],
    }


@router.get("/runs/{run_id}/skills/{skill_id}")
async def get_run_skill(run_id: str, skill_id: str) -> dict:
    """Return the full SKILL.md + metadata for one genome in a run.

    Used by the SkillDiffViewer to render parent/child side-by-side.

    Looks up the genome first in ``run.generations[].skills[]`` (molecular
    mode), then falls back to a direct ``skill_genomes`` table query scoped
    by ``run_id`` (atomic mode, where genomes live outside the generations
    tree and are linked only via ``skill_genomes.run_id``).
    """
    run = await get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")

    def _skill_to_dict(skill: SkillGenome) -> dict:
        return {
            "id": skill.id,
            "generation": skill.generation,
            "skill_md_content": skill.skill_md_content,
            "supporting_files": skill.supporting_files or {},
            "traits": skill.traits,
            "maturity": skill.maturity,
            "parent_ids": skill.parent_ids,
            "mutations": skill.mutations,
            "mutation_rationale": skill.mutation_rationale,
            "pareto_objectives": skill.pareto_objectives,
        }

    for gen in run.generations:
        for skill in gen.skills:
            if skill.id == skill_id:
                return _skill_to_dict(skill)

    # Atomic-mode fallback: genomes are linked to the run via
    # skill_genomes.run_id without nesting under run.generations.
    from skillforge.db.queries import _connect, _row_to_genome

    async with _connect() as conn, conn.execute(
        "SELECT * FROM skill_genomes WHERE id = ? AND run_id = ?",
        (skill_id, run_id),
    ) as cur:
        row = await cur.fetchone()
    if row is not None:
        return _skill_to_dict(_row_to_genome(row))

    raise HTTPException(
        status_code=404, detail=f"skill {skill_id} not found in run {run_id}"
    )
