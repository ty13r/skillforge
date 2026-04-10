"""Internal dataclasses for SkillForge.

Internal models use ``@dataclass``; API request/response schemas live in
``skillforge.api.schemas`` as Pydantic models.
"""

from skillforge.models.challenge import Challenge
from skillforge.models.competition import CompetitionResult
from skillforge.models.family import SkillFamily
from skillforge.models.generation import Generation
from skillforge.models.genome import SkillGenome
from skillforge.models.run import EvolutionRun
from skillforge.models.taxonomy import TaxonomyNode
from skillforge.models.variant import Variant, VariantEvolution

__all__ = [
    "Challenge",
    "CompetitionResult",
    "Generation",
    "SkillGenome",
    "EvolutionRun",
    "TaxonomyNode",
    "SkillFamily",
    "Variant",
    "VariantEvolution",
]
