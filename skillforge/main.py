"""FastAPI application entry point.

Mounts REST routes, the WebSocket evolution event stream, and (optionally)
the built frontend SPA from ``frontend/dist``. The static mount is conditional
so the backend works in both deployments (with frontend) and dev (without).
"""

# ruff: noqa: E402
# Logging must be configured before any ``skillforge.*`` imports so structured
# logging is in place for any import-time warnings. This intentionally puts the
# application imports below the logging setup block.

from __future__ import annotations

import json as _json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


class _JsonFormatter(logging.Formatter):
    """Single-line JSON log format for structured log ingestion (e.g. Railway)."""

    def format(self, record: logging.LogRecord) -> str:
        return _json.dumps({
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        })


# Configure structured logging before any other imports touch loggers.
_log_level = os.getenv("SKILLFORGE_LOG_LEVEL", "INFO").upper()
_log_format = os.getenv("SKILLFORGE_LOG_FORMAT", "text")

if _log_format == "json":
    _handler = logging.StreamHandler()
    _handler.setFormatter(_JsonFormatter())
    logging.basicConfig(level=getattr(logging, _log_level, logging.INFO), handlers=[_handler])
else:
    logging.basicConfig(
        level=getattr(logging, _log_level, logging.INFO),
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

from skillforge.api.bible import router as bible_router
from skillforge.api.candidates import router as candidates_router
from skillforge.api.debug import router as debug_router
from skillforge.api.invites import router as invites_router
from skillforge.api.routes import router as api_router
from skillforge.api.seeds import router as seeds_router
from skillforge.api.spec_assistant import router as spec_assistant_router
from skillforge.api.taxonomy import router as taxonomy_router
from skillforge.api.uploads import router as uploads_router
from skillforge.api.websocket import router as ws_router
from skillforge.db.database import init_db
from skillforge.db.queries import mark_zombie_runs
from skillforge.db.seed_loader import load_seeds
from skillforge.db.taxonomy_seeds import load_taxonomy

logger = logging.getLogger("skillforge")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the SQLite schema on startup.

    Runs exactly once per container boot. Idempotent — ``init_db`` uses
    ``CREATE TABLE IF NOT EXISTS`` so re-running on an existing DB is safe.
    """
    await init_db()
    await load_seeds()
    try:
        taxonomy_diag = await load_taxonomy()
        logger.info(
            "Taxonomy bootstrapped: %d nodes, %d families created, %d reused",
            taxonomy_diag.get("nodes_total", 0),
            taxonomy_diag.get("families_created", 0),
            taxonomy_diag.get("families_reused", 0),
        )
    except Exception as exc:  # pragma: no cover - boot-time resiliency
        logger.exception("Taxonomy bootstrap failed: %s", exc)
    zombie_count = await mark_zombie_runs()
    if zombie_count:
        logger.warning("Marked %d zombie run(s) as failed on startup", zombie_count)
    yield
    # No shutdown hook needed — aiosqlite connections are per-query.


app = FastAPI(
    title="SKLD.run",
    description="Evolve Claude Agent Skills through natural selection",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router)
app.include_router(ws_router)
app.include_router(debug_router)
app.include_router(bible_router)
app.include_router(spec_assistant_router)
app.include_router(seeds_router)
app.include_router(uploads_router)
app.include_router(invites_router)
app.include_router(candidates_router)
app.include_router(taxonomy_router)


@app.get("/api/health")
async def health() -> dict:
    """Backend health check with active run count."""
    from skillforge.api.routes import _active_runs
    return {
        "status": "ok",
        "service": "skillforge",
        "active_runs": len(_active_runs),
    }


# --- Optional frontend SPA mount ---------------------------------------------
# If frontend/dist exists (built by Vite), serve it as the SPA at /. Otherwise
# fall back to a JSON health check at /. This makes the same image deployable
# whether or not the frontend has been built.

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def _mount_frontend_spa() -> None:
    """Mount the built SPA if frontend/dist exists. No-op otherwise."""
    if not _FRONTEND_DIST.exists() or not (_FRONTEND_DIST / "index.html").exists():

        @app.get("/")
        async def root_no_frontend() -> dict[str, str]:
            return {"status": "ok", "service": "skillforge", "frontend": "not built"}

        return

    # Serve assets/* etc. from dist
    app.mount(
        "/assets",
        StaticFiles(directory=str(_FRONTEND_DIST / "assets")),
        name="assets",
    )

    # SPA index for / and any unknown route (client-side router handles it)
    @app.get("/")
    async def root_spa() -> FileResponse:
        return FileResponse(str(_FRONTEND_DIST / "index.html"))


_mount_frontend_spa()


if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("skillforge.main:app", host="0.0.0.0", port=port, reload=True)
