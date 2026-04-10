# SPEC v2.0 — Atomic Variant Evolution & Skill Assembly

**Status**: Finalized  
**Date**: 2026-04-10  
**Authors**: Matt + Claude Code

---

## Overview

v2.0 introduces **atomic variant evolution**: decompose skills into focused, independently-evolvable variants, then assemble the best variants into a composite skill. This replaces the v1.x approach of evolving entire SKILL.md files as monolithic units.

**Why**: v1.x's monolithic evolution has a huge mutation surface (45 competitor runs, ~$7, ~54 min). Fitness signals are averaged across dimensions, making it hard to know which part of a skill is good or bad. Atomic evolution isolates each dimension, produces clearer fitness signals, and enables cheaper/faster convergence.

**Key metaphor**: Don't evolve the whole organism. Evolve the genes. Assemble the organism.

---

## Taxonomy

### Hierarchy

```
Domain → Focus → Language → Skill (family) → Variant (atomic unit)
```

| Level | Examples | Stability | Approximate count |
|-------|---------|-----------|-------------------|
| Domain | Testing, Security, DevOps, Data, Code Quality, Documentation, Architecture | Fixed | ~8-10 |
| Focus | Unit Tests, E2E, Static Analysis, Containers, Cleaning | Semi-stable | ~30-50 |
| Language | Python, JavaScript, Rust, SQL, universal | Fixed | ~15 |
| Skill | pytest-generator, playwright-gen, dockerfile-optimizer | Grows organically | ~100s |
| Variant | mock-heavy, fixture-rich, property-based, snapshot | Evolved/discovered | ~1000s |

### Definitions

- **Variant** is the atomic unit. A complete, runnable, testable mini-SKILL.md package focused on one specific capability or strategy. Each variant includes its own frontmatter, focused instructions, scripts, and references. Can be tested independently.
- **Skill** is a family of related variants. Not a single file — a collection of variants that address the same domain+focus+language from different angles.
- **Tags** capture cross-cutting concerns (framework, strategy, convention) that don't fit the hierarchy.
- **Specialization text** is the free-form nuance that the taxonomy can't capture.

### What varies across domains

| Domain | Variant axis | Examples |
|--------|-------------|----------|
| Testing | Strategy | mock-heavy, property-based, snapshot, fixture-rich |
| Security | Target | web-focused, crypto, injection, supply-chain |
| DevOps / IaC | Platform | AWS, GCP, Azure, multi-cloud |
| Code Quality | Concern | security, performance, style, complexity |
| Documentation | Convention | numpy-style, google-style, sphinx, JSDoc |
| Data | Backend | Postgres, MySQL, SQLite, BigQuery |

---

## Agent Roster

| Agent | Role | New in v2.0? |
|-------|------|-------------|
| Taxonomist | Classify, decompose, recommend reuse | Yes |
| Scientist | Design focused experiments per variant dimension | Renamed from Challenge Designer |
| Spawner | Create initial variant populations (narrower scope) | Updated |
| Competitor | Run variant against focused challenge | Unchanged |
| Reviewer | Evaluate variant fitness (L1-L5 pipeline) | Renamed from Judge |
| Breeder | Mutate within a single variant dimension (horizontal) | Updated |
| Engineer | Assemble variants + integration test + refinement (vertical) | Yes |

### Taxonomist

Dedicated agent for classification and decomposition. Runs before evolution begins. Does NOT design challenges or evaluate fitness.

**Responsibilities:**
1. **Classify** — assign Domain → Focus → Language. Uses existing taxonomy as primary guide; only creates new entries when nothing fits (with justification).
2. **Decompose** — identify variant dimensions (foundation + capabilities). Output: list of dimensions with name, tier, description, and evaluation focus.
3. **Check existing** — query the registry for matching entries and reusable variants. Prevents taxonomy sprawl.
4. **Recommend reuse** — flag high-fitness variants from other families that could be reused instead of re-evolved.
5. **Decide decomposition strategy** — flag simple skills as `"monolithic"` (no decomposition, flows through v1.x pipeline unchanged). Threshold: fewer than 2 meaningfully independent dimensions → skip decomposition.

**Model**: Sonnet (classification is structured, not creative).

### Scientist (renamed from Challenge Designer)

Designs focused challenges per variant dimension. Each challenge tests one specific capability in isolation.

### Breeder vs Engineer

