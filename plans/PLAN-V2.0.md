# PLAN v2.0 — Atomic Variant Evolution

**Source of truth**: `plans/SPEC-V2.0.md`  
**Phases**: 5 phases, 15 waves. Each wave = one commit.  
**Estimated total**: ~3-4 sessions  

---

## Development Workflow

Same as v1.x: wave-based commits, tests passing after each wave, push after each wave.

### QA Checklist (per wave)
1. `uv run pytest tests/ -x -q` — all passing
2. `cd frontend && npx tsc --noEmit` — clean
3. `uv run ruff check skillforge/ tests/` — clean
4. New code has type hints
5. `plans/PROGRESS.md` updated with dated completion entry
6. `SCHEMA.md` updated if any DB changes in this wave
7. `CLAUDE.md` updated if architecture context changed

### QA Gate (per phase)
After each phase completes, before starting the next:
1. End-to-end integration test verifying the phase's milestone
2. Manual browser QA of any frontend changes
3. Journal entry documenting the phase's work

### Parallelization Strategy
Within each wave, backend and frontend work are independent when possible. Across waves, the following can run in parallel (non-overlapping files):
- Wave 1-1: agent skills (6 packages, subagent) ‖ dataclasses (main thread)
- Wave 1-4: backend API ‖ frontend components
- Wave 3-2 ‖ Wave 3-3: Scientist + Spawner updates touch different files
- Phase 5 frontend can start once Phase 4 API endpoints exist (before Phase 4 is fully polished)

---

## Phase 1: Taxonomy + Data Model

**Goal**: Build the hierarchy, classify existing seeds, browsable registry. No evolution changes.

### Wave 1-1: Dataclasses + Agent Skills

**Create:**
- `skillforge/models/taxonomy.py` — `TaxonomyNode` dataclass
  - Fields: id, level, slug, label, parent_id, description, created_at
  - `to_dict()` / `from_dict()` following existing `_serde.py` patterns
- `skillforge/models/family.py` — `SkillFamily` dataclass
  - Fields: id, slug, label, domain_id, focus_id, language_id, tags (list[str]), specialization, decomposition_strategy, created_at, best_assembly_id
- `skillforge/models/variant.py` — `Variant` + `VariantEvolution` dataclasses
  - Variant: id, family_id, dimension, tier, genome_id, fitness_score, is_active, evolution_id, created_at
  - VariantEvolution: id, family_id, dimension, tier, parent_run_id, population_size, num_generations, status, winner_variant_id, foundation_genome_id, challenge_id, created_at, completed_at
- `.claude/skills/taxonomist/` — full golden-template skill package
  - SKILL.md, scripts/classify.py, scripts/validate.sh, references/taxonomy-guide.md
- `.claude/skills/scientist/` — full golden-template skill package
- `.claude/skills/spawner/` — full golden-template skill package
- `.claude/skills/breeder/` — full golden-template skill package
- `.claude/skills/reviewer/` — full golden-template skill package
- `.claude/skills/engineer/` — full golden-template skill package
- `tests/test_models_v2.py` — serialization round-trips for all new dataclasses

**Modify:**
- `skillforge/models/__init__.py` — export TaxonomyNode, SkillFamily, Variant, VariantEvolution
- `skillforge/models/genome.py` — add `variant_id: str | None = None`, update to_dict/from_dict
- `skillforge/models/run.py` — add `family_id: str | None = None`, `evolution_mode: str = "molecular"`, update to_dict/from_dict

### Wave 1-2: Database Schema

**Modify:**
- `skillforge/db/database.py` — add DDL for 4 new tables (taxonomy_nodes, skill_families, variants, variant_evolutions). Add migration in `init_db()`: use `PRAGMA table_info()` to check existing tables, `ALTER TABLE ADD COLUMN` for evolution_runs.family_id, evolution_runs.evolution_mode, skill_genomes.variant_id. Add indexes.
- `SCHEMA.md` — document all new tables and modified columns

