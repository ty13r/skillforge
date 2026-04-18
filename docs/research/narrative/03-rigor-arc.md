# The Scientific-Rigor Arc

> **Status:** active · **Depth:** substantial · **Last updated:** 2026-04-18
>
> Five pivots documented with primary-source links. New pivots will land here as they happen — this page is a living ledger, not a finished history.

SKLD's current design didn't arrive fully formed. It emerged from five concrete moments where we discovered the previous approach was quietly lying to us, stopped, and rebuilt the measurement infrastructure. This page is the story of those pivots — what we thought, what we discovered, what we changed, and why the current design is better.

Each section cites the specific journal entry and plan document where the pivot was reasoned through, so a reader can verify the story against the primary sources.

---

## 1. Molecular → Atomic Evolution

**What we thought (v1.x).** Evolve the entire SKILL.md as a single blob. Spawn 5 variants, run 3 challenges each across 3 generations (45 competitor runs), pick the winner. Simple, end-to-end, works.

**What we discovered.** When a molecular variant scored well, we couldn't tell *why*. Was it the fixture strategy? The mock patterns? The assertion style? Every gene had been mutated simultaneously, so the fitness signal was an average across the whole skill. Worse, mutation was blind to which trait mattered — the Breeder improved the whole blob, which in practice meant it improved whichever trait had the lowest hanging fruit, often at the expense of others that were already working.

The cost was also bad. 45 runs at ~$0.15 each is not expensive, but the information per run was low. A generation of 5 competitors against 3 challenges produces 15 data points, each averaged across every trait. The fitness landscape was too noisy to climb efficiently.

**What we changed (v2.0).** Decompose each skill into foundation + capability *variants*. Evolve each dimension independently: 2 population × 2 generations × 1 focused challenge. Foundation wins first; capabilities compete against the winner.

**Why it's better.**
- **Trait-level signal.** Each dimension produces a clean fitness number for one specific trait. No averaging.
- **Lower cost, same or better outcomes.** ~16 runs per skill instead of 45. The atomic pipeline costs roughly half to three-quarters of molecular for comparable or better outputs.
- **Composable winners.** A great mock strategy evolved in one family is reusable in another. Molecular outputs are idiosyncratic; atomic outputs are library components.
- **Cleaner mutation.** The Breeder working on the mock-strategy variant only sees mock-strategy traces. Mutations can target what matters without disturbing unrelated traits.

**Sources.** Journal #9 (*Atomic Evolution and the v2.0 Vision*), journal #11 (*Atomic Evolution Port, Phases 2-5*), `plans/SPEC-V2.0.md`, `plans/PLAN-V2.0.md`.

**Matt's framing at the moment of the pivot:** *"We've been evolving entire molecules instead of evolving atomic units. What if we decompose a skill into focused variants, evolve each one independently against narrow challenges, then assemble the winners?"* (Journal #9).

---

## 2. Ad-Hoc Challenges → SKLD-Bench

**What we thought.** A Challenge Designer agent invents challenges fresh at run time, scores each variant against what it generates, and the fitness number is meaningful because every variant faced a real challenge.

**What we discovered.** The 5th live atomic test produced four foundation variants on the same dimension scoring 0.60 / 0.60 / 0.67 / 0.60 against four *different* challenges. Those numbers are not comparable. The Challenge Designer was effectively re-rolling the test set for every variant. Worse, the judging pipeline scored skills against the same challenges they were spawned for — which means the surviving skills' content carried that adaptation into the next generation. Even with a blind Breeder, the system was implicitly training on the test set. The research-paper methodology section had no defensible "what did we measure" answer.

**What we changed (v2.1).** Build **SKLD-bench** — a fixed, versioned benchmark that lives on disk. For each of seven Elixir lighthouse families, author ~100-150 challenges spread across difficulty tiers (easy / medium / hard / legendary), plus test fixtures, goldens, a score.py, a criteria.json, and an environment.yml. 867 challenges total. Hold out ~20% of each pool for champion evaluation only. Variants train on the training pool; the headline fitness number comes from the held-out pool that no skill ever saw during evolution.

