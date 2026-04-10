"""Candidate seeds API — save, list, promote AI-generated and evolved skills."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from skillforge.db.queries import (
    list_candidate_seeds,
    save_candidate_seed,
    update_candidate_seed_status,
)

logger = logging.getLogger("skillforge.api.candidates")

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


class SaveCandidateRequest(BaseModel):
    title: str
    specialization: str
    skill_md_content: str
    supporting_files: dict[str, str] = Field(default_factory=dict)
    traits: list[str] = Field(default_factory=list)
    category: str = "uncategorized"
    source: str = "generated"  # "generated" | "evolved"
    source_run_id: str | None = None
    source_skill_id: str | None = None
    fitness_score: float | None = None


class UpdateStatusRequest(BaseModel):
    status: str  # "approved" | "rejected" | "promoted"
    notes: str | None = None


@router.post("")
async def save_candidate(req: SaveCandidateRequest) -> dict:
    """Save a skill package as a candidate seed."""
    candidate_id = str(uuid.uuid4())
    await save_candidate_seed(
        id=candidate_id,
        source=req.source,
        title=req.title,
        specialization=req.specialization,
        skill_md_content=req.skill_md_content,
        supporting_files=req.supporting_files,
        traits=req.traits,
        category=req.category,
        fitness_score=req.fitness_score,
        source_run_id=req.source_run_id,
        source_skill_id=req.source_skill_id,
    )
    logger.info("candidate=%s saved: source=%s title=%s", candidate_id[:8], req.source, req.title)
    return {"id": candidate_id, "status": "pending"}


@router.get("")
async def list_candidates(status: str | None = None) -> list[dict]:
    """List candidate seeds, optionally filtered by status."""
    return await list_candidate_seeds(status=status)


@router.patch("/{candidate_id}")
async def update_candidate(candidate_id: str, req: UpdateStatusRequest) -> dict:
    """Update a candidate's status (approve, reject, promote)."""
    if req.status not in ("approved", "rejected", "promoted", "pending"):
        raise HTTPException(status_code=400, detail=f"invalid status: {req.status}")
    found = await update_candidate_seed_status(candidate_id, req.status, req.notes)
    if not found:
        raise HTTPException(status_code=404, detail=f"candidate {candidate_id} not found")
    logger.info("candidate=%s status=%s", candidate_id[:8], req.status)
    return {"id": candidate_id, "status": req.status}
