"""Finalize an atomic mock-pipeline run: save composite + mark run complete.

Called after the Engineer subagent has produced a composite SKILL.md. Persists
the composite as a generation-1 SkillGenome, sets it as the run's
``best_skill``, marks the run ``status=complete``, and updates the SkillFamily's
``best_assembly_id`` to point at the composite.

Usage:
    uv run python scripts/mock_pipeline/finalize_run.py \\
        --run-id elixir-phoenix-liveview-mock-v1 \\
        --composite-skill-md-path /tmp/skld-composite.md \\
        --total-cost-usd 28.50

Prints a JSON summary with the composite genome id + run status.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from skillforge.db.queries import (
    get_active_variants,
    get_run,
    save_genome,
    save_run,
    save_skill_family,
)
from skillforge.models import SkillGenome


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


async def finalize_run(
    run_id: str,
    composite_path: Path,
    total_cost_usd: float,
) -> dict:
    run = await get_run(run_id)
    if run is None:
        raise RuntimeError(f"Run {run_id} not found — run create_run first")
    if run.family_id is None:
        raise RuntimeError(f"Run {run_id} has no family_id — cannot finalize")

    # Pull all winning variants to compute avg fitness and collect parent ids.
    winners = await get_active_variants(run.family_id)
    parent_genome_ids = [v.genome_id for v in winners]
    fitnesses = [v.fitness_score for v in winners if v.fitness_score > 0]
    avg_fitness = (sum(fitnesses) / len(fitnesses)) if fitnesses else 0.0

    # Build + save the composite genome.
    composite_md = composite_path.read_text()
    frontmatter = _parse_frontmatter(composite_md)
    composite_id = f"gen_composite_{run_id}".replace("-", "_")
    composite = SkillGenome(
        id=composite_id,
        generation=1,
        skill_md_content=composite_md,
        frontmatter=frontmatter,
        supporting_files={},
        traits=[v.dimension for v in winners],
        meta_strategy="engineer_composite",
        parent_ids=parent_genome_ids,
        maturity="tested",
        deterministic_scores={"l1": round(avg_fitness, 4)},
        pareto_objectives={"quality": round(avg_fitness, 4)},
        is_pareto_optimal=True,
    )
    await save_genome(composite, run_id)

    # Update the run: best_skill, status, cost, completed_at.
    run.best_skill = composite
    run.pareto_front = [composite]
    run.status = "complete"
    run.total_cost_usd = total_cost_usd
    run.completed_at = _now()
    run.learning_log.append(
        f"mock_pipeline: finalized at {_now().isoformat()} with "
        f"{len(winners)} winning variants, avg fitness={avg_fitness:.3f}"
    )
    await save_run(run)

    # Update the SkillFamily's best_assembly_id to point at the composite.
    from skillforge.db.queries import get_family

    family = await get_family(run.family_id)
    if family is not None:
        family.best_assembly_id = composite.id
        await save_skill_family(family)

    return {
        "composite_genome_id": composite.id,
        "run_status": run.status,
        "avg_fitness": round(avg_fitness, 4),
        "winning_variants": len(winners),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--composite-skill-md-path", required=True, type=Path)
    parser.add_argument("--total-cost-usd", type=float, default=0.0)
    args = parser.parse_args()

    result = asyncio.run(
        finalize_run(
            run_id=args.run_id,
            composite_path=args.composite_skill_md_path,
            total_cost_usd=args.total_cost_usd,
        )
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
