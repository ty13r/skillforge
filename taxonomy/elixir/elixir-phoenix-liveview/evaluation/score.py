#!/usr/bin/env python3
"""SKLD-bench score.py for elixir-phoenix-liveview.

Static analyzer for Phoenix 1.7+ LiveView challenges. Checks for modern
idioms (~p sigil, <.link, :for/:if, <.form, streams, connected?) and
penalizes pre-1.7 anti-patterns (live_link, Routes.*, <%= for %>, DB-in-mount).
"""
import argparse
import json
import re
import sys
from pathlib import Path


# ---- Phoenix 1.7+ canonical patterns ---------------------------------------

VERIFIED_ROUTE = re.compile(r'~p"/', re.MULTILINE)
DOT_LINK = re.compile(r"<\.link\b", re.MULTILINE)
DOT_FORM = re.compile(r"<\.form\b", re.MULTILINE)
DOT_INPUT = re.compile(r"<\.input\b", re.MULTILINE)
COLON_FOR = re.compile(r":for=", re.MULTILINE)
COLON_IF = re.compile(r":if=", re.MULTILINE)
H_SIGIL = re.compile(r'~H"""')
TO_FORM = re.compile(r"to_form\s*\(")
STREAM_MACRO = re.compile(r"stream\s*\(\s*socket\s*,")
STREAM_INSERT = re.compile(r"stream_insert\s*\(")
STREAM_DELETE = re.compile(r"stream_delete\s*\(")
ATTR_DECL = re.compile(r"^\s*attr\s+:[a-z_]", re.MULTILINE)
SLOT_DECL = re.compile(r"^\s*slot\s+:[a-z_]", re.MULTILINE)
ASSIGN_NEW = re.compile(r"assign_new\s*\(")
CONNECTED_CHECK = re.compile(r"connected\?\s*\(\s*socket\s*\)")
PUSH_NAVIGATE = re.compile(r"push_navigate\s*\(")
PUSH_PATCH = re.compile(r"push_patch\s*\(")
PHX_CLICK = re.compile(r'phx-click="')
PHX_SUBMIT = re.compile(r'phx-submit="')
PHX_CHANGE = re.compile(r'phx-change="')
HANDLE_EVENT = re.compile(r'def\s+handle_event\s*\(\s*"')
HANDLE_INFO = re.compile(r"def\s+handle_info\s*\(")
HANDLE_PARAMS = re.compile(r"def\s+handle_params\s*\(")
MOUNT_DEF = re.compile(r"def\s+mount\s*\(")
PUBSUB_SUBSCRIBE = re.compile(r"Phoenix\.PubSub\.subscribe\s*\(")
PUBSUB_BROADCAST = re.compile(r"Phoenix\.PubSub\.broadcast\s*\(")
ON_MOUNT_HOOK = re.compile(r"on_mount\s*\{?\s*(?:[A-Z]|:)")
LIVE_SESSION = re.compile(r"live_session\s+:[a-z_]")

# ---- Pre-1.7 anti-patterns -------------------------------------------------

LIVE_LINK = re.compile(r"\blive_link\b", re.MULTILINE)
LIVE_PATCH_HELPER = re.compile(r"<%=\s*live_patch\b", re.MULTILINE)
LIVE_REDIRECT_HELPER = re.compile(r"<%=\s*live_redirect\b", re.MULTILINE)
ROUTES_HELPER = re.compile(r"Routes\.[a-z_]+_path\s*\(")
OLD_FOR_EEX = re.compile(r"<%=\s*for\s+", re.MULTILINE)
OLD_IF_EEX = re.compile(r"<%=\s*if\s+", re.MULTILINE)
STRING_INTERP_ROUTE = re.compile(r'to:\s*"/\w+/#\{')

# DB queries in mount (the named iron law)
REPO_CALL_IN_MOUNT = re.compile(
    r"def\s+mount\s*\([^)]*\)[^\n]*\n(?:\s*[^\n]*\n){0,10}?\s*(?:Repo|MyApp\.Repo)\.(?:all|one|get|get_by|insert|update|delete|preload)",
    re.MULTILINE,
)

# assign_new used where a fresh value is required
ASSIGN_WITHOUT_CONNECTED_CHECK = re.compile(
    r"Phoenix\.PubSub\.subscribe[^\n]*\n(?!.*connected\?)", re.MULTILINE
)


