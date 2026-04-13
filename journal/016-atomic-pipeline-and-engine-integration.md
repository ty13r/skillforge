# SKLD — Project Journal

## Entry #16: The Atomic Pipeline Comes to Life

**Date**: April 13, 2026  
**Session Duration**: ~6 hours  
**Participants**: Matt + Claude Opus 4.6 (1M context) + Sonnet subagents  

---

### The Starting Point

Entry #15 closed with the frontend sprint shipped — SKLD-bench pages, taxonomy capabilities, homepage pipeline flow, journal browser, and the first round of scoring visibility. But the run detail page was still showing a molecular-era demo: generic "Variant A / Variant B" labels, an L1-L5 judging pipeline that no longer reflected reality, and no connection to the actual atomic evolution engine. Matt said "we need to redesign this for atomic evolution — it doesn't just need to be the demo, but the actual working pipeline."

---

### Phase 1: The Run Detail Redesign

The existing EvolutionArena was built for molecular evolution — spawn N variants, compete all on M challenges, judge, breed, repeat. Atomic evolution works fundamentally differently: decompose a skill into 12 dimensions, evolve each dimension independently (design 1 challenge, spawn 2 variants, compete, score, pick winner), then assemble the winners into one composite.

We built three new components:

**AtomicSidebar** — replaces the molecular ProcessFlow sidebar with a dimension progress tracker. Foundation dimensions listed first, then capabilities. Each dimension shows pending/running/complete status with fitness scores. A progress bar at the top shows overall completion.

**DimensionsOverview** — new default tab on completed runs showing per-dimension fitness bars with raw Sonnet baseline comparison and lift percentages. Summary cards for dimension count, avg fitness, baseline, and skill lift. Bench tier breakdown table.

**New `/api/runs/{runId}/dimensions` endpoint** — returns variant_evolutions joined with winning variants, sorted foundation-first. This gives the frontend the per-dimension status, tier, fitness, and winner info that the old generation-based API didn't expose.

### Phase 2: Phase 6 Engine Integration

With the UI showing what composite scoring looks like, we wired it into the actual evolution engine.

Three new modules built with Sonnet subagents in parallel:

**`engine/scorer.py`** — async wrapper around the composite scorer scripts. Uses `asyncio.to_thread()` to run the sync compile/AST/behavioral checks without blocking the event loop. Handles in-memory challenges (writes temp files for the L0 scorer). Returns zero-fallback on any error so the engine never crashes.

**`engine/transcript_logger.py`** — saves every competitor dispatch to the `dispatch_transcripts` table. Extracts prompt from trace, serializes the full trace as raw_response, includes composite score breakdown. Best-effort — never raises.

**Wired into `variant_evolution.py`** — after each competitor runs, the composite scorer scores the output and merges results into `pareto_objectives`. The transcript logger records everything. The existing `run_judging_pipeline` still runs after, augmenting with L2-L5 data.

### Phase 3: The Demo

The demo script was completely rewritten for atomic evolution. Instead of 3 generations of molecular breeding, it simulates 12 dimensions of atomic evolution with realistic Phoenix LiveView challenges, 3 competitors per dimension (baseline + seed + spawn), syntax-highlighted Elixir code output, and per-competitor composite score breakdowns.

Key decisions:

**3 competitors, not 2.** Matt wanted the raw Sonnet baseline visible during the run, not just the seed and spawn. This makes the comparison concrete — you can see the baseline's old `<%= for %>` templates vs the seed's modern `:for` directives vs the spawn's `stream/3` approach.

**Code output expanded by default.** The whole point of the tool is the code the models produce. Hiding it behind a toggle was "handwavy." Now each competitor card shows the actual Elixir code with syntax highlighting (Prism Elixir grammar added to CodeViewer), file path headers, and line counts.

**Permanent demo URL.** `/runs/demo-live` always has a running demo. The backend loops the atomic demo with 5-second pauses between iterations. The homepage "Watch Live Demo" button and InviteGate link both point here.

**Molecular layout removed entirely.** All runs going forward are atomic. No more fallback to the old generation-based view.

### Phase 4: Polish and QA

Code review (via Sonnet subagent) caught several issues:
- React hooks ordering bug (useMemo after early return)
- Status badge always green even on failure
- `scores_published` fitness lost when `activeDimension` already cleared
- Unstable useEffect dependency on array prop

All fixed, full test suite green (403 Python + 35 frontend).

The scoring display was updated throughout — "Judge L1-L5" replaced with the real 6-layer composite formula (Behavioral 40%, Compile 15%, AST 15%, L0 10%, Template 10%, Brevity 10%). Baseline context panel shows real SKLD-bench numbers.

Cleaned 102 junk test runs from the local DB (test artifacts from automated tests).

---

### Artifacts Produced
| Artifact | Lines | Purpose |
|---|---|---|
| `frontend/src/components/AtomicSidebar.tsx` | ~160 | Dimension progress tracker sidebar |
| `frontend/src/components/EvolutionArena.tsx` | ~560 | Complete rewrite for atomic pipeline |
| `frontend/src/components/AtomicRunDetail.tsx` | +280 | Dimensions tab with baseline comparison |
| `skillforge/engine/scorer.py` | ~120 | Async composite scorer for engine |
| `skillforge/engine/transcript_logger.py` | ~85 | Dispatch transcript persistence |
| `skillforge/engine/variant_evolution.py` | +65 | Composite scoring integration |
| `skillforge/api/debug.py` | ~370 | Atomic demo script rewrite |
| `skillforge/api/routes.py` | +47 | `/runs/{runId}/dimensions` endpoint |
| `frontend/src/components/SkillVariantCard.tsx` | +60 | Score breakdown + code output |
| `frontend/src/components/CodeViewer.tsx` | +20 | Elixir Prism grammar |

---

### Key Decisions Summary
| Decision | Rationale |
|---|---|
| Remove molecular layout entirely | All future runs are atomic. No point maintaining two code paths |
| 3 competitors per dimension (baseline + seed + spawn) | Makes the comparison concrete — user sees what raw Sonnet produces vs skilled variants |
| Code output expanded by default | The code IS the product. Hiding it undermines the demo |
| Permanent `/runs/demo-live` URL | Visitors can always see the pipeline in action without creating runs |
| Composite scorer in thread pool | Sync compile/AST/behavioral checks can't run on the event loop |
| Transcript logging is best-effort | Never block the engine. If logging fails, evolution continues |

---

### What's Next

- **Phase 6 verification**: Run a real `POST /evolve` with API calls to verify the composite scorer works in production (not just scripts). ~$5 API cost.
- **Scoring overhaul update**: When composite scores flow through real runs, the dimension fitness bars and competition brackets will show honest numbers instead of L0-based seed run data.
- **Opus raw baselines**: Deferred until Thursday subscription reset.

---

*"The demo isn't a demo anymore — it's the actual pipeline."*
