# SKLD — Project Journal

## Entry #14: Seven Seed Runs and the Scoring Crisis

**Date**: April 12, 2026
**Session Duration**: ~14 hours (single marathon session)
**Participants**: Matt + Claude Opus 4.6 (1M context)

---

### The Starting Point

Entry #13 left us with 4 seed runs shipped (phoenix-liveview,
ecto-sandbox-test, security-linter, oban-worker) and 3 remaining
(ecto-schema-changeset, ecto-query-writer, pattern-match-refactor).
All the prep work was done — families seeded, variants spawned, 35/35
v2 variants confirmed. The task was straightforward: dispatch
competitors, score, persist winners, assemble composites, ship.

What actually happened was more interesting.

---

### Phase 1: Finishing the Seed Runs

The first half of the session was pure execution. Schema-changeset
went cleanly: 44 competitor dispatches across 12 dimensions, all
scored via score.py, winners persisted, Engineer assembled a 398-line
composite, fitness 0.987 — the highest of all 7 families. Shipped as
PR #33.

Query-writer was messier. The first batch of 8 dispatches scored
mostly 0.0 because I'd manually crafted prompts that didn't match the
actual challenge content. A lesson in "read the challenge JSON, don't
guess from truncated output." After re-dispatching with the correct
prompts, 48 competitors scored properly. 4 v1 wins, 8 v2 wins,
composite fitness 0.935. PR #34.

Pattern-match-refactor went fastest — I delegated 36 of 44 competitor
dispatches to a single background Opus agent that solved and scored
them all autonomously. 1 v1 win, 10 v2 wins, fitness 0.945. PR #35.

**All 7 seed runs shipped.** 83 dimensions evolved across 7 Elixir
families, ~300 real competitor dispatches, 7 composite skills
assembled. Total API cost across all 7 runs: $63.18 at current Opus
4.6 pricing ($5/$25 per M tokens) — dramatically lower than the
$28-35 estimates we'd been showing on the Registry, which were based
on old Opus 4.1 pricing ($15/$75). Matt noticed the $0.00 cost
display on the new runs and asked me to compute real costs from token
usage, which led to updating all 7 runs with accurate numbers.

---

### Phase 2: SKLD-bench — The Baseline Nobody Expected

Matt asked a question that changed the trajectory of the session:
"Wouldn't running the ENTIRE challenge pool against raw Sonnet and
Opus tell us how capable the models are without any skill guidance?"

Yes. And the answer was uncomfortable.

We designed the benchmark infrastructure: a `benchmark_results` table
(15 columns, unique on challenge_id + model), a runner script that
dispatches raw model against challenges and scores via score.py, and
a report generator. Then launched 7 background Sonnet agents in
parallel — one per family — to process all 874 challenges.

The results came back over about an hour:

```
ecto-schema-changeset:     100 challenges, avg 0.990, 100% pass
ecto-query-writer:         151 challenges, avg 0.980, 100% pass
ecto-sandbox-test:         151 challenges, avg 0.958, 100% pass
pattern-match-refactor:    130 challenges, avg 0.920, 100% pass
oban-worker:               100 challenges, avg 0.915, 100% pass
security-linter:           100 challenges, avg 0.912, 100% pass
phoenix-liveview:          135 challenges, avg 0.855, 88% pass
```

**Raw Sonnet scores 93.3% average across 867 challenges with no skill
guidance at all.** 405 out of 867 challenges scored a perfect 1.0.
The only family with failures was phoenix-liveview (16 failures out
of 135).

This meant that for 6 of 7 families, a skill-guided variant could
improve by at most ~5-8% over a model that already aces the tests.
The scorers couldn't discriminate.

---

### Phase 3: "Are We Not Testing If the Code Actually Works?"

Matt asked the question directly: "So are we not testing if the code
actually works????"

No. None of it. Every single score across all 874 challenges and all
7 seed runs was purely string pattern matching. `must_contain` checks
if a string appears in the output file. A file containing
`field :price, :decimal` in a comment scores the same as a working
module. Code with syntax errors passes if it contains the right
keywords.

This was the moment the session pivoted from "ship more runs" to
"fix the fundamental evaluation problem."

---

### Phase 4: The Deep Dive — 3 Challenges, 6 Sources, 4 Levels

We picked the 3 hardest Phoenix LiveView challenges (hard-07 at
0.109, medium-12 at 0.292, hard-06 at 0.292) and generated outputs
from 6 different sources:

1. Sonnet raw (no skill)
2. Opus raw (no skill)
3. Sonnet + v1 seed skill
4. Sonnet + v2 spawn skill
5. Opus + v1 seed skill
6. Opus + v2 spawn skill

Then scored each through increasingly rigorous levels:

**Level 0 — String matching (current scorer):** 5 of 6 sources scored
identically at 0.636 on hard-07. Useless for ranking.

**Level 1 — AST parse:** All 9 passed. Too shallow.

**Level 2 — Compilation in a Phoenix project:** Caught exactly one
real bug — Opus+v1 used an invalid `&` capture syntax that string
matching ranked as the best solution. Cheap, high value.

**Level 3 — ExUnit behavioral tests:** The discriminator. Opus raw
passed 12/12 tests. Sonnet+v1/v2 passed 5/12. Sonnet raw passed
0/12. Code that compiles and contains the right strings but calls
undefined modules crashes at runtime.

