import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import AtomicLineageView from "./AtomicLineageView";
import ChallengeGallery from "./ChallengeGallery";
import CompetitionBracket from "./CompetitionBracket";
import CompositeMarkdownView from "./CompositeMarkdownView";
import FitnessExplainer from "./FitnessExplainer";
import FitnessRadar from "./FitnessRadar";
import OverallAssessment from "./OverallAssessment";
import PackageExplorer from "./PackageExplorer";
import PerDimensionFitnessBar from "./PerDimensionFitnessBar";
import PipelineOverview from "./PipelineOverview";
import PrimaryButton from "./PrimaryButton";
import RunNarrative from "./RunNarrative";
import type {
  CompetitionScoresPayload,
  LineageEdge,
  LineageNode,
  RunDetail,
  RunReport,
  Variant,
} from "../types";

interface AtomicRunDetailProps {
  runId: string;
  runDetail: RunDetail;
}

type TabId =
  | "composite"
  | "competition"
  | "metrics"
  | "tests"
  | "narrative"
  | "lineage"
  | "package";

const TABS: { id: TabId; label: string }[] = [
  { id: "composite", label: "Composite" },
  { id: "competition", label: "Competition" },
  { id: "metrics", label: "Metrics" },
  { id: "tests", label: "Tests" },
  { id: "narrative", label: "Narrative" },
  { id: "lineage", label: "Lineage" },
  { id: "package", label: "Package" },
];

/**
 * Rich showcase page for atomic-mode evolution runs — restructured into a
 * sticky tab bar so only one large section is on screen at a time.
 *
 * Always visible:
 *   - Header (title, Gen 1 badge, fitness, cost, export buttons at top)
 *   - PipelineOverview (summary + pipeline diagram)
 *
 * Tabs:
 *   - Composite: the final composite SKILL.md
 *   - Competition: Gen 0 → Gen 1 bracket (12 matches)
 *   - Metrics: FitnessRadar (12 axes) + PerDimensionFitnessBar + explainer
 *   - Tests: ChallengeGallery
 *   - Narrative: RunNarrative with integration report
 *   - Lineage: AtomicLineageView (composite + 12 parent cards)
 */
