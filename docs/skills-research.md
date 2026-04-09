# The definitive technical guide to Claude Agent Skills

**Claude Agent Skills are filesystem-based instruction packages — a `SKILL.md` file with YAML frontmatter plus optional scripts, references, and assets — that teach Claude reusable workflows through progressive context disclosure.** For SkillForge, the critical insight is that skill routing uses pure LLM reasoning (not embeddings or classifiers), meaning description quality directly controls activation probability. Skills follow an open standard (agentskills.io) already adopted by Claude Code, Codex CLI, Gemini CLI, Cursor, and others, making cross-platform portability a design reality. This report synthesizes every documented specification, empirical finding, and advanced pattern into an actionable engineering reference.

---

## 1. The complete SKILL.md format specification

Every Skill is a directory containing at minimum a `SKILL.md` file. The file consists of YAML frontmatter between `---` markers followed by Markdown instruction content.

### YAML frontmatter fields

The open standard (agentskills.io) defines the base schema; Claude Code extends it significantly. **Only `description` is functionally required** — all other fields have sensible defaults.

| Field | Required | Default | Constraints | Purpose |
|-------|----------|---------|-------------|---------|
| `name` | No | Directory name | 1–64 chars, `^[a-z0-9]+(-[a-z0-9]+)*$`, no "anthropic"/"claude" | Display name and `/slash-command` identifier |
| `description` | Recommended | First paragraph of body | 1–1024 chars, no XML tags, **truncated at 250 chars in skill listing** | Primary trigger mechanism — Claude reads this to decide activation |
| `allowed-tools` | No | — | Space-delimited string or YAML list | Pre-approves tools without user permission prompts |
| `argument-hint` | No | — | Free text | Autocomplete hint, e.g. `[issue-number]` |
| `disable-model-invocation` | No | `false` | Boolean | When `true`, only user can invoke via `/name` |
| `user-invocable` | No | `true` | Boolean | When `false`, hidden from `/` menu — only Claude auto-invokes |
| `model` | No | Session default | Model identifier string | Override model for this skill |
| `effort` | No | Session default | `low`, `medium`, `high`, `max` | Thinking effort level |
| `context` | No | Inline | `fork` | Run in isolated subagent context |
| `agent` | No | `general-purpose` | `Explore`, `Plan`, `general-purpose`, or custom | Subagent type when `context: fork` |
| `hooks` | No | — | Hook configuration object | Lifecycle hooks scoped to skill |
| `paths` | No | Always eligible | Glob patterns (comma-separated or YAML list) | Restrict activation to matching file contexts |
| `shell` | No | `bash` | `bash` or `powershell` | Shell for `!command` blocks |
| `version` | No | — | Semver string | Documentation/management metadata |
| `license` | No | — | License name or file reference | Legal metadata |
| `compatibility` | No | — | Max 500 chars | Environment requirements |
| `metadata` | No | — | Key-value string map | Arbitrary additional properties |

### Directory structure

```
skill-name/
├── SKILL.md          # Required: YAML frontmatter + Markdown instructions
├── scripts/          # Executable code — runs via bash, output only enters context
├── references/       # Documentation — loaded into context on demand
├── assets/           # Templates, schemas, fonts — referenced by path, zero token cost
└── ...               # Any additional files
```

**The architectural distinction is critical for SkillForge**: `scripts/` code never enters the context window (only stdout/stderr output does), `references/` content enters context when Claude reads the file, and `assets/` are path-referenced only at zero token cost until explicitly read.

### Naming and size constraints

The name must match the parent directory name exactly. The regex `^[a-z0-9]+(-[a-z0-9]+)*$` enforces lowercase alphanumeric with single hyphens — no leading/trailing hyphens, no consecutive hyphens. **Maximum upload size for API skills is 30 MB** across all files combined. The description budget for all skills combined scales at **1% of the context window** with an 8,000-character fallback, configurable via the `SLASH_COMMAND_TOOL_CHAR_BUDGET` environment variable. Unknown frontmatter fields are silently ignored. A validator exists: `skills-ref validate ./my-skill` from the agentskills/agentskills repository.

---

## 2. How skills are discovered, loaded, and executed

