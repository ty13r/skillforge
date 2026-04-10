# SkillForge — Project Journal

## Entry #9: Atomic Evolution and the v2.0 Vision

**Date**: April 10, 2026  
**Session Duration**: ~3 hours  
**Participants**: Matt + Claude Code (Opus 4.6)

---

### The Starting Point

We came in to fix a specific bug — the generate-skill endpoint was hitting Anthropic's Tier 1 rate limits (8K output tokens per minute for Sonnet). The previous session had built the full SpecAssistantChat → generate-skill pipeline, but every generation attempt failed with a 429. Matt had confirmed the rate limit tier from his API dashboard.

What started as a bug fix turned into a UX polish pass, a new persistence layer for candidate seeds, and — most significantly — a riff session that produced the architectural vision for v2.0.

---

### Phase 1: Fixing the Generation Pipeline

Three bugs, all interrelated:

**The rate limit.** `max_tokens=8192` on the generate-skill call consumed the entire Tier 1 output budget in one request. Dropped to 4096 and tightened the prompt to produce compact packages. The LLM completes naturally within ~3500 tokens now.

**The phantom empty key.** The `.env` loader checked `if key not in os.environ` — but `ANTHROPIC_API_KEY` was already in the environment as an empty string (from Claude Code's shell profile). The `.env` value never overwrote it. Changed to `if not os.environ.get(key)` so empty values get replaced.

**The retry trap.** When validation found minor issues (guide.md at 47 lines instead of 50), the retry prompt produced a tiny 552-char response — losing all the supporting files from the 11K-char first attempt. Fixed by accepting the first attempt whenever it has supporting files, regardless of minor validation failures. The retry only triggers when we got no supporting files at all.

After the fixes, we tested end-to-end through the browser: SpecAssistantChat → chat refines the domain → finalize → auto-generate package → file tree shows 4 files → "SKILL PACKAGE READY" → Start Evolution. Clean run.

---

### Phase 2: Candidate Seeds and File Preview

Matt asked two questions that led to new features: "Should we save the output and flag them to promote to Gen 0 skills?" and "Should we let them view the files?"

**File preview** was quick — clicking any file in the generated package tree now shows an inline preview. SKILL.md and .md files render as formatted markdown (ReactMarkdown + remarkGfm). Scripts render with syntax highlighting via the CodeViewer component we built in the previous session. Toggle on/off by clicking.

**Candidate seeds** was the bigger piece. New `candidate_seeds` table in SQLite with full SKILL.md content, supporting files, fitness scores, and a status workflow (pending → approved → promoted, or rejected). Two auto-save hooks:

1. Every successful `generate-skill` call saves a `source="generated"` candidate
2. Every completed evolution run saves the best_skill as `source="evolved"` with its fitness score

REST API for management: list, create, update status. The idea is that Matt (or eventually any admin) can review candidates and promote the best ones into the curated seed library.

---

### Phase 3: UX Polish

Small but important changes to the "From Scratch" flow:

- "Help me write this with AI" (tiny inline link) → "Generate Skill with AI" (right-aligned outlined button). Matt's feedback: "should be a more pronounced button type and on the right."
- Placeholder text: "Describe the target evolution... e.g., Cleans messy pandas DataFrames..." → "What should this skill do? e.g., 'Write pytest unit tests for Python code'..." More inviting, less technical.
- Button initially had a solid fill that Matt felt was "a bit much" — toned down to outlined with tinted background. The primary CTA should be "Start Evolution," not this secondary action.

---

### Phase 4: The v2.0 Vision — Atomic Variant Evolution

This started as Matt asking about a taxonomic ranking system for skills. The riff session went deep and produced something genuinely new.

**The taxonomy.** We landed on 3 fixed levels plus flexible tags:

- Domain → Focus → Language (structured, filterable, browsable)
- Tags capture framework/strategy specifics (pytest, mock-heavy, AWS)
- Specialization text is the free-form nuance

Matt caught a level I missed: Language sits between Focus and Skill. A pytest skill and a jest skill share Focus (Unit Tests) but differ fundamentally in execution.

**The insight.** Matt articulated something he'd been feeling: "We've been evolving entire molecules instead of evolving atomic units." The current pipeline evolves a full SKILL.md as a monolith — 45 competitor runs, huge mutation surface, averaged fitness signals. What if we decompose a skill into focused variants, evolve each one independently against narrow challenges, then assemble the winners?

This is the difference between evolving organisms and evolving genes. Genes evolve under focused selection pressure, then organisms are assemblies of fit genes.

**Two-tier variant model.** Not a full dependency graph — just foundation variants (structural decisions) and capability variants (focused modules that plug into the foundation). The fixture strategy is a foundation; the mock patterns adapt to whatever foundation won. One level of dependency, not arbitrary depth.

**The agent roster.** Matt pushed hard on naming — every agent should feel like a role in a biotech lab. We landed on:

| Agent | Role |
|-------|------|
| Taxonomist | Classifies, decomposes, recommends reuse |
| Scientist | Designs experiments (challenges) per variant |
| Spawner | Creates initial population |
| Breeder | Refines variants over generations (horizontal) |
| Reviewer | Evaluates fitness (peer review) |
| Engineer | Assembles variants + integration test + refinement (vertical) |

"Challenge Designer" → Scientist (designs experiments). "Judge" → Reviewer (peer review). "Assembler" → Engineer (Matt: "assembler sounds like a factory worker"). The Breeder vs Engineer separation is clean: Breeder works within a single variant dimension, Engineer combines across dimensions.

**Default vs Advanced mode.** Matt's call: "Let's make visibility the advanced mode option." Default users get a clean "here's your skill." Advanced users see the variant breakdown and can swap individual variants, lock good ones, re-evolve weak ones, or pull variants from other skill families.

**The Taxonomist principle.** Matt insisted: "They should check what we've already mapped and use that as the guide before creating anything new." The Taxonomist is conservative — reuse existing taxonomy and variants before creating new ones. This prevents sprawl and enables cross-family reuse (a proven mock strategy from the FastAPI skill family can be pulled into a Django skill).

---

### Artifacts Produced

| Artifact | Lines | Purpose |
|---|---|---|
| `plans/PLAN-V2.0-CONCEPT.md` | ~320 | Atomic variant evolution architecture, taxonomy, agent roles |
| `plans/BACKLOG.md` | ~100 | Extracted v1.2 backlog items (test backfill, streaming, BYOK, etc.) |
| `skillforge/api/candidates.py` | ~75 | Candidate seeds REST API |
| `skillforge/db/database.py` (updated) | +20 | candidate_seeds table DDL |
| `skillforge/db/queries.py` (updated) | +90 | save/list/update candidate seed queries |
| `skillforge/api/spec_assistant.py` (updated) | +30 | Auto-save generated packages, rate limit fix |
| `skillforge/engine/evolution.py` (updated) | +20 | Auto-save evolution winners |
| `frontend/src/components/SpecAssistantChat.tsx` (updated) | +50 | File preview, button/UX overhaul |
| `SCHEMA.md` (updated) | +40 | candidate_seeds + run_events documentation |
| `plans/PROGRESS.md` (updated) | +10 | Session completions logged |

---

### Key Decisions Summary

| Decision | Rationale |
|---|---|
| max_tokens 8192 → 4096 for generate-skill | Tier 1 rate limit is 8K output TPM; 4096 leaves headroom for chat calls |
| Accept first generation with supporting_files | Retry degrades output; minor validation failures < lost content |
| Empty env vars override from .env | Shell profile sets empty ANTHROPIC_API_KEY; must not block .env |
| Taxonomy: Domain → Focus → Language (3 levels + tags) | Deep enough to browse, shallow enough to maintain; tags handle variant-level specifics |
| Variant is the atomic unit, Skill is a collection | Enables focused evolution, cheaper testing, user-swappable components |
| Foundation + Capability two-tier model | One level of dependency, not arbitrary depth; foundation first, capabilities adapt |
| Default vs Advanced mode for variant visibility | Clean UX by default, power users can swap/evolve individual variants |
| Taxonomist checks existing before creating new | Prevents taxonomy sprawl, enables cross-family variant reuse |
| Agent rename: Scientist, Reviewer, Engineer | Biology-adjacent roles that communicate intent; dropped generic "Judge" and "Assembler" |

---

### What's Next

The v2.0 concept doc is drafted but several design questions remain open:

- **Variant granularity**: how small is too small? When does decomposition stop being helpful?
- **Assembly format**: how does the Engineer physically combine variants into one SKILL.md?
- **Simple skills**: some skills (git-commit-message) probably don't benefit from atomic evolution — when to skip decomposition?
- **Cross-family reuse**: the Taxonomist can recommend variants from other families, but the compatibility guarantees need work

The backlog items from v1.2 (streaming progress, cost recalibration, pipeline integration of supporting files, domain-specific test environments) are captured in `plans/BACKLOG.md`. Some overlap with v2.0 and will be absorbed into the new architecture.

Matt wants to start building v2.0. The natural first step is the taxonomy — add Domain → Focus → Language classification to the data model, auto-classify existing seeds, and build the registry UI around it. That's Phase 1 in the concept doc, and it's valuable even without the rest of v2.0.

---

*"Don't evolve the whole organism. Evolve the genes. Assemble the organism."*
