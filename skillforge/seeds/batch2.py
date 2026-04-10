"""Batch 2 Gen 0 Skill library — full packages with scripts + references.

Domains 6-10 from the seed research report:
  6. dockerfile-optimizer (DevOps, Medium)
  7. ci-cd-pipeline (DevOps, Hard)
  8. dependency-auditor (Security, Easy)
  9. secret-scanner (Security, Easy)
 10. api-doc-generator (Documentation, Easy)

Each seed ships with functional scripts/ and references/ as supporting_files,
following the golden template structure exactly.
"""
from __future__ import annotations

from skillforge.seeds import _build

# ---------------------------------------------------------------------------
# 6. Dockerfile Optimizer
# ---------------------------------------------------------------------------
_DOCKERFILE_OPT_BODY = """\
## Quick Start
Analyze an existing Dockerfile for anti-patterns (root user, unpinned tags, poor layer ordering, missing HEALTHCHECK), score it 0-100, and emit a rewritten version that fixes every finding. Run the validation script to confirm the rewrite is clean.

## When to use this skill
Use when the user says "optimize Dockerfile", "reduce image size", "Dockerfile best practices", "Dockerfile security", "lint Dockerfile", "hadolint", or pastes a Dockerfile and asks "what's wrong with this". Also triggers on "my image is too big" or "container runs as root". Even if they don't explicitly ask for optimization.
NOT for writing Dockerfiles from scratch, docker-compose orchestration, or Kubernetes manifests.

## Workflow

### Step 1: Parse and profile the Dockerfile
Read the Dockerfile. Run `python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py --analyze <path>` to get a JSON report of anti-patterns, layer count, and optimization opportunities.

### Step 2: Consult the reference guide
For each detected anti-pattern, read `${CLAUDE_SKILL_DIR}/references/guide.md` for the recommended fix pattern. Pay special attention to multi-stage build conversion and layer ordering.

### Step 3: Rewrite the Dockerfile
Apply fixes in priority order:
1. Pin base image tags (never `:latest`)
2. Add non-root USER as the final instruction
3. Reorder COPY to put dependency manifests before source
4. Merge consecutive RUN layers with `&&`
5. Add `--no-install-recommends` and cleanup to apt-get
6. Add HEALTHCHECK instruction
7. Convert to multi-stage if build tools are in the final image

### Step 4: Validate the rewrite
Run `bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh <rewritten-dockerfile>`.
If validation fails, fix the flagged issues and re-validate before presenting to the user.

## Examples

**Example 1: Python app with anti-patterns**
Input: "optimize this Dockerfile:
FROM python:latest
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
EXPOSE 8000
CMD python app.py"
Output: Rewrites as two-stage build with `python:3.12-slim-bookworm`, copies `requirements.txt` first, installs deps in builder, copies only `.venv` to runtime, adds non-root user, HEALTHCHECK on port 8000. Score improves from 15 to 92.

**Example 2: Node.js image that's too large**
Input: "my Docker image is 1.8GB, can you trim it?"
Output: Identifies `FROM node:20` (full Debian), `COPY . .` before `npm install`, dev dependencies in production. Rewrites with `node:20-alpine`, multi-stage build, copies only `node_modules` production deps and built assets. Image drops to ~180MB.

**Example 3: Security hardening request**
Input: "make this Dockerfile more secure"
Output: Adds `USER nonroot`, removes `ENV SECRET_KEY=...` (moves to runtime), pins base to digest, adds `--no-new-privileges` security opt, removes unnecessary SHELL instructions, adds `.dockerignore` recommendation.

## Common mistakes to avoid
- Merging ALL RUN instructions into one layer — only merge related commands
- Using alpine for Python apps with C extensions (musl vs glibc issues)
- Adding HEALTHCHECK that depends on tools not in the image (curl not in distroless)
- Forgetting to copy the dependency lockfile alongside the manifest
"""

_DOCKERFILE_OPT_VALIDATE = """\
#!/usr/bin/env bash
set -euo pipefail
# validate.sh — Check a Dockerfile for common anti-patterns.
# Usage: bash validate.sh <path-to-Dockerfile>
# Exit 0 = clean, exit 1 = violations found.

DOCKERFILE="${1:?Usage: validate.sh <Dockerfile-path>}"
ERRORS=0

if [[ ! -f "$DOCKERFILE" ]]; then
  echo "ERROR: File not found: $DOCKERFILE"
  exit 1
fi

# 1. No :latest tags on FROM
if grep -qE '^FROM\\s+\\S+:latest' "$DOCKERFILE"; then
  echo "VIOLATION: Base image uses ':latest' tag — pin to a specific version."
  ERRORS=$((ERRORS + 1))
fi

# 2. FROM without a tag at all (implies :latest)
while IFS= read -r line; do
  image="${line#FROM }"
  image="${image%% *}"  # strip AS alias
  if [[ "$image" != "scratch" && "$image" != *:* && "$image" != *@* ]]; then
    echo "VIOLATION: FROM $image has no tag — pin to a specific version."
    ERRORS=$((ERRORS + 1))
  fi
done < <(grep -E '^FROM ' "$DOCKERFILE")

# 3. Must have a non-root USER instruction
if ! grep -qE '^USER\\s+' "$DOCKERFILE"; then
  echo "VIOLATION: No USER instruction — container runs as root."
  ERRORS=$((ERRORS + 1))
else
  LAST_USER=$(grep -E '^USER\\s+' "$DOCKERFILE" | tail -1 | awk '{print $2}')
  if [[ "$LAST_USER" == "root" || "$LAST_USER" == "0" ]]; then
    echo "VIOLATION: Final USER is root — use a non-root user."
    ERRORS=$((ERRORS + 1))
  fi
fi

# 4. HEALTHCHECK present
if ! grep -qE '^HEALTHCHECK' "$DOCKERFILE"; then
  echo "WARNING: No HEALTHCHECK instruction."
  ERRORS=$((ERRORS + 1))
fi

# 5. No secrets in ENV or ARG
if grep -qiE '^(ENV|ARG)\\s+(PASSWORD|SECRET|API_KEY|TOKEN|PRIVATE_KEY)\\s*=' "$DOCKERFILE"; then
  echo "VIOLATION: Secrets exposed via ENV/ARG — use runtime env or build secrets."
  ERRORS=$((ERRORS + 1))
fi

# 6. apt-get without --no-install-recommends
if grep -qE 'apt-get install' "$DOCKERFILE" && ! grep -qE 'apt-get install.*--no-install-recommends' "$DOCKERFILE"; then
  echo "WARNING: apt-get install without --no-install-recommends — bloats image."
  ERRORS=$((ERRORS + 1))
fi

# 7. apt-get without cleanup in same layer
if grep -qE 'apt-get install' "$DOCKERFILE"; then
  if ! grep -qE 'rm -rf /var/lib/apt/lists' "$DOCKERFILE"; then
    echo "WARNING: apt-get without 'rm -rf /var/lib/apt/lists/*' cleanup."
    ERRORS=$((ERRORS + 1))
  fi
fi

if [[ $ERRORS -gt 0 ]]; then
  echo "---"
  echo "Found $ERRORS violation(s)."
  exit 1
else
  echo "Dockerfile passes all checks."
  exit 0
fi
"""

_DOCKERFILE_OPT_HELPER = '''\
#!/usr/bin/env python3
"""Dockerfile anti-pattern analyzer.

Usage: python main_helper.py --analyze <Dockerfile-path>
       python main_helper.py --score <Dockerfile-path>

Outputs JSON with detected anti-patterns, optimization suggestions, and a score.
"""
import argparse
import json
import re
import sys
from pathlib import Path


def parse_dockerfile(text: str) -> list[dict]:
    """Parse Dockerfile into a list of instruction dicts."""
    instructions: list[dict] = []
    current_line = ""
    line_start = 0
    for i, raw_line in enumerate(text.splitlines(), 1):
        stripped = raw_line.strip()
        if stripped.endswith("\\\\"):
            if not current_line:
                line_start = i
            current_line += stripped[:-1] + " "
            continue
        current_line += stripped
        if not current_line or current_line.startswith("#"):
            current_line = ""
            continue
        parts = current_line.split(None, 1)
        instructions.append({
            "line": line_start or i,
            "instruction": parts[0].upper(),
            "args": parts[1] if len(parts) > 1 else "",
        })
        current_line = ""
        line_start = 0
    return instructions


def analyze(path: str) -> dict:
    """Analyze a Dockerfile and return a JSON-serializable report."""
    text = Path(path).read_text()
    instructions = parse_dockerfile(text)
    anti_patterns: list[dict] = []
    optimizations: list[dict] = []

    from_instructions = [i for i in instructions if i["instruction"] == "FROM"]
    run_instructions = [i for i in instructions if i["instruction"] == "RUN"]
    copy_instructions = [i for i in instructions if i["instruction"] == "COPY"]

    # Check for :latest or untagged base images
    for inst in from_instructions:
        image = inst["args"].split(" ")[0].split(" as ")[0].strip()
        if image == "scratch":
            continue
        if ":latest" in image:
            anti_patterns.append({
                "line": inst["line"],
                "issue": "Base image uses :latest tag",
                "fix": f"Pin to a specific version, e.g. {image.replace(':latest', ':3.12-slim')}",
            })
        elif ":" not in image and "@" not in image:
            anti_patterns.append({
                "line": inst["line"],
                "issue": f"Base image '{image}' has no tag (implies :latest)",
                "fix": f"Pin to a specific version, e.g. {image}:<version>-slim",
            })

    # Check for root user
    user_instructions = [i for i in instructions if i["instruction"] == "USER"]
    if not user_instructions:
        anti_patterns.append({
            "line": 0,
            "issue": "No USER instruction — container runs as root",
            "fix": "Add 'RUN useradd -r app && USER app' before CMD/ENTRYPOINT",
        })
    elif user_instructions[-1]["args"].strip() in ("root", "0"):
        anti_patterns.append({
            "line": user_instructions[-1]["line"],
            "issue": "Final USER is root",
            "fix": "Switch to a non-root user for the runtime stage",
        })

    # Check for HEALTHCHECK
    if not any(i["instruction"] == "HEALTHCHECK" for i in instructions):
        anti_patterns.append({
            "line": 0,
            "issue": "No HEALTHCHECK instruction",
            "fix": "Add HEALTHCHECK --interval=30s CMD curl -f http://localhost:<port>/health || exit 1",
        })

    # Check for secrets in ENV/ARG
    secret_re = re.compile(r"(PASSWORD|SECRET|API_KEY|TOKEN|PRIVATE_KEY)\\s*=", re.IGNORECASE)
    for inst in instructions:
        if inst["instruction"] in ("ENV", "ARG") and secret_re.search(inst["args"]):
            anti_patterns.append({
                "line": inst["line"],
                "issue": f"Secret exposed via {inst['instruction']}",
                "fix": "Use --mount=type=secret or runtime environment variables",
            })

    # Check for COPY . . before dependency install
    for idx, inst in enumerate(instructions):
        if inst["instruction"] == "COPY" and ". ." in inst["args"].replace("./", "."):
            later_runs = [r for r in run_instructions if r["line"] > inst["line"]]
            for r in later_runs:
                if any(kw in r["args"] for kw in ("pip install", "npm install", "npm ci", "yarn", "go mod")):
                    anti_patterns.append({
                        "line": inst["line"],
                        "issue": "COPY . . before dependency install — breaks layer cache",
                        "fix": "Copy dependency manifest first, install deps, then copy source",
                    })
                    break

    # Check multi-stage
    if len(from_instructions) < 2 and len(run_instructions) > 2:
        optimizations.append({
            "description": "Convert to multi-stage build to separate build tools from runtime",
            "estimated_savings": "30-80% image size reduction",
        })

    # Check for consecutive RUN layers that could be merged
    prev_was_run = False
    consecutive_runs = 0
    for inst in instructions:
        if inst["instruction"] == "RUN":
            if prev_was_run:
                consecutive_runs += 1
            prev_was_run = True
        else:
            prev_was_run = False
    if consecutive_runs > 1:
        optimizations.append({
            "description": f"Merge {consecutive_runs + 1} consecutive RUN layers to reduce layer count",
            "estimated_savings": f"{consecutive_runs} fewer layers",
        })

    # Check apt-get hygiene
    for inst in run_instructions:
        if "apt-get install" in inst["args"]:
            if "--no-install-recommends" not in inst["args"]:
                anti_patterns.append({
                    "line": inst["line"],
                    "issue": "apt-get install without --no-install-recommends",
                    "fix": "Add --no-install-recommends and rm -rf /var/lib/apt/lists/*",
                })

    # Score: start at 100, deduct per issue
    score = max(0, 100 - len(anti_patterns) * 15 - len(optimizations) * 5)

    return {
        "anti_patterns": anti_patterns,
        "optimizations": optimizations,
        "layer_count": len(instructions),
        "from_count": len(from_instructions),
        "is_multi_stage": len(from_instructions) >= 2,
        "score": score,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Dockerfile anti-pattern analyzer")
    parser.add_argument("--analyze", metavar="PATH", help="Analyze a Dockerfile")
    parser.add_argument("--score", metavar="PATH", help="Score a Dockerfile (0-100)")
    args = parser.parse_args()

    path = args.analyze or args.score
    if not path:
        parser.print_help()
        sys.exit(1)

    result = analyze(path)
    if args.score:
        print(result["score"])
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
'''

