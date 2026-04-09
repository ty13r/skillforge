"""Evolution engine integration tests (Step 7).

Mocked end-to-end test runs a small evolution (2 pop x 1 gen x 1 challenge)
through the full pipeline with all SDK calls stubbed. Asserts:
    - Run completes with status='complete'
    - All event types fire in the documented order
    - Budget tracking accumulates correctly
    - DB persistence happens after each generation
    - Skills are mutated by the judging pipeline (fitness fields populated)
    - The Breeder produces children for gen 1+

A separate live-SDK end-to-end test is gated behind SKILLFORGE_LIVE_TESTS=1
and only runs when the user explicitly opts into real API spend.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from skillforge.config import LIVE_TESTS
from skillforge.engine.events import clear_all, get_queue
from skillforge.engine.evolution import run_evolution
from skillforge.models import (
    Challenge,
    CompetitionResult,
    EvolutionRun,
    SkillGenome,
)

# ---------------------------------------------------------------------------
# Helpers & fixtures
# ---------------------------------------------------------------------------


def _valid_skill_md(name: str = "test-skill") -> str:
    return f"""---
name: {name}
description: >-
  Does things. Use when testing things, even if not asked. NOT for prod.
---

# Skill

## Quick start
Do the thing.

## Workflow

### Step 1: Read context
Do this.

### Step 2: Execute
Run the script.

## Examples

