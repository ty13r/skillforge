"""One-shot dumper for benchmark_results → skillforge/seeds/benchmark_results.json.

Run locally whenever you want the prod baseline refreshed:

    uv run python scripts/export_benchmark_results.py

Commit the resulting JSON; the startup loader in
``skillforge/db/benchmark_seed_loader.py`` will replay it on any
environment whose ``benchmark_results`` table is empty.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiosqlite

from skillforge.config import DB_PATH, ROOT_DIR

OUT_PATH = ROOT_DIR / "skillforge" / "seeds" / "benchmark_results.json"

COLUMNS = [
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


async def main() -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM benchmark_results ORDER BY family_slug, model, challenge_id"
        )
        rows = await cur.fetchall()

    records = [dict(zip(COLUMNS, row)) for row in rows]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(records)} rows → {OUT_PATH.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    asyncio.run(main())
