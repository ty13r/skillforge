# PLAN-V1.2.md — Port Competitor to Anthropic Managed Agents

**Status**: ✅ LOCKED 2026-04-09 — all decisions resolved, risks smoke-checked, ready to build.
**Date**: 2026-04-09
**Picks up from**: PLAN-V1.1.md (locked + shipped). This is the next batch.

**Locked decisions (from review checklist)**:
- Advisor Strategy ships in Phase 1 (same commit as the Managed Agents port).
- Default executor model: **A/B tested on Phase 2** — Phase 1 wires both Haiku and Sonnet paths; Phase 2 runs the same fork-from-python-utils run under both + picks a winner based on correctness × cost on our workload.
- Advisor `max_uses = 3` default. Adjustable via `SKILLFORGE_COMPETITOR_ADVISOR_MAX_USES` env var.
- **Model swapping is a hard design goal**: every agent role must be swappable via a single env var with zero code changes. See §Model swap ergonomics below.
- Step 0 smoke test runs before any code, resolves open questions #1 and #2 inline.
- Phase 2 triggers after ≥3 days of Phase 1 on prod; Phase 3 triggers after ≥1 week of Phase 2 clean.
- `leaked_skills` cleanup: auto-sweep on app startup (via new `leaked_skills_sweeper` in the FastAPI lifespan handler, same pattern as `seed_loader`).
- Frontend `cost_breakdown` display: Phase 1 ships the backend field, Phase 2 adds the arena cost-card render (separate small commit).

---

## Risk smoke-check (completed 2026-04-09)

Three risks raised, all verified via doc review. Findings drove the three plan additions below (phased ship, best-effort teardown, session-runtime cost).

1. **Skill upload rate limits + teardown** → 🟡 yellow. Endpoint confirmed (`POST /v1/skills`, multipart form data, bundle via `files[]` or single zip, 30 MB cap). Delete is a 3-step dance: `GET /v1/skills/{id}/versions` → `DELETE /v1/skills/{id}/versions/{v}` for each → `DELETE /v1/skills/{id}`. Rate limits **not documented**. Mitigation: ship with `SKILLFORGE_MANAGED_AGENTS_SKILL_MODE=upload|inline` flag and run an empirical 20-upload smoke test as step 0 of implementation (see §Step 0).
2. **Pricing vs SDK** → 🟢 green. Managed Agents bills tokens at **standard model rates** (`$3/$15` Sonnet 4.6, `$1/$5` Haiku 4.5, `$5/$25` Opus 4.6 per MTok) **+ $0.08 per session-hour** metered only while status is `running` (not `idle`/`rescheduling`/`terminated`). Replaces Code Execution container-hour billing (no double-bill). For a calibrated 5×3×3 run (~$7.50 tokens currently): adds ~$0.18 runtime overhead = ~2.4%. Parallelism is effectively free — 5 concurrent 3-min sessions = same 0.25 session-hours as sequential. Worked example from docs: 1-hour Opus session with 50k in / 15k out = $0.705 ($0.25 input + $0.375 output + $0.08 runtime). Batch API discount, Fast mode, data-residency, and long-context premium all **don't apply** to Managed Agents sessions.
3. **Beta API churn** → 🟢 green. Dated beta header (`managed-agents-2026-04-01`) is the stability contract — Anthropic's convention is to freeze the API surface per header date; breaking changes ship in new dated headers with documented deprecation windows. Mitigation: pin the header as a module constant in `managed_agents.py`; audit `agent_toolset_20260401` tool shapes (`write_file`, bash) on every beta version bump since `_extract_written_files()` depends on them.

**Verdict**: safer than staying on the SDK. All SDK bugs are confirmed current; Managed Agents risks are theoretical and have documented escape hatches.

---

## Context

SkillForge's Competitor agent is the one place still using `claude-agent-sdk` (the local-subprocess SDK). Every other agent (Challenge Designer, Spawner, Breeder, Judge L2-L5) was already ported to `AsyncAnthropic` direct calls during Wave 5. The Competitor stayed on the SDK because it's the only agent that needs agentic tool-use (Read/Write/Bash) inside an isolated sandbox with the evolved Skill loaded via `setting_sources=["project"]`.

The SDK has been the source of several painful bugs this session:
- **Concurrency race**: multiple `query()` calls in the same process hit a subprocess/stdio contention bug. Forced `COMPETITOR_CONCURRENCY=1` → sequential competitor runs → 45-min default runs.
- **Memory bloat**: the `claude-agent-sdk` wheel is 68 MB and pushed Railway's build container past its OOM ceiling (required `UV_CONCURRENT_DOWNLOADS=1` workaround).
- **Silent hangs**: the SDK's subprocess can get stuck with no error output.

Anthropic's **Managed Agents** product (beta `managed-agents-2026-04-01`) solves all three:
- Each session runs in its own Anthropic-managed cloud container → no subprocess race, parallelism is free.
- Control plane is plain REST + SSE streaming, no heavyweight local SDK → smaller Docker image.
- Session events are observable via a typed event stream with `span.model_request_end` carrying real token counts → honest cost tracking.

**Outcome**: remove `claude-agent-sdk` entirely, lift `COMPETITOR_CONCURRENCY` to 5–10, shrink default run time from ~54 min → ~10 min, get real token-based cost tracking, fix the Railway OOM workaround.

---

## Architecture changes

### Current flow (SDK-based)
1. `evolution.py::run_evolution()` → for each `(skill, challenge)` pair, acquires semaphore, calls `run_competitor()`.
2. `competitor.py::run_competitor()`:
   - Creates a local temp sandbox (`/tmp/skillforge-{run_id}-gen{N}-competitor{i}/`) via `sandbox.create_sandbox()`.
   - Writes evolved SKILL.md to `{sandbox}/.claude/skills/evolved-skill/SKILL.md`.
   - Writes challenge setup files to `{sandbox}/challenge/`.
   - Calls `claude_agent_sdk.query()` with `cwd=sandbox`, `setting_sources=["project"]`.
   - SDK discovers the skill via filesystem convention, launches a local `claude` CLI subprocess.
   - Streams messages as they arrive; builds a trace list.
   - After completion, collects files from `{sandbox}/output/` via `sandbox.collect_written_files()`.