The objective-level breakdown was equally revealing. On hard-07,
`stream(socket, :posts` fails for ALL 6 sources because everyone
writes `socket |> stream(:posts, ...)` — the pipe operator hides the
first argument from the string matcher. `limit: -50` fails for
everyone because they use `limit: -@page_size`. These aren't code
bugs; they're scorer bugs.

---

### Phase 5: The Composite Fitness Score

Matt asked: "Can you generate a compiled fitness score, so we have
a single number to rank everything?"

The formula:

```
composite = (
    L0_string_match  * 0.10 +
    compilation      * 0.15 +
    ast_quality      * 0.15 +
    behavioral_tests * 0.40 +
    template_quality * 0.10 +
    brevity          * 0.10
)
```

Applied to the 6 sources on hard-07:

```
#1  0.913  Opus raw          — 12/12 tests, concise
#2  0.721  Opus+v2 skill     — 7/12 tests, best templates
#3  0.681  Sonnet+v2 skill   — 5/12 tests, skill helped
#4  0.645  Sonnet+v1 skill   — 5/12 tests
#5  0.413  Sonnet raw        — 0/12 tests, 121 LOC
#6  0.368  Opus+v1 skill     — compile failure, zeroed
```

L0 alone ranked 5 of these identically. The composite produces a
clear, defensible ranking where code that actually works wins.

---

### What We Learned

**1. Skills are a Sonnet equalizer, not an Opus accelerator.**
Sonnet jumps from 0.11 to 0.64 with a skill (6x improvement). Opus
raw already hits 0.64 without any skill. Skills bring Sonnet up to
Opus's level but don't push Opus further. The value proposition is
"make a cheaper model perform like the expensive one."

**2. Skills can hurt.** Opus+v1 was the only compile failure across
all 18 outputs. The seed skill guided it toward an invalid capture
pattern. A skill that teaches the wrong thing is worse than no skill.

**3. String matching is nearly worthless for ranking.** When 5 of 6
sources score identically, the scorer is measuring "is this Elixir?"
not "is this good Elixir?"

**4. Behavioral tests are the dominant signal.** The 0.40 weight on
test pass rate isn't arbitrary — it's the only metric that separated
working code from broken code in our experiment.

**5. The pipeline loses data at every step.** Competitor outputs go
to temp dirs and get deleted. Agent transcripts are buried in JSONL.
The production system needs a `dispatch_transcripts` table that
stores the full prompt, response, extracted code, and multi-level
scores for every single dispatch.

**6. Opus 4.6 pricing changed the economics.** At $5/$25 per M
tokens (down from $15/$75 on Opus 4.1), running 300 Opus dispatches
costs $63 total. The 7 seed runs that we estimated at $28-35 each
actually cost $4.50-$11.74 each.

---

### Artifacts Produced

| Artifact | Lines/Size | Purpose |
|---|---|---|
| `skillforge/seeds/seed_runs/elixir-ecto-schema-changeset.json` | 1,871 | Seed run #5, fitness 0.987, PR #33 |
| `skillforge/seeds/seed_runs/elixir-ecto-query-writer.json` | 1,919 | Seed run #6, fitness 0.935, PR #34 |
| `skillforge/seeds/seed_runs/elixir-pattern-match-refactor.json` | 1,776 | Seed run #7, fitness 0.945, PR #35 |
| `scripts/benchmark/run_benchmark.py` | 225 | SKLD-bench baseline runner |
| `scripts/benchmark/benchmark_report.py` | 175 | Benchmark statistics generator |
| `benchmark_results` DB table | 867 rows | Sonnet baseline across all 7 families |
| `plans/PLAN-SKLDbench.md` | 150 | Benchmark execution plan |
| `plans/PLAN-V2.1.2.md` | 457 | Scoring overhaul + pipeline observability plan |
| `/tmp/scoring_test/` | ~20 files | Phoenix test scaffold + AST analyzer + ExUnit tests |
| `/tmp/skld-level-test/` | 18 dirs | Deep-dive outputs (6 sources × 3 challenges) |

### Key Decisions

| Decision | Rationale |
|---|---|
| Behavioral tests get 40% weight in composite | Only metric that separated working from broken code in 18-output experiment |
| Compilation is a gate, not a bonus | Code that doesn't compile is objectively broken regardless of string match score |
| L0 string matching kept at 10% weight | Still provides some signal but can't dominate — too gameable |
| dispatch_transcripts table for full audit trail | Can't improve what you can't measure; losing agent outputs is losing data |
| 7-sprint execution plan, scorer fixes first | Everything downstream (benchmarks, seed runs, engine) depends on accurate scoring |
| Per-family Mix scaffolds for compilation testing | Each family has different deps (Phoenix vs Ecto vs Oban); one scaffold doesn't fit all |

### What's Next

The immediate next step is Sprint 1 of PLAN-V2.1.2: fix the
string-matching bugs in all 7 scorers, then re-score the existing
867 Sonnet outputs without re-dispatching. This gives us a corrected
baseline and validates the fixes. Then compilation gates, then
behavioral tests, building up to the full composite scorer.

The deeper question is whether SKLD's value proposition is "make
Sonnet perform like Opus through skills" (which the data supports)
or "make Opus perform better than Opus through skills" (which it
currently doesn't). The answer shapes whether we optimize for
Sonnet-tier skill lift or invest in harder challenges that stress
even Opus.

---

*"We spent 14 hours shipping 3 seed runs and discovering that none
of the scores mean anything."*
