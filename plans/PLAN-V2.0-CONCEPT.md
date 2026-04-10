# PLAN v2.0 — Atomic Variant Evolution & Skill Assembly

**Status**: Concept / Active Design  
**Date**: 2026-04-10  
**Authors**: Matt + Claude Code  

---

## The Insight

v1.x evolves entire skills as monolithic units — a full SKILL.md with instructions, scripts, references, and all behavioral patterns bundled together. This is **molecular evolution**: mutating whole organisms and testing them end-to-end.

The problem: the mutation surface is enormous, testing is expensive ($5-10 per run, ~54 min), and fitness evaluation averages across many dimensions, making it hard to know *which part* of a skill is good or bad.

v2.0 proposes **atomic evolution**: break skills into focused, independently-evolvable **variants**, then **assemble** the best variants into a composite skill. This mirrors how biological evolution works at the gene level — genes evolve independently under selection pressure, and organisms are assemblies of fit genes.

---

## Taxonomy

### Hierarchy

```
Domain → Focus → Language → Skill (family) → Variant (atomic unit)
```

| Level | Example | Stability | Count |
|-------|---------|-----------|-------|
| Domain | Testing, Security, DevOps, Data, Code Quality, Documentation, Architecture | Fixed | ~8-10 |
| Focus | Unit Tests, E2E, Static Analysis, Containers, Cleaning | Semi-stable | ~30-50 |
| Language | Python, JavaScript, Rust, SQL, universal | Fixed | ~15 |
| Skill | pytest-generator, playwright-gen, dockerfile-optimizer | Grows organically | ~100s |
| Variant | mock-heavy, fixture-rich, property-based, snapshot | Evolved/discovered | ~1000s |

### Key principles

- **Variant is the atomic unit.** It's a complete, runnable, testable package focused on one specific capability or strategy.
- **Skill is a family of related variants.** Not a single file — a collection of variants that address the same domain+focus+language from different angles.
- **Tags capture cross-cutting concerns.** Framework (pytest, jest), strategy (mock-heavy, AWS), convention (numpy-style) — things that don't fit neatly into the hierarchy.
- **Specialization text is the full address.** Free-form nuance that the taxonomy can't capture.

### What varies across domains

The "variant" dimension means different things in different domains:

| Domain | Variant axis | Examples |
|--------|-------------|----------|
| Testing | Strategy | mock-heavy, property-based, snapshot, fixture-rich |
| Security | Target | web-focused, crypto, injection, supply-chain |
| DevOps / IaC | Platform | AWS, GCP, Azure, multi-cloud |
| Code Quality | Concern | security, performance, style, complexity |
| Documentation | Convention | numpy-style, google-style, sphinx, JSDoc |
| Data | Backend | Postgres, MySQL, SQLite, BigQuery |

This is why variants are better modeled as flexible atomic units with tags, not as a rigid 5th taxonomy level.

---

## Atomic Evolution

### Current (v1.x) — Molecular Evolution

```
Seed Skill (monolith)
  ↓ spawn population of 5 full skills
  ↓ test each against 3 challenges (end-to-end)
  ↓ judge across all dimensions simultaneously
  ↓ breed next generation (mutate entire molecule)
  ↓ repeat × 3 generations
  = 45 full competitor runs, ~$7, ~54 min
```

**Problems:**
- Huge mutation surface — changing the fixture strategy also mutates mock patterns
- Fitness is averaged across dimensions — a great fixture strategy can be masked by bad assertion style
- Expensive — each competitor is a full Agent SDK session
- Slow convergence — too many variables changing at once

### Proposed (v2.0) — Atomic Evolution → Assembly

```
Identify variant dimensions for the skill domain
  ↓ evolve each variant independently
     ├── fixture strategy:  2 pop × 2 gen × 1 focused challenge
     ├── mock patterns:     2 pop × 2 gen × 1 focused challenge
     ├── assertion style:   2 pop × 2 gen × 1 focused challenge
     └── edge case gen:     2 pop × 2 gen × 1 focused challenge
  ↓ pick winners from each variant evolution
  ↓ assemble into composite skill
  ↓ (optional) one integration round to tune the assembly
  = ~16 focused runs + 1 integration run, potentially cheaper & faster
```

**Benefits:**
- Smaller evolution surface → faster convergence per variant
- Focused judging → clearer signal on what's actually good
- Parallelizable — evolve all variants simultaneously
- Cheaper per run — narrow challenges, fewer turns needed
- Reusable — winning mock strategy works across multiple skill families
- User choice — swap out individual variants without re-evolving everything

### Cost comparison (estimated)

