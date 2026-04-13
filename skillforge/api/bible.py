"""Bible browser endpoint — reads bible/patterns/ and bible/findings/ from disk."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from skillforge.config import BIBLE_DIR

router = APIRouter(prefix="/api/bible", tags=["bible"])


def _load_dir(category: str, subdir: Path) -> list[dict]:
    if not subdir.exists():
        return []
    entries = []
    for path in sorted(subdir.glob("*.md")):
        body = path.read_text(encoding="utf-8")
        # Extract the first h1 as title, fall back to filename stem
        title = path.stem.replace("-", " ").title()
        for line in body.splitlines():
            if line.startswith("# "):
                title = line.lstrip("# ").strip()
                break
        entries.append(
            {
                "slug": f"{category}/{path.stem}",
                "category": category,
                "title": title,
                "filename": path.name,
                "body": body,
            }
        )
    return entries


def _load_books(bible_dir: Path) -> list[dict]:
    """Load top-level book-of-*.md files as a 'books' category."""
    entries = []
    for path in sorted(bible_dir.glob("book-of-*.md")):
        body = path.read_text(encoding="utf-8")
        title = path.stem.replace("-", " ").title()
        for line in body.splitlines():
            if line.startswith("# "):
                title = line.lstrip("# ").strip()
                break
        entries.append(
            {
                "slug": f"books/{path.stem}",
                "category": "books",
                "title": title,
                "filename": path.name,
                "body": body,
            }
        )
    return entries


@router.get("/entries")
async def list_bible_entries() -> dict:
    """Return all bible entries grouped by category."""
    books = _load_books(BIBLE_DIR)
    patterns = _load_dir("patterns", BIBLE_DIR / "patterns")
    findings = _load_dir("findings", BIBLE_DIR / "findings")
    anti = _load_dir("anti-patterns", BIBLE_DIR / "anti-patterns")
    return {
        "books": books,
        "patterns": patterns,
        "findings": findings,
        "anti_patterns": anti,
    }


@router.get("/entry/{category}/{slug}")
async def get_bible_entry(category: str, slug: str) -> dict:
    allowed = {"patterns", "findings", "anti-patterns", "books"}
    if category not in allowed:
        raise HTTPException(status_code=400, detail=f"unknown category: {category}")
    if category == "books":
        path = BIBLE_DIR / f"{slug}.md"
    else:
        path = BIBLE_DIR / category / f"{slug}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"entry not found: {category}/{slug}")
    body = path.read_text(encoding="utf-8")
    title = slug.replace("-", " ").title()
    for line in body.splitlines():
        if line.startswith("# "):
            title = line.lstrip("# ").strip()
            break
    return {
        "slug": f"{category}/{slug}",
        "category": category,
        "title": title,
        "body": body,
    }
