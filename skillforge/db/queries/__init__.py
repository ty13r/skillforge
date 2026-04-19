"""Database CRUD package — split by entity for maintainability.

Every function previously on ``skillforge.db.queries`` is re-exported here
so ``from skillforge.db.queries import save_run`` etc. keeps working.
New code should prefer importing from the submodule directly:

    from skillforge.db.queries.runs import save_run, get_run

Submodule ownership:
  _helpers       — connection context manager + row helpers
  challenges     — Challenge rows (per-run evaluation tasks)
  genomes        — SkillGenome, CompetitionResult, Generation (per-generation data)
  runs           — EvolutionRun + lineage + leaked skills + zombies
  seeds          — candidate seeds (user-facing registry of starter skills)
  taxonomy       — TaxonomyNode + SkillFamily + Variant + VariantEvolution
  transcripts    — dispatch transcripts (audit trail of every LLM call)
"""

from __future__ import annotations

from skillforge.db.queries._helpers import _connect, _int_or_none, _row_get
from skillforge.db.queries.challenges import (
    _get_challenges_for_run,
    save_challenge,
)
from skillforge.db.queries.genomes import (
    _get_generations_for_run,
    _get_genome_by_id,
    _get_genomes_for_run_gen,
    _get_results_for_run_gen,
    _row_to_genome,
    _row_to_result,
    save_generation,
    save_genome,
    save_result,
)
from skillforge.db.queries.runs import (
    delete_leaked_skill,
    get_lineage,
    get_run,
    list_leaked_skills,
    list_runs,
    log_leaked_skill,
    mark_zombie_runs,
    save_run,
)
from skillforge.db.queries.seeds import (
    list_candidate_seeds,
    save_candidate_seed,
    update_candidate_seed_status,
)
from skillforge.db.queries.taxonomy import (
    _row_to_family,
    _row_to_taxonomy_node,
    _row_to_variant,
    _row_to_variant_evolution,
    get_active_variants,
    get_family,
    get_family_by_slug,
    get_taxonomy_node,
    get_taxonomy_node_by_slug,
    get_taxonomy_tree,
    get_variant_evolution,
    get_variant_evolutions_for_run,
    get_variants_for_family,
    list_families,
    save_skill_family,
    save_taxonomy_node,
    save_variant,
    save_variant_evolution,
)
from skillforge.db.queries.transcripts import save_transcript

__all__ = [
    # _helpers
    "_connect",
    "_int_or_none",
    "_row_get",
    # challenges
    "save_challenge",
    "_get_challenges_for_run",
    # genomes
    "save_genome",
    "save_result",
    "save_generation",
    "_get_genome_by_id",
    "_get_genomes_for_run_gen",
    "_get_generations_for_run",
    "_get_results_for_run_gen",
    "_row_to_genome",
    "_row_to_result",
    # runs
    "save_run",
    "get_run",
    "list_runs",
    "get_lineage",
    "log_leaked_skill",
    "list_leaked_skills",
    "delete_leaked_skill",
    "mark_zombie_runs",
    # seeds
    "save_candidate_seed",
    "list_candidate_seeds",
    "update_candidate_seed_status",
    # taxonomy
    "save_taxonomy_node",
    "get_taxonomy_node",
    "get_taxonomy_node_by_slug",
    "get_taxonomy_tree",
    "save_skill_family",
    "get_family",
    "get_family_by_slug",
    "list_families",
    "save_variant",
    "get_variants_for_family",
    "get_active_variants",
    "save_variant_evolution",
    "get_variant_evolution",
    "get_variant_evolutions_for_run",
    "_row_to_family",
    "_row_to_taxonomy_node",
    "_row_to_variant",
    "_row_to_variant_evolution",
    # transcripts
    "save_transcript",
]