3. Returns `CompetitionResult{trace, output_files, skill_id, challenge_id}`.
4. L1 judge runs the test suite on `output_files` via subprocess; L3 parses `trace` for tool-use sequences.

### New flow (Managed Agents)
1. `evolution.py::run_evolution()` — same loop shape, but `COMPETITOR_CONCURRENCY` default bumps from `1` → `5`.
2. **New `competitor_managed.py::run_competitor()`**:
   - **One-time per run**: create a cloud environment with `pip: ["pytest", "ruff"]` pre-installed.
   - **Per-competitor**: upload the evolved SKILL.md as a custom skill → get a `skill_id`.
   - Create an agent referencing that `skill_id` + `agent_toolset_20260401` (bash/file ops) + a system prompt identical to the current competitor's.
   - Create a session against the agent and environment.
   - Send a `user.message` containing the challenge prompt AND the challenge setup files inlined as text (the agent writes them to disk in its first bash turn).
   - Stream session events until `session.status_idle` fires.
   - Parse the event stream:
     - `agent.tool_use` events with `name=="write_file"` or bash `cat > <path>` → reconstruct `output_files`
     - All events → `trace` (converted to the same dict shape L3 expects)
     - `span.model_request_end` events → sum `model_usage.input_tokens + output_tokens` for real cost
   - Return `CompetitionResult` with the same field shape as today.
   - Archive the custom skill + agent + session so they don't pollute the org.
3. L1/L3 work unchanged because the adapter layer preserves the existing `CompetitionResult` shape.

### Critical architectural decisions

1. **One-skill-per-competitor upload + teardown.** Custom skills are persistent org resources. To avoid accumulating thousands of skills, we upload → use → archive/delete per competitor run. Adds ~1–2s overhead per competitor but keeps the org clean. Alternative (baking the skill content into the system prompt instead) loses the `skill_was_loaded` behavioral signal that L3 depends on.

2. **Inline setup files via user.message text + agent bash writes.** Managed Agents has no documented file-upload-to-session API. We embed the setup files in the first user message as heredocs and the agent writes them to disk via bash before solving the challenge. Token cost is low (setup files are small) and it works today without waiting for a file-upload feature.

3. **Output file reconstruction from event stream.** Managed Agents has no documented files-retrieval API either. We parse `agent.tool_use` events for `write_file` and `bash` commands to reconstruct `output_files`. The `agent_toolset_20260401` tool set's `write_file` tool exposes the full content in the `tool_use.input`. Bash-based writes (`cat > file.py <<EOF ... EOF`) are also reconstructable from the bash command string.

4. **One environment per run, shared across all competitor sessions.** Environments are cheap to create and sessions are isolated per container anyway. Created at run start, archived at run end.

5. **Delete claude-agent-sdk dependency entirely.** Removes the 68 MB wheel, fixes the Railway OOM, removes `UV_CONCURRENT_DOWNLOADS=1` workaround. **But not in Phase 1** — see "Phased ship" below.

6. **Phased ship with a backend flag.** Ship `competitor_managed.py` alongside the existing `competitor.py` (renamed internally to `competitor_sdk.py` for clarity), gated by a new `SKILLFORGE_COMPETITOR_BACKEND=sdk|managed` env var. Phase 1 lands the new code with default still `sdk` so every existing test + deploy keeps working. Phase 2 flips the default to `managed` once a real run validates end-to-end. Phase 3 (separate commit, after ≥1 week of Managed Agents running stable on prod) deletes the SDK path + `claude-agent-sdk` dep + Dockerfile workarounds. Lets us A/B the two backends side by side on the same run, take a "before/after" screenshot for the demo narrative, and roll back in seconds via env var if anything blows up.

7. **Best-effort skill teardown + leak tracking.** Skill cleanup must never block the evolution loop. Each session schedules its own teardown as a detached `asyncio.create_task()` after the session ends. Failures are logged to a new `leaked_skills` table (`id TEXT, skill_id TEXT, created_at TEXT, run_id TEXT, error TEXT`) so a future batch cleanup can reap them. Don't fail the run on cleanup failures; don't await them before returning `CompetitionResult`.

8. **Session runtime cost in budget accounting.** Managed Agents bills `$0.08/session-hour` on top of token costs. The engine's per-competitor cost calculation must include this or budget caps become inaccurate. Track session start/end timestamps from `session.status_running` / `session.status_idle` events, compute `runtime_hours = (end - start) / 3600`, add `runtime_hours * 0.08` to each competitor's cost. Keep it as a separate line item in `CompetitionResult.cost_breakdown` (new field, dict) so the cost-update events can show "tokens: $X / runtime: $Y" to the user.

