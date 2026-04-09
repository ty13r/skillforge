"""Sandbox creation and Skill structure validation tests (Step 5)."""

from __future__ import annotations

from pathlib import Path

import pytest

import skillforge.engine.sandbox as sandbox_mod
from skillforge.engine.sandbox import (
    cleanup_sandbox,
    collect_written_files,
    create_sandbox,
    validate_skill_structure,
)
from skillforge.models import Challenge, SkillGenome

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_SKILL_MD = """\
---
name: my-skill
description: >-
  Does useful things. Use when you need useful things done, or when the user
  mentions "useful", even if they don't explicitly ask for my-skill.
  NOT for unrelated things.
allowed-tools: Read Write Bash
---

# My Skill

## Quick Start
Run the skill to get useful output.

## Workflow

### Step 1: Gather
Read context.

### Step 2: Execute
Do the thing.

## Examples

**Example 1: Typical use case**
Input: "Do useful thing"
Output: Useful result

**Example 2: Edge case**
Input: "Do useful thing differently"
Output: Another useful result

## Gotchas
- Watch out for edge cases.

## Out of Scope
This skill does NOT:
- Handle unrelated things.
"""

_MINIMAL_CHALLENGE = Challenge(
    id="ch-001",
    prompt="Write a hello world function.",
    difficulty="easy",
    setup_files={"starter.py": "# starter"},
)


