"""Wave 1-4 — HTTP tests for the taxonomy + families + variants endpoints.

The FastAPI lifespan populates the taxonomy from ``SEED_SKILLS`` on app start,
so every test in this module can rely on a known-good baseline of 7 domains,
14 focuses, and 15 families (or more — assertions use ``>=`` not ``==``).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from skillforge.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient wrapped as a context manager so the FastAPI lifespan runs.

    The bare ``TestClient(app)`` pattern (used elsewhere in the suite)
    does NOT trigger ``lifespan`` — it only intercepts HTTP calls. This
    module's tests depend on ``load_taxonomy()`` having bootstrapped the
    DB with real seed families like ``terraform-module-full``, so we
    must enter ``TestClient`` as a context manager. An isolated temp
    DB keeps the bootstrap from stomping on the dev DB and keeps tests
    independent of previous runs.
    """
    monkeypatch.setenv("SKILLFORGE_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("SKILLFORGE_DATA_DIR", str(tmp_path))

    import importlib

    from skillforge import config as cfg
    from skillforge.db import database as db_module
    from skillforge.db import queries as queries_module

    importlib.reload(cfg)
    importlib.reload(db_module)
    importlib.reload(queries_module)

    with TestClient(app) as c:
        yield c

    # Restore module state for downstream tests that import config.
    monkeypatch.delenv("SKILLFORGE_DB", raising=False)
    monkeypatch.delenv("SKILLFORGE_DATA_DIR", raising=False)
    importlib.reload(cfg)
    importlib.reload(db_module)
    importlib.reload(queries_module)


# ---------------------------------------------------------------------------
# /api/taxonomy
# ---------------------------------------------------------------------------


def test_list_taxonomy_returns_nodes(client: TestClient) -> None:
    resp = client.get("/api/taxonomy")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 28  # 7 domains + 14 focuses + 14+ languages

    levels = {n["level"] for n in data}
    assert levels == {"domain", "focus", "language"}

    # Ordering invariant: domain rows come before focus which come before language
    level_order = {"domain": 0, "focus": 1, "language": 2}
    indices = [level_order[n["level"]] for n in data]
    assert indices == sorted(indices)


def test_taxonomy_contains_known_domain_slugs(client: TestClient) -> None:
    resp = client.get("/api/taxonomy")
    assert resp.status_code == 200
    domain_slugs = {n["slug"] for n in resp.json() if n["level"] == "domain"}
    # These seven are declared in taxonomy_seeds._SEED_CLASSIFICATIONS
    expected = {
        "code-quality",
        "testing",
        "development",
        "data",
        "devops",
        "security",
        "documentation",
    }
    assert expected.issubset(domain_slugs)


def test_get_taxonomy_node_returns_children(client: TestClient) -> None:
    resp = client.get("/api/taxonomy")
    domains = [n for n in resp.json() if n["level"] == "domain"]
    assert domains
    # Use the devops domain — it has four focuses so children will be non-empty
    devops = next(n for n in domains if n["slug"] == "devops")

    detail = client.get(f"/api/taxonomy/{devops['id']}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["node"]["id"] == devops["id"]
    assert payload["node"]["level"] == "domain"
    assert isinstance(payload["children"], list)
    assert len(payload["children"]) >= 4  # containers, ci-cd, iac, observability
    assert all(c["level"] == "focus" for c in payload["children"])
    assert all(c["parent_id"] == devops["id"] for c in payload["children"])


def test_get_taxonomy_node_404_on_unknown(client: TestClient) -> None:
    resp = client.get("/api/taxonomy/not-a-real-node-id")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# /api/families
# ---------------------------------------------------------------------------


def test_list_families_unfiltered(client: TestClient) -> None:
    resp = client.get("/api/families")
    assert resp.status_code == 200
    fams = resp.json()
    assert isinstance(fams, list)
    assert len(fams) >= 15
    # Every family should have a slug and a decomposition_strategy
    for fam in fams:
        assert "slug" in fam
        assert fam["decomposition_strategy"] in ("atomic", "molecular")


def test_list_families_filtered_by_domain(client: TestClient) -> None:
    # Find the devops domain id first
    taxonomy = client.get("/api/taxonomy").json()
    devops = next(n for n in taxonomy if n["level"] == "domain" and n["slug"] == "devops")

    resp = client.get(f"/api/families?domain={devops['id']}")
    assert resp.status_code == 200
    fams = resp.json()
    assert len(fams) >= 4  # ci-cd-pipeline, dockerfile-optimizer, terraform-module, error-handler
    assert all(f["domain_id"] == devops["id"] for f in fams)


def test_list_families_empty_domain_returns_empty(client: TestClient) -> None:
    resp = client.get("/api/families?domain=nonexistent-id")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_family_detail_known_slug(client: TestClient) -> None:
    # Resolve the terraform-module-full family by listing then filtering
    fams = client.get("/api/families").json()
    terraform = next(
        (f for f in fams if f["slug"] == "terraform-module-full"), None
    )
    assert terraform is not None, "bootstrap should have produced terraform-module-full"

    resp = client.get(f"/api/families/{terraform['id']}")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["family"]["slug"] == "terraform-module-full"
    assert payload["family"]["decomposition_strategy"] in ("atomic", "molecular")
    assert payload["variant_count"] == 0  # no variants yet — wave 3+ creates them
    assert payload["active_variants"] == []


def test_get_family_detail_404_on_unknown(client: TestClient) -> None:
    resp = client.get("/api/families/not-a-real-family")
    assert resp.status_code == 404


def test_list_family_variants_empty_by_default(client: TestClient) -> None:
    # Pick a known seeded family that no other test will populate with
    # variants — terraform-module-full is created by the bootstrap loader
    # and stays untouched by the rest of the suite.
    fams = client.get("/api/families").json()
    target = next(
        (f for f in fams if f["slug"] == "terraform-module-full"), None
    )
    assert target is not None, "bootstrap loader should have created terraform-module-full"
    resp = client.get(f"/api/families/{target['id']}/variants")
    assert resp.status_code == 200
    assert resp.json() == []  # no variants on a never-evolved seed family


def test_list_family_variants_404_on_unknown_family(client: TestClient) -> None:
    resp = client.get("/api/families/not-a-real-family/variants")
    assert resp.status_code == 404
