import StatusGlow from "./StatusGlow";
import type { CompetitorState } from "../types";

interface CompetitorCardProps {
  competitorId: number;
  skillId: string;
  state: CompetitorState;
  challengeId?: string;
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

const ACTIVE_STATES: ReadonlySet<CompetitorState> = new Set([
  "writing",
  "testing",
  "iterating",
]);

export default function CompetitorCard({
  competitorId,
  skillId,
  state,
  challengeId,
}: CompetitorCardProps) {
  const isActive = ACTIVE_STATES.has(state);
  return (
    <div
      className={
        "flex items-center gap-4 rounded-xl px-5 py-4 transition-all " +
        (isActive
          ? "border border-primary/40 bg-surface-container-low animate-breathe-border"
          : state === "done"
            ? "border border-tertiary/30 bg-surface-container-low"
            : "border border-transparent bg-surface-container-low hover:bg-surface-container-high")
      }
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-container-highest">
        <StatusGlow variant={STATE_VARIANT[state]} pulse={isActive} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="truncate text-base font-medium text-on-surface">
          Competitor {String.fromCharCode(65 + competitorId)}
        </p>
        <p className="truncate font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          skill {skillId.slice(0, 8)}
          {challengeId ? ` • challenge ${challengeId.slice(0, 8)}` : ""}
        </p>
      </div>
      <span
        className={
          "font-mono text-[0.6875rem] uppercase tracking-wider " +
          (isActive ? "text-secondary" : "text-on-surface-dim")
        }
      >
        {STATE_LABEL[state]}
      </span>
    </div>
  );
}
