"""API routes package — split by lifecycle concern.

- ``evolve`` — POST endpoints that start / fork evolution runs
- ``runs``   — POST cancel + all GET endpoints for reading run state

``router`` here is the single ``APIRouter(prefix="/api")`` that
``skillforge.main`` mounts. Submodules expose their own un-prefixed
routers and we include them below — same public URLs as before the
split.
"""

from __future__ import annotations

from fastapi import APIRouter

from skillforge.api.routes import evolve, runs

router = APIRouter(prefix="/api")
router.include_router(evolve.router)
router.include_router(runs.router)

__all__ = ["router"]
