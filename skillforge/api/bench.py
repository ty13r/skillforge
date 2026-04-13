"""SKLD-bench API endpoints.

Serves benchmark data from the ``benchmark_results`` table:
- ``GET /api/bench/summary`` — per-family aggregate stats + scoring progression
- ``GET /api/bench/{family_slug}`` — challenge-level detail for one family
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException

from skillforge.db.queries import _connect

logger = logging.getLogger("skillforge.api.bench")

router = APIRouter(prefix="/api/bench", tags=["bench"])

# The two model tags we compare: raw Sonnet vs Sonnet + seed skill
RAW_MODEL = "claude-sonnet-4-6"
SKILL_MODEL = "claude-sonnet-4-6+seed-v1"


def _parse_scores(scores_json: str) -> dict:
    """Parse the scores JSON column, returning empty dict on failure."""
    if not scores_json:
        return {}
    try:
        return json.loads(scores_json)
    except (json.JSONDecodeError, TypeError):
        return {}


def _safe_div(a: float, b: float) -> float | None:
    """Safe division returning None if denominator is zero."""
    return round(a / b, 4) if b else None


@router.get("/summary")
async def bench_summary() -> dict:
    """Per-family aggregate stats + overall + scoring progression.

    Returns the main SKLD-bench scoreboard data.
    """
    async with _connect() as conn:
        conn.row_factory = None  # use tuple rows for speed
        cursor = await conn.execute(
            "SELECT family_slug, model, tier, score, scores "
            "FROM benchmark_results ORDER BY family_slug, model"
        )
        rows = await cursor.fetchall()

    # Accumulate per (family, model) stats
    # row: (family_slug, model, tier, l0_score, scores_json)
    family_model: dict[tuple[str, str], dict] = {}
    # Also accumulate overall scoring progression (raw model only)
    all_l0 = []
    all_compile = []
    all_ast = []
    all_behavioral = []
    all_template = []
    all_brevity = []
    all_composite = []

    for family_slug, model, tier, l0_score, scores_json in rows:
        key = (family_slug, model)
        if key not in family_model:
            family_model[key] = {
                "challenges": 0,
                "l0_sum": 0.0,
                "composite_sum": 0.0,
                "compile_pass": 0,
                "behavioral_sum": 0.0,
                "has_scores": 0,
                "tiers": {},
            }

        bucket = family_model[key]
        bucket["challenges"] += 1
        bucket["l0_sum"] += l0_score or 0.0

        scores = _parse_scores(scores_json)
        if scores.get("composite") is not None:
            bucket["composite_sum"] += scores["composite"]
            bucket["has_scores"] += 1

            compile_val = scores.get("compile", {})
            if isinstance(compile_val, dict) and compile_val.get("compiles"):
                bucket["compile_pass"] += 1

            behavioral = scores.get("behavioral", {})
            if isinstance(behavioral, dict):
                bucket["behavioral_sum"] += behavioral.get("score", 0.0)

            # Tier tracking
            if tier not in bucket["tiers"]:
                bucket["tiers"][tier] = {"count": 0, "composite_sum": 0.0}
            bucket["tiers"][tier]["count"] += 1
            bucket["tiers"][tier]["composite_sum"] += scores["composite"]

            # Overall scoring progression (raw model only)
            if model == RAW_MODEL:
                all_l0.append(scores.get("l0", {}).get("score", l0_score or 0))
                all_compile.append(
                    1.0
                    if isinstance(compile_val, dict) and compile_val.get("compiles")
                    else 0.0
                )
                ast = scores.get("ast", {})
                all_ast.append(ast.get("score", 0.0) if isinstance(ast, dict) else 0.0)
                beh = scores.get("behavioral", {})
                all_behavioral.append(
                    beh.get("score", 0.0) if isinstance(beh, dict) else 0.0
                )
                tmpl = scores.get("template", {})
                all_template.append(tmpl.get("score", 0.0) if isinstance(tmpl, dict) else float(tmpl or 0))
                all_brevity.append(float(scores.get("brevity", 0.0) or 0))
                all_composite.append(scores["composite"])

    # Build family list
    families = []
    family_slugs = sorted({k[0] for k in family_model})

    for slug in family_slugs:
        raw = family_model.get((slug, RAW_MODEL))
        skill = family_model.get((slug, SKILL_MODEL))

        raw_composite = (
            round(raw["composite_sum"] / raw["has_scores"], 4)
            if raw and raw["has_scores"]
            else None
        )
        skill_composite = (
            round(skill["composite_sum"] / skill["has_scores"], 4)
            if skill and skill["has_scores"]
            else None
        )

        lift = None
        if raw_composite and skill_composite and raw_composite > 0:
            lift = round((skill_composite - raw_composite) / raw_composite, 4)

        compile_pct = None
        if raw and raw["has_scores"]:
            compile_pct = round(raw["compile_pass"] / raw["has_scores"], 4)

        families.append(
            {
                "slug": slug,
                "label": slug.replace("elixir-", "").replace("-", " ").title(),
                "challenges": raw["challenges"] if raw else 0,
                "challenges_scored": raw["has_scores"] if raw else 0,
                "raw_composite": raw_composite,
                "skill_composite": skill_composite,
                "lift": lift,
                "compile_pct": compile_pct,
                "raw_l0": (
                    round(raw["l0_sum"] / raw["challenges"], 4) if raw else None
                ),
                "skill_challenges": skill["challenges"] if skill else 0,
            }
        )

    # Overall stats
    total_challenges = sum(f["challenges"] for f in families)
    total_scored = sum(f["challenges_scored"] for f in families)
    overall_raw = (
        round(sum(all_composite) / len(all_composite), 4) if all_composite else None
    )

    # Scoring progression — how baseline drops as scoring layers are added
    scoring_progression = None
    if all_l0:
        n = len(all_l0)
        scoring_progression = {
            "l0": round(sum(all_l0) / n, 4),
            "compile": round(sum(all_compile) / n, 4),
            "ast": round(sum(all_ast) / n, 4),
            "behavioral": round(sum(all_behavioral) / n, 4),
            "template": round(sum(all_template) / n, 4),
            "brevity": round(sum(all_brevity) / n, 4),
            "composite": round(sum(all_composite) / n, 4),
        }

    return {
        "families": families,
        "overall": {
            "challenges": total_challenges,
            "challenges_scored": total_scored,
            "raw_composite": overall_raw,
        },
        "scoring_progression": scoring_progression,
    }


@router.get("/{family_slug}")
async def bench_family(family_slug: str) -> dict:
    """Challenge-level detail for a single family.

    Returns tier breakdown, challenge data, dimension stats, and score distribution.
    """
    async with _connect() as conn:
        conn.row_factory = None
        cursor = await conn.execute(
            "SELECT challenge_id, model, tier, dimension, score, scores, "
            "total_tokens, duration_ms, error "
            "FROM benchmark_results WHERE family_slug = ? "
            "ORDER BY tier, challenge_id, model",
            (family_slug,),
        )
        rows = await cursor.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No benchmark data for {family_slug}")

    # Build challenge-level data
    # Key: challenge_id → {raw: {...}, skill: {...}, tier, dimension}
    challenges: dict[str, dict] = {}
    tier_stats: dict[str, dict] = {}
    dimension_stats: dict[str, dict] = {}
    composite_values: list[float] = []  # for histogram

    for challenge_id, model, tier, dimension, l0_score, scores_json, tokens, dur_ms, error in rows:
        scores = _parse_scores(scores_json)
        composite = scores.get("composite")
        compile_val = scores.get("compile", {})
        compiles = (
            compile_val.get("compiles", False) if isinstance(compile_val, dict) else False
        )
        behavioral = scores.get("behavioral", {})
        behavioral_score = (
            behavioral.get("score", 0.0) if isinstance(behavioral, dict) else 0.0
        )
        ast = scores.get("ast", {})
        ast_score = ast.get("score", 0.0) if isinstance(ast, dict) else 0.0

        entry = {
            "l0": l0_score,
            "composite": composite,
            "compiles": compiles,
            "behavioral": behavioral_score,
            "ast": ast_score,
            "tokens": tokens,
            "duration_ms": dur_ms,
            "error": error,
        }

        if challenge_id not in challenges:
            challenges[challenge_id] = {
                "challenge_id": challenge_id,
                "tier": tier,
                "dimension": dimension,
            }

        if model == RAW_MODEL:
            challenges[challenge_id]["raw"] = entry
            if composite is not None:
                composite_values.append(composite)
        elif model == SKILL_MODEL:
            challenges[challenge_id]["skill"] = entry

        # Tier aggregation (raw model only)
        if model == RAW_MODEL and composite is not None:
            if tier not in tier_stats:
                tier_stats[tier] = {
                    "count": 0,
                    "composite_sum": 0.0,
                    "compile_pass": 0,
                    "behavioral_sum": 0.0,
                    "l0_sum": 0.0,
                }
            t = tier_stats[tier]
            t["count"] += 1
            t["composite_sum"] += composite
            t["compile_pass"] += 1 if compiles else 0
            t["behavioral_sum"] += behavioral_score
            t["l0_sum"] += l0_score or 0.0

        # Dimension aggregation (raw model only)
        if model == RAW_MODEL and composite is not None:
            if dimension not in dimension_stats:
                dimension_stats[dimension] = {
                    "count": 0,
                    "composite_sum": 0.0,
                    "compile_pass": 0,
                }
            d = dimension_stats[dimension]
            d["count"] += 1
            d["composite_sum"] += composite
            d["compile_pass"] += 1 if compiles else 0

    # Format tier breakdown
    tier_order = ["easy", "medium", "hard", "legendary"]
    tiers = []
    for t_name in tier_order:
        if t_name in tier_stats:
            t = tier_stats[t_name]
            tiers.append(
                {
                    "tier": t_name,
                    "count": t["count"],
                    "avg_composite": round(t["composite_sum"] / t["count"], 4),
                    "compile_pct": round(t["compile_pass"] / t["count"], 4),
                    "avg_behavioral": round(t["behavioral_sum"] / t["count"], 4),
                    "avg_l0": round(t["l0_sum"] / t["count"], 4),
                }
            )

    # Format dimension breakdown
    dimensions = []
    for dim_name, d in sorted(dimension_stats.items()):
        dimensions.append(
            {
                "dimension": dim_name,
                "count": d["count"],
                "avg_composite": round(d["composite_sum"] / d["count"], 4),
                "compile_pct": round(d["compile_pass"] / d["count"], 4),
            }
        )

    # Score distribution histogram (0.1 buckets)
    histogram = [0] * 10  # [0.0-0.1), [0.1-0.2), ..., [0.9-1.0]
    for v in composite_values:
        bucket = min(int(v * 10), 9)
        histogram[bucket] += 1

    # Challenge list sorted by composite (ascending = hardest first)
    challenge_list = sorted(
        challenges.values(),
        key=lambda c: c.get("raw", {}).get("composite") or 0.0,
    )

    return {
        "family_slug": family_slug,
        "label": family_slug.replace("elixir-", "").replace("-", " ").title(),
        "total_challenges": len(
            [c for c in challenges.values() if "raw" in c]
        ),
        "tiers": tiers,
        "dimensions": dimensions,
        "histogram": {
            "buckets": [f"{i/10:.1f}-{(i+1)/10:.1f}" for i in range(10)],
            "counts": histogram,
        },
        "challenges": challenge_list,
    }
