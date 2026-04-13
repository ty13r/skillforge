#!/usr/bin/env python3
"""Phase 5: Full scored mock run for elixir-phoenix-liveview.

Orchestrates the complete evolution loop:
  For each of 12 dimensions (foundation first, then 11 capabilities):
    1. Sample 2 challenges
    2. Spawn alternative variant via claude -p (Opus)
    3. Dispatch 4 competitors (seed x 2 challenges + spawn x 2 challenges)
    4. Score with composite scorer
    5. Pick winner (higher mean composite)
    6. Persist winner via persist_variant.py

After all 12:
    7. Engineer assembles composite
    8. Finalize run

Usage:
    uv run python scripts/mock_pipeline/phase5_full_run.py [--start-dim N] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from skillforge.config import DB_PATH
from skillforge.db.database import init_db
from skillforge.db.queries import save_transcript

import aiosqlite

FAMILY_SLUG = "elixir-phoenix-liveview"
FAMILY_ID = "fam_8dfbc491c886"
RUN_ID = "elixir-phoenix-liveview-seed-v1"
TAXONOMY_BASE = REPO_ROOT / "taxonomy" / "elixir"

# Ordered dimensions: foundation first, then capabilities
DIMENSIONS = [
    ("architectural-stance", "foundation"),
    ("heex-and-verified-routes", "capability"),
    ("function-components-and-slots", "capability"),
    ("live-components-stateful", "capability"),
    ("form-handling", "capability"),
    ("streams-and-collections", "capability"),
    ("mount-and-lifecycle", "capability"),
    ("event-handlers-and-handle-info", "capability"),
    ("pubsub-and-realtime", "capability"),
    ("navigation-patterns", "capability"),
    ("auth-and-authz", "capability"),
    ("anti-patterns-catalog", "capability"),
]

# Dimension descriptions for spawner prompts
DIMENSION_DESCRIPTIONS = {
    "architectural-stance": "Overall module structure: LiveView modules own state, function components are stateless, context modules handle DB. Separation of concerns, module naming, code organization.",
    "heex-and-verified-routes": "HEEx template syntax, verified routes with ~p sigil, assigns in templates, dynamic attributes, component slots in templates.",
    "function-components-and-slots": "Stateless function components with attr/slot declarations, default values, required attributes, named slots, rendering patterns.",
    "live-components-stateful": "Stateful LiveComponent modules with update/mount lifecycle, send_update patterns, component communication, ID requirements.",
    "form-handling": "Phoenix.HTML.Form integration, changesets in forms, to_form/1, validate events, phx-change/phx-submit, error handling, nested forms.",
    "streams-and-collections": "LiveView streams for efficient collection rendering, stream/3, stream_insert, stream_delete, reset: true, phx-update='stream'.",
    "mount-and-lifecycle": "mount/3 callback patterns, handle_params, on_mount hooks, connected?/1 checks, assign_new, temporary_assigns.",
    "event-handlers-and-handle-info": "handle_event/3 for user interactions, handle_info/2 for server-side messages, Process.send_after, event validation.",
    "pubsub-and-realtime": "Phoenix.PubSub subscribe/broadcast patterns, topic naming, handle_info for PubSub messages, real-time updates across processes.",
    "navigation-patterns": "push_patch vs push_navigate vs redirect, ~p verified routes, handle_params for URL state, live_session scoping.",
    "auth-and-authz": "on_mount hooks for authentication, current_user assignment, authorization checks in mount and handle_event, live_session hooks.",
    "anti-patterns-catalog": "Common LiveView mistakes to avoid: DB queries in render, large assigns, missing connected? checks, improper component communication.",
}


def sample_challenges(dimension: str, num: int = 2) -> list[dict]:
    """Sample challenges using the existing script."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "mock_pipeline" / "sample_challenges.py"),
         "--family-slug", FAMILY_SLUG,
         "--dimension", dimension,
         "--num", str(num)],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        print(f"  WARNING: sample_challenges failed: {result.stderr[:200]}")
        return []
    return json.loads(result.stdout)


async def get_seed_skill_md(dimension: str) -> str:
    """Get the seed SKILL.md content from the DB."""
    genome_id = f"gen_seed_elixir_phoenix_liveview_{dimension.replace('-', '_')}"
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT skill_md_content FROM skill_genomes WHERE id = ?",
            (genome_id,)
        ) as cur:
            row = await cur.fetchone()
    if row is None:
        raise RuntimeError(f"Seed genome {genome_id} not found")
    return row["skill_md_content"]


