# How SKLD Works

**SKLD** — **S**kill **K**inetics through **L**ayered **D**arwinism

## What It Is

SKLD is an evolutionary breeding platform for AI agent skills. It takes a description of what you want an AI agent to be good at — "write pytest unit tests" or "review pull requests for security issues" — and breeds a population of competing skill packages through tournament selection until the best one emerges.

A "skill" in this context is a structured instruction set that tells Claude (Anthropic's AI) how to behave when it encounters a specific type of task. Think of it as a specialized playbook: when a user says "write tests for this code," the skill tells Claude exactly how to approach it — which patterns to use, what scripts to run, what references to consult, what mistakes to avoid.

SKLD doesn't write these skills by hand. It evolves them.

## The Problem It Solves

Writing a great AI skill is surprisingly hard. You need to get the trigger conditions right (when should this skill activate?), the instructions right (what steps should the agent follow?), the supporting scripts right (what deterministic work can be offloaded from the AI?), and the reference material right (what domain knowledge does the agent need on demand?). A small change in any of these can dramatically affect quality.

Humans are bad at optimizing across all these dimensions simultaneously. We tend to focus on one aspect and neglect others. Evolution doesn't have this bias — it tests everything together and lets fitness determine what survives.

## How Evolution Works (v1.x)

The current system evolves skills as whole units:

1. **You describe the domain.** "Generate pytest unit tests with fixtures and mocked dependencies."

2. **A Scientist agent designs experiments.** It creates challenges that test whether a skill actually works — specific coding tasks with measurable success criteria.

3. **A Spawner agent creates a population.** Five diverse skill variants, each taking a different approach to the same domain. One might emphasize fixture-heavy testing, another might focus on property-based testing.

4. **Each variant competes.** An AI agent loads the skill and attempts to solve every challenge. Its work is recorded — what tools it used, what code it wrote, whether it followed the skill's instructions.

5. **A Reviewer evaluates fitness.** Five layers of judgment:
   - L1: Did the code compile? Do tests pass? (deterministic, no AI needed)
   - L2: Does the skill activate on the right triggers? (precision/recall)
   - L3: Did the agent actually follow the skill's instructions? (trace analysis)
   - L4: How does this variant compare to others? (pairwise ranking)
   - L5: Which specific instructions contributed to fitness? (trait attribution)

6. **A Breeder creates the next generation.** It reads the execution traces — not just the scores — to understand *why* things worked or failed. Then it mutates the best variants, crosses over winning traits, and produces the next population.

7. **Repeat for multiple generations.** Each generation is better than the last because selection pressure eliminates weak strategies and amplifies strong ones.

The output is a production-ready skill package: a SKILL.md file with instructions, scripts for deterministic operations, and reference documents — all battle-tested through competition.

## What Changes in v2.0: Atomic Evolution

### The Insight

v1.x evolves entire skills as monoliths — like trying to breed a better animal by mutating every gene at once. It works, but it's slow, expensive, and the fitness signal is noisy. When a skill scores well, you can't tell if it's because of the fixture strategy, the mock patterns, or the assertion style.

v2.0 breaks skills into **variants** — focused, independently-evolvable atomic units. Each variant addresses one specific dimension of the skill: how to set up test fixtures, how to mock dependencies, how to generate edge cases. These variants evolve independently under focused selection pressure, then get assembled into a composite skill.

This is how biological evolution actually works. Genes evolve independently. Organisms are assemblies of fit genes.

### The Taxonomy

Every skill lives in a classification hierarchy:

```
Domain    →  Focus        →  Language  →  Skill Family      →  Variants
Testing      Unit Tests      Python       pytest-generator      fixture-rich
                                                                mock-heavy
                                                                property-based
                                                                snapshot
```

The first three levels (Domain, Focus, Language) are the address. The Skill Family is the grouping. The Variants are the atomic units that get evolved and assembled.

### Two Tiers of Variants

Not all variants are equal. Some are structural decisions that everything else depends on:

**Foundation variants** set the philosophy — the fixture strategy, the project conventions, the overall approach. Other variants adapt to whatever foundation wins.

**Capability variants** are focused modules that plug into the foundation — mock patterns, assertion style, edge case generation, output formatting. They're evolved *in the context of* the winning foundation, so they're already compatible.

### The Agent Team

Six specialized AI agents collaborate in the pipeline:

| Agent | Role |
|-------|------|
| **Taxonomist** | Classifies the domain, decomposes it into variant dimensions. Checks what already exists before creating anything new. |
| **Scientist** | Designs focused experiments — one narrow challenge per variant dimension. |
| **Spawner** | Creates the initial population of variants for each dimension. |
| **Breeder** | Refines variants over generations through selective mutation. Works within a single dimension — never sees the whole picture. |
| **Reviewer** | Evaluates fitness through 5 layers of judgment (deterministic checks, trigger accuracy, trace analysis, comparative ranking, trait attribution). |
| **Engineer** | Assembles the winning variants into a composite skill. Runs integration tests. Refines the seams. |

The Breeder and Engineer have a clean separation: the Breeder works *horizontally* (improving one variant over generations), the Engineer works *vertically* (combining the best variants from different dimensions into one skill).

### The Flow

```
User: "I want a pytest skill optimized for API testing"
                    │
                    ▼
            ┌──────────────┐
            │  Taxonomist   │ → Testing > Unit Tests > Python > pytest-generator
            │               │ → Dimensions: foundation, mock-strategy, 
            │               │   assertion-style, edge-case-generation
            └──────┬───────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │Foundation│ │Foundation│ │Foundation│    ← 2 pop × 2 gen × 1 challenge
   │Variant A │ │Variant B │ │   ...   │
   └────┬────┘ └─────────┘ └─────────┘
        │ winner
        ▼
        ┌──────────┬──────────┬──────────┐
        ▼          ▼          ▼          ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
   │  Mock    │ │ Assert  │ │  Edge   │ │   ...   │  ← evolved in context
   │ Strategy │ │  Style  │ │  Cases  │ │         │    of winning foundation
   └────┬────┘ └────┬────┘ └────┬────┘ └─────────┘
        │           │           │
        └─────┬─────┘───────────┘
              ▼
       ┌──────────────┐
       │   Engineer    │ → Assembles foundation + capabilities
       │               │ → Integration test
       │               │ → Refinement pass if needed
       └──────┬───────┘
              │
              ▼
     ┌────────────────┐
     │ Composite Skill │ → Production-ready, battle-tested
     │  (assembled)    │
     └────────────────┘
```

### Why This Is Better

| | v1.x (Monolithic) | v2.0 (Atomic) |
|---|---|---|
| What evolves | Entire skill as one blob | Individual variant dimensions |
| Mutation surface | Huge — everything changes at once | Focused — one thing at a time |
| Fitness signal | Averaged across dimensions | Clear per-dimension |
| Cost | ~$7, ~54 minutes | ~$3-4, ~20-30 minutes |
| User control | Take it or leave it | Swap individual variants |
| Reusability | None — each skill is unique | Winning variants reusable across families |

### Default vs Advanced Mode

Most users never see the variant decomposition. They describe what they want, get a finished skill. The atomic evolution happens behind the scenes.

Power users can toggle Advanced Mode to see the variant breakdown — which foundation won, which capability variants were selected, their individual fitness scores. They can swap a weak variant for a better one, re-evolve a single dimension, or pull a proven variant from a completely different skill family.

## The Recursive Self-Improvement Loop

Here's where it gets interesting.

Each agent in the pipeline (Taxonomist, Scientist, Spawner, Breeder, Reviewer, Engineer) is itself powered by a Claude Agent Skill. The Taxonomist has a skill that tells it how to classify domains. The Scientist has a skill that tells it how to design experiments. The Engineer has a skill that tells it how to assemble variants.

These skills are evolvable by the very platform they power.

```
┌─────────────────────────────────────────────┐
│              SKLD Pipeline             │
│                                              │
│  Taxonomist ─→ Scientist ─→ Spawner         │
│       │                        │             │
│       │    Competitor ←────────┘             │
│       │        │                             │
│       │    Reviewer ─→ Breeder ─→ Engineer   │
│       │                             │        │
│       └─────────────────────────────┘        │
│                                              │
│  Each agent runs on a Claude Agent Skill     │
│  that was EVOLVED BY THIS SAME PIPELINE      │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
          ┌────────────────┐
          │   Meta-Loop    │
          │                │
          │  1. Run pipeline with current agent skills
          │  2. Measure: speed, cost, output fitness
          │  3. Evolve the agent skills themselves
          │  4. Run pipeline again with improved agents
          │  5. Goto 1
          └────────────────┘
```

The Taxonomist gets better at classifying. The Scientist designs sharper experiments. The Breeder makes smarter mutations. The Engineer produces tighter assemblies. Each cycle, the entire pipeline improves — and the improved pipeline produces better improvements.

This is recursive self-improvement applied to AI skill authoring. The system bootstraps its own optimization.

## Implications

### For developers

Instead of spending hours crafting a perfect skill prompt, describe what you want and let evolution find the optimal strategy. The resulting skill will have been tested against real challenges, evaluated across multiple dimensions, and refined through competition. It will almost certainly be better than what you'd write by hand.

### For the skill ecosystem

Winning variants are reusable. A great mock strategy evolved for pytest might work for unittest, or even for jest tests in a completely different language. The variant catalog becomes a library of proven strategies that accelerate future evolution — new skills don't start from zero, they start from the best existing components.

### For AI capabilities

The recursive self-improvement loop means the platform gets better at making things better. Each generation of agent skills produces a more capable pipeline, which produces better agent skills, which produces an even more capable pipeline. The ceiling is wherever the underlying model's capabilities plateau — but within that ceiling, SKLD finds the optimal configuration automatically.

### The broader question

SKLD is an experiment in whether evolutionary pressure, applied systematically to AI instruction sets, can produce capabilities that exceed what human prompt engineers can design. Early results suggest yes — the tournament selection process discovers strategies that humans wouldn't think to try, and the multi-layer fitness evaluation catches failure modes that humans wouldn't notice.

The atomic variant architecture in v2.0 pushes this further by making evolution more precise, cheaper, and composable. And the recursive self-improvement loop means the system's ability to evolve skills is itself subject to evolution.

We're building a machine that builds better machines that build better machines.

---

*SKLD is open source at [github.com/ty13r/skillforge](https://github.com/ty13r/skillforge).*