_DOCKERFILE_OPT_GUIDE = """\
# Dockerfile Optimization Guide

## Base Image Selection

| Use Case | Recommended Base | Size |
|----------|-----------------|------|
| Python | `python:3.12-slim-bookworm` | ~150MB |
| Node.js | `node:20-alpine` | ~130MB |
| Go | `golang:1.22-alpine` (build), `gcr.io/distroless/static` (run) | ~2MB final |
| Rust | `rust:1.77-slim` (build), `debian:bookworm-slim` (run) | ~80MB final |
| Java | `eclipse-temurin:21-jre-alpine` | ~170MB |
| Static files | `nginx:alpine` or `caddy:alpine` | ~40MB |
| Minimal | `scratch` (Go/Rust static binaries only) | 0MB |

## Multi-Stage Build Pattern

```dockerfile
# Stage 1: Build
FROM python:3.12-slim-bookworm AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev
COPY . .

# Stage 2: Runtime
FROM python:3.12-slim-bookworm
WORKDIR /app
RUN useradd --create-home --shell /bin/bash app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
USER app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD curl -fsS http://localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Layer Ordering (Cache Efficiency)

Order from least-frequently-changed to most-frequently-changed:
1. Base image and system packages (changes: quarterly)
2. Dependency manifests + install (changes: weekly)
3. Source code copy (changes: every commit)
4. Build step (changes: every commit)

## Security Hardening Checklist

- [ ] Non-root USER as final instruction
- [ ] Base image pinned to specific tag or digest
- [ ] No secrets in ENV, ARG, or COPY
- [ ] `--no-new-privileges` in docker run or compose security_opt
- [ ] Read-only root filesystem where possible
- [ ] No unnecessary packages (--no-install-recommends)
- [ ] Apt cache cleaned in same layer as install
- [ ] .dockerignore blocks .git, .env, node_modules, __pycache__

## Anti-Pattern Quick Reference

| Anti-Pattern | Impact | Fix |
|-------------|--------|-----|
| `:latest` tag | Non-reproducible builds | Pin version + digest |
| `COPY . .` before deps | Cache invalidation every commit | Copy manifest first |
| Running as root | Container escape = host compromise | `USER nonroot` |
| Secrets in ENV/ARG | Visible in image history | Build secrets or runtime env |
| No HEALTHCHECK | Orchestrator can't detect failures | Add health endpoint check |
| No .dockerignore | Bloated context, leaked secrets | Always create one |
| Full base image | 500MB+ unnecessary packages | Use -slim or -alpine |
| Separate RUN layers for related ops | Excess layers | Merge with && |
"""

# ---------------------------------------------------------------------------
# 7. CI/CD Pipeline Generator
# ---------------------------------------------------------------------------
_CICD_BODY = """\
## Quick Start
Detect the project type from manifest files, generate a complete GitHub Actions workflow with pinned actions, least-privilege permissions, and caching. Validate the YAML before presenting it.

## When to use this skill
Use when the user says "CI/CD", "GitHub Actions", "pipeline", "workflow", "continuous integration", "deploy automation", ".github/workflows", or "set up CI". Also triggers on "run tests on push" or "automate my builds", even if they don't explicitly mention GitHub Actions.
NOT for Jenkins, Bamboo, or infrastructure provisioning. NOT for GitLab CI or CircleCI (mention this if asked).

## Workflow

### Step 1: Detect project type
Scan the repository for manifest files:
- `package.json` / `pnpm-lock.yaml` / `yarn.lock` -> Node.js
- `pyproject.toml` / `requirements.txt` / `Pipfile` -> Python
- `go.mod` -> Go
- `Cargo.toml` -> Rust
- `pom.xml` / `build.gradle` -> Java/Kotlin

Read `${CLAUDE_SKILL_DIR}/references/guide.md` for platform-specific workflow templates.

### Step 2: Generate the workflow
Run `python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py --project-type <type> --stages lint,test,build` to generate a base workflow YAML. The script outputs valid YAML with SHA-pinned actions.

### Step 3: Customize for the project
Adapt the generated workflow:
- Add matrix strategy for multi-version testing if needed
- Configure caching for the detected package manager
- Set appropriate concurrency group to cancel stale runs
- Add environment-specific deploy jobs if requested

### Step 4: Validate the workflow
Run `bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh <workflow-file>` to check:
- Valid YAML syntax
- Required keys present (on, jobs, runs-on, steps)
- SHA-pinned action references
- Permissions block is least-privilege
- No plaintext secrets

## Examples

**Example 1: Node.js project CI**
Input: "set up CI for my Next.js app"
Output: Generates `.github/workflows/ci.yml` with lint (ESLint), type-check (tsc), test (vitest), and build jobs. Uses `actions/setup-node` with pnpm caching, matrix for Node 18/20, concurrency group per PR. All actions SHA-pinned.

**Example 2: Python with multiple test environments**
Input: "I need GitHub Actions for my Python library that supports 3.10-3.12"
Output: Generates workflow with ruff lint, mypy type-check, and pytest across a 3x matrix (3.10, 3.11, 3.12). Uses `actions/setup-python` with pip caching. Includes a publish job triggered on release tags using trusted publishing (OIDC).

**Example 3: Monorepo with path filters**
Input: "only run frontend tests when frontend/ changes"
Output: Generates workflow with `paths` filter on `push` and `pull_request` triggers scoped to `frontend/**`. Uses path-based job conditions for backend vs frontend, shared setup action for common steps.

## Common mistakes to avoid
- Using `@v4` instead of `@<sha>` for actions — supply chain risk
- `permissions: write-all` — always use least privilege per job
- Missing `concurrency` — stale runs waste CI minutes
- Hardcoding secrets in workflow files — use GitHub Secrets + OIDC
- Forgetting to cache dependencies — doubles CI time for no reason
"""

_CICD_VALIDATE = """\
#!/usr/bin/env bash
set -euo pipefail
# validate.sh — Validate a GitHub Actions workflow YAML.
# Usage: bash validate.sh <path-to-workflow.yml>
# Exit 0 = valid, exit 1 = issues found.

WORKFLOW="${1:?Usage: validate.sh <workflow.yml>}"
ERRORS=0

if [[ ! -f "$WORKFLOW" ]]; then
  echo "ERROR: File not found: $WORKFLOW"
  exit 1
fi

# 1. Valid YAML (requires python3 + PyYAML or yq)
if command -v python3 &>/dev/null; then
  if ! python3 -c "
import sys, yaml
try:
    with open('$WORKFLOW') as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        print('ERROR: YAML root is not a mapping')
        sys.exit(1)
except yaml.YAMLError as e:
    print(f'ERROR: Invalid YAML: {e}')
    sys.exit(1)
" 2>&1; then
    echo "VIOLATION: Invalid YAML syntax."
    ERRORS=$((ERRORS + 1))
  fi
else
  echo "WARNING: python3 not available, skipping YAML parse check."
fi

# 2. Required top-level keys
for key in "on" "jobs"; do
  if ! grep -qE "^${key}:" "$WORKFLOW" && ! grep -qE "^\"${key}\":" "$WORKFLOW" && ! grep -qE "^'${key}':" "$WORKFLOW"; then
    # 'on' is a YAML keyword, might be quoted
    if [[ "$key" == "on" ]]; then
      if ! grep -qE '^(on|"on"|'"'"'on'"'"')\\s*:' "$WORKFLOW"; then
        echo "VIOLATION: Missing required top-level key: $key"
        ERRORS=$((ERRORS + 1))
      fi
    else
      echo "VIOLATION: Missing required top-level key: $key"
      ERRORS=$((ERRORS + 1))
    fi
  fi
done

# 3. Action references should use SHA pinning (not @v1, @main, etc.)
UNPINNED=$(grep -oE 'uses:\\s*[^#]+@[a-zA-Z]' "$WORKFLOW" 2>/dev/null | head -5 || true)
if [[ -n "$UNPINNED" ]]; then
  echo "VIOLATION: Action references not SHA-pinned:"
  echo "$UNPINNED"
  ERRORS=$((ERRORS + 1))
fi

# 4. Check for write-all permissions
if grep -qE 'permissions:\\s*write-all' "$WORKFLOW"; then
  echo "VIOLATION: 'permissions: write-all' is overly broad — use least privilege."
  ERRORS=$((ERRORS + 1))
fi

# 5. No plaintext secrets patterns
if grep -qiE '(password|secret_key|api_key|token)\\s*:\\s*["\x27][^$]' "$WORKFLOW"; then
  echo "VIOLATION: Possible plaintext secret detected — use GitHub Secrets."
  ERRORS=$((ERRORS + 1))
fi

# 6. Check jobs have runs-on
if command -v python3 &>/dev/null; then
  python3 -c "
import yaml, sys
with open('$WORKFLOW') as f:
    data = yaml.safe_load(f)
jobs = data.get('jobs', {})
if not jobs:
    print('VIOLATION: No jobs defined')
    sys.exit(1)
for name, job in jobs.items():
    if 'runs-on' not in job and 'uses' not in job:
        print(f'VIOLATION: Job \"{name}\" missing runs-on')
        sys.exit(1)
" 2>&1 || ERRORS=$((ERRORS + 1))
fi

if [[ $ERRORS -gt 0 ]]; then
  echo "---"
  echo "Found $ERRORS issue(s)."
  exit 1
else
  echo "Workflow passes all checks."
  exit 0
fi
"""

