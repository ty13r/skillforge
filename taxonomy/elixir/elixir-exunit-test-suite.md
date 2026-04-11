# elixir-exunit-test-suite

**Rank**: #13 of 22
**Tier**: C (marginal, thin evidence)
**Taxonomy path**: `testing` / `unit-tests` / `elixir`
**Status**: 🟡 Partially validated — authoring isn't the pain; sandbox (#2) is

## Specialization

Writes ExUnit test modules with proper `async: true` mode, `describe` blocks, `setup` / `setup_all` callbacks, fixtures, tags, `on_exit/1` cleanup, `ExUnit.CaseTemplate` for shared setup, property-based tests via `StreamData`, doctests, and Mox-style mocking.

## Why LLMs struggle

The research found this is partially validated but with weaker evidence than expected:

> *"generated tests are inconsistent"*
> — [Elixir Forum: How are you using AI with Elixir at work](https://elixirforum.com/t/how-are-you-using-ai-with-elixir-at-work-on-production-ready-apps/72326)

But the bigger test pain is **sandbox/concurrency**, which is its own family (`elixir-ecto-sandbox-test`). Authoring tests is not the primary complaint.

Specific minor failure modes:
- Defaulting to Python pytest patterns (fixture decorators) instead of `setup`/`setup_all`
- Forgetting `describe` blocks
- Writing tests without `async: true` even when async-safe
- Confusing `setup` (per-test) with `setup_all` (per-module)
- Not tagging slow tests
- Not using `on_exit/1` for cleanup

## Decomposition

### Foundation
- **F: `test-organization-philosophy`** — Describe-heavy vs file-per-concept vs mirror-source. Variants determine the canonical test file shape.

### Capabilities
1. **C: `setup-and-setup-all`** — Per-test vs per-module fixtures
2. **C: `describe-blocks`** — Grouping, naming conventions
3. **C: `async-mode-safety`** — `async: true` when safe, when not
4. **C: `fixtures-and-factories`** — ExMachina patterns, reusable test data
5. **C: `tags-and-filtering`** — `@tag :slow`, `mix test --only integration`
6. **C: `on-exit-cleanup`** — `on_exit/1` for resource cleanup
7. **C: `case-templates`** — `ExUnit.CaseTemplate` for shared setup across test files
8. **C: `property-based-with-stream-data`** — `StreamData`, generators, shrinking
9. **C: `doctest-integration`** — `doctest MyModule`, verifying examples
10. **C: `mock-strategy-mox`** — `Mox.defmock/2`, expectations, verification

### Total dimensions
**11** = 1 foundation + 10 capabilities

## Evidence

- [Research report Part 2 — verdict #8](../../docs/research/elixir-llm-pain-points.md#part-2--validation-verdicts-on-the-original-10-candidate-families)
- [Elixir Forum: How are you using AI with Elixir at work](https://elixirforum.com/t/how-are-you-using-ai-with-elixir-at-work-on-production-ready-apps/72326)

## Notes

- **Could be dropped** if the active roster is constrained to 7 families.
- The bigger test pain (sandbox) is its own family — this family is left with the smaller authoring concerns.
- The Mox capability is the most distinctive — Mox is Elixir-specific and Claude regularly invents non-existent mocking patterns.
- Adjacent to `elixir-ecto-sandbox-test`. The two could potentially merge into one `elixir-testing` mega-family if both prove thin.
