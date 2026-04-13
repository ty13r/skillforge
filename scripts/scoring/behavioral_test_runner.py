#!/usr/bin/env python3
"""Behavioral test runner for SKLD-bench.

Copies candidate Elixir code into a Phoenix scaffold, runs ExUnit tests
against it, and parses results.

Two modes:
1. **Generic test**: Compiles the code + runs a generic "mount and don't crash" test
2. **Challenge-specific test**: Runs a hand-written/generated test file

Usage:
    uv run python scripts/scoring/behavioral_test_runner.py \
        --code-files '{"lib/my_app_web/live/foo_live.ex": "defmodule ..."}' \
        --scaffold taxonomy/elixir/elixir-phoenix-liveview/scaffold/skld_bench \
        [--test-file taxonomy/elixir/elixir-phoenix-liveview/tests/hard-07_test.exs] \
        [--namespace MyAppWeb=SkldBenchWeb,MyApp=SkldBench]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path


def namespace_adapt(code: str, mappings: list[tuple[str, str]]) -> str:
    """Replace module namespace prefixes in code."""
    for old, new in mappings:
        code = re.sub(rf"\b{re.escape(old)}\b", new, code)
    return code


def extract_module_name(code: str) -> str | None:
    """Extract the defmodule name from Elixir source code."""
    m = re.search(r"defmodule\s+([\w.]+)\s+do", code)
    return m.group(1) if m else None


def extract_handle_events(code: str) -> list[str]:
    """Extract event names from handle_event definitions."""
    return re.findall(r'def\s+handle_event\s*\(\s*"(\w+)"', code)


def generate_generic_test(module_name: str, events: list[str]) -> str:
    """Generate a generic behavioral test for a LiveView module.

    Tests:
    1. Module can be mounted via live_isolated without crashing
    2. Each handle_event can be called without crashing
    """
    event_tests = ""
    for event in events:
        event_tests += f"""
    test "handle_event {event!r} does not crash" do
      {{:ok, view, _html}} = live_isolated(build_conn(), {module_name})
      # Send the event — we just check it doesn't crash
      try do
        render_hook(view, "{event}", %{{}})
      rescue
        _ -> :ok  # Some events may need params; that's fine
      end
      # If we got here, the event handler exists and processed without fatal error
      assert Process.alive?(view.pid)
    end
