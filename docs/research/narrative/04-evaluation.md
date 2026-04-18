# Evaluation

Every fitness number in SKLD comes from a specific, auditable pipeline. This page documents that pipeline: the benchmark (**SKLD-bench**), the scoring layers (L0 through L5 with a composite formula), the train / held-out split, and the things the evaluation stack still cannot measure.

`03-rigor-arc.md` explains *why* the evaluation looks like this; this page is the current spec.

## SKLD-bench

SKLD-bench is a fixed, versioned benchmark that lives on disk in `taxonomy/elixir/<family-slug>/`. It currently covers seven Elixir lighthouse families:

| Family | Challenges | Status |
|---|---|---|
| `elixir-phoenix-liveview` | 135 | seed run shipped, fitness 0.9407 |
| `elixir-ecto-sandbox-test` | 151 | seed run shipped, fitness 0.8939 |
| `elixir-security-linter` | 100 | seed run shipped |
| `elixir-oban-worker` | 100 | seed run shipped |
| `elixir-ecto-schema-changeset` | 100 | seed run shipped, fitness 0.987 |
| `elixir-ecto-query-writer` | 151 | seed run shipped, fitness 0.935 |
| `elixir-pattern-match-refactor` | 130 | seed run shipped, fitness 0.945 |
| **Total** | **867** | |

Each family directory contains:

```
taxonomy/elixir/<family-slug>/
├── family.json           metadata + taxonomy + slug
├── seed.json             Gen 0 SkillGenome (the seed)
├── test_fixtures/        immutable input files
├── challenges/           versioned challenge pool
│   ├── easy/
│   ├── medium/
│   ├── hard/
│   └── legendary/
├── goldens/              known-good reference outputs
├── evaluation/
│   ├── score.py          family-specific scorer
│   ├── criteria.json     per-capability weights (sum to 1.0)
│   ├── environment.yml   scorer deps (python, elixir, mix, regex)
│   └── _calibration.json tier rationales
└── scaffold/             per-family Mix project for compilation gates
```

The schemas are documented in `taxonomy/elixir/SCHEMAS.md`. Each family's `score.py` implements the per-family rubric over the six composite layers described below.

## Difficulty tiers

Every challenge is tagged `easy`, `medium`, `hard`, or `legendary`. Tiers were assigned heuristically during drafting (single-step vs multi-step, ambiguity, prior knowledge required, known Claude failure modes) and each challenge carries a `tier_rationale` field. Empirical recalibration against multi-model baseline pass rates is future work — see `06-open-questions.md`.

## Train / held-out split

- Each generation of an evolution run samples **3-5 challenges from a training pool**. Variants can't memorize specific held-out challenges.
- After evolution finishes, the champion is evaluated against a **held-out subset (~20% of each pool)** that no skill saw during evolution.
- **The held-out score is the headline number.** A training-set score is reported but clearly labeled.

This prevents the implicit train-on-test problem that v2.0 had before SKLD-bench existed.

## The six scoring layers

Every challenge is scored through six layers. Each layer produces a bounded number; the composite is a weighted average.

### L0 — String match (10%)
Fast pattern matching against expected keywords. Catches absent concepts ("output does not mention `stream/4`"). Nearly useless on its own — raw Sonnet scored 93.3% on L0-only across all 867 challenges. Kept because it is a useful *necessary* check, not because it ranks well. Weight capped at 10% so it cannot dominate the composite.

### L1 — Compilation gate (15%)
Does the code compile? Each family ships a per-family Mix scaffold at `taxonomy/elixir/<family>/scaffold/`. The candidate's code is copied into the scaffold's `lib/` directory and `mix compile --force` runs with a 30-second timeout. Output is `{compiles: bool, warnings: int, errors: [str]}`.

Compilation is binary, cheap (~1 second cached), and catches a class of failures that no amount of string matching can detect. In the deep-dive experiment, 46% of outputs failed compilation despite most scoring above 0.70 on string matching. Eight outputs scored above 0.85 on L0 but did not compile — "ghost passes" that look perfect on paper.

### L2 — AST quality (15%)
Shells out to `scripts/scoring/ast_quality.exs`, which parses the candidate's code with Elixir's native AST and checks for idiomatic constructs (pattern matching over if-else chains, pipe operators, tagged-tuple returns, `with` expressions where appropriate, absence of defensive nil-checking). Per-family rubrics in `criteria.json` weight these factors differently.

