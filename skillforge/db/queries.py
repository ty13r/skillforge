"""CRUD operations for EvolutionRun, SkillGenome, Generation, Challenge.

All functions are async. Each opens its own connection via ``get_connection``
and closes it on exit (using async-with). Serialization delegates entirely to
the model dataclasses' ``to_dict``/``from_dict`` methods — no ad-hoc JSON
logic here beyond the column-level ``json.dumps``/``json.loads`` needed to
store complex fields in TEXT columns.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from skillforge.db.database import get_connection
from skillforge.models import (
    Challenge,
    CompetitionResult,
    EvolutionRun,
    Generation,
    SkillFamily,
    SkillGenome,
    TaxonomyNode,
    Variant,
    VariantEvolution,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _connect(db_path: Path | None = None) -> AsyncIterator[aiosqlite.Connection]:
    """Async context manager: open a connection, yield it, then close.

    This avoids the ``async with await get_connection(...)`` double-entry
    anti-pattern.  ``get_connection`` is kept for callers that need an
    already-open connection handed back (e.g., the API layer in a future step).
    """
    conn = await get_connection(db_path)
    try:
        yield conn
    finally:
        await conn.close()


def _int_or_none(v: bool | int | None) -> int | None:
    """Convert a bool/None to 0/1/None for SQLite INTEGER columns."""
    if v is None:
        return None
    return int(v)


def _row_get(row: aiosqlite.Row, column: str, default=None):
    """Defensive column lookup on an aiosqlite.Row.

    `aiosqlite.Row` does not implement `dict.get()` and indexing a missing
    column raises `IndexError`. We use this on v2.0 columns that may be
    absent on legacy databases that haven't migrated yet (init_db
    handles the migration but tests sometimes pre-build a partial schema).
    """
    try:
        return row[column]
    except (IndexError, KeyError):
        return default


# ---------------------------------------------------------------------------
# Challenge
# ---------------------------------------------------------------------------


async def save_challenge(
    challenge: Challenge,
    run_id: str,
    db_path: Path | None = None,
) -> None:
    """Upsert a Challenge row linked to ``run_id``."""
    d = challenge.to_dict()
    async with _connect(db_path) as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO challenges
                (id, run_id, prompt, difficulty, evaluation_criteria,
                 verification_method, setup_files, gold_standard_hints)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                d["id"],
                run_id,
                d["prompt"],
                d["difficulty"],
                json.dumps(d["evaluation_criteria"]),
                d["verification_method"],
                json.dumps(d["setup_files"]),
                d["gold_standard_hints"],
            ),
        )
        await conn.commit()


async def _get_challenges_for_run(
    run_id: str,
    conn: aiosqlite.Connection,
) -> list[Challenge]:
    async with conn.execute(
        "SELECT * FROM challenges WHERE run_id = ?", (run_id,)
    ) as cur:
        rows = await cur.fetchall()
    challenges = []
    for row in rows:
        d = {
            "id": row["id"],
            "prompt": row["prompt"],
            "difficulty": row["difficulty"],
            "evaluation_criteria": json.loads(row["evaluation_criteria"]),
            "verification_method": row["verification_method"],
            "setup_files": json.loads(row["setup_files"]),
            "gold_standard_hints": row["gold_standard_hints"],
        }
        challenges.append(Challenge.from_dict(d))
    return challenges


# ---------------------------------------------------------------------------
# SkillGenome
# ---------------------------------------------------------------------------


async def save_genome(
    genome: SkillGenome,
    run_id: str,
    db_path: Path | None = None,
) -> None:
    """Upsert a SkillGenome row linked to ``run_id``."""
    d = genome.to_dict()
    async with _connect(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO skill_genomes
                (id, run_id, generation, skill_md_content, frontmatter,
                 supporting_files, traits, meta_strategy, parent_ids,
                 mutations, mutation_rationale, maturity, generations_survived,
                 deterministic_scores, trigger_precision, trigger_recall,
                 behavioral_signature, pareto_objectives, is_pareto_optimal,
                 trait_attribution, trait_diagnostics, consistency_score,
                 variant_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                maturity=excluded.maturity,
                generations_survived=excluded.generations_survived,
                deterministic_scores=excluded.deterministic_scores,
                trigger_precision=excluded.trigger_precision,
                trigger_recall=excluded.trigger_recall,
                behavioral_signature=excluded.behavioral_signature,
                pareto_objectives=excluded.pareto_objectives,
                is_pareto_optimal=excluded.is_pareto_optimal,
                trait_attribution=excluded.trait_attribution,
                trait_diagnostics=excluded.trait_diagnostics,
                consistency_score=excluded.consistency_score,
                variant_id=excluded.variant_id
            """,
            (
                d["id"],
                run_id,
                d["generation"],
                d["skill_md_content"],
                json.dumps(d["frontmatter"]),
                json.dumps(d["supporting_files"]),
                json.dumps(d["traits"]),
                d["meta_strategy"],
                json.dumps(d["parent_ids"]),
                json.dumps(d["mutations"]),
                d["mutation_rationale"],
                d["maturity"],
                d["generations_survived"],
                json.dumps(d["deterministic_scores"]),
                d["trigger_precision"],
                d["trigger_recall"],
                json.dumps(d["behavioral_signature"]),
                json.dumps(d["pareto_objectives"]),
                int(d["is_pareto_optimal"]),
                json.dumps(d["trait_attribution"]),
                json.dumps(d["trait_diagnostics"]),
                d["consistency_score"],
                d.get("variant_id"),
            ),
        )
        await conn.commit()