# ---- Capability-specific anti-patterns -------------------------------------

CAPABILITY_ANTIPATTERNS = {
    "heex-and-verified-routes": [
        (LIVE_LINK, "live_link (pre-1.7 helper)", 0.7),
        (LIVE_PATCH_HELPER, "<%= live_patch %> (pre-1.7 helper)", 0.6),
        (ROUTES_HELPER, "Routes.*_path helper (replaced by ~p)", 0.8),
        (OLD_FOR_EEX, "<%= for ... %> (replaced by :for)", 0.5),
        (OLD_IF_EEX, "<%= if ... %> (replaced by :if)", 0.4),
    ],
    "function-components-and-slots": [
        # Absence is detected via positive signal
    ],
    "live-components-stateful": [
        # Absence is detected via positive signal
    ],
    "form-handling": [
        (
            re.compile(r"@changeset\s+%>.*\b<%=\s*f\s*=\s*form_for"),
            "old form_for helper (pre-1.7)", 0.8,
        ),
    ],
    "streams-and-collections": [
        # Absence of stream/3 detected via positive signal
    ],
    "mount-and-lifecycle": [
        (REPO_CALL_IN_MOUNT, "Repo call inside mount/3 (runs twice!)", 0.9),
    ],
    "event-handlers-and-handle-info": [
        # absence detected
    ],
    "pubsub-and-realtime": [
        (ASSIGN_WITHOUT_CONNECTED_CHECK, "PubSub.subscribe without connected? check", 0.8),
    ],
    "navigation-patterns": [
        (LIVE_PATCH_HELPER, "live_patch (replaced by push_patch)", 0.6),
        (LIVE_REDIRECT_HELPER, "live_redirect (replaced by push_navigate)", 0.6),
    ],
    "auth-and-authz": [
        # Positive signals handle this
    ],
    "anti-patterns-catalog": [
        (REPO_CALL_IN_MOUNT, "DB in mount anti-pattern", 0.9),
        (LIVE_LINK, "live_link anti-pattern", 0.5),
        (ROUTES_HELPER, "Routes.* anti-pattern", 0.6),
    ],
    "architectural-stance": [
        (REPO_CALL_IN_MOUNT, "DB in mount (structural anti-pattern)", 0.7),
        (LIVE_LINK, "live_link (structural anti-pattern)", 0.4),
    ],
}


# ---- Capability-specific positive signals ----------------------------------

CAPABILITY_POSITIVE = {
    "architectural-stance": [
        (H_SIGIL, "~H sigil (modern template style)"),
        (DOT_LINK, "<.link component"),
    ],
    "heex-and-verified-routes": [
        (VERIFIED_ROUTE, "~p verified route sigil"),
        (DOT_LINK, "<.link component"),
        (COLON_FOR, ":for attribute"),
        (COLON_IF, ":if attribute"),
    ],
    "function-components-and-slots": [
        (ATTR_DECL, "attr declaration"),
        (SLOT_DECL, "slot declaration"),
    ],
    "live-components-stateful": [
        (re.compile(r"use\s+Phoenix\.LiveComponent"), "Phoenix.LiveComponent used"),
    ],
    "form-handling": [
        (TO_FORM, "to_form/2 used"),
        (DOT_FORM, "<.form> component"),
        (DOT_INPUT, "<.input> component"),
        (PHX_CHANGE, "phx-change binding"),
    ],
    "streams-and-collections": [
        (STREAM_MACRO, "stream/3 used"),
        (STREAM_INSERT, "stream_insert used"),
    ],
    "mount-and-lifecycle": [
        (CONNECTED_CHECK, "connected?(socket) guard"),
        (HANDLE_PARAMS, "handle_params/3 defined"),
    ],
    "event-handlers-and-handle-info": [
        (HANDLE_EVENT, "handle_event defined"),
        (HANDLE_INFO, "handle_info defined"),
    ],
    "pubsub-and-realtime": [
        (PUBSUB_SUBSCRIBE, "PubSub.subscribe"),
        (CONNECTED_CHECK, "connected? check before subscribe"),
    ],
    "navigation-patterns": [
        (PUSH_NAVIGATE, "push_navigate used"),
        (PUSH_PATCH, "push_patch used"),
        (DOT_LINK, "<.link with navigate={...}"),
    ],
    "auth-and-authz": [
        (ON_MOUNT_HOOK, "on_mount hook for auth"),
        (LIVE_SESSION, "live_session boundary"),
    ],
    "anti-patterns-catalog": [
        (CONNECTED_CHECK, "connected? check"),
        (VERIFIED_ROUTE, "~p verified route"),
    ],
}


