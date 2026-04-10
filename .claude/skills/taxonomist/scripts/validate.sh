#!/usr/bin/env bash
# Validate a classification output JSON file produced by classify.py or by
# the Taxonomist agent. Exits 0 on success, 1 on failure with diagnostics.
#
# Usage: bash validate.sh <path-to-classification.json>
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "ERROR: missing argument. Usage: validate.sh <classification.json>" >&2
  exit 1
fi

INPUT="$1"

if [[ ! -f "$INPUT" ]]; then
  echo "ERROR: file not found: $INPUT" >&2
  exit 1
fi

python3 - "$INPUT" <<'PY'
import json
import sys

path = sys.argv[1]

try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
except json.JSONDecodeError as e:
    print(f"ERROR: invalid JSON in {path}: {e}", file=sys.stderr)
    sys.exit(1)

if not isinstance(data, dict):
    print("ERROR: top-level JSON must be an object.", file=sys.stderr)
    sys.exit(1)

required = ["specialization", "best_match_slug", "confidence",
            "suggested_new", "ranked_matches"]
missing = [k for k in required if k not in data]
if missing:
    print(f"ERROR: missing required fields: {missing}", file=sys.stderr)
    sys.exit(1)

if not isinstance(data["specialization"], str) or not data["specialization"].strip():
    print("ERROR: 'specialization' must be a non-empty string.", file=sys.stderr)
    sys.exit(1)

bms = data["best_match_slug"]
if bms is not None and not isinstance(bms, str):
    print("ERROR: 'best_match_slug' must be a string or null.", file=sys.stderr)
    sys.exit(1)

conf = data["confidence"]
if not isinstance(conf, (int, float)):
    print("ERROR: 'confidence' must be a number.", file=sys.stderr)
    sys.exit(1)
conf = float(conf)
if conf < 0.0 or conf > 1.0:
    print(f"ERROR: 'confidence' must be in [0.0, 1.0], got {conf}.", file=sys.stderr)
    sys.exit(1)

if not isinstance(data["suggested_new"], bool):
    print("ERROR: 'suggested_new' must be a boolean.", file=sys.stderr)
    sys.exit(1)

rm = data["ranked_matches"]
if not isinstance(rm, list):
    print("ERROR: 'ranked_matches' must be a list.", file=sys.stderr)
    sys.exit(1)

for i, entry in enumerate(rm):
    if not isinstance(entry, dict):
        print(f"ERROR: ranked_matches[{i}] must be an object.", file=sys.stderr)
        sys.exit(1)
    if "slug" not in entry or not isinstance(entry["slug"], str):
        print(f"ERROR: ranked_matches[{i}].slug must be a string.", file=sys.stderr)
        sys.exit(1)
    if "score" not in entry or not isinstance(entry["score"], (int, float)):
        print(f"ERROR: ranked_matches[{i}].score must be a number.", file=sys.stderr)
        sys.exit(1)

if bms is not None and rm:
    top = rm[0]["slug"]
    if top != bms:
        print(
            f"WARN: 'best_match_slug'={bms!r} but top-ranked slug is {top!r}.",
            file=sys.stderr,
        )

if data["suggested_new"] is False and conf < 0.4:
    print(
        f"WARN: suggested_new=false but confidence={conf:.2f} is below 0.4.",
        file=sys.stderr,
    )
if data["suggested_new"] is True and conf >= 0.4 and bms is not None:
    print(
        f"WARN: suggested_new=true but confidence={conf:.2f} and a match exists.",
        file=sys.stderr,
    )

print(f"OK: {path} is a valid classification output.")
PY
