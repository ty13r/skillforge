"""Wave 2-2 integration tests — POST /evolve runs the Taxonomist before
spawning the evolution task.

We mock the Taxonomist's LLM call (via the agent's ``classify_and_decompose``
in the routes module) and the run_evolution background task (so we don't
actually start the engine). The goal is to prove the wiring:

- ``run.family_id`` and ``run.evolution_mode`` are stamped from the
  Taxonomist's output.
- The ``taxonomy_classified`` event lands on the run's queue.
- An explicit ``evolution_mode`` in the request overrides the Taxonomist's
  recommendation.
- A failure in the Taxonomist call falls back to ``molecular`` mode without
  raising.
- A missing API key short-circuits the call entirely.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from skillforge.agents.taxonomist import (
    ReuseRecommendation,
    TaxonomistOutput,
    VariantDimension,
)
from skillforge.engine.events import drop_queue, get_queue
from skillforge.main import app
from skillforge.models import SkillFamily, TaxonomyNode


def _make_taxonomist_output(
    *,
    family_slug: str = "django-rest-pytest",
    evolution_mode: str = "atomic",
) -> TaxonomistOutput:
    """Hand-build a TaxonomistOutput so we can hardcode mock results."""
    domain = TaxonomyNode(
        id="dom_test", level="domain", slug="testing", label="Testing"
    )
    focus = TaxonomyNode(
        id="foc_unit",
        level="focus",
        slug="unit-tests",
        label="Unit Tests",
        parent_id="dom_test",
    )
    language = TaxonomyNode(
        id="lang_py",
        level="language",
        slug="python",
        label="Python",
        parent_id="foc_unit",
    )
    family = SkillFamily(
        id="fam_test",
        slug=family_slug,
        label="Django REST Pytest",
        specialization="x",
        domain_id=domain.id,
        focus_id=focus.id,
        language_id=language.id,
        decomposition_strategy=evolution_mode,
    )
    dims = (
        [
            VariantDimension(
                name="fixture-strategy",
                tier="foundation",
                description="how fixtures are organized",
                evaluation_focus="reusability",
            ),
            VariantDimension(
                name="mock-strategy",
                tier="capability",
                description="how external deps are isolated",
                evaluation_focus="isolation",
            ),
        ]
        if evolution_mode == "atomic"
        else []
    )
    return TaxonomistOutput(
        family=family,
        domain=domain,
        focus=focus,
        language=language,
        evolution_mode=evolution_mode,
        variant_dimensions=dims,
        reuse_recommendations=[
            ReuseRecommendation(
                source_family_slug="flask-pytest",
                dimension="mock-strategy",
                variant_slug="responses-mock",
                fitness=0.91,
                reason="proven",
            )
        ]
        if evolution_mode == "atomic"
        else [],
        created_new_nodes=[],
        justification="mocked output",
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _ensure_api_key(monkeypatch):
    """All tests in this module assume an API key is set; if the test env
    doesn't have one, fake it so the early-return path doesn't fire."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    # The skillforge.config module reads ANTHROPIC_API_KEY at import time,
    # so we also patch the module-level constant.
    monkeypatch.setattr(
        "skillforge.config.ANTHROPIC_API_KEY", "test-key", raising=False
    )
    yield


def _drain_queue(run_id: str) -> list[dict]:
    """Pull every event off the run's queue without blocking."""
    queue = get_queue(run_id)
    events = []
    while True:
        try:
            events.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            break
    return events


