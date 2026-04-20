// @vitest-environment jsdom
//
// Smoke test for PackageExplorer — renders with realistic fixture data,
// asserts the master-detail layout reaches the DOM (installable section,
// metadata section, download link). Detailed pure-logic assertions live
// in packageExplorer/buildFiles.test.ts.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RunReportChallenge, RunReportGenome } from "@/types";

import PackageExplorer from "./PackageExplorer";

const compositeGenome: RunReportGenome = {
  id: "composite_abc",
  generation: 1,
  skill_md_content: "---\nname: composite\n---\n# composite",
  frontmatter: { name: "composite", description: "x" },
  supporting_files: {
    "scripts/validate.sh": "#!/bin/bash\necho ok",
    "references/guide.md": "# guide",
  },
  traits: [],
  meta_strategy: "engineer_composite",
  parent_ids: [],
  mutations: [],
  mutation_rationale: "",
  maturity: "draft",
  pareto_objectives: {},
  deterministic_scores: {},
} as unknown as RunReportGenome;

const winner: RunReportGenome = {
  ...compositeGenome,
  id: "gen_seed_streams_winner",
  meta_strategy: "seed_pipeline_winner",
};

const challenge: RunReportChallenge = {
  id: "easy-01",
  prompt: "stub",
  difficulty: "easy",
  evaluation_criteria: {},
  verification_method: "judge_review",
  setup_files: {},
  gold_standard_hints: "",
} as unknown as RunReportChallenge;

describe("PackageExplorer", () => {
  it("renders the installable section, metadata section, and download link", () => {
    render(
      <PackageExplorer
        compositeSkillMd="---\nname: x\n---\n# x"
        genomes={[compositeGenome, winner]}
        challenges={[challenge]}
        learningLog={["[integration_report] clean merge"]}
        runId="run-smoke-1"
        familyLabel="Phoenix LiveView"
      />,
    );

    expect(screen.getByText(/Skill package · Pre-download view/)).toBeTruthy();
    // Installable section: SKILL.md + the two supporting files = 3
    expect(screen.getByText(/Installable · 3/)).toBeTruthy();
    // Metadata: PACKAGE.md + REPORT.md + 1 parent + 1 challenge = 4
    expect(screen.getByText(/Evolution metadata · 4/)).toBeTruthy();
    const download = screen.getByRole("link", { name: /Download \.zip/ });
    expect(download.getAttribute("href")).toBe("/api/runs/run-smoke-1/export?format=skill_dir");
    expect(screen.getByText(/Gold Standard Checklist/)).toBeTruthy();
  });
});
