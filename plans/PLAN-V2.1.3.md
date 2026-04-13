# PLAN-V2.1.3: Scoring Overhaul, Data Capture & Challenge Classification

## Context

All 7 SKLD-bench seed runs shipped (867 challenges, $63 API cost), but the Sonnet baseline benchmark exposed three foundational problems:

1. **Scoring is string-matching only** — raw Sonnet scores 93.3% with no skill. 5/6 sources scored identically (0.636) on the hardest challenge. Scores don't discriminate.
2. **Data gets lost** — competitor outputs, scorer details, and deep-dive analysis land in `/tmp` and disappear. The richest experiment of the project (18 outputs × 4 scoring levels) exists only as prose in journal #14.
3. **Challenge quality is unknown** — we can't tell if challenges are too easy or if the scorer is too lenient until scoring actually works.

**Short-term goal**: Sonnet + Skills convincingly outperforms Sonnet raw.  
**Long-term goal**: Sonnet + Skills approaches or beats Opus raw.  
**Data rule**: Every mock output persists to DB from day one — nothing to `/tmp` without a permanent copy.

### What we have
- Elixir 1.19.5 + mix installed (mise)
- `/tmp/skld-level-test/` — 18 deep-dive outputs (6 sources × 3 challenges), still alive
- `/tmp/scoring_test/` — Phoenix scaffold + `ast_quality.exs` (74 lines) + graduated ExUnit tests (140 lines)
- `benchmark_results` table: 867 rows with `output_files` JSON — re-scorable without re-dispatch
- 7 family-specific `score.py` files (all string-matching)
- `dispatch_transcripts` table does NOT exist yet
- `competition_results` table exists in schema but has 0 rows

---

## Phase 0: Data Foundation

**Why first**: Every subsequent phase produces data. Without persistence, we lose it again.

### Build

1. **`dispatch_transcripts` table** — add to `skillforge/db/database.py`
   - Schema: `id, run_id, benchmark_id, family_slug, challenge_id, dispatch_type, model, skill_variant, prompt, raw_response, extracted_files, scores, total_tokens, duration_ms, error, created_at`
   - Follow `CREATE TABLE IF NOT EXISTS` pattern
   - Add `save_transcript()` query in `skillforge/db/queries.py`

2. **`scores` TEXT column on `benchmark_results`** — via `_ADDITIVE_COLUMN_MIGRATIONS`
   - Stores multi-level breakdown JSON: `{l0, compile, ast, behavioral, template, composite}`
   - Existing scalar `score` column stays (backward compat); `scores.composite` is the new truth

3. **Archive `/tmp/skld-level-test/`** — one-time script copies 18 deep-dive outputs into `dispatch_transcripts` rows with `dispatch_type='deep_dive'` and proper source labels

4. **Archive `/tmp/scoring_test/ast_quality.exs`** — copy to `scripts/scoring/ast_quality.exs` (permanent home)

5. **Update `SCHEMA.md`**

### Verify
- `SELECT COUNT(*) FROM dispatch_transcripts` = 18
- Each row has non-empty `extracted_files` matching on-disk content
- `init_db()` idempotent on fresh + existing DB
- 867 existing `benchmark_results` rows untouched

### Files touched
- `skillforge/db/database.py` — DDL + migration
- `skillforge/db/queries.py` — `save_transcript()`, `get_transcripts_for_challenge()`
- `scripts/scoring/archive_deep_dive.py` (new, one-time)
- `scripts/scoring/ast_quality.exs` (copied from /tmp)
- `SCHEMA.md`

---

## Phase 1: Compilation + AST Scorer (phoenix-liveview)

**Why**: Cheapest improvement that breaks the 93.3% floor. Zero per-challenge authoring. Compilation caught 1/18 bugs in the deep-dive that L0 ranked as "best solution."

### Build

1. **Phoenix LiveView Mix scaffold** at `taxonomy/elixir/elixir-phoenix-liveview/scaffold/`
   - `mix phx.new skld_bench --no-ecto --no-mailer --no-dashboard`
   - Commit `mix.exs` + `config/`, gitignore `_build/` + `deps/`
   - First use: `mix deps.get && mix compile` (~30s, cached thereafter)
   - Namespace adapter: candidate code's `MyApp` → `SkldBench` via sed

