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

import json
import re

from anthropic import AsyncAnthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from skillforge.config import model_for

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
