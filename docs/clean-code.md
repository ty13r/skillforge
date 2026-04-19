# SKLD Clean Code Standard

The review rubric. Every PR is held to this. Written to be scannable, not exhaustive — if a rule isn't here, defer to **readability over cleverness**.

## 1. Philosophy

- **Functional-dominant idiomatic Python.** Pure core, imperative shell. No classes where free functions suffice. No monads, no `returns.Result`, no pipe operators — that's novelty debt, not functional programming.
- **Functional React.** Function components only. Derived state over synced state. Hooks do one thing.
- **Pareto over perfection.** Touch the 30% of files that yield 85% of the gain. Seed data and generated files get exempted explicitly.
- **Readability beats cleverness.** If a reviewer pauses to decode a line, it's wrong — rewrite, don't comment.
- **Delete before you rewrite.** Dead code stays deleted. "Removed for X" breadcrumbs belong in git history, not source.

---

## 2. Naming & Module Shape

**File size ceilings.** Hard caps — violating means split:

| Kind | Cap | Why |
|---|---|---|
| Python module | 500 LOC | One module, one concern. `db/queries.py` at 1362 LOC is six modules pretending to be one. |
| Python test module | 800 LOC | Test modules balloon; split along the same seams as the module they test. |
| React component (.tsx) | 400 LOC | `AtomicRunDetail.tsx` at 738 LOC hides three components wearing a trenchcoat. |
| Hook module | 300 LOC | Hooks compose; if yours is bigger than this, it's two hooks. |

**Naming**:

- **No `utils.py` or `helpers.py`.** These are landfills. Name the concern: `json_parsing.py`, `ranking.py`, `prompt_builder.py`.
- **No `manager`, `handler`, `processor`, `service` suffixes.** They describe nothing. `RunRegistry`, not `RunManager`.
- **Verbs for functions, nouns for data.** `compute_fitness(...)`, not `fitness(...)`. `SkillGenome`, not `process_skill(...)`.
- **Private helpers prefixed with `_`.** Public surface = no underscore. If half a module is `_` functions, it probably wants to be a sub-package.

**Bad:**
```python
# skillforge/utils.py
def process(x):
    return _helper(x)
```

**Good:**
```python
# skillforge/agents/_json.py
def extract_json_array(text: str) -> list[dict]: ...
```

---

## 3. Functions

**Rules**:

1. **≤50 lines.** If you're at 80, you're hiding a second function. Extract.
2. **≤4 positional parameters.** More than that → keyword-only or a dataclass.
3. **Single responsibility.** A function that parses *and* validates *and* persists is three functions.
4. **Early return over nesting.** Guard clauses first, happy path last. Max nesting depth: 3.
5. **Pure by default.** If a function reads/writes disk, network, globals, or clocks — that's a side effect. Name it so (`fetch_*`, `persist_*`, `now_*`), and keep the side-effect-free logic in a peer function.
6. **No `None` as sentinel-plus-meaning.** If `None` means "not found" *and* `None` means "error", split return types.
7. **No booleans as flags for behavior change.** `run(dry=True)` → `run_dry()` and `run()`. Two names beats one overloaded call site.

**Bad:**
```python
async def handle_run(run_id, force=False, skip_cache=False, log=True, retry=3, timeout=None):
    if run_id is not None:
        if force or not _cache.has(run_id):
            # 60 more lines
            ...
```

**Good:**
```python
async def handle_run(
    run_id: str,
    *,
    options: RunOptions,
) -> RunResult:
    if _cache.has(run_id) and not options.force:
        return _cached(run_id)
    return await _execute(run_id, options)
```

---

## 4. Error Handling & Logging

**Rules**:

1. **Never `except Exception:`.** Catch the types you can actually handle. If you can't enumerate them, let it propagate — the framework has a handler.
2. **Never `except: pass`.** Silent failure is the single worst habit in this codebase. It turns a failed run into a green checkmark and a mystery.
3. **Typed exceptions.** All domain errors live in `skillforge/errors.py` and inherit from a single `SkldError` base: `SpawnError`, `BreedError`, `JudgeError`, `AgentSDKError`, `DBError`.
4. **`logging`, never `print`.** Every module: `logger = logging.getLogger(__name__)`. Never `print(...)` in library code.
5. **Log context, not prose.** `logger.exception("spawn_failed", extra={"run_id": run_id, "gen": gen})` beats `logger.error(f"oh no {run_id} gen {gen}")`.
6. **`logger.exception()` inside `except`** — it captures the traceback. `logger.error(str(e))` throws it away.

**Bad** (from `skillforge/agents/breeder.py:153`):
```python
try:
    diagnostic_children = await breed_next_gen(...)
    next_gen.extend(diagnostic_children[: slots["diagnostic"]])
except Exception as exc:  # noqa: BLE001
    # Fall through — wildcard slots below absorb the shortfall
    print(f"breeder: diagnostic mutation failed: {exc}")
```

Three problems: broad except, print, and a silent graceful-degradation that nobody will notice failing in production.

**Good:**
```python
try:
    diagnostic_children = await breed_next_gen(...)
    next_gen.extend(diagnostic_children[: slots["diagnostic"]])
except (AgentSDKError, BreedError):
    logger.exception(
        "breeder.diagnostic_failed",
        extra={"run_id": run_id, "generation": generation.number},
    )
```

The graceful-degradation is still there (we fall through), but now the failure is counted, attributed, and searchable.

---

## 5. Data

**Rules**:

1. **Pydantic only at API boundaries.** Incoming requests, outgoing responses, config parsing. That's it.
2. **Frozen dataclasses for internal domain records.** `@dataclass(slots=True, frozen=True)`. Mutation requires `dataclasses.replace(...)`. This is the single biggest readability win for functional style — you can't accidentally mutate something shared.
3. **No mutable default arguments.** `def f(xs: list = [])` is a landmine. `def f(xs: list | None = None): xs = xs or []`.
4. **No mutable module globals.** `PENDING_PARENTS: dict[str, SkillGenome] = {}` at `engine/evolution.py:46` is a bug factory. Thread state through a `RunRegistry` injected at startup.
5. **`TypedDict` for ad-hoc dict shapes.** If a dict has known keys, type it. Opaque `dict[str, Any]` is a review red flag.

**Bad** (from `skillforge/engine/evolution.py:44`):
```python
# Module-level registry: run_id -> parent SkillGenome
PENDING_PARENTS: dict[str, SkillGenome] = {}
```

Two requests to the same pid mutate this dict concurrently. No tests will catch it.

**Good:**
```python
# skillforge/engine/run_registry.py
@dataclass(slots=True)
class RunRegistry:
    _pending_parents: dict[str, SkillGenome] = field(default_factory=dict)

    def register(self, run_id: str, parent: SkillGenome) -> None: ...
    def take(self, run_id: str) -> SkillGenome | None: ...
```

Injected into handlers via FastAPI `Depends(get_registry)`. Testable. No collisions across tests. Async-safe with a `asyncio.Lock` if needed.

---

## 6. Async & Side Effects

**Rules**:

1. **Never `await` inside a sync function.** You'll write `asyncio.run(...)` and regret it. Either the whole call chain is async or none of it is.
2. **Isolate I/O at the edges.** A pure planner builds the prompt. A thin I/O shell calls the SDK. Tests exercise the planner; the shell mocks cleanly.
3. **Inject clients, never construct in function bodies.** `anthropic = Anthropic()` at module scope is a hidden dependency. Pass it.
4. **Semaphore for concurrency caps, not `asyncio.gather()` alone.** `asyncio.gather(*lots_of_tasks)` without a semaphore will rate-limit you. The codebase already has this pattern in `engine/evolution.py:_gated_competitor` — reuse it.
5. **No fire-and-forget tasks without a `TaskGroup`.** `asyncio.create_task(...)` loses exceptions by default. Use `asyncio.TaskGroup` (3.11+) or capture the task and `await` it.

