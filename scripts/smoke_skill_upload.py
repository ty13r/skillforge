"""Step 0 smoke test for the Managed Agents port (PLAN-V1.2 §Step 0).

Probes the Anthropic Skills + Managed Agents + Advisor Strategy beta APIs
empirically before committing any code in PLAN-V1.2 Phase 1. Resolves five
unknowns documented in the plan:

  1. Skill upload rate limits (serial 20 + parallel 10 burst).
  2. Whether ``beta.skills.delete`` handles the version dance internally.
  3. ``agent_toolset_20260401`` write_file event payload (full content
     vs preview).
  4. ``span.model_request_end`` (or equivalent) token usage field path.
  5. ``advisor_20260301`` tool availability on the Competitor agent.

Run via: ``uv run python scripts/smoke_skill_upload.py``

Cost estimate: ~$0.50 — most calls are control-plane (free); the only token
spend is one Haiku session writing a 10 KB file (~$0.05) and one short
advisor probe session (~$0.20-0.30 if Opus advisor tokens are billed during
the throwaway agent test).

Outputs: a structured stdout report. Capture it via ``tee`` if you want it
saved alongside the journal entry.

Safety: every created resource is tracked + torn down in a ``finally`` block.
The script never touches the 4 Anthropic built-in skills (xlsx/pptx/pdf/docx)
because cleanup filters on ``source != "anthropic"``.
"""

from __future__ import annotations

import asyncio
import json
import time
import traceback

from anthropic import AsyncAnthropic

import skillforge.config  # noqa: F401 — triggers .env autoloader on import

# Beta header constants — pinned per PLAN-V1.2 architectural decision #6
SKILLS_BETA = "skills-2025-10-02"
MANAGED_AGENTS_BETA = "managed-agents-2026-04-01"
ADVISOR_BETA = "advisor-2026-03-01"

SKILL_NAME_PREFIX = "sf-smoke-test"
SKILL_MD_TEMPLATE = """---
name: {name}
description: Throwaway smoke-test skill #{i} for the SkillForge v1.2 rate-limit smoke test. Use when running the SkillForge Step 0 probe. NOT for production.
---

# Smoke Test {i}

## Workflow
- Step one: do nothing
- Step two: still do nothing

## Examples
**Example 1:** input → output
**Example 2:** other input → other output
"""

# 10 KB filler used by the session-event-shape probe.
TEN_KB_FILLER = "x" * (10 * 1024)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_skill_md(i: int) -> str:
    return SKILL_MD_TEMPLATE.format(name=f"{SKILL_NAME_PREFIX}-{i:03d}", i=i)


async def _upload_one(client: AsyncAnthropic, i: int) -> tuple[str | None, str | None, float]:
    """Upload a single throwaway skill. Returns (skill_id, error, elapsed_seconds).

    The Anthropic Skills API requires SKILL.md to live inside a top-level
    folder — passing a bare ``SKILL.md`` filename returns 400 with
    "SKILL.md file must be exactly in the top-level folder."
    """
    t0 = time.monotonic()
    name = f"{SKILL_NAME_PREFIX}-{i:03d}"
    try:
        resp = await client.beta.skills.create(
            display_title=f"{SKILL_NAME_PREFIX} {i}",
            files=[
                (
                    f"{name}/SKILL.md",
                    _make_skill_md(i).encode("utf-8"),
                    "text/markdown",
                )
            ],
            betas=[SKILLS_BETA],
        )
        elapsed = time.monotonic() - t0
        skill_id = getattr(resp, "id", None)
        return skill_id, None, elapsed
    except Exception as exc:  # noqa: BLE001
        elapsed = time.monotonic() - t0
        return None, f"{exc.__class__.__name__}: {str(exc)[:200]}", elapsed


