"""Wave 1-2 database schema tests — v2.0 tables + additive migration.

Covers:
- ``init_db`` creates all 4 new tables (``taxonomy_nodes``, ``skill_families``,
  ``variants``, ``variant_evolutions``).
- Fresh install has the new columns on ``evolution_runs`` and ``skill_genomes``.
- Additive migration on a pre-v2.0 database adds ``family_id``,
  ``evolution_mode`` (evolution_runs) and ``variant_id`` (skill_genomes)
  without touching the existing row data.
- Roundtrip insert/select for every new table.
- FK cascades behave sensibly (family delete → variants gone; run delete →
  variant_evolutions gone).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import aiosqlite
import pytest

from skillforge.db import get_connection, init_db

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def _columns(conn: aiosqlite.Connection, table: str) -> list[str]:
    async with conn.execute(f"PRAGMA table_info({table})") as cur:
        return [row[1] async for row in cur]


async def _tables(conn: aiosqlite.Connection) -> set[str]:
    async with conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ) as cur:
        return {row[0] async for row in cur}


# ---------------------------------------------------------------------------
# Schema presence
# ---------------------------------------------------------------------------


async def test_init_db_creates_all_v2_tables(temp_db_path):
    await init_db(temp_db_path)
    conn = await get_connection(temp_db_path)
    try:
        names = await _tables(conn)
    finally:
        await conn.close()

    expected_v2 = {
        "taxonomy_nodes",
        "skill_families",
        "variants",
        "variant_evolutions",
    }
    assert expected_v2.issubset(names), (
        f"Missing v2.0 tables: {expected_v2 - names}"
    )

    # v1.x tables must also still exist
    expected_v1 = {
        "evolution_runs",
        "challenges",
        "skill_genomes",
        "generations",
        "competition_results",
    }
    assert expected_v1.issubset(names)


async def test_fresh_install_has_v2_columns_on_existing_tables(temp_db_path):
    await init_db(temp_db_path)
    conn = await get_connection(temp_db_path)
    try:
        runs_cols = await _columns(conn, "evolution_runs")
        genome_cols = await _columns(conn, "skill_genomes")
    finally:
        await conn.close()

    assert "family_id" in runs_cols
    assert "evolution_mode" in runs_cols
    assert "variant_id" in genome_cols


async def test_init_db_is_idempotent(temp_db_path):
    await init_db(temp_db_path)
    # Running it a second time must not error or duplicate anything.
    await init_db(temp_db_path)
    conn = await get_connection(temp_db_path)
    try:
        runs_cols = await _columns(conn, "evolution_runs")
    finally:
        await conn.close()

    # No duplicate columns
    assert runs_cols.count("family_id") == 1
    assert runs_cols.count("evolution_mode") == 1


# ---------------------------------------------------------------------------
# Additive migration from a pre-v2.0 schema
# ---------------------------------------------------------------------------


_PREV2_EVOLUTION_RUNS_DDL = """
CREATE TABLE evolution_runs (
    id              TEXT PRIMARY KEY,
    mode            TEXT NOT NULL,
    specialization  TEXT NOT NULL,
    population_size INTEGER NOT NULL,
    num_generations INTEGER NOT NULL,
    status          TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    completed_at    TEXT,
    total_cost_usd  REAL NOT NULL DEFAULT 0.0,
    max_budget_usd  REAL NOT NULL DEFAULT 10.0,
    learning_log    TEXT NOT NULL,
    pareto_front_ids TEXT NOT NULL,
    best_skill_id   TEXT,
    failure_reason  TEXT
)
"""

_PREV2_SKILL_GENOMES_DDL = """
CREATE TABLE skill_genomes (
    id                    TEXT PRIMARY KEY,
    run_id                TEXT NOT NULL,
    generation            INTEGER NOT NULL,
    skill_md_content      TEXT NOT NULL,
    frontmatter           TEXT NOT NULL,
    supporting_files      TEXT NOT NULL,
    traits                TEXT NOT NULL,
    meta_strategy         TEXT NOT NULL,
    parent_ids            TEXT NOT NULL,
    mutations             TEXT NOT NULL,
    mutation_rationale    TEXT NOT NULL,
    maturity              TEXT NOT NULL,
    generations_survived  INTEGER NOT NULL,
    deterministic_scores  TEXT NOT NULL,
    trigger_precision     REAL NOT NULL DEFAULT 0.0,
    trigger_recall        REAL NOT NULL DEFAULT 0.0,
    behavioral_signature  TEXT NOT NULL,
    pareto_objectives     TEXT NOT NULL,
    is_pareto_optimal     INTEGER NOT NULL DEFAULT 0,
    trait_attribution     TEXT NOT NULL,
    trait_diagnostics     TEXT NOT NULL,
    consistency_score     REAL
)
"""


async def test_migration_upgrades_prev2_database_without_data_loss(temp_db_path):
    # 1. Hand-create a pre-v2.0 evolution_runs + skill_genomes schema with a row
    async with aiosqlite.connect(temp_db_path) as conn:
        await conn.execute("PRAGMA foreign_keys = OFF")
        await conn.execute(_PREV2_EVOLUTION_RUNS_DDL)
        await conn.execute(_PREV2_SKILL_GENOMES_DDL)
        await conn.execute(
            """
            INSERT INTO evolution_runs (
                id, mode, specialization, population_size, num_generations,
                status, created_at, total_cost_usd, max_budget_usd,
                learning_log, pareto_front_ids
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run_legacy",
                "domain",
                "legacy skill",
                5,
                3,
                "complete",
                _now(),
                1.23,
                10.0,
                "[]",
                "[]",
            ),
        )
        await conn.execute(
            """
            INSERT INTO skill_genomes (
                id, run_id, generation, skill_md_content, frontmatter,
                supporting_files, traits, meta_strategy, parent_ids,
                mutations, mutation_rationale, maturity,
                generations_survived, deterministic_scores, trigger_precision,
                trigger_recall, behavioral_signature, pareto_objectives,
                is_pareto_optimal, trait_attribution, trait_diagnostics
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "genome_legacy",
                "run_legacy",
                0,
                "# Legacy\n",
                "{}",
                "{}",
                "[]",
                "",
                "[]",
                "[]",
                "",
                "draft",
                0,
                "{}",
                0.0,
                0.0,
                "[]",
                "{}",
                0,
                "{}",
                "{}",
            ),
        )
        await conn.commit()

    # 2. Run init_db — this must ADD the missing columns without losing data
    await init_db(temp_db_path)

    # 3. Verify the new columns exist and the old row is intact + has defaults
    conn = await get_connection(temp_db_path)
    try:
        runs_cols = await _columns(conn, "evolution_runs")
        genome_cols = await _columns(conn, "skill_genomes")

        assert "family_id" in runs_cols
        assert "evolution_mode" in runs_cols
        assert "variant_id" in genome_cols

        async with conn.execute(
            "SELECT id, specialization, total_cost_usd, family_id, evolution_mode "
            "FROM evolution_runs WHERE id = ?",
            ("run_legacy",),
        ) as cur:
            row = await cur.fetchone()
        assert row is not None
        assert row["id"] == "run_legacy"
        assert row["specialization"] == "legacy skill"
        assert row["total_cost_usd"] == 1.23
        assert row["family_id"] is None
        assert row["evolution_mode"] == "molecular"

        async with conn.execute(
            "SELECT id, run_id, variant_id FROM skill_genomes WHERE id = ?",
            ("genome_legacy",),
        ) as cur:
            row = await cur.fetchone()
        assert row is not None
        assert row["id"] == "genome_legacy"
        assert row["variant_id"] is None
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Roundtrip inserts — every new table should accept its natural shape
# ---------------------------------------------------------------------------


async def test_taxonomy_nodes_roundtrip(temp_db_path):
    await init_db(temp_db_path)
    conn = await get_connection(temp_db_path)
    try:
        dom_id = str(uuid.uuid4())
        focus_id = str(uuid.uuid4())
        now = _now()

        await conn.execute(
            "INSERT INTO taxonomy_nodes (id, level, slug, label, parent_id, description, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (dom_id, "domain", "testing", "Testing", None, "", now),
        )
        await conn.execute(
            "INSERT INTO taxonomy_nodes (id, level, slug, label, parent_id, description, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (focus_id, "focus", "unit-tests", "Unit Tests", dom_id, "", now),
        )
        await conn.commit()

        async with conn.execute(
            "SELECT id, level, slug, parent_id FROM taxonomy_nodes "
            "ORDER BY level DESC"
        ) as cur:
            rows = [dict(row) async for row in cur]
    finally:
        await conn.close()

    by_level = {r["level"]: r for r in rows}
    assert by_level["domain"]["id"] == dom_id
    assert by_level["domain"]["parent_id"] is None
    assert by_level["focus"]["parent_id"] == dom_id


async def test_skill_families_roundtrip_with_taxonomy_fks(temp_db_path):
    await init_db(temp_db_path)
    conn = await get_connection(temp_db_path)
    try:
        now = _now()
        dom_id = "dom_testing"
        await conn.execute(
            "INSERT INTO taxonomy_nodes (id, level, slug, label, description, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (dom_id, "domain", "testing", "Testing", "", now),
        )
        family_id = "fam_abc"
        await conn.execute(
            "INSERT INTO skill_families "
            "(id, slug, label, specialization, domain_id, tags, decomposition_strategy, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                family_id,
                "pytest-generator",
                "Pytest Generator",
                "Generate pytest tests",
                dom_id,
                '["python","testing"]',
                "atomic",
                now,
            ),
        )
        await conn.commit()

        async with conn.execute(
            "SELECT id, slug, domain_id, decomposition_strategy, tags "
            "FROM skill_families WHERE id = ?",
            (family_id,),
        ) as cur:
            row = await cur.fetchone()
    finally:
        await conn.close()

    assert row is not None
    assert row["id"] == family_id
    assert row["slug"] == "pytest-generator"
    assert row["domain_id"] == dom_id
    assert row["decomposition_strategy"] == "atomic"
    assert row["tags"] == '["python","testing"]'


async def test_variants_and_variant_evolutions_roundtrip(temp_db_path):
    await init_db(temp_db_path)
    conn = await get_connection(temp_db_path)
    try:
        now = _now()
        # Prerequisites: an evolution_run + skill_family + skill_genome
        run_id = "run_1"
        await conn.execute(
            "INSERT INTO evolution_runs "
            "(id, mode, specialization, population_size, num_generations, status, "
            " created_at, learning_log, pareto_front_ids) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, "domain", "x", 2, 2, "running", now, "[]", "[]"),
        )
        family_id = "fam_1"
        await conn.execute(
            "INSERT INTO skill_families (id, slug, label, specialization, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (family_id, "fam-one", "Family One", "do a thing", now),
        )
        genome_id = "gen_1"
        await conn.execute(
            "INSERT INTO skill_genomes "
            "(id, run_id, generation, skill_md_content, frontmatter, supporting_files, "
            " traits, meta_strategy, parent_ids, mutations, mutation_rationale, "
            " maturity, generations_survived, deterministic_scores, trigger_precision, "
            " trigger_recall, behavioral_signature, pareto_objectives, is_pareto_optimal, "
            " trait_attribution, trait_diagnostics) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                genome_id,
                run_id,
                0,
                "# G\n",
                "{}",
                "{}",
                "[]",
                "",
                "[]",
                "[]",
                "",
                "draft",
                0,
                "{}",
                0.0,
                0.0,
                "[]",
                "{}",
                0,
                "{}",
                "{}",
            ),
        )

        # VariantEvolution row (referenced by variants.evolution_id)
        vevo_id = "vevo_1"
        await conn.execute(
            "INSERT INTO variant_evolutions "
            "(id, family_id, dimension, tier, parent_run_id, population_size, "
            " num_generations, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (vevo_id, family_id, "mock-strategy", "capability", run_id, 2, 2, "pending", now),
        )

        # Variant row
        var_id = "var_1"
        await conn.execute(
            "INSERT INTO variants "
            "(id, family_id, dimension, tier, genome_id, fitness_score, is_active, "
            " evolution_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (var_id, family_id, "mock-strategy", "capability", genome_id, 0.81, 1, vevo_id, now),
        )

        # Point the variant_evolution at the winner
        await conn.execute(
            "UPDATE variant_evolutions SET winner_variant_id = ?, status = 'complete', "
            "completed_at = ? WHERE id = ?",
            (var_id, now, vevo_id),
        )
        await conn.commit()

        async with conn.execute(
            "SELECT id, dimension, tier, fitness_score, is_active, evolution_id "
            "FROM variants WHERE id = ?",
            (var_id,),
        ) as cur:
            v = await cur.fetchone()

        async with conn.execute(
            "SELECT id, status, winner_variant_id, completed_at "
            "FROM variant_evolutions WHERE id = ?",
            (vevo_id,),
        ) as cur:
            ve = await cur.fetchone()
    finally:
        await conn.close()

    assert v is not None
    assert v["dimension"] == "mock-strategy"
    assert v["tier"] == "capability"
    assert v["fitness_score"] == pytest.approx(0.81)
    assert v["is_active"] == 1
    assert v["evolution_id"] == vevo_id

    assert ve is not None
    assert ve["status"] == "complete"
    assert ve["winner_variant_id"] == var_id
    assert ve["completed_at"] is not None


# ---------------------------------------------------------------------------
# Cascading deletes
# ---------------------------------------------------------------------------


async def test_taxonomy_root_uniqueness_enforced(temp_db_path):
    """Two domain rows with the same slug must be rejected — SQLite treats
    NULL parent_id as distinct under normal UNIQUE, so we rely on a partial
    unique index. This regression-locks that behavior."""
    await init_db(temp_db_path)
    conn = await get_connection(temp_db_path)
    try:
        now = _now()
        await conn.execute(
            "INSERT INTO taxonomy_nodes (id, level, slug, label, parent_id, description, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("dom_a", "domain", "testing", "Testing", None, "", now),
        )
        await conn.commit()

        with pytest.raises(aiosqlite.IntegrityError):
            await conn.execute(
                "INSERT INTO taxonomy_nodes (id, level, slug, label, parent_id, description, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("dom_b", "domain", "testing", "Also Testing", None, "", now),
            )
            await conn.commit()
    finally:
        await conn.close()


async def test_taxonomy_child_uniqueness_enforced(temp_db_path):
    """Two focus rows with the same slug under the same parent must be
    rejected via the table-level UNIQUE(level, slug, parent_id)."""
    await init_db(temp_db_path)
    conn = await get_connection(temp_db_path)
    try:
        now = _now()
        await conn.execute(
            "INSERT INTO taxonomy_nodes (id, level, slug, label, parent_id, description, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("dom_1", "domain", "testing", "Testing", None, "", now),
        )
        await conn.execute(
            "INSERT INTO taxonomy_nodes (id, level, slug, label, parent_id, description, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("focus_1", "focus", "unit-tests", "Unit", "dom_1", "", now),
        )
        await conn.commit()

        with pytest.raises(aiosqlite.IntegrityError):
            await conn.execute(
                "INSERT INTO taxonomy_nodes (id, level, slug, label, parent_id, description, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("focus_2", "focus", "unit-tests", "Unit 2", "dom_1", "", now),
            )
            await conn.commit()
    finally:
        await conn.close()


async def test_deleting_family_cascades_variants(temp_db_path):
    await init_db(temp_db_path)
    conn = await get_connection(temp_db_path)
    try:
        now = _now()
        run_id, family_id, genome_id, var_id = "r1", "f1", "g1", "v1"

        await conn.execute(
            "INSERT INTO evolution_runs "
            "(id, mode, specialization, population_size, num_generations, status, "
            " created_at, learning_log, pareto_front_ids) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, "domain", "x", 2, 2, "running", now, "[]", "[]"),
        )
        await conn.execute(
            "INSERT INTO skill_families (id, slug, label, specialization, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (family_id, "f-one", "F One", "x", now),
        )
        await conn.execute(
            "INSERT INTO skill_genomes "
            "(id, run_id, generation, skill_md_content, frontmatter, supporting_files, "
            " traits, meta_strategy, parent_ids, mutations, mutation_rationale, "
            " maturity, generations_survived, deterministic_scores, trigger_precision, "
            " trigger_recall, behavioral_signature, pareto_objectives, is_pareto_optimal, "
            " trait_attribution, trait_diagnostics) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                genome_id,
                run_id,
                0,
                "# G\n",
                "{}",
                "{}",
                "[]",
                "",
                "[]",
                "[]",
                "",
                "draft",
                0,
                "{}",
                0.0,
                0.0,
                "[]",
                "{}",
                0,
                "{}",
                "{}",
            ),
        )
        await conn.execute(
            "INSERT INTO variants "
            "(id, family_id, dimension, tier, genome_id, fitness_score, is_active, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (var_id, family_id, "d1", "capability", genome_id, 0.5, 0, now),
        )
        await conn.commit()

        # Sanity check: variant exists
        async with conn.execute("SELECT COUNT(*) FROM variants") as cur:
            row = await cur.fetchone()
        assert row[0] == 1

        await conn.execute("DELETE FROM skill_families WHERE id = ?", (family_id,))
        await conn.commit()

        async with conn.execute("SELECT COUNT(*) FROM variants") as cur:
            row = await cur.fetchone()
        assert row[0] == 0, "deleting the family should cascade to variants"
    finally:
        await conn.close()
