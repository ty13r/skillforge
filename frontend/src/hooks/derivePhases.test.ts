import { describe, expect, it } from "vitest";

import { derivePhases } from "./useEvolutionSocket";
import type { EvolutionSocketState } from "./useEvolutionSocket";
import type { EvolutionEvent } from "../types";

function makeState(
  events: EvolutionEvent[],
  overrides: Partial<EvolutionSocketState> = {},
): EvolutionSocketState {
  return {
    events,
    status: "open",
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
    ...overrides,
  };
}

describe("derivePhases", () => {
  it("returns all phases pending when no events have fired", () => {
    const phases = derivePhases(makeState([]), 15);
    expect(phases).toHaveLength(6);
    expect(phases.every((p) => p.status === "pending")).toBe(true);
    expect(phases.map((p) => p.id)).toEqual([
      "design_challenges",
      "spawn_or_breed",
      "compete",
      "judge",
      "score_select",
      "finalize",
    ]);
  });

  it("marks design_challenges running when challenge_design_started fires", () => {
    const phases = derivePhases(
      makeState([{ event: "challenge_design_started" }]),
      15,
    );
    expect(phases[0].status).toBe("running");
    expect(phases[1].status).toBe("pending");
  });

  it("counts designed challenges in the detail line", () => {
    const phases = derivePhases(
      makeState([
        { event: "challenge_design_started" },
        { event: "challenge_designed", challenge_id: "ch-a" },
        { event: "challenge_designed", challenge_id: "ch-b" },
      ]),
      15,
    );
    expect(phases[0].status).toBe("running");
    expect(phases[0].detail).toBe("2 designed");
  });

  it("marks design_challenges complete and spawn_or_breed running after generation_started", () => {
    const phases = derivePhases(
      makeState(
        [
          { event: "challenge_design_started" },
          { event: "challenge_designed", challenge_id: "ch-a" },
          { event: "challenge_designed", challenge_id: "ch-b" },
          { event: "challenge_designed", challenge_id: "ch-c" },
          { event: "generation_started", generation: 0 },
        ],
        { currentGeneration: 0 },
      ),
      15,
    );
    expect(phases[0].status).toBe("complete");
    expect(phases[1].status).toBe("running");
    expect(phases[1].label).toBe("Spawn Variants");
    expect(phases[1].detail).toContain("generating");
  });

  it("uses 'Breed Next Gen' label for non-zero generation", () => {
    const phases = derivePhases(
      makeState(
        [
          { event: "challenge_designed", challenge_id: "ch-a" },
          { event: "generation_started", generation: 1 },
          { event: "breeding_started", generation: 1 },
        ],
        { currentGeneration: 1 },
      ),
      15,
    );
    expect(phases[1].label).toBe("Breed Next Gen");
    expect(phases[1].status).toBe("running");
  });

  it("transitions spawn_or_breed -> compete when first competitor starts", () => {
    const phases = derivePhases(
      makeState(
        [
          { event: "challenge_designed", challenge_id: "ch-a" },
          { event: "generation_started", generation: 0 },
          {
            event: "competitor_started",
            competitor: 0,
            skill_id: "sk-1",
            challenge_id: "ch-a",
          },
        ],
        {
          currentGeneration: 0,
          finishedCompetitors: 0,
          competitors: [
            {
              competitorId: 0,
              skillId: "sk-1",
              challengeId: "ch-a",
              state: "writing",
            },
          ],
        },
      ),
      15,
    );
    expect(phases[1].status).toBe("complete");
    expect(phases[2].status).toBe("running");
    expect(phases[2].detail).toBe("0 of 15");
  });

  it("counts finished competitors in the compete detail", () => {
    const phases = derivePhases(
      makeState(
        [
          { event: "challenge_designed", challenge_id: "ch-a" },
          { event: "generation_started", generation: 0 },
          { event: "competitor_started", competitor: 0 },
          { event: "competitor_finished", competitor: 0 },
          { event: "competitor_started", competitor: 1 },
        ],
        { finishedCompetitors: 1, currentGeneration: 0 },
      ),
      15,
    );
    expect(phases[2].status).toBe("running");
    expect(phases[2].detail).toBe("1 of 15");
  });

  it("transitions compete -> judge when judging_started fires", () => {
    const phases = derivePhases(
      makeState(
        [
          { event: "challenge_designed", challenge_id: "ch-a" },
          { event: "generation_started", generation: 0 },
          { event: "competitor_started", competitor: 0 },
          { event: "judging_started", generation: 0 },
        ],
        { currentGeneration: 0 },
      ),
      15,
    );
    expect(phases[2].status).toBe("complete");
    expect(phases[3].status).toBe("running");
    expect(phases[3].detail).toBe("L1 → L5");
  });

  it("transitions judge -> score_select when scores_published fires", () => {
    const phases = derivePhases(
      makeState(
        [
          { event: "challenge_designed", challenge_id: "ch-a" },
          { event: "generation_started", generation: 0 },
          { event: "competitor_started", competitor: 0 },
          { event: "judging_started", generation: 0 },
          { event: "scores_published", best_fitness: 0.65, generation: 0 },
        ],
        {
          currentGeneration: 0,
          generations: [
            {
              number: 0,
              best_fitness: 0.65,
              avg_fitness: 0.6,
              status: "complete",
            },
          ],
        },
      ),
      15,
    );
    expect(phases[3].status).toBe("complete");
    expect(phases[4].status).toBe("running");
    expect(phases[4].detail).toBe("best 0.65");
  });

  it("transitions score_select -> finalize when generation_complete fires", () => {
    const phases = derivePhases(
      makeState(
        [
          { event: "challenge_designed", challenge_id: "ch-a" },
          { event: "generation_started", generation: 0 },
          { event: "competitor_started", competitor: 0 },
          { event: "judging_started", generation: 0 },
          { event: "scores_published", generation: 0 },
          { event: "generation_complete", generation: 0 },
        ],
        { currentGeneration: 0 },
      ),
      15,
    );
    expect(phases[4].status).toBe("complete");
    expect(phases[5].status).toBe("running");
  });

  it("marks all phases complete when isComplete=true", () => {
    const phases = derivePhases(
      makeState([{ event: "evolution_complete" }], { isComplete: true }),
      15,
    );
    expect(phases.every((p) => p.status === "complete")).toBe(true);
  });

  it("marks the active phase failed when isFailed=true", () => {
    const phases = derivePhases(
      makeState(
        [
          { event: "challenge_designed", challenge_id: "ch-a" },
          { event: "generation_started", generation: 0 },
          { event: "competitor_started", competitor: 0 },
          { event: "run_failed", reason: "boom" },
        ],
        { isFailed: true, failureReason: "boom", currentGeneration: 0 },
      ),
      15,
    );
    // The last "running" phase before failure was "compete"
    const failedPhases = phases.filter((p) => p.status === "failed");
    expect(failedPhases.length).toBeGreaterThan(0);
  });
});
