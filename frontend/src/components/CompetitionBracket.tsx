import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { CompetitionMatch, CompetitionScoresPayload, RunReportGenome } from "../types";

interface CompetitionBracketProps {
  scores: CompetitionScoresPayload;
  genomes: RunReportGenome[];
  /** Per-challenge raw Sonnet baseline composite scores from SKLD-bench */
  rawBaselineMap?: Record<string, number>;
}

/**
 * Visualizes Gen 0 → Gen 1 competition as a 12-match bracket with full
 * per-(variant, challenge) fitness breakdown.
 *
 * Each match shows:
 *   - Variant 1 (seed) and Variant 2 (spawn) side by side
 *   - The 2 challenge IDs they were scored against
 *   - Per-challenge scores for both variants
 *   - Each variant's mean score
 *   - Winner indicator + a concrete "why this variant won" rationale
 *   - Click-to-expand previews of the winning variant's SKILL.md
 *
 * A disclaimer card at the top explains the scoring methodology (L1 only,
 * 2 sampled challenges per variant, 1 generation, no baseline run) so a
 * first-time visitor understands what they're looking at.
 */
export default function CompetitionBracket({
  scores,
  genomes,
  rawBaselineMap = {},
}: CompetitionBracketProps) {
  const [expandedKey, setExpandedKey] = useState<string | null>(null);

  // Guard against a malformed/partial payload — an older shape (pre-schema-
  // alignment) or a hand-constructed entry may be missing `matches`. Render
  // a graceful placeholder instead of crashing the whole page.
  const sortedMatches = useMemo<CompetitionMatch[]>(() => {
    const matches = Array.isArray(scores?.matches) ? scores.matches : [];
    return [...matches].sort((a, b) => {
      if (a.tier !== b.tier) return a.tier === "foundation" ? -1 : 1;
      return b.winning_fitness - a.winning_fitness;
    });
  }, [scores?.matches]);

  // Empty / malformed payload: render the disclaimer only, with a notice.
  if (sortedMatches.length === 0) {
    return (
      <div className="rounded-xl border border-outline-variant bg-surface-container-low p-6">
        <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          Competition
        </p>
        <p className="mt-3 text-sm text-on-surface-dim">
          This run has no competition bracket data available. The seed run either pre-dates the{" "}
          <code className="rounded bg-surface-container-high px-1">[competition_scores]</code>{" "}
          learning-log format, or its payload was malformed during export.
        </p>
      </div>
    );
  }

  const challengesPerVariant = scores?.challenges_per_variant ?? 0;
  const generation = scores?.generation ?? 1;
  const totalGenerations = scores?.total_generations ?? 1;
  const baselineRan = scores?.baseline_ran ?? false;

  return (
    <div className="space-y-6">
      {/* Methodology disclaimer */}
      <div className="rounded-xl border border-outline-variant bg-surface-container-low p-5">
        <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          How selection works · Why winners were picked
        </p>
        <div className="mt-3 space-y-2 text-xs leading-relaxed text-on-surface-dim">
          <p>
            Each dimension ran a <strong className="text-on-surface">1-round</strong> competition:
            the pre-existing seed variant vs. one freshly-spawned alternative. Both variants were
            scored on{" "}
            <strong className="text-on-surface">{challengesPerVariant} sampled challenges</strong>{" "}
            drawn from the dimension's 108-challenge training pool (27 held-out for future test-time
            evaluation). The variant with the higher{" "}
            <strong className="text-on-surface">mean L1 fitness</strong> won.
          </p>
          <p>
            <strong className="text-on-surface">Scoring criteria</strong> per challenge: the L1
            scorer runs regex checks against the generated output file. Each challenge defines{" "}
            <code className="rounded bg-surface-container-high px-1">must_contain</code> required
            substrings,{" "}
            <code className="rounded bg-surface-container-high px-1">must_not_contain</code>{" "}
            forbidden substrings, and a set of dimension-specific anti-pattern detectors. The
            fraction of passing checks is weighted by each check's weight, and the weighted pass
            rate becomes the score.
          </p>
          <p>
            <strong className="text-on-surface">Limitations for this run</strong>: this is
            generation{" "}
            <span className="font-mono">
              {generation}/{totalGenerations}
            </span>{" "}
            (single-round).{" "}
            {baselineRan
              ? "A baseline run on the full challenge pool was completed before this competition."
              : "No baseline pass over the full 108-challenge pool was run before sampling."}{" "}
            Higher reviewer layers (L2 trigger accuracy, L3 trace, L4 comparative, L5 trait
            attribution) were not exercised. Real production runs would layer these on top for
            richer signal.
          </p>
        </div>
      </div>

      {/* Matches */}
      {sortedMatches.map((match) => {
        const isExpanded = expandedKey === match.dimension;
        const winnerLabel = match.winner_slot === 1 ? match.variant_1_label : match.variant_2_label;
        const winnerScores =
          match.winner_slot === 1 ? match.variant_1_scores : match.variant_2_scores;
        const loserScores =
          match.winner_slot === 1 ? match.variant_2_scores : match.variant_1_scores;
        const winnerMean = match.winner_slot === 1 ? match.variant_1_mean : match.variant_2_mean;
        const loserMean = match.winner_slot === 1 ? match.variant_2_mean : match.variant_1_mean;

        // Find the winning genome for the expand-on-click view.
        const winnerGenome = genomes.find(
          (g) =>
            g.meta_strategy === "seed_pipeline_winner" && deriveDimFromId(g.id) === match.dimension,
        );

        const rationale = buildRationale(match, winnerMean, loserMean);

        // Look up raw baseline scores for this match's challenges
        const rawScores = match.challenge_ids.map((id) => rawBaselineMap[id] ?? null);
        const validRawScores = rawScores.filter((s): s is number => s !== null);
        const rawMean =
          validRawScores.length > 0
            ? validRawScores.reduce((a, b) => a + b, 0) / validRawScores.length
            : null;
        const hasRaw = validRawScores.length > 0;

        return (
          <div
            key={match.dimension}
            className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5"
          >
            {/* Header: dimension + tier */}
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <p className="font-mono text-sm font-bold text-on-surface">{match.dimension}</p>
                <span
                  className={`rounded px-1.5 py-0.5 font-mono text-[0.5625rem] uppercase tracking-wider ${
                    match.tier === "foundation"
                      ? "bg-tertiary/10 text-tertiary"
                      : "bg-primary/10 text-primary"
                  }`}
                >
                  {match.tier}
                </span>
              </div>
              <p className="font-mono text-[0.625rem] text-on-surface-dim">
                Tested on {match.challenge_ids.length} challenges
              </p>
            </div>

            {/* Challenge strip */}
            <div className="mt-3 flex flex-wrap gap-2">
              {match.challenge_ids.map((id) => (
                <span
                  key={id}
                  className="rounded bg-surface-container-low px-2 py-1 font-mono text-[0.5625rem] text-on-surface-dim"
                >
                  {id}
                </span>
              ))}
            </div>

            {/* Three-column match: Raw vs Seed vs Spawn */}
            <div
              className={`mt-4 grid grid-cols-1 items-stretch gap-3 ${
                hasRaw ? "md:grid-cols-[1fr_1fr_1fr]" : "md:grid-cols-[1fr_auto_1fr]"
              }`}
            >
              {hasRaw && (
                <SideCard
                  label="Raw Sonnet"
                  name="No skill guidance"
                  perChallenge={rawScores.map((s) => s ?? 0)}
                  mean={rawMean ?? 0}
                  isWinner={false}
                  variant="baseline"
                />
              )}
              <SideCard
                label={hasRaw ? "Seed (V1)" : "Variant 1 · Seed"}
                name={match.variant_1_label}
                perChallenge={match.variant_1_scores}
                mean={match.variant_1_mean}
                isWinner={match.winner_slot === 1}
              />
              {!hasRaw && (
                <div className="flex items-center justify-center font-mono text-xl text-on-surface-dim">
                  vs
                </div>
              )}
              <SideCard
                label={hasRaw ? "Spawn (V2)" : "Variant 2 · Spawn"}
                name={match.variant_2_label}
                perChallenge={match.variant_2_scores}
                mean={match.variant_2_mean}
                isWinner={match.winner_slot === 2}
              />
            </div>

            {/* Rationale + drill-down toggle */}
            <div className="mt-4 flex flex-col gap-3 rounded-lg bg-surface-container-low p-4 md:flex-row md:items-center md:justify-between">
              <p className="text-xs leading-relaxed text-on-surface">
                <strong className="text-tertiary">{winnerLabel}</strong> won with mean fitness{" "}
                <span className="font-mono">{winnerMean.toFixed(3)}</span> vs{" "}
                <span className="font-mono">{loserMean.toFixed(3)}</span> (winning scores:{" "}
                <span className="font-mono">
                  {winnerScores.map((s) => s.toFixed(3)).join(" / ")}
                </span>
                ; losing scores:{" "}
                <span className="font-mono">
                  {loserScores.map((s) => s.toFixed(3)).join(" / ")}
                </span>
                ). {rationale}
              </p>
              {winnerGenome && (
                <button
                  type="button"
                  onClick={() => setExpandedKey(isExpanded ? null : match.dimension)}
                  className="shrink-0 rounded bg-tertiary/20 px-3 py-1.5 font-mono text-[0.625rem] uppercase tracking-wider text-tertiary transition-colors hover:bg-tertiary/30"
                >
                  {isExpanded ? "hide" : "view winning SKILL.md"}
                </button>
              )}
            </div>

            {/* Expanded SKILL.md */}
            {isExpanded && winnerGenome && (
              <div className="mt-4 rounded-lg bg-surface-container-low p-4">
                <p className="mb-3 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
                  Winning SKILL.md — {winnerGenome.id.slice(0, 48)}
                </p>
                <div className="bible-prose max-h-96 overflow-y-auto">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {stripFrontmatter(winnerGenome.skill_md_content)}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

interface SideCardProps {
  label: string;
  name: string;
  perChallenge: number[];
  mean: number;
  isWinner: boolean;
  variant?: "default" | "baseline";
}

function SideCard({
  label,
  name,
  perChallenge,
  mean,
  isWinner,
  variant = "default",
}: SideCardProps) {
  const borderClass =
    variant === "baseline"
      ? "border-on-surface-dim/30 bg-surface-container-low/50"
      : isWinner
        ? "border-tertiary/60 bg-tertiary/10"
        : "border-outline-variant bg-surface-container-low";

  return (
    <div className={`rounded-lg border p-3 ${borderClass}`}>
      <div className="flex items-center justify-between gap-2">
        <p className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
          {label}
        </p>
        {isWinner && (
          <span className="rounded bg-tertiary/20 px-1.5 py-0.5 font-mono text-[0.5625rem] uppercase tracking-wider text-tertiary">
            ✓ Winner
          </span>
        )}
      </div>
      <p className="mt-2 line-clamp-1 font-mono text-xs text-on-surface">{name}</p>
      <div className="mt-3 space-y-1">
        {perChallenge.map((score, i) => (
          <div key={i} className="flex items-center gap-2 font-mono text-[0.625rem]">
            <span className="text-on-surface-dim">c{i + 1}</span>
            <div className="relative h-2 flex-1 overflow-hidden rounded bg-surface-container-high">
              <div
                className={`h-full ${
                  variant === "baseline"
                    ? "bg-on-surface-dim/30"
                    : isWinner
                      ? "bg-tertiary/60"
                      : "bg-primary/40"
                }`}
                style={{ width: `${Math.max(0, Math.min(1, score)) * 100}%` }}
              />
            </div>
            <span className="w-10 text-right text-on-surface">{score.toFixed(3)}</span>
          </div>
        ))}
      </div>
      <p className="mt-3 flex items-baseline justify-between font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
        <span>mean</span>
        <span className="text-base text-tertiary">{mean.toFixed(3)}</span>
      </p>
    </div>
  );
}

function buildRationale(_match: CompetitionMatch, winnerMean: number, loserMean: number): string {
  const delta = winnerMean - loserMean;
  if (delta < 0.001) {
    return "Both variants scored identically across both sampled challenges — a tie. The tie-break picked the spawned variant (slot 2) by default so the Registry could show evidence of the Spawner's output.";
  }
  if (delta >= 0.1) {
    return "That's a decisive margin — the winning variant passed substantially more L1 checks. The losing side likely tripped a must_not_contain constraint or missed required substrings on at least one challenge.";
  }
  if (delta >= 0.05) {
    return "A noticeable margin driven by at least one challenge where the winning variant outperformed the losing side.";
  }
  return "The margin is narrow (<0.05). On ties or near-ties the L1 scorer isn't fully discriminating on this dimension — higher reviewer layers would help in a real run.";
}

function deriveDimFromId(id: string): string {
  return id
    .replace(/^gen_seed_/, "")
    .replace(/_winner$/, "")
    .replace(/^elixir_phoenix_liveview_?/, "")
    .replace(/_/g, "-");
}

function stripFrontmatter(md: string): string {
  const m = md.match(/^---\s*\n[\s\S]*?\n---\s*\n([\s\S]*)$/);
  return m?.[1] ?? md;
}
