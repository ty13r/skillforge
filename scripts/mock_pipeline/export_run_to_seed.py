"""Dump an atomic-mode EvolutionRun to a replayable JSON seed file.

Walks the live DB and collects every row needed to reconstruct the run on a
fresh database: taxonomy nodes, SkillFamily, EvolutionRun, every SkillGenome
linked to the run, every Variant for the family, every VariantEvolution for
the run, and every Challenge linked to the run.

Writes a deterministic JSON file consumed on boot by
``skillforge.seeds.mock_run_loader``. Deterministic ordering means the file
diffs stay clean across re-runs.

Usage:
    uv run python scripts/mock_pipeline/export_run_to_seed.py \\
        --run-id elixir-phoenix-liveview-mock-v1 \\
        --output skillforge/seeds/mock_runs/elixir-phoenix-liveview.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import aiosqlite

from skillforge.config import DB_PATH
from skillforge.db.queries import (
    get_family,
    get_run,
    get_taxonomy_node,
    get_variant_evolutions_for_run,
    get_variants_for_family,
)


_GENOME_JSON_COLUMNS = (
    "frontmatter",
    "supporting_files",
    "traits",
    "parent_ids",
    "mutations",
    "deterministic_scores",
    "behavioral_signature",
    "pareto_objectives",
    "trait_attribution",
    "trait_diagnostics",
)

_CHALLENGE_JSON_COLUMNS = (
    "evaluation_criteria",
    "setup_files",
)


def _decode_json_columns(row: dict, columns: tuple[str, ...]) -> dict:
    """Decode the named JSON-string columns into their Python objects.

    Keeps the JSON file self-describing (no double-encoded strings) so the
    loader can rebuild dataclasses without string-parsing.
    """
    decoded = dict(row)
    for col in columns:
        val = decoded.get(col)
        if isinstance(val, str):
            try:
                decoded[col] = json.loads(val)
            except json.JSONDecodeError:
                pass
    return decoded


async def _fetch_genomes_for_run(run_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM skill_genomes WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [_decode_json_columns(dict(r), _GENOME_JSON_COLUMNS) for r in rows]


async def _fetch_challenges_for_run(run_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM challenges WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [_decode_json_columns(dict(r), _CHALLENGE_JSON_COLUMNS) for r in rows]


async def export_run_to_seed(run_id: str, output_path: Path) -> dict:
    run = await get_run(run_id)
    if run is None:
        raise RuntimeError(f"Run {run_id} not found")
    if run.family_id is None:
        raise RuntimeError(f"Run {run_id} has no family_id")

    family = await get_family(run.family_id)
    if family is None:
        raise RuntimeError(f"Family {run.family_id} not found")

    taxonomy_nodes: list[dict] = []
    for node_id in (family.domain_id, family.focus_id, family.language_id):
        if node_id is None:
            continue
        node = await get_taxonomy_node(node_id)
        if node is None:
            continue
        taxonomy_nodes.append(node.to_dict())

    variants = await get_variants_for_family(family.id)
    vevos = await get_variant_evolutions_for_run(run_id)
    genomes = await _fetch_genomes_for_run(run_id)
    challenges = await _fetch_challenges_for_run(run_id)

    # Sort everything for deterministic diffs.
    variants_sorted = sorted([v.to_dict() for v in variants], key=lambda d: d["id"])
    vevos_sorted = sorted([v.to_dict() for v in vevos], key=lambda d: d["id"])

    document = {
        "schema_version": 1,
        "mock_run_id": run_id,
        "generated_at": run.completed_at.isoformat() if run.completed_at else None,
        "taxonomy_nodes": taxonomy_nodes,
        "skill_families": [family.to_dict()],
        "evolution_runs": [run.to_dict()],
        "skill_genomes": genomes,
        "variants": variants_sorted,
        "variant_evolutions": vevos_sorted,
        "challenges": challenges,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(document, indent=2, sort_keys=True))

    return {
        "output_path": str(output_path),
        "bytes": output_path.stat().st_size,
        "rows": {
            "taxonomy_nodes": len(taxonomy_nodes),
            "skill_families": 1,
            "evolution_runs": 1,
            "skill_genomes": len(genomes),
            "variants": len(variants_sorted),
            "variant_evolutions": len(vevos_sorted),
            "challenges": len(challenges),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    result = asyncio.run(export_run_to_seed(args.run_id, args.output))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
