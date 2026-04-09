# SkillForge — Project Journal

## Entry #1: From Zero to Spec in One Session

**Date**: April 8, 2026  
**Session Duration**: ~3 hours  
**Participants**: Matt + Claude Desktop  

---

### The Starting Point

Matt came in with a simple goal: build something cool with the Claude Agent SDK that he could ship quickly and talk about in a job interview the next day. The constraint was real — it needed to be genuinely agentic (not just an LLM API call with a wrapper), involve multi-agent orchestration, and solve a problem nobody else had solved yet.

---

### Phase 1: Idea Exploration

**Round 1 — Initial brainstorming.** I proposed five projects: Repo Roast Bot, README Agent, Codebase Explainer, PR Changelog Agent, and Spec-to-Scaffold Agent. Matt's feedback was sharp: "these more feel like API calls to an LLM instead of real agent development work." He was right — none of them had a real agentic loop.

**Round 2 — Genuinely agentic ideas.** I proposed five more with real feedback loops: Deploy Doctor, Migration Agent, Bug Bounty Hunter, Self-Healing API Monitor, and Multi-Agent Debate Researcher. Matt noted the debate researcher was something he'd been thinking about, but asked to keep exploring.

**Round 3 — Multi-agent focus.** Matt pushed for multi-agent orchestration specifically. I proposed: Adversarial Red/Blue Team, Agent Negotiation Protocol, Agent Swarm Codebase Exploration, Evolutionary Agent Tournament, and Agent Civilization. Matt locked in on **#4: Evolutionary Agent Tournament** — breeding agents through competitive natural selection.

**Key decisions:**
- Python (not TypeScript)
- User-configurable challenges (not hardcoded)
- Deploy to Railway
- Spec-driven development (spec first, then build)

---

### Phase 2: The Pivot to Skills

While drafting the initial spec for "AgentForge" (evolutionary system prompt optimization), Matt had two critical insights that transformed the project:

**Insight 1: "We could also do the same thing with Skills?"** Instead of evolving raw system prompts, evolve Claude Agent Skills — the native composability primitive in the Claude ecosystem. Skills have a defined format (SKILL.md + supporting files), they're discoverable, they're composable, and they slot directly into Claude Code, the Agent SDK, and the Skills API. This made the output immediately useful rather than just a demo.

**Insight 2: "This could be a cool way to optimize for sub-agent types."** The real value isn't the tournament — it's the evolved artifact. An Elixir specialist Skill, a testing Skill, a security review Skill. Each one battle-tested through competition, not hand-tuned through vibes.

These two insights transformed the project from "cool demo" to "missing piece in the Claude Skills ecosystem."

**The project was renamed from AgentForge to SkillForge.**

Decisions made during this phase:
- Skills only (not system prompts) — cleaner, more focused
- Both CLAUDE.md and Agent SDK config as export formats — portable across tools
- Agent-generated challenges (not user-provided) — the Challenge Designer agent creates eval tasks from the specialization description
- Full lineage tracking with fork capability — evolved Skills are persistable and shareable

---

### Phase 3: Judging and Meta-Evolution

Matt raised two critical questions: "How are we going to judge these effectively?" and "Should we think about evolving generic patterns that apply to any skill?"

**Judging evolution.** The initial spec had a single Judge agent. Matt pushed back (rightly) that LLM-as-judge is noisy. We designed a multi-layered approach:
- Layer 1: Deterministic checks (compile, tests, lint — no LLM)
- Layer 2: Comparative pairwise ranking (more stable than absolute scoring)
- Layer 3: Trait attribution (which SKILL.md instructions caused better/worse output)
- Layer 4: Consistency checks (repeated runs to measure variance)

**Meta mode.** Instead of just evolving domain expertise ("how to write Elixir"), also evolve universal Skill-authoring patterns ("how to write a good Skill, period"). Meta mode tests generalization by applying candidate Meta-Skills across 3+ random domains. This produces a "Skill Meta-Skill" — a Skill that coaches Claude on authoring better Skills. We scoped both modes from the start (ambitious) with Meta mode in v1.1 for MVP.

---

### Phase 4: Competitive Research

I ran a web search to see who else was doing evolutionary optimization of LLM agents. Key findings:

