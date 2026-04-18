# SKLD — Prior Art & Influences

## Overview

SKLD didn't emerge from a vacuum. The concept of applying evolutionary optimization to AI agent configurations has active research behind it. This document maps exactly what we borrowed, what we referenced, and what we built new — with rationale for each decision.

SKLD's thesis: the techniques proven by academic research and industry tools for evolving prompts and agent configs can be applied specifically to Claude Agent Skills, producing a tighter integration with the Claude ecosystem and a novel artifact (installable Skill directories) that nobody else outputs.

---

## 1. EvoPrompt (Tsinghua University / Microsoft, ICLR 2024)

**What it is:** The foundational academic paper connecting LLMs with evolutionary algorithms for prompt optimization. Uses genetic algorithms (GA) and differential evolution (DE) to evolve short task prompts, evaluated on 31 NLP benchmarks. Achieved up to 25% improvement over hand-engineered prompts on BIG-Bench Hard tasks.

**What we took:**
- The core concept: LLMs can serve as evolutionary operators — performing crossover and mutation on natural language, producing coherent offspring prompts that a traditional genetic algorithm couldn't generate.
- The population-based approach: maintain a pool of N candidates, evaluate all of them, select the fittest, breed the next generation. This is the skeleton of SKLD's evolution loop.

**What we didn't take:**
- Their evaluation method (fixed NLP benchmarks with known correct answers). SKLD generates evaluation challenges dynamically from a specialization description.
- Their optimization target (short classification prompts). SKLD evolves complete Skill directories — SKILL.md files, supporting scripts, reference documents — a much richer artifact.
- Their mutation operators (template-based DE/GA operators). SKLD uses reflective mutation informed by execution traces (from GEPA, see below).

**Why it matters:** EvoPrompt proved the fundamental thesis that evolutionary optimization of natural language prompts works and outperforms hand-tuning. Without this paper, the entire approach would be speculative.

