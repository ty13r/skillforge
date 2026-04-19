"""GET endpoints that read run state + POST /runs/{id}/cancel.

All handlers here work off an existing run id — they never start new
evolutions. See ``evolve.py`` for the POST endpoints that do.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Response

from skillforge.api.schemas import (
    ExportFormat,
    LineageEdge,
    LineageNode,
    RunDetail,
)
from skillforge.db.queries import get_lineage, get_run, list_runs
from skillforge.engine.export import (
    export_agent_sdk_config,
    export_skill_md,
    export_skill_zip,
)
from skillforge.engine.run_registry import registry
from skillforge.models import SkillGenome

logger = logging.getLogger("skillforge.api.runs")
router = APIRouter()


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str) -> dict:
    """Cancel an in-progress evolution run.

    Finds the backing asyncio task in the ``RunRegistry``, cancels it,
    and marks the run status as ``cancelled`` in the DB. The engine catches
    ``CancelledError`` in its main loop, emits a ``run_cancelled`` event,
    and persists the partial state before exiting.
    """
    task = registry.get_task(run_id)
    if task is None or task.done():
        # Maybe already done, maybe never existed — either way nothing to cancel
        raise HTTPException(
            status_code=404, detail=f"no active run {run_id!r} to cancel"
        )
    task.cancel()
    return {"run_id": run_id, "cancelled": True}


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run_detail(run_id: str) -> RunDetail:
    run = await get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")

    # Compute baseline_fitness from benchmark_results if this run has a family
    baseline_fitness = None
    family_id = getattr(run, "family_id", None)
    if family_id:
        from skillforge.db.queries import _connect

        async with _connect() as conn:
            # Look up the family slug
            cursor = await conn.execute(
                "SELECT slug FROM skill_families WHERE id = ?", (family_id,)
            )
            fam_row = await cursor.fetchone()
            if fam_row:
                family_slug = fam_row[0]
                # Average composite score of raw Sonnet on this family's challenges
                cursor = await conn.execute(
                    "SELECT AVG(json_extract(scores, '$.composite')) "
                    "FROM benchmark_results "
                    "WHERE family_slug = ? AND model = 'claude-sonnet-4-6' "
                    "AND scores != '{}'",
                    (family_slug,),
                )
                avg_row = await cursor.fetchone()
                if avg_row and avg_row[0] is not None:
                    baseline_fitness = round(avg_row[0], 4)

    return RunDetail(
        id=run.id,
        mode=run.mode,
        specialization=run.specialization,
        status=run.status,
        population_size=run.population_size,
        num_generations=run.num_generations,
        total_cost_usd=run.total_cost_usd,
        best_fitness=(
            max(run.best_skill.pareto_objectives.values())
            if run.best_skill and run.best_skill.pareto_objectives
            else None
        ),
        best_skill_id=run.best_skill.id if run.best_skill else None,
        family_id=family_id,
        evolution_mode=getattr(run, "evolution_mode", "molecular"),
        learning_log=list(run.learning_log),
        baseline_fitness=baseline_fitness,
    )


@router.get("/runs/{run_id}/dimensions")
async def get_run_dimensions(run_id: str) -> list[dict]:
    """Return variant_evolutions + winning variant data for an atomic run.

    Each entry represents one dimension's mini-evolution: its tier, status,
    winning variant fitness, and challenge info.
    """
    from skillforge.db.queries import _connect

    async with _connect() as conn:
        cursor = await conn.execute(
            """
            SELECT ve.id, ve.dimension, ve.tier, ve.status,
                   ve.winner_variant_id, ve.challenge_id,
                   ve.population_size, ve.num_generations,
                   ve.created_at, ve.completed_at,
                   v.fitness_score, v.genome_id
            FROM variant_evolutions ve
            LEFT JOIN variants v ON v.id = ve.winner_variant_id
            WHERE ve.parent_run_id = ?
            ORDER BY
                CASE ve.tier WHEN 'foundation' THEN 0 ELSE 1 END,
                ve.dimension ASC
            """,
            (run_id,),
        )
        rows = await cursor.fetchall()

    return [
        {
            "id": r[0],
            "dimension": r[1],
            "tier": r[2],
            "status": r[3],
            "winner_variant_id": r[4],
            "challenge_id": r[5],
            "population_size": r[6],
            "num_generations": r[7],
            "created_at": r[8],
            "completed_at": r[9],
            "fitness_score": r[10],
            "genome_id": r[11],
        }
        for r in rows
    ]


@router.get("/runs/{run_id}/events")
async def get_run_events(run_id: str) -> list[dict]:
    """Return the full event history for a run (for post-mortem debugging)."""
    from skillforge.db.queries import _connect

    async with _connect() as conn:
        cursor = await conn.execute(
            "SELECT event_type, payload, timestamp FROM run_events WHERE run_id = ? ORDER BY id",
            (run_id,),
        )
        rows = await cursor.fetchall()
    return [{"event": row[0], "payload": json.loads(row[1]), "timestamp": row[2]} for row in rows]


@router.get("/runs/{run_id}/report")
async def get_run_report(run_id: str) -> dict:
    """Return the post-run report JSON for a completed run.

    Generated by ``skillforge.engine.report.generate_run_report`` as a detached
    task after ``evolution_complete``. If the report does not exist yet (e.g.,
    a run that was inserted via a seed loader rather than through the engine),
    we lazy-generate it on the first call so the frontend never has to poll.
    """
    from skillforge.engine.report import generate_run_report, get_report

    report = await get_report(run_id)
    if report is None:
        # Lazy generation. Safe: generate_run_report is read-only against
        # the run tables and writes to data/reports/. Returns None on error
        # so we can still 404 cleanly.
        report = await generate_run_report(run_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"report not generated yet for run_id={run_id}",
        )
    return report


@router.get("/runs")
async def list_all_runs():
    """List recent runs (most recent first)."""
    runs = await list_runs(limit=50)
    return [
        {
            "id": r.id,
            "mode": r.mode,
            "specialization": r.specialization,
            "status": r.status,
            "best_fitness": (
                max(r.best_skill.pareto_objectives.values())
                if r.best_skill and r.best_skill.pareto_objectives
                else None
            ),
            "total_cost_usd": r.total_cost_usd,
        }
        for r in runs
    ]


@router.get("/runs/{run_id}/export")
async def export_run(run_id: str, format: ExportFormat = ExportFormat.skill_dir):
    run = await get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    if run.best_skill is None:
        raise HTTPException(status_code=400, detail="run has no best_skill to export")

    if format == ExportFormat.skill_dir:
        zip_bytes = export_skill_zip(run.best_skill)
        # Prefer the composite's own skill name from the frontmatter (kebab-case
        # slug) for the download filename — that's what the user is actually
        # deploying. Fall back to the run id with any legacy "mock" marker
        # scrubbed so the filename never says "mock" to an end user.
        name = ""
        if run.best_skill.frontmatter:
            name = str(run.best_skill.frontmatter.get("name", "")).strip()
        if not name:
            name = run_id.replace("mock-v", "v").replace("mock", "seed")
        filename = f"{name}.zip"
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    if format == ExportFormat.skill_md:
        md = export_skill_md(run.best_skill)
        return Response(content=md, media_type="text/markdown")
    if format == ExportFormat.agent_sdk_config:
        config = export_agent_sdk_config(run.best_skill)
        return Response(content=json.dumps(config, indent=2), media_type="application/json")
    raise HTTPException(status_code=400, detail=f"unknown format: {format}")


@router.get("/runs/{run_id}/lineage")
async def get_run_lineage(run_id: str) -> dict:
    """Return lineage tree data: nodes (genomes) + edges (parent→child).

    Nodes are built from ``run.generations[].skills[]`` for molecular runs,
    and fall back to a direct ``skill_genomes`` query for atomic runs where
    ``run.generations`` is always empty. Edges are always sourced from
    ``get_lineage``, which reads ``skill_genomes.parent_ids`` directly, so
    it's already atomic-compatible.
    """
    run = await get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")

    # Pre-fetch the child genomes' meta_strategy so we can infer mutation_type
    # for atomic-mode composite edges. In atomic mode the Engineer assembles
    # 12+ parents into a single composite — that's an "assembly" edge, not a
    # mutation. Without this inference every edge defaults to "unknown".
    child_meta_strategy: dict[str, str] = {}
    if getattr(run, "evolution_mode", "molecular") == "atomic":
        from skillforge.db.queries import _connect

        async with _connect() as conn, conn.execute(
            "SELECT id, meta_strategy FROM skill_genomes WHERE run_id = ?",
            (run_id,),
        ) as cur:
            for row in await cur.fetchall():
                child_meta_strategy[row["id"]] = row["meta_strategy"] or ""

    def _infer_mutation_type(edge: dict) -> str:
        child_id = edge.get("child_id", "")
        strategy = child_meta_strategy.get(child_id, "")
        if strategy == "engineer_composite":
            return "assembly"
        if strategy in {"seed_pipeline_winner", "mock_pipeline_winner", "gen0_seed"}:
            return "selection"
        return edge.get("mutation_type", "unknown")

    edges_data = await get_lineage(run_id)
    edges = [
        LineageEdge(
            parent_id=e.get("parent_id", ""),
            child_id=e.get("child_id", ""),
            mutation_type=_infer_mutation_type(e),
        )
        for e in edges_data
    ]

    # Build nodes from all genomes across all generations
    nodes = []
    seen_ids: set[str] = set()
    for gen in run.generations:
        for skill in gen.skills:
            if skill.id in seen_ids:
                continue
            seen_ids.add(skill.id)
            fitness = (
                sum(skill.pareto_objectives.values()) / len(skill.pareto_objectives)
                if skill.pareto_objectives
                else 0.0
            )
            nodes.append(
                LineageNode(
                    id=skill.id,
                    generation=skill.generation,
                    fitness=fitness,
                    maturity=skill.maturity,
                    traits=skill.traits,
                )
            )

    # Atomic-mode fallback: genomes are linked via skill_genomes.run_id
    # without nesting under run.generations. Query the table directly for
    # any genomes not already captured above.
    if not nodes or getattr(run, "evolution_mode", "molecular") == "atomic":
        from skillforge.db.queries import _connect, _row_to_genome

        async with _connect() as conn, conn.execute(
            "SELECT * FROM skill_genomes WHERE run_id = ? ORDER BY generation, id",
            (run_id,),
        ) as cur:
            rows = await cur.fetchall()
        for row in rows:
            genome = _row_to_genome(row)
            if genome.id in seen_ids:
                continue
            seen_ids.add(genome.id)
            fitness = (
                sum(genome.pareto_objectives.values()) / len(genome.pareto_objectives)
                if genome.pareto_objectives
                else 0.0
            )
            nodes.append(
                LineageNode(
                    id=genome.id,
                    generation=genome.generation,
                    fitness=fitness,
                    maturity=genome.maturity,
                    traits=genome.traits,
                )
            )

    return {
        "nodes": [n.model_dump() for n in nodes],
        "edges": [e.model_dump() for e in edges],
    }


@router.get("/runs/{run_id}/skills/{skill_id}")
async def get_run_skill(run_id: str, skill_id: str) -> dict:
    """Return the full SKILL.md + metadata for one genome in a run.

    Used by the SkillDiffViewer to render parent/child side-by-side.

    Looks up the genome first in ``run.generations[].skills[]`` (molecular
    mode), then falls back to a direct ``skill_genomes`` table query scoped
    by ``run_id`` (atomic mode, where genomes live outside the generations
    tree and are linked only via ``skill_genomes.run_id``).
    """
    run = await get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")

    def _skill_to_dict(skill: SkillGenome) -> dict:
        return {
            "id": skill.id,
            "generation": skill.generation,
            "skill_md_content": skill.skill_md_content,
            "supporting_files": skill.supporting_files or {},
            "traits": skill.traits,
            "maturity": skill.maturity,
            "parent_ids": skill.parent_ids,
            "mutations": skill.mutations,
            "mutation_rationale": skill.mutation_rationale,
            "pareto_objectives": skill.pareto_objectives,
        }

    for gen in run.generations:
        for skill in gen.skills:
            if skill.id == skill_id:
                return _skill_to_dict(skill)

    # Atomic-mode fallback: genomes are linked to the run via
    # skill_genomes.run_id without nesting under run.generations.
    from skillforge.db.queries import _connect, _row_to_genome

    async with _connect() as conn, conn.execute(
        "SELECT * FROM skill_genomes WHERE id = ? AND run_id = ?",
        (skill_id, run_id),
    ) as cur:
        row = await cur.fetchone()
    if row is not None:
        return _skill_to_dict(_row_to_genome(row))

    raise HTTPException(
        status_code=404, detail=f"skill {skill_id} not found in run {run_id}"
    )
