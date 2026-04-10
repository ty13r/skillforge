"""Wave 1-3 tests — taxonomy CRUD, family CRUD, variant CRUD, and the
``load_taxonomy`` bootstrap loader.

Every test starts with an isolated ``temp_db_path`` so no run touches the
real database. The bootstrap loader is exercised end-to-end against the real
``SEED_SKILLS`` module so the hardcoded classification table stays honest.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from skillforge.db import (
    get_active_variants,
    get_family,
    get_family_by_slug,
    get_taxonomy_node,
    get_taxonomy_node_by_slug,
    get_taxonomy_tree,
    get_variant_evolution,
    get_variant_evolutions_for_run,
    get_variants_for_family,
    init_db,
    list_families,
    save_genome,
    save_run,
    save_skill_family,
    save_taxonomy_node,
    save_variant,
    save_variant_evolution,
)
from skillforge.db.taxonomy_seeds import (
    _SEED_CLASSIFICATIONS,
    load_taxonomy,
)
from skillforge.models import (
    EvolutionRun,
    SkillFamily,
    SkillGenome,
    TaxonomyNode,
    Variant,
    VariantEvolution,
)
from skillforge.seeds import SEED_SKILLS

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def _make_genome(gid: str = "g1", run_id: str = "r1") -> SkillGenome:
    return SkillGenome(
        id=gid,
        generation=0,
        skill_md_content="# Test\n",
        frontmatter={"name": "test"},
        supporting_files={},
        traits=[],
    )


def _make_run(rid: str = "r1") -> EvolutionRun:
    return EvolutionRun(
        id=rid,
        mode="domain",
        specialization="test",
        population_size=2,
        num_generations=2,
    )


# ---------------------------------------------------------------------------
# TaxonomyNode CRUD
# ---------------------------------------------------------------------------


async def test_save_and_get_taxonomy_node(temp_db_path):
    await init_db(temp_db_path)
    node = TaxonomyNode(
        id="dom_1",
        level="domain",
        slug="testing",
        label="Testing",
    )
    await save_taxonomy_node(node, temp_db_path)

    fetched = await get_taxonomy_node("dom_1", temp_db_path)
    assert fetched is not None
    assert fetched.id == "dom_1"
    assert fetched.level == "domain"
    assert fetched.slug == "testing"
    assert fetched.parent_id is None


async def test_save_taxonomy_node_is_idempotent_on_id(temp_db_path):
    """Saving twice with the same id must update, not duplicate."""
    await init_db(temp_db_path)
    n1 = TaxonomyNode(id="x1", level="domain", slug="t", label="First")
    await save_taxonomy_node(n1, temp_db_path)

    n1b = TaxonomyNode(id="x1", level="domain", slug="t", label="Second")
    await save_taxonomy_node(n1b, temp_db_path)

    fetched = await get_taxonomy_node("x1", temp_db_path)
    assert fetched is not None
    assert fetched.label == "Second"


async def test_get_taxonomy_node_by_slug_with_null_parent(temp_db_path):
    """Root rows (parent_id=NULL) must be lookup-able by natural key."""
    await init_db(temp_db_path)
    await save_taxonomy_node(
        TaxonomyNode(id="dom_s", level="domain", slug="security", label="Security"),
        temp_db_path,
    )
    found = await get_taxonomy_node_by_slug("domain", "security", None, temp_db_path)
    assert found is not None
    assert found.id == "dom_s"

    missing = await get_taxonomy_node_by_slug("domain", "nope", None, temp_db_path)
    assert missing is None


async def test_get_taxonomy_node_by_slug_with_parent(temp_db_path):
    await init_db(temp_db_path)
    await save_taxonomy_node(
        TaxonomyNode(id="dom_t", level="domain", slug="testing", label="Testing"),
        temp_db_path,
    )
    await save_taxonomy_node(
        TaxonomyNode(
            id="foc_u",
            level="focus",
            slug="unit-tests",
            label="Unit",
            parent_id="dom_t",
        ),
        temp_db_path,
    )
    found = await get_taxonomy_node_by_slug(
        "focus", "unit-tests", "dom_t", temp_db_path
    )
    assert found is not None
    assert found.id == "foc_u"
    # Same slug under a different (non-existent) parent → None
    not_found = await get_taxonomy_node_by_slug(
        "focus", "unit-tests", "dom_other", temp_db_path
    )
    assert not_found is None


async def test_get_taxonomy_tree_returns_all_nodes_ordered(temp_db_path):
    """FK constraints require insert in dependency order, but the tree
    getter must still return rows ordered by level regardless of insert
    sequence. We rely on sort-by-level in the query layer."""
    await init_db(temp_db_path)
    await save_taxonomy_node(
        TaxonomyNode(id="dom_t", level="domain", slug="testing", label="Testing"),
        temp_db_path,
    )
    await save_taxonomy_node(
        TaxonomyNode(id="foc_u", level="focus", slug="unit-tests", label="Unit", parent_id="dom_t"),
        temp_db_path,
    )
    await save_taxonomy_node(
        TaxonomyNode(id="lang_py", level="language", slug="python", label="Python", parent_id="foc_u"),
        temp_db_path,
    )

    tree = await get_taxonomy_tree(temp_db_path)
    # Expect domain → focus → language ordering
    assert [n.level for n in tree] == ["domain", "focus", "language"]
    assert [n.slug for n in tree] == ["testing", "unit-tests", "python"]


# ---------------------------------------------------------------------------
# SkillFamily CRUD
# ---------------------------------------------------------------------------


async def test_save_and_get_skill_family(temp_db_path):
    await init_db(temp_db_path)
    fam = SkillFamily(
        id="fam_1",
        slug="pytest-gen",
        label="Pytest Gen",
        specialization="generate pytest tests",
        tags=["python", "testing"],
        decomposition_strategy="atomic",
    )
    await save_skill_family(fam, temp_db_path)

    by_id = await get_family("fam_1", temp_db_path)
    assert by_id is not None
    assert by_id.slug == "pytest-gen"
    assert by_id.tags == ["python", "testing"]
    assert by_id.decomposition_strategy == "atomic"

    by_slug = await get_family_by_slug("pytest-gen", temp_db_path)
    assert by_slug is not None
    assert by_slug.id == "fam_1"


async def test_list_families_filters_by_taxonomy(temp_db_path):
    await init_db(temp_db_path)
    # Taxonomy nodes required for the FKs
    await save_taxonomy_node(
        TaxonomyNode(id="dom_t", level="domain", slug="testing", label="Testing"),
        temp_db_path,
    )
    await save_taxonomy_node(
        TaxonomyNode(id="dom_d", level="domain", slug="devops", label="DevOps"),
        temp_db_path,
    )
    await save_skill_family(
        SkillFamily(
            id="fam_t",
            slug="f-test",
            label="Test Fam",
            specialization="x",
            domain_id="dom_t",
        ),
        temp_db_path,
    )
    await save_skill_family(
        SkillFamily(
            id="fam_d",
            slug="f-dev",
            label="Dev Fam",
            specialization="y",
            domain_id="dom_d",
        ),
        temp_db_path,
    )

    all_fams = await list_families(db_path=temp_db_path)
    assert len(all_fams) == 2

    test_only = await list_families(db_path=temp_db_path, domain_id="dom_t")
    assert len(test_only) == 1
    assert test_only[0].id == "fam_t"

    dev_only = await list_families(db_path=temp_db_path, domain_id="dom_d")
    assert len(dev_only) == 1
    assert dev_only[0].id == "fam_d"


# ---------------------------------------------------------------------------
# Variant + VariantEvolution CRUD
# ---------------------------------------------------------------------------


async def test_save_variant_and_list_for_family(temp_db_path):
    await init_db(temp_db_path)
    # Prereqs: run + family + genome
    await save_run(_make_run("r1"), temp_db_path)
    await save_skill_family(
        SkillFamily(id="fam_1", slug="f1", label="F1", specialization="x"),
        temp_db_path,
    )
    await save_genome(_make_genome("g1", "r1"), "r1", temp_db_path)
    await save_genome(_make_genome("g2", "r1"), "r1", temp_db_path)

    v1 = Variant(
        id="v1",
        family_id="fam_1",
        dimension="mock-strategy",
        tier="capability",
        genome_id="g1",
        fitness_score=0.81,
        is_active=True,
    )
    v2 = Variant(
        id="v2",
        family_id="fam_1",
        dimension="fixture-strategy",
        tier="foundation",
        genome_id="g2",
        fitness_score=0.64,
        is_active=False,
    )
    await save_variant(v1, temp_db_path)
    await save_variant(v2, temp_db_path)

    all_in_fam = await get_variants_for_family("fam_1", db_path=temp_db_path)
    assert len(all_in_fam) == 2
    # Ordered by fitness DESC
    assert all_in_fam[0].id == "v1"
    assert all_in_fam[1].id == "v2"

    # Filter by dimension
    caps = await get_variants_for_family(
        "fam_1", dimension="mock-strategy", db_path=temp_db_path
    )
    assert len(caps) == 1
    assert caps[0].id == "v1"

    # Filter by tier
    foundations = await get_variants_for_family(
        "fam_1", tier="foundation", db_path=temp_db_path
    )
    assert len(foundations) == 1
    assert foundations[0].id == "v2"


async def test_get_active_variants_only_returns_is_active(temp_db_path):
    await init_db(temp_db_path)
    await save_run(_make_run("r1"), temp_db_path)
    await save_skill_family(
        SkillFamily(id="fam_1", slug="f1", label="F1", specialization="x"),
        temp_db_path,
    )
    await save_genome(_make_genome("g1", "r1"), "r1", temp_db_path)
    await save_genome(_make_genome("g2", "r1"), "r1", temp_db_path)
    await save_genome(_make_genome("g3", "r1"), "r1", temp_db_path)

    await save_variant(
        Variant(
            id="va",
            family_id="fam_1",
            dimension="d1",
            tier="foundation",
            genome_id="g1",
            is_active=True,
        ),
        temp_db_path,
    )
    await save_variant(
        Variant(
            id="vb",
            family_id="fam_1",
            dimension="d2",
            tier="capability",
            genome_id="g2",
            is_active=True,
        ),
        temp_db_path,
    )
    await save_variant(
        Variant(
            id="vc",
            family_id="fam_1",
            dimension="d3",
            tier="capability",
            genome_id="g3",
            is_active=False,
        ),
        temp_db_path,
    )

    active = await get_active_variants("fam_1", temp_db_path)
    assert len(active) == 2
    # Foundation comes first per tier ordering
    assert active[0].tier == "foundation"
    assert active[0].id == "va"
    assert active[1].tier == "capability"


async def test_variant_evolution_roundtrip_and_list_by_run(temp_db_path):
    await init_db(temp_db_path)
    await save_run(_make_run("run_parent"), temp_db_path)
    await save_skill_family(
        SkillFamily(id="fam_1", slug="f1", label="F1", specialization="x"),
        temp_db_path,
    )

    ve1 = VariantEvolution(
        id="vevo_1",
        family_id="fam_1",
        dimension="mock-strategy",
        tier="capability",
        parent_run_id="run_parent",
    )
    ve2 = VariantEvolution(
        id="vevo_2",
        family_id="fam_1",
        dimension="fixture-strategy",
        tier="foundation",
        parent_run_id="run_parent",
        status="complete",
        completed_at=_now(),
    )
    await save_variant_evolution(ve1, temp_db_path)
    await save_variant_evolution(ve2, temp_db_path)

    fetched = await get_variant_evolution("vevo_1", temp_db_path)
    assert fetched is not None
    assert fetched.status == "pending"
    assert fetched.completed_at is None

    for_run = await get_variant_evolutions_for_run("run_parent", temp_db_path)
    assert len(for_run) == 2
    # Ordered by created_at ASC so ve1 comes first
    assert for_run[0].id == "vevo_1"


# ---------------------------------------------------------------------------
# load_taxonomy() — bootstrap against the real SEED_SKILLS module
# ---------------------------------------------------------------------------


async def test_load_taxonomy_bootstraps_nodes_and_families(temp_db_path):
    """Run the full bootstrap once and verify every seed lands in a family."""
    await init_db(temp_db_path)
    diagnostic = await load_taxonomy(temp_db_path)

    assert diagnostic["families_created"] == len(SEED_SKILLS)
    assert diagnostic["families_reused"] == 0
    assert diagnostic["nodes_total"] > 0

    tree = await get_taxonomy_tree(temp_db_path)
    levels = {n.level for n in tree}
    assert levels == {"domain", "focus", "language"}

    # Every classified seed should yield a family matching its slug
    for seed in SEED_SKILLS:
        classification = _SEED_CLASSIFICATIONS.get(seed["id"])
        if classification is None:
            continue
        family_slug = classification[3]
        fam = await get_family_by_slug(family_slug, temp_db_path)
        assert fam is not None, f"missing family for seed {seed['id']}"
        assert fam.domain_id is not None
        assert fam.focus_id is not None
        assert fam.language_id is not None


async def test_load_taxonomy_is_idempotent(temp_db_path):
    """Running the loader twice must not duplicate nodes or families."""
    await init_db(temp_db_path)
    first = await load_taxonomy(temp_db_path)
    second = await load_taxonomy(temp_db_path)

    assert first["families_created"] > 0
    assert second["families_created"] == 0
    assert second["families_reused"] == first["families_created"]
    assert second["nodes_total"] == first["nodes_total"]

    # Re-running must not increase the node or family counts
    tree = await get_taxonomy_tree(temp_db_path)
    fams = await list_families(db_path=temp_db_path)
    assert len(tree) == first["nodes_total"]
    assert len(fams) == first["families_created"]


async def test_load_taxonomy_is_additive_when_new_node_missing(temp_db_path):
    """If a partially-populated taxonomy is missing one seed's family,
    running the loader must fill that gap without touching existing rows."""
    await init_db(temp_db_path)

    # Seed the full taxonomy
    await load_taxonomy(temp_db_path)
    all_fams_before = await list_families(db_path=temp_db_path)

    # Manually delete one family row to simulate a missing entry
    from skillforge.db.database import get_connection

    conn = await get_connection(temp_db_path)
    try:
        await conn.execute(
            "DELETE FROM skill_families WHERE slug = ?", ("regex-builder",)
        )
        await conn.commit()
    finally:
        await conn.close()

    fams_after_delete = await list_families(db_path=temp_db_path)
    assert len(fams_after_delete) == len(all_fams_before) - 1

    # Re-run loader — it should recreate only the missing row
    second = await load_taxonomy(temp_db_path)
    assert second["families_created"] == 1
    assert second["families_reused"] == len(all_fams_before) - 1

    fams_after_reload = await list_families(db_path=temp_db_path)
    assert len(fams_after_reload) == len(all_fams_before)
    regex = await get_family_by_slug("regex-builder", temp_db_path)
    assert regex is not None
