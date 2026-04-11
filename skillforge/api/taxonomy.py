"""Taxonomy + families + variants REST router (v2.0).

Read endpoints (Wave 1-4):
- ``GET /api/taxonomy``               — flat list of every taxonomy node
- ``GET /api/taxonomy/{node_id}``     — single node with its direct children
- ``GET /api/families``               — list of families, filterable
- ``GET /api/families/{family_id}``   — single family with summary
- ``GET /api/families/{family_id}/variants`` — variants belonging to the family
- ``GET /api/families/{family_id}/assembly`` — best assembled composite (Wave 4-3)

Write endpoints (Wave 5-2):
- ``POST /api/families/{family_id}/swap-variant``    — swap the active variant
- ``POST /api/families/{family_id}/evolve-variant``  — re-evolve a single dimension

The Taxonomist agent + bootstrap loader handle the rest of the writes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from skillforge.api.schemas import (
    SkillFamilyResponse,
    TaxonomyNodeResponse,
    VariantResponse,
)
from skillforge.db import (
    get_family,
    get_taxonomy_node,
    get_taxonomy_tree,
    get_variants_for_family,
    list_families,
    save_variant,
    save_variant_evolution,
)
from skillforge.models import SkillFamily, TaxonomyNode, Variant, VariantEvolution

router = APIRouter(tags=["taxonomy"])


def _node_to_response(node: TaxonomyNode) -> TaxonomyNodeResponse:
    data = node.to_dict()
    return TaxonomyNodeResponse(**data)


def _family_to_response(family: SkillFamily) -> SkillFamilyResponse:
    data = family.to_dict()
    return SkillFamilyResponse(**data)


def _variant_to_response(variant: Variant) -> VariantResponse:
    data = variant.to_dict()
    return VariantResponse(**data)


@router.get("/api/taxonomy", response_model=list[TaxonomyNodeResponse])
async def list_taxonomy() -> list[TaxonomyNodeResponse]:
    """Return every taxonomy node ordered domain → focus → language."""
    nodes = await get_taxonomy_tree()
    return [_node_to_response(n) for n in nodes]


@router.get("/api/taxonomy/{node_id}")
async def get_taxonomy_node_detail(node_id: str) -> dict:
    """Return a single node with its direct children.

    The response shape is ``{"node": {...}, "children": [...]}``. Children
    are computed from the full tree (the taxonomy is small by design, so
    streaming all nodes and filtering is cheaper than a second query).
    """
    node = await get_taxonomy_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"taxonomy node not found: {node_id}")

    tree = await get_taxonomy_tree()
    children = [n for n in tree if n.parent_id == node_id]
    return {
        "node": _node_to_response(node).model_dump(),
        "children": [_node_to_response(c).model_dump() for c in children],
    }


@router.get("/api/families", response_model=list[SkillFamilyResponse])
async def list_skill_families(
    domain: str | None = Query(default=None, description="Filter by domain_id"),
    focus: str | None = Query(default=None, description="Filter by focus_id"),
    language: str | None = Query(default=None, description="Filter by language_id"),
    tag: str | None = Query(default=None, description="Filter by tag membership"),
) -> list[SkillFamilyResponse]:
    """List skill families, optionally filtered by taxonomy + tag.

    The ``tag`` filter is applied in Python after the DB query because tags
    live in a JSON column. With ≤50 families expected, this is trivially cheap.
    """
    families = await list_families(
        domain_id=domain,
        focus_id=focus,
        language_id=language,
    )
    if tag is not None:
        families = [f for f in families if tag in f.tags]
    return [_family_to_response(f) for f in families]


@router.get("/api/families/{family_id}")
async def get_family_detail(family_id: str) -> dict:
    """Return a single family with a summary of its variants.

    Shape: ``{"family": {...}, "variant_count": N, "active_variants": [...]}``.
    Active variants are the ones with ``is_active=True``, typically one per
    dimension — the current winners.
    """
    family = await get_family(family_id)
    if family is None:
        raise HTTPException(status_code=404, detail=f"family not found: {family_id}")

    all_variants = await get_variants_for_family(family_id)
    active = [_variant_to_response(v) for v in all_variants if v.is_active]
    return {
        "family": _family_to_response(family).model_dump(),
        "variant_count": len(all_variants),
        "active_variants": [v.model_dump() for v in active],
    }


@router.get(
    "/api/families/{family_id}/variants", response_model=list[VariantResponse]
)
async def list_family_variants(
    family_id: str,
    dimension: str | None = Query(default=None),
    tier: str | None = Query(default=None),
) -> list[VariantResponse]:
    """List every variant in a family, optionally filtered by dimension + tier.

    Ordered by fitness_score DESC. Returns 404 if the family itself is missing."""
    family = await get_family(family_id)
    if family is None:
        raise HTTPException(status_code=404, detail=f"family not found: {family_id}")

    variants = await get_variants_for_family(
        family_id, dimension=dimension, tier=tier
    )
    return [_variant_to_response(v) for v in variants]


class SwapVariantRequest(BaseModel):
    dimension: str = Field(..., description="Dimension slug to swap within")
    variant_id: str = Field(..., description="ID of the variant to mark active")


@router.post("/api/families/{family_id}/swap-variant")
async def swap_family_variant(
    family_id: str, req: SwapVariantRequest
) -> dict:
    """Swap which variant is active for a (family, dimension) pair.

    Marks every variant in the (family, dimension) as ``is_active=False``,
    then marks the requested variant as ``is_active=True``. Returns the
    new active variant. Wave 5-2 stub: this does NOT trigger re-assembly
    automatically — call ``GET /api/families/{id}/assembly`` to fetch the
    current composite, or trigger a fresh evolve run if you want a new
    composite assembled.
    """
    family = await get_family(family_id)
    if family is None:
        raise HTTPException(status_code=404, detail=f"family not found: {family_id}")

    variants = await get_variants_for_family(family_id, dimension=req.dimension)
    if not variants:
        raise HTTPException(
            status_code=404,
            detail=f"no variants for family={family_id} dimension={req.dimension}",
        )

    target = next((v for v in variants if v.id == req.variant_id), None)
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"variant {req.variant_id} not found in family={family_id} "
                f"dimension={req.dimension}"
            ),
        )

    # Deactivate every variant in the dimension, then activate the target
    for v in variants:
        v.is_active = v.id == target.id
        await save_variant(v)

    return {
        "family_id": family_id,
        "dimension": req.dimension,
        "active_variant_id": target.id,
        "fitness_score": target.fitness_score,
    }


class EvolveVariantRequest(BaseModel):
    dimension: str = Field(..., description="Dimension slug to re-evolve")
    population_size: int = 2
    num_generations: int = 1
    parent_run_id: str | None = Field(
        default=None,
        description="Explicit parent run id; defaults to latest run for the family",
    )


@router.post("/api/families/{family_id}/evolve-variant")
async def evolve_family_variant(
    family_id: str, req: EvolveVariantRequest
) -> dict:
    """Schedule a fresh single-dimension mini-evolution for a family.

    Wave 5-2 stub: creates a new ``VariantEvolution`` row with status
    "pending" and returns its id. The orchestrator picks it up the next
    time the parent run is processed. The frontend uses this to surface
    "Re-evolve this dimension" without launching a full atomic run.

    The ``parent_run_id`` is the existing run that the variant evolution
    attaches to. If the caller doesn't pass one, we look up the most
    recent ``evolution_runs`` row for this family. Returns 400 if neither
    is available because the FK on ``variant_evolutions.parent_run_id``
    requires a real run row.
    """
    family = await get_family(family_id)
    if family is None:
        raise HTTPException(status_code=404, detail=f"family not found: {family_id}")

    # Resolve parent_run_id — prefer the explicit one, else find the
    # latest evolution_run row tied to this family.
    parent_run_id = req.parent_run_id
    if parent_run_id is None:
        from skillforge.db.queries import _connect

        async with _connect() as conn, conn.execute(
            "SELECT id FROM evolution_runs WHERE family_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (family_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"no parent_run_id provided and no existing run found for "
                    f"family={family_id}"
                ),
            )
        parent_run_id = row["id"]

    # Look up the existing variants in this dimension to derive the tier
    existing = await get_variants_for_family(family_id, dimension=req.dimension)
    tier = existing[0].tier if existing else "capability"

    vevo = VariantEvolution(
        id=f"vevo_{uuid.uuid4().hex[:12]}",
        family_id=family_id,
        dimension=req.dimension,
        tier=tier,
        parent_run_id=parent_run_id,
        population_size=req.population_size,
        num_generations=req.num_generations,
        status="pending",
        created_at=datetime.now(UTC),
    )
    await save_variant_evolution(vevo)

    return {
        "family_id": family_id,
        "dimension": req.dimension,
        "variant_evolution_id": vevo.id,
        "status": "pending",
        "tier": tier,
        "parent_run_id": parent_run_id,
    }


@router.get("/api/families/{family_id}/assembly")
async def get_family_assembly(family_id: str) -> dict:
    """Return the current best assembled composite skill for the family.

    Shape: ``{"family_id": "...", "best_assembly_id": "...", "skill": {...}}``.
    Returns 404 if the family doesn't exist or has no assembly yet (atomic
    runs that haven't reached the assembly step won't have a
    ``best_assembly_id``).
    """
    family = await get_family(family_id)
    if family is None:
        raise HTTPException(status_code=404, detail=f"family not found: {family_id}")

    if not family.best_assembly_id:
        raise HTTPException(
            status_code=404,
            detail=f"family {family_id} has no assembled composite yet",
        )

    # Resolve the composite SkillGenome
    from skillforge.db.queries import _connect, _row_to_genome

    async with _connect() as conn, conn.execute(
        "SELECT * FROM skill_genomes WHERE id = ?",
        (family.best_assembly_id,),
    ) as cur:
        row = await cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"family {family_id} references best_assembly_id="
                f"{family.best_assembly_id} but the genome row is missing"
            ),
        )

    composite = _row_to_genome(row)
    return {
        "family_id": family.id,
        "family_slug": family.slug,
        "best_assembly_id": composite.id,
        "skill": composite.to_dict(),
    }
