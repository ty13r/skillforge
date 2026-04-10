# Metrics → Mutations Lookup

The Breeder's routing table. Given a weakest metric from the Reviewer's fitness
breakdown, look up the symptom pattern and recommended mutation strategy here.
The embedded table in `scripts/analyze_fitness.py` MUST stay in sync with this
document — this file is the human-readable source of truth.

Every entry follows the same shape:

- **Metric** — name as it appears in the fitness JSON
- **Symptom pattern** — what the trace typically shows when this metric is weak
- **Strategy** — the named mutation strategy (also in `mutation-patterns.md`)
- **Edit pattern** — the concrete edit shape
- **Anti-pattern** — what to avoid

---

## cyclomatic_complexity (high is bad)

- **Symptom**: deep if/elif chains, switch-like ladders, mixed-concern branches
- **Strategy**: `simplify_control_flow`
- **Edit**: extract branches into a dispatch dict (`HANDLERS = {...}`), pull
  repeated predicate logic into named helpers, collapse boolean chains into
  early returns, split mixed-concern branches into separate functions
- **Anti-pattern**: adding a "smart" nested conditional to fix one branch —
  this usually raises complexity further

## max_function_length (high is bad)

- **Symptom**: one function > 40 lines doing parsing + validation + side effects
- **Strategy**: `decompose_functions`
- **Edit**: extract setup, parsing, validation, side effects into named helpers
  with single responsibilities; keep the top-level function as orchestration
- **Anti-pattern**: splitting purely by line count (arbitrary chunks hurt
  readability as much as a long function)

## max_nesting_depth (high is bad)

- **Symptom**: 4+ levels of indentation, pyramid-of-doom blocks
- **Strategy**: `flatten_nesting`
- **Edit**: guard clauses + early returns at the top; invert conditionals so
  the happy path stays at indentation level 1; extract inner loops into helpers
- **Anti-pattern**: replacing nesting with a single long boolean expression

## test_pass_rate (low is bad)

- **Symptom**: failing assertions on specific input shapes visible in the trace
- **Strategy**: `focus_on_correctness`
- **Edit**: add I/O examples in SKILL.md that mirror the failing shapes; add
  the exact failure mode to Gotchas; strengthen the workflow step that produced
  the wrong output; if a helper script was wrong, fix the script
- **Anti-pattern**: adding more examples that look like the already-passing
  cases (changes nothing)

## trigger_precision (low is bad)

- **Symptom**: skill activated on prompts from adjacent domains (noisy skill)
- **Strategy**: `refine_description_exclusions`
- **Edit**: append "NOT for X, Y, or Z" to the description, naming the adjacent
  domains the trace shows it falsely matched; tighten the capability statement
  from generic ("handles data") to specific ("validates CSV headers against a
  schema")
- **Anti-pattern**: removing keywords — kills recall as a side effect

## trigger_recall (low is bad)

- **Symptom**: skill skipped on prompts it should have handled
- **Strategy**: `broaden_description_triggers`
- **Edit**: add synonyms, file extensions, and colloquialisms users actually
  type; apply the "pushy" pattern ("even if they don't explicitly ask for X");
  front-load trigger keywords in the first 250 characters
- **Anti-pattern**: keyword-stuffing — tips into the noisy-skill anti-pattern

## token_usage (high is bad)

- **Symptom**: SKILL.md body > 400 lines, long fixture inline, prose paragraphs
- **Strategy**: `reduce_verbosity`
- **Edit**: move deep detail into `references/*.md` (loaded on demand), convert
  prose paragraphs to bullet lists, cut ceremony words, compress examples to
  the minimum illustrative form
- **Anti-pattern**: deleting examples (drops quality per bible finding §009)

## instruction_compliance (low is bad)

- **Symptom**: trace shows Claude skipped workflow steps or reordered them
- **Strategy**: `strengthen_imperatives`
- **Edit**: convert prose instructions to numbered steps with imperative verbs
  (Run, Read, Validate); remove hedging language ("you might want to"); make
  the step boundary explicit with `###` headers
- **Anti-pattern**: ALL-CAPS warnings — Claude learns to ignore them

## coverage_delta (zero or negative is bad)

- **Symptom**: test coverage unchanged or dropped after a generation
- **Strategy**: `inject_edge_cases`
- **Edit**: add edge-case I/O examples (empty input, max size, unicode,
  malformed), ensure fixtures include the edge cases, add a validation step
  that rejects happy-path-only implementations
- **Anti-pattern**: adding unit tests without changing the SKILL.md — no
  guidance improvement

## tool_precision (low is bad)

- **Symptom**: wrong tool chosen (Bash where Read would suffice, etc.)
- **Strategy**: `tighten_allowed_tools`
- **Edit**: prune `allowed-tools` to the minimum set the workflow actually
  needs; add an explicit tool-use example per workflow step showing the
  expected tool
- **Anti-pattern**: removing a tool the workflow actually needs (breaks the
  execution path)

## cost_usd (high is bad)

- **Symptom**: high token spend per challenge, long prompts, re-reading fixtures
- **Strategy**: `compress_prompt`
- **Edit**: shorten SKILL.md, move static content into references, cache long
  fixtures via filesystem reads instead of inline prompts
- **Anti-pattern**: cutting workflow steps — usually regresses quality

## lint_score (low is bad)

- **Symptom**: output fails style checks on consistent rules
- **Strategy**: `add_formatting_rules`
- **Edit**: add a formatting rule to the workflow (e.g., "Step N: Run
  `ruff format`"), document the specific rule in Gotchas, enforce with
  `validate.sh`
- **Anti-pattern**: hoping Claude will guess the house style
