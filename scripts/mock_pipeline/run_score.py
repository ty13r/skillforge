"""Thin subprocess wrapper around a family's ``evaluation/score.py``.

Invokes the score.py process, parses its JSON output, and returns a small
summary dict. Used by the main session to score each Competitor output
directory against a challenge.

Usage:
    uv run python scripts/mock_pipeline/run_score.py \\
        --family-dir taxonomy/elixir/elixir-phoenix-liveview \\
        --challenge-path .../challenges/medium/elixir-phoenix-liveview-medium-05.json \\
        --output-dir /tmp/skld-comp-abc123

Prints a JSON summary:
    {"score": 0.85, "passed": true, "diagnostics": [...], "raw": {...}}
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_score(
    family_dir: Path,
    challenge_path: Path,
    output_dir: Path,
) -> dict:
    score_script = family_dir / "evaluation" / "score.py"
    if not score_script.exists():
        return {
            "score": 0.0,
            "passed": False,
            "diagnostics": [f"score.py not found at {score_script}"],
            "raw": {},
        }

    proc = subprocess.run(
        [
            sys.executable,
            str(score_script),
            "--challenge",
            str(challenge_path),
            "--output",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if proc.returncode != 0:
        return {
            "score": 0.0,
            "passed": False,
            "diagnostics": [
                f"score.py exit={proc.returncode}",
                proc.stderr.strip()[:500] if proc.stderr else "",
            ],
            "raw": {"stdout": proc.stdout, "stderr": proc.stderr},
        }

    try:
        raw = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        return {
            "score": 0.0,
            "passed": False,
            "diagnostics": [f"score.py output not JSON: {e}"],
            "raw": {"stdout": proc.stdout[:500]},
        }

    return {
        "score": float(raw.get("score", 0.0)),
        "passed": bool(raw.get("passed", False)),
        "diagnostics": list(raw.get("diagnostics", [])),
        "raw": raw,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family-dir", required=True, type=Path)
    parser.add_argument("--challenge-path", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    result = run_score(args.family_dir, args.challenge_path, args.output_dir)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
