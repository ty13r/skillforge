# SKLD — Skill Kinetics through Layered Darwinism

## What is this?
An evolutionary breeding platform for Claude Agent Skills. Decomposes skills into focused, independently-evolvable **atomic variants**, evolves each under targeted selection pressure, then assembles the best variants into a composite skill.

**Full overview**: `docs/how-skld-works.md`

## Current Status
- **v1.x** (shipped): Monolithic skill evolution — works end-to-end, deployed on Railway
- **v2.0** (active development): Atomic variant evolution — `plans/PLAN-V2.0.md` is the active plan, start at **Wave 1-1**

## Tech
- Python 3.12+, FastAPI, Claude Agent SDK, SQLite (aiosqlite), WebSockets
- Dependency management: `uv`
- React + Vite + Tailwind frontend
- Deploy target: Railway (Docker)

## Architecture

### Taxonomy
```
Domain → Focus → Language → Skill (family) → Variant (atomic unit)
```

### Agent Roster (v2.0)
| Agent | Role |
|-------|------|
| **Taxonomist** | Classifies domains, decomposes into variant dimensions, recommends reuse. Checks existing taxonomy before creating new entries. |
| **Scientist** | Designs focused experiments (challenges) per variant dimension with machine-readable evaluation rubrics. |
| **Spawner** | Creates initial variant populations (narrower scope per dimension). |
| **Competitor** | Runs a variant against a focused challenge via Agent SDK. |
| **Reviewer** | Evaluates variant fitness — L1 (deterministic + code quality metrics), L3 (trace), L4 (comparative), L5 (trait attribution). Owns the metrics catalog. |
| **Breeder** | Refines variants over generations through selective mutation. Works within a single dimension (horizontal). |
| **Engineer** | Assembles winning variants into composite skill. Foundation skeleton + trait merge. Runs integration test + refinement (vertical). |

### Two-Tier Variant Model
- **Foundation variants**: structural decisions (fixture strategy, project conventions). Evolved first.
- **Capability variants**: focused modules (mock strategy, assertion patterns). Evolved in context of winning foundation.

### Evolution Modes
- **Molecular** (v1.x): evolve entire SKILL.md as monolith. 5 pop × 3 gen × 3 challenges = 45 runs.
- **Atomic** (v2.0): decompose → evolve per dimension (2 pop × 2 gen × 1 challenge each) → assemble. ~16 runs + assembly.
- **Auto**: Taxonomist decides based on skill complexity. Simple skills → molecular. Complex skills → atomic.

### Agent Skills (Recursive Self-Improvement)
Each pipeline agent has its own Claude Agent Skill in `.claude/skills/`. The platform can evolve these skills using itself — a recursive self-improvement loop.

Core loop: `skillforge/engine/evolution.py` (molecular) + `skillforge/engine/variant_evolution.py` (atomic, v2.0)

## Key Reference Documents
- `docs/how-skld-works.md` — **start here**: full system overview for first-time readers.
- `plans/SPEC-V2.0.md` — v2.0 architecture spec (taxonomy, agents, variants, evaluation, data model).
- `plans/PLAN-V2.0.md` — v2.0 implementation plan (5 phases, 15 waves, file-by-file).
- `docs/skills-research.md` — the definitive technical reference for Claude Agent Skills.
- `docs/golden-template.md` — canonical gen 0 structure. Spawner uses this as its seed.
- `docs/golden-template/` — actual template files the Spawner copies and mutates.
- `bible/` — the Claude Skills Bible. Breeder publishes findings after each generation.
- `SCHEMA.md` — database schema source of truth.

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

## Gen 0 Seed Quality Standard (non-negotiable for new seeds)

Every Gen 0 seed skill MUST be a full golden-template package, not just a SKILL.md blob.

**Minimum required files (4):**
- `SKILL.md` — frontmatter + body per golden template (Quick Start, When to use, Workflow with `${CLAUDE_SKILL_DIR}` paths, 2-3 Examples, Common mistakes)
- `scripts/validate.sh` — real bash validation (exit 0/1 with diagnostic output, not a stub)
- `scripts/main_helper.py` — real Python logic (parser, formatter, validator, generator — does actual deterministic work)
- `references/guide.md` — domain reference document Claude reads on demand

