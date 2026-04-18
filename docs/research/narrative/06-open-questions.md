# Open Questions

> **Status:** drafting · **Depth:** skeletal · **Last updated:** 2026-04-18
>
> Ten questions with experiment shapes sketched but none of the experiments have been run yet. Entries will migrate off this page (into findings or rigor arc) as they close.

SKLD has shipped seven seed runs, 867 challenges, and a six-layer composite scorer. This page is the list of uncomfortable questions the current evidence does *not* answer. Each question is the seed of a future experiment; anyone reading this is invited to poke at them.

---

## 1. Does an evolved skill generalize across languages?

Every lighthouse family in SKLD-bench is Elixir. We have no evidence yet that a foundation variant evolved for `elixir-ecto-query-writer` — say, "always narrow the schema before joining" — transfers as a reusable capability to a hypothetical `python-sqlalchemy-query-writer` or `typescript-prisma-query-writer`.

The methodology supports the test. SKLD-bench's structure is language-agnostic; nothing prevents adding a Python or TypeScript lighthouse family with its own challenges, scaffold, and score.py. What we need is the content: one or two non-Elixir lighthouse families and a concrete cross-language port experiment. Until that runs, "cross-family reuse" is a design affordance, not a result.

**Experiment shape.** Port `elixir-ecto-query-writer`'s winning foundation variant to a new `python-sqlalchemy-query-writer` family with its own challenges. Measure whether the ported variant outperforms a fresh spawn. Positive result supports the cross-language thesis; null result is also informative.

## 2. Is reflective mutation quantitatively better than random mutation?

The claim that reflective mutation (GEPA-style, trace-informed diagnosis) produces larger per-generation fitness gains than random mutation is currently supported only by informal comparison — Matt and Claude looking at run output and concluding it feels better. The rigorous version is an **ablation**: run two pipelines side by side on the same family, one with reflective mutation, one with random mutation, matched on generation count and challenge budget.

**Experiment shape.** Pick one family (probably `elixir-pattern-match-refactor` because it has the clearest per-generation signal), run 5 generations of reflective mutation and 5 generations of random mutation on identical seed populations, compare headline held-out fitness. Repeat 3× for variance.

## 3. Does the held-out score differ meaningfully from the training score?

SKLD-bench holds out ~20% of each challenge pool for champion evaluation. In principle this measures whether variants generalize rather than memorize. In practice we have not yet run the comparison: all shipped fitness numbers are training-set scores because the held-out evaluator landed after the seed runs.

The infrastructure exists; the experiment is the next obvious step.

**Experiment shape.** Re-score every shipped champion against its family's held-out pool. If training and held-out scores are close, the benchmark is robust. If they diverge by more than a few percentage points, we have evidence of train-set contamination that needs fixing.

## 4. How much variance is in a single fitness number?

Every fitness score in SKLD-bench today is a single-run score. Claude output is non-deterministic; the same variant on the same challenge can score differently across repeats. A production-grade evaluation would run each challenge N times and report mean + variance.

We have not yet measured the variance. This matters because small fitness deltas (0.78 → 0.82) might be within the noise floor.

**Experiment shape.** Pick 20 challenges across difficulty tiers, run each 5 times with the same variant, measure the standard deviation of the composite score. Publish the noise floor. Any claimed fitness improvement smaller than the noise floor is meaningless.

## 5. Can SKLD push Opus beyond Opus raw?