def dispatch_claude(prompt: str, model: str, timeout: int = 180) -> tuple[str, int]:
    """Dispatch via claude CLI. Returns (response_text, duration_ms)."""
    start = time.time()
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", model, "--max-turns", "1",
         "--output-format", "text"],
        capture_output=True, text=True, timeout=timeout,
    )
    duration_ms = int((time.time() - start) * 1000)
    if result.returncode != 0:
        print(f"  WARNING: claude dispatch returned {result.returncode}: {result.stderr[:200]}")
    return result.stdout, duration_ms


def extract_files(text: str) -> dict[str, str]:
    """Extract code files from fenced blocks."""
    files = {}
    for m in re.finditer(r'```\w*\s+path=["\']?([^"\'>\s]+)["\']?\s*\n(.*?)\n```', text, re.DOTALL):
        files[m.group(1)] = m.group(2)
    if not files:
        for m in re.finditer(r'```\w*\s*\n#\s*(\S+\.ex\S*)\s*\n(.*?)\n```', text, re.DOTALL):
            files[m.group(1)] = m.group(2)
    # Fallback: if still no files, try to extract any elixir code block
    if not files:
        for m in re.finditer(r'```elixir\s*\n(.*?)\n```', text, re.DOTALL):
            code = m.group(1)
            # Try to infer filename from defmodule
            mod_match = re.search(r'defmodule\s+([\w.]+)', code)
            if mod_match:
                mod_name = mod_match.group(1)
                # Convert MyAppWeb.FooLive to lib/my_app_web/live/foo_live.ex
                parts = mod_name.split(".")
                path_parts = []
                for p in parts:
                    # CamelCase to snake_case
                    s = re.sub(r'([A-Z])', r'_\1', p).strip('_').lower()
                    path_parts.append(s)
                fname = "lib/" + "/".join(path_parts) + ".ex"
                files[fname] = code
                break
    return files


def load_fixture(fixture_path: str) -> str:
    """Load a fixture file."""
    full_path = TAXONOMY_BASE / FAMILY_SLUG / fixture_path
    return full_path.read_text() if full_path.exists() else ""


def build_competitor_prompt(challenge: dict, skill_md: str) -> str:
    """Build the competitor prompt with skill context + challenge."""
    parts = []
    # Inject the skill variant as context
    parts.append("You have the following skill guidance for Phoenix LiveView:\n")
    parts.append(f"```\n{skill_md}\n```\n")
    parts.append("You are solving an Elixir coding challenge.\n")
    for fixture_path in challenge.get("fixture_files", []):
        content = load_fixture(fixture_path)
        if content:
            parts.append(f"Fixture file ({fixture_path}):\n```elixir\n{content}\n```\n")
    parts.append(f"CHALLENGE: {challenge['prompt']}\n")
    expected = challenge.get("expected_outputs", {}).get("files", [])
    if expected:
        parts.append(f"Expected output files: {', '.join(expected)}\n")
    parts.append("Produce ONLY fenced code blocks with path attribute. No preamble, no explanation.\n")
    for f in expected:
        parts.append(f'```elixir path="{f}"\n...\n```')
    return "\n".join(parts)


def build_spawner_prompt(dimension: str, seed_skill_md: str) -> str:
    """Build the spawner prompt for creating a diverse alternative variant."""
    desc = DIMENSION_DESCRIPTIONS.get(dimension, dimension)
    return f"""You are creating an alternative variant for the '{dimension}' dimension of a Phoenix LiveView skill.

Here is the seed variant:
```
{seed_skill_md}
```

Create a DIVERSE alternative approach to the same dimension. Your variant should:
1. Take a fundamentally different angle or philosophy from the seed
2. Use different code patterns, naming conventions, or structural approaches
3. Still be correct and idiomatic Elixir/Phoenix LiveView
4. Include concrete code examples

Focus on: {desc}

Write ONLY the SKILL.md content including frontmatter (---/name/description/---). The body should be 50-150 lines of actionable guidance with code examples. Do NOT explain what you're doing - just produce the SKILL.md content."""


def score_output(challenge_path: str, output_files: dict[str, str]) -> dict:
    """Score using composite scorer."""
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "scoring"))
    from composite_scorer import composite_score
    return composite_score(FAMILY_SLUG, challenge_path, output_files)


