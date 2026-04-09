import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import BreedingReport from "./BreedingReport";
import CompetitorCard from "./CompetitorCard";
import EvolutionResults from "./EvolutionResults";
import FitnessChart from "./FitnessChart";
import JudgingPipelinePill from "./JudgingPipelinePill";
import LiveFeedLog from "./LiveFeedLog";
import Sidebar from "./Sidebar";
import StatusGlow from "./StatusGlow";
import { useEvolutionSocket } from "../hooks/useEvolutionSocket";
import type { RunDetail } from "../types";

const JUDGING_LAYERS: { layer: string; label: string }[] = [
  { layer: "L1", label: "Deterministic" },
  { layer: "L2", label: "Trigger" },
  { layer: "L3", label: "Trace" },
  { layer: "L4", label: "Pareto" },
  { layer: "L5", label: "Attribution" },
];

export default function EvolutionArena() {
  const { runId } = useParams<{ runId: string }>();
  const [runDetail, setRunDetail] = useState<RunDetail | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const startTime = useState(() => Date.now())[0];

  const sockState = useEvolutionSocket(runId ?? null);

  // Fetch run detail once on mount (for population_size, num_generations)
  useEffect(() => {
    if (!runId) return;
    fetch(`/runs/${runId}`)
      .then((r) => r.json())
      .then((d: RunDetail) => setRunDetail(d))
      .catch(() => undefined);
  }, [runId]);

  // Tick elapsed timer
  useEffect(() => {
    if (sockState.isComplete || sockState.isFailed) return;
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [sockState.isComplete, sockState.isFailed, startTime]);

  if (!runId) return null;

  // If complete, render the results screen
  if (sockState.isComplete) {
    return <EvolutionResults runId={runId} sockState={sockState} runDetail={runDetail} />;
  }

  // Show breeding state when active
  const showBreeding = !!sockState.latestBreedingReport;

  const elapsedFmt = `${Math.floor(elapsed / 60)
    .toString()
    .padStart(2, "0")}:${(elapsed % 60).toString().padStart(2, "0")}`;
  const budgetCap = 10; // Could come from runDetail; not currently exposed

  return (
    <div className="flex">
      <Sidebar
        runId={runId}
        generation={sockState.currentGeneration}
        totalGenerations={runDetail?.num_generations}
      />

      <div className="flex-1 px-8 py-6">
        {/* Breadcrumbs + status */}
        <div className="flex items-center justify-between">
          <div>
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
              Dashboard <span className="text-on-surface-dim">›</span>{" "}
              Run {runId.slice(0, 8)} <span className="text-on-surface-dim">›</span>{" "}
              Generation {sockState.currentGeneration} of{" "}
              {runDetail?.num_generations ?? "?"}
            </p>
            <h1 className="mt-2 flex items-center gap-3 font-display text-4xl tracking-tight">
              Evolution Cycle
              <span className="inline-flex items-center gap-1 rounded-full bg-tertiary/15 px-3 py-1 text-xs font-medium text-tertiary">
                <StatusGlow variant="success" />
                {sockState.isFailed ? "FAILED" : "RUNNING"}
              </span>
            </h1>
          </div>
          <div className="text-right">
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
              Elapsed Time
            </p>
            <p className="font-display text-2xl tracking-tight">{elapsedFmt}</p>
            <p className="mt-1 font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
              Budget Used
            </p>
            <p className="font-mono text-sm text-tertiary">
              ${sockState.totalCostUsd.toFixed(2)} / ${budgetCap.toFixed(2)}
            </p>
          </div>
        </div>

        {/* Connection status banner */}
        {sockState.status === "closed" && !sockState.isComplete && !sockState.isFailed && (
          <div className="mt-4 rounded-xl bg-warning/10 p-3 text-sm text-warning">
            Connection lost. Reconnecting...
          </div>
        )}
        {sockState.isFailed && (
          <div className="mt-4 rounded-xl bg-error/10 p-3 text-sm text-error">
            Run failed: {sockState.failureReason ?? "(no reason)"}
          </div>
        )}

        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
          {/* Main column: arena + breeding + log */}
          <div className="space-y-6">
            <div className="rounded-xl bg-surface-container-low p-5">
              <div className="flex items-center justify-between">
                <h2 className="font-display text-xl tracking-tight">
                  ✕ Competitor Arena
                </h2>
                <span className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                  Active Pool: {sockState.competitors.length} agents
                </span>
              </div>
              <div className="mt-4 space-y-2">
                {sockState.competitors.length === 0 ? (
                  <p className="text-sm text-on-surface-dim">Waiting for competitors to start...</p>
                ) : (
                  sockState.competitors.map((c) => (
                    <CompetitorCard
                      key={`${c.competitorId}-${c.skillId}`}
                      competitorId={c.competitorId}
                      skillId={c.skillId}
                      state={c.state}
                      challengeId={c.challengeId}
                    />
                  ))
                )}
              </div>
            </div>

            {showBreeding && (
              <BreedingReport
                report={sockState.latestBreedingReport}
                lessons={sockState.latestLessons}
              />
            )}

            <LiveFeedLog events={sockState.events} />
          </div>

          {/* Right column: stats + judging pipeline */}
          <div className="space-y-6">
            <div className="rounded-xl bg-surface-container-low p-5">
              <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                Generation Stats
              </p>
              <FitnessChart generations={sockState.generations} />
              <div className="mt-2 grid grid-cols-2 gap-4">
                <div>
                  <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                    Best Fitness
                  </p>
                  <p className="font-display text-2xl tracking-tight">
                    {sockState.generations.at(-1)?.best_fitness?.toFixed(2) ?? "—"}
                  </p>
                </div>
                <div>
                  <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                    Avg Fitness
                  </p>
                  <p className="font-display text-2xl tracking-tight">
                    {sockState.generations.at(-1)?.avg_fitness?.toFixed(2) ?? "—"}
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-xl bg-surface-container-low p-5">
              <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                Judging Pipeline
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {JUDGING_LAYERS.map((l) => (
                  <JudgingPipelinePill
                    key={l.layer}
                    layer={l.layer}
                    label={l.label}
                    status={
                      sockState.generations.at(-1)?.status === "complete"
                        ? "complete"
                        : sockState.generations.at(-1)?.status === "judging"
                          ? "running"
                          : "pending"
                    }
                  />
                ))}
              </div>
            </div>

            {runDetail && (
              <Link
                to={`/runs/${runId}/export`}
                className="block rounded-xl bg-surface-container-low p-4 text-center text-sm text-on-surface transition-colors hover:bg-surface-container-high"
              >
                View Export →
              </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
