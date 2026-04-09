"""Tests for L3 trace-based behavioral analysis judging layer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skillforge.agents.judge.trace_analysis import (
    _classify_instruction_adherence,
    _detect_skill_loaded,
    _diagnose_ignored,
    _extract_behavioral_signature,
    _extract_instructions,
    _extract_scripts_executed,
    run_l3,
)
from skillforge.models import CompetitionResult, SkillGenome

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(**kwargs) -> CompetitionResult:
    defaults = dict(skill_id="s1", challenge_id="c1", trace=[])
    defaults.update(kwargs)
    return CompetitionResult(**defaults)


def _make_skill(body: str = "") -> SkillGenome:
    md = f"""---
name: test-skill
description: Use when testing.
---

{body}
"""
    return SkillGenome(id="s1", generation=0, skill_md_content=md)


def _tool_use_block(name: str, input_data: dict | None = None) -> dict:
    return {"type": "tool_use", "name": name, "input": input_data or {}}


def _mock_anthropic_response(text: str) -> MagicMock:
    block = MagicMock()
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


# ---------------------------------------------------------------------------
# Unit tests — deterministic helpers
# ---------------------------------------------------------------------------

def test_detect_skill_loaded_true():
    """Trace containing a tool_use block named 'Skill' should return True."""
    trace = [
        {"role": "assistant", "content": [
            _tool_use_block("Read"),
            _tool_use_block("Skill"),
        ]},
    ]
    assert _detect_skill_loaded(trace) is True


def test_detect_skill_loaded_false():
    """Trace with only Read/Write tool calls should return False."""
    trace = [
        {"role": "assistant", "content": [
            _tool_use_block("Read"),
            _tool_use_block("Write"),
        ]},
    ]
    assert _detect_skill_loaded(trace) is False


def test_extract_behavioral_signature_preserves_order():
    """Tool call names should appear in the order they occur in the trace."""
    trace = [
        {"role": "assistant", "content": [_tool_use_block("Read")]},
        {"role": "assistant", "content": [_tool_use_block("Write")]},
        {"role": "assistant", "content": [_tool_use_block("Bash")]},
    ]
    sig = _extract_behavioral_signature(trace)
    assert sig == ["Read", "Write", "Bash"]


def test_extract_scripts_executed_finds_scripts_paths():
    """Bash tool calls referencing scripts/ should be captured."""
    trace = [
        {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": "bash scripts/validate.sh"}},
        ]},
    ]
    scripts = _extract_scripts_executed(trace)
    assert "scripts/validate.sh" in scripts


def test_extract_instructions_from_skill_md():
    """Numbered step headings and bullet points should be extracted as instructions."""
    body = """## Workflow

### Step 1: Run the validation script
### Step 2: Check the output file

- Use the cache helper for fast lookups
- Write results to output directory
"""
    skill = _make_skill(body)
    instructions = _extract_instructions(skill.skill_md_content)
    assert any("validation" in i.lower() or "Run the validation" in i for i in instructions)
    assert any("output" in i.lower() for i in instructions)
    assert len(instructions) >= 2


def test_extract_instructions_empty_on_no_frontmatter():
    """Content without '---' frontmatter delimiters should yield an empty list."""
    skill = SkillGenome(id="s2", generation=0, skill_md_content="No frontmatter here at all.")
    assert _extract_instructions(skill.skill_md_content) == []


def test_classify_instruction_adherence_followed():
    """Instruction whose keywords appear in the trace should end up in 'followed'."""
    instructions = ["Run the validation script"]
    trace = [
        {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": "bash scripts/validation.sh"}},
        ]},
    ]
    followed, ignored = _classify_instruction_adherence(instructions, trace)
    assert "Run the validation script" in followed
    assert "Run the validation script" not in ignored


def test_classify_instruction_adherence_ignored():
    """Instruction whose keywords are absent from the trace should end up in 'ignored'."""
    instructions = ["Use the cache helper"]
    trace = [
        {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": "/tmp/output.txt"}},
        ]},
    ]
    followed, ignored = _classify_instruction_adherence(instructions, trace)
    assert "Use the cache helper" in ignored
    assert "Use the cache helper" not in followed


# ---------------------------------------------------------------------------
# Integration tests — run_l3 with mocked LLM
# ---------------------------------------------------------------------------

@patch("skillforge.agents.judge.trace_analysis.AsyncAnthropic")
@pytest.mark.asyncio
async def test_run_l3_full_pipeline_mocked_llm(mock_anthropic_cls):
    """Happy path: Skill loaded, Bash script executed, 2 instructions (1 followed, 1 ignored)."""
    diagnosis_json = '{"1": "not relevant to this challenge"}'
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        return_value=_mock_anthropic_response(diagnosis_json)
    )
    mock_anthropic_cls.return_value = mock_client

    body = """## Workflow

