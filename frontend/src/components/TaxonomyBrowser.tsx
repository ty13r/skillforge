import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { SkillFamily, TaxonomyNode } from "../types";

/**
 * Taxonomy tree view + per-family drill-down.
 *
 * Loads the full taxonomy (`GET /api/taxonomy`) and all families
 * (`GET /api/families`) on mount, then renders a two-column layout:
 *   - Left: collapsible tree Domain → Focus → Language with per-node
 *     family counts.
 *   - Right: list of families under the currently-selected taxonomy node,
 *     with a link through to the family detail page.
 *
 * Families without any taxonomy assignment live in an "Unclassified" bucket
 * at the bottom so they still surface in the UI.
 */

type FilterSelection = {
  domain_id: string | null;
  focus_id: string | null;
  language_id: string | null;
};

const INITIAL_FILTER: FilterSelection = {
  domain_id: null,
  focus_id: null,
  language_id: null,
};

function countFamiliesUnderNode(
  node: TaxonomyNode,
  nodes: TaxonomyNode[],
  families: SkillFamily[],
): number {
  // Gather ids of this node + all descendants so a domain count includes
  // every family tagged with its focuses/languages.
  const descendants = new Set<string>([node.id]);
  let changed = true;
  while (changed) {
    changed = false;
    for (const n of nodes) {
      if (n.parent_id && descendants.has(n.parent_id) && !descendants.has(n.id)) {
        descendants.add(n.id);
        changed = true;
      }
    }
  }
  return families.filter(
    (f) =>
      (f.domain_id && descendants.has(f.domain_id)) ||
      (f.focus_id && descendants.has(f.focus_id)) ||
      (f.language_id && descendants.has(f.language_id)),
  ).length;
}

function familiesMatchingFilter(
  families: SkillFamily[],
  filter: FilterSelection,
): SkillFamily[] {
  return families.filter((f) => {
    if (filter.domain_id && f.domain_id !== filter.domain_id) return false;
    if (filter.focus_id && f.focus_id !== filter.focus_id) return false;
    if (filter.language_id && f.language_id !== filter.language_id) return false;
    return true;
  });
}

