"""Pytest fixtures shared across test modules."""

from __future__ import annotations

import os

# Disable invite gating for the whole test suite — tests exercise the
# evolve endpoints directly and shouldn't need to thread an invite code
# through every payload. Must be set BEFORE skillforge.config imports.
os.environ.setdefault("SKILLFORGE_GATING_DISABLED", "1")

import pytest  # noqa: E402


@pytest.fixture
def temp_db_path(tmp_path):
    """Return a temp SQLite path for database tests."""
    return tmp_path / "test.db"
