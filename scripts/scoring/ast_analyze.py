#!/usr/bin/env python3
"""AST quality analysis for Elixir code.

Shells out to the ast_quality.exs Elixir script for real AST walking,
with a regex-based Python fallback for environments without Elixir.

Usage:
    uv run python scripts/scoring/ast_analyze.py --code /path/to/file.ex
    uv run python scripts/scoring/ast_analyze.py --code-string "defmodule Foo do ... end"
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
AST_QUALITY_EXS = SCRIPT_DIR / "ast_quality.exs"


def ast_analyze_elixir(code: str) -> dict | None:
    """Run the Elixir AST analyzer. Returns None if Elixir is unavailable."""
    if not AST_QUALITY_EXS.exists():
        return None

    with tempfile.NamedTemporaryFile(suffix=".ex", mode="w", delete=False) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["elixir", str(AST_QUALITY_EXS), tmp_path],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout.strip())
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def ast_analyze_regex(code: str) -> dict:
    """Regex-based fallback AST analysis (no Elixir dependency)."""
    lines = code.split("\n")
    non_empty = [l for l in lines if l.strip()]

    functions = len(re.findall(r"^\s*def\s+\w+", code, re.MULTILINE))
    private_functions = len(re.findall(r"^\s*defp\s+\w+", code, re.MULTILINE))
    impl_annotations = len(re.findall(r"@impl\s+true", code))
    pipe_chains = len(re.findall(r"\|>", code))
    pattern_match_heads = len(re.findall(r"^\s*def\s+\w+\(.*%\{", code, re.MULTILINE))
    guard_clauses = len(re.findall(r"\bwhen\s+", code))
    module_attributes = len(re.findall(r"^\s*@(?!impl|doc|moduledoc|behaviour|derive|type|spec|callback)\w+\s", code, re.MULTILINE))
    case_expressions = len(re.findall(r"\bcase\s+", code))
    if_expressions = len(re.findall(r"\bif\s+", code))

    # Template patterns
    heex_modern = len(re.findall(r"\{[^}]+\}", code))
    heex_legacy = len(re.findall(r"<%=.*?%>", code))
    for_directive = len(re.findall(r":for=", code))
    if_directive = len(re.findall(r":if=", code))
    for_legacy = len(re.findall(r"<%= for\b", code))
    if_legacy = len(re.findall(r"<%= if\b", code))

    total_fns = functions + private_functions
    return {
        "functions": functions,
        "private_functions": private_functions,
        "impl_annotations": impl_annotations,
        "pipe_chains": pipe_chains,
        "pattern_match_heads": pattern_match_heads,
        "guard_clauses": guard_clauses,
        "module_attributes": module_attributes,
        "case_expressions": case_expressions,
        "if_expressions": if_expressions,
        "total_lines": len(lines),
        "non_empty_lines": len(non_empty),
        "heex_modern": heex_modern,
        "heex_legacy": heex_legacy,
        "for_directive": for_directive,
        "if_directive": if_directive,
        "for_legacy": for_legacy,
        "if_legacy": if_legacy,
        "avg_fn_length": round(len(non_empty) / total_fns, 1) if total_fns > 0 else 0.0,
        "impl_coverage": round(min(impl_annotations / functions, 1.0), 2) if functions > 0 else 0.0,
        "pipe_density": round(pipe_chains / len(non_empty) * 10, 2) if non_empty else 0.0,
        "template_modernity": round(heex_modern / (heex_modern + heex_legacy), 2) if (heex_modern + heex_legacy) > 0 else 1.0,
    }


def ast_analyze(code: str) -> dict:
    """Analyze Elixir code for AST quality metrics. Tries Elixir first, regex fallback."""
    result = ast_analyze_elixir(code)
    if result is not None:
        result["analyzer"] = "elixir"
        return result
    result = ast_analyze_regex(code)
    result["analyzer"] = "regex_fallback"
    return result


def main():
    parser = argparse.ArgumentParser(description="AST quality analysis for Elixir")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--code", help="Path to .ex file")
    group.add_argument("--code-string", help="Elixir code as string")
    args = parser.parse_args()

    if args.code:
        code = Path(args.code).read_text()
    else:
        code = args.code_string

    result = ast_analyze(code)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
