"""Unit tests for skillforge.agents.managed_agents.

Covers the pure parsing helpers (which need no SDK mocking) plus the
lifecycle wrappers via mocked AsyncAnthropic clients.

PLAN-V1.2 §"Step 0 empirical findings" pinned the event shapes that
this module's helpers parse — these tests are the executable contract
for those shapes. If Anthropic ships a new beta header that changes
the shapes, these tests fail loudly.

Coverage:
- ``extract_written_files``: write tool, multiple writes (last wins),
  bash heredoc, bash echo redirect, mixed sources, ignored event types.
- ``compute_token_usage``: sums input/output/cache fields across multiple
  span.model_request_end events.
- ``compute_session_runtime_hours``: status_running → status_idle delta.
- ``session_was_skill_loaded``: heuristic with/without skill_id.
- ``archive_skill``: 3-step dance via mocked SDK; refuses Anthropic
  built-ins; ``archive_skill_safe`` swallows errors.
- ``upload_skill``: file path format ``<name>/SKILL.md``.
- ``send_user_message``: builds the user.message event shape.
- ``iter_session_events``: paginates + dedupes + stops on idle event.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from skillforge.agents import managed_agents

# ---------------------------------------------------------------------------
# Helpers — build fake event dicts that match the SDK's BetaManagedAgentsSessionEvent shape
# ---------------------------------------------------------------------------


def _ev(etype: str, **fields) -> dict:
    return {"id": fields.pop("id", f"ev_{etype}_{hash(str(fields)) & 0xFFFFFF}"), "type": etype, **fields}


def _tool_use_write(file_path: str, content: str, **extra) -> dict:
    return _ev("agent.tool_use", name="write", input={"file_path": file_path, "content": content}, **extra)


def _tool_use_bash(command: str, **extra) -> dict:
    return _ev("agent.tool_use", name="bash", input={"command": command}, **extra)


def _model_request_end(*, input_tokens: int, output_tokens: int, cache_creation_input_tokens: int = 0, cache_read_input_tokens: int = 0) -> dict:
    return _ev(
        "span.model_request_end",
        model_usage={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation_input_tokens": cache_creation_input_tokens,
            "cache_read_input_tokens": cache_read_input_tokens,
        },
    )


# ---------------------------------------------------------------------------
# extract_written_files
# ---------------------------------------------------------------------------


# NOTE: extract_written_files NORMALIZES paths to relative form
# (strips leading slashes) — see test_normalize_output_path. Tests below
# use absolute path inputs and assert the relative-path outputs.


def test_extract_written_files_write_tool_happy_path():
    events = [
        _tool_use_write("/output/solution.py", "print('hi')\n"),
    ]
    out = managed_agents.extract_written_files(events)
    assert out == {"output/solution.py": "print('hi')\n"}


def test_extract_written_files_last_write_wins():
    events = [
        _tool_use_write("/output/solution.py", "first version"),
        _tool_use_write("/output/solution.py", "second version"),
    ]
    out = managed_agents.extract_written_files(events)
    assert out == {"output/solution.py": "second version"}


def test_extract_written_files_multiple_distinct_files():
    events = [
        _tool_use_write("/output/a.py", "a"),
        _tool_use_write("/output/b.py", "b"),
        _tool_use_write("/output/c.txt", "c"),
    ]
    out = managed_agents.extract_written_files(events)
    assert out == {
        "output/a.py": "a",
        "output/b.py": "b",
        "output/c.txt": "c",
    }


def test_extract_written_files_bash_heredoc_cat():
    cmd = "cat > /output/solution.py <<EOF\nprint('hello')\nprint('world')\nEOF"
    out = managed_agents.extract_written_files([_tool_use_bash(cmd)])
    assert "output/solution.py" in out
    assert "print('hello')" in out["output/solution.py"]
    assert "print('world')" in out["output/solution.py"]


def test_extract_written_files_bash_heredoc_quoted_delimiter():
    cmd = "cat > /tmp/x.txt <<'END'\nliteral $var no expansion\nEND"
    out = managed_agents.extract_written_files([_tool_use_bash(cmd)])
    assert "tmp/x.txt" in out
    assert "literal $var no expansion" in out["tmp/x.txt"]


def test_extract_written_files_bash_tee_heredoc():
    cmd = "tee /tmp/y.py <<EOF\nfoo = 1\nEOF"
    out = managed_agents.extract_written_files([_tool_use_bash(cmd)])
    assert "tmp/y.py" in out
    assert "foo = 1" in out["tmp/y.py"]


def test_extract_written_files_bash_echo_redirect():
    cmd = 'echo "hello" > /tmp/greet.txt'
    out = managed_agents.extract_written_files([_tool_use_bash(cmd)])
    assert out.get("tmp/greet.txt") == "hello"


def test_extract_written_files_mixed_write_and_bash():
    events = [
        _tool_use_write("/output/solution.py", "from write tool"),
        _tool_use_bash("cat > /output/notes.md <<EOF\nfrom bash heredoc\nEOF"),
    ]
    out = managed_agents.extract_written_files(events)
    assert out["output/solution.py"] == "from write tool"
    assert "from bash heredoc" in out["output/notes.md"]


def test_extract_written_files_ignores_non_tool_use_events():
    events = [
        _ev("session.status_running", processed_at="2026-04-10T01:00:00Z"),
        _ev("agent.thinking", content="reasoning..."),
        _ev("agent.message", content=[{"type": "text", "text": "hi"}]),
        _tool_use_write("/output/solution.py", "real write"),
        _ev("session.status_idle", processed_at="2026-04-10T01:01:00Z"),
    ]
    out = managed_agents.extract_written_files(events)
    assert out == {"output/solution.py": "real write"}


def test_extract_written_files_ignores_unknown_tool_names():
    events = [
        _ev("agent.tool_use", name="read", input={"file_path": "/tmp/x"}),
        _ev("agent.tool_use", name="grep", input={"pattern": "foo"}),
    ]
    out = managed_agents.extract_written_files(events)
    assert out == {}


def test_extract_written_files_handles_missing_input_field():
    events = [
        _ev("agent.tool_use", name="write", input=None),
        _ev("agent.tool_use", name="write"),
        _ev("agent.tool_use", name="write", input={}),
    ]
    out = managed_agents.extract_written_files(events)
    assert out == {}


# ---------------------------------------------------------------------------
# compute_token_usage
# ---------------------------------------------------------------------------


def test_compute_token_usage_sums_across_multiple_events():
    events = [
        _model_request_end(input_tokens=100, output_tokens=50),
        _model_request_end(input_tokens=200, output_tokens=80, cache_creation_input_tokens=500),
        _model_request_end(input_tokens=10, output_tokens=20, cache_read_input_tokens=300),
    ]
    totals = managed_agents.compute_token_usage(events)
    assert totals == {
        "input": 310,
        "output": 150,
        "cache_creation_input": 500,
        "cache_read_input": 300,
        "n_requests": 3,
    }


def test_compute_token_usage_zero_when_no_events():
    assert managed_agents.compute_token_usage([]) == {
        "input": 0,
        "output": 0,
        "cache_creation_input": 0,
        "cache_read_input": 0,
        "n_requests": 0,
    }


def test_compute_token_usage_ignores_non_model_request_end_events():
    events = [
        _ev("session.status_running"),
        _model_request_end(input_tokens=42, output_tokens=10),
        _ev("agent.thinking"),
    ]
    totals = managed_agents.compute_token_usage(events)
    assert totals["input"] == 42
    assert totals["output"] == 10
    assert totals["n_requests"] == 1


def test_compute_token_usage_handles_missing_model_usage():
    events = [
        _ev("span.model_request_end"),  # no model_usage at all
        _ev("span.model_request_end", model_usage=None),
        _model_request_end(input_tokens=5, output_tokens=3),
    ]
    totals = managed_agents.compute_token_usage(events)
    assert totals["input"] == 5
    assert totals["output"] == 3


# ---------------------------------------------------------------------------
# compute_session_runtime_hours
# ---------------------------------------------------------------------------


def test_compute_session_runtime_hours_basic():
    start = datetime(2026, 4, 10, 1, 0, 0, tzinfo=UTC)
    end = datetime(2026, 4, 10, 1, 0, 36, tzinfo=UTC)  # 36 seconds
    events = [
        _ev("session.status_running", processed_at=start.isoformat()),
        _ev("session.status_idle", processed_at=end.isoformat()),
    ]
    hours = managed_agents.compute_session_runtime_hours(events)
    assert hours == pytest.approx(36 / 3600, rel=1e-6)


def test_compute_session_runtime_hours_zero_when_missing_running():
    events = [
        _ev("session.status_idle", processed_at="2026-04-10T01:00:00+00:00"),
    ]
    assert managed_agents.compute_session_runtime_hours(events) == 0.0


def test_compute_session_runtime_hours_zero_when_missing_idle():
    events = [
        _ev("session.status_running", processed_at="2026-04-10T01:00:00+00:00"),
    ]
    assert managed_agents.compute_session_runtime_hours(events) == 0.0


def test_compute_session_runtime_hours_zero_for_negative_delta():
    events = [
        _ev("session.status_running", processed_at="2026-04-10T01:01:00+00:00"),
        _ev("session.status_idle", processed_at="2026-04-10T01:00:00+00:00"),
    ]
    assert managed_agents.compute_session_runtime_hours(events) == 0.0


def test_compute_session_runtime_hours_uses_first_running_only():
    """If multiple status_running events arrive, use the first one."""
    events = [
        _ev("session.status_running", processed_at="2026-04-10T01:00:00+00:00"),
        _ev("session.status_running", processed_at="2026-04-10T01:00:30+00:00"),
        _ev("session.status_idle", processed_at="2026-04-10T01:01:00+00:00"),
    ]
    hours = managed_agents.compute_session_runtime_hours(events)
    assert hours == pytest.approx(60 / 3600, rel=1e-6)


# ---------------------------------------------------------------------------
# session_was_skill_loaded
# ---------------------------------------------------------------------------


def test_session_was_skill_loaded_false_when_no_skill_id():
    events = [_tool_use_write("/x.py", "x")]
    assert managed_agents.session_was_skill_loaded(events, None) is False


def test_session_was_skill_loaded_true_when_tool_use_after_running():
    events = [
        _ev("session.status_running"),
        _tool_use_write("/x.py", "x"),
    ]
    assert managed_agents.session_was_skill_loaded(events, "skill_123") is True


def test_session_was_skill_loaded_false_when_tool_use_before_running():
    events = [
        _tool_use_write("/x.py", "x"),
        _ev("session.status_running"),
    ]
    assert managed_agents.session_was_skill_loaded(events, "skill_123") is False


def test_session_was_skill_loaded_false_when_no_tool_use():
    events = [
        _ev("session.status_running"),
        _ev("agent.message", content=[{"type": "text", "text": "I refuse"}]),
        _ev("session.status_idle"),
    ]
    assert managed_agents.session_was_skill_loaded(events, "skill_123") is False


# ---------------------------------------------------------------------------
# upload_skill — verifies the <name>/SKILL.md path format
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_competitor_agent_skill_link_uses_custom_type():
    """Skill references must use type='custom', not 'skill'.

    Empirical finding from the Phase 1 end-to-end smoke: passing
    type='skill' returns ``400 skills[0].type: "skill" is not a valid
    value; expected one of "anthropic", "custom"``.
    """
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.id = "agent_test_id"
    mock_client.beta.agents.create = AsyncMock(return_value=mock_response)

    await managed_agents.create_competitor_agent(
        mock_client,
        name="test-agent",
        model="claude-sonnet-4-6",
        system_prompt="prompt",
        skill_id="skill_xyz",
    )

    call_kwargs = mock_client.beta.agents.create.call_args.kwargs
    skills = call_kwargs.get("skills")
    # The CustomSkillParams shape: {"skill_id": str, "type": "custom"}
    # NOT {"id": str} — that returns 400 "Extra inputs not permitted".
    assert skills == [{"skill_id": "skill_xyz", "type": "custom"}]


@pytest.mark.asyncio
async def test_create_competitor_agent_no_skill_when_skill_id_none():
    """When no skill_id is provided, the agent.create call omits the skills field."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.id = "agent_no_skill"
    mock_client.beta.agents.create = AsyncMock(return_value=mock_response)

    await managed_agents.create_competitor_agent(
        mock_client,
        name="test-agent",
        model="claude-sonnet-4-6",
        system_prompt="prompt",
        skill_id=None,
    )

    call_kwargs = mock_client.beta.agents.create.call_args.kwargs
    assert "skills" not in call_kwargs


