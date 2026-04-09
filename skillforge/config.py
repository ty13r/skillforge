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
        if key and key not in os.environ:
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
# Real evolution runs require a valid invite code from this allowlist. Rotate
# by editing the env var (on Railway: Variables → SKILLFORGE_INVITE_CODES).
# Demo runs (/api/debug/fake-run) are NOT gated. Empty/unset disables gating
# entirely — useful for local dev.
#
# Format: comma-separated, whitespace and case-insensitive.
_raw_codes = os.getenv("SKILLFORGE_INVITE_CODES", "")
INVITE_CODES: frozenset[str] = frozenset(
    c.strip().upper() for c in _raw_codes.split(",") if c.strip()
)
# Admin token for reading /api/invites/requests — set on Railway, never commit.
ADMIN_TOKEN: str = os.getenv("SKILLFORGE_ADMIN_TOKEN", "")


def invite_code_valid(code: str | None) -> bool:
    """Return True if the given code is in the allowlist.

    If INVITE_CODES is empty (unset env var), gating is disabled and every
    code — including missing ones — validates. This is the local-dev default.
    """
    if not INVITE_CODES:
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

# Maximum number of parallel Competitor runs. Each Competitor invokes the
# Claude Agent SDK's query(), which spawns a local `claude` CLI subprocess.
# The SDK hits a "Command failed with exit code 1" concurrency bug when
# multiple subprocesses run in the same Python process (file/pipe/auth
# contention). Default 1 = sequential = safe.
#
# A future migration to Anthropic's Managed Agents API would run competitors
# in isolated cloud containers (no local subprocess bug) and let this flag
# be raised to pop_size × challenges for ~10x speedup. Until then: 1.
COMPETITOR_CONCURRENCY: int = int(os.getenv("SKILLFORGE_COMPETITOR_CONCURRENCY", "1"))

# --- Models -------------------------------------------------------------------

DEFAULT_MODEL: str = os.getenv("SKILLFORGE_MODEL_DEFAULT", "claude-sonnet-4-6")

MODEL_DEFAULTS: dict[str, str] = {
    "challenge_designer": DEFAULT_MODEL,
    "spawner": DEFAULT_MODEL,
    "competitor": DEFAULT_MODEL,
    "breeder": DEFAULT_MODEL,
    "judge_trace": DEFAULT_MODEL,
    "judge_comparative": DEFAULT_MODEL,
    "judge_attribution": DEFAULT_MODEL,
    "l2_trigger": DEFAULT_MODEL,
    "spec_assistant": DEFAULT_MODEL,
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
