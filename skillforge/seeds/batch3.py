"""Batch 3 Gen 0 Seeds: domains 11-15.

Accessibility Auditor, Data Transformer, Regex Builder,
Error Handler, Terraform Module — each with full supporting_files
(scripts + references).
"""
from __future__ import annotations

from skillforge.seeds import _build

# ---------------------------------------------------------------------------
# 11. Accessibility Auditor
# ---------------------------------------------------------------------------
_A11Y_BODY = """\
## Quick Start
Scan HTML/JSX files for WCAG 2.1 Level A and AA violations, report each with
the specific success criterion and a concrete fix. Run the helper script for
deterministic static checks, then layer on manual review guidance.

## When to use this skill
Use when the user says "accessibility", "a11y", "WCAG", "screen reader",
"alt text", "ARIA", "keyboard navigation", "contrast ratio", "form labels",
or "audit this page". Triggers on any HTML, JSX, or TSX file review where
accessibility is mentioned, even if they don't explicitly ask for WCAG compliance.

## Workflow

### Step 1: Gather target files
Identify the HTML/JSX/TSX files to audit. If the user provides a directory,
glob for `**/*.html`, `**/*.jsx`, `**/*.tsx`. Read
`${CLAUDE_SKILL_DIR}/references/guide.md` for the WCAG criteria checklist.

### Step 2: Run the static scanner
```bash
python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py --mode static --path "<target>"
```
This parses files for missing alt text, unlabeled inputs, empty interactive
elements, heading hierarchy gaps, missing lang attribute, and missing ARIA
landmarks. Output is JSON with violations and a compliance score.

### Step 3: Review scanner output and add manual findings
Read the JSON output. For each violation:
- Confirm the file and line reference is correct
- Add the WCAG success criterion (e.g., 1.1.1 for alt text)
- Write a concrete fix with a code example

For issues the scanner cannot detect (dynamic content, focus management,
screen reader announcements), add manual findings based on code review.

### Step 4: Validate the report
```bash
bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh "<report_json_path>"
```
Ensures all violations reference valid WCAG criteria, impact levels are
correct, and fix suggestions are non-empty.

### Step 5: Present the audit report
Group findings by severity (critical > serious > moderate > minor). Include
the compliance score, total violations, and a prioritized fix list.

## Examples

**Example 1: Missing alt text and form labels**
Input: "audit the accessibility of src/components/LoginForm.tsx"
Output: Scans the file, finds 2 `<img>` tags without alt attributes (WCAG 1.1.1),
1 `<input>` without a `<label>` (WCAG 1.3.1), reports compliance score of 70%,
provides fix code for each violation.

**Example 2: Heading hierarchy and landmarks**
Input: "check if our landing page passes WCAG AA"
Output: Detects h1 -> h3 skip (WCAG 1.3.1), missing `<main>` landmark (WCAG 1.3.1),
low contrast on subtitle text (WCAG 1.4.3 requires 4.5:1), provides fixes with
correct heading nesting and ARIA landmark roles.

**Example 3: Interactive widget accessibility**
Input: "is our custom dropdown accessible?"
Output: Finds missing `role="combobox"`, no `aria-expanded` state, no keyboard
handler for arrow keys or Escape. References the ARIA combobox pattern from the
guide and provides a complete accessible implementation.

## Common mistakes to avoid
- Relying solely on automated scanning — axe-core catches ~30% of WCAG issues;
  manual review is required for focus management, reading order, and dynamic content
- Adding `alt=""` to every image — decorative images get empty alt, informative
  images need descriptive text
- Using `aria-label` when a visible `<label>` element would be better
- Assuming color contrast tools handle all cases — text over images and gradients
  need manual checking
- Ignoring keyboard navigation — every interactive element must be reachable and
  operable via keyboard alone

## Out of Scope
This skill does NOT:
- Run browser-based axe-core scans (use Playwright + axe-core separately)
- Test with actual screen readers (manual testing required)
- Certify legal WCAG compliance (requires human auditor)
"""

_A11Y_VALIDATE = r"""#!/usr/bin/env bash
set -euo pipefail

# validate.sh — Validate an accessibility audit report JSON.
# Usage: bash validate.sh <report.json>

REPORT="${1:?Usage: validate.sh <report.json>}"

if [[ ! -f "$REPORT" ]]; then
  echo "FAIL: report file not found: $REPORT" >&2
  exit 1
fi

# Must be valid JSON
if ! python3 -c "import json, sys; json.load(open(sys.argv[1]))" "$REPORT" 2>/dev/null; then
  echo "FAIL: report is not valid JSON" >&2
  exit 1
fi

python3 - "$REPORT" <<'PYEOF'
import json, sys

VALID_IMPACTS = {"critical", "serious", "moderate", "minor"}
VALID_WCAG = {
    "1.1.1","1.2.1","1.2.2","1.2.3","1.2.4","1.2.5",
    "1.3.1","1.3.2","1.3.3","1.3.4","1.3.5",
    "1.4.1","1.4.2","1.4.3","1.4.4","1.4.5","1.4.10","1.4.11","1.4.12","1.4.13",
    "2.1.1","2.1.2","2.1.4",
    "2.2.1","2.2.2",
    "2.3.1",
    "2.4.1","2.4.2","2.4.3","2.4.4","2.4.5","2.4.6","2.4.7",
    "2.5.1","2.5.2","2.5.3","2.5.4",
    "3.1.1","3.1.2",
    "3.2.1","3.2.2","3.2.3","3.2.4",
    "3.3.1","3.3.2","3.3.3","3.3.4",
    "4.1.1","4.1.2","4.1.3",
}

report = json.load(open(sys.argv[1]))
errors = []

if "violations" not in report:
    errors.append("Missing 'violations' key")
if "score" not in report:
    errors.append("Missing 'score' key")

for i, v in enumerate(report.get("violations", [])):
    if v.get("impact") not in VALID_IMPACTS:
        errors.append(f"violations[{i}]: invalid impact '{v.get('impact')}'")
    for crit in v.get("wcag_criteria", []):
        if crit not in VALID_WCAG:
            errors.append(f"violations[{i}]: unknown WCAG criterion '{crit}'")
    if not v.get("fix"):
        errors.append(f"violations[{i}]: empty fix suggestion")

if errors:
    print("FAIL:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    sys.exit(1)

print(f"OK: {len(report.get('violations',[]))} violations validated, score={report.get('score')}")
PYEOF
"""

_A11Y_HELPER = r'''#!/usr/bin/env python3
"""Accessibility static scanner.

Parses HTML/JSX/TSX files for common WCAG 2.1 Level A and AA violations.

Usage:
    python main_helper.py --mode static --path <file_or_dir>
    python main_helper.py --mode static --path src/components/

Output: JSON to stdout with violations and compliance score.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path


def find_files(path: str) -> list[str]:
    p = Path(path)
    if p.is_file():
        return [str(p)]
    exts = {".html", ".htm", ".jsx", ".tsx"}
    return sorted(str(f) for f in p.rglob("*") if f.suffix in exts)


def scan_file(filepath: str) -> list[dict]:
    violations = []
    with open(filepath, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    content = "".join(lines)

    # 1. Missing alt on <img> — WCAG 1.1.1
    for m in re.finditer(r"<img\b([^>]*)>", content, re.IGNORECASE):
        attrs = m.group(1)
        if not re.search(r'\balt\s*=', attrs):
            lineno = content[:m.start()].count("\n") + 1
            violations.append({
                "rule": "img-alt",
                "impact": "critical",
                "wcag_criteria": ["1.1.1"],
                "file": filepath,
                "line": lineno,
                "element": m.group(0)[:120],
                "fix": 'Add alt="descriptive text" to the <img> tag. Use alt="" only for decorative images.',
            })

    # 2. Missing label for <input> — WCAG 1.3.1
    for m in re.finditer(r"<input\b([^>]*)>", content, re.IGNORECASE):
        attrs = m.group(1)
        if re.search(r'type\s*=\s*["\']hidden["\']', attrs, re.IGNORECASE):
            continue
        has_label = bool(re.search(r'\baria-label\s*=', attrs) or re.search(r'\bid\s*=', attrs))
        if not has_label:
            lineno = content[:m.start()].count("\n") + 1
            violations.append({
                "rule": "input-label",
                "impact": "serious",
                "wcag_criteria": ["1.3.1"],
                "file": filepath,
                "line": lineno,
                "element": m.group(0)[:120],
                "fix": "Add an id and a corresponding <label for='id'>, or add aria-label.",
            })

    # 3. Empty <a> or <button> — WCAG 4.1.2
    for tag in ("a", "button"):
        for m in re.finditer(rf"<{tag}\b([^>]*)>\s*</{tag}>", content, re.IGNORECASE):
            attrs = m.group(1)
            if re.search(r'aria-label\s*=', attrs):
                continue
            lineno = content[:m.start()].count("\n") + 1
            violations.append({
                "rule": f"empty-{tag}",
                "impact": "serious",
                "wcag_criteria": ["4.1.2"],
                "file": filepath,
                "line": lineno,
                "element": m.group(0)[:120],
                "fix": f"Add visible text content or aria-label to the <{tag}> element.",
            })

    # 4. Missing lang on <html> — WCAG 3.1.1
    if re.search(r"<html\b", content, re.IGNORECASE):
        html_tag = re.search(r"<html\b([^>]*)>", content, re.IGNORECASE)
        if html_tag and not re.search(r'\blang\s*=', html_tag.group(1)):
            violations.append({
                "rule": "html-lang",
                "impact": "serious",
                "wcag_criteria": ["3.1.1"],
                "file": filepath,
                "line": 1,
                "element": html_tag.group(0)[:120],
                "fix": 'Add lang="en" (or appropriate language) to the <html> tag.',
            })

    # 5. Heading hierarchy — WCAG 1.3.1
    headings = [(int(m.group(1)), content[:m.start()].count("\n") + 1)
                for m in re.finditer(r"<h(\d)\b", content, re.IGNORECASE)]
    for i in range(1, len(headings)):
        prev_level, _ = headings[i - 1]
        curr_level, lineno = headings[i]
        if curr_level > prev_level + 1:
            violations.append({
                "rule": "heading-order",
                "impact": "moderate",
                "wcag_criteria": ["1.3.1"],
                "file": filepath,
                "line": lineno,
                "element": f"<h{curr_level}> after <h{prev_level}>",
                "fix": f"Don't skip heading levels. Use <h{prev_level + 1}> instead of <h{curr_level}>.",
            })

    # 6. Missing ARIA landmark (no <main>) — WCAG 1.3.1
    if re.search(r"<body\b", content, re.IGNORECASE):
        if not re.search(r'<main\b|role\s*=\s*["\']main["\']', content, re.IGNORECASE):
            violations.append({
                "rule": "landmark-main",
                "impact": "moderate",
                "wcag_criteria": ["1.3.1"],
                "file": filepath,
                "line": 1,
                "element": "<body>",
                "fix": "Wrap the primary content in a <main> element or add role='main'.",
            })

    return violations


def main() -> None:
    parser = argparse.ArgumentParser(description="Accessibility static scanner")
    parser.add_argument("--mode", choices=["static"], default="static")
    parser.add_argument("--path", required=True, help="File or directory to scan")
    args = parser.parse_args()

    files = find_files(args.path)
    if not files:
        print(json.dumps({"mode": args.mode, "violations": [], "files_scanned": 0, "score": 100.0}))
        return

    all_violations: list[dict] = []
    checks_per_file = 6  # number of rules we check
    total_checks = len(files) * checks_per_file

    for f in files:
        all_violations.extend(scan_file(f))

    passes = total_checks - len(all_violations)
    score = round(passes / total_checks * 100, 1) if total_checks > 0 else 100.0

    report = {
        "mode": args.mode,
        "files_scanned": len(files),
        "violations": all_violations,
        "passes": max(passes, 0),
        "total_checks": total_checks,
        "score": max(score, 0.0),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
'''

