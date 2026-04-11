import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import CodeViewer from "./CodeViewer";
import type { RunReportChallenge, RunReportGenome } from "../types";

interface PackageExplorerProps {
  compositeSkillMd: string | null;
  genomes: RunReportGenome[];
  challenges: RunReportChallenge[];
  learningLog: string[];
  runId: string;
  familyLabel: string;
}

type VirtualFile = {
  path: string;
  content: string;
  // "markdown" = render via ReactMarkdown. "code" = render via CodeViewer
  // which picks syntax based on file extension.
  language: "markdown" | "code";
  // "installable" = part of the downloadable .zip, loaded by Claude.
  // "metadata" = evolution artifact, NOT loaded at runtime, kept for audit.
  kind: "installable" | "metadata";
};

function detectLanguage(path: string): "markdown" | "code" {
  return path.endsWith(".md") ? "markdown" : "code";
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
 *     Authoring Constraints in CLAUDE.md. Shows which files are present
 *     and which would be produced by a richer evolution pipeline.
 *
 * The tree is rendered as a custom flat list grouped by section so we can
 * force SKILL.md at the very top without fighting the shared FileTree's
 * directories-first sort.
 */
export default function PackageExplorer({
  compositeSkillMd,
  genomes,
  challenges,
  learningLog,
  runId,
  familyLabel,
}: PackageExplorerProps) {
  const { installable, metadata } = useMemo(() => {
    const inst: VirtualFile[] = [];
    const meta: VirtualFile[] = [];

    // 1. SKILL.md — the one real file that always ships.
    inst.push({
      path: "SKILL.md",
      content: compositeSkillMd ?? "# (composite SKILL.md not loaded)",
      language: "markdown",
      kind: "installable",
    });

    // 2. Real supporting_files from the composite genome. These are the
    //    rich-package artifacts (scripts/*, references/*, test_fixtures/*,
    //    assets/*) produced by post-assembly enrichment OR by a production
    //    engine that natively generates rich directory packages. Sorted so
    //    directories group together visually.
    const composite = genomes.find(
      (g) => g.meta_strategy === "engineer_composite",
    );
    const supportingFiles = composite?.supporting_files ?? {};
    const sortedPaths = Object.keys(supportingFiles).sort((a, b) => {
      // Group by top-level directory, then alphabetical within.
      const dirA = a.split("/")[0];
      const dirB = b.split("/")[0];
      if (dirA !== dirB) return dirA.localeCompare(dirB);
      return a.localeCompare(b);
    });
    for (const path of sortedPaths) {
      inst.push({
        path,
        content: supportingFiles[path],
        language: detectLanguage(path),
        kind: "installable",
      });
    }

    // 3. PACKAGE.md — metadata, synthesized.
    const winnerGenomes = genomes.filter(
      (g) => g.meta_strategy === "seed_pipeline_winner",
    );
    meta.push({
      path: "_meta/PACKAGE.md",
      content: buildPackageMd({
        runId,
        familyLabel,
        winnerCount: winnerGenomes.length,
        challengeCount: challenges.length,
        genomeCount: genomes.length,
        installableCount: inst.length,
      }),
      language: "markdown",
      kind: "metadata",
    });

    // 4. REPORT.md — integration report from learning_log
    const reportEntry = learningLog.find((e) =>
      e.startsWith("[integration_report] "),
    );
    if (reportEntry) {
      meta.push({
        path: "_meta/REPORT.md",
        content: reportEntry.replace("[integration_report] ", ""),
        language: "markdown",
        kind: "metadata",
      });
    }

    // 5. parents/ — 12 winning variant SKILL.md files
    for (const g of winnerGenomes) {
      const dim = deriveDimensionFromId(g.id);
      meta.push({
        path: `_meta/parents/${dim}.md`,
        content: g.skill_md_content,
        language: "markdown",
        kind: "metadata",
      });
    }

    // 6. challenges/ — all 24 JSON specs
    for (const c of challenges) {
      meta.push({
        path: `_meta/challenges/${c.id}.json`,
        content: JSON.stringify(c, null, 2),
        language: "code",
        kind: "metadata",
      });
    }

    return { installable: inst, metadata: meta };
  }, [
    compositeSkillMd,
    genomes,
    challenges,
    learningLog,
    runId,
    familyLabel,
  ]);

  const allFiles = useMemo(
    () => [...installable, ...metadata],
    [installable, metadata],
  );

  // SKILL.md is the first installable file and the default selection.
  const [selectedPath, setSelectedPath] = useState<string>("SKILL.md");
  const selectedFile = allFiles.find((f) => f.path === selectedPath);

  // Gold Standard Checklist — compare against the CLAUDE.md Skill Authoring
  // Constraints. For each recommended file, is it present in the
  // installable set?
  const checklist = useMemo(() => {
    const present = new Set(installable.map((f) => f.path));
    return [
      {
        path: "SKILL.md",
        label: "SKILL.md with frontmatter + body",
        kind: "required",
        present: present.has("SKILL.md"),
      },
      {
        path: "scripts/validate.sh",
        label: "scripts/validate.sh (structural self-check)",
        kind: "recommended",
        present: present.has("scripts/validate.sh"),
      },
      {
        path: "scripts/main_helper.py",
        label: "scripts/main_helper.py (deterministic helper)",
        kind: "recommended",
        present: present.has("scripts/main_helper.py"),
      },
      {
        path: "references/guide.md",
        label: "references/guide.md (domain reference)",
        kind: "recommended",
        present: present.has("references/guide.md"),
      },
      {
        path: "test_fixtures/",
        label: "test_fixtures/ (sample input files)",
        kind: "optional",
        present: Array.from(present).some((p) =>
          p.startsWith("test_fixtures/"),
        ),
      },
      {
        path: "assets/",
        label: "assets/ (templates, configs)",
        kind: "optional",
        present: Array.from(present).some((p) => p.startsWith("assets/")),
      },
    ];
  }, [installable]);

  const isMarkdown = selectedFile?.language === "markdown";
  const bodyOnly = useMemo(() => {
    if (!selectedFile || !isMarkdown) return "";
    const m = selectedFile.content.match(
      /^---\s*\n[\s\S]*?\n---\s*\n([\s\S]*)$/,
    );
    return m?.[1] ?? selectedFile.content;
  }, [selectedFile, isMarkdown]);

  return (
    <div className="space-y-6">
      {/* Header with honest framing */}
      <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <div>
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
              Skill package · Pre-download view
            </p>
            <p className="mt-2 text-sm text-on-surface">
              <strong className="text-tertiary">
                {installable.length} installable{" "}
                {installable.length === 1 ? "file" : "files"}
              </strong>{" "}
              ship in the downloadable zip and are loaded by Claude at
              runtime. {metadata.length} additional metadata files are
              preserved for auditing the evolution process but are NOT part
              of the deployable package.
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

      {/* Master-detail: sectioned file list on left, viewer on right */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
        <aside className="rounded-xl border border-outline-variant bg-surface-container-lowest p-4 lg:sticky lg:top-[96px] lg:max-h-[calc(100vh-120px)] lg:self-start lg:overflow-y-auto">
          {/* Installable section — directories open by default so the user
              can see scripts/, references/, assets/, test_fixtures/ at a
              glance. SKILL.md + any other top-level files render first. */}
          <p className="mb-3 font-mono text-[0.6875rem] uppercase tracking-wider text-tertiary">
            Installable · {installable.length}
          </p>
          <FileTreeSection
            files={installable}
            selectedPath={selectedPath}
            onSelect={setSelectedPath}
            defaultOpen
          />

          {/* Metadata section — strips the _meta/ prefix and starts
              collapsed so it doesn't overwhelm the installable area. */}
          <p className="mb-2 mt-5 font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Evolution metadata · {metadata.length}
          </p>
          <p className="mb-3 text-[0.625rem] leading-tight text-on-surface-dim">
            Not loaded by Claude. Preserved for audit only.
          </p>
          <FileTreeSection
            files={metadata}
            selectedPath={selectedPath}
            onSelect={setSelectedPath}
            stripPrefix="_meta/"
            defaultOpen={false}
          />
        </aside>

        <div className="min-w-0 rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
          {selectedFile ? (
            <>
              <div className="mb-4 flex items-baseline justify-between">
                <p className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
                  {selectedFile.path}
                </p>
                {selectedFile.kind === "installable" ? (
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
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {bodyOnly}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <CodeViewer
                    code={selectedFile.content}
                    filePath={selectedFile.path}
                  />
                )}
              </div>
            </>
          ) : (
            <p className="text-sm text-on-surface-dim">Select a file.</p>
          )}
        </div>
      </div>

      {/* Gold Standard Checklist */}
      <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
        <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          Gold Standard Checklist
        </p>
        <p className="mt-2 text-sm text-on-surface-dim">
          What this package contains vs. the Skill Authoring Constraints in{" "}
          <code className="rounded bg-surface-container-high px-1">
            CLAUDE.md
          </code>
          .
        </p>
        <div className="mt-4 space-y-2">
          {checklist.map((item) => (
            <div
              key={item.path}
              className="flex items-start gap-3 rounded-lg bg-surface-container-low p-3"
            >
              <span
                className={`mt-0.5 font-mono text-sm ${
                  item.present ? "text-tertiary" : "text-on-surface-dim"
                }`}
              >
                {item.present ? "✓" : "○"}
              </span>
              <div className="flex-1 min-w-0">
                <p className="font-mono text-xs text-on-surface">
                  {item.label}
                </p>
                <p className="mt-0.5 font-mono text-[0.625rem] text-on-surface-dim">
                  {item.kind} ·{" "}
                  {item.present
                    ? "present in this package"
                    : "not generated by this run"}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

interface FileRowProps {
  file: VirtualFile;
  selected: boolean;
  onSelect: () => void;
  indent?: number;
}

function FileRow({ file, selected, onSelect, indent = 0 }: FileRowProps) {
  // Show only the basename in the list.
  const basename = file.path.split("/").pop() ?? file.path;
  const icon = basename.endsWith(".json") ? "{ }" : "📄";
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left font-mono text-[0.6875rem] transition-colors ${
        selected
          ? "bg-tertiary/10 text-tertiary"
          : "text-on-surface-dim hover:bg-surface-container-high hover:text-on-surface"
      }`}
      style={{ paddingLeft: `${8 + indent * 12}px` }}
      title={file.path}
    >
      <span className="w-4 shrink-0 text-center text-[0.625rem]">{icon}</span>
      <span className="truncate">{basename}</span>
    </button>
  );
}

interface FileTreeSectionProps {
  files: VirtualFile[];
  selectedPath: string;
  onSelect: (path: string) => void;
  stripPrefix?: string;
  defaultOpen?: boolean;
}

/**
 * Collapsible tree for a section of files. Groups files under their
 * top-level subdirectory so ``scripts/*`` and ``references/*`` render as
 * collapsible directory groups. Standalone top-level files render above
 * the directory groups.
 *
 * Props:
 *   - ``stripPrefix``: an optional path prefix to strip from each file
 *     (e.g. ``"_meta/"`` for the metadata section) before grouping.
 *   - ``defaultOpen``: whether directories start expanded (true) or
 *     collapsed (false).
 */
function FileTreeSection({
  files,
  selectedPath,
  onSelect,
  stripPrefix = "",
  defaultOpen = true,
}: FileTreeSectionProps) {
  const { topLevel, dirs, allDirNames } = useMemo(() => {
    const top: VirtualFile[] = [];
    const grouped = new Map<string, VirtualFile[]>();
    const dirNames: string[] = [];
    for (const f of files) {
      const rest = stripPrefix
        ? f.path.replace(new RegExp(`^${stripPrefix}`), "")
        : f.path;
      if (!rest.includes("/")) {
        top.push(f);
      } else {
        const dirName = rest.split("/")[0];
        if (!grouped.has(dirName)) {
          grouped.set(dirName, []);
          dirNames.push(dirName);
        }
        grouped.get(dirName)!.push(f);
      }
    }
    return { topLevel: top, dirs: grouped, allDirNames: dirNames };
  }, [files, stripPrefix]);

  const [openDirs, setOpenDirs] = useState<Set<string>>(() =>
    defaultOpen ? new Set(allDirNames) : new Set(),
  );

  const toggle = (dir: string) => {
    setOpenDirs((prev) => {
      const next = new Set(prev);
      if (next.has(dir)) next.delete(dir);
      else next.add(dir);
      return next;
    });
  };

  // The indent for nested items depends on whether we're stripping a prefix.
  // Files inside a stripped-prefix path look as if they live at the root so
  // directory rows get no extra indent.
  const indent = 0;

  return (
    <div className="space-y-0.5">
      {topLevel.map((f) => (
        <FileRow
          key={f.path}
          file={f}
          selected={selectedPath === f.path}
          onSelect={() => onSelect(f.path)}
          indent={indent}
        />
      ))}
      {Array.from(dirs.entries()).map(([dir, dirFiles]) => {
        const isOpen = openDirs.has(dir);
        return (
          <div key={dir}>
            <button
              type="button"
              onClick={() => toggle(dir)}
              className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left font-mono text-[0.6875rem] text-on-surface-dim transition-colors hover:text-on-surface"
              style={{ paddingLeft: `${8 + indent * 12}px` }}
            >
              <span className="w-4 text-center text-[0.625rem]">
                {isOpen ? "▾" : "▸"}
              </span>
              <span className="text-[0.625rem]">📁</span>
              <span>
                {dir}/ · {dirFiles.length}
              </span>
            </button>
            {isOpen &&
              dirFiles.map((f) => (
                <FileRow
                  key={f.path}
                  file={f}
                  selected={selectedPath === f.path}
                  onSelect={() => onSelect(f.path)}
                  indent={indent + 1}
                />
              ))}
          </div>
        );
      })}
    </div>
  );
}

function deriveDimensionFromId(id: string): string {
  let slug = id
    .replace(/^gen_seed_/, "")
    .replace(/_winner$/, "")
    .replace(/^elixir_phoenix_liveview_?/, "");
  slug = slug.replace(/_/g, "-");
  return slug || id;
}

interface PackageMdInput {
  runId: string;
  familyLabel: string;
  winnerCount: number;
  challengeCount: number;
  genomeCount: number;
  installableCount: number;
}

function buildPackageMd({
  runId,
  familyLabel,
  winnerCount,
  challengeCount,
  genomeCount,
  installableCount,
}: PackageMdInput): string {
  return `# ${familyLabel} — Package Metadata

**Run ID**: \`${runId}\`
**Evolution mode**: atomic
**Generation**: 1

## What's actually in the .zip

${installableCount} installable file${installableCount === 1 ? "" : "s"} (SKILL.md + scripts/, references/, test_fixtures/, assets/) ship in the downloadable package. Everything under
\`_meta/\` — including this file — is preserved for auditing the evolution
process but is NOT loaded by Claude at runtime.

| Location        | Role                                     |
|-----------------|------------------------------------------|
| \`SKILL.md\`      | The composite skill — deploy this |
| \`_meta/PACKAGE.md\` | This manifest (metadata only)      |
| \`_meta/REPORT.md\`  | Engineer integration report        |
| \`_meta/parents/*.md\`  | ${winnerCount} winning variant sources  |
| \`_meta/challenges/*.json\` | ${challengeCount} L1 test specs    |

## Totals

- **${genomeCount}** SkillGenomes (seeds + winners + composite)
- **${winnerCount}** winning variants merged into the composite
- **${challengeCount}** L1 test challenges sampled

## How to deploy

1. Extract the .zip into your project.
2. Place \`SKILL.md\` at \`.claude/skills/<your-skill-name>/SKILL.md\`.
3. Delete the \`_meta/\` directory if present — Claude ignores it, but
   removing it keeps your deployment clean.
4. Done. Claude Code will pick up the skill on next restart.

## What's NOT in this package

A richer skill would also include:

- \`scripts/validate.sh\` — structural self-check
- \`scripts/main_helper.py\` — deterministic helper (parser, formatter, generator)
- \`references/guide.md\` — domain reference doc Claude reads on demand
- \`test_fixtures/\` — sample inputs
- \`assets/\` — templates and static resources

The evolution pipeline that produced this skill only generated prose rules,
not helper scripts or reference files. A production pipeline could add a
\`.claude/skills/scripter/\` agent per dimension to produce those.

## Generation lineage

This is **Generation 1** — produced by evolving a pre-existing seed plus
spawned alternatives across 12 dimensions. A re-evolution would produce
Generation 2 with this composite as the seed input.

For full context on assembly decisions, see \`_meta/REPORT.md\`.
`;
}
