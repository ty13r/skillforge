---
name: spawner
description: >-
  Creates diverse initial variant populations for atomic evolution. Builds
  focused mini-SKILL.md packages per dimension (foundation or capability
  tier). Use when spawning gen 0 or seeding a dimension. NOT for mutation.
allowed-tools: Read Write Bash(python *) Bash(bash *) Glob Grep
---

# Spawner

## Quick Start
Given a variant dimension (e.g. `mock-strategy`, tier `capability`) and a focused challenge from the Scientist, spawn N initial variant packages that are structurally valid, narrowly scoped to the dimension, diverse in approach, and ready for the Competitor + Reviewer pipeline. Each variant is a complete mini-SKILL.md package with frontmatter, focused body, `scripts/score.py` stub, and validate.sh.

## When to use this skill
Use when the Evolution Engine needs gen 0 for a variant dimension. Triggers on "spawn population", "seed dimension", "create initial variants", "gen 0 for foundation", "bootstrap capability variants", or any request to produce a starting population for `variant_evolution.py`. Also triggers when someone asks you to "generate N different approaches for dimension X" — that is spawning in disguise.

NOT for mutating existing variants (that is the Breeder), not for authoring a standalone full skill (that is `skill-creator`), not for assembling winning variants into a composite (that is the Engineer).

## Inputs you will receive

From the Evolution Engine, as a structured payload:
- `family_id`, `family_slug`, `specialization` — identifies the parent skill family
- `dimension` — e.g. `"mock-strategy"`, `"fixture-approach"`, `"project-structure"`
- `tier` — `"foundation"` or `"capability"`
- `population_size` — how many variants to spawn (default 2 for atomic mode)
- `challenge` — the focused challenge this dimension will be tested against (JSON from Scientist)
- `rubric` — the per-dimension scoring rubric (metrics + weights)
- `foundation_context` — ONLY for capability variants: the winning foundation variant's SKILL.md + scripts. Used as grounding so capability variants plug into a consistent skeleton.

## Workflow

### Step 1: Load structural contract
Read `${CLAUDE_SKILL_DIR}/references/golden-template-spec.md` before drafting anything. Every spawned variant must match this contract exactly (frontmatter schema, directory layout, body sections, size limits, naming rules).

### Step 2: Load measurability rules
Read `${CLAUDE_SKILL_DIR}/references/metrics-awareness.md`. This explains what the Reviewer will measure deterministically — AST-parseable code, short functions, shallow nesting, declared I/O in docstrings, `scripts/score.py` stub. Spawned variants must be structured so these metrics can be computed without LLM judgment.

### Step 3: Plan diversity (do not converge)
Gen 0 exists to explore, not to optimize. For `population_size` of N, plan N genuinely different approaches to the single dimension. Examples:
- Dimension `mock-strategy`, N=3 → (a) `unittest.mock.patch` decorators, (b) `pytest-mock` fixtures, (c) hand-rolled fake classes
- Dimension `fixture-approach`, N=2 → (a) function-scope fixtures in conftest.py, (b) class-scope fixtures parameterized with `@pytest.mark.parametrize`
- Dimension `project-structure`, N=2 → (a) `tests/` flat layout, (b) mirrored `tests/unit/` + `tests/integration/` layout

Do NOT spawn N near-duplicates. Do NOT kitchen-sink one variant with every approach. **One dimension, one angle per variant.**

### Step 4: For capability variants, absorb foundation context
If `tier == "capability"`, read `foundation_context.skill_md` first. Every capability variant you spawn must be compatible with that foundation's directory layout, naming, and fixture philosophy. Reference the foundation's scripts and conventions in the spawned variant's workflow steps. This is how we keep capability variants pluggable during Engineer assembly.

### Step 5: Draft each variant package

For each of the N variants, produce this directory structure:

```
<family-slug>-<dimension>-<approach-slug>/
  SKILL.md
  scripts/
    score.py          # deterministic metrics for this dimension
    validate.sh       # structural self-check
    <tool>.py         # OPTIONAL: dimension-specific helper
  references/
    <dimension>-guide.md
```

**SKILL.md frontmatter** (required fields):
- `name`: matches directory basename, kebab-case, satisfies `^[a-z0-9]+(-[a-z0-9]+)*$`
- `description`: ≤250 chars. Front-load the *dimension* and the *angle*. "Pushy" triggers. Explicit exclusions.
- `allowed-tools`: space-separated, only what the variant actually uses
- `dimension`: the dimension slug (v2.0 extension — Reviewer scopes L3/L4 by this)
- `tier`: `foundation` or `capability`

**SKILL.md body** (≤500 lines, 2-3 Examples required):
- `# <Display Name>` (single H1)
- `## Quick Start` — 2-3 sentences, dimension-scoped
- `## When to use this skill` — triggers AND explicit scope boundary ("only for `<dimension>`")
- `## Workflow` — numbered steps, every path uses `${CLAUDE_SKILL_DIR}/...`
- `## Examples` — 2-3 diverse I/O pairs (MANDATORY — this is the 72% → 90% quality jump)
- `## Gotchas` — failure modes specific to this approach

