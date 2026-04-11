# elixir-pattern-match-refactor — Per-Capability Research Dossier

**Generated**: 2026-04-11
**Workstream**: SKLD-bench v2.1 (see [`../SEEDING-PLAN.md`](../SEEDING-PLAN.md))
**Sources surveyed**:
- BoothIQ post-mortem ("150,000 lines of vibe-coded Elixir")
- HN thread on the BoothIQ post-mortem (item 46752907)
- Elixir Forum: "150,000 lines of vibe-coded Elixir" discussion thread
- Elixir Forum: "Current status of LLMs writing Elixir code"
- Elixir Forum: "How are you using AI with Elixir at work"
- Elixir Forum: "Coding with LLMs: CONVENTIONS.md for Elixir"
- Elixir Forum: "Claude - Opinionated Claude Code integration for Elixir"
- Elixir Forum: "Idiomatic Pattern Matching: function `def` vs. `case`"
- Paul Fedory blog: "Practicing Elixir in the age of AI coding assistants"
- Zach Daniel blog: "LLMs & Elixir: Windfall or Deathblow?"
- Dashbit blog: "Writing assertive code with Elixir" (José Valim)
- Nick Janetakis blog: "Refactoring Elixir Code: If, Cond and Pattern Matching"
- georgeguimaraes/claude-code-elixir — `elixir-thinking` skill
- oliver-kriska/claude-elixir-phoenix — Iron Laws catalog
- Elixir v1.20 official docs: `code-anti-patterns.html` (non-assertive pattern matching, non-assertive truthiness, non-assertive map access, complex else clauses in with, complex extractions in clauses)
- Elixir Streams: "Refactoring complex else clauses in with", "Refactoring complex extractions in function heads" (German Velasco)
- lucasvegi/Elixir-Refactorings catalog
- Credo: `Credo.Check.Refactor.NegatedIsNil`
- MCP Market listings for `elixir-essentials` and `elixir-thinking` skills

**Total citations**: 38

---

## Family-level summary

`elixir-pattern-match-refactor` is the **most-cited** Elixir+Claude complaint in public sources. The evidence is wide and consistent: Claude defaults to imperative control flow (`if`/`else` chains, `cond`, defensive `nil` checks, helper `maybe_do_*` functions) instead of Elixir's native idioms (multi-clause function heads, guards, `with` chains, pipe pipelines). This happens across every 2025 LLM generation Elixir developers have tried, surfaces repeatedly in HN threads and Elixir Forum discussions, and is the reason the two most-starred Elixir Claude Code plugins (`oliver-kriska/claude-elixir-phoenix` and `georgeguimaraes/claude-code-elixir`) both ship an explicit "match on function heads instead of `if/else` or `case` in bodies" iron law.

Severity is **moderate** (idiomatic nits, not data corruption), but pervasiveness is the highest of any Elixir pain point. The BoothIQ post-mortem named it first. HN commenter **te_chris** captured the frustration most vividly: *"Even the latest models still write elixir like a JS developer, checking nils, maybe_do_blah helper functions everywhere. 30 lines when 8 would do."* The complaint is language-independent (troupo: *"It tends to always write Java even if it's Elixir"*); Claude falls into imperative mode regardless of the surrounding Elixir codebase's style.

The research maps cleanly to the family's 10 capabilities, with strongest evidence for **defensive-nil-checks-elimination**, **function-head-pattern-matching**, **cond-and-if-reduction**, and **with-expressions**. Weaker but still present evidence for **pipe-operator-flows**, **guard-clauses**, **map-and-struct-destructuring**, and **recursive-functions**. The thinnest evidence is for **binary-pattern-matching-basic** (not a complaint locus in the community discussion — though the official anti-patterns guide covers it) and **enum-vs-recursion-choice** (subsumed under the broader "imperative style" pain but rarely surfaced as a distinct complaint).

A critical subtlety: the official Elixir anti-patterns guide (v1.20) also warns against **over-using** pattern matching via the *"Complex extractions in clauses"* anti-pattern. A naive refactor skill could push Claude from one anti-pattern (too much `if`/`case`) into another (unreadable 8-arg destructured function heads). Challenges should test both directions — a skill that mechanically converts every `case` into function heads is wrong; the skill must decide when each idiom fits.

---

## Capability research

### Foundation: `refactor-philosophy`

**Description** (from README.md): How aggressively the skill rewrites: in-place edits (preserve structure, change idioms), extract-functions (pull conditional branches into separate function heads), pipe-first rewrite (rebuild around `|>`). Variants determine the canonical "after" shape.

