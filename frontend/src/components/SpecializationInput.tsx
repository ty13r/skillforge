import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import ParameterInput from "./ParameterInput";
import PrimaryButton from "./PrimaryButton";
import SkillUploader from "./SkillUploader";
import SpecAssistantChat from "./SpecAssistantChat";
import type { EvolveRequest, EvolveResponse } from "../types";

type SourceMode = "scratch" | "upload" | "fork";

interface UploadResponse {
  upload_id: string | null;
  filename: string;
  valid: boolean;
  frontmatter?: Record<string, unknown>;
  skill_md_content?: string;
  supporting_files?: string[];
  errors?: string[];
}

interface SeedSummary {
  id: string;
  title: string;
  description: string;
  category: string;
  difficulty: "easy" | "medium" | "hard";
}

const DIFFICULTY_COLOR: Record<string, string> = {
  easy: "text-tertiary",
  medium: "text-warning",
  hard: "text-error",
};

const SOURCE_MODES: { value: SourceMode; label: string; hint: string }[] = [
  {
    value: "scratch",
    label: "From Scratch",
    hint: "Describe a domain and evolve a new Skill from the golden template.",
  },
  {
    value: "upload",
    label: "Upload Existing",
    hint: "Bring your own SKILL.md (or zipped Skill dir) and evolve it forward.",
  },
  {
    value: "fork",
    label: "Fork from Registry",
    hint: "Pick a curated Gen 0 Skill from the library as your starting point.",
  },
];