async def _get_genome_by_id(
    genome_id: str,
    conn: aiosqlite.Connection,
) -> SkillGenome | None:
    async with conn.execute(
        "SELECT * FROM skill_genomes WHERE id = ?", (genome_id,)
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        return None
    return _row_to_genome(row)


async def _get_genomes_for_run_gen(
    run_id: str,
    generation: int,
    conn: aiosqlite.Connection,
) -> list[SkillGenome]:
    async with conn.execute(
        "SELECT * FROM skill_genomes WHERE run_id = ? AND generation = ?",
        (run_id, generation),
    ) as cur:
        rows = await cur.fetchall()
    return [_row_to_genome(r) for r in rows]


def _row_to_genome(row: aiosqlite.Row) -> SkillGenome:
    d = {
        "id": row["id"],
        "generation": row["generation"],
        "skill_md_content": row["skill_md_content"],
        "frontmatter": json.loads(row["frontmatter"]),
        "supporting_files": json.loads(row["supporting_files"]),
        "traits": json.loads(row["traits"]),
        "meta_strategy": row["meta_strategy"],
        "parent_ids": json.loads(row["parent_ids"]),
        "mutations": json.loads(row["mutations"]),
        "mutation_rationale": row["mutation_rationale"],
        "maturity": row["maturity"],
        "generations_survived": row["generations_survived"],
        "deterministic_scores": json.loads(row["deterministic_scores"]),
        "trigger_precision": row["trigger_precision"],
        "trigger_recall": row["trigger_recall"],
        "behavioral_signature": json.loads(row["behavioral_signature"]),
        "pareto_objectives": json.loads(row["pareto_objectives"]),
        "is_pareto_optimal": bool(row["is_pareto_optimal"]),
        "trait_attribution": json.loads(row["trait_attribution"]),
        "trait_diagnostics": json.loads(row["trait_diagnostics"]),
        "consistency_score": row["consistency_score"],
        "variant_id": _row_get(row, "variant_id"),
    }
    return SkillGenome.from_dict(d)


# ---------------------------------------------------------------------------
# CompetitionResult
# ---------------------------------------------------------------------------


async def save_result(
    result: CompetitionResult,
    run_id: str,
    generation: int,
    db_path: Path | None = None,
) -> None:
    """Upsert a CompetitionResult row."""
    d = result.to_dict()
    async with _connect(db_path) as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO competition_results
                (skill_id, challenge_id, run_id, generation,
                 output_files, trace, compiles, tests_pass, lint_score,
                 perf_metrics, trigger_precision, trigger_recall,
                 skill_was_loaded, instructions_followed, instructions_ignored,
                 ignored_diagnostics, scripts_executed, behavioral_signature,
                 pairwise_wins, pareto_objectives, trait_contribution,
                 trait_diagnostics, judge_reasoning)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                d["skill_id"],
                d["challenge_id"],
                run_id,
                generation,
                json.dumps(d["output_files"]),
                json.dumps(d["trace"]),
                int(d["compiles"]),
                _int_or_none(d["tests_pass"]),
                d["lint_score"],
                json.dumps(d["perf_metrics"]),
                d["trigger_precision"],
                d["trigger_recall"],
                int(d["skill_was_loaded"]),
                json.dumps(d["instructions_followed"]),
                json.dumps(d["instructions_ignored"]),
                json.dumps(d["ignored_diagnostics"]),
                json.dumps(d["scripts_executed"]),
                json.dumps(d["behavioral_signature"]),
                json.dumps(d["pairwise_wins"]),
                json.dumps(d["pareto_objectives"]),
                json.dumps(d["trait_contribution"]),
                json.dumps(d["trait_diagnostics"]),
                d["judge_reasoning"],
            ),
        )
        await conn.commit()


