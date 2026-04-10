---
name: breeder
description: >-
  Refines skill variants across generations via reflective mutation grounded in
  fitness breakdowns and execution traces. Use when evolving, mutating, or
  crossing over variants inside a single dimension. NOT for assembling composites.
allowed-tools: Read Write Bash(python *) Bash(bash *)
---

# Breeder

## Quick Start
Given a variant's fitness breakdown + execution trace + learning log, identify the weakest metric, look up the matching mutation strategy, and emit a grounded mutation plan with rationale. Never mutate randomly — every edit must point at a specific weak metric and cite the trace evidence that justifies it.

## When to use this skill
Use when refining variants across generations in SKLD's atomic evolution loop. Triggers on "breed", "mutate", "refine", "improve this variant", "next generation", "crossover", "learning log", "weak metric", "reflective mutation", or any request to evolve a single-dimension variant toward a focused fitness target. Also triggers when someone says "why did this variant lose?" or "what should we change?" — even when they don't say "breeder."

This skill operates **horizontally** inside one variant dimension (e.g., `mock_strategy` or `assertion_pattern`). It does not assemble across dimensions — that belongs to `engineer`. It does not design the challenge or rubric — that belongs to `scientist`. It does not spawn generation 0 — that belongs to `spawner`.

## Core Principles

1. **Reflective, not random.** Every mutation targets the lowest-scoring metric from the fitness breakdown. Random edits are forbidden except for the 1-per-generation wildcard slot.
2. **Trace-grounded.** Read the execution trace to confirm the weak metric has a concrete symptom (e.g., "complexity 18 because of nested if-elif chain in lines 42-71"). Cite the line range in the rationale.
3. **Decouple description from body.** Description mutations (routing) and body mutations (execution) evolve on independent tracks. A description edit should not force a body edit unless the skill's capability shifts.
4. **Preserve elites.** The top-k variants by aggregate fitness carry forward unchanged each generation. Mutation only applies to non-elite slots.
5. **Learning log is persistent.** After each generation, append new lessons to the run's `learning_log: list[str]`. The log is injected into every subsequent Breeder prompt. Never rediscover a known failure.
6. **Multi-parent crossover** is allowed for non-elite slots when two parents have complementary strengths (e.g., parent A high on `trigger_precision`, parent B high on `test_pass_rate`). Inherit the strong trait from each.

## Workflow

### Step 1: Load fitness + trace + learning log
Read the variant's fitness JSON (from the Reviewer), the execution trace, and the current run's learning log.

- Fitness shape: `{"variant_id": "...", "quantitative": {...}, "qualitative": {...}, "aggregate_fitness": 0.X}`
- Read `${CLAUDE_SKILL_DIR}/references/metrics-to-mutations.md` to know how each metric maps to an edit pattern.
- Read `${CLAUDE_SKILL_DIR}/references/mutation-patterns.md` for the full strategy catalog (reflective mutation, crossover, elitism, wildcard, description-body decoupling, example injection).

### Step 2: Identify the weakest metric
Run the analyzer to pick the lowest-scoring metric and look up its mutation strategy:

```
python ${CLAUDE_SKILL_DIR}/scripts/analyze_fitness.py --fitness /tmp/variant_fitness.json
```

Output is a JSON object: `{"variant_id", "weakest_metric", "weakest_score", "mutation_strategy", "rationale"}`.

If the weakest metric is not in the lookup table, fall back to `generic_refinement` and flag the gap so the metrics catalog can be extended.

### Step 3: Ground the strategy in trace evidence
Open the execution trace and locate the concrete symptom that caused the weak score. For code metrics, cite line ranges. For trigger metrics, cite the exact description phrases Claude matched against. For test failures, cite the assertion that failed. The rationale in the final mutation plan **must** include this citation — otherwise the mutation is ungrounded and should be rejected.

### Step 4: Consult the learning log
Read `run.learning_log` (passed in via the prompt context). If a prior generation already tried the recommended strategy on this dimension and failed, skip that strategy and pick the next-weakest metric instead. Append a `"learned: <strategy> does not work for <symptom>"` entry before proceeding.

### Step 5: Emit the mutation plan
Produce a structured mutation plan with exact edits (file path, old text → new text), preserved invariants (name regex, ≤500-line body, ≤250-char description, `${CLAUDE_SKILL_DIR}/` paths), and the grounded rationale.

