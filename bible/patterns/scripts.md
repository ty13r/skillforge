# Script Patterns

*Empirically-validated patterns for using scripts effectively inside Skills.*

## Confirmed Patterns

### P-SCRIPT-001: Script code never enters the context window

**Finding**: Script source code is never loaded into the context window — only stdout/stderr output is. This means scripts can be arbitrarily large without impacting token usage.

**Evidence**: Research report §1 — "`scripts/` code never enters the context window (only stdout/stderr output does)." §6 — "The key architectural insight: script code never enters the context window — only stdout/stderr output does. This means scripts can be arbitrarily large without impacting token usage."

**How to apply**: Any deterministic operation that would otherwise be described in prose instructions (and therefore eat the instruction budget) should be delegated to a script. A 500-line script in `scripts/` costs zero instruction budget.

### P-SCRIPT-002: Scripts for deterministic operations, instructions for judgment

**Finding**: Scripts handle deterministic operations — sorting, form extraction, data validation, XML manipulation. Instructions handle flexible reasoning — workflows, decision trees, context-dependent judgment.

**Evidence**: Research report §6 quoting the Anthropic engineering blog — "Sorting a list via token generation is far more expensive than simply running a sorting algorithm." The PDF skill ships a Python script that reads PDFs and extracts form fields — Claude runs it without ever loading the script or the PDF into context.

**How to apply**: Classify each step of the workflow. If the operation is fully specifiable (sort, parse, compute, validate), make it a script. If it requires judgment or synthesis, leave it as an instruction.

### P-SCRIPT-003: Bundle repeated helper scripts

**Finding**: If evaluation runs consistently show Claude writing the same helper script from scratch, that's a strong signal to bundle the script. Bundled scripts cost zero tokens; regenerating them costs many tokens and may produce subtly different code each run.

**Evidence**: Research report §8 — "Resource bundling signals: 'If all 3 test cases resulted in the subagent writing a similar helper script, that's a strong signal the skill should bundle that script.'" §11 #8 lists "Not bundling helper scripts" as a top-10 mistake.

**How to apply**: Instrument evaluation runs. When a helper script recurs across test cases, promote it into `scripts/` and replace the instruction with a call.

### P-SCRIPT-004: Use `${CLAUDE_SKILL_DIR}` for all paths

**Finding**: Scripts must reference their skill directory via the `${CLAUDE_SKILL_DIR}` variable, never hardcoded paths. This makes the skill portable across Claude Code, the Agent SDK, and the Skills API.

**Evidence**: Research report §6 — "Use `${CLAUDE_SKILL_DIR}` for all paths (never hardcode)." Cross-reference `structural.md` P-STRUCT-004.

**How to apply**: Inside SKILL.md: `Run: python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py`. Inside the script itself: resolve paths relative to the script's own directory or via the same env var.

### P-SCRIPT-005: Check package availability at script start

**Finding**: Script execution environments differ. Claude Code has full filesystem and network access. The API sandbox has no network and cannot install packages at runtime — only pre-installed packages are available. claude.ai varies by admin setting.

**Evidence**: Research report §2 script execution environment. §6 — "Check available packages at script start. Avoid runtime package installation. Handle varying network access."

**How to apply**: Import guards at the top of the script. Fail fast with a clear error message identifying the missing package, not mid-execution. Never `pip install` at runtime.

### P-SCRIPT-006: Ship a validation script as a default

**Finding**: A dedicated validation script (e.g., `scripts/validate.sh`) that checks the skill's output catches errors that instruction-only approaches miss.

**Evidence**: Research report §12 golden template includes `scripts/validate.sh` as one of only two default scripts — the other being the main helper. §8 notes that execution failure ("skills load but steps get skipped") is a distinct failure mode worth defending against.

**How to apply**: Include a validator script that runs after the main workflow and verifies output invariants. The SKILL.md workflow ends with "Step N: Validate — Run: `bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh`".

## Anti-Patterns

### AP-SCRIPT-001: Describing sort/parse/validate logic in prose
If it's deterministic, it belongs in a script. Describing it in prose eats the instruction budget and produces inconsistent results across runs. See P-SCRIPT-001/002.

### AP-SCRIPT-002: Runtime package installation
`pip install` or `npm install` inside a script will fail silently in the API sandbox. Always assume no network and no installation. See P-SCRIPT-005.

### AP-SCRIPT-003: Hardcoded absolute paths
Breaks portability across environments. Always use `${CLAUDE_SKILL_DIR}` (P-SCRIPT-004).
