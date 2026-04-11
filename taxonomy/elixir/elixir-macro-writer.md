# elixir-macro-writer

**Rank**: #19 of 22
**Tier**: E (brainstormed runner-up; no research signal)
**Taxonomy path**: `development` / `meta-programming` / `elixir`
**Status**: Brainstormed; advanced escape hatch

## Specialization

Writes Elixir macros: `defmacro`, `quote`/`unquote`, AST manipulation via `Macro.postwalk/2` and `Macro.prewalk/2`, macro hygiene rules, `__using__/1` patterns, `@before_compile`, `@after_compile`, and compile-time code generation.

## Why this family is here

Macros are Elixir's escape hatch for code that needs to manipulate the AST. They're the source of significant complexity in many libraries (Ecto, Phoenix, Plug all use macros heavily). LLMs really struggle with macros because the mental model (data is code is data) is unusual and the training corpus is small. But the audience is small — most Elixir developers should NOT be writing macros, they should be using the macros others wrote.

The research found **no specific macro-related Claude failures**, possibly because most developers don't try to ask Claude to write macros in the first place.

## Decomposition

### Foundation
- **F: `macro-philosophy`** — Hygiene-first vs minimal-rewriting; "is this even a macro" detection

### Capabilities
1. **C: `quote-and-unquote`** — AST construction basics
2. **C: `ast-manipulation`** — `Macro.postwalk/2`, `Macro.prewalk/2`, pattern matching on AST
3. **C: `macro-hygiene`** — `var!/1`, `bind_quoted`, variable capture rules
4. **C: `use-macro-patterns`** — `__using__/1`, `@before_compile`, `@after_compile`
5. **C: `compile-time-code-generation`** — Generating functions from data structures
6. **C: `macro-debugging`** — `Macro.to_string/1`, `Code.format_string!/1`, expanding macros manually

### Total dimensions
**7** = 1 foundation + 6 capabilities

## Notes

- Most Elixir developers should never write macros. The "smell detection" foundation (this isn't a macro problem) might be more valuable than the authoring capabilities.
- Lowest priority of all 22 families. Build only if a macro-heavy library author specifically requests SKLD support.
