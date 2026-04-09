"""FastAPI application entry point.

Mounts REST routes and the WebSocket evolution event stream. Real route
handlers arrive in Step 8; this is a stub that boots cleanly.
"""

from __future__ import annotations

from fastapi import FastAPI

from skillforge.api.routes import router as api_router
from skillforge.api.websocket import router as ws_router

app = FastAPI(
    title="SkillForge",
    description="Evolutionary breeding platform for Claude Agent Skills",
    version="0.1.0",
)

app.include_router(api_router)
app.include_router(ws_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Health check."""
    return {"status": "ok", "service": "skillforge"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("skillforge.main:app", host="0.0.0.0", port=8000, reload=True)
