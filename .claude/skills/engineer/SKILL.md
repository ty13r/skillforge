---
name: engineer
description: >-
  Assembles winning variants into a composite skill. Foundation skeleton plus
  trait merge with conflict resolution and one refinement pass. Use when
  merging variants or building a final skill from atomic winners.
allowed-tools: Read Write Bash(python *) Bash(bash *) Glob Grep
---

# Engineer

## Quick Start
Take one foundation variant, N capability variants, and SkillFamily metadata. Produce ONE composite SKILL.md package by using the foundation as a skeleton, weaving capability traits into its H2/H3 structure, deconflicting supporting files, merging the frontmatter description to ≤250 chars, validating structure, then running an integration test. If the integration test fails, perform exactly one refinement pass.

## When to use this skill
Use whenever a set of per-dimension variant winners needs to be merged into a single installable skill package. Triggers on "assemble variants", "merge variants", "build composite skill", "finalize atomic evolution", "compose winning variants", or whenever the variant-evolution orchestrator has a foundation plus capability list ready. Also triggers on "re-assemble family" after a swap. NOT for single-variant evolution, Gen 0 spawning, or editing a live skill in place.

## Workflow

### Step 1: Gather inputs
Collect from the caller:
- **Foundation variant** — the highest-fitness foundation genome. Its `SKILL.md` is the structural skeleton.
- **Capability variants** — list of per-dimension winning genomes. Each has its own focused `SKILL.md`, scripts, references.
- **SkillFamily metadata** — name, slug, domain, focus, language, tags, specialization.

Read `${CLAUDE_SKILL_DIR}/references/assembly-metrics.md` for synergy ratio, integration pass rate, and refinement triggers.
Read `${CLAUDE_SKILL_DIR}/references/merge-patterns.md` for concrete before/after merge sketches.

### Step 2: Detect conflicts up front
Run the conflict scanner against all variant directories:

```
python ${CLAUDE_SKILL_DIR}/scripts/check_conflicts.py \
  --variants <foundation_dir> <cap1_dir> <cap2_dir> [<cap3_dir> ...]
```

Parse the JSON output. Surface three signals:
- `duplicate_files` — same script filename in ≥2 variants
- `overlapping_sections` — same H2/H3 header text in ≥2 variants
- `description_conflict` — concatenated descriptions exceed 250 chars

If `conflict_count > 3`, stop and report back to the Taxonomist — the decomposition is probably too granular and dimensions should be merged. Otherwise proceed.

### Step 3: Build the skeleton
Copy the foundation's `SKILL.md` body verbatim as the skeleton. Preserve its H2/H3 outline, its Quick Start, its Workflow numbering. Foundation wins structural decisions by definition.

### Step 4: Weave in capability traits
For each capability variant, extract:
- Unique sections (H2/H3 headers not already in the skeleton)
- Unique scripts (filenames not already in the foundation)
- Unique references (files with novel content)
- New workflow steps that belong under an existing foundation section

Apply the merge patterns from `${CLAUDE_SKILL_DIR}/references/merge-patterns.md`:
- **Weave-under-header**: new H3 slots under matching foundation H2
- **Append-new-section**: whole H2 blocks get appended after the foundation's workflow
- **Highest-fitness-wins**: on any true instruction conflict, keep the variant with the higher `fitness_score` and log the loser to `alternatives.md`
- **Script-deconflict-rename**: duplicate script filenames get renamed to `<name>_<dimension>.<ext>` and every `${CLAUDE_SKILL_DIR}/scripts/<name>` reference in the woven SKILL.md is rewritten to match

### Step 5: Merge frontmatter
Combine the foundation description with each capability's trigger phrases into one composite ≤250 chars. Drop less-essential `NOT for` clauses first if you overflow. Union the `allowed-tools` list. Keep the foundation's `name` and the family's canonical slug. Merge `tags` as a set.

### Step 6: Assemble supporting files
Copy all unique `scripts/`, `references/`, `assets/`, and `test_fixtures/` into the composite. Apply script rename rules from Step 4. Dedupe `references/` by content hash — if two variants ship the same-named reference with different content, keep the higher-fitness version.

