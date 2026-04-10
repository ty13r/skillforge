---
name: reviewer
description: >-
  Evaluates evolved skill variants with quantitative metrics (AST code quality, execution,
  output) and qualitative LLM scoring, producing aggregate fitness JSON. Use when scoring
  variants, judging competitions, computing L1-L5 fitness, or benchmarking candidates.
  NOT for designing challenges, mutating skills, or assembling composites.
allowed-tools: Read, Bash(python3 *), Bash(bash *), Glob, Grep
---

# Reviewer — Variant Fitness Evaluator

## Quick Start
The Reviewer is the canonical measurement authority for SKLD. It runs the L1-L5 evaluation
pipeline against a competitor trace and produces a single aggregate fitness JSON object that
the Breeder, Engineer, and post-run Report consume. For **variant evaluation** (v2.0 atomic
mode), the pipeline is scoped and simplified: L1 is driven by a dimension-specific rubric,
L2 is skipped, and L3-L5 are narrowed to the variant's dimension only.

## When to use
- Scoring a single variant after a Competitor run completes
- Computing an aggregate fitness score that feeds the Breeder's mutation decisions
- Producing the per-variant JSON that rolls into the post-run report
- Comparing variants within the same dimension (within-dimension pairwise, not cross-dimension)
- Benchmarking an assembled composite skill via L1-L3 integration tests