---

## 7. Functional Idioms (Python)

**Embrace**:

- **Comprehensions over `for`-loops** when the loop is building a collection. `[f(x) for x in xs if p(x)]` beats 4 lines of `result.append`.
- **Generators for large/streaming data.** `yield` over materializing a list.
- **`itertools` and `functools`.** `groupby`, `chain`, `takewhile`, `reduce`. These exist; use them.
- **Pure functions take data, return data.** No hidden state reads.
- **`map`/`filter` where readable.** Don't force it — comprehensions usually read better in Python.

**Reject**:

- **`returns.Result`, `Maybe`, `IO` monads.** Use exceptions — they're the idiomatic error channel in Python.
- **Pipe operators (`|>`).** Not Python.
- **Immutable-everywhere zealotry.** Mutating a local list you just built is fine. The rule is: don't mutate things you didn't create *and* don't leak mutable state across function boundaries.

**Example**:

**Bad:**
```python
scores = []
for skill in skills:
    if skill.generation == gen:
        scores.append(compute_fitness(skill))
max_score = 0
for s in scores:
    if s > max_score:
        max_score = s
```

**Good:**
```python
max_score = max(
    compute_fitness(s) for s in skills if s.generation == gen
)
```

---

## 8. React / TypeScript

**Rules**:

1. **Function components only.** No classes. No `React.FC` (infers badly; prefer plain function signatures).
2. **≤3 `useState` per component.** More → `useReducer`. `AtomicRunDetail.tsx` with 9 `useState` is a state machine that hasn't been written yet.
3. **Derived state, not synced state.** If `useEffect` exists only to copy one state into another, delete it and compute inline or with `useMemo`.
4. **Server state via TanStack Query.** No raw `fetch()` in components. Ever. The pattern in `AtomicRunDetail.tsx:130-171` (four `useEffect`s chaining fetches) becomes four `useQuery` hooks that cache, dedupe, and handle errors for free.
5. **One responsibility per hook.** A hook that fetches, formats, and paginates is three hooks.
6. **Never call hooks conditionally.** Same order every render. Lint enforces this.
7. **Extract JSX when it branches.** If your return has three ternaries, extract `<RunHeader />`, `<RunBody />`, `<RunFooter />`.
8. **`@/` path aliases.** No `../../../components/X`. Configure once in `tsconfig.json` + `vite.config.ts`.
9. **Zod schemas at API boundary.** Parse once at the edge; inside, trust the types.
10. **No `any`.** If you need an escape hatch, use `unknown` and narrow.

**Bad** (from `AtomicRunDetail.tsx:143-153`):
```tsx
useEffect(() => {
  if (!runId) return;
  fetch(`/api/runs/${runId}/export?format=skill_md`)
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.text();
    })
    .then(setSkillMd)
    .catch((err) => setSkillMdError(String(err)));
}, [runId]);
```

Five problems: raw fetch, no dedup, no cancellation, manual error state, stringly-typed error.

**Good:**
```tsx
const { data: skillMd, error } = useRunSkillMd(runId);
```

The hook lives in `src/api/hooks/runs.ts`. It handles cache, dedup, retry, cancellation, and types — all of it. The component stops caring.

**Hook structure:**
```tsx
// src/api/hooks/runs.ts
export function useRunSkillMd(runId: string | null) {
  return useQuery({
    queryKey: ["run", runId, "skill_md"],
    queryFn: () => apiClient.get(`/runs/${runId}/export?format=skill_md`).text(),
    enabled: !!runId,
  });
}
```

---

## 9. Testing

**Rules**:

1. **Mock at seams, not at the SDK.** The codebase already does this well — `tests/test_agents.py` mocks `_generate()` (prompt in → text out). Keep doing it.
2. **One assertion per test, unless they're testing the same invariant.** Multi-assert tests are easier to read when failing, worse to diagnose.
3. **Property tests for pure cores.** `hypothesis` for parsers, rankers, fitness computations. If `extract_json_array` is pure, throw random strings at it.
4. **Live tests gated.** `SKILLFORGE_LIVE_TESTS=1` + cost tier. Existing pattern in `tests/conftest.py::_apply_test_tier`. Reuse.
5. **RTL smoke tests before decomposing components.** If you're about to split a 700-LOC component, render it first and assert it doesn't crash. That's the safety net.
6. **Test names describe behavior, not functions.** `test_breeder_pads_short_generation_with_elites` beats `test_breed_next_gen_2`.

---

## 10. Comments

**Default: write none.** The bar:

- **Remove WHAT comments.** `# increment counter` next to `counter += 1` is noise.
- **Remove task/PR comments.** `# fixed for JIRA-4231` — rots, belongs in git blame.
- **Keep WHY comments only when non-obvious.** A workaround for a specific bug, a subtle invariant, a constraint the code can't express.
- **Docstrings on public functions** — one line is plenty unless the contract is genuinely subtle.
- **No module-level ASCII art dividers.** `# --- helpers ---` is a code smell: if a file needs sections, it's too big.

**Bad:**
```python
# Module-level registry: run_id -> parent SkillGenome when the run was started
# via fork-and-evolve (seed or upload). Looked up at gen 0 spawn time.
PENDING_PARENTS: dict[str, SkillGenome] = {}
```

The comment describes *what*. The fix is to delete the global, not annotate it.

**Good:**
```python
# Strip BOM explicitly — FastAPI's JSON decoder chokes on it when
# the upload came from Excel-exported CSVs (see issue with customer X).
body = body.removeprefix("\ufeff")
```

The comment explains the *why* (a hidden constraint) that the code can't express.

---

## 11. Review Rubric (checklist)

Use this when reviewing a PR. Each no = a blocker.

- [ ] No `except Exception:` or `except:` without explicit type
- [ ] No `print(` in library code (tests + CLI scripts exempt)
- [ ] No module-level mutable `dict` / `list` / `set`
- [ ] No file over 500 LOC (Python) / 400 LOC (TSX)
- [ ] No function over 50 LOC
- [ ] No function with >4 positional params
- [ ] No `useEffect` whose sole purpose is to `setState` from another `setState`
- [ ] No raw `fetch()` in components
- [ ] No `any` in TS (use `unknown` + narrow)
- [ ] No `# utils.py` / `# helpers.py` / `// utils.ts`
- [ ] No `React.FC` / class components
- [ ] No WHAT comments, task-reference comments, or ASCII dividers
- [ ] mypy passes on touched modules
- [ ] ruff passes
- [ ] eslint + prettier pass on touched `.ts`/`.tsx`
- [ ] Tests updated/added for changed behavior
- [ ] New exceptions inherit from `SkldError`

---

## 12. Appendix — Anti-Patterns Found in This Codebase

Concrete evidence the rules are grounded in reality. Each will be fixed during the refactor:

| Smell | Example | Count | Wave |
|---|---|---|---|
| Broad `except Exception` + `# noqa: BLE001` | `breeder.py:153,174,191` | 75 | 2 |
| `print(...)` as diagnostic logging | `breeder.py:155,175,192` | ~40 | 2 |
| Module-level mutable global | `engine/evolution.py:46` (`PENDING_PARENTS`) | 2 | 2 |
| Duplicated JSON extractor | `spawner.py`, `engineer.py`, `taxonomist.py`, `challenge_designer.py` | 4 copies | 2 |
| File >500 LOC | `db/queries.py` (1362), `spawner.py` (805), `routes.py` (707), ... | 12 files | 3 |
| Raw `fetch()` in component | `AtomicRunDetail.tsx:131,146,159` | 51 calls | 4 |
| `useEffect` chains for data-fetching | `AtomicRunDetail.tsx` (7 effects, 9 useStates) | 5+ components | 5 |
| No ESLint / Prettier | `frontend/` — absent | — | 1 |
| No mypy / CI / pre-commit | project-wide | — | 1 |

Each row is a promise. The refactor cashes them.