def test_evolve_classifies_run_via_taxonomist(client: TestClient):
    """Happy path — Taxonomist returns atomic, run is stamped + event emitted."""
    mock_output = _make_taxonomist_output(evolution_mode="atomic")

    with patch(
        "skillforge.agents.taxonomist.classify_and_decompose",
        new=AsyncMock(return_value=mock_output),
    ), patch(
        "skillforge.api.routes.run_evolution",
        new=AsyncMock(return_value=None),
    ):
        resp = client.post(
            "/api/evolve",
            json={
                "mode": "domain",
                "specialization": "Generate pytest tests for Django",
                "population_size": 2,
                "num_generations": 1,
                "max_budget_usd": 1.0,
            },
        )

    assert resp.status_code == 200
    run_id = resp.json()["run_id"]

    # Inspect the run row that just got persisted
    from skillforge.db import get_run

    async def _check():
        run = await get_run(run_id)
        assert run is not None
        assert run.family_id == "fam_test"
        assert run.evolution_mode == "atomic"

    asyncio.new_event_loop().run_until_complete(_check())

    events = _drain_queue(run_id)
    event_types = [e["event"] for e in events]
    assert "taxonomy_classified" in event_types
    assert "decomposition_complete" in event_types

    classified = next(e for e in events if e["event"] == "taxonomy_classified")
    assert classified["family_id"] == "fam_test"
    assert classified["evolution_mode"] == "atomic"

    decomp = next(e for e in events if e["event"] == "decomposition_complete")
    assert decomp["dimension_count"] == 2

    drop_queue(run_id)


def test_evolve_explicit_mode_overrides_taxonomist(client: TestClient):
    """If the request specifies evolution_mode, use it regardless of what
    the Taxonomist returns."""
    mock_output = _make_taxonomist_output(evolution_mode="atomic")

    with patch(
        "skillforge.agents.taxonomist.classify_and_decompose",
        new=AsyncMock(return_value=mock_output),
    ), patch(
        "skillforge.api.routes.run_evolution",
        new=AsyncMock(return_value=None),
    ):
        resp = client.post(
            "/api/evolve",
            json={
                "mode": "domain",
                "specialization": "x",
                "evolution_mode": "molecular",
                "population_size": 2,
                "num_generations": 1,
                "max_budget_usd": 1.0,
            },
        )

    assert resp.status_code == 200
    run_id = resp.json()["run_id"]

    from skillforge.db import get_run

    async def _check():
        run = await get_run(run_id)
        assert run is not None
        # Family was still set by the Taxonomist
        assert run.family_id == "fam_test"
        # But mode was forced to molecular by the caller
        assert run.evolution_mode == "molecular"

    asyncio.new_event_loop().run_until_complete(_check())

    drop_queue(run_id)


def test_evolve_taxonomist_failure_falls_back_to_molecular(client: TestClient):
    """If the Taxonomist call raises, the run still gets created in
    molecular mode and family_id stays None."""
    with patch(
        "skillforge.agents.taxonomist.classify_and_decompose",
        new=AsyncMock(side_effect=RuntimeError("simulated LLM crash")),
    ), patch(
        "skillforge.api.routes.run_evolution",
        new=AsyncMock(return_value=None),
    ):
        resp = client.post(
            "/api/evolve",
            json={
                "mode": "domain",
                "specialization": "anything",
                "population_size": 2,
                "num_generations": 1,
                "max_budget_usd": 1.0,
            },
        )

    assert resp.status_code == 200
    run_id = resp.json()["run_id"]

    from skillforge.db import get_run

    async def _check():
        run = await get_run(run_id)
        assert run is not None
        assert run.family_id is None
        assert run.evolution_mode == "molecular"

    asyncio.new_event_loop().run_until_complete(_check())

    # No taxonomy_classified event should have been emitted
    events = _drain_queue(run_id)
    event_types = [e["event"] for e in events]
    assert "taxonomy_classified" not in event_types

    drop_queue(run_id)


def test_evolve_skips_taxonomist_when_no_api_key(client: TestClient, monkeypatch):
    """No API key → skip the Taxonomist entirely, default to molecular."""
    monkeypatch.setattr(
        "skillforge.config.ANTHROPIC_API_KEY", None, raising=False
    )

    classify_mock = AsyncMock()
    with patch(
        "skillforge.agents.taxonomist.classify_and_decompose",
        new=classify_mock,
    ), patch(
        "skillforge.api.routes.run_evolution",
        new=AsyncMock(return_value=None),
    ):
        resp = client.post(
            "/api/evolve",
            json={
                "mode": "domain",
                "specialization": "x",
                "population_size": 2,
                "num_generations": 1,
                "max_budget_usd": 1.0,
            },
        )

    assert resp.status_code == 200
    classify_mock.assert_not_called()  # Taxonomist never invoked

    run_id = resp.json()["run_id"]
    drop_queue(run_id)