_A11Y_GUIDE = """\
# WCAG 2.1 Quick Reference for Auditing

## Principles

### 1. Perceivable
- **1.1.1 Non-text Content (A)**: All images need alt text. Decorative = `alt=""`.
  Informative = descriptive text. Functional (link/button) = describes destination/action.
- **1.3.1 Info and Relationships (A)**: Use semantic HTML. Headings (`h1`-`h6`) in
  order. Form inputs have labels. Tables have `<th>` and `scope`. Lists use `<ul>`/`<ol>`.
- **1.3.2 Meaningful Sequence (A)**: DOM order matches visual order.
- **1.4.3 Contrast Minimum (AA)**: Normal text 4.5:1. Large text (18pt/14pt bold) 3:1.
- **1.4.11 Non-text Contrast (AA)**: UI components and graphical objects need 3:1 contrast.

### 2. Operable
- **2.1.1 Keyboard (A)**: All functionality available via keyboard. No keyboard traps.
- **2.4.1 Bypass Blocks (A)**: Skip-to-main link or landmark regions.
- **2.4.2 Page Titled (A)**: Every page has a descriptive `<title>`.
- **2.4.3 Focus Order (A)**: Tab order follows logical reading order.
- **2.4.7 Focus Visible (AA)**: Keyboard focus indicator is visible.

### 3. Understandable
- **3.1.1 Language of Page (A)**: `<html lang="en">` (or appropriate language code).
- **3.2.1 On Focus (A)**: No unexpected context changes on focus.
- **3.3.1 Error Identification (A)**: Form errors described in text, not just color.
- **3.3.2 Labels or Instructions (A)**: Form inputs have visible labels.

### 4. Robust
- **4.1.1 Parsing (A)**: Valid HTML, unique IDs, complete start/end tags.
- **4.1.2 Name, Role, Value (A)**: Custom widgets have proper ARIA roles/states.
- **4.1.3 Status Messages (AA)**: Use `aria-live` for dynamic status updates.

## ARIA Patterns for Common Widgets

### Modal Dialog
```html
<div role="dialog" aria-modal="true" aria-labelledby="dialog-title">
  <h2 id="dialog-title">Title</h2>
  <!-- Focus trapped inside. Escape closes. Return focus to trigger. -->
</div>
```

### Tabs
```html
<div role="tablist" aria-label="Settings">
  <button role="tab" aria-selected="true" aria-controls="panel-1">Tab 1</button>
  <button role="tab" aria-selected="false" aria-controls="panel-2">Tab 2</button>
</div>
<div role="tabpanel" id="panel-1">Content 1</div>
```

### Combobox (Autocomplete)
```html
<label for="search">Search</label>
<input id="search" role="combobox" aria-expanded="false"
       aria-autocomplete="list" aria-controls="results">
<ul id="results" role="listbox" hidden>
  <li role="option">Option 1</li>
</ul>
```

## Contrast Requirements
| Text Type       | Min Ratio | WCAG Criterion |
|----------------|-----------|----------------|
| Normal text    | 4.5:1     | 1.4.3 (AA)     |
| Large text     | 3:1       | 1.4.3 (AA)     |
| UI components  | 3:1       | 1.4.11 (AA)    |
| Enhanced (AAA) | 7:1 / 4.5:1 | 1.4.6 (AAA) |
"""

# ---------------------------------------------------------------------------
# 12. Data Transformer
# ---------------------------------------------------------------------------
_DATA_XFORM_BODY = """\
## Quick Start
Detect the source format, parse into an intermediate representation, convert
to the target format, and validate that no records were lost. The helper script
handles the deterministic parsing and serialization.

## When to use this skill
Use when the user says "convert", "transform", "CSV to JSON", "JSON to YAML",
"XML to JSON", "flatten", "reshape data", "change format", or mentions any
pair of data formats (CSV, JSON, YAML, XML, TOML). Triggers on file extension
changes like "turn this .csv into .json", even if they don't explicitly say
"transform". NOT for database ETL, Spark jobs, or binary formats.

## Workflow

### Step 1: Identify source and target formats
Determine the source format from the file extension or user description.
If ambiguous, read the first few lines of the file to auto-detect.
Read `${CLAUDE_SKILL_DIR}/references/guide.md` for format specifications.

### Step 2: Run the transformer
```bash
python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py \\
    --source "<source_file>" \\
    --target-format <json|csv|yaml|xml|toml> \\
    --output "<output_file>"
```
The script infers the source format, parses it, converts to the target,
and writes the output plus a metadata JSON report.

### Step 3: Review the metadata report
Check the metadata for warnings (type coercion issues, null handling,
nested structure flattening). Address any data integrity concerns.

### Step 4: Validate the output
```bash
bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh "<source_file>" "<output_file>"
```
Confirms the output parses cleanly and record counts match the source.

## Examples

**Example 1: CSV to JSON**
Input: "convert users.csv to JSON"
Output: Reads the CSV, infers column types (string, int, float, bool),
produces a JSON array of objects. Metadata shows 1,247 records, 8 fields,
0 warnings. Output is properly indented JSON.

**Example 2: Nested JSON to flat CSV**
Input: "flatten this API response JSON into a CSV I can open in Excel"
Output: Flattens nested objects using dot notation (e.g., `address.city`),
explodes arrays into separate rows with an index column, handles nulls as
empty strings. Reports 3 nested fields flattened, 1 array exploded.

**Example 3: YAML config to TOML**
Input: "convert our docker-compose.yml to TOML format"
Output: Parses YAML preserving types (strings, ints, lists, nested maps),
serializes to TOML with proper table headers. Warns about YAML features
with no TOML equivalent (anchors, multi-line strings).

## Common mistakes to avoid
- Losing data during conversion — always verify record counts match
- Treating all CSV values as strings — infer types and preserve them
- Ignoring encoding — always read/write as UTF-8 and handle BOM
- Flattening arrays without preserving the relationship to the parent record
- Silently dropping null values instead of representing them in the target format

## Out of Scope
This skill does NOT:
- Handle binary formats (Parquet, Avro, Protocol Buffers)
- Connect to databases or APIs for extraction
- Process files larger than available memory (use streaming tools instead)
"""

_DATA_XFORM_VALIDATE = r"""#!/usr/bin/env bash
set -euo pipefail

# validate.sh — Validate a data transformation output.
# Usage: bash validate.sh <source_file> <output_file>

SOURCE="${1:?Usage: validate.sh <source_file> <output_file>}"
OUTPUT="${2:?Usage: validate.sh <source_file> <output_file>}"

if [[ ! -f "$SOURCE" ]]; then
  echo "FAIL: source file not found: $SOURCE" >&2
  exit 1
fi
if [[ ! -f "$OUTPUT" ]]; then
  echo "FAIL: output file not found: $OUTPUT" >&2
  exit 1
fi

python3 - "$SOURCE" "$OUTPUT" <<'PYEOF'
import csv
import json
import sys
from pathlib import Path

def count_records(filepath: str) -> int:
    ext = Path(filepath).suffix.lower()
    if ext == ".csv":
        with open(filepath, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return sum(1 for _ in reader)
    elif ext == ".json":
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return len(data)
            return 1
    elif ext in (".yaml", ".yml"):
        try:
            import yaml
            with open(filepath, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, list):
                    return len(data)
                return 1
        except ImportError:
            print("WARN: PyYAML not installed, skipping YAML record count", file=sys.stderr)
            return -1
    elif ext == ".xml":
        import xml.etree.ElementTree as ET
        tree = ET.parse(filepath)
        root = tree.getroot()
        return len(root)
    elif ext == ".toml":
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        with open(filepath, "rb") as f:
            data = tomllib.load(f)
            return len(data)
    else:
        print(f"WARN: unknown extension {ext}, skipping record count", file=sys.stderr)
        return -1

def validate_parseable(filepath: str) -> bool:
    ext = Path(filepath).suffix.lower()
    try:
        if ext == ".json":
            with open(filepath, encoding="utf-8") as f:
                json.load(f)
        elif ext == ".csv":
            with open(filepath, encoding="utf-8") as f:
                list(csv.DictReader(f))
        elif ext in (".yaml", ".yml"):
            import yaml
            with open(filepath, encoding="utf-8") as f:
                yaml.safe_load(f)
        elif ext == ".xml":
            import xml.etree.ElementTree as ET
            ET.parse(filepath)
        elif ext == ".toml":
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib
            with open(filepath, "rb") as f:
                tomllib.load(f)
        else:
            print(f"WARN: cannot validate {ext} format", file=sys.stderr)
            return True
        return True
    except Exception as e:
        print(f"FAIL: output file is not valid {ext}: {e}", file=sys.stderr)
        return False

source, output = sys.argv[1], sys.argv[2]

if not validate_parseable(output):
    sys.exit(1)

src_count = count_records(source)
out_count = count_records(output)

if src_count >= 0 and out_count >= 0 and src_count != out_count:
    print(f"WARN: record count mismatch: source={src_count}, output={out_count}", file=sys.stderr)

print(f"OK: output is valid, source_records={src_count}, output_records={out_count}")
PYEOF
"""

_DATA_XFORM_HELPER = r'''#!/usr/bin/env python3
"""Data format transformer.

Converts between CSV, JSON, YAML, XML, and TOML formats.

Usage:
    python main_helper.py --source data.csv --target-format json --output data.json
    python main_helper.py --source config.yaml --target-format toml --output config.toml
"""
import argparse
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET
from io import StringIO
from pathlib import Path

FORMAT_MAP = {
    ".csv": "csv", ".json": "json",
    ".yaml": "yaml", ".yml": "yaml",
    ".xml": "xml", ".toml": "toml",
}


def detect_format(filepath: str) -> str:
    ext = Path(filepath).suffix.lower()
    fmt = FORMAT_MAP.get(ext)
    if not fmt:
        raise ValueError(f"Cannot detect format from extension: {ext}")
    return fmt


def infer_type(value: str):
    """Try to coerce a string value to a richer Python type."""
    if value == "":
        return None
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def read_source(filepath: str, fmt: str) -> list[dict]:
    """Parse source file into a list of dicts."""
    if fmt == "csv":
        with open(filepath, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            return [
                {k: infer_type(v) for k, v in row.items()}
                for row in reader
            ]
    elif fmt == "json":
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return [data]
    elif fmt == "yaml":
        import yaml
        with open(filepath, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, list):
                return data
            return [data]
    elif fmt == "xml":
        tree = ET.parse(filepath)
        root = tree.getroot()
        records = []
        for child in root:
            record = dict(child.attrib)
            for sub in child:
                record[sub.tag] = sub.text
            records.append(record)
        return records
    elif fmt == "toml":
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        with open(filepath, "rb") as f:
            data = tomllib.load(f)
            if isinstance(data, list):
                return data
            return [data]
    raise ValueError(f"Unsupported source format: {fmt}")


def flatten_record(record: dict, prefix: str = "") -> dict:
    """Flatten nested dicts using dot notation."""
    flat = {}
    for key, value in record.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(flatten_record(value, full_key))
        elif isinstance(value, list):
            flat[full_key] = json.dumps(value)
        else:
            flat[full_key] = value
    return flat


def write_target(records: list[dict], filepath: str, fmt: str) -> dict:
    """Write records to target format. Returns metadata."""
    warnings = []

    if fmt == "csv":
        # Flatten nested records for CSV
        flat_records = [flatten_record(r) for r in records]
        if flat_records:
            fieldnames = list(dict.fromkeys(k for r in flat_records for k in r))
        else:
            fieldnames = []
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(flat_records)

    elif fmt == "json":
        data = records if len(records) != 1 else records[0]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)

    elif fmt == "yaml":
        import yaml
        data = records if len(records) != 1 else records[0]
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    elif fmt == "xml":
        root = ET.Element("root")
        for i, record in enumerate(records):
            item = ET.SubElement(root, "item")
            for key, value in record.items():
                child = ET.SubElement(item, key.replace(".", "_"))
                child.text = str(value) if value is not None else ""
            item.set("index", str(i))
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(filepath, encoding="unicode", xml_declaration=True)

    elif fmt == "toml":
        try:
            import tomli_w
        except ImportError:
            warnings.append("tomli_w not installed; falling back to manual TOML")
            with open(filepath, "w", encoding="utf-8") as f:
                for record in records:
                    for k, v in record.items():
                        if isinstance(v, str):
                            f.write(f'{k} = "{v}"\n')
                        elif isinstance(v, bool):
                            f.write(f"{k} = {str(v).lower()}\n")
                        elif v is None:
                            f.write(f'# {k} = <null>\n')
                        else:
                            f.write(f"{k} = {v}\n")
                    f.write("\n")
        else:
            data = records if len(records) != 1 else records[0]
            if isinstance(data, list):
                data = {"items": data}
                warnings.append("Wrapped list in {items: [...]} for TOML compatibility")
            with open(filepath, "wb") as f:
                tomli_w.dump(data, f)

    return {"warnings": warnings}


def main() -> None:
    parser = argparse.ArgumentParser(description="Data format transformer")
    parser.add_argument("--source", required=True, help="Source file path")
    parser.add_argument("--source-format", help="Override source format detection")
    parser.add_argument("--target-format", required=True,
                        choices=["csv", "json", "yaml", "xml", "toml"])
    parser.add_argument("--output", required=True, help="Output file path")
    args = parser.parse_args()

    src_fmt = args.source_format or detect_format(args.source)
    records = read_source(args.source, src_fmt)
    meta = write_target(records, args.output, args.target_format)

    # Infer schema from first record
    schema = []
    if records:
        for key, value in records[0].items():
            schema.append({"name": key, "type": type(value).__name__})

    metadata = {
        "source_format": src_fmt,
        "target_format": args.target_format,
        "record_count": len(records),
        "schema": schema,
        "warnings": meta.get("warnings", []),
    }
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
'''

