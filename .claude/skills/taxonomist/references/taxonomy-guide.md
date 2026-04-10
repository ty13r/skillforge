# Taxonomy Guide

This document defines the rules the Taxonomist follows when classifying a skill specialization and deciding how to decompose it. It is the **rules** document — not a snapshot of current contents. The populated taxonomy is seeded in Wave 1-3 from the 16 Gen 0 seeds; until then this guide describes the structure and policies that govern taxonomy changes.

## The 3-Level Hierarchy

SkillForge organizes skills in three stable layers, from most general to most specific:

```
Domain → Focus → Language/Platform → Skill (family) → Variant (atomic unit)
```

### Domain — the problem space

The top layer. Broad categories of work. Fixed set, grows rarely (maybe once per quarter).

Examples: `testing`, `security`, `devops`, `data`, `code-quality`, `documentation`, `architecture`, `content`.

A new domain should only be proposed if the specialization doesn't fit inside any existing one — and even then, prefer to argue it is a new **focus** within an existing domain first.

### Focus — specialization within a domain

The mid layer. A coherent sub-problem inside a domain. Semi-stable — grows organically as new families are classified.

Examples under `testing`: `unit-tests`, `integration-tests`, `e2e`, `property-based`, `static-analysis`.
Examples under `devops`: `containers`, `iac`, `deployment`, `observability`.
Examples under `data`: `etl`, `cleaning`, `validation`, `parsing`.

A new focus is more acceptable than a new domain. Still requires justification — is this genuinely distinct from existing focuses, or a different flavor of one that already exists?

### Language / Platform — the concrete implementation context

The bottom layer. The tool, language, or platform the skill targets. Near-fixed set.

Examples: `python`, `javascript`, `typescript`, `rust`, `go`, `sql`, `yaml`, `kubernetes`, `terraform`, `markdown`, `universal`.

Use `universal` only when the skill is genuinely language-agnostic. Most skills target a specific language even if the underlying ideas transfer.

## Reuse-First Principle

**Always check existing slugs before creating a new one.**

The Taxonomist runs `scripts/classify.py` against the existing slug list at each level. The classifier returns a confidence score in `[0.0, 1.0]` blending sequence similarity and token overlap.

- **Confidence ≥ 0.4 → reuse** the best-matching existing slug.
- **Confidence < 0.4 → propose new**, but only with a one-line justification logged alongside the classification.

Never create a new entry "just in case". Duplicate slugs (e.g., both `unit-tests` and `unit-test` at the same level) poison the registry and split fitness data across spurious categories.

## Naming Rules

All slugs must satisfy:
- Kebab-case: lowercase letters, digits, and hyphens only
- Regex: `^[a-z0-9]+(-[a-z0-9]+)*$`
- Concise: prefer 1-3 hyphen-separated words
- No version numbers (`pytest`, not `pytest-7`)
- No adjectives that aren't load-bearing (`mock-strategy`, not `advanced-mock-strategy`)
- Unique within their level — `(level, slug)` is a primary-key-grade constraint

## Decomposition Heuristic

After classification, decide whether the skill should be evolved **atomically** (decomposed into independent variant dimensions) or **monolithically** (evolved as a single unit through the v1.x pipeline).

### The rule

> If the skill has **≥ 2 meaningfully independent dimensions** that can be (a) evolved separately AND (b) assembled into a working whole, recommend `"atomic"`. Otherwise recommend `"monolithic"`.

### What counts as a "dimension"

A dimension is a coherent strategy axis a user could meaningfully swap. Three tests:

1. **Independently testable** — the Scientist can design a focused challenge that evaluates just this dimension.
2. **Independently evolvable** — the Breeder can mutate this dimension without touching the others.
3. **Assemblable** — the Engineer can combine the winning variant with winners from other dimensions into a working composite.

### Examples

**Good dimensions for a pytest-generator skill** (all three tests pass):
- `fixture-strategy` (foundation): how test fixtures are organized
- `mock-strategy` (capability): unittest.mock vs pytest-mock vs responses
- `assertion-patterns` (capability): style and strictness of assertions
- `edge-case-generation` (capability): hypothesis vs enumerated vs snapshot

Four independent dimensions → clear **atomic** case.

**Bad dimension (too small)**: `assertion phrasing style`. Cannot be tested in isolation from `assertion-patterns`.

**Bad dimension (too large)**: the entire skill. That's molecular.

### Counter-example (monolithic)

A `csv-to-dataclass` skill parses CSV, infers types, generates a Python dataclass. It's one tight module — there are no independent substrategies. Even if you could technically split "type inference" from "dataclass generation", they're so tightly coupled the assembly overhead would dwarf any gain. **Monolithic.**

### Foundation vs Capability tiers

When decomposing for atomic mode, split dimensions into two tiers:

- **Foundation** — structural decisions other variants build on. Project structure, fixture strategy, tool configuration, the skill's philosophy. Evolved first.
- **Capability** — focused modules that plug into the foundation. Mock strategy, assertion patterns, edge-case generation, output formatting. Evolved in the context of the winning foundation.

Foundation variants usually come first in the dimension list. Capability variants depend on a foundation being locked in.

## Monolithic Default

When uncertain, prefer `"monolithic"`. Atomic evolution has real overhead: per-dimension challenge design, assembly step, integration test, refinement pass. Those costs only pay off when there are genuinely independent dimensions to exploit.

If the decomposition feels forced — if you're inventing dimensions to hit the threshold — that's the signal to fall back to molecular.

## Cross-Family Reuse

Before recommending a fresh evolution, scan related families for reusable variants:

- **Same Focus + same Language** — strongest signal. A proven `mock-strategy` variant in `flask-pytest` is highly likely to transfer to `django-pytest`.
- **Same Focus, different Language** — moderate signal. Patterns transfer, but surface syntax differs.
- **Same Domain, different Focus** — weak signal. Usually not worth the port cost.

When a strong reuse candidate exists, recommend plugging it in to the Engineer instead of re-evolving that dimension from scratch. Include `source_family`, `variant_slug`, `fitness`, and a one-line `reason` in the classification output.

## When to Create New Entries

Only when all of the following hold:
1. No existing slug at the target level scores confidence ≥ 0.4 against the specialization.
2. The specialization does not reduce to an existing category when you squint.
3. You can write a one-line justification that a reviewer would accept.

Log the justification in the classification result under `justification`. The registry stores it with the new taxonomy_node row.

## Historical-Metrics Note

The populated taxonomy and historical performance metrics are seeded in Wave 1-3 from the 16 Gen 0 seeds. Until runs accumulate, `historical-metrics.md` describes the **schema** of historical data, not its contents. Do not over-weight empty data when deciding reuse vs create.
