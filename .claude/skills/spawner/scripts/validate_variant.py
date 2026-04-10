#!/usr/bin/env python3
"""Validate a spawned variant package.

Checks:
  - variant directory exists and contains SKILL.md
  - SKILL.md frontmatter has required fields (name, description, dimension)
  - name matches directory basename and regex ^[a-z0-9]+(-[a-z0-9]+)*$
  - description is <= 250 characters
  - body (after closing ---) is <= 500 lines
  - body has at least 2 Example sections (## Example... or ### Example...)
  - every ${CLAUDE_SKILL_DIR}/<path> reference resolves to a file inside the variant dir
  - warns if body has more than 5 H2 sections (variant may be kitchen-sinking)
  - warns if the `dimension` field value is not mentioned anywhere in the body

Outputs JSON to stdout:
  {"valid": bool, "variant_dir": "...", "errors": [...], "warnings": [...]}

Exit code: 0 if no errors, 1 if errors. Warnings do not fail validation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SKILL_DIR_REF_RE = re.compile(r"\$\{CLAUDE_SKILL_DIR\}/([^\s\"'`)<>]+)")
FRONTMATTER_FENCE = "---"
MAX_DESCRIPTION_CHARS = 250
MAX_BODY_LINES = 500
MIN_EXAMPLES = 2
MAX_H2_SECTIONS_WARN = 5


def parse_frontmatter(text: str) -> tuple[dict[str, str], str, list[str]]:
    """Parse YAML-ish frontmatter between --- fences. Returns (fields, body, errors)."""
    errors: list[str] = []
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_FENCE:
        errors.append("SKILL.md does not start with '---' frontmatter fence")
        return {}, text, errors

    close_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == FRONTMATTER_FENCE:
            close_idx = i
            break
    if close_idx == -1:
        errors.append("SKILL.md frontmatter is not closed with '---'")
        return {}, text, errors

    fm_lines = lines[1:close_idx]
    body = "\n".join(lines[close_idx + 1 :])

    fields: dict[str, str] = {}
    i = 0
    while i < len(fm_lines):
        raw = fm_lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if ":" not in raw:
            i += 1
            continue
        key, _, value = raw.partition(":")
        key = key.strip()
        value = value.strip()
        if value in (">-", ">", "|", "|-"):
            collected: list[str] = []
            j = i + 1
            while j < len(fm_lines):
                nxt = fm_lines[j]
                if nxt and not nxt.startswith((" ", "\t")):
                    break
                collected.append(nxt.strip())
                j += 1
            fields[key] = " ".join(c for c in collected if c).strip()
            i = j
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("\"", "'"):
            value = value[1:-1]
        fields[key] = value
        i += 1

    return fields, body, errors


def count_body_lines(body: str) -> int:
    return len(body.splitlines())


def count_example_sections(body: str) -> int:
    count = 0
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Example") or stripped.startswith("### Example"):
            count += 1
    bold_examples = len(re.findall(r"^\s*\*\*Example\s*\d+", body, re.MULTILINE))
    return max(count, bold_examples)


def count_h2_sections(body: str) -> int:
    return sum(1 for line in body.splitlines() if line.startswith("## "))


def validate(variant_dir: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    if not variant_dir.exists() or not variant_dir.is_dir():
        return {
            "valid": False,
            "variant_dir": str(variant_dir),
            "errors": [f"variant directory does not exist: {variant_dir}"],
            "warnings": [],
        }

    skill_md = variant_dir / "SKILL.md"
    if not skill_md.exists():
        return {
            "valid": False,
            "variant_dir": str(variant_dir),
            "errors": ["SKILL.md not found in variant directory"],
            "warnings": [],
        }

    text = skill_md.read_text(encoding="utf-8")
    fields, body, fm_errors = parse_frontmatter(text)
    errors.extend(fm_errors)

    for required in ("name", "description", "dimension"):
        if required not in fields or not fields[required]:
            errors.append(f"frontmatter missing required field: {required}")

    name = fields.get("name", "")
    description = fields.get("description", "")
    dimension = fields.get("dimension", "")

    if name:
        if not NAME_RE.match(name):
            errors.append(
                f"name '{name}' does not match regex ^[a-z0-9]+(-[a-z0-9]+)*$"
            )
        if name != variant_dir.name:
            errors.append(
                f"name '{name}' does not match directory basename '{variant_dir.name}'"
            )

    if description and len(description) > MAX_DESCRIPTION_CHARS:
        errors.append(
            f"description is {len(description)} chars (max {MAX_DESCRIPTION_CHARS})"
        )

    body_lines = count_body_lines(body)
    if body_lines > MAX_BODY_LINES:
        errors.append(f"body is {body_lines} lines (max {MAX_BODY_LINES})")

    example_count = count_example_sections(body)
    if example_count < MIN_EXAMPLES:
        errors.append(
            f"body has {example_count} Example section(s); need at least {MIN_EXAMPLES}"
        )

    for match in SKILL_DIR_REF_RE.finditer(text):
        rel = match.group(1).strip().rstrip(".,;:)")
        rel = re.sub(r"[\s`\"']+$", "", rel)
        target = variant_dir / rel
        if not target.exists():
            errors.append(f"unresolved ${{CLAUDE_SKILL_DIR}} reference: {rel}")

    h2_count = count_h2_sections(body)
    if h2_count > MAX_H2_SECTIONS_WARN:
        warnings.append(
            f"body has {h2_count} H2 sections (> {MAX_H2_SECTIONS_WARN}); "
            "variant may be kitchen-sinking instead of staying focused"
        )

    if dimension and dimension not in body:
        warnings.append(
            f"dimension '{dimension}' is not mentioned anywhere in the body; "
            "variant may not actually be scoped to the dimension"
        )

    return {
        "valid": len(errors) == 0,
        "variant_dir": str(variant_dir),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a spawned variant package against the golden template."
    )
    parser.add_argument(
        "--variant-dir",
        required=True,
        help="path to the variant directory containing SKILL.md",
    )
    args = parser.parse_args()

    result = validate(Path(args.variant_dir).resolve())
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