@pytest.mark.asyncio
async def test_upload_skill_folder_name_matches_frontmatter_name():
    """The folder name MUST match the SKILL.md `name:` field per the live API.

    Empirical finding from the Phase 1 end-to-end smoke: the API rejects
    uploads where the folder name and frontmatter name diverge:
    ``400 The folder name 'sf-...' must match the skill name '...' in SKILL.md``.

    The wrapper extracts the real name from the SKILL.md and uses THAT
    as the folder name, ignoring the ``name`` argument (which is still
    used as ``display_title``).
    """
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.id = "skill_test_123"
    mock_client.beta.skills.create = AsyncMock(return_value=mock_response)

    skill_md = "---\nname: real-skill-name\ndescription: x\n---\n# X"
    result = await managed_agents.upload_skill(
        mock_client, name="some-display-title", skill_md=skill_md
    )

    assert result == "skill_test_123"
    call_kwargs = mock_client.beta.skills.create.call_args.kwargs
    files = call_kwargs["files"]
    filename, content, ctype = files[0]
    assert filename == "real-skill-name/SKILL.md"
    assert call_kwargs["display_title"] == "some-display-title"
    assert ctype == "text/markdown"
    assert call_kwargs["betas"] == [managed_agents.SKILLS_BETA]


@pytest.mark.asyncio
async def test_upload_skill_falls_back_to_arg_name_when_frontmatter_missing():
    """If SKILL.md has no parseable name, use the ``name`` arg as the folder."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.id = "skill_fallback_999"
    mock_client.beta.skills.create = AsyncMock(return_value=mock_response)

    skill_md = "no frontmatter at all, just prose"
    await managed_agents.upload_skill(
        mock_client, name="fallback-name", skill_md=skill_md
    )
    files = mock_client.beta.skills.create.call_args.kwargs["files"]
    assert files[0][0] == "fallback-name/SKILL.md"


def test_extract_skill_name_from_md_happy_path():
    md = "---\nname: my-skill\ndescription: x\n---\n# Body"
    assert managed_agents._extract_skill_name_from_md(md) == "my-skill"


def test_extract_skill_name_from_md_returns_none_when_missing():
    assert managed_agents._extract_skill_name_from_md("no frontmatter") is None
    assert managed_agents._extract_skill_name_from_md("---\ndescription: x\n---\n# x") is None
    assert managed_agents._extract_skill_name_from_md("---\nname: x") is None  # no closing ---


def test_normalize_output_path_strips_leading_slash():
    """Cloud sandbox uses absolute paths; L1 needs them relative.

    Empirical finding from the Phase 1 end-to-end smoke: writing to
    ``/output/solution.py`` made L1 try to mkdir /output on the local
    FS and crash with a read-only filesystem error.
    """
    assert managed_agents._normalize_output_path("/output/solution.py") == "output/solution.py"
    assert managed_agents._normalize_output_path("///deeply/nested") == "deeply/nested"
    assert managed_agents._normalize_output_path("output/solution.py") == "output/solution.py"
    assert managed_agents._normalize_output_path("./output/x.py") == "output/x.py"
    assert managed_agents._normalize_output_path("  ./out/y  ") == "out/y"


def test_extract_written_files_normalizes_absolute_write_paths():
    """The write tool's absolute file_path becomes a relative key in output_files."""
    events = [_tool_use_write("/output/solution.py", "code")]
    out = managed_agents.extract_written_files(events)
    assert "/output/solution.py" not in out
    assert "output/solution.py" in out
    assert out["output/solution.py"] == "code"


