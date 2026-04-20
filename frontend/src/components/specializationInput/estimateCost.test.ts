import { describe, expect, it } from "vitest";

import { estimateCost } from "./estimateCost";

describe("estimateCost", () => {
  it("matches the 5 pop × 3 gen calibration point (~53min, ~$7.50)", () => {
    const e = estimateCost({ populationSize: 5, numGenerations: 3 });
    expect(e.competitorRuns).toBe(45);
    expect(e.minutes).toBeGreaterThanOrEqual(48);
    expect(e.minutes).toBeLessThanOrEqual(58);
    expect(e.usd).toBeGreaterThanOrEqual(6.5);
    expect(e.usd).toBeLessThanOrEqual(8.5);
  });

  it("matches the 2 pop × 1 gen calibration point (~9min, ~$2.00)", () => {
    const e = estimateCost({ populationSize: 2, numGenerations: 1 });
    expect(e.competitorRuns).toBe(6);
    expect(e.minutes).toBeGreaterThanOrEqual(7);
    expect(e.minutes).toBeLessThanOrEqual(15);
    expect(e.usd).toBeGreaterThanOrEqual(1.5);
    expect(e.usd).toBeLessThanOrEqual(3.0);
  });

  it("labels as hours when runtime ≥90 minutes", () => {
    const e = estimateCost({ populationSize: 20, numGenerations: 10 });
    expect(e.timeLabel).toMatch(/hrs$/);
  });

  it("labels as minutes when runtime <90 minutes", () => {
    const e = estimateCost({ populationSize: 2, numGenerations: 1 });
    expect(e.timeLabel).toMatch(/min$/);
  });
});
