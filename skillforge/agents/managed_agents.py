"""Thin typed wrapper around the Anthropic Managed Agents + Skills beta APIs.

Hides SDK quirks discovered during the Step 0 smoke test
(``scripts/smoke_skill_upload.py``):

- Skill uploads must place ``SKILL.md`` inside a top-level folder; a bare
  ``SKILL.md`` filename returns 400.
- ``beta.skills.delete()`` does NOT auto-clean versions — the 3-step
  dance is required (``versions.list`` → ``versions.delete`` per version
  → ``skills.delete``).
- Anthropic ships built-in skills (xlsx/pptx/pdf/docx) with
  ``source="anthropic"``. Cleanup must NEVER attempt to delete them — the
  guard is enforced here.
- ``beta.sessions.events.stream()`` is unusable: the SDK routes it through
  the Anthropic Messages API SSE decoder which only recognizes
  ``message_start``/``content_block_delta``/etc. and silently filters out
  every Managed Agents event type. We poll ``events.list(order="asc")``
  instead.
- Tool name in ``agent_toolset_20260401`` is ``write`` (not
  ``write_file``). Input shape: ``{"file_path": str, "content": str}``.
  Bash tool input is ``{"command": str}`` only.
- Token usage path: ``event.model_usage.input_tokens`` /
  ``.output_tokens`` / ``.cache_creation_input_tokens`` /
  ``.cache_read_input_tokens`` on ``span.model_request_end`` events.
- Session runtime cost = (``status_idle.processed_at`` -
  ``status_running.processed_at``) hours × $0.08.

This module is the ONLY place that imports beta resource paths from the
``anthropic`` SDK. ``competitor_managed.py`` and the engine consume only
the wrapper's typed return values.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
import time
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from anthropic import AsyncAnthropic

from skillforge.config import ANTHROPIC_API_KEY

# ---------------------------------------------------------------------------
# Beta header constants — pinned per PLAN-V1.2 architectural decision #6.
# Treat any version bump as a plan-edit event, not a silent dependency
# update. Update both the constant and the bump notes in the journal.
# ---------------------------------------------------------------------------

MANAGED_AGENTS_BETA: str = "managed-agents-2026-04-01"
SKILLS_BETA: str = "skills-2025-10-02"

# Built-in skill source — never delete. Confirmed via Step 0 inspection of
# the four pre-existing skills (xlsx/pptx/pdf/docx) on the org.
ANTHROPIC_SKILL_SOURCE = "anthropic"

# $0.08 per session-hour metered while status == running. Mirrors the
# constant in skillforge.config; duplicated here so this module can be
# imported standalone without pulling the whole config tree.
SESSION_RUNTIME_USD_PER_HOUR = 0.08


# ---------------------------------------------------------------------------
# Client construction
# ---------------------------------------------------------------------------


def make_client(timeout: float = 600.0) -> AsyncAnthropic:
    """Construct an AsyncAnthropic client wired to skillforge config.

    The caller is responsible for closing the client (``await client.close()``)
    or using it as an async context manager.
    """
    return AsyncAnthropic(api_key=ANTHROPIC_API_KEY, timeout=timeout)


# ---------------------------------------------------------------------------
# Environment lifecycle
# ---------------------------------------------------------------------------


async def create_environment(
    client: AsyncAnthropic,
    *,
    run_id: str,
    packages: list[str] | None = None,
) -> str:
    """Create a cloud environment with the given pip packages pre-installed.

    Returns the environment id. The caller stores it on the EvolutionRun
    and reuses it across all competitor sessions in that run.
    """
    pkg_list = packages if packages is not None else ["pytest", "ruff"]
    resp = await client.beta.environments.create(
        name=f"sf-run-{run_id[:12]}",
        config={
            "type": "cloud",
            "packages": {
                "type": "packages",
                "pip": pkg_list,
            },
        },
        betas=[MANAGED_AGENTS_BETA],
    )
    return resp.id


async def archive_environment(client: AsyncAnthropic, environment_id: str) -> None:
    """Best-effort environment teardown. Logs and swallows errors.

    Cleanup must never block. The ``leaked_environments`` counterpart
    would go here if we needed bookkeeping; for now we accept the
    leak — environments are cheap and Anthropic GCs them.
    """
    with contextlib.suppress(Exception):
        await client.beta.environments.archive(
            environment_id,
            betas=[MANAGED_AGENTS_BETA],
        )


# ---------------------------------------------------------------------------
# Skill upload + 3-step delete dance
# ---------------------------------------------------------------------------


async def upload_skill(
    client: AsyncAnthropic,
    *,
    name: str,
    skill_md: str,
) -> str:
    """Upload a SKILL.md as a versioned org-level custom skill.

    Two empirical constraints from Step 0:

      1. The file must live inside a top-level folder — passing a bare
         ``SKILL.md`` filename returns ``400 SKILL.md file must be exactly
         in the top-level folder.``
      2. **The folder name must MATCH the ``name:`` field in the SKILL.md
         frontmatter** — surfaced during the live end-to-end smoke. The
         ``name`` argument to this function is therefore IGNORED for the
         folder/upload — we always extract the actual frontmatter name and
         use that. The ``name`` arg is still used as the ``display_title``
         (which can be anything human-readable).

    Returns the new ``skill_id``. The caller is responsible for archiving it
    via :func:`archive_skill` after the session completes.
    """
    folder = _extract_skill_name_from_md(skill_md) or name
    resp = await client.beta.skills.create(
        display_title=name,
        files=[
            (
                f"{folder}/SKILL.md",
                skill_md.encode("utf-8"),
                "text/markdown",
            )
        ],
        betas=[SKILLS_BETA],
    )
    return resp.id


_SKILL_NAME_RE = re.compile(r"^name:\s*(?P<name>[^\s\n]+)\s*$", re.MULTILINE)


def _extract_skill_name_from_md(skill_md: str) -> str | None:
    """Pull the ``name`` field out of a SKILL.md's YAML frontmatter.

    Robust to variations in YAML formatting — uses a simple regex against
    the raw text instead of parsing YAML, because the API's matching is
    string-literal so we want exactly what's in the file. Returns None
    if no name field is found.
    """
    if not skill_md.startswith("---"):
        return None
    try:
        _, fm_block, _ = skill_md.split("---", 2)
    except ValueError:
        return None
    match = _SKILL_NAME_RE.search(fm_block)
    if not match:
        return None
    return match.group("name").strip()


async def archive_skill(client: AsyncAnthropic, skill_id: str) -> None:
    """Tear down a custom skill via the 3-step delete dance.

    Steps:
      1. ``versions.list(skill_id)`` — paginator over version objects
      2. ``versions.delete(version=ver_str, skill_id=skill_id)`` for each
      3. ``skills.delete(skill_id)``

    **Anthropic built-in skills are protected**: we never list or delete
    a skill we did not upload. The caller is responsible for passing
    only ``skill_id``s that came from :func:`upload_skill`. As a
    belt-and-suspenders, we re-fetch the skill via ``retrieve`` and
    refuse to proceed if its ``source`` is ``anthropic``.

    Best-effort: any error in the dance is raised so the caller can log
    a leak in the ``leaked_skills`` table. Use :func:`archive_skill_safe`
    if you want a swallow-and-log variant.
    """
    # Built-in guard
    try:
        existing = await client.beta.skills.retrieve(skill_id, betas=[SKILLS_BETA])
        source = getattr(existing, "source", None)
        if source == ANTHROPIC_SKILL_SOURCE:
            raise PermissionError(
                f"refusing to archive Anthropic built-in skill {skill_id} "
                f"(source={source!r})"
            )
    except PermissionError:
        raise
    except Exception:  # noqa: BLE001
        # If retrieve fails (skill already gone? auth issue?), proceed —
        # the delete dance will surface a clearer error if there's a
        # real problem.
        pass

    # Step 1+2: enumerate and delete versions
    versions_page = await client.beta.skills.versions.list(
        skill_id, betas=[SKILLS_BETA]
    )
    async for version in versions_page:
        ver = getattr(version, "version", None)
        if ver is None and hasattr(version, "model_dump"):
            ver = version.model_dump().get("version")
        if ver is None:
            continue
        await client.beta.skills.versions.delete(
            version=str(ver),
            skill_id=skill_id,
            betas=[SKILLS_BETA],
        )

    # Step 3: delete the skill itself
    await client.beta.skills.delete(skill_id, betas=[SKILLS_BETA])


async def archive_skill_safe(
    client: AsyncAnthropic,
    skill_id: str,
) -> tuple[bool, str | None]:
    """Swallow-and-log variant. Returns ``(success, error_message)``."""
    try:
        await archive_skill(client, skill_id)
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, f"{exc.__class__.__name__}: {str(exc)[:300]}"


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


# ---------------------------------------------------------------------------
# Event parsing helpers
# ---------------------------------------------------------------------------


def extract_written_files(events: list[dict]) -> dict[str, str]:
    """Reconstruct ``output_files`` from a session's event stream.

    Strategy:
      1. Walk all ``agent.tool_use`` events with ``name == "write"``.
         The ``input.file_path`` and ``input.content`` keys are present
         and complete (verified in Step 0).
      2. Walk all ``agent.tool_use`` events with ``name == "bash"``.
         Parse the ``input.command`` for common file-write idioms:
         heredoc redirects (``cat > path << EOF ... EOF``), simple
         redirects (``echo "..." > path``), ``tee path <<<``,
         ``printf "..." > path``. Best-effort — bash output is opaque
         and the command may use shell expansion that we can't safely
         eval.

    All paths are normalized to RELATIVE form: leading slashes are
    stripped (the agent typically writes to absolute paths inside its
    cloud sandbox, but L1's deterministic runner consumes relative
    paths under a temp dir). The smoke test caught this — writing to
    ``/output/solution.py`` in the cloud became ``Path('/') / '/output'``
    on the local FS and crashed L1's mkdir with a read-only filesystem
    error.

    Later writes to the same path overwrite earlier ones (last-write-wins).
    Files written via the ``edit`` tool are NOT captured here — that
    tool produces a patch event, not a content event. v1.3 follow-up.
    """
    out: dict[str, str] = {}

    for ev in events:
        if ev.get("type") != "agent.tool_use":
            continue
        name = ev.get("name", "")
        inp = ev.get("input") or {}
        if not isinstance(inp, dict):
            continue

        if name == "write":
            path = inp.get("file_path")
            content = inp.get("content")
            if isinstance(path, str) and isinstance(content, str):
                out[_normalize_output_path(path)] = content

        elif name == "bash":
            cmd = inp.get("command")
            if not isinstance(cmd, str):
                continue
            for path, content in _parse_bash_writes(cmd):
                out[_normalize_output_path(path)] = content

    return out


def _normalize_output_path(path: str) -> str:
    """Strip leading slashes so the path is relative for L1 consumption.

    Also collapses ``./`` prefixes and any leading whitespace. The result
    is always safe to pass to ``Path(tmp_dir) / normalized_path`` without
    accidentally jumping out of the temp dir via an absolute path or a
    parent traversal.
    """
    p = path.strip().lstrip("/")
    while p.startswith("./"):
        p = p[2:]
    return p


_HEREDOC_RE = re.compile(
    # cat redirects stdout to a file (`cat > path`); tee takes the path as a
    # positional arg (`tee path`). Make the `>` optional so both work.
    r"(?:cat|tee)\s*(?:-[a-z]+\s*)*(?:>\s*)?(?P<path>['\"]?\S+['\"]?)\s*"
    r"<<\s*['\"]?(?P<delim>\w+)['\"]?\n(?P<body>.*?)\n(?P=delim)\s*$",
    re.DOTALL | re.MULTILINE,
)
_SIMPLE_REDIRECT_RE = re.compile(
    r"echo\s+(?P<content>['\"][^'\"]*['\"]|\S+)\s*>\s*(?P<path>['\"]?\S+['\"]?)"
)


def _parse_bash_writes(command: str) -> list[tuple[str, str]]:
    """Best-effort parser for shell file-write idioms in a bash command string.

    Recognizes:
      - ``cat > path << EOF ... EOF`` and ``cat > path << 'EOF' ... EOF``
      - ``tee path << EOF ... EOF``
      - ``echo "content" > path``

    Returns a list of ``(path, content)`` tuples. Strips quoting from
    paths. Returns an empty list if nothing recognizable matches.
    """
    results: list[tuple[str, str]] = []

    for match in _HEREDOC_RE.finditer(command):
        path = match.group("path").strip().strip("'\"")
        body = match.group("body")
        results.append((path, body))

    for match in _SIMPLE_REDIRECT_RE.finditer(command):
        path = match.group("path").strip().strip("'\"")
        content = match.group("content").strip().strip("'\"")
        results.append((path, content))

    return results


def compute_token_usage(events: list[dict]) -> dict[str, int]:
    """Sum token usage across all ``span.model_request_end`` events.

    Returns a dict with ``input``, ``output``, ``cache_creation_input``,
    ``cache_read_input``, and ``n_requests`` keys. Missing fields default
    to 0. Field paths verified in Step 0:
    ``event.model_usage.{input_tokens, output_tokens,
    cache_creation_input_tokens, cache_read_input_tokens}``.
    """
    totals = {
        "input": 0,
        "output": 0,
        "cache_creation_input": 0,
        "cache_read_input": 0,
        "n_requests": 0,
    }
    for ev in events:
        if ev.get("type") != "span.model_request_end":
            continue
        usage = ev.get("model_usage") or {}
        if not isinstance(usage, dict):
            continue
        totals["input"] += int(usage.get("input_tokens") or 0)
        totals["output"] += int(usage.get("output_tokens") or 0)
        totals["cache_creation_input"] += int(usage.get("cache_creation_input_tokens") or 0)
        totals["cache_read_input"] += int(usage.get("cache_read_input_tokens") or 0)
        totals["n_requests"] += 1
    return totals


def compute_session_runtime_hours(events: list[dict]) -> float:
    """Return ``(idle_time - running_time)`` in hours, or 0.0 if either is missing.

    Used to compute the session-runtime line item in
    ``CompetitionResult.cost_breakdown`` — multiply the result by
    :data:`SESSION_RUNTIME_USD_PER_HOUR` (``$0.08``) for USD.
    """
    running_at: datetime | None = None
    idle_at: datetime | None = None

    for ev in events:
        etype = ev.get("type")
        ts_raw = ev.get("processed_at")
        if ts_raw is None:
            continue
        try:
            if isinstance(ts_raw, datetime):
                ts = ts_raw
            else:
                ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        if etype == "session.status_running" and running_at is None:
            running_at = ts
        elif etype == "session.status_idle":
            idle_at = ts

    if running_at is None or idle_at is None:
        return 0.0
    delta = (idle_at - running_at).total_seconds()
    if delta < 0:
        return 0.0
    return delta / 3600.0


def session_was_skill_loaded(events: list[dict], skill_id: str | None) -> bool:
    """Return True if any event indicates the agent loaded the custom skill.

    For now, this is a heuristic: if the session was created with a
    ``skill_id`` AND the agent emitted at least one tool_use after
    ``session.status_running``, we consider the skill "loaded" (the
    agent had access and chose to use tools). Refine in v1.3 once
    Anthropic exposes a ``skill_load`` or equivalent event.

    Returns False if ``skill_id`` is None (no skill was attached).
    """
    if skill_id is None:
        return False
    seen_running = False
    for ev in events:
        etype = ev.get("type")
        if etype == "session.status_running":
            seen_running = True
        elif seen_running and etype == "agent.tool_use":
            return True
    return False
