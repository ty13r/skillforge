"""API + WebSocket tests for skillforge.api."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from skillforge.engine.events import clear_all, get_queue
from skillforge.main import app
from skillforge.models import EvolutionRun, SkillGenome


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_event_queues():
    """Clear all event queues before each test to prevent state leakage."""
    clear_all()
    yield
    clear_all()


def _make_skill(skill_id: str = "skill-1", generation: int = 0) -> SkillGenome:
    return SkillGenome(
        id=skill_id,
        generation=generation,
        skill_md_content="# Test Skill\n",
        traits=["efficient", "precise"],
        maturity="draft",
        pareto_objectives={"quality": 0.8, "speed": 0.7},
    )


def _make_run(
    run_id: str = "run-1",
    status: str = "complete",
    best_skill: SkillGenome | None = None,
) -> EvolutionRun:
    from datetime import UTC, datetime

    return EvolutionRun(
        id=run_id,
        mode="domain",
        specialization="python",
        population_size=5,
        num_generations=3,
        status=status,
        created_at=datetime.now(UTC),
        total_cost_usd=0.5,
        best_skill=best_skill,
    )


# ---------------------------------------------------------------------------
# 1. Health check
# ---------------------------------------------------------------------------


def test_root_health_check(client):
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# 2. POST /evolve — happy path (domain mode)
# ---------------------------------------------------------------------------


def test_evolve_creates_run(client):
    with (
        patch("skillforge.api.routes.init_db", new_callable=AsyncMock),
        patch("skillforge.api.routes.save_run", new_callable=AsyncMock),
        patch("skillforge.api.routes.run_evolution", new_callable=AsyncMock) as mock_evo,
    ):
        mock_evo.return_value = None

        resp = client.post(
            "/evolve",
            json={
                "mode": "domain",
                "specialization": "python-data-science",
                "population_size": 2,
                "num_generations": 1,
                "max_budget_usd": 1.0,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "run_id" in data
    assert "ws_url" in data
    run_id = data["run_id"]
    # run_id should be a UUID-like string (36 chars with dashes)
    assert len(run_id) == 36
    assert data["ws_url"] == f"/ws/evolve/{run_id}"


# ---------------------------------------------------------------------------
# 3. POST /evolve — meta mode returns 501
# ---------------------------------------------------------------------------


def test_evolve_rejects_meta_mode_in_mvp(client):
    resp = client.post("/evolve", json={"mode": "meta"})
    assert resp.status_code == 501


# ---------------------------------------------------------------------------
# 4. POST /evolve — domain mode without specialization returns 400
# ---------------------------------------------------------------------------


def test_evolve_rejects_domain_mode_without_specialization(client):
    resp = client.post(
        "/evolve",
        json={"mode": "domain", "population_size": 2, "num_generations": 1, "max_budget_usd": 1.0},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 5. GET /runs/{run_id} — 404 on missing run
# ---------------------------------------------------------------------------


def test_get_run_returns_404_if_missing(client):
    with patch("skillforge.api.routes.get_run", new_callable=AsyncMock, return_value=None):
        resp = client.get("/runs/nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 6. GET /runs/{run_id} — returns detail for existing run
# ---------------------------------------------------------------------------


def test_get_run_returns_detail(client):
    skill = _make_skill()
    run = _make_run(best_skill=skill)

    with patch("skillforge.api.routes.get_run", new_callable=AsyncMock, return_value=run):
        resp = client.get(f"/runs/{run.id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == run.id
    assert data["mode"] == "domain"
    assert data["specialization"] == "python"
    assert data["status"] == "complete"
    assert data["population_size"] == 5
    assert data["num_generations"] == 3
    assert data["best_skill_id"] == skill.id


# ---------------------------------------------------------------------------
# 7. GET /runs — returns array of runs
# ---------------------------------------------------------------------------


def test_list_runs_returns_array(client):
    runs = [_make_run(run_id="run-1"), _make_run(run_id="run-2")]

    with patch("skillforge.api.routes.list_runs", new_callable=AsyncMock, return_value=runs):
        resp = client.get("/runs")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    ids = {r["id"] for r in data}
    assert ids == {"run-1", "run-2"}


# ---------------------------------------------------------------------------
# 8. GET /runs/{id}/export?format=skill_md
# ---------------------------------------------------------------------------


def test_export_skill_md_format(client):
    skill = _make_skill()
    run = _make_run(best_skill=skill)

    with (
        patch("skillforge.api.routes.get_run", new_callable=AsyncMock, return_value=run),
        patch("skillforge.api.routes.export_skill_md", return_value="fake md content"),
    ):
        resp = client.get(f"/runs/{run.id}/export?format=skill_md")

    assert resp.status_code == 200
    assert "text/markdown" in resp.headers["content-type"]
    assert resp.text == "fake md content"


# ---------------------------------------------------------------------------
# 9. GET /runs/{id}/export?format=skill_dir — returns zip bytes
# ---------------------------------------------------------------------------


def test_export_skill_dir_format_returns_zip(client):
    skill = _make_skill()
    run = _make_run(best_skill=skill)

    with (
        patch("skillforge.api.routes.get_run", new_callable=AsyncMock, return_value=run),
        patch("skillforge.api.routes.export_skill_zip", return_value=b"PK...fake zip"),
    ):
        resp = client.get(f"/runs/{run.id}/export?format=skill_dir")

    assert resp.status_code == 200
    assert "application/zip" in resp.headers["content-type"]
    assert resp.content == b"PK...fake zip"


# ---------------------------------------------------------------------------
# 10. GET /runs/nonexistent/export — 404
# ---------------------------------------------------------------------------


def test_export_404_on_missing_run(client):
    with patch("skillforge.api.routes.get_run", new_callable=AsyncMock, return_value=None):
        resp = client.get("/runs/nonexistent/export")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 11. GET /runs/{id}/export — 400 when run has no best_skill
# ---------------------------------------------------------------------------


def test_export_400_on_no_best_skill(client):
    run = _make_run(best_skill=None)

    with patch("skillforge.api.routes.get_run", new_callable=AsyncMock, return_value=run):
        resp = client.get(f"/runs/{run.id}/export")

    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 12. GET /runs/{id}/lineage — returns nodes and edges
# ---------------------------------------------------------------------------


def test_lineage_returns_nodes_and_edges(client):
    from skillforge.models import Generation

    skill = _make_skill()
    gen = Generation(number=0, skills=[skill], results=[])
    run = _make_run(best_skill=skill)
    run.generations = [gen]

    fake_edges = [
        {"parent_id": "parent-1", "child_id": skill.id, "mutation_type": "mutation"}
    ]

    with (
        patch("skillforge.api.routes.get_run", new_callable=AsyncMock, return_value=run),
        patch("skillforge.api.routes.get_lineage", new_callable=AsyncMock, return_value=fake_edges),
    ):
        resp = client.get(f"/runs/{run.id}/lineage")

    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["id"] == skill.id
    assert len(data["edges"]) == 1
    assert data["edges"][0]["parent_id"] == "parent-1"
    assert data["edges"][0]["child_id"] == skill.id
    assert data["edges"][0]["mutation_type"] == "mutation"


# ---------------------------------------------------------------------------
# 13. WebSocket — streams events and closes after terminal event
# ---------------------------------------------------------------------------


def test_websocket_streams_events(client):
    run_id = "ws-test-run"

    # Pre-populate the queue with events including a terminal one
    q = get_queue(run_id)
    q.put_nowait({"event": "run_started", "specialization": "python"})
    q.put_nowait({"event": "generation_started", "generation": 0})
    q.put_nowait({"event": "evolution_complete", "best_skill_id": "skill-abc", "total_cost_usd": 0.1})

    received = []
    with client.websocket_connect(f"/ws/evolve/{run_id}") as ws:
        # Receive all three events
        for _ in range(3):
            msg = ws.receive_json()
            received.append(msg)

    assert len(received) == 3
    assert received[0]["event"] == "run_started"
    assert received[1]["event"] == "generation_started"
    assert received[2]["event"] == "evolution_complete"


# ---------------------------------------------------------------------------
# 14. WebSocket — handles client disconnect gracefully
# ---------------------------------------------------------------------------


def test_websocket_handles_disconnect(client):
    run_id = "ws-disconnect-run"
    # Don't put anything in the queue — the client will disconnect immediately

    # The server should not raise even when the client closes before any events
    with client.websocket_connect(f"/ws/evolve/{run_id}") as ws:
        ws.close()

    # If we get here without an exception, the server handled disconnect cleanly
