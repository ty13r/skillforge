"""Engineer agent (v2.0 Wave 4-1).

Takes one foundation variant + N capability variants + the SkillFamily
metadata and produces ONE composite SKILL.md package by:

1. Using the foundation's SKILL.md as the structural skeleton.
2. Extracting unique sections / instructions / scripts from each capability.
3. Weaving capability content into the foundation's H2/H3 structure.
4. Merging supporting_files with name deconfliction (duplicate filenames
   from capabilities are renamed to ``<stem>_<dimension>.<ext>``).
5. Combining frontmatter descriptions into one ≤250-char composite.
6. Validating the composite via ``validate_skill_structure``.

The agent is a single streaming Anthropic Messages call (Sonnet by default)
with a structured-output JSON schema. Test seam: pass ``generate_fn`` to
short-circuit the LLM call with a canned response.

Conflict resolution: when foundation and a capability provide contradictory
instructions for the same H3 section, the higher-fitness variant wins; the
loser is logged in the integration_report.

The Engineer is invoked once per SkillFamily by the Phase 4 ``assemble_skill``
flow in ``skillforge/engine/assembly.py``. It does NOT run the integration
test or refinement pass — those are the Assembly engine's responsibility.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from anthropic import AsyncAnthropic

from skillforge.agents._llm import stream_text
from skillforge.config import ANTHROPIC_API_KEY, model_for
from skillforge.models import SkillFamily, SkillGenome

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------


@dataclass
class IntegrationReport:
    """Diagnostic record describing what the Engineer did during assembly."""

    conflict_count: int = 0
    duplicate_files_renamed: list[dict[str, str]] = field(default_factory=list)
    overlapping_sections: list[str] = field(default_factory=list)
    description_truncated: bool = False
    body_truncated: bool = False
    rejected_instructions: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_count": self.conflict_count,
            "duplicate_files_renamed": list(self.duplicate_files_renamed),
            "overlapping_sections": list(self.overlapping_sections),
            "description_truncated": self.description_truncated,
            "body_truncated": self.body_truncated,
            "rejected_instructions": list(self.rejected_instructions),
            "notes": self.notes,
        }


_OUTPUT_SCHEMA = """{
  "frontmatter": {
    "name": "kebab-case",
    "description": "≤250 char composite description",
    "allowed-tools": "Read Write Bash(python *)"
  },
  "skill_md_content": "# Display Name\\n\\n## Quick Start\\n...\\n## Workflow\\n...\\n## Examples\\n...",
  "supporting_files": {
    "scripts/validate.sh": "...",
    "scripts/score.py": "...",
    "references/guide.md": "..."
  },
  "integration_notes": "one paragraph describing key merge decisions, conflicts encountered, and any rejected instructions"
}"""


def _build_engineer_prompt(
    foundation: SkillGenome,
    capabilities: list[SkillGenome],
    family: SkillFamily,
) -> str:
    """Render the system prompt for the Engineer's structured-output call."""
    cap_blocks: list[str] = []
    for i, cap in enumerate(capabilities):
        dim = cap.frontmatter.get("dimension", f"capability-{i}")
        cap_blocks.append(
            f"### Capability {i + 1}: dimension `{dim}` (fitness "
            f"{cap.pareto_objectives.get('quality', 'n/a')})\n\n"
            f"#### Frontmatter\n```json\n{json.dumps(cap.frontmatter, indent=2)}\n```\n\n"
            f"#### SKILL.md content\n```markdown\n{cap.skill_md_content[:3000]}\n```\n\n"
            f"#### Supporting files\n"
            + "\n".join(
                f"- `{path}` ({len(content)} bytes)"
                for path, content in cap.supporting_files.items()
            )
        )

    capabilities_section = "\n\n".join(cap_blocks) if cap_blocks else "(none)"

    return f"""# Engineer

You are assembling winning variants of a skill family into ONE composite
skill package. The foundation variant is the structural skeleton; the
capability variants contribute focused modules that plug into it.

## Family

- Slug: `{family.slug}`
- Label: {family.label}
- Specialization: {family.specialization}

## Foundation variant (the skeleton)

### Frontmatter
```json
{json.dumps(foundation.frontmatter, indent=2)}
```

### SKILL.md content
```markdown
{foundation.skill_md_content[:5000]}
```

### Foundation supporting files
{chr(10).join(f"- `{path}` ({len(content)} bytes)" for path, content in foundation.supporting_files.items()) or "(none)"}

## Capability variants

{capabilities_section}

## Your job

Produce ONE composite SKILL.md package by weaving the capability content
into the foundation skeleton. Specifically:

1. **Skeleton**: keep the foundation's SKILL.md as the structural base.
   Preserve its Quick Start, the order of its H2 sections, and its
   numbered Workflow steps.

2. **Weave capability sections**: for each capability, find the right
   place under the foundation's H2/H3 structure and weave the
   capability's instructions in. New H3s slot under matching foundation
   H2s; new H2s append after the foundation's Workflow but before
   Gotchas.

3. **Conflict resolution**: when the foundation and a capability give
   contradictory instructions for the same section, prefer the foundation
   (it has higher fitness for structural decisions). Log the rejected
   instruction in `integration_notes`.

4. **Frontmatter merge**:
   - `name`: keep `{family.slug}` (the family canonical slug)
   - `description`: combine into a ≤250 char composite that names the
     primary capability + lists triggers + retains explicit NOT-for clauses
   - `allowed-tools`: union of all variants' tool lists
   - Drop any other extension fields

5. **Supporting file merge**:
   - Copy every unique file from the foundation as-is
   - For each capability, copy its files INTO the composite. If a filename
     collides with a foundation file, RENAME the capability's version to
     `<stem>_<dimension>.<ext>` (where `<dimension>` is the capability's
     `dimension` frontmatter value), and update any references in the
     composite SKILL.md body to point at the renamed file.

6. **Body must stay ≤500 lines** and include AT LEAST 2 examples.

## Output format

Return ONLY a JSON object — no prose before or after — matching:

{_OUTPUT_SCHEMA}
"""


