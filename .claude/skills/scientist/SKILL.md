---
name: scientist
description: >-
  Designs focused variant challenges and machine-readable evaluation rubrics for
  atomic evolution. Use when decomposing a skill, writing per-dimension scoring
  criteria, or validating a rubric. NOT for running evolution or scoring variants.
allowed-tools: Read Write Bash(python *) Bash(bash *) Grep Glob
---

# Scientist

## Quick Start
Given a variant dimension (e.g. `{name: "mock-strategy", tier: "capability"}`), produce (1) a single focused challenge prompt that makes the dimension observable and (2) a machine-readable rubric JSON whose quantitative weights sum to 1.0 and reference metrics from the shared catalog. Validate both with `scripts/validate.sh`.

## When to use this skill
Use whenever SKLD needs a narrow, measurable experiment targeting exactly one variant dimension. Triggers on "design a challenge", "write a rubric", "scoring criteria", "per-dimension evaluation", "what should we test", or any request for focused experimental design for foundation or capability variants. Also triggers when a user asks to validate an existing rubric or sanity-check a challenge/rubric pair before an evolution run starts.

## Core Principles

1. **One dimension per challenge.** A challenge that tests two things teaches nothing. If you cannot state the dimension in a single noun phrase, decompose further.
2. **Measurable > vibes.** Prefer deterministic metrics (exit codes, AST counts, pass rates) to LLM-judged rubrics. Qualitative criteria are a fallback, not a default.
3. **Weights sum to 1.0.** Every quantitative entry carries a `weight`. The sum across `quantitative` must equal 1.0 within 0.001. Validator enforces this.
4. **Reference the catalog.** Every quantitative `metric` name MUST appear in `${CLAUDE_SKILL_DIR}/references/metrics-catalog.md`. Do not invent new metric names; if you need one, add it to the catalog first.
5. **Tier-aware difficulty.** Foundation challenges probe structural decisions (harder, broader). Capability challenges probe narrow modules (focused, shallower). See `${CLAUDE_SKILL_DIR}/references/challenge-design-guide.md`.
6. **Fixtures are immutable.** All variants in the same dimension face the identical fixture files, referenced from `test_fixtures/` inside the challenge prompt.

## Workflow

### Step 1: Read the dimension + catalog
- Read the dimension spec handed in by the Taxonomist: `{name, tier, description, evaluation_focus}`.
- Read `${CLAUDE_SKILL_DIR}/references/metrics-catalog.md` so you know what is actually measurable.
- Read `${CLAUDE_SKILL_DIR}/references/challenge-design-guide.md` for tier-specific patterns and anti-patterns.

### Step 2: Draft the challenge JSON
Produce a JSON object with exactly these fields:
```json
{
  "dimension": "<dimension-slug>",
  "prompt": "<a single focused task that forces the dimension into the output>",
  "difficulty": "easy|medium|hard",
  "verification_method": "deterministic|hybrid|qualitative",
  "fixtures": ["test_fixtures/<file>", "..."]
}
```
Rules:
- `prompt` must name observable artifacts (e.g. "write `tests/test_parser.py`", not "handle testing").
- `verification_method = "deterministic"` when `score.py` alone decides. `hybrid` when some criteria need L4. `qualitative` only if nothing numeric is possible (rare — justify it).
- Foundation tier → `difficulty` in `{medium, hard}`. Capability tier → `{easy, medium}`.

### Step 3: Draft the rubric JSON
Produce:
```json
{
  "dimension": "<same slug as challenge>",
  "quantitative": [
    {"metric": "<name from catalog>", "weight": 0.4, "description": "<why this matters here>"}
  ],
  "qualitative": [
    "<single-sentence criterion a human or LLM can judge>"
  ]
}
```
Rules:
- Weights MUST sum to 1.0 ± 0.001.
- Between 2 and 6 quantitative entries — fewer is too coarse, more dilutes signal.
- Every `metric` must appear in the catalog (validator checks this).
- `qualitative` may be empty when `verification_method == "deterministic"`.

### Step 4: Validate
Run:
```
bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh <challenge.json> <rubric.json>
```
- Exit 0 → hand the pair back to the caller.
- Exit 1 → read the JSON error list on stderr, fix, re-validate. Never ship a pair the validator rejects.

## Examples