export default function AtomicRunDetail({
  runId,
  runDetail,
}: AtomicRunDetailProps) {
  const [report, setReport] = useState<RunReport | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [variants, setVariants] = useState<Variant[] | null>(null);
  const [variantsError, setVariantsError] = useState<string | null>(null);
  const [lineage, setLineage] = useState<{
    nodes: LineageNode[];
    edges: LineageEdge[];
  } | null>(null);
  const [skillMd, setSkillMd] = useState<string | null>(null);
  const [skillMdError, setSkillMdError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("composite");

  // Fetch the report (includes skill_genomes array for atomic runs)
  useEffect(() => {
    if (!runId) return;
    fetch(`/api/runs/${runId}/report`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<RunReport>;
      })
      .then(setReport)
      .catch((err) => setReportError(String(err)));
  }, [runId]);

  // Fetch the variants list
  useEffect(() => {
    const familyId = runDetail.family_id;
    if (!familyId) return;
    fetch(`/api/families/${familyId}/variants`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<Variant[]>;
      })
      .then(setVariants)
      .catch((err) => setVariantsError(String(err)));
  }, [runDetail.family_id]);

  // Fetch the lineage graph
  useEffect(() => {
    if (!runId) return;
    fetch(`/api/runs/${runId}/lineage`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<{
          nodes: LineageNode[];
          edges: LineageEdge[];
        }>;
      })
      .then(setLineage)
      .catch(() => setLineage({ nodes: [], edges: [] }));
  }, [runId]);

  // Fetch the composite SKILL.md body
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

  // Hard-coded per the seed run's fitness_summary. The pre-existing seed
  // variant beat the Spawner alternative on these 3 dimensions out of 12.
  const seedWinnerDimensions = useMemo(
    () =>
      new Set<string>([
        "heex-and-verified-routes",
        "streams-and-collections",
        "navigation-patterns",
      ]),
    [],
  );

  // Radar axes: one per dimension, keyed to the variant fitness.
  const radarObjectives = useMemo(() => {
    if (!variants) return {};
    const out: Record<string, number> = {};
    for (const v of variants) {
      const short = v.dimension.replace(/-and-/g, " + ").replace(/-/g, " ");
      out[short] = v.fitness_score;
    }
    return out;
  }, [variants]);

  const strippedSpecialization = useMemo(
    () =>
      runDetail.specialization
        .replace(/\s*\[(mock|seed)_v[a-f0-9]+\]\s*/gi, " ")
        .trim(),
    [runDetail.specialization],
  );

  // Parse competition scores out of the learning_log if present.
  const competitionScores = useMemo<CompetitionScoresPayload | null>(() => {
    const log = runDetail.learning_log ?? report?.learning_log ?? [];
    const entry = log.find((e) => e.startsWith("[competition_scores] "));
    if (!entry) return null;
    try {
      return JSON.parse(entry.slice("[competition_scores] ".length));
    } catch {
      return null;
    }
  }, [runDetail.learning_log, report]);

  const totalCost = report?.metadata.total_cost_usd ?? runDetail.total_cost_usd;
  const durationMin =
    report?.metadata.duration_sec != null
      ? (report.metadata.duration_sec / 60).toFixed(1)
      : null;
  const genomes = report?.skill_genomes ?? [];

  return (
    <div className="mx-auto max-w-7xl px-8 py-10">
      {/* Hero header */}
      <div className="flex items-start justify-between gap-6">
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-tertiary">
            Protocol · Atomic Evolution · Generation 1
          </p>
          <h1 className="mt-2 font-display text-5xl leading-[1.05] tracking-tight">
            {report?.taxonomy?.family_label ?? runDetail.specialization}
          </h1>
          <p className="mt-3 max-w-3xl text-sm text-on-surface-dim">
            {strippedSpecialization}
          </p>
          <div className="mt-4 flex flex-wrap gap-2 font-mono text-[0.625rem] uppercase tracking-wider">
            <span className="rounded bg-green-500/10 px-2 py-1 text-green-400">
              {runDetail.status}
            </span>
            <span
              className="rounded bg-tertiary/10 px-2 py-1 text-tertiary"
              title={
                "This run has 1 generation. A re-evolution would produce Gen 2 seeded by this Gen 1 composite + newly-spawned alternatives."
              }
            >
              Gen {competitionScores?.generation ?? 1} /{" "}
              {competitionScores?.total_generations ?? 1}
            </span>
            <span className="rounded bg-surface-container-low px-2 py-1 text-on-surface-dim">
              {variants?.length ?? "—"} dimensions
            </span>
            <span className="rounded bg-surface-container-low px-2 py-1 text-on-surface-dim">
              {report?.challenges.length ?? "—"} tests
            </span>
            <span className="rounded bg-surface-container-low px-2 py-1 text-on-surface-dim">
              {genomes.length || "—"} genomes
            </span>
            {durationMin && (
              <span className="rounded bg-surface-container-low px-2 py-1 text-on-surface-dim">
                {durationMin} min wall clock
              </span>
            )}
          </div>
        </div>

        <div className="flex flex-col items-end gap-4">
          <div className="text-right">
            <p className="font-display text-6xl leading-none tracking-tight text-tertiary">
              {(runDetail.best_fitness ?? 0).toFixed(2)}
            </p>
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
              Best Fitness
            </p>
            <p className="mt-1 font-mono text-sm text-on-surface">
              ${totalCost.toFixed(2)}
            </p>
          </div>
          <div className="flex gap-2">
            <a
              href={`/api/runs/${runId}/export?format=skill_dir`}
              className="rounded bg-surface-container-low px-3 py-1.5 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface transition-colors hover:bg-surface-container-high"
            >
              ↓ .zip
            </a>
            <a
              href={`/api/runs/${runId}/export?format=agent_sdk_config`}
              target="_blank"
              rel="noreferrer"
              className="rounded bg-surface-container-low px-3 py-1.5 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface transition-colors hover:bg-surface-container-high"
            >
              ↓ SDK
            </a>
            <Link to={`/runs/${runId}/export`}>
              <PrimaryButton className="!px-3 !py-1.5 !text-[0.625rem]">
                Preview →
              </PrimaryButton>
            </Link>
          </div>
        </div>
      </div>

      {/* Overall assessment — plain-English 3-paragraph TL;DR. Always visible. */}
      {report && (
        <div className="mt-8">
          <OverallAssessment
            report={report}
            seedWinnerCount={seedWinnerDimensions.size}
            perfectFitnessCount={
              variants?.filter(
                (v) => v.tier === "capability" && v.fitness_score >= 0.999,
              ).length ?? 0
            }
          />
        </div>
      )}

      {/* Pipeline overview (always visible) */}
      {report && (
        <div className="mt-6">
          <PipelineOverview report={report} />
        </div>
      )}

      {/* Sticky tab bar */}
      <div className="sticky top-[64px] z-10 mt-8 -mx-2 bg-background/80 px-2 py-3 backdrop-blur-md">
        <div className="flex flex-wrap gap-1 rounded-xl border border-outline-variant bg-surface-container-lowest p-1">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 rounded-lg px-4 py-2 font-mono text-[0.625rem] uppercase tracking-wider transition-colors ${
                activeTab === tab.id
                  ? "bg-tertiary/20 text-tertiary"
                  : "text-on-surface-dim hover:bg-surface-container-high hover:text-on-surface"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Active tab content */}
      <div className="mt-8 min-h-[400px]">
        {activeTab === "composite" && (
          <CompositeMarkdownView
            skillMd={skillMd}
            skillMdError={skillMdError}
            bestSkillId={runDetail.best_skill_id ?? null}
          />
        )}

        {activeTab === "competition" && competitionScores && (
          <CompetitionBracket scores={competitionScores} genomes={genomes} />
        )}
        {activeTab === "competition" && !competitionScores && (
          <p className="text-xs text-on-surface-dim">
            Loading competition scores…
          </p>
        )}

        {activeTab === "metrics" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
                <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                  Fitness Radar — per dimension
                </p>
                <div className="mt-4" style={{ height: 380 }}>
                  <FitnessRadar objectives={radarObjectives} />
                </div>
              </div>
              <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
                <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                  Per-dimension fitness
                </p>
                <div className="mt-4">
                  {variants ? (
                    <PerDimensionFitnessBar
                      variants={variants}
                      seedWinnerDimensions={seedWinnerDimensions}
                    />
                  ) : (
                    <p className="text-xs text-on-surface-dim">
                      {variantsError ?? "Loading variants…"}
                    </p>
                  )}
                </div>
              </div>
            </div>
            <FitnessExplainer />
          </div>
        )}

        {activeTab === "tests" && report && (
          <ChallengeGallery challenges={report.challenges} />
        )}

        {activeTab === "narrative" && report && (
          <RunNarrative
            learningLog={runDetail.learning_log ?? report.learning_log}
            summary={report.summary}
          />
        )}

        {activeTab === "lineage" && lineage && (
          <AtomicLineageView
            nodes={lineage.nodes}
            edges={lineage.edges}
            genomes={genomes}
          />
        )}
        {activeTab === "lineage" && !lineage && (
          <p className="text-xs text-on-surface-dim">Loading lineage…</p>
        )}

        {activeTab === "package" && report && (
          <PackageExplorer
            compositeSkillMd={skillMd}
            genomes={genomes}
            challenges={report.challenges}
            learningLog={runDetail.learning_log ?? report.learning_log}
            runId={runId}
            familyLabel={
              report.taxonomy?.family_label ?? runDetail.specialization
            }
          />
        )}
        {activeTab === "package" && !report && (
          <p className="text-xs text-on-surface-dim">Loading package…</p>
        )}
      </div>

      {/* Error fallback */}
      {reportError && (
        <p className="mt-8 text-xs text-on-surface-dim">
          Report endpoint error: {reportError}
        </p>
      )}
    </div>
  );
}
