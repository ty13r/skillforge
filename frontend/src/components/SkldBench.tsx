import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import type { BenchSummary } from "../types";

/**
 * SKLD-bench overview page — shows the benchmark methodology, per-family
 * scoreboard, and scoring progression across all 7 Elixir families.
 */
export default function SkldBench() {
  const [data, setData] = useState<BenchSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/bench/summary")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<BenchSummary>;
      })
      .then(setData)
      .catch((err) => setError(String(err)));
  }, []);

  if (error) {
    return (
      <div className="mx-auto max-w-5xl px-8 py-16">
        <p className="text-error">Failed to load bench data: {error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-5xl px-8 py-16">
        <p className="text-on-surface-dim">Loading SKLD-bench data...</p>
      </div>
    );
  }

  const { families, overall, scoring_progression } = data;

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      {/* Hero */}
      <div className="mb-10">
        <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-tertiary">
          SKLD-bench
        </p>
        <h1 className="mt-2 font-display text-5xl leading-[1.05] tracking-tight">
          {overall.challenges} Elixir Challenges
        </h1>
        <p className="mt-3 max-w-3xl text-sm text-on-surface-dim">
          A controlled evaluation benchmark for measuring whether Claude Agent Skills actually
          improve code generation. Each challenge is scored through multiple layers: string
          matching, compilation, AST analysis, and behavioral testing.
        </p>
      </div>

      {/* Scoring Methodology */}
      <div className="mb-10 rounded-xl border border-outline-variant bg-surface-container-low p-6">
        <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          Composite Scoring Formula
        </p>
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
          {[
            { label: "String Match", weight: "10%", desc: "L0" },
            { label: "Compilation", weight: "15%", desc: "Compiles?" },
            { label: "AST Quality", weight: "15%", desc: "Structure" },
            { label: "Behavioral", weight: "40%", desc: "Does it work?" },
            { label: "Template", weight: "10%", desc: "Modern idioms" },
            { label: "Brevity", weight: "10%", desc: "Conciseness" },
          ].map((item) => (
            <div
              key={item.label}
              className="rounded-lg bg-surface-container-lowest p-3 text-center"
            >
              <p className="font-display text-2xl text-tertiary">{item.weight}</p>
              <p className="mt-1 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface">
                {item.label}
              </p>
              <p className="text-[0.5625rem] text-on-surface-dim">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Scoring Progression */}
      {scoring_progression && (
        <div className="mb-10 rounded-xl border border-outline-variant bg-surface-container-low p-6">
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Scoring Progression — How the baseline drops as layers are added
          </p>
          <div className="mt-4 space-y-3">
            {[
              {
                label: "L0 String Match",
                value: scoring_progression.l0,
                weight: "10%",
                color: "bg-primary/60",
              },
              {
                label: "Compilation",
                value: scoring_progression.compile,
                weight: "15%",
                color: "bg-tertiary/60",
              },
              {
                label: "AST Quality",
                value: scoring_progression.ast,
                weight: "15%",
                color: "bg-tertiary/40",
              },
              {
                label: "Behavioral Tests",
                value: scoring_progression.behavioral,
                weight: "40%",
                color: "bg-error/60",
              },
              {
                label: "Template",
                value: scoring_progression.template,
                weight: "10%",
                color: "bg-primary/40",
              },
              {
                label: "Brevity",
                value: scoring_progression.brevity,
                weight: "10%",
                color: "bg-primary/30",
              },
              {
                label: "Composite",
                value: scoring_progression.composite,
                weight: "",
                color: "bg-on-surface/40",
              },
            ].map((layer) => (
              <div key={layer.label} className="flex items-center gap-4">
                <p className="w-44 shrink-0 text-right font-mono text-xs text-on-surface-dim">
                  {layer.label}
                  {layer.weight && (
                    <span className="ml-2 text-[0.5625rem] text-on-surface-dim/60">
                      ({layer.weight})
                    </span>
                  )}
                </p>
                <div className="relative h-6 flex-1 overflow-hidden rounded bg-surface-container-high">
                  <div
                    className={`h-full ${layer.color} transition-all`}
                    style={{
                      width: `${Math.max(0, Math.min(1, layer.value)) * 100}%`,
                    }}
                  />
                </div>
                <p className="w-14 font-mono text-sm text-on-surface">
                  {(layer.value * 100).toFixed(1)}%
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Family Scoreboard */}
      <div className="rounded-xl border border-outline-variant bg-surface-container-low p-6">
        <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          Family Scoreboard — Raw Sonnet vs Sonnet + Skill
        </p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-outline-variant font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
                <th className="pb-3 pr-4">Family</th>
                <th className="pb-3 pr-4 text-right">Challenges</th>
                <th className="pb-3 pr-4 text-right">Sonnet Raw</th>
                <th className="pb-3 pr-4 text-right">+ Skill</th>
                <th className="pb-3 pr-4 text-right">Lift</th>
                <th className="pb-3 text-right">Compile %</th>
              </tr>
            </thead>
            <tbody>
              {families.map((fam) => (
                <tr
                  key={fam.slug}
                  className="border-b border-outline-variant/30 transition-colors hover:bg-surface-container-lowest"
                >
                  <td className="py-3 pr-4">
                    <Link
                      to={`/bench/${fam.slug}`}
                      className="font-mono text-sm text-tertiary hover:underline"
                    >
                      {fam.label}
                    </Link>
                  </td>
                  <td className="py-3 pr-4 text-right font-mono text-sm text-on-surface">
                    {fam.challenges}
                  </td>
                  <td className="py-3 pr-4 text-right font-mono text-sm text-on-surface">
                    {fam.raw_composite?.toFixed(3) ?? "—"}
                  </td>
                  <td className="py-3 pr-4 text-right font-mono text-sm text-on-surface">
                    {fam.skill_composite?.toFixed(3) ?? "—"}
                  </td>
                  <td
                    className={`py-3 pr-4 text-right font-mono text-sm ${
                      fam.lift != null && fam.lift > 0
                        ? "text-tertiary"
                        : fam.lift != null && fam.lift < 0
                          ? "text-error"
                          : "text-on-surface-dim"
                    }`}
                  >
                    {fam.lift != null
                      ? `${fam.lift > 0 ? "+" : ""}${(fam.lift * 100).toFixed(0)}%`
                      : "—"}
                  </td>
                  <td className="py-3 text-right font-mono text-sm text-on-surface">
                    {fam.compile_pct != null ? `${(fam.compile_pct * 100).toFixed(0)}%` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="font-mono text-sm font-bold text-on-surface">
                <td className="pr-4 pt-3">Overall</td>
                <td className="pr-4 pt-3 text-right">{overall.challenges}</td>
                <td className="pr-4 pt-3 text-right">{overall.raw_composite?.toFixed(3) ?? "—"}</td>
                <td className="pr-4 pt-3 text-right" colSpan={3}></td>
              </tr>
            </tfoot>
          </table>
        </div>
        <p className="mt-4 text-[0.625rem] text-on-surface-dim">
          Click a family name to see per-challenge detail, tier breakdowns, and score distributions.
        </p>
      </div>
    </div>
  );
}
