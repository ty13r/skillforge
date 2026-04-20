"""Post-run event-stream introspection.

Pulls the written-file map out of trace events, parses bash
``cat <<'EOF' > path`` writes, and computes token usage + session
runtime cost. All pure functions — no network, no mutation.
"""

from __future__ import annotations

import re
from datetime import datetime

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