2. **`scripts/scoring/compile_check.py`** (new)
   - Input: `(code_content, scaffold_path)` → `{compiles: bool, warnings: int, errors: [str]}`
   - Copies code to scaffold `lib/`, runs `mix compile --force`, parses output
   - 30s timeout

3. **`scripts/scoring/ast_analyze.py`** (new)
   - Shells out to `elixir scripts/scoring/ast_quality.exs <file>`, parses JSON
   - Returns: `{functions, impl_coverage, pipe_density, loc, heex_modern, heex_legacy}`

4. **Fix 3 string-matching bugs** in `elixir-phoenix-liveview/evaluation/score.py`
   - Pipe-operator blind spot: `stream(socket, :posts` → also match `|> stream(:posts`
   - Variable-vs-literal: `limit: -50` → also accept `limit: -@page_size`
   - Cross-cutting inflation: downweight 7+ free checks from 2.5 to 0.5

5. **`scripts/scoring/composite_scorer.py`** (new) — orchestrates all levels
   - Input: `(family_slug, challenge_path, output_dir)`
   - Runs: L0 score.py → compile_check → ast_analyze → composite formula
   - Phase 1 weights (no behavioral): `l0*0.25 + compile*0.30 + ast*0.25 + brevity*0.20`
   - Output: full breakdown JSON → updates `benchmark_results.scores`

6. **Re-score 18 deep-dive outputs** → update `dispatch_transcripts.scores`

7. **Re-score 135 phoenix-liveview benchmark outputs** → update `benchmark_results.scores`

### Verify
- Hard-07 spread: ≥ 0.4 across the 6 sources (vs 0.0 with L0)
- Opus raw ranks #1 or #2; Opus+v1 (compile failure) ranks last
- Phoenix-liveview Sonnet baseline average drops below 0.85 (from 0.855 L0)
- At least 5 of 135 outputs fail compilation

### Files touched
- `taxonomy/elixir/elixir-phoenix-liveview/scaffold/` (new dir)
- `taxonomy/elixir/elixir-phoenix-liveview/evaluation/score.py` (bug fixes)
- `scripts/scoring/compile_check.py` (new)
- `scripts/scoring/ast_analyze.py` (new)
- `scripts/scoring/composite_scorer.py` (new)

---

## Phase 2: Behavioral Tests (phoenix-liveview, phased)

**Why**: Deep-dive proved behavioral tests are the dominant differentiator (0/12 to 12/12 spread). This is the long pole — hand-write tests for the hardest challenges first, then LLM-generate the rest.

### Build

1. **Hand-write ExUnit tests for 20 hardest phoenix-liveview challenges**
   - Bottom 16 by Sonnet L0 score + 4 from the 0.70-0.75 range
   - Storage: `taxonomy/elixir/elixir-phoenix-liveview/tests/<challenge_id>_test.exs`
   - Port the 3 existing prototype tests from `/tmp/scoring_test/test/`
   - Each test covers: mount works, events trigger state changes, edge cases don't crash

2. **`scripts/scoring/behavioral_test_runner.py`** (new)
   - Copies candidate code → scaffold `lib/`, test file → scaffold `test/`
   - Runs `mix test <file> --formatter json` (or parses ExUnit output)
   - Returns: `{passed: int, total: int, failures: [{test, error}]}`
   - 30s timeout per test file

3. **LLM-generate tests for remaining ~115 phoenix-liveview challenges**
   - Use 20 hand-written tests as few-shot examples
   - Feed challenge JSON + expected outputs to Claude
   - Save generation prompts + outputs to `dispatch_transcripts` (audit trail)
   - Spot-check 20/115 by running against stored Sonnet outputs

4. **Update composite formula** with behavioral weight:
   - `l0*0.10 + compile*0.15 + ast*0.15 + behavioral*0.40 + template*0.10 + brevity*0.10`
   - Template quality: `heex_modern / (heex_modern + heex_legacy)` from AST analyzer

5. **Re-score 135 phoenix-liveview outputs** with full composite

### Verify
- Sonnet + Skill beats Sonnet raw on ≥60% of the 20 hand-tested challenges
- Score standard deviation > 0.15 across the 20 (vs ~0.0 with L0)
- ≥3 challenges where L0 scored > 0.90 now show composite < 0.70
- 18 deep-dive outputs match the manual rankings from the experiment

