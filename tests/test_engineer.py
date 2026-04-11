"""Wave 4-1 unit tests for the Engineer agent.

The LLM call is mocked via the ``generate_fn`` seam. Tests cover:

- Happy path: foundation + 2 capabilities → composite returned with the
  family slug as ``frontmatter.name``, parent_ids include all inputs, the
  IntegrationReport's ``conflict_count`` reflects the pre-scan.
- ``_detect_conflicts``: duplicate filenames + overlapping H2/H3 headers
  are picked up and renamed.
- Shape validator: rejects missing fields, oversized descriptions.
- ``assemble_variants`` raises ValueError on persistent bad LLM output
  even after one retry.
"""

from __future__ import annotations

import json

import pytest

from skillforge.agents.engineer import (
    IntegrationReport,
    _detect_conflicts,
    _validate_composite_shape,
    assemble_variants,
)
from skillforge.models import SkillFamily, SkillGenome


def _make_genome(
    gid: str,
    *,
    dimension: str = "",
    skill_md: str = "# stub\n## Workflow\nstuff",
    files: dict | None = None,
    fitness: float = 0.5,
) -> SkillGenome:
    return SkillGenome(
        id=gid,
        generation=0,
        skill_md_content=skill_md,
        frontmatter={"name": gid, "description": "x", "dimension": dimension},
        supporting_files=files or {},
        traits=[f"trait-{gid}"],
        meta_strategy="t",
        pareto_objectives={"quality": fitness},
    )


def _make_family(slug: str = "test-family") -> SkillFamily:
    return SkillFamily(
        id="fam_test",
        slug=slug,
        label="Test Family",
        specialization="x",
        decomposition_strategy="atomic",
    )


def _canned_engineer_response(
    family_slug: str = "test-family",
    extra_files: dict | None = None,
) -> str:
    fm = {
        "name": family_slug,
        "description": "Composite skill assembled from foundation + capabilities",
        "allowed-tools": "Read Write",
    }
    files = {
        "scripts/validate.sh": "#!/bin/bash\nexit 0",
        "scripts/score.py": "#!/usr/bin/env python3\nprint('{}')",
    }
    if extra_files:
        files.update(extra_files)

    return json.dumps(
        {
            "frontmatter": fm,
            "skill_md_content": (
                "# Composite\n\n## Quick Start\nDo it.\n\n"
                "## Workflow\n1. Read\n2. Run\n\n"
                "## Examples\n**Example 1:** in → out\n**Example 2:** in → out\n"
            ),
            "supporting_files": files,
            "integration_notes": "merged cleanly, no conflicts encountered",
        }
    )


# ---------------------------------------------------------------------------
# Pure unit tests
# ---------------------------------------------------------------------------


def test_detect_conflicts_finds_duplicate_files():
    foundation = _make_genome(
        "f",
        skill_md="# foundation\n## Foundation Section\nx",
        files={"scripts/validate.sh": "old", "scripts/main.py": "old"},
    )
    cap = _make_genome(
        "c1",
        dimension="mock-strategy",
        skill_md="# cap\n## Capability Section\nx",
        files={"scripts/validate.sh": "new", "scripts/extra.sh": "x"},
    )
    count, dups, overlap = _detect_conflicts(foundation, [cap])
    assert count == 1
    assert dups[0]["original"] == "scripts/validate.sh"
    assert dups[0]["renamed"] == "scripts/validate_mock-strategy.sh"
    assert dups[0]["dimension"] == "mock-strategy"
    assert overlap == []


def test_detect_conflicts_finds_overlapping_headers():
    foundation = _make_genome(
        "f", skill_md="# foo\n## Workflow\nfound\n### Step 1: Init\nx"
    )
    cap = _make_genome(
        "c1",
        skill_md="# bar\n### Step 1: Init\ndifferent",
        dimension="d1",
    )
    count, dups, overlap = _detect_conflicts(foundation, [cap])
    assert count == 1
    assert dups == []
    assert "Step 1: Init" in overlap


def test_validate_composite_shape_happy():
    raw = json.loads(_canned_engineer_response())
    _validate_composite_shape(raw)  # no exception


def test_validate_composite_shape_rejects_missing_frontmatter():
    raw = {"skill_md_content": "x", "supporting_files": {}}
    with pytest.raises(ValueError, match="frontmatter"):
        _validate_composite_shape(raw)


def test_validate_composite_shape_rejects_oversize_description():
    raw = json.loads(_canned_engineer_response())
    raw["frontmatter"]["description"] = "x" * 300
    with pytest.raises(ValueError, match="> 250"):
        _validate_composite_shape(raw)


# ---------------------------------------------------------------------------
# assemble_variants — full path with mocked LLM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assemble_variants_happy_path():
    foundation = _make_genome(
        "found",
        skill_md="# found\n## Quick Start\nQ\n## Workflow\n1. Step",
        files={"scripts/validate.sh": "fnd", "scripts/score.py": "fnd"},
        fitness=0.85,
    )
    cap1 = _make_genome(
        "cap1",
        dimension="mock-strategy",
        skill_md="# cap1\n## Workflow\nmocking guidance",
        files={"scripts/validate.sh": "cap"},  # collides → renamed
        fitness=0.78,
    )
    cap2 = _make_genome(
        "cap2",
        dimension="assertion-style",
        skill_md="# cap2\n## Workflow\nassertion guidance",
        files={"scripts/asserts.py": "x"},
        fitness=0.80,
    )
    family = _make_family("py-pytest-composite")

    async def _gen(_prompt):
        return _canned_engineer_response(family_slug="py-pytest-composite")

    composite, report = await assemble_variants(
        foundation, [cap1, cap2], family, generate_fn=_gen
    )

    assert composite.frontmatter["name"] == "py-pytest-composite"
    assert composite.id.startswith("composite_")
    assert composite.parent_ids == ["found", "cap1", "cap2"]
    assert composite.maturity == "tested"

    # Pre-scan should have caught the validate.sh collision from cap1
    assert isinstance(report, IntegrationReport)
    assert report.conflict_count >= 1
    assert any(
        d["original"] == "scripts/validate.sh"
        and d["dimension"] == "mock-strategy"
        for d in report.duplicate_files_renamed
    )


@pytest.mark.asyncio
async def test_assemble_variants_retries_on_bad_response():
    foundation = _make_genome("found")
    family = _make_family()

    call_count = {"n": 0}

    async def _gen(_prompt):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return "this is not json at all"
        return _canned_engineer_response()

    composite, _ = await assemble_variants(
        foundation, [], family, generate_fn=_gen
    )
    assert call_count["n"] == 2
    assert composite.id.startswith("composite_")


@pytest.mark.asyncio
async def test_assemble_variants_raises_when_retry_also_fails():
    foundation = _make_genome("found")
    family = _make_family()

    async def _gen(_prompt):
        return "still not json"

    with pytest.raises(ValueError):
        await assemble_variants(
            foundation, [], family, generate_fn=_gen
        )


@pytest.mark.asyncio
async def test_assemble_variants_requires_foundation():
    family = _make_family()

    async def _gen(_prompt):
        return _canned_engineer_response()

    with pytest.raises(ValueError, match="foundation"):
        await assemble_variants(None, [], family, generate_fn=_gen)