**Known Claude failure modes**:
- [HIGH] No coherent refactor philosophy — Claude does spot fixes rather than committing to a structural transformation, leaving codebases in mixed styles.
- [HIGH] When instructed to "use pattern matching," Claude mechanically converts every `case` into function heads without asking whether that's the right shape for the specific function — can introduce the "Complex extractions in clauses" anti-pattern.
- [MED] Preserves `if` chains as the outer structure and only cleans up leaf branches, leaving imperative spine in place.
- [MED] Inconsistency across a single file: some functions get refactored to function-head style, others keep `case`, with no defensible reason.

**Citations**:
- *"It defaults to defensive, imperative code. You need to be strict about what good Elixir looks like."* — John-BoothIQ, https://elixirforum.com/t/150-000-lines-of-vibe-coded-elixir-the-good-the-bad-and-the-ugly/73899 (2026)
- *"The defensive/imperative code issue persists though. Still correcting if/else chains that should be pattern matches."* — Alex66, https://elixirforum.com/t/150-000-lines-of-vibe-coded-elixir-the-good-the-bad-and-the-ugly/73899 (2026)
- Elixir Streams (German Velasco): *"Function-head pattern matching can be used as logic control **and** as an extraction mechanism... when both are used at the same time in different function heads, it becomes difficult to know what's important for logic flow and what's merely an extraction convenience."* — https://www.elixirstreams.com/tips/function_head_extraction_anti_pattern
- Elixir official anti-patterns (v1.20): *"Complex extractions in clauses ... when you have extractions made across several clauses and several arguments of the same function, it becomes hard to know which extracted parts are used for pattern/guards and what is used only inside the function body."* — https://hexdocs.pm/elixir/main/code-anti-patterns.html

**Suggested challenge angles**:
- Mixed-style file: refactor so the entire file follows one philosophy consistently
- "Don't over-refactor": given a 4-arg function where destructuring in the head would create noise, keep extraction in the body
- Decide when a `case` should become function heads vs. stay as `case` based on whether branches produce the function's return directly
- Pipe-first full rewrite: take a 30-line nested function and restructure around `|>`

**Tier guidance**:
- 3 easy (obvious single-direction refactors), 4 medium (decide when to refactor vs. leave alone), 4 hard (mixed-style cleanup across multiple functions), 3 legendary (avoid introducing `Complex extractions in clauses` anti-pattern while refactoring).

---

### Capability: `function-head-pattern-matching`

**Description** (from README.md): Replacing `case` chains with multiple function heads.

**Known Claude failure modes**:
- [HIGH] Produces a `case x do` block inside the function body when multi-clause function heads would be more idiomatic — this is the single most-cited Elixir Claude complaint.
- [HIGH] When branches produce the function's return directly, Claude still prefers `case` over function heads.
- [MED] Given a `case`, Claude may convert to function heads but leave the call site still wrapped in the same `case` (ghost wrapping).
- [MED] Duplicates setup logic across new function heads instead of extracting a helper.

**Citations**:
- **oliver-kriska/claude-elixir-phoenix & georgeguimaraes/claude-code-elixir** both ship the explicit rule: *"Match on function heads instead of `if/else` or `case` in bodies"* — `elixir-thinking` skill, https://github.com/georgeguimaraes/claude-code-elixir
- *"Even the latest models still write elixir like a JS developer, checking nils, maybe_do_blah helper functions everywhere. 30 lines when 8 would do."* — te_chris, https://news.ycombinator.com/item?id=46752907 (2026)
- *"It tends to always write Java even if it's Elixir."* — troupo, https://news.ycombinator.com/item?id=46752907 (2026)
- Paul Fedory: *"the model doesn't often generate idiomatic Elixir unless explicitly prompted to rewrite the code in a specific way. For example, I've noticed it prefers standard control structures (e.g., `if`/`else`, `case`) over function clauses with guards."* — https://paulfedory.com/software/practicing-elixir-in-the-age-of-ai/ (2025)
- Nick Janetakis: *"the above code works, it's not very maintainable... you have your conditionals mixed in with what your function is supposed to do"* (referring to stacked `if`s before showing the multi-clause refactor) — https://nickjanetakis.com/blog/refactoring-elixir-code-if-cond-and-pattern-matching

**Suggested challenge angles**:
- "Given this `case user.role do "admin" -> ...; "editor" -> ...; "viewer" -> ... end`, produce multi-clause function heads."
- Case with 5+ branches where function-head style is clearly better
- Case where branches share setup — refactor should extract shared helper, not duplicate
- Deliberate anti-case: function heads would fight against the existing structure — skill should explain why it's leaving the `case` alone

**Tier guidance**:
- 4 easy (straight `case` → multi-clause), 5 medium (decide which branches to split), 4 hard (preserve tracing/dbg hooks), 3 legendary (refactor without creating complex-extractions anti-pattern).

---

### Capability: `guard-clauses`

**Description** (from README.md): `when` clauses, what's allowed in guards (limited subset of Elixir), composition with `and`/`or`.