_DATA_XFORM_GUIDE = """\
# Data Format Transformation Guide

## Format Specifications

### CSV (RFC 4180)
- Fields separated by commas, records by CRLF (or LF)
- Fields containing commas, double-quotes, or newlines must be quoted
- Double-quotes in fields escaped as two double-quotes: `""`
- First row is typically headers
- Encoding: UTF-8 preferred; watch for BOM (`\\xEF\\xBB\\xBF`)

### JSON (RFC 8259)
- UTF-8 encoding required for interchange
- Types: string, number, boolean, null, object, array
- No trailing commas, no comments
- Keys must be strings (double-quoted)

### YAML 1.2
- Superset of JSON
- Indentation-based nesting (spaces only, no tabs)
- Gotchas: `yes`/`no` parsed as booleans, `1.0` as float
- Anchors and aliases (`&anchor` / `*alias`) for dedup
- Multi-line strings: `|` (literal), `>` (folded)

### XML 1.0
- Tree structure with elements, attributes, text nodes
- Requires single root element
- Attributes are unordered; elements are ordered
- CDATA for literal text: `<![CDATA[ raw content ]]>`
- Namespaces: `xmlns:prefix="uri"`

### TOML 1.0
- Key-value pairs with typed values
- Tables (sections): `[table]`, `[[array-of-tables]]`
- No null type — omit key or use empty string
- Datetime support built in
- Cannot represent heterogeneous arrays

## Type Coercion Rules
| Source Value  | Inferred Type | Notes                           |
|--------------|---------------|---------------------------------|
| `"true"`     | bool          | Case-insensitive in YAML        |
| `"123"`      | int           | No leading zeros (octal in YAML)|
| `"12.5"`     | float         | Locale-independent (always `.`) |
| `""`         | null          | Depends on context              |
| `"2024-01-15"` | string     | Unless target has date type     |

## Nested-to-Flat Mapping
- **Dot notation**: `address.city` -> column name `address.city`
- **Underscore**: `address.city` -> column name `address_city`
- **Array handling**: Explode into rows or JSON-encode in cell
"""

# ---------------------------------------------------------------------------
# 13. Regex Builder
# ---------------------------------------------------------------------------
_REGEX_BODY = """\
## Quick Start
Take a natural-language description of a pattern (or an existing regex to
explain), build the regex, test it against examples, and return the pattern
with a plain-English explanation of every component.

## When to use this skill
Use when the user says "regex", "regular expression", "pattern match",
"find strings that match", "extract from text", "validate format", or
describes a string pattern they need to match. Triggers on "parse this log
line", "validate email format", or "capture the version number", even if
they don't mention regex explicitly. NOT for full text search engines or NLP.

## Workflow

### Step 1: Clarify requirements
Determine: what to match, what to capture (groups), what to reject, and
the target dialect (Python, JavaScript, PCRE, RE2). Default to Python.
Read `${CLAUDE_SKILL_DIR}/references/guide.md` for dialect differences.

### Step 2: Build and test the pattern
```bash
python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py \\
    --mode build \\
    --description "<natural language description>" \\
    --positive "example1" "example2" \\
    --negative "non-match1" "non-match2" \\
    --dialect python
```
The script returns the pattern and test results.

### Step 3: Validate the pattern
```bash
bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh "<pattern>" \\
    --positive "example1" "example2" \\
    --negative "non-match1"
```
Confirms the pattern compiles, matches positives, rejects negatives, and
does not exhibit catastrophic backtracking.

### Step 4: Explain the pattern
If the user has an existing regex to understand:
```bash
python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py \\
    --mode explain \\
    --pattern "<regex>"
```

## Examples

**Example 1: Email validation**
Input: "build a regex to validate email addresses"
Output: Pattern `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$` with
explanation of each component. Tests against `user@example.com` (match),
`user@.com` (no match), `user+tag@sub.domain.co.uk` (match).

**Example 2: Semantic version extraction**
Input: "extract semver versions like v1.2.3 or 2.0.0-beta.1 from text"
Output: Pattern with named groups `(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)(?:-(?P<pre>[\\w.]+))?`
and captures tested against `v1.2.3`, `0.1.0-alpha`, `2.0.0-beta.1+build.42`.

**Example 3: Explain an existing regex**
Input: "what does this regex do? `(?<=\\$)\\d{1,3}(?:,\\d{3})*(?:\\.\\d{2})?`"
Output: Decomposes into: lookbehind for `$`, 1-3 digits, optional comma-separated
thousands groups, optional decimal with exactly 2 digits. Matches US currency
amounts like `$1,234.56` (captures `1,234.56`).

## Common mistakes to avoid
- Forgetting to escape dots (`.` matches any character, `\\.` matches a literal dot)
- Using greedy `.*` when `.*?` (non-greedy) or `[^X]*` (negated class) is correct
- Catastrophic backtracking from nested quantifiers like `(a+)+b`
- Assuming `\\b` and lookaheads work identically across dialects (RE2 has no lookaheads)
- Testing only positive matches and not verifying negatives are rejected

## Out of Scope
This skill does NOT:
- Build parsers for complex grammars (use a proper parser generator)
- Handle binary pattern matching
- Replace full NLP for fuzzy text matching
"""

_REGEX_VALIDATE = r"""#!/usr/bin/env bash
set -euo pipefail

# validate.sh — Validate a regex pattern against positive and negative examples.
# Usage: bash validate.sh "<pattern>" --positive "ex1" "ex2" --negative "nex1"

PATTERN="${1:?Usage: validate.sh <pattern> [--positive ...] [--negative ...]}"
shift

POSITIVES=()
NEGATIVES=()
MODE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --positive) MODE="pos"; shift ;;
    --negative) MODE="neg"; shift ;;
    *)
      if [[ "$MODE" == "pos" ]]; then
        POSITIVES+=("$1")
      elif [[ "$MODE" == "neg" ]]; then
        NEGATIVES+=("$1")
      fi
      shift
      ;;
  esac
done

python3 - "$PATTERN" "${POSITIVES[@]+"${POSITIVES[@]}"}" "---SEP---" "${NEGATIVES[@]+"${NEGATIVES[@]}"}" <<'PYEOF'
import re
import sys

args = sys.argv[1:]
pattern = args[0]
rest = args[1:]

# Split on separator
if "---SEP---" in rest:
    sep_idx = rest.index("---SEP---")
    positives = rest[:sep_idx]
    negatives = rest[sep_idx + 1:]
else:
    positives = rest
    negatives = []

errors = []

# 1. Compile check
try:
    compiled = re.compile(pattern)
except re.error as e:
    print(f"FAIL: pattern does not compile: {e}", file=sys.stderr)
    sys.exit(1)

# 2. Positive matches
for s in positives:
    if not compiled.search(s):
        errors.append(f"FAIL: positive example not matched: '{s}'")

# 3. Negative matches
for s in negatives:
    if compiled.search(s):
        errors.append(f"FAIL: negative example incorrectly matched: '{s}'")

# 4. Backtracking check — test with a pathological input
import signal

def timeout_handler(signum, frame):
    raise TimeoutError()

try:
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(2)  # 2 second timeout
    compiled.search("a" * 100)
    signal.alarm(0)
except TimeoutError:
    errors.append("FAIL: possible catastrophic backtracking detected")
except (ValueError, OSError):
    pass  # signal not available on some platforms

if errors:
    for e in errors:
        print(e, file=sys.stderr)
    sys.exit(1)

print(f"OK: pattern compiles, {len(positives)} positives matched, {len(negatives)} negatives rejected")
PYEOF
"""

_REGEX_HELPER = r'''#!/usr/bin/env python3
"""Regex pattern builder, tester, and explainer.

Usage:
    python main_helper.py --mode build --description "email addresses" \
        --positive "user@example.com" --negative "not-an-email" --dialect python
    python main_helper.py --mode test --pattern "\\d+" --positive "abc123" --negative "abc"
    python main_helper.py --mode explain --pattern "(?<=\\$)\\d+"
"""
import argparse
import json
import re
import sys

COMMON_PATTERNS = {
    "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    "url": r"https?://[^\s/$.?#].[^\s]*",
    "ipv4": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "semver": r"v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:-(?P<pre>[\w.]+))?(?:\+(?P<build>[\w.]+))?",
    "date_iso": r"\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])",
    "phone_us": r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
    "hex_color": r"#(?:[0-9a-fA-F]{3}){1,2}\b",
    "uuid": r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
}

COMPONENT_DESCRIPTIONS = {
    r"\d": "any digit (0-9)",
    r"\w": "word character (letter, digit, underscore)",
    r"\s": "whitespace (space, tab, newline)",
    r"\b": "word boundary",
    r"^": "start of string",
    r"$": "end of string",
    r".": "any character except newline",
    r"*": "zero or more of preceding",
    r"+": "one or more of preceding",
    r"?": "zero or one of preceding (optional)",
}


def explain_pattern(pattern: str) -> list[dict]:
    """Decompose a regex into named components with descriptions."""
    components = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]

        # Named groups
        if pattern[i:].startswith("(?P<"):
            end = pattern.index(">", i)
            name = pattern[i+4:end]
            # Find matching paren
            depth = 1
            j = end + 1
            while j < len(pattern) and depth > 0:
                if pattern[j] == "(" and pattern[j-1:j] != "\\":
                    depth += 1
                elif pattern[j] == ")" and pattern[j-1:j] != "\\":
                    depth -= 1
                j += 1
            inner = pattern[end+1:j-1]
            components.append({
                "component": pattern[i:j],
                "description": f"Named capture group '{name}' matching: {inner}",
            })
            i = j
            continue

        # Lookahead/lookbehind
        if pattern[i:].startswith("(?="):
            components.append({"component": "(?=...)", "description": "Positive lookahead"})
        elif pattern[i:].startswith("(?!"):
            components.append({"component": "(?!...)", "description": "Negative lookahead"})
        elif pattern[i:].startswith("(?<="):
            components.append({"component": "(?<=...)", "description": "Positive lookbehind"})
        elif pattern[i:].startswith("(?<!"):
            components.append({"component": "(?<!...)", "description": "Negative lookbehind"})

        # Escaped characters
        if ch == "\\" and i + 1 < len(pattern):
            esc = pattern[i:i+2]
            desc = COMPONENT_DESCRIPTIONS.get(esc, f"Literal '{pattern[i+1]}'")
            components.append({"component": esc, "description": desc})
            i += 2
            continue

        # Character classes
        if ch == "[":
            end = pattern.index("]", i + 1) + 1
            cls = pattern[i:end]
            components.append({
                "component": cls,
                "description": f"Character class: one of {cls}",
            })
            i = end
            continue

        # Quantifiers
        if ch == "{":
            end = pattern.index("}", i) + 1
            quant = pattern[i:end]
            components.append({
                "component": quant,
                "description": f"Quantifier: repeat {quant}",
            })
            i = end
            continue

        # Simple characters
        desc = COMPONENT_DESCRIPTIONS.get(ch, f"Literal '{ch}'")
        components.append({"component": ch, "description": desc})
        i += 1

    return components


def test_pattern(pattern: str, positives: list[str], negatives: list[str]) -> dict:
    """Test a pattern against example strings."""
    compiled = re.compile(pattern)
    results = []

    for s in positives:
        m = compiled.search(s)
        results.append({
            "input": s,
            "expected": "match",
            "matched": m is not None,
            "captures": list(m.groups()) if m else [],
            "pass": m is not None,
        })

    for s in negatives:
        m = compiled.search(s)
        results.append({
            "input": s,
            "expected": "no_match",
            "matched": m is not None,
            "captures": list(m.groups()) if m else [],
            "pass": m is None,
        })

    all_pass = all(r["pass"] for r in results)
    return {"pattern": pattern, "test_results": results, "all_pass": all_pass}


def main() -> None:
    parser = argparse.ArgumentParser(description="Regex pattern builder")
    parser.add_argument("--mode", required=True, choices=["build", "test", "explain"])
    parser.add_argument("--pattern", help="Existing pattern (for test/explain)")
    parser.add_argument("--description", help="Natural language description (for build)")
    parser.add_argument("--positive", nargs="*", default=[], help="Should-match examples")
    parser.add_argument("--negative", nargs="*", default=[], help="Should-not-match examples")
    parser.add_argument("--dialect", default="python", choices=["python", "javascript", "pcre", "re2"])
    args = parser.parse_args()

    if args.mode == "explain":
        if not args.pattern:
            print("Error: --pattern required for explain mode", file=sys.stderr)
            sys.exit(1)
        components = explain_pattern(args.pattern)
        result = {"pattern": args.pattern, "explanation": components}
        print(json.dumps(result, indent=2))

    elif args.mode == "test":
        if not args.pattern:
            print("Error: --pattern required for test mode", file=sys.stderr)
            sys.exit(1)
        result = test_pattern(args.pattern, args.positive, args.negative)
        print(json.dumps(result, indent=2))

    elif args.mode == "build":
        # Check common patterns first
        desc_lower = (args.description or "").lower()
        pattern = None
        for key, pat in COMMON_PATTERNS.items():
            if key in desc_lower:
                pattern = pat
                break

        if not pattern:
            # Return a placeholder that Claude will refine
            pattern = ".*"
            print(json.dumps({
                "pattern": pattern,
                "note": "Generic placeholder. Refine based on specific requirements.",
                "dialect": args.dialect,
                "common_patterns_available": list(COMMON_PATTERNS.keys()),
            }, indent=2))
            return

        result = test_pattern(pattern, args.positive, args.negative)
        result["dialect"] = args.dialect
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
'''