_CICD_HELPER = '''\
#!/usr/bin/env python3
"""CI/CD workflow generator for GitHub Actions.

Usage: python main_helper.py --project-type node --stages lint,test,build
       python main_helper.py --project-type python --stages lint,test,build,publish
"""
import argparse
import json
import sys
from typing import Any


# SHA pins for common actions (stable as of early 2025)
ACTION_PINS = {
    "actions/checkout": "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",  # v4.2.2
    "actions/setup-node": "actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020",  # v4.4.0
    "actions/setup-python": "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",  # v5.6.0
    "actions/setup-go": "actions/setup-go@d35c59abb061a4a6fb18e82ac0862c26744d6ab5",  # v5.5.0
    "actions/cache": "actions/cache@5a3ec84eff668545956fd18022155c47e93e2684",  # v4.2.3
}


def node_workflow(stages: list[str]) -> dict[str, Any]:
    """Generate a Node.js CI workflow."""
    jobs: dict[str, Any] = {}
    if "lint" in stages:
        jobs["lint"] = {
            "runs-on": "ubuntu-latest",
            "permissions": {"contents": "read"},
            "steps": [
                {"uses": ACTION_PINS["actions/checkout"]},
                {
                    "uses": ACTION_PINS["actions/setup-node"],
                    "with": {"node-version": "20", "cache": "npm"},
                },
                {"run": "npm ci"},
                {"run": "npm run lint"},
            ],
        }
    if "test" in stages:
        jobs["test"] = {
            "runs-on": "ubuntu-latest",
            "permissions": {"contents": "read"},
            "strategy": {"matrix": {"node-version": ["18", "20"]}},
            "steps": [
                {"uses": ACTION_PINS["actions/checkout"]},
                {
                    "uses": ACTION_PINS["actions/setup-node"],
                    "with": {
                        "node-version": "${{ matrix.node-version }}",
                        "cache": "npm",
                    },
                },
                {"run": "npm ci"},
                {"run": "npm test"},
            ],
        }
    if "build" in stages:
        needs = [j for j in ("lint", "test") if j in jobs]
        jobs["build"] = {
            "runs-on": "ubuntu-latest",
            "permissions": {"contents": "read"},
            **({"needs": needs} if needs else {}),
            "steps": [
                {"uses": ACTION_PINS["actions/checkout"]},
                {
                    "uses": ACTION_PINS["actions/setup-node"],
                    "with": {"node-version": "20", "cache": "npm"},
                },
                {"run": "npm ci"},
                {"run": "npm run build"},
            ],
        }
    return {
        "name": "CI",
        "on": {
            "push": {"branches": ["main"]},
            "pull_request": {"branches": ["main"]},
        },
        "concurrency": {
            "group": "${{ github.workflow }}-${{ github.ref }}",
            "cancel-in-progress": True,
        },
        "jobs": jobs,
    }


def python_workflow(stages: list[str]) -> dict[str, Any]:
    """Generate a Python CI workflow."""
    jobs: dict[str, Any] = {}
    if "lint" in stages:
        jobs["lint"] = {
            "runs-on": "ubuntu-latest",
            "permissions": {"contents": "read"},
            "steps": [
                {"uses": ACTION_PINS["actions/checkout"]},
                {
                    "uses": ACTION_PINS["actions/setup-python"],
                    "with": {"python-version": "3.12"},
                },
                {"run": "pip install ruff"},
                {"run": "ruff check ."},
                {"run": "ruff format --check ."},
            ],
        }
    if "test" in stages:
        jobs["test"] = {
            "runs-on": "ubuntu-latest",
            "permissions": {"contents": "read"},
            "strategy": {"matrix": {"python-version": ["3.10", "3.11", "3.12"]}},
            "steps": [
                {"uses": ACTION_PINS["actions/checkout"]},
                {
                    "uses": ACTION_PINS["actions/setup-python"],
                    "with": {"python-version": "${{ matrix.python-version }}"},
                },
                {"run": "pip install -e '.[test]'"},
                {"run": "pytest -v"},
            ],
        }
    if "build" in stages:
        needs = [j for j in ("lint", "test") if j in jobs]
        jobs["build"] = {
            "runs-on": "ubuntu-latest",
            "permissions": {"contents": "read"},
            **({"needs": needs} if needs else {}),
            "steps": [
                {"uses": ACTION_PINS["actions/checkout"]},
                {
                    "uses": ACTION_PINS["actions/setup-python"],
                    "with": {"python-version": "3.12"},
                },
                {"run": "pip install build"},
                {"run": "python -m build"},
            ],
        }
    return {
        "name": "CI",
        "on": {
            "push": {"branches": ["main"]},
            "pull_request": {"branches": ["main"]},
        },
        "concurrency": {
            "group": "${{ github.workflow }}-${{ github.ref }}",
            "cancel-in-progress": True,
        },
        "jobs": jobs,
    }


def go_workflow(stages: list[str]) -> dict[str, Any]:
    """Generate a Go CI workflow."""
    jobs: dict[str, Any] = {}
    if "lint" in stages:
        jobs["lint"] = {
            "runs-on": "ubuntu-latest",
            "permissions": {"contents": "read"},
            "steps": [
                {"uses": ACTION_PINS["actions/checkout"]},
                {
                    "uses": ACTION_PINS["actions/setup-go"],
                    "with": {"go-version-file": "go.mod"},
                },
                {"run": "go vet ./..."},
            ],
        }
    if "test" in stages:
        jobs["test"] = {
            "runs-on": "ubuntu-latest",
            "permissions": {"contents": "read"},
            "steps": [
                {"uses": ACTION_PINS["actions/checkout"]},
                {
                    "uses": ACTION_PINS["actions/setup-go"],
                    "with": {"go-version-file": "go.mod"},
                },
                {"run": "go test -race -v ./..."},
            ],
        }
    if "build" in stages:
        needs = [j for j in ("lint", "test") if j in jobs]
        jobs["build"] = {
            "runs-on": "ubuntu-latest",
            "permissions": {"contents": "read"},
            **({"needs": needs} if needs else {}),
            "steps": [
                {"uses": ACTION_PINS["actions/checkout"]},
                {
                    "uses": ACTION_PINS["actions/setup-go"],
                    "with": {"go-version-file": "go.mod"},
                },
                {"run": "go build -o bin/ ./..."},
            ],
        }
    return {
        "name": "CI",
        "on": {
            "push": {"branches": ["main"]},
            "pull_request": {"branches": ["main"]},
        },
        "concurrency": {
            "group": "${{ github.workflow }}-${{ github.ref }}",
            "cancel-in-progress": True,
        },
        "jobs": jobs,
    }


GENERATORS = {
    "node": node_workflow,
    "python": python_workflow,
    "go": go_workflow,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="GitHub Actions workflow generator")
    parser.add_argument(
        "--project-type",
        choices=list(GENERATORS.keys()),
        required=True,
        help="Project type",
    )
    parser.add_argument(
        "--stages",
        default="lint,test,build",
        help="Comma-separated pipeline stages",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of YAML",
    )
    args = parser.parse_args()

    stages = [s.strip() for s in args.stages.split(",")]
    generator = GENERATORS[args.project_type]
    workflow = generator(stages)

    if args.json:
        print(json.dumps(workflow, indent=2, default=str))
    else:
        try:
            import yaml
            print(yaml.dump(workflow, default_flow_style=False, sort_keys=False))
        except ImportError:
            print(json.dumps(workflow, indent=2, default=str))


if __name__ == "__main__":
    main()
'''

_CICD_GUIDE = """\
# CI/CD Pipeline Reference Guide

## GitHub Actions Workflow Structure

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<sha>
      # ...
```

## Security Best Practices

### SHA Pinning
Always pin actions to a full SHA, not a tag:
```yaml
# Bad
- uses: actions/checkout@v4
# Good
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
```

### Least-Privilege Permissions
Set permissions at the workflow level and override per job:
```yaml
permissions:
  contents: read    # default: read-only
  pull-requests: write  # only where needed
```

### Secrets
- Never hardcode secrets in workflow files
- Use `${{ secrets.MY_SECRET }}` for GitHub Secrets
- Use OIDC for cloud provider authentication (no long-lived credentials)

## Caching Strategies

| Package Manager | Cache Key |
|----------------|-----------|
| npm | `${{ runner.os }}-node-${{ hashFiles('**/package-lock.json') }}` |
| pnpm | `${{ runner.os }}-pnpm-${{ hashFiles('**/pnpm-lock.yaml') }}` |
| pip | `${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}` |
| Go | Built into actions/setup-go via go.sum |

## Matrix Strategy

```yaml
strategy:
  matrix:
    node-version: [18, 20, 22]
    os: [ubuntu-latest, macos-latest]
  fail-fast: false  # don't cancel all on first failure
```

## Job Dependencies

```yaml
jobs:
  lint:
    # runs immediately
  test:
    needs: lint  # waits for lint
  deploy:
    needs: [lint, test]  # waits for both
    if: github.ref == 'refs/heads/main'  # only on main
```

## Common Action SHA Pins (stable 2025)

| Action | SHA | Tag |
|--------|-----|-----|
| actions/checkout | 11bd71901bbe5b1630ceea73d27597364c9af683 | v4.2.2 |
| actions/setup-node | 49933ea5288caeca8642d1e84afbd3f7d6820020 | v4.4.0 |
| actions/setup-python | a26af69be951a213d495a4c3e4e4022e16d87065 | v5.6.0 |
| actions/setup-go | d35c59abb061a4a6fb18e82ac0862c26744d6ab5 | v5.5.0 |
| actions/cache | 5a3ec84eff668545956fd18022155c47e93e2684 | v4.2.3 |

## Concurrency Groups

Cancel stale runs to save CI minutes:
```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

## Path Filters (Monorepo)

```yaml
on:
  push:
    paths:
      - 'frontend/**'
      - '.github/workflows/frontend.yml'
```
"""

# ---------------------------------------------------------------------------
# 8. Dependency Auditor
# ---------------------------------------------------------------------------
_DEP_AUDIT_BODY = """\
## Quick Start
Detect the project ecosystem from lockfiles, run the native audit tool, normalize findings into a unified JSON report with severity counts and remediation advice. Validate the report before presenting it.

## When to use this skill
Use when the user says "audit dependencies", "vulnerability scan", "npm audit", "pip-audit", "security check", "CVE", "supply chain", "outdated packages", or "are my deps safe". Also triggers on "check for vulnerabilities" or "dependency review", even if they don't name a specific tool.
NOT for source code security review, container scanning, or SAST/DAST.

## Workflow

### Step 1: Detect ecosystem
Scan the project directory for lockfiles:
- `package-lock.json` / `pnpm-lock.yaml` / `yarn.lock` -> npm
- `poetry.lock` / `Pipfile.lock` / `requirements.txt` -> Python (pip)
- `Cargo.lock` -> Rust
- `go.sum` -> Go

Read `${CLAUDE_SKILL_DIR}/references/guide.md` for ecosystem-specific audit commands and severity mapping.

### Step 2: Run the audit
Run `python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py --dir <project-dir>` to auto-detect the ecosystem and produce a unified JSON report.

If the native audit tool is available, it will be called. Otherwise the script falls back to parsing lockfiles directly for known-vulnerable patterns.

### Step 3: Analyze and prioritize
Group findings by severity (critical > high > medium > low). For each critical/high finding:
- Check if a fix version exists
- Determine if the vulnerable code path is reachable
- Suggest the minimal upgrade that resolves it

### Step 4: Validate the report
Run `bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh <report.json>` to confirm the report schema is correct and severity counts match.

## Examples

**Example 1: Node.js project with known CVEs**
Input: "audit my Node.js project for vulnerabilities"
Output: Runs npm audit, finds 3 critical (prototype pollution in lodash, ReDoS in semver, path traversal in tar), 5 high, 12 moderate. Reports fix versions for all critical issues, estimates 2 are direct deps (fixable with `npm update`) and 1 is transitive (requires `npm audit fix --force` or override).

**Example 2: Python project with outdated deps**
Input: "check if my Python dependencies have any CVEs"
Output: Runs pip-audit against the lockfile, finds 1 critical (Jinja2 SSTI in old version), 2 medium. Shows upgrade path from Jinja2 2.11 to 3.1.3. Flags 4 packages with no updates in 2+ years as unmaintained.

**Example 3: Quick health check**
Input: "are my dependencies safe?"
Output: Auto-detects Go project from go.sum. Runs `go vuln check`, finds 0 critical, 1 medium (golang.org/x/crypto timing attack in old version). Reports overall health as "good" with one recommended upgrade.

## Common mistakes to avoid
- Running `npm audit fix --force` without reviewing — can introduce breaking changes
- Ignoring transitive dependency vulnerabilities — they are still exploitable
- Treating all "moderate" findings as low priority — check if the vulnerable function is actually called
- Not checking if a vulnerability has a fix — some CVEs have no patched version yet
"""

