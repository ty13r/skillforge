#!/usr/bin/env python3
"""Generate a starter skill directory structure.

Usage: python scaffold.py skill-name [--output-dir /path/to/output]
"""

import argparse
import re
import sys
from pathlib import Path


NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

SKILL_MD_TEMPLATE = """\
---
name: {name}
description: |
  TODO: Describe what this skill does and its key capabilities.
  Use when the user asks about {title_words}. NOT for unrelated tasks.
  Helps with {title_words} even if they don't explicitly ask for it.
---

## Quick Start

1. TODO: First step
2. TODO: Second step
3. TODO: Third step

## Workflow

1. **Understand the request** — Parse what the user needs.
2. **Execute** — Perform the core task.
3. **Validate** — Check the output meets quality criteria.
4. **Report** — Summarize what was done.

## Examples

**Example 1: Basic usage**
- Input: "TODO: describe a typical input"
- Output: TODO: describe what the skill produces

**Example 2: Edge case**
- Input: "TODO: describe a less obvious input"
- Output: TODO: describe output for the edge case

## Gotchas

- TODO: Common mistake #1
- TODO: Common mistake #2

## Out of Scope

- TODO: What this skill does NOT do
- TODO: Adjacent tasks the user should handle differently

## Resources

- `${{CLAUDE_SKILL_DIR}}/scripts/validate.sh` — validation script
- `${{CLAUDE_SKILL_DIR}}/scripts/main_helper.py` — helper utilities
- `${{CLAUDE_SKILL_DIR}}/references/guide.md` — domain reference
"""

VALIDATE_SH_TEMPLATE = """\
#!/usr/bin/env bash
set -euo pipefail

# Validation script for {name} skill
# Usage: bash validate.sh [target-dir]

TARGET_DIR="${{1:-.}}"

echo "Validating {name} skill output..."

# TODO: Add validation checks
# Example checks:
#   - File exists
#   - File is valid syntax
#   - Expected patterns present

echo "All checks passed."
"""

MAIN_HELPER_TEMPLATE = """\
#!/usr/bin/env python3
\"\"\"Helper utilities for the {name} skill.

This module provides reusable functions that the skill
can invoke for deterministic operations (zero context cost).
\"\"\"

import json
import sys
from pathlib import Path


def load_config(config_path: Path) -> dict:
    \"\"\"Load and return a JSON config file.\"\"\"
    if not config_path.exists():
        return {{}}
    return json.loads(config_path.read_text(encoding="utf-8"))


def validate_output(output_path: Path) -> bool:
    \"\"\"Check that the output file exists and is non-empty.\"\"\"
    if not output_path.exists():
        print(f"ERROR: {{output_path}} does not exist", file=sys.stderr)
        return False
    if output_path.stat().st_size == 0:
        print(f"ERROR: {{output_path}} is empty", file=sys.stderr)
        return False
    return True


def main() -> None:
    \"\"\"CLI entry point for direct invocation.\"\"\"
    if len(sys.argv) < 2:
        print("Usage: python main_helper.py <command> [args...]", file=sys.stderr)
        sys.exit(1)
    command = sys.argv[1]
    print(f"Running command: {{command}}")
    # TODO: Add command dispatch


if __name__ == "__main__":
    main()
"""

GUIDE_MD_TEMPLATE = """\
# {title} Domain Reference

## Overview

TODO: Provide a comprehensive reference for the {title} domain.
This guide is loaded by the skill to provide domain context
without consuming conversation turns.

## Key Concepts

### Concept 1
TODO: Define the first key concept.

### Concept 2
TODO: Define the second key concept.

### Concept 3
TODO: Define the third key concept.

## Patterns

### Pattern 1: TODO
- When to use: TODO
- How it works: TODO
- Example: TODO

### Pattern 2: TODO
- When to use: TODO
- How it works: TODO
- Example: TODO

## Common Pitfalls

1. **TODO: Pitfall 1** — Description and how to avoid it.
2. **TODO: Pitfall 2** — Description and how to avoid it.
3. **TODO: Pitfall 3** — Description and how to avoid it.

## Quality Checklist

- [ ] TODO: Check 1
- [ ] TODO: Check 2
- [ ] TODO: Check 3
- [ ] TODO: Check 4
- [ ] TODO: Check 5

## Best Practices

- TODO: Best practice 1
- TODO: Best practice 2
- TODO: Best practice 3

## References

- TODO: Link to relevant documentation
- TODO: Link to relevant standards
- TODO: Link to relevant examples
"""


def scaffold(name: str, output_dir: Path) -> list[Path]:
    """Create the skill directory structure and return list of created files."""
    skill_dir = output_dir / name
    scripts_dir = skill_dir / "scripts"
    refs_dir = skill_dir / "references"

    title_words = name.replace("-", " ")
    title = title_words.title()

    skill_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)
    refs_dir.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []

    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(SKILL_MD_TEMPLATE.format(name=name, title_words=title_words),
                        encoding="utf-8")
    created.append(skill_md)

    validate_sh = scripts_dir / "validate.sh"
    validate_sh.write_text(VALIDATE_SH_TEMPLATE.format(name=name), encoding="utf-8")
    validate_sh.chmod(0o755)
    created.append(validate_sh)

    main_helper = scripts_dir / "main_helper.py"
    main_helper.write_text(MAIN_HELPER_TEMPLATE.format(name=name), encoding="utf-8")
    main_helper.chmod(0o755)
    created.append(main_helper)

    guide_md = refs_dir / "guide.md"
    guide_md.write_text(GUIDE_MD_TEMPLATE.format(title=title), encoding="utf-8")
    created.append(guide_md)

    return created


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a starter skill directory structure."
    )
    parser.add_argument("name", help="Skill name (kebab-case, e.g. 'my-skill')")
    parser.add_argument("--output-dir", type=Path, default=Path("."),
                        help="Parent directory for the new skill (default: current directory)")
    args = parser.parse_args()

    if not NAME_RE.match(args.name):
        print(f"Error: '{args.name}' does not match required pattern: {NAME_RE.pattern}",
              file=sys.stderr)
        sys.exit(1)

    output_dir = args.output_dir.resolve()
    if not output_dir.is_dir():
        print(f"Error: output directory does not exist: {output_dir}", file=sys.stderr)
        sys.exit(1)

    created = scaffold(args.name, output_dir)

    print(f"Scaffolded skill '{args.name}' in {output_dir / args.name}:")
    for f in created:
        print(f"  {f.relative_to(output_dir)}")


if __name__ == "__main__":
    main()
