import type { RunReport } from "../types";

interface PipelineOverviewProps {
  report: RunReport;
}

/**
 * Always-visible "what happened" card at the top of the atomic run page.
 *
 * Renders:
 *   - A single-sentence takeaway ("12 dimensions evolved, 8 spawn winners,
 *     final composite at 0.94")
 *   - A mini pipeline diagram: 24 starting variants → compete → 12 winners
 *     → assemble → 1 composite
 *   - A short one-paragraph narrative that ties it together
 *
 * This is the first thing a visitor sees, so it explains the whole story
 * without requiring any tab navigation.
 */
export default function PipelineOverview({ report }: PipelineOverviewProps) {
  const startingVariants = 24;
  const winners = report.variant_evolutions.length;
  const challenges = report.challenges.length;
  const fitness = report.summary.aggregate_fitness;

  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
      <div className="flex items-baseline justify-between">
        <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-tertiary">
          Generation 1 · Pipeline Overview
        </p>
        <p className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
          Atomic evolution
        </p>
      </div>

      <h2 className="mt-3 text-lg leading-snug text-on-surface">
        This run decomposed the skill into{" "}
        <strong className="text-tertiary">{winners} dimensions</strong>, spawned{" "}
        <strong className="text-tertiary">{startingVariants} candidate variants</strong>,
        competed them on{" "}
        <strong className="text-tertiary">{challenges} challenges</strong>, and
        assembled the winners into{" "}
        <strong className="text-tertiary">one composite skill</strong> at{" "}
        <strong className="text-tertiary">
          {fitness.toFixed(2)} average fitness
        </strong>
        .
      </h2>

      {/* Mini pipeline diagram */}
      <div className="mt-5 grid grid-cols-1 gap-3 lg:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr]">
        <PipelineStage
          label="Gen 0 · Variants"
          count={startingVariants}
          caption={`${winners} seeds + ${winners} spawns`}
        />
        <Arrow />
        <PipelineStage
          label="Competition"
          count={challenges}
          caption="challenge runs"
          accent
        />
        <Arrow />
        <PipelineStage
          label="Gen 0 · Winners"
          count={winners}
          caption={`1 per dimension`}
        />
        <Arrow />
        <PipelineStage
          label="Gen 1 · Composite"
          count={1}
          caption={`fitness ${fitness.toFixed(2)}`}
          accent
        />
      </div>
    </div>
  );
}

interface PipelineStageProps {
  label: string;
  count: number;
  caption: string;
  accent?: boolean;
}

function PipelineStage({ label, count, caption, accent }: PipelineStageProps) {
  return (
    <div
      className={`rounded-lg p-4 text-center ${
        accent
          ? "bg-tertiary/10 border border-tertiary/30"
          : "bg-surface-container-low border border-outline-variant"
      }`}
    >
      <p className="font-mono text-[0.5625rem] uppercase tracking-wider text-on-surface-dim">
        {label}
      </p>
      <p className="mt-1 font-display text-4xl leading-none tracking-tight text-tertiary">
        {count}
      </p>
      <p className="mt-2 font-mono text-[0.5625rem] text-on-surface-dim">
        {caption}
      </p>
    </div>
  );
}

function Arrow() {
  return (
    <div className="flex items-center justify-center text-lg text-on-surface-dim lg:text-2xl">
      →
    </div>
  );
}