async def _get_results_for_run_gen(
    run_id: str,
    generation: int,
    conn: aiosqlite.Connection,
) -> list[CompetitionResult]:
    async with conn.execute(
        "SELECT * FROM competition_results WHERE run_id = ? AND generation = ?",
        (run_id, generation),
    ) as cur:
        rows = await cur.fetchall()
    return [_row_to_result(r) for r in rows]


def _row_to_result(row: aiosqlite.Row) -> CompetitionResult:
    raw_tests_pass = row["tests_pass"]
    d = {
        "skill_id": row["skill_id"],
        "challenge_id": row["challenge_id"],
        "output_files": json.loads(row["output_files"]),
        "trace": json.loads(row["trace"]),
        "compiles": bool(row["compiles"]),
        "tests_pass": bool(raw_tests_pass) if raw_tests_pass is not None else None,
        "lint_score": row["lint_score"],
        "perf_metrics": json.loads(row["perf_metrics"]),
        "trigger_precision": row["trigger_precision"],
        "trigger_recall": row["trigger_recall"],
        "skill_was_loaded": bool(row["skill_was_loaded"]),
        "instructions_followed": json.loads(row["instructions_followed"]),
        "instructions_ignored": json.loads(row["instructions_ignored"]),
        "ignored_diagnostics": json.loads(row["ignored_diagnostics"]),
        "scripts_executed": json.loads(row["scripts_executed"]),
        "behavioral_signature": json.loads(row["behavioral_signature"]),
        "pairwise_wins": json.loads(row["pairwise_wins"]),
        "pareto_objectives": json.loads(row["pareto_objectives"]),
        "trait_contribution": json.loads(row["trait_contribution"]),
        "trait_diagnostics": json.loads(row["trait_diagnostics"]),
        "judge_reasoning": row["judge_reasoning"],
    }
    return CompetitionResult.from_dict(d)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


async def save_generation(
    generation: Generation,
    run_id: str,
    db_path: Path | None = None,
) -> None:
    """Upsert a Generation row and all its nested skills and results."""
    d = generation.to_dict()
    async with _connect(db_path) as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO generations
                (run_id, number, pareto_front, breeding_report,
                 learning_log_entries, best_fitness, avg_fitness,
                 trait_survival, trait_emergence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                d["number"],
                json.dumps(d["pareto_front"]),
                d["breeding_report"],
                json.dumps(d["learning_log_entries"]),
                d["best_fitness"],
                d["avg_fitness"],
                json.dumps(d["trait_survival"]),
                json.dumps(d["trait_emergence"]),
            ),
        )
        await conn.commit()

    # Save nested skills and results using their own connections
    for skill in generation.skills:
        await save_genome(skill, run_id, db_path)
    for result in generation.results:
        await save_result(result, run_id, generation.number, db_path)


async def _get_generations_for_run(
    run_id: str,
    conn: aiosqlite.Connection,
) -> list[Generation]:
    async with conn.execute(
        "SELECT * FROM generations WHERE run_id = ? ORDER BY number",
        (run_id,),
    ) as cur:
        rows = await cur.fetchall()

    generations = []
    for row in rows:
        gen_number = row["number"]
        skills = await _get_genomes_for_run_gen(run_id, gen_number, conn)
        results = await _get_results_for_run_gen(run_id, gen_number, conn)
        d = {
            "number": gen_number,
            "skills": [s.to_dict() for s in skills],
            "results": [r.to_dict() for r in results],
            "pareto_front": json.loads(row["pareto_front"]),
            "breeding_report": row["breeding_report"],
            "learning_log_entries": json.loads(row["learning_log_entries"]),
            "best_fitness": row["best_fitness"],
            "avg_fitness": row["avg_fitness"],
            "trait_survival": json.loads(row["trait_survival"]),
            "trait_emergence": json.loads(row["trait_emergence"]),
        }
        generations.append(Generation.from_dict(d))
    return generations


# ---------------------------------------------------------------------------
# EvolutionRun
# ---------------------------------------------------------------------------


