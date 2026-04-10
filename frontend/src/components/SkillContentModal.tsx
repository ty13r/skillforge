import { useEffect } from "react";
import CodeViewer from "./CodeViewer";

interface SkillContentModalProps {
  skillMdContent?: string;
  supportingFiles?: string[];
  traits?: string[];
  mutations?: string[];
  mutationRationale?: string;
  onClose: () => void;
}

export default function SkillContentModal({
  skillMdContent,
  supportingFiles,
  traits,
  mutations,
  mutationRationale,
  onClose,
}: SkillContentModalProps) {
  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const hasFiles = supportingFiles && supportingFiles.length > 0;
  const totalFiles = 1 + (supportingFiles?.length ?? 0);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="max-h-[80vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-outline-variant bg-surface-container-lowest p-6 shadow-elevated">
        <div className="flex items-start justify-between">
          <div className="flex items-baseline gap-2">
            <h2 className="font-display text-xl tracking-tight">Skill Package</h2>
            <span className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
              {totalFiles} {totalFiles === 1 ? "FILE" : "FILES"}
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-on-surface-dim transition-colors hover:text-on-surface"
          >
            &#x2715;
          </button>
        </div>

        {/* Traits */}
        {traits && traits.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1">
            {traits.map((t) => (
              <span key={t} className="rounded-full bg-primary/10 px-2 py-0.5 font-mono text-[0.625rem] text-primary">
                {t}
              </span>
            ))}
          </div>
        )}

        {/* Mutations */}
        {mutations && mutations.length > 0 && (
          <div className="mt-3">
            <p className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
              Mutations
            </p>
            <div className="mt-1 flex flex-wrap gap-1">
              {mutations.map((m) => (
                <span key={m} className="rounded-full bg-tertiary/10 px-2 py-0.5 font-mono text-[0.625rem] text-tertiary">
                  {m}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Mutation rationale */}
        {mutationRationale && (
          <p className="mt-2 text-sm text-on-surface-dim italic">
            {mutationRationale}
          </p>
        )}

        {/* Supporting files list */}
        {hasFiles && (
          <div className="mt-4 rounded-xl border border-outline-variant bg-surface-container-low p-4">
            <p className="mb-2 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
              Supporting Files
            </p>
            <div className="space-y-0.5">
              {supportingFiles.map((path) => (
                <p
                  key={path}
                  className="font-mono text-xs text-on-surface-dim px-2 py-1"
                >
                  {path}
                </p>
              ))}
            </div>
            <p className="mt-2 text-[0.625rem] text-on-surface-dim italic">
              Full package available in the skill registry detail view.
            </p>
          </div>
        )}

        {/* SKILL.md content */}
        <div className="mt-4 rounded-xl border border-outline-variant bg-surface-container-low p-4">
          <p className="mb-2 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
            SKILL.md
          </p>
          {skillMdContent ? (
            <CodeViewer code={skillMdContent} filePath="SKILL.md" className="max-h-[50vh] overflow-y-auto" />
          ) : (
            <p className="text-sm text-on-surface-dim">
              Skill content not available (demo run or skill not yet persisted).
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
