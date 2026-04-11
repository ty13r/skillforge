"""Pydantic v2 request/response schemas for the REST API boundary.

Internal models use dataclasses (``skillforge.models``); these Pydantic models
exist only to validate API I/O. Implemented fully in Step 8.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from skillforge.config import DEFAULT_BUDGET_USD, DEFAULT_GENS, DEFAULT_POP


class Mode(StrEnum):
    domain = "domain"
    meta = "meta"


class ExportFormat(StrEnum):
    skill_dir = "skill_dir"
    skill_md = "skill_md"
    agent_sdk_config = "agent_sdk_config"


class EvolveRequest(BaseModel):
    mode: Mode = Mode.domain
    specialization: str | None = None
    test_domains: list[str] | None = None  # meta mode only
    population_size: int = Field(default=DEFAULT_POP, ge=2, le=20)
    num_generations: int = Field(default=DEFAULT_GENS, ge=1, le=10)
    max_budget_usd: float = Field(default=DEFAULT_BUDGET_USD, gt=0)
    invite_code: str | None = None
    # v2.0 — explicit evolution mode override. ``None`` (default) → auto-detect
    # via the Taxonomist. Caller can force a specific mode by passing
    # ``"atomic"`` or ``"molecular"``.
    evolution_mode: str | None = None


class EvolveResponse(BaseModel):
    run_id: str
    ws_url: str


class RunSummary(BaseModel):
    id: str
    mode: str
    specialization: str
    status: str
    best_fitness: float | None = None
    total_cost_usd: float = 0.0


class RunDetail(BaseModel):
    id: str
    mode: str
    specialization: str
    status: str
    population_size: int
    num_generations: int
    total_cost_usd: float
    best_fitness: float | None = None
    best_skill_id: str | None = None
    # v2.0 — present so the frontend Advanced toggle can render the
    # VariantBreakdown for atomic runs.
    family_id: str | None = None
    evolution_mode: str = "molecular"
    # v2.0 Step 1b — exposes the audit trail + reconstructed integration report
    # so the atomic run-detail page can render a narrative timeline.
    learning_log: list[str] = Field(default_factory=list)


class LineageNode(BaseModel):
    id: str
    generation: int
    fitness: float
    maturity: str
    traits: list[str]


class LineageEdge(BaseModel):
    parent_id: str
    child_id: str
    mutation_type: str  # elitism | crossover | mutation | wildcard


# ---------------------------------------------------------------------------
# v2.0 taxonomy + families + variants
# ---------------------------------------------------------------------------


class TaxonomyNodeResponse(BaseModel):
    id: str
    level: str  # domain | focus | language
    slug: str
    label: str
    parent_id: str | None = None
    description: str = ""
    created_at: str | None = None


class SkillFamilyResponse(BaseModel):
    id: str
    slug: str
    label: str
    specialization: str
    domain_id: str | None = None
    focus_id: str | None = None
    language_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    decomposition_strategy: str = "molecular"
    best_assembly_id: str | None = None
    created_at: str | None = None


class VariantResponse(BaseModel):
    id: str
    family_id: str
    dimension: str
    tier: str  # foundation | capability
    genome_id: str
    fitness_score: float = 0.0
    is_active: bool = False
    evolution_id: str | None = None
    created_at: str | None = None
