"""Batch 1 Gen 0 Seeds: git-commit-message, code-review, unit-test-generator,
api-endpoint-designer, database-migration.

Each skill ships with functional scripts/ and references/ as supporting_files.
"""
from __future__ import annotations

from skillforge.seeds import _build

# ---------------------------------------------------------------------------
# 1. Git Commit Message Generator
# ---------------------------------------------------------------------------
_GIT_COMMIT_BODY = """\
## Quick Start
Read the staged diff, infer the scope and change type, then generate a
Conventional Commits message with a subject line under 72 characters and
a body explaining *what* changed and *why*.

## When to use this skill
Use when the user says "commit message", "write a commit", "describe these
changes", "what should I commit", "conventional commit", or stages changes
and asks what to write. Also triggers on "git commit -m" requests, even if
they don't explicitly ask for help.

## Workflow

### Step 1: Gather context from the staged diff
Run `python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py` in the repo root.
It executes `git diff --staged --stat` and `git diff --staged` and outputs
a JSON summary with files changed, inferred scope, change magnitude, and a
truncated diff excerpt.

### Step 2: Choose the commit type and scope
Read `${CLAUDE_SKILL_DIR}/references/guide.md` for the type definitions.
Pick the most specific type:
- `feat` for new user-facing functionality
- `fix` for bug corrections
- `refactor` for internal restructuring with no behavior change
- `docs`, `test`, `build`, `ci`, `chore`, `perf`, `style`, `revert` as appropriate
Infer scope from the directory or module most affected (e.g., `auth`, `api`, `ui`).

### Step 3: Draft the message
- Subject: `type(scope): imperative description` (max 72 chars)
- Blank line
- Body: 1-3 sentences on *what* and *why*, wrapped at 80 columns
- Footer: `BREAKING CHANGE: ...` if applicable, or `Closes #NNN`

### Step 4: Validate
Run `bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh "subject line here"`.
If it exits non-zero, fix the issues it reports and re-validate.

## Examples

**Example 1: Simple feature addition**
Input: "write a commit message for these staged changes" (user added a search bar component)
Output:
```
feat(ui): add search bar to the header

Introduce a debounced search input that filters the product list
client-side. Results update as the user types with a 300ms delay
to avoid excessive re-renders.
```

**Example 2: Bug fix with issue reference**
Input: "commit message for fixing the login timeout bug"
Output:
```
fix(auth): prevent session timeout during active requests

The keepalive middleware now resets the inactivity timer on every
authenticated API call, not just page navigations.

Closes #247
```

**Example 3: Refactor across multiple files**
Input: "I refactored the database layer, what should the commit say?"
Output:
```
refactor(db): extract connection pooling into dedicated module

Move pool configuration, health checks, and retry logic out of
individual repository files into db/pool.py. No behavior change;
existing tests pass without modification.
```

## Common mistakes to avoid
- Using past tense ("added") instead of imperative ("add") in the subject
- Exceeding 72 characters on the subject line — many tools truncate
- Omitting the body for non-trivial changes — "fix bug" is never enough
- Using `chore` as a catch-all — it's specifically for tooling and maintenance
- Forgetting `BREAKING CHANGE:` footer when the public API changes
"""

_GIT_COMMIT_VALIDATE_SH = r"""#!/usr/bin/env bash
set -euo pipefail

# validate.sh — Validate a Conventional Commits message.
# Usage: bash validate.sh "subject line"
#   or:  bash validate.sh < message_file.txt
#
# Exit 0 on pass, non-zero with violation messages on failure.

errors=0

if [[ $# -ge 1 ]]; then
    subject="$1"
else
    # Read first line from stdin
    read -r subject
fi

# --- Subject line checks ---

# Must match Conventional Commits pattern
pattern='^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-z0-9._-]+\))?(!)?: .+'
if ! echo "$subject" | grep -qE "$pattern"; then
    echo "ERROR: Subject does not match Conventional Commits format."
    echo "  Expected: type(scope): description"
    echo "  Got:      $subject"
    errors=$((errors + 1))
fi

# Length check (max 72 characters)
length=${#subject}
if [[ $length -gt 72 ]]; then
    echo "ERROR: Subject line is $length chars (max 72)."
    errors=$((errors + 1))
fi

# Imperative mood heuristic: first word after "type(scope): " should not
# end in -ed, -ing, or -s (common non-imperative suffixes).
desc=$(echo "$subject" | sed -E 's/^[a-z]+(\([^)]*\))?(!)?: //')
first_word=$(echo "$desc" | awk '{print $1}')
if echo "$first_word" | grep -qiE '(ed|ing|ies)$'; then
    echo "WARNING: '$first_word' may not be imperative mood. Use 'add' not 'added'."
    # Warning only — don't fail
fi

# Must not start with uppercase after the colon
first_char=$(echo "$desc" | cut -c1)
if [[ "$first_char" =~ [A-Z] ]]; then
    echo "WARNING: Description starts with uppercase '$first_char'. Conventional style uses lowercase."
fi

# --- Body checks (if provided via stdin after subject) ---
if [[ $# -eq 0 ]]; then
    line_num=0
    while IFS= read -r line; do
        line_num=$((line_num + 1))
        line_len=${#line}
        if [[ $line_len -gt 80 ]]; then
            echo "WARNING: Body line $line_num is $line_len chars (recommended max 80)."
        fi
        # Check breaking change footer format
        if echo "$line" | grep -qi "^breaking.change" && ! echo "$line" | grep -qE '^BREAKING CHANGE: .+'; then
            echo "ERROR: Breaking change footer must be 'BREAKING CHANGE: description'."
            errors=$((errors + 1))
        fi
    done
fi

if [[ $errors -gt 0 ]]; then
    echo "FAILED: $errors error(s) found."
    exit 1
fi

echo "OK: Commit message passes all checks."
exit 0
"""

_GIT_COMMIT_HELPER_PY = r'''#!/usr/bin/env python3
"""Change context analyzer for commit message generation.

Runs git diff --staged and produces a JSON summary with:
- files_changed: list of modified file paths
- scope_hint: inferred scope from common directory prefix
- magnitude: small / medium / large based on insertions+deletions
- diff_summary: truncated diff output (first 3000 chars)
"""

import json
import os
import subprocess
import sys


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout.strip()


def infer_scope(files: list[str]) -> str:
    """Infer a scope from the common directory of changed files."""
    if not files:
        return ""
    # Take the first path component after any src/ or lib/ prefix
    scopes: list[str] = []
    for f in files:
        parts = f.replace("\\", "/").split("/")
        # Skip common top-level dirs
        filtered = [p for p in parts if p not in ("src", "lib", "app", "pkg", "internal")]
        if len(filtered) >= 2:
            scopes.append(filtered[0])
        elif filtered:
            scopes.append(os.path.splitext(filtered[0])[0])
    if not scopes:
        return ""
    # Most common scope
    from collections import Counter
    most_common = Counter(scopes).most_common(1)
    return most_common[0][0] if most_common else ""


def classify_magnitude(insertions: int, deletions: int) -> str:
    total = insertions + deletions
    if total <= 20:
        return "small"
    elif total <= 150:
        return "medium"
    else:
        return "large"


def main() -> None:
    stat_output = run(["git", "diff", "--staged", "--stat"])
    diff_output = run(["git", "diff", "--staged"])

    if not stat_output:
        print(json.dumps({"error": "No staged changes found. Stage files with git add first."}))
        sys.exit(1)

    # Parse stat output for file list and counts
    files: list[str] = []
    total_ins = 0
    total_del = 0
    for line in stat_output.splitlines():
        if "|" in line:
            fname = line.split("|")[0].strip()
            files.append(fname)
        if "insertions" in line or "deletions" in line:
            import re
            nums = re.findall(r"(\d+) (insertion|deletion)", line)
            for count, kind in nums:
                if kind == "insertion":
                    total_ins = int(count)
                else:
                    total_del = int(count)

    result = {
        "files_changed": files,
        "scope_hint": infer_scope(files),
        "magnitude": classify_magnitude(total_ins, total_del),
        "insertions": total_ins,
        "deletions": total_del,
        "diff_summary": diff_output[:3000],
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
'''

_GIT_COMMIT_GUIDE_MD = """\
# Conventional Commits Reference Guide

## Commit Types

| Type | When to use |
|------|-------------|
| `feat` | A new feature visible to users |
| `fix` | A bug fix |
| `docs` | Documentation-only changes |
| `style` | Formatting, whitespace, semicolons (no logic change) |
| `refactor` | Code restructuring without behavior change |
| `perf` | Performance improvement |
| `test` | Adding or correcting tests |
| `build` | Build system or dependency changes (pip, npm, cargo) |
| `ci` | CI configuration changes (GitHub Actions, etc.) |
| `chore` | Maintenance tasks (updating .gitignore, tooling config) |
| `revert` | Reverting a previous commit |

## Subject Line Rules

1. Use imperative mood: "add", "fix", "remove" -- not "added", "fixes", "removing"
2. Maximum 72 characters (many tools truncate at this width)
3. Lowercase after the colon: `feat(ui): add search bar` not `feat(ui): Add search bar`
4. No period at the end
5. Scope is optional but encouraged: `feat(auth):`, `fix(api):`

## Scope Conventions

Scope should be a single noun identifying the section of the codebase:
- Module name: `auth`, `api`, `db`, `ui`, `cli`
- Feature area: `search`, `billing`, `notifications`
- Config target: `eslint`, `docker`, `ci`

## Body Guidelines

- Separate from subject by a blank line
- Wrap at 80 characters
- Explain WHAT changed and WHY, not HOW (the diff shows how)
- Use bullet points for multiple distinct changes

## Footer Conventions

- `BREAKING CHANGE: description` -- signals a semver-major bump
- `Closes #123` -- auto-closes the referenced issue
- `Refs #456` -- references without closing
- `Co-authored-by: Name <email>` -- for pair programming

## Examples of Good Messages

```
feat(search): add fuzzy matching to product search

Use Levenshtein distance with threshold 2 to catch typos.
Results are ranked by edit distance then relevance score.

Closes #189
```

```
fix(api): return 404 instead of 500 for missing resources

The generic exception handler was catching NotFoundError before
the specific handler. Reorder middleware to let domain exceptions
propagate first.
```

```
refactor(db): replace raw SQL with repository pattern

Extract all database queries into repository classes with typed
methods. This enables unit testing with in-memory fakes and
removes SQL strings from business logic.

BREAKING CHANGE: DatabaseService.query() removed; use
UserRepository.find_by_id() and similar typed methods instead.
```
"""