| | v1.x Molecular | v2.0 Atomic |
|---|---|---|
| Population per evolution | 5 | 2 |
| Generations | 3 | 2 |
| Challenges per evolution | 3 | 1 (focused) |
| Competitor runs per evolution | 45 | 4 |
| Variant dimensions | 1 (whole skill) | ~4 |
| Total competitor runs | 45 | ~16 + assembly |
| Estimated cost | ~$7 | ~$3-4 (TBD) |
| Estimated time | ~54 min | ~20-30 min (parallel) |

---

## Skill Assembly (Composability)

### The hard question: how do variants compose?

This is the core design challenge of v2.0. Options under consideration:

### Option A: Section-based composition

Each variant owns a section of the final SKILL.md. Assembly is concatenation with a generated preamble.

```markdown
# pytest-generator

## Core Workflow          ← from base variant
## Fixture Strategy       ← from fixture-rich variant (winner)  
## Mocking Patterns       ← from mock-heavy variant (winner)
## Assertion Style        ← from strict-assertions variant (winner)
## Edge Case Generation   ← from hypothesis-style variant (winner)
```

**Pros:** Simple, predictable, each section is self-contained  
**Cons:** Sections may conflict, no awareness of each other, ordering matters

### Option B: Layered composition

Base variant provides the skeleton. Overlay variants inject modifications.

```
Base: pytest-generator-core
  + Layer: fixture-strategy-rich (overrides fixture section)
  + Layer: mock-pattern-auto (adds mock guidance)
  + Layer: edge-case-hypothesis (adds property testing section)
```

**Pros:** Clear precedence, base handles integration  
**Cons:** Layers need to know about the base structure, coupling

### Option C: Router composition

A meta-skill that dispatches to the appropriate variant based on context.

```markdown
# pytest-generator

## Routing
- If user mentions fixtures or conftest → use fixture-rich approach
- If user mentions mocking or external APIs → use mock-heavy approach  
- If user mentions edge cases or fuzzing → use property-based approach
- Default → use balanced approach
```

**Pros:** Dynamic, adapts to context, no conflicts  
**Cons:** Adds routing complexity, may not combine strategies within a single request

### Option D: Trait-based merging (most promising?)

Each variant produces **trait contributions** — specific instructions, script functions, reference sections. An assembler merges non-conflicting traits and resolves conflicts via priority or fitness score.

```
Variant A contributes: fixture_setup(), conftest patterns, fixture examples
Variant B contributes: mock_strategy(), patch patterns, mock examples  
Variant C contributes: edge_case_gen(), hypothesis integration
Engineer: merge scripts, concatenate reference sections, weave instructions
```

**Pros:** Granular, composable, conflict-detectable  
**Cons:** Needs a smart assembler (possibly LLM-assisted), trait compatibility isn't guaranteed

### Open questions

1. **Can variants be truly independent?** Or do some strategies conflict (e.g., fixture-rich + mock-heavy may have different conftest philosophies)?
2. **Who decides the variant dimensions?** Auto-detected from the domain? User-specified? Discovered during evolution?
3. **Assembly validation** — how do we verify the composite skill works as well as (or better than) the sum of its parts?
4. **Granularity** — what's the right size for an atomic variant? A section of instructions? A script? A single behavioral pattern?
5. **Cross-family reuse** — can a great "mock strategy" variant be reused across pytest, unittest, and even jest skills?

---

## Agent Roles (v2.0 additions)

### Taxonomist (new in v2.0)

Dedicated agent responsible for classification and decomposition. Runs *before* evolution begins. Does NOT design challenges or judge fitness — purely structural analysis.

**Responsibilities:**
1. **Classify** — given a specialization string, assign Domain → Focus → Language. Uses the existing taxonomy as the primary guide; only creates new entries when nothing fits.
2. **Decompose** — identify the variant dimensions for this skill. Outputs a list of foundation variants and capability variants, each with a name, description, and focused evaluation criteria.
3. **Check existing** — query the registry for matching taxonomy entries, existing skill families, and reusable variants before creating anything new. Prevents taxonomy sprawl.
4. **Recommend reuse** — if high-fitness variants from other skill families could fit (e.g., a proven mock-strategy from the FastAPI test skill), flag them as candidates for assembly rather than re-evolving from scratch.

**Key principle: check what exists before creating anything new.** The Taxonomist is conservative — it prefers reusing proven taxonomy and variants over inventing new ones. New taxonomy entries require justification (nothing existing fits within reasonable semantic distance).

**Input:** specialization string + current taxonomy registry + existing variant catalog  
**Output:** classification (Domain/Focus/Language/Skill family) + variant decomposition (foundation + capabilities) + reuse recommendations

