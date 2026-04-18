import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ResearchEntry {
  slug: string;
  category: string;
  title: string;
  filename: string;
  body: string;
}

interface ResearchResponse {
  narrative: ResearchEntry[];
  audits: ResearchEntry[];
  external_papers: ResearchEntry[];
}

const CATEGORY_LABELS: Record<string, string> = {
  narrative: "Narrative",
  audits: "Audits",
  external_papers: "External Papers",
};

export default function ResearchBrowser() {
  const { category, slug } = useParams();
  const navigate = useNavigate();
  const urlSlug = category && slug ? `${category}/${slug}` : null;
  const [data, setData] = useState<ResearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(urlSlug);

  useEffect(() => {
    fetch("/api/research/entries")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<ResearchResponse>;
      })
      .then((d) => {
        setData(d);
        if (!urlSlug) {
          const first = d.narrative[0] ?? d.audits[0] ?? d.external_papers[0];
          if (first) setSelectedSlug(first.slug);
        }
      })
      .catch((err) => setError(String(err)));
  }, [urlSlug]);

  useEffect(() => {
    if (urlSlug) setSelectedSlug(urlSlug);
  }, [urlSlug]);

  const selectSlug = (next: string) => {
    setSelectedSlug(next);
    navigate(`/research/${next}`);
  };

  const allEntries = useMemo(() => {
    if (!data) return [];
    return [
      ...(data.narrative ?? []),
      ...(data.audits ?? []),
      ...(data.external_papers ?? []),
    ];
  }, [data]);

  const selected = useMemo(
    () => allEntries.find((e) => e.slug === selectedSlug) ?? null,
    [allEntries, selectedSlug],
  );

  const groups: { key: keyof ResearchResponse; entries: ResearchEntry[] }[] =
    data
      ? [
          { key: "narrative", entries: data.narrative ?? [] },
          { key: "audits", entries: data.audits ?? [] },
          { key: "external_papers", entries: data.external_papers ?? [] },
        ]
      : [];

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-10">
      <div className="flex items-end justify-between">
        <div>
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-tertiary">
            Protocol: Research
          </p>
          <h1 className="mt-2 font-display text-5xl leading-[1.05] tracking-tight">
            <span className="text-secondary">Research</span>
          </h1>
          <p className="mt-3 max-w-2xl text-on-surface-dim">
            The research angle: the problem SKLD is solving, the prior work it
            builds on, the methodology and evaluation stack, the findings so
            far, and the questions still open. Built for reviewers, not
            marketers.
          </p>
        </div>
      </div>

      {error && (
        <div className="mt-6 rounded-xl bg-error/10 p-4 text-sm text-error">
          {error}
        </div>
      )}

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[280px_1fr]">
        <aside className="rounded-xl bg-surface-container-low p-4">
          {data == null ? (
            <p className="text-sm text-on-surface-dim">Loading...</p>
          ) : (
            <nav className="space-y-6">
              {groups.map(({ key, entries }) =>
                entries.length === 0 ? null : (
                  <div key={key}>
                    <p className="mb-2 px-2 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
                      {CATEGORY_LABELS[key]} · {entries.length}
                    </p>
                    <ul className="space-y-0.5">
                      {entries.map((e) => (
                        <li key={e.slug}>
                          <button
                            onClick={() => selectSlug(e.slug)}
                            className={`w-full rounded-lg px-2 py-1.5 text-left text-sm transition-colors ${
                              selectedSlug === e.slug
                                ? key === "narrative"
                                  ? "bg-tertiary/15 text-tertiary"
                                  : "bg-secondary/15 text-secondary"
                                : "text-on-surface hover:bg-surface-container-high"
                            } ${key === "narrative" ? "font-medium" : ""}`}
                          >
                            {e.title}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                ),
              )}
            </nav>
          )}
        </aside>

        <main className="rounded-xl bg-surface-container-lowest p-8">
          {selected ? (
            <>
              <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                {CATEGORY_LABELS[selected.category] ?? selected.category}
                {" · "}
                {selected.filename}
              </p>
              <article className="bible-prose mt-4 max-w-none text-on-surface">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {selected.body}
                </ReactMarkdown>
              </article>
            </>
          ) : (
            <p className="text-on-surface-dim">Select an entry from the left.</p>
          )}
        </main>
      </div>
    </div>
  );
}
