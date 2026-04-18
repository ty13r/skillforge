# Methodology

SKLD is an evolutionary breeding pipeline for Claude Agent Skills. A skill is a structured artifact — a `SKILL.md` instruction file plus optional scripts and reference documents — that specializes Claude on a particular task. The pipeline takes a description of a domain ("write pytest unit tests", "generate Phoenix LiveView modules") and produces a production-ready skill directory that beats a hand-authored seed on a controlled benchmark.

This page explains the mechanics of the current (v2.0) pipeline. `03-rigor-arc.md` explains how we arrived at this design; this page describes the design itself.

## The taxonomy

Every skill lives at a fixed address in a four-level hierarchy:

```
Domain → Focus → Language → Skill Family → Variant
Testing   Unit Tests  Python    pytest-generator   fixture-rich
                                                   mock-heavy
                                                   property-based
```

- **Domain / Focus / Language** are browsable, filterable coordinates for discovery.
- **Skill Family** is the grouping — a set of variants that share trigger conditions and domain.
- **Variant** is the atomic unit. Variants are what evolves. A skill as delivered is an *assembly* of variants.

This structure is what makes atomic evolution possible. Variants are decoupled enough to evolve independently, compatible enough to combine.

## Two tiers of variants

Not all variants are equal. Some set the overall approach; others plug into it.

**Foundation variants** commit to the structural philosophy of the skill — the fixture strategy, the project conventions, the overall workflow shape. They are evaluated first, and the winner defines the context for everything else.

**Capability variants** are focused modules that adapt to whatever foundation won. Mock strategy, assertion patterns, edge-case generation, output formatting. They evolve *in the context of* the winning foundation, so by the time they compete they are already compatible with it.

One level of dependency, not arbitrary depth. Foundation wins first, then capabilities compete against it. This is the minimum structure needed to keep atomic evolution coherent without falling into a full dependency graph.

## The agent roster

The pipeline is a set of specialist agents, each implemented as a Claude Agent Skill in its own right. None of them talks directly to another — all communication flows through the Evolution Engine.

| Agent | Role |
|-------|------|
| **Taxonomist** | Classifies the domain, decomposes it into variant dimensions, recommends reuse from existing taxonomy before creating anything new. |
| **Scientist** | Designs focused experiments — narrow challenges, one per variant dimension — with machine-readable evaluation rubrics. |
| **Spawner** | Creates the initial population of variants for each dimension. Narrower scope per dimension than a molecular spawn. |
| **Competitor** | Runs a variant against a focused challenge via the Claude Agent SDK, producing a full execution trace. |
| **Reviewer** | Evaluates fitness through multiple layers: deterministic code-quality checks, compilation gates, trace analysis, pairwise comparison, trait attribution. Owns the metrics catalog. |
| **Breeder** | Refines variants over generations through reflective mutation that reads traces to diagnose failures. Works within a single dimension — never sees the full skill. |
| **Engineer** | Assembles the winning foundation + capability variants into a composite skill, runs an integration test, and runs one refinement pass. |

The Breeder and Engineer divide the work cleanly: the Breeder works *horizontally* (improving one variant across generations), the Engineer works *vertically* (combining winners from different dimensions into one skill).

## Evolution modes

**Molecular mode (v1.x).** Evolves an entire SKILL.md as a monolith. Default: 5 population × 3 generations × 3 challenges = 45 competitor runs per family. Kept for simple skills where decomposition costs more than it helps.

**Atomic mode (v2.0).** Decomposes a skill into foundation + capability dimensions and evolves each independently. Default: 2 population × 2 generations × 1 challenge per dimension. Cheaper than molecular (~16 runs plus assembly) and produces cleaner per-dimension fitness signal.

**Auto.** The Taxonomist inspects the skill description and picks the mode. Complex skills → atomic. Simple skills → molecular.

## The atomic flow

