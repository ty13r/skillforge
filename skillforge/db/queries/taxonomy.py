"""CRUD for v2.0 taxonomy: TaxonomyNode + SkillFamily + Variant + VariantEvolution.

A Skill Family is classified by a (domain, focus, language) triple where each
level is a TaxonomyNode. Variants are child skills of a Family, each targeting
a single dimension of variation; VariantEvolutions are the per-dimension
mini-evolutions that produce those variants.
"""

from __future__ import annotations

import json
from pathlib import Path

import aiosqlite

from skillforge.db.queries._helpers import _connect, _int_or_none
from skillforge.models import SkillFamily, TaxonomyNode, Variant, VariantEvolution


def _row_to_taxonomy_node(row: aiosqlite.Row) -> TaxonomyNode:
    return TaxonomyNode.from_dict(
        {
            "id": row["id"],
            "level": row["level"],
            "slug": row["slug"],
            "label": row["label"],
            "parent_id": row["parent_id"],
            "description": row["description"],
            "created_at": row["created_at"],
        }
    )


def _row_to_family(row: aiosqlite.Row) -> SkillFamily:
    return SkillFamily.from_dict(
        {
            "id": row["id"],
            "slug": row["slug"],
            "label": row["label"],
            "specialization": row["specialization"],
            "domain_id": row["domain_id"],
            "focus_id": row["focus_id"],
            "language_id": row["language_id"],
            "tags": json.loads(row["tags"]),
            "decomposition_strategy": row["decomposition_strategy"],
            "best_assembly_id": row["best_assembly_id"],
            "created_at": row["created_at"],
        }
    )


def _row_to_variant(row: aiosqlite.Row) -> Variant:
    return Variant.from_dict(
        {
            "id": row["id"],
            "family_id": row["family_id"],
            "dimension": row["dimension"],
            "tier": row["tier"],
            "genome_id": row["genome_id"],
            "fitness_score": row["fitness_score"],
            "is_active": bool(row["is_active"]),
            "evolution_id": row["evolution_id"],
            "created_at": row["created_at"],
        }
    )


def _row_to_variant_evolution(row: aiosqlite.Row) -> VariantEvolution:
    return VariantEvolution.from_dict(
        {
            "id": row["id"],
            "family_id": row["family_id"],
            "dimension": row["dimension"],
            "tier": row["tier"],
            "parent_run_id": row["parent_run_id"],
            "population_size": row["population_size"],
            "num_generations": row["num_generations"],
            "status": row["status"],
            "winner_variant_id": row["winner_variant_id"],
            "foundation_genome_id": row["foundation_genome_id"],
            "challenge_id": row["challenge_id"],
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
        }
    )


