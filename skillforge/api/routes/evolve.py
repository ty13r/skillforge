"""POST endpoints that start evolution runs.

- POST /api/evolve — start a fresh run from a specialization
- POST /api/evolve/from-parent — fork from a registry skill, upload, or
  inline generated skill
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from skillforge.api.routes._helpers import classify_run_via_taxonomist
from skillforge.api.schemas import EvolveRequest, EvolveResponse, Mode
from skillforge.api.uploads import clear_upload, get_upload
from skillforge.config import invite_code_valid
from skillforge.db.database import init_db
from skillforge.db.queries import get_run, save_run
from skillforge.engine.evolution import run_evolution
from skillforge.engine.run_registry import registry
from skillforge.models import EvolutionRun, SkillGenome

logger = logging.getLogger("skillforge.api.evolve")
router = APIRouter()


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
    await classify_run_via_taxonomist(run, req.evolution_mode)

    await save_run(run)

    # Spawn background task — store reference so it isn't GC'd
    task = asyncio.create_task(run_evolution(run))
    registry.set_task(run.id, task)
    logger.info("run=%s started: spec=%s pop=%d gens=%d",
                run.id[:8], run.specialization[:60], run.population_size, run.num_generations)

    # Cleanup callback removes the task from the registry when it finishes
    def _cleanup(t: asyncio.Task) -> None:
        registry.clear_task(run.id)
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

    The parent is stashed in the ``RunRegistry`` (see ``engine/run_registry.py``)
    keyed by the new run's id. The evolution engine picks it up at gen 0 spawn
    time and routes through ``spawner.spawn_from_parent()`` instead of
    ``spawn_gen0()``.
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
    registry.stash_parent(run.id, parent)

    # Clear the upload cache so we don't leak memory
    if req.parent_source == "upload":
        clear_upload(req.parent_id)

    task = asyncio.create_task(run_evolution(run))
    registry.set_task(run.id, task)

    def _cleanup(t: asyncio.Task) -> None:
        registry.clear_task(run.id)

    task.add_done_callback(_cleanup)

    return EvolveResponse(run_id=run.id, ws_url=f"/ws/evolve/{run.id}")
