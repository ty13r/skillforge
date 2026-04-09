# SkillForge — Evolve Agent Skills Through Natural Selection

## One-liner

Evolve Agent Skills through natural selection. Two modes: **Domain mode** breeds specialist Skills (Elixir, testing, security review). **Meta mode** breeds universal Skill-authoring patterns that make *any* Skill better. Both export production-ready Skills you install directly into Claude Code, the Agent SDK, or the Skills API.

---

## The Problem

Writing good Agent Skills is hard. You write a SKILL.md, test it manually, tweak it, test again. It's artisanal prompt engineering with no systematic feedback loop. The result: mediocre Skills tuned by gut feel, with no way to know if a different approach would perform better.

Meanwhile, the Skill format is powerful — it packages instructions, scripts, references, and metadata into composable capabilities. But the authoring process doesn't match the format's potential.

## The Solution

SkillForge applies evolutionary pressure to Skill populations in two modes:

### Domain Mode
You describe a specialization ("Elixir LiveView expert"). SkillForge:
1. Auto-generates evaluation challenges from your description
2. Spawns a diverse population of candidate Skills
3. Evaluates each Skill against the challenges using the Claude Agent SDK
4. A multi-layered judging system scores results (deterministic checks + comparative ranking + trait attribution)
5. A Breeder agent recombines the best-performing Skills' traits and introduces mutations
6. Repeats for N generations

The output: a proven, portable domain-specialist Skill.

### Meta Mode
Instead of optimizing *what* a Skill knows, Meta mode optimizes *how Skills are written*. It evolves universal Skill-authoring patterns — optimal structure, progressive disclosure strategy, instruction phrasing, example density, anti-pattern formatting — that make any Skill more effective.

The meta evaluation is harder: each candidate meta-pattern is tested by applying it to generate Skills across 3+ random domains, then measuring whether the resulting Skills perform better than ones written without the pattern. This tests generalization, not domain expertise.

The output: a **Skill Meta-Skill** — a Skill whose job is to help author better Skills. Load it when writing any new Skill and it coaches Claude on structure, phrasing, and patterns that have been empirically proven to work.

---

## Prior Art & Differentiation

SkillForge builds on proven techniques from the evolutionary prompt optimization space while targeting a novel artifact (Agent Skills) with novel evaluation methods.

### What we learn from

