"""Robust JSON-array extraction from LLM prose.

Shared by agents that ask an LLM for a list of structured items and must
tolerate responses wrapped in prose, code fences, nested backticks, or
string values that contain ``[``/``]``. See ``docs/clean-code.md`` §1
(reuse over duplication).
"""

from __future__ import annotations

import json
import re

from skillforge.errors import ParseError

_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*)\n?```", re.DOTALL)


def extract_json_array(text: str) -> list[dict]:
    """Return the outermost JSON array embedded in ``text``.

    Handles three response shapes:
      1. Raw JSON array — the entire response is a ``[...]``.
      2. Fenced block — response wrapped in ```` ```json ... ``` ```` fences.
         Matched greedily so nested fences in string values don't split.
      3. Array embedded in prose — extracted via bracket-depth scanning
         that respects JSON string literal state (``[``/``]`` inside
         string values don't perturb the depth counter).

    Raises:
        ParseError: no balanced JSON array could be located.
    """
    candidate = text.strip()

    if candidate.startswith("[") and candidate.endswith("]"):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(parsed, list):
                return parsed

    fence_match = _FENCE_RE.search(text)
    if fence_match:
        fenced = fence_match.group(1).strip()
        try:
            parsed = json.loads(fenced)
        except json.JSONDecodeError:
            text_to_scan = fenced
        else:
            if isinstance(parsed, list):
                return parsed
            text_to_scan = fenced
    else:
        text_to_scan = text

    array_src = _scan_outermost_array(text_to_scan)
    if array_src is not None:
        try:
            parsed = json.loads(array_src)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(parsed, list):
                return parsed

    raise ParseError("no valid JSON array found in response text")


def _scan_outermost_array(text: str) -> str | None:
    """Return the outermost balanced ``[...]`` substring, or ``None``."""
    start = text.find("[")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None
