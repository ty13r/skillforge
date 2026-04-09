"""Tests for L5 trait attribution judging layer."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skillforge.agents.judge.attribution import _parse_attribution_response, run_l5
from skillforge.models import CompetitionResult, SkillGenome

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(**kwargs) -> CompetitionResult:
    defaults = dict(skill_id="s1", challenge_id="c1")
    defaults.update(kwargs)
    return CompetitionResult(**defaults)


def _make_skill(**kwargs) -> SkillGenome:
    defaults = dict(
        id="s1",
        generation=0,
        skill_md_content="---\nname: test-skill\ndescription: Use when testing.\n---\n\nDo step A.\nDo step B.\n",
    )
    defaults.update(kwargs)
    return SkillGenome(**defaults)


def _mock_api_response(text: str) -> MagicMock:
    """Build a mock AsyncAnthropic client that returns ``text``."""
    block = MagicMock()
    block.text = text

    response = MagicMock()
    response.content = [block]

    create_mock = AsyncMock(return_value=response)

    messages_mock = MagicMock()
    messages_mock.create = create_mock

    client_mock = MagicMock()
    client_mock.messages = messages_mock

    client_class = MagicMock(return_value=client_mock)
    return client_class


def _valid_json_response(traits: list[str], contributions: dict | None = None, diagnostics: dict | None = None) -> str:
    contrib = contributions or {t: 0.3 for t in traits}
    diag = diagnostics or {t: "traced to successful outcome" for t in traits}
    return json.dumps({
        "trait_contribution": contrib,
        "trait_diagnostics": diag,
        "summary": "overall good",
    })


# ---------------------------------------------------------------------------
# Test 1: populates contribution and diagnostics
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_l5_populates_contribution_and_diagnostics():
    """Mock API returns well-formed JSON with 2 traits; both dicts are populated."""
    traits = ["imperative-phrasing", "tdd-first"]
    skill = _make_skill(traits=traits)
    result = _make_result()

    response_text = _valid_json_response(traits)
    client_class = _mock_api_response(response_text)

    with patch("skillforge.agents.judge.attribution.AsyncAnthropic", client_class):
        out = await run_l5(result, skill)

    assert "imperative-phrasing" in out.trait_contribution
    assert "tdd-first" in out.trait_contribution
    assert "imperative-phrasing" in out.trait_diagnostics
    assert "tdd-first" in out.trait_diagnostics


# ---------------------------------------------------------------------------
# Test 2: uses skill.traits when present
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_l5_uses_skill_traits_when_present():
    """When skill.traits is set, those are the keys (not L3 instructions)."""
    traits = ["imperative-phrasing", "tdd-first"]
    skill = _make_skill(traits=traits)
    result = _make_result(
        instructions_followed=["do something else"],
        instructions_ignored=["another thing"],
    )

    response_text = _valid_json_response(traits)
    client_class = _mock_api_response(response_text)

    with patch("skillforge.agents.judge.attribution.AsyncAnthropic", client_class):
        out = await run_l5(result, skill)

    assert set(out.trait_contribution.keys()) == set(traits)
    assert "do something else" not in out.trait_contribution
    assert "another thing" not in out.trait_contribution


# ---------------------------------------------------------------------------
# Test 3: falls back to L3 instructions when no skill traits
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_l5_falls_back_to_l3_instructions_when_no_traits():
    """skill.traits is empty; L3's followed+ignored lists become the trait set."""
    skill = _make_skill(traits=[])
    result = _make_result(
        instructions_followed=["step A"],
        instructions_ignored=["step B"],
    )

    traits = ["step A", "step B"]
    response_text = _valid_json_response(traits)
    client_class = _mock_api_response(response_text)

    with patch("skillforge.agents.judge.attribution.AsyncAnthropic", client_class):
        out = await run_l5(result, skill)

    assert "step A" in out.trait_contribution
    assert "step B" in out.trait_contribution


# ---------------------------------------------------------------------------
# Test 4: empty traits and instructions → returns early without API call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_l5_empty_traits_and_instructions_returns_early():
    """No traits or L3 instructions → no API call, empty dicts, reasoning note."""
    skill = _make_skill(traits=[])
    result = _make_result()  # instructions_followed/ignored default to []

    client_class = MagicMock()

    with patch("skillforge.agents.judge.attribution.AsyncAnthropic", client_class):
        out = await run_l5(result, skill)

    # No API call was made
    client_class.assert_not_called()
    assert out.trait_contribution == {}
    assert out.trait_diagnostics == {}
    assert "no traits" in out.judge_reasoning


# ---------------------------------------------------------------------------
# Test 5: clamps out-of-range contribution values
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_l5_clamps_contribution_to_valid_range():
    """Values outside [-1.0, 1.0] are clamped."""
    traits = ["x", "y"]
    skill = _make_skill(traits=traits)
    result = _make_result()

    response_text = json.dumps({
        "trait_contribution": {"x": 2.5, "y": -5.0},
        "trait_diagnostics": {"x": "good", "y": "bad"},
        "summary": "clamped",
    })
    client_class = _mock_api_response(response_text)

    with patch("skillforge.agents.judge.attribution.AsyncAnthropic", client_class):
        out = await run_l5(result, skill)

    assert out.trait_contribution["x"] == 1.0
    assert out.trait_contribution["y"] == -1.0


