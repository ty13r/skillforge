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
    SkillGenome,
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
                 trait_attribution, trait_diagnostics, consistency_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                consistency_score=excluded.consistency_score
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

    # Step 1: insert/replace the run row with best_skill_id = NULL to avoid
    # FK violation (the referenced genome may not exist yet).
    async with _connect(db_path) as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO evolution_runs
                (id, mode, specialization, population_size, num_generations,
                 status, created_at, completed_at, total_cost_usd, max_budget_usd,
                 learning_log, pareto_front_ids, best_skill_id, failure_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
]
