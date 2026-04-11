# elixir-supervisor-tree

**Rank**: #12 of 22
**Tier**: C (marginal, thin evidence)
**Taxonomy path**: `development` / `otp-supervision` / `elixir`
**Status**: 🟡 Partially validated — thin evidence; subsumed under broader OTP-blindness pain

## Specialization

Designs supervision trees with the modern child_spec format, correct restart strategies (`:one_for_one` / `:one_for_all` / `:rest_for_one`), `DynamicSupervisor` for variable-count children, nested supervisors, and proper `Application` integration.

## Why LLMs struggle

Real but thinner pain than the GenServer family. Failure modes:

- Mixing pre-1.5 `worker(MyMod, [args])` format with modern `%{id:, start:, restart:}` map
- Defaulting to `:one_for_one` regardless of actual failure dependency between children
- Not knowing when `DynamicSupervisor` beats `Supervisor`
- Forgetting to add new workers to the `Application` supervisor's children list
- Mishandling shutdown values (`:brutal_kill`, `:infinity`, integer timeouts)

## Decomposition

### Foundation
- **F: `supervision-philosophy`** — Flat vs nested, shallow vs deep trees. Variants determine the canonical tree shape.

### Capabilities
1. **C: `child-spec-format`** — Modern `%{id:, start:, restart:, shutdown:, type:}` map
2. **C: `restart-strategies`** — `:one_for_one`, `:one_for_all`, `:rest_for_one`, when each applies
3. **C: `max-restarts-and-intensity`** — `:max_restarts`, `:max_seconds` tuning
4. **C: `dynamic-supervisor`** — For variable-count children, `start_child/2`, `:transient` restart
5. **C: `nested-supervisors`** — Supervision subtrees for modularity
6. **C: `application-supervisor-tree`** — `Application.start/2` integration, `mix.exs` `application/0` callback
7. **C: `named-registry-vs-via-tuple`** — `Registry`, `:via` tuple, `{:global, name}` registration
8. **C: `shutdown-values-and-brutal-kill`** — `:brutal_kill`, `:infinity`, integer timeouts, when each applies

### Total dimensions
**9** = 1 foundation + 8 capabilities

## Evidence

- Mentioned in HN/Forum threads as part of broader OTP-blindness, but no dedicated post-mortems
- 1 explicit plugin rule about `worker(...)` format being deprecated

## Notes

- **Could be dropped** if the active roster is constrained to 7 families (per research recommendation).
- **Could be merged** with `elixir-genserver-builder-and-smells` into a single `elixir-otp-authoring` family — they're naturally adjacent and share evaluation surface.
- Real pain exists but it's subsumed under the broader "Claude doesn't understand processes" cluster. Building this family alone won't fix the underlying blind spot.