async def _delete_skill_safely(client: AsyncAnthropic, skill_id: str) -> str | None:
    """Delete a skill via the 3-step dance. Returns error string or None.

    The SDK's ``beta.skills.delete()`` does NOT auto-delete versions —
    confirmed via Step 0 probe. Must list, delete each version, then
    delete the skill.
    """
    try:
        # Step 1+2: enumerate and delete versions
        versions_page = await client.beta.skills.versions.list(
            skill_id, betas=[SKILLS_BETA]
        )
        async for v in versions_page:
            d = v.model_dump() if hasattr(v, "model_dump") else dict(v)
            ver = d.get("version") or d.get("id")
            if ver is None:
                continue
            try:
                await client.beta.skills.versions.delete(
                    version=str(ver),
                    skill_id=skill_id,
                    betas=[SKILLS_BETA],
                )
            except Exception as exc:  # noqa: BLE001
                return f"version delete failed: {type(exc).__name__}: {str(exc)[:200]}"

        # Step 3: delete the skill itself
        await client.beta.skills.delete(skill_id, betas=[SKILLS_BETA])
        return None
    except Exception as exc:  # noqa: BLE001
        return f"{exc.__class__.__name__}: {str(exc)[:200]}"


async def _list_smoke_skills(client: AsyncAnthropic) -> list[dict]:
    """List skills, filter to source != 'anthropic' AND name has the smoke prefix."""
    resp = await client.beta.skills.list(betas=[SKILLS_BETA])
    leftovers: list[dict] = []
    for s in getattr(resp, "data", []) or []:
        d = s.model_dump() if hasattr(s, "model_dump") else dict(s)
        if d.get("source") == "anthropic":
            continue
        title = (d.get("display_title") or "").lower()
        sid = (d.get("id") or "").lower()
        if SKILL_NAME_PREFIX in title or "smoke" in title or "smoke" in sid:
            leftovers.append(d)
    return leftovers


# ---------------------------------------------------------------------------
# Probe 1 — serial 20 uploads
# ---------------------------------------------------------------------------


async def probe_serial_uploads(client: AsyncAnthropic, n: int = 20) -> list[str]:
    print(f"\n=== Probe 1: serial {n} skill uploads ===")
    uploaded: list[str] = []
    failures = 0
    rate_limited_at: int | None = None

    t_start = time.monotonic()
    for i in range(n):
        skill_id, err, elapsed = await _upload_one(client, i)
        marker = "OK" if skill_id else "FAIL"
        print(f"  [{i:2d}] {marker} {elapsed:5.2f}s {skill_id or err}")
        if skill_id:
            uploaded.append(skill_id)
        else:
            failures += 1
            if err and ("429" in err or "rate" in err.lower() or "quota" in err.lower()):
                rate_limited_at = i
                print(f"  → rate-limited after {i} successful uploads")
                break
    t_total = time.monotonic() - t_start
    print(f"  total: {len(uploaded)}/{n} ok, {failures} failed in {t_total:.1f}s")
    if rate_limited_at is not None:
        print(f"  rate_limit_threshold ≈ {rate_limited_at} requests")
    return uploaded


# ---------------------------------------------------------------------------
# Probe 2 — parallel 10 burst
# ---------------------------------------------------------------------------


async def probe_parallel_uploads(client: AsyncAnthropic, n: int = 10) -> list[str]:
    print(f"\n=== Probe 2: parallel {n} skill uploads ===")
    t_start = time.monotonic()
    results = await asyncio.gather(
        *(_upload_one(client, 100 + i) for i in range(n)),
        return_exceptions=False,
    )
    t_total = time.monotonic() - t_start
    uploaded = [r[0] for r in results if r[0]]
    failures = [r[1] for r in results if not r[0]]
    print(f"  total: {len(uploaded)}/{n} ok, {len(failures)} failed in {t_total:.1f}s")
    for i, (sid, err, elapsed) in enumerate(results):
        marker = "OK" if sid else "FAIL"
        print(f"  [{i:2d}] {marker} {elapsed:5.2f}s {sid or err}")
    return uploaded


# ---------------------------------------------------------------------------
# Probe 3 — session event shape
# ---------------------------------------------------------------------------


