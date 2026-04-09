import { Link } from "react-router-dom";

import StatusGlow from "./StatusGlow";
import type { RunStatus } from "../types";

interface EvolutionCardProps {
  id: string;
  specialization: string;
  status: RunStatus;
  bestFitness?: number | null;
  cost: number;
}

const STATUS_LABEL: Record<RunStatus, string> = {
  pending: "PENDING",
  running: "RUNNING",
  complete: "COMPLETE",
  failed: "FAILED",
};

const STATUS_VARIANT: Record<
  RunStatus,
  "running" | "success" | "error" | "neutral"
> = {
  pending: "neutral",
  running: "running",
  complete: "success",
  failed: "error",
};

export default function EvolutionCard({
  id,
  specialization,
  status,
  bestFitness,
  cost,
}: EvolutionCardProps) {
  return (
    <Link
      to={`/runs/${id}`}
      className="block rounded-xl border border-outline-variant bg-surface-container-lowest p-5 transition-all hover:border-primary/40 hover:bg-surface-container-low hover:shadow-elevated"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StatusGlow variant={STATUS_VARIANT[status]} />
          <span className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            {STATUS_LABEL[status]}
          </span>
        </div>
        <span className="font-mono text-[0.6875rem] text-on-surface-dim">
          {id.slice(0, 8)}
        </span>
      </div>

      <h3 className="mt-3 line-clamp-2 text-base font-medium text-on-surface">
        {specialization || "(unspecified)"}
      </h3>

      <div className="mt-4 flex items-end justify-between">
        <div>
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Fitness
          </p>
          <p className="font-display text-2xl tracking-tight text-on-surface">
            {bestFitness != null ? bestFitness.toFixed(2) : "—"}
          </p>
        </div>
        <div className="text-right">
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Spent
          </p>
          <p className="font-mono text-sm text-on-surface">${cost.toFixed(2)}</p>
        </div>
      </div>
    </Link>
  );
}
