"""Pinned beta headers, static constants, and the shared client factory.

The constants are called out as a plan-edit event — any version bump
to ``MANAGED_AGENTS_BETA`` / ``SKILLS_BETA`` should land with a journal
entry explaining the upgrade.
"""

from __future__ import annotations

from anthropic import AsyncAnthropic

from skillforge.config import ANTHROPIC_API_KEY

# Pinned per PLAN-V1.2 architectural decision #6. Treat any version
# bump as a plan-edit event, not a silent dependency update.
MANAGED_AGENTS_BETA: str = "managed-agents-2026-04-01"
SKILLS_BETA: str = "skills-2025-10-02"

# Built-in skill source — never delete. Confirmed via Step 0 inspection
# of the four pre-existing Anthropic skills (xlsx/pptx/pdf/docx) on the org.
ANTHROPIC_SKILL_SOURCE = "anthropic"

# $0.08 per session-hour metered while status == running. Mirrors the
# constant in skillforge.config; duplicated here so this module can be
# imported standalone without pulling the whole config tree.
SESSION_RUNTIME_USD_PER_HOUR = 0.08


def make_client(timeout: float = 600.0) -> AsyncAnthropic:
    """Construct an AsyncAnthropic client wired to skillforge config.

    The caller is responsible for closing the client (``await client.close()``)
    or using it as an async context manager.
    """
    return AsyncAnthropic(api_key=ANTHROPIC_API_KEY, timeout=timeout)
