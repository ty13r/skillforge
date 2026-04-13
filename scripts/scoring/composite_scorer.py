#!/usr/bin/env python3
"""Composite scorer — orchestrates L0 string match, compilation check,
and AST quality analysis into a single graduated fitness score.

Usage:
    uv run python scripts/scoring/composite_scorer.py \
        --family elixir-phoenix-liveview \
        --challenge taxonomy/elixir/elixir-phoenix-liveview/challenges/hard/hard-07.json \
        --output-dir /path/to/output/files/ \
        [--scaffold taxonomy/elixir/elixir-phoenix-liveview/scaffold/skld_bench]

Can also be used as a library:
    from scripts.scoring.composite_scorer import composite_score
    result = composite_score(family_slug, challenge_path, output_files, scaffold_path)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
TAXONOMY_BASE = PROJECT_ROOT / "taxonomy" / "elixir"

# Default scaffolds per family
SCAFFOLD_PATHS = {
    "elixir-phoenix-liveview": TAXONOMY_BASE / "elixir-phoenix-liveview" / "scaffold" / "skld_bench",
    "elixir-ecto-schema-changeset": TAXONOMY_BASE / "elixir-ecto-schema-changeset" / "scaffold" / "skld_bench",
    "elixir-ecto-query-writer": TAXONOMY_BASE / "elixir-ecto-query-writer" / "scaffold" / "skld_bench",
    "elixir-ecto-sandbox-test": TAXONOMY_BASE / "elixir-ecto-sandbox-test" / "scaffold" / "skld_bench",
    "elixir-security-linter": TAXONOMY_BASE / "elixir-security-linter" / "scaffold" / "skld_bench",
    "elixir-oban-worker": TAXONOMY_BASE / "elixir-oban-worker" / "scaffold" / "skld_bench",
    "elixir-pattern-match-refactor": TAXONOMY_BASE / "elixir-pattern-match-refactor" / "scaffold" / "skld_bench",
}

# Default namespace mappings per family
NAMESPACE_MAPS = {
    "elixir-phoenix-liveview": [("MyAppWeb", "SkldBenchWeb"), ("MyApp", "SkldBench")],
    "elixir-ecto-sandbox-test": [("MyAppWeb", "SkldSandboxWeb"), ("MyApp", "SkldSandbox")],
    "elixir-security-linter": [("MyAppWeb", "SkldBenchWeb"), ("MyApp", "SkldBench")],
    "elixir-ecto-schema-changeset": [("MyApp", "SkldEcto")],
    "elixir-ecto-query-writer": [("MyApp", "SkldEcto")],
    "elixir-oban-worker": [("MyApp", "SkldOban")],
    "elixir-pattern-match-refactor": [("MyApp", "SkldPatternMatch")],
}

# Phase 1 weights (no behavioral tests yet)
# Recalibrated in Phase 2 when behavioral tests are added
WEIGHTS_PHASE1 = {
    "l0": 0.25,
    "compile": 0.30,
    "ast": 0.25,
    "brevity": 0.20,
}

# Phase 2+ weights (with behavioral tests)
WEIGHTS_PHASE2 = {
    "l0": 0.10,
    "compile": 0.15,
    "ast": 0.15,
    "behavioral": 0.40,
    "template": 0.10,
    "brevity": 0.10,
}


def run_l0_scorer(family_slug: str, challenge_path: Path, output_dir: Path) -> dict:
    """Run the family's score.py L0 string-match scorer."""
    scorer_path = TAXONOMY_BASE / family_slug / "evaluation" / "score.py"
    if not scorer_path.exists():
        return {"score": 0.0, "passed": False, "objectives": {}, "diagnostics": ["scorer not found"]}

    try:
        result = subprocess.run(
            [sys.executable, str(scorer_path),
             "--challenge", str(challenge_path),
             "--output", str(output_dir)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return {"score": 0.0, "passed": False, "objectives": {},
                    "diagnostics": [f"scorer exit {result.returncode}: {result.stderr[:500]}"]}
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return {"score": 0.0, "passed": False, "objectives": {}, "diagnostics": [str(e)]}


def run_compile_check(code_files: dict[str, str], scaffold_path: Path,
                      namespace_map: list[tuple[str, str]]) -> dict:
    """Run compilation check via compile_check module."""
    # Import locally to avoid circular issues when used as script
    sys.path.insert(0, str(SCRIPT_DIR))
    from compile_check import compile_check
    return compile_check(code_files, scaffold_path, namespace_map)


def run_behavioral(code_files: dict[str, str], scaffold_path: Path,
                    namespace_map: list[tuple[str, str]],
                    test_file: Path | None = None) -> dict:
    """Run behavioral tests via the test runner."""
    sys.path.insert(0, str(SCRIPT_DIR))
    from behavioral_test_runner import run_behavioral_test
    return run_behavioral_test(code_files, scaffold_path, namespace_map, test_file)


def run_ast_analyze(code: str) -> dict:
    """Run AST quality analysis."""
    sys.path.insert(0, str(SCRIPT_DIR))
    from ast_analyze import ast_analyze
    return ast_analyze(code)


def compute_ast_score(ast: dict) -> float:
    """Compute a 0.0-1.0 AST quality score from metrics."""
    impl_cov = ast.get("impl_coverage", 0.0)
    pipe_dens = min(ast.get("pipe_density", 0.0) / 3.0, 1.0)  # Normalize: 3.0 = excellent
    return impl_cov * 0.5 + pipe_dens * 0.5


def compute_template_score(ast: dict) -> float:
    """Compute template modernity score (HEEx modern vs legacy)."""
    return ast.get("template_modernity", 1.0)


def compute_brevity_score(loc: int, optimal: int = 40, penalty_range: int = 100) -> float:
    """Penalize verbose code. Optimal ~40 LOC, penalty starts above that."""
    return max(0.0, min(1.0, 1.0 - (loc - optimal) / penalty_range))


def composite_score(
    family_slug: str,
    challenge_path: Path | str,
    output_files: dict[str, str],
    scaffold_path: Path | None = None,
    namespace_map: list[tuple[str, str]] | None = None,
    behavioral_result: dict | None = None,
    run_behavioral_tests: bool = False,
    test_file: Path | None = None,
    weights: dict | None = None,
) -> dict:
    """Compute a multi-level composite fitness score.

    Args:
        family_slug: Family identifier.
        challenge_path: Path to the challenge JSON.
        output_files: Dict of {path: content} — the code to score.
        scaffold_path: Path to Mix scaffold for compilation.
        namespace_map: Namespace replacements for compilation.
        behavioral_result: Optional pre-computed {passed, total} from ExUnit tests.
        run_behavioral_tests: If True, run generic behavioral tests via the test runner.
        test_file: Optional challenge-specific test file for behavioral testing.
        weights: Optional weight override. Defaults to WEIGHTS_PHASE1.

    Returns:
        Dict with full score breakdown and composite.
    """
    challenge_path = Path(challenge_path)
    scaffold_path = scaffold_path or SCAFFOLD_PATHS.get(family_slug)
    namespace_map = namespace_map or NAMESPACE_MAPS.get(family_slug, [])

    if behavioral_result:
        w = weights or WEIGHTS_PHASE2
    else:
        w = weights or WEIGHTS_PHASE1

    # Concatenate all code for analysis
    all_code = "\n".join(output_files.values())
    if not all_code.strip():
        return {
            "l0": {"score": 0.0, "passed": False},
            "compile": {"compiles": False, "errors": ["no code"]},
            "ast": {},
            "brevity": 0.0,
            "composite": 0.0,
        }

    # --- L0: String-match scorer ---
    # Write files to a temp dir for the L0 scorer
    import tempfile
    with tempfile.TemporaryDirectory(prefix="skld-score-") as tmp:
        tmp_path = Path(tmp)
        for rel_path, content in output_files.items():
            out = tmp_path / rel_path
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(content)

        l0_result = run_l0_scorer(family_slug, challenge_path, tmp_path)

    l0_score = l0_result.get("score", 0.0)

    # --- Compile check ---
    compile_result = {"compiles": False, "warnings": 0, "errors": ["no scaffold"]}
    if scaffold_path and scaffold_path.exists():
        try:
            compile_result = run_compile_check(output_files, scaffold_path, namespace_map)
        except FileNotFoundError:
            compile_result = {"compiles": False, "warnings": 0,
                              "errors": ["mix/elixir not installed"]}
    compile_score = 1.0 if compile_result.get("compiles", False) else 0.0

    # --- AST analysis ---
    ast_result = run_ast_analyze(all_code)
    ast_score = compute_ast_score(ast_result)

    # --- Template quality ---
    template_score = compute_template_score(ast_result)

    # --- Brevity ---
    loc = ast_result.get("non_empty_lines", 0)
    brevity_score = compute_brevity_score(loc)

    # --- Behavioral tests (Phase 2+) ---
    behavioral_score = 0.0
    if run_behavioral_tests and not behavioral_result and scaffold_path:
        behavioral_result = run_behavioral(
            output_files, scaffold_path, namespace_map, test_file
        )
    if behavioral_result:
        total = behavioral_result.get("total", 1)
        passed = behavioral_result.get("passed", 0)
        behavioral_score = passed / max(total, 1)

    # --- Composite ---
    composite = (
        l0_score * w.get("l0", 0) +
        compile_score * w.get("compile", 0) +
        ast_score * w.get("ast", 0) +
        brevity_score * w.get("brevity", 0) +
        template_score * w.get("template", 0) +
        behavioral_score * w.get("behavioral", 0)
    )

    return {
        "l0": {
            "score": round(l0_score, 4),
            "passed": l0_result.get("passed", False),
            "objectives": l0_result.get("objectives", {}),
        },
        "compile": {
            "compiles": compile_result.get("compiles", False),
            "warnings": compile_result.get("warnings", 0),
            "errors": compile_result.get("errors", []),
            "duration_ms": compile_result.get("duration_ms", 0),
        },
        "ast": {
            "functions": ast_result.get("functions", 0),
            "impl_coverage": ast_result.get("impl_coverage", 0.0),
            "pipe_density": ast_result.get("pipe_density", 0.0),
            "loc": loc,
            "score": round(ast_score, 4),
        },
        "template": {
            "modern": ast_result.get("heex_modern", 0),
            "legacy": ast_result.get("heex_legacy", 0),
            "score": round(template_score, 4),
        },
        "brevity": round(brevity_score, 4),
        "behavioral": {
            "passed": behavioral_result.get("passed", 0) if behavioral_result else None,
            "total": behavioral_result.get("total", 0) if behavioral_result else None,
            "score": round(behavioral_score, 4),
        } if behavioral_result else None,
        "composite": round(composite, 4),
        "weights": w,
    }


def main():
    parser = argparse.ArgumentParser(description="Composite scorer for SKLD-bench")
    parser.add_argument("--family", required=True, help="Family slug")
    parser.add_argument("--challenge", required=True, help="Path to challenge JSON")
    parser.add_argument("--output-dir", required=True, help="Path to output files directory")
    parser.add_argument("--scaffold", help="Path to Mix scaffold (optional, auto-detected)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_files = {}
    for f in output_dir.rglob("*.ex"):
        rel = str(f.relative_to(output_dir))
        output_files[rel] = f.read_text()

    scaffold = Path(args.scaffold) if args.scaffold else None
    result = composite_score(args.family, args.challenge, output_files, scaffold)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
