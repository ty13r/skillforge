"""Async SQLite setup and connection management.

Tables:
- ``evolution_runs`` — top-level runs with JSON-blob learning_log + pareto_front
- ``skill_genomes`` — full SKILL.md content + layered fitness as JSON blobs
- ``generations`` — per-generation records with Pareto front + breeding report
- ``challenges`` — auto-generated challenges with evaluation_criteria blob
- ``competition_results`` — per Skill × Challenge results with trace blob

Schema source of truth: SCHEMA.md. This module must match SCHEMA.md exactly.
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite

from skillforge.config import DB_PATH

# ---------------------------------------------------------------------------
# DDL — order matters: evolution_runs → challenges → skill_genomes →
#         generations → competition_results  (FK dependency order)
# ---------------------------------------------------------------------------

_CREATE_EVOLUTION_RUNS = """
CREATE TABLE IF NOT EXISTS evolution_runs (
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
    failure_reason  TEXT,
    family_id       TEXT,
    evolution_mode  TEXT NOT NULL DEFAULT 'molecular',
    FOREIGN KEY (best_skill_id) REFERENCES skill_genomes(id)
)
"""

_CREATE_CHALLENGES = """
CREATE TABLE IF NOT EXISTS challenges (
    id                   TEXT PRIMARY KEY,
    run_id               TEXT NOT NULL,
    prompt               TEXT NOT NULL,
    difficulty           TEXT NOT NULL,
    evaluation_criteria  TEXT NOT NULL,
    verification_method  TEXT NOT NULL,
    setup_files          TEXT NOT NULL,
    gold_standard_hints  TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES evolution_runs(id) ON DELETE CASCADE
)
"""

_CREATE_SKILL_GENOMES = """
CREATE TABLE IF NOT EXISTS skill_genomes (
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
    consistency_score     REAL,
    variant_id            TEXT,
    FOREIGN KEY (run_id) REFERENCES evolution_runs(id) ON DELETE CASCADE
)
"""

_CREATE_GENERATIONS = """
CREATE TABLE IF NOT EXISTS generations (
    run_id               TEXT NOT NULL,
    number               INTEGER NOT NULL,
    pareto_front         TEXT NOT NULL,
    breeding_report      TEXT NOT NULL,
    learning_log_entries TEXT NOT NULL,
    best_fitness         REAL NOT NULL,
    avg_fitness          REAL NOT NULL,
    trait_survival       TEXT NOT NULL,
    trait_emergence      TEXT NOT NULL,
    PRIMARY KEY (run_id, number),
    FOREIGN KEY (run_id) REFERENCES evolution_runs(id) ON DELETE CASCADE
)
"""

_CREATE_COMPETITION_RESULTS = """
CREATE TABLE IF NOT EXISTS competition_results (
    skill_id               TEXT NOT NULL,
    challenge_id           TEXT NOT NULL,
    run_id                 TEXT NOT NULL,
    generation             INTEGER NOT NULL,
    output_files           TEXT NOT NULL,
    trace                  TEXT NOT NULL,
    compiles               INTEGER NOT NULL,
    tests_pass             INTEGER,
    lint_score             REAL,
    perf_metrics           TEXT NOT NULL,
    trigger_precision      REAL NOT NULL,
    trigger_recall         REAL NOT NULL,
    skill_was_loaded       INTEGER NOT NULL,
    instructions_followed  TEXT NOT NULL,
    instructions_ignored   TEXT NOT NULL,
    ignored_diagnostics    TEXT NOT NULL,
    scripts_executed       TEXT NOT NULL,
    behavioral_signature   TEXT NOT NULL,
    pairwise_wins          TEXT NOT NULL,
    pareto_objectives      TEXT NOT NULL,
    trait_contribution     TEXT NOT NULL,
    trait_diagnostics      TEXT NOT NULL,
    judge_reasoning        TEXT NOT NULL,
    PRIMARY KEY (skill_id, challenge_id),
    FOREIGN KEY (skill_id) REFERENCES skill_genomes(id) ON DELETE CASCADE,
    FOREIGN KEY (challenge_id) REFERENCES challenges(id) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES evolution_runs(id) ON DELETE CASCADE
)
"""

_CREATE_INVITE_REQUESTS = """
CREATE TABLE IF NOT EXISTS invite_requests (
    id          TEXT PRIMARY KEY,
    email       TEXT NOT NULL,
    message     TEXT,
    created_at  TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    notes       TEXT
)
"""

# Bookkeeping for best-effort skill teardown failures from the Managed Agents
# backend. Cleanup must NEVER block the evolution loop, so the Phase 1
# competitor schedules teardown as a detached task; failures land here for
# a batch sweeper to retry. See PLAN-V1.2 architectural decision #7.
_CREATE_LEAKED_SKILLS = """
CREATE TABLE IF NOT EXISTS leaked_skills (
    id          TEXT PRIMARY KEY,
    skill_id    TEXT NOT NULL,
    run_id      TEXT,
    created_at  TEXT NOT NULL,
    error       TEXT
)
"""

_CREATE_RUN_EVENTS = """
CREATE TABLE IF NOT EXISTS run_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    payload     TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES evolution_runs (id) ON DELETE CASCADE
)
"""

_CREATE_CANDIDATE_SEEDS = """
CREATE TABLE IF NOT EXISTS candidate_seeds (
    id              TEXT PRIMARY KEY,
    source          TEXT NOT NULL,
    source_run_id   TEXT,
    source_skill_id TEXT,
    title           TEXT NOT NULL,
    specialization  TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT 'uncategorized',
    skill_md_content TEXT NOT NULL,
    supporting_files TEXT NOT NULL DEFAULT '{}',
    traits          TEXT NOT NULL DEFAULT '[]',
    fitness_score   REAL,
    status          TEXT NOT NULL DEFAULT 'pending',
    created_at      TEXT NOT NULL,
    promoted_at     TEXT,
    notes           TEXT
)
"""

# ---------------------------------------------------------------------------
# v2.0 tables — taxonomy, families, variants, variant evolutions
# ---------------------------------------------------------------------------

_CREATE_TAXONOMY_NODES = """
CREATE TABLE IF NOT EXISTS taxonomy_nodes (
    id          TEXT PRIMARY KEY,
    level       TEXT NOT NULL,
    slug        TEXT NOT NULL,
    label       TEXT NOT NULL,
    parent_id   TEXT,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    FOREIGN KEY (parent_id) REFERENCES taxonomy_nodes(id) ON DELETE CASCADE,
    UNIQUE (level, slug, parent_id)
)
"""

_CREATE_SKILL_FAMILIES = """
CREATE TABLE IF NOT EXISTS skill_families (
    id                     TEXT PRIMARY KEY,
    slug                   TEXT NOT NULL UNIQUE,
    label                  TEXT NOT NULL,
    specialization         TEXT NOT NULL,
    domain_id              TEXT,
    focus_id               TEXT,
    language_id            TEXT,
    tags                   TEXT NOT NULL DEFAULT '[]',
    decomposition_strategy TEXT NOT NULL DEFAULT 'molecular',
    best_assembly_id       TEXT,
    created_at             TEXT NOT NULL,
    FOREIGN KEY (domain_id)   REFERENCES taxonomy_nodes(id) ON DELETE SET NULL,
    FOREIGN KEY (focus_id)    REFERENCES taxonomy_nodes(id) ON DELETE SET NULL,
    FOREIGN KEY (language_id) REFERENCES taxonomy_nodes(id) ON DELETE SET NULL
)
"""

_CREATE_VARIANTS = """
CREATE TABLE IF NOT EXISTS variants (
    id            TEXT PRIMARY KEY,
    family_id     TEXT NOT NULL,
    dimension     TEXT NOT NULL,
    tier          TEXT NOT NULL,
    genome_id     TEXT NOT NULL,
    fitness_score REAL NOT NULL DEFAULT 0.0,
    is_active     INTEGER NOT NULL DEFAULT 0,
    evolution_id  TEXT,
    created_at    TEXT NOT NULL,
    FOREIGN KEY (family_id)    REFERENCES skill_families(id)      ON DELETE CASCADE,
    FOREIGN KEY (genome_id)    REFERENCES skill_genomes(id)       ON DELETE CASCADE,
    FOREIGN KEY (evolution_id) REFERENCES variant_evolutions(id)  ON DELETE SET NULL
)
"""

# Note: no ``FOREIGN KEY winner_variant_id REFERENCES variants(id)`` because
# variants.evolution_id already points here and SQLite dislikes circular FKs
# on CREATE. The relationship is enforced at the query layer.
_CREATE_VARIANT_EVOLUTIONS = """
CREATE TABLE IF NOT EXISTS variant_evolutions (
    id                   TEXT PRIMARY KEY,
    family_id            TEXT NOT NULL,
    dimension            TEXT NOT NULL,
    tier                 TEXT NOT NULL,
    parent_run_id        TEXT NOT NULL,
    population_size      INTEGER NOT NULL DEFAULT 2,
    num_generations      INTEGER NOT NULL DEFAULT 2,
    status               TEXT NOT NULL DEFAULT 'pending',
    winner_variant_id    TEXT,
    foundation_genome_id TEXT,
    challenge_id         TEXT,
    created_at           TEXT NOT NULL,
    completed_at         TEXT,
    FOREIGN KEY (family_id)            REFERENCES skill_families(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_run_id)        REFERENCES evolution_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (foundation_genome_id) REFERENCES skill_genomes(id)  ON DELETE SET NULL,
    FOREIGN KEY (challenge_id)         REFERENCES challenges(id)     ON DELETE SET NULL
)
"""

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_runs_status ON evolution_runs (status)",
    "CREATE INDEX IF NOT EXISTS idx_runs_created_at ON evolution_runs (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_challenges_run ON challenges (run_id)",
    "CREATE INDEX IF NOT EXISTS idx_genomes_run_gen ON skill_genomes (run_id, generation)",
    "CREATE INDEX IF NOT EXISTS idx_genomes_pareto ON skill_genomes (run_id, is_pareto_optimal)",
    "CREATE INDEX IF NOT EXISTS idx_results_run_gen ON competition_results (run_id, generation)",
    "CREATE INDEX IF NOT EXISTS idx_results_challenge ON competition_results (challenge_id)",
    "CREATE INDEX IF NOT EXISTS idx_invite_requests_created ON invite_requests (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_leaked_skills_created ON leaked_skills (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_run_events_run_id ON run_events (run_id, id)",
    "CREATE INDEX IF NOT EXISTS idx_candidate_seeds_status ON candidate_seeds (status, created_at DESC)",
    # v2.0 indexes
    "CREATE INDEX IF NOT EXISTS idx_taxonomy_nodes_level_slug ON taxonomy_nodes (level, slug)",
    "CREATE INDEX IF NOT EXISTS idx_taxonomy_nodes_parent ON taxonomy_nodes (parent_id)",
    # Partial unique index enforces "one domain row per (level, slug)" because
    # the table-level UNIQUE(level, slug, parent_id) constraint does not catch
    # root rows — SQLite treats NULL parent_id values as distinct.
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_taxonomy_nodes_root_unique "
    "ON taxonomy_nodes (level, slug) WHERE parent_id IS NULL",
    "CREATE INDEX IF NOT EXISTS idx_skill_families_slug ON skill_families (slug)",
    "CREATE INDEX IF NOT EXISTS idx_skill_families_domain ON skill_families (domain_id)",
    "CREATE INDEX IF NOT EXISTS idx_skill_families_focus ON skill_families (focus_id)",
    "CREATE INDEX IF NOT EXISTS idx_skill_families_language ON skill_families (language_id)",
    "CREATE INDEX IF NOT EXISTS idx_variants_family_dim ON variants (family_id, dimension)",
    "CREATE INDEX IF NOT EXISTS idx_variants_family_active ON variants (family_id, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_variants_genome ON variants (genome_id)",
    "CREATE INDEX IF NOT EXISTS idx_variant_evolutions_family ON variant_evolutions (family_id, dimension)",
    "CREATE INDEX IF NOT EXISTS idx_variant_evolutions_parent_run ON variant_evolutions (parent_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_runs_family ON evolution_runs (family_id)",
    "CREATE INDEX IF NOT EXISTS idx_genomes_variant ON skill_genomes (variant_id)",
    # SKLD-bench indexes
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_benchmark_challenge_model ON benchmark_results (challenge_id, model)",
    "CREATE INDEX IF NOT EXISTS idx_benchmark_family ON benchmark_results (family_slug, model)",
    "CREATE INDEX IF NOT EXISTS idx_benchmark_tier ON benchmark_results (tier, model)",
    # SKLD-bench dispatch transcript indexes
    "CREATE INDEX IF NOT EXISTS idx_dispatch_family ON dispatch_transcripts (family_slug, challenge_id)",
    "CREATE INDEX IF NOT EXISTS idx_dispatch_type ON dispatch_transcripts (dispatch_type)",
    "CREATE INDEX IF NOT EXISTS idx_dispatch_run ON dispatch_transcripts (run_id)",
]

# ---------------------------------------------------------------------------
# SKLD-bench — dispatch transcripts (full audit trail for every agent dispatch)
# ---------------------------------------------------------------------------

_CREATE_DISPATCH_TRANSCRIPTS = """
CREATE TABLE IF NOT EXISTS dispatch_transcripts (
    id              TEXT PRIMARY KEY,
    run_id          TEXT,
    benchmark_id    TEXT,
    family_slug     TEXT NOT NULL,
    challenge_id    TEXT NOT NULL,
    dispatch_type   TEXT NOT NULL,
    model           TEXT NOT NULL,
    skill_variant   TEXT,
    prompt          TEXT NOT NULL,
    raw_response    TEXT NOT NULL,
    extracted_files TEXT NOT NULL,
    scores          TEXT NOT NULL DEFAULT '{}',
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    duration_ms     INTEGER NOT NULL DEFAULT 0,
    error           TEXT,
    created_at      TEXT NOT NULL
)
"""

# ---------------------------------------------------------------------------
# SKLD-bench — raw model baseline performance, no skill guidance
# ---------------------------------------------------------------------------

_CREATE_BENCHMARK_RESULTS = """
CREATE TABLE IF NOT EXISTS benchmark_results (
    id              TEXT PRIMARY KEY,
    family_slug     TEXT NOT NULL,
    challenge_id    TEXT NOT NULL,
    challenge_path  TEXT NOT NULL,
    model           TEXT NOT NULL,
    tier            TEXT NOT NULL,
    dimension       TEXT NOT NULL,
    score           REAL NOT NULL,
    passed          INTEGER NOT NULL,
    objectives      TEXT NOT NULL,
    output_files    TEXT NOT NULL,
    total_tokens    INTEGER NOT NULL,
    duration_ms     INTEGER NOT NULL,
    error           TEXT,
    created_at      TEXT NOT NULL
)
"""

_TABLE_DDLS = [
    _CREATE_EVOLUTION_RUNS,
    _CREATE_CHALLENGES,
    _CREATE_SKILL_GENOMES,
    _CREATE_GENERATIONS,
    _CREATE_COMPETITION_RESULTS,
    _CREATE_INVITE_REQUESTS,
    _CREATE_LEAKED_SKILLS,
    _CREATE_RUN_EVENTS,
    _CREATE_CANDIDATE_SEEDS,
    # v2.0 — taxonomy must precede skill_families (FK); skill_families must
    # precede variants + variant_evolutions; variant_evolutions is referenced
    # by variants.evolution_id so it must come first.
    _CREATE_TAXONOMY_NODES,
    _CREATE_SKILL_FAMILIES,
    _CREATE_VARIANT_EVOLUTIONS,
    _CREATE_VARIANTS,
    # SKLD-bench baseline + audit trail
    _CREATE_BENCHMARK_RESULTS,
    _CREATE_DISPATCH_TRANSCRIPTS,
]

_DROP_ORDER = [
    # SKLD-bench
    "dispatch_transcripts",
    "benchmark_results",
    # v2.0 — drop leaves first
    "variants",
    "variant_evolutions",
    "skill_families",
    "taxonomy_nodes",
    # v1.x
    "competition_results",
    "generations",
    "skill_genomes",
    "challenges",
    "evolution_runs",
]

# ---------------------------------------------------------------------------
# Migrations — additive, idempotent. Each entry describes a column we want to
# ADD to an existing table. Guarded by a ``PRAGMA table_info()`` probe, so
# running init_db twice is a no-op and upgrading an older DB doesn't lose data.
# ---------------------------------------------------------------------------

# (table_name, column_name, column_sql_fragment)
_ADDITIVE_COLUMN_MIGRATIONS: list[tuple[str, str, str]] = [
    ("evolution_runs", "family_id", "TEXT"),
    ("evolution_runs", "evolution_mode", "TEXT NOT NULL DEFAULT 'molecular'"),
    ("skill_genomes", "variant_id", "TEXT"),
    # v2.1.3 — multi-level score breakdown on benchmark_results
    ("benchmark_results", "scores", "TEXT NOT NULL DEFAULT '{}'"),
]


async def _apply_additive_migrations(conn: aiosqlite.Connection) -> None:
    """Add missing columns to existing tables without touching data.

    Uses ``PRAGMA table_info`` to detect which columns already exist. On a
    freshly-created database the v2.0 columns already come from the CREATE
    TABLE DDL above, so this function is a no-op. On an upgrade from a
    pre-v2.0 database, the columns are added via ``ALTER TABLE``.
    """
    for table, column, column_sql in _ADDITIVE_COLUMN_MIGRATIONS:
        # Check whether the column already exists on this table.
        async with conn.execute(f"PRAGMA table_info({table})") as cur:
            existing = {row[1] async for row in cur}  # row[1] is column name
        if column in existing:
            continue
        await conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_sql}")


async def init_db(db_path: Path | None = None) -> None:
    """Create tables and indexes if they don't exist.

    Opens a fresh connection to ``db_path`` (defaults to ``config.DB_PATH``),
    enables foreign keys, runs all DDL, applies additive column migrations
    for v2.0, creates indexes, commits, and closes.
    """
    path = db_path if db_path is not None else DB_PATH
    async with aiosqlite.connect(path) as conn:
        await conn.execute("PRAGMA foreign_keys = ON")
        for ddl in _TABLE_DDLS:
            await conn.execute(ddl)
        await _apply_additive_migrations(conn)
        for idx in _INDEXES:
            await conn.execute(idx)
        await conn.commit()


async def get_connection(db_path: Path | None = None) -> aiosqlite.Connection:
    """Return an open async SQLite connection with foreign keys enabled.

    Opens a fresh connection, sets ``row_factory`` to ``aiosqlite.Row``, and
    enables ``PRAGMA foreign_keys = ON``.

    The *caller* is responsible for closing the connection.  Use either::

        conn = await get_connection(path)
        try:
            ...
        finally:
            await conn.close()

    or with an async-context-manager wrapper (queries.py uses
    ``_open_conn`` for this).
    """
    path = db_path if db_path is not None else DB_PATH
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    return conn


async def reset_db(db_path: Path | None = None) -> None:
    """Drop all tables then re-run ``init_db``. Intended for tests only."""
    path = db_path if db_path is not None else DB_PATH
    async with aiosqlite.connect(path) as conn:
        await conn.execute("PRAGMA foreign_keys = OFF")
        for table in _DROP_ORDER:
            await conn.execute(f"DROP TABLE IF EXISTS {table}")
        await conn.commit()
    await init_db(path)


__all__ = ["init_db", "get_connection", "reset_db", "DB_PATH"]
