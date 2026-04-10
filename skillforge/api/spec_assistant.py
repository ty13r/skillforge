"""AI Spec Assistant — chat-guided specialization builder for /new.

The user describes what they want in natural language; the assistant asks
clarifying questions about domain, trigger patterns, failure modes, and
structural constraints, then produces a well-formed `specialization` string
the evolution engine can act on.

When the assistant is ready to commit, it emits a JSON block of the form
`{"final_spec": "..."}` inside its reply. The frontend extracts that and
auto-fills the specialization textarea.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger("skillforge.api.spec_assistant")

from anthropic import AsyncAnthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from skillforge.config import ROOT_DIR, model_for

router = APIRouter(prefix="/api/spec-assistant", tags=["spec-assistant"])


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class SpecChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)


class SpecChatResponse(BaseModel):
    message: str
    final_spec: str | None = None


SYSTEM_PROMPT = """You are the SKLD.run Spec Assistant.

SKLD.run is an evolutionary breeding platform for Claude Agent Skills. Users
bring a problem domain; the platform evolves a population of SKILL.md files
through tournament selection and returns the best-performing Skill.

Your job: conduct a short, focused conversation that turns a vague idea
into a crisp `specialization` string the evolution engine can act on. A
good specialization is 1-3 sentences that clearly state:

1. **The domain and task** — what kind of work the Skill handles
2. **The trigger patterns** — what user requests should activate it
3. **Scope boundaries** — what it explicitly does NOT handle
4. **(Optional) Tech stack or conventions** — language, framework, style

## How to run the conversation

- Start with a warm one-line greeting + one open question about what
  they're trying to accomplish.
- Ask at most ONE question per turn. Keep each message under 4 sentences.
- If the user is already specific, move faster. If vague, probe gently for
  a concrete use case they have in mind.
- Cover in this rough order: domain → concrete example → trigger language →
  boundaries → (optional) tech specifics.
- After 3-5 exchanges you should have enough. Don't drag it out.

## How to commit the final spec

When you have enough context, write a short confirmation message AND append
a fenced JSON block with the final specialization on its own line:

```json
{"final_spec": "<the full specialization string, 1-3 sentences>"}
```

The frontend parses this block to auto-fill the form. Do not emit the JSON
block until you're confident — once emitted, the conversation ends.

## Quality bar for the final_spec

- Uses imperative, action-first phrasing ("Cleans pandas DataFrames by..." not
  "A skill for cleaning...")
- Names the domain explicitly (no generic "data processing")
- Includes at least one concrete trigger phrase the user might say
- Mentions at least one exclusion ("Not for ..." or "Does NOT handle ...")

## Example good final_spec