**Why it's better.**
- **Comparability.** Variant A and variant B in the same family face identical evaluation. Their fitness numbers are directly comparable.
- **Reproducibility.** Re-running an evolution against the same family produces comparable fitness numbers across runs.
- **Generalization signal.** The held-out score measures whether the variant generalized, not whether it memorized.
- **Difficulty curve, not a single score.** Every variant now produces `easy: 0.95, medium: 0.78, hard: 0.45, legendary: 0.10`. One number hid that structure.

**Sources.** Journal #12 (*SKLD-bench: Authoring, Audit, Augment*), `plans/SPEC-V2.1.md`, `taxonomy/elixir/SEEDING-PLAN.md`, `taxonomy/elixir/SCHEMAS.md`.

**Matt's framing at the moment of the pivot:** *"This is a big issue, because without controlled evaluation environments we're not able to know if the change we're making is meaningful."* (`plans/SPEC-V2.1.md`, conversation 2026-04-10).

---

## 3. String-Match → Six-Layer Composite Scoring

**What we thought.** Score each challenge by checking whether the output contains the expected strings — `stream(socket, :posts`, `limit: -50`, idiomatic keywords. This is how most LLM benchmarks work. Fast, cheap, reproducible.

**What we discovered.** Once SKLD-bench was in place, we ran raw Sonnet with no skill attached against all 867 challenges. Raw Sonnet scored **93.3% average**. 405 of 867 challenges scored a perfect 1.0. It looked like the model already knew everything and skills had nothing to add.

Then we ran the deep-dive experiment: 3 hardest Phoenix LiveView challenges × 6 sources (Sonnet raw, Opus raw, Sonnet + v1 skill, Sonnet + v2 spawn, Opus + v1 skill, Opus + v2 spawn). **Five of the six sources scored identically at 0.636 on the hardest challenge.** The string matcher could not tell them apart.

When we compiled the code instead of matching strings, one of those five outputs had a syntax error — Opus + v1 skill had been guided toward an invalid `&` capture pattern. String matching ranked it as the best solution. Compilation scored it zero. When we ran behavioral tests (mounting the LiveView and invoking each event handler), Sonnet raw passed 0 out of 12. Its code compiled, contained the right strings, and called `MyApp.Blog.list_posts/1` — a module that does not exist.

String matching was measuring *"does this look like Elixir?"* — not *"is this good Elixir?"*

**What we changed (v2.1.3).** Replace the scorer with a six-layer composite:

```
composite = (
    L0_string_match   * 0.10 +
    compilation_gate  * 0.15 +
    ast_quality       * 0.15 +
    behavioral_tests  * 0.40 +   ← dominant signal
    template_quality  * 0.10 +
    brevity           * 0.10
)
```

Each layer detects a class of failure the others miss. String matching catches absent keywords; compilation catches syntax errors; AST quality catches non-idiomatic code; behavioral tests catch code that compiles but doesn't work; template quality catches poorly-structured outputs; brevity catches padding. Behavioral tests carry the dominant 40% weight because they are the only metric that separated working code from broken code in the 18-output experiment.

**Why it's better.**
- **Discrimination.** On the challenges where L0 ranked 5 sources identically, the composite produces a clear ranking where code that actually works wins.
- **Real lift shows up.** Raw Sonnet drops from 93.3% to 51.1% on behavioral tests alone. Skill-guided Sonnet now has room to move, and the movement is measurable.
- **Failure modes are auditable.** Each layer records its score and its reasoning. If a composite score drops, we can see whether it was a compile break, a test failure, or a brevity regression.

**Sources.** Journal #14 (*Seven Seed Runs and the Scoring Crisis*), journal #15 (*Scoring Overhaul and Frontend Sprint*), `plans/PLAN-V2.1.3.md`, `bible/book-of-genesis.md` Chapter 1.

**Matt's framing at the moment of the pivot:** *"So are we not testing if the code actually works????"* (Journal #14). The answer, uncomfortably, was no. None of the 867 challenges across all 7 seed runs had been checked for compilation, correct behavior, or structural quality. The session pivoted from "ship more runs" to "fix the fundamental evaluation problem." That pivot is what made the rest of the research defensible.

