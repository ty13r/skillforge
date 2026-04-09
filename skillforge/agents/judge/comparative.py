"""L4 — Pairwise comparative ranking and Pareto front selection.

Runs pairwise comparisons across all competitors on each evaluation criterion,
derives per-criterion win rates, and computes the Pareto front across all
objectives (correctness, token efficiency, code quality, trigger accuracy,
consistency). Skills on the Pareto front survive regardless of aggregate score.
"""

from __future__ import annotations

import itertools
import json
import re

from anthropic import AsyncAnthropic

from skillforge.config import ANTHROPIC_API_KEY, L4_STRATEGY, model_for
from skillforge.models import CompetitionResult

# Pareto objectives used in MVP. L6 consistency is 0.0 for MVP since L6
# is deferred to v1.1.
_OBJECTIVES = [
    "correctness",
    "token_efficiency",
    "code_quality",
    "trigger_accuracy",
    "consistency",
]


async def run_l4(results: list[CompetitionResult]) -> dict:
    """Run pairwise or batched comparative ranking + compute Pareto front.

    Returns a dict: {
        "pareto_optimal_ids": [skill_ids...],
        "per_result_objectives": {skill_id: {objective: score}},
    }

    Also mutates each result in place: sets result.pairwise_wins and
    result.pareto_objectives.
    """
    if not results:
        return {"pareto_optimal_ids": [], "per_result_objectives": {}}

    # Step 1: Compute baseline per-objective scores from existing fields
    # (correctness, code_quality, trigger_accuracy, consistency can be
    # derived from L1-L3 fields; token_efficiency from trace length).
    for r in results:
        r.pareto_objectives = _compute_base_objectives(r)

    # Step 2: Run comparative ranking (pairwise OR batched)
    if L4_STRATEGY == "batched_rank":
        await _run_batched_rank(results)
    else:
        await _run_pairwise(results)

    # Step 3: Compute Pareto front
    pareto_ids = _compute_pareto_front(results)

    return {
        "pareto_optimal_ids": pareto_ids,
        "per_result_objectives": {r.skill_id: dict(r.pareto_objectives) for r in results},
    }


def _compute_base_objectives(result: CompetitionResult) -> dict[str, float]:
    """Derive baseline objective scores from L1-L3 result fields."""
    from skillforge.config import MAX_TURNS

    correctness = 0.0
    if result.tests_pass is True:
        correctness = 1.0
    elif result.tests_pass is False:
        correctness = 0.0
    elif result.compiles:
        correctness = 0.5

    code_quality = result.lint_score if result.lint_score is not None else 0.5

    trigger_accuracy = 0.0
    if result.trigger_precision + result.trigger_recall > 0:
        # F1-style aggregate
        p, r_ = result.trigger_precision, result.trigger_recall
        trigger_accuracy = 2 * p * r_ / (p + r_) if (p + r_) > 0 else 0.0

    # token_efficiency: shorter traces are better (normalized to [0, 1])
    trace_len = len(result.trace)
    token_efficiency = max(0.0, 1.0 - (trace_len / (MAX_TURNS * 2)))

    consistency = 0.0  # L6 is v1.1

    return {
        "correctness": correctness,
        "token_efficiency": token_efficiency,
        "code_quality": code_quality,
        "trigger_accuracy": trigger_accuracy,
        "consistency": consistency,
    }


async def _run_pairwise(results: list[CompetitionResult]) -> None:
    """Run C(n,2) pairwise comparisons for each comparable criterion.

    Populates result.pairwise_wins with per-criterion win counts.
    """
    if len(results) < 2:
        for r in results:
            r.pairwise_wins = {c: 0 for c in _OBJECTIVES}
        return

    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    # Initialize win counts
    for r in results:
        r.pairwise_wins = {c: 0 for c in _OBJECTIVES}

    # For each criterion, run all pairs
    # In MVP we only do LLM pairwise on "correctness" (the others are already
    # derived deterministically from L1-L3 fields). This keeps cost bounded.
    criterion = "correctness"

    for a, b in itertools.combinations(results, 2):
        winner = await _compare_pair(client, a, b, criterion)
        if winner == "a":
            a.pairwise_wins[criterion] = a.pairwise_wins.get(criterion, 0) + 1
        elif winner == "b":
            b.pairwise_wins[criterion] = b.pairwise_wins.get(criterion, 0) + 1
        # tie → no increment


