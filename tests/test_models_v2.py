"""Wave 1-1 serialization round-trip tests for new v2.0 dataclasses.

Covers TaxonomyNode, SkillFamily, Variant, VariantEvolution, plus the new
fields added to SkillGenome (variant_id) and EvolutionRun (family_id,
evolution_mode).
"""

from __future__ import annotations

from datetime import UTC, datetime

from skillforge.models import (
    EvolutionRun,
    SkillFamily,
    SkillGenome,
    TaxonomyNode,
    Variant,
    VariantEvolution,
)

# ---------------------------------------------------------------------------
# TaxonomyNode
# ---------------------------------------------------------------------------


def test_taxonomy_node_roundtrip_minimal() -> None:
    node = TaxonomyNode(
        id="dom_testing",
        level="domain",
        slug="testing",
        label="Testing",
    )
    data = node.to_dict()
    assert data["id"] == "dom_testing"
    assert data["level"] == "domain"
    assert data["parent_id"] is None
    assert data["description"] == ""
    assert isinstance(data["created_at"], str)

    restored = TaxonomyNode.from_dict(data)
    assert restored.id == node.id
    assert restored.level == node.level
    assert restored.slug == node.slug
    assert restored.parent_id is None


def test_taxonomy_node_roundtrip_with_parent() -> None:
    node = TaxonomyNode(
        id="focus_unit",
        level="focus",
        slug="unit-tests",
        label="Unit Tests",
        parent_id="dom_testing",
        description="Focused unit-level tests",
        created_at=datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
    )
    restored = TaxonomyNode.from_dict(node.to_dict())
    assert restored == node


# ---------------------------------------------------------------------------
# SkillFamily
# ---------------------------------------------------------------------------


def test_skill_family_roundtrip_defaults() -> None:
    fam = SkillFamily(
        id="fam_abc",
        slug="django-rest-pytest",
        label="Django REST Pytest",
        specialization="Pytest tests for DRF views",
    )
    data = fam.to_dict()
    assert data["tags"] == []
    assert data["decomposition_strategy"] == "molecular"
    assert data["best_assembly_id"] is None

    restored = SkillFamily.from_dict(data)
    assert restored.id == fam.id
    assert restored.slug == fam.slug
    assert restored.decomposition_strategy == "molecular"


def test_skill_family_roundtrip_populated() -> None:
    fam = SkillFamily(
        id="fam_xyz",
        slug="pytest-generator",
        label="Pytest Generator",
        specialization="Generate pytest tests",
        domain_id="dom_testing",
        focus_id="focus_unit",
        language_id="lang_python",
        tags=["python", "testing", "pytest"],
        decomposition_strategy="atomic",
        best_assembly_id="skill_123",
        created_at=datetime(2026, 4, 10, 15, 30, tzinfo=UTC),
    )
    restored = SkillFamily.from_dict(fam.to_dict())
    assert restored == fam


# ---------------------------------------------------------------------------
# Variant
# ---------------------------------------------------------------------------


def test_variant_roundtrip() -> None:
    v = Variant(
        id="var_001",
        family_id="fam_xyz",
        dimension="mock-strategy",
        tier="capability",
        genome_id="skill_abc",
        fitness_score=0.81,
        is_active=True,
        evolution_id="vevo_001",
    )
    restored = Variant.from_dict(v.to_dict())
    assert restored.id == v.id
    assert restored.dimension == "mock-strategy"
    assert restored.tier == "capability"
    assert restored.is_active is True
    assert restored.fitness_score == 0.81


# ---------------------------------------------------------------------------
# VariantEvolution
# ---------------------------------------------------------------------------


def test_variant_evolution_roundtrip_pending() -> None:
    ve = VariantEvolution(
        id="vevo_001",
        family_id="fam_xyz",
        dimension="mock-strategy",
        tier="capability",
        parent_run_id="run_parent",
    )
    data = ve.to_dict()
    assert data["population_size"] == 2
    assert data["num_generations"] == 2
    assert data["status"] == "pending"
    assert data["completed_at"] is None

    restored = VariantEvolution.from_dict(data)
    assert restored.id == ve.id
    assert restored.status == "pending"


def test_variant_evolution_roundtrip_complete() -> None:
    ve = VariantEvolution(
        id="vevo_002",
        family_id="fam_xyz",
        dimension="fixture-strategy",
        tier="foundation",
        parent_run_id="run_parent",
        population_size=3,
        num_generations=4,
        status="complete",
        winner_variant_id="var_winner",
        foundation_genome_id=None,
        challenge_id="chal_001",
        created_at=datetime(2026, 4, 10, 10, 0, tzinfo=UTC),
        completed_at=datetime(2026, 4, 10, 10, 12, tzinfo=UTC),
    )
    restored = VariantEvolution.from_dict(ve.to_dict())
    assert restored == ve


# ---------------------------------------------------------------------------
# SkillGenome — new v2.0 field
# ---------------------------------------------------------------------------


def test_skill_genome_variant_id_default_none() -> None:
    g = SkillGenome(id="s1", generation=0, skill_md_content="# hi")
    assert g.variant_id is None
    assert g.to_dict()["variant_id"] is None


def test_skill_genome_variant_id_roundtrip() -> None:
    g = SkillGenome(
        id="s1",
        generation=0,
        skill_md_content="# hi",
        variant_id="var_42",
    )
    restored = SkillGenome.from_dict(g.to_dict())
    assert restored.variant_id == "var_42"


def test_skill_genome_backward_compatible_load() -> None:
    """Loading a pre-v2.0 dict (no variant_id) should still work."""
    legacy_data = {
        "id": "s1",
        "generation": 0,
        "skill_md_content": "# hi",
    }
    restored = SkillGenome.from_dict(legacy_data)
    assert restored.variant_id is None


# ---------------------------------------------------------------------------
# EvolutionRun — new v2.0 fields
# ---------------------------------------------------------------------------


def test_evolution_run_v2_fields_defaults() -> None:
    run = EvolutionRun(id="run_1", mode="domain", specialization="foo")
    assert run.family_id is None
    assert run.evolution_mode == "molecular"
    data = run.to_dict()
    assert data["family_id"] is None
    assert data["evolution_mode"] == "molecular"


def test_evolution_run_v2_atomic_roundtrip() -> None:
    run = EvolutionRun(
        id="run_2",
        mode="domain",
        specialization="django pytest",
        family_id="fam_xyz",
        evolution_mode="atomic",
    )
    restored = EvolutionRun.from_dict(run.to_dict())
    assert restored.family_id == "fam_xyz"
    assert restored.evolution_mode == "atomic"


def test_evolution_run_backward_compatible_load() -> None:
    """Pre-v2.0 persisted runs (no family_id / evolution_mode) still rehydrate."""
    legacy = {
        "id": "run_legacy",
        "mode": "domain",
        "specialization": "legacy skill",
    }
    restored = EvolutionRun.from_dict(legacy)
    assert restored.family_id is None
    assert restored.evolution_mode == "molecular"
