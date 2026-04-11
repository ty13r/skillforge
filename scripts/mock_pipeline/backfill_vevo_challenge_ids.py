"""Backfill missing ``variant_evolutions.challenge_id`` values.

The original ``persist_variant.py`` set ``vevo.challenge_id`` before calling
``save_variant_evolution``, but some path (possibly the JSON-seed roundtrip
that happened later) lost the value. All 12 vevos for the mock run now have
NULL challenge_ids in the DB.

Fix: for each dimension, find the first sampled challenge from
``/tmp/skld-mock-run/capabilities/<dim>/challenges.json`` (or
``/tmp/skld-mock-run/architectural-stance/challenges.json`` for the
foundation) and UPDATE the corresponding vevo row directly via SQL.

Usage:
    uv run python scripts/mock_pipeline/backfill_vevo_challenge_ids.py \\
        --run-id elixir-phoenix-liveview-mock-v1

Prints a summary of how many vevos were updated.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import aiosqlite

from skillforge.config import DB_PATH

CAPABILITY_DIMS = [
    "heex-and-verified-routes",
    "function-components-and-slots",
    "live-components-stateful",
    "form-handling",
    "streams-and-collections",
    "mount-and-lifecycle",
    "event-handlers-and-handle-info",
    "pubsub-and-realtime",
    "navigation-patterns",
    "auth-and-authz",
    "anti-patterns-catalog",
]
FOUNDATION_DIM = "architectural-stance"

MOCK_ROOT = Path("/tmp/skld-mock-run")


def _challenges_path_for(dim: str) -> Path:
    if dim == FOUNDATION_DIM:
        return MOCK_ROOT / FOUNDATION_DIM / "challenges.json"
    return MOCK_ROOT / "capabilities" / dim / "challenges.json"


def _first_challenge_id(dim: str) -> str | None:
    p = _challenges_path_for(dim)
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    if not data:
        return None
    return data[0].get("id")


async def backfill(run_id: str) -> dict:
    updated: dict[str, str] = {}
    missing: list[str] = []

    all_dims = [FOUNDATION_DIM, *CAPABILITY_DIMS]
    async with aiosqlite.connect(DB_PATH) as conn:
        for dim in all_dims:
            ch_id = _first_challenge_id(dim)
            if ch_id is None:
                missing.append(dim)
                continue
            result = await conn.execute(
                "UPDATE variant_evolutions SET challenge_id = ? "
                "WHERE parent_run_id = ? AND dimension = ?",
                (ch_id, run_id, dim),
            )
            if result.rowcount > 0:
                updated[dim] = ch_id
        await conn.commit()

    return {
        "run_id": run_id,
        "updated_count": len(updated),
        "updated": updated,
        "missing_challenge_files": missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    result = asyncio.run(backfill(args.run_id))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
