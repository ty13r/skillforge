import { useEffect, useRef, useState } from "react";

import type {
  CompetitorView,
  EvolutionEvent,
  GenerationStats,
} from "../types";

export type ConnectionStatus = "connecting" | "open" | "closed" | "error";

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

function applyEvent(
  state: EvolutionSocketState,
  ev: EvolutionEvent,
): EvolutionSocketState {
  const events = [...state.events, ev];
  let next = { ...state, events };

  switch (ev.event) {
    case "generation_started":
      next.currentGeneration = ev.generation ?? next.currentGeneration;
      next.generations = upsertGeneration(next.generations, {
        number: ev.generation ?? 0,
        status: "running",
      });
      next.competitors = []; // reset for new generation
      break;

    case "competitor_started":
      next.competitors = upsertCompetitor(next.competitors, {
        competitorId: ev.competitor ?? 0,
        skillId: ev.skill_id ?? "",
        challengeId: ev.challenge_id,
        state: "writing",
      });
      break;

    case "competitor_finished":
      next.competitors = upsertCompetitor(next.competitors, {
        competitorId: ev.competitor ?? 0,
        skillId: ev.skill_id ?? "",
        challengeId: ev.challenge_id,
        state: "done",
      });
      break;

    case "judging_started":
      next.generations = upsertGeneration(next.generations, {
        number: ev.generation ?? next.currentGeneration,
        status: "judging",
      });
      break;

    case "scores_published":
      next.generations = upsertGeneration(next.generations, {
        number: ev.generation ?? next.currentGeneration,
        best_fitness: ev.best_fitness,
        avg_fitness: ev.avg_fitness,
        pareto_front: ev.pareto_front,
        status: "complete",
      });
      break;

    case "cost_update":
      next.totalCostUsd = ev.total_cost_usd ?? next.totalCostUsd;
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

    default:
      break;
  }

  return next;
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
      c.skillId === patch.skillId,
  );
  if (idx === -1) {
    return [...list, patch];
  }
  const next = [...list];
  next[idx] = { ...next[idx], ...patch };
  return next;
}
