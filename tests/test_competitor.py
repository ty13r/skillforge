"""Tests for skillforge.agents.competitor (Step 6c)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import skillforge.engine.sandbox as sandbox_mod

# After PLAN-V1.2 Phase 1 the SDK competitor implementation moved to
# competitor_sdk.py. The top-level competitor.py is now a dispatcher that
# routes between sdk/managed backends. Import from competitor_sdk directly
# so these tests stay focused on the SDK path regardless of COMPETITOR_BACKEND.
from skillforge.agents.competitor_sdk import _message_to_dict, run_competitor
from skillforge.config import MAX_TURNS
from skillforge.engine.sandbox import create_sandbox
from skillforge.models import Challenge, SkillGenome

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_MINIMAL_SKILL_MD = """\
---
name: my-skill
description: >-
  Does useful things. Use when you need useful things done, or when the user
  mentions "useful", even if they don't explicitly ask for my-skill.
  NOT for unrelated things.
allowed-tools: Read Write Bash
---

# My Skill

## Quick Start
Run the skill to get useful output.

## Workflow

### Step 1: Gather
Read context.

### Step 2: Execute
Do the thing.

## Examples

**Example 1: Typical use case**
Input: "Do useful thing"
Output: Useful result

**Example 2: Edge case**
Input: "Do useful thing differently"
Output: Another useful result

## Gotchas
- Watch out for edge cases.

## Out of Scope
This skill does NOT:
- Handle unrelated things.
"""

_MINIMAL_CHALLENGE = Challenge(
    id="ch-test-001",
    prompt="Write a hello world function.",
    difficulty="easy",
    setup_files={"starter.py": "# starter"},
)


def _minimal_skill(**kwargs) -> SkillGenome:
    defaults: dict = {
        "id": "sk-test-001",
        "generation": 0,
        "skill_md_content": _MINIMAL_SKILL_MD,
    }
    defaults.update(kwargs)
    return SkillGenome(**defaults)


class FakeMessage:
    """Minimal stand-in for Agent SDK message objects."""

    def __init__(self, text: str):
        self.text = text

        class _Block:
            def __init__(self, t: str) -> None:
                self.text = t
                self.type = "text"

        self.content = [_Block(text)]


async def _fake_query_from(messages: list[str]):
    """Async generator that yields FakeMessage objects for each text."""
    for text in messages:
        yield FakeMessage(text)


@pytest.fixture()
def patched_sandbox_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Monkeypatch SANDBOX_ROOT so tests never touch /tmp."""
    root = tmp_path / "sandbox"
    root.mkdir()
    monkeypatch.setattr(sandbox_mod, "SANDBOX_ROOT", root)
    return root


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_competitor_collects_trace_and_output(
    patched_sandbox_root: Path,
) -> None:
    """Happy path: 3 messages collected into trace, output file captured."""
    skill = _minimal_skill()
    sandbox_path = create_sandbox("run1", 0, 0, skill, _MINIMAL_CHALLENGE)

    # Place an output file for collect_written_files to find
    output_file = sandbox_path / "output" / "solution.py"
    output_file.write_text("print('hello world')")

    with patch("skillforge.agents.competitor_sdk.query") as mock_query:
        mock_query.return_value = _fake_query_from(
            ["Starting task.", "Working on it.", "Done!"]
        )
        result = await run_competitor(skill, _MINIMAL_CHALLENGE, sandbox_path)

    assert len(result.trace) == 3
    assert "solution.py" in result.output_files
    assert result.output_files["solution.py"] == "print('hello world')"
    assert result.skill_id == skill.id
    assert result.challenge_id == _MINIMAL_CHALLENGE.id


@pytest.mark.asyncio
async def test_run_competitor_passes_correct_options_to_sdk(
    patched_sandbox_root: Path,
) -> None:
    """query() is called with the right ClaudeAgentOptions fields."""
    skill = _minimal_skill()
    sandbox_path = create_sandbox("run1", 0, 0, skill, _MINIMAL_CHALLENGE)

    captured_options = {}

    def _capturing_query(prompt, options):
        captured_options["options"] = options
        return _fake_query_from([])

    with patch("skillforge.agents.competitor_sdk.query", side_effect=_capturing_query):
        await run_competitor(skill, _MINIMAL_CHALLENGE, sandbox_path)

    opts = captured_options["options"]
    assert opts.setting_sources == ["project"]
    assert opts.permission_mode == "dontAsk"
    assert opts.cwd == str(sandbox_path)
    assert opts.max_turns == MAX_TURNS
    assert "Skill" in opts.allowed_tools
    # System prompt must tell Claude to save output files or the L1 judge
    # has nothing to score against (the first live run failed because of this).
    assert opts.system_prompt is not None
    assert "output/" in opts.system_prompt
    assert "Write tool" in opts.system_prompt


