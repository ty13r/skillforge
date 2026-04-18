"""LLM-readable surface: /llms.txt index + plain markdown endpoints per route.

Purpose: let Claude / crawlers / any non-JS agent read the site without
parsing a client-rendered SPA. Content is served as ``text/markdown`` straight
from the authoritative sources (journal files on disk, bible files on disk,
family READMEs in the taxonomy dir, SQLite for dynamic registry data).

No React, no HTML rendering, no duplication of the UI — just the raw content
that would otherwise be hidden inside a rendered page.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, Response

from skillforge.config import ROOT_DIR
from skillforge.db.queries import _connect

router = APIRouter(tags=["llms"])

SITE_URL = "https://skld.run"
JOURNAL_DIR = ROOT_DIR / "journal"
BIBLE_DIR = ROOT_DIR / "bible"
TAXONOMY_DIR = ROOT_DIR / "taxonomy"
RESEARCH_DIR = ROOT_DIR / "docs" / "research"


def _md(body: str) -> PlainTextResponse:
    return PlainTextResponse(content=body, media_type="text/markdown; charset=utf-8")


@router.get("/robots.txt")
async def robots_txt() -> PlainTextResponse:
    """Crawler hints. Points to both sitemap.xml and llms.txt."""
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n"
        f"# LLM-readable index: {SITE_URL}/llms.txt\n"
    )
    return PlainTextResponse(body, media_type="text/plain; charset=utf-8")


@router.get("/sitemap.xml")
async def sitemap_xml() -> Response:
    """XML sitemap enumerating every markdown URL + key SPA routes."""
    urls: list[str] = [
        f"{SITE_URL}/",
        f"{SITE_URL}/llms.txt",
        f"{SITE_URL}/about.md",
        f"{SITE_URL}/journal",
        f"{SITE_URL}/journal.md",
        f"{SITE_URL}/bible",
        f"{SITE_URL}/bible.md",
        f"{SITE_URL}/bench",
        f"{SITE_URL}/bench.md",
        f"{SITE_URL}/registry",
        f"{SITE_URL}/registry.md",
        f"{SITE_URL}/research",
        f"{SITE_URL}/research.md",
    ]
    for cat in ("narrative", "audits"):
        subdir = RESEARCH_DIR / cat
        if subdir.exists():
            for p in sorted(subdir.glob("*.md")):
                urls.append(f"{SITE_URL}/research/{cat}/{p.stem}.md")
    if JOURNAL_DIR.exists():
        for p in sorted(JOURNAL_DIR.glob("*.md")):
            urls.append(f"{SITE_URL}/journal/{p.stem}.md")
    if BIBLE_DIR.exists():
        for p in sorted(BIBLE_DIR.glob("*.md")):
            urls.append(f"{SITE_URL}/bible/{p.stem}.md")
    for slug in _list_families():
        urls.append(f"{SITE_URL}/bench/{slug}")
        urls.append(f"{SITE_URL}/bench/{slug}.md")

    try:
        async with _connect() as conn:
            conn.row_factory = None
            cursor = await conn.execute(
                "SELECT id FROM evolution_runs ORDER BY created_at DESC LIMIT 500"
            )
            for (run_id,) in await cursor.fetchall():
                urls.append(f"{SITE_URL}/runs/{run_id}")
                urls.append(f"{SITE_URL}/runs/{run_id}.md")
    except Exception:
        pass

    body_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in urls:
        body_lines.append(f"  <url><loc>{url}</loc></url>")
    body_lines.append("</urlset>")
    return Response("\n".join(body_lines), media_type="application/xml")


@router.get("/llms.txt")
async def llms_index() -> PlainTextResponse:
    """Index of LLM-readable content, following the llms.txt convention."""
    lines: list[str] = [
        "# SKLD — Skill Kinetics through Layered Darwinism",
        "",
        "> SKLD is an evolutionary breeding platform for Claude Agent Skills. "
        "It decomposes a skill into focused atomic variants, evolves each under "
        "targeted selection pressure with multi-layer fitness scoring, and "
        "assembles the winners into a composite skill.",
        "",
        "## Overview",
        f"- [About SKLD]({SITE_URL}/about.md): system overview, architecture, evolution modes",
        "",
        "## Journal",
        f"- [All entries]({SITE_URL}/journal.md): narrative log of how SKLD was built",
    ]
    if JOURNAL_DIR.exists():
        for p in sorted(JOURNAL_DIR.glob("*.md"), reverse=True):
            lines.append(f"- [{p.stem}]({SITE_URL}/journal/{p.stem}.md)")

    lines += ["", "## Bible (empirical skill engineering findings)",
              f"- [Index]({SITE_URL}/bible.md)"]
    if BIBLE_DIR.exists():
        for p in sorted(BIBLE_DIR.glob("*.md")):
            lines.append(f"- [{p.stem}]({SITE_URL}/bible/{p.stem}.md)")

    lines += ["", "## SKLD-bench (controlled evaluation)",
              f"- [Benchmark overview]({SITE_URL}/bench.md)"]
    families = _list_families()
    for slug in families:
        lines.append(f"- [{slug}]({SITE_URL}/bench/{slug}.md)")

    lines += ["", "## Research (problem, prior art, methodology, findings)",
              f"- [Research index]({SITE_URL}/research.md)"]
    narrative_dir = RESEARCH_DIR / "narrative"
    if narrative_dir.exists():
        for p in sorted(narrative_dir.glob("*.md")):
            lines.append(f"- [{p.stem}]({SITE_URL}/research/narrative/{p.stem}.md)")
    audits_dir = RESEARCH_DIR / "audits"
    if audits_dir.exists():
        for p in sorted(audits_dir.glob("*.md")):
            lines.append(f"- [audit: {p.stem}]({SITE_URL}/research/audits/{p.stem}.md)")

    lines += [
        "",
        "## Registry (evolved skills)",
        f"- [All runs]({SITE_URL}/registry.md): evolved skill packages with fitness scores",
    ]

    return PlainTextResponse("\n".join(lines), media_type="text/plain; charset=utf-8")


@router.get("/about.md")
async def about_md() -> PlainTextResponse:
    """High-level SKLD overview pulled from docs/how-skld-works.md if present, else CLAUDE.md."""
    for candidate in (ROOT_DIR / "docs" / "how-skld-works.md", ROOT_DIR / "CLAUDE.md"):
        if candidate.exists():
            return _md(candidate.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="about content not found")


# --- Journal ----------------------------------------------------------------


@router.get("/journal.md")
async def journal_md() -> PlainTextResponse:
    if not JOURNAL_DIR.exists():
        return _md("# Journal\n\n_No entries yet._\n")
    lines = ["# SKLD Journal", "",
             "Narrative log of how SKLD was built, session by session.", ""]
    for p in sorted(JOURNAL_DIR.glob("*.md"), reverse=True):
        title = _first_heading(p) or p.stem
        lines.append(f"- [{title}]({SITE_URL}/journal/{p.stem}.md)")
    return _md("\n".join(lines))


@router.get("/journal/{slug}.md")
async def journal_entry_md(slug: str) -> PlainTextResponse:
    path = JOURNAL_DIR / f"{slug}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"journal entry not found: {slug}")
    return _md(path.read_text(encoding="utf-8"))


# --- Bible ------------------------------------------------------------------


@router.get("/bible.md")
async def bible_md() -> PlainTextResponse:
    if not BIBLE_DIR.exists():
        raise HTTPException(status_code=404, detail="bible dir not found")
    lines = ["# The SKLD Bible", "",
             "Empirical findings from evolving skill families.", ""]
    for p in sorted(BIBLE_DIR.glob("*.md")):
        title = _first_heading(p) or p.stem
        lines.append(f"- [{title}]({SITE_URL}/bible/{p.stem}.md)")
    return _md("\n".join(lines))


@router.get("/bible/{slug}.md")
async def bible_entry_md(slug: str) -> PlainTextResponse:
    path = BIBLE_DIR / f"{slug}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"bible entry not found: {slug}")
    return _md(path.read_text(encoding="utf-8"))


# --- Research ---------------------------------------------------------------


@router.get("/research.md")
async def research_md() -> PlainTextResponse:
    if not RESEARCH_DIR.exists():
        raise HTTPException(status_code=404, detail="research dir not found")
    lines = ["# SKLD Research", "",
             "Problem, prior art, methodology, evaluation, findings, and open "
             "questions for evolutionary breeding of Claude Agent Skills.", ""]
    narrative = RESEARCH_DIR / "narrative"
    if narrative.exists():
        lines += ["## Narrative", ""]
        for p in sorted(narrative.glob("*.md")):
            title = _first_heading(p) or p.stem
            lines.append(f"- [{title}]({SITE_URL}/research/narrative/{p.stem}.md)")
    audits = RESEARCH_DIR / "audits"
    if audits.exists():
        lines += ["", "## Audits", ""]
        for p in sorted(audits.glob("*.md")):
            title = _first_heading(p) or p.stem
            lines.append(f"- [{title}]({SITE_URL}/research/audits/{p.stem}.md)")
    external = RESEARCH_DIR / "external-papers"
    if external.exists():
        pdfs = sorted(external.glob("*.pdf"))
        if pdfs:
            lines += ["", "## External papers", ""]
            for p in pdfs:
                lines.append(f"- `{p.name}` (see GitHub repo for PDF)")
    return _md("\n".join(lines))


@router.get("/research/{category}/{slug}.md")
async def research_entry_md(category: str, slug: str) -> PlainTextResponse:
    if category not in {"narrative", "audits"}:
        raise HTTPException(status_code=400, detail=f"unknown category: {category}")
    path = RESEARCH_DIR / category / f"{slug}.md"
    if not path.exists():
        raise HTTPException(
            status_code=404, detail=f"research entry not found: {category}/{slug}"
        )
    return _md(path.read_text(encoding="utf-8"))


# --- Bench ------------------------------------------------------------------


def _list_families() -> list[str]:
    elixir_dir = TAXONOMY_DIR / "elixir"
    if not elixir_dir.exists():
        return []
    return sorted(
        p.name for p in elixir_dir.iterdir()
        if p.is_dir() and (p / "family.json").exists()
    )


@router.get("/bench.md")
async def bench_md() -> PlainTextResponse:
    families = _list_families()
    lines = [
        "# SKLD-bench",
        "",
        "Controlled evaluation benchmark measuring whether Claude Agent Skills "
        "improve code generation. 7 Elixir lighthouse families, 867 challenges, "
        "6-layer composite scoring (L0 string match 10%, compilation 15%, AST "
        "quality 15%, behavioral tests 40%, template quality 10%, brevity 10%).",
        "",
        "## Families",
        "",
    ]
    for slug in families:
        family_json = TAXONOMY_DIR / "elixir" / slug / "family.json"
        summary = ""
        try:
            data = json.loads(family_json.read_text(encoding="utf-8"))
            summary = data.get("description") or data.get("summary") or ""
        except Exception:
            pass
        lines.append(f"- [{slug}]({SITE_URL}/bench/{slug}.md)"
                     + (f" — {summary}" if summary else ""))
    return _md("\n".join(lines))


@router.get("/bench/{slug}.md")
async def bench_family_md(slug: str) -> PlainTextResponse:
    family_dir = TAXONOMY_DIR / "elixir" / slug
    if not family_dir.exists():
        raise HTTPException(status_code=404, detail=f"family not found: {slug}")
    readme = family_dir / "README.md"
    if readme.exists():
        body = readme.read_text(encoding="utf-8")
    else:
        body = f"# {slug}\n\n_No README for this family._\n"
    family_json = family_dir / "family.json"
    if family_json.exists():
        try:
            data = json.loads(family_json.read_text(encoding="utf-8"))
            body += "\n\n## family.json\n\n```json\n" + json.dumps(data, indent=2) + "\n```\n"
        except Exception:
            pass
    return _md(body)


# --- Registry ---------------------------------------------------------------


@router.get("/registry.md")
async def registry_md() -> PlainTextResponse:
    """List all evolution runs from SQLite."""
    lines = [
        "# Skill Registry",
        "",
        "Evolved Claude Agent Skill packages with composite fitness scores.",
        "",
    ]
    try:
        async with _connect() as conn:
            conn.row_factory = None
            cursor = await conn.execute(
                "SELECT id, specialization, status, domain, language "
                "FROM evolution_runs ORDER BY created_at DESC LIMIT 200"
            )
            rows = await cursor.fetchall()
    except Exception:
        rows = []
    if not rows:
        lines.append("_No runs found._")
    for run_id, spec, status, domain, language in rows:
        label = (spec or run_id).strip()
        tags = " · ".join(filter(None, [domain, language, status]))
        lines.append(f"- [{label}]({SITE_URL}/runs/{run_id}.md)"
                     + (f" — {tags}" if tags else ""))
    return _md("\n".join(lines))


@router.get("/runs/{run_id}.md")
async def run_md(run_id: str) -> PlainTextResponse:
    """Single-run markdown summary: spec, status, best skill, fitness."""
    try:
        from skillforge.db.queries import get_run
        run = await get_run(run_id)
    except Exception:
        run = None
    if run is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")

    spec = (run.specialization or "").strip()
    lines = [f"# {spec or run_id}", "",
             f"- **Run ID:** `{run_id}`",
             f"- **Status:** {run.status}",
             f"- **Domain:** {getattr(run, 'domain', '') or '—'}",
             f"- **Language:** {getattr(run, 'language', '') or '—'}",
             ""]
    best = getattr(run, "best_skill", None)
    if best is not None:
        name = ""
        if getattr(best, "frontmatter", None):
            name = str(best.frontmatter.get("name", "")).strip()
        lines += ["## Best Skill", "",
                  f"- **Name:** {name or '—'}"]
        if getattr(best, "pareto_objectives", None):
            try:
                fit = max(best.pareto_objectives.values())
                lines.append(f"- **Fitness:** {fit:.4f}")
            except Exception:
                pass
            lines.append("- **Pareto objectives:**")
            for k, v in sorted(best.pareto_objectives.items()):
                lines.append(f"  - {k}: {v}")
        body = getattr(best, "body", "") or ""
        if body:
            lines += ["", "## SKILL.md", "", body]
    return _md("\n".join(lines))


# --- Helpers ----------------------------------------------------------------


def _first_heading(path: Path) -> str | None:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("## Entry"):
                return s.lstrip("#").strip()
            if s.startswith("# "):
                return s.lstrip("#").strip()
    except Exception:
        return None
    return None
