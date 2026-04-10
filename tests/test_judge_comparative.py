"""Tests for L4 comparative judging layer."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from skillforge.agents.judge.comparative import (
    _compute_base_objectives,
    _compute_pareto_front,
    _dominates,
    run_l4,
)
from skillforge.models import CompetitionResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    skill_id: str = "skill-1",
    challenge_id: str = "ch-1",
    tests_pass: bool | None = True,
    lint_score: float | None = 0.8,
    trigger_precision: float = 0.7,
    trigger_recall: float = 0.7,
    trace: list[dict] | None = None,
    compiles: bool = True,
    output_files: dict[str, str] | None = None,
) -> CompetitionResult:
    """Build a minimal CompetitionResult for testing."""
    return CompetitionResult(
        skill_id=skill_id,
        challenge_id=challenge_id,
        tests_pass=tests_pass,
        lint_score=lint_score,
        trigger_precision=trigger_precision,
        trigger_recall=trigger_recall,
        trace=trace if trace is not None else [{}] * 3,
        compiles=compiles,
        output_files=output_files or {"solution.py": "def f(): pass"},
    )


# ---------------------------------------------------------------------------
# Test 1: empty results returns empty dict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_l4_empty_results_returns_empty() -> None:
    result = await run_l4([])
    assert result == {"pareto_optimal_ids": [], "per_result_objectives": {}}


# ---------------------------------------------------------------------------
# Test 2: single result is Pareto-optimal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_l4_single_result_is_pareto_optimal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("skillforge.agents.judge.comparative.L4_STRATEGY", "pairwise")
    r = _make_result(skill_id="only-skill")
    result = await run_l4([r])
    assert "only-skill" in result["pareto_optimal_ids"]


# ---------------------------------------------------------------------------
# Test 3: base objectives from passing tests
# ---------------------------------------------------------------------------


def test_compute_base_objectives_from_passing_tests() -> None:
    r = _make_result(
        tests_pass=True,
        lint_score=0.9,
        trigger_precision=0.8,
        trigger_recall=0.7,
        trace=[{}] * 5,
    )
    objs = _compute_base_objectives(r)

    assert set(objs.keys()) == {
        "correctness",
        "token_efficiency",
        "code_quality",
        "trigger_accuracy",
        "consistency",
    }
    for val in objs.values():
        assert 0.0 <= val <= 1.0, f"objective out of [0,1]: {val}"

    assert objs["correctness"] == 1.0
    assert objs["code_quality"] == 0.9


# ---------------------------------------------------------------------------
# Test 4: base objectives with tests_pass=None, compiles=True → correctness=0.5
# ---------------------------------------------------------------------------


def test_compute_base_objectives_handles_none_tests_pass() -> None:
    r = _make_result(tests_pass=None, compiles=True)
    objs = _compute_base_objectives(r)
    assert objs["correctness"] == 0.5


# ---------------------------------------------------------------------------
# Test 5: _dominates — strict better
# ---------------------------------------------------------------------------


def test_dominates_strict_better() -> None:
    a = {"correctness": 0.9, "token_efficiency": 0.9}
    b = {"correctness": 0.8, "token_efficiency": 0.8}
    assert _dominates(a, b) is True


# ---------------------------------------------------------------------------
# Test 6: _dominates — tie returns False
# ---------------------------------------------------------------------------


def test_dominates_tie_returns_false() -> None:
    a = {"correctness": 0.8, "token_efficiency": 0.8}
    b = {"correctness": 0.8, "token_efficiency": 0.8}
    assert _dominates(a, b) is False


# ---------------------------------------------------------------------------
# Test 7: _dominates — mixed (neither dominates the other)
# ---------------------------------------------------------------------------


def test_dominates_mixed_returns_false() -> None:
    a = {"correctness": 0.9, "token_efficiency": 0.5}
    b = {"correctness": 0.5, "token_efficiency": 0.9}
    assert _dominates(a, b) is False
    assert _dominates(b, a) is False


# ---------------------------------------------------------------------------
# Test 8: Pareto front identifies the 2 incomparable results
# ---------------------------------------------------------------------------


def test_compute_pareto_front_identifies_optimal() -> None:
    # r1: best on correctness, worst on efficiency → not dominated
    r1 = _make_result(skill_id="s1")
    r1.pareto_objectives = {"correctness": 1.0, "token_efficiency": 0.2}

    # r2: best on efficiency, worst on correctness → not dominated
    r2 = _make_result(skill_id="s2")
    r2.pareto_objectives = {"correctness": 0.2, "token_efficiency": 1.0}

    # r3: strictly dominated by r1 on correctness and tied/worse on efficiency
    r3 = _make_result(skill_id="s3")
    r3.pareto_objectives = {"correctness": 0.5, "token_efficiency": 0.1}

    front = _compute_pareto_front([r1, r2, r3])
    assert set(front) == {"s1", "s2"}
    assert "s3" not in front


# ---------------------------------------------------------------------------
# Test 9: pairwise strategy — mock always picks A
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_l4_pairwise_strategy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("skillforge.agents.judge.comparative.L4_STRATEGY", "pairwise")

    r1 = _make_result(skill_id="s1")
    r2 = _make_result(skill_id="s2")
    r3 = _make_result(skill_id="s3")
    results = [r1, r2, r3]

    with patch(
        "skillforge.agents.judge.comparative.stream_text",
        new_callable=AsyncMock,
        return_value="A",
    ):
        await run_l4(results)

    # With 3 results and always picking A: s1 beats s2, s1 beats s3 → 2 wins
    # s2 beats s3 → 1 win. s3 gets 0 wins.
    assert r1.pairwise_wins["correctness"] == 2
    assert r2.pairwise_wins["correctness"] == 1
    assert r3.pairwise_wins["correctness"] == 0


# ---------------------------------------------------------------------------
# Test 10: batched_rank strategy — mock returns [2, 1, 3]
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_l4_batched_rank_strategy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("skillforge.agents.judge.comparative.L4_STRATEGY", "batched_rank")

    r1 = _make_result(skill_id="s1")
    r2 = _make_result(skill_id="s2")
    r3 = _make_result(skill_id="s3")
    results = [r1, r2, r3]

    with patch(
        "skillforge.agents.judge.comparative.stream_text",
        new_callable=AsyncMock,
        return_value="[2, 1, 3]",
    ):
        await run_l4(results)

    # Ranking [2, 1, 3]: candidate 2 (r2) is best → wins=2
    # candidate 1 (r1) is second → wins=1
    # candidate 3 (r3) is worst → wins=0
    assert r2.pairwise_wins["correctness"] == 2
    assert r1.pairwise_wins["correctness"] == 1
    assert r3.pairwise_wins["correctness"] == 0


# ---------------------------------------------------------------------------
# Test 11: batched_rank handles malformed response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_l4_batched_rank_handles_malformed_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("skillforge.agents.judge.comparative.L4_STRATEGY", "batched_rank")

    r1 = _make_result(skill_id="s1")
    r2 = _make_result(skill_id="s2")
    results = [r1, r2]

    with patch(
        "skillforge.agents.judge.comparative.stream_text",
        new_callable=AsyncMock,
        return_value="garbage text without a valid array",
    ):
        output = await run_l4(results)  # must not crash

    assert r1.pairwise_wins["correctness"] == 0
    assert r2.pairwise_wins["correctness"] == 0
    assert isinstance(output, dict)


# ---------------------------------------------------------------------------
# Test 12: pairwise handles API error (ties assumed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_l4_pairwise_handles_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("skillforge.agents.judge.comparative.L4_STRATEGY", "pairwise")

    r1 = _make_result(skill_id="s1")
    r2 = _make_result(skill_id="s2")

    with patch(
        "skillforge.agents.judge.comparative.stream_text",
        new_callable=AsyncMock,
        side_effect=RuntimeError("API down"),
    ):
        output = await run_l4([r1, r2])  # must not crash

    # Both ties → 0 wins each
    assert r1.pairwise_wins["correctness"] == 0
    assert r2.pairwise_wins["correctness"] == 0
    assert isinstance(output, dict)


# ---------------------------------------------------------------------------
# Test 13: pareto_objectives populated on all results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_l4_populates_pareto_objectives_on_each_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("skillforge.agents.judge.comparative.L4_STRATEGY", "pairwise")

    r1 = _make_result(skill_id="s1")
    r2 = _make_result(skill_id="s2")

    with patch(
        "skillforge.agents.judge.comparative.stream_text",
        new_callable=AsyncMock,
        return_value="A",
    ):
        await run_l4([r1, r2])

    expected_keys = {
        "correctness",
        "token_efficiency",
        "code_quality",
        "trigger_accuracy",
        "consistency",
    }
    for r in [r1, r2]:
        assert set(r.pareto_objectives.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Test 14: uses configured model from model_for("judge_comparative")
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_l4_uses_configured_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("skillforge.agents.judge.comparative.L4_STRATEGY", "pairwise")

    sentinel_model = "claude-sentinel-model-test"
    monkeypatch.setenv("SKILLFORGE_MODEL_JUDGE_COMPARATIVE", sentinel_model)

    r1 = _make_result(skill_id="s1")
    r2 = _make_result(skill_id="s2")

    with patch(
        "skillforge.agents.judge.comparative.stream_text",
        new_callable=AsyncMock,
        return_value="A",
    ) as mock_stream:
        await run_l4([r1, r2])

    # Verify the model used in the stream_text call matches the sentinel
    mock_stream.assert_called()
    call_kwargs = mock_stream.call_args.kwargs
    assert call_kwargs.get("model") == sentinel_model
