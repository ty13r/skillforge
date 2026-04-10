#!/usr/bin/env python3
"""Lightweight taxonomy classifier.

Given a free-form specialization string and an optional list of existing
slugs, score each slug against the specialization using two signals:

1. difflib.SequenceMatcher ratio (character-level similarity)
2. Token overlap (specialization keywords that appear in the slug)

Outputs a JSON classification result to stdout. The caller (the Taxonomist
agent) uses this as a fast first pass before deciding whether to adopt an
existing slug or propose a new one.

Usage:
    python classify.py --specialization "pytest for Django views" \
                       --existing-slugs "unit-tests,integration-tests,e2e"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher

CONFIDENCE_THRESHOLD = 0.4
SEQUENCE_WEIGHT = 0.6
TOKEN_WEIGHT = 0.4


def tokenize(text: str) -> list[str]:
    """Lowercase + split on non-alphanumeric. Drops empty tokens."""
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def token_overlap_score(spec_tokens: set[str], slug: str) -> float:
    """Fraction of slug tokens that also appear in the specialization."""
    slug_tokens = set(tokenize(slug))
    if not slug_tokens:
        return 0.0
    matched = slug_tokens & spec_tokens
    return len(matched) / len(slug_tokens)


def sequence_score(specialization: str, slug: str) -> float:
    """Character-level similarity between specialization and slug."""
    return SequenceMatcher(None, specialization.lower(), slug.lower()).ratio()


def blended_score(specialization: str, spec_tokens: set[str], slug: str) -> float:
    seq = sequence_score(specialization, slug)
    tok = token_overlap_score(spec_tokens, slug)
    return round(SEQUENCE_WEIGHT * seq + TOKEN_WEIGHT * tok, 4)


def parse_existing_slugs(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def classify(specialization: str, existing_slugs: list[str]) -> dict:
    spec_tokens = set(tokenize(specialization))

    if not existing_slugs:
        return {
            "specialization": specialization,
            "best_match_slug": None,
            "confidence": 0.0,
            "suggested_new": True,
            "ranked_matches": [],
            "reason": "No existing slugs provided — cannot reuse, must create new.",
        }

    ranked = [
        {"slug": slug, "score": blended_score(specialization, spec_tokens, slug)}
        for slug in existing_slugs
    ]
    ranked.sort(key=lambda r: r["score"], reverse=True)

    best = ranked[0]
    confidence = best["score"]
    suggested_new = confidence < CONFIDENCE_THRESHOLD

    if suggested_new:
        reason = (
            f"Best match '{best['slug']}' scored {confidence:.2f}, below "
            f"threshold {CONFIDENCE_THRESHOLD}. Propose a new slug with "
            f"justification."
        )
        best_slug: str | None = None
    else:
        reason = (
            f"Best match '{best['slug']}' scored {confidence:.2f}, at or "
            f"above threshold {CONFIDENCE_THRESHOLD}. Reuse this slug."
        )
        best_slug = best["slug"]

    return {
        "specialization": specialization,
        "best_match_slug": best_slug,
        "confidence": confidence,
        "suggested_new": suggested_new,
        "ranked_matches": ranked,
        "reason": reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Score a specialization against existing taxonomy slugs."
    )
    parser.add_argument(
        "--specialization",
        required=True,
        help="Free-form specialization text to classify.",
    )
    parser.add_argument(
        "--existing-slugs",
        default="",
        help="Comma-separated list of existing slugs at the target hierarchy level.",
    )
    args = parser.parse_args()

    if not args.specialization.strip():
        print(
            json.dumps({"error": "specialization must not be empty"}),
            file=sys.stderr,
        )
        return 2

    existing = parse_existing_slugs(args.existing_slugs)
    result = classify(args.specialization, existing)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