| Project | Key Insight We Adopt | What SkillForge Adds |
|---|---|---|
| **GEPA** (Berkeley) | Reflective mutation via execution traces ("Actionable Side Information"); Pareto-efficient selection across multiple objectives | Applied to Skills (not prompts); trait attribution layer; learning log that accumulates across generations |
| **EvoPrompt** (ICLR '24) | LLMs as evolutionary operators — use the model itself to do crossover and mutation on natural language | Multi-parent crossover (2-3 parents); joint mutation of interdependent Skill components |
| **Artemis** (TurinTech) | Joint optimization of prompts + tools + parameters as interdependent components | Extended to full Skill directories: frontmatter + instructions + scripts + references as a holistic genome |
| **singularity-claude** | Score → repair → harden → crystallize maturity lifecycle for Claude Skills | Population-based competition (not single-Skill hill climbing); maturity label on evolved outputs |
| **Anthropic skill-creator** | Trigger accuracy testing; A/B comparisons between Skill versions; description optimization | Trigger accuracy as a first-class fitness dimension in the evolutionary loop, not a separate manual step |
| **MLflow Skill evals** | Trace-based behavioral verification — did Claude load the Skill, follow instructions, use scripts? | Trace analysis feeds directly into trait attribution and reflective mutation |
| **Imbue Darwinian Evolver** | Multi-parent crossover; learning log that prevents rediscovering failed approaches | Learning log is persistent across generations and injected into every Breeder prompt |

### What nobody is doing

1. **Population-based evolution of Agent Skills.** Everything is either single-candidate hill-climbing or generic prompt optimization. Nobody breeds competing populations of SKILL.md files.
2. **Trait-level attribution.** Existing tools optimize the whole prompt/config as a blob. Nobody decomposes a Skill into discrete traits and attributes fitness to individual instructions using execution trace evidence.
3. **Meta-Skill evolution.** Nobody's evolving universal Skill-authoring patterns and testing for cross-domain generalization.
4. **Skills-native output.** Other tools output optimized prompts/configs. SkillForge outputs installable Skill directories that slot into the Claude ecosystem (Claude Code, Agent SDK, Skills API) with zero friction.

---

## Core Concepts

### Specialization

A user-defined description of what the evolved Skill should be great at.

Examples:
- "An Elixir Skill that writes idiomatic Phoenix LiveView code with proper OTP patterns, comprehensive tests, and LiveView Native considerations"
- "A test engineering Skill that writes edge-case-heavy test suites with property-based testing, mutation testing awareness, and clear failure messages"
- "A security review Skill that audits Python web applications for OWASP Top 10 vulnerabilities, writes proof-of-concept exploit tests, and produces actionable remediation reports"
- "An API design Skill that produces clean RESTful interfaces with proper error handling, pagination, versioning, and OpenAPI specs"

### Skill Genome

A Skill's full "DNA" — the complete contents of its Skill directory:

```
evolved-skill/
├── SKILL.md              # Core instructions + YAML frontmatter
├── scripts/              # Optional helper scripts the Skill references
│   └── validate.py
├── references/           # Optional reference docs
│   └── patterns.md
└── assets/               # Optional templates, schemas, etc.
    └── template.yaml
```

The evolvable components:
- **Frontmatter** — name, description (trigger conditions), allowed-tools
- **Instructions** — the markdown body of SKILL.md (approach, patterns, constraints, examples)
- **Behavioral traits** — discrete, extractable characteristics ("always writes tests first", "uses function components over class components", "prefers explicit error types over generic exceptions")
- **Meta-strategy** — how the Skill tells Claude to approach problems (plan-first vs. dive-in, top-down vs. bottom-up, TDD vs. implement-then-test)
- **Supporting files** — scripts, references, templates that the Skill bundles
- **Progressive disclosure strategy** — what goes in SKILL.md vs. what gets split into reference files Claude loads on demand

### Skill Authoring Constraints (Empirically Derived)

These constraints are derived from the Deep Research report (`docs/skills-research.md`) and must be enforced by both the Spawner (gen 0 creation) and the Breeder (mutation/crossover). They represent hard limits discovered through Anthropic's own testing, community audits, and production skill analysis.

**Description constraints (Level 1 — routing):**
- Front-load capability + trigger conditions within **250 characters** (hard truncation in skill listing)
- Always use the "pushy" pattern: list adjacent concepts + "even if they don't explicitly ask for [skill name]"
- Include explicit exclusion clauses: "NOT for [X], [Y], or [Z]"
- Two-part structure: what the skill does + when to use it ("Use when...")
- Description and instruction body evolve **separately** — they serve fundamentally different functions (routing vs. execution)

**Instruction constraints (Level 2 — execution):**
- SKILL.md body must stay under **500 lines** (~5,000 words)
- Total instruction budget across all loaded context is ~150-200; Claude's system prompt consumes ~50
- Numbered steps for ordered workflows, bullets for options, prose for context
- **2-3 diverse input/output examples mandatory** — empirically proven to improve quality from 72% to 90%
- Headers (H2/H3) are structural — Claude relies on formatting hierarchy to parse instructions
- Prefer goals/constraints over step-by-step prescriptions for high-freedom tasks
- Don't teach Claude things it already knows — run tasks without the skill first, then close specific gaps

**Resource constraints (Level 3 — on-demand):**
- Scripts for deterministic operations — **script code never enters context window**, only stdout/stderr
- Reference files must be **one level deep** from SKILL.md (Claude only previews deeper nesting with head -100)
- Reference files over 100 lines should include a table of contents
- If tests show Claude repeatedly writing the same helper script, **bundle it** — regenerating costs tokens, bundling costs zero
- Use `${CLAUDE_SKILL_DIR}` for all paths (never hardcode)
- Validate all reference paths in CI — community audit found **73% of skill setups broken**, primarily from missing references

**Structural constraints:**
- Name must match directory name exactly: `^[a-z0-9]+(-[a-z0-9]+)*$`
- `allowed-tools` frontmatter is **ignored by the Agent SDK** — tool access controlled via ClaudeAgentOptions only
- Max 8 skills per API request, max 30 MB per skill upload
- Skills require code execution tool as a hard dependency
- Skills are not eligible for Zero Data Retention (ZDR)

**The Golden Template** (from research, used as gen 0 seed):
All gen 0 Skills must follow the structure defined in `docs/golden-template.md`. The Spawner varies content while preserving structure. The Breeder may evolve structure only when trait attribution provides evidence that structural changes improve fitness.

### Challenge

A concrete task the Skill must handle well, auto-generated by the Challenge Designer agent. Each challenge includes:

- **Task prompt** — what to ask Claude while the Skill is loaded ("Build a GenServer that manages a rate limiter with sliding window")
- **Evaluation criteria** — weighted dimensions (correctness: 0.4, idiomaticity: 0.3, robustness: 0.2, simplicity: 0.1)
- **Difficulty tier** — easy / medium / hard (diverse difficulty reveals different Skill weaknesses)
- **Verification method** — how to check the output (run tests, static analysis, judge review, or combination)
- **Gold standard hints** — what a great solution looks like (helps the Judge calibrate)

### Generation

One cycle of: compete → evaluate → select → breed → mutate.

### Lineage

A full ancestry tree tracking:
- Which SKILL.md sections survived across generations
- Which traits were discarded and why
- Which mutations proved beneficial
- Which supporting files were added/removed/modified
- Fitness trajectory per trait

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     SkillForge API                        │
│                   (FastAPI + WebSocket)                    │
├──────────────────────────────────────────────────────────┤
│                                                            │
│  ┌────────────────┐       ┌───────────────────────────┐   │
│  │  Challenge      │       │   Evolution Engine         │   │
│  │  Designer Agent │       │                           │   │
│  │                │       │   for each generation:     │   │
│  │  Analyzes the   │       │     1. Write Skills to     │   │
│  │  specialization │       │        temp directories    │   │
│  │  and generates  │       │     2. Run Competitors     │   │
│  │  graded eval    │       │        via Agent SDK       │   │
│  │  challenges     │       │        (Skill loaded)      │   │
│  └────────────────┘       │     3. Judge scores         │   │
│                            │     4. Breeder evolves      │   │
│  ┌────────────────┐       │     5. Repeat               │   │
│  │  Lineage Store  │       └───────────────────────────┘   │
│  │  (SQLite)       │                                       │
│  │                │       ┌───────────────────────────┐   │
│  │  Full genome    │       │   Export Engine             │   │
│  │  history, trait │       │                           │   │
│  │  scores, diffs  │       │   → Skill directory (zip)  │   │
│  └────────────────┘       │   → Skills API upload       │   │
│                            │   → Claude Code install     │   │
│                            └───────────────────────────┘   │
│                                                            │
├──────────────────────────────────────────────────────────┤
│              Claude Agent SDK (Python)                      │
│   Each competitor = Agent SDK query() with Skill loaded     │
│   via setting_sources pointed at the Skill's temp dir       │
└──────────────────────────────────────────────────────────┘
```

### Agent Roles

**1. Challenge Designer Agent**
- Input: specialization description
- Output: 3-5 graded challenges with evaluation rubrics
- Behavior: thinks about what would truly test this specialization across different facets. A good Elixir Skill shouldn't just handle happy-path GenServers — it should handle error recovery, testing, supervision trees, and performance.
- Uses web search to find real-world examples of the specialization domain

**2. Spawner Agent**
- Input: specialization + generation number + (if gen > 0) parent genomes
- Output: N complete Skill directories (SKILL.md + any supporting files)
- Gen 0: generates intentionally diverse approaches. One Skill might emphasize TDD, another might focus on patterns, another on performance. Different frontmatter descriptions, different instruction structures, different supporting files.
- Gen 1+: recombines winning traits, introduces mutations

**3. Competitor Agents (N per generation)**
- Each competitor is a Claude Agent SDK `query()` call with:
  - `setting_sources=["project"]` pointed at a temp directory containing the candidate Skill
  - `allowed_tools=["Skill", "Read", "Write", "Edit", "Bash"]`
  - The challenge task as the prompt
- The competitor runs a full agentic loop: reads the Skill, follows its instructions, writes code, runs it, iterates
- Output: the solution files + execution trace
- Key: each competitor runs in an isolated temp directory

**4. Judging System (Multi-Layered)**

The Judge is not a single agent — it's a pipeline of five layers that progressively refine the evaluation. This is critical: a single LLM judge is noisy and inconsistent. Layered evaluation grounds fitness in real execution results.

**Layer 1: Deterministic Checks (no LLM, automated)**
- Does the code parse / compile without errors?
- Do tests pass? (challenge-provided test suite or competitor-generated tests)
- Linting / static analysis score (ruff, credo, eslint — depending on domain)
- Performance benchmarks if applicable (execution time, memory)
- Output matches expected structure / format
- Produces a numeric score per criterion: pass/fail or 0-100

**Layer 2: Trigger Accuracy (automated, no LLM)**
- Tests whether the Skill's frontmatter `description` fires correctly
- Present Claude with 5 prompts that SHOULD trigger the Skill and 5 that SHOULDN'T
- Measure precision (no false triggers) and recall (no missed triggers)
- A Skill with great instructions but a bad description is useless in practice — it'll never fire when needed
- This is a first-class fitness dimension, not an afterthought
- (Insight from Anthropic's skill-creator description optimization)

**Layer 3: Trace-Based Behavioral Analysis (LLM-assisted)**
- Read the full execution trace from the Agent SDK — every tool call, every file read/write, every reasoning step
- Verify: Did Claude actually load the Skill? Did it follow the instructions? Did it use the supporting scripts?
- Identify the *behavioral signature* of each Skill: what sequence of actions did it produce?
- Compare behavioral signatures across competitors to understand HOW they differ, not just that their outputs differ
- (Insight from MLflow's trace-based skill evaluation)

**Layer 4: Comparative Ranking + Pareto Selection (LLM-assisted)**
- Pairwise comparisons across all competitors: "Is solution A or B better on criterion X?"
- Derive rankings from win rates per criterion
- Instead of collapsing to a single fitness score, maintain a **Pareto front** across objectives:
  - Correctness, token efficiency, code quality, trigger accuracy, consistency
  - A Skill that's best on correctness but worst on efficiency is Pareto-optimal and survives
  - This preserves diversity and prevents premature convergence to "balanced but mediocre" Skills
- The Breeder receives the full Pareto front, not a single ranking
- (Insight from GEPA's Pareto-efficient selection)

**Layer 5: Trait Attribution (the novel part)**
- The Judge reads each competing Skill's SKILL.md alongside its execution trace and output
- Identifies which instructions were actually followed vs. ignored (trace evidence, not guessing)
- For instructions that were followed, correlates with Layer 1-4 scores
- For instructions that were ignored, diagnoses *why* (too vague? contradicted by another instruction? not relevant to this challenge?)
- Produces a trait → fitness contribution map AND a diagnostic trace the Breeder uses for reflective mutation
- This is the bridge between judging and breeding — it gives the Breeder causal signal, not just rankings

**Layer 6: Consistency Check (optional, expensive)**
- Run the top 2 Skills on the same challenge a second time
- Compare output quality variance — if a Skill produces wildly different results, its instructions aren't constraining enough
- Consistency is itself a fitness dimension: a Skill that reliably produces B+ work beats one that oscillates between A+ and D
- Skip for MVP, enable for production runs

**5. Breeder Agent (Reflective Mutation)**

Inspired by GEPA's core insight: mutations should be *diagnostic*, not random. The Breeder reads execution traces, not just scores, and proposes targeted fixes.

- Input: ranked Skills + execution traces + trait attribution + **learning log**
- Output: next generation's Skill directories + updated learning log
- Strategy:
  - **Elitism**: top 2 Skills survive unchanged
  - **Reflective Crossover**: combine traits from 2-3 parents, but guided by trace analysis. The Breeder reads each parent's execution traces and identifies *why* specific traits succeeded or failed. Crossover isn't "take section A from parent 1 and section B from parent 2" — it's "parent 1's testing approach worked because of X, parent 2's error handling worked because of Y, combine them while preserving the causal mechanism."
  - **Diagnostic Mutation**: instead of random changes, the Breeder reads the execution trace of a low-scoring Skill, diagnoses the root cause ("the instruction to 'always write tests first' caused the Skill to waste turns on trivial test scaffolding before understanding the problem"), and proposes a targeted fix. This is GEPA's "Actionable Side Information" concept applied to Skills.
  - **Joint Mutation**: when mutating instructions, also check if the frontmatter description, allowed-tools, or supporting scripts need corresponding changes. A Skill's components are interdependent — mutating one in isolation can break others. (Insight from Artemis's multi-component optimization.)
  - **Wildcard**: 1 slot per generation for a completely fresh Skill to prevent convergence
  - **Pruning**: remove instructions that trace analysis shows were consistently ignored or counterproductive
- **Learning Log**: a persistent, accumulating document that records lessons learned across ALL generations:
  - "Instructions phrased as imperatives were followed 80% more often than descriptive phrasing"
  - "Including a concrete example after each pattern instruction improved output quality by 15%"
  - "Scripts that validate output format caught errors that instruction-only approaches missed"
  - The learning log is injected into every mutation prompt, preventing the population from rediscovering the same failures. (Insight from Imbue's Darwinian Evolver.)
- Writes a breeding report explaining every decision with trace evidence
- **Bible Publishing**: after each generation, the Breeder extracts generalizable findings from the learning log and writes them to `bible/findings/`. Findings that survive across 3+ independent evolution runs get promoted to `bible/patterns/`. Patterns that consistently reduce fitness across runs get documented in `bible/anti-patterns/`. This creates a public, growing knowledge base of empirically-proven Skill authoring practices.

---

## How Competitor Evaluation Works (Detail)

This is the core agentic loop and the trickiest part to get right.

For each competitor Skill, for each challenge:

```python
async def evaluate_competitor(skill_dir: Path, challenge: Challenge) -> CompetitionResult:
    """
    1. Write the candidate Skill to a temp project directory
    2. Write the challenge task files (if any) to the same directory
    3. Run Agent SDK query() with the Skill loaded
    4. Collect the output (files written, code produced, tests run)
    5. Return the result for judging
    """
    
    work_dir = create_temp_project(skill_dir, challenge)
    
    # The Agent SDK loads the Skill from .claude/skills/
    # and uses it to solve the challenge
    results = []
    async for message in query(
        prompt=challenge.prompt,
        options=ClaudeAgentOptions(
            cwd=str(work_dir),
            setting_sources=["project"],
            allowed_tools=["Skill", "Read", "Write", "Edit", "Bash"],
            max_turns=15,
            permission_mode="bypassPermissions",
            model="claude-sonnet-4-6",
        )
    ):
        results.append(message)
    
    # Collect outputs
    output_files = collect_written_files(work_dir)
    execution_trace = extract_trace(results)
    
    return CompetitionResult(
        skill_id=skill_dir.name,
        challenge_id=challenge.id,
        output_files=output_files,
        trace=execution_trace,
    )
```

The temp project directory structure for each competitor:

```
/tmp/skillforge-{run_id}-gen{N}-competitor{M}/
├── .claude/
│   └── skills/
│       └── evolved-skill/        # ← the candidate Skill being tested
│           ├── SKILL.md
│           ├── scripts/
│           └── references/
├── challenge/                    # ← challenge setup files (if any)
│   ├── starter_code.py
│   └── test_suite.py
└── output/                       # ← where the competitor writes its solution
```

---

## Meta Mode — Evolving Universal Skill Patterns

Meta mode is the more novel and potentially more valuable feature. Instead of evolving domain expertise, it evolves **how to write Skills well**.

### What Gets Evolved

A Meta-Skill genome contains universal Skill-authoring patterns:

```markdown
---
name: skill-author
description: >
  Guides Claude in authoring high-quality Agent Skills. Use when creating
  or improving any SKILL.md file. Provides empirically-evolved patterns
  for structure, instruction phrasing, progressive disclosure, and examples.
---

# Skill Authoring Patterns
*Evolved by SkillForge Meta — Generation 8, Fitness: 0.91*

## Optimal Structure
1. Start with a one-sentence identity statement ("You are a...")
2. Follow with 3-5 behavioral constraints (what to always/never do)
3. Then domain patterns grouped by task type
4. End with anti-patterns and escape hatches
[... evolved through competition ...]

## Instruction Phrasing
- Imperative voice outperforms descriptive ("Write tests first" > "Tests should be written first")
- Numbered steps outperform bullets for sequential workflows
- Concrete examples after every abstract instruction (evolved ratio: 1 example per 2 instructions)
[... evolved through competition ...]

## Progressive Disclosure
- SKILL.md should stay under 3000 tokens
- Split reference material into separate files when > 500 tokens
- Name reference files by task type, not by content ("testing.md" not "patterns.md")
[... evolved through competition ...]
```

### How Meta Evaluation Works

Meta evaluation requires an extra layer of indirection:

```
1. Candidate Meta-Skill M is loaded
2. Use M to generate 3 domain Skills across random domains:
   - e.g., "Python CLI tool specialist"
   - e.g., "React component specialist"  
   - e.g., "SQL query optimization specialist"
3. Each generated domain Skill is tested against domain-specific challenges
   (using the same Domain Mode evaluation pipeline)
4. M's fitness = average fitness of the domain Skills it helped create
```

This tests **generalization**. A Meta-Skill that only helps with one domain will score well on 1/3 of its evaluations and poorly on the other 2. Patterns that genuinely improve Skill authoring across domains rise to the top.

### Meta-Specific Evaluation Criteria

In addition to the domain Skill's downstream fitness, Meta-Skills are scored on:

- **Generalization** — did the pattern help across all 3 test domains, or just one?
- **Token efficiency** — did Skills authored with this Meta-Skill use fewer tokens in SKILL.md while maintaining quality?
- **Trigger accuracy** — did the generated Skills' frontmatter descriptions fire correctly? (test by presenting Claude with tasks that should/shouldn't trigger the Skill)
- **Instruction adherence** — what % of the generated Skill's instructions did Claude actually follow during challenges?
- **Consistency** — did repeated runs with the same Meta-Skill produce similarly-structured domain Skills?

### Meta Mode Output

The evolved Meta-Skill installs like any other Skill:

```bash
# Install the Meta-Skill
unzip skill-author.zip -d ~/.claude/skills/

# Now when you ask Claude to create a Skill, it loads skill-author
# and follows evolved best practices automatically
```

Or use it programmatically in SkillForge itself — the Meta-Skill becomes the Spawner's guide for generating better initial populations in Domain Mode. This creates a **bootstrap loop**: Meta mode improves Domain mode, which produces better training signal for Meta mode.

---

## Data Model

```python
@dataclass
class EvolutionRun:
    id: str                          # uuid
    mode: str                        # "domain" | "meta"
    specialization: str              # user-provided (domain) or "meta" (meta mode)
    population_size: int             # default 5
    num_generations: int             # default 3
    challenges: list[Challenge]
    generations: list[Generation]
    learning_log: list[str]          # accumulates lessons across ALL generations
    status: str                      # pending | running | complete | failed
    created_at: datetime
    completed_at: datetime | None
    best_skill: SkillGenome | None
    pareto_front: list[SkillGenome]  # all Pareto-optimal Skills (may be > 1)
    total_cost_usd: float

@dataclass
class SkillGenome:
    id: str                          # uuid
    generation: int
    skill_md_content: str            # the full SKILL.md text
    frontmatter: dict                # parsed YAML frontmatter
    supporting_files: dict[str, str] # path -> content for scripts/, references/, assets/
    traits: list[str]                # extracted behavioral traits (for breeding)
    meta_strategy: str               # approach description
    parent_ids: list[str]            # for lineage (supports 2-3 parents for multi-parent crossover)
    mutations: list[str]             # description of mutations applied
    mutation_rationale: str          # Breeder's diagnostic reasoning for each mutation
    
    # Maturity lifecycle (inspired by singularity-claude)
    maturity: str                    # draft | tested | hardened | crystallized
    generations_survived: int        # how many gens this genome (or its core traits) persisted
    
    # Layered fitness scores
    deterministic_scores: dict[str, float]   # L1: automated checks per challenge
    trigger_precision: float                 # L2: % of correct non-triggers
    trigger_recall: float                    # L2: % of correct triggers
    behavioral_signature: list[str]          # L3: sequence of actions from trace analysis
    pareto_objectives: dict[str, float]      # L4: per-objective scores for Pareto front
    is_pareto_optimal: bool                  # L4: on the Pareto front?
    trait_attribution: dict[str, float]      # L5: trait -> fitness contribution
    trait_diagnostics: dict[str, str]        # L5: trait -> diagnostic explanation
    consistency_score: float | None          # L6: variance across repeated runs

@dataclass
class Challenge:
    id: str
    prompt: str                      # what to ask Claude
    difficulty: str                  # easy | medium | hard
    evaluation_criteria: dict[str, float]  # criterion -> weight
    verification_method: str         # run_tests | judge_review | both
    setup_files: dict[str, str]      # starter code, test suites, etc.
    gold_standard_hints: str         # what great looks like

@dataclass
class Generation:
    number: int
    skills: list[SkillGenome]
    results: list[CompetitionResult]
    pareto_front: list[str]          # IDs of Pareto-optimal Skills this generation
    breeding_report: str             # Breeder's diagnostic reasoning with trace evidence
    learning_log_entries: list[str]  # new lessons discovered this generation
    best_fitness: float
    avg_fitness: float
    trait_survival: dict[str, bool]  # which traits made it to next gen
    trait_emergence: list[str]       # new traits that appeared via mutation

@dataclass  
class CompetitionResult:
    skill_id: str
    challenge_id: str
    output_files: dict[str, str]     # path -> content
    trace: list[dict]                # full execution trace from Agent SDK
    
    # L1: Deterministic
    compiles: bool
    tests_pass: bool | None          # None if no test suite
    lint_score: float | None
    perf_metrics: dict[str, float]   # optional benchmarks
    
    # L2: Trigger accuracy
    trigger_precision: float         # correct non-triggers / total non-trigger prompts
    trigger_recall: float            # correct triggers / total trigger prompts
    
    # L3: Trace-based behavioral analysis
    skill_was_loaded: bool           # did Claude actually load the Skill?
    instructions_followed: list[str] # which SKILL.md instructions were followed (trace evidence)
    instructions_ignored: list[str]  # which were ignored
    ignored_diagnostics: dict[str, str]  # instruction -> why it was ignored
    scripts_executed: list[str]      # which supporting scripts were run
    behavioral_signature: list[str]  # ordered sequence of actions (tool calls, file ops)
    
    # L4: Comparative + Pareto
    pairwise_wins: dict[str, int]    # criterion -> win count
    pareto_objectives: dict[str, float]  # objective -> score (for Pareto front)
    
    # L5: Trait attribution
    trait_contribution: dict[str, float]  # trait -> fitness delta
    trait_diagnostics: dict[str, str]     # trait -> causal explanation from trace
    judge_reasoning: str
```

---

## API Endpoints

### POST /evolve
Start a new evolution run.
```json
{
    "mode": "domain",
    "specialization": "An Elixir developer Skill that writes idiomatic Phoenix LiveView...",
    "population_size": 5,
    "num_generations": 3,
    "max_budget_usd": 10.0
}
```

For meta mode:
```json
{
    "mode": "meta",
    "test_domains": [
        "Python CLI tools",
        "React components", 
        "SQL query optimization"
    ],
    "population_size": 5,
    "num_generations": 3,
    "max_budget_usd": 25.0
}
```
Returns: `{ "run_id": "...", "ws_url": "/ws/evolve/{run_id}" }`

### WebSocket /ws/evolve/{run_id}
Real-time event stream:
```
challenge_designed        — a new evaluation challenge
generation_started        — generation N beginning
competitor_started        — competitor M starting challenge K  
competitor_progress       — competitor writing/testing/iterating
competitor_finished       — competitor M done with challenge K
judging_layer1_complete   — deterministic checks done (pass/fail, lint, perf)
judging_layer2_started    — pairwise comparisons beginning
judging_layer2_complete   — comparative rankings finalized
judging_layer3_complete   — trait attribution done
scores_published          — full generation results
breeding_started          — Breeder producing next gen
breeding_report           — Breeder's reasoning and decisions
generation_complete       — generation N done, fitness summary
evolution_complete        — final results, best Skill identified
cost_update               — running cost for the evolution run

# Meta mode additional events:
meta_domain_generated     — a test domain Skill was generated using the Meta-Skill
meta_domain_evaluated     — a test domain Skill completed its evaluation
meta_generalization_score — cross-domain fitness computed
```

### GET /runs/{run_id}
Full evolution run results.

### GET /runs/{run_id}/export?format={format}
Export the best evolved Skill:
- `format=skill_dir` → zip of the complete Skill directory (SKILL.md + supporting files)
- `format=skill_md` → just the SKILL.md content
- `format=agent_sdk_config` → ClaudeAgentOptions JSON with system_prompt extracted from the Skill

### GET /runs/{run_id}/lineage
Lineage tree data (nodes = Skills, edges = parent→child, annotations = mutations + trait survival).

### POST /runs/{run_id}/fork
Fork from any SkillGenome in a completed run. Starts a new evolution seeded with that Skill.

### GET /registry
Browse published evolved Skills. Filterable by specialization, fitness score, generation count.

### POST /runs/{run_id}/publish
Publish the best Skill to the community registry with metadata.

---

## Export Formats

### Skill Directory Export (primary)

The main export. A zip file containing a complete, installable Skill:

```
elixir-liveview-specialist/
├── SKILL.md
├── scripts/
│   └── validate_liveview.py    # if the evolved Skill created helper scripts
├── references/
│   └── otp_patterns.md         # if it created reference docs
└── META.md                     # SkillForge metadata (lineage, fitness, generation)
```

The SKILL.md follows the standard Agent Skills format:

```markdown
---
name: elixir-liveview-specialist
description: >
  Specializes Claude in writing idiomatic Phoenix LiveView code with proper OTP
  patterns, comprehensive ExUnit tests, and LiveView Native considerations.
  Use when working on Elixir/Phoenix projects involving LiveView components,
  live navigation, or real-time features.
---

# Elixir LiveView Specialist
*Evolved by SkillForge — Generation 5, Fitness: 0.94*

## Approach
When working on LiveView code, always start by identifying the data flow...

## Patterns
- Structure LiveView modules in mount → handle_params → handle_event → render order
- Prefer function components over stateful components when state isn't needed
- Minimize assigns — derive computed values in render/1
- Use streams for large collections instead of storing full lists in assigns
[... evolved instructions ...]

## Testing Strategy
- Write ExUnit tests that exercise the full LiveView lifecycle
- Use live/2 to mount, then render_* helpers to simulate events
- Always test disconnected mount separately from connected mount
[... evolved instructions ...]

## Anti-patterns to Avoid
- Never put business logic in handle_event — delegate to context modules
- Avoid nested live_components more than 2 levels deep
[... evolved from generations of competition ...]
```

### Agent SDK Config Export

```json
{
    "system_prompt": "You are a specialist Elixir/Phoenix developer...",
    "model": "claude-sonnet-4-6",
    "allowed_tools": ["Skill", "Read", "Write", "Edit", "Bash"],
    "max_turns": 25,
    "metadata": {
        "evolved_by": "SkillForge",
        "specialization": "Elixir LiveView Specialist",
        "fitness": 0.94,
        "generation": 5,
        "lineage": ["gen0-alpha", "gen1-bravo", "gen3-delta", "gen5-echo"],
        "challenges_passed": 15,
        "traits_survived": [
            "mount-params-event-render ordering",
            "function-components-first",
            "derive-in-render"
        ]
    }
}
```

---

## Installation Paths

The evolved Skill can be installed via:

**Claude Code (filesystem)**
```bash
# Unzip to personal skills directory
unzip elixir-liveview-specialist.zip -d ~/.claude/skills/

# Or to a project
unzip elixir-liveview-specialist.zip -d .claude/skills/
```

**Skills API**
```bash
curl -X POST "https://api.anthropic.com/v1/skills" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-beta: skills-2025-10-02" \
  -F "display_title=Elixir LiveView Specialist" \
  -F "files[]=@elixir-liveview-specialist/SKILL.md;filename=elixir-liveview-specialist/SKILL.md"
```

**Agent SDK**
```python
options = ClaudeAgentOptions(
    cwd="/path/to/project",
    setting_sources=["project"],  # loads from .claude/skills/
    allowed_tools=["Skill", "Read", "Write", "Edit", "Bash"],
)
```

---

## UI (Web Frontend)

### Evolution Dashboard
- Specialization input + "Start Evolution" button
- Real-time tournament visualization as WebSocket events stream
- Each competitor shown as a card with live status (writing → testing → iterating → done)
- Scores appear after judging with expandable reasoning
- Breeding report between generations explaining crossover/mutation decisions
- Fitness-over-generations line chart (best + average per generation)

### Skill Diff Viewer
- Side-by-side SKILL.md comparison between parent and child
- Highlighted additions/removals/modifications
- Trait annotations showing which changes improved fitness

### Lineage Explorer
- Interactive tree visualization (d3 or similar)
- Click any node to see full Skill content, scores, and trait attribution
- Color-coded by fitness (green = high, red = low)
- Edges annotated with mutation type (crossover, mutation, wildcard, elitism)

### Agent Registry
- Browse evolved Skills by specialization
- Each entry shows: specialization, generation count, fitness, trait list, download count
- Fork button → starts new evolution seeded with that Skill
- Install instructions for Claude Code / API / Agent SDK

---

## Tech Stack

- **Backend**: Python 3.12+, FastAPI, WebSockets (starlette)
- **Agent Runtime**: Claude Agent SDK (Python) — `claude-agent-sdk`
- **Database**: SQLite via aiosqlite (evolution runs, genomes, lineage, registry)
- **Frontend**: React (Vite) + Tailwind — WebSocket-driven dashboard
- **Deployment**: Railway (Docker)
- **Model**: claude-sonnet-4-6 for all agents (cost-effective for MVP)
- **Cost control**: `max_budget_usd` per run, track token usage per agent call

---

## File Structure

```
skillforge/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── Dockerfile
├── railway.toml
│
├── docs/
│   ├── skills-research.md           # Deep Research report — complete Skills technical reference
│   ├── golden-template.md           # The canonical starting structure for all gen 0 Skills
│   ├── golden-template/             # Actual template files
│   │   ├── SKILL.md                 # Template SKILL.md with placeholder variables
│   │   ├── scripts/
│   │   │   └── validate.sh          # Template validation script
│   │   ├── references/
│   │   │   └── .gitkeep
│   │   └── assets/
│   │       └── .gitkeep
│   └── eval-queries-template.json   # Template for trigger accuracy testing
│
├── bible/
│   ├── README.md                    # The Claude Skills Bible — introduction and methodology
│   ├── findings/                    # Individual findings from evolution runs
│   │   ├── 001-description-patterns.md
│   │   ├── 002-instruction-density.md
│   │   └── ...                      # Auto-generated by the Breeder's learning log
│   ├── patterns/                    # Proven patterns that survive across generations
│   │   ├── structural.md            # What SKILL.md structures work best
│   │   ├── descriptions.md          # Description patterns with measured trigger rates
│   │   ├── instructions.md          # Instruction styles with adherence scores
│   │   ├── scripts.md               # When and how to use scripts effectively
│   │   └── progressive-disclosure.md # Optimal Level 2 vs Level 3 splitting
│   ├── anti-patterns/               # Patterns that consistently reduce fitness
│   │   └── ...
│   └── evolution-log.md             # Chronological log of all evolution runs and key findings
│
├── skillforge/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app entry point
│   ├── config.py                    # Settings, env vars, defaults
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── challenge_designer.py    # Generates evaluation challenges
│   │   ├── spawner.py               # Creates initial + bred Skill populations
│   │   ├── competitor.py            # Runs a Skill against a challenge via Agent SDK
│   │   ├── judge/
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py          # Orchestrates all 6 layers
│   │   │   ├── deterministic.py     # L1: compile, test, lint, perf
│   │   │   ├── trigger.py           # L2: trigger precision/recall testing
│   │   │   ├── trace_analysis.py    # L3: behavioral signature from execution trace
│   │   │   ├── comparative.py       # L4: pairwise ranking + Pareto front
│   │   │   ├── attribution.py       # L5: trait → fitness mapping with diagnostics
│   │   │   └── consistency.py       # L6: repeated-run variance (optional)
│   │   └── breeder.py              # Reflective crossover, diagnostic mutation, learning log
│   │
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── evolution.py             # Core evolution loop orchestration
│   │   ├── meta.py                  # Meta mode: cross-domain evaluation pipeline
│   │   ├── sandbox.py               # Temp directory setup for competitors
│   │   └── export.py                # Skill dir zip, API config, SKILL.md export
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── genome.py                # SkillGenome dataclass
│   │   ├── challenge.py             # Challenge dataclass
│   │   ├── generation.py            # Generation dataclass
│   │   └── run.py                   # EvolutionRun dataclass
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py              # SQLite setup + migrations
│   │   └── queries.py               # CRUD for runs, genomes, lineage
│   │
│   └── api/
│       ├── __init__.py
│       ├── routes.py                # REST endpoints
│       └── websocket.py             # WS event streaming
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── App.tsx
│       ├── components/
│       │   ├── EvolutionDashboard.tsx
│       │   ├── SpecializationInput.tsx
│       │   ├── CompetitorCard.tsx
│       │   ├── FitnessChart.tsx
│       │   ├── BreedingReport.tsx
│       │   ├── SkillDiffViewer.tsx
│       │   ├── LineageExplorer.tsx
│       │   └── AgentRegistry.tsx
│       ├── hooks/
│       │   └── useEvolutionSocket.ts
│       └── types/
│           └── index.ts
│
└── tests/
    ├── test_evolution.py
    ├── test_agents.py
    ├── test_sandbox.py
    └── test_export.py
```

---

## CLAUDE.md

```markdown
# SkillForge

## What is this?
An evolutionary breeding platform for Claude Agent Skills. Two modes:
- **Domain mode**: Users define a specialization, we evolve a population of
  SKILL.md files through tournament selection, export the winner.
- **Meta mode**: Evolves universal Skill-authoring patterns that make any
  Skill better. Tests generalization across multiple random domains.

## Tech
- Python 3.12, FastAPI, Claude Agent SDK, SQLite (aiosqlite), WebSockets
- React + Vite + Tailwind frontend
- Deploy target: Railway (Docker)

## Architecture
Multi-agent orchestration with insights from GEPA, Artemis, and Imbue.

Agent roles:
1. Challenge Designer — generates evaluation tasks from the specialization
2. Spawner — creates diverse initial Skill populations (gen 0) or breeds next gen
3. Competitor — Agent SDK query() with candidate Skill loaded via setting_sources
4. Judging Pipeline (6 layers):
   - L1: Deterministic (compile, tests, lint, perf — no LLM)
   - L2: Trigger Accuracy (precision/recall of frontmatter description)
   - L3: Trace-Based Behavioral Analysis (did Skill load? instructions followed?)
   - L4: Comparative + Pareto Selection (pairwise ranking, multi-objective front)
   - L5: Trait Attribution (instruction → fitness mapping with diagnostics)
   - L6: Consistency (repeated runs, variance check — optional, expensive)
5. Breeder — reflective mutation (reads traces, not just scores), multi-parent
   crossover (2-3 parents), joint component mutation, persistent learning log

Core loop: skillforge/engine/evolution.py

## Key Reference Documents
- `docs/skills-research.md` — the definitive technical reference for Claude Agent Skills.
  Covers format spec, routing mechanics, API, instruction best practices, trigger
  optimization, evaluation frameworks, and production patterns. READ THIS FIRST.
- `docs/golden-template.md` — the canonical starting structure for all gen 0 Skills.
  The Spawner uses this as its seed template, varying content while preserving structure.
- `bible/` — the Claude Skills Bible. Accumulated learnings from evolution runs.
  The Breeder publishes findings here after each generation. Patterns that survive
  across multiple runs get promoted to `bible/patterns/`. Anti-patterns go to
  `bible/anti-patterns/`. This directory is the public-facing knowledge base.

## Key Techniques (from prior art)
- Reflective mutation via execution traces, not random (GEPA's ASI concept)
- Pareto-efficient selection across multiple objectives (GEPA)
- Joint optimization of interdependent Skill components (Artemis)
- Learning log that accumulates lessons and prevents rediscovering failures (Imbue)
- Trigger accuracy as first-class fitness dimension (Anthropic skill-creator)
- Trace-based behavioral verification (MLflow)
- Maturity lifecycle: draft → tested → hardened → crystallized (singularity-claude)

## Key Patterns
- Each competitor runs in an isolated temp directory with the Skill in .claude/skills/
- Agent SDK loads the Skill via setting_sources=["project"]
- All agent communication goes through the Evolution Engine (no direct agent-to-agent)
- WebSocket streams every event to the frontend in real-time
- Skills are versioned as full directory snapshots with lineage tracking
- Learning log is a persistent list[str] on the EvolutionRun, injected into Breeder prompts
- Pareto front maintained per generation — multiple "best" Skills can coexist

## Constraints
- Competitors get max 15 turns per challenge (prevent runaway costs)
- max_budget_usd caps total API spend per evolution run
- Use claude-sonnet-4-6 for all agents in MVP
- SQLite for storage — no external DB dependencies
- Default domain run (5 pop, 3 gen, 3 challenges) should complete in < 15 minutes
- Meta mode is more expensive (~3x domain mode) due to cross-domain testing

## Code Style
- Type hints everywhere, use dataclasses for internal models
- Pydantic for API request/response schemas only
- Async throughout — evolution engine is fully async
- No classes where functions suffice
- Short functions, clear names, minimal comments
- Prefer composition over inheritance

## Testing
- Test evolution loop with mock Agent SDK responses
- Test each judging layer independently
- Test Skill directory creation and structure validation
- Test export formats produce valid SKILL.md and installable directories
- Test WebSocket events fire in correct order
- Test pairwise comparison produces stable rankings
```

---

## MVP Scope — Ship Tonight

### Must Have
- [ ] `docs/skills-research.md` included in repo (the deep research report)
- [ ] `docs/golden-template.md` + template directory for gen 0 seeding
- [ ] `bible/` directory structure initialized with README
- [ ] Spawner uses golden template as structural seed for all gen 0 Skills
- [ ] Spawner enforces authoring constraints (250-char descriptions, 500-line body, 2-3 examples)
- [ ] Description and instruction body evolve on separate tracks
- [ ] POST /evolve starts a run (domain mode)
- [ ] Challenge Designer generates 3 challenges from specialization
- [ ] Spawner creates 5 diverse initial Skills (gen 0)
- [ ] Competitors solve challenges via Agent SDK with Skill loaded
- [ ] L1 judging: deterministic checks (compile, tests, lint, reference validation)
- [ ] L2 judging: trigger accuracy (precision/recall on description)
- [ ] L3 judging: trace-based analysis (did Skill load, which instructions followed)
- [ ] L4 judging: pairwise comparative ranking
- [ ] L5 judging: trait attribution with diagnostics
- [ ] Breeder with reflective mutation (reads traces + learning log)
- [ ] Learning log accumulates across generations
- [ ] Breeder publishes generalizable findings to `bible/findings/`
- [ ] 3 generations complete end-to-end
- [ ] Export best Skill as downloadable zip (SKILL.md + supporting files)
- [ ] Export as Agent SDK config JSON
- [ ] WebSocket streams progress events (including per-layer judging events)
- [ ] Basic React dashboard with real-time tournament view
- [ ] Fitness-over-generations chart
- [ ] Deploy to Railway via Docker
- [ ] max_budget_usd cost cap

### Nice to Have (v1.1)
- [ ] Pareto front selection (multi-objective, export multiple Pareto-optimal Skills)
- [ ] Meta mode — evolve universal Skill-authoring patterns
- [ ] L6 judging: consistency checks (repeated runs)
- [ ] Maturity lifecycle labels (draft → tested → hardened → crystallized)
- [ ] Multi-parent crossover (3 parents)
- [ ] Skill diff viewer (parent vs. child with trait annotations)
- [ ] Lineage tree visualization
- [ ] Fork from any genome
- [ ] Public Skills registry
- [ ] Parallel competitor execution (concurrent Agent SDK queries)
- [ ] Upload to Skills API directly from export
- [ ] Custom seed challenges alongside auto-generated ones
- [ ] Cost breakdown per agent role

### Future
- [ ] Bootstrap loop: Meta-Skill feeds back into Domain mode Spawner
- [ ] Skills that evolve their own evaluation challenges
- [ ] Cross-specialization breeding (combine Elixir Skill + Testing Skill)
- [ ] Continuous evolution (background daemon that keeps improving)
- [ ] Community registry with upvotes, fitness leaderboards, fork graphs
- [ ] One-click install into Claude Code projects
- [ ] Skill-to-Skill competition (pit two evolved Skills against each other)
- [ ] Self-improving SkillForge (use SkillForge to evolve SkillForge's own agent prompts)
- [ ] Auto-promote bible findings to patterns after N confirming runs
- [ ] Publish Claude Skills Bible as a standalone public resource (GitHub Pages / mdbook)
- [ ] Bible-informed Spawner: gen 0 Skills incorporate all proven patterns automatically
- [ ] Cross-run learning: bible patterns feed back into the golden template itself
- [ ] Model-version tracking: tag bible findings with Claude model version for regression detection
```
