import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import CodeViewer from "./CodeViewer";
import FileTree from "./FileTree";

interface SkillDetail {
  id: string;
  generation: number;
  skill_md_content: string;
  supporting_files?: Record<string, string>;
  traits: string[];
  maturity: string;
  parent_ids: string[];
  mutations: string[];
  mutation_rationale: string;
  pareto_objectives: Record<string, number>;
}

export default function SeedDetailView() {
  const { runId, skillId } = useParams<{ runId: string; skillId: string }>();
  const [skill, setSkill] = useState<SkillDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<string>("SKILL.md");

  useEffect(() => {
    if (!runId || !skillId) return;
    fetch(`/api/runs/${runId}/skills/${skillId}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<SkillDetail>;
      })
      .then(setSkill)
      .catch((err) => setError(String(err)));
  }, [runId, skillId]);

  const files = useMemo(() => {
    if (!skill) return [];
    const list = [{ path: "SKILL.md", content: skill.skill_md_content || "" }];
    if (skill.supporting_files) {
      for (const [path, content] of Object.entries(skill.supporting_files)) {
        list.push({ path, content: content as string });
      }
    }
    return list;
  }, [skill]);

  const selectedContent = useMemo(() => {
    return files.find((f) => f.path === selectedFile)?.content ?? "";
  }, [files, selectedFile]);

  if (error) {
    return (
      <div className="mx-auto max-w-[1400px] px-6 py-10">
        <div className="rounded-xl bg-error/10 p-4 text-sm text-error">{error}</div>
      </div>
    );
  }

  if (!skill) {
    return (
      <div className="mx-auto max-w-[1400px] px-6 py-10">
        <p className="text-on-surface-dim">Loading skill...</p>
      </div>
    );
  }

  // Strip YAML frontmatter for the main markdown render
  const bodyOnly = skill.skill_md_content.replace(/^---\n[\s\S]*?\n---\n?/, "");

  // Extract frontmatter values for the sidebar
  const frontmatterMatch = skill.skill_md_content.match(/^---\n([\s\S]*?)\n---/);
  const frontmatter = frontmatterMatch ? frontmatterMatch[1] : "";
  const nameMatch = frontmatter.match(/^name:\s*(.+)$/m);
  const descMatch = frontmatter.match(/description:\s*>-\n((?:\s+.*\n?)+)/);

  const hasMultipleFiles = files.length > 1;

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-10">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <Link
            to="/registry"
            className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim hover:text-on-surface"
          >
            &larr; Registry
          </Link>
          <div className="mt-2 flex items-baseline gap-3">
            <h1 className="font-display text-4xl leading-[1.05] tracking-tight">
              {nameMatch?.[1] ?? skill.id}
            </h1>
            <span className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
              {files.length} {files.length === 1 ? "FILE" : "FILES"}
            </span>
          </div>
          <p className="mt-2 max-w-3xl text-sm text-on-surface-dim">
            {descMatch?.[1].trim().replace(/\s+/g, " ") ?? ""}
          </p>
        </div>
        <Link
          to={`/new?seed=${skill.id}`}
          className="rounded-xl bg-primary px-5 py-2.5 text-sm font-medium text-surface-container-lowest transition-colors hover:bg-primary/90"
        >
          &#9794; Fork &amp; Evolve
        </Link>
      </div>

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[1fr_280px]">
        {/* Main content area with optional file tree */}
        <article className="min-w-0 rounded-xl border border-outline-variant bg-surface-container-lowest p-8">
          <div className={hasMultipleFiles ? "flex gap-4" : ""}>
            {/* File tree sidebar (only when there are supporting files) */}
            {hasMultipleFiles && (
              <div className="w-52 shrink-0 border-r border-outline-variant pr-4">
                <p className="mb-3 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
                  Skill Package
                </p>
                <FileTree
                  files={files.map((f) => f.path)}
                  selected={selectedFile}
                  onSelect={setSelectedFile}
                />
              </div>
            )}

            {/* Content viewer */}
            <div className="min-w-0 flex-1">
              {hasMultipleFiles && (
                <p className="mb-3 font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
                  {selectedFile}
                </p>
              )}

              {selectedFile === "SKILL.md" ? (
                <div className="bible-prose">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{bodyOnly}</ReactMarkdown>
                </div>
              ) : selectedFile.endsWith(".md") ? (
                <div className="bible-prose">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{selectedContent}</ReactMarkdown>
                </div>
              ) : (
                <CodeViewer code={selectedContent} filePath={selectedFile} />
              )}
            </div>
          </div>
        </article>

        {/* Sidebar */}
        <aside className="space-y-4">
          <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5">
            <p className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
              Maturity
            </p>
            <p className="mt-1 font-display text-lg tracking-tight text-tertiary">
              {skill.maturity}
            </p>
          </div>

          {skill.traits.length > 0 && (
            <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5">
              <p className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
                Traits
              </p>
              <ul className="mt-2 flex flex-wrap gap-1">
                {skill.traits.map((t) => (
                  <li
                    key={t}
                    className="rounded-full bg-primary/10 px-2 py-0.5 font-mono text-[0.625rem] text-primary"
                  >
                    {t}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5">
            <p className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
              Export
            </p>
            <div className="mt-3 space-y-2">
              <a
                href={`/api/runs/${runId}/export?format=skill_dir`}
                className="bg-surface-container-mid block rounded-lg px-3 py-2 text-center text-xs text-on-surface transition-colors hover:bg-surface-container-high"
              >
                &darr; Download .zip
              </a>
              <a
                href={`/api/runs/${runId}/export?format=skill_md`}
                target="_blank"
                rel="noreferrer"
                className="bg-surface-container-mid block rounded-lg px-3 py-2 text-center text-xs text-on-surface transition-colors hover:bg-surface-container-high"
              >
                &darr; Download SKILL.md
              </a>
              <a
                href={`/api/runs/${runId}/export?format=agent_sdk_config`}
                target="_blank"
                rel="noreferrer"
                className="bg-surface-container-mid block rounded-lg px-3 py-2 text-center text-xs text-on-surface transition-colors hover:bg-surface-container-high"
              >
                &darr; Agent SDK Config
              </a>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
