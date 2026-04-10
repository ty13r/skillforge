# Example Seed: git-commit-message

A complete skill package for generating Conventional Commits messages. This is a real seed from the SkillForge seed library -- use it as a pattern to match against when creating new skills.

---

## Frontmatter

```yaml
---
name: git-commit-message
description: >-
  Generates Conventional Commits messages from staged git diffs with proper
  type, scope, and imperative subject. Use when writing commit messages,
  describing changes, or when user says "commit", "what should I commit",
  even if they don't explicitly ask for help formatting. NOT for amending
  existing commits, interactive rebase, or git history rewriting.
allowed-tools: Read Write Bash(python *) Bash(git diff *) Bash(git log *)
---
```

**Breakdown:**
- First sentence: capability (what it does)
- "Use when": specific trigger scenarios
- "even if": pushy language for undertrigger prevention
- "NOT for": explicit exclusions
- Total description fits within 250 characters for the routing-critical portion

## SKILL.md Body (key sections)

### Quick Start
```markdown
Read the staged diff, infer the scope and change type, then generate a
Conventional Commits message with a subject line under 72 characters and
a body explaining *what* changed and *why*.
```

### Workflow
```markdown
### Step 1: Gather context from the staged diff
Run `python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py` in the repo root.
It executes `git diff --staged --stat` and `git diff --staged` and outputs
a JSON summary with files changed, inferred scope, change magnitude, and a
truncated diff excerpt.

### Step 2: Choose the commit type and scope
Read `${CLAUDE_SKILL_DIR}/references/guide.md` for the type definitions.
Pick the most specific type: feat, fix, refactor, docs, test, build, ci, chore, perf, style, revert.
Infer scope from the directory or module most affected.

### Step 3: Draft the message
- Subject: `type(scope): imperative description` (max 72 chars)
- Blank line
- Body: 1-3 sentences on *what* and *why*, wrapped at 80 columns
- Footer: `BREAKING CHANGE: ...` if applicable, or `Closes #NNN`

### Step 4: Validate
Run `bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh "subject line here"`.
If it exits non-zero, fix the issues it reports and re-validate.
```

### Examples (3 diverse cases)
```markdown
**Example 1: Simple feature addition**
Input: "write a commit message for these staged changes" (user added a search bar)
Output:
  feat(ui): add search bar to the header
  [body explaining debounced input and client-side filtering]

**Example 2: Bug fix with issue reference**
Input: "commit message for fixing the login timeout bug"
Output:
  fix(auth): prevent session timeout during active requests
  [body explaining keepalive middleware fix]
  Closes #247

**Example 3: Refactor across multiple files**
Input: "I refactored the database layer, what should the commit say?"
Output:
  refactor(db): extract connection pooling into dedicated module
  [body explaining extraction with no behavior change]
```

### Gotchas
```markdown
- Using past tense ("added") instead of imperative ("add") in the subject
- Exceeding 72 characters on the subject line
- Omitting the body for non-trivial changes
- Using `chore` as a catch-all
- Forgetting `BREAKING CHANGE:` footer when the public API changes
```

## scripts/validate.sh (complete)

```bash
#!/usr/bin/env bash
set -euo pipefail

# Validate a Conventional Commits message.
# Usage: bash validate.sh "subject line"
# Exit 0 on pass, non-zero on failure.

errors=0

if [[ $# -ge 1 ]]; then
    subject="$1"
else
    read -r subject
fi

# Must match Conventional Commits pattern
pattern='^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-z0-9._-]+\))?(!)?: .+'
if ! echo "$subject" | grep -qE "$pattern"; then
    echo "ERROR: Subject does not match Conventional Commits format."
    echo "  Expected: type(scope): description"
    echo "  Got:      $subject"
    errors=$((errors + 1))
fi

# Length check
length=${#subject}
if [[ $length -gt 72 ]]; then
    echo "ERROR: Subject line is $length chars (max 72)."
    errors=$((errors + 1))
fi

# Imperative mood heuristic
desc=$(echo "$subject" | sed -E 's/^[a-z]+(\([^)]*\))?(!)?: //')
first_word=$(echo "$desc" | awk '{print $1}')
if echo "$first_word" | grep -qiE '(ed|ing|ies)$'; then
    echo "WARNING: '$first_word' may not be imperative mood."
fi

if [[ $errors -gt 0 ]]; then
    echo "FAILED: $errors error(s) found."
    exit 1
fi

echo "OK: Commit message passes all checks."
exit 0
```

**Key patterns:**
- `set -euo pipefail` at the top
- Real validation logic (regex match, length check, mood heuristic)
- Clear error messages explaining what failed
- Exit 0 on pass, exit 1 on failure
- Handles input from argument or stdin

## scripts/main_helper.py (key structure)

```python
#!/usr/bin/env python3
"""Change context analyzer for commit message generation.

Runs git diff --staged and produces a JSON summary.
"""
import json, os, subprocess, sys

def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout.strip()

def infer_scope(files: list[str]) -> str:
    """Infer scope from common directory of changed files."""
    # ... real logic using path analysis and Counter ...

def classify_magnitude(insertions: int, deletions: int) -> str:
    total = insertions + deletions
    if total <= 20: return "small"
    elif total <= 150: return "medium"
    else: return "large"

def main() -> None:
    stat_output = run(["git", "diff", "--staged", "--stat"])
    diff_output = run(["git", "diff", "--staged"])
    if not stat_output:
        print(json.dumps({"error": "No staged changes found."}))
        sys.exit(1)
    # Parse stat output, build result dict
    result = {
        "files_changed": files,
        "scope_hint": infer_scope(files),
        "magnitude": classify_magnitude(total_ins, total_del),
        "diff_summary": diff_output[:3000],
    }
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
```

**Key patterns:**
- Real Python doing real work (subprocess, parsing, JSON output)
- Structured JSON output to stdout
- Error handling with informative messages
- `if __name__ == "__main__"` guard

## references/guide.md (structure)

```markdown
# Conventional Commits Reference Guide

## Commit Types
| Type | When to use |
|------|-------------|
| feat | A new feature visible to users |
| fix  | A bug fix |
| ...  | (11 types total with descriptions) |

## Subject Line Rules
1. Imperative mood: "add" not "added"
2. Max 72 characters
3. Lowercase after colon
4. No period at end
5. Scope optional but encouraged

## Scope Conventions
(module names, feature areas, config targets)

## Body Guidelines
(what/why not how, wrap at 80, bullets for multiple changes)

## Footer Conventions
(BREAKING CHANGE, Closes #N, Refs #N, Co-authored-by)

## Examples of Good Messages
(3 complete examples with type, subject, body, footer)
```

**Key patterns:**
- 50-200 lines of domain-specific content
- Tables for structured data
- Actionable rules (not vague guidance)
- Complete examples showing the expected output format
