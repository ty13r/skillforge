import { useMemo } from "react";
import { Link } from "react-router-dom";

import type { RunReportVariantEvolution, Variant } from "../types";

interface RichVariantBreakdownProps {
  runId: string;
  variants: Variant[];
  variantEvolutions: RunReportVariantEvolution[];
  seedWinnerDimensions?: Set<string>;
}

/**
 * Always-expanded per-dimension variant breakdown for atomic-mode runs.
 *
 * Each row shows:
 *   - Dimension name + tier badge
 *   - Winning variant's fitness_score
 *   - Seed-winner or Spawn-winner badge
 *   - Challenge ID the dimension was tested against (from the vevo)
 *   - Compare link to the SkillDiffViewer for that dimension
 *
 * No swap dropdown, no re-evolve button — those belong in a separate UI.
 * This component is read-only.
 */
export default function RichVariantBreakdown({
  runId,
  variants,
  variantEvolutions,
  seedWinnerDimensions,
}: RichVariantBreakdownProps) {
  const vevoByDimension = useMemo(() => {
    const map = new Map<string, RunReportVariantEvolution>();
    for (const ve of variantEvolutions) {
      map.set(ve.dimension, ve);
    }
    return map;
  }, [variantEvolutions]);

  const foundationVariants = variants.filter((v) => v.tier === "foundation");
  const capabilityVariants = variants
    .filter((v) => v.tier === "capability")
    .sort((a, b) => b.fitness_score - a.fitness_score);

  const renderRow = (v: Variant) => {
    const vevo = vevoByDimension.get(v.dimension);
    const isSeedWinner = seedWinnerDimensions?.has(v.dimension);
    const isFoundation = v.tier === "foundation";

    return (
      <div
        key={v.id}
        className="rounded-lg border border-outline-variant bg-surface-container-low p-4"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <p className="font-mono text-sm font-bold text-on-surface">{v.dimension}</p>
              {isFoundation && (
                <span className="rounded bg-tertiary/10 px-1.5 py-0.5 font-mono text-[0.5625rem] uppercase tracking-wider text-tertiary">
                  Foundation
                </span>
              )}
              {!isFoundation && (
                <span className="rounded bg-primary/10 px-1.5 py-0.5 font-mono text-[0.5625rem] uppercase tracking-wider text-primary">
                  Capability
                </span>
              )}
              {isSeedWinner ? (
                <span className="rounded bg-surface-container-high px-1.5 py-0.5 font-mono text-[0.5625rem] uppercase tracking-wider text-on-surface-dim">
                  Seed Winner
                </span>
              ) : (
                <span className="rounded bg-primary/10 px-1.5 py-0.5 font-mono text-[0.5625rem] uppercase tracking-wider text-primary">
                  Spawn Winner
                </span>
              )}
            </div>
            {vevo && (
              <p className="mt-2 font-mono text-[0.6875rem] text-on-surface-dim">
                Tested against: <span className="text-on-surface">{vevo.challenge_id ?? "—"}</span>
                {" · Status: "}
                <span className="text-on-surface">{vevo.status}</span>
              </p>
            )}
          </div>
          <div className="text-right">
            <p className="font-display text-2xl tracking-tight text-tertiary">
              {v.fitness_score.toFixed(3)}
            </p>
            <p className="font-mono text-[0.5625rem] uppercase tracking-wider text-on-surface-dim">
              Fitness
            </p>
          </div>
        </div>
        <div className="mt-3 flex gap-2">
          <Link
            to={`/runs/${runId}/skills/${v.genome_id}`}
            className="rounded bg-surface-container-high px-2.5 py-1 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface transition-colors hover:bg-surface-container-highest"
          >
            View SKILL.md
          </Link>
          <Link
            to={`/runs/${runId}/diff`}
            className="rounded bg-surface-container-high px-2.5 py-1 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface transition-colors hover:bg-surface-container-highest"
          >
            Compare Lineage
          </Link>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {foundationVariants.length > 0 && (
        <div>
          <p className="mb-3 font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Foundation (1)
          </p>
          <div className="space-y-3">{foundationVariants.map(renderRow)}</div>
        </div>
      )}
      {capabilityVariants.length > 0 && (
        <div>
          <p className="mb-3 font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Capabilities ({capabilityVariants.length})
          </p>
          <div className="space-y-3">{capabilityVariants.map(renderRow)}</div>
        </div>
      )}
    </div>
  );
}