**Known Claude failure modes**:
- [HIGH] Uses arbitrary function calls in guards — `when validate(x)` — which won't compile because guards only allow a restricted subset.
- [HIGH] Uses `&&`/`||` in guards instead of `and`/`or`, or uses `not is_nil(x)` instead of asserting the type you actually expect.
- [MED] Fails to use `defguard`/`defguardp` to DRY out repeated guard expressions.
- [MED] Puts logic that should be a guard into the function body with an `if`/`case`, bypassing the guard system entirely.
- [LOW] Doesn't know that `in [nil, ""]` works as a guard and opts for verbose alternatives.

**Citations**:
- Credo `Credo.Check.Refactor.NegatedIsNil`: *"avoid negating the is_nil predicate function ... code using `when not is_nil(external_id)` should be refactored to either match on nil cases directly or match on what you were expecting in the first place, such as `when is_binary(external_id)`"* — https://hexdocs.pm/credo/Credo.Check.Refactor.NegatedIsNil.html
- Elixir Forum guidance: *"State what you want, not what you don't. ... don't use `def call_service(%{req: req}) when not is_nil(req)`, instead use `def call_service(%{req: req}) when is_binary(req)`"* — https://elixirforum.com/t/idiomatic-guard-clause-for-checking-not-nil/18296
- georgeguimaraes `elixir-thinking`: *"Reserve `is_thing` names for guards only"* and *"`%{}` matches ANY map—use `map_size(map) == 0` guard for empty maps"* — https://github.com/georgeguimaraes/claude-code-elixir
- Official Elixir docs (Patterns and Guards): Guards are a *"handy tool for augmenting pattern matching with more complex checks"* that support a restricted subset of Elixir expressions. — https://hexdocs.pm/elixir/patterns-and-guards.html
- Elixir Non-assertive Truthiness anti-pattern: *"Replace truthiness operators `&&`, `||`, `!` with boolean-specific `and`, `or`, `not` when operands are expected to be booleans."* — https://hexdocs.pm/elixir/main/code-anti-patterns.html

**Suggested challenge angles**:
- Refactor a function body with `if is_integer(x) and x > 0` into a guard clause
- Convert `when not is_nil(req)` into an assertive guard (e.g., `when is_binary(req)`)
- Extract a repeated guard expression into a `defguard` macro
- Identify a "compile error if you run this" challenge where Claude must recognize that the expression it wrote is not allowed in a guard
- Convert `&&`/`||` inside `when` to `and`/`or`

**Tier guidance**:
- 3 easy (apply guard for type check), 4 medium (negate-is-nil refactor), 4 hard (restricted-subset awareness), 2 legendary (`defguard` extraction with composability).

---

### Capability: `pipe-operator-flows`

**Description** (from README.md): Chaining transformations via `|>`; when to break the pipe.

