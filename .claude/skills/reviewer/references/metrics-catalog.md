# Metrics Catalog

This document is the canonical authority for every metric SKLD measures. The Scientist's
rubric `metric` fields must reference a name defined here. The Reviewer computes them. The
Breeder reads them to decide mutations. The post-run Report serializes them. If a metric is
not in this file, it does not exist.

Each entry lists: **name**, **category**, **description**, **how_calculated**, **thresholds**,
and **interpretation**.

---

## Execution metrics

These are captured automatically by the Evolution Engine for every Competitor run. They do not
require LLM judgment.

### wall_time_sec
- **category**: execution
- **description**: Total wall-clock time of the competitor run in seconds.
- **how_calculated**: `time.monotonic()` delta around the Competitor's Agent SDK invocation.
- **thresholds**: `<30s` excellent, `30-120s` normal, `>300s` investigate.
- **interpretation**: Lower is better when fitness is held constant. Used as the denominator
  of `speed_quality`.

### turn_count
- **category**: execution
- **description**: Number of assistant turns the Competitor consumed.
- **how_calculated**: Count of assistant messages in the trace.
- **thresholds**: `<=5` lean, `6-10` normal, `>15` hit the budget cap.
- **interpretation**: Fewer turns on the same challenge is better — the skill is more direct.

### tool_call_count
- **category**: execution
- **description**: Total tool invocations during the run.
- **how_calculated**: Count of tool-use blocks in the trace.
- **thresholds**: none — domain-dependent.
- **interpretation**: Input to `tool_precision`.

### token_usage
- **category**: execution
- **description**: Sum of input + output tokens for the run.
- **how_calculated**: Sum of `usage.input_tokens + usage.output_tokens` across all turns.
- **thresholds**: domain-dependent; flag if an atomic-mode variant exceeds `20k` tokens.
- **interpretation**: Denominator of `efficiency`.

### cost_usd
- **category**: execution
- **description**: Dollar cost of the run.
- **how_calculated**: Token counts multiplied by the per-model price from `config.py`.
- **thresholds**: atomic variant runs should stay under `$0.10`.
- **interpretation**: Rolled up into `max_budget_usd` enforcement.

---

## Output metrics

These measure what the variant produced, not how it got there.

### compiles
- **category**: output
- **description**: Whether the produced code parses / compiles.
- **how_calculated**: Language-specific: Python → `ast.parse`, JS/TS → `tsc --noEmit`, shell → `bash -n`.
- **thresholds**: boolean. `1` = compiles, `0` = broken.
- **interpretation**: A `0` here short-circuits most other metrics — broken code cannot pass tests.

### test_pass_rate
- **category**: output
- **description**: Fraction of tests that pass after the variant's changes.
- **how_calculated**: `passing_tests / total_tests` from the test runner output.
- **thresholds**: `>=0.9` strong, `0.7-0.9` acceptable, `<0.7` weak.
- **interpretation**: The most reliable quality signal for code-generation variants.

### coverage_delta
- **category**: output
- **description**: Change in test coverage attributable to the variant's output, as a fraction.
- **how_calculated**: `post_coverage - pre_coverage` from a coverage tool (e.g., `coverage.py`).
- **thresholds**: `>=0.05` noteworthy gain, `<0` regression.
- **interpretation**: Positive deltas indicate the variant added meaningful tests.

### lint_score
- **category**: output
- **description**: Normalized lint cleanliness on a `[0, 1]` scale.
- **how_calculated**: `1 - min(1, lint_errors / 10)` using the project's linter (e.g., `ruff`).
- **thresholds**: `>=0.9` clean, `<0.7` noisy.
- **interpretation**: A cheap proxy for style discipline.

### validator_exit_code
- **category**: output
- **description**: Exit code of the variant's own `scripts/validate.sh`.
- **how_calculated**: Run `validate.sh` against the variant's output, capture the integer exit code.
- **thresholds**: `0` = valid, non-zero = invalid.
- **interpretation**: Hard gate on structural validity before any other scoring runs.

### file_count
- **category**: output
- **description**: Number of files produced or modified by the variant.
- **how_calculated**: `git status --porcelain` in the sandbox, counted.
- **thresholds**: domain-dependent.
- **interpretation**: Context for complexity judgments.

