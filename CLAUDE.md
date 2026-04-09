# SkillForge

## What is this?
An evolutionary breeding platform for Claude Agent Skills. Two modes:
- **Domain mode**: Users define a specialization, we evolve a population of
  SKILL.md files through tournament selection, export the winner.
- **Meta mode**: Evolves universal Skill-authoring patterns that make any
  Skill better. Tests generalization across multiple random domains. (v1.1)

## Tech
- Python 3.12+, FastAPI, Claude Agent SDK, SQLite (aiosqlite), WebSockets
- Dependency management: `uv`
- React + Vite + Tailwind frontend
- Deploy target: Railway (Docker)

## Architecture
Multi-agent orchestration with insights from GEPA, Artemis, and Imbue.

Agent roles:
1. Challenge Designer — generates evaluation tasks from the specialization (WebSearch enabled)
2. Spawner — creates diverse initial Skill populations (gen 0) or breeds next gen
3. Competitor — Agent SDK `query()` with candidate Skill loaded via `setting_sources=["project"]`
4. Judging Pipeline (6 layers):
   - L1: Deterministic (compile, tests, lint, perf — no LLM, dispatch on `verification_method`)
   - L2: Trigger Accuracy (batched single-call precision/recall on frontmatter description)
   - L3: Trace-Based Behavioral Analysis (did Skill load? instructions followed?)
   - L4: Comparative + Pareto Selection (pairwise ranking, multi-objective front)
   - L5: Trait Attribution (instruction → fitness mapping with diagnostics)
   - L6: Consistency (repeated runs, variance check — v1.1)
5. Breeder — reflective mutation (reads traces, not just scores), multi-parent
   crossover, joint component mutation, persistent learning log, publishes to `bible/findings/`

Core loop: `skillforge/engine/evolution.py`

## Key Reference Documents
- `docs/skills-research.md` — the definitive technical reference for Claude Agent Skills. READ FIRST.
- `docs/golden-template.md` — canonical gen 0 structure. Spawner uses this as its seed.
- `docs/golden-template/` — actual template files the Spawner copies and mutates.
- `bible/` — the Claude Skills Bible. Breeder publishes findings after each generation.
  Spawner reads `bible/patterns/*.md` at spawn time to incorporate proven patterns.

