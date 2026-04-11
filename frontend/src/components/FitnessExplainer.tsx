/**
 * Compact inline explainer for the L1 deterministic fitness score.
 *
 * Shown as a small card so a first-time visitor understands what "0.94"
 * means without hunting through docs. Intentionally short.
 */
export default function FitnessExplainer() {
  return (
    <div className="rounded-lg border border-outline-variant bg-surface-container-low p-4 text-xs leading-relaxed text-on-surface-dim">
      <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface">
        What does "fitness" mean?
      </p>
      <p className="mt-2">
        Fitness is the average of the <strong className="text-on-surface">L1
        deterministic checks</strong> across all sampled challenges for a
        variant. Each challenge defines a list of required substrings
        (<code>must_contain</code>) and forbidden ones
        (<code>must_not_contain</code>); the score is the fraction of checks
        that pass, weighted by the challenge's own weight.
      </p>
      <p className="mt-2">
        <strong className="text-on-surface">1.0</strong> = every required
        substring was present and zero forbidden substrings appeared.{" "}
        <strong className="text-on-surface">0.5</strong> = half the checks
        passed. The composite skill's fitness is the average across all 12
        dimension winners.
      </p>
      <p className="mt-2">
        Higher reviewer layers — trigger accuracy (L2), trace analysis (L3),
        comparative pairwise (L4), trait attribution (L5) — are part of the
        production pipeline but were not run for this showcase.
      </p>
    </div>
  );
}
