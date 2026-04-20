/**
 * Footer card showing est. time / cost / competitor-runs plus the
 * Start-Evolution submit button. Pure presentational — receives an
 * already-computed CostEstimate from the caller.
 */
import PrimaryButton from "../PrimaryButton";

import type { CostEstimate } from "./estimateCost";

interface RunEstimateCardProps {
  estimate: CostEstimate;
  budget: number;
  populationSize: number;
  numGenerations: number;
  submitting: boolean;
  onSubmit: () => void;
}

export default function RunEstimateCard({
  estimate,
  budget,
  populationSize,
  numGenerations,
  submitting,
  onSubmit,
}: RunEstimateCardProps) {
  const overBudget = estimate.usd > budget;

  return (
    <div className="mt-8 rounded-xl border border-outline-variant bg-surface-container-low p-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex gap-6">
          <div>
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
              Est. Compute Time
            </p>
            <p className="font-mono text-sm text-on-surface">{estimate.timeLabel}</p>
          </div>
          <div>
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
              Est. Compute Cost
            </p>
            <p className={`font-mono text-sm ${overBudget ? "text-error" : "text-on-surface"}`}>
              ~${estimate.usd.toFixed(2)}
            </p>
          </div>
          <div>
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
              Competitor Runs
            </p>
            <p className="font-mono text-sm text-on-surface">
              {estimate.competitorRuns} ({populationSize}×{numGenerations}×
              {estimate.challengesPerGen})
            </p>
          </div>
        </div>
        <PrimaryButton onClick={onSubmit} disabled={submitting}>
          {submitting ? "Starting..." : "Start Evolution →"}
        </PrimaryButton>
      </div>
      {overBudget && (
        <p className="mt-3 font-mono text-[0.6875rem] text-error">
          ⚠ Estimated cost exceeds your ${budget} budget cap. The run will abort when the cap is hit
          — increase the cap or reduce population/generations.
        </p>
      )}
    </div>
  );
}
