#!/usr/bin/env python3
"""SKLD-bench score.py for elixir-pattern-match-refactor.

Refactor-quality scorer. Rewards idiomatic Elixir patterns (multi-clause
function heads, guards, pipes, with expressions, pattern-matched destructures)
and penalizes Ruby/Java-style imperative code (if/case chains, defensive
is_nil checks, manual accumulator loops).
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


# ---- Canonical idiomatic patterns ------------------------------------------

DEF_LINE = re.compile(r"^\s*(?:def|defp)\s+([a-z_][a-z0-9_?!]*)\s*\(", re.MULTILINE)
PIPE_OP = re.compile(r"\|>")
WITH_EXPR = re.compile(r"\bwith\b\s+[\w%{][^\n]*<-", re.MULTILINE)
GUARD_WHEN = re.compile(r"\)\s+when\s+", re.MULTILINE)
FUNCTION_HEAD_GUARD = re.compile(r"def\s+\w+\s*\([^)]*\)\s+when\s", re.MULTILINE)
MAP_DESTRUCTURE = re.compile(r"def\s+\w+\s*\(\s*%\{[^}]*=>", re.MULTILINE)
STRUCT_DESTRUCTURE = re.compile(r"def\s+\w+\s*\(\s*%[A-Z][\w.]*\{", re.MULTILINE)
TUPLE_MATCH = re.compile(r"def\s+\w+\s*\(\s*\{", re.MULTILINE)
LIST_HEAD_TAIL = re.compile(r"\[\s*\w+\s*\|\s*\w+\s*\]")
BINARY_PATTERN = re.compile(r'<<\s*"[^"]*"\s*,\s*\w+::binary\s*>>')
ENUM_REDUCE = re.compile(r"Enum\.reduce\s*\(")
ENUM_MAP_FILTER = re.compile(r"Enum\.(?:map|filter|flat_map|take_while|drop_while)\s*\(")

# ---- Anti-patterns ---------------------------------------------------------

# if/case/cond keywords (counted)
IF_KEYWORD = re.compile(r"\bif\b", re.MULTILINE)
CASE_KEYWORD = re.compile(r"\bcase\b\s+.*\s+do\b", re.MULTILINE)
COND_KEYWORD = re.compile(r"\bcond\b\s+do\b", re.MULTILINE)
UNLESS_KEYWORD = re.compile(r"\bunless\b", re.MULTILINE)

# Defensive nil checks
IS_NIL_GUARD = re.compile(r"is_nil\s*\(")
NIL_EQUALITY = re.compile(r"(?:==|===)\s*nil\b")
SAFE_NAV_PUN = re.compile(r"(\w+)\s*&&\s*\1\.[a-z_]")  # user && user.name

# Imperative-ish patterns
ACCUMULATOR_MANUAL = re.compile(
    r"Enum\.reduce\s*\([^,]+,\s*\[\]\s*,\s*fn", re.MULTILINE
)  # Enum.reduce with [] is often a proxy for accumulator
INTERMEDIATE_TEMP_VARS = re.compile(
    r"^\s*(?:temp|tmp|result|data|value|x|y)_?\d*\s*=", re.MULTILINE
)
EARLY_RETURN = re.compile(r"throw\s*\(|raise\s+.*\b(?:early_return|nope)\b")

# String.Contains / ends_with instead of binary patterns
STRING_ENDS_WITH = re.compile(r"String\.(?:ends_with\?|starts_with\?)\s*\(")

# Bad guards (non-whitelisted function calls)
COMPLEX_GUARD = re.compile(
    r"when\s+[\w.]+\.(?:some|any|all)\?", re.MULTILINE
)


# ---- Capability-specific anti-patterns -------------------------------------

CAPABILITY_ANTIPATTERNS = {
    "function-head-pattern-matching": [
        # Measured by counting function heads instead
    ],
    "guard-clauses": [
        (COMPLEX_GUARD, "disallowed function call in guard", 0.6),
    ],
    "pipe-operator-flows": [
        (INTERMEDIATE_TEMP_VARS, "intermediate temp_var = ... breaks pipe flow", 0.4),
    ],
    "with-expressions": [
        # Detected via positive signal
    ],
    "recursive-functions": [
        # Detected via positive signal
    ],
    "enum-vs-recursion-choice": [
        # Detected via positive signal
    ],
    "map-and-struct-destructuring": [
        # Detected via positive signal
    ],
    "binary-pattern-matching-basic": [
        (STRING_ENDS_WITH, "String.ends_with? instead of binary pattern", 0.4),
    ],
    "cond-and-if-reduction": [
        # Hard-count if/case/cond below
    ],
    "defensive-nil-checks-elimination": [
        (IS_NIL_GUARD, "is_nil() defensive check", 0.7),
        (NIL_EQUALITY, "x == nil / x === nil check", 0.6),
        (SAFE_NAV_PUN, "`x && x.field` Ruby-style safe-nav pun", 0.7),
    ],
    "refactor-philosophy": [
        (IS_NIL_GUARD, "defensive is_nil check (structural anti-pattern)", 0.5),
        (INTERMEDIATE_TEMP_VARS, "intermediate temps (structural anti-pattern)", 0.4),
    ],
}


# ---- Capability-specific positive signals ----------------------------------

CAPABILITY_POSITIVE = {
    "refactor-philosophy": [
        (PIPE_OP, "pipe operator used"),
        (WITH_EXPR, "with expression used"),
    ],
    "function-head-pattern-matching": [
        (FUNCTION_HEAD_GUARD, "function head guard clause"),
        (MAP_DESTRUCTURE, "map destructure in function head"),
        (STRUCT_DESTRUCTURE, "struct destructure in function head"),
    ],
    "guard-clauses": [
        (GUARD_WHEN, "when guard present"),
    ],
    "pipe-operator-flows": [
        (PIPE_OP, "pipe operator used"),
        (ENUM_MAP_FILTER, "Enum.map/filter/flat_map in pipe"),
    ],
    "with-expressions": [
        (WITH_EXPR, "with <- ... do ... else pattern"),
    ],
    "recursive-functions": [
        (LIST_HEAD_TAIL, "list [h | t] head/tail pattern"),
    ],
    "enum-vs-recursion-choice": [
        (ENUM_REDUCE, "Enum.reduce used"),
        (ENUM_MAP_FILTER, "Enum.map/filter used"),
    ],
    "map-and-struct-destructuring": [
        (MAP_DESTRUCTURE, "map destructure %{key => val}"),
        (STRUCT_DESTRUCTURE, "struct destructure %Struct{field: val}"),
    ],
    "binary-pattern-matching-basic": [
        (BINARY_PATTERN, "binary pattern <<\"prefix\", rest::binary>>"),
    ],
    "cond-and-if-reduction": [
        (FUNCTION_HEAD_GUARD, "function head guard (replaces cond)"),
    ],
    "defensive-nil-checks-elimination": [
        (FUNCTION_HEAD_GUARD, "function head guard (replaces nil check)"),
    ],
}


def _has(pattern: re.Pattern, text: str) -> bool:
    return bool(pattern.search(text))


def _count(pattern: re.Pattern, text: str) -> int:
    return len(pattern.findall(text))


def _load_files(output_dir: Path, expected_files: list) -> dict:
    contents = {}
    for rel in expected_files:
        f = output_dir / rel
        if f.exists():
            try:
                contents[rel] = f.read_text()
            except Exception:
                contents[rel] = ""
        else:
            contents[rel] = None
    return contents


def _function_head_count(text: str) -> int:
    """Count distinct function names that have >1 def clause (pattern matching)."""
    names = [m.group(1) for m in DEF_LINE.finditer(text)]
    counts = Counter(names)
    return sum(1 for n, c in counts.items() if c > 1)


def score_challenge(challenge: dict, output_dir: Path) -> dict:
    objectives: dict = {}
    diagnostics: list = []

    expected = challenge.get("expected_outputs", {})
    scoring = challenge.get("scoring", {})
    primary_cap = scoring.get("primary_capability", "")

    expected_files = expected.get("files", []) or []
    must_contain = expected.get("must_contain", []) or []
    must_not_contain = expected.get("must_not_contain", []) or []

    file_contents = _load_files(output_dir, expected_files)

    for rel, content in file_contents.items():
        objectives[f"file_present:{rel}"] = {
            "passed": content is not None,
            "weight": 1.0,
            "actual": "present" if content is not None else "missing",
            "expected": "present",
            "details": f"Expected output file {rel}",
        }

    present_contents = {k: v for k, v in file_contents.items() if v}

    if not present_contents:
        for pat in must_contain:
            objectives[f"contains:{pat}"] = {
                "passed": False, "weight": 1.5,
                "actual": "absent", "expected": "present",
                "details": f"Required substring: {pat!r}",
            }
        for pat in must_not_contain:
            objectives[f"absent:{pat}"] = {
                "passed": True, "weight": 0.0,
                "actual": "absent", "expected": "absent",
                "details": f"Forbidden substring: {pat!r}",
            }
        total = sum(o["weight"] for o in objectives.values()) or 1.0
        passed = sum(o["weight"] for o in objectives.values() if o["passed"])
        score = passed / total
        return {
            "challenge_id": challenge.get("id"),
            "passed": score >= 0.7,
            "score": round(score, 4),
            "objectives": objectives,
            "diagnostics": ["no output files produced"],
        }

    all_text = "\n".join(v for v in present_contents.values() if v)

    # must_contain
    for pat in must_contain:
        present = pat in all_text
        objectives[f"contains:{pat}"] = {
            "passed": present, "weight": 2.5,
            "actual": "present" if present else "absent",
            "expected": "present",
            "details": f"Required substring: {pat!r}",
        }

    # must_not_contain
    for pat in must_not_contain:
        absent = pat not in all_text
        weight = 2.5 if not absent else 0.25
        objectives[f"absent:{pat}"] = {
            "passed": absent, "weight": weight,
            "actual": "absent" if absent else "present",
            "expected": "absent",
            "details": f"Forbidden substring: {pat!r}",
        }

    # Capability-specific anti-patterns
    for ap_regex, ap_desc, weight in CAPABILITY_ANTIPATTERNS.get(primary_cap, []):
        found = _has(ap_regex, all_text)
        effective_weight = weight * 2.0 if found else weight * 0.25
        objectives[f"antipattern:{ap_desc}"] = {
            "passed": not found, "weight": effective_weight,
            "actual": "present" if found else "absent",
            "expected": "absent",
            "details": f"Anti-pattern for {primary_cap}",
        }
        if found:
            diagnostics.append(f"anti-pattern: {ap_desc}")

    # Capability-specific positive signals
    for pos_regex, pos_desc in CAPABILITY_POSITIVE.get(primary_cap, []):
        found = _has(pos_regex, all_text)
        objectives[f"positive:{pos_desc}"] = {
            "passed": found, "weight": 0.6,
            "actual": "present" if found else "absent",
            "expected": "present",
            "details": f"Positive signal for {primary_cap}",
        }

    # Cross-cutting: count imperative constructs — fewer is better
    if_count = _count(IF_KEYWORD, all_text)
    case_count = _count(CASE_KEYWORD, all_text)
    cond_count = _count(COND_KEYWORD, all_text)
    is_nil_count = _count(IS_NIL_GUARD, all_text)
    multi_heads = _function_head_count(all_text)
    pipe_count = _count(PIPE_OP, all_text)
    with_count = _count(WITH_EXPR, all_text)

    # Imperative-construct score: penalize high if/case/cond counts
    imperative_total = if_count + case_count + cond_count
    objectives["cross:imperative_construct_count"] = {
        "passed": imperative_total <= 2,  # allow up to 2 conditionals in refactored code
        "weight": 1.5 if imperative_total > 4 else 0.4,
        "actual": str(imperative_total),
        "expected": "<=2",
        "details": f"if={if_count} case={case_count} cond={cond_count}",
    }
    if imperative_total > 4:
        diagnostics.append(f"too many imperative constructs ({imperative_total})")

    objectives["cross:is_nil_count"] = {
        "passed": is_nil_count == 0,
        "weight": 1.0 if is_nil_count > 0 else 0.25,
        "actual": str(is_nil_count),
        "expected": "0",
        "details": "is_nil() defensive checks",
    }
    if is_nil_count > 0:
        diagnostics.append(f"is_nil() present ({is_nil_count})")

    # Positive cross-cutting: function-head pattern matching present
    objectives["cross:multi_head_functions"] = {
        "passed": multi_heads > 0,
        "weight": 0.8 if multi_heads > 0 else 0.2,
        "actual": str(multi_heads),
        "expected": ">=1",
        "details": "functions with multiple def clauses",
    }

    # Positive cross-cutting: pipe operator present
    objectives["cross:pipe_operator"] = {
        "passed": pipe_count > 0,
        "weight": 0.5,
        "actual": str(pipe_count),
        "expected": ">=1",
        "details": "|> pipe operator count",
    }

    total = sum(o["weight"] for o in objectives.values()) or 1.0
    passed = sum(o["weight"] for o in objectives.values() if o["passed"])
    score = passed / total

    return {
        "challenge_id": challenge.get("id"),
        "passed": score >= 0.7,
        "score": round(score, 4),
        "objectives": objectives,
        "diagnostics": diagnostics,
    }


def main() -> None:
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
