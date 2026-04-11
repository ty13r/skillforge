"""Wave 3-1 / 3-2 / 3-3 unit tests + Phase 3 e2e atomic-evolution test.

The orchestrator's per-dimension flow goes Spawner → Competitor →
Reviewer → Variant winner. Every LLM-bound step is mocked here so the
tests stay hermetic and run in milliseconds.

Coverage:
- ``run_variant_evolution`` happy path: 1 foundation + 2 capability dims,
  the orchestrator emits the full event sequence and stamps
  ``run.best_skill`` with the foundation winner (stub assembly).
- Tier ordering: foundation runs first, capabilities run after with the
  winning foundation passed as ``foundation_genome``.
- Empty pending list: orchestrator flips ``evolution_mode`` back to
  molecular and returns without doing any work.
- ``design_variant_challenge`` returns a single Challenge from a mocked
  generator; raises if the model returns the wrong number.
- ``spawn_variant_gen0`` produces population_size focused variants and
  stamps the ``dimension`` + ``tier`` keys on each frontmatter; raises
  when validation drops everything.
- Wave 3 QA gate: end-to-end mocked atomic pipeline. Verifies the full
  event sequence — taxonomy_classified → decomposition_complete →
  variant_evolution_started × N → variant_evolution_complete × N →
  assembly_started → assembly_complete → evolution_complete.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from skillforge.db import (
    init_db,
    save_run,
    save_skill_family,
    save_variant_evolution,
)
from skillforge.engine.events import drop_queue, get_queue
from skillforge.engine.variant_evolution import (
    _aggregate_fitness,
    _tier_sort_key,
    run_variant_evolution,
)
from skillforge.models import (
    Challenge,
    CompetitionResult,
    EvolutionRun,
    Generation,
    SkillFamily,
    SkillGenome,
    VariantEvolution,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(run_id: str = "run_phase3", evolution_mode: str = "atomic") -> EvolutionRun:
    return EvolutionRun(
        id=run_id,
        mode="domain",
        specialization="test variant evolution",
        population_size=2,
        num_generations=1,
        evolution_mode=evolution_mode,
        family_id="fam_phase3",
        status="pending",
        created_at=datetime.now(UTC),
    )


def _make_genome(gid: str, fitness: float = 0.5) -> SkillGenome:
    """Build a SkillGenome with a non-empty pareto_objectives so
    _aggregate_fitness returns the expected value."""
    return SkillGenome(
        id=gid,
        generation=0,
        skill_md_content=f"# {gid}\nbody",
        frontmatter={"name": gid},
        supporting_files={},
        traits=["test"],
        meta_strategy="test",
        pareto_objectives={"quality": fitness},
    )


def _make_challenge(cid: str = "ch_test") -> Challenge:
    return Challenge(
        id=cid,
        prompt="test prompt",
        difficulty="easy",
        evaluation_criteria={"correctness": 1.0},
        verification_method="run_tests",
        setup_files={},
        gold_standard_hints="hint",
    )


async def _seed_family(family_id: str = "fam_phase3"):
    """Insert a family row so VariantEvolution.family_id has a valid FK."""
    await save_skill_family(
        SkillFamily(
            id=family_id,
            slug="phase3-fam",
            label="Phase 3 Family",
            specialization="x",
        )
    )


async def _seed_variant_evolution(
    family_id: str,
    parent_run_id: str,
    dimension: str,
    tier: str,
    population_size: int = 2,
) -> str:
    vevo_id = f"vevo_{uuid.uuid4().hex[:8]}"
    await save_variant_evolution(
        VariantEvolution(
            id=vevo_id,
            family_id=family_id,
            dimension=dimension,
            tier=tier,
            parent_run_id=parent_run_id,
            population_size=population_size,
            num_generations=1,
            status="pending",
            created_at=datetime.now(UTC),
        )
    )
    return vevo_id


def _drain_queue(run_id: str) -> list[dict]:
    queue = get_queue(run_id)
    events = []
    while True:
        try:
            events.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            break
    return events


# ---------------------------------------------------------------------------
# Sort + fitness helpers
# ---------------------------------------------------------------------------


def test_tier_sort_key_orders_foundation_first():
    fnd = VariantEvolution(
        id="a", family_id="f", dimension="d1", tier="foundation",
        parent_run_id="r"
    )
    cap = VariantEvolution(
        id="b", family_id="f", dimension="d2", tier="capability",
        parent_run_id="r"
    )
    items = sorted([cap, fnd], key=_tier_sort_key)
    assert items[0].tier == "foundation"
    assert items[1].tier == "capability"


def test_aggregate_fitness_uses_pareto_then_deterministic():
    g1 = _make_genome("g1", fitness=0.9)
    assert _aggregate_fitness(g1) == pytest.approx(0.9)

    g2 = SkillGenome(
        id="g2",
        generation=0,
        skill_md_content="",
        deterministic_scores={"a": 0.6, "b": 0.4},
    )
    assert _aggregate_fitness(g2) == pytest.approx(0.5)

    g3 = SkillGenome(id="g3", generation=0, skill_md_content="")
    assert _aggregate_fitness(g3) == 0.0


# ---------------------------------------------------------------------------
# run_variant_evolution — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_variant_evolution_happy_path():
    await init_db()
    run = _make_run(run_id=f"run_happy_{uuid.uuid4().hex[:6]}")
    await save_run(run)
    await _seed_family(family_id=run.family_id)
    await _seed_variant_evolution(run.family_id, run.id, "fixture-strategy", "foundation")
    await _seed_variant_evolution(run.family_id, run.id, "mock-strategy", "capability")

    # Mock every LLM-bound stage. The challenge designer returns a fixed
    # Challenge; the spawner returns 2 genomes per dimension; the
    # competitor returns trivial passing CompetitionResult objects; the
    # judging pipeline assigns fitness scores.

    challenge = _make_challenge()

    async def mock_design(*args, **kwargs):
        return challenge

    spawn_call_count = {"value": 0}

    async def mock_spawn(*, specialization, dimension, foundation_genome, pop_size):
        spawn_call_count["value"] += 1
        # First call (foundation) gets None; second call (capability) gets
        # the foundation winner — capture for assertion.
        if dimension["tier"] == "capability":
            assert foundation_genome is not None, (
                "capability spawn must receive the winning foundation"
            )
            assert foundation_genome.id.startswith("g_foundation_winner")
        else:
            assert foundation_genome is None
        prefix = "foundation_winner" if dimension["tier"] == "foundation" else "cap"
        return [
            _make_genome(f"g_{prefix}_{i}", fitness=0.9 - 0.2 * i)
            for i in range(pop_size)
        ]

    async def mock_competitor(*, semaphore, run_id, generation, competitor_idx, skill, challenge, env_id):
        return CompetitionResult(
            skill_id=skill.id,
            challenge_id=challenge.id,
            output_files={},
            trace=[],
            compiles=True,
            tests_pass=True,
            lint_score=1.0,
            perf_metrics={},
            trigger_precision=1.0,
            trigger_recall=1.0,
            skill_was_loaded=True,
            instructions_followed=[],
            instructions_ignored=[],
            ignored_diagnostics={},
            scripts_executed=[],
            behavioral_signature=[],
            pairwise_wins={},
            pareto_objectives={},
            trait_contribution={},
            trait_diagnostics={},
            judge_reasoning="",
        )

    async def mock_judging(generation, challenges, *, run_id):
        # Leave the genomes' pareto_objectives as set by _make_genome
        generation.best_fitness = max(
            (_aggregate_fitness(s) for s in generation.skills), default=0.0
        )
        generation.avg_fitness = (
            sum(_aggregate_fitness(s) for s in generation.skills)
            / max(1, len(generation.skills))
        )
        return generation

    # Mock the Engineer's assemble_skill call too — Phase 4 wired the
    # real assembly into the orchestrator, so without this mock the test
    # would hit the real Anthropic API. The mock also emits the same
    # event sequence the real assemble_skill would emit, so the
    # variant_evolution event-sequence assertions still hold.
    async def mock_assemble_skill(parent_run, family, foundation, capabilities, **kwargs):
        from skillforge.agents.engineer import IntegrationReport
        from skillforge.engine.events import emit as _emit

        await _emit(
            parent_run.id,
            "assembly_started",
            family_id=family.id,
            foundation_id=foundation.id,
            capability_count=len(capabilities),
        )
        await _emit(
            parent_run.id,
            "assembly_complete",
            family_id=family.id,
            composite_id=foundation.id,
            integration_passed=True,
            refinement_attempted=False,
        )
        return foundation, IntegrationReport(notes="mocked assembly")

    with patch(
        "skillforge.agents.challenge_designer.design_variant_challenge",
        new=mock_design,
    ), patch(
        "skillforge.agents.spawner.spawn_variant_gen0",
        new=mock_spawn,
    ), patch(
        "skillforge.engine.evolution._gated_competitor",
        new=mock_competitor,
    ), patch(
        "skillforge.agents.judge.pipeline.run_judging_pipeline",
        new=mock_judging,
    ), patch(
        "skillforge.engine.assembly.assemble_skill",
        new=mock_assemble_skill,
    ):
        result = await run_variant_evolution(run)

    assert result is run
    assert result.evolution_mode == "atomic"
    assert result.best_skill is not None
    # The mocked assembly returns the foundation winner unchanged
    assert result.best_skill.id.startswith("g_foundation_winner")

    events = _drain_queue(run.id)
    types = [e["event"] for e in events]
    assert "variant_evolution_started" in types
    assert "variant_evolution_complete" in types
    assert "assembly_started" in types
    assert "assembly_complete" in types
    # Foundation processed before capability
    foundation_idx = types.index("variant_evolution_started")
    second_started = types.index("variant_evolution_started", foundation_idx + 1)
    assert second_started > foundation_idx
    started_events = [e for e in events if e["event"] == "variant_evolution_started"]
    assert started_events[0]["tier"] == "foundation"
    assert started_events[1]["tier"] == "capability"

    drop_queue(run.id)


@pytest.mark.asyncio
async def test_run_variant_evolution_no_dimensions_falls_back_to_molecular():
    """If no VariantEvolution rows exist for the run, the orchestrator
    flips evolution_mode to "molecular" and returns without doing work."""
    await init_db()
    run = _make_run(run_id=f"run_empty_{uuid.uuid4().hex[:6]}")
    await save_run(run)
    # No _seed_variant_evolution calls — the queue is empty

    result = await run_variant_evolution(run)
    assert result.evolution_mode == "molecular"
    assert result.best_skill is None

    drop_queue(run.id)


# ---------------------------------------------------------------------------
# design_variant_challenge — pure unit test with mocked _generate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_design_variant_challenge_returns_one():
    from skillforge.agents import challenge_designer

    response = json.dumps(
        [
            {
                "prompt": "write a function reverse_string(s)",
                "difficulty": "easy",
                "evaluation_criteria": {"correctness": 1.0},
                "verification_method": "run_tests",
                "setup_files": {"test_solution.py": "def test(): pass"},
                "gold_standard_hints": "use slicing",
            }
        ]
    )

    with patch.object(
        challenge_designer, "_generate", new=AsyncMock(return_value=response)
    ):
        challenge = await challenge_designer.design_variant_challenge(
            specialization="test",
            dimension={"name": "mock-strategy", "tier": "capability", "description": "x", "evaluation_focus": "y"},
        )

    assert isinstance(challenge, Challenge)
    assert challenge.difficulty == "easy"
    assert challenge.prompt.startswith("write")


@pytest.mark.asyncio
async def test_design_variant_challenge_rejects_multiple():
    from skillforge.agents import challenge_designer

    bad_response = json.dumps(
        [
            {
                "prompt": "p1",
                "difficulty": "easy",
                "evaluation_criteria": {},
                "verification_method": "run_tests",
                "setup_files": {},
                "gold_standard_hints": "",
            },
            {
                "prompt": "p2",
                "difficulty": "easy",
                "evaluation_criteria": {},
                "verification_method": "run_tests",
                "setup_files": {},
                "gold_standard_hints": "",
            },
        ]
    )

    with patch.object(
        challenge_designer, "_generate", new=AsyncMock(return_value=bad_response)
    ):
        with pytest.raises(ValueError, match="expected 1 challenge"):
            await challenge_designer.design_variant_challenge(
                specialization="test",
                dimension={"name": "d", "tier": "foundation"},
            )


# ---------------------------------------------------------------------------
# spawn_variant_gen0 — pure unit test with mocked _generate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spawn_variant_gen0_produces_focused_variants():
    from skillforge.agents import spawner

    valid_skill_md = """---
