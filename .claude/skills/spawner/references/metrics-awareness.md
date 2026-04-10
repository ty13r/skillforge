# Metrics Awareness for Spawned Variants

A variant is only as good as the signal the Reviewer can extract from it. Every variant you spawn must be structured so quantitative metrics can be computed deterministically — no LLM judgment required for the hard facts. The Reviewer's L1 pipeline and `code_metrics.py` depend on these rules.

This document is the Spawner's mental model of what the Reviewer measures and how to make variants measurable by construction.

## Hard metrics the Reviewer will compute

### Execution metrics (from the Competitor harness, not your concern)
- `execution_time_s`, `turn_count`, `tool_calls`, `token_input`, `token_output`, `cost_usd`
- You do not set these — but keep the variant's workflow lean so Competitor runs stay efficient. Every "read this reference" step consumes tokens.

### Output metrics (from `scripts/score.py` per variant)
- `code_compiles` — does the produced code parse?
- `tests_pass_rate` — proportion of generated tests that pass
- `lint_score` — ruff/eslint violation count
- `output_file_count` — did the variant produce the expected artifacts?
- `validate_sh_exit` — does the variant's own validator accept the output?

### Code quality proxies (from `code_metrics.py`, AST-based)
- `cyclomatic_complexity` — average per function
- `max_function_length` — longest function in lines
- `max_nesting_depth` — deepest indentation level
- `function_count`, `import_count`

### Derived metrics (calculated downstream)
- `efficiency = fitness / token_usage`
- `speed_quality = fitness / execution_time`
- `instruction_compliance = instructions_followed / total_instructions` (from L3 trace)
- `tool_precision = useful_tool_calls / total_tool_calls`

See `.claude/skills/reviewer/references/metrics-catalog.md` for the canonical catalog.

## Structural rules for variant code

These are the rules that make a variant *measurable*. Break them and the Reviewer will score the variant lower than it deserves because the metrics will be noisy or uncomputable.

1. **Keep Python AST-parseable.** No `exec()`, no `eval()` on untrusted input, no dynamic imports via `importlib` inside business logic, no metaclass trickery, no monkey-patching at module load. `code_metrics.py` uses `ast.parse` — anything that breaks `ast.parse` or obscures the call graph makes the variant un-scorable.
2. **Keep functions short — target < 40 lines.** `max_function_length` is measured directly. A 200-line function tanks the score.
3. **Keep nesting shallow — target < 4 levels.** `max_nesting_depth` is measured directly. Early returns, guard clauses, and helper functions flatten control flow.
4. **Keep cyclomatic complexity reasonable — target < 8 per function.** Measured directly. Favor small pure functions over `if/elif` trees.
5. **Declare I/O in docstrings.** The L3 trace analyzer looks for input/output declarations. A function with a one-line docstring describing `Args:` and `Returns:` scores higher on instruction compliance than an undocumented one.
6. **Produce deterministic outputs.** Given the same input, a variant's script must produce the same output. Non-determinism (time-dependent output, random without seed, set ordering assumptions) makes reproducibility scoring fail.
7. **Prefer stdlib.** Third-party dependencies inflate `import_count` and `cost_usd` (install time) without improving the measured signal. Use stdlib unless the dimension truly requires otherwise.
8. **Move verbose docs out of SKILL.md.** SKILL.md tokens are consumed on every competitor run. Put detail in `references/` and load on demand. Every 100 tokens saved in SKILL.md shows up as lower `token_input` and higher `efficiency`.

## `scripts/score.py` stub contract

Every variant MUST include `scripts/score.py`. It is the Reviewer's deterministic entry point for L1 scoring of this variant's dimension. Signature:

```python
#!/usr/bin/env python3
"""Per-variant deterministic scoring.

Usage:
    python score.py <competitor_output_dir>

Reads the competitor's output directory, computes dimension-specific metrics,
and writes a single JSON object to stdout. Exit 0 on success, 1 on hard failure.

The JSON MUST include at least:
    {
      "dimension": "<this variant's dimension slug>",
      "metrics": {
        "<metric_name>": <number or bool>,
        ...
      },
      "notes": "<optional human-readable summary>"
    }

Metric keys should align with `.claude/skills/reviewer/references/metrics-catalog.md`
so the Reviewer can aggregate them without a translation layer.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def score(output_dir: Path) -> dict:
    """Compute metrics for this variant's dimension. Override per variant."""
    return {
        "dimension": "<fill-me-in>",
        "metrics": {
            "output_file_count": sum(1 for _ in output_dir.rglob("*") if _.is_file()),
        },
        "notes": "",
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: score.py <competitor_output_dir>", file=sys.stderr)
        return 1
    out_dir = Path(sys.argv[1])
    if not out_dir.exists():
        print(f"output dir not found: {out_dir}", file=sys.stderr)
        return 1
    json.dump(score(out_dir), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

The stub is the contract. Each variant replaces the `score()` body with real dimension-specific analysis (count mock calls, measure fixture reuse, check assertion specificity, etc.).

## What the Reviewer will penalize

Treat this as the spawner's pre-flight checklist. If any of these are true, the variant will lose fitness on a dimension that has nothing to do with its actual strategy:

- [ ] `score.py` missing, or importable but raises on sample input
- [ ] `validate.sh` missing or a stub that always exits 0
- [ ] Any `exec()`/`eval()`/dynamic import in scripts
- [ ] A single function > 80 lines (`max_function_length` tanks)
- [ ] Nesting deeper than 5 levels (`max_nesting_depth` tanks)
- [ ] `cyclomatic_complexity` average > 15
- [ ] Non-deterministic output (uses `time.time()`, `random` without seed, unordered set iteration)
- [ ] SKILL.md body > 500 lines (validator rejects before Reviewer even sees it)
- [ ] SKILL.md body pulls 3+ heavy references at routing time (inflates `token_input`)
- [ ] `dimension` field present in frontmatter but never mentioned in the body (variant isn't actually scoped)
- [ ] Undocumented functions (no docstrings → L3 instruction compliance drops)

Structuring variants for measurability is not polish — it is the whole point. A "clever" variant that can't be measured deterministically will lose to a plain variant that can.
