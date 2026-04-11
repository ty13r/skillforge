"""Taxonomist agent (v2.0 Wave 2-1).

At run submission time the Taxonomist takes a free-form specialization,
the current taxonomy tree, and the list of existing skill families, then
returns a ``TaxonomistOutput`` dataclass describing:

- ``classification`` — which ``(domain, focus, language)`` slugs the skill
  maps to, whether each is reused from the existing taxonomy or newly
  proposed
- ``family`` — a ``SkillFamily`` shell (slug + label + specialization)
- ``evolution_mode`` — ``"atomic"`` when ≥ 2 independent variant dimensions
  exist, else ``"molecular"``
- ``variant_dimensions`` — list of ``(name, tier, description,
  evaluation_focus)`` tuples (empty for molecular mode)
- ``reuse_recommendations`` — zero or more existing variants from related
  families that could be plugged in instead of re-evolved
- ``justification`` — a human-readable rationale for every new taxonomy
  node the model proposes

The agent does ONE Anthropic Messages API call via ``stream_text`` (same
shape as the Challenge Designer). Parses the JSON reply, validates every
slug, persists any new taxonomy nodes + the family, and returns the
structured output. Callers in ``skillforge/api/routes.py`` then stamp
``EvolutionRun.family_id`` and ``EvolutionRun.evolution_mode`` before
kicking off the evolution loop.

This module is imported by the REST API entry point, not by the evolution
engine inner loop — it runs once per run submission.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from anthropic import AsyncAnthropic

from skillforge.agents._llm import stream_text
from skillforge.config import ANTHROPIC_API_KEY, model_for
from skillforge.db.queries import (
    get_family_by_slug,
    get_taxonomy_node_by_slug,
    save_skill_family,
    save_taxonomy_node,
)
from skillforge.models import SkillFamily, TaxonomyNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------


@dataclass
class VariantDimension:
    """One dimension the Scientist will design a focused challenge for."""

    name: str
    tier: str  # foundation | capability
    description: str
    evaluation_focus: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "tier": self.tier,
            "description": self.description,
            "evaluation_focus": self.evaluation_focus,
        }


@dataclass
class ReuseRecommendation:
    """A variant from a related family that could be plugged in as-is."""

    source_family_slug: str
    dimension: str
    variant_slug: str
    fitness: float | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_family_slug": self.source_family_slug,
            "dimension": self.dimension,
            "variant_slug": self.variant_slug,
            "fitness": self.fitness,
            "reason": self.reason,
        }


@dataclass
class TaxonomistOutput:
    """Complete result of a classification + decomposition call."""

    family: SkillFamily
    domain: TaxonomyNode
    focus: TaxonomyNode
    language: TaxonomyNode
    evolution_mode: str  # atomic | molecular
    variant_dimensions: list[VariantDimension] = field(default_factory=list)
    reuse_recommendations: list[ReuseRecommendation] = field(default_factory=list)
    created_new_nodes: list[str] = field(default_factory=list)
    justification: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family.to_dict(),
            "domain": self.domain.to_dict(),
            "focus": self.focus.to_dict(),
            "language": self.language.to_dict(),
            "evolution_mode": self.evolution_mode,
            "variant_dimensions": [d.to_dict() for d in self.variant_dimensions],
            "reuse_recommendations": [
                r.to_dict() for r in self.reuse_recommendations
            ],
            "created_new_nodes": list(self.created_new_nodes),
            "justification": self.justification,
        }


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


_OUTPUT_SCHEMA = """{
  "classification": {
    "domain": {"slug": "existing-or-new-slug", "label": "Display Label", "reused": true | false, "justification": "..."},
    "focus":  {"slug": "existing-or-new-slug", "label": "Display Label", "reused": true | false, "justification": "..."},
    "language": {"slug": "existing-or-new-slug", "label": "Display Label", "reused": true | false, "justification": "..."}
  },
  "family": {
    "slug": "kebab-case-family-slug",
    "label": "Display Label",
    "decomposition_strategy": "atomic" | "molecular",
    "tags": ["optional", "tags"]
  },
  "variant_dimensions": [
    {
      "name": "dimension-slug",
      "tier": "foundation" | "capability",
      "description": "one sentence describing what this dimension controls",
      "evaluation_focus": "what metric the Scientist should score"
    }
  ],
  "reuse_recommendations": [
    {
      "source_family_slug": "existing-family-slug",
      "dimension": "mock-strategy",
      "variant_slug": "responses-lib-mock",
      "fitness": 0.89,
      "reason": "proven mock strategy in a sibling family"
    }
  ],
  "justification": "overall rationale for the decomposition + any new nodes"
}"""


def _render_existing_taxonomy(nodes: list[TaxonomyNode]) -> str:
    """Render the existing taxonomy as a compact tree for the prompt."""
    domains = [n for n in nodes if n.level == "domain"]
    focuses = [n for n in nodes if n.level == "focus"]
    languages = [n for n in nodes if n.level == "language"]

    lines: list[str] = []
    for dom in sorted(domains, key=lambda n: n.slug):
        lines.append(f"- domain `{dom.slug}` — {dom.label}")
        for foc in sorted(
            (f for f in focuses if f.parent_id == dom.id), key=lambda n: n.slug
        ):
            lines.append(f"  - focus `{foc.slug}` — {foc.label}")
            for lng in sorted(
                (la for la in languages if la.parent_id == foc.id),
                key=lambda n: n.slug,
            ):
                lines.append(f"    - language `{lng.slug}` — {lng.label}")
    if not lines:
        return "(empty — no taxonomy nodes exist yet)"
    return "\n".join(lines)


def _render_existing_families(families: list[SkillFamily]) -> str:
    if not families:
        return "(empty — no skill families exist yet)"
    lines = [
        f"- `{f.slug}` ({f.decomposition_strategy}) — {f.specialization[:80]}"
        for f in families
    ]
    return "\n".join(lines)


def _build_system_prompt(
    specialization: str,
    taxonomy_nodes: list[TaxonomyNode],
    existing_families: list[SkillFamily],
) -> str:
    tree = _render_existing_taxonomy(taxonomy_nodes)
    fams = _render_existing_families(existing_families)
    return f"""# Taxonomist

