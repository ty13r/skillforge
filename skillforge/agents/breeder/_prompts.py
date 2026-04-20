"""Breeding-instruction prompt builders.

Pure string-templating functions — no LLM calls, no I/O. The actual
breeding happens in ``main.breed()`` which feeds these prompts to the
Spawner.
"""

from __future__ import annotations

from skillforge.agents.breeder._ranking import _aggregate_fitness
from skillforge.models import SkillGenome


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

