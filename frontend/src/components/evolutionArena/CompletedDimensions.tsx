/**
 * Summary card listing each completed dimension's fitness score + an
 * overall average at the bottom.
 */
import type { DimensionStatus } from "@/types";

interface CompletedDimensionsProps {
  completed: DimensionStatus[];
}

export default function CompletedDimensions({ completed }: CompletedDimensionsProps) {
  if (completed.length === 0) return null;

  const scored = completed.filter((d) => d.fitness_score != null);
  const avg =
    scored.length > 0
      ? scored.reduce((sum, d) => sum + (d.fitness_score ?? 0), 0) / scored.length
      : 0;

  return (
    <div className="rounded-xl bg-surface-container-low p-5">
      <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
        Completed Dimensions
      </p>
      <div className="mt-3 space-y-1.5">
        {completed.map((d) => (
          <div key={d.id} className="flex items-center justify-between">
            <span className="truncate text-xs capitalize text-on-surface-dim">
              {d.dimension.replace(/-/g, " ")}
            </span>
            <span className="ml-2 shrink-0 font-mono text-[0.625rem] text-tertiary">
              {d.fitness_score?.toFixed(2) ?? "—"}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-3 border-t border-outline-variant pt-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
            Avg Fitness
          </span>
          <span className="font-mono text-sm text-tertiary">{avg.toFixed(3)}</span>
        </div>
      </div>
    </div>
  );
}