Do NOT use the Reviewer to design challenges (that's Scientist), to propose mutations (that's
Breeder), or to merge variants (that's Engineer).

## Workflow

### Step 1: Gather the evaluation inputs
Before scoring, make sure you have:
- The **trace** produced by the Competitor run (events, turns, tool calls, output files)
- The **rubric JSON** from the Scientist (see `${CLAUDE_SKILL_DIR}/references/scoring-rubric-spec.md`)
- The **variant package directory** (the evolved skill being evaluated)
- The **challenge** the variant was run against

If any are missing, abort with a clear error — do not guess.

### Step 2: Read the rubric and metrics catalog
- Read `${CLAUDE_SKILL_DIR}/references/scoring-rubric-spec.md` to understand the rubric shape.
- Read `${CLAUDE_SKILL_DIR}/references/metrics-catalog.md` to resolve every `metric` name referenced
  in the rubric. Every metric in the rubric MUST exist in the catalog. If one does not, fail loudly.

### Step 3: Run L1 — deterministic + code quality metrics
This is the quantitative layer. It runs with zero LLM calls.

1. Execute the variant's own `scripts/score.py` (if present) and capture its JSON output. This
   produces dimension-specific metrics like `isolation_score`, `mock_realism`, `test_pass_rate`, etc.
2. Run the AST analyzer across the variant's produced code:
   ```
   python3 ${CLAUDE_SKILL_DIR}/scripts/code_metrics.py --dir <variant_output_dir> --format json
   ```
   This emits `cyclomatic_complexity`, `max_function_length`, `max_nesting_depth`, `function_count`,
   `import_count` per file.
3. Merge the two JSON blobs. Every metric in the rubric's `quantitative` list must now have a value.
4. Compute the `quantitative_subtotal`: for each rubric entry, normalize the metric to [0, 1] (using
   thresholds from the catalog), multiply by its weight, sum.

### Step 4: Decide if you need qualitative scoring
Prefer the quantitative subtotal when:
- Every rubric `quantitative` entry has a real measured value (no nulls).
- The rubric's `quantitative` weights sum to 1.0 ± 0.001.
- The variant produced runnable output (otherwise qualitative can't help — the run failed).

Fall back to qualitative LLM scoring when:
- The rubric contains `qualitative` criteria that cannot be measured deterministically.
- Quantitative coverage of the rubric is incomplete.
- The variant is a foundation where "extensibility" or "clarity" is a rubric criterion.

### Step 5: Run L3 / L4 / L5 — scoped to the variant dimension
For **variant** evaluation (v2.0 atomic mode):
- **L2 — triggers**: SKIPPED. Variants don't own triggers; the composite does.
- **L3 — trace scoped**: check only whether the variant used its own scripts/references and stayed
  within its dimension. Score as a fraction: `(in-scope turns) / (total turns)`.
- **L4 — comparative within dimension only**: pairwise compare this variant against sibling variants
  in the same dimension, never across dimensions. The Scientist's rubric defines the comparison axis.
- **L5 — simplified**: the variant IS the trait, so trait-attribution collapses to the variant's
  overall score. Report it as-is rather than decomposing per instruction.

For **composite** (assembled skill) evaluation, run the full L1-L5 pipeline unchanged from v1.x.

### Step 6: Aggregate
Default weighting (overridable by rubric):
```
aggregate_fitness = quantitative_subtotal * 0.7 + qualitative_subtotal * 0.3
```

### Step 7: Emit the evaluation JSON
Write a single JSON object with these required fields:
```
{
  "variant_id": "...",
  "dimension": "...",
  "aggregate_fitness": 0.0..1.0,
  "quantitative_subtotal": 0.0..1.0,
  "qualitative_subtotal": 0.0..1.0,
  "metrics": { "<metric_name>": <raw_value>, ... },
  "weights": { "quantitative": 0.7, "qualitative": 0.3 },
  "l3_scope_score": 0.0..1.0,
  "l4_within_dim_rank": <int | null>,
  "l5_trait_summary": "..."
}
```

### Step 8: Validate the emitted JSON
Always validate before handing the result back:
```
bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh <path/to/evaluation.json>
```
Exit 0 means the JSON is structurally valid and weights (if present) sum to 1.0 ± 0.001. Exit 1 means
fix and re-emit. Never return an unvalidated evaluation.

## Examples

**Example 1: Scoring a mock-strategy capability variant**
Input: A competitor trace for variant `mock-strategy-v0` against the "inject a real HTTP call"
challenge, plus the rubric with four quantitative metrics summing to 1.0 and two qualitative strings.
Output: An evaluation JSON with `aggregate_fitness: 0.78`, `quantitative_subtotal: 0.81` (from
score.py + code_metrics.py), `qualitative_subtotal: 0.70` (from a focused Reviewer LLM call on the
two qualitative criteria), `l3_scope_score: 1.0` (variant stayed in its lane). Validator exits 0.

**Example 2: Foundation variant with extensibility criterion**
Input: Foundation variant `fixture-strategy-v2` that produced a skeleton package. Rubric includes
`code_runs` (boolean), `internal_consistency`, `extensibility`, `clarity`.
Output: Quantitative layer measures `code_runs` (1 if `validate.sh` exits 0, else 0) and pulls
cyclomatic complexity from `code_metrics.py` as a `clarity` proxy. `extensibility` has no automated
measure → fall back to qualitative LLM scoring for that single criterion. Aggregate: 0.72.

**Example 3: Near-miss — variant failed to run**
Input: Competitor produced an empty output directory because the variant's SKILL.md had a broken
`${CLAUDE_SKILL_DIR}` reference.
Output: `code_metrics.py` returns empty set, `score.py` is absent. `quantitative_subtotal: 0.0`,
`qualitative_subtotal: 0.0`, `aggregate_fitness: 0.0`. The Reviewer still emits a valid JSON (the
Breeder needs the signal) and logs the failure in `l5_trait_summary: "variant did not execute —
broken reference path"`.

## Common mistakes
- Running L2 (trigger accuracy) on a variant. Variants have no triggers — skip it.
- Comparing a foundation variant against a capability variant in L4. L4 is within-dimension only.
- Skipping `validate.sh` on the final JSON. The Breeder and Report consumers assume validated shape.
- Letting an unknown metric name survive into the output. Every metric must exist in
  `${CLAUDE_SKILL_DIR}/references/metrics-catalog.md`.
- Hardcoding the 0.7 / 0.3 split when the rubric specifies custom weights. Rubric weights win.
- Using LLM qualitative scoring when the metric is actually deterministic (e.g., judging "test
  pass rate" by vibes instead of running the tests).

## Out of Scope
This skill does NOT:
- Design challenges or rubrics (use `scientist`)
- Propose mutations based on scores (use `breeder`)
- Assemble variants into composites (use `engineer`)
- Classify skills into the taxonomy (use `taxonomist`)