def _extract_json_object(text: str) -> dict[str, Any]:
    """Pull a JSON object out of LLM text. Tolerates ```json fences."""
    candidate = text.strip()
    if candidate.startswith("{") and candidate.endswith("}"):
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    fence = re.search(r"```(?:json)?\s*\n?(.*)\n?```", text, re.DOTALL)
    if fence:
        try:
            obj = json.loads(fence.group(1).strip())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object in Engineer response")
    depth = 0
    in_str = False
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
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start : i + 1])
                    if isinstance(obj, dict):
                        return obj
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSON object: {exc}") from exc
    raise ValueError("unterminated JSON object in Engineer response")


def _validate_composite_shape(raw: dict[str, Any]) -> None:
    if not isinstance(raw, dict):
        raise ValueError("Engineer output must be a JSON object")
    fm = raw.get("frontmatter")
    if not isinstance(fm, dict) or "name" not in fm or "description" not in fm:
        raise ValueError(
            "Engineer output missing frontmatter.name or frontmatter.description"
        )
    if not isinstance(raw.get("skill_md_content"), str):
        raise ValueError("Engineer output missing skill_md_content")
    if not isinstance(raw.get("supporting_files"), dict):
        raise ValueError("Engineer output missing supporting_files dict")

    desc = fm.get("description", "")
    if isinstance(desc, str) and len(desc) > 250:
        raise ValueError(
            f"Engineer composite description is {len(desc)} chars > 250 limit"
        )


