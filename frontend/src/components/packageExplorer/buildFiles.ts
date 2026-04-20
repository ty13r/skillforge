/**
 * Pure function that synthesizes the virtual file list for a run's
 * package browser. Partitions into installable (ships in zip) vs.
 * metadata (audit-only, under _meta/).
 *
 * Extracted from the main component so the tree-shaping logic can be
 * tested in isolation and so the component file stays focused on
 * rendering.
 */
import type { RunReportChallenge, RunReportGenome } from "@/types";

import { buildPackageMd } from "./buildMeta";
import { deriveDimensionFromId, detectLanguage } from "./types";
import type { VirtualFile } from "./types";

export interface BuildFilesInput {
  compositeSkillMd: string | null;
  genomes: RunReportGenome[];
  challenges: RunReportChallenge[];
  learningLog: string[];
  runId: string;
  familyLabel: string;
}

export interface BuildFilesOutput {
  installable: VirtualFile[];
  metadata: VirtualFile[];
}

export function buildFiles({
  compositeSkillMd,
  genomes,
  challenges,
  learningLog,
  runId,
  familyLabel,
}: BuildFilesInput): BuildFilesOutput {
  const installable: VirtualFile[] = [];
  const metadata: VirtualFile[] = [];

  // 1. SKILL.md — the one real file that always ships.
  installable.push({
    path: "SKILL.md",
    content: compositeSkillMd ?? "# (composite SKILL.md not loaded)",
    language: "markdown",
    kind: "installable",
  });

  // 2. Real supporting_files from the composite genome. Sorted so
  //    directories group together visually.
  const composite = genomes.find((g) => g.meta_strategy === "engineer_composite");
  const supportingFiles = composite?.supporting_files ?? {};
  const sortedPaths = Object.keys(supportingFiles).sort((a, b) => {
    const dirA = a.split("/")[0];
    const dirB = b.split("/")[0];
    if (dirA !== dirB) return dirA.localeCompare(dirB);
    return a.localeCompare(b);
  });
  for (const path of sortedPaths) {
    installable.push({
      path,
      content: supportingFiles[path],
      language: detectLanguage(path),
      kind: "installable",
    });
  }

  // 3. PACKAGE.md — metadata, synthesized.
  const winnerGenomes = genomes.filter((g) => g.meta_strategy === "seed_pipeline_winner");
  metadata.push({
    path: "_meta/PACKAGE.md",
    content: buildPackageMd({
      runId,
      familyLabel,
      winnerCount: winnerGenomes.length,
      challengeCount: challenges.length,
      genomeCount: genomes.length,
      installableCount: installable.length,
    }),
    language: "markdown",
    kind: "metadata",
  });

  // 4. REPORT.md — integration report from learning_log (if present).
  const reportEntry = learningLog.find((e) => e.startsWith("[integration_report] "));
  if (reportEntry) {
    metadata.push({
      path: "_meta/REPORT.md",
      content: reportEntry.replace("[integration_report] ", ""),
      language: "markdown",
      kind: "metadata",
    });
  }

  // 5. parents/ — 12 winning variant SKILL.md files.
  for (const g of winnerGenomes) {
    const dim = deriveDimensionFromId(g.id);
    metadata.push({
      path: `_meta/parents/${dim}.md`,
      content: g.skill_md_content,
      language: "markdown",
      kind: "metadata",
    });
  }

  // 6. challenges/ — JSON specs for audit.
  for (const c of challenges) {
    metadata.push({
      path: `_meta/challenges/${c.id}.json`,
      content: JSON.stringify(c, null, 2),
      language: "code",
      kind: "metadata",
    });
  }

  return { installable, metadata };
}