### Step 7: Validate structure
Run the validator on the assembled directory:

```
bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh <assembled_skill_dir>
```

It checks: SKILL.md exists, frontmatter parses, description ≤250 chars, body ≤500 lines, every `${CLAUDE_SKILL_DIR}/` path in the body resolves. Exit non-zero blocks assembly.

### Step 8: Integration test + refinement
Run one cross-dimension integration challenge through the Competitor against the assembled skill. Compute:

- `integration_pass_rate` — target ≥0.7
- `synergy_ratio = composite_fitness / max(individual_variant_fitness)` — target ≥1.05

If `integration_pass_rate < 0.7` OR `conflict_count > 2` OR description was truncated by >10% OR body was trimmed by >20%, perform **exactly one** refinement pass: rewrite the weakest woven section, re-run validate.sh, re-run the integration challenge. No second refinement pass — if it still fails, ship the best-effort assembly and flag the family for re-decomposition.

## Examples

**Example 1: Python-testing family, clean merge**
Input: foundation=`pytest-fixture-strategy-a` (fitness 0.82), capabilities=[`mock-strategy-b` (0.78), `assertion-style-c` (0.80)]. `check_conflicts.py` reports 0 duplicates, 1 overlapping H3 (`### Step 2: Execute`), description concat = 198 chars.
Output: skeleton from A; B's mock workflow woven as new H3 under A's "Workflow"; C's assertion examples appended to A's "Examples" section; frontmatter merged at 223 chars; validate.sh passes; integration challenge passes 2/2; synergy ratio 1.08. Ship.

**Example 2: Docker skill, description overflow edge case**
Input: foundation=`multi-stage-build-x` (0.76), capabilities=[`layer-caching-y` (0.72), `security-hardening-z` (0.74)]. Concatenated description = 287 chars.
Output: drop "NOT for Kubernetes manifests" clause from Y (least essential, covered by family scope). New description = 241 chars. Script conflict: both X and Y ship `validate.sh` — rename Y's to `validate_caching.sh`, rewrite one SKILL.md reference. Integration test passes. Ship with `alternatives.md` logging Y's original filename.

**Example 3: SQL migration family, integration test fails**
Input: foundation=`expand-contract-m` (0.70), capabilities=[`lock-avoidance-n` (0.68), `rollback-template-o` (0.71)]. Assembly merges cleanly, validate.sh passes, but integration challenge fails 1/2 (rollback template contradicted foundation's expand-contract order).
Output: one refinement pass rewrites the "Rollback" subsection to sequence rollback *after* the contract phase. Re-run integration: 2/2 pass. Synergy ratio 0.98 (slight interference but above ship threshold). Ship with note in `assembly_report.md` flagging the near-miss for Breeder attention.

## Gotchas
- **Never allow two refinement passes.** One pass maximum. Diminishing returns past that — escalate to re-decomposition instead.
- **Script references after rename.** Every `${CLAUDE_SKILL_DIR}/scripts/<old>` in the woven SKILL.md must be rewritten. Grep the body after Step 4.
- **Description length is computed *after* YAML folding.** A `>-` folded scalar joins lines with spaces — count the joined length, not the raw lines.
- **Do not merge foundation vs foundation.** Only ever one foundation per assembly. If two foundations arrive, pick the highest fitness and treat the other as a capability for context only.
- **Conflict count >3 is a taxonomy signal, not a merge problem.** Report back to the Taxonomist with the conflict JSON rather than forcing a bad merge.
- **Preserve the foundation's Quick Start verbatim.** Capabilities may extend the Workflow, but the entry point stays foundation-owned.

## Out of Scope
This skill does NOT:
- Evolve or mutate variants (that is the Breeder)
- Design challenges or rubrics (that is the Scientist)
- Classify skills into the taxonomy (that is the Taxonomist)
- Spawn Gen 0 populations (that is the Spawner)
- Score individual variants (that is the Reviewer)
- Perform more than one refinement pass per assembly