You classify skill specializations into the SKLD three-level taxonomy
(Domain → Focus → Language) and decide whether they should be evolved
atomically (decomposed into independent variant dimensions) or
molecularly (evolved as a single unit).

## Specialization

{specialization}

## Existing taxonomy (REUSE BEFORE CREATING NEW)

{tree}

## Existing skill families

{fams}

## Rules

1. **Reuse first.** If any existing domain/focus/language slug is a
   reasonable fit for this specialization, reuse it. Set `reused: true`
   and provide a one-line justification. Never create a new slug when
   an existing one fits.

2. **Create new only with justification.** When no existing slug fits,
   propose a new kebab-case slug and set `reused: false` with a clear
   one-line explanation of why no existing entry works. New domain
   entries are rare — the domain layer should grow at most once a
   quarter. New focuses are more acceptable. Language entries are
   near-fixed.

3. **Decomposition heuristic.** If the skill has ≥ 2 meaningfully
   independent dimensions that can be evolved separately AND assembled
   into a working whole, set `decomposition_strategy: "atomic"` and
   list 2–5 dimensions in `variant_dimensions`. Otherwise set
   `decomposition_strategy: "molecular"` and return an empty
   `variant_dimensions` list. A "dimension" must be independently
   testable, independently evolvable, and assemblable with the other
   dimensions.

4. **Default to molecular.** When uncertain, prefer molecular. Atomic
   evolution has real overhead (per-dimension challenges, assembly,
   integration test); it only pays off when the dimensions are
   genuinely independent.

5. **Foundation vs capability tiers.** When decomposing for atomic
   mode, at least one dimension should be `foundation` (structural
   decisions the others build on) and the rest should be `capability`
   (focused modules that plug into the foundation).

6. **Cross-family reuse.** If any existing family in a related
   domain/focus has a proven variant that fits one of the dimensions
   you identified, add it to `reuse_recommendations` so the Engineer
   can plug it in instead of re-evolving from scratch.

7. **Slugs are kebab-case.** Lowercase letters, digits, hyphens only.
   Matches regex `^[a-z0-9]+(-[a-z0-9]+)*$`.

## Output format

Return ONLY a JSON object — no prose before or after — matching this
schema exactly:

