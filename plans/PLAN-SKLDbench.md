# PLAN — SKLD-bench Baseline Benchmark

## Goal

Run every challenge across all 7 Elixir SKLD-bench families against raw Claude (no skill guidance) to establish a baseline benchmark. This answers: "How good is Claude at these Elixir tasks without any evolved skill?" and calibrates difficulty tiers against real model performance.

## Why

1. **Skill lift measurement** — compare evolved skill scores against raw model baseline to quantify actual value added
2. **Difficulty calibration** — validate that "hard" challenges are actually hard; identify mislabeled tiers
3. **Model comparison** — Sonnet vs Opus capability gap across 874 Elixir challenges
4. **Scorer validation** — if raw Opus scores 0.0 on a well-formed challenge, the scorer may be broken
5. **Publishable artifact** — "SKLD-bench: Claude baseline on 874 Elixir challenges" is real benchmark data

## Scope

- **874 challenges** across 7 families (all tiers: easy, medium, hard, legendary)
- **2 models**: Sonnet 4.6 first (cheaper, validates pipeline), then Opus 4.6
- **No skill guidance** — raw model solves each challenge with only the challenge prompt + fixture files
- **Same scorer** — `score.py` per family, identical to seed run scoring
- **New DB table** — `benchmark_results` stores per-(challenge, model) scores

## Challenge Inventory

| Family | Easy | Medium | Hard | Legendary | Total |
|--------|------|--------|------|-----------|-------|
| elixir-phoenix-liveview | ~34 | ~45 | ~38 | ~14 | 136 |
| elixir-ecto-sandbox-test | ~38 | ~45 | ~45 | ~14 | 152 |
| elixir-security-linter | ~25 | ~30 | ~30 | ~16 | 101 |
| elixir-oban-worker | ~25 | ~30 | ~30 | ~16 | 101 |
| elixir-ecto-schema-changeset | ~25 | ~30 | ~30 | ~16 | 101 |
| elixir-ecto-query-writer | ~38 | ~45 | ~45 | ~14 | 152 |
| elixir-pattern-match-refactor | ~33 | ~40 | ~40 | ~18 | 131 |
| **Total** | | | | | **874** |

## Cost Estimate

Per-dispatch cost (challenge prompt + fixture files, ~15K tokens avg):
- Sonnet 4.6: ~$0.09/dispatch → 874 × $0.09 = **~$79**
- Opus 4.6: ~$0.20/dispatch → 874 × $0.20 = **~$175**
- **Total both models: ~$254**

Subscription dispatches (no API key needed): rate limit is the constraint, not cost.

## Execution Order

1. **Sonnet first** — cheaper, validates the pipeline end-to-end
2. **Evaluate Sonnet results** — check score distributions, identify scorer issues, validate tiers
3. **Opus second** — if Sonnet results look good, run Opus for comparison
4. **Batch by family** — process one family at a time (100-150 dispatches per batch)

## Architecture

### New DB Table: `benchmark_results`

```sql
CREATE TABLE IF NOT EXISTS benchmark_results (
    id TEXT PRIMARY KEY,
    family_slug TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    challenge_path TEXT NOT NULL,
    model TEXT NOT NULL,
    tier TEXT NOT NULL,
    dimension TEXT NOT NULL,
    score REAL NOT NULL,
    passed INTEGER NOT NULL,
    objectives TEXT NOT NULL,       -- JSON dict of per-objective results
    output_files TEXT NOT NULL,     -- JSON dict {path: content}
    total_tokens INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    error TEXT,                     -- NULL if successful, error message if failed
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_benchmark_challenge_model
    ON benchmark_results (challenge_id, model);
CREATE INDEX IF NOT EXISTS idx_benchmark_family
    ON benchmark_results (family_slug, model);
CREATE INDEX IF NOT EXISTS idx_benchmark_tier
    ON benchmark_results (tier, model);
```

Unique constraint on `(challenge_id, model)` — one result per challenge per model. Re-running overwrites.

### Runner Script: `scripts/benchmark/run_benchmark.py`

```
uv run python scripts/benchmark/run_benchmark.py \
  --family elixir-phoenix-liveview \
  --model claude-sonnet-4-6 \
  [--tier medium]              # optional: run only one tier
  [--limit 10]                 # optional: cap dispatches for testing
  [--dry-run]                  # list challenges without dispatching
```

