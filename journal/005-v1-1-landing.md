# SkillForge — Project Journal

## Entry #5: The v1.1 Landing

**Date**: April 9, 2026 (late evening → early morning)  
**Session Duration**: ~5 hours  
**Participants**: Matt + Claude Code (Opus 4.6, 1M context) + 3 background subagents

---

### The Starting Point

Entry #4 closed with the post-MVP polish pass complete and a `PLAN-V1.1.md` draft waiting for Matt's sign-off on four features: seed library, upload-existing-skill, Anthropic palette, light/dark toggle. The plan had 7 open questions. Matt came back to the session, said "yes to all your recs," and re-scoped the seed feature on the spot: seeds shouldn't be specialization templates on `/new` — they should be actual Gen 0 SkillGenomes living in the Registry that users can browse, export, or fork-and-evolve. That single change unified features §1 and §2 into one backend code path.

He also clarified the design system ask: use Anthropic's real brand, not evocative stand-ins. Go to anthropic.com, extract the actual tokens, apply them. And seed the Registry with 15 real Gen 0 Skills so it has content from day one.

---

### Phase 1: Research in Parallel (three agents, zero main-context cost)

I kept the main Opus context out of the research work entirely. Three Sonnet/Opus subagents ran in parallel while I rewrote `PLAN-V1.1.md` to reflect the re-scope.

**Agent A — Anthropic design system (Sonnet)**: fetched `anthropic.com` and `claude.com` via WebFetch, extracted what was available in the raw HTML. Came back with two literal brand hexes (`#d97757` clay, `#c6613f` accent) and `#131314` ink, plus one gap — the warm cream backgrounds and the full neutral ramp were hidden behind CSS custom properties that WebFetch couldn't resolve. Agent proposed inferred values as placeholders and flagged the gap in `design/anthropic-design-system.md`.

**Agent B — 15 Gen 0 Skills (Opus)**: read `docs/skills-research.md` and `bible/patterns/*.md` in full, then authored 15 production-quality SKILL.md bodies at `skillforge/seeds/__init__.py` (1,452 lines). Validated every seed against the bible patterns at build time via a `_build()` helper with runtime assertions: descriptions ≤250 chars, "Use when" + "NOT for" clauses present, 2-3 diverse examples, bodies under 500 lines, slugs matching `^[a-z0-9]+(-[a-z0-9]+)*$`, `SkillGenome` roundtrip clean. Returned with notes on patterns that repeated across seeds ("classify-before-act", "before/after diff", "rotate-before-remove") — good candidates for future bible promotions.

**Agent C — headless CSS var extraction (Sonnet)**: after Matt pointed me at the Geist Studio case study for Anthropic's brand and we confirmed the paid fonts were real (Anthropic Sans / Serif / Mono — custom, not Styrene/Tiempos), I launched a third agent to install Playwright in `/tmp`, open `anthropic.com` in headless Chromium, and dump every `--*` CSS custom property from `getComputedStyle`. Came back with **everything**: `--swatch--clay #d97757`, `--swatch--ivory-light #faf9f5` (the real warm cream), `--swatch--slate-dark #141413`, the full cloud ramp, the 10%/20% slate-faded border alphas, `--radius--main 0.5rem` (8px, not my 12px guess), and the Tailwind-HSL token system from claude.com. Bonus finding: the marketing site is serif-body/sans-display, but the **product app (claude.com) is sans-body/serif-display** — the opposite. SKLD.run should follow the product convention.

Total main-context cost of all three agents: roughly 3 tool calls to spawn them + 3 result notifications. The actual research, extraction, writing, and validation happened in sub-contexts I never loaded.

---

### Phase 2: Lock the Plan, Get Permission to Build

With the research in, I brought Matt the 7-item review checklist. He said "I'm good with your recs on 1–7," which resolved to:

