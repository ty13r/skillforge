import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface CompositeMarkdownViewProps {
  skillMd: string | null;
  skillMdError: string | null;
  bestSkillId: string | null;
}

/**
 * Rendered view of a composite SKILL.md with a raw-text toggle.
 *
 * Extracts the frontmatter (``--- ... ---``) to display the name + description
 * as a header, then renders the body as GFM Markdown. Falls back to a
 * placeholder if the backend 404'd (fake/incomplete runs).
 */
export default function CompositeMarkdownView({
  skillMd,
  skillMdError,
  bestSkillId,
}: CompositeMarkdownViewProps) {
  const [showRaw, setShowRaw] = useState(false);

  const { name, description, body } = useMemo(() => {
    if (!skillMd) {
      return { name: null, description: null, body: null };
    }
    // Basic frontmatter split.
    const fmMatch = skillMd.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/);
    if (!fmMatch) {
      return { name: null, description: null, body: skillMd };
    }
    const fm = fmMatch[1];
    const bodyText = fmMatch[2];
    const nameMatch = fm.match(/^name:\s*(.+)$/m);
    const descMatch = fm.match(/^description:\s*([\s\S]+?)(?:\n\w|\n---|$)/m);
    return {
      name: nameMatch?.[1].trim() ?? null,
      description: descMatch?.[1].trim().replace(/\s+/g, " ") ?? null,
      body: bodyText,
    };
  }, [skillMd]);

  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container-lowest">
      <div className="flex items-start justify-between gap-4 border-b border-outline-variant p-6">
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Composite Skill — {bestSkillId?.slice(0, 16) ?? "—"}
          </p>
          {name && (
            <h2 className="mt-2 font-display text-3xl leading-tight tracking-tight">{name}</h2>
          )}
          {description && <p className="mt-2 text-sm text-on-surface-dim">{description}</p>}
        </div>
        <button
          type="button"
          onClick={() => setShowRaw((v) => !v)}
          className="shrink-0 rounded bg-surface-container-high px-3 py-1.5 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface transition-colors hover:bg-surface-container-highest"
        >
          {showRaw ? "Rendered" : "Raw"}
        </button>
      </div>

      <div className="max-h-[720px] overflow-y-auto p-6">
        {skillMdError ? (
          <div className="flex h-64 flex-col items-center justify-center rounded-lg border border-dashed border-on-surface-dim/20 p-6 text-center">
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
              No SKILL.md artifact
            </p>
            <p className="mt-2 max-w-xs text-xs text-on-surface-dim">
              This run has no persisted composite skill. Real evolutions render the full evolved
              SKILL.md here.
            </p>
          </div>
        ) : !skillMd ? (
          <div className="flex h-64 items-center justify-center text-xs text-on-surface-dim">
            Loading SKILL.md…
          </div>
        ) : showRaw ? (
          <pre className="whitespace-pre-wrap font-mono text-xs text-on-surface">{skillMd}</pre>
        ) : (
          <div className="bible-prose">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{body ?? skillMd}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
