"""WebSocket handler streaming evolution events to the frontend."""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from skillforge.engine.events import drop_queue, get_queue

router = APIRouter()


@router.websocket("/ws/evolve/{run_id}")
async def evolution_events(websocket: WebSocket, run_id: str) -> None:
    """Stream evolution events for ``run_id`` until evolution_complete or run_failed.

    Reads from the per-run asyncio.Queue populated by the engine.
    Cleans up the queue after the terminal event is sent.
    """
    await websocket.accept()
    queue = get_queue(run_id)

    try:
        while True:
            try:
                # 60s timeout per receive — keeps the connection alive but
                # doesn't hang forever if the engine crashes silently
                event = await asyncio.wait_for(queue.get(), timeout=60.0)
            except TimeoutError:
                # Heartbeat to detect dead connections
                await websocket.send_json({"event": "heartbeat"})
                continue

            await websocket.send_json(event)

            # Terminal events: stop streaming, clean up queue, close cleanly
            if event.get("event") in (
                "evolution_complete",
                "run_failed",
                "run_cancelled",
            ):
                drop_queue(run_id)
                break
    except WebSocketDisconnect:
        # Client disconnected — leave the queue alone (engine continues)
        return
    except Exception:
        # Any other error: best-effort close
        with contextlib.suppress(Exception):
            await websocket.close(code=1011)
