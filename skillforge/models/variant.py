"""Variant + VariantEvolution — the atomic unit of v2.0 evolution.

A ``Variant`` is a specialized mini-skill evolved against a single dimension
of a ``SkillFamily`` (e.g., "mock-strategy" for a Python testing family). A
``VariantEvolution`` is the mini-evolution run that produced it (2 pop × 2 gen
× 1 challenge by default).

Two tiers: ``foundation`` (structural decisions, evolved first) and
``capability`` (focused modules, evolved in context of a winning foundation).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from skillforge.models._serde import from_iso, to_iso


@dataclass
class Variant:
    """A single evolved variant within a family's dimension."""

    id: str
    family_id: str
    dimension: str  # e.g., "mock-strategy", "fixture-strategy"
    tier: str  # foundation | capability
    genome_id: str  # points at the underlying SkillGenome
    fitness_score: float = 0.0
    is_active: bool = False  # True for the current winning variant in (family, dimension)
    evolution_id: str | None = None  # the VariantEvolution run that produced it
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict."""
        return {
            "id": self.id,
            "family_id": self.family_id,
            "dimension": self.dimension,
            "tier": self.tier,
            "genome_id": self.genome_id,
            "fitness_score": self.fitness_score,
            "is_active": self.is_active,
            "evolution_id": self.evolution_id,
            "created_at": to_iso(self.created_at),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Variant:
        """Rehydrate from a dict."""
        created_at = from_iso(data.get("created_at"))
        return cls(
            id=data["id"],
            family_id=data["family_id"],
            dimension=data["dimension"],
            tier=data["tier"],
            genome_id=data["genome_id"],
            fitness_score=data.get("fitness_score", 0.0),
            is_active=data.get("is_active", False),
            evolution_id=data.get("evolution_id"),
            created_at=created_at if created_at is not None else datetime.now(UTC),
        )


@dataclass
class VariantEvolution:
    """A mini-evolution run targeting one dimension of a family.

    Child of a parent ``EvolutionRun``. Multiple VariantEvolution records per
    parent run — one per dimension being evolved.
    """

    id: str
    family_id: str
    dimension: str
    tier: str  # foundation | capability
    parent_run_id: str  # the top-level EvolutionRun this mini-evolution belongs to
    population_size: int = 2
    num_generations: int = 2
    status: str = "pending"  # pending | running | complete | failed
    winner_variant_id: str | None = None
    foundation_genome_id: str | None = None  # for capability tier: the winning foundation
    challenge_id: str | None = None  # the focused challenge used for this dimension
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict."""
        return {
            "id": self.id,
            "family_id": self.family_id,
            "dimension": self.dimension,
            "tier": self.tier,
            "parent_run_id": self.parent_run_id,
            "population_size": self.population_size,
            "num_generations": self.num_generations,
            "status": self.status,
            "winner_variant_id": self.winner_variant_id,
            "foundation_genome_id": self.foundation_genome_id,
            "challenge_id": self.challenge_id,
            "created_at": to_iso(self.created_at),
            "completed_at": to_iso(self.completed_at),
        }

    @classmethod
    def from_dict(cls, data: dict) -> VariantEvolution:
        """Rehydrate from a dict."""
        created_at = from_iso(data.get("created_at"))
        return cls(
            id=data["id"],
            family_id=data["family_id"],
            dimension=data["dimension"],
            tier=data["tier"],
            parent_run_id=data["parent_run_id"],
            population_size=data.get("population_size", 2),
            num_generations=data.get("num_generations", 2),
            status=data.get("status", "pending"),
            winner_variant_id=data.get("winner_variant_id"),
            foundation_genome_id=data.get("foundation_genome_id"),
            challenge_id=data.get("challenge_id"),
            created_at=created_at if created_at is not None else datetime.now(UTC),
            completed_at=from_iso(data.get("completed_at")),
        )