9. **Advisor Strategy: Haiku Competitor with Opus advisor.** Anthropic announced the Advisor Strategy (`advisor_20260301` tool type) the same week we're planning this port. It pairs a cheap executor with an expensive advisor: the advisor never calls tools or produces final output, it only provides strategic guidance when invoked. Published numbers are compelling for SkillForge's workload:
   - **Haiku + Opus advisor doubled BrowseComp** (19.7% → 41.2%), at 85% less cost than Sonnet solo
   - **Sonnet + Opus advisor** gained 2.7 pp on SWE-bench Multilingual, at 11.9% less cost than Opus solo
   - Competitor's task (read challenge → iterate → produce `solution.py`) is structurally identical to BrowseComp
   - Net expected impact: switching the Competitor from Sonnet → Haiku-with-Opus-advisor likely **improves L1 correctness while cutting token cost to ~30%** of current Sonnet spend

   **Integration**: the agent definition in `managed_agents.create_competitor_agent()` adds a new tool entry alongside `agent_toolset_20260401`:
   ```python
   tools=[
       {"type": "agent_toolset_20260401"},
       {
           "type": "advisor_20260301",
           "name": "advisor",
           "model": "claude-opus-4-6",
           "max_uses": 3,
       },
   ]
   ```
   `max_uses=3` caps the number of advisor invocations per session so a pathological case can't burn through budget. Gated by a new env flag `SKILLFORGE_COMPETITOR_ADVISOR=on|off` (default `on` once Phase 2 validates) so we can A/B the same run with and without the advisor to measure the actual quality delta on our workload.

   **Config changes**:
   - `model_for("competitor")` default flips from `claude-sonnet-4-6` → `claude-haiku-4-5-20251001` when `SKILLFORGE_COMPETITOR_BACKEND=managed` AND `SKILLFORGE_COMPETITOR_ADVISOR=on`
   - New role `competitor_advisor` defaulting to `claude-opus-4-6`, overridable via `SKILLFORGE_MODEL_COMPETITOR_ADVISOR`
   - `cost_breakdown` gets two new keys: `advisor_tokens_input_usd` and `advisor_tokens_output_usd`, billed at Opus rates ($5/$25 per MTok); executor tokens billed at the executor's rate

   **Risks**:
   - Advisor tool is in beta (`advisor_20260301`) — subject to the same stability contract as the Managed Agents beta header, but it's a separate beta dimension. Pin it as a constant in `managed_agents.py`.
   - Haiku 4.5 may not follow complex SKILL.md instructions as well as Sonnet even with an advisor. The A/B flag lets us measure this empirically on real evolutions before committing.
   - Advisor tokens generally 400–700 per call — cheap per call but budget still needs to track them separately.

---

## Model swap ergonomics (hard design goal)

Every agent role in SkillForge must be swappable with a **single env var** and **zero code changes**. This is already the design of `model_for(role)` in `config.py` — each role defaults via `MODEL_DEFAULTS` and each can be overridden via `SKILLFORGE_MODEL_<ROLE>`. The port must preserve this and extend it to the new roles.

**Complete role → env var map after the port**:

| Role | Default | Override env var | Notes |
|---|---|---|---|
| `challenge_designer` | Sonnet 4.6 | `SKILLFORGE_MODEL_CHALLENGE_DESIGNER` | Streaming via `stream_text` |
| `spawner` | Sonnet 4.6 | `SKILLFORGE_MODEL_SPAWNER` | Streaming via `stream_text` |
| `competitor` | Haiku 4.5 (if managed + advisor), Sonnet 4.6 otherwise | `SKILLFORGE_MODEL_COMPETITOR` | The executor in the Advisor Strategy |
| **`competitor_advisor`** | Opus 4.6 | `SKILLFORGE_MODEL_COMPETITOR_ADVISOR` | **NEW** — the Opus advisor, never calls tools |
| `breeder` | Sonnet 4.6 | `SKILLFORGE_MODEL_BREEDER` | Streaming via `stream_text` |
| `judge_trace` | Sonnet 4.6 | `SKILLFORGE_MODEL_JUDGE_TRACE` | L3 |
| `judge_comparative` | Sonnet 4.6 | `SKILLFORGE_MODEL_JUDGE_COMPARATIVE` | L4 — Haiku-safe candidate |
| `judge_attribution` | Sonnet 4.6 | `SKILLFORGE_MODEL_JUDGE_ATTRIBUTION` | L5 |
| `l2_trigger` | Sonnet 4.6 | `SKILLFORGE_MODEL_L2_TRIGGER` | Haiku-safe candidate (pure Y/N classification) |
| `spec_assistant` | Sonnet 4.6 | `SKILLFORGE_MODEL_SPEC_ASSISTANT` | User-facing chat |

**Implementation rule**: every new call site must go through `model_for(role)`. Never hardcode a model string. `competitor_managed.py` and the advisor tool config must both use `model_for("competitor")` and `model_for("competitor_advisor")` respectively.

**Verification**: a single unit test (`tests/test_config.py::test_every_role_overridable`) enumerates `MODEL_DEFAULTS` and asserts each role key has both (a) a default and (b) an env-var path that `model_for(role)` honors. If the test fails, the role wasn't registered correctly.

**Why this matters for the narrative**: the ability to swap any agent's model in 30 seconds is itself a demo-worthy property. "We ran the same evolution with Sonnet competitor, then with Haiku-plus-Opus-advisor, then with all-Opus, no code changes — here's the cost/quality chart" is a strong engineering story.

---

## File-by-file changes

### New files

**`skillforge/agents/managed_agents.py`** (new, ~200 lines)
Thin typed wrapper around the Anthropic Python SDK's Managed Agents beta API. Functions:
- `async create_environment(run_id, packages=["pytest", "ruff"]) -> env_id`
- `async upload_custom_skill(skill_md: str, name: str) -> skill_id` — uploads via `POST /v1/skills` (multipart), returns skill_id.
- `async create_competitor_agent(skill_id: str, system_prompt: str) -> agent_id`
- `async create_session(agent_id, environment_id) -> session_id`
- `async stream_session(client, session_id) -> AsyncIterator[Event]` — wraps `client.beta.sessions.events.stream()`.
- `async send_user_message(client, session_id, text: str) -> None`
- `async archive_agent(agent_id)`, `async archive_skill(skill_id)`, `async archive_session(session_id)` — cleanup. `archive_skill` implements the 3-step delete-versions-then-skill dance.
- Pins `managed-agents-2026-04-01` + `skills-2025-10-02` beta headers as module constants.