async def save_taxonomy_node(
    node: TaxonomyNode,
    db_path: Path | None = None,
) -> None:
    """Upsert a taxonomy node by id. Idempotent on id conflict."""
    d = node.to_dict()
    async with _connect(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO taxonomy_nodes
                (id, level, slug, label, parent_id, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                level=excluded.level,
                slug=excluded.slug,
                label=excluded.label,
                parent_id=excluded.parent_id,
                description=excluded.description
            """,
            (
                d["id"],
                d["level"],
                d["slug"],
                d["label"],
                d["parent_id"],
                d["description"],
                d["created_at"],
            ),
        )
        await conn.commit()


async def get_taxonomy_node(
    node_id: str,
    db_path: Path | None = None,
) -> TaxonomyNode | None:
    """Fetch a single node by id."""
    async with _connect(db_path) as conn, conn.execute(
        "SELECT * FROM taxonomy_nodes WHERE id = ?", (node_id,)
    ) as cur:
        row = await cur.fetchone()
    return _row_to_taxonomy_node(row) if row is not None else None


async def get_taxonomy_node_by_slug(
    level: str,
    slug: str,
    parent_id: str | None = None,
    db_path: Path | None = None,
) -> TaxonomyNode | None:
    """Fetch a node by its (level, slug, parent_id) natural key.

    ``parent_id`` is compared with ``IS`` semantics so NULL-parent domain rows
    are matched correctly.
    """
    async with _connect(db_path) as conn:
        if parent_id is None:
            query = (
                "SELECT * FROM taxonomy_nodes "
                "WHERE level = ? AND slug = ? AND parent_id IS NULL"
            )
            params: tuple = (level, slug)
        else:
            query = (
                "SELECT * FROM taxonomy_nodes "
                "WHERE level = ? AND slug = ? AND parent_id = ?"
            )
            params = (level, slug, parent_id)
        async with conn.execute(query, params) as cur:
            row = await cur.fetchone()
    return _row_to_taxonomy_node(row) if row is not None else None


async def get_taxonomy_tree(
    db_path: Path | None = None,
) -> list[TaxonomyNode]:
    """Return every taxonomy node as a flat list.

    Callers assemble the tree client-side from ``parent_id`` relationships.
    Ordered by ``level`` (domain → focus → language) then ``slug`` for stable
    display. Cheap query — the taxonomy is small by design.
    """
    level_order = {"domain": 0, "focus": 1, "language": 2}
    async with _connect(db_path) as conn, conn.execute("SELECT * FROM taxonomy_nodes") as cur:
        rows = await cur.fetchall()
    nodes = [_row_to_taxonomy_node(row) for row in rows]
    nodes.sort(key=lambda n: (level_order.get(n.level, 99), n.slug))
    return nodes


async def save_skill_family(
    family: SkillFamily,
    db_path: Path | None = None,
) -> None:
    """Upsert a skill family by id."""
    d = family.to_dict()
    async with _connect(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO skill_families
                (id, slug, label, specialization, domain_id, focus_id,
                 language_id, tags, decomposition_strategy, best_assembly_id,
                 created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                slug=excluded.slug,
                label=excluded.label,
                specialization=excluded.specialization,
                domain_id=excluded.domain_id,
                focus_id=excluded.focus_id,
                language_id=excluded.language_id,
                tags=excluded.tags,
                decomposition_strategy=excluded.decomposition_strategy,
                best_assembly_id=excluded.best_assembly_id
            """,
            (
                d["id"],
                d["slug"],
                d["label"],
                d["specialization"],
                d["domain_id"],
                d["focus_id"],
                d["language_id"],
                json.dumps(d["tags"]),
                d["decomposition_strategy"],
                d["best_assembly_id"],
                d["created_at"],
            ),
        )
        await conn.commit()


async def get_family(
    family_id: str,
    db_path: Path | None = None,
) -> SkillFamily | None:
    """Fetch a single skill family by id."""
    async with _connect(db_path) as conn, conn.execute(
        "SELECT * FROM skill_families WHERE id = ?", (family_id,)
    ) as cur:
        row = await cur.fetchone()
    return _row_to_family(row) if row is not None else None


async def get_family_by_slug(
    slug: str,
    db_path: Path | None = None,
) -> SkillFamily | None:
    """Fetch a family by its slug (unique)."""
    async with _connect(db_path) as conn, conn.execute(
        "SELECT * FROM skill_families WHERE slug = ?", (slug,)
    ) as cur:
        row = await cur.fetchone()
    return _row_to_family(row) if row is not None else None


async def list_families(
    *,
    domain_id: str | None = None,
    focus_id: str | None = None,
    language_id: str | None = None,
    db_path: Path | None = None,
) -> list[SkillFamily]:
    """List families filterable by any taxonomy slot. All args optional.

    Filters compose with AND. Ordered by ``created_at DESC``.
    """
    clauses: list[str] = []
    params: list[str] = []
    if domain_id is not None:
        clauses.append("domain_id = ?")
        params.append(domain_id)
    if focus_id is not None:
        clauses.append("focus_id = ?")
        params.append(focus_id)
    if language_id is not None:
        clauses.append("language_id = ?")
        params.append(language_id)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"SELECT * FROM skill_families{where} ORDER BY created_at DESC"
    async with _connect(db_path) as conn, conn.execute(query, tuple(params)) as cur:
        rows = await cur.fetchall()
    return [_row_to_family(r) for r in rows]


async def save_variant(
    variant: Variant,
    db_path: Path | None = None,
) -> None:
    """Upsert a variant by id. Typical update path rewrites fitness_score +
    is_active, which is why those fields are in the DO UPDATE clause."""
    d = variant.to_dict()
    async with _connect(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO variants
                (id, family_id, dimension, tier, genome_id, fitness_score,
                 is_active, evolution_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                fitness_score=excluded.fitness_score,
                is_active=excluded.is_active,
                evolution_id=excluded.evolution_id
            """,
            (
                d["id"],
                d["family_id"],
                d["dimension"],
                d["tier"],
                d["genome_id"],
                d["fitness_score"],
                _int_or_none(d["is_active"]),
                d["evolution_id"],
                d["created_at"],
            ),
        )
        await conn.commit()


async def get_variants_for_family(
    family_id: str,
    *,
    dimension: str | None = None,
    tier: str | None = None,
    db_path: Path | None = None,
) -> list[Variant]:
    """Return every variant in a family. Optional filter by dimension and tier."""
    clauses = ["family_id = ?"]
    params: list[str] = [family_id]
    if dimension is not None:
        clauses.append("dimension = ?")
        params.append(dimension)
    if tier is not None:
        clauses.append("tier = ?")
        params.append(tier)
    query = (
        f"SELECT * FROM variants WHERE {' AND '.join(clauses)} "
        "ORDER BY fitness_score DESC, created_at DESC"
    )
    async with _connect(db_path) as conn, conn.execute(query, tuple(params)) as cur:
        rows = await cur.fetchall()
    return [_row_to_variant(r) for r in rows]


async def get_active_variants(
    family_id: str,
    db_path: Path | None = None,
) -> list[Variant]:
    """Return the currently-active variants for a family (``is_active=1``).

    Typically one per ``(family_id, dimension)`` — the winner. Ordered by
    tier (foundation first) then dimension for deterministic output.
    """
    tier_order = {"foundation": 0, "capability": 1}
    async with _connect(db_path) as conn, conn.execute(
        "SELECT * FROM variants WHERE family_id = ? AND is_active = 1",
        (family_id,),
    ) as cur:
        rows = await cur.fetchall()
    variants = [_row_to_variant(r) for r in rows]
    variants.sort(key=lambda v: (tier_order.get(v.tier, 99), v.dimension))
    return variants


async def save_variant_evolution(
    evolution: VariantEvolution,
    db_path: Path | None = None,
) -> None:
    """Upsert a variant evolution record by id."""
    d = evolution.to_dict()
    async with _connect(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO variant_evolutions
                (id, family_id, dimension, tier, parent_run_id, population_size,
                 num_generations, status, winner_variant_id, foundation_genome_id,
                 challenge_id, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status=excluded.status,
                winner_variant_id=excluded.winner_variant_id,
                foundation_genome_id=excluded.foundation_genome_id,
                challenge_id=excluded.challenge_id,
                completed_at=excluded.completed_at
            """,
            (
                d["id"],
                d["family_id"],
                d["dimension"],
                d["tier"],
                d["parent_run_id"],
                d["population_size"],
                d["num_generations"],
                d["status"],
                d["winner_variant_id"],
                d["foundation_genome_id"],
                d["challenge_id"],
                d["created_at"],
                d["completed_at"],
            ),
        )
        await conn.commit()


async def get_variant_evolution(
    evolution_id: str,
    db_path: Path | None = None,
) -> VariantEvolution | None:
    """Fetch a variant evolution row by id."""
    async with _connect(db_path) as conn, conn.execute(
        "SELECT * FROM variant_evolutions WHERE id = ?", (evolution_id,)
    ) as cur:
        row = await cur.fetchone()
    return _row_to_variant_evolution(row) if row is not None else None


async def get_variant_evolutions_for_run(
    parent_run_id: str,
    db_path: Path | None = None,
) -> list[VariantEvolution]:
    """Return all variant evolutions created by a parent evolution run."""
    async with _connect(db_path) as conn, conn.execute(
        "SELECT * FROM variant_evolutions WHERE parent_run_id = ? "
        "ORDER BY created_at ASC",
        (parent_run_id,),
    ) as cur:
        rows = await cur.fetchall()
    return [_row_to_variant_evolution(r) for r in rows]

