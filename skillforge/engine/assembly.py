"""Assembly engine (v2.0 Wave 4-2).

Thin wrapper around the Engineer agent that handles persistence + the
optional refinement pass. Called by the variant evolution orchestrator
after every dimension has produced a winning variant.

Flow:

  1. Call ``engineer.assemble_variants(foundation_genome, capability_genomes,
     family)`` to produce the composite ``SkillGenome`` + an
     ``IntegrationReport``.
  2. Persist the composite genome via ``save_genome``.
  3. Stamp ``family.best_assembly_id`` with the composite id and persist
     the family update.
  4. (Phase 4 Wave 4-2 stub) Run an integration test against the composite
     by re-using the foundation's challenge — currently a sanity check that
     ``validate_skill_structure`` returns no violations. Wave 4 polish will
     replace this with a real Competitor + Reviewer L1-L3 run on a separate
     cross-dimension challenge.
  5. If the integration check fails, perform exactly one refinement pass —
     re-call the Engineer with the conflicts log appended to the prompt.
     If still failing, ship the best-effort assembly and flag in the
     report.
  6. Return the assembled ``SkillGenome``.

The assembly engine never raises on integration failure — failures are
recorded in the report and the (possibly imperfect) composite is still
returned. Atomic mode never blocks on assembly.
"""

from __future__ import annotations

import logging
from typing import Any

from skillforge.agents.engineer import IntegrationReport, assemble_variants
from skillforge.db.queries import save_genome, save_skill_family
from skillforge.engine.events import emit
from skillforge.engine.sandbox import validate_skill_structure
from skillforge.models import SkillFamily, SkillGenome
from skillforge.models.run import EvolutionRun

logger = logging.getLogger("skillforge.engine.assembly")


async def _run_integration_check(
    composite: SkillGenome,
) -> tuple[bool, list[str]]:
    """Stub integration check — runs validate_skill_structure on the composite.

    Returns ``(passed, violations)``. Wave 4 polish will replace this with
    a real cross-dimension Competitor + Reviewer L1-L3 run; for now we
    confirm the composite is structurally valid (which is the most common
    failure mode anyway).
    """
    violations = validate_skill_structure(composite)
    return (len(violations) == 0, violations)


async def assemble_skill(
    run: EvolutionRun,
    family: SkillFamily,
    foundation: SkillGenome,
    capabilities: list[SkillGenome],
    *,
    generate_fn: Any = None,
) -> tuple[SkillGenome, IntegrationReport]:
    """Assemble a composite from the winning variants and persist it.

    Args:
        run: parent EvolutionRun (used for emit() target + persistence
            scoping).
        family: the SkillFamily this composite belongs to. Updated in place
            with ``best_assembly_id`` set to the new composite id.
        foundation: the winning foundation variant's SkillGenome.
        capabilities: list of winning capability variant genomes.
        generate_fn: test seam — if provided, used as the LLM call inside
            the Engineer instead of the real Anthropic API.

    Returns:
        ``(composite_genome, integration_report)``. Always returns a
        composite even if the integration check fails (the report records
        the failure).
    """
    await emit(
        run.id,
        "assembly_started",
        family_id=family.id,
        foundation_id=foundation.id,
        capability_count=len(capabilities),
    )

    # Step 1: Engineer call
    composite, report = await assemble_variants(
        foundation, capabilities, family, generate_fn=generate_fn
    )

    # Step 2: persist the composite genome
    await save_genome(composite, run.id)

    # Step 3: integration check
    await emit(
        run.id,
        "integration_test_started",
        composite_id=composite.id,
    )
    passed, violations = await _run_integration_check(composite)
    await emit(
        run.id,
        "integration_test_complete",
        composite_id=composite.id,
        passed=passed,
        violation_count=len(violations),
    )

    # Step 4: optional refinement pass
    refinement_attempted = False
    if not passed:
        logger.info(
            "run=%s composite %s failed integration check (%d violations); "
            "attempting one refinement pass",
            run.id[:8],
            composite.id,
            len(violations),
        )
        refinement_attempted = True
        try:
            refined, refined_report = await assemble_variants(
                foundation, capabilities, family, generate_fn=generate_fn
            )
            refined_passed, refined_violations = await _run_integration_check(refined)
            if refined_passed or len(refined_violations) < len(violations):
                # Refinement helped — adopt it
                composite = refined
                await save_genome(composite, run.id)
                report = refined_report
                report.notes = (
                    (report.notes or "")
                    + " | refinement adopted (improved violation count)"
                )
                violations = refined_violations
                passed = refined_passed
            else:
                report.notes = (
                    (report.notes or "")
                    + " | refinement did not improve violations; original kept"
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "run=%s refinement pass failed: %s — keeping original composite",
                run.id[:8],
                exc,
            )
            report.notes = (
                (report.notes or "") + f" | refinement raised: {exc}"
            )

    # Step 5: stamp family.best_assembly_id and persist
    family.best_assembly_id = composite.id
    await save_skill_family(family)

    await emit(
        run.id,
        "assembly_complete",
        family_id=family.id,
        composite_id=composite.id,
        conflict_count=report.conflict_count,
        integration_passed=passed,
        violation_count=len(violations),
        refinement_attempted=refinement_attempted,
    )

    return composite, report
