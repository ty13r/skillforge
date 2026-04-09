"""Per-run event queues for streaming evolution progress to WebSocket clients.

The engine publishes events via ``get_queue(run_id).put(...)``. The WebSocket
handler in ``api/websocket.py`` reads from the same queue to stream events to
the frontend. This decouples the engine from the transport layer — the engine
never touches WebSockets directly.

Event types (documented on each emit site):
    run_started, challenge_designed, generation_started, competitor_started,
    competitor_progress, competitor_finished,
    judging_layer1_complete ... judging_layer5_complete,
    scores_published, breeding_started, breeding_report,
    generation_complete, evolution_complete, cost_update, run_failed.
"""

from __future__ import annotations

import asyncio
from typing import Any

# Module-level registry: run_id -> queue
_QUEUES: dict[str, asyncio.Queue[dict[str, Any]]] = {}


def get_queue(run_id: str) -> asyncio.Queue[dict[str, Any]]:
    """Return the event queue for ``run_id``, creating it if needed."""
    if run_id not in _QUEUES:
        _QUEUES[run_id] = asyncio.Queue()
    return _QUEUES[run_id]


def drop_queue(run_id: str) -> None:
    """Remove a queue from the registry (called after a run completes/fails).

    Should be called after ``evolution_complete`` or ``run_failed`` events have
    been consumed by the WebSocket handler, to prevent unbounded memory growth.
    """
    _QUEUES.pop(run_id, None)


async def emit(run_id: str, event: str, **kwargs: Any) -> None:
    """Convenience helper: put an event dict on the run's queue.

    Usage:
        await emit(run_id, "generation_started", generation=0, population_size=5)
    """
    queue = get_queue(run_id)
    payload = {"event": event, **kwargs}
    await queue.put(payload)


def clear_all() -> None:
    """Test helper: wipe all queues."""
    _QUEUES.clear()
