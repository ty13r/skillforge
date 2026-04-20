"""Spawner — creates gen 0 populations and breeds next generations.

Gen 0: reads the golden template from ``config.GOLDEN_TEMPLATE_DIR`` and
``bible/patterns/*.md``, generates ``pop_size`` diverse Skills varying
content while preserving structure.

Gen 1+: takes parent genomes + breeding instructions from the Breeder
and produces child Skills. The Spawner MUST enforce all authoring
constraints from ``engine.sandbox.validate_skill_structure``.

Uses the Anthropic Messages API directly (NOT the Agent SDK's query())
because this is a pure generation task with no tool use. The Agent SDK's
query() is for agentic loops with tools and hung the overnight live test.

Submodule layout:

  _helpers.py    _generate (LLM call) + _parse_genomes + validation +
                 auto-repair + bible-pattern reader
  _prompts.py    all _build_*_prompt functions (pure string templating)
  main.py        four public entry points — spawn_gen0, breed_next_gen,
                 spawn_from_parent, spawn_variant_gen0
"""

from __future__ import annotations

# Helpers re-exported for tests that patch them on the package root.
from skillforge.agents.spawner._helpers import (
    _auto_repair_missing_references,
    _generate,
    _parse_genomes,
    _read_bible_patterns,
    _validate_genomes,
)
from skillforge.agents.spawner.main import (
    breed_next_gen,
    spawn_from_parent,
    spawn_gen0,
    spawn_variant_gen0,
)
from skillforge.config import BIBLE_DIR

__all__ = [
    "spawn_gen0",
    "breed_next_gen",
    "spawn_from_parent",
    "spawn_variant_gen0",
    # Private helpers re-exported for test access.
    "_auto_repair_missing_references",
    "_generate",
    "_parse_genomes",
    "_read_bible_patterns",
    "_validate_genomes",
    "BIBLE_DIR",
]