async def save_dispatch_transcript(
    family_slug: str,
    challenge_id: str,
    dispatch_type: str,
    model: str,
    prompt: str,
    response: str,
    output_files: dict,
    duration_ms: int,
    scores: dict | None = None,
    skill_variant: str | None = None,
    error: str | None = None,
):
    """Save a dispatch transcript to the DB."""
    tid = f"p5-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    total_tokens = len(prompt.split()) + len(response.split())
    await save_transcript(
        id=tid,
        family_slug=family_slug,
        challenge_id=challenge_id,
        dispatch_type=dispatch_type,
        model=model,
        prompt=prompt[:10000],
        raw_response=response[:10000],
        extracted_files=output_files,
        total_tokens=total_tokens,
        duration_ms=duration_ms,
        error=error,
        created_at=now,
        run_id=RUN_ID,
        skill_variant=skill_variant,
        scores=scores or {},
        db_path=DB_PATH,
    )


async def run_dimension(
    dimension: str,
    tier: str,
    dim_index: int,
    total_dims: int,
    dry_run: bool = False,
) -> dict:
    """Run the full pipeline for a single dimension. Returns summary dict."""
    print(f"\n{'='*60}")
    print(f"[{dim_index+1}/{total_dims}] Dimension: {dimension} ({tier})")
    print(f"{'='*60}")

    # --- Step a: Sample challenges ---
    print("  Step 1: Sampling 2 challenges...")
    challenges = sample_challenges(dimension, num=2)
    if not challenges:
        print(f"  ERROR: No challenges found for {dimension}")
        return {"dimension": dimension, "error": "no challenges"}
    print(f"  Sampled: {[c['id'] for c in challenges]}")

    # Save challenges to temp file for persist_variant
    challenges_tmp = Path(tempfile.mktemp(suffix=".json", prefix=f"skld-ch-{dimension}-"))
    challenges_tmp.write_text(json.dumps(challenges, indent=2))

    # --- Step b: Get seed + spawn alternative ---
    print("  Step 2: Loading seed variant...")
    seed_skill_md = await get_seed_skill_md(dimension)
    print(f"  Seed loaded ({len(seed_skill_md)} chars)")

    print("  Step 3: Spawning alternative variant via Opus...")
    if dry_run:
        spawn_skill_md = seed_skill_md  # In dry-run, use seed as "spawn"
        spawn_duration = 0
    else:
        spawner_prompt = build_spawner_prompt(dimension, seed_skill_md)
        spawn_response, spawn_duration = dispatch_claude(
            spawner_prompt, "claude-opus-4-6", timeout=120
        )
        spawn_skill_md = spawn_response.strip()
        if not spawn_skill_md:
            print("  WARNING: Empty spawn response, using seed as fallback")
            spawn_skill_md = seed_skill_md

        # Save spawner transcript
        await save_dispatch_transcript(
            family_slug=FAMILY_SLUG,
            challenge_id=f"spawn-{dimension}",
            dispatch_type="spawner",
            model="claude-opus-4-6",
            prompt=spawner_prompt,
            response=spawn_response,
            output_files={},
            duration_ms=spawn_duration,
            skill_variant=f"spawn-{dimension}",
        )
    print(f"  Spawn complete ({len(spawn_skill_md)} chars, {spawn_duration}ms)")

    # --- Step c+d: Dispatch competitors and score ---
    variants = {
        "seed": seed_skill_md,
        "spawn": spawn_skill_md,
    }
    scores_by_variant: dict[str, list[float]] = {"seed": [], "spawn": []}
    score_details: dict[str, list[dict]] = {"seed": [], "spawn": []}

    for var_name, skill_md in variants.items():
        for ch_idx, challenge in enumerate(challenges):
            ch_id = challenge["id"]
            print(f"  Step 4: Competing {var_name} on {ch_id}...")

            if dry_run:
                comp_score = {"composite": 0.5, "l0": {"score": 0.5}, "compile": {"compiles": True}}
                output_files = {}
                comp_response = "[dry-run]"
                comp_duration = 0
            else:
                prompt = build_competitor_prompt(challenge, skill_md)
                comp_response, comp_duration = dispatch_claude(
                    prompt, "claude-sonnet-4-6", timeout=180
                )
                output_files = extract_files(comp_response)
                if output_files:
                    comp_score = score_output(challenge["path"], output_files)
                else:
                    comp_score = {"composite": 0.0, "l0": {"score": 0.0},
                                  "compile": {"compiles": False, "errors": ["no files extracted"]}}

                # Save competitor transcript
                await save_dispatch_transcript(
                    family_slug=FAMILY_SLUG,
                    challenge_id=ch_id,
                    dispatch_type="competitor",
                    model="claude-sonnet-4-6",
                    prompt=prompt,
                    response=comp_response,
                    output_files=output_files,
                    duration_ms=comp_duration,
                    scores=comp_score,
                    skill_variant=f"{var_name}-{dimension}",
                )

            composite = comp_score.get("composite", 0.0)
            scores_by_variant[var_name].append(composite)
            score_details[var_name].append(comp_score)
            l0 = comp_score.get("l0", {}).get("score", 0.0)
            compiles = comp_score.get("compile", {}).get("compiles", False)
            print(f"    {var_name}/{ch_id}: composite={composite:.4f} l0={l0:.4f} compiles={compiles}")

    # --- Step e: Pick winner ---
    seed_mean = sum(scores_by_variant["seed"]) / max(len(scores_by_variant["seed"]), 1)
    spawn_mean = sum(scores_by_variant["spawn"]) / max(len(scores_by_variant["spawn"]), 1)
    winner = "seed" if seed_mean >= spawn_mean else "spawn"
    delta = abs(seed_mean - spawn_mean)
    winner_mean = max(seed_mean, spawn_mean)

    print(f"\n  RESULTS:")
    print(f"    Seed mean:  {seed_mean:.4f}")
    print(f"    Spawn mean: {spawn_mean:.4f}")
    print(f"    Winner: {winner} (+{delta:.4f})")

    # --- Step f: Persist winner ---
    winner_skill_md = variants[winner]
    winner_genome_id = f"gen_seed_elixir_phoenix_liveview_{dimension.replace('-', '_')}_winner"
    vevo_id = f"vevo_elixir_phoenix_liveview_{dimension.replace('-', '_')}"

    # Write winner SKILL.md to temp file
    winner_tmp = Path(tempfile.mktemp(suffix=".md", prefix=f"skld-winner-{dimension}-"))
    winner_tmp.write_text(winner_skill_md)

    print(f"  Step 5: Persisting winner ({winner})...")
    persist_result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "mock_pipeline" / "persist_variant.py"),
         "--run-id", RUN_ID,
         "--vevo-id", vevo_id,
         "--family-id", FAMILY_ID,
         "--family-slug", FAMILY_SLUG,
         "--dimension", dimension,
         "--tier", tier,
         "--genome-id", winner_genome_id,
         "--skill-md-path", str(winner_tmp),
         "--fitness", str(round(winner_mean, 4)),
         "--challenges-json", str(challenges_tmp)],
        capture_output=True, text=True, timeout=30,
    )
    if persist_result.returncode != 0:
        print(f"  WARNING: persist_variant failed: {persist_result.stderr[:300]}")
    else:
        print(f"  Persisted: {persist_result.stdout.strip()}")

    # Cleanup temp files
    winner_tmp.unlink(missing_ok=True)
    challenges_tmp.unlink(missing_ok=True)

    return {
        "dimension": dimension,
        "tier": tier,
        "seed_mean": round(seed_mean, 4),
        "spawn_mean": round(spawn_mean, 4),
        "winner": winner,
        "delta": round(delta, 4),
        "challenges": [c["id"] for c in challenges],
        "seed_details": score_details["seed"],
        "spawn_details": score_details["spawn"],
    }


