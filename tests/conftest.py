"""Pytest fixtures shared across test modules."""

from __future__ import annotations

import pytest


@pytest.fixture
def temp_db_path(tmp_path):
    """Return a temp SQLite path for database tests."""
    return tmp_path / "test.db"