```
User: "Phoenix LiveView skill optimized for API-driven pages"
                    │
                    ▼
            ┌──────────────┐
            │  Taxonomist  │ → Web > Reactive UI > Elixir > phoenix-liveview
            │              │ → Dimensions: foundation, mount-and-lifecycle,
            │              │   event-handling, stream-management, templating
            └──────┬───────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │Foundation│ │Foundation│ │Foundation│   ← 2 pop × 2 gen × 1 challenge
   │Variant A │ │Variant B │ │   …     │
   └────┬────┘ └─────────┘ └─────────┘
        │ winner
        ▼
        ┌──────────┬──────────┬──────────┐
        ▼          ▼          ▼          ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
   │Mount &  │ │ Event   │ │ Stream  │ │Template │   ← evolved in context
   │Lifecycle│ │Handling │ │ Mgmt    │ │          │     of winning foundation
   └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘
        │           │           │           │
        └─────┬─────┴───────────┴───────────┘
              ▼
       ┌──────────────┐
       │   Engineer   │ → Assemble foundation + capabilities
       │              │ → Integration test
       │              │ → Refinement pass if needed
       └──────┬───────┘
              │
              ▼
     ┌────────────────┐
     │Composite Skill │ → Production-ready, benchmark-tested
     │  (assembled)   │
     └────────────────┘
```

## Key techniques

Several techniques are not ours — they come from prior art (`01-prior-art.md`) and are applied here to a specific artifact.

**Reflective mutation via execution traces.** The Breeder reads the full SDK trace of a failed or weak run — tool calls, reasoning, outputs — and diagnoses *why* the variant underperformed before proposing a targeted mutation. Not "change a word and see if fitness improves." From GEPA (Actionable Side Information).

**Pareto-efficient selection.** Fitness is multi-dimensional (correctness, trigger accuracy, trace adherence, token efficiency, consistency). We maintain a Pareto front per generation rather than collapsing to a single scalar. A candidate that is best on one dimension and worst on another survives — it may carry a trait the balanced candidates lack. From GEPA.

**Joint multi-component mutation.** When mutating the instruction body of a SKILL.md, the Breeder also checks whether the frontmatter description, allowed-tools list, or supporting scripts need corresponding updates. Skills are structurally interdependent; changing one part often forces changes elsewhere. From Artemis.

**Persistent learning log.** Each EvolutionRun carries a growing list of observed lessons. The Breeder reads the log before every mutation so the population does not re-discover failures that were already explored. Mature findings are promoted to the public Claude Skills Bible for cross-run knowledge sharing. From Imbue (adapted for cross-run accumulation).

**Trace-based behavioral verification.** The Reviewer's behavioral layer inspects the trace to ask *what Claude did*, not just *what Claude produced*. Did it load the skill? Follow the workflow? Run the scripts? This catches failures that output-only scoring misses. From MLflow.

**Two-part description, pushy wording, hard constraints.** Skill descriptions are structurally constrained: under 250 characters, front-loaded with triggers, "pushy" (listing adjacent concepts and "even if they don't explicitly ask for…"). Hard constraints enforced by Spawner and Breeder. From Anthropic's skill-creator.

## Hard constraints enforced by the pipeline

Derived from `docs/skills-research.md`; these are non-negotiable and enforced programmatically by the Spawner and Breeder:

- **Description:** ≤ 250 characters; front-loaded capability + triggers; explicit exclusions ("NOT for X, Y, or Z"); evolves on a separate track from the instruction body.
- **Body:** ≤ 500 lines; numbered steps for workflows, bullets for options, prose for context; 2-3 diverse I/O examples mandatory (empirically 72% → 90% quality lift).
- **Resources:** scripts for deterministic operations (zero context cost at runtime); references one level deep from SKILL.md; all paths use `${CLAUDE_SKILL_DIR}`.
- **Structural:** name regex `^[a-z0-9]+(-[a-z0-9]+)*$`; matches directory name exactly.

## Recursive self-improvement

Every agent in the pipeline is itself a Claude Agent Skill (`.claude/skills/taxonomist/`, `.claude/skills/breeder/`, etc.). Those skills are themselves evolvable by this same pipeline.

Running the pipeline on itself — evolving the Breeder's skill against challenges that measure how effectively it produces high-fitness offspring — creates a recursive improvement loop. A better Breeder produces better variants; better variants eventually include a better Breeder skill; which produces still better variants. The ceiling is wherever the underlying model's capabilities plateau.

This is a capability we have built, not one we have exhaustively exercised. See `06-open-questions.md`.

---

*The methodology is a composition of techniques borrowed from prior art plus one genuinely new contribution — decomposing Agent Skills specifically into evolvable atomic variants and producing an installable Skill directory as the output artifact. The sum is the specific pipeline described above. How we got here — the scientific-rigor arc — is in `03-rigor-arc.md`.*
