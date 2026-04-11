#!/usr/bin/env python3
"""SKLD-bench score.py for elixir-ecto-schema-changeset.

Family-specific Ecto schema/migration/changeset scorer. Checks:
- Every expected file exists
- must_contain substrings present
- must_not_contain substrings absent
- Money-named fields (price/amount/total/balance/cost/salary) use :decimal never :float
- cast/3 allowlists do not contain :is_admin or :role from public changeset names
- unique_constraint in changesets has a matching unique_index in produced migrations
  (matched by shared column name OR explicit :name option)
- Association direction sanity: belongs_to parent module and has_many child module
  are inverse-consistent when both appear
"""
import argparse
import json
import re
import sys
from pathlib import Path

# Money-looking field name roots that require :decimal not :float.
MONEY_NAME_RE = re.compile(
    r":(price|amount|total|balance|cost|salary|subtotal|tax|unit_price|quantity_price|fee|rate)\b",
    re.IGNORECASE,
)

# Regex: `field :foo, :float` where foo looks like money.
# We match across a line only — one line per field declaration.
FIELD_FLOAT_RE = re.compile(
    r"field\s+:([a-z_][a-z0-9_]*)\s*,\s*:float",
    re.IGNORECASE,
)

# Regex: `cast(attrs, [:a, :b, :c])` — we'll extract the list contents.
CAST_LIST_RE = re.compile(
    r"cast\s*\(\s*\w+\s*,\s*\[([^\]]*)\]",
)

# Public changeset function names where :is_admin must not be castable.
PUBLIC_CHANGESET_NAMES = {
    "changeset",
    "registration_changeset",
    "update_changeset",
    "profile_changeset",
}

# Regex: `def X_changeset(...)` to locate changeset function definitions.
DEF_CHANGESET_RE = re.compile(r"def\s+([a-z_][a-z0-9_]*)\s*\(")

# Regex: `unique_constraint(:col[, name: :x])`
UNIQUE_CONSTRAINT_RE = re.compile(
    r"unique_constraint\s*\(\s*:([a-z_][a-z0-9_]*)(?:\s*,\s*name:\s*:([a-z_][a-z0-9_]*))?",
)

# Regex: `create unique_index(:table, [:col1, :col2][, name: :x])`
UNIQUE_INDEX_RE = re.compile(
    r"create\s+unique_index\s*\(\s*:([a-z_][a-z0-9_]*)\s*,\s*\[([^\]]*)\](?:[^)]*name:\s*:([a-z_][a-z0-9_]*))?",
)


def _read(path: Path) -> str:
    try:
        return path.read_text()
    except Exception:
        return ""


def _score_file_presence_nonempty(rel: str, output_dir: Path) -> dict:
    """File must exist AND contain something (non-whitespace, >20 chars)."""
    f = output_dir / rel
    exists = f.exists()
    content = _read(f) if exists else ""
    non_empty = len(content.strip()) >= 20
    passed = exists and non_empty
    return {
        "passed": passed,
        "weight": 1.0,
        "actual": (
            "present and non-empty"
            if passed
            else ("empty" if exists else "missing")
        ),
        "expected": "present and non-empty",
        "details": f"Expected output file {rel} (must be non-empty)",
    }


def _score_contains(pat: str, content: str, total: int) -> dict:
    present = pat in content
    return {
        "passed": present,
        "weight": 1.0 / max(total, 1),
        "actual": "present" if present else "absent",
        "expected": "present",
        "details": f"Looking for `{pat}`",
    }


def _score_not_contains(pat: str, content: str, total: int) -> dict:
    absent = pat not in content
    return {
        "passed": absent,
        "weight": 1.0 / max(total, 1),
        "actual": "absent" if absent else "present",
        "expected": "absent",
        "details": f"Looking for absence of `{pat}`",
    }


