"""CRUD operations for EvolutionRun, SkillGenome, Generation, Challenge.

All queries are async and operate on the connection returned by
``database.get_connection``. Real implementations land in Step 4.
"""

from __future__ import annotations

from skillforge.models import (
    Challenge,
    CompetitionResult,
    EvolutionRun,
    Generation,
    SkillGenome,
)


async def save_run(run: EvolutionRun) -> None:
    """Upsert an EvolutionRun."""
    raise NotImplementedError


async def get_run(run_id: str) -> EvolutionRun | None:
    """Fetch a single run by ID, rehydrated with all generations + genomes."""
    raise NotImplementedError


async def list_runs(limit: int = 50) -> list[EvolutionRun]:
    """List recent runs, most recent first."""
    raise NotImplementedError


async def save_genome(genome: SkillGenome, run_id: str) -> None:
    """Persist a SkillGenome and link it to its run + generation."""
    raise NotImplementedError


async def save_generation(generation: Generation, run_id: str) -> None:
    """Persist a Generation record."""
    raise NotImplementedError


async def save_challenge(challenge: Challenge, run_id: str) -> None:
    """Persist a Challenge record."""
    raise NotImplementedError


async def save_result(result: CompetitionResult, run_id: str, gen: int) -> None:
    """Persist a CompetitionResult."""
    raise NotImplementedError


async def get_lineage(run_id: str) -> list[dict]:
    """Return lineage tree data: nodes (genomes) + edges (parent→child)."""
    raise NotImplementedError