**Create:**
- `tests/test_db_v2.py` — init_db creates new tables, migration adds columns without data loss, roundtrip insert/select

### Wave 1-3: Taxonomy CRUD + Seed Data

**Modify:**
- `skillforge/db/queries.py` — add functions:
  - `save_taxonomy_node()`, `get_taxonomy_tree()`, `get_taxonomy_node()`
  - `save_skill_family()`, `get_family()`, `list_families()`
  - `save_variant()`, `get_variants_for_family()`, `get_active_variants()`
  - `save_variant_evolution()`, `get_variant_evolution()`

**Create:**
- `skillforge/db/taxonomy_seeds.py` — idempotent loader (same pattern as seed_loader.py)
  - On first boot (empty taxonomy): run a lightweight `_bootstrap_classify()` against each of the 16 seeds' specialization strings, one at a time. Each call reads the current taxonomy_nodes from DB first, so previously-created nodes are reused (not duplicated). The classifier creates domains, focuses, languages, and classifies each seed into a family.
  - On subsequent boots: hash-based skip (same as seed content hash)
  - If new seeds are added: hash changes → classifier re-runs for unclassified seeds only, reading existing taxonomy from DB each time
  - `_bootstrap_classify()` is a simpler prompt than the full Taxonomist agent (classification only, no decomposition or reuse recommendations). The full Taxonomist in Phase 2 replaces this at runtime with richer output, but the bootstrap function remains for startup seeding.
  - **Critical**: every classify call must read `taxonomy_nodes` + `skill_families` from DB before deciding — this is how the Taxonomist avoids creating duplicate entries
  - Fallback: if no API key available (local dev without key), load a hardcoded default taxonomy so the app still boots

**Modify:**
- `skillforge/main.py` — call `load_taxonomy()` in lifespan handler after `load_seeds()`

**Create:**
- `tests/test_taxonomy_queries.py` — CRUD operations, tree traversal, idempotent loading

### Wave 1-4: Taxonomy API + Registry UI

**Create:**
- `skillforge/api/taxonomy.py` — new router:
  - `GET /api/taxonomy` — full tree (domains with nested focuses and languages)
  - `GET /api/taxonomy/{node_id}` — single node with children
  - `GET /api/families` — list families, filterable by `?domain=`, `?focus=`, `?language=`, `?tag=`
  - `GET /api/families/{family_id}` — family detail with variant list
  - `GET /api/families/{family_id}/variants` — variants with fitness scores

**Modify:**
- `skillforge/api/schemas.py` — add TaxonomyNodeResponse, SkillFamilyResponse, VariantResponse
- `skillforge/main.py` — register taxonomy router

**Create:**
- `frontend/src/components/TaxonomyBrowser.tsx` — tree view: Domain > Focus > Language with skill counts

**Modify:**
- `frontend/src/components/AgentRegistry.tsx` — add taxonomy filter dropdowns (Domain, Focus, Language) above the grid
- `frontend/src/types/index.ts` — add TaxonomyNode, SkillFamily, Variant types
- `frontend/src/App.tsx` — add `/taxonomy` route (optional, or integrate into Registry)
- `frontend/src/components/Sidebar.tsx` — add Taxonomy nav item

### Wave 1-5: Post-Run Report Generator

**Goal**: After every evolution run, generate a single structured report artifact that captures everything about the run in one place. This feeds the research paper and lets any future model ingest a complete run without querying 6+ tables.

