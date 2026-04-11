#!/usr/bin/env python3
"""SKLD-bench score.py for elixir-ecto-query-writer.

Scores competitor output against a single challenge JSON. Family-specific
discrimination emphasizes:
  1. Pin operator presence inside `where:` / `select:` / `order_by:` clauses.
  2. Preload-strategy detection — distinguishes `preload: [:posts]` (struct)
     from `join: ... preload: [posts: p]` (join-preload).
  3. Query-macro structure — detects `from`, `where`, `select`, `order_by`,
     `join`, `preload`, `having`, `group_by` presence.
  4. Anti-pattern checks from research.md — `Ecto.Adapters.SQL.query`,
     fragment string interpolation, `on_conflict: :replace_all` without
     `conflict_target`, `nil` comparisons in filters.

Output contract: JSON to stdout per SCHEMAS.md. Exit 0 on success, 1 on
malformed input, 2 on internal scorer bug.
"""

import argparse
import json
import re
import sys
from pathlib import Path


# --- Ecto-specific pattern library ---

# Detects `u.<ident> == <ident>` where the right-hand side is a plain var (no pin)
MISSING_PIN_BINARY_RE = re.compile(
    r"(?:where|and|or)[^,\n]*\b([a-z_][a-z0-9_]*)\.(?:[a-z_][a-z0-9_]*)"
    r"\s*(?:==|!=|<|>|<=|>=)\s*([a-z_][a-z0-9_]*)\b(?!\s*\()"
)

# Detects pin operator applications `^variable`
PIN_OPERATOR_RE = re.compile(r"\^[a-z_][a-zA-Z0-9_]*")

# Detects join-preload pattern: join with same assoc + preload referencing its binding
JOIN_PRELOAD_HAS_MANY_RE = re.compile(
    r"join:\s*\w+\s+in\s+assoc\([^,]+,\s*:(\w+)\)[^)]*?preload:\s*\[\1:\s*\w+\]",
    re.DOTALL,
)

# Detects struct-preload pattern: `preload: [:atom]` or `preload: [atom: :nested]`
STRUCT_PRELOAD_RE = re.compile(r"preload:\s*\[:?[a-z_]+")

# Detects raw SQL escape hatch
RAW_SQL_RE = re.compile(r"Ecto\.Adapters\.SQL\.query")

# Detects fragment with string interpolation — the SQL injection anti-pattern
FRAGMENT_INTERP_RE = re.compile(r'fragment\(\s*"[^"]*#\{')

# Detects on_conflict: :replace_all (generally unsafe for partial changesets)
REPLACE_ALL_RE = re.compile(r"on_conflict:\s*:replace_all\b")

# Detects nil comparison (anti-pattern)
NIL_COMPARE_RE = re.compile(r"\b\w+\.\w+\s*==\s*nil\b")

# Detects dynamic query composition (dynamic(true) or Enum.reduce with dynamic)
DYNAMIC_REDUCE_RE = re.compile(r"Enum\.reduce\([^)]+,\s*dynamic\(true\)")

# Detects named binding pattern: `as: :atom`
NAMED_BINDING_RE = re.compile(r"as:\s*:[a-z_]+")

# Detects typed window function form: `row_number() |> over(...)`
TYPED_WINDOW_RE = re.compile(r"(?:row_number|rank|dense_rank|lag|lead|sum|count|avg)\(\)?\s*\|>\s*over\(")

# Detects fragment-based window function (anti-pattern when typed exists)
FRAGMENT_WINDOW_RE = re.compile(
    r'fragment\(\s*"(?:row_number|rank|dense_rank|lag|lead|RANK|ROW_NUMBER)[^"]*OVER'
)

# Detects parent_as for correlated subqueries
PARENT_AS_RE = re.compile(r"parent_as\(\s*:[a-z_]+\s*\)")

# Detects subquery helper
SUBQUERY_HELPER_RE = re.compile(r"\bsubquery\(")


