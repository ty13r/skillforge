# SkillForge — Project Journal

## Entry #10: Phase 1 Lands — Taxonomy + Agent Skills + Report Generator

**Date**: April 10, 2026
**Session Duration**: ~6 hours
**Participants**: Matt + Claude Code (Opus 4.6, 1M context)

---

### The Starting Point

Entry #9 closed with the v2.0 architectural vision locked: atomic variant
evolution, the six-agent roster (Taxonomist, Scientist, Spawner, Competitor,
Reviewer, Breeder, Engineer), the Domain → Focus → Language → Family → Variant
taxonomy, and a five-phase implementation plan in `plans/PLAN-V2.0.md`.

This session was Phase 1 — taxonomy + data model. No evolution changes yet;
just the scaffolding the rest of v2.0 depends on. Five waves to land:

1. Dataclasses + six agent skill packages
2. Database schema + additive migration
3. Taxonomy CRUD + bootstrap seed loader
4. Taxonomy REST API + frontend browser
5. Post-run report generator

---

### Phase 1: Dataclasses + the Six Skill Packages

Wave 1-1 was the biggest single commit of the session. Four new internal
dataclasses — `TaxonomyNode`, `SkillFamily`, `Variant`, `VariantEvolution` —
and two extensions to existing models: `SkillGenome.variant_id` and
`EvolutionRun.family_id` + `evolution_mode`. All with full `to_dict` /
`from_dict` round trip, backward-compatible loading from pre-v2.0 dicts.
Thirteen round-trip tests in `tests/test_models_v2.py` pinning the shape.

The bigger chunk was the six agent skill packages under `.claude/skills/`.
Each skill is a full golden-template package: `SKILL.md` with frontmatter +
workflow + 2-3 I/O examples, real Python scripts with `argparse` entry
points, real `validate.sh` bash scripts, substantive reference docs. Not
stubs — working code. The Reviewer's `code_metrics.py` is a real AST-based
analyzer that computes cyclomatic complexity, max function length, max
nesting depth, function count, import count. I dogfooded it on itself and
it returned `{cyclomatic_complexity: 27, function_count: 10, ...}`.

#### The Subagent Permission Block

I kicked off the skill packages via a single Opus subagent, thinking it
would be the fastest path. Matt flagged it — "can you generate them in
parallel instead of to one agent?" Switched to six parallel Opus subagents,
one per skill. Thirty seconds later the first one came back with:

> Both Write and Bash are denied. I cannot create any files or directories
> with the tools available.

The harness subagents don't have Write or Bash. The `general-purpose` type
nominally has `*` tools, but the permission mode inherited by subagents is
more restrictive than the main thread. All five other subagents were killed
right as they hit the same wall. I pivoted to a pattern I'll use again: the
subagent drafts content and returns it as delimited text, the main thread
extracts + unescapes + writes. Built a small helper
`/tmp/skillforge-write-drafts.py` that parses `===FILE:path===` blocks,
`html.unescape`s the content (HTML entities sneak in through the task
notification channel), and writes each file to disk with `chmod +x` on
anything under `scripts/`. Six new Opus subagents, all in parallel, all
returning delimited content blocks. 30 files written in two batches.

Every subagent except the first one flagged its own description as being
over the 250-char limit. I caught and tightened each one manually when I
wrote them to disk. The pattern note I'm saving: "subagents draft, main
thread writes" is the right shape for any future parallel-file-authoring
work in this harness.

---

### Phase 2: Database Schema + the Additive Migration

Wave 1-2 was four new tables — `taxonomy_nodes`, `skill_families`, `variants`,
`variant_evolutions` — plus nullable column additions to `evolution_runs`
(`family_id`, `evolution_mode`) and `skill_genomes` (`variant_id`). Nothing
exotic from a DDL perspective, but I wanted the migration to be truly
zero-touch: fresh installs get the columns from the CREATE TABLE statements,
upgrades from pre-v2.0 databases get them via `ALTER TABLE ADD COLUMN` —
same code path, same `init_db()` call, no user action required.

Built that as `_apply_additive_migrations()` inside `database.py`. It walks
a `(table, column, column_sql)` tuple list and runs a `PRAGMA table_info`
probe before each `ALTER` — so running init_db twice is a no-op and upgrading
from a pre-v2.0 schema drops the new columns in without touching the
existing row data. The regression test inserts a hand-built pre-v2.0 row
via `_PREV2_EVOLUTION_RUNS_DDL`, runs `init_db`, then asserts the old row
is still intact with `total_cost_usd=1.23` but the new `family_id`
(null) and `evolution_mode` (default "molecular") columns are present.
Seven more tests cover the structural invariants and the family → variants
cascade delete.

#### The NULL-parent UNIQUE Gotcha