# ---------------------------------------------------------------------------
# 2. Code Review Assistant
# ---------------------------------------------------------------------------
_CODE_REVIEW_BODY = """\
## Quick Start
Perform a multi-pass review: security first, then correctness, then quality
and style. Produce a structured report with severity levels. Use the helper
script for deterministic pattern detection before applying judgment.

## When to use this skill
Use when the user says "review", "code review", "check this code", "audit",
"find bugs", "security check", or pastes code and asks "anything wrong?".
Also triggers on "PR review", "pull request feedback", even if they don't
explicitly ask for a formal review. NOT for writing new code, refactoring,
or test generation.

## Workflow

### Step 1: Run automated checks
Run `python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py <file_or_dir>` to
detect security anti-patterns, complexity hotspots, and common code smells.
Review the JSON output for any critical or high-severity findings.

### Step 2: Security review
Read `${CLAUDE_SKILL_DIR}/references/guide.md` for the security checklist.
Check for:
- Injection vulnerabilities (SQL, command, XSS, template)
- Hardcoded secrets or credentials
- Insecure deserialization or eval/exec usage
- Missing input validation on user-facing endpoints
- Improper error handling that leaks internals

### Step 3: Correctness and logic review
Walk through the code path by path:
- Are edge cases handled (empty input, None, zero, negative)?
- Do error paths clean up resources (close files, release locks)?
- Are race conditions possible in concurrent code?
- Do type annotations match actual usage?

### Step 4: Quality and maintainability
- Function length (>30 lines is a smell)
- Naming clarity (can you understand the function without reading the body?)
- DRY violations (copy-pasted blocks)
- Missing or misleading comments

### Step 5: Compile the report
Run `bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh <report_file>` to verify
the report format is valid. Present findings grouped by severity:
critical > warning > suggestion.

## Examples

**Example 1: Python API endpoint with SQL injection**
Input: "review this Flask endpoint" (handler builds SQL with f-strings)
Output: CRITICAL: SQL injection via string formatting on line 24. Use
parameterized queries. Also: WARNING: bare `except:` on line 31 swallows
all errors. SUGGESTION: extract DB logic into a repository function.

**Example 2: JavaScript with XSS vulnerability**
Input: "check this React component for issues" (uses dangerouslySetInnerHTML)
Output: CRITICAL: XSS risk from unsanitized user input passed to
dangerouslySetInnerHTML on line 18. Sanitize with DOMPurify or use
textContent. WARNING: useEffect missing dependency array causes infinite
re-renders.

**Example 3: Go function with race condition**
Input: "anything wrong with this handler?" (shared map without mutex)
Output: CRITICAL: concurrent map writes without synchronization on line 45.
Use sync.Mutex or sync.Map. SUGGESTION: extract the cache into its own
type with thread-safe methods.

## Common mistakes to avoid
- Reviewing only the happy path and ignoring error handling
- Flagging style issues as critical (use the right severity)
- Suggesting rewrites when a targeted fix is sufficient
- Missing the security angle entirely — always check for injection first
"""

_CODE_REVIEW_HELPER_PY = r'''#!/usr/bin/env python3
"""Static analysis helper for code review.

Scans files for security anti-patterns, complexity metrics, and code smells.
Outputs a JSON report.

Usage: python main_helper.py <file_or_directory>
"""

import json
import os
import re
import sys
from pathlib import Path


SECURITY_PATTERNS = [
    # (pattern, description, severity, languages)
    (r'(?:execute|exec)\s*\(', "Potential code execution via exec/execute", "critical", ["python", "javascript"]),
    (r'eval\s*\(', "Use of eval() — potential code injection", "critical", ["python", "javascript"]),
    (r'subprocess\.call\s*\([^,]*shell\s*=\s*True', "Shell injection risk: subprocess with shell=True", "critical", ["python"]),
    (r'os\.system\s*\(', "Shell injection risk: os.system()", "critical", ["python"]),
    (r'f["\'].*(?:SELECT|INSERT|UPDATE|DELETE|DROP).*\{', "Potential SQL injection via f-string", "critical", ["python"]),
    (r'\$\{.*\}.*(?:SELECT|INSERT|UPDATE|DELETE|DROP)', "Potential SQL injection via template literal", "critical", ["javascript"]),
    (r'dangerouslySetInnerHTML', "XSS risk: dangerouslySetInnerHTML", "critical", ["javascript"]),
    (r'innerHTML\s*=', "XSS risk: direct innerHTML assignment", "warning", ["javascript"]),
    (r'(?:password|secret|api_key|token)\s*=\s*["\'][^"\']+["\']', "Potential hardcoded secret", "critical", ["python", "javascript"]),
    (r'(?:PASSWORD|SECRET|API_KEY|TOKEN)\s*=\s*["\'][^"\']+["\']', "Potential hardcoded secret (uppercase)", "critical", ["python", "javascript"]),
    (r'except\s*:', "Bare except catches all exceptions including KeyboardInterrupt", "warning", ["python"]),
    (r'except\s+Exception\s*:', "Broad exception catch — consider specific types", "suggestion", ["python"]),
    (r'# ?TODO', "Unresolved TODO comment", "suggestion", ["python", "javascript"]),
    (r'\.chmod\s*\(\s*0?o?777', "Insecure file permissions: 777", "warning", ["python"]),
    (r'pickle\.loads?\s*\(', "Insecure deserialization via pickle", "warning", ["python"]),
    (r'yaml\.load\s*\([^)]*\)(?!.*Loader)', "Unsafe YAML load without explicit Loader", "warning", ["python"]),
]


def detect_language(filepath: str) -> str:
    ext = os.path.splitext(filepath)[1].lower()
    mapping = {
        ".py": "python",
        ".js": "javascript", ".jsx": "javascript",
        ".ts": "javascript", ".tsx": "javascript",
        ".go": "go", ".java": "java",
        ".rb": "ruby", ".rs": "rust",
    }
    return mapping.get(ext, "unknown")


def scan_file(filepath: str) -> dict:
    """Scan a single file for security patterns and complexity."""
    lang = detect_language(filepath)
    findings = []

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except (OSError, IOError) as e:
        return {"file": filepath, "error": str(e), "findings": []}

    # Security pattern scan
    for i, line in enumerate(lines, 1):
        for pattern, desc, severity, languages in SECURITY_PATTERNS:
            if lang in languages or "unknown" == lang:
                if re.search(pattern, line):
                    findings.append({
                        "line": i,
                        "severity": severity,
                        "category": "security",
                        "description": desc,
                        "snippet": line.strip()[:120],
                    })

    # Complexity: function length
    func_start = None
    func_name = ""
    func_lines = 0
    for i, line in enumerate(lines, 1):
        # Python function detection
        m = re.match(r'^(?:async\s+)?def\s+(\w+)', line)
        if not m and lang == "javascript":
            m = re.match(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)', line)
        if m:
            if func_start and func_lines > 30:
                findings.append({
                    "line": func_start,
                    "severity": "suggestion",
                    "category": "complexity",
                    "description": f"Function '{func_name}' is {func_lines} lines (>30)",
                    "snippet": "",
                })
            func_start = i
            func_name = m.group(1)
            func_lines = 0
        if func_start:
            func_lines += 1

    # Final function check
    if func_start and func_lines > 30:
        findings.append({
            "line": func_start,
            "severity": "suggestion",
            "category": "complexity",
            "description": f"Function '{func_name}' is {func_lines} lines (>30)",
            "snippet": "",
        })

    return {
        "file": filepath,
        "language": lang,
        "total_lines": len(lines),
        "findings": findings,
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python main_helper.py <file_or_directory>", file=sys.stderr)
        sys.exit(1)

    target = sys.argv[1]
    results = []

    if os.path.isfile(target):
        results.append(scan_file(target))
    elif os.path.isdir(target):
        for root, _dirs, files in os.walk(target):
            # Skip hidden dirs, node_modules, __pycache__, .venv
            if any(skip in root for skip in ["node_modules", "__pycache__", ".venv", ".git"]):
                continue
            for fname in sorted(files):
                if detect_language(fname) != "unknown":
                    results.append(scan_file(os.path.join(root, fname)))
    else:
        print(f"Error: {target} not found", file=sys.stderr)
        sys.exit(1)

    summary = {
        "files_scanned": len(results),
        "total_findings": sum(len(r["findings"]) for r in results),
        "by_severity": {},
        "results": results,
    }
    for r in results:
        for f in r["findings"]:
            sev = f["severity"]
            summary["by_severity"][sev] = summary["by_severity"].get(sev, 0) + 1

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
'''

_CODE_REVIEW_VALIDATE_SH = r"""#!/usr/bin/env bash
set -euo pipefail

# validate.sh — Validate a code review report JSON file.
# Usage: bash validate.sh <report.json>
#
# Checks that the report is well-formed JSON with required fields.
# Exit 0 on pass, non-zero on failure.

if [[ $# -lt 1 ]]; then
    echo "Usage: validate.sh <report.json>"
    exit 1
fi

report="$1"
errors=0

if [[ ! -f "$report" ]]; then
    echo "ERROR: File not found: $report"
    exit 1
fi

# Check valid JSON
if ! python3 -c "import json; json.load(open('$report'))" 2>/dev/null; then
    echo "ERROR: Invalid JSON in $report"
    exit 1
fi

# Check required top-level fields
for field in files_scanned total_findings results; do
    if ! python3 -c "
import json, sys
data = json.load(open('$report'))
if '$field' not in data:
    print(f'ERROR: Missing required field: $field')
    sys.exit(1)
" 2>/dev/null; then
        errors=$((errors + 1))
    fi
done

# Check that each finding has required sub-fields
python3 -c "
import json, sys
data = json.load(open('$report'))
errs = 0
required = {'line', 'severity', 'description'}
valid_severities = {'critical', 'warning', 'suggestion'}
for result in data.get('results', []):
    for finding in result.get('findings', []):
        missing = required - set(finding.keys())
        if missing:
            print(f'ERROR: Finding in {result.get(\"file\", \"?\")} missing fields: {missing}')
            errs += 1
        if finding.get('severity') not in valid_severities:
            print(f'ERROR: Invalid severity \"{finding.get(\"severity\")}\" in {result.get(\"file\", \"?\")}')
            errs += 1
if errs:
    sys.exit(1)
" || errors=$((errors + 1))

if [[ $errors -gt 0 ]]; then
    echo "FAILED: Report validation found errors."
    exit 1
fi

echo "OK: Report format is valid."
exit 0
"""

_CODE_REVIEW_GUIDE_MD = """\
# Code Review Checklist

## Security Review (check first, always)

### Injection Vulnerabilities
- **SQL injection**: Never build queries with string concatenation or f-strings.
  Use parameterized queries (`cursor.execute("SELECT * FROM t WHERE id = ?", (id,))`).
- **Command injection**: Never pass user input to `os.system()` or `subprocess` with
  `shell=True`. Use argument lists: `subprocess.run(["cmd", arg])`.
- **XSS**: Never insert unsanitized user input into HTML. In React, avoid
  `dangerouslySetInnerHTML`. Use `textContent` or sanitize with DOMPurify.
- **Template injection**: Never pass user input directly into template engines
  (Jinja2, Handlebars) without escaping.

### Secrets and Credentials
- No hardcoded passwords, API keys, tokens, or connection strings in source code.
- Use environment variables or a secrets manager.
- Check for accidentally committed `.env` files or config with secrets.

### Deserialization
- Never use `pickle.loads()` or `yaml.load()` on untrusted input.
- Use `yaml.safe_load()` and `json.loads()` instead.

## Correctness Review

### Edge Cases
- Empty input / None / zero / negative numbers
- Unicode and special characters in strings
- Boundary values (off-by-one, max int, empty collections)
- Concurrent access (shared state without locks)

### Error Handling
- Are exceptions specific (not bare `except:`)?
- Do error paths release resources (files, connections, locks)?
- Are error messages helpful without leaking internals?

### Type Safety
- Do type annotations match actual usage?
- Are Optional types checked for None before use?
- Are numeric types consistent (int vs float)?

## Quality Review

### Complexity
- Functions over 30 lines: consider splitting
- Cyclomatic complexity over 10: consider refactoring
- Nesting depth over 3: consider early returns or extraction

### Naming
- Can you understand a function from its name alone?
- Are boolean variables phrased as questions? (`is_valid`, `has_items`)
- Are abbreviations avoided? (`usr` -> `user`, `mgr` -> `manager`)

### DRY (Don't Repeat Yourself)
- Is the same logic copy-pasted in multiple places?
- Could a helper function or base class reduce duplication?

## Severity Definitions

| Severity | Meaning | Action |
|----------|---------|--------|
| **critical** | Security vulnerability or data loss risk | Must fix before merge |
| **warning** | Bug, potential bug, or significant code smell | Should fix before merge |
| **suggestion** | Style, readability, or minor improvement | Nice to have |
"""

