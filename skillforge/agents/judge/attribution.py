"""L5 — Trait attribution (the novel SkillForge contribution).

Reads each Skill's SKILL.md alongside its execution trace and output. For each
discrete instruction or trait:
- If followed (trace evidence): correlate with L1-L4 scores → ``trait_contribution``
- If ignored: diagnose *why* (too vague? contradicted? irrelevant?) → ``trait_diagnostics``

Produces the causal signal the Breeder uses for reflective mutation.
"""

from __future__ import annotations

import json
import re

from anthropic import AsyncAnthropic
from skillforge.agents._llm import stream_text

from skillforge.config import ANTHROPIC_API_KEY, model_for
from skillforge.models import CompetitionResult, SkillGenome


async def run_l5(result: CompetitionResult, skill: SkillGenome) -> CompetitionResult:
    """Populate L5 trait_contribution + trait_diagnostics. Returns result."""
    # The Breeder depends on these fields — always populate them, even if
    # the attribution call fails, default to empty dicts.
    result.trait_contribution = {}
    result.trait_diagnostics = {}

    # Use skill.traits if populated (Spawner extracted them); otherwise fall
    # back to L3's instructions_followed + instructions_ignored as the trait set.
    traits = skill.traits if skill.traits else (
        result.instructions_followed + result.instructions_ignored
    )
    if not traits:
        result.judge_reasoning += " [L5: no traits to attribute]"
        return result

    # Build the prompt
    prompt = _build_attribution_prompt(result, skill, traits)

    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY, timeout=300.0)
    try:
        text = await stream_text(
            client,
            model=model_for("judge_attribution"),
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # noqa: BLE001
        result.judge_reasoning += f" [L5: attribution API error: {exc}]"
        return result

    # Parse structured response
    parsed = _parse_attribution_response(text, traits)
    result.trait_contribution = parsed["contribution"]
    result.trait_diagnostics = parsed["diagnostics"]
    if "judge_reasoning" in parsed and parsed["judge_reasoning"]:
        result.judge_reasoning += f" [L5: {parsed['judge_reasoning']}]"

    return result


def _build_attribution_prompt(
    result: CompetitionResult,
    skill: SkillGenome,
    traits: list[str],
) -> str:
    """Build the attribution prompt for the LLM."""
    # Summarize L1-L4 scores
    scores = {
        "compiles": result.compiles,
        "tests_pass": result.tests_pass,
        "lint_score": result.lint_score,
        "trigger_precision": result.trigger_precision,
        "trigger_recall": result.trigger_recall,
        "skill_was_loaded": result.skill_was_loaded,
        "pareto_objectives": result.pareto_objectives,
    }

    # Trace preview (bounded)
    trace_preview = _summarize_trace(result.trace, max_chars=1500)

    # Numbered traits
    numbered_traits = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(traits))

    followed = "\n".join(f"  - {i}" for i in result.instructions_followed[:10])
    ignored = "\n".join(f"  - {i}" for i in result.instructions_ignored[:10])

    return (
        "You are judging a Claude Agent Skill's trait-level fitness contribution.\n\n"
        "## Task\n"
        "For each trait/instruction below, estimate:\n"
        "  1. Its FITNESS CONTRIBUTION: a float in [-1.0, 1.0] where +1.0 means\n"
        "     the trait strongly improved the outcome, -1.0 means it strongly hurt,\n"
        "     and 0.0 means neutral or no effect.\n"
        "  2. A one-sentence DIAGNOSTIC explaining WHY it contributed or didn't,\n"
        "     grounded in trace evidence when possible.\n\n"
        f"## SKILL.md content\n```\n{skill.skill_md_content[:2000]}\n```\n\n"
        f"## L1-L4 scores\n{json.dumps(scores, default=str, indent=2)}\n\n"
        f"## Instructions followed (from L3)\n{followed or '  (none)'}\n\n"
        f"## Instructions ignored (from L3)\n{ignored or '  (none)'}\n\n"
        f"## Execution trace summary\n{trace_preview}\n\n"
        f"## Traits to judge\n{numbered_traits}\n\n"
        "## Response format\n"
        "Respond with ONLY a JSON object. No prose before or after. Example:\n"
        '{\n'
        '  "trait_contribution": {"trait name 1": 0.3, "trait name 2": -0.1},\n'
        '  "trait_diagnostics": {\n'
        '    "trait name 1": "traced to successful test execution on challenge X",\n'
        '    "trait name 2": "instruction was too vague; Claude ignored it"\n'
        '  },\n'
        '  "summary": "one sentence overall assessment"\n'
        '}\n'
        "Use the EXACT trait strings as keys. Every trait must appear in both dicts."
    )


def _summarize_trace(trace: list[dict], max_chars: int = 1500) -> str:
    """Compact trace summary for the prompt."""
    parts: list[str] = []
    for msg in trace:
        content = msg.get("content")
        if isinstance(content, str):
            parts.append(content[:150])
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    name = block.get("name", "")
                    text = str(block.get("text", ""))[:100]
                    if name:
                        parts.append(f"[{name}] {text}")
                    elif text:
                        parts.append(text)
    summary = " | ".join(parts)
    if len(summary) > max_chars:
        return summary[:max_chars] + " ... [truncated]"
    return summary or "(empty trace)"


def _parse_attribution_response(text: str, expected_traits: list[str]) -> dict:
    """Parse the LLM's JSON response into contribution + diagnostics dicts.

    Defensively handles malformed responses — always returns valid dicts with
    every expected trait present. Missing traits get contribution=0.0 and
    diagnostic='no attribution returned'.
    """
    contribution: dict[str, float] = {}
    diagnostics: dict[str, str] = {}
    summary = ""

    # Try to find a JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        # Degenerate — fill defaults
        return {
            "contribution": dict.fromkeys(expected_traits, 0.0),
            "diagnostics": {t: "no JSON in attribution response" for t in expected_traits},
            "judge_reasoning": "attribution unparseable",
        }

    try:
        raw = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {
            "contribution": dict.fromkeys(expected_traits, 0.0),
            "diagnostics": {t: "attribution JSON malformed" for t in expected_traits},
            "judge_reasoning": "attribution unparseable",
        }

    raw_contrib = raw.get("trait_contribution", {})
    raw_diag = raw.get("trait_diagnostics", {})
    summary = raw.get("summary", "")

    for trait in expected_traits:
        # Coerce contribution to a float in [-1.0, 1.0]
        val = raw_contrib.get(trait, 0.0)
        try:
            fval = float(val)
            contribution[trait] = max(-1.0, min(1.0, fval))
        except (TypeError, ValueError):
            contribution[trait] = 0.0

        diag = raw_diag.get(trait, "no attribution returned")
        diagnostics[trait] = str(diag) if diag is not None else "no attribution returned"

    return {
        "contribution": contribution,
        "diagnostics": diagnostics,
        "judge_reasoning": summary,
    }
