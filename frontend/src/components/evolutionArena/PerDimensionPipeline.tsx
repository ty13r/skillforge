/**
 * Right-column tracker of the 5 mini-pipeline steps per dimension. The
 * parent passes in the booleans derived from event-stream state; this
 * component just renders dots.
 */

interface PerDimensionPipelineProps {
  challengeDesigned: boolean;
  variantsSpawned: boolean;
  competitorsFinished: boolean;
  scored: boolean;
  winnerPicked: boolean;
}

export default function PerDimensionPipeline({
  challengeDesigned,
  variantsSpawned,
  competitorsFinished,
  scored,
  winnerPicked,
}: PerDimensionPipelineProps) {
  const steps = [
    { step: "1", label: "Design focused challenge", done: challengeDesigned },
    { step: "2", label: "Spawn seed + alternative", done: variantsSpawned },
    { step: "3", label: "Compete on challenge", done: competitorsFinished },
    { step: "4", label: "Score (6-layer composite)", done: scored },
    { step: "5", label: "Pick winner", done: winnerPicked },
  ];
  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5">
      <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
        Per-Dimension Pipeline
      </p>
      <div className="mt-3 space-y-1.5">
        {steps.map((s) => (
          <div key={s.step} className="flex items-center gap-2">
            <span
              className={`flex h-5 w-5 items-center justify-center rounded-full text-[0.5625rem] font-bold ${
                s.done
                  ? "bg-tertiary/20 text-tertiary"
                  : "bg-surface-container-high text-on-surface-dim"
              }`}
            >
              {s.done ? "✓" : s.step}
            </span>
            <span className={`text-xs ${s.done ? "text-on-surface-dim" : "text-on-surface"}`}>
              {s.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
