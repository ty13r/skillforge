"""Session lifecycle + event iteration + user-message dispatch.

Poll-based iteration intentionally avoids ``events.stream()`` — the SDK
routes that through the Messages API SSE decoder which silently filters
out every Managed Agents event type. See the package docstring for the
smoke-test findings.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic

from skillforge.agents.managed_agents._constants import MANAGED_AGENTS_BETA

# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


async def create_session(
    client: AsyncAnthropic,
    *,
    agent_id: str,
    environment_id: str,
    title: str | None = None,
) -> str:
    """Create a session and return its id."""
    kwargs: dict[str, Any] = {
        "agent": agent_id,
        "environment_id": environment_id,
        "betas": [MANAGED_AGENTS_BETA],
    }
    if title is not None:
        kwargs["title"] = title
    resp = await client.beta.sessions.create(**kwargs)
    return resp.id


async def archive_session(client: AsyncAnthropic, session_id: str) -> None:
    """Best-effort session teardown."""
    with contextlib.suppress(Exception):
        await client.beta.sessions.archive(
            session_id, betas=[MANAGED_AGENTS_BETA]
        )


async def send_user_message(
    client: AsyncAnthropic,
    session_id: str,
    text: str,
) -> None:
    """Send a single ``user.message`` event into a session."""
    await client.beta.sessions.events.send(
        session_id,
        events=[
            {
                "type": "user.message",
                "content": [{"type": "text", "text": text}],
            }
        ],
        betas=[MANAGED_AGENTS_BETA],
    )


# ---------------------------------------------------------------------------
# Event polling — replaces the broken events.stream()
# ---------------------------------------------------------------------------


async def iter_session_events(
    client: AsyncAnthropic,
    session_id: str,
    *,
    deadline_seconds: float = 300.0,
    poll_interval: float = 2.0,
    page_limit: int = 100,
) -> AsyncIterator[dict]:
    """Yield session events as plain dicts until ``session.status_idle`` arrives.

    Polls ``beta.sessions.events.list(order="asc")`` every ``poll_interval``
    seconds. Yields each new event exactly once (deduped by ``id``).
    Stops on the first ``session.status_idle`` event OR when
    ``deadline_seconds`` elapses.

    Why polling instead of ``events.stream()``: the SDK's stream wrapper
    routes through the Anthropic Messages API SSE decoder, which only
    recognizes Messages event names and silently filters out every
    Managed Agents event type. ``events.list()`` returns structured
    ``BetaManagedAgentsSessionEvent`` objects directly. See PLAN-V1.2
    §"Step 0 empirical findings" for the full investigation.
    """
    deadline = time.monotonic() + deadline_seconds
    seen_ids: set[str] = set()
    idle_seen = False

    while time.monotonic() < deadline and not idle_seen:
        page = await client.beta.sessions.events.list(
            session_id,
            limit=page_limit,
            order="asc",
            betas=[MANAGED_AGENTS_BETA],
        )
        async for ev in page:
            ev_id = getattr(ev, "id", None)
            if ev_id is None or ev_id in seen_ids:
                continue
            seen_ids.add(ev_id)
            d = ev.model_dump() if hasattr(ev, "model_dump") else dict(ev)
            yield d
            if d.get("type") == "session.status_idle":
                idle_seen = True
                break

        if idle_seen:
            return
        await asyncio.sleep(poll_interval)


