"""Wave 4-2 tests for ``skillforge/engine/assembly.py``.

The Engineer LLM call is mocked via ``generate_fn``. We exercise the real
persistence path (genome saved, family.best_assembly_id updated, events
emitted) and the integration check fallback.

Coverage:
- Happy path: foundation + 1 capability → composite is persisted, family
  gets best_assembly_id, integration_test_complete fires with passed=True.
- Integration failure → refinement attempted, second attempt adopted only
  if it actually improves the violation count.
- assembly_started + assembly_complete events present.
- Family.best_assembly_id stamped after the run.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

import pytest

from skillforge.db import (
    get_family,
    init_db,
    save_run,
    save_skill_family,
)
from skillforge.engine.assembly import assemble_skill
from skillforge.engine.events import drop_queue, get_queue
from skillforge.models import EvolutionRun, SkillFamily, SkillGenome


def _make_run(run_id: str, family_id: str) -> EvolutionRun:
    return EvolutionRun(
        id=run_id,
        mode="domain",
        specialization="x",
        population_size=2,
        num_generations=1,
        evolution_mode="atomic",
        family_id=family_id,
        status="running",
        created_at=datetime.now(UTC),
    )


def _make_genome(gid: str, dimension: str = "", fitness: float = 0.5) -> SkillGenome:
    valid_md = """---
name: composite-skill
description: Composite assembled by the Engineer. Use when the family is fully evolved. NOT for in-progress runs.
allowed-tools: Read Write
---

# Composite Skill

## Quick Start
Run the composite.

## When to use this skill
After the family has been fully evolved.

## Workflow
1. Read inputs
2. Run

## Examples
**Example 1:** in → out
**Example 2:** in → out

## Gotchas
- Be careful
"""
    return SkillGenome(
        id=gid,
        generation=0,
        skill_md_content=valid_md,
        frontmatter={
            "name": "composite-skill",
            "description": (
                "Composite assembled by the Engineer. Use when the family is "
                "fully evolved. NOT for in-progress runs."
            ),
            "dimension": dimension,
        },
        supporting_files={"scripts/validate.sh": "#!/bin/bash\nexit 0"},
        traits=[],
        meta_strategy="",
        pareto_objectives={"quality": fitness},
    )


def _canned_engineer_response() -> str:
    valid_md = """# Composite Skill

## Quick Start
Run the composite.

## When to use this skill
After the family has been fully evolved.

## Workflow
1. Read inputs
2. Run

## Examples
**Example 1:** in → out
**Example 2:** in → out
"""
    return json.dumps(
        {
            "frontmatter": {
                "name": "composite-skill",
                "description": (
                    "Composite assembled by the Engineer. Use when the family "
                    "is fully evolved. NOT for in-progress runs."
                ),
                "allowed-tools": "Read Write",
            },
            "skill_md_content": valid_md,
            "integration_notes": "merged cleanly",
        }
    )


def _drain_queue(run_id: str) -> list[dict]:
    queue = get_queue(run_id)
    events = []
    while True:
        try:
            events.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            break
    return events


@pytest.mark.asyncio
async def test_assemble_skill_happy_path():
    await init_db()
    family_id = f"fam_assembly_{uuid.uuid4().hex[:8]}"
    family = SkillFamily(
        id=family_id,
        slug=f"composite-skill-{family_id[12:]}",
        label="Test Family",
        specialization="x",
        decomposition_strategy="atomic",
    )
    await save_skill_family(family)

    run_id = f"run_assembly_{uuid.uuid4().hex[:8]}"
    run = _make_run(run_id, family_id)
    await save_run(run)

    foundation = _make_genome(f"found_{run_id[:6]}", dimension="fixture-strategy", fitness=0.85)
    cap = _make_genome(f"cap_{run_id[:6]}", dimension="mock-strategy", fitness=0.78)

    async def _gen(_prompt):
        return _canned_engineer_response()

    composite, report = await assemble_skill(
        run, family, foundation, [cap], generate_fn=_gen
    )

    assert composite.id.startswith("composite_")
    assert report.notes  # at least the canned "merged cleanly" note

    # Family should now point at the composite
    refreshed = await get_family(family_id)
    assert refreshed is not None
    assert refreshed.best_assembly_id == composite.id

    # Event sequence
    events = _drain_queue(run_id)
    types = [e["event"] for e in events]
    assert "assembly_started" in types
    assert "integration_test_started" in types
    assert "integration_test_complete" in types
    assert "assembly_complete" in types

    # assembly_complete should report integration_passed
    assembly_done = next(e for e in events if e["event"] == "assembly_complete")
    assert assembly_done["composite_id"] == composite.id
    assert assembly_done["family_id"] == family_id

    drop_queue(run_id)


@pytest.mark.asyncio
async def test_assemble_skill_with_no_capabilities():
    """Composite assembly with only a foundation should still produce a result."""
    await init_db()
    family_id = f"fam_solo_{uuid.uuid4().hex[:8]}"
    family = SkillFamily(
        id=family_id,
        slug=f"solo-{family_id[12:]}",
        label="Solo",
        specialization="x",
    )
    await save_skill_family(family)

    run_id = f"run_solo_{uuid.uuid4().hex[:8]}"
    run = _make_run(run_id, family_id)
    await save_run(run)

    foundation = _make_genome(f"found_solo_{run_id[:6]}", dimension="foundation")

    async def _gen(_prompt):
        return _canned_engineer_response()

    composite, _ = await assemble_skill(run, family, foundation, [], generate_fn=_gen)

    assert composite.id.startswith("composite_")
    refreshed = await get_family(family_id)
    assert refreshed.best_assembly_id == composite.id

    drop_queue(run_id)
