# SkillForge — Project Journal

## Entry #4: Post-MVP Polish and the v1.1 Push

**Date**: April 9, 2026 (evening → late evening)
**Session Duration**: ~4 hours
**Participants**: Matt + Claude Code (Opus 4.6, 1M context)

---

### The Starting Point

Entry #3 ended with Wave 6c complete and the first real live evolution passing (`c3c22eb`). The MVP was functional end-to-end: frontend renders, backend evolves, WebSocket streams, exports work, Railway auto-deploys. But the app still *felt* like a scaffold. The arena page was quiet during long phases. The sidebar didn't explain what was happening. Attempting to open a run URL rendered raw JSON because Vite's dev proxy was stealing `/runs/:id`. The Bible page existed but said "Coming in v1.1." The Registry was empty. There was no way for a visitor to see the app do its thing without paying API spend to witness it.

This session was the polish pass. Not a wave, not a milestone — a steady march of small, visible improvements that turned a functional MVP into something that could actually be demoed.

---

### Phase 1: Unblocking the SPA

The first bug Matt hit was the most embarrassing. He navigated to `localhost:5173/runs/demo-1` and got back `{"detail":"run demo-1 not found"}` — raw JSON, no UI. The Vite dev proxy had `/runs` hard-coded to forward to the backend, which meant React Router never saw the client-side route. It was forwarding `/runs/demo-1` as a GET to `http://localhost:8000/runs/demo-1`, which hit the REST API's `GET /runs/{id}`, which 404'd because no DB row matched.

The fix was structural: namespace the entire REST API under `/api/*`. `APIRouter(prefix="/api")` on `routes.py`, then chase every `fetch("/runs")` / `fetch("/evolve")` through the frontend and every `client.get("/runs/...")` through `test_api.py`. The Vite proxy simplified down to just `/api` and `/ws`. After the refactor, `/runs/:id` was a clean client-side route and the arena loaded properly.

Matt wanted to test this without paying for a real run, so I added a dev-only "Start Fake Run" button that POSTed to a new `/api/debug/fake-run` endpoint. That endpoint spawned a background task which pushed a scripted sequence of events into the in-process queue — `run_started`, `challenge_design_started`, `challenge_designed`, `generation_started`, `competitor_started/finished`, `judging_started`, `scores_published`, `cost_update`, `generation_complete`, `evolution_complete`. The frontend WebSocket consumer read them as if they came from a real run. No AI calls, free to trigger, and the whole animation surface lit up.

---

### Phase 2: Fake-Run Aesthetics

Matt pressed the button and the UI worked — but the empty state at the end was glaring: the SKILL.md preview pane just showed `View raw SKILL.md →` over a sea of black pixels. Real runs have a `best_skill` persisted in the DB that the export endpoint renders as Markdown; fake runs don't. Fixed that by fetching the export in `EvolutionResults.tsx` and rendering a dashed-border "No Skill Artifact — this is a demo run" placeholder when the backend 404'd.

Then Matt said the demo looked great but was "a bunch of fake stuff" — literal strings like "(fake) Generation 0 surfaced..." and "Fake lesson #1.1 — imperative phrasing wins" appearing verbatim in the breeding report card. The narrative broke the illusion. I rewrote `_drive_fake_run` from scratch with a scripted narrative modeled after a real evolution of a pandas data-cleaning Skill:

- Specialization: *"Pandas DataFrame cleaning — handling missing values, deduplication, type coercion, and schema normalization for messy CSV ingestion"*
- 4 realistic challenge prompts each with specific file/column references ("Load customers.csv, handle mixed-type 'age' column…")
- 3 breeding reports that cite real bible patterns (pipeline composition, classification-before-action, diagnostic mutation)
- Lessons that sound like lessons a real Breeder would harvest ("Numbered workflow steps outperform prose for deterministic tasks", "Including 2+ I/O examples lifts correctness from ~60% to ~85%")
- A climbing fitness curve: 0.52 → 0.71 → 0.86 → 0.91 across 3 generations
- A realistic cost curve: $0.42, $0.58, $0.67

Paired that with default pacing at `speed=0.5` (half real-time) and slightly longer phase dwells so viewers could read the events as they came in. Renamed the button "Watch Live Demo" and ungated it from `import.meta.env.DEV`. Added a DEMO chip in the arena header whenever `runId` starts with `fake-`, so anyone watching knows what they're seeing.

---

### Phase 3: The Bible, For Real This Time

The Bible and Registry had been `<ComingSoon title="..." />` stubs for the entire MVP. Time to make them real.

