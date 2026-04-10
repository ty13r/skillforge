---
name: skill-creator
description: >-
  Creates production-quality Claude Agent Skill packages from a domain description.
  Generates SKILL.md, scripts, references, and domain-specific files following the
  golden template. Use when building, creating, or authoring a new skill, even if
  they just say "make a skill for X". NOT for editing existing skills or evolutions.
allowed-tools: Read Write Bash(python *) Glob Grep
---

# Skill Creator

## Quick Start
Given a domain description, create a complete Skill package: SKILL.md with optimized frontmatter and body, helper scripts, validation scripts, and reference files. Read the golden template spec, scaffold the directory, generate all files, then validate.

## When to use this skill
Use when the user wants to create a new Claude Agent Skill from scratch. Triggers on "make a skill", "create a skill for X", "build a skill package", "new skill", "skill for doing Y", "author a skill", or any request to produce a SKILL.md with supporting files. Also triggers when someone says "I need a skill that does X" or "can you make me a skill", even if they don't use the word "skill" explicitly but describe a reusable workflow they want Claude to follow.

## Workflow

### Step 1: Gather domain context
Ask the user (or infer from context) the answers to these questions:
- **What domain?** (e.g., "code review", "database migration", "regex builder")
- **What validation is possible?** (lint, compile, test, parse output, or LLM-only)
- **What tools/languages are involved?** (determines `allowed-tools` and script language)
- **What are the key failure modes?** (informs Gotchas and validation)

Read `${CLAUDE_SKILL_DIR}/references/golden-template-spec.md` for the structural requirements.
Read `${CLAUDE_SKILL_DIR}/references/quality-checklist.md` for the full validation criteria.
Read `${CLAUDE_SKILL_DIR}/references/anti-patterns.md` to avoid common mistakes.
Read `${CLAUDE_SKILL_DIR}/references/example-seed.md` for a concrete example of a complete skill.

### Step 2: Scaffold the package
Create the directory structure:
```
{skill-name}/
  SKILL.md
  scripts/
    main_helper.py
    validate.sh
  references/
    guide.md
```

The skill name MUST match regex `^[a-z0-9]+(-[a-z0-9]+)*$` and the directory name must match the `name` field in frontmatter exactly.

### Step 3: Generate all files

**SKILL.md frontmatter:**
- `name`: lowercase-kebab matching directory name
- `description`: front-load capability + triggers within 250 characters. Use the two-part pattern: "Does X. Use when Y, even if Z. NOT for A, B, or C."
- `allowed-tools`: only tools the skill actually needs

**SKILL.md body (under 500 lines):**
- `## Quick Start` — 2-3 sentences, the entire workflow compressed
- `## When to use this skill` — expanded trigger language
- `## Workflow` — numbered steps with imperative verbs, `${CLAUDE_SKILL_DIR}/` paths
- `## Examples` — 2-3 diverse I/O pairs (easy, edge case, near-miss)
- `## Gotchas` — real failure modes with fixes, not generic advice
- `## Out of Scope` — explicit exclusions with alternatives

**scripts/validate.sh:**
- Shebang: `#!/usr/bin/env bash`
- `set -euo pipefail`
- Real validation logic (not a stub that always exits 0)
- Exit 0 on pass, non-zero on failure with error messages

**scripts/main_helper.py:**
- Real Python that does deterministic work (parsing, formatting, file ops)
- At least 10 lines of actual logic
- Outputs structured data (JSON preferred) to stdout

**references/guide.md:**
- 50-200 lines of domain-specific reference material
- Loaded on demand, not at routing time
- One level deep from SKILL.md (no nested references)

**Domain-specific files** (as needed):
- Templates in `assets/`
- Additional references for complex domains
- Extra scripts for multi-step validation

### Step 4: Validate
Review the generated package against the quality checklist:

1. Frontmatter: name regex, description length, trigger language, exclusions
2. Body: line count, required sections, path resolution
3. Scripts: validate.sh does real work, main_helper.py has real logic
4. References: guide.md exists and has substance

Fix any issues found, then review once more.

## Examples

**Example 1: Simple domain (regex builder)**
Input: "Make a skill for building regex patterns"
Output: A `regex-builder/` package with:
- SKILL.md: description triggers on "regex", "pattern", "match", "regular expression"
- scripts/main_helper.py: takes a description, generates candidate regex, tests against examples
- scripts/validate.sh: runs regex against test strings, checks for catastrophic backtracking
- references/guide.md: common regex patterns, character class reference, engine differences

**Example 2: Medium domain (code review)**
Input: "Create a skill that does thorough code reviews"
Output: A `code-review/` package with:
- SKILL.md: triggers on "review", "PR", "pull request", "code quality", "look at my code"
- scripts/main_helper.py: parses diff, categorizes changes, detects common anti-patterns
- scripts/validate.sh: checks that review output has severity levels, file references, suggestions
- references/guide.md: review checklist by language, severity definitions, feedback tone guide

**Example 3: Complex domain (database migration)**
Input: "I need a skill for writing and validating database migrations"
Output: A `database-migration/` package with:
- SKILL.md: triggers on "migration", "schema change", "alter table", "db migrate"
- scripts/main_helper.py: parses SQL migration, checks for destructive ops, estimates lock time
- scripts/validate.sh: syntax-checks SQL, verifies up/down pair, checks naming convention
- references/guide.md: migration patterns (expand-contract, blue-green), ORM-specific syntax
- references/destructive-ops.md: list of operations that require extra review (DROP, TRUNCATE, etc.)

## Gotchas
- **Stub scripts**: validate.sh that just does `echo "OK" && exit 0` is the most common failure. The script must check something real about the skill's output domain.
- **Weak descriptions**: "A skill for X" undertriggers. Always use the two-part pattern with "Use when" + "even if" + "NOT for".
- **Missing ${CLAUDE_SKILL_DIR}/ paths**: Every reference to scripts/ or references/ in the SKILL.md body must use `${CLAUDE_SKILL_DIR}/` prefix. Bare relative paths break in production.
- **All skills looking the same**: Each skill must have domain-specific examples, validation logic, and reference content. Generic boilerplate gets ignored by Claude. The examples section is where differentiation matters most.
- **Over-engineering**: A skill body over 300 lines is usually trying to do too much. Move detail to references/. The body should be quick-start + routing + core workflow.

## Out of Scope
This skill does NOT:
- Edit or improve existing skills (that requires reading the current skill, running evals, and iterating)
- Run the SkillForge evolution engine (that is a separate system)
- Create skills for the Skills API (this creates filesystem-based Claude Code skills)
- Test or benchmark skills (use eval tooling for that)
- Manage skill installation or deployment
