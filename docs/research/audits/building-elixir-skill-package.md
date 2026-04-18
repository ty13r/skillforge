# Building an Elixir skill package for Claude Code

**Claude Code's skill system can comfortably host 20–66 skills with minimal context overhead, and the plugin marketplace provides a one-command distribution path for the Elixir community.** Skills use a three-tier progressive disclosure model that loads only names and descriptions at session start (~30–50 tokens each), deferring full content until invocation. The plugin system — backed by GitHub-hosted marketplaces and a `/plugin install` CLI — is production-ready and already used by major skill collections with hundreds of bundled skills. For an Elixir/BEAM skill package, the recommended architecture is a Claude Code plugin with skills organized by domain, using `paths` globs to conditionally activate Elixir-relevant skills and optionally bundling an MCP server for deterministic tooling like Mix task execution.

## How Claude Code discovers, loads, and routes skills

Claude Code does **not** eagerly load all SKILL.md files into context. It uses a three-tier progressive disclosure architecture:

**Tier 1 — Descriptions only (always loaded).** At session start, Claude pre-loads every installed skill's `name` and `description` from YAML frontmatter into the system prompt. This costs roughly **30–50 tokens per skill**. All descriptions share a character budget that scales at **1% of the context window** with a fallback floor of **8,000 characters**. Individual descriptions are capped at **250 characters** regardless of budget. With 66 skills averaging 120 characters each, you'd consume about 7,920 characters — right at the budget limit but feasible. You can raise this ceiling via the `SLASH_COMMAND_TOOL_CHAR_BUDGET` environment variable.

**Tier 2 — Full SKILL.md (loaded on invocation).** When Claude determines a skill is relevant (or the user types `/skill-name`), it reads the full SKILL.md via its bash Read tool. The rendered content enters the conversation as a single message and **persists for the rest of the session**. After auto-compaction, Claude re-attaches the most recent invocation of each skill, keeping the **first 5,000 tokens per skill** within a shared budget of **25,000 tokens** across all invoked skills. Older skills get dropped first if the budget overflows.

**Tier 3 — Supporting files (on demand).** Scripts, references, and templates bundled alongside SKILL.md are read only when Claude determines they're needed. Scripts are *executed* via bash — only their output enters context, not the source code.

Routing uses **pure LLM reasoning** against the description field, not embeddings or classifiers. Claude's transformer forward pass matches user intent against all available descriptions. Community testing across 200+ prompts found activation reliability ranges from ~20% with vague descriptions to **72–90%** with optimized descriptions that include explicit "Use when…" trigger phrases and examples in the body. Claude tends to handle simple tasks without consulting skills, so descriptions need to be somewhat assertive about their scope.

## The SKILL.md format and all frontmatter fields

Every skill is a directory containing a `SKILL.md` file with YAML frontmatter and Markdown content. The format follows the **Agent Skills open standard** (published at agentskills.io, December 2025), which is supported by 26+ platforms including OpenAI Codex, Gemini CLI, GitHub Copilot, and Cursor.

The complete frontmatter reference for Claude Code:

| Field | Required | Purpose |
|---|---|---|
| `name` | No | Lowercase alphanumeric with hyphens, max 64 chars. Becomes the `/slash-command`. Defaults to directory name |
| `description` | Recommended | What the skill does and when to use it. **Primary routing mechanism**. Front-load key use case; truncated at 250 chars |
| `argument-hint` | No | Autocomplete hint, e.g. `[module-name]` or `[mix-task]` |
| `paths` | No | Glob patterns limiting auto-activation to matching files, e.g. `**/*.ex, **/*.exs, mix.exs` |
| `disable-model-invocation` | No | `true` prevents Claude from auto-loading; user must invoke manually via `/name` |
| `user-invocable` | No | `false` hides from `/` menu but allows Claude auto-loading. Use for background knowledge |
| `allowed-tools` | No | Tools pre-approved without asking permission. Space-separated or YAML list |
| `model` | No | Override model for this skill (e.g., Haiku for simple tasks, Opus for complex ones) |
| `effort` | No | Override effort level: `low`, `medium`, `high`, `max` |
| `context` | No | Set to `fork` to run in an isolated subagent context |
| `agent` | No | Subagent type when `context: fork` is set (`Explore`, `Plan`, or custom) |
| `hooks` | No | Lifecycle hooks scoped to this skill |
| `shell` | No | `bash` (default) or `powershell` |

String substitutions available in skill content: **`$ARGUMENTS`**, **`$ARGUMENTS[N]`** or **`$N`**, **`${CLAUDE_SKILL_DIR}`** (the directory containing SKILL.md), and **`${CLAUDE_SESSION_ID}`**. Dynamic context injection via `` !`command` `` backtick syntax runs shell commands *before* content is sent to Claude, replacing the placeholder with command output.

Recommended directory structure per skill:

```
genserver-patterns/
├── SKILL.md              # Entry point (<500 lines, <5k tokens)
├── scripts/
│   └── validate_genserver.sh
├── references/
│   └── otp_behaviors.md
├── templates/
│   └── genserver_template.ex
└── examples/
    └── sample_genserver.ex
```

## The plugin system is production-ready for distribution

Claude Code's plugin system bundles skills, hooks, subagents, and MCP servers into a single installable unit. **This is the distribution mechanism for an Elixir skill package.** Any GitHub repository with a `.claude-plugin/plugin.json` manifest can serve as a plugin, and any repository with a `.claude-plugin/marketplace.json` can serve as a marketplace hosting multiple plugins.

A plugin for an Elixir skill collection would look like this:

```
elixir-skills/
├── .claude-plugin/
│   └── plugin.json              # Plugin manifest
├── skills/
│   ├── genserver-patterns/
│   │   └── SKILL.md
│   ├── supervisor-trees/
│   │   └── SKILL.md
│   ├── ecto-queries/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── ecto_cheatsheet.md
│   ├── phoenix-liveview/
│   │   └── SKILL.md
│   ├── mix-tasks/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── run_mix.sh
│   └── ... (up to 66 skills)
├── .mcp.json                    # Optional MCP server config
└── README.md
```

Plugin skills are **namespaced** as `plugin-name:skill-name` (e.g., `elixir-skills:genserver-patterns`), preventing conflicts with user or project skills. The `${CLAUDE_SKILL_DIR}` variable points to the skill's subdirectory within the plugin, not the plugin root, enabling correct script and file references.

Installation for end users requires two commands:

```
/plugin marketplace add your-github-org/elixir-skills
/plugin install elixir-skills@your-marketplace-name
```

Or if published to the official marketplace (`claude-plugins-official`):

```
/plugin install elixir-skills@claude-plugins-official
```

CLI equivalents exist: `claude plugin install`, `claude plugin marketplace add`. The VS Code extension provides a graphical plugin management UI. Plugins support version tracking — bumping the version in `plugin.json` triggers update notifications for users. Local development uses `--plugin-dir <path>` and `/reload-plugins` for hot reloading.

## Scaling to 20–66 skills without blowing the context budget

There is **no hard limit** on skill count. The community proves this works at scale: one user runs **56 skill directories** plus 16 plugin-based skills simultaneously; the Antigravity collection installs **1,370+ skills at once**; alirezarezvani/claude-skills bundles **232+ skills**. The practical constraints are manageable with the right architecture.

**The `paths` field is your primary scaling tool.** Skills with `paths` specified sit in a conditional map and only activate when Claude works with matching files. For an Elixir package, most skills should declare paths:

```yaml
---
name: ecto-queries
description: Ecto query composition patterns for complex joins, preloads, and dynamic queries. Use when writing or refactoring Ecto queries.
paths: ["**/*.ex", "**/*.exs"]
---
```

Without `paths`, every skill's description burns context on every session regardless of relevance. With `paths`, Elixir skills only appear when the user is actually working with Elixir files — dramatically reducing noise for polyglot projects.

**Description budget math for 66 skills**: At 250 characters max per description and an 8,000-character budget, you can fit ~32 skill descriptions before truncation begins. Two strategies mitigate this. First, use `paths` on most skills so they're conditionally loaded rather than always present. Second, use `disable-model-invocation: true` on specialized skills (like deployment or release management) — this removes their descriptions from context entirely, making them manual-invoke-only via `/name`.

**Post-compaction math**: The 25,000-token shared budget with a 5,000-token-per-skill cap means at most **5 fully invoked skills survive compaction** in a single session. This is fine because users rarely need more than 3–5 Elixir skills in one coding session. Design each SKILL.md to be self-contained so it works well alone.

## Multi-skill composition and conflict handling

**Multiple skills can be active simultaneously** — each invoked skill enters as a conversation message and persists. Claude can auto-invoke several skills in sequence based on task analysis. However, **skills cannot explicitly reference other skills**. Composition happens implicitly: Claude uses its understanding of all active skills to synthesize behavior.

Conflict resolution follows a clear hierarchy: **enterprise > personal > project** when skills share the same name. Plugin skills use namespaced names (`plugin-name:skill-name`) and cannot conflict with other scopes. If two skills from different sources have different names but overlapping descriptions, Claude may select either — the fix is to make descriptions unambiguous.