**`skillforge/agents/competitor_managed.py`** (new, ~250 lines)
The full new competitor implementation:
- `async def run_competitor(skill: SkillGenome, challenge: Challenge, env_id: str) -> CompetitionResult` — same signature as the current one except `sandbox_path` param is replaced with `env_id` (no more local sandbox).
- Internal flow:
  1. Upload skill, create agent, create session.
  2. Build the first `user.message` = system prompt (with `output/solution.py` convention) + challenge prompt + inlined setup files as heredocs.
  3. Stream events with an `asyncio.timeout(300)` wrapper.
  4. Accumulate trace + parse tool_use events → output_files.
  5. On `session.status_idle`, break.
  6. Schedule cleanup as a detached task (archive skill/agent/session). Log failures to `leaked_skills` table.
  7. Return `CompetitionResult(skill_id, challenge_id, trace, output_files, cost_breakdown, judge_reasoning)`.
- Internal helpers:
  - `_event_to_dict(event) -> dict` — converts streamed event objects to the dict shape L3 expects (`{type, role, content: [{type, name, input, text}]}`).
  - `_extract_written_files(events) -> dict[str, str]` — scans tool_use events for `write_file` calls and bash `cat > / tee` patterns; returns a `{path: content}` dict.
  - `_token_usage(events) -> dict` — sums `span.model_request_end` model_usage counts for real cost reporting.
  - `_runtime_cost(events) -> float` — computes session-hour cost from `session.status_running` and `session.status_idle` event timestamps × `$0.08`.

### Modified files

**`skillforge/agents/competitor.py`** → RENAME to `competitor_sdk.py` in Phase 1, DELETE in Phase 3
Phase 1 keeps the SDK implementation alongside the new Managed Agents one under `SKILLFORGE_COMPETITOR_BACKEND=sdk` (default). Phase 3 removes it after the Managed Agents path is validated on prod.

**`skillforge/agents/competitor.py`** (new thin dispatcher, ~20 lines, Phase 1)
```python
from skillforge.config import COMPETITOR_BACKEND
if COMPETITOR_BACKEND == "managed":
    from skillforge.agents.competitor_managed import run_competitor  # noqa: F401
else:
    from skillforge.agents.competitor_sdk import run_competitor  # noqa: F401
```
Gives `evolution.py` a stable import path that doesn't change between phases.

**`skillforge/engine/evolution.py`** (~15 lines changed)
- Import path is unchanged (`from skillforge.agents.competitor import run_competitor`) — the dispatcher above routes.
- After the initial `emit("run_started")`: create one environment per run via `managed_agents.create_environment(run.id)` **if `COMPETITOR_BACKEND == "managed"`**, store `env_id` in a local var.
- Pass `env_id` to every `_gated_competitor()` call instead of building a local sandbox.
- After all generations finish (or on `CancelledError` / exception): archive the environment.
- The sandbox-path-based logic in `_gated_competitor` becomes conditional on `COMPETITOR_BACKEND`. **L1's existing subprocess-based test-runner already works on `output_files` only, so it's unchanged.**

**`skillforge/engine/sandbox.py`** (no changes in Phase 1)
- Phase 1 keeps `create_sandbox()` + `collect_written_files()` because the SDK path still uses them.
- Phase 3 removes them.
- `validate_skill_structure()` stays forever — used by the Spawner and uploads endpoint.

**`skillforge/config.py`** (~25 lines changed)
- Add `COMPETITOR_BACKEND: str = os.getenv("SKILLFORGE_COMPETITOR_BACKEND", "sdk")` — Phase 1 default is `sdk`, Phase 2 flips to `managed`.
- Add `MANAGED_AGENTS_SKILL_MODE: str = os.getenv("SKILLFORGE_MANAGED_AGENTS_SKILL_MODE", "upload")` — fallback to `inline` if skill uploads rate-limit.
- Add `MANAGED_AGENTS_SESSION_RUNTIME_USD_PER_HOUR: float = 0.08` — constant from the published pricing page (2026-04-09); bumps require a plan edit.
- Add `COMPETITOR_ADVISOR: bool = os.getenv("SKILLFORGE_COMPETITOR_ADVISOR", "on") == "on"` — enables the `advisor_20260301` tool on the Competitor agent. Only meaningful when `COMPETITOR_BACKEND == "managed"`. Default `on` after Phase 2 validates on real runs.
- Add `COMPETITOR_ADVISOR_MAX_USES: int = int(os.getenv("SKILLFORGE_COMPETITOR_ADVISOR_MAX_USES", "3"))` — hard cap on advisor invocations per competitor session.
- Add new `MODEL_DEFAULTS` entries: `"competitor_advisor": "claude-opus-4-6"`. Overridable via `SKILLFORGE_MODEL_COMPETITOR_ADVISOR`.
- **Conditional default model for competitor**: when `COMPETITOR_BACKEND == "managed"` AND `COMPETITOR_ADVISOR`, flip `MODEL_DEFAULTS["competitor"]` from `claude-sonnet-4-6` → `claude-haiku-4-5-20251001` (Advisor Strategy published numbers show this is the cost-efficient sweet spot). SDK path keeps Sonnet.
- `COMPETITOR_CONCURRENCY` default: `1` → `5` ONLY when `COMPETITOR_BACKEND == "managed"`. Keep at 1 for the SDK path to preserve the subprocess-race workaround. Compute at import time: `COMPETITOR_CONCURRENCY = int(os.getenv("SKILLFORGE_COMPETITOR_CONCURRENCY", "5" if COMPETITOR_BACKEND == "managed" else "1"))`.
- Remove the old "SDK subprocess race" comment block in Phase 3.

**`skillforge/db/database.py` + `SCHEMA.md`** (new table)
- Add `leaked_skills` table: `id TEXT PRIMARY KEY, skill_id TEXT NOT NULL, run_id TEXT, created_at TEXT NOT NULL, error TEXT`.
- `CREATE INDEX idx_leaked_skills_created ON leaked_skills(created_at DESC)`.
- Document in SCHEMA.md under the Conventions section as a bookkeeping table for best-effort skill teardown failures. Cleanup job reads it, tries deletion again, removes rows on success.