def test_extract_written_files_normalizes_absolute_bash_heredoc_paths():
    """Bash heredoc writing to an absolute path also gets normalized."""
    cmd = "cat > /output/solution.py <<EOF\ncode\nEOF"
    out = managed_agents.extract_written_files([_tool_use_bash(cmd)])
    assert "output/solution.py" in out
    assert "/output/solution.py" not in out


# ---------------------------------------------------------------------------
# archive_skill — 3-step delete dance with built-in guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_archive_skill_runs_three_step_dance():
    """Verifies versions.list → versions.delete (per version) → skills.delete."""
    mock_client = MagicMock()
    # retrieve returns a custom skill (source != anthropic)
    mock_retrieved = MagicMock()
    mock_retrieved.source = "custom"
    mock_client.beta.skills.retrieve = AsyncMock(return_value=mock_retrieved)

    # Two versions to delete
    v1 = MagicMock()
    v1.version = "v1"
    v1.model_dump = MagicMock(return_value={"version": "v1"})
    v2 = MagicMock()
    v2.version = "v2"
    v2.model_dump = MagicMock(return_value={"version": "v2"})

    async def fake_aiter():
        yield v1
        yield v2

    mock_paginator = MagicMock()
    mock_paginator.__aiter__ = lambda self: fake_aiter()
    mock_client.beta.skills.versions.list = AsyncMock(return_value=mock_paginator)
    mock_client.beta.skills.versions.delete = AsyncMock()
    mock_client.beta.skills.delete = AsyncMock()

    await managed_agents.archive_skill(mock_client, "skill_test_xyz")

    # 3-step dance: list once, delete each version, delete the skill
    mock_client.beta.skills.versions.list.assert_called_once()
    assert mock_client.beta.skills.versions.delete.call_count == 2
    mock_client.beta.skills.delete.assert_called_once_with(
        "skill_test_xyz", betas=[managed_agents.SKILLS_BETA]
    )


