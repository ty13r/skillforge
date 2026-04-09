"""JSON-safe serialization primitives shared by the model dataclasses.

This module provides datetime ↔ ISO-8601 string conversions used by the
``to_dict``/``from_dict`` methods on each dataclass. It is private to the
models package — do not import from outside ``skillforge.models``.
"""

from __future__ import annotations

from datetime import datetime


def to_iso(dt: datetime | None) -> str | None:
    """Convert a datetime to an ISO-8601 string, or return None."""
    if dt is None:
        return None
    return dt.isoformat()


def from_iso(s: str | None) -> datetime | None:
    """Parse an ISO-8601 string to a datetime, or return None.

    Handles both timezone-aware and naive inputs for robustness.
    """
    if s is None:
        return None
    dt = datetime.fromisoformat(s)
    return dt