### The routing mechanism uses pure LLM reasoning

There is **no embedding-based matching, no classifier, and no keyword algorithm** at the code level. At startup, Claude Code loads all skill metadata (name + description, ~100 tokens each) into the system prompt as a formatted list inside the `Skill` tool's description. When a user sends a request, Claude's transformer forward pass evaluates user intent against every skill description simultaneously and decides whether to invoke one. This means **description quality is the single largest lever for activation reliability**.

### The three-level progressive disclosure model

| Level | When loaded | Token cost | Content |
|-------|------------|------------|---------|
| **Level 1: Metadata** | Always at startup | ~100 tokens per skill | `name` + `description` from frontmatter |
| **Level 2: Instructions** | When skill is triggered | Under 5,000 tokens recommended | Full SKILL.md markdown body |
| **Level 3: Resources** | As needed during execution | Variable/unlimited | scripts/, references/, assets/ |

Once invoked, the rendered SKILL.md content enters the conversation as a single message and **stays for the rest of the session**. Claude does not re-read the file on later turns. During auto-compaction, Claude Code re-attaches the most recent invocation of each skill after the summary (truncated if very large). If the same skill is invoked multiple times, only the latest copy carries forward.

### Priority and conflict resolution

When skills share the same name across levels: **enterprise > personal > project**. Plugin skills use `plugin-name:skill-name` namespacing and cannot conflict with other levels. Skills take precedence over commands (`.claude/commands/`) sharing the same name. When multiple skills could match semantically, Claude's LLM reasoning selects the best fit — there is no documented formal tiebreaker beyond namespace precedence.

### `setting_sources` in the Agent SDK

The SDK loads **no filesystem settings by default** — this is the single most common troubleshooting issue. You must explicitly configure:

```python
options = ClaudeAgentOptions(
    cwd="/path/to/project",
    setting_sources=["user", "project"],   # Required to discover skills
    allowed_tools=["Skill", "Read", "Write", "Bash"],  # "Skill" must be listed
)
```

Sources and precedence (highest to lowest): programmatic options → `local` → `project` → `user`. The `"project"` source loads `.claude/skills/` from `cwd`, `"user"` loads `~/.claude/skills/`, and `"local"` loads `.claude.local/` overrides.

### Script execution environment

In **Claude Code**: full filesystem and network access, same as any program on the user's machine. In the **API**: sandboxed container with no network access and no runtime package installation — only pre-installed packages. In **claude.ai**: can install from npm/PyPI and pull from GitHub, network access varies by admin settings. In all cases, **script source code never loads into the context window**.

### The `allowed-tools` interaction

The `allowed-tools` frontmatter field **only works in Claude Code CLI directly** — it is ignored by the Agent SDK. In Claude Code, it grants permission for listed tools without prompting, but does not restrict which tools are available. In the SDK, tool access is controlled exclusively via the main `allowed_tools` option paired with `permission_mode`.

### Dynamic context injection

Skills support shell preprocessing via the `!` backtick syntax:

```markdown
## Environment context
- Current branch: !`git branch --show-current`
- PR diff: !`gh pr diff`
```

Commands execute *before* Claude sees the content — output replaces the placeholder. String substitutions also available: `$ARGUMENTS`, `$ARGUMENTS[N]`, `${CLAUDE_SESSION_ID}`, `${CLAUDE_SKILL_DIR}`.

---

## 3. The Skills API for programmatic access

### Endpoints and operations

