"""SKLD-bench baseline runner.

Dispatches raw Claude (no skill guidance) against challenge pools and scores
the output via each family's score.py. Results go to the benchmark_results
table for analysis.

Usage:
    uv run python scripts/benchmark/run_benchmark.py \
        --family elixir-ecto-schema-changeset \
        --model claude-sonnet-4-6 \
        [--tier medium] [--limit 10] [--dry-run] [--parallel 4]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from skillforge.config import DB_PATH

TAXONOMY_BASE = Path("taxonomy/elixir")

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
    """Walk the challenges directory and return parsed challenge dicts."""
    family_dir = TAXONOMY_BASE / family_slug / "challenges"
    challenges = []
    tiers = [tier] if tier else ["easy", "medium", "hard", "legendary"]

    for t in tiers:
        tier_dir = family_dir / t
        if not tier_dir.exists():
            continue
        for path in sorted(tier_dir.glob("*.json")):
            with open(path) as f:
                ch = json.load(f)
            ch["_path"] = str(path)
            challenges.append(ch)

    return challenges


def load_fixture(family_slug: str, fixture_path: str) -> str:
    """Load a fixture file's content."""
    full_path = TAXONOMY_BASE / family_slug / fixture_path
    if full_path.exists():
        return full_path.read_text()
    return ""


def build_prompt(family_slug: str, challenge: dict) -> str:
    """Build a competitor prompt with no skill guidance — just the challenge."""
    parts = [f"You are solving an Elixir coding challenge.\n"]

    # Inline fixture files
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
    """Extract code files from fenced blocks with path attributes."""
    files = {}

    # Pattern 1: path="..." or path=...
    for m in re.finditer(r'```\w*\s+path=["\']?([^"\'>\s]+)["\']?\s*\n(.*?)\n```', text, re.DOTALL):
        files[m.group(1)] = m.group(2)

    # Pattern 2: # path comment at top of block
    if not files:
        for m in re.finditer(r'```\w*\s*\n#\s*(\S+\.ex\S*)\s*\n(.*?)\n```', text, re.DOTALL):
            files[m.group(1)] = m.group(2)

    return files


def score_output(family_slug: str, challenge_path: str, output_dir: str) -> dict:
    """Run score.py and return the result dict."""
    scorer = str(TAXONOMY_BASE / family_slug / "evaluation" / "score.py")
    result = subprocess.run(
        ["python", scorer, "--challenge", challenge_path, "--output", output_dir],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        return {"score": 0.0, "passed": False, "objectives": {}, "error": result.stderr[:500]}
    return json.loads(result.stdout)


async def save_result(db_path: Path, result: dict) -> None:
    """Upsert a benchmark result into the DB."""
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute(
            """INSERT OR REPLACE INTO benchmark_results
               (id, family_slug, challenge_id, challenge_path, model, tier,
                dimension, score, passed, objectives, output_files,
                total_tokens, duration_ms, error, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result["id"],
                result["family_slug"],
                result["challenge_id"],
                result["challenge_path"],
                result["model"],
                result["tier"],
                result["dimension"],
                result["score"],
                1 if result["passed"] else 0,
                json.dumps(result["objectives"]),
                json.dumps(result["output_files"]),
                result["total_tokens"],
                result["duration_ms"],
                result.get("error"),
                result["created_at"],
            ),
        )
        await conn.commit()


async def already_scored(db_path: Path, challenge_id: str, model: str) -> bool:
    """Check if this (challenge, model) pair already has a result."""
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT 1 FROM benchmark_results WHERE challenge_id = ? AND model = ?",
            (challenge_id, model),
        ) as cur:
            return await cur.fetchone() is not None


async def run_single(
    family_slug: str,
    challenge: dict,
    model: str,
    db_path: Path,
    dry_run: bool = False,
) -> dict | None:
    """Run a single challenge against the model and save the result."""
    ch_id = challenge["id"]
    tier = challenge["tier"]
    dimension = challenge.get("scoring", {}).get("primary_capability", "unknown")

    if await already_scored(db_path, ch_id, model):
        return None  # skip

    if dry_run:
        print(f"  [dry-run] {ch_id} ({tier})")
        return None

    prompt = build_prompt(family_slug, challenge)
    start = time.time()

    # Dispatch via Claude Agent SDK
    try:
        from claude_code_sdk import query as claude_query, ClaudeCodeOptions

        response_parts = []
        async for msg in claude_query(
            prompt=prompt,
            options=ClaudeCodeOptions(model=model, max_turns=1),
        ):
            if hasattr(msg, "content"):
                response_parts.append(msg.content)

        response_text = "\n".join(str(p) for p in response_parts)
        total_tokens = len(prompt.split()) * 2  # rough estimate
        error = None
    except Exception as e:
        response_text = ""
        total_tokens = 0
        error = str(e)[:500]

    duration_ms = int((time.time() - start) * 1000)

    # Extract files and score
    output_files = extract_files(response_text)

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

    result = {
        "id": uuid.uuid4().hex[:16],
        "family_slug": family_slug,
        "challenge_id": ch_id,
        "challenge_path": challenge["_path"],
        "model": model,
        "tier": tier,
        "dimension": dimension,
        "score": score_result["score"],
        "passed": score_result.get("passed", False),
        "objectives": score_result.get("objectives", {}),
        "output_files": output_files,
        "total_tokens": total_tokens,
        "duration_ms": duration_ms,
        "error": error or score_result.get("error"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await save_result(db_path, result)

    status = "PASS" if result["passed"] else "FAIL"
    print(f"  [{status}] {ch_id} ({tier}) score={result['score']:.3f} {duration_ms}ms")
    return result


async def run_family(
    family_slug: str,
    model: str,
    tier: str | None,
    limit: int | None,
    dry_run: bool,
    db_path: Path,
) -> list[dict]:
    """Run all challenges for a family."""
    challenges = discover_challenges(family_slug, tier)
    if limit:
        challenges = challenges[:limit]

    print(f"\n{'='*60}")
    print(f"SKLD-bench: {family_slug} × {model}")
    print(f"Challenges: {len(challenges)}")
    print(f"{'='*60}")

    results = []
    for i, ch in enumerate(challenges):
        print(f"[{i+1}/{len(challenges)}]", end="")
        result = await run_single(family_slug, ch, model, db_path, dry_run)
        if result:
            results.append(result)
        elif not dry_run:
            print(f"  [SKIP] {ch['id']} (already scored)")

    scored = [r for r in results if r]
    if scored:
        avg = sum(r["score"] for r in scored) / len(scored)
        passed = sum(1 for r in scored if r["passed"])
        print(f"\nFamily summary: {len(scored)} scored, avg={avg:.3f}, pass_rate={passed}/{len(scored)}")

    return results


async def main():
    parser = argparse.ArgumentParser(description="SKLD-bench baseline runner")
    parser.add_argument("--family", required=True, choices=FAMILIES, help="Family slug")
    parser.add_argument("--model", required=True, help="Model ID (e.g. claude-sonnet-4-6)")
    parser.add_argument("--tier", choices=["easy", "medium", "hard", "legendary"])
    parser.add_argument("--limit", type=int, help="Max challenges to run")
    parser.add_argument("--dry-run", action="store_true", help="List challenges without dispatching")
    args = parser.parse_args()

    # Ensure DB has the table
    from skillforge.db.database import init_db
    await init_db()

    await run_family(args.family, args.model, args.tier, args.limit, args.dry_run, DB_PATH)


if __name__ == "__main__":
    asyncio.run(main())