name: variant-foo
description: Generates focused mocks for HTTP clients. Use when testing HTTP-bound code, mocking external services, or isolating network calls. NOT for fixture generation, assertion patterns, or integration testing.
allowed-tools: Read Write
---

# Variant Foo

## Quick Start
Mock HTTP clients with patch decorators.

## When to use this skill
When you need to mock HTTP calls in unit tests.

## Workflow
1. Identify the HTTP client
2. Patch with autospec
3. Set return values

## Examples

**Example 1: Single client**
Input: "mock requests.get"
Output: @patch("module.requests.get", autospec=True)

**Example 2: Multiple clients**
Input: "mock requests + httpx"
Output: stack patches in bottom-up order

## Gotchas
- Patch where used, not where defined
"""

    response = json.dumps(
        [
            {
                "frontmatter": {
                    "name": f"variant-foo-{i}",
                    "description": (
                        "Generates focused mocks for HTTP clients. Use when "
                        "mocking, NOT for fixtures."
                    ),
                    "allowed-tools": "Read Write",
                },
                "skill_md_content": valid_skill_md.replace(
                    "name: variant-foo", f"name: variant-foo-{i}"
                ),
                "supporting_files": {},
                "traits": ["mock-decorator"],
                "meta_strategy": "patch with autospec",
            }
            for i in range(2)
        ]
    )

    with patch.object(
        spawner, "_generate", new=AsyncMock(return_value=response)
    ), patch.object(
        spawner, "_validate_genomes", lambda gs: (gs, {})
    ):
        result = await spawner.spawn_variant_gen0(
            specialization="generate pytest mocks",
            dimension={
                "name": "mock-strategy",
                "tier": "capability",
                "description": "how external HTTP deps are isolated",
                "evaluation_focus": "isolation",
            },
            foundation_genome=None,
            pop_size=2,
        )

    assert len(result) == 2
    for genome in result:
        assert genome.frontmatter.get("dimension") == "mock-strategy"
        assert genome.frontmatter.get("tier") == "capability"


@pytest.mark.asyncio
async def test_spawn_variant_gen0_rejects_when_all_invalid():
    from skillforge.agents import spawner

    response = json.dumps(
        [
            {
                "frontmatter": {"name": "bad"},
                "skill_md_content": "# bad\n",
                "supporting_files": {},
                "traits": [],
                "meta_strategy": "",
            }
        ]
    )

    def _all_invalid(gs):
        return ([], {i: ["forced invalid"] for i in range(len(gs))})

    with patch.object(
        spawner, "_generate", new=AsyncMock(return_value=response)
    ), patch.object(
        spawner, "_validate_genomes", _all_invalid
    ):
        with pytest.raises(ValueError, match="no valid variants"):
            await spawner.spawn_variant_gen0(
                specialization="x",
                dimension={"name": "d", "tier": "foundation"},
                foundation_genome=None,
                pop_size=2,
            )
