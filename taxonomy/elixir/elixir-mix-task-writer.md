# elixir-mix-task-writer

**Rank**: #20 of 22
**Tier**: E (brainstormed runner-up; no research signal)
**Taxonomy path**: `development` / `otp-primitives` / `elixir`
**Status**: Brainstormed; DX tooling

## Specialization

Writes custom Mix tasks: `use Mix.Task` modules with `@shortdoc`, `@moduledoc`, `run/1` callbacks, args parsing via `OptionParser`, shell interaction via `Mix.shell()`, task dependencies, and `mix help` integration.

## Why this family is here

Mix tasks are how Elixir projects ship custom CLI tools. The shape is well-defined and the failure surface is small (it's mostly boilerplate). Low audience and low pain — but easy to validate if SkillForge ever wants a "tooling" family.

The research found **no specific Mix task complaints**.

## Decomposition

### Foundation
- **F: `task-structure`** — One-shot vs recurring, side-effect-heavy vs pure data transformation

### Capabilities
1. **C: `mix-task-module-shape`** — `use Mix.Task`, `@shortdoc`, `run/1`
2. **C: `args-parsing`** — `OptionParser.parse/2`, switch declarations, aliases
3. **C: `shell-interaction`** — `Mix.shell().info/1`, `yes?/1`, colored output
4. **C: `task-dependencies`** — Running other tasks via `Mix.Task.run/2`, ensuring app started
5. **C: `help-and-doc`** — `mix help task_name`, moduledoc conventions

### Total dimensions
**6** = 1 foundation + 5 capabilities

## Notes

- Smallest family in the roster. Only build if SkillForge is targeting Elixir tooling/DX explicitly.
