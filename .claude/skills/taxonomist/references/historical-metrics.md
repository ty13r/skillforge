# Historical Metrics per Taxonomy Node

The Taxonomist uses historical performance data to weight its decisions: which nodes have produced high-fitness variants, which are chronically underperforming (hinting at bad decomposition), which mutations have worked, and which variants are strong cross-family reuse candidates.

This document defines the **schema** for per-node historical metrics. The data is populated over time as evolution runs complete. Until Wave 4+ begins populating it, this file describes the fields and how they're used — not the current contents.

> **Note**: empty until runs complete. Wave 4+ will begin populating rows per taxonomy node after every evolution run.

## Per-Node Schema

Each taxonomy node (domain, focus, or language) and each skill family accumulates a row of aggregated metrics:

| Field | Type | Notes |
|-------|------|-------|
| `node_id` | str | UUID of the taxonomy_node or skill_family |
| `node_slug` | str | Kebab-case slug |
| `level` | str | `"domain"` / `"focus"` / `"language"` / `"family"` |
| `run_count` | int | Total evolution runs completed under this node |
| `total_cost_usd` | float | Cumulative API spend |
| `avg_fitness_delta` | float | Mean fitness improvement (gen N vs gen 0) across all runs |
| `best_variant_id` | str \| null | UUID of the highest-fitness variant ever produced under this node |
| `best_fitness` | float | Fitness score of the best variant |
| `last_run_at` | str | ISO-8601 UTC timestamp of most recent run |
| `avg_wall_time_sec` | float | Mean wall-clock duration per run |
| `aggregated_mutations` | list[obj] | Top N mutation patterns that improved fitness (see below) |

### `aggregated_mutations` shape

```json
[
  {
    "pattern": "strengthen-instructions",
    "trigger_metric": "instruction_compliance",
    "applied_count": 14,
    "success_rate": 0.71,
    "avg_fitness_delta": 0.08
  }
]
```

Each entry is a mutation pattern the Breeder has applied under this node, paired with the metric that typically triggered it and how often it worked. The Taxonomist uses this to recommend which dimensions are likely to respond well to further evolution vs which are near saturation.

## Aggregation Rules

- **Rolling 30-day window** for velocity metrics: `run_count`, `avg_wall_time_sec`, `avg_fitness_delta`. Captures how the node is trending right now, not how it performed years ago.
- **All-time** for success metrics: `best_variant_id`, `best_fitness`, `total_cost_usd`. Peak performance never decays.
- **Rebuild on run completion**: every time an evolution run completes, recompute the affected node rows. Cheap because the data is already in SQLite.

## How the Taxonomist Uses This Data

### Identify underperforming nodes → reconsider decomposition

If a focus node has `run_count ≥ 5` and `avg_fitness_delta < 0.05`, evolution isn't producing meaningful improvement under it. That's a signal the decomposition into dimensions may be wrong — the Taxonomist should flag the family for re-decomposition instead of spawning another atomic run.

### Identify winning variants → cross-family reuse

When classifying a new specialization, the Taxonomist queries related families (same Focus or Language) for their `best_variant_id` + `best_fitness`. Any variant with `best_fitness ≥ 0.8` in a related family becomes a reuse candidate, surfaced in the `cross_family_reuse` list of the classification output.

### Weight decomposition confidence

If two candidate decompositions look equally plausible, prefer the one where the implied nodes have stronger historical performance. Proven categories are a safer bet than speculative new ones.

### Cost-aware mode selection

Nodes with `avg_wall_time_sec < 600` and `avg_fitness_delta > 0.15` are good candidates for atomic mode — the overhead pays off. Nodes with high wall time and low delta are candidates for defaulting back to molecular.

## JSON Schema Example

A materialized row for a hypothetical `testing > unit-tests > python` family once data exists:

```json
{
  "node_id": "fam_a1b2c3d4",
  "node_slug": "django-rest-pytest",
  "level": "family",
  "run_count": 12,
  "total_cost_usd": 47.20,
  "avg_fitness_delta": 0.21,
  "best_variant_id": "var_f7e8d9",
  "best_fitness": 0.93,
  "last_run_at": "2026-06-15T14:22:00Z",
  "avg_wall_time_sec": 1430.5,
  "aggregated_mutations": [
    {
      "pattern": "clarify-examples",
      "trigger_metric": "instruction_compliance",
      "applied_count": 9,
      "success_rate": 0.78,
      "avg_fitness_delta": 0.11
    },
    {
      "pattern": "reduce-verbosity",
      "trigger_metric": "token_input",
      "applied_count": 6,
      "success_rate": 0.5,
      "avg_fitness_delta": 0.04
    }
  ]
}
```

## Storage

Rows live in a `historical_metrics` table (or a materialized view built from `evolution_runs`, `variants`, and `variant_evolutions`). The exact storage mechanism is a Wave 4 decision — this document only specifies the logical schema and usage.

Until that wave lands, the Taxonomist treats historical metrics as "may be empty" and does not crash when a node has no row. Empty data means "no prior signal" — classify purely from the specialization text.
