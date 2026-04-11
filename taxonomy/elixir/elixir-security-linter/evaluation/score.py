#!/usr/bin/env python3
"""SKLD-bench score.py for elixir-security-linter.

SAST-style scorer for Elixir/Phoenix security challenges. Each challenge
presents vulnerable code and asks for a fix. We check that the fix:
1. Removes the specific vulnerability (via must_not_contain + capability-specific antipattern regex)
2. Preserves functional structure (via must_contain)
3. Doesn't introduce new vulnerabilities (via cross-cutting anti-pattern checks)
4. Uses the safer alternative (via capability-specific positive signals)
"""
import argparse
import json
import re
import sys
from pathlib import Path


# ---- Elixir security anti-pattern regexes ---------------------------------

# Atom exhaustion: String.to_atom / List.to_atom / :erlang.binary_to_atom on user input
STRING_TO_ATOM = re.compile(r"String\.to_atom\s*\(", re.MULTILINE)
LIST_TO_ATOM = re.compile(r"List\.to_atom\s*\(", re.MULTILINE)
BINARY_TO_ATOM = re.compile(r":erlang\.binary_to_atom\s*\(", re.MULTILINE)
ATOM_INTERPOLATION = re.compile(r":\"[^\"]*#\{[^}]*\}", re.MULTILINE)
STRING_TO_EXISTING_ATOM = re.compile(r"String\.to_existing_atom\s*\(", re.MULTILINE)

# SQL injection via fragment/1 with string interpolation
FRAGMENT_WITH_INTERP = re.compile(
    r'fragment\s*\(\s*"[^"]*#\{[^}]*\}[^"]*"', re.MULTILINE
)
PIN_OPERATOR = re.compile(r"[\s(,]\^[a-zA-Z_][a-zA-Z0-9_]*", re.MULTILINE)

# XSS via raw/1 on user-controlled content
RAW_WITH_USER_CONTENT = re.compile(
    r"raw\s*\(\s*@[a-z_][a-z0-9_]*", re.MULTILINE
)
PHOENIX_SANITIZE = re.compile(
    r"(Phoenix\.HTML\.html_escape|HtmlSanitizeEx\.)"
)

# Open redirect: redirect(to: user_controlled) without URL validation
REDIRECT_USER_PARAM = re.compile(
    r'redirect\s*\(\s*(?:to|external):\s*(?:params\[|conn\.params\[|@return_to|Map\.get\(params)',
    re.MULTILINE,
)
URL_VALIDATION = re.compile(
    r'(URI\.parse|String\.starts_with\?\s*\([^,]+,\s*"/"|String\.match\?\s*\(.*~r)',
    re.MULTILINE,
)

# Timing attacks: == on tokens/secrets/hashes
TIMING_TOKEN_EQ = re.compile(
    r"\b(?:token|secret|password_hash|api_key|hash|signature|hmac|otp)\s*==",
    re.MULTILINE | re.IGNORECASE,
)
TIMING_EQ_TOKEN = re.compile(
    r"==\s*\b(?:token|secret|password_hash|api_key|hash|signature|hmac|otp)\b",
    re.MULTILINE | re.IGNORECASE,
)
SECURE_COMPARE = re.compile(
    r"(Plug\.Crypto\.secure_compare|:crypto\.hash_equals)\s*\("
)

# LiveView handle_event missing authz
HANDLE_EVENT_DEF = re.compile(
    r'def\s+handle_event\s*\(\s*"[^"]*"\s*,', re.MULTILINE
)
OWNERSHIP_CHECK = re.compile(
    r"(?:owner_id|user_id|author_id|account_id)\s*(?:==|===)\s*"
    r"(?:socket\.assigns\.|@current_user|current_user|assigns\.current_user)",
    re.MULTILINE,
)
WITH_OWNERSHIP_GUARD = re.compile(
    r"with\s+(?:.*?owner|.*?authorize|.*?:ok\s*<-\s*authorize)",
    re.MULTILINE,
)

