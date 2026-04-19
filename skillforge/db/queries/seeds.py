"""CRUD for curated candidate-seed rows (user-saved or auto-saved skills).

Seeds are a user-facing registry: a pool of skill packages surfaced in the
"Start from a seed" UI. Distinct from the immutable ``SEED_SKILLS`` list in
``skillforge.seeds`` — those are the on-disk golden-template examples;
these are database rows that can be filtered/approved/rejected over time.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from skillforge.db.queries._helpers import _connect


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