### Files touched
- `taxonomy/elixir/elixir-phoenix-liveview/tests/` (new dir, ~135 test files)
- `scripts/scoring/behavioral_test_runner.py` (new)
- `scripts/scoring/composite_scorer.py` (weight update)

---

## Phase 3: Challenge Classification & Cross-Family Generalization

**Why**: Before writing new challenges or investing in behavioral tests for other families, classify the 867 existing challenges. Also: build scaffolds for the remaining 6 families.

### Build

1. **Mix scaffolds for remaining 6 families**
   - ecto-schema-changeset, ecto-query-writer: `mix new --sup` + ecto
   - ecto-sandbox-test: `mix phx.new` + ecto
   - oban-worker: `mix new --sup` + oban
   - security-linter: `mix phx.new`
   - pattern-match-refactor: `mix new` (no deps)
   - All at `taxonomy/elixir/<family>/scaffold/`

2. **Run compile + AST checks on all 867 outputs** (no behavioral — just Phase 1 scorer)
   - Re-score using each family's scaffold
   - Update all `benchmark_results.scores`

3. **`scripts/analysis/classify_challenges.py`** (new)
   - Per challenge, compute:
     - **Headroom**: `1.0 - sonnet_composite_score`
     - **Compile gate hit**: does any output fail compilation?
     - **AST spread**: std dev of AST quality across sources
   - Classify: `discriminating` (headroom > 0.15), `calibration` (0.05-0.15), `noise` (< 0.05), `broken` (scorer crashes)
   - Store classification in `benchmark_results.scores` or new `challenge_classifications` table

4. **Calibrate AST metrics per family**
   - Phoenix-liveview: template_modernity, heex patterns
   - Ecto families: changeset coverage, query composition complexity
   - Pattern-match-refactor: multi-clause density, guard clause ratio
   - Oban: worker callback coverage, queue config patterns

### Verify
- ≥100 challenges classified as "noise" (Sonnet aces trivially)
- ≥50 challenges classified as "discriminating" (real headroom)
- All 7 families have working compile checks with ≥2% failure rate
- No scorer crashes on any of the 867 outputs

### Decision gate
After this phase, evaluate which scenario we're in:
- **Scenario A** (baseline drops to ~60-70%): Challenges are hard enough. Skip to Phase 4.
- **Scenario B** (baseline drops to ~80%): Need harder challenges for top tier. Author legendary+ for the weakest families before Phase 4.
- **Scenario C** (baseline stays 85%+): Challenges are genuinely too easy. Major challenge authoring sprint needed.

---

## Phase 4: Skill-Guided Benchmark

**Why**: Measure whether skills actually help with the corrected scorer. This validates the short-term goal: Sonnet + Skills > Sonnet raw.

### Build

1. **`scripts/benchmark/run_skill_benchmark.py`** (new)
   - Loads SKILL.md from seed run composite
   - Dispatches Sonnet + skill against top 20 discriminating challenges per family
   - 7 families × 20 challenges = 140 dispatches
   - Saves ALL outputs to `dispatch_transcripts` + `benchmark_results`
   - Model tag: `claude-sonnet-4-6+seed-v1`

2. **`scripts/benchmark/comparative_report.py`** (extend existing)
   - Per-family: skill-guided composite vs raw composite delta
   - Per-challenge: which improved, which got worse
   - Aggregate: mean skill lift across discriminating challenges

3. **Update `persist_variant.py`**
   - Accept composite score dict (not just scalar)
   - Write `competition_results` rows with full breakdown
   - Write `dispatch_transcripts` for every competitor output

### Verify
- **Short-term goal gate**: Sonnet+Skill > Sonnet raw on ≥65% of discriminating challenges for ≥5/7 families
- Mean skill lift positive across all 7 families
- No family shows skill-guided performance worse than raw on average
- All 140 outputs persisted: `SELECT COUNT(*) FROM dispatch_transcripts WHERE dispatch_type='benchmark' AND skill_variant IS NOT NULL` = 140

---

## Phase 5: Full Scored Mock Run (End-to-End)

**Why**: Prove the complete loop works with real scoring and full data capture before productionizing.