{_OUTPUT_SCHEMA}
"""


# ---------------------------------------------------------------------------
# JSON parsing (lenient — accepts fenced code blocks)
# ---------------------------------------------------------------------------


_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _extract_json_object(text: str) -> dict[str, Any]:
    """Pull a JSON object out of LLM text. Tolerates ```json fences and prose."""
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
        inner = fence.group(1).strip()
        try:
            obj = json.loads(inner)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # Greedy outermost-object match — find first `{` and matching `}` honoring
    # string-literal state so braces inside strings don't fool the scanner.
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object found in Taxonomist response")
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
                candidate = text[start : i + 1]
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict):
                        return obj
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSON object: {exc}") from exc
    raise ValueError("unterminated JSON object in Taxonomist response")


def _require_slug(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not _SLUG_RE.match(value):
        raise ValueError(
            f"{field_name!r} must be a kebab-case slug, got {value!r}"
        )
    return value


def _validate_output_shape(raw: dict[str, Any]) -> None:
    """Structural check before we try to persist anything."""
    if not isinstance(raw, dict):
        raise ValueError("Taxonomist output must be a JSON object")
    classification = raw.get("classification")
    if not isinstance(classification, dict):
        raise ValueError("`classification` must be an object")
    for level in ("domain", "focus", "language"):
        entry = classification.get(level)
        if not isinstance(entry, dict):
            raise ValueError(f"`classification.{level}` missing or not an object")
        _require_slug(entry.get("slug"), f"classification.{level}.slug")
        if not isinstance(entry.get("label"), str):
            raise ValueError(f"`classification.{level}.label` must be a string")
        if not isinstance(entry.get("reused"), bool):
            raise ValueError(f"`classification.{level}.reused` must be a boolean")

    family = raw.get("family")
    if not isinstance(family, dict):
        raise ValueError("`family` must be an object")
    _require_slug(family.get("slug"), "family.slug")
    if not isinstance(family.get("label"), str):
        raise ValueError("`family.label` must be a string")
    if family.get("decomposition_strategy") not in {"atomic", "molecular"}:
        raise ValueError(
            "`family.decomposition_strategy` must be 'atomic' or 'molecular'"
        )

    dimensions = raw.get("variant_dimensions", [])
    if not isinstance(dimensions, list):
        raise ValueError("`variant_dimensions` must be a list")
    for i, dim in enumerate(dimensions):
        if not isinstance(dim, dict):
            raise ValueError(f"variant_dimensions[{i}] must be an object")
        _require_slug(dim.get("name"), f"variant_dimensions[{i}].name")
        if dim.get("tier") not in {"foundation", "capability"}:
            raise ValueError(
                f"variant_dimensions[{i}].tier must be 'foundation' or 'capability'"
            )
        if not isinstance(dim.get("description"), str):
            raise ValueError(
                f"variant_dimensions[{i}].description must be a string"
            )

    # Atomic ⇒ dimensions must be non-empty; molecular ⇒ dimensions must be empty
    mode = family["decomposition_strategy"]
    if mode == "atomic" and len(dimensions) < 2:
        raise ValueError(
            "atomic decomposition requires at least 2 variant_dimensions"
        )
    if mode == "molecular" and dimensions:
        raise ValueError(
            "molecular decomposition must not include variant_dimensions"
        )

    recs = raw.get("reuse_recommendations", [])
    if not isinstance(recs, list):
        raise ValueError("`reuse_recommendations` must be a list")
    for i, rec in enumerate(recs):
        if not isinstance(rec, dict):
            raise ValueError(f"reuse_recommendations[{i}] must be an object")


# ---------------------------------------------------------------------------
# LLM call + persistence orchestration
# ---------------------------------------------------------------------------


async def _generate(prompt: str) -> str:
    """Streaming Anthropic API call. Same pattern as challenge_designer."""
    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY, timeout=300.0)
    return await stream_text(
        client,
        model=model_for("taxonomist"),
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )


async def _ensure_node(
    level: str,
    slug: str,
    label: str,
    parent_id: str | None,
    created_new_nodes: list[str],
) -> TaxonomyNode:
    """Lookup-or-create a taxonomy node. Records created slugs for the report."""
    existing = await get_taxonomy_node_by_slug(level, slug, parent_id)
    if existing is not None:
        return existing
    node = TaxonomyNode(
        id=f"tax_{uuid.uuid4().hex[:12]}",
        level=level,
        slug=slug,
        label=label,
        parent_id=parent_id,
        description="",
        created_at=datetime.now(UTC),
    )
    await save_taxonomy_node(node)
    created_new_nodes.append(f"{level}:{slug}")
    logger.info("taxonomist: created new %s node '%s'", level, slug)
    return node


async def classify_and_decompose(
    specialization: str,
    taxonomy_tree: list[TaxonomyNode],
    existing_families: list[SkillFamily],
    *,
    generate_fn: Any = None,
) -> TaxonomistOutput:
    """Classify a specialization and return a TaxonomistOutput.

    The ``generate_fn`` parameter is a test seam — tests pass a mock
    coroutine that returns a canned JSON string. In production it's
    unset and the function calls the real Anthropic API.
    """
    prompt = _build_system_prompt(specialization, taxonomy_tree, existing_families)

    generator = generate_fn or _generate
    text = await generator(prompt)

    try:
        raw = _extract_json_object(text)
    except ValueError:
        # One retry with a stricter instruction.
        retry = (
            "Your previous response was not parseable JSON. Respond with "
            "ONLY a single JSON object — no prose, no markdown fences — "
            "matching the schema described above.\n\n" + prompt
        )
        text = await generator(retry)
        raw = _extract_json_object(text)

    _validate_output_shape(raw)

    # Persist any new taxonomy nodes + create the family
    created_new_nodes: list[str] = []

    dom_spec = raw["classification"]["domain"]
    focus_spec = raw["classification"]["focus"]
    lang_spec = raw["classification"]["language"]

    domain = await _ensure_node(
        "domain",
        dom_spec["slug"],
        dom_spec["label"],
        None,
        created_new_nodes,
    )
    focus = await _ensure_node(
        "focus",
        focus_spec["slug"],
        focus_spec["label"],
        domain.id,
        created_new_nodes,
    )
    language = await _ensure_node(
        "language",
        lang_spec["slug"],
        lang_spec["label"],
        focus.id,
        created_new_nodes,
    )

    family_spec = raw["family"]

    # Reuse-or-create: if a family with the proposed slug already exists,
    # adopt it (the LLM is implicitly recommending we use the existing one).
    # This is the analog of the taxonomy-node reuse path and prevents the
    # UNIQUE constraint violation when the LLM proposes an existing slug.
    family = await get_family_by_slug(family_spec["slug"])
    if family is None:
        family = SkillFamily(
            id=f"fam_{uuid.uuid4().hex[:12]}",
            slug=family_spec["slug"],
            label=family_spec["label"],
            specialization=specialization,
            domain_id=domain.id,
            focus_id=focus.id,
            language_id=language.id,
            tags=list(family_spec.get("tags", [])),
            decomposition_strategy=family_spec["decomposition_strategy"],
            best_assembly_id=None,
            created_at=datetime.now(UTC),
        )
        await save_skill_family(family)
        logger.info(
            "taxonomist: created new family '%s' under %s/%s/%s",
            family.slug,
            domain.slug,
            focus.slug,
            language.slug,
        )
    else:
        logger.info(
            "taxonomist: reusing existing family '%s' (id=%s) for new run",
            family.slug,
            family.id,
        )

    dimensions = [
        VariantDimension(
            name=d["name"],
            tier=d["tier"],
            description=d["description"],
            evaluation_focus=d.get("evaluation_focus", ""),
        )
        for d in raw.get("variant_dimensions", [])
    ]

    recommendations = [
        ReuseRecommendation(
            source_family_slug=r.get("source_family_slug", ""),
            dimension=r.get("dimension", ""),
            variant_slug=r.get("variant_slug", ""),
            fitness=r.get("fitness"),
            reason=r.get("reason", ""),
        )
        for r in raw.get("reuse_recommendations", [])
    ]

    return TaxonomistOutput(
        family=family,
        domain=domain,
        focus=focus,
        language=language,
        evolution_mode=family.decomposition_strategy,
        variant_dimensions=dimensions,
        reuse_recommendations=recommendations,
        created_new_nodes=created_new_nodes,
        justification=raw.get("justification", ""),
    )