export default function TaxonomyBrowser() {
  const [nodes, setNodes] = useState<TaxonomyNode[] | null>(null);
  const [families, setFamilies] = useState<SkillFamily[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterSelection>(INITIAL_FILTER);

  useEffect(() => {
    Promise.all([
      fetch("/api/taxonomy").then((r) =>
        r.ok ? (r.json() as Promise<TaxonomyNode[]>) : Promise.reject(r.statusText),
      ),
      fetch("/api/families").then((r) =>
        r.ok ? (r.json() as Promise<SkillFamily[]>) : Promise.reject(r.statusText),
      ),
    ])
      .then(([taxonomy, fams]) => {
        setNodes(taxonomy);
        setFamilies(fams);
      })
      .catch((err) => setError(String(err)));
  }, []);

  const domains = useMemo(
    () => (nodes ?? []).filter((n) => n.level === "domain"),
    [nodes],
  );

  const focusesByDomain = useMemo(() => {
    const map = new Map<string, TaxonomyNode[]>();
    for (const n of nodes ?? []) {
      if (n.level !== "focus" || !n.parent_id) continue;
      if (!map.has(n.parent_id)) map.set(n.parent_id, []);
      map.get(n.parent_id)!.push(n);
    }
    return map;
  }, [nodes]);

  const languagesByFocus = useMemo(() => {
    const map = new Map<string, TaxonomyNode[]>();
    for (const n of nodes ?? []) {
      if (n.level !== "language" || !n.parent_id) continue;
      if (!map.has(n.parent_id)) map.set(n.parent_id, []);
      map.get(n.parent_id)!.push(n);
    }
    return map;
  }, [nodes]);

  const filteredFamilies = useMemo(() => {
    if (!families) return [];
    return familiesMatchingFilter(families, filter);
  }, [families, filter]);

  const isLoading = nodes == null || families == null;
  const hasNoFilter =
    filter.domain_id == null &&
    filter.focus_id == null &&
    filter.language_id == null;

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-10">
      <header className="flex items-end justify-between">
        <div>
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-primary">
            Protocol: Taxonomy
          </p>
          <h1 className="mt-2 font-display text-5xl leading-[1.05] tracking-tight">
            Skill <span className="text-primary">Taxonomy</span>
          </h1>
          <p className="mt-3 max-w-2xl text-on-surface-dim">
            Browse the Domain → Focus → Language hierarchy. Pick any node to
            filter the family list to variants that live underneath it.
          </p>
        </div>
        <div className="text-right font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          {nodes?.length ?? 0} nodes · {families?.length ?? 0} families
        </div>
      </header>

      {error && (
        <div className="mt-6 rounded-xl bg-error/10 p-4 text-sm text-error">
          {error}
        </div>
      )}

      {isLoading ? (
        <p className="mt-10 text-on-surface-dim">Loading taxonomy…</p>
      ) : (
        <div className="mt-8 grid gap-6 lg:grid-cols-[320px,1fr]">
          {/* ── Tree column ──────────────────────────────────────────── */}
          <aside className="rounded-xl border border-outline-variant bg-surface-container-lowest p-4">
            <div className="flex items-center justify-between pb-3">
              <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                Hierarchy
              </p>
              <button
                type="button"
                onClick={() => setFilter(INITIAL_FILTER)}
                className="font-mono text-[0.625rem] uppercase tracking-wider text-primary hover:underline"
              >
                Clear
              </button>
            </div>
            <ul className="space-y-1 text-sm">
              {domains.map((dom) => {
                const domCount = countFamiliesUnderNode(
                  dom,
                  nodes ?? [],
                  families ?? [],
                );
                const isDomActive = filter.domain_id === dom.id;
                const focuses = focusesByDomain.get(dom.id) ?? [];
                return (
                  <li key={dom.id}>
                    <button
                      type="button"
                      onClick={() =>
                        setFilter({
                          domain_id: isDomActive ? null : dom.id,
                          focus_id: null,
                          language_id: null,
                        })
                      }
                      className={`flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left transition-colors ${
                        isDomActive
                          ? "bg-primary/15 text-primary"
                          : "hover:bg-surface-container-low"
                      }`}
                    >
                      <span className="font-medium">{dom.label}</span>
                      <span className="font-mono text-[0.625rem] text-on-surface-dim">
                        {domCount}
                      </span>
                    </button>
                    {isDomActive && focuses.length > 0 && (
                      <ul className="ml-4 mt-1 space-y-1 border-l border-outline-variant pl-3">
                        {focuses.map((foc) => {
                          const focCount = countFamiliesUnderNode(
                            foc,
                            nodes ?? [],
                            families ?? [],
                          );
                          const isFocActive = filter.focus_id === foc.id;
                          const languages = languagesByFocus.get(foc.id) ?? [];
                          return (
                            <li key={foc.id}>
                              <button
                                type="button"
                                onClick={() =>
                                  setFilter({
                                    domain_id: dom.id,
                                    focus_id: isFocActive ? null : foc.id,
                                    language_id: null,
                                  })
                                }
                                className={`flex w-full items-center justify-between rounded-lg px-2 py-1 text-left text-[0.8125rem] transition-colors ${
                                  isFocActive
                                    ? "bg-primary/10 text-primary"
                                    : "hover:bg-surface-container-low"
                                }`}
                              >
                                <span>{foc.label}</span>
                                <span className="font-mono text-[0.5625rem] text-on-surface-dim">
                                  {focCount}
                                </span>
                              </button>
                              {isFocActive && languages.length > 0 && (
                                <ul className="ml-3 mt-0.5 space-y-0.5 border-l border-outline-variant pl-2">
                                  {languages.map((lng) => {
                                    const lngCount = countFamiliesUnderNode(
                                      lng,
                                      nodes ?? [],
                                      families ?? [],
                                    );
                                    const isLngActive =
                                      filter.language_id === lng.id;
                                    return (
                                      <li key={lng.id}>
                                        <button
                                          type="button"
                                          onClick={() =>
                                            setFilter({
                                              domain_id: dom.id,
                                              focus_id: foc.id,
                                              language_id: isLngActive
                                                ? null
                                                : lng.id,
                                            })
                                          }
                                          className={`flex w-full items-center justify-between rounded-lg px-2 py-0.5 text-left text-[0.75rem] transition-colors ${
                                            isLngActive
                                              ? "bg-primary/10 text-primary"
                                              : "hover:bg-surface-container-low"
                                          }`}
                                        >
                                          <span className="font-mono text-[0.6875rem]">
                                            {lng.slug}
                                          </span>
                                          <span className="font-mono text-[0.5625rem] text-on-surface-dim">
                                            {lngCount}
                                          </span>
                                        </button>
                                      </li>
                                    );
                                  })}
                                </ul>
                              )}
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </li>
                );
              })}
            </ul>
          </aside>

          {/* ── Families column ────────────────────────────────────────── */}
          <section>
            <div className="flex items-end justify-between">
              <div>
                <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-primary">
                  Families
                </p>
                <h2 className="mt-1 font-display text-2xl tracking-tight">
                  {hasNoFilter ? "All families" : "Filtered families"}
                </h2>
              </div>
              <span className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                {filteredFamilies.length} matches
              </span>
            </div>

            {filteredFamilies.length === 0 ? (
              <p className="mt-6 text-on-surface-dim">
                No families match the current filter.
              </p>
            ) : (
              <ul className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
                {filteredFamilies.map((fam) => (
                  <li key={fam.id}>
                    <Link
                      to={`/registry?family=${fam.slug}`}
                      className="block rounded-xl border border-outline-variant bg-surface-container-lowest p-4 transition-all hover:border-primary/40 hover:shadow-elevated"
                    >
                      <div className="flex items-start justify-between">
                        <span
                          className={`rounded-full px-2 py-0.5 font-mono text-[0.5625rem] uppercase tracking-wider ${
                            fam.decomposition_strategy === "atomic"
                              ? "bg-primary/10 text-primary"
                              : "bg-surface-container-high text-on-surface-dim"
                          }`}
                        >
                          {fam.decomposition_strategy}
                        </span>
                        <span className="font-mono text-[0.625rem] text-on-surface-dim">
                          {fam.slug}
                        </span>
                      </div>
                      <h3 className="mt-2 font-display text-lg tracking-tight">
                        {fam.label}
                      </h3>
                      <p className="mt-1 line-clamp-2 text-sm text-on-surface-dim">
                        {fam.specialization}
                      </p>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
