# elixir-error-tuple-handler

**Rank**: #9 of 22
**Tier**: B (valuable, moderate evidence)
**Taxonomy path**: `code-quality` / `error-handling` / `elixir`
**Status**: 🆕 NEW from research — runner-up; overlaps with pattern-match family

## Specialization

Teaches Claude to handle Elixir's `{:ok, val} | {:error, reason}` tuple convention correctly: no silent `_ = error` discards, no swallowed rescues, use `with` expressions for multi-step happy-paths, and know when to use raising vs non-raising variants of standard library functions.

## Why LLMs struggle

Two HN commenters explicitly named the failure modes:

> *"rescuing exceptions and then not notifying about them ... using the non-raising version of a function and then not doing something reasonable when it returns `:error`"*
> — [HN thread](https://news.ycombinator.com/item?id=46752907)

Specific failure modes:
- Calling `Repo.get/2` (returns `nil` or struct) and then dereferencing without checking
- `try / rescue` blocks that swallow exceptions without logging or notifying
- Using `Repo.insert!/2` where `Repo.insert/2` + `with` would be more graceful
- Mixing tuple-based error returns with raising functions inconsistently

## Decomposition

### Foundation
- **F: `error-flow-philosophy`** — Tuple-based vs exception-based vs hybrid. Variants determine the canonical "how does this code communicate failure" voice.

### Capabilities
1. **C: `ok-error-tuple-basics`** — The canonical `{:ok, val} | {:error, reason}` shape
2. **C: `with-expressions-for-multi-step`** — Happy path + `else` clause for error handling
3. **C: `raising-vs-nonraising-variants`** — `Repo.get!/2` vs `Repo.get/2`, when each is right
4. **C: `rescue-blocks`** — `try/rescue`, exception matching, re-raising with stacktrace
5. **C: `try-catch-for-throws`** — `try/catch` for non-exception signals (`throw/1`, `exit/1`)
6. **C: `let-it-crash-philosophy`** — When to propagate vs handle, supervisor restarts, fault tolerance design
7. **C: `error-logging-and-notification`** — `Logger.error`, Sentry/Honeybadger/Bugsnag integration patterns
8. **C: `custom-exception-modules`** — `defexception`, message templates, exception data
9. **C: `result-tuple-composition`** — Flattening nested `{:ok, {:ok, ...}}` patterns; `Result`-style helper modules

### Total dimensions
**10** = 1 foundation + 9 capabilities

## Evaluation criteria sketch

- **`with` chain test**: refactor a nested `case` chain into a `with` expression
- **Raising vs non-raising test**: identify which function variant is appropriate given the surrounding context (controller action vs background script)
- **Swallowed rescue test**: present a `try/rescue` that silently discards exceptions; rewrite to log + re-raise
- **Result composition test**: flatten three nested `{:ok, _}` matches

## Evidence

- [Research report Part 1 #11](../../docs/research/elixir-llm-pain-points.md#11-error-handling-gaps-ignored-error-tuples-swallowed-rescues)
- [HN thread](https://news.ycombinator.com/item?id=46752907)

## Notes

- Significant overlap with `elixir-pattern-match-refactor` — `with` expressions and pattern matching on `{:ok, _}` / `{:error, _}` straddle both families.
- Could be merged into the pattern-match family if both prove thin in evaluation. But error handling has its own distinct pedagogical surface (`let it crash`, raising variants) that would be lost in a merge.
- Lower priority than the Tier S families — the pain is real but less catastrophic than security or sandbox issues.