async def probe_session_event_shape(client: AsyncAnthropic) -> dict:
    """Create one cheap session, write a 10 KB file, poll events.list for findings.

    Notes from the first attempt:
      - ``beta.sessions.events.stream`` returns an ``AsyncStream`` whose SSE
        decoder is hardcoded for Anthropic Messages API event names
        (message_start, content_block_delta, ...). It silently filters out
        every Managed Agents event type, then drops the connection. We use
        ``events.list`` polling instead to get structured ``BetaManagedAgentsSessionEvent``
        objects directly.
    """
    print("\n=== Probe 3: session event shape (events.list polling) ===")
    findings: dict = {
        "agent_id": None,
        "session_id": None,
        "environment_id": None,
        "events_observed": [],
    }
    agent_id = None
    env_id = None
    session_id = None

    try:
        env_resp = await client.beta.environments.create(
            name="sf-smoke-env",
            config={
                "type": "cloud",
                "packages": {
                    "type": "packages",
                    "pip": [],
                },
            },
            betas=[MANAGED_AGENTS_BETA],
        )
        env_id = getattr(env_resp, "id", None)
        findings["environment_id"] = env_id
        print(f"  environment: {env_id}")

        agent_resp = await client.beta.agents.create(
            name="sf-smoke-agent",
            model="claude-haiku-4-5-20251001",
            system="You are a smoke-test agent. When asked to write a file, do so with bash.",
            tools=[{"type": "agent_toolset_20260401"}],
            betas=[MANAGED_AGENTS_BETA],
        )
        agent_id = getattr(agent_resp, "id", None)
        findings["agent_id"] = agent_id
        print(f"  agent: {agent_id}")

        session_resp = await client.beta.sessions.create(
            agent=agent_id,
            environment_id=env_id,
            title="sf-smoke-session",
            betas=[MANAGED_AGENTS_BETA],
        )
        session_id = getattr(session_resp, "id", None)
        findings["session_id"] = session_id
        print(f"  session: {session_id}")

        prompt = (
            f"Write exactly {len(TEN_KB_FILLER)} 'x' characters to /tmp/probe.txt "
            f"using bash. Then run `wc -c /tmp/probe.txt` to confirm size and stop."
        )
        await client.beta.sessions.events.send(
            session_id,
            events=[
                {
                    "type": "user.message",
                    "content": [{"type": "text", "text": prompt}],
                }
            ],
            betas=[MANAGED_AGENTS_BETA],
        )
        print("  user.message sent — polling events.list...")

        # Poll events.list until we see session.status_idle (or hit a safety cap).
        seen_event_types: set[str] = set()
        all_events: list[dict] = []
        idle_seen = False
        running_at: str | None = None
        idle_at: str | None = None
        deadline = time.monotonic() + 180  # 3 min cap

        while time.monotonic() < deadline:
            events_seen_this_poll = 0
            page = await client.beta.sessions.events.list(
                session_id,
                limit=100,
                order="asc",
                betas=[MANAGED_AGENTS_BETA],
            )
            async for ev in page:
                events_seen_this_poll += 1
                d = ev.model_dump() if hasattr(ev, "model_dump") else dict(ev)
                etype = d.get("type", "?")
                seen_event_types.add(str(etype))
                all_events.append(d)
                if etype == "session.status_running":
                    running_at = d.get("processed_at") and str(d["processed_at"])
                if etype == "session.status_idle":
                    idle_seen = True
                    idle_at = d.get("processed_at") and str(d["processed_at"])
            print(
                f"  poll: {events_seen_this_poll} events this poll, "
                f"{len(all_events)} total, types so far: {sorted(seen_event_types)}"
            )
            if idle_seen:
                break
            if events_seen_this_poll == 0 and len(all_events) > 0:
                # No new events for a poll cycle — check session status directly
                pass
            await asyncio.sleep(2.0)
        else:
            print("  → poll deadline reached without session.status_idle")

        findings["events_observed"] = sorted(seen_event_types)
        findings["n_events"] = len(all_events)
        findings["running_at"] = running_at
        findings["idle_at"] = idle_at
        findings["session_runtime_seconds"] = None
        if running_at and idle_at:
            from datetime import datetime as _dt
            try:
                start = _dt.fromisoformat(running_at.replace("Z", "+00:00"))
                end = _dt.fromisoformat(idle_at.replace("Z", "+00:00"))
                findings["session_runtime_seconds"] = (end - start).total_seconds()
            except Exception:
                pass

        # Inspect tool_use events for write_file / bash content
        write_file_events = [e for e in all_events if e.get("type") == "agent.tool_use" and e.get("name") == "write_file"]
        bash_events = [e for e in all_events if e.get("type") == "agent.tool_use" and e.get("name") == "bash"]
        if write_file_events:
            sample = write_file_events[0]
            inp = sample.get("input", {}) or {}
            content_field = None
            for key in ("content", "file_content", "text", "contents"):
                v = inp.get(key)
                if isinstance(v, str):
                    content_field = key
                    break
            content_len = len(inp.get(content_field, "")) if content_field else 0
            findings["write_file_payload_full"] = content_len >= 9000
            findings["write_file_content_field"] = content_field
            findings["write_file_content_len"] = content_len
            findings["write_file_input_keys"] = list(inp.keys())
            print(
                f"  write_file: payload={content_len} bytes via "
                f"field='{content_field}' (full≥9KB={'yes' if content_len >= 9000 else 'no'}), "
                f"input keys={list(inp.keys())}"
            )
        if bash_events:
            sample = bash_events[0]
            inp = sample.get("input", {}) or {}
            cmd = inp.get("command", "")
            findings["bash_command_sample"] = str(cmd)[:400]
            findings["bash_input_keys"] = list(inp.keys())
            print(f"  bash sample: keys={list(inp.keys())}, cmd[:200]={str(cmd)[:200]}")

        # Token usage
        token_events = [e for e in all_events if e.get("type") == "span.model_request_end"]
        if token_events:
            usage = token_events[0].get("model_usage", {}) or {}
            total_input = sum((e.get("model_usage") or {}).get("input_tokens", 0) for e in token_events)
            total_output = sum((e.get("model_usage") or {}).get("output_tokens", 0) for e in token_events)
            total_cache_create = sum((e.get("model_usage") or {}).get("cache_creation_input_tokens", 0) for e in token_events)
            total_cache_read = sum((e.get("model_usage") or {}).get("cache_read_input_tokens", 0) for e in token_events)
            findings["token_usage_sample"] = usage
            findings["token_totals"] = {
                "input": total_input,
                "output": total_output,
                "cache_creation_input": total_cache_create,
                "cache_read_input": total_cache_read,
                "n_model_requests": len(token_events),
            }
            print(f"  token_usage sample: {usage}")
            print(f"  token totals: in={total_input} out={total_output} cache_create={total_cache_create} cache_read={total_cache_read} requests={len(token_events)}")

    except Exception as exc:  # noqa: BLE001
        findings["error"] = f"{exc.__class__.__name__}: {exc}"
        print(f"  ERROR: {exc}")
        traceback.print_exc()
    finally:
        # Cleanup — best-effort
        if session_id:
            try:
                await client.beta.sessions.archive(session_id, betas=[MANAGED_AGENTS_BETA])
                print(f"  session archived: {session_id}")
            except Exception as exc:
                print(f"  session archive failed: {exc}")
        if agent_id:
            try:
                await client.beta.agents.archive(agent_id, betas=[MANAGED_AGENTS_BETA])
                print(f"  agent archived: {agent_id}")
            except Exception as exc:
                print(f"  agent archive failed: {exc}")
        if env_id:
            try:
                await client.beta.environments.archive(env_id, betas=[MANAGED_AGENTS_BETA])
                print(f"  environment archived: {env_id}")
            except Exception as exc:
                print(f"  environment archive failed: {exc}")

    return findings