All endpoints require the `skills-2025-10-02` beta header. There is no PUT/PATCH — updates are new versions.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/skills` | POST | Create skill (multipart form data with `files[]`) |
| `/v1/skills` | GET | List skills (filterable by `?source=anthropic\|custom`) |
| `/v1/skills/{skill_id}` | GET | Retrieve skill |
| `/v1/skills/{skill_id}` | DELETE | Delete skill (must delete all versions first) |
| `/v1/skills/{skill_id}/versions` | POST | Create new version |
| `/v1/skills/{skill_id}/versions` | GET | List versions |
| `/v1/skills/{skill_id}/versions/{version}` | GET/DELETE | Get or delete specific version |

### Using skills in the Messages API

```json
{
  "model": "claude-opus-4-6",
  "max_tokens": 4096,
  "container": {
    "skills": [
      {"type": "anthropic", "skill_id": "pptx", "version": "latest"},
      {"type": "custom", "skill_id": "skill_01AbCdEf...", "version": "1759178010641129"}
    ]
  },
  "tools": [{"type": "code_execution_20250825", "name": "code_execution"}],
  "messages": [{"role": "user", "content": "Create a sales deck"}]
}
```

**Skills absolutely require the code execution tool** — this is a hard dependency. Both beta headers must be present: `anthropic-beta: code-execution-2025-08-25,skills-2025-10-02`.

### Hard limits

- **Maximum 8 skills per request**
- **Maximum 30 MB upload** per skill creation
- Anthropic pre-built skills use date-based versions (`20251013`); custom skills use epoch timestamps
- `version` is optional — defaults to `latest`
- **Skills are not eligible for Zero Data Retention** (ZDR)
- Custom skills uploaded via API are workspace-wide but **do not sync across surfaces** (API, claude.ai, Claude Code are independent)
- Changing the skills list in `container` breaks the prompt cache

---

## 4. Writing effective skill instructions

### The instruction budget is finite and shared

Research shows **frontier thinking LLMs can follow ~150–200 total instructions** with reasonable consistency. Claude Code's system prompt already consumes ~50 of those. Each skill adds more. As instruction count rises, quality degrades **uniformly across all instructions** — Claude doesn't just ignore the new ones, it begins dropping random ones throughout.

### What Claude follows vs ignores

Claude follows well: concrete actions with specific commands, clear numbered workflow steps, instructions that push Claude out of its default behavior, and constraints stated as goals/boundaries rather than step-by-step prescriptions. Claude tends to ignore: overly verbose explanations of things it already knows, deeply nested reference chains (2+ levels deep), time-sensitive conditional logic, and excessive MUSTs for non-critical behavior. **The skill-creator itself warns**: "Rather than put in fiddly overfitty changes, or oppressively constrictive MUSTs, if there's some stubborn issue, you might try branching out and using different metaphors."

### Instruction format and structure

**Numbered steps** produce highest adherence for ordered workflows. **Bullets** work for presenting non-sequential options. **Prose** is best for context and motivation. **Headers (H2/H3)** are essential — Claude relies on formatting hierarchy to parse instructions. The key framework is "degrees of freedom": high-freedom tasks get goals and constraints (prose), medium-freedom tasks get pseudocode/templates, low-freedom critical operations get exact scripts.

### The power of examples

Empirical testing across 200+ prompts showed adding examples improved activation and output quality from **72% to 90%**. Input/output pairs are the recommended format. Community consensus: "Claude learns from examples, not descriptions — examples should be longer than your rules section." However, too many examples bloat token budget and can create unintended patterns. **Two to three diverse, representative examples** is the sweet spot.

### Progressive disclosure architecture

Keep SKILL.md under **500 lines** (~5,000 words). The body should contain quick-start instructions, decision routing to reference files, core constraints, and critical rules. Move detailed API docs, schemas, templates, large example libraries, and domain-specific references to `references/` files. **Critical structural rule**: keep references one level deep from SKILL.md — Claude may only preview files referenced from other referenced files (using `head -100`). Reference files over 100 lines should include a table of contents.

---

## 5. Description optimization for reliable triggering

### The "pushy description" principle

Anthropic's own skill-creator explicitly states: "Currently Claude has a tendency to 'undertrigger' skills — to not use them when they'd be useful. To combat this, please make the skill descriptions a little bit 'pushy'." The recommended pattern expands the trigger surface by listing adjacent concepts:

```yaml
# Weak (undertriggers):
description: "How to build a dashboard to display internal data."