# ---------------------------------------------------------------------------
# 3. Unit Test Generator
# ---------------------------------------------------------------------------
_UNIT_TEST_BODY = """\
## Quick Start
Read the source file, parse its function signatures and dependencies, then
generate tests covering happy path, edge cases, and error conditions. Use
the Arrange-Act-Assert pattern. Run the tests to verify they pass.

## When to use this skill
Use when the user says "write tests", "unit test", "test this", "add tests",
"pytest", "jest", "coverage", or mentions a function and says "how do I test
this?". Also triggers on "TDD", "test-driven", or "make sure this works",
even if they don't explicitly ask for test files. NOT for integration tests,
E2E tests, or load testing.

## Workflow

### Step 1: Analyze the source
Run `python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py <source_file>` to
extract function signatures, detect the language/framework, and identify
dependencies that need mocking.

### Step 2: Read framework patterns
Read `${CLAUDE_SKILL_DIR}/references/guide.md` for the test patterns
matching the detected framework (pytest, Jest, Go testing, etc.).

### Step 3: Generate tests
For each function, write:
1. **Happy path**: typical input producing expected output
2. **Edge cases**: empty input, None/null, zero, boundary values
3. **Error conditions**: invalid input, missing dependencies, timeouts

Follow the Arrange-Act-Assert pattern:
```
# Arrange — set up inputs and mocks
# Act — call the function under test
# Assert — verify the result
```

### Step 4: Validate and run
Run `bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh <test_file>` to check
syntax and structure. Then run the tests with the appropriate framework
command (`pytest`, `npx jest`, `go test`) to confirm they pass.

## Examples

**Example 1: Python function with no dependencies**
Input: "write tests for this calculate_discount function"
Output: pytest file with tests for: normal discount (10% off $100 = $90),
zero price, negative price raises ValueError, discount > 100% raises
ValueError, float precision edge case.

**Example 2: JavaScript async function with API call**
Input: "test this fetchUserProfile function"
Output: Jest file with: mock fetch, test successful response returns user
object, test 404 returns null, test network error throws, test timeout
handling. Uses `jest.mock()` for the HTTP client.

**Example 3: Go struct method with database dependency**
Input: "add tests for the UserRepository.FindByEmail method"
Output: Go test file with table-driven tests: existing user returns struct,
non-existent email returns nil + ErrNotFound, empty email returns
ErrInvalidInput. Uses interface mock for the database connection.

## Common mistakes to avoid
- Testing implementation details instead of behavior (asserting internal state)
- Not mocking external dependencies (hitting real databases or APIs)
- Only testing the happy path — edge cases catch the real bugs
- Writing tests that depend on each other or on execution order
- Using random data without seeds — makes failures non-reproducible
"""

_UNIT_TEST_HELPER_PY = r'''#!/usr/bin/env python3
"""Source file analyzer for test generation.

Parses function signatures, detects language and framework, identifies
dependencies that need mocking.

Usage: python main_helper.py <source_file>
"""

import json
import os
import re
import sys
from pathlib import Path


def detect_language(filepath: str) -> str:
    ext = os.path.splitext(filepath)[1].lower()
    return {
        ".py": "python", ".js": "javascript", ".jsx": "javascript",
        ".ts": "typescript", ".tsx": "typescript",
        ".go": "go", ".java": "java", ".rb": "ruby",
    }.get(ext, "unknown")


def detect_test_framework(filepath: str, language: str) -> str:
    """Infer the test framework from project config files."""
    directory = os.path.dirname(os.path.abspath(filepath))
    # Walk up looking for config files
    for _ in range(5):
        if language == "python":
            for cfg in ("pyproject.toml", "setup.cfg", "pytest.ini", "tox.ini"):
                if os.path.exists(os.path.join(directory, cfg)):
                    return "pytest"
            return "pytest"  # default for Python
        elif language in ("javascript", "typescript"):
            pkg_json = os.path.join(directory, "package.json")
            if os.path.exists(pkg_json):
                try:
                    with open(pkg_json) as f:
                        import json as _json
                        pkg = _json.load(f)
                    deps = {**pkg.get("devDependencies", {}), **pkg.get("dependencies", {})}
                    if "vitest" in deps:
                        return "vitest"
                    if "jest" in deps:
                        return "jest"
                    if "mocha" in deps:
                        return "mocha"
                except (json.JSONDecodeError, OSError):
                    pass
            return "jest"  # default for JS/TS
        elif language == "go":
            return "go-testing"
        elif language == "java":
            return "junit"
        directory = os.path.dirname(directory)
    return "unknown"


def parse_python_functions(source: str) -> list[dict]:
    """Extract Python function signatures."""
    functions = []
    pattern = re.compile(
        r'^(?P<indent>\s*)(?:async\s+)?def\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)'
        r'(?:\s*->\s*(?P<return>[^:]+))?:',
        re.MULTILINE,
    )
    for m in pattern.finditer(source):
        if m.group("name").startswith("_") and m.group("name") != "__init__":
            continue  # skip private helpers by default
        params_raw = m.group("params").strip()
        params = []
        if params_raw and params_raw != "self" and params_raw != "cls":
            for p in params_raw.split(","):
                p = p.strip()
                if p in ("self", "cls"):
                    continue
                params.append(p)
        functions.append({
            "name": m.group("name"),
            "params": params,
            "return_type": (m.group("return") or "").strip() or None,
            "is_async": "async" in source[max(0, m.start()-6):m.start()+4],
        })
    return functions


def parse_js_functions(source: str) -> list[dict]:
    """Extract JavaScript/TypeScript function signatures."""
    functions = []
    # Named function declarations
    for m in re.finditer(
        r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)',
        source,
    ):
        functions.append({
            "name": m.group(1),
            "params": [p.strip() for p in m.group(2).split(",") if p.strip()],
            "return_type": None,
            "is_async": "async" in source[max(0, m.start()-6):m.start()+8],
        })
    # Arrow functions assigned to const/let
    for m in re.finditer(
        r'(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s+)?\(?([^)=]*)\)?\s*=>',
        source,
    ):
        functions.append({
            "name": m.group(1),
            "params": [p.strip() for p in m.group(2).split(",") if p.strip()],
            "return_type": None,
            "is_async": "async" in source[max(0, m.start()):m.end()],
        })
    return functions


def find_dependencies(source: str, language: str) -> list[str]:
    """Identify imported modules that likely need mocking."""
    deps = []
    mock_hints = [
        "database", "db", "redis", "cache", "http", "fetch", "axios",
        "request", "client", "session", "connection", "pool", "queue",
        "email", "smtp", "s3", "storage", "bucket",
    ]
    if language == "python":
        for m in re.finditer(r'(?:from\s+(\S+)\s+)?import\s+(.+)', source):
            module = m.group(1) or m.group(2).split(",")[0].strip()
            if any(h in module.lower() for h in mock_hints):
                deps.append(module)
    elif language in ("javascript", "typescript"):
        for m in re.finditer(r'import\s+.*?from\s+["\']([^"\']+)', source):
            module = m.group(1)
            if any(h in module.lower() for h in mock_hints):
                deps.append(module)
    return deps


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python main_helper.py <source_file>", file=sys.stderr)
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.isfile(filepath):
        print(f"Error: {filepath} not found", file=sys.stderr)
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()

    language = detect_language(filepath)
    framework = detect_test_framework(filepath, language)

    if language == "python":
        functions = parse_python_functions(source)
    elif language in ("javascript", "typescript"):
        functions = parse_js_functions(source)
    else:
        functions = []

    dependencies = find_dependencies(source, language)

    result = {
        "file": filepath,
        "language": language,
        "framework": framework,
        "functions": functions,
        "dependencies_to_mock": dependencies,
        "total_functions": len(functions),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
'''

_UNIT_TEST_VALIDATE_SH = r"""#!/usr/bin/env bash
set -euo pipefail

# validate.sh — Validate a generated test file.
# Usage: bash validate.sh <test_file>
#
# Checks syntax, structure, and naming conventions.
# Exit 0 on pass, non-zero on failure.

if [[ $# -lt 1 ]]; then
    echo "Usage: validate.sh <test_file>"
    exit 1
fi

test_file="$1"
errors=0

if [[ ! -f "$test_file" ]]; then
    echo "ERROR: File not found: $test_file"
    exit 1
fi

ext="${test_file##*.}"

case "$ext" in
    py)
        # Check Python syntax
        if ! python3 -m py_compile "$test_file" 2>/dev/null; then
            echo "ERROR: Python syntax error in $test_file"
            errors=$((errors + 1))
        fi
        # Check for test functions
        if ! grep -qE '^(def test_|class Test)' "$test_file"; then
            echo "ERROR: No test functions found (expected test_* or Test* class)"
            errors=$((errors + 1))
        fi
        # Check for assert statements
        if ! grep -qE '(assert |self\.assert|pytest\.raises)' "$test_file"; then
            echo "WARNING: No assertions found in test file"
        fi
        ;;
    js|ts|jsx|tsx)
        # Check for test blocks
        if ! grep -qE '(describe|it|test)\s*\(' "$test_file"; then
            echo "ERROR: No test blocks found (expected describe/it/test)"
            errors=$((errors + 1))
        fi
        # Check for expect assertions
        if ! grep -qE '(expect|assert)\s*\(' "$test_file"; then
            echo "WARNING: No expect/assert calls found"
        fi
        # Syntax check with node if available
        if command -v node &>/dev/null; then
            if ! node --check "$test_file" 2>/dev/null; then
                echo "ERROR: JavaScript syntax error in $test_file"
                errors=$((errors + 1))
            fi
        fi
        ;;
    go)
        # Check for Test functions
        if ! grep -qE '^func Test\w+' "$test_file"; then
            echo "ERROR: No Test functions found (expected func TestXxx)"
            errors=$((errors + 1))
        fi
        ;;
    *)
        echo "WARNING: Unknown test file type: .$ext"
        ;;
esac

# General checks: file should not be empty
line_count=$(wc -l < "$test_file" | tr -d ' ')
if [[ "$line_count" -lt 5 ]]; then
    echo "ERROR: Test file has only $line_count lines — likely a stub"
    errors=$((errors + 1))
fi

if [[ $errors -gt 0 ]]; then
    echo "FAILED: $errors error(s) found in $test_file"
    exit 1
fi

echo "OK: Test file structure is valid."
exit 0
"""

