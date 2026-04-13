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
  // v2.0 — explicit override; omit/undefined means "let the Taxonomist decide"
  evolution_mode?: "atomic" | "molecular";
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
  // v2.0 — present so the Advanced toggle can render the VariantBreakdown
  family_id?: string | null;
  evolution_mode?: "molecular" | "atomic";
  // v2.0 Step 1b — audit trail + reconstructed integration report
  learning_log?: string[];
  // v2.1.3 — honest composite baseline from SKLD-bench
  baseline_fitness?: number | null;
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

// --- v2.0 Step 1b — post-run report shape matching skillforge/engine/report.py

export interface RunReportMetadata {
  run_id: string;
  mode: string;
  specialization: string;
  status: string;
  population_size: number;
  num_generations: number;
  evolution_mode: string;
  family_id: string | null;
  total_cost_usd: number;
  max_budget_usd: number;
  created_at: string | null;
  completed_at: string | null;
  duration_sec: number | null;
  failure_reason: string | null;
}

export interface RunReportTaxonomy {
  family_id: string;
  family_slug: string;
  family_label: string;
  decomposition_strategy: string;
  domain: { slug: string; label: string } | null;
  focus: { slug: string; label: string } | null;
  language: { slug: string; label: string } | null;
  tags: string[];
}

export interface RunReportChallenge {
  id: string;
  prompt: string;
  difficulty: string;
  verification_method: string;
  evaluation_criteria: Record<string, unknown>;
}

export interface RunReportVariantEvolution {
  id: string;
  dimension: string;
  tier: "foundation" | "capability";
  status: string;
  population_size: number;
  num_generations: number;
  winner_variant_id: string | null;
  foundation_genome_id: string | null;
  challenge_id: string | null;
  created_at: string | null;
  completed_at: string | null;
}

export interface RunReportSummary {
  best_skill_id: string | null;
  aggregate_fitness: number;
  total_cost_usd: number;
  cost_per_generation: number;
  wall_clock_duration_sec: number | null;
  evolution_mode: string;
  dimensions_evolved: (string | number)[];
  key_discoveries: string[];
}

export interface RunReportGenome {
  id: string;
  generation: number;
  maturity: string;
  meta_strategy: string;
  parent_ids: string[];
  traits: string[];
  pareto_objectives: Record<string, number>;
  deterministic_scores: Record<string, number>;
  skill_md_content: string;
  frontmatter: Record<string, unknown>;
  supporting_files?: Record<string, string>;
}

// Parsed from the "[competition_scores] {...}" learning_log entry.
export interface CompetitionMatch {
  dimension: string;
  tier: "foundation" | "capability";
  challenge_ids: string[];
  variant_1_label: string;
  variant_2_label: string;
  variant_1_scores: number[];
  variant_2_scores: number[];
  variant_1_mean: number;
  variant_2_mean: number;
  winner_slot: 1 | 2;
  winning_fitness: number;
}

export interface CompetitionScoresPayload {
  matches: CompetitionMatch[];
  generation: number;
  total_generations: number;
  challenges_per_variant: number;
  baseline_ran: boolean;
  scorer: string;
}

