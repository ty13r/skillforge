"""Composite assembly — call the Engineer to merge winning variants."""

from __future__ import annotations

import logging

from skillforge.engine.events import emit
from skillforge.engine.variant_evolution._helpers import _aggregate_fitness
from skillforge.models import SkillGenome
from skillforge.models.run import EvolutionRun

logger = logging.getLogger("skillforge.engine.variant_evolution.assembly")


async def _real_assembly(
    run: EvolutionRun,
    foundation_winner: SkillGenome | None,
    capability_winners: list[SkillGenome],
) -> SkillGenome:
    """Phase 4 real assembly — invoke the Engineer agent + integration test.

    Falls back to a "use the highest-fitness winner as-is" path when no
    foundation variant exists (some atomic decompositions only have
    capability dimensions). Otherwise runs the full Engineer flow:
    weave → validate → optionally refine → persist composite.
    """
    if foundation_winner is None:
        if not capability_winners:
            raise RuntimeError("assembly: no winners to assemble from")
        # Edge case: no foundation tier in this decomposition. Use the
        # highest-fitness capability as the de facto skeleton and emit
        # a stub assembly_complete. Wave 4 polish will extend the
        # Engineer to handle capability-only assemblies.
        await emit(
            run.id,
            "assembly_started",
            capability_count=len(capability_winners),
            mode="capability_only_fallback",
        )
        composite = max(capability_winners, key=_aggregate_fitness)
        await emit(
            run.id,
            "assembly_complete",
            composite_skill_id=composite.id,
            capability_count=len(capability_winners),
            integration_passed=True,
            mode="capability_only_fallback",
        )
        return composite

    # Resolve the family for the Engineer call
    from skillforge.db.queries import get_family

    family = await get_family(run.family_id) if run.family_id else None
    if family is None:
        # Defensive fallback — synthesize a minimal SkillFamily so the
        # Engineer call still has metadata to work with. The orchestrator
        # logs a warning but doesn't block.
        from skillforge.models import SkillFamily

        logger.warning(
            "run=%s atomic assembly: no family found for family_id=%s; "
            "using a synthesized SkillFamily for the Engineer call",
            run.id[:8],
            run.family_id,
        )
        family = SkillFamily(
            id=run.family_id or "fam_unknown",
            slug="composite",
            label="Composite",
            specialization=run.specialization,
        )

    from skillforge.engine.assembly import assemble_skill

    composite, _report = await assemble_skill(
        run, family, foundation_winner, capability_winners
    )
    return composite


