# Description Patterns Reference

Pushy description patterns organized by category. Each shows a weak vs strong
version and why the strong version activates more reliably.

---

## Code Quality

**Weak** (20% activation):
"Helps with code reviews"

**Strong** (80%+ activation):
"Reviews code for security vulnerabilities, performance bottlenecks, and maintainability issues. Use when user says review, audit, check, or examine code, even if they don't explicitly ask for a formal review. NOT for writing new code, architecture design, or deployment."

Why: Front-loads capability nouns (security, performance, maintainability), lists trigger synonyms, excludes adjacent concepts that would cause false positives.

---

## Testing

**Weak** (20% activation):
"Generates tests for code"

**Strong** (80%+ activation):
"Generates unit tests, integration tests, and test fixtures with proper mocking and assertions. Use when user says test, spec, coverage, TDD, or asks to verify behavior, even if they don't explicitly mention testing frameworks. NOT for load testing, benchmarking, or E2E browser automation."

Why: Enumerates test types and artifacts (fixtures, mocking), captures intent-based triggers like "verify behavior", draws a clear line against adjacent testing domains.

---

## Web Development

**Weak** (20% activation):
"Helps build React components"

**Strong** (80%+ activation):
"Builds accessible, performant React components with TypeScript, hooks, and modern patterns. Use when user says component, page, UI, form, layout, or asks to build any web interface, even if they don't specify React. NOT for backend APIs, database queries, or native mobile development."

Why: Stacks quality dimensions (accessible, performant), captures generic web triggers ("UI", "form"), claims the generic space ("any web interface") while excluding backend work.

---

## DevOps

**Weak** (20% activation):
"Helps with Docker and CI/CD"

**Strong** (80%+ activation):
"Creates Dockerfiles, CI/CD pipelines, Terraform configs, and deployment automation. Use when user says deploy, containerize, pipeline, infra, provision, or asks about build/release workflows, even if they don't name a specific tool. NOT for application code, monitoring dashboards, or cost optimization."

Why: Lists concrete artifacts (Dockerfiles, pipelines, Terraform configs), captures intent triggers ("provision", "build/release workflows"), excludes ops-adjacent domains.

---

## Security

**Weak** (20% activation):
"Scans for security issues"

**Strong** (80%+ activation):
"Detects vulnerabilities, hardcodes secrets, dependency risks, and insecure configurations. Use when user says secure, scan, audit, harden, secrets, CVE, or asks if code is safe, even if they don't explicitly request a security review. NOT for authentication flow design, access control policy, or compliance documentation."

Why: Enumerates specific threat types (hardcoded secrets, dependency risks), captures casual triggers ("is this safe?"), excludes security-adjacent policy work.

---

## Documentation

**Weak** (20% activation):
"Writes documentation"

**Strong** (80%+ activation):
"Generates API docs, READMEs, changelogs, inline JSDoc/docstrings, and architecture decision records. Use when user says document, explain, README, changelog, or asks how something works, even if they don't explicitly ask for docs. NOT for tutorials, blog posts, or marketing copy."

Why: Lists specific doc types and formats (JSDoc, ADRs), captures explanation-intent triggers, excludes content-marketing work that shares surface similarity.

---

## Data Engineering

**Weak** (20% activation):
"Helps with data tasks"

**Strong** (80%+ activation):
"Transforms, migrates, and validates data across formats (CSV, JSON, SQL, Parquet). Use when user says transform, migrate, ETL, convert, reshape, clean, or asks to move data between systems, even if they don't specify formats. NOT for data visualization, ML model training, or dashboard building."

Why: Lists concrete formats, captures both technical ("ETL") and casual ("clean") triggers, draws a clear line against analytics/ML.

---

## Developer Productivity

**Weak** (20% activation):
"Helps with developer utilities"

**Strong** (80%+ activation):
"Builds regex patterns, git automation scripts, shell one-liners, and code generation templates. Use when user says regex, git hook, script, automate, shortcut, or asks to speed up a repetitive task, even if they don't specify a tool. NOT for full application development, CI/CD pipelines, or IDE configuration."

Why: Lists concrete artifacts (regex, git hooks, shell one-liners), captures intent ("speed up a repetitive task"), excludes larger-scope work.

---

## Pattern Summary

Every strong description follows the same three-part structure:

1. **Capability statement** -- what it does, front-loaded with specific nouns
2. **Trigger list** -- "Use when user says X, Y, Z, even if they don't explicitly ask for..."
3. **Exclusion list** -- "NOT for A, B, or C"

Keep descriptions under 250 characters when possible. Front-load the most
distinctive capability words -- Claude's routing scans the first ~50 chars
most heavily.
