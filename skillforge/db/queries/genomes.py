"""CRUD for SkillGenome, CompetitionResult, and Generation rows.

Grouped into one module because these three entities are the per-generation
payload of an EvolutionRun — a Generation owns a list of Skill genomes and
a list of Competition results, all indexed by ``(run_id, generation)``.
"""

from __future__ import annotations

import json
from pathlib import Path

import aiosqlite

from skillforge.db.queries._helpers import _connect, _int_or_none, _row_get
from skillforge.models import CompetitionResult, Generation, SkillGenome


async def save_genome(
    genome: SkillGenome,
    run_id: str,
    db_path: Path | None = None,
) -> None:
    """Upsert a SkillGenome row linked to ``run_id``."""
    d = genome.to_dict()
    async with _connect(db_path) as conn:
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
                maturity=excluded.maturity,
                generations_survived=excluded.generations_survived,
                deterministic_scores=excluded.deterministic_scores,
                trigger_precision=excluded.trigger_precision,
                trigger_recall=excluded.trigger_recall,
                behavioral_signature=excluded.behavioral_signature,
                pareto_objectives=excluded.pareto_objectives,
                is_pareto_optimal=excluded.is_pareto_optimal,
                trait_attribution=excluded.trait_attribution,
                trait_diagnostics=excluded.trait_diagnostics,
                consistency_score=excluded.consistency_score,
                variant_id=excluded.variant_id
            """,
            (
                d["id"],
                run_id,
                d["generation"],
                d["skill_md_content"],
                json.dumps(d["frontmatter"]),
                json.dumps(d["supporting_files"]),
                json.dumps(d["traits"]),
                d["meta_strategy"],
                json.dumps(d["parent_ids"]),
                json.dumps(d["mutations"]),
                d["mutation_rationale"],
                d["maturity"],
                d["generations_survived"],
                json.dumps(d["deterministic_scores"]),
                d["trigger_precision"],
                d["trigger_recall"],
                json.dumps(d["behavioral_signature"]),
                json.dumps(d["pareto_objectives"]),
                int(d["is_pareto_optimal"]),
                json.dumps(d["trait_attribution"]),
                json.dumps(d["trait_diagnostics"]),
                d["consistency_score"],
                d.get("variant_id"),
            ),
        )
        await conn.commit()


async def _get_genome_by_id(
    genome_id: str,
    conn: aiosqlite.Connection,
) -> SkillGenome | None:
    async with conn.execute(
        "SELECT * FROM skill_genomes WHERE id = ?", (genome_id,)
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        return None
    return _row_to_genome(row)


async def _get_genomes_for_run_gen(
    run_id: str,
    generation: int,
    conn: aiosqlite.Connection,
) -> list[SkillGenome]:
    async with conn.execute(
        "SELECT * FROM skill_genomes WHERE run_id = ? AND generation = ?",
        (run_id, generation),
    ) as cur:
        rows = await cur.fetchall()
    return [_row_to_genome(r) for r in rows]


def _row_to_genome(row: aiosqlite.Row) -> SkillGenome:
    d = {
        "id": row["id"],
        "generation": row["generation"],
        "skill_md_content": row["skill_md_content"],
        "frontmatter": json.loads(row["frontmatter"]),
        "supporting_files": json.loads(row["supporting_files"]),
        "traits": json.loads(row["traits"]),
        "meta_strategy": row["meta_strategy"],
        "parent_ids": json.loads(row["parent_ids"]),
        "mutations": json.loads(row["mutations"]),
        "mutation_rationale": row["mutation_rationale"],
        "maturity": row["maturity"],
        "generations_survived": row["generations_survived"],
        "deterministic_scores": json.loads(row["deterministic_scores"]),
        "trigger_precision": row["trigger_precision"],
        "trigger_recall": row["trigger_recall"],
        "behavioral_signature": json.loads(row["behavioral_signature"]),
        "pareto_objectives": json.loads(row["pareto_objectives"]),
        "is_pareto_optimal": bool(row["is_pareto_optimal"]),
        "trait_attribution": json.loads(row["trait_attribution"]),
        "trait_diagnostics": json.loads(row["trait_diagnostics"]),
        "consistency_score": row["consistency_score"],
        "variant_id": _row_get(row, "variant_id"),
    }
    return SkillGenome.from_dict(d)


# ---------------------------------------------------------------------------
# CompetitionResult
# ---------------------------------------------------------------------------


async def save_result(
    result: CompetitionResult,
    run_id: str,
    generation: int,
    db_path: Path | None = None,
) -> None:
    """Upsert a CompetitionResult row."""
    d = result.to_dict()
    async with _connect(db_path) as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO competition_results
                (skill_id, challenge_id, run_id, generation,
                 output_files, trace, compiles, tests_pass, lint_score,
                 perf_metrics, trigger_precision, trigger_recall,
                 skill_was_loaded, instructions_followed, instructions_ignored,
                 ignored_diagnostics, scripts_executed, behavioral_signature,
                 pairwise_wins, pareto_objectives, trait_contribution,
                 trait_diagnostics, judge_reasoning)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                d["skill_id"],
                d["challenge_id"],
                run_id,
                generation,
                json.dumps(d["output_files"]),
                json.dumps(d["trace"]),
                int(d["compiles"]),
                _int_or_none(d["tests_pass"]),
                d["lint_score"],
                json.dumps(d["perf_metrics"]),
                d["trigger_precision"],
                d["trigger_recall"],
                int(d["skill_was_loaded"]),
                json.dumps(d["instructions_followed"]),
                json.dumps(d["instructions_ignored"]),
                json.dumps(d["ignored_diagnostics"]),
                json.dumps(d["scripts_executed"]),
                json.dumps(d["behavioral_signature"]),
                json.dumps(d["pairwise_wins"]),
                json.dumps(d["pareto_objectives"]),
                json.dumps(d["trait_contribution"]),
                json.dumps(d["trait_diagnostics"]),
                d["judge_reasoning"],
            ),
        )
        await conn.commit()


async def _get_results_for_run_gen(
    run_id: str,
    generation: int,
    conn: aiosqlite.Connection,
) -> list[CompetitionResult]:
    async with conn.execute(
        "SELECT * FROM competition_results WHERE run_id = ? AND generation = ?",
        (run_id, generation),
    ) as cur:
        rows = await cur.fetchall()
    return [_row_to_result(r) for r in rows]


def _row_to_result(row: aiosqlite.Row) -> CompetitionResult:
    raw_tests_pass = row["tests_pass"]
    d = {
        "skill_id": row["skill_id"],
        "challenge_id": row["challenge_id"],
        "output_files": json.loads(row["output_files"]),
        "trace": json.loads(row["trace"]),
        "compiles": bool(row["compiles"]),
        "tests_pass": bool(raw_tests_pass) if raw_tests_pass is not None else None,
        "lint_score": row["lint_score"],
        "perf_metrics": json.loads(row["perf_metrics"]),
        "trigger_precision": row["trigger_precision"],
        "trigger_recall": row["trigger_recall"],
        "skill_was_loaded": bool(row["skill_was_loaded"]),
        "instructions_followed": json.loads(row["instructions_followed"]),
        "instructions_ignored": json.loads(row["instructions_ignored"]),
        "ignored_diagnostics": json.loads(row["ignored_diagnostics"]),
        "scripts_executed": json.loads(row["scripts_executed"]),
        "behavioral_signature": json.loads(row["behavioral_signature"]),
        "pairwise_wins": json.loads(row["pairwise_wins"]),
        "pareto_objectives": json.loads(row["pareto_objectives"]),
        "trait_contribution": json.loads(row["trait_contribution"]),
        "trait_diagnostics": json.loads(row["trait_diagnostics"]),
        "judge_reasoning": row["judge_reasoning"],
    }
    return CompetitionResult.from_dict(d)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


async def save_generation(
    generation: Generation,
    run_id: str,
    db_path: Path | None = None,
) -> None:
    """Upsert a Generation row and all its nested skills and results."""
    d = generation.to_dict()
    async with _connect(db_path) as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO generations
                (run_id, number, pareto_front, breeding_report,
                 learning_log_entries, best_fitness, avg_fitness,
                 trait_survival, trait_emergence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                d["number"],
                json.dumps(d["pareto_front"]),
                d["breeding_report"],
                json.dumps(d["learning_log_entries"]),
                d["best_fitness"],
                d["avg_fitness"],
                json.dumps(d["trait_survival"]),
                json.dumps(d["trait_emergence"]),
            ),
        )
        await conn.commit()

    # Save nested skills and results using their own connections
    for skill in generation.skills:
        await save_genome(skill, run_id, db_path)
    for result in generation.results:
        await save_result(result, run_id, generation.number, db_path)


async def _get_generations_for_run(
    run_id: str,
    conn: aiosqlite.Connection,
) -> list[Generation]:
    async with conn.execute(
        "SELECT * FROM generations WHERE run_id = ? ORDER BY number",
        (run_id,),
    ) as cur:
        rows = await cur.fetchall()

    generations = []
    for row in rows:
        gen_number = row["number"]
        skills = await _get_genomes_for_run_gen(run_id, gen_number, conn)
        results = await _get_results_for_run_gen(run_id, gen_number, conn)
        d = {
            "number": gen_number,
            "skills": [s.to_dict() for s in skills],
            "results": [r.to_dict() for r in results],
            "pareto_front": json.loads(row["pareto_front"]),
            "breeding_report": row["breeding_report"],
            "learning_log_entries": json.loads(row["learning_log_entries"]),
            "best_fitness": row["best_fitness"],
            "avg_fitness": row["avg_fitness"],
            "trait_survival": json.loads(row["trait_survival"]),
            "trait_emergence": json.loads(row["trait_emergence"]),
        }
        generations.append(Generation.from_dict(d))
    return generations

