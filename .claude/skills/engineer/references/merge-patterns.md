# Merge Patterns

Concrete patterns the Engineer applies when weaving capability variants into the foundation skeleton. Each pattern has a before sketch, an after sketch, and the rule that triggers it.

## 1. Weave-under-header

**When:** A capability variant has an H3 subsection that belongs under an existing foundation H2 — typically a new sub-step of the Workflow.

**Before (foundation):**
```markdown
## Workflow
### Step 1: Gather Context
...
### Step 2: Execute
Run the main helper.
```

**Before (capability "mock-strategy"):**
```markdown
## Workflow
### Mock external dependencies
Create fakes for all IO before running tests.
```

**After (composite):**
```markdown
## Workflow
### Step 1: Gather Context
...
### Step 2: Execute
Run the main helper.
### Step 3: Mock external dependencies
Create fakes for all IO before running tests.
```

**Rule:** renumber the injected step to continue the foundation's sequence.

## 2. Append-new-section

**When:** A capability adds a whole H2 block that has no overlap with anything in the foundation — e.g. a new "Performance Considerations" section.

**Before (foundation):**
```markdown
## Workflow
...
## Gotchas
...
```

**Before (capability "perf-tuning"):**
```markdown
## Performance Considerations
Profile before optimizing; prefer vectorized ops.
```

**After:**
```markdown
## Workflow
...
## Performance Considerations
Profile before optimizing; prefer vectorized ops.
## Gotchas
...
```

**Rule:** append between Workflow and Gotchas. Never insert new H2 above Quick Start or the main Workflow.

## 3. Highest-fitness-wins

**When:** Two variants provide contradictory instructions under a header with the same text.

**Example:** foundation says "use `pytest.fixture(scope='module')`" (fitness 0.80); capability says "use `pytest.fixture(scope='function')`" (fitness 0.78).

**Rule:** keep the foundation's line (higher fitness). Log the losing instruction to `alternatives.md` in the composite, with variant name, fitness, and the rationale "conflict resolution — lower fitness". The `alternatives.md` file is informational, not loaded at runtime.

**After (alternatives.md):**
```markdown
# Alternatives considered during assembly

## Step 2 fixture scope
- **Chosen:** `scope='module'` from foundation (fitness 0.80)
- **Rejected:** `scope='function'` from capability `fixture-scope-b` (fitness 0.78)
- **Reason:** conflict resolution — lower fitness
```

## 4. Script-deconflict-rename

**When:** Two or more variants ship a script with the same filename (commonly `validate.sh` or `main_helper.py`).

**Before:**
```
foundation/scripts/validate.sh
capability-mock/scripts/validate.sh
```

**After:**
```
composite/scripts/validate.sh              # foundation's, unchanged
composite/scripts/validate_mock.sh         # capability's, renamed by dimension slug
```

**Rule:** keep the foundation's filename. Rename other variants' scripts to `<stem>_<dimension>.<ext>` using the variant's dimension slug. Then grep the composite SKILL.md body for every `${CLAUDE_SKILL_DIR}/scripts/<old>` and rewrite it to the new path. Missed references are the #1 post-merge bug — always re-grep after rename.

## 5. Description-merge

**When:** Frontmatter descriptions must be combined into one ≤250-char composite.

**Before:**
- Foundation: `"Does X. Use when X1, X2, or X3. NOT for Y."` (72 chars)
- Capability A: `"Handles A. Use when A1, A2. NOT for B or C."` (48 chars)
- Capability B: `"Enables B-style output. Use when asked for B or D."` (56 chars)

**Naive concat:** 72 + 1 + 48 + 1 + 56 = 178 chars — fits, but not a real description.

**Merged (real):**
```
"Does X with A-style handling and B output. Use when X1, X2, X3, A1, A2, or user asks for B. NOT for Y or C."  (107 chars)
```

**Rule:** preserve the foundation's capability statement; fold capability triggers into the "Use when" list; union `NOT for` clauses, dropping least-essential first if overflow. If still >250 after all drops, shorten trigger synonyms.

## 6. Reference-merge

**When:** Two variants ship reference files with the same name (e.g. `guide.md`) but different content.

**Rule:**
1. Compute content hash (SHA-256 of the bytes) of each file.
2. If hashes match, keep one copy.
3. If hashes differ, keep the copy from the higher-fitness variant. Rename the loser to `guide_<losing_dimension>.md` only if its content is substantively unique (>30% diff); otherwise discard.
4. Update any `${CLAUDE_SKILL_DIR}/references/<name>` references in the composite body accordingly.

## 7. Frontmatter-merge

**When:** Combining all variants' frontmatter into one composite.

**Rule per field:**
- `name` — keep the foundation's / family canonical slug. Always.
- `description` — apply the description-merge pattern (§5).
- `allowed-tools` — **union** of all variants' tool lists, deduped. Preserves every capability's tool needs.
- `tags` — union as a set. Dedupe on exact string match.
- Any other scalar field present only in capabilities — copy through if it doesn't conflict with a foundation value; on conflict, foundation wins.

**Before (foundation):**
```yaml
name: foo
description: Does X. ...
allowed-tools: Read Write
tags: [python, testing]
```

**Before (capability):**
```yaml
name: foo-mock
description: Handles mocking.
allowed-tools: Read Bash(pytest *)
tags: [testing, mocking]
```

**After (composite):**
```yaml
name: foo
description: Does X with mocking. Use when ..., NOT for ...
allowed-tools: Read Write Bash(pytest *)
tags: [python, testing, mocking]
```

## Application order

When a composite needs multiple patterns, apply in this order to avoid rework:

1. Frontmatter-merge (§7) — lock the header block first
2. Description-merge (§5) — fit within 250 chars
3. Script-deconflict-rename (§4) — fix filenames before any body rewrites
4. Reference-merge (§6) — fix filenames before any body rewrites
5. Weave-under-header (§1) and Append-new-section (§2) — body assembly
6. Highest-fitness-wins (§3) — resolve remaining contradictions
7. Re-grep body for stale `${CLAUDE_SKILL_DIR}/` paths and rewrite

Then run `scripts/validate.sh` on the composite directory.
