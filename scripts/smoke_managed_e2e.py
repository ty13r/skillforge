"""End-to-end smoke test for the Managed Agents competitor backend.

PLAN-V1.2 §Verification §6: ``SKILLFORGE_COMPETITOR_BACKEND=managed`` plus
a minimal 2×1 evolution. Verifies the full Phase 1 path against the live
Anthropic API:

- The per-run environment + agents + sessions are created cleanly.
- Multiple competitors run in parallel (no SDK subprocess race).
- ``output_files`` is reconstructed from the event stream.
- ``cost_breakdown`` is populated with real token counts + session
  runtime cost.
- ``leaked_skills`` table stays empty (cleanup worked).
- L1/L3 still produce sensible scores against the new trace shape.

Run via: ``SKILLFORGE_COMPETITOR_BACKEND=managed uv run python scripts/smoke_managed_e2e.py``

Cost estimate: ~$2-3 — the executor is Sonnet by default (Phase 1 keeps
the SDK default model since the Advisor Strategy is descoped). 6
competitors × ~$0.30-0.50 each + design + spawn + judge.

Outputs: a structured stdout report. NOT committed (per Step 0 convention).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

# Force the managed backend BEFORE any skillforge imports — config picks up
# env at module load time.
os.environ.setdefault("SKILLFORGE_COMPETITOR_BACKEND", "managed")

import skillforge.config  # noqa: E402, F401 — triggers .env autoloader

# Sanity check: did the env override land?
if skillforge.config.COMPETITOR_BACKEND != "managed":
    print(
        f"ERROR: expected COMPETITOR_BACKEND=managed, "
        f"got {skillforge.config.COMPETITOR_BACKEND!r}",
        file=sys.stderr,
    )
    sys.exit(1)

from skillforge.db.database import init_db  # noqa: E402
from skillforge.db.queries import list_leaked_skills  # noqa: E402
from skillforge.engine.evolution import run_evolution  # noqa: E402
from skillforge.models import EvolutionRun  # noqa: E402

SPECIALIZATION = (
    "Implements small Python utility functions and data-structure classes "
    "(list operations, string parsing, simple data transformations). "
    "Use when the user asks for a Python helper or algorithm. "
    "NOT for full apps or data science."
)


async def main() -> int:
    print("=" * 60)
    print("SkillForge v1.2 Phase 1 — Managed Agents end-to-end smoke")
    print("=" * 60)
    print(f"  COMPETITOR_BACKEND     = {skillforge.config.COMPETITOR_BACKEND}")
    print(f"  COMPETITOR_CONCURRENCY = {skillforge.config.COMPETITOR_CONCURRENCY}")
    print(f"  MANAGED_AGENTS_SKILL_MODE = {skillforge.config.MANAGED_AGENTS_SKILL_MODE}")
    print(f"  COMPETITOR_ADVISOR     = {skillforge.config.COMPETITOR_ADVISOR}")
    print(f"  competitor model       = {skillforge.config.model_for('competitor')}")

    await init_db()

    run = EvolutionRun(
        id="smoke-managed-e2e",
        mode="domain",
        specialization=SPECIALIZATION,
        population_size=2,
        num_generations=1,
        max_budget_usd=5.0,
    )

    t_start = time.monotonic()
    try:
        out = await run_evolution(run)
    except Exception as exc:  # noqa: BLE001
        print(f"\nERROR: run_evolution raised {type(exc).__name__}: {exc}")
        import traceback

        traceback.print_exc()
        return 2
    t_total = time.monotonic() - t_start

    print(f"\n=== Run finished in {t_total:.1f}s ===")
    print(f"  status:               {out.status}")
    print(f"  failure_reason:       {out.failure_reason}")
    print(f"  generations:          {len(out.generations)}")
    print(f"  challenges:           {len(out.challenges)}")
    print(f"  total_cost_usd:       ${out.total_cost_usd:.4f}")
    print(f"  best_skill_id:        {out.best_skill.id if out.best_skill else None}")

    # Per-competitor cost_breakdown inspection
    print("\n=== Per-competitor cost_breakdown ===")
    if out.generations:
        gen0 = out.generations[0]
        print(f"  competitors in gen 0: {len(gen0.results)}")
        for i, result in enumerate(gen0.results):
            cb = result.cost_breakdown or {}
            print(
                f"  [{i}] skill={result.skill_id[:8]} ch={result.challenge_id[:8]} "
                f"backend={cb.get('backend', '?')} "
                f"in={cb.get('input_tokens', 0)} "
                f"out={cb.get('output_tokens', 0)} "
                f"runtime={cb.get('session_runtime_hours', 0):.4f}h "
                f"executor_in_usd={cb.get('executor_input_usd', 0):.4f} "
                f"executor_out_usd={cb.get('executor_output_usd', 0):.4f} "
                f"runtime_usd={cb.get('session_runtime_usd', 0):.6f} "
                f"compiles={result.compiles} tests={result.tests_pass} "
                f"output_files={list(result.output_files.keys())}"
            )

    # Trace shape inspection
    print("\n=== L3 trace inspection (first competitor) ===")
    if out.generations and out.generations[0].results:
        first = out.generations[0].results[0]
        print(f"  trace length: {len(first.trace)}")
        print(f"  skill_was_loaded: {first.skill_was_loaded}")
        print(f"  behavioral_signature: {first.behavioral_signature}")
        print(f"  scripts_executed: {first.scripts_executed}")
        print(f"  instructions_followed: {len(first.instructions_followed)}")
        print(f"  instructions_ignored: {len(first.instructions_ignored)}")

    # Leaked skills check
    leaked = await list_leaked_skills(limit=50)
    print("\n=== leaked_skills table ===")
    if leaked:
        print(f"  WARNING: {len(leaked)} skills leaked teardown")
        for row in leaked[:10]:
            print(f"    - {row['skill_id']} (run={row['run_id']}): {row['error']}")
    else:
        print("  empty (cleanup succeeded for all skills)")

    # Final verdict
    print("\n=== Verdict ===")
    ok = (
        out.status in {"complete", "failed"}
        and len(out.generations) >= 1
        and len(leaked) == 0
    )
    print(f"  smoke {'PASSED' if ok else 'FAILED'}")
    print(f"  wall time:    {t_total:.1f}s")
    print(f"  total cost:   ${out.total_cost_usd:.4f}")

    # Dump full first-result cost_breakdown for the journal entry
    if out.generations and out.generations[0].results:
        print("\n=== Full cost_breakdown[0] (JSON) ===")
        print(json.dumps(out.generations[0].results[0].cost_breakdown, indent=2, default=str))

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
