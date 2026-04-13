# Book of Genesis

*Universal principles of AI skill engineering, discovered through empirical evolution.*

---

## What This Is

This book documents what we've learned about building skills for AI coding agents — not through theory, but through running 867 controlled experiments across 7 skill families and measuring what actually works.

Every finding here was discovered the hard way: by building something, testing it, finding out it was broken, and fixing it. Each section cites exactly where the learning came from so you can trace the evidence yourself.

These principles apply regardless of programming language or domain. The experiments happened to use Elixir, but the lessons are universal.

---

## Chapter 1: The Scoring Problem

**The single most important finding in this project: if your evaluation can't tell good code from bad code, nothing else matters.**

### 1.1 String Matching Is Nearly Worthless

We built 867 coding challenges and scored AI-generated solutions by checking whether the output contained expected strings — patterns like `stream(socket, :posts` or `limit: -50`. This is how most LLM benchmarks work: check if the output contains the right keywords.

Raw Sonnet (no skill guidance) scored **93.3% average** across all 867 challenges. It looked like the model already knew everything and skills had nothing to add.

Then we actually tried to compile the code.

**How we learned this:** We ran a deep-dive experiment on the 3 hardest Phoenix LiveView challenges, generating code from 6 different sources (2 models × 3 skill configurations). Five of the six sources scored identically at 0.636 on the hardest challenge. The string matcher couldn't tell them apart. *(Journal #14, "The Scoring Crisis", April 12 2026)*

**The evidence:**
| Scorer | Sonnet Baseline | Can It Rank? |
|--------|----------------|-------------|
| String match (L0) | 93.3% | No — 5/6 sources tied |
| + Compilation | 68.4% | Yes — catches broken code |
| + AST quality | 68.4% | Yes — rewards idiomatic style |
| + Behavioral tests | 51.1% | Yes — only 14% actually work |

**The principle:** Any evaluation that doesn't test whether code actually runs is measuring "does this look like code?" not "is this good code?" String matching is a necessary check (does the output contain the right concepts?) but should carry no more than 10% of the total score weight.

### 1.2 Compilation Is the Cheapest High-Value Gate

Adding a single binary check — does this code compile? — dropped the baseline from 93.3% to 68.4% and caught bugs that every other quality gate missed.

