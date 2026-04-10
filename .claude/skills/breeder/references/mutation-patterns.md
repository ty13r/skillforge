# Mutation Patterns Catalog

Proven mutation strategies, grounded in SKLD bible findings and GEPA/Artemis
prior art. Use this file to decide **how** to edit once
`metrics-to-mutations.md` has told you **where** to edit.

Every pattern follows the same shape:

- **Name** — the strategy identifier used in `analyze_fitness.py`
- **When to apply** — the trigger condition
- **What to edit** — exact file + section target
- **Before / After** — concrete illustrative shape
- **Preserved invariants** — things the mutation must NOT break
- **Anti-pattern** — the wrong version of this pattern

---

## reflective_mutation

- **When to apply**: always. This is the master pattern — every non-wildcard
  mutation must be reflective.
- **What to edit**: whichever file contains the symptom the trace points at.
- **Before**: "variant scored poorly on metric X → random prose tweak"
- **After**: "variant scored 0.18 on cyclomatic_complexity because trace lines
  42-71 show a 6-branch if/elif → replace chain with dispatch dict"
- **Preserved invariants**: name regex, ≤500-line body, ≤250-char description,
  `${CLAUDE_SKILL_DIR}/` paths, frontmatter shape.
- **Anti-pattern**: editing without citing a concrete trace symptom. Prior art:
  GEPA's ASI (Automatic Self-Improvement) requires trace-grounded edits.

## multi_parent_crossover

- **When to apply**: two parents have complementary strengths in the same
  dimension (parent A strong on metric X, parent B strong on metric Y, both
  weak on metric Z).
- **What to edit**: take the trait responsible for A's strong metric X, merge
  it into B's body in the corresponding H2/H3 section; keep B's shape.
- **Before**: parent A description has sharp NOT-for exclusions; parent B body
  has tight numbered steps.
- **After**: child inherits A's description + B's body. Single crossover per
  generation to keep attribution clean.
- **Preserved invariants**: the inherited trait must be structurally
  self-contained (a full section, not half a paragraph). Frontmatter shape
  stays consistent with B.
- **Anti-pattern**: blending half-phrases from both parents — produces
  incoherent output and kills L5 trait attribution.

## elitism

- **When to apply**: always, for the top-k variants by aggregate fitness.
- **What to edit**: nothing. Elites carry forward unchanged.
- **Before**: top variant has aggregate_fitness 0.82
- **After**: same variant present in next generation, zero mutation applied.
- **Preserved invariants**: variant id can stay or a new id can be minted as
  long as the genome hash is unchanged.
- **Anti-pattern**: "improving" the elite. Breaks the Pareto frontier and
  discards the best known solution.

## wildcard_exploration

- **When to apply**: exactly 1 slot per generation in the non-elite pool.
- **What to edit**: pick a pattern at random from this catalog (excluding
  elitism), or apply a deliberately novel mutation the lookup table would not
  suggest. The point is local-optima escape, not noise.
- **Before**: population converging on the same 2-3 patterns.
- **After**: 1 variant tries something none of the others has tried (e.g., a
  completely restructured workflow order).
- **Preserved invariants**: all authoring constraints still apply. Wildcard
  means *strategy choice* is random, not *output quality*.
- **Anti-pattern**: wildcard = random character edits. That's not exploration,
  that's corruption.

## description_body_decoupling

- **When to apply**: the weak metric is routing-only (`trigger_precision`,
  `trigger_recall`) or execution-only (everything else).
- **What to edit**: the description track OR the body track — not both in the
  same mutation.
- **Before**: trigger_precision=0.31, trigger_recall=0.88, aggregate=0.52,
  test_pass_rate=0.90
- **After**: description-only mutation tightens exclusions; body is
  byte-identical. Next generation attributes the fitness delta cleanly to the
  description track.
- **Preserved invariants**: treat description mutators and body mutators as
  orthogonal operators.
- **Anti-pattern**: changing both tracks in one mutation. Destroys
  attribution, forces the next generation to re-evolve from ambiguity. Prior
  art: bible/patterns/descriptions.md §P-DESC-007.

## example_injection

- **When to apply**: quality plateau on `test_pass_rate` or
  `instruction_compliance` despite other mutations; Examples section has < 3
  examples.
- **What to edit**: SKILL.md `## Examples` section.
- **Before**: 1 happy-path example.
- **After**: 3 examples covering typical use, edge case, near-miss (matching
  the failing shapes from the trace).
- **Preserved invariants**: examples stay conversational (match user vocab,
  not taxonomy), each example is independently runnable.
- **Anti-pattern**: adding 5+ examples — bloats body, hits token_usage ceiling.
  Prior art: bible finding §009 (example count 1→3 lifted quality 72%→90%;
  gains flatten past 3).

## learning_log_consultation

- **When to apply**: before any mutation. This is a preflight check, not an
  edit pattern.
- **What to edit**: nothing directly. Read `run.learning_log` and filter out
  strategies that already failed for this dimension.
- **Before**: "apply strategy X to metric Y"
- **After**: "learning log shows X failed on Y in gen N; pick next-weakest
  metric or the alternative strategy listed in metrics-to-mutations.md"
- **Preserved invariants**: always append the outcome of the new mutation to
  the learning log after the next generation scores it.
- **Anti-pattern**: ignoring the log. Wastes a generation rediscovering a
  known failure. Prior art: Imbue's accumulating lessons log.

## guard_clause_flattening

- **When to apply**: `max_nesting_depth` ≥ 4 in helper scripts.
- **What to edit**: the function body flagged by `code_metrics.py`.
- **Before**: `if a: if b: if c: do_thing()`
- **After**: `if not a: return; if not b: return; if not c: return; do_thing()`
- **Preserved invariants**: behavior must be identical; add a test that
  exercises the old nested path.
- **Anti-pattern**: flattening without testing — correctness regressions are
  invisible until the next generation runs.

## dispatch_table_extraction

- **When to apply**: `cyclomatic_complexity` ≥ 15 and trace shows a branching
  ladder.
- **What to edit**: extract the branch map into a module-level dict, replace
  the chain with a single lookup + call.
- **Before**:
  ```python
  if kind == "a": return handle_a(x)
  elif kind == "b": return handle_b(x)
  elif kind == "c": return handle_c(x)
  ```
- **After**:
  ```python
  HANDLERS = {"a": handle_a, "b": handle_b, "c": handle_c}
  return HANDLERS.get(kind, default_handler)(x)
  ```
- **Preserved invariants**: default case must be preserved explicitly; all
  branch semantics are unchanged.
- **Anti-pattern**: replacing branches with a dict where one branch has
  side-effecting setup that doesn't translate — silently changes behavior.