For each challenge:
1. Read challenge JSON (prompt, expected_outputs, fixture_files)
2. Load fixture file contents from `taxonomy/elixir/<family>/test_fixtures/`
3. Build prompt: challenge prompt + inlined fixtures (no SKILL.md)
4. Dispatch via Agent SDK (`claude-sonnet-4-6` or `claude-opus-4-6`)
5. Parse output files from fenced code blocks
6. Write to temp dir, run `score.py --challenge <json> --output <dir>`
7. Save result to `benchmark_results` table
8. Clean up temp dir

### Report Script: `scripts/benchmark/benchmark_report.py`

```
uv run python scripts/benchmark/benchmark_report.py \
  [--family elixir-phoenix-liveview]  # optional: one family
  [--model claude-sonnet-4-6]         # optional: one model
  [--format json|markdown]
```

Outputs:
- Per-family summary: avg score, pass rate, by tier
- Per-tier breakdown: avg score, hardest/easiest challenges
- Per-dimension breakdown: which dimensions are strongest/weakest
- Model comparison (when both models have data): Opus vs Sonnet delta per family/tier
- Challenge difficulty ranking: hardest 20, easiest 20 across all families
- Scorer health check: any 0.0 scores on easy challenges? (probable scorer bugs)

### API Endpoint (future, not in this plan)

`GET /api/benchmark?family=<slug>&model=<model>` — returns aggregated benchmark data for the Registry UI. Deferred until we have data and know what visualizations make sense.

## Execution Plan

### Phase 1: Infrastructure (~1 hour)
1. Add `benchmark_results` table to `database.py` init_db
2. Update `SCHEMA.md` with the new table
3. Write `scripts/benchmark/run_benchmark.py`
4. Write `scripts/benchmark/benchmark_report.py`
5. Smoke test: `--dry-run` lists all challenges, `--limit 1` runs one dispatch

### Phase 2: Sonnet Baseline (~2-3 hours wall-clock)
Run Sonnet against all 874 challenges, one family at a time:
1. `--family elixir-ecto-schema-changeset` (101 challenges, smallest)
2. `--family elixir-security-linter` (101)
3. `--family elixir-oban-worker` (101)
4. `--family elixir-pattern-match-refactor` (131)
5. `--family elixir-phoenix-liveview` (136)
6. `--family elixir-ecto-sandbox-test` (152)
7. `--family elixir-ecto-query-writer` (152)

After each family: run `benchmark_report.py` to check score distributions. If a family shows >50% zero scores, investigate scorer issues before proceeding.

### Phase 3: Evaluate Sonnet Results
- Generate full Sonnet report
- Check: are tier labels calibrated? (easy > medium > hard > legendary in avg score?)
- Check: any scorer bugs? (easy challenges scoring 0.0?)
- Check: which dimensions/families are hardest?
- Present findings to Matt for review

### Phase 4: Opus Baseline (after Matt review)
Same as Phase 2, with `--model claude-opus-4-6`. Expect:
- Higher scores across the board
- Smaller gap on easy, bigger gap on hard/legendary
- Some challenges where Sonnet = Opus (the "ceiling" challenges where the scorer is the bottleneck)

### Phase 5: Comparative Report
- Opus vs Sonnet delta per family, per tier, per dimension
- Identify "Opus-only" challenges (Sonnet < 0.5, Opus > 0.8)
- Identify ceiling challenges (both models > 0.95 — too easy?)
- Identify floor challenges (both models < 0.3 — scorer broken or genuinely hard?)

## Deliverables

1. `benchmark_results` table with ~1,748 rows (874 × 2 models)
2. `scripts/benchmark/run_benchmark.py` — reusable runner
3. `scripts/benchmark/benchmark_report.py` — analysis + reporting
4. Sonnet baseline report (markdown, after Phase 3)
5. Comparative report (markdown, after Phase 5)
6. Updated `SCHEMA.md` with new table

## What This Enables

- **Skill lift metric**: for any evolved skill, compare its challenge scores against the baseline to compute `lift = skill_score - baseline_score`. Positive lift = the skill helps.
- **Challenge pruning**: challenges where both models score 1.0 baseline are too easy — consider removing or upgrading to harder criteria.
- **Difficulty rebalancing**: if "hard" challenges have higher avg than "medium", the labels are miscalibrated.
- **Evolution ROI**: is it worth evolving a skill for a dimension where baseline is already 0.95?
- **New model comparison**: when Claude 5 ships, re-run the benchmark to see the delta.

## Out of Scope

- Running with skill guidance (that's the seed run pipeline, already shipped)
- Frontend visualization (defer until we have data)
- Held-out challenge separation (include ALL challenges — this is a benchmark, not training)
- Multi-language families (Elixir only for now)
