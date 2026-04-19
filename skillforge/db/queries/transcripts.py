"""CRUD for v2.1.3 dispatch transcripts — full audit trail of every LLM call."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from skillforge.db.queries._helpers import _connect


async def save_transcript(
    *,
    id: str,
    family_slug: str,
    challenge_id: str,
    dispatch_type: str,
    model: str,
    prompt: str,
    raw_response: str,
    extracted_files: dict,
    scores: dict | None = None,
    run_id: str | None = None,
    benchmark_id: str | None = None,
    skill_variant: str | None = None,
    total_tokens: int = 0,
    duration_ms: int = 0,
    error: str | None = None,
    created_at: str | None = None,
    db_path: Path | None = None,
) -> None:
    """Upsert a dispatch transcript row."""

    ts = created_at or datetime.now(UTC).isoformat()
    async with _connect(db_path) as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO dispatch_transcripts
                (id, run_id, benchmark_id, family_slug, challenge_id,
                 dispatch_type, model, skill_variant, prompt, raw_response,
                 extracted_files, scores, total_tokens, duration_ms,
                 error, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id,
                run_id,
                benchmark_id,
                family_slug,
                challenge_id,
                dispatch_type,
                model,
                skill_variant,
                prompt,
                raw_response,
                json.dumps(extracted_files),
                json.dumps(scores or {}),
                total_tokens,
                duration_ms,
                error,
                ts,
            ),
        )
        await conn.commit()


async def get_transcripts_for_challenge(
    challenge_id: str,
    db_path: Path | None = None,
) -> list[dict]:
    """Return all dispatch transcripts for a given challenge."""
    async with _connect(db_path) as conn, conn.execute(
        "SELECT * FROM dispatch_transcripts WHERE challenge_id = ? "
        "ORDER BY created_at ASC",
        (challenge_id,),
    ) as cur:
        rows = await cur.fetchall()
    return [
        {
            "id": r["id"],
            "run_id": r["run_id"],
            "benchmark_id": r["benchmark_id"],
            "family_slug": r["family_slug"],
            "challenge_id": r["challenge_id"],
            "dispatch_type": r["dispatch_type"],
            "model": r["model"],
            "skill_variant": r["skill_variant"],
            "extracted_files": json.loads(r["extracted_files"]),
            "scores": json.loads(r["scores"]),
            "total_tokens": r["total_tokens"],
            "duration_ms": r["duration_ms"],
            "error": r["error"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


async def get_transcripts_for_family(
    family_slug: str,
    dispatch_type: str | None = None,
    db_path: Path | None = None,
) -> list[dict]:
    """Return all dispatch transcripts for a family, optionally filtered by type."""
    query = "SELECT * FROM dispatch_transcripts WHERE family_slug = ?"
    params: list = [family_slug]
    if dispatch_type:
        query += " AND dispatch_type = ?"
        params.append(dispatch_type)
    query += " ORDER BY created_at ASC"
    async with _connect(db_path) as conn, conn.execute(query, params) as cur:
        rows = await cur.fetchall()
    return [
        {
            "id": r["id"],
            "challenge_id": r["challenge_id"],
            "dispatch_type": r["dispatch_type"],
            "model": r["model"],
            "skill_variant": r["skill_variant"],
            "scores": json.loads(r["scores"]),
            "total_tokens": r["total_tokens"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
