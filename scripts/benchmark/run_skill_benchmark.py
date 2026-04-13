#!/usr/bin/env python3
"""SKLD-bench skill-guided benchmark runner.

Same as run_benchmark_cli.py but prepends the seed skill's SKILL.md to
the prompt. Measures skill lift: how much does adding a skill improve
Sonnet's output vs the raw baseline?

Results stored with model tag "claude-sonnet-4-6+seed-v1" so they're
distinct from raw baseline results.

Usage:
    uv run python scripts/benchmark/run_skill_benchmark.py \
        --family elixir-phoenix-liveview \
        [--top-n 20] [--tier hard] [--limit 5] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from skillforge.config import DB_PATH
from skillforge.db.database import init_db
from skillforge.db.queries import save_transcript

import aiosqlite

TAXONOMY_BASE = Path(__file__).resolve().parent.parent.parent / "taxonomy" / "elixir"
SEEDS_DIR = Path(__file__).resolve().parent.parent.parent / "skillforge" / "seeds" / "seed_runs"

FAMILIES = [
    "elixir-phoenix-liveview",
    "elixir-ecto-sandbox-test",
    "elixir-security-linter",
    "elixir-oban-worker",
    "elixir-ecto-schema-changeset",
    "elixir-ecto-query-writer",
    "elixir-pattern-match-refactor",
]


def discover_challenges(family_slug: str, tier: str | None = None) -> list[dict]:
    family_dir = TAXONOMY_BASE / family_slug / "challenges"
    challenges = []
    tiers = [tier] if tier else ["easy", "medium", "hard", "legendary"]
    for t in tiers:
        tier_dir = family_dir / t
        if not tier_dir.exists():
            continue
        for path in sorted(tier_dir.glob("*.json")):
            ch = json.loads(path.read_text())
            ch["_path"] = str(path)
            challenges.append(ch)
    return challenges


async def get_top_discriminating(family_slug: str, top_n: int) -> list[str]:
    """Get the top N most discriminating challenge IDs by composite score (lowest = most headroom)."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            """SELECT challenge_id, scores FROM benchmark_results
               WHERE family_slug = ? AND scores != '{}'
               ORDER BY json_extract(scores, '$.composite') ASC
               LIMIT ?""",
            (family_slug, top_n),
        ) as cur:
            rows = await cur.fetchall()
    return [r["challenge_id"] for r in rows]


def load_seed_skill(family_slug: str) -> str | None:
    """Load the composite SKILL.md from the seed run JSON."""
    seed_path = SEEDS_DIR / f"{family_slug}.json"
    if not seed_path.exists():
        return None

    seed = json.loads(seed_path.read_text())
    # Find the composite genome (best_skill or engineer_composite)
    genomes = seed.get("skill_genomes", [])
    for g in genomes:
        if g.get("meta_strategy") in ("engineer_composite", "seed_pipeline_winner"):
            if g.get("skill_md_content"):
                return g["skill_md_content"]

    # Fallback: find genome with most content
    best = max(genomes, key=lambda g: len(g.get("skill_md_content", "")), default=None)
    return best["skill_md_content"] if best else None


def load_fixture(family_slug: str, fixture_path: str) -> str:
    full_path = TAXONOMY_BASE / family_slug / fixture_path
    return full_path.read_text() if full_path.exists() else ""


def build_prompt(family_slug: str, challenge: dict, skill_md: str) -> str:
    """Build prompt with skill context prepended."""
    parts = []

    # Skill context
    parts.append("You have the following skill loaded for guidance:\n")
    parts.append(f"```markdown\n{skill_md}\n```\n")
    parts.append("Use the patterns and guidance from this skill to produce high-quality output.\n")
    parts.append("---\n")

    # Challenge (same format as baseline)
    parts.append("You are solving an Elixir coding challenge.\n")
    for fixture_path in challenge.get("fixture_files", []):
        content = load_fixture(family_slug, fixture_path)
        if content:
            parts.append(f"Fixture file ({fixture_path}):\n```elixir\n{content}\n```\n")
    parts.append(f"CHALLENGE: {challenge['prompt']}\n")
    expected = challenge["expected_outputs"]["files"]
    parts.append(f"Expected output files: {', '.join(expected)}\n")
    parts.append("Produce ONLY fenced code blocks with path attribute. No preamble, no explanation.\n")
    for f in expected:
        parts.append(f'```elixir path="{f}"\n...\n```')
    return "\n".join(parts)


def extract_files(text: str) -> dict[str, str]:
    files = {}
    for m in re.finditer(r'```\w*\s+path=["\']?([^"\'>\s]+)["\']?\s*\n(.*?)\n```', text, re.DOTALL):
        files[m.group(1)] = m.group(2)
    if not files:
        for m in re.finditer(r'```\w*\s*\n#\s*(\S+\.ex\S*)\s*\n(.*?)\n```', text, re.DOTALL):
            files[m.group(1)] = m.group(2)
    return files


def score_output(family_slug: str, challenge_path: str, output_dir: str) -> dict:
    scorer = str(TAXONOMY_BASE / family_slug / "evaluation" / "score.py")
    result = subprocess.run(
        [sys.executable, scorer, "--challenge", challenge_path, "--output", output_dir],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        return {"score": 0.0, "passed": False, "objectives": {}, "error": result.stderr[:500]}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"score": 0.0, "passed": False, "objectives": {}, "error": "invalid scorer JSON"}


def dispatch_claude(prompt: str, model: str, timeout: int = 120) -> tuple[str, int]:
    start = time.time()
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", model, "--max-turns", "1",
         "--output-format", "text"],
        capture_output=True, text=True, timeout=timeout,
    )
    duration_ms = int((time.time() - start) * 1000)
    return result.stdout, duration_ms


async def run_single(
    family_slug: str, challenge: dict, model: str, skill_md: str,
    skill_tag: str, db_path: Path, dry_run: bool = False,
) -> dict | None:
    ch_id = challenge["id"]
    tier = challenge["tier"]
    dimension = challenge.get("scoring", {}).get("primary_capability", "unknown")
    model_tag = f"{model}+{skill_tag}"

    if dry_run:
        print(f"  [dry-run] {ch_id} ({tier})")
        return None

    prompt = build_prompt(family_slug, challenge, skill_md)

    try:
        response_text, duration_ms = dispatch_claude(prompt, model)
        error = None
    except subprocess.TimeoutExpired:
        response_text, duration_ms, error = "", 120000, "timeout"
    except Exception as e:
        response_text, duration_ms, error = "", 0, str(e)[:500]

    output_files = extract_files(response_text)
    total_tokens = len(prompt.split()) + len(response_text.split())

    if output_files:
        with tempfile.TemporaryDirectory(prefix="skld-bench-") as tmpdir:
            for fpath, content in output_files.items():
                dest = Path(tmpdir) / fpath
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content)
            score_result = score_output(family_slug, challenge["_path"], tmpdir)
    else:
        score_result = {"score": 0.0, "passed": False, "objectives": {}}
        if not error:
            error = "no output files extracted"

    result_id = uuid.uuid4().hex[:16]
    now = datetime.now(timezone.utc).isoformat()

    result = {
        "id": result_id, "family_slug": family_slug, "challenge_id": ch_id,
        "challenge_path": challenge["_path"], "model": model_tag, "tier": tier,
        "dimension": dimension, "score": score_result["score"],
        "passed": score_result.get("passed", False),
        "objectives": score_result.get("objectives", {}),
        "output_files": output_files, "total_tokens": total_tokens,
        "duration_ms": duration_ms, "error": error or score_result.get("error"),
        "created_at": now,
    }

    # Save to benchmark_results (model tag distinguishes from raw baseline)
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute(
            """INSERT OR REPLACE INTO benchmark_results
               (id, family_slug, challenge_id, challenge_path, model, tier,
                dimension, score, passed, objectives, output_files,
                total_tokens, duration_ms, error, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (result_id, family_slug, ch_id, challenge["_path"], model_tag, tier,
             dimension, result["score"], 1 if result["passed"] else 0,
             json.dumps(result["objectives"]), json.dumps(output_files),
             total_tokens, duration_ms, result.get("error"), now),
        )
        await conn.commit()

    # Save dispatch transcript
    await save_transcript(
        id=f"skill-bench-{result_id}", family_slug=family_slug,
        challenge_id=ch_id, dispatch_type="benchmark", model=model_tag,
        skill_variant=skill_tag, prompt=prompt[:10000],
        raw_response=response_text[:10000], extracted_files=output_files,
        benchmark_id=result_id, total_tokens=total_tokens,
        duration_ms=duration_ms, error=result.get("error"),
        created_at=now, db_path=db_path,
    )

    status = "PASS" if result["passed"] else "FAIL"
    print(f"  [{status}] {ch_id} ({tier}) score={result['score']:.3f} {duration_ms}ms files={len(output_files)}")
    return result