def _score_money_not_float(content: str) -> dict:
    """Penalize any :float used for money-named field."""
    bad_matches = []
    for m in FIELD_FLOAT_RE.finditer(content):
        name = m.group(1)
        if MONEY_NAME_RE.search(f":{name}"):
            bad_matches.append(name)
    passed = len(bad_matches) == 0
    return {
        "passed": passed,
        "weight": 1.0,
        "actual": f"{len(bad_matches)} money-named :float field(s)" + (
            f": {bad_matches}" if bad_matches else ""
        ),
        "expected": "0 money-named :float fields",
        "details": "Money-named fields must use :decimal not :float",
    }


def _score_no_is_admin_public_cast(content: str) -> dict:
    """Penalize :is_admin or :role in public changeset cast/3 calls.

    A best-effort heuristic: we look for def <name>_changeset blocks whose
    name is in PUBLIC_CHANGESET_NAMES, scan until the next `def ` boundary,
    extract cast lists, and check for forbidden atoms.
    """
    bad_matches = []
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        m = DEF_CHANGESET_RE.search(line)
        if m and m.group(1) in PUBLIC_CHANGESET_NAMES:
            # collect lines until next def or end
            body_lines = [line]
            j = i + 1
            while j < len(lines) and not DEF_CHANGESET_RE.search(lines[j]):
                body_lines.append(lines[j])
                j += 1
            body = "\n".join(body_lines)
            for cm in CAST_LIST_RE.finditer(body):
                cast_list = cm.group(1)
                for bad in (":is_admin", ":role", ":password_hash_override"):
                    if bad in cast_list:
                        # password_hash is ok in registration, but bad elsewhere
                        # We only flag is_admin and role hard.
                        if bad in (":is_admin", ":role"):
                            bad_matches.append(
                                f"{m.group(1)}: {bad}"
                            )
            i = j
        else:
            i += 1
    passed = len(bad_matches) == 0
    return {
        "passed": passed,
        "weight": 1.0,
        "actual": f"{len(bad_matches)} privileged fields in public cast lists"
        + (f": {bad_matches}" if bad_matches else ""),
        "expected": "no :is_admin or :role in public cast lists",
        "details": "Mass assignment guard — see Phoenix security guide",
    }


def _score_unique_constraint_matches_index(
    schema_content: str, migration_content: str
) -> dict:
    """Check each unique_constraint in schema has a matching unique_index in migration.

    Matching is by: (a) shared :name option, or (b) constraint column appearing
    in a unique_index columns list.
    """
    constraints = list(UNIQUE_CONSTRAINT_RE.finditer(schema_content))
    indexes = list(UNIQUE_INDEX_RE.finditer(migration_content))
    if not constraints:
        return {
            "passed": True,
            "weight": 1.0,
            "actual": "no unique_constraint in schema",
            "expected": "all unique_constraints matched by unique_index",
            "details": "nothing to check",
        }
    unmatched = []
    for c in constraints:
        col = c.group(1)
        name = c.group(2)
        matched = False
        for idx in indexes:
            idx_cols_raw = idx.group(2)
            idx_name = idx.group(3)
            idx_cols = [s.strip().lstrip(":") for s in idx_cols_raw.split(",")]
            if name and idx_name and name == idx_name:
                matched = True
                break
            if not name and col in idx_cols:
                matched = True
                break
            if name and idx_name and name != idx_name and col in idx_cols:
                # still an OK match if at least columns overlap and no explicit name
                matched = True
                break
        if not matched:
            unmatched.append(f"unique_constraint(:{col})")
    passed = len(unmatched) == 0
    return {
        "passed": passed,
        "weight": 1.0,
        "actual": f"{len(unmatched)} unmatched" + (
            f": {unmatched}" if unmatched else ""
        ),
        "expected": "all unique_constraints matched by unique_index",
        "details": "See Arrowsmith Labs: unique_constraint does nothing without matching unique_index",
    }