async def assemble_composite(dimension_results: list[dict]) -> str:
    """Dispatch Engineer to assemble composite from winning variants."""
    print(f"\n{'='*60}")
    print("ASSEMBLING COMPOSITE")
    print(f"{'='*60}")

    # Collect all winning SKILL.md sections
    winner_sections = []
    for result in dimension_results:
        dim = result["dimension"]
        tier = result["tier"]
        winner = result["winner"]
        genome_id = f"gen_seed_elixir_phoenix_liveview_{dim.replace('-', '_')}_winner"

        async with aiosqlite.connect(DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT skill_md_content FROM skill_genomes WHERE id = ?",
                (genome_id,)
            ) as cur:
                row = await cur.fetchone()
        if row:
            winner_sections.append(f"## {dim} ({tier}, winner={winner})\n{row['skill_md_content']}")

    all_sections = "\n\n---\n\n".join(winner_sections)

    engineer_prompt = f"""You are the Engineer agent assembling a composite Phoenix LiveView skill from 12 winning dimension variants.

Each dimension's winning variant is below, separated by ---. Your job:
1. Create a unified SKILL.md that combines ALL winning variants into one coherent skill
2. Start with the foundation (architectural-stance) as the skeleton
3. Merge each capability dimension's guidance into the appropriate section
4. Resolve any conflicts between dimensions (foundation wins on structural decisions)
5. Keep the final SKILL.md under 500 lines
6. Include frontmatter (---/name/description/---)
7. Include 2-3 diverse examples that demonstrate multiple dimensions working together

WINNING VARIANTS:

{all_sections}

Produce ONLY the final composite SKILL.md content. No explanation."""

    print("  Dispatching Engineer via Opus...")
    response, duration = dispatch_claude(engineer_prompt, "claude-opus-4-6", timeout=180)
    composite_md = response.strip()

    # Save transcript
    await save_dispatch_transcript(
        family_slug=FAMILY_SLUG,
        challenge_id="composite-assembly",
        dispatch_type="engineer",
        model="claude-opus-4-6",
        prompt=engineer_prompt[:10000],
        response=response[:10000],
        output_files={},
        duration_ms=duration,
        skill_variant="composite",
    )

    print(f"  Composite assembled ({len(composite_md)} chars, {duration}ms)")
    return composite_md


