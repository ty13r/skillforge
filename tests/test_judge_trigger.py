"""Tests for L2 trigger accuracy judging layer."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from skillforge.agents.judge.trigger import _extract_description, _parse_yn_response, run_l2
from skillforge.models import SkillGenome


def _make_skill(description: str = "Use when testing. Does things.") -> SkillGenome:
    md = f"""---
name: test-skill
description: {description}
---

# Test Skill

## Quick start
Do the thing.

## Examples
**Example 1:** Input: x / Output: y
**Example 2:** Input: a / Output: b
"""
    return SkillGenome(id="s1", generation=0, skill_md_content=md)


@pytest.mark.asyncio
async def test_run_l2_perfect_precision_and_recall():
    """Model predicts correctly: both triggers fire, both non-triggers don't."""
    with patch(
        "skillforge.agents.judge.trigger.stream_text",
        new_callable=AsyncMock,
        return_value="1. Y\n2. Y\n3. N\n4. N",
    ):
        skill = _make_skill()
        precision, recall = await run_l2(
            skill,
            should_trigger=["do the thing", "run the test"],
            should_not_trigger=["unrelated query", "something else"],
        )

    assert precision == 1.0
    assert recall == 1.0


@pytest.mark.asyncio
async def test_run_l2_zero_recall_all_missed():
    """Model says N for every prompt — triggers are all missed."""
    with patch(
        "skillforge.agents.judge.trigger.stream_text",
        new_callable=AsyncMock,
        return_value="1. N\n2. N\n3. N\n4. N",
    ):
        skill = _make_skill()
        precision, recall = await run_l2(
            skill,
            should_trigger=["do the thing", "run the test"],
            should_not_trigger=["unrelated query", "something else"],
        )

    assert recall == 0.0


@pytest.mark.asyncio
async def test_run_l2_handles_zero_precision():
    """All should_not_trigger prompts are falsely predicted Y — precision degrades."""
    with patch(
        "skillforge.agents.judge.trigger.stream_text",
        new_callable=AsyncMock,
        return_value="1. Y\n2. Y\n3. Y",
    ):
        skill = _make_skill()
        precision, recall = await run_l2(
            skill,
            should_trigger=["do the thing"],
            should_not_trigger=["unrelated query", "something else"],
        )

    # TP=1, FP=2 → precision = 1/3 < 1.0
    assert precision < 1.0


@pytest.mark.asyncio
async def test_run_l2_empty_queries_returns_zero_zero():
    """Empty query lists return (0.0, 0.0) without calling the API."""
    with patch(
        "skillforge.agents.judge.trigger.stream_text",
        new_callable=AsyncMock,
    ) as mock_stream:
        skill = _make_skill()
        precision, recall = await run_l2(skill, should_trigger=[], should_not_trigger=[])

        assert (precision, recall) == (0.0, 0.0)
        mock_stream.assert_not_called()


@pytest.mark.asyncio
async def test_run_l2_handles_malformed_response():
    """API returns random text with no Y/N — defaults to all N, recall=0. No crash."""
    with patch(
        "skillforge.agents.judge.trigger.stream_text",
        new_callable=AsyncMock,
        return_value="I cannot determine the answer to this.",
    ):
        skill = _make_skill()
        precision, recall = await run_l2(
            skill,
            should_trigger=["do the thing", "run the test"],
            should_not_trigger=["unrelated query"],
        )

    assert recall == 0.0


@pytest.mark.asyncio
async def test_run_l2_handles_missing_description():
    """Skill with empty frontmatter / no description returns (0.0, 0.0) without API call."""
    md = "No frontmatter here at all — just body text."
    skill = SkillGenome(id="s2", generation=0, skill_md_content=md)

    with patch(
        "skillforge.agents.judge.trigger.stream_text",
        new_callable=AsyncMock,
    ) as mock_stream:
        precision, recall = await run_l2(
            skill,
            should_trigger=["do the thing"],
            should_not_trigger=["unrelated"],
        )

        assert (precision, recall) == (0.0, 0.0)
        mock_stream.assert_not_called()


def test_extract_description_pulls_from_frontmatter():
    """Helper correctly extracts description from valid SKILL.md frontmatter."""
    md = """---
name: my-skill
description: Use this for code review tasks.
version: 1.0
---

# Body
"""
    assert _extract_description(md) == "Use this for code review tasks."


def test_extract_description_returns_empty_on_malformed():
    """No frontmatter, malformed YAML, or missing description key → empty string, no crash."""
    # No frontmatter
    assert _extract_description("Just some body text.") == ""

    # Missing description key
    md_no_desc = "---\nname: my-skill\n---\n# Body\n"
    assert _extract_description(md_no_desc) == ""

    # Malformed YAML
    md_bad_yaml = "---\n: invalid: yaml: [\n---\n# Body\n"
    assert _extract_description(md_bad_yaml) == ""

    # Only one --- delimiter
    assert _extract_description("---\nname: skill\n") == ""


def test_parse_yn_response_handles_formatting_variants():
    """Various Y/N line formats are all parsed correctly."""
    text = "1. Y\n2) N\n3: Y\n  4.   Y  "
    result = _parse_yn_response(text, 4)
    assert result == ["Y", "N", "Y", "Y"]


def test_parse_yn_response_defaults_missing_to_n():
    """Model only answers prompts 1 and 3 of 5 — the rest default to N."""
    text = "1. Y\n3. Y"
    result = _parse_yn_response(text, 5)
    assert result[0] == "Y"
    assert result[1] == "N"
    assert result[2] == "Y"
    assert result[3] == "N"
    assert result[4] == "N"


@pytest.mark.asyncio
async def test_run_l2_uses_configured_model():
    """The model passed to stream_text matches the return value of model_for."""
    sentinel_model = "claude-sentinel-model-9999"

    with (
        patch(
            "skillforge.agents.judge.trigger.stream_text",
            new_callable=AsyncMock,
            return_value="1. Y\n2. N",
        ) as mock_stream,
        patch(
            "skillforge.agents.judge.trigger.model_for",
            return_value=sentinel_model,
        ) as mock_model_for,
    ):
        skill = _make_skill()
        await run_l2(
            skill,
            should_trigger=["do the thing"],
            should_not_trigger=["unrelated"],
        )

        mock_model_for.assert_called_once_with("l2_trigger")
        mock_stream.assert_called_once()
        call_kwargs = mock_stream.call_args.kwargs
        assert call_kwargs.get("model") == sentinel_model


def test_run_l2_never_hardcodes_model():
    """Source file must not contain hardcoded model strings."""
    import pathlib
    source = pathlib.Path(__file__).parent.parent / "skillforge" / "agents" / "judge" / "trigger.py"
    content = source.read_text()
    assert "claude-sonnet" not in content, "Hardcoded model string found: claude-sonnet"
    assert "claude-opus" not in content, "Hardcoded model string found: claude-opus"
    assert "claude-haiku" not in content, "Hardcoded model string found: claude-haiku"
