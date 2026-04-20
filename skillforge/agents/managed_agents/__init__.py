"""Thin typed wrapper around the Anthropic Managed Agents + Skills beta APIs.

Hides SDK quirks discovered during the Step 0 smoke test
(``scripts/smoke_skill_upload.py``):

- Skill uploads must place ``SKILL.md`` inside a top-level folder that
  matches the frontmatter ``name:`` field; a bare filename returns 400.
- ``beta.skills.delete()`` does NOT auto-clean versions — the 3-step
  dance is required (``versions.list`` → ``versions.delete`` per
  version → ``skills.delete``).
- Anthropic ships built-in skills (xlsx/pptx/pdf/docx) with
  ``source="anthropic"``. Cleanup must NEVER attempt to delete them —
  the guard is enforced in ``skills.archive_skill``.
- ``beta.sessions.events.stream()`` is unusable: the SDK routes it
  through the Messages API SSE decoder which silently filters out every
  Managed Agents event type. ``sessions.iter_session_events`` polls
  ``events.list(order="asc")`` instead.
- Tool name in ``agent_toolset_20260401`` is ``write`` (not
  ``write_file``). Input shape: ``{"file_path": str, "content": str}``.
  Bash tool input is ``{"command": str}``.
- Token usage path: ``event.model_usage.input_tokens`` /
  ``.output_tokens`` / ``.cache_creation_input_tokens`` /
  ``.cache_read_input_tokens`` on ``span.model_request_end`` events.
- Session runtime cost = (``status_idle.processed_at`` -
  ``status_running.processed_at``) hours × $0.08.

This package is the ONLY place that imports beta resource paths from
the ``anthropic`` SDK. ``competitor_managed`` and the engine consume
only the wrapper's typed return values.

Public surface is re-exported here so import sites keep reading
``from skillforge.agents import managed_agents`` and calling
``managed_agents.upload_skill(...)`` etc.
"""

from __future__ import annotations

from skillforge.agents.managed_agents._constants import (
    ANTHROPIC_SKILL_SOURCE,
    MANAGED_AGENTS_BETA,
    SESSION_RUNTIME_USD_PER_HOUR,
    SKILLS_BETA,
    make_client,
)
from skillforge.agents.managed_agents.agents import archive_agent, create_competitor_agent
from skillforge.agents.managed_agents.environments import (
    archive_environment,
    create_environment,
)
from skillforge.agents.managed_agents.output import (
    _normalize_output_path,
    compute_session_runtime_hours,
    compute_token_usage,
    extract_written_files,
    session_was_skill_loaded,
)
from skillforge.agents.managed_agents.sessions import (
    archive_session,
    create_session,
    iter_session_events,
    send_user_message,
)
from skillforge.agents.managed_agents.skills import (
    _extract_skill_name_from_md,
    archive_skill,
    archive_skill_safe,
    upload_skill,
)

__all__ = [
    # Constants + client
    "ANTHROPIC_SKILL_SOURCE",
    "MANAGED_AGENTS_BETA",
    "SESSION_RUNTIME_USD_PER_HOUR",
    "SKILLS_BETA",
    "make_client",
    # Environments
    "create_environment",
    "archive_environment",
    # Skills
    "upload_skill",
    "archive_skill",
    "archive_skill_safe",
    # Agents
    "create_competitor_agent",
    "archive_agent",
    # Sessions
    "create_session",
    "archive_session",
    "send_user_message",
    "iter_session_events",
    # Output introspection
    "extract_written_files",
    "compute_token_usage",
    "compute_session_runtime_hours",
    "session_was_skill_loaded",
    # Private helpers re-exported for test access
    "_extract_skill_name_from_md",
    "_normalize_output_path",
]
