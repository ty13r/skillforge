#!/usr/bin/env python3
"""Focused description validator and improver for skill descriptions.

Usage: python check_description.py "your description text here"
"""

import argparse
import re
import sys


def analyze(description: str) -> tuple[list[dict], list[str]]:
    """Analyze a description and return (checks, suggestions)."""
    checks: list[dict] = []
    suggestions: list[str] = []
    desc_len = len(description)

    # Length check
    if desc_len > 1024:
        checks.append({"name": "length", "status": "fail",
                        "detail": f"{desc_len} chars (exceeds 1024 max)"})
    elif desc_len > 250:
        checks.append({"name": "length", "status": "warn",
                        "detail": f"{desc_len} chars (over 250 recommended)"})
    else:
        checks.append({"name": "length", "status": "pass",
                        "detail": f"{desc_len} chars, under 250"})

    desc_lower = description.lower()

    # "Use when" pattern
    if "use when" in desc_lower:
        checks.append({"name": "use_when", "status": "pass",
                        "detail": 'Has "Use when" trigger language'})
    else:
        checks.append({"name": "use_when", "status": "fail",
                        "detail": 'Missing "Use when" trigger language'})
        suggestions.append('Add "Use when ..." to specify activation triggers')

    # "NOT for" exclusion
    if "not for" in desc_lower:
        checks.append({"name": "not_for", "status": "pass",
                        "detail": 'Has "NOT for" exclusions'})
    else:
        checks.append({"name": "not_for", "status": "fail",
                        "detail": 'Missing "NOT for" exclusions'})
        suggestions.append('Consider adding: "NOT for X, Y, or Z" to prevent false activations')

    # "even if" pushy language
    if "even if" in desc_lower:
        checks.append({"name": "even_if", "status": "pass",
                        "detail": 'Has "even if" pushy language'})
    else:
        checks.append({"name": "even_if", "status": "fail",
                        "detail": 'Missing "even if" pushy language'})
        suggestions.append(
            'Consider adding: "even if they don\'t explicitly ask for {skill-name}" '
            "for better trigger recall"
        )

    # Front-loading: check if key capability words are in the first 100 chars
    first_100 = description[:100].lower()
    capability_words = re.findall(r"[a-z]{4,}", desc_lower)
    if capability_words:
        first_100_words = set(re.findall(r"[a-z]{4,}", first_100))
        overlap = first_100_words & set(capability_words)
        ratio = len(overlap) / len(set(capability_words)) if capability_words else 0
        if ratio >= 0.3 or len(first_100_words) >= 3:
            checks.append({"name": "front_loading", "status": "pass",
                            "detail": "Key capability words appear early"})
        else:
            checks.append({"name": "front_loading", "status": "warn",
                            "detail": "Key capability words may not be front-loaded"})
            suggestions.append(
                "Front-load the description: put the most important capability words "
                "in the first 100 characters"
            )
    else:
        checks.append({"name": "front_loading", "status": "warn",
                        "detail": "Could not extract capability words"})

    return checks, suggestions


STATUS_SYMBOLS = {"pass": "\u2713", "warn": "!", "fail": "\u2717"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and suggest improvements for a skill description."
    )
    parser.add_argument("description", help="The description text to analyze")
    args = parser.parse_args()

    description = args.description.strip()
    if not description:
        print("Error: description is empty", file=sys.stderr)
        sys.exit(1)

    checks, suggestions = analyze(description)

    has_fail = any(c["status"] == "fail" for c in checks)

    print(f"Description Analysis ({len(description)} chars):")
    for c in checks:
        sym = STATUS_SYMBOLS[c["status"]]
        print(f"  {sym} {c['detail']}")

    if suggestions:
        print()
        print("Suggestions:")
        for s in suggestions:
            print(f"  {s}")

    sys.exit(1 if has_fail else 0)


if __name__ == "__main__":
    main()
