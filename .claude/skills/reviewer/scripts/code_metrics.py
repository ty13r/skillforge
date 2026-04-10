"""AST-based code quality metrics for skill variant evaluation.

Parses Python source files with the standard-library `ast` module and emits
deterministic code-quality proxies per file:

- cyclomatic_complexity: branch count (If, For, While, Try, ExceptHandler,
  BoolOp, comprehensions) plus 1 for the entry node
- max_function_length: largest number of source lines spanned by any top-level
  or nested FunctionDef / AsyncFunctionDef
- max_nesting_depth: deepest AST nesting of control-flow / function / class
  nodes, computed recursively
- function_count: total number of function definitions
- import_count: total number of Import / ImportFrom statements

Output is JSON on stdout. For non-Python files this script returns a structured
"unsupported" record rather than failing, so callers can treat it uniformly.

Usage:
    python3 code_metrics.py --file path/to/module.py
    python3 code_metrics.py --dir path/to/package --format json
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any

# AST node types that introduce a control-flow branch and therefore add to
# cyclomatic complexity.
_BRANCH_NODES: tuple[type[ast.AST], ...] = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.ExceptHandler,
    ast.With,
    ast.AsyncWith,
    ast.IfExp,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)

# Nodes that introduce a nesting level for max_nesting_depth.
_NESTING_NODES: tuple[type[ast.AST], ...] = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.With,
    ast.AsyncWith,
)


def _cyclomatic_complexity(tree: ast.AST) -> int:
    """Return an approximate cyclomatic complexity for the whole module.

    Counts every branch node plus one for each BoolOp operand beyond the first
    (each `and`/`or` introduces a new path). The base complexity is 1.
    """
    complexity = 1
    for node in ast.walk(tree):
        if isinstance(node, _BRANCH_NODES):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            # Each additional operand introduces an extra decision point.
            complexity += max(0, len(node.values) - 1)
    return complexity


def _max_function_length(tree: ast.AST) -> int:
    """Return the line span of the longest function definition."""
    longest = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            end = getattr(node, "end_lineno", None) or start
            span = max(0, end - start + 1)
            if span > longest:
                longest = span
    return longest


def _max_nesting_depth(tree: ast.AST) -> int:
    """Recursively walk the AST tracking nesting of control-flow / scope nodes."""

    def walk(node: ast.AST, depth: int) -> int:
        deepest = depth
        for child in ast.iter_child_nodes(node):
            next_depth = depth + 1 if isinstance(child, _NESTING_NODES) else depth
            child_deepest = walk(child, next_depth)
            if child_deepest > deepest:
                deepest = child_deepest
        return deepest

    return walk(tree, 0)


def _function_count(tree: ast.AST) -> int:
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )


def _import_count(tree: ast.AST) -> int:
    return sum(
        1 for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
    )


def analyze_file(path: Path) -> dict[str, Any]:
    """Analyze a single source file and return its metrics dict."""
    suffix = path.suffix.lower()
    if suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
        return {
            "file": str(path),
            "language": "javascript",
            "status": "unsupported",
            "reason": "AST analysis limited to Python in v2.0",
        }
    if suffix != ".py":
        return {
            "file": str(path),
            "language": suffix.lstrip(".") or "unknown",
            "status": "unsupported",
            "reason": "AST analysis limited to Python in v2.0",
        }

    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {
            "file": str(path),
            "status": "error",
            "reason": f"could not read file: {exc}",
        }

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return {
            "file": str(path),
            "status": "error",
            "reason": f"syntax error on line {exc.lineno}: {exc.msg}",
        }

    return {
        "file": str(path),
        "language": "python",
        "status": "ok",
        "cyclomatic_complexity": _cyclomatic_complexity(tree),
        "max_function_length": _max_function_length(tree),
        "max_nesting_depth": _max_nesting_depth(tree),
        "function_count": _function_count(tree),
        "import_count": _import_count(tree),
    }


def analyze_dir(root: Path) -> list[dict[str, Any]]:
    """Recursively analyze every Python file under `root`."""
    results: list[dict[str, Any]] = []
    for py_file in sorted(root.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        results.append(analyze_file(py_file))
    return results


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AST-based code quality metrics for Python source files."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=Path, help="Analyze a single source file.")
    group.add_argument(
        "--dir", type=Path, help="Recursively analyze all .py files under a directory."
    )
    parser.add_argument(
        "--format",
        choices=["json"],
        default="json",
        help="Output format (only 'json' is currently supported).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.file is not None:
        if not args.file.exists():
            print(
                json.dumps({"status": "error", "reason": f"file not found: {args.file}"}),
                file=sys.stdout,
            )
            return 1
        payload: Any = analyze_file(args.file)
    else:
        if not args.dir.exists() or not args.dir.is_dir():
            print(
                json.dumps({"status": "error", "reason": f"dir not found: {args.dir}"}),
                file=sys.stdout,
            )
            return 1
        payload = {
            "root": str(args.dir),
            "files": analyze_dir(args.dir),
        }

    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
