/**
 * Top-of-arena header: status badge + title + elapsed timer + cost badge +
 * Cancel button. Pure presentational — cancel action is lifted via callback.
 */
import StatusGlow from "../StatusGlow";

interface ArenaHeaderProps {
  specialization: string;
  isFailed: boolean;
  isComplete: boolean;
  activeDimension: string | null;
  completedDims: number;
  totalDims: number;
  elapsed: number;
  totalCostUsd: number;
  budgetCap: number;
  onCancel: () => void;
}

export default function ArenaHeader({
  specialization,
  isFailed,
  isComplete,
  activeDimension,
  completedDims,
  totalDims,
  elapsed,
  totalCostUsd,
  budgetCap,
  onCancel,
}: ArenaHeaderProps) {
  const elapsedFmt = `${Math.floor(elapsed / 60)
    .toString()
    .padStart(2, "0")}:${(elapsed % 60).toString().padStart(2, "0")}`;

  return (
    <div className="flex items-start justify-between gap-6">
      <div className="min-w-0 flex-1">
        <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-primary">
          {activeDimension
            ? `Dimension ${completedDims + 1} of ${totalDims} · ${activeDimension.replace(/-/g, " ")}`
            : `Evolving ${totalDims} dimensions`}
        </p>
        <h1 className="mt-2 font-display text-3xl leading-tight tracking-tight md:text-4xl">
          {specialization || "Atomic Evolution"}
        </h1>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 font-mono text-[0.625rem] uppercase tracking-wider ${
              isFailed ? "bg-error/15 text-error" : "bg-tertiary/15 text-tertiary"
            }`}
          >
            <StatusGlow variant={isFailed ? "error" : "success"} />
            {isFailed ? "FAILED" : "RUNNING"}
          </span>
          <span className="font-mono text-[0.6875rem] text-on-surface-dim">
            {completedDims}/{totalDims} dimensions
          </span>
        </div>
      </div>
      <div className="flex flex-col items-end gap-3">
        <div className="text-right">
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Elapsed
          </p>
          <p className="font-display text-2xl tracking-tight">{elapsedFmt}</p>
          <p className="mt-2 font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Budget Used
          </p>
          <p className="font-mono text-sm text-tertiary">
            ${totalCostUsd.toFixed(2)} / ${budgetCap.toFixed(2)}
          </p>
        </div>
        {!isComplete && !isFailed && (
          <button
            onClick={onCancel}
            className="rounded-lg border border-error/40 bg-surface-container-lowest px-3 py-1.5 text-xs font-medium text-error transition-colors hover:bg-error/10"
          >
            Cancel Run
          </button>
        )}
      </div>
    </div>
  );
}
