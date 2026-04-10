#!/usr/bin/env python3
"""Validate a skill package directory against all quality criteria.

Usage: python validate_skill_package.py /path/to/skill-dir
"""

import argparse
import ast
import json
import re
import sys
from pathlib import Path


def parse_frontmatter(text: str) -> dict[str, str]:
    """Extract YAML frontmatter from SKILL.md content.

    Handles simple key: value pairs and YAML multiline scalars (| and >).
    """
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    block = text[3:end].strip()
    result: dict[str, str] = {}
    current_key: str | None = None
    multiline_lines: list[str] = []

    def _flush() -> None:
        if current_key is not None and multiline_lines:
            result[current_key] = " ".join(multiline_lines).strip()

    for line in block.splitlines():
        # Check if this is a top-level key (not indented)
        if line and not line[0].isspace() and ":" in line:
            _flush()
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value in ("|", ">", "|+", "|-", ">+", ">-"):
                # Start of multiline block
                current_key = key
                multiline_lines = []
            else:
                current_key = None
                multiline_lines = []
                result[key] = value
        elif current_key is not None:
            # Continuation of multiline block
            multiline_lines.append(line.strip())
        # else: ignore malformed lines

    _flush()
    return result


def check(name: str, passed: bool, detail: str = "", warn: bool = False) -> dict:
    if passed:
        status = "pass"
    elif warn:
        status = "warn"
    else:
        status = "fail"
    return {"name": name, "status": status, "detail": detail}