Bible backend was simple: `api/bible.py` reads `bible/patterns/*.md`, `bible/findings/*.md`, and `bible/anti-patterns/*.md` from disk, extracts the first `# H1` as the title, returns everything grouped by category. Frontend was a two-column browser — sidebar navigation, main panel rendering markdown via `react-markdown`. The trick was the styling: by default `react-markdown` renders unstyled HTML, which looked wrong in a Tailwind app. I added a `.bible-prose` component class in `index.css` with targeted rules for every element (display-font H1s, secondary-colored H2s, code chips, blockquotes with a left border, proper list spacing) so the rendered markdown matched the rest of the app's voice.

The content in `bible/patterns/*.md` was thin — 34 to 45 lines per file, placeholder-ish. I spawned a Sonnet subagent with a detailed prompt to read `docs/skills-research.md` in full and rewrite the 5 pattern files with properly-structured patterns: Finding, Evidence (with verbatim metrics), How to apply, Example. The subagent came back claiming "no modifications necessary" but had actually written the files — they grew from 194 lines total to 439. I spot-checked: 7 description patterns with sections like "P-DESC-001: Front-load within 250 characters" citing the research report verbatim ("Descriptions are hard-capped at 250 characters in the skill listing regardless of total budget"). Real content. The Bible page was now worth opening.

Registry was simpler — no new backend needed, just a grid of completed runs from the existing `/api/runs` endpoint. Featured top-fitness card at the top, filter tabs (auto-derived from mode values in the data), sort dropdown, search. Click-through to the arena page for each run.

---

### Phase 4: The Spec Assistant and the Diff Viewer

Matt posted a screenshot of the `/new` page pointing at the Specialization Blueprint textarea: "it would be nice if we added an option here that would help guide users with AI to figure out what skill they want to build and prompt the system properly." Added to the backlog in the moment, then tackled it later in the session.