async def run_family(family_slug: str, model: str, top_n: int,
                     tier: str | None, limit: int | None,
                     dry_run: bool, db_path: Path):
    skill_md = load_seed_skill(family_slug)
    if not skill_md:
        print(f"ERROR: No seed skill found for {family_slug}")
        return

    skill_tag = "seed-v1"
    print(f"\nSkill loaded: {len(skill_md)} chars")

    # Get challenges — either top-N discriminating or filtered by tier
    if tier:
        challenges = discover_challenges(family_slug, tier)
    else:
        top_ids = await get_top_discriminating(family_slug, top_n)
        all_challenges = discover_challenges(family_slug)
        challenges = [ch for ch in all_challenges if ch["id"] in top_ids]

    if limit:
        challenges = challenges[:limit]

    print(f"{'=' * 60}")
    print(f"SKLD-bench SKILL: {family_slug} × {model}+{skill_tag}")
    print(f"Challenges: {len(challenges)}")
    print(f"{'=' * 60}")

    results = []
    for i, ch in enumerate(challenges):
        print(f"[{i + 1}/{len(challenges)}]", end="")
        result = await run_single(family_slug, ch, model, skill_md, skill_tag, db_path, dry_run)
        if result:
            results.append(result)

    if results:
        avg = sum(r["score"] for r in results) / len(results)
        passed = sum(1 for r in results if r["passed"])
        print(f"\nFamily summary: {len(results)} scored, avg={avg:.3f}, pass_rate={passed}/{len(results)}")


async def main():
    parser = argparse.ArgumentParser(description="SKLD-bench skill-guided benchmark")
    parser.add_argument("--family", required=True, choices=FAMILIES)
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--top-n", type=int, default=20, help="Top N most discriminating challenges")
    parser.add_argument("--tier", choices=["easy", "medium", "hard", "legendary"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    await init_db()
    await run_family(args.family, args.model, args.top_n, args.tier, args.limit, args.dry_run, DB_PATH)


if __name__ == "__main__":
    asyncio.run(main())