# Strong (reliably triggers):
description: "How to build a dashboard to display internal data. Make sure to use
this skill whenever the user mentions dashboards, data visualization, internal
metrics, or wants to display any kind of company data, even if they don't
explicitly ask for a 'dashboard.'"
```

### The two-part description structure

Every description should contain: (1) what the skill does (capability statement) and (2) when to use it (trigger conditions with "Use when..." language). Empirical results: vague descriptions achieve ~20% activation, optimized descriptions with "Use when" patterns achieve ~50%, and descriptions plus examples in SKILL.md achieve 72–90%.

### Front-load within 250 characters

Descriptions are **hard-capped at 250 characters in the skill listing** regardless of total budget. Any content beyond 250 characters may be truncated during the initial routing decision. Place the most important trigger keywords and use-case language in the first 250 characters. Include explicit exclusion clauses: "NOT for backend logic, API design, database schema, deployment, or server-side code."

### The description optimization pipeline

Located at `skills/skill-creator/scripts/run_loop.py`, this automated pipeline works like a mini ML training loop:

1. Generate ~20 eval queries — half should trigger, half shouldn't (near-misses sharing keywords but needing something different)
2. Split 60% train / 40% held-out test
3. Run each query **3 times** for reliability (triggers on ≥2/3 = "triggered")
4. Identify failures, call `improve_description.py` to propose improved descriptions
5. Iterate up to 5 rounds, selecting winner by **test score not training score**
6. Output HTML comparison report

Anthropic applied this to their own 6 document skills and **improved triggering on 5 of 6**.

### Known failure patterns

Five documented categories: (1) **The Silent Skill** — never fires due to weak description, (2) **The Noisy Skill** — fires for everything due to overly broad keywords, (3) **The Redundant Skill** — model already handles this natively, skill adds noise, (4) **The Token Hog** — works but burns excessive context, (5) **The Stale Skill** — worked with a previous model version but broken on the current one. One skeptical test found **0/20 correct activations** for a review skill, underscoring that automatic activation is probabilistic — explicit `/skill-name` invocation remains the reliable fallback.

---

## 6. Scripts, references, and the context window

### When to use scripts vs instructions

Scripts handle **deterministic operations** — sorting, form extraction, data validation, XML manipulation. The Anthropic engineering blog notes: "Sorting a list via token generation is far more expensive than simply running a sorting algorithm." Instructions handle **flexible reasoning** — workflows, decision trees, context-dependent judgment.

The key architectural insight: **script code never enters the context window — only stdout/stderr output does.** This means scripts can be arbitrarily large without impacting token usage. Anthropic's PDF skill includes a Python script that reads PDFs and extracts form fields — Claude runs it without loading either the script or the PDF into context.

### Reference file loading

Claude uses its language understanding to match context needs against available files. SKILL.md explicitly names which references are relevant for which scenarios:

```markdown
**For Python implementations, also load:**
- [Python Guide](./reference/python_mcp_server.md)

**For TypeScript implementations, also load:**
- [TypeScript Guide](./reference/node_mcp_server.md)
```

Claude conditionally loads only the relevant reference file. Reference content enters context and consumes tokens; asset files (`assets/`) are referenced by path only at zero token cost until explicitly read.

### Cross-environment script compatibility

Use `${CLAUDE_SKILL_DIR}` for all paths (never hardcode). Check available packages at script start. Avoid runtime package installation. Handle varying network access (full in Claude Code, none in API sandbox). The `disableSkillShellExecution: true` managed setting disables shell preprocessing for security.

---

## 7. Evaluating and benchmarking skills

### The four-mode evaluation framework

Anthropic's updated skill-creator (March 2026) operates in four modes: **Create** (interview → research → draft → test), **Eval** (execute on test prompts → grade outputs), **Improve** (execute → grade → blind A/B compare → analyze → iterate), and **Benchmark** (multiple runs with variance analysis for statistical rigor).

The eval system uses **4 parallel sub-agents** in isolated contexts: an Executor (runs skill on test prompt), a Grader (checks outputs against assertions, assigns PASS/FAIL), a Comparator (blind A/B between versions), and an Analyzer (post-hoc analysis generating improvement suggestions).

### A/B comparator for version testing

The comparator conducts blind comparisons — a separate Claude instance reviews both outputs without knowing which came from which configuration and picks a winner with rationale. This eliminates subjective bias. Available in Claude Code and Cowork only (requires subagent capability).

### External testing frameworks

**Promptfoo** provides a dedicated `anthropic:claude-agent-sdk` provider with a `skill-used` assertion type:

```yaml
providers:
  - id: anthropic:claude-agent-sdk
    config:
      working_dir: ./my-project
      setting_sources: ['project']
      append_allowed_tools: ['Skill', 'Read', 'Write']
