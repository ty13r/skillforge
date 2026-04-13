#!/usr/bin/env python3
"""One-time script: archive the 18 deep-dive outputs from /tmp/skld-level-test/
into the dispatch_transcripts table so they survive OS cleanup.

Usage:
    uv run python scripts/scoring/archive_deep_dive.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from skillforge.db.database import init_db
from skillforge.db.queries import save_transcript

DEEP_DIVE_DIR = Path("/tmp/skld-level-test")

# Map directory names to structured metadata
# Format: {source}-{challenge} → (model, skill_variant, challenge_id)
def parse_source_dir(name: str) -> tuple[str, str | None, str]:
    """Parse directory name like 'sonnet-noskill-hard-07' into components."""
    parts = name.split("-")
    # Model: sonnet or opus
    model_short = parts[0]
    model = f"claude-{model_short}-4-6" if model_short == "sonnet" else f"claude-{model_short}-4-6"

    # Skill variant: noskill, v1-skill, v2-skill
    if parts[1] == "noskill":
        skill_variant = None
        challenge_tier = parts[2]
        challenge_num = parts[3]
    else:
        # v1-skill or v2-skill
        skill_variant = f"{parts[1]}-{parts[2]}"  # "v1-skill" or "v2-skill"
        challenge_tier = parts[3]
        challenge_num = parts[4]

    challenge_id = f"elixir-phoenix-liveview-{challenge_tier}-{challenge_num}"
    return model, skill_variant, challenge_id


def collect_files(source_dir: Path) -> dict[str, str]:
    """Read all .ex/.exs files from a source directory into a dict."""
    files = {}
    for f in sorted(source_dir.rglob("*")):
        if f.is_file() and f.suffix in (".ex", ".exs"):
            rel = str(f.relative_to(source_dir))
            files[rel] = f.read_text()
    return files


async def main(dry_run: bool = False) -> None:
    if not DEEP_DIVE_DIR.exists():
        print(f"ERROR: {DEEP_DIVE_DIR} does not exist. Nothing to archive.")
        sys.exit(1)

    if not dry_run:
        await init_db()

    source_dirs = sorted(d for d in DEEP_DIVE_DIR.iterdir() if d.is_dir())
    print(f"Found {len(source_dirs)} deep-dive output directories")

    archived = 0
    for source_dir in source_dirs:
        name = source_dir.name
        try:
            model, skill_variant, challenge_id = parse_source_dir(name)
        except (IndexError, ValueError) as e:
            print(f"  SKIP {name}: could not parse ({e})")
            continue

        files = collect_files(source_dir)
        if not files:
            print(f"  SKIP {name}: no .ex/.exs files found")
            continue

        transcript_id = f"deep-dive-{name}"

        if dry_run:
            print(f"  [DRY-RUN] {name} → model={model}, skill={skill_variant}, "
                  f"challenge={challenge_id}, files={list(files.keys())}")
        else:
            await save_transcript(
                id=transcript_id,
                family_slug="elixir-phoenix-liveview",
                challenge_id=challenge_id,
                dispatch_type="deep_dive",
                model=model,
                skill_variant=skill_variant,
                prompt="(deep-dive experiment — prompt not captured)",
                raw_response="(deep-dive experiment — response not captured)",
                extracted_files=files,
                scores={},
                total_tokens=0,
                duration_ms=0,
                created_at="2026-04-12T00:00:00+00:00",
            )
            print(f"  OK {name} → {transcript_id}")

        archived += 1

    print(f"\nArchived {archived} deep-dive outputs"
          + (" (dry run)" if dry_run else " to dispatch_transcripts"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Archive deep-dive outputs to DB")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be archived")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
