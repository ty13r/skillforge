"""Shared helpers for the db.queries submodules.

These are internal to the package but also imported by a handful of
external call sites that manipulate connections or rows directly
(``api/bench.py``, ``api/llms.py``, ``api/taxonomy.py``, etc.). The
package ``__init__`` re-exports them so those imports keep working.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from skillforge.db.database import get_connection


@asynccontextmanager
async def _connect(db_path: Path | None = None) -> AsyncIterator[aiosqlite.Connection]:
    """Async context manager: open a connection, yield it, then close.

    This avoids the ``async with await get_connection(...)`` double-entry
    anti-pattern.  ``get_connection`` is kept for callers that need an
    already-open connection handed back (e.g., the API layer).
    """
    conn = await get_connection(db_path)
    try:
        yield conn
    finally:
        await conn.close()


def _int_or_none(v: bool | int | None) -> int | None:
    """Convert a bool/None to 0/1/None for SQLite INTEGER columns."""
    if v is None:
        return None
    return int(v)


def _row_get(row: aiosqlite.Row, column: str, default=None):
    """Defensive column lookup on an aiosqlite.Row.

    ``aiosqlite.Row`` does not implement ``dict.get()`` and indexing a
    missing column raises ``IndexError``. Used for v2.0 columns that may
    be absent on legacy databases that haven't migrated yet (init_db
    handles the migration but tests sometimes pre-build a partial schema).
    """
    try:
        return row[column]
    except (IndexError, KeyError):
        return default