_DEP_AUDIT_VALIDATE = """\
#!/usr/bin/env bash
set -euo pipefail
# validate.sh — Validate a dependency audit report JSON.
# Usage: bash validate.sh <report.json>
# Exit 0 = valid, exit 1 = schema violations.

REPORT="${1:?Usage: validate.sh <report.json>}"
ERRORS=0

if [[ ! -f "$REPORT" ]]; then
  echo "ERROR: File not found: $REPORT"
  exit 1
fi

# Validate with python
python3 -c "
import json, sys

with open('$REPORT') as f:
    try:
        data = json.load(f)
    except json.JSONDecodeError as e:
        print(f'ERROR: Invalid JSON: {e}')
        sys.exit(1)

errors = 0

# Required top-level keys
for key in ('ecosystem', 'total_deps', 'vulnerabilities', 'summary'):
    if key not in data:
        print(f'VIOLATION: Missing required key: {key}')
        errors += 1

# Check vulnerabilities schema
vulns = data.get('vulnerabilities', [])
if not isinstance(vulns, list):
    print('VIOLATION: vulnerabilities must be a list')
    errors += 1
else:
    seen = set()
    for i, v in enumerate(vulns):
        for field in ('package', 'version', 'severity'):
            if field not in v:
                print(f'VIOLATION: vulnerability[{i}] missing {field}')
                errors += 1
        # Check severity is valid
        if v.get('severity') not in ('critical', 'high', 'medium', 'low'):
            print(f'VIOLATION: vulnerability[{i}] invalid severity: {v.get(\"severity\")}')
            errors += 1
        # Check for duplicates
        key = (v.get('package', ''), v.get('cve', ''))
        if key[1] and key in seen:
            print(f'VIOLATION: duplicate entry: {key}')
            errors += 1
        seen.add(key)

# Check summary counts match
summary = data.get('summary', {})
for sev in ('critical', 'high', 'medium', 'low'):
    expected = len([v for v in vulns if v.get('severity') == sev])
    actual = summary.get(sev, 0)
    if expected != actual:
        print(f'VIOLATION: summary.{sev}={actual} but found {expected} entries')
        errors += 1

if errors:
    print(f'---')
    print(f'Found {errors} schema violation(s).')
    sys.exit(1)
else:
    print('Report passes all schema checks.')
" 2>&1 || ERRORS=$((ERRORS + 1))

exit $ERRORS
"""

_DEP_AUDIT_HELPER = '''\
#!/usr/bin/env python3
"""Dependency audit tool — multi-ecosystem vulnerability scanner.

Usage: python main_helper.py --dir <project-directory>
       python main_helper.py --dir . --ecosystem npm
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def detect_ecosystem(project_dir: str) -> str | None:
    """Detect project ecosystem from lockfiles."""
    p = Path(project_dir)
    checks = [
        (["package-lock.json", "pnpm-lock.yaml", "yarn.lock"], "npm"),
        (["poetry.lock", "Pipfile.lock"], "pip"),
        (["requirements.txt"], "pip"),
        (["Cargo.lock"], "cargo"),
        (["go.sum"], "go"),
    ]
    for files, ecosystem in checks:
        for f in files:
            if (p / f).exists():
                return ecosystem
    return None


def count_deps(project_dir: str, ecosystem: str) -> int:
    """Count approximate number of dependencies."""
    p = Path(project_dir)
    if ecosystem == "npm":
        lock = p / "package-lock.json"
        if lock.exists():
            data = json.loads(lock.read_text())
            packages = data.get("packages", data.get("dependencies", {}))
            return len(packages)
    elif ecosystem == "pip":
        for fname in ("poetry.lock", "requirements.txt"):
            f = p / fname
            if f.exists():
                lines = [l for l in f.read_text().splitlines()
                         if l.strip() and not l.startswith("#") and not l.startswith("-")]
                return len(lines)
    elif ecosystem == "cargo":
        lock = p / "Cargo.lock"
        if lock.exists():
            return lock.read_text().count("[[package]]")
    elif ecosystem == "go":
        gosum = p / "go.sum"
        if gosum.exists():
            return len(set(l.split()[0] for l in gosum.read_text().splitlines() if l.strip()))
    return 0


def run_npm_audit(project_dir: str) -> list[dict]:
    """Run npm audit and parse results."""
    try:
        result = subprocess.run(
            ["npm", "audit", "--json"],
            capture_output=True, text=True, cwd=project_dir, timeout=60,
        )
        data = json.loads(result.stdout)
        vulns = []
        advisories = data.get("vulnerabilities", {})
        for name, info in advisories.items():
            severity = info.get("severity", "medium")
            via = info.get("via", [])
            cve = ""
            desc = ""
            fix_version = info.get("fixAvailable", {})
            if isinstance(fix_version, dict):
                fix_version = fix_version.get("version", "")
            elif isinstance(fix_version, bool):
                fix_version = "available" if fix_version else ""
            for v in via:
                if isinstance(v, dict):
                    cve = v.get("cve", cve) or cve
                    desc = v.get("title", desc) or desc
            vulns.append({
                "package": name,
                "version": info.get("range", "unknown"),
                "severity": severity,
                "cve": cve,
                "description": desc,
                "fix_version": str(fix_version),
            })
        return vulns
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        return []


def run_pip_audit(project_dir: str) -> list[dict]:
    """Run pip-audit and parse results."""
    try:
        result = subprocess.run(
            ["pip-audit", "--format=json", "--desc"],
            capture_output=True, text=True, cwd=project_dir, timeout=120,
        )
        entries = json.loads(result.stdout)
        vulns = []
        for entry in entries:
            for vuln in entry.get("vulns", []):
                vulns.append({
                    "package": entry["name"],
                    "version": entry["version"],
                    "severity": classify_cvss(vuln.get("fix_versions", [])),
                    "cve": vuln.get("id", ""),
                    "description": vuln.get("description", ""),
                    "fix_version": vuln.get("fix_versions", [""])[0] if vuln.get("fix_versions") else "",
                })
        return vulns
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        return []


def classify_cvss(fix_versions: list) -> str:
    """Classify severity heuristically when CVSS not available."""
    # Default to medium when we can't determine
    return "medium"


def audit(project_dir: str, ecosystem: str | None = None) -> dict:
    """Run audit and return unified report."""
    if ecosystem is None:
        ecosystem = detect_ecosystem(project_dir)
    if ecosystem is None:
        return {"error": "Could not detect project ecosystem", "ecosystem": "unknown",
                "total_deps": 0, "vulnerabilities": [], "summary": {}}

    total_deps = count_deps(project_dir, ecosystem)

    runners = {"npm": run_npm_audit, "pip": run_pip_audit}
    vulns = runners.get(ecosystem, lambda d: [])(project_dir)

    summary = {
        "critical": len([v for v in vulns if v["severity"] == "critical"]),
        "high": len([v for v in vulns if v["severity"] == "high"]),
        "medium": len([v for v in vulns if v["severity"] == "medium"]),
        "low": len([v for v in vulns if v["severity"] == "low"]),
    }

    return {
        "ecosystem": ecosystem,
        "total_deps": total_deps,
        "vulnerabilities": vulns,
        "summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-ecosystem dependency auditor")
    parser.add_argument("--dir", required=True, help="Project directory to audit")
    parser.add_argument("--ecosystem", choices=["npm", "pip", "cargo", "go"],
                        help="Override ecosystem detection")
    args = parser.parse_args()

    result = audit(args.dir, args.ecosystem)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
'''

_DEP_AUDIT_GUIDE = """\
# Dependency Audit Reference Guide

## Severity-to-Action Mapping

| Severity | CVSS Range | Action | Timeline |
|----------|-----------|--------|----------|
| Critical | 9.0-10.0 | Block deploy, fix immediately | Same day |
| High | 7.0-8.9 | Fix within current sprint | 1-2 weeks |
| Medium | 4.0-6.9 | Fix within quarter | 1-3 months |
| Low | 0.1-3.9 | Track, fix opportunistically | Best effort |

## Native Audit Commands

### npm
```bash
npm audit --json                # JSON output
npm audit --omit=dev            # Skip devDependencies
npm audit fix                   # Auto-fix (safe upgrades only)
npm audit fix --force           # Force fix (may break things!)
```

### Python (pip-audit)
```bash
pip install pip-audit
pip-audit                        # Scan installed packages
pip-audit -r requirements.txt   # Scan requirements file
pip-audit --format=json          # JSON output
```

### Cargo
```bash
cargo install cargo-audit
cargo audit                      # Scan Cargo.lock
cargo audit --json               # JSON output
```

### Go
```bash
go install golang.org/x/vuln/cmd/govulncheck@latest
govulncheck ./...                # Scan source code
```

## Supply Chain Attack Taxonomy

### Typosquatting
Attacker publishes a package with a name similar to a popular one:
- `lod-ash` instead of `lodash`
- `crossenv` instead of `cross-env`
Detection: Compare dependency names against top-1000 packages using edit distance.

### Dependency Confusion
Attacker publishes a public package with the same name as an internal one:
- npm/PyPI public registry takes priority over private
Detection: Check for packages that match internal naming patterns on public registries.

### Maintainer Compromise
Attacker gains access to a legitimate maintainer's account:
- `event-stream` (2018): malicious code added via new maintainer
- `ua-parser-js` (2021): maintainer's npm account compromised
Detection: Monitor for sudden maintainer changes or unusual publish patterns.

## Unmaintained Package Indicators

A package may be unmaintained if:
- No commits in 2+ years
- No releases in 2+ years
- Archived GitHub repository
- Unresponsive to critical security issues
- Deprecated on the registry

## Remediation Strategies

1. **Upgrade**: Update to the patched version (preferred)
2. **Override/Resolution**: Force a transitive dep version (npm overrides, pip constraints)
3. **Replace**: Switch to an actively maintained alternative
4. **Mitigate**: If no fix exists, add runtime checks or WAF rules
5. **Accept**: Document risk acceptance for low-severity with no fix
"""

# ---------------------------------------------------------------------------
# 9. Secret Scanner
# ---------------------------------------------------------------------------
_SECRET_SCANNER_BODY = """\
## Quick Start
Scan a codebase for hardcoded secrets (API keys, tokens, passwords, connection strings) using regex patterns. Classify each finding by type and confidence, filter false positives, and suggest remediation. Run validation to confirm the report is well-formed.

## When to use this skill
Use when the user says "scan for secrets", "find hardcoded keys", "secret detection", "credential leak", "API key in code", "check for passwords", "trufflehog", or "gitleaks". Also triggers on "is my code leaking secrets" or "pre-commit secret check", even if they don't name a specific tool.
NOT for runtime secret management, vault configuration, or encryption implementation.

## Workflow

### Step 1: Scan the codebase
Run `python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py --scan <directory>` to scan all text files for secret patterns. The script checks 30+ pattern types and applies false-positive filtering.

### Step 2: Review findings
Read `${CLAUDE_SKILL_DIR}/references/guide.md` for the full pattern catalog and false-positive heuristics. For each finding:
- Verify it's not a test fixture, example, or placeholder
- Check the confidence level (high = known format, medium = generic pattern, low = heuristic)
- Determine if the secret is still active (check git history)

### Step 3: Prioritize and remediate
For each confirmed secret:
1. Rotate the credential immediately (before removing from code)
2. Move to environment variable or secret manager
3. Add the pattern to `.gitignore` and pre-commit hooks
4. If in git history, use `git filter-repo` to purge

### Step 4: Validate the report
Run `bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh <report.json>` to confirm schema compliance.

## Examples

**Example 1: AWS credentials in source**
Input: "scan my project for leaked secrets"
Output: Finds `AKIA...` pattern in `config/aws.py` line 12 (confidence: high, type: AWS Access Key), `aws_secret_access_key` in same file line 13 (confidence: high). Recommends: rotate keys in AWS console, replace with `os.environ["AWS_ACCESS_KEY_ID"]`, add `config/aws.py` to `.gitignore`.

**Example 2: Mixed results with false positives**
Input: "check for hardcoded passwords"
Output: Scans 847 files, finds 5 matches. 2 are real (database password in `settings.py`, API token in `deploy.sh`), 3 are false positives (test fixtures with `password="test123"`, documentation example, placeholder `YOUR_API_KEY_HERE`). Reports only the 2 real findings with confidence: high.

**Example 3: Pre-commit check**
Input: "are there any secrets in the files I'm about to commit?"
Output: Scans staged files only (`git diff --cached --name-only`). Finds JWT token in `src/auth.ts` line 45. Blocks commit recommendation, suggests moving to environment variable.

## Common mistakes to avoid
- Removing secrets from code without rotating them first — they're already in git history
- Ignoring low-confidence findings — review them manually, don't auto-dismiss
- Scanning only current files — check git history too (`git log -p | grep`)
- Adding secrets to `.env` without adding `.env` to `.gitignore`
"""