async def save_run(
    run: EvolutionRun,
    db_path: Path | None = None,
) -> None:
    """Upsert an EvolutionRun and its entire nested tree.

    Saves challenges, generations (which in turn save genomes + results).

    The run row is first written with ``best_skill_id = NULL`` so that the FK
    constraint (``best_skill_id → skill_genomes.id``) is satisfied before the
    genomes are inserted.  A second UPDATE sets the real ``best_skill_id`` after
    all genomes are persisted.
    """
    d = run.to_dict()
    pareto_front_ids = [s["id"] for s in d["pareto_front"]]
    best_skill_id = d["best_skill"]["id"] if d["best_skill"] is not None else None

    # Step 1: upsert the run row with best_skill_id = NULL to avoid the
    # FK violation (the referenced genome may not exist yet).
    #
    # Uses INSERT ... ON CONFLICT(id) DO UPDATE instead of INSERT OR REPLACE
    # because REPLACE deletes the existing row (triggering ON DELETE CASCADE
    # on variant_evolutions/challenges/generations/etc.) and then inserts a
    # new one, which WIPES every child row. DO UPDATE is a proper in-place
    # update that leaves children intact. This matters when save_run is
    # called twice during run submission (once before and once after the
    # Taxonomist's variant_evolutions INSERTs).
    async with _connect(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO evolution_runs
                (id, mode, specialization, population_size, num_generations,
                 status, created_at, completed_at, total_cost_usd, max_budget_usd,
                 learning_log, pareto_front_ids, best_skill_id, failure_reason,
                 family_id, evolution_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                mode=excluded.mode,
                specialization=excluded.specialization,
                population_size=excluded.population_size,
                num_generations=excluded.num_generations,
                status=excluded.status,
                completed_at=excluded.completed_at,
                total_cost_usd=excluded.total_cost_usd,
                max_budget_usd=excluded.max_budget_usd,
                learning_log=excluded.learning_log,
                pareto_front_ids=excluded.pareto_front_ids,
                failure_reason=excluded.failure_reason,
                family_id=excluded.family_id,
                evolution_mode=excluded.evolution_mode
            """,
            (
                d["id"],
                d["mode"],
                d["specialization"],
                d["population_size"],
                d["num_generations"],
                d["status"],
                d["created_at"],
                d["completed_at"],
                d["total_cost_usd"],
                d.get("max_budget_usd", 10.0),
                json.dumps(d["learning_log"]),
                json.dumps(pareto_front_ids),
                None,  # best_skill_id deferred — set after genomes are saved
                d.get("failure_reason"),
                d.get("family_id"),
                d.get("evolution_mode", "molecular"),
            ),
        )
        await conn.commit()

    # Step 2: persist challenges, then generations (which save genomes + results).
    for challenge in run.challenges:
        await save_challenge(challenge, run.id, db_path)
    for generation in run.generations:
        await save_generation(generation, run.id, db_path)
    # best_skill may already be stored as part of a generation; save anyway
    # (INSERT OR REPLACE is idempotent).
    if run.best_skill is not None:
        await save_genome(run.best_skill, run.id, db_path)

    # Step 3: update best_skill_id now that the genome row exists.
    if best_skill_id is not None:
        async with _connect(db_path) as conn:
            await conn.execute(
                "UPDATE evolution_runs SET best_skill_id = ? WHERE id = ?",
                (best_skill_id, run.id),
            )
            await conn.commit()


async def get_run(
    run_id: str,
    db_path: Path | None = None,
) -> EvolutionRun | None:
    """Fetch a single run by ID with the full nested tree rehydrated."""
    async with _connect(db_path) as conn:
        async with conn.execute(
            "SELECT * FROM evolution_runs WHERE id = ?", (run_id,)
        ) as cur:
            row = await cur.fetchone()

        if row is None:
            return None

        challenges = await _get_challenges_for_run(run_id, conn)
        generations = await _get_generations_for_run(run_id, conn)

        best_skill: SkillGenome | None = None
        if row["best_skill_id"] is not None:
            best_skill = await _get_genome_by_id(row["best_skill_id"], conn)

        pareto_front_ids: list[str] = json.loads(row["pareto_front_ids"])
        pareto_front: list[SkillGenome] = []
        for gid in pareto_front_ids:
            g = await _get_genome_by_id(gid, conn)
            if g is not None:
                pareto_front.append(g)

    # Build a dict that EvolutionRun.from_dict can consume
    run_dict = {
        "id": row["id"],
        "mode": row["mode"],
        "specialization": row["specialization"],
        "population_size": row["population_size"],
        "num_generations": row["num_generations"],
        "status": row["status"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
        "total_cost_usd": row["total_cost_usd"],
        "learning_log": json.loads(row["learning_log"]),
        "challenges": [c.to_dict() for c in challenges],
        "generations": [g.to_dict() for g in generations],
        "best_skill": best_skill.to_dict() if best_skill is not None else None,
        "pareto_front": [s.to_dict() for s in pareto_front],
        # v2.0 columns — present in fresh installs and on upgraded DBs after
        # the additive migration in init_db.
        "family_id": _row_get(row, "family_id"),
        "evolution_mode": _row_get(row, "evolution_mode") or "molecular",
    }
    return EvolutionRun.from_dict(run_dict)


async def list_runs(
    limit: int = 50,
    db_path: Path | None = None,
) -> list[EvolutionRun]:
    """Return up to ``limit`` runs ordered by ``created_at DESC``."""
    async with _connect(db_path) as conn, conn.execute(
        "SELECT id FROM evolution_runs ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ) as cur:
        rows = await cur.fetchall()

    runs = []
    for row in rows:
        run = await get_run(row["id"], db_path)
        if run is not None:
            runs.append(run)
    return runs


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------


async def get_lineage(
    run_id: str,
    db_path: Path | None = None,
) -> list[dict]:
    """Return parent→child lineage edges for all genomes in a run.

    Each edge is ``{"parent_id": str, "child_id": str, "generation": int}``.
    Edges are derived from ``skill_genomes.parent_ids`` (a JSON array).
    """
    async with _connect(db_path) as conn, conn.execute(
        "SELECT id, generation, parent_ids FROM skill_genomes WHERE run_id = ?",
        (run_id,),
    ) as cur:
        rows = await cur.fetchall()

    edges: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        child_id = row["id"]
        generation = row["generation"]
        parent_ids: list[str] = json.loads(row["parent_ids"])
        for parent_id in parent_ids:
            key = (parent_id, child_id)
            if key not in seen:
                seen.add(key)
                edges.append(
                    {
                        "parent_id": parent_id,
                        "child_id": child_id,
                        "generation": generation,
                    }
                )
    return edges


async def log_leaked_skill(
    *,
    skill_id: str,
    run_id: str | None,
    error: str | None,
    db_path: Path | None = None,
) -> None:
    """Record a Managed Agents skill that failed to tear down.

    Best-effort: any DB error is swallowed (cleanup must NEVER block the
    evolution loop). The leaked_skills table is read by a future batch
    sweeper that retries deletion. PLAN-V1.2 architectural decision #7.
    """
    import uuid
    from datetime import UTC, datetime

    try:
        async with _connect(db_path) as conn:
            await conn.execute(
                """
                INSERT INTO leaked_skills (id, skill_id, run_id, created_at, error)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    skill_id,
                    run_id,
                    datetime.now(UTC).isoformat(),
                    error,
                ),
            )
            await conn.commit()
    except Exception:  # noqa: BLE001
        pass


