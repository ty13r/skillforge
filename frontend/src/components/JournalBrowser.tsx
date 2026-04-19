import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface JournalEntry {
  slug: string;
  number: number;
  title: string;
  date: string | null;
  duration: string | null;
  participants: string | null;
  filename: string;
  body: string;
}

export default function JournalBrowser() {
  const [entries, setEntries] = useState<JournalEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedSlug = searchParams.get("entry");
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/api/journal/entries")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<JournalEntry[]>;
      })
      .then((data) => {
        setEntries(data);
        if (!selectedSlug && data.length > 0) {
          setSearchParams({ entry: data[0].slug }, { replace: true });
        }
      })
      .catch((err) => setError(String(err)));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Close mobile nav on outside click
  useEffect(() => {
    if (!mobileNavOpen) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setMobileNavOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [mobileNavOpen]);

  const selected = useMemo(
    () => entries?.find((e) => e.slug === selectedSlug) ?? null,
    [entries, selectedSlug],
  );

  const selectEntry = (slug: string) => {
    setSearchParams({ entry: slug });
    setMobileNavOpen(false);
  };

  // Navigate between entries
  const selectedIndex = entries?.findIndex((e) => e.slug === selectedSlug) ?? -1;
  const hasPrev = selectedIndex > 0;
  const hasNext = entries != null && selectedIndex < entries.length - 1;

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-8 md:px-6 md:py-10">
      <div className="flex items-end justify-between">
        <div>
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-tertiary">
            Building in Public
          </p>
          <h1 className="mt-2 font-display text-3xl leading-[1.05] tracking-tight md:text-5xl">
            Project Journal
          </h1>
          <p className="mt-3 text-sm text-on-surface-dim md:text-base">
            The story of how we built SKLD — sessions, decisions, pivots, and lessons learned.
          </p>
        </div>
        <span className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          {entries?.length ?? 0} entries
        </span>
      </div>

      {error && <div className="mt-6 rounded-xl bg-error/10 p-4 text-sm text-error">{error}</div>}

      {/* Mobile entry selector — visible below lg */}
      <div className="relative mt-6 lg:hidden" ref={dropdownRef}>
        <button
          type="button"
          onClick={() => setMobileNavOpen((o) => !o)}
          className="flex w-full items-center justify-between rounded-xl border border-outline-variant bg-surface-container-low px-4 py-3 text-left transition-colors hover:bg-surface-container"
        >
          <div className="min-w-0 flex-1">
            {selected ? (
              <div className="flex items-baseline gap-2">
                <span className="shrink-0 font-mono text-[0.625rem] text-tertiary">
                  #{String(selected.number).padStart(3, "0")}
                </span>
                <span className="truncate text-sm font-medium text-on-surface">
                  {selected.title}
                </span>
              </div>
            ) : (
              <span className="text-sm text-on-surface-dim">Select an entry</span>
            )}
          </div>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className={`ml-2 h-4 w-4 shrink-0 text-on-surface-dim transition-transform ${mobileNavOpen ? "rotate-180" : ""}`}
          >
            <path
              fillRule="evenodd"
              d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
              clipRule="evenodd"
            />
          </svg>
        </button>

        {mobileNavOpen && (
          <div className="absolute left-0 right-0 top-full z-30 mt-1 max-h-80 overflow-y-auto rounded-xl border border-outline-variant bg-surface-container-low shadow-lg">
            <nav className="p-2">
              {entries?.map((entry) => {
                const isActive = selectedSlug === entry.slug;
                return (
                  <button
                    key={entry.slug}
                    onClick={() => selectEntry(entry.slug)}
                    className={`w-full rounded-lg px-3 py-2.5 text-left transition-colors ${
                      isActive
                        ? "bg-tertiary/15 text-tertiary"
                        : "text-on-surface hover:bg-surface-container-high"
                    }`}
                  >
                    <div className="flex items-baseline gap-2">
                      <span className="font-mono text-[0.625rem] text-on-surface-dim">
                        #{String(entry.number).padStart(3, "0")}
                      </span>
                      <span className="text-sm font-medium leading-snug">{entry.title}</span>
                    </div>
                    {entry.date && (
                      <p className="mt-0.5 pl-8 font-mono text-[0.5625rem] text-on-surface-dim">
                        {entry.date}
                      </p>
                    )}
                  </button>
                );
              })}
            </nav>
          </div>
        )}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:mt-8 lg:grid-cols-[280px_1fr]">
        {/* Desktop sidebar — hidden below lg */}
        <aside className="hidden rounded-xl bg-surface-container-low p-4 lg:block">
          {entries == null ? (
            <p className="text-sm text-on-surface-dim">Loading...</p>
          ) : (
            <nav className="space-y-1">
              {entries.map((entry) => {
                const isActive = selectedSlug === entry.slug;
                return (
                  <button
                    key={entry.slug}
                    onClick={() => selectEntry(entry.slug)}
                    className={`w-full rounded-lg px-3 py-2.5 text-left transition-colors ${
                      isActive
                        ? "bg-tertiary/15 text-tertiary"
                        : "text-on-surface hover:bg-surface-container-high"
                    }`}
                  >
                    <div className="flex items-baseline gap-2">
                      <span className="font-mono text-[0.625rem] text-on-surface-dim">
                        #{String(entry.number).padStart(3, "0")}
                      </span>
                      <span className="text-sm font-medium leading-snug">{entry.title}</span>
                    </div>
                    {entry.date && (
                      <p className="mt-0.5 pl-8 font-mono text-[0.5625rem] text-on-surface-dim">
                        {entry.date}
                      </p>
                    )}
                  </button>
                );
              })}
            </nav>
          )}
        </aside>

        {/* Content */}
        <main className="rounded-xl bg-surface-container-lowest p-5 md:p-8">
          {selected ? (
            <>
              <div className="mb-6 flex flex-wrap items-baseline gap-4 border-b border-outline-variant pb-4">
                <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-tertiary">
                  Entry #{String(selected.number).padStart(3, "0")}
                </p>
                {selected.date && (
                  <p className="font-mono text-[0.6875rem] text-on-surface-dim">{selected.date}</p>
                )}
                {selected.duration && (
                  <p className="font-mono text-[0.6875rem] text-on-surface-dim">
                    {selected.duration}
                  </p>
                )}
              </div>
              <article className="bible-prose mt-4 max-w-none text-on-surface">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{selected.body}</ReactMarkdown>
              </article>
              {/* Prev / Next navigation */}
              <div className="mt-10 flex items-center justify-between border-t border-outline-variant pt-6">
                {hasPrev ? (
                  <button
                    onClick={() => selectEntry(entries![selectedIndex - 1].slug)}
                    className="group flex items-center gap-2 text-sm text-on-surface-dim transition-colors hover:text-on-surface"
                  >
                    <span className="transition-transform group-hover:-translate-x-0.5">←</span>
                    <span className="font-mono text-[0.625rem]">
                      #{String(entries![selectedIndex - 1].number).padStart(3, "0")}
                    </span>
                    <span className="hidden sm:inline">{entries![selectedIndex - 1].title}</span>
                  </button>
                ) : (
                  <div />
                )}
                {hasNext ? (
                  <button
                    onClick={() => selectEntry(entries![selectedIndex + 1].slug)}
                    className="group flex items-center gap-2 text-sm text-on-surface-dim transition-colors hover:text-on-surface"
                  >
                    <span className="hidden sm:inline">{entries![selectedIndex + 1].title}</span>
                    <span className="font-mono text-[0.625rem]">
                      #{String(entries![selectedIndex + 1].number).padStart(3, "0")}
                    </span>
                    <span className="transition-transform group-hover:translate-x-0.5">→</span>
                  </button>
                ) : (
                  <div />
                )}
              </div>
            </>
          ) : (
            <p className="text-on-surface-dim">Select an entry from the left.</p>
          )}
        </main>
      </div>
    </div>
  );
}