1. **§3 palette first** (the screenshot he'd sent showed a bare dark Registry — palette swap was the most visible immediate win)
2. **Unified `/api/evolve/from-parent`** endpoint with `{parent_source: "registry" | "upload", parent_id}`
3. **Hash-based seed reload** on every boot
4. **Seeds immutable** — view / export / fork only
5. **Both `.md` and `.zip`** uploads accepted
6. **Fonts swap + colors** — not color-only. Inter + Source Serif 4 + JetBrains Mono as free alternatives to Anthropic Sans/Serif/Mono
7. **Three-state** theme toggle — light / dark / system

I locked the plan with a `✅ LOCKED` header on `PLAN-V1.1.md` and started building.

---

### Phase 3: Palette + Theme Toggle

This was the biggest structural change of the session. The existing MD3 token system used hardcoded hex values in `tailwind.config.js` (a dark-only palette with teal/purple/green accents). To support runtime theme swapping without renaming every `primary/20` class in the app, I moved the colors to CSS custom properties in `index.css`:

```css
:root, [data-theme="light"] {
  --color-primary: 217 119 87;           /* #d97757 clay */
  --color-surface: 250 249 245;          /* #faf9f5 ivory-light */
  --color-on-surface: 20 20 19;          /* #141413 slate-dark */
  /* ...20+ tokens */
}
[data-theme="dark"] { /* ...inverted */ }
```

Then remapped `tailwind.config.js` to reference them via the `rgb(var(--color-xxx) / <alpha-value>)` trick so the alpha-channel syntax (`primary/20`) kept working across the whole app. Swapped `font-display` from Space Grotesk → Source Serif 4, added Google Fonts import at the top of `index.css`.

Critically, I added a **no-flash inline script** in `index.html` that runs synchronously before React boots. It reads the `skld-theme` cookie, resolves "system" via `prefers-color-scheme`, and sets `document.documentElement.dataset.theme` before the first paint. This prevents the flash-of-wrong-theme that plagues every Vite SPA with client-side theme resolution.

`ThemeToggle.tsx` — a 3-state button group (☀ / 🖥 / 🌙) mounted in the AppShell top nav. `useTheme` hook manages cookie persistence and live reaction to `prefers-color-scheme` changes when set to "system". All CSS var swaps animate via a 200ms transition on `background-color`, `color`.

Recharts was a special case — it accepts color strings as props, not CSS classes. I wrote a tiny `useCssVar(name, alpha?)` hook that uses `getComputedStyle` + a `MutationObserver` on `[data-theme]` to return live `rgb(...)` strings. Charts auto-theme on toggle with zero extra code in the consuming components.

---

### Phase 4: Seeds in the Registry

Path decision: instead of building a new table or JSON-file-based seed system, load the 15 seeds into the DB as a **synthetic `seed-library` EvolutionRun** at app startup. Reuses every existing endpoint for free:

- `GET /api/runs` → Registry sees the seed library (filtered out for the Dashboard separately)
- `GET /api/runs/{id}/skills/{skill_id}` → seed detail view works
- `GET /api/runs/{id}/export` → download/copy buttons work
- No new tables, no migrations, no special cases on the read path

`seed_loader.py` computes a SHA-256 over the `SEED_SKILLS` list, stores the 12-char prefix in the run's specialization string, and on every boot checks if the stored prefix matches. If yes, skip. If no (seeds edited), delete and recreate. Idempotent, safe to call on every boot, reflects edits automatically.

`GET /api/seeds` — a separate in-memory endpoint that returns just the seed metadata (title, category, difficulty, traits, description) for the Registry frontend. Bypasses the DB entirely for this path since all 15 seeds live in module-level Python.

Registry UI rewritten with **two sections**: "✦ Curated Library · Gen 0 Skills" at the top (with category filter chips and per-card "View" + "⑂ Fork" buttons) and "Community Evolutions" below. `SeedDetailView.tsx` at `/runs/:runId/skills/:skillId` — full SKILL.md rendered via `react-markdown` with export buttons in the sidebar. Deep-link from any seed card to `/new?seed=<id>` for the fork flow.

---

### Phase 5: Upload Existing Skill

`POST /api/uploads/skill` accepts `.md` or `.zip`. Validation runs through the existing `validate_skill_structure()` in `engine/sandbox.py` — same authoring constraints as evolved skills. Safety caps: 1MB upload, 5MB unpacked, 100 files max, 20:1 compression ratio limit, path-traversal rejection, allowed-extension allowlist (`.md, .sh, .py, .txt, .json, .yml, .yaml`).

Valid uploads land in an in-memory `_UPLOADS: dict[upload_id, SkillGenome]` cache. The unified `POST /api/evolve/from-parent` endpoint resolves both `parent_source: "registry"` and `parent_source: "upload"` against their respective sources, stashes the resolved `SkillGenome` in a module-level `PENDING_PARENTS` dict keyed by the new run's id, and kicks off `run_evolution()`. The engine picks up the pending parent at gen-0 spawn time and routes through `spawner.spawn_from_parent()` instead of `spawn_gen0()`.

`spawn_from_parent` is a new spawner function: it carries the parent forward as elite (slot 0, unchanged) and calls the LLM to generate `pop_size - 1` diverse mutations preserving the core capability but varying description phrasing, instruction structure, and trait emphasis. Falls back to elite-only if the LLM refuses or produces invalid JSON — graceful degradation means evolution can still proceed even if mutation fails.

`SkillUploader.tsx` — drag-and-drop zone with inline validation feedback, 1MB size cap, live error list. `SpecializationInput` gets a 3-mode toggle at the top: "From Scratch" / "Upload Existing" / "Fork from Registry". Picking Upload hides the textarea and shows the uploader. Picking Fork shows the 15-card grid with category filter chips.

---

### Phase 6: Polish Passes

Three rapid rounds of visual fixes after Matt sent screenshots:

**Round 1**: Dashboard was blending everything into warm cream. Fixed by:
- Separating `--color-surface-low` from page bg (`#f4f2ea` vs `#faf9f5`)
- Adding hairline borders (`border border-outline-variant`) to every card
- Filtering the seed-library run from the Dashboard list (still visible in Registry)
- Fixing `<span className="text-secondary">` on the hero headline — "secondary" in the Anthropic mapping is slate-dark, invisible against cream. Changed to `text-primary` (clay orange)
- Sticky nav header with stronger backdrop

**Round 2**: Empty Dashboard when no user runs — seeded it with 6 curated Gen 0 cards in the "Recent Evolutions" slot. Empty state becomes a "Try a Curated Gen 0 Skill" featured grid, complete with View/⑂ Fork buttons per card.

**Round 3**: Matt pointed at two issues in the hero — the gradient was too subtle, and the right side was empty on desktop. Fixed by:
- Bumping hero-radial primary alpha from `0.15` → `0.35` with a middle stop at `0.08`
- Converting the hero to flex layout with headline + CTAs on the left and a "The Platform" stats panel on the right (Curated Gen 0 Skills · 15, Bible Patterns · 37, Judging Layers · 5, Your Runs · N) + a "Browse Registry →" link. Hides on mobile so layout reflows cleanly.

**Round 4**: The compute estimates on `/new` were fantasy. First pass overestimated (~3.6 hrs / $47 for 5×3). Matt provided real data: "we did a full run in about 53 mins and cost ~$7.50". Recalibrated to `MIN_PER_COMPETITOR_RUN=0.95` and `USD_PER_COMPETITOR_RUN=$0.11`. Default 5×3 now shows ~54 min / ~$7.45 — matches observation within 1%.

**Round 5**: Fork mode showed "No seed selected — go to the Registry" as a dead-end. Matt: "can we load the registry here?" Inlined the 15-seed grid directly into the fork-mode body with category filter chips. Click any card → picks it, fills the spec, collapses into a summary. "Change" button to swap seeds without leaving the page.

---

### Artifacts Produced

| Artifact | Lines | Purpose |
|---|---|---|
| `skillforge/seeds/__init__.py` (new, subagent) | 1,452 | 15 production-ready Gen 0 Skills |
| `skillforge/db/seed_loader.py` (new) | 110 | Idempotent loader, hash-based skip |
| `skillforge/api/seeds.py` (new) | 35 | `GET /api/seeds` endpoint |
| `skillforge/api/uploads.py` (new) | 195 | `.md` + `.zip` upload w/ safety caps |
| `skillforge/agents/spawner.py` (append) | +120 | `spawn_from_parent()` function |
| `skillforge/engine/evolution.py` (edit) | +10 | `PENDING_PARENTS` + branch on gen 0 |
| `skillforge/api/routes.py` (edit) | +105 | `POST /api/evolve/from-parent` unified endpoint |
| `skillforge/main.py` (edit) | +8 | Mount 2 new routers + load_seeds() in lifespan |
| `skillforge/config.py` (edit) | +1 | `spec_assistant` role (carried over) |
| `design/anthropic-design-system.md` (new, subagents) | ~350 | Extracted palette + fonts + radii literal values |
| `frontend/tailwind.config.js` (rewrite) | 95 | CSS-var color tokens, Anthropic radii, Source Serif 4 |
| `frontend/src/index.css` (rewrite) | 110 | `:root` + `[data-theme=dark]` CSS vars, Google Fonts import |
| `frontend/index.html` (edit) | +17 | No-flash inline theme script |
| `frontend/src/hooks/useTheme.ts` (new) | 70 | Cookie-backed 3-state theme hook |
| `frontend/src/hooks/useCssVar.ts` (new) | 40 | Read CSS var live with MutationObserver |
| `frontend/src/components/ThemeToggle.tsx` (new) | 35 | ☀ 🖥 🌙 button group |
| `frontend/src/components/SeedDetailView.tsx` (new) | 155 | Full SKILL.md render w/ export sidebar |
| `frontend/src/components/SkillUploader.tsx` (new) | 170 | Drag-drop upload w/ validation UI |
| `frontend/src/components/AgentRegistry.tsx` (rewrite) | 280 | Two sections: Curated Library + Community Evolutions |
| `frontend/src/components/EvolutionDashboard.tsx` (rewrite) | 225 | Stats hero panel + seed fallback for empty state |
| `frontend/src/components/SpecializationInput.tsx` (rewrite) | 365 | 3-mode toggle, inline seed picker, real cost estimates |
| `frontend/src/components/EvolutionCard.tsx` (edit) | border | Hairline border, hover elevation |
| `frontend/src/components/StatCard.tsx` (edit) | border | Hairline border |
| `frontend/src/components/FitnessChart.tsx` (edit) | CSS vars | `useCssVar` for theme-aware charts |
| `frontend/src/components/FitnessRadar.tsx` (edit) | CSS vars | Same |
| `frontend/src/components/ModeCard.tsx` (edit) | ring | Replace hardcoded rgba with `ring-primary` |
| `frontend/src/components/AppShell.tsx` (edit) | sticky | Sticky nav + ThemeToggle mount |
| `frontend/src/App.tsx` (edit) | +1 route | `/runs/:runId/skills/:skillId` |
| `PLAN-V1.1.md` (rewrite then locked) | ~400 | v2 plan reflecting re-scope |
| `journal/005-v1-1-landing.md` (new, this entry) | — | — |

---

### Key Decisions Summary

| Decision | Rationale |
|---|---|
| Seeds as a synthetic `seed-library` EvolutionRun | Reuses every existing endpoint. Zero migrations. No special cases on the read path. |
| Hash-based seed reload on every boot | Safest default — reflects edits automatically, skips work when unchanged |
| Unified `/api/evolve/from-parent` endpoint | Seed-fork and upload-fork share the same backend code path. `PENDING_PARENTS` registry stashes the resolved SkillGenome keyed by run id |
| CSS variables over full Tailwind rewrite | Every `primary/20` class keeps working. Theme swap is a single `[data-theme]` attribute change. No app sweep needed |
| No-flash inline script in index.html | Cookie-based theme is readable pre-React. Prevents the white flash on hard reload that every client-side theme system has |
| `useCssVar` hook for Recharts | Charts need color strings, not CSS classes. `MutationObserver` on `[data-theme]` gives live values with no framework integration |
| Headless Chromium for anthropic.com extraction | WebFetch can only see raw HTML; anthropic.com hides everything behind CSS custom properties. Playwright in /tmp was the only way to get the real tokens |
| Product fonts over marketing fonts | claude.com (app) uses sans-body/serif-display; anthropic.com (marketing) uses serif-body/sans-display. SKLD.run is a product app, follows claude.com |
| Three subagents in parallel, not sequential | Research is embarrassingly parallel. No dependencies between Agent A (design), B (seeds), C (headless extraction) |
| Inline seed picker in fork mode | Fork mode with a dead-link to /registry was a dead end. Inline picker keeps the user on /new and cuts a full round-trip |
| Calibrate estimates from real observed data | "Default run completes in <15 min, <$10" was a design target, not reality. Matt's real numbers (53 min, $7.50 for 5×3×3) produced honest formulas |

---

### What's Next

Next session is a deploy + smoke-test session. All the code is in place; the seed loader runs on app startup via the FastAPI lifespan handler, so Railway's production DB will seed itself on first boot after the push.

Priority items for the next session:
- Commit this batch + push + verify Railway deploys cleanly
- Open the live URL in both light and dark mode, hit every page, verify no leftover dark-only hardcoded values
- Test the fork-from-registry flow end-to-end on prod with a real evolution run (not demo)
- Test the upload flow with a real SKILL.md file
- If the real live run reveals calibration gaps in the estimate formula, update the constants

Longer-term items on the v1.1 backlog still:
- **LineageExplorer** — visual lineage graph using the existing `/api/runs/{id}/lineage` endpoint
- **Spec assistant tests** — unit tests for `_extract_final_spec` edge cases
- **Seed library growth** — 15 is a good start; eventually 30-50 with community contributions
- **A way to publish evolved Skills back into the Registry** — right now only curated seeds live there. Future runs could opt-in to promotion

---

*"Three research agents, one main context, zero wasted tokens — the work that looks parallel in the final commit actually was parallel."*