### Step 1: Run the validation script
- Use the xyzzyx_zorp_gizmo for lookups
"""
    skill = _make_skill(body)
    trace = [
        {"role": "assistant", "content": [
            _tool_use_block("Skill"),
            {"type": "tool_use", "name": "Bash", "input": {"command": "bash scripts/validate.sh"}},
        ]},
        {"role": "assistant", "content": "Run the validation script now."},
    ]
    result = _make_result(trace=trace)
    out = await run_l3(result, skill)

    assert out.skill_was_loaded is True
    assert "scripts/validate.sh" in out.scripts_executed
    assert "Skill" in out.behavioral_signature
    assert "Bash" in out.behavioral_signature
    # At least one instruction classified (followed or ignored)
    assert len(out.instructions_followed) + len(out.instructions_ignored) >= 1
    # Ignored diagnostics populated (LLM was called because something was ignored)
    assert isinstance(out.ignored_diagnostics, dict)


@patch("skillforge.agents.judge.trace_analysis.AsyncAnthropic")
@pytest.mark.asyncio
async def test_run_l3_skips_llm_when_no_ignored(mock_anthropic_cls):
    """When all instructions are followed, the LLM should NOT be called."""
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock()
    mock_anthropic_cls.return_value = mock_client

    # Instruction: "Run the validation script"
    # Trace contains "validation" — heuristic should classify as followed
    body = "- Run the validation script\n"
    skill = _make_skill(body)
    trace = [
        {"role": "assistant", "content": "Run the validation script now for validation purposes."},
    ]
    result = _make_result(trace=trace)
    out = await run_l3(result, skill)

    assert out.ignored_diagnostics == {}
    mock_client.messages.create.assert_not_called()


@patch("skillforge.agents.judge.trace_analysis.AsyncAnthropic")
@pytest.mark.asyncio
async def test_run_l3_handles_malformed_diagnosis_response(mock_anthropic_cls):
    """Garbage LLM response should produce 'diagnosis unparseable' entries, no crash."""
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        return_value=_mock_anthropic_response("I cannot provide JSON right now.")
    )
    mock_anthropic_cls.return_value = mock_client

    body = "- Use the xyzzyx_zorp_gizmo helper\n"
    skill = _make_skill(body)
    # Trace has nothing matching "xyzzyx_zorp_gizmo" — guaranteed ignored
    trace = [{"role": "assistant", "content": "Just reading files."}]
    result = _make_result(trace=trace)
    out = await run_l3(result, skill)

    # Should not crash; diagnostics should exist
    assert isinstance(out.ignored_diagnostics, dict)
    for val in out.ignored_diagnostics.values():
        assert "diagnosis unparseable" in val


@patch("skillforge.agents.judge.trace_analysis.AsyncAnthropic")
@pytest.mark.asyncio
async def test_diagnose_ignored_handles_llm_error(mock_anthropic_cls):
    """LLM raising an exception should produce 'diagnosis error' strings, no crash."""
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=RuntimeError("network failure"))
    mock_anthropic_cls.return_value = mock_client

    ignored = ["Use the xyzzyx_zorp_gizmo helper", "Check the frobnitz cache"]
    trace: list[dict] = []
    result = await _diagnose_ignored(ignored, trace, "---\nname: s\n---\nbody")

    assert isinstance(result, dict)
    for ins in ignored:
        assert ins in result
        assert "diagnosis error" in result[ins]