def ecto_diagnostics(content: str) -> list[str]:
    """Return a list of Ecto-specific diagnostics found in the content."""
    diags = []

    if RAW_SQL_RE.search(content):
        diags.append("anti-pattern: Ecto.Adapters.SQL.query raw SQL fallback present")

    if FRAGMENT_INTERP_RE.search(content):
        diags.append("anti-pattern: fragment with string interpolation (SQL injection)")

    if REPLACE_ALL_RE.search(content):
        diags.append("warning: on_conflict: :replace_all can clobber unspecified fields with NULL")

    if NIL_COMPARE_RE.search(content):
        diags.append("anti-pattern: `== nil` filter (use is_nil/1)")

    if FRAGMENT_WINDOW_RE.search(content):
        diags.append("hint: typed window function form exists (row_number() |> over(...))")

    return diags


def ecto_capability_signals(content: str) -> dict[str, bool]:
    """Return signals about which capabilities are demonstrated in the output."""
    return {
        "has_pin": bool(PIN_OPERATOR_RE.search(content)),
        "has_struct_preload": bool(STRUCT_PRELOAD_RE.search(content)),
        "has_join_preload_hasmany": bool(JOIN_PRELOAD_HAS_MANY_RE.search(content)),
        "has_dynamic_reduce": bool(DYNAMIC_REDUCE_RE.search(content)),
        "has_named_binding": bool(NAMED_BINDING_RE.search(content)),
        "has_typed_window": bool(TYPED_WINDOW_RE.search(content)),
        "has_fragment_window_antipattern": bool(FRAGMENT_WINDOW_RE.search(content)),
        "has_parent_as": bool(PARENT_AS_RE.search(content)),
        "has_subquery_helper": bool(SUBQUERY_HELPER_RE.search(content)),
        "has_raw_sql": bool(RAW_SQL_RE.search(content)),
        "has_fragment_interpolation": bool(FRAGMENT_INTERP_RE.search(content)),
        "has_replace_all": bool(REPLACE_ALL_RE.search(content)),
        "has_nil_compare": bool(NIL_COMPARE_RE.search(content)),
    }


