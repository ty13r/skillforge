"""Main breed() orchestrator — allocate slots, run subagents, pad + return.

``breed_next_gen`` / ``spawn_gen0`` / ``_extract_lessons_and_report`` are
resolved through the package namespace at call time (not bound at import)
so that tests which ``patch("skillforge.agents.breeder.breed_next_gen")``
still intercept the call after the monolithic module was split.
"""

from __future__ import annotations

import logging

from skillforge.agents.breeder._prompts import (
    _build_crossover_instructions,
    _build_diagnostic_instructions,
)
from skillforge.agents.breeder._ranking import compute_slots, rank_skills
from skillforge.models import Generation, SkillGenome

logger = logging.getLogger("skillforge.agents.breeder")


def _pkg():
    """Return the breeder package so attribute lookups honor test patches."""
    from skillforge.agents import breeder as _breeder_pkg

    return _breeder_pkg


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
            diagnostic_children = await _pkg().breed_next_gen(
                parents=low_scorers,
                learning_log=learning_log,
                breeding_instructions=diagnostic_instructions,
            )
            next_gen.extend(diagnostic_children[: slots["diagnostic"]])
        except Exception:  # noqa: BLE001 — subagent boundary: one slot failure must not kill the whole breed
            # Fall through — wildcard slots below absorb the shortfall.
            logger.exception("breeder.diagnostic_failed")

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
            crossover_children = await _pkg().breed_next_gen(
                parents=pareto_parents,
                learning_log=learning_log,
                breeding_instructions=crossover_instructions,
            )
            next_gen.extend(crossover_children[: slots["crossover"]])
        except Exception:  # noqa: BLE001 — subagent boundary: one slot failure must not kill the whole breed
            logger.exception("breeder.crossover_failed")

    # --- Wildcard: fresh Skills via spawn_gen0 ---
    if slots["wildcards"] > 0:
        try:
            wildcards = await _pkg().spawn_gen0(
                specialization=specialization,
                pop_size=slots["wildcards"],
            )
            # Mark wildcards as mutations on the next generation
            next_gen_num = generation.number + 1
            for w in wildcards:
                w.generation = next_gen_num
                w.mutations = ["wildcard"]
                w.mutation_rationale = "Wildcard slot: fresh spawn to prevent convergence"
            next_gen.extend(wildcards)
        except Exception:  # noqa: BLE001 — subagent boundary: one slot failure must not kill the whole breed
            logger.exception("breeder.wildcard_spawn_failed")

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
    new_lessons, breeding_report = await _pkg()._extract_lessons_and_report(
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

