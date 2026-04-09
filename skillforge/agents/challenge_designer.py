"""Challenge Designer — auto-generates evaluation challenges from a specialization.

Uses the Claude Agent SDK ``query()`` with WebSearch enabled (gated by
``config.WEBSEARCH_ENABLED``) to ground challenges in real-world examples of
the specialization domain. Produces 3-5 challenges spanning easy/medium/hard
with distinct verification methods.
"""

from __future__ import annotations

from skillforge.models import Challenge


async def design_challenges(specialization: str, n: int = 3) -> list[Challenge]:
    """Generate ``n`` challenges for the given specialization.

    Implemented in Step 6a.
    """
    raise NotImplementedError
