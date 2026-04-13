# PLAN-V2.1.2 — Scoring System Overhaul & Pipeline Observability

## Context

Session 919831b9 (April 12, 2026) shipped all 7 SKLD-bench seed runs and ran the first full Sonnet baseline across 874 challenges. The results exposed fundamental problems:

1. **The scorers don't test if code works.** Every score across all 874 challenges and 7 seed runs is purely string matching (`must_contain`). No compilation, no execution, no behavioral testing.
2. **Raw Sonnet scores 93.3% baseline.** The scorers are too easy — skills can't demonstrate meaningful lift over a model that already aces the tests.
3. **Agent outputs are lost.** Competitor code, spawner variants, engineer composites — all written to temp dirs and deleted. No audit trail, no reproducibility.
4. **The composite fitness formula doesn't exist.** Winner selection uses a single L0 string-match score. No graduated quality assessment.

This plan addresses all four. It covers the scoring overhaul, pipeline observability, the graduated fitness formula, and the path to integrating these into the production engine.

## What We Learned (Mock Testing Playbook)

### The Deep-Dive Experiment

We took the 3 hardest Phoenix LiveView challenges (hard-07, medium-12, hard-06) and generated outputs from 6 sources:

| Source | Description |
|--------|-------------|
| Sonnet raw | Sonnet 4.6, no skill guidance |
| Opus raw | Opus 4.6, no skill guidance |
| Sonnet + v1 | Sonnet 4.6 with seed variant SKILL.md |
| Sonnet + v2 | Sonnet 4.6 with spawn variant SKILL.md |
| Opus + v1 | Opus 4.6 with seed variant SKILL.md |
| Opus + v2 | Opus 4.6 with spawn variant SKILL.md |

Then scored each output through 4 levels:

| Level | What it checks | Discriminating? |
|-------|---------------|----------------|
| L0: String match | `must_contain` patterns | Poor — 5/6 sources scored identically (0.636) |
| L2: Compilation | `mix compile` in Phoenix project | Caught 1 real bug that L0 missed |
| #1: AST quality | Functions, pipes, @impl, LOC | Good — 121 LOC vs 44 LOC differentiates verbosity |
| #2+4: Behavioral | ExUnit tests — does it run? | Excellent — 0/12 to 12/12 spread |
| #3: Template quality | Modern HEEx patterns | Moderate — 0.78 to 0.90 spread |

### Key Findings

