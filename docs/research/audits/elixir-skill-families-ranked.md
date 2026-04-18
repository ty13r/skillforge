# Elixir & BEAM Skill Families — Full Ranked Roster (66 families)

| Rank | Tier | Family | Source | Status |
|---|---|---|---|---|
| 1 | S | `elixir-phoenix-liveview` | Original | Validated — strongest evidence |
| 2 | S | `elixir-ecto-sandbox-test` | Original | Validated — "the ugly" pain |
| 3 | S | `elixir-security-linter` | Original | Validated — entire plugin tier |
| 4 | S | `elixir-ecto-query-writer` | Original | Validated — pin operator + preload bugs |
| 5 | S | `elixir-ecto-safe-migration` | Research | NEW — production-locking DDL, 80%+ reach, 4+ sources |
| 6 | S | `elixir-task-async` | Research | NEW — Task.async/await misuse, 80%+ reach, 4+ sources |
| 7 | S | `elixir-http-client` | Research | NEW — silent SSL bypass, adapter confusion, 80%+ reach |
| 8 | S | `elixir-ecto-multi-transaction` | Research | NEW — Ecto.Multi 4-tuple mishandling, 80%+ reach |
| 9 | S | `elixir-auth-session` | Research | NEW — JWT-for-sessions misuse, library confusion, 80%+ reach |
| 10 | A | `elixir-ecto-schema-changeset` | Original | Validated — float-for-money clincher |
| 11 | A | `elixir-oban-worker` | Original | Validated — 3 named failure modes |
| 12 | A | `elixir-pattern-match-refactor` | Original | Validated — most-cited complaint |
| 13 | A | `elixir-absinthe-resolver` | Research | NEW — N+1, subscription auth bypass, 50%+ reach |
| 14 | A | `elixir-plug-pipeline` | Research | NEW — halt semantics, ordering bugs, 80%+ reach |
| 15 | A | `elixir-ets-usage` | Research | NEW — race conditions, ownership lifecycle, 50%+ reach |
| 16 | A | `elixir-behaviour-mock` | Research | NEW — Mox/behaviour boilerplate, 80%+ reach |
| 17 | A | `elixir-phoenix-json-api` | Research | NEW — field exposure, error formatting, 50%+ reach |
| 18 | A | `beam-fault-tolerance` | BEAM research | NEW — "let it crash" misunderstanding, kill/killed signal rules, 80%+ reach |
| 19 | A | `beam-process-design` | BEAM research | NEW — when to use processes, selective receive O(n), mailbox design |
| 20 | B | `elixir-genserver-builder-and-smells` | Original | Reframed — teach when NOT to use |
| 21 | B | `elixir-error-tuple-handler` | Original | Runner-up |
| 22 | B | `elixir-otp-debugger` | Original | Runner-up |
| 23 | B | `elixir-stdlib-validator` | Original | Runner-up |
| 24 | B | `elixir-authorization` | Research | NEW — scattered policy logic, 80%+ reach but moderate evidence |
| 25 | B | `elixir-phoenix-upgrade` | Research | NEW — LiveView breaking changes, LLM-specific pain, 80%+ reach |
| 26 | B | `elixir-stream-resource` | Research | NEW — OOM on large data, Stream.resource cleanup, 50% reach |
| 27 | B | `elixir-erlang-interop` | Research | NEW — charlist/binary, :ssl defaults, 50% reach |
| 28 | B | `elixir-swoosh-email` | Research | NEW — TLS config since OTP 26, adapter switching, 50% reach |
| 29 | B | `elixir-registry-dynamic-sup` | Research | NEW — :via tuples, find-or-create races, 50% reach |
| 30 | B | `elixir-distributed-cluster` | Research | NEW — libcluster, net-split, cookie auth, 20-50% reach |
| 31 | B | `elixir-process-backpressure` | Research | NEW — unbounded mailboxes, cast vs call, 20-50% reach |
| 32 | B | `elixir-ash-resource` | Research | NEW — LLM-specific pain, official AI guidance built, 20% reach |
| 33 | B | `beam-concurrency-model` | BEAM research | NEW — reduction preemption, NIF scheduling, runtime model misconceptions |
| 34 | B | `beam-memory-management` | BEAM research | NEW — per-process heaps, 64-byte binary threshold, refc leaks |
| 35 | B | `beam-scheduler-tuning` | BEAM research | NEW — dirty schedulers, container misdetection, busy-wait flags |
| 36 | B | `beam-observability-debugging` | BEAM research | NEW — :recon, :sys.trace, OTP 27 trace sessions, crash dumps |
| 37 | C | `elixir-supervisor-tree` | Original | Thin evidence |
| 38 | C | `elixir-exunit-test-suite` | Original | Authoring isn't the pain — sandbox is |
| 39 | C | `elixir-umbrella-app` | Research | NEW — boundary enforcement, declining pattern, 20-50% reach |
| 40 | C | `elixir-rate-limiter` | Research | NEW — algorithm selection, window boundary bugs, 20-50% reach |
| 41 | C | `elixir-behaviour-protocol` | Research | NEW — behaviour vs protocol confusion, 20-50% reach |
| 42 | C | `elixir-binary-memory-gc` | Research | NEW — ref-counted binary leaks, 20% reach but severe impact |
| 43 | C | `beam-performance-profiling` | BEAM research | NEW — fprof/eprof/tprof (OTP 27), system_monitor, flame graphs |
| 44 | C | `beam-hot-code-upgrades` | BEAM research | NEW — two-version limit, appups/relups, code_change misconceptions |
| 45 | C | `beam-distribution-internals` | BEAM research | NEW — EPMD, single-TCP bottleneck, busy_dist_port, :pg vs :global |
| 46 | C | `beam-ets-internals` | BEAM research | NEW — words vs bytes, match specs, CA tree, DETS 2GB limit, Mnesia |
| 47 | D | `elixir-phoenix-context` | Original | DROPPED — zero evidence |
| 48 | D | `elixir-typespec-annotator` | Original | DROPPED — zero AI complaints |
| 49 | D | `elixir-phoenix-pubsub` | Research | NEW — topic sharding, Presence CRDTs, 20-50% reach |
| 50 | D | `elixir-caching-strategy` | Research | NEW — Cachex/Nebulex topology, invalidation, 20% reach |
| 51 | D | `elixir-gettext-i18n` | Research | NEW — POT workflow, plural forms, 20% reach |
| 52 | D | `elixir-native-interop` | Research | NEW — NIF safety, Rustler, dirty schedulers, 10-20% reach |
| 53 | D | `elixir-ecto-multi-tenant` | Research | NEW — prefix isolation, dynamic repos, 10-20% reach |
| 54 | D | `elixir-commanded-cqrs` | Research | NEW — aggregate memory, event versioning, <10% reach |
| 55 | D | `elixir-nx-ml` | Research | NEW — backend mixing, defn semantics, <10% reach |
| 56 | E | `elixir-phoenix-channel` | Original | Brainstormed; LiveView replaces |
| 57 | E | `elixir-broadway-pipeline` | Original | Enterprise niche |
| 58 | E | `elixir-telemetry-instrument` | Original | Observability cross-cutting |
| 59 | E | `elixir-macro-writer` | Original | Advanced escape hatch |
| 60 | E | `elixir-mix-task-writer` | Original | DX tooling |
| 61 | E | `elixir-binary-pattern-match` | Original | Low-level protocols |
| 62 | E | `elixir-release-config` | Original | Deployment niche |
| 63 | E | `elixir-port-external` | Research | NEW — zombie processes, command injection, 10-20% reach |
| 64 | E | `elixir-sage-distributed-tx` | Research | NEW — cross-service compensation, <10% reach |
| 65 | E | `elixir-nerves-firmware` | Research | NEW — embedded constraints, <10% reach |
| 66 | E | `elixir-membrane-pipeline` | Research | NEW — multimedia pipelines, <5% reach |

## Summary by tier

| Tier | Count | Profile |
|---|---|---|
| S | 9 | 80%+ reach, 4+ evidence sources each |
| A | 10 | 50-80% reach, strong evidence, includes BEAM fundamentals |
| B | 17 | 20-50% reach, moderate evidence, includes BEAM runtime layer |
| C | 10 | 20-50% reach, thin evidence or expert-level BEAM internals |
| D | 9 | 10-20% reach, speculative or niche |
| E | 11 | <10% reach, specialized or low-priority |

## Variant dimension estimate

| Scope | Families | Est. dimensions |
|---|---|---|
| Tier S + A only | 19 | ~155 |
| Through Tier B | 36 | ~295 |
| All 66 | 66 | ~530 |
