# Book of Elixir

*What we learned from evolving 7 Elixir skill families across 867 challenges.*

---

## What This Is

This book documents the Elixir-specific findings from SKLD-bench — a controlled evaluation of AI-generated Elixir code across 7 domain families. Every finding is grounded in measured data from real model dispatches, scored through compilation, AST analysis, and behavioral testing.

If you're building Elixir skills for AI agents, training models on Elixir code, or evaluating AI-generated Elixir, this is the empirical reference.

---

## Chapter 1: The Seven Families

We chose 7 Elixir skill families that cover the most common areas where developers use AI assistance. Each family has its own challenges, scoring criteria, and distinct failure patterns.

| Family | Challenges | What It Tests | Compile Rate |
|--------|-----------|---------------|-------------|
| phoenix-liveview | 135 | Phoenix 1.7+ LiveView idioms, HEEx, streams, PubSub | 83.7% |
| ecto-sandbox-test | 151 | Test isolation, sandbox checkout, async safety | 94.0% |
| pattern-match-refactor | 130 | Idiomatic pattern matching, pipe chains, guards | 83.8% |
| security-linter | 100 | OWASP-style security patterns, Plug middleware | 58.0% |
| oban-worker | 100 | Background job workers, queue config, error handling | 32.0% |
| ecto-schema-changeset | 100 | Schema definitions, changeset validations, types | 13.0% |
| ecto-query-writer | 151 | Ecto query composition, preloads, dynamic queries | 0.7% |

**Source:** Phase 3 cross-family classification, 867 benchmark results with composite scoring, April 12 2026.

The compile rates tell a story about how much external context each domain requires — covered in Chapter 2.

---

## Chapter 2: The Context Dependency Spectrum

Elixir families fall on a spectrum from "self-contained" to "deeply embedded." This spectrum directly predicts compile rates and determines how skills need to be designed.

### Self-Contained Families (high compile rate)

**ecto-sandbox-test (94.0% compile)** and **phoenix-liveview (83.7%)** and **pattern-match-refactor (83.8%)** produce code that mostly stands alone. A LiveView module needs `use MyAppWeb, :live_view` and a few callbacks — the scaffold provides the web framework. A pattern-match refactor just needs pure Elixir.

**What fails:** The 6-17% that don't compile typically reference application-specific modules (`MyApp.Accounts`, `MyApp.Blog`) in mount callbacks or event handlers, or use invalid syntax patterns.

**How we learned this:** Phase 1 compile check against the Phoenix scaffold. 22/135 LiveView outputs failed compilation. Most failures were in `mount/3` where the model called `MyApp.Blog.list_posts/1` — a context module that doesn't exist. *(Phase 1, compile_check.py results, April 12 2026)*

### Context-Dependent Families (low compile rate)

**oban-worker (32.0%)**, **security-linter (58.0%)**, and especially **ecto-schema-changeset (13.0%)** and **ecto-query-writer (0.7%)** produce code that fundamentally depends on application schemas, repos, and configuration.

An Ecto query like `from p in Product, where: p.price > ^min_price, preload: [:category]` requires `Product` to be a defined schema with a `:category` association and `MyApp.Repo` to exist. Without those, compilation fails regardless of code quality.

**How we learned this:** When we re-scored ecto-query-writer with compilation checking, 150 out of 151 outputs failed to compile. The single passing output defined its own inline schema. *(Phase 3, ecto-query-writer re-scoring, April 12 2026)*

**What this means for skill design:** Skills for context-dependent families need to teach the model to either:
1. Define inline schemas/stubs when writing examples
2. Clearly mark external dependencies so evaluation can provide them
3. Focus on query composition patterns rather than complete runnable modules

This isn't a flaw in the model — it's writing realistic production code. The evaluation environment needs to meet it halfway with schema stubs.

---

## Chapter 3: Phoenix LiveView — The Flagship Family

Phoenix LiveView produced the deepest data and the strongest skill lift of any family. It's where the scoring crisis was discovered and where every scoring innovation was validated first.

### 3.1 The Idiom Detection Problem

Phoenix 1.7 introduced a major syntax overhaul: `<.link>` replaced `live_link`, `~p` replaced `Routes.*_path`, `:for` replaced `<%= for %>`, `to_form/2` replaced `form_for`. The scorer checks for these modern idioms.

