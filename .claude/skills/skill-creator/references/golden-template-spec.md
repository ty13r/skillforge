# Golden Template Specification (Condensed)

## Directory Structure

```
skill-name/
├── SKILL.md              # < 500 lines, core instructions
├── scripts/
│   ├── main_helper.py    # Deterministic operations (zero context cost)
│   └── validate.sh       # Output validation (exit 0/1)
├── references/
│   ├── guide.md          # Domain-specific reference (50-200 lines)
│   └── examples.md       # Extended examples if needed
└── assets/
    └── template.*        # Templates referenced by path (zero token cost)
```

## SKILL.md Frontmatter

```yaml
---
name: skill-name          # Must match directory name exactly
description: >-           # Primary trigger mechanism
  Capability statement. Use when trigger1, trigger2, trigger3,
  or when user mentions "keyword1", "keyword2", even if they
  don't explicitly ask for skill-name. NOT for exclusion1, exclusion2.
allowed-tools: Read Write Bash(python *)
---
```

**Name**: regex `^[a-z0-9]+(-[a-z0-9]+)*$`, 1-64 chars, no "anthropic"/"claude".

**Description rules**:
- Front-load capability + triggers within **250 characters** (hard truncation at routing)
- Two-part structure: (1) what it does, (2) when to use it
- "Pushy" pattern: list adjacent concepts + "even if they don't explicitly ask for..."
- Explicit exclusions: "NOT for X, Y, or Z"
- Total budget: ~100 tokens per skill in the system prompt listing

**allowed-tools**: Space-delimited. Only works in Claude Code CLI (ignored by SDK).
Common patterns: `Read Write Bash(python *)`, `Read Write Edit Bash Glob Grep`.

## SKILL.md Body Sections

### Quick Start
2-3 sentences. The entire workflow compressed to its essence.

### When to use this skill (optional but recommended)
Expanded trigger language beyond the 250-char description. Synonyms, edge cases.

### Workflow
Numbered steps with imperative verbs. Each step:
- One concrete action
- References to scripts via `${CLAUDE_SKILL_DIR}/scripts/`
- References to guides via `${CLAUDE_SKILL_DIR}/references/`
- Conditional loading: "For scenario A, read X; for scenario B, read Y"

### Examples (2-3 required)
I/O pairs in conversational tone. Include:
1. Typical use case
2. Edge case that should still trigger
3. Near-miss (synonym/adjacent concept)

Examples improve quality from 72% to 90% empirically.

### Gotchas
Real failure modes with specific fixes. Not generic advice.

### Out of Scope
Explicit exclusions with alternatives: "does NOT do X (use Y instead)".

## Script Requirements

### validate.sh
- Shebang: `#!/usr/bin/env bash`
- Must include: `set -euo pipefail`
- Exit 0 on pass, non-zero on failure
- Print error messages explaining what failed
- Must do REAL validation (not `echo OK && exit 0`)
- Validate the skill's output domain (syntax, format, constraints)

### main_helper.py
- Valid Python 3, >10 lines of logic
- Does deterministic work (parsing, formatting, data extraction)
- Outputs structured data (JSON preferred) to stdout
- Script source never enters context window (only stdout/stderr does)
- Use `${CLAUDE_SKILL_DIR}` for paths, never hardcode

## Reference Requirements

### guide.md
- 50-200 lines of domain-specific reference material
- Loaded on demand when Claude reads it (tokens consumed at read time)
- One level deep from SKILL.md (no references to references)
- Files over 100 lines should include a table of contents
- Keep factual: definitions, patterns, checklists, syntax references

## Path Convention

All paths in SKILL.md use `${CLAUDE_SKILL_DIR}/`:
- `${CLAUDE_SKILL_DIR}/scripts/main_helper.py`
- `${CLAUDE_SKILL_DIR}/scripts/validate.sh`
- `${CLAUDE_SKILL_DIR}/references/guide.md`
- `${CLAUDE_SKILL_DIR}/assets/template.html`

Never use bare relative paths (they break across environments).

## Size Budgets

| Component | Limit | Rationale |
|-----------|-------|-----------|
| Description | 250 chars (routing) | Hard truncation in skill listing |
| SKILL.md body | 500 lines | Shared instruction budget (~150-200 total) |
| Reference file | 200 lines max | Context window cost |
| Script | No limit | Zero context cost (only output enters context) |
| Total skill files | 30 MB | API upload limit |
| Active skills | 20-50 | Routing reliability degrades beyond this |