I nearly shipped a latent bug here. The table-level
`UNIQUE (level, slug, parent_id)` constraint on `taxonomy_nodes` looks
correct until you remember SQLite treats `NULL != NULL` in UNIQUE — so two
`domain` rows with the same slug and null `parent_id` would both be
accepted. Added a partial unique index:

```sql
CREATE UNIQUE INDEX idx_taxonomy_nodes_root_unique
ON taxonomy_nodes (level, slug) WHERE parent_id IS NULL
```

Wrote the regression test for it — attempt a duplicate root insert, assert
an IntegrityError. The child-level uniqueness case is covered by the
table constraint and I wrote a regression test for that too.

---

### Phase 3: Taxonomy CRUD + the Bootstrap Loader

Wave 1-3 added 13 async CRUD functions to `queries.py` — save/get/list for
every v2.0 table, with filter composition on `list_families` and
`get_variants_for_family`. The interesting piece was `get_taxonomy_node_by_slug`:
because SQLite treats NULL parent_id as distinct, the function has two code
paths — `WHERE parent_id IS NULL` for root lookups and `WHERE parent_id = ?`
for child lookups. Clean fix, but it's a paper cut you wouldn't notice
until you tried to look up a root by natural key.

Then the real work: `skillforge/db/taxonomy_seeds.py`. The plan said to
"run a lightweight `_bootstrap_classify()` against each of the 16 seeds'
specialization strings" using an LLM at boot, with a hardcoded fallback
when no API key is present. I inverted that — made the hardcoded path the
primary and documented the LLM path as optional. Rationale: the existing
seeds already ship with a `category` field, so deriving a
`(domain, focus, language, family_slug, family_label)` tuple is a
deterministic lookup, not a classification problem. The LLM adds zero value
for the 15 seeds I've got; it would only matter when a new seed without a
category gets added.

The loader is fully additive — it walks each seed, looks up or creates
the domain/focus/language nodes by natural key, then looks up or creates
the family. Running it twice is a no-op. Adding a new seed between boots
auto-extends the taxonomy. Tested that explicitly: hand-delete one family
row after a full bootstrap, re-run the loader, assert exactly one family
was created and 14 were reused.

End-to-end via the lifespan handler in `main.py`: 35 nodes (7 domains ×
14 focuses × 14 languages scoped per focus) + 15 families created on first
boot, 0 created on every subsequent boot.

---

### Phase 4: REST API + Frontend Browser

Wave 1-4 was the first wave where backend and frontend landed in one
commit. Backend was straightforward — five read-only endpoints in
`skillforge/api/taxonomy.py`, three new Pydantic response schemas, router
registered in `main.py`. The taxonomy API uses `get_taxonomy_tree` +
in-Python filtering rather than pushing the filter into SQL because the
taxonomy is small by design (≤50 nodes) and Python filters are easier to
review.

The frontend piece was a new `/taxonomy` route with a two-column layout:
collapsible Domain → Focus → Language tree on the left with descendant-aware
per-node family counts, and a filtered families grid on the right. Click
any node to filter; click again to clear that level. I kept AgentRegistry's
existing category-based filters alone — it's already working well and the
taxonomy route provides the deeper drill-down without needing to refactor
an existing component.

#### The Vercel Plugin Injection Noise

Three times this session the harness's Vercel plugin injected "MANDATORY"
best-practice context for unrelated libraries — Next.js on `npm run build`,
react-best-practices on reading a `.tsx` file, vercel-functions on
reading a file under `api/`. This is a Vite + React SPA on a FastAPI
backend running on Railway. None of the Vercel guidance applied. I flagged
each injection in the response and proceeded without the skill invocation.

---

### Phase 5: The Post-Run Report Generator

Wave 1-5 closed out Phase 1. `skillforge/engine/report.py` assembles a
nine-section structured report: metadata, taxonomy, challenges, generations
(with per-gen fitness curve + delta from previous), variant_evolutions
(empty for molecular runs), assembly_report (empty for molecular runs),
bible_findings (stub for Wave 4+), learning_log, summary. Writes both a
JSON payload and a markdown sidecar to `data/reports/{run_id}.{json,md}`.

The 1MB size cap constraint was load-bearing: with 5 pop × 3 gen = 15
skills per run and each skill carrying a full SKILL.md, the naive report
could balloon past a megabyte. Added `SKILL_MD_PREVIEW_LINES = 30` with a
`"... (truncated)"` trailer and tested it explicitly — inflated a skill
with 500 lines × 100 chars each, asserted the serialized JSON still comes
in under the cap. Works.

Hooked into `evolution.py` right after the `evolution_complete` event as
a fire-and-forget `asyncio.create_task` wrapped in
`contextlib.suppress(Exception)`. Report failures never block the
pipeline. The `GET /api/runs/{run_id}/report` endpoint returns the JSON
or 404 if it hasn't been generated yet.

#### The ON CONFLICT Trap