async def list_leaked_skills(
    *,
    limit: int = 100,
    db_path: Path | None = None,
) -> list[dict]:
    """Return up to ``limit`` recent leaked skill records as dicts.

    Used by the future batch cleanup job + by tests that verify the
    Managed Agents teardown path logs failures correctly.
    """
    async with _connect(db_path) as conn:
        cursor = await conn.execute(
            """
            SELECT id, skill_id, run_id, created_at, error
            FROM leaked_skills
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        await cursor.close()

    return [dict(r) for r in rows]


async def delete_leaked_skill(
    *,
    leaked_id: str,
    db_path: Path | None = None,
) -> None:
    """Remove a leaked-skill record after a successful retry."""
    async with _connect(db_path) as conn:
        await conn.execute(
            "DELETE FROM leaked_skills WHERE id = ?",
            (leaked_id,),
        )
        await conn.commit()


async def mark_zombie_runs(db_path: Path | None = None) -> int:
    """Mark any 'running'/'pending' runs as failed on startup.

    Called during server lifespan init to clean up runs orphaned by
    a server restart. Returns the count of affected rows.
    """
    async with _connect(db_path) as conn:
        cursor = await conn.execute(
            "UPDATE evolution_runs SET status = 'failed', "
            "failure_reason = 'server restarted while run was in progress' "
            "WHERE status IN ('running', 'pending')"
        )
        await conn.commit()
        return cursor.rowcount


__all__ = [
    "save_run",
    "get_run",
    "list_runs",
    "save_genome",
    "save_generation",
    "save_challenge",
    "save_result",
    "get_lineage",
    "log_leaked_skill",
    "list_leaked_skills",
    "delete_leaked_skill",
    "mark_zombie_runs",
    "save_candidate_seed",
    "list_candidate_seeds",
    "update_candidate_seed_status",
]


# ---------------------------------------------------------------------------
# Candidate seeds
# ---------------------------------------------------------------------------


async def save_candidate_seed(
    *,
    id: str,
    source: str,
    title: str,
    specialization: str,
    skill_md_content: str,
    supporting_files: dict[str, str] | None = None,
    traits: list[str] | None = None,
    category: str = "uncategorized",
    fitness_score: float | None = None,
    source_run_id: str | None = None,
    source_skill_id: str | None = None,
    created_at: str | None = None,
) -> None:
    """Save a candidate seed (AI-generated or evolution winner)."""
    from datetime import UTC, datetime

    async with _connect() as conn:
        await conn.execute(
            """INSERT OR REPLACE INTO candidate_seeds
               (id, source, source_run_id, source_skill_id, title, specialization,
                category, skill_md_content, supporting_files, traits, fitness_score,
                status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (
                id,
                source,
                source_run_id,
                source_skill_id,
                title,
                specialization,
                category,
                skill_md_content,
                json.dumps(supporting_files or {}),
                json.dumps(traits or []),
                fitness_score,
                created_at or datetime.now(UTC).isoformat(),
            ),
        )
        await conn.commit()


async def list_candidate_seeds(status: str | None = None) -> list[dict]:
    """List candidate seeds, optionally filtered by status."""
    async with _connect() as conn:
        if status:
            cur = await conn.execute(
                "SELECT * FROM candidate_seeds WHERE status = ? ORDER BY created_at DESC",
                (status,),
            )
        else:
            cur = await conn.execute(
                "SELECT * FROM candidate_seeds ORDER BY created_at DESC"
            )
        rows = await cur.fetchall()
    return [
        {
            "id": r["id"],
            "source": r["source"],
            "source_run_id": r["source_run_id"],
            "source_skill_id": r["source_skill_id"],
            "title": r["title"],
            "specialization": r["specialization"],
            "category": r["category"],
            "skill_md_content": r["skill_md_content"],
            "supporting_files": json.loads(r["supporting_files"]),
            "traits": json.loads(r["traits"]),
            "fitness_score": r["fitness_score"],
            "status": r["status"],
            "created_at": r["created_at"],
            "promoted_at": r["promoted_at"],
            "notes": r["notes"],
        }
        for r in rows
    ]


async def update_candidate_seed_status(
    id: str, status: str, notes: str | None = None
) -> bool:
    """Update a candidate seed's status. Returns True if found."""
    from datetime import UTC, datetime

    async with _connect() as conn:
        promoted_at = datetime.now(UTC).isoformat() if status == "promoted" else None
        cur = await conn.execute(
            """UPDATE candidate_seeds
               SET status = ?, notes = COALESCE(?, notes), promoted_at = COALESCE(?, promoted_at)
               WHERE id = ?""",
            (status, notes, promoted_at, id),
        )
        await conn.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# v2.0: taxonomy, families, variants, variant evolutions
# ---------------------------------------------------------------------------


def _row_to_taxonomy_node(row: aiosqlite.Row) -> TaxonomyNode:
    return TaxonomyNode.from_dict(
        {
            "id": row["id"],
            "level": row["level"],
            "slug": row["slug"],
            "label": row["label"],
            "parent_id": row["parent_id"],
            "description": row["description"],
            "created_at": row["created_at"],
        }
    )


def _row_to_family(row: aiosqlite.Row) -> SkillFamily:
    return SkillFamily.from_dict(
        {
            "id": row["id"],
            "slug": row["slug"],
            "label": row["label"],
            "specialization": row["specialization"],
            "domain_id": row["domain_id"],
            "focus_id": row["focus_id"],
            "language_id": row["language_id"],
            "tags": json.loads(row["tags"]),
            "decomposition_strategy": row["decomposition_strategy"],
            "best_assembly_id": row["best_assembly_id"],
            "created_at": row["created_at"],
        }
    )


def _row_to_variant(row: aiosqlite.Row) -> Variant:
    return Variant.from_dict(
        {
            "id": row["id"],
            "family_id": row["family_id"],
            "dimension": row["dimension"],
            "tier": row["tier"],
            "genome_id": row["genome_id"],
            "fitness_score": row["fitness_score"],
            "is_active": bool(row["is_active"]),
            "evolution_id": row["evolution_id"],
            "created_at": row["created_at"],
        }
    )


def _row_to_variant_evolution(row: aiosqlite.Row) -> VariantEvolution:
    return VariantEvolution.from_dict(
        {
            "id": row["id"],
            "family_id": row["family_id"],
            "dimension": row["dimension"],
            "tier": row["tier"],
            "parent_run_id": row["parent_run_id"],
            "population_size": row["population_size"],
            "num_generations": row["num_generations"],
            "status": row["status"],
            "winner_variant_id": row["winner_variant_id"],
            "foundation_genome_id": row["foundation_genome_id"],
            "challenge_id": row["challenge_id"],
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
        }
    )


async def save_taxonomy_node(
    node: TaxonomyNode,
    db_path: Path | None = None,
) -> None:
    """Upsert a taxonomy node by id. Idempotent on id conflict."""
    d = node.to_dict()
    async with _connect(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO taxonomy_nodes
                (id, level, slug, label, parent_id, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                level=excluded.level,
                slug=excluded.slug,
                label=excluded.label,
                parent_id=excluded.parent_id,
                description=excluded.description
            """,
            (
                d["id"],
                d["level"],
                d["slug"],
                d["label"],
                d["parent_id"],
                d["description"],
                d["created_at"],
            ),
        )
        await conn.commit()


async def get_taxonomy_node(
    node_id: str,
    db_path: Path | None = None,
) -> TaxonomyNode | None:
    """Fetch a single node by id."""
    async with _connect(db_path) as conn, conn.execute(
        "SELECT * FROM taxonomy_nodes WHERE id = ?", (node_id,)
    ) as cur:
        row = await cur.fetchone()
    return _row_to_taxonomy_node(row) if row is not None else None


async def get_taxonomy_node_by_slug(
    level: str,
    slug: str,
    parent_id: str | None = None,
    db_path: Path | None = None,
) -> TaxonomyNode | None:
    """Fetch a node by its (level, slug, parent_id) natural key.

    ``parent_id`` is compared with ``IS`` semantics so NULL-parent domain rows
    are matched correctly.
    """
    async with _connect(db_path) as conn:
        if parent_id is None:
            query = (
                "SELECT * FROM taxonomy_nodes "
                "WHERE level = ? AND slug = ? AND parent_id IS NULL"
            )
            params: tuple = (level, slug)
        else:
            query = (
                "SELECT * FROM taxonomy_nodes "
                "WHERE level = ? AND slug = ? AND parent_id = ?"
            )
            params = (level, slug, parent_id)
        async with conn.execute(query, params) as cur:
            row = await cur.fetchone()
    return _row_to_taxonomy_node(row) if row is not None else None


async def get_taxonomy_tree(
    db_path: Path | None = None,
) -> list[TaxonomyNode]:
    """Return every taxonomy node as a flat list.

    Callers assemble the tree client-side from ``parent_id`` relationships.
    Ordered by ``level`` (domain → focus → language) then ``slug`` for stable
    display. Cheap query — the taxonomy is small by design.
    """
    level_order = {"domain": 0, "focus": 1, "language": 2}
    async with _connect(db_path) as conn, conn.execute("SELECT * FROM taxonomy_nodes") as cur:
        rows = await cur.fetchall()
    nodes = [_row_to_taxonomy_node(row) for row in rows]
    nodes.sort(key=lambda n: (level_order.get(n.level, 99), n.slug))
    return nodes


async def save_skill_family(
    family: SkillFamily,
    db_path: Path | None = None,
) -> None:
    """Upsert a skill family by id."""
    d = family.to_dict()
    async with _connect(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO skill_families
                (id, slug, label, specialization, domain_id, focus_id,
                 language_id, tags, decomposition_strategy, best_assembly_id,
                 created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                slug=excluded.slug,
                label=excluded.label,
                specialization=excluded.specialization,
                domain_id=excluded.domain_id,
                focus_id=excluded.focus_id,
                language_id=excluded.language_id,
                tags=excluded.tags,
                decomposition_strategy=excluded.decomposition_strategy,
                best_assembly_id=excluded.best_assembly_id
            """,
            (
                d["id"],
                d["slug"],
                d["label"],
                d["specialization"],
                d["domain_id"],
                d["focus_id"],
                d["language_id"],
                json.dumps(d["tags"]),
                d["decomposition_strategy"],
                d["best_assembly_id"],
                d["created_at"],
            ),
        )
        await conn.commit()


async def get_family(
    family_id: str,
    db_path: Path | None = None,
) -> SkillFamily | None:
    """Fetch a single skill family by id."""
    async with _connect(db_path) as conn, conn.execute(
        "SELECT * FROM skill_families WHERE id = ?", (family_id,)
    ) as cur:
        row = await cur.fetchone()
    return _row_to_family(row) if row is not None else None


async def get_family_by_slug(
    slug: str,
    db_path: Path | None = None,
) -> SkillFamily | None:
    """Fetch a family by its slug (unique)."""
    async with _connect(db_path) as conn, conn.execute(
        "SELECT * FROM skill_families WHERE slug = ?", (slug,)
    ) as cur:
        row = await cur.fetchone()
    return _row_to_family(row) if row is not None else None


async def list_families(
    *,
    domain_id: str | None = None,
    focus_id: str | None = None,
    language_id: str | None = None,
    db_path: Path | None = None,
) -> list[SkillFamily]:
    """List families filterable by any taxonomy slot. All args optional.

    Filters compose with AND. Ordered by ``created_at DESC``.
    """
    clauses: list[str] = []
    params: list[str] = []
    if domain_id is not None:
        clauses.append("domain_id = ?")
        params.append(domain_id)
    if focus_id is not None:
        clauses.append("focus_id = ?")
        params.append(focus_id)
    if language_id is not None:
        clauses.append("language_id = ?")
        params.append(language_id)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"SELECT * FROM skill_families{where} ORDER BY created_at DESC"
    async with _connect(db_path) as conn, conn.execute(query, tuple(params)) as cur:
        rows = await cur.fetchall()
    return [_row_to_family(r) for r in rows]


async def save_variant(
    variant: Variant,
    db_path: Path | None = None,
) -> None:
    """Upsert a variant by id. Typical update path rewrites fitness_score +
    is_active, which is why those fields are in the DO UPDATE clause."""
    d = variant.to_dict()
    async with _connect(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO variants
                (id, family_id, dimension, tier, genome_id, fitness_score,
                 is_active, evolution_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                fitness_score=excluded.fitness_score,
                is_active=excluded.is_active,
                evolution_id=excluded.evolution_id
            """,
            (
                d["id"],
                d["family_id"],
                d["dimension"],
                d["tier"],
                d["genome_id"],
                d["fitness_score"],
                _int_or_none(d["is_active"]),
                d["evolution_id"],
                d["created_at"],
            ),
        )
        await conn.commit()


async def get_variants_for_family(
    family_id: str,
    *,
    dimension: str | None = None,
    tier: str | None = None,
    db_path: Path | None = None,
) -> list[Variant]:
    """Return every variant in a family. Optional filter by dimension and tier."""
    clauses = ["family_id = ?"]
    params: list[str] = [family_id]
    if dimension is not None:
        clauses.append("dimension = ?")
        params.append(dimension)
    if tier is not None:
        clauses.append("tier = ?")
        params.append(tier)
    query = (
        f"SELECT * FROM variants WHERE {' AND '.join(clauses)} "
        "ORDER BY fitness_score DESC, created_at DESC"
    )
    async with _connect(db_path) as conn, conn.execute(query, tuple(params)) as cur:
        rows = await cur.fetchall()
    return [_row_to_variant(r) for r in rows]


async def get_active_variants(
    family_id: str,
    db_path: Path | None = None,
) -> list[Variant]:
    """Return the currently-active variants for a family (``is_active=1``).

    Typically one per ``(family_id, dimension)`` — the winner. Ordered by
    tier (foundation first) then dimension for deterministic output.
    """
    tier_order = {"foundation": 0, "capability": 1}
    async with _connect(db_path) as conn, conn.execute(
        "SELECT * FROM variants WHERE family_id = ? AND is_active = 1",
        (family_id,),
    ) as cur:
        rows = await cur.fetchall()
    variants = [_row_to_variant(r) for r in rows]
    variants.sort(key=lambda v: (tier_order.get(v.tier, 99), v.dimension))
    return variants


async def save_variant_evolution(
    evolution: VariantEvolution,
    db_path: Path | None = None,
) -> None:
    """Upsert a variant evolution record by id."""
    d = evolution.to_dict()
    async with _connect(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO variant_evolutions
                (id, family_id, dimension, tier, parent_run_id, population_size,
                 num_generations, status, winner_variant_id, foundation_genome_id,
                 challenge_id, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status=excluded.status,
                winner_variant_id=excluded.winner_variant_id,
                foundation_genome_id=excluded.foundation_genome_id,
                challenge_id=excluded.challenge_id,
                completed_at=excluded.completed_at
            """,
            (
                d["id"],
                d["family_id"],
                d["dimension"],
                d["tier"],
                d["parent_run_id"],
                d["population_size"],
                d["num_generations"],
                d["status"],
                d["winner_variant_id"],
                d["foundation_genome_id"],
                d["challenge_id"],
                d["created_at"],
                d["completed_at"],
            ),
        )
        await conn.commit()


async def get_variant_evolution(
    evolution_id: str,
    db_path: Path | None = None,
) -> VariantEvolution | None:
    """Fetch a variant evolution row by id."""
    async with _connect(db_path) as conn, conn.execute(
        "SELECT * FROM variant_evolutions WHERE id = ?", (evolution_id,)
    ) as cur:
        row = await cur.fetchone()
    return _row_to_variant_evolution(row) if row is not None else None


async def get_variant_evolutions_for_run(
    parent_run_id: str,
    db_path: Path | None = None,
) -> list[VariantEvolution]:
    """Return all variant evolutions created by a parent evolution run."""
    async with _connect(db_path) as conn, conn.execute(
        "SELECT * FROM variant_evolutions WHERE parent_run_id = ? "
        "ORDER BY created_at ASC",
        (parent_run_id,),
    ) as cur:
        rows = await cur.fetchall()
    return [_row_to_variant_evolution(r) for r in rows]
