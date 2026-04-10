"""Competitor backend: Anthropic Managed Agents (cloud sessions).

The new Phase 1 implementation that replaces the local-subprocess SDK
backend (``competitor_sdk.py``). Selected via
``SKILLFORGE_COMPETITOR_BACKEND=managed``. Uses the thin wrapper in
``managed_agents.py`` for all API surface area.

Per-competitor flow:
  1. (Optional) upload the evolved SKILL.md as a versioned custom skill.
  2. Create a Managed Agent linked to the skill + ``agent_toolset_20260401``.
  3. Create a session against the agent + the per-run environment.
  4. Send the challenge prompt + inlined setup files as a single user.message.
  5. Poll ``events.list`` until ``session.status_idle`` (or deadline).
  6. Reconstruct ``output_files`` from ``write``/``bash`` tool_use events.
  7. Build the ``trace`` in the L3-expected shape (capitalized tool names,
     synthetic ``Skill`` marker so L3's ``_detect_skill_loaded`` works).
  8. Compute ``cost_breakdown`` (token usage × model rates + session
     runtime × $0.08).
  9. Schedule teardown of skill/agent/session as a detached task —
     cleanup must NEVER block the evolution loop.
 10. Return ``CompetitionResult`` matching the SDK backend's contract.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from skillforge.agents import managed_agents
from skillforge.config import (
    COMPETITOR_ADVISOR,
    MANAGED_AGENTS_SKILL_MODE,
    MAX_TURNS,
    MODEL_CACHE_CREATE_MULTIPLIER,
    MODEL_CACHE_READ_MULTIPLIER,
    MODEL_PRICE_PER_MTOK_INPUT,
    MODEL_PRICE_PER_MTOK_OUTPUT,
    model_for,
)
from skillforge.models import Challenge, CompetitionResult, SkillGenome

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt — copied verbatim from competitor_sdk.py so output behavior
# is identical between backends. The L1 judge expects output/solution.py.
# ---------------------------------------------------------------------------

_COMPETITOR_SYSTEM_PROMPT = """\
You are competing to solve a coding challenge. A Claude Agent Skill has been
attached to this agent — follow its instructions carefully.

CRITICAL OUTPUT REQUIREMENTS:

1. Save your solution to ``output/solution.py`` using the `write` tool. The
   ``output/`` directory will be created if it does not exist (use `bash`
   to ``mkdir -p output`` first if needed). Do NOT save to any other
   filename (no ``solution_template.py``, etc).

2. Your solution MUST define the function(s) the challenge prompt specifies.
   The grading tests import your ``solution.py`` as a module and call those
   functions with test inputs. A solution that only sets module-level
   variables like ``result = [...]`` with hardcoded values will score zero —
   the tests want a REUSABLE function that works for any input.

3. Read the ``challenge/`` directory if it exists — it will contain starter
   code, test files, or fixtures. You may read from there but you must
   write your solution only to ``output/solution.py``.

4. You may run the Skill's bundled helper scripts via the `bash` tool.
   That's encouraged.

5. If you only respond with inline code in text blocks and never call the
   `write` tool, your score is zero. Make the write call.

