import type { PhaseState } from "../types";

interface ProcessFlowProps {
  phases: PhaseState[];
  currentGeneration: number;
  totalGenerations?: number;
}

const STATUS_DOT_CLASS: Record<PhaseState["status"], string> = {
  pending: "bg-surface-container-high text-on-surface-dim",
  running: "bg-primary text-primary shadow-glow animate-pulse-glow",
  complete: "bg-tertiary text-tertiary",
  failed: "bg-error text-error",
};

const STATUS_LABEL_CLASS: Record<PhaseState["status"], string> = {
  pending: "text-on-surface-dim",
  running: "text-on-surface font-medium",
  complete: "text-on-surface-dim",
  failed: "text-error font-medium",
};

const STATUS_ICON: Record<PhaseState["status"], string> = {
  pending: "○",
  running: "◉",
  complete: "✓",
  failed: "✕",
};

export default function ProcessFlow({
  phases,
  currentGeneration,
  totalGenerations,
}: ProcessFlowProps) {
  return (
    <div className="space-y-1">
      {/* Generation header */}
      <div className="mb-3 px-3 py-2">
        <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          Process Flow
        </p>
        <p className="mt-1 text-sm text-on-surface">
          Generation{" "}
          <span className="font-display text-base text-primary">
            {currentGeneration + 1}
          </span>
          {totalGenerations != null && (
            <span className="text-on-surface-dim"> / {totalGenerations}</span>
          )}
        </p>
      </div>

      {/* Phases */}
      <div className="relative">
        {/* Vertical connector line behind the dots */}
        <div className="absolute left-[1.375rem] top-3 bottom-3 w-px bg-outline-variant" />

        {phases.map((phase) => (
          <PhaseRow key={phase.id} phase={phase} />
        ))}
      </div>
    </div>
  );
}

function PhaseRow({ phase }: { phase: PhaseState }) {
  return (
    <div className="relative flex items-start gap-3 rounded-xl px-3 py-2 transition-colors hover:bg-surface-container-high">
      {/* Dot */}
      <div
        className={
          "relative mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold " +
          STATUS_DOT_CLASS[phase.status]
        }
        aria-hidden="true"
      >
        {phase.status === "complete" || phase.status === "failed"
          ? STATUS_ICON[phase.status]
          : null}
      </div>

      {/* Label + detail */}
      <div className="min-w-0 flex-1">
        <p className={"text-sm leading-tight " + STATUS_LABEL_CLASS[phase.status]}>
          {phase.label}
        </p>
        {phase.detail && (
          <p className="mt-0.5 truncate font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            {phase.detail}
          </p>
        )}
      </div>
    </div>
  );
}