"Cleans messy CSV ingestion in pandas — handling missing values, near-duplicate
rows, mixed-type columns, and inconsistent date formats. Use when the user
mentions data cleaning, deduplication, schema normalization, or 'why is this
column all strings'. Does NOT handle schema design for new databases."
"""


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_final_spec(text: str) -> str | None:
    """Pull `final_spec` out of a fenced JSON block if present."""
    for match in _JSON_BLOCK_RE.finditer(text):
        try:
            obj = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        spec = obj.get("final_spec")
        if isinstance(spec, str) and spec.strip():
            return spec.strip()
    return None


def _strip_json_block(text: str) -> str:
    """Remove the fenced JSON block so the chat reply reads naturally."""
    return _JSON_BLOCK_RE.sub("", text).strip()


@router.post("/chat", response_model=SpecChatResponse)
async def chat(req: SpecChatRequest) -> SpecChatResponse:
    """Advance the spec-building conversation by one turn."""
    if not req.messages:
        # Seed turn — synthesize a greeting without calling the API
        return SpecChatResponse(
            message=(
                "Hi — I'll help you shape this into a strong specialization. "
                "In one or two sentences, what kind of task do you want the "
                "evolved Skill to handle?"
            )
        )

    try:
        client = AsyncAnthropic()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Anthropic client unavailable: {e}",
        ) from e

    api_messages = [
        {"role": m.role, "content": m.content}
        for m in req.messages
        if m.role in ("user", "assistant")
    ]
    if not api_messages or api_messages[-1]["role"] != "user":
        raise HTTPException(
            status_code=400,
            detail="The last message must be from the user.",
        )

    try:
        resp = await client.messages.create(
            model=model_for("spec_assistant"),
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=api_messages,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e}") from e

    # Claude returns a list of content blocks; concatenate text parts
    raw = "".join(
        block.text for block in resp.content if getattr(block, "type", None) == "text"
    )

    final_spec = _extract_final_spec(raw)
    clean_message = _strip_json_block(raw)
    if final_spec and not clean_message:
        clean_message = "Done — I've filled in the specialization. Review it and hit Start Evolution when ready."

    return SpecChatResponse(message=clean_message, final_spec=final_spec)


# ---------------------------------------------------------------------------
# Skill package generation
# ---------------------------------------------------------------------------

_SKILL_CREATOR_DIR = ROOT_DIR / ".claude" / "skills" / "skill-creator"


class GenerateSkillRequest(BaseModel):
    specialization: str


class GenerateSkillResponse(BaseModel):
    name: str = ""
    title: str = ""
    skill_md_content: str = ""
    supporting_files: dict[str, str] = Field(default_factory=dict)
    validation_passed: bool = False
    validation_issues: list[str] = Field(default_factory=list)


def _read_ref(name: str) -> str:
    """Read a reference file from the skill-creator skill."""
    path = _SKILL_CREATOR_DIR / "references" / name
    if path.exists():
        return path.read_text()
    return ""


_GENERATE_SYSTEM = """You generate Claude Agent Skill packages. Be CONCISE — fit within 3500 tokens.

Given a domain specialization, produce a complete skill package as a single JSON object.

{golden_template_spec}

{quality_checklist}