**How we learned this:** During the deep-dive experiment, one source (Opus + v1 skill) was ranked as the *best* solution by string matching. When we compiled it, it had a syntax error. The skill had guided the model toward an invalid capture pattern. String matching scored it highest; compilation scored it zero. *(Deep-dive experiment, source: opus-v1-skill-hard-07, Journal #14)*

**The evidence:** Across all 867 challenges, **399 outputs (46%) fail compilation** despite most scoring above 0.70 on string matching. Eight outputs scored above 0.85 on string matching but didn't compile at all — "ghost passes" that look perfect on paper.

**The principle:** Compilation is binary, cheap (~1 second), and catches a class of failures that no amount of string matching can detect. It should be the first automated gate in any code evaluation pipeline.

### 1.3 Behavioral Tests Are the Dominant Signal

The question "does this code compile?" is necessary but insufficient. Code can compile perfectly and still not work — it might reference external modules that don't exist, handle events incorrectly, or crash on mount.

**How we learned this:** We built a generic behavioral test runner that mounts LiveView modules via `live_isolated` and calls each defined event handler. On the hardest challenge (hard-07), Opus raw passed 4/4 behavioral tests. Sonnet raw passed 0/4 — its code compiled fine but called `MyApp.Blog.list_posts/1`, a module that doesn't exist. *(Phase 2, behavioral test runner, April 12 2026)*

**The evidence:**
| Source | L0 Score | Compiles? | Behavioral | Composite |
|--------|----------|-----------|-----------|-----------|
| Opus raw | 0.959 | Yes | 4/4 | **0.952** |
| Opus + v2 skill | 0.619 | Yes | 4/4 | **0.921** |
| Sonnet + v2 skill | 0.959 | Yes | 0/4 | 0.550 |
| Sonnet raw | 0.238 | Yes | 0/4 | 0.382 |
| Opus + v1 skill | 0.789 | No | 0/1 | 0.388 |

Behavioral tests carry 40% of the composite score weight — the largest single component — because they're the only metric that separates "code that works" from "code that looks right."

**The principle:** The highest-value evaluation metric is always "does this code actually do what it's supposed to do?" Every other metric is a proxy.

---

## Chapter 2: The Self-Containment Problem

### 2.1 Models Write Code for Projects, Not for Isolation

When you ask an AI model to write a module, it writes it the way a developer would: assuming the rest of the application exists. A Phoenix LiveView module references `MyApp.Blog.list_posts/1`. An Ecto schema references `MyApp.Repo`. An Oban worker references `MyApp.Mailer`.

None of these modules exist in a test scaffold. The code compiles (the module names are syntactically valid) but crashes immediately at runtime.

**How we learned this:** After adding behavioral tests, we discovered that the dominant failure mode for Sonnet wasn't bad code — it was realistic code that assumed context. Sonnet writes production-style code. Opus writes self-contained demonstrations. Both are "correct" in different contexts, but only self-contained code passes isolated behavioral tests. *(Phase 2 analysis, April 12 2026)*

**The evidence:** Across 135 Phoenix LiveView challenges, only 19 outputs (14.1%) passed all behavioral tests. The primary failure: `UndefinedFunctionError: function MyApp.Blog.list_posts/1 is undefined`. The code was well-structured, idiomatic, and would work perfectly in a real application.

**The principle:** AI-generated code exists on a spectrum from "self-contained demonstration" to "production module." Evaluation environments must decide which they're testing for and be explicit about it. If you test in isolation, you're measuring self-containment as much as code quality.

### 2.2 This Is a Feature, Not a Bug — For Evolution

The self-containment problem creates a natural selection pressure when used inside an evolution loop. Variants that produce self-contained code score higher on behavioral tests. Over generations, the breeder learns that "stub your dependencies" and "inline sample data" are winning traits.

This is exactly how skills should teach: not by adding a rule that says "always write self-contained code," but by creating an environment where self-contained code wins and letting the evolution discover the pattern.

**How we learned this:** In the Phase 5 mock run, the spawned variant for `mount-and-lifecycle` dramatically outperformed the seed (+0.256 composite delta). The spawn produced self-contained lifecycle code; the seed assumed external context. The composite scorer selected the spawn as winner — correct behavior emerging from selection pressure, not explicit instruction. *(Phase 5, mount-and-lifecycle dimension, April 12 2026)*

---

## Chapter 3: Skills as an Equalizer

### 3.1 Skills Make Cheaper Models Perform Like Expensive Ones

The most consistent finding across all 7 families: skills bring Sonnet up toward Opus's level but don't push Opus further. The value proposition isn't "make the best model better" — it's "make a cheaper model perform like the expensive one."

**How we learned this:** The deep-dive experiment scored 6 sources on the 3 hardest challenges. Sonnet raw scored 0.382. Sonnet + skill scored 0.550. Opus raw scored 0.952. Skills gave Sonnet a 44% improvement but Opus was already at the ceiling. *(Deep-dive experiment, hard-07, April 12 2026)*

**The evidence (Phase 4, all 7 families):**
| Family | Sonnet Raw | Sonnet + Skill | Lift |
|--------|-----------|---------------|------|
| phoenix-liveview | 0.267 | 0.533 | **+100%** |
| ecto-query-writer | 0.440 | 0.479 | +9% |
| ecto-sandbox-test | 0.476 | 0.513 | +8% |
| pattern-match-refactor | 0.424 | 0.456 | +7% |
| ecto-schema-changeset | 0.424 | 0.439 | +3% |
| oban-worker | 0.496 | 0.501 | +1% |
| security-linter | 0.419 | 0.421 | ~0% |

All 7 families showed positive lift. Zero showed negative lift (skills never made things worse on average).

**The principle:** The economic value of skills is cost reduction: achieve Opus-quality output at Sonnet pricing. For a team running thousands of AI coding tasks per day, this is significant.

### 3.2 Skills Can Hurt

While the average lift is always positive, individual cases exist where a skill guides the model toward a worse answer than it would produce on its own.

**How we learned this:** In the deep-dive, Opus + v1 skill was the *only* source that failed to compile. The seed skill contained a pattern using an invalid function capture syntax (`&`). Opus, following the skill's guidance, reproduced the error. Without the skill, Opus would have written correct code. *(Deep-dive, opus-v1-skill-hard-07, Journal #14)*

**The principle:** A skill that teaches the wrong thing is worse than no skill. This is why evolution matters — it creates selection pressure against harmful patterns. Variants that introduce bad patterns lose competitions and get eliminated.

---

## Chapter 4: Data Capture

### 4.1 If You Don't Save It, It Didn't Happen

Over the course of building this platform, we lost data three separate times to temporary directories being cleaned up. The richest experiment of the project — 18 outputs scored through 4 levels — existed only as prose in a journal entry because the actual code was in `/tmp`.

**How we learned this:**
1. The original 7 seed runs stored benchmark output filenames but not code content. When we tried to re-score with the new composite scorer, 5 of 7 families had lost their code. We had to re-dispatch 581 challenges ($15 in API costs + 45 minutes of wall time). *(Phase 3 discovery, April 12 2026)*
2. The deep-dive experiment outputs in `/tmp/skld-level-test/` were only rescued because the OS hadn't cleaned them yet. We archived them to the database immediately. *(Phase 0, archive_deep_dive.py)*
3. Competitor outputs during seed runs were written to temp directories and deleted after scoring — losing the raw model responses forever. *(Phase 3, data flow audit)*

**The principle:** Every agent dispatch should write to permanent storage before the pipeline moves on. The `dispatch_transcripts` table pattern — save the prompt, response, extracted files, and scores for every single dispatch — means nothing is ever lost. The cost of storage is trivial; the cost of re-dispatching is not.

### 4.2 Schema Checks Pass Broken Packages

We had three layers of quality gates on our skill packages: a zip export validator, a Gold Standard Checklist, and a Package Explorer with green indicators. All three passed. Then we tried to actually install and run the package.

Three real bugs emerged:
1. A bash script used `declare -A` (bash 4+ only) — broken on macOS
2. A pipeline created a subshell that swallowed variable assignments
3. A code rewriter produced syntactically invalid output

**How we learned this:** Matt asked "should we try installing the skill?" after everything showed green. The install test caught bugs that no schema-level check could detect. *(Journal #13, "The Install Test", April 11 2026)*

**The principle:** The only way to know if a package works is to install it and run it. File-existence checks, line counts, and structural validators are necessary but not sufficient. This is the code evaluation problem (Chapter 1) applied to skill packages themselves.

---

## Chapter 5: Evolution Dynamics

### 5.1 The Scorer Shapes the Outcome

When we ran evolution with L0-only scoring, every variant looked equally good because the scorer couldn't discriminate. Winner selection was essentially random. When we switched to composite scoring (L0 + compile + AST + brevity), different winners emerged.

**How we learned this:** In the Phase 5 mock run, we compared L0-only rankings against composite rankings. The `mount-and-lifecycle` dimension had the largest change: the seed scored higher on L0 (more keyword hits) but the spawn scored higher on composite (its code actually compiled and had better structure). The composite scorer selected the spawn — the correct choice. *(Phase 5, dimension results, April 12 2026)*

**The principle:** The fitness function *is* the specification. Whatever you measure is what evolution optimizes for. If you measure keyword presence, you get keyword-stuffed code. If you measure "does it compile and run," you get working code.

### 5.2 Challenges Were Hard Enough All Along

We initially worried that our 867 challenges were too easy — raw Sonnet scored 93.3% — and considered writing harder ones. After fixing the scorer, the baseline dropped to 51.1%. The challenges were discriminating the whole time; the scorer just couldn't see it.

**How we learned this:** After applying composite scoring to all 867 challenges across 7 families, the classification changed from 478 noise / 217 discriminating to **0 noise / 836 discriminating**. Every single challenge now has meaningful headroom for skill improvement. *(Phase 3 classification, April 12 2026)*

**The principle:** Before investing in harder content, fix the evaluation. Bad scores make good content look easy.

---

## Chapter 6: Skill Design Patterns

*These patterns are preserved from the original Skills Bible research. They were derived from analysis of community-contributed Claude Agent Skills and empirical testing.*

### 6.1 Descriptions (Routing Layer)

The description is what determines whether Claude activates your skill. It's the most leveraged piece of text in the entire package.

| Pattern | Finding | Source |
|---------|---------|--------|
| Front-load capability + triggers within 250 chars | Longer descriptions get truncated by the routing system | Skills research audit, `docs/skills-research.md` |
| Use "Use when..." clause | Activation rate jumps from ~20% (vague) to ~50% (with "Use when") | Skills research, P-DESC-003 |
| Include "NOT for..." exclusions | Prevents false activations on adjacent topics | Skills research, P-DESC-004 |
| Add 2-3 examples in the body | Quality jumps from 72% to 90% with diverse examples | Skills research, P-DESC-002 |
| Use task-verb phrasing ("Build a REST API") not identity ("You are an API expert") | Task-verb phrasing produces more focused, actionable output | Skills research, P-DESC-005 |

### 6.2 Instructions (Execution Layer)

| Pattern | Finding | Source |
|---------|---------|--------|
| Keep SKILL.md under 500 lines | Quality degrades past ~500 lines; the model loses focus | Skills research, P-INST-001 |
| Instruction budget: ~150-200 discrete instructions max | Beyond this, later instructions get ignored | Skills research, P-INST-006 |
| Don't teach what the model already knows | Redundant instructions waste budget and can conflict with training | Skills research, P-INST-007 |
| Numbered steps for workflows, bullets for options | Structural markers help the model navigate long documents | Skills research, P-INST-003 |
| Use H2/H3 headers as section boundaries | The model uses headers to locate relevant sections | Skills research, P-INST-004 |

### 6.3 Resources (Context Layer)

| Pattern | Finding | Source |
|---------|---------|--------|
| Script code never enters context — only stdout/stderr | Scripts are cost-free for context; use them for deterministic work | Skills research, P-SCRIPT-001 |
| Validate all reference paths in CI | 73% of audited community skills had broken `${CLAUDE_SKILL_DIR}` references | Skills research, P-STRUCT-005 |
| Use `${CLAUDE_SKILL_DIR}` for all paths | Hard-coded paths break when skills are installed in different locations | Skills research, P-STRUCT-004 |
| References must be better than training data | The model already knows the basics; references compete with its training | Phoenix-liveview seed run, Journal #13 |
| Test fixtures should exhibit specific anti-patterns | Generic "example.ex" files don't test anything meaningful | Phoenix-liveview install test, Journal #13 |

---

## Appendix: The Composite Fitness Formula

The formula we converged on after the scoring crisis:

```
composite = (
    L0_string_match  * 0.10 +   # Does it contain expected patterns?
    compilation      * 0.15 +   # Does it compile?
    ast_quality      * 0.15 +   # Is it well-structured?
    behavioral_tests * 0.40 +   # Does it actually work?
    template_quality * 0.10 +   # Does it use modern idioms?
    brevity          * 0.10     # Is it concise?
)
```

These weights were derived from the deep-dive experiment on 6 sources × 3 challenges, where behavioral tests provided the dominant differentiator (0-100% spread vs string matching's 0% spread). They are not arbitrary — they reflect empirical signal strength. *(Phase 2, composite formula validation, April 12 2026)*

---

*"We spent 14 hours shipping 3 seed runs and discovering that none of the scores mean anything." — Journal #14*
