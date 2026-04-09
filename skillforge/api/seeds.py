"""Seed library endpoint — returns the 15 curated Gen 0 Skills as JSON.

These are the same seeds loaded into the DB by `seed_loader` at boot.
Returning them directly from the in-memory module is faster than round-
tripping through SQLite and gives the Registry frontend a single fetch
for both metadata and content.
"""

from __future__ import annotations

from fastapi import APIRouter

from skillforge.seeds import SEED_SKILLS

router = APIRouter(prefix="/api/seeds", tags=["seeds"])


@router.get("")
async def list_seeds() -> list[dict]:
    """Return every curated seed with title, category, difficulty, traits, and slug."""
    return [
        {
            "id": s["id"],
            "slug": s["slug"],
            "title": s["title"],
            "category": s["category"],
            "difficulty": s["difficulty"],
            "traits": s.get("traits", []),
            "meta_strategy": s.get("meta_strategy", ""),
            "description": s["frontmatter"].get("description", ""),
        }
        for s in SEED_SKILLS
    ]
