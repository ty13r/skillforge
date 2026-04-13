import { useEffect, useRef, useState } from "react";

import type {
  CompetitorView,
  EvolutionEvent,
  GenerationStats,
  PhaseState,
} from "../types";

export type ConnectionStatus = "connecting" | "open" | "closed" | "error";

export interface AtomicDimensionState {
  dimension: string;
  tier: string;
  status: "pending" | "running" | "complete" | "failed";
  fitness?: number;
  phase?: string;
  phaseDetail?: string;
}

export interface EvolutionSocketState {
  events: EvolutionEvent[];
  status: ConnectionStatus;
  currentGeneration: number;
  generations: GenerationStats[];
  competitors: CompetitorView[];
  isComplete: boolean;
  isFailed: boolean;
  failureReason?: string;
  totalCostUsd: number;
  latestBreedingReport?: string;
  latestLessons?: string[];
  bestSkillId?: string | null;
  /** Total competitors expected for the current generation (pop × challenges) */
  expectedCompetitors: number;
  /** Number of competitors that have finished in the current generation */
  finishedCompetitors: number;
  /** Last "tick" timestamp from any non-heartbeat event — used for stale detection */
  lastEventAt: number;
  /** Which judging layer (1-5) most recently completed; 0 = none yet */
  currentJudgingLayer: number;
  /** Whether this run is atomic (detected from events) */
  isAtomic: boolean;
  /** Per-dimension status for atomic runs (built from events) */
  atomicDimensions: AtomicDimensionState[];
  /** Currently active dimension name */
  activeDimension?: string;
}

const INITIAL_STATE: EvolutionSocketState = {
  events: [],
  status: "connecting",
  currentGeneration: 0,
  generations: [],
  competitors: [],
  isComplete: false,
  isFailed: false,
  totalCostUsd: 0,
  expectedCompetitors: 0,
  finishedCompetitors: 0,
  lastEventAt: 0,
  currentJudgingLayer: 0,
  isAtomic: false,
  atomicDimensions: [],
};

/**
 * Subscribes to the per-run WebSocket event stream and exposes derived state.
 *
 * Reconnects ONCE on close (no infinite loop).
 */
