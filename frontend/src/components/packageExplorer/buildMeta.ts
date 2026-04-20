/**
 * Builds the synthesized PACKAGE.md metadata file that lives under _meta/.
 *
 * Extracted from the inline template in PackageExplorer so the main
 * component stays focused on master-detail rendering. Pure function —
 * deterministic output for a given input, no I/O, no side effects.
 */

export interface PackageMdInput {
  runId: string;
  familyLabel: string;
  winnerCount: number;
  challengeCount: number;
  genomeCount: number;
  installableCount: number;
}

export function buildPackageMd({
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
