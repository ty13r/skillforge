// TypeScript types mirroring the Python API boundary (skillforge/api/schemas.py).
// Kept in sync manually; real expansion in Step 10.

export type Mode = "domain" | "meta";

export interface EvolveRequest {
  mode: Mode;
  specialization?: string;
  test_domains?: string[];
  population_size: number;
  num_generations: number;
  max_budget_usd: number;
}

export interface EvolveResponse {
  run_id: string;
  ws_url: string;
}

export interface RunSummary {
  id: string;
  mode: Mode;
  specialization: string;
  status: string;
  best_fitness?: number;
  total_cost_usd: number;
}
