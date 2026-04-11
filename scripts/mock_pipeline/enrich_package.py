"""Enrich a seed-run composite genome with a real distributable package.

Loads generated content from ``/tmp/skld-seed-run/enrichment/`` (or a
caller-supplied dir) and curated test fixtures from the family dir,
merges them into ``composite_genome.supporting_files``, and re-exports
the JSON seed so the prod loader picks them up.

This is the post-hoc "make the seed package rich" step. The production
v2.1 engine is supposed to generate this content natively (Spawner
produces full directory packages per variant, Engineer merges them), but
for each seed pipeline run we dispatch a handful of focused Opus
subagents and bolt the results onto the existing composite.

Family-agnostic: reads fixtures from the caller-supplied family dir and
defaults to a sensible "include everything under test_fixtures/" when no
curated manifest is provided. Each of the 7 lighthouse Elixir families can
either pass ``--fixtures`` as a comma-separated name list or drop a
``.package_manifest.json`` into the family dir with a ``"fixture_names"``
array.

Usage:
    uv run python scripts/mock_pipeline/enrich_package.py \\
        --run-id elixir-ecto-sandbox-test-seed-v1 \\
        --composite-id gen_composite_elixir_ecto_sandbox_test_seed_v1 \\
        --family-slug elixir-ecto-sandbox-test

    # or with explicit curation
    uv run python scripts/mock_pipeline/enrich_package.py \\
        --family-slug elixir-oban-worker \\
        --fixtures "noisy_worker.ex,retry_storm.ex,unique_conflict.ex" \\
        ...

Idempotent — re-running replaces any existing supporting_files entries
with the latest generated content.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import aiosqlite

from skillforge.config import DB_PATH

REPO_ROOT = Path(__file__).resolve().parents[2]

# Canonical enrichment slot map — the rich package shape every composite
# aspires to. Key = relative path in the skill package, value = source
# filename inside the caller-supplied enrichment dir. This is family-
# agnostic: the SAME slots are populated for every family, but the
# subagents that fill them run with family-specific context (research.md +
# README.md) so the content is actually different per family.
ENRICHMENT_MAP = {
    "scripts/validate.sh": "validate.sh",
    "scripts/main_helper.py": "main_helper.py",
    "references/guide.md": "guide.md",
    "references/cheatsheet.md": "cheatsheet.md",
    "references/anti-patterns.md": "anti-patterns.md",
    "assets/starter_primary.ex.template": "starter_primary.ex.template",
    "assets/starter_secondary.ex.template": "starter_secondary.ex.template",
    "assets/migration_checklist.md": "migration_checklist.md",
}

# Per-family curated fixture lists. When a family appears here, only the
# named fixtures are copied into the composite. Otherwise every file in
# the family's test_fixtures/ dir is included. Keep curations focused —
# 4-8 named files per family is the sweet spot.
CURATED_FIXTURES: dict[str, list[str]] = {
    "elixir-phoenix-liveview": [
        "pre_1_7_user_list.ex",            # 1.6 migration target
        "db_in_mount_dashboard.ex",        # DB-in-mount anti-pattern
        "pubsub_unguarded_chat.ex",        # PubSub without connected? guard
        "nested_invoice_form.ex",          # good nested form example
        "multi_antipattern_liveview.ex",   # kitchen-sink anti-patterns
        "navigation_mix_up.ex",            # legacy nav helpers
    ],
}


def load_enrichment_files(source_dir: Path) -> dict[str, str]:
    """Read all generated enrichment files from ``source_dir``.

    Returns a dict mapping target package path -> file contents. Skips
    entries whose source file is missing (partial enrichment is OK).
    """
    out: dict[str, str] = {}
    missing: list[str] = []
    for target_path, source_name in ENRICHMENT_MAP.items():
        src = source_dir / source_name
        if not src.exists():
            missing.append(source_name)
            continue
        out[target_path] = src.read_text()
    if missing:
        print(
            f"[warn] {len(missing)} enrichment source files missing: {missing}",
            file=sys.stderr,
        )
    return out


def _resolve_fixture_names(
    family_slug: str,
    family_dir: Path,
    cli_override: list[str] | None,
) -> list[str] | None:
    """Pick which test fixtures to copy into the composite package.

    Priority:
    1. CLI ``--fixtures`` override (caller knows exactly which ones they want)
    2. ``.package_manifest.json`` in the family dir with ``fixture_names``
    3. ``CURATED_FIXTURES[family_slug]`` constant in this module
    4. None (signals "include everything under test_fixtures/")
    """
    if cli_override:
        return cli_override

    manifest_path = family_dir / ".package_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
            names = manifest.get("fixture_names")
            if isinstance(names, list) and all(isinstance(n, str) for n in names):
                return names
        except (json.JSONDecodeError, OSError) as err:
            print(
                f"[warn] could not read {manifest_path.name}: {err}",
                file=sys.stderr,
            )

    if family_slug in CURATED_FIXTURES:
        return CURATED_FIXTURES[family_slug]

    return None  # include everything


def load_test_fixtures(
    family_slug: str,
    cli_override: list[str] | None = None,
) -> dict[str, str]:
    """Copy the curated (or full) test fixtures from the family dir.

    Returns ``{target_package_path: file_content}``.
    """
    family_dir = REPO_ROOT / "taxonomy" / "elixir" / family_slug
    fixture_dir = family_dir / "test_fixtures"
    if not fixture_dir.exists():
        print(f"[warn] fixture dir not found: {fixture_dir}", file=sys.stderr)
        return {}

    names = _resolve_fixture_names(family_slug, family_dir, cli_override)
    out: dict[str, str] = {}

    if names is None:
        # No curation — include every regular file under test_fixtures/.
        for src in sorted(fixture_dir.iterdir()):
            if src.is_file() and not src.name.startswith("."):
                out[f"test_fixtures/{src.name}"] = src.read_text()
        if not out:
            print(
                f"[warn] test_fixtures/ for {family_slug} is empty",
                file=sys.stderr,
            )
        return out

    for name in names:
        src = fixture_dir / name
        if not src.exists():
            print(f"[warn] fixture not found: {src}", file=sys.stderr)
            continue
        out[f"test_fixtures/{name}"] = src.read_text()
    return out


async def enrich(
    run_id: str,
    composite_id: str,
    family_slug: str,
    enrichment_dir: Path,
    fixtures_override: list[str] | None = None,
) -> dict:
    enrichment = load_enrichment_files(enrichment_dir)
    fixtures = load_test_fixtures(family_slug, cli_override=fixtures_override)
    combined = {**enrichment, **fixtures}

    if not combined:
        raise RuntimeError("No enrichment files loaded — aborting")

    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            "SELECT supporting_files FROM skill_genomes WHERE id = ? AND run_id = ?",
            (composite_id, run_id),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            raise RuntimeError(
                f"Composite {composite_id} not found for run {run_id}"
            )
        try:
            existing: dict = json.loads(row[0]) if row[0] else {}
        except (TypeError, json.JSONDecodeError):
            existing = {}

        merged = {**existing, **combined}

        await conn.execute(
            "UPDATE skill_genomes SET supporting_files = ? "
            "WHERE id = ? AND run_id = ?",
            (json.dumps(merged), composite_id, run_id),
        )
        await conn.commit()

    return {
        "run_id": run_id,
        "composite_id": composite_id,
        "enrichment_files": len(enrichment),
        "fixture_files": len(fixtures),
        "total_files": len(merged),
        "total_bytes": sum(len(v) for v in merged.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--composite-id", required=True)
    parser.add_argument("--family-slug", required=True)
    parser.add_argument(
        "--enrichment-dir",
        default="/tmp/skld-seed-run/enrichment",
        type=Path,
        help="Directory with generated enrichment files (validate.sh, "
        "main_helper.py, guide.md, etc.). Defaults to /tmp/skld-seed-run/"
        "enrichment for fresh runs.",
    )
    parser.add_argument(
        "--fixtures",
        default=None,
        help="Comma-separated list of fixture filenames to include "
        "(overrides in-family manifest and CURATED_FIXTURES constant). "
        "When unset, uses the curation lookup, then falls back to "
        "including every file in test_fixtures/.",
    )
    args = parser.parse_args()

    fixtures_override: list[str] | None = None
    if args.fixtures:
        fixtures_override = [
            name.strip() for name in args.fixtures.split(",") if name.strip()
        ]

    result = asyncio.run(
        enrich(
            run_id=args.run_id,
            composite_id=args.composite_id,
            family_slug=args.family_slug,
            enrichment_dir=args.enrichment_dir,
            fixtures_override=fixtures_override,
        )
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
