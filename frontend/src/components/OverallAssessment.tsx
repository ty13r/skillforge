import type { RunReport } from "../types";

interface OverallAssessmentProps {
  report: RunReport;
  seedWinnerCount: number;
  perfectFitnessCount: number;
}

/**
 * Plain-English 3-paragraph "TL;DR" assessment of the run.
 *
 * For the phoenix-liveview seed run the content is hard-coded against known
 * facts (11 capabilities, component-forward foundation, 14-rule anti-pattern
 * catalog, 3 seed winners, 5 perfect scores). Future seed runs can
 * parameterize this further; real engine runs could LLM-generate a similar
 * assessment post-assembly.
 *
 * Position: always visible, directly under the hero header and above the
 * pipeline diagram. This is the first thing a visitor reads.
 */
export default function OverallAssessment({
  report,
  seedWinnerCount,
  perfectFitnessCount,
}: OverallAssessmentProps) {
  const family = report.taxonomy?.family_label ?? "this skill";
  const numDims = report.variant_evolutions.length;
  const numChallenges = report.challenges.length;
  const fitness = report.summary.aggregate_fitness;
  const spawnWinnerCount = numDims - seedWinnerCount;

  return (
    <div className="rounded-xl border border-tertiary/30 bg-tertiary/5 p-6">
      <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-tertiary">
        Overall Assessment
      </p>

      <div className="mt-4 space-y-4 text-sm leading-relaxed text-on-surface">
        <p>
          <strong className="text-tertiary">What this is.</strong> A production-ready Claude Agent
          Skill for writing <span className="font-mono text-xs">{family}</span>. It enforces a
          component-forward architecture — parent LiveView as a thin coordinator, LiveComponents own
          stateful regions — covers the {numDims - 1} most important capability areas (HEEx
          templates, function components, streams, forms, mount lifecycle, event handlers, PubSub,
          navigation, auth) and ships with a 14-rule anti-patterns catalog that includes mechanical
          grep-based detectors a reviewer can run directly.
        </p>

        <p>
          <strong className="text-tertiary">How it was built.</strong> {numDims} dimensions of the
          skill were evolved in parallel. For each, a pre-existing seed variant competed against a
          freshly-spawned alternative on 2 sampled challenges. The higher-scoring variant became the
          dimension's winner. An Engineer then assembled the {numDims} winners into one coherent
          composite, resolving <strong>3 conflicts</strong> between capability stances (mount vs.
          async-load discipline, event funnel vs. PubSub direct handling, composite granularity).
          The final composite weighs ~20KB of Markdown across {numDims} named sections plus the
          detector catalog.
        </p>

        <p>
          <strong className="text-tertiary">Quality signal.</strong>{" "}
          <span className="font-mono">{fitness.toFixed(3)}</span> average fitness across{" "}
          <span className="font-mono">{numChallenges * 2}</span> test runs (L1 deterministic checks
          — required-substring presence + forbidden-substring absence).{" "}
          <span className="font-mono">{perfectFitnessCount}</span> of {numDims - 1} capability
          dimensions hit a perfect 1.000. The <span className="font-mono">{seedWinnerCount}</span>{" "}
          dimensions where the pre-existing seed beat the spawned alternative
          (heex-and-verified-routes, streams-and-collections, navigation-patterns) flag weak scorer
          discrimination on those facets — the production pipeline would layer L2 trigger accuracy,
          L3 trace analysis, and L4 comparative pairwise review on top to get richer signal. Bottom
          line: <strong className="text-tertiary">publishable as a showcase</strong>;{" "}
          {spawnWinnerCount}/{numDims} wins for the Spawner are a healthy signal that atomic
          evolution isn't just elitism.
        </p>
      </div>
    </div>
  );
}
