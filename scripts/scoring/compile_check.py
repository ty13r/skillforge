#!/usr/bin/env python3
"""Compilation check for Elixir code against a per-family Mix scaffold.

Copies candidate .ex file(s) into the scaffold's lib/ directory, runs
`mix compile --force`, and reports whether compilation succeeded.

Usage:
    uv run python scripts/scoring/compile_check.py \
        --code /path/to/candidate.ex \
        --scaffold taxonomy/elixir/elixir-phoenix-liveview/scaffold/skld_bench \
        [--namespace MyApp=SkldBench]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def namespace_adapt(code: str, mappings: list[tuple[str, str]]) -> str:
    """Replace module namespace prefixes in code."""
    for old, new in mappings:
        # Replace all occurrences of the module name as a word boundary
        # Handles: MyApp.Foo, use MyApp, defmodule MyApp, alias MyApp
        code = re.sub(rf"\b{re.escape(old)}\b", new, code)
    return code


def compile_check(
    code_files: dict[str, str],
    scaffold_path: Path,
    namespace_map: list[tuple[str, str]] | None = None,
    timeout: int = 30,
) -> dict:
    """Run mix compile on code_files placed into a copy of scaffold_path.

    Args:
        code_files: Dict of {relative_path: content} to place in the scaffold.
        scaffold_path: Path to the pre-built Mix project scaffold.
        namespace_map: Optional list of (old, new) namespace replacements.
        timeout: Compile timeout in seconds.

    Returns:
        Dict with keys: compiles (bool), warnings (int), errors (list[str]),
        duration_ms (int), raw_output (str).
    """
    if not scaffold_path.exists():
        return {
            "compiles": False,
            "warnings": 0,
            "errors": [f"Scaffold not found: {scaffold_path}"],
            "duration_ms": 0,
            "raw_output": "",
        }

    # Work in the scaffold directory directly — avoid copying 100MB+ of deps.
    # We write candidate files, compile, then clean up.
    lib_dir = scaffold_path / "lib"
    written_files: list[Path] = []

    try:
        for rel_path, content in code_files.items():
            adapted = content
            if namespace_map:
                adapted = namespace_adapt(adapted, namespace_map)

            # Place file in lib/ under the scaffold
            target = lib_dir / rel_path.lstrip("/")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(adapted)
            written_files.append(target)

        # Run mix compile --force
        start = time.monotonic()
        result = subprocess.run(
            ["mix", "compile", "--force"],
            cwd=str(scaffold_path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        combined = result.stdout + result.stderr
        compiles = result.returncode == 0

        # Count warnings
        warnings = len(re.findall(r"warning:", combined))

        # Extract error lines
        errors = []
        if not compiles:
            for line in combined.splitlines():
                if "error" in line.lower() and "==" not in line:
                    errors.append(line.strip())

        return {
            "compiles": compiles,
            "warnings": warnings,
            "errors": errors[:10],  # Cap at 10 errors
            "duration_ms": duration_ms,
            "raw_output": combined[-2000:] if len(combined) > 2000 else combined,
        }

    except subprocess.TimeoutExpired:
        return {
            "compiles": False,
            "warnings": 0,
            "errors": [f"Compilation timed out after {timeout}s"],
            "duration_ms": timeout * 1000,
            "raw_output": "",
        }
    finally:
        # Clean up candidate files so scaffold stays pristine
        for f in written_files:
            f.unlink(missing_ok=True)
            # Remove empty parent dirs we may have created
            try:
                f.parent.rmdir()
            except OSError:
                pass


def main():
    parser = argparse.ArgumentParser(description="Check if Elixir code compiles")
    parser.add_argument("--code", required=True, help="Path to .ex file or directory")
    parser.add_argument("--scaffold", required=True, help="Path to Mix scaffold")
    parser.add_argument("--namespace", default="MyApp=SkldBench",
                        help="Namespace mapping (e.g., MyApp=SkldBench)")

    args = parser.parse_args()
    scaffold = Path(args.scaffold)

    # Parse namespace mapping
    ns_map = []
    for mapping in args.namespace.split(","):
        if "=" in mapping:
            old, new = mapping.split("=", 1)
            ns_map.append((old.strip(), new.strip()))

    # Read code files
    code_path = Path(args.code)
    code_files = {}
    if code_path.is_dir():
        for f in code_path.rglob("*.ex"):
            rel = str(f.relative_to(code_path))
            code_files[rel] = f.read_text()
    else:
        code_files[code_path.name] = code_path.read_text()

    result = compile_check(code_files, scaffold, ns_map)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["compiles"] else 1)


if __name__ == "__main__":
    main()
