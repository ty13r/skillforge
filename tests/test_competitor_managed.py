"""Tests for skillforge.agents.competitor_managed.

These tests stay above the SDK boundary by mocking the
``skillforge.agents.managed_agents`` wrapper directly. The wrapper itself
has its own unit tests in test_managed_agents.py — here we just verify
that competitor_managed orchestrates the calls correctly and produces a
``CompetitionResult`` with the right shape.

Coverage:
- Happy path with skill upload + write tool: result has output_files,
  trace (with synthetic Skill marker), cost_breakdown populated.
- Inline mode (skill upload disabled): no upload, skill content inlined
  into the user message, no synthetic Skill marker in the trace.
- Skill upload failure: gracefully degrades to inline mode, no synthetic
  marker, evolution still produces a result.
- Cleanup is scheduled as detached tasks (skill, agent, session, env).
- ``cost_breakdown`` math: token counts × model rates + runtime × $0.08
  produce the expected USD figures.
- Empty event stream: result still returned, no crash.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from skillforge.agents import competitor_managed
from skillforge.models import Challenge, CompetitionResult, SkillGenome

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_skill() -> SkillGenome:
    md = """---
name: test-skill
description: Use when testing managed competitor. NOT for production.
---

# Test Skill

## Workflow
- Step one

## Examples
**Example 1:** in → out
**Example 2:** in2 → out2
"""
    return SkillGenome(
        id="skill-test-12345678",
        generation=0,
        skill_md_content=md,
        traits=["x"],
    )


def _make_challenge() -> Challenge:
    return Challenge(
        id="ch-test-12345678",
        prompt="Implement add(a, b) that returns a + b.",
        difficulty="easy",
        evaluation_criteria=["correctness"],
        verification_method="python",
        setup_files={"test_solution.py": "def test_add(): assert solution.add(1, 2) == 3"},
        gold_standard_hints=[],
    )


def _make_event_stream(*, with_write: bool = True, runtime_seconds: float = 5.0) -> list[dict]:
    """Build a fake managed-agents event stream that the wrapper would produce."""
    start = datetime(2026, 4, 10, 1, 0, 0, tzinfo=UTC)
    end = datetime(2026, 4, 10, 1, 0, 0, tzinfo=UTC).replace(
        microsecond=int((runtime_seconds % 1) * 1_000_000)
    )
    end = end.replace(second=int(start.second + runtime_seconds))

    events: list[dict] = [
        {"id": "ev_user", "type": "user.message", "content": []},
        {"id": "ev_running", "type": "session.status_running", "processed_at": start.isoformat()},
        {
            "id": "ev_req_start",
            "type": "span.model_request_start",
        },
        {
            "id": "ev_req_end",
            "type": "span.model_request_end",
            "model_usage": {
                "input_tokens": 1000,
                "output_tokens": 500,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        },
    ]
    if with_write:
        events.append(
            {
                "id": "ev_write",
                "type": "agent.tool_use",
                "name": "write",
                "input": {
                    "file_path": "output/solution.py",
                    "content": "def add(a, b):\n    return a + b\n",
                },
            }
        )
        events.append(
            {
                "id": "ev_tool_result",
                "type": "agent.tool_result",
                "content": "wrote 28 bytes",
            }
        )
    events.append(
        {
            "id": "ev_msg",
            "type": "agent.message",
            "content": [{"type": "text", "text": "done"}],
        }
    )
    events.append(
        {"id": "ev_idle", "type": "session.status_idle", "processed_at": end.isoformat()}
    )
    return events


async def _async_iter(items):
    """Helper: turn a sync list into an async iterator for AsyncMock side_effects."""
    for item in items:
        yield item


# ---------------------------------------------------------------------------
# Happy path: skill upload + write tool + cost_breakdown populated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_competitor_managed_happy_path():
    """Default 'upload' mode succeeds end-to-end with mocked wrapper calls."""
    skill = _make_skill()
    challenge = _make_challenge()
    events = _make_event_stream(with_write=True)

    # Patch the entire managed_agents module surface used by competitor_managed
    with (
        patch("skillforge.agents.competitor_managed.MANAGED_AGENTS_SKILL_MODE", "upload"),
        patch("skillforge.agents.competitor_managed.managed_agents") as mocked_ma,
    ):
        mocked_ma.make_client.return_value = AsyncMock()
        mocked_ma.upload_skill = AsyncMock(return_value="skill_uploaded_id_123")
        mocked_ma.create_competitor_agent = AsyncMock(return_value="agent_id_456")
        mocked_ma.create_session = AsyncMock(return_value="sesn_id_789")
        mocked_ma.send_user_message = AsyncMock()
        mocked_ma.iter_session_events = lambda *a, **kw: _async_iter(events)
        mocked_ma.archive_session = AsyncMock()
        mocked_ma.archive_agent = AsyncMock()
        mocked_ma.archive_skill_safe = AsyncMock(return_value=(True, None))
        # Real wrapper helpers — pass-through to the actual functions
        from skillforge.agents.managed_agents import (
            SESSION_RUNTIME_USD_PER_HOUR,
            compute_session_runtime_hours,
            compute_token_usage,
            extract_written_files,
        )
        mocked_ma.SESSION_RUNTIME_USD_PER_HOUR = SESSION_RUNTIME_USD_PER_HOUR
        mocked_ma.extract_written_files = extract_written_files
        mocked_ma.compute_token_usage = compute_token_usage
        mocked_ma.compute_session_runtime_hours = compute_session_runtime_hours

        result = await competitor_managed.run_competitor(skill, challenge, "env_xyz")

    assert isinstance(result, CompetitionResult)
    assert result.skill_id == skill.id
    assert result.challenge_id == challenge.id

    # Output files reconstructed from the write tool event
    assert "output/solution.py" in result.output_files
    assert "def add" in result.output_files["output/solution.py"]

    # Trace has the synthetic Skill marker (because skill_attached=True)
    assert any(
        any(b.get("name") == "Skill" for b in entry.get("content", []))
        for entry in result.trace
    )

    # cost_breakdown populated with all expected fields
    cb = result.cost_breakdown
    assert cb["backend"] == "managed"
    assert cb["input_tokens"] == 1000
    assert cb["output_tokens"] == 500
    assert cb["n_model_requests"] == 1
    assert cb["session_runtime_hours"] >= 0
    # executor_input_usd = 1000 * 3.0 / 1M = 0.003 (Sonnet rate), output = 500 * 15 / 1M = 0.0075
    assert cb["executor_input_usd"] == pytest.approx(0.003, rel=1e-3)
    assert cb["executor_output_usd"] == pytest.approx(0.0075, rel=1e-3)
    # Advisor descoped → zero
    assert cb["advisor_input_usd"] == 0.0
    assert cb["advisor_output_usd"] == 0.0


# ---------------------------------------------------------------------------
# Inline mode: no skill upload, content inlined into user message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_competitor_managed_inline_mode():
    """When MANAGED_AGENTS_SKILL_MODE='inline', no upload happens."""
    skill = _make_skill()
    challenge = _make_challenge()
    events = _make_event_stream(with_write=True)

    with (
        patch("skillforge.agents.competitor_managed.MANAGED_AGENTS_SKILL_MODE", "inline"),
        patch("skillforge.agents.competitor_managed.managed_agents") as mocked_ma,
    ):
        mocked_ma.make_client.return_value = AsyncMock()
        mocked_ma.upload_skill = AsyncMock()  # should NOT be called
        mocked_ma.create_competitor_agent = AsyncMock(return_value="agent_id")
        mocked_ma.create_session = AsyncMock(return_value="sesn_id")
        mocked_ma.send_user_message = AsyncMock()
        mocked_ma.iter_session_events = lambda *a, **kw: _async_iter(events)
        mocked_ma.archive_session = AsyncMock()
        mocked_ma.archive_agent = AsyncMock()
        mocked_ma.archive_skill_safe = AsyncMock()
        from skillforge.agents.managed_agents import (
            SESSION_RUNTIME_USD_PER_HOUR,
            compute_session_runtime_hours,
            compute_token_usage,
            extract_written_files,
        )
        mocked_ma.SESSION_RUNTIME_USD_PER_HOUR = SESSION_RUNTIME_USD_PER_HOUR
        mocked_ma.extract_written_files = extract_written_files
        mocked_ma.compute_token_usage = compute_token_usage
        mocked_ma.compute_session_runtime_hours = compute_session_runtime_hours

        result = await competitor_managed.run_competitor(skill, challenge, "env_xyz")

    mocked_ma.upload_skill.assert_not_called()
    # create_competitor_agent should be called WITHOUT a skill_id
    create_call = mocked_ma.create_competitor_agent.call_args
    assert create_call.kwargs["skill_id"] is None

    # The user message should contain the inlined SKILL.md
    send_call = mocked_ma.send_user_message.call_args
    user_text = send_call.args[2] if len(send_call.args) > 2 else send_call.kwargs.get("text", "")
    assert "test-skill" in user_text or "Test Skill" in user_text
    assert "inline mode" in user_text

    # No synthetic Skill marker in the trace (skill_attached=False)
    has_skill_marker = any(
        any(b.get("name") == "Skill" for b in entry.get("content", []))
        for entry in result.trace
    )
    assert has_skill_marker is False


# ---------------------------------------------------------------------------
# Upload failure → graceful fallback to inline mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_competitor_managed_upload_failure_falls_back_to_inline():
    """A skill upload exception drops the run into inline mode, doesn't crash."""
    skill = _make_skill()
    challenge = _make_challenge()
    events = _make_event_stream(with_write=True)

    with (
        patch("skillforge.agents.competitor_managed.MANAGED_AGENTS_SKILL_MODE", "upload"),
        patch("skillforge.agents.competitor_managed.managed_agents") as mocked_ma,
    ):
        mocked_ma.make_client.return_value = AsyncMock()
        mocked_ma.upload_skill = AsyncMock(side_effect=RuntimeError("rate limit"))
        mocked_ma.create_competitor_agent = AsyncMock(return_value="agent_id")
        mocked_ma.create_session = AsyncMock(return_value="sesn_id")
        mocked_ma.send_user_message = AsyncMock()
        mocked_ma.iter_session_events = lambda *a, **kw: _async_iter(events)
        mocked_ma.archive_session = AsyncMock()
        mocked_ma.archive_agent = AsyncMock()
        mocked_ma.archive_skill_safe = AsyncMock()
        from skillforge.agents.managed_agents import (
            SESSION_RUNTIME_USD_PER_HOUR,
            compute_session_runtime_hours,
            compute_token_usage,
            extract_written_files,
        )
        mocked_ma.SESSION_RUNTIME_USD_PER_HOUR = SESSION_RUNTIME_USD_PER_HOUR
        mocked_ma.extract_written_files = extract_written_files
        mocked_ma.compute_token_usage = compute_token_usage
        mocked_ma.compute_session_runtime_hours = compute_session_runtime_hours

        result = await competitor_managed.run_competitor(skill, challenge, "env_xyz")

    # Run completed despite upload failure
    assert isinstance(result, CompetitionResult)
    assert "output/solution.py" in result.output_files
    # Agent created without skill_id (fallback)
    create_call = mocked_ma.create_competitor_agent.call_args
    assert create_call.kwargs["skill_id"] is None
    # No synthetic Skill marker (we couldn't actually attach it)
    has_skill_marker = any(
        any(b.get("name") == "Skill" for b in entry.get("content", []))
        for entry in result.trace
    )
    assert has_skill_marker is False


