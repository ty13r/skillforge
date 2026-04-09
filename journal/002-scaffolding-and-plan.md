# SkillForge — Project Journal

## Entry #2: Scaffolding, Planning, and the Shape of the Build

**Date**: April 9, 2026
**Session Duration**: ~2.5 hours
**Participants**: Matt + Claude Code (Opus 4.6, 1M context)

---

### The Starting Point

Entry #1 ended with Matt taking the kickoff prompt into Claude Code for the first implementation session. This entry picks up from that moment. The goal for this session: get from "spec in a repo" to "fully scaffolded project with an end-to-end implementation plan and a workflow that doesn't burn Opus tokens on mechanical work."

---

### Phase 1: Reorganization and Foundational Reading

The repo arrived with a flat file structure — `skillforge-spec.md`, `skills-research.md`, `golden-template.md`, `descriptions.md`, `instructions.md`, `README.md` — all at root. The kickoff prompt referenced a very different layout (`docs/`, `bible/`, `SPEC.md`), so the first real task was reorganizing.

I flagged the mismatch, Matt confirmed the reorg, and the files found their proper homes:
- `skillforge-spec.md` → `SPEC.md`
- `skills-research.md` → `docs/skills-research.md`
- `golden-template.md` → `docs/golden-template.md`
- `README.md` (which turned out to be the bible methodology doc) → `bible/README.md`
- `descriptions.md` + `instructions.md` → `bible/patterns/`

Then I read everything. 518 lines of deep research on Skills. 116 lines of golden template. The entire 1046-line spec. Both bible pattern files. The spec is dense — six-layer judging pipeline, trait attribution, reflective mutation, multi-parent crossover, Pareto fronts, a learning log that accumulates across every generation, and a "Skills Bible" that grows as an emergent public artifact from every evolution run.

The insight that stuck: **this isn't "evolve a prompt." It's "build a feedback loop that discovers what makes Agent Skills work, at the trait level, and writes down what it learns."** The feedback loop is the product.

---

### Phase 2: Clarifying Questions Before Writing Code

Before touching any files, I surfaced twelve open questions that the spec left underdetermined. Matt's answers shaped everything downstream:

1. **Permission mode** — the spec's competitor example used `bypassPermissions`, but the research report flagged it as "the bypassPermissions trap" (`allowed_tools` doesn't constrain it). I pushed for `dontAsk`. Matt approved.
2. **`allowed-tools` in frontmatter** — the SDK ignores it, but Claude Code honors it. Keep it for export portability. Matt: "keep it."
3. **Model selection** — Sonnet for MVP but with optionality. This became `config.model_for(role)` with per-role env overrides.
4. **Python tooling** — my call. `uv` for deps, Python 3.12+, flat package layout.
5. **Challenge Designer WebSearch** — Matt: "yes enable it." Behind a feature flag for offline tests.
6. **Multi-language verification in L1 judging** — dispatch on `Challenge.verification_method`, Python-native as the only concrete implementation for MVP.
7. **L2 trigger accuracy implementation** — the naive version spawns an Agent SDK query per eval query (~150 extra calls per generation). The cheap version batches into one Anthropic Messages API call per Skill. Matt: "your call" → batched.
8. **Spawner reads the bible** — my call. Concatenates `bible/patterns/*.md` into the Spawner's system prompt. Degrades gracefully when empty.
9. **Live-SDK tests** — gated behind `SKILLFORGE_LIVE_TESTS=1` so CI stays hermetic.
10. **Frontend v1.1 components** — empty stubs, not full implementations.
11. **Package layout** — my call. Flat `skillforge/skillforge/`, no `src/`.
12. **Missing files the spec references** — `docs/golden-template/` (the actual template directory, not just the explainer), `docs/eval-queries-template.json`, `bible/` seeded pattern files. Matt: "yes create them."

Every answer got logged to `CLAUDE.md` Decisions Log with a date and rationale. That log is already at 13 entries and climbing.

---

### Phase 3: CLAUDE.md — The Source of Truth for "How We Work"

Step 1 of the kickoff prompt was creating `CLAUDE.md`. It isn't a README — it's a control document that tells any future Claude Code session (or human contributor) how to work in this repo:

- The architectural summary (6-layer judging, reflective mutation, Pareto fronts)
- All the skill authoring constraints the Spawner and Breeder must enforce
- The Agent SDK gotchas (`setting_sources=["project"]`, never `bypassPermissions`, `allowed-tools` is SDK-ignored)
- Code style rules (dataclasses internal, Pydantic only at API boundary, async throughout)
- A Progress Tracker with the full MVP checklist
- A Decisions Log

