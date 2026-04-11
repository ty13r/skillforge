# elixir-ecto-sandbox-test

**Rank**: #2 of 22
**Tier**: S (must-have, strongest evidence)
**Taxonomy path**: `testing` / `test-isolation` / `elixir`
**Status**: ⭐ NEW from research — surfaced as "the ugly" in the BoothIQ post-mortem; nothing in the original 10-family roster covered it

## Specialization

Helps Claude navigate `Ecto.Adapters.SQL.Sandbox` correctly: per-test transaction isolation, async-test safety rules, the `allow/3` pattern for background processes that share a connection, connection ownership transfer, and the Tidewave dev-vs-test database confusion that wastes hours of developer time.

## Why LLMs struggle

This is **the most-named "ugly" pain point** in the Elixir+AI research, directly cited in the BoothIQ post-mortem:

> *"It can't debug concurrent test failures. It doesn't understand that each test runs in an isolated transaction... Claude doesn't understand this. It uses Tidewave's dev DB connection and thinks it's looking at the test DB — which is always empty."*

Specific failure modes:
- Claude tries to **seed test databases** to force passing tests instead of understanding sandbox isolation
- Recommends **disabling async tests** as a "fix" when isolation breaks down (instead of fixing the actual ownership issue)
- Doesn't know about `Ecto.Adapters.SQL.Sandbox.allow/3` for background processes
- Doesn't understand connection ownership transfer when tasks spawn other tasks
- Can't distinguish dev DB connection (Tidewave's perspective) from test DB connection (test runner's perspective)

## Decomposition

### Foundation
- **F: `test-isolation-philosophy`** — How the skill frames test isolation: per-test-transaction (default Sandbox), per-process (manual checkout), or shared mode (only when isolation breaks down). Variants determine how every capability below presents tradeoffs.

### Capabilities
1. **C: `sandbox-checkout-and-modes`** — `Ecto.Adapters.SQL.Sandbox.checkout/2`, `:manual` vs `:auto` vs `:shared` modes, when each is appropriate
2. **C: `async-test-safety-rules`** — Which tests can be `async: true`, which can't, and why (sandbox + connection pool requirements)
3. **C: `allow-pattern-for-spawned-processes`** — `Ecto.Adapters.SQL.Sandbox.allow/3` for background processes that need DB access
4. **C: `connection-ownership-transfer`** — Passing ownership between processes; what happens when the owning process dies
5. **C: `liveview-sandbox-integration`** — Sandbox config for `Phoenix.LiveViewTest`; the special pattern of `Phoenix.Ecto.SQL.Sandbox` plug
6. **C: `channels-sandbox-integration`** — Sandbox for `Phoenix.ChannelTest`; allow on the channel process
7. **C: `oban-sandbox-integration`** — Testing Oban workers that hit the DB: inline mode vs manual mode
8. **C: `tidewave-dev-vs-test-trap`** — The specific BoothIQ-named bug: don't read from dev DB connection in test context
9. **C: `shared-mode-fallback`** — When per-process isolation truly breaks down and shared mode is unavoidable; what you give up
10. **C: `flaky-test-diagnosis`** — Recognizing test bleed between tests, identifying connection leaks, debugging "it passes alone but fails in suite"

### Total dimensions
**11** = 1 foundation + 10 capabilities

## Evaluation criteria sketch

- **Basic isolation test**: write a test that creates a record and asserts it exists; verify it doesn't leak to other tests
- **Async-safety test**: write 10 async tests that all create records with the same unique constraint — should not collide
- **Background process test**: spawn a Task inside a test that needs DB access; the Task should see the test's data
- **LiveView test**: write a `Phoenix.LiveViewTest` test that mounts a LiveView and verifies DB-backed assigns
- **Diagnosis test**: given a flaky test suite, identify the connection ownership bug

## Evidence

- [BoothIQ post-mortem](https://getboothiq.com/blog/150k-lines-vibe-coded-elixir-good-bad-ugly) — "the ugly" section
- [HN discussion](https://news.ycombinator.com/item?id=46752907)
- [Research report Part 1 #3](../../docs/research/elixir-llm-pain-points.md#3-ecto-sandbox--concurrent-test-isolation-misunderstanding)

## Notes

- **Should displace `elixir-phoenix-context`** in the active 10-family roster (per research recommendation).
- This family is highly **adjacent to `elixir-phoenix-liveview`** — LiveView tests are one of the main consumers of Sandbox patterns. Cross-reference but keep separate.
- Also adjacent to `elixir-oban-worker` — Oban tests have their own sandbox idioms.
- Hard to evaluate without a real Postgres instance running. The challenge pool's `score.py` will need to spin up a temp DB or mock the sandbox interactions.
