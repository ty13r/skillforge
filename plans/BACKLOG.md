# SKLD Backlog

Items carried over from PLAN-V1.2. These are not blockers for v2.0 but remain valuable work. Items may be absorbed into v2.0 phases where they overlap with the new architecture.

---

## Rebrand: SkillForge → SKLD

Rename all references to "SkillForge" throughout the repo to "SKLD" (Skill Kinetics through Layered Darwinism).

**Scope:**
- Python package: `skillforge/` → `skld/` (module rename, all imports)
- Config references: `SKILLFORGE_*` env vars → `SKLD_*`
- Database: `skillforge.db` → `skld.db`
- Docker/Railway: image name, service name
- Frontend: any "SkillForge" text in UI components
- Docs: CLAUDE.md, SCHEMA.md, SPEC files, journal entries (headers only, don't rewrite history)
- pyproject.toml: package name
- GitHub repo: coordinate with Matt (ty13r/skillforge → ty13r/skld)

**Risk:** Breaking change for Railway deploy, env vars, imports. Do as a single atomic commit with a find-and-replace sweep + manual verification. Old env var names should be supported as fallbacks for one release cycle.

---

## Test Backfill (from PLAN-V1.1 → V1.2)

### tests/test_seeds.py
- Seed loader idempotency (hash comparison short-circuits)
- Seed loader refresh (content hash change triggers re-insert)
- `spawn_from_parent()` returns pop_size genomes with elite slot 0
- Fork-from-seed integration (mocked LLM)
- 404 on unknown seed id

### tests/test_uploads.py
- Happy paths: single .md, .zip at root, .zip one level deep
- Size caps: .md >1MB, .zip unpacked >5MB
- File cap: .zip >100 entries
- Zip bomb: compression ratio >20:1
- Path traversal: `..` entries, absolute paths
- Extension allowlist enforcement
- Structural validation failures surface to client
- Upload → evolve integration

### frontend/src/hooks/useTheme.test.ts
- Already shipped and passing (10 tests)

### Hex value grep sweep
- Verify no hardcoded hex values outside the token system in component source
- One-off check, record result in journal

---

## Streaming Progress for Long LLM Calls

**Problem:** Challenge designer, spawner, and breeder each make single long LLM calls (30-80+ seconds) with zero events emitted. Users think the engine is broken.

**Solution:** Stream responses and emit each parsed item as it arrives:
1. Challenge Designer — emit `challenge_designed` as each challenge is parsed
2. Spawner — emit `skill_spawned` as each variant is parsed
3. Breeder — emit partial breeding report + each mutation as parsed

**Stopgap:** Emit `phase_progress` heartbeat every ~10s while LLM call is in-flight.

**Affected files:** challenge_designer.py, spawner.py, breeder.py, evolution.py, useEvolutionSocket.ts

---

## Recalibrate Cost & Time Estimates

**Blocked until:** real data from Managed Agents backend (need 3+ runs).

Current constants in SpecializationInput.tsx are calibrated against old SDK backend with sequential execution. Managed Agents changes: parallel runs, $0.08/session-hour overhead, Haiku vs Sonnet cost differences.

**Action:** After 3+ prod runs, extract actual metrics and recalibrate. Consider making constants dynamic (fetched from backend based on config).

---

## Pipeline Integration: Supporting Files in Evolution

Ensure every file in the skill package participates in the evolution lifecycle:

- **Spawner**: copies full directory (not just SKILL.md) into competitor sandbox. Mutates scripts/references when creating variants.
- **Competitor**: runs with full skill directory. Scripts and references available at `${CLAUDE_SKILL_DIR}/`.
- **L1 Judge**: runs `scripts/validate.sh` as part of scoring.
- **L3 Trace Analysis**: checks whether competitor read references and ran scripts.
- **L5 Trait Attribution**: maps script/reference usage to fitness contribution.
- **Breeder**: reads full directory diff when deciding mutations. Can evolve scripts and references.

**Note:** This overlaps significantly with v2.0's atomic variant architecture. The variant decomposition naturally separates scripts, references, and instructions into independently evolvable units.

---

## Domain-Specific Test Environments

**Status:** Architecture documented in PLAN-V1.2. Extends the golden template with `test_fixtures/`, `evaluation/criteria.json`, and `scripts/score.py`.

**Core principle:** The test environment is a property of the domain, not the individual skill. Every variant faces identical fixtures.

**Phases:**
- A: Add test_fixtures + criteria.json to seed packages
- B: Update create_sandbox() to run setup_env.sh
- C: Update L1 to run scripts/score.py and parse JSON output

**Note:** This maps directly to v2.0's Scientist agent role — the Scientist uses domain-specific evaluation criteria rather than inventing generic challenges.

---

## BYOK (Bring Your Own Key)

**Status:** Unresolved. Options explored (none accepted):
1. Ephemeral in-memory key — trust concerns
2. Anthropic OAuth / delegated access — unclear if available
3. Client-side proxy — not feasible for long pipelines
4. Self-hosted mode — kills hosted product

Needs a decision on acceptable trade-off before any public "run with your own key" feature.

---

## Research Paper: Evolutionary Optimization of LLM Agent Skills

**Status**: Collecting data. Draft when v2.0 atomic evolution has results.

### Working title

"SKLD: Atomic Variant Evolution for LLM Agent Skill Optimization"

### Core contributions

1. **Structured skill evolution** — multi-layer fitness evaluation (deterministic, trigger accuracy, trace analysis, comparative, trait attribution) applied to complete skill packages (instructions + scripts + references), not just prompt text
2. **Atomic variant decomposition** — breaking skills into independently-evolvable variants (foundation + capabilities) with trait-based assembly, reducing evolution cost and improving convergence
3. **Recursive self-improvement** — evolving the pipeline's own agent skills using the pipeline itself, with measurable generation-over-generation improvement
4. **Empirical comparison** — monolithic vs atomic evolution on identical domains, with ablation studies across Reviewer layers, learning log, and decomposition strategies

### Related work to cite

- GEPA (Generative Evolution of Prompts and Architectures) — Pareto-efficient selection, reflective mutation
- Artemis — joint optimization of interdependent components
- Imbue — learning log, preventing rediscovered failures
- EvoPrompt / PromptBreeder — evolutionary prompt optimization (but for raw prompts, not structured skill packages)
- DSPy — programmatic prompt optimization (different approach, complementary)
- OpenELM — evolutionary LLM agents
- Constitutional AI — self-improvement through AI feedback (adjacent)

### Data to collect (starting now)

All of this is already persisted or can be with minor additions:

| Data | Source | Status |
|------|--------|--------|
| Full event streams per run | `run_events` table | Already collecting |
| Per-generation fitness curves | `generations` table (best_fitness, avg_fitness) | Already collecting |
| Trait survival/emergence | `generations` table (trait_survival, trait_emergence) | Already collecting |
| Cost breakdowns per run | `evolution_runs.total_cost_usd` + cost_update events | Already collecting |
| Learning log per run | `evolution_runs.learning_log` | Already collecting |
| Bible findings | `bible/findings/*.md` | Already collecting |
| Pairwise comparison matrices | `competition_results.pairwise_wins` | Already collecting |
| Trait attribution scores | `skill_genomes.trait_attribution` | Already collecting |
| **v2.0 additions needed:** | | |
| Per-variant fitness over generations | `variants` table + `variant_evolutions` | Planned (Phase 3) |
| Assembly quality vs sum-of-parts | Engineer integration test results | Planned (Phase 4) |
| Cross-family variant reuse success rate | Taxonomist recommendations + outcomes | Planned (Phase 5) |
| RSI meta-loop metrics | Pipeline speed/cost/fitness before/after self-evolution | Planned (backlog) |
| Human baseline comparison | Human-authored skills vs evolved skills on same challenges | Need to design |

### Experiments to run

1. **v1.x vs v2.0 head-to-head**: same 5 domains, same budget, compare output fitness + cost + time
2. **Ablation: Reviewer layers**: remove L2 (trigger), L3 (trace), L5 (attribution) individually, measure fitness degradation
3. **Ablation: learning log**: with vs without accumulated lessons across generations
4. **Ablation: decomposition**: atomic vs monolithic on skills the Taxonomist classifies as "atomic-ready"
5. **RSI loop**: evolve pipeline agent skills, measure pipeline output quality before/after N self-improvement cycles
6. **Human vs evolved**: 3 experienced prompt engineers write skills for 5 domains, compare against evolved skills on identical challenges with blind judging
7. **Variant reuse**: take a proven mock-strategy variant from Domain A, inject into Domain B without re-evolution, measure fitness vs evolving from scratch

### Paper structure (rough)

1. Introduction — the skill authoring problem, why evolution
2. Background — Claude Agent Skills, related work
3. System architecture — taxonomy, agents, Reviewer pipeline, evolution loop
4. Atomic variant evolution — decomposition, focused selection, assembly
5. Recursive self-improvement — the meta-loop
6. Experiments + results
7. Discussion — limitations, implications, future work
8. Conclusion

### What to do now

- Keep collecting data (already happening via existing persistence)
- Document every surprising finding in journal entries (already doing this)
- When v2.0 Phase 4 ships: run the head-to-head experiments
- When RSI meta-loop is operational: run self-improvement experiments
- Draft paper after 2-3 rounds of experimental results

---

## Rich Variant Cards (Remaining Polish)

Most of this shipped in the QA session. Remaining items:
- Streaming trace: real-time output snippets in variant cards
- Diff view against parent skill in the skill modal
- Full rename sweep: any remaining "Competitor" → "Variant" labels

---

## Ship SKLD-bench Elixir families as a Claude Code plugin

**Goal**: once the 7 Elixir lighthouse families have shipped as evolved composite skills (PR #18 landed the first, `elixir-phoenix-liveview-composite`; 6 more to go), bundle ALL of them into a single distributable Claude Code plugin called `skldbench-elixir-plugin`. Users run `claude plugin install skldbench-elixir` and get the whole Elixir toolkit at once — not one skill at a time.

**Why a plugin, not just skill directories**: a bare `SKILL.md` relies on passive Level 1 routing (Claude reads frontmatter descriptions and picks the best match). A plugin ships keyword-triggered hooks that AGGRESSIVELY inject skills into the conversation when the user mentions relevant terms. We confirmed this by inspecting `~/.claude/plugins/cache/vercel-vercel-plugin/0.32.0/` — the vercel plugin's `hooks/user-prompt-submit-skill-inject.mjs` (788 lines of BM25 matching) is what fires the `[vercel-plugin]` system-reminders we've seen throughout this project when we mention "deploy", "edge functions", etc. Users who install our plugin would get the same aggressive routing for Phoenix, Ecto, Oban, and security-linter keywords.

**Plugin structure** (one directory ships 7 skills):

```
skldbench-elixir-plugin/
├── .claude-plugin/
│   ├── plugin.json                       # name, version, author, keywords
│   └── marketplace.json                  # (optional) marketplace listing
├── hooks/
│   ├── hooks.json                        # registers UserPromptSubmit + PreToolUse hooks
│   ├── user-prompt-submit-skill-inject.mjs   # lexical matcher (simplified from vercel pattern)
│   └── pretooluse-skill-inject.mjs       # tool-call-time reminder
├── generated/
│   └── skill-manifest.json               # 7 skills × retrieval.{aliases, intents, entities, pathPatterns, bashPatterns}
├── skills/
│   ├── elixir-phoenix-liveview-composite/
│   │   ├── SKILL.md
│   │   ├── scripts/{validate.sh, main_helper.py}
│   │   ├── references/{guide.md, cheatsheet.md, anti-patterns.md}
│   │   ├── test_fixtures/*.ex
│   │   └── assets/*.template
│   ├── elixir-ecto-schema-changeset-composite/
│   ├── elixir-ecto-sandbox-test-composite/
│   ├── elixir-ecto-query-writer-composite/
│   ├── elixir-oban-worker-composite/
│   ├── elixir-pattern-match-refactor-composite/
│   └── elixir-security-linter-composite/
└── README.md                             # install instructions + keyword cheat sheet
```

**Requirements**:

1. All 7 Elixir composites must be evolved (via real engine or post-hoc enrichment) and shipping a rich package (SKILL.md + scripts + references + test_fixtures + assets). First one (`elixir-phoenix-liveview-composite`) is done. 6 more to go — either via repeated mock runs (~45 min each via the current helper scripts) or via the real v2.1 engine once Phase 0 plumbing lands (see `plans/PLAN-V2.1.md`).

2. A **SkillForge-native plugin emitter**: a new `scripts/emit_plugin/` helper that:
   - Takes a list of run IDs
   - Pulls each composite + supporting_files from the DB
   - Generates `.claude-plugin/plugin.json` with proper metadata
   - Generates `hooks/hooks.json` registering `UserPromptSubmit` and `PreToolUse` hooks
   - Ships a minimal `user-prompt-submit-skill-inject.mjs` (~150-200 lines, keyword regex + session dedup — don't clone the full BM25 complexity unless it proves necessary)
   - Generates `generated/skill-manifest.json` from each composite's frontmatter description + per-dimension traits. Possibly dispatch a Claude agent to extract `retrieval.{aliases, intents, entities}` from the composite body.
   - Assembles the `skills/*/` directory structure from each genome's `supporting_files`
   - Outputs a directory ready to `zip -r skldbench-elixir-plugin.zip .` and publish

3. A **Claude Code plugin marketplace listing** at the end. The Vercel plugin has a `.claude-plugin/marketplace.json` — ours should too, so users can `claude plugin search skldbench` and find it.

4. **End-to-end verification**: install the plugin locally via `claude plugin install <path>`, open a fresh Claude Code session in a Phoenix project, type "help me refactor this LiveView", and confirm the `elixir-phoenix-liveview-composite` skill gets auto-injected via the hook.

5. **Optional SkillForge UI integration**: add a "Download as Plugin" button on the Registry page (alongside the existing "Download .zip" button per run). Each run's zip stays a single skill; the plugin button bundles multiple runs into a plugin distribution.

**Blocked on**:
- 6 more Elixir composite runs (real engine preferred over mock repeat, so this is really blocked on `plans/PLAN-V2.1.md` Phase 0 completion)
- A decision on whether the hook script should be a minimal custom matcher (~200 lines) or a vendored + adapted version of the Vercel plugin's matcher
- Authoritative Claude Code plugin schema docs (`claude-code-guide` agent can fetch)

**Priority**: high once all 7 families exist. Low until then. This is the "grand finale" — the polished, distributable artifact that justifies the entire SKLD-bench content workstream + v2.1 engine build.

**Not this**: do NOT build the plugin wrapper before all 7 composites are rich and validated. Packaging a half-done set of skills as a plugin is worse than no plugin, because it sets a quality floor and anchors user expectations to an incomplete product.