**What exists:**
- **EvoPrompt** (ICLR 2024) — academic paper on evolutionary prompt optimization. Purely academic, short prompts, no agent context.
- **GEPA** (Berkeley) — Pareto-efficient evolutionary search over text parameters. Shopify's CEO called it "severely under-hyped." The closest competitor conceptually.
- **Artemis** (TurinTech) — enterprise evolutionary agent optimization. Joint multi-component optimization.
- **singularity-claude** — self-evolving loop for Claude Skills. Single-Skill hill climbing, not population-based.
- **Anthropic's skill-creator** — just updated with evals, A/B testing, description optimization. Testing side, not evolutionary side.

**What nobody is doing:**
1. Population-based evolution of Agent Skills specifically
2. Trait-level attribution (decompose a Skill into discrete traits, attribute fitness to individual instructions)
3. Meta-Skill evolution (universal Skill-authoring patterns tested for cross-domain generalization)
4. Skills-native output (installable Skill directories, not optimized prompts)

This validated the positioning: SkillForge isn't competing with GEPA, it's applying the same insight (evolutionary optimization) to a specific artifact (Claude Skills) with features nobody else has.

---

### Phase 5: Incorporating Prior Art

With the competitive landscape mapped, Matt asked: "Should we update the spec to leverage some of their insights?" Yes.

**From GEPA:** Reflective mutation via execution traces ("Actionable Side Information") — mutations are diagnostic, not random. Pareto-efficient selection across multiple objectives.

**From Artemis:** Joint optimization of interdependent Skill components — frontmatter, instructions, scripts, and allowed-tools are interdependent.

**From Imbue's Darwinian Evolver:** Multi-parent crossover (2-3 parents, not just 2) and a persistent learning log that accumulates lessons across all generations.

**From Anthropic's skill-creator:** Trigger accuracy as a first-class fitness dimension. Description optimization via 60/40 train/test split with 3 runs per query.

**From MLflow:** Trace-based behavioral verification — did Claude actually load the Skill, follow instructions, use scripts?

**From singularity-claude:** Maturity lifecycle — draft → tested → hardened → crystallized.

The judging system expanded from 4 to 6 layers. The Breeder was completely reworked around reflective mutation. The data model grew to include Pareto fronts, learning logs, maturity labels, and diagnostic traces.

---

### Phase 6: Monetization Thinking

We explored the business model briefly:
- **Open source core** — the engine is free, bring your own API key
- **Hosted runs** — $5-15/domain run, $25-50/meta run
- **Skill registry/marketplace** — free community Skills, premium evolved Skills with revenue share
- **Enterprise** — evolve against proprietary codebases, private registry, continuous evolution
- **The Meta-Skill moat** — accumulates knowledge about how to write effective Skills across every customer run, creating a network effect

The key insight for the interview: "Skills are Anthropic's composability primitive. There's no toolchain for optimizing them. SkillForge is the missing piece."

---

### Phase 7: Deep Research

Matt asked me to write a comprehensive research prompt, then run it. The prompt covered 11 areas across Skills: format specification, discovery/loading mechanics, API endpoints, instruction writing, description optimization, scripts/references/assets, evaluation frameworks, real-world patterns, Agent SDK integration, future roadmap, and advanced patterns.

**Critical findings that changed the spec:**

- **Routing is pure LLM reasoning** — no embeddings, no classifiers. Description quality is THE dominant variable.
- **250-character cliff** — descriptions truncated in skill listing. Front-load or die.
- **~150-200 instruction budget shared across all context** — Skills must be lean.
- **Scripts are free, instructions are expensive** — script code never enters context.
- **73% of skill setups in the wild are broken** — primarily missing references.
- **Examples beat rules empirically** — 72% → 90% quality improvement with 2-3 examples.
- **`allowed-tools` frontmatter ignored by Agent SDK** — critical for competitor evaluation.

---

### Phase 8: Integrating Research into the Spec

We folded the research findings into the spec:

1. **Added "Skill Authoring Constraints" section** — every hard limit encoded as rules the Spawner and Breeder must enforce
2. **Split description evolution from instruction evolution** — they serve fundamentally different functions
3. **Golden Template** — the empirically-derived starting structure for all gen 0 Skills
4. **Bible structure** — `bible/` directory with patterns, anti-patterns, findings, and evolution log, seeded with 12 confirmed patterns from research

