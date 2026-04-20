import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useSeeds } from "@/api/hooks/seeds";

import InviteGate from "./InviteGate";
import ParameterInput from "./ParameterInput";
import SkillUploader from "./SkillUploader";
import SpecAssistantChat from "./SpecAssistantChat";
import EvolutionModePicker from "./specializationInput/EvolutionModePicker";
import RunEstimateCard from "./specializationInput/RunEstimateCard";
import SeedPicker from "./specializationInput/SeedPicker";
import SourceModePicker from "./specializationInput/SourceModePicker";
import { estimateCost } from "./specializationInput/estimateCost";
import { startEvolution } from "./specializationInput/startEvolution";
import type {
  EvolutionMode,
  GeneratedPackage,
  SeedSummary,
  SourceMode,
  UploadResponse,
} from "./specializationInput/types";
import { DIFFICULTY_COLOR } from "./specializationInput/types";

/**
 * "Start an Evolution Run" form.
 *
 * Orchestrates three source modes (from scratch / upload / fork registry),
 * four parameter knobs, and the run-estimate footer. The fetch layer, form
 * sub-views, and pure estimators live in ``specializationInput/*`` so this
 * file stays focused on state composition and the submit flow.
 */
export default function SpecializationInput() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const seedParam = searchParams.get("seed");

  const [sourceMode, setSourceMode] = useState<SourceMode>(seedParam ? "fork" : "scratch");
  const [specialization, setSpecialization] = useState("");
  const [populationSize, setPopulationSize] = useState(5);
  const [numGenerations, setNumGenerations] = useState(3);
  const [budget, setBudget] = useState(10);
  const [evolutionMode, setEvolutionMode] = useState<EvolutionMode>("auto");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [forkedSeed, setForkedSeed] = useState<SeedSummary | null>(null);
  const [inviteCode, setInviteCode] = useState<string | null>(null);
  const [generatedPackage, setGeneratedPackage] = useState<GeneratedPackage | null>(null);

  const { data: allSeeds = null } = useSeeds();

  // Auto-select the seed named in ?seed=<id> as soon as the library loads.
  useEffect(() => {
    if (!seedParam || !allSeeds) return;
    const match = allSeeds.find((s) => s.id === seedParam);
    if (match) setForkedSeed(match);
  }, [seedParam, allSeeds]);

  const handleValidated = useCallback((code: string) => {
    setInviteCode(code);
  }, []);

  const estimate = useMemo(
    () => estimateCost({ populationSize, numGenerations }),
    [populationSize, numGenerations],
  );

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const runId = await startEvolution({
        sourceMode,
        specialization,
        populationSize,
        numGenerations,
        budget,
        evolutionMode,
        inviteCode,
        upload,
        forkedSeedId: forkedSeed?.id ?? null,
        generatedPackage,
      });
      navigate(`/runs/${runId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  };

  // Invite gate: no code yet => show gate. The gate handles its own
  // "already validated" fast-path via localStorage, so returning users
  // with a saved code see the form directly.
  if (inviteCode === null) {
    return <InviteGate onValidated={handleValidated} />;
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-primary">
        Protocol: New Evolution
      </p>
      <h1 className="mt-2 font-display text-4xl tracking-tight">Start an Evolution Run</h1>

      <div className="mt-8">
        <SourceModePicker value={sourceMode} onChange={setSourceMode} />
      </div>

      {sourceMode === "scratch" && (
        <ScratchBody
          specialization={specialization}
          onSpecChange={setSpecialization}
          onPackageReady={setGeneratedPackage}
        />
      )}

      {sourceMode === "upload" && (
        <UploadBody
          upload={upload}
          onUploadReady={setUpload}
          specialization={specialization}
          onSpecChange={setSpecialization}
        />
      )}

      {sourceMode === "fork" && (
        <ForkBody
          forkedSeed={forkedSeed}
          allSeeds={allSeeds}
          specialization={specialization}
          onSpecChange={setSpecialization}
          onPickSeed={setForkedSeed}
          onClearSeed={() => {
            setForkedSeed(null);
            setSpecialization("");
          }}
        />
      )}

      {generatedPackage && sourceMode === "scratch" && (
        <GeneratedPackageBanner
          fileCount={Object.keys(generatedPackage.supportingFiles).length + 1}
          onDiscard={() => setGeneratedPackage(null)}
        />
      )}

      <div className="mt-6">
        <EvolutionModePicker value={evolutionMode} onChange={setEvolutionMode} />
      </div>

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

      {error && <div className="mt-4 rounded-xl bg-error/10 p-3 text-sm text-error">{error}</div>}

      <RunEstimateCard
        estimate={estimate}
        budget={budget}
        populationSize={populationSize}
        numGenerations={numGenerations}
        submitting={submitting}
        onSubmit={submit}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inline source-mode bodies. Small enough that their state is already lifted
// to the parent — extracting them as full sub-components would trade one
// level of indirection for two.
// ---------------------------------------------------------------------------

interface ScratchBodyProps {
  specialization: string;
  onSpecChange: (next: string) => void;
  onPackageReady: (pkg: GeneratedPackage) => void;
}

function ScratchBody({ specialization, onSpecChange, onPackageReady }: ScratchBodyProps) {
  return (
    <div className="mt-6">
      <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
        Specialization Blueprint
      </p>
      <textarea
        value={specialization}
        onChange={(e) => onSpecChange(e.target.value)}
        placeholder="What should this skill do? e.g., 'Write pytest unit tests for Python code' or 'Review pull requests for security issues' — or click Generate Skill with AI to build one interactively."
        rows={6}
        className="mt-2 w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-4 font-mono text-sm text-on-surface placeholder:text-on-surface-dim/60 focus:border-primary focus:outline-none"
      />
      <SpecAssistantChat onSpecReady={onSpecChange} onPackageReady={onPackageReady} />
    </div>
  );
}

interface UploadBodyProps {
  upload: UploadResponse | null;
  onUploadReady: (next: UploadResponse | null) => void;
  specialization: string;
  onSpecChange: (next: string) => void;
}

function UploadBody({ upload, onUploadReady, specialization, onSpecChange }: UploadBodyProps) {
  return (
    <div className="mt-6 space-y-4">
      <SkillUploader onUploadReady={onUploadReady} current={upload} />
      {upload?.valid && (
        <div>
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Optional: override the specialization
          </p>
          <input
            type="text"
            value={specialization}
            onChange={(e) => onSpecChange(e.target.value)}
            placeholder="(inherits from the uploaded SKILL.md frontmatter)"
            className="mt-2 w-full rounded-xl border border-outline-variant bg-surface-container-lowest px-4 py-2.5 text-sm text-on-surface placeholder:text-on-surface-dim focus:border-primary focus:outline-none"
          />
        </div>
      )}
    </div>
  );
}

interface ForkBodyProps {
  forkedSeed: SeedSummary | null;
  allSeeds: SeedSummary[] | null;
  specialization: string;
  onSpecChange: (next: string) => void;
  onPickSeed: (seed: SeedSummary) => void;
  onClearSeed: () => void;
}

function ForkBody({
  forkedSeed,
  allSeeds,
  specialization,
  onSpecChange,
  onPickSeed,
  onClearSeed,
}: ForkBodyProps) {
  return (
    <div className="mt-6 space-y-4">
      {forkedSeed ? (
        <>
          <div className="flex items-start justify-between rounded-xl border border-primary/40 bg-primary/5 p-5">
            <div>
              <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-primary">
                ⑂ Forking from
              </p>
              <p className="mt-1 font-display text-xl tracking-tight">{forkedSeed.title}</p>
              <p className="mt-1.5 inline-flex items-center gap-2">
                <span className="rounded-full bg-primary/10 px-2 py-0.5 font-mono text-[0.5625rem] uppercase tracking-wider text-primary">
                  {forkedSeed.category}
                </span>
                <span
                  className={`font-mono text-[0.5625rem] uppercase tracking-wider ${DIFFICULTY_COLOR[forkedSeed.difficulty]}`}
                >
                  {forkedSeed.difficulty}
                </span>
              </p>
            </div>
            <button
              onClick={onClearSeed}
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
              onChange={(e) => onSpecChange(e.target.value)}
              placeholder="(leave empty to inherit from the seed's specialization)"
              rows={3}
              className="mt-2 w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-3 font-mono text-sm text-on-surface placeholder:text-on-surface-dim/60 focus:border-primary focus:outline-none"
            />
          </div>
        </>
      ) : (
        <SeedPicker seeds={allSeeds} onPick={onPickSeed} />
      )}
    </div>
  );
}

interface GeneratedPackageBannerProps {
  fileCount: number;
  onDiscard: () => void;
}

function GeneratedPackageBanner({ fileCount, onDiscard }: GeneratedPackageBannerProps) {
  return (
    <div className="mt-4 rounded-xl border border-tertiary/30 bg-tertiary/5 p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-mono text-[0.625rem] uppercase tracking-wider text-tertiary">
            ✓ Skill Package Ready
          </p>
          <p className="mt-1 text-sm text-on-surface-dim">
            {fileCount} files will be used as the Gen 0 seed
          </p>
        </div>
        <button
          onClick={onDiscard}
          className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim transition-colors hover:text-on-surface"
        >
          Discard
        </button>
      </div>
    </div>
  );
}