_REGEX_GUIDE = """\
# Regex Quick Reference

## Syntax Cheat Sheet

### Character Classes
| Pattern   | Matches                                    |
|-----------|-------------------------------------------|
| `.`       | Any character except newline               |
| `\\d`     | Digit `[0-9]`                              |
| `\\D`     | Non-digit                                  |
| `\\w`     | Word char `[a-zA-Z0-9_]`                  |
| `\\W`     | Non-word character                         |
| `\\s`     | Whitespace `[ \\t\\n\\r\\f\\v]`           |
| `\\S`     | Non-whitespace                             |
| `[abc]`   | One of a, b, c                             |
| `[^abc]`  | Not a, b, or c                             |
| `[a-z]`   | Range: a through z                         |

### Quantifiers
| Pattern   | Meaning                 |
|-----------|------------------------|
| `*`       | 0 or more (greedy)     |
| `+`       | 1 or more (greedy)     |
| `?`       | 0 or 1 (optional)      |
| `{3}`     | Exactly 3              |
| `{2,5}`   | 2 to 5                 |
| `{2,}`    | 2 or more              |
| `*?`      | 0 or more (non-greedy) |
| `+?`      | 1 or more (non-greedy) |

### Anchors & Boundaries
| Pattern  | Meaning                   |
|----------|--------------------------|
| `^`      | Start of string/line     |
| `$`      | End of string/line       |
| `\\b`    | Word boundary            |
| `\\B`    | Non-word boundary        |

### Groups & Lookaround
| Pattern         | Meaning                       |
|----------------|-------------------------------|
| `(abc)`        | Capturing group               |
| `(?:abc)`      | Non-capturing group           |
| `(?P<n>abc)`   | Named group (Python)          |
| `(?<n>abc)`    | Named group (JS/PCRE)         |
| `(?=abc)`      | Positive lookahead            |
| `(?!abc)`      | Negative lookahead            |
| `(?<=abc)`     | Positive lookbehind           |
| `(?<!abc)`     | Negative lookbehind           |

## Dialect Differences

| Feature              | Python | JavaScript | PCRE | RE2  |
|---------------------|--------|------------|------|------|
| Named groups         | `(?P<n>)` | `(?<n>)` | `(?P<n>)` or `(?<n>)` | `(?P<n>)` |
| Lookbehind (variable)| Yes    | ES2018+    | Yes  | No   |
| Atomic groups        | No     | No         | Yes  | No   |
| Possessive quantifiers| No    | No         | Yes  | No   |
| Unicode properties   | `\\p{L}` (3.8+) | `\\p{L}` (with `u`) | `\\p{L}` | `\\p{L}` |
| Backreferences       | Yes    | Yes        | Yes  | No   |

## Avoiding Catastrophic Backtracking
- Never nest quantifiers: `(a+)+` is dangerous
- Prefer `[^X]*X` over `.*X` (fails faster)
- Use atomic groups or possessive quantifiers (PCRE) where available
- Test with pathological inputs: `"a" * 30 + "b"` against `(a+)+b`

## Common Patterns Library

### Email (simplified)
`^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$`

### URL
`https?://[^\\s/$.?#].[^\\s]*`

### IPv4
`\\b(?:(?:25[0-5]|2[0-4]\\d|[01]?\\d\\d?)\\.){3}(?:25[0-5]|2[0-4]\\d|[01]?\\d\\d?)\\b`

### Semantic Version
`v?(?P<major>\\d+)\\.(?P<minor>\\d+)\\.(?P<patch>\\d+)(?:-(?P<pre>[\\w.]+))?`

### ISO Date
`\\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\\d|3[01])`
"""

# ---------------------------------------------------------------------------
# 14. Error Handler
# ---------------------------------------------------------------------------
_ERROR_HANDLER_BODY = """\
## Quick Start
Scan source code for unhandled exceptions, bare catch blocks, and missing
structured logging. Generate proper error handling with specific exception
types, contextual log messages, and retry logic where appropriate.

## When to use this skill
Use when the user says "error handling", "try catch", "exception", "logging",
"unhandled error", "bare except", "retry logic", "circuit breaker",
"structured logging", or "observability". Triggers on "this crashes sometimes",
"add proper error handling", or "why does this silently fail", even if they
don't explicitly ask for structured logging. NOT for debugging runtime errors
or performance profiling.

## Workflow

### Step 1: Scan for error handling issues
```bash
python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py \\
    --path "<source_file>" \\
    --language <python|javascript|typescript>
```
The script identifies: bare except/catch blocks, unhandled async operations,
missing finally/cleanup, console.log instead of structured logger, and
functions that throw but callers don't handle.

### Step 2: Review findings and prioritize
Read `${CLAUDE_SKILL_DIR}/references/guide.md` for language-specific best
practices. Prioritize by severity:
- Critical: unhandled exceptions that crash the process
- Serious: bare except blocks that swallow errors silently
- Moderate: missing structured logging (using print/console.log)
- Minor: missing context in error messages

### Step 3: Generate fixes
For each finding, generate the corrected code:
- Replace bare except with specific exception types
- Add structured log messages with context (request_id, operation, input)
- Add retry logic with exponential backoff for transient failures
- Add proper cleanup in finally blocks

### Step 4: Validate the generated code
```bash
bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh "<report_json>"
```
Ensures generated code has valid syntax, no bare catch blocks, structured
log format, and appropriate log levels.

## Examples

**Example 1: Python API endpoint with bare except**
Input: "add proper error handling to this Flask endpoint"
Output: Identifies bare `except:` on the DB query, replaces with
`except sqlalchemy.exc.OperationalError as e:` with structured logging
`logger.error("db_query_failed", exc_info=e, request_id=g.request_id,
table="users")`, adds retry with 3 attempts and exponential backoff for
transient DB errors.

**Example 2: JavaScript async chain without error handling**
Input: "this function crashes sometimes but I don't know why"
Output: Finds 3 unhandled `await` calls, wraps in try/catch with specific
error types (TypeError, NetworkError), adds structured JSON logging with
correlation ID, adds graceful degradation returning cached data on failure.

**Example 3: Missing cleanup in file operations**
Input: "add error handling to this file processing script"
Output: Adds try/finally with proper file handle cleanup, catches specific
IOError/PermissionError, logs structured messages with file path and
operation context, adds temp file cleanup on failure.

## Common mistakes to avoid
- Bare `except:` or `catch(e)` that swallows all errors including
  KeyboardInterrupt/SystemExit
- Error messages without context: "An error occurred" is useless in production
- Using `print()` or `console.log()` instead of a structured logger
- Catching too broadly: catch specific exceptions at the call site
- Missing cleanup: always use finally/with/using for resource management
- Retry without backoff: hammering a failing service makes things worse

## Out of Scope
This skill does NOT:
- Debug runtime errors (use a debugger or systematic-debugging skill)
- Profile performance (use profiling tools)
- Set up monitoring infrastructure (Sentry, Datadog, etc.)
"""

_ERROR_HANDLER_VALIDATE = r"""#!/usr/bin/env bash
set -euo pipefail

# validate.sh — Validate an error handling analysis report.
# Usage: bash validate.sh <report.json>

REPORT="${1:?Usage: validate.sh <report.json>}"

if [[ ! -f "$REPORT" ]]; then
  echo "FAIL: report file not found: $REPORT" >&2
  exit 1
fi

if ! python3 -c "import json, sys; json.load(open(sys.argv[1]))" "$REPORT" 2>/dev/null; then
  echo "FAIL: report is not valid JSON" >&2
  exit 1
fi

python3 - "$REPORT" <<'PYEOF'
import json
import re
import sys

VALID_SEVERITIES = {"critical", "serious", "moderate", "minor"}
VALID_FINDING_TYPES = {
    "bare_except", "bare_catch", "unhandled_async", "missing_finally",
    "console_log", "print_debug", "missing_context", "broad_catch",
    "no_retry", "swallowed_error",
}
VALID_LOG_LEVELS = {"debug", "info", "warning", "warn", "error", "critical", "fatal"}

report = json.load(open(sys.argv[1]))
errors = []

if "findings" not in report:
    errors.append("Missing 'findings' key")

for i, f in enumerate(report.get("findings", [])):
    if f.get("severity") not in VALID_SEVERITIES:
        errors.append(f"findings[{i}]: invalid severity '{f.get('severity')}'")

    if not f.get("suggestion"):
        errors.append(f"findings[{i}]: empty suggestion")

    # Check generated code doesn't have bare except/catch
    code = f.get("generated_code", "")
    if re.search(r'\bexcept\s*:', code):
        errors.append(f"findings[{i}]: generated code contains bare 'except:'")
    if re.search(r'\bcatch\s*\(\s*\w+\s*\)\s*\{', code) and "Error" not in code:
        errors.append(f"findings[{i}]: generated catch block may be too broad")

    # Check log messages have context
    if "log" in code.lower() and "error occurred" in code.lower():
        errors.append(f"findings[{i}]: log message lacks context (generic 'error occurred')")

coverage = report.get("error_coverage", {})
if coverage:
    handled = coverage.get("handled", 0)
    total = coverage.get("total", 0)
    if total > 0:
        pct = round(handled / total * 100, 1)
        if pct != coverage.get("percentage", -1):
            errors.append(f"error_coverage.percentage mismatch: calculated {pct} vs reported {coverage.get('percentage')}")

if errors:
    print("FAIL:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    sys.exit(1)

print(f"OK: {len(report.get('findings', []))} findings validated")
PYEOF
"""