1. **L0 string matching is nearly useless for ranking.** 5 of 6 sources scored identically. It can't distinguish working code from broken code.
2. **Behavioral tests are the primary differentiator.** The test pass rate (0/12 to 12/12) provides the clearest quality signal.
3. **Compilation is a cheap, high-value gate.** Caught exactly 1 bug (Opus+v1's invalid `&` capture) that L0 ranked as the best solution.
4. **Raw Opus beats Sonnet+skill.** On the hardest challenges, Opus without any skill (0.913 composite) beats Sonnet with a skill (0.645-0.681). Skills equalize Sonnet to Opus level but don't surpass it.
5. **Skills can hurt.** Opus+v1 was the only compile failure — the skill guided it toward a broken pattern. A skill that teaches the wrong thing is worse than no skill.
6. **The scorer has systemic bugs.** Pipe-operator hides first args (`stream(socket, :posts` doesn't match `|> stream(:posts`). Literal requirements reject variables (`limit: -50` doesn't match `limit: -@page_size`).

### Composite Fitness Formula

```
composite = (
    L0_string_match * 0.10 +
    compilation      * 0.15 +
    ast_quality      * 0.15 +
    behavioral_tests * 0.40 +
    template_quality * 0.10 +
    brevity          * 0.10
)
```

Where:
- `L0_string_match`: Current score.py output (0.0-1.0)
- `compilation`: Binary 1.0 (compiles) or 0.0 (doesn't)
- `ast_quality`: `impl_coverage * 0.5 + pipe_density * 0.5` (0.0-1.0)
- `behavioral_tests`: `tests_passed / tests_total` (0.0-1.0)
- `template_quality`: `modern_patterns / (modern + legacy)` (0.0-1.0)
- `brevity`: `max(0, 1.0 - (loc - 40) / 100)` (0.0-1.0, penalizes >140 LOC)

Validation results from the deep-dive:
```
#1  0.913  Opus raw        — 12/12 tests, concise, self-contained
#2  0.721  Opus+v2 skill   — 7/12 tests, best templates, missing fn
#3  0.681  Sonnet+v2 skill — 5/12 tests, skill helped but ext deps
#4  0.645  Sonnet+v1 skill — 5/12 tests, missing @impl
#5  0.413  Sonnet raw      — 0/12 tests, 121 LOC, verbose
#6  0.368  Opus+v1 skill   — compile failure, zeroed
```

L0 alone ranked 5 of these identically at 0.636. The composite produces a clear, defensible ranking.

---

## Phase 1: Scorer Overhaul

### 1.1 Fix String Matching Bugs (all 7 scorers)

The shared scoring engine (`must_contain` checks) has systemic issues:

**Bug 1: Pipe-operator blind spot**
- Current: checks for `stream(socket, :posts`
- Fails on: `socket |> stream(:posts, ...)`
- Fix: When checking `fn(arg1, arg2`, also match `|> fn(arg2` (strip first arg when pipe is upstream)

**Bug 2: Variable-vs-literal rejection**
- Current: checks for `limit: -50`
- Fails on: `limit: -@page_size` where `@page_size` is 50
- Fix: For numeric literals in `must_contain`, also accept module attributes and variables that could hold that value

**Bug 3: Cross-cutting score inflation**
- Current: 7+ "cross-cutting" checks (live_link, Routes.*_path, etc.) pass for every solution, adding ~7 free points
- Fix: Downweight cross-cutting checks to 0.25x or remove them. They measure "is this a LiveView?" not "is this a good solution."

### 1.2 Add Compilation Gate

For every challenge evaluation, after extracting output files:

1. Copy files into a pre-built Mix project scaffold (per family)
2. Run `mix compile --force` 
3. If compilation fails: cap L0 score at 0.3, add `compile_error` to diagnostics
4. If compilation passes: no bonus (it's the minimum bar)

**Infrastructure needed:**
- One Mix project scaffold per family (e.g., Phoenix project for LiveView, bare Mix for Ecto)
- Module namespace adapter: `MyApp` → `SkldBench` (sed-based, same as our prototype)
- Scaffold bootstrapped once, compiled deps cached, only user code recompiles (~2s per check)

### 1.3 Add AST Quality Metrics

Using the `ast_quality.exs` analyzer from the prototype:

| Metric | What it measures | Score formula |
|--------|-----------------|---------------|
| `impl_coverage` | `@impl true` on OTP callbacks | annotations / public functions |
| `pipe_density` | Idiomatic pipe usage | pipe_chains / LOC * 10, capped at 1.0 |
| `pattern_match_ratio` | Multi-clause dispatch | pattern_heads / total functions |
| `module_attributes` | Named constants vs magic numbers | count of @attr declarations |
| `brevity` | Conciseness | 1.0 - (loc - optimal) / 100 |

### 1.4 Add Template Quality Metrics (LiveView/HEEx families)

| Metric | Modern (good) | Legacy (bad) |
|--------|--------------|-------------|
| Expression syntax | `{expr}` | `<%= expr %>` |
| Conditional | `:if={cond}` | `<%= if cond do %>` |
| Comprehension | `:for={item <- list}` | `<%= for item <- list do %>` |

Score: `modern_count / (modern_count + legacy_count)`

### 1.5 Add Behavioral Test Harness

For each challenge, write ExUnit tests that verify:
- **Core behavior**: Does mount work? Do events trigger correct state changes?
- **Edge cases**: Empty data, nil values, rapid events, boundary conditions
- **Anti-patterns**: Does the solution avoid the specific bad pattern the challenge describes?

**Scale challenge**: Writing ExUnit tests for all 874 challenges is substantial. Phased approach:
- Phase 1: Write tests for the 50 hardest challenges (bottom 50 by Sonnet baseline score)
- Phase 2: Generate test templates via LLM for the remaining 824
- Phase 3: Human review + fix generated tests

---

## Phase 2: Pipeline Observability

### 2.1 Problem Statement

Currently, agent dispatches produce output that's:
- Written to `/tmp` dirs and deleted after scoring
- Logged in `.claude/projects/.../subagents/` JSONL but not linked to runs
- Not queryable — you can't ask "what code did Sonnet produce for challenge X?"

The production system needs a complete, queryable audit trail for every dispatch.

### 2.2 New DB Table: `dispatch_transcripts`

```sql
CREATE TABLE IF NOT EXISTS dispatch_transcripts (
    id              TEXT PRIMARY KEY,
    run_id          TEXT,                    -- FK → evolution_runs, NULL for benchmarks
    benchmark_id    TEXT,                    -- FK → benchmark_results, NULL for evolution
    family_slug     TEXT NOT NULL,
    challenge_id    TEXT NOT NULL,
    dispatch_type   TEXT NOT NULL,           -- 'competitor' | 'spawner' | 'engineer' | 'benchmark'
    model           TEXT NOT NULL,           -- 'claude-sonnet-4-6' | 'claude-opus-4-6'
    skill_variant   TEXT,                    -- variant SKILL.md name, NULL for no-skill
    prompt          TEXT NOT NULL,           -- full prompt sent to the model
    raw_response    TEXT NOT NULL,           -- complete model response text
    extracted_files TEXT NOT NULL,           -- JSON dict {path: content}
    scores          TEXT NOT NULL,           -- JSON: {l0: ..., compile: ..., ast: ..., behavioral: ..., composite: ...}
    total_tokens    INTEGER NOT NULL,
    duration_ms     INTEGER NOT NULL,
    error           TEXT,
    created_at      TEXT NOT NULL
);
```

### 2.3 What Gets Stored

For EVERY dispatch in the pipeline:

| Field | Content |
|-------|---------|
| `prompt` | The exact text sent to the model — challenge prompt + skill content + fixture files |
| `raw_response` | The complete model response, unparsed |
| `extracted_files` | The code files extracted from the response |
| `scores` | Multi-level score breakdown: `{l0: 0.636, compile: true, ast: {impl: 1.0, pipes: 0.67, ...}, behavioral: {passed: 12, total: 12, details: [...]}, template: 0.90, composite: 0.913}` |

### 2.4 Integration Points

**Seed run pipeline** (scripts/mock_pipeline/):
- `persist_variant.py` → also saves dispatch transcript
- Competitor dispatches → save raw response + extracted code + all score levels

**Benchmark pipeline** (scripts/benchmark/):
- `run_benchmark.py` → save full transcript per challenge
- Currently stores `output_files` in `benchmark_results` — extend to include `scores` breakdown

**Future engine** (skillforge/engine/):
- Every `Agent` SDK call wraps in a transcript logger
- Transcript ID linked to the run + variant_evolution + challenge

---

## Phase 3: SKLD-bench Test Suite

### 3.1 Current State (867 Sonnet results)

Sonnet baseline ran against 867/874 challenges. Results by family:

| Family | Challenges | Avg L0 | Pass Rate |
|--------|-----------|--------|-----------|
| ecto-schema-changeset | 100 | 0.990 | 100% |
| ecto-query-writer | 151 | 0.980 | 100% |
| ecto-sandbox-test | 151 | 0.958 | 100% |
| pattern-match-refactor | 130 | 0.920 | 100% |
| oban-worker | 100 | 0.915 | 100% |
| security-linter | 100 | 0.912 | 100% |
| phoenix-liveview | 135 | 0.855 | 88% |

**Caveat**: Several benchmark agents iterated by reading scorer code and fixing outputs. These scores are upper bounds, not blind baselines. True first-pass scores would be lower.

### 3.2 Opus Baseline (pending)

Run Opus 4.6 against all 874 challenges for model comparison. Estimated cost: ~$175 (API) or ~2-3 hours (subscription).

### 3.3 Re-score with Graduated Metrics

After the scorer overhaul (Phase 1), re-run all 867 Sonnet outputs through the upgraded scorer:
1. Compilation check against per-family Mix scaffolds
2. AST quality analysis
3. Template quality (LiveView/HEEx families only)
4. Behavioral tests (for the challenges that have them)
5. New composite fitness score

This produces a corrected baseline that's directly comparable to future skill-guided runs.

### 3.4 Stored Outputs Available for Re-scoring

The `benchmark_results` table has `output_files` (JSON dict of extracted code) for all 867 Sonnet results. These can be re-scored without re-dispatching — just pipe the stored code through the upgraded scorer.

Additionally, we have 18 outputs from the deep-dive experiment stored at `/tmp/skld-level-test/`:
- 6 sources × 3 challenges
- Full code content preserved
- Already scored through all 4 levels

---

## Phase 4: Composite Fitness Score Integration

### 4.1 Score Formula

```python
def composite_fitness(l0, compiles, ast_metrics, test_results, template_metrics, loc):
    """
    Compute a single 0.0-1.0 fitness score from multi-level evaluation.
    
    Weights:
      behavioral_tests: 0.40  — does the code work?
      compilation:      0.15  — does it compile?
      ast_quality:      0.15  — is it well-structured?
      l0_string_match:  0.10  — does it contain expected patterns?
      template_quality: 0.10  — modern HEEx?
      brevity:          0.10  — concise?
    """
    # Compilation: binary gate
    compile_score = 1.0 if compiles else 0.0
    
    # AST quality: impl coverage + pipe density
    impl_cov = min(ast_metrics["impl_annotations"] / max(ast_metrics["functions"], 1), 1.0)
    pipe_dens = min(ast_metrics["pipe_chains"] / max(ast_metrics["non_empty_lines"], 1) * 10, 1.0)
    ast_score = impl_cov * 0.5 + pipe_dens * 0.5
    
    # Behavioral: test pass rate
    test_score = test_results["passed"] / max(test_results["total"], 1)
    
    # Template: modern pattern ratio
    modern = template_metrics.get("heex_modern", 0)
    legacy = template_metrics.get("heex_legacy", 0)
    template_score = modern / max(modern + legacy, 1)
    
    # Brevity: penalize verbose code
    brevity = max(0.0, min(1.0, 1.0 - (loc - 40) / 100.0))
    
    return (
        l0 * 0.10 +
        compile_score * 0.15 +
        ast_score * 0.15 +
        test_score * 0.40 +
        template_score * 0.10 +
        brevity * 0.10
    )
```

### 4.2 Where the Score Lives

- **`benchmark_results.scores`** — JSON column with full breakdown: `{l0, compile, ast, behavioral, template, brevity, composite}`
- **`competition_results`** — extended with `composite_fitness` column for seed run competition data
- **`variants.fitness_score`** — uses the composite instead of L0

### 4.3 Winner Selection

Current: winner = variant with higher L0 mean across challenges.
New: winner = variant with higher **composite** mean across challenges.

The composite naturally handles cases where:
- High L0 but doesn't compile → penalized (0.15 weight on compilation)
- Compiles but doesn't work → penalized (0.40 weight on behavioral tests)
- Works but verbose/unidiomatic → penalized (0.15 AST + 0.10 brevity)

---

## Phase 5: Production Integration

### 5.1 Per-Family Mix Scaffolds

Each family needs a pre-built Mix project for compilation testing:

| Family | Project Type | Key Dependencies |
|--------|-------------|-----------------|
| phoenix-liveview | `mix phx.new` | Phoenix, LiveView, PubSub |
| ecto-schema-changeset | `mix new --sup` | Ecto |
| ecto-query-writer | `mix new --sup` | Ecto |
| ecto-sandbox-test | `mix phx.new` | Phoenix, Ecto, ExUnit |
| security-linter | `mix phx.new` | Phoenix, Plug |
| oban-worker | `mix new --sup` | Oban |
| pattern-match-refactor | `mix new` | (none) |

Scaffolds stored at `taxonomy/elixir/<family>/scaffold/` — gitignored `_build` and `deps`, but `mix.exs` and `config/` committed. `mix deps.get && mix compile` on first use, cached thereafter.

### 5.2 ExUnit Test Generation Strategy

For each challenge:
1. **Core test**: Does `mount/3` work? Do expected events trigger correct responses?
2. **Pattern test**: Does the output match the structural pattern the challenge requires?
3. **Anti-pattern test**: Does the output avoid the bad pattern the fixture demonstrates?
4. **Edge case tests**: Empty data, nil inputs, rapid events, boundary conditions

Storage: `taxonomy/elixir/<family>/tests/<challenge_id>_test.exs`

### 5.3 Scorer Architecture

```
score.py (entry point)
├── L0: string_match(must_contain, must_not_contain)  → 0.0-1.0
├── L1: ast_parse(code)                               → pass/fail
├── L2: compile(code, scaffold_path)                   → pass/fail + warnings
├── AST: ast_quality(code)                             → {impl, pipes, loc, ...}
├── L3: template_quality(code)                         → {modern, legacy, score}
├── L4: behavioral_test(code, test_path, scaffold)     → {passed, total, details}
└── composite(all_above)                               → 0.0-1.0
```

Single entry point, returns a comprehensive JSON result:
```json
{
  "challenge_id": "elixir-phoenix-liveview-hard-07",
  "l0": {"score": 0.636, "objectives": {...}},
  "compile": {"passed": true, "warnings": 1, "errors": 0},
  "ast": {"functions": 4, "impl_coverage": 1.0, "pipe_density": 0.67, "loc": 44},
  "template": {"modern": 7, "legacy": 2, "score": 0.78},
  "behavioral": {"passed": 12, "total": 12, "failures": []},
  "composite": 0.913
}
```

---

## Execution Order

### Sprint 1: Scorer Fixes (foundation, unblocks everything)
1. Fix pipe-operator blind spot in all 7 `score.py` files
2. Fix variable-vs-literal rejection
3. Downweight cross-cutting checks
4. Re-score existing 867 Sonnet benchmark results (no re-dispatch needed)
5. Compare corrected scores vs original — validate the fixes don't break things

### Sprint 2: Compilation Gate
1. Create Mix project scaffolds for all 7 families
2. Build `compile_check.py` utility (takes code + scaffold → pass/fail)
3. Wire into `score.py` as L2
4. Re-score 867 Sonnet outputs with compilation check
5. Identify how many "passing" solutions don't actually compile

### Sprint 3: AST + Template Quality
1. Port `ast_quality.exs` to Python (or keep as Elixir subprocess)
2. Wire into `score.py` as graduated metrics
3. Add template quality checks for HEEx-producing families
4. Re-score 867 Sonnet outputs with graduated metrics

### Sprint 4: Behavioral Tests (long pole)
1. Write ExUnit tests for 50 hardest challenges (bottom 50 by corrected L0)
2. Build test runner: copies code to scaffold, runs `mix test`, parses results
3. Wire into `score.py` as L4
4. Score the 50 challenges with behavioral tests
5. Evaluate: does the test pass rate differentiate solutions?

### Sprint 5: Pipeline Observability
1. Add `dispatch_transcripts` table to `database.py`
2. Update `SCHEMA.md`
3. Wire transcript storage into `run_benchmark.py`
4. Wire transcript storage into `persist_variant.py` and competitor dispatch flow
5. Verify: can we reconstruct a complete run from transcript records alone?

### Sprint 6: Composite Score & Winner Selection
1. Implement `composite_fitness()` function
2. Replace L0-only winner selection in `persist_variant.py`
3. Update `benchmark_results` schema to store full score breakdown
4. Re-run seed run #1 (phoenix-liveview) with composite scoring as validation
5. Compare old winners vs new winners — did the better scorer pick different variants?

### Sprint 7: Opus Baseline & Comparison
1. Run Opus 4.6 against all 874 challenges (with upgraded scorer)
2. Generate comparative report: Sonnet vs Opus × old scorer vs new scorer
3. Identify challenges where the new scorer changes the ranking
4. Publish SKLD-bench baseline report

---

## Open Questions

1. **Weight tuning**: The 0.40 weight on behavioral tests came from the deep-dive. Should it be validated across more challenges?
2. **Test generation at scale**: Writing ExUnit tests for 874 challenges is significant. Can we generate them via LLM and human-review a sample?
3. **Non-LiveView families**: Template quality only applies to phoenix-liveview. What replaces it for ecto/oban/security families?
4. **Scorer gaming**: If the benchmark agents read the ExUnit tests, they could game those too. How do we prevent that for blind baselines?
5. **Cost of behavioral testing**: Running `mix test` for 874 challenges × 2 models adds ~30 minutes of compile time. Acceptable?

---

## Artifacts from This Session

### Stored Outputs (re-scorable without re-dispatch)
- **867 Sonnet baseline outputs**: `benchmark_results` table, `output_files` column
- **18 deep-dive outputs**: `/tmp/skld-level-test/{source}-{challenge}/` (6 sources × 3 challenges)
- **7 seed run JSON files**: `skillforge/seeds/seed_runs/*.json` (contain all genomes with SKILL.md content)

### Prototype Code (working, needs productionization)
- **AST analyzer**: `/tmp/scoring_test/ast_quality.exs` — Elixir script, counts functions/pipes/patterns
- **Graduated ExUnit tests**: `/tmp/scoring_test/test/scoring_test_web/live/graduated_scoring_test.exs`
- **Phoenix test scaffold**: `/tmp/scoring_test/` — full Phoenix project with LiveView routes
- **Benchmark runner**: `scripts/benchmark/run_benchmark.py` — dispatches + scores + stores
- **Benchmark reporter**: `scripts/benchmark/benchmark_report.py` — generates statistics

### Data Points
- Composite fitness formula validated against 6 sources × 3 challenges = 18 data points
- 5 of 6 sources scored identically (0.636) by L0; composite produced a spread of 0.368-0.913
- Compilation gate caught 1/18 real bug that string matching ranked as best
- Behavioral tests provided the dominant differentiator (0-100% spread)
