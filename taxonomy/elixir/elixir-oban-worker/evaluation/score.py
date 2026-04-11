#!/usr/bin/env python3
"""SKLD-bench score.py for elixir-oban-worker.

Family-specific deterministic scorer for Oban worker challenges.

Checks the generic `must_contain` / `must_not_contain` contract from the
challenge JSON and adds Oban-specific anti-pattern detectors derived from
the three iron laws (idempotency, string keys, no structs) and the
return-value protocol.
"""
import argparse
import json
import re
import sys
from pathlib import Path


# ---- family-specific regex detectors ---------------------------------------

# atom keys inside a perform/1 function head or an args-building expression
# Matches:
#   def perform(%Oban.Job{args: %{user_id: ...}})
#   def perform(%{user_id: ...})
ATOM_KEY_IN_PERFORM = re.compile(
    r"def\s+perform\s*\(\s*(?:%Oban\.Job\{\s*args:\s*)?%\{\s*[a-z_][a-z0-9_]*\s*:",
    re.MULTILINE,
)
ATOM_KEY_IN_ARGS_BUILD = re.compile(
    r"%\{\s*[a-z_][a-z0-9_]*\s*:\s*[a-zA-Z_][\w.]*\s*(?:,|\})",
    re.MULTILINE,
)

# String.to_atom inside a worker body is unsafe (atom exhaustion)
STRING_TO_ATOM = re.compile(r"String\.to_atom\s*\(", re.MULTILINE)

# Deprecated :discard return form
DISCARD_RETURN = re.compile(r"\{\s*:discard\s*,", re.MULTILINE)

# Process.sleep inside a worker
PROCESS_SLEEP = re.compile(r"Process\.sleep\s*\(", re.MULTILINE)

# max_attempts: 1 is a defensive anti-pattern for real work
MAX_ATTEMPTS_ONE = re.compile(r"max_attempts:\s*1\b", re.MULTILINE)

# raise inside a perform/1 clause on rate limit (should be {:snooze, _})
RAISE_RATE_LIMIT = re.compile(
    r"raise\s+\".*(?:rate|429|limit)", re.IGNORECASE | re.MULTILINE
)

# Passing a struct directly in args (%User{}, %DateTime{}, %Decimal{}, etc.)
STRUCT_IN_ARGS = re.compile(
    r"%\{\s*\w+:\s*%[A-Z][A-Za-z0-9_.]*\{", re.MULTILINE
)

# Return value shapes
RETURN_OK = re.compile(r"(^|\s)(:ok|\{:ok,\s*[^}]*\})\b", re.MULTILINE)
RETURN_ERROR = re.compile(r"\{:error,\s*[^}]*\}", re.MULTILINE)
RETURN_CANCEL = re.compile(r"\{:cancel,\s*[^}]*\}", re.MULTILINE)
RETURN_SNOOZE = re.compile(r"\{:snooze,\s*[^}]*\}", re.MULTILINE)

# Oban.Job destructure shape
JOB_DESTRUCTURE = re.compile(
    r"%Oban\.Job\{\s*(?:[a-z_]+:\s*[^,}]+,?\s*)*args:\s*%\{", re.MULTILINE
)


# ---- capability-specific anti-pattern penalties ----------------------------

# A map from capability slug → list of (regex, description, penalty_weight)
# anti-patterns. Each found anti-pattern subtracts from the challenge score.
CAPABILITY_ANTIPATTERNS = {
    "args-serialization": [
        (ATOM_KEY_IN_PERFORM, "atom keys in perform/1 head", 0.5),
        (STRUCT_IN_ARGS, "struct stored directly in args", 0.5),
        (STRING_TO_ATOM, "String.to_atom in worker body (atom exhaustion)", 0.3),
    ],
    "perform-callback-basics": [
        (ATOM_KEY_IN_PERFORM, "atom keys in perform/1 head", 0.5),
    ],
    "return-values": [
        (DISCARD_RETURN, "deprecated {:discard, _} return", 0.5),
        (RAISE_RATE_LIMIT, "raise on rate-limit instead of {:snooze, _}", 0.4),
    ],
    "retry-strategy": [
        (PROCESS_SLEEP, "Process.sleep-based hand-rolled retry", 0.4),
        (MAX_ATTEMPTS_ONE, "max_attempts: 1 defeats retry semantics", 0.3),
    ],
    "worker-philosophy": [
        (PROCESS_SLEEP, "Process.sleep in a worker", 0.3),
        (MAX_ATTEMPTS_ONE, "max_attempts: 1 undermines idempotency assumptions", 0.2),
    ],
    "telemetry-and-observability": [
        (
            re.compile(r"\[:oban,\s*:worker,\s*:exception\]"),
            "wrong event name [:oban, :worker, :exception] (should be [:oban, :job, :exception])",
            0.6,
        ),
    ],
}


