"""Async SQLite setup and connection management.

Tables (created in Step 4):
- ``evolution_runs`` — top-level runs with JSON-blob learning_log + pareto_front
- ``skill_genomes`` — full SKILL.md content + layered fitness as JSON blobs
- ``generations`` — per-generation records with Pareto front + breeding report
- ``challenges`` — auto-generated challenges with evaluation_criteria blob
- ``competition_results`` — per Skill × Challenge results with trace blob
"""

from __future__ import annotations

import aiosqlite

from skillforge.config import DB_PATH


async def init_db() -> None:
    """Create tables if they don't exist. Implemented in Step 4."""
    raise NotImplementedError


async def get_connection() -> aiosqlite.Connection:
    """Return an async SQLite connection to ``DB_PATH``. Implemented in Step 4."""
    raise NotImplementedError


__all__ = ["init_db", "get_connection", "DB_PATH"]