**Create:**
- `skillforge/engine/report.py`
  - `async def generate_run_report(run_id: str) -> dict`
  - Queries all relevant tables and assembles a complete report:
    ```
    report/
    ├── metadata (run_id, mode, specialization, cost, duration, evolution_mode, family)
    ├── taxonomy (domain, focus, language — if classified)
    ├── challenges[] (prompt, difficulty, criteria, verification_method)
    ├── generations[]
    │   ├── fitness_curve (best, avg, delta from previous)
    │   ├── trait_survival + emergence
    │   ├── learning_log_entries (new lessons this gen)
    │   ├── pareto_front (skill IDs + their objectives)
    │   └── skills[]
    │       ├── id, maturity, is_pareto_optimal
    │       ├── fitness_breakdown (L1-L5 scores)
    │       ├── trait_attribution (which traits → which scores)
    │       ├── mutations + parent_ids + rationale
    │       ├── competition_results[] (per challenge: pass/fail, metrics, trace summary)
    │       └── skill_md_preview (first 30 lines, not full content — keep report <1MB)
    ├── variant_evolutions[] (v2.0: per-dimension winner, fitness, challenge)
    ├── assembly_report (v2.0: Engineer's merge decisions, integration test result)
    ├── bible_findings[] (new patterns published during this run)
    ├── learning_log (full accumulated lessons)
    └── summary
        ├── best_skill_id + aggregate_fitness
        ├── total_cost_usd + cost_per_generation
        ├── wall_clock_duration
        ├── key_discoveries (top 3 learning log entries by novelty)
        └── evolution_mode + dimensions_evolved (v2.0)
    ```
  - Saves to `data/reports/{run_id}.json`
  - Also saves a human-readable markdown version to `data/reports/{run_id}.md`

**Modify:**
- `skillforge/engine/evolution.py` — call `generate_run_report(run.id)` as the last step after `evolution_complete` event, fire-and-forget (report failure never blocks the pipeline)
- `skillforge/api/routes.py` — add `GET /api/runs/{run_id}/report` endpoint that returns the JSON report (or 404 if not yet generated)

**Create:**
- `tests/test_report.py` — verify report structure, verify all sections populated from mock data, verify <1MB size constraint

---

## Phase 2: Taxonomist Agent

**Goal**: Build the Taxonomist, classify runs at submission time. Runs still evolve molecularly.

### Wave 2-1: Taxonomist Agent

**Create:**
- `skillforge/agents/taxonomist.py`
  - `async def classify_and_decompose(specialization: str, taxonomy_tree: list[TaxonomyNode], existing_families: list[SkillFamily]) -> TaxonomistOutput`
  - Single structured-output Sonnet call
  - Output: classification (domain/focus/language/family slugs), decomposition_strategy, variant_dimensions (list of {name, tier, description, evaluation_focus}), reuse_recommendations, justification
  - Prompt enforces: check existing before creating new, justify new entries
- `tests/test_taxonomist.py` — mock LLM, verify classification, verify reuse of existing entries, verify monolithic for simple skills

### Wave 2-2: Integration into Evolution Entry Point

**Modify:**
- `skillforge/api/schemas.py` — add `evolution_mode: str | None = None` to EvolveRequest (defaults to auto-detect)
- `skillforge/api/routes.py` — before spawning evolution task: (1) query `get_taxonomy_tree()` and `list_families()` from DB, (2) pass both to Taxonomist along with the specialization, (3) store returned family_id + evolution_mode on EvolutionRun. If mode is auto, Taxonomist decides. If Taxonomist creates new taxonomy_nodes or families, they are persisted to DB before the evolution starts.
- `skillforge/engine/events.py` — add new event types: taxonomy_classified, decomposition_complete, variant_evolution_started, variant_evolution_complete, assembly_started, assembly_complete, integration_test_started, integration_test_complete
- `skillforge/engine/evolution.py` — after challenge design, check `run.evolution_mode`. If "molecular", proceed as v1.x. If "atomic", delegate to variant_evolution (Phase 3). For now, "atomic" falls back to molecular with a log warning.
- `skillforge/config.py` — add model roles: "taxonomist" → Sonnet, "scientist" → same as challenge_designer, "engineer" → Sonnet

**Modify (frontend):**
- `frontend/src/components/SpecializationInput.tsx` — add "Evolution Mode" selector in parameters section: Auto (default) / Atomic / Classic. Auto means Taxonomist decides.
- `frontend/src/types/index.ts` — add new event types to discriminated union
- `frontend/src/hooks/useEvolutionSocket.ts` — handle new event types

