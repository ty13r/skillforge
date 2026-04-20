/**
 * Pure cost + duration estimator for an evolution run.
 *
 * Calibrated from observed live runs:
 *   • 5 pop × 3 gen × 3 challenges = 53 min, ~$7.50
 *   • 2 pop × 1 gen × 1 challenge  = 9 min, ~$2.00
 *
 * Backend hardcodes num_challenges=3. Competitors currently run
 * sequentially (COMPETITOR_CONCURRENCY=1) due to the Agent SDK
 * subprocess race; if that changes these estimates need recalibration.
 */

export interface CostEstimateInput {
  populationSize: number;
  numGenerations: number;
}

export interface CostEstimate {
  competitorRuns: number;
  challengesPerGen: number;
  minutes: number;
  usd: number;
  /** Human-readable time (">=90 min shows hours, otherwise minutes"). */
  timeLabel: string;
}

const CHALLENGES_PER_GEN = 3;
const MIN_PER_COMPETITOR_RUN = 0.95;
const USD_PER_COMPETITOR_RUN = 0.11;
const SETUP_MIN = 5; // challenge design + spawn startup
const BREEDING_MIN_PER_GEN = 2;
const SETUP_USD = 1.0;
const BREEDING_USD_PER_GEN = 0.5;

export function estimateCost({ populationSize, numGenerations }: CostEstimateInput): CostEstimate {
  const competitorRuns = populationSize * numGenerations * CHALLENGES_PER_GEN;
  const minutes = Math.round(
    competitorRuns * MIN_PER_COMPETITOR_RUN + SETUP_MIN + numGenerations * BREEDING_MIN_PER_GEN,
  );
  const usd =
    competitorRuns * USD_PER_COMPETITOR_RUN + SETUP_USD + numGenerations * BREEDING_USD_PER_GEN;
  const timeLabel = minutes >= 90 ? `~${(minutes / 60).toFixed(1)} hrs` : `~${minutes} min`;
  return {
    competitorRuns,
    challengesPerGen: CHALLENGES_PER_GEN,
    minutes,
    usd,
    timeLabel,
  };
}
