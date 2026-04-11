# Elixir Skill Families — Taxonomy

This directory holds the proposed Elixir skill family roster for SkillForge, with full variant decomposition (foundation + capabilities) for each family.

## How to read this directory

- One markdown file per proposed family (22 total)
- Each file lists the family's foundation dimension(s) and all capability dimensions
- Capabilities are the **atomic unit of evolution** — each is independently spawned, scored, and bred via the v2.0 atomic variant evolution pipeline
- Foundations are evolved first; the winning foundation grounds the capability evolution; the Engineer assembles winners into a composite skill

## Source material

- **Original brainstorm**: 10 families proposed unvalidated, plus 7 runners-up
- **Validation research**: [`docs/research/elixir-llm-pain-points.md`](../../docs/research/elixir-llm-pain-points.md) — Opus 4.6 web research agent collected real developer pain points from Elixir Forum, Hacker News, plugin repos, and blogs
- **Final ranking**: tier S = strongest evidence, tier E = brainstormed only

## Ranked roster

| Rank | Tier | Family | Status |
|---|---|---|---|
| 1 | S | [`elixir-phoenix-liveview`](elixir-phoenix-liveview.md) | Validated — strongest evidence |
| 2 | S | [`elixir-ecto-sandbox-test`](elixir-ecto-sandbox-test.md) | NEW from research — "the ugly" pain |
| 3 | S | [`elixir-security-linter`](elixir-security-linter.md) | NEW from research — entire plugin tier |
| 4 | S | [`elixir-ecto-query-writer`](elixir-ecto-query-writer.md) | Validated — pin operator + preload bugs |
| 5 | A | [`elixir-ecto-schema-changeset`](elixir-ecto-schema-changeset.md) | Validated — float-for-money clincher |
| 6 | A | [`elixir-oban-worker`](elixir-oban-worker.md) | Validated — 3 named failure modes |
| 7 | A | [`elixir-pattern-match-refactor`](elixir-pattern-match-refactor.md) | Validated — most-cited complaint |
| 8 | B | [`elixir-genserver-builder-and-smells`](elixir-genserver-builder-and-smells.md) | Reframed — teach when NOT to use |
| 9 | B | [`elixir-error-tuple-handler`](elixir-error-tuple-handler.md) | NEW runner-up |
| 10 | B | [`elixir-otp-debugger`](elixir-otp-debugger.md) | NEW runner-up |
| 11 | B | [`elixir-stdlib-validator`](elixir-stdlib-validator.md) | NEW runner-up |
| 12 | C | [`elixir-supervisor-tree`](elixir-supervisor-tree.md) | Thin evidence |
| 13 | C | [`elixir-exunit-test-suite`](elixir-exunit-test-suite.md) | Authoring isn't the pain — sandbox is |
| 14 | D | [`elixir-phoenix-context`](elixir-phoenix-context.md) | DROPPED — zero evidence |
| 15 | D | [`elixir-typespec-annotator`](elixir-typespec-annotator.md) | DROPPED — zero AI complaints |
| 16 | E | [`elixir-phoenix-channel`](elixir-phoenix-channel.md) | Brainstormed; LiveView replaces |
| 17 | E | [`elixir-broadway-pipeline`](elixir-broadway-pipeline.md) | Enterprise niche |
| 18 | E | [`elixir-telemetry-instrument`](elixir-telemetry-instrument.md) | Observability cross-cutting |
| 19 | E | [`elixir-macro-writer`](elixir-macro-writer.md) | Advanced escape hatch |
| 20 | E | [`elixir-mix-task-writer`](elixir-mix-task-writer.md) | DX tooling |
| 21 | E | [`elixir-binary-pattern-match`](elixir-binary-pattern-match.md) | Low-level protocols |
| 22 | E | [`elixir-release-config`](elixir-release-config.md) | Deployment niche |

## Variant dimension count

Across all 22 families:
- **22 foundation dimensions** (1 per family)
- **~175 capability dimensions** (avg ~8 per family, range 4-12)
- **~197 total variant dimensions**

If only the top 7 (Tier S + Tier A) are built, that's roughly **77 variant dimensions** total — still a sizable evolution surface but tractable.

## Taxonomy additions required

To accommodate this roster, the existing SkillForge taxonomy in `skillforge/db/taxonomy_seeds.py` needs the following additions:

### New language node
- `elixir` (currently the language nodes are: python, javascript, typescript, sql, docker, yaml, html, terraform)

### New focus nodes (under existing domains)
- Under `development`:
  - `otp-primitives`
  - `otp-supervision`
  - `phoenix-framework`
  - `background-jobs`
  - `data-pipelines`
  - `meta-programming`
- Under `data`:
  - `ecto-orm`
  - `ecto-queries`
- Under `code-quality`:
  - `refactoring`
  - `type-annotations`
  - `error-handling`
- Under `testing`:
  - `test-isolation`
- Under `security`:
  - `security-linting`
- Under `devops`:
  - `releases`
- Under `documentation`:
  - (none new — Elixir families don't fall under documentation)

That's ~13 new focus nodes + 1 language node. The taxonomy bootstrap loader is additive (idempotent), so adding these is a one-time edit to `_SEED_CLASSIFICATIONS`.

## Status

This is a **planning document**. None of these families have been authored as Gen 0 seeds yet. The next step is to pick a flagship family (recommended: `elixir-phoenix-liveview`), draft its full Gen 0 package (SKILL.md + scripts + references + test_fixtures + 50 challenges), and run a controlled evaluation against vanilla Claude to validate the SkillForge methodology before scaling to the rest.
