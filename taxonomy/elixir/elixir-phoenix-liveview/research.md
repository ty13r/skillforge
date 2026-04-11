# elixir-phoenix-liveview — Per-Capability Research Dossier

**Generated**: 2026-04-11
**Workstream**: SKLD-bench v2.1 (see [`../SEEDING-PLAN.md`](../SEEDING-PLAN.md))
**Sources surveyed**: github.com/oliver-kriska, github.com/georgeguimaraes, hexdocs.pm/phoenix_live_view, fly.io/phoenix-files, elixirforum.com, news.ycombinator.com, getboothiq.com, johnelmlabs.com, hashrocket.com, aicodingrules.com, hexshift.medium.com, phoenixframework.org, arrowsmithlabs.com, dev.to, appsignal.com, binarynoggin.com, mrpopov.com, mcpmarket.com
**Total citations**: 38

## Family-level summary

Phoenix LiveView is the capability with the strongest public-failure-mode evidence in the entire Elixir ecosystem. The combination of (a) a major 1.6→1.7 version break where verified routes, function components, `<.link>`, streams, and `to_form/2` replaced a huge slice of the earlier API, and (b) a training corpus that is majority pre-1.7 means LLMs consistently regress to dead idioms. Two well-maintained Claude Code plugins — `oliver-kriska/claude-elixir-phoenix` and `georgeguimaraes/claude-code-elixir` — encode Claude's observed LiveView failures as "iron laws" that the plugin halts execution on. Every iron law is effectively a developer-confirmed bug report.

The highest-impact failure clusters are: (1) **lifecycle mistakes** — database queries in disconnected `mount/3`, missing `connected?/1` before PubSub subscribe, misuse of `assign_new/3` for values that should be freshly computed on reconnect; (2) **markup regressions** — string-interpolated `Routes.*_path` helpers instead of `~p`, old `<%= for %>` instead of `:for`, `live_redirect`/`live_patch` instead of `<.link navigate={}/patch={}>`; (3) **performance traps** — large collections in regular `assign/3` instead of `stream/3`, N+1 queries inside `live_component` list comprehensions, blocking work inside the LiveView process; (4) **form handling gaps** — building `to_form/2` incorrectly, mis-implementing `<.inputs_for>`, storing ephemeral UI state in socket assigns instead of hidden inputs, manually merging changesets with `Map.put`; (5) **security omissions** — missing `handle_event` authorization, unscoped PubSub topics that leak between tenants, `raw/1` on user content.

The best challenges for stress-testing variants of this family are **Phoenix 1.6→1.7 migrations** (exercises every capability at once), **reconnect-sensitive lifecycle tests** (catches `assign_new` abuse), **streams-vs-assigns swaps** on large collections (catches performance regression), **nested `<.inputs_for>` forms** with add/remove semantics (catches form-handling regressions), and **multi-tenant PubSub scoping** (catches auth + pubsub together). Migration challenges are uniquely valuable because they force a recognition step — the model has to see a deprecated idiom in the fixture and refuse to preserve it.

There is moderate but concentrated signal for every capability in this family; **nothing here is a pure greenfield guess**.

---

## Capability research

### Foundation: `architectural-stance`

**Description** (from README.md): How the skill decomposes responsibility across LiveView module ↔ LiveComponent ↔ function components ↔ Phoenix context. Variants: strict-LiveView, component-heavy, context-thin. Locks in vocabulary for every capability below.

**Known Claude failure modes**:
- [HIGH] Treats LiveView, LiveComponent, and function component as interchangeable — reaches for LiveComponent when a function component would do, and vice versa. Results in either over-stated components (stateless LC) or under-structured LiveViews (no decomposition at all).
- [HIGH] Passes the `%Socket{}` struct as an argument to helper functions instead of passing only the data the function actually needs. Leaks the socket into business logic.
- [MED] Allows parent LiveView and child LiveComponent to maintain two copies of the same state — no explicit source-of-truth decision.
- [MED] Duplicates logic across files because it doesn't know where something already lives ("writes new files everywhere").