@pytest.mark.asyncio
async def test_run_competitor_never_uses_bypass_permissions(
    patched_sandbox_root: Path,
) -> None:
    """permission_mode must not be bypassPermissions."""
    skill = _minimal_skill()
    sandbox_path = create_sandbox("run1", 0, 0, skill, _MINIMAL_CHALLENGE)

    captured_options = {}

    def _capturing_query(prompt, options):
        captured_options["options"] = options
        return _fake_query_from([])

    with patch("skillforge.agents.competitor_sdk.query", side_effect=_capturing_query):
        await run_competitor(skill, _MINIMAL_CHALLENGE, sandbox_path)

    opts = captured_options["options"]
    assert opts.permission_mode != "bypassPermissions"


@pytest.mark.asyncio
async def test_run_competitor_handles_timeout(
    patched_sandbox_root: Path,
) -> None:
    """TimeoutError is caught; result has judge_reasoning containing 'timeout'."""
    skill = _minimal_skill()
    sandbox_path = create_sandbox("run1", 0, 0, skill, _MINIMAL_CHALLENGE)

    async def _hanging_query(prompt, options):
        raise TimeoutError()
        yield  # make it an async generator (unreachable)

    with patch("skillforge.agents.competitor_sdk.query", side_effect=_hanging_query):
        result = await run_competitor(skill, _MINIMAL_CHALLENGE, sandbox_path)

    assert "timeout" in result.judge_reasoning.lower()
    assert result.trace == []
    assert result.skill_id == skill.id
    assert result.challenge_id == _MINIMAL_CHALLENGE.id


@pytest.mark.asyncio
async def test_run_competitor_handles_sdk_error(
    patched_sandbox_root: Path,
) -> None:
    """SDK RuntimeError is caught; result carries error info and does not re-raise."""
    skill = _minimal_skill()
    sandbox_path = create_sandbox("run1", 0, 0, skill, _MINIMAL_CHALLENGE)

    async def _failing_query(prompt, options):
        raise RuntimeError("boom")
        yield  # make it an async generator (unreachable)

    with patch("skillforge.agents.competitor_sdk.query", side_effect=_failing_query):
        result = await run_competitor(skill, _MINIMAL_CHALLENGE, sandbox_path)

    assert "boom" in result.judge_reasoning or "sdk error" in result.judge_reasoning.lower()
    assert result.skill_id == skill.id
    assert result.challenge_id == _MINIMAL_CHALLENGE.id


def test_message_to_dict_handles_text_and_tool_blocks() -> None:
    """_message_to_dict converts messages with text/tool blocks to JSON-safe dicts."""

    class _TextBlock:
        type = "text"
        text = "Hello from the assistant."

    class _ToolUseBlock:
        type = "tool_use"
        name = "Bash"
        input = {"command": "echo hello"}

    class _FakeMsg:
        def __init__(self):
            self.content = [_TextBlock(), _ToolUseBlock()]
            self.role = "assistant"

    result = _message_to_dict(_FakeMsg())

    # Must be JSON-serializable
    json_str = json.dumps(result)
    parsed = json.loads(json_str)

    assert parsed["role"] == "assistant"
    assert isinstance(parsed["content"], list)
    assert len(parsed["content"]) == 2

    text_block = parsed["content"][0]
    assert text_block["type"] == "text"
    assert text_block["text"] == "Hello from the assistant."

    tool_block = parsed["content"][1]
    assert tool_block["type"] == "tool_use"
    assert tool_block["name"] == "Bash"
    assert tool_block["input"] == {"command": "echo hello"}


def test_message_to_dict_handles_unknown_shape() -> None:
    """_message_to_dict does not raise on objects with no expected attrs."""

    class _Opaque:
        pass

    result = _message_to_dict(_Opaque())

    # Should return at minimum {"type": "_Opaque"} without raising
    assert isinstance(result, dict)
    assert "type" in result
    # Must still be JSON-serializable
    json.dumps(result)
