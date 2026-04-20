/**
 * Static rubric explaining the 6-layer composite scoring weights, plus the
 * optional "best this dimension" fitness if a judging generation has
 * completed. Pure presentational.
 */

interface CompositeScoringProps {
  bestThisDimension: number | null;
}

const LAYERS: { label: string; weight: string; desc: string }[] = [
  { label: "Behavioral Tests", weight: "40%", desc: "ExUnit — does the code work?" },
  { label: "Compilation", weight: "15%", desc: "mix compile — does it build?" },
  { label: "AST Quality", weight: "15%", desc: "Structure, coverage, pipes" },
  { label: "String Match", weight: "10%", desc: "L0 expected patterns" },
  { label: "Template", weight: "10%", desc: "Modern HEEx idioms" },
  { label: "Brevity", weight: "10%", desc: "Conciseness" },
];

export default function CompositeScoring({ bestThisDimension }: CompositeScoringProps) {
  return (
    <div className="rounded-xl bg-surface-container-low p-5">
      <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
        Composite Scoring
      </p>
      <p className="mt-1.5 text-[0.6875rem] leading-relaxed text-on-surface-dim">
        Each variant is scored through 6 layers, weighted into one composite fitness.
      </p>
      <div className="mt-3 space-y-1.5">
        {LAYERS.map((layer) => (
          <div key={layer.label} className="flex items-center gap-2">
            <span className="w-8 shrink-0 text-right font-mono text-[0.5625rem] text-tertiary">
              {layer.weight}
            </span>
            <span className="text-xs text-on-surface">{layer.label}</span>
            <span className="ml-auto text-[0.5625rem] text-on-surface-dim">{layer.desc}</span>
          </div>
        ))}
      </div>
      {bestThisDimension != null && (
        <div className="mt-3 border-t border-outline-variant pt-3">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
              Best This Dimension
            </span>
            <span className="font-mono text-sm text-tertiary">{bestThisDimension.toFixed(3)}</span>
          </div>
        </div>
      )}
    </div>
  );
}