_ERROR_HANDLER_HELPER = r'''#!/usr/bin/env python3
"""Error handling and logging analyzer.

Scans source code for error handling anti-patterns and generates fixes.

Usage:
    python main_helper.py --path app.py --language python
    python main_helper.py --path server.js --language javascript
"""
import argparse
import json
import re
import sys
from pathlib import Path


def scan_python(content: str, filepath: str) -> list[dict]:
    """Scan Python code for error handling issues."""
    findings = []
    lines = content.split("\n")

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Bare except
        if re.match(r"except\s*:", stripped):
            findings.append({
                "file": filepath,
                "line": i,
                "type": "bare_except",
                "severity": "serious",
                "suggestion": "Catch specific exceptions (e.g., except ValueError as e:)",
                "generated_code": (
                    f"except (ValueError, TypeError) as e:\n"
                    f'    logger.error("operation_failed", exc_info=e, '
                    f'operation="<describe>", input_data=str(locals())[:200])\n'
                    f"    raise"
                ),
            })

        # Broad except Exception
        if re.match(r"except\s+Exception\s*(as\s+\w+)?:", stripped):
            findings.append({
                "file": filepath,
                "line": i,
                "type": "broad_catch",
                "severity": "moderate",
                "suggestion": "Catch more specific exception types when possible",
                "generated_code": "",
            })

        # print() used for error reporting
        if re.match(r'print\s*\(\s*f?["\'].*error', stripped, re.IGNORECASE):
            findings.append({
                "file": filepath,
                "line": i,
                "type": "print_debug",
                "severity": "moderate",
                "suggestion": "Use structured logging instead of print()",
                "generated_code": (
                    'import logging\n'
                    'logger = logging.getLogger(__name__)\n'
                    'logger.error("descriptive_event_name", extra={"context_key": "value"})'
                ),
            })

        # Missing error handling on file open without with
        if re.match(r"\w+\s*=\s*open\(", stripped) and "with" not in stripped:
            findings.append({
                "file": filepath,
                "line": i,
                "type": "missing_finally",
                "severity": "serious",
                "suggestion": "Use 'with' statement for automatic resource cleanup",
                "generated_code": (
                    'with open(filepath, "r") as f:\n'
                    "    data = f.read()"
                ),
            })

    # Check for unhandled async operations
    for i, line in enumerate(lines, 1):
        if "await " in line:
            # Check if inside try block
            indent = len(line) - len(line.lstrip())
            in_try = False
            for j in range(i - 2, max(0, i - 20), -1):
                prev = lines[j]
                prev_indent = len(prev) - len(prev.lstrip())
                if prev_indent < indent and "try:" in prev.strip():
                    in_try = True
                    break
            if not in_try:
                findings.append({
                    "file": filepath,
                    "line": i,
                    "type": "unhandled_async",
                    "severity": "critical",
                    "suggestion": "Wrap await calls in try/except for proper async error handling",
                    "generated_code": (
                        "try:\n"
                        f"    {line.strip()}\n"
                        "except Exception as e:\n"
                        '    logger.error("async_operation_failed", exc_info=e)\n'
                        "    raise"
                    ),
                })

    return findings


def scan_javascript(content: str, filepath: str) -> list[dict]:
    """Scan JavaScript/TypeScript code for error handling issues."""
    findings = []
    lines = content.split("\n")

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Empty catch block
        if re.search(r"catch\s*\(\s*\w*\s*\)\s*\{\s*\}", stripped):
            findings.append({
                "file": filepath,
                "line": i,
                "type": "swallowed_error",
                "severity": "critical",
                "suggestion": "Never swallow errors silently. Log and re-throw or handle.",
                "generated_code": (
                    "catch (error) {\n"
                    '  logger.error("operation_failed", { error: error.message, stack: error.stack });\n'
                    "  throw error;\n"
                    "}"
                ),
            })

        # console.log for error reporting
        if re.match(r"console\.(log|error)\s*\(", stripped):
            findings.append({
                "file": filepath,
                "line": i,
                "type": "console_log",
                "severity": "moderate",
                "suggestion": "Use a structured logger (winston, pino) instead of console.log",
                "generated_code": (
                    'import pino from "pino";\n'
                    'const logger = pino();\n'
                    'logger.error({ err, operation: "describe", requestId }, "event_name");'
                ),
            })

        # Unhandled promise (.then without .catch)
        if ".then(" in stripped and ".catch(" not in stripped and "await" not in stripped:
            findings.append({
                "file": filepath,
                "line": i,
                "type": "unhandled_async",
                "severity": "critical",
                "suggestion": "Add .catch() handler or use async/await with try/catch",
                "generated_code": (
                    ".then((result) => {\n"
                    "  // handle result\n"
                    "})\n"
                    ".catch((error) => {\n"
                    '  logger.error({ err: error, operation: "describe" }, "promise_rejected");\n'
                    "});"
                ),
            })

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Error handling analyzer")
    parser.add_argument("--path", required=True, help="Source file to scan")
    parser.add_argument("--language", choices=["python", "javascript", "typescript"],
                        help="Override language detection")
    args = parser.parse_args()

    filepath = args.path
    content = Path(filepath).read_text(encoding="utf-8")

    lang = args.language
    if not lang:
        ext = Path(filepath).suffix
        lang = {".py": "python", ".js": "javascript", ".ts": "typescript",
                ".jsx": "javascript", ".tsx": "typescript"}.get(ext, "python")

    if lang == "python":
        findings = scan_python(content, filepath)
    else:
        findings = scan_javascript(content, filepath)

    handled = sum(1 for f in findings if f["generated_code"])
    total = len(findings)
    percentage = round(handled / total * 100, 1) if total > 0 else 100.0

    report = {
        "file": filepath,
        "language": lang,
        "findings": findings,
        "error_coverage": {
            "handled": handled,
            "total": total,
            "percentage": percentage,
        },
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
'''

_ERROR_HANDLER_GUIDE = """\
# Error Handling & Structured Logging Guide

## Python Error Handling

### Exception Hierarchy (catch specific, not broad)
```
BaseException
 +-- SystemExit          # Never catch
 +-- KeyboardInterrupt   # Never catch
 +-- GeneratorExit       # Never catch
 +-- Exception
      +-- ValueError     # Invalid argument value
      +-- TypeError      # Wrong type
      +-- KeyError       # Missing dict key
      +-- AttributeError # Missing attribute
      +-- IOError        # File I/O failure
      +-- ConnectionError # Network failure (retryable)
      +-- TimeoutError   # Operation timed out (retryable)
```

### Best Practices
- Catch specific exceptions at the call site, not `Exception`
- Use `except ValueError as e:` to capture the exception object
- Always include `exc_info=True` or pass the exception to the logger
- Use `finally` for cleanup (file handles, connections, temp files)
- Use context managers (`with`) for resource management
- Create custom exceptions for domain-specific errors

### Structured Logging (Python)
```python
import logging
import json

logger = logging.getLogger(__name__)

# JSON structured log
logger.error(
    "db_query_failed",
    extra={
        "request_id": request_id,
        "table": "users",
        "query_time_ms": elapsed,
        "error_type": type(e).__name__,
    },
    exc_info=e,
)
```

## JavaScript Error Handling

### Error Subclasses
```javascript
class AppError extends Error {
  constructor(message, { code, statusCode, context }) {
    super(message);
    this.name = "AppError";
    this.code = code;
    this.statusCode = statusCode;
    this.context = context;
  }
}

class NotFoundError extends AppError {
  constructor(resource, id) {
    super(`${resource} not found: ${id}`, {
      code: "NOT_FOUND", statusCode: 404,
      context: { resource, id },
    });
  }
}
```

### Async Error Handling
```javascript
// Always use try/catch with await
async function fetchUser(id) {
  try {
    const response = await fetch(`/api/users/${id}`);
    if (!response.ok) throw new AppError("fetch_failed", {
      code: "HTTP_ERROR", statusCode: response.status,
      context: { url: `/api/users/${id}` },
    });
    return await response.json();
  } catch (error) {
    logger.error({ err: error, userId: id }, "user_fetch_failed");
    throw error;
  }
}
```

## Retry Patterns

### Exponential Backoff with Jitter
```python
import random
import time

def retry_with_backoff(fn, max_retries=3, base_delay=1.0):
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except (ConnectionError, TimeoutError) as e:
            if attempt == max_retries:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            logger.warning("retry_attempt", extra={
                "attempt": attempt + 1, "max_retries": max_retries,
                "delay_seconds": round(delay, 2), "error": str(e),
            })
            time.sleep(delay)
```

### Circuit Breaker
States: CLOSED (normal) -> OPEN (failing) -> HALF-OPEN (testing)
- CLOSED: requests pass through, failures counted
- OPEN: requests fail fast, no backend calls (for cooldown period)
- HALF-OPEN: one test request allowed; success -> CLOSED, failure -> OPEN

## Log Levels
| Level    | When to use                                    |
|----------|-----------------------------------------------|
| DEBUG    | Internal state, variable values (dev only)    |
| INFO     | Normal operations: started, completed, config |
| WARNING  | Retries, deprecations, approaching limits     |
| ERROR    | Failed operations that need attention         |
| CRITICAL | System-wide failure, data corruption          |

## Structured Log Format (JSON)
Every log entry should include:
- `timestamp`: ISO 8601 with timezone
- `level`: log level
- `message`: event name (snake_case, not a sentence)
- `service`: service name
- `correlation_id`: request/trace ID for distributed tracing
- `context`: operation-specific data (user_id, resource, etc.)
"""

# ---------------------------------------------------------------------------
# 15. Terraform Module
# ---------------------------------------------------------------------------
_TERRAFORM_BODY = """\
## Quick Start
Generate a production-ready Terraform module with proper structure
(main.tf, variables.tf, outputs.tf, versions.tf), typed variables with
validation, pinned provider versions, and security-checked defaults.

## When to use this skill
Use when the user says "Terraform", "module", "HCL", ".tf files",
"infrastructure as code", "provision", "cloud resources", or asks to
"create an AWS/GCP/Azure resource". Triggers on "set up a VPC",
"create an S3 bucket", or "deploy to cloud", even if they don't
say "Terraform" explicitly. NOT for Pulumi, CDK, CloudFormation, or
Ansible.

## Workflow

### Step 1: Gather requirements
Determine the target provider (AWS, GCP, Azure), resource types needed,
naming conventions, and security requirements. Read
`${CLAUDE_SKILL_DIR}/references/guide.md` for provider-specific patterns.

### Step 2: Generate the module structure
```bash
python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py \\
    --module-name "<name>" \\
    --provider <aws|gcp|azure> \\
    --resources "vpc,subnet,security_group"
```
Generates the standard module files with typed variables, validation
blocks, and security defaults.

### Step 3: Review and customize
Review the generated files. Customize variable defaults, add additional
resources, and adjust security settings for the specific use case.

### Step 4: Validate the module
```bash
bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh "<module_directory>"
```
Checks HCL structure, variable descriptions, provider pinning, security
anti-patterns, and README completeness.

## Examples

**Example 1: AWS VPC with subnets**
Input: "create a Terraform module for a VPC with public and private subnets"
Output: Generates module with `aws_vpc`, `aws_subnet` (public + private per AZ),
`aws_internet_gateway`, `aws_nat_gateway`, `aws_route_table`. Variables for
CIDR block, AZ count, tags. Outputs for VPC ID, subnet IDs, route table IDs.

**Example 2: S3 bucket with encryption**
Input: "Terraform module for a secure S3 bucket"
Output: Generates `aws_s3_bucket` with `aws_s3_bucket_server_side_encryption_configuration`
(AES256 default), `aws_s3_bucket_versioning` enabled, `aws_s3_bucket_public_access_block`
blocking all public access, `aws_s3_bucket_logging`. Variables for bucket name,
KMS key ARN (optional), retention days.

**Example 3: GCP GKE cluster**
Input: "create a Terraform module for a GKE cluster"
Output: Generates `google_container_cluster` with private nodes,
`google_container_node_pool` with autoscaling, workload identity enabled,
network policy enabled. Variables for machine type, min/max nodes, k8s version.

## Common mistakes to avoid
- Hardcoding values that should be variables (region, account ID, names)
- Using `count` instead of `for_each` (count causes index-based recreation)
- Not pinning provider versions (`>= 0.0.0` means any version, including breaking)
- Missing `sensitive = true` on password/key variables
- Forgetting to add descriptions to all variables and outputs
- Creating public resources by default (S3, security groups, subnets)

## Out of Scope
This skill does NOT:
- Manage Terraform state backends (that's a root module concern)
- Write Terragrunt configurations
- Generate Pulumi, CDK, or CloudFormation templates
"""

_TERRAFORM_VALIDATE = r"""#!/usr/bin/env bash
set -euo pipefail

# validate.sh — Validate a Terraform module structure and conventions.
# Usage: bash validate.sh <module_directory>

MODULE_DIR="${1:?Usage: validate.sh <module_directory>}"

if [[ ! -d "$MODULE_DIR" ]]; then
  echo "FAIL: directory not found: $MODULE_DIR" >&2
  exit 1
fi

ERRORS=()

# Check required files
for f in main.tf variables.tf outputs.tf versions.tf; do
  if [[ ! -f "$MODULE_DIR/$f" ]]; then
    ERRORS+=("Missing required file: $f")
  fi
done

# Check all variables have descriptions
if [[ -f "$MODULE_DIR/variables.tf" ]]; then
  python3 - "$MODULE_DIR/variables.tf" <<'PYEOF'
import re
import sys

content = open(sys.argv[1]).read()
errors = []

# Find all variable blocks
var_blocks = re.finditer(
    r'variable\s+"(\w+)"\s*\{(.*?)\n\}',
    content, re.DOTALL
)

for m in var_blocks:
    name = m.group(1)
    body = m.group(2)
    if "description" not in body:
        errors.append(f"Variable '{name}' missing description")
    if "type" not in body:
        errors.append(f"Variable '{name}' missing type")
    # Check sensitive variables
    if any(kw in name.lower() for kw in ("password", "secret", "key", "token")):
        if "sensitive" not in body or "true" not in body:
            errors.append(f"Variable '{name}' should be marked sensitive = true")

for e in errors:
    print(f"WARN: {e}", file=sys.stderr)
if errors:
    sys.exit(1)
PYEOF
  if [[ $? -ne 0 ]]; then
    ERRORS+=("variables.tf has issues (see above)")
  fi
fi

# Check outputs have descriptions
if [[ -f "$MODULE_DIR/outputs.tf" ]]; then
  if ! grep -q "description" "$MODULE_DIR/outputs.tf" 2>/dev/null; then
    if grep -q "output" "$MODULE_DIR/outputs.tf" 2>/dev/null; then
      ERRORS+=("outputs.tf: some outputs may be missing descriptions")
    fi
  fi
fi

# Check provider version pinning
if [[ -f "$MODULE_DIR/versions.tf" ]]; then
  if grep -q '>= 0.0.0' "$MODULE_DIR/versions.tf" 2>/dev/null; then
    ERRORS+=("versions.tf: provider version not properly pinned (found >= 0.0.0)")
  fi
  if ! grep -q 'required_providers' "$MODULE_DIR/versions.tf" 2>/dev/null; then
    ERRORS+=("versions.tf: missing required_providers block")
  fi
fi

# Check for hardcoded AWS account IDs or regions
for tf_file in "$MODULE_DIR"/*.tf; do
  [[ -f "$tf_file" ]] || continue
  if grep -qE '[0-9]{12}' "$tf_file" 2>/dev/null; then
    ERRORS+=("$(basename "$tf_file"): possible hardcoded AWS account ID")
  fi
done

# Check for security anti-patterns
if [[ -f "$MODULE_DIR/main.tf" ]]; then
  if grep -qi 'cidr_blocks.*0\.0\.0\.0/0' "$MODULE_DIR/main.tf" 2>/dev/null; then
    ERRORS+=("main.tf: found 0.0.0.0/0 CIDR — ensure this is intentional")
  fi
fi

if [[ ${#ERRORS[@]} -gt 0 ]]; then
  echo "FAIL: ${#ERRORS[@]} issue(s) found:" >&2
  for e in "${ERRORS[@]}"; do
    echo "  - $e" >&2
  done
  exit 1
fi

echo "OK: module structure valid"
"""