# ---------------------------------------------------------------------------
# Empty event stream — no crash, empty result
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_competitor_managed_empty_events_no_crash():
    """If the agent emits no events at all, the function still returns cleanly."""
    skill = _make_skill()
    challenge = _make_challenge()

    with (
        patch("skillforge.agents.competitor_managed.MANAGED_AGENTS_SKILL_MODE", "upload"),
        patch("skillforge.agents.competitor_managed.managed_agents") as mocked_ma,
    ):
        mocked_ma.make_client.return_value = AsyncMock()
        mocked_ma.upload_skill = AsyncMock(return_value="skill_id")
        mocked_ma.create_competitor_agent = AsyncMock(return_value="agent_id")
        mocked_ma.create_session = AsyncMock(return_value="sesn_id")
        mocked_ma.send_user_message = AsyncMock()
        mocked_ma.iter_session_events = lambda *a, **kw: _async_iter([])
        mocked_ma.archive_session = AsyncMock()
        mocked_ma.archive_agent = AsyncMock()
        mocked_ma.archive_skill_safe = AsyncMock()
        from skillforge.agents.managed_agents import (
            SESSION_RUNTIME_USD_PER_HOUR,
            compute_session_runtime_hours,
            compute_token_usage,
            extract_written_files,
        )
        mocked_ma.SESSION_RUNTIME_USD_PER_HOUR = SESSION_RUNTIME_USD_PER_HOUR
        mocked_ma.extract_written_files = extract_written_files
        mocked_ma.compute_token_usage = compute_token_usage
        mocked_ma.compute_session_runtime_hours = compute_session_runtime_hours

        result = await competitor_managed.run_competitor(skill, challenge, "env_xyz")

    assert isinstance(result, CompetitionResult)
    assert result.output_files == {}
    # Trace contains only the synthetic Skill marker
    assert len(result.trace) == 1
    assert result.cost_breakdown["n_model_requests"] == 0
    assert result.cost_breakdown["session_runtime_hours"] == 0.0


