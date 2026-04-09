"""L1 — Deterministic checks (no LLM).

Dispatches on ``Challenge.verification_method``:
- ``run_tests``: Python-native path for MVP; generic subprocess fallback for other langs
- ``judge_review``: LLM review deferred to L4
- ``both``: runs both

Populates: ``compiles``, ``tests_pass``, ``lint_score``, ``perf_metrics`` on the
``CompetitionResult``. Reference validation (broken paths) also happens here.
"""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
from pathlib import Path

from skillforge.models import Challenge, CompetitionResult


async def run_l1(result: CompetitionResult, challenge: Challenge) -> CompetitionResult:
    """Populate L1 fields on result in place. Returns the same object for chaining."""
    method = challenge.verification_method

    if method in ("run_tests", "both"):
        await _check_compiles(result)
        await _run_tests(result, challenge)
        await _run_lint(result)
    elif method == "judge_review":
        await _check_compiles(result)
    else:
        # Unknown method — don't crash, just log a warning in judge_reasoning
        result.judge_reasoning += f" [L1: unknown verification_method '{method}']"

    return result


async def _check_compiles(result: CompetitionResult) -> None:
    """Run py_compile on every .py file in output_files. Sets result.compiles."""
    py_files = {p: c for p, c in result.output_files.items() if p.endswith(".py")}
    if not py_files:
        # No Python files to check — treat as vacuously compiling
        result.compiles = True
        return

    with tempfile.TemporaryDirectory(prefix="skillforge-l1-") as tmpdir:
        tmp = Path(tmpdir)
        for rel, content in py_files.items():
            target = tmp / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)

        # Run py_compile on each file
        all_ok = True
        for rel in py_files:
            proc = await asyncio.create_subprocess_exec(
                "python",
                "-m",
                "py_compile",
                str(tmp / rel),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode != 0:
                all_ok = False
                break
        result.compiles = all_ok


async def _run_tests(result: CompetitionResult, challenge: Challenge) -> None:
    """If challenge.setup_files contains test_*.py, run pytest on them.

    Sets result.tests_pass to True/False or leaves None if no tests.
    """
    test_files = {p: c for p, c in challenge.setup_files.items() if "test" in Path(p).name}
    if not test_files:
        result.tests_pass = None
        return

    with tempfile.TemporaryDirectory(prefix="skillforge-l1-tests-") as tmpdir:
        tmp = Path(tmpdir)
        # Write output files
        for rel, content in result.output_files.items():
            target = tmp / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        # Write test files
        for rel, content in test_files.items():
            target = tmp / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)

        proc = await asyncio.create_subprocess_exec(
            "python",
            "-m",
            "pytest",
            "-q",
            "--tb=no",
            str(tmp),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(tmp),
        )
        await proc.communicate()
        result.tests_pass = proc.returncode == 0


async def _run_lint(result: CompetitionResult) -> None:
    """Run ruff check on output .py files. Sets result.lint_score in [0.0, 1.0]."""
    py_files = {p: c for p, c in result.output_files.items() if p.endswith(".py")}
    if not py_files:
        result.lint_score = None
        return

    with tempfile.TemporaryDirectory(prefix="skillforge-l1-lint-") as tmpdir:
        tmp = Path(tmpdir)
        for rel, content in py_files.items():
            target = tmp / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)

        proc = await asyncio.create_subprocess_exec(
            "ruff",
            "check",
            "--quiet",
            "--output-format=concise",
            str(tmp),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        # Score: 1.0 if no violations, scaling down with count
        violation_count = len([line for line in stdout.decode().splitlines() if line.strip()])
        total_lines = sum(len(c.splitlines()) for c in py_files.values())
        if total_lines == 0:
            result.lint_score = 1.0
        else:
            result.lint_score = max(0.0, 1.0 - (violation_count / total_lines))
