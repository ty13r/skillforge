# elixir-ecto-sandbox-test — Per-Capability Research Dossier

**Generated**: 2026-04-11
**Workstream**: SKLD-bench v2.1 (see [`../SEEDING-PLAN.md`](../SEEDING-PLAN.md))
**Sources surveyed**: getboothiq.com, news.ycombinator.com, elixirforum.com, github.com (elixir-ecto, phoenix_live_view, phoenix_ecto, oliver-kriska, oban-bg), hexdocs.pm (ecto_sql, phoenix_ecto, oban, tidewave), blog.appsignal.com, dockyard.com, rakshanshetty.in, nimblehq.co, qertoip.medium.com, phoenixframework docs
**Total citations**: 47

## Family-level summary

`elixir-ecto-sandbox-test` is the "ugly" pain point directly named in the BoothIQ vibe-coded-Elixir post-mortem. It covers the surface area of `Ecto.Adapters.SQL.Sandbox`: per-test transaction isolation, the `:manual`/`:auto`/`:shared` mode triad, the `allow/3` pattern for background processes, connection ownership transfer across spawned tasks, and the layered integrations with Phoenix LiveView, Channels, and Oban. This is the family where Claude fails *in a way developers notice* — not as a style nit, but as a "your test suite is broken and the AI is making it worse" catastrophe.

The Sandbox architecture is the single most conceptually dense piece of the Elixir testing story. Matt's research notes and the BoothIQ post-mortem both capture the core failure: Claude doesn't internalize that tests run in isolated transactions that roll back, so when a test fails, Claude queries the database, sees an empty table, and starts "fixing" the wrong problem — often by seeding the test DB or disabling async tests. When Tidewave MCP is in the loop, this confusion compounds: Tidewave queries the dev database, Claude reads the dev DB state, and reasons about test failures as if that data was visible to the test process. It never is.

Claude tends to struggle in three distinct ways across this family: (1) *mode confusion* — confidently picking `:shared` mode as a panacea without understanding it forces `async: false`; (2) *ownership blindness* — spawning processes (Tasks, GenServers, Oban workers, channel processes) without realizing the connection is owned by the test process and not automatically shared; (3) *symptom-chasing* — when flaky tests appear, recommending `Process.sleep` or `async: false` instead of diagnosing the underlying connection leak. All three have been directly observed and documented in public sources.

The best challenges will stress-test variants on realistic idioms: a Task spawned from a LiveView needing `allow/3`, an Oban worker under `:inline` vs `:manual` testing mode, a channel test that needs `Phoenix.Ecto.SQL.Sandbox.allow/2` at join time, and diagnosis tasks where the fix is "reduce the ownership leak" rather than "disable async." Legendary-tier challenges should deliberately reproduce the Tidewave dev-vs-test trap from the BoothIQ post-mortem.

---

## Capability research

### Foundation: `test-isolation-philosophy`

**Description** (from README.md): How the skill frames test isolation: per-test-transaction (default Sandbox), per-process (manual checkout), or shared mode (only when isolation breaks down). Variants determine how every capability below presents tradeoffs.

**Known Claude failure modes**:
- [HIGH] Claude does not internalize that each test runs in its own rolled-back transaction — debugs failures by querying the live database and "finding" no data
- [HIGH] Claude recommends disabling async tests entirely as the first response to any isolation error instead of diagnosing ownership
- [MED] Claude attempts to seed the test database to force passing tests instead of recognizing transaction rollback
- [MED] Claude confuses dev DB state with test DB state when Tidewave MCP is in the loop

