"""Assembly engine (v2.0 Wave 4-2 + post-v2.0 item 3).

Thin wrapper around the Engineer agent that handles persistence + the
optional refinement pass. Called by the variant evolution orchestrator
after every dimension has produced a winning variant.

Flow:

  1. Call ``engineer.assemble_variants(foundation_genome, capability_genomes,
     family)`` to produce the composite ``SkillGenome`` + an
     ``IntegrationReport``.
  2. Persist the composite genome via ``save_genome``.
  3. Run the integration check against the composite:
       - Static: ``validate_skill_structure(composite)`` catches structural
         violations (broken paths, size overflow, frontmatter issues).
       - Behavioral (optional, opt-in via ``enable_behavioral_check=True``):
         runs the composite through the real Competitor against the
         foundation variant's original challenge, then scores the result
         via the judging pipeline. The composite passes only if its
         aggregate fitness clears ``BEHAVIORAL_CHECK_THRESHOLD`` (0.5).
         Opt-in because it doubles the API cost of assembly; the live
         e2e test and Phase 4+ QA runs set the flag.
  4. Stamp ``family.best_assembly_id`` with the composite id and persist
     the family update.
  5. If the integration check fails, perform exactly one refinement pass —
     re-call the Engineer. Adopted only if the second attempt has
     STRICTLY fewer violations than the first.
  6. Return the assembled ``SkillGenome``.

The assembly engine never raises on integration failure — failures are
recorded in the report and the (possibly imperfect) composite is still
returned. Atomic mode never blocks on assembly.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from skillforge.agents.engineer import IntegrationReport, assemble_variants
from skillforge.db.queries import (
    get_variant_evolutions_for_run,
    save_genome,
    save_skill_family,
)
from skillforge.engine.events import emit
from skillforge.engine.sandbox import validate_skill_structure
from skillforge.models import Challenge, Generation, SkillFamily, SkillGenome
from skillforge.models.run import EvolutionRun

logger = logging.getLogger("skillforge.engine.assembly")

# The composite passes the behavioral integration check if its aggregate
# fitness on the foundation's challenge clears this threshold. Tuned to
# catch composites that outright broke the foundation's functionality
# without being so strict that minor merge drift fails the check.
BEHAVIORAL_CHECK_THRESHOLD = 0.5


async def _find_foundation_challenge(
    run_id: str,
) -> Challenge | None:
    """Look up the challenge the foundation variant was evaluated against.

    Returns the first foundation-tier variant_evolution's challenge from
    the database, or ``None`` if no foundation dimension exists for this
    run. Used by ``_run_integration_check_behavioral`` to re-run the
    composite through the foundation's original challenge — which is the
    most natural "does the composite still solve the foundation's task?"
    regression test.
    """
    from skillforge.db.queries import _connect

    vevos = await get_variant_evolutions_for_run(run_id)
    foundation_vevos = [v for v in vevos if v.tier == "foundation"]
    if not foundation_vevos:
        return None

    challenge_id = foundation_vevos[0].challenge_id
    if not challenge_id:
        return None

    async with _connect() as conn, conn.execute(
        "SELECT * FROM challenges WHERE id = ?", (challenge_id,)
    ) as cur:
        row = await cur.fetchone()

    if row is None:
        return None

    import json as _json

    return Challenge.from_dict(
        {
            "id": row["id"],
            "prompt": row["prompt"],
            "difficulty": row["difficulty"],
            "evaluation_criteria": _json.loads(row["evaluation_criteria"]),
            "verification_method": row["verification_method"],
            "setup_files": _json.loads(row["setup_files"]),
            "gold_standard_hints": row["gold_standard_hints"],
        }
    )


async def _run_integration_check(
    composite: SkillGenome,
    run: EvolutionRun | None = None,
    *,
    enable_behavioral_check: bool = False,
) -> tuple[bool, list[str]]:
    """Run the integration check on a composite.

    Always runs the structural check (``validate_skill_structure``). When
    ``enable_behavioral_check=True`` and a foundation challenge is
    discoverable, ALSO runs the composite through the real Competitor +
    judging pipeline against that challenge and requires the aggregate
    fitness to clear ``BEHAVIORAL_CHECK_THRESHOLD``.

    Returns ``(passed, violations)``. ``violations`` is a list of strings
    covering both structural violations from ``validate_skill_structure``
    and (when applicable) a ``behavioral:below_threshold=...`` entry.
    """
    violations: list[str] = list(validate_skill_structure(composite))
    passed_structural = len(violations) == 0

    if not enable_behavioral_check:
        return (passed_structural, violations)

    if run is None:
        violations.append("behavioral:no_run_context")
        return (passed_structural, violations)

    challenge = await _find_foundation_challenge(run.id)
    if challenge is None:
        # No foundation dimension to regression-test against. This is
        # not a failure — capability-only assemblies legitimately have
        # no foundation challenge — but we log it so callers know the
        # behavioral check was skipped.
        logger.info(
            "run=%s behavioral check skipped: no foundation challenge",
            run.id[:8],
        )
        return (passed_structural, violations)

    logger.info(
        "run=%s running behavioral check against foundation challenge %s",
        run.id[:8],
        challenge.id[:12],
    )

    # Run the composite through the real Competitor + judging pipeline.
    # Imports are local so the unit-test path doesn't pull in the agent
    # SDK until the behavioral check actually fires.
    from skillforge.agents.judge.pipeline import run_judging_pipeline
    from skillforge.engine.evolution import _gated_competitor

    semaphore = asyncio.Semaphore(1)
    try:
        result = await _gated_competitor(
            semaphore=semaphore,
            run_id=run.id,
            generation=0,
            competitor_idx=0,
            skill=composite,
            challenge=challenge,
            env_id=None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "run=%s behavioral check competitor failed: %s", run.id[:8], exc
        )
        violations.append(f"behavioral:competitor_failed={exc}")
        return (False, violations)

    generation = Generation(number=0, skills=[composite], results=[result])
    try:
        generation = await run_judging_pipeline(
            generation, [challenge], run_id=run.id
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "run=%s behavioral check judging failed: %s", run.id[:8], exc
        )
        violations.append(f"behavioral:judging_failed={exc}")
        return (False, violations)

    # The judging pipeline populates composite.pareto_objectives in place
    score = 0.0
    if composite.pareto_objectives:
        score = sum(composite.pareto_objectives.values()) / max(
            1, len(composite.pareto_objectives)
        )
    elif composite.deterministic_scores:
        score = sum(composite.deterministic_scores.values()) / max(
            1, len(composite.deterministic_scores)
        )

    logger.info(
        "run=%s behavioral check score=%.3f threshold=%.2f",
        run.id[:8],
        score,
        BEHAVIORAL_CHECK_THRESHOLD,
    )

    if score < BEHAVIORAL_CHECK_THRESHOLD:
        violations.append(
            f"behavioral:below_threshold={score:.3f}<{BEHAVIORAL_CHECK_THRESHOLD}"
        )
        return (False, violations)

    return (passed_structural, violations)


async def assemble_skill(
    run: EvolutionRun,
    family: SkillFamily,
    foundation: SkillGenome,
    capabilities: list[SkillGenome],
    *,
    generate_fn: Any = None,
    enable_behavioral_check: bool = False,
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
        behavioral=enable_behavioral_check,
    )
    passed, violations = await _run_integration_check(
        composite, run, enable_behavioral_check=enable_behavioral_check
    )
    await emit(
        run.id,
        "integration_test_complete",
        composite_id=composite.id,
        passed=passed,
        violation_count=len(violations),
        behavioral=enable_behavioral_check,
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
            refined_passed, refined_violations = await _run_integration_check(
                refined, run, enable_behavioral_check=enable_behavioral_check
            )
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
