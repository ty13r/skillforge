"""Journal entries endpoint — reads journal/*.md from disk."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from skillforge.config import ROOT_DIR

router = APIRouter(prefix="/api/journal", tags=["journal"])

JOURNAL_DIR = ROOT_DIR / "journal"


def _parse_entry(path: Path) -> dict:
    """Parse a journal markdown file into structured metadata + body."""
    body = path.read_text(encoding="utf-8")
    slug = path.stem  # e.g. "015-scoring-overhaul-and-frontend-sprint"

    # Extract metadata from the markdown content
    title = slug
    date = None
    duration = None
    participants = None

    for line in body.splitlines():
        if line.startswith("## Entry"):
            # "## Entry #15: The Scoring Overhaul and the Frontend Sprint"
            m = re.match(r"## Entry #(\d+):\s*(.*)", line)
            if m:
                title = m.group(2).strip()
        elif line.startswith("**Date**:"):
            date = line.split(":", 1)[1].strip().rstrip("*")
        elif line.startswith("**Session Duration**:"):
            duration = line.split(":", 1)[1].strip().rstrip("*")
        elif line.startswith("**Participants**:"):
            participants = line.split(":", 1)[1].strip().rstrip("*")

    # Extract entry number from filename
    number_match = re.match(r"(\d+)", slug)
    number = int(number_match.group(1)) if number_match else 0

    return {
        "slug": slug,
        "number": number,
        "title": title,
        "date": date,
        "duration": duration,
        "participants": participants,
        "filename": path.name,
        "body": body,
    }


@router.get("/entries")
async def list_journal_entries() -> list[dict]:
    """Return all journal entries sorted by number descending (newest first)."""
    if not JOURNAL_DIR.exists():
        return []
    entries = []
    for path in sorted(JOURNAL_DIR.glob("*.md"), reverse=True):
        try:
            entries.append(_parse_entry(path))
        except (OSError, UnicodeDecodeError, ValueError):
            # Skip malformed entries — the journal index should never
            # crash because a single file is unreadable.
            continue
    return entries


@router.get("/entry/{slug}")
async def get_journal_entry(slug: str) -> dict:
    """Return a single journal entry by slug."""
    path = JOURNAL_DIR / f"{slug}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"journal entry not found: {slug}")
    return _parse_entry(path)