_SECRET_SCANNER_VALIDATE = """\
#!/usr/bin/env bash
set -euo pipefail
# validate.sh — Validate a secret scan report JSON.
# Usage: bash validate.sh <report.json>
# Exit 0 = valid, exit 1 = schema violations.

REPORT="${1:?Usage: validate.sh <report.json>}"

if [[ ! -f "$REPORT" ]]; then
  echo "ERROR: File not found: $REPORT"
  exit 1
fi

python3 -c "
import json, sys

with open('$REPORT') as f:
    try:
        data = json.load(f)
    except json.JSONDecodeError as e:
        print(f'ERROR: Invalid JSON: {e}')
        sys.exit(1)

errors = 0

# Required top-level keys
for key in ('files_scanned', 'findings', 'summary'):
    if key not in data:
        print(f'VIOLATION: Missing required key: {key}')
        errors += 1

findings = data.get('findings', [])
if not isinstance(findings, list):
    print('VIOLATION: findings must be a list')
    errors += 1
else:
    for i, f in enumerate(findings):
        for field in ('file', 'line', 'type', 'confidence'):
            if field not in f:
                print(f'VIOLATION: findings[{i}] missing {field}')
                errors += 1
        if f.get('confidence') not in ('high', 'medium', 'low'):
            print(f'VIOLATION: findings[{i}] invalid confidence: {f.get(\"confidence\")}')
            errors += 1

# Excluded paths check
excluded = ('.git/', 'node_modules/', 'vendor/', '__pycache__/')
for i, f in enumerate(findings):
    fp = f.get('file', '')
    for exc in excluded:
        if exc in fp:
            print(f'VIOLATION: findings[{i}] in excluded path: {fp}')
            errors += 1

# Summary counts
summary = data.get('summary', {})
by_type = {}
for f in findings:
    t = f.get('type', 'unknown')
    by_type[t] = by_type.get(t, 0) + 1
if summary.get('total', 0) != len(findings):
    print(f'VIOLATION: summary.total={summary.get(\"total\")} but {len(findings)} findings')
    errors += 1

if errors:
    print(f'---')
    print(f'Found {errors} schema violation(s).')
    sys.exit(1)
else:
    print('Report passes all schema checks.')
"
"""

_SECRET_SCANNER_HELPER = '''\
#!/usr/bin/env python3
"""Secret scanner — detect hardcoded credentials in source code.

Usage: python main_helper.py --scan <directory>
       python main_helper.py --scan . --exclude "test_*,*.md"
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

# Secret patterns: (name, regex, confidence)
SECRET_PATTERNS: list[tuple[str, str, str]] = [
    # AWS
    ("AWS Access Key", r"AKIA[0-9A-Z]{16}", "high"),
    ("AWS Secret Key", r"aws_secret_access_key\s*=\s*[\"'][A-Za-z0-9/+=]{40}[\"']", "high"),
    # GitHub
    ("GitHub Token (classic)", r"ghp_[A-Za-z0-9_]{36}", "high"),
    ("GitHub Token (fine-grained)", r"github_pat_[A-Za-z0-9_]{22}_[A-Za-z0-9]{59}", "high"),
    ("GitHub OAuth", r"gho_[A-Za-z0-9_]{36}", "high"),
    # Stripe
    ("Stripe Secret Key", r"sk_live_[A-Za-z0-9]{24,}", "high"),
    ("Stripe Restricted Key", r"rk_live_[A-Za-z0-9]{24,}", "high"),
    # Slack
    ("Slack Token", r"xox[bpars]-[A-Za-z0-9-]{10,}", "high"),
    ("Slack Webhook", r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+", "high"),
    # Database URLs
    ("Database URL", r"(postgres|mysql|mongodb|redis)://[^:]+:[^@]+@[^\s\"']+", "high"),
    # JWT
    ("JWT Token", r"eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_.+/=]+", "medium"),
    # Generic
    ("Generic API Key", r"(?i)(api[_-]?key|apikey)\s*[:=]\s*[\"'][A-Za-z0-9_\-]{20,}[\"']", "medium"),
    ("Generic Secret", r"(?i)(secret|password|passwd|pwd)\s*[:=]\s*[\"'][^\"']{8,}[\"']", "medium"),
    ("Generic Token", r"(?i)(token|auth_token|access_token)\s*[:=]\s*[\"'][A-Za-z0-9_\-]{20,}[\"']", "medium"),
    ("Bearer Token", r"Bearer\s+[A-Za-z0-9\-._~+/]{20,}=*", "medium"),
    ("Private Key Header", r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----", "high"),
    # SendGrid
    ("SendGrid API Key", r"SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}", "high"),
    # Twilio
    ("Twilio API Key", r"SK[a-f0-9]{32}", "medium"),
    # Mailgun
    ("Mailgun API Key", r"key-[A-Za-z0-9]{32}", "medium"),
    # Heroku
    ("Heroku API Key", r"(?i)heroku.*['\"][0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}['\"]", "medium"),
]

# False positive indicators
FALSE_POSITIVE_INDICATORS = [
    "example", "sample", "test", "mock", "fake", "dummy", "placeholder",
    "YOUR_", "xxx", "CHANGEME", "REPLACE_ME", "TODO", "FIXME",
    "<your-", "insert-your", "your_api_key", "your-api-key",
]

EXCLUDED_DIRS = {".git", "node_modules", "vendor", "__pycache__", ".venv",
                 "venv", ".tox", ".mypy_cache", ".ruff_cache", "dist", "build"}

TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".rb",
    ".php", ".sh", ".bash", ".zsh", ".yml", ".yaml", ".json", ".toml",
    ".cfg", ".ini", ".env", ".conf", ".config", ".xml", ".html", ".css",
    ".sql", ".tf", ".hcl", ".md", ".txt", ".r", ".R",
}


def is_excluded(path: Path) -> bool:
    """Check if path is in an excluded directory."""
    return any(part in EXCLUDED_DIRS for part in path.parts)


def is_text_file(path: Path) -> bool:
    """Check if file has a recognized text extension."""
    return path.suffix.lower() in TEXT_EXTENSIONS or path.name in {
        ".env", ".env.local", ".env.production", "Dockerfile",
        "Makefile", "Gemfile", "Rakefile",
    }


def is_false_positive(line: str, match_text: str) -> bool:
    """Check if a match is likely a false positive."""
    lower_line = line.lower()
    lower_match = match_text.lower()
    for indicator in FALSE_POSITIVE_INDICATORS:
        if indicator.lower() in lower_line or indicator.lower() in lower_match:
            return True
    # Check if it's in a comment
    stripped = line.lstrip()
    if stripped.startswith(("#", "//", "*", "/*")):
        # Still flag if it looks like a real secret despite being commented
        if any(p in match_text for p in ("AKIA", "ghp_", "sk_live_", "xox")):
            return False
        return True
    return False


def scan_file(filepath: Path) -> list[dict]:
    """Scan a single file for secrets."""
    findings = []
    try:
        text = filepath.read_text(errors="ignore")
    except (OSError, PermissionError):
        return findings

    for line_num, line in enumerate(text.splitlines(), 1):
        for name, pattern, confidence in SECRET_PATTERNS:
            for match in re.finditer(pattern, line):
                match_text = match.group(0)
                if is_false_positive(line, match_text):
                    continue
                # Redact the actual secret in the snippet
                snippet = line.strip()[:120]
                findings.append({
                    "file": str(filepath),
                    "line": line_num,
                    "type": name,
                    "confidence": confidence,
                    "snippet": snippet,
                })
    return findings


def scan_directory(root: str, exclude_patterns: list[str] | None = None) -> dict:
    """Scan a directory tree for secrets."""
    root_path = Path(root)
    all_findings: list[dict] = []
    files_scanned = 0

    for dirpath, dirnames, filenames in os.walk(root_path):
        dp = Path(dirpath)
        # Prune excluded directories
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]

        for fname in filenames:
            fpath = dp / fname
            if not is_text_file(fpath):
                continue
            if is_excluded(fpath):
                continue
            if exclude_patterns:
                from fnmatch import fnmatch
                if any(fnmatch(fname, p) for p in exclude_patterns):
                    continue
            files_scanned += 1
            all_findings.extend(scan_file(fpath))

    by_type: dict[str, int] = {}
    for f in all_findings:
        t = f["type"]
        by_type[t] = by_type.get(t, 0) + 1

    return {
        "files_scanned": files_scanned,
        "findings": all_findings,
        "summary": {
            "total": len(all_findings),
            "by_type": by_type,
            "high_confidence": len([f for f in all_findings if f["confidence"] == "high"]),
            "medium_confidence": len([f for f in all_findings if f["confidence"] == "medium"]),
            "low_confidence": len([f for f in all_findings if f["confidence"] == "low"]),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Secret scanner")
    parser.add_argument("--scan", required=True, metavar="DIR", help="Directory to scan")
    parser.add_argument("--exclude", default="", help="Comma-separated glob patterns to exclude")
    parser.add_argument("--json", action="store_true", default=True, help="Output JSON (default)")
    args = parser.parse_args()

    excludes = [p.strip() for p in args.exclude.split(",") if p.strip()] if args.exclude else None
    result = scan_directory(args.scan, excludes)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
'''

_SECRET_SCANNER_GUIDE = """\
# Secret Scanner Reference Guide

## Secret Pattern Catalog

### Cloud Provider Keys

| Provider | Pattern | Example Format |
|----------|---------|---------------|
| AWS Access Key | `AKIA[0-9A-Z]{16}` | `AKIAIOSFODNN7EXAMPLE` |
| AWS Secret Key | 40-char base64 after `aws_secret_access_key=` | `wJalrXUtnFEMI/K7MDENG/...` |
| GCP Service Account | JSON with `type: service_account` | `{"type": "service_account",...}` |
| Azure Storage Key | 88-char base64 after `AccountKey=` | `AccountKey=abc123...==` |

### Code Platform Tokens

| Platform | Pattern | Example Format |
|----------|---------|---------------|
| GitHub (classic) | `ghp_[A-Za-z0-9_]{36}` | `ghp_ABCdef123456...` |
| GitHub (fine-grained) | `github_pat_...` | `github_pat_11A...` |
| GitLab | `glpat-[A-Za-z0-9_-]{20}` | `glpat-abc123...` |

### Payment/SaaS

| Service | Pattern | Example Format |
|---------|---------|---------------|
| Stripe Secret | `sk_live_[A-Za-z0-9]{24,}` | `sk_live_abc123...` |
| SendGrid | `SG.[A-Za-z0-9_-]{22}.[A-Za-z0-9_-]{43}` | `SG.abc...xyz` |
| Twilio | `SK[a-f0-9]{32}` | `SK1234abcd...` |
| Slack Token | `xox[bpars]-...` | `xoxb-123-456-abc` |

### Generic Patterns

| Type | Pattern | Confidence |
|------|---------|-----------|
| Database URL | `(postgres|mysql|mongodb)://user:pass@host` | High |
| JWT | `eyJ...eyJ...` (3 base64 segments) | Medium |
| Private Key | `-----BEGIN ... PRIVATE KEY-----` | High |
| Bearer Token | `Bearer [20+ chars]` | Medium |
| Password assignment | `password = "..."` | Medium |

## False Positive Heuristics

Skip matches that contain:
- `example`, `sample`, `test`, `mock`, `fake`, `dummy`
- `YOUR_`, `xxx`, `CHANGEME`, `REPLACE_ME`, `TODO`
- Appear in files named `*test*`, `*example*`, `*fixture*`
- Are in documentation (`.md`, `.rst`, `.adoc`) with placeholder values
- Match `000000`, `abcdef`, `123456` (obviously fake)

## Remediation Playbook

### Immediate Response (Critical/High)

1. **Rotate the credential** before removing from code
   - AWS: IAM console -> Security credentials -> Create new key -> Delete old
   - GitHub: Settings -> Developer settings -> Personal access tokens -> Regenerate
   - Stripe: Dashboard -> Developers -> API keys -> Roll key

2. **Remove from code**
   ```bash
   # Replace with environment variable
   # Before: API_KEY = "sk_live_abc123"
   # After:  API_KEY = os.environ["STRIPE_SECRET_KEY"]
   ```

3. **Purge from git history** (if committed)
   ```bash
   pip install git-filter-repo
   git filter-repo --path config/secrets.py --invert-paths
   # OR for specific strings:
   git filter-repo --replace-text replacements.txt
   ```

4. **Add prevention**
   ```bash
   # .gitignore
   .env
   .env.*
   *.pem
   *.key

   # Pre-commit hook (.pre-commit-config.yaml)
   - repo: https://github.com/gitleaks/gitleaks
     rev: v8.18.0
     hooks:
       - id: gitleaks
   ```

## Environment Variable Best Practices

- Use `.env` files for local development (always gitignored)
- Use platform secret stores for production (AWS SSM, GCP Secret Manager, Vault)
- Never log environment variables at startup
- Use `--mount=type=secret` for Docker build secrets
"""

