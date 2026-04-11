#!/usr/bin/env python3
"""SKLD-bench score.py for elixir-ecto-sandbox-test.

Static analyzer for Ecto sandbox test isolation challenges. Detects correct
patterns for test-isolation setup, connection ownership transfer, async-
safety rules, and anti-patterns like :auto mode, Process.sleep, seeding
dev DB, and raw Oban.drain_queue in sandbox contexts.
"""
import argparse
import json
import re
import sys
from pathlib import Path


# ---- Canonical sandbox patterns --------------------------------------------

# Canonical DataCase shape
DATA_CASE_TEMPLATE = re.compile(r"use\s+ExUnit\.CaseTemplate", re.MULTILINE)
START_OWNER = re.compile(r"Ecto\.Adapters\.SQL\.Sandbox\.start_owner!\s*\(")
STOP_OWNER = re.compile(r"Ecto\.Adapters\.SQL\.Sandbox\.stop_owner")
SHARED_NOT_ASYNC = re.compile(r"shared:\s*not\s+tags\[:async\]")
ON_EXIT = re.compile(r"on_exit\s*\(")
SANDBOX_CHECKOUT = re.compile(r"Ecto\.Adapters\.SQL\.Sandbox\.checkout\s*\(")
SANDBOX_ALLOW = re.compile(r"Ecto\.Adapters\.SQL\.Sandbox\.allow\s*\(")
SANDBOX_MODE_MANUAL = re.compile(r"Ecto\.Adapters\.SQL\.Sandbox\.mode\s*\([^,]+,\s*:manual\)")
SANDBOX_MODE_AUTO = re.compile(r"Ecto\.Adapters\.SQL\.Sandbox\.mode\s*\([^,]+,\s*:auto\)")
SANDBOX_MODE_SHARED = re.compile(r"Ecto\.Adapters\.SQL\.Sandbox\.mode\s*\([^,]+,\s*\{:shared")

ASYNC_TRUE = re.compile(r"async:\s*true", re.MULTILINE)
ASYNC_FALSE = re.compile(r"async:\s*false", re.MULTILINE)

# Phoenix / LiveView sandbox plug
PHOENIX_SANDBOX_PLUG = re.compile(r"Phoenix\.Ecto\.SQL\.Sandbox")
SANDBOX_METADATA_HEADER = re.compile(r'"user-agent".*sandbox|Sandbox\.metadata_for')

# Oban testing patterns
OBAN_TESTING = re.compile(r"use\s+Oban\.Testing", re.MULTILINE)
PERFORM_JOB = re.compile(r"perform_job\s*\(")
OBAN_DRAIN_QUEUE = re.compile(r"Oban\.drain_queue\s*\(")
OBAN_INSERT_EMPTY = re.compile(r"Oban\.insert\s*\(\s*\)")

# Channel testing
CHANNEL_TEST_CASE = re.compile(r"use\s+Phoenix\.ChannelCase")

# Task / spawned processes
TASK_ASYNC = re.compile(r"Task\.(?:async|Supervisor\.async_nolink)")
SPAWN_LINK = re.compile(r"spawn(?:_link)?\s*\(")

# Anti-patterns: flaky workarounds
PROCESS_SLEEP = re.compile(r"Process\.sleep\s*\(")
REPO_INSERT_NO_TXN = re.compile(
    r"Repo\.insert!\s*\([^)]*\)\s*(?:#[^\n]*)?\n(?!.*(?:checkout|allow|start_owner))",
    re.MULTILINE,
)

# Tidewave dev-vs-test confusion
TIDEWAVE_DEV = re.compile(r"Tidewave|:dev\s*=>\s*Repo|use\s+Mix\.Config", re.MULTILINE)
TIDEWAVE_SEEDING_FIX = re.compile(
    r"(?:seed_test_db|insert_for_test|# Seed test data here to force)",
    re.MULTILINE,
)

# Shared mode usage
SHARED_MODE_TUPLE = re.compile(r"\{:shared,\s*self\(\)\}")

