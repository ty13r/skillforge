import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";

interface BibleEntry {
  slug: string;
  category: string;
  title: string;
  filename: string;
  body: string;
}

interface BibleResponse {
  patterns: BibleEntry[];
  findings: BibleEntry[];
  anti_patterns: BibleEntry[];
}

const CATEGORY_LABELS: Record<string, string> = {
  patterns: "Patterns",
  findings: "Findings",
  anti_patterns: "Anti-Patterns",
};

export default function BibleBrowser() {
  const [data, setData] = useState<BibleResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/bible/entries")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<BibleResponse>;
      })
      .then((d) => {
        setData(d);
        // Auto-select the first pattern on load
        const first = d.patterns[0] ?? d.findings[0];
        if (first) setSelectedSlug(first.slug);
      })
      .catch((err) => setError(String(err)));
  }, []);

  const allEntries = useMemo(() => {
    if (!data) return [];
    return [...data.patterns, ...data.findings, ...data.anti_patterns];
  }, [data]);

  const selected = useMemo(
    () => allEntries.find((e) => e.slug === selectedSlug) ?? null,
    [allEntries, selectedSlug],
  );

  const groups: { key: keyof BibleResponse; entries: BibleEntry[] }[] = data
    ? [
        { key: "patterns", entries: data.patterns },
        { key: "findings", entries: data.findings },
        { key: "anti_patterns", entries: data.anti_patterns },
      ]
    : [];

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-10">
      <div className="flex items-end justify-between">
        <div>
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-tertiary">
            Protocol: Knowledge
          </p>
          <h1 className="mt-2 font-display text-5xl leading-[1.05] tracking-tight">
            The <span className="text-secondary">Claude Skills Bible</span>
          </h1>
          <p className="mt-3 max-w-2xl text-on-surface-dim">
            Empirically-validated patterns harvested from every evolution run.
            The Breeder publishes new findings here after each generation.
          </p>
        </div>
      </div>

      {error && (
        <div className="mt-6 rounded-xl bg-error/10 p-4 text-sm text-error">
          {error}
        </div>
      )}

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[280px_1fr]">
        {/* Sidebar */}
        <aside className="rounded-xl bg-surface-container-low p-4">
          {data == null ? (
            <p className="text-sm text-on-surface-dim">Loading…</p>
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
                            onClick={() => setSelectedSlug(e.slug)}
                            className={`w-full rounded-lg px-2 py-1.5 text-left text-sm transition-colors ${
                              selectedSlug === e.slug
                                ? "bg-secondary/15 text-secondary"
                                : "text-on-surface hover:bg-surface-container-high"
                            }`}
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

        {/* Content */}
        <main className="rounded-xl bg-surface-container-lowest p-8">
          {selected ? (
            <>
              <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                {CATEGORY_LABELS[selected.category as keyof BibleResponse] ??
                  selected.category}
                {" · "}
                {selected.filename}
              </p>
              <article className="bible-prose mt-4 max-w-none text-on-surface">
                <ReactMarkdown>{selected.body}</ReactMarkdown>
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
