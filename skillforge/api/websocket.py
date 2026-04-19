"""WebSocket handler streaming evolution events to the frontend."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from skillforge.engine.events import drop_queue, get_queue

logger = logging.getLogger("skillforge.ws")
router = APIRouter()


@router.websocket("/ws/evolve/{run_id}")
async def evolution_events(websocket: WebSocket, run_id: str) -> None:
    """Stream evolution events for ``run_id`` until evolution_complete or run_failed.

    Reads from the per-run asyncio.Queue populated by the engine.
    Cleans up the queue after the terminal event is sent.
    """
    await websocket.accept()
    logger.info("ws run=%s connected", run_id[:8])
    queue = get_queue(run_id)

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=60.0)
            except TimeoutError:
                await websocket.send_json({"event": "heartbeat"})
                continue

            await websocket.send_json(event)

            # Terminal events: stop streaming, clean up queue, close cleanly
            if event.get("event") in (
                "evolution_complete",
                "run_failed",
                "run_cancelled",
            ):
                logger.info("ws run=%s terminal event: %s", run_id[:8], event.get("event"))
                drop_queue(run_id)
                break
    except WebSocketDisconnect:
        logger.info("ws run=%s client disconnected", run_id[:8])
        return
    except Exception:  # noqa: BLE001 — WS handler must always close cleanly, never propagate
        logger.exception("ws run=%s error", run_id[:8])
        with contextlib.suppress(Exception):
            await websocket.close(code=1011)