tests:
  - assert:
      - type: skill-used
        value: code-review
```

**MLflow** uses a Trace → Judge → Refine architecture: `mlflow.anthropic.autolog()` captures every tool call, LLM judges evaluate behavioral questions against traces, and Claude reads traces to make targeted SKILL.md edits. Rule-based judges provide deterministic checks on observable side effects.

### Detecting model absorption

Run your eval suite with the skill loaded and again without it. If the base model passes at a comparable rate, the skill's techniques have been incorporated into the model's default behavior and the skill is no longer necessary — or worse, it may be **actively degrading output** by overriding behavior the model has already learned to do natively.

---

## 8. Real-world patterns from production skills

### Anthropic's document skills architecture

The `pptx`, `xlsx`, `docx`, and `pdf` skills in the anthropics/skills repository (113k stars) are source-available and reveal production patterns. All four share a common architecture: unpack Office Open XML ZIP archives → modify XML directly → repack. Three use LibreOffice headless (`soffice --headless`) with isolated profiles to prevent conflicts. Each bundles **helper scripts for deterministic tasks** that would be unreliable if regenerated each time.

The PPTX skill's description is maximally aggressive: "Use this skill any time a .pptx file is involved in any way... Trigger whenever the user mentions 'deck,' 'slides,' 'presentation,' or references a .pptx filename, regardless of what they plan to do with the content afterward." Its instructions are opinionated: "Don't create boring slides. Plain bullets on a white background won't impress anyone." It mandates subagent verification: "USE SUBAGENTS — even for 2-3 slides. You've been staring at the code and will see what you expect, not what's there."

### The skill-creator as a design template

The skill-creator encodes its own best practices: parallel evaluation (spawn two subagents simultaneously — one with skill, one without), near-miss test design, resource bundling signals ("If all 3 test cases resulted in the subagent writing a similar helper script, that's a strong signal the skill should bundle that script"), and pushy description writing.

### Community ecosystem

Notable community contributions include **obra/superpowers** (20+ skills with explore-plan-execute chains), **Trail of Bits security skills** (CodeQL/Semgrep analysis), **Expo's official React Native skills**, and **shadcn/ui's component pattern enforcement**. The community has produced diagnostic tools like **pulser** (scans skills for structural issues — in one audit, **61% of skills had problems**, mostly broken references) and curated registries like awesome-claude-skills (9.6k stars).

### Common failure modes

A 192-file community audit found **73% of setups had failures**, and the primary cause was broken/missing references — not bad instructions. The five failure categories: (1) activation failure from weak descriptions, (2) execution failure where skills load but steps get skipped, (3) silent structural degradation from broken references, (4) context drift in long sessions, and (5) contradiction between co-loaded skills. The tested mitigation for execution failure — strengthening skill instructions with imperative language and verification steps — brought activation to **100% in controlled experiments**.

---

## 9. Agent SDK integration details

### Critical configuration for both SDKs

```python
# Python
from claude_agent_sdk import query, ClaudeAgentOptions

options = ClaudeAgentOptions(
    cwd="/path/to/project",
    setting_sources=["user", "project"],    # REQUIRED
    allowed_tools=["Skill", "Read", "Write", "Bash"],  # "Skill" REQUIRED
    permission_mode="dontAsk",              # For automated workflows
)

async for message in query(prompt="...", options=options):
    print(message)
