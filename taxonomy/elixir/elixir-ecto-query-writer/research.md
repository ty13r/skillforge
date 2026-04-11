# elixir-ecto-query-writer — Per-Capability Research Dossier

**Generated**: 2026-04-11
**Workstream**: SKLD-bench v2.1 (see [`../SEEDING-PLAN.md`](../SEEDING-PLAN.md))
**Sources surveyed**: Elixir Forum (10+ threads), Hacker News, Dashbit blog, AppSignal blog, Fly.io Phoenix Files, Dennis Beatty blog, Dev.to, Gatlin.io, Curiosum blog, Medium (Jonny Eberhardt, Cory O'Daniel, Sergey Chechaev), Victor Björklund blog, Amberbit blog, Vereis.com, oliver-kriska/claude-elixir-phoenix GitHub repo, georgeguimaraes/claude-code-elixir GitHub repo, elixir-ecto/ecto GitHub issues (#495, #1010, #1284, #1478, #1937, #2281, #2297, #2474, #2815, #3334, #3363, #4589, #4633), Hexdocs official Ecto documentation, BoothIQ post-mortem, `docs/research/elixir-llm-pain-points.md`
**Total citations**: 48

## Family-level summary

Ecto.Query is a macro-based DSL that looks SQL-ish but is semantically closer to a data-structure builder than to a SQL string. Two patterns dominate the public failure record: (1) the **pin operator (`^`)** — Claude and other LLMs frequently forget it, producing queries that either fail to compile with a cryptic "variable is not a valid query expression" error or, worse, silently treat the variable as a binding name, and (2) **preload strategy selection** — Claude defaults to join-preloads for `has_many` associations, which causes Cartesian-product memory bloat (~10x) and has been the single most frequently enforced "iron law" in the community Claude Code plugins.

Beyond those two, Ecto queries trip LLMs in several distinct ways. Dynamic queries built with `Ecto.Query.dynamic/2` require a specific `Enum.reduce(params, dynamic(true), …)` composition pattern that Claude does not spontaneously reproduce. Subqueries require `subquery/1` wrapping and often `parent_as/1` for correlation — two pieces of API that Claude regularly skips in favor of raw-SQL fragments. Window functions require the `|> over(…)` pipe or a named `windows:` clause; Claude leans on `fragment("… OVER (…)")` even when a typed version exists. Fragments are a SQL-injection vector: the caret `^` operator is deliberately forbidden as the first argument to `fragment/1`, but Claude frequently tries to write `fragment("... #{user_input} ...")` or uses string interpolation inside the fragment literal. Upserts via `insert_all(..., on_conflict: :replace_all)` have at least four documented ways to silently lose or corrupt data (missing `conflict_target`, NULL violations on unspecified NOT NULL columns, timestamp mutation, and `replace_all` writing NULLs for fields absent from the changeset).

The query composition style layer (pipe vs keyword vs schema-module-encapsulated) is not itself a correctness issue but strongly affects whether the resulting code is reusable. The Elixir community has converged on two patterns worth teaching the skill: `from MySchema, as: :my_schema` with named bindings so query functions compose across joins, and separating query-builder modules from context modules for single-responsibility.

Public Elixir-specific LLM-failure documentation is concentrated in two places: the oliver-kriska and georgeguimaraes Claude Code plugins (which encode observed failures as enforcement rules) and the BoothIQ "150k lines of vibe-coded Elixir" post-mortem (which narrates the pain at a higher level). Both plugins explicitly list Ecto rules that stop Claude mid-flight: pin operator, preload strategy, and separate-query-for-has_many. The ecto-thinking skill in georgeguimaraes adds the crucial nuance — "Separate preloads work best for Has-many with many records (less memory); Join preloads suit Belongs-to, has-one" — and names the 10x memory figure directly.

---

## Capability research

### Foundation: `query-composition-style`

**Description** (from README.md): How the skill teaches query composition: pipe-heavy (`Query |> where(...) |> where(...)`), keyword-heavy (`from u in User, where: ..., where: ...`), or schema-macro-driven (encapsulating queries inside the schema module). Variants determine the canonical form for every capability.

**Known Claude failure modes**:
- [HIGH] Producing non-composable queries: Claude tends to write one monolithic `from` block rather than decomposing into reusable query-builder functions that take and return a `Ecto.Queryable`.
- [HIGH] Repeating bindings inconsistently across pipe-chained operations, causing binding-position bugs when functions are composed together (Ecto binds positionally; names don't have to match but the positions must line up).
- [MED] Mixing keyword and pipe styles within a single query in ways that make the binding scope unclear.
- [MED] Burying queries inside context files so the context module grows unboundedly — the community anti-pattern.
- [MED] Forgetting to default to `from MySchema, as: :my_schema` so query functions can be reused across joins via named bindings.

**Citations**:
- "Keyword-based and pipe-based examples are equivalent. The downside of using macros is that the binding must be specified for every operation." — [Ecto.Query hexdocs](https://hexdocs.pm/ecto/Ecto.Query.html), 2026
- "Bindings are positional, and the names do not have to be consistent between input and refinement queries." — [Ecto.Query hexdocs](https://hexdocs.pm/ecto/Ecto.Query.html), 2026
- "It seems to me that the root of the issue is that there is another binding available after the first query runs, and the second query having no idea about it does the `where` on the incorrect binding." — iwarshak, [elixir-ecto/ecto issue #1284](https://github.com/elixir-ecto/ecto/issues/1284)
- "This issue does not happen when using keyword queries because we can track bindings more efficiently there." — José Valim, [elixir-ecto/ecto issue #1284](https://github.com/elixir-ecto/ecto/issues/1284)
- "A common anti-pattern is to put resource queries in files that hold resource business logic, such as in a context file... the context file may grow very large since queries tend to be pretty long." — Szymon Soppa, [Curiosum: Elixir Ecto Query Modules](https://curiosum.com/blog/composable-elixir-ecto-queries-modules), April 2021
- "Always defaulting query functions to `from(MySchema, as: :my_schema)` so functions can be reused across joins." — [Curiosum: Elixir Ecto Query Modules](https://curiosum.com/blog/composable-elixir-ecto-queries-modules), April 2021

**Suggested challenge angles**:
- Given a monolithic 40-line `from` block, refactor into 3-5 composable query-builder functions that pipe together.
- Given two query-builder functions that use conflicting positional bindings, fix so they can be composed.
- Port a keyword-style query to a pipe chain while preserving a shared named binding (`as: :user`) that a later `order_by` references.
- Extract Ecto queries out of a bloated context module into a dedicated `Accounts.UserQueries` module.
- Given a query that joins three tables, ensure a downstream function can filter against the third via a named binding.

**Tier guidance**: Easy (style port, no new bindings), Medium (decompose + preserve semantics), Hard (reusable builders + named bindings + downstream composition), Legendary (multi-context query library with cross-schema composition).

---

### Capability: `basic-where-select-order`

**Description** (from README.md): The foundational query shape; `where`, `select`, `order_by`, `limit`, `offset`.

**Known Claude failure modes**:
- [HIGH] Writing `where: u.email == nil` instead of `where: is_nil(u.email)` — Ecto forbids `nil` comparisons in filters for safety and raises at compile time.
- [MED] `select: [:id, :name]` returns a struct with only those fields set (plus the rest as `nil`), versus `select: map(u, [:id, :name])` which returns a plain map — Claude conflates the two.
- [MED] Returning `select: u` when caller only needs two fields, defeating index-only scans.
- [MED] `order_by: [desc: u.inserted_at]` vs `order_by: [desc: :inserted_at]` — atom form works unbound, but breaks when the schema has been joined and you meant the joined table.

**Citations**:
- "`nil` comparison in filters... is forbidden and it will raise an error" for security. Use `is_nil/1` instead. — [Ecto.Query hexdocs](https://hexdocs.pm/ecto/Ecto.Query.html)
- "Using `select: [:id, :title]` is equivalent to `select: struct(p, [:id, :title])` but for maps use `select: map(p, [:name])`" — [Ecto.Query hexdocs](https://hexdocs.pm/ecto/Ecto.Query.html)
- "Simple selects avoid bindings: `|> select([:foo, :bar, :baz])`" — michalmuskala, [Elixir Forum: About Ecto query syntax](https://elixirforum.com/t/about-ecto-query-keyword-based-or-pipe-based-style/10989), December 20, 2017

**Suggested challenge angles**:
- Replace `where: u.email == nil` with `is_nil/1`.
- Return a map of `%{id: ..., name: ...}` instead of a full struct using `select: map/2`.
- Sort a paginated feed by multiple keys (`inserted_at desc, id desc`) to make the cursor deterministic.
- Use `limit` with an interpolated variable (forcing the pin operator into the test).
- Given a struct-shaped `select: [:id, :name]`, convert to a map shape and explain the difference.

**Tier guidance**: Easy (single clause edit), Medium (multi-clause + pin operator integration), Hard (compose several clauses + select shape), Legendary (rare — mostly belongs in other capabilities).

---

### Capability: `joins`

**Description** (from README.md): `inner_join`, `left_join`, `full_join`, `cross_join`, `as: :alias_name` for named bindings.

**Known Claude failure modes**:
- [HIGH] Using `join` when `assoc/2` would do — forgetting Ecto's schema-driven `join u in assoc(p, :user)`.
- [HIGH] Forgetting to name bindings with `as:` when the join target needs to be referenced later (e.g., for `order_by` or `select_merge`).
- [MED] Left-join then filtering in `where` — which effectively turns the left-join into an inner join because the `NULL` row gets filtered out. Requires filtering inside the `on` clause instead.
- [MED] Producing Cartesian duplication when joining a `has_many` and then selecting the parent without distinct or preload — the parent row is returned once per child.

**Citations**:
- "Named binding references must always be placed at the end of the bindings list" — [Ecto.Query hexdocs](https://hexdocs.pm/ecto/Ecto.Query.html)
- "`belongs_to` pointing across context boundaries" and "`has_many` with join preloads" are listed as Red Flags for query patterns. — [georgeguimaraes/claude-code-elixir ecto-thinking SKILL](https://github.com/georgeguimaraes/claude-code-elixir)
- "The resulting SQL will output the same column values multiple times. If these are large text/blobs, the amount of data to be transferred over the wire quickly grows." — hubertlepicki, [Elixir Forum: Advantages of Ecto preloads with/without joins](https://elixirforum.com/t/advantages-of-ecto-preloads-with-without-joins/21751), April 19, 2019
- "If you're running a query that needs to check the related records anyways… you might be looking to retrieve all Timecards that have an associated TimecardData with a specific approver_id." — al2o3cr, [Elixir Forum: Advantages of Ecto preloads with/without joins](https://elixirforum.com/t/advantages-of-ecto-preloads-with-without-joins/21751), April 19, 2019

**Suggested challenge angles**:
- Convert a hand-written `inner_join: x in X, on: x.parent_id == p.id` to `join: x in assoc(p, :children)`.
- Add a named binding `as: :owner` to a join so a downstream `order_by: [asc: o.name]` compiles.
- Fix a broken `left_join` where the `where` clause nullified the outer behavior; move the condition into the `on` clause.
- Given a query that joins a `has_many` and selects the parent, dedupe rows without breaking aggregation semantics.
- Rewrite a multi-join query with three named bindings (`:user`, `:post`, `:comment`) where all three are referenced in `where` and `select`.

**Tier guidance**: Easy (convert to `assoc/2`), Medium (named bindings + downstream reference), Hard (left-join-filter-in-on-clause correctness), Legendary (multi-join + correlated subquery + no duplicates).

---

### Capability: `preloads`

**Description** (from README.md): Struct preloads (separate query) vs join preloads (single query); when each is appropriate; N+1 avoidance.

**Known Claude failure modes**:
- [HIGH] **Join-preloading `has_many` associations**, consuming ~10x more memory than the separate-query strategy. This is the single most-enforced Ecto rule in community Claude Code plugins.
- [HIGH] **Missing preloads entirely**, generating N+1 queries when iterating `Enum.map(users, & &1.posts)`.
- [HIGH] Using `Ecto.Repo.preload/3` in a loop instead of `Ecto.Query.preload/3` at query build time — forces a double query (and often more).
- [MED] Using `preload` with a join but not passing the bound variable via `preload: [posts: p]`, causing Ecto to re-query the associations despite the join (silent 2x).
- [MED] Missing deduplication when join-preloading: the join produces a Cartesian product which Ecto then has to merge, and the merge can elide expected duplicates.

**Citations**:
- "Separate queries for `has_many`, JOIN for `belongs_to`." — [oliver-kriska/claude-elixir-phoenix Iron Law](https://github.com/oliver-kriska/claude-elixir-phoenix)
- "Join preloads can use 10x more memory for has-many." — [georgeguimaraes/claude-code-elixir ecto-thinking SKILL](https://github.com/georgeguimaraes/claude-code-elixir)
- "Separate preloads work best for Has-many with many records (less memory) while Join preloads suit Belongs-to, has-one (single query)." — [georgeguimaraes/claude-code-elixir ecto-thinking SKILL](https://github.com/georgeguimaraes/claude-code-elixir)
- "Avoiding N+1 queries with Ecto is easy using `preload/3`" — Cory O'Daniel, [Medium: Ecto preloading subsets](https://medium.com/coryodaniel/til-ecto-preloading-subsets-ad9ad0490e80), February 11, 2018
- "An N+1 query with 200 users and 200 roles takes 20 seconds to load on my computer. Using the preload, this number is reduced to 600 milliseconds!" — [AppSignal: Tackling Performance Issues in Ecto Applications](https://blog.appsignal.com/2023/05/23/tackling-performance-issues-in-ecto-applications.html), May 23, 2023
- "you should try to avoid using `Ecto.Repo.preload/3`… The first issue with Repo.preload is that you are forced to double-query the database." — Austin Gatlin, [Gatlin.io: On an Ecto Preload Dilemma](https://www.gatlin.io/content/on-an-ecto-preload-dilemma), May 22, 2021
- "When you preload in the first case, Ecto is going to merge all duplicate entries." — José Valim, [elixir-ecto/ecto issue #1478](https://github.com/elixir-ecto/ecto/issues/1478)
- "I think this behaviour is very counter intuitive, I found myself with the exact same problem, I didn't know what was going on." — anonymous community member, [elixir-ecto/ecto issue #1478](https://github.com/elixir-ecto/ecto/issues/1478)

**Suggested challenge angles**:
- Given code that preloads `has_many` via `join: p in assoc(u, :posts), preload: [posts: p]` for 10,000 users × 50 posts, rewrite as a separate-query preload and measure/explain memory savings.
- Fix an N+1: a context function returns `Repo.all(User)` and the caller `Enum.map(&(&1.posts))`. Add a preload at query time.
- Replace `Repo.preload/2` in a loop with `Ecto.Query.preload/3` at the query-builder level.
- Given a join-preload that produces duplicates because the join binding was not threaded into `preload:`, correct the binding.
- Given a preload of a subset (only published posts), use the query-tuple preload syntax `{query, [:nested]}`.
- Force a legendary challenge: implement hybrid strategy — join-preload `belongs_to :author` but separate-preload `has_many :comments` — in one query function.

**Tier guidance**: Easy (add missing preload), Medium (switch strategy + justify), Hard (subset preload with filtering + deduplication), Legendary (hybrid strategy + correct binding threading + perf justification).

---

### Capability: `aggregates-and-group-by`

**Description** (from README.md): `count`, `sum`, `avg`, `max`, `min`, `group_by`, `having`.

**Known Claude failure modes**:
- [HIGH] Forgetting that `group_by` restricts the `select` list: any field in `select` must either appear in `group_by` or be wrapped in an aggregate function. Claude frequently writes `select: {u.name, u.email, count(p.id)}` and groups only by `u.id`.
- [MED] Using `where` instead of `having` to filter aggregated results (or vice versa) — the `where` clause runs before aggregation, `having` after.
- [MED] Calling `Repo.aggregate(query, :count)` when `count(distinct: true)` is actually needed.
- [MED] Counting by iterating: `length(Repo.all(query))` instead of `Repo.aggregate(query, :count, :id)`.

**Citations**:
- "Groups together rows from the schema that have the same values in the given fields. Using group_by 'groups' the query giving it different semantics in the select expression. If a query is grouped, only fields that were referenced in the group_by can be used in the select or if the field is given as an argument to an aggregate function." — [Ecto.Query hexdocs](https://hexdocs.pm/ecto/Ecto.Query.html)
- "having filters rows from the model, but after the grouping is performed giving it the same semantics as select for a grouped query." — [Ecto.Query hexdocs](https://hexdocs.pm/ecto/Ecto.Query.html)
- "A common pattern is to return the number of posts in each category using: `from(p in Post, group_by: p.category, select: {p.category, count(p.id)})`" — [Aggregates and subqueries hexdocs](https://hexdocs.pm/ecto/aggregates-and-subqueries.html)

**Suggested challenge angles**:
- Given a query selecting three non-aggregated fields with `group_by` on only one, fix the grouping.
- Replace `length(Repo.all(q))` with `Repo.aggregate(q, :count, :id)`.
- Write a top-N users by `count(p.id)` as a virtual field, returning a map shape.
- Use `having` to filter groups with `count(*) > 5`.
- Compose an aggregate `sum` with a joined table where one side could be nil (test `coalesce`).

**Tier guidance**: Easy (swap `where`→`having`), Medium (group + select shape fix), Hard (aggregate + preload interaction), Legendary (multi-group with window functions overlap).

---

### Capability: `subqueries`

**Description** (from README.md): `subquery/1`, correlated vs uncorrelated, exists/in/any patterns.

**Known Claude failure modes**:
- [HIGH] Reaching for raw SQL via `Ecto.Adapters.SQL.query/3` or `fragment("... IN (SELECT ...)", ...)` instead of using the typed `subquery/1` function.
- [HIGH] Missing `parent_as/1` for correlated subqueries — Claude typically forgets that Ecto has a dedicated binding reference mechanism for the outer query.
- [MED] Passing a schema directly where `subquery/1` is required (`from u in User, join: r in recent_users_query` instead of `join: r in subquery(recent_users_query)`).
- [MED] Not knowing that subqueries need `select:` explicitly specified when used as join sources, otherwise Ecto doesn't know the column shape.

**Citations**:
- "inner_query = `from c in Comment, where: parent_as(:posts).id == c.post_id`, and then `query = from p in Post, as: :posts, inner_lateral_join: c in subquery(inner_query)`" — [Aggregates and subqueries hexdocs](https://hexdocs.pm/ecto/aggregates-and-subqueries.html)
- "inner join can do the same without a subquery" — kylethebaker, [Elixir Forum: Ecto query in subquery](https://elixirforum.com/t/ecto-query-in-subquery/9096), October 4, 2017
- "take a look at the `subquery/2` function" — yurko, [Elixir Forum: Ecto query in subquery](https://elixirforum.com/t/ecto-query-in-subquery/9096), October 4, 2017
- "Ecto's support for lazy named bindings allows combining child and parent queries in subqueries, and since you have a proper subquery instead of a fragment, Ecto understands exactly what the subquery returns and correctly loads results into structs without extra mapping." — [Lateral joins in Ecto without fragments (justinappears.com)](https://justinappears.com/posts/lateral-joins-ecto)
- "`parent_as(:group)` can only be used in subqueries, and using it in CTE subqueries with the `with_cte` can cause a `Ecto.SubQueryError`." — [elixir-ecto/ecto issue #3619](https://github.com/elixir-ecto/ecto/issues/3619)

**Suggested challenge angles**:
- Replace a raw `fragment("... IN (SELECT ...)")` with `where: u.id in subquery(q)`.
- Write a correlated subquery using `parent_as(:user)` to return users whose latest post is within the last 7 days.
- Convert a hand-written two-query pattern (query1 for ids, query2 filtered by those ids) into a single `subquery/1`-based query.
- Compose a subquery that returns a ranked list and then join the outer query against it, selecting both sides.
- Legendary: build a lateral join with a correlated subquery and a window function inside the subquery.

**Tier guidance**: Easy (swap `fragment` for `subquery/1`), Medium (`parent_as` usage), Hard (lateral join with correlation), Legendary (lateral + window + named bindings).

---

### Capability: `dynamic-query-builder`

**Description** (from README.md): `Ecto.Query.dynamic/2` for runtime-conditional filters; composing dynamics.

**Known Claude failure modes**:
- [HIGH] Building queries by conditionally piping `Ecto.Query.where/2` calls in Elixir control-flow chains (`if params["name"], do: query = where(query, ...), else: query`) instead of using the canonical `Enum.reduce(params, dynamic(true), ...)` pattern.
- [HIGH] Using Elixir `||` and `&&` outside of `dynamic/2` instead of composing `and`/`or` inside dynamic fragments with pinned outer dynamics.
- [MED] Forgetting that `dynamic/2` needs a binding or named reference — Claude writes `dynamic(u.name == ^name)` without the `[u]` binding list.
- [MED] Recomposing dynamics incorrectly: `dynamic([u], ^existing_dynamic and u.active == true)` must explicitly pin the existing dynamic with `^`.

**Citations**:
- "Sometimes you want the contents of the where or order_by clauses themselves to be defined dynamically. By using dynamic fragments, you can decouple the processing of parameters from the query generation." — [Dynamic queries hexdocs](https://hexdocs.pm/ecto/dynamic-queries.html)
- "Because we were able to break our problem into smaller functions that receive regular data structures, we can use all the tools available in Elixir to work with data." — [Dynamic queries hexdocs](https://hexdocs.pm/ecto/dynamic-queries.html)
- "not all expressions can be converted to data structures. For example, `where` converts a key-value to a `key == value` comparison, and therefore order-based comparisons... need to be written as before." — [Dynamic queries hexdocs](https://hexdocs.pm/ecto/dynamic-queries.html)
- "`dynamic(true)` serves as the initial condition, allowing seamless composition." — Jonny Eberhardt, [Medium: Mastering Advanced Querying in Ecto](https://medium.com/@jonnyeberhardt7/mastering-advanced-querying-in-ecto-unlocking-the-full-potential-of-your-elixir-applications-cef83e1d363c), November 1, 2024

**Suggested challenge angles**:
- Build a search endpoint with 5 optional filters (`name`, `email`, `min_age`, `max_age`, `active`) using `Enum.reduce(params, dynamic(true), ...)`.
- Given a Claude-style chained `if/where` pattern, refactor into a dynamic-based composition.
- Compose two dynamics with `and`/`or` where one was already built and is pinned into the other.
- Handle `order_by` dynamically where only the direction varies between `:asc` and `:desc`.
- Legendary: dynamic query that sometimes needs a join (based on which filter is present) and thread the named binding through to the dynamic fragment.

**Tier guidance**: Easy (trivial single optional filter), Medium (reduce-based composition with 3-5 filters), Hard (dynamic composition with joins), Legendary (dynamic join + dynamic ordering + dynamic select).

---

### Capability: `pin-operator-safety` ⭐

**Description** (from README.md): `^` for interpolating variables; required for safety; the most common Claude bug.

**Known Claude failure modes**:
- [HIGH] **Omitting the pin entirely**: `where: u.id == user_id` instead of `where: u.id == ^user_id`. The raw-variable form either raises a cryptic compile error ("variable is not a valid query expression") or, if the variable name happens to match a binding, silently treats it as a binding reference.
- [HIGH] Pinning at compile-time constants unnecessarily, interfering with query plan caching and causing database-side performance regressions.
- [MED] Not understanding that `fragment/1` does **not** allow `^` for the first argument — you must use placeholders (`?`) and pass values separately.
- [MED] Silent type coercion: the pin coerces values to the schema-declared type, which can mask incorrect-type bugs at the caller.

**Citations**:
- "Always pinning values with `^` in queries" — [oliver-kriska/claude-elixir-phoenix Iron Law](https://github.com/oliver-kriska/claude-elixir-phoenix)
- "External values and Elixir expressions can be injected into a query expression with `^`." — [Ecto.Query hexdocs](https://hexdocs.pm/ecto/Ecto.Query.html)
- "Think of it as a safe interpolation operator: the Ecto query doesn't see your variables outside the from macro call unless you tell it to look outside itself." — KronicDeth, [Elixir Forum: Ecto the pin operator](https://elixirforum.com/t/ecto-the-pin-operator/1101), July 15, 2016
- "The pin operator makes it clear that the right hand side of the == is referring to the external u." — benwilson512, [Elixir Forum: Ecto the pin operator](https://elixirforum.com/t/ecto-the-pin-operator/1101), July 15, 2016
- "It was simply ignoring that I had to do with a string and coerced it into a integer… I thought the pin-operator was only for inserting values of variables, but now I know it also acts as a coercer (or interpolator)." — Lasse Skindstad Ebert, [Dev.to: TIL Ecto's pin is coercing](https://dev.to/lasseebert/til-ecto-s-pin-is-coercing-19fh), October 21, 2019
- "When the pin is present, the Ecto Query can often hang for many seconds or even time out." — michallepicki, [Elixir Forum: Ecto query often timing out when using a pin next to module attribute](https://elixirforum.com/t/ecto-query-often-timing-out-when-using-a-pin-next-to-module-attribute/40640), June 24, 2021
- "Without the pin the query should not use a parameter for the `@active_statuses`, but include the value in the query itself. The change to not using the pin operator has a profound overall impact on the performance." — hubertlepicki, [Elixir Forum (same thread)](https://elixirforum.com/t/ecto-query-often-timing-out-when-using-a-pin-next-to-module-attribute/40640), June 25, 2021
- "SQLite works properly, it starts scanning `s0` as it cannot determine the selectivity of the parameterized values" — regex.sh, [Elixir Forum: Ecto query slows down when using pin operator](https://elixirforum.com/t/ecto-query-slows-down-when-using-pin-operator/70597), April 24, 2025
- "The pin operator marks a value to be passed as a parameter to a query. If values change between executions, use it." — LostKobrakai, [Elixir Forum: Ecto query slows down when using pin operator](https://elixirforum.com/t/ecto-query-slows-down-when-using-pin-operator/70597), April 23, 2025

**Suggested challenge angles**:
- Add the missing `^` to 3-5 filter conditions.
- Given a query that times out because of inappropriate pinning of a compile-time constant, remove the pin and explain why.
- Convert `where: u.email == email` (which raises at compile time) into `where: u.email == ^email`.
- Write a multi-clause `where` where half the values come from a params map and half are module attributes — correctly pin only the runtime ones.
- Legendary: convert a query where a module attribute is inappropriately pinned, causing plan-cache performance regression on Postgres.

**Tier guidance**: Easy (add missing pin), Medium (multi-clause pin + type coercion awareness), Hard (when-to-pin-vs-inline tradeoff), Legendary (plan-cache aware + correct pin/no-pin per value).

---

### Capability: `pagination-patterns`

**Description** (from README.md): Offset-based vs cursor-based; tradeoffs and edge cases.

**Known Claude failure modes**:
- [HIGH] Defaulting to `offset`/`limit` pagination for large datasets without warning about the linear-scan cost of `OFFSET N`.
- [HIGH] Cursor pagination without a deterministic sort (e.g., only `order_by: [desc: :inserted_at]` when `inserted_at` is not unique), producing dropped or duplicated records across pages.
- [MED] Using `offset` + `limit` with an unindexed `order_by` column.
- [MED] Not pinning the cursor value, so filtering doesn't interpolate correctly.
- [MED] Forgetting that cursor pagination can't jump directly to a specific page.

**Citations**:
- "Query execution time grows proportionally to the number of rows you need to skip with offset-based pagination, because database engines scan those sequentially. In contrast, keyset- or cursor-based pagination relies on concrete values in columns which unlocks the power of indexing, so the 1000th page loads as quickly as the first." — [Jack Marchant: Offset and Cursor Pagination explained](https://www.jackmarchant.com/offset-cursor-pagination)
- "Offset-based pagination has two major drawbacks: inconsistent results (if the dataset changes while you are querying, the results in the page will shift), and inefficiency (OFFSET N instructs the database to skip the first N results, but the database must still fetch these rows from disk and order them before it can return the ones requested; if the dataset is large this will result in significant slowdowns)." — [duffelhq/paginator README](https://github.com/duffelhq/paginator)
- "This method requires a deterministic sort order; if the columns you are currently using for sorting don't match that definition, just add any unique column and extend your index accordingly." — [duffelhq/paginator README](https://github.com/duffelhq/paginator)
- "You need to add `:order_by` clauses yourself before passing your query to `paginate/2`." — [duffelhq/paginator README](https://github.com/duffelhq/paginator)
- "You can't jump directly to a specific page, though this may not be an issue for an API or if you use infinite scrolling on your website." — [duffelhq/paginator README](https://github.com/duffelhq/paginator)

**Suggested challenge angles**:
- Implement cursor-based pagination over a feed ordered by `(inserted_at desc, id desc)`.
- Given an offset-based pagination that's O(N) slow at page 1000, rewrite to keyset.
- Fix a cursor pagination bug caused by non-unique sort columns.
- Implement `load_more` with a properly-pinned cursor variable.
- Legendary: pagination over a joined, filtered, and aggregated feed with deterministic ordering and stable cursors.

**Tier guidance**: Easy (add missing tie-breaker), Medium (offset→cursor refactor), Hard (cursor on joined query), Legendary (cursor on aggregated query with stable ordering).

---

### Capability: `raw-sql-fragment`

**Description** (from README.md): When `fragment/1` is necessary as an escape hatch; safe vs unsafe interpolation.

**Known Claude failure modes**:
- [HIGH] **String interpolation inside the fragment literal**: `fragment("f0.quantity >= #{min_q}")` — SQL injection. Ecto compiler catches this at compile time, but Claude produces the pattern often.
- [HIGH] Trying to use `^` as the first fragment argument: `fragment(^query_string, ^val)` — deliberately disallowed.
- [HIGH] Reaching for `fragment` for things that have a typed equivalent (window functions, `coalesce`, `json_extract`, etc.).
- [MED] Missing that `unsafe_fragment/1` exists for the rare dynamic-SQL case, and that it's a security-sensitive last resort.
- [MED] Passing the wrong number of `?` placeholders for the values provided.

**Citations**:
- "fragment(...) does not allow strings to be interpolated as the first argument via the `^` operator. This is a deliberate design choice by the Ecto team. You must use placeholders (`?`) in your SQL expressions and pass the corresponding values as the second argument to fragment/2." — [Victor Björklund: A Guide to Using Fragments in Ecto](https://victorbjorklund.com/a-guide-to-fragments-in-ecto-elixir/)
- "If you're in a rare situation where the string that must be sent to the database is defined dynamically, you can use `unsafe_fragment/1` to bypass Ecto checks, but you should use it only as last resort and wisely." — [Ecto unsafe_fragment PR #2249](https://github.com/elixir-ecto/ecto/pull/2249)
- "Ecto, as a database wrapper for Elixir, provides Query DSL which is quite a good safeguard, making code resistant to SQL Injections through the usage of parametrized queries." — [Curiosum: SQL Injection Prevention in Elixir](https://curiosum.com/blog/sql-injections-vs-elixir)
- "Excessive use of fragment/1 can reduce the portability and maintainability of your code." — Jonny Eberhardt, [Medium: Mastering Advanced Querying in Ecto](https://medium.com/@jonnyeberhardt7/mastering-advanced-querying-in-ecto-unlocking-the-full-potential-of-your-elixir-applications-cef83e1d363c), November 1, 2024
- "String interpolation in Ecto fragment" flagged as SQL-injection security rule. — [oliver-kriska/claude-elixir-phoenix security rules](https://github.com/oliver-kriska/claude-elixir-phoenix)

**Suggested challenge angles**:
- Given `fragment("name ILIKE '%#{q}%'")`, convert to `fragment("name ILIKE ?", ^"%#{q}%")`.
- Replace a `fragment` usage with a typed equivalent (e.g., `fragment("COALESCE(?, ?)", x, y)` → `coalesce(x, y)`).
- Handle a case where `unsafe_fragment` is genuinely required (dynamic table name or column) and document why.
- Compose a JSON-extraction fragment with correct placeholder count.
- Legendary: combine fragment, pin operator, and a correlated subquery — all correctly.

**Tier guidance**: Easy (remove interpolation), Medium (parameterize placeholders), Hard (replace with typed equivalent), Legendary (unsafe_fragment with security justification).

---

### Capability: `window-functions`

**Description** (from README.md): `row_number`, `rank`, `lag`, `lead`, `partition_by`.

**Known Claude failure modes**:
- [HIGH] Using a fragment-based `row_number() OVER (...)` pattern instead of Ecto's typed `row_number() |> over(partition_by: ..., order_by: ...)`.
- [HIGH] Wrapping window fragments in `type/2` to cast the result — not a valid query expression pattern.
- [MED] Misusing the `windows:` clause when defining named window specs — Claude often tries to inline them where they don't belong.
- [MED] Attempting to parameterize column names in an `OVER (PARTITION BY ?)` fragment, causing PostgreSQL syntax errors.

**Citations**:
- "The proper way to use `row_number()` with `partition_by` is: `from p in Post, select: row_number() |> over(partition_by: p.category_id, order_by: p.date)`" — [Ecto.Query.WindowAPI hexdocs](https://hexdocs.pm/ecto/Ecto.Query.WindowAPI.html)
- "PG does not support quoted arguments there nor interpolations [in fragment-based OVER clauses]." — José Valim, [elixir-ecto/ecto issue #2281](https://github.com/elixir-ecto/ecto/issues/2281)
- "Write window function clauses directly in fragments without parameterization: `fragment(\"row_number() OVER (PARTITION BY user_id ORDER BY updated_at DESC)\")`." — José Valim, [elixir-ecto/ecto issue #2281](https://github.com/elixir-ecto/ecto/issues/2281)
- "`fragment(\"rank() OVER (PARTITION BY ? ORDER BY ? DESC NULLS LAST)\", group.id, score.score)`" — Eric Meadows-Jönsson, [elixir-ecto/ecto issue #2281](https://github.com/elixir-ecto/ecto/issues/2281)
- "Seems there is not actually in Ecto for a OVER PARTITION BY query syntax [in preload operations]." — obsidienne, [Elixir Forum: Fragment, SQL over partition by not working](https://elixirforum.com/t/fragment-sql-over-partition-by-not-working/3347), January 20, 2017

**Suggested challenge angles**:
- Replace `fragment("row_number() OVER (PARTITION BY ? ORDER BY ? DESC)", user_id, inserted_at)` with the typed `row_number() |> over(partition_by: ..., order_by: ...)`.
- Use the `windows:` clause to define a named window and reference it via `over(:window_name)`.
- Compose a ranked query using `rank()` then filter to `rank <= 3` per partition (subquery wrapping).
- Use `lag/lead` to compute a per-row delta against the previous row in a time-ordered feed.
- Legendary: correlated subquery with a window function inside, returning top-N per partition.

**Tier guidance**: Easy (typed row_number), Medium (named windows), Hard (rank + subquery filter), Legendary (lag/lead + correlated + named).

---

### Capability: `upserts-and-on-conflict`

**Description** (from README.md): `insert_all` with `on_conflict: :replace_all` / `:nothing` / replace lists.

**Known Claude failure modes**:
- [HIGH] Using `on_conflict: :replace_all` without `conflict_target`, causing the database to raise a cryptic SQL-level error rather than a clear Ecto error.
- [HIGH] Using `replace_all` on a partial changeset — Ecto writes NULLs for fields not in the changeset, silently clobbering existing data.
- [HIGH] NULL violations on NOT-NULL columns not included in the `insert_all` rows: PostgreSQL validates INSERT before evaluating ON CONFLICT, so `ON CONFLICT DO NOTHING` does **not** bypass required-field validation.
- [MED] `:replace_all` overwrites `inserted_at` on conflict (treating an update as a fresh insert), while a `{:replace, [...]}` list skips timestamps entirely if not named.
- [MED] `insert_all` bypasses changeset validation entirely — data integrity checks must be done upfront.

**Citations**:
- "`{:replace_all_except, [:other_field]}` with `conflict_target` may raise ArgumentError when `:other_field` is ONLY other field." — [elixir-ecto/ecto issue #4633](https://github.com/elixir-ecto/ecto/issues/4633), June 24, 2025
- "insert(on_conflict: :replace_all)'s documentation should warn that it writes nil for non-present properties." — [elixir-ecto/ecto issue #3334](https://github.com/elixir-ecto/ecto/issues/3334)
- "Upsert has unexpected effects on `timestamps`." — [elixir-ecto/ecto issue #2382](https://github.com/elixir-ecto/ecto/issues/2382)
- "It applies constraints as if a new row were being inserted, so even if the existing row + update clause are valid, the latter query will still error if it doesn't include all not null columns." — tfwright, [Elixir Forum: Upsert with insert_all and on_conflict causing null violation](https://elixirforum.com/t/upsert-with-insert-all-and-on-conflict-causing-null-violation-on-unspecified-field/36139), December 11, 2020
- "PostgreSQL requires all NOT NULL columns to be provided in an INSERT, even if the row already exists. `ON CONFLICT DO NOTHING` does NOT bypass this. Instead, the INSERT itself is invalid, so the query never proceeds to the `ON CONFLICT` clause." — benzene73, [Elixir Forum: Upsert with insert_all and on_conflict causing null violation](https://elixirforum.com/t/upsert-with-insert-all-and-on-conflict-causing-null-violation-on-unspecified-field/36139), February 26, 2025
- "Batch inserts bypass validation entirely, meaning data integrity checks must be handled manually before insertion." — [AppSignal: Batch Updates and Advanced Inserts in Ecto](https://blog.appsignal.com/2025/10/07/batch-updates-and-advanced-inserts-in-ecto-for-elixir.html), October 7, 2025
- "Database-level constraints like unique indexes can cause the entire batch to fail if even a single record violates them." — [AppSignal: Batch Updates and Advanced Inserts in Ecto](https://blog.appsignal.com/2025/10/07/batch-updates-and-advanced-inserts-in-ecto-for-elixir.html), October 7, 2025
- "If two posts are submitted at the same time with a similar tag, there is a chance we will check if the tag exists at the same time, leading both submissions to believe there is no such tag." — [Constraints and Upserts hexdocs](https://hexdocs.pm/ecto/constraints-and-upserts.html)

**Suggested challenge angles**:
- Fix an `insert_all` that's missing `conflict_target` on a table with multiple unique indexes.
- Replace `on_conflict: :replace_all` with a targeted `{:replace, [:name, :updated_at]}` to preserve NOT NULL fields not in the changeset.
- Handle the race condition of two concurrent inserts with `on_conflict` + returning.
- Use `insert_all` with `placeholders:` for a batch of tagged entities.
- Legendary: write an upsert that only updates if the incoming row's `updated_at` is newer than the existing one (needs `on_conflict:` with a dynamic query).

**Tier guidance**: Easy (add missing `conflict_target`), Medium (targeted replace list), Hard (race-safe get-or-insert), Legendary (conditional upsert with `on_conflict: query`).

---

## Research process notes

I searched public sources in three passes. Pass 1 was a scan for LLM-specific Ecto failure reports on Elixir Forum, HN, Reddit, and developer blogs — the direct "Claude wrote wrong Ecto" evidence is sparse because most Elixir+AI discussion focuses on higher-level concerns (OTP, concurrency, test isolation), not query-level bugs. Pass 2 leaned on the two community Claude Code plugins (oliver-kriska and georgeguimaraes), which encode observed Claude failures as enforcement rules — these are the richest source of specific Ecto failure modes, particularly the pin operator and preload strategy iron laws. Pass 3 filled in the capability-level evidence with official Ecto docs, GitHub issue discussions (especially José Valim explanations), and the Curiosum/Vereis/Medium composition-pattern blogs.

Where direct "Claude failure" evidence is thin (e.g., window functions, aggregates, pagination), I cited community-documented pain points that a pre-trained LLM is likely to reproduce because the correct Ecto pattern is non-obvious. This is slightly weaker than "BoothIQ saw Claude do X" but acceptable for challenge authoring: the goal is to exercise patterns where the Ecto API deviates from the generic SQL mental model the LLM brings.

The strongest three capabilities by evidence are `preloads`, `pin-operator-safety`, and `upserts-and-on-conflict`. The weakest two are `basic-where-select-order` (which barely has LLM-specific failure evidence; the community pain is elsewhere) and `aggregates-and-group-by` (documented as a general Ecto gotcha but not specifically observed as a Claude failure).

## Capability prioritization (Phase 2 output)

| Capability | Evidence strength | Recommended primary count | Rationale |
|---|---|---|---|
| `query-composition-style` (foundation) | MED | 12-14 | Foundation that affects everything else; strong composition/anti-pattern evidence, modest LLM-specific failure data. |
| `basic-where-select-order` | LOW | 12 | Lower bound — community pain is elsewhere. Still needed because most other capabilities build on these clauses. |
| `joins` | MED | 14 | Strong Ecto-specific gotchas (named bindings, left-join-filter), moderate LLM evidence. |
| `preloads` | HIGH | 16 | Highest-evidence capability. Plugin iron law + BoothIQ narrative + AppSignal perf data. Upper bound. |
| `aggregates-and-group-by` | LOW | 12 | Lower bound. Well-documented Ecto gotcha with thin direct LLM evidence. |
| `subqueries` | MED | 14 | `parent_as` and `subquery/1` are non-obvious API; Claude reaches for fragments. |
| `dynamic-query-builder` | MED | 14 | Reduce-based composition is the canonical pattern; Claude defaults to imperative chaining. |
| `pin-operator-safety` ⭐ | HIGH | 16 | Highest-confidence single fix; plugin iron law #1; silent-bug class. Upper bound. |
| `pagination-patterns` | MED | 14 | Strong community guidance on cursor-vs-offset; Claude defaults to offset. |
| `raw-sql-fragment` | HIGH | 14 | SQL-injection vector explicitly blocked by plugins; Ecto compile-time defense gives clean scoring signals. |
| `window-functions` | MED | 12-14 | Typed vs fragment-based forms diverge sharply; Claude chooses fragments. |
| `upserts-and-on-conflict` | HIGH | 16 | 4+ documented silent-bug modes; recent 2025 issues; NULL-violation behavior is counterintuitive. Upper bound. |

## Capabilities with insufficient public failure documentation

- `basic-where-select-order` — General Ecto gotchas exist (`is_nil/1`, `select` struct vs map) but no direct Claude-failure narrative in public sources. Mitigated by: Ecto's compile-time errors provide strong deterministic scoring signals. Challenges should rely on those signals rather than narrative evidence.
- `aggregates-and-group-by` — Well-documented Ecto quirks (grouped select restrictions, `having` vs `where`) but the only direct LLM complaint is the broader "Claude reaches for raw SQL for anything non-trivial" narrative, not specifically aggregates. Treat as corroborating evidence; lower-bound the primary count.