def validate(skill_dir: Path) -> dict:
    checks: list[dict] = []
    suggestions: list[str] = []

    skill_md = skill_dir / "SKILL.md"

    # --- SKILL.md existence ---
    if not skill_md.exists():
        checks.append(check("skill_md_exists", False, "SKILL.md not found"))
        return _build_report(checks, suggestions)

    content = skill_md.read_text(encoding="utf-8")
    lines = content.splitlines()
    checks.append(check("skill_md_exists", True))
    checks.append(check("skill_md_nonempty", len(content.strip()) > 0,
                         "SKILL.md is empty" if not content.strip() else ""))

    # --- Frontmatter ---
    fm = parse_frontmatter(content)
    name_val = fm.get("name", "")
    name_re = r"^[a-z0-9]+(-[a-z0-9]+)*$"
    checks.append(check("frontmatter_name_present", bool(name_val),
                         "" if name_val else "Missing 'name' in frontmatter"))
    checks.append(check("frontmatter_name_valid",
                         bool(re.match(name_re, name_val)) if name_val else False,
                         f"'{name_val}' does not match {name_re}" if name_val and not re.match(name_re, name_val) else ""))

    desc = fm.get("description", "")
    checks.append(check("frontmatter_description_present", bool(desc),
                         "" if desc else "Missing 'description' in frontmatter"))

    desc_len = len(desc)
    if desc_len > 1024:
        checks.append(check("description_length", False,
                             f"{desc_len} chars (>1024 max)"))
    elif desc_len > 250:
        checks.append(check("description_length", False,
                             f"{desc_len} chars (>250 recommended)", warn=True))
    else:
        checks.append(check("description_length", True, f"{desc_len} chars"))

    desc_lower = desc.lower()
    has_use_when = "use when" in desc_lower
    checks.append(check("description_use_when", has_use_when,
                         "" if has_use_when else "Missing 'Use when' trigger language"))
    if not has_use_when:
        suggestions.append("Add 'Use when ...' to the description for better trigger activation")

    has_not_for = "not for" in desc_lower
    checks.append(check("description_not_for", has_not_for,
                         "" if has_not_for else "Missing 'NOT for' exclusions"))
    if not has_not_for:
        suggestions.append("Add 'NOT for X, Y, or Z' to prevent false activations")

    has_even_if = "even if" in desc_lower
    checks.append(check("description_even_if", has_even_if,
                         "" if has_even_if else "Missing 'even if' pushy language"))
    if not has_even_if:
        suggestions.append("Add 'even if they don't explicitly ask for ...' for better trigger recall")

    # --- Body checks ---
    # Find where body starts (after frontmatter)
    body_start = 0
    if content.startswith("---"):
        end_idx = content.find("---", 3)
        if end_idx != -1:
            body_start = end_idx + 3

    body = content[body_start:]
    body_lines = body.splitlines()

    line_count = len(lines)
    checks.append(check("skill_md_under_500_lines", line_count <= 500,
                         f"{line_count} lines" if line_count > 500 else f"{line_count} lines"))

    body_lower = body.lower()

    checks.append(check("has_quick_start_section",
                         bool(re.search(r"^##\s+quick\s+start", body_lower, re.MULTILINE)),
                         "" if re.search(r"^##\s+quick\s+start", body_lower, re.MULTILINE) else "Missing '## Quick Start' section"))

    checks.append(check("has_workflow_section",
                         bool(re.search(r"^##\s+workflow", body_lower, re.MULTILINE)),
                         "" if re.search(r"^##\s+workflow", body_lower, re.MULTILINE) else "Missing '## Workflow' section"))

    has_examples = bool(re.search(r"^##\s+examples?", body_lower, re.MULTILINE))
    example_entries = re.findall(r"\*\*example", body_lower)
    example_count = len(example_entries)
    checks.append(check("has_examples_section", has_examples,
                         "" if has_examples else "Missing '## Examples' section"))
    checks.append(check("has_enough_examples", example_count >= 2,
                         f"Found {example_count} '**Example' entries (need >=2)"))
    if example_count < 2:
        suggestions.append(f"Add at least {2 - example_count} more '**Example ...**' entries under ## Examples")

    has_gotchas = bool(re.search(r"^##\s+(gotchas?|common\s+mistakes?)", body_lower, re.MULTILINE))
    checks.append(check("has_gotchas_section", has_gotchas,
                         "" if has_gotchas else "Missing '## Gotchas' or '## Common Mistakes' section"))

    has_out_of_scope = bool(re.search(r"^##\s+out\s+of\s+scope", body_lower, re.MULTILINE))
    checks.append(check("has_out_of_scope_section", has_out_of_scope,
                         "" if has_out_of_scope else "Missing '## Out of Scope' section"))

    # --- Path references ---
    path_refs = re.findall(r'\$\{CLAUDE_SKILL_DIR\}/([^\s`"\']+)', body)
    for ref_path in path_refs:
        resolved = skill_dir / ref_path
        checks.append(check(f"path_ref_{ref_path}", resolved.exists(),
                             f"Referenced path does not exist: {ref_path}" if not resolved.exists() else ""))

    # --- Scripts ---
    validate_sh = skill_dir / "scripts" / "validate.sh"
    checks.append(check("validate_sh_exists", validate_sh.exists(),
                         "" if validate_sh.exists() else "scripts/validate.sh not found"))
    if validate_sh.exists():
        sh_content = validate_sh.read_text(encoding="utf-8")
        sh_lines = sh_content.splitlines()
        checks.append(check("validate_sh_shebang", sh_content.startswith("#!/"),
                             "" if sh_content.startswith("#!/") else "Missing shebang (#!/...)"))
        checks.append(check("validate_sh_set_e",
                             "set -e" in sh_content or "set -euo pipefail" in sh_content,
                             "" if ("set -e" in sh_content or "set -euo pipefail" in sh_content) else "Missing 'set -e' or 'set -euo pipefail'"))
        checks.append(check("validate_sh_not_stub", len(sh_lines) > 5,
                             f"Only {len(sh_lines)} lines (stub?)" if len(sh_lines) <= 5 else ""))

    main_helper = skill_dir / "scripts" / "main_helper.py"
    checks.append(check("main_helper_exists", main_helper.exists(),
                         "" if main_helper.exists() else "scripts/main_helper.py not found"))
    if main_helper.exists():
        helper_content = main_helper.read_text(encoding="utf-8")
        helper_lines = helper_content.splitlines()
        try:
            ast.parse(helper_content)
            checks.append(check("main_helper_valid_python", True))
        except SyntaxError as e:
            checks.append(check("main_helper_valid_python", False,
                                 f"SyntaxError: {e}"))
        checks.append(check("main_helper_not_stub", len(helper_lines) > 10,
                             f"Only {len(helper_lines)} lines (stub?)" if len(helper_lines) <= 10 else ""))

    # --- References ---
    guide_md = skill_dir / "references" / "guide.md"
    checks.append(check("guide_md_exists", guide_md.exists(),
                         "" if guide_md.exists() else "references/guide.md not found"))
    if guide_md.exists():
        guide_lines = guide_md.read_text(encoding="utf-8").splitlines()
        checks.append(check("guide_md_substantive", len(guide_lines) > 50,
                             f"Only {len(guide_lines)} lines (need >50)" if len(guide_lines) <= 50 else ""))

    return _build_report(checks, suggestions)


def _build_report(checks: list[dict], suggestions: list[str]) -> dict:
    summary = {"pass": 0, "warn": 0, "fail": 0}
    for c in checks:
        summary[c["status"]] += 1
    status = "fail" if summary["fail"] > 0 else "pass"
    return {
        "status": status,
        "checks": checks,
        "summary": summary,
        "suggestions": suggestions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a skill package directory against quality criteria."
    )
    parser.add_argument("directory", type=Path, help="Path to the skill directory")
    args = parser.parse_args()

    skill_dir = args.directory.resolve()
    if not skill_dir.is_dir():
        print(json.dumps({"error": f"Not a directory: {skill_dir}"}), file=sys.stderr)
        sys.exit(1)

    report = validate(skill_dir)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
