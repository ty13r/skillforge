#!/usr/bin/env python3
"""Detect merge conflicts across variant directories before assembly.

Usage:
    python check_conflicts.py --variants <dir1> <dir2> [<dir3> ...]

Emits a JSON report to stdout. Exit 0 if conflict_count == 0, else 1.
Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


MAX_DESCRIPTION_CHARS = 250


def read_frontmatter(skill_md: Path) -> dict[str, str]:
    """Parse the YAML frontmatter block of a SKILL.md file.

    Supports folded scalars introduced with `>-` by joining continuation
    lines with a single space. Returns a dict of top-level scalar keys.
    Tolerant of missing file.
    """
    if not skill_md.exists() or not skill_md.is_file():
        return {}
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return {}

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}

    fm_lines = lines[1:end]
    out: dict[str, str] = {}
    i = 0
    while i < len(fm_lines):
        line = fm_lines[i]
        m = re.match(r"^([a-zA-Z][\w\-]*)\s*:\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2).strip()
        if rest in (">-", ">", "|", "|-"):
            # Folded / literal block scalar. Consume indented lines.
            j = i + 1
            buf: list[str] = []
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
            joined = " ".join(s for s in buf if s != "")
            out[key] = joined.strip()
            i = j
        else:
            # Strip surrounding quotes if present.
            if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in ("'", '"'):
                rest = rest[1:-1]
            out[key] = rest
            i += 1
    return out


def extract_body(skill_md: Path) -> str:
    """Return the post-frontmatter body of a SKILL.md. Empty string if missing."""
    if not skill_md.exists() or not skill_md.is_file():
        return ""
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return ""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[i + 1 :])
    return ""


def extract_headers(body: str) -> list[str]:
    """Return all H2 and H3 headers from the body, stripped of leading #."""
    headers: list[str] = []
    for raw in body.splitlines():
        line = raw.rstrip()
        if line.startswith("### "):
            headers.append(line[4:].strip())
        elif line.startswith("## "):
            headers.append(line[3:].strip())
    return headers


def list_scripts(variant_dir: Path) -> list[str]:
    """Return script filenames (not paths) under <variant>/scripts/. Empty if missing."""
    scripts_dir = variant_dir / "scripts"
    if not scripts_dir.exists() or not scripts_dir.is_dir():
        return []
    return sorted(p.name for p in scripts_dir.iterdir() if p.is_file())


def scan_variant(variant_dir: Path) -> dict:
    """Collect frontmatter, scripts, headers for one variant directory."""
    skill_md = variant_dir / "SKILL.md"
    fm = read_frontmatter(skill_md)
    body = extract_body(skill_md)
    return {
        "path": str(variant_dir),
        "name": fm.get("name", variant_dir.name),
        "description": fm.get("description", ""),
        "description_length": len(fm.get("description", "")),
        "scripts": list_scripts(variant_dir),
        "headers": extract_headers(body),
    }


def detect_duplicate_files(variants: list[dict]) -> list[dict]:
    """Any script filename appearing in ≥2 variant scripts/ directories."""
    seen: dict[str, list[str]] = defaultdict(list)
    for v in variants:
        for script in v["scripts"]:
            seen[script].append(v["name"])
    return [
        {"filename": name, "variants": owners}
        for name, owners in sorted(seen.items())
        if len(owners) > 1
    ]


def detect_overlapping_sections(variants: list[dict]) -> list[dict]:
    """Any H2/H3 header text appearing in ≥2 variants."""
    seen: dict[str, list[str]] = defaultdict(list)
    for v in variants:
        for h in v["headers"]:
            seen[h].append(v["name"])
    return [
        {"header": h, "variants": owners}
        for h, owners in sorted(seen.items())
        if len(owners) > 1
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect merge conflicts across variant directories."
    )
    parser.add_argument(
        "--variants",
        nargs="+",
        required=True,
        help="Two or more variant directory paths.",
    )
    args = parser.parse_args()

    if len(args.variants) < 2:
        print("error: --variants requires at least 2 directories", file=sys.stderr)
        return 2

    variant_paths = [Path(p) for p in args.variants]
    variants = [scan_variant(p) for p in variant_paths]

    duplicate_files = detect_duplicate_files(variants)
    overlapping_sections = detect_overlapping_sections(variants)

    concatenated = " ".join(v["description"] for v in variants if v["description"])
    total_description_length = len(concatenated)
    description_conflict = total_description_length > MAX_DESCRIPTION_CHARS

    conflict_count = (
        len(duplicate_files)
        + len(overlapping_sections)
        + (1 if description_conflict else 0)
    )

    report = {
        "variants": [
            {
                "name": v["name"],
                "path": v["path"],
                "description_length": v["description_length"],
                "script_count": len(v["scripts"]),
                "header_count": len(v["headers"]),
            }
            for v in variants
        ],
        "duplicate_files": duplicate_files,
        "overlapping_sections": overlapping_sections,
        "description_conflict": description_conflict,
        "total_description_length": total_description_length,
        "conflict_count": conflict_count,
    }

    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if conflict_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