- **Breeder** operates *horizontally* — improving one variant over generations. Reads traces, mutates, produces next-gen variants. Never sees the full composite. Stays in its lane.
- **Engineer** operates *vertically* — picks best variant per dimension, composes them into a whole skill, runs integration test, refines seams. Owns the full compose → test → refine cycle.

---

## Two-Tier Variant Model

### Foundation variants

Structural decisions other variants build on:
- Project structure / conventions
- Test setup / fixture strategy
- Import patterns / tool configuration
- The "philosophy" of the skill

### Capability variants

Focused modules that plug into the foundation:
- Mock strategy (adapts to the foundation's fixture approach)
- Edge case generation
- Assertion patterns
- Output formatting
- Error handling style

### Evolution order

1. Foundation variants evolve first (or in parallel with a default foundation)
2. Pick the winning foundation
3. Capability variants evolve in the context of the winning foundation
4. Parallel within each tier (all foundation variants evolve simultaneously, then all capability variants simultaneously)

### Variant granularity

A variant represents one coherent "strategy dimension" — something a user could meaningfully swap. The Taxonomist proposes dimensions; the Scientist validates each is independently testable by designing a focused challenge for it.

- **Too small**: "assertion phrasing style" (not independently testable)
- **Right size**: "mock strategy", "fixture approach", "edge case generation method"
- **Too large**: the entire skill (that's v1.x molecular evolution)

---

## Assembly Strategy

**Locked**: Foundation skeleton + trait-based capability merging (Options B+D from concept phase).

The Engineer:
1. Starts with the winning foundation variant's SKILL.md as the skeleton
2. For each winning capability variant, extracts its unique instructions, scripts, and references
3. Weaves capability instructions into the foundation's H2/H3 structure
4. Merges supporting_files: scripts from all variants into scripts/, references into references/, with name deconfliction
5. Merges frontmatter: description combines trigger conditions from all variants
6. Validates the assembly via `validate_skill_structure`
7. Runs a single integration challenge to verify the composite works end-to-end
8. If integration fails (L1 score < threshold), gets one refinement pass

Conflict resolution: higher-fitness variant wins on overlap. The Engineer's LLM call makes the final judgment on integration.

---

## Variant Evaluation

### How variant review differs from monolithic review

The v1.x L1-L5 pipeline evaluates whole skills across all dimensions at once. For atomic variants, evaluation is narrower and more precise:

- **L1 (Deterministic)**: replaced by per-dimension `score.py` that produces quantifiable metrics specific to what the variant does (isolation score for mock-strategy, coverage for edge-case-generation, etc.)
- **L2 (Trigger accuracy)**: skipped — variants don't have triggers, the composite does
- **L3 (Trace analysis)**: scoped to the variant's dimension — did it use its own scripts? Did it stay in scope?
- **L4 (Comparative)**: within-dimension only — compare mock strategies against each other, not against fixture strategies
- **L5 (Trait attribution)**: simplified — the variant IS the trait, so attribution equals the variant's overall score

### Per-dimension evaluation criteria

Each variant dimension gets a machine-readable scoring rubric (JSON) designed by the Scientist alongside the focused challenge. The rubric specifies quantitative metrics (weighted, measured by `score.py`) and qualitative criteria (evaluated by the Reviewer's LLM layers).

Foundation variants additionally measure extensibility — can capability variants plug into this foundation cleanly?

### Assembly evaluation

After the Engineer assembles the composite, a separate evaluation measures:
- **Integration pass rate**: does the composite solve challenges spanning multiple dimensions?
- **Synergy ratio**: composite fitness / best individual variant fitness. >1.0 means synergy, <1.0 means interference.
- **Structural validity**: passes `validate_skill_structure`

### Controlled testing guarantees

1. Same challenge per dimension — designed once, used for all variants in that dimension
2. Same foundation context — all capability variants tested with identical scaffolding
3. Deterministic scoring where possible — `score.py` produces JSON metrics, no LLM judgment on quantifiable dimensions
4. Immutable test fixtures within a run — same variant + same challenge + same foundation = same environment

---

## Atomic Evolution Flow

### Molecular (v1.x — unchanged)

```
Seed Skill (monolith)
  ↓ spawn population of 5 full skills
  ↓ test each against 3 challenges (end-to-end)
  ↓ judge across all dimensions
  ↓ breed next generation
  ↓ repeat × 3 generations
  = 45 full competitor runs, ~$7, ~54 min
```

### Atomic (v2.0)

```
Taxonomist classifies + decomposes into variant dimensions
  ↓ Scientist designs 1 focused challenge per dimension
  ↓ Evolve foundation variants (2 pop × 2 gen × 1 challenge each, parallel)
  ↓ Pick winning foundation
  ↓ Evolve capability variants in context of foundation (2 pop × 2 gen × 1 challenge each, parallel)
  ↓ Pick winning capabilities
  ↓ Engineer assembles foundation + capabilities into composite skill
  ↓ Integration test + optional refinement
  = ~16 focused runs + 1 integration, ~$3-4, ~20-30 min (parallel)
```

### Cost comparison

| | v1.x Molecular | v2.0 Atomic |
|---|---|---|
| Population per evolution | 5 | 2 |
| Generations | 3 | 2 |
| Challenges per evolution | 3 | 1 (focused) |
| Competitor runs per evolution | 45 | 4 |
| Variant dimensions | 1 (whole skill) | ~4 |
| Total competitor runs | 45 | ~16 + assembly |
| Estimated cost | ~$7 | ~$3-4 |
| Estimated time | ~54 min | ~20-30 min (parallel) |

---

## User Experience

### Default mode

The decomposition is invisible. User describes what they want, gets a finished skill. The engine handles variant evolution and assembly behind the scenes.

### Advanced mode

Opt-in, not shown by default. Reveals the variant breakdown:

```
Foundation: fixture-rich (v3, fitness 0.92)     [swap ▾]
├── Mock strategy: auto-patch (v2, 0.88)        [swap ▾] [evolve]
├── Assertions: strict-typing (v4, 0.95)        [swap ▾] [evolve]
├── Edge cases: hypothesis (v1, 0.78)           [swap ▾] [evolve]
└── Output: pytest-style (v2, 0.91)             [swap ▾] [evolve]

[Re-assemble]  [Export]
```

**Advanced user capabilities:**
- Swap any variant from alternatives (sorted by fitness)
- Lock good variants, re-evolve only the weak ones
- Pull high-fitness variants from other skill families (cross-pollination)
- Fork and evolve a single variant in isolation
- View lineage/evolution history per variant

**Upgrade path**: Default → get good skill → notice one aspect isn't right → flip to advanced → swap that variant → done.

---

## Data Model

### New tables

**`taxonomy_nodes`** — Domain/Focus/Language hierarchy.

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT PK | UUID |
| `level` | TEXT NOT NULL | `"domain"` / `"focus"` / `"language"` |
| `slug` | TEXT NOT NULL | kebab-case, UNIQUE within level |
| `label` | TEXT NOT NULL | Display name |
| `parent_id` | TEXT NULL | FK → self. NULL for domain-level |
| `description` | TEXT NOT NULL | Short explanation |
| `created_at` | TEXT NOT NULL | ISO-8601 UTC |

Indexes: `idx_taxonomy_level_slug` UNIQUE on `(level, slug)`, `idx_taxonomy_parent` on `(parent_id)`.

**`skill_families`** — Groups variants under a taxonomy path.

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT PK | UUID |
| `slug` | TEXT NOT NULL | kebab-case, UNIQUE |
| `label` | TEXT NOT NULL | Display name |
| `domain_id` | TEXT NOT NULL | FK → taxonomy_nodes |
| `focus_id` | TEXT NOT NULL | FK → taxonomy_nodes |
| `language_id` | TEXT NOT NULL | FK → taxonomy_nodes |
| `tags` | TEXT NOT NULL | JSON array of strings |
| `specialization` | TEXT NOT NULL | Free-form nuance text |
| `decomposition_strategy` | TEXT NOT NULL | `"atomic"` / `"monolithic"` |
| `created_at` | TEXT NOT NULL | ISO-8601 UTC |
| `best_assembly_id` | TEXT NULL | FK → skill_genomes (current best assembled skill) |

Indexes: `idx_family_slug` UNIQUE, `idx_family_taxonomy` on `(domain_id, focus_id, language_id)`.

**`variants`** — Atomic units linking to families and genomes.

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT PK | UUID |
| `family_id` | TEXT NOT NULL | FK → skill_families |
| `dimension` | TEXT NOT NULL | e.g., "foundation", "mock-strategy" |
| `tier` | TEXT NOT NULL | `"foundation"` / `"capability"` |
| `genome_id` | TEXT NOT NULL | FK → skill_genomes (the actual content) |
| `fitness_score` | REAL NULL | Aggregate fitness |
| `is_active` | INTEGER NOT NULL | 1 = current best for this dimension |
| `evolution_id` | TEXT NULL | FK → variant_evolutions |
| `created_at` | TEXT NOT NULL | ISO-8601 UTC |

Indexes: `idx_variant_family` on `(family_id, dimension)`, `idx_variant_active` on `(family_id, is_active)`.

**`variant_evolutions`** — Independent mini-evolution runs per dimension.

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT PK | UUID |
| `family_id` | TEXT NOT NULL | FK → skill_families |
| `dimension` | TEXT NOT NULL | Which dimension |
| `tier` | TEXT NOT NULL | `"foundation"` / `"capability"` |
| `parent_run_id` | TEXT NOT NULL | FK → evolution_runs (orchestrating run) |
| `population_size` | INTEGER NOT NULL | Default 2 |
| `num_generations` | INTEGER NOT NULL | Default 2 |
| `status` | TEXT NOT NULL | pending / running / complete / failed |
| `winner_variant_id` | TEXT NULL | FK → variants |
| `foundation_genome_id` | TEXT NULL | FK → skill_genomes (context for capabilities) |
| `challenge_id` | TEXT NULL | FK → challenges (focused challenge) |
| `created_at` | TEXT NOT NULL | ISO-8601 UTC |
| `completed_at` | TEXT NULL | ISO-8601 UTC |

Indexes: `idx_varevo_family` on `(family_id)`, `idx_varevo_parent` on `(parent_run_id)`.

### Modified tables (nullable additions, backward compatible)

**`evolution_runs`** — add:
- `family_id` TEXT NULL FK → skill_families
- `evolution_mode` TEXT NOT NULL DEFAULT `"molecular"` (`"molecular"` / `"atomic"`)

**`skill_genomes`** — add:
- `variant_id` TEXT NULL FK → variants

---

## Event Types (new)

| Event | Emitted when |
|-------|-------------|
| `taxonomy_classified` | Taxonomist finished classification |
| `decomposition_complete` | Variant dimensions identified |
| `variant_evolution_started` | A single dimension's mini-evolution begins |
| `variant_evolution_complete` | A single dimension's winner selected |
| `assembly_started` | Engineer begins merge |
| `assembly_complete` | Assembled skill ready |
| `integration_test_started` | Post-assembly integration test |
| `integration_test_complete` | Integration test results |

---

## Configuration (new entries in config.py)

| Key | Default | Notes |
|-----|---------|-------|
| `DEFAULT_VARIANT_POP` | 2 | Population per variant evolution |
| `DEFAULT_VARIANT_GENS` | 2 | Generations per variant evolution |
| `VARIANT_CONCURRENCY` | 3 | Max variant dimensions evolving in parallel |
| Model: `"taxonomist"` | Sonnet | Classification agent |
| Model: `"scientist"` | Sonnet | Alias for challenge_designer |
| Model: `"engineer"` | Sonnet (Opus optional) | Assembly agent |

---

## Recursive Self-Improvement

Each pipeline agent has its own Claude Agent Skill in `.claude/skills/`:
- `taxonomist/` — classifying domains, decomposing into variant dimensions
- `scientist/` — designing focused evaluation challenges
- `spawner/` — creating diverse initial populations
- `breeder/` — reflective mutation from execution traces
- `reviewer/` — multi-layer fitness evaluation
- `engineer/` — assembling variants into composite skills

These skills are evolvable by the platform itself. The meta-loop:
1. Pipeline runs using current agent skills
2. Measure pipeline quality (speed, cost, output fitness)
3. Evolve the agent skills using the platform
4. Run pipeline again with improved agents
5. Repeat

---

## Backward Compatibility

- All new columns on existing tables are nullable with defaults
- `evolution_mode = "molecular"` is the default; v1.x runs unaffected
- The existing `POST /api/evolve` auto-detects mode via Taxonomist (or accepts explicit override)
- The existing evolution.py loop is the inner loop for variant mini-evolutions — no changes to it
- All existing tests pass unchanged
- Each phase is independently deployable

---

## Relationship to v1.x

v2.0 is not a rewrite — it's an evolution of the platform.

- v1.x molecular evolution still works and ships value today
- v2.0 is introduced incrementally: taxonomy → Taxonomist → atomic evolution → assembly → advanced UI
- The Reviewer pipeline, Competitor infrastructure, and Breeder all carry forward
- The key new components: Taxonomist, variant evolution orchestrator, Engineer

---

## Implementation

See `plans/PLAN-V2.0.md` for phased file-by-file implementation (5 phases, 14 waves).