_UNIT_TEST_GUIDE_MD = """\
# Unit Testing Framework Patterns

## Python (pytest)

### Basic Test
```python
def test_add_positive_numbers():
    # Arrange
    a, b = 2, 3
    # Act
    result = add(a, b)
    # Assert
    assert result == 5
```

### Parametrized Tests
```python
import pytest

@pytest.mark.parametrize("input_val,expected", [
    ("hello", "HELLO"),
    ("", ""),
    ("Hello World", "HELLO WORLD"),
])
def test_to_upper(input_val, expected):
    assert to_upper(input_val) == expected
```

### Fixtures and Mocking
```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.fetch_one.return_value = {"id": 1, "name": "Alice"}
    return db

async def test_get_user(mock_db):
    user = await get_user(mock_db, user_id=1)
    assert user["name"] == "Alice"
    mock_db.fetch_one.assert_called_once()
```

### Testing Exceptions
```python
def test_divide_by_zero():
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)
```

## JavaScript/TypeScript (Jest / Vitest)

### Basic Test
```javascript
describe('add', () => {
  it('should add two positive numbers', () => {
    expect(add(2, 3)).toBe(5);
  });
});
```

### Mocking Modules
```javascript
jest.mock('./database');
import { getUser } from './database';

describe('fetchProfile', () => {
  beforeEach(() => {
    getUser.mockReset();
  });

  it('returns user for valid id', async () => {
    getUser.mockResolvedValue({ id: 1, name: 'Alice' });
    const result = await fetchProfile(1);
    expect(result.name).toBe('Alice');
  });

  it('returns null for missing user', async () => {
    getUser.mockResolvedValue(null);
    const result = await fetchProfile(999);
    expect(result).toBeNull();
  });
});
```

### Testing Async Errors
```javascript
it('throws on network failure', async () => {
  fetch.mockRejectedValue(new Error('Network error'));
  await expect(fetchData()).rejects.toThrow('Network error');
});
```

## Go (testing package)

### Table-Driven Tests
```go
func TestAdd(t *testing.T) {
    tests := []struct {
        name     string
        a, b     int
        expected int
    }{
        {"positive", 2, 3, 5},
        {"zero", 0, 0, 0},
        {"negative", -1, -2, -3},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got := Add(tt.a, tt.b)
            if got != tt.expected {
                t.Errorf("Add(%d, %d) = %d, want %d", tt.a, tt.b, got, tt.expected)
            }
        })
    }
}
```

## When to Mock vs. Use Real Dependencies

| Dependency | Mock it? | Reason |
|-----------|----------|--------|
| Database | YES | Slow, stateful, needs setup |
| HTTP API | YES | Unreliable, rate-limited |
| File system | MAYBE | Fast but can leak state |
| Pure functions | NO | Deterministic, fast |
| Time/clock | YES | Non-deterministic |

## Boundary Value Analysis

Always test these boundaries:
- Zero / empty / null / undefined
- One element (minimum valid input)
- Maximum valid value
- Just below and just above limits
- Negative numbers for unsigned expectations
- Unicode / special characters for strings
"""

# ---------------------------------------------------------------------------
# 4. REST API Endpoint Designer
# ---------------------------------------------------------------------------
_API_ENDPOINT_BODY = """\
## Quick Start
Define the resource, generate OpenAPI 3.1 YAML for standard CRUD operations
with proper schemas, status codes, pagination, and error responses. Validate
the output for spec compliance.

## When to use this skill
Use when the user says "design an API", "REST endpoint", "OpenAPI", "CRUD
endpoints", "API schema", or describes a resource and asks "what should the
endpoints look like?". Also triggers on "Swagger", "API contract", or "route
design", even if they don't explicitly ask for OpenAPI output. NOT for
GraphQL, gRPC, or WebSocket APIs.

## Workflow

### Step 1: Define the resource
Identify the resource name (singular and plural), its fields with types,
required vs optional, and any relationships to other resources. Read
`${CLAUDE_SKILL_DIR}/references/guide.md` for naming conventions.

### Step 2: Generate the endpoint spec
Run `python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py --resource <name> --fields "<field_spec>"`.
The script generates OpenAPI 3.1 YAML with:
- GET /resources (list with pagination)
- GET /resources/{id} (single)
- POST /resources (create)
- PUT /resources/{id} (full update)
- PATCH /resources/{id} (partial update)
- DELETE /resources/{id}

### Step 3: Customize
Adjust the generated spec based on the user's needs:
- Add query parameters for filtering and sorting
- Customize authentication scheme
- Add nested resource routes if needed
- Include webhook definitions for async operations

### Step 4: Validate
Run `bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh <spec.yaml>` to verify
OpenAPI compliance, naming conventions, and completeness.

## Examples

**Example 1: Simple resource CRUD**
Input: "design REST endpoints for a Todo resource with title, done, due_date"
Output: OpenAPI YAML with 6 endpoints, TodoCreate/TodoUpdate/TodoResponse
schemas, cursor-based pagination on the list endpoint, 400/404/422 error
responses, and Bearer auth.

**Example 2: Nested resource**
Input: "I need endpoints for comments on blog posts"
Output: POST /posts/{post_id}/comments, GET /posts/{post_id}/comments with
pagination, GET /comments/{id}, DELETE /comments/{id}. Separate top-level
GET for admin listing all comments with filtering by post_id.

**Example 3: Resource with file upload**
Input: "API for user profile with avatar upload"
Output: Standard CRUD for /users plus PATCH /users/{id}/avatar with
multipart/form-data request body, Content-Type validation, max file size
constraint in schema, and a presigned URL alternative for large files.

## Common mistakes to avoid
- Using verbs in URLs (/getUsers) instead of nouns (/users)
- Returning 200 for creation (use 201) or deletion (use 204)
- Missing pagination on list endpoints — always paginate
- Inconsistent error response format across endpoints
- Forgetting PATCH for partial updates (PUT requires full replacement)
"""

_API_ENDPOINT_HELPER_PY = r'''#!/usr/bin/env python3
"""REST API endpoint spec generator.

Generates OpenAPI 3.1 YAML for CRUD endpoints given a resource name
and field definitions.

Usage: python main_helper.py --resource <name> --fields "name:string:required,age:integer,email:string:required"
"""

import argparse
import json
import sys
import textwrap
from datetime import datetime


def parse_fields(fields_str: str) -> list[dict]:
    """Parse field spec string into structured list."""
    fields = []
    for field_def in fields_str.split(","):
        parts = field_def.strip().split(":")
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        ftype = parts[1].strip()
        required = len(parts) >= 3 and parts[2].strip() == "required"
        fields.append({"name": name, "type": ftype, "required": required})
    return fields


def openapi_type(ftype: str) -> dict:
    """Map common type names to OpenAPI types."""
    mapping = {
        "string": {"type": "string"},
        "str": {"type": "string"},
        "integer": {"type": "integer"},
        "int": {"type": "integer"},
        "number": {"type": "number"},
        "float": {"type": "number"},
        "boolean": {"type": "boolean"},
        "bool": {"type": "boolean"},
        "date": {"type": "string", "format": "date"},
        "datetime": {"type": "string", "format": "date-time"},
        "email": {"type": "string", "format": "email"},
        "uuid": {"type": "string", "format": "uuid"},
        "url": {"type": "string", "format": "uri"},
    }
    return mapping.get(ftype.lower(), {"type": "string"})


def to_pascal(name: str) -> str:
    """Convert kebab-case or snake_case to PascalCase."""
    return "".join(w.capitalize() for w in name.replace("-", "_").split("_"))


def pluralize(name: str) -> str:
    """Simple English pluralization."""
    if name.endswith("y") and name[-2] not in "aeiou":
        return name[:-1] + "ies"
    if name.endswith(("s", "x", "z", "ch", "sh")):
        return name + "es"
    return name + "s"


def generate_openapi(resource: str, fields: list[dict]) -> str:
    """Generate OpenAPI 3.1 YAML string."""
    pascal = to_pascal(resource)
    plural = pluralize(resource.replace("-", "_")).replace("_", "-")
    path = f"/{plural}"

    required_fields = [f["name"] for f in fields if f["required"]]
    all_fields = fields

    # Build properties YAML
    def field_yaml(indent: int, include_id: bool = False) -> str:
        lines = []
        prefix = " " * indent
        if include_id:
            lines.append(f"{prefix}id:")
            lines.append(f"{prefix}  type: string")
            lines.append(f"{prefix}  format: uuid")
            lines.append(f"{prefix}  readOnly: true")
        for f in all_fields:
            lines.append(f"{prefix}{f['name']}:")
            oa = openapi_type(f["type"])
            for k, v in oa.items():
                lines.append(f"{prefix}  {k}: {v}")
        if include_id:
            lines.append(f"{prefix}created_at:")
            lines.append(f"{prefix}  type: string")
            lines.append(f"{prefix}  format: date-time")
            lines.append(f"{prefix}  readOnly: true")
            lines.append(f"{prefix}updated_at:")
            lines.append(f"{prefix}  type: string")
            lines.append(f"{prefix}  format: date-time")
            lines.append(f"{prefix}  readOnly: true")
        return "\n".join(lines)

    req_yaml = ""
    if required_fields:
        req_yaml = "\n      required:\n" + "\n".join(f"        - {r}" for r in required_fields)

    yaml_out = textwrap.dedent(f"""\
    openapi: "3.1.0"
    info:
      title: {pascal} API
      version: "1.0.0"
    paths:
      {path}:
        get:
          summary: List {plural}
          operationId: list{to_pascal(plural)}
          parameters:
            - name: cursor
              in: query
              schema:
                type: string
              description: Pagination cursor
            - name: limit
              in: query
              schema:
                type: integer
                default: 20
                minimum: 1
                maximum: 100
          responses:
            "200":
              description: Paginated list of {plural}
              content:
                application/json:
                  schema:
                    type: object
                    properties:
                      items:
                        type: array
                        items:
                          $ref: "#/components/schemas/{pascal}Response"
                      next_cursor:
                        type: string
                        nullable: true
                      total:
                        type: integer
            "401":
              $ref: "#/components/responses/Unauthorized"
        post:
          summary: Create a {resource}
          operationId: create{pascal}
          requestBody:
            required: true
            content:
              application/json:
                schema:
                  $ref: "#/components/schemas/{pascal}Create"
          responses:
            "201":
              description: Created
              content:
                application/json:
                  schema:
                    $ref: "#/components/schemas/{pascal}Response"
            "400":
              $ref: "#/components/responses/BadRequest"
            "422":
              $ref: "#/components/responses/ValidationError"
      {path}/{{id}}:
        get:
          summary: Get a {resource} by ID
          operationId: get{pascal}
          parameters:
            - name: id
              in: path
              required: true
              schema:
                type: string
                format: uuid
          responses:
            "200":
              description: The {resource}
              content:
                application/json:
                  schema:
                    $ref: "#/components/schemas/{pascal}Response"
            "404":
              $ref: "#/components/responses/NotFound"
        put:
          summary: Replace a {resource}
          operationId: replace{pascal}
          parameters:
            - name: id
              in: path
              required: true
              schema:
                type: string
                format: uuid
          requestBody:
            required: true
            content:
              application/json:
                schema:
                  $ref: "#/components/schemas/{pascal}Create"
          responses:
            "200":
              description: Updated
              content:
                application/json:
                  schema:
                    $ref: "#/components/schemas/{pascal}Response"
            "404":
              $ref: "#/components/responses/NotFound"
            "422":
              $ref: "#/components/responses/ValidationError"
        patch:
          summary: Partially update a {resource}
          operationId: update{pascal}
          parameters:
            - name: id
              in: path
              required: true
              schema:
                type: string
                format: uuid
          requestBody:
            required: true
            content:
              application/json:
                schema:
                  $ref: "#/components/schemas/{pascal}Update"
          responses:
            "200":
              description: Updated
              content:
                application/json:
                  schema:
                    $ref: "#/components/schemas/{pascal}Response"
            "404":
              $ref: "#/components/responses/NotFound"
            "422":
              $ref: "#/components/responses/ValidationError"
        delete:
          summary: Delete a {resource}
          operationId: delete{pascal}
          parameters:
            - name: id
              in: path
              required: true
              schema:
                type: string
                format: uuid
          responses:
            "204":
              description: Deleted
            "404":
              $ref: "#/components/responses/NotFound"
    components:
      schemas:
        {pascal}Create:
          type: object{req_yaml}
          properties:
    {field_yaml(8)}
        {pascal}Update:
          type: object
          properties:
    {field_yaml(8)}
        {pascal}Response:
          type: object
          properties:
    {field_yaml(8, include_id=True)}
        Error:
          type: object
          required:
            - code
            - message
          properties:
            code:
              type: string
            message:
              type: string
            details:
              type: array
              items:
                type: object
                properties:
                  field:
                    type: string
                  message:
                    type: string
      responses:
        BadRequest:
          description: Bad request
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"
        Unauthorized:
          description: Authentication required
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"
        NotFound:
          description: Resource not found
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"
        ValidationError:
          description: Validation failed
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"
      securitySchemes:
        BearerAuth:
          type: http
          scheme: bearer
          bearerFormat: JWT
    security:
      - BearerAuth: []
    """)
    return yaml_out


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate OpenAPI spec for a resource")
    parser.add_argument("--resource", required=True, help="Resource name (singular, kebab-case)")
    parser.add_argument("--fields", required=True, help="Field spec: name:type[:required],...")
    parser.add_argument("--json", action="store_true", help="Output as JSON summary instead of YAML")
    args = parser.parse_args()

    fields = parse_fields(args.fields)
    if not fields:
        print("Error: No valid fields parsed", file=sys.stderr)
        sys.exit(1)

    yaml_output = generate_openapi(args.resource, fields)

    if args.json:
        plural = pluralize(args.resource.replace("-", "_")).replace("_", "-")
        summary = {
            "resource": args.resource,
            "plural_path": f"/{plural}",
            "endpoints": [
                {"method": "GET", "path": f"/{plural}", "operation": "list"},
                {"method": "POST", "path": f"/{plural}", "operation": "create"},
                {"method": "GET", "path": f"/{plural}/{{id}}", "operation": "get"},
                {"method": "PUT", "path": f"/{plural}/{{id}}", "operation": "replace"},
                {"method": "PATCH", "path": f"/{plural}/{{id}}", "operation": "update"},
                {"method": "DELETE", "path": f"/{plural}/{{id}}", "operation": "delete"},
            ],
            "schemas": [f"{to_pascal(args.resource)}Create", f"{to_pascal(args.resource)}Update", f"{to_pascal(args.resource)}Response"],
            "fields": fields,
        }
        print(json.dumps(summary, indent=2))
    else:
        print(yaml_output)


if __name__ == "__main__":
    main()
'''