The evidence so far says skills are a Sonnet equalizer, not an Opus accelerator (finding #2 in `05-findings-summary.md`). That's a useful result, but it's a negative result for Opus users: a skill-guided Opus is barely better than Opus raw.

Is this a hard limit, or an artifact of the challenge pool being too easy for Opus? The SKLD-bench tiers were heuristically calibrated. A `legendary` tier *should* stress Opus, but empirical confirmation is missing.

**Experiment shape.** Generate a set of deliberately hard challenges — multi-file refactors, challenges requiring cross-module reasoning, challenges where Opus raw scores below 0.5. Test whether a skill lifts Opus on those. If yes, the current plateau is a challenge-difficulty artifact. If no, skills have a capability ceiling at the underlying model.

## 6. Do evolved skills hit a fitness plateau?

We have shipped seed runs (typically 2 generations, sometimes 3 on a single dimension). What happens at generation 10? 20? Does fitness keep rising, asymptote, or regress?

A rising curve validates the evolution mechanism. An asymptote is useful information about the ceiling. Regression would reveal a bug in the Breeder or the fitness function.

**Experiment shape.** Pick one family, run 10 generations on a single dimension (probably `mount-and-lifecycle` on phoenix-liveview because it's the dimension with the cleanest signal), plot fitness per generation, identify the inflection.

## 7. Is meta-mode lift real?

SKLD supports a "meta-mode" where the pipeline evolves the *skills of the pipeline's own agents* — a better Breeder skill, a better Engineer skill. This is recursive self-improvement on paper. In practice we have not yet run meta-mode end-to-end with a rigorous measurement.

The question is whether meta-mode produces measurable downstream fitness gains on the actual skill-evolution pipeline, or whether it is theoretical.

**Experiment shape.** Baseline: run the current pipeline on a new family, record headline fitness. Meta run: evolve the Breeder's skill across 3 generations using pipeline performance as the fitness function. Post-meta run: re-run the pipeline on the same family with the evolved Breeder. Compare headline fitness. Repeat for Engineer. Report lift — or absence of lift.

## 8. Does empirical tier calibration change the numbers?

SKLD-bench tiers are currently assigned heuristically during challenge drafting (single-step vs multi-step, ambiguity, prior knowledge). The SPEC called for empirical calibration via multi-model baseline pass rates; it was deferred because the calibration sweep was too expensive for the overnight window (~5,400 dispatches).

Is the heuristic close enough to empirical? If we run the calibration sweep now and re-tier challenges, does the fitness picture change?

**Experiment shape.** Run the Haiku + Sonnet pass-rate sweep (3 trials each × 867 challenges = ~5,200 dispatches), re-assign tiers empirically, re-compute the difficulty curves for every shipped champion. If the curves shift materially, the heuristic was wrong. If they don't, the heuristic was good enough.

## 9. What is the right way to measure trigger accuracy inside SKLD-bench?

Anthropic's skill-creator pioneered a rigorous methodology for measuring skill *activation* — generate should-trigger and should-not-trigger query sets, run each 3 times, measure precision/recall. SKLD borrowed the concept but has not yet instrumented it against SKLD-bench.

This is the L2 layer that's specced but not shipped. The question is not whether to build it — we should — but what data model makes the results auditable. Where do the query sets live? How does the run_loop integrate with SKLD's composite scorer? What's the right weight in the composite?

**Build shape.** Not an experiment — an implementation task. Documented as a near-term priority; scope in `plans/PLAN-V2.1.3.md`.

## 10. Is the benchmark itself discriminating enough?

SKLD-bench was authored overnight by Opus subagents with Matt reviewing partial outputs in the morning (Journal #12). It is substantive — 867 challenges, 7 families, 6-layer composite scoring — but it is not yet externally validated. We don't know whether the challenge pools cover the failure surface or leave gaps a skilled evader could walk through.

The right way to stress this is with adversarial authoring: hand-craft a skill that scores perfectly on SKLD-bench but is obviously bad on out-of-distribution queries. If such a skill is easy to write, the benchmark has holes. If it's hard, the benchmark is robust.

**Experiment shape.** Commission (or self-administer) an adversarial authoring exercise. Publish the resulting gap analysis, whether positive or negative for SKLD-bench.

---

## What success looks like for a given question

A question leaves this page when:

1. An experiment has been designed specifically enough to falsify it.
2. The experiment has run.
3. The result has been published — as a finding in the Bible if the result is general, as a note in the rigor arc (`03-rigor-arc.md`) if it caused a design change, as a closed entry here with a link to the evidence.

Questions that have been closed — findings #1 through #7 in `05-findings-summary.md` — all went through this path. Every question on this page is a candidate for the next pivot in the rigor arc.

---

*This is the honest list. If a reviewer's question isn't here and isn't already a closed finding, that's a gap worth telling us about.*
