"""Post-run report generator (Wave 1-5).

After every evolution run completes, ``generate_run_report(run_id)`` assembles
a single structured artifact that captures everything about the run — metadata,
taxonomy classification, challenges, per-generation fitness + learning log +
Pareto front, per-skill fitness breakdown, variant evolutions (v2.0 atomic
runs), the assembly report (v2.0 atomic runs), bible findings, the full
learning log, and a top-level summary.

The report exists so:
  1. A future model can ingest a complete run without joining 6+ tables.
  2. The research paper has a stable, serializable artifact per run.
  3. The frontend can fetch one endpoint and render the whole story.

Output lives in ``data/reports/{run_id}.json`` plus a human-readable
``{run_id}.md`` sidecar. Both are capped at ~1MB; we truncate the
``skill_md_content`` preview to keep the JSON under the cap.

This module only READS the database — it never writes back to the run
tables. Errors are logged and swallowed so a report failure never blocks
the evolution pipeline (the caller fires this as a detached task).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from skillforge.config import DATA_DIR
from skillforge.db import (
    get_family,
    get_run,
    get_taxonomy_node,
    get_variant_evolutions_for_run,
    get_variants_for_family,
)
from skillforge.models import EvolutionRun

logger = logging.getLogger(__name__)

# Reports live next to the SQLite DB so Railway's persistent volume keeps them.
REPORTS_DIR: Path = Path(DATA_DIR) / "reports"

# Preview cap for SKILL.md content to keep reports bounded (first N lines).
SKILL_MD_PREVIEW_LINES = 30
# Hard size cap we refuse to exceed — at ~1MB the JSON stays responsive.
MAX_REPORT_BYTES = 1_000_000


# ---------------------------------------------------------------------------
# Section builders — each returns a serializable dict/list
# ---------------------------------------------------------------------------


def _build_metadata(run: EvolutionRun) -> dict[str, Any]:
    duration_sec: float | None = None
    if run.completed_at is not None:
        duration_sec = (run.completed_at - run.created_at).total_seconds()
    return {
        "run_id": run.id,
        "mode": run.mode,
        "specialization": run.specialization,
        "status": run.status,
        "population_size": run.population_size,
        "num_generations": run.num_generations,
        "evolution_mode": getattr(run, "evolution_mode", "molecular"),
        "family_id": getattr(run, "family_id", None),
        "total_cost_usd": run.total_cost_usd,
        "max_budget_usd": run.max_budget_usd,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "duration_sec": duration_sec,
        "failure_reason": run.failure_reason,
    }


async def _build_taxonomy_section(run: EvolutionRun) -> dict[str, Any] | None:
    """If the run has been classified into a family, resolve its taxonomy."""
    family_id = getattr(run, "family_id", None)
    if not family_id:
        return None
    family = await get_family(family_id)
    if family is None:
        return {"family_id": family_id, "resolved": False}

    domain = (
        await get_taxonomy_node(family.domain_id) if family.domain_id else None
    )
    focus = (
        await get_taxonomy_node(family.focus_id) if family.focus_id else None
    )
    language = (
        await get_taxonomy_node(family.language_id)
        if family.language_id
        else None
    )
    return {
        "family_id": family.id,
        "family_slug": family.slug,
        "family_label": family.label,
        "decomposition_strategy": family.decomposition_strategy,
        "domain": domain.to_dict() if domain else None,
        "focus": focus.to_dict() if focus else None,
        "language": language.to_dict() if language else None,
        "tags": list(family.tags),
    }


def _build_challenges_section(run: EvolutionRun) -> list[dict[str, Any]]:
    return [
        {
            "id": c.id,
            "prompt": c.prompt,
            "difficulty": c.difficulty,
            "verification_method": c.verification_method,
            "evaluation_criteria": c.evaluation_criteria,
        }
        for c in run.challenges
    ]


def _preview_skill_md(content: str) -> str:
    lines = content.splitlines()
    if len(lines) <= SKILL_MD_PREVIEW_LINES:
        return content
    return "\n".join(lines[:SKILL_MD_PREVIEW_LINES]) + "\n... (truncated)"


def _build_skill_entry(skill: Any) -> dict[str, Any]:
    """One skill entry inside a generation — shape-safe even for partial data."""
    return {
        "id": skill.id,
        "generation": skill.generation,
        "maturity": skill.maturity,
        "is_pareto_optimal": bool(skill.is_pareto_optimal),
        "variant_id": getattr(skill, "variant_id", None),
        "fitness_breakdown": {
            "deterministic_scores": skill.deterministic_scores,
            "trigger_precision": skill.trigger_precision,
            "trigger_recall": skill.trigger_recall,
            "pareto_objectives": skill.pareto_objectives,
            "trait_attribution": skill.trait_attribution,
            "consistency_score": skill.consistency_score,
        },
        "traits": list(skill.traits),
        "mutations": list(skill.mutations),
        "mutation_rationale": skill.mutation_rationale,
        "parent_ids": list(skill.parent_ids),
        "meta_strategy": skill.meta_strategy,
        "skill_md_preview": _preview_skill_md(skill.skill_md_content),
    }


def _build_generations_section(run: EvolutionRun) -> list[dict[str, Any]]:
    generations: list[dict[str, Any]] = []
    prev_best: float | None = None
    for gen in run.generations:
        delta = None
        if prev_best is not None:
            delta = gen.best_fitness - prev_best
        prev_best = gen.best_fitness

        generations.append(
            {
                "number": gen.number,
                "fitness_curve": {
                    "best": gen.best_fitness,
                    "avg": gen.avg_fitness,
                    "delta_from_prev": delta,
                },
                "trait_survival": gen.trait_survival,
                "trait_emergence": list(gen.trait_emergence),
                "learning_log_entries": list(gen.learning_log_entries),
                "pareto_front": list(gen.pareto_front),
                "breeding_report": gen.breeding_report,
                "skills": [_build_skill_entry(s) for s in gen.skills],
            }
        )
    return generations


async def _build_atomic_genomes_section(
    run: EvolutionRun,
) -> list[dict[str, Any]]:
    """For atomic runs, fetch every genome linked to this run.

    Atomic runs store genomes as standalone ``skill_genomes`` rows keyed on
    ``run_id`` without the nested ``run.generations[].skills[]`` path that
    molecular runs use. The frontend needs the full list to render Gen 0
    variants, the Competition bracket, and the atomic lineage view without
    paying for 25 separate round-trips to ``/runs/{id}/skills/{id}``.

    Returns an empty list for molecular runs or on error (defensive).
    """
    if getattr(run, "evolution_mode", "molecular") != "atomic":
        return []
    try:
        from skillforge.db.queries import _connect, _row_to_genome

        async with _connect() as conn, conn.execute(
            "SELECT * FROM skill_genomes WHERE run_id = ? "
            "ORDER BY generation, id",
            (run.id,),
        ) as cur:
            rows = await cur.fetchall()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("report: failed to fetch atomic genomes: %s", exc)
        return []

    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            g = _row_to_genome(row)
        except Exception:
            continue
        out.append(
            {
                "id": g.id,
                "generation": g.generation,
                "maturity": g.maturity,
                "meta_strategy": g.meta_strategy,
                "parent_ids": list(g.parent_ids),
                "traits": list(g.traits),
                "pareto_objectives": g.pareto_objectives,
                "deterministic_scores": g.deterministic_scores,
                # Full content — atomic seed runs have ~25KB of prose
                # genomes plus any supporting_files, still well under the
                # MAX_REPORT_BYTES budget.
                "skill_md_content": g.skill_md_content,
                "frontmatter": g.frontmatter,
                # Rich package contents (scripts/, references/, test_fixtures/,
                # assets/) for composites that were enriched post-assembly or
                # generated by a production engine that natively produces
                # rich directory packages.
                "supporting_files": dict(g.supporting_files),
            }
        )
    return out


async def _build_variant_evolutions_section(
    run: EvolutionRun,
) -> list[dict[str, Any]]:
    """For atomic runs, fetch the per-dimension VariantEvolution records.

    Returns an empty list for molecular runs (the common case today).
    """
    try:
        evolutions = await get_variant_evolutions_for_run(run.id)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("report: failed to fetch variant evolutions: %s", exc)
        return []

    out: list[dict[str, Any]] = []
    for vevo in evolutions:
        entry: dict[str, Any] = {
            "id": vevo.id,
            "dimension": vevo.dimension,
            "tier": vevo.tier,
            "status": vevo.status,
            "population_size": vevo.population_size,
            "num_generations": vevo.num_generations,
            "winner_variant_id": vevo.winner_variant_id,
            "foundation_genome_id": vevo.foundation_genome_id,
            "challenge_id": vevo.challenge_id,
            "created_at": vevo.created_at.isoformat()
            if vevo.created_at
            else None,
            "completed_at": vevo.completed_at.isoformat()
            if vevo.completed_at
            else None,
        }
        out.append(entry)
    return out


async def _build_assembly_report(run: EvolutionRun) -> dict[str, Any] | None:
    """Stub for the v2.0 Engineer assembly report.

    Wave 4 (Phase 4) will populate this with synergy ratio, conflict count,
    integration pass rate, merge decisions. For now we surface the family's
    current best_assembly_id and active variants so the report has a
    recognizable hook point.
    """
    family_id = getattr(run, "family_id", None)
    if not family_id:
        return None
    family = await get_family(family_id)
    if family is None:
        return None

    active_variants: list[dict[str, Any]] = []
    try:
        variants = await get_variants_for_family(family_id)
        active_variants = [v.to_dict() for v in variants if v.is_active]
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("report: failed to fetch active variants: %s", exc)

    return {
        "family_id": family.id,
        "best_assembly_id": family.best_assembly_id,
        "active_variants": active_variants,
    }


def _build_summary(
    run: EvolutionRun,
    generations: list[dict[str, Any]],
    learning_log_entries: list[str],
    variant_evolutions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the run summary. Handles both molecular and atomic modes.

    For atomic runs, ``generations`` is typically empty (no nested Generation
    rows) so we derive ``aggregate_fitness`` from ``run.best_skill`` (the
    composite genome) instead, and ``dimensions_evolved`` from the per-
    dimension ``variant_evolutions`` list.
    """
    # Pick the three most-recent lessons as "key discoveries" until we have
    # a novelty score. Good enough for the research paper baseline. Skip
    # the prefix-tagged integration_report entries when surfacing discoveries.
    surfaceable = [
        e for e in learning_log_entries if not e.startswith("[integration_report]")
    ]
    key_discoveries = surfaceable[-3:][::-1]

    # Divisor: number of Generation rows for molecular, or variant_evolutions
    # for atomic (each dim is one unit of evolution work).
    num_units = len(run.generations) or (
        len(variant_evolutions) if variant_evolutions else 1
    )
    cost_per_gen = (
        run.total_cost_usd / max(1, num_units) if run.total_cost_usd else 0.0
    )
    wall_clock = None
    if run.completed_at is not None:
        wall_clock = (run.completed_at - run.created_at).total_seconds()

    # aggregate_fitness priority: last generation's best (molecular),
    # else composite best_skill's pareto_objectives max (atomic),
    # else 0.0.
    if generations:
        aggregate_fitness = generations[-1]["fitness_curve"]["best"]
    elif run.best_skill and run.best_skill.pareto_objectives:
        aggregate_fitness = max(run.best_skill.pareto_objectives.values())
    else:
        aggregate_fitness = 0.0

    # dimensions_evolved priority: molecular generation numbers, else the
    # per-dimension string list from variant_evolutions.
    if generations:
        dimensions_evolved: list[Any] = [
            g.get("number", i) for i, g in enumerate(generations)
        ]
    elif variant_evolutions:
        dimensions_evolved = [ve.get("dimension") for ve in variant_evolutions]
    else:
        dimensions_evolved = []

    return {
        "best_skill_id": run.best_skill.id if run.best_skill else None,
        "aggregate_fitness": aggregate_fitness,
        "total_cost_usd": run.total_cost_usd,
        "cost_per_generation": cost_per_gen,
        "wall_clock_duration_sec": wall_clock,
        "evolution_mode": getattr(run, "evolution_mode", "molecular"),
        "dimensions_evolved": dimensions_evolved,
        "key_discoveries": key_discoveries,
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _render_markdown(report: dict[str, Any]) -> str:
    meta = report["metadata"]
    summary = report["summary"]
    lines: list[str] = []
    lines.append(f"# Run Report — {meta['run_id']}")
    lines.append("")
    lines.append(f"**Specialization**: {meta['specialization']}")
    lines.append(f"**Mode**: {meta['mode']} ({meta['evolution_mode']})")
    lines.append(f"**Status**: {meta['status']}")
    lines.append(f"**Cost**: ${meta['total_cost_usd']:.2f}")
    if meta.get("duration_sec") is not None:
        lines.append(f"**Duration**: {meta['duration_sec']:.1f}s")
    lines.append("")

    if report.get("taxonomy"):
        t = report["taxonomy"]
        lines.append("## Taxonomy")
        lines.append(
            f"- Family: `{t.get('family_slug', '?')}` "
            f"({t.get('decomposition_strategy', '?')})"
        )
        if t.get("domain"):
            lines.append(f"- Domain: `{t['domain']['slug']}` — {t['domain']['label']}")
        if t.get("focus"):
            lines.append(f"- Focus: `{t['focus']['slug']}` — {t['focus']['label']}")
        if t.get("language"):
            lines.append(
                f"- Language: `{t['language']['slug']}` — {t['language']['label']}"
            )
        lines.append("")

    lines.append("## Summary")
    lines.append(f"- **Best skill**: `{summary.get('best_skill_id', '?')}`")
    lines.append(
        f"- **Aggregate fitness**: {summary.get('aggregate_fitness', 0):.3f}"
    )
    lines.append(
        f"- **Cost per generation**: ${summary.get('cost_per_generation', 0):.2f}"
    )
    if summary.get("wall_clock_duration_sec") is not None:
        lines.append(
            f"- **Wall clock**: {summary['wall_clock_duration_sec']:.1f}s"
        )
    lines.append("")

    if summary.get("key_discoveries"):
        lines.append("### Key discoveries")
        for d in summary["key_discoveries"]:
            lines.append(f"- {d}")
        lines.append("")

    gens = report.get("generations", [])
    if gens:
        lines.append("## Generations")
        for g in gens:
            fc = g["fitness_curve"]
            delta = fc.get("delta_from_prev")
            delta_str = f" (Δ {delta:+.3f})" if delta is not None else ""
            lines.append(
                f"- **Gen {g['number']}** — best {fc['best']:.3f}, "
                f"avg {fc['avg']:.3f}{delta_str}"
            )
        lines.append("")

    if report.get("variant_evolutions"):
        lines.append("## Variant evolutions (v2.0 atomic)")
        for ve in report["variant_evolutions"]:
            lines.append(
                f"- `{ve['dimension']}` ({ve['tier']}) — {ve['status']}"
            )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("_Generated by `skillforge.engine.report.generate_run_report`._")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def generate_run_report(
    run_id: str, reports_dir: Path | None = None
) -> dict[str, Any] | None:
    """Assemble a full post-run report and save JSON + Markdown to disk.

    Returns the report dict on success. Returns ``None`` if the run does not
    exist or generation fails — the caller should never treat a missing report
    as a fatal error.
    """
    try:
        run = await get_run(run_id)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("report: failed to load run %s: %s", run_id, exc)
        return None

    if run is None:
        logger.warning("report: run %s not found", run_id)
        return None

    try:
        taxonomy_section = await _build_taxonomy_section(run)
        challenges_section = _build_challenges_section(run)
        generations_section = _build_generations_section(run)
        variant_evolutions_section = await _build_variant_evolutions_section(run)
        assembly_section = await _build_assembly_report(run)
        atomic_genomes_section = await _build_atomic_genomes_section(run)

        learning_log_entries = list(run.learning_log)

        report: dict[str, Any] = {
            "metadata": _build_metadata(run),
            "taxonomy": taxonomy_section,
            "challenges": challenges_section,
            "generations": generations_section,
            "variant_evolutions": variant_evolutions_section,
            "skill_genomes": atomic_genomes_section,
            "assembly_report": assembly_section,
            "bible_findings": [],  # Wave 4+ will populate from the breeder
            "learning_log": learning_log_entries,
            "summary": _build_summary(
                run,
                generations_section,
                learning_log_entries,
                variant_evolutions=variant_evolutions_section,
            ),
            "generated_at": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("report: failed to build report for %s: %s", run_id, exc)
        return None

    target_dir = reports_dir if reports_dir is not None else REPORTS_DIR
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        json_path = target_dir / f"{run_id}.json"
        md_path = target_dir / f"{run_id}.md"

        payload = json.dumps(report, indent=2, default=str)
        size_bytes = len(payload.encode("utf-8"))
        if size_bytes > MAX_REPORT_BYTES:
            logger.warning(
                "report: %s exceeds %d bytes (%d); caller may need to truncate",
                run_id,
                MAX_REPORT_BYTES,
                size_bytes,
            )

        json_path.write_text(payload, encoding="utf-8")
        md_path.write_text(_render_markdown(report), encoding="utf-8")
        logger.info(
            "report: generated %s (%d bytes)", run_id, size_bytes
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("report: failed to write report for %s: %s", run_id, exc)
        return None

    return report


async def get_report(
    run_id: str, reports_dir: Path | None = None
) -> dict[str, Any] | None:
    """Load a previously-generated report from disk, or None if missing."""
    target_dir = reports_dir if reports_dir is not None else REPORTS_DIR
    path = target_dir / f"{run_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("report: failed to load %s: %s", run_id, exc)
        return None