@pytest.mark.asyncio
async def test_archive_skill_refuses_anthropic_built_in():
    """source='anthropic' MUST raise PermissionError before any delete attempt."""
    mock_client = MagicMock()
    mock_retrieved = MagicMock()
    mock_retrieved.source = "anthropic"
    mock_client.beta.skills.retrieve = AsyncMock(return_value=mock_retrieved)
    mock_client.beta.skills.delete = AsyncMock()
    mock_client.beta.skills.versions.list = AsyncMock()
    mock_client.beta.skills.versions.delete = AsyncMock()

    with pytest.raises(PermissionError, match="Anthropic built-in"):
        await managed_agents.archive_skill(mock_client, "xlsx")

    # No delete attempts whatsoever
    mock_client.beta.skills.versions.list.assert_not_called()
    mock_client.beta.skills.versions.delete.assert_not_called()
    mock_client.beta.skills.delete.assert_not_called()


@pytest.mark.asyncio
async def test_archive_skill_safe_swallows_errors():
    """archive_skill_safe returns (False, error) instead of raising."""
    mock_client = MagicMock()
    mock_client.beta.skills.retrieve = AsyncMock(side_effect=RuntimeError("boom"))
    # The retrieve failure is caught silently; the dance continues and trips on list
    mock_client.beta.skills.versions.list = AsyncMock(side_effect=RuntimeError("list down"))

    success, err = await managed_agents.archive_skill_safe(mock_client, "skill_x")
    assert success is False
    assert err is not None
    assert "RuntimeError" in err


