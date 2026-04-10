#!/usr/bin/env bash
# Spawner self-check: validates a spawned variant package.
# Usage: bash validate.sh <variant_dir>
# Exit 0 if the variant is structurally valid, 1 otherwise.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: validate.sh <variant_dir>" >&2
  exit 2
fi

VARIANT_DIR="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALIDATOR="${SCRIPT_DIR}/validate_variant.py"

if [[ ! -f "${VALIDATOR}" ]]; then
  echo "ERROR: validator not found at ${VALIDATOR}" >&2
  exit 2
fi

RESULT="$(python3 "${VALIDATOR}" --variant-dir "${VARIANT_DIR}" || true)"
echo "${RESULT}"

VALID="$(printf '%s' "${RESULT}" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("valid"))')"
ERR_COUNT="$(printf '%s' "${RESULT}" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d.get("errors",[])))')"
WARN_COUNT="$(printf '%s' "${RESULT}" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d.get("warnings",[])))')"

echo ""
echo "----- variant validation summary -----"
echo "variant_dir: ${VARIANT_DIR}"
echo "valid:       ${VALID}"
echo "errors:      ${ERR_COUNT}"
echo "warnings:    ${WARN_COUNT}"
echo "--------------------------------------"

if [[ "${VALID}" == "True" ]]; then
  exit 0
else
  exit 1
fi
