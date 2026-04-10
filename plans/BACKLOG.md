# SkillForge Backlog

Items carried over from PLAN-V1.2. These are not blockers for v2.0 but remain valuable work. Items may be absorbed into v2.0 phases where they overlap with the new architecture.

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

## Rich Variant Cards (Remaining Polish)

Most of this shipped in the QA session. Remaining items:
- Streaming trace: real-time output snippets in variant cards
- Diff view against parent skill in the skill modal
- Full rename sweep: any remaining "Competitor" → "Variant" labels
