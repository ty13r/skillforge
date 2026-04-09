"""Idempotent loader for the curated Gen 0 Skill library.

Loads `skillforge.seeds.SEED_SKILLS` into the database as a synthetic
EvolutionRun with id='seed-library'. Reuses the existing schema — no
special-casing on the read path: the Registry, skill-detail view, export
endpoints, and fork-and-evolve flow all work against the standard run
tables.

Idempotency: computes a SHA-256 hash of the seed content. On boot, if the
stored run's hash matches, the loader skips. If the hash differs (seeds
were edited), the loader deletes and recreates the run with the new content.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime

from skillforge.db.queries import get_run, save_run
from skillforge.models import EvolutionRun, Generation, SkillGenome
from skillforge.seeds import SEED_SKILLS

logger = logging.getLogger(__name__)

SEED_RUN_ID = "seed-library"
SEED_RUN_MODE = "curated"
SEED_RUN_SPECIALIZATION = "Curated Gen 0 Skill Library"


def _content_hash() -> str:
    """SHA-256 over the seed list, for change detection."""
    payload = json.dumps(
        [
            {
                "id": s["id"],
                "slug": s["slug"],
                "title": s["title"],
                "category": s["category"],
                "difficulty": s["difficulty"],
                "frontmatter": s["frontmatter"],
                "skill_md_content": s["skill_md_content"],
                "supporting_files": s.get("supporting_files", {}),
                "traits": s.get("traits", []),
                "meta_strategy": s.get("meta_strategy", ""),
            }
            for s in SEED_SKILLS
        ],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_genome(seed: dict) -> SkillGenome:
    """Convert a seed dict into a SkillGenome suitable for DB storage."""
    return SkillGenome(
        id=seed["id"],
        generation=0,
        skill_md_content=seed["skill_md_content"],
        frontmatter=seed["frontmatter"],
        supporting_files=seed.get("supporting_files", {}),
        traits=seed.get("traits", []),
        meta_strategy=seed.get("meta_strategy", ""),
        maturity="hardened",  # curated seeds ship as hardened by default
    )


def _build_seed_run() -> EvolutionRun:
    """Assemble the synthetic seed-library run."""
    genomes = [_build_genome(s) for s in SEED_SKILLS]
    generation = Generation(
        number=0,
        skills=genomes,
        results=[],
        best_fitness=0.0,
        avg_fitness=0.0,
    )
    return EvolutionRun(
        id=SEED_RUN_ID,
        mode=SEED_RUN_MODE,
        specialization=(
            f"{SEED_RUN_SPECIALIZATION} · {len(genomes)} production-ready "
            f"skills across Data Engineering, Web Development, DevOps, Code "
            f"Quality, Security, and Documentation. Hash: {_content_hash()[:12]}"
        ),
        population_size=len(genomes),
        num_generations=1,
        generations=[generation],
        status="complete",
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        best_skill=genomes[0] if genomes else None,
        total_cost_usd=0.0,
        max_budget_usd=0.0,
    )


async def load_seeds() -> None:
    """Idempotently load seeds into the DB.

    Safe to call on every boot. Skips if the stored seed-library run's
    specialization string already contains the current content hash.
    """
    existing = await get_run(SEED_RUN_ID)
    current_hash = _content_hash()
    if existing is not None and current_hash[:12] in existing.specialization:
        logger.info("seed_loader: seeds unchanged, skipping reload")
        return

    run = _build_seed_run()
    await save_run(run)
    logger.info(
        "seed_loader: loaded %d seeds into run '%s'",
        len(SEED_SKILLS),
        SEED_RUN_ID,
    )
