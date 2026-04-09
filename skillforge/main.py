"""FastAPI application entry point.

Mounts REST routes, the WebSocket evolution event stream, and (optionally)
the built frontend SPA from ``frontend/dist``. The static mount is conditional
so the backend works in both deployments (with frontend) and dev (without).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from skillforge.api.routes import router as api_router
from skillforge.api.websocket import router as ws_router

app = FastAPI(
    title="SkillForge",
    description="Evolutionary breeding platform for Claude Agent Skills",
    version="0.1.0",
)

app.include_router(api_router)
app.include_router(ws_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Backend health check (unaffected by static mount)."""
    return {"status": "ok", "service": "skillforge"}


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
