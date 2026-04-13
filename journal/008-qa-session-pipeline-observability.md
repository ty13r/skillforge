# SkillForge — Project Journal

## Entry #8: QA Session — Pipeline Observability Overhaul

**Date**: April 9, 2026  
**Session Duration**: ~3.5 hours  
**Participants**: Matt + Claude Code (Opus 4.6)

---

### The Starting Point

Phase 1 of the Managed Agents port had landed (Entry #7). The backend worked — the smoke test proved it. But nobody had actually sat down and watched a real evolution run from the user's perspective through the full UI. Matt wanted to QA the app end-to-end with Chrome, and what followed was a sobering 3.5-hour session that surfaced the gap between "the backend works" and "the product works."

---

### Phase 1: Setting Up for QA

We started by configuring Chrome-in-the-loop QA — Claude Code driving the browser alongside Matt, both watching the same localhost:5173. The immediate question: should we use the preview tool's dev server (with backend log access) or Matt's existing servers? We chose to spin up our own so we could monitor backend logs directly. This turned out to be critical.

First discovery: clicking a completed run from the dashboard showed a running timer and a "Cancel Run" button. The `EvolutionArena` component only checked `sockState.isComplete` (from WebSocket events), but revisiting a finished run never replays those events. Fixed by checking `runDetail.status` from the REST API as a fallback.

### Phase 2: The 22-Minute Silence

Matt started a new evolution run from the "Fork from Registry" flow. The arena loaded. The timer started. And then... nothing. "Waiting for events from the engine..." for 22 minutes straight.

The backend logs showed only HTTP 200s and WebSocket open/close cycles. Zero engine output. The engine was silently hanging because:

1. The old `--reload` server had been killed by a code edit, orphaning the background task
2. The new server had no API key (`.env` loading race condition)
3. The `_active_runs` volatile dict was empty after restart

No logs. No warnings. No stale detection. The user had no way to know the engine was dead.

This was the turning point. Matt said: "we need a better way to QA this pipeline frontend and backend... this is the core product and I feel like we're flying blind here."

### Phase 3: The Observability Plan

We entered plan mode and did a thorough exploration of the existing infrastructure. Three parallel Explore agents mapped out: (1) testing coverage — 19 backend test files, only 2 frontend tests; (2) the event flow — 15 event types, frontend handles 11, ignores 4, no per-layer judging events, no event replay; (3) error handling gaps — no zombie detection, no stale banner, silent cleanup failures, `leaked_skills` table with zero callers.

The Plan agent synthesized this into a 15-item prioritized plan across three batches:
- **Batch 1** (immediate pain): structured logging, stale detection, zombie cleanup, card dedup fix
- **Batch 2** (deeper observability): per-judging-layer events, event timestamps, cleanup error logging, admin endpoint, event persistence, copy debug info
- **Batch 3** (test hardening): integration tests, WebSocket tests, frontend hook tests, enhanced health endpoint

Plus deployed-environment items: JSON logging for Railway, admin diagnostic endpoint.

### Phase 4: Building It

All three batches implemented in a single session. Key architectural choices:

**Structured logging** replaced every `print()` with `logging.getLogger()`. The critical insight: logging before AND after `asyncio.gather` for competitors — this is exactly where hangs become invisible. A single `logger.debug()` in `events.py:emit()` captures every event the system produces.

**Stale detection** was the cheapest high-impact fix. `lastEventAt` was already tracked in the socket hook but never consumed. One `useState` + one line in the timer effect = "No progress events for 90+ seconds" banner.

**Per-judging-layer events** turned L1-L5 from a multi-minute black box into visible progress. The frontend types already had `judging_layer1_complete` through `judging_layer5_complete` defined — they just never fired. Added `run_id` parameter to `run_judging_pipeline()` and emitted after each layer.

**Event persistence** writes every event to a `run_events` table for post-mortem debugging. Fire-and-forget from `emit()` so it never blocks the engine. Queryable via `GET /api/runs/{id}/events`.

### Phase 5: The Live Validation Run

With all three batches landed (334 tests passing), we ran a real managed agents evolution: 2 pop x 1 gen, fork from Python Utils seed.

The difference was night and day. Backend terminal showed:
```
00:36:50 INFO  run=b6c2d218 starting: spec=... pop=2 gens=1 backend=managed
00:36:51 INFO  run=b6c2d218 managed environment ready: env_015cVD...
00:37:42 INFO  run=b6c2d218 3 challenges designed
00:38:17 INFO  run=b6c2d218 gen=0 gathering 6 competitor tasks (concurrency=5)
00:40:03 INFO  run=b6c2d218 gen=0 all 6 competitors finished
00:40:03 INFO  run=b6c2d218 gen=0 starting judging pipeline...
```

Every phase visible. No more mystery. The judging pipeline showed L1 through L5 completing individually with checkmarks. The arena displayed 6 competitor cards (2 skills x 3 challenges — the dedup fix working). The run completed with fitness 0.51.

One issue caught: budget stayed at $0.00 throughout the run. The cost_update event only fired once after judging, using the old heuristic. Fixed by emitting incremental cost updates after each competitor finishes with real token cost data from the managed agents session.

### Phase 6: Additional QA Findings

During the session we also cataloged larger issues for the backlog:
- **Seed skills aren't full packages** — SKILL.md-only, no scripts/references/assets per the golden template
- **Competitor cards are opaque** — no skill differentiation, no challenge context, no streaming trace
- **No control labeling** — the elite carry (original seed) isn't visually distinguished
- **Cost estimates need recalibration** for managed agents (parallel runs change timing dramatically)
- **BYOK** — no comfortable solution for letting users bring their own API key

All added to PLAN-V1.2 as structured backlog items with clear scoping.

---

### Artifacts Produced

| Artifact | Purpose |
|---|---|
| `skillforge/main.py` | logging.basicConfig + JSON formatter + zombie cleanup |
| `skillforge/engine/events.py` | Event timestamps + persistence + debug logging |
| `skillforge/engine/evolution.py` | Structured phase logging + real cost tracking |
| `skillforge/api/websocket.py` | Connection logging |
| `skillforge/api/routes.py` | Run start/complete logging + events endpoint |
| `skillforge/api/debug.py` | Admin diagnostic endpoint + fake-run cost events |
| `skillforge/agents/judge/pipeline.py` | Per-layer event emission |
| `skillforge/agents/competitor_managed.py` | Cleanup callbacks + leaked_skills wiring + timestamp fix |
| `skillforge/db/database.py` | run_events table |
| `skillforge/db/queries.py` | mark_zombie_runs + event queries |
| `frontend/src/hooks/useEvolutionSocket.ts` | Card dedup fix + layer tracking + incremental cost |
| `frontend/src/hooks/useEvolutionSocket.test.ts` | 11 new test cases |
| `frontend/src/components/EvolutionArena.tsx` | Stale banner + completed run fix + copy debug info |
| `frontend/src/components/EvolutionResults.tsx` | REST fallback for fitness/cost/bestSkillId |
| `tests/test_evolution_integration.py` | Full event sequence test with 30s timeout |
| `tests/test_websocket_integration.py` | Fake-run through WebSocket |
| `plans/PLAN-V1.2.md` | 5 new backlog sections |

---

### Key Decisions Summary

| Decision | Rationale |
|---|---|
| Log before AND after asyncio.gather | This is where hangs become invisible — the single most diagnostic log site |
| 90-second stale threshold | Long enough to not false-positive during slow LLM calls; short enough to catch real stalls |
| Zombie cleanup on startup, not recovery | Run recovery requires checkpointing; marking as failed is immediate and honest |
| Event persistence via fire-and-forget task | Never blocks the engine; best-effort is fine for debugging data |
| Incremental cost updates per competitor | Users need real-time feedback, not a summary after judging |
| Card dedup key includes challengeId | The skill x challenge matrix is the fundamental unit, not just the skill |

---

### What's Next

The observability infrastructure is solid. The next session should:

1. **Run a full 5x3 evolution** on managed agents and validate cost tracking end-to-end
2. **Start the Rich Skill Variant Cards** backlog item — the arena still looks rough
3. **Deep research for 15 real Gen 0 skills** — the current seeds are SKILL.md-only
4. **Push to Railway** and validate the JSON logging + admin endpoint in production

The pipeline QA uncovered that the gap between "backend works" and "product works" is mostly in the frontend's ability to tell the user what's happening. The engine is solid; the presentation layer needs the same care.

---

*"You can't QA what you can't see."*
