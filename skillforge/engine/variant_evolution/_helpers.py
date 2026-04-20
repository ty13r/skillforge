"""Shared helpers + defaults for variant_evolution orchestration."""

from __future__ import annotations

from skillforge.models import SkillGenome, VariantEvolution

# Atomic-mode defaults — small populations because the per-dimension
# challenge is narrow. Wave 1 of Phase 3 kept gen=1 (no breeding loop yet);
# post-v2.0 item 4 bumped the default to 2 so the default produces one
# round of breeding after gen 0. Existing VariantEvolution rows with
# ``num_generations=1`` still work — the loop collapses to a single pass.
DEFAULT_VARIANT_POP = 2
DEFAULT_VARIANT_GENS = 2
DEFAULT_VARIANT_CONCURRENCY = 3


def _tier_sort_key(ve: VariantEvolution) -> tuple[int, str]:
    """Sort foundation dimensions before capability dimensions."""
    order = {"foundation": 0, "capability": 1}
    return (order.get(ve.tier, 99), ve.dimension)


def _aggregate_fitness(skill: SkillGenome) -> float:
    """Compute a single fitness number for ranking variants."""
    if skill.pareto_objectives:
        vals = list(skill.pareto_objectives.values())
        return sum(vals) / max(1, len(vals))
    if skill.deterministic_scores:
        vals = list(skill.deterministic_scores.values())
        return sum(vals) / max(1, len(vals))
    return 0.0
