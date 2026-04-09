# Progressive Disclosure Patterns

*How to split content across Level 1 (metadata), Level 2 (SKILL.md body), and Level 3 (resources).*

## Confirmed Patterns

### P-DISC-001: The three-level loading model

**Finding**: Skills load across three distinct levels with different triggers and token costs. Understanding this model is a prerequisite for every other structural decision.

**Evidence**: Research report §2 progressive disclosure table.

**How to apply**:

| Level | When loaded | Cost | Content |
|-------|-------------|------|---------|
| **L1 Metadata** | Always at startup | ~100 tokens/skill | `name` + `description` from frontmatter |
| **L2 Instructions** | When the skill is triggered | Under 5,000 tokens recommended | Full SKILL.md markdown body |
| **L3 Resources** | As needed during execution | Variable / unlimited | `scripts/`, `references/`, `assets/` |

Once L2 is invoked, the rendered SKILL.md enters the conversation as a single message and **stays for the rest of the session** — Claude does not re-read the file on later turns.

### P-DISC-002: L1 description is for routing, not content

**Finding**: The `description` field has one job: make Claude decide whether to load the skill. Routing uses pure LLM reasoning over description text; no embeddings, no classifier, no keywords.

**Evidence**: Research report §2 — "There is no embedding-based matching, no classifier, and no keyword algorithm at the code level... Claude's transformer forward pass evaluates user intent against every skill description simultaneously." §5 — "description quality is the single largest lever for activation reliability."

**How to apply**: Put capability + triggers + exclusions in the description. Never put actual workflow instructions there — they don't execute at routing time, and the 250-character truncation will eat them anyway. See `descriptions.md`.

### P-DISC-003: L2 body holds quick-start + decision routing

**Finding**: The SKILL.md body should contain quick-start instructions, decision routing to reference files, core constraints, and critical rules — not detailed API docs, schemas, or large example libraries.

**Evidence**: Research report §4 — "The body should contain quick-start instructions, decision routing to reference files, core constraints, and critical rules. Move detailed API docs, schemas, templates, large example libraries, and domain-specific references to `references/` files."

**How to apply**: Structure the body as: YAML frontmatter → H1 title → Quick Start → Workflow (numbered steps) → conditional loading instructions pointing to `references/` → 2–3 examples → Gotchas → Out-of-scope. Keep it under 500 lines.

**Example decision routing**:
```markdown
**For Python implementations, also load:**
- [Python Guide](./references/python_mcp_server.md)

**For TypeScript implementations, also load:**
- [TypeScript Guide](./references/node_mcp_server.md)
```

### P-DISC-004: L3 references enter context; L3 assets do not

**Finding**: Inside Level 3 there is a critical distinction. Reference files enter the context window (and cost tokens) the moment Claude reads them. Asset files are referenced by path only — zero token cost until explicitly read.

**Evidence**: Research report §6 — "Reference content enters context and consumes tokens; asset files (`assets/`) are referenced by path only at zero token cost until explicitly read." §1 — "`assets/` are path-referenced only at zero token cost until explicitly read."

**How to apply**: Content Claude must *read and reason about* goes in `references/`. Content Claude only *points at* (templates passed to a script, font files, schemas consumed by a tool) goes in `assets/`. Scripts in `scripts/` also cost zero context — see `scripts.md`.

### P-DISC-005: One level deep from SKILL.md — 73% broken-ref rule

**Finding**: Keep all references one level deep from SKILL.md. A 192-file community audit found **73% of skill setups had failures**, primarily from broken/missing references. A second tool (`pulser`) found **61% of skills had problems**, mostly broken refs.

**Evidence**: Research report §4 — "Critical structural rule: keep references one level deep from SKILL.md — Claude may only preview files referenced from other referenced files (using `head -100`)." §8 — "A 192-file community audit found 73% of setups had failures, and the primary cause was broken/missing references — not bad instructions." §11 #4 reiterates it.

**How to apply**: Every `references/*.md` file must be directly linked from SKILL.md, not from another reference. Validate all reference paths in CI (SkillForge's sandbox validator enforces this pre-run). See `structural.md` P-STRUCT-005/006.

### P-DISC-006: Long reference files need a table of contents

**Finding**: Reference files over 100 lines should include a table of contents. Claude previews long files using `head -100`, so the TOC must be in the first 100 lines to be discoverable.

**Evidence**: Research report §4 — "Reference files over 100 lines should include a table of contents."

**How to apply**: First section of any reference file >100 lines is a markdown TOC listing the H2/H3 headers with one-line summaries. This lets Claude decide whether to read the rest after a single preview.

### P-DISC-007: L2 persists for the whole session

**Finding**: Once invoked, SKILL.md content enters the conversation as a single message and stays for the remainder of the session. Claude does not re-read the file on later turns. During auto-compaction, Claude Code re-attaches the most recent invocation after the summary.

**Evidence**: Research report §2 — "Once invoked, the rendered SKILL.md content enters the conversation as a single message and stays for the rest of the session."

**How to apply**: Do not rely on Claude "re-reading" SKILL.md mid-session. State anything critical up front. If a change is needed mid-session, emit it through a script output or a references/ read, not by expecting a re-parse of the SKILL.md body.

### P-DISC-008: Split content by load probability

**Finding**: The goal of progressive disclosure is to minimize expected context cost. Content needed on every invocation belongs in L2 (SKILL.md body). Content needed conditionally (e.g., only for Python implementations) belongs in L3 references, with a pointer from L2.

**Evidence**: Research report §2 progressive disclosure table and §4 reference loading pattern.

**How to apply**: For each piece of content, ask "what fraction of invocations will need this?" If near 100%, put it in SKILL.md. If conditional, move it to `references/` and add a one-line pointer in the decision routing section of SKILL.md.

## Anti-Patterns

### AP-DISC-001: Inlining everything into SKILL.md
Dumping all domain details into the body breaks the 500-line ceiling, blows the instruction budget (P-INST-006), and drags Claude's attention away from the core workflow.

### AP-DISC-002: Nested references
References that link to further references past one level are effectively unreachable. See P-DISC-005 and the 73% broken-ref finding.

### AP-DISC-003: Putting instructions in the description
Description is routing-only. Instructions there never execute — and they burn the 250-character budget that should be teaching the router when to fire.
