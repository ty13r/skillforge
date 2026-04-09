# Progressive Disclosure Patterns

*How to split content across Level 1 (metadata), Level 2 (SKILL.md body), and Level 3 (references/scripts/assets).*

## Confirmed Patterns

### P-PD-001: Level 1 (description) is for routing, not content
The `description` field has one job: make Claude decide whether to load the Skill. Pack it with capability statement, trigger conditions, and exclusions. Do NOT put actual instructions there — they won't execute, they only influence routing.

**Evidence**: Research report §5 — routing uses pure LLM reasoning over description text. The body never enters context until after routing.

### P-PD-002: Level 2 (SKILL.md body) holds the quick-start + routing to references
The body should contain: (1) quick-start workflow, (2) decision routing to reference files ("For X, read references/x.md"), (3) core constraints, (4) 2-3 examples. Anything longer belongs in references/.

**Evidence**: Research report §4 — "The body should contain quick-start instructions, decision routing to reference files, core constraints, and critical rules."

### P-PD-003: Level 3 (references/) holds details loaded on demand
Move detailed API docs, schemas, templates, large example libraries, and domain-specific references to `references/` files. Claude loads them only when SKILL.md explicitly points at them.

**Evidence**: Research report §6 — "Reference content enters context and consumes tokens; asset files (`assets/`) are referenced by path only at zero token cost until explicitly read."

### P-PD-004: Reference files over 100 lines need a table of contents
Claude previews long files with `head -100`. Put a TOC in the first 100 lines so Claude can decide whether to read the rest.

**Evidence**: Research report §4 — "Reference files over 100 lines should include a table of contents."

### P-PD-005: Assets are path-referenced, zero token cost
Templates, schemas, fonts, and other files referenced by path (not read into context) belong in `assets/`. They cost nothing until Claude explicitly reads them.

**Evidence**: Research report §6 — "asset files (`assets/`) are referenced by path only at zero token cost until explicitly read."

---

*Seeded from Deep Research report. Will be validated and refined through SkillForge evolution runs.*
