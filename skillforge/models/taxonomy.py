"""TaxonomyNode — a single node in the Domain → Focus → Language hierarchy.

Introduced in v2.0 to classify SkillFamily records and enable variant reuse
across related skills. Nodes form a tree where ``parent_id`` points up; the
root nodes (``level="domain"``) have ``parent_id=None``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from skillforge.models._serde import from_iso, to_iso


@dataclass
class TaxonomyNode:
    """A single taxonomy node.

    ``level`` is one of: ``domain`` | ``focus`` | ``language``. Hierarchy rules:
    a ``focus`` node must have a ``domain`` parent; a ``language`` node must
    have a ``focus`` parent; a ``domain`` node has no parent.
    """

    id: str
    level: str  # domain | focus | language
    slug: str  # kebab-case, unique within (level, parent_id)
    label: str
    parent_id: str | None = None
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict."""
        return {
            "id": self.id,
            "level": self.level,
            "slug": self.slug,
            "label": self.label,
            "parent_id": self.parent_id,
            "description": self.description,
            "created_at": to_iso(self.created_at),
        }

    @classmethod
    def from_dict(cls, data: dict) -> TaxonomyNode:
        """Rehydrate from a dict."""
        created_at = from_iso(data.get("created_at"))
        return cls(
            id=data["id"],
            level=data["level"],
            slug=data["slug"],
            label=data["label"],
            parent_id=data.get("parent_id"),
            description=data.get("description", ""),
            created_at=created_at if created_at is not None else datetime.now(UTC),
        )
