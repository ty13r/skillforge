"""Competitor backend dispatcher.

Routes ``run_competitor`` to either the local-subprocess SDK implementation
(``competitor_sdk.py``) or the cloud-managed implementation
(``competitor_managed.py``) based on the ``SKILLFORGE_COMPETITOR_BACKEND``
env var. The third positional argument means different things for each
backend:

  - ``backend=sdk``: a ``Path`` to a local sandbox directory.
  - ``backend=managed``: a ``str`` Managed Agents environment id.

The engine knows which backend is active and constructs the right context
before calling ``run_competitor``. This module is the seam that lets us
flip between backends with a single env var (and rolls back the same way
during Phase 2).

Phase 1 default is ``sdk`` so existing tests + deploys are unchanged.
Phase 2 flips to ``managed`` after the local end-to-end smoke validates.
Phase 3 deletes ``competitor_sdk.py`` and inlines the ``managed`` import.
"""

from __future__ import annotations

from skillforge.config import COMPETITOR_BACKEND

if COMPETITOR_BACKEND == "managed":
    from skillforge.agents.competitor_managed import run_competitor  # noqa: F401
else:
    from skillforge.agents.competitor_sdk import run_competitor  # noqa: F401

__all__ = ["run_competitor"]
