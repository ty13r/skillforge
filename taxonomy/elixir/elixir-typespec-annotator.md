# elixir-typespec-annotator

**Rank**: #15 of 22
**Tier**: D (DROPPED — zero AI-related evidence)
**Taxonomy path**: `code-quality` / `type-annotations` / `elixir`
**Status**: ❌ NOT validated by research — Dashbit evidence suggests Claude already handles this adequately

## Specialization

Adds `@spec`, `@type`, `@opaque`, `@callback`, and `@behaviour` annotations to existing Elixir modules so they pass Dialyzer cleanly. Covers basic types, union types, keyword lists, options, maps, structs, and protocol/behaviour callbacks.

## Why this family was DROPPED

The research found **no developer complaints** about missing or wrong typespecs in AI-generated Elixir. Dashbit's positive coverage of Dialyzer + AI suggests Claude is already decent at this:

> *"Why Elixir is the best language for AI"* — [Dashbit blog](https://dashbit.co/blog/why-elixir-best-language-for-ai)

Building a family without evidence is a waste of authoring effort. **Removed from the recommended top-10 roster** in favor of `elixir-security-linter`.

## Decomposition (preserved for reference)

### Foundation
- **F: `typespec-strictness`** — Aggressive vs relaxed; how strict the Dialyzer-clean bar is

### Capabilities
1. **C: `basic-specs`** — `@spec`, arity matching, arrow syntax `(args) :: return`
2. **C: `type-aliases-and-opaque`** — `@type`, `@opaque`, `@typep`
3. **C: `callbacks-for-behaviours`** — `@callback`, `@macrocallback`
4. **C: `union-and-structured-types`** — `t1 | t2`, `%{key: type}`, struct types
5. **C: `protocol-typespecs`** — Spec'ing protocol implementations
6. **C: `dialyzer-warning-resolution`** — Common warnings and fixes (`no_return`, `pattern_no_match`)

### Total dimensions
**7** = 1 foundation + 6 capabilities

## Evidence (or lack thereof)

- [Research report Part 2 — verdict #10](../../docs/research/elixir-llm-pain-points.md#part-2--validation-verdicts-on-the-original-10-candidate-families)
- [Dashbit: Why Elixir is the best language for AI](https://dashbit.co/blog/why-elixir-best-language-for-ai)

## Notes

- **DROPPED from active roster.** Use `elixir-security-linter` (#3) in its place.
- This family file is preserved in the taxonomy for reference. If future research surfaces real evidence (e.g., a wave of Claude-generated Elixir code with bad typespecs causing Dialyzer regressions), it can be re-promoted.
- Typespecs are an area where Elixir's culture (Dialyzer is rare in practice, Hex packages don't enforce specs) and AI handling intersect well. Probably not worth dedicated optimization.