# ---- positive signals ------------------------------------------------------

CAPABILITY_POSITIVE = {
    "args-serialization": [
        (re.compile(r'"\w+"\s*=>'), "string-keyed args present"),
    ],
    "perform-callback-basics": [
        (JOB_DESTRUCTURE, "perform/1 destructures %Oban.Job{args: ...}"),
    ],
    "return-values": [
        (RETURN_CANCEL, "{:cancel, _} return present"),
    ],
    "retry-strategy": [
        (
            re.compile(r"def\s+backoff\s*\("),
            "backoff/1 callback defined",
        ),
    ],
    "unique-constraints": [
        (
            re.compile(r"unique:\s*\[", re.MULTILINE),
            "unique: [ ... ] block present",
        ),
        (
            re.compile(r"period:\s*\d"),
            "unique period specified",
        ),
    ],
    "cron-scheduling": [
        (
            re.compile(r'"[\d*/,\-\s]+"\s*,\s*MyApp\.'),
            "crontab tuple shape present",
        ),
    ],
    "transactional-jobs": [
        (
            re.compile(r"Ecto\.Multi\.new"),
            "Ecto.Multi.new pipeline",
        ),
        (
            re.compile(r"Oban\.insert\s*\(\s*:"),
            "Oban.insert with Multi key",
        ),
    ],
    "testing-workers": [
        (
            re.compile(r"perform_job\s*\("),
            "perform_job/3 helper used",
        ),
    ],
    "telemetry-and-observability": [
        (
            re.compile(r"\[:oban,\s*:job,\s*:(?:start|stop|exception)\]"),
            "correct [:oban, :job, :_] event tuple",
        ),
    ],
}


def _has(pattern: re.Pattern, text: str) -> bool:
    return bool(pattern.search(text))


def _load_files(output_dir: Path, expected_files: list[str]) -> dict[str, str]:
    """Read each expected output file; missing files return empty string."""
    contents = {}
    for rel in expected_files:
        f = output_dir / rel
        if f.exists():
            try:
                contents[rel] = f.read_text()
            except Exception:
                contents[rel] = ""
        else:
            contents[rel] = None  # sentinel for missing
    return contents