**`skillforge/models/competition.py`** (~5 lines added)
- Add `cost_breakdown: dict[str, float] = field(default_factory=dict)` to `CompetitionResult`. Populated by `competitor_managed.py` with up to 5 keys: `{"executor_input_usd", "executor_output_usd", "advisor_input_usd", "advisor_output_usd", "session_runtime_usd"}`. SDK path leaves it empty (engine falls back to the old turn-count heuristic). Shown in the cost_update WebSocket event so the frontend can display a breakdown. Advisor tokens billed at Opus rates ($5/$25 per MTok); executor at whatever model is configured (Haiku default under the Advisor Strategy path).

**`pyproject.toml`** (Phase 3 only, Phase 1 may need a bump)
- Phase 1: bump `anthropic` to the latest version that includes the `beta.agents` / `beta.sessions` namespaces if not already present. Confirm during Step 0.
- Phase 3: remove `claude-agent-sdk` from `[project].dependencies`.

**`Dockerfile`** (Phase 3 only)
- Can remove the `UV_CONCURRENT_DOWNLOADS=1` + `UV_CONCURRENT_INSTALLS=1` workarounds now that the 68 MB SDK wheel is gone. Keep `UV_COMPILE_BYTECODE=0` + `UV_LINK_MODE=copy` as belt-and-suspenders.

**`tests/test_agents.py` / `tests/test_evolution.py`** (~50 lines changed in Phase 1)
- SDK mocks stay (Phase 1 default is `sdk`). Add NEW mocks that patch `skillforge.agents.managed_agents.stream_session` for the managed-backend tests.
- Parameterize the evolve test to run under both `COMPETITOR_BACKEND=sdk` and `=managed` so both paths are exercised in CI.
- The live integration test (`test_minimal_evolution_live`) should work unchanged regardless of backend.

**`tests/test_config.py`** (new, ~40 lines)
- `test_every_role_overridable()` — enumerates `MODEL_DEFAULTS`, asserts each key has a default string and that `model_for(role)` picks up `SKILLFORGE_MODEL_<ROLE_UPPER>` when set via monkeypatch.
- `test_competitor_advisor_registered()` — asserts `competitor_advisor` is in `MODEL_DEFAULTS` and its default is an Opus model string.
- `test_managed_advisor_flips_executor_default()` — when `COMPETITOR_BACKEND=managed` AND `COMPETITOR_ADVISOR=True`, the default for `competitor` must resolve to a Haiku model (or whatever the A/B test concludes).
- This test file is the tripwire that catches hardcoded model strings slipping in.

### Phase boundaries

**Phase 1 — ship the new backend behind a flag** (1 commit, default backend stays `sdk`)
- Step 0 smoke test runs and passes, or plan rolls back to `inline` mode
- Add `competitor_managed.py`, `managed_agents.py`
- Rename old `competitor.py` → `competitor_sdk.py`
- Add new thin `competitor.py` dispatcher
- Add `COMPETITOR_BACKEND`, `MANAGED_AGENTS_SKILL_MODE`, `MANAGED_AGENTS_SESSION_RUNTIME_USD_PER_HOUR` to `config.py`
- Add `leaked_skills` table to `database.py` + `SCHEMA.md`
- Add `cost_breakdown` to `CompetitionResult`
- All tests still pass (SDK path unchanged, new tests added for managed path)
- Deploy to prod with `SKILLFORGE_COMPETITOR_BACKEND=sdk` (default) — behavior unchanged for users

**Phase 2 — flip the default, validate on prod** (env var change + smoke test, no commit)
- Set `SKILLFORGE_COMPETITOR_BACKEND=managed` on Railway
- Run a 2×1 fork-from-python-utils run end-to-end
- Then a 5×3 run for the "before/after" screenshot
- Validate: parallelism works, `leaked_skills` stays empty, session-runtime accounting is accurate, L1/L3 still read the expected shapes
- If anything breaks, flip back to `sdk` in seconds via env var

**Phase 3 — delete the SDK path** (after ≥3 days of Phase 2 running clean)
- Delete `competitor_sdk.py`
- Collapse `competitor.py` dispatcher into a direct import from `competitor_managed.py`
- Remove `claude-agent-sdk` from `pyproject.toml`
- Remove `UV_CONCURRENT_DOWNLOADS=1` + `UV_CONCURRENT_INSTALLS=1` from Dockerfile
- Remove `create_sandbox()` and `collect_written_files()` from `sandbox.py`
- Delete the old "SDK subprocess race" comment in `config.py`
- Ship as a separate commit so rollback is a single revert

### Unchanged (sanity-check dependencies)

- `skillforge/models/competition.py` — `CompetitionResult` shape unchanged except for the new `cost_breakdown` dict (additive, backward-compat).
- `skillforge/agents/judge/deterministic.py` (L1) — reads `output_files`; unchanged.
- `skillforge/agents/judge/trace_analysis.py` (L3) — reads `trace` as `list[dict]` with `type/content[name]/content[input]`; adapter in `competitor_managed.py` preserves this exact shape.
- `skillforge/agents/spawner.py::spawn_from_parent()` — no Competitor touchpoint.
- Frontend — no API changes.

---

## Critical files to reference (existing functions reused)

| File | Function | Why it's reused |
|---|---|---|
| `skillforge/models/competition.py` | `CompetitionResult` | Return shape contract — the whole judging pipeline reads these fields |
| `skillforge/engine/sandbox.py` | `validate_skill_structure()` | Still needed by Spawner + upload endpoint |
| `skillforge/agents/_llm.py` | `stream_text()` | Not directly used by Managed Agents (different API) but proves the streaming-over-SSE pattern works |
| `skillforge/config.py` | `model_for("competitor")`, `ANTHROPIC_API_KEY` | Agent creation payload pulls model and auth from here |
| `skillforge/agents/competitor_sdk.py::_COMPETITOR_SYSTEM_PROMPT` | The existing system prompt | Copy verbatim into the new agent's `system` field — it's the key to getting `output/solution.py` output |

