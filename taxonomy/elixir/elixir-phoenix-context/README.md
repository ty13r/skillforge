# elixir-phoenix-context

**Rank**: #14 of 22
**Tier**: D (DROPPED — zero developer evidence)
**Taxonomy path**: `development` / `phoenix-framework` / `elixir`
**Status**: ❌ NOT validated by research — no specific complaints about context module authoring

## Specialization

Generates Phoenix context modules (the "service layer") with the standard public API (`list_*`, `get_*`, `get_*!`, `create_*`, `update_*`, `delete_*`), Ecto wiring, changeset helpers, and `Phoenix.PubSub` broadcasts for real-time updates.

## Why this family was DROPPED

The research found **zero specific developer complaints** about Phoenix context module authoring. The closest mention was a "cross-context belongs_to" warning in plugin docs, but that's an Ecto association issue, not a context structure issue.

Compare to the families we kept:
- `elixir-phoenix-liveview`: 5+ specific failure modes documented
- `elixir-ecto-sandbox-test`: explicitly named "the ugly" in BoothIQ
- `elixir-security-linter`: entire plugin enforcement tier

This family doesn't meet the evidence bar for active inclusion. **Removed from the recommended top-10 roster** in favor of `elixir-ecto-sandbox-test`.

## Decomposition (preserved for reference)

### Foundation
- **F: `context-boundary-philosophy`** — Tall vs wide contexts; context as bounded context vs CRUD service

### Capabilities
1. **C: `crud-api-conventions`** — `list_/get_/get_!/create_/update_/delete_` naming + return shapes
2. **C: `ecto-wiring`** — Repo access patterns, preloading, returning `{:ok, _}` / `{:error, changeset}`
3. **C: `pubsub-broadcasts`** — Broadcasting create/update/delete for live updates
4. **C: `changeset-helpers`** — Exposing `change_*/2` for form rendering
5. **C: `cross-context-communication`** — When one context calls another; tradeoffs
6. **C: `ets-caching-layer`** — Optional in-memory caching inside contexts

### Total dimensions
**7** = 1 foundation + 6 capabilities

## Evidence (or lack thereof)

- [Research report Part 2 — verdict #7](../../docs/research/elixir-llm-pain-points.md#part-2--validation-verdicts-on-the-original-10-candidate-families)

## Notes

- **DROPPED from active roster.** Use `elixir-ecto-sandbox-test` (#2) in its place.
- This family file is preserved in the taxonomy for reference. If future research surfaces real evidence, it can be re-promoted.
- Context structure is something Phoenix devs mostly get right because the Phoenix generators (`mix phx.gen.context`) produce conventional output that Claude has seen plenty of in training. The pain isn't here.