---

## Variant Evaluation Strategy

The v1.x L1-L5 Reviewer pipeline was designed for monolithic skills. Atomic variants need a different approach — more focused, more measurable, and controlled for consistency.

### What changes for variant evaluation

| Layer | v1.x (monolithic) | v2.0 (variant) |
|-------|-------------------|----------------|
| L1: Deterministic | Generic compile/test/lint | **Per-dimension `score.py`** — quantifiable metrics specific to what the variant does |
| L2: Trigger accuracy | Precision/recall on description | **Skipped** — variants don't have triggers, the composite does |
| L3: Trace analysis | Did the skill load? Instructions followed? | **Scoped** — did the variant use its own scripts/references? Did it stay in scope? |
| L4: Comparative | Pairwise across all dimensions | **Within-dimension only** — compare fixture strategies against each other, not against mock strategies |
| L5: Trait attribution | Which instruction → fitness | **Simplified** — the variant IS the trait, so attribution is the variant's overall score |

### Per-dimension evaluation criteria

The Scientist designs a focused challenge per dimension AND a scoring rubric. The rubric is machine-readable JSON (same as the Domain-Specific Test Environments architecture from the backlog):

```json
{
  "dimension": "mock-strategy",
  "quantitative": [
    {"metric": "isolation_score", "weight": 0.4, "description": "Are external deps fully isolated?"},
    {"metric": "mock_realism", "weight": 0.3, "description": "Do mocks behave like real deps?"},
    {"metric": "setup_brevity", "weight": 0.15, "description": "Lines of mock setup code"},
    {"metric": "teardown_clean", "weight": 0.15, "description": "Are mocks properly cleaned up?"}
  ],
  "qualitative": [
    "Mocks should be maintainable — no brittle implementation detail coupling",
    "Should work with both sync and async code"
  ]
}
```

For foundation variants, add extensibility metrics:
```json
{
  "dimension": "foundation",
  "quantitative": [
    {"metric": "code_runs", "weight": 0.3, "type": "boolean"},
    {"metric": "internal_consistency", "weight": 0.25, "description": "All parts follow same patterns"},
    {"metric": "extensibility", "weight": 0.25, "description": "Can capability variants plug in easily?"},
    {"metric": "clarity", "weight": 0.2, "description": "Readability and maintainability"}
  ]
}
```

### Controlled testing guarantees

1. **Same challenge per dimension**: every variant in the "mock-strategy" dimension faces the identical challenge. The Scientist designs it once.
2. **Same foundation context**: all capability variants receive the same winning foundation. They're tested with identical scaffolding.
3. **Deterministic scoring where possible**: `scripts/score.py` produces JSON metrics that feed directly into fitness. No LLM judgment on quantifiable dimensions.
4. **Qualitative scoring via Reviewer**: only the qualitative criteria go through L4/L5 LLM evaluation. This is a smaller, more focused LLM call than v1.x.
5. **Reproducibility**: test fixtures are immutable within a run. Same variant + same challenge + same foundation = same environment every time.

### Assembly evaluation

After the Engineer assembles the composite, a separate evaluation checks:

| Metric | What it measures | How |
|--------|-----------------|-----|
| Integration pass rate | Does the composite solve challenges that span multiple dimensions? | Run 1-2 broad challenges (v1.x style) against the assembly |
| Synergy ratio | composite fitness / best individual variant fitness | >1.0 = synergy, <1.0 = interference |
| Conflict count | How many merge conflicts did the Engineer resolve? | Counted during assembly |
| validate_skill_structure | Does the composite meet all structural requirements? | Existing validator |

### Metrics that matter for the research paper

| Metric | Why it matters |
|--------|---------------|
| Per-dimension convergence rate | How fast do variants improve? Faster = atomic evolution is working |
| Fitness per dollar | Cost efficiency of atomic vs monolithic |
| Synergy ratio | Does assembly produce more than the sum of parts? |
| Variant reusability score | Does a variant from family A work in family B without re-evolution? |
| Human preference (blind) | Would a developer choose the evolved skill over a hand-written one? |
| Ablation impact | How much does removing one Reviewer layer degrade results? |

