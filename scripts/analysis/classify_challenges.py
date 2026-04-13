#!/usr/bin/env python3
"""Classify SKLD-bench challenges by discriminating power.

Uses scored benchmark_results to compute headroom, compile gate rate,
and score spread per challenge, then classifies each as:
- discriminating: headroom > 0.15 (real room for skill improvement)
- calibration: headroom 0.05-0.15 (marginal improvement possible)
- noise: headroom < 0.05 (model already aces it)
- broken: scorer crashes or returns invalid data

Usage:
    uv run python scripts/analysis/classify_challenges.py \
        [--family elixir-phoenix-liveview] [--all]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from skillforge.config import DB_PATH
from skillforge.db.database import init_db

import aiosqlite

FAMILIES = [
    "elixir-phoenix-liveview",
    "elixir-ecto-sandbox-test",
    "elixir-security-linter",
    "elixir-oban-worker",
    "elixir-ecto-schema-changeset",
    "elixir-ecto-query-writer",
    "elixir-pattern-match-refactor",
]


async def classify_family(family_slug: str) -> dict:
    """Classify challenges for a single family."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT challenge_id, tier, score, scores FROM benchmark_results "
            "WHERE family_slug = ? ORDER BY challenge_id",
            (family_slug,),
        ) as cur:
            rows = await cur.fetchall()

    classifications = {
        "discriminating": [],
        "calibration": [],
        "noise": [],
        "broken": [],
    }
    stats = {
        "total": len(rows),
        "has_composite": 0,
        "compile_failures": 0,
        "behavioral_failures": 0,
    }

    for row in rows:
        cid = row["challenge_id"]
        tier = row["tier"]
        l0_score = row["score"]

        scores_raw = row["scores"] if "scores" in row.keys() else "{}"
        try:
            scores = json.loads(scores_raw) if scores_raw else {}
        except json.JSONDecodeError:
            classifications["broken"].append({
                "id": cid, "tier": tier, "reason": "invalid scores JSON"
            })
            continue

        if not scores or "composite" not in scores:
            # No composite score — use L0 as fallback
            composite = l0_score
            has_composite = False
        else:
            composite = scores["composite"]
            has_composite = True
            stats["has_composite"] += 1

        # Check compile status
        compile_info = scores.get("compile", {})
        if not compile_info.get("compiles", True):
            stats["compile_failures"] += 1

        # Check behavioral status
        beh = scores.get("behavioral")
        if beh and beh.get("total", 0) > 0 and beh.get("passed", 0) < beh.get("total", 0):
            stats["behavioral_failures"] += 1

        # Compute headroom
        headroom = 1.0 - composite

        entry = {
            "id": cid,
            "tier": tier,
            "l0": round(l0_score, 4),
            "composite": round(composite, 4),
            "headroom": round(headroom, 4),
            "compiles": compile_info.get("compiles", True) if compile_info else True,
        }

        if headroom > 0.15:
            entry["category"] = "discriminating"
            classifications["discriminating"].append(entry)
        elif headroom >= 0.05:
            entry["category"] = "calibration"
            classifications["calibration"].append(entry)
        else:
            entry["category"] = "noise"
            classifications["noise"].append(entry)

    # Sort discriminating by headroom (most headroom first)
    classifications["discriminating"].sort(key=lambda x: -x["headroom"])
    classifications["calibration"].sort(key=lambda x: -x["headroom"])

    return {
        "family": family_slug,
        "stats": stats,
        "classifications": classifications,
        "summary": {
            "discriminating": len(classifications["discriminating"]),
            "calibration": len(classifications["calibration"]),
            "noise": len(classifications["noise"]),
            "broken": len(classifications["broken"]),
        },
    }


async def main(args):
    await init_db()

    families = FAMILIES if args.all else [args.family]

    all_results = {}
    totals = {"discriminating": 0, "calibration": 0, "noise": 0, "broken": 0}

    for family in families:
        result = await classify_family(family)
        all_results[family] = result

        s = result["summary"]
        totals["discriminating"] += s["discriminating"]
        totals["calibration"] += s["calibration"]
        totals["noise"] += s["noise"]
        totals["broken"] += s["broken"]

        print(f"\n=== {family} ({result['stats']['total']} challenges) ===")
        print(f"  Discriminating: {s['discriminating']:3d}  "
              f"Calibration: {s['calibration']:3d}  "
              f"Noise: {s['noise']:3d}  "
              f"Broken: {s['broken']:3d}")

        if result["stats"]["has_composite"] > 0:
            print(f"  Composite scores: {result['stats']['has_composite']}/{result['stats']['total']}")
            print(f"  Compile failures: {result['stats']['compile_failures']}")
            print(f"  Behavioral failures: {result['stats']['behavioral_failures']}")
        else:
            print(f"  (L0 scores only — no composite yet)")

        # Show top 5 discriminating
        disc = result["classifications"]["discriminating"][:5]
        if disc:
            print(f"  Top discriminating:")
            for d in disc:
                print(f"    {d['id']}: composite={d['composite']:.3f} headroom={d['headroom']:.3f}")

    if len(families) > 1:
        total_challenges = sum(r["stats"]["total"] for r in all_results.values())
        print(f"\n=== TOTALS ({total_challenges} challenges across {len(families)} families) ===")
        print(f"  Discriminating: {totals['discriminating']}")
        print(f"  Calibration:    {totals['calibration']}")
        print(f"  Noise:          {totals['noise']}")
        print(f"  Broken:         {totals['broken']}")

    # Save full results
    if args.output:
        Path(args.output).write_text(json.dumps(all_results, indent=2))
        print(f"\nFull results saved to {args.output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Classify SKLD-bench challenges")
    parser.add_argument("--family", default="elixir-phoenix-liveview")
    parser.add_argument("--all", action="store_true", help="Classify all 7 families")
    parser.add_argument("--output", help="Save full JSON results to file")
    args = parser.parse_args()
    asyncio.run(main(args))