@pytest.mark.asyncio
async def test_archive_skill_safe_returns_true_on_success():
    """Happy path through archive_skill_safe returns (True, None)."""
    mock_client = MagicMock()
    mock_retrieved = MagicMock()
    mock_retrieved.source = "custom"
    mock_client.beta.skills.retrieve = AsyncMock(return_value=mock_retrieved)

    async def empty_aiter():
        if False:
            yield  # pragma: no cover

    mock_paginator = MagicMock()
    mock_paginator.__aiter__ = lambda self: empty_aiter()
    mock_client.beta.skills.versions.list = AsyncMock(return_value=mock_paginator)
    mock_client.beta.skills.delete = AsyncMock()

    success, err = await managed_agents.archive_skill_safe(mock_client, "skill_y")
    assert success is True
    assert err is None


# ---------------------------------------------------------------------------
# send_user_message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_user_message_builds_correct_event_shape():
    mock_client = MagicMock()
    mock_client.beta.sessions.events.send = AsyncMock()

    await managed_agents.send_user_message(
        mock_client, "sesn_123", "hello world"
    )

    mock_client.beta.sessions.events.send.assert_called_once()
    call = mock_client.beta.sessions.events.send.call_args
    assert call.args == ("sesn_123",)
    events = call.kwargs["events"]
    assert events == [
        {
            "type": "user.message",
            "content": [{"type": "text", "text": "hello world"}],
        }
    ]
    assert call.kwargs["betas"] == [managed_agents.MANAGED_AGENTS_BETA]


