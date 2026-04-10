"""Tests for L3 trace-based behavioral analysis judging layer."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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

@pytest.mark.asyncio
async def test_run_l3_full_pipeline_mocked_llm():
    """Happy path: Skill loaded, Bash script executed, 2 instructions (1 followed, 1 ignored)."""
    diagnosis_json = '{"1": "not relevant to this challenge"}'

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

    with patch(
        "skillforge.agents.judge.trace_analysis.stream_text",
        new_callable=AsyncMock,
        return_value=diagnosis_json,
    ):
        out = await run_l3(result, skill)

    assert out.skill_was_loaded is True
    assert "scripts/validate.sh" in out.scripts_executed
    assert "Skill" in out.behavioral_signature
    assert "Bash" in out.behavioral_signature
    # At least one instruction classified (followed or ignored)
    assert len(out.instructions_followed) + len(out.instructions_ignored) >= 1
    # Ignored diagnostics populated (LLM was called because something was ignored)
    assert isinstance(out.ignored_diagnostics, dict)


@pytest.mark.asyncio
async def test_run_l3_skips_llm_when_no_ignored():
    """When all instructions are followed, the LLM should NOT be called."""
    # Instruction: "Run the validation script"
    # Trace contains "validation" — heuristic should classify as followed
    body = "- Run the validation script\n"
    skill = _make_skill(body)
    trace = [
        {"role": "assistant", "content": "Run the validation script now for validation purposes."},
    ]
    result = _make_result(trace=trace)

    with patch(
        "skillforge.agents.judge.trace_analysis.stream_text",
        new_callable=AsyncMock,
    ) as mock_stream:
        out = await run_l3(result, skill)

    assert out.ignored_diagnostics == {}
    mock_stream.assert_not_called()


@pytest.mark.asyncio
async def test_run_l3_handles_malformed_diagnosis_response():
    """Garbage LLM response should produce 'diagnosis unparseable' entries, no crash."""
    body = "- Use the xyzzyx_zorp_gizmo helper\n"
    skill = _make_skill(body)
    # Trace has nothing matching "xyzzyx_zorp_gizmo" — guaranteed ignored
    trace = [{"role": "assistant", "content": "Just reading files."}]
    result = _make_result(trace=trace)

    with patch(
        "skillforge.agents.judge.trace_analysis.stream_text",
        new_callable=AsyncMock,
        return_value="I cannot provide JSON right now.",
    ):
        out = await run_l3(result, skill)

    # Should not crash; diagnostics should exist
    assert isinstance(out.ignored_diagnostics, dict)
    for val in out.ignored_diagnostics.values():
        assert "diagnosis unparseable" in val


@pytest.mark.asyncio
async def test_diagnose_ignored_handles_llm_error():
    """stream_text raising an exception should produce 'diagnosis error' strings, no crash."""
    ignored = ["Use the xyzzyx_zorp_gizmo helper", "Check the frobnitz cache"]
    trace: list[dict] = []

    with patch(
        "skillforge.agents.judge.trace_analysis.stream_text",
        new_callable=AsyncMock,
        side_effect=RuntimeError("network failure"),
    ):
        result = await _diagnose_ignored(ignored, trace, "---\nname: s\n---\nbody")

    assert isinstance(result, dict)
    for ins in ignored:
        assert ins in result
        assert "diagnosis error" in result[ins]
