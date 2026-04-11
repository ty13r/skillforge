"""Idempotent loader for mock-pipeline run seeds.

Mirrors the seed_loader pattern: on boot, for each JSON file under
``skillforge/seeds/mock_runs/``, check whether the run already exists in the
DB with a matching content hash, and if not, replay the full row set
(taxonomy nodes → family → genomes → run → variants → variant_evolutions →
challenges).

These runs are produced by ``scripts/mock_pipeline/export_run_to_seed.py``
after a manual Claude-Code-subagent orchestration of the atomic pipeline.
They exist so that production (Railway, ephemeral DB) shows real v2.1 content
in the Registry without waiting for the full Phase 0 plumbing to land.

Fail-soft: a bad JSON file is logged and skipped; it never prevents boot.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import aiosqlite

from skillforge.config import DB_PATH
from skillforge.db.queries import (
    get_family,
    get_family_by_slug,
    get_run,
    get_taxonomy_node_by_slug,
    save_skill_family,
    save_taxonomy_node,
    save_variant,
    save_variant_evolution,
)
from skillforge.models import (
    EvolutionRun,
    SkillFamily,
    TaxonomyNode,
    Variant,
    VariantEvolution,
)

logger = logging.getLogger(__name__)

MOCK_RUNS_DIR = Path(__file__).parent / "mock_runs"


def _content_hash(document: dict) -> str:
    """Stable hash over the mock run JSON content."""
    payload = json.dumps(document, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _hash_marker(content_hash: str) -> str:
    return f"[mock_v{content_hash[:12]}]"


async def _save_run_shallow(run: EvolutionRun) -> None:
    """Upsert ONLY the evolution_runs row, skipping nested children.

    We need this because ``save_run`` would try to save nested challenges and
    generations — neither exists for an atomic run at the run level — and
    would also try to save ``best_skill`` via a FK that only resolves once
    every genome row has been written separately. The loader persists rows
    in dependency order and then patches ``best_skill_id`` via a separate
    UPDATE at the end.
    """
    d = run.to_dict()
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO evolution_runs
                (id, mode, specialization, population_size, num_generations,
                 status, created_at, completed_at, total_cost_usd, max_budget_usd,
                 learning_log, pareto_front_ids, best_skill_id, failure_reason,
                 family_id, evolution_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                mode=excluded.mode,
                specialization=excluded.specialization,
                population_size=excluded.population_size,
                num_generations=excluded.num_generations,
                status=excluded.status,
                completed_at=excluded.completed_at,
                total_cost_usd=excluded.total_cost_usd,
                max_budget_usd=excluded.max_budget_usd,
                learning_log=excluded.learning_log,
                pareto_front_ids=excluded.pareto_front_ids,
                failure_reason=excluded.failure_reason,
                family_id=excluded.family_id,
                evolution_mode=excluded.evolution_mode
            """,
            (
                d["id"],
                d["mode"],
                d["specialization"],
                d["population_size"],
                d["num_generations"],
                d["status"],
                d["created_at"],
                d["completed_at"],
                d["total_cost_usd"],
                d.get("max_budget_usd", 10.0),
                json.dumps(d["learning_log"]),
                json.dumps([s["id"] for s in d["pareto_front"]]),
                None,  # best_skill_id patched below
                d.get("failure_reason"),
                d.get("family_id"),
                d.get("evolution_mode", "atomic"),
            ),
        )
        await conn.commit()