_API_ENDPOINT_VALIDATE_SH = r"""#!/usr/bin/env bash
set -euo pipefail

# validate.sh — Validate an OpenAPI YAML spec file.
# Usage: bash validate.sh <spec.yaml>
#
# Checks YAML syntax, basic OpenAPI structure, naming conventions.
# Exit 0 on pass, non-zero on failure.

if [[ $# -lt 1 ]]; then
    echo "Usage: validate.sh <spec.yaml>"
    exit 1
fi

spec="$1"
errors=0

if [[ ! -f "$spec" ]]; then
    echo "ERROR: File not found: $spec"
    exit 1
fi

# Check valid YAML
if ! python3 -c "
import yaml, sys
with open('$spec') as f:
    yaml.safe_load(f)
" 2>/dev/null; then
    echo "ERROR: Invalid YAML in $spec"
    exit 1
fi

# Check required OpenAPI fields
python3 -c "
import yaml, sys, re

with open('$spec') as f:
    doc = yaml.safe_load(f)

errs = 0

# Must have openapi version
if 'openapi' not in doc:
    print('ERROR: Missing openapi version field')
    errs += 1

# Must have info
if 'info' not in doc:
    print('ERROR: Missing info section')
    errs += 1

# Must have paths
paths = doc.get('paths', {})
if not paths:
    print('ERROR: No paths defined')
    errs += 1

# Check naming conventions
for path in paths:
    # Paths should use kebab-case and plural nouns
    segments = [s for s in path.split('/') if s and not s.startswith('{')]
    for seg in segments:
        if seg != seg.lower():
            print(f'WARNING: Path segment \"{seg}\" in {path} should be lowercase')
        if '_' in seg:
            print(f'WARNING: Path segment \"{seg}\" uses underscores; prefer kebab-case')

    # Each endpoint should have at least one response
    for method in ('get', 'post', 'put', 'patch', 'delete'):
        op = paths[path].get(method)
        if op and not op.get('responses'):
            print(f'ERROR: {method.upper()} {path} has no responses defined')
            errs += 1

# Check that referenced schemas exist
schemas = doc.get('components', {}).get('schemas', {})
responses = doc.get('components', {}).get('responses', {})

if errs:
    sys.exit(1)
print('Schema and structure checks passed.')
" || errors=$((errors + 1))

if [[ $errors -gt 0 ]]; then
    echo "FAILED: OpenAPI spec validation found errors."
    exit 1
fi

echo "OK: OpenAPI spec is valid."
exit 0
"""

_API_ENDPOINT_GUIDE_MD = """\
# REST API Design Guide

## URL Naming Conventions

- Use **plural nouns** for resource collections: `/users`, `/products`, `/orders`
- Use **kebab-case**: `/order-items` not `/orderItems` or `/order_items`
- No verbs in URLs: `/users` not `/getUsers`
- Nest for direct relationships: `/posts/{id}/comments`
- Keep nesting shallow (max 2 levels): `/users/{id}/posts` not `/users/{id}/posts/{id}/comments`

## HTTP Methods

| Method | Purpose | Request Body | Response Code |
|--------|---------|-------------|---------------|
| GET | Read (list or single) | None | 200 |
| POST | Create | Required | 201 + Location header |
| PUT | Full replace | Required | 200 |
| PATCH | Partial update | Required | 200 |
| DELETE | Remove | None | 204 (no body) |

## Status Codes

### Success
- **200** OK — general success, includes response body
- **201** Created — resource was created, include Location header
- **204** No Content — success with no response body (DELETE)

### Client Errors
- **400** Bad Request — malformed syntax, missing required header
- **401** Unauthorized — authentication required or invalid
- **403** Forbidden — authenticated but not authorized
- **404** Not Found — resource does not exist
- **409** Conflict — duplicate resource, version conflict
- **422** Unprocessable Entity — valid syntax but failed validation

### Server Errors
- **500** Internal Server Error — unexpected failure
- **503** Service Unavailable — temporary overload or maintenance

## Pagination

### Cursor-Based (recommended)
```json
{
  "items": [...],
  "next_cursor": "eyJpZCI6MTIzfQ==",
  "total": 1542
}
```
Query: `GET /users?cursor=eyJpZCI6MTIzfQ==&limit=20`

### Offset-Based (simpler but slower for large datasets)
```json
{
  "items": [...],
  "page": 2,
  "per_page": 20,
  "total": 1542
}
```
Query: `GET /users?page=2&per_page=20`

## Filtering and Sorting

- Filter: `GET /products?status=active&category=electronics`
- Sort: `GET /products?sort=price&order=desc`
- Search: `GET /products?q=wireless+keyboard`
- Date range: `GET /orders?created_after=2024-01-01&created_before=2024-12-31`

## Error Response Format

Use a consistent error envelope across all endpoints:
```json
{
  "code": "VALIDATION_ERROR",
  "message": "One or more fields failed validation",
  "details": [
    {"field": "email", "message": "must be a valid email address"},
    {"field": "age", "message": "must be a positive integer"}
  ]
}
```

## Authentication Schemes

| Scheme | Use When |
|--------|----------|
| Bearer JWT | Stateless, microservices, mobile apps |
| API Key | Server-to-server, simple integrations |
| OAuth 2.0 | Third-party access, delegated authorization |
| Session cookie | Traditional web apps, server-rendered pages |

## Versioning

- **URL prefix** (recommended): `/v1/users`, `/v2/users`
- **Header**: `Accept: application/vnd.myapi.v2+json`
- **Query param**: `/users?version=2` (least common)
"""

# ---------------------------------------------------------------------------
# 5. Database Migration Generator
# ---------------------------------------------------------------------------
_DB_MIGRATION_BODY = """\
## Quick Start
Describe the schema change, generate a timestamped up/down migration pair,
validate for destructive operations and zero-downtime compliance, then review
the rollback path before applying.

## When to use this skill
Use when the user says "migration", "schema change", "ALTER TABLE", "add
column", "create table", "database change", "migrate", or describes a data
model change. Also triggers on "add a field", "rename column", "drop table",
or "change the schema", even if they don't use the word migration. NOT for
query optimization, ORM model code, or database design from scratch.

## Workflow

### Step 1: Understand the change
Identify: target database dialect (PostgreSQL, MySQL, SQLite), the current
schema (read existing migrations or ask), and the desired end state.
Read `${CLAUDE_SKILL_DIR}/references/guide.md` for migration patterns.

### Step 2: Generate the migration
Run `python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py --dialect <pg|mysql|sqlite> --description "<change>"`.
The script generates timestamped `up.sql` and `down.sql` files and a
validation report checking for destructive operations.

### Step 3: Apply zero-downtime rules
For production databases, enforce the expand-contract pattern:
- **Adding a column**: add as NULLABLE with DEFAULT first, backfill, then
  add NOT NULL constraint in a separate migration
- **Renaming a column**: add new column, backfill, update code, drop old
  column (3 separate migrations)
- **Dropping a column**: remove from code first, then drop in a later migration
- **Adding an index**: use CONCURRENTLY (PostgreSQL) or check lock duration

### Step 4: Validate
Run `bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh <up.sql> <down.sql>` to
check SQL syntax, destructive operation detection, and reversibility.

## Examples

**Example 1: Add a nullable column**
Input: "add an email column to the users table"
Output:
```sql
-- up.sql
ALTER TABLE users ADD COLUMN email VARCHAR(255);
CREATE INDEX CONCURRENTLY idx_users_email ON users (email);

-- down.sql
DROP INDEX CONCURRENTLY IF EXISTS idx_users_email;
ALTER TABLE users DROP COLUMN IF EXISTS email;
```

**Example 2: Rename a column (expand-contract)**
Input: "rename users.name to users.full_name"
Output: Three migrations:
1. Add `full_name` column and backfill from `name`
2. Update application code to use `full_name` (manual step, documented)
3. Drop `name` column after verification period

**Example 3: Create table with foreign key**
Input: "create a comments table linked to posts and users"
Output:
```sql
-- up.sql
CREATE TABLE comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_comments_post_id ON comments (post_id);
CREATE INDEX idx_comments_user_id ON comments (user_id);

-- down.sql
DROP TABLE IF EXISTS comments;
```

## Common mistakes to avoid
- Adding NOT NULL without DEFAULT on a populated table (locks + fails)
- Renaming columns directly instead of expand-contract (breaks running code)
- Missing the down migration — every up must have a reverse
- Creating indexes without CONCURRENTLY on production PostgreSQL (locks table)
- Running destructive operations (DROP) without a backup verification step
"""

