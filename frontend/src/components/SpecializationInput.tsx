import { useState } from "react";
import { useNavigate } from "react-router-dom";

import ModeCard from "./ModeCard";
import ParameterInput from "./ParameterInput";
import PrimaryButton from "./PrimaryButton";
import type { EvolveRequest, EvolveResponse, Mode } from "../types";

export default function SpecializationInput() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("domain");
  const [specialization, setSpecialization] = useState("");
  const [populationSize, setPopulationSize] = useState(5);
  const [numGenerations, setNumGenerations] = useState(3);
  const [budget, setBudget] = useState(10);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!specialization.trim()) {
      setError("Specialization is required");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const body: EvolveRequest = {
        mode,
        specialization,
        population_size: populationSize,
        num_generations: numGenerations,
        max_budget_usd: budget,
      };
      const res = await fetch("/evolve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status}: ${text}`);
      }
      const data = (await res.json()) as EvolveResponse;
      navigate(`/runs/${data.run_id}`);
    } catch (err) {
      setError(String(err));
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
        Project Alpha // Execution Mode R42
      </p>
      <h1 className="mt-2 font-display text-4xl tracking-tight">
        New Evolution Run
      </h1>

      {/* Mode selection */}
      <div className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-2">
        <ModeCard
          title="Domain Mode"
          description="Execute targeted evolution with specific domain specializations."
          selected={mode === "domain"}
          onClick={() => setMode("domain")}
          icon={<span className="font-display">D</span>}
        />
        <ModeCard
          title="Meta Mode"
          description="Define abstract skill-authoring patterns and cognitive frameworks."
          selected={mode === "meta"}
          disabled
          badge="v1.1"
          icon={<span className="font-display">M</span>}
        />
      </div>

      {/* Specialization textarea */}
      <div className="mt-6">
        <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          Specialization Blueprint
        </p>
        <textarea
          value={specialization}
          onChange={(e) => setSpecialization(e.target.value)}
          placeholder="Describe the target evolution... e.g., Optimizing Elixir OTP supervision trees for Phoenix LiveView high-concurrency state management in fintech applications"
          rows={6}
          className="mt-2 w-full rounded-xl bg-surface-container-lowest p-4 font-mono text-sm text-on-surface placeholder:text-on-surface-dim/60 focus:outline-none focus:ring-1 focus:ring-primary focus:shadow-glow"
        />
      </div>

      {/* Parameter row */}
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

      {/* Footer */}
      <div className="mt-8 flex items-center justify-between rounded-xl bg-surface-container-low p-4">
        <div className="flex gap-6">
          <div>
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
              Est. Compute Time
            </p>
            <p className="font-mono text-sm text-on-surface">
              ~{Math.round(populationSize * numGenerations * 1.2)} min
            </p>
          </div>
          <div>
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
              Est. Compute Cost
            </p>
            <p className="font-mono text-sm text-on-surface">
              ~${(populationSize * numGenerations * 0.3).toFixed(2)}
            </p>
          </div>
        </div>
        <PrimaryButton onClick={submit} disabled={submitting}>
          {submitting ? "Starting..." : "Start Evolution ✈"}
        </PrimaryButton>
      </div>
    </div>
  );
}