---

### Phase 9: Claude Skills Bible

Matt's idea: "Over time we can start to compile all of our learning from generation testing into a Claude Skills Bible we can publicly distribute."

This turned the learning log from an internal optimization signal into a public knowledge product. The bible:
- Gets seeded with research findings (12 patterns already documented)
- Gets updated by the Breeder after each generation (findings auto-published)
- Promotes findings to patterns after 3+ independent confirmations
- Documents anti-patterns that consistently reduce fitness
- Becomes a standalone public resource over time

The flywheel: SkillForge runs → Breeder publishes findings → findings replicate → patterns confirmed → patterns feed back into golden template → next gen 0 starts stronger → more runs → more findings → bible grows.

---

### Phase 10: Claude Code Kickoff Prompt

Wrote a structured 11-step development plan designed to be pasted directly into Claude Code:

0. Read all docs (research, golden template, bible, spec)
1. Set up CLAUDE.md with Progress Tracker
2. Scaffold project structure (stubs with type hints)
3. Implement data model (dataclasses)
4. Database layer (async SQLite)
5. Sandbox system (isolated competitor environments)
6. Individual agents (Challenge Designer → Spawner → Competitor → Judge Pipeline → Breeder)
7. Evolution engine (core orchestration loop)
8. API + WebSocket
9. Export engine
10. Frontend (React + Vite + Tailwind)
11. Docker + Railway deploy

Each step has clear deliverables, tests, and ends with "Update the Progress Tracker."

---

### Artifacts Produced

| Artifact | Lines | Purpose |
|----------|-------|---------|
| `SPEC.md` (skillforge-spec.md) | ~1,050 | Complete project specification |
| `docs/skills-research.md` | ~1,200 | Deep research report on Claude Agent Skills |
| `docs/golden-template.md` | ~120 | Canonical gen 0 Skill structure |
| `bible/README.md` | ~80 | Bible methodology and usage guide |
| `bible/patterns/descriptions.md` | ~60 | 5 confirmed description patterns |
| `bible/patterns/instructions.md` | ~70 | 7 confirmed instruction patterns |
| `bible/evolution-log.md` | ~10 | Empty log awaiting first run |
| `claude-code-kickoff.md` | ~220 | 11-step Claude Code development prompt |
| **This journal** | ~250 | Session documentation |

---

### Key Decisions Summary

| Decision | Rationale |
|----------|-----------|
| Skills over system prompts | Skills are the native composability primitive; output is immediately installable |
| Population-based evolution | Hill climbing gets stuck in local optima; populations explore more of the space |
| 6-layer judging | Single LLM judge is noisy; layered evaluation grounds fitness in real execution |
| Reflective mutation (from GEPA) | Random mutation wastes generations; trace-informed mutation targets root causes |
| Learning log (from Imbue) | Prevents rediscovering the same failures across generations |
| Pareto selection (from GEPA) | Single fitness score kills diversity; Pareto front preserves specialist Skills |
| Separate description/instruction evolution | Different functions, different optimization landscapes, different constraints |
| Golden template as gen 0 seed | Starting from proven structure means less wasted evolution on structural basics |
| Bible as public artifact | Turns internal optimization signal into a unique, growing knowledge product |
| Python + FastAPI + Railway | Matt's preference + fast to ship + free tier |
| Meta mode in v1.1 (not MVP) | Ambitious but secondary to proving the core loop works |

---

### What's Next

Matt takes the kickoff prompt into Claude Code tonight. Even partial completion (Steps 0-5) produces a demonstrable body of work for tomorrow's interview: comprehensive spec, research report, skills bible, scaffolded project, working data model, database layer. The spec alone demonstrates deep product thinking about the Claude Skills ecosystem.

The longer arc: ship the MVP, run the first evolution, publish the first bible findings, open source it, and build the community registry. The Meta-Skill mode is where it gets really interesting — agents that systematically improve their own capabilities through empirical optimization.

---

*"Nobody's hand-tuning SKILL.md files anymore. Evolution does it better."*
