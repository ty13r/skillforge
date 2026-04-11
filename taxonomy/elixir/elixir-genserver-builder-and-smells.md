# elixir-genserver-builder-and-smells

**Rank**: #8 of 22
**Tier**: B (valuable, moderate evidence)
**Taxonomy path**: `development` / `otp-primitives` / `elixir`
**Status**: 🟡 Partially validated — REFRAMED based on research

## Specialization

Writes well-formed GenServer modules from a functional description (correct `init/1`, `handle_call/3`, `handle_cast/2`, `handle_info/2` callbacks, return tuple shapes, state shape, cleanup) AND — critically — teaches *when NOT to use a GenServer* in the first place. The "smells" half of the family is what makes it actually useful given the research findings.

## Why LLMs struggle

**The research insight**: the dominant Claude failure isn't writing GenServers wrong — it's **wrapping stateless code in GenServers for "organization"**. The plugin authors built an iron law:

> *"NO PROCESS WITHOUT A RUNTIME REASON"*
> — [georgeguimaraes/claude-code-elixir otp-thinking](https://github.com/georgeguimaraes/claude-code-elixir/blob/main/plugins/elixir/skills/otp-thinking/SKILL.md)

A naive "GenServer builder" skill would actually make things worse by giving Claude more confidence to over-use the pattern. The reframed family teaches both authoring correctness AND smell detection.

Specific failure modes:
- Wrapping plain modules in GenServers for "encapsulation"
- Confusing `handle_call` (sync) vs `handle_cast` (async) vs `handle_info` (external messages)
- Returning wrong tuple shapes (`{:ok, state}` where `{:reply, result, state}` is needed)
- Storing state in module attributes (impossible — module attrs are compile-time)
- Forgetting `start_link/1` public API

## Decomposition

### Foundation
- **F: `when-to-use-genserver`** ⭐ — The smell-detection philosophy. Variants: strict (default to plain modules, justify every process), pragmatic (use GenServer when obvious benefit), educational (show before/after pairs of "this should not be a GenServer"). The reframed foundation from the research insight.

### Capabilities
1. **C: `init-and-start-link`** — Public API conventions, arg passing, named registration
2. **C: `handle-call-patterns`** — Sync-with-reply, return tuple shapes (`{:reply, reply, state}`)
3. **C: `handle-cast-patterns`** — Async fire-and-forget, when it's appropriate
4. **C: `handle-info-patterns`** — External messages, timer callbacks, monitor messages, port messages
5. **C: `state-shape-design`** — Maps vs structs, initialization, invariants
6. **C: `terminate-and-cleanup`** — Resource release, logging, `terminate/2` caveats (not always called!)
7. **C: `timeouts-and-continuations`** — `{:reply, reply, state, timeout}`, `{:continue, ...}`, `handle_continue/2`
8. **C: `smell-detection`** ⭐ — Recognizing when NOT to use a GenServer (THE research insight)
9. **C: `alternatives`** — `Agent`, `Task`, `:ets`, `:persistent_term`, plain modules as substitutes
10. **C: `testing-genservers`** — Starting/stopping in tests, state inspection, call/cast verification

### Total dimensions
**11** = 1 foundation + 10 capabilities

## Evaluation criteria sketch

- **Smell test**: present a "GenServer that does nothing stateful" and ask the skill to refactor it; the right answer is "delete it, use a plain module"
- **Authoring test**: build a rate limiter GenServer (legitimate stateful use case)
- **Wrong-callback test**: present a GenServer that uses `handle_cast` for something that should be `handle_call`; identify the bug
- **Alternative-picker test**: present a stateful problem and ask the skill which OTP primitive to use (Agent vs GenServer vs Task vs ETS)

## Evidence

- [Research report Part 1 #2](../../docs/research/elixir-llm-pain-points.md#2-otpconcurrency-blindness-genservers-supervision-async)
- [BoothIQ post-mortem](https://getboothiq.com/blog/150k-lines-vibe-coded-elixir-good-bad-ugly)
- [georgeguimaraes/claude-code-elixir otp-thinking](https://github.com/georgeguimaraes/claude-code-elixir/blob/main/plugins/elixir/skills/otp-thinking/SKILL.md)

## Notes

- The reframing is critical. Without `smell-detection` as a first-class capability, this family makes Claude WORSE.
- Adjacent to `elixir-supervisor-tree` — they're often used together. Could potentially merge into one `elixir-otp-authoring` family if both prove thin individually.
- Adjacent to `elixir-otp-debugger` (runner-up) — debugging is the other half of the OTP pain.
