"""SkillFamily — a named lineage that groups variants sharing a specialization.

Introduced in v2.0. A family lives inside the taxonomy (``domain_id`` / ``focus_id``
/ ``language_id`` point into ``TaxonomyNode`` rows) and owns the current best
assembled composite skill (``best_assembly_id``) plus all the variants that
have been evolved to fit its specialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from skillforge.models._serde import from_iso, to_iso


@dataclass
class SkillFamily:
    """A family of related variants pursuing the same specialization.

    ``decomposition_strategy`` is one of ``atomic`` | ``molecular`` — set by
    the Taxonomist at classification time.
    """

    id: str
    slug: str  # kebab-case, unique
    label: str
    specialization: str
    domain_id: str | None = None
    focus_id: str | None = None
    language_id: str | None = None
    tags: list[str] = field(default_factory=list)
    decomposition_strategy: str = "molecular"  # atomic | molecular
    best_assembly_id: str | None = None  # SkillGenome id of the winning composite
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict."""
        return {
            "id": self.id,
            "slug": self.slug,
            "label": self.label,
            "specialization": self.specialization,
            "domain_id": self.domain_id,
            "focus_id": self.focus_id,
            "language_id": self.language_id,
            "tags": list(self.tags),
            "decomposition_strategy": self.decomposition_strategy,
            "best_assembly_id": self.best_assembly_id,
            "created_at": to_iso(self.created_at),
        }

    @classmethod
    def from_dict(cls, data: dict) -> SkillFamily:
        """Rehydrate from a dict."""
        created_at = from_iso(data.get("created_at"))
        return cls(
            id=data["id"],
            slug=data["slug"],
            label=data["label"],
            specialization=data["specialization"],
            domain_id=data.get("domain_id"),
            focus_id=data.get("focus_id"),
            language_id=data.get("language_id"),
            tags=list(data.get("tags", [])),
            decomposition_strategy=data.get("decomposition_strategy", "molecular"),
            best_assembly_id=data.get("best_assembly_id"),
            created_at=created_at if created_at is not None else datetime.now(UTC),
        )
