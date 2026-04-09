"""Tests for L1 deterministic judging layer."""

from __future__ import annotations

import pytest

from skillforge.agents.judge.deterministic import run_l1
from skillforge.models import Challenge, CompetitionResult  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_result(
    output_files: dict[str, str] | None = None,
    skill_id: str = "skill-test",
    challenge_id: str = "ch-test",
) -> CompetitionResult:
    """Construct a minimal CompetitionResult for testing."""
    return CompetitionResult(
        skill_id=skill_id,
        challenge_id=challenge_id,
        output_files=output_files or {},
    )


def make_challenge(
    verification_method: str = "run_tests",
    setup_files: dict[str, str] | None = None,
) -> Challenge:
    """Construct a minimal Challenge for testing."""
    return Challenge(
        id="ch-test",
        prompt="Write a function.",
        difficulty="easy",
        verification_method=verification_method,
        setup_files=setup_files or {},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_l1_dispatches_on_verification_method_judge_review() -> None:
    """With judge_review, only compiles is populated; tests_pass and lint_score stay None."""
    result = make_result(output_files={"solution.py": "def f(): return 1\n"})
    challenge = make_challenge(verification_method="judge_review")

    await run_l1(result, challenge)

    assert result.compiles is True
    assert result.tests_pass is None
    assert result.lint_score is None


@pytest.mark.asyncio
async def test_run_l1_compile_pass_for_valid_python() -> None:
    """Valid Python in output_files causes compiles=True."""
    result = make_result(output_files={"solution.py": "def f(): return 1\n"})
    challenge = make_challenge(verification_method="run_tests")

    await run_l1(result, challenge)

    assert result.compiles is True


@pytest.mark.asyncio
async def test_run_l1_compile_fail_for_invalid_python() -> None:
    """A syntax-broken Python file causes compiles=False."""
    result = make_result(output_files={"broken.py": "def broken(:\n    return\n"})
    challenge = make_challenge(verification_method="run_tests")

    await run_l1(result, challenge)

    assert result.compiles is False


@pytest.mark.asyncio
async def test_run_l1_compiles_true_when_no_python_files() -> None:
    """No .py files → vacuous compile success."""
    result = make_result(output_files={"README.md": "# Hello\n"})
    challenge = make_challenge(verification_method="run_tests")

    await run_l1(result, challenge)

    assert result.compiles is True


@pytest.mark.asyncio
async def test_run_l1_compiles_true_when_output_files_empty() -> None:
    """Empty output_files → vacuous compile success."""
    result = make_result(output_files={})
    challenge = make_challenge(verification_method="run_tests")

    await run_l1(result, challenge)

    assert result.compiles is True


@pytest.mark.asyncio
async def test_run_l1_runs_tests_when_test_file_present() -> None:
    """Passing test file in setup_files → tests_pass=True."""
    solution_code = "def add(a, b):\n    return a + b\n"
    test_code = (
        "from solution import add\n\n"
        "def test_add():\n"
        "    assert add(1, 2) == 3\n"
    )
    result = make_result(output_files={"solution.py": solution_code})
    challenge = make_challenge(
        verification_method="run_tests",
        setup_files={"test_solution.py": test_code},
    )

    await run_l1(result, challenge)

    assert result.tests_pass is True


@pytest.mark.asyncio
async def test_run_l1_tests_pass_false_on_failing_tests() -> None:
    """Failing test file in setup_files → tests_pass=False."""
    solution_code = "def add(a, b):\n    return a - b  # wrong\n"
    test_code = (
        "from solution import add\n\n"
        "def test_add():\n"
        "    assert add(1, 2) == 3\n"
    )
    result = make_result(output_files={"solution.py": solution_code})
    challenge = make_challenge(
        verification_method="run_tests",
        setup_files={"test_solution.py": test_code},
    )

    await run_l1(result, challenge)

    assert result.tests_pass is False


@pytest.mark.asyncio
async def test_run_l1_tests_pass_none_when_no_test_files() -> None:
    """No test files in setup_files → tests_pass=None."""
    result = make_result(output_files={"solution.py": "def f(): return 1\n"})
    challenge = make_challenge(
        verification_method="run_tests",
        setup_files={"helper.py": "# not a test\n"},
    )

    await run_l1(result, challenge)

    assert result.tests_pass is None


@pytest.mark.asyncio
async def test_run_l1_lint_score_perfect_for_clean_code() -> None:
    """Clean Python code → lint_score > 0.9."""
    clean_code = "def add(a: int, b: int) -> int:\n    return a + b\n"
    result = make_result(output_files={"solution.py": clean_code})
    challenge = make_challenge(verification_method="run_tests")

    await run_l1(result, challenge)

    assert result.lint_score is not None
    assert result.lint_score > 0.9


@pytest.mark.asyncio
async def test_run_l1_lint_score_none_for_no_python() -> None:
    """No .py files → lint_score=None."""
    result = make_result(output_files={"notes.txt": "hello\n"})
    challenge = make_challenge(verification_method="run_tests")

    await run_l1(result, challenge)

    assert result.lint_score is None


@pytest.mark.asyncio
async def test_run_l1_handles_unknown_verification_method() -> None:
    """Unknown verification_method does not crash; warns in judge_reasoning."""
    result = make_result(output_files={"solution.py": "x = 1\n"})
    challenge = make_challenge(verification_method="invalid")

    await run_l1(result, challenge)  # must not raise

    assert "unknown" in result.judge_reasoning.lower()
    assert "invalid" in result.judge_reasoning
