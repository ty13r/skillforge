"""Challenge Designer — auto-generates evaluation challenges from a specialization.

Uses the Anthropic Messages API directly (NOT the Agent SDK's query()) because
this is a pure generation task with no tool use. The Agent SDK is for agentic
loops; direct API is faster, simpler, and avoids the multi-turn session
overhead that caused the overnight live test to hang.

WebSearch is not available via the direct API, so the MVP challenge designer
does not ground challenges in real-world examples via search. That's a v1.1
improvement — we can add WebSearch as a tool definition in the Messages API
request when we're ready.
"""

from __future__ import annotations

import json
import re
import uuid

from anthropic import AsyncAnthropic

from skillforge.config import ANTHROPIC_API_KEY, model_for
from skillforge.models import Challenge

# JSON schema description embedded in prompts
_SCHEMA_DESCRIPTION = """[
  {
    "prompt": "concrete task instruction to give Claude when the Skill is loaded",
    "difficulty": "easy" | "medium" | "hard",
    "evaluation_criteria": {"correctness": 0.4, "idiomaticity": 0.3, "robustness": 0.2, "simplicity": 0.1},
    "verification_method": "run_tests" | "judge_review" | "both",
    "setup_files": {"relative/path.py": "file contents"},
    "gold_standard_hints": "what a great solution looks like"
  }
]"""


def _extract_json_array(text: str) -> list[dict]:
    """Extract a JSON array from text.

    Robust against:
      1. Raw JSON array (ideal case)
      2. ``` json ... ``` fences with nested backticks in string values
      3. JSON embedded in prose with `[`/`]` characters in string literals

    Raises:
        ValueError: if no valid JSON array can be extracted.
    """
    candidate = text.strip()

    # 1. Try the whole text as JSON
    if candidate.startswith("[") and candidate.endswith("]"):
        try:
            result = json.loads(candidate)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # 2. Strip outer ```json ... ``` fence greedily
    fence_match = re.search(r"```(?:json)?\s*\n?(.*)\n?```", text, re.DOTALL)
    if fence_match:
        fenced = fence_match.group(1).strip()
        try:
            result = json.loads(fenced)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            text_to_scan = fenced
        else:
            text_to_scan = fenced
    else:
        text_to_scan = text

    # 3. Bracket-depth scan respecting string literal state
    array = _scan_outermost_array(text_to_scan)
    if array is not None:
        try:
            result = json.loads(array)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    raise ValueError("No valid JSON array found in response text")


def _scan_outermost_array(text: str) -> str | None:
    """Find the outermost JSON array via bracket-depth scanning that
    respects string literal state. Returns substring including ``[`` and
    ``]``, or ``None`` if no balanced array found.
    """
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


_FILE_CONVENTION = """\
## File convention (STRICT — follow exactly)

The Competitor agent saves its solution to ``solution.py``. Your test files
will be placed alongside ``solution.py`` in the same working directory
before pytest runs.

Therefore:

1. Your ``setup_files`` MUST include a test file named ``test_solution.py``
   (or ``test_*.py``). Tests MUST import from ``solution`` (the module) —
   NOT from ``solution_template.py`` or any other name.

2. Do NOT create a ``solution_template.py`` — the Competitor writes
   ``solution.py`` directly. Your tests must work against whatever the
   Competitor writes.

3. Tests should call FUNCTIONS defined in the solution module with test
   inputs. Do NOT rely on module-level variables like ``assert mod.result == ...``
   with hardcoded input data — that pattern breaks when the Competitor writes
   a generic solution instead of one wired to your specific example.

4. The challenge prompt MUST tell the Competitor what function signature to
   implement, e.g.: "Define a function ``solve(numbers: list) -> list``
   that returns...". The tests then call ``sol.solve([...])``.

5. Preferred test loader pattern (use this exact loader, then write
   tests SPECIFIC TO THE SPECIALIZATION DOMAIN):

```python
import importlib.util, sys

def load_solution():
    spec = importlib.util.spec_from_file_location("sol", "solution.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sol"] = mod
    spec.loader.exec_module(mod)
    return mod
```

Then your tests call domain-specific functions defined by the challenge,
e.g. `sol.refactor_component(jsx_string)`, `sol.optimize_query(sql_string)`,
`sol.clean_dataframe(df)` — whatever the specialization actually requires.
DO NOT default to generic algorithms like flatten/sort/cache/parse.

6. You may include small data files or fixtures in ``setup_files`` if
   the challenge needs them, but the test logic must go through a
   function call pattern.
"""