```

```typescript
// TypeScript
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "...",
  options: {
    cwd: "/path/to/project",
    settingSources: ["user", "project"],
    allowedTools: ["Skill", "Read", "Write", "Bash"],
  }
})) { /* handle messages */ }
```

### Skills and custom tools coexist

Custom tools defined via `@tool` decorator wrap in an in-process MCP server. Skills and custom tools operate on separate layers but share the same permission pipeline. MCP tool naming uses `mcp__{server_name}__{tool_name}`. Skills can instruct Claude to call MCP tools, but the `allowed-tools` frontmatter field is **ignored by the SDK** — tool access is controlled only via the main `allowed_tools` option.

### Subagents and skills

Subagents can use skills but **do not inherit them from the parent** by default. Skills must be explicitly listed in `AgentDefinition.skills`:

```python
agent = AgentDefinition(
    description="API developer following team conventions",
    prompt="Implement API endpoints.",
    tools=["Read", "Edit", "Write"],
    skills=["api-conventions", "error-handling-patterns"],
)
```

### The `bypassPermissions` trap

Setting `permission_mode="bypassPermissions"` with `allowed_tools=["Read"]` still **approves every tool** — `allowed_tools` does not constrain bypass mode. All subagents inherit bypass mode and it cannot be overridden. Use `disallowed_tools` to actually block tools in bypass mode. The safer pattern for automation is `permission_mode="dontAsk"`, which denies anything not pre-approved.

### Session persistence

Skills are re-discovered from the filesystem at each session start based on `setting_sources`. They are not carried from previous sessions. When resuming a session with the same `setting_sources` and `cwd`, the same skills will be available. The V2 Session API (`unstable_v2_createSession`) is TypeScript-only and provides `send()`/`stream()` patterns but skills configuration works identically.

---

## 10. The future trajectory of agent skills

The open standard at agentskills.io, published December 2025, has achieved rapid cross-platform adoption. As of March 2026, the same SKILL.md files work across **Claude Code, Codex CLI, Gemini CLI, Cursor, and Antigravity IDE**. The community marketplace SkillsMP.com indexes over 700,000 skills. Anthropic's stated long-term goal is "agents that create, edit, and evaluate Skills on their own" — autonomous skill authoring. The plugin ecosystem opened to third parties in February 2026, with enterprise partners including GitLab, Harvey, and Lovable already publishing.

**Skills and MCP are complementary, not competing**: Skills encode procedural knowledge (the "how"), MCP provides external connectivity (the "what"). A CData case study documented **85%+ token savings** by codifying successful MCP interaction patterns as reusable Skills. The architectural significance is that Anthropic has defined both halves of the agentic stack with open standards — what AI can access (MCP) and how AI works (Skills).

---

## 11. Things most people get wrong

**1. Forgetting `setting_sources`.** The SDK loads no filesystem settings by default. Without `setting_sources=["user", "project"]`, skills simply never load — the most common troubleshooting issue.

**2. Writing descriptions about what the skill *is* instead of what it *does*.** "A frontend design agent" undertriggers. "Use this skill for frontend UI design tasks — buttons, cards, forms, navbars, modals" reliably activates.

**3. Assuming `allowed_tools` constrains `bypassPermissions`.** It doesn't. You must use `disallowed_tools` to actually block tools in bypass mode.

**4. Nesting references more than one level deep.** Claude may only preview deeply-nested files with `head -100`. Keep all references one level from SKILL.md.

**5. Ignoring the 250-character description truncation.** Only the first 250 characters appear in the skill listing during routing. Critical trigger keywords buried after 250 characters may never influence activation.

**6. Over-investing in instructions Claude already follows.** The base model is already very capable. Run tasks without the skill first, document where Claude fails, then write minimal instructions to close those specific gaps. Skills that teach Claude things it already knows can actively degrade output quality.

**7. Treating skills as set-and-forget.** Skills expire as models improve. A skill written for Claude 3.5 may be redundant or harmful with Claude 4.6. Periodic evaluation is essential.

**8. Not bundling helper scripts.** If your test runs consistently show Claude writing similar helper scripts from scratch, that's a signal to bundle the script. Script code costs zero tokens; regenerating it costs many.

**9. Broken references.** A community audit found 73% of skill setups had failures, primarily from references to files that had been moved, renamed, or deleted. Validate references in CI.

**10. Loading too many skills simultaneously.** At 50+ active skills, performance degrades noticeably. The description budget is finite (~8,000 characters total). Cap at 20–50 active skills for reliable routing.

---

## 12. The golden template for any new skill

Based on every specification, empirical finding, and production pattern documented above, here is the ideal starting structure:

### Directory structure

```
my-skill/
├── SKILL.md              # < 500 lines, core instructions
├── scripts/
│   ├── main_helper.py    # Deterministic operations (zero context cost)
│   └── validate.sh       # Output validation
├── references/
│   ├── detailed-guide.md # Domain-specific reference (loaded on demand)
│   └── examples.md       # Extended examples library
└── assets/
    └── template.html     # Templates referenced by path
