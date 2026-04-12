"""Idempotent loader for seed-pipeline run artifacts.

Mirrors the seed_loader pattern: on boot, for each JSON file under
``skillforge/seeds/seed_runs/``, check whether the run already exists in the
DB with a matching content hash, and if not, replay the full row set
(taxonomy nodes → family → genomes → run → variants → variant_evolutions →
challenges).

These runs are produced by ``scripts/mock_pipeline/export_run_to_seed.py``
after an orchestrated atomic-pipeline run. They exist so that production
(Railway, ephemeral DB) shows real v2.1 content in the Registry without
waiting for the full Phase 0 plumbing to land.

Fail-soft: a bad JSON file is logged and skipped; it never prevents boot.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path

import aiosqlite

from skillforge.config import DATA_DIR, DB_PATH
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

SEED_RUNS_DIR = Path(__file__).parent / "seed_runs"

# Legacy run IDs that should be deleted before loading the seed JSON.
# Keyed by the NEW run id (what's in the current seed JSON); value is the
# legacy id shipped in earlier versions. On boot, if the legacy row still
# exists in the DB (e.g. Railway persistent volume survived the rebrand),
# it is removed along with every row that FKs to it so the Registry shows
# the single, rebranded run instead of a stale pair.
LEGACY_RUN_RENAMES: dict[str, str] = {
    "elixir-phoenix-liveview-seed-v1": "elixir-phoenix-liveview-mock-v1",
}


def _content_hash(document: dict) -> str:
    """Stable hash over the seed run JSON content."""
    payload = json.dumps(document, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_MARKER_RE = re.compile(r"\s*\[(mock|seed)_v[a-f0-9]+\]\s*")


def _hash_marker(content_hash: str) -> str:
    return f"[seed_v{content_hash[:12]}]"


def _strip_markers(specialization: str) -> str:
    """Remove any existing ``[mock_v...]`` or ``[seed_v...]`` markers.

    The loader used to append a fresh marker on every reload without
    removing stale ones, which led to specialization strings like
    ``"... [mock_v...] [mock_v...] [seed_v...]"``. This helper is idempotent
    cleanup.
    """
    return _MARKER_RE.sub(" ", specialization).strip()


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


async def _delete_legacy_run(legacy_run_id: str) -> bool:
    """Delete a legacy evolution_runs row + everything that FKs to it.

    Called on boot when a seed JSON's run_id has been rebranded (e.g.
    ``elixir-phoenix-liveview-mock-v1`` → ``elixir-phoenix-liveview-seed-v1``)
    and the legacy row is still sitting in the DB from an earlier deploy.

    Returns True if a legacy row was found and deleted, False if no-op.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            "SELECT 1 FROM evolution_runs WHERE id = ?", (legacy_run_id,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return False

        # Collect the variant IDs we need to null out of variant_evolutions
        # before deleting — variant_evolutions.winner_variant_id has an FK
        # constraint that blocks straight-up variant deletion otherwise.
        async with conn.execute(
            "SELECT id FROM variants WHERE id IN "
            "(SELECT variant_id FROM skill_genomes WHERE run_id = ?)",
            (legacy_run_id,),
        ) as cur:
            variant_rows = await cur.fetchall()
        variant_ids = [r[0] for r in variant_rows]

        # Also collect variants linked via variant_evolutions.parent_run_id.
        async with conn.execute(
            "SELECT winner_variant_id FROM variant_evolutions "
            "WHERE parent_run_id = ? AND winner_variant_id IS NOT NULL",
            (legacy_run_id,),
        ) as cur:
            vevo_winner_rows = await cur.fetchall()
        variant_ids.extend(r[0] for r in vevo_winner_rows)

        await conn.execute("PRAGMA foreign_keys = OFF")
        try:
            # Null out FK links so child deletes don't cascade unpredictably.
            await conn.execute(
                "UPDATE variant_evolutions SET winner_variant_id = NULL "
                "WHERE parent_run_id = ?",
                (legacy_run_id,),
            )
            # Delete in dependency order.
            await conn.execute(
                "DELETE FROM competition_results WHERE run_id = ?",
                (legacy_run_id,),
            )
            await conn.execute(
                "DELETE FROM run_events WHERE run_id = ?",
                (legacy_run_id,),
            )
            if variant_ids:
                placeholders = ",".join(["?"] * len(variant_ids))
                await conn.execute(
                    f"DELETE FROM variants WHERE id IN ({placeholders})",
                    variant_ids,
                )
            await conn.execute(
                "DELETE FROM variant_evolutions WHERE parent_run_id = ?",
                (legacy_run_id,),
            )
            await conn.execute(
                "DELETE FROM challenges WHERE run_id = ?",
                (legacy_run_id,),
            )
            await conn.execute(
                "DELETE FROM skill_genomes WHERE run_id = ?",
                (legacy_run_id,),
            )
            await conn.execute(
                "DELETE FROM evolution_runs WHERE id = ?",
                (legacy_run_id,),
            )
            await conn.commit()
        finally:
            await conn.execute("PRAGMA foreign_keys = ON")
    logger.info("seed_run_loader: deleted legacy run %s", legacy_run_id)
    return True


def _invalidate_report_cache(run_id: str) -> None:
    """Delete any cached report files for ``run_id`` so the next API hit
    triggers a fresh ``generate_run_report`` call against the newly-loaded
    DB state. No-op if the files are already absent. Fail-soft on any OS
    error (report regeneration is lazy, so a bad delete just means the
    stale cache stays a little longer).
    """
    reports_dir = DATA_DIR / "reports"
    for suffix in (".json", ".md"):
        path = reports_dir / f"{run_id}{suffix}"
        try:
            if path.exists():
                path.unlink()
                logger.info(
                    "seed_run_loader: invalidated cached report %s", path.name
                )
        except OSError as e:  # pragma: no cover - defensive
            logger.warning(
                "seed_run_loader: failed to invalidate %s: %s", path.name, e
            )


async def _load_one(path: Path) -> None:
    try:
        document = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("seed_run_loader: failed to read %s: %s", path.name, e)
        return

    runs = document.get("evolution_runs", [])
    if not runs:
        logger.info("seed_run_loader: %s has no evolution_runs, skipping", path.name)
        return

    run_id = runs[0]["id"]
    content_hash = _content_hash(document)
    marker = _hash_marker(content_hash)

    # Always invalidate the cached report on disk at this point, BEFORE the
    # hash-skip check below. The cache lives on Railway's persistent /data
    # volume and can diverge from the DB across deploys — even when the seed
    # JSON itself hasn't changed (e.g. if an older boot generated a report
    # with stale filter logic and the current boot has new code). Costs one
    # report regeneration on the next API hit, which is lazy and cheap.
    _invalidate_report_cache(run_id)

    # Legacy cleanup: if this run_id was renamed from an older id (e.g. the
    # phoenix-liveview mock → seed rebrand), delete the legacy row + all its
    # FK children so the Registry shows only the current id.
    legacy_id = LEGACY_RUN_RENAMES.get(run_id)
    if legacy_id:
        await _delete_legacy_run(legacy_id)

    existing = await get_run(run_id)
    if existing is not None and marker in existing.specialization:
        logger.info("seed_run_loader: %s unchanged, skipping", path.name)
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
    # Strip any stale `[mock_v...]` / `[seed_v...]` markers before injecting
    # the fresh one. Replace "mock pipeline" legacy wording with "seed
    # pipeline" on the way through so old seed files rebrand on reload.
    cleaned = _strip_markers(run.specialization).replace(
        "mock pipeline", "seed pipeline"
    )
    run.specialization = f"{cleaned} {marker}"
    await _save_run_shallow(run)

    # 4. Genomes — they FK to run, so they must come after the run row.
    best_skill_id: str | None = None
    for genome_dict in document.get("skill_genomes", []):
        await _save_genome_raw(genome_dict, run_id)
    # Find the composite genome id for the best_skill_id patch.
    if run.best_skill is not None:
        best_skill_id = run.best_skill.id

    # 5. Challenges — saved BEFORE vevos because variant_evolutions.challenge_id
    # FKs into challenges(id). Earlier seed runs shipped with NULL challenge_ids
    # so this ordering didn't matter; the phoenix-liveview rebrand tripped the
    # FK constraint because backfill_vevo_challenge_ids.py populated the field.
    for ch_dict in document.get("challenges", []):
        await _save_challenge_raw(ch_dict, run_id)

    # 6. Variant evolutions — variants.evolution_id FKs here, so vevos first.
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

    # 7. Variants — FK to skill_genomes + variant_evolutions + skill_families.
    for var_dict in document.get("variants", []):
        variant = Variant.from_dict(_translate_family(var_dict))
        await save_variant(variant)

    # 7b. Re-save vevos with their winner_variant_id now that variants exist.
    for vevo_dict in translated_vevos:
        vevo = VariantEvolution.from_dict(vevo_dict)
        await save_variant_evolution(vevo)

    # 8. Patch best_skill_id now that the genome row exists.
    if best_skill_id is not None:
        await _patch_best_skill_id(run_id, best_skill_id)

    logger.info(
        "seed_run_loader: loaded %s → run_id=%s (%d genomes, %d variants, %d vevos, %d challenges)",
        path.name,
        run_id,
        len(document.get("skill_genomes", [])),
        len(document.get("variants", [])),
        len(document.get("variant_evolutions", [])),
        len(document.get("challenges", [])),
    )


async def load_mock_runs() -> None:
    """Load every ``seed_runs/*.json`` into the DB. Safe to call on every boot.

    Function name kept as ``load_mock_runs`` to preserve the existing import
    in ``main.py``; it loads from the ``seed_runs/`` directory now.
    """
    if not SEED_RUNS_DIR.exists():
        logger.info("seed_run_loader: no seed_runs dir at %s", SEED_RUNS_DIR)
        return

    files = sorted(SEED_RUNS_DIR.glob("*.json"))
    if not files:
        logger.info("seed_run_loader: no seed run files to load")
        return

    for path in files:
        try:
            await _load_one(path)
        except Exception as e:  # noqa: BLE001 - fail soft, never break boot
            logger.exception("seed_run_loader: failed to load %s: %s", path.name, e)
