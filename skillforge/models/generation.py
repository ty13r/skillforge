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

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict, including nested dataclasses."""
        return {
            "number": self.number,
            "skills": [s.to_dict() for s in self.skills],
            "results": [r.to_dict() for r in self.results],
            "pareto_front": self.pareto_front,
            "breeding_report": self.breeding_report,
            "learning_log_entries": self.learning_log_entries,
            "best_fitness": self.best_fitness,
            "avg_fitness": self.avg_fitness,
            "trait_survival": self.trait_survival,
            "trait_emergence": self.trait_emergence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Generation:
        """Rehydrate from a dict, including nested dataclasses."""
        return cls(
            number=data["number"],
            skills=[SkillGenome.from_dict(s) for s in data.get("skills", [])],
            results=[CompetitionResult.from_dict(r) for r in data.get("results", [])],
            pareto_front=data.get("pareto_front", []),
            breeding_report=data.get("breeding_report", ""),
            learning_log_entries=data.get("learning_log_entries", []),
            best_fitness=data.get("best_fitness", 0.0),
            avg_fitness=data.get("avg_fitness", 0.0),
            trait_survival=data.get("trait_survival", {}),
            trait_emergence=data.get("trait_emergence", []),
        )
