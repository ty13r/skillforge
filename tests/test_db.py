"""Database layer tests — Step 4.

All tests are async (pytest-asyncio, asyncio_mode = "auto").
Every test takes ``temp_db_path`` and never touches the real ``DB_PATH``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from skillforge.db import (
    get_connection,
    get_lineage,
    get_run,
    init_db,
    list_runs,
    reset_db,
    save_generation,
    save_genome,
    save_run,
)
from skillforge.models import (
    Challenge,
    CompetitionResult,
    EvolutionRun,
    Generation,
    SkillGenome,
)

# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------


def make_genome(
    generation: int = 0,
    parent_ids: list[str] | None = None,
    *,
    gid: str | None = None,
) -> SkillGenome:
    return SkillGenome(
        id=gid or str(uuid.uuid4()),
        generation=generation,
        skill_md_content="# Test Skill\nDoes something useful.",
        frontmatter={"name": "TestSkill", "version": "0.1.0", "tags": ["test"]},
        supporting_files={"scripts/run.sh": "#!/bin/bash\necho hello"},
        traits=["fast", "accurate", "robust"],
        meta_strategy="greedy search with backtracking",
        parent_ids=parent_ids or [],
        mutations=["widened search radius", "added retry"],
        mutation_rationale="coverage was low",
        maturity="tested",
        generations_survived=2,
        deterministic_scores={"compile": 1.0, "lint": 0.85},
        trigger_precision=0.92,
        trigger_recall=0.88,
        behavioral_signature=["load_skill", "invoke_tool", "return_result"],
        pareto_objectives={"quality": 0.9, "speed": 0.7},
        is_pareto_optimal=True,
        trait_attribution={"fast": 0.6, "accurate": 0.4},
        trait_diagnostics={"fast": "uses cache", "accurate": "verifies output"},
        consistency_score=None,
    )


def make_challenge(cid: str | None = None) -> Challenge:
    return Challenge(
        id=cid or str(uuid.uuid4()),
        prompt="Write a function that reverses a string.",
        difficulty="easy",
        evaluation_criteria={"correctness": 0.6, "efficiency": 0.4},
        verification_method="run_tests",
        setup_files={"test_solution.py": "def test_reverse(): assert reverse('abc') == 'cba'"},
        gold_standard_hints="Use slicing: s[::-1]",
    )


def make_result(skill_id: str, challenge_id: str) -> CompetitionResult:
    return CompetitionResult(
        skill_id=skill_id,
        challenge_id=challenge_id,
        output_files={"solution.py": "def reverse(s): return s[::-1]"},
        trace=[{"role": "assistant", "content": "Here is the solution"}],
        compiles=True,
        tests_pass=True,
        lint_score=9.5,
        perf_metrics={"runtime_ms": 1.2},
        trigger_precision=0.95,
        trigger_recall=0.90,
        skill_was_loaded=True,
        instructions_followed=["write function", "use docstring"],
        instructions_ignored=[],
        ignored_diagnostics={},
        scripts_executed=["run_tests.sh"],
        behavioral_signature=["read_prompt", "write_code", "run_tests"],
        pairwise_wins={"correctness": 3},
        pareto_objectives={"correctness": 1.0, "efficiency": 0.8},
        trait_contribution={"fast": 0.5, "accurate": 0.5},
        trait_diagnostics={"fast": "O(1) slicing", "accurate": "handles unicode"},
        judge_reasoning="Clean, idiomatic solution.",
    )


def make_run(
    *,
    run_id: str | None = None,
    created_at: datetime | None = None,
    status: str = "complete",
    num_challenges: int = 2,
    num_generations: int = 2,
    include_best: bool = True,
) -> EvolutionRun:
    rid = run_id or str(uuid.uuid4())
    challenges = [make_challenge() for _ in range(num_challenges)]

    generations: list[Generation] = []
    all_skills: list[SkillGenome] = []

    for gen_num in range(num_generations):
        skills = [make_genome(generation=gen_num) for _ in range(2)]
        all_skills.extend(skills)
        results = [
            make_result(sk.id, ch.id)
            for sk in skills
            for ch in challenges
        ]
        gen = Generation(
            number=gen_num,
            skills=skills,
            results=results,
            pareto_front=[skills[0].id],
            breeding_report=f"Gen {gen_num} report",
            learning_log_entries=[f"lesson {gen_num}"],
            best_fitness=0.9,
            avg_fitness=0.75,
            trait_survival={"fast": True, "accurate": True},
            trait_emergence=["new_trait"] if gen_num > 0 else [],
        )
        generations.append(gen)

    best = all_skills[0] if include_best else None
    pareto = all_skills[:2] if all_skills else []

    return EvolutionRun(
        id=rid,
        mode="domain",
        specialization="string manipulation",
        population_size=2,
        num_generations=num_generations,
        challenges=challenges,
        generations=generations,
        learning_log=["lesson A", "lesson B"],
        status=status,
        created_at=created_at or datetime.now(UTC),
        completed_at=datetime.now(UTC) if status == "complete" else None,
        best_skill=best,
        pareto_front=pareto,
        total_cost_usd=0.42,
    )


# ---------------------------------------------------------------------------
# Test 1: init_db creates all 5 tables
# ---------------------------------------------------------------------------


async def test_init_db_creates_all_tables(temp_db_path):
    await init_db(temp_db_path)
    conn = await get_connection(temp_db_path)
    try:
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ) as cur:
            names = {row["name"] async for row in cur}
    finally:
        await conn.close()

    expected = {
        "evolution_runs",
        "challenges",
        "skill_genomes",
        "generations",
        "competition_results",
    }
    assert expected.issubset(names), f"Missing tables: {expected - names}"


# ---------------------------------------------------------------------------
# Test 2: foreign keys enabled
# ---------------------------------------------------------------------------


async def test_foreign_keys_enabled(temp_db_path):
    await init_db(temp_db_path)
    conn = await get_connection(temp_db_path)
    try:
        async with conn.execute("PRAGMA foreign_keys") as cur:
            row = await cur.fetchone()
    finally:
        await conn.close()
    assert row is not None
    assert row[0] == 1


# ---------------------------------------------------------------------------
# Test 3: save and get a SkillGenome via round-trip
# ---------------------------------------------------------------------------


async def test_save_and_get_skill_genome(temp_db_path):
    await init_db(temp_db_path)

    # Need a run row first (genome has FK → evolution_runs)
    run = make_run(num_challenges=1, num_generations=0, include_best=False)
    run.generations = []  # no generations, just the run shell
    run.pareto_front = []
    run.challenges = []
    await save_run(run, temp_db_path)

    genome = make_genome(generation=0)
    await save_genome(genome, run.id, temp_db_path)

    fetched_run = await get_run(run.id, temp_db_path)
    assert fetched_run is not None
    # The genome is reachable via get_run only if attached to a generation.
    # Test genome directly via save_genome + get_run after adding a generation:
    gen = Generation(
        number=0,
        skills=[genome],
        results=[],
        pareto_front=[genome.id],
        breeding_report="",
        learning_log_entries=[],
        best_fitness=0.9,
        avg_fitness=0.9,
        trait_survival={},
        trait_emergence=[],
    )
    await save_generation(gen, run.id, temp_db_path)

    run2 = await get_run(run.id, temp_db_path)
    assert run2 is not None
    assert len(run2.generations) == 1
    fetched_genomes = run2.generations[0].skills
    assert len(fetched_genomes) == 1
    fetched = fetched_genomes[0]

    assert fetched.id == genome.id
    assert fetched.generation == genome.generation
    assert fetched.traits == genome.traits
    assert fetched.frontmatter == genome.frontmatter
    assert fetched.pareto_objectives == genome.pareto_objectives
    assert fetched.is_pareto_optimal == genome.is_pareto_optimal
    assert fetched.consistency_score == genome.consistency_score


# ---------------------------------------------------------------------------
# Test 4: save and get EvolutionRun with full nested tree
# ---------------------------------------------------------------------------


async def test_save_and_get_evolution_run_with_nested(temp_db_path):
    await init_db(temp_db_path)
    run = make_run(num_challenges=2, num_generations=2)
    await save_run(run, temp_db_path)

    fetched = await get_run(run.id, temp_db_path)
    assert fetched is not None

    assert fetched.id == run.id
    assert fetched.mode == run.mode
    assert fetched.specialization == run.specialization
    assert fetched.status == run.status
    assert len(fetched.challenges) == len(run.challenges)
    assert len(fetched.generations) == len(run.generations)
    assert fetched.best_skill is not None
    assert fetched.best_skill.id == run.best_skill.id  # type: ignore[union-attr]
    assert len(fetched.pareto_front) == len(run.pareto_front)

    for orig_gen, fetched_gen in zip(run.generations, fetched.generations, strict=True):
        assert fetched_gen.number == orig_gen.number
        assert fetched_gen.best_fitness == orig_gen.best_fitness
        assert fetched_gen.pareto_front == orig_gen.pareto_front
        assert len(fetched_gen.skills) == len(orig_gen.skills)
        assert len(fetched_gen.results) == len(orig_gen.results)


# ---------------------------------------------------------------------------
# Test 5: list_runs orders by created_at DESC
# ---------------------------------------------------------------------------


async def test_list_runs_orders_by_created_at_desc(temp_db_path):
    await init_db(temp_db_path)

    t1 = datetime(2024, 1, 1, tzinfo=UTC)
    t2 = datetime(2024, 6, 1, tzinfo=UTC)
    t3 = datetime(2025, 1, 1, tzinfo=UTC)

    run1 = make_run(created_at=t1, num_challenges=1, num_generations=0, include_best=False)
    run1.generations = []
    run1.pareto_front = []

    run2 = make_run(created_at=t2, num_challenges=1, num_generations=0, include_best=False)
    run2.generations = []
    run2.pareto_front = []

    run3 = make_run(created_at=t3, num_challenges=1, num_generations=0, include_best=False)
    run3.generations = []
    run3.pareto_front = []

    for r in [run1, run2, run3]:
        r.challenges = []
        await save_run(r, temp_db_path)

    runs = await list_runs(db_path=temp_db_path)
    assert len(runs) == 3
    # Most recent first
    assert runs[0].id == run3.id
    assert runs[1].id == run2.id
    assert runs[2].id == run1.id


# ---------------------------------------------------------------------------
# Test 6: get_run returns None for missing ID
# ---------------------------------------------------------------------------


async def test_get_run_returns_none_for_missing(temp_db_path):
    await init_db(temp_db_path)
    result = await get_run("nonexistent-id-xyz", temp_db_path)
    assert result is None


# ---------------------------------------------------------------------------
# Test 7: get_lineage returns parent→child edges
# ---------------------------------------------------------------------------


async def test_get_lineage_returns_parent_child_edges(temp_db_path):
    await init_db(temp_db_path)

    parent_a = make_genome(generation=0)
    parent_b = make_genome(generation=0)
    child = make_genome(generation=1, parent_ids=[parent_a.id, parent_b.id])

    run = make_run(num_challenges=0, num_generations=0, include_best=False)
    run.challenges = []
    run.generations = []
    run.pareto_front = []
    await save_run(run, temp_db_path)

    gen0 = Generation(
        number=0,
        skills=[parent_a, parent_b],
        results=[],
        pareto_front=[],
        breeding_report="",
        learning_log_entries=[],
        best_fitness=0.0,
        avg_fitness=0.0,
        trait_survival={},
        trait_emergence=[],
    )
    gen1 = Generation(
        number=1,
        skills=[child],
        results=[],
        pareto_front=[],
        breeding_report="",
        learning_log_entries=[],
        best_fitness=0.0,
        avg_fitness=0.0,
        trait_survival={},
        trait_emergence=[],
    )
    await save_generation(gen0, run.id, temp_db_path)
    await save_generation(gen1, run.id, temp_db_path)

    edges = await get_lineage(run.id, temp_db_path)

    assert len(edges) == 2
    child_ids = {e["child_id"] for e in edges}
    parent_ids_in_edges = {e["parent_id"] for e in edges}
    assert child_ids == {child.id}
    assert parent_ids_in_edges == {parent_a.id, parent_b.id}
    for e in edges:
        assert e["generation"] == 1


# ---------------------------------------------------------------------------
# Test 8: reset_db clears tables
# ---------------------------------------------------------------------------


async def test_reset_db_clears_tables(temp_db_path):
    await init_db(temp_db_path)
    run = make_run(num_challenges=1, num_generations=0, include_best=False)
    run.generations = []
    run.challenges = []
    run.pareto_front = []
    await save_run(run, temp_db_path)

    runs_before = await list_runs(db_path=temp_db_path)
    assert len(runs_before) == 1

    await reset_db(temp_db_path)

    runs_after = await list_runs(db_path=temp_db_path)
    assert runs_after == []


# ---------------------------------------------------------------------------
# Test 9: save_run overwrites on same ID
# ---------------------------------------------------------------------------


async def test_save_run_overwrites_on_same_id(temp_db_path):
    await init_db(temp_db_path)
    run = make_run(status="pending", num_challenges=1, num_generations=0, include_best=False)
    run.generations = []
    run.challenges = []
    run.pareto_front = []
    await save_run(run, temp_db_path)

    fetched1 = await get_run(run.id, temp_db_path)
    assert fetched1 is not None
    assert fetched1.status == "pending"

    run.status = "complete"
    await save_run(run, temp_db_path)

    fetched2 = await get_run(run.id, temp_db_path)
    assert fetched2 is not None
    assert fetched2.status == "complete"


# ---------------------------------------------------------------------------
# Test 10: JSON column round-trip for complex data
# ---------------------------------------------------------------------------


async def test_json_columns_round_trip_complex_data(temp_db_path):
    await init_db(temp_db_path)

    genome = SkillGenome(
        id=str(uuid.uuid4()),
        generation=0,
        skill_md_content="# Complex Skill",
        frontmatter={
            "name": "Complex",
            "nested": {"deep": [1, 2, 3], "flag": True},
        },
        supporting_files={
            "scripts/a.sh": "#!/bin/bash\necho a",
            "references/doc.md": "# Reference\nSome text.",
        },
        traits=["trait_alpha", "trait_beta", "trait_gamma"],
        meta_strategy="hierarchical decomposition",
        parent_ids=["parent-1", "parent-2"],
        mutations=["mutation A", "mutation B"],
        mutation_rationale="exploration vs exploitation",
        maturity="hardened",
        generations_survived=5,
        deterministic_scores={"compile": 1.0, "test": 0.95, "lint": 0.88},
        trigger_precision=0.99,
        trigger_recall=0.97,
        behavioral_signature=["step1", "step2", "step3", "step4"],
        pareto_objectives={"quality": 0.95, "speed": 0.80, "cost": 0.60},
        is_pareto_optimal=True,
        trait_attribution={"trait_alpha": 0.5, "trait_beta": 0.3, "trait_gamma": 0.2},
        trait_diagnostics={
            "trait_alpha": "dominates in quality",
            "trait_beta": "speeds up stage 2",
            "trait_gamma": "reduces overhead",
        },
        consistency_score=0.93,
    )

    run = make_run(num_challenges=0, num_generations=0, include_best=False)
    run.challenges = []
    run.generations = []
    run.pareto_front = []
    await save_run(run, temp_db_path)

    gen = Generation(
        number=0,
        skills=[genome],
        results=[],
        pareto_front=[genome.id],
        breeding_report="complex report",
        learning_log_entries=["entry 1"],
        best_fitness=0.95,
        avg_fitness=0.80,
        trait_survival={"trait_alpha": True, "trait_beta": False},
        trait_emergence=["new_complex_trait"],
    )
    await save_generation(gen, run.id, temp_db_path)

    fetched_run = await get_run(run.id, temp_db_path)
    assert fetched_run is not None
    assert len(fetched_run.generations) == 1

    fetched_gen = fetched_run.generations[0]
    assert fetched_gen.trait_survival == {"trait_alpha": True, "trait_beta": False}
    assert fetched_gen.trait_emergence == ["new_complex_trait"]

    assert len(fetched_gen.skills) == 1
    g = fetched_gen.skills[0]

    assert g.frontmatter == genome.frontmatter
    assert g.supporting_files == genome.supporting_files
    assert g.traits == genome.traits
    assert g.parent_ids == genome.parent_ids
    assert g.mutations == genome.mutations
    assert g.deterministic_scores == genome.deterministic_scores
    assert g.behavioral_signature == genome.behavioral_signature
    assert g.pareto_objectives == genome.pareto_objectives
    assert g.is_pareto_optimal == genome.is_pareto_optimal
    assert g.trait_attribution == genome.trait_attribution
    assert g.trait_diagnostics == genome.trait_diagnostics
    assert g.consistency_score == pytest.approx(0.93)
