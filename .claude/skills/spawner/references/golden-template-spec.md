# Golden Template Spec (v2.0)

This is the structural contract every spawned variant must satisfy. It extends the base golden template at `docs/golden-template/` with v2.0 variant-specific fields (`dimension`, `tier`) and the `scripts/score.py` requirement.

A variant that violates this spec is rejected by `validate_variant.py` before ever reaching the Competitor.

## 1. Naming rules

- Skill / variant `name` must match regex: `^[a-z0-9]+(-[a-z0-9]+)*$`
- Directory basename MUST equal the `name` field in frontmatter, character for character.
- Kebab-case only. No underscores, no uppercase, no leading digits (digits allowed in later segments).
- For variants, the convention is `<family-slug>-<dimension>-<approach-slug>`, e.g. `pytest-generator-mock-strategy-patch-decorators`.

## 2. Frontmatter schema

Frontmatter is YAML-ish, fenced between two `---` lines at the very top of `SKILL.md`.

### Required fields (all variants)

| Field | Type | Rule |
|-------|------|------|
| `name` | string | kebab-case, matches dir basename, satisfies name regex |
| `description` | string | ≤ 250 characters, front-loads capability + triggers, pushy pattern with explicit exclusions |
| `allowed-tools` | string | space-separated (or comma-separated) list of Claude tools the variant actually uses |

### v2.0 variant extensions (required for variants)

| Field | Type | Rule |
|-------|------|------|
| `dimension` | string | Non-empty. The dimension slug this variant targets (e.g. `mock-strategy`, `fixture-approach`, `project-structure`). Reviewer scopes L3/L4 evaluation by this field. |
| `tier` | string | Either `foundation` or `capability`. |

### Description style (the 250-char budget)

The description is Level 1 routing signal. It must:
- Lead with WHAT the variant does (not how).
- List 3+ trigger phrases (synonyms, adjacent concepts).
- Use the pushy "even if they don't explicitly ask for..." pattern.
- End with explicit exclusions: "NOT for X, Y, or Z".

The description evolves on a separate track from the body — it is what determines whether the variant gets selected by the router at all.

## 3. Directory layout

```
<variant-name>/
  SKILL.md                    # required — single H1, frontmatter + body
  scripts/
    score.py                  # REQUIRED (v2.0) — deterministic per-dimension scoring
    validate.sh               # REQUIRED — real bash self-check, not a stub
    <tool>.py                 # optional — dimension-specific helpers
    <tool>.sh                 # optional
  references/
    <dimension>-guide.md      # required — substantive reference, 50-150 lines
    <additional>.md           # optional — extra references one level deep
  assets/                     # optional — templates, configs, static resources
    <template>.<ext>
  test_fixtures/              # optional — immutable sample inputs for the dimension
    <sample>.<ext>
```

Rules:
- All paths referenced from `SKILL.md` MUST use `${CLAUDE_SKILL_DIR}/...`. Never relative, never absolute.
- `scripts/` holds executables and deterministic helpers. `references/` holds markdown Claude reads on demand. `assets/` holds non-markdown templates. `test_fixtures/` holds immutable inputs (same across all variants in a dimension run).
- Reference docs are ONE level deep. No nested `references/foo/bar.md`.

## 4. Body sections (order matters)

```markdown
# <Display Name>           <- single H1, required

## Quick Start             <- 2-3 sentence workflow summary
## When to use this skill  <- trigger guidance, expanded from description
## Workflow                <- numbered steps, every path uses ${CLAUDE_SKILL_DIR}/...
## Examples                <- 2-3 diverse I/O pairs — MANDATORY
## Gotchas                 <- failure modes specific to this variant
## Out of Scope            <- optional but recommended — explicit exclusions
```

### Section rules

- **Single H1.** The H1 is the display name; never repeat it.
- **Workflow** uses numbered steps (`### Step 1`, `### Step 2`, ...) with imperative verbs. Every script invocation uses `${CLAUDE_SKILL_DIR}/scripts/<name>.py` or `${CLAUDE_SKILL_DIR}/scripts/<name>.sh`.
- **Examples** are the single biggest fitness lever — empirically 72% → 90% quality jump. Always 2-3. Diverse: (a) typical use, (b) edge case, (c) near-miss trigger.
- **Gotchas** are specific failure modes the variant has actually encountered, not generic advice.

### Size limits

| Limit | Value | Why |
|-------|-------|-----|
| Description | ≤ 250 chars | Level 1 router token budget |
| Body | ≤ 500 lines | Level 2 instruction budget |
| Any single reference | ≤ 300 lines | Loaded on demand, but still needs to fit |
| `max_function_length` in scripts | target < 40 | Measured by `code_metrics.py` |
| `max_nesting_depth` in scripts | target < 4 | Measured by `code_metrics.py` |

## 5. Focused scope (the hardest rule to follow)

A variant targets ONE dimension. The `dimension` field in frontmatter declares it. The body must visibly honor it:

- The body should mention the `dimension` value somewhere (validator warning if not).
- The body should have ≤ 5 H2 sections (validator warning if more — sign of kitchen-sinking).
- Every example should demonstrate the variant's specific angle on the dimension.
- The workflow steps should not drift into adjacent dimensions (a `mock-strategy` variant should not be prescribing fixture layouts).

## 6. Rejection conditions (enforced by `validate_variant.py`)

A variant is rejected if any of these are true:
- Missing `SKILL.md`
- Missing or malformed frontmatter (no open or close fence)
- Missing `name`, `description`, or `dimension` field
- `name` does not match regex or does not match directory basename
- `description` > 250 characters
- Body > 500 lines
- Fewer than 2 Example sections
- Any `${CLAUDE_SKILL_DIR}/...` reference points to a file that does not exist in the variant dir

Warnings (not rejections, but Spawner should address):
- More than 5 H2 sections in the body (possible kitchen-sink)
- `dimension` field value not mentioned anywhere in the body (possible scope drift)
