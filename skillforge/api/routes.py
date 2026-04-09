"""REST API routes."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response

from skillforge.api.schemas import (
    EvolveRequest,
    EvolveResponse,
    ExportFormat,
    LineageEdge,
    LineageNode,
    Mode,
    RunDetail,
)
from skillforge.db.database import init_db
from skillforge.db.queries import get_lineage, get_run, list_runs, save_run
from skillforge.engine.evolution import run_evolution
from skillforge.engine.export import export_agent_sdk_config, export_skill_md, export_skill_zip
from skillforge.models import EvolutionRun

router = APIRouter()

# Module-level registry: run_id -> background task
_active_runs: dict[str, asyncio.Task] = {}


@router.post("/evolve", response_model=EvolveResponse)
async def start_evolution(req: EvolveRequest) -> EvolveResponse:
    """Start a new evolution run and return its ID + WebSocket URL.

    Validates the request, creates an EvolutionRun, persists it, and spawns
    a background task that runs the evolution loop. Returns immediately —
    the client subscribes to the WebSocket to watch progress.
    """
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

    # Cleanup callback removes the task from the registry when it finishes
    def _cleanup(t: asyncio.Task) -> None:
        _active_runs.pop(run.id, None)

    task.add_done_callback(_cleanup)

    return EvolveResponse(run_id=run.id, ws_url=f"/ws/evolve/{run.id}")


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
        best_skill_id=run.best_skill.id if run.best_skill else None,
    )


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
