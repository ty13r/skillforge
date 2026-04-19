import { useMemo } from "react";

import type { RunReportChallenge } from "../types";

interface ChallengeGalleryProps {
  challenges: RunReportChallenge[];
}

type CriteriaWithCapability = {
  primary_capability?: string;
  weight?: number;
};

const DIFFICULTY_COLORS: Record<string, string> = {
  easy: "bg-green-500/10 text-green-400",
  medium: "bg-yellow-500/10 text-yellow-400",
  hard: "bg-orange-500/10 text-orange-400",
  legendary: "bg-purple-500/10 text-purple-400",
};

/**
 * Renders the challenges a run's variants were tested against.
 * Groups challenges by their ``scoring.primary_capability`` (the dimension
 * the challenge was designed to stress). For atomic runs with 2 challenges
 * per dimension, this produces 12 capability groups with 2 cards each.
 */
export default function ChallengeGallery({ challenges }: ChallengeGalleryProps) {
  const grouped = useMemo(() => {
    const groups = new Map<string, RunReportChallenge[]>();
    for (const c of challenges) {
      const criteria = (c.evaluation_criteria ?? {}) as CriteriaWithCapability;
      const capability = criteria.primary_capability ?? "uncategorized";
      if (!groups.has(capability)) groups.set(capability, []);
      groups.get(capability)!.push(c);
    }
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [challenges]);

  if (challenges.length === 0) {
    return (
      <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
        <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          Challenge Gallery
        </p>
        <p className="mt-3 text-sm text-on-surface-dim">No challenges recorded for this run.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
      <div className="flex items-baseline justify-between">
        <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          Challenge Gallery
        </p>
        <p className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
          {challenges.length} tests · {grouped.length} capabilities
        </p>
      </div>

      <div className="mt-4 space-y-5">
        {grouped.map(([capability, group]) => (
          <div key={capability}>
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-tertiary">
              {capability.replace(/-/g, " ")}
            </p>
            <div className="mt-2 grid grid-cols-1 gap-3 md:grid-cols-2">
              {group.map((c) => (
                <div
                  key={c.id}
                  className="rounded-lg border border-outline-variant bg-surface-container-low p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
                      {c.id}
                    </p>
                    <span
                      className={`rounded px-2 py-0.5 font-mono text-[0.5625rem] uppercase tracking-wider ${
                        DIFFICULTY_COLORS[c.difficulty] ??
                        "bg-surface-container-high text-on-surface-dim"
                      }`}
                    >
                      {c.difficulty}
                    </span>
                  </div>
                  <p className="mt-2 line-clamp-4 text-xs text-on-surface">{c.prompt}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