def score_challenge(challenge: dict, output_dir: Path) -> dict:
    """Family-specific scoring: expected file + must_contain/must_not_contain + ecto checks."""
    objectives: dict[str, dict] = {}
    expected = challenge.get("expected_outputs", {}) or {}
    files = expected.get("files", []) or []
    must_contain = expected.get("must_contain", []) or []
    must_not_contain = expected.get("must_not_contain", []) or []

    diagnostics: list[str] = []
    aggregated_content = ""

    # Score file-by-file. Each challenge may require multiple files; all must exist.
    for rel in files:
        f = output_dir / rel
        if not f.exists():
            objectives[f"file:{rel}"] = {
                "passed": False,
                "weight": 2.0,
                "actual": "missing",
                "expected": "present",
                "details": f"Expected output file {rel} was not produced",
            }
            continue

        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            objectives[f"file:{rel}"] = {
                "passed": False,
                "weight": 2.0,
                "actual": f"read error: {e}",
                "expected": "readable",
                "details": f"Could not read {rel}",
            }
            continue

        objectives[f"file:{rel}"] = {
            "passed": True,
            "weight": 0.5,
            "actual": "present",
            "expected": "present",
            "details": f"Found {rel} ({len(content)} bytes)",
        }
        aggregated_content += "\n" + content

    # must_contain patterns (each is equal-weighted within the set)
    mc_weight = 2.0 / max(len(must_contain), 1) if must_contain else 0
    for pat in must_contain:
        present = pat in aggregated_content
        objectives[f"contains:{pat[:60]}"] = {
            "passed": present,
            "weight": mc_weight,
            "actual": "present" if present else "absent",
            "expected": "present",
            "details": f"Looking for `{pat}` in any output file",
        }

    # must_not_contain patterns (each is equal-weighted within the set)
    mnc_weight = 1.5 / max(len(must_not_contain), 1) if must_not_contain else 0
    for pat in must_not_contain:
        absent = pat not in aggregated_content
        objectives[f"absent:{pat[:60]}"] = {
            "passed": absent,
            "weight": mnc_weight,
            "actual": "absent" if absent else "present",
            "expected": "absent",
            "details": f"Looking for absence of `{pat}` in any output file",
        }

    # Ecto-specific bonus checks based on the primary capability
    primary = (challenge.get("scoring", {}) or {}).get("primary_capability", "")
    signals = ecto_capability_signals(aggregated_content)

    # Capability-aware bonuses (+0.5 weight each when they apply)
    if primary == "pin-operator-safety":
        objectives["ecto:pin_present"] = {
            "passed": signals["has_pin"],
            "weight": 0.5,
            "actual": "pin operator found" if signals["has_pin"] else "no pin operator",
            "expected": "pin operator present",
            "details": "Pin operator `^var` should appear in the output",
        }

    if primary == "preloads":
        # Either a struct preload OR an appropriate join-preload should be present
        has_any_preload = signals["has_struct_preload"] or signals["has_join_preload_hasmany"]
        objectives["ecto:preload_present"] = {
            "passed": has_any_preload,
            "weight": 0.5,
            "actual": "preload found" if has_any_preload else "no preload",
            "expected": "preload present",
            "details": "Some form of preload should be present for preload challenges",
        }

    if primary == "dynamic-query-builder":
        objectives["ecto:dynamic_reduce"] = {
            "passed": signals["has_dynamic_reduce"],
            "weight": 0.5,
            "actual": "dynamic reduce found" if signals["has_dynamic_reduce"] else "no dynamic reduce",
            "expected": "Enum.reduce + dynamic(true)",
            "details": "Canonical dynamic-query pattern should be present",
        }

    if primary == "window-functions":
        objectives["ecto:typed_window"] = {
            "passed": signals["has_typed_window"] and not signals["has_fragment_window_antipattern"],
            "weight": 0.5,
            "actual": "typed window" if signals["has_typed_window"] else "no typed window",
            "expected": "typed `|> over(...)` form",
            "details": "Typed window function form is preferred over fragments",
        }

    if primary == "subqueries":
        objectives["ecto:subquery_helper"] = {
            "passed": signals["has_subquery_helper"] or signals["has_parent_as"],
            "weight": 0.5,
            "actual": "subquery/parent_as found" if (signals["has_subquery_helper"] or signals["has_parent_as"]) else "neither",
            "expected": "subquery/1 or parent_as/1 present",
            "details": "Subquery challenges should use typed Ecto subquery helpers",
        }

    # Universal anti-pattern penalties — reduce score if any are present
    if signals["has_raw_sql"] and primary in ("subqueries", "dynamic-query-builder", "raw-sql-fragment"):
        diagnostics.append("penalty: raw Ecto.Adapters.SQL.query found")

    if signals["has_fragment_interpolation"]:
        diagnostics.append("penalty: fragment with string interpolation found")

    diagnostics.extend(ecto_diagnostics(aggregated_content))

    # Compute weighted score
    total_weight = sum(o["weight"] for o in objectives.values()) or 1.0
    weighted_score = sum(o["weight"] for o in objectives.values() if o["passed"])
    score = weighted_score / total_weight

    return {
        "challenge_id": challenge["id"],
        "passed": score >= 0.7,
        "score": score,
        "objectives": objectives,
        "diagnostics": diagnostics,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--challenge", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()

    try:
        challenge = json.loads(args.challenge.read_text())
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(json.dumps({"error": f"malformed challenge: {e}"}))
        sys.exit(1)

    try:
        result = score_challenge(challenge, args.output)
    except Exception as e:
        print(json.dumps({"error": f"scorer crashed: {e}"}))
        sys.exit(2)

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
