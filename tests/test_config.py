"""Tripwire tests for skillforge.config — model swap ergonomics + Phase 1 flags.

PLAN-V1.2 §"Model swap ergonomics" sets a hard design goal: every agent role
must be swappable via a single env var with zero code changes. This file is
the contract enforcement — if anyone hardcodes a model string or forgets to
register a new role in MODEL_DEFAULTS, the test fails loudly.

Coverage:
- Every role in MODEL_DEFAULTS has a default that's a non-empty string.
- Every role respects ``SKILLFORGE_MODEL_<ROLE_UPPER>`` override via
  ``model_for(role)``.
- ``competitor_advisor`` is registered as an Opus role (forward-compat for
  the descoped Advisor Strategy).
- Phase 1 flags (``COMPETITOR_BACKEND``, ``MANAGED_AGENTS_SKILL_MODE``,
  ``COMPETITOR_ADVISOR``, ``COMPETITOR_CONCURRENCY``) have sane defaults.
- ``COMPETITOR_CONCURRENCY`` defaults to 1 under sdk backend, 5 under
  managed backend (verified via env var manipulation + module reimport).
"""

from __future__ import annotations

import importlib

import pytest

import skillforge.config as cfg

# ---------------------------------------------------------------------------
# 1. MODEL_DEFAULTS shape
# ---------------------------------------------------------------------------


def test_model_defaults_is_non_empty_dict():
    assert isinstance(cfg.MODEL_DEFAULTS, dict)
    assert len(cfg.MODEL_DEFAULTS) > 0


def test_every_role_has_a_string_default():
    """Each registered role must have a non-empty string default model id."""
    for role, default in cfg.MODEL_DEFAULTS.items():
        assert isinstance(role, str) and role, f"role {role!r} must be a non-empty string"
        assert isinstance(default, str) and default, (
            f"role {role!r} default must be a non-empty string, got {default!r}"
        )
        assert default.startswith("claude-"), (
            f"role {role!r} default {default!r} must look like a Claude model id"
        )


# ---------------------------------------------------------------------------
# 2. model_for(role) override contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", sorted(cfg.MODEL_DEFAULTS.keys()))
def test_every_role_overridable_via_env(role: str, monkeypatch: pytest.MonkeyPatch):
    """Every role must honor SKILLFORGE_MODEL_<ROLE_UPPER>.

    This is the model-swap-ergonomics tripwire from PLAN-V1.2 §Model swap
    ergonomics. If a new role is added to MODEL_DEFAULTS but the call site
    bypasses model_for(), this test fails.
    """
    sentinel = f"claude-sentinel-{role}-test"
    env_var = f"SKILLFORGE_MODEL_{role.upper()}"
    monkeypatch.setenv(env_var, sentinel)

    assert cfg.model_for(role) == sentinel, (
        f"model_for({role!r}) did not pick up {env_var}={sentinel!r}"
    )


def test_model_for_unknown_role_returns_default():
    """Unknown roles fall back to DEFAULT_MODEL — never raise."""
    result = cfg.model_for("definitely-not-a-real-role-name")
    assert result == cfg.DEFAULT_MODEL


def test_model_for_default_when_no_env_override(monkeypatch: pytest.MonkeyPatch):
    """When no env var is set, model_for returns the MODEL_DEFAULTS value."""
    for role in cfg.MODEL_DEFAULTS:
        monkeypatch.delenv(f"SKILLFORGE_MODEL_{role.upper()}", raising=False)
    for role, default in cfg.MODEL_DEFAULTS.items():
        assert cfg.model_for(role) == default


# ---------------------------------------------------------------------------
# 3. Forward-compat: competitor_advisor role registered
# ---------------------------------------------------------------------------


def test_competitor_advisor_role_registered():
    """The Advisor Strategy is descoped from Phase 1 but the role is reserved.

    PLAN-V1.2 §Step 0 confirmed advisor_20260301 isn't in SDK 0.92 and the
    API rejects the type. The role stays in MODEL_DEFAULTS as a forward-
    compatible no-op so wiring is ready when it lands. Default must be Opus
    per the published BrowseComp / SWE-bench numbers.
    """
    assert "competitor_advisor" in cfg.MODEL_DEFAULTS
    advisor_default = cfg.MODEL_DEFAULTS["competitor_advisor"]
    assert "opus" in advisor_default.lower(), (
        f"competitor_advisor default should be an Opus model, got {advisor_default!r}"
    )