For an Elixir package, design skills as **composable building blocks** rather than monolithic workflows. A user working on a Phoenix LiveView feature might have `phoenix-liveview`, `ecto-queries`, and `testing-exunit` all active simultaneously. Keep each focused on one concern, and avoid contradictory instructions across skills (e.g., don't have one skill recommend `Repo.all` and another recommend `Repo.stream` for the same scenario).

The `context: fork` option runs a skill in an isolated subagent, useful for heavy-weight operations like comprehensive code reviews that shouldn't pollute the main conversation context.

## MCP servers as a complementary distribution channel

MCP servers and skills solve fundamentally different problems. **Skills tell Claude *how* to use tools; MCP *provides* the tools.** For an Elixir package, the hybrid approach inside a single plugin is optimal.

An MCP server would make sense for deterministic Elixir operations: running `mix format`, executing `mix test`, querying `mix hex.info`, checking dialyzer output, or introspecting OTP application trees. These operations need exact execution, not LLM interpretation. A bundled MCP server in your plugin would provide typed tools with JSON Schema validation.

Skills handle the knowledge layer: GenServer design patterns, Supervisor tree architecture decisions, Ecto query optimization strategies, Phoenix LiveView best practices, OTP behavior selection guides. These are inherently instructional — Claude needs to understand *when* and *why* to apply patterns, not just execute commands.

The plugin structure supports both simultaneously:

```json
// .mcp.json (bundled with plugin)
{
  "mcpServers": {
    "elixir-tools": {
      "command": "node",
      "args": ["${PLUGIN_DIR}/bin/mcp-server.js"]
    }
  }
}
```

MCP context cost is higher than skills: **~550–1,400 tokens per tool definition** versus ~30–50 tokens per skill description. Claude Code's Tool Search feature (enabled by default) mitigates this by deferring schema loading, but 66 MCP tools would still consume significantly more context than 66 skills. Use MCP sparingly for operations that genuinely need deterministic execution.

## Configuration files and project-vs-user installation

Claude Code uses a layered configuration system. The files relevant to skill package distribution:

| File | Purpose | Scope |
|---|---|---|
| `~/.claude/skills/<name>/SKILL.md` | User-level skills | All projects for this user |
| `.claude/skills/<name>/SKILL.md` | Project-level skills | This project only (version-controlled) |
| `.claude/settings.json` | Project permissions, hooks, plugin config | Shared via git |
| `~/.claude/settings.json` | User-wide settings | Personal |
| `CLAUDE.md` | Project-level persistent instructions | Shared via git |
| `~/.claude/CLAUDE.md` | Global persistent instructions | Personal |
| `.mcp.json` | Project-scoped MCP servers | Shared via git |
| `~/.claude.json` | User MCP servers, OAuth, per-project state | Personal |

For distribution, the **plugin marketplace** is the primary mechanism. Users can also manually clone a repo into `~/.claude/skills/` (user-level) or `.claude/skills/` (project-level). The `npx skills add` CLI (from Vercel's `skills` npm package, 7.5k stars) provides cross-platform installation: `npx skills add your-org/elixir-skills --skill genserver-patterns -a claude-code`.

## Recommended architecture for the Elixir skill package

Based on everything above, here is the concrete architecture for distributing 20–66 Elixir/BEAM skills:

**Organize skills into 5–7 domain groups** using the `paths` field aggressively. Category suggestions: OTP Patterns (GenServer, Supervisor, Agent, Task, Registry), Ecto & Data (queries, migrations, schemas, changesets), Phoenix & LiveView (controllers, channels, LiveView, components), Testing (ExUnit, Mox, property-based), Tooling & DevOps (Mix tasks, releases, deployment, Dialyzer), and BEAM Internals (processes, ETS, distribution, hot code loading).

**Use `disable-model-invocation: true`** on niche or risky skills (deployment procedures, database migrations, release cutting) to keep them out of the description budget and require manual `/invoke`.

**Keep SKILL.md files under 3,000 tokens** with critical instructions inline — community experience confirms that agents often skip reference files. Move supplementary content to `references/` only for genuinely optional deep-dives.

**Write descriptions in the pattern**: "What it does. Use when [specific trigger]. NOT for [exclusion]." Front-load the key use case within 120 characters since truncation hits at 250. Include "Elixir" or "BEAM" in every description to help routing when users work in polyglot repos.

**Publish as a plugin** with a `.claude-plugin/marketplace.json` manifest on GitHub. This gives users one-command installation, automatic updates on version bumps, and namespaced skills that won't conflict with their existing setup. Consider also publishing to the official `claude-plugins-official` marketplace for maximum visibility.

## Conclusion

The skill system's progressive disclosure model makes 20–66 skills entirely viable — the description-only loading at Tier 1 means even 66 skills add only ~3,300 tokens of baseline overhead, and `paths`-based conditional loading can reduce this further. The plugin marketplace provides a mature distribution channel that several large skill collections (obra/superpowers at 137k stars, alirezarezvani/claude-skills at 232+ skills) already use successfully. The key design decision is whether to go pure-skills (simpler, lower context cost, cross-platform portable via the Agent Skills open standard) or hybrid skills-plus-MCP (adding deterministic tooling for Mix commands and BEAM introspection). For an Elixir community package, starting with a pure-skills plugin and adding an MCP server for deterministic tooling in a later version is the pragmatic path — it minimizes complexity while delivering immediate value through the instructional layer that developers most need when working with OTP, Ecto, and Phoenix patterns.