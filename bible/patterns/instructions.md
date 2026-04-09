# Instruction Patterns

*Empirically-validated patterns for writing Skill instructions that Claude follows consistently.*

## Confirmed Patterns

### P-INST-001: Examples beat rules
Adding 2-3 diverse input/output examples improved Skill output quality from 72% to 90% in testing across 200+ prompts. Examples teach format and style more effectively than declarative rules.

**Recommendation**: Always include 2-3 examples. One typical case, one edge case, one near-miss. Input/output pairs are the most effective format.

### P-INST-002: Numbered steps for ordered workflows
Numbered steps produce highest instruction adherence for sequential operations. Bullets work for non-sequential options. Prose for motivation and context.

**Evidence**: Community consensus and Anthropic best practices documentation.

### P-INST-003: Don't teach what Claude already knows
Run tasks without the skill first. Document where Claude fails. Then write minimal instructions to close those specific gaps. Skills that teach Claude things it already knows can actively degrade output quality by overriding better base behavior.

**Evidence**: Anthropic's evaluation framework explicitly tests "skill vs. no skill" — if the base model passes at comparable rates, the skill is redundant or harmful.

### P-INST-004: Scripts for deterministic operations
Script code never enters the context window — only stdout/stderr. If a task is deterministic (sorting, validation, format checking, data extraction), put it in a script. Regenerating via token generation is expensive and unreliable.

**Evidence**: Anthropic's engineering blog: "Sorting a list via token generation is far more expensive than simply running a sorting algorithm." PDF skill bundles Python scripts that extract form fields at zero context cost.

### P-INST-005: Keep SKILL.md under 500 lines
The total instruction budget across all loaded context is ~150-200 instructions. Claude's system prompt consumes ~50. As instruction count rises, quality degrades uniformly across ALL instructions — not just the new ones. Stay under 500 lines (~5,000 words).

**Evidence**: Research on frontier LLM instruction following capacity. Community testing confirms degradation patterns.

### P-INST-006: Use headers (H2/H3) as structural markers
Claude relies on formatting hierarchy to parse instructions. Headers are not decorative — they're structural markers that help Claude navigate the instruction space.

**Evidence**: Anthropic best practices documentation and community testing.

### P-INST-007: Bundle repeated helper scripts
If test runs consistently show Claude writing the same helper script from scratch, that's a signal to bundle the script in `scripts/`. Bundled scripts cost zero tokens. Regenerated scripts cost many tokens and may be subtly different each time.

**Evidence**: Anthropic's skill-creator explicitly checks for this pattern during evaluation.

---

*Seeded from Deep Research report. Will be validated and refined through SkillForge evolution runs.*
