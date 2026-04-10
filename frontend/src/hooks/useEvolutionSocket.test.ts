import { describe, it, expect } from "vitest";

import { applyEvent } from "./useEvolutionSocket";
import type { EvolutionSocketState } from "./useEvolutionSocket";
import type { EvolutionEvent } from "../types";

/** Helper to create a minimal initial state. */
function makeState(
  overrides?: Partial<EvolutionSocketState>,
): EvolutionSocketState {
  return {
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
    ...overrides,
  };
}

describe("applyEvent", () => {
  it("generation_started updates currentGeneration, resets competitors and currentJudgingLayer", () => {
    const before = makeState({
      currentGeneration: 0,
      competitors: [
        { competitorId: 0, skillId: "sk-old", state: "done" },
      ],
      currentJudgingLayer: 3,
      finishedCompetitors: 5,
    });
    const ev: EvolutionEvent = { event: "generation_started", generation: 1 };
    const after = applyEvent(before, ev);

    expect(after.currentGeneration).toBe(1);
    expect(after.competitors).toEqual([]);
    expect(after.currentJudgingLayer).toBe(0);
    expect(after.finishedCompetitors).toBe(0);
  });

  it("competitor_started adds a competitor with state 'writing'", () => {
    const before = makeState();
    const ev: EvolutionEvent = {
      event: "competitor_started",
      competitor: 0,
      skill_id: "sk-1",
      challenge_id: "ch-a",
    };
    const after = applyEvent(before, ev);

    expect(after.competitors).toHaveLength(1);
    expect(after.competitors[0]).toEqual({
      competitorId: 0,
      skillId: "sk-1",
      challengeId: "ch-a",
      state: "writing",
    });
  });

  it("competitor_started with same (competitorId, skillId) but different challengeId creates TWO entries", () => {
    const before = makeState();
    const ev1: EvolutionEvent = {
      event: "competitor_started",
      competitor: 0,
      skill_id: "sk-1",
      challenge_id: "ch-a",
    };
    const ev2: EvolutionEvent = {
      event: "competitor_started",
      competitor: 0,
      skill_id: "sk-1",
      challenge_id: "ch-b",
    };
    const after = applyEvent(applyEvent(before, ev1), ev2);

    expect(after.competitors).toHaveLength(2);
    expect(after.competitors[0].challengeId).toBe("ch-a");
    expect(after.competitors[1].challengeId).toBe("ch-b");
  });

  it("competitor_finished updates state to 'done' and increments finishedCompetitors", () => {
    const before = makeState({
      competitors: [
        { competitorId: 0, skillId: "sk-1", challengeId: "ch-a", state: "writing" },
      ],
      finishedCompetitors: 0,
    });
    const ev: EvolutionEvent = {
      event: "competitor_finished",
      competitor: 0,
      skill_id: "sk-1",
      challenge_id: "ch-a",
    };
    const after = applyEvent(before, ev);

    expect(after.competitors[0].state).toBe("done");
    expect(after.finishedCompetitors).toBe(1);
  });

  it("evolution_complete sets isComplete=true and stores bestSkillId", () => {
    const before = makeState();
    const ev: EvolutionEvent = {
      event: "evolution_complete",
      best_skill_id: "sk-winner",
      total_cost_usd: 4.5,
    };
    const after = applyEvent(before, ev);

    expect(after.isComplete).toBe(true);
    expect(after.bestSkillId).toBe("sk-winner");
    expect(after.totalCostUsd).toBe(4.5);
  });

  it("run_failed sets isFailed=true and stores failureReason", () => {
    const before = makeState();
    const ev: EvolutionEvent = { event: "run_failed", reason: "out of budget" };
    const after = applyEvent(before, ev);

    expect(after.isFailed).toBe(true);
    expect(after.failureReason).toBe("out of budget");
  });

  it("run_cancelled sets isFailed=true with reason 'cancelled by user'", () => {
    const before = makeState();
    const ev: EvolutionEvent = { event: "run_cancelled" };
    const after = applyEvent(before, ev);

    expect(after.isFailed).toBe(true);
    expect(after.failureReason).toBe("cancelled by user");
  });

  it("judging_layer_complete updates currentJudgingLayer", () => {
    const before = makeState({ currentJudgingLayer: 0 });
    const ev: EvolutionEvent = {
      event: "judging_layer_complete",
      layer: 3,
    };
    const after = applyEvent(before, ev);

    expect(after.currentJudgingLayer).toBe(3);
  });

  it("cost_update updates totalCostUsd", () => {
    const before = makeState({ totalCostUsd: 1.0 });
    const ev: EvolutionEvent = {
      event: "cost_update",
      total_cost_usd: 2.75,
    };
    const after = applyEvent(before, ev);

    expect(after.totalCostUsd).toBe(2.75);
  });

  it("scores_published updates generation with fitness data", () => {
    const before = makeState({
      currentGeneration: 0,
      generations: [{ number: 0, status: "judging" }],
    });
    const ev: EvolutionEvent = {
      event: "scores_published",
      generation: 0,
      best_fitness: 0.85,
      avg_fitness: 0.7,
      pareto_front: ["sk-a", "sk-b"],
    };
    const after = applyEvent(before, ev);

    const gen = after.generations.find((g) => g.number === 0);
    expect(gen).toBeDefined();
    expect(gen!.best_fitness).toBe(0.85);
    expect(gen!.avg_fitness).toBe(0.7);
    expect(gen!.pareto_front).toEqual(["sk-a", "sk-b"]);
    expect(gen!.status).toBe("complete");
  });

  it("every event updates lastEventAt to a non-zero value", () => {
    const eventNames: EvolutionEvent["event"][] = [
      "generation_started",
      "competitor_started",
      "competitor_finished",
      "judging_started",
      "judging_layer_complete",
      "scores_published",
      "cost_update",
      "breeding_started",
      "breeding_report",
      "generation_complete",
      "evolution_complete",
      "run_failed",
      "run_cancelled",
    ];

    for (const name of eventNames) {
      const before = makeState({ lastEventAt: 0 });
      const ev: EvolutionEvent = { event: name };
      const after = applyEvent(before, ev);
      expect(after.lastEventAt).toBeGreaterThan(0);
    }
  });
});
