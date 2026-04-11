# elixir-ecto-query-writer

**Rank**: #4 of 22
**Tier**: S (must-have, strongest evidence)
**Taxonomy path**: `data` / `ecto-queries` / `elixir`
**Status**: ✅ Validated by research — multiple plugin-enforced bug patterns

## Specialization

Writes idiomatic `Ecto.Query` expressions from plain-English query descriptions: joins, preloads, subqueries, aggregates, window functions, dynamic conditional filters via `Ecto.Query.dynamic/2`, pagination, and the `^` pin operator for safe variable interpolation.

## Why LLMs struggle

Ecto's macro-based query DSL is unique — it doesn't behave like SQL strings, ActiveRecord chains, or Django's ORM. Claude defaults to patterns from those other frameworks, producing queries that are either inefficient (wrong preload strategy), unsafe (missing pin operator → unintended variable capture), or simply wrong (raw SQL strings via `Ecto.Adapters.SQL.query`).

Specific failure modes from the research:
- **Missing pin operator (`^`)**: `where: u.id == user_id` instead of `where: u.id == ^user_id` — without the pin, Ecto treats `user_id` as a binding name (silent bug)
- **Wrong preload strategy**: using `join` preloads on `has_many` associations consumes ~10× more memory than struct preloads
- Falling back to raw SQL via `Ecto.Adapters.SQL.query/3` instead of composing query macros
- Trying to chain methods like Rails (`User.where(...).where(...)`) — Ecto uses pipe + macro composition
- Mishandling `dynamic/2` for runtime-conditional filters

## Decomposition

### Foundation
- **F: `query-composition-style`** — How the skill teaches query composition: pipe-heavy (`Query |> where(...) |> where(...)`), keyword-heavy (`from u in User, where: ..., where: ...`), or schema-macro-driven (encapsulating queries inside the schema module). Variants determine the canonical form for every capability.

### Capabilities
1. **C: `basic-where-select-order`** — The foundational query shape; `where`, `select`, `order_by`, `limit`, `offset`
2. **C: `joins`** — `inner_join`, `left_join`, `full_join`, `cross_join`, `as: :alias_name` for named bindings
3. **C: `preloads`** — Struct preloads (separate query) vs join preloads (single query); when each is appropriate; N+1 avoidance
4. **C: `aggregates-and-group-by`** — `count`, `sum`, `avg`, `max`, `min`, `group_by`, `having`
5. **C: `subqueries`** — `subquery/1`, correlated vs uncorrelated, exists/in/any patterns
6. **C: `dynamic-query-builder`** — `Ecto.Query.dynamic/2` for runtime-conditional filters; composing dynamics
7. **C: `pin-operator-safety`** ⭐ — `^` for interpolating variables; **required** for safety; the most common Claude bug
8. **C: `pagination-patterns`** — Offset-based vs cursor-based; tradeoffs and edge cases
9. **C: `raw-sql-fragment`** — When `fragment/1` is necessary as an escape hatch; safe vs unsafe interpolation
10. **C: `window-functions`** — `row_number`, `rank`, `lag`, `lead`, `partition_by`
11. **C: `upserts-and-on-conflict`** — `insert_all` with `on_conflict: :replace_all` / `:nothing` / replace lists

### Total dimensions
**12** = 1 foundation + 11 capabilities

## Evaluation criteria sketch

- **Pin operator test**: write a query that filters by an external variable; score.py checks for `^` presence
- **Preload strategy test**: load 1000 users with their 50000 posts; verify struct preloads (not join preload) used; measure memory if possible
- **Dynamic query test**: build a search endpoint with 5 optional filters using `dynamic/2`
- **Subquery test**: find users whose latest post was within the last 7 days
- **Aggregate test**: top-N users by total comment count with the count as a virtual field
- **Pagination test**: implement cursor-based pagination over an ordered feed

## Evidence

- [Research report Part 1 #9](../../docs/research/elixir-llm-pain-points.md#9-missing-pin-operator--in-ecto-queries) — pin operator
- [Research report Part 1 #10](../../docs/research/elixir-llm-pain-points.md#10-wrong-preload-strategy-join-preload-on-has_many) — preload strategy
- [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix) — pin operator iron law
- [georgeguimaraes/claude-code-elixir ecto-thinking](https://github.com/georgeguimaraes/claude-code-elixir) — preload strategy iron law

## Notes

- The pin operator capability is the **highest-confidence single fix** in the entire Elixir roster. Adding `^` reliably prevents a real bug class.
- Preload strategy depends on data shape — sometimes join preloads ARE the right call. The capability should teach the decision criteria, not the dogma.
- Closely linked to `elixir-ecto-schema-changeset` — queries reference schemas; both families need to agree on naming conventions.
