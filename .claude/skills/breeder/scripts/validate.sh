#!/usr/bin/env bash
# Validate a Breeder mutation output JSON.
#
# Usage: validate.sh <mutation_output.json>
# Exit 0 on pass, non-zero on failure with diagnostics on stderr.

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $(basename "$0") <mutation_output.json>" >&2
  exit 2
fi

INPUT="$1"

if [[ ! -f "$INPUT" ]]; then
  echo "error: file not found: $INPUT" >&2
  exit 1
fi

python3 - "$INPUT" <<'PY'
import json
import sys

path = sys.argv[1]
required = ("variant_id", "weakest_metric", "mutation_strategy", "rationale")

try:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
except json.JSONDecodeError as exc:
    print(f"error: invalid JSON: {exc}", file=sys.stderr)
    sys.exit(1)

if not isinstance(data, dict):
    print("error: top-level JSON must be an object", file=sys.stderr)
    sys.exit(1)

missing = [f for f in required if f not in data]
if missing:
    print(f"error: missing required fields: {', '.join(missing)}", file=sys.stderr)
    sys.exit(1)

empty = [f for f in required if not str(data.get(f, "")).strip()]
if empty:
    print(f"error: empty required fields: {', '.join(empty)}", file=sys.stderr)
    sys.exit(1)

rationale = str(data["rationale"]).strip()
if len(rationale) < 20:
    print(
        f"error: rationale too short ({len(rationale)} chars); "
        "must cite a concrete symptom from the trace",
        file=sys.stderr,
    )
    sys.exit(1)

print(f"ok: mutation output valid for variant {data['variant_id']}")
PY

exit 0