AST quality catches *non-idiomatic* code that compiles and works — Ruby-style imperative Elixir that a post-mortem would flag. See `docs/research/audits/elixir-llm-pain-points.md` for the provenance of the idiom catalog.

### L3 — Behavioral tests (40% — **dominant signal**)
The candidate's module is loaded into a per-family test scaffold and exercised via ExUnit. For Phoenix LiveView: mount via `live_isolated`, invoke each defined event handler, assert responses. For Ecto: run against an in-memory SQLite or sandboxed Postgres, insert/query/update. For Oban: enqueue and drain, check side effects. Each family defines its own `behavioral_tests/` suite in the scaffold.

This is the only metric that separates code that *works* from code that *looks right*. Carries the largest single weight (40%) because the 18-output deep-dive experiment showed it was the only layer that distinguished Opus raw (4/4 tests passing) from Sonnet + v2 skill (0/4 tests) when both scored identically on L0.

A compilation failure short-circuits L3 to 0 — you can't behaviorally test code that doesn't compile.

### L4 — Template quality (10%)
For challenges that produce templated output (HEEx, SQL migrations, Oban worker stubs), this layer checks structural quality: HEEx parses and matches the expected shape, migrations are reversible, workers declare a `queue`. Complementary to L2 — AST checks function definitions, L4 checks the non-code artifacts.

### L5 — Brevity (10%)
Penalizes padding. Compared against the golden's line count; outputs that are more than 2× the golden or less than 0.5× get dinged. Brevity is a small component but catches a common LLM failure mode: verbose output that scores well on keyword matching because it hits all the keywords by saying everything twice.

### The composite

```python
composite = (
    0.10 * L0_string_match
  + 0.15 * L1_compile_gate   # 0 if compile fails
  + 0.15 * L2_ast_quality
  + 0.40 * L3_behavioral
  + 0.10 * L4_template_quality
  + 0.10 * L5_brevity
)
```

L1 acts as a gate for L3: if the code doesn't compile, L3 is 0 regardless. Every other layer scores independently.

## What the evaluation does not yet measure

- **Trigger accuracy (Anthropic skill-creator methodology).** We have the concept and the data model, but automated precision/recall for activation (should-trigger vs should-not-trigger query sets) is not yet running against SKLD-bench. See `01-prior-art.md` §Anthropic skill-creator.
- **Trace adherence.** We record execution traces via the Agent SDK but the Reviewer layer that reads traces and attributes fitness to specific instructions ("this instruction was ignored in 7 of 10 runs") is partially implemented.
- **Consistency across runs.** Every fitness number in SKLD-bench today is a single-run score. Claude output is non-deterministic; a production-grade evaluation would run each challenge N times and report mean + variance. Implementing this is gated on cost; at the current challenge volumes, a 3× repeat is an affordable next step.
- **Cross-language generalization.** Every family in SKLD-bench is Elixir. Whether an atomic variant evolved for `elixir-ecto-query-writer` transfers its traits to a hypothetical `python-sqlalchemy-query-writer` is an untested claim. See `06-open-questions.md`.

## Cost and runtime

Typical numbers as of the seed-run cohort:

- **Per-variant dispatch:** ~$0.05–$0.15 on Sonnet 4.6 + 15-turn cap.
- **Per-family seed run (v2 atomic):** ~$5–$12, depending on dimensions and challenge tier mix.
- **Full SKLD-bench baseline sweep (867 challenges × 1 model):** ~$20–$30.
- **Wall clock for a family seed run:** 30–90 minutes at 20-wide concurrency.

The seven shipped seed runs totaled $63.18 in API spend.

## What a reviewer should ask

- What is the variance across repeats of the same challenge?
- Does the held-out score differ meaningfully from the training score?
- Which layer produced the fitness lift — compilation, behavioral tests, or AST quality?
- Is the per-family `score.py` calibrated against its goldens? (Each ships with a self-validation that computes golden score, vulnerable-fixture score, and empty-output score. The three should spread from near-1.0 to near-0.0.)

Every one of these questions is answerable from the data SKLD already records. The answers live in the `benchmark_results` and `dispatch_transcripts` tables and are exposed via the `/api/bench/...` endpoints. If a reviewer's question isn't answerable from those tables, that's a gap worth knowing about.