# ---------------------------------------------------------------------------
# Probe 4 — advisor_20260301 availability
# ---------------------------------------------------------------------------


async def probe_advisor(client: AsyncAnthropic) -> dict:
    """Try to create an agent with the advisor_20260301 tool. Capture failures."""
    print("\n=== Probe 4: advisor_20260301 tool ===")
    findings: dict = {"agent_id": None, "error": None, "available": False}
    agent_id = None
    try:
        agent_resp = await client.beta.agents.create(
            name="sf-smoke-advisor-agent",
            model="claude-haiku-4-5-20251001",
            system="You are a smoke-test agent.",
            tools=[
                {"type": "agent_toolset_20260401"},
                {
                    "type": "advisor_20260301",
                    "name": "advisor",
                    "model": "claude-opus-4-6",
                    "max_uses": 3,
                },
            ],
            betas=[MANAGED_AGENTS_BETA, ADVISOR_BETA],
        )
        agent_id = getattr(agent_resp, "id", None)
        findings["agent_id"] = agent_id
        findings["available"] = True
        print(f"  advisor agent created: {agent_id}")
    except Exception as exc:  # noqa: BLE001
        findings["error"] = f"{exc.__class__.__name__}: {str(exc)[:400]}"
        print(f"  advisor unavailable: {exc}")
    finally:
        if agent_id:
            try:
                await client.beta.agents.archive(agent_id, betas=[MANAGED_AGENTS_BETA])
                print(f"  advisor agent archived: {agent_id}")
            except Exception as exc:
                print(f"  advisor agent archive failed: {exc}")
    return findings


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


