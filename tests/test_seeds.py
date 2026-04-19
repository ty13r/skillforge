"""Tests for the curated seed library + fork-from-seed flow.

Carries over the testing items from PLAN-V1.1 §1.5 + §Testing strategy §1
that were specified but never landed during the v1.1 batch. Targets the
SHIPPED implementation (in-memory PENDING_PARENTS dict, not a seed_skill_id
column).

Coverage:
- ``seed_loader.load_seeds()`` idempotency: hash-match short-circuits.
- ``seed_loader.load_seeds()`` refresh: differing hash triggers re-insert.
- ``_content_hash()`` is deterministic across calls.
- ``_build_genome()`` shape: SkillGenome with ``maturity=hardened``.
- ``spawner.spawn_from_parent`` elite carry, pop_size variants, validator
  filtering, ``pop_size < 1`` rejection, JSON-parse fallback path.
- ``POST /api/evolve/from-parent`` with ``parent_source="registry"``: happy
  path resolves a real seed and stashes it in ``PENDING_PARENTS``.
- 404s on unknown registry skill_id and unknown upload_id.
- 400 on a bad ``parent_source`` value.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from skillforge.db import seed_loader
from skillforge.engine.run_registry import registry as _run_registry
from skillforge.main import app
from skillforge.models import EvolutionRun, Generation, SkillGenome

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_pending_parents():
    """RunRegistry is process-level state — wipe between tests."""
    _run_registry._pending_parents.clear()
    yield
    _run_registry._pending_parents.clear()


def _make_seed_skill(skill_id: str = "seed-foo", description: str = "Use when foo. NOT for bar.") -> SkillGenome:
    """Build a SkillGenome that looks like a curated seed."""
    md = f"""---
name: foo-skill
description: {description}
---

# Foo Skill

## Workflow
- Step one
- Step two

## Examples
**Example 1:** input → output
**Example 2:** input → output
"""
    return SkillGenome(
        id=skill_id,
        generation=0,
        skill_md_content=md,
        frontmatter={"name": "foo-skill", "description": description},
        traits=["edge-case-first", "stdlib-only"],
        meta_strategy="One-shot Foo",
        maturity="hardened",
    )


def _make_seed_run(skills: list[SkillGenome], hash_marker: str = "abc123def456") -> EvolutionRun:
    """Build a synthetic seed-library run that mimics the loader's output."""
    gen = Generation(
        number=0,
        skills=skills,
        results=[],
        best_fitness=0.0,
        avg_fitness=0.0,
    )
    return EvolutionRun(
        id="seed-library",
        mode="curated",
        specialization=f"Curated Gen 0 Skill Library · {len(skills)} seeds. Hash: {hash_marker}",
        population_size=len(skills),
        num_generations=1,
        generations=[gen],
        status="complete",
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        best_skill=skills[0] if skills else None,
        total_cost_usd=0.0,
        max_budget_usd=0.0,
    )


# ---------------------------------------------------------------------------
# 1. Hash determinism
# ---------------------------------------------------------------------------


def test_content_hash_is_deterministic():
    """Computing the hash twice on the same SEED_SKILLS list returns the same value."""
    h1 = seed_loader._content_hash()
    h2 = seed_loader._content_hash()
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


def test_content_hash_is_sensitive_to_seed_changes(monkeypatch):
    """Mutating the seed list (or any nested field) changes the hash."""
    h_original = seed_loader._content_hash()

    fake_seeds = [
        {
            "id": "test-seed",
            "slug": "test",
            "title": "Test",
            "category": "Test",
            "difficulty": "easy",
            "frontmatter": {"name": "test", "description": "Test description."},
            "skill_md_content": "---\nname: test\ndescription: Test\n---\n# Test",
            "supporting_files": {},
            "traits": ["a"],
            "meta_strategy": "test",
        }
    ]
    monkeypatch.setattr(seed_loader, "SEED_SKILLS", fake_seeds)
    h_after = seed_loader._content_hash()
    assert h_after != h_original


# ---------------------------------------------------------------------------
# 2. _build_genome shape
# ---------------------------------------------------------------------------


