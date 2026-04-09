"""Shared LLM call helper.

Wraps `AsyncAnthropic.messages.stream()` to produce a plain text response.
Streaming keeps the TCP connection alive during long generations, avoiding
the silent-drop hangs observed with non-streaming `messages.create()` on
longer judge/breeder prompts.
"""

from __future__ import annotations

from typing import Any


async def stream_text(
    client: Any,
    *,
    model: str,
    max_tokens: int,
    messages: list[dict[str, str]],
    system: str | None = None,
) -> str:
    """Call Anthropic Messages API via streaming and return the full text."""
    parts: list[str] = []
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system is not None:
        kwargs["system"] = system
    async with client.messages.stream(**kwargs) as stream:
        async for chunk in stream.text_stream:
            parts.append(chunk)
    return "".join(parts)
