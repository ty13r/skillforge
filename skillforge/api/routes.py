"""REST API routes. Stub handlers — real logic lands in Step 8."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from skillforge.api.schemas import (
    EvolveRequest,
    EvolveResponse,
    ExportFormat,
    RunDetail,
)

router = APIRouter()


@router.post("/evolve", response_model=EvolveResponse)
async def start_evolution(req: EvolveRequest) -> EvolveResponse:
    """Start a new evolution run and return its ID + WebSocket URL."""
    raise HTTPException(status_code=501, detail="not implemented (Step 8)")


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: str) -> RunDetail:
    """Fetch the full evolution run by ID."""
    raise HTTPException(status_code=501, detail="not implemented (Step 8)")


@router.get("/runs/{run_id}/export")
async def export_run(run_id: str, format: ExportFormat = ExportFormat.skill_dir):
    """Export the best evolved Skill in the requested format."""
    raise HTTPException(status_code=501, detail="not implemented (Step 9)")


@router.get("/runs/{run_id}/lineage")
async def get_lineage(run_id: str) -> dict:
    """Return lineage tree data: nodes + edges + mutation annotations."""
    raise HTTPException(status_code=501, detail="not implemented (Step 8)")
