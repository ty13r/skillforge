"""L3 — Trace-based behavioral analysis.

Parses the Agent SDK execution trace to answer:
- Did Claude actually load the Skill?
- Which SKILL.md instructions were followed vs. ignored?
- Which supporting scripts were executed?
- What is the Skill's behavioral signature (ordered sequence of actions)?

Populates: ``skill_was_loaded``, ``instructions_followed``, ``instructions_ignored``,
``ignored_diagnostics``, ``scripts_executed``, ``behavioral_signature``.
"""

from __future__ import annotations

import json
import re

from anthropic import AsyncAnthropic

from skillforge.config import ANTHROPIC_API_KEY, model_for
from skillforge.models import CompetitionResult, SkillGenome


async def run_l3(result: CompetitionResult, skill: SkillGenome) -> CompetitionResult:
    """Populate L3 fields on result. Returns the same object for chaining."""
    trace = result.trace

    # 1. Did Claude load the Skill? Look for any tool_use block with name=="Skill"
    result.skill_was_loaded = _detect_skill_loaded(trace)

    # 2. Behavioral signature — ordered list of tool call names (+ their first arg)
    result.behavioral_signature = _extract_behavioral_signature(trace)

    # 3. Scripts executed — Bash calls that reference scripts/
    result.scripts_executed = _extract_scripts_executed(trace)

    # 4. Extract discrete instructions from SKILL.md body
    instructions = _extract_instructions(skill.skill_md_content)

    # 5. For each instruction, check if a corresponding action appears in the trace
    followed, ignored = _classify_instruction_adherence(instructions, trace)
    result.instructions_followed = followed
    result.instructions_ignored = ignored

    # 6. For ignored instructions, ask the LLM WHY (single batched call)
    if ignored:
        diagnostics = await _diagnose_ignored(ignored, trace, skill.skill_md_content)
        result.ignored_diagnostics = diagnostics
    else:
        result.ignored_diagnostics = {}

    return result


def _detect_skill_loaded(trace: list[dict]) -> bool:
    """Walk trace looking for any tool_use with name 'Skill'."""
    for msg in trace:
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("name") == "Skill":
                    return True
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Skill":
                    return True
    return False


def _extract_behavioral_signature(trace: list[dict]) -> list[str]:
    """Ordered list of tool_use names from the trace."""
    signature: list[str] = []
    for msg in trace:
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    name = block.get("name")
                    block_type = block.get("type")
                    if name and (block_type == "tool_use" or block_type is None):
                        signature.append(name)
    return signature


def _extract_scripts_executed(trace: list[dict]) -> list[str]:
    """Pull out Bash commands that reference scripts/ from trace."""
    scripts: list[str] = []
    for msg in trace:
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("name") == "Bash":
                    cmd_input = block.get("input", {})
                    if isinstance(cmd_input, dict):
                        cmd = cmd_input.get("command", "")
                    else:
                        cmd = str(cmd_input)
                    # Find references to scripts/
                    for match in re.finditer(r"scripts/[\w\-./]+", cmd):
                        script = match.group(0)
                        if script not in scripts:
                            scripts.append(script)
    return scripts


def _extract_instructions(skill_md_content: str) -> list[str]:
    """Extract discrete actionable instructions from SKILL.md body.

    Looks for:
    - Numbered step lines under ## Workflow or similar (e.g., "### Step 1: Do X")
    - Bullet lines starting with '- ' under workflow sections
    - Imperative-voice directives

    Returns a list of instruction strings, de-duplicated.
    """
    if "---" not in skill_md_content:
        return []
    try:
        _, _, body = skill_md_content.split("---", 2)
    except ValueError:
        return []

    instructions: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        # Numbered step headings: "### Step N: ..."
        if re.match(r"^#{2,4}\s*Step\s+\d+", stripped, re.IGNORECASE):
            text = re.sub(r"^#+\s*Step\s+\d+[:.]?\s*", "", stripped, flags=re.IGNORECASE)
            if text:
                instructions.append(text)
        # Bullet points starting with "- " (not tables, not blockquotes)
        elif stripped.startswith("- ") and len(stripped) > 2:
            text = stripped[2:].strip()
            if text and not text.startswith("["):  # skip markdown link-list items
                instructions.append(text)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for ins in instructions:
        key = ins.lower()[:80]
        if key not in seen:
            seen.add(key)
            unique.append(ins)
    return unique


