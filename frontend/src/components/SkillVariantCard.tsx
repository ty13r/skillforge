import { useMemo, useState } from "react";

import SkillContentModal from "./SkillContentModal";
import StatusGlow from "./StatusGlow";
import type { CompetitorState, CompetitorView } from "../types";

interface ChallengeInfo {
  id: string;
  index: number;
  prompt: string;
  difficulty: string;
}

interface SkillVariantCardProps {
  variantIndex: number;
  skillId: string;
  isControl: boolean;
  competitors: CompetitorView[];
  challenges: ChallengeInfo[];
}

const ACTIVE_STATES: ReadonlySet<CompetitorState> = new Set([
  "writing",
  "testing",
  "iterating",
]);

const STATE_LABEL_SHORT: Record<CompetitorState, string> = {
  queued: "queued",
  writing: "writing...",
  testing: "testing...",
  iterating: "iterating...",
  done: "done \u2713",
  error: "error",
};

export default function SkillVariantCard({
  variantIndex,
  skillId,
  isControl,
  competitors,
  challenges,
}: SkillVariantCardProps) {
  const letter = String.fromCharCode(65 + variantIndex);
  const [showModal, setShowModal] = useState(false);
  const firstCompetitor = competitors[0] ?? undefined;

  const { doneCount, total, anyActive } = useMemo(() => {
    let done = 0;
    let active = false;
    for (const c of competitors) {
      if (c.state === "done") done++;
      if (ACTIVE_STATES.has(c.state)) active = true;
    }
    return { doneCount: done, total: competitors.length, anyActive: active };
  }, [competitors]);

  const allDone = doneCount === total && total > 0;

  return (
    <div
      className={
        "rounded-xl border px-5 py-4 transition-all " +
        (anyActive
          ? "border-primary/40 bg-surface-container-lowest animate-breathe-border"
          : allDone
            ? "border-tertiary/30 bg-surface-container-lowest"
            : "border-outline-variant bg-surface-container-lowest hover:bg-surface-container-low")
      }
    >
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-container-high">
          <StatusGlow
            variant={anyActive ? "running" : allDone ? "success" : "neutral"}
            pulse={anyActive}
          />
        </div>
        <p className="text-base font-medium text-on-surface">
          Variant {letter}
        </p>
        {isControl && (
          <span className="rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 font-mono text-[0.5625rem] uppercase tracking-wider text-primary">
            Control
          </span>
        )}
        <button
          onClick={() => setShowModal(true)}
          className="ml-auto font-mono text-[0.5625rem] uppercase tracking-wider text-on-surface-dim transition-colors hover:text-primary"
        >
          View Skill
        </button>
        <span className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
          {skillId.slice(0, 8)}
        </span>
        <span
          className={
            "font-mono text-[0.6875rem] uppercase tracking-wider " +
            (allDone
              ? "text-tertiary"
              : anyActive
                ? "text-primary"
                : "text-on-surface-dim")
          }
        >
          {allDone
            ? `${doneCount}/${total} done \u2713`
            : anyActive
              ? `${doneCount}/${total} writing...`
              : `${doneCount}/${total}`}
        </span>
      </div>

      {/* Trait chips */}
      {firstCompetitor?.traits && firstCompetitor.traits.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1">
          {firstCompetitor.traits.slice(0, 3).map((t) => (
            <span key={t} className="rounded-full bg-surface-container-low px-1.5 py-0.5 font-mono text-[0.5rem] text-on-surface-dim">
              {t}
            </span>
          ))}
        </div>
      )}

      {/* Mutation rationale */}
      {!isControl && firstCompetitor?.mutationRationale && (
        <p className="mt-1 text-[0.6875rem] text-on-surface-dim italic">
          {firstCompetitor.mutationRationale}
        </p>
      )}

      {/* Challenge sub-rows */}
      {challenges.length > 0 && (
        <div className="mt-3 space-y-0.5">
          {challenges.map((ch) => {
            const match = competitors.find((c) => c.challengeId === ch.id);
            const state: CompetitorState = match?.state ?? "queued";
            const isActive = ACTIVE_STATES.has(state);
            return (
              <div
                key={ch.id}
                className={
                  "flex items-center gap-2 rounded-lg px-3 py-1.5 " +
                  (isActive
                    ? "bg-primary/5"
                    : state === "done"
                      ? "bg-tertiary/5"
                      : "bg-transparent")
                }
                style={{ minHeight: "32px" }}
              >
                <span className="font-mono text-[0.5625rem] uppercase tracking-wider text-on-surface-dim">
                  Ch {ch.index + 1}
                </span>
                <span
                  className={`rounded-full px-1.5 py-0.5 font-mono text-[0.5rem] uppercase tracking-wider ${
                    ch.difficulty === "hard"
                      ? "bg-error/10 text-error"
                      : ch.difficulty === "medium"
                        ? "bg-warning/10 text-warning"
                        : "bg-tertiary/10 text-tertiary"
                  }`}
                >
                  {ch.difficulty}
                </span>
                <span
                  className={
                    "ml-auto font-mono text-[0.5625rem] uppercase tracking-wider " +
                    (isActive
                      ? "text-primary"
                      : state === "done"
                        ? "text-tertiary"
                        : state === "error"
                          ? "text-error"
                          : "text-on-surface-dim")
                  }
                >
                  {STATE_LABEL_SHORT[state]}
                </span>
                {match?.state === "writing" && match.turn != null && (
                  <span className="font-mono text-[0.5625rem] text-primary">
                    Turn {match.turn}{match.lastTool ? ` \u00b7 ${match.lastTool}` : ""}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {showModal && (
        <SkillContentModal
          skillMdContent={firstCompetitor?.skillMdContent}
          traits={firstCompetitor?.traits}
          mutations={firstCompetitor?.mutations}
          mutationRationale={firstCompetitor?.mutationRationale}
          onClose={() => setShowModal(false)}
        />
      )}
    </div>
  );
}