async def _save_genome_raw(row: dict, run_id: str) -> None:
    """Insert a raw genome row from JSON into skill_genomes.

    ``row`` is the decoded export format: JSON columns are already Python
    objects, so we re-encode them with ``json.dumps`` on the way in.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO skill_genomes
                (id, run_id, generation, skill_md_content, frontmatter,
                 supporting_files, traits, meta_strategy, parent_ids,
                 mutations, mutation_rationale, maturity, generations_survived,
                 deterministic_scores, trigger_precision, trigger_recall,
                 behavioral_signature, pareto_objectives, is_pareto_optimal,
                 trait_attribution, trait_diagnostics, consistency_score,
                 variant_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                skill_md_content=excluded.skill_md_content,
                deterministic_scores=excluded.deterministic_scores,
                pareto_objectives=excluded.pareto_objectives,
                is_pareto_optimal=excluded.is_pareto_optimal,
                maturity=excluded.maturity
            """,
            (
                row["id"],
                run_id,
                row["generation"],
                row["skill_md_content"],
                json.dumps(row.get("frontmatter", {})),
                json.dumps(row.get("supporting_files", {})),
                json.dumps(row.get("traits", [])),
                row.get("meta_strategy", ""),
                json.dumps(row.get("parent_ids", [])),
                json.dumps(row.get("mutations", [])),
                row.get("mutation_rationale", ""),
                row.get("maturity", "draft"),
                row.get("generations_survived", 0),
                json.dumps(row.get("deterministic_scores", {})),
                row.get("trigger_precision", 0.0),
                row.get("trigger_recall", 0.0),
                json.dumps(row.get("behavioral_signature", [])),
                json.dumps(row.get("pareto_objectives", {})),
                int(row.get("is_pareto_optimal", 0)),
                json.dumps(row.get("trait_attribution", {})),
                json.dumps(row.get("trait_diagnostics", {})),
                row.get("consistency_score"),
                row.get("variant_id"),
            ),
        )
        await conn.commit()


async def _save_challenge_raw(row: dict, run_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO challenges
                (id, run_id, prompt, difficulty, evaluation_criteria,
                 verification_method, setup_files, gold_standard_hints)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                run_id,
                row["prompt"],
                row.get("difficulty", "medium"),
                json.dumps(row.get("evaluation_criteria", {})),
                row.get("verification_method", "run_tests"),
                json.dumps(row.get("setup_files", {})),
                row.get("gold_standard_hints", ""),
            ),
        )
        await conn.commit()


async def _patch_best_skill_id(run_id: str, best_skill_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE evolution_runs SET best_skill_id = ? WHERE id = ?",
            (best_skill_id, run_id),
        )
        await conn.commit()