# CSRF / secure headers
PUT_SECURE_HEADERS = re.compile(r"put_secure_browser_headers")
PROTECT_FROM_FORGERY = re.compile(r"protect_from_forgery")
CSP_HEADER = re.compile(r'"content-security-policy"', re.IGNORECASE)
HSTS_HEADER = re.compile(r'"strict-transport-security"', re.IGNORECASE)
X_FRAME_HEADER = re.compile(r'"x-frame-options"', re.IGNORECASE)
X_CONTENT_TYPE = re.compile(r'"x-content-type-options"', re.IGNORECASE)

# Mass assignment: cast/3 with :role / :admin / :is_admin / :permissions
CAST_WITH_PROTECTED_FIELD = re.compile(
    r"cast\s*\([^,]+,[^,]+,\s*\[[^\]]*:(?:role|is_admin|admin|permissions|privileges)\b",
    re.MULTILINE,
)
CAST_WIDE_OPEN = re.compile(
    r"cast\s*\([^,]+,[^,]+,\s*(?:params|attrs)\s*\)", re.MULTILINE
)

# Password hashing: weak hashes
MD5_HASH = re.compile(
    r":crypto\.hash\s*\(\s*:md5", re.MULTILINE
)
SHA1_HASH = re.compile(
    r":crypto\.hash\s*\(\s*:sha\b(?!256|384|512)", re.MULTILINE
)
PLAINTEXT_PASSWORD = re.compile(
    r'(?:password|password_hash|hashed_password)\s*:\s*(?:params\[|attrs\[|"[^"]+")',
    re.MULTILINE,
)
BCRYPT = re.compile(r"Bcrypt\.(?:hash_pwd_salt|hashpwsalt|verify_pass|check_pass)")
ARGON2 = re.compile(r"Argon2\.(?:hash_pwd_salt|verify_pass|check_pass)")
PBKDF2 = re.compile(r"Pbkdf2\.(?:hash_pwd_salt|verify_pass|check_pass)")

# Session / cookie security
COOKIE_SECURE_TRUE = re.compile(r"secure:\s*true", re.MULTILINE)
COOKIE_HTTPONLY_TRUE = re.compile(r"http_only:\s*true", re.MULTILINE)
COOKIE_SAMESITE = re.compile(r'same_site:\s*"(?:Strict|Lax)"', re.MULTILINE)
SIGNING_SALT = re.compile(r"signing_salt|encryption_salt", re.MULTILINE)

# Plug middleware chain
PUT_RESP_HEADER = re.compile(r"put_resp_header\s*\(")

# Secrets in config
HARDCODED_SECRET = re.compile(
    r'(?:secret_key_base|api_key|aws_secret|database_url|access_token)\s*'
    r'(?::|=>)\s*"(?!\$|System)[a-zA-Z0-9+/=_\-]{20,}"',
    re.MULTILINE,
)
SYSTEM_FETCH_ENV = re.compile(r"System\.fetch_env!\s*\(\s*\"", re.MULTILINE)
SYSTEM_GET_ENV_WITH_FALLBACK = re.compile(
    r'System\.get_env\s*\(\s*"[^"]+"\s*,\s*"[^"]+"', re.MULTILINE
)


# ---- Capability-specific anti-pattern penalties ----------------------------

