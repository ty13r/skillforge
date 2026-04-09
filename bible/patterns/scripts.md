# Script Patterns

*Empirically-validated patterns for using scripts effectively inside Skills.*

## Confirmed Patterns

### P-SCRIPT-001: Scripts for deterministic operations only
**Script code never enters the context window — only stdout/stderr does.** Use scripts for sorting, form extraction, data validation, XML manipulation, format checking — anything deterministic. Use instructions for flexible reasoning and judgment.

**Evidence**: Anthropic engineering blog — "Sorting a list via token generation is far more expensive than simply running a sorting algorithm." Scripts can be arbitrarily large without impacting token usage.

### P-SCRIPT-002: Bundle repeated helper scripts
If evaluation runs consistently show Claude writing the same helper script from scratch, that's a signal to bundle it. Bundled scripts cost zero tokens. Regenerated scripts cost many tokens and may be subtly different each time.

**Evidence**: Research report §11 — "Not bundling helper scripts" is a top-10 mistake. The skill-creator explicitly checks for this pattern during evaluation.

### P-SCRIPT-003: Scripts must use `${CLAUDE_SKILL_DIR}` paths
Never hardcode paths in scripts. Use `${CLAUDE_SKILL_DIR}` so the script works across Claude Code, Agent SDK, and Skills API environments.

**Evidence**: Research report §6 — "Use `${CLAUDE_SKILL_DIR}` for all paths (never hardcode)."

### P-SCRIPT-004: Check package availability at script start
Claude Code has full filesystem and network access. The API sandbox has no network and cannot install packages at runtime. Scripts should check for required packages upfront and fail with a clear message, not mid-execution.

**Evidence**: Research report §6 — "Check available packages at script start. Avoid runtime package installation."

### P-SCRIPT-005: Prefer scripts for output validation
A validate.sh or validate.py script that checks the Skill's output is worth its weight in instructions. Validation caught errors that instruction-only approaches missed in community testing.

**Evidence**: Golden template includes `scripts/validate.sh` by default for this reason.

---

*Seeded from Deep Research report. Will be validated and refined through SkillForge evolution runs.*
