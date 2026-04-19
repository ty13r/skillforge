import { Link } from "react-router-dom";

import type { DimensionStatus } from "../types";

interface AtomicSidebarProps {
  runId: string;
  dimensions: DimensionStatus[];
  activeDimension?: string | null;
}

const STATUS_STYLES: Record<DimensionStatus["status"], { dot: string; label: string }> = {
  pending: {
    dot: "bg-surface-container-high",
    label: "text-on-surface-dim",
  },
  running: {
    dot: "bg-primary animate-pulse",
    label: "text-on-surface font-medium",
  },
  complete: {
    dot: "bg-tertiary",
    label: "text-on-surface-dim",
  },
  failed: {
    dot: "bg-error",
    label: "text-error",
  },
};

export default function AtomicSidebar({ runId, dimensions, activeDimension }: AtomicSidebarProps) {
  const completed = dimensions.filter((d) => d.status === "complete").length;
  const total = dimensions.length;
  const foundations = dimensions.filter((d) => d.tier === "foundation");
  const capabilities = dimensions.filter((d) => d.tier === "capability");

  return (
    <aside className="w-72 shrink-0 overflow-y-auto bg-surface-container py-6">
      {/* Run header */}
      <div className="mx-4 rounded-xl bg-surface-container-low p-4">
        <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          Atomic Evolution
        </p>
        <p className="mt-1 font-mono text-[0.6875rem] text-on-surface-dim">{runId.slice(0, 20)}</p>
        <div className="mt-3">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[0.5625rem] uppercase tracking-wider text-on-surface-dim">
              Progress
            </span>
            <span className="font-mono text-[0.625rem] text-tertiary">
              {completed}/{total}
            </span>
          </div>
          <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-container-high">
            <div
              className="h-full rounded-full bg-tertiary transition-all duration-500"
              style={{ width: `${total > 0 ? (completed / total) * 100 : 0}%` }}
            />
          </div>
        </div>
      </div>

      {/* Dimension list */}
      <div className="mt-5 px-2">
        {/* Foundation dimensions */}
        {foundations.length > 0 && (
          <div className="mb-1">
            <p className="px-3 py-1 font-mono text-[0.5625rem] uppercase tracking-wider text-on-surface-dim">
              Foundation
            </p>
            {foundations.map((dim) => (
              <DimensionRow key={dim.id} dim={dim} isActive={activeDimension === dim.dimension} />
            ))}
          </div>
        )}

        {/* Capability dimensions */}
        {capabilities.length > 0 && (
          <div>
            <p className="px-3 py-1 font-mono text-[0.5625rem] uppercase tracking-wider text-on-surface-dim">
              Capabilities
            </p>
            {capabilities.map((dim) => (
              <DimensionRow key={dim.id} dim={dim} isActive={activeDimension === dim.dimension} />
            ))}
          </div>
        )}
      </div>

      {/* Bottom action */}
      <div className="mt-6 px-4">
        <Link
          to="/new"
          className="block rounded-xl bg-primary-gradient px-4 py-2 text-center text-sm font-medium text-surface-container-lowest transition-transform hover:scale-[1.02]"
        >
          + New Experiment
        </Link>
      </div>
    </aside>
  );
}

function DimensionRow({ dim, isActive }: { dim: DimensionStatus; isActive: boolean }) {
  const styles = STATUS_STYLES[dim.status];
  const label = dim.dimension.replace(/-/g, " ");

  return (
    <div
      className={`relative flex items-center gap-2.5 rounded-lg px-3 py-2 transition-colors ${
        isActive ? "bg-primary/10" : "hover:bg-surface-container-high"
      }`}
    >
      <div className={`h-2.5 w-2.5 shrink-0 rounded-full ${styles.dot}`} aria-hidden />
      <div className="min-w-0 flex-1">
        <p className={`truncate text-[0.6875rem] capitalize leading-tight ${styles.label}`}>
          {label}
        </p>
      </div>
      {dim.status === "complete" && dim.fitness_score != null && (
        <span className="shrink-0 font-mono text-[0.5625rem] text-tertiary">
          {dim.fitness_score.toFixed(2)}
        </span>
      )}
      {dim.status === "running" && (
        <span className="shrink-0 font-mono text-[0.5625rem] text-primary">live</span>
      )}
    </div>
  );
}