### Build

1. **Run a complete seed pipeline for phoenix-liveview** (or a fresh family)
   - 12 dimensions × 2 variants × 2 challenges = 48 dispatches
   - Every dispatch → `dispatch_transcripts`
   - Every score → `competition_results` with full composite breakdown
   - Winner selection uses composite mean (not L0)

2. **Update mock pipeline scripts**
   - `run_score.py` → call `composite_scorer.py` instead of bare `score.py`
   - `persist_variant.py` → store composite in `deterministic_scores`, write `competition_results`
   - `backfill_competition_scores.py` → use composite scores

3. **Validate completeness**
   - 48 `dispatch_transcripts` rows (zero empty scores)
   - 48 `competition_results` rows with populated `compiles` and `tests_pass`
   - Winner differs from L0-only winner on ≥2 of 12 dimensions
   - Install test passes on the composite

### Verify
- `SELECT COUNT(*) FROM dispatch_transcripts WHERE scores = '{}'` = 0
- Run renders correctly in web UI with all 7 tabs
- Downloaded zip passes Gold Standard Checklist
- Composite scorer picked different winners than L0 on at least 2 dimensions

---

## Phase 6: Production Engine Integration

**Why**: With the full mock validated, wire the composite scorer into `skillforge/engine/` so `POST /evolve` runs produce composite-scored, fully-persisted results automatically.

### Build

1. **`skillforge/engine/scorer.py`** — async composite scorer
2. **`skillforge/engine/transcript_logger.py`** — wraps Agent SDK calls, saves transcripts
3. **Update `skillforge/engine/variant_evolution.py`** — composite fitness for Pareto front, `competition_results` population, transcript logging
4. **Revise `plans/PLAN-V2.1.md`** — incorporate scoring architecture, remove assumptions about L0-only scoring
5. **Consolidate `PLAN-V2.1.2.md` into `PLAN-V2.1.md`** — single plan, not two competing ones

### Verify
- Real `POST /evolve` produces non-zero `competition_results` rows
- `dispatch_transcripts` populated for every competitor dispatch
- Composite fitness in `variants.fitness_score`
- No outputs written to `/tmp` without DB persistence

---

## Dependency Graph

```
Phase 0 (Data Foundation) ──────────────────────┐
    │                                            │
    ▼                                            │ parallel
Phase 1 (Compile + AST, phoenix-liveview) ◄──────┘
    │
    ├──────────────────────────┐
    ▼                          ▼
Phase 2 (Behavioral Tests)   Phase 3 (Classify + Cross-Family)
    │                          │
    └──────────┬───────────────┘
               ▼
Phase 4 (Skill-Guided Benchmark)
               │
               ▼
Phase 5 (Full Scored Mock Run)
               │
               ▼
Phase 6 (Production Engine)
```

Phases 0 and 1 can overlap (scaffold work while DB tables are built).  
Phases 2 and 3 can partially overlap (behavioral tests for phoenix-liveview while building other family scaffolds).  
Phase 4 requires both 2 and 3.  
Phase 6 is the V2.1 engine work, now informed by everything above.

---

## What this replaces

This plan **supersedes** `PLAN-V2.1.2.md` (scoring overhaul) and revises the prerequisites for `PLAN-V2.1.md` (production engine). The V2.1 engine plan's Phase 0 (DB migration, family loader, dispatcher) remains valid but should not start until Phase 5 here is complete — by then, the scoring architecture is proven and the data persistence patterns are battle-tested.

## Estimated effort

| Phase | Mock work | Verify | API cost |
|-------|-----------|--------|----------|
| 0 | ~2 hours | ~30 min | $0 |
| 1 | ~4 hours | ~1 hour | $0 (re-scoring stored outputs) |
| 2 | ~8 hours (hand-write 20 + LLM-generate 115) | ~2 hours | ~$5-10 (LLM generation) |
| 3 | ~4 hours | ~1 hour | $0 (re-scoring stored outputs) |
| 4 | ~3 hours | ~1 hour | ~$15-20 (140 Sonnet dispatches) |
| 5 | ~6 hours | ~2 hours | ~$30-40 (48 Opus dispatches) |
| 6 | ~8 hours | ~2 hours | ~$5 (live test) |