# ---------------------------------------------------------------------------
# 10. API Documentation Generator
# ---------------------------------------------------------------------------
_API_DOC_BODY = """\
## Quick Start
Parse source code to extract public symbols (functions, classes, methods), check for existing documentation, generate or complete docstrings in the target format, and report coverage. Validate that all parameters are documented.

## When to use this skill
Use when the user says "document", "docstring", "JSDoc", "TSDoc", "API docs", "add documentation", "document my code", "generate docs", "Sphinx", or "missing docs". Also triggers on "my functions have no docs" or "improve code documentation", even if they don't specify a format.
NOT for README writing, user guides, or architecture documentation.

## Workflow

### Step 1: Analyze the source file
Run `python ${CLAUDE_SKILL_DIR}/scripts/main_helper.py --analyze <file>` to extract all public symbols, their signatures, existing documentation, and coverage metrics.

### Step 2: Determine the target format
Detect or ask for the documentation style:
- Python: Google-style (default), Sphinx RST, NumPy
- JavaScript/TypeScript: JSDoc/TSDoc
- Java: Javadoc

Read `${CLAUDE_SKILL_DIR}/references/guide.md` for format specifications and examples.

### Step 3: Generate documentation
For each undocumented or incomplete symbol:
1. Write a one-line summary (what, not how)
2. Document all parameters with types and descriptions
3. Document return value and type
4. Document exceptions/errors raised
5. Add one usage example for complex functions

### Step 4: Validate
Run `bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh <file> --format <format>` to verify:
- All public symbols have documentation
- All parameters from signatures are documented
- Format matches the target style

## Examples

**Example 1: Python module with no docstrings**
Input: "add Google-style docstrings to my Python file"
Output: Analyzes `utils.py`, finds 8 public functions with 0 documented. Generates Google-style docstrings for each with Args, Returns, and Raises sections. Coverage goes from 0% to 100%.

**Example 2: TypeScript file with partial JSDoc**
Input: "my TypeScript functions are missing JSDoc for some params"
Output: Analyzes `api.ts`, finds 12 functions, 7 have JSDoc but 3 are missing `@param` for newly added arguments. Completes the existing JSDoc blocks without rewriting the descriptions that already exist.

**Example 3: Coverage report only**
Input: "what's my documentation coverage?"
Output: Scans `src/` directory, finds 45 public symbols across 8 files. 28 documented (62% coverage). Lists the 17 undocumented symbols by file with their signatures. Recommends starting with the 5 exported functions that appear in the public API.

## Common mistakes to avoid
- Documenting the "what" instead of the "why" — `# Adds 1 to x` is useless
- Forgetting to update docs when parameters change — stale docs are worse than none
- Mixing documentation styles in the same file — pick one and be consistent
- Not documenting exceptions/errors — callers need to know what can go wrong
"""

_API_DOC_VALIDATE = """\
#!/usr/bin/env bash
set -euo pipefail
# validate.sh — Validate documentation coverage and format compliance.
# Usage: bash validate.sh <source-file> [--format google|jsdoc|sphinx]
# Exit 0 = passes, exit 1 = issues found.

FILE="${1:?Usage: validate.sh <source-file> [--format google|jsdoc|sphinx]}"
FORMAT="${3:-auto}"
ERRORS=0

if [[ ! -f "$FILE" ]]; then
  echo "ERROR: File not found: $FILE"
  exit 1
fi

EXT="${FILE##*.}"

# Auto-detect format from extension
if [[ "$FORMAT" == "auto" ]]; then
  case "$EXT" in
    py) FORMAT="google" ;;
    js|ts|jsx|tsx) FORMAT="jsdoc" ;;
    java) FORMAT="javadoc" ;;
    *) FORMAT="google" ;;
  esac
fi

python3 -c "
import ast, re, sys

file_path = '$FILE'
fmt = '$FORMAT'
errors = 0

if fmt in ('google', 'sphinx'):
    # Python file analysis
    try:
        with open(file_path) as f:
            tree = ast.parse(f.read())
    except SyntaxError as e:
        print(f'ERROR: Cannot parse Python file: {e}')
        sys.exit(1)

    public_symbols = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith('_'):
                public_symbols.append(node)
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith('_'):
                public_symbols.append(node)

    documented = 0
    for sym in public_symbols:
        docstring = ast.get_docstring(sym)
        if docstring:
            documented += 1
            # Check parameter documentation
            if isinstance(sym, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = [a.arg for a in sym.args.args if a.arg != 'self' and a.arg != 'cls']
                if fmt == 'google':
                    for p in params:
                        if p + ':' not in docstring and p + ' :' not in docstring:
                            if 'Args:' in docstring:
                                print(f'WARNING: {sym.name}() missing doc for param \"{p}\"')
                elif fmt == 'sphinx':
                    for p in params:
                        if f':param {p}:' not in docstring and f':param {p} ' not in docstring:
                            print(f'WARNING: {sym.name}() missing :param {p}: in docstring')
        else:
            print(f'VIOLATION: {sym.name} has no docstring')
            errors += 1

    total = len(public_symbols)
    pct = (documented / total * 100) if total else 100
    print(f'Coverage: {documented}/{total} ({pct:.0f}%)')

elif fmt == 'jsdoc':
    # JS/TS file analysis
    with open(file_path) as f:
        content = f.read()

    # Find exported functions
    fn_pattern = re.compile(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)')
    arrow_pattern = re.compile(r'(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*(?::\s*\w+)?\s*=>')

    functions = list(fn_pattern.finditer(content)) + list(arrow_pattern.finditer(content))
    documented = 0

    for match in functions:
        name = match.group(1)
        params_str = match.group(2)
        # Check if JSDoc exists before this function
        start = match.start()
        before = content[:start].rstrip()
        if before.endswith('*/'):
            jsdoc_start = before.rfind('/**')
            if jsdoc_start != -1:
                jsdoc = before[jsdoc_start:]
                documented += 1
                # Check @param tags
                if params_str.strip():
                    param_names = [p.strip().split(':')[0].split('=')[0].strip()
                                   for p in params_str.split(',') if p.strip()]
                    for p in param_names:
                        if p and f'@param' not in jsdoc:
                            print(f'WARNING: {name}() JSDoc missing @param tags')
                            break
            else:
                print(f'VIOLATION: {name}() has no JSDoc')
                errors += 1
        else:
            print(f'VIOLATION: {name}() has no JSDoc')
            errors += 1

    total = len(functions)
    pct = (documented / total * 100) if total else 100
    print(f'Coverage: {documented}/{total} ({pct:.0f}%)')

if errors:
    print(f'---')
    print(f'Found {errors} documentation issue(s).')
    sys.exit(1)
else:
    print('Documentation passes all checks.')
" 2>&1 || ERRORS=$((ERRORS + 1))

exit $ERRORS
"""

_API_DOC_HELPER = '''\
#!/usr/bin/env python3
"""API documentation analyzer — extract symbols and measure coverage.

Usage: python main_helper.py --analyze <source-file>
       python main_helper.py --analyze src/ --recursive
"""
import argparse
import ast
import json
import re
import sys
from pathlib import Path


def analyze_python(filepath: Path) -> list[dict]:
    """Analyze a Python file for public symbols and documentation."""
    text = filepath.read_text()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    symbols = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            params = []
            for arg in node.args.args:
                if arg.arg in ("self", "cls"):
                    continue
                annotation = ""
                if arg.annotation:
                    annotation = ast.unparse(arg.annotation)
                params.append({"name": arg.arg, "type": annotation})

            return_type = ""
            if node.returns:
                return_type = ast.unparse(node.returns)

            docstring = ast.get_docstring(node) or ""
            symbols.append({
                "name": node.name,
                "type": "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function",
                "line": node.lineno,
                "params": params,
                "return_type": return_type,
                "has_doc": bool(docstring),
                "doc_complete": _check_doc_completeness(docstring, params),
                "existing_doc": docstring[:200] if docstring else "",
            })
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            docstring = ast.get_docstring(node) or ""
            symbols.append({
                "name": node.name,
                "type": "class",
                "line": node.lineno,
                "params": [],
                "return_type": "",
                "has_doc": bool(docstring),
                "doc_complete": bool(docstring),
                "existing_doc": docstring[:200] if docstring else "",
            })

    return symbols


def _check_doc_completeness(docstring: str, params: list[dict]) -> bool:
    """Check if a docstring documents all parameters."""
    if not docstring:
        return False
    for p in params:
        name = p["name"]
        if name not in docstring:
            return False
    return True


def analyze_javascript(filepath: Path) -> list[dict]:
    """Analyze a JS/TS file for exported functions and JSDoc coverage."""
    text = filepath.read_text()
    symbols = []

    # Match function declarations and arrow functions
    patterns = [
        re.compile(r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)"),
        re.compile(r"(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*(?::\s*[\w<>,\s|]+)?\s*=>"),
    ]

    for pattern in patterns:
        for match in pattern.finditer(text):
            name = match.group(1)
            params_str = match.group(2)
            params = []
            if params_str.strip():
                for p in params_str.split(","):
                    p = p.strip()
                    if not p:
                        continue
                    parts = p.split(":")
                    params.append({
                        "name": parts[0].strip().rstrip("?"),
                        "type": parts[1].strip() if len(parts) > 1 else "",
                    })

            # Check for JSDoc before function
            start = match.start()
            before = text[:start].rstrip()
            has_jsdoc = before.endswith("*/") and "/**" in before[max(0, len(before) - 500):]

            symbols.append({
                "name": name,
                "type": "function",
                "line": text[:start].count("\n") + 1,
                "params": params,
                "return_type": "",
                "has_doc": has_jsdoc,
                "doc_complete": has_jsdoc,  # simplified
                "existing_doc": "",
            })

    return symbols


def analyze_file(filepath: Path) -> list[dict]:
    """Route to the appropriate analyzer based on file extension."""
    ext = filepath.suffix.lower()
    if ext == ".py":
        return analyze_python(filepath)
    elif ext in (".js", ".ts", ".jsx", ".tsx"):
        return analyze_javascript(filepath)
    return []


def analyze_path(path: str, recursive: bool = False) -> dict:
    """Analyze a file or directory."""
    p = Path(path)
    all_symbols: list[dict] = []
    files_analyzed = 0

    if p.is_file():
        symbols = analyze_file(p)
        all_symbols.extend({"file": str(p), **s} for s in symbols)
        files_analyzed = 1
    elif p.is_dir() and recursive:
        for ext in ("*.py", "*.js", "*.ts", "*.jsx", "*.tsx"):
            for fp in p.rglob(ext):
                if any(part.startswith(".") or part in ("node_modules", "vendor", "__pycache__", "dist", "build")
                       for part in fp.parts):
                    continue
                symbols = analyze_file(fp)
                all_symbols.extend({"file": str(fp), **s} for s in symbols)
                files_analyzed += 1

    documented = sum(1 for s in all_symbols if s["has_doc"])
    total = len(all_symbols)
    coverage = (documented / total * 100) if total else 100.0

    return {
        "files_analyzed": files_analyzed,
        "symbols": all_symbols,
        "coverage": {
            "documented": documented,
            "total": total,
            "percentage": round(coverage, 1),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="API documentation analyzer")
    parser.add_argument("--analyze", required=True, metavar="PATH",
                        help="File or directory to analyze")
    parser.add_argument("--recursive", action="store_true",
                        help="Recursively scan directories")
    args = parser.parse_args()

    result = analyze_path(args.analyze, args.recursive)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
'''

