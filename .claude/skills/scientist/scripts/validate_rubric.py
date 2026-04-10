#!/usr/bin/env python3
"""Validate a Scientist rubric JSON against structural and catalog rules.

CLI:
    python validate_rubric.py --rubric <path> [--catalog <path>]

Exit codes:
    0 — valid
    1 — invalid (errors printed as JSON list to stderr)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


REQUIRED_TOP = ("dimension", "quantitative", "qualitative")
REQUIRED_QUANT = ("metric", "weight", "description")
WEIGHT_TOLERANCE = 0.001


def _default_catalog_path() -> Path:
    skill_dir = os.environ.get("CLAUDE_SKILL_DIR")
    if skill_dir:
        return Path(skill_dir) / "references" / "metrics-catalog.md"
    return Path(__file__).resolve().parent.parent / "references" / "metrics-catalog.md"


def load_catalog_metrics(catalog_path: Path) -> set[str]:
    """Parse metric names from a markdown catalog.

    Recognizes headers like `## metric_name` and bold patterns like `**metric_name**`.
    """
    if not catalog_path.exists():
        return set()
    text = catalog_path.read_text(encoding="utf-8")
    names: set[str] = set()
    header_re = re.compile(r"^##\s+`?([a-z0-9_]+)`?\s*$", re.MULTILINE)
    bold_re = re.compile(r"\*\*`?([a-z0-9_]+)`?\*\*")
    for m in header_re.finditer(text):
        names.add(m.group(1))
    for m in bold_re.finditer(text):
        names.add(m.group(1))
    return names


def validate_rubric(rubric: object, catalog: set[str] | None) -> list[str]:
    errors: list[str] = []

    if not isinstance(rubric, dict):
        return ["rubric must be a JSON object"]

    for key in REQUIRED_TOP:
        if key not in rubric:
            errors.append(f"missing required field: {key}")

    dimension = rubric.get("dimension")
    if "dimension" in rubric and (not isinstance(dimension, str) or not dimension.strip()):
        errors.append("dimension must be a non-empty string")

    quant = rubric.get("quantitative")
    if "quantitative" in rubric:
        if not isinstance(quant, list) or len(quant) == 0:
            errors.append("quantitative must be a non-empty list")
        else:
            total_weight = 0.0
            for i, item in enumerate(quant):
                if not isinstance(item, dict):
                    errors.append(f"quantitative[{i}] must be an object")
                    continue
                for req in REQUIRED_QUANT:
                    if req not in item:
                        errors.append(f"quantitative[{i}] missing field: {req}")
                weight = item.get("weight")
                if not isinstance(weight, (int, float)):
                    errors.append(f"quantitative[{i}].weight must be a number")
                else:
                    if weight < 0 or weight > 1:
                        errors.append(f"quantitative[{i}].weight out of range [0,1]: {weight}")
                    total_weight += float(weight)
                metric = item.get("metric")
                if not isinstance(metric, str) or not metric.strip():
                    errors.append(f"quantitative[{i}].metric must be a non-empty string")
                elif catalog is not None and len(catalog) > 0 and metric not in catalog:
                    errors.append(
                        f"quantitative[{i}].metric '{metric}' not found in metrics catalog"
                    )
                desc = item.get("description")
                if not isinstance(desc, str) or not desc.strip():
                    errors.append(f"quantitative[{i}].description must be a non-empty string")
            if abs(total_weight - 1.0) > WEIGHT_TOLERANCE:
                errors.append(
                    f"quantitative weights must sum to 1.0 (got {total_weight:.6f}, "
                    f"tolerance {WEIGHT_TOLERANCE})"
                )

    qual = rubric.get("qualitative")
    if "qualitative" in rubric:
        if not isinstance(qual, list):
            errors.append("qualitative must be a list")
        else:
            for i, item in enumerate(qual):
                if not isinstance(item, str) or not item.strip():
                    errors.append(f"qualitative[{i}] must be a non-empty string")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Scientist rubric JSON.")
    parser.add_argument("--rubric", required=True, help="Path to rubric JSON file")
    parser.add_argument(
        "--catalog",
        default=None,
        help="Path to metrics catalog markdown (defaults to skill references dir)",
    )
    args = parser.parse_args()

    rubric_path = Path(args.rubric)
    if not rubric_path.exists():
        print(json.dumps([f"rubric file not found: {rubric_path}"]), file=sys.stderr)
        return 1

    try:
        rubric_data = json.loads(rubric_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(json.dumps([f"rubric is not valid JSON: {e}"]), file=sys.stderr)
        return 1

    catalog_path = Path(args.catalog) if args.catalog else _default_catalog_path()
    catalog_metrics = load_catalog_metrics(catalog_path)
    if not catalog_metrics:
        print(
            json.dumps(
                [f"warning: metrics catalog empty or not found at {catalog_path}; skipping catalog check"]
            ),
            file=sys.stderr,
        )
        catalog_for_check: set[str] | None = None
    else:
        catalog_for_check = catalog_metrics

    errors = validate_rubric(rubric_data, catalog_for_check)
    if errors:
        print(json.dumps(errors, indent=2), file=sys.stderr)
        return 1

    print(f"OK: rubric '{rubric_data.get('dimension')}' is valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