export function useEvolutionSocket(runId: string | null): EvolutionSocketState {
  const [state, setState] = useState<EvolutionSocketState>(INITIAL_STATE);
  const reconnectAttempted = useRef(false);

  useEffect(() => {
    if (!runId) return;

    // Reset on run change
    setState({ ...INITIAL_STATE });
    reconnectAttempted.current = false;

    let socket: WebSocket | null = null;
    let cancelled = false;

    const connect = () => {
      const url =
        (window.location.protocol === "https:" ? "wss://" : "ws://") +
        window.location.host +
        `/ws/evolve/${runId}`;
      socket = new WebSocket(url);

      socket.onopen = () => {
        if (cancelled) return;
        setState((s) => ({ ...s, status: "open" }));
      };

      socket.onmessage = (msg) => {
        if (cancelled) return;
        try {
          const ev = JSON.parse(msg.data) as EvolutionEvent;
          if (ev.event === "heartbeat") return;
          setState((s) => applyEvent(s, ev));
        } catch {
          // Ignore malformed payloads
        }
      };

      socket.onerror = () => {
        if (cancelled) return;
        setState((s) => ({ ...s, status: "error" }));
      };

      socket.onclose = () => {
        if (cancelled) return;
        setState((s) => ({ ...s, status: "closed" }));
        if (!reconnectAttempted.current) {
          reconnectAttempted.current = true;
          setTimeout(() => {
            if (!cancelled) connect();
          }, 1500);
        }
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (socket) socket.close();
    };
  }, [runId]);

  return state;
}

// ----------------------------------------------------------------------------
// Reducer-style state update from incoming events
// ----------------------------------------------------------------------------

export function applyEvent(
  state: EvolutionSocketState,
  ev: EvolutionEvent,
): EvolutionSocketState {
  const events = [...state.events, ev];
  const next = { ...state, events, lastEventAt: Date.now() };

  switch (ev.event) {
    case "generation_started":
      next.currentGeneration = ev.generation ?? next.currentGeneration;
      next.currentJudgingLayer = 0;
      next.generations = upsertGeneration(next.generations, {
        number: ev.generation ?? 0,
        status: "running",
      });
      next.competitors = []; // reset for new generation
      next.finishedCompetitors = 0;
      // expectedCompetitors gets set on first competitor_started below if
      // we don't already know it
      break;

    case "competitor_started":
      next.competitors = upsertCompetitor(next.competitors, {
        competitorId: ev.competitor ?? 0,
        skillId: ev.skill_id ?? "",
        challengeId: ev.challenge_id,
        state: "writing",
        mutations: ev.mutations,
        traits: ev.traits,
        metaStrategy: ev.meta_strategy,
        mutationRationale: ev.mutation_rationale,
        skillMdContent: ev.skill_md_content,
      });
      break;

    case "competitor_progress":
      next.competitors = upsertCompetitor(next.competitors, {
        competitorId: ev.competitor ?? 0,
        skillId: ev.skill_id ?? "",
        challengeId: ev.challenge_id,
        state: "writing",
        turn: ev.turn,
        lastTool: ev.tool_name,
      });
      break;

    case "competitor_finished":
      next.competitors = upsertCompetitor(next.competitors, {
        competitorId: ev.competitor ?? 0,
        skillId: ev.skill_id ?? "",
        challengeId: ev.challenge_id,
        state: "done",
        outputFiles: ev.output_files as Record<string, string> | undefined,
        scores: ev.competitor_scores as CompetitorView["scores"] | undefined,
      });
      next.finishedCompetitors = next.finishedCompetitors + 1;
      break;

    case "judging_started":
      next.generations = upsertGeneration(next.generations, {
        number: ev.generation ?? next.currentGeneration,
        status: "judging",
      });
      break;

    case "judging_layer_complete":
      next.currentJudgingLayer = (ev.layer as number) ?? next.currentJudgingLayer;
      break;

    case "scores_published":
      next.generations = upsertGeneration(next.generations, {
        number: ev.generation ?? next.currentGeneration,
        best_fitness: ev.best_fitness,
        avg_fitness: ev.avg_fitness,
        pareto_front: ev.pareto_front,
        status: "complete",
      });
      // For atomic runs, update the active dimension's fitness from scores
      if (next.isAtomic && ev.best_fitness != null) {
        const target = next.activeDimension
          ?? next.atomicDimensions.find((d) => d.status === "running")?.dimension;
        if (target) {
          next.atomicDimensions = next.atomicDimensions.map((d) =>
            d.dimension === target ? { ...d, fitness: ev.best_fitness } : d,
          );
        }
      }
      break;

    case "cost_update":
      if (ev.incremental) {
        next.totalCostUsd += (ev.total_cost_usd as number) ?? 0;
      } else {
        next.totalCostUsd = ev.total_cost_usd ?? next.totalCostUsd;
      }
      break;

    case "breeding_started":
      next.generations = upsertGeneration(next.generations, {
        number: ev.generation ?? next.currentGeneration,
        status: "breeding",
      });
      break;

    case "breeding_report":
      next.latestBreedingReport = ev.report;
      next.latestLessons = ev.new_lessons;
      break;

    case "generation_complete":
      next.generations = upsertGeneration(next.generations, {
        number: ev.generation ?? next.currentGeneration,
        status: "complete",
      });
      break;

    case "evolution_complete":
      next.isComplete = true;
      next.bestSkillId = ev.best_skill_id;
      next.totalCostUsd = ev.total_cost_usd ?? next.totalCostUsd;
      break;

    case "run_failed":
      next.isFailed = true;
      next.failureReason = ev.reason;
      break;

    case "run_cancelled":
      next.isFailed = true;
      next.failureReason = "cancelled by user";
      break;

    // Dimension phase progress (designing challenge, spawning variants, etc.)
    case "dimension_phase":
      if (ev.dimension) {
        next.atomicDimensions = next.atomicDimensions.map((d) =>
          d.dimension === ev.dimension
            ? { ...d, phase: ev.phase, phaseDetail: ev.detail }
            : d,
        );
      }
      break;

    // Atomic evolution events
    case "taxonomy_classified":
      if (ev.evolution_mode === "atomic") {
        next.isAtomic = true;
      }
      break;

    case "decomposition_complete":
      next.isAtomic = true;
      if (ev.dimensions && Array.isArray(ev.dimensions)) {
        next.atomicDimensions = ev.dimensions.map((d) => ({
          dimension: d.name,
          tier: d.tier,
          status: "pending" as const,
        }));
      }
      break;

    case "variant_evolution_started":
      next.isAtomic = true;
      next.activeDimension = ev.dimension;
      // Reset competitors for this new dimension
      next.competitors = [];
      next.finishedCompetitors = 0;
      next.currentJudgingLayer = 0;
      next.generations = [];
      // Update existing dimension or add it if we missed the decomposition event
      if (ev.dimension) {
        const exists = next.atomicDimensions.some((d) => d.dimension === ev.dimension);
        if (exists) {
          next.atomicDimensions = next.atomicDimensions.map((d) =>
            d.dimension === ev.dimension ? { ...d, status: "running" as const } : d,
          );
        } else {
          next.atomicDimensions = [
            ...next.atomicDimensions,
            { dimension: ev.dimension, tier: ev.tier ?? "capability", status: "running" as const },
          ];
        }
      }
      break;

    case "variant_evolution_complete": {
      const completeStatus = (ev.status === "complete" ? "complete" : "failed") as "complete" | "failed";
      const exists = next.atomicDimensions.some((d) => d.dimension === ev.dimension);
      if (exists) {
        next.atomicDimensions = next.atomicDimensions.map((d) =>
          d.dimension === ev.dimension
            ? { ...d, status: completeStatus, fitness: ev.best_fitness }
            : d,
        );
      } else if (ev.dimension) {
        next.atomicDimensions = [
          ...next.atomicDimensions,
          { dimension: ev.dimension, tier: ev.tier ?? "capability", status: completeStatus, fitness: ev.best_fitness },
        ];
      }
      next.activeDimension = undefined;
      break;
    }

    default:
      break;
  }

  return next;
}

// ----------------------------------------------------------------------------
// Derive PhaseState[] for the sidebar process flow diagram
// ----------------------------------------------------------------------------

/**
 * Map the current socket state to an ordered list of PhaseState objects.
 *
 * The phases reflect the per-generation cycle SkillForge runs:
 *   1. design_challenges (gen 0 only — finalized after the very first event)
 *   2. spawn_or_breed    (Spawner on gen 0, Breeder on gen 1+)
 *   3. compete           (run all competitors)
 *   4. judge             (L1-L5 pipeline)
 *   5. score_select      (Pareto + best skill selection for this gen)
 *   6. finalize          (only highlighted on the last generation, becomes
 *                         "evolution complete" once isComplete is true)
 *
 * The phase corresponding to the most recent event is "running".
 * Anything before it is "complete". Anything after is "pending".
 */
export function derivePhases(
  state: EvolutionSocketState,
  expectedCompetitors: number,
): PhaseState[] {
  const events = state.events;
  const has = (name: string) =>
    events.some((e) => e.event === name);

  // Default labels
  const labels: Record<PhaseState["id"], string> = {
    design_challenges: "Design Challenges",
    spawn_or_breed: state.currentGeneration === 0 ? "Spawn Variants" : "Breed Next Gen",
    compete: "Compete on Challenge",
    judge: "Composite Score",
    score_select: "Pick Winner",
    finalize: "Assemble Composite",
  };

  const phases: PhaseState[] = (
    [
      "design_challenges",
      "spawn_or_breed",
      "compete",
      "judge",
      "score_select",
      "finalize",
    ] as PhaseState["id"][]
  ).map((id) => ({ id, label: labels[id], status: "pending" as const }));

  if (state.isFailed) {
    // Mark whatever phase the run was in as failed; mark prior as complete.
    const lastRunningIdx = phases.findIndex((p) => p.status === "running");
    if (lastRunningIdx >= 0) phases[lastRunningIdx].status = "failed";
    else phases[0].status = "failed";
    return phases;
  }

  if (state.isComplete) {
    return phases.map((p) => ({ ...p, status: "complete" as const }));
  }

  // --- Walk forward through phases based on what events have fired ---

  // Phase 1: design_challenges
  if (has("challenge_design_started") || has("challenge_designed")) {
    if (has("generation_started")) {
      phases[0].status = "complete";
    } else {
      phases[0].status = "running";
      const designed = events.filter((e) => e.event === "challenge_designed").length;
      phases[0].detail = designed > 0 ? `${designed} designed` : "designing...";
      return phases;
    }
  }

  // Phase 2: spawn_or_breed
  if (has("generation_started")) {
    if (has("competitor_started") || has("breeding_started")) {
      // For gen 0, breeding_started never fires, so just check competitor_started
      if (has("competitor_started")) {
        phases[1].status = "complete";
      } else if (state.currentGeneration > 0 && has("breeding_started")) {
        phases[1].status = "running";
        phases[1].detail = state.latestBreedingReport ? "report ready" : "thinking...";
        return phases;
      }
    } else {
      phases[1].status = "running";
      phases[1].detail =
        state.currentGeneration === 0 ? "generating skills..." : "breeding...";
      return phases;
    }
  }

  // Phase 3: compete
  if (has("competitor_started")) {
    if (has("judging_started")) {
      phases[2].status = "complete";
    } else {
      phases[2].status = "running";
      const expected = Math.max(expectedCompetitors, state.competitors.length);
      const finished = state.finishedCompetitors;
      phases[2].detail =
        expected > 0 ? `${finished} of ${expected}` : `${finished} done`;
      return phases;
    }
  }

  // Phase 4: judge
  if (has("judging_started")) {
    if (has("scores_published")) {
      phases[3].status = "complete";
    } else {
      phases[3].status = "running";
      phases[3].detail = "L1 → L5";
      return phases;
    }
  }

  // Phase 5: score_select
  if (has("scores_published")) {
    if (has("generation_complete")) {
      phases[4].status = "complete";
    } else {
      phases[4].status = "running";
      const lastGen = state.generations.at(-1);
      phases[4].detail = lastGen?.best_fitness != null
        ? `best ${lastGen.best_fitness.toFixed(2)}`
        : undefined;
      return phases;
    }
  }

  // Phase 6: finalize / next-gen breeding
  if (has("generation_complete")) {
    phases[5].status = "running";
    phases[5].detail = "next generation...";
  }

  return phases;
}


function upsertGeneration(
  list: GenerationStats[],
  patch: Partial<GenerationStats> & { number: number },
): GenerationStats[] {
  const idx = list.findIndex((g) => g.number === patch.number);
  if (idx === -1) {
    return [...list, { ...patch, status: patch.status ?? "running" }];
  }
  const next = [...list];
  next[idx] = { ...next[idx], ...patch };
  return next;
}

function upsertCompetitor(
  list: CompetitorView[],
  patch: CompetitorView,
): CompetitorView[] {
  const idx = list.findIndex(
    (c) =>
      c.competitorId === patch.competitorId &&
      c.skillId === patch.skillId &&
      c.challengeId === patch.challengeId,
  );
  // Strip undefined values from patch so spread doesn't overwrite existing data
  const cleanPatch: Partial<CompetitorView> = {};
  for (const [k, v] of Object.entries(patch)) {
    if (v !== undefined) {
      (cleanPatch as Record<string, unknown>)[k] = v;
    }
  }
  if (idx === -1) {
    return [...list, { ...patch }];
  }
  const next = [...list];
  next[idx] = { ...next[idx], ...cleanPatch };
  return next;
}