The Spec Assistant is a minimal chat UI that sits beneath the specialization textarea — closed by default with a "✨ Help me write this with AI" button, opens to a scrollable message history with a typing indicator and input. Backend is `api/spec_assistant.py` — a stateless `POST /chat` that takes the full message history and returns the next assistant turn. The clever bit is the completion signal: the system prompt tells Claude to emit a fenced ```json block with `{"final_spec": "..."}` when it's ready to commit, and `_extract_final_spec()` + `_strip_json_block()` parse that out with a regex. When the frontend gets a `final_spec` back, it calls `onSpecReady(spec)` which fills the textarea and shows a ✓ badge. Uses `AsyncAnthropic` directly, never the Agent SDK — same pattern as the Breeder.

The seed turn is hand-written: when `messages` is empty, the backend returns a canned greeting without calling the API. Free first turn, zero latency, and it makes the assistant feel instantly responsive.

The Skill Diff Viewer was the last v1.1 piece. Backend: new `GET /api/runs/{run_id}/skills/{skill_id}` that returns the full genome content for a single skill in a run (the existing lineage endpoint only returned metadata). Frontend: `/runs/:runId/diff` route with a left sidebar listing every lineage edge color-coded by mutation type (elitism=tertiary, crossover=secondary, mutation=primary, wildcard=warning) and a main panel showing the mutation rationale + a unified line-by-line diff via the `diff` npm package. Auto-selects the first non-elitism edge on load so the default view is actually interesting. Added a `⑂ View Lineage Diff` link on the results page so users discover it.

---

### Phase 5: Setting Up v1.1

Matt closed the session with a planning ask rather than a build ask. Four new items for the v1.1 backlog:

1. **Deep research across the skills landscape** — find 10-20 curated seed specializations users can click instead of typing into a blank textarea. Needs its own UI.
2. **Upload-your-own-skill** — let users hand us an existing SKILL.md and we evolve it for them (instead of spawning from scratch).
3. **Anthropic color palette** — retheme the app to match Anthropic's brand.
4. **Light/dark mode toggle** — with state persisted in a cookie.

"Let's plan this out first before we build it this time." So the next move is a proper plan doc — scope, file list, dependencies, open questions — not a code change.

---

### Artifacts Produced

| Artifact | Lines | Purpose |
|---|---|---|
| `skillforge/api/debug.py` (rewrite) | ~240 | Scripted fake-run narrative (pandas data cleaning) |
| `skillforge/api/bible.py` (new) | 61 | Bible entries endpoint reading `bible/*` from disk |
| `skillforge/api/spec_assistant.py` (new) | 140 | `POST /api/spec-assistant/chat` with final-spec JSON extraction |
| `skillforge/api/routes.py` (edit) | +30 | `/api/*` prefix, new `/runs/{id}/skills/{skill_id}` endpoint |
| `skillforge/main.py` (edit) | +4 | Mount bible + spec-assistant routers |
| `skillforge/config.py` (edit) | +1 | `spec_assistant` role in MODEL_DEFAULTS |
| `bible/patterns/*.md` (rewrite via subagent) | 439 total | 37 patterns + 15 anti-patterns from research report |
| `frontend/vite.config.ts` (edit) | simplified | Proxy forwards only `/api` + `/ws` |
| `frontend/src/components/AgentRegistry.tsx` (rewrite) | 200 | Registry grid w/ search, filter, sort, featured card |
| `frontend/src/components/BibleBrowser.tsx` (new) | 132 | Two-column markdown browser using `react-markdown` |
| `frontend/src/components/SpecAssistantChat.tsx` (new) | 190 | Collapsible chat panel on `/new` |
| `frontend/src/components/SkillDiffViewer.tsx` (rewrite) | 240 | Lineage diff viewer using `diff` npm package |
| `frontend/src/components/EvolutionResults.tsx` (edit) | +12 | Empty state for fake runs; ⑂ Diff Viewer link |
| `frontend/src/components/EvolutionArena.tsx` (edit) | +6 | DEMO chip when runId starts with `fake-` |
| `frontend/src/components/EvolutionDashboard.tsx` (edit) | +20 | Public "Watch Live Demo" button + `useNavigate` |
| `frontend/src/components/SpecializationInput.tsx` (edit) | +2 | Mount the SpecAssistantChat component |
| `frontend/src/index.css` (edit) | +35 | `.bible-prose` markdown styles |
| `frontend/src/App.tsx` (edit) | +5 | Routes: `/bible`, `/registry`, `/runs/:id/diff` |
| `frontend/src/vite-env.d.ts` (new) | 1 | Vite client types for `import.meta.env` |
| `tests/test_api.py` (edit) | 10 path updates | Migrated to `/api/*` namespace |
| `PLAN.md` (appended) | +150 | Post-MVP work log, both sessions |

---

### Key Decisions Summary

| Decision | Rationale |
|---|---|
| Namespace REST API under `/api/*` | Cleanest fix for the Vite proxy / SPA route collision; future-proofs against any new `/foo` backend route clobbering a client-side route |
| Scripted fake-run narrative (not randomized) | A scripted story reads like a real run; randomized output always feels fake no matter how good the templates are |
| Fenced-JSON completion signal for spec assistant | Decouples the conversation from the commit moment — assistant can keep chatting or hand off, frontend parses either way; same pattern as the existing JSON extractor in `spawner.py` |
| Canned seed turn for spec assistant (no API call) | First-turn latency is the worst UX; hand-writing the greeting costs nothing and makes the feature feel instant |
| `AsyncAnthropic` for spec assistant, not Agent SDK | Pure generation, no tool use needed; learned this lesson the hard way with the Spawner hang in Entry #3 |
| Subagent for bible content seeding | Long-form content extraction from a 518-line research report is exactly the kind of parallelizable work subagents are good at; kept the main context clean |
| `.bible-prose` Tailwind class over `@tailwindcss/typography` | Zero new deps, full control over branding, the content is targeted enough that a hand-rolled class is smaller than pulling in the plugin |
| Planning before building for the v1.1 batch | Matt explicitly asked. Prior sessions burned context thrashing on file moves; a plan doc freezes the design decisions before the code starts |

---

### What's Next

The next session is a planning session, not a build session. The plan doc needs to cover:

- **Seed specializations**: research approach (which domains? Python/web/data/security/ops? how many per category?), data structure (where do the seeds live — JSON file? bible directory? new dir?), UI (where on `/new` — above textarea? modal? carousel of cards?)
- **Upload existing skill**: backend endpoint accepting a zip or single SKILL.md file, validation via existing `validate_skill_structure`, how to wire it into the Spawner as a "gen 0 seed" instead of fresh generation, UI (drag-drop zone? file picker? paste-markdown?)
- **Anthropic color palette**: find the official palette, map it to the existing `primary`/`secondary`/`tertiary`/`surface` semantic tokens in `tailwind.config.js`, preserve the `shadow-glow` / hero-radial aesthetics or rework them
- **Light/dark toggle**: theme state management (context provider? Zustand? just a cookie + data attribute on `<html>`?), cookie strategy (httpOnly? samesite? expiry?), how to handle the Material Design 3 token system which is currently dark-only

Once the plan doc lands and Matt signs off, the build session follows.

---

*"Shipping polish always takes longer than shipping features — but it's the only thing users notice."*
