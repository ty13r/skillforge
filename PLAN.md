# SkillForge Implementation Plan — Steps 3–11

This plan fleshes out every remaining step at the file-by-file level. The goal is one document the dev loop can check against so each step ships with a clear scope, clear verification, and no drift from `SPEC.md`.

Steps 0–2 are complete. Their artifacts:
- Step 0: all foundational docs read (`docs/skills-research.md`, `docs/golden-template.md`, `bible/README.md`, `bible/patterns/*.md`, `SPEC.md`)
- Step 1: `CLAUDE.md` with Progress Tracker + MVP checklist + Decisions Log
- Step 2: full project scaffold (~82 files), `uv sync` clean, import graph clean, stub tests pass

**Rule of thumb**: each step ships behind a passing test suite, a passing QA checklist (§QA Checklist below), and an updated `CLAUDE.md` Progress Tracker entry.

---

## QA Checklist — Applied to Every Step

Every step (whether I do it directly or a Sonnet subagent does it) must pass this checklist before it's marked complete on the Progress Tracker. This is the "is the system still healthy" pass that runs **after** the step's own tests pass.

### Per-step QA (before marking the step complete)

1. **Full import graph clean**: `uv run python -c "import skillforge; from skillforge import main, config, models, db, engine, agents, api"` — no ImportError, no circular deps.
2. **Full test suite green**: `uv run pytest -q` — all tests pass, skipped tests are only the live-SDK-gated ones.
3. **Ruff clean**: `uv run ruff check skillforge/ tests/` — no new lint violations. Warnings are fine but must be reviewed.
4. **No hardcoded model strings**: `uv run ruff check --select=F skillforge/ | grep -i claude` returns nothing outside `config.py`. (Cross-cutting contract #2.)
5. **No `bypassPermissions`**: `grep -rn "bypassPermissions" skillforge/` returns nothing. (Cross-cutting contract #3.)
6. **Cross-cutting contract audit** (manual Opus review): the diff honors all 11 contracts from §Cross-cutting contracts. Spot-check the ones most relevant to the step.
7. **Progress Tracker updated**: `CLAUDE.md` has a new entry in the Completed section with today's date and a one-line summary.
8. **Decisions Log updated** if any non-obvious call was made during the step.

### Per-wave QA (before starting the next wave)

9. **FastAPI boot**: `uv run uvicorn skillforge.main:app --port 8000 &` succeeds and `curl localhost:8000/` returns `{"status": "ok"}`. Kill the process after.
10. **Integration test**: after Wave 4 (Breeder + pipeline), run a mocked-SDK end-to-end test with `pytest tests/test_evolution.py::test_minimal_evolution_mocked -v` (written in Wave 5). This catches contract drift between Sonnet-delegated modules.
11. **DB migration sanity** (Wave 2 and later): `rm -f skillforge.db && uv run python -c "import asyncio; from skillforge.db import init_db; asyncio.run(init_db())"` — fresh DB creates cleanly.
12. **No orphaned files**: the file tree matches `SPEC.md §File Structure` + any documented additions (`PLAN.md`, `SCHEMA.md`). No stray `.tmp`, `.bak`, or half-written files.

### Sonnet subagent output QA

When a Sonnet subagent reports back, Opus runs this before accepting the diff:

13. **Diff review** — read every file the subagent touched. Reject silently-expanded scope (files the subagent modified that weren't in the prompt).
14. **Subagent report cross-check** — does the subagent's summary match the actual diff? If it claims "tests pass" did Opus run them?
15. **Contract honor check** — did the subagent hardcode a model? Use `bypassPermissions`? Skip validation? Reject and re-prompt if so.
16. **Test coverage check** — did the subagent write the tests listed in the prompt? If not, write them or send the subagent back.

If any step of this checklist fails, the step is not done. Fix the failure or send the subagent back before moving on.

---

---

## Step 3 — Data model (real serialization + tests)

**Scope**: Make `skillforge/models/*.py` fully usable — `to_dict`/`from_dict` helpers on every dataclass, JSON-safe serialization of nested structures, real `tests/test_models.py`.

**Files to modify**:
- `skillforge/models/genome.py` — implement `to_dict`, `from_dict`. Datetimes (none here) and nested objects (none) are trivial; all fields are primitives, dicts, or lists.
- `skillforge/models/challenge.py` — same.
- `skillforge/models/run.py` — `to_dict` must serialize nested `Challenge[]`, `Generation[]`, `best_skill: SkillGenome | None`, `pareto_front: SkillGenome[]`, and `created_at`/`completed_at` datetimes as ISO strings.
- `skillforge/models/generation.py` — `to_dict` serializes nested `SkillGenome[]` + `CompetitionResult[]`.
- `skillforge/models/competition.py` — `to_dict`/`from_dict`.
- `skillforge/models/__init__.py` — no changes.

**Helper**: add a private `_json_default(obj)` in a new `skillforge/models/_serde.py` that handles `datetime` → ISO. Keep it out of the public API.

**Tests** (`tests/test_models.py`):
- Round-trip every dataclass through `to_dict` → `from_dict`, assert equality.
- `EvolutionRun.to_dict()` produces JSON-serializable output (`json.dumps(run.to_dict())` succeeds).
- Default factories produce independent instances (two `SkillGenome`s don't share a `traits` list).
- Datetime round-trip preserves timezone (or lack thereof — we use naive `utcnow`; switch to `datetime.now(UTC)` and document).

**Decision to log**: switch from `datetime.utcnow()` → `datetime.now(UTC)` in `run.py` (deprecated in 3.12+).

**Verification**: `uv run pytest tests/test_models.py -v` — all tests pass. Progress Tracker updated.

**QA focus**: the `to_dict` / `from_dict` round-trip must be exact — `obj == from_dict(to_dict(obj))` for every dataclass. Nested genome lists inside `EvolutionRun` are the highest-risk path. Run the full QA checklist before marking complete.

---

## Step 4 — Database layer

**Scope**: Real async SQLite with table creation, CRUD, lineage queries. JSON-blob columns for complex fields.

**Database**: SQLite via `aiosqlite` (per SPEC.md §Tech Stack — "SQLite only, no external DB dependencies").

**Schema source of truth**: [`SCHEMA.md`](./SCHEMA.md) — documents all 5 tables, columns, indexes, foreign keys, and conventions. Any schema change updates `SCHEMA.md` first, then `init_db()`.

**Files to modify**:
- `skillforge/db/database.py`
  - `async def init_db()` — opens connection, enables `PRAGMA foreign_keys = ON`, executes `CREATE TABLE IF NOT EXISTS` for all 5 tables in dependency order per `SCHEMA.md`, creates all indexes.
  - `async def get_connection() -> aiosqlite.Connection` — returns a connection with `PRAGMA foreign_keys = ON` set.
  - Add `async def reset_db()` for tests.
- `skillforge/db/queries.py` — implement all stub functions. Each function opens a connection, runs SQL, closes. Use `json.dumps`/`json.loads` for blob columns. The `save_*` and `get_*` functions delegate serialization to the model dataclasses' `to_dict`/`from_dict` (from Step 3).
- `skillforge/db/__init__.py` — export key functions.

**Tests** (`tests/test_db.py`):
- `init_db()` creates all 5 tables.
- Save and retrieve a `SkillGenome` — round-trip equality.
- Save and retrieve an `EvolutionRun` with nested generations + challenges.
- `get_lineage(run_id)` returns correct parent→child edges.
- Use `temp_db_path` fixture (already in `conftest.py`) with monkeypatched `config.DB_PATH`.

**Verification**: `uv run pytest tests/test_db.py -v`. Progress Tracker updated.

**QA focus**: SCHEMA.md and `init_db` must match exactly — columns, types, nullability, indexes, FK cascades. Run `PRAGMA table_info(table)` in a test to verify each table's shape. DB file must be deletable and recreatable cleanly (QA check 11).

---

## Step 5 — Sandbox system + Skill validator

**Scope**: The isolated temp-directory system each competitor runs in, plus the `validate_skill_structure` checker that enforces Skill Authoring Constraints.

**Files to modify**:
- `skillforge/engine/sandbox.py`
  - `create_sandbox(run_id, generation, competitor_idx, skill, challenge) -> Path`:
    1. Compute path: `{SANDBOX_ROOT}/skillforge-{run_id}-gen{generation}-competitor{competitor_idx}/`
    2. Create `.claude/skills/evolved-skill/` with SKILL.md + supporting files from `skill.supporting_files`
    3. Create `challenge/` with `challenge.setup_files`
    4. Create empty `output/`
    5. Return the root path
  - `cleanup_sandbox(path)` — `shutil.rmtree` guarded by path-prefix check against `SANDBOX_ROOT` (safety).
  - `validate_skill_structure(skill: SkillGenome) -> list[str]` — returns list of violation strings (empty = valid).
    - Parse frontmatter via `python-frontmatter`.
    - Check name regex `^[a-z0-9]+(-[a-z0-9]+)*$`.
    - Check `description` ≤1024 chars; first 250 chars contain "Use when" (pushy pattern signal).
    - Check body ≤500 lines.
    - Count `**Example` markers — must be ≥2.
    - Walk body for `${CLAUDE_SKILL_DIR}/references/...` paths, check each exists in `skill.supporting_files`.
    - Walk scripts for hardcoded absolute paths → violation.
  - Add `collect_written_files(sandbox_path: Path) -> dict[str, str]` — recursively reads `output/` into a dict.

**Tests** (`tests/test_sandbox.py`):
- `create_sandbox` produces the expected directory tree.
- `cleanup_sandbox` refuses to delete paths outside `SANDBOX_ROOT` (safety test).
- `validate_skill_structure` catches each violation category (8 test cases, one per rule).
- `validate_skill_structure` returns empty list on a Skill built from the golden template.
- `collect_written_files` reads nested output files correctly.

**Verification**: `uv run pytest tests/test_sandbox.py -v`. Progress Tracker updated.

**QA focus**: `cleanup_sandbox` path-prefix safety check is critical — a buggy cleanup could delete unrelated user files. Write a negative test that tries to pass `/` or `~` and confirms it raises. The validator must be deterministic — same input, same violations list, every time.

---

## Step 6 — Agents (bottom-up)

Each sub-step has its own test module; the whole judging pipeline gets wired in 6d.

### Step 6a — Challenge Designer

**Files**: `skillforge/agents/challenge_designer.py`.

**Implementation**:
- `async def design_challenges(specialization, n=3) -> list[Challenge]`
- Use `claude_agent_sdk.query()` with `ClaudeAgentOptions(permission_mode="dontAsk", allowed_tools=["WebSearch"] if WEBSEARCH_ENABLED else [], model=model_for("challenge_designer"))`.
- System prompt: "You design evaluation challenges for a Claude Skill specialized in: {specialization}. Produce exactly {n} challenges spanning easy/medium/hard difficulty. Return JSON matching this schema: [...Challenge fields...]."
- Parse JSON response, build `Challenge` objects with generated UUIDs.
- On parse failure, retry once with a more explicit schema prompt.

**Tests** (in `tests/test_agents.py`):
- Mock `query()` via a fake async iterator yielding a pre-baked JSON response. Assert we get 3 `Challenge` objects with unique IDs, correct difficulty distribution.
- Test retry path: first response is malformed JSON, second is valid.

### Step 6b — Spawner

**Files**: `skillforge/agents/spawner.py`.

**Implementation**:
- `async def spawn_gen0(specialization, pop_size) -> list[SkillGenome]`:
  1. Read `GOLDEN_TEMPLATE_DIR/SKILL.md` as template.
  2. Read all `bible/patterns/*.md` into a concatenated string (skip if dir empty).
  3. Prompt LLM: "Generate {pop_size} diverse SKILL.md files for the specialization '{specialization}', following this template: {template}. Apply these validated patterns: {bible_patterns}. Each Skill must vary its approach while preserving structure."
  4. Parse response into individual Skills (delimiter-based or structured JSON).
  5. For each, validate via `validate_skill_structure()`. On violation, reprompt once to fix.
  6. Assemble `SkillGenome` objects with generation=0, empty lineage.
- `async def breed_next_gen(parents, learning_log, breeding_instructions) -> list[SkillGenome]`:
  1. Format parents' SKILL.md content + trait attribution as context.
  2. Inject learning_log and breeding_instructions.
  3. Prompt LLM to produce children per the Breeder's instructions.
  4. Validate each child.
- Helper: `async def _generate_and_validate(prompt: str, role: str) -> SkillGenome` — shared retry loop.

**Tests**:
- `spawn_gen0` with mocked SDK returns 5 `SkillGenome`s, each passing `validate_skill_structure`.
- `spawn_gen0` with empty bible directory still works.
- `breed_next_gen` respects elitism (2 parents marked elite survive unchanged).

### Step 6c — Competitor

**Files**: `skillforge/agents/competitor.py`.

**Implementation**:
- `async def run_competitor(skill, challenge, sandbox_path) -> CompetitionResult`:
  1. Build `ClaudeAgentOptions(cwd=str(sandbox_path), setting_sources=["project"], allowed_tools=["Skill", "Read", "Write", "Edit", "Bash"], max_turns=MAX_TURNS, permission_mode="dontAsk", model=model_for("competitor"))`.
  2. `async for message in query(prompt=challenge.prompt, options=options): trace.append(message_to_dict(message))`
  3. Wrap in `asyncio.timeout(300)` (5 min per competitor).
  4. `output_files = collect_written_files(sandbox_path / "output")`.
  5. Build and return `CompetitionResult` with L1–L5 fields empty (filled by judge).
- Helper: `_message_to_dict(msg) -> dict` — converts SDK message objects to JSON-safe dicts for trace storage.

**Tests**:
- Mock `query()` to yield 3 fake messages; assert trace length 3, sandbox files collected.
- Timeout path: mock yields that never finish → assert `asyncio.TimeoutError` caught and `CompetitionResult` returned with `compiles=False` + error in `judge_reasoning`.

### Step 6d — Judging pipeline

Each layer gets its own tests then the pipeline wires them.

**`deterministic.py`** (L1):
- Dispatch on `challenge.verification_method`.
- Python path: if `output_files` contain `.py`, run `python -m py_compile` (sets `compiles`). If `challenge.setup_files` include a `test_*.py`, write it to a temp dir alongside output and run `pytest` in subprocess (sets `tests_pass`). Run `ruff check --quiet` for lint_score (1.0 if clean, proportional otherwise).
- Reference validation: parse SKILL.md, check all `${CLAUDE_SKILL_DIR}/...` paths resolve against `skill.supporting_files`.
- Generic fallback: run `challenge.setup_files.get("verify.sh")` in subprocess if present.

**`trigger.py`** (L2):
- Single batched call via `anthropic.Anthropic().messages.create()` with `model=model_for("l2_trigger")`.
- Prompt: "Given this skill description: '{description}'\n\nFor each prompt below, answer Y/N whether it would trigger the skill:\n\n{numbered_prompts}\n\nRespond with one Y or N per line."
- Parse response, compute precision (TP / (TP+FP)) and recall (TP / (TP+FN)).
- If should_trigger/should_not_trigger aren't provided on the Challenge, use `docs/eval-queries-template.json` as generic default.

**`trace_analysis.py`** (L3):
- Scan trace for tool calls to `Skill` → `skill_was_loaded`.
- Extract SKILL.md instruction lines (lines starting with `-` or numbered inside `## Workflow`).
- For each instruction, check if a corresponding action appears in the trace (substring match on tool call args or content). Populate `instructions_followed` / `instructions_ignored`.
- LLM-assisted diagnosis: one call per ignored instruction batch — "Why was this instruction likely ignored given this trace?" Use `model_for("judge_trace")`.
- Build `behavioral_signature` from ordered tool-call names.

**`comparative.py`** (L4):
- For each criterion in `challenge.evaluation_criteria`, run pairwise comparisons across all competitors (`C(n,2)` calls using `model_for("judge_comparative")`).
- Compute per-criterion win rates → `pairwise_wins`.
- Map criteria to Pareto objectives: correctness, token_efficiency (turns used / max_turns), code_quality (lint_score), trigger_accuracy (from L2), consistency (0.0 for MVP since L6 skipped).
- Compute Pareto front: a result is optimal if no other result dominates it on all objectives.
- Return dict `{"pareto_optimal_ids": [...], "per_result_objectives": {...}}`.

**`attribution.py`** (L5):
- For each skill: single LLM call with `model_for("judge_attribution")` that receives the SKILL.md, the trace, the L1-L4 scores, and the `instructions_followed/ignored` lists.
- Prompt: "For each trait/instruction below, estimate its fitness contribution (+/- delta from baseline) and give a one-sentence causal explanation from the trace. Return JSON."
- Parse into `trait_contribution` (dict) + `trait_diagnostics` (dict).

**`consistency.py`** (L6): leave as `NotImplementedError("v1.1")` — already is.

**`pipeline.py`**:
- `async def run_judging_pipeline(generation, challenges) -> Generation`:
  1. For each `result` in `generation.results`: `await run_l1(result, matching_challenge)`
  2. For each unique skill in generation: `await run_l2(skill, should_trigger, should_not_trigger)` — cache precision/recall on each result for that skill.
  3. For each result: `await run_l3(result, matching_skill)`
  4. `l4_output = await run_l4(generation.results)` — mutate results with pareto_objectives + pairwise_wins.
  5. For each result: `await run_l5(result, matching_skill)`
  6. Aggregate per-skill scores → update `SkillGenome` fitness fields. Set `is_pareto_optimal`.
  7. Compute `generation.best_fitness`, `avg_fitness`, populate `pareto_front`.
  8. Return mutated `Generation`.

**Tests** (`tests/test_judge.py`):
- Each layer has ≥2 unit tests with mocked LLM calls.
- Pipeline integration test: feed a 3-skill × 2-challenge generation through the pipeline with all LLM calls stubbed, assert the Generation comes back with populated fitness fields and a valid Pareto front.

### Step 6e — Breeder

**Files**: `skillforge/agents/breeder.py`.

**Implementation**:
- `async def breed(generation, learning_log, target_pop_size) -> tuple[list[SkillGenome], list[str], str]`:
  1. Sort skills by aggregate fitness (weighted sum of Pareto objectives for ranking purposes, though Pareto front preserved separately).
  2. **Compute slot allocation as a function of `target_pop_size`** (the run's `population_size`, not hardcoded 5). Formula:
     ```python
     elitism    = max(1, target_pop_size // 5 * 2)     # ~40% floor at 1
     wildcards  = max(1, target_pop_size // 10)        # ~10% floor at 1
     remainder  = target_pop_size - elitism - wildcards
     diagnostic = remainder // 2
     crossover  = remainder - diagnostic
     # At target_pop_size=5: elitism=2, wildcards=1, diagnostic=1, crossover=1 → 5 ✓
     # At target_pop_size=10: elitism=4, wildcards=1, diagnostic=2, crossover=3 → 10 ✓
     # At target_pop_size=3 (edge): elitism=1, wildcards=1, diagnostic=0, crossover=1 → 3 ✓
     ```
  3. Elitism: top `elitism` Skills (Pareto-optimal preferred, then by aggregate fitness) carry forward unchanged.
  4. Diagnostic mutation: pick `diagnostic` low scorers. For each, build a prompt with trace + trait_diagnostics + learning_log, ask LLM (`model_for("breeder")`) for a targeted fix. Call `spawner.breed_next_gen` with that fix.
  5. Reflective crossover: pick 2-3 Pareto-optimal parents per child, produce `crossover` children combining high-contributing traits.
  6. Wildcard: `wildcards` fresh Skills via `spawner.spawn_gen0`.
  7. Assert `len(next_gen) == target_pop_size` before returning.
  7. Extract generalizable lessons from traces → new `learning_log_entries` (one LLM call summarizing "what new lesson emerged from this generation").
  8. Write a breeding_report (LLM call) explaining every decision.
  9. Call `publish_findings_to_bible(new_entries, run_id, generation.number)`.
- `publish_findings_to_bible(new_entries, run_id, generation)`:
  - For each entry, generate a finding markdown file matching the schema in `bible/README.md`.
  - Write to `bible/findings/{NNN}-{slug}.md` where NNN auto-increments by scanning existing findings.
  - Append a line to `bible/evolution-log.md`.

**Tests**:
- Mock the generation with 5 skills (2 Pareto-optimal). Assert top 2 survive unchanged.
- Assert wildcard slot is always filled.
- Assert `learning_log` grows.
- Assert `bible/findings/` gains a new file in a temp bible dir (monkeypatched `config.BIBLE_DIR`).

**Verification**: `uv run pytest tests/test_agents.py tests/test_judge.py -v`. Progress Tracker updated after each sub-step.

**QA focus** (applies to all of Step 6):
- Every SDK call must be mocked in tests. Any test that triggers real API calls is a bug — verify with `grep -rn "query\|messages.create" tests/` and confirm each match is inside a mock context.
- Every `SkillGenome` produced (in 6b Spawner and 6e Breeder) must pass `validate_skill_structure` before returning. Assert this in tests.
- L4 `comparative.py` must dispatch on `config.L4_STRATEGY`. Write a test that flips the flag and verifies both branches produce valid output.
- L5 `attribution.py` output must be JSON-parseable — the Breeder depends on it downstream. Schema-check it in tests.
- After Wave 3 (the 8-agent parallel wave), run the full QA checklist — this is where contract drift between subagents would surface.

---

## Step 7 — Evolution engine

**Files**: `skillforge/engine/evolution.py`.

**Implementation** (built incrementally):

Phase 1 — single-generation hardcoded:
```python
async def run_evolution(run: EvolutionRun) -> EvolutionRun:
    run.status = "running"
    run.challenges = await design_challenges(run.specialization, n=3)
    gen0_skills = await spawn_gen0(run.specialization, run.population_size)
    results = []
    for skill in gen0_skills:
        for challenge in run.challenges:
            sandbox = create_sandbox(run.id, 0, skills.index(skill), skill, challenge)
            try:
                result = await run_competitor(skill, challenge, sandbox)
                results.append(result)
            finally:
                cleanup_sandbox(sandbox)
    generation = Generation(number=0, skills=gen0_skills, results=results)
    generation = await run_judging_pipeline(generation, run.challenges)
    run.generations.append(generation)
    # ... finalize
```

Phase 2 — multi-generation loop with breeding.

Phase 3 — WebSocket event emission via an event queue. The engine writes events; `api/websocket.py` reads from the queue per-run.

Phase 4 — database persistence after each generation.

Phase 5 — budget tracking: accumulate token costs from SDK messages, abort if `total_cost_usd > run.max_budget_usd`.

**Event queue**: add `skillforge/engine/events.py` with a per-run `asyncio.Queue[dict]`. The engine `await queue.put({"event": "...", ...})`. The WebSocket handler `await queue.get()` and sends to the client.

**Tests**:
- Mocked-SDK integration test: 2 pop × 1 gen × 1 challenge end-to-end. Asserts run completes with `status="complete"` and `best_skill` populated.
- Budget-abort test: set `max_budget_usd=0.001`, assert run finishes with `status="failed"` and budget-exceeded error.
- Live test in `test_evolution.py` (already gated behind `SKILLFORGE_LIVE_TESTS=1`).

**Verification**: `uv run pytest tests/test_evolution.py -v`. Progress Tracker updated.

**QA focus**: this is the highest-risk integration point in the entire project. Do NOT skip QA checklist items 9-12 here. Specifically:
- Mocked end-to-end test must run to completion without raising (2 pop × 1 gen × 1 challenge).
- Budget abort test must actually abort — assert `run.status == "failed"` and no further SDK calls happen after abort.
- Event queue must emit events in the documented order (generation_started → competitor_started → ... → evolution_complete). Capture events in a list and assert the sequence.
- `rm -f skillforge.db && run full mocked evolution && inspect DB` — every generation, genome, and result must be persisted. No in-memory-only state.
- After this step, also run the **live** integration test manually (not in CI): `SKILLFORGE_LIVE_TESTS=1 uv run pytest tests/test_evolution.py::test_minimal_evolution_live -v`. This is the first time we hit the real SDK end-to-end and it's where real-world contract mismatches surface.

---

## Step 8 — API + WebSocket

**Files**: `skillforge/api/routes.py`, `skillforge/api/websocket.py`, `skillforge/api/schemas.py`.

**routes.py**:
- `POST /evolve`:
  1. Validate `EvolveRequest` (either `specialization` for domain mode or `test_domains` for meta — raise 400 if wrong mode).
  2. Create `EvolutionRun` with fresh UUID, status="pending".
  3. Persist via `save_run`.
  4. Spawn a background task: `asyncio.create_task(run_evolution(run))`. Register the task in a module-level dict `_active_runs: dict[str, asyncio.Task]`.
  5. Return `EvolveResponse(run_id=run.id, ws_url=f"/ws/evolve/{run.id}")`.
- `GET /runs/{run_id}`: fetch via `get_run`, convert to `RunDetail`.
- `GET /runs/{run_id}/export?format=...`: fetch run, get `best_skill`, dispatch to the right export function, return appropriate MIME type.
- `GET /runs/{run_id}/lineage`: call `get_lineage`, format as `{nodes: LineageNode[], edges: LineageEdge[]}`.

**websocket.py**:
- `/ws/evolve/{run_id}`:
  1. Accept.
  2. Look up the run's event queue from `engine.events.get_queue(run_id)`.
  3. Loop: `while True: event = await queue.get(); await websocket.send_json(event); if event["event"] == "evolution_complete": break`.
  4. Handle disconnects cleanly.

**schemas.py**: already has the models. Add `BreedingEvent`, `ScoresEvent`, etc. as typed event schemas if helpful (optional — the WS sends arbitrary dicts).

**Tests**:
- `tests/test_api.py` (new file): FastAPI `TestClient` tests for POST /evolve (mocked evolution engine), GET /runs/{id}, 404 on missing run, 501 on meta mode in MVP.
- WebSocket test: `TestClient.websocket_connect`, assert events stream in order.

**Verification**: `uv run pytest tests/test_api.py -v` + manual: `uv run uvicorn skillforge.main:app` → `curl -X POST localhost:8000/evolve -d '{"specialization": "test"}'`. Progress Tracker updated.

**QA focus**: WebSocket tests with FastAPI TestClient can mask ordering bugs because the test client runs synchronously. Also spot-check with a real browser WebSocket connection to `ws://localhost:8000/ws/evolve/{id}` during a mocked run. Confirm disconnects don't crash the engine.

---

## Step 9 — Export engine

**Files**: `skillforge/engine/export.py`.

**Implementation**:
- `export_skill_md(genome) -> str`: return `genome.skill_md_content`.
- `export_agent_sdk_config(genome) -> dict`: return `{"system_prompt": genome.skill_md_content, "model": "claude-sonnet-4-6", "allowed_tools": [...], "max_turns": 25, "metadata": {"evolved_by": "SkillForge", "fitness": ..., "generation": genome.generation, "lineage": genome.parent_ids, "traits_survived": genome.traits}}`.
- `export_skill_zip(genome) -> bytes`:
  1. Create a BytesIO + `zipfile.ZipFile`.
  2. Write `evolved-skill/SKILL.md` with genome content.
  3. Write every `supporting_files` entry at its relative path.
  4. Write `META.md` with lineage + fitness + generation.
  5. Return bytes.
- Validate the exported zip by unpacking it into a temp dir and running `validate_skill_structure` on the unpacked SkillGenome (reconstructed). This guarantees exports are always installable.

**Tests**:
- `export_skill_zip` produces a valid zip that unpacks to a validatable Skill.
- `export_agent_sdk_config` produces JSON-serializable dict with all required fields.
- `export_skill_md` is idempotent.

**Verification**: `uv run pytest tests/test_export.py -v`. Progress Tracker updated.

**QA focus**: the exported zip must round-trip through `validate_skill_structure` — if it doesn't, we're shipping broken Skills to users. Also manually unpack one export and drop it into a real `.claude/skills/` directory in a scratch project, start Claude Code, and confirm the Skill loads.

---

## Step 10 — Frontend

**Files**: `frontend/src/components/*.tsx`, `frontend/src/hooks/useEvolutionSocket.ts`, `frontend/src/App.tsx`.

**Scope**: Real implementations for the MVP components only. v1.1 components stay as empty stubs.

**`useEvolutionSocket.ts`**:
- Opens WebSocket to `/ws/evolve/{runId}`.
- Maintains `events: EvolutionEvent[]`, `status: "connecting" | "open" | "closed"`.
- Auto-reconnects once on close.
- Parses events into typed shapes matching the backend event dict.

**`SpecializationInput.tsx`**:
- Form with textarea (specialization), sliders for population_size and num_generations, number input for max_budget_usd.
- On submit: POST `/evolve`, capture `run_id`, pass up to parent.

**`CompetitorCard.tsx`**:
- Props: `competitorId`, `status`, `currentChallenge`, `scores?`.
- Visual states: writing / testing / iterating / done (colored borders + spinner).

**`FitnessChart.tsx`**:
- Props: `generations: {number, best_fitness, avg_fitness}[]`.
- Recharts LineChart with two lines.

**`BreedingReport.tsx`**:
- Props: `report: string`, `decisions: {type, parent_ids, rationale}[]`.
- Collapsible per decision.

**`EvolutionDashboard.tsx`**:
- Top-level state: current run_id, events list, derived generation/competitor state.
- Layout: `SpecializationInput` on the left, grid of `CompetitorCard`s, `FitnessChart` below, `BreedingReport` at the bottom.
- Subscribes to `useEvolutionSocket` when run_id is set.

**Minimum visual bar**: a real user can paste a specialization, click Start, see competitors update in real-time, and watch the fitness chart grow over generations.

**Verification**: `cd frontend && npm install && npm run dev`, then manually run a mocked evolution from the backend and watch the dashboard update. Progress Tracker updated.

**QA focus**: frontend has no automated tests in MVP. Manual QA pass: (1) start backend, start frontend, submit a specialization, watch a mocked evolution progress. (2) Disconnect the backend mid-run and confirm the frontend shows a sensible error state, not a silent hang. (3) TypeScript build must pass (`npm run build`) — this catches type drift from `schemas.py` to `types/index.ts`. (4) Lighthouse quick pass — no accessibility regressions, no blocking console errors.

---

## Step 11 — Docker + Railway

**Files**: `Dockerfile`, `railway.toml` (both exist as placeholders).

**Scope**:
- Finalize the Dockerfile multi-stage build (frontend → Python runtime).
- Test locally: `docker build -t skillforge . && docker run -p 8000:8000 -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY skillforge`.
- `railway.toml` already wired. Push to Railway via `railway up` or GitHub integration.
- Verify the deployed URL serves the frontend at `/` and the API at `/evolve`.

**Environment variables to configure on Railway**:
- `ANTHROPIC_API_KEY`
- `SKILLFORGE_DEFAULT_BUDGET_USD` (if overriding)
- Any `SKILLFORGE_MODEL_*` overrides

**Verification**: curl the Railway URL, POST /evolve with a minimal specialization, watch logs in Railway. Progress Tracker updated → **MVP complete**.

**QA focus**: final production smoke test. Before declaring MVP complete: (1) a real live evolution run completes end-to-end on the deployed URL within budget. (2) The evolved Skill exports cleanly and installs in a fresh Claude Code project. (3) Logs show no unhandled exceptions, no secrets in plaintext, no CORS errors. (4) DB persists across container restarts (or the migration to a persistent volume is documented).

---

## Cross-cutting contracts (locked in now so later steps don't drift)

1. **Serialization**: every dataclass has `to_dict`/`from_dict`. The DB layer uses these directly; no ad-hoc serialization.
2. **Model selection**: every agent calls `config.model_for(role)`. No hardcoded `"claude-sonnet-4-6"` strings outside `config.py`.
3. **Permissions**: every Agent SDK call uses `permission_mode="dontAsk"` + explicit `allowed_tools`. Never `bypassPermissions`.
4. **Skill loading**: every Competitor sets `setting_sources=["project"]` and `cwd=sandbox_path`.
5. **Validation**: every code path that produces a `SkillGenome` (Spawner gen0, Breeder crossover, Breeder mutation) runs it through `validate_skill_structure` before returning.
6. **Budget**: every SDK call increments `run.total_cost_usd` via a central tracker. Engine aborts on overrun.
7. **Events**: the engine only emits events via `events.get_queue(run_id).put(...)`. No direct WebSocket access from the engine.
8. **Bible writes**: only the Breeder writes to `bible/findings/` + `bible/evolution-log.md`. Nothing else touches the Bible.
9. **Testing**: unit tests mock the SDK. Any test that hits the real SDK lives behind `SKILLFORGE_LIVE_TESTS=1`.
10. **Schema**: `SCHEMA.md` is the source of truth for the database schema. Any schema change updates `SCHEMA.md` first, then `db/database.py::init_db`, then the affected queries and tests. Never the other way around.
11. **Population scaling**: the Breeder allocates slots as a function of `target_pop_size`, never hardcoded. See Step 6e for the formula. Any component that assumes `pop_size=5` is a bug.

---

## Open questions (flag at the relevant step, not now)

- **Step 6a**: how many challenges is "right"? Spec says 3–5. MVP uses `n=3`. Revisit after first real run.
- **Step 6d L2**: batched-call fidelity vs. per-query SDK fidelity. If L2 scores turn out noisy, upgrade to per-query SDK in v1.1.
- **Step 6e**: LLM-based lesson extraction may hallucinate. Consider adding a rule-based fallback (e.g., "if trait X had contribution >0.2 in 3+ skills, write a finding").
- **Step 7**: parallel competitor execution is v1.1. MVP runs competitors sequentially to keep the event stream simple.
- **Step 10**: recharts vs. a custom SVG chart. Recharts is bigger but saves time.

---

## Running tally of what each step adds

| Step | New files | Modified files | New tests | Deps added |
|---|---|---|---|---|
| 3 | `models/_serde.py` | all 5 model files | `test_models.py` (expanded) | — |
| 4 | — | `db/database.py`, `db/queries.py` | `test_db.py` | — |
| 5 | — | `engine/sandbox.py` | `test_sandbox.py` | — |
| 6a | — | `agents/challenge_designer.py` | `test_agents.py` | — |
| 6b | — | `agents/spawner.py` | `test_agents.py` | — |
| 6c | — | `agents/competitor.py` | `test_agents.py` | — |
| 6d | — | all `agents/judge/*.py` | `test_judge.py` | — |
| 6e | — | `agents/breeder.py` | `test_agents.py` | — |
| 7 | `engine/events.py` | `engine/evolution.py` | `test_evolution.py` | — |
| 8 | `tests/test_api.py` | `api/routes.py`, `api/websocket.py` | `test_api.py` | — |
| 9 | — | `engine/export.py` | `test_export.py` | — |
| 10 | — | frontend components + hook | — (manual) | — |
| 11 | — | `Dockerfile`, `railway.toml` | — (deploy) | — |

---

## Development Workflow — Wave Plan + Sonnet/Opus Split

To reduce subscription spend, the remaining implementation work is organized into **waves** of parallelizable work delegated to **Sonnet subagents** (via the `Agent` tool with `model: "sonnet"`), with **Opus** (the main orchestrator) reserved for high-judgment integration points where bug cost is highest.

### Principles

1. **Delegate mechanical work to Sonnet**. Pattern-following, CRUD, FS ops, standalone algorithms, standard library usage, component scaffolding.
2. **Reserve Opus for integration**. Anywhere multiple components meet under cross-cutting state, or where a bug would cost days to debug.
3. **Run independent work in parallel**. Multiple Agent tool calls in a single message when they share no files.
4. **Opus reviews every Sonnet diff**, runs tests, wires results together, updates Progress Tracker. Sonnet never ships unreviewed.
5. **Self-contained prompts**. Each subagent receives: the PLAN.md step reference, file paths to touch, function signatures, test expectations, verification commands. No "figure it out" prompts.

### Wave dependency graph

```
Wave 1 (1 agent):    Step 3 models serialization                                    [Sonnet]
  │
Wave 2 (3 agents):   Step 4 DB   |   Step 5 sandbox   |   Step 10 frontend scaffold  [Sonnet ×3]
  │
Wave 3 (8 agents):   6a Challenge │ 6b Spawner │ 6c Competitor │ 6d L1 │ 6d L2       [Sonnet ×8]
                     6d L3 │ 6d L4 │ 6d L5
  │
Wave 4 (Opus):       6d pipeline.py wire-up   +   6e Breeder                         [Opus, direct]
  │
Wave 5 (Opus):       Step 7 evolution engine (phased implementation)                 [Opus, direct]
  │
Wave 6 (3 agents):   Step 8 API   |   Step 9 export   |   Step 10 frontend finish    [Sonnet ×3]
  │
Wave 7 (1 agent):    Step 11 Docker + Railway                                        [Sonnet]
```

### Ownership table

| Work | Owner | Why |
|---|---|---|
| Step 3 models serialization | Sonnet (1 agent) | Pattern-following, well-defined schema |
| Step 4 DB CRUD | Sonnet | SCHEMA.md is the spec — just translate |
| Step 5 sandbox FS ops + validator | Sonnet | Rules already enumerated in docstrings |
| Step 6a Challenge Designer | Sonnet | Single SDK call + JSON parsing |
| Step 6b Spawner | Sonnet | Template + LLM call + validator |
| Step 6c Competitor | Sonnet | Thin SDK wrapper |
| Step 6d L1–L5 (5 agents) | Sonnet | Each layer is a self-contained algorithm |
| **Step 6d pipeline.py wire-up** | **Opus** | Orchestrates shared-state mutation |
| **Step 6e Breeder** | **Opus** | Slot allocation + reflective reasoning + bible publishing |
| **Step 7 evolution engine** | **Opus** | Phased integration, highest bug cost |
| Step 8 API | Sonnet | Standard FastAPI patterns |
| Step 9 export | Sonnet | Pure data transforms |
| Step 10 frontend | Sonnet | Standard React + Vite + Tailwind |
| Step 11 Docker/Railway | Sonnet | Mechanical |

**Sonnet handles ~11 of 14 distinct work units (~80%). Opus retains the 3 hardest integration points.**

### Subagent prompt template

Every Sonnet subagent invocation uses this structure:

```
You are implementing SkillForge Step {N} ({Step name}).

## Context
SkillForge is an evolutionary breeding platform for Claude Agent Skills.
Read these files to understand the project: PLAN.md §Step {N}, SPEC.md, CLAUDE.md.
Schema of truth: SCHEMA.md (if DB-related).

## Scope
{bullet list of files to create/modify}
{function signatures to implement}

## Constraints (from CLAUDE.md cross-cutting contracts)
- Every SDK call: permission_mode="dontAsk", explicit allowed_tools, never bypassPermissions
- Every agent: model via config.model_for(role), never hardcoded model strings
- Every SkillGenome produced: validate via engine.sandbox.validate_skill_structure
- Tests mock the SDK; live tests gated behind SKILLFORGE_LIVE_TESTS=1

## Tests to write
{test cases}

## Verification
{exact commands to run: e.g., `uv run pytest tests/test_X.py -v`}

## Out of scope
{explicit exclusions — what NOT to touch}

Report back in under 200 words: what you changed, which tests pass, any deviations from the plan with justification.
```

### Post-wave orchestration loop

After each wave completes, the main orchestrator (Opus) runs this loop **in order**:

1. **Review all subagent diffs** (QA checks 13–16). Reject scope creep, contract violations, or missing tests. Send subagents back if needed.
2. **Run the full QA checklist** (§QA Checklist above, steps 1–12 as applicable to this wave).
3. **Debug any failures** before moving on — never accumulate broken state between waves. A red test at wave N makes wave N+1 untrustworthy.
4. **Update `CLAUDE.md` Progress Tracker** with completion date + wave summary.
5. **Log any cross-step decisions** in the Decisions Log.
6. **Announce wave completion** to the user with: what shipped, what's next, any surprises.

The loop is gated: I do not start wave N+1 until wave N's QA passes. No exceptions.

---

## Flexibility Hooks — Cost-Saver Switches

Three cost-saving strategies were identified during review. All are **designed to be one-line env-var or config flips**, not refactors. The code must be structured so switching any of them ON is trivial.

### Flex-1: Haiku for classification-style judging

**Eligible roles**: `l2_trigger` (batched classification), `judge_comparative` (pairwise A-vs-B).

**Mechanism**: already in place via `config.model_for(role)` + `SKILLFORGE_MODEL_<ROLE>` env override. Zero code changes to activate:
```bash
SKILLFORGE_MODEL_L2_TRIGGER=claude-haiku-4-5-20251001 \
SKILLFORGE_MODEL_JUDGE_COMPARATIVE=claude-haiku-4-5-20251001 \
uv run uvicorn skillforge.main:app
```

**Rule to enforce**: the roles `l2_trigger` and `judge_comparative` must NEVER have their model hardcoded. They go through `model_for(role)` like everything else. Captured as cross-cutting contract #2.

### Flex-2: Batched L4 ranking (vs. pairwise)

At pop=5 with 4 criteria, pairwise L4 is `C(5,2) × 4 = 40` LLM calls per generation — the single most expensive judging step. The batched alternative asks one LLM call to rank all N candidates on one criterion → `N × 4` calls per generation, ~10× cheaper.

**Mechanism**: `config.L4_STRATEGY` env flag with two values: `"pairwise"` (default, MVP) or `"batched_rank"` (cost-saver). The `comparative.py` layer implements both and dispatches on the flag.

**Enforced in code** (Step 6d L4):
```python
async def run_l4(results):
    if config.L4_STRATEGY == "batched_rank":
        return await _run_l4_batched(results)
    return await _run_l4_pairwise(results)
```

Both strategies write the same fields on `CompetitionResult`, so downstream code (Pareto computation, Breeder) is agnostic. The flag can flip per-run or globally.

### Flex-3: Consolidated Breeder LLM calls

Step 6e's Breeder as currently planned makes 4 distinct LLM calls per generation: (1) diagnostic mutation instructions, (2) crossover generation, (3) learning log extraction, (4) breeding report. Calls (3) and (4) operate on the same context and can be merged into one call.

**Mechanism**: `config.BREEDER_CALL_MODE` flag — `"separate"` (default, MVP) or `"consolidated"` (cost-saver). The consolidated path prompts the Breeder LLM for a structured JSON response containing both the new learning log entries and the breeding report.

**Enforced in code** (Step 6e): `breeder.py` factors the prompt assembly so either mode is a branch in a single helper, not a duplicated code path.

### Flex-4: Trace compression (DB size)

`competition_results.trace` is the largest blob we store. At production scale it becomes the dominant DB cost.

**Mechanism**: `config.COMPRESS_TRACES` bool flag. When true, `db/queries.py::save_result` runs the trace JSON through `zlib.compress` before insert, and `get_run` decompresses on read. A magic-byte prefix distinguishes compressed vs. raw rows so the switch is backward-compatible within a single database.

**MVP default**: OFF (simpler debugging). Flip to ON for production runs.

### Where these flags live

All four flags live in `skillforge/config.py` alongside the existing `WEBSEARCH_ENABLED` and `LIVE_TESTS`:

```python
# Cost-saver strategy flags — see PLAN.md §Flexibility Hooks
L4_STRATEGY: str = os.getenv("SKILLFORGE_L4_STRATEGY", "pairwise")
BREEDER_CALL_MODE: str = os.getenv("SKILLFORGE_BREEDER_CALL_MODE", "separate")
COMPRESS_TRACES: bool = os.getenv("SKILLFORGE_COMPRESS_TRACES", "0") == "1"
```

The point is not to pre-optimize — it's to make the code shapes compatible with the cost-savers so we can flip them later without a rewrite.

