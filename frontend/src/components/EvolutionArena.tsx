import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { apiClient } from "@/api/client";
import { useBenchSummary } from "@/api/hooks/bench";
import { useRun, useRunDimensions } from "@/api/hooks/runs";
import { useEvolutionSocket } from "@/hooks/useEvolutionSocket";
import type { CompetitorView, DimensionStatus } from "@/types";

import AtomicRunDetail from "./AtomicRunDetail";
import AtomicSidebar from "./AtomicSidebar";
import BreedingReport from "./BreedingReport";
import LiveFeedLog from "./LiveFeedLog";
import SkillVariantCard from "./SkillVariantCard";
import ArenaHeader from "./evolutionArena/ArenaHeader";
import BaselineContext from "./evolutionArena/BaselineContext";
import CompletedDimensions from "./evolutionArena/CompletedDimensions";
import CompositeScoring from "./evolutionArena/CompositeScoring";
import PerDimensionPipeline from "./evolutionArena/PerDimensionPipeline";

const BUDGET_CAP = 10;
const DIMENSIONS_POLL_MS = 5000;

/**
 * Live evolution "arena" — watches a run via WebSocket events + cached
 * REST snapshots and renders the atomic-mode status board. On completion
 * it hands off to ``AtomicRunDetail`` for the post-run showcase.
 *
 * Data comes from three sources:
 *   - ``useEvolutionSocket`` for real-time events (wins while active)
 *   - ``useRun`` / ``useRunDimensions`` / ``useBenchSummary`` for REST
 *     fallbacks + polling while active
 *
 * Right-column cards, header, and pipeline tracker live as sub-components
 * under ``evolutionArena/`` so this file stays focused on composition.
 */
