# Elixir LLM Pain Points — Research Report

**Date**: 2026-04-10
**Researcher**: Claude Opus 4.6 (autonomous web research agent)
**Purpose**: Validate the proposed Elixir skill family roster for SkillForge against real developer reports
**Signal quality**: Moderate but unusually concrete

---

## Methodology

The research agent searched Elixir Forum, Hacker News, GitHub plugin repositories, Dev.to, and developer blogs for 2025-2026 reports of Elixir developers using Claude (and other LLM coding assistants) to write Elixir code. The strongest evidence came from three sources:

1. **The BoothIQ post-mortem** ("150,000 lines of vibe-coded Elixir") and its follow-on discussions on Hacker News and Elixir Forum
2. **The "iron law" catalogs inside two widely-shared Claude Code plugins** for Elixir: `oliver-kriska/claude-elixir-phoenix` and `georgeguimaraes/claude-code-elixir`. Each enforced rule is a de facto bug report — the plugin authors built tooling to prevent observed Claude failures.
3. **The Elixir Forum thread "Current status of LLMs writing Elixir"** and several related "how I'm using AI with Elixir" threads.

Public Elixir+AI discussion is modest in volume compared to the JavaScript or Python communities, but unusually concrete when it does surface — the Elixir community leans toward detailed post-mortems. The plugin repos are particularly valuable because each "iron law" represents a developer-confirmed Claude failure mode.

**Limitation**: The signal is moderate. Any pain point whose evidence is *only* "a plugin has a rule for it" is corroborating rather than primary. In this report, every claim has at least one independent developer narrative backing it.

---

## Part 1 — Top pain points by evidence

### 1. Ruby/Java-style imperative code instead of pattern matching

