# Metrics Catalog (Scientist copy)

> **Sync note**: this is a synced copy of the Reviewer's canonical metrics catalog
> (`${CLAUDE_SKILL_DIR}/.claude/skills/reviewer/references/metrics-catalog.md`).
> Reconcile if the Reviewer's version differs. The Scientist uses this as the
> authoritative list of metric names that may appear in rubric JSON.

Every entry below defines: **name** (the identifier used in rubric JSON),
**category**, **calculation**, **thresholds**, and **how to use in rubrics**.
The rubric validator matches against `## <name>` headers and `**<name>**` bold
spans, so keep the formatting consistent.

---

## Execution metrics

## wall_time_sec
- **category**: execution
- **calculation**: end-to-end seconds from competitor spawn to final turn
- **thresholds**: <30s excellent, 30–90s normal, >180s slow
- **rubric use**: weight 0.1–0.25 when speed matters; penalize high values via a
  linear or inverse mapping in `score.py`

## turn_count
- **category**: execution
- **calculation**: number of agent SDK turns consumed by the competitor
- **thresholds**: 1–5 focused, 6–10 normal, >12 thrashing
- **rubric use**: proxy for planning quality; combine with output quality

## tool_call_count
- **category**: execution
- **calculation**: total tool invocations across all turns
- **thresholds**: <10 tight, 10–25 normal, >40 spammy
- **rubric use**: lower is better when paired with an equal-quality outcome

## token_usage
- **category**: execution
- **calculation**: sum of input + output tokens (SDK accounting)
- **thresholds**: skill-dependent; compare within-dimension only
- **rubric use**: cost proxy; use inside derived `efficiency`

## cost_usd
- **category**: execution
- **calculation**: token_usage × model rate
- **thresholds**: runs should stay inside `max_budget_usd`
- **rubric use**: rarely used directly; usually aggregated in the run report

---

## Output metrics

## compiles
- **category**: output
- **calculation**: boolean — does the primary artifact parse/compile cleanly
- **thresholds**: hard gate — 0 should zero out most rubrics
- **rubric use**: weight 0.2–0.4 in any code-generation dimension

## test_pass_rate
- **category**: output
- **calculation**: passing_tests / total_tests (0.0–1.0)
- **thresholds**: ≥0.9 excellent, 0.7–0.9 acceptable, <0.7 failing
- **rubric use**: core weight for correctness-centric dimensions

## coverage_delta
- **category**: output
- **calculation**: coverage_after − coverage_before on touched files
- **thresholds**: ≥0.1 strong, 0.01–0.1 modest, ≤0 regression
- **rubric use**: pair with test_pass_rate; avoid double-counting

## lint_score
- **category**: output
- **calculation**: 1.0 − (lint_errors / max(1, lint_checks))
- **thresholds**: ≥0.95 clean, 0.8–0.95 noisy, <0.8 broken
- **rubric use**: weight 0.1–0.2 in style-sensitive dimensions

## validator_exit_code
- **category**: output
- **calculation**: exit status of the dimension-specific validator (0 = pass)
- **thresholds**: 0 = full credit, non-zero = 0
- **rubric use**: preferred boolean gate for deterministic rubrics

## file_count
- **category**: output
- **calculation**: number of files the competitor created or modified
- **thresholds**: dimension-dependent; extreme values usually indicate drift
- **rubric use**: signal for overgeneration or skimping; weight 0.05–0.15

---

## Code quality proxies (AST)

## cyclomatic_complexity
- **category**: code_quality
- **calculation**: average McCabe complexity across functions, via
  `skillforge/engine/code_metrics.py`
- **thresholds**: ≤5 simple, 6–10 moderate, >10 risky
- **rubric use**: weight 0.1–0.25 for clarity-focused dimensions

## max_function_length
- **category**: code_quality
- **calculation**: longest function body in lines (non-blank, non-comment)
- **thresholds**: ≤30 tight, 31–60 normal, >80 bloated
- **rubric use**: proxy for decomposition quality

## max_nesting_depth
- **category**: code_quality
- **calculation**: deepest nesting of control structures observed
- **thresholds**: ≤3 clean, 4 acceptable, ≥5 tangled
- **rubric use**: complements cyclomatic_complexity

## function_count
- **category**: code_quality
- **calculation**: number of defined functions (or equivalents per language)
- **thresholds**: dimension-specific; watch for both 0 and absurdly high
- **rubric use**: sanity check for modularity

## import_count
- **category**: code_quality
- **calculation**: number of unique top-level imports
- **thresholds**: ≤10 lean, 11–25 normal, >40 smells
- **rubric use**: weight 0.05–0.15 for minimalism or isolation dimensions

---

## Derived metrics

## efficiency
- **category**: derived
- **calculation**: fitness_score / token_usage (normalized per-dimension)
- **thresholds**: compare within-dimension only
- **rubric use**: research metric; rarely enters rubric JSON directly

## speed_quality
- **category**: derived
- **calculation**: fitness_score / wall_time_sec
- **thresholds**: within-dimension comparison
- **rubric use**: optional secondary weight for latency-sensitive dimensions

## instruction_compliance
- **category**: derived
- **calculation**: fraction of explicit prompt requirements satisfied (L4 check)
- **thresholds**: 1.0 full, ≥0.8 mostly, <0.6 ignoring prompt
- **rubric use**: preferred qualitative-becoming-quantitative signal; weight
  0.2–0.4 for dimensions whose challenge imposes hard constraints

## tool_precision
- **category**: derived
- **calculation**: useful_tool_calls / total_tool_calls
- **thresholds**: ≥0.8 focused, 0.5–0.8 normal, <0.5 flailing
- **rubric use**: diagnostic; low weight when used at all