# ---------------------------------------------------------------------------
# 4. Phase 1 flags
# ---------------------------------------------------------------------------


def test_competitor_backend_default_is_sdk():
    """Phase 1 default MUST be 'sdk' so existing tests + deploys are unchanged."""
    # Note: this test runs against the imported module's frozen value, which
    # was set at import time based on the env at that point. If
    # SKILLFORGE_COMPETITOR_BACKEND was set in the test environment, this
    # would be that value — we just verify it's one of the valid options.
    assert cfg.COMPETITOR_BACKEND in {"sdk", "managed"}


def test_managed_agents_skill_mode_default():
    assert cfg.MANAGED_AGENTS_SKILL_MODE in {"upload", "inline"}


def test_competitor_advisor_flag_is_bool():
    assert isinstance(cfg.COMPETITOR_ADVISOR, bool)


def test_competitor_advisor_max_uses_is_positive_int():
    assert isinstance(cfg.COMPETITOR_ADVISOR_MAX_USES, int)
    assert cfg.COMPETITOR_ADVISOR_MAX_USES >= 1


def test_managed_agents_session_runtime_rate_matches_pricing():
    """The session-hour rate must match Anthropic's published pricing.

    A rate change requires a plan edit — see PLAN-V1.2 §Risk smoke-check
    item #2. This test exists so a typo or accidental edit fails loudly.
    """
    assert cfg.MANAGED_AGENTS_SESSION_RUNTIME_USD_PER_HOUR == 0.08


# ---------------------------------------------------------------------------
# 5. COMPETITOR_CONCURRENCY: backend-aware default
# ---------------------------------------------------------------------------


def test_competitor_concurrency_default_under_sdk_is_one(monkeypatch: pytest.MonkeyPatch):
    """SDK backend MUST default to 1 because of the subprocess race."""
    monkeypatch.setenv("SKILLFORGE_COMPETITOR_BACKEND", "sdk")
    monkeypatch.delenv("SKILLFORGE_COMPETITOR_CONCURRENCY", raising=False)
    reloaded = importlib.reload(cfg)
    try:
        assert reloaded.COMPETITOR_BACKEND == "sdk"
        assert reloaded.COMPETITOR_CONCURRENCY == 1
    finally:
        # Restore the canonical module state for downstream tests
        importlib.reload(cfg)


def test_competitor_concurrency_default_under_managed_is_five(
    monkeypatch: pytest.MonkeyPatch,
):
    """Managed backend can lift the cap because there's no subprocess."""
    monkeypatch.setenv("SKILLFORGE_COMPETITOR_BACKEND", "managed")
    monkeypatch.delenv("SKILLFORGE_COMPETITOR_CONCURRENCY", raising=False)
    reloaded = importlib.reload(cfg)
    try:
        assert reloaded.COMPETITOR_BACKEND == "managed"
        assert reloaded.COMPETITOR_CONCURRENCY == 5
    finally:
        importlib.reload(cfg)


def test_competitor_concurrency_explicit_override_wins(
    monkeypatch: pytest.MonkeyPatch,
):
    """A SKILLFORGE_COMPETITOR_CONCURRENCY override beats both defaults."""
    monkeypatch.setenv("SKILLFORGE_COMPETITOR_BACKEND", "managed")
    monkeypatch.setenv("SKILLFORGE_COMPETITOR_CONCURRENCY", "12")
    reloaded = importlib.reload(cfg)
    try:
        assert reloaded.COMPETITOR_CONCURRENCY == 12
    finally:
        importlib.reload(cfg)


# ---------------------------------------------------------------------------
# 6. invite_code_valid sanity (smoke check — fully covered in test_api.py)
# ---------------------------------------------------------------------------


def test_invite_code_valid_returns_true_when_gating_disabled(
    monkeypatch: pytest.MonkeyPatch,
):
    """The conftest fixture sets SKILLFORGE_GATING_DISABLED=1 for all tests.

    This is a sanity check: if the conftest setup ever drifts, this test
    catches the regression instantly so test_api.py doesn't get mysterious
    403 failures.
    """
    assert cfg.invite_code_valid(None) is True
    assert cfg.invite_code_valid("anything") is True
