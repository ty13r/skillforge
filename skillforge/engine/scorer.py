"""Async wrapper around scripts/scoring/composite_scorer.py.

Runs the sync composite_score() in a thread pool so the evolution engine
can await it without blocking the event loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger("skillforge.engine.scorer")

# Ensure scripts/scoring is importable.
_SCRIPTS_SCORING = Path(__file__).resolve().parents[2] / "scripts" / "scoring"
if str(_SCRIPTS_SCORING) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_SCORING))

# Deferred import — pulled in at call time so the path insertion above has
# already taken effect by the time the module is resolved.
def _get_composite_score():
    from composite_scorer import composite_score  # type: ignore[import]
    return composite_score


_FALLBACK: dict = {
    "l0": {"score": 0.0, "passed": False, "objectives": {}},
    "compile": {"compiles": False, "warnings": 0, "errors": ["scorer error"]},
    "ast": {"functions": 0, "impl_coverage": 0.0, "pipe_density": 0.0, "loc": 0, "score": 0.0},
    "template": {"modern": 0, "legacy": 0, "score": 0.0},
    "brevity": 0.0,
    "behavioral": None,
    "composite": 0.0,
    "weights": {},
}


async def score_competitor(
    *,
    family_slug: str,
    challenge_id: str,
    challenge_path: str | Path | None = None,
    challenge_data: dict | None = None,
    output_files: dict[str, str],
    run_behavioral: bool = True,
) -> dict:
    """Score a competitor's output using the composite scorer.

    Runs the sync composite_score() in a thread pool to avoid blocking the
    event loop (the scorer does file I/O and subprocess calls).

    Args:
        family_slug: e.g. "elixir-phoenix-liveview"
        challenge_id: used only for log messages (e.g. "hard-07")
        challenge_path: path to the challenge JSON file (if on disk)
        challenge_data: challenge dict to write to a temp file (for engine runs
            where the challenge was generated in-memory)
        output_files: {relative_path: code_content} produced by the competitor
        run_behavioral: whether to run ExUnit behavioral tests (Phase 2+)

    Returns:
        Full breakdown dict from composite_score(), or a zero-filled fallback
        dict on any error.
    """

    def _run() -> dict:
        composite_score = _get_composite_score()

        # Resolve challenge path — use on-disk file or write a temp file
        resolved_path: Path
        tmp_dir = None
        try:
            if challenge_path is not None:
                resolved_path = Path(challenge_path)
            elif challenge_data is not None:
                tmp_dir = tempfile.mkdtemp(prefix="skld-scorer-")
                resolved_path = Path(tmp_dir) / f"{challenge_id}.json"
                resolved_path.write_text(json.dumps(challenge_data))
            else:
                # No challenge info — L0 scorer will return 0 but compile/AST/behavioral still run
                tmp_dir = tempfile.mkdtemp(prefix="skld-scorer-")
                resolved_path = Path(tmp_dir) / "empty.json"
                resolved_path.write_text("{}")

            return composite_score(
                family_slug,
                resolved_path,
                output_files,
                run_behavioral_tests=run_behavioral,
            )
        finally:
            if tmp_dir is not None:
                import shutil
                shutil.rmtree(tmp_dir, ignore_errors=True)

    try:
        result: dict = await asyncio.to_thread(_run)
        logger.debug(
            "scored %s/%s → composite=%.4f",
            family_slug,
            challenge_id,
            result.get("composite", 0.0),
        )
        return result
    except Exception:
        logger.exception(
            "composite_score failed for %s/%s — returning zero fallback",
            family_slug,
            challenge_id,
        )
        return dict(_FALLBACK)


def scores_to_pareto_objectives(scores: dict) -> dict[str, float]:
    """Convert composite scorer output to pareto_objectives format.

    Extracts scalar floats from the nested breakdown so the result can be
    assigned directly to SkillGenome.pareto_objectives.

    Returns a dict like:
        {"composite": 0.72, "l0": 0.85, "compile": 1.0, "ast": 0.60,
         "template": 1.0, "brevity": 0.80, "behavioral": 0.90}

    Behavioral is omitted when the scorer did not run behavioral tests
    (i.e. when scores["behavioral"] is None).
    """
    objectives: dict[str, float] = {
        "composite": float(scores.get("composite", 0.0)),
        "l0": float((scores.get("l0") or {}).get("score", 0.0)),
        "compile": 1.0 if (scores.get("compile") or {}).get("compiles", False) else 0.0,
        "ast": float((scores.get("ast") or {}).get("score", 0.0)),
        "template": float((scores.get("template") or {}).get("score", 0.0)),
        "brevity": float(scores.get("brevity", 0.0)),
    }
    behavioral = scores.get("behavioral")
    if behavioral is not None:
        objectives["behavioral"] = float(behavioral.get("score", 0.0))
    return objectives
