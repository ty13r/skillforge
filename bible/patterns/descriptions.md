# Description Patterns

*Empirically-validated patterns for writing Skill descriptions that trigger reliably.*

## Confirmed Patterns

### P-DESC-001: Front-load within 250 characters

**Finding**: Descriptions are hard-capped at 250 characters in the skill listing regardless of total budget. Any content beyond 250 characters may be truncated during the initial routing decision.

**Evidence**: Research report §5 — "Descriptions are hard-capped at 250 characters in the skill listing regardless of total budget." Also flagged in §11 as one of the top "things most people get wrong."

**How to apply**: Place capability statement + primary trigger keywords in the first 250 characters. Secondary triggers and extended exclusions can follow, but cannot be relied on for routing.

**Example**:
```
description: >-
  Builds React dashboards with charts, KPI tiles, and filters.
  Use when user mentions dashboards, data viz, metrics, reports,
  charts, or graphs, even if they don't say "dashboard."
```

### P-DESC-002: The "pushy" trigger pattern

**Finding**: Claude has a tendency to "undertrigger" skills. The fix is deliberately "pushy" description language that expands the trigger surface.

**Evidence**: Research report §5 quoting Anthropic's skill-creator: "Currently Claude has a tendency to 'undertrigger' skills — to not use them when they'd be useful. To combat this, please make the skill descriptions a little bit 'pushy.'" Applied to Anthropic's own 6 document skills, improved triggering on 5 of 6.

**How to apply**: List adjacent concepts the user might mention, and include the phrase "even if they don't explicitly ask for..." to cover indirect requests.

**Example**:
```
description: "How to build a dashboard to display internal data. Make sure to use
this skill whenever the user mentions dashboards, data visualization, internal
metrics, or wants to display any kind of company data, even if they don't
explicitly ask for a 'dashboard.'"
```

### P-DESC-003: Two-part structure — capability + "Use when"

**Finding**: Every description should contain (1) what the skill does (capability) and (2) when to use it (trigger conditions using explicit "Use when..." language).

**Evidence**: Research report §5 — "Empirical results: vague descriptions achieve ~20% activation, optimized descriptions with 'Use when' patterns achieve ~50%, and descriptions plus examples in SKILL.md achieve 72–90%."

**How to apply**: Sentence 1 states capability. Sentence 2 begins "Use when..." and lists concrete trigger conditions in user vocabulary.

### P-DESC-004: Explicit exclusion clauses

**Finding**: Descriptions should include explicit "NOT for..." clauses to reduce false-positive activations.

**Evidence**: Research report §5 — "Include explicit exclusion clauses: 'NOT for backend logic, API design, database schema, deployment, or server-side code.'" Cross-reference §11 where "The Noisy Skill" that fires for everything is listed as a known failure pattern.

**How to apply**: After triggers, append "NOT for X, Y, or Z" naming adjacent capabilities the skill explicitly does not handle. Being specific about exclusions directly reduces noise.

### P-DESC-005: Describe what it *does*, not what it *is*

**Finding**: Descriptions phrased as identity statements ("A frontend design agent") undertrigger. Descriptions phrased as tasks ("Use for frontend UI design tasks — buttons, cards, forms, navbars, modals") activate reliably.

**Evidence**: Research report §11 #2 — "Writing descriptions about what the skill *is* instead of what it *does*."

**How to apply**: Use verbs and task nouns. Avoid "is a", "is an agent that", "helps with". Prefer "Builds X", "Generates Y", "Use for Z".

### P-DESC-006: Match user vocabulary, not taxonomy

**Finding**: Routing is LLM semantic matching against the user's literal prompt. Alignment with the exact words users type outperforms formal category names.

**Evidence**: Research report §2 — "Claude's transformer forward pass evaluates user intent against every skill description simultaneously." §8 PPTX skill example lists "deck," "slides," "presentation," and the ".pptx" filename explicitly.

**How to apply**: List filename extensions, colloquialisms, and synonyms a user would naturally say. Enumerate them inline in the description.

### P-DESC-007: Descriptions evolve on a separate track from the body

**Finding**: Descriptions are read at routing time by pure LLM reasoning; instructions are executed post-activation. They serve fundamentally different functions and should be optimized independently.

**Evidence**: Research report §12 SkillForge section — "The description and instruction body should evolve separately since they serve fundamentally different functions."

**How to apply**: Treat description mutation operators and instruction mutation operators as orthogonal. A description change should not force a body change (and vice versa) unless the skill's capability itself shifts.

## Anti-Patterns

### AP-DESC-001: The Silent Skill
Description too weak or vague to ever trigger. Research report §5 documents a skeptical test where a review skill achieved 0/20 correct activations due to a weak description.

### AP-DESC-002: The Noisy Skill
Description so broad or keyword-stuffed that it fires for everything, polluting unrelated workflows. Mitigation: tighten capability statement, add explicit NOT-for exclusions (P-DESC-004).

### AP-DESC-003: Burying keywords past 250 characters
Critical trigger terms placed after the 250-char cutoff are invisible to the router. Always put the strongest trigger keywords in the first sentence.
