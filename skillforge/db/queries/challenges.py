"""CRUD for Challenge rows (evaluation challenges produced by the challenge designer)."""

from __future__ import annotations

import json
from pathlib import Path

import aiosqlite

from skillforge.db.queries._helpers import _connect
from skillforge.models import Challenge


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