def test_build_genome_produces_hardened_maturity():
    """Curated seeds ship at maturity='hardened' so they can be exported directly."""
    seed = {
        "id": "seed-foo",
        "slug": "foo",
        "title": "Foo",
        "category": "Test",
        "difficulty": "easy",
        "frontmatter": {"name": "foo", "description": "Use when foo."},
        "skill_md_content": "---\nname: foo\ndescription: Use when foo.\n---\n# Foo",
        "supporting_files": {"scripts/x.sh": "#!/bin/bash"},
        "traits": ["a", "b"],
        "meta_strategy": "do foo",
    }
    genome = seed_loader._build_genome(seed)
    assert isinstance(genome, SkillGenome)
    assert genome.id == "seed-foo"
    assert genome.generation == 0
    assert genome.maturity == "hardened"
    assert genome.traits == ["a", "b"]
    assert genome.supporting_files == {"scripts/x.sh": "#!/bin/bash"}
    assert genome.meta_strategy == "do foo"


# ---------------------------------------------------------------------------
# 3. load_seeds idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_seeds_inserts_when_run_missing():
    """First boot: get_run returns None → save_run is called once."""
    save_mock = AsyncMock()
    with (
        patch("skillforge.db.seed_loader.get_run", new_callable=AsyncMock, return_value=None),
        patch("skillforge.db.seed_loader.save_run", save_mock),
    ):
        await seed_loader.load_seeds()

    save_mock.assert_called_once()
    saved_run = save_mock.call_args.args[0]
    assert saved_run.id == seed_loader.SEED_RUN_ID
    assert saved_run.mode == "curated"
    assert saved_run.status == "complete"


@pytest.mark.asyncio
async def test_load_seeds_skips_when_hash_unchanged():
    """Second boot with matching hash → save_run NOT called."""
    current_hash_prefix = seed_loader._content_hash()[:12]
    existing_run = _make_seed_run(
        [_make_seed_skill("seed-1")],
        hash_marker=current_hash_prefix,
    )

    save_mock = AsyncMock()
    with (
        patch("skillforge.db.seed_loader.get_run", new_callable=AsyncMock, return_value=existing_run),
        patch("skillforge.db.seed_loader.save_run", save_mock),
    ):
        await seed_loader.load_seeds()

    save_mock.assert_not_called()


@pytest.mark.asyncio
async def test_load_seeds_reloads_on_hash_mismatch():
    """Existing run with stale hash → save_run IS called (re-insert)."""
    stale_run = _make_seed_run(
        [_make_seed_skill("seed-1")],
        hash_marker="STALEHASH123",
    )

    save_mock = AsyncMock()
    with (
        patch("skillforge.db.seed_loader.get_run", new_callable=AsyncMock, return_value=stale_run),
        patch("skillforge.db.seed_loader.save_run", save_mock),
    ):
        await seed_loader.load_seeds()

    save_mock.assert_called_once()
    saved_run = save_mock.call_args.args[0]
    # The new run should carry the live hash, not the stale marker
    assert seed_loader._content_hash()[:12] in saved_run.specialization
    assert "STALEHASH123" not in saved_run.specialization


# ---------------------------------------------------------------------------
# 4. spawn_from_parent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spawn_from_parent_pop_size_one_returns_elite_only():
    """pop_size=1 short-circuits the LLM call and returns just the elite."""
    from skillforge.agents.spawner import spawn_from_parent

    parent = _make_seed_skill("parent-1")

    with patch(
        "skillforge.agents.spawner._generate", new_callable=AsyncMock
    ) as mock_gen:
        result = await spawn_from_parent(parent, pop_size=1)

    assert len(result) == 1
    elite = result[0]
    assert elite.skill_md_content == parent.skill_md_content
    assert elite.traits == parent.traits
    assert elite.meta_strategy == parent.meta_strategy
    assert elite.parent_ids == [parent.id]
    assert "elite-carry" in elite.mutations
    # Elite carry path must NOT call the LLM at all
    mock_gen.assert_not_called()


