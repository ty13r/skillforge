import { describe, expect, it } from "vitest";

import type { RunReportChallenge, RunReportGenome } from "@/types";

import { buildFiles } from "./buildFiles";

const genome = (over: Partial<RunReportGenome>): RunReportGenome =>
  ({
    id: "g1",
    generation: 0,
    skill_md_content: "# stub\n\n## Examples\n**Example 1**\n**Example 2**\n",
    frontmatter: {},
    supporting_files: {},
    traits: [],
    meta_strategy: "",
    parent_ids: [],
    mutations: [],
    mutation_rationale: "",
    maturity: "draft",
    pareto_objectives: {},
    deterministic_scores: {},
    ...over,
  }) as unknown as RunReportGenome;

const challenge = (id: string): RunReportChallenge =>
  ({
    id,
    prompt: "stub",
    difficulty: "easy",
    evaluation_criteria: {},
    verification_method: "judge_review",
    setup_files: {},
    gold_standard_hints: "",
  }) as unknown as RunReportChallenge;

describe("buildFiles", () => {
  it("puts SKILL.md first in installable and falls back to placeholder when null", () => {
    const { installable } = buildFiles({
      compositeSkillMd: null,
      genomes: [],
      challenges: [],
      learningLog: [],
      runId: "run-x",
      familyLabel: "Fam",
    });
    expect(installable[0].path).toBe("SKILL.md");
    expect(installable[0].content).toContain("not loaded");
  });

  it("adds composite's supporting_files to installable, grouped by directory", () => {
    const composite = genome({
      id: "c",
      meta_strategy: "engineer_composite",
      supporting_files: {
        "scripts/validate.sh": "#!/bin/bash\necho ok",
        "references/guide.md": "# guide",
        "scripts/main.py": "print(1)",
      },
    });
    const { installable } = buildFiles({
      compositeSkillMd: "---\nname: x\n---\n# x",
      genomes: [composite],
      challenges: [],
      learningLog: [],
      runId: "run-x",
      familyLabel: "Fam",
    });
    const paths = installable.map((f) => f.path);
    expect(paths[0]).toBe("SKILL.md");
    // Directories stay grouped (alphabetical by top-level dir, then by full path)
    expect(paths.slice(1)).toEqual([
      "references/guide.md",
      "scripts/main.py",
      "scripts/validate.sh",
    ]);
  });

  it("emits PACKAGE.md into metadata with the right counts", () => {
    const winner = genome({ id: "w1", meta_strategy: "seed_pipeline_winner" });
    const composite = genome({ id: "c", meta_strategy: "engineer_composite" });
    const { metadata } = buildFiles({
      compositeSkillMd: "# x",
      genomes: [winner, composite],
      challenges: [challenge("easy-01"), challenge("easy-02")],
      learningLog: [],
      runId: "run-x",
      familyLabel: "Phoenix LiveView",
    });
    const pkg = metadata.find((f) => f.path === "_meta/PACKAGE.md");
    expect(pkg).toBeDefined();
    expect(pkg!.content).toContain("Phoenix LiveView — Package Metadata");
    expect(pkg!.content).toContain("**1** winning variants");
    expect(pkg!.content).toContain("**2** L1 test challenges");
  });

  it("includes integration_report from learning_log when present", () => {
    const { metadata } = buildFiles({
      compositeSkillMd: null,
      genomes: [],
      challenges: [],
      learningLog: ["[integration_report] merged cleanly"],
      runId: "run-x",
      familyLabel: "Fam",
    });
    const report = metadata.find((f) => f.path === "_meta/REPORT.md");
    expect(report).toBeDefined();
    expect(report!.content).toBe("merged cleanly");
  });

  it("emits one _meta/parents/<dim>.md per winning variant", () => {
    const winners = [
      genome({ id: "gen_seed_streams_winner", meta_strategy: "seed_pipeline_winner" }),
      genome({ id: "gen_seed_routes_winner", meta_strategy: "seed_pipeline_winner" }),
    ];
    const { metadata } = buildFiles({
      compositeSkillMd: null,
      genomes: winners,
      challenges: [],
      learningLog: [],
      runId: "run-x",
      familyLabel: "Fam",
    });
    const parents = metadata.filter((f) => f.path.startsWith("_meta/parents/"));
    expect(parents.map((p) => p.path)).toEqual([
      "_meta/parents/streams.md",
      "_meta/parents/routes.md",
    ]);
  });
});