**Citations**:
- "Functions only needs the socket's assigns or a subset of them... violates separation of concerns between LiveView callbacks and business logic" — [John Elm Labs, "Phoenix LiveView Anti-Patterns"](https://johnelmlabs.com/posts/anti-patterns-in-liveview), undated (2024-2025), Hex Shift/John Elm Labs
- "Generally speaking, you want to avoid both the parent LiveView and the LiveComponent working on two different copies of the state. Instead, you should assume only one of them to be the source of truth." — [Medium/Hex Shift, "Advanced LiveComponent Architecture"](https://hexshift.medium.com/advanced-livecomponent-architecture-in-phoenix-liveview-patterns-for-scalability-and-1b53d3c41408)
- "A good LiveComponent encapsulates application concerns and not DOM functionality. Do not write a component that is simply encapsulating generic DOM components." — [Phoenix.LiveComponent docs, hexdocs.pm](https://hexdocs.pm/phoenix_live_view/Phoenix.LiveComponent.html)
- "AI is exceptional at churning out lines of code. It's significantly less exceptional at deciding where those lines should go. It defaults to creating new files everywhere. It repeats code it's already written." — [BoothIQ blog, "150,000 Lines of Vibe Coded Elixir"](https://getboothiq.com/blog/150k-lines-vibe-coded-elixir-good-bad-ugly), 2026, BoothIQ
- Plugin skill rule: "Functional components: Display-only, no internal state. LiveComponents: Own state, handle own events. LiveViews: Full page, owns URL, top-level state." — [georgeguimaraes/claude-code-elixir phoenix-thinking SKILL.md](https://github.com/georgeguimaraes/claude-code-elixir) (mirrored at [lobehub.com](https://lobehub.com/skills/georgeguimaraes-claude-code-elixir-phoenix-thinking))

**Suggested challenge angles** (these become Phase 3 drafting input):
- Refactor a LiveView that passes `%Socket{}` into helper functions to pass only the assigns the helpers actually use.
- Decompose a 600-line LiveView into (LiveView + LiveComponent + function components) with an explicit source-of-truth rule. Evaluate that the decomposition is sane (no duplicated state, no stateless LCs).
- Given a multi-tab dashboard, decide for each tab whether it should be a LiveComponent, a function component, or a live_session route. Score the justification.
- Convert a LiveView that inlines business logic into a LiveView + Phoenix context module pair, preserving tests.
- Detect and fix an over-stated function component (a component that accepts `assigns` but should be a LiveComponent because it needs `handle_event/3`).

**Tier guidance**:
- Easy: One-step decomposition — extract a stateless function component from inline markup.
- Medium: Decide LiveView vs LiveComponent for a given spec and justify. Extract a two-level component tree from a procedural LiveView.
- Hard: Multi-file refactor that moves business logic into a context, fixes a shared-state bug between parent/child, and preserves test suite behavior.
- Legendary: Refactor a codebase with both the socket-passing anti-pattern AND duplicated state between LiveView and LiveComponent AND inline business logic — fix all three without regressing existing tests.

---

### Capability: `heex-and-verified-routes`

**Description** (from README.md): HEEx syntax (`:if`, `:for`, `:let`), `~p` sigil for routes, attribute interpolation.

**Known Claude failure modes**:
- [HIGH] Emits `Routes.user_path(socket, :show, user)` (removed helper) instead of `~p"/users/#{user}"`. The corpus is dominated by 1.6-era code that uses `Routes.*_path`.
- [HIGH] Uses `<%= for item <- @items do %>` EEx-style loops instead of HEEx's `:for` attribute on an HTML element.
- [HIGH] Uses `live_patch` / `live_redirect` helper calls instead of the `<.link patch={...}/navigate={...}>` function component.
- [MED] Omits `:if` / `:for` special attributes and drops to `<%= if %>` blocks inside HEEx — which works syntactically but loses LiveView's compile-time diff optimizations.
- [MED] String-interpolates route paths (`"/users/#{user.id}"`) instead of `~p`, silently bypassing compile-time route verification.

**Citations**:
- "Verified routes tackle this problem by allowing the routes to be written as we would read them in a browser, but using the ~p sigil to guarantee they actually exist at compilation time. They remove the indirection of named routes while keeping their guarantees." — [fly.io, "Migrating to Verified Routes"](https://fly.io/phoenix-files/migrating-to-verified-routes/)
- "The compiler will dispatch all ~p's at compile-time against your router, and let you know when it can't find a matching route, providing warnings about invalid routes during compilation rather than runtime." — [Phoenix.VerifiedRoutes docs](https://hexdocs.pm/phoenix/Phoenix.VerifiedRoutes.html)
- "In LiveView v0.18, `live_patch/2` and `live_redirect/2` calls were replaced with the new `<.link>` function component, where `live_patch` becomes `patch={...}` and `live_redirect` becomes `navigate={...}`." — [fly.io, "Migrating to LiveView v0.18"](https://fly.io/phoenix-files/migrating-to-lv-0-18/)
- "HEEx supports shorthand syntax for if and for expressions via the special :if and :for attributes." — [Phoenix Components and HEEx docs](https://hexdocs.pm/phoenix/components.html)
- Plugin iron law referenced: "Use verified routes (`~p`) — never string-interpolate `Routes.*_path`" — [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix) (surfaced via [mcpmarket.com Phoenix Thinking](https://mcpmarket.com/tools/skills/phoenix-thinking) skill mirror)

**Suggested challenge angles**:
- Convert a LiveView template containing `<%= link "profile", to: Routes.user_path(@socket, :show, @user) %>` to use `<.link navigate={~p"/users/#{@user}"}>profile</.link>`.
- Convert an EEx loop `<%= for item <- @items do %>...<% end %>` to `<div :for={item <- @items}>...</div>`.
- Given a LiveView with 30 route-helper call sites, convert all of them to `~p` including query-string cases.
- Adversarial: fixture contains a route path that does not exist in the router. Verify that `~p` breaks at compile time but a string-interpolated `/users/#{id}/edit-me` silently compiles.
- Nested `<.link>` pattern — when to use `navigate=` vs `patch=` vs plain `href=` on the same page.

**Tier guidance**:
- Easy: Single-line `Routes.user_path` → `~p"/users/#{user}"` conversion.
- Medium: Convert a full LiveView template (20+ route sites, mix of live_patch/live_redirect/live_link). Assert no `Routes.` references remain.
- Hard: Migrate a 1.6 LiveView template to 1.7 HEEx idioms — verified routes, `<.link>`, `:for`, `:if`, attribute shorthands — all at once, preserving semantics.
- Legendary: Fixture has subtly wrong routes (typos) that compile today because of string interpolation. Claude must convert to `~p` AND catch the compile-time errors that surface AND fix them against the router.

---

### Capability: `function-components-and-slots`

**Description** (from README.md): `attr` declarations, `slot` declarations, `inner_block`, named slots, composition.

**Known Claude failure modes**:
- [HIGH] Forgets to declare `attr :name, :type` for every attribute the component receives, leaving the component silently under-documented and un-validated.
- [MED] Uses `slot :default` or passes an `:inner_block` block with positional arguments in the wrong way; misses that `:inner_block` cannot accept a block declaration.
- [MED] Declares an attribute and a slot with the same name (compile error).
- [MED] Declares slot attributes with `:default` options (compile warning — "slot attributes cannot accept the :default option").
- [LOW] Uses `Phoenix.LiveView.Helpers` import in newer projects instead of `Phoenix.Component`.

**Citations**:
- "Slot attributes cannot accept the :default option, and passing one will result in a compile warning being issued." — [Phoenix.Component docs](https://hexdocs.pm/phoenix_live_view/Phoenix.Component.html)
- "The :inner_block slot declaration cannot accept a block, and passing one will result in a compilation error." — [Phoenix.Component docs](https://hexdocs.pm/phoenix_live_view/Phoenix.Component.html)
- "LiveView performs some validation of slots via the :phoenix_live_view compiler. When slots are defined, LiveView will warn at compilation time on the caller if a required slot of a component is missing, an unknown slot is given, or an unknown slot attribute is given." — [Phoenix.Component docs](https://hexdocs.pm/phoenix_live_view/Phoenix.Component.html)
- "The recommended approach is to import the Phoenix.Component module and remove the Phoenix.LiveView.Helpers import." — [fly.io "Migrating to LiveView v0.18"](https://fly.io/phoenix-files/migrating-to-lv-0-18/)

**Suggested challenge angles**:
- Author a `<.button>` component with `attr :variant, :string, default: "primary"`, `attr :rest, :global`, and a default `slot :inner_block`.
- Author a `<.modal>` with two named slots (`:header`, `:footer`) + default inner block.
- Fix a component that is missing `attr` declarations, then verify it raises compile warnings when called with an unknown attribute.
- Convert a LiveComponent that only renders markup (no state, no `handle_event`) into a function component.
- Compose three function components (card + header + action_row) into a single `<.data_card>` wrapper with slot-based customization.

**Tier guidance**:
- Easy: Add missing `attr` declarations to an existing function component.
- Medium: Author a function component with named slots, `:global` attrs for arbitrary HTML pass-through, and a doc block.
- Hard: Convert a stateless LiveComponent into a function component, and fix the call sites.
- Legendary: Build a component library (button, input, card, modal) that composes cleanly, has no `attr`/`slot` compile warnings, and correctly passes-through `class` and ARIA attrs via `:global`.

---

### Capability: `live-components-stateful`

**Description** (from README.md): When to use `LiveComponent` (stateful) vs function component (stateless), `handle_event` in components.

**Known Claude failure modes**:
- [HIGH] Wraps stateless rendering in a LiveComponent "for organization" — an analog of the GenServer-abuse pattern.
- [HIGH] Issues database queries inside `update/2` for each rendered LiveComponent instance, causing N+1 queries. Does not use `preload/1` to batch.
- [MED] Passes the parent's `%Socket{}` through to the LiveComponent instead of only the assigns it needs.
- [MED] Forgets the required unique `id` attribute on LiveComponent invocations.

**Citations**:
- "When a LiveComponent performing database access is rendered multiple times, it creates an N + 1 query problem. Showing 10 users issues 10 queries, plus 1 query for the LiveView." — [John Elm Labs, "Phoenix LiveView Anti-Patterns" #4](https://johnelmlabs.com/posts/anti-patterns-in-liveview)
- "LiveComponents are defined by using Phoenix.LiveComponent and are used by calling Phoenix.Component.live_component/1 in a parent LiveView. They can handle events with `handle_event/3`. They require a unique `id` attribute." — [Phoenix.LiveComponent docs](https://hexdocs.pm/phoenix_live_view/Phoenix.LiveComponent.html)
- Plugin rule paraphrased: "NO PROCESS WITHOUT A RUNTIME REASON — Claude wraps stateless code in GenServers for 'organization'." The LiveComponent analog is the same instinct. — [georgeguimaraes/claude-code-elixir otp-thinking](https://github.com/georgeguimaraes/claude-code-elixir)
- "Every `UserDetailComponent` rendered issues a DB query" — [John Elm Labs Anti-Patterns](https://johnelmlabs.com/posts/anti-patterns-in-liveview)

**Suggested challenge angles**:
- Identify a LiveComponent that should be a function component (no state, no events) and convert it.
- Fix a LiveComponent with N+1 queries in `update/2` by introducing a `preload/1` callback that batches the queries.
- Author a stateful filter/sort LiveComponent (handles its own `handle_event`) embedded in a parent LiveView; ensure parent and child don't both own the filter state.
- Given a spec for an "expandable row" UI, decide: LiveComponent with local `:expanded` state, or function component + parent-owned assign? Justify.
- Fix missing `id=` on a `<.live_component module={Foo}>` invocation (raises at runtime).

**Tier guidance**:
- Easy: Add a missing `id=` to a `<.live_component>` invocation.
- Medium: Demote a stateless LiveComponent to a function component.
- Hard: Fix N+1 in a LiveComponent with `preload/1` — must correctly wire the batched data through `list_of_assigns`.
- Legendary: Refactor a LiveView with three nested LiveComponents that all hold their own duplicated filter state into a single source-of-truth pattern with message-passing via `send_update/2`.

---

### Capability: `form-handling`

**Description** (from README.md): `to_form/2`, `<.form>`, `<.input>`, `<.inputs_for>`, validation feedback via `phx-change`, server-side validation.

**Known Claude failure modes**:
- [HIGH] Forgets the full `phx-change="validate"` → re-run-changeset → `to_form(action: :validate)` cycle. Missing the `action: :validate` means no errors surface.
- [HIGH] Stores ephemeral UI state (toggles, conditional inputs) in socket assigns and round-trips to the server for every toggle, instead of keeping the state in hidden form inputs.
- [HIGH] Butchers `<.inputs_for>` for nested forms — wrong schema config (missing `cast_assoc`, missing `on_replace: :delete`), wrong template (missing `sort_param`/`drop_param`), "add" button in wrong position.
- [HIGH] Manually mutates changesets with `Map.put(changeset, :changes, ...)` or `Map.merge` instead of `Ecto.Changeset` functions, leaving stale errors behind so the user "has valid data but can't submit".
- [MED] Couples database schemas directly to forms instead of using a form-specific schema or embedded schema — brittle as UI and DB evolve.
- [MED] Does not use `used_input?/1` to suppress errors on fields the user hasn't touched yet.

**Citations**:
- "Slow, laggy forms with scattered logic because form state gets stored in socket assigns and server round-trips get used for dynamic UI (conditional inputs, toggles), instead of keeping that state in hidden form inputs where it belongs." — [John Elm Labs, "Top 3 LiveView Form Mistakes" #1](https://johnelmlabs.com/posts/top-3-liveview-form-mistakes)
- "Brittle system where UI and database can't evolve independently because database schemas get used directly for forms, coupling persistence logic to presentation." — [John Elm Labs, "Top 3 LiveView Form Mistakes" #2](https://johnelmlabs.com/posts/top-3-liveview-form-mistakes)
- "Users stuck with valid data but can't submit because changesets get manually manipulated with `Map.put` or `Map.merge` instead of `Ecto.Changeset` functions, leaving stale errors behind." — [John Elm Labs, "Top 3 LiveView Form Mistakes" #3](https://johnelmlabs.com/posts/top-3-liveview-form-mistakes)
- "The validate callback simply updates the changeset based on all form input values, then converts the changeset to a form and assigns it to the socket." — [Phoenix LiveView Form bindings](https://hexdocs.pm/phoenix_live_view/form-bindings.html)
- "LiveView sends special parameters on form events starting with `_unused_` to indicate that the input for the specific field has not been interacted with yet. When creating a form through `to_form/2`, the `used_input?/1` function can be used to filter error messages." — [Phoenix LiveView Form bindings](https://hexdocs.pm/phoenix_live_view/form-bindings.html)
- "inputs_for is a function component used to handle nested inputs... Ecto sees an unrecognized value like 'new' and inserts a new nested changeset, which becomes a new set of nested inputs — this is the standard way to add a new nested item... but it only works like this if you place the 'add more' button after the list of ingredient inputs." — [Arrowsmith Labs, "Nested forms in Phoenix LiveView"](https://arrowsmithlabs.com/blog/phoenix-liveview-nested-forms-advanced-tricks)
- "`phx-change` receives proper params for Ecto to detect an item is being removed, while `phx-submit` does not — resulting in a no-op changeset being generated." — [GitHub issue #3270, phoenix_live_view](https://github.com/phoenixframework/phoenix_live_view/issues/3270)

**Suggested challenge angles**:
- Author a contact form with `to_form(Accounts.change_user(%User{}, %{}))`, a `validate` event that re-runs the changeset with `action: :validate`, and a `save` event with success/failure branches.
- Fix a form where errors display for fields the user hasn't touched yet — must use `used_input?/1` or filter in the template.
- Convert a form with server-round-tripped toggle state to use hidden form inputs + CSS for the toggle.
- Author a nested invoice form with `<.inputs_for>`, `cast_assoc`, `on_replace: :delete`, plus add/remove line-item buttons using `sort_param`/`drop_param`.
- Fix a form that manually merges changeset state with `Map.merge` — replace with `Ecto.Changeset.put_change/3`.
- Adversarial: Form submits but save handler never fires. Debug and fix (missing `phx-submit`, wrong event name, or missing `to_form` wrapping).

**Tier guidance**:
- Easy: Wire up `to_form/2` + `<.form>` + `phx-change="validate"` for a single-field form.
- Medium: Validate-with-errors pattern + `used_input?/1` gating + preserve user input on validation failure.
- Hard: Nested `<.inputs_for>` form with add/remove line items, correct schema config, and correct cast_assoc behavior.
- Legendary: Convert a form that couples to DB schemas and mutates changesets with `Map.merge` into a form-specific embedded schema with full `Ecto.Changeset` API usage — AND move the UI-toggle state out of socket assigns into hidden inputs.

---

### Capability: `streams-and-collections`

**Description** (from README.md): `stream/3`, `stream_insert/3`, `stream_delete/3`, `dom_id`, large collection performance.

**Known Claude failure modes**:
- [HIGH] Defaults to `assign(socket, :items, items)` for large collections (>100 items), causing full-list re-render on any update.
- [HIGH] Forgets the required `id` attribute on the stream container or the `phx-update="stream"` attribute, silently breaking surgical DOM diffing.
- [HIGH] Forgets that the stream container children must use `id={id}` from the `{id, item}` tuple yielded by `:for={{id, item} <- @streams.items}`.
- [MED] Mixes `stream/3` with regular `assign/3` for the same collection — can't decide which pattern to use.
- [MED] Tries to read `@streams.items` as a list (e.g., `Enum.count`) — streams are not enumerable on the server side after initial mount.

**Citations**:
- "Phoenix LiveView streams are a great feature that allows you to manage large collections of data on the client without having to keep those resources in memory on your server. Phoenix.LiveView.stream/4 is a game changer that lets you declaratively manage a list of items in a way that is both memory-efficient and surgically precise." — [fly.io, "Phoenix Dev Blog - Streams"](https://fly.io/phoenix-files/phoenix-dev-blog-streams/)
- "The parent element of the list to be rendered must have a unique id attribute and you must add a special phx-update='stream' attribute to define that children of this element are part of a stream." — [Phoenix.LiveView docs](https://hexdocs.pm/phoenix_live_view/Phoenix.LiveView.html)
- Iron law: "Use streams for lists >100 items." — [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix)
- "Keeping too much data in the socket: A LiveView's socket assigns are kept in the server process's memory for the life of the connection. Fix: Store only minimal fields needed for rendering; use temporary assigns or streams for large collections." — [Hex Shift Medium, "Ten Biggest Mistakes" #1](https://hexshift.medium.com/the-ten-biggest-mistakes-made-with-phoenix-liveview-and-how-to-fix-them-cbe2afda4c36)
- "When rendering a stream of 3000 items in the mount callback, the process uses 5.1 MB memory, which never gets released." — [GitHub issue #2592, phoenix_live_view](https://github.com/phoenixframework/phoenix_live_view/issues/2592)

**Suggested challenge angles**:
- Convert a LiveView that assigns a 10k-message inbox via `assign(:messages, ...)` to a stream.
- Fix a stream container that is missing `phx-update="stream"` — messages render but don't update.
- Author a `stream_insert/3` on a PubSub-received message (append to end, reset to top).
- Given a stream of notifications, author a "clear all" action using `stream(:items, [], reset: true)`.
- Adversarial: `Enum.count(@streams.notifications)` doesn't work — rework the UI to track count in a separate assign.

**Tier guidance**:
- Easy: Replace a regular `assign/3` on a list with `stream/3` in a LiveView that already has a container with `phx-update="stream"`.
- Medium: Author a full streaming inbox from scratch — `mount` sets up stream, `handle_info` inserts new items, `handle_event("delete", ...)` removes.
- Hard: Add virtualized infinite scrolling with `:limit` + `phx-viewport-top`/`phx-viewport-bottom`.
- Legendary: Convert a LiveView that uses `temporary_assigns` + `phx-update="append"` (pre-stream idiom) to modern `stream/3` — must preserve `dom_id` semantics and update behavior.

---

### Capability: `mount-and-lifecycle`

**Description** (from README.md): `mount/3` vs `handle_params/3`, `connected?/1` checks, `assign_new/3` gotcha, `temporary_assigns`.

**Known Claude failure modes**:
- [HIGH] Puts database queries in `mount/3` even though `mount/3` runs twice (once for the HTTP request and once over WebSocket). Every query runs twice.
- [HIGH] Uses `assign_new/3` for values that need to be freshly computed on reconnect, not understanding that `assign_new/3` silently skips on reconnect if the assign already exists.
- [HIGH] Writes URL-parameter-driven state updates in `mount/3` instead of `handle_params/3`, causing stale state on `push_patch`.
- [MED] Misuses `temporary_assigns: [items: []]` with a list that is actually needed across renders (count, filter, etc.) — the list resets to `[]` every render and the UI breaks in subtle ways.
- [MED] Uses `connected?/1` inside `handle_event` or `handle_info` instead of `mount/3` (doesn't make sense outside mount).

**Citations**:
- **The Iron Law:** "NO DATABASE QUERIES IN MOUNT. Mount runs twice (HTTP + WebSocket). Queries in mount duplicate. Instead: mount/3: Setup only—empty assigns, subscriptions, defaults. handle_params/3: All database queries and URL-driven state. No exceptions to defer. This is non-negotiable in LiveView lifecycle." — [georgeguimaraes/claude-code-elixir phoenix-thinking SKILL.md](https://github.com/georgeguimaraes/claude-code-elixir) (mirrored at [lobehub.com phoenix-thinking](https://lobehub.com/skills/georgeguimaraes-claude-code-elixir-phoenix-thinking))
- Iron law: "Never use `assign_new` for values refreshed every mount." — [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix)
- "When a LiveView is mounted in a disconnected state, the Plug.Conn assigns will be available for reference via assign_new/3... The Plug.Conn assigns will not be available during the connected mount." — [Phoenix.LiveView docs](https://hexdocs.pm/phoenix_live_view/Phoenix.LiveView.html)
- "mount/3 is called twice (HTTP request + WebSocket connection), and queries in mount result in duplicate queries. Database queries should be placed in handle_params/3 rather than mount/3, as handle_params is called once per navigation while mount is called twice." — [Binary Noggin, "Lifecycle of a Phoenix LiveView"](https://binarynoggin.com/blog/the-lifecycle-of-a-phoenix-liveview/)
- "When the liveview request completed and we asserted on the results, the test process finished and exited before their async tasks (which we didn't care about in those specific tests) could finish running." — [egeersoz, Elixir Forum thread "150,000 Lines of Vibe Coded Elixir"](https://elixirforum.com/t/150-000-lines-of-vibe-coded-elixir-the-good-the-bad-and-the-ugly/73899)

**Suggested challenge angles**:
- Refactor a LiveView that calls `Accounts.list_users()` in `mount/3` to move the query into `handle_params/3`.
- Fix a LiveView using `assign_new(socket, :current_time, fn -> DateTime.utc_now() end)` that shows stale time after reconnect.
- Convert a LiveView with an if-branch based on `connected?(socket)` in the wrong callback to the correct pattern.
- Author a URL-param-driven LiveView (e.g., `?filter=active&sort=name`) where `mount` sets up the shell and `handle_params` reads/applies the params.
- Adversarial: Fixture shows a LiveView that uses `temporary_assigns` on a list that the template tries to `Enum.count` — debug the broken count.

**Tier guidance**:
- Easy: Move a single `Repo.all` call from `mount/3` to `handle_params/3`.
- Medium: Add proper `connected?/1` gating to a LiveView that subscribes to PubSub, AND move its queries to `handle_params`.
- Hard: Fix an `assign_new/3` bug where a reconnect leaves the UI in a stale state — requires understanding that `assign_new` preserves the value across reconnect.
- Legendary: Refactor a LiveView that (a) queries in mount, (b) uses `assign_new` wrong, (c) reads URL params in mount, and (d) has a misconfigured `temporary_assigns` — all four bugs, fixed as a single coherent rewrite.

---

### Capability: `event-handlers-and-handle-info`

**Description** (from README.md): `phx-click` / `phx-submit` / `phx-change` / `phx-focus`, `handle_info/2` for external messages.

**Known Claude failure modes**:
- [HIGH] Abuses function-head pattern matching in `handle_event` — binds every param + every assign in the function head, producing "function head soup" that obscures intent and makes error messages cryptic.
- [HIGH] Forgets authorization checks inside `handle_event` (covered more under `auth-and-authz`) — relies on UI-level hiding.
- [MED] Uses `handle_info` without a matching pattern, leading to unhandled-message crashes on unrelated pubsub broadcasts.
- [MED] Treats `terminate/2` as a cleanup hook — "terminate/2 won't fire without `trap_exit`—don't use in LiveView."
- [MED] Doesn't debounce or throttle `phx-change` on text inputs, flooding the server with events per keystroke.

**Citations**:
- "Function Head Pattern Matching Abuse: Binding every variable in params or socket.assigns in function heads creates 'function head soup' that obscures intent... If a function head fails to match on the passed arguments, a cryptic FunctionClauseError error is raised." — [John Elm Labs Anti-Patterns #2](https://johnelmlabs.com/posts/anti-patterns-in-liveview)
- "terminate/2 won't fire without `trap_exit`—don't use in LiveView. Instead: separate GenServer monitoring via `Process.monitor/1` and `:DOWN` messages." — [georgeguimaraes/claude-code-elixir phoenix-thinking](https://github.com/georgeguimaraes/claude-code-elixir) (via [lobehub mirror](https://lobehub.com/skills/georgeguimaraes-claude-code-elixir-phoenix-thinking))
- "Not debouncing or rate limiting frequent events: Every keystroke sends an event to the server. Fix: Use phx-debounce and phx-throttle attributes on client elements." — [Hex Shift, "Ten Biggest LiveView Mistakes" #4](https://hexshift.medium.com/the-ten-biggest-mistakes-made-with-phoenix-liveview-and-how-to-fix-them-cbe2afda4c36)
- "When a message is broadcasted, handle it with handle_info/2 and update the LiveView state. def handle_info(%{message: message}, socket) do..." — [Elixir School, "Building Real-Time Features"](https://elixirschool.com/blog/live-view-with-pub-sub)

**Suggested challenge angles**:
- Refactor a `handle_event("validate", %{"a" => a, "b" => b, "c" => c, ...} = params, socket)` with 8 field bindings into a clean discriminating head + body destructure.
- Add `phx-debounce="300"` to a search input that currently fires on every keystroke.
- Add a `handle_info` catch-all that logs and no-ops unexpected messages.
- Fix a `terminate/2` callback that assumes cleanup will run on LV shutdown — move the cleanup to a separate supervised process with `Process.monitor`.
- Author a LiveView that receives PubSub broadcasts of two kinds (`:user_joined`, `:user_left`), handles each in `handle_info`, and uses `handle_event` for user-initiated actions.

**Tier guidance**:
- Easy: Add `phx-debounce="200"` to an input.
- Medium: Refactor function-head soup into discriminating pattern + body destructure.
- Hard: Author a multi-message LiveView that handles PubSub + internal timers + user events without crashing on unknown messages.
- Legendary: Given a crashing LiveView with an unhandled `:DOWN` message from a monitored task, diagnose and fix — either add a handler or cancel the monitor.

---

### Capability: `pubsub-and-realtime`

**Description** (from README.md): Subscribe on connected mount, topic namespacing, broadcast filtering, unsubscribe semantics.

**Known Claude failure modes**:
- [HIGH] Subscribes to PubSub inside `mount/3` without guarding with `if connected?(socket), do: Phoenix.PubSub.subscribe(...)`. On disconnected mount this either errors or subscribes twice.
- [HIGH] Uses unscoped PubSub topics (e.g., `"posts"`) instead of tenant/resource-scoped topics (`"posts:org:#{org.id}"`) — causes cross-tenant data leakage.
- [MED] Broadcasts from the LiveView process (a user-scoped process) instead of from a shared process or Phoenix context function.
- [MED] LiveView polls an external API (e.g., hits a REST endpoint every second) — multiplies the external request count by connected users. Should be one GenServer polling + broadcasting via PubSub.
- [LOW] Forgets `unsubscribe` semantics (rarely needed since the process exit handles it, but sometimes matters for manual resub).

**Citations**:
- **Iron Law:** "Check `connected?/1` before PubSub subscribe." — [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix)
- "Unscoped topics leak data between tenants." — [georgeguimaraes/claude-code-elixir phoenix-thinking, on PubSub Scoping](https://github.com/georgeguimaraes/claude-code-elixir) (via [lobehub mirror](https://lobehub.com/skills/georgeguimaraes-claude-code-elixir-phoenix-thinking))
- "Use connected?/1 to conditionally perform stateful work, such as subscribing to pubsub topics, sending messages, etc. This is important because on initial page render, the view is mounted statically, rendered, and the HTML is sent to the client. Once the client connects to the server, a LiveView is then spawned and mounted statefully within a process." — [Phoenix.LiveView docs](https://hexdocs.pm/phoenix_live_view/Phoenix.LiveView.html)
- "External Data Polling — Anti-pattern: LiveView polls external APIs (multiplies requests by connected users). Pattern: Single GenServer polls, broadcasts results via PubSub to all users." — [georgeguimaraes/claude-code-elixir phoenix-thinking](https://github.com/georgeguimaraes/claude-code-elixir) (via [lobehub mirror](https://lobehub.com/skills/georgeguimaraes-claude-code-elixir-phoenix-thinking))
- "If connected?(socket), do: Phoenix.PubSub.subscribe(Meeter.PubSub, 'change') ensures subscriptions only happen after the LiveView is fully connected to the server." — [Curiosum, LiveView Messenger Tutorial](https://curiosum.com/blog/elixir-phoenix-liveview-messenger-part-3)

**Suggested challenge angles**:
- Add `if connected?(socket)` guard to a LiveView that subscribes to PubSub in mount.
- Refactor a LiveView that subscribes to `"messages"` to instead subscribe to `"messages:org:#{org_id}"` — with a matching broadcast-site change.
- Fix a LiveView that polls `HTTPClient.fetch_price()` every second — move the polling to a GenServer that broadcasts via PubSub.
- Author a chat LiveView where each chat room has a scoped topic, users subscribe on connected mount, and `handle_info` renders new messages into a stream.
- Adversarial: Fixture has a PubSub broadcast that can be received by users with the wrong tenant. Detect and fix.

**Tier guidance**:
- Easy: Add `if connected?(socket)` around a PubSub subscription.
- Medium: Author a tenant-scoped PubSub subscribe + matching broadcast + `handle_info` render.
- Hard: Convert a per-user external API poll into a single GenServer poll + broadcast pattern.
- Legendary: Debug a cross-tenant data leak caused by an unscoped topic, AND fix the subscribe site AND the broadcast site AND add regression tests.

---

### Capability: `navigation-patterns`

**Description** (from README.md): `push_navigate` vs `push_patch` vs `redirect` vs `<.link>`; live_session boundaries.

**Known Claude failure modes**:
- [HIGH] Uses `push_redirect/2` (deprecated) instead of `push_navigate/2`.
- [HIGH] Uses `live_patch`/`live_redirect` helper functions (deprecated) instead of `<.link patch={...}/navigate={...}>`.
- [MED] Uses `push_navigate` when `push_patch` is correct (same LiveView state change) — causes a full dismount/mount cycle and loses transient state.
- [MED] Uses `push_patch` when `push_navigate` is required (crossing a `live_session` boundary) — raises at runtime.
- [MED] Uses plain HTTP `redirect/2` when a live navigation would be more appropriate (full page reload, loses socket state).
- [LOW] Confuses `<.link href={}>` (full reload) with `<.link navigate={}>` / `<.link patch={}>`.

**Citations**:
- "The `push_redirect/2` function is deprecated in favor of `push_navigate/2`. Additionally, `live_redirect` and `live_patch` are deprecated in favor of the new `<.link navigate={..}>` and `<.link patch={..}>` components." — [Phoenix LiveView live-navigation docs](https://hexdocs.pm/phoenix_live_view/live-navigation.html)
- "Use `push_patch/2` to trigger patch navigation, and `push_navigate/2` to navigate to another LiveView. The 'patch' operations should be used when navigating to the current LiveView without mounting a new one, while the 'navigate' operations should be used when you want to dismount the current LiveView and mount a new one." — [dev.to, "Phoenix LiveView: When to use navigate, patch, href..."](https://dev.to/ceolinwill/phoenix-liveview-when-to-use-navigate-patch-href-redirect-pushpatch-pushnavigate-6pl)
- "live_redirects don't go through the plug pipeline." — [Phoenix LiveView Security considerations](https://hexdocs.pm/phoenix_live_view/security-model.html)

**Suggested challenge angles**:
- Convert `push_redirect(socket, to: "/users")` to `push_navigate(socket, to: "/users")`.
- Convert `<%= live_patch "Edit", to: Routes.user_path(@socket, :edit, @user) %>` to `<.link patch={~p"/users/#{@user}/edit"}>Edit</.link>`.
- Decide when to use `patch` vs `navigate` for a filter change vs a detail-view transition.
- Given a spec where the user must re-authenticate when crossing a live_session boundary, verify that the transition uses `push_navigate/2` not `push_patch/2`.
- Adversarial: A `push_patch/2` call tries to cross a live_session boundary. Detect the runtime error and fix by switching to `push_navigate/2`.

**Tier guidance**:
- Easy: Rename `push_redirect` → `push_navigate`.
- Medium: Convert a `live_patch`/`live_redirect` template block to `<.link patch/navigate=>`.
- Hard: Audit a multi-page LiveView flow and decide patch vs navigate at each transition, with justification.
- Legendary: Fix a subtle bug where a filter change uses `push_navigate/2` and loses scroll position + transient form state — must switch to `push_patch/2` AND refactor the `handle_params` branch.

---

### Capability: `auth-and-authz`

**Description** (from README.md): `on_mount` hooks for authentication, per-`handle_event` authorization checks.

**Known Claude failure modes**:
- [HIGH] Missing `handle_event` authorization — relies on UI-level hiding (hiding the "Delete" button) instead of re-checking permissions server-side in the event handler. A savvy user can call the event directly.
- [HIGH] Performs auth only in the router plug pipeline, not in `mount/3` — leaves live navigation (`<.link navigate=>`) bypass-able, because it skips the plug pipeline.
- [MED] Uses `on_mount` for authentication but forgets that session validation must happen in both the HTTP plug pipeline AND the stateful LiveView mount.
- [MED] Mixes authentication (who) with authorization (what) — puts "is this user an admin?" checks in on_mount alongside "is this user logged in?" checks.
- [MED] Does not thread an authorization scope through context functions — raw `Repo.all(Post)` instead of `Post |> where(user_id: ^scope.user.id) |> Repo.all()`.

**Citations**:
- **Iron Law:** "Authorize in every LiveView `handle_event`." — [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix)
- "A common security concern is that a user can see all projects but may not have permission to delete any of them, and while the UI might not show the delete button, a savvy user could directly talk to the server and request a deletion. This highlights why most actions are handled by the handle_event callback, and you typically need to authorize the user within those callbacks." — [Hashrocket, "Authorization in Phoenix LiveView"](https://hashrocket.com/blog/posts/authorization-in-phoenix-liveview)
- "Any session validation must happen both in the HTTP request (plug pipeline) and the stateful connection (LiveView mount). Always perform your authentication and authorization in your LiveViews and if your application handles both HTTP requests and LiveViews, you need to perform these on both because live_redirects don't go through the plug pipeline." — [Phoenix LiveView Security considerations](https://hexdocs.pm/phoenix_live_view/security-model.html)
- Scopes pattern (Phoenix 1.8+): "Authorization context threads automatically through function signatures: `def list_posts(%Scope{user: user}) do Post |> where(user_id: ^user.id) |> Repo.all() end`" — [georgeguimaraes/claude-code-elixir phoenix-thinking](https://github.com/georgeguimaraes/claude-code-elixir) (via [lobehub mirror](https://lobehub.com/skills/georgeguimaraes-claude-code-elixir-phoenix-thinking))
- "Security and authorization mistakes: If the user can trigger events that change sensitive data, you must check authorization in those handlers too." — [Hex Shift, "Ten Biggest LiveView Mistakes" #9](https://hexshift.medium.com/the-ten-biggest-mistakes-made-with-phoenix-liveview-and-how-to-fix-them-cbe2afda4c36)

**Suggested challenge angles**:
- Add ownership checks to a `handle_event("delete-post", ...)` that currently trusts the UI.
- Author an `on_mount` hook that rejects unauthenticated users on all LiveViews in a `live_session`.
- Convert a `Posts.list_posts()` context function to `Posts.list_posts(%Scope{user: user})` — and update all call sites.
- Adversarial: Fixture LiveView has auth in the router plug pipeline but not in on_mount. Verify that `<.link navigate=>` bypasses the plug chain.
- Author a two-layer auth pattern (on_mount: ensure_authenticated, handle_event: per-action authorize).

**Tier guidance**:
- Easy: Add a `case authorized?(user, post) do :ok -> ...` guard to a single `handle_event`.
- Medium: Author an `on_mount` hook for a live_session + per-event ownership checks on a LiveView.
- Hard: Thread a `%Scope{}` pattern through a context module, change every query to be scope-aware, and update the LiveView to pass `scope` into context calls.
- Legendary: Debug a LiveView where `<.link navigate=>` bypasses auth (only plug-level auth exists). Fix via on_mount AND verify with a failing-then-passing test that asserts unauthenticated access is blocked.

---

### Capability: `anti-patterns-catalog`

**Description** (from README.md): Explicit iron-law catalog teaching what NOT to do (no DB in mount, connected? before subscribe, no float for money in displayed values, etc.). **This is a negative-space capability** — teaches what to avoid, not what to do.

**Known Claude failure modes**:
- [HIGH] (meta) Reverts to canonical anti-patterns repeatedly across multiple turns, even when corrected. This is the core motivation for the iron-law plugin architecture — Claude "forgets" the rule between turns.
- [HIGH] Passes `%Socket{}` as a function argument (socket-leak anti-pattern).
- [HIGH] N+1 queries inside `live_component :for` loops.
- [HIGH] Function-head pattern matching abuse / "function head soup".
- [MED] Missing debounce/throttle on text input events.
- [MED] Blocking work inside the LiveView process (heavy synchronous computation in `handle_event`).
- [MED] `temporary_assigns` + `phx-update="append"` instead of modern streams.
- [MED] Treating the LiveView process as global/shared state ("works for one user, not across nodes/restarts").
- [LOW] Passing raw user input to `raw/1` (XSS, covered under security).
- [LOW] Storing large data in socket assigns ("Keeping too much data in the socket").

**Citations**:
- Ten-item enumeration: "Keeping too much data in the socket / Misunderstanding temporary assigns and streams / Blocking work on the LiveView process / Not debouncing or rate limiting frequent events / Rendering anti-patterns from over-rendering / Trying to use LiveView for every UI / Failing to handle disconnects / Treating the LiveView process as a place for global state / Security and authorization mistakes / Not instrumenting or profiling." — [Hex Shift, "The Ten Biggest Mistakes Made With Phoenix LiveView"](https://hexshift.medium.com/the-ten-biggest-mistakes-made-with-phoenix-liveview-and-how-to-fix-them-cbe2afda4c36)
- "Don't Pass the Socket as an Argument to Functions / Function Head Pattern Matching Abuse / Indexing: Not Just For the Database / You Have N + 1 Queries In Your LiveComponents" — [John Elm Labs Anti-Patterns](https://johnelmlabs.com/posts/anti-patterns-in-liveview)
- Iron-law catalog philosophy: "The plugin enforces critical rules including: LiveView should not have database queries in disconnected mount, use streams for lists greater than 100 items, and check connected?/1 before PubSub subscribe... Additional Iron Laws include: Ecto — never use :float for money, always pin values with ^ in queries... Oban — jobs must be idempotent, args use string keys, never store structs in args... Security — no String.to_atom with user input, authorize in every LiveView handle_event, never use raw/1 with untrusted content." — [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix)
- "Claude Code had the right skills but wasn't invoking them consistently." — [Elixir Forum, "Sharing My Claude Code Plugin"](https://elixirforum.com/t/sharing-my-claude-code-plugin-for-elixir-development/74119)
- "Also, Claude has some bad habits... other annoying things like doing `case functioncall() do nil -> ... end` instead of `if var = functioncall() do else`" — [dnautics, Hacker News](https://news.ycombinator.com/item?id=46752907)
- "The imperative thing is so frustrating. Even the latest models still write elixir like a JS developer, checking nils, maybe_do_blah helper functions everywhere. 30 lines when 8 would do." — [te_chris, Hacker News](https://news.ycombinator.com/item?id=46752907)

**Suggested challenge angles**:
- Multi-anti-pattern fixture: a LiveView file that contains 4 distinct anti-patterns (socket-leak, function head soup, N+1 in component, DB in mount). Claude must detect and fix each.
- "Anti-pattern detector" challenge: given a SKILL.md fragment listing 10 anti-patterns, verify that a sample LiveView contains exactly N of them and identify them by name.
- Fix a LiveView that uses the pre-stream idiom `temporary_assigns: [messages: []] + phx-update="append"` by converting to `stream/3`.
- Debug a LiveView that freezes under load because `handle_event` runs a synchronous 2-second computation. Move the work to `start_async/3`.
- Adversarial: Fixture looks correct at first glance. Detect a subtle anti-pattern (e.g., `Enum.find` on a large `@departments` assign — should be Map-indexed).

**Tier guidance**:
- Easy: Fix a single well-known anti-pattern (e.g., replace `Enum.find` on a large list with a Map lookup).
- Medium: Fix a multi-anti-pattern LiveView (2-3 independent bugs).
- Hard: Detect and name 5+ anti-patterns in a deliberately bad fixture and fix all of them.
- Legendary: Detect a subtle performance regression (O(n²) reduce building a lookup table) that is NOT in any of the canonical anti-pattern lists — requires reasoning about the algorithm, not matching against a rule.

---

## Research process notes

The richest material for this family came from the two Claude Code plugin repos (`oliver-kriska/claude-elixir-phoenix` and `georgeguimaraes/claude-code-elixir`'s `phoenix-thinking` skill), the John Elm Labs anti-patterns posts, the Hex Shift "Ten Biggest Mistakes" article, and the BoothIQ post-mortem (which is stronger on Ecto and OTP than on LiveView specifically, but the one LiveView quote it has is golden). Official Phoenix LiveView docs were also consulted directly — they are the ground-truth source for deprecations and migration guidance.

Capabilities with thinner but still-adequate material: `function-components-and-slots` (docs are strong, public failure reports are thin — most of the failure evidence is in the fact that plugin authors ship slot/attr lint rules at all), `navigation-patterns` (migration docs are excellent, but there's little public "here's what Claude gets wrong" about navigation specifically — it's inferred from the deprecation pattern), and `event-handlers-and-handle-info` (the "function head soup" anti-pattern is well documented but not specifically tagged as an LLM failure — it's a general anti-pattern that LLMs happen to commit).

Cross-cutting theme: **the training-corpus-era problem.** Phoenix 1.6 is much more common in the corpus than 1.7, and LiveView's API changed substantially between the two. Almost every failure mode in this dossier is either (a) a regression to a pre-1.7 idiom, (b) a misunderstanding of the `mount/connected?/handle_params` lifecycle split, or (c) a misuse of `to_form/2` + `<.inputs_for>`, which are also 1.7-era features. A migration-heavy challenge set is the single most valuable way to stress-test this family, because it forces the model to recognize stale idioms in the input and not merely generate correct-from-scratch code.

The `anti-patterns-catalog` capability is unique: it is explicitly negative-space teaching, and the canonical "evaluation" for it is "did Claude detect and fix N of N planted anti-patterns in a fixture". Its challenge pool will look different from the others — the fixtures will be deliberately bad, not neutral.

## Capability prioritization (Phase 2 output, embedded here)

| Capability | Evidence strength | Recommended primary count | Rationale |
|---|---|---|---|
| `architectural-stance` (foundation) | MED | 12 rich | Foundation cross-cuts every capability; evidence is present but less concentrated than lifecycle/forms |
| `heex-and-verified-routes` | HIGH | 16 rich | Strongest migration signal — direct 1.6→1.7 conversion cases are the best legendary challenges in the family |
| `function-components-and-slots` | MED | 12 rich | Docs strong, failure reports thinner; challenge difficulty centered on slot + attr correctness |
| `live-components-stateful` | HIGH | 14 rich | N+1 + socket-passing are well-cited anti-patterns and high-value challenges |
| `form-handling` | HIGH | 16 rich | Top-3 form mistakes article + nested forms complexity — richest source of adversarial/legendary material |
| `streams-and-collections` | HIGH | 16 rich | Iron law + ten-biggest-mistakes + direct perf evidence — perfect for performance-sensitive challenges |
| `mount-and-lifecycle` | HIGH | 16 rich | THE Iron Law. Most cited pattern in the entire family. Needs legendary-tier adversarial fixtures |
| `event-handlers-and-handle-info` | MED | 13 rich | Function-head soup + debounce are well-cited; handle_info patterns less so |
| `pubsub-and-realtime` | HIGH | 14 rich | Iron law + tenant-scoping evidence — strong for auth+pubsub combo challenges |
| `navigation-patterns` | MED | 12 rich | Deprecation evidence excellent, "Claude gets it wrong" evidence inferred — ship medium volume |
| `auth-and-authz` | HIGH | 14 rich | Iron law + two direct expert posts + docs warning on live_redirect-bypass |
| `anti-patterns-catalog` | HIGH | 16 rich | Negative-space capability — the single most evidence-backed chunk; fixtures will be deliberately bad |

**Total primary-tagged target: ~171 challenges across 12 dimensions** (matches README target ~150 with ~14% overlap for secondary-tag coverage).

## Capabilities with insufficient public failure documentation

None of the 12 capabilities are purely undocumented. The thinnest-documented-as-Claude-failure are:
- `function-components-and-slots` — excellent official docs, but "here's what Claude gets wrong" is inferred rather than directly cited. Challenge authoring should lean on the official compile-time warnings (`unknown slot attribute`, `slot :default` error, etc.) as the ground truth, and create challenges where a component must pass compile without warnings.
- `navigation-patterns` — strong deprecation/migration docs but thin "Claude fails here" narratives. Challenges should lean on the deprecation itself as the failure surface (`push_redirect` → `push_navigate`, `live_patch`/`live_redirect` → `<.link>`).
- `event-handlers-and-handle-info` outside of function-head soup — debounce/`terminate` evidence is thin but present. Challenges beyond the top 2-3 well-evidenced patterns should target textbook idioms from the official LiveView `handle_info` docs.