async def cleanup_skills(client: AsyncAnthropic, ids: list[str]) -> None:
    print(f"\n=== Cleanup: deleting {len(ids)} skills ===")
    failures: list[tuple[str, str]] = []
    for sid in ids:
        err = await _delete_skill_safely(client, sid)
        if err:
            failures.append((sid, err))
            print(f"  FAIL {sid}: {err}")
        else:
            print(f"  OK   {sid}")
    if failures:
        print(f"  {len(failures)} skills failed to delete — will leak")
    else:
        print("  all skills deleted cleanly")

    # Sweep for any leftovers from previous failed runs
    print("\n=== Sweep: residual smoke skills in org ===")
    leftover = await _list_smoke_skills(client)
    if leftover:
        print(f"  {len(leftover)} residual smoke skills found:")
        for s in leftover:
            print(f"    - {s.get('id')} {s.get('display_title')}")
    else:
        print("  none")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    import os
    skip_uploads = os.getenv("SF_SMOKE_SKIP_UPLOADS") == "1"
    skip_session = os.getenv("SF_SMOKE_SKIP_SESSION") == "1"
    skip_advisor = os.getenv("SF_SMOKE_SKIP_ADVISOR") == "1"

    print("=" * 60)
    print("SkillForge v1.2 Step 0 smoke test")
    print("=" * 60)
    print(f"  managed-agents beta: {MANAGED_AGENTS_BETA}")
    print(f"  skills beta:         {SKILLS_BETA}")
    print(f"  advisor beta:        {ADVISOR_BETA}")
    if skip_uploads or skip_session or skip_advisor:
        print(
            f"  skipping: "
            f"{'uploads ' if skip_uploads else ''}"
            f"{'session ' if skip_session else ''}"
            f"{'advisor ' if skip_advisor else ''}".strip()
        )

    client = AsyncAnthropic(timeout=300.0)

    uploaded: list[str] = []
    findings: dict = {}

    try:
        if not skip_uploads:
            serial = await probe_serial_uploads(client, n=20)
            uploaded.extend(serial)
            parallel = await probe_parallel_uploads(client, n=10)
            uploaded.extend(parallel)

        if not skip_session:
            findings["session_probe"] = await probe_session_event_shape(client)

        if not skip_advisor:
            findings["advisor_probe"] = await probe_advisor(client)

    finally:
        if uploaded:
            await cleanup_skills(client, uploaded)
        await client.close()

    print("\n" + "=" * 60)
    print("Findings (JSON-ish summary):")
    print("=" * 60)
    print(json.dumps(findings, default=str, indent=2)[:6000])


if __name__ == "__main__":
    asyncio.run(main())