**The pipe-operator blind spot:** The original scorer checked for `stream(socket, :posts` as a literal string. But idiomatic Elixir uses the pipe operator: `socket |> stream(:posts, ...)`. The first argument disappears. Five of six deep-dive sources scored identically because the scorer missed the piped form.

**The variable-vs-literal blind spot:** The scorer checked for `limit: -50`. Models write `limit: -@page_size` where `@page_size` is a module attribute set to 50. Same semantics, different syntax.

**How we fixed it:** `_pipe_aware_contains()` in `score.py` — when checking `fn(arg1, arg2`, also matches `|> fn(arg2`. For numeric literals, also accepts `@variable` forms. *(Phase 1, score.py bug fixes, April 12 2026)*

### 3.2 Cross-Cutting Score Inflation

The original scorer had 7 "cross-cutting" checks (live_link absent, Routes.*_path absent, etc.) that passed for virtually every solution because modern models don't use pre-1.7 patterns. These contributed ~7 free points to the denominator, inflating every score.

**The fix:** Cross-cutting checks now have weight 0.0 when the anti-pattern is absent (no free points) and 0.5 when present (penalty only). *(Phase 1, cross-cutting weight fix, April 12 2026)*

### 3.3 Where Skills Help Most: +100% Lift

Phoenix LiveView showed the strongest skill lift of any family: +0.267 absolute, +100% relative on the 20 hardest challenges. Sonnet raw scored 0.267; Sonnet + seed skill scored 0.533.

**Why LiveView benefits most:** LiveView has the most domain-specific patterns that differ from what models learn in general training — streams with negative limits, viewport events, `connected?` guards for PubSub, `push_navigate` vs `push_patch`. A skill that teaches these specific patterns gives the model information it genuinely doesn't have.

**The evidence (Phase 4, top 20 hardest LiveView challenges):**
- Raw Sonnet: 0.267 composite mean
- Sonnet + seed skill: 0.533 composite mean
- Win rate: 20/20 (100%) — the skill helped on every single challenge

*(Phase 4, run_skill_benchmark.py, April 12 2026)*

### 3.4 The HEEx Template Quality Signal

For LiveView and other template-producing families, template modernity is a measurable quality signal:

| Pattern | Modern (good) | Legacy (bad) |
|---------|--------------|-------------|
| Expression syntax | `{expr}` | `<%= expr %>` |
| Conditional | `:if={cond}` | `<%= if cond do %>` |
| Comprehension | `:for={item <- list}` | `<%= for item <- list do %>` |
| Links | `<.link navigate={~p"/path"}>` | `<%= live_link "text", to: path %>` |
| Forms | `<.form for={@form}>` | `<%= form_for @changeset, ... %>` |

Template modernity score = `modern_count / (modern_count + legacy_count)`. This metric carries 10% of the composite weight for template-producing families.

**Source:** AST analyzer (`ast_quality.exs`), template pattern counts via regex. *(Phase 1, ast_analyze.py)*

---

## Chapter 4: Ecto Families — Schema Dependencies

### 4.1 Query Writer: The Hardest to Score

Ecto query composition is arguably the most valuable AI coding skill in the Elixir ecosystem — and the hardest to evaluate in isolation.

**The problem:** Every Ecto query references schemas (`from p in Product`), associations (`:category`), repo functions (`Repo.all/1`), and often application-specific query builders. A query writer skill's output is inherently embedded in an application.

**The evidence:** 150/151 outputs failed compilation. L0 scored this family at 98.0% (highest of all 7). Composite scored it at 47.9% (second lowest). The gap between "looks right" and "compiles" is the widest of any family. *(Phase 3, ecto-query-writer re-scoring, April 12 2026)*

**What the skill teaches that helps (+9% lift):**
- Pin operator usage (`^variable` in where clauses)
- Preload strategy discrimination (struct-based vs join-based)
- Fragment safety (avoiding SQL injection in `fragment/1`)
- Dynamic query composition with `Ecto.Query.dynamic/2`
- Window function patterns

*(Phase 4, ecto-query-writer skill benchmark, 14/20 win rate)*

### 4.2 Schema-Changeset: Validation Patterns

Schema-changeset had the highest L0 score (97.4%) and the steepest drop to composite (52.2%) after ecto-query-writer. The 87% compile failure rate comes from the same schema dependency issue.

**What the skill teaches:** Changeset validation chains, custom validators, embedded schemas, polymorphic associations, type casting patterns.

