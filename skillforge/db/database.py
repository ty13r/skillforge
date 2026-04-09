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

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_runs_status ON evolution_runs (status)",
    "CREATE INDEX IF NOT EXISTS idx_runs_created_at ON evolution_runs (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_challenges_run ON challenges (run_id)",
    "CREATE INDEX IF NOT EXISTS idx_genomes_run_gen ON skill_genomes (run_id, generation)",
    "CREATE INDEX IF NOT EXISTS idx_genomes_pareto ON skill_genomes (run_id, is_pareto_optimal)",
    "CREATE INDEX IF NOT EXISTS idx_results_run_gen ON competition_results (run_id, generation)",
    "CREATE INDEX IF NOT EXISTS idx_results_challenge ON competition_results (challenge_id)",
    "CREATE INDEX IF NOT EXISTS idx_invite_requests_created ON invite_requests (created_at DESC)",
]

_TABLE_DDLS = [
    _CREATE_EVOLUTION_RUNS,
    _CREATE_CHALLENGES,
    _CREATE_SKILL_GENOMES,
    _CREATE_GENERATIONS,
    _CREATE_COMPETITION_RESULTS,
    _CREATE_INVITE_REQUESTS,
]

_DROP_ORDER = [
    "competition_results",
    "generations",
    "skill_genomes",
    "challenges",
    "evolution_runs",
]


async def init_db(db_path: Path | None = None) -> None:
    """Create tables and indexes if they don't exist.

    Opens a fresh connection to ``db_path`` (defaults to ``config.DB_PATH``),
    enables foreign keys, runs all DDL, commits, and closes.
    """
    path = db_path if db_path is not None else DB_PATH
    async with aiosqlite.connect(path) as conn:
        await conn.execute("PRAGMA foreign_keys = ON")
        for ddl in _TABLE_DDLS:
            await conn.execute(ddl)
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
