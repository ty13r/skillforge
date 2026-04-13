import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import type { BenchFamilyDetail } from "../types";

type SortKey = "challenge_id" | "composite" | "tier" | "dimension" | "compiles";
type SortDir = "asc" | "desc";

/**
 * Per-family SKLD-bench detail page — tier breakdown, dimension stats,
 * score histogram, and a sortable challenge table.
 */
export default function SkldBenchFamily() {
  const { familySlug } = useParams<{ familySlug: string }>();
  const [data, setData] = useState<BenchFamilyDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("composite");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [tierFilter, setTierFilter] = useState<string | null>(null);
  const [dimFilter, setDimFilter] = useState<string | null>(null);

  useEffect(() => {
    if (!familySlug) return;
    fetch(`/api/bench/${familySlug}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<BenchFamilyDetail>;
      })
      .then(setData)
      .catch((err) => setError(String(err)));
  }, [familySlug]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir(key === "challenge_id" ? "asc" : "asc");
    }
  };

  const filteredAndSorted = useMemo(() => {
    if (!data) return [];
    let list = data.challenges.filter((c) => c.raw);
    if (tierFilter) list = list.filter((c) => c.tier === tierFilter);
    if (dimFilter) list = list.filter((c) => c.dimension === dimFilter);

    const dir = sortDir === "asc" ? 1 : -1;
    return [...list].sort((a, b) => {
      switch (sortKey) {
        case "challenge_id":
          return a.challenge_id.localeCompare(b.challenge_id) * dir;
        case "composite":
          return ((a.raw?.composite ?? 0) - (b.raw?.composite ?? 0)) * dir;
        case "tier": {
          const order = { easy: 0, medium: 1, hard: 2, legendary: 3 };
          return (
            ((order[a.tier as keyof typeof order] ?? 4) -
              (order[b.tier as keyof typeof order] ?? 4)) *
            dir
          );
        }
        case "dimension":
          return a.dimension.localeCompare(b.dimension) * dir;
        case "compiles":
          return (
            (Number(a.raw?.compiles ?? false) -
              Number(b.raw?.compiles ?? false)) *
            dir
          );
        default:
          return 0;
      }
    });
  }, [data, sortKey, sortDir, tierFilter, dimFilter]);

  if (error) {
    return (
      <div className="mx-auto max-w-5xl px-8 py-16">
        <p className="text-error">Failed to load data: {error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-5xl px-8 py-16">
        <p className="text-on-surface-dim">Loading...</p>
      </div>
    );
  }

  const tierColors: Record<string, string> = {
    easy: "text-green-400",
    medium: "text-yellow-400",
    hard: "text-orange-400",
    legendary: "text-red-400",
  };

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      {/* Header */}
      <div className="mb-8">
        <Link
          to="/bench"
          className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim hover:text-on-surface"
        >
          &larr; SKLD-bench
        </Link>
        <h1 className="mt-2 font-display text-4xl tracking-tight">
          {data.label}
        </h1>
        <p className="mt-1 font-mono text-sm text-on-surface-dim">
          {data.total_challenges} challenges scored with composite evaluation
        </p>
      </div>

      {/* Tier Breakdown */}
      <div className="mb-8 rounded-xl border border-outline-variant bg-surface-container-low p-6">
        <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          Tier Breakdown
        </p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-outline-variant font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
                <th className="pb-3 pr-4">Tier</th>
                <th className="pb-3 pr-4 text-right">Count</th>
                <th className="pb-3 pr-4 text-right">Avg Composite</th>
                <th className="pb-3 pr-4 text-right">Compile %</th>
                <th className="pb-3 pr-4 text-right">Avg Behavioral</th>
                <th className="pb-3 text-right">Avg L0</th>
              </tr>
            </thead>
            <tbody>
              {data.tiers.map((t) => (
                <tr
                  key={t.tier}
                  className="border-b border-outline-variant/30"
                >
                  <td
                    className={`py-2.5 pr-4 font-mono text-sm capitalize ${tierColors[t.tier] ?? "text-on-surface"}`}
                  >
                    {t.tier}
                  </td>
                  <td className="py-2.5 pr-4 text-right font-mono text-sm text-on-surface">
                    {t.count}
                  </td>
                  <td className="py-2.5 pr-4 text-right font-mono text-sm text-on-surface">
                    {t.avg_composite.toFixed(3)}
                  </td>
                  <td className="py-2.5 pr-4 text-right font-mono text-sm text-on-surface">
                    {(t.compile_pct * 100).toFixed(0)}%
                  </td>
                  <td className="py-2.5 pr-4 text-right font-mono text-sm text-on-surface">
                    {t.avg_behavioral.toFixed(3)}
                  </td>
                  <td className="py-2.5 text-right font-mono text-sm text-on-surface">
                    {t.avg_l0.toFixed(3)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Dimension Breakdown + Histogram side by side */}
      <div className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Dimensions */}
        <div className="rounded-xl border border-outline-variant bg-surface-container-low p-6">
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            By Dimension
          </p>
          <div className="mt-4 space-y-2">
            {data.dimensions.map((dim) => (
              <div key={dim.dimension} className="flex items-center gap-3">
                <p className="w-44 shrink-0 truncate font-mono text-[0.625rem] text-on-surface-dim">
                  {dim.dimension}
                </p>
                <div className="relative h-4 flex-1 overflow-hidden rounded bg-surface-container-high">
                  <div
                    className="h-full bg-tertiary/50"
                    style={{
                      width: `${Math.max(0, Math.min(1, dim.avg_composite)) * 100}%`,
                    }}
                  />
                </div>
                <p className="w-12 text-right font-mono text-[0.625rem] text-on-surface">
                  {dim.avg_composite.toFixed(3)}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Histogram */}
        <div className="rounded-xl border border-outline-variant bg-surface-container-low p-6">
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Score Distribution (Composite)
          </p>
          <div className="mt-4 flex items-end gap-1" style={{ height: 160 }}>
            {data.histogram.counts.map((count, i) => {
              const maxCount = Math.max(...data.histogram.counts, 1);
              const heightPct = (count / maxCount) * 100;
              return (
                <div key={i} className="flex flex-1 flex-col items-center gap-1">
                  <span className="font-mono text-[0.5rem] text-on-surface-dim">
                    {count > 0 ? count : ""}
                  </span>
                  <div
                    className="w-full rounded-t bg-tertiary/50"
                    style={{ height: `${heightPct}%`, minHeight: count > 0 ? 4 : 0 }}
                  />
                  <span className="font-mono text-[0.5rem] text-on-surface-dim">
                    {data.histogram.buckets[i]?.split("-")[0]}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Challenge Table */}
      <div className="rounded-xl border border-outline-variant bg-surface-container-low p-6">
        <div className="flex items-center justify-between gap-4">
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            All Challenges ({filteredAndSorted.length})
          </p>
          <div className="flex gap-2">
            <select
              value={tierFilter ?? ""}
              onChange={(e) => setTierFilter(e.target.value || null)}
              className="rounded bg-surface-container-high px-2 py-1 font-mono text-[0.625rem] text-on-surface"
            >
              <option value="">All tiers</option>
              {data.tiers.map((t) => (
                <option key={t.tier} value={t.tier}>
                  {t.tier}
                </option>
              ))}
            </select>
            <select
              value={dimFilter ?? ""}
              onChange={(e) => setDimFilter(e.target.value || null)}
              className="rounded bg-surface-container-high px-2 py-1 font-mono text-[0.625rem] text-on-surface"
            >
              <option value="">All dimensions</option>
              {data.dimensions.map((d) => (
                <option key={d.dimension} value={d.dimension}>
                  {d.dimension}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-4 max-h-[600px] overflow-y-auto">
          <table className="w-full text-left">
            <thead className="sticky top-0 bg-surface-container-low">
              <tr className="border-b border-outline-variant font-mono text-[0.5625rem] uppercase tracking-wider text-on-surface-dim">
                <SortHeader
                  label="Challenge"
                  sortKey="challenge_id"
                  current={sortKey}
                  dir={sortDir}
                  onClick={handleSort}
                />
                <SortHeader
                  label="Tier"
                  sortKey="tier"
                  current={sortKey}
                  dir={sortDir}
                  onClick={handleSort}
                  className="text-center"
                />
                <SortHeader
                  label="Dimension"
                  sortKey="dimension"
                  current={sortKey}
                  dir={sortDir}
                  onClick={handleSort}
                />
                <SortHeader
                  label="Compiles"
                  sortKey="compiles"
                  current={sortKey}
                  dir={sortDir}
                  onClick={handleSort}
                  className="text-center"
                />
                <SortHeader
                  label="Composite"
                  sortKey="composite"
                  current={sortKey}
                  dir={sortDir}
                  onClick={handleSort}
                  className="text-right"
                />
                <th className="pb-2 pr-3 text-right">Skill</th>
                <th className="pb-2 text-right">Lift</th>
              </tr>
            </thead>
            <tbody>
              {filteredAndSorted.map((c) => {
                const rawComp = c.raw?.composite ?? 0;
                const skillComp = c.skill?.composite;
                const lift =
                  skillComp != null && rawComp > 0
                    ? (skillComp - rawComp) / rawComp
                    : null;

                return (
                  <tr
                    key={c.challenge_id}
                    className="border-b border-outline-variant/20 transition-colors hover:bg-surface-container-lowest"
                  >
                    <td className="py-1.5 pr-3 font-mono text-[0.625rem] text-on-surface">
                      {c.challenge_id}
                    </td>
                    <td
                      className={`py-1.5 pr-3 text-center font-mono text-[0.625rem] capitalize ${tierColors[c.tier] ?? "text-on-surface"}`}
                    >
                      {c.tier}
                    </td>
                    <td className="py-1.5 pr-3 font-mono text-[0.5625rem] text-on-surface-dim">
                      {c.dimension}
                    </td>
                    <td className="py-1.5 pr-3 text-center font-mono text-[0.625rem]">
                      {c.raw?.compiles ? (
                        <span className="text-green-400">Y</span>
                      ) : (
                        <span className="text-red-400">N</span>
                      )}
                    </td>
                    <td className="py-1.5 pr-3 text-right font-mono text-[0.625rem] text-on-surface">
                      {rawComp.toFixed(3)}
                    </td>
                    <td className="py-1.5 pr-3 text-right font-mono text-[0.625rem] text-on-surface-dim">
                      {skillComp != null ? skillComp.toFixed(3) : "—"}
                    </td>
                    <td
                      className={`py-1.5 text-right font-mono text-[0.625rem] ${
                        lift != null && lift > 0
                          ? "text-tertiary"
                          : lift != null && lift < 0
                            ? "text-error"
                            : "text-on-surface-dim"
                      }`}
                    >
                      {lift != null
                        ? `${lift > 0 ? "+" : ""}${(lift * 100).toFixed(0)}%`
                        : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function SortHeader({
  label,
  sortKey,
  current,
  dir,
  onClick,
  className = "",
}: {
  label: string;
  sortKey: SortKey;
  current: SortKey;
  dir: SortDir;
  onClick: (key: SortKey) => void;
  className?: string;
}) {
  const arrow = current === sortKey ? (dir === "asc" ? " ↑" : " ↓") : "";
  return (
    <th className={`cursor-pointer pb-2 pr-3 ${className}`}>
      <button
        type="button"
        onClick={() => onClick(sortKey)}
        className="hover:text-on-surface"
      >
        {label}
        {arrow}
      </button>
    </th>
  );
}
