# SKLD — Project Journal

## Entry #15: The Scoring Overhaul and the Frontend Sprint

**Date**: April 12, 2026  
**Session Duration**: ~8 hours (continuation of Entry #14's marathon)  
**Participants**: Matt + Claude Opus 4.6 (1M context)

---

### The Starting Point

Entry #14 ended with a crisis: raw Sonnet scored 93.3% on our 867 challenges using string matching alone, and 5 of 6 sources scored identically on the hardest challenge. We had a prototype composite scorer in `/tmp/scoring_test/` and a plan (`PLAN-V2.1.2`), but nothing was wired into the real pipeline. The `dispatch_transcripts` table didn't exist yet. Deep-dive outputs were still in `/tmp`.

Matt's directive was clear: fix scoring, classify challenges, validate skill lift, and do it properly — save everything, no shortcuts.

---

### Phase 1: Data Foundation (Phase 0 of PLAN-V2.1.3)

The plan crystallized into 6 phases (`plans/PLAN-V2.1.3.md`), superseding the earlier V2.1.2 draft. Phase 0 was about preventing future data loss.

Built the `dispatch_transcripts` table — 16 columns covering the full audit trail for every agent dispatch. Added a `scores` TEXT column to `benchmark_results` via additive migration to hold the multi-level breakdown JSON alongside the existing scalar `score` column.

Archived the 18 deep-dive outputs from `/tmp/skld-level-test/` into `dispatch_transcripts` before the OS could clean them up. Copied the `ast_quality.exs` prototype to its permanent home at `scripts/scoring/ast_quality.exs`.

This was the lesson from Entry #14 applied: "if you don't save it, it didn't happen."

---

### Phase 2: The Composite Scorer Goes Live (Phases 1-2)

**Phase 1 — Compilation + AST**: Built `compile_check.py` (namespace-aware, word-boundary regex for `MyApp` → `SkldBench` substitution), `ast_analyze.py` (shells out to the Elixir AST walker, falls back to Python regex analysis), and the main `composite_scorer.py` orchestrating all levels.

Created 7 Mix scaffolds — one per family — with appropriate dependencies. Phoenix families got `mix phx.new`, Ecto families got `mix + ecto`, Oban got `mix + oban`. Each scaffold lives at `taxonomy/elixir/<family>/scaffold/skld_bench/`.

Fixed 3 real bugs in the phoenix-liveview `score.py`: pipe-operator blindness (`stream(socket, :posts` didn't match `|> stream(:posts`), variable-vs-literal (`limit: -50` didn't match `limit: -@page_size`), and cross-cutting weight inflation (7 "free" anti-pattern checks were adding 2.5 weight each to the absent score, inflating every output).

Re-scored all 18 deep-dive transcripts and 135 phoenix-liveview benchmark outputs. The baseline dropped from 0.855 to 0.684 — compilation alone caught 22 failures (16.3%) that string matching had missed.

**Phase 2 — Behavioral Tests**: Built `behavioral_test_runner.py` with generic LiveView tests using `live_isolated` — no router config needed. The runner extracts the module name and `handle_event` names from the code, generates ExUnit tests for mount + each event handler, and reports pass/fail/failures.

This was the real discriminator. The mean dropped to 0.511. Only 19 of 135 outputs (14.1%) passed all behavioral tests. The dominant failure mode: `UndefinedFunctionError: function MyApp.Blog.list_posts/1 is undefined`. Sonnet writes production-style code that assumes the rest of the application exists — the module compiles fine but crashes immediately at runtime.

The composite formula with full weights: behavioral (0.40) + compile (0.15) + AST (0.15) + L0 (0.10) + template (0.10) + brevity (0.10).

---

### Phase 3: The $53 Incident

To re-score all 867 challenges across 7 families, we needed the code content stored in `benchmark_results.output_files`. Five of seven families had only stored filenames, not content — the code was lost to `/tmp`. We had to re-dispatch 581 challenges.

I delegated the re-dispatching to a background agent. That agent installed `claude-code-sdk` into the project venv and dispatched through the Anthropic API key instead of the `claude` CLI (which uses Matt's Max subscription). By the time Matt noticed, ~75 challenges had been dispatched through the API at full credit pricing.

Matt's screenshot of $53.31 in API credit charges was not a happy moment.

**Lesson burned into memory**: All dispatches MUST use `claude -p` (CLI, Max subscription). Never install or use `claude_code_sdk` in the project venv. The API key in `.env` is for gated live tests only. This became a critical feedback memory — no exceptions, no "just this once."

After Matt disabled the API key, I built `run_benchmark_cli.py` using `subprocess.run(["claude", "-p", ...])` and re-dispatched properly. The 581 bad rows (zero scores from the failed SDK approach) were cleaned up and replaced.

---

### Phase 4: Cross-Family Classification (Phase 3)

All 867 challenges re-scored with composite (L0 + compile + AST + brevity — no behavioral for cross-family, since only phoenix-liveview had the scaffold for it).

The classification reversed completely:

```
L0-only:       478 noise / 217 discriminating / 172 calibration
Composite:       0 noise / 836 discriminating /  31 calibration
```

Every single challenge now has meaningful headroom for skill improvement. The challenges were hard enough all along — the scorer just couldn't see it.

Ecto families had very low compile rates (query-writer: 0.7%, schema-changeset: 13%) because the generated code references undefined schemas and repos. Not a challenge problem — a scaffold problem. Future work: add stub schemas/repos to Ecto scaffolds for fairer compile testing.

---

### Phase 5: Skill Lift Validated (Phase 4)

Built `run_skill_benchmark.py` — prepends the seed SKILL.md to each challenge prompt, dispatches via `claude -p`. Ran the top 20 most discriminating challenges per family (140 total) with Sonnet + seed-v1 skill.

**All 7 families showed positive composite lift. Zero showed negative lift.**

Phoenix-liveview had the highest lift: +0.267 absolute, effectively doubling the composite score. Query-writer had modest +0.040. Every family improved. The short-term goal — "Sonnet + Skills convincingly outperforms Sonnet raw" — was validated with measured data.

---

### Phase 6: The Full Mock Run (Phase 5)

Built `phase5_full_run.py` — a complete evolution loop orchestrator for phoenix-liveview. For each of 12 dimensions: sample 2 challenges, spawn a diverse alternative via Opus, dispatch 4 competitors (seed x 2 + spawn x 2) via Sonnet, score with composite, pick the winner.

62 total dispatches. Seed won 7/12 dimensions, spawns won 5/12. Average winner composite: **0.5024**. The biggest spawn victory was mount-and-lifecycle (+0.256 delta) — the spawn produced self-contained code while the seed variant assumed external context.

Re-exported the phoenix-liveview seed JSON with honest composite scores. The fitness number on the Registry dropped from the inflated 0.94 to the honest **0.50**. Matt said he wanted accurate numbers, not pretty ones.

---

### Phase 7: The Bible Rewrite

Matt looked at the existing Bible — pattern descriptions, findings, anti-patterns — and said "this is kind of weak." He was right. The entries were research notes from the skills-research phase, not empirical findings from our actual experiments.

We rewrote it into two books:

**Book of Genesis** — universal principles of AI skill engineering. 6 chapters covering the scoring problem (string matching is worthless, compilation is the cheapest gate, behavioral tests are the dominant signal), the self-containment problem (models write code for projects not for isolation, and this is a feature for evolution), skills as an equalizer (Sonnet → Opus level, not Opus → better), data capture (if you don't save it, it didn't happen), evolution dynamics (the scorer shapes the outcome), and skill design patterns (preserved from the original research with full provenance).

**Book of Elixir** — Elixir-specific findings from the 7 lighthouse families. 8 chapters covering the compile rate spectrum (8.5% overall, 83.7% for phoenix-liveview, 0.7% for ecto-query-writer), per-family profiles, the context dependency problem, Phoenix LiveView idiom detection (modern vs legacy HEEx), Ecto schema dependencies, the mock run results, and the full 867-challenge benchmark dataset.

Every finding cites the specific experiment, journal entry, or data source where it was discovered. No theory — just measured results.

---

### Phase 8: The Frontend Sprint

The scoring overhaul produced real data but none of it was visible in the UI. The Registry still showed inflated L0 numbers. There was no SKLD-bench page. The taxonomy page didn't show capability breakdowns. The homepage didn't explain the process.

Matt approved a 6-workstream sprint to make the data visible before starting Phase 6 (production engine integration):

1. **Backend bench API**: `GET /api/bench/summary` and `GET /api/bench/:familySlug` — query `benchmark_results` for per-family stats, tier breakdowns, dimension stats, score histograms, challenge-level data.

2. **Fitness card**: The big "0.94 BEST FITNESS" became "0.50 BEST FITNESS" with "Baseline: 0.511" and "Lift: -2%" underneath. Honest numbers.

3. **Competition section**: Added a Raw Sonnet column alongside Seed and Spawn, turning the 2-column match cards into 3-column comparisons showing where the raw model sits relative to evolved variants.

4. **SKLD-bench pages**: New `/bench` overview with the scoring formula, a scoring progression chart (L0: 87.9% → Compile: 54.0% → Behavioral: 3.6% → Composite: 58.4%), a family scoreboard, and per-family detail pages at `/bench/:familySlug` with tier breakdowns, dimension bars, score distribution histograms, and sortable/filterable challenge tables.

5. **Taxonomy capabilities**: Family cards now expand to show per-dimension fitness bars when you click "Show dimensions."

6. **Homepage pipeline flow**: 12 scroll-triggered animated steps showing the full SKLD pipeline from ecosystem research through shipping, with SVG mini-visualizations for each step (network graphs, ranking bars, tree decompositions, file trees, versus matchups, scoring layers, selection funnels, merge diagrams). Updated the Platform stats card from stale hardcoded numbers to real data (867 challenges, 7 families, 6 scoring layers).

7. **Bible update**: The API now serves Book of Genesis and Book of Elixir as a "books" category alongside the existing patterns and findings. The Bible browser auto-selects the first book on load and features them prominently in the sidebar.

Shipped as PR #36, merged to main, Railway auto-deploys.

---

### Artifacts Produced

| Artifact | Lines/Size | Purpose |
|---|---|---|
| `skillforge/api/bench.py` | 225 | SKLD-bench API endpoints |
| `frontend/src/components/SkldBench.tsx` | 224 | Bench overview page |
| `frontend/src/components/SkldBenchFamily.tsx` | 395 | Per-family bench detail page |
| `frontend/src/components/PipelineSteps.tsx` | 541 | Homepage animated pipeline flow |
| `plans/PLAN-V2.1.3.md` | 290 | Active scoring overhaul plan (6 phases) |
| `bible/book-of-genesis.md` | 231 | Universal skill engineering principles |
| `bible/book-of-elixir.md` | ~400 | Elixir-specific empirical findings |
| `scripts/scoring/composite_scorer.py` | ~300 | Multi-level composite scorer |
| `scripts/scoring/compile_check.py` | ~150 | Compilation gate |
| `scripts/scoring/ast_analyze.py` | ~100 | AST quality analyzer |
| `scripts/scoring/behavioral_test_runner.py` | ~200 | Generic behavioral test generator |
| `scripts/scoring/rescore_benchmark.py` | ~150 | Batch re-scorer for existing results |
| `scripts/benchmark/run_benchmark_cli.py` | ~120 | CLI-based benchmark runner (safe) |
| `scripts/benchmark/run_skill_benchmark.py` | ~150 | Skill-guided benchmark runner |
| 7 Mix scaffolds | ~50 files | Per-family compilation environments |
| PR #36 | 16 files, 1,954 lines | Frontend sprint (merged) |

### Key Decisions

| Decision | Rationale |
|---|---|
| Supersede V2.1.2 with V2.1.3 | Cleaner 6-phase structure after discovering the data loss problem needed Phase 0 |
| Never use `claude_code_sdk` in venv | $53 API incident — all dispatches must use `claude -p` CLI (Max subscription) |
| Generic behavioral tests over hand-written | `live_isolated` + extracted event handlers provides strong signal with zero per-challenge authoring |
| Composite scorer weights: behavioral 40% | Empirically the only metric that separates working from broken code |
| Frontend sprint before Phase 6 | Matt wanted the story visible before wiring scoring into production — data exists, needs to be seen |
| Honest numbers over pretty numbers | Phoenix LV fitness dropped from 0.94 to 0.50 — accurate composite, not inflated L0 |
| Bible split: Genesis (universal) + Elixir (specific) | Universal lessons apply to any language; Elixir findings are ecosystem-specific |

### What's Next

**Phase 6: Production Engine Integration** — wire the composite scorer into the evolution engine so real runs (not mock runs) use multi-level scoring. The Competitor agent needs to save outputs to `dispatch_transcripts`, the Reviewer needs to run composite scoring, and the Breeder needs to see honest fitness values.

**Opus raw baselines** — dispatch all 867 challenges against raw Opus to establish the ceiling. Deferred until Matt's subscription resets Thursday.

**Other 6 families re-export** — need Phase 5 mock runs per family to get honest composite numbers. Currently showing old L0 fitness values.

**Ecto scaffold stubs** — schema-changeset and query-writer families need stub schemas/repos in their scaffolds for fair compile testing. Current 0.7% and 13% compile rates are partly a scaffold problem.

---

*"The hardest part wasn't building the scorer — it was accepting that our flagship number was 0.50, not 0.94."*
