import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import EvolutionCard from "./EvolutionCard";
import PipelineSteps from "./PipelineSteps";
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

  const watchDemo = async () => {
    try {
      // Ensure the demo is running, then navigate to it
      await fetch("/api/debug/demo", { method: "POST" });
      navigate("/runs/demo-live");
    } catch {
      navigate("/runs/demo-live");
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
            <p className="font-mono text-[0.6875rem] uppercase tracking-[0.18em] text-tertiary">
              Skill Kinetics through Layered Darwinism
            </p>
            <h1 className="mt-2 font-display text-4xl leading-[1.05] tracking-tight md:text-5xl">
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
                onClick={watchDemo}
                className="rounded-xl border border-primary/40 bg-surface-container-lowest px-4 py-2 text-sm text-primary transition-colors hover:bg-primary/10"
              >
                Watch Live Demo
              </button>
            </div>
          </div>

          {/* Right — live stats panel (desktop only) */}
          <div className="hidden lg:block lg:w-[320px] lg:shrink-0">
            <div className="rounded-xl border border-outline-variant bg-surface-container-lowest/80 p-5 backdrop-blur">
              <p className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
                SKLD-bench
              </p>
              <div className="mt-4 space-y-4">
                <div className="flex items-baseline justify-between">
                  <span className="text-sm text-on-surface">
                    Bench Challenges
                  </span>
                  <span className="font-display text-2xl tracking-tight text-primary">
                    867
                  </span>
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-sm text-on-surface">
                    Skill Families
                  </span>
                  <span className="font-display text-2xl tracking-tight text-primary">
                    7
                  </span>
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-sm text-on-surface">
                    Scoring Layers
                  </span>
                  <span className="font-display text-2xl tracking-tight text-primary">
                    6
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
                to="/bench"
                className="mt-5 block rounded-lg border border-outline-variant bg-surface-container-lowest px-3 py-2 text-center text-xs font-medium text-on-surface transition-colors hover:border-primary/40 hover:text-primary"
              >
                View Benchmark →
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Pipeline Steps — animated scroll-triggered overview */}
      <PipelineSteps />

      {/* Backed by Research — prior art that SKLD builds on */}
      <section className="mt-14">
        <div className="flex items-end justify-between">
          <div>
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-tertiary">
              Provenance
            </p>
            <h2 className="mt-2 font-display text-2xl tracking-tight">
              Backed by Research
            </h2>
            <p className="mt-2 max-w-2xl text-sm text-on-surface-dim">
              SKLD didn't emerge from a vacuum. The techniques below come from
              active ML and applied-AI research; SKLD composes them for a
              specific artifact (Claude Agent Skills) with a controlled
              benchmark. Each source is mapped to what we took and what we
              didn't.
            </p>
          </div>
          <Link
            to="/research/narrative/01-prior-art"
            className="hidden text-sm text-on-surface-dim transition-colors hover:text-on-surface md:inline"
          >
            Full prior art ↗
          </Link>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          <a
            href="https://arxiv.org/abs/2309.08532"
            target="_blank"
            rel="noreferrer noopener"
            className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5 transition-colors hover:border-primary/40 hover:bg-surface-container-low"
          >
            <p className="font-mono text-[0.625rem] uppercase tracking-wider text-tertiary">
              EvoPrompt · ICLR 2024
            </p>
            <p className="mt-2 font-display text-lg tracking-tight">
              LLMs as evolutionary operators
            </p>
            <p className="mt-2 text-sm text-on-surface-dim">
              Proved population-based evolution of natural-language prompts
              outperforms hand-tuning. SKLD's evolution loop skeleton.
            </p>
            <p className="mt-3 font-mono text-[0.625rem] text-on-surface-dim">
              Guo et al. · arXiv:2309.08532 ↗
            </p>
          </a>

          <a
            href="https://github.com/gepa-ai/gepa"
            target="_blank"
            rel="noreferrer noopener"
            className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5 transition-colors hover:border-primary/40 hover:bg-surface-container-low"
          >
            <p className="font-mono text-[0.625rem] uppercase tracking-wider text-tertiary">
              GEPA · UC Berkeley · ICLR 2026
            </p>
            <p className="mt-2 font-display text-lg tracking-tight">
              Reflective mutation + Pareto selection
            </p>
            <p className="mt-2 text-sm text-on-surface-dim">
              Trace-informed diagnosis before mutation, multi-objective
              Pareto fronts. The two techniques that make evolution
              intelligent instead of a random walk.
            </p>
            <p className="mt-3 font-mono text-[0.625rem] text-on-surface-dim">
              Agrawal et al. · github.com/gepa-ai ↗
            </p>
          </a>

          <a
            href="https://arxiv.org/pdf/2512.09108"
            target="_blank"
            rel="noreferrer noopener"
            className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5 transition-colors hover:border-primary/40 hover:bg-surface-container-low"
          >
            <p className="font-mono text-[0.625rem] uppercase tracking-wider text-tertiary">
              Artemis · TurinTech · 2025-26
            </p>
            <p className="mt-2 font-display text-lg tracking-tight">
              Joint multi-component optimization
            </p>
            <p className="mt-2 text-sm text-on-surface-dim">
              Mutating one agent component (a prompt, a tool, a parameter)
              often requires matching changes elsewhere. SKLD applies this
              to the interdependent parts of a SKILL.md.
            </p>
            <p className="mt-3 font-mono text-[0.625rem] text-on-surface-dim">
              TurinTech · arXiv:2512.09108 ↗
            </p>
          </a>

          <a
            href="https://imbue.com/research/2026-02-27-darwinian-evolver/"
            target="_blank"
            rel="noreferrer noopener"
            className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5 transition-colors hover:border-primary/40 hover:bg-surface-container-low"
          >
            <p className="font-mono text-[0.625rem] uppercase tracking-wider text-tertiary">
              Imbue Darwinian Evolver · Feb 2026
            </p>
            <p className="mt-2 font-display text-lg tracking-tight">
              Persistent learning log + multi-parent crossover
            </p>
            <p className="mt-2 text-sm text-on-surface-dim">
              Accumulated lessons inject into every mutation prompt, so the
              population never re-discovers failures it already explored.
              SKLD promotes these to the public Bible.
            </p>
            <p className="mt-3 font-mono text-[0.625rem] text-on-surface-dim">
              Imbue Research · imbue.com ↗
            </p>
          </a>

          <a
            href="https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills"
            target="_blank"
            rel="noreferrer noopener"
            className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5 transition-colors hover:border-primary/40 hover:bg-surface-container-low"
          >
            <p className="font-mono text-[0.625rem] uppercase tracking-wider text-tertiary">
              Anthropic skill-creator · Mar 2026
            </p>
            <p className="mt-2 font-display text-lg tracking-tight">
              Trigger accuracy + A/B comparator
            </p>
            <p className="mt-2 text-sm text-on-surface-dim">
              Skills have two reliability problems: activation (does it
              trigger on the right queries?) and execution (does it produce
              good output?). SKLD's L2 and L4 layers borrow this directly.
            </p>
            <p className="mt-3 font-mono text-[0.625rem] text-on-surface-dim">
              Anthropic · claude.com/blog ↗
            </p>
          </a>

          <a
            href="https://mlflow.org/blog/evaluating-skills-mlflow"
            target="_blank"
            rel="noreferrer noopener"
            className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5 transition-colors hover:border-primary/40 hover:bg-surface-container-low"
          >
            <p className="font-mono text-[0.625rem] uppercase tracking-wider text-tertiary">
              MLflow · Mar 2026
            </p>
            <p className="mt-2 font-display text-lg tracking-tight">
              Trace-based behavioral verification
            </p>
            <p className="mt-2 text-sm text-on-surface-dim">
              You can't assert <code>output == expected</code> for LLM
              behavior. Execution traces answer <em>what Claude did</em>,
              which is what SKLD's L3 layer scores against.
            </p>
            <p className="mt-3 font-mono text-[0.625rem] text-on-surface-dim">
              MLflow · mlflow.org/blog ↗
            </p>
          </a>
        </div>

        <div className="mt-6 flex justify-center">
          <Link
            to="/research"
            className="rounded-xl border border-primary/40 bg-surface-container-lowest px-5 py-2.5 text-sm text-primary transition-colors hover:bg-primary/10"
          >
            Read the Research Section →
          </Link>
        </div>
      </section>

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