---

## 4. Single Fitness → Pareto Front

**What we thought.** Fitness is a single number. Rank variants by it. Best variant wins the generation.

**What we discovered.** Collapsing a multi-dimensional evaluation (correctness, trigger accuracy, trace adherence, token efficiency, consistency) into one scalar destroyed information. A variant that was best on correctness and worst on token efficiency was ranked below a "balanced" variant — but the worst-on-efficiency variant might carry a correctness trait the balanced ones lacked. Killing it meant losing that trait forever.

**What we changed.** Maintain a Pareto front per generation. A variant survives if it is best-in-class on *any* objective, not just on the aggregate. Multiple "best" variants can coexist; the Engineer can combine strengths across them at assembly time.

**Why it's better.**
- **Diversity preservation.** Traits that would otherwise be selected against survive if they contribute to any objective.
- **Multi-parent crossover.** The Engineer can merge strengths from multiple Pareto-optimal parents into the composite.
- **No tuning of aggregation weights.** We don't have to pick the "right" weights for the objectives — the Pareto front avoids the question.

**Sources.** Borrowed from GEPA; see `01-prior-art.md` §GEPA. Implemented in `skillforge/engine/variant_evolution.py`.

---

## 5. Random Mutation → Reflective Mutation via Traces

**What we thought.** Mutation is the genetic-algorithm primitive: change a word, swap a paragraph, reorder steps, see if fitness improves. Let selection do the work.

**What we discovered.** Random mutation in SKILL.md space is catastrophic. A skill is a tightly-coupled instruction set — changing one rule often requires matching changes in three others (frontmatter description, allowed-tools, supporting script). Random mutation breaks more than it fixes. Fitness improvements per generation were low, and many generations regressed outright.

**What we changed.** The Breeder reads the full execution trace from the Agent SDK — tool calls, reasoning, outputs, errors — and *diagnoses* why the variant failed before proposing a mutation. A Breeder note now looks like: *"The instruction 'always write tests first' caused the skill to waste 4 turns on trivial scaffolding before understanding the problem. Mutation: rewrite as 'write tests after implementing core logic, then iterate.'"* — targeted, explainable, trace-grounded.

**Why it's better.**
- **Per-generation lift.** Reflective mutation produces larger and more consistent fitness improvements per generation than random mutation in informal comparison.
- **Explainable.** Each mutation has a diagnosis attached. We can read the Breeder's reasoning in the run log and audit whether its diagnosis was correct.
- **Cross-run learning.** Diagnoses accumulate in the learning log. The Breeder reads the log before mutating, so the population does not re-discover failures already explored.

**Sources.** Borrowed from GEPA's Actionable Side Information concept; see `01-prior-art.md` §GEPA. The learning-log mechanic for cross-run accumulation is borrowed from Imbue (same page, §Imbue). Implemented in `skillforge/agents/breeder.py`.

---

## The pattern underneath the five pivots

Each pivot follows the same shape. We shipped something. It produced numbers. Someone asked a skeptical question. We ran a focused experiment to answer it. The experiment exposed a flaw in the measurement. We rebuilt the measurement.

- v1 → atomic: *"which trait is causing the fitness gain?"* — turned out we couldn't tell.
- ad-hoc challenges → SKLD-bench: *"can we compare variant A's score to variant B's?"* — turned out we couldn't.
- string-match → composite: *"is the code actually working?"* — turned out we had no idea.
- single fitness → Pareto: *"is the winner really the best on every axis?"* — turned out the aggregate was hiding useful tradeoffs.
- random → reflective mutation: *"why did fitness regress this generation?"* — turned out the mutations were breaking more than they fixed.

The pattern matters for new contributors and reviewers: progress on SKLD happens when someone asks a question that is specific enough to produce a falsifying experiment. The five pivots above all started as uncomfortable questions, not as planned features.

`06-open-questions.md` lists the uncomfortable questions that are still open.
