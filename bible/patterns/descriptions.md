# Description Patterns

*Empirically-validated patterns for writing Skill descriptions that trigger reliably.*

## Confirmed Patterns

### P-DESC-001: Front-load within 250 characters
Descriptions are truncated to 250 characters in the skill listing during the routing decision. Place capability statement + primary trigger conditions within the first 250 characters. Secondary triggers and exclusions can follow.

**Evidence**: Anthropic's routing mechanism presents only truncated descriptions during skill selection. Keywords beyond 250 chars may never influence activation.

### P-DESC-002: Use "pushy" trigger language
Anthropic's own skill-creator documentation states Claude "undertriggers" by default. Combat this by listing adjacent concepts explicitly and including "even if they don't explicitly ask for [skill name]."

**Example**:
```
# Weak (undertriggers):
description: "How to build a dashboard to display internal data."

# Strong (reliably triggers):
description: "How to build a dashboard to display internal data. Use when 
user mentions dashboards, data visualization, internal metrics, or wants to 
display any kind of company data, even if they don't explicitly ask for a 'dashboard.'"
```

**Evidence**: Anthropic's skill-creator source code explicitly recommends this pattern. Applied to 6 internal document skills, improved triggering on 5 of 6.

### P-DESC-003: Two-part structure — capability + trigger conditions
Every description should contain (1) what the skill does and (2) when to use it with "Use when..." language.

**Evidence**: Vague descriptions achieve ~20% activation. Optimized descriptions with "Use when" patterns achieve ~50%. With examples in SKILL.md body, 72-90%.

### P-DESC-004: Explicit exclusion clauses
Include "NOT for [X], [Y], or [Z]" to reduce false positive activations. Be specific about adjacent capabilities the skill does NOT handle.

**Evidence**: Community testing shows false triggers are as damaging as missed triggers — they waste context budget and confuse the workflow.

### P-DESC-005: Match user vocabulary, not technical terminology
Descriptions should use the words users actually type, not formal category names. "When user asks about charts, graphs, or data pictures" outperforms "For data visualization tasks."

**Evidence**: Routing is LLM-based semantic matching against user prompts. User vocabulary alignment directly increases match probability.

---

*These patterns are seeded from the initial Deep Research report. They will be validated and refined as SkillForge generates evolution data.*
