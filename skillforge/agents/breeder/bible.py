"""Write learning-log entries out to ``bible/findings/`` on disk.

All I/O lives here; the caller just passes in the new entries + run
metadata and expects best-effort persistence. Failures are logged,
never raised — a bible write must not abort an evolution run.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

logger = logging.getLogger("skillforge.agents.breeder.bible")


def _resolve_bible_dir():
    """Look up BIBLE_DIR through the breeder package's namespace.

    The test suite patches ``skillforge.agents.breeder.BIBLE_DIR`` to
    redirect writes to a tmp_path fixture. Reading the attribute fresh
    each call (instead of binding at import time) keeps that patch
    observable after the monolithic module was split into a package.
    """
    from skillforge.agents import breeder as _pkg

    return _pkg.BIBLE_DIR


def publish_findings_to_bible(
    new_entries: list[str],
    run_id: str,
    generation: int,
) -> None:
    """Write new learning-log entries as numbered finding files under bible/findings/.

    Each finding gets its own file following the schema in bible/README.md.
    Also appends a summary line to bible/evolution-log.md.

    Failures here are logged but never raised — we don't want a bible write
    failure to abort an evolution run.
    """
    if not new_entries:
        return

    bible_dir = _resolve_bible_dir()
    findings_dir = bible_dir / "findings"
    try:
        findings_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        logger.exception("bible.findings_dir_mkdir_failed")
        return

    # Determine the next finding number by scanning existing files
    existing_nums = []
    for f in findings_dir.glob("*.md"):
        match = re.match(r"^(\d{3})-", f.name)
        if match:
            existing_nums.append(int(match.group(1)))
    next_num = (max(existing_nums) + 1) if existing_nums else 1

    timestamp = datetime.now(UTC).strftime("%Y-%m-%d")

    for entry in new_entries:
        if not entry or entry.startswith("("):
            # Skip error placeholders
            continue
        slug = _slugify(entry)[:40]
        filename = f"{next_num:03d}-{slug}.md"
        content = _finding_markdown(
            num=next_num,
            title=entry,
            body=entry,
            run_id=run_id,
            generation=generation,
            timestamp=timestamp,
        )
        try:
            (findings_dir / filename).write_text(content)
        except OSError:
            logger.exception("bible.finding_write_failed", extra={"filename": filename})
            continue
        next_num += 1

    # Append to evolution log
    log_path = bible_dir / "evolution-log.md"
    try:
        if log_path.exists():
            existing = log_path.read_text()
        else:
            existing = "# Evolution Log\n\n*Chronological log of all SkillForge evolution runs.*\n\n"
        entry_line = f"- **{timestamp}** — run `{run_id[:8]}` gen {generation}: {len(new_entries)} new finding(s)\n"
        log_path.write_text(existing + entry_line)
    except OSError:
        logger.exception("bible.evolution_log_write_failed")


def _slugify(text: str) -> str:
    """Kebab-case a string for use in a filename."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "untitled"


def _finding_markdown(
    num: int,
    title: str,
    body: str,
    run_id: str,
    generation: int,
    timestamp: str,
) -> str:
    """Render a finding markdown file per bible/README.md schema."""
    short_title = title.split(".")[0][:60] if "." in title else title[:60]
    return f"""# Finding {num:03d}: {short_title}

**Discovered**: {timestamp}
**Evolution Run**: {run_id}
**Generation**: {generation}
**Status**: finding

## Observation

{body}

## Evidence

Automatically extracted from the generation {generation} trait attribution
and trace analysis by the Breeder agent. See run `{run_id}` in the
SkillForge database for the raw scores and traces.

## Mechanism

*To be filled in if this finding replicates across 3+ runs and gets
promoted to a pattern.*

## Recommendation

*To be filled in upon promotion.*
"""
