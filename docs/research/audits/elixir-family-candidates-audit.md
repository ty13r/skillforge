# Elixir skill family audit: 34 new candidates across the ecosystem

**The Elixir ecosystem contains at least 34 distinct skill families not yet covered by your existing 22**, spanning safe migrations, HTTP client configuration, GraphQL resolvers, authentication integration, and deep Erlang/OTP layer concerns. Research across ElixirForum, GitHub issues, Hex.pm, conference talks, blog posts, and LLM-specific complaints reveals consistent pain points that cluster into testable, independently evolvable domains. The strongest candidates—safe Ecto migrations, Task concurrency, HTTP client composition, and Absinthe resolver patterns—each have **4+ independent evidence sources** and affect the majority of Elixir developers. LLMs perform disproportionately worse on Elixir than on Python/JS due to smaller training corpora and OTP-specific paradigms, making skill-based guidance especially impactful.

---

## Tier 1 — High confidence: multiple sources, broad reach, clearly testable

### 1. `elixir-ecto-safe-migration`
**Description:** Teaches safe PostgreSQL migration patterns that avoid production-locking DDL operations in Ecto migrations.

**Evidence sources:** Fly.io 4-part guide (fly.io/phoenix-files/safe-ecto-migrations/), ElixirConf 2025 talk "Beyond Safe Migrations," GitHub repository fly-apps/safe-ecto-migrations, Ecto SQL issues #365 and #31.

**Pain point summary:** Adding indexes without `@disable_ddl_transaction true` and `concurrently: true` acquires ACCESS EXCLUSIVE locks that block all reads and writes on production tables. Developers also fail to use the two-step pattern for NOT NULL constraints, skip `lock_timeout` settings, and use `modify/3` which rewrites entire tables. Cars.com and other production teams have shared war stories about migrations taking down services.

**Estimated community reach:** **80%+** — every production Elixir app runs migrations against PostgreSQL.

**Overlap check:** Existing ecto families cover queries (`ecto-query-writer`), schemas/changesets (`ecto-schema-changeset`), and sandbox testing (`ecto-sandbox-test`). None addresses DDL lock safety, concurrent indexing, or migration ordering.

**Testability assessment:** Highly testable. A `score.py` could parse migration files checking for: `concurrently: true` on index creation, `@disable_ddl_transaction true` paired with concurrent operations, two-step NOT NULL constraint pattern (add column nullable → backfill → validate), presence of `lock_timeout` in `execute` statements, absence of `modify/3` for large tables, and correct use of `Ecto.Migration.flush/0` between dependent operations.

---

### 2. `elixir-task-async`
**Description:** Enforces correct use of Task.async/await, Task.Supervisor, and Task.async_stream with proper timeout handling, supervision, and error propagation.

**Evidence sources:** Elixir official Task docs, ElixirForum threads on async_stream confusion (elixirforum.com/t/task-async-stream-not-using-all-cores-solved-ish/61131), DEV.to deep dives, Exercism Elixir Tasks concept, blog posts on cascading Task crashes.

**Pain point summary:** Developers write sequential `Task.await` calls inside `Enum.map` causing cumulative timeout drift, spawn millions of unsupervised tasks without `max_concurrency`, and use `Task.async` without understanding it links the caller—meaning a task crash kills the caller process. The default **5-second timeout** on `Task.await/2` catches developers off guard in production, and using `Task.async_stream` with the `:exit` on_timeout default causes the entire stream to crash if one task times out.

**Estimated community reach:** **80%+** — Task is the primary concurrency primitive for one-off parallel work.

**Overlap check:** `elixir-broadway-pipeline` covers Broadway-specific data processing. `elixir-genserver-builder-and-smells` covers GenServer patterns. Task concurrency is a general-purpose OTP primitive distinct from both.

**Testability assessment:** Highly testable. Check for: `Task.Supervisor` vs bare `Task.async` usage, explicit timeout parameters on `await`, `max_concurrency` on `async_stream`, `on_timeout: :kill_task` configuration, proper error handling in task bodies, absence of `Task.async` without corresponding `await` (message leak), and linked vs unlinked task selection.

---

### 3. `elixir-http-client`
**Description:** Guides correct HTTP client selection, adapter configuration, SSL validation, and connection pooling across Tesla/Finch/Req.

**Evidence sources:** ElixirForum "Mint vs Finch vs Gun vs Tesla vs HTTPoison" thread (elixirforum.com/t/38588), Andrea Leopardi's HTTP client breakdown (andrealeopardi.com/posts/breakdown-of-http-clients-in-elixir/), Tesla README SSL warning, Hex.pm download stats (HTTPoison 60M, Tesla 55M, Finch 41M).

**Pain point summary:** Tesla's default `:httpc` adapter **does not validate SSL certificates**, creating a silent security vulnerability in production. Developers experience "paralysis by analysis" choosing between 6+ clients with different abstraction levels. Common failures include not adding Finch to the supervision tree, confusing the layering (Mint → Finch → Req/Tesla → application), and using HTTPoison/Hackney which pulls 7+ dependencies with their own SSL issues.

**Estimated community reach:** **80%+** — every Elixir application making HTTP calls faces this choice.

**Overlap check:** No existing family covers HTTP client patterns. The closest is `elixir-release-config` for deployment, which is unrelated.

**Testability assessment:** Highly testable. Check for: explicit adapter configuration (not using default `:httpc`), SSL verification enabled, Finch child spec in supervision tree when used as adapter, connection pool configuration, proper middleware ordering in Tesla (Telemetry before other middleware), retry logic presence, timeout configuration, and whether deprecated HTTPoison is used instead of modern alternatives.

---

### 4. `elixir-absinthe-resolver`
**Description:** Teaches correct Absinthe/GraphQL resolver patterns including Dataloader batching, subscription lifecycle, middleware error handling, and query complexity limiting.

**Evidence sources:** GitHub issues absinthe-graphql/absinthe#269 (N+1), absinthe-graphql/absinthe#583 (subscription middleware bypass), absinthe-graphql/absinthe#1064 (duplicate pushes), ElixirForum threads on GraphQL performance (elixirforum.com/t/31746), GC/WebSocket memory leaks (elixirforum.com/t/73713), Curiosum Absinthe getting-started guide.

**Pain point summary:** Developers build resolvers making individual DB queries per field (N+1 problem) without configuring Dataloader, whose batching mechanism fails with deeply nested queries because `Dataloader.run/1` fires prematurely during `before_resolution`. Authentication middleware is **not called during subscription setup**—only during resolution after event publishing—meaning auth checks in middleware don't protect subscription registration. Custom error-handling middleware is required for every project because exceptions in resolvers return HTML 500s by default.

**Estimated community reach:** **50%+** — Absinthe is the primary GraphQL library with 1.5K+ GitHub stars.

