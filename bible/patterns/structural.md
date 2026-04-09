# Structural Patterns

*Empirically-validated patterns for Skill directory and SKILL.md structure.*

## Confirmed Patterns

### P-STRUCT-001: Progressive disclosure 3-level model
Every Skill should exploit Claude's three-level disclosure model:
- **Level 1 (metadata, ~100 tokens)**: `name` + `description`. Always loaded at startup.
- **Level 2 (instructions, <5,000 tokens)**: the SKILL.md body. Loaded when the Skill is triggered.
- **Level 3 (resources, variable)**: `scripts/`, `references/`, `assets/`. Loaded on demand.

**Evidence**: Anthropic's own documentation defines this model. Skills that front-load everything into SKILL.md waste context budget on content Claude doesn't need for most invocations.

### P-STRUCT-002: Keep references one level deep from SKILL.md
Claude can only preview deeply-nested files with `head -100`. Reference files should be directly reachable from SKILL.md, not nested inside other references.

**Evidence**: `docs/skills-research.md` §2 — "keep references one level deep from SKILL.md — Claude may only preview files referenced from other referenced files."

### P-STRUCT-003: Use `${CLAUDE_SKILL_DIR}` for all paths
Never hardcode paths. Use the `${CLAUDE_SKILL_DIR}` variable so Skills remain portable across Claude Code, Agent SDK, and Skills API environments.

**Evidence**: Research report §6 — "Use `${CLAUDE_SKILL_DIR}` for all paths (never hardcode)."

### P-STRUCT-004: SKILL.md body under 500 lines
Frontier LLMs follow ~150-200 total instructions. Claude Code's system prompt consumes ~50. Skills sharing the budget degrade uniformly as count rises. Under 500 lines keeps the Skill within budget while leaving headroom for co-loaded Skills.

**Evidence**: Research report §4 — "Keep SKILL.md under 500 lines (~5,000 words)."

### P-STRUCT-005: Validate reference paths in CI
A community audit of 192 skill setups found **73% had failures**, primarily from broken/missing references — not bad instructions. Every reference path in SKILL.md should be checked before shipping.

**Evidence**: Research report §8 — "The primary cause was broken/missing references — not bad instructions."

---

*Seeded from Deep Research report. Will be validated and refined through SkillForge evolution runs.*