The Progress Tracker pattern turned out to be critical. Every future session opens `CLAUDE.md`, sees what's done and what's next, and picks up without me having to reconstruct state. It's the closest thing to durable project memory we have.

---

### Phase 4: The Big Scaffold (Step 2)

Matt asked the right question before I started writing: "Want to drop into plan mode first?" Yes — 50 files in one go deserves review.

I wrote a plan to `~/.claude/plans/stateless-honking-ocean.md` covering every file the scaffold would create, grouped by area: root config, `docs/golden-template/`, bible seeds, `skillforge/` Python package, tests, and a Vite/React/Tailwind frontend skeleton. Out of scope was any business logic — stubs only, `raise NotImplementedError` in every body, docstrings that describe what the function will do. The point was to **freeze the import graph early** so later steps don't thrash on file moves.

Matt approved. I exited plan mode and scaffolded 50+ files in one continuous pass.

A few non-obvious calls:
- `config.py` got real content immediately (not a stub) because every later step needs `model_for(role)` and the constants.
- `main.py` got real content immediately so the FastAPI app would actually boot.
- The `SkillGenome` dataclass matched SPEC.md §Data Model exactly — all six fitness layers with correct defaults.
- `engine/sandbox.py::validate_skill_structure` had its full constraint list documented in the docstring even though the body was `raise NotImplementedError`. This becomes the shared validator in Step 5 and Step 6b.

Scaffold verified: `python3 -c "from skillforge import config; from skillforge.models import SkillGenome; ..."` resolved cleanly on system Python 3.9 (stdlib-only paths), confirming the basics were sound even before `uv sync`.

---

### Phase 5: Python Environment Bootstrap

Step 3 required actually installing dependencies. System Python was 3.9 (we target 3.12+), and `uv` wasn't installed. Matt confirmed Python 3.13 was fine (Homebrew had it) and green-lit `brew install uv`.

`brew install uv` → 48.6 MB → `uv sync --extra dev` → full dependency tree resolved clean. The import graph check came back green: `main, config, models, db, engine, agents, api` all resolved, FastAPI app title printed correctly, 2 stub tests passed, 1 live-SDK test correctly skipped.

This was the first moment the project felt real. `uv run uvicorn skillforge.main:app` would now actually start a server.

---

### Phase 6: The Full Implementation Plan

With scaffolding verified, Matt asked the question that shaped the rest of the session: "Is the full plan fleshed out and documented?"

**Honest answer: no.** `SPEC.md` had the architecture. `CLAUDE.md` had conventions and the MVP checklist. The kickoff prompt had 11 steps, but one paragraph each. The Step 2 plan file only covered Step 2. There was no single document covering Steps 3–11 at file-by-file granularity.

So I wrote `PLAN.md` — 413 lines when it landed, covering every remaining step with:
- File-by-file scope
- Function signatures to implement
- Test cases to write
- Verification commands
- Dependencies between steps
- A cross-cutting contracts section (9 rules that every step must honor — no hardcoded model strings, always `dontAsk`, always validate genomes, always mock the SDK in tests)

Then Matt asked about the schema and the Breeder scaling, and `PLAN.md` grew:

**SCHEMA.md** — Matt asked what DB we were using and whether the schema should live in its own file. Yes to both. The spec already mandated SQLite via `aiosqlite` (no external deps, single file, works on Railway). I extracted the five-table schema into `SCHEMA.md` with columns, types, nullability, indexes, foreign-key relationships, and trace-size concerns. Step 4 in `PLAN.md` now references `SCHEMA.md` instead of inlining DDL.

**Breeder scaling** — my original plan hardcoded the slot allocation for `population_size=5`. Matt asked what the issue was. I caught it: at `population_size=10`, the Breeder would produce 5 children and the population would shrink every generation. The fix was a formula: `elitism = max(1, pop//5*2)`, `wildcards = max(1, pop//10)`, remainder split between diagnostic and crossover. Worked examples at pop=3, 5, and 10 all sum correctly. Added as cross-cutting contract #11.

---

### Phase 7: The Wave Plan — Cost-Aware Development

Then Matt asked the question that changed the shape of the build entirely: "Can you review the plan and look for opportunities where we can run DEVELOPMENT agents in parallel and also use Sonnet agents instead of Opus to reduce my subscription spend?"

This was the moment the project went from "Opus builds everything sequentially" to "Opus orchestrates, Sonnet executes."