_TERRAFORM_HELPER = r'''#!/usr/bin/env python3
# Terraform module generator.
#
# Generates production-ready Terraform module files.
#
# Usage:
#     python main_helper.py --module-name vpc --provider aws --resources "vpc,subnet,igw"
#     python main_helper.py --module-name storage --provider aws --resources "s3_bucket"
import argparse
import json
import os
import sys
from pathlib import Path

# Resource templates by provider
AWS_RESOURCES = {
    "vpc": {
        "main": """resource "aws_vpc" "this" {
  cidr_block           = var.cidr_block
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(var.tags, {
    Name = var.name
  })
}""",
        "variables": [
            ('cidr_block', 'string', '"10.0.0.0/16"', 'CIDR block for the VPC'),
            ('name', 'string', None, 'Name of the VPC'),
        ],
        "outputs": [
            ('vpc_id', 'aws_vpc.this.id', 'ID of the created VPC'),
            ('vpc_cidr', 'aws_vpc.this.cidr_block', 'CIDR block of the VPC'),
        ],
    },
    "subnet": {
        "main": """resource "aws_subnet" "this" {
  for_each = var.subnets

  vpc_id            = aws_vpc.this.id
  cidr_block        = each.value.cidr
  availability_zone = each.value.az

  tags = merge(var.tags, {
    Name = "${var.name}-${each.key}"
  })
}""",
        "variables": [
            ('subnets', 'map(object({ cidr = string, az = string }))', '{}', 'Map of subnet configurations'),
        ],
        "outputs": [
            ('subnet_ids', '{ for k, v in aws_subnet.this : k => v.id }', 'Map of subnet name to ID'),
        ],
    },
    "s3_bucket": {
        "main": """resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name

  tags = var.tags
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket = aws_s3_bucket.this.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}""",
        "variables": [
            ('bucket_name', 'string', None, 'Name of the S3 bucket'),
        ],
        "outputs": [
            ('bucket_id', 'aws_s3_bucket.this.id', 'ID of the S3 bucket'),
            ('bucket_arn', 'aws_s3_bucket.this.arn', 'ARN of the S3 bucket'),
        ],
    },
    "security_group": {
        "main": """resource "aws_security_group" "this" {
  name_prefix = "${var.name}-"
  vpc_id      = var.vpc_id
  description = var.description

  tags = merge(var.tags, {
    Name = var.name
  })

  lifecycle {
    create_before_destroy = true
  }
}""",
        "variables": [
            ('vpc_id', 'string', None, 'VPC ID for the security group'),
            ('description', 'string', '"Managed by Terraform"', 'Description of the security group'),
        ],
        "outputs": [
            ('security_group_id', 'aws_security_group.this.id', 'ID of the security group'),
        ],
    },
}

PROVIDER_VERSIONS = {
    "aws": ("hashicorp/aws", "~> 5.0"),
    "gcp": ("hashicorp/google", "~> 5.0"),
    "azure": ("hashicorp/azurerm", "~> 3.0"),
}


def generate_module(module_name: str, provider: str, resources: list[str], output_dir: str) -> dict:
    """Generate Terraform module files."""
    os.makedirs(output_dir, exist_ok=True)

    all_main = []
    all_vars = [('tags', 'map(string)', '{}', 'Tags to apply to all resources')]
    all_outputs = []
    seen_vars = {"tags"}

    resource_map = AWS_RESOURCES if provider == "aws" else {}

    for res in resources:
        template = resource_map.get(res)
        if template:
            all_main.append(template["main"])
            for v in template.get("variables", []):
                if v[0] not in seen_vars:
                    all_vars.append(v)
                    seen_vars.add(v[0])
            all_outputs.extend(template.get("outputs", []))

    # Write main.tf
    with open(os.path.join(output_dir, "main.tf"), "w") as f:
        f.write("\n\n".join(all_main) + "\n")

    # Write variables.tf
    with open(os.path.join(output_dir, "variables.tf"), "w") as f:
        for name, type_str, default, desc in all_vars:
            f.write(f'variable "{name}" {{\n')
            f.write(f'  description = "{desc}"\n')
            f.write(f'  type        = {type_str}\n')
            if default is not None:
                f.write(f'  default     = {default}\n')
            # Mark sensitive vars
            if any(kw in name.lower() for kw in ("password", "secret", "key", "token")):
                f.write('  sensitive   = true\n')
            f.write('}\n\n')

    # Write outputs.tf
    with open(os.path.join(output_dir, "outputs.tf"), "w") as f:
        for name, value, desc in all_outputs:
            f.write(f'output "{name}" {{\n')
            f.write(f'  description = "{desc}"\n')
            f.write(f'  value       = {value}\n')
            f.write('}\n\n')

    # Write versions.tf
    provider_source, provider_version = PROVIDER_VERSIONS.get(provider, ("hashicorp/aws", "~> 5.0"))
    with open(os.path.join(output_dir, "versions.tf"), "w") as f:
        f.write('terraform {\n')
        f.write('  required_version = ">= 1.5.0"\n\n')
        f.write('  required_providers {\n')
        f.write(f'    {provider if provider != "gcp" else "google"} = {{\n')
        f.write(f'      source  = "{provider_source}"\n')
        f.write(f'      version = "{provider_version}"\n')
        f.write('    }\n')
        f.write('  }\n')
        f.write('}\n')

    return {
        "module_name": module_name,
        "provider": provider,
        "resources": resources,
        "files_generated": ["main.tf", "variables.tf", "outputs.tf", "versions.tf"],
        "variables_count": len(all_vars),
        "outputs_count": len(all_outputs),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Terraform module generator")
    parser.add_argument("--module-name", required=True, help="Module name")
    parser.add_argument("--provider", required=True, choices=["aws", "gcp", "azure"])
    parser.add_argument("--resources", required=True, help="Comma-separated resource types")
    parser.add_argument("--output-dir", default=".", help="Output directory")
    args = parser.parse_args()

    resources = [r.strip() for r in args.resources.split(",")]
    result = generate_module(args.module_name, args.provider, resources,
                             args.output_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
'''

_TERRAFORM_GUIDE = """\
# Terraform Module Authoring Guide

## Standard Module Structure
```
module-name/
  main.tf          # Resources
  variables.tf     # Input variables (all of them, nowhere else)
  outputs.tf       # Output values (all of them, nowhere else)
  versions.tf      # Terraform and provider version constraints
  README.md        # Usage documentation
  locals.tf        # Local values (optional)
  data.tf          # Data sources (optional)
```

## Variable Best Practices

### Always include
- `description`: what the variable controls
- `type`: explicit type constraint
- `validation`: for complex inputs

### Example with validation
```hcl
variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "cidr_block" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"

  validation {
    condition     = can(cidrhost(var.cidr_block, 0))
    error_message = "Must be a valid CIDR block."
  }
}
```

## Provider Pinning
```hcl
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"  # Allows 5.x but not 6.0
    }
  }
}
```

Never use `>= 0.0.0` — it accepts any version including breaking changes.

## for_each vs count
- **Use `for_each`**: stable identity, adding/removing doesn't shift indexes
- **Avoid `count`**: index-based, removing item N recreates items N+1, N+2, ...

```hcl
# Good: for_each with a map
resource "aws_subnet" "this" {
  for_each = var.subnets
  cidr_block = each.value.cidr
}

# Bad: count with a list (fragile)
resource "aws_subnet" "this" {
  count      = length(var.subnet_cidrs)
  cidr_block = var.subnet_cidrs[count.index]
}
```

## Security Checklist

### AWS
- S3: block public access, enable encryption, enable versioning
- Security Groups: no 0.0.0.0/0 ingress (except ALB on 80/443)
- IAM: least privilege, no inline policies, use managed policies
- EC2: IMDSv2 required, no public IPs unless behind ALB
- RDS: no public accessibility, encryption at rest, automated backups
- KMS: rotation enabled, key policies restrict access

### GCP
- IAM: use conditions, no allUsers/allAuthenticatedUsers
- GCS: uniform bucket-level access, no public
- GKE: private cluster, workload identity, network policy
- VPC: enable flow logs, private Google access

### Azure
- NSG: deny by default, specific allow rules
- Storage: disable public blob access, enable encryption
- Key Vault: soft delete enabled, access policies or RBAC
- AKS: private cluster, managed identity, network policy

## Module Composition
```hcl
# Root module consuming child modules
module "vpc" {
  source = "./modules/vpc"
  cidr_block = "10.0.0.0/16"
  name       = "production"
}

module "app" {
  source     = "./modules/app"
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids
}
```
"""

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

