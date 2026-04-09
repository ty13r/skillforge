"""Generation — one cycle of compete → evaluate → select → breed → mutate."""

from __future__ import annotations

from dataclasses import dataclass, field

from skillforge.models.competition import CompetitionResult
from skillforge.models.genome import SkillGenome


@dataclass
class Generation:
    """Single generation of the evolution loop."""

    number: int
    skills: list[SkillGenome] = field(default_factory=list)
    results: list[CompetitionResult] = field(default_factory=list)
    pareto_front: list[str] = field(default_factory=list)  # SkillGenome IDs
    breeding_report: str = ""
    learning_log_entries: list[str] = field(default_factory=list)
    best_fitness: float = 0.0
    avg_fitness: float = 0.0
    trait_survival: dict[str, bool] = field(default_factory=dict)
    trait_emergence: list[str] = field(default_factory=list)