I built a dependency graph of Steps 3–11 and identified the biggest parallelization wins:
- **Wave 1**: Step 3 (models) solo — foundational, everything imports from it.
- **Wave 2**: Steps 4 (DB) + 5 (sandbox) + 10 frontend scaffold in parallel (3 Sonnet agents). They share no files.
- **Wave 3**: Steps 6a-c + 6d L1-L5 in parallel (8 Sonnet agents). The judging layers are genuinely independent — each one is a self-contained algorithm operating on the same `CompetitionResult` shape. Eight-way parallel work that would take 8× serial time if I did it alone.
- **Wave 4**: Opus — the 6d pipeline wire-up and the 6e Breeder. Integration glue and judgment-heavy reflective reasoning. Not delegable.
- **Wave 5**: Opus — Step 7 evolution engine. Phased implementation, highest bug cost. Not delegable.
- **Wave 6**: Steps 8 + 9 + 10 finish in parallel (3 Sonnet agents).
- **Wave 7**: Step 11 Docker/Railway (1 Sonnet agent).

**Ownership table**: 11 of 14 work units (~80%) go to Sonnet subagents. Opus retains the 3 hardest integration points. Opus reviews every Sonnet diff, runs the test suite, wires things together, updates the Progress Tracker. Sonnet never ships unreviewed.

I also identified four cost-saver switches for later:
1. **Haiku 4.5 for classification-style judging** (`l2_trigger`, `judge_comparative`) — already a one-line env override via `model_for(role)`.
2. **Batched L4 ranking** instead of `C(n,2)` pairwise — the single most expensive judging step.
3. **Consolidated Breeder calls** — merge learning log + breeding report into one call.
4. **Compressed traces in DB** — `competition_results.trace` is the largest blob we store.

Matt said: "lets make sure we stay flexible with development so if we need to utilize some of these cost saving strategies it's easy to switch to." So the flags landed in `config.py` immediately — `L4_STRATEGY`, `BREEDER_CALL_MODE`, `COMPRESS_TRACES` — with sensible MVP defaults but env-var flippable. The point isn't to pre-optimize, it's to **shape the code so the cost savers are a one-line env change later, not a refactor.**

Verified: flipping `SKILLFORGE_MODEL_L2_TRIGGER=claude-haiku-4-5-20251001` swaps the model immediately. No code change needed.

---

### Phase 8: QA, Woven Through

Matt: "I want you to make sure you're QAing all of your work as we progress can you make sure that's documented at each step of the PLAN as well as the agent orchestration."

This is the kind of instruction I want to hear early, not late. QA tacked on at the end catches nothing. QA woven into the orchestration loop catches contract drift between Sonnet subagents **while the context is still fresh**.

I added a QA checklist with 16 checks split across three levels:

- **Per-step (1-8)**: import graph clean, full test suite green, ruff clean, no hardcoded models, no `bypassPermissions`, contract audit, Progress Tracker updated, Decisions Log updated if needed.
- **Per-wave (9-12)**: FastAPI boot check, integration test, fresh DB creation, no orphaned files.
- **Per-subagent (13-16)**: diff review (reject scope creep), subagent report cross-check, contract honor check, test coverage check.

Then I added a per-step "QA focus" paragraph to each major step calling out the specific risks. Step 7 (evolution engine) got the longest treatment because it's the highest-risk integration point in the whole project.

The post-wave orchestration loop is now explicitly gated: **"I do not start wave N+1 until wave N's QA passes. No exceptions."**

---

### Phase 9: UI Design and the Journal

Matt's last two asks before kicking off:

**UI design.** I don't have one. The spec lists components and their purposes but no visual design — no layout, no palette, no component states, no empty/error states. I told Matt honestly: without a design, Step 10 becomes guesswork, and we'd ship something functional but generic. He said he'd design it. I created `design/` with a `README.md` explaining what goes there, when it's needed (Wave 6, not blocking earlier waves), and a minimum acceptance bar: dashboard wireframe, competitor card states, color/typography direction, empty/error states.

**The journal.** Matt asked me to continue the journal Claude Desktop started. Entry #1 was the spec session — three hours of idea exploration, pivots, research, and spec-drafting. This entry (Entry #2) is the scaffolding-and-plan session — the moment the project went from "document" to "code that will compile" plus a full implementation strategy that honors Matt's subscription budget. The journal is the story of how we built this, alongside the spec, the plan, the schema, and the code.

I also updated `CLAUDE.md` with instructions for maintaining the journal — format, cadence, voice — so every future session knows to continue the story.

