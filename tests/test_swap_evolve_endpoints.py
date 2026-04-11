"""Wave 5-2 tests for the swap-variant + evolve-variant endpoints.

Backend-only tests against the FastAPI TestClient. We seed a family with
two variants in one dimension, swap the active flag, and verify both the
endpoint response and the persisted state.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from skillforge.db import (
    get_variant_evolutions_for_run,
    init_db,
    save_genome,
    save_run,
    save_skill_family,
    save_variant,
)
from skillforge.main import app
from skillforge.models import EvolutionRun, SkillFamily, SkillGenome, Variant


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _run(unique_id: str = ""):
    """Set up a run + family + 2 variants in one dimension. Returns
    (family_id, [variant_ids])."""
    suffix = unique_id or uuid.uuid4().hex[:8]

    async def _setup():
        await init_db()
        run_id = f"run_swap_{suffix}"
        family_id = f"fam_swap_{suffix}"

        await save_run(
            EvolutionRun(
                id=run_id,
                mode="domain",
                specialization="x",
                population_size=2,
                num_generations=1,
                status="complete",
                created_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
        )
        await save_skill_family(
            SkillFamily(
                id=family_id,
                slug=f"fam-swap-{suffix}",
                label="Swap Test",
                specialization="x",
                decomposition_strategy="atomic",
                created_at=datetime.now(UTC),
            )
        )

        # Two genomes, two variants in the same dimension
        genome1 = SkillGenome(
            id=f"g1_{suffix}",
            generation=0,
            skill_md_content="# g1\n",
            frontmatter={"name": "g1"},
            traits=[],
            meta_strategy="",
        )
        genome2 = SkillGenome(
            id=f"g2_{suffix}",
            generation=0,
            skill_md_content="# g2\n",
            frontmatter={"name": "g2"},
            traits=[],
            meta_strategy="",
        )
        await save_genome(genome1, run_id)
        await save_genome(genome2, run_id)

        variant1 = Variant(
            id=f"v1_{suffix}",
            family_id=family_id,
            dimension="mock-strategy",
            tier="capability",
            genome_id=genome1.id,
            fitness_score=0.8,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        variant2 = Variant(
            id=f"v2_{suffix}",
            family_id=family_id,
            dimension="mock-strategy",
            tier="capability",
            genome_id=genome2.id,
            fitness_score=0.7,
            is_active=False,
            created_at=datetime.now(UTC),
        )
        await save_variant(variant1)
        await save_variant(variant2)

        return family_id, [variant1.id, variant2.id]

    return asyncio.new_event_loop().run_until_complete(_setup())


def test_swap_variant_happy_path(client: TestClient):
    family_id, variant_ids = _run()

    # Initially v1 is active
    initial = client.get(f"/api/families/{family_id}/variants").json()
    active_initial = [v for v in initial if v["is_active"]]
    assert len(active_initial) == 1
    assert active_initial[0]["id"] == variant_ids[0]

    # Swap to v2
    resp = client.post(
        f"/api/families/{family_id}/swap-variant",
        json={"dimension": "mock-strategy", "variant_id": variant_ids[1]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["family_id"] == family_id
    assert body["dimension"] == "mock-strategy"
    assert body["active_variant_id"] == variant_ids[1]

    # Verify persistence
    after = client.get(f"/api/families/{family_id}/variants").json()
    active_after = [v for v in after if v["is_active"]]
    assert len(active_after) == 1
    assert active_after[0]["id"] == variant_ids[1]


def test_swap_variant_404_on_unknown_family(client: TestClient):
    resp = client.post(
        "/api/families/nope/swap-variant",
        json={"dimension": "x", "variant_id": "y"},
    )
    assert resp.status_code == 404


def test_swap_variant_404_on_unknown_dimension(client: TestClient):
    family_id, _ = _run()
    resp = client.post(
        f"/api/families/{family_id}/swap-variant",
        json={"dimension": "nonexistent", "variant_id": "y"},
    )
    assert resp.status_code == 404


def test_swap_variant_404_on_unknown_variant(client: TestClient):
    family_id, _ = _run()
    resp = client.post(
        f"/api/families/{family_id}/swap-variant",
        json={"dimension": "mock-strategy", "variant_id": "not_a_real_id"},
    )
    assert resp.status_code == 404


def test_evolve_variant_creates_pending_row(client: TestClient):
    family_id, _ = _run()
    # Need a parent_run_id — pass one explicitly that we know exists
    suffix = family_id.split("_")[-1]
    parent_run_id = f"run_swap_{suffix}"

    resp = client.post(
        f"/api/families/{family_id}/evolve-variant",
        json={
            "dimension": "mock-strategy",
            "population_size": 3,
            "num_generations": 2,
            "parent_run_id": parent_run_id,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["family_id"] == family_id
    assert body["dimension"] == "mock-strategy"
    assert body["status"] == "pending"
    assert body["tier"] == "capability"
    assert body["variant_evolution_id"].startswith("vevo_")

    async def _verify():
        rows = await get_variant_evolutions_for_run(parent_run_id)
        assert any(r.id == body["variant_evolution_id"] for r in rows)
        target = next(r for r in rows if r.id == body["variant_evolution_id"])
        assert target.status == "pending"
        assert target.population_size == 3
        assert target.num_generations == 2
        assert target.parent_run_id == parent_run_id

    asyncio.new_event_loop().run_until_complete(_verify())


def test_evolve_variant_404_on_unknown_family(client: TestClient):
    resp = client.post(
        "/api/families/nope/evolve-variant",
        json={"dimension": "mock-strategy"},
    )
    assert resp.status_code == 404