export default function EvolutionArena() {
  const { runId } = useParams<{ runId: string }>();
  const [elapsed, setElapsed] = useState(0);
  const [startTime] = useState(() => Date.now());

  // Kick the permanent demo run if we're routed to it.
  useEffect(() => {
    if (runId === "demo-live") {
      apiClient.post("/api/debug/demo").catch(() => undefined);
    }
  }, [runId]);

  const { data: runDetail = null } = useRun(runId ?? null);
  const runAlreadyDone = runDetail?.status === "complete" || runDetail?.status === "failed";

  // Poll dimensions every 5s while the run is active; stop once it's done.
  const { data: fetchedDimensions = [] } = useRunDimensions(runId ?? null, {
    refetchInterval: runAlreadyDone ? false : DIMENSIONS_POLL_MS,
  });

  const { data: benchData } = useBenchSummary();
  const sockState = useEvolutionSocket(runAlreadyDone ? null : (runId ?? null));

  const isComplete = sockState.isComplete || runDetail?.status === "complete";
  const isFailed = sockState.isFailed || runDetail?.status === "failed";

  useEffect(() => {
    if (isComplete || isFailed) return;
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [isComplete, isFailed, startTime]);

  const specialization = useMemo(() => {
    if (runDetail?.specialization) return runDetail.specialization;
    const started = sockState.events.find((e) => e.event === "run_started");
    return (started?.specialization as string | undefined) ?? "";
  }, [runDetail, sockState.events]);

  const challenges = useMemo(() => {
    const byId = new Map<
      string,
      { id: string; difficulty: string; prompt: string; index: number }
    >();
    let idx = 0;
    for (const e of sockState.events) {
      if (e.event === "challenge_designed" && e.challenge_id) {
        const id = e.challenge_id as string;
        if (!byId.has(id)) {
          byId.set(id, {
            id,
            difficulty: (e.difficulty as string) ?? "medium",
            prompt: (e.prompt as string) ?? "",
            index: idx++,
          });
        }
      }
    }
    return Array.from(byId.values());
  }, [sockState.events]);

  const variantGroups = useMemo(() => {
    const groups = new Map<string, { competitorId: number; competitors: CompetitorView[] }>();
    for (const c of sockState.competitors) {
      const existing = groups.get(c.skillId);
      if (existing) {
        existing.competitors.push(c);
      } else {
        groups.set(c.skillId, { competitorId: c.competitorId, competitors: [c] });
      }
    }
    return Array.from(groups.entries()).map(([skillId, data], idx) => ({
      variantIndex: idx,
      skillId,
      competitorId: data.competitorId,
      competitors: data.competitors,
    }));
  }, [sockState.competitors]);

  // For demo/fake runs, reconstruct dimensions from the socket stream
  // rather than the REST endpoint (which has nothing to return for
  // scripted runs).
  const effectiveDimensions: DimensionStatus[] = useMemo(() => {
    if (fetchedDimensions.length > 0) return fetchedDimensions;
    return sockState.atomicDimensions.map((d) => ({
      id: d.dimension,
      dimension: d.dimension,
      tier: d.tier as "foundation" | "capability",
      status: d.status,
      winner_variant_id: null,
      challenge_id: null,
      population_size: 2,
      num_generations: 1,
      created_at: null,
      completed_at: null,
      fitness_score: d.fitness ?? null,
      genome_id: null,
    }));
  }, [fetchedDimensions, sockState.atomicDimensions]);

  const activeDimension = useMemo(() => {
    const running = effectiveDimensions.find((d) => d.status === "running");
    if (running) return running.dimension;
    return sockState.activeDimension ?? null;
  }, [effectiveDimensions, sockState.activeDimension]);

  const completedDims = effectiveDimensions.filter((d) => d.status === "complete");
  const totalDims = effectiveDimensions.length;

  const benchBaseline = benchData?.overall
    ? {
        rawComposite: benchData.overall.raw_composite ?? null,
        challenges: benchData.overall.challenges,
        families: benchData.families.length,
      }
    : null;

  // --- All hooks above this line ---

  if (!runId) return null;

  // Completed runs → AtomicRunDetail showcase.
  if (isComplete) {
    return (
      <AtomicRunDetail runId={runId} runDetail={runDetail!} dimensions={effectiveDimensions} />
    );
  }

  const showBreeding = !!sockState.latestBreedingReport;
  const handleCancel = async () => {
    if (!window.confirm("Cancel this run? Completed dimensions will be saved.")) return;
    try {
      await apiClient.post(`/api/runs/${runId}/cancel`);
    } catch (err) {
      alert(`Cancel error: ${String(err)}`);
    }
  };

  const activeDim = sockState.atomicDimensions.find((d) => d.dimension === activeDimension);
  const bestThisDimension = sockState.generations.at(-1)?.best_fitness ?? null;

  return (
    <div className="flex">
      <AtomicSidebar
        runId={runId}
        dimensions={effectiveDimensions}
        activeDimension={activeDimension}
      />

      <div className="flex-1 px-8 py-6">
        <ArenaHeader
          specialization={specialization}
          isFailed={!!isFailed}
          isComplete={!!isComplete}
          activeDimension={activeDimension}
          completedDims={completedDims.length}
          totalDims={totalDims}
          elapsed={elapsed}
          totalCostUsd={sockState.totalCostUsd}
          budgetCap={BUDGET_CAP}
          onCancel={handleCancel}
        />

        {sockState.status === "closed" && !isComplete && !isFailed && (
          <div className="mt-4 rounded-xl bg-warning/10 p-3 text-sm text-warning">
            Connection lost. Reconnecting...
          </div>
        )}
        {isFailed && (
          <div className="mt-4 rounded-xl bg-error/10 p-3 text-sm text-error">
            Run failed: {sockState.failureReason ?? "(no reason)"}
          </div>
        )}

        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
          <div className="space-y-6">
            {activeDim?.phaseDetail && variantGroups.length === 0 && (
              <div className="flex items-center gap-3 rounded-xl border border-primary/20 bg-primary/5 px-5 py-4">
                <div className="h-2.5 w-2.5 shrink-0 animate-pulse rounded-full bg-primary" />
                <p className="text-sm text-on-surface">{activeDim.phaseDetail}</p>
              </div>
            )}

            {challenges.length > 0 && (
              <CurrentChallenge challenge={challenges[challenges.length - 1]} />
            )}

            <CompetitionPanel variantGroups={variantGroups} challenges={challenges} />

            {showBreeding && (
              <BreedingReport
                report={sockState.latestBreedingReport}
                lessons={sockState.latestLessons}
              />
            )}

            <LiveFeedLog events={sockState.events} />
          </div>

          <div className="space-y-6">
            <CompletedDimensions completed={completedDims} />
            <CompositeScoring bestThisDimension={activeDimension ? bestThisDimension : null} />
            <BaselineContext
              rawComposite={benchBaseline?.rawComposite ?? null}
              challenges={benchBaseline?.challenges ?? 0}
              families={benchBaseline?.families ?? 0}
              thisFamilyBaseline={runDetail?.baseline_fitness ?? null}
              loading={benchData === undefined}
            />
            <PerDimensionPipeline
              challengeDesigned={challenges.length > 0}
              variantsSpawned={variantGroups.length >= 2}
              competitorsFinished={sockState.finishedCompetitors >= 2}
              scored={sockState.currentJudgingLayer >= 5}
              winnerPicked={sockState.generations.at(-1)?.status === "complete"}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

interface CurrentChallengeProps {
  challenge: { difficulty: string; prompt: string };
}

function CurrentChallenge({ challenge }: CurrentChallengeProps) {
  const difficultyClass =
    challenge.difficulty === "hard"
      ? "bg-error/10 text-error"
      : challenge.difficulty === "medium"
        ? "bg-warning/10 text-warning"
        : "bg-tertiary/10 text-tertiary";
  return (
    <div className="flex items-start gap-3 rounded-xl border border-outline-variant bg-surface-container-lowest px-5 py-4">
      <span
        className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 font-mono text-[0.5625rem] uppercase tracking-wider ${difficultyClass}`}
      >
        {challenge.difficulty}
      </span>
      <p className="text-sm leading-relaxed text-on-surface">{challenge.prompt}</p>
    </div>
  );
}

interface CompetitionPanelProps {
  variantGroups: {
    variantIndex: number;
    skillId: string;
    competitorId: number;
    competitors: CompetitorView[];
  }[];
  challenges: { id: string; difficulty: string; prompt: string; index: number }[];
}

function CompetitionPanel({ variantGroups, challenges }: CompetitionPanelProps) {
  const labels = ["Baseline (Raw Sonnet)", "Seed (V1)", "Spawn (V2)"];
  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-xl tracking-tight">Competition</h2>
          <p className="mt-0.5 text-xs text-on-surface-dim">
            Baseline vs seed vs spawn — scored with 6-layer composite.
          </p>
        </div>
        <span className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          {variantGroups.length > 0 ? `${variantGroups.length} competitors` : "waiting"}
        </span>
      </div>
      <div className="mt-4 space-y-2">
        {variantGroups.length === 0 ? (
          <div className="flex items-center gap-3 py-4">
            <div className="h-2.5 w-2.5 shrink-0 animate-pulse rounded-full bg-primary" />
            <p className="text-sm text-on-surface-dim">
              Generating skill variants — each variant is a complete SKILL.md package with scripts,
              references, and examples. This typically takes 1-2 minutes per dimension.
            </p>
          </div>
        ) : (
          [...variantGroups]
            .reverse()
            .map((g) => (
              <SkillVariantCard
                key={g.skillId}
                variantIndex={g.variantIndex}
                skillId={g.skillId}
                isControl={g.competitorId === 0}
                competitors={g.competitors}
                challenges={challenges}
                label={labels[g.competitorId] ?? `Variant ${g.competitorId}`}
                controlLabel="SKLD-bench"
              />
            ))
        )}
      </div>
    </div>
  );
}