BATCH3_SEEDS: list[dict] = [
    # 11. Accessibility Auditor
    {
        "id": "seed-accessibility-auditor",
        "slug": "accessibility-auditor",
        "title": "Web Accessibility Auditor",
        "category": "Web Development",
        "difficulty": "hard",
        "frontmatter": {
            "name": "accessibility-auditor",
            "description": (
                "Audits HTML/JSX for WCAG 2.1 AA violations (alt text, labels, contrast, ARIA, headings). "
                "Use when user says accessibility, a11y, WCAG, screen reader, or audit. NOT for runtime browser testing or legal certification."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="accessibility-auditor",
            title="Web Accessibility Auditor",
            description=(
                "Audits HTML/JSX for WCAG 2.1 AA violations (alt text, labels, contrast, ARIA, headings). "
                "Use when user says accessibility, a11y, WCAG, screen reader, or audit. NOT for runtime browser testing or legal certification."
            ),
            allowed_tools="Read Write Bash(python *)",
            body=_A11Y_BODY,
        ),
        "supporting_files": {
            "scripts/validate.sh": _A11Y_VALIDATE,
            "scripts/main_helper.py": _A11Y_HELPER,
            "references/guide.md": _A11Y_GUIDE,
            "test_fixtures/sample.html": """\
<!DOCTYPE html>
<html>
<!-- Intentionally contains common accessibility violations for testing. -->

<head>
  <meta charset="UTF-8">
  <title></title><!-- A11Y: Empty page title (WCAG 2.4.2) -->
  <style>
    .low-contrast { color: #aaaaaa; background-color: #ffffff; }
    .tiny-text { font-size: 9px; }
    .skip-link { display: none; }/* A11Y: skip link is hidden and non-functional */
  </style>
</head>

<body>
  <!-- A11Y: No skip navigation link -->
  <!-- A11Y: No lang attribute on <html> (WCAG 3.1.1) -->

  <!-- Navigation without ARIA landmark -->
  <div id="nav">
    <a href="/home">Home</a>
    <a href="/about">About</a>
    <a href="/contact">Click here</a><!-- A11Y: Vague link text (WCAG 2.4.4) -->
    <a href="/more">Read more</a><!-- A11Y: Vague link text -->
  </div>

  <!-- Heading hierarchy violation -->
  <h1>Welcome to Our Site</h1>
  <h3>Latest News</h3><!-- A11Y: Skipped h2 level (WCAG 1.3.1) -->

  <!-- Images without alt text -->
  <img src="/images/hero.jpg"><!-- A11Y: Missing alt attribute (WCAG 1.1.1) -->
  <img src="/images/decorative-line.png" alt="decorative line image">
  <!-- A11Y: Decorative images should use alt="" not descriptive text -->

  <!-- Form without labels -->
  <form action="/subscribe" method="POST">
    <input type="text" name="fullname" placeholder="Your name">
    <!-- A11Y: No <label> element, placeholder is not a substitute (WCAG 1.3.1) -->

    <input type="email" name="email" placeholder="Email address">
    <!-- A11Y: No <label> element -->

    <select name="country">
      <!-- A11Y: No label for select -->
      <option value="">Choose...</option>
      <option value="us">United States</option>
      <option value="uk">United Kingdom</option>
    </select>

    <input type="checkbox" name="terms">I agree to the terms
    <!-- A11Y: Checkbox not associated with label text -->

    <div class="low-contrast">
      <p>By subscribing you agree to receive emails from us.</p>
      <!-- A11Y: Insufficient contrast ratio (WCAG 1.4.3) -->
    </div>

    <input type="submit" value=""><!-- A11Y: Empty submit button text -->
  </form>

  <!-- Table without proper headers -->
  <table>
    <!-- A11Y: No caption (WCAG 1.3.1) -->
    <tr>
      <td><b>Name</b></td>
      <td><b>Price</b></td>
      <!-- A11Y: Using <td><b> instead of <th> for headers -->
    </tr>
    <tr>
      <td>Widget A</td>
      <td>$9.99</td>
    </tr>
  </table>

  <!-- Custom interactive element without keyboard support -->
  <div class="button" onclick="doSomething()">
    Click Me
  </div>
  <!-- A11Y: Missing role="button", tabindex, and keyboard handler (WCAG 2.1.1) -->

  <!-- Auto-playing media -->
  <video autoplay src="/promo.mp4"></video>
  <!-- A11Y: Autoplay without controls (WCAG 1.4.2) -->
  <!-- A11Y: No captions/subtitles track (WCAG 1.2.2) -->

  <!-- Focus trap: tabindex > 0 disrupts natural tab order -->
  <a href="/special" tabindex="5">Special Offer</a>
  <!-- A11Y: Positive tabindex disrupts tab order (WCAG 2.4.3) -->

  <div id="modal" style="display:none;" aria-hidden="false">
    <!-- A11Y: aria-hidden conflicts with display state -->
    <p>Modal content here</p>
  </div>

</body>
</html>
""",
        },
        "traits": [
            "dual-mode-scan",
            "wcag-criterion-linked",
            "fix-code-examples",
            "severity-ranked",
        ],
        "meta_strategy": "Scan statically for WCAG violations, link each finding to its success criterion, and always provide a concrete fix with code.",
    },
    # 12. Data Transformer
    {
        "id": "seed-data-transformer",
        "slug": "data-transformer",
        "title": "Data Format Transformer",
        "category": "Data Engineering",
        "difficulty": "medium",
        "frontmatter": {
            "name": "data-transformer",
            "description": (
                "Converts data between CSV, JSON, YAML, XML, and TOML with schema inference and record-count validation. "
                "Use when user says convert, transform, flatten, or mentions any format pair. NOT for databases, Spark, or binary formats."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="data-transformer",
            title="Data Format Transformer",
            description=(
                "Converts data between CSV, JSON, YAML, XML, and TOML with schema inference and record-count validation. "
                "Use when user says convert, transform, flatten, or mentions any format pair. NOT for databases, Spark, or binary formats."
            ),
            allowed_tools="Read Write Bash(python *)",
            body=_DATA_XFORM_BODY,
        ),
        "supporting_files": {
            "scripts/validate.sh": _DATA_XFORM_VALIDATE,
            "scripts/main_helper.py": _DATA_XFORM_HELPER,
            "references/guide.md": _DATA_XFORM_GUIDE,
        },
        "traits": [
            "format-auto-detect",
            "schema-inference",
            "record-count-preservation",
            "nested-flattening",
        ],
        "meta_strategy": "Auto-detect source format, parse to intermediate dicts, convert to target format, and validate zero data loss by comparing record counts.",
    },
    # 13. Regex Builder
    {
        "id": "seed-regex-builder",
        "slug": "regex-builder",
        "title": "Regex Pattern Builder",
        "category": "Developer Productivity",
        "difficulty": "easy",
        "frontmatter": {
            "name": "regex-builder",
            "description": (
                "Builds, tests, and explains regular expressions from natural language. "
                "Use when user says regex, pattern match, extract, or validate format, even without saying regex. NOT for full parsers or NLP."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="regex-builder",
            title="Regex Pattern Builder",
            description=(
                "Builds, tests, and explains regular expressions from natural language. "
                "Use when user says regex, pattern match, extract, or validate format, even without saying regex. NOT for full parsers or NLP."
            ),
            allowed_tools="Read Write Bash(python *)",
            body=_REGEX_BODY,
        ),
        "supporting_files": {
            "scripts/validate.sh": _REGEX_VALIDATE,
            "scripts/main_helper.py": _REGEX_HELPER,
            "references/guide.md": _REGEX_GUIDE,
            "references/cheatsheet.md": """\
# Regex Quick Reference

Syntax reference and ready-to-use patterns for common validation tasks.
Patterns are shown in PCRE/Python syntax; notes where JS or Go differ.

---

## Core Syntax

| Token       | Meaning                            | Example             |
|-------------|------------------------------------|---------------------|
| `.`         | Any character (except newline)     | `a.c` matches `abc` |
| `\\d`       | Digit `[0-9]`                      | `\\d{3}` matches `123` |
| `\\D`       | Non-digit                          | `\\D+` matches `abc` |
| `\\w`       | Word char `[A-Za-z0-9_]`          | `\\w+` matches `foo_1` |
| `\\W`       | Non-word char                      |                     |
| `\\s`       | Whitespace `[ \\t\\n\\r\\f]`      |                     |
| `\\S`       | Non-whitespace                     |                     |
| `\\b`       | Word boundary                      | `\\bfoo\\b` matches whole word |

## Quantifiers

| Token    | Meaning                  |
|----------|--------------------------|
| `*`      | 0 or more (greedy)       |
| `+`      | 1 or more (greedy)       |
| `?`      | 0 or 1 (optional)        |
| `{n}`    | Exactly n                |
| `{n,}`   | n or more                |
| `{n,m}`  | Between n and m          |
| `*?`     | 0 or more (lazy)         |
| `+?`     | 1 or more (lazy)         |

## Anchors

| Token  | Meaning          |
|--------|------------------|
| `^`    | Start of string (or line with `re.MULTILINE`) |
| `$`    | End of string (or line with `re.MULTILINE`)   |
| `\\A`  | Absolute start of string |
| `\\Z`  | Absolute end of string   |

## Groups & Lookaround

| Token             | Meaning                     |
|-------------------|-----------------------------|
| `(abc)`           | Capturing group             |
| `(?:abc)`         | Non-capturing group         |
| `(?P<name>abc)`   | Named group (Python)        |
| `(?<name>abc)`    | Named group (JS/Go)         |
| `(?=abc)`         | Positive lookahead          |
| `(?!abc)`         | Negative lookahead          |
| `(?<=abc)`        | Positive lookbehind         |
| `(?<!abc)`        | Negative lookbehind         |

## Character Classes

| Token        | Meaning                     |
|--------------|-----------------------------|
| `[abc]`      | Any of a, b, c              |
| `[^abc]`     | Not a, b, or c              |
| `[a-z]`      | Range: a through z          |
| `[a-zA-Z]`   | Any letter                  |
| `[\\[\\]]`   | Literal brackets (escaped)  |

---

## Common Patterns

### Email Address (simplified, RFC 5322-ish)
```regex
^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$
```
Matches: `user@example.com`, `first.last+tag@sub.domain.org`
Rejects: `@example.com`, `user@.com`, `user@com`

### URL (HTTP/HTTPS)
```regex
^https?://[a-zA-Z0-9.-]+(?:\\.[a-zA-Z]{2,})(?:/[^\\s]*)?$
```
Matches: `https://example.com`, `http://sub.domain.co.uk/path?q=1`
Rejects: `ftp://file.txt`, `://missing-scheme.com`

### IPv4 Address
```regex
^(?:(?:25[0-5]|2[0-4]\\d|[01]?\\d\\d?)\\.){3}(?:25[0-5]|2[0-4]\\d|[01]?\\d\\d?)$
```
Matches: `192.168.1.1`, `0.0.0.0`, `255.255.255.255`
Rejects: `256.1.1.1`, `192.168.1`, `1.2.3.4.5`

### Date (YYYY-MM-DD)
```regex
^\\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\\d|3[01])$
```
Matches: `2025-01-15`, `2000-12-31`
Rejects: `2025-13-01`, `2025-00-15`, `25-1-1`

### Phone (US, flexible)
```regex
^\\+?1?[-.\\s]?\\(?\\d{3}\\)?[-.\\s]?\\d{3}[-.\\s]?\\d{4}$
```
Matches: `(555) 123-4567`, `+1-555-123-4567`, `5551234567`

### UUID v4
```regex
^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$
```
Matches: `550e8400-e29b-41d4-a716-446655440000`

### Semantic Version
```regex
^(0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)(?:-((?:0|[1-9]\\d*|\\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\\.(?:0|[1-9]\\d*|\\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\\+([0-9a-zA-Z-]+(?:\\.[0-9a-zA-Z-]+)*))?$
```
Matches: `1.0.0`, `2.3.4-beta.1`, `1.0.0-alpha+build.123`

### Hex Color Code
```regex
^#(?:[0-9a-fA-F]{3}){1,2}$
```
Matches: `#fff`, `#1a2B3c`

### Slug (URL-safe identifier)
```regex
^[a-z0-9]+(?:-[a-z0-9]+)*$
```
Matches: `hello-world`, `post-123`

---

## Dialect Differences

| Feature              | Python (`re`) | JavaScript | Go (`regexp`) |
|----------------------|---------------|------------|---------------|
| Named groups         | `(?P<n>...)`  | `(?<n>...)` | `(?P<n>...)` |
| Lookbehind           | Variable-width | Fixed-width only | Not supported |
| `\\A` / `\\Z`       | Supported     | Not supported | Supported  |
| Unicode categories   | `\\p{L}`      | `\\p{L}` (with `u` flag) | `\\p{L}` |
| Atomic groups        | Not supported | Not supported | Not supported |
| Possessive quantifiers | Not supported | Not supported | Not supported |
""",
        },
        "traits": [
            "natural-language-to-pattern",
            "multi-dialect",
            "positive-negative-testing",
            "plain-english-explanation",
        ],
        "meta_strategy": "Build patterns from requirements, test against both positive and negative examples, and explain every component in plain English.",
    },
    # 14. Error Handler
    {
        "id": "seed-error-handler",
        "slug": "error-handler",
        "title": "Error Handling & Logging Generator",
        "category": "Observability",
        "difficulty": "hard",
        "frontmatter": {
            "name": "error-handler",
            "description": (
                "Scans code for unhandled exceptions and bare catch blocks, generates structured error handling with logging. "
                "Use when user says error handling, try catch, logging, or bare except. NOT for debugging runtime errors or profiling."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="error-handler",
            title="Error Handling & Logging Generator",
            description=(
                "Scans code for unhandled exceptions and bare catch blocks, generates structured error handling with logging. "
                "Use when user says error handling, try catch, logging, or bare except. NOT for debugging runtime errors or profiling."
            ),
            allowed_tools="Read Write Bash(python *)",
            body=_ERROR_HANDLER_BODY,
        ),
        "supporting_files": {
            "scripts/validate.sh": _ERROR_HANDLER_VALIDATE,
            "scripts/main_helper.py": _ERROR_HANDLER_HELPER,
            "references/guide.md": _ERROR_HANDLER_GUIDE,
            "references/exception-hierarchy.md": """\
# Structured Exception Hierarchy Examples

Well-designed exception hierarchies make error handling precise and
maintainable. These examples show how to organize custom exceptions
for Python and JavaScript/TypeScript projects.

---

## Python

### Base hierarchy

```python
class AppError(Exception):
    \"\"\"Base exception for the application. All custom exceptions inherit from this.\"\"\"

    def __init__(self, message: str, *, code: str = "UNKNOWN", context: dict | None = None):
        super().__init__(message)
        self.code = code
        self.context = context or {}


# --- Validation errors (client's fault) ---

class ValidationError(AppError):
    \"\"\"Input failed validation rules.\"\"\"

    def __init__(self, message: str, *, field: str | None = None, **kwargs):
        super().__init__(message, code="VALIDATION_ERROR", **kwargs)
        self.field = field


class MissingFieldError(ValidationError):
    \"\"\"A required field was not provided.\"\"\"

    def __init__(self, field: str):
        super().__init__(f"Missing required field: {field}", field=field)
        self.code = "MISSING_FIELD"


class InvalidFormatError(ValidationError):
    \"\"\"Field value does not match expected format.\"\"\"

    def __init__(self, field: str, expected: str):
        super().__init__(f"{field} must be {expected}", field=field)
        self.code = "INVALID_FORMAT"


# --- Resource errors (not found, conflict) ---

class NotFoundError(AppError):
    \"\"\"Requested resource does not exist.\"\"\"

    def __init__(self, resource: str, identifier: str | int):
        super().__init__(
            f"{resource} not found: {identifier}",
            code="NOT_FOUND",
            context={"resource": resource, "id": str(identifier)},
        )


class ConflictError(AppError):
    \"\"\"Operation conflicts with current resource state.\"\"\"

    def __init__(self, message: str):
        super().__init__(message, code="CONFLICT")


# --- Authentication / Authorization ---

class AuthError(AppError):
    \"\"\"Base for auth-related failures.\"\"\"
    pass


class AuthenticationError(AuthError):
    \"\"\"Caller identity could not be verified.\"\"\"

    def __init__(self, reason: str = "Invalid credentials"):
        super().__init__(reason, code="UNAUTHENTICATED")


class AuthorizationError(AuthError):
    \"\"\"Caller lacks permission for this action.\"\"\"

    def __init__(self, action: str, resource: str):
        super().__init__(
            f"Not authorized to {action} on {resource}",
            code="FORBIDDEN",
            context={"action": action, "resource": resource},
        )


# --- External service errors (retryable) ---

class ExternalServiceError(AppError):
    \"\"\"An external dependency failed.\"\"\"

    def __init__(self, service: str, message: str, *, retryable: bool = True):
        super().__init__(
            f"{service}: {message}",
            code="EXTERNAL_ERROR",
            context={"service": service, "retryable": retryable},
        )
        self.retryable = retryable


class TimeoutError(ExternalServiceError):
    \"\"\"External call exceeded time limit.\"\"\"

    def __init__(self, service: str, timeout_seconds: float):
        super().__init__(service, f"Timed out after {timeout_seconds}s", retryable=True)
        self.code = "TIMEOUT"


class RateLimitError(ExternalServiceError):
    \"\"\"External service returned 429.\"\"\"

    def __init__(self, service: str, retry_after: int | None = None):
        msg = f"Rate limited" + (f", retry after {retry_after}s" if retry_after else "")
        super().__init__(service, msg, retryable=True)
        self.code = "RATE_LIMITED"
        self.retry_after = retry_after
```

### Usage with structured logging

```python
import logging, json

logger = logging.getLogger(__name__)

try:
    user = get_user(user_id)
except NotFoundError as e:
    logger.warning(json.dumps({"error": e.code, "context": e.context}))
    raise
except ExternalServiceError as e:
    if e.retryable:
        logger.info(f"Retryable error: {e}")
        # ... retry logic
    else:
        logger.error(f"Permanent failure: {e}")
        raise
```

---

## JavaScript / TypeScript

### Base hierarchy

```typescript
class AppError extends Error {
  readonly code: string;
  readonly context: Record<string, unknown>;
  readonly statusCode: number;

  constructor(
    message: string,
    { code = 'UNKNOWN', statusCode = 500, context = {} }: {
      code?: string;
      statusCode?: number;
      context?: Record<string, unknown>;
    } = {}
  ) {
    super(message);
    this.name = this.constructor.name;
    this.code = code;
    this.statusCode = statusCode;
    this.context = context;
    Error.captureStackTrace?.(this, this.constructor);
  }

  toJSON() {
    return { error: this.code, message: this.message, context: this.context };
  }
}

// --- Validation ---

class ValidationError extends AppError {
  readonly field?: string;
  constructor(message: string, field?: string) {
    super(message, { code: 'VALIDATION_ERROR', statusCode: 400, context: { field } });
    this.field = field;
  }
}

class MissingFieldError extends ValidationError {
  constructor(field: string) {
    super(`Missing required field: ${field}`, field);
    (this as any).code = 'MISSING_FIELD';
  }
}

// --- Resource ---

class NotFoundError extends AppError {
  constructor(resource: string, id: string | number) {
    super(`${resource} not found: ${id}`, {
      code: 'NOT_FOUND',
      statusCode: 404,
      context: { resource, id: String(id) },
    });
  }
}

class ConflictError extends AppError {
  constructor(message: string) {
    super(message, { code: 'CONFLICT', statusCode: 409 });
  }
}

// --- Auth ---

class AuthenticationError extends AppError {
  constructor(reason = 'Invalid credentials') {
    super(reason, { code: 'UNAUTHENTICATED', statusCode: 401 });
  }
}

class AuthorizationError extends AppError {
  constructor(action: string, resource: string) {
    super(`Not authorized to ${action} on ${resource}`, {
      code: 'FORBIDDEN',
      statusCode: 403,
      context: { action, resource },
    });
  }
}

// --- External ---

class ExternalServiceError extends AppError {
  readonly retryable: boolean;
  constructor(service: string, message: string, retryable = true) {
    super(`${service}: ${message}`, {
      code: 'EXTERNAL_ERROR',
      statusCode: 502,
      context: { service, retryable },
    });
    this.retryable = retryable;
  }
}
```

---

## Mapping to HTTP Status Codes

| Exception Class       | HTTP Status | When to Use                     |
|-----------------------|-------------|----------------------------------|
| ValidationError       | 400         | Bad input from client            |
| AuthenticationError   | 401         | Missing or invalid credentials   |
| AuthorizationError    | 403         | Valid identity, insufficient role |
| NotFoundError         | 404         | Resource does not exist          |
| ConflictError         | 409         | Duplicate, version conflict      |
| RateLimitError        | 429         | Too many requests                |
| ExternalServiceError  | 502         | Upstream dependency failed       |
| TimeoutError          | 504         | Upstream timed out               |
| AppError (default)    | 500         | Unexpected internal error        |

---

## Design Principles

1. **Single base class** — catch `AppError` to handle all known errors.
2. **Machine-readable code** — `error.code` for programmatic matching; `error.message` for humans.
3. **Structured context** — attach relevant data (field name, resource ID, service name) for logging.
4. **Retryable flag** — distinguish transient failures from permanent ones at the type level.
5. **HTTP status mapping** — each exception knows its status code; handlers just read it.
6. **Never catch bare `Exception`/`Error`** — always catch the most specific type first.
""",
        },
        "traits": [
            "anti-pattern-detection",
            "specific-exception-types",
            "structured-logging",
            "retry-with-backoff",
        ],
        "meta_strategy": "Detect bare catch blocks and unhandled exceptions, replace with specific types and structured JSON logging, and add retry logic for transient failures.",
    },
    # 15. Terraform Module
    {
        "id": "seed-terraform-module-full",
        "slug": "terraform-module-full",
        "title": "Terraform Module Generator",
        "category": "Infrastructure as Code",
        "difficulty": "medium",
        "frontmatter": {
            "name": "terraform-module-full",
            "description": (
                "Generates production-ready Terraform modules with typed variables, validation, pinned providers, and security checks. "
                "Use when user says Terraform, module, HCL, or provision cloud resources. NOT for Pulumi, CDK, or CloudFormation."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="terraform-module-full",
            title="Terraform Module Generator",
            description=(
                "Generates production-ready Terraform modules with typed variables, validation, pinned providers, and security checks. "
                "Use when user says Terraform, module, HCL, or provision cloud resources. NOT for Pulumi, CDK, or CloudFormation."
            ),
            allowed_tools="Read Write Bash(terraform * python *)",
            body=_TERRAFORM_BODY,
        ),
        "supporting_files": {
            "scripts/validate.sh": _TERRAFORM_VALIDATE,
            "scripts/main_helper.py": _TERRAFORM_HELPER,
            "references/guide.md": _TERRAFORM_GUIDE,
            "assets/module-template.tf": """\
# Terraform Module Template
# A properly structured module showing variable typing, validation,
# resource best practices, and output conventions.

# ---------------------------------------------------------------------------
# Variables — typed, validated, documented
# ---------------------------------------------------------------------------

variable "name" {
  description = "Human-readable name for the resource. Used in tags and resource naming."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,62}$", var.name))
    error_message = "Name must be 3-63 lowercase alphanumeric characters or hyphens, starting with a letter."
  }
}

variable "environment" {
  description = "Deployment environment (e.g., dev, staging, production)."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be one of: dev, staging, production."
  }
}

variable "tags" {
  description = "Additional tags to apply to all resources. Merged with default tags."
  type        = map(string)
  default     = {}
}

variable "enable_monitoring" {
  description = "Whether to create monitoring and alerting resources."
  type        = bool
  default     = true
}

variable "instance_count" {
  description = "Number of instances to create."
  type        = number
  default     = 1

  validation {
    condition     = var.instance_count >= 1 && var.instance_count <= 10
    error_message = "Instance count must be between 1 and 10."
  }
}

# ---------------------------------------------------------------------------
# Locals — computed values, tag merging, naming
# ---------------------------------------------------------------------------

locals {
  # Consistent naming: <project>-<environment>-<name>
  resource_prefix = "${var.name}-${var.environment}"

  default_tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
    Module      = "example-module"
    Name        = local.resource_prefix
  }

  tags = merge(local.default_tags, var.tags)
}

# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

# Use for_each over count for named resources (easier to reason about state)
# resource "aws_instance" "this" {
#   for_each = toset([for i in range(var.instance_count) : "${local.resource_prefix}-${i}"])
#
#   ami           = data.aws_ami.latest.id
#   instance_type = "t3.micro"
#
#   tags = merge(local.tags, {
#     Name = each.key
#   })
#
#   # Security defaults
#   metadata_options {
#     http_tokens = "required"  # IMDSv2 only
#   }
#
#   root_block_device {
#     encrypted = true
#   }
# }

# ---------------------------------------------------------------------------
# Outputs — always output ID, ARN, and any connection info
# ---------------------------------------------------------------------------

# output "instance_ids" {
#   description = "List of instance IDs created by this module."
#   value       = [for inst in aws_instance.this : inst.id]
# }

# output "instance_arns" {
#   description = "List of instance ARNs created by this module."
#   value       = [for inst in aws_instance.this : inst.arn]
# }

# output "resource_prefix" {
#   description = "The computed resource name prefix used by this module."
#   value       = local.resource_prefix
# }
""",
            "assets/versions.tf.template": """\
# Provider Version Pinning Template
#
# Pin providers to exact versions to ensure reproducible applies.
# Use `~>` (pessimistic constraint) only when you explicitly want
# minor version upgrades.
#
# Update versions deliberately with `terraform init -upgrade` after
# reviewing changelogs.

terraform {
  required_version = ">= 1.5.0, < 2.0.0"

  required_providers {
    # AWS Provider
    # Changelog: https://github.com/hashicorp/terraform-provider-aws/releases
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40.0"
    }

    # Google Cloud Provider
    # Changelog: https://github.com/hashicorp/terraform-provider-google/releases
    # google = {
    #   source  = "hashicorp/google"
    #   version = "~> 5.20.0"
    # }

    # Azure Provider
    # Changelog: https://github.com/hashicorp/terraform-provider-azurerm/releases
    # azurerm = {
    #   source  = "hashicorp/azurerm"
    #   version = "~> 3.95.0"
    # }

    # Kubernetes Provider
    # kubernetes = {
    #   source  = "hashicorp/kubernetes"
    #   version = "~> 2.27.0"
    # }

    # Random provider (for unique naming)
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6.0"
    }

    # Null provider (for provisioners, lifecycle hooks)
    # null = {
    #   source  = "hashicorp/null"
    #   version = "~> 3.2.0"
    # }
  }
}

# ---------------------------------------------------------------------------
# Backend Configuration
# ---------------------------------------------------------------------------
# Uncomment and configure for remote state storage.
#
# terraform {
#   backend "s3" {
#     bucket         = "my-terraform-state"
#     key            = "modules/example/terraform.tfstate"
#     region         = "us-east-1"
#     dynamodb_table = "terraform-locks"
#     encrypt        = true
#   }
# }

# ---------------------------------------------------------------------------
# Provider Configuration
# ---------------------------------------------------------------------------

# provider "aws" {
#   region = var.aws_region
#
#   default_tags {
#     tags = {
#       ManagedBy   = "terraform"
#       Environment = var.environment
#     }
#   }
# }
""",
        },
        "traits": [
            "contract-first-modules",
            "provider-pinning",
            "security-defaults",
            "for-each-over-count",
        ],
        "meta_strategy": "Generate typed module contracts (variables + outputs), pin providers, default to secure settings, and validate structure before shipping.",
    },
]

__all__ = ["BATCH3_SEEDS"]
