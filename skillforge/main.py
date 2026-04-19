"""FastAPI application entry point.

Mounts REST routes, the WebSocket evolution event stream, and (optionally)
the built frontend SPA from ``frontend/dist``. The static mount is conditional
so the backend works in both deployments (with frontend) and dev (without).
"""

# ruff: noqa: E402
# Logging must be configured before any ``skillforge.*`` imports so structured
# logging is in place for any import-time warnings. This intentionally puts the
# application imports below the logging setup block.

from __future__ import annotations

import json as _json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
import html
import re

from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles


class _JsonFormatter(logging.Formatter):
    """Single-line JSON log format for structured log ingestion (e.g. Railway)."""

    def format(self, record: logging.LogRecord) -> str:
        return _json.dumps({
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        })


# Configure structured logging before any other imports touch loggers.
_log_level = os.getenv("SKILLFORGE_LOG_LEVEL", "INFO").upper()
_log_format = os.getenv("SKILLFORGE_LOG_FORMAT", "text")

if _log_format == "json":
    _handler = logging.StreamHandler()
    _handler.setFormatter(_JsonFormatter())
    logging.basicConfig(level=getattr(logging, _log_level, logging.INFO), handlers=[_handler])
else:
    logging.basicConfig(
        level=getattr(logging, _log_level, logging.INFO),
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

from skillforge.config import ROOT_DIR
from skillforge.api.bench import router as bench_router
from skillforge.api.bible import router as bible_router
from skillforge.api.candidates import router as candidates_router
from skillforge.api.debug import router as debug_router
from skillforge.api.invites import router as invites_router
from skillforge.api.journal import router as journal_router
from skillforge.api.llms import router as llms_router
from skillforge.api.research import router as research_router
from skillforge.api.routes import router as api_router
from skillforge.api.seeds import router as seeds_router
from skillforge.api.spec_assistant import router as spec_assistant_router
from skillforge.api.taxonomy import router as taxonomy_router
from skillforge.api.uploads import router as uploads_router
from skillforge.api.websocket import router as ws_router
from skillforge.db.benchmark_seed_loader import load_benchmark_results
from skillforge.db.database import init_db
from skillforge.db.queries import mark_zombie_runs
from skillforge.db.seed_loader import load_seeds
from skillforge.db.taxonomy_seeds import load_taxonomy
from skillforge.seeds.mock_run_loader import load_mock_runs

logger = logging.getLogger("skillforge")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the SQLite schema on startup.

    Runs exactly once per container boot. Idempotent — ``init_db`` uses
    ``CREATE TABLE IF NOT EXISTS`` so re-running on an existing DB is safe.
    """
    await init_db()
    await load_seeds()
    try:
        await load_mock_runs()
    except Exception as exc:  # pragma: no cover - fail-soft on seed run load
        logger.exception("Seed run loader failed: %s", exc)
    try:
        diag = await load_benchmark_results()
        if diag.get("loaded"):
            logger.info("Benchmark seed loaded: %d rows", diag["loaded"])
    except Exception as exc:  # pragma: no cover - fail-soft on benchmark seed load
        logger.exception("Benchmark seed loader failed: %s", exc)
    try:
        taxonomy_diag = await load_taxonomy()
        logger.info(
            "Taxonomy bootstrapped: %d nodes, %d families created, %d reused",
            taxonomy_diag.get("nodes_total", 0),
            taxonomy_diag.get("families_created", 0),
            taxonomy_diag.get("families_reused", 0),
        )
    except Exception as exc:  # pragma: no cover - boot-time resiliency
        logger.exception("Taxonomy bootstrap failed: %s", exc)
    zombie_count = await mark_zombie_runs()
    if zombie_count:
        logger.warning("Marked %d zombie run(s) as failed on startup", zombie_count)
    yield
    # No shutdown hook needed — aiosqlite connections are per-query.


app = FastAPI(
    title="SKLD.run",
    description="Evolve Claude Agent Skills through natural selection",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router)
app.include_router(ws_router)
app.include_router(debug_router)
app.include_router(bench_router)
app.include_router(bible_router)
app.include_router(spec_assistant_router)
app.include_router(seeds_router)
app.include_router(uploads_router)
app.include_router(invites_router)
app.include_router(journal_router)
app.include_router(llms_router)
app.include_router(research_router)
app.include_router(candidates_router)
app.include_router(taxonomy_router)


@app.get("/api/health")
async def health() -> dict:
    """Backend health check with active run count."""
    from skillforge.api.routes import _active_runs
    return {
        "status": "ok",
        "service": "skillforge",
        "active_runs": len(_active_runs),
    }


# --- Optional frontend SPA mount ---------------------------------------------
# If frontend/dist exists (built by Vite), serve it as the SPA at /. Otherwise
# fall back to a JSON health check at /. This makes the same image deployable
# whether or not the frontend has been built.

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def _mount_frontend_spa() -> None:
    """Mount the built SPA if frontend/dist exists. No-op otherwise."""
    if not _FRONTEND_DIST.exists() or not (_FRONTEND_DIST / "index.html").exists():

        @app.get("/")
        async def root_no_frontend() -> dict[str, str]:
            return {"status": "ok", "service": "skillforge", "frontend": "not built"}

        return

    # Serve assets/* etc. from dist
    app.mount(
        "/assets",
        StaticFiles(directory=str(_FRONTEND_DIST / "assets")),
        name="assets",
    )

    # SPA index for / and any unknown route — the react-router client takes
    # over for deep links like /runs/:runId/* and /registry.
    @app.get("/")
    async def root_spa() -> FileResponse:
        return FileResponse(str(_FRONTEND_DIST / "index.html"))

    # Explicit static-asset routes for root-level files in dist/ that the
    # /assets mount doesn't cover. Must come BEFORE the catch-all so the
    # PNG isn't swallowed and served as index.html.
    @app.get("/og-image.png")
    async def og_image() -> FileResponse:
        return FileResponse(
            str(_FRONTEND_DIST / "og-image.png"),
            media_type="image/png",
        )

    @app.get("/favicon.ico")
    async def favicon_ico() -> FileResponse:
        # Browsers hit /favicon.ico automatically; serve the OG image as a
        # reasonable fallback so we don't leak 404s into server logs.
        return FileResponse(
            str(_FRONTEND_DIST / "og-image.png"),
            media_type="image/png",
        )

    # Catch-all: any GET that didn't match a registered API route, the
    # /assets mount, or the explicit "/" above falls through to here and
    # gets index.html back so the SPA router can hydrate and render the
    # requested path. API 404s are preserved by explicitly rejecting any
    # /api/* or /ws/* path that somehow reaches this fallback.
    from fastapi import HTTPException

    from skillforge.db.queries import get_run

    _RUN_PATH_RE = re.compile(r"^runs/([a-z0-9][a-z0-9\-_]*)(?:/.*)?$")
    _MAX_OG_DESC = 200
    _SITE_URL = "https://skld.run"

    def _clean_specialization(text: str) -> str:
        """Strip `[seed_v...]` / `[mock_v...]` markers for display."""
        return re.sub(r"\s*\[(mock|seed)_v[a-f0-9]+\]\s*", " ", text).strip()

    def _truncate(text: str, limit: int) -> str:
        text = text.strip()
        if len(text) <= limit:
            return text
        return text[: limit - 1].rstrip() + "…"

    async def _run_meta_tags(run_id: str) -> dict[str, str] | None:
        """Build per-run OG + Twitter meta tags from the DB.

        Returns a mapping of replacement-target → replacement-value, or
        ``None`` if the run is unknown (caller falls back to static tags).
        """
        try:
            run = await get_run(run_id)
        except Exception:  # noqa: BLE001 - meta injection must never break page render
            return None
        if run is None:
            return None

        skill_name: str = ""
        if run.best_skill and run.best_skill.frontmatter:
            skill_name = str(
                run.best_skill.frontmatter.get("name", "")
            ).strip()

        specialization = _clean_specialization(run.specialization or "")
        fitness_str = ""
        if run.best_skill and run.best_skill.pareto_objectives:
            try:
                fitness = max(run.best_skill.pareto_objectives.values())
                fitness_str = f"fitness {fitness:.2f} · "
            except Exception:  # noqa: BLE001
                fitness_str = ""

        title_display = skill_name or specialization or run_id
        title = f"{title_display} — SKLD"

        desc_parts = []
        if specialization:
            desc_parts.append(specialization)
        if fitness_str:
            desc_parts.append(f"{fitness_str}status {run.status}")
        desc = " · ".join(desc_parts) or specialization or "Evolved Claude Agent Skill on SKLD."
        desc = _truncate(desc, _MAX_OG_DESC)

        run_url = f"{_SITE_URL}/runs/{run_id}"

        return {
            "title": html.escape(title, quote=True),
            "description": html.escape(desc, quote=True),
            "url": html.escape(run_url, quote=True),
        }

    def _inject_meta(raw_html: str, meta: dict[str, str]) -> str:
        """Replace the static og/twitter tags with run-specific values."""
        title = meta["title"]
        description = meta["description"]
        url = meta["url"]

        patterns = [
            (
                r"<title>.*?</title>",
                f"<title>{title}</title>",
            ),
            (
                r'(<meta name="description" content=")[^"]*(")',
                lambda m: f'{m.group(1)}{description}{m.group(2)}',
            ),
            (
                r'(<meta property="og:title" content=")[^"]*(")',
                lambda m: f'{m.group(1)}{title}{m.group(2)}',
            ),
            (
                r'(<meta property="og:description" content=")[^"]*(")',
                lambda m: f'{m.group(1)}{description}{m.group(2)}',
            ),
            (
                r'(<meta property="og:url" content=")[^"]*(")',
                lambda m: f'{m.group(1)}{url}{m.group(2)}',
            ),
            (
                r'(<meta name="twitter:title" content=")[^"]*(")',
                lambda m: f'{m.group(1)}{title}{m.group(2)}',
            ),
            (
                r'(<meta name="twitter:description" content=")[^"]*(")',
                lambda m: f'{m.group(1)}{description}{m.group(2)}',
            ),
        ]
        for pattern, repl in patterns:
            raw_html = re.sub(pattern, repl, raw_html, count=1)
        return raw_html

    # Static meta for known SPA routes so bots/AI can understand the page
    _ROUTE_META: dict[str, dict[str, str]] = {
        "bench": {
            "title": "SKLD-bench — 867 Elixir Challenges",
            "description": "Controlled evaluation benchmark for measuring whether Claude Agent Skills improve code generation. 7 families, 6 scoring layers, composite fitness.",
        },
        "registry": {
            "title": "Skill Registry — SKLD",
            "description": "Browse evolved Claude Agent Skills. 7 Elixir lighthouse families with composite fitness scores, competition results, and per-dimension breakdowns.",
        },
        "taxonomy": {
            "title": "Skill Taxonomy — SKLD",
            "description": "Domain, Focus, Language hierarchy for AI coding skills. 49 taxonomy nodes, 22 skill families with expandable capability dimensions.",
        },
        "bible": {
            "title": "The SKLD Bible — Empirical Skill Engineering Knowledge",
            "description": "Book of Genesis (universal principles) and Book of Elixir (Elixir-specific findings) from evolving 7 skill families across 867 challenges.",
        },
        "journal": {
            "title": "Project Journal — SKLD",
            "description": "The story of building SKLD: sessions, decisions, pivots, and lessons learned. Building in public with full provenance.",
        },
        "research": {
            "title": "Research — SKLD",
            "description": "Problem, prior art, methodology, evaluation, findings, and open questions for evolutionary breeding of Claude Agent Skills.",
        },
    }

    # Paths for journal entries and bench family sub-pages
    _JOURNAL_PATH_RE = re.compile(r"^journal\b")
    _BENCH_FAMILY_PATH_RE = re.compile(r"^bench/([a-z0-9][a-z0-9\-]*)$")

    def _static_route_meta(full_path: str) -> dict[str, str] | None:
        """Return meta tags for known SPA routes."""
        # Exact match first
        base = full_path.rstrip("/").split("?")[0]
        if base in _ROUTE_META:
            meta = _ROUTE_META[base]
            return {
                "title": html.escape(meta["title"], quote=True),
                "description": html.escape(meta["description"], quote=True),
                "url": html.escape(f"{_SITE_URL}/{base}", quote=True),
            }
        # Bench family sub-pages
        bench_m = _BENCH_FAMILY_PATH_RE.match(base)
        if bench_m:
            slug = bench_m.group(1)
            label = slug.replace("elixir-", "").replace("-", " ").title()
            return {
                "title": html.escape(f"{label} — SKLD-bench", quote=True),
                "description": html.escape(
                    f"Per-challenge benchmark data for {label}: tier breakdown, dimension stats, score distribution, and sortable challenge table.",
                    quote=True,
                ),
                "url": html.escape(f"{_SITE_URL}/bench/{slug}", quote=True),
            }
        # Journal path
        if _JOURNAL_PATH_RE.match(base):
            return _ROUTE_META["journal"] | {
                "url": html.escape(f"{_SITE_URL}/{base}", quote=True),
                "title": html.escape("Project Journal — SKLD", quote=True),
                "description": html.escape(
                    "The story of building SKLD: sessions, decisions, pivots, and lessons learned.",
                    quote=True,
                ),
            }
        return None

    def _inject_noscript_content(raw_html: str, full_path: str) -> str:
        """Add a <noscript> block with file-based content so AI/crawlers can read the page."""
        base = full_path.rstrip("/").split("?")[0]
        content_lines: list[str] = []

        try:
            if base == "bible" or base.startswith("bible"):
                bible_dir = ROOT_DIR / "bible"
                for book_path in sorted(bible_dir.glob("book-of-*.md")):
                    body = book_path.read_text(encoding="utf-8")
                    content_lines.append(f"<article><pre>{html.escape(body[:3000])}</pre></article>")
            elif base == "journal" or base.startswith("journal"):
                journal_dir = ROOT_DIR / "journal"
                if journal_dir.exists():
                    for p in sorted(journal_dir.glob("*.md"), reverse=True)[:5]:
                        body = p.read_text(encoding="utf-8")
                        content_lines.append(f"<article><pre>{html.escape(body[:3000])}</pre></article>")
            elif base == "bench":
                content_lines.append("<h1>SKLD-bench: 867 Elixir Challenges</h1>")
                content_lines.append("<p>Controlled evaluation benchmark across 7 Elixir skill families with 6-layer composite scoring (L0 string match 10%, compilation 15%, AST quality 15%, behavioral tests 40%, template quality 10%, brevity 10%). Families: phoenix-liveview, ecto-query-writer, ecto-sandbox-test, ecto-schema-changeset, oban-worker, pattern-match-refactor, security-linter.</p>")
        except Exception:
            pass

        if not content_lines:
            return raw_html

        noscript_block = "<noscript>\n" + "\n".join(content_lines) + "\n</noscript>"
        return raw_html.replace("</body>", f"{noscript_block}\n</body>")

    @app.get("/{full_path:path}", response_model=None)
    async def spa_catchall(full_path: str) -> FileResponse | HTMLResponse:
        if full_path.startswith(("api/", "ws", "assets/")):
            raise HTTPException(status_code=404, detail="Not Found")

        raw = None
        meta = None

        # Per-run meta tag injection
        match = _RUN_PATH_RE.match(full_path)
        if match:
            run_id = match.group(1)
            meta = await _run_meta_tags(run_id)

        # Static route meta for known SPA routes
        if meta is None:
            meta = _static_route_meta(full_path)

        if meta is not None:
            try:
                raw = (_FRONTEND_DIST / "index.html").read_text(encoding="utf-8")
                patched = _inject_meta(raw, meta)
                patched = _inject_noscript_content(patched, full_path)
                return HTMLResponse(content=patched)
            except Exception:  # noqa: BLE001 - degrade to static tags
                pass

        return FileResponse(str(_FRONTEND_DIST / "index.html"))


_mount_frontend_spa()


if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("skillforge.main:app", host="0.0.0.0", port=port, reload=True)
