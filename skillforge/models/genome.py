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
        """Serialize to a JSON-safe dict."""
        return {
            "id": self.id,
            "generation": self.generation,
            "skill_md_content": self.skill_md_content,
            "frontmatter": self.frontmatter,
            "supporting_files": self.supporting_files,
            "traits": self.traits,
            "meta_strategy": self.meta_strategy,
            "parent_ids": self.parent_ids,
            "mutations": self.mutations,
            "mutation_rationale": self.mutation_rationale,
            "maturity": self.maturity,
            "generations_survived": self.generations_survived,
            "deterministic_scores": self.deterministic_scores,
            "trigger_precision": self.trigger_precision,
            "trigger_recall": self.trigger_recall,
            "behavioral_signature": self.behavioral_signature,
            "pareto_objectives": self.pareto_objectives,
            "is_pareto_optimal": self.is_pareto_optimal,
            "trait_attribution": self.trait_attribution,
            "trait_diagnostics": self.trait_diagnostics,
            "consistency_score": self.consistency_score,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SkillGenome:
        """Rehydrate from a dict."""
        return cls(
            id=data["id"],
            generation=data["generation"],
            skill_md_content=data["skill_md_content"],
            frontmatter=data.get("frontmatter", {}),
            supporting_files=data.get("supporting_files", {}),
            traits=data.get("traits", []),
            meta_strategy=data.get("meta_strategy", ""),
            parent_ids=data.get("parent_ids", []),
            mutations=data.get("mutations", []),
            mutation_rationale=data.get("mutation_rationale", ""),
            maturity=data.get("maturity", "draft"),
            generations_survived=data.get("generations_survived", 0),
            deterministic_scores=data.get("deterministic_scores", {}),
            trigger_precision=data.get("trigger_precision", 0.0),
            trigger_recall=data.get("trigger_recall", 0.0),
            behavioral_signature=data.get("behavioral_signature", []),
            pareto_objectives=data.get("pareto_objectives", {}),
            is_pareto_optimal=data.get("is_pareto_optimal", False),
            trait_attribution=data.get("trait_attribution", {}),
            trait_diagnostics=data.get("trait_diagnostics", {}),
            consistency_score=data.get("consistency_score"),
        )