**Overlap check:** `elixir-phoenix-context` covers business logic organization, not GraphQL schema/resolver patterns. `elixir-phoenix-channel` covers WebSocket channels but not GraphQL subscriptions specifically.

**Testability assessment:** Highly testable. Check for: Dataloader source configuration for associations, `Absinthe.Middleware` usage for error handling, subscription `config/2` callback for auth (not relying on middleware), query complexity/depth limiting, absence of N+1 patterns in resolvers (direct Repo calls inside field resolvers), and proper use of `batch/4` or Dataloader for nested associations.

---

### 5. `elixir-ecto-multi-transaction`
**Description:** Enforces correct Ecto.Multi composition, error handling, and transaction patterns for multi-step database operations.

**Evidence sources:** Ecto.Multi official docs, Tom Konidas "Repo.transact" pattern (tomkonidas.com/repo-transact/), Curiosum Ecto transactions guide (curiosum.com/blog/elixir-ecto-database-transactions), ElixirForum debate on Multi vs transact (elixirforum.com/t/61733), SmartLogic Multi introduction.

**Pain point summary:** `Ecto.Multi` returns `{:error, failed_op, failed_value, changes_so_far}`—a 4-tuple that's unwieldy to pattern match and differs from the standard `{:ok, _}/{:error, _}` convention. Developers struggle with nested transaction gotchas where `Repo.rollback/1` inside a Multi raises unexpected errors, and Multi operations don't compose naturally with `with` blocks. The simpler `Repo.transact` pattern (Saša Jurić's approach) isn't officially part of Ecto, creating ecosystem fragmentation.

**Estimated community reach:** **80%+** — nearly every production app uses database transactions.

**Overlap check:** `elixir-ecto-query-writer` covers query composition, `elixir-ecto-schema-changeset` covers data validation. Multi/transactions are about atomic multi-step orchestration, rollback handling, and cross-operation composition—a distinct concern.

**Testability assessment:** Testable. Check for: proper 4-tuple error handling pattern matching, absence of nested `Repo.transaction` inside Multi, named operations for debugging, use of `Ecto.Multi.run/3` for side-effect operations, proper rollback semantics, and whether the Multi pipeline handles partial failure states correctly.

---

### 6. `elixir-plug-pipeline`
**Description:** Teaches custom Plug development, pipeline composition, halt semantics, and the Plug.Conn lifecycle for cross-cutting HTTP concerns.

**Evidence sources:** Phoenix router pipeline documentation, ElixirConf 2025 security talk, AppSignal authorization with Plugs (blog.appsignal.com/2021/11/02/authorization-and-policy-scopes-for-phoenix-apps.html), Subvisual Plug-based auth guide, Plug.Cowboy issue #10 (streaming/backpressure).

**Pain point summary:** Developers forget to call `Plug.Conn.halt/1` after sending a response, allowing downstream plugs to execute on an already-sent connection. Plug ordering creates subtle bugs—placing auth after body parsing exposes unprotected parsing, and placing CORS after auth blocks preflight requests. Module plugs vs function plugs have different initialization semantics that confuse developers, and testing plugs in isolation (outside Phoenix router) requires manually building `%Plug.Conn{}` structs.

**Estimated community reach:** **80%+** — every Phoenix application uses Plug pipelines.

**Overlap check:** `elixir-phoenix-context` covers business logic organization. Plug pipeline composition is about HTTP middleware architecture, request/response transformation, and connection lifecycle—a lower-level concern.

**Testability assessment:** Highly testable. Check for: `halt/1` called after response-sending operations, correct plug ordering in router pipelines, proper `init/1` and `call/2` signatures, conn returned from every plug, appropriate use of module vs function plugs, error responses for both HTML and JSON content types, and isolated plug unit tests.

---

### 7. `elixir-ets-usage`
**Description:** Teaches correct ETS table management including table types, ownership lifecycle, concurrency flags, atomic operations, and the decision of when ETS is appropriate vs GenServer state.

**Evidence sources:** DockYard ETS guide by Chris McCord (dockyard.com/blog/2017/05/19/optimizing-elixir-and-phoenix-with-ets), AppSignal caching guide, Johanna Larsson's ETS patterns (blog.jola.dev/patterns-for-managing-ets-tables), PagerDuty ETS memory leak post-mortem, ElixirSchool ETS lesson, official Elixir ETS guide (includes intentional race condition example as teaching moment).

**Pain point summary:** Developers create race conditions by using `GenServer.cast/2` to update ETS then immediately reading—the cast is async so the write may not have completed. Tables are destroyed when the owning process dies, leading to silent data loss without heir configuration. The `:ets.insert` and `:ets.lookup` combination is not atomic, requiring `:ets.update_counter/3` or `:ets.select_replace/2` for safe concurrent updates. ETS `:public` tables allow any process to write, creating hidden mutation points.

**Estimated community reach:** **50%+** — ETS underlies Phoenix.PubSub, Presence, and Registry; developers encounter it for caching, rate limiting, and feature flags.

**Overlap check:** `elixir-genserver-builder-and-smells` covers GenServer patterns. ETS involves table type selection, match specifications, concurrent access control, and memory management—fundamentally different from GenServer state management.

**Testability assessment:** Highly testable. Check for: correct table type selection (set vs ordered_set vs bag), appropriate access flags (`:protected` vs `:public`), `:ets.update_counter` for atomic increments, heir configuration for fault tolerance, `read_concurrency`/`write_concurrency` flag usage, absence of race-prone cast+read patterns, and `:binary.copy/1` for binaries stored in ETS to prevent reference retention.

---

### 8. `elixir-behaviour-mock`
**Description:** Teaches behaviour-based dependency injection and Mox mocking patterns including behaviour definition for third-party modules, process ownership, and test isolation.

**Evidence sources:** ElixirForum "Testing third-party modules with Mox" (elixirforum.com/t/11853), ElixirForum Mox/behaviour/optional arguments conflict (elixirforum.com/t/73103), ElixirSchool Mox lesson, thoughtbot mocking guide, AppSignal DI series (blog.appsignal.com/2024/05/21/using-dependency-injection-in-elixir.html), German Velasco's Mox patterns guide.

**Pain point summary:** Mox requires behaviours but third-party libraries rarely define them, forcing developers to create wrapper behaviours for every external dependency—adding significant boilerplate. Default/optional arguments in behaviours cause arity mismatches with Mox expectations, producing cryptic errors. Mock ownership between processes confuses async test scenarios, and when no expectations are defined, Mox's `stub_with` vs `expect` vs `stub` distinction trips up developers migrating from OOP mocking frameworks.

**Estimated community reach:** **80%+** — Mox is the idiomatic mocking approach; every team testing external dependencies encounters this.

**Overlap check:** `elixir-exunit-test-suite` covers test structure/organization. `elixir-ecto-sandbox-test` covers database test isolation. Behaviour-based mocking is a cross-cutting architectural concern about dependency injection design, not test scaffolding.

**Testability assessment:** Highly testable. Check for: behaviour definition for mocked modules, `Mox.defmock` with correct behaviour reference, explicit `expect` vs `stub` usage, `Mox.verify_on_exit!` in test setup, proper allowance configuration for async tests, absence of compile-time `Application.get_env` for module selection (should use runtime config), and whether wrapper behaviours match the original module's function signatures.

---

### 9. `elixir-phoenix-json-api`
**Description:** Enforces correct Phoenix JSON API patterns including response formatting, error serialization, pagination, content negotiation, and the Phoenix 1.7+ JSON rendering approach.

**Evidence sources:** Phoenix official JSON guide (hexdocs.pm/phoenix/json_and_apis.html), intercaetera hands-on API guide, ElixirForum HTML+JSON endpoints discussion (elixirforum.com/t/32441), Hex.pm Jason download stats (4.1M recent), ElixirConf CFP topics on "efficient data serialization."

**Pain point summary:** Developers accidentally expose sensitive fields by using `@derive Jason.Encoder` on schemas without an explicit `:only` field list, creating data leaks. The Phoenix 1.7 shift from `Phoenix.View` to function components changed API rendering patterns, but LLMs still generate deprecated view-based code. Error response formatting is inconsistent across projects because Phoenix provides no built-in standard (JSON:API spec, custom error shapes, and ad-hoc formats all coexist).

**Estimated community reach:** **50%+** — many Phoenix apps serve JSON APIs alongside or instead of HTML.

**Overlap check:** `elixir-phoenix-liveview` covers LiveView. `elixir-phoenix-context` covers business logic organization. `elixir-phoenix-channel` covers WebSockets. JSON API controller/serialization patterns occupy a distinct layer.

**Testability assessment:** Highly testable. Check for: explicit `:only` on `@derive Jason.Encoder`, proper HTTP status codes for different error types, consistent error response format, pagination metadata in list endpoints, `fallback_controller` or `action_fallback` configuration, proper use of `Phoenix.Controller.json/2` vs render patterns, absence of N+1 in API endpoints (preloading), and CORS plug configuration.

---

### 10. `elixir-auth-session`
**Description:** Guides correct authentication implementation including library selection (phx.gen.auth vs Guardian vs Pow), session management, JWT anti-patterns, and OAuth integration with Ueberauth.

**Evidence sources:** ElixirForum "Guardian vs Pow" (elixirforum.com/t/33848), "Do I want Ueberauth, Guardian, or both?" (elixirforum.com/t/26457), "JWTs should not be used for user sessions" (elixirforum.com/t/17546), ElixirMerge auth comparison (elixirmerge.com/p/elixir-authentication-gen-auth-vs-guardian-vs-pow), DEV.to OAuth integration struggles.

**Pain point summary:** Developers consistently misuse **JWT tokens for server-rendered sessions** via Guardian when Phoenix's built-in `phx.gen.auth` with server-side sessions is more appropriate and secure. The auth landscape has 4+ overlapping libraries (Guardian for tokens, Ueberauth for OAuth strategies, Pow for full auth, phx.gen.auth for built-in generation) that developers try to combine incorrectly—one developer described "scavenging through no fewer than three other posts" to get auth working. Sign-out fails silently with JWT because tokens are stateless, and Guardian's `resource_for_token` callback interface is described as "esoteric."

**Estimated community reach:** **80%+** — every web application needs authentication.

**Overlap check:** `elixir-security-linter` covers Sobelow static analysis for security vulnerabilities. Authentication implementation is about runtime session management, token handling, and library integration—entirely different from static security scanning.

**Testability assessment:** Testable. Check for: JWT usage only for API/stateless contexts (not server-rendered sessions), proper token expiration configuration, secure cookie flags (`:http_only`, `:secure`, `:same_site`), password hashing library usage (bcrypt/argon2), phx.gen.auth as default recommendation for new projects, proper Ueberauth callback handling with error cases, and session invalidation on password change.

---

## Tier 2 — Moderate confidence: evidence from 1-2 sources, significant subset, probably testable

### 11. `elixir-distributed-cluster`
**Description:** Teaches Erlang distribution configuration, libcluster topology setup, node discovery, cookie management, and network partition handling for multi-node deployments.

**Evidence sources:** Fly.io clustering guide (fly.io/docs/elixir/the-basics/clustering/), OneUptime distributed systems guide, AppSignal distributed Phoenix article, MonkeyVault distributed Erlang guide (monkeyvault.net/distributed-elixir-erlang-guide/).

**Pain point summary:** Clustering looks "deceivingly simple" but involves IPv6 misconfiguration on platforms like Fly.io, cookie mismatches that silently prevent connections, and network partitions causing split-brain scenarios with `:global` process registration. The mesh topology means N nodes require N*(N-1)/2 connections, which doesn't scale beyond ~50-100 nodes. Default Erlang distribution is **unencrypted** and cookie-based auth uses MD5—neither cryptographically secure.

**Estimated community reach:** **20-50%** — affects anyone scaling beyond a single node or deploying to platforms like Fly.io.

**Overlap check:** `elixir-supervisor-tree` covers local supervision. Distributed clustering involves EPMD, node connectivity, libcluster strategies, and net-split resilience—different from local process supervision.

**Testability assessment:** Moderately testable. Check for: libcluster configuration presence, explicit cookie configuration (not default), TLS distribution setup for production, `:pg` or Horde usage instead of `:global` for partition tolerance, `net_ticktime` tuning, and IPv6 configuration flags when targeting Fly.io/cloud platforms.

---

### 12. `elixir-process-backpressure`
**Description:** Teaches mailbox overflow prevention, demand-driven messaging, load shedding, and backpressure strategies for high-throughput Elixir systems.

**Evidence sources:** Fred Hébert's "Handling Overload" (ferd.ca/handling-overload.html), PO Box library (github.com/ferd/pobox), Sequin blog on Observer bottleneck hunting, ElixirForum "strategies to keep process mailboxes from exploding" (elixirforum.com/t/20331), Erlang Solutions mailbox performance article.

**Pain point summary:** Erlang mailboxes are **unbounded** and grow until the node runs out of memory. Using `GenServer.cast/2` instead of `call/2` eliminates backpressure, allowing messages to pile up silently in production. Selective receive patterns that scan the entire mailbox degrade to O(n²) performance. The BEAM has no native mailbox size limit—`max_heap_size` in OTP 19+ is a partial mitigation that kills the process rather than managing load gracefully.

**Estimated community reach:** **20-50%** — critical for high-throughput systems but less relevant for low-traffic apps.

**Overlap check:** `elixir-genserver-builder-and-smells` covers GenServer structure. `elixir-broadway-pipeline` covers Broadway-specific processing. General mailbox management, load shedding, and backpressure patterns are cross-cutting concerns distinct from both.

**Testability assessment:** Moderately testable. Check for: `call/2` vs `cast/2` usage in high-throughput paths, `max_heap_size` process flag configuration, GenStage/Flow usage for demand-driven pipelines, absence of unbounded `send` loops, proper use of `Process.info(pid, :message_queue_len)` for monitoring, and load-shedding patterns (dropping or buffering under pressure).

---

### 13. `elixir-stream-resource`
**Description:** Teaches correct Stream vs Enum selection, Stream.resource/3 lifecycle management, and memory-safe patterns for processing large datasets.

**Evidence sources:** PSPDFKit "Perils of Large Files in Elixir" (pspdfkit.com/blog/2021/the-perils-of-large-files-in-elixir/), Elixir official Stream docs, ElixirForum discussions on Repo.stream transaction requirements.

**Pain point summary:** Developers load entire files into memory with `File.read!/1` instead of streaming, causing OOM on large datasets. `Stream.resource/3` cleanup functions aren't called if the stream consumer crashes mid-processing, leading to resource leaks. `Repo.stream` requires wrapping in `Repo.transaction`—a non-obvious requirement that causes runtime errors. Holding binary references from streamed file chunks prevents garbage collection of the original buffer.

**Estimated community reach:** **50%** — any application processing CSV exports, file uploads, or large database result sets.

**Overlap check:** No existing family covers Stream patterns. `elixir-stdlib-validator` covers standard library function usage but not lazy evaluation design decisions.

**Testability assessment:** Testable. Check for: `Stream` vs `Enum` choice for large data (should be Stream), `Stream.resource/3` with proper cleanup function, `Repo.stream` wrapped in transaction, `:binary.copy/1` on streamed binary chunks, explicit `max_rows` on Repo.stream, and absence of `Enum.to_list` on potentially large streams.

---

### 14. `elixir-authorization`
**Description:** Teaches consistent authorization/access control patterns across controllers, LiveView, and GraphQL using policy-based approaches.

**Evidence sources:** ElixirConf EU 2025 dedicated authorization talk, Curiosum authorization blog series (curiosum.com/blog/authorization-access-control-elixirconf), AppSignal policy scopes guide, multiple competing libraries (Bodyguard, Permit, Canary, Dictator, Canada).

**Pain point summary:** Authorization logic scatters across controllers, LiveView handlers, and GraphQL resolvers with no single source of truth, causing some actions to **lack authorization checks entirely**. The fragmented library ecosystem (6+ competing approaches) signals that the problem isn't well-solved. Different patterns are needed for controllers (Plug-based) vs LiveView (mount/handle_event) vs Absinthe (middleware), and mixing authorization with business logic makes both harder to test.

**Estimated community reach:** **80%+** — every production app needs authorization, though many implement it ad-hoc.

**Overlap check:** `elixir-security-linter` covers Sobelow static analysis, not runtime authorization. `elixir-phoenix-context` covers business logic boundaries but not access control enforcement.

**Testability assessment:** Moderately testable. Check for: consistent authorization check presence on all controller actions and LiveView events, policy module separation from business logic, authorization in `mount/3` for LiveView (not just handle_event), use of a policy library or consistent pattern, and coverage of both allow and deny paths in tests.

---

### 15. `elixir-erlang-interop`
**Description:** Teaches correct patterns for calling Erlang OTP modules from Elixir including charlist/binary conversion, application configuration, and secure SSL/crypto defaults.

**Evidence sources:** Official Elixir Erlang libraries guide (hexdocs.pm/elixir/erlang-libraries.html), ElixirSchool Erlang interop lesson, ERLEF SSL security guide (security.erlef.org/secure_coding_and_deployment_hardening/ssl.html), Exercism Erlang libraries concept.

**Pain point summary:** Erlang functions return charlists (`'hello'`) where Elixir developers expect binaries (`"hello"`), causing silent type mismatches in string operations. The `:crypto` app must be explicitly added to `extra_applications` in `mix.exs` (it's not auto-started), and `:ssl` defaults to `verify: :verify_none`—**making HTTPS connections vulnerable to man-in-the-middle attacks**. Erlang function docs use Erlang syntax, which Elixir developers struggle to translate.

**Estimated community reach:** **50%** — virtually every app uses some Erlang stdlib, but many do so indirectly through wrapper libraries.

**Overlap check:** `elixir-stdlib-validator` covers Elixir's standard library. Erlang interop specifically addresses the Erlang↔Elixir boundary: charlist conversion, Erlang app configuration, OTP module APIs, and Erlang documentation navigation.

**Testability assessment:** Testable. Check for: `to_string/1` or `List.to_string/1` on Erlang function returns, `:crypto` in `extra_applications`, `verify: :verify_peer` with CA certificate store for `:ssl` connections, correct Erlang module atom syntax (`:timer.tc` not `Timer.tc`), and proper type conversion in function arguments.

---

### 16. `elixir-swoosh-email`
**Description:** Teaches correct Swoosh email configuration, adapter selection, TLS/SSL setup, and testing patterns for production email delivery.

**Evidence sources:** ElixirForum "Setting up Swoosh mailer in production" (elixirforum.com/t/55311), ElixirForum "Issues sending emails with Swoosh" (elixirforum.com/t/44707), chrisza.me TLS frustrations post, ElixirForum Bamboo vs Swoosh comparison (elixirforum.com/t/4752).

**Pain point summary:** SMTP adapters require manual TLS configuration since OTP 26 because `gen_smtp` doesn't auto-configure trusted CAs, causing emails to silently fail. The missing `:adapter` key in production config is a top-reported error. Dev environments use the Local adapter with a preview mailbox, but switching to production adapters (SendGrid, Mailgun, SES) introduces config differences that break on deploy. Swoosh.TestAssertions explicitly doesn't work in E2E/Wallaby tests.

**Estimated community reach:** **50%** — most production apps send email.

**Overlap check:** No existing family covers email delivery. The closest would be `elixir-release-config` for production config, but email adapter selection, TLS setup, and test adapter patterns are domain-specific concerns.

**Testability assessment:** Testable. Check for: explicit adapter configuration in production config, TLS options with `verify: :verify_peer` for SMTP, `Swoosh.TestAssertions` in test helpers, correct use of `Swoosh.Adapters.Local` only in dev, Oban or Task.Supervisor for async delivery reliability, and proper runtime.exs configuration for adapter credentials.

---

### 17. `elixir-phoenix-upgrade`
**Description:** Guides Phoenix and LiveView version migrations including template syntax changes, deprecated API replacement, routing updates, and component system transitions.

**Evidence sources:** LiveView changelog (hexdocs.pm/phoenix_live_view/changelog.html), Chris McCord upgrade gist (gist.github.com/chrismccord), ElixirForum upgrade struggles (elixirforum.com/t/54670, elixirforum.com/t/51355), GitHub LiveView breaking changes issue #1565.

**Pain point summary:** LiveView alone has had breaking changes across 0.16→0.17→0.18→1.0→1.1, including `.leex` to `.heex` template conversion, `Phoenix.LiveView.Helpers` → `Phoenix.Component` migration, `live_redirect`/`live_patch` → `<.link navigate={}/patch={}>` replacement, and `phx-feedback-for` removal in LV 1.0. LLMs are especially bad here because they were trained on pre-1.0 LiveView code and generate deprecated patterns. Phoenix 1.7's shift from `Phoenix.View` to function components broke the entire rendering layer.

**Estimated community reach:** **80%+** — every existing Phoenix app must eventually upgrade.

**Overlap check:** `elixir-release-config` covers release building. Version migration involves template syntax, routing changes, and component API transitions—a temporal but distinct concern.

**Testability assessment:** Testable. Check for: deprecated API usage (`live_redirect`, `live_patch`, `Phoenix.LiveView.Helpers`), old `.leex` template syntax, pre-1.7 `Phoenix.View` usage, `phx-feedback-for` attribute (removed in LV 1.0), `Application.get_env` where `Application.compile_env` is enforced, and old layout configuration patterns.

---

### 18. `elixir-registry-dynamic-sup`
**Description:** Teaches the Registry + DynamicSupervisor pattern for entity-per-process architectures including `:via` tuples, find-or-create semantics, and process lifecycle management.

**Evidence sources:** AppSignal multiplayer game tutorial (blog.appsignal.com/2019/08/13/elixir-alchemy-multiplayer-go-with-registry-pubsub-and-dynamic-supervisors.html), Medium Registry deep dives, Elixir official Registry docs, "Taming Dynamic Processes" blog post.

**Pain point summary:** The `:via` tuple syntax `{:via, Registry, {RegistryName, key}}` is unintuitive and easy to get wrong. Race conditions occur when two callers simultaneously try to start a process for the same entity—both pass the "does it exist?" check and attempt to start, with one failing. Registry match specifications use Erlang term format (`{:"$1", :_, :_}`) that's confusing in Elixir. Registry is **local-only** and doesn't work across distributed nodes without additional tooling like Horde or Syn.

**Estimated community reach:** **50%** — core pattern for chat rooms, game sessions, per-user connections, and entity-per-process systems.

**Overlap check:** `elixir-supervisor-tree` covers static supervision trees. Registry + DynamicSupervisor is about dynamic process management with named registration—`:via` tuples, find-or-create patterns, and entity lifecycle management are distinct concerns.

**Testability assessment:** Testable. Check for: proper `:via` tuple formatting, `start_or_lookup` pattern with race condition handling (using `DynamicSupervisor.start_child` return value), Registry listener configuration for process death notifications, proper `child_spec` in dynamic children, and absence of hardcoded process names for entities that should be dynamic.

---

### 19. `elixir-ash-resource`
**Description:** Teaches correct Ash Framework resource definition, action configuration, policy authorization, and DSL patterns for this rapidly growing framework where LLMs perform especially poorly.

**Evidence sources:** ElixirForum "Improving AI tooling with Ash documentation" (elixirforum.com/t/68286), Ash official LLM tooling thread (elixirforum.com/t/70980), ElixirForum Ash misconceptions (elixirforum.com/t/72763), "Getting started can be quite challenging...need to understand at least five different Ash libraries" (elixirforum.com/t/69857).

**Pain point summary:** Ash's declarative DSL requires understanding 5+ sub-libraries simultaneously (ash, ash_phoenix, ash_auth, ash_postgres, ash_json_api) with a steep learning curve. The framework team **built official LLM guidance** because AI tools produce incorrect code so frequently—LLMs hallucinate DSL syntax and generate code using outdated APIs. Policy authorization has had multiple bug fixes in its core logic (composing filter-checks, honoring trailing policies), meaning even the framework's own authorization system had correctness issues.

**Estimated community reach:** **20%** — rapidly growing but not yet mainstream. However, it's one of the most discussed frameworks on ElixirForum.

**Overlap check:** No existing family covers Ash Framework patterns. The closest would be `elixir-phoenix-context` for business logic, but Ash's declarative DSL is fundamentally different from Phoenix contexts.

**Testability assessment:** Testable. Check for: correct resource DSL structure, proper action definitions (create/read/update/destroy), policy authorization setup, relationship configuration, correct use of preparations and changes, and absence of non-Ash patterns mixed into Ash resources.

---

### 20. `elixir-umbrella-app`
**Description:** Teaches correct umbrella application architecture including dependency boundary enforcement, configuration management, and when to use umbrellas vs monoliths vs poncho projects.

**Evidence sources:** Jack Marchant "The Problem with Elixir Umbrella Apps" (jackmarchant.com), Ben Munat "Ditch that Umbrella" (ben.munat.com), ElixirForum debate (elixirforum.com/t/49585), ElixirSchool umbrella guide, DockYard top-5 mistakes listing "overconfidence" with umbrellas.

**Pain point summary:** Teams adopt umbrella apps for separation of concerns but find that boundaries blur over time through transient dependency conflicts, circular dependencies, and shared config/lockfile limitations. Dave Thomas actively discourages umbrellas, and DockYard lists overconfidence in umbrella architecture as a top Elixir mistake. VSCode/ElixirLS has IDE issues with nested project structures, and compile-time coupling persists despite apparent separation.

**Estimated community reach:** **20-50%** — many teams use umbrellas but the pattern is declining in favor of monoliths with good context boundaries.

**Overlap check:** No existing family covers project architecture or code organization. `elixir-phoenix-context` covers business logic boundaries within a single app, not multi-app umbrella architecture.

**Testability assessment:** Moderately testable. Check for: absence of circular dependencies between child apps, proper boundary enforcement (app A doesn't call app B's internal modules), correct config management (no duplicate config entries), explicit dependency declarations in child `mix.exs`, and boundary tool integration (like `boundary` hex package).

---

### 21. `elixir-rate-limiter`
**Description:** Teaches rate limiting algorithm selection, implementation patterns, and integration with Phoenix/Plug for API protection.

**Evidence sources:** Hammer library (github.com/ExHammer/hammer), Akoutmos GenServer rate limiter post (akoutmos.com/post/rate-limiting-with-genservers/), ElixirForum AtomicBucket discussion (elixirforum.com/t/74225), ElixirCasts Hammer tutorial.

**Pain point summary:** Fixed window counters allow **2x burst at window boundaries** (a request just before the window resets and another just after both count against different windows). GenServer-based rate limiters become single-process bottlenecks under extreme load. ETS-based implementations are single-node only, requiring Redis or similar backends for distributed rate limiting. Choosing between token bucket (allows bursts), leaky bucket (shapes traffic uniformly), and sliding window (accurate but expensive) requires understanding tradeoffs most developers don't have.

**Estimated community reach:** **20-50%** — needed for API protection, external API consumption, and DDoS mitigation.

**Overlap check:** No existing family covers rate limiting. This is an independent, self-contained skill involving algorithm selection, storage backend choices, and Plug integration.

**Testability assessment:** Testable. Check for: correct algorithm selection for use case, Plug integration for automatic rate limiting, proper storage backend (ETS for single-node, Redis for distributed), window boundary handling, appropriate response headers (X-RateLimit-Remaining, Retry-After), and absence of GenServer bottleneck patterns in high-throughput paths.

---

### 22. `elixir-binary-memory-gc`
**Description:** Teaches BEAM binary memory management, reference-counted binary lifecycle, GC tuning, and memory leak debugging with recon/Observer.

**Evidence sources:** Stephen Bussey "Elixir Memory: Not Quite Free" (stephenbussey.com/2018/05/09/elixir-memory-not-quite-free.html), PagerDuty ETS memory leak post-mortem (pagerduty.com/eng/tracking-down-ets-related-memory-leak/), Honeybadger memory structure guide, PSPDFKit large files post, Postgrex issue #167 (binary retention in TCP buffers).

**Pain point summary:** BEAM uses reference-counted binaries (>64 bytes) stored in a shared heap. Slicing a large binary with `binary_part/3` holds a reference to the **entire original binary**—developers must use `:binary.copy/1` to release it. Long-running GenServers accumulate binaries in the old heap where minor GC won't collect them, and Phoenix WebSocket processes holding large payload references silently leak memory. Debugging requires specialized tools (`:recon.bin_leak/1`, `:recon.proc_count(:binary_memory, N)`) that most developers don't know about.

**Estimated community reach:** **20%** — primarily affects production systems under load, but the impact is severe (OOM crashes).

**Overlap check:** `elixir-binary-pattern-match` covers binary pattern matching syntax. Binary memory management covers reference counting, GC behavior, and leak debugging—completely different from matching syntax.

**Testability assessment:** Moderately testable. Check for: `:binary.copy/1` usage when storing sub-binaries long-term, absence of `binary_part` on large binaries stored in ETS or GenServer state, `:erlang.garbage_collect/1` or `:erlang.hibernate` hints in long-running processes, proper streaming of large responses instead of buffering, and recon dependency for production debugging.

---

### 23. `elixir-behaviour-protocol`
**Description:** Teaches the design decision between Behaviours (module-level polymorphism) and Protocols (data-type polymorphism), including custom behaviour authoring and protocol consolidation.

**Evidence sources:** j3rn.com "Behaviours vs Protocols," Yiming Chen "Stop using Behaviour to define interfaces, use Protocol" (yiming.dev), DJM.org.uk comparison, Savonarola DEV.to "additional thoughts," ElixirSchool Behaviours lesson.

**Pain point summary:** Developers consistently confuse when to use Behaviours (dispatch on module identity, adapter pattern) vs Protocols (dispatch on data type, encoding/display pattern). Using behaviours where protocols are appropriate forces explicit module passing rather than leveraging data-driven dispatch. Protocol consolidation is disabled in dev for faster compilation, causing performance differences between environments. LLMs trained on OOP languages default to interface-like behaviours when protocols would be more idiomatic.

**Estimated community reach:** **20-50%** — affects library authors and anyone designing extensible systems.

**Overlap check:** `elixir-typespec-annotator` covers type annotations. Behaviour/Protocol design decisions are about polymorphism strategy, not type documentation.

**Testability assessment:** Testable. Check for: correct choice of behaviour vs protocol for the use case (adapter pattern → behaviour, data serialization → protocol), `@impl true` annotations on behaviour callbacks, protocol implementation with `defimpl`, consolidation enabled in production config, and absence of anti-patterns like passing module names as arguments when a protocol dispatch would be cleaner.

---

## Tier 3 — Speculative: mentioned once or pattern-matched, needs validation

### 24. `elixir-native-interop`
**Description:** Teaches safe NIF and Port patterns for integrating native C/Rust code without crashing the BEAM VM.

**Evidence sources:** Rustler GitHub (github.com/rusterlium/rustler), Mainmatter Rust NIF guide, Fly.io "Elixir and Rust is a Good Mix," Curiosum "Getting Rusty with Elixir NIFs."

**Pain point summary:** A NIF segfault crashes the entire BEAM VM, destroying all fault-tolerance guarantees. Long-running NIFs must complete within ~1ms or use dirty schedulers (`DirtyCpu`/`DirtyIo`) to avoid starving the scheduler. Deployment requires the Rust/C toolchain in Docker builds, and cross-compilation adds complexity. Discord's famous Rust NIF for sorted member lists is a success story, but most developers lack the experience to build production-safe NIFs.

**Estimated community reach:** **10-20%** — growing with Rustler and Nx but still specialized.

**Overlap check:** `elixir-binary-pattern-match` covers binary matching syntax. NIFs involve native toolchains, scheduler interaction, and VM safety—a completely different domain.

**Testability assessment:** Moderately testable. Check for: Rustler usage over raw C NIFs, `schedule: :DirtyCpu` on long-running operations, proper error mapping between Rust Result and Elixir tuples, NIF resource cleanup implementation, and Port usage for untrusted external code (instead of NIF).

---

### 25. `elixir-commanded-cqrs`
**Description:** Teaches CQRS/Event Sourcing patterns with Commanded including aggregate design, event schema evolution, process managers, and snapshotting.

**Evidence sources:** Christian Alexander "Elixir Commanded" review (christianalexander.com), Zarar.dev CQRS guide, Blog Nootch event sourcing series, ElixirForum ES without CQRS thread (elixirforum.com/t/25049).

**Pain point summary:** Commanded's aggregate processes persist in memory indefinitely unless lifespans are configured, causing steadily growing memory usage. Event schema evolution requires careful snapshot versioning—if the aggregate state shape changes, snapshots must be rebuilt. Cross-aggregate operations cannot be atomic, and eventual consistency between write and read models creates UI confusion. EventStore database setup fails on managed PostgreSQL that lacks a "postgres" maintenance database.

**Estimated community reach:** **<10%** — niche architectural pattern with a dedicated but small community.

**Overlap check:** No existing family covers CQRS/Event Sourcing. The closest would be `elixir-ecto-multi-transaction` for database transactions, but CQRS involves event stores, aggregate lifecycles, and read model projections.

**Testability assessment:** Testable. Check for: aggregate lifespan configuration, snapshot interval settings, proper command → event transformation, event versioning/upcasting, process manager implementation for sagas, and read model projection handlers.

---

### 26. `elixir-nx-ml`
**Description:** Teaches Nx tensor operations, EXLA backend configuration, defn numerical definitions, and Bumblebee model serving for Elixir ML workloads.

**Evidence sources:** DockYard "Three Years of Nx" (dockyard.com/blog/2023/11/08/three-years-of-nx), Nx GitHub issue #776 (backend incompatibility), Seanmoriarity.com Axon deep learning guide ("still very young...sharp edges"), DockYard Nx for absolute beginners guide.

**Pain point summary:** Mixing tensor backends (e.g., `Nx.Defn.Expr` and `EXLA.Backend`) causes cryptic "cannot invoke Nx function because it relies on two incompatible tensor implementations" errors requiring explicit `Nx.backend_transfer/1`. `defn` has different semantics than `def`—it only supports numerical computations, not general Elixir code. EXLA compilation requires platform-specific XLA dependencies that fail on non-standard setups. The Nx ecosystem API changes rapidly between versions, breaking tutorials.

**Estimated community reach:** **<10%** — growing rapidly but still a small percentage of Elixir developers work with ML.

**Overlap check:** No existing family covers ML/numerical computing. This is entirely novel territory.

**Testability assessment:** Testable. Check for: explicit backend specification, correct `defn` usage (numerical code only), proper tensor type handling, Nx.Serving configuration for model serving, correct EXLA backend setup, and absence of `Enum` operations on tensors (should use Nx operations).

---

### 27. `elixir-gettext-i18n`
**Description:** Teaches correct Gettext internationalization patterns including POT/PO file management, plural forms, domain organization, and Ecto error translation.

**Evidence sources:** ElixirSchool Gettext lesson, Phoenix i18n documentation, Crudry's Gettext middleware for Absinthe, ElixirForum ecosystem gap discussions.

**Pain point summary:** Developers hardcode user-facing strings instead of wrapping them in `gettext/1` calls, making retroactive i18n painful. The POT extraction workflow (`mix gettext.extract --merge`) is non-obvious, and plural form handling uses C-style `ngettext` syntax that differs across locales. Runtime locale switching requires careful placement of `Gettext.put_locale/2` in the request lifecycle (typically a Plug), and Ecto changeset errors need a separate `Gettext`-aware error helper for translation.

**Estimated community reach:** **20%** — primarily relevant for apps serving multiple locales.

**Overlap check:** No existing family covers internationalization. This is an independent domain.

**Testability assessment:** Testable. Check for: `gettext/1` usage instead of hardcoded strings in templates/controllers, POT file presence and freshness, plural form definitions for all supported locales, Gettext Plug in router pipeline, and proper Ecto error message translation configuration.

---

### 28. `elixir-ecto-multi-tenant`
**Description:** Teaches multi-tenant database architecture patterns in Ecto including prefix-based schemas, dynamic repos, row-level security, and cross-tenant query isolation.

**Evidence sources:** ElixirConf 2023 talk on `Ecto.Repo.put_dynamic_repo/1` ("sharp corners and lessons learned"), Ecto prefix-based multi-tenancy documentation, ElixirConf separate-database talk.

**Pain point summary:** Dynamic repo configuration is complex and error-prone—`put_dynamic_repo/1` must be called in every process that touches the database, including background jobs and PubSub handlers. Prefix-based queries require consistent prefix usage across all Ecto calls, and forgetting to set the prefix in one query leaks data across tenants. Migrations must be run across all schemas/databases, and test isolation with dynamic repos requires custom sandbox setup.

**Estimated community reach:** **10-20%** — SaaS applications routinely need this but it's specialized.

**Overlap check:** Existing Ecto families cover queries, schemas, and testing. Multi-tenancy is an architecture-level concern about tenant isolation, dynamic configuration, and cross-cutting data boundaries.

**Testability assessment:** Testable. Check for: consistent prefix setting across all Repo calls, dynamic repo configuration in all process contexts, migration scripts that iterate across tenants, test setup with proper tenant isolation, and absence of non-prefixed queries that could leak cross-tenant data.

---

### 29. `elixir-nerves-firmware`
**Description:** Teaches Nerves embedded Elixir patterns including firmware building, VintageNet networking, GPIO/I2C hardware interaction, and read-only filesystem constraints.

**Evidence sources:** ElixirForum Nerves boot debugging (elixirforum.com/t/33507), SSH connection failures (elixirforum.com/t/71579), Nerves FAQ (hexdocs.pm/nerves/faq.html), ElixirForum resource constraints discussion (elixirforum.com/t/68944).

**Pain point summary:** Firmware boots with no debugging output (just a raspberry icon) when configuration is wrong, and SSH connections fail silently without clear error messages. Libraries that assume writable `priv` directories break on Nerves' read-only filesystem. Cross-compilation NIF issues vary by OS, and `MIX_TARGET` must be set consistently. The BEAM VM's memory footprint (~30MB minimum) is a concern on constrained devices.

**Estimated community reach:** **<10%** — dedicated community but small relative to web development.

**Overlap check:** No existing family covers embedded/IoT development. This is entirely distinct.

**Testability assessment:** Difficult to test without hardware. Could check for: proper `MIX_TARGET` configuration, VintageNet networking setup, read-only filesystem awareness in code, firmware metadata configuration, and correct Nerves dependency pinning.

---

### 30. `elixir-membrane-pipeline`
**Description:** Teaches Membrane Framework multimedia pipeline construction including element wiring, dynamic pads, flow control, and native dependency management.

**Evidence sources:** ElixirForum RTMP pipeline crash discussion (elixirforum.com/t/69442), Underjord Membrane + LiveView tutorial, Membrane Core v1.2.0 release notes (added compile-time architectural checks), Membrane documentation ("we can cover only a limited number of use cases").

**Pain point summary:** Dynamic pads from demuxers can't be attached incrementally to sinks with `:always` availability, and `Membrane.Tee.Parallel` causes "toilet capacity" overflow errors when outputs process at different speeds. Pipeline crashes propagate to the entire application without proper isolation. Many plugins require native OS libraries (FFmpeg, PortAudio) that complicate deployment, and Windows isn't supported for native code plugins.

**Estimated community reach:** **<5%** — very niche multimedia processing domain.

**Overlap check:** `elixir-broadway-pipeline` covers data processing pipelines. Membrane is about multimedia-specific concerns: stream formats, audio/video caps negotiation, and media codec integration.

**Testability assessment:** Moderately testable. Check for: correct pipeline element wiring, dynamic pad handling configuration, flow control mode selection (push vs pull), proper element ordering (source → filter → sink), and crash isolation patterns.

---

### 31. `elixir-port-external`
**Description:** Teaches safe external OS process management via Ports including lifecycle cleanup, flow control, and command injection prevention.

**Evidence sources:** Saša Jurić "Outside Elixir" (theerlangelist.com/article/outside_elixir), MuonTrap library (github.com/fhunleth/muontrap), Tony Coconate's Port management guide, Elixir Port documentation.

**Pain point summary:** External processes persist as zombies after VM termination—programs like `ping` that don't watch stdin keep running indefinitely. There's no built-in flow control, so fast-producing external processes can overflow the port owner's mailbox. Passing user input directly into `Port.open({:spawn, "cmd #{user_input}"})` creates **command injection vulnerabilities**. MuonTrap exists to fix these issues but developers must know to use it instead of raw Ports.

**Estimated community reach:** **10-20%** — used for FFmpeg, ImageMagick, shell scripts, and serial communication.

**Overlap check:** No existing family covers OS process management. This is distinct from all existing families.

**Testability assessment:** Testable. Check for: MuonTrap usage over raw `Port.open`, `{:spawn_executable, path}` over `{:spawn, cmd}` for injection safety, proper cleanup in GenServer `terminate/2`, absence of user input interpolation in spawn commands, and flow control patterns for high-output external processes.

---

### 32. `elixir-phoenix-pubsub`
**Description:** Teaches Phoenix.PubSub patterns beyond basic subscribe/broadcast including topic design, distributed broadcasting, presence tracking at scale, and payload optimization.

**Evidence sources:** AppSignal distributed Phoenix scaling article (blog.appsignal.com/2024/12/10/distributed-phoenix-deployment-and-scaling.html), ElixirConf 2025 CFP request for PubSub state management talks, OneUptime distributed systems guide.

**Pain point summary:** PubSub broadcasts are O(subscribers)—broadcasting to thousands of subscribers on a topic becomes a bottleneck without topic sharding. Presence tracking CRDTs grow large with many concurrent users, and PubSub across nodes inherits all distributed Erlang net-split problems. Topic proliferation without cleanup leads to gradual memory growth, and naive broadcasting of large payloads saturates network between clustered nodes.

**Estimated community reach:** **20-50%** — relevant for real-time applications (chat, notifications, dashboards).

**Overlap check:** `elixir-phoenix-channel` covers WebSocket channel patterns. PubSub is the underlying broadcasting infrastructure—topic design, distributed delivery, and presence CRDT management are lower-level concerns.

**Testability assessment:** Moderately testable. Check for: topic naming conventions, payload size awareness, subscription cleanup on process termination, Presence configuration for tracking, and distributed PubSub adapter configuration.

---

### 33. `elixir-caching-strategy`
**Description:** Teaches caching library selection and configuration (Cachex, Nebulex, ConCache) including TTL management, distributed topologies, and cache invalidation patterns.

**Evidence sources:** AppSignal Cachex guide (blog.appsignal.com/2024/03/05/powerful-caching-in-elixir-with-cachex.html), Nebulex v3 release (medium.com/erlang-battleground/nebulex-v3), Nebulex distributed caching guide.

**Pain point summary:** Nebulex v3 (released Feb 2026) introduced major API changes requiring migration from v2, fragmenting documentation and examples. Choosing between coherent (invalidation-based), replicated, and partitioned cache topologies requires distributed systems knowledge most developers lack. Cache invalidation remains inherently difficult—stale data during invalidation windows causes subtle bugs, and over-caching with long TTLs masks data freshness issues.

**Estimated community reach:** **20%** — most production apps benefit from caching but many use ad-hoc approaches.

**Overlap check:** Somewhat related to `elixir-ets-usage` but operates at the library abstraction level rather than raw ETS. Caching strategy involves library selection, topology design, and invalidation patterns.

**Testability assessment:** Testable. Check for: explicit TTL configuration, cache topology matching deployment topology (local cache for single-node, distributed for multi-node), proper cache key design, invalidation on data mutation, and correct Cachex/Nebulex child spec in supervision tree.

---

### 34. `elixir-sage-distributed-tx`
**Description:** Teaches distributed transaction orchestration with Sage for multi-service operations that span beyond a single database, including compensation/rollback logic.

**Evidence sources:** Sage library (hex.pm/packages/sage), "Essential Libraries for Elixir Developers" (brittonbroderick.com — "Think Ecto.Multi, but for cases when you need to reach outside a single database transaction"), ElixirForum discussions.

**Pain point summary:** LLMs don't know about Sage and generate `Ecto.Multi` for operations spanning multiple services (API calls + database writes), which doesn't provide rollback for non-database operations. Implementing proper compensation functions (undoing a Stripe charge if a database insert fails) requires thinking in reverse, which is non-intuitive. Sage's step composition and retry semantics have a learning curve, and mixing sync and async compensation steps adds complexity.

**Estimated community reach:** **<10%** — needed in apps with external service integrations (payments, third-party APIs) but not widely known.

**Overlap check:** `elixir-ecto-multi-transaction` covers database-scoped transactions. Sage handles cross-service orchestration with compensation—fundamentally different scope.

**Testability assessment:** Testable. Check for: Sage usage for operations spanning database + external services, compensation function implementation for each step, proper error propagation through the saga, retry configuration on transient failures, and absence of Ecto.Multi used for cross-service operations.

---

## Cross-cutting observations that inform prioritization

The research revealed a critical meta-pattern about LLM performance on Elixir. **Elixir has disproportionately worse AI code generation** compared to Python/JavaScript due to three factors: smaller training corpora (DockYard explicitly noted this), syntactic similarity to Ruby causing cross-contamination (GitHub Copilot users report Ruby suggestions in Elixir files), and OTP-specific paradigms that LLMs trained on OOP code fundamentally misunderstand. One ElixirForum thread documented that ChatGPT tells users to "override functions in a base module" using inheritance patterns that don't exist in Elixir.

The **most impactful skill families** will be those that address both developer confusion and LLM failure modes simultaneously. Safe Ecto migrations, HTTP client configuration, and authentication session management rank highest because they affect 80%+ of developers, have clear testability, and represent areas where LLMs produce actively dangerous code (silent SSL bypass, production-locking DDL, JWT misuse for sessions). The Tier 1 candidates collectively cover the core web application lifecycle: database operations (safe-migration, multi-transaction), HTTP layer (http-client, plug-pipeline, json-api, auth-session), concurrency (task-async), testing (behaviour-mock), data storage (ets-usage), and API design (absinthe-resolver).

The Ash Framework candidate deserves special attention despite lower community reach because the framework team built **official LLM guidance** in response to consistently wrong AI-generated code—a direct signal that skill-based intervention has high impact. Similarly, the Phoenix upgrade family addresses a temporal but persistent problem: every LiveView version change renders prior LLM training data partially incorrect, and LLMs have no way to know which API version a project targets.

For the Tier 3 candidates, `elixir-native-interop` and `elixir-port-external` are likely to grow in importance as the Nx ecosystem matures and Rustler adoption increases. The `elixir-commanded-cqrs` and `elixir-membrane-pipeline` families serve small communities but those communities have few alternative resources, making skill-based guidance especially valuable per-user.