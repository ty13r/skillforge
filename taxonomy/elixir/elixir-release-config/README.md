# elixir-release-config

**Rank**: #22 of 22
**Tier**: E (brainstormed runner-up; no research signal)
**Taxonomy path**: `devops` / `releases` / `elixir`
**Status**: Brainstormed; deployment niche

## Specialization

Configures Elixir releases via `mix release`: `config/runtime.exs` for runtime config, env vars and secrets management, overlays for custom files, deployment Dockerfiles for Elixir releases, and the tradeoffs between hot upgrades and rolling deployments.

## Why this family is here

Releases are how production Elixir gets deployed. The mechanics are well-defined but Claude doesn't always know the conventions (`runtime.exs` vs `config.exs`, `RELEASE_*` env vars, overlays). Audience is small but specific — anyone deploying Elixir to production needs this.

The research found **no specific release-related Claude failures**, but this might be because release config is usually copy-pasted from existing projects rather than authored fresh.

## Decomposition

### Foundation
- **F: `release-strategy`** — Single release vs multi-release, umbrella vs flat, hot-upgrade vs rolling

### Capabilities
1. **C: `mix-release-basics`** — `mix release` mechanics, `releases:` configuration in `mix.exs`
2. **C: `runtime-config`** — `config/runtime.exs`, `System.fetch_env!/1` at boot
3. **C: `env-vars-and-secrets`** — `RELEASE_*` env vars, secret loading strategies
4. **C: `overlays-and-includes`** — Custom files in the release tarball
5. **C: `hot-upgrades-vs-rolling`** — When hot upgrades work, when they don't, the OTP machinery
6. **C: `deployment-dockerfile`** — Multi-stage Dockerfile for Elixir releases (build → runtime)

### Total dimensions
**7** = 1 foundation + 6 capabilities

## Notes

- Lowest-priority Tier E family. Build only if SkillForge explicitly wants to support Elixir deployment workflows.
- Adjacent to `elixir-mix-task-writer` and general DevOps families. Could merge into a broader "Elixir DevOps" family if more deployment-related capabilities surface later.
