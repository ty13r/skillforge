# SkillForge — Project Journal

## Entry #3: The Overnight Run Begins

**Date**: April 9, 2026
**Session Duration**: (overnight, in progress)
**Participants**: Matt (asleep) + Claude Code (Opus 4.6, 1M context) orchestrating Sonnet subagents

---

### The Starting Point

Entry #2 ended with everything staged for an autonomous overnight run: `PLAN.md` with file-level scope for Steps 3-11, `SCHEMA.md` for the DB, the wave plan with Sonnet/Opus split, QA checklist at three levels, flexibility hooks in `config.py`, and journaling instructions in `CLAUDE.md`. The baseline git commit captured the scaffolded state as `e016d80`.

Matt's final instructions before bed: yes commit per wave, yes authorize up to $5 of live SDK spend at the Wave 5 QA gate, yes to default scope and default block behavior, designs coming later. "Continue for now."

This entry documents the handoff and will be updated across the run as waves complete. Each wave also gets its own commit.

---

### Phase 1: Handoff Checklist

Before kicking off Wave 1, I verified everything the overnight run needs:

- **`ANTHROPIC_API_KEY` loaded**: Matt dropped the key into `.env` at project root. `config.py` auto-loads it via the hand-rolled loader I added (zero new deps, reads `ROOT_DIR/.env`, respects existing env vars as precedence). Verified: `key loaded: True, starts with: sk-ant-api..., length: 108`. The key never gets logged, committed, or exposed in any subagent prompt.
- **Git repo initialized**: `git init -b main` then baseline commit `e016d80` captured the scaffolded state. Second commit `87eacaa` documented the inline git identity policy (`-c user.email/name` per-commit since no global identity is set on the machine).
- **Commit policy**: one commit per wave, conventional-commit style (`wave(N): <summary>`), never push, never force-push, never destructive ops.
- **QA gates**: 16 checks across per-step (1-8), per-wave (9-12), per-subagent (13-16) levels. Wave N+1 does not start until Wave N passes QA.
- **Block behavior**: hard blocks get documented in Progress Tracker with `[BLOCKED: reason]`, journal entry explains what was tried, skip to independent work, stop cleanly if nothing independent remains.
- **Scope**: free to spawn Sonnet subagents, run `uv`/`npm`/`pytest`/`ruff`/`uvicorn`, modify anything under `/Users/mjdecour/apps/skillforge/`, create/delete temp dirs under `/tmp/skillforge-*`. Not allowed to touch anything else, `brew install`, push, spend API money beyond $5.
- **`design/`**: empty. Matt is working on designs and will drop them later. Step 10 frontend implementation is blocked on designs; everything else is unblocked.
- **Baseline state**: 2 tests passing, 1 skipped (live-gated), import graph clean, `uv sync` green.

All clear for liftoff.

---

### Phase 2: Kicking Off Wave 1

Wave 1 is Step 3 — implement `to_dict`/`from_dict` serialization helpers on all five dataclasses (`SkillGenome`, `Challenge`, `Generation`, `EvolutionRun`, `CompetitionResult`) plus expanded tests in `tests/test_models.py` verifying round-trip equality, default factory independence, and datetime handling.

Delegated to one Sonnet subagent via the Agent tool with a self-contained prompt referencing `PLAN.md §Step 3` and the cross-cutting contracts. Opus reviews the diff, runs the full QA checklist, and commits on success.

*(This entry continues as waves land. Each wave appends a Phase section with what happened, what shipped, and what surprised me.)*

---

*(Sections below will be filled in as the overnight run progresses.)*