def _minimal_skill(**kwargs: object) -> SkillGenome:
    defaults: dict = {
        "id": "sk-001",
        "generation": 0,
        "skill_md_content": _MINIMAL_SKILL_MD,
    }
    defaults.update(kwargs)
    return SkillGenome(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def patched_sandbox_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Monkeypatch SANDBOX_ROOT so tests never touch /tmp."""
    root = tmp_path / "sandbox"
    root.mkdir()
    monkeypatch.setattr(sandbox_mod, "SANDBOX_ROOT", root)
    return root


# ---------------------------------------------------------------------------
# create_sandbox
# ---------------------------------------------------------------------------

def test_create_sandbox_makes_correct_tree(
    patched_sandbox_root: Path,
) -> None:
    skill = _minimal_skill()
    challenge = _MINIMAL_CHALLENGE
    result = create_sandbox("run1", 0, 0, skill, challenge)

    assert result.exists()
    assert result.is_dir()

    skill_md = result / ".claude" / "skills" / "evolved-skill" / "SKILL.md"
    assert skill_md.exists()
    assert skill_md.read_text() == _MINIMAL_SKILL_MD

    challenge_file = result / "challenge" / "starter.py"
    assert challenge_file.exists()
    assert challenge_file.read_text() == "# starter"

    output_dir = result / "output"
    assert output_dir.exists()
    assert output_dir.is_dir()
    assert list(output_dir.iterdir()) == []


def test_create_sandbox_writes_supporting_files(
    patched_sandbox_root: Path,
) -> None:
    supporting = {
        "scripts/validate.sh": "#!/bin/bash\necho ok",
        "references/patterns.md": "# Patterns",
    }
    skill = _minimal_skill(supporting_files=supporting)
    result = create_sandbox("run1", 0, 0, skill, _MINIMAL_CHALLENGE)

    skill_dir = result / ".claude" / "skills" / "evolved-skill"
    assert (skill_dir / "scripts" / "validate.sh").read_text() == "#!/bin/bash\necho ok"
    assert (skill_dir / "references" / "patterns.md").read_text() == "# Patterns"


def test_create_sandbox_unique_per_competitor(
    patched_sandbox_root: Path,
) -> None:
    skill = _minimal_skill()
    path0 = create_sandbox("run1", 0, 0, skill, _MINIMAL_CHALLENGE)
    path1 = create_sandbox("run1", 0, 1, skill, _MINIMAL_CHALLENGE)
    assert path0 != path1
    assert path0.exists()
    assert path1.exists()


# ---------------------------------------------------------------------------
# cleanup_sandbox
# ---------------------------------------------------------------------------

def test_cleanup_sandbox_removes_dir(
    patched_sandbox_root: Path,
) -> None:
    skill = _minimal_skill()
    path = create_sandbox("run2", 0, 0, skill, _MINIMAL_CHALLENGE)
    assert path.exists()
    cleanup_sandbox(path)
    assert not path.exists()


def test_cleanup_sandbox_refuses_outside_sandbox_root(
    patched_sandbox_root: Path,
) -> None:
    with pytest.raises(ValueError, match="SANDBOX_ROOT"):
        cleanup_sandbox(Path("/"))
    with pytest.raises(ValueError, match="SANDBOX_ROOT"):
        cleanup_sandbox(Path("/etc"))


def test_cleanup_sandbox_refuses_non_skillforge_dir(
    patched_sandbox_root: Path,
) -> None:
    non_sf = patched_sandbox_root / "not-skillforge"
    non_sf.mkdir()
    with pytest.raises(ValueError, match="non-SkillForge"):
        cleanup_sandbox(non_sf)


# ---------------------------------------------------------------------------
# collect_written_files
# ---------------------------------------------------------------------------

def test_collect_written_files_reads_nested(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "a.py").write_text("print('hello')")
    sub = output / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("world")

    result = collect_written_files(output)
    assert result == {
        "a.py": "print('hello')",
        "sub/b.txt": "world",
    }


def test_collect_written_files_empty_dir(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    result = collect_written_files(output)
    assert result == {}


def test_collect_written_files_missing_dir(tmp_path: Path) -> None:
    result = collect_written_files(tmp_path / "nonexistent")
    assert result == {}


# ---------------------------------------------------------------------------
# validate_skill_structure — valid cases
# ---------------------------------------------------------------------------

def test_validate_minimal_valid_skill_passes() -> None:
    skill = _minimal_skill()
    assert validate_skill_structure(skill) == []


def test_validate_golden_template_passes() -> None:
    """Read golden template, substitute placeholders, validate."""
    from skillforge.config import GOLDEN_TEMPLATE_DIR

    template_path = GOLDEN_TEMPLATE_DIR / "SKILL.md"
    raw = template_path.read_text()

    # Replace all placeholder variables with valid values
    filled = (
        raw.replace("{skill-name}", "my-skill")
        .replace("{Skill Display Name}", "My Skill")
        .replace(
            "{Capability statement — 1 sentence, WHAT it does}. Use when {trigger 1},\n"
            "  {trigger 2}, {trigger 3}, or when user mentions \"{keyword1}\", \"{keyword2}\",\n"
            "  \"{keyword3}\", even if they don't explicitly ask for {exact skill name}.\n"
            "  NOT for {exclusion 1}, {exclusion 2}, or {exclusion 3}.",
            "Helps you build stuff. Use when building things, writing code, or when user "
            'mentions "build", "create", "implement", even if they don\'t explicitly ask for my-skill. '
            "NOT for deletion, cleanup, or security audits.",
        )
        .replace("{scenario A}", "scenario A")
        .replace("{scenario B}", "scenario B")
        .replace("{2-3 sentences: the core workflow in the simplest possible terms.}", "Run, check, done.")
        .replace("{Concrete instruction with specific action — imperative voice.}", "Gather context first.")
        .replace("{Concrete instruction — what to do, not what to think about.}", "Execute the plan.")
        .replace("{Concrete instruction — verify the output meets quality bar.}", "Check the output.")
        .replace("{Typical use case}", "Typical use case")
        .replace("{Edge case}", "Edge case")
        .replace("{Near-miss — should trigger but might not}", "Near-miss")
        .replace('"{realistic user prompt, conversational tone}"', '"Build me a thing"')
        .replace("{expected result with specific format}", "A built thing")
        .replace('"{edge case prompt that should still trigger}"', '"Edge case prompt"')
        .replace("{expected result}", "Correct handling")
        .replace('"{prompt using synonym/adjacent concept}"', '"Make a widget"')
        .replace("{correct handling}", "Correct")
        .replace("{Known failure point #1 — what goes wrong and how to handle it}", "Edge case failure — catch it.")
        .replace("{Known failure point #2 — specific, actionable}", "Another failure — handle it.")
        .replace("{Common user mistake and correct response}", "Misuse — redirect politely.")
        .replace("{Explicit exclusion} (use {other-skill} instead)", "Deletion (use delete-skill instead)")
        .replace("{Explicit exclusion}", "Out of scope item")
    )

    supporting = {
        "references/detailed-guide.md": "# Detailed Guide\nContent here.",
        "references/examples.md": "# Examples\nContent here.",
        "scripts/main_helper.py": "# helper",
        "scripts/validate.sh": "#!/bin/bash\necho ok",
    }

    skill = SkillGenome(
        id="golden-test",
        generation=0,
        skill_md_content=filled,
        supporting_files=supporting,
    )

    violations = validate_skill_structure(skill)
    assert violations == [], f"Golden template violations: {violations}"


# ---------------------------------------------------------------------------
# validate_skill_structure — violation cases
# ---------------------------------------------------------------------------

def test_validate_catches_missing_frontmatter() -> None:
    skill = _minimal_skill(skill_md_content="# No frontmatter here\n\nJust body text.")
    violations = validate_skill_structure(skill)
    assert any("missing YAML frontmatter" in v for v in violations)


def test_validate_catches_bad_name() -> None:
    bad_md = _MINIMAL_SKILL_MD.replace("name: my-skill", "name: Bad_Name")
    skill = _minimal_skill(skill_md_content=bad_md)
    violations = validate_skill_structure(skill)
    assert any("does not match regex" in v for v in violations)


def test_validate_catches_reserved_word() -> None:
    bad_md = _MINIMAL_SKILL_MD.replace("name: my-skill", "name: claude-helper")
    skill = _minimal_skill(skill_md_content=bad_md)
    violations = validate_skill_structure(skill)
    assert any("reserved word" in v for v in violations)


def test_validate_catches_long_description() -> None:
    long_desc = "Use when needed. " + "x" * 1100
    bad_md = _MINIMAL_SKILL_MD.replace(
        "description: >-\n"
        "  Does useful things. Use when you need useful things done, or when the user\n"
        '  mentions "useful", even if they don\'t explicitly ask for my-skill.\n'
        "  NOT for unrelated things.",
        f"description: '{long_desc}'",
    )
    skill = _minimal_skill(skill_md_content=bad_md)
    violations = validate_skill_structure(skill)
    assert any("max 1024" in v for v in violations)


def test_validate_catches_missing_use_when() -> None:
    bad_md = _MINIMAL_SKILL_MD.replace(
        "description: >-\n"
        "  Does useful things. Use when you need useful things done, or when the user\n"
        '  mentions "useful", even if they don\'t explicitly ask for my-skill.\n'
        "  NOT for unrelated things.",
        "description: 'Does useful things. No trigger info here. NOT for anything.'",
    )
    skill = _minimal_skill(skill_md_content=bad_md)
    violations = validate_skill_structure(skill)
    assert any("Use when" in v for v in violations)


def test_validate_catches_long_body() -> None:
    # Build a body with 600 lines
    long_body = "\n".join([f"line {i}" for i in range(600)])
    # Rebuild SKILL.md with a body over 500 lines but keep 2 examples
    skill_md = (
        "---\n"
        "name: my-skill\n"
        "description: 'Use when needed. NOT for excluded things.'\n"
        "---\n\n"
        "**Example 1:** Input A → Output A\n\n"
        "**Example 2:** Input B → Output B\n\n"
        + long_body
    )
    skill = _minimal_skill(skill_md_content=skill_md)
    violations = validate_skill_structure(skill)
    assert any("max 500" in v for v in violations)


def test_validate_catches_too_few_examples() -> None:
    # Only 1 example in body
    skill_md = (
        "---\n"
        "name: my-skill\n"
        "description: 'Use when needed. NOT for excluded things.'\n"
        "---\n\n"
        "## Quick Start\n"
        "Do stuff.\n\n"
        "**Example 1:** Input → Output\n\n"
        "## Out of Scope\n"
        "Not for this.\n"
    )
    skill = _minimal_skill(skill_md_content=skill_md)
    violations = validate_skill_structure(skill)
    assert any("examples" in v.lower() for v in violations)


def test_validate_catches_broken_reference() -> None:
    skill_md = (
        "---\n"
        "name: my-skill\n"
        "description: 'Use when needed. NOT for excluded things.'\n"
        "---\n\n"
        "Read `${CLAUDE_SKILL_DIR}/references/missing.md` for details.\n\n"
        "**Example 1:** Input → Output\n\n"
        "**Example 2:** Another → Result\n"
    )
    skill = _minimal_skill(skill_md_content=skill_md, supporting_files={})
    violations = validate_skill_structure(skill)
    assert any("not in supporting_files" in v for v in violations)


def test_validate_accepts_valid_reference() -> None:
    skill_md = (
        "---\n"
        "name: my-skill\n"
        "description: 'Use when needed. NOT for excluded things.'\n"
        "---\n\n"
        "Read `${CLAUDE_SKILL_DIR}/references/guide.md` for details.\n\n"
        "**Example 1:** Input → Output\n\n"
        "**Example 2:** Another → Result\n"
    )
    skill = _minimal_skill(
        skill_md_content=skill_md,
        supporting_files={"references/guide.md": "# Guide\nContent."},
    )
    violations = validate_skill_structure(skill)
    assert not any("not in supporting_files" in v for v in violations)
