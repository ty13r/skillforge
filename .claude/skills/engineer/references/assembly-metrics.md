# Assembly Metrics

Canonical definitions for how the Engineer measures an assembled composite skill. Every metric here is computed from inputs the Engineer already has: the foundation variant, the capability variants with their individual fitness scores, the conflict-scan JSON, the validator output, and a single integration test result.

## 1. Synergy ratio

**Formula:**
```
synergy_ratio = composite_fitness / max(individual_variant_fitness)
```

Where:
- `composite_fitness` — aggregate fitness of the assembled skill on the integration challenge (weighted sum of L1 deterministic + L3 trace + L4 comparative, per the Reviewer's rubric).
- `max(individual_variant_fitness)` — highest fitness score across the foundation and all capability variants on *their own* focused challenges.

**Interpretation:**
- `>= 1.05` — healthy synergy. The whole is measurably more than the sum of parts. Target for all shipped composites.
- `0.95 – 1.05` — neutral. Assembly neither helped nor hurt. Acceptable if conflict_count == 0 and integration passed.
- `< 0.95` — interference. One or more merges undid fitness gains. Trigger refinement pass; if still <0.95 after refinement, ship but flag for Breeder attention.
- `< 0.80` — severe interference. Do not ship. Report to Taxonomist for re-decomposition.

## 2. Integration pass rate

**Formula:**
```
integration_pass_rate = passed_challenges / total_challenges
```

The Engineer runs exactly one cross-dimension integration challenge by default. In that case the metric is either 0.0 or 1.0. When caller supplies multiple integration challenges (advanced flow), compute the ratio directly.

**Thresholds:**
- `>= 0.7` — ship without refinement.
- `< 0.7` — trigger exactly one refinement pass.
- Still `< 0.7` after refinement — ship best-effort assembly with a warning in the assembly report; do not perform a second refinement pass.

## 3. Conflict count

**Formula:**
```
conflict_count =
    len(duplicate_files) +
    len(overlapping_sections) +
    (1 if description_conflict else 0)
```

Computed by `scripts/check_conflicts.py` *before* merging.

**Thresholds:**
- `0` — ideal. Clean merge.
- `1 – 2` — acceptable. Apply standard merge patterns (rename, weave, drop clauses).
- `3` — marginal. Still assemble, but raise a warning in the assembly report.
- `> 3` — stop. Do not force the merge. Return the conflict JSON to the Taxonomist so the decomposition can be revised. A high conflict count almost always indicates dimensions that should have been merged into one.

## 4. Description length compliance

**Formula:**
```
description_length = len(composite_frontmatter_description)  # after YAML folding
```

**Rules:**
- Hard limit: `≤ 250` chars. Non-negotiable — the routing layer truncates past this.
- Compute length *after* joining folded scalar lines with single spaces, not on the raw YAML text.
- If overflow after naive concat, drop `NOT for X` exclusion clauses in order of least-essential-first, then shorten trigger lists.
- **Truncation budget:** if more than 10% of the concatenated length is dropped to fit, that counts as a refinement trigger.

## 5. Body length compliance

**Formula:**
```
body_lines = count_lines(composite_skill_md_body)  # post-frontmatter
```

**Rules:**
- Hard limit: `≤ 500` lines.
- If overflow, trim in priority order: (a) redundant Gotchas, (b) duplicated Examples, (c) verbose prose in Workflow steps. Never trim Quick Start, frontmatter, or the core numbered Workflow.
- **Truncation budget:** if more than 20% of the pre-trim length was removed, that counts as a refinement trigger.

## 6. Refinement triggers

A refinement pass (exactly one, ever) is triggered if **any** of these hold after the first assembly:

| Trigger | Threshold |
|---|---|
| Integration test failed | `integration_pass_rate < 0.7` |
| Excessive conflicts | `conflict_count > 2` |
| Description over-trimmed | `dropped_chars / concat_length > 0.10` |
| Body over-trimmed | `removed_lines / pre_trim_lines > 0.20` |
| Synergy collapse | `synergy_ratio < 0.95` with validate.sh passing |

The refinement pass targets the weakest woven section (lowest marginal contribution to integration score). It re-weaves that one section, re-runs validate.sh, and re-runs the integration challenge. Exactly once. Then ship whatever the second attempt produced.

## 7. Computing from available inputs

- `composite_fitness` — from Reviewer output on the integration challenge run
- `individual_variant_fitness` — from the `Variant.fitness_score` field of each input variant
- `conflict_count` — from `scripts/check_conflicts.py` JSON, `conflict_count` field
- `description_length` — parse composite SKILL.md frontmatter, count chars in folded `description`
- `body_lines` — count `\n`-separated lines after the closing `---` of frontmatter
- `integration_pass_rate` — ratio of passing challenges reported by the Reviewer L1 pass

All metrics land in the `assembly_report` section of the post-run report (see `plans/PLAN-V2.0.md` Wave 1-5).
