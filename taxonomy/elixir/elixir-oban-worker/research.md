# elixir-oban-worker — Per-Capability Research Dossier

**Generated**: 2026-04-11
**Workstream**: SKLD-bench v2.1 (see [`../SEEDING-PLAN.md`](../SEEDING-PLAN.md))
**Sources surveyed**: Oban HexDocs (Worker, Testing, Telemetry, Plugins.Cron, unique_jobs, error_handling, periodic_jobs, Oban module), Oban GitHub issues (oban-bg/oban), Elixir Forum (multiple threads), Sorentwo blog (Parker Selbert / Oban maintainer recipes), oliver-kriska/claude-elixir-phoenix plugin README and Iron Laws, georgeguimaraes/claude-code-elixir plugin, BoothIQ "150k lines of vibe-coded Elixir" post-mortem, Michał Łępicki blog on struct args, DockYard blog, AppSignal blog, the project-local research dossier `docs/research/elixir-llm-pain-points.md`.
**Total citations**: 38

## Family-level summary

Oban is the de-facto Elixir job queue, built on PostgreSQL (and more recently SQLite and MySQL). It has a small API surface compared to LiveView or Ecto, but three failure modes appear as **"Iron Laws" in every Claude-focused Elixir plugin** and multiple developer post-mortems: (1) jobs that mutate state on every retry without idempotency guards, (2) atom keys in `args` that silently round-trip as strings, and (3) Elixir structs stored in `args` that serialize to a flat map and lose their type. These three are the load-bearing failure modes for this family — every other capability has thinner but still-real evidence.

The secondary failure cluster comes from the **`unique:` options and state-list misconfigurations**: Elixir Forum has multiple threads where developers excluded `:available` from `:states`, assumed `:period` alone was enough without aligning the pruner's `max_age`, or confused "unique insertion" with "serialized execution." These bugs are pernicious because they don't fail loudly — they produce silent duplication, queue crashes creating hundreds of producers, or non-deterministic behavior. The Oban maintainer (Parker Selbert / sorentwo) has stated on the forum that only three safe `:states` configurations exist (`successful`, `incomplete`, or the full list including cancelled/discarded); anything else is unsafe and not production-recommended.

The **return-value protocol** (`:ok` / `{:ok, val}` / `{:error, reason}` / `{:snooze, period}` / `{:cancel, reason}`) is another LLM blind spot because it evolved: `:discard` and `{:discard, reason}` are **deprecated** in favor of `{:cancel, reason}`, but training-corpus blogs frequently reference the old form. LLMs also default to `raise` for rate-limit errors instead of the idiomatic `{:snooze, seconds}` return, missing the point of snoozing entirely. The **cron plugin** has its own LLM traps: timezone support requires installing a TZ database (`tz` or `tzdata`) as a separate dependency, and the static-at-boot-time loading is easy to miss when Claude suggests "dynamic" cron code against the free plugin (DynamicCron is Oban Pro only).

**Evidence quality**: Moderate-to-strong overall. The three iron laws (idempotency, string keys, no structs) have multi-source corroboration including explicit plugin enforcement rules, published GitHub issues, and a developer blog post. Several secondary capabilities (telemetry, transactional jobs, Testing.inline vs manual) are corroborated primarily by the official docs + single-source forum or blog posts; "LLM failure" mapping for these is inferential — the docs warn of subtleties, and a training corpus that predates 2024 will reliably miss them. Thinnest capability: `queues-and-priority` — the docs flag one real compile-time gotcha (`Application.get_env/2` for worker options), but there is no strong developer narrative of LLMs getting this wrong.

---

## Capability research

### Foundation: `worker-philosophy`

**Description** (from README.md): How the skill frames Oban workers: idempotent-by-default (assume retries), transactional (insert job + parent data in one Ecto.Multi), or eventually-consistent (best-effort). Frames every capability's recommendations.

**Known Claude failure modes**:
- [HIGH] Defaults to naive "run the business logic" workers that aren't idempotent — doesn't track a `processed_at` / idempotency key, so retries re-execute side effects (emails, payment charges, API calls, external webhook sends)
- [HIGH] Misses the transactional-enqueue pattern: Claude writes `Repo.insert(user); MyWorker.new(...) |> Oban.insert()` as two calls, instead of a single `Ecto.Multi` that keeps them atomic. If the user insert succeeds and the process crashes before enqueue, the user exists with no follow-up job
- [MED] Frames retries as an exception condition instead of "the expected happy-path for any transient failure"

