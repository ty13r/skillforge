"""Central configuration: env vars, defaults, paths, per-role model selection.

All agent model choices flow through ``model_for(role)`` so individual roles
can be upgraded (e.g. Sonnet → Opus) via ``SKILLFORGE_MODEL_<ROLE>`` env vars
without touching call sites.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Paths --------------------------------------------------------------------

ROOT_DIR: Path = Path(__file__).resolve().parent.parent

# --- .env auto-loading (zero-dep, lazy) ---------------------------------------
# Reads ROOT_DIR/.env on import and populates os.environ with anything not
# already set. Supports KEY=value, KEY="value", and #-prefixed comments.
# Values already in os.environ take precedence (env vars > .env file).


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and not os.environ.get(key):
            os.environ[key] = value


_load_env_file(ROOT_DIR / ".env")
DOCS_DIR: Path = ROOT_DIR / "docs"
BIBLE_DIR: Path = ROOT_DIR / "bible"
GOLDEN_TEMPLATE_DIR: Path = DOCS_DIR / "golden-template"
SANDBOX_ROOT: Path = Path(os.getenv("SKILLFORGE_SANDBOX_ROOT", "/tmp"))

# Data directory for persistent state (DB, JSON run dumps, exported skills).
# On Railway, set SKILLFORGE_DATA_DIR=/data and mount a persistent volume there
# so the DB and run history survive container rebuilds.
DATA_DIR: Path = Path(os.getenv("SKILLFORGE_DATA_DIR", str(ROOT_DIR)))
DB_PATH: Path = Path(os.getenv("SKILLFORGE_DB", str(DATA_DIR / "skillforge.db")))
RUN_DUMPS_DIR: Path = Path(
    os.getenv("SKILLFORGE_RUN_DUMPS", str(DATA_DIR / "run-dumps"))
)

# --- Evolution defaults -------------------------------------------------------

MAX_TURNS: int = int(os.getenv("SKILLFORGE_MAX_TURNS", "15"))
DEFAULT_POP: int = int(os.getenv("SKILLFORGE_DEFAULT_POP", "5"))
DEFAULT_GENS: int = int(os.getenv("SKILLFORGE_DEFAULT_GENS", "3"))
DEFAULT_BUDGET_USD: float = float(os.getenv("SKILLFORGE_DEFAULT_BUDGET_USD", "10.0"))

# --- Feature flags ------------------------------------------------------------

WEBSEARCH_ENABLED: bool = os.getenv("SKILLFORGE_WEBSEARCH", "1") == "1"
LIVE_TESTS: bool = os.getenv("SKILLFORGE_LIVE_TESTS") == "1"

# --- Invite gating ------------------------------------------------------------
# Real evolution runs require a valid invite code. Gating is ON BY DEFAULT —
# fail-closed semantics so a production deploy without env vars denies
# everyone rather than silently allowing all traffic.
#
# - `SKILLFORGE_INVITE_CODES` (comma-separated) — the allowlist. Case-
#   insensitive and whitespace-trimmed.
# - `SKILLFORGE_GATING_DISABLED=1` — explicit escape hatch for local dev
#   that allows any code (including missing) to pass validation.
#
# Demo runs (/api/debug/fake-run) are NEVER gated.
_raw_codes = os.getenv("SKILLFORGE_INVITE_CODES", "")
INVITE_CODES: frozenset[str] = frozenset(
    c.strip().upper() for c in _raw_codes.split(",") if c.strip()
)
GATING_DISABLED: bool = os.getenv("SKILLFORGE_GATING_DISABLED") == "1"

# Admin token for reading /api/invites/requests — set on Railway, never commit.
ADMIN_TOKEN: str = os.getenv("SKILLFORGE_ADMIN_TOKEN", "")

# Log gating state at import so Railway logs show whether env vars landed.
# Startup diagnostic moved to end of file (after all constants are defined).


def invite_code_valid(code: str | None) -> bool:
    """Return True if the given code is accepted.

    Fail-closed by default: when no codes are configured and gating isn't
    explicitly disabled, every code (including missing) is rejected.
    """
    if GATING_DISABLED:
        return True
    if not code:
        return False
    return code.strip().upper() in INVITE_CODES

# --- Cost-saver strategy flags (see PLAN.md §Flexibility Hooks) ---------------
# All default to "MVP simple" values. Flip via env var to enable cost savers.

# L4 pairwise ranking is exhaustive (C(n,2) × criteria). Batched ranking asks
# one call per criterion to rank all candidates → ~10× cheaper at pop=5.
L4_STRATEGY: str = os.getenv("SKILLFORGE_L4_STRATEGY", "pairwise")  # "pairwise" | "batched_rank"

# The Breeder can make 4 separate LLM calls or consolidate learning-log +
# breeding-report into one (they share context).
BREEDER_CALL_MODE: str = os.getenv("SKILLFORGE_BREEDER_CALL_MODE", "separate")  # "separate" | "consolidated"

# Compress competition trace JSON with zlib before DB insert. Off for easier
# debugging in MVP; on for production runs where DB size matters.
COMPRESS_TRACES: bool = os.getenv("SKILLFORGE_COMPRESS_TRACES", "0") == "1"

# --- Competitor backend selection (PLAN-V1.2 Phase 1) -------------------------
# Selects which competitor implementation runs the Skill × Challenge match:
#
#   - "sdk"     → competitor_sdk.py — local subprocess via claude_agent_sdk.
#                  Default for Phase 1 so existing tests + deploys are
#                  unchanged. Concurrency MUST stay at 1 (subprocess race).
#   - "managed" → competitor_managed.py — Anthropic Managed Agents (cloud
#                  containers). No subprocess race; concurrency safely
#                  raised to 5+. Selected at Phase 2 via env var, no
#                  code push required.
COMPETITOR_BACKEND: str = os.getenv("SKILLFORGE_COMPETITOR_BACKEND", "sdk")

# Skill upload mode for the managed backend:
#   - "upload" → POST /v1/skills then attach to the agent (default; gives
#                L3 the skill_was_loaded signal). Step 0 confirmed
#                30 serial + 10 parallel uploads work with no rate limits.
#   - "inline" → bake the SKILL.md content into the user.message text
#                (escape hatch if upload rate-limits ever bite). Loses the
#                skill_was_loaded signal but everything else still works.
MANAGED_AGENTS_SKILL_MODE: str = os.getenv("SKILLFORGE_MANAGED_AGENTS_SKILL_MODE", "upload")

# Anthropic Managed Agents bills $0.08 per session-hour, metered only while
# the session status is `running` (idle/rescheduled/terminated don't count).
# Mirrors the constant in skillforge.agents.managed_agents — duplicated here
# so the engine can budget without importing the wrapper. A bump requires
# a plan edit (PLAN-V1.2 §Risk smoke-check).
MANAGED_AGENTS_SESSION_RUNTIME_USD_PER_HOUR: float = 0.08

# Per-model token pricing (USD per million tokens). Anthropic published rates
# as of 2026-04-09. A bump requires a plan edit. The model name keys here
# are NOT model selections — they're a lookup table indexed by whatever model
# the per-role config has resolved to. Cross-cutting contract #2 ("no
# hardcoded model strings outside config.py") puts this table in this file.
MODEL_PRICE_PER_MTOK_INPUT: dict[str, float] = {
    "claude-sonnet-4-6": 3.0,
    "claude-haiku-4-5-20251001": 1.0,
    "claude-opus-4-6": 5.0,
}
MODEL_PRICE_PER_MTOK_OUTPUT: dict[str, float] = {
    "claude-sonnet-4-6": 15.0,
    "claude-haiku-4-5-20251001": 5.0,
    "claude-opus-4-6": 25.0,
}
# Cache creation tokens are billed at base input × 1.25; cache reads at × 0.1.
MODEL_CACHE_CREATE_MULTIPLIER: float = 1.25
MODEL_CACHE_READ_MULTIPLIER: float = 0.1

# Advisor Strategy (advisor_20260301) — DESCOPED FROM PHASE 1.
# Step 0 confirmed the tool type is not yet supported in anthropic SDK 0.92
# or our beta access. Phase 1 ships without the advisor; this flag exists
# as a forward-compatible no-op so wiring (cost_breakdown.advisor_*,
# competitor_advisor model role) is ready when the tool lands. Default off
# until that day.
COMPETITOR_ADVISOR: bool = os.getenv("SKILLFORGE_COMPETITOR_ADVISOR", "off") == "on"
COMPETITOR_ADVISOR_MAX_USES: int = int(
    os.getenv("SKILLFORGE_COMPETITOR_ADVISOR_MAX_USES", "3")
)

# Maximum number of parallel Competitor runs. The SDK backend MUST stay at 1
# because of the subprocess concurrency race (multiple `claude` CLI
# subprocesses in the same Python process collide on file/pipe/auth state).
# The Managed Agents backend has no local subprocess and can safely lift this
# to 5+ — defaults to 5 when COMPETITOR_BACKEND=managed unless explicitly
# overridden. Override always wins via SKILLFORGE_COMPETITOR_CONCURRENCY.
_concurrency_default = "5" if COMPETITOR_BACKEND == "managed" else "1"
COMPETITOR_CONCURRENCY: int = int(
    os.getenv("SKILLFORGE_COMPETITOR_CONCURRENCY", _concurrency_default)
)

# --- Models -------------------------------------------------------------------

DEFAULT_MODEL: str = os.getenv("SKILLFORGE_MODEL_DEFAULT", "claude-sonnet-4-6")

MODEL_DEFAULTS: dict[str, str] = {
    "challenge_designer": DEFAULT_MODEL,
    "spawner": DEFAULT_MODEL,
    "competitor": DEFAULT_MODEL,
    # Forward-compat: advisor model role for the Advisor Strategy. Default
    # is Opus 4.6 per the published BrowseComp / SWE-bench numbers, but
    # advisor is descoped from Phase 1 so this is a no-op until the SDK
    # adds support. Override via SKILLFORGE_MODEL_COMPETITOR_ADVISOR.
    "competitor_advisor": "claude-opus-4-6",
    "breeder": DEFAULT_MODEL,
    "judge_trace": DEFAULT_MODEL,
    "judge_comparative": DEFAULT_MODEL,
    "judge_attribution": DEFAULT_MODEL,
    "l2_trigger": DEFAULT_MODEL,
    "spec_assistant": DEFAULT_MODEL,
    # v2.0 — structured-output agents for atomic variant evolution
    "taxonomist": DEFAULT_MODEL,
    "scientist": DEFAULT_MODEL,
    "engineer": DEFAULT_MODEL,
}


def model_for(role: str) -> str:
    """Return the model ID to use for a given agent role.

    Env override: ``SKILLFORGE_MODEL_<ROLE_UPPER>`` takes precedence over
    ``MODEL_DEFAULTS``. Unknown roles fall back to ``DEFAULT_MODEL``.
    """
    override = os.getenv(f"SKILLFORGE_MODEL_{role.upper()}")
    if override:
        return override
    return MODEL_DEFAULTS.get(role, DEFAULT_MODEL)


# --- API keys / external -------------------------------------------------------

ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")

# --- Startup diagnostic (all constants now defined) ---------------------------
import logging as _logging

_logging.getLogger("skillforge.config").info(
    "gating_disabled=%s codes_loaded=%d backend=%s api_key=%s",
    GATING_DISABLED, len(INVITE_CODES), COMPETITOR_BACKEND,
    "set" if ANTHROPIC_API_KEY else "NOT SET",
)