_API_DOC_GUIDE = """\
# API Documentation Format Guide

## Google-Style Python Docstrings (Recommended)

```python
def fetch_user(user_id: int, include_deleted: bool = False) -> User | None:
    \"\"\"Fetch a user by their database ID.

    Queries the users table and returns the matching record. Returns None
    if no user exists with the given ID. Soft-deleted users are excluded
    by default.

    Args:
        user_id: The primary key of the user to fetch.
        include_deleted: If True, include soft-deleted users in the lookup.
            Defaults to False.

    Returns:
        The User object if found, or None if no matching user exists.

    Raises:
        DatabaseConnectionError: If the database is unreachable.
        ValueError: If user_id is negative.

    Example:
        >>> user = fetch_user(42)
        >>> user.name
        'Alice'
    \"\"\"
```

### Rules
- First line: imperative summary under 79 chars
- Blank line between summary and description
- Args: one entry per parameter, indented 4 spaces under section header
- Returns: describe the return value and its type
- Raises: one entry per exception that can be raised
- Example: runnable doctest when practical

## Sphinx RST Style

```python
def fetch_user(user_id: int) -> User | None:
    \"\"\"Fetch a user by their database ID.

    :param user_id: The primary key of the user to fetch.
    :type user_id: int
    :returns: The User object if found, or None.
    :rtype: User | None
    :raises DatabaseConnectionError: If the database is unreachable.
    \"\"\"
```

## JSDoc / TSDoc

```typescript
/**
 * Fetch a user by their database ID.
 *
 * @param userId - The primary key of the user to fetch
 * @param includeDeleted - If true, include soft-deleted users
 * @returns The user object if found, or null
 * @throws {DatabaseError} If the database is unreachable
 *
 * @example
 * ```ts
 * const user = await fetchUser(42);
 * console.log(user.name); // 'Alice'
 * ```
 */
export async function fetchUser(
  userId: number,
  includeDeleted: boolean = false
): Promise<User | null> {
```

### Rules
- First line: imperative summary
- `@param name - description` for each parameter
- `@returns` for return value
- `@throws {ErrorType}` for errors
- `@example` with runnable code block

## Javadoc

```java
/**
 * Fetch a user by their database ID.
 *
 * <p>Queries the users table and returns the matching record.</p>
 *
 * @param userId the primary key of the user to fetch
 * @return the User object if found, or null
 * @throws DatabaseException if the database is unreachable
 */
public User fetchUser(int userId) throws DatabaseException {
```

## Coverage Standards

| Scope | Target Coverage |
|-------|----------------|
| Public API (exported) | 100% |
| Protected methods | 80%+ |
| Private/internal | Optional (but encouraged for complex logic) |
| Test files | Optional |

## Common Documentation Smells

- **Tautological**: `Returns the name` on `getName()` — describe edge cases instead
- **Stale params**: Docstring lists params that no longer exist
- **Missing errors**: Function throws but docs don't mention it
- **No examples**: Complex functions without usage examples
- **Copy-paste**: Same description on overloaded methods
"""

