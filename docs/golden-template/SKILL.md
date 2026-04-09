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