export interface RunReport {
  metadata: RunReportMetadata;
  taxonomy: RunReportTaxonomy | null;
  challenges: RunReportChallenge[];
  generations: Record<string, unknown>[];
  variant_evolutions: RunReportVariantEvolution[];
  skill_genomes: RunReportGenome[];
  assembly_report: {
    family_id: string;
    best_assembly_id: string | null;
    active_variants: Record<string, unknown>[];
  } | null;
  bible_findings: unknown[];
  learning_log: string[];
  summary: RunReportSummary;
  generated_at: string;
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
  | "heartbeat"
  // v2.0 atomic evolution events
  | "taxonomy_classified"
  | "decomposition_complete"
  | "variant_evolution_started"
  | "variant_evolution_complete"
  | "assembly_started"
  | "assembly_complete"
  | "integration_test_started"
  | "integration_test_complete";

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
  // v2.0 atomic evolution payload fields
  variant_evolution_id?: string;
  dimension?: string;
  tier?: string;
  family_id?: string;
  family_slug?: string;
  domain_slug?: string;
  focus_slug?: string;
  language_slug?: string;
  evolution_mode?: "atomic" | "molecular";
  created_new_nodes?: string[];
  dimension_count?: number;
  dimensions?: { name: string; tier: string; description: string; evaluation_focus: string }[];
  reuse_recommendations?: { source_family_slug: string; dimension: string; variant_slug: string; fitness: number | null; reason: string }[];
  // competitor output + scores
  output_files?: Record<string, string>;
  competitor_scores?: {
    composite: number;
    l0: number;
    compile: boolean;
    ast: number;
    behavioral: number;
    template: number;
    brevity: number;
  };
  // variant_evolution_complete fields
  status?: string;
  winner_variant_id?: string;
  // assembly fields
  capability_count?: number;
  mode?: string;
  composite_skill_id?: string;
  integration_passed?: boolean;
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
  // Output (from competitor_finished)
  outputFiles?: Record<string, string>;
  // Scores (from competitor_finished)
  scores?: {
    composite: number;
    l0: number;
    compile: boolean;
    ast: number;
    behavioral: number;
    template: number;
    brevity: number;
  };
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

// --- v2.0 taxonomy + families + variants ----------------------------------

export type TaxonomyLevel = "domain" | "focus" | "language";

export interface TaxonomyNode {
  id: string;
  level: TaxonomyLevel;
  slug: string;
  label: string;
  parent_id: string | null;
  description: string;
  created_at?: string | null;
}

export type DecompositionStrategy = "atomic" | "molecular";

export interface SkillFamily {
  id: string;
  slug: string;
  label: string;
  specialization: string;
  domain_id: string | null;
  focus_id: string | null;
  language_id: string | null;
  tags: string[];
  decomposition_strategy: DecompositionStrategy;
  best_assembly_id: string | null;
  created_at?: string | null;
}

export type VariantTier = "foundation" | "capability";

export interface Variant {
  id: string;
  family_id: string;
  dimension: string;
  tier: VariantTier;
  genome_id: string;
  fitness_score: number;
  is_active: boolean;
  evolution_id: string | null;
  created_at?: string | null;
}

export interface DimensionStatus {
  id: string;
  dimension: string;
  tier: VariantTier;
  status: "pending" | "running" | "complete" | "failed";
  winner_variant_id: string | null;
  challenge_id: string | null;
  population_size: number;
  num_generations: number;
  created_at: string | null;
  completed_at: string | null;
  fitness_score: number | null;
  genome_id: string | null;
}

export interface TaxonomyNodeDetail {
  node: TaxonomyNode;
  children: TaxonomyNode[];
}

export interface FamilyDetail {
  family: SkillFamily;
  variant_count: number;
  active_variants: Variant[];
}

// --- SKLD-bench types -------------------------------------------------------

export interface BenchFamilySummary {
  slug: string;
  label: string;
  challenges: number;
  challenges_scored: number;
  raw_composite: number | null;
  skill_composite: number | null;
  lift: number | null;
  compile_pct: number | null;
  raw_l0: number | null;
  skill_challenges: number;
}

export interface BenchScoringProgression {
  l0: number;
  compile: number;
  ast: number;
  behavioral: number;
  template: number;
  brevity: number;
  composite: number;
}

export interface BenchSummary {
  families: BenchFamilySummary[];
  overall: {
    challenges: number;
    challenges_scored: number;
    raw_composite: number | null;
  };
  scoring_progression: BenchScoringProgression | null;
}

export interface BenchTierBreakdown {
  tier: string;
  count: number;
  avg_composite: number;
  compile_pct: number;
  avg_behavioral: number;
  avg_l0: number;
}

export interface BenchDimension {
  dimension: string;
  count: number;
  avg_composite: number;
  compile_pct: number;
}

export interface BenchChallengeEntry {
  l0: number;
  composite: number | null;
  compiles: boolean;
  behavioral: number;
  ast: number;
  tokens: number;
  duration_ms: number;
  error: string | null;
}

export interface BenchChallenge {
  challenge_id: string;
  tier: string;
  dimension: string;
  raw?: BenchChallengeEntry;
  skill?: BenchChallengeEntry;
}

export interface BenchHistogram {
  buckets: string[];
  counts: number[];
}

export interface BenchFamilyDetail {
  family_slug: string;
  label: string;
  total_challenges: number;
  tiers: BenchTierBreakdown[];
  dimensions: BenchDimension[];
  histogram: BenchHistogram;
  challenges: BenchChallenge[];
}
