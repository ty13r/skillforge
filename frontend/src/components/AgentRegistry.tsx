import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { RunSummary } from "../types";

interface SeedSummary {
  id: string;
  slug: string;
  title: string;
  category: string;
  difficulty: "easy" | "medium" | "hard";
  traits: string[];
  meta_strategy: string;
  description: string;
}

type SortKey = "fitness" | "cost" | "recent";

const DIFFICULTY_COLOR: Record<string, string> = {
  easy: "text-tertiary",
  medium: "text-warning",
  hard: "text-error",
};

// Filter out the seed-library run from the user-runs list — it's rendered
// separately in the curated section.
const SEED_RUN_ID = "seed-library";

export default function AgentRegistry() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [seeds, setSeeds] = useState<SeedSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("fitness");
  const [modeFilter, setModeFilter] = useState<string>("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  useEffect(() => {
    fetch("/api/runs")
      .then((r) => r.json() as Promise<RunSummary[]>)
      .then(setRuns)
      .catch((err) => {
        setError(String(err));
        setRuns([]);
      });
    fetch("/api/seeds")
      .then((r) => r.json() as Promise<SeedSummary[]>)
      .then(setSeeds)
      .catch(() => setSeeds([]));
  }, []);

  const completed = useMemo(
    () => (runs ?? []).filter((r) => r.status === "complete" && r.id !== SEED_RUN_ID),
    [runs],
  );

  const modes = useMemo(() => {
    const set = new Set<string>();
    completed.forEach((r) => set.add(r.mode));
    return ["all", ...Array.from(set)];
  }, [completed]);

  const filteredRuns = useMemo(() => {
    let list = completed;
    if (modeFilter !== "all") list = list.filter((r) => r.mode === modeFilter);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((r) => r.specialization.toLowerCase().includes(q) || r.id.includes(q));
    }
    const sorted = [...list];
    if (sortKey === "fitness") {
      sorted.sort((a, b) => (b.best_fitness ?? 0) - (a.best_fitness ?? 0));
    } else if (sortKey === "cost") {
      sorted.sort((a, b) => a.total_cost_usd - b.total_cost_usd);
    }
    return sorted;
  }, [completed, modeFilter, search, sortKey]);

  const categories = useMemo(() => {
    const set = new Set<string>();
    (seeds ?? []).forEach((s) => set.add(s.category));
    return ["all", ...Array.from(set)];
  }, [seeds]);

  const filteredSeeds = useMemo(() => {
    let list = seeds ?? [];
    if (categoryFilter !== "all") list = list.filter((s) => s.category === categoryFilter);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (s) =>
          s.title.toLowerCase().includes(q) ||
          s.description.toLowerCase().includes(q) ||
          s.category.toLowerCase().includes(q),
      );
    }
    return list;
  }, [seeds, categoryFilter, search]);

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-10">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-primary">
            Protocol: Archive
          </p>
          <h1 className="mt-2 font-display text-5xl leading-[1.05] tracking-tight">
            Skill <span className="text-primary">Registry</span>
          </h1>
          <p className="mt-3 max-w-2xl text-on-surface-dim">
            Browse curated Gen 0 Skills and completed evolution runs. Deploy any Skill directly or
            fork-and-evolve it with your own specialization.
          </p>
        </div>
      </div>

      {/* Global search */}
      <div className="mt-8">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search across all skills and runs…"
          className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest px-4 py-2.5 text-sm text-on-surface placeholder:text-on-surface-dim focus:border-primary focus:outline-none"
        />
      </div>

      {error && <div className="mt-6 rounded-xl bg-error/10 p-4 text-sm text-error">{error}</div>}

      {/* ─── Curated Seeds Section ─────────────────────────────────────── */}
      <section className="mt-12">
        <div className="flex items-end justify-between">
          <div>
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-primary">
              ✦ Curated Library
            </p>
            <h2 className="mt-1 font-display text-2xl tracking-tight">Gen 0 Skills</h2>
            <p className="mt-1 text-sm text-on-surface-dim">
              Production-ready Skills you can deploy immediately or fork as the starting point for
              evolution.
            </p>
          </div>
          <div className="text-right font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            {seeds?.length ?? 0} skills
          </div>
        </div>

        {/* Category filter chips */}
        <div className="mt-4 flex flex-wrap gap-1 rounded-xl bg-surface-container-low p-1">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat)}
              className={`rounded-lg px-3 py-1.5 font-mono text-[0.6875rem] uppercase tracking-wider transition-colors ${
                categoryFilter === cat
                  ? "bg-primary/15 text-primary"
                  : "text-on-surface-dim hover:text-on-surface"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Seed cards */}
        {seeds == null ? (
          <p className="mt-6 text-on-surface-dim">Loading seeds…</p>
        ) : filteredSeeds.length === 0 ? (
          <p className="mt-6 text-on-surface-dim">No seeds match the filter.</p>
        ) : (
          <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filteredSeeds.map((seed) => (
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
                <h3 className="mt-3 font-display text-xl tracking-tight group-hover:text-primary">
                  {seed.title}
                </h3>
                <p className="mt-2 line-clamp-3 flex-1 text-sm text-on-surface-dim">
                  {seed.description}
                </p>
                {seed.traits.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {seed.traits.slice(0, 3).map((t) => (
                      <span
                        key={t}
                        className="bg-surface-container-mid rounded-full px-2 py-0.5 font-mono text-[0.5625rem] text-on-surface-dim"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                )}
                <div className="mt-4 flex gap-2 border-t border-outline-variant pt-4">
                  <Link
                    to={`/runs/${SEED_RUN_ID}/skills/${seed.id}`}
                    className="bg-surface-container-mid flex-1 rounded-lg px-3 py-2 text-center text-xs font-medium text-on-surface transition-colors hover:bg-surface-container-high"
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

      {/* ─── Community Evolutions Section ──────────────────────────────── */}
      <section className="mt-16">
        <div className="flex items-end justify-between">
          <div>
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
              Completed Runs
            </p>
            <h2 className="mt-1 font-display text-2xl tracking-tight">Community Evolutions</h2>
          </div>
          <div className="text-right font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            {completed.length} runs
          </div>
        </div>

        {/* Mode + sort controls */}
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <div className="flex gap-1 rounded-xl bg-surface-container-low p-1">
            {modes.map((m) => (
              <button
                key={m}
                onClick={() => setModeFilter(m)}
                className={`rounded-lg px-3 py-1.5 font-mono text-[0.6875rem] uppercase tracking-wider transition-colors ${
                  modeFilter === m
                    ? "bg-primary/15 text-primary"
                    : "text-on-surface-dim hover:text-on-surface"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
          <select
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
            className="rounded-xl border border-outline-variant bg-surface-container-lowest px-3 py-2.5 font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface"
          >
            <option value="fitness">Sort: Fitness</option>
            <option value="cost">Sort: Cost</option>
            <option value="recent">Sort: Recent</option>
          </select>
        </div>

        {/* Runs grid */}
        {runs == null ? (
          <p className="mt-6 text-on-surface-dim">Loading runs…</p>
        ) : filteredRuns.length === 0 ? (
          <div className="mt-6 rounded-xl bg-surface-container-low p-12 text-center">
            <p className="text-on-surface-dim">
              {completed.length === 0
                ? "No community evolutions yet — be the first to run one."
                : "No runs match the current filters."}
            </p>
          </div>
        ) : (
          <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filteredRuns.map((run) => (
              <Link
                key={run.id}
                to={`/runs/${run.id}`}
                className="group rounded-xl border border-outline-variant bg-surface-container-lowest p-5 transition-all hover:border-primary/40 hover:shadow-elevated"
              >
                <div className="flex items-start justify-between">
                  <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                    {run.mode}
                  </p>
                  <span className="rounded-full bg-tertiary/10 px-2 py-0.5 font-mono text-[0.625rem] uppercase tracking-wider text-tertiary">
                    complete
                  </span>
                </div>
                <h3 className="mt-3 line-clamp-2 font-display text-lg tracking-tight group-hover:text-primary">
                  {run.specialization || "Untitled"}
                </h3>
                <p className="mt-1 font-mono text-[0.625rem] text-on-surface-dim">
                  {run.id.slice(0, 12)}
                </p>
                <div className="mt-4 flex items-end justify-between">
                  <div>
                    <p className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
                      Fitness
                    </p>
                    <p className="font-display text-3xl tracking-tight text-primary">
                      {(run.best_fitness ?? 0).toFixed(2)}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
                      Cost
                    </p>
                    <p className="font-mono text-sm text-on-surface">
                      ${run.total_cost_usd.toFixed(2)}
                    </p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