CAPABILITY_ANTIPATTERNS = {
    "atom-exhaustion": [
        (STRING_TO_ATOM, "String.to_atom on user input (atom exhaustion)", 0.9),
        (LIST_TO_ATOM, "List.to_atom on user input", 0.5),
        (BINARY_TO_ATOM, ":erlang.binary_to_atom", 0.5),
        (ATOM_INTERPOLATION, "atom interpolation sigil :\"...#{}\"", 0.4),
    ],
    "ecto-fragment-injection": [
        (FRAGMENT_WITH_INTERP, "fragment/1 with string interpolation (SQLi)", 1.0),
    ],
    "raw-xss-prevention": [
        (RAW_WITH_USER_CONTENT, "raw/1 on user-controlled assign (XSS)", 0.9),
    ],
    "open-redirect-protection": [
        (REDIRECT_USER_PARAM, "redirect to user-controlled param without validation", 0.8),
    ],
    "timing-attack-comparisons": [
        (TIMING_TOKEN_EQ, "== on token/secret variable (timing attack)", 0.8),
        (TIMING_EQ_TOKEN, "== with token/secret on RHS (timing attack)", 0.8),
    ],
    "liveview-handle-event-authz": [
        # Absence of an ownership check in a handle_event body is the anti-pattern;
        # detected via positive signals rather than direct regex.
    ],
    "mass-assignment-in-changesets": [
        (CAST_WITH_PROTECTED_FIELD, "cast allowlist includes :role/:admin/:permissions", 0.9),
        (CAST_WIDE_OPEN, "cast with wide-open params/attrs", 0.5),
    ],
    "password-hashing-choice": [
        (MD5_HASH, ":crypto.hash(:md5, ...) — broken hash", 1.0),
        (SHA1_HASH, ":crypto.hash(:sha, ...) — broken hash", 0.8),
        (PLAINTEXT_PASSWORD, "plaintext password assignment", 0.9),
    ],
    "secrets-in-config": [
        (HARDCODED_SECRET, "hardcoded secret in config value", 0.7),
    ],
    "security-scan-philosophy": [
        (STRING_TO_ATOM, "String.to_atom (cross-cutting foundation check)", 0.5),
        (FRAGMENT_WITH_INTERP, "fragment interpolation (cross-cutting foundation check)", 0.5),
        (MD5_HASH, "md5 hash (cross-cutting foundation check)", 0.5),
    ],
}


# ---- Capability-specific positive signals (bonus credit) ------------------

CAPABILITY_POSITIVE = {
    "atom-exhaustion": [
        (STRING_TO_EXISTING_ATOM, "String.to_existing_atom (safer bounded variant)"),
        (re.compile(r"@(?:allowed|permitted|valid)_\w+\s+%\{"), "allowlist module attribute"),
    ],
    "ecto-fragment-injection": [
        (PIN_OPERATOR, "^ pin operator present"),
    ],
    "raw-xss-prevention": [
        (PHOENIX_SANITIZE, "Phoenix.HTML.html_escape or sanitizer used"),
    ],
    "open-redirect-protection": [
        (URL_VALIDATION, "URL validation before redirect"),
    ],
    "timing-attack-comparisons": [
        (SECURE_COMPARE, "Plug.Crypto.secure_compare used"),
    ],
    "liveview-handle-event-authz": [
        (OWNERSHIP_CHECK, "ownership check in handle_event"),
        (WITH_OWNERSHIP_GUARD, "with-chain authorize guard"),
    ],
    "csrf-and-secure-headers": [
        (PUT_SECURE_HEADERS, "put_secure_browser_headers plug"),
        (PROTECT_FROM_FORGERY, "protect_from_forgery plug"),
        (CSP_HEADER, "Content-Security-Policy header"),
    ],
    "plug-security-middleware-chain": [
        (CSP_HEADER, "CSP header configured"),
        (HSTS_HEADER, "HSTS header configured"),
        (X_FRAME_HEADER, "X-Frame-Options configured"),
        (X_CONTENT_TYPE, "X-Content-Type-Options configured"),
        (PUT_RESP_HEADER, "put_resp_header used for custom headers"),
    ],
    "password-hashing-choice": [
        (BCRYPT, "Bcrypt used"),
        (ARGON2, "Argon2 used"),
        (PBKDF2, "Pbkdf2 used"),
    ],
    "session-and-cookie-security": [
        (COOKIE_SECURE_TRUE, "secure: true cookie flag"),
        (COOKIE_HTTPONLY_TRUE, "http_only: true cookie flag"),
        (COOKIE_SAMESITE, "same_site: Strict/Lax cookie flag"),
        (SIGNING_SALT, "signing/encryption salt configured"),
    ],
    "secrets-in-config": [
        (SYSTEM_FETCH_ENV, "System.fetch_env! used for secret loading"),
    ],
    "mass-assignment-in-changesets": [
        (
            re.compile(r"cast\s*\([^,]+,[^,]+,\s*\[\s*:[a-z_][a-z0-9_]*"),
            "cast with explicit allowlist",
        ),
    ],
}


