# Skill Package Quality Checklist

## Frontmatter

- [ ] Name matches `^[a-z0-9]+(-[a-z0-9]+)*$` (lowercase, hyphens, no leading/trailing)
- [ ] Name matches the directory name exactly
- [ ] Name does not contain "anthropic" or "claude"
- [ ] Name is 1-64 characters
- [ ] Description is present and non-empty
- [ ] Description first 250 chars contain capability statement + trigger language
- [ ] Description has "Use when" trigger language with specific scenarios
- [ ] Description has "NOT for" exclusions listing what the skill should not handle
- [ ] Description has "even if" pushy language to prevent undertriggering
- [ ] Description total length is under 1024 characters
- [ ] allowed-tools lists only tools the skill actually uses

## Body Structure

- [ ] Total body is under 500 lines
- [ ] Has `## Quick Start` section (2-3 sentences)
- [ ] Has `## Workflow` section with numbered steps
- [ ] Has `## Examples` section with 2-3 diverse I/O pairs
- [ ] Has `## Gotchas` section with real failure modes
- [ ] Has `## Out of Scope` section with explicit exclusions
- [ ] Workflow steps use imperative voice ("Run", "Read", "Check")
- [ ] All `${CLAUDE_SKILL_DIR}/` paths reference files that exist
- [ ] No bare relative paths to scripts/ or references/
- [ ] Examples include: typical case, edge case, and near-miss
- [ ] Examples use conversational input tone (how a real user would ask)

## Scripts

### validate.sh
- [ ] Has shebang: `#!/usr/bin/env bash`
- [ ] Has `set -euo pipefail`
- [ ] Performs REAL validation (not a stub)
- [ ] Exits 0 on pass
- [ ] Exits non-zero on failure
- [ ] Prints specific error messages on failure
- [ ] Validates something domain-specific (syntax, format, constraints)
- [ ] Handles missing input gracefully (error message, not crash)

### main_helper.py
- [ ] Valid Python 3 syntax
- [ ] More than 10 lines of actual logic
- [ ] Does real deterministic work (not a placeholder)
- [ ] Outputs to stdout (JSON preferred for structured data)
- [ ] Has a `if __name__ == "__main__": main()` guard
- [ ] Handles errors with informative messages
- [ ] Uses no hardcoded paths (uses args or env vars)

## References

### guide.md
- [ ] Exists in references/ directory
- [ ] More than 50 lines of content
- [ ] Under 200 lines
- [ ] Contains domain-specific reference material (not generic filler)
- [ ] One level deep from SKILL.md (no nested references)
- [ ] Has table of contents if over 100 lines

### Domain-specific files (if applicable)
- [ ] Additional references are justified by domain complexity
- [ ] Templates in assets/ are realistic, not empty placeholders
- [ ] All files referenced in SKILL.md actually exist at the stated path

## Description Quality (Trigger Optimization)

- [ ] Would trigger on the 3 most common phrasings a user would use
- [ ] Would NOT trigger on adjacent-but-different requests
- [ ] Front-loads the most important keywords before the 250-char mark
- [ ] Uses domain-specific terminology (not just generic "helps with X")
- [ ] Exclusions name specific alternatives where possible

## Anti-Pattern Check

- [ ] Not a "Silent Skill" (description is specific enough to trigger)
- [ ] Not a "Noisy Skill" (has clear exclusions to prevent false triggers)
- [ ] Not a "Redundant Skill" (does something Claude cannot do well natively)
- [ ] Not a "Token Hog" (body is concise, detail is in references)
- [ ] Scripts do real work (not stubs)
- [ ] References are loaded conditionally (not all at once)
- [ ] Examples are diverse (not 3 variations of the same case)