# ---- Cross-cutting anti-patterns ------------------------------------------

CROSS_CUTTING_ANTIPATTERNS = [
    (LIVE_LINK, "cross-cutting live_link", 0.8),
    (ROUTES_HELPER, "cross-cutting Routes.*_path helper", 0.8),
    (OLD_FOR_EEX, "cross-cutting <%= for %>", 0.5),
    (OLD_IF_EEX, "cross-cutting <%= if %>", 0.4),
    (LIVE_PATCH_HELPER, "cross-cutting live_patch", 0.5),
    (LIVE_REDIRECT_HELPER, "cross-cutting live_redirect", 0.5),
    (REPO_CALL_IN_MOUNT, "cross-cutting DB in mount", 1.0),
]


def _has(pattern: re.Pattern, text: str) -> bool:
    return bool(pattern.search(text))


def _pipe_aware_contains(pat: str, text: str) -> bool:
    """Check if a pattern is present, accounting for Elixir pipe operator.

    If pat looks like `fn(arg1, arg2` (a function call with first arg),
    also check for `|> fn(arg2` (pipe strips first arg).

    Also handles variable-vs-literal: `limit: -50` also matches
    `limit: -@page_size` or `limit: -@limit`.
    """
    if pat in text:
        return True

    # Pipe-operator variant: fn(first_arg, rest → |> fn(rest
    # Match patterns like: `stream(socket, :posts` → `|> stream(:posts`
    pipe_match = re.match(r'^(\w+)\(\s*\w+\s*,\s*(.+)', pat)
    if pipe_match:
        fn_name = pipe_match.group(1)
        rest = pipe_match.group(2)
        pipe_pat = f"|> {fn_name}({rest}"
        if pipe_pat in text:
            return True
        # Also try with preceding whitespace flexibility
        if re.search(rf'\|>\s*{re.escape(fn_name)}\({re.escape(rest)}', text):
            return True

    # Variable-vs-literal: `limit: -50` → also match `limit: -@\w+`
    literal_match = re.match(r'^(.*:\s*-?)(\d+)(.*)$', pat)
    if literal_match:
        prefix = re.escape(literal_match.group(1))
        suffix = re.escape(literal_match.group(3))
        var_pat = rf'{prefix}@?\w+{suffix}'
        if re.search(var_pat, text):
            return True

    return False


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

    for pat in must_contain:
        present = _pipe_aware_contains(pat, all_text)
        objectives[f"contains:{pat}"] = {
            "passed": present, "weight": 2.5,
            "actual": "present" if present else "absent",
            "expected": "present",
            "details": f"Required substring: {pat!r}",
        }

    for pat in must_not_contain:
        absent = pat not in all_text
        weight = 2.5 if not absent else 0.25
        objectives[f"absent:{pat}"] = {
            "passed": absent, "weight": weight,
            "actual": "absent" if absent else "present",
            "expected": "absent",
            "details": f"Forbidden substring: {pat!r}",
        }

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

    for pos_regex, pos_desc in CAPABILITY_POSITIVE.get(primary_cap, []):
        found = _has(pos_regex, all_text)
        objectives[f"positive:{pos_desc}"] = {
            "passed": found, "weight": 0.6,
            "actual": "present" if found else "absent",
            "expected": "present",
            "details": f"Positive signal for {primary_cap}",
        }

    for ap_regex, ap_desc, weight in CROSS_CUTTING_ANTIPATTERNS:
        found = _has(ap_regex, all_text)
        key = f"cross:{ap_desc}"
        # Downweighted: only contribute when found (penalty), zero when
        # absent to prevent inflating the denominator with free points.
        effective_weight = weight * 0.5 if found else 0.0
        objectives[key] = {
            "passed": not found, "weight": effective_weight,
            "actual": "present" if found else "absent",
            "expected": "absent",
            "details": "Cross-cutting Phoenix 1.7 iron-law check",
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
