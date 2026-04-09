"""SkillGenome — the full "DNA" of an evolved Skill.

Contains the SKILL.md contents, frontmatter, supporting files, extracted traits,
lineage info, and layered fitness scores from the 6-layer judging pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SkillGenome:
    """Complete genome for a single candidate Skill.

    Fitness fields are organized by judging layer (L1-L6) per SPEC.md §Data Model.
    Mutable defaults use ``field(default_factory=...)``; serialization helpers
    are stubs until Step 4.
    """

    id: str
    generation: int
    skill_md_content: str
    frontmatter: dict = field(default_factory=dict)
    supporting_files: dict[str, str] = field(default_factory=dict)
    traits: list[str] = field(default_factory=list)
    meta_strategy: str = ""
    parent_ids: list[str] = field(default_factory=list)
    mutations: list[str] = field(default_factory=list)
    mutation_rationale: str = ""

    # Maturity lifecycle (inspired by singularity-claude)
    maturity: str = "draft"  # draft | tested | hardened | crystallized
    generations_survived: int = 0

    # L1: Deterministic checks
    deterministic_scores: dict[str, float] = field(default_factory=dict)

    # L2: Trigger accuracy
    trigger_precision: float = 0.0
    trigger_recall: float = 0.0

    # L3: Trace-based behavioral analysis
    behavioral_signature: list[str] = field(default_factory=list)

    # L4: Comparative + Pareto
    pareto_objectives: dict[str, float] = field(default_factory=dict)
    is_pareto_optimal: bool = False

    # L5: Trait attribution
    trait_attribution: dict[str, float] = field(default_factory=dict)
    trait_diagnostics: dict[str, str] = field(default_factory=dict)

    # L6: Consistency (v1.1)
    consistency_score: float | None = None

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict. Implemented in Step 4."""
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict) -> SkillGenome:
        """Rehydrate from a dict. Implemented in Step 4."""
        raise NotImplementedError