**Example 1:** in:x / out:y
**Example 2:** in:a / out:b
"""


def _make_skill(skill_id: str, generation: int = 0) -> SkillGenome:
    return SkillGenome(
        id=skill_id,
        generation=generation,
        skill_md_content=_valid_skill_md(name=f"sk-{skill_id[:6]}"),
        traits=["concise", "structured"],
        pareto_objectives={"correctness": 0.8, "quality": 0.7},
        is_pareto_optimal=True,
        trait_attribution={"concise": 0.4, "structured": 0.3},
        trait_diagnostics={"concise": "good", "structured": "good"},
    )


def _make_challenge() -> Challenge:
    return Challenge(
        id="ch-test-001",
        prompt="Write a function.",
        difficulty="easy",
        evaluation_criteria={"correctness": 1.0},
        verification_method="judge_review",  # avoid running real subprocesses
        setup_files={},
    )


def _make_result(skill_id: str, challenge_id: str) -> CompetitionResult:
    return CompetitionResult(
        skill_id=skill_id,
        challenge_id=challenge_id,
        output_files={"solution.py": "def f(): return 1\n"},
        trace=[{"type": "AssistantMessage", "content": []}],
    )


@pytest.fixture(autouse=True)
def _clear_event_queues():
    """Reset the event registry between tests."""
    clear_all()
    yield
    clear_all()


@pytest.fixture
def fake_run():
    return EvolutionRun(
        id="run-test-001",
        mode="domain",
        specialization="Test specialization",
        population_size=2,
        num_generations=1,
        max_budget_usd=100.0,
    )


@pytest.fixture
def patch_engine_dependencies(tmp_path, monkeypatch):
    """Mock all the network/SDK-touching dependencies of the evolution engine."""
    import skillforge.engine.sandbox as sandbox_mod

    # Use a temp sandbox dir
    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()
    monkeypatch.setattr(sandbox_mod, "SANDBOX_ROOT", sandbox_dir)

    async def fake_design_challenges(specialization, n=3):
        return [_make_challenge()]  # always 1 challenge for the small test

    async def fake_spawn_gen0(specialization, pop_size):
        return [_make_skill(f"sk-{i:02d}") for i in range(pop_size)]

    async def fake_run_competitor(skill, challenge, sandbox_path):
        return _make_result(skill.id, challenge.id)

    async def fake_run_judging_pipeline(generation, challenges):
        # Populate fitness fields the engine reads after the pipeline returns
        for skill in generation.skills:
            skill.pareto_objectives = {"correctness": 0.85, "quality": 0.75}
            skill.is_pareto_optimal = True
            skill.trigger_precision = 0.9
            skill.trigger_recall = 0.85
        for result in generation.results:
            result.pareto_objectives = {"correctness": 0.85, "quality": 0.75}
        generation.best_fitness = 0.85
        generation.avg_fitness = 0.80
        generation.pareto_front = [s.id for s in generation.skills]
        return generation

    async def fake_breed(generation, learning_log, specialization, target_pop_size):
        children = [_make_skill(f"sk-bred-{i:02d}", generation=generation.number + 1) for i in range(target_pop_size)]
        return (children, ["new lesson"], "breeding report text")

    async def fake_save_run(run, db_path=None):
        return None

    with (
        patch("skillforge.engine.evolution.design_challenges", side_effect=fake_design_challenges),
        patch("skillforge.engine.evolution.spawn_gen0", side_effect=fake_spawn_gen0),
        patch("skillforge.engine.evolution.run_competitor", side_effect=fake_run_competitor),
        patch("skillforge.engine.evolution.run_judging_pipeline", side_effect=fake_run_judging_pipeline),
        patch("skillforge.engine.evolution.breed", side_effect=fake_breed),
        patch("skillforge.engine.evolution.save_run", side_effect=fake_save_run),
        patch("skillforge.engine.evolution.publish_findings_to_bible") as mock_publish,
    ):
        yield {"publish": mock_publish}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_minimal_evolution_completes(fake_run, patch_engine_dependencies):
    """2 pop x 1 gen x 1 challenge end-to-end with all SDK calls mocked."""
    out = await run_evolution(fake_run)

    assert out.status == "complete"
    assert out.completed_at is not None
    assert len(out.generations) == 1
    assert out.best_skill is not None
    assert out.best_skill.id in [s.id for s in out.pareto_front]


async def test_evolution_emits_events_in_order(fake_run, patch_engine_dependencies):
    """The event queue must contain events in the documented order."""
    await run_evolution(fake_run)

    queue = get_queue(fake_run.id)
    events: list[dict] = []
    while not queue.empty():
        events.append(queue.get_nowait())

    event_names = [e["event"] for e in events]
    # The order is: run_started, challenge_design_started, challenge_designed,
    # generation_started, competitor_started/finished, judging_started,
    # scores_published, cost_update, generation_complete, evolution_complete
    assert event_names[0] == "run_started"
    assert "challenge_designed" in event_names
    assert "generation_started" in event_names
    assert "competitor_started" in event_names
    assert "competitor_finished" in event_names
    assert "judging_started" in event_names
    assert "scores_published" in event_names
    assert "cost_update" in event_names
    assert "generation_complete" in event_names
    assert event_names[-1] == "evolution_complete"

    # generation_started before any competitor_started
    gen_started_idx = event_names.index("generation_started")
    competitor_started_idx = event_names.index("competitor_started")
    assert gen_started_idx < competitor_started_idx


async def test_evolution_persists_after_each_generation(fake_run, patch_engine_dependencies):
    """save_run should be called multiple times across the run."""
    with patch("skillforge.engine.evolution.save_run") as mock_save:

        async def _ok(run, db_path=None):
            return None

        mock_save.side_effect = _ok
        await run_evolution(fake_run)

    # save_run is called: after challenges designed, after gen 0 complete, after final
    assert mock_save.call_count >= 3


async def test_evolution_budget_abort(patch_engine_dependencies):
    """If estimated cost exceeds max_budget_usd, run aborts with status=failed."""
    cheap_run = EvolutionRun(
        id="run-budget",
        mode="domain",
        specialization="test",
        population_size=2,
        num_generations=3,
        max_budget_usd=0.0001,  # impossibly tiny
    )

    out = await run_evolution(cheap_run)

    assert out.status == "failed"
    assert "budget" in (getattr(out, "failure_reason", "") or "").lower()
    # Should have aborted before completing all 3 generations
    assert len(out.generations) < 3


async def test_evolution_multi_generation_runs_breeder(patch_engine_dependencies):
    """When num_generations > 1, the Breeder should be called for gen 1+."""
    multi_run = EvolutionRun(
        id="run-multi",
        mode="domain",
        specialization="test",
        population_size=2,
        num_generations=3,
        max_budget_usd=100.0,
    )

    with patch("skillforge.engine.evolution.breed") as mock_breed:
        async def _fake_breed(generation, learning_log, specialization, target_pop_size):
            children = [_make_skill(f"bred-{generation.number}-{i}", generation=generation.number + 1) for i in range(target_pop_size)]
            return (children, [f"lesson gen{generation.number}"], f"report gen{generation.number}")

        mock_breed.side_effect = _fake_breed
        out = await run_evolution(multi_run)

    assert out.status == "complete"
    # Breeder is called for gen 1 and gen 2 (NOT gen 0, which uses spawn_gen0)
    assert mock_breed.call_count == 2
    # Learning log should have grown
    assert len(out.learning_log) >= 2


async def test_evolution_publishes_findings_to_bible(patch_engine_dependencies):
    """After each non-zero generation, findings should be published."""
    multi_run = EvolutionRun(
        id="run-bible",
        mode="domain",
        specialization="test",
        population_size=2,
        num_generations=2,
        max_budget_usd=100.0,
    )

    out = await run_evolution(multi_run)

    publish_mock = patch_engine_dependencies["publish"]
    # Called for gen 1 (and would be called for gen 2+ if we had more)
    assert publish_mock.call_count >= 1
    assert out.status == "complete"


async def test_evolution_failure_emits_run_failed_event(fake_run):
    """If a sub-call raises, the engine emits run_failed and re-raises."""
    async def boom_designer(*a, **kw):
        raise RuntimeError("designer crashed")

    with (
        patch("skillforge.engine.evolution.design_challenges", side_effect=boom_designer),
        patch("skillforge.engine.evolution.save_run") as mock_save,
    ):
        async def _ok(run, db_path=None):
            return None

        mock_save.side_effect = _ok

        with pytest.raises(RuntimeError, match="designer crashed"):
            await run_evolution(fake_run)

    queue = get_queue(fake_run.id)
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())

    assert any(e["event"] == "run_failed" for e in events)
    assert fake_run.status == "failed"


async def test_evolution_db_persistence_failure_does_not_abort(fake_run, patch_engine_dependencies):
    """A DB save failure must not abort the evolution — it's logged and skipped."""
    with patch("skillforge.engine.evolution.save_run", side_effect=RuntimeError("db down")):
        # Should not raise — DB failures are non-fatal
        out = await run_evolution(fake_run)

    assert out.status == "complete"


# ---------------------------------------------------------------------------
# Live SDK test (gated)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not LIVE_TESTS, reason="Live SDK test — set SKILLFORGE_LIVE_TESTS=1")
async def test_minimal_evolution_live():
    """Run a real 2 pop x 1 gen x 1 challenge against the actual SDK.

    Spends real money (~$1-3). Only runs when SKILLFORGE_LIVE_TESTS=1.
    """
    run = EvolutionRun(
        id="run-live-test",
        mode="domain",
        specialization=(
            "A skill that writes idiomatic Python list comprehensions for data transformation."
        ),
        population_size=2,
        num_generations=1,
        max_budget_usd=5.0,
    )

    out = await run_evolution(run)

    assert out.status == "complete"
    assert out.best_skill is not None
    assert out.total_cost_usd > 0.0
    assert out.total_cost_usd < 5.0  # under budget
    assert len(out.generations) == 1
