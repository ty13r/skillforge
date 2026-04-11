# elixir-pattern-match-refactor

**Rank**: #7 of 22
**Tier**: A (high-value, good evidence)
**Taxonomy path**: `code-quality` / `refactoring` / `elixir`
**Status**: ✅ Validated by research — most-cited complaint, though lowest severity

## Specialization

Takes non-idiomatic Elixir code (imperative if/else chains, `case` with `==`, defensive nil checks, manual loops with accumulators) and refactors it to use function head pattern matching, guard clauses, the pipe operator, `with` expressions, and recursive functions with pattern-matched base/step cases.

## Why LLMs struggle

The most-cited Elixir complaint in the research, with 5+ independent sources. Severity is moderate (idiom nits, not data corruption) but pervasiveness is high. Claude defaults to Python/Ruby/Java imperative style:

- *"Claude writes Ruby-style Elixir — if/then/else chains, defensive nil-checking, early returns that don't make sense in a functional context."* — BoothIQ
- *"writes Java even if it's Elixir"* — troupo, HN
- *"`case functioncall() do nil -> ... end` instead of idiomatic `if var = functioncall() do`"* — dnautics, HN

The skill takes this code and produces idiomatic equivalents.

## Decomposition

### Foundation
- **F: `refactor-philosophy`** — How aggressively the skill rewrites: in-place edits (preserve structure, change idioms), extract-functions (pull conditional branches into separate function heads), pipe-first rewrite (rebuild around `|>`). Variants determine the canonical "after" shape.

### Capabilities
1. **C: `function-head-pattern-matching`** — Replacing `case` chains with multiple function heads
2. **C: `guard-clauses`** — `when` clauses, what's allowed in guards (limited subset of Elixir), composition with `and`/`or`
3. **C: `pipe-operator-flows`** — Chaining transformations via `|>`; when to break the pipe
4. **C: `with-expressions`** — Multi-step happy-path with `else` clause for error handling
5. **C: `recursive-functions`** — Tail recursion with pattern-matched base/step cases; replacing manual loops
6. **C: `enum-vs-recursion-choice`** — When `Enum.reduce/3` is right, when explicit recursion is right
7. **C: `map-and-struct-destructuring`** — Extracting fields in function heads (`def update(%User{id: id} = user, attrs)`)
8. **C: `binary-pattern-matching-basic`** — `<<"prefix", rest::binary>>` patterns for string parsing
9. **C: `cond-and-if-reduction`** — Collapsing conditionals into pattern matches
10. **C: `defensive-nil-checks-elimination`** — Replacing `if is_nil(x)` chains with pattern matching

### Total dimensions
**11** = 1 foundation + 10 capabilities

## Evaluation criteria sketch

Each challenge presents a piece of non-idiomatic Elixir code and asks the skill to refactor it. The score.py runs:

- AST analysis to count `if` / `case` / `cond` constructs (fewer is better, all else equal)
- Function head count (more heads = more pattern matching usage)
- Pipe operator usage in transformation flows
- Whether the refactored code still compiles and passes the original test cases

Concrete challenges:
- **Case-to-function-heads**: refactor a `case user.role do "admin" -> ...` into multiple function heads with guards
- **Imperative-to-pipeline**: rewrite a 30-line manual loop with accumulator into a `|>` pipeline
- **Nested-if elimination**: collapse 3 levels of nested `if`s into a `with` expression with proper error handling
- **Defensive nil removal**: convert `if is_nil(user) do ... else ... end` patterns into function head pattern matching
- **Recursive base case**: refactor an `Enum.reduce` into an explicit recursive function

## Evidence

- [Research report Part 1 #1](../../docs/research/elixir-llm-pain-points.md#1-rubyjava-style-imperative-code-instead-of-pattern-matching) — 5+ sources
- [BoothIQ post-mortem](https://getboothiq.com/blog/150k-lines-vibe-coded-elixir-good-bad-ugly)
- [HN thread](https://news.ycombinator.com/item?id=46752907)

## Notes

- This is the **most common complaint** but the **lowest severity** — don't over-prioritize it. The data says skills with hard correctness bugs (#3 sandbox, #5 float-money, #8 security) should ship before this one.
- Closely linked to `elixir-error-tuple-handler` — `with` expressions are the bridge between pattern matching and error handling.
- The challenge pool should include "before/after" pairs where the "before" is real Claude output observed in the wild, not synthesized examples. The plugin repos have many such examples.
