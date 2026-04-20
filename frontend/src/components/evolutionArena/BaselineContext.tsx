/**
 * "What does raw Sonnet score?" — the baseline card the arena shows so the
 * user has a reference point for interpreting evolved fitness in real time.
 */

interface BaselineContextProps {
  rawComposite: number | null;
  challenges: number;
  families: number;
  thisFamilyBaseline: number | null;
  loading: boolean;
}

export default function BaselineContext({
  rawComposite,
  challenges,
  families,
  thisFamilyBaseline,
  loading,
}: BaselineContextProps) {
  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5">
      <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
        Baseline — Raw Sonnet
      </p>
      <p className="mt-1.5 text-[0.6875rem] leading-relaxed text-on-surface-dim">
        What Claude Sonnet scores with no skill on the same challenges. The goal: evolved skill
        consistently beats baseline.
      </p>
      {loading ? (
        <p className="mt-3 text-xs text-on-surface-dim">Loading baseline data...</p>
      ) : (
        <div className="mt-3 space-y-2">
          <Row label="Raw Composite" value={rawComposite?.toFixed(3) ?? "—"} />
          <Row label="Challenges" value={challenges.toString()} />
          <Row label="Families" value={families.toString()} />
          {thisFamilyBaseline != null && (
            <Row label="This Family Baseline" value={thisFamilyBaseline.toFixed(3)} />
          )}
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-on-surface-dim">{label}</span>
      <span className="font-mono text-sm text-on-surface">{value}</span>
    </div>
  );
}