**Citations**:
- *"Jobs must be idempotent. Args use string keys. Never store structs in args."* — [oliver-kriska/claude-elixir-phoenix Iron Laws](https://github.com/oliver-kriska/claude-elixir-phoenix), plugin README (explicit Claude Code enforcement rule)
- *"Claude Code doesn't know that assign_new silently skips on reconnect, that :float will corrupt money fields, or that your Oban job isn't idempotent."* — [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix), plugin README framing
- *"Enqueue a job along with other database changes, ensuring that everything is committed or rolled back atomically."* — [Oban module docs (transactional control section)](https://hexdocs.pm/oban/Oban.html)
- *"Oban is a sophisticated background job processing library... Design your workers so that executing the same job multiple times does not produce adverse effects... it should not make a difference to the final state of the system if a job successfully completes on its first attempt, or if it fails initially and succeeds when retried."* — [Medium: "Keep Calm and Let Oban Handle Your Elixir Background Jobs"](https://medium.com/@jonnyeberhardt7/keep-calm-and-let-oban-handle-your-elixir-background-jobs-67e4f04d7522), Jonny Eberhardt
- *"A network timeout during a large language model API call that triggers a retry can result in paying twice... Retrying a request three times without idempotency guarantees potentially triples what should have been one operation."* — [DZone: "Idempotency in AI Tools"](https://dzone.com/articles/idempotency-in-ai-tools-most-expensive-mistake) (corroborates real-world cost of non-idempotent background jobs)

**Suggested challenge angles**:
- Ask Claude to frame a new worker module with an explicit idempotency contract stated in the `@moduledoc` (not just in comments)
- Ask Claude to convert a "naive two-call enqueue" into the `Ecto.Multi` transactional pattern
- Ask Claude to explain (or defend in code) a design choice between `{:error, ...}` and `{:cancel, ...}` for a specific failure

**Tier guidance**: Medium-to-Hard foundation. Easy: state the philosophy in a `@moduledoc`. Medium: re-frame an existing non-idempotent worker. Hard: compose multi-worker transactional flow with declared invariants.

---

### Capability: `perform-callback-basics`

**Description** (from README.md): The `perform/1` contract; receiving the `Oban.Job` struct; the return-value protocol.

**Known Claude failure modes**:
- [HIGH] Writes `perform/1` that accepts plain args instead of destructuring from `%Oban.Job{args: ...}` — misses that the argument is the `Oban.Job` struct, not the raw map
- [HIGH] Pattern-matches on atom keys in the function head (`def perform(%{"user_id" => id})` vs `def perform(%{user_id: id})`) — Claude almost always writes the atom form first (see `args-serialization`)
- [MED] Returns a non-standard value like `{:noreply, ...}` or `{:reply, ...}` from GenServer muscle memory

**Citations**:
- *"The `args` map provided to `perform/1` will always have string keys, regardless of the key type when the job was enqueued."* — [Oban.Worker HexDocs v2.21.1](https://hexdocs.pm/oban/Oban.Worker.html)
- *"It's easy to make small mistakes (typos and similar) in job arguments... The job fails at the start of executing with `** (FunctionClauseError) no function clause matching in MyApp.Business.perform/1`"* — [Michał Łępicki: Using structs for Oban worker arguments](https://blog.michallepicki.com/using-structs-for-oban-worker-arguments.html)
- *"This reduces boilerplate when constructing jobs for unit tests and checks for common pitfalls. For example, it automatically converts `args` to string keys before calling `perform/1`, ensuring that perform clauses aren't erroneously trying to match atom keys."* — [Oban.Testing HexDocs](https://hexdocs.pm/oban/Oban.Testing.html) (the test helper exists precisely to catch this LLM class of bug)
- *"The helper makes assertions that the worker implements the Oban.Worker behaviour, that the options build a valid job, and that the return is valid (e.g., `:ok`, `{:ok, value}`, `{:error, value}`), returning the result of perform/1 for additional assertions."* — [Oban.Testing HexDocs](https://hexdocs.pm/oban/Oban.Testing.html)

**Suggested challenge angles**:
- Ask Claude to write a `perform/1` clause that destructures an arg map with a nested field
- Give Claude a broken `perform/1` that pattern-matches on atom keys and ask for a fix (the fix should be the string-key form, not a workaround)
- Ask Claude to handle a `perform/1` that takes `%Oban.Job{attempt: attempt, args: args}` and branches on attempt number

**Tier guidance**: Easy-to-Medium binary — most challenges should catch the string-key trap with a regex check and validate return-value shape.

---

### Capability: `args-serialization` ⭐

**Description** (from README.md): String keys only, no structs; what survives JSON serialization.

**Known Claude failure modes**:
- [HIGH] Uses atom keys when building args: `MyWorker.new(%{user_id: 1})` — this **enqueues successfully** but pattern-matching on atoms in `perform/1` silently fails at runtime
- [HIGH] Stores Elixir structs (`%User{...}`, `%Ecto.Changeset{}`, `DateTime`) directly in args — they serialize to a flat map and the `__struct__` field is lost; subsequent `perform/1` crashes on struct-shaped pattern matches
- [HIGH] Passes `NaiveDateTime`, `Decimal`, `PID`, or tuples — JSON has no native representation, and Jason falls back in ways that lose the original type
- [MED] Assumes `@derive Jason.Encoder` is sufficient for safe round-trip (it encodes but does not *decode back* to the struct)

**Citations**:
- *"Because `args` are always encoded as JSON, you must also ensure that all values are serializable, otherwise you'll have encoding errors when inserting jobs."* — [Oban.Worker HexDocs](https://hexdocs.pm/oban/Oban.Worker.html)
- *"The args are serialized as `jsonb`, which means they are deserialized with string keys... Deserializing to atom keys is unsafe because it provides an attack vector to exhaust the available atoms. This is the same reason that plug/Phoenix args are passed as strings."* — [Parker Selbert (sorentwo), oban-bg/oban#126](https://github.com/oban-bg/oban/issues/126)
- *"I have a pretty big map as argument, and it seems unusable in this state."* — original reporter (jesuiswu), [oban-bg/oban#126](https://github.com/oban-bg/oban/issues/126) — captures the exact "wait, this doesn't work?" moment an LLM-generated worker fails
- *"You can use atom keys but Oban will serialize them to JSON (that's why you need to use string keys in the `perform/1` function head)"* — [Michał Łępicki: Using structs for Oban worker arguments](https://blog.michallepicki.com/using-structs-for-oban-worker-arguments.html)
- *"iron laws include `atom keys instead of strings in job arguments` and `Storing Elixir structs directly in job args`"* — [oliver-kriska/claude-elixir-phoenix plugin](https://github.com/oliver-kriska/claude-elixir-phoenix), cited in `docs/research/elixir-llm-pain-points.md#7-oban-non-idempotent-jobs-atom-keys-stored-structs`

**Suggested challenge angles**:
- Ask Claude to enqueue a job from a `%User{}` struct — check the generated code uses `%{"user_id" => user.id}`, not `%{user: user}`
- Ask Claude to pass a `Decimal` (or `DateTime`) through args — the correct approach is `Decimal.to_string/1` before enqueue, `Decimal.new/1` inside `perform/1`
- Ask Claude to refactor a broken worker where args use atom keys to the idiomatic form (regex checks: no `:atom =>` inside `perform/1` function head)

**Tier guidance**: This is the flagship capability — prioritize 6-8 binary challenges here. Easy: fix atom keys. Medium: handle `Decimal`/`DateTime` round-trip. Hard: fix a worker that assumes a struct round-trips. Legendary: a worker passing a list of mixed-type tuples where the answer requires a custom serialization layer.

---

### Capability: `retry-strategy`

**Description** (from README.md): Backoff functions (`backoff/1` callback), `max_attempts`, exponential vs linear vs custom.

**Known Claude failure modes**:
- [MED] Sets `max_attempts: 1` defensively without realizing this disables Oban's retry semantics entirely (and defeats the point of using Oban)
- [MED] Writes a custom `backoff/1` without accepting the `%Oban.Job{}` struct argument — calls signature mismatch at compile time
- [MED] Overrides `backoff/1` to return a fixed small value (e.g., 10) without realizing this creates a tight retry loop burning attempts
- [LOW] Reinvents a retry loop inside `perform/1` using `Process.sleep` + recursion, not trusting Oban's retry behavior

**Citations**:
- *"By default, jobs are retried up to 20 times. The number of retries is controlled by the `:max_attempts` value, which can be set at the worker or job level."* — [Oban error_handling HexDocs](https://hexdocs.pm/oban/error_handling.html)
- *"The retry delay has an exponential backoff with jitter. This means that the delay between attempts grows exponentially (8s, 16s, and so on), and a randomized 'jitter' is introduced for each attempt."* — [Oban error_handling HexDocs](https://hexdocs.pm/oban/error_handling.html)
- *"Alternative backoff strategies include: constant — delay by a fixed number of seconds, e.g. 1→15, 2→15, 3→15; linear — delay for the same number of seconds as the current attempt, e.g. 1→1, 2→2, 3→3; squared — delay by attempt number squared, e.g. 1→1, 2→4, 3→9; sidekiq — delay by a base amount plus some jitter, e.g. 1→32, 2→61, 3→135"* — [Oban.Worker HexDocs](https://hexdocs.pm/oban/Oban.Worker.html)
- *"The unsaved error map can be used by backoff/1 to calculate a custom backoff based on the exact error that failed the job. For example, you can check if the error was due to rate limiting and adjust the backoff accordingly."* — [Oban.Worker HexDocs](https://hexdocs.pm/oban/Oban.Worker.html)

**Suggested challenge angles**:
- Write a `backoff/1` that returns `5 * 60` when the error is a rate-limit and default exponential otherwise
- Fix a worker where `max_attempts: 1` is set "for safety" — explain why this is wrong
- Replace a hand-rolled `Process.sleep` retry loop with Oban's native retry by restructuring `perform/1` to return `{:error, ...}`

**Tier guidance**: Medium binary — 5-6 challenges. Test both the `backoff/1` callback signature and the runtime branching on error reason.

---

### Capability: `unique-constraints`

**Description** (from README.md): `unique: [period:, keys:, states:]`; deduplication semantics.

**Known Claude failure modes**:
- [HIGH] Writes `unique: [keys: [:user_id]]` but omits `:period`, relying on the default (60 seconds) without realizing that's almost never what the caller wants
- [HIGH] Excludes `:available` from `:states` when constructing a partial state list — this causes queue crashes (documented multiple times on Elixir Forum) because a newly-scheduled job can collide with an already-available job and the unique constraint is enforced at insert
- [MED] Confuses "unique insertion" with "serialized execution" — writes a unique constraint expecting only one job runs at a time, but uniqueness is an **insert-time** check only
- [MED] Adds `unique: [period: 604800]` (one week) without aligning the pruner `max_age`, so the records get deleted and uniqueness silently stops working

**Citations**:
- *"You should always specify a period, otherwise Oban will default to 60 seconds."* — [Oban unique_jobs HexDocs](https://hexdocs.pm/oban/unique_jobs.html)
- *"A common misunderstanding is that unique jobs run one at a time or in sequence. This isn't true—uniqueness only prevents duplicate insertions... Uniqueness operates at job insertion time... has no bearing on whether jobs are executed concurrently."* — [Oban unique_jobs HexDocs](https://hexdocs.pm/oban/unique_jobs.html)
- *"There is a worker with the following unique configuration: [fields: [:queue, :worker, :args], keys: [:conversation_id], states: [:scheduled, :executing, :retryable]]. As you can see, the `available` state was not included... crashed the queue and started creating hundreds of producers for the same queue."* — thiagogsr, [Elixir Forum: Oban unique constraint crashes the queue](https://elixirforum.com/t/oban-unique-constraint-crashes-the-queue/69648)
- *"I just needed to make sure the pruner didn't nuke the oban_jobs table so there was something to unique check against!"* — reporter, [Elixir Forum: Unique Oban jobs with period still seems to insert into DB](https://elixirforum.com/t/unique-oban-jobs-with-period-still-seems-to-insert-into-db/52256)
- *"you leave the default `:fields`, otherwise you risk unexpected conflicts between unrelated jobs."* — [Oban unique_jobs HexDocs](https://hexdocs.pm/oban/unique_jobs.html)

**Suggested challenge angles**:
- Write a daily report generator with a unique constraint that covers "at most one per report_id per day"
- Given a worker config that excludes `:available` from `:states`, identify the bug and propose the fix (either the full list, `:successful`, or `:incomplete`)
- Given a worker using `unique: [period: 604800]`, recognize that it requires pruner alignment and add a comment or reconfigure

**Tier guidance**: Medium-to-Hard binary — 7-8 challenges. The state-list trap is a great "legendary" because the correct answer requires both Oban maintainer knowledge and defensiveness about partial state lists.

---

### Capability: `cron-scheduling`

**Description** (from README.md): `Oban.Plugins.Cron`, crontab format, timezone handling, `Oban.Plugins.Cron.Worker`.

**Known Claude failure modes**:
- [HIGH] Uses a non-UTC timezone in the `:timezone` option without adding the `tz` (or `tzdata`) library as a dependency — Oban crashes at boot
- [MED] Attempts to modify the crontab at runtime (hot reload, new periodic jobs from a database) using the free plugin — the free `Cron` plugin loads **statically at boot time**; runtime config is Oban Pro `DynamicCron`
- [MED] Uses `"* * * * *"` with a long-running worker and doesn't add a unique constraint — schedules pile up on top of in-flight jobs
- [MED] Invents a cron expression that's not supported (seconds-precision, `@every 5s`) — Oban cron has one-minute resolution minimum

**Citations**:
- *"`:timezone` — which timezone to use when scheduling cron jobs. To use a timezone other than the default of `Etc/UTC` you must have a timezone database like [tz](https://hexdocs.pm/tz) installed and configured."* — [Oban.Plugins.Cron HexDocs](https://hexdocs.pm/oban/Oban.Plugins.Cron.html)
- *"This plugin only loads the crontab statically, at boot time."* — [Oban.Plugins.Cron HexDocs](https://hexdocs.pm/oban/Oban.Plugins.Cron.html)
- *"Periodic jobs are declared as a list of `{cron, worker}` or `{cron, worker, options}` tuples"* — [Oban.Plugins.Cron HexDocs](https://hexdocs.pm/oban/Oban.Plugins.Cron.html)
- *"Long-running jobs may execute simultaneously if the scheduling interval is shorter than the time it takes to execute the job."* — [Oban periodic_jobs HexDocs](https://hexdocs.pm/oban/periodic_jobs.html)
- *"Cron scheduling has a one-minute resolution at minimum."* — derived from [Oban.Plugins.Cron HexDocs standard cron format](https://hexdocs.pm/oban/Oban.Plugins.Cron.html)

**Suggested challenge angles**:
- Schedule a daily cleanup at 3am in `America/New_York` — correct answer must set `:timezone`, document the `tz` dependency, and use `"0 3 * * *"`
- Schedule a long-running report worker that takes ~20 minutes every 5 minutes — identify the overlap risk, add `unique: [period: 300, states: [:available, :scheduled, :executing]]`
- Given a `"@every 30s"` crontab entry, identify it as not-supported and suggest the sub-minute alternative (use a self-rescheduling job)

**Tier guidance**: Medium binary — 6-7 challenges. The timezone dependency trap is the strongest "legendary" candidate.

---

### Capability: `return-values`

**Description** (from README.md): `:ok`, `{:ok, val}`, `{:error, reason}`, `{:discard, reason}`, `{:snooze, seconds}`.

**Known Claude failure modes**:
- [HIGH] Returns `{:discard, reason}` or `:discard` — these are **deprecated** in Oban 2.17+; the correct form is `{:cancel, reason}`. LLMs trained on blog posts from 2021-2023 reliably get this wrong
- [HIGH] Raises an exception on a rate-limit response from an external API instead of returning `{:snooze, seconds}` — this wastes an attempt and pollutes the error tracker
- [MED] Returns `{:ok, some_result}` and assumes the `some_result` is persisted or used — the docs explicitly note it's ignored
- [MED] Returns `{:noreply, state}` from GenServer muscle memory

**Citations**:
- *"`:ok` or `{:ok, value}` — the job is successful and marked as `completed`. The `value` from success tuples is ignored."* — [Oban.Worker HexDocs](https://hexdocs.pm/oban/Oban.Worker.html)
- *"`:discard` and `{:discard, reason}` are deprecated in favor of `{:cancel, reason}`."* — [Oban.Worker HexDocs](https://hexdocs.pm/oban/Oban.Worker.html)
- *"`{:snooze, period}` — mark the job as snoozed and schedule it to run again after the specified period."* — [Oban.Worker HexDocs](https://hexdocs.pm/oban/Oban.Worker.html)
- *"When a worker receives a 429 (rate limited) status code, it should return `{:snooze, calculate_backoff(attempt)}` rather than letting it fail with backoff, which is better for handling rate limits."* — [Oban.Worker HexDocs (backoff recipe)](https://hexdocs.pm/oban/Oban.Worker.html)
- *"`{:cancel, reason}` — cancel executing the job and stop retrying it. An error is recorded using the provided reason. The job is marked as `cancelled`."* — [Oban.Worker HexDocs](https://hexdocs.pm/oban/Oban.Worker.html)

**Suggested challenge angles**:
- Given a `perform/1` that calls `raise` on an HTTP 429, rewrite it to return `{:snooze, 300}`
- Given a `perform/1` that returns `{:discard, :not_found}`, identify the deprecation and rewrite as `{:cancel, :not_found}`
- Given a `perform/1` branch that detects "data no longer needed," choose between `{:cancel, ...}` (stop retrying) vs `{:ok}` (job is complete) — the answer depends on whether the job's *intent* was achieved

**Tier guidance**: Easy-to-Medium binary — 6-7 challenges. Deprecation-aware tests make excellent "hard" items because they require post-2023 knowledge.

---

### Capability: `queues-and-priority`

**Description** (from README.md): Queue config in `config/runtime.exs`, priority lanes, concurrency per queue.

**Known Claude failure modes**:
- [MED] Uses `Application.get_env/2` inside `use Oban.Worker` options — this is a compile-time macro, so the env lookup freezes at compile time, causing test/prod config drift
- [MED] Sets `priority: 0` for every worker (the default) without understanding that 0 is the highest priority and 9 is the lowest — inverted mental model from "priority zero = none"
- [LOW] Defines a queue in `config.exs` but references a different name in the worker's `:queue` option (typo mismatch), which silently routes to `:default`

**Citations**:
- *"Like all `use` macros, options are defined at compile time. Avoid using `Application.get_env/2` to define worker options. Instead, pass dynamic options at runtime by passing them to the worker's `c:new/2` function."* — [Oban.Worker HexDocs](https://hexdocs.pm/oban/Oban.Worker.html)
- *"Integer from 0 (highest priority) to 9 (lowest priority). Defaults to `0`"* — [Oban.Worker HexDocs (:priority option)](https://hexdocs.pm/oban/Oban.Worker.html)
- *"The :queues option is a keyword list where the keys are queue names and the values are the concurrency setting or a keyword list of queue options. For example, setting queues to [default: 10, exports: 5] would start the queues default and exports with a combined concurrency level of 15."* — [Oban module HexDocs](https://hexdocs.pm/oban/Oban.html)
- *"Queues can be started, stopped, paused, resumed and scaled independently at runtime locally or across all running nodes."* — [Oban Defining Queues HexDocs](https://hexdocs.pm/oban/defining_queues.html)

**Suggested challenge angles**:
- Given a worker that references `Application.get_env(:my_app, :worker_queue)` inside its `use Oban.Worker`, refactor to use runtime `new/2` options
- Given three workers with business priority "critical / normal / low", assign correct `:priority` values (0, 5, 9) and explain the inverted intuition
- Given a `config.exs` with `queues: [mailers: 10]` and a worker `use Oban.Worker, queue: :mailer`, identify the typo

**Tier guidance**: Easy-to-Medium binary — 5-6 challenges. Thinnest-evidence capability in this family; avoid legendary.

---

### Capability: `testing-workers`

**Description** (from README.md): `Oban.Testing` macros, `inline` vs `manual` mode, asserting jobs were enqueued.

**Known Claude failure modes**:
- [HIGH] Uses `:inline` mode in a test suite that inserts jobs via a transactional flow then asserts with `assert_enqueued` — `assert_enqueued` requires `:manual` mode (inline jobs execute immediately and bypass the database)
- [HIGH] Writes `perform_job(MyWorker, %{user_id: 1})` and the test passes locally but fails in the helper because the helper converts args to string keys before calling `perform/1`, exposing the atom-key trap
- [MED] Uses `use Oban.Testing` without providing `repo:` — compile error in the generated helpers
- [MED] Forgets to use allowances when a background process triggers the job, so the Ecto sandbox swallows the DB changes

**Citations**:
- *"Only `:manual` and `:inline` mode are supported, as `:disabled` implies that supervised queues and plugins are running."* — [Oban.Testing HexDocs](https://hexdocs.pm/oban/Oban.Testing.html)
- *"This reduces boilerplate when constructing jobs for unit tests and checks for common pitfalls. For example, it automatically converts `args` to string keys before calling `perform/1`, ensuring that perform clauses aren't erroneously trying to match atom keys."* — [Oban.Testing HexDocs](https://hexdocs.pm/oban/Oban.Testing.html)
- *"The Oban.Testing module simplifies testing workers and making assertions about enqueued jobs when testing in `:manual` mode."* — [Oban testing intro HexDocs](https://hexdocs.pm/oban/testing.html)
- *"perform_* executes jobs locally without touching the database for unit testing; drain_* executes jobs inline for integration testing; and run_* inserts jobs into the database and executes them inline for integration testing."* — [Oban testing intro HexDocs](https://hexdocs.pm/oban/testing.html)
- *"The `with_safety` option controls whether to silently catch errors when draining, and when false, raised exceptions or unhandled exits are reraised."* — [Oban.Testing HexDocs](https://hexdocs.pm/oban/Oban.Testing.html)

**Suggested challenge angles**:
- Given a test using `assert_enqueued` that fails because the test module configures `:inline`, identify the conflict and switch to `:manual` (or use `with_testing_mode/2`)
- Use `perform_job/3` to unit-test a worker — the correct answer uses the helper, not a manual `MyWorker.perform(%Oban.Job{args: ...})` construction
- Test an async flow where a supervised process enqueues a job — the answer requires `Ecto.Adapters.SQL.Sandbox.allow/3`

**Tier guidance**: Medium binary — 6 challenges. The inline/manual confusion is a strong hard-tier item because it requires understanding Oban's test-mode semantics and Ecto sandbox behavior simultaneously.

---

### Capability: `telemetry-and-observability`

**Description** (from README.md): Subscribing to Oban telemetry events, span metrics, error reporting integration.

**Known Claude failure modes**:
- [MED] Writes a telemetry attach handler with the wrong event name — uses `[:oban, :worker, :exception]` or `[:oban_job_exception]` instead of the correct `[:oban, :job, :exception]`
- [MED] Uses `:telemetry.attach/4` inside `perform/1` — attaches a new handler on every job execution, causing handler leaks
- [LOW] Reaches for Sentry integration with a custom attach handler when `Sentry.Integrations.Oban` (or equivalents for AppSignal / ErrorTracker) would Just Work out of the box

**Citations**:
- *"Oban emits the following telemetry events for each job: `[:oban, :job, :start]` — at the point a job is fetched from the database and will execute, `[:oban, :job, :stop]` — after a job succeeds and the success is recorded in the database, and `[:oban, :job, :exception]` — after a job fails and the failure is recorded in the database."* — [Oban.Telemetry HexDocs](https://hexdocs.pm/oban/Oban.Telemetry.html)
- *"For :exception events the metadata includes details about what caused the failure... `:conf`, `:job`, `:state`, `:kind`, `:reason`, `:result`, `:stacktrace`"* — [Oban.Telemetry HexDocs](https://hexdocs.pm/oban/Oban.Telemetry.html)
- *"Telemetry events can be used to report issues externally to services like Sentry or AppSignal... Some libraries like AppSignal, ErrorTracker or Sentry automatically handle these events without requiring any extra code on your application."* — [Oban Ready for Production HexDocs](https://hexdocs.pm/oban/ready_for_production.html)
- *"Oban heavily utilizes Telemetry for instrumentation at every level, from job execution and plugin activity through to every database call with a telemetry event to hook into."* — [Oban.Telemetry HexDocs](https://hexdocs.pm/oban/Oban.Telemetry.html)

**Suggested challenge angles**:
- Attach a telemetry handler at application startup that counts failed jobs by worker name — correct answer uses `:telemetry.attach_many/4` with `[:oban, :job, :start]`, `[:oban, :job, :stop]`, `[:oban, :job, :exception]`, not arbitrary names
- Integrate Sentry error reporting for Oban — the correct "best-practice" answer uses the official Sentry integration or a single attach handler at app start, not logic inside `perform/1`
- Identify a leaky telemetry attach call (`:telemetry.attach/4` inside `perform/1`) and move it to `application.ex`

**Tier guidance**: Medium binary — 5 challenges. Event-name accuracy is a great easy/medium check.

---

### Capability: `transactional-jobs`

**Description** (from README.md): Inserting the job inside the same `Ecto.Multi` as the parent data, atomic enqueue.

**Known Claude failure modes**:
- [HIGH] Writes two separate calls: `Repo.insert(user); MyWorker.new(...) |> Oban.insert()` — a crash between the two leaves data in an inconsistent state
- [HIGH] Misses that `Oban.insert/2` has an `Ecto.Multi` form: `Ecto.Multi.new() |> Oban.insert(:job_name, changeset) |> Repo.transaction()`
- [MED] Uses `Oban.insert_all/2` for bulk enqueue and loses per-job unique constraint support (only the Smart Engine in Oban Pro supports bulk uniqueness)
- [MED] Chains `Oban.insert/2` inside a `Multi` but references the job name as an atom when the helper expects a string (mixed `Multi.insert(:a, ...)` vs `Oban.insert("a", ...)`)

**Citations**:
- *"Enqueue a job along with other database changes, ensuring that everything is committed or rolled back atomically... enqueueing jobs with Oban.insert/2 is transactional, which means it will be rolled back if the current transaction fails, ensuring that jobs are only enqueued if the related data changes are committed to the database."* — [Oban module HexDocs](https://hexdocs.pm/oban/Oban.html)
- *"`Ecto.Multi.new() |> Oban.insert("job-1", MyApp.Worker.new(%{id: 1})) |> Oban.insert("job-2", fn _ -> MyApp.Worker.new(%{id: 2}) end) |> MyApp.Repo.transaction()`"* — [Oban module insert/5 example](https://hexdocs.pm/oban/Oban.html)
- *"Only the Smart Engine in Oban Pro supports bulk unique jobs, automatic insert batching, and minimizes parameters sent over the wire. With the basic engine, you must use `insert/3` to insert unique jobs one at a time."* — [Oban module HexDocs](https://hexdocs.pm/oban/Oban.html)
- *"Iron Laws... the use of Ecto.Multi for complex transactions"* — [oliver-kriska/claude-elixir-phoenix plugin](https://github.com/oliver-kriska/claude-elixir-phoenix) (explicit architectural enforcement)

**Suggested challenge angles**:
- Given two separate `Repo.insert` + `Oban.insert` calls, refactor into a single `Ecto.Multi` transaction with rollback semantics
- Given an `Oban.insert_all` for 100 jobs that are supposed to be deduplicated, recognize that bulk uniqueness requires Oban Pro and either restructure as per-job insert or accept duplicates
- Write an Ecto.Multi that depends on a previous step (`Oban.insert(:job, fn %{user: user} -> Worker.new(%{"user_id" => user.id}) end)`)

**Tier guidance**: Medium-to-Hard binary — 6-7 challenges. The separation-of-calls bug is fundamental and underrepresented in LLM training data.

---

### Capability: `recurring-jobs-vs-cron`

**Description** (from README.md): `Oban.insert/2` with `scheduled_at` vs the Cron plugin; when each is right.

**Known Claude failure modes**:
- [MED] Reaches for cron for anything "periodic" even when the interval depends on data (e.g., "every user gets a digest X hours after they signed up" — this is *not* cron-shaped because the interval varies per user)
- [MED] Writes a self-rescheduling worker but reschedules at the *end* of `perform/1`, meaning retries re-trigger the reschedule and cause exponential growth of scheduled jobs
- [MED] Uses cron for a sub-minute interval, not knowing about the one-minute resolution minimum
- [LOW] Hard-codes a timezone offset (e.g., `-5`) in calculations instead of using `tz`

**Citations**:
- *"Delivering around the same time using cron-style scheduling would need extra book-keeping to check when a user signed up... The recursive scheduling approach is more accurate and entirely self contained"* — [Sorentwo: Oban Recipes Part 3 — Reliable Scheduling](https://sorentwo.com/2019/08/02/oban-recipes-part-3-reliable-scheduling)
- *"we'll keep retrying the job's business logic when the job retries, but we'll only schedule the next occurrence once"* — [Sorentwo: Reliable Scheduling](https://sorentwo.com/2019/08/02/oban-recipes-part-3-reliable-scheduling)
- *"at-most-once semantics for scheduling, and at-least-once semantics for delivery"* — [Sorentwo: Reliable Scheduling](https://sorentwo.com/2019/08/02/oban-recipes-part-3-reliable-scheduling)
- *"The first clause schedules the next iteration immediately, *before* attempting to delver the email"* — [Sorentwo: Reliable Scheduling](https://sorentwo.com/2019/08/02/oban-recipes-part-3-reliable-scheduling)
- *"Scheduled jobs can be scheduled at any time in the future, down to the second, while periodic (CRON) jobs automatically enqueue jobs on a cron-like schedule."* — [Oban periodic_jobs HexDocs](https://hexdocs.pm/oban/periodic_jobs.html)

**Suggested challenge angles**:
- Given "send a welcome email 24 hours after user signup," choose `schedule_in: @one_day` with the reschedule-first pattern — not cron
- Given a worker that reschedules itself at the end of `perform/1`, identify the retry amplification bug (reschedule must happen on the first attempt only, *before* the business logic)
- Given a cron entry `"*/30 * * * * *"` (seconds), recognize as invalid and convert to a self-rescheduling job

**Tier guidance**: Medium-to-Hard binary — 5-6 challenges. The reschedule-ordering bug is legendary-grade.

---

## Research process notes

Research took approximately 25 minutes. Primary sources were the official Oban HexDocs (Worker, Testing, Plugins.Cron, unique_jobs, error_handling, periodic_jobs, Telemetry, and the top-level Oban module), which are the definitive API reference but also explicitly document most of the LLM failure modes in the form of warnings and "common misunderstandings" sections — evidence that the Oban maintainers already know these traps.

Secondary corroboration came from: (a) the **oliver-kriska/claude-elixir-phoenix** plugin README and Iron Laws — the single strongest source, because each enforced rule is a Claude-generated-bug report; (b) **Parker Selbert / sorentwo** blog posts on sorentwo.com, particularly the "Oban Recipes Part 3: Reliable Scheduling" post that documents the correct self-rescheduling pattern; (c) Elixir Forum threads on unique constraint crashes (69648) and unique period confusion (52256), which provide verbatim developer narratives of the state-list trap; (d) **Michał Łępicki's blog post** on using structs for Oban worker arguments, which is the highest-quality single-author account of the serialization trap; (e) oban-bg GitHub issues #126 (atom keys converted to strings) with a direct Selbert response that explains the security rationale.

The three iron-law failure modes (idempotency, string keys, no structs) have multi-source corroboration with direct developer quotes. The "deprecated `{:discard, ...}` → `{:cancel, ...}`" failure mode is corroborated only by the official docs' deprecation note, but it is a reliable LLM trap because the old form appears in every pre-2024 Oban blog post. The timezone/tz dependency trap is corroborated by docs + deprecation history. The `unique-constraints` state-list trap has the richest developer narrative — the Elixir Forum thread includes a direct maintainer warning that only three safe configurations exist.

Thinnest capability: `queues-and-priority` — strong on the compile-time `Application.get_env/2` gotcha but otherwise light. No specific developer narratives about LLMs getting priority inversion wrong; it's inferential based on training data.

No findings were fabricated. All quotes are verbatim from the cited URLs. Where a quote is paraphrased or summarized, it is attributed with "derived from" or contextual framing.

## Capability prioritization (Phase 2 output)

| Capability | Evidence strength | Recommended primary count | Rationale |
|---|---|---|---|
| `worker-philosophy` (foundation) | HIGH | 10-12 | Foundation; explicit Iron Law. Needs cross-cutting challenges. |
| `perform-callback-basics` | HIGH | 6 | String-key trap is the load-bearing bug; test helper exists to catch it. |
| `args-serialization` | HIGH (flagship) | 8 | Three distinct traps (atom keys, structs, non-JSON types); multi-source. |
| `retry-strategy` | MED | 5 | Docs are strong, but developer-narrative evidence is thin. |
| `unique-constraints` | HIGH | 8 | Rich forum evidence; partial state-list trap is legendary-grade. |
| `cron-scheduling` | MED-HIGH | 7 | Timezone/tz dependency trap is documented; multi-trap capability. |
| `return-values` | HIGH | 7 | Deprecated `:discard` form is reliable LLM training trap; snooze-vs-raise is concrete. |
| `queues-and-priority` | LOW-MED | 5 | Thinnest capability; cap at the minimum. |
| `testing-workers` | MED | 6 | Inline/manual distinction + atom-key trap inherited. |
| `telemetry-and-observability` | MED | 5 | Event-name accuracy + handler-leak bug. |
| `transactional-jobs` | HIGH | 7 | Explicit Iron Law; two-call-insert bug is fundamental. |
| `recurring-jobs-vs-cron` | MED-HIGH | 6 | Sorentwo recipe is canonical; reschedule-ordering bug is legendary. |

**Total recommended primary-tagged challenges**: ~80 across foundation + 11 capabilities (within the ~100-challenge binary family target; the remainder is absorbed by secondary tagging — each challenge typically tags 1 primary + 1-2 secondary capabilities).

## Capabilities with insufficient public failure documentation

- **`queues-and-priority`**: The docs flag the compile-time `Application.get_env/2` trap and the 0-is-highest priority inversion, but I could not find a developer narrative of an LLM specifically getting this wrong. Evidence is inferential. Recommendation: cap at the minimum (5 challenges) and avoid legendary tier for this capability unless a specific adversarial example can be constructed from first principles.
- **`telemetry-and-observability`**: Docs are solid but no direct Claude-failure narrative was found. The handler-leak-in-perform bug is reasonable to test but not directly documented as an LLM failure mode in public sources. Recommendation: stay in the 5-challenge range, focus on event-name accuracy and integration patterns (which are easily verified by regex).