Follow the Skill's workflow, use its tools, and save a function-based
solution to ``output/solution.py``.
"""


def _model_token_cost(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_input: int,
    cache_read_input: int,
) -> tuple[float, float]:
    """Return ``(executor_input_usd, executor_output_usd)`` for one model.

    Pricing tables live in ``skillforge.config`` (cross-cutting contract #2:
    no hardcoded model strings outside config.py). Cache creation/read are
    folded into the input bucket because they're just discounted variants
    of input tokens. The cost_breakdown surfaces them separately for
    diagnostics; this function returns the two aggregates the engine cares about.
    """
    in_rate = MODEL_PRICE_PER_MTOK_INPUT.get(model, 3.0)  # default to Sonnet
    out_rate = MODEL_PRICE_PER_MTOK_OUTPUT.get(model, 15.0)
    base_input_usd = (input_tokens / 1_000_000) * in_rate
    cache_create_usd = (
        (cache_creation_input / 1_000_000) * in_rate * MODEL_CACHE_CREATE_MULTIPLIER
    )
    cache_read_usd = (
        (cache_read_input / 1_000_000) * in_rate * MODEL_CACHE_READ_MULTIPLIER
    )
    output_usd = (output_tokens / 1_000_000) * out_rate
    return (base_input_usd + cache_create_usd + cache_read_usd, output_usd)


# ---------------------------------------------------------------------------
# Trace conversion: Managed Agents events → L3-expected shape
# ---------------------------------------------------------------------------

# Tool name canonicalization: managed agents use lowercase tool names (bash,
# write, edit, ...). L3's helpers expect Capitalized names (Bash, Write, ...)
# matching the SDK convention. Translate so L3 keeps working unchanged.
_TOOL_NAME_CANONICAL = {
    "bash": "Bash",
    "write": "Write",
    "edit": "Edit",
    "read": "Read",
    "glob": "Glob",
    "grep": "Grep",
    "web_fetch": "WebFetch",
    "web_search": "WebSearch",
}


def _convert_event_to_trace_entry(event: dict) -> dict | None:
    """Convert a single Managed Agents event into an L3-shaped trace entry.

    L3's heuristics expect ``trace[i].content`` to be a list of dicts where
    each dict can have ``type``, ``name``, ``input``, and ``text`` fields.
    Returns None for events that don't carry useful behavioral information
    (status events, model_request_start, etc.).
    """
    etype = event.get("type", "")

    if etype == "agent.tool_use":
        name = event.get("name", "")
        canonical = _TOOL_NAME_CANONICAL.get(name, name)
        return {
            "role": "assistant",
            "type": "AssistantMessage",
            "content": [
                {
                    "type": "tool_use",
                    "name": canonical,
                    "input": event.get("input") or {},
                }
            ],
        }

    if etype == "agent.tool_result":
        # Carry as a separate trace entry so L3's _classify_instruction_adherence
        # can match against tool result text too.
        content = event.get("content") or event.get("output") or ""
        text = (
            " ".join(str(c) for c in content) if isinstance(content, list) else str(content)
        )
        return {
            "role": "user",
            "type": "ToolResultMessage",
            "content": [{"type": "tool_result", "text": text[:2000]}],
        }

    if etype == "agent.message":
        # Agent's text response — pull whatever text content is present
        content = event.get("content") or []
        text_blocks: list[dict] = []
        if isinstance(content, list):
            for block in content:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "text"
                    and isinstance(block.get("text"), str)
                ):
                    text_blocks.append({"type": "text", "text": block["text"]})
        elif isinstance(content, str):
            text_blocks.append({"type": "text", "text": content})
        if text_blocks:
            return {
                "role": "assistant",
                "type": "AssistantMessage",
                "content": text_blocks,
            }

    if etype == "agent.thinking":
        # Thinking blocks are useful context for L5 attribution
        text = event.get("content") or event.get("text") or ""
        if isinstance(text, str) and text:
            return {
                "role": "assistant",
                "type": "AssistantMessage",
                "content": [{"type": "thinking", "text": text[:2000]}],
            }

    if etype == "user.message":
        content = event.get("content") or []
        text_blocks = []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_blocks.append({"type": "text", "text": str(block.get("text", ""))})
        if text_blocks:
            return {
                "role": "user",
                "type": "UserMessage",
                "content": text_blocks,
            }

    return None


def _build_trace(
    events: list[dict],
    *,
    skill_attached: bool,
) -> list[dict]:
    """Convert the raw event list into an L3-compatible trace.

    Synthesizes a leading "Skill" tool_use marker when ``skill_attached``
    is True so L3's ``_detect_skill_loaded`` heuristic returns True. The
    Managed Agents API doesn't emit an explicit skill-load event — the
    skill is auto-loaded into the agent's context — but L3's existing
    contract expects to see it in the trace. Documented as a Phase 1
    compatibility shim; revisit when Anthropic ships a skill_load event.
    """
    trace: list[dict] = []
    if skill_attached:
        trace.append(
            {
                "role": "assistant",
                "type": "AssistantMessage",
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Skill",
                        "input": {"_synthetic": True},
                    }
                ],
            }
        )

    for ev in events:
        entry = _convert_event_to_trace_entry(ev)
        if entry is not None:
            trace.append(entry)

    return trace


# ---------------------------------------------------------------------------
# User message construction
# ---------------------------------------------------------------------------


def _build_user_message(
    challenge: Challenge,
    *,
    inline_skill_md: str | None = None,
) -> str:
    """Assemble the first user.message text for the session.

    Always inlines the challenge setup files as bash heredocs that the
    agent should write to disk before solving (Managed Agents has no
    documented file-upload-to-session API). Optionally inlines the skill
    body itself when running in ``inline`` mode (no custom skill upload).
    """
    parts: list[str] = []

    if inline_skill_md is not None:
        parts.append(
            "## Skill instructions (inline mode — no custom skill uploaded)\n\n"
            f"```\n{inline_skill_md}\n```\n"
        )

    parts.append(f"## Challenge\n\n{challenge.prompt}\n")

    if challenge.setup_files:
        parts.append(
            "## Setup files (write each to its path before solving)\n\n"
            "Use bash to create the ``challenge/`` directory and write each "
            "of these files into it. Then read them as needed for context.\n"
        )
        parts.append("```bash\nmkdir -p challenge output\n```\n")
        for path, content in challenge.setup_files.items():
            # Use a unique heredoc delimiter to avoid collision with file
            # contents that might contain "EOF"
            delim = "SF_HEREDOC_END"
            parts.append(
                f"```bash\ncat > challenge/{path} <<'{delim}'\n{content}\n{delim}\n```\n"
            )

    parts.append(
        "## Reminder\n\n"
        "Save the solution to ``output/solution.py`` via the `write` tool. "
        "Define a real function — not a hardcoded variable. Use bash to "
        "``mkdir -p output`` first if needed."
    )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main entry point — same shape as competitor_sdk.run_competitor
# ---------------------------------------------------------------------------


async def run_competitor(
    skill: SkillGenome,
    challenge: Challenge,
    env_id: str,
    *,
    client: Any | None = None,
) -> CompetitionResult:
    """Run one Skill against one Challenge inside a Managed Agents session.

    The third positional argument is the per-run environment id (a string),
    NOT a sandbox path — that's the key API difference from the SDK
    backend. The engine creates one environment per run via
    ``managed_agents.create_environment()`` and reuses its id for every
    competitor in that run.

    Cleanup is best-effort and runs in detached tasks. ``leaked_skills``
    bookkeeping is the engine's job, not this function's.
    """
    own_client = client is None
    if client is None:
        client = managed_agents.make_client()

    skill_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    trace: list[dict] = []
    output_files: dict[str, str] = {}
    cost_breakdown: dict[str, float] = {}
    judge_reasoning_parts: list[str] = []
    skill_attached = False

    try:
        # ---- Skill upload (if mode == "upload") ------------------------
        inline_skill_md: str | None = None
        if MANAGED_AGENTS_SKILL_MODE == "upload":
            try:
                # Each (skill, challenge) pair uploads its own copy so the
                # display_title is unique. Re-uploading the same skill across
                # competitors returns:
                # ``400 Skill cannot reuse an existing display_title: ...``
                # (per the live e2e smoke). The folder name inside the upload
                # still has to match the SKILL.md frontmatter `name:` field —
                # the wrapper handles that — but the display_title is free
                # form. Including the challenge id keeps each upload distinct.
                #
                # An optimization for v1.3: cache uploaded skill_id at the
                # run level keyed by skill.id so we upload once per skill and
                # reuse across challenges. Phase 1 keeps the per-pair upload
                # for simplicity (uploads are free + fast — Step 0 measured
                # ~2s parallel, ~4s serial).
                display_title = f"sf-{skill.id[:8]}-{challenge.id[:8]}"
                skill_id = await managed_agents.upload_skill(
                    client, name=display_title, skill_md=skill.skill_md_content
                )
                skill_attached = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("skill upload failed, falling back to inline: %s", exc)
                inline_skill_md = skill.skill_md_content
                skill_id = None
        else:
            inline_skill_md = skill.skill_md_content

        # ---- Agent creation -------------------------------------------
        agent_name = f"sf-comp-{skill.id[:8]}-{challenge.id[:8]}"
        agent_id = await managed_agents.create_competitor_agent(
            client,
            name=agent_name,
            model=model_for("competitor"),
            system_prompt=_COMPETITOR_SYSTEM_PROMPT,
            skill_id=skill_id,
        )

        # ---- Session creation -----------------------------------------
        session_id = await managed_agents.create_session(
            client,
            agent_id=agent_id,
            environment_id=env_id,
            title=f"sf-{skill.id[:8]}-{challenge.id[:8]}",
        )

        # ---- Send challenge prompt ------------------------------------
        user_text = _build_user_message(challenge, inline_skill_md=inline_skill_md)
        await managed_agents.send_user_message(client, session_id, user_text)

        # ---- Poll session events until idle ---------------------------
        # Deadline matches the SDK backend's 300s. Managed Agents sessions
        # often beat this comfortably; the cap exists so a runaway agent
        # can't burn through budget.
        events: list[dict] = []
        deadline = 300.0 + 30.0 * MAX_TURNS  # extra slack per turn
        try:
            async for ev in managed_agents.iter_session_events(
                client, session_id, deadline_seconds=deadline, poll_interval=2.0
            ):
                events.append(ev)
        except Exception as exc:  # noqa: BLE001
            judge_reasoning_parts.append(f"event polling error: {exc}")

        # ---- Build outputs --------------------------------------------
        output_files = managed_agents.extract_written_files(events)
        trace = _build_trace(events, skill_attached=skill_attached)

        # ---- Compute cost_breakdown ------------------------------------
        token_totals = managed_agents.compute_token_usage(events)
        runtime_hours = managed_agents.compute_session_runtime_hours(events)
        executor_model = model_for("competitor")
        executor_in_usd, executor_out_usd = _model_token_cost(
            model=executor_model,
            input_tokens=token_totals["input"],
            output_tokens=token_totals["output"],
            cache_creation_input=token_totals["cache_creation_input"],
            cache_read_input=token_totals["cache_read_input"],
        )
        runtime_usd = runtime_hours * managed_agents.SESSION_RUNTIME_USD_PER_HOUR

        cost_breakdown = {
            "executor_input_usd": round(executor_in_usd, 6),
            "executor_output_usd": round(executor_out_usd, 6),
            # Advisor is descoped from Phase 1 (Step 0 found the tool type
            # is not yet supported). The keys stay as no-op zeros so the
            # frontend cost-card schema is forward-compatible.
            "advisor_input_usd": 0.0,
            "advisor_output_usd": 0.0,
            "session_runtime_usd": round(runtime_usd, 6),
            "input_tokens": token_totals["input"],
            "output_tokens": token_totals["output"],
            "cache_creation_input_tokens": token_totals["cache_creation_input"],
            "cache_read_input_tokens": token_totals["cache_read_input"],
            "n_model_requests": token_totals["n_requests"],
            "session_runtime_hours": round(runtime_hours, 6),
            # Forward-compat marker so analytics can tell which backend
            # produced this result.
            "backend": "managed",
            "advisor_enabled": COMPETITOR_ADVISOR,
        }

    except Exception as exc:  # noqa: BLE001
        logger.exception("competitor_managed: unexpected error")
        judge_reasoning_parts.append(f"competitor_managed error: {exc}")

    finally:
        # Schedule cleanup as DETACHED tasks so they never block the
        # evolution loop. The engine's leaked_skills bookkeeping is
        # responsible for catching anything that fails here.
        if session_id:
            asyncio.create_task(managed_agents.archive_session(client, session_id))
        if agent_id:
            asyncio.create_task(managed_agents.archive_agent(client, agent_id))
        if skill_id:
            # archive_skill_safe doesn't raise — engine wraps with leak
            # bookkeeping at the integration point (task #8).
            asyncio.create_task(managed_agents.archive_skill_safe(client, skill_id))
        # If WE created the client, close it (best-effort).
        if own_client:
            asyncio.create_task(client.close())

    return CompetitionResult(
        skill_id=skill.id,
        challenge_id=challenge.id,
        output_files=output_files,
        trace=trace,
        cost_breakdown=cost_breakdown,
        judge_reasoning="; ".join(judge_reasoning_parts),
    )