### Quantitative metrics (always collected, deterministic)

Every variant competitor run automatically measures:
- **Execution**: time, turn count, tool calls, token usage, cost
- **Output**: compiles, test pass rate, coverage delta, lint score, file count, validator exit code
- **Code quality proxies** (AST analysis): cyclomatic complexity, max function length, max nesting depth, function count, import count
- **Derived**: efficiency (fitness/tokens), speed-quality (fitness/time), instruction compliance, tool precision

Code quality proxies are measured by a shared `skillforge/engine/code_metrics.py` module that parses Python AST (and later JS/TS AST). These are reported alongside LLM-based qualitative scores — both feed into the run report, but separately, so the research paper can analyze their relative importance.

### Implementation

- `skillforge/engine/code_metrics.py` — new module, AST-based analysis (Wave 3-1)
- The Scientist outputs both a Challenge AND an evaluation criteria JSON per dimension (Wave 3-2)
- `scripts/score.py` per variant is generated by the Spawner as part of the mini-SKILL.md package (Wave 3-3)
- The Reviewer runs `score.py` + `code_metrics.py` for L1, skips L2, scopes L3/L4/L5 to the dimension (Wave 3-1, variant_evolution.py)
- Assembly evaluation runs after the Engineer (Wave 4-2, assembly.py)
- All quantitative metrics land in the post-run report (Wave 1-5)

---

## Phase 3: Variant-Aware Evolution

**Goal**: Build the orchestrator that runs per-dimension mini-evolutions. The core change.

### Wave 3-1: Variant Evolution Orchestrator

**Create:**
- `skillforge/engine/variant_evolution.py`
  - `async def run_variant_evolution(run: EvolutionRun, family: SkillFamily, dimensions: list[dict]) -> SkillGenome`
  - Orchestration:
    1. Scientist designs focused challenges per dimension
    2. Foundation variants evolve first (parallel within tier)
    3. Pick winning foundation
    4. Capability variants evolve in context of winning foundation (parallel within tier)
    5. Pick winning capabilities
    6. Engineer assembles (calls Phase 4, stub for now → returns foundation as-is)
    7. Returns assembled SkillGenome as run.best_skill
  - Each mini-evolution creates a VariantEvolution record + child EvolutionRun
  - Reuses existing run_evolution loop internally with smaller params (pop=2, gen=2, challenges=1)
  - Emits variant_evolution_started/complete events per dimension
  - Concurrency limited by VARIANT_CONCURRENCY config
- `tests/test_variant_evolution.py` — mock LLM, verify: orchestration order (foundation before capabilities), event sequence, VariantEvolution records created, concurrency limit respected

**Modify:**
- `skillforge/engine/evolution.py` — at the top of `run_evolution`, if `run.evolution_mode == "atomic"`, delegate to `variant_evolution.run_variant_evolution()` and return its result

### Wave 3-2: Scientist (Focused Challenge Generation) ‖ Wave 3-3: Spawner Variant Scope

*These two waves touch non-overlapping files and can run in parallel.*

**Wave 3-2 — Modify:**
- `skillforge/agents/challenge_designer.py` — add:
  - `async def design_variant_challenge(specialization: str, dimension: dict) -> Challenge`
  - Generates a single narrow challenge targeting one variant dimension
  - Reuses existing `_generate` + JSON extraction patterns
- `skillforge/config.py` — add `"scientist"` as alias for challenge_designer model
- `tests/test_challenge_designer.py` — add test for `design_variant_challenge` (mock LLM, verify single focused challenge output)

