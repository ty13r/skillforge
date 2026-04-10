"""Integration test: validates the full event sequence from run_evolution.

Mocks only the LLM-calling agents (challenge designer, spawner, competitor,
judging pipeline, breeder) but lets the real event queue, DB persistence,
and engine orchestration run end-to-end.
"""

from __future__ import annotations

import asyncio

import pytest
from unittest.mock import AsyncMock, patch

from skillforge.engine.events import get_queue, clear_all
from skillforge.engine.evolution import run_evolution
from skillforge.models import (
    Challenge,
    CompetitionResult,
    EvolutionRun,
    Generation,
    SkillGenome,
)


# ---------------------------------------------------------------------------
# Helpers
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


def _make_challenge(challenge_id: str = "ch-int-001") -> Challenge:
    return Challenge(
        id=challenge_id,
        prompt="Write a function.",
        difficulty="easy",
        evaluation_criteria={"correctness": 1.0},
        verification_method="judge_review",
        setup_files={},
    )


def _make_result(skill_id: str, challenge_id: str) -> CompetitionResult:
    return CompetitionResult(
        skill_id=skill_id,
        challenge_id=challenge_id,
        output_files={"solution.py": "def f(): return 1\n"},
        trace=[{"type": "AssistantMessage", "content": []}],
    )


async def drain_events(run_id: str, timeout: float = 30.0) -> list[dict]:
    """Collect all events from the queue until a terminal event or timeout."""
    queue = get_queue(run_id)
    events: list[dict] = []
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            break
        try:
            event = await asyncio.wait_for(queue.get(), timeout=min(remaining, 2.0))
            events.append(event)
            if event.get("event") in ("evolution_complete", "run_failed", "run_cancelled"):
                break
        except TimeoutError:
            continue
        except asyncio.TimeoutError:
            continue
    return events


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_queues():
    """Reset the event registry between tests."""
    clear_all()
    yield
    clear_all()


@pytest.fixture
def integration_run() -> EvolutionRun:
    return EvolutionRun(
        id="run-integration-001",
        mode="domain",
        specialization="Integration test specialization",
        population_size=2,
        num_generations=1,
        max_budget_usd=10.0,
    )


@pytest.fixture
def patch_all_agents(tmp_path, monkeypatch):
    """Mock all LLM-calling agents and DB/IO side-effects.

    Lets the real event queue and engine orchestration run untouched.
    """
    import skillforge.engine.sandbox as sandbox_mod

    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()
    monkeypatch.setattr(sandbox_mod, "SANDBOX_ROOT", sandbox_dir)

    async def fake_design_challenges(specialization, n=3):
        return [_make_challenge("ch-int-001"), _make_challenge("ch-int-002")]

    async def fake_spawn_gen0(specialization, pop_size):
        return [_make_skill(f"sk-int-{i:02d}") for i in range(pop_size)]

    async def fake_run_competitor(skill, challenge, sandbox_path):
        return _make_result(skill.id, challenge.id)

    async def fake_run_judging_pipeline(generation, challenges, run_id=None):
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

    async def fake_save_run(run, db_path=None):
        return None

    with (
        patch("skillforge.engine.evolution.design_challenges", side_effect=fake_design_challenges),
        patch("skillforge.engine.evolution.spawn_gen0", side_effect=fake_spawn_gen0),
        patch("skillforge.engine.evolution.run_competitor", side_effect=fake_run_competitor),
        patch("skillforge.engine.evolution.run_judging_pipeline", side_effect=fake_run_judging_pipeline),
        patch("skillforge.engine.evolution.breed", new_callable=AsyncMock),
        patch("skillforge.engine.evolution.save_run", side_effect=fake_save_run),
        patch("skillforge.engine.evolution.publish_findings_to_bible"),
        patch("skillforge.engine.evolution.init_db", new_callable=AsyncMock),
        patch("skillforge.engine.evolution.dump_run_json", return_value=None),
    ):
        yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_full_event_sequence_completes(integration_run, patch_all_agents):
    """Run the full evolution with concurrent event draining and verify
    that all expected events fire in order and the run completes."""

    async def run_and_return():
        return await run_evolution(integration_run)

    # Run evolution and drain events concurrently
    run_result, events = await asyncio.wait_for(
        asyncio.gather(
            run_and_return(),
            drain_events(integration_run.id, timeout=30.0),
        ),
        timeout=30.0,
    )

    # --- Verify run completed successfully ---
    assert run_result.status == "complete"
    assert run_result.completed_at is not None
    assert len(run_result.generations) == 1
    assert run_result.best_skill is not None

    # --- Verify event sequence ---
    event_names = [e["event"] for e in events]

    # All required events must be present
    required_events = [
        "run_started",
        "challenge_designed",
        "generation_started",
        "competitor_started",
        "competitor_finished",
        "judging_started",
        "scores_published",
        "evolution_complete",
    ]
    for required in required_events:
        assert required in event_names, f"Missing required event: {required}"

    # First event must be run_started
    assert event_names[0] == "run_started"

    # Last event must be evolution_complete
    assert event_names[-1] == "evolution_complete"

    # challenge_designed must come before generation_started
    first_challenge = event_names.index("challenge_designed")
    first_gen = event_names.index("generation_started")
    assert first_challenge < first_gen, "challenge_designed must precede generation_started"

    # generation_started must come before competitor_started
    first_competitor = event_names.index("competitor_started")
    assert first_gen < first_competitor, "generation_started must precede competitor_started"

    # competitor_finished must come before judging_started
    # (all competitors finish before judging begins)
    last_competitor_finished = len(event_names) - 1 - event_names[::-1].index("competitor_finished")
    first_judging = event_names.index("judging_started")
    assert last_competitor_finished < first_judging, "all competitor_finished must precede judging_started"

    # judging_started must come before scores_published
    first_scores = event_names.index("scores_published")
    assert first_judging < first_scores, "judging_started must precede scores_published"

    # With pop_size=2 and 2 challenges, expect at least 4 competitor_started events
    assert event_names.count("competitor_started") >= 4
    assert event_names.count("competitor_finished") >= 4

    # At least 2 challenge_designed events (we return 2 challenges)
    assert event_names.count("challenge_designed") >= 2


async def test_event_timestamps_present(integration_run, patch_all_agents):
    """Every event emitted by the engine must carry a `timestamp` field."""

    _, events = await asyncio.wait_for(
        asyncio.gather(
            run_evolution(integration_run),
            drain_events(integration_run.id, timeout=30.0),
        ),
        timeout=30.0,
    )

    assert len(events) > 0, "Expected at least one event"

    for event in events:
        assert "timestamp" in event, (
            f"Event {event.get('event', '<unknown>')} missing 'timestamp' field"
        )
        # Timestamp should be a non-empty ISO string
        assert isinstance(event["timestamp"], str)
        assert len(event["timestamp"]) > 0
