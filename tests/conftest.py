"""Pytest fixtures shared across test modules."""

from __future__ import annotations

import os

# Disable invite gating for the whole test suite — tests exercise the
# evolve endpoints directly and shouldn't need to thread an invite code
# through every payload. Must be set BEFORE skillforge.config imports.
os.environ.setdefault("SKILLFORGE_GATING_DISABLED", "1")


def _apply_test_tier() -> None:
    """Configure per-role model selection for cost-tiered live testing.

    Reads ``SKILLFORGE_TEST_TIER`` and sets ``SKILLFORGE_MODEL_<ROLE>``
    env vars so ``skillforge.config.model_for()`` returns the chosen
    tier's model for each agent role. Runs at conftest.py import time,
    which happens before any test module imports skillforge, so the
    per-role env vars are live by the time any agent call happens.

    Tiers:
      - ``sonnet`` (or unset): every role uses ``claude-sonnet-4-6``.
        Default — full-quality pre-release validation. Most expensive.

      - ``cheap`` / ``haiku``: every role uses ``claude-haiku-4-5-20251001``
        (~1/3 the cost of Sonnet per the pricing table in
        ``skillforge/config.py``). Best for fast dev iteration on
        pipeline bugs — structural/contract/state-machine bugs surface
        identically, and Haiku's stricter JSON formatting tends to
        *increase* test sensitivity to schema regressions.

      - ``mixed``: structured-output agents (Taxonomist, Scientist,
        Spawner, Engineer, judges) run on Haiku; reasoning-heavy agents
        (Breeder, Competitor) stay on Sonnet so the live test exercises
        real-quality reasoning on the parts where output quality
        genuinely matters. Middle-ground cost (~$0.80 vs $1.50 Sonnet
        vs $0.50 all-Haiku).

    Explicit per-role overrides in the environment always win — this
    helper only fills in the roles the caller didn't specify, so you
    can still do things like ``SKILLFORGE_TEST_TIER=cheap
    SKILLFORGE_MODEL_ENGINEER=claude-sonnet-4-6`` to override a
    specific role within a tier.
    """
    tier = os.getenv("SKILLFORGE_TEST_TIER", "").strip().lower()
    if not tier or tier == "sonnet":
        return

    HAIKU = "claude-haiku-4-5-20251001"
    SONNET = "claude-sonnet-4-6"

    # Mirror of the role keys in skillforge/config.py::MODEL_DEFAULTS.
    # Kept in sync manually because importing from skillforge here would
    # run config.py before the test tier env vars are set.
    ALL_ROLES = [
        "challenge_designer",
        "spawner",
        "competitor",
        "breeder",
        "judge_trace",
        "judge_comparative",
        "judge_attribution",
        "l2_trigger",
        "spec_assistant",
        "taxonomist",
        "scientist",
        "engineer",
    ]
    # Roles that need deeper reasoning — kept on Sonnet in the mixed tier
    REASONING_ROLES = {"breeder", "competitor"}

    if tier in ("cheap", "haiku"):
        per_role_model = dict.fromkeys(ALL_ROLES, HAIKU)
    elif tier == "mixed":
        per_role_model = {
            role: SONNET if role in REASONING_ROLES else HAIKU
            for role in ALL_ROLES
        }
    else:
        raise ValueError(
            f"Unknown SKILLFORGE_TEST_TIER={tier!r}. "
            "Expected one of: cheap, haiku, mixed, sonnet"
        )

    for role, model in per_role_model.items():
        env_key = f"SKILLFORGE_MODEL_{role.upper()}"
        # Respect explicit per-role overrides from the caller
        if env_key not in os.environ:
            os.environ[env_key] = model

    # Diagnostic print (goes to pytest's stdout) so the user sees which
    # tier is active and how it resolved per role. Use a plain print
    # because logging isn't configured yet at conftest import time.
    roles_by_model: dict[str, list[str]] = {}
    for role, model in per_role_model.items():
        roles_by_model.setdefault(model, []).append(role)
    summary_parts = [
        f"{model.split('-')[1]}={len(roles)}" for model, roles in roles_by_model.items()
    ]
    print(
        f"[conftest] SKILLFORGE_TEST_TIER={tier} applied "
        f"({', '.join(summary_parts)})"
    )


_apply_test_tier()

import pytest  # noqa: E402


@pytest.fixture
def temp_db_path(tmp_path):
    """Return a temp SQLite path for database tests."""
    return tmp_path / "test.db"
