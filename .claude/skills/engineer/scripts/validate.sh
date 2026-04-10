#!/usr/bin/env bash
# Validate an assembled skill package produced by the Engineer.
#
# Usage: validate.sh <assembled_skill_dir>
#
# Checks:
#   1. SKILL.md exists
#   2. Frontmatter parseable (has at least name + description)
#   3. description <= 250 chars (after YAML folding)
#   4. body <= 500 lines
#   5. every ${CLAUDE_SKILL_DIR}/<path> reference in the body resolves
#
# Exit 0 on pass, 1 on failure with diagnostics to stderr.

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: validate.sh <assembled_skill_dir>" >&2
  exit 1
fi

SKILL_DIR="$1"

if [[ ! -d "$SKILL_DIR" ]]; then
  echo "error: not a directory: $SKILL_DIR" >&2
  exit 1
fi

SKILL_MD="$SKILL_DIR/SKILL.md"
if [[ ! -f "$SKILL_MD" ]]; then
  echo "error: SKILL.md not found in $SKILL_DIR" >&2
  exit 1
fi

python3 - "$SKILL_DIR" "$SKILL_MD" <<'PY'
import re
import sys
from pathlib import Path

MAX_DESC = 250
MAX_BODY_LINES = 500

skill_dir = Path(sys.argv[1])
skill_md = Path(sys.argv[2])

text = skill_md.read_text(encoding="utf-8")
lines = text.splitlines()

errors = []

if not lines or lines[0].strip() != "---":
    errors.append("frontmatter: missing opening '---'")
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)

end = None
for i in range(1, len(lines)):
    if lines[i].strip() == "---":
        end = i
        break
if end is None:
    errors.append("frontmatter: missing closing '---'")
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)

fm_lines = lines[1:end]
body_lines = lines[end + 1:]

fm: dict[str, str] = {}
i = 0
while i < len(fm_lines):
    line = fm_lines[i]
    m = re.match(r"^([a-zA-Z][\w\-]*)\s*:\s*(.*)$", line)
    if not m:
        i += 1
        continue
    key, rest = m.group(1), m.group(2).strip()
    if rest in (">-", ">", "|", "|-"):
        j = i + 1
        buf = []
        while j < len(fm_lines):
            nxt = fm_lines[j]
            if nxt.startswith(" ") or nxt.startswith("\t"):
                buf.append(nxt.strip())
                j += 1
            elif nxt.strip() == "":
                buf.append("")
                j += 1
            else:
                break
        fm[key] = " ".join(s for s in buf if s != "").strip()
        i = j
    else:
        if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in ("'", '"'):
            rest = rest[1:-1]
        fm[key] = rest
        i += 1

name = fm.get("name", "")
description = fm.get("description", "")

if not name:
    errors.append("frontmatter: missing 'name'")
if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name or ""):
    errors.append(f"frontmatter: invalid name '{name}' (must match ^[a-z0-9]+(-[a-z0-9]+)*$)")
if name and name != skill_dir.name:
    errors.append(f"frontmatter: name '{name}' != directory '{skill_dir.name}'")

if not description:
    errors.append("frontmatter: missing 'description'")
elif len(description) > MAX_DESC:
    errors.append(f"description: {len(description)} chars > {MAX_DESC} limit")

if len(body_lines) > MAX_BODY_LINES:
    errors.append(f"body: {len(body_lines)} lines > {MAX_BODY_LINES} limit")

body_text = "\n".join(body_lines)
ref_pattern = re.compile(r"\$\{CLAUDE_SKILL_DIR\}/([A-Za-z0-9_\-./]+)")
seen_refs: set[str] = set()
for m in ref_pattern.finditer(body_text):
    seen_refs.add(m.group(1))

for rel in sorted(seen_refs):
    target = skill_dir / rel
    if not target.exists():
        errors.append(f"path: referenced but missing -> {rel}")

if errors:
    print("VALIDATION FAILED:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    sys.exit(1)

print(f"OK: {skill_dir.name} (description={len(description)}c, body={len(body_lines)}l, refs={len(seen_refs)})")
PY
