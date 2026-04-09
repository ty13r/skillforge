"""Breeder — reflective mutation, multi-parent crossover, learning log, bible publishing.

Inspired by GEPA's Actionable Side Information: mutations are diagnostic, not
random. The Breeder reads execution traces and trait attribution from the judging
pipeline, identifies root causes of failures, and proposes targeted fixes.

Responsibilities:
- Elitism: top N Skills survive unchanged (N scales with population size)
- Reflective crossover: combine traits from 2-3 parents guided by attribution
- Diagnostic mutation: fix specific causes surfaced by trait attribution
- Joint component mutation: frontmatter + body + scripts mutate together
- Wildcard: 1+ slots per generation for fresh Skills
- Learning log maintenance: append new lessons each generation
- Bible publishing: extract generalizable findings to ``bible/findings/``

Slot allocation scales with ``target_pop_size`` (never hardcoded; see PLAN.md
§Cross-cutting contracts #11).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from anthropic import AsyncAnthropic

from skillforge.agents.spawner import breed_next_gen, spawn_gen0
from skillforge.config import (
    ANTHROPIC_API_KEY,
    BIBLE_DIR,
    BREEDER_CALL_MODE,
    model_for,
)
from skillforge.models import Generation, SkillGenome

# ---------------------------------------------------------------------------
# Slot allocation
# ---------------------------------------------------------------------------


def compute_slots(target_pop_size: int) -> dict[str, int]:
    """Allocate breeding slots as a function of ``target_pop_size``.

    Formula (from PLAN.md §Step 6e Breeder):

        elitism    = max(1, target_pop_size // 5 * 2)   ~40% floor 1
        wildcards  = max(1, target_pop_size // 10)      ~10% floor 1
        remainder  = target_pop_size - elitism - wildcards
        diagnostic = remainder // 2
        crossover  = remainder - diagnostic

    Worked examples:
        pop_size=3  → elitism=1, wildcards=1, diagnostic=0, crossover=1 (sum 3)
        pop_size=5  → elitism=2, wildcards=1, diagnostic=1, crossover=1 (sum 5)
        pop_size=10 → elitism=4, wildcards=1, diagnostic=2, crossover=3 (sum 10)
    """
    if target_pop_size < 1:
        raise ValueError(f"target_pop_size must be >=1, got {target_pop_size}")

    elitism = max(1, (target_pop_size // 5) * 2)
    wildcards = max(1, target_pop_size // 10)

    # Ensure elitism + wildcards doesn't exceed target (pathological tiny sizes)
    if elitism + wildcards > target_pop_size:
        elitism = max(1, target_pop_size - 1)
        wildcards = max(0, target_pop_size - elitism)

    remainder = target_pop_size - elitism - wildcards
    diagnostic = remainder // 2
    crossover = remainder - diagnostic

    slots = {
        "elitism": elitism,
        "wildcards": wildcards,
        "diagnostic": diagnostic,
        "crossover": crossover,
    }
    assert sum(slots.values()) == target_pop_size, (
        f"slot sum {sum(slots.values())} != target {target_pop_size}: {slots}"
    )
    return slots


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def _aggregate_fitness(skill: SkillGenome) -> float:
    """Scalar aggregate of Pareto objectives for ranking (charts/selection).

    The Pareto front is the real answer; this scalar is a summary for
    ordering within the front (and for ranking Skills OFF the front).
    """
    if not skill.pareto_objectives:
        return 0.0
    return sum(skill.pareto_objectives.values()) / len(skill.pareto_objectives)


def rank_skills(generation: Generation) -> list[SkillGenome]:
    """Return generation.skills sorted by (is_pareto_optimal desc, fitness desc)."""
    return sorted(
        generation.skills,
        key=lambda s: (s.is_pareto_optimal, _aggregate_fitness(s)),
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Main breed() entry point
# ---------------------------------------------------------------------------


async def breed(
    generation: Generation,
    learning_log: list[str],
    specialization: str,
    target_pop_size: int,
) -> tuple[list[SkillGenome], list[str], str]:
    """Produce the next generation from a ranked current generation.

    Returns ``(next_gen_skills, new_learning_log_entries, breeding_report)``.

    The slot allocation scales with ``target_pop_size`` — see ``compute_slots``.
    The function guarantees ``len(next_gen_skills) == target_pop_size``.
    """
    slots = compute_slots(target_pop_size)
    ranked = rank_skills(generation)

    next_gen: list[SkillGenome] = []

    # --- Elitism: top-N survive unchanged (but bump generations_survived) ---
    elites = ranked[: slots["elitism"]]
    for elite in elites:
        carried = _carry_elite(elite)
        next_gen.append(carried)

    # --- Diagnostic mutation: pick low-scoring Skills, ask LLM for targeted fixes ---
    low_scorers = ranked[-slots["diagnostic"] :] if slots["diagnostic"] > 0 else []
    diagnostic_instructions = _build_diagnostic_instructions(
        low_scorers, learning_log, slots["diagnostic"]
    )
    if slots["diagnostic"] > 0 and low_scorers:
        try:
            diagnostic_children = await breed_next_gen(
                parents=low_scorers,
                learning_log=learning_log,
                breeding_instructions=diagnostic_instructions,
            )
            next_gen.extend(diagnostic_children[: slots["diagnostic"]])
        except Exception as exc:  # noqa: BLE001
            # Fall through — wildcard slots below absorb the shortfall
            print(f"breeder: diagnostic mutation failed: {exc}")

    # --- Reflective crossover: combine 2-3 Pareto-optimal parents ---
    pareto_parents = [s for s in ranked if s.is_pareto_optimal][:3]
    if not pareto_parents:
        # Fallback: use top 3 by fitness if nobody is Pareto-optimal
        pareto_parents = ranked[:3]

    crossover_instructions = _build_crossover_instructions(
        pareto_parents, learning_log, slots["crossover"]
    )
    if slots["crossover"] > 0 and pareto_parents:
        try:
            crossover_children = await breed_next_gen(
                parents=pareto_parents,
                learning_log=learning_log,
                breeding_instructions=crossover_instructions,
            )
            next_gen.extend(crossover_children[: slots["crossover"]])
        except Exception as exc:  # noqa: BLE001
            print(f"breeder: crossover failed: {exc}")

    # --- Wildcard: fresh Skills via spawn_gen0 ---
    if slots["wildcards"] > 0:
        try:
            wildcards = await spawn_gen0(
                specialization=specialization,
                pop_size=slots["wildcards"],
            )
            # Mark wildcards as mutations on the next generation
            next_gen_num = (generation.number + 1)
            for w in wildcards:
                w.generation = next_gen_num
                w.mutations = ["wildcard"]
                w.mutation_rationale = "Wildcard slot: fresh spawn to prevent convergence"
            next_gen.extend(wildcards)
        except Exception as exc:  # noqa: BLE001
            print(f"breeder: wildcard spawn failed: {exc}")

    # --- Trim or pad to exactly target_pop_size ---
    next_gen = next_gen[:target_pop_size]

    # If we fell short (any slot failed), pad with elites cloned forward
    while len(next_gen) < target_pop_size and ranked:
        next_gen.append(_carry_elite(ranked[0]))

    assert len(next_gen) == target_pop_size, (
        f"breeder produced {len(next_gen)} children, expected {target_pop_size}"
    )

    # --- Stamp generation number on everything ---
    next_gen_num = generation.number + 1
    for child in next_gen:
        child.generation = next_gen_num

    # --- Extract new learning log entries + write breeding report ---
    new_lessons, breeding_report = await _extract_lessons_and_report(
        generation, learning_log, slots, elites, pareto_parents
    )

    return (next_gen, new_lessons, breeding_report)


def _carry_elite(skill: SkillGenome) -> SkillGenome:
    """Return an elite skill carried forward with bumped metadata."""
    import copy

    carried = copy.deepcopy(skill)
    carried.generations_survived += 1
    carried.mutations = ["elitism"]
    carried.mutation_rationale = "Elitism: top-ranked parent carried forward unchanged"
    # Bump maturity if the skill is surviving well
    if carried.generations_survived >= 3 and carried.maturity == "tested":
        carried.maturity = "hardened"
    elif carried.generations_survived >= 2 and carried.maturity == "draft":
        carried.maturity = "tested"
    return carried


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_diagnostic_instructions(
    low_scorers: list[SkillGenome],
    learning_log: list[str],
    n_children: int,
) -> str:
    """Build breeding instructions for diagnostic mutation of low scorers."""
    if not low_scorers or n_children == 0:
        return ""

    diagnoses = []
    for skill in low_scorers:
        worst_traits = sorted(
            skill.trait_attribution.items(),
            key=lambda kv: kv[1],
        )[:3]
        trait_notes = "\n".join(
            f"    - {t}: contribution {c:.2f} — {skill.trait_diagnostics.get(t, 'no diagnosis')}"
            for t, c in worst_traits
        )
        diagnoses.append(
            f"  Skill {skill.id[:8]}:\n"
            f"    aggregate fitness: {_aggregate_fitness(skill):.2f}\n"
            f"    worst traits:\n{trait_notes}"
        )

    log_section = "\n".join(f"  - {entry}" for entry in learning_log[-10:])

    return (
        f"Produce exactly {n_children} child Skill(s) by DIAGNOSTIC MUTATION of the "
        "low-scoring parent(s) below. For each child, identify the root cause of "
        "the parent's low fitness (from the trait diagnostics), and make a TARGETED "
        "fix — rewrite or remove the underperforming instructions, tighten vague "
        "phrasing, add concrete examples for ignored rules, or rescope the trait.\n\n"
        "Do NOT make random changes. Every mutation must cite a specific parent "
        "trait and explain (in mutation_rationale) how the child addresses it.\n\n"
        f"Low-scoring parents:\n{chr(10).join(diagnoses)}\n\n"
        f"Recent lessons (learning log):\n{log_section or '  (none yet)'}"
    )


def _build_crossover_instructions(
    parents: list[SkillGenome],
    learning_log: list[str],
    n_children: int,
) -> str:
    """Build instructions for reflective crossover across 2-3 parents."""
    if not parents or n_children == 0:
        return ""

    parent_notes = []
    for p in parents:
        best_traits = sorted(
            p.trait_attribution.items(),
            key=lambda kv: kv[1],
            reverse=True,
        )[:3]
        trait_summary = ", ".join(f"{t}:{c:+.2f}" for t, c in best_traits) or "(no attribution)"
        parent_notes.append(
            f"  Parent {p.id[:8]} (fitness {_aggregate_fitness(p):.2f}): "
            f"best traits → {trait_summary}"
        )

    log_section = "\n".join(f"  - {entry}" for entry in learning_log[-10:])

    return (
        f"Produce exactly {n_children} child Skill(s) by REFLECTIVE CROSSOVER of the "
        f"Pareto-optimal parents below. Combine the HIGH-CONTRIBUTING traits from "
        "each parent into each child, preserving the causal mechanism that made "
        "each trait successful (not just the surface phrasing).\n\n"
        "Crossover is NOT concatenation. For each child, explain (in mutation_rationale) "
        "which traits from which parents were combined and WHY those particular "
        "traits work together.\n\n"
        f"Pareto-optimal parents:\n{chr(10).join(parent_notes)}\n\n"
        f"Recent lessons (learning log):\n{log_section or '  (none yet)'}"
    )


# ---------------------------------------------------------------------------
# Learning log extraction + breeding report
# ---------------------------------------------------------------------------


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
    else:
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
        client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model=model_for("breeder"),
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text if response.content else ""
    except Exception as exc:  # noqa: BLE001
        return [f"(lesson extraction failed: {exc})"]

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
        client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model=model_for("breeder"),
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text if response.content else ""
    except Exception as exc:  # noqa: BLE001
        return f"(breeding report failed: {exc})"


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
        client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model=model_for("breeder"),
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text if response.content else ""
    except Exception as exc:  # noqa: BLE001
        return ([f"(consolidated extraction failed: {exc})"], "")

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


# ---------------------------------------------------------------------------
# Bible publishing
# ---------------------------------------------------------------------------


def publish_findings_to_bible(
    new_entries: list[str],
    run_id: str,
    generation: int,
) -> None:
    """Write new learning-log entries as numbered finding files under bible/findings/.

    Each finding gets its own file following the schema in bible/README.md.
    Also appends a summary line to bible/evolution-log.md.

    Failures here are logged but never raised — we don't want a bible write
    failure to abort an evolution run.
    """
    if not new_entries:
        return

    findings_dir = BIBLE_DIR / "findings"
    try:
        findings_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"bible: failed to create findings dir: {exc}")
        return

    # Determine the next finding number by scanning existing files
    existing_nums = []
    for f in findings_dir.glob("*.md"):
        match = re.match(r"^(\d{3})-", f.name)
        if match:
            existing_nums.append(int(match.group(1)))
    next_num = (max(existing_nums) + 1) if existing_nums else 1

    timestamp = datetime.now(UTC).strftime("%Y-%m-%d")

    for entry in new_entries:
        if not entry or entry.startswith("("):
            # Skip error placeholders
            continue
        slug = _slugify(entry)[:40]
        filename = f"{next_num:03d}-{slug}.md"
        content = _finding_markdown(
            num=next_num,
            title=entry,
            body=entry,
            run_id=run_id,
            generation=generation,
            timestamp=timestamp,
        )
        try:
            (findings_dir / filename).write_text(content)
        except OSError as exc:
            print(f"bible: failed to write finding {filename}: {exc}")
            continue
        next_num += 1

    # Append to evolution log
    log_path = BIBLE_DIR / "evolution-log.md"
    try:
        if log_path.exists():
            existing = log_path.read_text()
        else:
            existing = "# Evolution Log\n\n*Chronological log of all SkillForge evolution runs.*\n\n"
        entry_line = f"- **{timestamp}** — run `{run_id[:8]}` gen {generation}: {len(new_entries)} new finding(s)\n"
        log_path.write_text(existing + entry_line)
    except OSError as exc:
        print(f"bible: failed to update evolution log: {exc}")


def _slugify(text: str) -> str:
    """Kebab-case a string for use in a filename."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "untitled"


def _finding_markdown(
    num: int,
    title: str,
    body: str,
    run_id: str,
    generation: int,
    timestamp: str,
) -> str:
    """Render a finding markdown file per bible/README.md schema."""
    short_title = title.split(".")[0][:60] if "." in title else title[:60]
    return f"""# Finding {num:03d}: {short_title}

**Discovered**: {timestamp}
**Evolution Run**: {run_id}
**Generation**: {generation}
**Status**: finding

## Observation

{body}

## Evidence

Automatically extracted from the generation {generation} trait attribution
and trace analysis by the Breeder agent. See run `{run_id}` in the
SkillForge database for the raw scores and traces.

## Mechanism

*To be filled in if this finding replicates across 3+ runs and gets
promoted to a pattern.*

## Recommendation

*To be filled in upon promotion.*
"""