**Wave 3-3 — Modify:**
- `skillforge/agents/spawner.py` — add:
  - `async def spawn_variant_gen0(specialization: str, dimension: dict, foundation_genome: SkillGenome | None, pop_size: int = 2) -> list[SkillGenome]`
  - Creates focused mini-SKILL.md packages per dimension
  - For capability variants, winning foundation provided as context
  - Prompt instructs: "Create a skill focused ONLY on {dimension.name}. This variant will be assembled with other variants later."
- `tests/test_spawner.py` — add test for `spawn_variant_gen0` (mock LLM, verify focused output, verify foundation context injected for capability tier)

**Phase 3 QA Gate:**
- `tests/test_atomic_evolution_e2e.py` — full atomic pipeline with mocked LLM: Taxonomist classifies → Scientist designs focused challenges → foundation variants evolve → capabilities evolve in context → stub assembly returns foundation. Verify complete event sequence (taxonomy_classified → decomposition_complete → variant_evolution_started × N → variant_evolution_complete × N → assembly_started → assembly_complete). 30s timeout.

---

## Phase 4: Engineer + Assembly

**Goal**: Build the Engineer agent that assembles winning variants into a composite skill.

### Wave 4-1: Engineer Agent

**Create:**
- `skillforge/agents/engineer.py`
  - `async def assemble_variants(foundation: SkillGenome, capabilities: list[SkillGenome], family: SkillFamily) -> tuple[SkillGenome, str]`
  - Returns: assembled genome + integration report
  - Assembly logic:
    1. Foundation SKILL.md as skeleton
    2. Extract unique sections/instructions/scripts from each capability
    3. Weave into foundation's H2/H3 structure
    4. Merge supporting_files with name deconfliction
    5. Combine frontmatter descriptions
    6. Validate via validate_skill_structure
  - Single structured-output call (Sonnet, optionally Opus)
- `tests/test_engineer.py` — mock LLM, verify merge produces valid SkillGenome

### Wave 4-2: Assembly Engine

**Create:**
- `skillforge/engine/assembly.py`
  - `async def assemble_skill(run: EvolutionRun, family: SkillFamily, foundation: Variant, capabilities: list[Variant]) -> SkillGenome`
  - Flow: call Engineer → integration test (single challenge via Competitor + Reviewer L1-L3) → if fails, one refinement pass → save assembled genome → update family.best_assembly_id → save variants with is_active=1
- `tests/test_assembly.py` — mock Engineer + Competitor + Reviewer, verify: assembly flow completes, integration test triggers, refinement on failure, family.best_assembly_id updated

**Modify:**
- `skillforge/engine/variant_evolution.py` — replace the assembly stub with real `assemble_skill()` call. Emit assembly_started/complete events.

**Phase 4 QA Gate:**
- `tests/test_atomic_evolution_e2e.py` — extend Phase 3 e2e test to include real assembly. Full pipeline: Taxonomist → Scientist → variant evolutions → Engineer assembly → integration test. Verify assembled SkillGenome passes `validate_skill_structure`.

### Wave 4-3: Assembly API + Arena Integration

**Modify:**
- `skillforge/api/taxonomy.py` — add `GET /api/families/{family_id}/assembly` (returns current best assembly)
- `SCHEMA.md` — ensure variant_evolutions and any Phase 3-4 schema additions are documented

**Modify (frontend):**
- `frontend/src/components/EvolutionArena.tsx` — for atomic-mode runs, show per-dimension progress cards instead of per-competitor cards. Show assembly phase after variant evolutions complete.
- `frontend/src/hooks/useEvolutionSocket.ts` — handle variant_evolution_started/complete and assembly events to drive the arena UI

---

## Phase 5: Advanced Mode UI

**Goal**: Reveal variant internals to power users.

### Wave 5-1: Variant Breakdown View

**Create:**
- `frontend/src/components/VariantBreakdown.tsx`
  - Tree showing foundation + capabilities with fitness scores
  - Swap dropdown per dimension (alternatives sorted by fitness)
  - "Evolve" button per dimension
  - "Re-assemble" button