**Example 1: Capability variant — Python mock strategy**
Input (dimension):
```json
{"name": "mock-strategy", "tier": "capability",
 "description": "How external dependencies are isolated in unit tests",
 "evaluation_focus": "isolation and maintainability"}
```
Output (challenge):
```json
{
  "dimension": "mock-strategy",
  "prompt": "Write pytest unit tests for test_fixtures/payment_client.py. The client calls an external HTTP API via requests. Your tests must run with no network access. Place tests in tests/test_payment_client.py.",
  "difficulty": "medium",
  "verification_method": "hybrid",
  "fixtures": ["test_fixtures/payment_client.py"]
}
```
Output (rubric):
```json
{
  "dimension": "mock-strategy",
  "quantitative": [
    {"metric": "test_pass_rate", "weight": 0.35, "description": "All tests green with network disabled"},
    {"metric": "coverage_delta", "weight": 0.25, "description": "Coverage increase on payment_client.py"},
    {"metric": "max_function_length", "weight": 0.2, "description": "Short, focused test functions"},
    {"metric": "import_count", "weight": 0.2, "description": "Lean imports — no over-mocking frameworks"}
  ],
  "qualitative": [
    "Mocks should not couple to private attributes of the real client"
  ]
}
```

**Example 2: Foundation variant — IaC project layout**
Input (dimension):
```json
{"name": "iac-layout", "tier": "foundation",
 "description": "How Terraform modules are organized for an AWS deployment",
 "evaluation_focus": "extensibility and clarity"}
```
Output (challenge):
```json
{
  "dimension": "iac-layout",
  "prompt": "Scaffold a Terraform project that deploys an S3 bucket and a Lambda triggered by object creation, using test_fixtures/aws_baseline.tf as the provider baseline. Organize modules so a future SNS topic can be added without editing existing files.",
  "difficulty": "hard",
  "verification_method": "deterministic",
  "fixtures": ["test_fixtures/aws_baseline.tf"]
}
```
Output (rubric):
```json
{
  "dimension": "iac-layout",
  "quantitative": [
    {"metric": "validator_exit_code", "weight": 0.3, "description": "terraform validate exits 0"},
    {"metric": "file_count", "weight": 0.2, "description": "Reasonable modularization, not a single mega-file"},
    {"metric": "max_nesting_depth", "weight": 0.2, "description": "Resource blocks stay shallow"},
    {"metric": "instruction_compliance", "weight": 0.3, "description": "Extensibility requirement met"}
  ],
  "qualitative": []
}
```

**Example 3: Capability variant — Python CLI argument parsing**
Input (dimension):
```json
{"name": "cli-parsing", "tier": "capability",
 "description": "How command-line arguments are defined and validated",
 "evaluation_focus": "ergonomics and error messages"}
```
Output (challenge):
```json
{
  "dimension": "cli-parsing",
  "prompt": "Implement cli.py exposing `mytool sync --source <path> --dest <path> [--dry-run]`. Reject missing paths with a non-zero exit and a single-line error. Use test_fixtures/cli_expected.txt as the reference for --help output.",
  "difficulty": "easy",
  "verification_method": "deterministic",
  "fixtures": ["test_fixtures/cli_expected.txt"]
}
```
Output (rubric):
```json
{
  "dimension": "cli-parsing",
  "quantitative": [
    {"metric": "validator_exit_code", "weight": 0.4, "description": "cli.py --help matches expected"},
    {"metric": "cyclomatic_complexity", "weight": 0.2, "description": "Parser stays simple"},
    {"metric": "max_function_length", "weight": 0.2, "description": "No monolithic main()"},
    {"metric": "tool_call_count", "weight": 0.2, "description": "Efficient implementation path"}
  ],
  "qualitative": []
}
```

## Gotchas
- **Weights off by rounding.** `[0.3, 0.3, 0.3, 0.1]` → 1.0, but `[0.33, 0.33, 0.33]` → 0.99 and fails. Always end on a value that closes the gap.
- **Metric not in catalog.** Validator fails silently-looking with an error about the specific metric. Either pick a canonical one or add it to the catalog first and get it reviewed.
- **Multi-dimension smell.** If your prompt contains "and also" or "while handling", you probably merged two dimensions. Split them.
- **Fixtures drift.** Do not edit fixtures between variants inside the same dimension. Copy to a new fixture with a new name if you need a variant.

## Out of Scope
This skill does NOT:
- Run competitors or score variants (that is the Reviewer)
- Decide which dimensions exist (that is the Taxonomist)
- Mutate variants between generations (that is the Breeder)
- Assemble winning variants into a composite skill (that is the Engineer)
