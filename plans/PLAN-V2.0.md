# PLAN v2.0 — Atomic Variant Evolution

**Source of truth**: `plans/SPEC-V2.0.md`  
**Phases**: 5 phases, 14 waves. Each wave = one commit.  
**Estimated total**: ~3-4 sessions  

---

## Development Workflow

Same as v1.x: wave-based commits, tests passing after each wave, push after each wave.

### QA Checklist (per wave)
1. `uv run pytest tests/ -x -q` — all passing
2. `cd frontend && npx tsc --noEmit` — clean
3. `uv run ruff check skillforge/ tests/` — clean
4. New code has type hints
5. PROGRESS.md updated

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
  - Hardcoded initial taxonomy: ~8 domains, ~30 focuses, ~15 languages
  - Classify existing 16 seed skills into families
  - Hash-based skip on startup (same as seed content hash)

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
- `skillforge/api/routes.py` — before spawning evolution task, call Taxonomist. Store family_id + evolution_mode on EvolutionRun. If mode is auto, Taxonomist decides.
- `skillforge/engine/events.py` — add new event types: taxonomy_classified, decomposition_complete, variant_evolution_started, variant_evolution_complete, assembly_started, assembly_complete, integration_test_started, integration_test_complete
- `skillforge/engine/evolution.py` — after challenge design, check `run.evolution_mode`. If "molecular", proceed as v1.x. If "atomic", delegate to variant_evolution (Phase 3). For now, "atomic" falls back to molecular with a log warning.
- `skillforge/config.py` — add model roles: "taxonomist" → Sonnet, "scientist" → same as challenge_designer, "engineer" → Sonnet

**Modify (frontend):**
- `frontend/src/components/SpecializationInput.tsx` — add "Evolution Mode" selector in parameters section: Auto (default) / Atomic / Classic. Auto means Taxonomist decides.
- `frontend/src/types/index.ts` — add new event types to discriminated union
- `frontend/src/hooks/useEvolutionSocket.ts` — handle new event types

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

**Modify:**
- `skillforge/engine/evolution.py` — at the top of `run_evolution`, if `run.evolution_mode == "atomic"`, delegate to `variant_evolution.run_variant_evolution()` and return its result

### Wave 3-2: Scientist (Focused Challenge Generation)

**Modify:**
- `skillforge/agents/challenge_designer.py` — add:
  - `async def design_variant_challenge(specialization: str, dimension: dict) -> Challenge`
  - Generates a single narrow challenge targeting one variant dimension
  - Reuses existing `_generate` + JSON extraction patterns

**Modify:**
- `skillforge/config.py` — add `"scientist"` as alias for challenge_designer model

### Wave 3-3: Spawner Variant Scope

**Modify:**
- `skillforge/agents/spawner.py` — add:
  - `async def spawn_variant_gen0(specialization: str, dimension: dict, foundation_genome: SkillGenome | None, pop_size: int = 2) -> list[SkillGenome]`
  - Creates focused mini-SKILL.md packages per dimension
  - For capability variants, winning foundation provided as context
  - Prompt instructs: "Create a skill focused ONLY on {dimension.name}. This variant will be assembled with other variants later."

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

**Modify:**
- `skillforge/engine/variant_evolution.py` — replace the assembly stub with real `assemble_skill()` call. Emit assembly_started/complete events.

### Wave 4-3: Assembly API + Arena Integration

**Modify:**
- `skillforge/api/taxonomy.py` — add `GET /api/families/{family_id}/assembly` (returns current best assembly)

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

### New event types (engine/events.py)
- taxonomy_classified, decomposition_complete
- variant_evolution_started, variant_evolution_complete
- assembly_started, assembly_complete
- integration_test_started, integration_test_complete

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
