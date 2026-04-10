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
    task after ``evolution_complete``. If the report does not exist yet (run
    still in flight, report generation failed, or disk-write error), return
    404 so the caller can poll or fall back to the live WebSocket state.
    """
    from skillforge.engine.report import get_report

    report = await get_report(run_id)
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
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{run_id}-skill.zip"'},
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
    """Return lineage tree data: nodes (genomes) + edges (parent→child)."""
    run = await get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")

    edges_data = await get_lineage(run_id)
    edges = [
        LineageEdge(
            parent_id=e.get("parent_id", ""),
            child_id=e.get("child_id", ""),
            mutation_type=e.get("mutation_type", "unknown"),
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

    return {
        "nodes": [n.model_dump() for n in nodes],
        "edges": [e.model_dump() for e in edges],
    }


@router.get("/runs/{run_id}/skills/{skill_id}")
async def get_run_skill(run_id: str, skill_id: str) -> dict:
    """Return the full SKILL.md + metadata for one genome in a run.

    Used by the SkillDiffViewer to render parent/child side-by-side.
    """
    run = await get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")

    for gen in run.generations:
        for skill in gen.skills:
            if skill.id == skill_id:
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
    raise HTTPException(
        status_code=404, detail=f"skill {skill_id} not found in run {run_id}"
    )