**Model:** Sonnet (classification is structured, not creative — doesn't need Opus)

### Updated agent roster (v2.0)

| Agent | Role | New in v2.0? |
|-------|------|-------------|
| Taxonomist | Classify, decompose, recommend reuse | Yes |
| Scientist | Generate focused challenges *per variant dimension* | Updated |
| Spawner | Create initial variant populations (narrower scope per variant) | Updated |
| Competitor | Run variant against focused challenge | Unchanged |
| Reviewer | Evaluate variant fitness (narrower, clearer signal) | Updated |
| Breeder | Mutate within a single variant dimension (horizontal) | Updated |
| Engineer | Compose variants + integration test + refine (vertical) | Yes |

**Breeder vs Engineer — clean separation:**
- **Breeder** operates *horizontally* — improving one variant over generations. Reads traces, mutates, produces next-gen variants. Never sees the full composite. Stays in its lane.
- **Engineer** operates *vertically* — picks best variant per dimension, composes them into a whole skill, runs an integration test round, and refines the seams. Owns the full compose → test → refine cycle.
- After assembly, if the composite needs tuning, that's the Engineer doing a refinement pass — NOT the Breeder doing molecular evolution. The Breeder only ever works within a single variant dimension.

---

## Variant Architecture

### Two-tier variant model

Not a full dependency graph — just two tiers:

**Foundation variants** — structural decisions other variants build on:
- Project structure / conventions
- Test setup / fixture strategy  
- Import patterns / tool configuration
- The "philosophy" of the skill

**Capability variants** — focused modules that plug into the foundation:
- Mock strategy (adapts to the foundation's fixture approach)
- Edge case generation
- Assertion patterns
- Output formatting
- Error handling style

**Evolution order:** Foundation first (or parallel with default foundation), then capabilities evolved *in the context of* the winning foundation. One level of dependency, not arbitrary depth.

### User experience: Default vs Advanced mode

**Default mode** — the decomposition is invisible. User describes what they want, gets a finished skill. The engine handles variant evolution and assembly behind the scenes.

**Advanced mode** — opt-in, not shown by default. Reveals the variant breakdown:

```
Foundation: fixture-rich (v3, fitness 0.92)     [swap ▾]
├── Mock strategy: auto-patch (v2, 0.88)        [swap ▾] [evolve]
├── Assertions: strict-typing (v4, 0.95)        [swap ▾] [evolve]  
├── Edge cases: hypothesis (v1, 0.78)           [swap ▾] [evolve]
└── Output: pytest-style (v2, 0.91)             [swap ▾] [evolve]

[Re-assemble]  [Export]
```

**Advanced user capabilities:**
- Swap any variant from alternatives (sorted by fitness within that dimension)
- Lock variants they like, re-evolve only the weak ones
- Pull high-fitness variants from other skill families (cross-pollination)
- Fork and evolve a single variant in isolation
- View the lineage/evolution history of each variant independently

**Upgrade path:** Users start in default mode → get a good skill → notice one aspect isn't right → flip to advanced → swap that one variant → done. No full re-evolution needed.

---

## Implementation Phases (Rough)

### Phase 1: Taxonomy & Registry
- Add Domain → Focus → Language → Skill hierarchy to the data model
- Auto-classify existing seeds and generated packages
- Registry UI: browse by taxonomy, filter by tags
- Candidate seeds flow into the taxonomy

### Phase 2: Variant-Aware Evolution  
- Decompose a skill into variant dimensions (Scientist identifies them)
- Run independent mini-evolutions per variant
- Focused challenge generation per variant dimension
- Focused judging per variant

### Phase 3: Assembly Engine
- Compose winning variants into a complete skill
- Integration test round on the assembled skill
- Conflict detection and resolution
- User can swap individual variants

### Phase 4: Cross-Family Reuse
- Variant marketplace — winning variants shared across skill families
- "This mock strategy works well in 12 different Python skill families"
- Transfer learning — proven patterns accelerate new skill evolution

---

## Relationship to v1.x

v2.0 is not a rewrite — it's an evolution of the platform (meta-evolution, if you will).

- v1.x molecular evolution still works and ships value today
- v2.0 can be introduced incrementally:
  1. First, add taxonomy to the existing system
  2. Then, allow focused single-variant evolution as an option
  3. Then, build the assembly engine
  4. Finally, make atomic evolution the default path
- The judging pipeline, competitor infrastructure, and breeder all carry forward
- The key new components: variant decomposer, focused challenge generator, assembler

---

*"Don't evolve the whole organism. Evolve the genes. Assemble the organism."*
