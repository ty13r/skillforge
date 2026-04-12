"""SKLD-bench baseline report generator.

Reads benchmark_results from the DB and produces summary statistics.

Usage:
    uv run python scripts/benchmark/benchmark_report.py
    uv run python scripts/benchmark/benchmark_report.py --family elixir-ecto-schema-changeset
    uv run python scripts/benchmark/benchmark_report.py --model claude-sonnet-4-6
    uv run python scripts/benchmark/benchmark_report.py --format json
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from pathlib import Path

import aiosqlite

from skillforge.config import DB_PATH


async def load_results(
    db_path: Path,
    family: str | None = None,
    model: str | None = None,
) -> list[dict]:
    """Load benchmark results from DB with optional filters."""
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        query = "SELECT * FROM benchmark_results WHERE 1=1"
        params = []
        if family:
            query += " AND family_slug = ?"
            params.append(family)
        if model:
            query += " AND model = ?"
            params.append(model)
        query += " ORDER BY family_slug, tier, challenge_id"

        async with conn.execute(query, params) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


def generate_report(results: list[dict]) -> dict:
    """Generate summary statistics from benchmark results."""
    if not results:
        return {"error": "no results found"}

    # Group by model
    by_model: dict[str, list] = defaultdict(list)
    for r in results:
        by_model[r["model"]].append(r)

    report = {"models": {}, "total_results": len(results)}

    for model, model_results in sorted(by_model.items()):
        # Overall
        scores = [r["score"] for r in model_results]
        passed = sum(1 for r in model_results if r["passed"])
        avg = sum(scores) / len(scores) if scores else 0

        # By family
        by_family: dict[str, list] = defaultdict(list)
        for r in model_results:
            by_family[r["family_slug"]].append(r)

        family_stats = {}
        for fam, fam_results in sorted(by_family.items()):
            fam_scores = [r["score"] for r in fam_results]
            fam_passed = sum(1 for r in fam_results if r["passed"])
            family_stats[fam] = {
                "count": len(fam_results),
                "avg_score": round(sum(fam_scores) / len(fam_scores), 4),
                "pass_rate": round(fam_passed / len(fam_results), 4),
                "min": round(min(fam_scores), 4),
                "max": round(max(fam_scores), 4),
            }

        # By tier
        by_tier: dict[str, list] = defaultdict(list)
        for r in model_results:
            by_tier[r["tier"]].append(r)

        tier_stats = {}
        for t in ["easy", "medium", "hard", "legendary"]:
            if t not in by_tier:
                continue
            t_scores = [r["score"] for r in by_tier[t]]
            t_passed = sum(1 for r in by_tier[t] if r["passed"])
            tier_stats[t] = {
                "count": len(by_tier[t]),
                "avg_score": round(sum(t_scores) / len(t_scores), 4),
                "pass_rate": round(t_passed / len(by_tier[t]), 4),
            }

        # By dimension
        by_dim: dict[str, list] = defaultdict(list)
        for r in model_results:
            by_dim[r["dimension"]].append(r)

        dim_stats = {}
        for dim, dim_results in sorted(by_dim.items()):
            dim_scores = [r["score"] for r in dim_results]
            dim_stats[dim] = {
                "count": len(dim_results),
                "avg_score": round(sum(dim_scores) / len(dim_scores), 4),
            }

        # Hardest challenges (bottom 10)
        sorted_by_score = sorted(model_results, key=lambda r: r["score"])
        hardest = [
            {"id": r["challenge_id"], "score": r["score"], "tier": r["tier"], "family": r["family_slug"]}
            for r in sorted_by_score[:10]
        ]

        # Easiest (all perfect scores)
        perfect = sum(1 for r in model_results if r["score"] >= 0.999)

        # Zero scores (potential scorer bugs)
        zeros = [
            {"id": r["challenge_id"], "tier": r["tier"], "family": r["family_slug"]}
            for r in model_results if r["score"] == 0.0
        ]

        report["models"][model] = {
            "total": len(model_results),
            "avg_score": round(avg, 4),
            "pass_rate": round(passed / len(model_results), 4),
            "perfect_scores": perfect,
            "zero_scores": len(zeros),
            "by_family": family_stats,
            "by_tier": tier_stats,
            "by_dimension": dim_stats,
            "hardest_10": hardest,
            "zero_score_challenges": zeros[:20],
        }

    # Model comparison (if 2+ models)
    if len(by_model) >= 2:
        models = sorted(by_model.keys())
        m1, m2 = models[0], models[1]
        m1_by_ch = {r["challenge_id"]: r["score"] for r in by_model[m1]}
        m2_by_ch = {r["challenge_id"]: r["score"] for r in by_model[m2]}
        common = set(m1_by_ch) & set(m2_by_ch)

        if common:
            deltas = [(ch, m2_by_ch[ch] - m1_by_ch[ch]) for ch in common]
            avg_delta = sum(d for _, d in deltas) / len(deltas)
            m2_wins = sum(1 for _, d in deltas if d > 0.01)
            m1_wins = sum(1 for _, d in deltas if d < -0.01)
            ties = len(common) - m2_wins - m1_wins

            report["comparison"] = {
                "models": [m1, m2],
                "common_challenges": len(common),
                "avg_delta": round(avg_delta, 4),
                f"{m2}_wins": m2_wins,
                f"{m1}_wins": m1_wins,
                "ties": ties,
            }

    return report


def print_markdown(report: dict) -> None:
    """Print report as formatted markdown."""
    print("# SKLD-bench Baseline Report\n")

    for model, stats in report.get("models", {}).items():
        print(f"## {model}\n")
        print(f"- **Challenges**: {stats['total']}")
        print(f"- **Avg Score**: {stats['avg_score']}")
        print(f"- **Pass Rate**: {stats['pass_rate']:.1%}")
        print(f"- **Perfect Scores**: {stats['perfect_scores']}")
        print(f"- **Zero Scores**: {stats['zero_scores']}")

        print(f"\n### By Tier\n")
        print("| Tier | Count | Avg Score | Pass Rate |")
        print("|------|-------|-----------|-----------|")
        for t, ts in stats.get("by_tier", {}).items():
            print(f"| {t} | {ts['count']} | {ts['avg_score']} | {ts['pass_rate']:.1%} |")

        print(f"\n### By Family\n")
        print("| Family | Count | Avg Score | Pass Rate | Min | Max |")
        print("|--------|-------|-----------|-----------|-----|-----|")
        for fam, fs in stats.get("by_family", {}).items():
            short = fam.replace("elixir-", "")
            print(f"| {short} | {fs['count']} | {fs['avg_score']} | {fs['pass_rate']:.1%} | {fs['min']} | {fs['max']} |")

        if stats.get("hardest_10"):
            print(f"\n### Hardest 10 Challenges\n")
            print("| Challenge | Score | Tier | Family |")
            print("|-----------|-------|------|--------|")
            for h in stats["hardest_10"]:
                print(f"| {h['id']} | {h['score']} | {h['tier']} | {h['family'].replace('elixir-', '')} |")

        if stats.get("zero_score_challenges"):
            print(f"\n### Zero-Score Challenges ({stats['zero_scores']} total)\n")
            for z in stats["zero_score_challenges"]:
                print(f"- `{z['id']}` ({z['tier']}, {z['family']})")

    if "comparison" in report:
        c = report["comparison"]
        print(f"\n## Model Comparison: {c['models'][0]} vs {c['models'][1]}\n")
        print(f"- Common challenges: {c['common_challenges']}")
        print(f"- Avg delta ({c['models'][1]} - {c['models'][0]}): {c['avg_delta']:+.4f}")


async def main():
    parser = argparse.ArgumentParser(description="SKLD-bench report")
    parser.add_argument("--family")
    parser.add_argument("--model")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()

    results = await load_results(DB_PATH, args.family, args.model)
    report = generate_report(results)

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print_markdown(report)


if __name__ == "__main__":
    asyncio.run(main())
