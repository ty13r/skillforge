"""Sample N challenges from a family's training pool for one dimension.

Selection logic:

- Walks ``challenges/medium/*.json`` and ``challenges/hard/*.json`` (both tiers;
  easy is too trivial, legendary is reserved for held-out / final eval).
- Excludes any challenge whose id is in ``family.json.challenges.held_out_ids``.
- For capability dimensions: filters by ``scoring.primary_capability == dimension``.
- For the foundation dimension: no capability filter — sample across all
  remaining challenges (foundation variants encode architectural stance that
  is relevant to every task).
- Prefers a balanced medium/hard split where possible. Deterministic seeding
  so re-runs produce the same challenges, which makes the pipeline idempotent.

Usage:
    uv run python scripts/mock_pipeline/sample_challenges.py \\
        --family-slug elixir-phoenix-liveview \\
        --dimension heex-and-verified-routes \\
        --num 2

Prints a JSON list of challenge objects, each enriched with ``path`` (absolute)
and the original ``tier`` so the Competitor dispatcher knows what to use.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _walk_tier(family_dir: Path, tier: str) -> list[dict]:
    tier_dir = family_dir / "challenges" / tier
    if not tier_dir.exists():
        return []
    items: list[dict] = []
    for path in sorted(tier_dir.glob("*.json")):
        data = json.loads(path.read_text())
        data["_path"] = str(path)
        data["_tier"] = tier
        items.append(data)
    return items


async def sample_challenges(
    family_slug: str,
    dimension: str,
    num: int,
) -> list[dict]:
    family_dir = REPO_ROOT / "taxonomy" / "elixir" / family_slug
    family_json = json.loads((family_dir / "family.json").read_text())

    held_out = set(family_json["challenges"].get("held_out_ids", []))
    is_foundation = dimension == family_json["foundation_dimension"]

    medium = _walk_tier(family_dir, "medium")
    hard = _walk_tier(family_dir, "hard")

    def _keep(ch: dict) -> bool:
        if ch["id"] in held_out:
            return False
        if is_foundation:
            return True
        scoring = ch.get("scoring", {})
        return scoring.get("primary_capability") == dimension

    medium_pool = [c for c in medium if _keep(c)]
    hard_pool = [c for c in hard if _keep(c)]

    # Deterministic seed keyed on family+dimension so re-runs pick the same
    # challenges. This is critical for idempotent re-execution.
    rng = random.Random(f"{family_slug}:{dimension}:{num}")
    rng.shuffle(medium_pool)
    rng.shuffle(hard_pool)

    picked: list[dict] = []
    half = num // 2
    picked.extend(medium_pool[:half])
    picked.extend(hard_pool[: num - half])

    # Backfill from whichever pool has more if one came up short.
    if len(picked) < num:
        remaining = num - len(picked)
        leftover = medium_pool[half:] + hard_pool[num - half :]
        picked.extend(leftover[:remaining])

    picked = picked[:num]

    # Strip internal fields for output clarity, but keep path + tier.
    out: list[dict] = []
    for c in picked:
        out.append(
            {
                "id": c["id"],
                "tier": c["_tier"],
                "path": c["_path"],
                "title": c.get("title", ""),
                "prompt": c["prompt"],
                "fixture_files": c.get("fixture_files", []),
                "expected_outputs": c.get("expected_outputs", {}),
                "scoring": c.get("scoring", {}),
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family-slug", required=True)
    parser.add_argument("--dimension", required=True)
    parser.add_argument("--num", type=int, default=2)
    args = parser.parse_args()

    result = asyncio.run(
        sample_challenges(args.family_slug, args.dimension, args.num)
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