### Step 6: Validate
```
bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh /tmp/mutation_output.json
```

If validation fails (missing field, empty rationale, ungrounded strategy), fix the plan and re-validate before returning.

### Step 7: Append to learning log
After the mutation is scored in the next generation, append the outcome to the run's learning log as a one-line lesson: `"gen N: <strategy> on <dimension> improved <metric> by +X.XX"` or `"gen N: <strategy> on <dimension> did not improve <metric>; try <alternative>"`.

## Mutation Slot Allocation (per non-elite generation)

For a population of size P with elitism K:
- **K slots**: elites carried unchanged.
- **~(P-K-1) slots**: reflective mutation targeting weakest metric of each parent.
- **1 slot**: wildcard — a deliberately exploratory mutation (random pattern pick, or a cross-parent experiment). Prevents local optima lock-in.
- **Optional**: 1 multi-parent crossover slot when two parents have clearly complementary strengths.

## Examples

**Example 1: High cyclomatic complexity**
Input: Variant fitness `{"quantitative": {"cyclomatic_complexity": 0.18, "test_pass_rate": 0.92, "token_usage": 0.71}, "aggregate_fitness": 0.54}`. Trace shows a 6-branch `if/elif` chain in `scripts/main_helper.py` lines 42-71.
Output: Mutation plan targeting `cyclomatic_complexity`. Strategy: "simplify_control_flow". Edit: extract branches into a dispatch dict `HANDLERS = {...}` and replace the chain with `HANDLERS.get(kind, default)(payload)`. Rationale: "cyclomatic_complexity=0.18 (weakest); trace shows 6-branch if/elif in main_helper.py:42-71; dispatch dict collapses branches to 1 lookup + 1 call."

**Example 2: Low trigger precision**
Input: Variant fitness `{"quantitative": {"trigger_precision": 0.31, "trigger_recall": 0.88}, "aggregate_fitness": 0.52}`. Trace shows the skill activated on 9 unrelated user prompts (noisy skill anti-pattern).
Output: Mutation plan targeting `trigger_precision`. Strategy: "refine_description_exclusions". Edit: description — append "NOT for <adjacent-domain-1>, <adjacent-domain-2>, or <adjacent-domain-3>" clause; tighten capability statement from "handles data tasks" to "validates CSV headers against a schema". Rationale: "trigger_precision=0.31; trace shows 9 false activations on adjacent prompts; explicit NOT-for exclusions are the proven fix per bible/patterns/descriptions.md §AP-DESC-002."

**Example 3: Plateau on test_pass_rate**
Input: Variant fitness `{"quantitative": {"test_pass_rate": 0.67, ...}}`. Learning log shows `"gen 1: add_edge_cases on assertion_pattern did not improve test_pass_rate"`. Only 1 example in SKILL.md.
Output: Mutation plan targeting `test_pass_rate` via the **example-injection** pattern instead of edge-case expansion (which already failed). Strategy: "inject_worked_examples". Edit: add 2 new I/O examples to the Examples section covering the two failing test shapes from the trace. Rationale: "test_pass_rate=0.67; learning log rules out add_edge_cases; bible finding §009 shows example count 1→3 empirically lifts quality 72%→90%; failing tests in trace match two unexampled shapes."

## Gotchas
- **Ungrounded rationale** — if the rationale doesn't cite a specific trace symptom (line range, exact phrase, failing assertion), reject the mutation and re-run Step 3.
- **Mutating the elite** — elites carry forward unchanged. Double-check the variant isn't in the top-k before mutating.
- **Ignoring the learning log** — repeating a strategy that already failed wastes a generation. Always scan `run.learning_log` before picking a strategy.
- **Coupling description + body** — changing both in one mutation makes attribution impossible. Pick one track per mutation unless the capability itself is changing.
- **Over-editing** — one mutation = one weak metric. Fixing 3 metrics in one edit destroys L5 trait attribution.

## Out of Scope
This skill does NOT:
- Assemble composite skills across dimensions (use `engineer` instead)
- Design challenges or rubrics (use `scientist`)
- Spawn gen 0 populations (use `spawner`)
- Decide whether to evolve molecularly vs atomically (use `taxonomist`)
- Run the competitor — mutation plans are consumed by the Evolution Engine
