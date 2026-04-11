"""Create an atomic EvolutionRun + VariantEvolution rows + gen-0 seed genomes.

Idempotent via a stable run_id keyed on family slug: if a run already exists
for ``<family-slug>-mock-v1``, it is reused and genomes/vevos are upserted.

Usage:
    uv run python scripts/mock_pipeline/create_run.py \\
        --family-slug elixir-phoenix-liveview

Prints a JSON summary with the run_id, vevo ids, and seed genome ids per
dimension. Downstream helpers consume this to drive the per-dimension loop.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from skillforge.db.queries import (
    get_family_by_slug,
    get_run,
    save_genome,
    save_run,
    save_variant_evolution,
)
from skillforge.models import EvolutionRun, SkillGenome, VariantEvolution

REPO_ROOT = Path(__file__).resolve().parents[2]


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


def _seed_genome_id(family_slug: str, dimension: str) -> str:
    return f"gen_seed_{family_slug}_{dimension}".replace("-", "_")


def _spawned_genome_id(family_slug: str, dimension: str, slot: int) -> str:
    # Used by persist_variant.py to look up this format when needed
    return f"gen_spawn_{family_slug}_{dimension}_{slot}".replace("-", "_")


def _vevo_id(family_slug: str, dimension: str) -> str:
    return f"vevo_{family_slug}_{dimension}".replace("-", "_")


def _run_id(family_slug: str) -> str:
    return f"{family_slug}-mock-v1"


async def _persist_seed_genome(
    variant: dict,
    run_id: str,
    family_slug: str,
) -> SkillGenome:
    skill_md = variant["skill_md"]
    frontmatter = _parse_frontmatter(skill_md)
    genome = SkillGenome(
        id=_seed_genome_id(family_slug, variant["dimension"]),
        generation=0,
        skill_md_content=skill_md,
        frontmatter=frontmatter,
        supporting_files={},
        traits=[],
        meta_strategy="gen0_seed",
        maturity="hardened",
    )
    await save_genome(genome, run_id)
    return genome


async def create_run(family_slug: str) -> dict:
    family_dir = REPO_ROOT / "taxonomy" / "elixir" / family_slug
    family_json = json.loads((family_dir / "family.json").read_text())
    seed_json = json.loads((family_dir / "seed.json").read_text())

    family = await get_family_by_slug(family_slug)
    if family is None:
        raise RuntimeError(
            f"Family '{family_slug}' not seeded yet — run seed_family.py first"
        )

    run_id = _run_id(family_slug)

    # Step 1: create (or reuse) the run row. best_skill is None initially; the
    # per-dimension loop will populate genomes and the finalize step will set
    # best_skill to the composite.
    existing = await get_run(run_id)
    if existing is None:
        run = EvolutionRun(
            id=run_id,
            mode="domain",
            specialization=(
                f"Elixir Phoenix LiveView · mock pipeline run over "
                f"{len(seed_json['capability_variants']) + 1} dimensions · "
                "Opus 4.6 subagent orchestration"
            ),
            population_size=2,
            num_generations=1,
            challenges=[],
            generations=[],
            learning_log=[
                f"mock_pipeline: run created for {family_slug} at {_now().isoformat()}",
            ],
            status="running",
            created_at=_now(),
            total_cost_usd=0.0,
            max_budget_usd=30.0,
            family_id=family.id,
            evolution_mode="atomic",
        )
        await save_run(run)

    # Step 2: persist gen-0 seed genomes under the new run_id. These become
    # "variant 1" per dimension — the Spawner's job is to produce variant 2.
    foundation_variant = seed_json["foundation_variants"][0]
    foundation_genome = await _persist_seed_genome(
        foundation_variant, run_id, family_slug
    )

    capability_genome_ids: dict[str, str] = {}
    for cap in seed_json["capability_variants"]:
        genome = await _persist_seed_genome(cap, run_id, family_slug)
        capability_genome_ids[cap["dimension"]] = genome.id

    # Step 3: create (or reuse) VariantEvolution rows — one per dimension.
    vevo_ids: dict[str, str] = {}
    foundation_dim = family_json["foundation_dimension"]
    foundation_vevo = VariantEvolution(
        id=_vevo_id(family_slug, foundation_dim),
        family_id=family.id,
        dimension=foundation_dim,
        tier="foundation",
        parent_run_id=run_id,
        population_size=2,
        num_generations=1,
        status="pending",
    )
    await save_variant_evolution(foundation_vevo)
    vevo_ids[foundation_dim] = foundation_vevo.id

    for dim in family_json["capability_dimensions"]:
        vevo = VariantEvolution(
            id=_vevo_id(family_slug, dim),
            family_id=family.id,
            dimension=dim,
            tier="capability",
            parent_run_id=run_id,
            population_size=2,
            num_generations=1,
            status="pending",
        )
        await save_variant_evolution(vevo)
        vevo_ids[dim] = vevo.id

    return {
        "run_id": run_id,
        "family_id": family.id,
        "vevo_ids": vevo_ids,
        "foundation_dimension": foundation_dim,
        "foundation_genome_id": foundation_genome.id,
        "capability_genome_ids": capability_genome_ids,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family-slug", required=True)
    args = parser.parse_args()

    result = asyncio.run(create_run(args.family_slug))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