"""

    return f"""defmodule SkldBench.BehavioralTest do
  use SkldBenchWeb.ConnCase
  import Phoenix.LiveViewTest

  describe "{module_name} behavioral tests" do
    test "mounts successfully via live_isolated" do
      {{:ok, _view, html}} = live_isolated(build_conn(), {module_name})
      assert is_binary(html)
      assert String.length(html) > 0
    end

    test "renders non-empty content" do
      {{:ok, _view, html}} = live_isolated(build_conn(), {module_name})
      # Strip HTML tags and check there's actual content
      text = Regex.replace(~r/<[^>]+>/, html, "")
      assert String.trim(text) != ""
    end
{event_tests}  end
end
"""


def run_behavioral_test(
    code_files: dict[str, str],
    scaffold_path: Path,
    namespace_map: list[tuple[str, str]] | None = None,
    test_file: Path | None = None,
    timeout: int = 30,
) -> dict:
    """Run ExUnit behavioral tests against candidate code.

    Args:
        code_files: Dict of {path: content} to compile.
        scaffold_path: Path to the Mix scaffold.
        namespace_map: Namespace replacements.
        test_file: Optional challenge-specific test file. If None, generates generic test.
        timeout: Test timeout in seconds.

    Returns:
        Dict with {passed, total, failures, duration_ms, raw_output}.
    """
    namespace_map = namespace_map or []
    written_files: list[Path] = []

    try:
        # 1. Write candidate code to scaffold lib/
        all_code = ""
        for rel_path, content in code_files.items():
            adapted = namespace_adapt(content, namespace_map)
            all_code += adapted + "\n"
            target = scaffold_path / "lib" / rel_path.lstrip("/")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(adapted)
            written_files.append(target)

        # 2. Determine test content
        if test_file and test_file.exists():
            test_content = test_file.read_text()
            # Apply namespace adaptation to the test too
            test_content = namespace_adapt(test_content, namespace_map)
        else:
            # Generate a generic behavioral test
            module_name = extract_module_name(all_code)
            if not module_name:
                return {
                    "passed": 0, "total": 0, "failures": [],
                    "duration_ms": 0, "raw_output": "Could not extract module name",
                    "error": "no_module",
                }
            events = extract_handle_events(all_code)
            test_content = generate_generic_test(module_name, events)

        # 3. Write test file
        test_path = scaffold_path / "test" / "skld_behavioral_test.exs"
        test_path.write_text(test_content)
        written_files.append(test_path)

        # 4. Run mix test
        start = time.monotonic()
        result = subprocess.run(
            ["mix", "test", str(test_path), "--no-deps-check", "--formatter",
             "ExUnit.CLIFormatter"],
            cwd=str(scaffold_path),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**__import__("os").environ, "MIX_ENV": "test"},
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        output = result.stdout + result.stderr

        # 5. Parse ExUnit output
        # Look for "X tests, Y failures" pattern
        summary_match = re.search(r"(\d+)\s+tests?,\s+(\d+)\s+failures?", output)
        if summary_match:
            total = int(summary_match.group(1))
            failures = int(summary_match.group(2))
            passed = total - failures
        else:
            # Check for compilation errors
            if "** (CompileError)" in output or "error:" in output.lower():
                return {
                    "passed": 0, "total": 1, "failures": [{"test": "compilation", "error": output[-1000:]}],
                    "duration_ms": duration_ms, "raw_output": output[-2000:],
                    "error": "compile_error",
                }
            total = 0
            passed = 0
            failures = 0

        # Extract failure details
        failure_details = []
        failure_blocks = re.findall(
            r"\d+\)\s+test\s+(.+?)(?:\n\s+\*\*\s+\((.+?)\)\s+(.+?))?(?=\n\n|\n\d+\)|\Z)",
            output, re.DOTALL
        )
        for block in failure_blocks:
            failure_details.append({
                "test": block[0].strip(),
                "error": f"{block[1]}: {block[2]}" if block[1] else "unknown",
            })

        return {
            "passed": passed,
            "total": total,
            "failures": failure_details[:10],
            "duration_ms": duration_ms,
            "raw_output": output[-2000:] if len(output) > 2000 else output,
        }

    except subprocess.TimeoutExpired:
        return {
            "passed": 0, "total": 1, "failures": [{"test": "timeout", "error": f"exceeded {timeout}s"}],
            "duration_ms": timeout * 1000, "raw_output": "",
            "error": "timeout",
        }
    except Exception as e:
        return {
            "passed": 0, "total": 0, "failures": [{"test": "runner", "error": str(e)}],
            "duration_ms": 0, "raw_output": "",
            "error": str(e),
        }
    finally:
        # Clean up candidate files
        for f in written_files:
            f.unlink(missing_ok=True)
            try:
                f.parent.rmdir()
            except OSError:
                pass


def main():
    parser = argparse.ArgumentParser(description="Run behavioral tests on Elixir code")
    parser.add_argument("--code-files", required=True,
                        help="JSON dict of {path: content}")
    parser.add_argument("--scaffold", required=True, help="Path to Mix scaffold")
    parser.add_argument("--test-file", help="Path to challenge-specific test file")
    parser.add_argument("--namespace", default="MyAppWeb=SkldBenchWeb,MyApp=SkldBench")
    args = parser.parse_args()

    code_files = json.loads(args.code_files)
    scaffold = Path(args.scaffold)
    test_file = Path(args.test_file) if args.test_file else None

    ns_map = []
    for m in args.namespace.split(","):
        if "=" in m:
            old, new = m.split("=", 1)
            ns_map.append((old.strip(), new.strip()))

    result = run_behavioral_test(code_files, scaffold, ns_map, test_file)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] == result["total"] and result["total"] > 0 else 1)


if __name__ == "__main__":
    main()