**Modify:**
- `frontend/src/components/EvolutionResults.tsx` — add "Advanced" toggle that reveals VariantBreakdown below the export preview
- `frontend/src/components/EvolutionArena.tsx` — per-dimension progress in atomic mode

### Wave 5-2: Swap + Re-evolve

**Create (API):**
- `POST /api/families/{family_id}/swap-variant` — swap a variant for an alternative, trigger re-assembly
- `POST /api/families/{family_id}/evolve-variant` — re-evolve a single dimension (creates a new VariantEvolution)

**Modify (frontend):**
- `frontend/src/components/VariantBreakdown.tsx` — wire swap dropdown + re-evolve/re-assemble buttons to API calls

---

## Cross-Cutting Concerns

### Config additions (`skillforge/config.py`)
- `DEFAULT_VARIANT_POP: int = 2`
- `DEFAULT_VARIANT_GENS: int = 2`
- `VARIANT_CONCURRENCY: int = 3`
- Model roles: `"taxonomist"`, `"scientist"`, `"engineer"` in MODEL_DEFAULTS

### Backward compatibility
- All new DB columns on existing tables: nullable with defaults
- `evolution_mode = "molecular"` is the default
- Existing evolution.py loop unchanged — it IS the inner loop for variant mini-evolutions
- All existing tests pass without modification
- Each phase is independently deployable
- `POST /api/evolve/from-parent` works with atomic mode: fork seed → Taxonomist classifies → atomic evolution

### New event types (engine/events.py)
- taxonomy_classified, decomposition_complete
- variant_evolution_started, variant_evolution_complete
- assembly_started, assembly_complete
- integration_test_started, integration_test_complete

### Documentation updates (every wave that changes them)
- **SCHEMA.md** — updated whenever DB tables/columns change (Waves 1-2, 4-3 at minimum, any wave that alters schema)
- **CLAUDE.md** — updated after Phase 1 (add v2.0 architecture context, taxonomy, agent roster) and after Phase 3 (atomic evolution flow)
- **PROGRESS.md** — updated after every wave (per QA checklist)
- **Journal entries** — one per phase completion

### Existing API updates
- `GET /api/seeds` — add taxonomy fields (domain, focus, language, family_id) to seed responses (Wave 1-4)
- `GET /api/runs` — add evolution_mode + family_id to run list responses (Wave 2-2)
- `GET /api/runs/{id}` — add variant_evolutions summary for atomic runs (Wave 4-3)

### Taxonomy sync strategy
- Initial taxonomy seeded in Wave 1-3 by running a lightweight classifier against the 16 Gen 0 seeds (LLM-driven, not hardcoded)
- Fallback: hardcoded default taxonomy if no API key available (local dev)
- Taxonomist can create new taxonomy_nodes at runtime when classifying runs (Wave 2-1)
- New nodes require justification (logged) and are auto-persisted to DB
- Seed reclassification: if seed content hash changes on startup, `taxonomy_seeds.py` re-runs the classifier for unclassified seeds
- The Gen 0 seeds are the training data for the initial taxonomy — it emerges from real data, not manual guesses

---

## Phase Boundaries

| After | Milestone | Independently deployable? |
|-------|-----------|--------------------------|
| Phase 1 | Taxonomy browsable in registry, seeds classified into families | Yes |
| Phase 2 | Runs get classified by Taxonomist, evolution mode selector on /new | Yes |
| Phase 3 | Atomic evolution produces per-dimension winners | Yes (feature-flagged) |
| Phase 4 | Engineer assembles composite skill, full atomic pipeline works | Yes |
| Phase 5 | Advanced mode reveals variants, swap/re-evolve works | Yes |

---

## Backlog (deferred)

- **Cross-family reuse**: Taxonomist recommends variants from other families. Data model supports it from Phase 1.
- **Recursive self-improvement meta-loop**: use the platform to evolve its own agent skills. Skills authored in Phase 1 Wave 1-1.
- **Variant marketplace**: community-shared variants across skill families.
- **Transfer learning**: proven patterns from one family accelerate evolution in new families.