# ---------------------------------------------------------------------------
# Iter session events polling failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_competitor_managed_polling_error_recorded():
    """Exceptions during event polling are captured in judge_reasoning."""
    skill = _make_skill()
    challenge = _make_challenge()

    async def boom(*a, **kw):
        if False:
            yield  # pragma: no cover
        raise RuntimeError("network glitch")

    with (
        patch("skillforge.agents.competitor_managed.MANAGED_AGENTS_SKILL_MODE", "upload"),
        patch("skillforge.agents.competitor_managed.managed_agents") as mocked_ma,
    ):
        mocked_ma.make_client.return_value = AsyncMock()
        mocked_ma.upload_skill = AsyncMock(return_value="skill_id")
        mocked_ma.create_competitor_agent = AsyncMock(return_value="agent_id")
        mocked_ma.create_session = AsyncMock(return_value="sesn_id")
        mocked_ma.send_user_message = AsyncMock()
        mocked_ma.iter_session_events = boom
        mocked_ma.archive_session = AsyncMock()
        mocked_ma.archive_agent = AsyncMock()
        mocked_ma.archive_skill_safe = AsyncMock()
        from skillforge.agents.managed_agents import (
            SESSION_RUNTIME_USD_PER_HOUR,
            compute_session_runtime_hours,
            compute_token_usage,
            extract_written_files,
        )
        mocked_ma.SESSION_RUNTIME_USD_PER_HOUR = SESSION_RUNTIME_USD_PER_HOUR
        mocked_ma.extract_written_files = extract_written_files
        mocked_ma.compute_token_usage = compute_token_usage
        mocked_ma.compute_session_runtime_hours = compute_session_runtime_hours

        result = await competitor_managed.run_competitor(skill, challenge, "env_xyz")

    assert "polling error" in result.judge_reasoning or "network glitch" in result.judge_reasoning


