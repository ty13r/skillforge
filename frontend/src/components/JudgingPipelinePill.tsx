interface JudgingPipelinePillProps {
  layer: string;
  label: string;
  status: "pending" | "running" | "complete";
}

const STATUS_CLASS: Record<JudgingPipelinePillProps["status"], string> = {
  pending: "bg-surface-container-high text-on-surface-dim",
  running:
    "bg-secondary/15 text-secondary shadow-glow animate-pulse-glow " +
    "bg-shimmer-stripe bg-[length:200%_100%] animate-shimmer",
  complete: "bg-tertiary/15 text-tertiary",
};

export default function JudgingPipelinePill({ layer, label, status }: JudgingPipelinePillProps) {
  return (
    <div
      className={
        "rounded-full px-3 py-1.5 font-mono text-[0.6875rem] uppercase tracking-wider " +
        STATUS_CLASS[status]
      }
    >
      <span className="font-bold">{layer}:</span> {label}
      {status === "complete" && " ✓"}
    </div>
  );
}
