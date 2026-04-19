"""Idempotent loader for the SKLD-bench baseline.

On boot, if ``benchmark_results`` is empty (fresh container, no prior
ingestion), replay ``skillforge/seeds/benchmark_results.json`` into the
table. Non-empty tables are left alone so real runs written from the app
are never overwritten.

Regenerate the JSON by running locally:
    uv run python scripts/export_benchmark_results.py
"""

from __future__ import annotations

import json
import logging

import aiosqlite

from skillforge.config import DB_PATH, ROOT_DIR

logger = logging.getLogger("skillforge.benchmark_seed")

SEED_PATH = ROOT_DIR / "skillforge" / "seeds" / "benchmark_results.json"

_COLUMNS = [
    "id",
    "family_slug",
    "challenge_id",
    "challenge_path",
    "model",
    "tier",
    "dimension",
    "score",
    "passed",
    "objectives",
    "output_files",
    "total_tokens",
    "duration_ms",
    "error",
    "created_at",
    "scores",
]


async def load_benchmark_results() -> dict:
    """Seed benchmark_results from disk if the table is empty.

    Returns a small diagnostic dict for structured logging.
    """
    if not SEED_PATH.exists():
        logger.info("No benchmark seed at %s; skipping", SEED_PATH)
        return {"loaded": 0, "skipped_reason": "no-seed-file"}

    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute("SELECT COUNT(*) FROM benchmark_results")
        (existing,) = await cur.fetchone()
        if existing > 0:
            return {"loaded": 0, "skipped_reason": "table-non-empty", "existing": existing}

        try:
            records = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("Failed to parse benchmark seed")
            return {"loaded": 0, "skipped_reason": "parse-error"}

        if not isinstance(records, list) or not records:
            return {"loaded": 0, "skipped_reason": "empty-seed"}

        placeholders = ", ".join(["?"] * len(_COLUMNS))
        sql = (
            f"INSERT OR IGNORE INTO benchmark_results ({', '.join(_COLUMNS)}) "
            f"VALUES ({placeholders})"
        )
        values = [
            tuple(rec.get(col) for col in _COLUMNS) for rec in records
        ]
        await conn.executemany(sql, values)
        await conn.commit()

    logger.info("Seeded benchmark_results with %d rows from %s", len(records), SEED_PATH.name)
    return {"loaded": len(records)}