---

## Step 0: Rate-limit smoke test (before any code changes)

Before starting the port, run an empirical check to flush out the biggest unknown — skill upload rate limits. Doc doesn't specify a cap; we need to know the real number.

**Test script** (run as a standalone Python file, not committed):

```python
# scripts/smoke_skill_upload.py
import asyncio, time, httpx, os

API_KEY = os.environ["ANTHROPIC_API_KEY"]
HEADERS = {
    "x-api-key": API_KEY,
    "anthropic-version": "2023-06-01",
    "anthropic-beta": "skills-2025-10-02",
}
SKILL_MD = """---
name: smoke-test-{i}
description: Placeholder smoke-test skill for rate limit testing. Use when running the SkillForge v1.2 rate-limit smoke test. NOT for production.
---

# Smoke Test {i}

Throwaway skill for rate-limit testing.
"""

async def upload(client, i):
    files = {"files[]": ("SKILL.md", SKILL_MD.format(i=i).encode(), "text/markdown")}
    data = {"display_title": f"Smoke Test {i}"}
    r = await client.post("https://api.anthropic.com/v1/skills", headers=HEADERS, files=files, data=data)
    return r.status_code, r.json().get("id") if r.status_code == 200 else r.text

async def delete_skill(client, skill_id):
    # List + delete versions first
    v = await client.get(f"https://api.anthropic.com/v1/skills/{skill_id}/versions", headers=HEADERS)
    for version in v.json().get("data", []):
        await client.delete(f"https://api.anthropic.com/v1/skills/{skill_id}/versions/{version['version']}", headers=HEADERS)
    await client.delete(f"https://api.anthropic.com/v1/skills/{skill_id}", headers=HEADERS)

async def main():
    uploaded = []
    async with httpx.AsyncClient(timeout=60) as client:
        t0 = time.monotonic()
        # Burst: 20 serial uploads
        for i in range(20):
            status, result = await upload(client, i)
            print(f"[{i:2d}] {status} {result}")
            if status == 200:
                uploaded.append(result)
            elif status == 429:
                print(f"  → rate limited after {i} uploads in {time.monotonic() - t0:.1f}s")
                break
        # Parallel burst: 10 concurrent uploads
        t1 = time.monotonic()
        results = await asyncio.gather(*(upload(client, 100 + i) for i in range(10)))
        print(f"parallel burst: {[r[0] for r in results]} in {time.monotonic() - t1:.1f}s")
        uploaded.extend(r[1] for r in results if r[0] == 200)
        # Cleanup
        print(f"cleaning up {len(uploaded)} skills...")
        for skill_id in uploaded:
            try:
                await delete_skill(client, skill_id)
            except Exception as exc:
                print(f"  cleanup failed for {skill_id}: {exc}")

asyncio.run(main())
```

**Expected outcomes**:
- All 30 uploads succeed → rate limits are permissive enough; proceed with `upload` mode as default.
- Partial 429s at N uploads → document N in the plan; set `COMPETITOR_CONCURRENCY ≤ N/2` to stay under the burst cap; still default to `upload` mode.
- All parallel-burst uploads 429 → rate limits are strict; flip default to `SKILLFORGE_MANAGED_AGENTS_SKILL_MODE=inline` and accept losing the L3 `skill_was_loaded` signal.
- Cleanup fails silently for some skills → document the exact 3-step dance + verify the `leaked_skills` table plan is correct.

**Also resolve in the same smoke test**:
- Create a session with `agent_toolset_20260401`, send one message that writes a 10KB file, and inspect the streamed events. Confirm `write_file`'s `input.content` field (or whatever it's called) holds the full file content, not a truncated preview. This resolves Open Question #1 below.
- Collect the first `span.model_request_end` event from the stream and record the exact `model_usage` field path. Resolves Open Question #2.

---

## Open questions (remaining after risk smoke-check)

Risk smoke-check resolved the big ones (see the top-of-file summary). Remaining:

1. **Output file reconstruction fidelity.** The `agent_toolset_20260401` write_file tool's `input` field — is it the full file content, or a truncated preview? Need to verify against `/docs/en/managed-agents/tools`. If truncated, fall back to bash heredoc detection OR add a `cat $FILE` turn at the end of the session to retrieve contents inline. **Resolve during the Step 0 smoke test** by creating a session that writes a 10KB file and inspecting the streamed `agent.tool_use` event.

2. **Span event payload shape.** `span.model_request_end` token count fields — need to confirm exact field names (`model_usage.input_tokens` vs `model_usage.tokens.input` etc.) by inspecting the live event stream during Step 0.

3. **Per-org session concurrency limits during beta.** Not documented. Start at `COMPETITOR_CONCURRENCY=5` and monitor for 429s on session creation. If we hit them, throttle down via env var and contact Anthropic support.

**The first two resolve during the Step 0 smoke test (add a session-creation + single-message flow). The third is an empirical runtime measurement during the first full-scale test.**

---

## Verification

### After Phase 1 (backend behind flag, default still sdk)

1. **Unit tests**: `uv run pytest tests/ -q` — 184/184 pass. The SDK path is untouched, so all existing mocks work. New `competitor_managed.py` has its own mocks patching `skillforge.agents.managed_agents.stream_session`.
2. **Import graph**: `uv run python -c "from skillforge.main import app"` — both `claude_agent_sdk` AND the new `managed_agents` module import cleanly.
3. **Docker build**: `docker build .` — succeeds. Image size unchanged at this phase (SDK still present).
4. **Env flag smoke test**: `SKILLFORGE_COMPETITOR_BACKEND=managed uv run pytest tests/test_agents.py tests/test_evolution.py` — the managed path runs its tests against mocks.
5. **Prod deploy**: push with default `sdk` backend. Behavior unchanged for users. Confirm `/api/invites/status` and a small real run still work.

