# elixir-phoenix-liveview

**Rank**: #1 of 22
**Tier**: S (must-have, strongest evidence)
**Taxonomy path**: `development` / `phoenix-framework` / `elixir`
**Status**: ✅ Validated by research — strongest evidence base in the Elixir roster

## Specialization

Writes modern Phoenix 1.7+ LiveView modules and components using function components, Verified Routes (`~p` sigil), streams, core_components, and the modern `handle_event` / `handle_info` patterns. Specifically targets the Phoenix 1.7 idioms that are missing from the bulk of LLM training data, which is heavily 1.6-era.

## Why LLMs struggle

Phoenix 1.7 changed significantly — function components, Verified Routes, streams, and `to_form/2` all replaced or evolved earlier patterns. The training corpus is mostly pre-1.7. LLMs default to `live_link` (removed), string-interpolated routes (replaced by `~p`), the old `live_redirect` (replaced by `push_navigate`), and `<%= for ... %>` instead of `:for`. Plugin authors have built explicit "iron law" catalogs to enforce the new patterns because Claude reverts to old ones repeatedly.

Specific reported failure modes (from `docs/research/elixir-llm-pain-points.md`):
- **"NO DATABASE QUERIES IN MOUNT"** — Claude routinely puts DB queries in `mount/3`, which runs twice (disconnected + connected).
- **`assign_new` silently skips on reconnect** — Claude uses it for things that need to be freshly computed.
- Missing `connected?(socket)` checks before `Phoenix.PubSub.subscribe/2`.
- Failing to use `stream/3` for lists >100 items, defaulting to `assign/3`.
- Forgets the `phx-change="validate"` → re-run-changeset → `to_form` cycle.
- Butchers `<.inputs_for>` for nested forms.

## Decomposition

### Foundation
- **F: `architectural-stance`** — How the skill decomposes responsibility across LiveView module ↔ LiveComponent ↔ function components ↔ Phoenix context. Variants: strict-LiveView, component-heavy, context-thin. Locks in vocabulary for every capability below.

### Capabilities
1. **C: `heex-and-verified-routes`** — HEEx syntax (`:if`, `:for`, `:let`), `~p` sigil for routes, attribute interpolation
2. **C: `function-components-and-slots`** — `attr` declarations, `slot` declarations, `inner_block`, named slots, composition
3. **C: `live-components-stateful`** — When to use `LiveComponent` (stateful) vs function component (stateless), `handle_event` in components
4. **C: `form-handling`** — `to_form/2`, `<.form>`, `<.input>`, `<.inputs_for>`, validation feedback via `phx-change`, server-side validation
5. **C: `streams-and-collections`** — `stream/3`, `stream_insert/3`, `stream_delete/3`, `dom_id`, large collection performance
6. **C: `mount-and-lifecycle`** — `mount/3` vs `handle_params/3`, `connected?/1` checks, `assign_new/3` gotcha, `temporary_assigns`
7. **C: `event-handlers-and-handle-info`** — `phx-click` / `phx-submit` / `phx-change` / `phx-focus`, `handle_info/2` for external messages
8. **C: `pubsub-and-realtime`** — Subscribe on connected mount, topic namespacing, broadcast filtering, unsubscribe semantics
9. **C: `navigation-patterns`** — `push_navigate` vs `push_patch` vs `redirect` vs `<.link>`; live_session boundaries
10. **C: `auth-and-authz`** — `on_mount` hooks for authentication, per-`handle_event` authorization checks
11. **C: `anti-patterns-catalog`** ⭐ — Explicit iron-law catalog teaching what NOT to do (no DB in mount, connected? before subscribe, no float for money in displayed values, etc.)

### Total dimensions
**12** = 1 foundation + 11 capabilities

## Evaluation criteria sketch

The challenge pool (50 challenges) should include at minimum:
- **Structural decomposition tests**: build a multi-step wizard, build a paginated table — measures `architectural-stance`
- **Markup tests**: navigation bars with dynamic routes, conditional rendering — measures `heex-and-verified-routes`
- **Form tests**: contact form, nested invoice form, async validation — measures `form-handling`
- **Stream tests**: 10k-message inbox, append-on-broadcast — measures `streams-and-collections`
- **Lifecycle tests**: URL-param-driven LiveView, reconnect handling — measures `mount-and-lifecycle`
- **PubSub tests**: real-time chat, presence broadcast — measures `pubsub-and-realtime`
- **Navigation tests**: same-LiveView state changes vs cross-LiveView routes — measures `navigation-patterns`
- **Auth tests**: protected routes, ownership checks on events — measures `auth-and-authz`
- **Migration tests**: convert a Phoenix 1.6 LiveView to 1.7 — exercises every capability in conversion mode

## Evidence

Strongest evidence base in the Elixir roster. See:
- [Research report Part 1 #4](../../docs/research/elixir-llm-pain-points.md#4-liveview-lifecycle-mistakes-mount-vs-handle_params-assign_new)
- [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix) — entire iron-law catalog targets LiveView
- [georgeguimaraes/claude-code-elixir phoenix-thinking](https://github.com/georgeguimaraes/claude-code-elixir)

## Notes

- This is the recommended **flagship family** for the SKLD lighthouse evaluation. Strongest evidence + biggest impact + clearest test surface.
- The `anti-patterns-catalog` capability is novel — it's negative-space teaching ("don't do X, do Y") rather than positive-pattern teaching. Plugin repos use this format because LLMs respond well to explicit "do not" framings.
- Adjacent to `elixir-ecto-sandbox-test` (LiveView tests use the sandbox adapter) — keep them separate but cross-reference.
- The Phoenix version anchor must be enforced in the skill description and frontmatter. Suggestion: `"Generates Phoenix 1.7+ LiveView. Use when writing or refactoring LiveView modules. NOT for Phoenix 1.6 — use phoenix-1.6-liveview skill instead."`
