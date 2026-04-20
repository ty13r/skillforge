"""Breeder's reflection step — post-generation lessons + written report.

Calls the LLM to distill what this generation revealed about trait
fitness and to write a paragraph explaining the breeding decisions.
Degrades gracefully on SDK errors (see docs/clean-code.md §4).
"""

from __future__ import annotations

import json
import logging
import re

from anthropic import AsyncAnthropic

from skillforge.agents._llm import stream_text
from skillforge.agents.breeder._ranking import _aggregate_fitness
from skillforge.config import ANTHROPIC_API_KEY, BREEDER_CALL_MODE, model_for
from skillforge.models import Generation, SkillGenome

logger = logging.getLogger("skillforge.agents.breeder.reports")


async def _extract_lessons_and_report(
    generation: Generation,
    learning_log: list[str],
    slots: dict[str, int],
    elites: list[SkillGenome],
    pareto_parents: list[SkillGenome],
) -> tuple[list[str], str]:
    """Ask the LLM for (a) new learning log entries and (b) a breeding report.

    Dispatches on ``config.BREEDER_CALL_MODE``:
    - "separate" (default): two LLM calls, one for lessons, one for report
    - "consolidated" (Flex-3 cost saver): one structured call returning both
    """
    context = _build_breeding_context(generation, slots, elites, pareto_parents)

    if BREEDER_CALL_MODE == "consolidated":
        return await _extract_consolidated(context, learning_log)
    lessons = await _extract_lessons(context, learning_log)
    report = await _extract_breeding_report(context, slots, elites, pareto_parents)
    return lessons, report


def _build_breeding_context(
    generation: Generation,
    slots: dict[str, int],
    elites: list[SkillGenome],
    pareto_parents: list[SkillGenome],
) -> str:
    """Summarize this generation's results for the Breeder's LLM prompts."""
    elite_section = "\n".join(
        f"  - {s.id[:8]} fitness={_aggregate_fitness(s):.2f} traits={s.traits[:3]}"
        for s in elites
    ) or "  (none)"

    pareto_section = "\n".join(
        f"  - {s.id[:8]} fitness={_aggregate_fitness(s):.2f}"
        for s in pareto_parents
    ) or "  (none)"

    # Top 3 trait contributions across all results
    all_traits: dict[str, list[float]] = {}
    for r in generation.results:
        for trait, contrib in r.trait_contribution.items():
            all_traits.setdefault(trait, []).append(contrib)
    trait_means = sorted(
        [(t, sum(vs) / len(vs)) for t, vs in all_traits.items()],
        key=lambda kv: kv[1],
        reverse=True,
    )
    top_traits = "\n".join(
        f"  - {t}: {m:+.2f} (from trace attribution)" for t, m in trait_means[:5]
    ) or "  (no trait data)"

    return (
        f"Generation {generation.number} summary:\n"
        f"  population: {len(generation.skills)}\n"
        f"  best_fitness: {generation.best_fitness:.3f}\n"
        f"  avg_fitness: {generation.avg_fitness:.3f}\n"
        f"  pareto_front_size: {len(generation.pareto_front)}\n"
        f"\n"
        f"Slot allocation for next gen: {slots}\n"
        f"\n"
        f"Elites (carrying forward):\n{elite_section}\n"
        f"\n"
        f"Pareto-optimal parents selected for crossover:\n{pareto_section}\n"
        f"\n"
        f"Top-contributing traits this generation:\n{top_traits}\n"
    )


async def _extract_lessons(context: str, learning_log: list[str]) -> list[str]:
    """Single LLM call extracting generalizable lessons as a JSON array."""
    recent_log = "\n".join(f"- {e}" for e in learning_log[-10:])

    prompt = (
        "You are the Breeder agent for a population-based evolution of Claude Agent Skills. "
        "Based on the generation summary below, identify 1-3 NEW generalizable lessons "
        "about Skill authoring that this generation revealed. Do NOT repeat lessons from "
        "the existing learning log. Lessons should be actionable for future breeding, "
        "generic enough to apply across domains, and grounded in the trait attribution data.\n\n"
        f"## Generation summary\n{context}\n\n"
        f"## Existing learning log (don't repeat these)\n{recent_log or '(empty)'}\n\n"
        "## Response format\n"
        'Respond with ONLY a JSON array of 1-3 strings, like ["lesson 1", "lesson 2"]. '
        "No prose before or after."
    )

    try:
        client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY, timeout=300.0)
        text = await stream_text(
            client,
            model=model_for("breeder"),
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        # Degrade gracefully — a breeder that blocks on LLM hiccups would
        # stall the whole run. The SDK has many concrete error types across
        # versions; catching at the boundary keeps the engine moving.
        logger.exception("breeder.lesson_extraction_failed")
        return ["(lesson extraction failed)"]

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        lessons = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    return [str(lesson) for lesson in lessons if isinstance(lesson, str)][:3]


async def _extract_breeding_report(
    context: str,
    slots: dict[str, int],
    elites: list[SkillGenome],
    pareto_parents: list[SkillGenome],
) -> str:
    """Single LLM call producing a human-readable breeding report."""
    prompt = (
        "You are the Breeder agent for SkillForge. Write a 2-paragraph breeding report "
        "explaining the decisions for the next generation. Paragraph 1: what this "
        "generation revealed about trait fitness and which skills earned elite/Pareto "
        "status. Paragraph 2: the strategy for the next generation's diagnostic "
        "mutations and crossovers. Be specific, cite skill IDs by their 8-char prefix, "
        "and reference trait contributions when they shaped a decision.\n\n"
        f"## Generation summary\n{context}\n\n"
        "Respond with ONLY the report prose. No headings."
    )

    try:
        client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY, timeout=300.0)
        return await stream_text(
            client,
            model=model_for("breeder"),
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        # Degrade gracefully — see _extract_lessons for rationale.
        logger.exception("breeder.report_extraction_failed")
        return "(breeding report failed)"


async def _extract_consolidated(
    context: str,
    learning_log: list[str],
) -> tuple[list[str], str]:
    """Flex-3 cost saver: one LLM call produces both lessons and report as JSON."""
    recent_log = "\n".join(f"- {e}" for e in learning_log[-10:])

    prompt = (
        "You are the Breeder agent for SkillForge. Given the generation summary below, "
        "produce BOTH: (1) 1-3 NEW generalizable lessons about Skill authoring, and "
        "(2) a 2-paragraph breeding report explaining the decisions.\n\n"
        f"## Generation summary\n{context}\n\n"
        f"## Existing learning log (don't repeat)\n{recent_log or '(empty)'}\n\n"
        "## Response format\n"
        "Respond with ONLY a JSON object matching:\n"
        '{\n'
        '  "lessons": ["lesson 1", "lesson 2"],\n'
        '  "report": "Paragraph 1...\\n\\nParagraph 2..."\n'
        '}\n'
        "No prose before or after the JSON."
    )

    try:
        client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY, timeout=300.0)
        text = await stream_text(
            client,
            model=model_for("breeder"),
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        # Degrade gracefully — see _extract_lessons for rationale.
        logger.exception("breeder.consolidated_extraction_failed")
        return (["(consolidated extraction failed)"], "")

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return ([], "")
    try:
        raw = json.loads(match.group(0))
    except json.JSONDecodeError:
        return ([], "")

    lessons = [str(entry) for entry in raw.get("lessons", []) if isinstance(entry, str)][:3]
    report = str(raw.get("report", ""))
    return (lessons, report)
