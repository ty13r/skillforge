# elixir-oban-worker

**Rank**: #6 of 22
**Tier**: A (high-value, good evidence)
**Taxonomy path**: `development` / `background-jobs` / `elixir`
**Status**: ✅ Validated by research — three named failure modes from plugin iron laws

## Specialization

Writes Oban background job workers with `use Oban.Worker`, correct `perform/1` implementation, unique constraints to prevent duplicate jobs, retry strategies with backoff, cron scheduling via `Oban.Plugins.Cron`, queue configuration, and proper handling of return values (`:ok`, `:error`, `:discard`, `:snooze`).

## Why LLMs struggle

Oban is Elixir-specific and heavily underrepresented in the training corpus. Three named failure modes from the research:

- **Non-idempotent jobs**: Claude writes jobs that mutate state on every retry without checking if the work has already been done; Oban WILL retry on transient failures, so non-idempotent jobs cause data corruption
- **Atom keys instead of strings in args**: `Oban.Worker.new(MyWorker, %{user_id: 1})` won't survive serialization; must use `%{"user_id" => 1}`
- **Storing Elixir structs directly in args**: structs serialize to a flat map and lose their type — typically results in crash-on-retry

Other common mistakes:
- Missing `unique: [period: ...]` to prevent duplicate jobs
- Doesn't handle `{:discard, reason}` and `{:snooze, seconds}` return values
- Doesn't use `Oban.Plugins.Cron` for periodic jobs (tries to invent its own scheduler)

## Decomposition

### Foundation
- **F: `worker-philosophy`** — How the skill frames Oban workers: idempotent-by-default (assume retries), transactional (insert job + parent data in one Ecto.Multi), or eventually-consistent (best-effort). Frames every capability's recommendations.

### Capabilities
1. **C: `perform-callback-basics`** — The `perform/1` contract; receiving the `Oban.Job` struct; the return-value protocol
2. **C: `args-serialization`** ⭐ — **String keys only, no structs**; what survives JSON serialization
3. **C: `retry-strategy`** — Backoff functions (`backoff/1` callback), `max_attempts`, exponential vs linear vs custom
4. **C: `unique-constraints`** — `unique: [period:, keys:, states:]`; deduplication semantics
5. **C: `cron-scheduling`** — `Oban.Plugins.Cron`, crontab format, timezone handling, `Oban.Plugins.Cron.Worker`
6. **C: `return-values`** — `:ok`, `{:ok, val}`, `{:error, reason}`, `{:discard, reason}`, `{:snooze, seconds}`
7. **C: `queues-and-priority`** — Queue config in `config/runtime.exs`, priority lanes, concurrency per queue
8. **C: `testing-workers`** — `Oban.Testing` macros, `inline` vs `manual` mode, asserting jobs were enqueued
9. **C: `telemetry-and-observability`** — Subscribing to Oban telemetry events, span metrics, error reporting integration
10. **C: `transactional-jobs`** — Inserting the job inside the same `Ecto.Multi` as the parent data, atomic enqueue
11. **C: `recurring-jobs-vs-cron`** — `Oban.insert/2` with `scheduled_at` vs the Cron plugin; when each is right

### Total dimensions
**12** = 1 foundation + 11 capabilities

## Evaluation criteria sketch

- **Idempotency test**: write a worker that sends an email; verify it tracks `sent_at` so retries don't duplicate
- **String keys test**: write a worker that processes user actions; score.py checks args use string keys, not atoms
- **Unique constraint test**: write a report-generation worker; should use `unique: [period: 3600, keys: [:report_id]]`
- **Snooze test**: write a worker that hits an external rate limit; should return `{:snooze, retry_after_seconds}`, not raise
- **Cron test**: write a daily cleanup worker scheduled at 3am UTC via the Cron plugin
- **Transactional test**: enqueue an email job in the same Ecto.Multi as the user creation

## Evidence

- [Research report Part 1 #7](../../docs/research/elixir-llm-pain-points.md#7-oban-non-idempotent-jobs-atom-keys-stored-structs)
- [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix) — three iron laws

## Notes

- Oban is the de facto Elixir job queue — high-impact family despite the smaller surface area than LiveView/Ecto.
- The `args-serialization` capability is the single most important safety fix here.
- Adjacent to `elixir-ecto-sandbox-test` — testing Oban workers has its own sandbox quirks (the `inline` vs `manual` mode).
- Adjacent to `elixir-error-tuple-handler` — return-value protocol is `:ok` / `:error` / `:discard` / `:snooze`, which is a niche of broader error handling.
