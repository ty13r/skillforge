"""Isolated per-competitor sandbox directories.

Each competitor runs in ``{SANDBOX_ROOT}/skillforge-{run_id}-gen{N}-competitor{M}/``
with structure::

    .claude/skills/evolved-skill/
        SKILL.md
        scripts/
        references/
    challenge/
        starter_code.py
        test_suite.py
    output/

``validate_skill_structure`` enforces all Skill Authoring Constraints from
SPEC.md and docs/skills-research.md before any Skill enters competition.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import yaml

from skillforge.config import SANDBOX_ROOT
from skillforge.models import Challenge, SkillGenome

SKILL_NAME_REGEX = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def create_sandbox(
    run_id: str,
    generation: int,
    competitor_idx: int,
    skill: SkillGenome,
    challenge: Challenge,
) -> Path:
    """Create a temp project directory with the Skill and challenge files.

    Directory layout::

        {SANDBOX_ROOT}/skillforge-{run_id}-gen{generation}-competitor{competitor_idx}/
        ├── .claude/
        │   └── skills/
        │       └── evolved-skill/
        │           ├── SKILL.md
        │           └── {supporting_files...}
        ├── challenge/
        │   └── {setup_files...}
        └── output/

    Returns the root path (used as cwd for Agent SDK query).
    """
    sandbox_dir = (
        SANDBOX_ROOT
        / f"skillforge-{run_id}-gen{generation}-competitor{competitor_idx}"
    )
    skill_dir = sandbox_dir / ".claude" / "skills" / "evolved-skill"

    # Create required directories
    skill_dir.mkdir(parents=True, exist_ok=True)
    (sandbox_dir / "challenge").mkdir(parents=True, exist_ok=True)
    (sandbox_dir / "output").mkdir(parents=True, exist_ok=True)

    # Write SKILL.md
    (skill_dir / "SKILL.md").write_text(skill.skill_md_content)

    # Write supporting files (relative paths like "scripts/validate.sh")
    for rel_path, content in skill.supporting_files.items():
        target = skill_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    # Write challenge setup files
    for rel_path, content in challenge.setup_files.items():
        target = sandbox_dir / "challenge" / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    return sandbox_dir


def cleanup_sandbox(path: Path) -> None:
    """Remove a sandbox directory after evaluation completes.

    Safety: refuses to delete anything not rooted under SANDBOX_ROOT and not
    named with the ``skillforge-`` prefix. Raises ``ValueError`` on violation.
    """
    path = Path(path).resolve()
    sandbox_root_resolved = SANDBOX_ROOT.resolve()

    try:
        path.relative_to(sandbox_root_resolved)
    except ValueError as exc:
        raise ValueError(
            f"Refusing to clean up path outside SANDBOX_ROOT: {path}"
        ) from exc

    if not path.name.startswith("skillforge-"):
        raise ValueError(f"Refusing to clean up non-SkillForge path: {path}")

    if path.exists():
        shutil.rmtree(path)


def collect_written_files(output_dir: Path) -> dict[str, str]:
    """Recursively read all text files under ``output_dir`` into a dict.

    Keys are POSIX-style relative paths from ``output_dir``.
    Binary files are skipped silently (caught via ``UnicodeDecodeError``).
    """
    output_dir = Path(output_dir)
    result: dict[str, str] = {}
    if not output_dir.exists():
        return result
    for p in output_dir.rglob("*"):
        if p.is_file():
            try:
                rel = p.relative_to(output_dir).as_posix()
                result[rel] = p.read_text()
            except (UnicodeDecodeError, PermissionError):
                continue
    return result


def validate_skill_structure(skill: SkillGenome) -> list[str]:
    """Return a list of authoring-constraint violations. Empty list = valid.

    Enforces (all non-negotiable per SPEC.md §Skill Authoring Constraints):

    1. SKILL.md has parseable YAML frontmatter (between --- markers).
    2. Frontmatter has a 'name' field matching ``^[a-z0-9]+(-[a-z0-9]+)*$``.
    3. Frontmatter 'name' does not contain 'anthropic' or 'claude' (reserved).
    4. Frontmatter has a 'description' ≤ 1024 chars.
    5. Description first 250 chars contain 'Use when' (pushy pattern signal).
    6. SKILL.md body (content after the second ---) is ≤ 500 lines.
    7. Body contains at least 2 example markers (**Example or ## Example).
    8. Every ``${CLAUDE_SKILL_DIR}/...`` reference path exists in
       ``skill.supporting_files`` (catches the 73%-broken-references issue).
    """
    violations: list[str] = []
    content = skill.skill_md_content

    # ── Rule 1: parseable YAML frontmatter ────────────────────────────────────
    if not content.startswith("---"):
        violations.append("SKILL.md missing YAML frontmatter (no leading ---)")
        return violations  # bail — everything else depends on frontmatter

    try:
        _, fm_block, body = content.split("---", 2)
    except ValueError:
        violations.append("SKILL.md frontmatter malformed (no closing ---)")
        return violations

    try:
        fm = yaml.safe_load(fm_block) or {}
    except yaml.YAMLError as exc:
        violations.append(f"SKILL.md frontmatter is invalid YAML: {exc}")
        return violations

    # ── Rule 2: name regex ────────────────────────────────────────────────────
    name = fm.get("name", "")
    if not isinstance(name, str) or not SKILL_NAME_REGEX.match(name):
        violations.append(
            f"name '{name}' does not match regex ^[a-z0-9]+(-[a-z0-9]+)*$"
        )

    # ── Rule 3: reserved words ────────────────────────────────────────────────
    if isinstance(name, str) and (
        "anthropic" in name.lower() or "claude" in name.lower()
    ):
        violations.append(
            f"name '{name}' contains reserved word (anthropic/claude)"
        )

    # ── Rule 4: description length ────────────────────────────────────────────
    desc = fm.get("description", "")
    if not isinstance(desc, str):
        violations.append("description must be a string")
        desc = ""
    elif len(desc) > 1024:
        violations.append(f"description is {len(desc)} chars (max 1024)")

    # ── Rule 5: pushy pattern ─────────────────────────────────────────────────
    if desc and "use when" not in desc[:250].lower():
        violations.append(
            "description first 250 chars must contain 'Use when' (pushy pattern)"
        )

    # ── Rule 6: body line count ───────────────────────────────────────────────
    body_lines = body.strip().splitlines()
    if len(body_lines) > 500:
        violations.append(f"SKILL.md body is {len(body_lines)} lines (max 500)")

    # ── Rule 7: at least 2 examples ──────────────────────────────────────────
    example_count = body.count("**Example") + body.count("## Example")
    if example_count < 2:
        violations.append(
            f"SKILL.md body must contain at least 2 examples (found {example_count})"
        )

    # ── Rule 8: reference paths exist in supporting_files ────────────────────
    ref_pattern = re.compile(r"\$\{CLAUDE_SKILL_DIR\}/([^\s`)\"']+)")
    for match in ref_pattern.finditer(body):
        rel_path = match.group(1).rstrip(".,;:)")
        if rel_path not in skill.supporting_files:
            violations.append(
                f"reference path not in supporting_files: {rel_path}"
            )

    return violations