def _build_system_prompt(specialization: str, n: int) -> str:
    return (
        f"## Specialization (THIS IS THE ONLY THING THAT MATTERS)\n\n"
        f"{specialization}\n\n"
        f"## Your job\n\n"
        f"Design {n} evaluation challenges that DIRECTLY exercise the specialization above. "
        f"Span easy/medium/hard difficulty.\n\n"
        f"**CRITICAL**: Each challenge MUST be specifically about the specialization domain. "
        f"DO NOT produce generic Python algorithm challenges (flatten, LRU cache, word frequency, "
        f"CSV parsing, etc.) unless those directly map to the specialization. If the specialization "
        f"is about React refactoring, your challenges must involve React component code. If it's "
        f"about pandas cleaning, they must involve real DataFrames. If it's about SQL optimization, "
        f"they must involve real queries. The specialization is the entire point of this evaluation.\n\n"
        f"{_FILE_CONVENTION}\n\n"
        "Return ONLY a JSON array — no prose before or after — matching this schema:\n"
        f"{_SCHEMA_DESCRIPTION}\n"
        "Each object must have all six keys. The 'id' field is generated by Python; do NOT include it."
    )


def _build_retry_prompt(specialization: str, n: int) -> str:
    return (
        "Your previous response was not parseable JSON. "
        f"Respond with ONLY a JSON array of exactly {n} challenge objects matching this schema:\n"
        f"{_SCHEMA_DESCRIPTION}\n"
        "No explanation, no markdown prose — ONLY the JSON array."
    )


def _parse_challenges(raw: list[dict]) -> list[Challenge]:
    """Convert raw dicts into Challenge objects, generating UUIDs."""
    challenges: list[Challenge] = []
    for item in raw:
        challenges.append(
            Challenge(
                id=str(uuid.uuid4()),
                prompt=item["prompt"],
                difficulty=item["difficulty"],
                evaluation_criteria=item.get("evaluation_criteria", {}),
                verification_method=item.get("verification_method", "judge_review"),
                setup_files=item.get("setup_files", {}),
                gold_standard_hints=item.get("gold_standard_hints", ""),
            )
        )
    return challenges


async def _generate(prompt: str) -> str:
    """Streaming Anthropic API call. Returns the concatenated text response.

    Uses `messages.stream()` so the TCP connection stays alive during long
    generations — the non-streaming `create()` variant can silently drop
    the connection and leave the client hanging indefinitely (observed
    on the Spawner's ~15KB prompts; same fix applied here).

    Also sets an explicit 300s read timeout as a belt-and-suspenders hard
    cap so the engine fails loudly instead of hanging forever.
    """
    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY, timeout=300.0)
    parts: list[str] = []
    async with client.messages.stream(
        model=model_for("challenge_designer"),
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for text in stream.text_stream:
            parts.append(text)
    return "".join(parts)


async def design_challenges(specialization: str, n: int = 3) -> list[Challenge]:
    """Generate ``n`` challenges for the given specialization.

    Uses the Anthropic Messages API directly for pure JSON generation. One
    retry on parse failure, then raises.

    Args:
        specialization: Description of the Skill domain to design challenges for.
        n: Number of challenges to generate. Defaults to 3.

    Returns:
        A list of exactly ``n`` Challenge objects with generated UUIDs.

    Raises:
        ValueError: if JSON cannot be parsed after 2 attempts, or if the
            number of returned challenges does not equal ``n``.
    """
    # Attempt 1
    text = await _generate(_build_system_prompt(specialization, n))

    try:
        raw = _extract_json_array(text)
    except ValueError:
        # Attempt 2 — retry with more explicit prompt
        text = await _generate(_build_retry_prompt(specialization, n))
        try:
            raw = _extract_json_array(text)
        except ValueError as err:
            raise ValueError(
                "challenge designer failed to produce valid JSON after 2 attempts"
            ) from err

    challenges = _parse_challenges(raw)

    if len(challenges) != n:
        raise ValueError(
            f"challenge designer returned {len(challenges)} challenges, expected {n}"
        )

    return challenges
