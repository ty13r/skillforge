import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import BreedingReport from "./BreedingReport";
import CompetitorCard from "./CompetitorCard";
import EvolutionResults from "./EvolutionResults";
import FitnessChart from "./FitnessChart";
import LiveFeedLog from "./LiveFeedLog";
import Sidebar from "./Sidebar";
import StatusGlow from "./StatusGlow";
import { derivePhases, useEvolutionSocket } from "../hooks/useEvolutionSocket";
import type { RunDetail } from "../types";

// Each judging layer with a human-readable sentence describing what it's
// actually scoring — so users don't see abstract "L1 Deterministic" but
// "L1 — Running the Skill's scripts against verification tests."
const JUDGING_LAYERS: { layer: string; label: string; description: string }[] = [
  {
    layer: "L1",
    label: "Deterministic Checks",
    description:
      "Running each candidate's scripts against verification tests. Does the code compile, execute, pass assertions?",
  },
  {
    layer: "L2",
    label: "Trigger Accuracy",
    description:
      "Batched LLM call: given 20 realistic user queries, does the frontmatter description correctly route to this Skill? (precision + recall)",
  },
  {
    layer: "L3",
    label: "Trace Analysis",
    description:
      "Reading each competitor's execution trace: did the Skill actually load? Which instructions did Claude follow vs ignore?",
  },
  {
    layer: "L4",
    label: "Pareto Ranking",
    description:
      "Pairwise comparison across all candidates. Builds a Pareto front where multiple winners coexist on different objectives.",
  },
  {
    layer: "L5",
    label: "Trait Attribution",
    description:
      "Maps each instruction in the SKILL.md to a fitness contribution. Surfaces which traits drove the win and which hurt.",
  },
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
    fetch(`/api/runs/${runId}`)
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

  // Derive the specialization from run_started event (fallback for fake runs
  // that aren't in the DB and won't load a runDetail).
  const specialization = useMemo(() => {
    if (runDetail?.specialization) return runDetail.specialization;
    const started = sockState.events.find((e) => e.event === "run_started");
    return (started?.specialization as string | undefined) ?? "";
  }, [runDetail, sockState.events]);

  // Collect all designed challenges with their prompts + difficulty. Keyed
  // by challenge_id so cards can cross-reference.
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

  // Expected number of (skill, challenge) competitor runs in the active gen
  const expectedCompetitors = useMemo(() => {
    const pop = runDetail?.population_size ?? 5;
    return pop * Math.max(challenges.length, 1);
  }, [runDetail, challenges.length]);

  // Judging layer that's currently active, if any. We don't get granular L1-L5
  // events, so when judging_started fires we treat L1 as running until
  // scores_published fires (which means all 5 have completed).
  const activeJudgingLayer = useMemo(() => {
    const gen = sockState.generations.at(-1);
    if (!gen) return null;
    if (gen.status === "judging") return "L1-L5";
    if (gen.status === "complete") return "done";
    return null;
  }, [sockState.generations]);

  // Compute phase states for the sidebar diagram
  const phases = useMemo(
    () => derivePhases(sockState, expectedCompetitors),
    [sockState, expectedCompetitors],
  );

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
        phases={phases}
      />

      <div className="flex-1 px-8 py-6">
        {/* Header — specialization is the headline, Evolution Cycle is the eyebrow */}
        <div className="flex items-start justify-between gap-6">
          <div className="min-w-0 flex-1">
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-primary">
              Evolving · Generation {sockState.currentGeneration + 1} of{" "}
              {runDetail?.num_generations ?? "?"}
            </p>
            <h1 className="mt-2 font-display text-3xl leading-tight tracking-tight md:text-4xl">
              {specialization || "Evolution Cycle"}
            </h1>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {runId.startsWith("fake-") && (
                <span className="rounded-full border border-primary/50 bg-primary/10 px-2.5 py-0.5 font-mono text-[0.625rem] uppercase tracking-wider text-primary">
                  DEMO
                </span>
              )}
              <span className="inline-flex items-center gap-1.5 rounded-full bg-tertiary/15 px-3 py-1 font-mono text-[0.625rem] uppercase tracking-wider text-tertiary">
                <StatusGlow variant="success" />
                {sockState.isFailed ? "FAILED" : "RUNNING"}
              </span>
              <span className="font-mono text-[0.6875rem] text-on-surface-dim">
                run {runId.slice(0, 8)}
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
            {!sockState.isComplete && !sockState.isFailed && (
              <button
                onClick={async () => {
                  if (
                    !window.confirm(
                      "Cancel this run? Any work completed so far will be saved, but no further generations will run.",
                    )
                  )
                    return;
                  try {
                    const res = await fetch(`/api/runs/${runId}/cancel`, {
                      method: "POST",
                    });
                    if (!res.ok) {
                      const text = await res.text();
                      alert(`Cancel failed: ${text}`);
                    }
                    // No further action — the WebSocket will receive
                    // run_cancelled and the UI reacts via sockState.isFailed
                  } catch (err) {
                    alert(`Cancel error: ${String(err)}`);
                  }
                }}
                className="rounded-lg border border-error/40 bg-surface-container-lowest px-3 py-1.5 text-xs font-medium text-error transition-colors hover:bg-error/10"
              >
                ✕ Cancel Run
              </button>
            )}
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
          {/* Main column: challenges + arena + breeding + log */}
          <div className="space-y-6">
            {/* Challenges Panel — what the skill is being tested against */}
            {challenges.length > 0 && (
              <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="font-display text-xl tracking-tight">
                      Test Gauntlet
                    </h2>
                    <p className="mt-0.5 text-xs text-on-surface-dim">
                      Every candidate is scored on all {challenges.length}{" "}
                      challenges.
                    </p>
                  </div>
                  <span className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                    {challenges.length} challenges
                  </span>
                </div>
                <div className="mt-4 space-y-3">
                  {challenges.map((ch) => {
                    // Is any competitor currently running this challenge?
                    const activeOnChallenge = sockState.competitors.some(
                      (c) => c.challengeId === ch.id && c.state !== "done",
                    );
                    return (
                      <div
                        key={ch.id}
                        className={`rounded-lg border p-3 transition-all ${
                          activeOnChallenge
                            ? "border-primary/40 bg-primary/5"
                            : "border-outline-variant bg-surface-container-low"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
                            Challenge {ch.index + 1}
                          </span>
                          <span
                            className={`rounded-full px-2 py-0.5 font-mono text-[0.5625rem] uppercase tracking-wider ${
                              ch.difficulty === "hard"
                                ? "bg-error/10 text-error"
                                : ch.difficulty === "medium"
                                  ? "bg-warning/10 text-warning"
                                  : "bg-tertiary/10 text-tertiary"
                            }`}
                          >
                            {ch.difficulty}
                          </span>
                          {activeOnChallenge && (
                            <span className="ml-auto font-mono text-[0.5625rem] uppercase tracking-wider text-primary">
                              ● live
                            </span>
                          )}
                        </div>
                        <p className="mt-2 text-sm leading-relaxed text-on-surface">
                          {ch.prompt || "(no prompt available)"}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Competitor Arena */}
            <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-display text-xl tracking-tight">
                    Competitor Arena
                  </h2>
                  <p className="mt-0.5 text-xs text-on-surface-dim">
                    Each competitor is a variant SKILL.md being tested against
                    the gauntlet.
                  </p>
                </div>
                <span className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                  {sockState.competitors.length} agents
                </span>
              </div>
              <div className="mt-4 space-y-2">
                {sockState.competitors.length === 0 ? (
                  <p className="text-sm text-on-surface-dim">
                    {phases.find((p) => p.id === "spawn_or_breed")?.status ===
                    "running"
                      ? sockState.currentGeneration === 0
                        ? `Spawning ${runDetail?.population_size ?? 5} diverse candidates from the golden template...`
                        : `Breeding ${runDetail?.population_size ?? 5} next-gen candidates from the Pareto front...`
                      : "Waiting for competitors to start..."}
                  </p>
                ) : (
                  sockState.competitors.map((c) => {
                    // Find the challenge this competitor is solving
                    const ch = challenges.find((x) => x.id === c.challengeId);
                    const challengeLabel = ch
                      ? `Challenge ${ch.index + 1}: ${ch.prompt.slice(0, 60)}${ch.prompt.length > 60 ? "…" : ""}`
                      : undefined;
                    return (
                      <CompetitorCard
                        key={`${c.competitorId}-${c.skillId}`}
                        competitorId={c.competitorId}
                        skillId={c.skillId}
                        state={c.state}
                        challengeId={c.challengeId}
                        challengeLabel={challengeLabel}
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

            <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5">
              <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                Judging Pipeline
              </p>
              <p className="mt-1 text-xs text-on-surface-dim">
                5 independent layers score every candidate from hard signals
                (L1) to trait attribution (L5).
              </p>
              <div className="mt-3 space-y-2">
                {JUDGING_LAYERS.map((l) => {
                  const genStatus = sockState.generations.at(-1)?.status;
                  const status =
                    genStatus === "complete"
                      ? "complete"
                      : activeJudgingLayer === "L1-L5"
                        ? "running"
                        : "pending";
                  return (
                    <div
                      key={l.layer}
                      className={`rounded-lg border p-2.5 transition-colors ${
                        status === "running"
                          ? "border-primary/40 bg-primary/5"
                          : status === "complete"
                            ? "border-tertiary/30 bg-tertiary/5"
                            : "border-outline-variant bg-surface-container-low"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className={`font-mono text-[0.625rem] font-bold uppercase tracking-wider ${
                            status === "running"
                              ? "text-primary"
                              : status === "complete"
                                ? "text-tertiary"
                                : "text-on-surface-dim"
                          }`}
                        >
                          {l.layer}
                        </span>
                        <span className="text-xs font-medium text-on-surface">
                          {l.label}
                        </span>
                        {status === "complete" && (
                          <span className="ml-auto text-[0.625rem] text-tertiary">
                            ✓
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-[0.6875rem] leading-relaxed text-on-surface-dim">
                        {l.description}
                      </p>
                    </div>
                  );
                })}
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
