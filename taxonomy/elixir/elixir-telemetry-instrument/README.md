# elixir-telemetry-instrument

**Rank**: #18 of 22
**Tier**: E (brainstormed runner-up; no research signal)
**Taxonomy path**: `development` / `otp-primitives` / `elixir`
**Status**: Brainstormed; observability cross-cutting

## Specialization

Writes Elixir code that emits and consumes `:telemetry` events: `:telemetry.execute/3` for emission, `:telemetry.attach/4` for handlers, `Telemetry.Metrics` for metric definitions, `:telemetry.span/3` for measurement spans, and integrations with library-emitted events from Phoenix, Ecto, Oban.

## Why this family is here

Telemetry is the standard observability primitive in Elixir, used by every major library. The pain is that handlers must be carefully written (no failures, no slow operations, no leaks) and Claude doesn't always know the conventions. But the research found **no specific Telemetry-related Claude failures**.

## Decomposition

### Foundation
- **F: `telemetry-philosophy`** — Pull vs push, metric naming conventions, what events to emit

### Capabilities
1. **C: `event-emission`** — `:telemetry.execute/3`, event naming conventions, measurement vs metadata
2. **C: `handler-attachment`** — `:telemetry.attach/4`, handler functions, error handling in handlers
3. **C: `metrics-module`** — `Telemetry.Metrics`, counter/distribution/summary/last_value
4. **C: `span-measurement`** — `:telemetry.span/3` for wrapping operations
5. **C: `integration-with-ecto-phoenix-oban`** — Subscribing to library-emitted events
6. **C: `aggregation-and-export`** — Prometheus, StatsD, OpenTelemetry exporters

### Total dimensions
**7** = 1 foundation + 6 capabilities

## Notes

- Cross-cutting concern more than a standalone skill. Low priority for the active roster.
