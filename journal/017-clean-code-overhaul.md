# SKLD — Project Journal

## Entry #17: The Clean-Code Overhaul

**Date**: April 19, 2026
**Session Duration**: ~6 hours
**Participants**: Matt + Claude Code (Opus 4.7, 1M context)

---

### The Starting Point

The codebase worked — atomic evolution ran end-to-end, seven Elixir
families were seeded, the homepage was shipping. But it had been built
in bursts. Matt put it plainly: "we vibe coded this thing in a couple
days and i'm certain the code is probably a mess." Then the challenge:
"imagine thousands of people are reviewing our codebase and they will
nitpick all the details."

The request had two parts. Build a concise clean-code reference doc
that captures Python + React/TS best practices (with a functional
preference). Then refactor the codebase to meet that standard.

---

### Phase 1: Write the rubric first

Every PR is reviewed against something. Rather than refactor first and
document after, the first wave landed `docs/clean-code.md` — a
341-line scannable rubric with ten sections (naming, functions,
errors, data, async, functional idioms, React/TS, testing, comments)
and a 15-item review checklist. Grounded in actual anti-patterns
found during exploration: `breeder.py:153` for bare-except-plus-print,
`evolution.py:46` for mutable globals, `AtomicRunDetail.tsx:131` for
raw fetch chains.

Putting the standard in writing first meant every subsequent PR had a
contract — the review decision was "does this match the doc?" rather
than "do I like this?"

---

### Phase 2: Tooling before surgery

Wave 1 was the least glamorous and probably the most load-bearing.
The codebase had ruff but no `mypy`, no ESLint, no Prettier, no
pre-commit hooks, no CI. Adding them surfaced 45 pre-existing ruff
errors on the stricter baseline, plus a flaky test
(`test_run_variant_evolution_happy_path`) that had been failing
intermittently for weeks — the symptom was "invalid x-api-key,"
which sounded like an Anthropic problem until CI exposed the root
cause. A sibling test in `test_config.py` was reloading the config
module with `SKILLFORGE_COMPETITOR_BACKEND=managed` and relying on
monkeypatch teardown order that didn't work the way the author
thought. CI on a clean checkout revealed it because there was no
stale local DB to paper over the damage.

The `test_taxonomy_api.py` failures followed the same pattern —
tests assumed a populated DB from prior `uvicorn` runs. On CI's
fresh filesystem, `TestClient(app)` didn't even trigger the
lifespan (you have to use it as a context manager). Fixed both by
entering `TestClient` correctly and pointing the bootstrap at a
per-test temp DB.

"CI surfaces latent bugs the local loop hides" is the cleanest way
to state the lesson.

---

### Phase 3: Cross-cutting hygiene

Wave 2 was the big one for exception discipline. 75 bare
`except Exception` catches across the codebase. Some were
unjustifiable — catch-and-print diagnostics that swallowed failures
into stdout. Some were legitimate boundaries — boot-time lifespan
steps that must never crash startup, LLM SDK calls that need to
degrade gracefully, WebSocket handlers that must always close
cleanly.

The rule the doc lays out: every broad catch carries a one-line
`# noqa: BLE001 —` comment that explains *why* it's a boundary. If
you can't write that comment honestly, it's not a boundary — narrow
the catch. Enabling ruff's `BLE + TRY` rule set turned this into a
forcing function: the reviewer sees every broad catch and has to
accept or reject the rationale.

Also landed in Wave 2: `skillforge/errors.py` (typed hierarchy —
`SpawnError`, `BreedError`, `ParseError`, etc., with `ParseError`
also inheriting from `ValueError` so legacy catches still match),
`skillforge/agents/_json.py` (one copy of `extract_json_array`
instead of two identical copies in spawner + challenge_designer),
and `skillforge/engine/run_registry.py` (eliminates the two
mutable module globals — `PENDING_PARENTS` and `_active_runs` —
behind explicit accessors).

---

### Phase 4: Hotspot decomposition

Wave 3a split `db/queries.py` (1363 LOC, 46 functions) into a
seven-submodule package — `_helpers`, `challenges`, `genomes`, `runs`,
`seeds`, `taxonomy`, `transcripts`. The `__init__.py` barrel re-exports
every public name so the 38 import sites never had to change. Largest
submodule landed at 416 LOC, under the doc's 500-LOC ceiling.

Wave 3b did the same for `api/routes.py` (704 LOC → four-submodule
package: `_helpers`, `evolve`, `runs`, `__init__`). The interesting
wrinkle: test patches like `patch("skillforge.api.routes.get_run", ...)`
target the *import site*, so after splitting the module, they had to
be retargeted to `patch("skillforge.api.routes.evolve.get_run", ...)`
for POST-endpoint tests and `...routes.runs.get_run` for GET-endpoint
tests. A quick reminder that "patch the lookup, not the definition."

---

### Phase 5: Frontend API layer

Wave 4 introduced TanStack Query. Before: 51 raw `fetch()` calls
scattered across 19 components, each with its own ad-hoc loading
state, error string, and retry logic. `AtomicRunDetail.tsx` led the
pack with 7 `useEffect`s chained to fetches and 9 `useState` hooks
— a 738-line god-component.

New infrastructure — `src/api/client.ts` (typed fetch wrapper with
`ApiError`), `src/api/hooks/runs.ts` (seven typed React Query hooks
keyed consistently as `["run", id, ...]`), QueryClientProvider in
`main.tsx` with SKLD-tuned defaults (retry=1, staleTime=30s, no
window-focus refetch — the WebSocket is the real-time channel, we
don't need it).

Then converted `AtomicRunDetail.tsx` as the exemplar:
738 → 625 LOC, 7 useEffect → 0, 9 useState → 1, 6 fetch() → 0. The
other 18 components are queued for future per-component
decomposition waves.

---

### Phase 6: Polish

Wave 6 ratcheted one more module into strict mypy (`engine/scorer.py`
passed after Wave 2's logging cleanup), updated `CLAUDE.md` to
point at the new standard, and wrote this entry.

---

### What's Next

Frontend hotspot decomposition (Wave 5 in the original plan) —
`PackageExplorer.tsx`, `SpecializationInput.tsx`, `PipelineSteps.tsx`,
and `EvolutionArena.tsx` are still above the 400-LOC TSX ceiling. Each
needs RTL smoke tests first (per the doc), then the fetch calls inside
can follow the `AtomicRunDetail` pattern. Picking them up is
non-urgent — the infrastructure is ready when the components are
opened for other reasons.

Remaining backend hotspots (`spawner.py` 805, `breeder.py` 619,
`variant_evolution.py` 622) are agent/engine logic. These want
"pure planner + thin I/O shell" decomposition rather than a
mechanical split, which is a different kind of refactor — worth doing
when there's a specific change that would benefit.

---

*"CI surfaces the bugs the local loop hides — and the more tooling you
wire up, the more honest the codebase becomes."*