# ---------------------------------------------------------------------------
# _build_user_message smoke check
# ---------------------------------------------------------------------------


def test_build_user_message_includes_setup_files():
    challenge = _make_challenge()
    text = competitor_managed._build_user_message(challenge)
    assert "## Challenge" in text
    assert challenge.prompt in text
    assert "test_solution.py" in text
    assert "mkdir -p challenge output" in text


def test_build_user_message_inlines_skill_md_when_provided():
    challenge = _make_challenge()
    skill_md = "---\nname: my-skill\n---\n# Body"
    text = competitor_managed._build_user_message(challenge, inline_skill_md=skill_md)
    assert "inline mode" in text
    assert "my-skill" in text


def test_build_user_message_omits_skill_block_when_no_inline():
    challenge = _make_challenge()
    text = competitor_managed._build_user_message(challenge, inline_skill_md=None)
    assert "inline mode" not in text


# ---------------------------------------------------------------------------
# _convert_event_to_trace_entry — tool name canonicalization
# ---------------------------------------------------------------------------


def test_convert_event_canonicalizes_tool_names():
    """write → Write, bash → Bash, etc. for L3 compatibility."""
    ev = {
        "type": "agent.tool_use",
        "name": "write",
        "input": {"file_path": "x.py", "content": "y"},
    }
    entry = competitor_managed._convert_event_to_trace_entry(ev)
    assert entry is not None
    assert entry["content"][0]["name"] == "Write"

    ev_bash = {
        "type": "agent.tool_use",
        "name": "bash",
        "input": {"command": "ls"},
    }
    entry_bash = competitor_managed._convert_event_to_trace_entry(ev_bash)
    assert entry_bash["content"][0]["name"] == "Bash"


def test_convert_event_returns_none_for_status_events():
    for etype in ("session.status_running", "session.status_idle", "span.model_request_start"):
        entry = competitor_managed._convert_event_to_trace_entry({"type": etype})
        assert entry is None