export default function SpecializationInput() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const seedParam = searchParams.get("seed");

  const [sourceMode, setSourceMode] = useState<SourceMode>(
    seedParam ? "fork" : "scratch",
  );
  const [specialization, setSpecialization] = useState("");
  const [populationSize, setPopulationSize] = useState(5);
  const [numGenerations, setNumGenerations] = useState(3);
  const [budget, setBudget] = useState(10);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [forkedSeed, setForkedSeed] = useState<SeedSummary | null>(null);
  const [allSeeds, setAllSeeds] = useState<SeedSummary[] | null>(null);
  const [seedCategoryFilter, setSeedCategoryFilter] = useState<string>("all");

  // Fetch all seeds once — used by both the ?seed=<id> auto-select path
  // AND the inline picker grid when fork mode is active.
  useEffect(() => {
    fetch("/api/seeds")
      .then((r) => r.json() as Promise<SeedSummary[]>)
      .then((seeds) => {
        setAllSeeds(seeds);
        if (seedParam) {
          const match = seeds.find((s) => s.id === seedParam);
          if (match) {
            setForkedSeed(match);
            setSpecialization(match.description);
          }
        }
      })
      .catch(() => setAllSeeds([]));
  }, [seedParam]);

  const seedCategories = allSeeds
    ? ["all", ...Array.from(new Set(allSeeds.map((s) => s.category)))]
    : ["all"];

  const visibleSeeds =
    allSeeds?.filter(
      (s) => seedCategoryFilter === "all" || s.category === seedCategoryFilter,
    ) ?? [];

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      let res: Response;
      if (sourceMode === "scratch") {
        if (!specialization.trim()) {
          throw new Error("Specialization is required");
        }
        const body: EvolveRequest = {
          mode: "domain",
          specialization,
          population_size: populationSize,
          num_generations: numGenerations,
          max_budget_usd: budget,
        };
        res = await fetch("/api/evolve", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      } else if (sourceMode === "upload") {
        if (!upload?.upload_id) {
          throw new Error("Upload a valid SKILL.md or zip first");
        }
        res = await fetch("/api/evolve/from-parent", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            parent_source: "upload",
            parent_id: upload.upload_id,
            specialization: specialization || undefined,
            population_size: populationSize,
            num_generations: numGenerations,
            max_budget_usd: budget,
          }),
        });
      } else {
        // fork
        if (!forkedSeed) {
          throw new Error("No seed selected to fork");
        }
        res = await fetch("/api/evolve/from-parent", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            parent_source: "registry",
            parent_id: forkedSeed.id,
            specialization: specialization || undefined,
            population_size: populationSize,
            num_generations: numGenerations,
            max_budget_usd: budget,
          }),
        });
      }

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status}: ${text}`);
      }
      const data = (await res.json()) as EvolveResponse;
      navigate(`/runs/${data.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-primary">
        Protocol: New Evolution
      </p>
      <h1 className="mt-2 font-display text-4xl tracking-tight">
        Start an Evolution Run
      </h1>

      {/* Source mode toggle */}
      <div className="mt-8">
        <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          Starting Point
        </p>
        <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-3">
          {SOURCE_MODES.map((m) => {
            const selected = sourceMode === m.value;
            return (
              <button
                key={m.value}
                onClick={() => setSourceMode(m.value)}
                className={`rounded-xl border p-4 text-left transition-all ${
                  selected
                    ? "border-primary bg-primary/5 ring-1 ring-primary/40"
                    : "border-outline-variant bg-surface-container-lowest hover:border-primary/40"
                }`}
              >
                <p
                  className={`font-display text-sm tracking-tight ${selected ? "text-primary" : "text-on-surface"}`}
                >
                  {m.label}
                </p>
                <p className="mt-1 text-xs text-on-surface-dim">{m.hint}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Source-specific body */}
      {sourceMode === "scratch" && (
        <div className="mt-6">
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Specialization Blueprint
          </p>
          <textarea
            value={specialization}
            onChange={(e) => setSpecialization(e.target.value)}
            placeholder="Describe the target evolution... e.g., Cleans messy pandas DataFrames — handling missing values, near-duplicate rows, and mixed-type columns. Use when user mentions data cleaning or dedupe. NOT for SQL."
            rows={6}
            className="mt-2 w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-4 font-mono text-sm text-on-surface placeholder:text-on-surface-dim/60 focus:border-primary focus:outline-none"
          />
          <SpecAssistantChat onSpecReady={setSpecialization} />
        </div>
      )}

      {sourceMode === "upload" && (
        <div className="mt-6 space-y-4">
          <SkillUploader onUploadReady={setUpload} current={upload} />
          {upload?.valid && (
            <div>
              <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                Optional: override the specialization
              </p>
              <input
                type="text"
                value={specialization}
                onChange={(e) => setSpecialization(e.target.value)}
                placeholder="(inherits from the uploaded SKILL.md frontmatter)"
                className="mt-2 w-full rounded-xl border border-outline-variant bg-surface-container-lowest px-4 py-2.5 text-sm text-on-surface placeholder:text-on-surface-dim focus:border-primary focus:outline-none"
              />
            </div>
          )}
        </div>
      )}

      {sourceMode === "fork" && (
        <div className="mt-6 space-y-4">
          {forkedSeed ? (
            <>
              <div className="flex items-start justify-between rounded-xl border border-primary/40 bg-primary/5 p-5">
                <div>
                  <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-primary">
                    ⑂ Forking from
                  </p>
                  <p className="mt-1 font-display text-xl tracking-tight">
                    {forkedSeed.title}
                  </p>
                  <p className="mt-2 max-w-2xl text-sm text-on-surface-dim">
                    {forkedSeed.description}
                  </p>
                </div>
                <button
                  onClick={() => {
                    setForkedSeed(null);
                    setSpecialization("");
                  }}
                  className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim transition-colors hover:text-on-surface"
                >
                  Change
                </button>
              </div>
              <div>
                <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                  Optional: override the specialization
                </p>
                <textarea
                  value={specialization}
                  onChange={(e) => setSpecialization(e.target.value)}
                  rows={3}
                  className="mt-2 w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-3 font-mono text-sm text-on-surface placeholder:text-on-surface-dim/60 focus:border-primary focus:outline-none"
                />
              </div>
            </>
          ) : (
            <>
              {/* Category filter chips */}
              {allSeeds && allSeeds.length > 0 && (
                <div className="flex flex-wrap gap-1 rounded-xl border border-outline-variant bg-surface-container-lowest p-1">
                  {seedCategories.map((cat) => (
                    <button
                      key={cat}
                      onClick={() => setSeedCategoryFilter(cat)}
                      className={`rounded-lg px-3 py-1.5 font-mono text-[0.6875rem] uppercase tracking-wider transition-colors ${
                        seedCategoryFilter === cat
                          ? "bg-primary/15 text-primary"
                          : "text-on-surface-dim hover:text-on-surface"
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              )}

              {/* Seed picker grid */}
              {allSeeds == null ? (
                <p className="text-on-surface-dim">Loading seed library…</p>
              ) : visibleSeeds.length === 0 ? (
                <p className="text-on-surface-dim">No seeds match the filter.</p>
              ) : (
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  {visibleSeeds.map((seed) => (
                    <button
                      key={seed.id}
                      onClick={() => {
                        setForkedSeed(seed);
                        setSpecialization(seed.description);
                      }}
                      className="group flex flex-col rounded-xl border border-outline-variant bg-surface-container-lowest p-4 text-left transition-all hover:border-primary/40 hover:shadow-elevated"
                    >
                      <div className="flex items-start justify-between">
                        <span className="rounded-full bg-primary/10 px-2 py-0.5 font-mono text-[0.5625rem] uppercase tracking-wider text-primary">
                          {seed.category}
                        </span>
                        <span
                          className={`font-mono text-[0.5625rem] uppercase tracking-wider ${DIFFICULTY_COLOR[seed.difficulty]}`}
                        >
                          {seed.difficulty}
                        </span>
                      </div>
                      <p className="mt-2 font-display text-base tracking-tight group-hover:text-primary">
                        {seed.title}
                      </p>
                      <p className="mt-1 line-clamp-2 text-xs text-on-surface-dim">
                        {seed.description}
                      </p>
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Parameters */}
      <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
        <ParameterInput
          label="Population Size"
          value={populationSize}
          onChange={setPopulationSize}
          min={2}
          max={20}
        />
        <ParameterInput
          label="Generations"
          value={numGenerations}
          onChange={setNumGenerations}
          min={1}
          max={10}
        />
        <ParameterInput
          label="Budget Cap"
          value={budget}
          onChange={setBudget}
          min={1}
          step={1}
          prefix="$"
          accent="tertiary"
        />
      </div>

      {error && (
        <div className="mt-4 rounded-xl bg-error/10 p-3 text-sm text-error">
          {error}
        </div>
      )}

      {(() => {
        // Calibrated from observed live runs:
        //   • 5 pop × 3 gen × 3 challenges = 53 min, ~$7.50
        //   • 2 pop × 1 gen × 1 challenge = 9 min, ~$2.00
        // Backend hardcodes num_challenges=3. Competitors run sequentially
        // (COMPETITOR_CONCURRENCY=1) due to the Agent SDK subprocess race.
        const CHALLENGES_PER_GEN = 3;
        const MIN_PER_COMPETITOR_RUN = 0.95;
        const USD_PER_COMPETITOR_RUN = 0.11;
        const SETUP_MIN = 5; // challenge design + spawn startup
        const BREEDING_MIN_PER_GEN = 2;
        const SETUP_USD = 1.0;
        const BREEDING_USD_PER_GEN = 0.5;

        const competitorRuns =
          populationSize * numGenerations * CHALLENGES_PER_GEN;
        const estMin = Math.round(
          competitorRuns * MIN_PER_COMPETITOR_RUN +
            SETUP_MIN +
            numGenerations * BREEDING_MIN_PER_GEN,
        );
        const estUsd =
          competitorRuns * USD_PER_COMPETITOR_RUN +
          SETUP_USD +
          numGenerations * BREEDING_USD_PER_GEN;
        const estTimeLabel =
          estMin >= 90
            ? `~${(estMin / 60).toFixed(1)} hrs`
            : `~${estMin} min`;
        const overBudget = estUsd > budget;

        return (
          <div className="mt-8 rounded-xl border border-outline-variant bg-surface-container-low p-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex gap-6">
                <div>
                  <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                    Est. Compute Time
                  </p>
                  <p className="font-mono text-sm text-on-surface">
                    {estTimeLabel}
                  </p>
                </div>
                <div>
                  <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                    Est. Compute Cost
                  </p>
                  <p
                    className={`font-mono text-sm ${overBudget ? "text-error" : "text-on-surface"}`}
                  >
                    ~${estUsd.toFixed(2)}
                  </p>
                </div>
                <div>
                  <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                    Competitor Runs
                  </p>
                  <p className="font-mono text-sm text-on-surface">
                    {competitorRuns} ({populationSize}×{numGenerations}×
                    {CHALLENGES_PER_GEN})
                  </p>
                </div>
              </div>
              <PrimaryButton onClick={submit} disabled={submitting}>
                {submitting ? "Starting..." : "Start Evolution →"}
              </PrimaryButton>
            </div>
            {overBudget && (
              <p className="mt-3 font-mono text-[0.6875rem] text-error">
                ⚠ Estimated cost exceeds your ${budget} budget cap. The run
                will abort when the cap is hit — increase the cap or reduce
                population/generations.
              </p>
            )}
          </div>
        );
      })()}
    </div>
  );
}