**Citation:** Guo et al., "Connecting Large Language Models with Evolutionary Algorithms Yields Powerful Prompt Optimizers," ICLR 2024. [arXiv:2309.08532](https://arxiv.org/abs/2309.08532)

---

## 2. GEPA (UC Berkeley, 2025-2026)

**What it is:** A general-purpose framework for optimizing any system with textual parameters — prompts, code, agent architectures, configurations — using LLM-based reflection and Pareto-efficient evolutionary search. Published at ICLR 2026 and ECIR 2026 workshops. Outperforms DSPy and TextGrad. Endorsed by Shopify CEO Tobi Lutke as "severely under-hyped."

**What we took:**

*Reflective mutation via Actionable Side Information (ASI):*
This is GEPA's biggest contribution and the single most important technique we adopted. Instead of random mutation ("change a word, see if fitness improves"), the mutating LLM reads the full execution trace — error messages, tool calls, reasoning logs — and *diagnoses* why a candidate failed before proposing a targeted fix. In SKLD, the Breeder agent reads competitor execution traces from the Agent SDK and produces diagnostic mutations: "The instruction to 'always write tests first' caused the Skill to waste 4 turns on trivial scaffolding before understanding the problem. Mutation: rewrite as 'write tests after implementing core logic, then iterate.'"

*Pareto-efficient selection:*
Instead of collapsing all fitness dimensions into a single score (which destroys information), GEPA maintains a Pareto front across multiple objectives. A candidate that's best on correctness but worst on token efficiency is Pareto-optimal — it survives because it might contribute traits the "balanced" candidates are missing. SKLD maintains a Pareto front across correctness, trigger accuracy, instruction adherence, token efficiency, and consistency.

*Multi-parent merge:*
GEPA supports combining strengths from multiple Pareto-optimal candidates excelling on different objectives. SKLD's Breeder performs 2-3 parent crossover informed by which parent excelled on which dimension.

**What we didn't take:**
- GEPA's adapter interface. GEPA is a general-purpose framework requiring custom adapters for each optimization target. SKLD is purpose-built for Claude Agent Skills with native integration into the Skills ecosystem.
- GEPA's optimization scope. GEPA optimizes arbitrary text parameters. SKLD optimizes a specific, structured artifact (SKILL.md + scripts + references) with known constraints (250-char description limit, 500-line body ceiling, etc.).

**Why it matters:** GEPA proved that trace-informed mutation dramatically outperforms random mutation, and that Pareto selection preserves diversity better than single-score ranking. These are the two techniques that make SKLD's evolution genuinely intelligent rather than a random walk.

**Citation:** Agrawal et al., "GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning," 2025. [GitHub](https://github.com/gepa-ai/gepa)

---

## 3. Artemis (TurinTech, 2025-2026)

**What it is:** An enterprise evolutionary optimization platform for LLM-based agent configurations. Treats agents as black boxes and jointly optimizes multiple configurable components — prompts, tool descriptions, model parameters, execution settings — while capturing their interdependencies. Demonstrated 9.3% to 36.9% improvements across four different agent systems.

**What we took:**

*Joint multi-component optimization:*
Artemis's key insight is that optimizing prompts in isolation misses critical interdependencies with tool configs and parameters. A mutation to an agent's prompt might require a corresponding mutation to its tool descriptions. SKLD applies this to Skills: a mutation to the SKILL.md instruction body might require a corresponding change to the frontmatter description (for trigger accuracy), the allowed-tools list (for capability alignment), or the supporting scripts (for consistency). The Breeder performs "joint mutation" — when changing one component, it checks whether interdependent components need updates.

*Component discovery:*
Artemis automatically analyzes a codebase to identify optimizable components. SKLD's trait extraction — decomposing a SKILL.md into discrete, evolvable traits — is a similar concept applied to the Skill format specifically.

**What we didn't take:**
- Artemis's no-code interface and enterprise packaging. SKLD is developer-focused.
- Artemis's black-box approach. SKLD has deep knowledge of the Skill format and exploits its structure (frontmatter vs. body vs. scripts vs. references) for more targeted evolution.

**Why it matters:** Artemis proved that joint optimization across interdependent components produces significantly better results than optimizing any single component alone. For Skills, this means evolving the description, instructions, and scripts together rather than independently.

**Citation:** TurinTech, "Evolving Excellence: Automated Optimization of LLM-based Agents," 2025. [arXiv:2512.09108](https://arxiv.org/pdf/2512.09108)

---

## 4. Imbue's Darwinian Evolver (Imbue, February 2026)

**What it is:** A general-purpose evolutionary optimization framework inspired by Sakana.ai's Darwin Gödel Machines. Applied to code optimization, prompt engineering, and agentic system development. Emphasizes that the evolution process is "in principle, open-ended" — there's no inherent limit to improvement given sufficient time.

**What we took:**

*Multi-parent crossover:*
Instead of combining exactly 2 parents (as in traditional genetic algorithms), Imbue's evolver samples multiple parents for a single mutation, prompting the LLM to combine the best ideas from each into a unified offspring. SKLD's Breeder supports 2-3 parent crossover, selecting parents that are Pareto-optimal on different objectives and combining their complementary strengths.

*Learning log:*
This is Imbue's alternative to crossover that works within a lineage. The learning log accumulates discoveries and lessons across the entire population's history and injects them into every mutation prompt. This prevents the population from rediscovering the same failures that were already explored and discarded in earlier generations. SKLD maintains a persistent learning log on each EvolutionRun that the Breeder reads before proposing any mutation. The log entries are also published to the Claude Skills Bible for cross-run knowledge sharing.

**What we didn't take:**
- Imbue's fitness scoring approach (data-set-based evaluation with known correct values). SKLD uses a multi-layered judging pipeline with both deterministic and LLM-assisted evaluation.
- Imbue's focus on code optimization. SKLD optimizes a specific artifact (Agent Skills) with its own format, constraints, and ecosystem.

**Why it matters:** The learning log is what makes SKLD's evolution accumulate knowledge rather than restart from scratch. Without it, each generation's Breeder would be blind to lessons already learned, potentially re-introducing mutations that were already proven harmful.

**Citation:** Imbue, "LLM-based Evolution as a Universal Optimizer," February 2026. [Blog post](https://imbue.com/research/2026-02-27-darwinian-evolver/)

---

## 5. singularity-claude (Community project, March 2026)

**What it is:** A self-evolving skill engine for Claude Code. Adds a recursive improvement loop: create a Skill → score it on 5 dimensions → if score drops below threshold, auto-repair → if score exceeds threshold after 5+ runs, crystallize (lock the version). Uses a Haiku assessor agent for lightweight scoring.

**What we took:**

*Maturity lifecycle:*
singularity-claude's progression of draft → tested → hardened → crystallized is a clean model for tracking Skill quality over time. SKLD assigns maturity labels to evolved Skills based on how many generations they've survived, their consistency scores, and whether their traits have been confirmed across multiple independent runs.

**What we didn't take:**
- Single-Skill hill climbing. singularity-claude improves one Skill at a time through iterative score → repair cycles. This is effective but can get stuck in local optima. SKLD uses population-based competition — 5+ Skills competing simultaneously — which explores a much larger solution space and discovers strategies that hill climbing would never find.
- Haiku-based scoring. singularity-claude uses a lightweight model for scoring. SKLD uses a multi-layered judging pipeline with deterministic checks, pairwise comparisons, and trace-based analysis for more rigorous evaluation.

**Why it matters:** singularity-claude validated that automated Skill improvement is viable and that Claude can meaningfully evaluate and improve its own Skills. It also introduced the practical concept that Skills should carry quality metadata — not just content. SKLD extends this from iterative repair to competitive evolution.

**Citation:** [GitHub](https://github.com/Shmayro/singularity-claude)

---

## 6. Anthropic's skill-creator (Anthropic, updated March 2026)

**What it is:** Anthropic's official tool for creating, evaluating, and iteratively improving Agent Skills. Updated in March 2026 with evals, benchmarking, A/B comparator agents, and description optimization. The skill-creator includes a description optimization pipeline (`run_loop.py`) that uses a 60/40 train/test split to tune trigger descriptions.

**What we took:**

*Trigger accuracy as a first-class fitness dimension:*
Anthropic's insight that Skills have two reliability problems — activation reliability (does the Skill trigger when it should?) and execution reliability (does it produce good output when triggered?) — directly shaped SKLD's judging pipeline. Our L2 layer specifically measures trigger precision and recall using the same methodology: generate should-trigger and should-not-trigger queries, run each 3 times, measure activation rates.

*The description optimization methodology:*
The skill-creator's `run_loop.py` implements a mini ML training loop: generate eval queries, split 60/40 train/test, evaluate current description, propose improvements, iterate up to 5 times, select winner by test score (not training score) to avoid overfitting. SKLD's L2 trigger accuracy layer follows this same evaluation protocol.

*The "pushy description" principle:*
Anthropic's documented observation that Claude undertriggers Skills, and their recommendation to make descriptions "a little pushy" by listing adjacent concepts and including "even if they don't explicitly ask for [skill name]." This is encoded as a hard constraint in SKLD's Spawner and Breeder.

*A/B comparator methodology:*
The skill-creator's blind A/B comparison — a separate Claude instance reviews both outputs without knowing which came from which Skill — informed SKLD's L4 pairwise comparative ranking layer.

**What we didn't take:**
- The iterative refinement model. skill-creator improves one Skill through guided iteration with human feedback. SKLD automates this through population-based competition with no human in the loop.
- The qualitative evaluation approach. skill-creator relies heavily on human review of outputs. SKLD uses automated multi-layered evaluation (deterministic checks, trigger testing, trace analysis, pairwise comparison, trait attribution).

**Why it matters:** Anthropic built the evaluation primitives — trigger testing, A/B comparison, description optimization — that SKLD composes into an automated evolutionary pipeline. We're standing on their testing infrastructure.

**Citation:** Anthropic, "Improving skill-creator: Test, measure, and refine Agent Skills," March 2026. [Blog](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills); [Source](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md)

---

## 7. MLflow Trace-Based Skill Evaluation (MLflow, March 2026)

**What it is:** A methodology for testing Claude Code Skills using MLflow tracing. Claude's execution is traced (`mlflow.anthropic.autolog()`), then LLM judges evaluate behavioral questions against the traces. The key insight: you can't assert `output == expected_output` for LLM behavior — you need to observe what Claude *did* (which tools it called, what steps it took, whether it made the right judgment calls).

**What we took:**

*Trace-based behavioral verification:*
SKLD's L3 judging layer reads the full execution trace from the Agent SDK and verifies: Did Claude actually load the Skill? Which instructions were followed? Which were ignored? Were supporting scripts executed? This is more rigorous than output-only evaluation because it answers *how* the result was achieved, not just *what* the result was.

*Judge → refine loop:*
MLflow's pattern of using trace-based judges to identify gaps, then having Claude read the traces and make targeted SKILL.md edits, directly informed SKLD's connection between the judging pipeline (L3/L5) and the Breeder's reflective mutation. The trait attribution layer (L5) identifies which instructions correlated with success or failure using trace evidence, and the Breeder reads those diagnostics to make targeted changes.

**What we didn't take:**
- MLflow as the infrastructure. SKLD uses its own trace collection from the Agent SDK rather than depending on MLflow's tracing library.
- Rule-based judges. MLflow recommends a mix of LLM judges and rule-based judges for deterministic checks. SKLD separates these into distinct layers (L1 deterministic, L3-L5 LLM-assisted).

**Why it matters:** MLflow proved that execution traces contain the information needed to diagnose *why* a Skill succeeds or fails, not just *whether* it does. This is what makes SKLD's trait attribution possible — without trace data, we'd be guessing at which instructions matter.

**Citation:** MLflow, "Testing and Refining Claude Code Skills with MLflow," March 2026. [Blog](https://mlflow.org/blog/evaluating-skills-mlflow)

---

## What SKLD Built New

These are the contributions that don't exist in any prior art:

**1. Population-based evolution of Agent Skills.**
Everyone else does either single-candidate hill climbing (singularity-claude, Anthropic skill-creator) or generic prompt/config optimization (GEPA, EvoPrompt, Artemis). Nobody breeds competing populations of SKILL.md files with supporting scripts and references.

**2. Trait-level attribution.**
No existing tool decomposes an agent configuration into discrete behavioral traits and attributes fitness scores to individual instructions using execution trace evidence. GEPA uses traces for reflection, but at the whole-candidate level, not the trait level.

**3. The Claude Skills Bible.**
No existing tool accumulates evolutionary learnings into a persistent, public knowledge base. The learning log concept from Imbue is per-run. SKLD promotes confirmed findings across runs into a growing repository of empirically-proven Skill authoring patterns.

**4. Meta-mode: universal Skill-authoring pattern evolution.**
Nobody is evolving patterns that make *any Skill better* and testing for cross-domain generalization. Meta-mode evaluates candidate Meta-Skills by applying them to generate domain Skills across 3+ random domains and measuring downstream fitness.

**5. Skills-native output.**
All other tools output optimized prompts, configs, or code. SKLD outputs installable Agent Skill directories that slot directly into Claude Code, the Agent SDK, or the Skills API with zero friction. The output artifact is native to the Claude ecosystem.

**6. Integrated judging pipeline (6 layers).**
No existing tool combines deterministic checks, trigger accuracy testing, trace-based behavioral analysis, pairwise comparative ranking with Pareto selection, trait attribution with diagnostics, and consistency verification into a single evaluation pipeline. Each layer addresses a specific failure mode that the others miss.

---

## Summary Table

| Source | What We Took | What's Different in SKLD |
|--------|-------------|------------------------|
| **EvoPrompt** | LLMs as evolutionary operators; population-based selection | Evolves Skills (not short prompts); dynamic challenges (not fixed benchmarks) |
| **GEPA** | Reflective mutation via traces; Pareto selection; multi-parent merge | Applied to Skills specifically; trait-level attribution; Skills-native output |
| **Artemis** | Joint multi-component optimization; component discovery | Deep Skill format knowledge; not black-box |
| **Imbue** | Multi-parent crossover; persistent learning log | Learning log feeds into public Bible; cross-run knowledge accumulation |
| **singularity-claude** | Maturity lifecycle (draft → crystallized) | Population competition vs. single-Skill hill climbing |
| **Anthropic skill-creator** | Trigger accuracy testing; description optimization; A/B comparison; "pushy" descriptions | Automated pipeline vs. human-guided iteration; multi-layered vs. single evaluation |
| **MLflow** | Trace-based behavioral verification; judge → refine loop | Integrated into evolutionary pipeline; trait-level attribution from traces |

---

*SKLD stands on the shoulders of serious research. What makes it novel is the specific combination: applying proven evolutionary techniques to a specific artifact (Agent Skills) with a specific ecosystem (Claude), producing both an installable output and a growing knowledge base. The whole is greater than the sum of its parts.*
