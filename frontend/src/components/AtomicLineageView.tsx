import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { LineageEdge, LineageNode, RunReportGenome } from "../types";

interface AtomicLineageViewProps {
  nodes: LineageNode[];
  edges: LineageEdge[];
  genomes: RunReportGenome[];
}

/**
 * Split a composite SKILL.md body into section bodies keyed by section slug.
 * Uses the H2 (##) headings as section boundaries.
 */
function parseCompositeSections(compositeMd: string): Map<string, string> {
  const out = new Map<string, string>();
  // Strip frontmatter if present.
  const fmStripped =
    compositeMd.match(/^---\s*\n[\s\S]*?\n---\s*\n([\s\S]*)$/)?.[1] ??
    compositeMd;
  const lines = fmStripped.split("\n");
  let currentHeading: string | null = null;
  let currentBody: string[] = [];
  for (const line of lines) {
    const m = line.match(/^##\s+(.+)$/);
    if (m) {
      if (currentHeading) {
        out.set(
          normalizeHeading(currentHeading),
          currentBody.join("\n").trim(),
        );
      }
      currentHeading = m[1];
      currentBody = [];
    } else if (currentHeading) {
      currentBody.push(line);
    }
  }
  if (currentHeading) {
    out.set(normalizeHeading(currentHeading), currentBody.join("\n").trim());
  }
  return out;
}

function normalizeHeading(heading: string): string {
  return heading
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

const PARENT_TO_COMPOSITE_SECTION: Record<string, string[]> = {
  "architectural-stance": ["architectural-skeleton-foundation"],
  "heex-and-verified-routes": ["heex-verified-routes"],
  "function-components-and-slots": ["function-components-slots"],
  "live-components-stateful": ["livecomponents-stateful"],
  "form-handling": ["forms-nested-associations"],
  "streams-and-collections": ["streams-collections"],
  "mount-and-lifecycle": ["mount-lifecycle-async-load"],
  "event-handlers-and-handle-info": ["event-handlers-handle-info"],
  "pubsub-and-realtime": ["pubsub-realtime"],
  "navigation-patterns": ["navigation-patterns"],
  "auth-and-authz": ["auth-authz"],
  "anti-patterns-catalog": ["anti-patterns-catalog"],
};

function deriveDimensionSlug(g: RunReportGenome): string {
  return g.id
    .replace(/^gen_seed_/, "")
    .replace(/_winner$/, "")
    .replace(/^elixir_phoenix_liveview_?/, "")
    .replace(/_/g, "-");
}

function stripFrontmatter(md: string): string {
  const m = md.match(/^---\s*\n[\s\S]*?\n---\s*\n([\s\S]*)$/);
  return m?.[1] ?? md;
}

/**
 * Replacement for SkillDiffViewer when the run is in atomic mode.
 *
 * The old viewer ran diffLines() between a parent and child genome and
 * rendered colored block diffs — which makes no sense for an atomic
 * composite, where the composite is an ASSEMBLY of 12 unrelated parents,
 * not a MUTATION of any single one. Every line looked "removed" from the
 * parent and "added" to the composite, which is noise.
 *
 * This view instead shows the composite at the top + a grid of the 12
 * parent variants below. Click a parent card to reveal the parent's
 * SKILL.md inline (no fake diff). A user can see exactly what each parent
 * contributed without being told lies about what "changed."
 */
export default function AtomicLineageView({
  nodes,
  edges,
  genomes,
}: AtomicLineageViewProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Partition nodes into composite (generation 1, engineer_composite) and
  // its parents (everything else reachable via an assembly edge).
  const { composite, parents } = useMemo(() => {
    const genomesById = new Map<string, RunReportGenome>();
    for (const g of genomes) genomesById.set(g.id, g);

    let composite: LineageNode | undefined;
    for (const n of nodes) {
      const g = genomesById.get(n.id);
      if (g?.meta_strategy === "engineer_composite") {
        composite = n;
        break;
      }
    }
    if (!composite) {
      return { composite: undefined, parents: [] as LineageNode[] };
    }
    const parentIds = new Set(
      edges
        .filter((e) => e.child_id === composite!.id)
        .map((e) => e.parent_id),
    );
    const parentNodes = nodes.filter((n) => parentIds.has(n.id));
    return { composite, parents: parentNodes };
  }, [nodes, edges, genomes]);

  const expanded = useMemo(() => {
    if (!expandedId) return null;
    return genomes.find((g) => g.id === expandedId) ?? null;
  }, [expandedId, genomes]);

  // Parse the composite body into sections by H2 heading so we can show a
  // side-by-side "what this parent contributed" view when a parent card is
  // clicked. The composite genome is the one with meta_strategy === 'engineer_composite'.
  const compositeSections = useMemo(() => {
    const compositeGenome = genomes.find(
      (g) => g.meta_strategy === "engineer_composite",
    );
    if (!compositeGenome) return new Map<string, string>();
    return parseCompositeSections(compositeGenome.skill_md_content);
  }, [genomes]);

  const expandedDim = useMemo(() => {
    if (!expanded) return null;
    return deriveDimensionSlug(expanded);
  }, [expanded]);

  const contributedSection = useMemo(() => {
    if (!expandedDim) return null;
    const candidates = PARENT_TO_COMPOSITE_SECTION[expandedDim] ?? [];
    for (const slug of candidates) {
      // Try exact match first.
      const body = compositeSections.get(slug);
      if (body) return { slug, body };
      // Try fuzzy: find any section whose slug contains all parts.
      const parts = slug.split("-");
      for (const [k, v] of compositeSections.entries()) {
        if (parts.every((p) => k.includes(p))) {
          return { slug: k, body: v };
        }
      }
    }
    return null;
  }, [expandedDim, compositeSections]);

  // Auto-select the first parent (foundation) once parents are loaded so
  // the right panel shows content on first render. Without this the user
  // sees a blank "select a parent" placeholder on arrival.
  useEffect(() => {
    if (!expandedId && parents.length > 0) {
      setExpandedId(parents[0].id);
    }
  }, [parents, expandedId]);

  if (!composite) {
    return (
      <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
        <p className="text-sm text-on-surface-dim">
          No composite genome found for this atomic run.
        </p>
      </div>
    );
  }

  const compositeGenome = genomes.find((g) => g.id === composite.id);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
        <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          Assembly graph · Not a mutation diff
        </p>
        <div className="mt-3 space-y-2 text-sm text-on-surface-dim">
          <p>
            Atomic composites are <strong className="text-on-surface">assembled</strong>{" "}
            from many independent parents, not <em>mutated</em> from one.
            Running a line-by-line diff between a parent (e.g. the
            heex-and-verified-routes variant) and the composite would produce
            nonsense — the parent's ~30 lines all appear "removed" and the
            composite's ~300 lines all appear "added", because they're about
            completely different topics. The traditional Lineage Diff Viewer
            is reserved for <strong className="text-on-surface">molecular</strong>{" "}
            mutation chains where parent → child is a real edit.
          </p>
          <p>
            Instead, this view shows a{" "}
            <strong className="text-on-surface">contribution view</strong>:
            click a parent card below to see its SKILL.md side-by-side with
            the matching section in the composite. The composite's body is
            organized by dimension — the heex-routes parent contributes the
            <span className="font-mono">## HEEx + Verified Routes</span>{" "}
            section, the streams parent contributes the{" "}
            <span className="font-mono">## Streams + Collections</span>{" "}
            section, and so on. You can read both sides and see exactly
            what survived into the final skill.
          </p>
        </div>
      </div>

      {/* Composite summary card */}
      <div className="rounded-xl border-2 border-tertiary/60 bg-tertiary/5 p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-4">
          <div>
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-tertiary">
              Generation 1 · Composite · Assembled from {parents.length} parents
            </p>
            <p className="mt-2 font-display text-2xl tracking-tight">
              {compositeGenome?.frontmatter &&
              typeof compositeGenome.frontmatter === "object" &&
              "name" in compositeGenome.frontmatter
                ? String(
                    (compositeGenome.frontmatter as { name: string }).name,
                  )
                : composite.id}
            </p>
          </div>
          <p className="font-mono text-xs text-on-surface-dim">
            fitness <span className="text-tertiary">{composite.fitness.toFixed(3)}</span>
          </p>
        </div>
      </div>

      {/* Master-detail: left rail of parents + right panel with the
          contribution view (parent SKILL.md side-by-side with the matching
          composite section). The left rail sticks at the top of the viewport
          while you scroll through a long composite section on the right. */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
        {/* Left rail: parent list */}
        <aside className="rounded-xl border border-outline-variant bg-surface-container-lowest p-4 lg:sticky lg:top-[96px] lg:max-h-[calc(100vh-120px)] lg:self-start lg:overflow-y-auto">
          <p className="mb-3 font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Parents · Gen 0
          </p>
          <div className="space-y-1">
            {parents.map((p) => {
              const g = genomes.find((x) => x.id === p.id);
              const dim = g ? deriveDimensionSlug(g) : p.id;
              const isSelected = expandedId === p.id;
              const genomeForTier = genomes.find((x) => x.id === p.id);
              const isFoundation =
                genomeForTier?.traits?.includes("architectural-stance") ||
                dim === "architectural-stance";
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => setExpandedId(p.id)}
                  className={`flex w-full flex-col items-start rounded-lg border px-3 py-2 text-left transition-colors ${
                    isSelected
                      ? "border-tertiary/60 bg-tertiary/10"
                      : "border-outline-variant bg-surface-container-low hover:bg-surface-container-high"
                  }`}
                >
                  <div className="flex w-full items-center justify-between gap-2">
                    <span className="font-mono text-xs text-on-surface line-clamp-1">
                      {dim}
                    </span>
                    {isFoundation && (
                      <span className="rounded bg-tertiary/10 px-1.5 py-0.5 font-mono text-[0.5rem] uppercase tracking-wider text-tertiary">
                        FND
                      </span>
                    )}
                  </div>
                  <span className="mt-1 font-mono text-[0.625rem] text-on-surface-dim">
                    fitness {p.fitness.toFixed(3)}
                  </span>
                </button>
              );
            })}
          </div>
        </aside>

        {/* Right panel: contribution view or placeholder */}
        <div className="min-w-0">
          {expanded ? (
            <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
              <div className="flex items-baseline justify-between">
                <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                  Contribution view · {expandedDim}
                </p>
                <p className="font-mono text-[0.625rem] text-on-surface-dim">
                  fitness{" "}
                  <span className="text-tertiary">
                    {expanded.deterministic_scores?.l1?.toFixed(3) ?? "—"}
                  </span>
                </p>
              </div>
              <div className="mt-4 space-y-4">
                {/* Top: parent SKILL.md */}
                <div className="min-w-0 rounded-lg border border-outline-variant bg-surface-container-low p-4">
                  <p className="mb-3 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
                    Parent SKILL.md
                  </p>
                  <div className="bible-prose max-h-[560px] overflow-y-auto">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {stripFrontmatter(expanded.skill_md_content)}
                    </ReactMarkdown>
                  </div>
                </div>

                {/* Bottom: matching composite section */}
                <div className="min-w-0 rounded-lg border border-tertiary/30 bg-tertiary/5 p-4">
                  <p className="mb-3 font-mono text-[0.625rem] uppercase tracking-wider text-tertiary">
                    Composite section: ## {contributedSection?.slug ?? "(not matched)"}
                  </p>
                  <div className="bible-prose max-h-[560px] overflow-y-auto">
                    {contributedSection ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {contributedSection.body}
                      </ReactMarkdown>
                    ) : (
                      <p className="text-sm text-on-surface-dim">
                        No matching section found in the composite body for
                        this parent's dimension. The parent may have
                        contributed cross-cutting rules rather than a single
                        named section.
                      </p>
                    )}
                  </div>
                </div>
              </div>
              <p className="mt-4 text-xs text-on-surface-dim">
                Top: the parent variant's full SKILL.md. Bottom: the matching{" "}
                <code className="rounded bg-surface-container-high px-1">##</code>{" "}
                section from the composite where this parent's guidance was
                distilled. Sections may have been compressed, reworded, or
                merged during Engineer assembly.
              </p>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-outline-variant bg-surface-container-lowest p-12 text-center">
              <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                Contribution view
              </p>
              <p className="mt-2 text-sm text-on-surface-dim">
                Select a parent from the list on the left to see its
                SKILL.md alongside the matching section in the composite.
              </p>
            </div>
          )}
        </div>
      </div>

    </div>
  );
}
