import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import AtomicRunDetail from "./AtomicRunDetail";
import AtomicSidebar from "./AtomicSidebar";
import BreedingReport from "./BreedingReport";
import LiveFeedLog from "./LiveFeedLog";
import SkillVariantCard from "./SkillVariantCard";
import StatusGlow from "./StatusGlow";
import { useEvolutionSocket } from "../hooks/useEvolutionSocket";
import type { BenchSummary, CompetitorView, DimensionStatus, RunDetail } from "../types";

export default function EvolutionArena() {
  const { runId } = useParams<{ runId: string }>();
  const [runDetail, setRunDetail] = useState<RunDetail | null>(null);
  const [dimensions, setDimensions] = useState<DimensionStatus[]>([]);
  const [benchBaseline, setBenchBaseline] = useState<{
    rawComposite: number | null;
    families: number;
    challenges: number;
  } | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const startTime = useState(() => Date.now())[0];

  // Fetch run detail once on mount
  useEffect(() => {
    if (!runId) return;
    // For the permanent demo, ensure it's running before fetching
    if (runId === "demo-live") {
      fetch("/api/debug/demo", { method: "POST" }).catch(() => {});
    }
    fetch(`/api/runs/${runId}`)
      .then((r) => r.json())
      .then((d: RunDetail) => setRunDetail(d))
      .catch(() => undefined);
  }, [runId]);

  // Fetch dimension status for atomic runs
  useEffect(() => {
    if (!runId) return;
    fetch(`/api/runs/${runId}/dimensions`)
      .then((r) => {
        if (!r.ok) return [];
        return r.json() as Promise<DimensionStatus[]>;
      })
      .then(setDimensions)
      .catch(() => setDimensions([]));
  }, [runId]);

  // Fetch bench baseline data (once)
  useEffect(() => {
    fetch("/api/bench/summary")
      .then((r) => r.ok ? r.json() as Promise<BenchSummary> : null)
      .then((data) => {
        if (data?.overall) {
          setBenchBaseline({
            rawComposite: data.overall.raw_composite ?? null,
            families: data.families.length,
            challenges: data.overall.challenges,
          });
        }
      })
      .catch(() => {});
  }, []);

  // Poll dimensions while run is active (every 5s)
  useEffect(() => {
    if (!runId || runDetail?.status === "complete" || runDetail?.status === "failed") return;
    const id = setInterval(() => {
      fetch(`/api/runs/${runId}/dimensions`)
        .then((r) => r.ok ? r.json() as Promise<DimensionStatus[]> : [])
        .then(setDimensions)
        .catch(() => {});
    }, 5000);
    return () => clearInterval(id);
  }, [runId, runDetail?.status]);

  const runAlreadyDone =
    runDetail?.status === "complete" || runDetail?.status === "failed";

  // Only open the WebSocket for runs that are still active
  const sockState = useEvolutionSocket(
    runAlreadyDone ? null : (runId ?? null),
  );

  const isComplete = sockState.isComplete || runDetail?.status === "complete";
  const isFailed = sockState.isFailed || runDetail?.status === "failed";

  // Tick elapsed timer
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

  // For demo/fake runs, build DimensionStatus[] from socket events
  const effectiveDimensions = useMemo(() => {
    if (dimensions.length > 0) return dimensions;
    // Fallback: build from socket state for demo runs
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
  }, [dimensions, sockState.atomicDimensions]);

  // Derive which dimension is currently running
  const activeDimension = useMemo(() => {
    const running = effectiveDimensions.find((d) => d.status === "running");
    if (running) return running.dimension;
    return sockState.activeDimension ?? null;
  }, [effectiveDimensions, sockState.activeDimension]);

  const completedDims = effectiveDimensions.filter((d) => d.status === "complete").length;
  const totalDims = effectiveDimensions.length;

  // --- All hooks above this line ---

  if (!runId) return null;

  // Completed runs → AtomicRunDetail showcase
  if (isComplete) {
    return <AtomicRunDetail runId={runId} runDetail={runDetail!} dimensions={effectiveDimensions} />;
  }

  const showBreeding = !!sockState.latestBreedingReport;
  const elapsedFmt = `${Math.floor(elapsed / 60)
    .toString()
    .padStart(2, "0")}:${(elapsed % 60).toString().padStart(2, "0")}`;
  const budgetCap = 10;

  // --- Atomic in-progress layout ---
  return (
      <div className="flex">
        <AtomicSidebar
          runId={runId}
          dimensions={effectiveDimensions}
          activeDimension={activeDimension}
        />

        <div className="flex-1 px-8 py-6">
          {/* Header */}
          <div className="flex items-start justify-between gap-6">
            <div className="min-w-0 flex-1">
              <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-primary">
                {activeDimension
                  ? `Dimension ${completedDims + 1} of ${totalDims} · ${activeDimension.replace(/-/g, " ")}`
                  : `Evolving ${totalDims} dimensions`}
              </p>
              <h1 className="mt-2 font-display text-3xl leading-tight tracking-tight md:text-4xl">
                {specialization || "Atomic Evolution"}
              </h1>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 font-mono text-[0.625rem] uppercase tracking-wider ${
                  isFailed ? "bg-error/15 text-error" : "bg-tertiary/15 text-tertiary"
                }`}>
                  <StatusGlow variant={isFailed ? "error" : "success"} />
                  {isFailed ? "FAILED" : "RUNNING"}
                </span>
                <span className="font-mono text-[0.6875rem] text-on-surface-dim">
                  {completedDims}/{totalDims} dimensions
                </span>
              </div>
            </div>
            <div className="flex flex-col items-end gap-3">
              <div className="text-right">
                <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                  Elapsed
                </p>
                <p className="font-display text-2xl tracking-tight">{elapsedFmt}</p>
                <p className="mt-2 font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                  Budget Used
                </p>
                <p className="font-mono text-sm text-tertiary">
                  ${sockState.totalCostUsd.toFixed(2)} / ${budgetCap.toFixed(2)}
                </p>
              </div>
              {!isComplete && !isFailed && (
                <button
                  onClick={async () => {
                    if (!window.confirm("Cancel this run? Completed dimensions will be saved.")) return;
                    try {
                      const res = await fetch(`/api/runs/${runId}/cancel`, { method: "POST" });
                      if (!res.ok) alert(`Cancel failed: ${await res.text()}`);
                    } catch (err) {
                      alert(`Cancel error: ${String(err)}`);
                    }
                  }}
                  className="rounded-lg border border-error/40 bg-surface-container-lowest px-3 py-1.5 text-xs font-medium text-error transition-colors hover:bg-error/10"
                >
                  Cancel Run
                </button>
              )}
            </div>
          </div>

          {/* Connection/error banners */}
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
            {/* Main column */}
            <div className="space-y-6">
              {/* Phase status — shows what the engine is doing during long waits */}
              {(() => {
                const activeDim = sockState.atomicDimensions.find(
                  (d) => d.dimension === activeDimension,
                );
                if (!activeDim?.phaseDetail) return null;
                // Don't show once competitors are running
                if (variantGroups.length > 0) return null;
                return (
                  <div className="flex items-center gap-3 rounded-xl border border-primary/20 bg-primary/5 px-5 py-4">
                    <div className="h-2.5 w-2.5 shrink-0 animate-pulse rounded-full bg-primary" />
                    <p className="text-sm text-on-surface">
                      {activeDim.phaseDetail}
                    </p>
                  </div>
                );
              })()}

              {/* Current challenge — single card, not a list */}
              {challenges.length > 0 && (() => {
                const ch = challenges[challenges.length - 1];
                return (
                  <div className="flex items-start gap-3 rounded-xl border border-outline-variant bg-surface-container-lowest px-5 py-4">
                    <span
                      className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 font-mono text-[0.5625rem] uppercase tracking-wider ${
                        ch.difficulty === "hard"
                          ? "bg-error/10 text-error"
                          : ch.difficulty === "medium"
                            ? "bg-warning/10 text-warning"
                            : "bg-tertiary/10 text-tertiary"
                      }`}
                    >
                      {ch.difficulty}
                    </span>
                    <p className="text-sm leading-relaxed text-on-surface">
                      {ch.prompt}
                    </p>
                  </div>
                );
              })()}

              {/* Competition */}
              <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="font-display text-xl tracking-tight">
                      Competition
                    </h2>
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
                    [...variantGroups].reverse().map((g) => {
                      const isBaseline = g.competitorId === 0;
                      const labels = ["Baseline (Raw Sonnet)", "Seed (V1)", "Spawn (V2)"];
                      return (
                        <SkillVariantCard
                          key={g.skillId}
                          variantIndex={g.variantIndex}
                          skillId={g.skillId}
                          isControl={isBaseline}
                          competitors={g.competitors}
                          challenges={challenges}
                          label={labels[g.competitorId] ?? `Variant ${g.competitorId}`}
                          controlLabel="SKLD-bench"
                        />
                      );
                    })
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

            {/* Right column: completed dimensions + judging */}
            <div className="space-y-6">
              {/* Completed dimensions summary */}
              {completedDims > 0 && (
                <div className="rounded-xl bg-surface-container-low p-5">
                  <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                    Completed Dimensions
                  </p>
                  <div className="mt-3 space-y-1.5">
                    {effectiveDimensions
                      .filter((d) => d.status === "complete")
                      .map((d) => (
                        <div key={d.id} className="flex items-center justify-between">
                          <span className="truncate text-xs capitalize text-on-surface-dim">
                            {d.dimension.replace(/-/g, " ")}
                          </span>
                          <span className="ml-2 shrink-0 font-mono text-[0.625rem] text-tertiary">
                            {d.fitness_score?.toFixed(2) ?? "—"}
                          </span>
                        </div>
                      ))}
                  </div>
                  <div className="mt-3 border-t border-outline-variant pt-3">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
                        Avg Fitness
                      </span>
                      <span className="font-mono text-sm text-tertiary">
                        {(
                          effectiveDimensions
                            .filter((d) => d.status === "complete" && d.fitness_score != null)
                            .reduce((sum, d) => sum + (d.fitness_score ?? 0), 0) /
                          Math.max(completedDims, 1)
                        ).toFixed(3)}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Composite Scoring */}
              <div className="rounded-xl bg-surface-container-low p-5">
                <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                  Composite Scoring
                </p>
                <p className="mt-1.5 text-[0.6875rem] leading-relaxed text-on-surface-dim">
                  Each variant is scored through 6 layers, weighted into one composite fitness.
                </p>
                <div className="mt-3 space-y-1.5">
                  {[
                    { label: "Behavioral Tests", weight: "40%", desc: "ExUnit — does the code work?" },
                    { label: "Compilation", weight: "15%", desc: "mix compile — does it build?" },
                    { label: "AST Quality", weight: "15%", desc: "Structure, coverage, pipes" },
                    { label: "String Match", weight: "10%", desc: "L0 expected patterns" },
                    { label: "Template", weight: "10%", desc: "Modern HEEx idioms" },
                    { label: "Brevity", weight: "10%", desc: "Conciseness" },
                  ].map((layer) => (
                    <div key={layer.label} className="flex items-center gap-2">
                      <span className="w-8 shrink-0 text-right font-mono text-[0.5625rem] text-tertiary">
                        {layer.weight}
                      </span>
                      <span className="text-xs text-on-surface">{layer.label}</span>
                      <span className="ml-auto text-[0.5625rem] text-on-surface-dim">{layer.desc}</span>
                    </div>
                  ))}
                </div>
                {activeDimension && sockState.generations.at(-1)?.best_fitness != null && (
                  <div className="mt-3 border-t border-outline-variant pt-3">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
                        Best This Dimension
                      </span>
                      <span className="font-mono text-sm text-tertiary">
                        {sockState.generations.at(-1)!.best_fitness!.toFixed(3)}
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* Baseline Context */}
              <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5">
                <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                  Baseline — Raw Sonnet
                </p>
                <p className="mt-1.5 text-[0.6875rem] leading-relaxed text-on-surface-dim">
                  What Claude Sonnet scores with no skill on the same challenges.
                  The goal: evolved skill consistently beats baseline.
                </p>
                {benchBaseline ? (
                  <div className="mt-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-on-surface-dim">Raw Composite</span>
                      <span className="font-mono text-sm text-on-surface">
                        {benchBaseline.rawComposite?.toFixed(3) ?? "—"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-on-surface-dim">Challenges</span>
                      <span className="font-mono text-sm text-on-surface">
                        {benchBaseline.challenges}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-on-surface-dim">Families</span>
                      <span className="font-mono text-sm text-on-surface">
                        {benchBaseline.families}
                      </span>
                    </div>
                    {runDetail?.baseline_fitness != null && (
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-on-surface-dim">This Family Baseline</span>
                        <span className="font-mono text-sm text-on-surface">
                          {runDetail.baseline_fitness.toFixed(3)}
                        </span>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="mt-3 text-xs text-on-surface-dim">Loading baseline data...</p>
                )}
              </div>

              {/* Per-dimension pipeline steps */}
              <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5">
                <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                  Per-Dimension Pipeline
                </p>
                <div className="mt-3 space-y-1.5">
                  {[
                    { step: "1", label: "Design focused challenge", done: challenges.length > 0 },
                    { step: "2", label: "Spawn seed + alternative", done: variantGroups.length >= 2 },
                    { step: "3", label: "Compete on challenge", done: sockState.finishedCompetitors >= 2 },
                    { step: "4", label: "Score (6-layer composite)", done: sockState.currentJudgingLayer >= 5 },
                    { step: "5", label: "Pick winner", done: sockState.generations.at(-1)?.status === "complete" },
                  ].map((s) => (
                    <div key={s.step} className="flex items-center gap-2">
                      <span className={`flex h-5 w-5 items-center justify-center rounded-full text-[0.5625rem] font-bold ${
                        s.done ? "bg-tertiary/20 text-tertiary" : "bg-surface-container-high text-on-surface-dim"
                      }`}>
                        {s.done ? "✓" : s.step}
                      </span>
                      <span className={`text-xs ${s.done ? "text-on-surface-dim" : "text-on-surface"}`}>
                        {s.label}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
}
