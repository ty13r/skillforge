# Scoring Rubric Spec

The Scientist produces one rubric JSON per variant dimension. The Reviewer consumes it to
score every variant in that dimension. This document is the authoritative schema.

## Top-level shape

```json
{
  "dimension": "mock-strategy",
  "quantitative": [
    {
      "metric": "isolation_score",
      "weight": 0.4,
      "description": "Are external deps fully isolated?",
      "type": "numeric"
    }
  ],
  "qualitative": [
    "Mocks should be maintainable — no brittle implementation detail coupling"
  ],
  "weights": {
    "quantitative": 0.7,
    "qualitative": 0.3
  }
}
```

## Required fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `dimension` | string | yes | Matches the variant dimension slug (kebab-case). |
| `quantitative` | array of objects | yes | At least one entry. Each entry matches the shape below. |
| `qualitative` | array of strings | yes | May be empty `[]` if fully quantitative. |
| `weights` | object | no | Optional top-level split between quantitative and qualitative subtotals. Defaults to `{"quantitative": 0.7, "qualitative": 0.3}`. |

## Quantitative entry fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `metric` | string | yes | Must exist in `references/metrics-catalog.md`. |
| `weight` | number `[0, 1]` | yes | Weight within the quantitative subtotal. |
| `description` | string | yes | Human-readable one-liner. |
| `type` | string | no | One of `numeric` (default), `boolean`, `percentage`. |

## Validation rules

1. Every `quantitative[*].metric` MUST appear in the canonical metrics catalog. Unknown names
   fail validation.
2. The sum of `quantitative[*].weight` MUST equal `1.0 ± 0.001`.
3. If `weights` is present at the top level, `weights.quantitative + weights.qualitative` MUST
   equal `1.0 ± 0.001`.
4. `qualitative` items are free-form strings; they are judged by a focused LLM call.
5. `dimension` MUST match the dimension slug the Scientist generated in the taxonomy.

## Worked example — capability variant

```json
{
  "dimension": "mock-strategy",
  "quantitative": [
    {"metric": "test_pass_rate",       "weight": 0.4, "description": "Tests pass under the variant's mocks"},
    {"metric": "cyclomatic_complexity","weight": 0.2, "description": "Mock setup stays simple"},
    {"metric": "max_function_length",  "weight": 0.2, "description": "No giant setup helpers"},
    {"metric": "lint_score",           "weight": 0.2, "description": "Mock code is clean"}
  ],
  "qualitative": [
    "Mocks should behave like real deps in happy-path and failure cases",
    "Should not couple to private implementation details"
  ]
}
```

Weights sum: `0.4 + 0.2 + 0.2 + 0.2 = 1.0`. Valid.

## Worked example — foundation variant

```json
{
  "dimension": "foundation",
  "quantitative": [
    {"metric": "validator_exit_code",  "weight": 0.3, "description": "Structure validator passes", "type": "boolean"},
    {"metric": "compiles",             "weight": 0.2, "description": "Produced code parses",        "type": "boolean"},
    {"metric": "cyclomatic_complexity","weight": 0.25,"description": "Foundation stays readable"},
    {"metric": "max_nesting_depth",    "weight": 0.25,"description": "Foundation is extensible"}
  ],
  "qualitative": [
    "Capability variants should plug into this foundation without structural surgery",
    "Internal conventions are consistent throughout"
  ]
}
```

## How weights roll up into aggregate fitness

The Reviewer computes:

```
quantitative_subtotal = sum(normalize(metric_value, catalog_thresholds) * entry.weight
                            for entry in rubric.quantitative)

qualitative_subtotal  = mean(llm_score(criterion)
                             for criterion in rubric.qualitative)

aggregate_fitness     = quantitative_subtotal * weights.quantitative
                      + qualitative_subtotal  * weights.qualitative
```

Where `weights` defaults to `{"quantitative": 0.7, "qualitative": 0.3}` when the rubric does
not specify its own split. Both subtotals are in `[0, 1]`; `aggregate_fitness` therefore lives
in `[0, 1]` as well.

## Common validation failures

- **Unknown metric name** — typo against the catalog. Fix: use `validate_rubric.py`.
- **Weights do not sum to 1.0** — most often off by `0.05` from hand-editing. Fix: rescale.
- **Empty `quantitative` list** — the rubric is unusable. Always include at least one deterministic
  measurement, even for subjective dimensions (use `compiles` or `validator_exit_code` as a floor).
- **Boolean metric with a non-boolean weight consumer** — if `type: "boolean"`, the normalized
  value is exactly `0.0` or `1.0`; do not try to interpolate.
- **Qualitative list of objects instead of strings** — qualitative criteria are plain strings the
  Reviewer passes to the LLM verbatim.

## Referencing this spec

Other agents should link to this document when emitting or consuming rubrics:
- Scientist's `scripts/validate_rubric.py` enforces these rules.
- Reviewer's `scripts/validate.sh` validates the downstream evaluation JSON, which depends on
  rubric shape matching this spec.
- The post-run Report stores the rubric alongside each variant's evaluation for reproducibility.
