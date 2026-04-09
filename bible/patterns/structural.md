# Structural Patterns

*Empirically-validated patterns for Skill directory layout, naming, and portable structure.*

## Confirmed Patterns

### P-STRUCT-001: Canonical directory layout

**Finding**: A Skill is a directory containing a required `SKILL.md` plus optional `scripts/`, `references/`, and `assets/` subdirectories. Each serves a distinct role in the progressive disclosure model.

**Evidence**: Research report §1 directory structure table and §12 golden template.

**How to apply**:
```
my-skill/
├── SKILL.md          # Required: YAML frontmatter + Markdown instructions
├── scripts/          # Executable code — runs via bash, output only enters context
├── references/       # Documentation — loaded into context on demand
└── assets/           # Templates, schemas, fonts — path-referenced, zero token cost
```

The architectural distinction: `scripts/` code never enters context (only stdout/stderr), `references/` content enters context when Claude reads the file, `assets/` are path-referenced only. See also `progressive-disclosure.md` and `scripts.md`.

### P-STRUCT-002: Name regex and directory match

**Finding**: The `name` must match the parent directory exactly. The regex `^[a-z0-9]+(-[a-z0-9]+)*$` enforces lowercase alphanumeric with single hyphens — no leading/trailing hyphens, no consecutive hyphens. Max 1–64 characters. Must not contain "anthropic" or "claude".

**Evidence**: Research report §1 frontmatter table and §1 naming constraints — "The name must match the parent directory name exactly."

**How to apply**: Pick a kebab-case slug. Use it as both the directory name and the `name:` field. Validate at spawn time; the Spawner/Breeder must never emit a name that fails the regex.

### P-STRUCT-003: Three-level progressive disclosure

**Finding**: Skills load in three distinct levels with different token costs and triggers.

**Evidence**: Research report §2 progressive disclosure table.

**How to apply**:

| Level | When loaded | Token cost | Content |
|-------|------------|------------|---------|
| L1: Metadata | Always at startup | ~100 tokens/skill | `name` + `description` |
| L2: Instructions | When triggered | Under 5,000 tokens | Full SKILL.md body |
| L3: Resources | As needed | Variable | scripts/, references/, assets/ |

Every structural decision should ask: "which level does this belong in?" Content loaded into L1 that belongs in L3 wastes budget; content in L3 that belongs in L1 never triggers. See `progressive-disclosure.md`.

### P-STRUCT-004: Use `${CLAUDE_SKILL_DIR}` for every path

**Finding**: Never hardcode paths. Use the `${CLAUDE_SKILL_DIR}` variable for portability across Claude Code, the Agent SDK, and the Skills API.

**Evidence**: Research report §6 — "Use `${CLAUDE_SKILL_DIR}` for all paths (never hardcode)." Also listed among dynamic context substitutions in §2.

**How to apply**: Every `Read`, `Run`, or file reference uses `${CLAUDE_SKILL_DIR}/references/...` or `${CLAUDE_SKILL_DIR}/scripts/...`. Path strings like `./references/foo.md` or absolute paths break portability.

### P-STRUCT-005: References one level deep from SKILL.md

**Finding**: Keep all references one level from SKILL.md. Claude may only preview deeply-nested files (referenced from other referenced files) with `head -100`, which is unreliable.

**Evidence**: Research report §4 — "Critical structural rule: keep references one level deep from SKILL.md." Also §11 #4 — "Nesting references more than one level deep."

**How to apply**: SKILL.md links directly to every reference file that might be needed. References should not themselves link to further references as a primary access path. For long reference files (>100 lines), include a table of contents at the top.

### P-STRUCT-006: Validate reference paths in CI

**Finding**: A community audit of 192 skill setups found **73% had failures**, primarily from broken/missing references — not bad instructions. A second tool (`pulser`) found **61% of skills had problems** mostly from broken refs.

**Evidence**: Research report §8 — "A 192-file community audit found 73% of setups had failures, and the primary cause was broken/missing references — not bad instructions."

**How to apply**: Every reference path in SKILL.md (and in referenced scripts) must be validated at build / spawn / promotion time. The SkillForge sandbox validator enforces this before a competitor runs.

### P-STRUCT-007: YAML frontmatter: only `description` is functionally required

**Finding**: Of all frontmatter fields, only `description` is functionally required for routing. All others have sensible defaults.

**Evidence**: Research report §1 — "Only `description` is functionally required — all other fields have sensible defaults."

**How to apply**: Don't clutter frontmatter with unused fields. `name`, `description`, and `allowed-tools` are typically enough. Add `argument-hint`, `version`, or `license` only when they serve a specific purpose.

### P-STRUCT-008: Keep `allowed-tools` in frontmatter even though the SDK ignores it

**Finding**: The `allowed-tools` frontmatter field works in Claude Code CLI but is **ignored by the Agent SDK**. Exported Skills still need it for Claude Code portability.

**Evidence**: Research report §2 — "The `allowed-tools` frontmatter field only works in Claude Code CLI directly — it is ignored by the Agent SDK." §9 — "the `allowed-tools` frontmatter field is ignored by the SDK."

**How to apply**: Keep it in frontmatter for portability. In the SDK, control tool access via the main `allowed_tools` option paired with `permission_mode="dontAsk"`.

## Anti-Patterns

### AP-STRUCT-001: Hardcoded paths
Absolute or relative paths break portability and fail silently when the Skill is relocated. Always use `${CLAUDE_SKILL_DIR}` (P-STRUCT-004).

### AP-STRUCT-002: Nested references
References linking to further references past one level become unreachable for full loading (P-STRUCT-005).

### AP-STRUCT-003: Name/directory mismatch
If `name:` in frontmatter doesn't exactly match the directory name, the Skill will fail to load. Enforce equality at spawn time.
