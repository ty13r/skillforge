"""Competitor — runs a single candidate Skill against a single Challenge.

Invokes the Claude Agent SDK ``query()`` with:
- ``cwd`` pointing at the sandbox directory
- ``setting_sources=["project"]`` so the Skill loads from ``.claude/skills/``
- ``permission_mode="dontAsk"`` (never ``bypassPermissions`` — that's a trap)
- ``allowed_tools=["Skill", "Read", "Write", "Edit", "Bash"]``
- ``max_turns=config.MAX_TURNS``
- A ``system_prompt`` that explicitly tells Claude to save solution files
  to ``output/`` so the Judge pipeline's L1 deterministic layer can run
  them against the challenge's test suite. Without this, Claude answers
  with inline code in text responses and L1 can't score anything
  (discovered during the first full live evolution run — every competitor
  had ``output_files: []`` and ``tests_pass: False``, collapsing fitness).

Collects the full execution trace + written files for the judging pipeline.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

from skillforge.config import MAX_TURNS, model_for
from skillforge.engine.sandbox import collect_written_files
from skillforge.models import Challenge, CompetitionResult, SkillGenome


def _message_to_dict(msg) -> dict:
    """Convert an SDK message to a JSON-safe dict for trace storage."""
    result = {"type": msg.__class__.__name__ if hasattr(msg, "__class__") else "unknown"}
    # Try common attrs in order of preference
    if hasattr(msg, "content"):
        content = msg.content
        if isinstance(content, str):
            result["content"] = content
        elif isinstance(content, list):
            # Content blocks — extract text and tool info
            blocks = []
            for block in content:
                block_dict = {"type": getattr(block, "type", block.__class__.__name__ if hasattr(block, "__class__") else "block")}
                if hasattr(block, "text"):
                    block_dict["text"] = block.text
                if hasattr(block, "name"):
                    block_dict["name"] = block.name
                if hasattr(block, "input"):
                    try:
                        import json
                        json.dumps(block.input)
                        block_dict["input"] = block.input
                    except (TypeError, ValueError):
                        block_dict["input"] = str(block.input)
                blocks.append(block_dict)
            result["content"] = blocks
    # Capture role if present (AssistantMessage, UserMessage, ResultMessage, etc.)
    if hasattr(msg, "role"):
        result["role"] = msg.role
    return result


_COMPETITOR_SYSTEM_PROMPT = """\
You are competing to solve a coding challenge. A Claude Agent Skill has been
loaded from .claude/skills/evolved-skill/ — follow its instructions carefully.

CRITICAL OUTPUT REQUIREMENT:
- Save your solution file(s) to the ``output/`` directory using the Write tool.
- The output/ directory already exists in your current working directory.
- If the challenge specifies a file name (e.g., ``solution.py``), save to
  ``output/solution.py``. Otherwise use a sensible name like ``output/solution.py``.
- If the challenge has a ``challenge/`` directory with starter code or test
  files, you may read from there but write only to output/.
- Your work is graded by running tests against the files in output/. If you
  only respond with inline code and do not call Write, you will score zero.

Follow the Skill's workflow, use its helper scripts if it bundles any, and
save the final result to output/.
"""


async def run_competitor(
    skill: SkillGenome,
    challenge: Challenge,
    sandbox_path: Path,
) -> CompetitionResult:
    """Run one Skill against one Challenge in an isolated sandbox."""
    options = ClaudeAgentOptions(
        cwd=str(sandbox_path),
        setting_sources=["project"],
        allowed_tools=["Skill", "Read", "Write", "Edit", "Bash"],
        max_turns=MAX_TURNS,
        permission_mode="dontAsk",
        model=model_for("competitor"),
        system_prompt=_COMPETITOR_SYSTEM_PROMPT,
    )

    trace: list[dict] = []

    try:
        async with asyncio.timeout(300):
            async for msg in query(prompt=challenge.prompt, options=options):
                trace.append(_message_to_dict(msg))
    except TimeoutError:
        output_files = collect_written_files(sandbox_path / "output")
        return CompetitionResult(
            skill_id=skill.id,
            challenge_id=challenge.id,
            output_files=output_files,
            trace=trace,
            judge_reasoning="timeout after 300s",
        )
    except Exception as exc:
        print(f"sdk error in run_competitor: {exc}", file=sys.stderr)
        output_files = collect_written_files(sandbox_path / "output")
        return CompetitionResult(
            skill_id=skill.id,
            challenge_id=challenge.id,
            output_files=output_files,
            trace=trace,
            judge_reasoning=f"sdk error: {exc}",
        )

    output_files = collect_written_files(sandbox_path / "output")
    return CompetitionResult(
        skill_id=skill.id,
        challenge_id=challenge.id,
        output_files=output_files,
        trace=trace,
    )