async def _load_one(path: Path) -> None:
    try:
        document = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("mock_run_loader: failed to read %s: %s", path.name, e)
        return

    runs = document.get("evolution_runs", [])
    if not runs:
        logger.info("mock_run_loader: %s has no evolution_runs, skipping", path.name)
        return

    run_id = runs[0]["id"]
    content_hash = _content_hash(document)
    marker = _hash_marker(content_hash)

    existing = await get_run(run_id)
    if existing is not None and marker in existing.specialization:
        logger.info("mock_run_loader: %s unchanged, skipping", path.name)
        return

    # 1. Taxonomy nodes in dependency order (domain → focus → language).
    #
    # The JSON carries random taxonomy_node IDs from the source DB. On a
    # target DB those IDs may not exist (or may exist with different values
    # if another loader created the node first via its own seed list).
    # Resolve everything by natural key (level + slug + parent_id) and build
    # a map from source IDs to resolved target IDs. All subsequent FKs that
    # point at taxonomy nodes translate through this map.
    level_order = {"domain": 0, "focus": 1, "language": 2}
    nodes_sorted = sorted(
        document.get("taxonomy_nodes", []),
        key=lambda n: level_order.get(n.get("level", "domain"), 99),
    )
    tax_id_map: dict[str, str] = {}
    for node_dict in nodes_sorted:
        src_id = node_dict["id"]
        src_parent = node_dict.get("parent_id")
        resolved_parent = tax_id_map.get(src_parent) if src_parent else None

        existing_node = await get_taxonomy_node_by_slug(
            node_dict["level"], node_dict["slug"], resolved_parent
        )
        if existing_node is not None:
            tax_id_map[src_id] = existing_node.id
        else:
            node = TaxonomyNode.from_dict(node_dict)
            node.parent_id = resolved_parent
            await save_taxonomy_node(node)
            tax_id_map[src_id] = node.id

    # 2. Skill families — translate the three taxonomy FKs through tax_id_map.
    # Families are also looked up by slug (unique) rather than by source id.
    family_id_map: dict[str, str] = {}
    for fam_dict in document.get("skill_families", []):
        src_fam_id = fam_dict["id"]
        existing_fam = await get_family_by_slug(fam_dict["slug"])
        if existing_fam is not None:
            family_id_map[src_fam_id] = existing_fam.id
        else:
            translated = dict(fam_dict)
            for fk in ("domain_id", "focus_id", "language_id"):
                if translated.get(fk):
                    translated[fk] = tax_id_map.get(translated[fk], translated[fk])
            family = SkillFamily.from_dict(translated)
            await save_skill_family(family)
            family_id_map[src_fam_id] = family.id

    # 3. Evolution run shallow (no best_skill_id yet).
    run_dict = dict(runs[0])
    if run_dict.get("family_id"):
        run_dict["family_id"] = family_id_map.get(run_dict["family_id"], run_dict["family_id"])
    run = EvolutionRun.from_dict(run_dict)
    # Inject the content-hash marker so the skip check on the next boot works.
    if marker not in run.specialization:
        run.specialization = f"{run.specialization} {marker}"
    await _save_run_shallow(run)

    # 4. Genomes — they FK to run, so they must come after the run row.
    best_skill_id: str | None = None
    for genome_dict in document.get("skill_genomes", []):
        await _save_genome_raw(genome_dict, run_id)
    # Find the composite genome id for the best_skill_id patch.
    if run.best_skill is not None:
        best_skill_id = run.best_skill.id

    # 5. Variant evolutions — variants.evolution_id FKs here, so vevos first.
    # Save vevos with winner_variant_id=NULL so the variant's FK to vevo
    # resolves; we'll re-save vevos after variants to set winner_variant_id.
    # Translate family_id through family_id_map.
    def _translate_family(d: dict) -> dict:
        out = dict(d)
        if out.get("family_id"):
            out["family_id"] = family_id_map.get(out["family_id"], out["family_id"])
        return out

    raw_vevos = document.get("variant_evolutions", [])
    translated_vevos = [_translate_family(v) for v in raw_vevos]
    for vevo_dict in translated_vevos:
        vevo_stub = VariantEvolution.from_dict(vevo_dict)
        vevo_stub.winner_variant_id = None
        await save_variant_evolution(vevo_stub)

    # 6. Variants — FK to skill_genomes + variant_evolutions + skill_families.
    for var_dict in document.get("variants", []):
        variant = Variant.from_dict(_translate_family(var_dict))
        await save_variant(variant)

    # 6b. Re-save vevos with their winner_variant_id now that variants exist.
    for vevo_dict in translated_vevos:
        vevo = VariantEvolution.from_dict(vevo_dict)
        await save_variant_evolution(vevo)

    # 7. Challenges.
    for ch_dict in document.get("challenges", []):
        await _save_challenge_raw(ch_dict, run_id)

    # 8. Patch best_skill_id now that the genome row exists.
    if best_skill_id is not None:
        await _patch_best_skill_id(run_id, best_skill_id)

    logger.info(
        "mock_run_loader: loaded %s → run_id=%s (%d genomes, %d variants, %d vevos, %d challenges)",
        path.name,
        run_id,
        len(document.get("skill_genomes", [])),
        len(document.get("variants", [])),
        len(document.get("variant_evolutions", [])),
        len(document.get("challenges", [])),
    )


async def load_mock_runs() -> None:
    """Load every ``mock_runs/*.json`` into the DB. Safe to call on every boot."""
    if not MOCK_RUNS_DIR.exists():
        logger.info("mock_run_loader: no mock_runs dir at %s", MOCK_RUNS_DIR)
        return

    files = sorted(MOCK_RUNS_DIR.glob("*.json"))
    if not files:
        logger.info("mock_run_loader: no mock run files to load")
        return

    for path in files:
        try:
            await _load_one(path)
        except Exception as e:  # noqa: BLE001 - fail soft, never break boot
            logger.exception("mock_run_loader: failed to load %s: %s", path.name, e)
