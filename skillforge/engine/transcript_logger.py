from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING
from uuid import uuid4

from skillforge.db.queries import save_transcript

if TYPE_CHECKING:
    from skillforge.models.competition import CompetitionResult

logger = logging.getLogger("skillforge.engine.transcript")


async def log_competitor_dispatch(
    *,
    run_id: str,
    family_slug: str,
    challenge_id: str,
    skill_id: str,
    model: str,
    result: CompetitionResult,
    scores: dict | None = None,
    duration_ms: int = 0,
) -> None:
    """Persist a competitor dispatch to the transcript table.

    Best-effort — never raises. Errors are logged.
    """
    try:
        tx_id = f"tx_{uuid4().hex[:12]}"

        # Extract prompt from trace if available (first user message)
        prompt = ""
        for event in result.trace:
            if isinstance(event, dict) and event.get("role") == "user":
                content = event.get("content", "")
                if isinstance(content, str):
                    prompt = content
                    break
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            prompt = block.get("text", "")
                            break
                    if prompt:
                        break

        # Serialize trace as raw_response
        try:
            raw_response = json.dumps(result.trace)
        except (TypeError, ValueError):
            raw_response = str(result.trace)

        # Extract total_tokens from cost_breakdown if present
        total_tokens = 0
        cb = result.cost_breakdown
        if cb:
            input_tok = cb.get("input_tokens", 0) or 0
            output_tok = cb.get("output_tokens", 0) or 0
            total_tokens = int(input_tok) + int(output_tok)

        await save_transcript(
            id=tx_id,
            family_slug=family_slug,
            challenge_id=challenge_id,
            run_id=run_id,
            dispatch_type="competitor",
            model=model,
            skill_variant=skill_id,
            prompt=prompt,
            raw_response=raw_response,
            extracted_files=result.output_files,
            scores=scores,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
        )
    except Exception:
        logger.exception(
            "Failed to log competitor dispatch tx for run=%s challenge=%s skill=%s",
            run_id,
            challenge_id,
            skill_id,
        )
