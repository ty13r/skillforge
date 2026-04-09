"""Spawner — creates gen 0 populations and breeds next generations.

Gen 0: reads the golden template from ``config.GOLDEN_TEMPLATE_DIR`` and
``bible/patterns/*.md``, generates ``pop_size`` diverse Skills varying content
while preserving structure.

Gen 1+: takes parent genomes + breeding instructions from the Breeder and
produces child Skills. The Spawner MUST enforce all authoring constraints
from ``engine.sandbox.validate_skill_structure``.

Implemented in Step 6b.
"""

from __future__ import annotations

from skillforge.models import SkillGenome


async def spawn_gen0(specialization: str, pop_size: int) -> list[SkillGenome]:
    """Generate ``pop_size`` diverse gen 0 Skills for the specialization."""
    raise NotImplementedError


async def breed_next_gen(
    parents: list[SkillGenome],
    learning_log: list[str],
    breeding_instructions: str,
) -> list[SkillGenome]:
    """Produce a child population from parents + Breeder's instructions."""
    raise NotImplementedError
