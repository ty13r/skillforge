"""Pure ranking helpers — slot allocation + fitness aggregation + sorting.

No I/O, no LLM calls. Used by the main ``breed()`` orchestrator and by
``_build_breeding_context`` when it needs to format a ranked list.
"""

from __future__ import annotations

from skillforge.models import Generation, SkillGenome


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