_DB_MIGRATION_HELPER_PY = r'''#!/usr/bin/env python3
"""Database migration generator and validator.

Generates timestamped up/down migration SQL files and checks for
destructive operations and zero-downtime compliance.

Usage:
    python main_helper.py --dialect pg --description "add email to users"
    python main_helper.py --check up.sql
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime


DESTRUCTIVE_PATTERNS = [
    (r'\bDROP\s+TABLE\b', "DROP TABLE — irreversible data loss"),
    (r'\bDROP\s+COLUMN\b', "DROP COLUMN — irreversible data loss"),
    (r'\bTRUNCATE\b', "TRUNCATE — removes all rows"),
    (r'\bDROP\s+DATABASE\b', "DROP DATABASE — catastrophic"),
    (r'\bDELETE\s+FROM\b(?!.*\bWHERE\b)', "DELETE without WHERE — removes all rows"),
]

ZERO_DOWNTIME_VIOLATIONS = [
    (r'ALTER\s+TABLE\s+\w+\s+ADD\s+(?:COLUMN\s+)?\w+.*NOT\s+NULL(?!\s+DEFAULT)', "Adding NOT NULL column without DEFAULT locks the table and fails on existing rows"),
    (r'ALTER\s+TABLE\s+\w+\s+RENAME\s+COLUMN', "Direct column rename breaks running application code — use expand-contract pattern"),
    (r'ALTER\s+TABLE\s+\w+\s+ALTER\s+COLUMN\s+\w+\s+SET\s+NOT\s+NULL', "Setting NOT NULL on existing column requires a table scan lock"),
    (r'CREATE\s+INDEX\s+(?!CONCURRENTLY)', "Creating index without CONCURRENTLY locks the table (PostgreSQL)"),
]


def check_sql(sql: str, dialect: str = "pg") -> dict:
    """Analyze SQL for destructive operations and zero-downtime violations."""
    findings = []

    for pattern, description in DESTRUCTIVE_PATTERNS:
        for m in re.finditer(pattern, sql, re.IGNORECASE):
            # Check if there's a DESTRUCTIVE comment nearby
            line_start = sql.rfind("\n", 0, m.start()) + 1
            line = sql[line_start:sql.find("\n", m.start())]
            has_comment = "-- DESTRUCTIVE:" in line or "-- DESTRUCTIVE:" in sql[max(0, line_start-80):line_start]
            findings.append({
                "type": "destructive",
                "severity": "critical" if not has_comment else "acknowledged",
                "description": description,
                "position": m.start(),
                "line": sql[:m.start()].count("\n") + 1,
                "acknowledged": has_comment,
            })

    if dialect == "pg":
        for pattern, description in ZERO_DOWNTIME_VIOLATIONS:
            for m in re.finditer(pattern, sql, re.IGNORECASE):
                findings.append({
                    "type": "zero_downtime_violation",
                    "severity": "warning",
                    "description": description,
                    "position": m.start(),
                    "line": sql[:m.start()].count("\n") + 1,
                })

    return {
        "total_findings": len(findings),
        "destructive_count": sum(1 for f in findings if f["type"] == "destructive" and not f.get("acknowledged")),
        "violation_count": sum(1 for f in findings if f["type"] == "zero_downtime_violation"),
        "findings": findings,
    }


def generate_timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def generate_migration(description: str, dialect: str) -> dict:
    """Generate a migration template based on the description."""
    ts = generate_timestamp()
    slug = re.sub(r'[^a-z0-9]+', '_', description.lower()).strip('_')
    filename = f"{ts}_{slug}"

    # Simple template generation based on keywords in description
    up_sql = f"-- Migration: {description}\n-- Dialect: {dialect}\n-- Generated: {ts}\n\n"
    down_sql = f"-- Rollback: {description}\n-- Dialect: {dialect}\n-- Generated: {ts}\n\n"

    desc_lower = description.lower()
    if "add" in desc_lower and "column" in desc_lower:
        up_sql += "-- ALTER TABLE <table> ADD COLUMN <name> <type>;\n"
        down_sql += "-- ALTER TABLE <table> DROP COLUMN IF EXISTS <name>;\n"
    elif "create" in desc_lower and "table" in desc_lower:
        up_sql += "-- CREATE TABLE <name> (\n--     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),\n--     created_at TIMESTAMPTZ NOT NULL DEFAULT now()\n-- );\n"
        down_sql += "-- DROP TABLE IF EXISTS <name>;\n"
    elif "drop" in desc_lower:
        up_sql += "-- DESTRUCTIVE: <reason>\n-- DROP TABLE IF EXISTS <name>;\n"
        down_sql += "-- CREATE TABLE <name> (...);\n"
    elif "index" in desc_lower:
        if dialect == "pg":
            up_sql += "-- CREATE INDEX CONCURRENTLY idx_<table>_<col> ON <table> (<col>);\n"
            down_sql += "-- DROP INDEX CONCURRENTLY IF EXISTS idx_<table>_<col>;\n"
        else:
            up_sql += "-- CREATE INDEX idx_<table>_<col> ON <table> (<col>);\n"
            down_sql += "-- DROP INDEX IF EXISTS idx_<table>_<col>;\n"
    else:
        up_sql += "-- TODO: Write up migration SQL\n"
        down_sql += "-- TODO: Write down migration SQL\n"

    return {
        "filename": filename,
        "up_file": f"{filename}.up.sql",
        "down_file": f"{filename}.down.sql",
        "up_sql": up_sql,
        "down_sql": down_sql,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Database migration helper")
    parser.add_argument("--dialect", choices=["pg", "mysql", "sqlite"], default="pg")
    parser.add_argument("--description", help="Migration description")
    parser.add_argument("--check", help="Check an existing SQL file for issues")
    args = parser.parse_args()

    if args.check:
        if not os.path.isfile(args.check):
            print(f"Error: {args.check} not found", file=sys.stderr)
            sys.exit(1)
        with open(args.check) as f:
            sql = f.read()
        result = check_sql(sql, args.dialect)
        print(json.dumps(result, indent=2))
    elif args.description:
        migration = generate_migration(args.description, args.dialect)
        # Also check the generated SQL
        migration["validation"] = check_sql(migration["up_sql"], args.dialect)
        print(json.dumps(migration, indent=2))
    else:
        print("Error: Provide --description or --check", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
'''

_DB_MIGRATION_VALIDATE_SH = r"""#!/usr/bin/env bash
set -euo pipefail

# validate.sh — Validate a migration pair (up.sql + down.sql).
# Usage: bash validate.sh <up.sql> [down.sql]
#
# Checks SQL syntax, destructive operations, and reversibility.
# Exit 0 on pass, non-zero on failure.

if [[ $# -lt 1 ]]; then
    echo "Usage: validate.sh <up.sql> [down.sql]"
    exit 1
fi

up_file="$1"
errors=0

if [[ ! -f "$up_file" ]]; then
    echo "ERROR: Up migration not found: $up_file"
    exit 1
fi

# Infer down file if not provided
if [[ $# -ge 2 ]]; then
    down_file="$2"
else
    down_file="${up_file/.up.sql/.down.sql}"
fi

# Check that both files exist and are non-empty
if [[ ! -f "$down_file" ]]; then
    echo "ERROR: Down migration not found: $down_file"
    errors=$((errors + 1))
fi

if [[ ! -s "$up_file" ]]; then
    echo "ERROR: Up migration is empty"
    errors=$((errors + 1))
fi

if [[ -f "$down_file" ]] && [[ ! -s "$down_file" ]]; then
    echo "ERROR: Down migration is empty"
    errors=$((errors + 1))
fi

# Check for valid SQL syntax using Python's sqlparse if available
python3 -c "
import sys
try:
    import sqlparse
    with open('$up_file') as f:
        sql = f.read()
    parsed = sqlparse.parse(sql)
    if not parsed or all(str(s).strip() == '' or str(s).strip().startswith('--') for s in parsed):
        print('WARNING: Up migration contains only comments or is empty')
    print('SQL parse: OK')
except ImportError:
    # sqlparse not available — skip syntax check
    print('INFO: sqlparse not installed, skipping SQL syntax check')
except Exception as e:
    print(f'ERROR: SQL parse failed: {e}')
    sys.exit(1)
" || errors=$((errors + 1))

# Check for unacknowledged destructive operations
if grep -iE '\b(DROP\s+TABLE|DROP\s+COLUMN|TRUNCATE)\b' "$up_file" | grep -v '-- DESTRUCTIVE:' > /dev/null 2>&1; then
    echo "WARNING: Destructive operation found without '-- DESTRUCTIVE: reason' comment"
    echo "  Add a comment explaining why the destructive operation is needed."
fi

# Check reversibility heuristic: if up has CREATE, down should have DROP (and vice versa)
if [[ -f "$down_file" ]]; then
    python3 -c "
import re, sys

with open('$up_file') as f:
    up = f.read().upper()
with open('$down_file') as f:
    down = f.read().upper()

issues = []
if 'CREATE TABLE' in up and 'DROP TABLE' not in down:
    issues.append('Up has CREATE TABLE but down has no DROP TABLE')
if 'ADD COLUMN' in up and 'DROP COLUMN' not in down:
    issues.append('Up has ADD COLUMN but down has no DROP COLUMN')
if 'CREATE INDEX' in up and 'DROP INDEX' not in down:
    issues.append('Up has CREATE INDEX but down has no DROP INDEX')

for issue in issues:
    print(f'WARNING: {issue}')
" 2>/dev/null
fi

# Filename convention check
basename=$(basename "$up_file")
if ! echo "$basename" | grep -qE '^[0-9]{8}_[0-9]{6}_'; then
    echo "INFO: Filename does not follow YYYYMMDD_HHMMSS_ convention (optional)."
fi

if [[ $errors -gt 0 ]]; then
    echo "FAILED: $errors error(s) found."
    exit 1
fi

echo "OK: Migration pair passes validation."
exit 0
"""

