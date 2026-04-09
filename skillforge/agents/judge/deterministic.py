"""L1 — Deterministic checks (no LLM).

Dispatches on ``Challenge.verification_method``:
- ``run_tests``: Python-native path for MVP; generic subprocess fallback for other langs
- ``judge_review``: LLM review deferred to L4
- ``both``: runs both

Populates: ``compiles``, ``tests_pass``, ``lint_score``, ``perf_metrics`` on the
``CompetitionResult``. Reference validation (broken paths) also happens here.
"""

from __future__ import annotations

from skillforge.models import Challenge, CompetitionResult


async def run_l1(result: CompetitionResult, challenge: Challenge) -> CompetitionResult:
    """Run deterministic checks and populate L1 fields in place."""
    raise NotImplementedError
