"""Bootstrap the v2.0 taxonomy from the curated Gen 0 Skill library.

On first boot the ``taxonomy_nodes`` and ``skill_families`` tables are empty.
This loader walks ``SEED_SKILLS``, maps each seed to a ``(domain, focus,
language)`` triple using a hardcoded dictionary derived from the seed
categories, and idempotently creates the required taxonomy nodes and skill
family records.

The hardcoded mapping is the default path: fast, deterministic, zero API cost,
safe to run in tests without an API key. The full ``Taxonomist`` agent in
Phase 2 runs at runtime on real user submissions and can create richer
classifications — this bootstrap only seeds the starting taxonomy.

Idempotency: every seed is processed one at a time. For each one we look up
existing nodes by their natural keys ``(level, slug, parent_id)`` before
inserting. Running the loader twice, or adding a new seed to ``SEED_SKILLS``
between boots, is safe — only the missing rows are written.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from skillforge.db.queries import (
    get_family_by_slug,
    get_taxonomy_node_by_slug,
    get_taxonomy_tree,
    save_skill_family,
    save_taxonomy_node,
)
from skillforge.models import SkillFamily, TaxonomyNode
from skillforge.seeds import SEED_SKILLS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hardcoded taxonomy structure
# ---------------------------------------------------------------------------
# Mapping keys are the seed ``id`` strings in ``SEED_SKILLS``. The value is a
# tuple ``(domain_slug, focus_slug, language_slug, family_slug, family_label)``.
# A seed that isn't listed here gets classified into the catch-all
# ``universal`` domain → ``misc`` focus → ``universal`` language so it still
# lands in the registry.

_Classification = tuple[str, str, str, str, str]

_SEED_CLASSIFICATIONS: dict[str, _Classification] = {
    "seed-git-commit-message": (
        "code-quality",
        "reviews",
        "universal",
        "git-commit-message",
        "Git Commit Message Generator",
    ),
    "seed-code-review": (
        "code-quality",
        "reviews",
        "universal",
        "code-review",
        "Code Review Assistant",
    ),
    "seed-unit-test-generator": (
        "testing",
        "unit-tests",
        "python",
        "unit-test-generator",
        "Unit Test Generator",
    ),
    "seed-api-endpoint-designer": (
        "development",
        "api-design",
        "universal",
        "api-endpoint-designer",
        "REST API Endpoint Designer",
    ),
    "seed-database-migration": (
        "data",
        "migrations",
        "sql",
        "database-migration",
        "Database Migration Generator",
    ),
    "seed-dockerfile-optimizer": (
        "devops",
        "containers",
        "docker",
        "dockerfile-optimizer",
        "Dockerfile Optimizer",
    ),
    "seed-ci-cd-pipeline": (
        "devops",
        "ci-cd",
        "yaml",
        "ci-cd-pipeline",
        "CI/CD Pipeline Generator",
    ),
    "seed-dependency-auditor": (
        "security",
        "dependencies",
        "universal",
        "dependency-auditor",
        "Dependency Auditor",
    ),
    "seed-secret-scanner": (
        "security",
        "secrets",
        "universal",
        "secret-scanner",
        "Secret Scanner",
    ),
    "seed-api-doc-generator": (
        "documentation",
        "api",
        "universal",
        "api-doc-generator",
        "API Documentation Generator",
    ),
    "seed-accessibility-auditor": (
        "development",
        "accessibility",
        "html",
        "accessibility-auditor",
        "Web Accessibility Auditor",
    ),
    "seed-data-transformer": (
        "data",
        "transforms",
        "python",
        "data-transformer",
        "Data Format Transformer",
    ),
    "seed-regex-builder": (
        "code-quality",
        "productivity",
        "universal",
        "regex-builder",
        "Regex Pattern Builder",
    ),
    "seed-error-handler": (
        "devops",
        "observability",
        "universal",
        "error-handler",
        "Error Handling & Logging Generator",
    ),
    "seed-terraform-module-full": (
        "devops",
        "iac",
        "terraform",
        "terraform-module-full",
        "Terraform Module Generator",
    ),
}

# Human-readable labels for the slugs the classifications reference. Kept
# separate so adding a new classification is a one-line change and labels
# stay consistent across domains/focuses.
_DOMAIN_LABELS: dict[str, str] = {
    "code-quality": "Code Quality",
    "testing": "Testing",
    "development": "Development",
    "data": "Data",
    "devops": "DevOps",
    "security": "Security",
    "documentation": "Documentation",
    "universal": "Universal",
}

_FOCUS_LABELS: dict[str, str] = {
    "reviews": "Code Reviews",
    "productivity": "Developer Productivity",
    "unit-tests": "Unit Tests",
    "api-design": "API Design",
    "accessibility": "Accessibility",
    "migrations": "Migrations",
    "transforms": "Data Transforms",
    "containers": "Containers",
    "ci-cd": "CI/CD",
    "iac": "Infrastructure as Code",
    "observability": "Observability",
    "dependencies": "Dependency Audit",
    "secrets": "Secret Detection",
    "api": "API Documentation",
    "misc": "Miscellaneous",
}

_LANGUAGE_LABELS: dict[str, str] = {
    "universal": "Universal",
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "sql": "SQL",
    "docker": "Docker",
    "yaml": "YAML",
    "html": "HTML",
    "terraform": "Terraform",
}

_FALLBACK_CLASSIFICATION: _Classification = (
    "universal",
    "misc",
    "universal",
    "uncategorized",
    "Uncategorized",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


async def _ensure_node(
    level: str,
    slug: str,
    label: str,
    parent_id: str | None,
    db_path: Path | None,
) -> TaxonomyNode:
    """Return an existing node or create a new one for ``(level, slug, parent_id)``.

    Looks up via the natural key first; inserts only when missing. The returned
    node always has a server-assigned ``id`` that callers can use as a FK.
    """
    existing = await get_taxonomy_node_by_slug(level, slug, parent_id, db_path)
    if existing is not None:
        return existing

    node = TaxonomyNode(
        id=f"tax_{uuid.uuid4().hex[:12]}",
        level=level,
        slug=slug,
        label=label,
        parent_id=parent_id,
        description="",
        created_at=_now(),
    )
    await save_taxonomy_node(node, db_path)
    logger.info(
        "taxonomy_seeds: created %s node '%s' (parent=%s)",
        level,
        slug,
        parent_id or "none",
    )
    return node


async def _ensure_family(
    seed_id: str,
    classification: _Classification,
    domain: TaxonomyNode,
    focus: TaxonomyNode,
    language: TaxonomyNode,
    db_path: Path | None,
) -> SkillFamily:
    """Return an existing family by slug or create one for ``seed_id``."""
    _, _, _, family_slug, family_label = classification
    existing = await get_family_by_slug(family_slug, db_path)
    if existing is not None:
        return existing

    family = SkillFamily(
        id=f"fam_{uuid.uuid4().hex[:12]}",
        slug=family_slug,
        label=family_label,
        specialization=seed_id,
        domain_id=domain.id,
        focus_id=focus.id,
        language_id=language.id,
        tags=[],
        decomposition_strategy="molecular",
        best_assembly_id=None,
        created_at=_now(),
    )
    await save_skill_family(family, db_path)
    logger.info(
        "taxonomy_seeds: created family '%s' under %s/%s/%s",
        family_slug,
        domain.slug,
        focus.slug,
        language.slug,
    )
    return family


def _classify_seed(seed_id: str) -> _Classification:
    return _SEED_CLASSIFICATIONS.get(seed_id, _FALLBACK_CLASSIFICATION)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def load_taxonomy(db_path: Path | None = None) -> dict:
    """Idempotently seed the taxonomy and family tables from ``SEED_SKILLS``.

    Safe to call on every boot. For each seed this function:
      1. Looks up or creates a ``domain`` node.
      2. Looks up or creates a ``focus`` node under that domain.
      3. Looks up or creates a ``language`` node under that focus.
      4. Looks up or creates a ``skill_families`` row referencing the triple.

    Returns a small diagnostic dict ``{"families": N, "nodes": M, "skipped": K}``
    so ``main.py`` can log the outcome.
    """
    existing_tree = await get_taxonomy_tree(db_path)
    if existing_tree:
        logger.info(
            "taxonomy_seeds: taxonomy already has %d nodes; running additive "
            "sync over %d seeds",
            len(existing_tree),
            len(SEED_SKILLS),
        )

    created_families = 0
    reused_families = 0

    for seed in SEED_SKILLS:
        seed_id = seed["id"]
        classification = _classify_seed(seed_id)
        domain_slug, focus_slug, lang_slug, _family_slug, _family_label = classification

        domain = await _ensure_node(
            "domain",
            domain_slug,
            _DOMAIN_LABELS.get(domain_slug, domain_slug.title()),
            None,
            db_path,
        )
        focus = await _ensure_node(
            "focus",
            focus_slug,
            _FOCUS_LABELS.get(focus_slug, focus_slug.title()),
            domain.id,
            db_path,
        )
        language = await _ensure_node(
            "language",
            lang_slug,
            _LANGUAGE_LABELS.get(lang_slug, lang_slug.title()),
            focus.id,
            db_path,
        )

        family_before = await get_family_by_slug(
            classification[3], db_path
        )
        await _ensure_family(seed_id, classification, domain, focus, language, db_path)
        if family_before is None:
            created_families += 1
        else:
            reused_families += 1

    # Count nodes after we're done so the diagnostic reflects the final state.
    final_tree = await get_taxonomy_tree(db_path)
    logger.info(
        "taxonomy_seeds: done — %d nodes total, %d families created, %d reused",
        len(final_tree),
        created_families,
        reused_families,
    )
    return {
        "families_created": created_families,
        "families_reused": reused_families,
        "nodes_total": len(final_tree),
    }