- **Frequency**: 5+ independent sources
- **Severity**: Moderate (idiom nits, pervasive but not data-corrupting)
- **Quote**: *"Claude writes Ruby-style Elixir — if/then/else chains, defensive nil-checking, early returns that don't make sense in a functional context."*
  — [BoothIQ blog post](https://getboothiq.com/blog/150k-lines-vibe-coded-elixir-good-bad-ugly)
- **Corroborated**: *"writes Java even if it's Elixir"* (troupo, HN); *"Still correcting if/else chains that should be pattern matches"* (Alex66, Elixir Forum); *"`case functioncall() do nil -> ... end` instead of idiomatic `if var = functioncall() do`"* (dnautics, HN)
- **Maps to**: yes → `elixir-pattern-match-refactor`

### 2. OTP/concurrency blindness (GenServers, supervision, async)

- **Frequency**: 4+ independent sources
- **Severity**: Major
- **Quote**: *"Claude is useless for debugging OTP, Task, or async issues. It doesn't understand how processes, the actor model, and GenServers work together."*
  — [BoothIQ blog post](https://getboothiq.com/blog/150k-lines-vibe-coded-elixir-good-bad-ugly)
- **Corroborated**: *"Async or mildly complex thread stuff is like kryptonite for LLMs"* (alecco, HN); *"crappy OTP ... brittle tests with concurrency issues, unsupervised processes, overuse of potentially runaway atoms"* (HN thread)
- **Plugin rule**: *"NO PROCESS WITHOUT A RUNTIME REASON"* — Claude wraps stateless code in GenServers for "organization"
  — [georgeguimaraes/claude-code-elixir otp-thinking](https://github.com/georgeguimaraes/claude-code-elixir/blob/main/plugins/elixir/skills/otp-thinking/SKILL.md)
- **Maps to**: partial → `elixir-genserver-builder` covers authoring but misses the *over-use* and *debugging* dimensions. **Reframing required**: the family should teach when NOT to use GenServers, not just how to write one.

### 3. Ecto sandbox / concurrent test isolation misunderstanding

- **Frequency**: 3 sources (one strong, two echoing)
- **Severity**: Major (wastes hours of debugging time)
- **Quote**: *"It can't debug concurrent test failures. It doesn't understand that each test runs in an isolated transaction... Claude doesn't understand this. It uses Tidewave's dev DB connection and thinks it's looking at the test DB — which is always empty."*
  — [BoothIQ blog post](https://getboothiq.com/blog/150k-lines-vibe-coded-elixir-good-bad-ugly)
- **Reported mitigation behavior**: *"Attempted to seed test databases to force passing tests"*; *"Recommends disabling async tests due to misunderstanding isolation"*
  — [HN discussion](https://news.ycombinator.com/item?id=46752907)
- **Maps to**: NO existing family. **NEW FAMILY**: `elixir-ecto-sandbox-test`. This is the most named "ugly" pain point and nothing in the original 10-family roster touches it.

### 4. LiveView lifecycle mistakes (mount vs handle_params, assign_new)

- **Frequency**: 3+ independent sources (plugin iron laws + HN discussion)
- **Severity**: Major (silent data corruption, duplicate queries)
- **Quote**: Iron law *"NO DATABASE QUERIES IN MOUNT"* exists because the plugin authors observed Claude writing this pattern repeatedly
  — [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix)
- **Also reported**: *"Claude Code doesn't know that `assign_new` silently skips on reconnect"*; missing `connected?/1` checks before PubSub subscribe; failing to use streams for lists >100 items
- **Maps to**: yes → `elixir-phoenix-liveview` (validates the family as the strongest evidence-backed candidate)

### 5. Float for money in Ecto

- **Frequency**: 2 sources (both plugin catalogs)
- **Severity**: Major (silent data corruption in production)
- **Quote**: *":float will corrupt your money fields"* — listed as an explicit iron law because Claude defaults to `:float` for monetary fields
  — [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix)
- **Maps to**: yes → `elixir-ecto-schema-changeset`

### 6. Hallucinated APIs / invented syntax

- **Frequency**: 3 sources
- **Severity**: Major
- **Quote**: *"Invented `elsif` syntax multiple times in Elixir code"*; *"Produces 'Java annotations as Elixir module attributes' when confused"*
  — [HN thread](https://news.ycombinator.com/item?id=46752907)
- **Copilot analog**: *"hallucinates on occasion, by suggesting function calls to modules from stdlib that are not there, or are in a different variant or different module (like Enum vs List)"*
  — hubertlepicki, [Elixir Forum](https://elixirforum.com/t/current-status-of-llms-writing-elixir-code/66465)
- **Maps to**: NO single existing family — this is cross-cutting. **Possible new family**: `elixir-stdlib-validator`. May be better solved as a tool hook (compile-with-warnings-as-errors) than a skill.

### 7. Oban: non-idempotent jobs, atom keys, stored structs

- **Frequency**: 2 plugin sources, multiple confirmed iron laws
- **Severity**: Major (data loss, crash-on-retry)
- **Quote**: *"Claude Code doesn't know... that Oban jobs might not be idempotent"*; iron laws include *"atom keys instead of strings in job arguments"* and *"Storing Elixir structs directly in job args"*
  — [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix)
- **Maps to**: yes → `elixir-oban-worker`

### 8. Security gaps (atom exhaustion, SQL injection, XSS, missing authorization)

- **Frequency**: 2 plugin sources, explicit enforcement rules
- **Severity**: Major (vulnerabilities)
- **Quote**: Plugin v2.3.0 enforces:
  - *"`String.to_atom/1` on user input"* (atom exhaustion)
  - *"String interpolation in Ecto fragment"* (SQL injection)
  - *"Redirect to user-controlled URLs"* (open redirects)
  - *"`==` with tokens/secrets"* (timing attacks)
  - *"XSS via `raw/1`"*
  - *"Missing authorization: forgetting authorization checks in LiveView `handle_event`"*
  — [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix)
- **Maps to**: NO existing family. **NEW FAMILY**: `elixir-security-linter`. An entire enforcement tier in the plugin exists for this — Claude has demonstrable security blind spots in Elixir.

### 9. Missing pin operator (`^`) in Ecto queries

- **Frequency**: 2 plugin sources
- **Severity**: Major (allows unintended matches, silent query bugs)
- **Quote**: *"Always pinning values with `^` in queries"* — explicit enforced rule
  — [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix)
- **Maps to**: yes → `elixir-ecto-query-writer`

### 10. Wrong preload strategy (join preload on has_many)

- **Frequency**: 2 plugin sources
- **Severity**: Moderate (performance regression)
- **Quote**: *"Using join preloads for has-many associations, which consumes '10x more memory'"*
  — [georgeguimaraes/claude-code-elixir ecto-thinking](https://github.com/georgeguimaraes/claude-code-elixir)
- **Maps to**: yes → `elixir-ecto-query-writer`

### 11. Error-handling gaps (ignored `:error` tuples, swallowed rescues)

- **Frequency**: 2 sources
- **Severity**: Moderate
- **Quote**: *"rescuing exceptions and then not notifying about them ... using the non-raising version of a function and then not doing something reasonable when it returns `:error`"*
  — [HN thread](https://news.ycombinator.com/item?id=46752907)
- **Maps to**: NO existing family. **Possible new family**: `elixir-error-tuple-handler`. Overlaps with pattern-match family but distinct enough to stand alone.

### 12. Code organization / duplication / amnesia

- **Frequency**: 3 sources
- **Severity**: Moderate
- **Quote**: *"AI is exceptional at churning out lines of code. It's significantly less exceptional at deciding where those lines should go. It defaults to creating new files everywhere. It repeats code it's already written."*
  — [BoothIQ blog post](https://getboothiq.com/blog/150k-lines-vibe-coded-elixir-good-bad-ugly)
- **Also**: *"It'll happily rewrite code it thinks it needs if it doesn't know where it exists"*
- **Maps to**: NOT a skill-shaped problem. This is an architectural / agent context problem, not something a skill family can fix.

### 13. Verbose / useless docs and over-commented code

- **Frequency**: 2 sources
- **Severity**: Minor
- **Quote**: *"The documentation it generates is usually way too verbose and focuses on minute details"*
  — [Elixir Forum](https://elixirforum.com/t/how-are-you-using-ai-with-elixir-at-work-on-production-ready-apps/72326)
- **Maps to**: NOT a candidate for a dedicated family. Style nit, not a structural failure.

---

## Part 2 — Validation verdicts on the original 10 candidate families

| # | Family | Verdict | Evidence |
|---|---|---|---|
| 1 | `elixir-pattern-match-refactor` | ✅ Validated | Pain point #1 — BoothIQ + 3 HN/Forum comments |
| 2 | `elixir-genserver-builder` | 🟡 Partial | Pain point #2 exists, but the complaint is *over-use*, not authoring correctness. A naive builder skill could make this worse unless it also teaches *when not to* |
| 3 | `elixir-supervisor-tree` | 🟡 Partial | Evidence exists ("unsupervised processes", "wrong supervision strategy") but it's a subset of the broader OTP-blindness pain — 1 explicit plugin rule |
| 4 | `elixir-ecto-schema-changeset` | ✅ Validated | Pain point #5 (float for money) + changeset mistakes cited in the ecto-thinking plugin |
| 5 | `elixir-ecto-query-writer` | ✅ Validated | Pain points #9 + #10 — pin operators, preload strategies — explicit plugin rules |
| 6 | `elixir-phoenix-liveview` | ✅ Validated | Pain point #4 — strongest plugin enforcement, 5+ specific mistakes catalogued |
| 7 | `elixir-phoenix-context` | ❌ Not validated | Zero specific complaints about context module authoring. Closest: "cross-context belongs_to" warning, but that's an association issue, not context structure |
| 8 | `elixir-exunit-test-suite` | 🟡 Partial | *"generated tests are inconsistent"* (Elixir Forum) but the bigger complaint is **sandbox/concurrency**, not test authoring |
| 9 | `elixir-oban-worker` | ✅ Validated | Pain point #7 — explicit plugin iron laws (idempotency, atom keys, struct args) |
| 10 | `elixir-typespec-annotator` | ❓ Unclear | No developer complaints found about missing/wrong typespecs in AI-generated Elixir. Dialyzer+AI is discussed positively by Dashbit — implies Claude is decent at this |

---

## Part 3 — Missed families (most important section)

### A. `elixir-ecto-sandbox-test` — TOP 10 CONTENDER ⭐

**Specialization**: Helps Claude navigate `Ecto.Adapters.SQL.Sandbox`, async-test isolation, `allow/3` for background processes, and connection ownership across the Tidewave dev-vs-test DB confusion.

**Evidence**: Pain point #3 — directly named as "the ugly" in the BoothIQ post-mortem, corroborated in HN discussion.

**Citations**:
- [BoothIQ blog](https://getboothiq.com/blog/150k-lines-vibe-coded-elixir-good-bad-ugly)
- [HN thread](https://news.ycombinator.com/item?id=46752907)

**Recommendation**: **Should displace `elixir-phoenix-context`** in the active roster. This is a major, named, evidence-backed pain and no existing family touches it.

---

### B. `elixir-security-linter` — TOP 10 CONTENDER ⭐

**Specialization**: Catches atom exhaustion (`String.to_atom` on user input), SQL injection via Ecto fragments, `raw/1` XSS, open redirects, timing attacks, missing LiveView `handle_event` authorization, mass-assignment in changesets, weak password hashing, insecure session config.

**Evidence**: Pain point #8 — an entire enforcement tier in the oliver-kriska plugin, explicitly motivated by Claude's blind spots.

**Citations**:
- [oliver-kriska/claude-elixir-phoenix v2.3.0 changelog](https://github.com/oliver-kriska/claude-elixir-phoenix)
- [Elixir Forum: Claude opinionated integration thread](https://elixirforum.com/t/claude-opinionated-claude-code-integration-for-elixir/71831)

**Recommendation**: **Should displace `elixir-typespec-annotator`** in the active roster.

---

### C. `elixir-error-tuple-handler` — close runner-up

**Specialization**: Teaches Claude to handle `{:ok, val} / {:error, reason}` correctly: no silent `_ = error`, no unnotified rescues, use `with` for multi-step flows, know when to use raising vs non-raising variants.

**Evidence**: Pain point #11 — 2 HN commenters explicitly named this.

**Citations**: [HN thread](https://news.ycombinator.com/item?id=46752907)

**Recommendation**: Runner-up, not top-10. Overlaps significantly with the pattern-match family.

---

### D. `elixir-stdlib-validator` — close runner-up (or cross-cutting tool)

**Specialization**: A skill that specifically targets hallucinated module calls (`Enum` vs `List` confusion, stdlib functions that don't exist, invented keywords like `elsif`).

**Evidence**: Pain point #6 — 3 sources.

**Recommendation**: Runner-up. May be better solved as a tool hook (compile-with-warnings-as-errors) than a skill family.

---

### E. `elixir-otp-debugger` — close runner-up

**Specialization**: Not authoring, but *reasoning about* a running system: reading `:observer` state, interpreting crash reports, understanding process lifecycles.

**Evidence**: Pain point #2 — BoothIQ explicitly flagged debugging (not authoring) as the OTP problem.

**Recommendation**: Runner-up. Harder to evaluate than authoring skills because the inputs are runtime artifacts (crash reports, observer dumps) rather than user prompts.

---

## Part 4 — Signal summary

### Strongest 5 of the original 10 candidates

1. **elixir-phoenix-liveview** — richest, most specific evidence base
2. **elixir-ecto-query-writer** — multiple hard bugs (pin operator, preload strategy) with plugin confirmation
3. **elixir-ecto-schema-changeset** — float-for-money alone is a clinching evidence item
4. **elixir-oban-worker** — three distinct, concrete failure modes
5. **elixir-pattern-match-refactor** — most cited complaint (though lowest severity)

### 3 to drop if building only 7 families

1. **elixir-typespec-annotator** — zero developer complaints; evidence suggests Claude already handles this adequately
2. **elixir-phoenix-context** — no real developer pain point; context structure is not what's breaking
3. **elixir-supervisor-tree** — real pain exists but subsumed under the broader GenServer/OTP debugging cluster; building it alone doesn't fix the underlying blind spot

### Surprises

- **Expected but absent**: I expected strong complaints about bad `with`-expression chains, wrong protocol implementations, and Phoenix Channels mistakes. None showed up clearly in the research.
- **Unexpected finds**: Ecto sandbox / concurrent-test confusion was the most-named "ugly" in the top post-mortem and isn't in the original candidate list at all. Security is the second big gap.
- **Also interesting**: developers widely report Claude writing "Ruby-style" Elixir — the pattern-matching refactor skill has the most frequent complaint base but the lowest severity. Don't over-weight this one when prioritizing.

### Overall signal quality

**Moderate, but better than feared.** Public Elixir+AI discussion is thin in volume compared to JS/Python communities, but the BoothIQ post-mortem plus two well-maintained Claude Code plugins give an unusually structured view of what's actually breaking. Any skill family whose evidence is *only* "a plugin has a rule for it" should be treated as corroborating rather than primary — but in this report those cases each have at least one independent developer narrative backing them. The one area where signal is genuinely thin is typespecs / Dialyzer; do not build that family without more direct evidence.

---

## Sources

### Primary sources (developer narratives + post-mortems)

- [BoothIQ: 150,000 Lines of Vibe Coded Elixir — The Good, The Bad, and The Ugly](https://getboothiq.com/blog/150k-lines-vibe-coded-elixir-good-bad-ugly)
- [HN discussion of BoothIQ article](https://news.ycombinator.com/item?id=46752907)
- [Elixir Forum discussion of BoothIQ article](https://elixirforum.com/t/150-000-lines-of-vibe-coded-elixir-the-good-the-bad-and-the-ugly/73899)
- [Elixir Forum: Current status of LLMs writing Elixir code](https://elixirforum.com/t/current-status-of-llms-writing-elixir-code/66465)
- [Elixir Forum: Here's how I'm coding Elixir with AI](https://elixirforum.com/t/heres-how-im-coding-elixir-with-ai-results-are-mixed-mostly-positive-how-about-you/71588)
- [Elixir Forum: How are you using AI with Elixir at work](https://elixirforum.com/t/how-are-you-using-ai-with-elixir-at-work-on-production-ready-apps/72326)
- [HN: I use Claude code with Elixir and Phoenix](https://news.ycombinator.com/item?id=45001245)
- [Petros blog: Upgrading Phoenix app with Claude Code](https://petros.blog/2026/02/15/upgrading-an-elixir-phoenix-app-using-tidewave/)
- [Dashbit: Why Elixir is the best language for AI](https://dashbit.co/blog/why-elixir-best-language-for-ai)

### Plugin-derived "iron law" catalogs (corroborating evidence)

- [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix)
- [georgeguimaraes/claude-code-elixir](https://github.com/georgeguimaraes/claude-code-elixir)
- [georgeguimaraes otp-thinking skill](https://github.com/georgeguimaraes/claude-code-elixir/blob/main/plugins/elixir/skills/otp-thinking/SKILL.md)
- [Elixir Forum: Sharing my Claude Code plugin for Elixir](https://elixirforum.com/t/sharing-my-claude-code-plugin-for-elixir-development/74119)
- [Elixir Forum: Claude opinionated integration thread](https://elixirforum.com/t/claude-opinionated-claude-code-integration-for-elixir/71831)
