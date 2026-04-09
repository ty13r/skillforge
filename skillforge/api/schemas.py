"""Pydantic v2 request/response schemas for the REST API boundary.

Internal models use dataclasses (``skillforge.models``); these Pydantic models
exist only to validate API I/O. Implemented fully in Step 8.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from skillforge.config import DEFAULT_BUDGET_USD, DEFAULT_GENS, DEFAULT_POP


class Mode(str, Enum):
    domain = "domain"
    meta = "meta"


class ExportFormat(str, Enum):
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
    best_skill_id: str | None = None


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
