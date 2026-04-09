"""Tests for internal dataclasses (Step 3)."""

from __future__ import annotations

from skillforge.models import (
    Challenge,
    CompetitionResult,
    EvolutionRun,
    Generation,
    SkillGenome,
)


def test_imports():
    """All model classes import cleanly."""
    assert SkillGenome and Challenge and Generation and EvolutionRun and CompetitionResult


def test_skill_genome_instantiates_with_minimal_args():
    g = SkillGenome(id="g1", generation=0, skill_md_content="")
    assert g.id == "g1"
    assert g.maturity == "draft"
    assert g.traits == []
    assert g.trigger_precision == 0.0
    assert g.consistency_score is None
