# SKLD.run

Evolve Claude Agent Skills through natural selection.

SKLD.run (formerly SkillForge) breeds populations of SKILL.md files, competes them against auto-generated challenges, scores them with a 6-layer judging pipeline, and exports the winner as an installable Skill directory. The internal Python package and GitHub repo retain the `skillforge` name for now — the rename is brand-only.

See [`SPEC.md`](./SPEC.md) for the full specification and [`CLAUDE.md`](./CLAUDE.md) for development guidance.

## Quickstart

```bash
uv sync
uv run uvicorn skillforge.main:app --reload
```

Then POST to `/evolve` with a specialization description. See `SPEC.md` §API Endpoints.

## Key directories

- `docs/` — technical reference (`skills-research.md`) and the golden template for gen 0 Skills
- `bible/` — the Claude Skills Bible: empirically-derived patterns and findings from evolution runs
- `skillforge/` — Python backend (FastAPI + Claude Agent SDK)
- `frontend/` — React + Vite dashboard
- `tests/` — unit + gated integration tests