---

### Artifacts Produced This Session

| Artifact | Lines | Purpose |
|---|---|---|
| `CLAUDE.md` | ~180 | Control document: architecture summary, conventions, Progress Tracker, Decisions Log, journaling instructions |
| `PLAN.md` | ~600 | File-by-file implementation plan for Steps 3-11, wave plan, QA checklist, flexibility hooks |
| `SCHEMA.md` | ~165 | SQLite schema source of truth — 5 tables, columns, indexes, FKs, trace-size concerns |
| `pyproject.toml` + 80 stub files | — | Full project scaffold: Python package, tests, Vite/React/Tailwind frontend, Docker, Railway config |
| `docs/golden-template/SKILL.md` + `scripts/validate.sh` | ~60 | Actual template the Spawner copies and mutates |
| `docs/eval-queries-template.json` | ~15 | Trigger accuracy eval query template |
| `bible/patterns/{structural,scripts,progressive-disclosure}.md` | ~150 | Three more seeded pattern files (in addition to descriptions + instructions from Entry #1) |
| `bible/evolution-log.md` | ~10 | Empty log awaiting first run |
| `design/README.md` | ~70 | Design directory landing pad with minimum acceptance bar |
| `journal/002-scaffolding-and-plan.md` | (this file) | Session documentation |
| Strategy flags in `config.py` | ~15 | `L4_STRATEGY`, `BREEDER_CALL_MODE`, `COMPRESS_TRACES` flags for cost-saver compatibility |

---

### Key Decisions Summary

| Decision | Rationale |
|---|---|
| Wave-based development with Sonnet subagents for ~80% of remaining work | Reduce subscription spend; most work is mechanical pattern-following |
| Opus retains 6d pipeline, 6e Breeder, Step 7 engine | Integration points with highest bug cost deserve the best reasoning |
| `PLAN.md` at project root (not `~/.claude/plans/`) | Version-controlled, visible to contributors, survives harness resets |
| `SCHEMA.md` as source of truth for DB | Schema changes update SCHEMA.md first, then code — prevents drift |
| Breeder slot allocation scales as a function of `target_pop_size` | Supports `population_size` ≠ 5 without shrinking populations |
| Cost-saver flags live in `config.py` as env-var-flippable switches | Keeps code shape compatible with future cost savers; no refactor needed to enable |
| Keep `parent_ids` as JSON column rather than normalized lineage table | Lineage queries are infrequent; JSON is simpler and can normalize later |
| QA checklist woven into every step and the orchestration loop (16 checks, 3 levels) | Catches contract drift between Sonnet subagents while context is still fresh |
| Gated orchestration: no wave N+1 until wave N QA passes | Prevents broken state from accumulating across waves |
| `design/` empty until Matt fills it; not blocking until Wave 6 | Parallel design work; backend unblocks first |
| `uv` + Python 3.13 via Homebrew | `requires-python = ">=3.12"` accepts 3.13; `uv` is fast and native-pyproject |
| `permission_mode="dontAsk"` everywhere, never `bypassPermissions` | Research flags the latter as a trap — `allowed_tools` doesn't constrain it |
| Keep `allowed-tools` in SKILL.md frontmatter despite SDK ignoring it | Exported Skills must work in Claude Code where it's honored |

---

### What's Next

Wave 1: Step 3 (models serialization + round-trip tests) delegated to one Sonnet subagent. Self-contained prompt references `PLAN.md §Step 3`, lists the files to modify, the test cases to write, and `uv run pytest tests/test_models.py -v` as the verification command. I review the diff, run the QA checklist, update the Progress Tracker, and move to Wave 2.

Wave 2 runs three Sonnet subagents in parallel: DB layer (Step 4), sandbox + validator (Step 5), and frontend component scaffold (Step 10 prep). They share no files so they can run concurrently.

By the end of Wave 3 we'll have a fully implemented backend minus the engine wire-up. Wave 4 (me) hooks everything together through the judging pipeline and the Breeder. Wave 5 (me) builds the evolution loop. Then Wave 6 finishes API, export, and frontend in parallel. Wave 7 ships to Railway.

If the wave plan holds, the MVP lands with significantly less Opus token spend than the sequential path — and the Sonnet subagents get a clean, well-specified job each with hard QA gates. The risk is contract drift across parallel agents, which is exactly what the QA checklist exists to catch.

---

*"Opus orchestrates. Sonnet executes. QA gates every handoff. The plan is the contract."*
