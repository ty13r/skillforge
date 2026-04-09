import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import EvolutionCard from "./EvolutionCard";
import PrimaryButton from "./PrimaryButton";
import StatCard from "./StatCard";
import type { RunSummary } from "../types";

export default function EvolutionDashboard() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/runs")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<RunSummary[]>;
      })
      .then((data) => setRuns(data))
      .catch((err) => {
        setError(String(err));
        setRuns([]);
      });
  }, []);

  const totalRuns = runs?.length ?? 0;
  const completed = runs?.filter((r) => r.status === "complete") ?? [];
  const avgFitness =
    completed.length > 0
      ? completed
          .map((r) => r.best_fitness ?? 0)
          .reduce((a, b) => a + b, 0) / completed.length
      : 0;
  const totalSpent = (runs ?? []).reduce((sum, r) => sum + r.total_cost_usd, 0);

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-10">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-xl bg-surface-container-low bg-hero-radial p-12">
        <div className="max-w-2xl">
          <h1 className="font-display text-5xl leading-[1.05] tracking-tight">
            Evolve Agent Skills
            <br />
            Through{" "}
            <span className="text-secondary">Natural Selection</span>
          </h1>
          <p className="mt-4 text-base text-on-surface-dim">
            Deploy autonomous populations into adversarial environments. Watch
            them compete, mutate, and survive to forge the ultimate cognitive
            skillsets.
          </p>
          <div className="mt-6">
            <Link to="/new">
              <PrimaryButton>Start Evolution →</PrimaryButton>
            </Link>
          </div>
        </div>
      </section>

      {/* Recent evolutions */}
      <section className="mt-10">
        <div className="flex items-end justify-between">
          <div>
            <h2 className="font-display text-2xl tracking-tight">
              Recent Evolutions
            </h2>
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
              Active Genetic Pathways
            </p>
          </div>
          <Link
            to="/registry"
            className="text-sm text-on-surface-dim transition-colors hover:text-on-surface"
          >
            View Registry ↗
          </Link>
        </div>

        {runs == null ? (
          <p className="mt-6 text-on-surface-dim">Loading runs...</p>
        ) : runs.length === 0 ? (
          <div className="mt-6 rounded-xl bg-surface-container-low p-12 text-center">
            <p className="text-on-surface-dim">
              {error
                ? "Backend not reachable. Start the server and refresh."
                : "No evolutions yet — start your first run."}
            </p>
            <div className="mt-4">
              <Link to="/new">
                <PrimaryButton>Start Evolution →</PrimaryButton>
              </Link>
            </div>
          </div>
        ) : (
          <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {runs.map((run) => (
              <EvolutionCard
                key={run.id}
                id={run.id}
                specialization={run.specialization}
                status={run.status}
                bestFitness={run.best_fitness}
                cost={run.total_cost_usd}
              />
            ))}
          </div>
        )}
      </section>

      {/* Footer stats */}
      <section className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-3">
        <StatCard
          label="Total Runs"
          value={totalRuns.toString()}
          hint="Skills evolved"
          accent="primary"
        />
        <StatCard
          label="Avg Fitness"
          value={avgFitness > 0 ? avgFitness.toFixed(2) : "—"}
          hint={completed.length > 0 ? `Across ${completed.length} runs` : "No runs yet"}
          accent="secondary"
        />
        <StatCard
          label="Total Spent"
          value={`$${totalSpent.toFixed(2)}`}
          hint="API spend across all runs"
          accent="tertiary"
        />
      </section>
    </div>
  );
}