**scripts/score.py**: see `references/metrics-awareness.md` for the stub signature. Reads `$1` (competitor output dir), writes JSON metrics for this dimension to stdout. Deterministic. AST-parseable. Stdlib only unless the dimension truly requires a library.

**scripts/validate.sh**: real bash, `set -euo pipefail`, checks the variant's own structural invariants. Not a stub.

**references/<dimension>-guide.md**: 50-150 lines of substantive reference material on this specific approach. Loaded on demand.

### Step 6: Self-validate every spawned variant
For each variant, run:

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh <variant_dir>
```

This invokes `validate_variant.py` which checks: directory exists, SKILL.md exists, frontmatter has `name`+`description`+`dimension`, name matches regex and dir basename, description ≤250 chars, body ≤500 lines, ≥2 Example sections, every `${CLAUDE_SKILL_DIR}/` path resolves, and the `dimension` field is actually referenced in the body. Fix any errors before returning.

### Step 7: Return the population
Return a JSON list of variant directory paths plus a one-line rationale per variant explaining its distinct angle. The Evolution Engine hands these to the Competitor.

## Examples

**Example 1: Foundation tier, N=2, dimension `project-structure`**

Input payload:
```json
{
  "family_slug": "pytest-generator",
  "dimension": "project-structure",
  "tier": "foundation",
  "population_size": 2,
  "challenge": {"prompt": "Add tests for src/auth.py with existing tests/ dir"}
}
```

Output (two directories):
- `pytest-generator-project-structure-flat/` — foundation variant that puts all tests in `tests/` with no subdirs, uses `conftest.py` at root, imports via `from src.module import x`. SKILL.md `dimension: project-structure`, `tier: foundation`. Body walks through flat-layout decisions.
- `pytest-generator-project-structure-mirrored/` — foundation variant that creates `tests/unit/` + `tests/integration/` mirroring `src/`, conftest.py per subdir, `pytest.ini` with testpaths. SKILL.md `dimension: project-structure`, `tier: foundation`. Body explains mirrored philosophy.

Both pass `validate_variant.py`. Both include `scripts/score.py` reporting `layout_depth`, `conftest_count`, `testpath_count`.

**Example 2: Capability tier, N=3, dimension `mock-strategy`, with foundation context**

Input payload:
```json
{
  "family_slug": "pytest-generator",
  "dimension": "mock-strategy",
  "tier": "capability",
  "population_size": 3,
  "foundation_context": {"skill_md": "...winning project-structure-mirrored..."}
}
```

Output (three directories, each compatible with the mirrored foundation):
- `pytest-generator-mock-strategy-patch-decorators/` — uses `@patch("src.auth.db")` decorators, autospec=True, references the mirrored foundation's `tests/unit/` path in its workflow.
- `pytest-generator-mock-strategy-pytest-mock/` — uses `pytest-mock`'s `mocker` fixture, spy patterns, depends on `pytest-mock` in `allowed-tools`.
- `pytest-generator-mock-strategy-hand-rolled-fakes/` — defines Fake classes in `tests/unit/fakes/`, no patching, pure DI.

Each SKILL.md mentions `mock-strategy` in the body (enforced by validator warning). Each has 2-3 Examples showing the angle concretely.

**Example 3: Near-miss — do not kitchen-sink**

Input: "spawn 2 variants for dimension `assertion-style`".

**Wrong**: Variant A covers all of `assert ==`, `pytest.approx`, `hypothesis`, snapshot testing, and property-based checks in one SKILL.md. Variant B is a near-duplicate with reordered sections.

**Right**: Variant A focuses purely on `pytest.approx` + type-narrow assertions. Variant B focuses purely on snapshot assertions via `syrupy`. Each variant is narrow; together the population covers the space.

## Gotchas

- **Forgetting the `dimension` frontmatter field** breaks Reviewer's L3/L4 scoping. `validate_variant.py` will reject the variant.
- **Kitchen-sinking** a single variant with every approach destroys the signal the Reviewer is trying to measure. Resist the urge to be "comprehensive" in gen 0 — be narrow and diverse.
- **Ignoring foundation_context** for capability variants causes Engineer assembly conflicts later. If the foundation puts fixtures in `tests/conftest.py`, a capability variant that assumes `tests/unit/conftest.py` will clash.
- **Relative paths in SKILL.md** (`./scripts/foo.py`) are silently wrong. Always use `${CLAUDE_SKILL_DIR}/scripts/foo.py`. The validator flags missing `${CLAUDE_SKILL_DIR}` prefixes indirectly by failing to resolve the referenced file.
- **Non-AST-parseable code in `score.py`** (e.g. `exec()`, dynamic imports, metaclass trickery) breaks Reviewer's `code_metrics.py`. Keep score.py boring and readable.
- **Description over 250 chars** fails the validator. Count before returning.
- **Fewer than 2 Examples** fails the validator. Three diverse examples is the sweet spot.

## Out of Scope

This skill does NOT:
- Mutate or refine existing variants (use the Breeder)
- Generate challenges or rubrics (use the Scientist)
- Assemble variants into a composite skill (use the Engineer)
- Classify domains or decompose dimensions (use the Taxonomist)
- Run variants against challenges (use the Competitor)