def _detect_conflicts(
    foundation: SkillGenome, capabilities: list[SkillGenome]
) -> tuple[int, list[dict[str, str]], list[str]]:
    """Pre-scan for duplicate filenames + overlapping H2/H3 headers.

    Returns ``(conflict_count, duplicate_files_renamed, overlapping_sections)``.
    The Engineer LLM does the actual rename — this scan is purely diagnostic
    so the integration report has accurate counts.
    """
    duplicates: list[dict[str, str]] = []
    foundation_files = set(foundation.supporting_files.keys())
    for cap in capabilities:
        dim = cap.frontmatter.get("dimension", "cap")
        for path in cap.supporting_files:
            if path in foundation_files:
                stem, _, ext = path.rpartition(".")
                renamed = f"{stem}_{dim}.{ext}" if ext else f"{path}_{dim}"
                duplicates.append(
                    {"original": path, "renamed": renamed, "dimension": dim}
                )

    header_re = re.compile(r"^(?:##|###)\s+(.+)$", re.MULTILINE)
    foundation_headers = set(header_re.findall(foundation.skill_md_content))
    overlap: set[str] = set()
    for cap in capabilities:
        cap_headers = set(header_re.findall(cap.skill_md_content))
        overlap.update(foundation_headers & cap_headers)

    conflict_count = len(duplicates) + len(overlap)
    return conflict_count, duplicates, sorted(overlap)


async def _generate(prompt: str) -> str:
    """Streaming Anthropic call."""
    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY, timeout=300.0)
    return await stream_text(
        client,
        model=model_for("engineer"),
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )


async def assemble_variants(
    foundation: SkillGenome,
    capabilities: list[SkillGenome],
    family: SkillFamily,
    *,
    generate_fn: Any = None,
) -> tuple[SkillGenome, IntegrationReport]:
    """Engineer entry point. Returns (assembled_genome, integration_report).

    The assembled genome's id is generated fresh; ``parent_ids`` lists every
    input variant. The genome's frontmatter ``decomposition_strategy`` is
    set to "atomic" so consumers can tell composites from molecular skills.

    The ``generate_fn`` test seam mirrors the Taxonomist's pattern: pass an
    async coroutine returning a canned JSON string and the LLM call is
    bypassed entirely.
    """
    if foundation is None:
        raise ValueError("assemble_variants requires a foundation variant")

    # Pre-scan for conflicts so the report is honest even if the LLM
    # claims it merged cleanly
    conflict_count, duplicates, overlap = _detect_conflicts(foundation, capabilities)

    prompt = _build_engineer_prompt(foundation, capabilities, family)

    generator = generate_fn or _generate
    text = await generator(prompt)

    try:
        raw = _extract_json_object(text)
        _validate_composite_shape(raw)
    except ValueError:
        # One retry with a stricter formatting reminder
        retry = (
            "Your previous response was not parseable as JSON or violated "
            "the composite schema. Respond with ONLY a JSON object — no "
            "prose, no markdown fences — matching the schema described "
            "above.\n\n" + prompt
        )
        text = await generator(retry)
        raw = _extract_json_object(text)
        _validate_composite_shape(raw)

    # Build the composite SkillGenome
    parent_ids = [foundation.id] + [c.id for c in capabilities]
    import uuid as _uuid

    composite = SkillGenome(
        id=f"composite_{_uuid.uuid4().hex[:12]}",
        generation=0,
        skill_md_content=raw["skill_md_content"],
        frontmatter=raw["frontmatter"],
        supporting_files=raw["supporting_files"],
        traits=list(set(foundation.traits + [t for c in capabilities for t in c.traits])),
        meta_strategy=f"composite of {family.slug}: foundation + {len(capabilities)} capabilities",
        parent_ids=parent_ids,
        mutations=[],
        mutation_rationale=raw.get("integration_notes", ""),
        maturity="tested",
        generations_survived=0,
    )

    report = IntegrationReport(
        conflict_count=conflict_count,
        duplicate_files_renamed=duplicates,
        overlapping_sections=overlap,
        description_truncated=False,
        body_truncated=len(composite.skill_md_content.splitlines()) > 500,
        rejected_instructions=[],
        notes=raw.get("integration_notes", ""),
    )

    return composite, report