# ---------------------------------------------------------------------------
# iter_session_events — polling, dedupe, idle stop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_iter_session_events_dedupes_by_id_and_stops_on_idle():
    """The polling iterator should yield each event exactly once and stop on idle."""

    # Page 1: 2 events. Page 2: same 2 events + idle event.
    e1 = MagicMock()
    e1.id = "ev1"
    e1.model_dump = MagicMock(return_value={"id": "ev1", "type": "user.message"})

    e2 = MagicMock()
    e2.id = "ev2"
    e2.model_dump = MagicMock(return_value={"id": "ev2", "type": "agent.thinking"})

    e3 = MagicMock()
    e3.id = "ev3"
    e3.model_dump = MagicMock(return_value={"id": "ev3", "type": "session.status_idle"})

    poll_count = {"n": 0}

    async def first_page():
        for ev in (e1, e2):
            yield ev

    async def second_page():
        for ev in (e1, e2, e3):
            yield ev

    def make_paginator(events):
        p = MagicMock()
        p.__aiter__ = lambda self: events
        return p

    mock_client = MagicMock()

    async def list_side_effect(*args, **kwargs):
        poll_count["n"] += 1
        if poll_count["n"] == 1:
            return make_paginator(first_page())
        return make_paginator(second_page())

    mock_client.beta.sessions.events.list = AsyncMock(side_effect=list_side_effect)

    yielded: list[dict] = []
    async for ev in managed_agents.iter_session_events(
        mock_client, "sesn_x", deadline_seconds=10.0, poll_interval=0.0
    ):
        yielded.append(ev)

    assert [e["id"] for e in yielded] == ["ev1", "ev2", "ev3"]
    assert yielded[-1]["type"] == "session.status_idle"


@pytest.mark.asyncio
async def test_iter_session_events_respects_deadline():
    """If idle never arrives, the iterator stops at deadline_seconds."""
    e_loop = MagicMock()
    e_loop.id = "ev_loop"
    e_loop.model_dump = MagicMock(return_value={"id": "ev_loop", "type": "agent.thinking"})

    async def page():
        yield e_loop

    def make_paginator():
        p = MagicMock()
        p.__aiter__ = lambda self: page()
        return p

    mock_client = MagicMock()
    mock_client.beta.sessions.events.list = AsyncMock(side_effect=lambda *a, **kw: make_paginator())

    yielded = []
    async for ev in managed_agents.iter_session_events(
        mock_client, "sesn_loop", deadline_seconds=0.05, poll_interval=0.0
    ):
        yielded.append(ev)
        if len(yielded) > 50:  # safety against infinite loop in the test
            break

    # Should have stopped on its own well before the safety limit
    assert len(yielded) <= 50