```

### SKILL.md template

```yaml
---
name: my-skill
description: >-
  [Capability statement — WHAT it does, 1 sentence]. Use when [trigger 1],
  [trigger 2], [trigger 3], or when user mentions "[keyword1]", "[keyword2]",
  "[keyword3]", even if they don't explicitly ask for [exact skill name].
  NOT for [exclusion 1], [exclusion 2], or [exclusion 3].
allowed-tools: Read Write Bash(python *)
---

# My Skill

## Quick start
[2-3 sentences: the core workflow in the simplest possible terms]

## Workflow

### Step 1: Gather context
[Concrete instruction with specific action]
- Read `${CLAUDE_SKILL_DIR}/references/detailed-guide.md` for [specific scenario]

### Step 2: Execute
[Concrete instruction]
- Run: `python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py --input "$ARGUMENTS"`

### Step 3: Validate
[Concrete instruction]
- Run: `bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh`

## Examples

**Example 1:**
Input: [realistic user prompt, conversational tone]
Output: [expected result with specific format]

**Example 2:**
Input: [edge case prompt]
Output: [expected result]

**Example 3:**
Input: [near-miss that should NOT trigger different behavior]
Output: [correct handling]

## Gotchas
- [Known failure point #1 — what goes wrong and how to handle it]
- [Known failure point #2]
- [Common user mistake and correct response]

## Out of scope
This skill does NOT:
- [Explicit exclusion with alternative] (use [other-skill] instead)
- [Explicit exclusion]
- [Explicit exclusion]
```

### Design principles encoded in this template

- **Description is front-loaded** with capability + triggers + exclusions within 250 characters for the critical routing decision, with additional trigger phrases following
- **"Pushy" trigger language** explicitly lists adjacent concepts and includes "even if they don't explicitly ask for..." per Anthropic's guidance
- **Instructions use numbered steps** for workflow ordering with imperative verbs
- **Progressive disclosure**: SKILL.md contains routing logic and quick-start; detailed content lives in `references/`
- **Scripts handle deterministic operations** at zero context cost
- **Three diverse examples** teach format and style more effectively than rules
- **Gotchas section** captures real failure points for iterative improvement
- **Explicit out-of-scope section** with alternatives reduces false positives
- **Under 500 lines** total to stay well within the instruction budget
- **Uses `${CLAUDE_SKILL_DIR}`** for portable path references
- **`allowed-tools` specified** for common tool permissions in Claude Code

### Evaluation companion (eval-queries.json)

```json
{
  "should_trigger": [
    "realistic prompt using exact user language #1",
    "realistic prompt using exact user language #2",
    "realistic prompt with synonym/adjacent concept #3",
    "edge case that should still trigger #4",
    "vague request that should trigger #5"
  ],
  "should_not_trigger": [
    "near-miss sharing keywords but needing different skill #1",
    "near-miss with overlapping domain #2",
    "simple request Claude handles natively #3",
    "request for adjacent but excluded capability #4"
  ]
}
```

Run with 60/40 train/test split, 3 runs per query, up to 5 improvement iterations, selecting winner by test score. Periodically re-run evals without the skill loaded to detect model absorption. Integrate into CI with Promptfoo's `skill-used` assertion to catch both trigger regressions and output quality regressions on every PR.

### For SkillForge specifically

Your evolutionary optimization should target three fitness dimensions independently: **trigger precision** (does the skill activate when and only when it should — measurable via the description optimization pipeline), **instruction adherence** (does Claude follow the instructions completely — measurable via output grading), and **token efficiency** (does the skill achieve its goal within minimal context budget — measurable via token counting). The description and instruction body should evolve separately since they serve fundamentally different functions — descriptions are read at routing time by LLM reasoning, while instructions are executed post-activation. Mutation operators should respect the 250-character front-loading constraint for descriptions and the 500-line ceiling for instruction bodies. The strongest baseline for any generated skill is a template that already encodes the pushy description pattern, progressive disclosure architecture, and bundled-script convention documented throughout this report.