"""Append a reconstructed Engineer integration report into ``run.learning_log``.

The mock pipeline's original Engineer dispatch produced an integration report
(conflicts detected/resolved + decision notes) in its subagent output, but
that content was never persisted to the DB — it lived only in the parent
session's context and was lost to compaction. This helper takes a post-facto
markdown reconstruction and appends it as a single multi-line entry to
``evolution_runs.learning_log``, prefixed with ``[integration_report]`` so
the frontend can detect it and render as a collapsible Markdown block.

Idempotent: if an entry already starts with ``[integration_report]``, it's
replaced in place.

Usage:
    uv run python scripts/mock_pipeline/persist_integration_report.py \\
        --run-id elixir-phoenix-liveview-mock-v1 \\
        --report-path /tmp/skld-mock-run/integration_report.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import aiosqlite

from skillforge.config import DB_PATH

INTEGRATION_REPORT_PREFIX = "[integration_report] "


async def persist(run_id: str, report_path: Path) -> dict:
    markdown = report_path.read_text()
    payload = f"{INTEGRATION_REPORT_PREFIX}{markdown}"

    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            "SELECT learning_log FROM evolution_runs WHERE id = ?",
            (run_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            raise RuntimeError(f"Run {run_id} not found")

        try:
            log: list[str] = json.loads(row[0]) if row[0] else []
        except (TypeError, json.JSONDecodeError):
            log = []

        # Replace any existing integration_report entry in place.
        new_log = [e for e in log if not e.startswith(INTEGRATION_REPORT_PREFIX)]
        new_log.append(payload)

        await conn.execute(
            "UPDATE evolution_runs SET learning_log = ? WHERE id = ?",
            (json.dumps(new_log), run_id),
        )
        await conn.commit()

    return {
        "run_id": run_id,
        "entries_before": len(log),
        "entries_after": len(new_log),
        "integration_report_bytes": len(payload),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--report-path", required=True, type=Path)
    args = parser.parse_args()

    result = asyncio.run(persist(args.run_id, args.report_path))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
