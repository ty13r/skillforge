"""EvolutionRun — a top-level evolution session, domain or meta mode."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from skillforge.models.challenge import Challenge
from skillforge.models.generation import Generation
from skillforge.models.genome import SkillGenome


@dataclass
class EvolutionRun:
    """A complete evolution run from specialization to exported Skill."""

    id: str
    mode: str  # "domain" | "meta"
    specialization: str
    population_size: int = 5
    num_generations: int = 3
    challenges: list[Challenge] = field(default_factory=list)
    generations: list[Generation] = field(default_factory=list)
    learning_log: list[str] = field(default_factory=list)
    status: str = "pending"  # pending | running | complete | failed
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    best_skill: SkillGenome | None = None
    pareto_front: list[SkillGenome] = field(default_factory=list)
    total_cost_usd: float = 0.0