**Citations**:
- *"In Elixir tests, each test runs in a database transaction that rolls back at the end. Tests run async without hitting each other. No test data persists."* — [BoothIQ blog post](https://getboothiq.com/blog/150k-lines-vibe-coded-elixir-good-bad-ugly), 2026-01-07, John-BoothIQ
- *"Claude doesn't understand this. It uses Tidewave's dev DB connection and thinks it's looking at the test DB — which is always empty."* — [BoothIQ blog post](https://getboothiq.com/blog/150k-lines-vibe-coded-elixir-good-bad-ugly), 2026-01-07, John-BoothIQ
- *"A test fails. Claude queries the database. Finds nothing. Thinks there's a data problem."* — [BoothIQ blog post](https://getboothiq.com/blog/150k-lines-vibe-coded-elixir-good-bad-ugly), 2026-01-07, John-BoothIQ
- *"It can't debug concurrent test failures. It doesn't understand that each test runs in an isolated transaction"* — [Elixir Forum BoothIQ discussion](https://elixirforum.com/t/150-000-lines-of-vibe-coded-elixir-the-good-the-bad-and-the-ugly/73899), 2026-01-07, John-BoothIQ
- *"Claude doesn't understand transaction isolation—tests can't see each other's data. It confuses itself and recommends disabling async tests altogether."* — [BoothIQ blog post](https://getboothiq.com/blog/150k-lines-vibe-coded-elixir-good-bad-ugly), 2026-01-07, John-BoothIQ

**Suggested challenge angles**:
- Diagnose a failing test where Claude's natural instinct is to add seed data — correct answer is "this is rollback, not missing data"
- Fix a test suite where the previous agent turn wrapped everything in `async: false` — correct answer is to restore `async: true` and use `allow/3` at the specific ownership point
- Draft a DataCase template that demonstrates the `shared: not tags[:async]` pattern and explain why it works
- Diagnose a "passes alone, fails in suite" test where seed data from a non-async test bled into an async-tagged module

**Tier guidance**:
- Easy: Write a DataCase setup block that checks out the sandbox with the `shared: not tags[:async]` idiom
- Medium: Given a test that fails with "expected record not found," decide whether the fix is (a) seeding, (b) fixing ownership, or (c) adjusting async
- Hard: Given a test suite where one non-async test leaks connection state into the next async test, diagnose and fix the root cause without regressing concurrency
- Legendary: Reproduce the Tidewave dev-vs-test confusion — a test fails because Claude (the prior agent turn) read the dev DB via an MCP tool and fabricated "expected" test state

---

### Capability: `sandbox-checkout-and-modes`

**Description** (from README.md): `Ecto.Adapters.SQL.Sandbox.checkout/2`, `:manual` vs `:auto` vs `:shared` modes, when each is appropriate

**Known Claude failure modes**:
- [HIGH] Claude picks `:shared` mode as a fix for ownership errors without realizing it forces `async: false`
- [HIGH] Claude uses `checkout/2` in places where `start_owner!/2` would correctly cover unlinked-process lifecycles
- [MED] Claude does not know `:auto` mode is not appropriate for test isolation — it's a production-pool mode
- [MED] Claude places `checkout` and `mode(:shared)` calls in the wrong order in setup blocks

**Citations**:
- *"Shared mode allows a process to share its connection with any other process automatically, without relying on explicit allowances"* — [Ecto.Adapters.SQL.Sandbox docs](https://hexdocs.pm/ecto_sql/Ecto.Adapters.SQL.Sandbox.html)
- *"Using allowances - requires explicit allowances. Tests may run concurrently... Using shared mode - does not require explicit allowances. Tests cannot run concurrently"* — [Ecto.Adapters.SQL.Sandbox docs](https://hexdocs.pm/ecto_sql/Ecto.Adapters.SQL.Sandbox.html)
- *"changing the sandbox mode affects what happens when you call `checkout`, so these should likely be in the opposite order"* — [Elixir Forum: DynamicSupervisor and Ecto Sandbox](https://elixirforum.com/t/dynamicsupervisor-and-ecto-adapters-sql-sandbox-problem/49187), 2022-07-28, al2o3cr
- *"For shared mode the checkout actually has to happen first. The checkout requests go through a GenServer which will have its state set with the owner's connection when changing the mode to shared"* — [Elixir Forum: DynamicSupervisor and Ecto Sandbox](https://elixirforum.com/t/dynamicsupervisor-and-ecto-adapters-sql-sandbox-problem/49187), 2022-07-28, joey_the_snake
- *"The sandbox defaults to `:auto` mode, which is essentially 'no sandboxing'."* — [Elixir Forum: Trouble with Sandbox Mode for e2e tests](https://elixirforum.com/t/trouble-with-sandbox-mode-for-e2e-tests/68661), 2025-01-13, LostKobrakai
- *"`start_owner!/2` solves the problem of unlinked processes started in a test outliving the test process and causing ownership errors"* — [Ecto.Adapters.SQL.Sandbox docs](https://hexdocs.pm/ecto_sql/Ecto.Adapters.SQL.Sandbox.html)

**Suggested challenge angles**:
- Given a setup block with `mode(:shared)` called before `checkout`, detect the ordering bug
- Decide when `start_owner!/2` is preferable to `checkout/2` (hint: unlinked processes that outlive the test)
- Given a module that wants to stay `async: true`, decide whether `:manual` or `:shared` is appropriate
- Explain why `:auto` mode is useless in tests and what it's actually for

**Tier guidance**:
- Easy: Write the correct `Ecto.Adapters.SQL.Sandbox.checkout/2` + `mode(:shared)` call sequence
- Medium: Choose between `checkout/2` and `start_owner!/2` for a test that spawns an unlinked worker
- Hard: Fix a DataCase where a subtle ordering bug means `mode(:shared)` runs before checkout — and explain the state-machine reason it's wrong
- Legendary: Given a suite that mixes async-tagged and non-async-tagged modules, determine which mode each should use and justify why `shared: not tags[:async]` is the canonical idiom

---

### Capability: `async-test-safety-rules`

**Description** (from README.md): Which tests can be `async: true`, which can't, and why (sandbox + connection pool requirements)

**Known Claude failure modes**:
- [HIGH] Claude recommends disabling async as the universal fix for any test failure
- [HIGH] Claude pairs `async: true` with `mode(:shared)`, which is a contradiction — shared mode requires serial execution
- [MED] Claude does not tag non-isolatable tests with `async: false` and adds a comment explaining *why* (a best practice)
- [MED] Claude defaults new test modules to `async: false` out of caution, permanently losing concurrency gains

**Citations**:
- *"If a test sets the Ecto.Adapters.SQL.Sandbox to :shared mode, never run it asynchronously"* — [AppSignal: 8 Common Causes of Flaky Tests in Elixir](https://blog.appsignal.com/2021/12/21/eight-common-causes-of-flaky-tests-in-elixir.html), 2021-12-21
- *"Do not run those particular tests in async - this way they will use a shared connection"* — [Elixir Forum: Testing a GenServer with Ecto.Sandbox](https://elixirforum.com/t/testing-a-genserver-with-ecto-sandbox-cannot-find-ownership/5638), 2018-01-08, josevalim
- *"you are using the code above and also setting `async: true`. This means the sandbox won't enter shared mode"* — [Elixir Forum: DynamicSupervisor and Ecto Sandbox](https://elixirforum.com/t/dynamicsupervisor-and-ecto-adapters-sql-sandbox-problem/49187), 2022-07-28, joey_the_snake
- *"Whenever possible, always run the tests concurrently."* and *"In cases where we cannot run the test asynchronously, explicitly state `async: false` with a comment."* — [Nimble: Fast and stable test suite](https://nimblehq.co/blog/fast-and-stable-test-suite)
- *"The `shared: not tags[:async]` pattern controls connection ownership: async tests get exclusive connections, sync tests get shared ones."* — [Rakshan Shetty: Elixir Testing Patterns Ecto Sandbox](https://rakshanshetty.in/blog/elixir-testing-patterns-ecto-sandbox)

**Suggested challenge angles**:
- Detect and fix a test module that has both `async: true` and a `mode(:shared)` setup call
- Given a failing test that currently has `async: false`, determine whether the async mode is the root cause or a symptom of a deeper ownership bug
- Write the canonical `setup tags do ... shared: not tags[:async] ... end` idiom from scratch
- Given a module that writes to ETS and also checks out the sandbox, decide whether it can safely be `async: true`

**Tier guidance**:
- Easy: Write a data module's opening line with correct `use MyApp.DataCase, async: true` + explain when this is safe
- Medium: Diagnose a module that contradicts itself with `async: true` plus `mode(:shared)`
- Hard: Fix a test that's currently `async: false` but could be `async: true` if ownership were handled via `allow/3`
- Legendary: Given a suite where 30% of modules are `async: false` out of "caution," identify which ones could be reclaimed to `async: true` and which are genuinely unsafe (touches global state)

---

### Capability: `allow-pattern-for-spawned-processes`

**Description** (from README.md): `Ecto.Adapters.SQL.Sandbox.allow/3` for background processes that need DB access

**Known Claude failure modes**:
- [HIGH] Claude does not know `allow/3` exists and reaches for `:shared` mode as the only remedy
- [HIGH] Claude forgets to call `allow/3` when spawning a Task or GenServer inside a test
- [MED] Claude does not know `$callers` tracking makes `allow/3` unnecessary for processes spawned via `Task.async` inside the test process
- [MED] Claude places `allow/3` after the spawned process has already tried to query the DB (race)
- [LOW] Claude conflates `Phoenix.Ecto.SQL.Sandbox.allow/2` (HTTP metadata variant) with `Ecto.Adapters.SQL.Sandbox.allow/3` (PID variant)

**Citations**:
- *"by calling `allow/3`, we are explicitly assigning the parent's connection (i.e. the test process' connection) to the task"* — [Ecto.Adapters.SQL.Sandbox docs](https://hexdocs.pm/ecto_sql/Ecto.Adapters.SQL.Sandbox.html)
- *"Because allowances use an explicit mechanism, their advantage is that you can still run your tests in async mode."* — [Ecto.Adapters.SQL.Sandbox docs](https://hexdocs.pm/ecto_sql/Ecto.Adapters.SQL.Sandbox.html)
- *"Whenever the sandbox can track the caller using the `$callers` key in the process dictionary, it will try to use a DB connection from the caller, and no explicit allowances are needed."* — [Elixir Forum: How are DB connections passed](https://elixirforum.com/t/how-are-db-connections-passed-from-the-test-process-to-the-liveview-process-when-using-the-ecto-sandbox/47624), 2022-05-08, trisolaran
- *"Spawning a task will respect the $callers/$ancestors hierarchy, and find the correct task to use"* — [Elixir Forum: Integration tests, async tasks & Ecto Sandbox](https://elixirforum.com/t/integration-tests-async-tasks-dealing-with-ecto-sandbox-errors/25337), 2020-03-19, ityonemo
- *"background processes spawned manually, Tasks and GenServers do fail outputting that or similar error to the console"* — [Elixir Forum: Integration tests, async tasks & Ecto Sandbox](https://elixirforum.com/t/integration-tests-async-tasks-dealing-with-ecto-sandbox-errors/25337), 2019-09-12, hubertlepicki

**Suggested challenge angles**:
- Add the minimum `allow/3` call required to make a spawned `Task.Supervisor` child visible to the sandbox
- Recognize when `$callers` tracking is already solving the problem and `allow/3` is not required
- Given a test that starts a GenServer under a Task.Supervisor, choose between `allow/3` and restructuring to use `start_supervised` under the test supervisor
- Debug a race where `allow/3` is called too late and the spawned process has already queried

**Tier guidance**:
- Easy: Add the missing `Ecto.Adapters.SQL.Sandbox.allow(Repo, self(), pid)` call in a Task-spawning test
- Medium: Decide whether `allow/3` is needed given a `Task.async` call inside the test (hint: $callers)
- Hard: Restructure a test so an unlinked process's lifecycle doesn't outlive the test, avoiding the need for `allow/3` entirely
- Legendary: Diagnose a case where `allow/3` is called on the wrong PID because the developer passed the Task.Supervisor's PID instead of the worker PID

---

### Capability: `connection-ownership-transfer`

**Description** (from README.md): Passing ownership between processes; what happens when the owning process dies

**Known Claude failure modes**:
- [HIGH] Claude writes tests where child processes outlive the test owner, then blames "flakiness" instead of the lifecycle bug
- [HIGH] Claude does not use `Task.Supervisor` to guarantee worker termination before the test exits
- [MED] Claude performs DB writes in `on_exit` callbacks, which execute in a different process than the test owner
- [MED] Claude does not know that `checkin/2` or owner-process crash reclaims the connection

**Citations**:
- *"The process calling `checkout/2` will own the connection until it calls `checkin/2` or until it crashes in which case the connection will be automatically reclaimed"* — [Ecto.Adapters.SQL.Sandbox docs](https://hexdocs.pm/ecto_sql/Ecto.Adapters.SQL.Sandbox.html)
- *"These ownership errors usually happen when a GenServer outlives the process that called `checkout`"* — [Elixir Forum: DynamicSupervisor and Ecto Sandbox](https://elixirforum.com/t/dynamicsupervisor-and-ecto-adapters-sql-sandbox-problem/49187), 2022-07-28, al2o3cr
- *"you are using the code above and also setting `async: true`. This means the sandbox won't enter shared mode"* and *"you might try to start the genserver under the test supervisor so it doesn't outlive the individual test process"* — [Elixir Forum: DynamicSupervisor and Ecto Sandbox](https://elixirforum.com/t/dynamicsupervisor-and-ecto-adapters-sql-sandbox-problem/49187), 2022-07-28, CherryPoppins
- *"Make sure those tasks are terminated at the end of the test. This means you should start those tasks behind a Task.Supervisor"* — [Elixir Forum: Testing a GenServer with Ecto.Sandbox](https://elixirforum.com/t/testing-a-genserver-with-ecto-sandbox-cannot-find-ownership/5638), 2018-01-08, josevalim
- *"The issue is that `on_exit` is executed in a different process than the test one, which is not the owner of the sandbox DB connection."* — [Elixir Forum: Ecto Sandbox ownership issue when persisting state in terminate callback](https://elixirforum.com/t/ecto-sandbox-ownership-issue-when-persisting-state-in-terminate-callback/37645), 2021-02-18, totorigolo
- *"For us they were caused almost exclusively by async code spawned by liveviews...the test process finished and exited before their async tasks could finish running"* — [Elixir Forum BoothIQ discussion](https://elixirforum.com/t/150-000-lines-of-vibe-coded-elixir-the-good-the-bad-and-the-ugly/73899), 2026-01-12, egeersoz

**Suggested challenge angles**:
- Fix a test where a GenServer started with `start_link` outlives the test and causes an ownership error on shutdown
- Move a stray DB write out of `on_exit` into the main test body where the owning process is correct
- Given a test that flakes only when run after another specific test, diagnose the escaped child process
- Rewrite a `Task.async_stream` consumer so all children terminate before the test returns

**Tier guidance**:
- Easy: Convert `Task.start/1` to `Task.Supervisor.async/2` under the test's existing supervisor
- Medium: Move a DB write from `on_exit` to a `setup` block to respect ownership
- Hard: Fix a suite where a LiveView test's async assign spawns a worker that outlives the test process
- Legendary: Given a test that passes in isolation but flakes under `--trace`, identify the stray process that's leaking connections and fix it without breaking test determinism

---

### Capability: `liveview-sandbox-integration`

**Description** (from README.md): Sandbox config for `Phoenix.LiveViewTest`; the special pattern of `Phoenix.Ecto.SQL.Sandbox` plug

**Known Claude failure modes**:
- [HIGH] Claude does not place `Phoenix.Ecto.SQL.Sandbox` plug at the TOP of `endpoint.ex` before other plugs
- [HIGH] Claude forgets to declare `:user_agent` in the LiveView socket `connect_info`
- [HIGH] Claude does not write an `on_mount` hook that calls `Phoenix.Ecto.SQL.Sandbox.allow/2` for LiveView processes
- [MED] Claude orders `on_mount` hooks so that the sandbox hook runs *after* hooks that need DB access (e.g. auth)
- [MED] Claude assumes `$callers` tracking covers LiveView processes automatically — it only does so via the metadata header plumbing
- [MED] Claude forgets to call `render_async/1` for `assign_async`, producing silent assertion failures unrelated to the sandbox

**Citations**:
- *"For us they were caused almost exclusively by async code spawned by liveviews...the test process finished and exited before their async tasks could finish running"* — [Elixir Forum BoothIQ discussion](https://elixirforum.com/t/150-000-lines-of-vibe-coded-elixir-the-good-the-bad-and-the-ugly/73899), 2026-01-12, egeersoz
- *"It's important that this is at the top of `endpoint.ex`, before any other plugs."* — [Phoenix.Ecto.SQL.Sandbox docs](https://hexdocs.pm/phoenix_ecto/Phoenix.Ecto.SQL.Sandbox.html)
- *"If you have other `on_mount` hooks in `live_session` defined in your router (such as authentication hooks), make sure the sandbox acceptance hook runs first, so following hooks have access to the Ecto Sandbox."* — [Phoenix.Ecto.SQL.Sandbox docs](https://hexdocs.pm/phoenix_ecto/Phoenix.Ecto.SQL.Sandbox.html)
- *"The problem is that the task does not use the sandbox."* and *"I thought that the sandbox would use the `:\"$callers\"` to automatically allow tasks to access it"* — [phoenix_ecto issue #157](https://github.com/phoenixframework/phoenix_ecto/issues/157), 2022-08-12, SteffenDE
- *"You still need to run in manual mode or shared mode. Without manual mode or shared mode, each process will automatically checkout a connection."* — [phoenix_ecto issue #157](https://github.com/phoenixframework/phoenix_ecto/issues/157), 2022-08-14, josevalim
- *"The sandbox uses the mechanic described here to track the caller (aka the test process) for a LV... With that pid as key it can fetch the connection checked out by that process."* — [Elixir Forum: How are DB connections passed](https://elixirforum.com/t/how-are-db-connections-passed-from-the-test-process-to-the-liveview-process-when-using-the-ecto-sandbox/47624), 2022-05-08, LostKobrakai

**Suggested challenge angles**:
- Write a LiveView `on_mount` sandbox hook that uses `get_connect_info/2` and calls `Phoenix.Ecto.SQL.Sandbox.allow/2`
- Fix an `endpoint.ex` where the sandbox plug is mispositioned below session/auth plugs
- Add `:user_agent` to the socket `connect_info` option
- Fix a LiveView test that fails silently because `render_async/1` was not called after `assign_async`
- Reorder `on_mount` hooks in a `live_session` so the sandbox hook precedes an auth hook that queries the DB

**Tier guidance**:
- Easy: Add the `connect_info: [:user_agent, session: @session_options]` option to the socket definition
- Medium: Write an `on_mount` hook that checks the user-agent metadata and calls `Phoenix.Ecto.SQL.Sandbox.allow/2`
- Hard: Fix a test where a Task spawned from a LiveView hits `DBConnection.OwnershipError` because the plug was never wired correctly
- Legendary: Diagnose a LiveView test that flakes only under `assign_async` — the root cause is a spawned task that outlives the LiveView process itself, not a sandbox plug issue

---

### Capability: `channels-sandbox-integration`

**Description** (from README.md): Sandbox for `Phoenix.ChannelTest`; allow on the channel process

**Known Claude failure modes**:
- [HIGH] Claude does not call `Phoenix.Ecto.SQL.Sandbox.allow/2` at the start of `join/3`
- [HIGH] Claude does not declare `connect_info: [:user_agent]` on the socket definition for channels
- [MED] Claude assumes `ChannelCase` handles sandbox propagation automatically
- [MED] Claude writes channel tests with `async: true` that silently race the sandbox allowance
- [LOW] Claude forgets to assign the sandbox metadata onto the socket in `connect/3`

**Citations**:
- *"You need to explicitly allow the channel process. We will need to find a way to integrate this with Phoenix."* — [Ecto issue #1319](https://github.com/elixir-ecto/ecto/issues/1319), 2016-03-15, josevalim
- *"`allow/2` needs to be manually called once for each channel, at best directly at the start of `c:Phoenix.Channel.join/3`"* — [Phoenix.Ecto.SQL.Sandbox docs](https://hexdocs.pm/phoenix_ecto/Phoenix.Ecto.SQL.Sandbox.html)
- *"To support channels, you need to make it so each channel is allowed within the sandbox. To do so, you must declare that you want to pass connection information to your socket."* — [Phoenix.Ecto.SQL.Sandbox docs](https://hexdocs.pm/phoenix_ecto/Phoenix.Ecto.SQL.Sandbox.html)
- *"I don't think we should talk about Phoenix channels in Ecto docs but no worries, we will figure it out before Ecto 2.0 is released and adapt Phoenix accordingly."* — [Ecto issue #1319](https://github.com/elixir-ecto/ecto/issues/1319), 2016-03-16, josevalim

**Suggested challenge angles**:
- Add the missing `allow_ecto_sandbox(socket)` helper call to a channel's `join/3`
- Add `:connect_info: [:user_agent]` to the socket definition for a channel
- Diagnose a channel test that has `async: true` but forgets the channel-level allow — explain why it sometimes passes
- Extract the sandbox allowance logic into a reusable helper module

**Tier guidance**:
- Easy: Add `Phoenix.Ecto.SQL.Sandbox.allow(socket.assigns.phoenix_ecto_sandbox, Ecto.Adapters.SQL.Sandbox)` at the start of `join/3`
- Medium: Wire connect_info metadata through `connect/3` into the socket assigns for later channel use
- Hard: Diagnose a channel test that passes locally but fails in CI because the sandbox allowance helper was not called for the newly joined channel
- Legendary: Given a multi-channel test (user joins lobby, then a room), ensure each channel's sandbox allowance is called exactly once and in the right order

---

### Capability: `oban-sandbox-integration`

**Description** (from README.md): Testing Oban workers that hit the DB: inline mode vs manual mode

**Known Claude failure modes**:
- [HIGH] Claude does not know Oban supports `:inline` and `:manual` testing modes — writes tests that start real queues
- [HIGH] Claude uses `Oban.drain_queue/1` without understanding it competes with sandbox transactions
- [MED] Claude cannot switch modes mid-test with `Oban.Testing.with_testing_mode/2`
- [MED] Claude uses `perform_job/3` with atom keys, causing the helper to reject the args
- [MED] Claude expects jobs inserted in a sandbox transaction to be visible to an external Oban queue runner (they never commit)
- [LOW] Claude does not understand why tests using `start_supervised_oban!/1` need explicit allowances

**Citations**:
- *"Sandbox transactions never commit. If they never commit, then the rows are never visible to other processes, and that means they are never visible to Oban."* — [Elixir Forum: Is it possible to have Oban running jobs normally with Sandbox](https://elixirforum.com/t/is-it-possible-to-have-oban-running-the-jobs-normally-with-ecto-sandbox/55372), 2023-04-18, benwilson512
- *"It's possible to run Oban normally in acceptance tests using a setup similar to the one you showed above, provided you're doing everything within the same transaction."* — [Elixir Forum: Is it possible to have Oban running jobs normally with Sandbox](https://elixirforum.com/t/is-it-possible-to-have-oban-running-the-jobs-normally-with-ecto-sandbox/55372), 2023-04-18, sorentwo
- *"Oban Pro has a dedicated start_supervised_oban!/1 helper to facilitate acceptance testing within the sandbox."* — [Elixir Forum: Is it possible to have Oban running jobs normally with Sandbox](https://elixirforum.com/t/is-it-possible-to-have-oban-running-the-jobs-normally-with-ecto-sandbox/55372), 2023-04-18, sorentwo
- *"Both testing modes prevent Oban from running any database queries in the background. This simultaneously prevents Sandbox errors from plugin queries and prevents queues from executing jobs unexpectedly."* — [Oban testing docs](https://hexdocs.pm/oban/testing.html)
- *"`:inline`—jobs execute immediately within the calling process and without touching the database. This mode is simple and may not be suitable for apps with complex jobs."* — [Oban testing docs](https://hexdocs.pm/oban/testing.html)

**Suggested challenge angles**:
- Convert a test from real-queue Oban to `testing: :manual` mode with `assert_enqueued`
- Use `perform_job/3` correctly with string-keyed args (Oban auto-converts, but Claude often constructs atom args directly)
- Diagnose a test where `Oban.drain_queue/1` never picks up sandboxed jobs — explain the commit problem
- Use `Oban.Testing.with_testing_mode(:manual, fn -> ... end)` to temporarily switch modes inside an otherwise-inline suite

**Tier guidance**:
- Easy: Configure `Oban` with `testing: :manual` in `config/test.exs`
- Medium: Write a `perform_job/3` invocation with correct string-key args and assertion
- Hard: Fix a test that expected `Oban.drain_queue/1` to pick up sandbox-inserted jobs — replace with `perform_job/3` or manual mode
- Legendary: Build a test setup that mixes `:inline` mode for most tests but uses `with_testing_mode(:manual, fn -> ... end)` for a subset that verifies scheduled/delayed jobs

---

### Capability: `tidewave-dev-vs-test-trap`

**Description** (from README.md): The specific BoothIQ-named bug: don't read from dev DB connection in test context

**Known Claude failure modes**:
- [HIGH] When using Tidewave MCP, Claude queries the dev database and reasons about the result as if it were test state
- [HIGH] Claude sees empty test DB state after a test rollback and concludes the test must be broken rather than recognizing normal isolation
- [MED] Claude does not understand Tidewave is a dev-only tool and attempts to use it while reasoning about test runs
- [MED] Claude fabricates "expected" data based on dev DB rows observed via Tidewave, then wonders why the test doesn't find them

**Citations**:
- *"Claude doesn't understand this. It uses Tidewave's dev DB connection and thinks it's looking at the test DB — which is always empty."* — [BoothIQ blog post](https://getboothiq.com/blog/150k-lines-vibe-coded-elixir-good-bad-ugly), 2026-01-07, John-BoothIQ
- *"A test fails. Claude queries the database. Finds nothing. Thinks there's a data problem."* — [BoothIQ blog post](https://getboothiq.com/blog/150k-lines-vibe-coded-elixir-good-bad-ugly), 2026-01-07, John-BoothIQ
- *"I've watched Claude try to seed the test database so a test will pass. That's clearly wrong."* — [BoothIQ blog post](https://getboothiq.com/blog/150k-lines-vibe-coded-elixir-good-bad-ugly), 2026-01-07, John-BoothIQ
- *"Never use Tidewave tools in production contexts. Avoid on shared dev servers with production data copies"* — [oliver-kriska/claude-elixir-phoenix tidewave-integration SKILL.md](https://github.com/oliver-kriska/claude-elixir-phoenix/blob/main/plugins/elixir-phoenix/skills/tidewave-integration/SKILL.md)
- *"It'll happily rewrite code it thinks it needs if it doesn't know where it exists...It's a little bit like onboarding a junior dev with amnesia every day"* — [Elixir Forum BoothIQ discussion](https://elixirforum.com/t/150-000-lines-of-vibe-coded-elixir-the-good-the-bad-and-the-ugly/73899), 2026-01-07, John-BoothIQ

**Suggested challenge angles**:
- Given a failing test and a Tidewave query result showing populated dev DB rows, reason *correctly* that the test DB is isolated and the dev state is irrelevant
- Refuse to seed the test database in response to "missing data" — explain why rollback is working as designed
- Recognize that a test failure's "missing row" is actually a symptom of a failing `insert/2`, not a test DB seed issue
- Answer: "Why does Tidewave show rows for this user but the test says not found?"

**Tier guidance**:
- Easy: Given a test failure message, state whether the fix is "seed the test DB" or "check the test's own insert path" (always the latter)
- Medium: Reject a seed-the-test-DB PR and explain why it's masking the real bug
- Hard: Diagnose a flaky test where the previous Claude turn added `Repo.insert!` seed data that now collides with async tests' data
- Legendary: Given a multi-turn conversation where a prior Claude turn queried Tidewave and fabricated expected data, recognize the trap and correctly reason "the dev DB doesn't exist inside the test's transaction"

---

### Capability: `shared-mode-fallback`

**Description** (from README.md): When per-process isolation truly breaks down and shared mode is unavoidable; what you give up

**Known Claude failure modes**:
- [HIGH] Claude reaches for `:shared` mode first instead of trying `allow/3` or restructuring
- [HIGH] Claude uses `:shared` mode without also marking the module `async: false` — these must pair
- [MED] Claude does not know why shared mode forces serial execution (owner must outlive all dependents)
- [MED] Claude uses shared mode for channel or LiveView tests when a simpler allow/2 would work

**Citations**:
- *"Using allowances - requires explicit allowances. Tests may run concurrently... Using shared mode - does not require explicit allowances. Tests cannot run concurrently"* — [Ecto.Adapters.SQL.Sandbox docs](https://hexdocs.pm/ecto_sql/Ecto.Adapters.SQL.Sandbox.html)
- *"tests can no longer run concurrently in shared mode... beware that if the test process terminates while the worker is using the connection, the connection will be taken away"* — [Ecto.Adapters.SQL.Sandbox docs](https://hexdocs.pm/ecto_sql/Ecto.Adapters.SQL.Sandbox.html)
- *"The shared mode works exactly how things used to work in Ecto 1.x."* and *"we give up running db-tests in parallel, which is a sad compromise on Erlang VM. But we do have a convenient and clean environment for running tests."* — [Piotr Włodarek: Making Sense of Ecto 2 SQL.Sandbox](https://qertoip.medium.com/making-sense-of-ecto-2-sql-sandbox-and-connection-ownership-modes-b45c5337c6b7), 2016-03-03
- *"In the manual mode the child processes do not have any db connection assigned and soon crash with an — admittedly — very informative error message."* — [Piotr Włodarek: Making Sense of Ecto 2 SQL.Sandbox](https://qertoip.medium.com/making-sense-of-ecto-2-sql-sandbox-and-connection-ownership-modes-b45c5337c6b7), 2016-03-03
- *"A shared sandbox results in the data leaking from one test to another, which could make the test suite unstable in asynchronous mode"* — [Nimble: Fast and stable test suite](https://nimblehq.co/blog/fast-and-stable-test-suite)

**Suggested challenge angles**:
- Given a test currently in shared mode, determine whether it could be refactored to allow/3 and reclaim `async: true`
- Explain why `:shared` mode requires `async: false` — cite the owner-outlive-dependent constraint
- Fix a module that uses `:shared` mode but still has `async: true` in its `use ExUnit.Case` line
- Given 10 tests, decide which should use shared mode and why

**Tier guidance**:
- Easy: Mark a module that uses `:shared` mode as `async: false`
- Medium: Justify in a comment why a specific test module must use shared mode (e.g., touches a GenServer registry that can't accept allowances)
- Hard: Refactor a shared-mode test to use allow/3 instead so the module can reclaim `async: true`
- Legendary: Given a suite with 15 shared-mode modules, identify which are truly unavoidable and which are historical workarounds

---

### Capability: `flaky-test-diagnosis`

**Description** (from README.md): Recognizing test bleed between tests, identifying connection leaks, debugging "it passes alone but fails in suite"

**Known Claude failure modes**:
- [HIGH] Claude's first response to flakiness is `Process.sleep/1` instead of diagnosing the ownership/state leak
- [HIGH] Claude disables async before diagnosing the cause
- [MED] Claude does not recognize that stray ETS writes, `Application.put_env` in async tests, or shared Mox globals are the actual culprits
- [MED] Claude does not use `--seed` or `--trace` to reproduce order-dependent flakiness
- [LOW] Claude does not suggest generating unique test data with UUIDs to avoid unique-constraint collisions

**Citations**:
- *"All flaky tests boil down to one thing: non-determinism. Non-determinism is when the same input can produce different results."* — [AppSignal: 8 Common Causes of Flaky Tests in Elixir](https://blog.appsignal.com/2021/12/21/eight-common-causes-of-flaky-tests-in-elixir.html), 2021-12-21
- *"If tests pass with `--seed` but fail randomly, you have state leakage between tests."* — [oliver-kriska/claude-elixir-phoenix testing/references/exunit-patterns.md](https://github.com/oliver-kriska/claude-elixir-phoenix/blob/main/plugins/elixir-phoenix/skills/testing/references/exunit-patterns.md)
- *"No Process.sleep"* and *"Use `assert_receive` with timeout for async operations"* — [oliver-kriska/claude-elixir-phoenix testing/SKILL.md](https://github.com/oliver-kriska/claude-elixir-phoenix/blob/main/plugins/elixir-phoenix/skills/testing/SKILL.md) (Iron Law)
- *"If your data should be unique, make it unique across all tests"* — [AppSignal: 8 Common Causes of Flaky Tests in Elixir](https://blog.appsignal.com/2021/12/21/eight-common-causes-of-flaky-tests-in-elixir.html), 2021-12-21
- *"It's impossible to know without seeing your code but this generally happens because one test is causing persisting side effects that another test is reading."* — [Elixir Forum: A single test passes but fails in suite](https://elixirforum.com/t/a-single-test-passes-but-if-i-run-the-whole-test-suite-the-same-test-fails/61767), 2024-02-20, sodapopcan
- *"Claude Code doesn't know... that Oban jobs might not be idempotent"* — [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix) Iron Law catalog

**Suggested challenge angles**:
- Given a test that fails only when run after a specific other test, identify the side-effect source
- Replace a `Process.sleep(100)` with `assert_receive` + timeout
- Diagnose a suite where one test writes to `Application.put_env` in async context, poisoning another
- Generate unique test data with UUIDs to resolve a unique-constraint collision between concurrent tests
- Given a "passes alone, fails in suite" case, determine whether the bug is (a) connection leak, (b) ETS state leak, (c) unique-constraint collision, or (d) Mox global mode

**Tier guidance**:
- Easy: Replace `Process.sleep(100)` with `assert_receive(msg, 200)`
- Medium: Given `mix test --seed 1234` reproduces flakiness but other seeds don't, identify the order-dependent test pair
- Hard: Fix a suite where an earlier async test leaks unique-constraint data, collisioning a later test in the same module
- Legendary: Diagnose a case where the flakiness is caused by a stray GenServer started in setup_all that outlives one test's connection checkout — the root cause is three layers deep

---

## Research process notes

The richest material came from three sources: (1) the BoothIQ post-mortem and its HN/Elixir Forum discussions, which contain the only verbatim *developer narrative* quotes about Claude specifically failing on the sandbox; (2) the official `Ecto.Adapters.SQL.Sandbox` and `Phoenix.Ecto.SQL.Sandbox` documentation, which frame the tradeoffs Claude consistently misses; and (3) the oliver-kriska `claude-elixir-phoenix` plugin's testing SKILL.md, whose Iron Laws are themselves documented Claude failures. José Valim's own comments (2016, 2018, 2022) across Ecto GitHub issues and Elixir Forum threads give the authoritative "you should do X" rationale for allow/3 and shared mode, corroborating what the docs state more abstractly.

Thin areas: the `channels-sandbox-integration` and `oban-sandbox-integration` capabilities have strong documentation but few organic developer-complaint quotes. The `tidewave-dev-vs-test-trap` capability has exactly one primary source (BoothIQ) for the specific Claude failure — but that source is canonical and the BoothIQ quotes in this dossier are the strongest single body of evidence in the entire family. The `shared-mode-fallback` capability relies heavily on the Piotr Włodarek blog post (2016) and Dockyard's "Understanding Test Concurrency" post (2019) — older but still the best explanatory sources.

Cross-cutting themes: (1) the single most frequent anti-fix Claude reaches for is `async: false`, which appears across every capability; (2) the `$callers`/`$ancestors` caller-tracking feature is well-documented but Claude rarely knows it exists, so variants should mention it; (3) the BoothIQ post-mortem is the one place where "Claude + Tidewave + test DB" is documented as a failure mode, and every challenge in `tidewave-dev-vs-test-trap` should either cite that quote or evoke it.

## Capability prioritization (Phase 2 output)

| Capability | Evidence strength | Recommended primary count | Rationale |
|---|---|---|---|
| `test-isolation-philosophy` (foundation) | HIGH | 14 rich | Canonical BoothIQ quote + multiple corroborating forum voices; this is the philosophical core |
| `sandbox-checkout-and-modes` | HIGH | 14 rich | Three modes + ordering bug + start_owner — rich surface area, well-documented |
| `async-test-safety-rules` | HIGH | 15 rich | Strongest evidence of Claude's "disable async" anti-reflex; cited by BoothIQ + plugin iron laws |
| `allow-pattern-for-spawned-processes` | HIGH | 16 rich | Highest gap: Claude doesn't know the function exists; corroborated by José + hubertlepicki + docs |
| `connection-ownership-transfer` | HIGH | 15 rich | Direct BoothIQ LiveView + async task quote; multiple forum threads show this pattern |
| `liveview-sandbox-integration` | HIGH | 16 rich | Overlap with LiveView family; egeersoz quote is definitive; multi-step integration errors common |
| `channels-sandbox-integration` | MED | 12 rich | Strong docs, thin organic complaints; rely on docs + José's 2016 quote |
| `oban-sandbox-integration` | MED | 13 rich | Strong docs + sorentwo/benwilson512 quotes; adjacent to oban family (secondary tagging) |
| `tidewave-dev-vs-test-trap` | HIGH | 14 rich | Single primary source but canonical; legendary-tier challenges should feature this prominently |
| `shared-mode-fallback` | MED | 12 rich | Older sources but conceptually crucial; often the "last resort" capability |
| `flaky-test-diagnosis` | MED | 15 rich | Broadly documented across multiple sources; rich enough to absorb cross-cutting challenges |

**Total estimated primary challenges**: ~156 primary-tagged challenges (above the ~150 target). With ~1.5x overlap from secondary capability tags, effective coverage will be ~234 capability-challenge pairs.

## Capabilities with insufficient public failure documentation

None of the 11 dimensions fell below the threshold for research coverage, though the following are on the thinner side and drafting should lean on textbook idioms more than adversarial scenarios:

- `channels-sandbox-integration` — docs are strong, but there are few "here's how Claude broke this" narrative quotes. Challenges should target the textbook `allow` call in `join/3` and the socket connect_info plumbing.
- `shared-mode-fallback` — evidence is older (2016-2019). Challenges should lean on the canonical "shared mode requires async: false" rule rather than recent bug reports.
- `oban-sandbox-integration` — richly documented by Oban maintainers but most developer complaints are subsumed under the general Oban family. Challenges here should target the specific sandbox interaction (inline vs manual mode, perform_job, the commit-visibility problem).