def score_challenge(challenge: dict, output_dir: Path) -> dict:
    """Main scoring function."""
    objectives: dict[str, dict] = {}
    diagnostics: list[str] = []

    expected = challenge.get("expected_outputs", {})
    scoring = challenge.get("scoring", {})
    primary_cap = scoring.get("primary_capability", "")

    expected_files = expected.get("files", [])
    must_contain = expected.get("must_contain", [])
    must_not_contain = expected.get("must_not_contain", [])

    if not expected_files:
        expected_files = []

    file_contents = _load_files(output_dir, expected_files)

    # 1) File presence
    for rel, content in file_contents.items():
        objectives[f"file_present:{rel}"] = {
            "passed": content is not None,
            "weight": 1.0,
            "actual": "present" if content is not None else "missing",
            "expected": "present",
            "details": f"Expected output file {rel}",
        }

    # Present content for downstream checks.
    present_contents = {k: v for k, v in file_contents.items() if v}

    # Emit failing objectives for must_contain / must_not_contain even if
    # no files exist, so an empty file can never score well.
    if not present_contents:
        for pat in must_contain:
            objectives[f"contains:{pat}"] = {
                "passed": False,
                "weight": 1.5,
                "actual": "absent",
                "expected": "present",
                "details": f"Required substring: {pat!r}",
            }
        # must_not_contain trivially pass on empty input — but zero-weight
        # them so they don't help the score.
        for pat in must_not_contain:
            objectives[f"absent:{pat}"] = {
                "passed": True,
                "weight": 0.0,
                "actual": "absent",
                "expected": "absent",
                "details": f"Forbidden substring: {pat!r}",
            }

        total_weight = sum(o["weight"] for o in objectives.values()) or 1.0
        passed_weight = sum(
            o["weight"] for o in objectives.values() if o["passed"]
        )
        score = passed_weight / total_weight
        return {
            "challenge_id": challenge.get("id"),
            "passed": score >= 0.7,
            "score": round(score, 4),
            "objectives": objectives,
            "diagnostics": ["no output files produced"],
        }

    # Concatenated text across all present files — most rules apply globally.
    all_text = "\n".join(v for v in present_contents.values() if v)

    # 2) must_contain substrings (required to pass challenge)
    # Weight is substantially higher so missing required content dominates.
    for pat in must_contain:
        present = pat in all_text
        objectives[f"contains:{pat}"] = {
            "passed": present,
            "weight": 2.5,  # structural match weighted higher than style
            "actual": "present" if present else "absent",
            "expected": "present",
            "details": f"Required substring: {pat!r}",
        }

    # 3) must_not_contain substrings (anti-patterns).
    # When the pattern is PRESENT (bad), count weight; when absent (good),
    # give only minimal credit so absence alone cannot sustain a high score.
    for pat in must_not_contain:
        absent = pat not in all_text
        # Hefty penalty if the forbidden pattern appears; tiny credit if not.
        weight = 2.0 if not absent else 0.25
        objectives[f"absent:{pat}"] = {
            "passed": absent,
            "weight": weight,
            "actual": "absent" if absent else "present",
            "expected": "absent",
            "details": f"Forbidden substring: {pat!r}",
        }

    # 4) Capability-specific anti-pattern regex detectors.
    # Like must_not_contain, FOUND = big penalty, ABSENT = minimal credit.
    for ap_regex, ap_desc, weight in CAPABILITY_ANTIPATTERNS.get(primary_cap, []):
        found = _has(ap_regex, all_text)
        key = f"antipattern:{ap_desc}"
        effective_weight = weight * 2.0 if found else weight * 0.25
        objectives[key] = {
            "passed": not found,
            "weight": effective_weight,
            "actual": "present" if found else "absent",
            "expected": "absent",
            "details": f"Anti-pattern regex for {primary_cap}",
        }
        if found:
            diagnostics.append(f"anti-pattern: {ap_desc}")

    # 5) Capability-specific positive signals (bonus credit)
    for pos_regex, pos_desc in CAPABILITY_POSITIVE.get(primary_cap, []):
        found = _has(pos_regex, all_text)
        key = f"positive:{pos_desc}"
        objectives[key] = {
            "passed": found,
            "weight": 0.5,
            "actual": "present" if found else "absent",
            "expected": "present",
            "details": f"Positive signal for {primary_cap}",
        }

    # 6) Cross-cutting anti-patterns that apply to every Oban worker output.
    # Same asymmetry: found = full weight penalty, absent = trivial credit.
    cross_cutting = [
        (ATOM_KEY_IN_PERFORM, "atom keys in perform/1 head (cross-cutting)", 1.5),
        (STRUCT_IN_ARGS, "struct stored in Oban args (cross-cutting)", 1.5),
        (DISCARD_RETURN, "deprecated {:discard, _} (cross-cutting)", 1.5),
    ]
    for ap_regex, ap_desc, weight in cross_cutting:
        found = _has(ap_regex, all_text)
        key = f"cross_antipattern:{ap_desc}"
        if key not in objectives and not any(
            ap_desc in k for k in objectives.keys()
        ):
            effective_weight = weight if found else weight * 0.15
            objectives[key] = {
                "passed": not found,
                "weight": effective_weight,
                "actual": "present" if found else "absent",
                "expected": "absent",
                "details": "Cross-cutting Oban iron-law check",
            }
            if found:
                diagnostics.append(f"cross-cutting anti-pattern: {ap_desc}")

    # Compute final score
    total_weight = sum(o["weight"] for o in objectives.values()) or 1.0
    passed_weight = sum(
        o["weight"] for o in objectives.values() if o["passed"]
    )
    score = passed_weight / total_weight

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
