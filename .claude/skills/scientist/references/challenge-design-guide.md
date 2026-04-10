# Challenge Design Guide

This guide teaches the Scientist how to design focused, measurable challenges
for SKLD variant evolution. Every challenge targets exactly **one** variant
dimension and is paired with a rubric whose weights sum to 1.0.

## Core principles

1. **One dimension per challenge.** A challenge is a microscope, not a net. If
   the prompt exercises two independent decisions (e.g. mock strategy *and*
   fixture strategy), split it into two dimensions and two challenges.
2. **Measurable success criteria.** Deterministic beats LLM-judged beats vibes.
   Prefer `validator_exit_code`, `test_pass_rate`, or AST-derived numbers over
   prose judgement. Reserve qualitative criteria for the last 10–20% that
   numbers genuinely cannot capture.
3. **The prompt must make the dimension observable in the output.** If the
   reviewer cannot point at a concrete artifact that reflects the dimension,
   the challenge is underspecified. Name files, commands, or function
   signatures explicitly.
4. **Match difficulty to tier.** Foundation variants encode broad structural
   decisions and need harder, more realistic tasks. Capability variants encode
   narrow modules and need short, sharp tasks.
5. **Same challenge for every variant in a dimension.** The whole point of
   atomic evolution is fair comparison. Never change the prompt between
   generations inside the same dimension — freeze it on creation.
6. **Fixtures are part of the challenge.** Reference files from `test_fixtures/`
   by path. Every variant in the dimension sees the same bytes.

## Tier calibration

| Tier | Scope | Difficulty | Turn budget | Verification |
|------|-------|-----------|-------------|--------------|
| foundation | Structural choices (layout, naming, fixtures, conventions) | medium–hard | 10–15 | hybrid or deterministic |
| capability | Focused modules (mocks, parsers, CLI, formatters) | easy–medium | 5–10 | deterministic preferred |

Foundation challenges should exercise extensibility ("a new X must plug in
without editing existing files"). Capability challenges should exercise a
single concrete behavior ("parse this fixture into that shape").

## Prompt-writing checklist

- [ ] Single dimension named in the first sentence
- [ ] At least one fixture path (`test_fixtures/...`) referenced
- [ ] Concrete artifact names (files, functions, outputs) the reviewer can inspect
- [ ] Explicit constraints that map directly to `instruction_compliance`
- [ ] No "and also" / "while handling" / "bonus points for" clauses
- [ ] Prompt length under 10 sentences — longer usually means overloaded

## Rubric-writing checklist

- [ ] 2–6 quantitative entries
- [ ] Every `metric` present in the metrics catalog
- [ ] Weights sum to exactly 1.0 (close gaps with the last entry)
- [ ] Each `description` explains *why this metric matters for this dimension*
- [ ] `qualitative` list is empty for `verification_method: deterministic`
- [ ] `qualitative` entries are single-sentence, judge-able criteria

## Example rubrics by domain

### Python code quality dimension — `function-decomposition`
```json
{
  "dimension": "function-decomposition",
  "quantitative": [
    {"metric": "cyclomatic_complexity", "weight": 0.3, "description": "Average McCabe across produced functions"},
    {"metric": "max_function_length", "weight": 0.3, "description": "Longest function stays under 30 lines"},
    {"metric": "function_count", "weight": 0.2, "description": "Enough functions to show decomposition"},
    {"metric": "test_pass_rate", "weight": 0.2, "description": "Behavior preserved after refactor"}
  ],
  "qualitative": []
}
```

### Infrastructure-as-Code dimension — `terraform-modules`
```json
{
  "dimension": "terraform-modules",
  "quantitative": [
    {"metric": "validator_exit_code", "weight": 0.4, "description": "terraform validate returns 0"},
    {"metric": "file_count", "weight": 0.2, "description": "Modularization without sprawl"},
    {"metric": "max_nesting_depth", "weight": 0.2, "description": "Resource blocks stay shallow"},
    {"metric": "instruction_compliance", "weight": 0.2, "description": "Extensibility requirement satisfied"}
  ],
  "qualitative": [
    "Module boundaries should map to distinct resource concerns"
  ]
}
```

### Data processing dimension — `pandas-pipeline`
```json
{
  "dimension": "pandas-pipeline",
  "quantitative": [
    {"metric": "test_pass_rate", "weight": 0.4, "description": "Pipeline output matches fixture expected.csv"},
    {"metric": "wall_time_sec", "weight": 0.2, "description": "Pipeline runs within budget on fixture"},
    {"metric": "cyclomatic_complexity", "weight": 0.2, "description": "Transformations stay readable"},
    {"metric": "import_count", "weight": 0.2, "description": "Lean dependency surface"}
  ],
  "qualitative": []
}
```

### UI/frontend dimension — `react-component-api`
```json
{
  "dimension": "react-component-api",
  "quantitative": [
    {"metric": "compiles", "weight": 0.3, "description": "TSX builds under strict mode"},
    {"metric": "lint_score", "weight": 0.2, "description": "eslint clean"},
    {"metric": "max_function_length", "weight": 0.2, "description": "Component bodies stay focused"},
    {"metric": "instruction_compliance", "weight": 0.3, "description": "Required props and a11y attributes present"}
  ],
  "qualitative": [
    "Component API should be composable — no internal state leaks through props"
  ]
}
```

## Anti-patterns

- **Multi-dimensional challenge.** "Build a REST endpoint with validation and
  caching and tests." That is three dimensions. Split them.
- **Pure-vibe scoring.** A rubric with only qualitative entries is the L4 trap:
  LLM judgement becomes the measurement. Always anchor with at least one
  deterministic metric unless the dimension is genuinely unmeasurable.
- **Moving goalposts.** Editing the prompt or fixtures between generations
  inside the same dimension invalidates every prior fitness score. Freeze on
  creation.
- **Invented metric names.** If the catalog does not have what you need, add
  the metric to the catalog first and get it reviewed. Never ship a rubric
  that the validator rejects because it references a non-catalog metric.
- **Prompt leakage.** Do not describe the rubric inside the challenge prompt.
  Variants should satisfy the spirit of the task, not game the scoring.
- **Fixture mutation.** Challenges must reference fixtures by path; never embed
  the fixture contents in the prompt. The prompt is a recipe, not a copy.

## Encoding fixtures in the challenge

Every fixture file lives in `test_fixtures/` at the skill-package root. The
Scientist references them by relative path inside the challenge JSON:

```json
{
  "dimension": "<slug>",
  "prompt": "... see test_fixtures/input.csv ...",
  "difficulty": "medium",
  "verification_method": "deterministic",
  "fixtures": ["test_fixtures/input.csv", "test_fixtures/expected.csv"]
}
```

The competitor receives fixtures as part of its isolated working directory.
The reviewer diffs outputs against expected fixtures where applicable. Because
fixtures are immutable within a run, reproducibility is guaranteed: same
variant + same fixture + same foundation → same environment every time.
