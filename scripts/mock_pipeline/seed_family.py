"""Seed a v2.1 family into the taxonomy + SkillFamily tables. Idempotent.

Reads ``taxonomy/elixir/<family-slug>/family.json`` and ensures the
``(domain, focus, language)`` taxonomy triple exists plus a ``skill_families``
row referencing the triple. No run, no genomes — those belong to ``create_run``.

Usage:
    uv run python scripts/mock_pipeline/seed_family.py \\
        --family-slug elixir-phoenix-liveview

Prints a JSON summary:

    {
      "family_id": "fam_...",
      "taxonomy_node_ids": {"domain": "...", "focus": "...", "language": "..."},
      "taxonomy_path": "development/phoenix-framework/elixir"
    }
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from skillforge.db.queries import (
    get_family_by_slug,
    get_taxonomy_node_by_slug,
    save_skill_family,
    save_taxonomy_node,
)
from skillforge.models import SkillFamily, TaxonomyNode

REPO_ROOT = Path(__file__).resolve().parents[2]


def _now() -> datetime:
    return datetime.now(UTC)


def _title(s: str) -> str:
    return s.replace("-", " ").title()


async def _ensure_node(level: str, slug: str, label: str, parent_id: str | None) -> TaxonomyNode:
    existing = await get_taxonomy_node_by_slug(level, slug, parent_id)
    if existing is not None:
        return existing
    node = TaxonomyNode(
        id=f"tax_{uuid.uuid4().hex[:12]}",
        level=level,
        slug=slug,
        label=label,
        parent_id=parent_id,
        description="",
        created_at=_now(),
    )
    await save_taxonomy_node(node)
    return node


async def _ensure_family(
    slug: str,
    label: str,
    specialization: str,
    domain_id: str,
    focus_id: str,
    language_id: str,
) -> SkillFamily:
    existing = await get_family_by_slug(slug)
    if existing is not None:
        return existing
    family = SkillFamily(
        id=f"fam_{uuid.uuid4().hex[:12]}",
        slug=slug,
        label=label,
        specialization=specialization,
        domain_id=domain_id,
        focus_id=focus_id,
        language_id=language_id,
        tags=[],
        decomposition_strategy="atomic",
        best_assembly_id=None,
        created_at=_now(),
    )
    await save_skill_family(family)
    return family


async def seed_family(family_slug: str) -> dict:
    family_dir = REPO_ROOT / "taxonomy" / "elixir" / family_slug
    family_json = json.loads((family_dir / "family.json").read_text())

    tax = family_json["taxonomy"]
    domain = await _ensure_node("domain", tax["domain"], _title(tax["domain"]), None)
    focus = await _ensure_node("focus", tax["focus"], _title(tax["focus"]), domain.id)
    language = await _ensure_node("language", tax["language"], _title(tax["language"]), focus.id)

    specialization = (
        f"{family_json['name']} - Phoenix 1.7+ LiveView modules with verified routes, "
        "streams, and modern lifecycle idioms"
    )
    family = await _ensure_family(
        slug=family_slug,
        label=family_json["name"],
        specialization=specialization,
        domain_id=domain.id,
        focus_id=focus.id,
        language_id=language.id,
    )

    return {
        "family_id": family.id,
        "taxonomy_node_ids": {
            "domain": domain.id,
            "focus": focus.id,
            "language": language.id,
        },
        "taxonomy_path": f"{tax['domain']}/{tax['focus']}/{tax['language']}",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family-slug", required=True)
    args = parser.parse_args()

    result = asyncio.run(seed_family(args.family_slug))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
