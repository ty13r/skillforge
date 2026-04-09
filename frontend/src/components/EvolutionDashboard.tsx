import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import EvolutionCard from "./EvolutionCard";
import PrimaryButton from "./PrimaryButton";
import StatCard from "./StatCard";
import type { RunSummary } from "../types";

interface SeedSummary {
  id: string;
  slug: string;
  title: string;
  category: string;
  difficulty: "easy" | "medium" | "hard";
  description: string;
  traits: string[];
}

const DIFFICULTY_COLOR: Record<string, string> = {
  easy: "text-tertiary",
  medium: "text-warning",
  hard: "text-error",
};

export default function EvolutionDashboard() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [seeds, setSeeds] = useState<SeedSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const startFakeRun = async () => {
    try {
      const res = await fetch("/api/debug/fake-run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ population_size: 4, num_generations: 3, num_challenges: 3, speed: 0.5 }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as { run_id: string };
      navigate(`/runs/${data.run_id}`);
    } catch (err) {
      alert(`Failed to start fake run: ${String(err)}`);
    }
  };

  useEffect(() => {
    fetch("/api/runs")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<RunSummary[]>;
      })
      // Hide the synthetic seed-library run — it lives in the Registry
      .then((data) => setRuns(data.filter((r) => r.id !== "seed-library")))
      .catch((err) => {
        setError(String(err));
        setRuns([]);
      });
    fetch("/api/seeds")
      .then((r) => r.json() as Promise<SeedSummary[]>)
      .then(setSeeds)
      .catch(() => setSeeds([]));
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
      <section className="relative overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest bg-hero-radial p-8 md:p-12">
        <div className="flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
          {/* Left — headline + CTAs */}
          <div className="max-w-2xl">
            <h1 className="font-display text-4xl leading-[1.05] tracking-tight md:text-5xl">
              Evolve Agent Skills
              <br />
              Through{" "}
              <span className="text-primary">Natural Selection</span>
            </h1>
            <p className="mt-4 text-base text-on-surface-dim">
              Deploy autonomous populations into adversarial environments.
              Watch them compete, mutate, and survive to forge the ultimate
              cognitive skillsets.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link to="/new">
                <PrimaryButton>Start Evolution →</PrimaryButton>
              </Link>
              <button
                onClick={startFakeRun}
                className="rounded-xl border border-primary/40 bg-surface-container-lowest px-4 py-2 text-sm text-primary transition-colors hover:bg-primary/10"
              >
                ▶ Watch Live Demo
              </button>
            </div>
          </div>

          {/* Right — live stats panel (desktop only) */}
          <div className="hidden lg:block lg:w-[320px] lg:shrink-0">
            <div className="rounded-xl border border-outline-variant bg-surface-container-lowest/80 p-5 backdrop-blur">
              <p className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
                The Platform
              </p>
              <div className="mt-4 space-y-4">
                <div className="flex items-baseline justify-between">
                  <span className="text-sm text-on-surface">
                    Curated Gen 0 Skills
                  </span>
                  <span className="font-display text-2xl tracking-tight text-primary">
                    {seeds?.length ?? "—"}
                  </span>
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-sm text-on-surface">
                    Bible Patterns
                  </span>
                  <span className="font-display text-2xl tracking-tight text-primary">
                    37
                  </span>
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-sm text-on-surface">
                    Judging Layers
                  </span>
                  <span className="font-display text-2xl tracking-tight text-primary">
                    5
                  </span>
                </div>
                <div className="flex items-baseline justify-between border-t border-outline-variant pt-4">
                  <span className="text-sm text-on-surface">Your Runs</span>
                  <span className="font-display text-2xl tracking-tight text-on-surface">
                    {totalRuns}
                  </span>
                </div>
              </div>
              <Link
                to="/registry"
                className="mt-5 block rounded-lg border border-outline-variant bg-surface-container-lowest px-3 py-2 text-center text-xs font-medium text-on-surface transition-colors hover:border-primary/40 hover:text-primary"
              >
                Browse Registry →
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Recent evolutions — or curated seeds if the user has none yet */}
      {/* Recent Evolutions — completed user runs only */}
      {completed.length > 0 && (
        <section className="mt-10">
          <div className="flex items-end justify-between">
            <div>
              <h2 className="font-display text-2xl tracking-tight">
                Recent Evolutions
              </h2>
              <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                Completed Runs
              </p>
            </div>
            <Link
              to="/registry"
              className="text-sm text-on-surface-dim transition-colors hover:text-on-surface"
            >
              View Registry ↗
            </Link>
          </div>
          <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {completed.map((run) => (
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
        </section>
      )}

      {/* Curated Gen 0 Skills — always visible */}
      <section className="mt-10">
        <div className="flex items-end justify-between">
          <div>
            <h2 className="font-display text-2xl tracking-tight">
              Try a Curated Gen 0 Skill
            </h2>
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
              ✦ Production-ready · fork to evolve
            </p>
          </div>
          {completed.length === 0 && (
            <Link
              to="/registry"
              className="text-sm text-on-surface-dim transition-colors hover:text-on-surface"
            >
              View Registry ↗
            </Link>
          )}
        </div>

        {seeds == null ? (
          <p className="mt-6 text-on-surface-dim">Loading seed library...</p>
        ) : seeds.length === 0 ? (
          <div className="mt-6 rounded-xl border border-outline-variant bg-surface-container-lowest p-12 text-center">
            <p className="text-on-surface-dim">
              {error ? "Backend not reachable. Start the server and refresh." : "No seeds available."}
            </p>
          </div>
        ) : (
          <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {seeds.slice(0, 6).map((seed) => (
              <div
                key={seed.id}
                className="group flex flex-col rounded-xl border border-outline-variant bg-surface-container-lowest p-5 transition-all hover:border-primary/40 hover:shadow-elevated"
              >
                <div className="flex items-start justify-between">
                  <span className="rounded-full bg-primary/10 px-2.5 py-0.5 font-mono text-[0.625rem] uppercase tracking-wider text-primary">
                    {seed.category}
                  </span>
                  <span
                    className={`font-mono text-[0.625rem] uppercase tracking-wider ${DIFFICULTY_COLOR[seed.difficulty]}`}
                  >
                    {seed.difficulty}
                  </span>
                </div>
                <h3 className="mt-3 font-display text-lg tracking-tight group-hover:text-primary">
                  {seed.title}
                </h3>
                <p className="mt-2 line-clamp-3 flex-1 text-sm text-on-surface-dim">
                  {seed.description}
                </p>
                <div className="mt-4 flex gap-2 border-t border-outline-variant pt-4">
                  <Link
                    to={`/runs/seed-library/skills/${seed.id}`}
                    className="flex-1 rounded-lg bg-surface-container-low px-3 py-2 text-center text-xs font-medium text-on-surface transition-colors hover:bg-surface-container-mid"
                  >
                    View
                  </Link>
                  <Link
                    to={`/new?seed=${seed.id}`}
                    className="flex-1 rounded-lg bg-primary/15 px-3 py-2 text-center text-xs font-medium text-primary transition-colors hover:bg-primary/25"
                  >
                    ⑂ Fork
                  </Link>
                </div>
              </div>
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