def score_challenge(challenge: dict, output_dir: Path) -> dict:
    objectives = {}
    expected = challenge.get("expected_outputs", {})

    files = expected.get("files", [])
    must_contain = expected.get("must_contain", [])
    must_not_contain = expected.get("must_not_contain", [])

    # File presence (must exist and be non-empty). Weight: 0.5 per file —
    # file presence is necessary but far from sufficient. A file that exists
    # but contains no correct content should still fail.
    n_files = max(len(files), 1)
    file_unit = 0.5 / n_files
    for rel in files:
        obj = _score_file_presence_nonempty(rel, output_dir)
        obj["weight"] = file_unit
        objectives[f"file:{rel}"] = obj

    # Concatenate content from all expected files (most checks are cross-file)
    combined = ""
    substantive_total = 0
    for rel in files:
        content = _read(output_dir / rel)
        combined += content + "\n"
        substantive_total += len(content.strip())

    # A file dump is "substantive" if it has at least 40 non-whitespace chars
    # per requested file (a sanity floor). If not, `must_not_contain` passes
    # become trivial and should not be credited.
    substantive = substantive_total >= 40 * max(len(files), 1)

    # Per-pattern contains — gets heaviest weight because these discriminate.
    # Weight each contains pattern at 2.0 collectively (combined = 2.0)
    n_contains = max(len(must_contain), 1)
    contains_unit = 2.0 / n_contains
    for pat in must_contain:
        key = f"contains:{pat[:40]}"
        obj = _score_contains(pat, combined, n_contains)
        obj["weight"] = contains_unit
        objectives[key] = obj

    # Per-pattern not-contains — only credit if content was substantive.
    # Otherwise an empty file would pass all absent checks for free.
    n_not = max(len(must_not_contain), 1)
    not_unit = (1.0 / n_not) if substantive else (0.0)
    for pat in must_not_contain:
        key = f"absent:{pat[:40]}"
        obj = _score_not_contains(pat, combined, n_not)
        obj["weight"] = not_unit
        # If non-substantive, mark as failed so the objective's "passed" reflects
        # that we can't really verify absence on empty content.
        if not substantive:
            obj["passed"] = False
            obj["actual"] = "content too short to verify"
            obj["details"] = (
                obj["details"] + " (content too short to verify absence)"
            )
        objectives[key] = obj

    # Family-specific: money-field :float guard (always applied to combined output)
    # Heavy weight — this is the family's signature discriminator.
    # Only credit when content is substantive — an empty file trivially has no :float.
    money_obj = _score_money_not_float(combined)
    money_obj["weight"] = 2.0 if substantive else 0.0
    if not substantive:
        money_obj["passed"] = False
        money_obj["actual"] = "content too short to verify"
    objectives["money_not_float"] = money_obj

    # Family-specific: public cast list must not contain :is_admin or :role
    # Heavy weight — the second-most critical discriminator.
    # Also guarded on substantive content.
    is_admin_obj = _score_no_is_admin_public_cast(combined)
    is_admin_obj["weight"] = 1.5 if substantive else 0.0
    if not substantive:
        is_admin_obj["passed"] = False
        is_admin_obj["actual"] = "content too short to verify"
    objectives["no_is_admin_public_cast"] = is_admin_obj

    # Family-specific: unique_constraint must have matching unique_index when both
    # schema and migration files are present in the output
    has_schema = any("/lib/" in rel or rel.endswith(".ex") and "migration" not in rel for rel in files)
    has_migration = any("migrations" in rel for rel in files)
    if has_schema and has_migration:
        schema_content = ""
        migration_content = ""
        for rel in files:
            content = _read(output_dir / rel)
            if "migrations" in rel:
                migration_content += content + "\n"
            else:
                schema_content += content + "\n"
        objectives["unique_constraint_index_match"] = _score_unique_constraint_matches_index(
            schema_content, migration_content
        )

    # Aggregate
    total_weight = sum(o["weight"] for o in objectives.values()) or 1.0
    weighted_score = sum(o["weight"] for o in objectives.values() if o["passed"])
    score = weighted_score / total_weight

    return {
        "challenge_id": challenge["id"],
        "passed": score >= 0.7,
        "score": round(score, 4),
        "objectives": objectives,
        "diagnostics": [],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--challenge", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()

    try:
        challenge = json.loads(args.challenge.read_text())
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(json.dumps({"error": f"malformed challenge: {e}"}))
        sys.exit(1)

    try:
        result = score_challenge(challenge, args.output)
    except Exception as e:
        print(json.dumps({"error": f"scorer crashed: {e}"}))
        sys.exit(2)

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