# ---- Cross-cutting anti-patterns (apply to every output) ------------------

CROSS_CUTTING_ANTIPATTERNS = [
    (STRING_TO_ATOM, "cross-cutting atom exhaustion", 1.2),
    (FRAGMENT_WITH_INTERP, "cross-cutting SQL injection via fragment", 1.2),
    (MD5_HASH, "cross-cutting broken crypto (md5)", 1.0),
    (SHA1_HASH, "cross-cutting broken crypto (sha1)", 0.8),
    (RAW_WITH_USER_CONTENT, "cross-cutting XSS via raw/1", 1.0),
    (ATOM_INTERPOLATION, "cross-cutting atom interpolation sigil", 0.5),
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

    # 1) File presence
    for rel, content in file_contents.items():
        objectives[f"file_present:{rel}"] = {
            "passed": content is not None,
            "weight": 1.0,
            "actual": "present" if content is not None else "missing",
            "expected": "present",
            "details": f"Expected output file {rel}",
        }

    present_contents = {k: v for k, v in file_contents.items() if v}

    # Empty output path — everything fails, must_not_contain gets zero credit
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

    # 2) must_contain (structural requirements)
    for pat in must_contain:
        present = pat in all_text
        objectives[f"contains:{pat}"] = {
            "passed": present,
            "weight": 2.5,
            "actual": "present" if present else "absent",
            "expected": "present",
            "details": f"Required substring: {pat!r}",
        }

    # 3) must_not_contain (challenge-declared anti-patterns)
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

    # 4) Capability-specific anti-pattern regex
    for ap_regex, ap_desc, weight in CAPABILITY_ANTIPATTERNS.get(primary_cap, []):
        found = _has(ap_regex, all_text)
        effective_weight = weight * 2.0 if found else weight * 0.25
        objectives[f"antipattern:{ap_desc}"] = {
            "passed": not found,
            "weight": effective_weight,
            "actual": "present" if found else "absent",
            "expected": "absent",
            "details": f"Anti-pattern regex for {primary_cap}",
        }
        if found:
            diagnostics.append(f"anti-pattern: {ap_desc}")

    # 5) Capability-specific positive signals
    for pos_regex, pos_desc in CAPABILITY_POSITIVE.get(primary_cap, []):
        found = _has(pos_regex, all_text)
        objectives[f"positive:{pos_desc}"] = {
            "passed": found,
            "weight": 0.5,
            "actual": "present" if found else "absent",
            "expected": "present",
            "details": f"Positive signal for {primary_cap}",
        }

    # 6) Cross-cutting anti-patterns
    for ap_regex, ap_desc, weight in CROSS_CUTTING_ANTIPATTERNS:
        found = _has(ap_regex, all_text)
        key = f"cross:{ap_desc}"
        # Avoid double-counting if the capability already covers this pattern
        if any(ap_desc.split("cross-cutting ")[-1] in k for k in objectives.keys() if k.startswith("antipattern:")):
            continue
        effective_weight = weight if found else weight * 0.15
        objectives[key] = {
            "passed": not found,
            "weight": effective_weight,
            "actual": "present" if found else "absent",
            "expected": "absent",
            "details": "Cross-cutting security iron-law check",
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
