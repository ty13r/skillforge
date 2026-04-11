import { useMemo } from "react";

import type { Variant } from "../types";

interface PerDimensionFitnessBarProps {
  variants: Variant[];
  seedWinnerDimensions?: Set<string>;
}

/**
 * Horizontal bar chart replacing the Growth Curve for atomic-mode runs.
 *
 * Each bar is a dimension. Bar length = winning variant's fitness_score.
 * Color by tier (foundation vs capability). Optional "seed-winner" badge
 * for dimensions where the pre-existing seed beat the spawned alternative —
 * those are interesting because they mean the Spawner's proposal was worse
 * than the baseline. CSS flexbox; no Recharts.
 */
export default function PerDimensionFitnessBar({
  variants,
  seedWinnerDimensions,
}: PerDimensionFitnessBarProps) {
  const rows = useMemo(() => {
    return variants
      .slice()
      .sort((a, b) => {
        // Foundation first, then by fitness DESC within each tier.
        if (a.tier !== b.tier) return a.tier === "foundation" ? -1 : 1;
        return b.fitness_score - a.fitness_score;
      });
  }, [variants]);

  if (rows.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-xs text-on-surface-dim">
        No variants to display.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {rows.map((v) => {
        const pct = Math.max(0, Math.min(1, v.fitness_score)) * 100;
        const isFoundation = v.tier === "foundation";
        const isSeedWinner = seedWinnerDimensions?.has(v.dimension);

        return (
          <div key={v.id} className="flex items-center gap-3">
            <div className="w-44 shrink-0 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
              {v.dimension}
            </div>
            <div className="relative flex-1 overflow-hidden rounded bg-surface-container-low">
              <div
                className={`h-5 transition-all ${
                  isFoundation
                    ? "bg-tertiary/60"
                    : "bg-primary/60"
                }`}
                style={{ width: `${pct}%` }}
              />
              <div className="absolute inset-0 flex items-center px-2 font-mono text-[0.625rem] text-on-surface">
                {v.fitness_score.toFixed(3)}
              </div>
            </div>
            <div className="flex w-24 shrink-0 items-center gap-1">
              {isFoundation && (
                <span className="rounded bg-tertiary/10 px-1.5 py-0.5 font-mono text-[0.5rem] uppercase tracking-wider text-tertiary">
                  FND
                </span>
              )}
              {isSeedWinner ? (
                <span
                  title="Seed variant beat the spawned alternative"
                  className="rounded bg-surface-container-high px-1.5 py-0.5 font-mono text-[0.5rem] uppercase tracking-wider text-on-surface-dim"
                >
                  SEED
                </span>
              ) : (
                <span
                  title="Spawned variant beat the seed"
                  className="rounded bg-primary/10 px-1.5 py-0.5 font-mono text-[0.5rem] uppercase tracking-wider text-primary"
                >
                  SPAWN
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
