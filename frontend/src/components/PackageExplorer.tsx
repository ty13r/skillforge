import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { RunReportChallenge, RunReportGenome } from "@/types";

import CodeViewer from "./CodeViewer";
import FileTree from "./packageExplorer/FileTree";
import GoldStandardChecklist from "./packageExplorer/GoldStandardChecklist";
import { buildFiles } from "./packageExplorer/buildFiles";

interface PackageExplorerProps {
  compositeSkillMd: string | null;
  genomes: RunReportGenome[];
  challenges: RunReportChallenge[];
  learningLog: string[];
  runId: string;
  familyLabel: string;
}

/**
 * Package explorer — separates the real installable skill package from
 * evolution metadata so a user can see exactly what they'd download and
 * deploy vs. what's just archival context.
 *
 * Structure:
 *   - Installable section: SKILL.md + any real supporting files from the
 *     composite genome. This is what gets zipped by
 *     /api/runs/{id}/export?format=skill_dir and what Claude actually loads.
 *   - Metadata section: parents/, challenges/, PACKAGE.md, REPORT.md.
 *     Preserved for audit + browsing but NOT in the deployable zip.
 *   - Gold Standard Checklist: transparent comparison against the Skill
 *     Authoring Constraints in CLAUDE.md.
 *
 * File list building lives in packageExplorer/buildFiles.ts; the tree
 * widget is packageExplorer/FileTree; the checklist is its own component.
 * This file is the master-detail orchestrator.
 */
export default function PackageExplorer({
  compositeSkillMd,
  genomes,
  challenges,
  learningLog,
  runId,
  familyLabel,
}: PackageExplorerProps) {
  const { installable, metadata } = useMemo(
    () =>
      buildFiles({
        compositeSkillMd,
        genomes,
        challenges,
        learningLog,
        runId,
        familyLabel,
      }),
    [compositeSkillMd, genomes, challenges, learningLog, runId, familyLabel],
  );

  const allFiles = useMemo(() => [...installable, ...metadata], [installable, metadata]);

  // SKILL.md is the first installable file and the default selection.
  const [selectedPath, setSelectedPath] = useState<string>("SKILL.md");
  const selectedFile = allFiles.find((f) => f.path === selectedPath);

  const isMarkdown = selectedFile?.language === "markdown";
  const markdownBody = useMemo(() => {
    if (!selectedFile || !isMarkdown) return "";
    // Strip YAML frontmatter from the rendered view — the browser shows
    // the body only, since the frontmatter is already surfaced in the
    // header/badge row above.
    const m = selectedFile.content.match(/^---\s*\n[\s\S]*?\n---\s*\n([\s\S]*)$/);
    return m?.[1] ?? selectedFile.content;
  }, [selectedFile, isMarkdown]);

  return (
    <div className="space-y-6">
      <ExplorerHeader
        installableCount={installable.length}
        metadataCount={metadata.length}
        runId={runId}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
        <aside className="rounded-xl border border-outline-variant bg-surface-container-lowest p-4 lg:sticky lg:top-[96px] lg:max-h-[calc(100vh-120px)] lg:self-start lg:overflow-y-auto">
          <p className="mb-3 font-mono text-[0.6875rem] uppercase tracking-wider text-tertiary">
            Installable · {installable.length}
          </p>
          <FileTree
            files={installable}
            selectedPath={selectedPath}
            onSelect={setSelectedPath}
            defaultOpen
          />

          <p className="mb-2 mt-5 font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Evolution metadata · {metadata.length}
          </p>
          <p className="mb-3 text-[0.625rem] leading-tight text-on-surface-dim">
            Not loaded by Claude. Preserved for audit only.
          </p>
          <FileTree
            files={metadata}
            selectedPath={selectedPath}
            onSelect={setSelectedPath}
            stripPrefix="_meta/"
            defaultOpen={false}
          />
        </aside>

        <div className="min-w-0 rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
          {selectedFile ? (
            <FileViewer file={selectedFile} isMarkdown={isMarkdown} markdownBody={markdownBody} />
          ) : (
            <p className="text-sm text-on-surface-dim">Select a file.</p>
          )}
        </div>
      </div>

      <GoldStandardChecklist installable={installable} />
    </div>
  );
}

interface ExplorerHeaderProps {
  installableCount: number;
  metadataCount: number;
  runId: string;
}

function ExplorerHeader({ installableCount, metadataCount, runId }: ExplorerHeaderProps) {
  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Skill package · Pre-download view
          </p>
          <p className="mt-2 text-sm text-on-surface">
            <strong className="text-tertiary">
              {installableCount} installable {installableCount === 1 ? "file" : "files"}
            </strong>{" "}
            ship in the downloadable zip and are loaded by Claude at runtime. {metadataCount}{" "}
            additional metadata files are preserved for auditing the evolution process but are NOT
            part of the deployable package.
          </p>
        </div>
        <a
          href={`/api/runs/${runId}/export?format=skill_dir`}
          className="rounded bg-tertiary/20 px-4 py-2 font-mono text-[0.625rem] uppercase tracking-wider text-tertiary transition-colors hover:bg-tertiary/30"
        >
          ↓ Download .zip
        </a>
      </div>
    </div>
  );
}

interface FileViewerProps {
  file: { path: string; content: string; kind: "installable" | "metadata" };
  isMarkdown: boolean;
  markdownBody: string;
}

function FileViewer({ file, isMarkdown, markdownBody }: FileViewerProps) {
  return (
    <>
      <div className="mb-4 flex items-baseline justify-between">
        <p className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
          {file.path}
        </p>
        {file.kind === "installable" ? (
          <span className="rounded bg-tertiary/10 px-2 py-0.5 font-mono text-[0.5625rem] uppercase tracking-wider text-tertiary">
            Installable
          </span>
        ) : (
          <span className="rounded bg-surface-container-high px-2 py-0.5 font-mono text-[0.5625rem] uppercase tracking-wider text-on-surface-dim">
            Metadata
          </span>
        )}
      </div>
      <div className="max-h-[720px] overflow-y-auto">
        {isMarkdown ? (
          <div className="bible-prose">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdownBody}</ReactMarkdown>
          </div>
        ) : (
          <CodeViewer code={file.content} filePath={file.path} />
        )}
      </div>
    </>
  );
}
