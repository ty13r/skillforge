"""Research browser endpoint — reads docs/research/narrative/, docs/research/audits/,
and docs/research/external-papers/ from disk.

Mirrors the shape of ``skillforge/api/bible.py`` so the frontend can reuse the
categorized-sidebar + reader-pane pattern.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from skillforge.config import DOCS_DIR

router = APIRouter(prefix="/api/research", tags=["research"])

RESEARCH_DIR = DOCS_DIR / "research"

_ALLOWED_CATEGORIES = {"narrative", "audits", "external-papers"}


def _first_heading(body: str, fallback: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped.lstrip("# ").strip()
    return fallback


def _load_dir(category: str, subdir: Path) -> list[dict]:
    if not subdir.exists():
        return []
    entries: list[dict] = []
    for path in sorted(subdir.glob("*.md")):
        body = path.read_text(encoding="utf-8")
        title = _first_heading(body, path.stem.replace("-", " ").title())
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


def _load_external_papers(subdir: Path) -> list[dict]:
    """External papers are PDFs; surface filenames + download links (no body)."""
    if not subdir.exists():
        return []
    entries: list[dict] = []
    for path in sorted(subdir.iterdir()):
        if path.is_file() and path.suffix.lower() == ".pdf":
            entries.append(
                {
                    "slug": f"external-papers/{path.stem}",
                    "category": "external-papers",
                    "title": path.stem.replace("-", " ").replace("_", " "),
                    "filename": path.name,
                    "body": (
                        f"# {path.name}\n\n"
                        "External paper referenced by SKLD. "
                        f"Source file: `docs/research/external-papers/{path.name}` "
                        "in the [GitHub repo](https://github.com/ty13r/skillforge/tree/main/docs/research/external-papers).\n"
                    ),
                }
            )
    return entries


@router.get("/entries")
async def list_research_entries() -> dict:
    """Return all research entries grouped by category."""
    return {
        "narrative": _load_dir("narrative", RESEARCH_DIR / "narrative"),
        "audits": _load_dir("audits", RESEARCH_DIR / "audits"),
        "external_papers": _load_external_papers(RESEARCH_DIR / "external-papers"),
    }


@router.get("/entry/{category}/{slug}")
async def get_research_entry(category: str, slug: str) -> dict:
    if category not in _ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"unknown category: {category}")
    if category == "external-papers":
        papers = _load_external_papers(RESEARCH_DIR / "external-papers")
        for entry in papers:
            if entry["slug"] == f"external-papers/{slug}":
                return entry
        raise HTTPException(status_code=404, detail=f"paper not found: {slug}")
    path = RESEARCH_DIR / category / f"{slug}.md"
    if not path.exists():
        raise HTTPException(
            status_code=404, detail=f"entry not found: {category}/{slug}"
        )
    body = path.read_text(encoding="utf-8")
    return {
        "slug": f"{category}/{slug}",
        "category": category,
        "title": _first_heading(body, slug.replace("-", " ").title()),
        "body": body,
    }