### After Phase 2 (default flipped to managed on prod)

6. **Local end-to-end with managed backend**: `SKILLFORGE_COMPETITOR_BACKEND=managed` + start backend + frontend, kick off a 2×1 fork-from-python-utils run. Expect:
   - Zero subprocess errors (there's no subprocess)
   - Completion in <5 minutes (vs. current ~9 min for 2×1)
   - Correct `output_files` with `solution.py` populated
   - L1 score > 0 (tests pass)
   - `leaked_skills` table stays empty (teardown succeeded)
7. **Parallelism stress test**: 5×1 run. Expect ~1-2 minutes total with concurrency=5 vs ~5 min sequential. No 429s. Monitor Railway logs for any session-creation errors.
8. **Cost tracking**: verify `CompetitionResult.cost_breakdown` has three keys (`tokens_input_usd`, `tokens_output_usd`, `session_runtime_usd`) summing close to `total_cost_usd`. Compare against the Anthropic Console usage page for the same API key — should match within rounding.
9. **Full 5×3 validation run**: start a real evolution. Expect ~10-15 min total (vs. current ~54 min) at ~$7.70 ($7.50 tokens + ~$0.18 runtime). Screenshot the arena "before/after" for the demo narrative.
10. **Rollback rehearsal**: flip `SKILLFORGE_COMPETITOR_BACKEND=sdk` on Railway without a code push, run another 2×1, confirm the SDK path still works as the safety net.

11. **Executor + advisor A/B matrix**: run the same fork-from-python-utils run (2×1×3 for speed) **four times** to fill out the A/B matrix and pick a default:

    | Run | `SKILLFORGE_MODEL_COMPETITOR` | `SKILLFORGE_COMPETITOR_ADVISOR` | Hypothesis |
    |---|---|---|---|
    | A | `claude-haiku-4-5-20251001` | `off` | Cheapest baseline |
    | B | `claude-haiku-4-5-20251001` | `on` | Advisor Strategy default (matches BrowseComp setup) |
    | C | `claude-sonnet-4-6` | `off` | Current production default |
    | D | `claude-sonnet-4-6` | `on` | Sonnet + advisor (matches SWE-bench setup) |

    **Record for each run**: total cost (tokens + session runtime), total wall time, L1 correctness average, L3 `skill_was_loaded` rate, advisor invocation count, number of `run_failed` or `cancelled` outcomes.

    **Decision rule**:
    - If **B** (Haiku+advisor) meets or beats **C** (Sonnet solo) on correctness, ship B as the default — that's the maximum cost win with the Advisor Strategy narrative intact.
    - If **B** underperforms **C** on correctness but **D** beats **C**, ship D — advisor helps but Haiku is too weak for our workload.
    - If neither B nor D beats C, ship C — the port still wins on parallelism + honest cost tracking even without the Advisor Strategy.

    **Commit the final matrix results to `journal/NNN-advisor-ab-test.md`** so the decision is traceable and reproducible.

### After Phase 3 (SDK path deleted)

11. **Image size**: `docker build .` succeeds with no `UV_CONCURRENT_*=1` workarounds. Image shrinks by ~60 MB (the `claude-agent-sdk` wheel).
12. **Import graph**: `uv run python -c "import sys, skillforge.main; assert 'claude_agent_sdk' not in sys.modules"` — SDK is fully gone.
13. **Final prod deploy**: push Phase 3 commit. Confirm `/api/health` + a small run works on the first post-delete deploy.

---

## Carried over from PLAN-V1.1 (backfill work)

PLAN-V1.1 shipped all four features end-to-end (seed library, upload existing skill, Anthropic palette, theme toggle — see the 2026-04-09 entries in `plans/PROGRESS.md`). Three testing-strategy items from PLAN-V1.1 and one one-off QA sweep never landed, so they're captured here to keep them from falling through the cracks during the v1.2 port.

**Priority**: backfill work, not blockers for the Managed Agents port. Can ship as a standalone commit **before** Phase 1, or interleaved with Phase 1's test additions — whichever keeps the diff clean. The `test_config.py` tripwire specified in §File-by-file changes is orthogonal to these and still lands as part of Phase 1.

**Architectural note**: PLAN-V1.1 §1.5 specified a `seed_skill_id` column on `evolution_runs`; the shipped implementation replaced that with an in-memory `PENDING_PARENTS` dict in `skillforge/api/routes.py` + `skillforge/agents/spawner.py::spawn_from_parent()`. This was a deliberate divergence (documented in the 2026-04-09 PROGRESS.md entries), not a gap — tests should target the shipped behavior, not the original plan.

### 1. `tests/test_seeds.py` (new file)

**Source**: PLAN-V1.1 §1.5 file list + §Testing strategy §1.

**What to cover**:
- `seed_loader.load_seeds()` idempotency — running it twice on the same DB is a no-op (hash comparison short-circuits).
- `seed_loader.load_seeds()` refresh — bumping the `SEED_SKILLS` content hash triggers a re-insert of the synthetic `seed-library` run without duplicating rows.
- `spawner.spawn_from_parent(parent, pop_size)` — returns `pop_size` genomes with the parent carried through as elite slot 0 and the rest as diverse mutations. Every returned genome passes `validate_skill_structure()`.
- Fork-from-seed integration (mocked LLM): load the seed library, POST `/api/evolve/from-parent` with `parent_source="registry"`, assert the new run has the seed's content as gen 0 and the `PENDING_PARENTS` entry is resolved + cleaned up.
- 404 on an unknown seed id.

**Verification**: `uv run pytest tests/test_seeds.py -v` passes; mocks cover the full fork flow without hitting the real Anthropic API.

### 2. `tests/test_uploads.py` (new file)

**Source**: PLAN-V1.1 §2.5 file list + §Testing strategy §2.

**What to cover**:
- Happy path — single `.md` upload → parses frontmatter, returns valid `upload_id` + `validation.ok=true`.
- Happy path — `.zip` with `SKILL.md` at root → valid.
- Happy path — `.zip` with `SKILL.md` one directory deep → valid.
- Size cap: `.md` file >1 MB → rejected with a clear error.
- Size cap: `.zip` unpacked >5 MB → rejected.
- File cap: `.zip` with >100 entries → rejected.
- Zip bomb: compression ratio >20:1 → rejected without OOM (test runs under a strict memory budget).
- Path traversal: `.zip` with a `..` entry → rejected.
- Path traversal: `.zip` with an absolute path entry → rejected.
- Extension allowlist: `.zip` containing a disallowed extension (e.g. `.exe`) → rejected.
- Structural validation failure (`validate_skill_structure()` violations) → errors surface to the client in the response payload.
- Upload → evolve integration: upload a valid skill, POST `/api/evolve/from-parent` with `parent_source="upload"`, assert the run starts and the `PENDING_PARENTS` entry is consumed.

**Verification**: `uv run pytest tests/test_uploads.py -v` passes; each case has its own test function so failures point to the exact rule that broke.

### 3. `frontend/src/hooks/useTheme.test.ts` (new file)

**Source**: PLAN-V1.1 §Testing strategy §4.

**What to cover**:
- On mount: reads `skld-theme` cookie → falls back to `"system"` if missing → resolves via `matchMedia('(prefers-color-scheme: dark)')`.
- `setTheme("dark")` writes the cookie with 1-year expiry and sets `document.documentElement.dataset.theme = "dark"`.
- `setTheme("system")` removes the explicit theme and re-subscribes to `matchMedia`.
- Media-query change event flips the resolved theme when the state is `"system"`.
- Cookie round-trip: reloading the hook picks up the persisted value.

**Verification**: `cd frontend && npm run test useTheme` passes under the existing vitest 2.1.9 harness (same setup used for `derivePhases.test.ts`). This is the second vitest file in the repo — the harness is already in place; no new dev-dep work required.

### 4. Grep sweep: no hardcoded hex values outside the token system

**Source**: PLAN-V1.1 §Testing strategy §3. A one-off verification step to confirm the palette migration left no hex literals in component source. Run once, record the result in the next journal entry, then forget.

**Command**:
```bash
rg '#[0-9a-fA-F]{3,8}\b' frontend/src \
  --glob '!*.css' \
  --glob '!*.config.*' \
  --type-add 'tsx:*.tsx' --type ts --type tsx
```

**Expected outcome**: zero matches in `.ts`/`.tsx` component source. Legitimate hex values should live only in `frontend/src/index.css` (CSS variable definitions) and `frontend/tailwind.config.js` (the Tailwind token map referencing those variables).

**If matches exist**: refactor each to a Tailwind token class (`bg-primary`, `text-on-surface`, etc.) or a `rgb(var(--color-xxx) / <alpha-value>)` reference. File a short journal note with the finding so it doesn't regress on the next palette pass.

---

## Out of scope

- **Meta mode** (v1.1) — untouched.
- **Spawner / Breeder / Judge layers** — all already use `AsyncAnthropic` direct calls; no change.
- **Frontend** — Managed Agents is purely a backend-side swap; the WebSocket event stream, arena UI, and run detail endpoint are unchanged. The new `cost_breakdown` field can optionally be rendered in the arena cost card, but that's polish, not blocking.
- **Persistent skill library** — we upload-and-delete per run. Storing evolved skills permanently as org-level custom skills is a v1.3+ feature (would make the Registry's exported skills directly usable in Claude.ai).
- **Migration of existing runs** — runs already in the DB don't need re-running. The port only affects new runs.

---

## Risk / rollback plan

The phased ship (§Phase boundaries) IS the rollback plan. Three rollback levers, each cheap:

**Lever 1: Skill upload rate-limited or unreliable** → flip `SKILLFORGE_MANAGED_AGENTS_SKILL_MODE=inline` (no redeploy needed, just a Railway env var change + restart). Bakes the evolved SKILL.md into the agent's system prompt. Loses the L3 `skill_was_loaded` signal but everything else works. Trade-off is explicit and measured.

**Lever 2: Managed Agents backend has a bug in production** → flip `SKILLFORGE_COMPETITOR_BACKEND=sdk` (same mechanism, env var + restart). Drops back to the old SDK path with all its known issues (sequential runs, 68 MB wheel) but every bug is familiar. This is available through the entire Phase 2 window and disappears at Phase 3.

**Lever 3: Anthropic changes the beta API** → pin the beta header in `managed_agents.py` and treat header bumps as plan-edit events (not silent auto-updates). If Anthropic deprecates the header we currently pin, we get a deprecation window to migrate.

**Lever 4: Advisor Strategy doesn't help (or hurts) on our workload** → flip `SKILLFORGE_COMPETITOR_ADVISOR=off` (env var + restart). Drops back to Haiku solo on the managed backend. Keeps all the other port wins (parallelism, no subprocess race, honest cost tracking) without relying on the advisor quality delta. Alternatively, set `SKILLFORGE_MODEL_COMPETITOR=claude-sonnet-4-6` to go back to Sonnet-solo at ~3x the Haiku cost if quality on our workload demands it.

There is **no undoable destructive step** until Phase 3 deletes the SDK path. That deletion is a separate commit that can be reverted with a single `git revert` if anything goes wrong in the first few days.

---

## Review checklist

All items resolved — see the Locked decisions block at the top of the file. Plan is ready to execute starting with the Step 0 smoke test.