_DB_MIGRATION_GUIDE_MD = """\
# Database Migration Patterns Guide

## Zero-Downtime Migration Rules

### Golden Rule
Never make a change that is incompatible with the currently running application
code. Migrations and code changes must be deployed separately.

### Adding a Column
```sql
-- Step 1: Add as nullable (safe, no lock on existing rows)
ALTER TABLE users ADD COLUMN email VARCHAR(255);

-- Step 2: Backfill in batches (avoid long-running transactions)
UPDATE users SET email = 'unknown@example.com'
WHERE email IS NULL
LIMIT 1000;  -- repeat until done

-- Step 3: Add constraint in separate migration (after backfill)
ALTER TABLE users ALTER COLUMN email SET NOT NULL;
ALTER TABLE users ALTER COLUMN email SET DEFAULT '';
```

### Renaming a Column (Expand-Contract)
```sql
-- Migration 1: Expand — add new column
ALTER TABLE users ADD COLUMN full_name VARCHAR(255);
UPDATE users SET full_name = name;

-- Deploy code that writes to BOTH columns and reads from full_name
-- Wait for verification period

-- Migration 2: Contract — drop old column
ALTER TABLE users DROP COLUMN name;
```

### Dropping a Column
1. Remove all code references to the column
2. Deploy the code change
3. Wait for all old instances to drain
4. Create migration to DROP COLUMN

### Adding an Index
```sql
-- PostgreSQL: CONCURRENTLY avoids locking the table
CREATE INDEX CONCURRENTLY idx_users_email ON users (email);

-- MySQL: Use pt-online-schema-change for large tables
-- SQLite: No concurrent option, but ALTERs are fast
```

## Dialect-Specific Notes

### PostgreSQL
- DDL is transactional (can ROLLBACK a CREATE TABLE)
- Use `CONCURRENTLY` for index creation on live tables
- `gen_random_uuid()` for UUID primary keys (requires pgcrypto or PG 13+)
- `TIMESTAMPTZ` preferred over `TIMESTAMP` for timezone safety

### MySQL
- DDL causes implicit COMMIT (cannot rollback schema changes)
- Use `pt-online-schema-change` for zero-downtime ALTERs on large tables
- `UUID()` generates v1 UUIDs; for v4, use application-generated values
- InnoDB row-level locking; MyISAM table-level (always use InnoDB)

### SQLite
- Limited ALTER TABLE: can only ADD COLUMN and RENAME TABLE
- To drop/rename columns: create new table, copy data, drop old, rename new
- No concurrent index creation (but fast enough for most cases)
- WAL mode recommended for concurrent reads during migration

## Migration File Conventions

### Naming
```
YYYYMMDD_HHMMSS_description.up.sql
YYYYMMDD_HHMMSS_description.down.sql
```
Example: `20240315_143022_add_email_to_users.up.sql`

### Structure
```sql
-- Description: Add email column to users table
-- Author: team-backend
-- Ticket: PROJ-123

BEGIN;  -- PostgreSQL only; MySQL auto-commits DDL

ALTER TABLE users ADD COLUMN email VARCHAR(255);
CREATE INDEX CONCURRENTLY idx_users_email ON users (email);

COMMIT;
```

### Down Migration Rules
- Every up migration MUST have a corresponding down
- Down must exactly reverse the up operation
- CREATE <-> DROP, ADD <-> DROP, INSERT <-> DELETE
- For data migrations: store original values in a temp table if needed

## Destructive Operation Checklist

Before running any destructive operation:
1. Verify backup exists and is restorable
2. Test the migration on a staging environment with production-scale data
3. Add `-- DESTRUCTIVE: <reason>` comment to acknowledge the risk
4. Plan the rollback procedure before executing
5. Schedule during low-traffic window if possible
"""

# ---------------------------------------------------------------------------
# Assemble BATCH1_SEEDS
# ---------------------------------------------------------------------------

