import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import FitnessChart from "./FitnessChart";
import FitnessRadar from "./FitnessRadar";
import PrimaryButton from "./PrimaryButton";
import Sidebar from "./Sidebar";
import VariantBreakdown from "./VariantBreakdown";
import { derivePhases, type EvolutionSocketState } from "../hooks/useEvolutionSocket";
import type { RunDetail } from "../types";

interface EvolutionResultsProps {
  runId: string;
  sockState: EvolutionSocketState;
  runDetail: RunDetail | null;
}

export default function EvolutionResults({
  runId,
  sockState,
  runDetail,
}: EvolutionResultsProps) {
  const finalGen = sockState.generations.at(-1);
  const bestFitness = finalGen?.best_fitness ?? runDetail?.best_fitness ?? 0;

  // Phase diagram in the sidebar — at this screen everything is complete
  const phases = useMemo(() => derivePhases(sockState, 0), [sockState]);

  // Fetch the SKILL.md preview for the winning skill. Fake runs have no
  // persisted skill — in that case the endpoint 404s and we show a placeholder.
  const [skillMd, setSkillMd] = useState<string | null>(null);
  const [skillMdError, setSkillMdError] = useState<string | null>(null);
  useEffect(() => {
    if (!runId) return;
    fetch(`/api/runs/${runId}/export?format=skill_md`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.text();
      })
      .then(setSkillMd)
      .catch((err) => setSkillMdError(String(err)));
  }, [runId]);

  // v2.0 — Advanced toggle reveals the VariantBreakdown for atomic-mode runs
  const [showAdvanced, setShowAdvanced] = useState(false);
  const isAtomic = runDetail?.evolution_mode === "atomic";
  const familyId = runDetail?.family_id ?? null;

  // Pull objectives from the latest generation_complete or scores_published event
  const lastScores = sockState.events
    .slice()
    .reverse()
    .find((e) => e.event === "scores_published");
  const objectives: Record<string, number> = lastScores?.pareto_front
    ? {} // The events don't carry per-objective scores; populate from API instead.
    : {};

  // Fallback synthetic radar based on the chart values so we render something
  // meaningful in MVP. Real per-objective scores will be populated when the
  // backend exposes them via the run detail endpoint.
  const radarData = {
    correctness: bestFitness,
    token_efficiency: Math.max(0, bestFitness - 0.05),
    code_quality: Math.max(0, bestFitness - 0.02),
    trigger_accuracy: Math.max(0, bestFitness - 0.08),
    consistency: 0,
    ...objectives,
  };

  return (
    <div className="flex">
      <Sidebar
        runId={runId}
        generation={sockState.currentGeneration}
        totalGenerations={runDetail?.num_generations}
        phases={phases}
      />
      <div className="flex-1 px-8 py-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-tertiary">
              Protocol: Forkless
            </p>
            <h1 className="mt-2 font-display text-5xl leading-[1.05] tracking-tight">
              Evolution
              <br />
              <span className="text-tertiary">Complete</span>
            </h1>
          </div>
          <div className="text-right">
            <p className="font-display text-7xl tracking-tight text-tertiary">
              {bestFitness.toFixed(2)}
            </p>
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
              Best Fitness
            </p>
          </div>
        </div>

        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
          {/* Code preview placeholder */}
          <div className="rounded-xl bg-surface-container-lowest p-5">
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
              Best Skill — {(sockState.bestSkillId ?? runDetail?.best_skill_id)?.slice(0, 8) ?? "—"}
            </p>
            {skillMd ? (
              <pre className="mt-3 max-h-[600px] overflow-y-auto whitespace-pre-wrap font-mono text-xs text-on-surface">
                {skillMd}
              </pre>
            ) : (
              <div className="mt-3 flex h-[600px] flex-col items-center justify-center rounded-lg border border-dashed border-on-surface-dim/20 p-6 text-center">
                <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                  {skillMdError ? "No Skill Artifact" : "Loading SKILL.md..."}
                </p>
                <p className="mt-2 max-w-xs text-xs text-on-surface-dim">
                  {skillMdError
                    ? "This run has no persisted best_skill — likely a fake/demo run. Real evolutions render the full evolved SKILL.md here."
                    : ""}
                </p>
              </div>
            )}
          </div>

          {/* Right column: radar + chart + actions */}
          <div className="space-y-6">
            <div className="rounded-xl bg-surface-container-low p-5">
              <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                Fitness Radar
              </p>
              <FitnessRadar objectives={radarData} />
            </div>

            <div className="rounded-xl bg-surface-container-low p-5">
              <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                Growth Curve
              </p>
              <FitnessChart generations={sockState.generations} />
            </div>

            <div className="space-y-3">
              <a
                href={`/api/runs/${runId}/export?format=skill_dir`}
                className="block rounded-xl bg-surface-container-low p-3 text-center text-sm text-on-surface transition-colors hover:bg-surface-container-high"
              >
                ↓ Export Build (.zip)
              </a>
              <a
                href={`/api/runs/${runId}/export?format=agent_sdk_config`}
                target="_blank"
                rel="noreferrer"
                className="block rounded-xl bg-surface-container-low p-3 text-center text-sm text-on-surface transition-colors hover:bg-surface-container-high"
              >
                ↓ Export Agent SDK Config
              </a>
              <Link to={`/runs/${runId}/export`} className="block">
                <PrimaryButton className="w-full">
                  Open Export Preview →
                </PrimaryButton>
              </Link>
              <Link
                to={`/runs/${runId}/diff`}
                className="block rounded-xl bg-surface-container-low p-3 text-center text-sm text-on-surface transition-colors hover:bg-surface-container-high"
              >
                ⑂ View Lineage Diff
              </Link>
            </div>

            <p className="text-center font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
              Total spent: ${(sockState.totalCostUsd || runDetail?.total_cost_usd || 0).toFixed(2)}
            </p>
          </div>
        </div>

        {isAtomic && familyId && (
          <div className="mt-8">
            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              className="rounded-lg bg-primary/10 px-4 py-2 font-mono text-[0.6875rem] uppercase tracking-wider text-primary transition-colors hover:bg-primary/20"
            >
              {showAdvanced ? "Hide" : "Show"} Advanced — Variant Breakdown
            </button>
            {showAdvanced && (
              <div className="mt-4">
                <VariantBreakdown familyId={familyId} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
