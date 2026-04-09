# Golden Template for Agent Skills

This template encodes every empirically-proven structural pattern from the deep research report (`skills-research.md`). All gen 0 Skills MUST follow this structure. The Spawner varies content while preserving structure. The Breeder may evolve structure only when trait attribution provides evidence that structural changes improve fitness.

## Template Structure

```
{skill-name}/
├── SKILL.md              # < 500 lines, core instructions
├── scripts/
│   ├── main_helper.py    # Deterministic operations (zero context cost)
│   └── validate.sh       # Output validation
├── references/
│   ├── detailed-guide.md # Domain-specific reference (loaded on demand)
│   └── examples.md       # Extended examples library (if > 3 examples needed)
└── assets/
    └── template.*        # Templates referenced by path
```

## SKILL.md Template

```yaml
---
name: {skill-name}
description: >-
  {Capability statement — 1 sentence, WHAT it does}. Use when {trigger 1},
  {trigger 2}, {trigger 3}, or when user mentions "{keyword1}", "{keyword2}",
  "{keyword3}", even if they don't explicitly ask for {exact skill name}.
  NOT for {exclusion 1}, {exclusion 2}, or {exclusion 3}.
allowed-tools: Read Write Bash(python *)
---

# {Skill Display Name}

## Quick Start
{2-3 sentences: the core workflow in the simplest possible terms.}

## Workflow

### Step 1: Gather Context
{Concrete instruction with specific action — imperative voice.}
- For {scenario A}, read `${CLAUDE_SKILL_DIR}/references/detailed-guide.md`
- For {scenario B}, read `${CLAUDE_SKILL_DIR}/references/examples.md`

### Step 2: Execute
{Concrete instruction — what to do, not what to think about.}
- Run: `python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py --input "$ARGUMENTS"`

### Step 3: Validate
{Concrete instruction — verify the output meets quality bar.}
- Run: `bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh`
- If validation fails, fix issues and re-validate before presenting to user.

## Examples

**Example 1: {Typical use case}**
Input: "{realistic user prompt, conversational tone}"
Output: {expected result with specific format}

**Example 2: {Edge case}**
Input: "{edge case prompt that should still trigger}"
Output: {expected result}

**Example 3: {Near-miss — should trigger but might not}**
Input: "{prompt using synonym/adjacent concept}"
Output: {correct handling}

## Gotchas
- {Known failure point #1 — what goes wrong and how to handle it}
- {Known failure point #2 — specific, actionable}
- {Common user mistake and correct response}

## Out of Scope
This skill does NOT:
- {Explicit exclusion} (use {other-skill} instead)
- {Explicit exclusion}
- {Explicit exclusion}
```

## Design Principles

1. **Description front-loaded within 250 chars** — the routing decision happens on truncated text
2. **"Pushy" trigger language** — list adjacent concepts, include "even if..."
3. **Numbered steps** for workflow ordering with imperative verbs
4. **2-3 diverse examples** — teach format/style more effectively than rules
5. **Progressive disclosure** — SKILL.md has routing + quick-start; details in references/
6. **Scripts for deterministic ops** — zero context cost vs. instruction cost
7. **Explicit out-of-scope** — reduces false positives
8. **Under 500 lines** — respects the shared instruction budget
9. **`${CLAUDE_SKILL_DIR}`** — portable path references
10. **Gotchas section** — captures real failure points for iterative improvement

## Eval Queries Template

Every evolved Skill should ship with eval queries for trigger accuracy testing:

```json
{
  "should_trigger": [
    "{realistic prompt using exact user language #1}",
    "{realistic prompt using exact user language #2}",
    "{prompt with synonym/adjacent concept}",
    "{edge case that should still trigger}",
    "{vague request that should trigger}"
  ],
  "should_not_trigger": [
    "{near-miss sharing keywords but needing different skill}",
    "{near-miss with overlapping domain}",
    "{simple request Claude handles natively}",
    "{request for adjacent but excluded capability}"
  ]
}
```

Run with 60/40 train/test split, 3 runs per query, up to 5 improvement iterations.
Select winner by **test score, not training score** to avoid overfitting.