**Domain-specific files (required where applicable):**
- `test_fixtures/` — sample input files for the domain (e.g., `Dockerfile.example`, `sample.html`, source files to test against). Immutable across variants.
- `assets/` — templates, configs, static resources (e.g., `.tf` templates, `.yml` workflow templates, `.sql` migration templates)
- `references/` — additional reference docs beyond `guide.md` (e.g., `checklist.md`, `patterns.md`, `cheatsheet.md`, `test-patterns.md`)

**Quality bar:**
- Scripts must be functional — `python scripts/main_helper.py` and `bash scripts/validate.sh` should run without error on appropriate input
- Reference docs must be substantive (50-200 lines of real content, not placeholders)
- Test fixtures must contain realistic domain-specific content with known issues/patterns to work with
- Every `${CLAUDE_SKILL_DIR}/` path referenced in SKILL.md must resolve to an actual file in `supporting_files`
- File diversity: skills should NOT all have the same 4 files — add domain-appropriate extras

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
- The live test at Wave 5 QA gate (2 pop × 1 gen × 1 challenge) costs ~$1-3 on Sonnet.
- If a live test would exceed the budget, skip it and log `[BLOCKED: budget]` in the Progress Tracker.
- The `ANTHROPIC_API_KEY` is loaded from `.env` at project root (gitignored) via `config.py`.

### Test Tiers (`SKILLFORGE_TEST_TIER`)
Cost-tiered live testing via `tests/conftest.py::_apply_test_tier`. Reads `SKILLFORGE_TEST_TIER` at conftest import time and injects `SKILLFORGE_MODEL_<ROLE>` env vars so `model_for()` resolves to the chosen tier for every agent role.

- **unset / `sonnet`**: every role on `claude-sonnet-4-6`. Full-quality, most expensive. Use for pre-release validation.
- **`cheap`** / **`haiku`**: every role on `claude-haiku-4-5-20251001`. ~1/3 the cost per the pricing table in `skillforge/config.py`. Best for fast dev iteration — contract/schema/state-machine bugs surface identically, and Haiku's stricter JSON tends to *increase* test sensitivity to regressions.
- **`mixed`**: Haiku for structured-output agents (Taxonomist, Scientist, Spawner, Engineer, judges); Sonnet for reasoning-heavy agents (Breeder, Competitor). Middle-ground cost.

Explicit per-role overrides (`SKILLFORGE_MODEL_ENGINEER=...`) always win — the tier helper only fills in roles the caller didn't pin. Bogus tier names raise `ValueError` at conftest import time.

Example invocations:
- Cheap Haiku run: `SKILLFORGE_TEST_TIER=cheap SKILLFORGE_LIVE_TESTS=1 uv run pytest tests/test_atomic_evolution_live.py`
- Mixed run: `SKILLFORGE_TEST_TIER=mixed SKILLFORGE_LIVE_TESTS=1 uv run pytest tests/test_atomic_evolution_live.py`
- Cheap + pin Engineer to Sonnet: `SKILLFORGE_TEST_TIER=cheap SKILLFORGE_MODEL_ENGINEER=claude-sonnet-4-6 SKILLFORGE_LIVE_TESTS=1 uv run pytest tests/test_atomic_evolution_live.py`

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
# SKLD — Project Journal

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

## Plans & Progress

All planning and progress documents live in `plans/`:
- **`plans/PLAN-V2.0.md`** — **active plan**: Atomic variant evolution. 5 phases, 15 waves. Start at Wave 1-1.
- **`plans/SPEC-V2.0.md`** — finalized spec: taxonomy, agent roster, variant architecture, evaluation strategy, data model.
- `plans/BACKLOG.md` — carried-over items from v1.2 + research paper framework + SKLD rebrand.
- `plans/PROGRESS.md` — completed work log, MVP checklist, decisions log.
- `plans/PLAN-V1.2.md` — v1.2 plan (Managed Agents port). Shipped via PR #1.
- `plans/archived/PLAN.md` — original MVP plan (Steps 3-11). Shipped.
- `plans/archived/PLAN-V1.1.md` — v1.1 plan (seeds, uploads, palette, theme). Shipped.

### Task Execution Workflow (REQUIRED)

Every time you complete a task, follow this loop:
1. **Read** the relevant plan in `plans/` before starting work.
2. **Execute** the task per the plan's contracts and QA checklist.
3. **Document** completion by appending a dated entry to `plans/PROGRESS.md`
   under `### Completed:`, checking off any MVP checklist items, and adding a
   row to the Decisions Log if a non-trivial decision was made.

Do not batch completions — update `plans/PROGRESS.md` immediately after each
task lands so the tracker never drifts from reality.