# ---------------------------------------------------------------------------
# Test 6: handles malformed JSON gracefully
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_l5_handles_malformed_json_gracefully():
    """Garbage API response → defaults (0.0) for all traits, no crash."""
    traits = ["trait-a", "trait-b"]
    skill = _make_skill(traits=traits)
    result = _make_result()

    client_class = _mock_api_response("this is not json at all!!!")

    with patch("skillforge.agents.judge.attribution.AsyncAnthropic", client_class):
        out = await run_l5(result, skill)

    # No crash; dicts populated with defaults
    assert "trait-a" in out.trait_contribution
    assert "trait-b" in out.trait_contribution
    assert out.trait_contribution["trait-a"] == 0.0
    assert out.trait_contribution["trait-b"] == 0.0
    # Diagnostics explain unparseable
    for trait in traits:
        assert "unparseable" in out.trait_diagnostics[trait] or "no JSON" in out.trait_diagnostics[trait]


# ---------------------------------------------------------------------------
# Test 7: handles missing trait in response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_l5_handles_missing_trait_in_response():
    """Request 3 traits, API returns only 2; missing gets contribution=0.0."""
    traits = ["alpha", "beta", "gamma"]
    skill = _make_skill(traits=traits)
    result = _make_result()

    # API only returns alpha and beta
    response_text = json.dumps({
        "trait_contribution": {"alpha": 0.5, "beta": -0.2},
        "trait_diagnostics": {"alpha": "good", "beta": "neutral"},
        "summary": "partial",
    })
    client_class = _mock_api_response(response_text)

    with patch("skillforge.agents.judge.attribution.AsyncAnthropic", client_class):
        out = await run_l5(result, skill)

    assert out.trait_contribution["gamma"] == 0.0
    assert out.trait_diagnostics["gamma"] == "no attribution returned"


# ---------------------------------------------------------------------------
# Test 8: handles API error gracefully
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_l5_handles_api_error():
    """API raises an exception → empty dicts, error in judge_reasoning, no crash."""
    skill = _make_skill(traits=["some-trait"])
    result = _make_result()

    create_mock = AsyncMock(side_effect=RuntimeError("network failure"))
    messages_mock = MagicMock()
    messages_mock.create = create_mock
    client_mock = MagicMock()
    client_mock.messages = messages_mock
    client_class = MagicMock(return_value=client_mock)

    with patch("skillforge.agents.judge.attribution.AsyncAnthropic", client_class):
        out = await run_l5(result, skill)

    assert out.trait_contribution == {}
    assert out.trait_diagnostics == {}
    assert "attribution API error" in out.judge_reasoning


# ---------------------------------------------------------------------------
# Test 9: handles non-float contribution values
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_l5_handles_non_float_contribution_values():
    """String contributions (e.g. 'high') are coerced to 0.0, no crash."""
    traits = ["x"]
    skill = _make_skill(traits=traits)
    result = _make_result()

    response_text = json.dumps({
        "trait_contribution": {"x": "high"},
        "trait_diagnostics": {"x": "worked well"},
        "summary": "ok",
    })
    client_class = _mock_api_response(response_text)

    with patch("skillforge.agents.judge.attribution.AsyncAnthropic", client_class):
        out = await run_l5(result, skill)

    assert out.trait_contribution["x"] == 0.0


# ---------------------------------------------------------------------------
# Test 10: uses configured model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_l5_uses_configured_model():
    """The model passed to messages.create matches model_for('judge_attribution')."""
    traits = ["x"]
    skill = _make_skill(traits=traits)
    result = _make_result()

    response_text = _valid_json_response(traits)

    block = MagicMock()
    block.text = response_text
    api_response = MagicMock()
    api_response.content = [block]

    create_mock = AsyncMock(return_value=api_response)
    messages_mock = MagicMock()
    messages_mock.create = create_mock
    client_mock = MagicMock()
    client_mock.messages = messages_mock
    client_class = MagicMock(return_value=client_mock)

    sentinel_model = "sentinel-model-for-test"

    with (
        patch("skillforge.agents.judge.attribution.AsyncAnthropic", client_class),
        patch("skillforge.agents.judge.attribution.model_for", return_value=sentinel_model),
    ):
        await run_l5(result, skill)

    create_mock.assert_called_once()
    call_kwargs = create_mock.call_args
    assert call_kwargs.kwargs.get("model") == sentinel_model or call_kwargs.args[0] == sentinel_model or create_mock.call_args[1].get("model") == sentinel_model


# ---------------------------------------------------------------------------
# Test 11: trace content appears in prompt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_l5_includes_trace_summary_in_prompt():
    """Captured prompt must contain trace content."""
    traits = ["x"]
    skill = _make_skill(traits=traits)
    result = _make_result(trace=[{"role": "user", "content": "hello from trace XYZ"}])

    response_text = _valid_json_response(traits)

    captured_prompts: list[str] = []

    block = MagicMock()
    block.text = response_text
    api_response = MagicMock()
    api_response.content = [block]

    async def capture_create(**kwargs):
        messages = kwargs.get("messages", [])
        for m in messages:
            captured_prompts.append(m.get("content", ""))
        return api_response

    messages_mock = MagicMock()
    messages_mock.create = capture_create
    client_mock = MagicMock()
    client_mock.messages = messages_mock
    client_class = MagicMock(return_value=client_mock)

    with patch("skillforge.agents.judge.attribution.AsyncAnthropic", client_class):
        await run_l5(result, skill)

    combined = "\n".join(captured_prompts)
    assert "hello from trace XYZ" in combined


# ---------------------------------------------------------------------------
# Test 12: parse_attribution_response populates summary into judge_reasoning key
# ---------------------------------------------------------------------------

def test_parse_attribution_response_populates_summary_field():
    """Summary field from LLM JSON appears under 'judge_reasoning' key in parsed result."""
    text = json.dumps({
        "trait_contribution": {"foo": 0.5},
        "trait_diagnostics": {"foo": "explained"},
        "summary": "overall the skill performed well",
    })
    parsed = _parse_attribution_response(text, ["foo"])
    assert parsed["judge_reasoning"] == "overall the skill performed well"