# Flaky test diagnosis signals
REFUTE_ENQUEUED = re.compile(r"refute_enqueued\s*\(")
ASSERT_ENQUEUED = re.compile(r"assert_enqueued\s*\(")
EVENTUALLY = re.compile(r"eventually|wait_for|poll_until", re.IGNORECASE)


# ---- Capability-specific anti-patterns -------------------------------------

CAPABILITY_ANTIPATTERNS = {
    "test-isolation-philosophy": [
        (SANDBOX_MODE_AUTO, "Sandbox.mode(:auto) in test code (breaks isolation)", 0.8),
        (ASYNC_FALSE, "async: false as a workaround (hides ownership bug)", 0.4),
    ],
    "sandbox-checkout-and-modes": [
        (SANDBOX_MODE_AUTO, "Sandbox.mode(:auto) bypasses per-test transaction", 0.9),
    ],
    "async-test-safety-rules": [
        (ASYNC_FALSE, "async: false disables per-test isolation", 0.5),
        (SANDBOX_MODE_AUTO, "Sandbox.mode(:auto) in async test is broken", 0.8),
    ],
    "allow-pattern-for-spawned-processes": [
        (
            re.compile(r"Task\.async\s*\([^)]*\)(?![^)]*Sandbox\.allow)", re.MULTILINE),
            "Task.async without preceding Sandbox.allow/3",
            0.6,
        ),
    ],
    "connection-ownership-transfer": [
        (PROCESS_SLEEP, "Process.sleep to 'wait for' connection transfer", 0.5),
    ],
    "liveview-sandbox-integration": [
        # Must have the Phoenix.Ecto.SQL.Sandbox plug — detected via positive signal
    ],
    "channels-sandbox-integration": [
        # Must call Sandbox.allow on the channel pid — detected via positive signal
    ],
    "oban-sandbox-integration": [
        (OBAN_DRAIN_QUEUE, "Oban.drain_queue in sandbox test (won't see uncommitted data)", 0.9),
    ],
    "tidewave-dev-vs-test-trap": [
        (TIDEWAVE_SEEDING_FIX, "Seeding test DB to force passing tests (masks sandbox bug)", 0.8),
    ],
    "shared-mode-fallback": [
        (SANDBOX_MODE_AUTO, ":auto mode used instead of proper :shared fallback", 0.7),
    ],
    "flaky-test-diagnosis": [
        (PROCESS_SLEEP, "Process.sleep used to paper over flaky test", 0.7),
    ],
}

# ---- Capability-specific positive signals ----------------------------------

CAPABILITY_POSITIVE = {
    "test-isolation-philosophy": [
        (DATA_CASE_TEMPLATE, "CaseTemplate used (proper scoping)"),
        (SHARED_NOT_ASYNC, "canonical shared: not tags[:async] pattern"),
        (START_OWNER, "Sandbox.start_owner! present"),
        (ON_EXIT, "on_exit cleanup registered"),
    ],
    "sandbox-checkout-and-modes": [
        (START_OWNER, "start_owner!/2 present"),
        (STOP_OWNER, "stop_owner present"),
        (SANDBOX_MODE_MANUAL, ":manual mode configured"),
    ],
    "async-test-safety-rules": [
        (ASYNC_TRUE, "async: true present"),
        (SHARED_NOT_ASYNC, "shared: not tags[:async] dispatcher"),
    ],
    "allow-pattern-for-spawned-processes": [
        (SANDBOX_ALLOW, "Sandbox.allow/3 called for spawned process"),
    ],
    "connection-ownership-transfer": [
        (SANDBOX_ALLOW, "Sandbox.allow/3 transfer"),
        (SANDBOX_CHECKOUT, "Sandbox.checkout present"),
    ],
    "liveview-sandbox-integration": [
        (PHOENIX_SANDBOX_PLUG, "Phoenix.Ecto.SQL.Sandbox plug"),
        (SANDBOX_METADATA_HEADER, "sandbox metadata header usage"),
    ],
    "channels-sandbox-integration": [
        (CHANNEL_TEST_CASE, "Phoenix.ChannelCase present"),
        (SANDBOX_ALLOW, "Sandbox.allow on channel process"),
    ],
    "oban-sandbox-integration": [
        (OBAN_TESTING, "use Oban.Testing"),
        (PERFORM_JOB, "perform_job/3 used (not drain_queue)"),
    ],
    "tidewave-dev-vs-test-trap": [
        (START_OWNER, "Explicit sandbox ownership instead of dev DB reliance"),
    ],
    "shared-mode-fallback": [
        (SHARED_MODE_TUPLE, "{:shared, self()} mode tuple"),
    ],
    "flaky-test-diagnosis": [
        (SANDBOX_ALLOW, "Sandbox.allow (root cause fix, not sleep)"),
        (REFUTE_ENQUEUED, "refute_enqueued used for negative assertions"),
        (ASSERT_ENQUEUED, "assert_enqueued used"),
    ],
}


