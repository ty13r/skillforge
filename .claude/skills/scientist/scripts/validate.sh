#!/usr/bin/env bash
# Validate a challenge + rubric JSON pair produced by the Scientist.
#
# Usage:
#   bash validate.sh <challenge.json> <rubric.json>
#
# Exit codes:
#   0 — both files valid
#   1 — one or both invalid (diagnostics printed to stderr)
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CATALOG="${SKILL_DIR}/references/metrics-catalog.md"

if [ "$#" -ne 2 ]; then
  echo "usage: validate.sh <challenge.json> <rubric.json>" >&2
  exit 1
fi

CHALLENGE_PATH="$1"
RUBRIC_PATH="$2"
FAIL=0

if [ ! -f "${CHALLENGE_PATH}" ]; then
  echo "FAIL: challenge file not found: ${CHALLENGE_PATH}" >&2
  FAIL=1
fi
if [ ! -f "${RUBRIC_PATH}" ]; then
  echo "FAIL: rubric file not found: ${RUBRIC_PATH}" >&2
  FAIL=1
fi
if [ "${FAIL}" -ne 0 ]; then
  exit 1
fi

python3 - "${CHALLENGE_PATH}" <<'PY'
import json, sys
path = sys.argv[1]
required = ["dimension", "prompt", "difficulty", "verification_method"]
try:
    data = json.loads(open(path, encoding="utf-8").read())
except Exception as e:
    print(f"FAIL: challenge not valid JSON: {e}", file=sys.stderr)
    sys.exit(1)
if not isinstance(data, dict):
    print("FAIL: challenge must be a JSON object", file=sys.stderr)
    sys.exit(1)
errors = []
for f in required:
    if f not in data:
        errors.append(f"missing field: {f}")
    elif not isinstance(data[f], str) or not data[f].strip():
        errors.append(f"field '{f}' must be a non-empty string")
if data.get("difficulty") not in (None, "easy", "medium", "hard"):
    errors.append("difficulty must be one of easy|medium|hard")
if data.get("verification_method") not in (
    None, "deterministic", "hybrid", "qualitative"
):
    errors.append("verification_method must be deterministic|hybrid|qualitative")
if errors:
    for e in errors:
        print(f"FAIL (challenge): {e}", file=sys.stderr)
    sys.exit(1)
print(f"OK: challenge '{data['dimension']}' structurally valid")
PY
CHALLENGE_RC=$?
if [ "${CHALLENGE_RC}" -ne 0 ]; then
  FAIL=1
fi

python3 "${SCRIPT_DIR}/validate_rubric.py" --rubric "${RUBRIC_PATH}" --catalog "${CATALOG}"
RUBRIC_RC=$?
if [ "${RUBRIC_RC}" -ne 0 ]; then
  echo "FAIL: rubric validation failed (see stderr JSON above)" >&2
  FAIL=1
fi

if [ "${FAIL}" -ne 0 ]; then
  echo "validate.sh: FAIL" >&2
  exit 1
fi

echo "validate.sh: PASS"
exit 0
