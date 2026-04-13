"""WebSocket integration test: validates event streaming via the fake-run system.

Uses threading to coordinate the HTTP POST (which spawns a background task)
with the WebSocket consumer, both running against the same TestClient/event loop.
"""

from __future__ import annotations

import threading
import time

import pytest
from starlette.testclient import WebSocketDenialResponse
from starlette.websockets import WebSocketDisconnect
from fastapi.testclient import TestClient

from skillforge.engine.events import clear_all
from skillforge.main import app


EXPECTED_EVENT_TYPES = {
    "run_started",
    "taxonomy_classified",
    "decomposition_complete",
    "variant_evolution_started",
    "challenge_designed",
    "generation_started",
    "competitor_started",
    "competitor_finished",
    "judging_started",
    "judging_layer_complete",
    "scores_published",
    "variant_evolution_complete",
    "evolution_complete",
}


@pytest.fixture(autouse=True)
def clean_queues():
    clear_all()
    yield
    clear_all()


def _post_fake_run(client: TestClient, run_id: str) -> None:
    """POST to /api/debug/fake-run in a background thread."""
    client.post(
        "/api/debug/fake-run",
        json={
            "run_id": run_id,
            "speed": 50,
            "population_size": 2,
            "num_generations": 1,
            "num_challenges": 2,
        },
    )


def _collect_events_via_ws(
    client: TestClient, run_id: str, max_events: int = 600
) -> list[dict]:
    """Connect to WS and collect events until terminal or limit.

    The POST is fired from a background thread — TestClient serialises ASGI
    calls via an internal anyio portal, so both POST and WS share one loop.
    """
    received: list[dict] = []

    poster = threading.Thread(target=_post_fake_run, args=(client, run_id), daemon=True)
    poster.start()

    # Give the POST a moment to land and schedule the background task
    time.sleep(0.1)

    with client.websocket_connect(f"/ws/evolve/{run_id}") as ws:
        for _ in range(max_events):
            try:
                msg = ws.receive_json(mode="text")
            except Exception:
                break
            received.append(msg)
            if msg.get("event") in ("evolution_complete", "run_failed", "run_cancelled"):
                break

    poster.join(timeout=5)
    return received


# ---------------------------------------------------------------------------
# Test 1: fake-run streams all expected event types
# ---------------------------------------------------------------------------


def test_fake_run_streams_all_events():
    with TestClient(app) as client:
        run_id = "integration-all-events"
        received = _collect_events_via_ws(client, run_id)

        # Filter out heartbeats
        events = [e for e in received if e.get("event") != "heartbeat"]

        assert len(events) > 0, "No non-heartbeat events received"

        event_types = {e["event"] for e in events}
        assert "evolution_complete" in event_types, (
            f"evolution_complete not found; got: {event_types}"
        )
        assert "run_failed" not in event_types, "Unexpected run_failed event"

        missing = EXPECTED_EVENT_TYPES - event_types
        assert not missing, f"Missing event types: {missing}"


# ---------------------------------------------------------------------------
# Test 2: terminal event is the last event delivered
# ---------------------------------------------------------------------------


def test_terminal_event_is_last():
    """After the server sends evolution_complete it breaks out of the loop,
    so evolution_complete must be the final event in the collected stream."""
    with TestClient(app) as client:
        run_id = "integration-terminal-last"
        received = _collect_events_via_ws(client, run_id)

        events = [e for e in received if e.get("event") != "heartbeat"]
        assert len(events) > 0, "No events received"

        # The last event must be the terminal one
        assert events[-1]["event"] == "evolution_complete", (
            f"Last event was {events[-1]['event']!r}, expected 'evolution_complete'"
        )

        # No events after evolution_complete
        terminal_indices = [
            i for i, e in enumerate(events) if e["event"] == "evolution_complete"
        ]
        assert len(terminal_indices) == 1, "Expected exactly one evolution_complete"
        assert terminal_indices[0] == len(events) - 1


# ---------------------------------------------------------------------------
# Test 3: all events carry a timestamp
# ---------------------------------------------------------------------------


def test_all_events_have_timestamps():
    with TestClient(app) as client:
        run_id = "integration-timestamps"
        received = _collect_events_via_ws(client, run_id)

        events = [e for e in received if e.get("event") != "heartbeat"]
        assert len(events) > 0, "No events to validate"

        missing_ts = [e["event"] for e in events if "timestamp" not in e]
        assert not missing_ts, f"Events missing 'timestamp': {missing_ts}"
