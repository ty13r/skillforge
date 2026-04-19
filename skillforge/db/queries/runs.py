"""CRUD for EvolutionRun rows + related ops (lineage, leaked skills, zombies).

All grouped here because they're top-level operations on a run or a run's
genealogy. The Challenge / Generation / Genome / Result rows a run owns
live in other submodules.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from skillforge.db.queries._helpers import _connect, _row_get
from skillforge.db.queries.challenges import _get_challenges_for_run, save_challenge
from skillforge.db.queries.genomes import (
    _get_generations_for_run,
    _get_genome_by_id,
    save_generation,
    save_genome,
)
from skillforge.models import EvolutionRun, SkillGenome


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