Output EXACTLY ONE JSON object (inside a ```json fence) with these fields:
- "name": kebab-case skill name
- "title": human-readable display title
- "description": ≤250 chars with "Use when ..." triggers AND "NOT for ..." exclusions
- "allowed_tools": space-separated tool list (default: "Read Write Bash(python *)")
- "body": SKILL.md body (after frontmatter). Include ## Quick Start, ## When to use this skill, ## Workflow (with ### Step N referencing ${{CLAUDE_SKILL_DIR}}/scripts/), ## Examples (2-3 brief Input/Output), ## Common mistakes, ## Out of Scope. Keep under 150 lines.
- "supporting_files": object mapping file paths to content:
  - "scripts/validate.sh": bash script (set -euo pipefail, exit 0/1) — keep under 30 lines
  - "scripts/main_helper.py": Python helper — keep under 60 lines
  - "references/guide.md": domain reference — keep 30-60 lines

RULES:
- Scripts must be functional, not stubs
- All ${{CLAUDE_SKILL_DIR}}/ paths must correspond to files in supporting_files
- Description ≤250 chars, body <200 lines
- STAY COMPACT — prioritize a complete, valid package over verbose content
"""


def _assemble_skill_md(name: str, title: str, description: str, allowed_tools: str, body: str) -> str:
    """Build a SKILL.md from its parts."""
    lines = [
        "---",
        f"name: {name}",
        "description: >-",
    ]
    for desc_line in description.strip().split("\n"):
        lines.append(f"  {desc_line.strip()}")
    lines.append(f"allowed-tools: {allowed_tools}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    lines.append(body.strip())
    lines.append("")
    return "\n".join(lines)


async def _validate_package(skill_md: str, supporting_files: dict[str, str]) -> tuple[bool, list[str]]:
    """Run validate_skill_package.py against a temp directory. Returns (passed, issues)."""
    validator = _SKILL_CREATOR_DIR / "scripts" / "validate_skill_package.py"
    if not validator.exists():
        return True, []  # skip if validator not installed

    with tempfile.TemporaryDirectory(prefix="sf-gen-") as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "SKILL.md").write_text(skill_md)
        for path, content in supporting_files.items():
            fp = tmp / path
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content)

        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(validator), str(tmp),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()

        try:
            report = json.loads(stdout.decode())
            issues = [
                c["name"] + ": " + c.get("detail", "")
                for c in report.get("checks", [])
                if c.get("status") == "fail"
            ]
            return report.get("status") == "pass", issues
        except (json.JSONDecodeError, KeyError):
            return proc.returncode == 0, []


@router.post("/generate-skill", response_model=GenerateSkillResponse)
async def generate_skill(req: GenerateSkillRequest) -> GenerateSkillResponse:
    """Generate a full skill package from a specialization string."""
    golden_spec = _read_ref("golden-template-spec.md")
    checklist = _read_ref("quality-checklist.md")

    system = _GENERATE_SYSTEM.format(
        golden_template_spec=golden_spec,
        quality_checklist=checklist,
    )

    try:
        client = AsyncAnthropic()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Anthropic client unavailable: {e}") from e

    user_msg = f"Generate a complete skill package for this domain:\n\n{req.specialization}"

    for attempt in range(2):
        try:
            resp = await client.messages.create(
                model=model_for("spec_assistant"),
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": user_msg}],
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"LLM call failed: {e}") from e

        raw = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
        stop_reason = getattr(resp, "stop_reason", None)
        logger.info("generate-skill attempt=%d stop_reason=%s raw_len=%d", attempt, stop_reason, len(raw))

        # Extract JSON from fenced block
        pkg = None
        for match in _JSON_BLOCK_RE.finditer(raw):
            try:
                pkg = json.loads(match.group(1))
                break
            except json.JSONDecodeError:
                continue

        if not pkg:
            # Try parsing the entire response as JSON
            try:
                pkg = json.loads(raw)
            except json.JSONDecodeError:
                pass

        if not pkg:
            # Try extracting JSON that may have been truncated (missing closing fence)
            json_start = raw.find("```json")
            if json_start >= 0:
                json_body = raw[json_start + 7:].strip()
                # Try to find the outermost { ... } even without closing fence
                brace_start = json_body.find("{")
                if brace_start >= 0:
                    try:
                        pkg = json.loads(json_body[brace_start:])
                    except json.JSONDecodeError:
                        pass

        if not pkg:
            if attempt == 0:
                user_msg = "Your response was not valid JSON or was truncated. Please output ONLY a compact JSON object inside a ```json fence. Keep all values short."
                continue
            return GenerateSkillResponse(validation_issues=["Failed to parse JSON from LLM response"])

        name = pkg.get("name", "generated-skill")
        title = pkg.get("title", name.replace("-", " ").title())
        description = pkg.get("description", req.specialization[:250])
        allowed_tools = pkg.get("allowed_tools", "Read Write Bash(python *)")
        body = pkg.get("body", "")
        supporting_files = pkg.get("supporting_files", {})

        skill_md = _assemble_skill_md(name, title, description, allowed_tools, body)

        passed, issues = await _validate_package(skill_md, supporting_files)

        # Accept if validation passed, or if we have supporting files
        # (minor validation issues are better than a degraded retry)
        if passed or attempt == 1 or supporting_files:
            # Auto-save as candidate seed
            try:
                from skillforge.db.queries import save_candidate_seed
                import uuid as _uuid
                await save_candidate_seed(
                    id=str(_uuid.uuid4()),
                    source="generated",
                    title=title,
                    specialization=req.specialization,
                    skill_md_content=skill_md,
                    supporting_files=supporting_files,
                    traits=[],
                )
                logger.info("auto-saved generated package as candidate seed: %s", name)
            except Exception as e:
                logger.warning("failed to auto-save candidate seed: %s", e)

            return GenerateSkillResponse(
                name=name,
                title=title,
                skill_md_content=skill_md,
                supporting_files=supporting_files,
                validation_passed=passed,
                validation_issues=issues,
            )

        # Only retry if we got no supporting files at all
        user_msg = (
            f"The generated skill package has validation issues:\n"
            + "\n".join(f"- {i}" for i in issues)
            + "\n\nPlease fix these issues and regenerate the complete JSON package."
        )
