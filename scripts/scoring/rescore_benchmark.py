#!/usr/bin/env python3
"""Re-score benchmark_results and dispatch_transcripts with the composite scorer.

Reads stored output_files/extracted_files, runs them through composite_scorer,
and updates the `scores` JSON column without re-dispatching.

Usage:
    uv run python scripts/scoring/rescore_benchmark.py \
        --family elixir-phoenix-liveview \
        [--table benchmark_results|dispatch_transcripts|both] \
        [--limit 10] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from skillforge.config import DB_PATH
from skillforge.db.database import init_db

import aiosqlite

# Import composite scorer
sys.path.insert(0, str(Path(__file__).resolve().parent))
from composite_scorer import composite_score, WEIGHTS_PHASE2

TAXONOMY_BASE = Path(__file__).resolve().parent.parent.parent / "taxonomy" / "elixir"


def find_challenge_path(family_slug: str, challenge_id: str) -> Path | None:
    """Locate the challenge JSON file on disk from the challenge_id."""
    family_dir = TAXONOMY_BASE / family_slug / "challenges"
    for tier_dir in family_dir.iterdir():
        if tier_dir.is_dir():
            candidate = tier_dir / f"{challenge_id}.json"
            if candidate.exists():
                return candidate
    return None


async def rescore_benchmark_results(
    family_slug: str,
    limit: int | None = None,
    dry_run: bool = False,
    behavioral: bool = False,
) -> dict:
    """Re-score all benchmark_results rows for a family."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        query = "SELECT * FROM benchmark_results WHERE family_slug = ? ORDER BY challenge_id"
        async with conn.execute(query, (family_slug,)) as cur:
            rows = await cur.fetchall()

    total = len(rows)
    if limit:
        rows = rows[:limit]

    scored = 0
    errors = 0
    compile_failures = 0

    for i, row in enumerate(rows):
        challenge_id = row["challenge_id"]
        challenge_path = find_challenge_path(family_slug, challenge_id)

        if not challenge_path:
            print(f"  [{i+1}/{len(rows)}] SKIP {challenge_id}: challenge file not found")
            errors += 1
            continue

        # Parse stored output files
        try:
            output_files = json.loads(row["output_files"])
        except json.JSONDecodeError:
            print(f"  [{i+1}/{len(rows)}] SKIP {challenge_id}: bad output_files JSON")
            errors += 1
            continue

        if not output_files:
            print(f"  [{i+1}/{len(rows)}] SKIP {challenge_id}: empty output_files")
            errors += 1
            continue

        # Run composite scorer
        try:
            result = composite_score(
                family_slug, challenge_path, output_files,
                run_behavioral_tests=behavioral,
                weights=WEIGHTS_PHASE2 if behavioral else None,
            )
        except Exception as e:
            print(f"  [{i+1}/{len(rows)}] ERROR {challenge_id}: {e}")
            errors += 1
            continue

        if not result["compile"]["compiles"]:
            compile_failures += 1

        if dry_run:
            print(f"  [{i+1}/{len(rows)}] {challenge_id}: "
                  f"composite={result['composite']:.4f} "
                  f"(L0={result['l0']['score']:.4f}, "
                  f"compile={'✓' if result['compile']['compiles'] else '✗'}, "
                  f"ast={result['ast']['score']:.4f})")
        else:
            # Update the scores column
            scores_json = json.dumps(result)
            async with aiosqlite.connect(DB_PATH) as conn:
                await conn.execute(
                    "UPDATE benchmark_results SET scores = ? WHERE id = ?",
                    (scores_json, row["id"]),
                )
                await conn.commit()

            if (i + 1) % 20 == 0 or (i + 1) == len(rows):
                print(f"  [{i+1}/{len(rows)}] scored... "
                      f"(last: {challenge_id} = {result['composite']:.4f})")

        scored += 1

    return {
        "total": total,
        "scored": scored,
        "errors": errors,
        "compile_failures": compile_failures,
    }


async def rescore_dispatch_transcripts(
    family_slug: str,
    limit: int | None = None,
    dry_run: bool = False,
    behavioral: bool = False,
) -> dict:
    """Re-score all dispatch_transcripts rows for a family."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        query = "SELECT * FROM dispatch_transcripts WHERE family_slug = ? ORDER BY challenge_id"
        async with conn.execute(query, (family_slug,)) as cur:
            rows = await cur.fetchall()

    if limit:
        rows = rows[:limit]

    scored = 0
    errors = 0

    for i, row in enumerate(rows):
        challenge_id = row["challenge_id"]
        challenge_path = find_challenge_path(family_slug, challenge_id)

        if not challenge_path:
            print(f"  [{i+1}/{len(rows)}] SKIP {challenge_id}: challenge file not found")
            errors += 1
            continue

        try:
            output_files = json.loads(row["extracted_files"])
        except json.JSONDecodeError:
            errors += 1
            continue

        if not output_files:
            errors += 1
            continue

        try:
            result = composite_score(
                family_slug, challenge_path, output_files,
                run_behavioral_tests=behavioral,
                weights=WEIGHTS_PHASE2 if behavioral else None,
            )
        except Exception as e:
            print(f"  [{i+1}/{len(rows)}] ERROR {challenge_id}: {e}")
            errors += 1
            continue

        source = f"{row['model'].split('-')[1]}-{row['skill_variant'] or 'noskill'}"

        if dry_run:
            print(f"  [{i+1}/{len(rows)}] {source} × {challenge_id}: "
                  f"composite={result['composite']:.4f} "
                  f"(compile={'✓' if result['compile']['compiles'] else '✗'})")
        else:
            scores_json = json.dumps(result)
            async with aiosqlite.connect(DB_PATH) as conn:
                await conn.execute(
                    "UPDATE dispatch_transcripts SET scores = ? WHERE id = ?",
                    (scores_json, row["id"]),
                )
                await conn.commit()

            print(f"  [{i+1}/{len(rows)}] {source} × {challenge_id}: "
                  f"composite={result['composite']:.4f}")

        scored += 1

    return {"scored": scored, "errors": errors}


async def main(args):
    await init_db()

    if args.table in ("dispatch_transcripts", "both"):
        print(f"\n=== Re-scoring dispatch_transcripts for {args.family} ===")
        dt_result = await rescore_dispatch_transcripts(
            args.family, args.limit, args.dry_run, behavioral=args.behavioral)
        print(f"  Done: {dt_result['scored']} scored, {dt_result['errors']} errors")

    if args.table in ("benchmark_results", "both"):
        print(f"\n=== Re-scoring benchmark_results for {args.family} ===")
        br_result = await rescore_benchmark_results(
            args.family, args.limit, args.dry_run, behavioral=args.behavioral)
        print(f"  Done: {br_result['scored']}/{br_result['total']} scored, "
              f"{br_result['errors']} errors, "
              f"{br_result['compile_failures']} compile failures")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-score stored outputs with composite scorer")
    parser.add_argument("--family", required=True, help="Family slug")
    parser.add_argument("--table", default="both",
                        choices=["benchmark_results", "dispatch_transcripts", "both"])
    parser.add_argument("--limit", type=int, help="Limit number of rows to score")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--behavioral", action="store_true",
                        help="Run generic behavioral tests (Phase 2 weights)")
    args = parser.parse_args()
    asyncio.run(main(args))
