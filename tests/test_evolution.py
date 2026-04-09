"""Evolution engine integration tests (Step 7).

The end-to-end live-SDK test is gated behind ``SKILLFORGE_LIVE_TESTS=1``.
"""

from __future__ import annotations

import pytest

from skillforge.config import LIVE_TESTS


@pytest.mark.skipif(not LIVE_TESTS, reason="Live SDK test — set SKILLFORGE_LIVE_TESTS=1")
def test_minimal_evolution_live():
    """Run 2 pop × 1 gen × 1 challenge end-to-end against the real SDK."""
    pytest.skip("Implemented in Step 7")
