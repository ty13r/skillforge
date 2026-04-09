# Instruction Patterns

*Empirically-validated patterns for writing the SKILL.md instruction body.*

## Confirmed Patterns

### P-INST-001: 500-line ceiling on SKILL.md body

**Finding**: Keep the SKILL.md body under 500 lines (~5,000 words / under 5,000 tokens).

**Evidence**: Research report §4 — "Keep SKILL.md under 500 lines (~5,000 words). The body should contain quick-start instructions, decision routing to reference files, core constraints, and critical rules."

**How to apply**: Quick-start + workflow + core rules only. Push detailed API docs, schemas, templates, and extended example libraries to `references/` files loaded on demand.

### P-INST-002: 2–3 diverse I/O examples are mandatory

**Finding**: Adding examples improved activation and output quality from **72% to 90%** in empirical testing across 200+ prompts. Two to three diverse, representative examples is the sweet spot.

**Evidence**: Research report §4 — "Empirical testing across 200+ prompts showed adding examples improved activation and output quality from 72% to 90%. Input/output pairs are the recommended format... Two to three diverse, representative examples is the sweet spot."

**How to apply**: Include an `## Examples` section with 2–3 input/output pairs. Make them diverse (normal case, edge case, near-miss). Use realistic conversational user language for inputs. Community consensus cited in the report: "Claude learns from examples, not descriptions — examples should be longer than your rules section."

**Example**:
```markdown
## Examples

**Example 1:**
Input: "make me a deck about Q3 revenue"
Output: [expected result with specific format]

**Example 2 (edge case):**
Input: "add a slide to presentation.pptx that explains the new pricing"
Output: [expected result]
```

### P-INST-003: Numbered steps for ordered workflows

**Finding**: Numbered steps produce the highest adherence for ordered workflows. Bullets work for non-sequential options. Prose is best for context and motivation.

**Evidence**: Research report §4 — "Numbered steps produce highest adherence for ordered workflows. Bullets work for presenting non-sequential options. Prose is best for context and motivation."

**How to apply**: Use `### Step 1:`, `### Step 2:` for the core workflow. Each step has an imperative verb + concrete action. Use bullets for "any of these options" and prose only for *why* context.

### P-INST-004: H2/H3 headers as structural markers

**Finding**: Claude relies on formatting hierarchy to parse instructions. Headers are essential, not decorative.

**Evidence**: Research report §4 — "Headers (H2/H3) are essential — Claude relies on formatting hierarchy to parse instructions."

**How to apply**: Every major section gets an H2. Each step in a workflow gets an H3. Do not flatten structure into a wall of prose.

### P-INST-005: Degrees-of-freedom framework

**Finding**: The format should match the rigidity of the task. High-freedom tasks get goals + constraints (prose). Medium-freedom tasks get pseudocode or templates. Low-freedom critical operations get exact scripts.

**Evidence**: Research report §4 — "The key framework is 'degrees of freedom': high-freedom tasks get goals and constraints (prose), medium-freedom tasks get pseudocode/templates, low-freedom critical operations get exact scripts."

**How to apply**: Before writing instructions, classify each task. If it must run identically every time, make it a script call. If it has a few variations, provide a template. If it needs judgment, describe goals.

### P-INST-006: The ~150–200 instruction budget

**Finding**: Frontier thinking LLMs can follow ~150–200 total instructions reliably. Claude Code's system prompt already consumes ~50. As instruction count rises, quality degrades uniformly — Claude doesn't just drop the new ones, it drops random ones throughout.

**Evidence**: Research report §4 — "Research shows frontier thinking LLMs can follow ~150–200 total instructions with reasonable consistency. Claude Code's system prompt already consumes ~50 of those... As instruction count rises, quality degrades uniformly across all instructions."

**How to apply**: Minimize total imperatives. Remove MUSTs for non-critical behavior. Every instruction should close a specific observed gap.

### P-INST-007: Close the gap, don't teach the baseline

**Finding**: Skills that teach Claude things it already knows can actively degrade output quality. The base model is very capable already.

**Evidence**: Research report §11 #6 — "Over-investing in instructions Claude already follows... Skills that teach Claude things it already knows can actively degrade output quality." Cross-reference §7 model absorption detection: run evals with and without the skill loaded.

**How to apply**: Before adding an instruction, verify Claude fails without it. Never instruct on capabilities the model handles natively. Periodically re-evaluate — skills written for older models may be redundant or harmful on newer ones.

### P-INST-008: Imperative verification language brings activation to 100%

**Finding**: Strengthening skill instructions with imperative language and explicit verification steps brought activation to 100% in controlled experiments targeting execution failures.

**Evidence**: Research report §8 — "The tested mitigation for execution failure — strengthening skill instructions with imperative language and verification steps — brought activation to 100% in controlled experiments."

**How to apply**: Use imperative verbs ("Run", "Validate", "Read") not hedged suggestions ("You might"). Add explicit verification steps after execution steps. Follow the PPTX skill pattern: "USE SUBAGENTS — even for 2-3 slides. You've been staring at the code and will see what you expect, not what's there."

## Anti-Patterns

### AP-INST-001: Oppressive MUSTs for non-critical behavior
Research report §4 quotes the skill-creator: "Rather than put in fiddly overfitty changes, or oppressively constrictive MUSTs, if there's some stubborn issue, you might try branching out and using different metaphors." Overusing MUST eats the instruction budget.

### AP-INST-002: More than ~3 examples
Too many examples bloat token budget and can create unintended patterns. Stick to 2–3 diverse examples (P-INST-002).

### AP-INST-003: Verbose restatements of things Claude knows
Wastes context and risks degrading native behavior (P-INST-007). Claude ignores "overly verbose explanations of things it already knows" per §4.