async def main():
    parser = argparse.ArgumentParser(description="Phase 5: Full scored mock run")
    parser.add_argument("--start-dim", type=int, default=0, help="Start from dimension index (0-based)")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual dispatches")
    args = parser.parse_args()

    await init_db()

    total = len(DIMENSIONS)
    results: list[dict] = []

    for idx, (dimension, tier) in enumerate(DIMENSIONS):
        if idx < args.start_dim:
            print(f"  Skipping {dimension} (before start_dim={args.start_dim})")
            continue

        result = await run_dimension(dimension, tier, idx, total, args.dry_run)
        results.append(result)

        # Print running summary
        print(f"\n  --- Running Summary ({len(results)}/{total}) ---")
        for r in results:
            if "error" in r:
                print(f"  {r['dimension']}: ERROR - {r['error']}")
            else:
                print(f"  {r['dimension']}: seed={r['seed_mean']:.4f} spawn={r['spawn_mean']:.4f} winner={r['winner']} (+{r['delta']:.4f})")

    # --- Final summary ---
    print(f"\n\n{'='*60}")
    print("FULL RESULTS TABLE")
    print(f"{'='*60}")
    print(f"{'Dimension':<40} {'Seed':>8} {'Spawn':>8} {'Winner':>8} {'Delta':>8}")
    print("-" * 72)
    for r in results:
        if "error" in r:
            print(f"{r['dimension']:<40} {'ERROR':>8}")
        else:
            print(f"{r['dimension']:<40} {r['seed_mean']:>8.4f} {r['spawn_mean']:>8.4f} {r['winner']:>8} {r['delta']:>8.4f}")

    # Compute aggregates
    valid = [r for r in results if "error" not in r]
    if valid:
        avg_winner = sum(max(r["seed_mean"], r["spawn_mean"]) for r in valid) / len(valid)
        seed_wins = sum(1 for r in valid if r["winner"] == "seed")
        spawn_wins = sum(1 for r in valid if r["winner"] == "spawn")
        print(f"\nAvg winner score: {avg_winner:.4f}")
        print(f"Seed wins: {seed_wins}, Spawn wins: {spawn_wins}")

    # --- Assemble composite ---
    if not args.dry_run and len(valid) == total:
        composite_md = await assemble_composite(results)

        # Write composite
        composite_path = Path(tempfile.mktemp(suffix=".md", prefix="skld-composite-"))
        composite_path.write_text(composite_md)

        # Finalize run
        print("\n  Finalizing run...")
        finalize_result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "mock_pipeline" / "finalize_run.py"),
             "--run-id", RUN_ID,
             "--composite-skill-md-path", str(composite_path),
             "--total-cost-usd", "0.0"],  # Will compute real cost from transcripts
            capture_output=True, text=True, timeout=30,
        )
        if finalize_result.returncode != 0:
            print(f"  WARNING: finalize_run failed: {finalize_result.stderr[:300]}")
        else:
            print(f"  Finalized: {finalize_result.stdout.strip()}")

        composite_path.unlink(missing_ok=True)
    elif args.dry_run:
        print("\n  [dry-run] Skipping composite assembly and finalization")

    # Save results to JSON for reference
    results_path = REPO_ROOT / "scripts" / "mock_pipeline" / "phase5_results.json"
    results_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nResults saved to {results_path}")


if __name__ == "__main__":
    asyncio.run(main())
