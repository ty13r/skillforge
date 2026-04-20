/** Seed-library picker — category filter chips + card grid. */
import { useMemo, useState } from "react";

import { DIFFICULTY_COLOR } from "./types";
import type { SeedSummary } from "./types";

interface SeedPickerProps {
  seeds: SeedSummary[] | null;
  onPick: (seed: SeedSummary) => void;
}

export default function SeedPicker({ seeds, onPick }: SeedPickerProps) {
  const [categoryFilter, setCategoryFilter] = useState("all");

  const categories = useMemo(
    () => (seeds ? ["all", ...Array.from(new Set(seeds.map((s) => s.category)))] : ["all"]),
    [seeds],
  );

  const visibleSeeds = useMemo(
    () => seeds?.filter((s) => categoryFilter === "all" || s.category === categoryFilter) ?? [],
    [seeds, categoryFilter],
  );

  return (
    <>
      {seeds && seeds.length > 0 && (
        <div className="flex flex-wrap gap-1 rounded-xl border border-outline-variant bg-surface-container-lowest p-1">
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
      )}

      {seeds == null ? (
        <p className="text-on-surface-dim">Loading seed library…</p>
      ) : visibleSeeds.length === 0 ? (
        <p className="text-on-surface-dim">No seeds match the filter.</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {visibleSeeds.map((seed) => (
            <button
              key={seed.id}
              onClick={() => onPick(seed)}
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
              <p className="mt-1 line-clamp-2 text-xs text-on-surface-dim">{seed.description}</p>
            </button>
          ))}
        </div>
      )}
    </>
  );
}