## Key Techniques (from prior art)
- Reflective mutation via execution traces, not random (GEPA's ASI concept)
- Pareto-efficient selection across multiple objectives (GEPA)
- Joint optimization of interdependent Skill components (Artemis)
- Learning log accumulates lessons, prevents rediscovering failures (Imbue)
- Trigger accuracy as first-class fitness dimension (Anthropic skill-creator)
- Trace-based behavioral verification (MLflow)
- Maturity lifecycle: draft → tested → hardened → crystallized (singularity-claude)

## Key Patterns
- Each competitor runs in an isolated temp directory with Skill in `.claude/skills/evolved-skill/`
- Agent SDK loads the Skill via `setting_sources=["project"]` — **this is required, #1 gotcha**
- `permission_mode="dontAsk"` + explicit `allowed_tools` — **never `bypassPermissions`** (trap)
- `allowed-tools` in SKILL.md frontmatter is ignored by SDK but kept for Claude Code portability of exports
- All agent communication goes through the Evolution Engine (no direct agent-to-agent)
- WebSocket streams every event to the frontend in real-time
- Skills are versioned as full directory snapshots with lineage tracking
- Learning log is a persistent `list[str]` on `EvolutionRun`, injected into every Breeder prompt
- Pareto front maintained per generation — multiple "best" Skills can coexist

## Model Selection
All agent models centralized in `skillforge/config.py` as a dict keyed by role.
MVP default: `claude-sonnet-4-6` for every role. Any role can be upgraded to Opus
later via env var override without touching call sites.

## Skill Authoring Constraints (non-negotiable, enforced by Spawner + Breeder)
Derived from `docs/skills-research.md`:

**Description (Level 1 — routing):**
- Front-load capability + triggers within **250 characters**
- "Pushy" pattern: list adjacent concepts + "even if they don't explicitly ask for..."
- Explicit exclusions: "NOT for X, Y, or Z"
- Two-part: what it does + "Use when..."
- Evolves on a **separate track** from the instruction body

**Instructions (Level 2 — execution):**
- SKILL.md body under **500 lines**
- Numbered steps for workflows, bullets for options, prose for context
- **2-3 diverse I/O examples mandatory** (empirically 72% → 90% quality)
- H2/H3 headers as structural markers

**Resources (Level 3):**
- Scripts for deterministic ops (zero context cost)
- References one level deep from SKILL.md
- All paths use `${CLAUDE_SKILL_DIR}`
- **Validate all reference paths in CI** (73% of audited community skills had broken refs)

**Structural:**
- Name regex: `^[a-z0-9]+(-[a-z0-9]+)*$`, matches directory name exactly

## Constraints
- Competitors: max 15 turns per challenge
- `max_budget_usd` caps total API spend per evolution run
- Default domain run (5 pop × 3 gen × 3 challenges) completes in <15 min, <$10
- SQLite only — no external DB dependencies
- Live-SDK integration tests gated behind `SKILLFORGE_LIVE_TESTS=1`

## Git Policy
- The repo is version-controlled and remotely hosted at **https://github.com/ty13r/skillforge** (public).
- Commits happen **per wave** during implementation (one commit per completed wave from `PLAN.md §Development Workflow`).
- Commit messages follow conventional-commit style: `wave(N): <summary>`. E.g., `wave(1): implement SkillGenome serialization + tests`.
- **Push after each wave commit**: `git push origin main`. Matt authorized this on 2026-04-09 so Railway can auto-deploy from the main branch.
- Never force-push. Never run destructive git ops (`reset --hard`, `branch -D`, `checkout .`) without explicit approval.
- Each wave commit must ship with all QA checks passing (see PLAN.md §QA Checklist).
- Baseline commit (before Wave 1) captures the scaffolded state as the starting point.
- **Git identity**: no global git identity is set on this machine. Per-commit identity is passed inline via `git -c user.email="matt@skillforge.local" -c user.name="Matt (via Claude Code)" commit ...`. This honors the "never update git config" rule — nothing persists. Matt can rewrite author history later if he wants his real identity.

## Live SDK Test Budget
- Matt has authorized up to **$5 of Anthropic API spend** for live SDK integration tests during overnight runs.
- The live test at Wave 5 QA gate (2 pop × 1 gen × 1 challenge) costs ~$1-3.
- If a live test would exceed the budget, skip it and log `[BLOCKED: budget]` in the Progress Tracker.
- The `ANTHROPIC_API_KEY` is loaded from `.env` at project root (gitignored) via `config.py`.

## Autonomous-Run Scope
When running autonomously (overnight work, no active user):
- **Allowed**: spawn Sonnet subagents freely, run `uv`/`npm`/`pytest`/`ruff`/`uvicorn`, modify files under `/Users/mjdecour/apps/skillforge/`, create/delete temp dirs under `/tmp/skillforge-*`, start/stop local servers on port 8000 (must kill any started process).
- **Not allowed**: touch files outside the project root (except `/tmp/skillforge-*`), modify `~/.claude/` or system state, `brew install` new packages, push to remotes, run destructive git ops, spend API money beyond the authorized budget.
- **On hard block**: document in Progress Tracker with `[BLOCKED: reason]` marker, write a journal entry explaining what was tried, skip to any independent work, stop cleanly if no independent work remains.

## Code Style
- Type hints everywhere. Dataclasses for internal models, Pydantic only at API boundary.
- Async throughout — evolution engine is fully async.
- No classes where functions suffice.
- Short functions, clear names, minimal comments.
- Prefer composition over inheritance.

## Testing
- Unit tests mock the Agent SDK.
- Each judging layer tested independently.
- Skill directory structure validation.
- Export formats produce valid, installable SKILL.md directories.
- WebSocket event ordering.
- Pairwise comparison produces stable rankings.
- End-to-end live evolution test gated behind `SKILLFORGE_LIVE_TESTS=1`.

---

## Journaling

`journal/` documents the story of how we're building this app. It's a running narrative of sessions, decisions, pivots, surprises, and lessons learned — the human context around the code and plans. Entry #1 (`001-project-kickoff.md`) was written by Claude Desktop and covers the spec-drafting session before Claude Code was involved. Every subsequent entry is written by the Claude Code session that did the work.

### When to write a journal entry

- **At the end of every significant working session** — a "session" is whatever chunk of work naturally closes with a meaningful milestone (a wave completed, a major problem solved, a pivot in approach).
- **After any pivot or strategic shift** — if the plan changes, document why.
- **When a surprising bug or insight emerges** — the journal is the right home for "we learned X the hard way" stories that don't fit in code comments.
- **Not for trivial updates** — routine "implemented function Y, tests pass" work goes in the Progress Tracker + commit messages, not the journal.

### Format

Each entry is a numbered markdown file in `journal/`: `NNN-short-slug.md`. Zero-padded to 3 digits. Slug is kebab-case.

Examples:
- `001-project-kickoff.md`
- `002-scaffolding-and-plan.md`
- `003-wave-1-models.md`
- `015-first-live-run.md`

### Content structure

Every entry follows the template established by Entry #1:

```markdown
# SkillForge — Project Journal

## Entry #N: {Short Title}

**Date**: {Month DD, YYYY}
**Session Duration**: ~{hours}
**Participants**: {Matt + which Claude}

---

### The Starting Point
{1-2 paragraphs: where we were when this session started, what came before}

---

### Phase 1: {Thematic phase name}
{Narrative — what we explored, what decisions we made, what changed, in Matt's + Claude's voices when dialogue matters}

### Phase 2: {...}
...

---

### Artifacts Produced
| Artifact | Lines | Purpose |
|---|---|---|
| ... | ... | ... |

---

### Key Decisions Summary
| Decision | Rationale |
|---|---|
| ... | ... |

---

### What's Next
{1-2 paragraphs: what the next session should pick up, what's unblocked, what's still waiting}

---

*"{a punchy one-liner that captures the session's theme}"*
```

### Voice and style

- **Narrative, not log.** Tell the story. Capture the *why*, not just the *what*. Quote Matt's actual words when they shaped a decision.
- **Honest about uncertainty.** If a decision was a judgment call with real tradeoffs, name the alternatives.
- **Document surprises.** If something didn't work the way I expected, write that down.
- **Match Entry #1's voice.** Declarative, specific, confident-but-humble. Avoid hype. Avoid filler.
- **Cite artifacts by relative path.** `PLAN.md §Step 4`, not "the plan document."
- **Preserve the timeline.** Phases are chronological, not topical. Matt asks → Claude proposes → Matt decides → Claude executes.

### Relationship to other docs

- **`CLAUDE.md` Progress Tracker**: mechanical state (what's done, what's next). Updated every time a step lands.
- **`CLAUDE.md` Decisions Log**: one-liner + rationale for each decision. Updated in the moment.
- **`PLAN.md`**: file-by-file execution plan. Source of truth for "what to build."
- **`SPEC.md`**: the product and architecture. Source of truth for "why we're building this."
- **`SCHEMA.md`**: the database schema. Source of truth for "how data is stored."
- **`journal/`**: the story. Source of truth for "how we got here and what we learned along the way."

The journal is the only doc that's written for humans first and machines second. It's what a new contributor (or a future version of me reconstituting context) reads to understand the project's reasoning, not just its shape.

---

## Progress Tracker

### Current Phase: Setup
### Completed:
- [x] 2026-04-08 — Repo reorganized: `SPEC.md`, `docs/`, `bible/` layout
- [x] 2026-04-08 — Read all foundational docs (skills-research, golden-template, bible, spec)
- [x] 2026-04-08 — `CLAUDE.md` created with Progress Tracker
- [x] 2026-04-08 — Step 2: Full project scaffolded (~50 files: pyproject, docs/golden-template, bible seeds, skillforge/ package stubs, tests/, frontend/)
- [x] 2026-04-09 — `uv` installed; `uv sync --extra dev` green; full import graph verified
- [x] 2026-04-09 — `PLAN.md` written (Steps 3-11, file-by-file, cross-cutting contracts, wave plan, QA checklist, flexibility hooks)
- [x] 2026-04-09 — `SCHEMA.md` written (SQLite schema source of truth)
- [x] 2026-04-09 — Cost-saver strategy flags live in `config.py` (`L4_STRATEGY`, `BREEDER_CALL_MODE`, `COMPRESS_TRACES`)
- [x] 2026-04-09 — `design/` directory created with README; awaiting Matt's wireframes
- [x] 2026-04-09 — Journal Entry #2 written (`journal/002-scaffolding-and-plan.md`); journaling instructions added to CLAUDE.md
- [x] 2026-04-09 — Baseline git commit `e016d80`; git identity policy committed `87eacaa`
- [x] 2026-04-09 — Journal Entry #3 (`003-overnight-run-begins.md`) + ANTHROPIC_API_KEY loader verified
- [x] 2026-04-09 — **Wave 1 / Step 3 complete**: models serialization (`to_dict`/`from_dict` on all 5 dataclasses, `_serde.py` helper, datetime UTC fix). 10 tests pass (up from 2). Ruff clean (+ fixed pre-existing StrEnum issues in schemas.py)
- [x] 2026-04-09 — **Wave 2 / Steps 4 + 5 complete**: async SQLite DB (init_db + 8 CRUD functions, 10 tests) + sandbox system (create/cleanup/collect + 8-rule validator, 20 tests). Schema matches SCHEMA.md exactly. Foreign keys on, path-prefix safety verified, validator enforces all Skill Authoring Constraints. 40 tests passing total.
- [x] 2026-04-09 — Design review + `design/DIGEST.md` written. "The Precision Architect" — 8 screens covering dashboard, new evolution form, generation in progress, breeding phase, complete results, export, bible (v1.1), registry (v1.1). Committed `6a17463`.
- [x] 2026-04-09 — **Wave 3 / Steps 6a-c + 6d L1-L5 complete**: 8 Sonnet subagents ran in parallel. Challenge Designer, Spawner (with bible patterns + validator integration), Competitor (with setting_sources=["project"] + dontAsk), and 5 judging layers (L1 deterministic subprocess, L2 batched trigger accuracy, L3 trace-based behavioral analysis, L4 pairwise+batched_rank Pareto computation, L5 novel trait attribution). 121 tests passing (up from 40). Ruff clean. All contracts honored. L4_STRATEGY dispatch verified. Every agent uses model_for(role), never hardcoded.
- [x] 2026-04-09 — GitHub: pushed to **https://github.com/ty13r/skillforge** (public). Remote tracking configured. push-after-each-wave policy enabled for Railway auto-deploy.
- [x] 2026-04-09 — **Wave 4 / Step 6d pipeline + Step 6e Breeder complete** (Opus direct): judging pipeline orchestrates L1→L5 and aggregates per-skill fitness + generation-level best/avg/Pareto front. Breeder implements compute_slots() scaling formula (verified at pop=3,5,10,20), reflective crossover, diagnostic mutation, elitism with maturity promotion, wildcard spawning, LLM-driven lesson extraction (separate or consolidated mode per BREEDER_CALL_MODE flag), and bible finding publication with auto-incrementing filenames. 147 tests passing (up from 121).
- [x] 2026-04-09 — **Wave 5 / Step 7 evolution engine complete** (Opus direct): full async run_evolution loop with phased implementation — design challenges → spawn/breed → competitor sandbox runs → judging pipeline → breeder → repeat. Per-run event queue (engine/events.py) decouples engine from WebSocket transport. Budget tracking estimates cost from trace length + judge call count, aborts cleanly on overrun. DB persistence after each generation, non-fatal on failure. 155 tests passing. Also fixed Wave 2 schema gap: added max_budget_usd + failure_reason fields to EvolutionRun dataclass + serialization + DB queries.
- [x] 2026-04-09 — **Wave 6 partial: Steps 8 + 9 complete** (Sonnet subagents): REST API (POST /evolve creates background task, GET /runs, /runs/{id}, /runs/{id}/export with 3 formats, /runs/{id}/lineage), WebSocket handler (60s heartbeat timeout, terminal event detection, clean disconnect), Export engine (export_skill_md, export_agent_sdk_config, export_skill_zip with mandatory validate_skill_structure check before packaging, META.md sidecar). 184 tests passing (up from 155). Manual API smoke test: GET / returns 200, POST /evolve creates real run with UUID + ws_url, GET /runs lists persisted run.
- [x] 2026-04-09 — **Wave 6c (frontend) complete via Opus fallback**: 3 Sonnet subagent retries failed with API 529; switched to Opus direct implementation. Built 17 React components: AppShell, Sidebar, EvolutionDashboard, EvolutionCard, StatCard, PrimaryButton, StatusGlow, SpecializationInput, ModeCard, ParameterInput, EvolutionArena, CompetitorCard, JudgingPipelinePill, LiveFeedLog, FitnessChart (recharts LineChart), FitnessRadar (recharts RadarChart), BreedingReport, EvolutionResults, SkillExportPreview. react-router-dom 7.14 routing with 6 routes. useEvolutionSocket hook with reducer-style state, auto-reconnect once. Tailwind theme extended with the full Precision Architect token system. `npm run build` clean: 858 modules, 0 TS errors. End-to-end smoke test: SPA renders at /, /assets serve, /api/health returns JSON. Updated test_root_health_check to hit /api/health (was hitting / which now serves the SPA).
- [x] 2026-04-09 — **Wave 7 / Step 11 in progress**: Dockerfile rewritten — multi-stage Vite frontend build + Python 3.12 slim runtime, copies `pyproject.toml + uv.lock + README.md` (the previous version was missing README which broke hatchling on Railway), uses `uv sync --frozen --no-dev` for reproducible installs, honors $PORT via `sh -c` expansion. railway.toml cleaned: removed redundant startCommand (Dockerfile CMD wins), added healthcheckPath=/api/health and 100s timeout. Confirmed Railway service exists (id 856a125c, latest deployment FAILED with `Readme file does not exist: README.md` error — the bug my new Dockerfile fixes). Pushing should auto-trigger a successful redeploy.
- [x] 2026-04-09 — Verified two Railway tokens loaded: RAILWAY_TOKEN (project, deploy-only) + RAILWAY_API_TOKEN (account, full CLI access). `railway whoami` returns ty13r authenticated. Used Railway plugin's use-railway skill conventions for status / logs / service queries.
- [x] 2026-04-09 — **🎉 FIRST REAL LIVE EVOLUTION PASSED** (`c3c22eb`). `test_minimal_evolution_live` passes in 9:03 for 2 pop × 1 gen × 1 challenge against the real Anthropic API. Fixed four bugs: (1) `/runs` 500 crash on deploy because init_db() wasn't called at startup — fixed via FastAPI lifespan handler in `99445fa`; (2) Spawner + Challenge Designer hung because they used `claude_agent_sdk.query()` for pure JSON generation (query() is for agentic loops with tools; the SDK started a session, emitted SystemMessages, then waited indefinitely for tool-use) — fixed by refactoring both to use `AsyncAnthropic` directly like the Breeder and L2-L5 already did; (3) `run_evolution` not self-contained for tests — now calls `init_db()` at the top (idempotent); (4) Anthropic API server disconnected at 3:35 on the Spawner's ~15KB prompt — fixed by switching Spawner to streaming via `client.messages.stream()`. 13 agent tests rewritten with a new `_generate(prompt) -> str` mock seam (simpler than mocking SDK messages). 184 unit tests passing + 1 live test passing. Railway auto-rebuilt with the fixes.
- [x] 2026-04-09 — **Post-MVP polish pass (evening)**: Fixed Vite proxy / SPA route collision by namespacing REST API under `/api/*`. Migrated `tests/test_api.py` + all frontend fetches. Vite proxy simplified to `/api` + `/ws`.
- [x] 2026-04-09 — **Demo mode (public)**: `POST /api/debug/fake-run` pushes scripted events into the in-process queue — no AI calls. Public "▶ Watch Live Demo" button on dashboard. DEMO chip on arena header. Graceful empty state for SKILL.md preview on fake runs. Scripted narrative rewritten as a realistic pandas data-cleaning evolution (4 real challenges, 3 breeding reports citing bible patterns, climbing fitness 0.52 → 0.91).
- [x] 2026-04-09 — **Bible + Registry shipped** (v1.1 stubs → real): `GET /api/bible/entries` reads `bible/patterns/` + `bible/findings/` + `bible/anti-patterns/` from disk. `BibleBrowser.tsx` — two-column markdown browser via `react-markdown` with `.bible-prose` styles. `AgentRegistry.tsx` — grid of completed runs w/ search, mode filter, sort, featured card.
- [x] 2026-04-09 — **Bible content seeded from research report** (Sonnet subagent): 5 pattern files rewritten from 194 → 439 lines. 37 confirmed patterns + 15 anti-patterns extracted from `docs/skills-research.md` with P-DESC/P-INST/P-STRUCT/P-SCRIPT/P-DISC codes, Finding/Evidence/How-to-apply/Example structure, verbatim metrics (250-char cap, 500-line ceiling, 72%→90%, 73% broken-refs).
- [x] 2026-04-09 — **AI Spec Assistant shipped** (v1.1): `POST /api/spec-assistant/chat` — stateless chat that signals completion via fenced JSON `{"final_spec": "..."}`. Canned seed turn (no API call) for instant first response. `SpecAssistantChat.tsx` — collapsible inline panel on `/new` with message history, typing indicator, auto-fills textarea on completion. New `spec_assistant` role in `MODEL_DEFAULTS`.
- [x] 2026-04-09 — **SkillDiffViewer shipped** (v1.1): new `GET /api/runs/{run_id}/skills/{skill_id}` endpoint. `SkillDiffViewer.tsx` at `/runs/:runId/diff` — sidebar lists lineage edges color-coded by mutation type, main panel shows mutation rationale + line-by-line diff via `diff` npm package.
- [x] 2026-04-09 — **Journal Entry #4** written (`journal/004-post-mvp-polish-and-v1-1-push.md`) covering all 5 phases of the polish pass.
- [x] 2026-04-09 — **PLAN-V1.1.md locked** after Matt's approval on 7 recs: §3 palette first, unified `/api/evolve/from-parent`, hash-based seed reload, immutable seeds, both `.md` + `.zip` uploads, fonts swap included, three-state theme toggle. Three research subagents run in parallel: Anthropic design extraction (2 rounds — WebFetch + headless Chromium), 15 Gen 0 Skills curation (Opus subagent, 1,452 lines, all validated against bible patterns).
- [x] 2026-04-09 — **§3 Anthropic Design System shipped**: CSS-variable token system with real extracted values from headless-Chromium dump of anthropic.com (clay `#d97757`, ivory-light `#faf9f5`, slate-dark `#141413`, cloud ramp, full `--swatch--*` palette, `--radius--main 0.5rem`). Fonts swapped to Inter + Source Serif 4 + JetBrains Mono (free substitutes for paid Anthropic Sans/Serif/Mono). `tailwind.config.js` remapped to `rgb(var(--color-xxx) / <alpha-value>)` so every existing alpha-channel class keeps working. Recharts components rewired via new `useCssVar` hook to auto-theme on toggle.
- [x] 2026-04-09 — **§4 Theme Toggle shipped**: `useTheme` hook with `skld-theme` cookie (3-state: light/dark/system), 1-year expiry, live reaction to `prefers-color-scheme` changes. `ThemeToggle.tsx` — 3-button group (☀ / 🖥 / 🌙) in AppShell nav. No-flash inline script in `index.html` reads cookie + sets `[data-theme]` before React boots — prevents the theme flicker on hard reload.
- [x] 2026-04-09 — **§1 Curated Seed Library shipped**: 15 production-ready Gen 0 Skills loaded into DB as synthetic `seed-library` EvolutionRun via idempotent `seed_loader.py` (hash-based skip on boot, runs via FastAPI lifespan handler). `GET /api/seeds` endpoint for frontend metadata. Registry rewritten with two sections: "✦ Curated Library · Gen 0 Skills" (category filter chips + View/⑂ Fork actions per card) and "Community Evolutions" below. New `SeedDetailView.tsx` at `/runs/:runId/skills/:skillId` renders full SKILL.md via `react-markdown` with export buttons in sidebar. Dashboard empty state shows 6 featured seed cards as fallback.
- [x] 2026-04-09 — **§2 Upload Existing Skill shipped**: `POST /api/uploads/skill` accepts `.md` + `.zip` with 1 MB/5 MB caps, 100-file limit, 20:1 compression ratio protection, path traversal rejection, extension allowlist. Validates via existing `validate_skill_structure()`. Unified `POST /api/evolve/from-parent` endpoint resolves `{parent_source: "registry" | "upload", parent_id}` against either source, stashes parent in `PENDING_PARENTS` in-memory registry. New `spawner.spawn_from_parent()` — elite carry + LLM-generated mutations. `SkillUploader.tsx` drag-drop with inline validation. `SpecializationInput` gets 3-mode toggle (From Scratch / Upload Existing / Fork from Registry) with inline seed picker grid in fork mode.
- [x] 2026-04-09 — **Dashboard polish**: separated `--color-surface-low` from page bg, added hairline borders to every card, filtered seed-library from Dashboard list, fixed `text-secondary` → `text-primary` on hero accent (secondary = slate-dark in Anthropic mapping), darkened hero radial gradient alpha 0.15 → 0.35, flex layout with right-side "The Platform" stats panel (Curated Skills · 15, Bible Patterns · 37, Judging Layers · 5, Your Runs · N). Sticky nav with stronger backdrop.
- [x] 2026-04-09 — **Real cost estimates on `/new`**: calibrated against observed live runs (5×3×3 = 53 min/$7.50, 2×1×1 = 9 min/$2). Formula: `competitor_runs × 0.95 min + 5 + gens × 2 overhead`; `competitor_runs × $0.11 + $1 + gens × $0.50`. Shows competitor run count + red warning banner when estimate exceeds budget cap.
- [x] 2026-04-09 — **Arena specificity overhaul**: header now leads with the specialization text (not "Evolution Cycle" generic). New "Test Gauntlet" panel shows all 3 designed challenges with difficulty chips, full prompts, and live `●` indicator when a competitor is actively solving. CompetitorCard enriched to show which challenge it's solving. JudgingPipelinePill replaced with descriptive per-layer cards explaining exactly what L1-L5 are scoring in plain English. Spawn/breed empty state shows contextual message ("Spawning 4 diverse candidates from the golden template…" vs "Breeding next-gen from Pareto front").
- [x] 2026-04-09 — **SCHEMA.md updated**: added `seed-library` to reserved run ids in the Conventions section. No table/column changes — seeds flow through existing `evolution_runs` + `skill_genomes` + `generations` tables. Uploads are in-memory only.
- [x] 2026-04-09 — **Journal Entry #5** written (`journal/005-v1-1-landing.md`) covering the full v1.1 landing across 6 phases: research in parallel, plan lock, palette + theme toggle, seeds in registry, upload flow, polish passes.

### MVP Checklist:
- [ ] `docs/skills-research.md` included in repo
- [ ] `docs/golden-template.md` + template directory for gen 0 seeding
- [ ] `bible/` directory structure initialized with README
- [ ] Spawner uses golden template as structural seed for all gen 0 Skills
- [ ] Spawner enforces authoring constraints (250-char descriptions, 500-line body, 2-3 examples)
- [ ] Description and instruction body evolve on separate tracks
- [ ] POST /evolve starts a run (domain mode)
- [ ] Challenge Designer generates 3 challenges from specialization
- [ ] Spawner creates 5 diverse initial Skills (gen 0)
- [ ] Competitors solve challenges via Agent SDK with Skill loaded
- [ ] L1 judging: deterministic checks (compile, tests, lint, reference validation)
- [ ] L2 judging: trigger accuracy (precision/recall on description)
- [ ] L3 judging: trace-based analysis (did Skill load, which instructions followed)
- [ ] L4 judging: pairwise comparative ranking
- [ ] L5 judging: trait attribution with diagnostics
- [ ] Breeder with reflective mutation (reads traces + learning log)
- [ ] Learning log accumulates across generations
- [ ] Breeder publishes generalizable findings to `bible/findings/`
- [ ] 3 generations complete end-to-end
- [ ] Export best Skill as downloadable zip (SKILL.md + supporting files)
- [ ] Export as Agent SDK config JSON
- [ ] WebSocket streams progress events (including per-layer judging events)
- [ ] Basic React dashboard with real-time tournament view
- [ ] Fitness-over-generations chart
- [ ] Deploy to Railway via Docker
- [ ] `max_budget_usd` cost cap

### Decisions Log:
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-08 | Reorganized repo into `docs/` + `bible/` + `SPEC.md` layout | Match paths referenced throughout the spec and kickoff prompt |
| 2026-04-08 | `uv` for Python dep management | Fast, modern, native `pyproject.toml` support |
| 2026-04-08 | Flat package layout (`skillforge/skillforge/`, no `src/`) | Matches file tree in SPEC.md §File Structure |
| 2026-04-08 | `permission_mode="dontAsk"` everywhere, never `bypassPermissions` | Research report flags `bypassPermissions` as a trap — `allowed_tools` doesn't constrain it |
| 2026-04-08 | Keep `allowed-tools` in SKILL.md frontmatter despite SDK ignoring it | Exported Skills must work in Claude Code, where it's honored |
| 2026-04-08 | All agents use `claude-sonnet-4-6` for MVP, centralized in `config.py` as a role→model dict | Cost control; optionality to upgrade individual roles to Opus later via env override |
| 2026-04-08 | L1 dispatches on `Challenge.verification_method`; Python-native implementation only for MVP, generic subprocess fallback for other languages | Supports the multi-language ambition without blocking MVP on language breadth |
| 2026-04-08 | L2 trigger accuracy via single batched Claude API call per Skill (not per-query SDK invocations) | ~150 SDK calls → 5 API calls per generation; faithful enough for MVP |
| 2026-04-08 | Challenge Designer has WebSearch tool enabled, gated by env flag for offline tests | Spec calls for real-world example grounding; tests stay hermetic |
| 2026-04-08 | Live-SDK integration tests gated behind `SKILLFORGE_LIVE_TESTS=1` | Prevents accidental API spend in CI |
| 2026-04-08 | Spawner reads `bible/patterns/*.md` at spawn time and concatenates into system prompt | Simple, works with any number of pattern files, degrades gracefully when empty |
| 2026-04-08 | Frontend v1.1 components (SkillDiffViewer, LineageExplorer, AgentRegistry) scaffolded as empty stubs | File tree matches spec; no implementation cost for MVP |
| 2026-04-09 | `PLAN.md` at project root is source of truth for Steps 3–11; `~/.claude/plans/` is ephemeral | Version-controlled, visible to any contributor, survives harness resets |
| 2026-04-09 | `SCHEMA.md` at project root is source of truth for the SQLite schema | Schema changes update SCHEMA.md first, then code — prevents drift |
| 2026-04-09 | Breeder slot allocation (elitism/wildcard/diagnostic/crossover) scales as a function of `target_pop_size`, not hardcoded | Supports `population_size` ≠ 5 without shrinking populations |
| 2026-04-09 | Keep `parent_ids` as JSON column on `skill_genomes` rather than a normalized `lineage_edges` table | Lineage queries are infrequent; can normalize later without migration pain |
| 2026-04-09 | Installed `uv` via Homebrew; `uv sync --extra dev` succeeds on Python 3.13 | Decision 2 confirmed — uv + Python 3.13 works cleanly |
| 2026-04-09 | Wave-based development workflow: Sonnet subagents for ~80% of remaining work, Opus only for integration points (6d pipeline, 6e Breeder, Step 7 engine) | Reduce subscription spend; most work is mechanical pattern-following |
| 2026-04-09 | Cost-saver strategy flags added to `config.py` (`L4_STRATEGY`, `BREEDER_CALL_MODE`, `COMPRESS_TRACES`) | Keep the code shape compatible with future cost savers; flip via env var, no refactor |
| 2026-04-09 | L2 and L4 judging layers model-selected via `model_for(role)` with no hardcoded strings | Makes Haiku-for-classification a one-line env change |
| 2026-04-09 | Pushed to public GitHub repo `ty13r/skillforge` and enabled push-after-each-wave policy | Matt is setting up Railway to auto-deploy from main branch |
| 2026-04-09 | Railway CLI installed; `RAILWAY_TOKEN` in `.env` is a Project Token (deploy-only, can't `whoami`/`list`); Railway hooked to GitHub repo for auto-deploy on push | Wave 7 will use `railway up` as fallback if needed; main deploy path is GitHub push → Railway watching |
| 2026-04-09 | Formal QA checklist added to PLAN.md: per-step (1-8), per-wave (9-12), per-subagent (13-16); gated between waves | Prevents contract drift across Sonnet subagents; catches integration issues early when they're cheap to fix |
| 2026-04-09 | `design/` directory created with README and minimum acceptance bar; Matt designing, not blocking until Wave 6 | Backend unblocks first; Step 10 frontend implementation reads `design/` as source of truth |
| 2026-04-09 | Journaling workflow documented in `CLAUDE.md`; entries in `journal/NNN-slug.md` format matching Entry #1 | Preserves the story of how we built this for future contributors and session continuity |
