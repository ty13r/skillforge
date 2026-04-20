"""Tests for the judging pipeline orchestrator (Step 6d pipeline.py).

Individual judge layers have their own test files (tests/test_judge_*.py).
This file tests only the pipeline's wiring: does it call every layer in
order, does it aggregate per-skill scores correctly, does it compute
generation-level fitness?

All LLM-dependent layers (L2, L3's diagnosis, L4 ranking, L5) are mocked.
L1 runs for real (it's just subprocess calls — fast and local).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from skillforge.agents.judge.pipeline import run_judging_pipeline
from skillforge.models import (
    Challenge,
    CompetitionResult,
    Generation,
    SkillGenome,
)

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _valid_skill_md(name: str = "my-skill") -> str:
    return f"""---
name: {name}
description: >-
  Does things. Use when you need things done, even if you don't ask for {name}.
  NOT for other stuff.
---

# Skill

## Quick start
Do the thing.

## Workflow

### Step 1: Read context
Do this.

### Step 2: Execute
Do that.

## Examples

**Example 1:** Input: x / Output: y
**Example 2:** Input: a / Output: b
"""


def _make_skill(skill_id: str, traits: list[str] | None = None) -> SkillGenome:
    return SkillGenome(
        id=skill_id,
        generation=0,
        skill_md_content=_valid_skill_md(name=f"skill-{skill_id}"),
        traits=traits or ["concise", "structured"],
    )


def _make_challenge(challenge_id: str) -> Challenge:
    return Challenge(
        id=challenge_id,
        prompt="Write a function.",
        difficulty="easy",
        evaluation_criteria={"correctness": 1.0},
        verification_method="run_tests",
        setup_files={},
        gold_standard_hints="keep it simple",
    )


def _make_result(
    skill_id: str,
    challenge_id: str,
    *,
    output: dict[str, str] | None = None,
    trace: list[dict] | None = None,
) -> CompetitionResult:
    return CompetitionResult(
        skill_id=skill_id,
        challenge_id=challenge_id,
        output_files=output or {"solution.py": "def f(): return 1\n"},
        trace=trace or [{"type": "AssistantMessage", "content": []}],
    )


def _make_generation(n_skills: int = 2, n_challenges: int = 1) -> tuple[Generation, list[Challenge]]:
    skills = [_make_skill(f"sk-{i}") for i in range(n_skills)]
    challenges = [_make_challenge(f"ch-{j}") for j in range(n_challenges)]
    results = [
        _make_result(s.id, c.id) for s in skills for c in challenges
    ]
    gen = Generation(number=0, skills=skills, results=results)
    return gen, challenges


# ---------------------------------------------------------------------------
# Patches: mock the layers that hit the network
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_network_layers():
    """Patch L2, L3, L4, L5 with mocks that populate the expected fields."""

    async def fake_l2(skill, should_trigger, should_not_trigger):
        return (0.9, 0.85)

    async def fake_l3(result, skill):
        result.skill_was_loaded = True
        result.instructions_followed = ["Read context", "Execute"]
        result.instructions_ignored = []
        result.behavioral_signature = ["Read", "Write"]
        return result

    async def fake_l4(results):
        # Populate pareto_objectives on every result with minimal non-zero values
        for r in results:
            r.pareto_objectives = {
                "correctness": 0.8,
                "token_efficiency": 0.7,
                "code_quality": 0.9,
                "trigger_accuracy": 0.85,
                "consistency": 0.0,
            }
            r.pairwise_wins = {"correctness": 1}
        # All results Pareto-optimal in this mock
        return {
            "pareto_optimal_ids": [r.skill_id for r in results],
            "per_result_objectives": {r.skill_id: dict(r.pareto_objectives) for r in results},
        }

    async def fake_l5(result, skill):
        result.trait_contribution = {t: 0.5 for t in (skill.traits or [])}
        result.trait_diagnostics = {t: f"contributed via {t}" for t in (skill.traits or [])}
        return result

    with (
        patch("skillforge.agents.judge.pipeline.run_l2", side_effect=fake_l2) as m_l2,
        patch("skillforge.agents.judge.pipeline.run_l3", side_effect=fake_l3) as m_l3,
        patch("skillforge.agents.judge.pipeline.run_l4", side_effect=fake_l4) as m_l4,
        patch("skillforge.agents.judge.pipeline.run_l5", side_effect=fake_l5) as m_l5,
    ):
        yield {"l2": m_l2, "l3": m_l3, "l4": m_l4, "l5": m_l5}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_pipeline_runs_all_layers_in_order(mock_network_layers):
    """Every layer is called at least once; L1 runs for real (subprocess)."""
    gen, challenges = _make_generation(n_skills=2, n_challenges=1)
    out = await run_judging_pipeline(gen, challenges)

    # L2 is called once per unique skill (not per result)
    assert mock_network_layers["l2"].call_count == 2
    # L3 is called once per result (2 skills × 1 challenge = 2 results)
    assert mock_network_layers["l3"].call_count == 2
    # L4 runs once on the full result set
    assert mock_network_layers["l4"].call_count == 1
    # L5 runs once per result
    assert mock_network_layers["l5"].call_count == 2

    # Mutates and returns the same Generation object
    assert out is gen


async def test_pipeline_populates_per_skill_fitness(mock_network_layers):
    gen, challenges = _make_generation(n_skills=2, n_challenges=1)
    await run_judging_pipeline(gen, challenges)

    for skill in gen.skills:
        assert skill.pareto_objectives, "pareto_objectives must be populated"
        assert skill.trigger_precision == 0.9
        assert skill.trigger_recall == 0.85
        assert skill.behavioral_signature == ["Read", "Write"]
        assert skill.is_pareto_optimal is True
        assert skill.trait_attribution, "trait_attribution must be populated"
        assert skill.deterministic_scores, "deterministic_scores must be populated"


async def test_pipeline_preserves_preexisting_pareto_objectives(mock_network_layers):
    """Atomic-mode regression: variant_evolution writes composite-scorer
    objectives onto skill.pareto_objectives BEFORE the judging pipeline
    runs. The pipeline's per-skill aggregation used to REPLACE those keys
    with comparative.py's legacy {correctness, code_quality, ...} set —
    silently clobbering the richer structural breakdown (l0/compile/ast/
    template/brevity). Now it MERGES: aggregated keys fill in only where
    the skill doesn't already carry a value.
    """
    gen, challenges = _make_generation(n_skills=2, n_challenges=1)
    # Simulate variant_evolution's composite scorer running first
    for skill in gen.skills:
        skill.pareto_objectives = {
            "composite": 0.72,
            "l0": 0.85,
            "compile": 1.0,
            "ast": 0.60,
            "template": 1.0,
            "brevity": 0.80,
        }

    await run_judging_pipeline(gen, challenges)

    for skill in gen.skills:
        # Composite-scorer keys survived
        assert skill.pareto_objectives["composite"] == 0.72
        assert skill.pareto_objectives["l0"] == 0.85
        assert skill.pareto_objectives["ast"] == 0.60
        # Aggregated keys from L4 are still there for molecular-mode parity
        assert "correctness" in skill.pareto_objectives
        assert "token_efficiency" in skill.pareto_objectives
        assert "trigger_accuracy" in skill.pareto_objectives


async def test_pipeline_computes_generation_fitness(mock_network_layers):
    gen, challenges = _make_generation(n_skills=3, n_challenges=1)
    await run_judging_pipeline(gen, challenges)

    assert gen.best_fitness > 0.0
    assert gen.avg_fitness > 0.0
    # With our mock (all skills get identical objectives) best == avg
    assert gen.best_fitness == gen.avg_fitness
    # Pareto front contains all 3 skills
    assert len(gen.pareto_front) == 3
    assert set(gen.pareto_front) == {s.id for s in gen.skills}


async def test_pipeline_handles_empty_generation(mock_network_layers):
    """Empty results/skills should not crash."""
    gen = Generation(number=0, skills=[], results=[])
    out = await run_judging_pipeline(gen, [])

    assert out.best_fitness == 0.0
    assert out.avg_fitness == 0.0
    assert out.pareto_front == []
    # No layers should have been called
    assert mock_network_layers["l2"].call_count == 0
    assert mock_network_layers["l3"].call_count == 0
    assert mock_network_layers["l4"].call_count == 1  # L4 is called even with empty — it handles that case
    assert mock_network_layers["l5"].call_count == 0


async def test_pipeline_skips_l2_call_for_empty_eval_queries(mock_network_layers, monkeypatch):
    """When eval queries are empty, L2 returns (0.0, 0.0) without being called."""
    import skillforge.agents.judge.pipeline as pipeline_mod

    # Force the cached default to be empty
    monkeypatch.setattr(pipeline_mod, "_DEFAULT_EVAL_QUERIES", {
        "should_trigger": [],
        "should_not_trigger": [],
    })

    gen, challenges = _make_generation(n_skills=2, n_challenges=1)
    await run_judging_pipeline(gen, challenges)

    # L2 should not have been called because queries are empty
    assert mock_network_layers["l2"].call_count == 0
    # But every skill still has zero-default trigger scores
    for skill in gen.skills:
        assert skill.trigger_precision == 0.0
        assert skill.trigger_recall == 0.0


async def test_pipeline_l2_scores_shared_across_skill_results(mock_network_layers):
    """A skill with 2 challenge results gets the SAME trigger scores on both."""
    gen, challenges = _make_generation(n_skills=1, n_challenges=2)
    await run_judging_pipeline(gen, challenges)

    assert len(gen.results) == 2
    # Both results for the single skill should have identical trigger scores
    assert gen.results[0].trigger_precision == gen.results[1].trigger_precision
    assert gen.results[0].trigger_recall == gen.results[1].trigger_recall

    # L2 was called exactly once (per unique skill)
    assert mock_network_layers["l2"].call_count == 1


async def test_pipeline_aggregates_deterministic_scores_per_challenge(mock_network_layers):
    """Per-challenge deterministic scores are keyed by challenge ID prefix."""
    gen, challenges = _make_generation(n_skills=1, n_challenges=2)
    await run_judging_pipeline(gen, challenges)

    skill = gen.skills[0]
    # Expect keys like "ch-0-abc:compiles", "ch-1-def:compiles", etc.
    det = skill.deterministic_scores
    assert any("compiles" in k for k in det)
    # One entry per challenge for at least the compiles check
    compiles_keys = [k for k in det if k.endswith(":compiles")]
    assert len(compiles_keys) >= 2


async def test_pipeline_averages_trait_contribution_across_results(mock_network_layers):
    """trait_attribution on the skill is the mean of per-result contributions."""
    gen, challenges = _make_generation(n_skills=1, n_challenges=2)
    await run_judging_pipeline(gen, challenges)

    skill = gen.skills[0]
    # Our fake L5 sets all traits to 0.5 → mean is 0.5
    assert skill.trait_attribution
    for value in skill.trait_attribution.values():
        assert value == 0.5


async def test_pipeline_handles_missing_skill_for_result(mock_network_layers):
    """If a result references a skill_id not in the generation, skip it gracefully."""
    gen, challenges = _make_generation(n_skills=1, n_challenges=1)
    # Add an orphan result pointing at a nonexistent skill
    orphan = _make_result("sk-orphan", challenges[0].id)
    gen.results.append(orphan)

    # Should not raise
    await run_judging_pipeline(gen, challenges)
