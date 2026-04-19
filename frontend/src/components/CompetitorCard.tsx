import StatusGlow from "./StatusGlow";
import type { CompetitorState } from "../types";

interface CompetitorCardProps {
  competitorId: number;
  skillId: string;
  state: CompetitorState;
  challengeId?: string;
  /** Human-readable challenge label, e.g. "Challenge 2: dedupe orders.csv" */
  challengeLabel?: string;
}

const STATE_LABEL: Record<CompetitorState, string> = {
  queued: "IN QUEUE",
  writing: "WRITING CODE...",
  testing: "RUNNING TESTS...",
  iterating: "ITERATING...",
  done: "DONE ✓",
  error: "ERROR",
};

const STATE_VARIANT: Record<
  CompetitorState,
  "neutral" | "running" | "warning" | "success" | "error"
> = {
  queued: "neutral",
  writing: "running",
  testing: "warning",
  iterating: "running",
  done: "success",
  error: "error",
};

const ACTIVE_STATES: ReadonlySet<CompetitorState> = new Set(["writing", "testing", "iterating"]);

export default function CompetitorCard({
  competitorId,
  skillId,
  state,
  challengeLabel,
}: CompetitorCardProps) {
  const isActive = ACTIVE_STATES.has(state);
  return (
    <div
      className={
        "flex items-start gap-4 rounded-xl border px-5 py-4 transition-all " +
        (isActive
          ? "animate-breathe-border border-primary/40 bg-surface-container-lowest"
          : state === "done"
            ? "border-tertiary/30 bg-surface-container-lowest"
            : "border-outline-variant bg-surface-container-lowest hover:bg-surface-container-low")
      }
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-surface-container-high">
        <StatusGlow variant={STATE_VARIANT[state]} pulse={isActive} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-3">
          <p className="truncate text-base font-medium text-on-surface">
            Competitor {String.fromCharCode(65 + competitorId)}
          </p>
          <span
            className={
              "font-mono text-[0.6875rem] uppercase tracking-wider " +
              (isActive ? "text-primary" : "text-on-surface-dim")
            }
          >
            {STATE_LABEL[state]}
          </span>
        </div>
        <p className="mt-0.5 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
          skill {skillId.slice(0, 8)}
        </p>
        {challengeLabel && (
          <p className="mt-1.5 text-xs leading-relaxed text-on-surface">→ {challengeLabel}</p>
        )}
      </div>
    </div>
  );
}
