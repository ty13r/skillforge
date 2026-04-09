"""SQLite persistence layer for evolution runs, genomes, and lineage."""

from skillforge.db.database import DB_PATH, get_connection, init_db, reset_db
from skillforge.db.queries import (
    get_lineage,
    get_run,
    list_runs,
    save_challenge,
    save_generation,
    save_genome,
    save_result,
    save_run,
)

__all__ = [
    "init_db",
    "get_connection",
    "reset_db",
    "DB_PATH",
    "save_run",
    "get_run",
    "list_runs",
    "save_genome",
    "save_generation",
    "save_challenge",
    "save_result",
    "get_lineage",
]