**Skill lift:** +3%, 9/20 win rate. Modest — the model already knows basic Ecto patterns well. The skill helps most on complex validation chains and embedded schema patterns. *(Phase 4)*

### 4.3 Sandbox Test: The Exception

Ecto sandbox test is unique — it has the **highest compile rate (94%)** of any family despite being Ecto-related. Why? Because test isolation code is more about ExUnit configuration and process architecture than about schemas. The code deals with `Ecto.Adapters.SQL.Sandbox.checkout`, `allowances`, and `shared` mode — none of which require application schemas.

**Skill lift:** +8%, 7/20 win rate. Meaningful lift because sandbox patterns are specialized knowledge that models don't encounter often in training data. *(Phase 4)*

---

## Chapter 5: Pattern Match Refactor — Pure Elixir

This family tests idiomatic Elixir transformation: converting imperative code (if/case chains, temporary variables, nil checks) into functional patterns (multi-clause functions, pattern matching, guards, pipe chains).

### 5.1 What the AST Analyzer Measures

The AST quality analyzer walks the Elixir AST and counts:
- **Functions** (public `def` and private `defp`)
- **`@impl` annotations** (callback documentation)
- **Pipe chains** (`|>` usage)
- **Pattern match heads** (multi-clause function definitions)
- **Guard clauses** (`when` expressions)
- **Module attributes** (named constants vs magic numbers)

**Derived scores:**
- `impl_coverage` = impl annotations / public functions (0.0-1.0)
- `pipe_density` = pipe chains / non-empty lines × 10 (normalized)

These metrics carry 15% of the composite weight and directly measure the kind of transformation this family tests.

**Source:** `scripts/scoring/ast_quality.exs`, a 74-line Elixir script using `Macro.prewalk/3`. *(Phase 0, archived from /tmp/scoring_test/)*

### 5.2 Compile Rate and Skill Lift

Compile rate: 83.8% — pure Elixir transforms mostly stand alone.

Skill lift: +7%, but only 3/20 win rate. The low win rate despite positive mean lift means the skill produces large improvements on a few challenges but doesn't help on most. The few challenges where it helps involve complex multi-module refactors where the skill teaches specific transformation sequences.

*(Phase 4, pattern-match-refactor benchmark)*

---

## Chapter 6: Security and Operations Families

### 6.1 Security Linter: Where Skills Barely Help

Security-linter had the weakest skill lift: +0.2%, essentially zero. The 20 hardest challenges involve detecting and fixing OWASP-style vulnerabilities in Phoenix applications — atom exhaustion, SQL injection via Ecto fragments, XSS, CSRF, timing attacks.

**Why skills don't help here:** Security knowledge is well-represented in model training data. Sonnet already knows not to use `String.to_atom(user_input)` or to use `Plug.Crypto.secure_compare/2` for timing-safe comparisons. The skill adds domain structure but not new knowledge.

**Compile rate:** 58.0% — security modules reference Plug, Phoenix, and application-specific middleware, creating moderate context dependency.

*(Phase 4, security-linter benchmark, 7/20 win rate)*

### 6.2 Oban Worker: Low Compile, Low Lift

Oban worker had a 32% compile rate and +1% skill lift. The compile failures come from Oban's macro-heavy design: `use Oban.Worker, queue: :default` requires Oban to be configured in the application, and most workers reference application modules for the actual work.

**What this suggests:** For operations-focused families (job queues, task schedulers, deployment tools), the evaluation scaffold needs to provide more application context — or the skill needs to teach self-contained patterns explicitly.

*(Phase 4, oban-worker benchmark, 8/20 win rate)*

---

## Chapter 7: The Behavioral Test Pattern

### 7.1 Generic Tests via `live_isolated`

Phoenix LiveView provides `live_isolated/2` which mounts a LiveView module without needing router configuration. This enabled a generic behavioral test pattern:

1. **Mount test:** Does `live_isolated(conn, Module)` succeed?
2. **Render test:** Does the rendered HTML contain actual content?
3. **Event tests:** For each `handle_event` defined, does calling it not crash?

This generic pattern — requiring zero per-challenge test authoring — caught the dominant failure mode (undefined external modules) across all 135 LiveView challenges.

**Source:** `scripts/scoring/behavioral_test_runner.py`, generic test generator. *(Phase 2, April 12 2026)*

### 7.2 What Generic Tests Can't Catch

