# The Claude Skills Bible

**An empirically-derived, continuously-updated guide to writing effective Claude Agent Skills.**

Every finding in this document was discovered through evolutionary optimization — not hand-tuning, not guesswork. SkillForge breeds populations of Skills, competes them against real challenges, and measures what works. The patterns that survive across generations and across domains end up here.

## How This Knowledge Is Generated

1. **SkillForge runs an evolution** — 5+ candidate Skills compete across 3+ challenges over 3+ generations
2. **The Breeder agent analyzes traces** — which instructions were followed, which were ignored, which correlated with higher fitness
3. **The Learning Log captures findings** — "imperative phrasing was followed 80% more than descriptive phrasing"
4. **Findings are published here** — each finding includes the specialization, generation, fitness delta, and trace evidence
5. **Patterns are promoted** — findings that replicate across 3+ independent evolution runs become patterns
6. **Anti-patterns are documented** — patterns that consistently reduce fitness across runs get flagged

## Directory Structure

```
bible/
├── README.md              # This file
├── findings/              # Individual findings from evolution runs
│   ├── 001-*.md           # Each finding: what was observed, evidence, fitness impact
│   ├── 002-*.md
│   └── ...
├── patterns/              # Proven patterns (promoted from findings after 3+ confirmations)
│   ├── structural.md      # What SKILL.md structures work best
│   ├── descriptions.md    # Description patterns with measured trigger rates
│   ├── instructions.md    # Instruction styles with adherence scores
│   ├── scripts.md         # When and how to use scripts effectively
│   └── progressive-disclosure.md  # Optimal Level 2 vs Level 3 splitting
├── anti-patterns/         # Patterns that consistently reduce fitness
│   └── ...
└── evolution-log.md       # Chronological log of all runs and key outcomes
```

## Finding Format

Each finding in `findings/` follows this structure:

```markdown
# Finding {NNN}: {Short title}

**Discovered**: {date}
**Evolution Run**: {run_id}
**Specialization**: {what was being evolved}
**Generation**: {which generation}
**Fitness Delta**: {+/- change attributed to this pattern}
**Confirmations**: {count of independent runs confirming this}
**Status**: finding | pattern | anti-pattern

## Observation
{What was observed during evolution}

## Evidence
{Trace data, fitness scores, specific SKILL.md diffs}

## Mechanism
{Why this works/fails — the Breeder's diagnostic explanation}

## Recommendation
{Concrete, actionable guidance for Skill authors}
```

## How to Use This

**If you're writing a Skill**: read `patterns/` first. These are battle-tested. Start from the golden template (`docs/golden-template.md`) and apply relevant patterns.

**If you're running SkillForge**: the Spawner automatically incorporates published patterns into gen 0 populations. The Breeder reads the bible before proposing mutations.

**If you're contributing**: run SkillForge on a new specialization and submit the findings via PR. Findings that replicate across 3+ runs from independent contributors get promoted to patterns.

## Current Status

*This bible is bootstrapping. Initial findings will be populated from SkillForge's first evolution runs. As the platform processes more runs across more domains, the patterns will become increasingly robust and generalizable.*

---

*Generated and maintained by [SkillForge](https://github.com/ty13r/skillforge) — evolving Agent Skills through natural selection.*
