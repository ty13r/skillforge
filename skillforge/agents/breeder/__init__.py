"""Breeder — reflective mutation, multi-parent crossover, learning log, bible publishing.

Inspired by GEPA's Actionable Side Information: mutations are diagnostic,
not random. The Breeder reads execution traces and trait attribution
from the judging pipeline, identifies root causes of failures, and
proposes targeted fixes.

Responsibilities:
- Elitism: top N Skills survive unchanged
- Reflective crossover: combine traits from 2-3 parents guided by attribution
- Diagnostic mutation: fix specific causes surfaced by trait attribution
- Joint component mutation: frontmatter + body + scripts mutate together
- Wildcard: 1+ slots per generation for fresh Skills
- Learning log maintenance: append new lessons each generation
- Bible publishing: extract generalizable findings to ``bible/findings/``

Slot allocation scales with ``target_pop_size`` (never hardcoded; see
``_ranking.compute_slots`` for the formula).

Submodule layout:

  _ranking.py   compute_slots + rank_skills + _aggregate_fitness (pure)
  _prompts.py   _build_diagnostic_instructions + _build_crossover_instructions
                + _build_breeding_context (pure string-templating)
  _reports.py   _extract_lessons_and_report + _extract_lessons
                + _extract_breeding_report + _extract_consolidated
                (LLM-calling; degrades gracefully on SDK errors)
  main.py       breed() + _carry_elite (top-level orchestrator)
  bible.py      publish_findings_to_bible (disk I/O, fire-and-forget)
"""

from __future__ import annotations

# Re-expose imports the old breeder.py module aliased so test patches
# targeting ``skillforge.agents.breeder.breed_next_gen`` and
# ``skillforge.agents.breeder.BIBLE_DIR`` continue to resolve.
from skillforge.agents.breeder._ranking import (
    _aggregate_fitness,
    compute_slots,
    rank_skills,
)
from skillforge.agents.breeder._reports import (
    _extract_breeding_report,
    _extract_consolidated,
    _extract_lessons,
    _extract_lessons_and_report,
)
from skillforge.agents.breeder.bible import publish_findings_to_bible
from skillforge.agents.breeder.main import _carry_elite, breed
from skillforge.agents.spawner import breed_next_gen, spawn_gen0
from skillforge.config import BIBLE_DIR

__all__ = [
    "breed",
    "compute_slots",
    "rank_skills",
    "publish_findings_to_bible",
    # Re-exports for test-patch stability.
    "breed_next_gen",
    "spawn_gen0",
    "BIBLE_DIR",
    # Private helpers re-exported for test access.
    "_aggregate_fitness",
    "_carry_elite",
    "_extract_lessons_and_report",
    "_extract_lessons",
    "_extract_breeding_report",
    "_extract_consolidated",
]
