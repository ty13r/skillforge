#!/usr/bin/env bash
# Validate a Reviewer evaluation JSON file.
#
# Checks:
#   - File exists and is valid JSON
#   - Required top-level fields present:
#       variant_id, aggregate_fitness, quantitative_subtotal,
#       qualitative_subtotal, metrics
#   - If `weights` is present, its numeric values sum to 1.0 +/- 0.001
#
# Exits 0 on success, 1 on failure. Prints diagnostics to stderr on failure.
#
# Usage:
#   bash scripts/validate.sh path/to/evaluation.json

set -e

if [ "$#" -ne 1 ]; then
    echo "usage: bash scripts/validate.sh <path-to-evaluation.json>" >&2
    exit 1
fi

TARGET="$1"

if [ ! -f "$TARGET" ]; then
    echo "validate.sh: file not found: $TARGET" >&2
    exit 1
fi

python3 - "$TARGET" <<'PY'
import json
import sys

path = sys.argv[1]

try:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
except json.JSONDecodeError as exc:
    print(f"validate.sh: invalid JSON ({exc})", file=sys.stderr)
    sys.exit(1)
except OSError as exc:
    print(f"validate.sh: could not read file ({exc})", file=sys.stderr)
    sys.exit(1)

if not isinstance(data, dict):
    print("validate.sh: root must be a JSON object", file=sys.stderr)
    sys.exit(1)

required = [
    "variant_id",
    "aggregate_fitness",
    "quantitative_subtotal",
    "qualitative_subtotal",
    "metrics",
]

missing = [field for field in required if field not in data]
if missing:
    print(
        "validate.sh: missing required fields: " + ", ".join(missing),
        file=sys.stderr,
    )
    sys.exit(1)

# Type sanity checks on the fitness triple.
for field in ("aggregate_fitness", "quantitative_subtotal", "qualitative_subtotal"):
    value = data[field]
    if not isinstance(value, (int, float)):
        print(
            f"validate.sh: field '{field}' must be numeric, got {type(value).__name__}",
            file=sys.stderr,
        )
        sys.exit(1)
    if not (0.0 <= float(value) <= 1.0):
        print(
            f"validate.sh: field '{field}' out of range [0, 1]: {value}",
            file=sys.stderr,
        )
        sys.exit(1)

if not isinstance(data["metrics"], dict):
    print("validate.sh: 'metrics' must be a JSON object", file=sys.stderr)
    sys.exit(1)

# Optional weights check.
if "weights" in data:
    weights = data["weights"]
    if not isinstance(weights, dict):
        print("validate.sh: 'weights' must be an object when present", file=sys.stderr)
        sys.exit(1)
    try:
        total = sum(float(v) for v in weights.values())
    except (TypeError, ValueError) as exc:
        print(f"validate.sh: non-numeric weight value ({exc})", file=sys.stderr)
        sys.exit(1)
    if abs(total - 1.0) > 0.001:
        print(
            f"validate.sh: weights must sum to 1.0 +/- 0.001, got {total:.6f}",
            file=sys.stderr,
        )
        sys.exit(1)

print("validate.sh: OK")
sys.exit(0)
PY