def _classify_instruction_adherence(
    instructions: list[str],
    trace: list[dict],
) -> tuple[list[str], list[str]]:
    """Split instructions into (followed, ignored) based on trace evidence.

    Heuristic: an instruction is "followed" if any significant noun from it
    (tokens >= 4 chars, not stopwords) appears in the trace's tool_use inputs
    or assistant text. Otherwise "ignored".
    """
    # Flatten trace to a single searchable string
    haystack_parts: list[str] = []
    for msg in trace:
        content = msg.get("content")
        if isinstance(content, str):
            haystack_parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if "text" in block:
                        haystack_parts.append(str(block["text"]))
                    if "input" in block:
                        haystack_parts.append(json.dumps(block["input"]) if not isinstance(block["input"], str) else block["input"])
    haystack = " ".join(haystack_parts).lower()

    stopwords = {
        "the", "and", "for", "with", "this", "that", "from", "into", "when",
        "your", "will", "must", "have", "been", "make", "them", "then",
    }

    followed: list[str] = []
    ignored: list[str] = []
    for ins in instructions:
        # Tokenize instruction — keep content words only
        tokens = [
            t.lower() for t in re.findall(r"\b[a-zA-Z]{4,}\b", ins)
            if t.lower() not in stopwords
        ]
        if not tokens:
            # Nothing to match — skip classification (don't penalize)
            continue
        # Count how many content tokens appear in the haystack
        hits = sum(1 for t in tokens if t in haystack)
        # If >=50% of content tokens appear, consider it followed
        if hits >= max(1, len(tokens) // 2):
            followed.append(ins)
        else:
            ignored.append(ins)

    return followed, ignored


async def _diagnose_ignored(
    ignored: list[str],
    trace: list[dict],
    skill_md_content: str,
) -> dict[str, str]:
    """Ask the LLM why each ignored instruction was ignored. One batched call."""
    if not ignored:
        return {}

    trace_summary = _summarize_trace_for_prompt(trace)
    numbered = "\n".join(f"{i + 1}. {ins}" for i, ins in enumerate(ignored))

    user_prompt = (
        "A Claude Agent Skill's SKILL.md contained instructions that were NOT followed "
        "during execution. Given the execution trace summary below, briefly diagnose "
        "WHY each instruction was ignored.\n\n"
        "Possible reasons: (a) too vague, (b) contradicted by another instruction, "
        "(c) not relevant to the task, (d) Claude chose a shortcut, (e) trace evidence "
        "unclear.\n\n"
        f"Execution trace summary:\n{trace_summary}\n\n"
        f"Ignored instructions:\n{numbered}\n\n"
        "Respond with a JSON object mapping each instruction number to a one-sentence "
        "diagnosis, like:\n"
        '{"1": "too vague — no concrete action", "2": "not relevant to this challenge"}\n\n'
        "Respond with ONLY the JSON object — no prose."
    )

    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    try:
        response = await client.messages.create(
            model=model_for("judge_trace"),
            max_tokens=len(ignored) * 100 + 200,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = response.content[0].text if response.content else "{}"
    except Exception as exc:  # noqa: BLE001 — log and fall through
        return {ins: f"diagnosis error: {exc}" for ins in ignored}

    # Parse JSON object
    try:
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if not json_match:
            raise ValueError("no JSON object in response")
        raw = json.loads(json_match.group(0))
    except (json.JSONDecodeError, ValueError):
        return {ins: "diagnosis unparseable" for ins in ignored}

    # Map numbered keys back to instruction strings
    diagnostics: dict[str, str] = {}
    for i, ins in enumerate(ignored):
        key = str(i + 1)
        diagnostics[ins] = raw.get(key, "no diagnosis returned")
    return diagnostics


def _summarize_trace_for_prompt(trace: list[dict], max_chars: int = 2000) -> str:
    """Produce a compact trace summary for the LLM diagnosis prompt."""
    parts: list[str] = []
    for msg in trace:
        msg_type = msg.get("type", "msg")
        content = msg.get("content")
        if isinstance(content, str):
            parts.append(f"[{msg_type}] {content[:200]}")
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    btype = block.get("type", "block")
                    name = block.get("name", "")
                    text = str(block.get("text", ""))[:150]
                    if name:
                        parts.append(f"[{msg_type}/{btype}:{name}] {text}")
                    elif text:
                        parts.append(f"[{msg_type}/{btype}] {text}")
    summary = "\n".join(parts)
    if len(summary) > max_chars:
        return summary[:max_chars] + "\n... [truncated]"
    return summary
