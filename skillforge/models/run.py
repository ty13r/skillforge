"""EvolutionRun — a top-level evolution session, domain or meta mode."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from skillforge.models._serde import from_iso, to_iso
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
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    best_skill: SkillGenome | None = None
    pareto_front: list[SkillGenome] = field(default_factory=list)
    total_cost_usd: float = 0.0
    max_budget_usd: float = 10.0
    failure_reason: str | None = None

    # v2.0: taxonomy + evolution mode
    family_id: str | None = None
    evolution_mode: str = "molecular"  # molecular | atomic

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict, including all nested dataclasses and datetimes."""
        return {
            "id": self.id,
            "mode": self.mode,
            "specialization": self.specialization,
            "population_size": self.population_size,
            "num_generations": self.num_generations,
            "challenges": [c.to_dict() for c in self.challenges],
            "generations": [g.to_dict() for g in self.generations],
            "learning_log": self.learning_log,
            "status": self.status,
            "created_at": to_iso(self.created_at),
            "completed_at": to_iso(self.completed_at),
            "best_skill": self.best_skill.to_dict() if self.best_skill is not None else None,
            "pareto_front": [s.to_dict() for s in self.pareto_front],
            "total_cost_usd": self.total_cost_usd,
            "max_budget_usd": self.max_budget_usd,
            "failure_reason": self.failure_reason,
            "family_id": self.family_id,
            "evolution_mode": self.evolution_mode,
        }

    @classmethod
    def from_dict(cls, data: dict) -> EvolutionRun:
        """Rehydrate from a dict, including all nested dataclasses and datetimes."""
        best_skill_data = data.get("best_skill")
        return cls(
            id=data["id"],
            mode=data["mode"],
            specialization=data["specialization"],
            population_size=data.get("population_size", 5),
            num_generations=data.get("num_generations", 3),
            challenges=[Challenge.from_dict(c) for c in data.get("challenges", [])],
            generations=[Generation.from_dict(g) for g in data.get("generations", [])],
            learning_log=data.get("learning_log", []),
            status=data.get("status", "pending"),
            created_at=from_iso(data.get("created_at")),
            completed_at=from_iso(data.get("completed_at")),
            best_skill=SkillGenome.from_dict(best_skill_data) if best_skill_data is not None else None,
            pareto_front=[SkillGenome.from_dict(s) for s in data.get("pareto_front", [])],
            total_cost_usd=data.get("total_cost_usd", 0.0),
            max_budget_usd=data.get("max_budget_usd", 10.0),
            failure_reason=data.get("failure_reason"),
            family_id=data.get("family_id"),
            evolution_mode=data.get("evolution_mode", "molecular"),
        )
