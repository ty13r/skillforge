"""Shared Spawner helpers — bible reading, response extraction, debug dumps,
genome parsing, auto-repair, structural validation, and the streaming LLM call.

Extracted from the monolithic spawner so the per-entry-point modules
(``gen0``, ``breed``, ``from_parent``, ``variant``) share one private
implementation layer without re-declaring helpers.
"""

from __future__ import annotations

import re
import uuid

from anthropic import AsyncAnthropic

from skillforge.config import ANTHROPIC_API_KEY, model_for
from skillforge.engine.sandbox import validate_skill_structure
from skillforge.models import SkillGenome

# Pulls ${CLAUDE_SKILL_DIR}/<relative/path> references out of a SKILL.md body.
# Must match the regex in ``engine.sandbox.validate_skill_structure`` rule 8.
_REF_PATH_RE = re.compile(r"\$\{CLAUDE_SKILL_DIR\}/([^\s`)\"']+)")


def _read_bible_patterns() -> str:
    """Concatenate all .md files under BIBLE_DIR/patterns in sorted order.

    Returns empty string if the directory doesn't exist or is empty.
    Looks up BIBLE_DIR through the package namespace so tests that
    monkeypatch ``skillforge.agents.spawner.BIBLE_DIR`` intercept the
    lookup.
    """
    from skillforge.agents import spawner as _pkg

    patterns_dir = _pkg.BIBLE_DIR / "patterns"
    if not patterns_dir.exists():
        return ""

    parts: list[str] = []
    for p in sorted(patterns_dir.glob("*.md")):
        try:
            parts.append(p.read_text())
        except (OSError, UnicodeDecodeError):
            continue

    return "\n\n---\n\n".join(parts)


def _extract_response_text(response) -> str:
    """Extract text from an Anthropic Messages API response.

    The response's ``content`` is a list of content blocks; extract any
    that have a ``.text`` attribute.
    """
    if not response.content:
        return ""
    parts: list[str] = []
    for block in response.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _save_debug_response(label: str, text: str) -> None:
    """Write the last raw LLM response to /tmp for post-hoc debugging.

    Non-fatal — any write error is silently swallowed. This is for
    diagnosing parse failures during live runs; in production the text
    is ephemeral.
    """
    try:
        from pathlib import Path

        path = Path("/tmp") / f"sf-{label}.txt"
        path.write_text(text)
    except OSError:
        pass


def _parse_genomes(
    raw: list[dict],
    generation: int,
    parent_ids: list[str] | None = None,
) -> list[SkillGenome]:
    """Convert raw dicts from Claude's response into SkillGenome objects."""
    genomes: list[SkillGenome] = []
    for item in raw:
        genome = SkillGenome(
            id=str(uuid.uuid4()),
            generation=generation,
            skill_md_content=item.get("skill_md_content", ""),
            supporting_files=item.get("supporting_files", {}),
            traits=item.get("traits", []),
            meta_strategy=item.get("meta_strategy", ""),
            parent_ids=parent_ids or item.get("parent_ids", []),
            mutations=item.get("mutations", []),
            mutation_rationale=item.get("mutation_rationale", ""),
            maturity="draft",
        )
        genomes.append(genome)
    return genomes


async def _generate(prompt: str) -> str:
    """Streaming Anthropic API call. Returns the full assistant text response.

    The Spawner generates structured JSON output containing multiple
    SKILL.md files (up to ~5KB per skill × pop_size = 25KB+ at pop_size=5).
    Non-streaming requests get server-disconnected around the 3-4 minute
    mark on prompts this size. Streaming keeps the connection alive via
    incremental chunks and handles long generations reliably.

    ``max_tokens`` is 32000 to fit a full population of rich SKILL.md
    files with supporting scripts. Claude Sonnet 4.6 supports up to 64K
    output tokens in streaming mode; 32K is plenty while keeping a sane
    ceiling.
    """
    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY, timeout=600.0)
    parts: list[str] = []
    async with client.messages.stream(
        model=model_for("spawner"),
        max_tokens=32000,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for text in stream.text_stream:
            parts.append(text)
    return "".join(parts)


def _auto_repair_missing_references(genome: SkillGenome) -> int:
    """Stub out ``${CLAUDE_SKILL_DIR}/<path>`` refs missing from supporting_files.

    Cheap-tier Haiku routinely emits SKILL.md bodies that reference
    ``references/*-guide.md`` in prose but forget to include the file in
    ``supporting_files``. Validator rule 8 rejects those genomes, which
    in atomic mode (pop=2, 1 retry) was killing the whole run 1-of-3
    times.

    Rather than burn another LLM call on a retry that often reproduces
    the same oversight, we stub each missing reference with a minimal
    placeholder. The skill still renders, the reference still resolves
    at runtime, and the genome passes validation. The Breeder can flesh
    out the stubs in later generations if fitness signal suggests they
    carry weight.

    Returns the count of paths that were stubbed (0 if everything
    already resolved, which is the expected Sonnet-tier case).
    """
    stubbed = 0
    for match in _REF_PATH_RE.finditer(genome.skill_md_content):
        rel_path = match.group(1).rstrip(".,;:)")
        if rel_path in genome.supporting_files:
            continue
        filename = rel_path.rsplit("/", 1)[-1]
        placeholder_title = filename.removesuffix(".md").replace("-", " ").title()
        genome.supporting_files[rel_path] = (
            f"# {placeholder_title}\n\n"
            f"_Placeholder — stubbed by the spawner's auto-repair pass "
            f"because the generating LLM referenced this file but did not "
            f"emit its contents. Replace with domain-specific material "
            f"during a later generation._\n"
        )
        stubbed += 1
    return stubbed


def _validate_genomes(
    genomes: list[SkillGenome],
) -> tuple[list[SkillGenome], dict[int, list[str]]]:
    """Validate each genome; returns (valid_genomes, {idx: violations}).

    Runs the reference-path auto-repair pass before validation so
    cheap-tier LLM drift on rule 8 (missing supporting_files entries)
    doesn't kill a whole population. The repair only adds files; it
    never touches the skill_md body.
    """
    valid: list[SkillGenome] = []
    invalid: dict[int, list[str]] = {}
    for i, genome in enumerate(genomes):
        _auto_repair_missing_references(genome)
        violations = validate_skill_structure(genome)
        if violations:
            invalid[i] = violations
        else:
            valid.append(genome)
    return valid, invalid