# ---------------------------------------------------------------------------
# BATCH2_SEEDS list
# ---------------------------------------------------------------------------
BATCH2_SEEDS: list[dict] = [
    # 6. dockerfile-optimizer
    {
        "id": "seed-dockerfile-optimizer",
        "slug": "dockerfile-optimizer",
        "title": "Dockerfile Optimizer",
        "category": "DevOps",
        "difficulty": "medium",
        "frontmatter": {
            "name": "dockerfile-optimizer",
            "description": (
                "Analyzes Dockerfiles for anti-patterns (root user, unpinned tags, poor layer order) "
                "and rewrites them. Use when user says optimize, lint, or fix Dockerfile, or says image "
                "is too big. NOT for writing Dockerfiles from scratch or Kubernetes."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="dockerfile-optimizer",
            title="Dockerfile Optimizer",
            description=(
                "Analyzes Dockerfiles for anti-patterns (root user, unpinned tags, poor layer order) "
                "and rewrites them. Use when user says optimize, lint, or fix Dockerfile, or says image "
                "is too big. NOT for writing Dockerfiles from scratch or Kubernetes."
            ),
            allowed_tools="Read Write Bash(docker * python *)",
            body=_DOCKERFILE_OPT_BODY,
        ),
        "supporting_files": {
            "scripts/validate.sh": _DOCKERFILE_OPT_VALIDATE,
            "scripts/main_helper.py": _DOCKERFILE_OPT_HELPER,
            "references/guide.md": _DOCKERFILE_OPT_GUIDE,
            "test_fixtures/Dockerfile.example": """\
# Anti-pattern example Dockerfile — intentionally contains common issues.
# Use this as test input for the Dockerfile optimizer skill.

FROM ubuntu:latest

RUN apt-get update
RUN apt-get install -y python3 python3-pip curl wget git openssh-client
RUN apt-get install -y nodejs npm

# Installing app dependencies (cache-bust on every code change)
COPY . /app
WORKDIR /app
RUN pip3 install -r requirements.txt
RUN npm install

# Build step
RUN npm run build

# Running as root (security anti-pattern)
EXPOSE 8080
CMD ["python3", "server.py"]

# Issues in this Dockerfile:
# 1. Unpinned base image (:latest) — builds are non-reproducible
# 2. No .dockerignore — COPY . sends .git, node_modules, etc. to context
# 3. Separate RUN for each apt-get — creates unnecessary layers
# 4. apt-get update and install in separate RUN — cache can serve stale index
# 5. No apt-get clean / rm -rf /var/lib/apt/lists/* — bloated image
# 6. COPY . before dependency install — cache-busts pip/npm on any code change
# 7. Running as root — no USER directive
# 8. No multi-stage build — build tools and source stay in final image
# 9. No HEALTHCHECK defined
# 10. No specific Python/Node version pinning
""",
            "references/best-practices.md": """\
# Dockerfile Best Practices Checklist

Quick reference for optimizing Dockerfiles. Each item includes the
anti-pattern it prevents and the fix.

---

## Base Image

- [ ] **Pin the base image digest or version tag** — never use `:latest`
  - Bad:  `FROM python:latest`
  - Good: `FROM python:3.12-slim@sha256:abc123...`
- [ ] **Use minimal base images** — `slim`, `alpine`, or `distroless`
  - `python:3.12` is ~1 GB; `python:3.12-slim` is ~150 MB

## Layer Optimization

- [ ] **Combine related RUN commands** with `&&` and `\\`
  ```dockerfile
  RUN apt-get update && \\
      apt-get install -y --no-install-recommends pkg1 pkg2 && \\
      rm -rf /var/lib/apt/lists/*
  ```
- [ ] **Order layers by change frequency** — least-changing first
  1. System dependencies (rarely change)
  2. Language dependencies (change with lockfile)
  3. Application code (changes every commit)
- [ ] **Copy dependency manifests before source code**
  ```dockerfile
  COPY requirements.txt .
  RUN pip install -r requirements.txt
  COPY . .
  ```

## Security

- [ ] **Run as non-root user**
  ```dockerfile
  RUN addgroup --system app && adduser --system --ingroup app app
  USER app
  ```
- [ ] **No secrets in the image** — use build secrets or runtime env vars
  ```dockerfile
  RUN --mount=type=secret,id=api_key cat /run/secrets/api_key
  ```
- [ ] **Scan the image** — `docker scout cves`, `trivy`, or `grype`
- [ ] **Drop all capabilities** unless specifically needed

## Multi-Stage Builds

- [ ] **Separate build and runtime stages**
  ```dockerfile
  FROM node:20-slim AS build
  WORKDIR /app
  COPY package*.json .
  RUN npm ci
  COPY . .
  RUN npm run build

  FROM node:20-slim AS runtime
  WORKDIR /app
  COPY --from=build /app/dist ./dist
  COPY --from=build /app/node_modules ./node_modules
  USER node
  EXPOSE 3000
  CMD ["node", "dist/server.js"]
  ```

## Metadata & Health

- [ ] **Add HEALTHCHECK**
  ```dockerfile
  HEALTHCHECK --interval=30s --timeout=5s --retries=3 \\
    CMD curl -f http://localhost:8080/health || exit 1
  ```
- [ ] **Add LABEL metadata** — maintainer, version, description
- [ ] **Use .dockerignore** — exclude `.git`, `node_modules`, `__pycache__`, `.env`

## Reproducibility

- [ ] **Pin all package versions** in `apt-get install`, `pip install`, `npm ci`
- [ ] **Use `COPY --link`** (BuildKit) to improve cache reuse
- [ ] **Set `ENV PYTHONDONTWRITEBYTECODE=1`** for Python images
- [ ] **Set `ENV NODE_ENV=production`** for Node images
""",
        },
        "traits": [
            "anti-pattern-detection",
            "score-before-fix",
            "multi-stage-conversion",
            "security-hardening",
        ],
        "meta_strategy": "Parse first, score second, rewrite third. Fix anti-patterns in priority order: security > cache efficiency > image size. Always validate the rewrite.",
    },
    # 7. ci-cd-pipeline
    {
        "id": "seed-ci-cd-pipeline",
        "slug": "ci-cd-pipeline",
        "title": "CI/CD Pipeline Generator",
        "category": "DevOps",
        "difficulty": "hard",
        "frontmatter": {
            "name": "ci-cd-pipeline",
            "description": (
                "Generates GitHub Actions CI/CD workflows with SHA-pinned actions, least-privilege "
                "permissions, caching, and matrix builds. Use when user says CI, pipeline, GitHub Actions, "
                "or automate builds. NOT for Jenkins, GitLab CI, or CircleCI."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="ci-cd-pipeline",
            title="CI/CD Pipeline Generator",
            description=(
                "Generates GitHub Actions CI/CD workflows with SHA-pinned actions, least-privilege "
                "permissions, caching, and matrix builds. Use when user says CI, pipeline, GitHub Actions, "
                "or automate builds. NOT for Jenkins, GitLab CI, or CircleCI."
            ),
            allowed_tools="Read Write Bash(gh * python *)",
            body=_CICD_BODY,
        ),
        "supporting_files": {
            "scripts/validate.sh": _CICD_VALIDATE,
            "scripts/main_helper.py": _CICD_HELPER,
            "references/guide.md": _CICD_GUIDE,
            "assets/workflow-template.yml": """\
# GitHub Actions CI/CD Workflow Template
# Best practices: SHA-pinned actions, least-privilege permissions,
# dependency caching, matrix strategy, and concurrency control.

name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

# Cancel in-flight runs for the same branch/PR
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

# Least-privilege: only grant what's needed
permissions:
  contents: read

jobs:
  lint:
    name: Lint
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      # SHA-pinned checkout (never use @v4 tag — pin the commit SHA)
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2

      - uses: actions/setup-node@39370e3970a6d050c480ffad4ff0ed4d3fdee5af # v4.1.0
        with:
          node-version-file: '.nvmrc'
          cache: 'npm'

      - run: npm ci
      - run: npm run lint

  test:
    name: Test (${{ matrix.os }} / Node ${{ matrix.node-version }})
    runs-on: ${{ matrix.os }}
    timeout-minutes: 15
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest]
        node-version: ['18', '20', '22']
        include:
          - os: macos-latest
            node-version: '20'
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2

      - uses: actions/setup-node@39370e3970a6d050c480ffad4ff0ed4d3fdee5af # v4.1.0
        with:
          node-version: ${{ matrix.node-version }}
          cache: 'npm'

      - run: npm ci
      - run: npm test

      # Upload coverage only from the primary matrix entry
      - if: matrix.os == 'ubuntu-latest' && matrix.node-version == '20'
        uses: actions/upload-artifact@b4b15b8c7c6ac21ea08fcf65892d2ee8f75cf882 # v4.4.3
        with:
          name: coverage
          path: coverage/
          retention-days: 7

  build:
    name: Build
    runs-on: ubuntu-latest
    timeout-minutes: 10
    needs: [lint, test]
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2

      - uses: actions/setup-node@39370e3970a6d050c480ffad4ff0ed4d3fdee5af # v4.1.0
        with:
          node-version-file: '.nvmrc'
          cache: 'npm'

      - run: npm ci
      - run: npm run build

      - uses: actions/upload-artifact@b4b15b8c7c6ac21ea08fcf65892d2ee8f75cf882 # v4.4.3
        with:
          name: build-output
          path: dist/
          retention-days: 14

# --- Template Notes ---
# 1. SHA pins: Use `gh api repos/OWNER/REPO/git/ref/tags/vX.Y.Z` to resolve
#    tag -> commit SHA. Add a trailing comment with the human-readable tag.
# 2. Caching: `setup-node` with `cache: 'npm'` handles node_modules caching.
#    For pip, use `actions/setup-python` with `cache: 'pip'`.
# 3. Matrix: `fail-fast: false` ensures all combinations run even if one fails.
# 4. Permissions: Start with `contents: read` and add only what each job needs.
#    For deployments, add `deployments: write`. For PR comments, `pull-requests: write`.
# 5. Timeouts: Always set `timeout-minutes` to prevent runaway jobs.
# 6. Concurrency: `cancel-in-progress` saves CI minutes on rapid pushes.
""",
        },
        "traits": [
            "sha-pinned-actions",
            "least-privilege-permissions",
            "project-type-detection",
            "matrix-strategy",
        ],
        "meta_strategy": "Detect project type from manifests, generate with security defaults (SHA pins, least privilege), validate YAML before presenting. Never use @tag references.",
    },
    # 8. dependency-auditor
    {
        "id": "seed-dependency-auditor",
        "slug": "dependency-auditor",
        "title": "Dependency Auditor",
        "category": "Security",
        "difficulty": "easy",
        "frontmatter": {
            "name": "dependency-auditor",
            "description": (
                "Audits project dependencies for known vulnerabilities across npm, pip, Cargo, and Go. "
                "Use when user says audit, vulnerability scan, CVE, supply chain, or npm audit. "
                "NOT for source code SAST, container scanning, or runtime security."
            ),
            "allowed-tools": ["Read", "Bash"],
        },
        "skill_md_content": _build(
            name="dependency-auditor",
            title="Dependency Auditor",
            description=(
                "Audits project dependencies for known vulnerabilities across npm, pip, Cargo, and Go. "
                "Use when user says audit, vulnerability scan, CVE, supply chain, or npm audit. "
                "NOT for source code SAST, container scanning, or runtime security."
            ),
            allowed_tools="Read Bash(npm * pip-audit * cargo * go *)",
            body=_DEP_AUDIT_BODY,
        ),
        "supporting_files": {
            "scripts/validate.sh": _DEP_AUDIT_VALIDATE,
            "scripts/main_helper.py": _DEP_AUDIT_HELPER,
            "references/guide.md": _DEP_AUDIT_GUIDE,
        },
        "traits": [
            "multi-ecosystem",
            "unified-report-format",
            "severity-prioritization",
            "remediation-advice",
        ],
        "meta_strategy": "Auto-detect ecosystem from lockfiles, run native audit tools, normalize into unified JSON with severity counts, and always suggest the minimal upgrade path.",
    },
    # 9. secret-scanner
    {
        "id": "seed-secret-scanner",
        "slug": "secret-scanner",
        "title": "Secret Scanner",
        "category": "Security",
        "difficulty": "easy",
        "frontmatter": {
            "name": "secret-scanner",
            "description": (
                "Scans codebases for hardcoded secrets (API keys, tokens, passwords, connection strings) "
                "using 30+ regex patterns with false-positive filtering. Use when user says scan for secrets "
                "or find leaked keys. NOT for secret management or encryption."
            ),
            "allowed-tools": ["Read", "Bash"],
        },
        "skill_md_content": _build(
            name="secret-scanner",
            title="Secret Scanner",
            description=(
                "Scans codebases for hardcoded secrets (API keys, tokens, passwords, connection strings) "
                "using 30+ regex patterns with false-positive filtering. Use when user says scan for secrets "
                "or find leaked keys. NOT for secret management or encryption."
            ),
            allowed_tools="Read Bash(python * git *)",
            body=_SECRET_SCANNER_BODY,
        ),
        "supporting_files": {
            "scripts/validate.sh": _SECRET_SCANNER_VALIDATE,
            "scripts/main_helper.py": _SECRET_SCANNER_HELPER,
            "references/guide.md": _SECRET_SCANNER_GUIDE,
            "references/patterns.md": """\
# Secret Patterns by Provider

Regex patterns for detecting hardcoded secrets. Each entry includes the
provider, pattern name, regex, and example of what it matches.

Use these patterns for scanning; apply false-positive filtering after
initial matches (test files, example values, placeholders).

---

## AWS

| Secret Type | Regex | Example Match |
|---|---|---|
| Access Key ID | `AKIA[0-9A-Z]{16}` | `AKIAIOSFODNN7EXAMPLE` |
| Secret Access Key | `(?i)aws_secret_access_key\\s*[=:]\\s*[A-Za-z0-9/+=]{40}` | 40-char base64 string |
| Session Token | `(?i)aws_session_token\\s*[=:]\\s*[A-Za-z0-9/+=]{100,}` | Long base64 token |
| MWS Auth Token | `amzn\\.mws\\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}` | `amzn.mws.abcd1234-...` |

## GCP / Google

| Secret Type | Regex | Example Match |
|---|---|---|
| Service Account Key | `"type"\\s*:\\s*"service_account"` | JSON key file indicator |
| API Key | `AIza[0-9A-Za-z_-]{35}` | `AIzaSyA1b2c3d4e5f6g7h8i9j0...` |
| OAuth Client Secret | `(?i)client_secret\\s*[=:]\\s*[A-Za-z0-9_-]{24,}` | OAuth secret value |

## GitHub

| Secret Type | Regex | Example Match |
|---|---|---|
| Personal Access Token (classic) | `ghp_[A-Za-z0-9]{36}` | `ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345` |
| Fine-grained PAT | `github_pat_[A-Za-z0-9]{22}_[A-Za-z0-9]{59}` | Long prefixed token |
| OAuth Access Token | `gho_[A-Za-z0-9]{36}` | `gho_...` |
| App Installation Token | `ghs_[A-Za-z0-9]{36}` | `ghs_...` |
| App Refresh Token | `ghr_[A-Za-z0-9]{36}` | `ghr_...` |

## Stripe

| Secret Type | Regex | Example Match |
|---|---|---|
| Secret Key (live) | `sk_live_[A-Za-z0-9]{24,}` | `sk_live_EXAMPLE_NOT_A_REAL_KEY` |
| Secret Key (test) | `sk_test_[A-Za-z0-9]{24,}` | `sk_test_...` |
| Restricted Key | `rk_live_[A-Za-z0-9]{24,}` | `rk_live_...` |
| Webhook Secret | `whsec_[A-Za-z0-9]{32,}` | `whsec_...` |

## Slack

| Secret Type | Regex | Example Match |
|---|---|---|
| Bot Token | `xoxb-[0-9]{10,}-[0-9]{10,}-[A-Za-z0-9]{24}` | `xoxb-123456789012-...` |
| User Token | `xoxp-[0-9]{10,}-[0-9]{10,}-[A-Za-z0-9]{24,}` | `xoxp-...` |
| Webhook URL | `https://hooks\\.slack\\.com/services/T[A-Z0-9]{8,}/B[A-Z0-9]{8,}/[A-Za-z0-9]{24}` | Full webhook URL |

## Generic / Multi-Provider

| Secret Type | Regex | Example Match |
|---|---|---|
| Private Key (PEM) | `-----BEGIN (RSA\\|EC\\|OPENSSH) PRIVATE KEY-----` | PEM header |
| JWT | `eyJ[A-Za-z0-9_-]{10,}\\.eyJ[A-Za-z0-9_-]{10,}\\.[A-Za-z0-9_-]{10,}` | `eyJhbGci...` |
| Basic Auth in URL | `https?://[^:]+:[^@]+@` | `https://user:pass@host` |
| Connection String | `(?i)(mongodb\\+srv\\|postgres\\|mysql\\|redis)://[^\\s]+:[^\\s]+@` | DB URL with credentials |
| Password Assignment | `(?i)(password\\|passwd\\|pwd)\\s*[=:]\\s*['\"][^'\"]{8,}['\"]` | `password = "hunter2"` |
| Bearer Token | `(?i)bearer\\s+[A-Za-z0-9_\\-.]{20,}` | `Bearer eyJhbGci...` |

## Twilio

| Secret Type | Regex | Example Match |
|---|---|---|
| Account SID | `AC[0-9a-f]{32}` | `AC00000000000000000000000000000000` |
| Auth Token | `(?i)twilio.*[=:]\\s*[0-9a-f]{32}` | 32-char hex string |

## SendGrid

| Secret Type | Regex | Example Match |
|---|---|---|
| API Key | `SG\\.[A-Za-z0-9_-]{22}\\.[A-Za-z0-9_-]{43}` | `SG.abc123...xyz789` |

---

## False-Positive Indicators

Skip matches that contain any of these signals:
- Inside a file path matching `test/`, `spec/`, `fixture/`, `mock/`
- Value is a well-known placeholder: `EXAMPLE`, `xxx`, `changeme`, `TODO`
- Value matches `\\$\\{.*\\}` (environment variable interpolation)
- Value is all one repeated character (e.g., `AAAAAAA`)
- Line contains `# noqa: secret` or `# nosec`
- File is a lockfile (`package-lock.json`, `Cargo.lock`, etc.)

## Confidence Scoring

| Confidence | Criteria |
|---|---|
| **High** | Provider-specific prefix + correct length + not in test file |
| **Medium** | Generic pattern match + not a placeholder |
| **Low** | Password-like assignment but could be a variable name |
""",
        },
        "traits": [
            "pattern-based-detection",
            "false-positive-filtering",
            "confidence-scoring",
            "remediation-playbook",
        ],
        "meta_strategy": "Scan with high-specificity patterns first, apply false-positive heuristics, classify by confidence, and always recommend rotating credentials before removing from code.",
    },
    # 10. api-doc-generator
    {
        "id": "seed-api-doc-generator",
        "slug": "api-doc-generator",
        "title": "API Documentation Generator",
        "category": "Documentation",
        "difficulty": "easy",
        "frontmatter": {
            "name": "api-doc-generator",
            "description": (
                "Generates and validates API documentation (Google-style, JSDoc, Sphinx) from source code. "
                "Use when user says docstring, JSDoc, document my code, or add docs. "
                "NOT for READMEs, user guides, or architecture docs."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="api-doc-generator",
            title="API Documentation Generator",
            description=(
                "Generates and validates API documentation (Google-style, JSDoc, Sphinx) from source code. "
                "Use when user says docstring, JSDoc, document my code, or add docs. "
                "NOT for READMEs, user guides, or architecture docs."
            ),
            allowed_tools="Read Write Bash(python *)",
            body=_API_DOC_BODY,
        ),
        "supporting_files": {
            "scripts/validate.sh": _API_DOC_VALIDATE,
            "scripts/main_helper.py": _API_DOC_HELPER,
            "references/guide.md": _API_DOC_GUIDE,
        },
        "traits": [
            "multi-format",
            "coverage-measurement",
            "signature-parsing",
            "incremental-completion",
        ],
        "meta_strategy": "Parse AST to extract symbols, detect the existing doc style (or default to Google for Python / JSDoc for TS), generate only what's missing, and validate that all params are covered.",
    },
]

__all__ = ["BATCH2_SEEDS"]
