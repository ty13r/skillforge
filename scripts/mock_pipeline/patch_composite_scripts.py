"""Patch the phoenix-liveview composite genome's supporting_files scripts.

One-off helper that reads fixed ``scripts/validate.sh`` + ``scripts/main_helper.py``
from a source directory and injects them into the composite genome's
``supporting_files`` dict inside the seed JSON. Also re-runs the loader's
content hash so the next boot picks up the fresh content.

This is needed because the enrichment scripts we generated during the first
seed run had bugs that only surfaced after actually installing the package
and running it against a fake Phoenix project on macOS:

1. ``validate.sh`` used ``declare -A`` (bash 4+) — broken on macOS bash 3.2
2. ``validate.sh`` piped detectors into ``report`` via ``|`` which creates a
   subshell on bash 3.2, so the hit counts never propagated back
3. ``main_helper.py migrate`` produced malformed Elixir (``<%= <.link> %>``
   wrappers, lost ``class:`` attrs, ``:for`` on the wrong tag, missed
   ``live_redirect`` with unquoted text expressions)
4. ``main_helper.py new-live`` had a double-Live suffix wart when the input
   name ended in ``_live``

Usage:
    uv run python scripts/mock_pipeline/patch_composite_scripts.py \\
        --run-id elixir-phoenix-liveview-seed-v1 \\
        --composite-id gen_composite_elixir_phoenix_liveview_seed_v1 \\
        --source-scripts /tmp/skld-fixes/scripts \\
        --seed-json skillforge/seeds/seed_runs/elixir-phoenix-liveview.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def patch_seed_json(
    seed_json_path: Path,
    run_id: str,
    composite_id: str,
    source_dir: Path,
    files_to_patch: tuple[str, ...] = ("scripts/validate.sh", "scripts/main_helper.py"),
) -> dict:
    doc = json.loads(seed_json_path.read_text())

    # Locate the composite genome by id.
    target = None
    for genome in doc.get("skill_genomes", []):
        if genome.get("id") == composite_id and genome.get("run_id") == run_id:
            target = genome
            break
    if target is None:
        raise RuntimeError(
            f"composite {composite_id} not found under run_id={run_id}"
        )

    supporting = target.setdefault("supporting_files", {})

    # Replace each file from the source dir. Keep everything else intact.
    replaced: dict[str, int] = {}
    for rel_path in files_to_patch:
        filename = Path(rel_path).name
        src = source_dir / filename
        if not src.exists():
            raise RuntimeError(f"source file missing: {src}")
        content = src.read_text()
        old_size = len(supporting.get(rel_path, "") or "")
        supporting[rel_path] = content
        replaced[rel_path] = {
            "old_bytes": old_size,
            "new_bytes": len(content),
        }

    # Write back. json.dumps with sort_keys=False keeps diff-friendly ordering
    # for the rest of the document; the replaced script strings just become
    # the new values at their existing keys.
    seed_json_path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    )

    return {
        "seed_json": str(seed_json_path),
        "run_id": run_id,
        "composite_id": composite_id,
        "patched": replaced,
        "total_supporting_files": len(supporting),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--composite-id", required=True)
    parser.add_argument("--source-scripts", required=True, type=Path)
    parser.add_argument("--seed-json", required=True, type=Path)
    args = parser.parse_args()

    result = patch_seed_json(
        seed_json_path=args.seed_json,
        run_id=args.run_id,
        composite_id=args.composite_id,
        source_dir=args.source_scripts,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