@pytest.mark.asyncio
async def test_spawn_from_parent_pop_size_three_returns_elite_plus_mutants():
    """pop_size=3 → elite + 2 valid mutations from a mocked LLM response."""
    from skillforge.agents.spawner import spawn_from_parent

    parent = _make_seed_skill("parent-2")

    # Build 2 valid mutation responses (each must pass validate_skill_structure)
    mutant_a = {
        "skill_md_content": (
            "---\n"
            "name: foo-skill-a\n"
            "description: Variant A. Use when foo with a different angle. NOT for bar.\n"
            "---\n\n"
            "# Foo Skill A\n\n"
            "## Workflow\n- A1\n- A2\n\n"
            "## Examples\n**Example 1:** in → out\n**Example 2:** in → out\n"
        ),
        "traits": ["edge-case-first", "concise"],
        "meta_strategy": "Variant A meta",
        "mutations": ["description-expansion"],
        "mutation_rationale": "broader trigger surface",
    }
    mutant_b = {
        "skill_md_content": (
            "---\n"
            "name: foo-skill-b\n"
            "description: Variant B. Use when foo, even if user says baz. NOT for bar.\n"
            "---\n\n"
            "# Foo Skill B\n\n"
            "## Workflow\n- B1\n- B2\n\n"
            "## Examples\n**Example 1:** in → out\n**Example 2:** in → out\n"
        ),
        "traits": ["stdlib-only", "type-hinted"],
        "meta_strategy": "Variant B meta",
        "mutations": ["trait-emphasis"],
        "mutation_rationale": "lean harder into stdlib",
    }

    response_text = json.dumps([mutant_a, mutant_b])

    with patch(
        "skillforge.agents.spawner._generate",
        new_callable=AsyncMock,
        return_value=response_text,
    ):
        result = await spawn_from_parent(parent, pop_size=3)

    assert len(result) == 3
    # First entry is the elite (parent content preserved)
    assert result[0].skill_md_content == parent.skill_md_content
    assert "elite-carry" in result[0].mutations
    # Mutants reference the parent
    for mutant in result[1:]:
        assert parent.id in mutant.parent_ids
        assert mutant.maturity == "draft"


@pytest.mark.asyncio
async def test_spawn_from_parent_falls_back_to_elite_only_on_bad_llm_response():
    """If LLM returns garbage, spawn_from_parent gracefully degrades to elite-only."""
    from skillforge.agents.spawner import spawn_from_parent

    parent = _make_seed_skill("parent-3")

    with patch(
        "skillforge.agents.spawner._generate",
        new_callable=AsyncMock,
        return_value="this is not JSON, just prose nonsense",
    ):
        result = await spawn_from_parent(parent, pop_size=4)

    # Graceful degradation: only the elite survives
    assert len(result) == 1
    assert result[0].skill_md_content == parent.skill_md_content


@pytest.mark.asyncio
async def test_spawn_from_parent_invalid_pop_size_raises():
    """pop_size < 1 is rejected up-front."""
    from skillforge.agents.spawner import spawn_from_parent

    parent = _make_seed_skill("parent-4")
    with pytest.raises(ValueError, match="pop_size"):
        await spawn_from_parent(parent, pop_size=0)


@pytest.mark.asyncio
async def test_spawn_from_parent_drops_invalid_mutants():
    """Mutants that fail validate_skill_structure are filtered out; elite always kept."""
    from skillforge.agents.spawner import spawn_from_parent

    parent = _make_seed_skill("parent-5")

    # Build one valid mutant and one obviously broken one
    valid_mutant = {
        "skill_md_content": (
            "---\n"
            "name: foo-skill-valid\n"
            "description: Valid mutant. Use when foo. NOT for bar.\n"
            "---\n\n"
            "# Valid\n\n"
            "## Workflow\n- step\n\n"
            "## Examples\n**Example 1:** x → y\n**Example 2:** a → b\n"
        ),
        "traits": ["x"],
        "meta_strategy": "valid",
        "mutations": [],
        "mutation_rationale": "",
    }
    broken_mutant = {
        # Missing frontmatter entirely → validator will reject
        "skill_md_content": "Just some prose, no frontmatter, no examples.",
        "traits": [],
        "meta_strategy": "",
        "mutations": [],
        "mutation_rationale": "",
    }

    response_text = json.dumps([valid_mutant, broken_mutant])

    with patch(
        "skillforge.agents.spawner._generate",
        new_callable=AsyncMock,
        return_value=response_text,
    ):
        result = await spawn_from_parent(parent, pop_size=3)

    # Elite + 1 valid mutant = 2; the broken one is filtered out
    assert len(result) == 2
    assert "elite-carry" in result[0].mutations
    assert result[1].skill_md_content.startswith("---\nname: foo-skill-valid")