One test bug that was instructive: `_make_genome()` in `test_report.py`
defaulted to `gid="s1"`, and `save_genome`'s `ON CONFLICT(id) DO UPDATE`
clause updates maturity/scores but does NOT update `run_id`. Test 1 saved
the skill with run_id=A, test 2 tried to save with run_id=B, and the
upsert preserved the original run_id=A — so when test 2 fetched its run,
the skill wasn't found (it was still tied to run_id=A in the DB). Fixed
by giving each test run a unique skill id via uuid. Worth noting for any
future tests that build multiple runs in one session.

---

### Artifacts Produced

| Artifact | Lines | Purpose |
|---|---|---|
| `skillforge/models/{taxonomy,family,variant}.py` | 220 | v2.0 dataclasses |
| `.claude/skills/{reviewer,scientist,breeder,engineer,taxonomist,spawner}/` | ~4200 | Six agent skill packages |
| `skillforge/db/database.py` | +150 | 4 new tables + additive migration |
| `SCHEMA.md` | +140 | v2.0 schema documentation |
| `skillforge/db/queries.py` | +320 | 13 taxonomy CRUD functions |
| `skillforge/db/taxonomy_seeds.py` | 290 | Hardcoded taxonomy bootstrap |
| `skillforge/api/taxonomy.py` | 135 | 5 REST endpoints |
| `skillforge/api/schemas.py` | +42 | 3 Pydantic response schemas |
| `frontend/src/components/TaxonomyBrowser.tsx` | 270 | /taxonomy route |
| `frontend/src/types/index.ts` | +55 | Taxonomy TypeScript types |
| `skillforge/engine/report.py` | 360 | Post-run report generator |
| `tests/test_models_v2.py` | 210 | 13 dataclass round-trip tests |
| `tests/test_db_v2.py` | 420 | 10 schema + migration tests |
| `tests/test_taxonomy_queries.py` | 490 | 13 taxonomy CRUD tests |
| `tests/test_taxonomy_api.py` | 160 | 11 REST endpoint tests |
| `tests/test_report.py` | 340 | 8 report generator tests |

---

### Key Decisions Summary

| Decision | Rationale |
|---|---|
| Subagents draft content, main thread writes | Harness subagents don't have Write/Bash. Built a delimited-format helper that unescapes HTML entities. |
| Hardcoded taxonomy bootstrap as the primary path | The 15 Gen 0 seeds already have a `category` field. LLM adds zero value for this case; defer the LLM path to Phase 2's Taxonomist agent. |
| Additive column migration inside `init_db()` | Upgrades from pre-v2.0 databases become zero-touch. Fresh installs skip the ALTER because the CREATE TABLE already has the columns. |
| Partial unique index for root taxonomy rows | SQLite treats `NULL != NULL` in UNIQUE; root domain rows with the same slug would slip through the table constraint. |
| `winner_variant_id` as a soft reference | Circular FK between variants.evolution_id and variant_evolutions.winner_variant_id is painful in SQLite. Enforce the forward FK, validate the reverse at the query layer. |
| Skill md preview capped at 30 lines in reports | Keeps the JSON serialization under 1MB even with inflated skill content. Full content is still available via the existing `/runs/{id}/skills/{id}` endpoint. |
| Fire-and-forget report generation | Report failures never block the evolution pipeline. Wrapped in `contextlib.suppress`; a missing report returns 404 from the API endpoint. |
| Branch `v2.0/phase1-taxonomy` for waves 1-3 onwards | Wave 1-1 and 1-2 landed directly on main (before Matt's PR-first decision). Wave 1-3 onward lives on the branch; Phase 1 will PR as one unit when all five waves are on the branch. |

---

### What's Next

Phase 1 is complete: 55 v2.0 backend tests pass (13 models + 10 db + 13
queries + 11 api + 8 report), ruff clean across all v2.0 files, frontend
build green. The branch `v2.0/phase1-taxonomy` holds waves 1-3, 1-4, 1-5
pending a single PR against main. Matt still needs to eyeball the
TaxonomyBrowser UI in a browser before merging — that's the manual QA
step the plan gates each phase on.

Phase 2 builds the Taxonomist agent proper — a Sonnet structured-output
call that takes a specialization string, the existing taxonomy tree, and
the list of existing families, and returns a classification +
decomposition recommendation. This replaces the hardcoded bootstrap at
runtime for real user submissions. The agent skill I already wrote in
Wave 1-1 (`.claude/skills/taxonomist/`) becomes the knowledge the agent
consults when it's loaded by an Agent SDK competitor.

After Phase 2 comes Phase 3 — the variant evolution orchestrator — which
is where the atomic evolution work actually happens. Everything Phase 1
built (taxonomy, families, variants, reports) exists to support Phase 3.

---

*"Five waves, one branch, one PR. The scaffolding is in. Now the fun part."*