# ---- Cross-cutting anti-patterns ------------------------------------------

CROSS_CUTTING_ANTIPATTERNS = [
    (SANDBOX_MODE_AUTO, "cross-cutting :auto mode in test", 1.0),
    (PROCESS_SLEEP, "cross-cutting Process.sleep workaround", 0.8),
    (OBAN_DRAIN_QUEUE, "cross-cutting Oban.drain_queue in sandbox", 0.7),
    (TIDEWAVE_SEEDING_FIX, "cross-cutting test DB seeding to force pass", 0.9),
]


def _has(pattern: re.Pattern, text: str) -> bool:
    return bool(pattern.search(text))


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
                "passed": False,
                "weight": 1.5,
                "actual": "absent",
                "expected": "present",
                "details": f"Required substring: {pat!r}",
            }
        for pat in must_not_contain:
            objectives[f"absent:{pat}"] = {
                "passed": True,
                "weight": 0.0,
                "actual": "absent",
                "expected": "absent",
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

    for pat in must_contain:
        present = pat in all_text
        objectives[f"contains:{pat}"] = {
            "passed": present,
            "weight": 2.5,
            "actual": "present" if present else "absent",
            "expected": "present",
            "details": f"Required substring: {pat!r}",
        }

    for pat in must_not_contain:
        absent = pat not in all_text
        weight = 2.5 if not absent else 0.25
        objectives[f"absent:{pat}"] = {
            "passed": absent,
            "weight": weight,
            "actual": "absent" if absent else "present",
            "expected": "absent",
            "details": f"Forbidden substring: {pat!r}",
        }

    for ap_regex, ap_desc, weight in CAPABILITY_ANTIPATTERNS.get(primary_cap, []):
        found = _has(ap_regex, all_text)
        effective_weight = weight * 2.0 if found else weight * 0.25
        objectives[f"antipattern:{ap_desc}"] = {
            "passed": not found,
            "weight": effective_weight,
            "actual": "present" if found else "absent",
            "expected": "absent",
            "details": f"Anti-pattern for {primary_cap}",
        }
        if found:
            diagnostics.append(f"anti-pattern: {ap_desc}")

    for pos_regex, pos_desc in CAPABILITY_POSITIVE.get(primary_cap, []):
        found = _has(pos_regex, all_text)
        objectives[f"positive:{pos_desc}"] = {
            "passed": found,
            "weight": 0.6,
            "actual": "present" if found else "absent",
            "expected": "present",
            "details": f"Positive signal for {primary_cap}",
        }

    for ap_regex, ap_desc, weight in CROSS_CUTTING_ANTIPATTERNS:
        found = _has(ap_regex, all_text)
        key = f"cross:{ap_desc}"
        effective_weight = weight if found else weight * 0.15
        objectives[key] = {
            "passed": not found,
            "weight": effective_weight,
            "actual": "present" if found else "absent",
            "expected": "absent",
            "details": "Cross-cutting sandbox iron-law check",
        }
        if found:
            diagnostics.append(f"cross-cutting: {ap_desc}")

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
