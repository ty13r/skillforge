"""Competitor agent lifecycle — create / archive beta agents."""

from __future__ import annotations

import contextlib
from typing import Any

from anthropic import AsyncAnthropic

from skillforge.agents.managed_agents._constants import MANAGED_AGENTS_BETA

# ---------------------------------------------------------------------------
# Agent lifecycle
# ---------------------------------------------------------------------------


async def create_competitor_agent(
    client: AsyncAnthropic,
    *,
    name: str,
    model: str,
    system_prompt: str,
    skill_id: str | None = None,
) -> str:
    """Create a Managed Agent for one competitor run.

    The agent is configured with the standard ``agent_toolset_20260401``
    (bash/edit/read/write/glob/grep/web_fetch/web_search) and an optional
    custom skill linked via the ``skills`` field.

    The Advisor Strategy (``advisor_20260301``) is intentionally NOT
    wired here — Step 0 confirmed it's not yet supported in the SDK or
    on our beta access. When it lands, add a second tool entry behind a
    ``COMPETITOR_ADVISOR`` flag.
    """
    kwargs: dict[str, Any] = {
        "name": name,
        "model": model,
        "system": system_prompt,
        "tools": [{"type": "agent_toolset_20260401"}],
        "betas": [MANAGED_AGENTS_BETA],
    }
    if skill_id is not None:
        # BetaManagedAgentsCustomSkillParams shape:
        # {"skill_id": str, "type": "custom", "version": Optional[str]}
        # Empirical errors during the e2e smoke caught two prior shape
        # mistakes: type="skill" (must be "custom"), id=... (must be
        # skill_id=...). Both surfaced as 400 invalid_request_error.
        kwargs["skills"] = [{"skill_id": skill_id, "type": "custom"}]
    resp = await client.beta.agents.create(**kwargs)
    return resp.id


async def archive_agent(client: AsyncAnthropic, agent_id: str) -> None:
    """Best-effort agent teardown."""
    with contextlib.suppress(Exception):
        await client.beta.agents.archive(agent_id, betas=[MANAGED_AGENTS_BETA])