---

## Code quality proxies (AST-based)

Computed by `scripts/code_metrics.py`. All limited to Python in v2.0; JS/TS returns an
`unsupported` record without blocking the rest of the pipeline.

### cyclomatic_complexity
- **category**: code_quality
- **description**: Approximate McCabe complexity across the whole module.
- **how_calculated**: `1 + sum(branch_nodes) + sum(extra BoolOp operands)` where `branch_nodes`
  covers `If`, `For`, `While`, `Try`, `ExceptHandler`, `With`, `IfExp`, and the four comprehensions.
- **thresholds**: `<=10` simple, `11-20` moderate, `>20` complex.
- **interpretation**: Lower is better for maintainability. Spikes suggest a target for mutation.

### max_function_length
- **category**: code_quality
- **description**: Line span of the longest function in the file.
- **how_calculated**: `max(end_lineno - lineno + 1)` over all `FunctionDef` / `AsyncFunctionDef`.
- **thresholds**: `<=40` good, `41-80` watch, `>80` refactor target.
- **interpretation**: Long functions correlate with low testability.

### max_nesting_depth
- **category**: code_quality
- **description**: Deepest AST nesting level across control-flow + scope nodes.
- **how_calculated**: Recursive descent, adding 1 when entering any nesting node.
- **thresholds**: `<=3` good, `4-5` acceptable, `>=6` problematic.
- **interpretation**: Deep nesting predicts cyclomatic complexity and reader confusion.

### function_count
- **category**: code_quality
- **description**: Total function definitions in the file or package.
- **how_calculated**: Count of `FunctionDef` + `AsyncFunctionDef` nodes.
- **thresholds**: none — context only.
- **interpretation**: Context for interpreting complexity averages.

### import_count
- **category**: code_quality
- **description**: Count of `import` / `from ... import` statements.
- **how_calculated**: Count of `Import` + `ImportFrom` nodes.
- **thresholds**: `>30` in a single file is a smell.
- **interpretation**: High counts can signal god-modules or missing encapsulation.

---

## Derived metrics

These are computed by the Reviewer from other metrics in this catalog.

### efficiency
- **category**: derived
- **description**: Fitness achieved per token spent.
- **how_calculated**: `aggregate_fitness / max(1, token_usage)`, then scaled by `1e4` for readability.
- **thresholds**: higher is better.
- **interpretation**: The primary cost-effectiveness signal for research paper analysis.

### speed_quality
- **category**: derived
- **description**: Fitness achieved per second of wall time.
- **how_calculated**: `aggregate_fitness / max(0.1, wall_time_sec)`.
- **thresholds**: higher is better.
- **interpretation**: Surfaces variants that are both fast and good.

### instruction_compliance
- **category**: derived
- **description**: Fraction of SKILL.md numbered steps the Competitor actually followed.
- **how_calculated**: From the trace: `followed_steps / total_steps_in_skill_md`.
- **thresholds**: `>=0.9` high compliance, `<0.7` weak.
- **interpretation**: Low scores mean the instructions are unclear or ignorable.

### tool_precision
- **category**: derived
- **description**: Fraction of tool uses that were inside the `allowed_tools` set.
- **how_calculated**: `|used_tools ∩ allowed_tools| / max(1, |used_tools|)`.
- **thresholds**: `1.0` ideal, `<1.0` means the skill is reaching outside its declared toolbox.
- **interpretation**: Feeds Breeder mutations that tighten `allowed-tools`.

---

## How other skills should reference this catalog

- **Scientist**: every `metric` name in a generated rubric MUST appear above. Use
  `scripts/validate_rubric.py` to enforce this.
- **Breeder**: consult `references/metrics-to-mutations.md` for mappings, then read this catalog
  to understand what the failing metric actually measures before proposing mutations.
- **Engineer**: assembly evaluation uses `test_pass_rate`, `validator_exit_code`, and the code
  quality proxies against the composite skill.
- **Spawner**: read the "Code quality proxies" section so spawned variants are structured to be
  parseable (real Python code, not pseudo-code blobs).