# ---------------------------------------------------------------------------
# 5. POST /api/evolve/from-parent — registry happy path
# ---------------------------------------------------------------------------


def test_evolve_from_parent_registry_happy_path(client):
    """Registry fork resolves a real seed_id and stashes it in PENDING_PARENTS."""
    seed = _make_seed_skill("seed-registry-1", description="Use when test fork. NOT for prod.")
    seed_run = _make_seed_run([seed])

    with (
        patch(
            "skillforge.api.routes.get_run",
            new_callable=AsyncMock,
            return_value=seed_run,
        ),
        patch("skillforge.api.routes.init_db", new_callable=AsyncMock),
        patch("skillforge.api.routes.save_run", new_callable=AsyncMock),
        patch(
            "skillforge.api.routes.run_evolution", new_callable=AsyncMock
        ),
    ):
        resp = client.post(
            "/api/evolve/from-parent",
            json={
                "parent_source": "registry",
                "parent_id": "seed-registry-1",
                "population_size": 2,
                "num_generations": 1,
                "max_budget_usd": 1.0,
            },
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "run_id" in payload
    assert payload["ws_url"] == f"/ws/evolve/{payload['run_id']}"
    # Parent was stashed for the engine to pick up
    parent = _run_registry.take_parent(payload["run_id"])
    assert parent is not None
    assert parent.id == "seed-registry-1"
    # Restore so the autouse fixture's post-yield clear() stays idempotent
    _run_registry.stash_parent(payload["run_id"], parent)


# ---------------------------------------------------------------------------
# 6. POST /api/evolve/from-parent — registry 404 on unknown skill
# ---------------------------------------------------------------------------


def test_evolve_from_parent_registry_unknown_skill_returns_404(client):
    """Unknown registry skill_id → 404, not a 500."""
    seed_run = _make_seed_run([_make_seed_skill("known-id")])

    with (
        patch(
            "skillforge.api.routes.get_run",
            new_callable=AsyncMock,
            return_value=seed_run,
        ),
        patch("skillforge.api.routes.init_db", new_callable=AsyncMock),
        patch("skillforge.api.routes.save_run", new_callable=AsyncMock),
    ):
        resp = client.post(
            "/api/evolve/from-parent",
            json={
                "parent_source": "registry",
                "parent_id": "nonexistent-skill-id",
            },
        )

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


def test_evolve_from_parent_registry_no_seed_run_returns_404(client):
    """If get_run('seed-library') returns None, fork still 404s cleanly."""
    with (
        patch(
            "skillforge.api.routes.get_run",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("skillforge.api.routes.init_db", new_callable=AsyncMock),
        patch("skillforge.api.routes.save_run", new_callable=AsyncMock),
    ):
        resp = client.post(
            "/api/evolve/from-parent",
            json={
                "parent_source": "registry",
                "parent_id": "any-id",
            },
        )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 7. POST /api/evolve/from-parent — upload 404 + bad source
# ---------------------------------------------------------------------------


def test_evolve_from_parent_upload_unknown_id_returns_404(client):
    """Unknown upload_id → 404."""
    with (
        patch(
            "skillforge.api.routes.get_upload",
            return_value=None,
        ),
        patch("skillforge.api.routes.init_db", new_callable=AsyncMock),
        patch("skillforge.api.routes.save_run", new_callable=AsyncMock),
    ):
        resp = client.post(
            "/api/evolve/from-parent",
            json={
                "parent_source": "upload",
                "parent_id": "nope-not-a-real-upload",
            },
        )

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"] or "expired" in resp.json()["detail"]


def test_evolve_from_parent_bad_source_returns_400(client):
    """parent_source must be 'registry' or 'upload' — anything else is 400."""
    resp = client.post(
        "/api/evolve/from-parent",
        json={
            "parent_source": "telepathy",
            "parent_id": "x",
        },
    )

    assert resp.status_code == 400
    assert "parent_source" in resp.json()["detail"]
