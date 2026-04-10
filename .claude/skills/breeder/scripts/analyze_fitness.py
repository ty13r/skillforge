#!/usr/bin/env python3
"""Analyze a variant's fitness breakdown and recommend a mutation strategy.

Reads a fitness JSON produced by the Reviewer, identifies the lowest-scoring
metric across quantitative + qualitative dimensions, and looks up the matching
mutation strategy from the embedded metric->strategy table (kept in sync with
references/metrics-to-mutations.md).

Usage:
    python analyze_fitness.py --fitness /path/to/fitness.json

Output (stdout, JSON):
    {
      "variant_id": "...",
      "weakest_metric": "...",
      "weakest_score": 0.XX,
      "mutation_strategy": "...",
      "rationale": "..."
    }
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Metric -> (strategy_name, rationale_template).
# Keep in lockstep with references/metrics-to-mutations.md.
METRIC_TO_STRATEGY: dict[str, tuple[str, str]] = {
    "cyclomatic_complexity": (
        "simplify_control_flow",
        "High branching drives complexity. Extract helpers, collapse if/elif "
        "chains into dispatch tables, prefer early-return guard clauses.",
    ),
    "max_function_length": (
        "decompose_functions",
        "Long functions hide intent. Split into smaller named functions with "
        "single responsibilities; move setup into fixtures or constants.",
    ),
    "max_nesting_depth": (
        "flatten_nesting",
        "Deep nesting hurts readability and complexity. Apply guard clauses, "
        "early returns, and invert conditionals to keep the happy path flat.",
    ),
    "test_pass_rate": (
        "focus_on_correctness",
        "Failing tests outweigh style. Read the failing assertions from the "
        "trace, add I/O examples that mirror the failing shapes, strengthen "
        "the workflow step that produced the wrong output.",
    ),
    "trigger_precision": (
        "refine_description_exclusions",
        "Noisy triggering. Tighten the capability statement and append "
        "explicit 'NOT for X, Y, or Z' exclusions covering the adjacent "
        "domains the trace shows it falsely matched.",
    ),
    "trigger_recall": (
        "broaden_description_triggers",
        "Undertriggering. Add synonyms, file extensions, and colloquialisms "
        "the user might say; apply the 'pushy' pattern with 'even if they "
        "don't explicitly ask for X'.",
    ),
    "token_usage": (
        "reduce_verbosity",
        "Body is too verbose. Move detail into references/, compress prose, "
        "prefer bullets over paragraphs, cut ceremony from the workflow.",
    ),
    "instruction_compliance": (
        "strengthen_imperatives",
        "Claude ignored steps. Convert prose to numbered imperative steps, "
        "add explicit verbs (Run, Read, Validate), remove hedging language.",
    ),
    "coverage_delta": (
        "inject_edge_cases",
        "Tests cover only the happy path. Add 2-3 edge-case examples to the "
        "Examples section and to the fixture set so variants are forced to "
        "handle them.",
    ),
    "tool_precision": (
        "tighten_allowed_tools",
        "Wrong tools being used. Prune allowed-tools to the minimum set and "
        "add an explicit tool-use example showing the expected tool per step.",
    ),
    "cost_usd": (
        "compress_prompt",
        "Spend is too high. Shorten SKILL.md prose, move static reference "
        "content into referenceable files, and cache long fixtures.",
    ),
    "lint_score": (
        "add_formatting_rules",
        "Output fails style checks. Add formatting rules to the workflow, "
        "include a Gotcha about the specific lint rule that failed, and run "
        "a formatter in validate.sh.",
    ),
    "max_function_complexity": (
        "decompose_functions",
        "Individual function is doing too much. Split by responsibility.",
    ),
    "import_count": (
        "reduce_verbosity",
        "Excessive imports signal scope creep. Consolidate or remove unused.",
    ),
}

FALLBACK_STRATEGY = "generic_refinement"
FALLBACK_RATIONALE = (
    "Metric not found in lookup table. Falling back to generic refinement: "
    "read the trace, identify the most visible symptom, and apply the closest "
    "matching pattern from references/mutation-patterns.md. Flag the gap so "
    "the metrics-to-mutations table can be extended."
)

# Metrics where HIGH is bad (we invert interpretation).
HIGHER_IS_WORSE = {
    "cyclomatic_complexity",
    "max_function_length",
    "max_nesting_depth",
    "max_function_complexity",
    "token_usage",
    "cost_usd",
    "import_count",
}


def _normalize(metric: str, score: float) -> float:
    """Return a 0..1 'goodness' score so we can pick the lowest uniformly."""
    if score is None:
        return 1.0
    try:
        s = float(score)
    except (TypeError, ValueError):
        return 1.0
    if 0.0 <= s <= 1.0:
        return s
    if metric in HIGHER_IS_WORSE:
        return max(0.0, min(1.0, 1.0 - (s / 50.0)))
    return max(0.0, min(1.0, s))


def find_weakest(fitness: dict) -> tuple[str, float]:
    """Return (metric_name, normalized_score) for the weakest dimension."""
    candidates: list[tuple[str, float]] = []
    for bucket in ("quantitative", "qualitative"):
        values = fitness.get(bucket) or {}
        if not isinstance(values, dict):
            continue
        for metric, score in values.items():
            candidates.append((metric, _normalize(metric, score)))
    if not candidates:
        return ("unknown", 1.0)
    candidates.sort(key=lambda pair: pair[1])
    return candidates[0]


def lookup_strategy(metric: str) -> tuple[str, str]:
    if metric in METRIC_TO_STRATEGY:
        return METRIC_TO_STRATEGY[metric]
    return (FALLBACK_STRATEGY, FALLBACK_RATIONALE)


def analyze(fitness_path: Path) -> dict:
    try:
        data = json.loads(fitness_path.read_text())
    except FileNotFoundError:
        raise SystemExit(f"fitness file not found: {fitness_path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"fitness file is not valid JSON: {exc}")

    variant_id = data.get("variant_id", "unknown")
    weakest_metric, weakest_score = find_weakest(data)
    strategy, rationale_template = lookup_strategy(weakest_metric)

    rationale = (
        f"{weakest_metric}={weakest_score:.2f} is the weakest dimension. "
        f"{rationale_template} "
        f"Cite a concrete symptom from the trace before applying the edit."
    )

    return {
        "variant_id": variant_id,
        "weakest_metric": weakest_metric,
        "weakest_score": round(float(weakest_score), 4),
        "mutation_strategy": strategy,
        "rationale": rationale,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pick a mutation strategy from a variant's fitness breakdown."
    )
    parser.add_argument(
        "--fitness",
        required=True,
        type=Path,
        help="Path to a JSON file containing the variant fitness breakdown.",
    )
    args = parser.parse_args()

    result = analyze(args.fitness)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
