// TypeScript types mirroring skillforge/api/schemas.py and engine/events.py.
// Kept manually in sync with the Python source.

export type Mode = "domain" | "meta";

export type ExportFormat = "skill_dir" | "skill_md" | "agent_sdk_config";

export type RunStatus = "pending" | "running" | "complete" | "failed";

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
  status: RunStatus;
  best_fitness?: number | null;
  total_cost_usd: number;
}

export interface RunDetail {
  id: string;
  mode: string;
  specialization: string;
  status: string;
  population_size: number;
  num_generations: number;
  total_cost_usd: number;
  best_fitness?: number | null;
  best_skill_id?: string | null;
}

export interface LineageNode {
  id: string;
  generation: number;
  fitness: number;
  maturity: string;
  traits: string[];
}

export interface LineageEdge {
  parent_id: string;
  child_id: string;
  mutation_type: string;
}

// --- WebSocket events --------------------------------------------------------
// Discriminated union over the event types emitted by skillforge/engine/events.py.
// Every event has at least an `event` discriminator; many have a `generation`
// or other context fields. We use a permissive shape so the UI can read any
// event without strict type-narrowing — fields not present are simply absent.

export type EvolutionEventName =
  | "run_started"
  | "challenge_design_started"
  | "challenge_designed"
  | "generation_started"
  | "competitor_started"
  | "competitor_finished"
  | "judging_started"
  | "judging_layer_complete"
  | "scores_published"
  | "cost_update"
  | "breeding_started"
  | "breeding_report"
  | "generation_complete"
  | "evolution_complete"
  | "run_failed"
  | "run_cancelled"
  | "competitor_progress"
  | "heartbeat";

export interface EvolutionEvent {
  event: EvolutionEventName;
  generation?: number;
  layer?: number;
  competitor?: number;
  skill_id?: string;
  challenge_id?: string;
  difficulty?: string;
  prompt?: string;
  best_fitness?: number;
  avg_fitness?: number;
  pareto_front?: string[];
  generation_cost_usd?: number;
  total_cost_usd?: number;
  incremental?: boolean;
  competitor_cost_usd?: number;
  trace_length?: number;
  report?: string;
  new_lessons?: string[];
  best_skill_id?: string | null;
  generations_completed?: number;
  reason?: string;
  specialization?: string;
  mutations?: string[];
  traits?: string[];
  meta_strategy?: string;
  mutation_rationale?: string;
  skill_md_content?: string;
  turn?: number;
  tool_name?: string;
}

// --- Derived view state ------------------------------------------------------

export type CompetitorState =
  | "queued"
  | "writing"
  | "testing"
  | "iterating"
  | "done"
  | "error";

export interface CompetitorView {
  competitorId: number;
  skillId: string;
  state: CompetitorState;
  challengeId?: string;
  message?: string;
  // Skill identity (from competitor_started)
  mutations?: string[];
  traits?: string[];
  metaStrategy?: string;
  mutationRationale?: string;
  skillMdContent?: string;
  // Live progress (from competitor_progress)
  turn?: number;
  lastTool?: string;
}

export interface GenerationStats {
  number: number;
  best_fitness?: number;
  avg_fitness?: number;
  pareto_front?: string[];
  status: "running" | "judging" | "breeding" | "complete";
}

// --- Process flow phases (drives the sidebar diagram) ----------------------

export type PhaseId =
  | "design_challenges"
  | "spawn_or_breed"
  | "compete"
  | "judge"
  | "score_select"
  | "finalize";

export type PhaseStatus = "pending" | "running" | "complete" | "failed";

export interface PhaseState {
  id: PhaseId;
  label: string;
  status: PhaseStatus;
  detail?: string; // sub-progress like "8 of 15 competitors" or "L3 trace analysis"
}
