# elixir-otp-debugger

**Rank**: #10 of 22
**Tier**: B (valuable, moderate evidence)
**Taxonomy path**: `development` / `otp-primitives` / `elixir`
**Status**: 🆕 NEW from research — runner-up; debugging-focused, hard to evaluate

## Specialization

Helps Claude *reason about* a running Elixir/OTP system: reading `:observer` state, interpreting SASL crash reports, understanding process lifecycles, walking supervision trees, diagnosing memory leaks, and using `recon` for production-safe tracing. Authoring is NOT the focus — debugging is.

## Why LLMs struggle

The BoothIQ post-mortem explicitly flagged debugging (not authoring) as the OTP problem:

> *"Claude is useless for debugging OTP, Task, or async issues. It doesn't understand how processes, the actor model, and GenServers work together."*

The inputs to debugging are runtime artifacts (crash reports, observer dumps, message queue snapshots) rather than user prompts asking to "build a thing". Claude doesn't have mental models for what these artifacts mean.

## Decomposition

### Foundation
- **F: `debugging-methodology`** — Reactive vs proactive, evidence-driven vs hypothesis-driven. Variants determine how the skill structures investigation steps.

### Capabilities
1. **C: `observer-and-process-inspection`** — `:observer.start/0`, process tree walking, message queue inspection
2. **C: `crash-report-interpretation`** — Reading SASL crash reports, Logger output, exit reasons
3. **C: `trace-and-dbg`** — `:dbg`, `:sys.trace/2`, `IO.inspect/2` debug tricks
4. **C: `recon-library-usage`** — `recon`, `recon_trace`, production-safe tracing
5. **C: `supervisor-tree-walking`** — `Supervisor.which_children/1`, `DynamicSupervisor.count_children/1`
6. **C: `process-message-queues`** — `Process.info(pid, :message_queue_len)`, mailbox diagnosis
7. **C: `memory-profiling`** — `:recon_alloc`, binary leaks, large heap diagnosis
8. **C: `schedulers-and-reductions`** — Scheduler balance, busy-wait detection, reduction budgets
9. **C: `distributed-debugging`** — `:net_kernel`, `Node` inspection, cross-node tracing

### Total dimensions
**10** = 1 foundation + 9 capabilities

## Evaluation criteria sketch

This family is harder to evaluate than authoring families because the inputs are runtime artifacts. Possible challenge formats:

- **Crash report interpretation**: provide a SASL crash report, ask the skill to identify the failing process, exit reason, and likely root cause
- **Memory leak diagnosis**: provide a `:recon_alloc.memory(:binary)` snapshot, identify the leak source
- **Message queue diagnosis**: provide a process info dump showing a 100k message queue, identify the slow consumer
- **Supervisor tree walk**: given a tree structure, identify which child crashing would cause cascading restarts under `:one_for_all`

## Evidence

- [Research report Part 1 #2](../../docs/research/elixir-llm-pain-points.md#2-otpconcurrency-blindness-genservers-supervision-async)
- [BoothIQ post-mortem](https://getboothiq.com/blog/150k-lines-vibe-coded-elixir-good-bad-ugly)

## Notes

- **Hardest family to author** — challenge inputs are runtime artifacts, not prompts. May need a special challenge format that supplies a "system snapshot" file as setup.
- **Hardest family to evaluate** — there's no single "right answer" for many debugging questions; the score.py would need to check whether the skill identified the right ROOT CAUSE rather than matching exact text.
- Probably ship after the Tier S/A families to validate the SkillForge methodology on simpler families first.
