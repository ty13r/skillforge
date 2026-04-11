"""Persist a dimension winner: genome + Variant + VariantEvolution + challenges.

Called by the main session after scoring both competing variants for a
dimension and picking the one with the higher mean L1 score.

Usage:
    uv run python scripts/mock_pipeline/persist_variant.py \\
        --run-id elixir-phoenix-liveview-mock-v1 \\
        --vevo-id vevo_elixir_phoenix_liveview_heex_and_verified_routes \\
        --family-id fam_abc123 \\
        --dimension heex-and-verified-routes \\
        --tier capability \\
        --genome-id gen_seed_elixir_phoenix_liveview_heex_and_verified_routes \\
        --skill-md-path /tmp/skld-winner-heex.md \\
        --fitness 0.87 \\
        --challenges-json /tmp/skld-challenges-heex.json

Idempotent — re-runs upsert all rows with stable IDs.

The ``--challenges-json`` file is the output of ``sample_challenges.py`` for
this dimension (a JSON list). Each challenge is saved as a Challenge row and
the first one is recorded on the VariantEvolution.challenge_id field.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from skillforge.db.queries import (
    get_variant_evolution,
    save_challenge,
    save_genome,
    save_variant,
    save_variant_evolution,
)
from skillforge.models import Challenge, SkillGenome, Variant


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_frontmatter(skill_md: str) -> dict:
    lines = skill_md.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fm: dict = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip()
    return fm


def _stable_variant_id(family_slug: str, dimension: str) -> str:
    return f"var_{family_slug}_{dimension}_winner".replace("-", "_")


async def persist_variant(
    run_id: str,
    vevo_id: str,
    family_id: str,
    family_slug: str,
    dimension: str,
    tier: str,
    genome_id: str,
    skill_md_path: Path,
    fitness: float,
    challenges_json_path: Path,
) -> dict:
    # 1. Upsert the winning genome with its fitness recorded.
    skill_md = skill_md_path.read_text()
    frontmatter = _parse_frontmatter(skill_md)
    genome = SkillGenome(
        id=genome_id,
        generation=0,
        skill_md_content=skill_md,
        frontmatter=frontmatter,
        supporting_files={},
        traits=[dimension],
        meta_strategy="seed_pipeline_winner",
        maturity="tested",
        deterministic_scores={"l1": fitness},
        pareto_objectives={"quality": fitness},
    )
    await save_genome(genome, run_id)

    # 2. Create/upsert the Variant row with a stable id.
    variant = Variant(
        id=_stable_variant_id(family_slug, dimension),
        family_id=family_id,
        dimension=dimension,
        tier=tier,
        genome_id=genome.id,
        fitness_score=fitness,
        is_active=True,
        evolution_id=vevo_id,
        created_at=_now(),
    )
    await save_variant(variant)

    # 3. Save each sampled challenge under the run_id.
    challenges = json.loads(challenges_json_path.read_text())
    challenge_id: str | None = None
    for idx, ch in enumerate(challenges):
        challenge = Challenge(
            id=ch["id"],
            prompt=ch["prompt"][:8000],  # cap for DB sanity
            difficulty=ch.get("tier", "medium"),
            evaluation_criteria={
                "primary_capability": ch.get("scoring", {}).get("primary_capability", ""),
                "weight": ch.get("scoring", {}).get("weight", 1.0),
            },
            verification_method="run_tests",
            setup_files={},
            gold_standard_hints="",
        )
        await save_challenge(challenge, run_id)
        if idx == 0:
            challenge_id = challenge.id

    # 4. Upsert the VariantEvolution row to record the winner.
    vevo = await get_variant_evolution(vevo_id)
    if vevo is None:
        raise RuntimeError(f"VariantEvolution {vevo_id} not found — run create_run first")
    vevo.status = "complete"
    vevo.winner_variant_id = variant.id
    vevo.challenge_id = challenge_id
    vevo.completed_at = _now()
    await save_variant_evolution(vevo)

    return {
        "genome_id": genome.id,
        "variant_id": variant.id,
        "challenge_id": challenge_id,
        "vevo_status": vevo.status,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--vevo-id", required=True)
    parser.add_argument("--family-id", required=True)
    parser.add_argument("--family-slug", required=True)
    parser.add_argument("--dimension", required=True)
    parser.add_argument("--tier", required=True, choices=["foundation", "capability"])
    parser.add_argument("--genome-id", required=True)
    parser.add_argument("--skill-md-path", required=True, type=Path)
    parser.add_argument("--fitness", required=True, type=float)
    parser.add_argument("--challenges-json", required=True, type=Path)
    args = parser.parse_args()

    result = asyncio.run(
        persist_variant(
            run_id=args.run_id,
            vevo_id=args.vevo_id,
            family_id=args.family_id,
            family_slug=args.family_slug,
            dimension=args.dimension,
            tier=args.tier,
            genome_id=args.genome_id,
            skill_md_path=args.skill_md_path,
            fitness=args.fitness,
            challenges_json_path=args.challenges_json,
        )
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
