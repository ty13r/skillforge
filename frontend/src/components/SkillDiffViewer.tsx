import { useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { diffLines, type Change } from "diff";

interface SkillDetail {
  id: string;
  generation: number;
  skill_md_content: string;
  traits: string[];
  maturity: string;
  parent_ids: string[];
  mutations: string[];
  mutation_rationale: string;
  pareto_objectives: Record<string, number>;
}

interface LineageEdge {
  parent_id: string;
  child_id: string;
  mutation_type: string;
}

interface LineageNode {
  id: string;
  generation: number;
  fitness: number;
  maturity: string;
  traits: string[];
}

interface LineageResponse {
  nodes: LineageNode[];
  edges: LineageEdge[];
}

const MUTATION_COLOR: Record<string, string> = {
  elitism: "text-tertiary",
  crossover: "text-secondary",
  mutation: "text-primary",
  wildcard: "text-warning",
  unknown: "text-on-surface-dim",
};

export default function SkillDiffViewer() {
  const { runId } = useParams<{ runId: string }>();
  const [lineage, setLineage] = useState<LineageResponse | null>(null);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [parent, setParent] = useState<SkillDetail | null>(null);
  const [child, setChild] = useState<SkillDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    fetch(`/api/runs/${runId}/lineage`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<LineageResponse>;
      })
      .then((data) => {
        setLineage(data);
        const interesting = data.edges.findIndex(
          (e) => e.mutation_type !== "elitism" && e.parent_id,
        );
        setSelectedIdx(interesting >= 0 ? interesting : 0);
      })
      .catch((err) => setError(String(err)));
  }, [runId]);

  useEffect(() => {
    if (!runId || !lineage || selectedIdx == null) return;
    const edge = lineage.edges[selectedIdx];
    if (!edge) return;
    setLoading(true);
    setError(null);
    const fetchSkill = (id: string): Promise<SkillDetail | null> =>
      id
        ? fetch(`/api/runs/${runId}/skills/${id}`).then((r) => {
            if (!r.ok) throw new Error(`Skill ${id}: HTTP ${r.status}`);
            return r.json() as Promise<SkillDetail>;
          })
        : Promise.resolve(null);
    Promise.all([fetchSkill(edge.parent_id), fetchSkill(edge.child_id)])
      .then(([p, c]) => {
        setParent(p);
        setChild(c);
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [runId, lineage, selectedIdx]);

  const diffChunks: Change[] = useMemo(() => {
    if (!parent || !child) return [];
    return diffLines(parent.skill_md_content, child.skill_md_content);
  }, [parent, child]);

  const nodeById = (nodeId: string) =>
    lineage?.nodes.find((n) => n.id === nodeId);

  const currentEdge =
    lineage && selectedIdx != null ? lineage.edges[selectedIdx] : null;

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-10">
      <div className="flex items-end justify-between">
        <div>
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-tertiary">
            Protocol: Ancestry
          </p>
          <h1 className="mt-2 font-display text-4xl leading-[1.05] tracking-tight">
            Lineage <span className="text-secondary">Diff Viewer</span>
          </h1>
          <p className="mt-2 text-sm text-on-surface-dim">
            Run {runId?.slice(0, 12)} · pick a parent→child transition to see
            what changed.
          </p>
        </div>
        <Link
          to={`/runs/${runId}`}
          className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim hover:text-on-surface"
        >
          ← Back to Arena
        </Link>
      </div>

      {error && (
        <div className="mt-6 rounded-xl bg-error/10 p-4 text-sm text-error">
          {error}
        </div>
      )}

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[300px_1fr]">
        <aside className="rounded-xl bg-surface-container-low p-4">
          <p className="mb-3 px-2 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
            Transitions · {lineage?.edges.length ?? 0}
          </p>
          {lineage == null ? (
            <p className="text-sm text-on-surface-dim">Loading lineage…</p>
          ) : lineage.edges.length === 0 ? (
            <p className="text-sm text-on-surface-dim">
              No lineage edges yet — run at least 2 generations to see diffs.
            </p>
          ) : (
            <ul className="space-y-1">
              {lineage.edges.map((edge, i) => {
                const parentNode = nodeById(edge.parent_id);
                const childNode = nodeById(edge.child_id);
                const selected = i === selectedIdx;
                return (
                  <li key={i}>
                    <button
                      onClick={() => setSelectedIdx(i)}
                      className={`w-full rounded-lg px-3 py-2 text-left text-xs transition-colors ${
                        selected
                          ? "bg-secondary/15"
                          : "hover:bg-surface-container-high"
                      }`}
                    >
                      <div
                        className={`font-mono uppercase tracking-wider ${MUTATION_COLOR[edge.mutation_type] ?? MUTATION_COLOR.unknown}`}
                      >
                        {edge.mutation_type}
                      </div>
                      <div className="mt-1 text-on-surface">
                        G{parentNode?.generation ?? "?"}/
                        {edge.parent_id.slice(0, 6)} → G
                        {childNode?.generation ?? "?"}/
                        {edge.child_id.slice(0, 6)}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </aside>

        <main className="min-w-0 rounded-xl bg-surface-container-lowest p-6">
          {loading ? (
            <p className="text-on-surface-dim">Loading skills…</p>
          ) : !parent && !child ? (
            <p className="text-on-surface-dim">
              Pick a transition from the left to see the diff.
            </p>
          ) : (
            <>
              {child && (
                <div className="mb-6 border-b border-outline-variant pb-4">
                  <div className="flex items-center gap-2">
                    <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                      Mutation Rationale
                    </p>
                    {currentEdge && (
                      <span
                        className={`rounded-full bg-surface-container-high px-2 py-0.5 font-mono text-[0.625rem] uppercase tracking-wider ${
                          MUTATION_COLOR[currentEdge.mutation_type] ??
                          MUTATION_COLOR.unknown
                        }`}
                      >
                        {currentEdge.mutation_type}
                      </span>
                    )}
                  </div>
                  <p className="mt-2 text-sm text-on-surface">
                    {child.mutation_rationale || (
                      <span className="text-on-surface-dim">
                        (no rationale recorded)
                      </span>
                    )}
                  </p>
                  {child.mutations.length > 0 && (
                    <ul className="mt-3 flex flex-wrap gap-1">
                      {child.mutations.map((m, i) => (
                        <li
                          key={i}
                          className="rounded-full bg-primary/10 px-2 py-0.5 font-mono text-[0.625rem] text-primary"
                        >
                          {m}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              <div className="overflow-x-auto">
                <pre className="whitespace-pre-wrap font-mono text-[0.8125rem] leading-relaxed">
                  {diffChunks.length === 0 ? (
                    <span className="text-on-surface-dim">
                      No changes (identical content — likely an elitism edge).
                    </span>
                  ) : (
                    diffChunks.map((chunk, i) => {
                      let cls = "text-on-surface";
                      let prefix = "  ";
                      if (chunk.added) {
                        cls = "bg-tertiary/10 text-tertiary";
                        prefix = "+ ";
                      } else if (chunk.removed) {
                        cls = "bg-error/10 text-error line-through";
                        prefix = "- ";
                      }
                      const lines = chunk.value.split("\n");
                      return (
                        <span key={i} className={cls}>
                          {lines
                            .map((line, j) =>
                              j < lines.length - 1 || line
                                ? prefix + line + "\n"
                                : "",
                            )
                            .join("")}
                        </span>
                      );
                    })
                  )}
                </pre>
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
