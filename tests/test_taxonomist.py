"""Wave 2-1 tests — Taxonomist agent.

The LLM call is mocked via the ``generate_fn`` seam so tests stay hermetic
and deterministic. Tests cover:

- Happy path: classify into existing taxonomy, atomic decomposition with
  2+ dimensions, persist the family, return the structured output.
- Reuse: when the model reports an existing slug (reused=true), the
  function finds and attaches the existing node — it does NOT create a
  duplicate.
- New nodes: when the model proposes a new slug (reused=false), the
  function creates it and records the addition in created_new_nodes.
- Monolithic: a simple specialization with no independent dimensions
  gets decomposition_strategy="molecular" and an empty
  variant_dimensions list.
- JSON validation: malformed LLM output is caught before persistence.
- Atomic requires ≥ 2 dimensions: the validator rejects the half-built case.
- Retry path: a first-attempt bad response plus a second-attempt good
  response succeeds.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from skillforge.agents.taxonomist import (
    TaxonomistOutput,
    _extract_json_object,
    _validate_output_shape,
    classify_and_decompose,
)
from skillforge.db import (
    get_family_by_slug,
    get_taxonomy_node_by_slug,
    get_taxonomy_tree,
    init_db,
    save_taxonomy_node,
)
from skillforge.models import TaxonomyNode

# Most tests in this module are async; the JSON parser + validator unit tests
# are sync. We apply the asyncio marker per-test rather than module-wide so the
# sync tests don't emit "not an async function" warnings.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_generator(*responses: str):
    """Return an async mock that yields successive responses per call."""
    state = {"call": 0}

    async def _gen(_prompt: str) -> str:
        idx = state["call"]
        state["call"] += 1
        if idx >= len(responses):
            raise RuntimeError(f"generator called {idx + 1} times, only {len(responses)} responses seeded")
        return responses[idx]

    return _gen


def _canned_atomic_response(
    *,
    domain_slug: str = "testing",
    domain_label: str = "Testing",
    domain_reused: bool = True,
    focus_slug: str = "unit-tests",
    focus_label: str = "Unit Tests",
    focus_reused: bool = True,
    language_slug: str = "python",
    language_label: str = "Python",
    language_reused: bool = True,
    family_slug: str = "django-rest-pytest",
    family_label: str = "Django REST Pytest",
) -> str:
    return json.dumps(
        {
            "classification": {
                "domain": {
                    "slug": domain_slug,
                    "label": domain_label,
                    "reused": domain_reused,
                    "justification": "ok",
                },
                "focus": {
                    "slug": focus_slug,
                    "label": focus_label,
                    "reused": focus_reused,
                    "justification": "ok",
                },
                "language": {
                    "slug": language_slug,
                    "label": language_label,
                    "reused": language_reused,
                    "justification": "ok",
                },
            },
            "family": {
                "slug": family_slug,
                "label": family_label,
                "decomposition_strategy": "atomic",
                "tags": ["python", "testing"],
            },
            "variant_dimensions": [
                {
                    "name": "fixture-strategy",
                    "tier": "foundation",
                    "description": "how test fixtures are organized",
                    "evaluation_focus": "reusability",
                },
                {
                    "name": "mock-strategy",
                    "tier": "capability",
                    "description": "how external deps are isolated",
                    "evaluation_focus": "isolation",
                },
            ],
            "reuse_recommendations": [],
            "justification": "Two independent dimensions → atomic.",
        }
    )


def _canned_molecular_response(
    family_slug: str = "csv-dataclass",
    family_label: str = "CSV to Dataclass",
) -> str:
    return json.dumps(
        {
            "classification": {
                "domain": {"slug": "data", "label": "Data", "reused": True, "justification": "ok"},
                "focus": {"slug": "parsing", "label": "Parsing", "reused": False, "justification": "new focus"},
                "language": {"slug": "python", "label": "Python", "reused": True, "justification": "ok"},
            },
            "family": {
                "slug": family_slug,
                "label": family_label,
                "decomposition_strategy": "molecular",
                "tags": [],
            },
            "variant_dimensions": [],
            "reuse_recommendations": [],
            "justification": "One tight module — no independent dimensions.",
        }
    )


# ---------------------------------------------------------------------------
# JSON parser unit tests
# ---------------------------------------------------------------------------


def test_extract_json_object_raw():
    text = '{"a": 1, "b": "two"}'
    assert _extract_json_object(text) == {"a": 1, "b": "two"}


def test_extract_json_object_fenced():
    text = "Here is the output:\n```json\n{\"x\": 42}\n```\n"
    assert _extract_json_object(text) == {"x": 42}


def test_extract_json_object_embedded_prose():
    text = 'Sure! The classification is {"ok": true} — that works.'
    assert _extract_json_object(text) == {"ok": True}


def test_extract_json_object_missing_raises():
    with pytest.raises(ValueError, match="no JSON object"):
        _extract_json_object("no json here")


# ---------------------------------------------------------------------------
# Shape validator unit tests
# ---------------------------------------------------------------------------


def test_validate_output_shape_happy_atomic():
    raw = json.loads(_canned_atomic_response())
    _validate_output_shape(raw)  # no exception


def test_validate_output_shape_happy_molecular():
    raw = json.loads(_canned_molecular_response())
    _validate_output_shape(raw)


def test_validate_output_shape_rejects_atomic_with_one_dim():
    raw = json.loads(_canned_atomic_response())
    raw["variant_dimensions"] = raw["variant_dimensions"][:1]
    with pytest.raises(ValueError, match="at least 2"):
        _validate_output_shape(raw)


def test_validate_output_shape_rejects_molecular_with_dims():
    raw = json.loads(_canned_molecular_response())
    raw["variant_dimensions"] = [
        {
            "name": "d1",
            "tier": "foundation",
            "description": "x",
            "evaluation_focus": "y",
        }
    ]
    with pytest.raises(ValueError, match="molecular"):
        _validate_output_shape(raw)


def test_validate_output_shape_rejects_bad_slug():
    raw = json.loads(_canned_atomic_response())
    raw["classification"]["domain"]["slug"] = "NotKebabCase"
    with pytest.raises(ValueError, match="kebab-case"):
        _validate_output_shape(raw)


def test_validate_output_shape_rejects_bad_tier():
    raw = json.loads(_canned_atomic_response())
    raw["variant_dimensions"][0]["tier"] = "invalid"
    with pytest.raises(ValueError, match="foundation"):
        _validate_output_shape(raw)


# ---------------------------------------------------------------------------
# classify_and_decompose — full integration with a mocked generator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_atomic_with_existing_taxonomy(temp_db_path):
    await init_db(temp_db_path)

    # Seed the taxonomy with the nodes the LLM will claim it's reusing
    await save_taxonomy_node(
        TaxonomyNode(
            id="dom_t", level="domain", slug="testing", label="Testing"
        ),
        temp_db_path,
    )
    await save_taxonomy_node(
        TaxonomyNode(
            id="foc_u",
            level="focus",
            slug="unit-tests",
            label="Unit Tests",
            parent_id="dom_t",
        ),
        temp_db_path,
    )
    await save_taxonomy_node(
        TaxonomyNode(
            id="lang_py",
            level="language",
            slug="python",
            label="Python",
            parent_id="foc_u",
        ),
        temp_db_path,
    )

    # Feed the cached tree to the agent
    taxonomy = await get_taxonomy_tree(temp_db_path)

    # Monkeypatch the DB helpers used inside taxonomist.py to target temp_db_path.
    # Since classify_and_decompose calls save_taxonomy_node / save_skill_family
    # / get_taxonomy_node_by_slug without a db_path argument, we override them
    # to always use temp_db_path for the duration of this test.
    from skillforge.agents import taxonomist as tx

    orig_ensure = tx._ensure_node
    orig_save_family = tx.save_skill_family

    async def _ensure_node_local(level, slug, label, parent_id, created):
        from skillforge.db.queries import (
            get_taxonomy_node_by_slug as _g,
        )
        from skillforge.db.queries import (
            save_taxonomy_node as _s,
        )
        existing = await _g(level, slug, parent_id, temp_db_path)
        if existing is not None:
            return existing
        import uuid as _uuid

        node = TaxonomyNode(
            id=f"tax_{_uuid.uuid4().hex[:12]}",
            level=level,
            slug=slug,
            label=label,
            parent_id=parent_id,
            description="",
            created_at=datetime.now(UTC),
        )
        await _s(node, temp_db_path)
        created.append(f"{level}:{slug}")
        return node

    async def _save_family_local(family, db_path=None):
        await orig_save_family(family, temp_db_path)

    tx._ensure_node = _ensure_node_local
    tx.save_skill_family = _save_family_local

    try:
        generator = _make_generator(_canned_atomic_response())
        result = await classify_and_decompose(
            specialization="Generate pytest unit tests for Django REST views",
            taxonomy_tree=taxonomy,
            existing_families=[],
            generate_fn=generator,
        )
    finally:
        tx._ensure_node = orig_ensure
        tx.save_skill_family = orig_save_family

    assert isinstance(result, TaxonomistOutput)
    assert result.evolution_mode == "atomic"
    assert len(result.variant_dimensions) == 2
    assert result.variant_dimensions[0].name == "fixture-strategy"
    assert result.variant_dimensions[0].tier == "foundation"
    assert result.variant_dimensions[1].tier == "capability"

    # No new nodes should have been created
    assert result.created_new_nodes == []
    assert result.domain.id == "dom_t"
    assert result.focus.id == "foc_u"
    assert result.language.id == "lang_py"

    # The family should be persisted
    fam = await get_family_by_slug("django-rest-pytest", temp_db_path)
    assert fam is not None
    assert fam.decomposition_strategy == "atomic"
    assert fam.tags == ["python", "testing"]


@pytest.mark.asyncio
async def test_classify_molecular_creates_new_focus(temp_db_path):
    await init_db(temp_db_path)
    # Start with only an existing "data" domain; focus will be created new
    await save_taxonomy_node(
        TaxonomyNode(id="dom_d", level="domain", slug="data", label="Data"),
        temp_db_path,
    )
    taxonomy = await get_taxonomy_tree(temp_db_path)

    from skillforge.agents import taxonomist as tx

    orig_ensure = tx._ensure_node
    orig_save_family = tx.save_skill_family

    async def _ensure_node_local(level, slug, label, parent_id, created):
        from skillforge.db.queries import (
            get_taxonomy_node_by_slug as _g,
        )
        from skillforge.db.queries import (
            save_taxonomy_node as _s,
        )
        existing = await _g(level, slug, parent_id, temp_db_path)
        if existing is not None:
            return existing
        import uuid as _uuid

        node = TaxonomyNode(
            id=f"tax_{_uuid.uuid4().hex[:12]}",
            level=level,
            slug=slug,
            label=label,
            parent_id=parent_id,
            description="",
            created_at=datetime.now(UTC),
        )
        await _s(node, temp_db_path)
        created.append(f"{level}:{slug}")
        return node

    async def _save_family_local(family, db_path=None):
        await orig_save_family(family, temp_db_path)

    tx._ensure_node = _ensure_node_local
    tx.save_skill_family = _save_family_local

    try:
        generator = _make_generator(_canned_molecular_response())
        result = await classify_and_decompose(
            specialization="Parse CSV files into typed Python dataclasses",
            taxonomy_tree=taxonomy,
            existing_families=[],
            generate_fn=generator,
        )
    finally:
        tx._ensure_node = orig_ensure
        tx.save_skill_family = orig_save_family

    assert result.evolution_mode == "molecular"
    assert result.variant_dimensions == []
    # New focus `parsing` and new language `python` should have been created
    assert "focus:parsing" in result.created_new_nodes
    assert "language:python" in result.created_new_nodes
    # Domain was reused
    assert result.domain.id == "dom_d"

    # Verify the new focus lives under the existing domain
    new_focus = await get_taxonomy_node_by_slug(
        "focus", "parsing", "dom_d", temp_db_path
    )
    assert new_focus is not None

    # Verify the family exists
    fam = await get_family_by_slug("csv-dataclass", temp_db_path)
    assert fam is not None
    assert fam.decomposition_strategy == "molecular"


@pytest.mark.asyncio
async def test_classify_retries_on_bad_first_response(temp_db_path):
    await init_db(temp_db_path)
    await save_taxonomy_node(
        TaxonomyNode(id="dom_t", level="domain", slug="testing", label="Testing"),
        temp_db_path,
    )
    taxonomy = await get_taxonomy_tree(temp_db_path)

    from skillforge.agents import taxonomist as tx

    orig_ensure = tx._ensure_node
    orig_save_family = tx.save_skill_family

    async def _ensure_node_local(level, slug, label, parent_id, created):
        from skillforge.db.queries import (
            get_taxonomy_node_by_slug as _g,
        )
        from skillforge.db.queries import (
            save_taxonomy_node as _s,
        )
        existing = await _g(level, slug, parent_id, temp_db_path)
        if existing is not None:
            return existing
        import uuid as _uuid

        node = TaxonomyNode(
            id=f"tax_{_uuid.uuid4().hex[:12]}",
            level=level,
            slug=slug,
            label=label,
            parent_id=parent_id,
            description="",
            created_at=datetime.now(UTC),
        )
        await _s(node, temp_db_path)
        created.append(f"{level}:{slug}")
        return node

    async def _save_family_local(family, db_path=None):
        await orig_save_family(family, temp_db_path)

    tx._ensure_node = _ensure_node_local
    tx.save_skill_family = _save_family_local

    try:
        generator = _make_generator(
            "not valid json at all",  # first attempt
            _canned_atomic_response(family_slug="retry-family", family_label="Retry"),  # second attempt
        )
        result = await classify_and_decompose(
            specialization="test retry behavior",
            taxonomy_tree=taxonomy,
            existing_families=[],
            generate_fn=generator,
        )
    finally:
        tx._ensure_node = orig_ensure
        tx.save_skill_family = orig_save_family

    assert result.family.slug == "retry-family"
    assert result.evolution_mode == "atomic"


@pytest.mark.asyncio
async def test_classify_rejects_atomic_without_enough_dimensions(temp_db_path):
    await init_db(temp_db_path)
    await save_taxonomy_node(
        TaxonomyNode(id="dom_t", level="domain", slug="testing", label="Testing"),
        temp_db_path,
    )
    taxonomy = await get_taxonomy_tree(temp_db_path)

    bad_atomic = json.loads(_canned_atomic_response())
    bad_atomic["variant_dimensions"] = bad_atomic["variant_dimensions"][:1]
    generator = _make_generator(
        json.dumps(bad_atomic),
        json.dumps(bad_atomic),  # retry also returns bad
    )

    with pytest.raises(ValueError, match="at least 2"):
        await classify_and_decompose(
            specialization="bad atomic",
            taxonomy_tree=taxonomy,
            existing_families=[],
            generate_fn=generator,
        )