Generic tests verify "doesn't crash" but not "does the right thing." A module that mounts successfully and handles events without crashing might still produce wrong output — displaying stale data, not updating state correctly, or rendering incorrect HTML.

Challenge-specific tests (hand-written ExUnit assertions about expected state changes) would catch these. We deferred writing them because the generic tests already provided strong discriminating signal — the gap between "crashes" and "doesn't crash" was the dominant quality axis.

For future work, the 20 hardest challenges per family are candidates for hand-written behavioral tests that verify correctness, not just liveness.

---

## Chapter 8: Evolution Results — Phoenix LiveView Mock Run

The Phase 5 full mock run evolved 12 dimensions of the Phoenix LiveView skill through competition, producing the first composite scored by the new evaluation pipeline.

### 8.1 Dimension-by-Dimension Results

| Dimension | Seed | Spawn | Winner | Delta |
|-----------|------|-------|--------|-------|
| architectural-stance (foundation) | 0.539 | 0.448 | seed | +0.090 |
| heex-and-verified-routes | 0.450 | 0.450 | tie (seed) | 0.000 |
| function-components-and-slots | 0.444 | 0.450 | spawn | +0.006 |
| live-components-stateful | 0.557 | 0.548 | seed | +0.009 |
| form-handling | 0.516 | 0.451 | seed | +0.066 |
| streams-and-collections | 0.480 | 0.482 | spawn | +0.002 |
| mount-and-lifecycle | 0.290 | 0.546 | **spawn** | **+0.256** |
| event-handlers-and-handle-info | 0.446 | 0.482 | spawn | +0.037 |
| pubsub-and-realtime | 0.498 | 0.563 | spawn | +0.066 |
| navigation-patterns | 0.450 | 0.450 | tie (seed) | 0.000 |
| auth-and-authz | 0.464 | 0.463 | seed | +0.001 |
| anti-patterns-catalog | 0.530 | 0.514 | seed | +0.015 |

**Seed wins: 7. Spawn wins: 5.** Average winner composite: 0.717 (with compile re-scoring).

**Source:** Phase 5, `phase5_full_run.py` orchestrator, 62 total dispatches (12 Opus spawner + 48 Sonnet competitor + 1 Opus engineer). *(April 12 2026)*

### 8.2 The Mount-and-Lifecycle Surprise

The largest swing in any dimension: the seed scored 0.290, the spawn scored 0.546 — nearly double. The spawn variant's approach to lifecycle management (self-contained mount with inline data, proper `connected?` guards) dramatically outperformed the seed's approach (which assumed external context modules).

This is the self-containment principle (Genesis Chapter 2) in action: the evolution environment created selection pressure toward working code, and the spawn's self-contained approach won.

### 8.3 Tied Dimensions

Two dimensions (heex-and-verified-routes, navigation-patterns) tied exactly at 0.450. In both cases, the seed and spawn produced structurally similar code — these dimensions have well-defined "right answers" (use `~p`, use `<.link>`, use `push_navigate`) that both variants hit. There's little room for diversity when the domain has clear canonical patterns.

---

## Appendix: Per-Family Scorecard

*Raw Sonnet baseline, no skill guidance. Composite scoring (L0 + compile + AST + brevity).*

| Family | L0 Mean | Composite Mean | Drop | Compile% | Discriminating |
|--------|---------|---------------|------|----------|---------------|
| ecto-query-writer | 0.980 | 0.479 | -0.501 | 0.7% | 151/151 |
| ecto-schema-changeset | 0.974 | 0.522 | -0.452 | 13.0% | 100/100 |
| oban-worker | 0.948 | 0.616 | -0.331 | 32.0% | 97/100 |
| security-linter | 0.905 | 0.624 | -0.282 | 58.0% | 96/100 |
| pattern-match-refactor | 0.884 | 0.689 | -0.195 | 83.8% | 118/130 |
| phoenix-liveview | 0.855 | 0.511 | -0.324 | 83.7% | 126/135 |
| ecto-sandbox-test | 0.687 | 0.658 | -0.029 | 94.0% | 148/151 |
| **OVERALL** | **0.879** | **0.584** | **-0.295** | **54.0%** | **836/867** |

*Source: Phase 3, all 867 benchmark results re-scored with composite scorer, April 12 2026.*

---

*"Three quality gates passed. The package was still broken. The only way to know is to install it and run it." — Journal #13*