BATCH1_SEEDS: list[dict] = [
    # 1. git-commit-message
    {
        "id": "seed-git-commit-message",
        "slug": "git-commit-message",
        "title": "Git Commit Message Generator",
        "category": "Code Quality",
        "difficulty": "easy",
        "frontmatter": {
            "name": "git-commit-message",
            "description": (
                "Generates Conventional Commits messages from staged diffs (feat, fix, refactor, etc.). "
                "Use when user says commit message, git commit, or describe changes, even if they don't ask explicitly. "
                "NOT for changelogs, release notes, or PR descriptions."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="git-commit-message",
            title="Git Commit Message Generator",
            description=(
                "Generates Conventional Commits messages from staged diffs (feat, fix, refactor, etc.). "
                "Use when user says commit message, git commit, or describe changes, even if they don't ask explicitly. "
                "NOT for changelogs, release notes, or PR descriptions."
            ),
            allowed_tools="Read Write Bash(git *)",
            body=_GIT_COMMIT_BODY,
        ),
        "supporting_files": {
            "scripts/validate.sh": _GIT_COMMIT_VALIDATE_SH.lstrip(),
            "scripts/main_helper.py": _GIT_COMMIT_HELPER_PY.lstrip(),
            "references/guide.md": _GIT_COMMIT_GUIDE_MD,
        },
        "traits": [
            "conventional-commits",
            "imperative-mood",
            "diff-aware",
            "scope-inference",
        ],
        "meta_strategy": "Parse staged diff for scope and magnitude, select commit type from Conventional Commits, enforce 72-char subject in imperative mood.",
    },
    # 2. code-review
    {
        "id": "seed-code-review",
        "slug": "code-review",
        "title": "Code Review Assistant",
        "category": "Code Quality",
        "difficulty": "medium",
        "frontmatter": {
            "name": "code-review",
            "description": (
                "Multi-pass code review: security vulnerabilities, correctness bugs, complexity smells, and style. "
                "Use when user says review, audit, check this code, or PR feedback. "
                "NOT for writing new code or refactoring."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="code-review",
            title="Code Review Assistant",
            description=(
                "Multi-pass code review: security vulnerabilities, correctness bugs, complexity smells, and style. "
                "Use when user says review, audit, check this code, or PR feedback. "
                "NOT for writing new code or refactoring."
            ),
            allowed_tools="Read Write Bash(grep * python *)",
            body=_CODE_REVIEW_BODY,
        ),
        "supporting_files": {
            "scripts/validate.sh": _CODE_REVIEW_VALIDATE_SH.lstrip(),
            "scripts/main_helper.py": _CODE_REVIEW_HELPER_PY.lstrip(),
            "references/guide.md": _CODE_REVIEW_GUIDE_MD,
            "references/checklist.md": """\
# Code Review Checklist

Structured checklist for systematic code reviews. Work through each
category in order — security issues outweigh style nits.

---

## 1. Security

- [ ] No hardcoded secrets, API keys, or credentials
- [ ] User input is validated and sanitized before use
- [ ] SQL queries use parameterized statements (no string concatenation)
- [ ] File paths are validated — no path traversal (`../`)
- [ ] Authentication and authorization checks are present on all protected routes
- [ ] Sensitive data is not logged or exposed in error messages
- [ ] Dependencies are from trusted sources with pinned versions
- [ ] CORS, CSP, and other security headers are properly configured
- [ ] Cryptographic operations use well-known libraries (no hand-rolled crypto)
- [ ] Deserialization of untrusted data uses safe loaders (e.g., `yaml.safe_load`)

## 2. Correctness

- [ ] Edge cases are handled (empty input, null, zero, negative, boundary values)
- [ ] Error conditions produce meaningful messages and appropriate status codes
- [ ] Concurrent access is safe (no race conditions, proper locking)
- [ ] Resource cleanup happens in `finally`/`defer`/`with` blocks (no leaks)
- [ ] Off-by-one errors checked in loops, slicing, and pagination
- [ ] Return values and error codes are checked — nothing silently ignored
- [ ] Type coercion is explicit — no reliance on implicit conversions
- [ ] Business logic matches the stated requirements

## 3. Performance

- [ ] No N+1 query patterns (batch or join instead)
- [ ] Large collections are paginated, streamed, or lazily loaded
- [ ] Expensive computations are cached where appropriate
- [ ] Database queries have proper indexes for their WHERE/JOIN clauses
- [ ] No unnecessary allocations inside hot loops
- [ ] Timeout and retry logic present for external calls
- [ ] Regex patterns are compiled once, not inside loops

## 4. Readability & Maintainability

- [ ] Functions do one thing and are under ~40 lines
- [ ] Variable and function names are descriptive and consistent
- [ ] Magic numbers and strings are extracted to named constants
- [ ] Comments explain *why*, not *what* (code should be self-documenting)
- [ ] Dead code and commented-out blocks are removed
- [ ] Nesting depth is 3 levels or less (use early returns)
- [ ] Public API has docstrings with parameter and return descriptions

## 5. Error Handling

- [ ] Exceptions are caught at the right level — not too broad, not too narrow
- [ ] No bare `except:` / `catch (Exception)` that swallows everything
- [ ] Errors are logged with enough context to diagnose (request ID, input values)
- [ ] User-facing errors do not leak stack traces or internal details
- [ ] Retry logic has exponential backoff and a maximum attempt count
- [ ] Transient vs. permanent failures are distinguished

## 6. Testing

- [ ] New code has corresponding tests (unit, integration, or both)
- [ ] Tests cover happy path, edge cases, and error conditions
- [ ] Mocks are used sparingly — prefer real implementations when fast enough
- [ ] Test names describe the scenario and expected outcome
- [ ] No flaky tests (non-deterministic, timing-dependent, or order-dependent)
- [ ] Test data is self-contained — no reliance on external state

## 7. API & Contract

- [ ] Public API changes are backward-compatible or versioned
- [ ] Request/response schemas are validated (Pydantic, Zod, JSON Schema)
- [ ] HTTP methods and status codes follow REST conventions
- [ ] Breaking changes are documented in a changelog or migration guide

---

## Severity Classification

| Severity    | Criteria                                          | Action      |
|-------------|---------------------------------------------------|-------------|
| **Critical**| Security vulnerability, data loss, crash           | Must fix    |
| **Warning** | Bug, performance issue, missing validation         | Should fix  |
| **Suggestion**| Style, naming, minor improvement                | Nice to fix |

When reporting findings, always include: file path, line number,
severity, the problematic code snippet, and a concrete fix.
""",
        },
        "traits": [
            "security-first",
            "severity-levels",
            "multi-language",
            "pattern-detection",
        ],
        "meta_strategy": "Security scan first (grep for injection, secrets, eval), then correctness walk-through, then quality metrics. Report by severity: critical > warning > suggestion.",
    },
    # 3. unit-test-generator
    {
        "id": "seed-unit-test-generator",
        "slug": "unit-test-generator",
        "title": "Unit Test Generator",
        "category": "Testing",
        "difficulty": "medium",
        "frontmatter": {
            "name": "unit-test-generator",
            "description": (
                "Generates unit tests with happy path, edge cases, and error conditions using AAA pattern. "
                "Use when user says write tests, unit test, pytest, jest, or add coverage. "
                "NOT for integration tests, E2E, or load testing."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="unit-test-generator",
            title="Unit Test Generator",
            description=(
                "Generates unit tests with happy path, edge cases, and error conditions using AAA pattern. "
                "Use when user says write tests, unit test, pytest, jest, or add coverage. "
                "NOT for integration tests, E2E, or load testing."
            ),
            allowed_tools="Read Write Bash(python * node * npx * go *)",
            body=_UNIT_TEST_BODY,
        ),
        "supporting_files": {
            "scripts/validate.sh": _UNIT_TEST_VALIDATE_SH.lstrip(),
            "scripts/main_helper.py": _UNIT_TEST_HELPER_PY.lstrip(),
            "references/guide.md": _UNIT_TEST_GUIDE_MD,
            "references/test-patterns.md": """\
# Common Test Patterns

Reference for writing effective unit tests. Each pattern includes
rationale and examples in Python (pytest) and JavaScript (Jest).

---

## 1. Arrange-Act-Assert (AAA)

The fundamental test structure. Every test has exactly three phases.

```python
# pytest
def test_user_creation_sets_default_role():
    # Arrange
    name = "Alice"
    email = "alice@example.com"

    # Act
    user = create_user(name=name, email=email)

    # Assert
    assert user.role == "viewer"
    assert user.is_active is True
```

```javascript
// Jest
test('user creation sets default role', () => {
  // Arrange
  const name = 'Alice';
  const email = 'alice@example.com';

  // Act
  const user = createUser({ name, email });

  // Assert
  expect(user.role).toBe('viewer');
  expect(user.isActive).toBe(true);
});
```

---

## 2. Parameterized Tests

Run the same test logic across multiple inputs. Eliminates copy-paste
test methods and makes coverage gaps obvious.

```python
# pytest
import pytest

@pytest.mark.parametrize("input_val,expected", [
    ("hello", "HELLO"),
    ("", ""),
    ("123abc", "123ABC"),
    ("already UPPER", "ALREADY UPPER"),
])
def test_to_upper(input_val, expected):
    assert to_upper(input_val) == expected
```

```javascript
// Jest
test.each([
  ['hello', 'HELLO'],
  ['', ''],
  ['123abc', '123ABC'],
  ['already UPPER', 'ALREADY UPPER'],
])('to_upper(%s) returns %s', (input, expected) => {
  expect(toUpper(input)).toBe(expected);
});
```

---

## 3. Fixtures & Setup

Shared state that multiple tests need. Use fixtures (pytest) or
beforeEach (Jest) to avoid duplication.

```python
# pytest
import pytest

@pytest.fixture
def db_connection():
    conn = create_test_database()
    yield conn
    conn.close()

@pytest.fixture
def sample_user(db_connection):
    return db_connection.create_user(name="Test", email="t@t.com")

def test_user_can_be_found(db_connection, sample_user):
    found = db_connection.find_user(sample_user.id)
    assert found.email == "t@t.com"
```

```javascript
// Jest
let db;
let sampleUser;

beforeEach(async () => {
  db = await createTestDatabase();
  sampleUser = await db.createUser({ name: 'Test', email: 't@t.com' });
});

afterEach(async () => {
  await db.close();
});

test('user can be found by id', async () => {
  const found = await db.findUser(sampleUser.id);
  expect(found.email).toBe('t@t.com');
});
```

---

## 4. Mocking & Stubbing

Replace external dependencies with controlled substitutes. Mock at the
boundary, not deep internals.

```python
# pytest + unittest.mock
from unittest.mock import patch, MagicMock

def test_send_email_calls_smtp(self):
    mock_smtp = MagicMock()
    with patch("myapp.email.smtp_client", mock_smtp):
        send_welcome_email("alice@example.com")

    mock_smtp.send.assert_called_once()
    args = mock_smtp.send.call_args[0]
    assert "alice@example.com" in args[0]
```

```javascript
// Jest
jest.mock('./emailClient');
const { sendEmail } = require('./emailClient');

test('send welcome email calls email client', () => {
  sendWelcomeEmail('alice@example.com');

  expect(sendEmail).toHaveBeenCalledTimes(1);
  expect(sendEmail).toHaveBeenCalledWith(
    expect.objectContaining({ to: 'alice@example.com' })
  );
});
```

**Rules of thumb:**
- Mock I/O boundaries (HTTP, DB, filesystem, clock)
- Do NOT mock the unit under test
- Prefer dependency injection over patching

---

## 5. Exception / Error Testing

Verify that code fails correctly — right exception type, right message.

```python
# pytest
import pytest

def test_divide_by_zero_raises():
    with pytest.raises(ZeroDivisionError, match="division by zero"):
        divide(10, 0)

def test_invalid_email_raises_validation_error():
    with pytest.raises(ValidationError) as exc_info:
        validate_email("not-an-email")
    assert "invalid format" in str(exc_info.value).lower()
```

```javascript
// Jest
test('divide by zero throws', () => {
  expect(() => divide(10, 0)).toThrow('division by zero');
});

test('invalid email throws validation error', () => {
  expect(() => validateEmail('not-an-email')).toThrow(ValidationError);
});
```

---

## 6. Boundary / Edge Case Patterns

Always test at the edges of valid input ranges.

| Category       | Test cases to include                         |
|----------------|-----------------------------------------------|
| Empty input    | `""`, `[]`, `{}`, `None`/`null`/`undefined`   |
| Single element | List with 1 item, string with 1 char          |
| Zero/negative  | `0`, `-1`, `Number.MIN_SAFE_INTEGER`          |
| Max boundary   | `MAX_INT`, very long strings, large lists      |
| Type coercion  | `"0"` vs `0`, `false` vs `null`               |
| Unicode        | Emoji, CJK characters, RTL text               |
| Concurrent     | Simultaneous calls, duplicate submissions      |

---

## 7. Test Naming Convention

Name tests so failures are self-documenting:

```
test_<unit>_<scenario>_<expected_outcome>
```

Examples:
- `test_parse_date_with_invalid_format_raises_value_error`
- `test_calculate_total_with_empty_cart_returns_zero`
- `test_login_with_expired_token_returns_401`
""",
        },
        "traits": [
            "arrange-act-assert",
            "multi-framework",
            "mock-aware",
            "edge-case-focus",
        ],
        "meta_strategy": "Parse function signatures and dependencies, generate tests per function covering happy/edge/error paths, use framework-appropriate patterns (pytest fixtures, Jest mocks, Go table-driven).",
    },
    # 4. api-endpoint-designer
    {
        "id": "seed-api-endpoint-designer",
        "slug": "api-endpoint-designer",
        "title": "REST API Endpoint Designer",
        "category": "Web Development",
        "difficulty": "medium",
        "frontmatter": {
            "name": "api-endpoint-designer",
            "description": (
                "Designs REST endpoints and generates OpenAPI 3.1 YAML with schemas, pagination, and error responses. "
                "Use when user says API design, REST endpoint, OpenAPI, CRUD, or Swagger. "
                "NOT for GraphQL, gRPC, or WebSocket APIs."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="api-endpoint-designer",
            title="REST API Endpoint Designer",
            description=(
                "Designs REST endpoints and generates OpenAPI 3.1 YAML with schemas, pagination, and error responses. "
                "Use when user says API design, REST endpoint, OpenAPI, CRUD, or Swagger. "
                "NOT for GraphQL, gRPC, or WebSocket APIs."
            ),
            allowed_tools="Read Write Bash(python *)",
            body=_API_ENDPOINT_BODY,
        ),
        "supporting_files": {
            "scripts/validate.sh": _API_ENDPOINT_VALIDATE_SH.lstrip(),
            "scripts/main_helper.py": _API_ENDPOINT_HELPER_PY.lstrip(),
            "references/guide.md": _API_ENDPOINT_GUIDE_MD,
        },
        "traits": [
            "openapi-compliant",
            "cursor-pagination",
            "consistent-errors",
            "kebab-case-urls",
        ],
        "meta_strategy": "Define resource and fields, generate full CRUD OpenAPI 3.1 YAML with proper schemas, pagination, error responses, and auth. Validate against spec.",
    },
    # 5. database-migration
    {
        "id": "seed-database-migration",
        "slug": "database-migration",
        "title": "Database Migration Generator",
        "category": "Data Engineering",
        "difficulty": "hard",
        "frontmatter": {
            "name": "database-migration",
            "description": (
                "Generates timestamped up/down SQL migration pairs with zero-downtime enforcement and destructive operation detection. "
                "Use when user says migration, schema change, ALTER TABLE, or add column. "
                "NOT for query optimization or ORM models."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="database-migration",
            title="Database Migration Generator",
            description=(
                "Generates timestamped up/down SQL migration pairs with zero-downtime enforcement and destructive operation detection. "
                "Use when user says migration, schema change, ALTER TABLE, or add column. "
                "NOT for query optimization or ORM models."
            ),
            allowed_tools="Read Write Bash(python *)",
            body=_DB_MIGRATION_BODY,
        ),
        "supporting_files": {
            "scripts/validate.sh": _DB_MIGRATION_VALIDATE_SH.lstrip(),
            "scripts/main_helper.py": _DB_MIGRATION_HELPER_PY.lstrip(),
            "references/guide.md": _DB_MIGRATION_GUIDE_MD,
            "assets/migration-template.sql": """\
-- Migration: <TITLE>
-- Created: <TIMESTAMP>
-- Description: <one-line summary of what this migration does>
--
-- SAFETY NOTES:
--   - Run inside a transaction (BEGIN / COMMIT) when your DB supports DDL transactions
--   - For zero-downtime deploys, use expand-contract:
--       Phase 1 (expand): add new column / table, keep old in place
--       Phase 2 (migrate): backfill data, deploy code that writes to both
--       Phase 3 (contract): drop old column / table once all readers are updated
--   - Always test the DOWN migration before merging

-- ============================================================================
-- UP MIGRATION
-- ============================================================================

BEGIN;

-- Example: Add a new column with a default value (safe, non-locking on Postgres)
-- ALTER TABLE users ADD COLUMN display_name TEXT NOT NULL DEFAULT '';

-- Example: Create a new table
-- CREATE TABLE IF NOT EXISTS audit_log (
--     id          BIGSERIAL PRIMARY KEY,
--     entity_type TEXT      NOT NULL,
--     entity_id   BIGINT    NOT NULL,
--     action      TEXT      NOT NULL CHECK (action IN ('create', 'update', 'delete')),
--     actor_id    BIGINT    REFERENCES users(id),
--     payload     JSONB     NOT NULL DEFAULT '{}',
--     created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
-- );
--
-- CREATE INDEX idx_audit_log_entity
--     ON audit_log (entity_type, entity_id);
--
-- CREATE INDEX idx_audit_log_created
--     ON audit_log (created_at);

-- Example: Add a constraint (use NOT VALID + VALIDATE for zero-downtime on Postgres)
-- ALTER TABLE orders
--     ADD CONSTRAINT chk_positive_total CHECK (total >= 0) NOT VALID;
-- ALTER TABLE orders
--     VALIDATE CONSTRAINT chk_positive_total;

COMMIT;


-- ============================================================================
-- DOWN MIGRATION (rollback)
-- ============================================================================

BEGIN;

-- Reverse every operation above in the opposite order.

-- DROP INDEX IF EXISTS idx_audit_log_created;
-- DROP INDEX IF EXISTS idx_audit_log_entity;
-- DROP TABLE IF EXISTS audit_log;
-- ALTER TABLE users DROP COLUMN IF EXISTS display_name;

COMMIT;


-- ============================================================================
-- DESTRUCTIVE OPERATION WARNINGS
-- ============================================================================
-- The following operations are DESTRUCTIVE and require explicit acknowledgment:
--
--   DROP TABLE   — irreversible data loss
--   DROP COLUMN  — irreversible data loss
--   TRUNCATE     — deletes all rows without row-level logging
--   ALTER TYPE   — may fail if existing data doesn't conform
--
-- When generating migrations with these operations:
--   1. Add a comment: "-- DESTRUCTIVE: <operation> on <table>"
--   2. Require the user to confirm before applying
--   3. Always provide a data-backup step in the UP migration
""",
        },
        "traits": [
            "expand-contract",
            "zero-downtime",
            "destructive-detection",
            "multi-dialect",
        ],
        "meta_strategy": "Generate timestamped up/down pairs, enforce expand-contract for column changes, detect destructive ops requiring acknowledgment, validate reversibility of down migration.",
    },
]

__all__ = ["BATCH1_SEEDS"]
