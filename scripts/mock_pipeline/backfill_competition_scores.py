"""Persist per-(variant, challenge) competition scores into ``run.learning_log``.

The mock pipeline computed fitness for each variant × challenge combination
but only the mean score per winner landed in the DB. The raw data lives in
``/tmp/skld-mock-run/capabilities/fitness_summary.json`` (for capabilities)
and has to be reconstructed from memory for the foundation dimension.

This helper bundles both sources into a single ``[competition_scores] {...}``
entry on ``run.learning_log`` so the frontend can render:

- Per-dimension bracket (v1 vs v2)
- Per-challenge scores for each variant
- Which challenge IDs were sampled
- A "why the winner won" one-liner

Idempotent: replaces any existing entry with the same prefix.

Usage:
    uv run python scripts/mock_pipeline/backfill_competition_scores.py \\
        --run-id elixir-phoenix-liveview-mock-v1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import aiosqlite

from skillforge.config import DB_PATH

PREFIX = "[competition_scores] "

# Foundation scores were captured during the scoring run but never persisted
# in fitness_summary.json (which only covers the 11 capability dimensions).
# Values from the 4 Competitor dispatches for architectural-stance on
# medium-21 and hard-27: v1 = strict-liveview, v2 = component-forward.
FOUNDATION_SCORES = {
    "dimension": "architectural-stance",
    "tier": "foundation",
    "challenge_ids": [
        "elixir-phoenix-liveview-medium-21",
        "elixir-phoenix-liveview-hard-27",
    ],
    "variant_1_label": "strict-liveview (seed)",
    "variant_2_label": "component-forward (spawned)",
    "variant_1_scores": [0.6248, 0.4797],
    "variant_2_scores": [0.9274, 0.4797],
    "variant_1_mean": 0.5523,
    "variant_2_mean": 0.7036,
    "winner_slot": 2,
    "winning_fitness": 0.7036,
}

MOCK_ROOT = Path("/tmp/skld-mock-run/capabilities")


def _load_challenge_ids(dim: str) -> list[str]:
    path = MOCK_ROOT / dim / "challenges.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return [c["id"] for c in data]


# Human-readable labels for the capability variants. v1 is always the seed;
# v2 is the spawned alternative. The slugs are the post-colon halves from
# the variant frontmatter names.
CAPABILITY_LABELS = {
    "heex-and-verified-routes": (
        "idiomatic (seed)",
        "patch-vs-navigate-discipline (spawned)",
    ),
    "function-components-and-slots": (
        "well-typed (seed)",
        "pure-stateless-layer (spawned)",
    ),
    "live-components-stateful": (
        "isolated (seed)",
        "update-discipline (spawned)",
    ),
    "form-handling": (
        "to-form-canonical (seed)",
        "nested-assoc-forms (spawned)",
    ),
    "streams-and-collections": (
        "stream-first (seed)",
        "reset-on-filter (spawned)",
    ),
    "mount-and-lifecycle": (
        "no-db-in-mount (seed)",
        "async-load (spawned)",
    ),
    "event-handlers-and-handle-info": (
        "clear-separation (seed)",
        "event-to-action-funnel (spawned)",
    ),
    "pubsub-and-realtime": (
        "connected-guard (seed)",
        "context-owns-broadcast (spawned)",
    ),
    "navigation-patterns": (
        "push-navigate-and-link (seed)",
        "url-is-state (spawned)",
    ),
    "auth-and-authz": (
        "on-mount-hook (seed)",
        "resource-scope-mount (spawned)",
    ),
    "anti-patterns-catalog": (
        "iron-laws (seed)",
        "detector-rules (spawned)",
    ),
}


async def backfill(run_id: str) -> dict:
    # 1. Capability scores from fitness_summary.json
    fitness_path = MOCK_ROOT / "fitness_summary.json"
    if not fitness_path.exists():
        raise RuntimeError(f"Missing {fitness_path}")
    capabilities = json.loads(fitness_path.read_text())

    matches = [FOUNDATION_SCORES]
    for dim, rec in capabilities.items():
        labels = CAPABILITY_LABELS.get(
            dim, (f"{dim} (seed)", f"{dim} (spawned)")
        )
        matches.append(
            {
                "dimension": dim,
                "tier": "capability",
                "challenge_ids": _load_challenge_ids(dim),
                "variant_1_label": labels[0],
                "variant_2_label": labels[1],
                "variant_1_scores": [round(x, 4) for x in rec["v1_scores"]],
                "variant_2_scores": [round(x, 4) for x in rec["v2_scores"]],
                "variant_1_mean": round(rec["v1_mean"], 4),
                "variant_2_mean": round(rec["v2_mean"], 4),
                "winner_slot": rec["winner"],
                "winning_fitness": round(rec["winning_fitness"], 4),
            }
        )

    payload = {
        "matches": matches,
        "generation": 1,
        "total_generations": 1,
        "challenges_per_variant": 2,
        "baseline_ran": False,
        "scorer": "L1 deterministic (skillforge.engine.score)",
    }
    payload_str = PREFIX + json.dumps(payload, separators=(",", ":"))

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
        # Replace any existing competition_scores entry.
        new_log = [e for e in log if not e.startswith(PREFIX)]
        new_log.append(payload_str)
        await conn.execute(
            "UPDATE evolution_runs SET learning_log = ? WHERE id = ?",
            (json.dumps(new_log), run_id),
        )
        await conn.commit()

    return {
        "run_id": run_id,
        "matches": len(matches),
        "bytes": len(payload_str),
        "entries_after": len(new_log),
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
