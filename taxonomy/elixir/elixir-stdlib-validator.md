# elixir-stdlib-validator

**Rank**: #11 of 22
**Tier**: B (valuable, moderate evidence)
**Taxonomy path**: `code-quality` / `refactoring` / `elixir`
**Status**: 🆕 NEW from research — runner-up; may be better solved as a tool hook

## Specialization

Targets Claude's tendency to hallucinate Elixir standard library calls: confusing `Enum` vs `List` modules, calling functions that don't exist (e.g., `Enum.flatten_map/2`), inventing keywords (`elsif`), and mixing up `String` vs `Binary` module functions. The skill teaches Claude to verify module/function existence before calling.

## Why LLMs struggle

Three sources cite this:

> *"hallucinates on occasion, by suggesting function calls to modules from stdlib that are not there, or are in a different variant or different module (like Enum vs List)"*
> — hubertlepicki, [Elixir Forum](https://elixirforum.com/t/current-status-of-llms-writing-elixir-code/66465)

> *"Invented `elsif` syntax multiple times in Elixir code"*
> *"Produces 'Java annotations as Elixir module attributes' when confused"*
> — [HN thread](https://news.ycombinator.com/item?id=46752907)

The Elixir stdlib has a few "trap" pairs: `Enum`/`List`, `Map`/`Keyword`, `String`/`Binary`. Functions exist in one but not the other, with subtly different semantics.

## Decomposition

### Foundation
- **F: `validation-approach`** — Compile-time vs runtime vs CI-checked validation. Variants determine when the validation kicks in (during code generation vs during a CI step vs at compile time).

### Capabilities
1. **C: `enum-vs-list-module-choice`** — `Enum.map/2` operates on enumerables; `List.map/2` doesn't exist; when each is appropriate
2. **C: `string-vs-binary-module-choice`** — `String.length/1` (graphemes) vs `byte_size/1` (bytes); when each applies
3. **C: `map-vs-keyword-module-choice`** — Structural differences, ordering guarantees, key types
4. **C: `module-existence-verification`** — `Code.ensure_loaded?/1`, `function_exported?/3`
5. **C: `function-arity-verification`** — Checking `function_exported?(Mod, :fun, arity)` with the correct arity
6. **C: `version-specific-apis`** — `@since` tags, `Version.match?/2`, handling library version differences

### Total dimensions
**7** = 1 foundation + 6 capabilities

## Evaluation criteria sketch

- **Hallucination detection test**: present code calling `Enum.flatten_map/2` (doesn't exist); skill should identify and fix
- **Module choice test**: code that calls `String.length/1` on a binary that may contain non-graphemes; identify the bug
- **Compile test**: every challenge runs `mix compile --warnings-as-errors` against the output; any "function does not exist" warning is a fail

## Evidence

- [Research report Part 1 #6](../../docs/research/elixir-llm-pain-points.md#6-hallucinated-apis--invented-syntax)
- [Elixir Forum: Current status of LLMs writing Elixir code](https://elixirforum.com/t/current-status-of-llms-writing-elixir-code/66465)

## Notes

- **Best alternative might be a tool hook** — a pre-write check that runs `mix compile` and rejects code that emits "function does not exist" warnings. That solves the problem without a skill.
- If built as a skill, it's the most narrowly-scoped of the Elixir families. 6 capabilities is the lower end.
- Could be merged with `elixir-pattern-match-refactor` as a "code quality" mega-family covering both idiom and existence concerns.