**Known Claude failure modes**:
- [HIGH] Writes intermediate variable assignments instead of piping — `a = step1(input); b = step2(a); c = step3(b)`.
- [MED] Starts pipelines from a control structure (`case`, `if`) instead of a plain value — an official anti-pattern.
- [MED] Over-pipes: pipes a single call when a direct call is clearer.
- [MED] Doesn't know when to break the pipe for readability (when argument positioning gets awkward, when a `Enum.reduce` callback makes the chain hard to follow).
- [LOW] Wrong-argument-position piping (`|>` into a function that doesn't take its piped arg as first arg).

**Citations**:
- HiveOS 2026 Elixir AI review: *"AI tools can struggle with producing pipe-operator chains and pattern matching clauses that are idiomatic and readable. More specifically, AI tools have limited Elixir training data, resulting in more frequent hallucinations — generating nonexistent module functions, incorrect Ecto query syntax."* — https://hiveoscity.com/best/elixir/
- Zach Daniel on idiom transfer: *"LLMs are quite good at translation. Where they often fall down with invention, this kind of thing is their bread and butter."* — https://www.zachdaniel.dev/p/llms-and-elixir-windfall-or-deathblow (2025)
- MCP Market `elixir-essentials`: *"enforces the pipe operator (|>) for readable and maintainable function chaining"* — https://mcpmarket.com/tools/skills/elixir-essentials
- Thinking Elixir (pipe module): *"pipelines are usually best to start with a simple value rather than the result of something like a control structure, and using the pipe operator with complex starting expressions or control structures can hurt readability."* — https://thinkingelixir.com/course/code-flow/module-1/pipe-operator/
- georgeguimaraes `elixir-thinking`: *"Model as data + pattern matching + recursion"* — implicit pipe-centric composition rule. — https://github.com/georgeguimaraes/claude-code-elixir

**Suggested challenge angles**:
- Convert intermediate-variable chain into a pipeline
- "Don't pipe this": a single call that Claude should recognize is better left un-piped
- Pipe that starts from an `if`: refactor so the pipe starts from a value
- Pipe + `Enum.reduce` callback that's hard to read: break the pipe, extract a named helper
- Wrong-position argument: pipe into a function whose first arg is not the previous value — skill must use `then/2` or refactor

**Tier guidance**:
- 3 easy (variable-chain → pipe), 5 medium (pipe-break judgment), 4 hard (awkward-position fixes with `then/2`), 2 legendary (refactor so the first arg of each step is coherent with the pipe).

---

### Capability: `with-expressions`

**Description** (from README.md): Multi-step happy-path with `else` clause for error handling.

**Known Claude failure modes**:
- [HIGH] Uses nested `case` or nested `if` chains instead of `with` for multi-step happy-path flows.
- [HIGH] Produces `with` expressions with a single opaque `else` clause that flattens all possible errors — an official anti-pattern ("Complex else clauses in with").
- [MED] Uses `with` for single-step operations where a plain call suffices.
- [MED] Doesn't know that `with` stops at the first non-matching clause and falls through to `else` — writes redundant guard code.
- [MED] Fails to chain `{:ok, _}` / `{:error, _}` correctly through `with`.

**Citations**:
- d3ckard: Claude *"struggles with letting things crash and tends to silence things that should never fail silently"* — https://news.ycombinator.com/item?id=46752907 (2026)
- Elixir official anti-patterns (v1.20): *"Complex else clauses in with ... refers to `with` expressions that flatten all its error clauses into a single complex `else` block. This situation is harmful to the code readability and maintainability."* — https://hexdocs.pm/elixir/main/code-anti-patterns.html
- Elixir Streams (German Velasco): refactoring the "Complex else clauses in with" anti-pattern by extracting each step into separate helper functions with dedicated error handling. — https://www.elixirstreams.com/tips/complex_else_clauses_in_with_anti_pattern
- georgeguimaraes `elixir-thinking`: *"Use `with` for chaining `{:ok, _}` / `{:error, _}` operations"*, *"Avoid nested `case`—refactor to single `case`, `with`, or separate functions"*, and *"Prefer `with` when cases branch on nil: `with {:ok, %{recommendations: recs}} <- get_run(id), do: recs`"* — https://github.com/georgeguimaraes/claude-code-elixir
- lucasvegi/Elixir-Refactorings catalog: *"Pipeline using `with`"* and *"Remove redundant last clause in `with`"* are listed refactorings — https://github.com/lucasvegi/Elixir-Refactorings

**Suggested challenge angles**:
- Collapse three levels of nested `case` into a single `with`
- Refactor a "Complex else clauses in with" into per-step helpers
- Given a 4-step happy-path with intermediate validation, produce a `with` chain that short-circuits correctly
- Remove a redundant last `<-` clause from a `with`
- Rewrite an `if` ladder that's actually doing railway-oriented error handling into `with`

**Tier guidance**:
- 3 easy (nested-case → with), 5 medium (correct `else` clause shape), 4 hard (avoid complex-else anti-pattern while refactoring), 3 legendary (multi-step refactor that also preserves error provenance).

---

### Capability: `recursive-functions`

**Description** (from README.md): Tail recursion with pattern-matched base/step cases; replacing manual loops.

**Known Claude failure modes**:
- [HIGH] Reaches for `Enum.reduce` when explicit recursion is clearer (or vice versa — uses recursion when `Enum.reduce/3` would be better).
- [HIGH] Writes non-tail-recursive functions where the recursive call isn't in tail position, causing stack growth on large inputs.
- [MED] Gets base case wrong — uses `if` inside the function instead of a pattern-matched `[]` clause.
- [MED] Uses `list ++ [new]` in the recursive step (O(n) per step) instead of prepending to an accumulator and reversing at the end.
- [LOW] Paul Fedory: Claude "does not use recurse for lower order digits."

**Citations**:
- Paul Fedory: *"the map approach was undesirable ... does not use recurse for lower order digits ... creates 'data' as a separate entity that adds complexity"* — https://paulfedory.com/software/practicing-elixir-in-the-age-of-ai/ (2025)
- georgeguimaraes `elixir-thinking`: *"Prepend to lists `[new | list]` not `list ++ [new]`"* — https://github.com/georgeguimaraes/claude-code-elixir
- SmartLogic recursion basics: *"To write a recursive function, you want at minimum two things: a base case, and the recursive case."* — https://smartlogic.io/blog/elixir-recursion-basics/
- georgeguimaraes `elixir-thinking` philosophy: *"Model as data + pattern matching + recursion"* — explicit alternative to OOP class hierarchies. — https://github.com/georgeguimaraes/claude-code-elixir
- HN te_chris (same pain but recursion-adjacent): *"maybe_do_blah helper functions everywhere. 30 lines when 8 would do."* — https://news.ycombinator.com/item?id=46752907 (2026)

**Suggested challenge angles**:
- Convert a `Enum.reduce/3` that has awkward accumulator shape into an explicit recursive function
- Fix a non-tail-recursive function to be tail-recursive
- Refactor a `list ++ [x]` loop into `[x | acc]` prepend-then-reverse
- Given a manual index-counting loop, produce a `Enum.with_index/1` chain (go the other direction: recursion → Enum)
- Missing base case — produce the pattern-matched empty-list clause

**Tier guidance**:
- 3 easy (base + step recursive), 4 medium (tail-recursion rewrite), 4 hard (pick recursion vs Enum), 2 legendary (fix O(n²) list-append pattern while preserving semantics).

---

### Capability: `enum-vs-recursion-choice`

**Description** (from README.md): When `Enum.reduce/3` is right, when explicit recursion is right.

**Known Claude failure modes**:
- [MED] Reaches for `Enum.reduce` as a hammer — uses it for every transformation including single-element lookups where `Enum.find/2` or a specific pattern match is cleaner.
- [MED] Writes explicit recursion for problems where `Enum.map/2` or `Enum.reduce/3` would be clearer.
- [MED] Mixes `Enum` and `Stream` semantics — uses `Enum` where `Stream` is needed (lazy pipeline over large lists) or vice versa.
- [LOW] Uses `for` comprehensions where `Enum.map` is more idiomatic.

**Citations**:
- Rafael Antunes: *"Mastering Enum.map and Enum.reduce: The Two Functions Every Elixir Developer Should Know"* — framed as the core choice every Elixir dev faces. — https://rafaelantunes.com.br/blog/mastering-enum-map-and-reduce
- Thinking Elixir: *"Internally, reduce is implemented using the recursion pattern. So using reduce can be a handy shortcut!"* — https://thinkingelixir.com/course/code-flow/module-1/enum-part-2/
- Paul Fedory observation: the case where the model didn't use recursion when recursion was the right tool. — https://paulfedory.com/software/practicing-elixir-in-the-age-of-ai/
- HN alecco: *"Async or mildly complex thread stuff is like kryptonite for LLMs"* — tangentially related pain for higher-order-function judgment. — https://news.ycombinator.com/item?id=46752907

**Suggested challenge angles**:
- Given a `Enum.reduce` that's awkward, rewrite as explicit pattern-matched recursion
- Given explicit recursion that's long, rewrite as `Enum.reduce/3`
- Stream vs Enum: refactor a large-list pipeline to use `Stream` for laziness
- Comprehension vs Enum: when to prefer `for`
- Pick the right enumerable function — `Enum.map` vs `Enum.filter` vs `Enum.reject` vs `Enum.flat_map`

**Tier guidance**:
- 3 easy (correct Enum function pick), 4 medium (Stream vs Enum for large inputs), 3 hard (recursion ↔ Enum rewrite preserving semantics), 2 legendary (convert `for` + side effects into pure `Enum.reduce`).

**Note**: Evidence is **thinner** for this capability as a distinct Claude failure locus — it's mostly subsumed under the broader "imperative style" complaint.

---

### Capability: `map-and-struct-destructuring`

**Description** (from README.md): Extracting fields in function heads (`def update(%User{id: id} = user, attrs)`).

**Known Claude failure modes**:
- [HIGH] Uses `user.field` access inside the function body when the field was available in the function head — misses the `%User{id: id} = user` destructuring opportunity.
- [HIGH] Uses `map[:key]` dynamic access where `map.key` static access (or head destructuring) would be more assertive — official anti-pattern "Non-assertive map access."
- [MED] Uses `Map.get/2` with default where pattern-matching the key's absence in a separate function head would be clearer.
- [MED] Destructures in the function head but then re-accesses the field via `user.field` — redundant.
- [LOW] Over-destructures — extracts every field when only one is needed (complex-extractions anti-pattern).

**Citations**:
- Elixir official anti-patterns (v1.20): *"Non-assertive Map Access ... Using dynamic access notation (`map[:key]`) for keys that must exist obscures intent and delays error detection."* Recommended refactoring uses pattern matching: *"`def plot(%{x: x, y: y, z: z}), do: {x, y, z}`"* — https://hexdocs.pm/elixir/main/code-anti-patterns.html
- Elixir official anti-patterns: *"Complex extractions in clauses ... A possible solution is to extract only pattern/guard related variables in the signature once you have many arguments or multiple clauses."* — https://hexdocs.pm/elixir/main/code-anti-patterns.html
- Elixir Streams (German Velasco): *"Refactoring an anti-pattern: complex extractions in function heads"* — https://www.elixirstreams.com/tips/function_head_extraction_anti_pattern
- Dashbit (José Valim) on assertive code via pattern matching: *"With pattern matching, we are asserting that `String.split/2` is going to return a list with two elements."* — https://dashbit.co/blog/writing-assertive-code-with-elixir
- Alex66 (BoothIQ thread): style guide recommends avoiding *"defensive nil-checking"* in favor of letting code fail naturally. — https://elixirforum.com/t/150-000-lines-of-vibe-coded-elixir-the-good-the-bad-and-the-ugly/73899

**Suggested challenge angles**:
- Convert `user.field` access throughout a function body into head destructuring
- Convert `map[:key]` dynamic access into `map.key` or head destructuring (non-assertive map access refactor)
- Avoid the complex-extractions anti-pattern when refactoring a 3-arg function
- Pick the right destructuring depth: shallow (`%User{id: id}`) vs deep (`%User{role: %Role{perms: perms}}`)
- Decide when to bind-and-destructure (`%User{id: id} = user`) vs destructure-only

**Tier guidance**:
- 3 easy (simple head destructuring), 4 medium (decide what to destructure), 4 hard (avoid complex-extractions anti-pattern), 3 legendary (refactor 5+ call sites consistently).

---

### Capability: `binary-pattern-matching-basic`

**Description** (from README.md): `<<"prefix", rest::binary>>` patterns for string parsing.

**Known Claude failure modes**:
- [MED] Uses `String.slice/2` or `String.starts_with?/2` + `String.slice` combos where a `<<"prefix", rest::binary>>` pattern would be simpler.
- [MED] Uses `Regex.run/2` where binary pattern matching would suffice for fixed-prefix parsing.
- [LOW] Does not know the `<<head::utf8, rest::binary>>` pattern for multi-byte character boundaries.
- [LOW] Doesn't use binary size modifiers (`<<head::binary-size(4), rest::binary>>`) for fixed-length parsing.

**Citations**:
- HiveOS 2026: *"AI tools have limited Elixir training data, resulting in more frequent hallucinations — generating nonexistent module functions, incorrect Ecto query syntax, or Phoenix routes that don't match the framework's conventions."* — https://hiveoscity.com/best/elixir/
- Ben Marx: *"Binary pattern matching is one of Elixir's superpowers. It lets you declaratively describe binary formats and extract data in a single expression."* — https://bgmarx.com/2015/06/12/binary-pattern-matching-with-elixir/
- Official Elixir docs (binaries, strings, charlists): using the utf8 modifier `<<x::utf8, rest::binary>> = "über"` is crucial for multi-byte characters. — https://hexdocs.pm/elixir/binaries-strings-and-charlists.html
- SmartLogic: *"binary pattern matching in Elixir is used for network protocols, file parsing, and embedded systems work."* — https://smartlogic.io/blog/binary-pattern-matching-in-elixir/

**Suggested challenge angles**:
- Refactor a `String.starts_with?/2` + `String.slice/3` combo into `<<"prefix", rest::binary>>`
- Parse a fixed-format header (version + length + payload) using binary size modifiers
- Refactor `Regex.run/2` with a simple prefix pattern into binary matching
- Multi-byte-safe refactor using `::utf8` modifier
- Extract variable-length field followed by binary payload

**Tier guidance**:
- 2 easy (prefix match), 3 medium (size-modifier parse), 3 hard (utf8-safe), 2 legendary (Regex → binary-match with performance-preserving semantics).

**Note**: Evidence is **thin** for this capability as a documented Claude failure locus. The general "limited training data" complaint applies, but no specific user complaints were found about Claude mishandling binary pattern matching. Challenges here should lean on standard Elixir idiom-correctness checks rather than specific Claude bug reports.

---

### Capability: `cond-and-if-reduction`

**Description** (from README.md): Collapsing conditionals into pattern matches.

**Known Claude failure modes**:
- [HIGH] Produces `cond do` blocks where multi-clause function heads or `case` would be more idiomatic.
- [HIGH] Writes nested `if/else` ladders that could be a flat `cond` or, better, multi-clause function heads with guards.
- [HIGH] Converts a pattern-matching situation to a truthiness check inside `if` — loses exhaustiveness checking.
- [MED] Leaves `true ->` fallback clauses in `cond` where a proper pattern match would make the exhaustion explicit.
- [MED] Doesn't reach for `unless` or `if`-with-early-return style that's more natural in Elixir than in Ruby.

**Citations**:
- *"`case functioncall() do nil -> ... end` instead of idiomatic `if var = functioncall() do else`"* — dnautics, https://news.ycombinator.com/item?id=46752907 (2026)
- Nick Janetakis refactoring guide: three-pass evolution from nested `if` → `cond` → multi-clause function heads. *"Pattern matching creates a more ordered view of the 3 cases... much more readable and glanceable because conditional logic separates from function purpose."* — https://nickjanetakis.com/blog/refactoring-elixir-code-if-cond-and-pattern-matching
- Elixir Forum: *"Writing conditional code is not exactly idiomatic in a high-level functional language such as Elixir. Using a combination of pattern matching and syntax rules, you can write extremely clean code free of if statements and conditionals in general."* — https://elixirforum.com/t/coding-with-llms-conventions-md-for-elixir-do-you-have-your-own-what-does-it-contain/69677
- Alex66: *"Still correcting if/else chains that should be pattern matches."* — https://elixirforum.com/t/150-000-lines-of-vibe-coded-elixir-the-good-the-bad-and-the-ugly/73899
- lucasvegi/Elixir-Refactorings: includes *"Transform 'if' statements using pattern matching into a 'case'"* and *"Transform nested 'if' statements into a 'cond'"* — https://github.com/lucasvegi/Elixir-Refactorings

**Suggested challenge angles**:
- Collapse a 3-level nested `if` into a `case` with guards, then into function heads
- Refactor a `cond do` with `true ->` fallback into an exhaustive function-head set
- The dnautics anti-pattern: `case x do nil -> ... end` → `if var = x do ... end` when binding-and-checking
- Refactor `unless x do ... else ... end` (the official "Non-assertive truthiness" anti-pattern direction)
- Distinguish when a problem is genuinely a truthiness check vs a pattern match

**Tier guidance**:
- 4 easy (nested `if` → `cond` or `case`), 4 medium (cond → function heads), 4 hard (decide when `cond` is still the right shape), 3 legendary (handle the dnautics `if var = ...` idiom where binding happens inside the conditional).

---

### Capability: `defensive-nil-checks-elimination`

**Description** (from README.md): Replacing `if is_nil(x)` chains with pattern matching.

**Known Claude failure modes**:
- [HIGH] Writes `if is_nil(user) do ... else ... end` — the single most-cited specific complaint.
- [HIGH] Adds "defensive" nil checks to functions whose contract guarantees non-nil input — pollutes call sites with noise.
- [HIGH] Produces `maybe_do_*` helper functions that wrap every call in a nil check.
- [MED] Uses `&&` / `||` for nil-defaulting (`value = input && input.field`) — obscures return types.
- [MED] Chains `if is_nil/1` checks through a function where a single pattern-matched head with `nil` would be cleaner.
- [MED] Uses `case functioncall() do nil -> ... end` instead of `if var = functioncall() do else`.

**Citations**:
- **Top-cited Claude Elixir complaint** — BoothIQ: *"Claude writes Ruby-style Elixir — if/then/else chains, defensive nil-checking, early returns that don't make sense in a functional context."* — https://getboothiq.com/blog/150k-lines-vibe-coded-elixir-good-bad-ugly
- te_chris: *"The imperative thing is so frustrating. Even the latest models still write elixir like a JS developer, checking nils, maybe_do_blah helper functions everywhere. 30 lines when 8 would do."* — https://news.ycombinator.com/item?id=46752907 (2026)
- dnautics: *"Claude has some bad habits... like doing `case functioncall() do nil -> ... end` instead of `if var = functioncall() do else`"* — https://news.ycombinator.com/item?id=46752907 (2026)
- georgeguimaraes `elixir-thinking`: *"Avoid `value && value.field` nil-punning—obscures actual return types"*. *"Use `/3` variants (`Keyword.get/3`, `Map.get/3`) instead of case statements branching on nil."* *"Prefer `with` when cases branch on nil: `with {:ok, %{recommendations: recs}} <- get_run(id), do: recs`"* — https://github.com/georgeguimaraes/claude-code-elixir
- Credo `NegatedIsNil`: *"avoid negating the is_nil predicate function ... refactor to either match on nil cases directly or match on what you were expecting."* — https://hexdocs.pm/credo/Credo.Check.Refactor.NegatedIsNil.html

**Suggested challenge angles**:
- Convert `if is_nil(user) do ... else ... end` into two function heads — one for `nil`, one for `%User{}`.
- Convert `case functioncall() do nil -> ...; val -> ... end` into `if var = functioncall() do val_branch else nil_branch end`.
- Remove `maybe_do_*` helper wrapper where pattern-matched heads eliminate the need.
- Refactor `&&`/`||` nil-punning into explicit pattern match with default in a function head.
- Remove defensive nil checks from a function whose upstream contract guarantees non-nil — explain the removal.
- Replace `Map.get(map, :k)` + nil check with `Map.get(map, :k, default)` or `with {:ok, val} <- Map.fetch(map, :k)`.

**Tier guidance**:
- 4 easy (straightforward `is_nil` removal), 5 medium (multi-point nil pollution cleanup), 4 hard (decide when defensive checking is warranted — at system boundaries), 3 legendary (refactor a file where defensive nil permeates 10+ call sites).

---

## Research process notes

Searches targeted five strata: (1) the top-cited vibe-coding post-mortem (BoothIQ) and its HN/Elixir Forum discussion threads; (2) the two widely-shared Claude Code Elixir plugins (`oliver-kriska/claude-elixir-phoenix` and `georgeguimaraes/claude-code-elixir`), which act as iron-law catalogs where each enforced rule is a de facto observed-bug report; (3) the official Elixir anti-patterns guide (v1.20), which is the authoritative source for the direction a refactor should *not* go; (4) community refactoring catalogs (lucasvegi/Elixir-Refactorings, Nick Janetakis's blog, Elixir Streams); and (5) single-author observations on 2025 LLM Elixir output (Paul Fedory, Zach Daniel, Dashbit). The BoothIQ + HN quotes are the densest source of developer-verbatim pain-point narratives; the plugin repos are the densest source of concrete behavioral rules. Where a skill's rule exists in the plugin but lacks a matching Elixir Forum / HN complaint, it was still included as corroborating evidence because the rule exists *because* the plugin author observed Claude failing at it — the plugin is functionally a crowd-sourced bug report.

Two capabilities have noticeably thinner public evidence than the rest: `binary-pattern-matching-basic` (no specific Claude complaint locus — generic "limited training data" only) and `enum-vs-recursion-choice` (subsumed under the broader imperative-style complaint, rarely surfaced as a distinct failure mode). These should still be populated with challenges, but leaning on Elixir-idiom correctness rather than Claude-specific failure modes. Conversely, `defensive-nil-checks-elimination`, `function-head-pattern-matching`, `cond-and-if-reduction`, and `with-expressions` have the richest evidence — multiple independent developer complaints plus plugin iron laws plus official anti-patterns documentation.

One methodological note: the Elixir Forum "LLMs writing Elixir" thread (#66465) had lighter pain-point density than expected — hubertlepicki was the only commenter with a specific complaint (syntax errors, hallucinated stdlib calls). Most Elixir Forum discussion is positive-leaning and focused on *how to use* AI, not *what it does wrong*. The negative signal is concentrated in the BoothIQ HN thread and in the plugin repos.

## Capability prioritization (Phase 2 output)

| Capability | Evidence strength | Recommended primary count | Rationale |
|---|---|---|---|
| `refactor-philosophy` (foundation) | HIGH | 14 | Foundation dim; needs coverage of both "refactor" and "don't-over-refactor" sides. |
| `function-head-pattern-matching` | HIGH | 16 | The single most-cited Claude Elixir failure — both plugins ship explicit rules, 3+ direct developer complaints. Top-tier priority. |
| `guard-clauses` | MED-HIGH | 13 | Credo has a dedicated check; official anti-patterns touches it; plugin rules. Rich enough for 13 challenges. |
| `pipe-operator-flows` | MED | 13 | Rich capability per README; moderate evidence (HiveOS, Thinking Elixir guidance, plugin rules). |
| `with-expressions` | HIGH | 15 | Official anti-pattern (Complex else clauses in with) + plugin rules + multiple refactoring catalog entries. |
| `recursive-functions` | MED | 13 | Specific evidence exists (Paul Fedory, `list ++ [x]` rule) plus general recursion-idiom guidance. |
| `enum-vs-recursion-choice` | LOW-MED | 12 | Thinner distinct evidence but high implicit coverage under imperative-style complaint. |
| `map-and-struct-destructuring` | MED-HIGH | 14 | Official "Non-assertive map access" anti-pattern + complex-extractions anti-pattern + Valim assertive-code framing. |
| `binary-pattern-matching-basic` | LOW | 12 | Thinnest evidence for this capability — general limited-training-data complaint only. Lower bound. |
| `cond-and-if-reduction` | HIGH | 16 | Single specific complaint (dnautics) + general pain + plugin rules + official anti-pattern + Nick Janetakis refactoring guide. Top-tier. |
| `defensive-nil-checks-elimination` | HIGH | 16 | Highest-density specific evidence — BoothIQ, te_chris, dnautics, plugin rules, Credo, anti-patterns guide. |

Total primary-tagged: ~154 (slight over-target to absorb variance; drafting agent can drop 4 to hit ~150).

## Capabilities with insufficient public failure documentation

- **`binary-pattern-matching-basic`**: no public source surfaces a Claude-specific failure in binary pattern matching. The general "AI tools have limited Elixir training data" complaint from HiveOS applies, but no developer has written "Claude got my binary pattern wrong" in a public forum. Challenges here should rely on Elixir-idiom correctness (matching reference solutions) rather than mirroring documented bugs. Recommend lower-bound challenge count (12) and keep legendary tier count low.
- **`enum-vs-recursion-choice`**: the tradeoff is recognized in the community but not surfaced as a distinct Claude failure. Paul Fedory's observation (Claude didn't use recursion when it should have) is the closest, but it's one data point. Include at lower-bound count (12) and skew toward recognition-of-idiom challenges rather than fault-correction.
