"""Tests for internal dataclasses (Step 3)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from skillforge.models import (
    Challenge,
    CompetitionResult,
    EvolutionRun,
    Generation,
    SkillGenome,
)
from skillforge.models._serde import from_iso, to_iso


def test_imports():
    """All model classes import cleanly."""
    assert SkillGenome and Challenge and Generation and EvolutionRun and CompetitionResult


def test_skill_genome_instantiates_with_minimal_args():
    g = SkillGenome(id="g1", generation=0, skill_md_content="")
    assert g.id == "g1"
    assert g.maturity == "draft"
    assert g.traits == []
    assert g.trigger_precision == 0.0
    assert g.consistency_score is None


def _make_skill_genome(genome_id: str = "sg-1") -> SkillGenome:
    return SkillGenome(
        id=genome_id,
        generation=2,
        skill_md_content="# My Skill\n\nDoes things.",
        frontmatter={"name": "my-skill", "version": "1.0"},
        supporting_files={"helper.py": "print('hi')"},
        traits=["concise", "structured"],
        meta_strategy="breadth-first",
        parent_ids=["sg-0a", "sg-0b"],
        mutations=["added example"],
        mutation_rationale="improves trigger recall",
        maturity="tested",
        generations_survived=1,
        deterministic_scores={"lint": 0.9, "tests": 1.0},
        trigger_precision=0.85,
        trigger_recall=0.78,
        behavioral_signature=["used_tool:Read", "used_tool:Write"],
        pareto_objectives={"quality": 0.9, "efficiency": 0.7},
        is_pareto_optimal=True,
        trait_attribution={"concise": 0.6, "structured": 0.3},
        trait_diagnostics={"concise": "reduces verbosity"},
        consistency_score=0.92,
    )


def _make_challenge(cid: str = "ch-1") -> Challenge:
    return Challenge(
        id=cid,
        prompt="Write a function that reverses a string.",
        difficulty="easy",
        evaluation_criteria={"correctness": 1.0, "style": 0.5},
        verification_method="run_tests",
        setup_files={"test_reverse.py": "assert reverse('abc') == 'cba'"},
        gold_standard_hints="use slicing",
    )


def _make_competition_result(skill_id: str = "sg-1", challenge_id: str = "ch-1") -> CompetitionResult:
    return CompetitionResult(
        skill_id=skill_id,
        challenge_id=challenge_id,
        output_files={"output.py": "def reverse(s): return s[::-1]"},
        trace=[{"role": "user", "content": "Do it"}, {"role": "assistant", "content": "Done"}],
        compiles=True,
        tests_pass=True,
        lint_score=0.95,
        perf_metrics={"latency_ms": 120.0},
        trigger_precision=0.88,
        trigger_recall=0.80,
        skill_was_loaded=True,
        instructions_followed=["step 1", "step 2"],
        instructions_ignored=["optional step"],
        ignored_diagnostics={"optional step": "not relevant"},
        scripts_executed=["setup.sh"],
        behavioral_signature=["used_tool:Bash"],
        pairwise_wins={"sg-2": 1},
        pareto_objectives={"quality": 0.9},
        trait_contribution={"concise": 0.5},
        trait_diagnostics={"concise": "good"},
        judge_reasoning="Well done.",
    )


def test_skill_genome_roundtrip():
    original = _make_skill_genome()
    restored = SkillGenome.from_dict(original.to_dict())
    assert original == restored


def test_challenge_roundtrip():
    original = _make_challenge()
    restored = Challenge.from_dict(original.to_dict())
    assert original == restored


def test_competition_result_roundtrip():
    # tests_pass=True case
    original = _make_competition_result()
    assert original.tests_pass is True
    restored = CompetitionResult.from_dict(original.to_dict())
    assert original == restored

    # tests_pass=None case
    original_none = _make_competition_result()
    original_none.tests_pass = None
    original_none.lint_score = None
    restored_none = CompetitionResult.from_dict(original_none.to_dict())
    assert restored_none.tests_pass is None
    assert restored_none.lint_score is None
    assert original_none == restored_none


def test_generation_roundtrip_with_nested():
    g1 = _make_skill_genome("sg-1")
    g2 = _make_skill_genome("sg-2")
    r1 = _make_competition_result("sg-1", "ch-1")
    r2 = _make_competition_result("sg-2", "ch-1")
    r3 = _make_competition_result("sg-1", "ch-2")

    gen = Generation(
        number=1,
        skills=[g1, g2],
        results=[r1, r2, r3],
        pareto_front=["sg-1"],
        breeding_report="Generation 1 complete.",
        learning_log_entries=["trait X survived"],
        best_fitness=0.91,
        avg_fitness=0.75,
        trait_survival={"concise": True, "structured": False},
        trait_emergence=["new-trait"],
    )

    restored = Generation.from_dict(gen.to_dict())
    assert gen == restored
    assert len(restored.skills) == 2
    assert len(restored.results) == 3
    assert restored.skills[0] == g1
    assert restored.skills[1] == g2


def test_evolution_run_roundtrip_full():
    created = datetime(2026, 4, 8, 12, 0, 0, tzinfo=UTC)
    completed = datetime(2026, 4, 8, 14, 30, 0, tzinfo=UTC)

    ch1 = _make_challenge("ch-1")
    ch2 = _make_challenge("ch-2")

    sg1 = _make_skill_genome("sg-1")
    sg2 = _make_skill_genome("sg-2")
    sg3 = _make_skill_genome("sg-3")

    r1 = _make_competition_result("sg-1", "ch-1")
    r2 = _make_competition_result("sg-2", "ch-1")

    gen1 = Generation(number=0, skills=[sg1, sg2], results=[r1, r2])
    gen2 = Generation(number=1, skills=[sg3], results=[])

    best = _make_skill_genome("sg-best")
    pareto_a = _make_skill_genome("sg-pa")
    pareto_b = _make_skill_genome("sg-pb")

    run = EvolutionRun(
        id="run-1",
        mode="domain",
        specialization="python code review",
        population_size=5,
        num_generations=3,
        challenges=[ch1, ch2],
        generations=[gen1, gen2],
        learning_log=["lesson 1", "lesson 2"],
        status="complete",
        created_at=created,
        completed_at=completed,
        best_skill=best,
        pareto_front=[pareto_a, pareto_b],
        total_cost_usd=2.45,
    )

    restored = EvolutionRun.from_dict(run.to_dict())
    assert run == restored
    assert restored.created_at == created
    assert restored.completed_at == completed
    assert restored.best_skill == best
    assert len(restored.pareto_front) == 2
    assert len(restored.challenges) == 2
    assert len(restored.generations) == 2
    assert restored.generations[0].skills[0] == sg1


def test_evolution_run_json_serializable():
    created = datetime(2026, 4, 8, 12, 0, 0, tzinfo=UTC)
    completed = datetime(2026, 4, 8, 14, 30, 0, tzinfo=UTC)

    run = EvolutionRun(
        id="run-json",
        mode="domain",
        specialization="json test",
        challenges=[_make_challenge("ch-1"), _make_challenge("ch-2")],
        generations=[
            Generation(
                number=0,
                skills=[_make_skill_genome("sg-1"), _make_skill_genome("sg-2")],
                results=[_make_competition_result("sg-1", "ch-1")],
            )
        ],
        learning_log=["entry 1"],
        status="complete",
        created_at=created,
        completed_at=completed,
        best_skill=_make_skill_genome("sg-best"),
        pareto_front=[_make_skill_genome("sg-pa"), _make_skill_genome("sg-pb")],
        total_cost_usd=1.23,
    )

    serialized = run.to_dict()
    # Must not raise
    result = json.dumps(serialized)
    assert isinstance(result, str)


def test_default_factory_independence():
    g1 = SkillGenome(id="a", generation=0, skill_md_content="")
    g2 = SkillGenome(id="b", generation=0, skill_md_content="")
    g1.traits.append("x")
    assert g2.traits == []


def test_datetime_handling():
    # Round-trip with timezone-aware datetime
    dt = datetime.now(UTC)
    iso = to_iso(dt)
    assert isinstance(iso, str)
    restored = from_iso(iso)
    assert restored == dt

    # None passes through as None
    assert to_iso(None) is None
    assert from_iso(None) is None

    # Naive datetime also works
    naive = datetime(2026, 1, 1, 0, 0, 0)
    iso_naive = to_iso(naive)
    assert from_iso(iso_naive) == naive