async def _compare_pair(
    client: AsyncAnthropic,
    a: CompetitionResult,
    b: CompetitionResult,
    criterion: str,
) -> str:
    """Return 'a', 'b', or 'tie' — which result is better on ``criterion``."""
    a_preview = _preview_output(a)
    b_preview = _preview_output(b)

    prompt = (
        f"Compare two candidate solutions on the criterion: {criterion}.\n\n"
        f"Solution A:\n{a_preview}\n\n"
        f"Solution B:\n{b_preview}\n\n"
        f"Which is better on {criterion}? Respond with ONLY one word: A, B, or TIE."
    )

    try:
        response = await client.messages.create(
            model=model_for("judge_comparative"),
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        text = (response.content[0].text if response.content else "").strip().upper()
    except Exception:  # noqa: BLE001
        return "tie"

    if text.startswith("A"):
        return "a"
    if text.startswith("B"):
        return "b"
    return "tie"


async def _run_batched_rank(results: list[CompetitionResult]) -> None:
    """Alternative to pairwise: one LLM call ranks all N candidates per criterion.

    ~10x cheaper than pairwise at pop=5. Populates pairwise_wins with
    rank-derived scores (N-1 = best, 0 = worst).
    """
    if len(results) < 2:
        for r in results:
            r.pairwise_wins = {c: 0 for c in _OBJECTIVES}
        return

    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    criterion = "correctness"

    numbered = "\n".join(
        f"{i + 1}. [{r.skill_id[:8]}]\n{_preview_output(r)}"
        for i, r in enumerate(results)
    )
    prompt = (
        f"Rank the following {len(results)} candidate solutions on the criterion: {criterion}.\n\n"
        f"{numbered}\n\n"
        f"Respond with ONLY a JSON array of the candidate numbers in order from best to worst, "
        f'like [3, 1, 4, 2]. No prose.'
    )

    try:
        response = await client.messages.create(
            model=model_for("judge_comparative"),
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text if response.content else "[]"
    except Exception:  # noqa: BLE001
        for r in results:
            r.pairwise_wins = {c: 0 for c in _OBJECTIVES}
        return

    # Parse the ranking
    match = re.search(r"\[[\d,\s]+\]", text)
    if not match:
        for r in results:
            r.pairwise_wins = {c: 0 for c in _OBJECTIVES}
        return

    try:
        ranking = json.loads(match.group(0))
    except json.JSONDecodeError:
        for r in results:
            r.pairwise_wins = {c: 0 for c in _OBJECTIVES}
        return

    # Rank → wins score: best gets N-1, worst gets 0
    n = len(results)
    rank_map: dict[int, int] = {}  # 1-based candidate number → rank position (0-indexed)
    for pos, candidate_num in enumerate(ranking):
        if isinstance(candidate_num, int):
            rank_map[candidate_num] = pos

    for i, r in enumerate(results):
        pos = rank_map.get(i + 1, n - 1)  # default to worst if missing
        r.pairwise_wins = {c: 0 for c in _OBJECTIVES}
        r.pairwise_wins[criterion] = n - 1 - pos


def _preview_output(result: CompetitionResult, max_chars: int = 600) -> str:
    """Compact preview of a result's output_files for LLM comparison."""
    if not result.output_files:
        return "(no output files)"
    parts: list[str] = []
    for path, content in list(result.output_files.items())[:3]:
        preview = content[:300]
        parts.append(f"=== {path} ===\n{preview}")
    joined = "\n\n".join(parts)
    if len(joined) > max_chars:
        return joined[:max_chars] + "\n... [truncated]"
    return joined


def _compute_pareto_front(results: list[CompetitionResult]) -> list[str]:
    """Return the list of skill_ids that are Pareto-optimal.

    A result is Pareto-optimal if no other result dominates it on ALL
    objectives (dominates = >= on every objective and > on at least one).
    """
    pareto_ids: list[str] = []
    for i, r in enumerate(results):
        dominated = False
        for j, other in enumerate(results):
            if i == j:
                continue
            if _dominates(other.pareto_objectives, r.pareto_objectives):
                dominated = True
                break
        if not dominated:
            pareto_ids.append(r.skill_id)
    return pareto_ids


def _dominates(a: dict[str, float], b: dict[str, float]) -> bool:
    """Return True if ``a`` dominates ``b`` (>= everywhere, > somewhere)."""
    all_objectives = set(a.keys()) | set(b.keys())
    better_anywhere = False
    for obj in all_objectives:
        av = a.get(obj, 0.0)
        bv = b.get(obj, 0.0)
        if av < bv:
            return False
        if av > bv:
            better_anywhere = True
    return better_anywhere
