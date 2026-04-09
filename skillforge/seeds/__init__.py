"""Curated Gen 0 Skill library.

These seeds are loaded into the Registry as gen-0 SkillGenomes users can
browse, export, or fork-and-evolve. Every seed follows the bible patterns
(P-DESC, P-INST, P-STRUCT, P-SCRIPT, P-DISC) and is production-quality
out of the box.

Each entry is a dict compatible with ``SkillGenome`` construction. The
``skill_md_content`` field contains the FULL SKILL.md (YAML frontmatter +
body). Descriptions are hand-counted to stay under the 250-character cap.
Each skill ships with exactly 2-3 diverse I/O examples (P-INST-002).
"""
from __future__ import annotations

from textwrap import dedent


def _build(
    *,
    name: str,
    title: str,
    description: str,
    allowed_tools: str,
    body: str,
) -> str:
    """Assemble a SKILL.md from its parts. Strips leading whitespace on body."""
    assert len(description) <= 250, f"{name}: description {len(description)} > 250"
    return (
        "---\n"
        f"name: {name}\n"
        "description: >-\n"
        + "".join(f"  {line}\n" for line in description.strip().split("\n"))
        + f"allowed-tools: {allowed_tools}\n"
        "---\n\n"
        f"# {title}\n\n"
        + dedent(body).strip()
        + "\n"
    )


# ---------------------------------------------------------------------------
# 1. Pandas DataFrame Cleaning
# ---------------------------------------------------------------------------
_PANDAS_CLEANING_BODY = """
## Quick Start
Classify the dirty DataFrame first (types, nulls, duplicates, outliers), then apply a deterministic cleaning pipeline. Never mutate the caller's DataFrame — return a cleaned copy plus a report of what changed.

## When to use this skill
Use when the user says "clean", "tidy", "normalize", "fix", "wrangle", or "preprocess" in the same breath as "DataFrame", "CSV", "pandas", "dataset", or a `.csv`/`.parquet` filename. Also triggers on "there are nulls in my data" or "dedupe this".

## Workflow

### Step 1: Profile before touching
Run `df.info()`, `df.describe(include="all")`, `df.isna().sum()`, and `df.duplicated().sum()`. Print the shape, dtypes, null counts, and duplicate count. Do not proceed until you have named each problem column.

### Step 2: Pick a strategy per column
For each problem column, classify it:
- Numeric with nulls -> median fill (or `interpolate` for time series)
- Categorical with nulls -> explicit `"Unknown"` category, never silent drop
- Dates stored as strings -> `pd.to_datetime(..., errors="coerce", utc=True)`
- Mixed-type object columns -> coerce with `errors="coerce"` then report the coerce count

### Step 3: Apply the pipeline
Compose operations as a chain on a copy:
```python
cleaned = (
    df.copy()
      .drop_duplicates()
      .assign(**{col: ... for col in problem_cols})
      .reset_index(drop=True)
)
```
Do NOT use `inplace=True` — it is deprecated in pandas 3.x and it hides provenance.

### Step 4: Verify and report
Re-run the profile from Step 1 on `cleaned`. Diff the before/after counts. Emit a short markdown report: rows dropped, nulls filled per column, dtype coercions, row/column deltas.

## Examples

**Example 1 — Sales CSV with mixed types**
Input: "clean up sales.csv, the revenue column is sometimes a string and there are blank rows"
Output: Profiles the file, reports 3,412 rows / 12 cols / 87 blank rows / `revenue` dtype=object. Drops blank rows, coerces `revenue` with `pd.to_numeric(errors="coerce")`, median-fills the resulting NaNs, and returns `cleaned_sales.csv` plus a report showing "dropped 87 duplicate rows, coerced 14 non-numeric revenue values to median $412.00".

**Example 2 — Time series with gaps**
Input: "my sensor data has missing timestamps and some nulls in temperature"
Output: Parses timestamp column with `pd.to_datetime(..., utc=True)`, sets as index, resamples to the detected frequency, forward-fills temperature for gaps under 5 minutes and flags longer gaps as `NaN` with an `is_imputed` boolean column.

**Example 3 — Deduplication with fuzzy keys**
Input: "dedupe this customer list but 'Acme Inc.' and 'ACME INC' should be the same"
Output: Normalizes the join key (lowercase, strip, collapse whitespace, drop trailing punctuation) into a temporary `_norm_name` column, drops duplicates on it, drops the helper column, reports the merge count.

## Common mistakes to avoid
- Using `inplace=True` — deprecated and hides what changed
- Dropping nulls without first checking if the column is recoverable
- Calling `astype(int)` on a column that still has NaNs (raises) instead of `.astype("Int64")` (nullable)
- Reporting "cleaned" without a before/after diff — users cannot trust invisible changes
"""

# ---------------------------------------------------------------------------
# 2. SQL Query Optimization
# ---------------------------------------------------------------------------
_SQL_OPT_BODY = """
## Quick Start
Read the query, read the EXPLAIN plan, identify the bottleneck (seq scan? nested loop? bad cardinality estimate?), and rewrite against the bottleneck. Never "optimize" without a plan to diff against.

## When to use this skill
Use when the user says "slow query", "optimize", "speed up", "EXPLAIN", "query plan", "index", "n+1", or pastes a SELECT/JOIN and complains about latency. Triggers on Postgres, MySQL, SQLite, and standard ANSI SQL.

## Workflow

### Step 1: Capture the baseline plan
Ask for or generate `EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)` on Postgres, `EXPLAIN ANALYZE` on MySQL 8+, or `EXPLAIN QUERY PLAN` on SQLite. Record actual row counts, buffer hits, and total execution time. Without a real plan, stop and ask.

### Step 2: Classify the bottleneck
Walk the plan top-down and identify the single most expensive node:
- **Sequential Scan on a large table** -> missing index on the filter/join column
- **Nested Loop with high outer rows** -> should be Hash Join; bad row estimate
- **Sort with external merge disk** -> `work_mem` too low or avoidable sort
- **Rows Removed by Filter >> Rows Returned** -> predicate not sargable
- **Index Scan but still slow** -> low selectivity; consider partial or covering index

### Step 3: Apply the smallest fix that addresses the bottleneck
Prefer in this order:
1. Rewrite the predicate to be sargable (move functions off the indexed column)
2. Add a covering or partial index
3. Rewrite correlated subqueries as JOINs or lateral joins
4. Add `ANALYZE` to refresh statistics
5. Only then consider denormalization or materialized views

### Step 4: Re-run EXPLAIN ANALYZE and diff
Show the user the before/after plan, the before/after time, and which change produced the win. If the change did not help, revert it and try the next candidate.

## Examples

**Example 1 — Seq scan on a filtered column**
Input: "this query takes 8 seconds, can you speed it up? `SELECT * FROM orders WHERE customer_id = 42 AND status = 'shipped'`"
Output: EXPLAIN shows Seq Scan on orders (1.2M rows). Recommends `CREATE INDEX CONCURRENTLY orders_customer_status_idx ON orders (customer_id, status) WHERE status = 'shipped';` (partial index on the hot path). Re-run shows Index Scan, 12ms.

**Example 2 — Non-sargable predicate**
Input: "why is `WHERE DATE(created_at) = '2024-01-15'` slow even though created_at is indexed?"
Output: The function wrapping `created_at` disables the index. Rewrite as `WHERE created_at >= '2024-01-15' AND created_at < '2024-01-16'`. Same result, uses the index, ~200x faster on the sample table.

**Example 3 — N+1 disguised as a subquery**
Input: "slow report query with a correlated subquery per row"
Output: Rewrites the correlated `SELECT (...)` into a LATERAL join or a window function aggregated in a single pass. Shows the plan changing from Nested Loop (outer 50k) to Hash Aggregate, cutting runtime from 14s to 180ms.

## Common mistakes to avoid
- Adding indexes without running EXPLAIN first — you may index the wrong column
- `SELECT *` in OLTP — forces extra I/O and defeats covering indexes
- Ignoring `rows=` estimate vs `actual rows=` mismatches, which signal stale statistics
- Adding hints before fixing the actual plan problem
"""

# ---------------------------------------------------------------------------
# 3. React Component Refactoring
# ---------------------------------------------------------------------------
_REACT_REFACTOR_BODY = """
## Quick Start
Identify the code smell (god component, prop drilling, inline handlers re-rendering, derived state), pick the matching refactor (extract, lift, memoize, derive), and preserve behavior. Run the tests after every step.

## When to use this skill
Use when the user says "refactor", "split", "extract", "clean up", "this component is too big", "prop drilling", "re-renders", or "unreadable" alongside `.jsx`, `.tsx`, React, or a component name. Also fires on "why is this slow" for React files.

## Workflow

### Step 1: Inventory the smells
Read the component top to bottom. Tag every issue:
- Line count > 200 or > 5 `useState` calls -> God Component
- Same prop threaded through 3+ levels -> Prop Drilling
- New object/array/function passed as a prop on every render -> Referential Churn
- `useState` holding a value derivable from props -> Derived State Anti-pattern
- JSX > 80 lines inside `return` -> Extract Subcomponents

### Step 2: Refactor in small, reversible steps
One smell per commit. Order by dependency: extract subcomponents first, then lift or colocate state, then memoize the hot path. Never combine a behavior change with a refactor.

### Step 3: Preserve the public API
The component's props, imports, and rendered output must not change. If the tests pass before and after with zero edits, the refactor is correct.

### Step 4: Verify
Run `npm test` (or `vitest`). If there are no tests, write a snapshot test for the component BEFORE refactoring. Run the linter and type-checker. Compare the rendered DOM with the browser devtools component inspector if possible.

## Examples

**Example 1 — God component split**
Input: "UserDashboard.tsx is 600 lines, can you clean it up?"
Output: Extracts `<UserHeader>`, `<UserStats>`, `<UserActivityFeed>`, and `<UserSettingsPanel>` as sibling files. Moves each useState block to the component that owns it. `UserDashboard.tsx` shrinks to 60 lines of layout. Tests pass unchanged.

**Example 2 — Referential churn causing re-renders**
Input: "my memoized child keeps re-rendering even though props look the same"
Output: Locates the inline `style={{...}}` or `onClick={() => ...}` in the parent. Moves the style object to a module const and wraps the handler in `useCallback` with the correct dependency array. The memoized child stops re-rendering.

**Example 3 — Derived state cleanup**
Input: "this form has `useState` for fullName but it's just firstName + lastName"
Output: Deletes the `fullName` state and the `useEffect` that syncs it. Replaces with a derived `const fullName = \\`${firstName} ${lastName}\\`;`. Removes a whole class of stale-state bugs.

## Common mistakes to avoid
- Refactoring without tests — you cannot prove behavior preservation
- Premature `useMemo` / `useCallback` — only memoize after profiling shows a win
- Mixing a refactor with a bug fix in the same commit
- Extracting components that are only used once with no state (just use a local render function)
"""

# ---------------------------------------------------------------------------
# 4. Next.js App Router Migration
# ---------------------------------------------------------------------------
_NEXT_MIGRATION_BODY = """
## Quick Start
Migrate route-by-route, not all at once. Next.js supports `pages/` and `app/` side-by-side — exploit that. For each route: choose server vs client, translate data fetching, rewrite the layout, verify, then delete the old `pages/` file.

## When to use this skill
Use when the user mentions "Next.js", "app router", "pages router", "migrate", "getServerSideProps", "getStaticProps", or "_app.tsx" in a migration context. Triggers on Next 12/13 -> 13/14/15 upgrades.

## Workflow

### Step 1: Audit the pages/ tree
List every file in `pages/`. Classify each:
- Uses `getServerSideProps` -> Server Component with async function body
- Uses `getStaticProps` + `getStaticPaths` -> Server Component with `generateStaticParams`
- Uses `useEffect` + `fetch` for data -> Server Component (move the fetch server-side)
- Uses browser APIs, `useState`, or event handlers -> Client Component (`"use client"`)
- API route (`pages/api/*`) -> move to `app/api/*/route.ts` as a Route Handler

### Step 2: Set up app/ alongside pages/
Create `app/layout.tsx` (required root layout) and `app/page.tsx` for `/`. Copy global CSS imports from `pages/_app.tsx` into the root layout. Both routers can coexist; Next resolves `app/` first when a route collides.

### Step 3: Migrate one route at a time
For each page, in order from least to most complex:
1. Create `app/<route>/page.tsx`
2. Translate data fetching to a top-level `async` function call in the Server Component
3. Mark interactive leaves with `"use client"` — not the whole tree
4. Replace `useRouter` from `next/router` with `useRouter` from `next/navigation` (different API!)
5. Replace `next/head` with the `metadata` export or `generateMetadata`
6. Delete the old `pages/<route>.tsx`
7. Run `npm run build` and smoke-test the route

### Step 4: Migrate API routes
`pages/api/foo.ts` with `export default function handler(req, res)` becomes `app/api/foo/route.ts` with named exports `export async function GET(request: Request)`. Read the Next.js 15 async API notes: `cookies()`, `headers()`, `params`, and `searchParams` are now async and must be awaited.

## Examples

**Example 1 — Simple SSR page**
Input: "migrate pages/products/[id].tsx, it uses getServerSideProps to fetch a product"
Output: Creates `app/products/[id]/page.tsx` as `export default async function Page({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; const product = await getProduct(id); return <ProductView product={product} />; }`. Notes the `params` is now a Promise in Next 15.

**Example 2 — Interactive form with useState**
Input: "migrate the /checkout page, it has a form with lots of state and client-side validation"
Output: Splits into `app/checkout/page.tsx` (server, fetches initial cart) and `app/checkout/CheckoutForm.tsx` with `"use client"` at the top (the interactive form). Server passes initial data as props.

**Example 3 — API route with cookies**
Input: "move pages/api/session.ts to the app router"
Output: Creates `app/api/session/route.ts` with `export async function GET() { const cookieStore = await cookies(); const session = cookieStore.get("session"); return Response.json({ session }); }`. Awaits `cookies()` per Next 15.

## Common mistakes to avoid
- Marking the entire tree `"use client"` — defeats the purpose of Server Components
- Importing `useRouter` from `next/router` inside `app/` — it's `next/navigation` there, with a different API
- Forgetting to `await` `params`, `searchParams`, `cookies()`, and `headers()` in Next 15+
- Deleting `pages/` wholesale before verifying every route works in `app/`
"""

# ---------------------------------------------------------------------------
# 5. FastAPI Endpoint Authoring
# ---------------------------------------------------------------------------
_FASTAPI_BODY = """
## Quick Start
Define the Pydantic request and response models first, then the handler, then the tests. Use dependency injection for auth and DB sessions. Never put business logic inside the route function — delegate to a service.

## When to use this skill
Use when the user mentions "FastAPI", "endpoint", "route", "API", "Pydantic", "POST /", or asks for a Python HTTP handler. Also triggers on "expose this as an API" for Python code.

## Workflow

### Step 1: Model the contract
Create `RequestModel` and `ResponseModel` as Pydantic `BaseModel` classes with explicit types, `Field(..., description=...)`, and validators. These are the contract — they drive the OpenAPI docs.

### Step 2: Write the route signature
```python
@router.post("/items", response_model=ItemResponse, status_code=201)
async def create_item(
    body: ItemCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> ItemResponse:
    ...
```
Always declare `response_model` and `status_code` explicitly. Use `Annotated[..., Depends(...)]`, not the old bare `Depends()` default.

### Step 3: Delegate to a service
The route function should be 3-8 lines: validate (Pydantic already did), call a service function, map the result to the response model, return. Business logic lives in `services/`, not in the route.

### Step 4: Handle errors deliberately
Raise `HTTPException(status_code=..., detail=...)` for client errors. Let unexpected exceptions bubble so the global exception handler logs them and returns 500. Never `except Exception: pass`.

### Step 5: Test with TestClient
Write tests using `httpx.AsyncClient` with `ASGITransport`. Cover: happy path, validation failure (422), auth failure (401), and any domain-specific error.

## Examples

**Example 1 — Create endpoint**
Input: "add a POST /todos endpoint that creates a todo and returns it"
Output: Creates `ItemCreate(title: str, done: bool = False)` and `Item(id: int, title: str, done: bool)` models, a `create_todo` service, and the route. Tests cover 201 success, 422 on missing title, and 401 when the auth header is absent.

**Example 2 — Paginated list**
Input: "GET /users that takes ?page=1&size=20"
Output: Declares `page: int = Query(1, ge=1)` and `size: int = Query(20, ge=1, le=100)`. Returns a `PaginatedResponse[User]` with `items`, `total`, `page`, `size`. Service does a single `SELECT COUNT(*)` + windowed query.

**Example 3 — File upload with auth**
Input: "endpoint to upload a CSV, only admins"
Output: `file: UploadFile` param, `Depends(require_admin)` dependency, streams the file to the service without loading it all into memory, returns `{ "rows_ingested": N }`. Tests assert 403 for non-admin.

## Common mistakes to avoid
- Putting SQL or business logic inside the route function — makes it untestable
- Forgetting `response_model=` — leaks internal fields into the API response
- Using sync `def` with async DB sessions — blocks the event loop
- Swallowing exceptions with bare `except:` — you will never debug it
"""

# ---------------------------------------------------------------------------
# 6. Dockerfile Authoring
# ---------------------------------------------------------------------------
_DOCKERFILE_BODY = """
## Quick Start
Multi-stage build. Pin base image to a digest or specific tag. Non-root user. Copy dependency manifests before source to maximize layer caching. Add a HEALTHCHECK. `.dockerignore` is not optional.

## When to use this skill
Use when the user says "Dockerfile", "containerize", "docker build", "image", "dockerize", or pastes an existing Dockerfile and asks for improvements. Triggers on any language runtime + "ship as a container".

## Workflow

### Step 1: Pick a minimal base
Prefer `-slim` or `-alpine` variants over full distros. Pin the tag: `python:3.12-slim-bookworm`, not `python:latest`. For production, pin the digest (`@sha256:...`) so rebuilds are reproducible.

### Step 2: Structure as multi-stage
Stage 1 (`builder`): install build tools, compile dependencies.
Stage 2 (`runtime`): copy only the built artifacts from the builder. The runtime stage must have zero build tools.

### Step 3: Order layers by change frequency
Copy dependency manifests (`requirements.txt`, `package.json`, `go.mod`) and install dependencies BEFORE copying source code. Source changes every commit; dependencies rarely do. This is the single biggest cache win.

### Step 4: Run as non-root
```dockerfile
RUN useradd --create-home --shell /bin/bash app
USER app
WORKDIR /home/app
```
Never `USER root` at runtime. Never `chmod 777`.

### Step 5: Add HEALTHCHECK and EXPOSE
```dockerfile
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \\
  CMD curl -fsS http://localhost:8000/health || exit 1
```

### Step 6: Write a .dockerignore
At minimum: `.git`, `node_modules`, `__pycache__`, `.venv`, `.env`, `dist`, `build`, `*.log`, `.DS_Store`. Without it, your build context balloons and secrets leak into layers.

## Examples

**Example 1 — Python FastAPI app**
Input: "containerize my FastAPI app that uses uv"
Output: Two-stage Dockerfile. Builder runs `uv sync --frozen --no-dev` against a copied `pyproject.toml` + `uv.lock`. Runtime copies `/app/.venv` and the source, runs as non-root `app`, exposes 8000, HEALTHCHECK on `/health`, `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`.

**Example 2 — Node + Next.js standalone**
Input: "Dockerfile for my Next.js app, keep the image small"
Output: Uses `node:20-alpine`. Builder runs `npm ci` then `npm run build`. Runtime copies `.next/standalone` and `.next/static` only, not `node_modules`. Final image ~150MB vs ~1.2GB naive.

**Example 3 — Go binary**
Input: "Dockerfile for my Go service"
Output: Builder stage `golang:1.22-alpine` with `CGO_ENABLED=0 go build -ldflags='-s -w' -o /out/server`. Runtime stage `FROM gcr.io/distroless/static-debian12`, copies the single binary, runs as `nonroot:nonroot`. Final image ~12MB.

## Common mistakes to avoid
- `COPY . .` before `pip install` — invalidates the dependency layer on every source change
- Running as root — container escapes become host compromises
- Leaking secrets via `ENV API_KEY=...` or `ARG` (they end up in the image history — use build secrets or runtime env)
- Missing `.dockerignore` — ships your `.git` and `.env` into the image
"""

# ---------------------------------------------------------------------------
# 7. GitHub Actions CI/CD
# ---------------------------------------------------------------------------
_GHA_BODY = """
## Quick Start
Pin action versions to commit SHAs, not tags. Use the least-privileged `permissions:` block. Cache dependencies. Run lint/test/build as parallel jobs, not sequential steps. Use `concurrency:` to cancel stale runs on the same branch.

## When to use this skill
Use when the user says "GitHub Actions", "CI", "workflow", ".github/workflows", "CI/CD pipeline", "deploy on push", or asks to automate tests/builds/deploys on GitHub. Triggers on `.yml` files under `.github/workflows/`.

## Workflow

### Step 1: Name the trigger precisely
Default to `push` on `main` + `pull_request` targeting `main`. Avoid `on: [push]` unqualified — it runs on every branch. Use `paths:` filters to skip workflow runs when only unrelated files change.

### Step 2: Set permissions to least-privilege
Add a top-level `permissions: {}` block and grant only what's needed per job (e.g. `contents: read`, `pull-requests: write`). The default is overbroad and a supply-chain risk.

### Step 3: Parallelize with jobs
Lint, type-check, test, and build are independent — make them separate jobs with `needs:` only where genuinely required. Parallel jobs finish faster and give clearer failure signals.

### Step 4: Pin actions by SHA
Never `uses: actions/checkout@v4` in production workflows — use `uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.1.1`. A compromised tag rewrites your CI supply chain silently.

### Step 5: Cache dependencies
Use the language-specific cache action or `actions/cache` keyed on the lockfile hash. Confirm the cache is actually hitting by checking the "Post" step log.

### Step 6: Add concurrency
```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```
Stops stale runs from queueing up when someone pushes 3 times in a row.

## Examples

**Example 1 — Python library CI**
Input: "set up CI for my Python package, run ruff and pytest on PRs"
Output: Workflow with `lint`, `test`, and `build` jobs running in parallel. Uses `astral-sh/setup-uv@<SHA>`, caches `.venv`, runs `uv run ruff check .` and `uv run pytest`. Concurrency cancels stale runs. Tests run on Python 3.11, 3.12, 3.13 via matrix.

**Example 2 — Node build + deploy to Vercel on main**
Input: "run tests on every PR, deploy to Vercel when main gets a push"
Output: Two workflows: `ci.yml` (pull_request) runs tests; `deploy.yml` (push to main) calls `vercel deploy --prod` with the token from secrets. Deploy job has `permissions: deployments: write, id-token: write`. Concurrency groups keep only the latest deploy running.

**Example 3 — Docker image build + publish**
Input: "build and push my Docker image to ghcr on tag releases"
Output: `on: push: tags: ['v*']`. Uses `docker/setup-buildx-action` and `docker/build-push-action` (both SHA-pinned), logs into ghcr with `GITHUB_TOKEN`, tags the image `ghcr.io/${{ github.repository }}:${{ github.ref_name }}` and `:latest`. Multi-arch via QEMU.

## Common mistakes to avoid
- `uses: actions/checkout@main` — a malicious commit to `main` pwns your CI
- Granting `permissions: write-all` — violates least privilege and is rarely needed
- Forgetting `concurrency:` — queues of stale runs eat minutes and slow the feedback loop
- Hardcoding secrets in workflow files instead of `${{ secrets.FOO }}`
"""

# ---------------------------------------------------------------------------
# 8. Terraform Module Authoring
# ---------------------------------------------------------------------------
_TERRAFORM_BODY = """
## Quick Start
A module is not a folder — it is a contract. Define `variables.tf` (inputs), `main.tf` (resources), `outputs.tf` (return values), and `versions.tf` (provider pins). Document every variable. Never hardcode region, account ID, or environment.

## When to use this skill
Use when the user mentions "Terraform", "module", "HCL", ".tf file", "infra as code", "provider", "variables.tf", or asks to wrap AWS/GCP/Azure resources into something reusable. Triggers on any IaC abstraction request.

## Workflow

### Step 1: Define the contract in variables.tf
Every input variable needs a `type`, a `description`, and (where possible) `validation` blocks. Optional inputs have `default =`. Required inputs do not. Use object types for grouped settings, not a flat forest of strings.

### Step 2: Pin providers in versions.tf
```hcl
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.30" }
  }
}
```
Pin to `~> MAJOR.MINOR` so patch upgrades are automatic but breaking changes are not.

### Step 3: Write main.tf against the contract
Resources reference `var.*` only — never literals for anything that could vary between callers. Use `locals` for derived values computed once. Use `for_each` over `count` when iterating — `count` re-creates resources on list reordering.

### Step 4: Expose outputs
Every resource a caller might need to reference (ID, ARN, DNS name) becomes an `output` with a description. Outputs are the module's return values.

### Step 5: Document
Write a README.md with: purpose, example usage, input table, output table. Run `terraform-docs markdown table .` to generate the input/output tables automatically if available.

### Step 6: Validate
Run `terraform fmt -check`, `terraform validate`, and `tflint`. Run `terraform plan` against an example module call and inspect the plan before declaring done.

## Examples

**Example 1 — S3 bucket module**
Input: "make a Terraform module for an S3 bucket with versioning and encryption"
Output: `variables.tf` with `name`, `environment`, `enable_versioning` (default true), `tags` (map). `main.tf` creates the bucket, enables SSE-KMS, attaches a public-access-block (all 4 flags true), configures versioning conditionally. Outputs `bucket_arn`, `bucket_id`, `bucket_domain_name`.

**Example 2 — VPC with subnets**
Input: "VPC module with public and private subnets across 3 AZs"
Output: Takes `cidr_block` and `az_count` as inputs. Uses `for_each` over `data.aws_availability_zones.available.names` sliced to `az_count`. Creates public subnet + private subnet per AZ, an IGW, a NAT per AZ, and route tables. Outputs `vpc_id`, `public_subnet_ids`, `private_subnet_ids`.

**Example 3 — Refactoring a god-module**
Input: "this 800-line main.tf does everything, help me split it"
Output: Identifies logical groups (networking, compute, storage, iam). Splits into child modules under `modules/` with their own `variables.tf` / `outputs.tf`. The root module becomes a composition that wires outputs from one child into inputs of the next.

## Common mistakes to avoid
- Hardcoding `region = "us-east-1"` or account IDs inside the module — breaks reusability
- Using `count` to iterate over a list — reordering the list destroys and recreates resources
- Forgetting `validation` blocks — callers pass garbage and only find out at apply time
- Not pinning provider versions — a provider major release silently breaks your module
"""

# ---------------------------------------------------------------------------
# 9. Python Test Generation
# ---------------------------------------------------------------------------
_PYTEST_GEN_BODY = """
## Quick Start
Read the function. Identify branches, edge cases, and error paths. Generate one test per branch using AAA (Arrange-Act-Assert). Use `pytest.mark.parametrize` for similar inputs. Mock at the boundary, not inside the unit.

## When to use this skill
Use when the user says "write tests", "add tests", "test this function", "pytest", "unit tests", or "test coverage" alongside a Python file or function. Also triggers on "untested" or "no tests for X".

## Workflow

### Step 1: Read the target
Load the function and any helpers it calls. Identify its signature, return type, exceptions, and every `if`/`elif`/`else`/`except` branch. Note external dependencies (I/O, network, clock, random) — these are your mock points.

### Step 2: Enumerate test cases
For each function, generate tests for:
- **Happy path** — typical valid input
- **Boundary values** — empty, zero, one, max, max+1
- **Invalid input** — wrong type, out of range, malformed (expect raises)
- **Each exception branch** — verify the right exception and message
- **Each external dependency failure** — mocked timeout, mocked error

### Step 3: Write them AAA-style with parametrize
```python
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (0, 1),
    (-5, -4),
])
def test_increment(input, expected):
    # Arrange (implicit via parametrize)
    # Act
    result = increment(input)
    # Assert
    assert result == expected
```
Group related inputs with `parametrize`. Give `ids=` when the inputs are not self-describing.

### Step 4: Mock at the boundary
Mock `httpx.AsyncClient.get`, not the `fetch_user` function under test. Use `respx` for HTTP, `freezegun` for time, `pytest-mock`'s `mocker.patch` for everything else. Never mock the thing you are testing.

### Step 5: Run and verify coverage
`pytest -q` then `pytest --cov=mymodule --cov-report=term-missing`. Any uncovered line is a missing test. Aim for branch coverage, not just line coverage.

## Examples

**Example 1 — Pure function**
Input: "write tests for `def slugify(s: str) -> str` that lowercases, strips, and replaces spaces with hyphens"
Output: One parametrized test with 6 cases: happy path `"Hello World" -> "hello-world"`, already-slug, leading/trailing whitespace, unicode, empty string, string of only spaces. All in ~15 lines.

**Example 2 — Async function with HTTP call**
Input: "test `async def fetch_user(user_id: int)` that calls an API and raises `UserNotFound` on 404"
Output: Uses `respx` to mock the HTTP layer. Three tests: 200 returns the parsed user, 404 raises `UserNotFound`, 500 raises `APIError`. Each uses `@respx.mock` and a single `respx_mock.get(...).mock(return_value=...)` call.

**Example 3 — Database repository**
Input: "tests for `UserRepository.find_by_email` that uses SQLAlchemy async"
Output: Uses an in-memory SQLite via a session fixture, seeds two users, tests: found returns the right user, not-found returns None, case-insensitive email match (if the function claims to be CI). Fixture lives in `conftest.py`.

## Common mistakes to avoid
- One giant test with 15 assertions — when it fails you learn nothing about which case broke
- Mocking the function under test — you end up testing the mock
- Testing only the happy path — the bugs live in the error branches
- Asserting on implementation details (exact log strings, mock call counts) that should be refactor-safe
"""

# ---------------------------------------------------------------------------
# 10. Docstring & Type Hint Authoring
# ---------------------------------------------------------------------------
_DOCSTRING_BODY = """
## Quick Start
Pick one docstring style (Google, NumPy, or Sphinx) and use it consistently across the file. Add type hints to every parameter and return. Document *why*, not *what* — the reader can see what the code does. Never paraphrase the function's literal implementation.

## When to use this skill
Use when the user says "docstring", "type hints", "annotate", "document", "mypy", "pyright", "missing types", or "undocumented" alongside Python code. Also triggers on "clean up this function's signature".

## Workflow

### Step 1: Pick and confirm the style
Scan the file (or the project) for existing docstrings. Match that style. If none exists, default to Google style — it is the most readable and supported by Sphinx via `sphinx.ext.napoleon`. Never mix styles in one file.

### Step 2: Add type hints first
Every parameter: `name: type`. Every return: `-> type`. Prefer modern syntax: `list[int]` not `List[int]`, `str | None` not `Optional[str]` (Python 3.10+). Use `from __future__ import annotations` for forward references.

### Step 3: Write the docstring
Structure:
1. **One-line summary** (imperative mood: "Return the parsed config", not "Returns the parsed config")
2. **Blank line**
3. **Extended description** (only if the one-liner is not enough)
4. **Args / Returns / Raises** sections
5. **Example** (only for non-obvious public APIs)

### Step 4: Check with mypy or pyright
Run the type checker. Fix any `Any`, `# type: ignore`, or unresolvable import. A docstring without type safety is half the job.

### Step 5: Verify the docstring does not lie
Re-read the function and re-read the docstring. If the docstring says "raises ValueError on negative input" and the function does not, one of them is wrong. A misleading docstring is worse than no docstring.

## Examples

**Example 1 — Pure utility function**
Input: "add a docstring and type hints to `def parse_date(s): return datetime.strptime(s, '%Y-%m-%d')`"
Output:
```python
def parse_date(s: str) -> datetime:
    \"\"\"Parse an ISO date string into a naive datetime.

    Args:
        s: Date string in ``YYYY-MM-DD`` format.

    Returns:
        A ``datetime`` at midnight UTC-naive.

    Raises:
        ValueError: If ``s`` does not match the expected format.
    \"\"\"
    return datetime.strptime(s, "%Y-%m-%d")
```

**Example 2 — Class with async method**
Input: "document this UserService class, it has a fetch() method that calls an API"
Output: Class docstring explains the service's role and its DI dependencies. `fetch` gets `Args`, `Returns`, and `Raises: httpx.HTTPError` sections. Async is noted explicitly: "Awaitable. Performs one HTTP round-trip."

**Example 3 — Generic function**
Input: "type hint this `def first(xs): return xs[0]`"
Output:
```python
from typing import TypeVar

T = TypeVar("T")

def first(xs: list[T]) -> T:
    \"\"\"Return the first element of a non-empty list.

    Raises:
        IndexError: If ``xs`` is empty.
    \"\"\"
    return xs[0]
```

## Common mistakes to avoid
- Paraphrasing the code ("This function adds two numbers" on `def add(a, b): return a + b`) — say *why* or say nothing
- Using `Any` as a type hint — it disables the entire point of type checking
- Mixing Google + NumPy + Sphinx styles in one file — picks a lane
- Documenting private helpers as exhaustively as the public API — use a one-liner
"""

# ---------------------------------------------------------------------------
# 11. OWASP Security Audit
# ---------------------------------------------------------------------------
_OWASP_BODY = """
## Quick Start
Walk the code against the OWASP Top 10 systematically. For each category, grep for the signature pattern, inspect each hit, classify severity (critical/high/medium/low), and produce a remediation with a concrete code change. Never mark a finding "fixed" without showing the patch.

## When to use this skill
Use when the user says "security audit", "OWASP", "vulnerability", "pentest", "secure review", "SQL injection", "XSS", "CSRF", "auth bypass", or asks to review code for security issues. Triggers on any "is this safe?" question about user-input handling.

## Workflow

### Step 1: Scope the audit
List the entry points: HTTP handlers, CLI args, file uploads, message queue consumers, webhook receivers. Every security issue lives at a trust boundary — map them first.

### Step 2: Walk the OWASP Top 10
For each category, search with a specific pattern:
- **A01 Broken Access Control**: find every route, confirm it has an auth check. Look for IDOR: does the handler verify the resource belongs to the current user?
- **A02 Cryptographic Failures**: `grep -r "md5\\|sha1\\|DES\\|ECB"`, plus check for HTTP URLs in auth flows, hardcoded keys, missing TLS.
- **A03 Injection**: string-formatted SQL (`f"SELECT ... {var}"`, `.format()`, `%`), `subprocess` with `shell=True`, `eval`/`exec`, `os.system`.
- **A04 Insecure Design**: rate limiting, account lockout, email enumeration, TOCTOU on file access.
- **A05 Misconfiguration**: default credentials, `DEBUG=True` in prod, permissive CORS (`*`), verbose error pages.
- **A06 Vulnerable Components**: run `pip-audit` / `npm audit` / `trivy fs`.
- **A07 Auth Failures**: weak password policy, session fixation, missing MFA on admin, predictable tokens (use `secrets`, not `random`).
- **A08 Integrity Failures**: unsigned update mechanisms, deserializing untrusted data (`pickle.loads`, `yaml.load` without SafeLoader).
- **A09 Logging Failures**: sensitive data in logs, no audit trail for admin actions.
- **A10 SSRF**: any `requests.get(user_url)` without allowlist.

### Step 3: Classify severity
- **Critical**: unauthenticated RCE, unauthenticated data exfil, auth bypass
- **High**: authenticated RCE, privilege escalation, stored XSS
- **Medium**: reflected XSS, info disclosure, weak crypto
- **Low**: missing security headers, verbose errors

### Step 4: Write the finding + fix
Every finding has: title, severity, location (file:line), description, exploit scenario, remediation (with code diff), references (CWE/CVE). No finding ships without a concrete fix.

### Step 5: Verify fixes
After the user applies fixes, re-scan the patched files. Confirm the pattern is gone AND that the fix is semantically correct (e.g. parameterized query actually parameterizes, not just string-concats differently).

## Examples

**Example 1 — SQL injection in a search endpoint**
Input: "review my Flask app for security issues"
Output: Finds `cursor.execute(f"SELECT * FROM users WHERE name LIKE '%{name}%'")`. Severity: Critical. Exploit: `name="'; DROP TABLE users; --"`. Fix: `cursor.execute("SELECT * FROM users WHERE name LIKE ?", (f"%{name}%",))`. CWE-89.

**Example 2 — IDOR on a document endpoint**
Input: "audit /api/documents/<id>"
Output: Handler reads `document_id` from the URL and fetches it without checking ownership. Any logged-in user can read any document. Severity: High. Fix: `Document.query.filter_by(id=document_id, owner_id=current_user.id).first_or_404()`. CWE-639.

**Example 3 — Hardcoded secret**
Input: "look for secrets in this repo"
Output: Finds `STRIPE_KEY = "sk_live_..."` in `config.py`. Severity: Critical (live key). Fix: move to env var via `os.environ["STRIPE_KEY"]`, add to `.gitignore`, rotate the key immediately (the committed one is burned), scrub git history with `git filter-repo`. CWE-798.

## Common mistakes to avoid
- Reporting findings without a concrete fix — "use parameterized queries" is not a fix, show the line
- Flagging best-practice gaps as "vulnerabilities" (inflates severity, erodes trust)
- Missing the trust boundary — internal service calls still need auth if the network is not isolated
- Declaring a fix verified without re-running the pattern scan against the patched code
"""

# ---------------------------------------------------------------------------
# 12. Secret & Credential Scanner
# ---------------------------------------------------------------------------
_SECRET_SCAN_BODY = """
## Quick Start
Scan working tree AND git history. Match against a ruleset (entropy + regex), filter false positives, and for every true positive: rotate the secret FIRST, then remove it from history. Rotation before removal is non-negotiable.

## When to use this skill
Use when the user says "scan for secrets", "check for leaked keys", "are there credentials in my repo", "pre-commit hook for secrets", or mentions `.env`, AWS keys, API tokens, or "did I commit a password". Also triggers after "I accidentally pushed..."

## Workflow

### Step 1: Scan the working tree
Run a ruleset against every tracked file. Use `gitleaks detect --no-git --verbose` or `trufflehog filesystem .`. If neither is installed, fall back to a regex sweep for the highest-signal patterns:
- AWS: `AKIA[0-9A-Z]{16}`
- GitHub: `gh[pousr]_[A-Za-z0-9]{36,}`
- Slack: `xox[baprs]-[A-Za-z0-9-]+`
- Generic high-entropy strings in `.env*`, `config.*`, `settings.*`

### Step 2: Scan git history
Working-tree scans miss secrets committed then deleted. Run `gitleaks detect` (scans all history by default) or `trufflehog git file://.`. Any hit here means rotation is required — the secret is in the remote.

### Step 3: Triage each hit
Classify:
- **True positive, live credential** -> ROTATE FIRST, then clean history
- **True positive, test/dummy credential** -> add to allowlist with a comment, move to `.env.example` with a fake value
- **False positive** (e.g. an AWS key shape inside a Go test fixture) -> add a targeted allowlist entry referencing the line

### Step 4: Rotate, then remove
```
1. Rotate the live secret at the provider (AWS IAM, GitHub, Stripe, ...)
2. Update your deployment with the new secret
3. Remove the old value from git history with `git filter-repo --replace-text` or BFG
4. Force-push the cleaned history (coordinate with your team)
5. Rescan to confirm
```
Never skip step 1. Once a secret is in a public remote, assume it is compromised within minutes.

### Step 5: Prevent recurrence
Install a pre-commit hook: `pre-commit` with `gitleaks` or `detect-secrets`. Add `.env` and friends to `.gitignore`. Add a CI job that scans on every PR.

## Examples

**Example 1 — Live AWS key in working tree**
Input: "scan this repo for secrets"
Output: Finds `AKIAIOSFODNN7EXAMPLE` in `deploy/provision.sh:42`. Severity: Critical. Instructions: (1) rotate via `aws iam create-access-key` + `delete-access-key`, (2) replace the hardcoded value with `${AWS_ACCESS_KEY_ID}` env var, (3) if this commit was pushed, run `git filter-repo --replace-text` to scrub history and force-push.

**Example 2 — OpenAI key in history only**
Input: "did I ever commit an OpenAI key?"
Output: Working tree clean. `gitleaks detect` on history finds `sk-proj-...` in commit `abc1234`, file `.env`, removed two commits later. The key is still in the remote history. Rotate at platform.openai.com, then `git filter-repo --replace-text` + force push.

**Example 3 — False positive in a test fixture**
Input: "why is the scanner flagging test/fixtures/aws_response.json?"
Output: Inspects the file — it is a mocked AWS SDK response containing `AKIAIOSFODNN7EXAMPLE` (the well-known documentation example). Adds a gitleaks allowlist entry keyed on file path + regex with a comment explaining it is Amazon's official docs example.

## Common mistakes to avoid
- Removing a secret from history without rotating — the key is already compromised, history cleanup is theater
- Force-pushing cleaned history without telling collaborators — they will re-introduce the secret on their next push
- Adding broad allowlists (`allowlist: .*`) that silence the scanner entirely
- Only scanning the working tree — most leaks are in commits that were later "fixed"
"""

# ---------------------------------------------------------------------------
# 13. README Drafting
# ---------------------------------------------------------------------------
_README_BODY = """
## Quick Start
Every README answers four questions in order: What is it? Why does it exist? How do I use it? How do I contribute? Skip any one and the README fails its job. Lead with a one-sentence tagline, not a logo.

## When to use this skill
Use when the user says "write a README", "document this project", "no README", "README.md is empty", or "draft a README for this repo". Also triggers on "how do I describe this project on GitHub".

## Workflow

### Step 1: Discover the project
Read `package.json` / `pyproject.toml` / `Cargo.toml` / `go.mod` for the name, version, description, and scripts. Read the entry-point file. Read the existing tests for usage patterns. Note the license file. Do not write a README from the user's description alone — read the code.

### Step 2: Draft the required sections
In order:
1. **H1 title** + one-sentence tagline
2. **Badges** (build status, package version, license) — optional, skip if not set up
3. **What it is** — 2-3 sentences explaining the project plainly
4. **Why** — one paragraph on the problem it solves (skip for toy projects)
5. **Install** — the literal command(s)
6. **Quick start / Usage** — the smallest runnable example
7. **Configuration** — environment variables, config files (table format)
8. **Contributing** — or a link to `CONTRIBUTING.md`
9. **License** — single line referencing the LICENSE file

### Step 3: Write the Quick Start against a fresh clone
The Quick Start must work on a blank machine with nothing but the prerequisites installed. If `npm install && npm start` produces errors, your Quick Start is wrong. Test it.

### Step 4: Keep it short
A good README is ~100-300 lines. Anything longer belongs in `docs/`. Link out; do not inline an API reference.

### Step 5: Lint the links
Before finishing, verify every link works. Broken links on a README page are the first impression of an unmaintained project.

## Examples

**Example 1 — Python library**
Input: "write a README for my pypi package `colorlog`"
Output: Title + tagline "Structured color logging for Python". Install: `pip install colorlog`. Quick Start: 8-line code block showing `import colorlog; logger = colorlog.getLogger(...); logger.info(...)`. Configuration table listing env vars. Link to `docs/` for the API reference. Apache-2.0 license line.

**Example 2 — CLI tool**
Input: "README for my Rust CLI that generates UUIDs"
Output: Title + "A fast UUID generator". Install via `cargo install uuidgen` AND a `brew install` option AND prebuilt binaries link. Usage section shows 4 example invocations with their output. A short `--help`-style flag table. MIT license line.

**Example 3 — Minimal hobby project**
Input: "README for my dotfiles repo"
Output: Two-sentence intro, an `install.sh` one-liner, a short list of what gets symlinked where, a "things I stole from" credits section. No badges, no contribution guide. ~40 lines total.

## Common mistakes to avoid
- Starting with a logo or ASCII art instead of a tagline — what the project *does* goes first
- Copy-pasting the library's API reference into the README instead of linking to it
- Writing Quick Start from memory without running it on a fresh clone
- Forgetting the license — without it, legally no one can use your code
"""

# ---------------------------------------------------------------------------
# 14. API Reference Generator
# ---------------------------------------------------------------------------
_API_REF_BODY = """
## Quick Start
Generate reference docs from the source of truth (OpenAPI spec, JSDoc, Python docstrings, Go doc comments), not from hand-written prose. Hand-written reference drifts within weeks. Pick the right generator for the language and wire it into CI.

## When to use this skill
Use when the user says "API reference", "API docs", "document my API", "OpenAPI", "Swagger", "generate docs", or asks how to publish reference documentation for a library or HTTP API. Also triggers on "docs are out of date".

## Workflow

### Step 1: Classify what you're documenting
- **HTTP API** -> OpenAPI 3.1 spec + Redoc or Scalar or Stoplight Elements for rendering
- **Python library** -> docstrings + Sphinx with `autodoc` + `napoleon`, or mkdocs + `mkdocstrings`
- **TypeScript/JavaScript library** -> JSDoc or TSDoc + TypeDoc
- **Go package** -> godoc comments + `pkg.go.dev` (automatic, zero setup)
- **Rust crate** -> `///` doc comments + `cargo doc` (automatic)

### Step 2: Fix the source of truth first
If the docstrings are wrong or missing, the generated docs will be wrong or missing. Do a pass over the public API:
- Every exported symbol has a docstring
- Every parameter and return is documented
- Every error/exception path is listed
- Each public function has one runnable example

### Step 3: Generate and render
HTTP APIs: if your framework supports it (FastAPI, Fastify with schemas, NestJS with decorators), let it emit the OpenAPI spec automatically. Otherwise hand-write the spec. Render with Redoc (`npx @redocly/cli build-docs openapi.yaml`).

Libraries: run the generator (`sphinx-build`, `typedoc`, `cargo doc`). Fix any warnings — they are almost always real doc bugs.

### Step 4: Publish and wire CI
Publish to GitHub Pages, Cloudflare Pages, or Vercel. Add a CI job that regenerates docs on push to main and fails the build if doc generation fails. This is the only way docs stay fresh.

### Step 5: Add a "Try it" affordance where possible
For HTTP APIs, Redoc/Scalar embed a request sandbox. For libraries, link to a CodeSandbox or a Replit template. Readers who can execute learn faster than readers who scroll.

## Examples

**Example 1 — FastAPI service**
Input: "generate an API reference for my FastAPI app"
Output: Shows that FastAPI already exposes `/openapi.json` for free. Script dumps it to `openapi.json`, runs `npx @redocly/cli build-docs openapi.json -o docs/api.html`, adds a GitHub Pages workflow. Notes which Pydantic fields need `description=` and `example=` so the rendered docs are not empty.

**Example 2 — Python library with Sphinx**
Input: "docs for my pandas helper library"
Output: Scaffolds `docs/conf.py` with `sphinx.ext.autodoc`, `sphinx.ext.napoleon`, `sphinx.ext.viewcode`. Adds a `docs/index.rst` with `automodule::` directives for each public module. CI job runs `sphinx-build -W docs docs/_build/html` (`-W` treats warnings as errors — the whole point).

**Example 3 — TypeScript SDK**
Input: "API reference for my TypeScript client SDK, tsconfig is strict"
Output: Installs `typedoc`. Config generates Markdown output into `docs/api`. Adds a Changesets + release workflow that re-runs typedoc on version bumps. Points out which public types are missing TSDoc comments (typedoc emits warnings, treat them as errors).

## Common mistakes to avoid
- Hand-writing reference docs in Markdown — they drift within one sprint
- Committing the generated output to the main branch alongside source — creates merge conflicts every PR
- Documenting private symbols as exhaustively as public ones — signal-to-noise tanks
- Letting `sphinx-build` warnings pile up — each warning is a real doc bug hiding in plain sight
"""

# ---------------------------------------------------------------------------
# 15. Changelog Extraction from Git
# ---------------------------------------------------------------------------
_CHANGELOG_BODY = """
## Quick Start
Group commits by conventional-commit type between two tags. Output under `## [x.y.z] - YYYY-MM-DD` sections keyed by Added/Changed/Fixed/Removed (Keep a Changelog format). Deduplicate squashed commits. Never fabricate entries — if a commit is missing, the user's git history is the fix, not the changelog.

## When to use this skill
Use when the user says "changelog", "CHANGELOG.md", "release notes", "what changed since v1.2.0", "keep a changelog", or "generate release notes from git". Triggers on preparing a release.

## Workflow

### Step 1: Identify the version range
Ask or detect: from which tag, to which tag (or to HEAD)? Default to `git describe --tags --abbrev=0` for the previous tag and HEAD for the next release. Confirm with the user before generating if the range is ambiguous.

### Step 2: Collect the commits
```
git log --pretty=format:'%H%x09%s%x09%an' <from>..<to>
```
Include merge commits only if the project uses merge-commit workflow (check `git log --merges -n 5`). Squash-merge projects already have clean linear history — skip merges.

### Step 3: Classify each commit
Parse the subject line against conventional-commit prefixes:
- `feat:` -> **Added**
- `fix:` -> **Fixed**
- `refactor:`, `perf:`, `style:` -> **Changed**
- `remove:`, `revert:` -> **Removed**
- `chore:`, `docs:`, `test:`, `ci:` -> skipped by default (include with a flag if the user asks)
- `BREAKING CHANGE:` in the body -> move to a top-level **BREAKING** section regardless of type

Commits that don't match any prefix go to **Changed** with their raw subject. Do not drop them silently.

### Step 4: Write the section
Follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format:
```markdown
## [1.3.0] - 2026-04-09

### Added
- Short user-facing description of the feature ([abc1234])

### Fixed
- Short description of the bug fix ([def5678])
```
Link each entry to its commit or PR. Rewrite commit subjects into user-facing prose — "feat: add WS reconnect" becomes "WebSocket automatically reconnects after disconnect".

### Step 5: Prepend, never overwrite
Insert the new section at the top of `CHANGELOG.md`, below the `# Changelog` title and the Keep-a-Changelog preamble. Never rewrite or delete previous entries unless the user explicitly requests a history rewrite.

## Examples

**Example 1 — Clean conventional-commit history**
Input: "generate a changelog for v1.4.0 from v1.3.0"
Output: Collects 23 commits. Classifies: 4 feat, 6 fix, 3 refactor, 8 chore (skipped), 2 docs (skipped). Produces an `## [1.4.0] - 2026-04-09` section with **Added** (4 bullets), **Fixed** (6 bullets), **Changed** (3 bullets). Each links to its commit SHA.

**Example 2 — Mixed history, some non-conventional**
Input: "changelog since last release but my commits are not all conventional"
Output: Buckets the conventional ones correctly, puts the rest under **Changed** with a note "(unclassified commits)". Flags three commits with `BREAKING CHANGE:` footers into a top-level **BREAKING** subsection.

**Example 3 — First changelog ever**
Input: "I never had a CHANGELOG.md, generate one from all history"
Output: Scans all tags via `git tag --sort=creatordate`. Generates one section per tag in reverse-chronological order. Adds the Keep-a-Changelog preamble. Warns the user that older sections will be rougher because pre-conventional commits are harder to classify — offers to trim to the last N releases.

## Common mistakes to avoid
- Including `chore:`, `ci:`, `test:` entries in the user-facing changelog — users do not care
- Leaving raw commit subjects like "fix: null ptr in parser #423" instead of rewriting to prose
- Overwriting prior changelog sections instead of prepending the new one
- Forgetting to bump the version in `package.json` / `pyproject.toml` at the same time
"""


SEED_SKILLS: list[dict] = [
    {
        "id": "seed-pandas-cleaning",
        "slug": "pandas-cleaning",
        "title": "Pandas DataFrame Cleaning",
        "category": "Data Engineering",
        "difficulty": "medium",
        "frontmatter": {
            "name": "pandas-cleaning",
            "description": (
                "Cleans dirty pandas DataFrames: null handling, dedup, dtype coercion, outliers. "
                "Use when user mentions pandas, DataFrame, CSV, nulls, NaN, dedupe, wrangle, or tidy data, even if they don't explicitly ask. NOT for SQL, Spark, or visualization."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="pandas-cleaning",
            title="Pandas DataFrame Cleaning",
            description=(
                "Cleans dirty pandas DataFrames: null handling, dedup, dtype coercion, outliers. "
                "Use when user mentions pandas, DataFrame, CSV, nulls, NaN, dedupe, wrangle, or tidy data, even if they don't explicitly ask. NOT for SQL, Spark, or visualization."
            ),
            allowed_tools="Read Write Bash(python *)",
            body=_PANDAS_CLEANING_BODY,
        ),
        "supporting_files": {},
        "traits": [
            "classification-before-action",
            "defensive-validation",
            "pipeline-composition",
            "before-after-diff",
        ],
        "meta_strategy": "Profile-first cleaning: never mutate without first classifying each problem column and emitting a diff report showing exactly what changed.",
    },
    {
        "id": "seed-sql-optimization",
        "slug": "sql-optimization",
        "title": "SQL Query Optimization",
        "category": "Data Engineering",
        "difficulty": "hard",
        "frontmatter": {
            "name": "sql-optimization",
            "description": (
                "Optimizes slow SQL queries via EXPLAIN analysis, index design, and predicate rewrites. "
                "Use when user says slow query, EXPLAIN, index, query plan, Postgres, or n+1, even without saying 'optimize'. NOT for schema design or ORM tuning."
            ),
            "allowed-tools": ["Read", "Bash"],
        },
        "skill_md_content": _build(
            name="sql-optimization",
            title="SQL Query Optimization",
            description=(
                "Optimizes slow SQL queries via EXPLAIN analysis, index design, and predicate rewrites. "
                "Use when user says slow query, EXPLAIN, index, query plan, Postgres, or n+1, even without saying 'optimize'. NOT for schema design or ORM tuning."
            ),
            allowed_tools="Read Bash(psql *)",
            body=_SQL_OPT_BODY,
        ),
        "supporting_files": {},
        "traits": [
            "plan-before-patch",
            "bottleneck-first",
            "smallest-fix-first",
            "before-after-diff",
        ],
        "meta_strategy": "Never optimize without an EXPLAIN baseline. Identify the single hottest node, apply the smallest fix, diff the plan, and only escalate if the small fix failed.",
    },
    {
        "id": "seed-react-refactoring",
        "slug": "react-refactoring",
        "title": "React Component Refactoring",
        "category": "Web Development",
        "difficulty": "medium",
        "frontmatter": {
            "name": "react-refactoring",
            "description": (
                "Refactors React components: extract subcomponents, lift state, fix re-renders and prop drilling. "
                "Use when user says refactor, split, extract, prop drilling, or re-renders on .jsx/.tsx, even without 'React'. NOT for new features."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="react-refactoring",
            title="React Component Refactoring",
            description=(
                "Refactors React components: extract subcomponents, lift state, fix re-renders and prop drilling. "
                "Use when user says refactor, split, extract, prop drilling, or re-renders on .jsx/.tsx, even without 'React'. NOT for new features."
            ),
            allowed_tools="Read Write Bash(npm *)",
            body=_REACT_REFACTOR_BODY,
        ),
        "supporting_files": {},
        "traits": [
            "smell-inventory-first",
            "small-reversible-steps",
            "behavior-preservation",
            "test-gated",
        ],
        "meta_strategy": "Tag smells explicitly before touching code, refactor one smell per commit, and prove behavior preservation by running the existing test suite unchanged.",
    },
    {
        "id": "seed-nextjs-migration",
        "slug": "nextjs-app-router-migration",
        "title": "Next.js App Router Migration",
        "category": "Web Development",
        "difficulty": "hard",
        "frontmatter": {
            "name": "nextjs-app-router-migration",
            "description": (
                "Migrates Next.js pages router to app router one route at a time: SSR, SSG, API routes, layouts. "
                "Use when user mentions Next.js, app router, pages router, migrate, or getServerSideProps. NOT for new Next.js projects (start in app/)."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="nextjs-app-router-migration",
            title="Next.js App Router Migration",
            description=(
                "Migrates Next.js pages router to app router one route at a time: SSR, SSG, API routes, layouts. "
                "Use when user mentions Next.js, app router, pages router, migrate, or getServerSideProps. NOT for new Next.js projects (start in app/)."
            ),
            allowed_tools="Read Write Bash(npm *)",
            body=_NEXT_MIGRATION_BODY,
        ),
        "supporting_files": {},
        "traits": [
            "incremental-migration",
            "route-by-route",
            "coexistence-strategy",
            "server-first-defaults",
        ],
        "meta_strategy": "Migrate one route at a time while both routers coexist; default to Server Components and only mark interactive leaves as client.",
    },
    {
        "id": "seed-fastapi-endpoint",
        "slug": "fastapi-endpoint",
        "title": "FastAPI Endpoint Authoring",
        "category": "Web Development",
        "difficulty": "easy",
        "frontmatter": {
            "name": "fastapi-endpoint",
            "description": (
                "Authors FastAPI endpoints with Pydantic models, DI, and tests. "
                "Use when user says FastAPI, endpoint, route, Pydantic, or asks for a Python HTTP handler, even without naming the framework. NOT for Flask, Django, or non-HTTP code."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="fastapi-endpoint",
            title="FastAPI Endpoint Authoring",
            description=(
                "Authors FastAPI endpoints with Pydantic models, DI, and tests. "
                "Use when user says FastAPI, endpoint, route, Pydantic, or asks for a Python HTTP handler, even without naming the framework. NOT for Flask, Django, or non-HTTP code."
            ),
            allowed_tools="Read Write Bash(pytest *)",
            body=_FASTAPI_BODY,
        ),
        "supporting_files": {},
        "traits": [
            "contract-first",
            "service-layer-delegation",
            "test-gated",
            "dependency-injection",
        ],
        "meta_strategy": "Define the Pydantic contract first, delegate business logic to a service, and ship the route with tests covering happy path plus every declared error.",
    },
    {
        "id": "seed-dockerfile-authoring",
        "slug": "dockerfile-authoring",
        "title": "Dockerfile Authoring",
        "category": "DevOps",
        "difficulty": "medium",
        "frontmatter": {
            "name": "dockerfile-authoring",
            "description": (
                "Writes production Dockerfiles: multi-stage, non-root, pinned base, cache-friendly layer order, HEALTHCHECK. "
                "Use when user says Dockerfile, containerize, docker build, or dockerize, even without 'production'. NOT for docker-compose or Kubernetes."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="dockerfile-authoring",
            title="Dockerfile Authoring",
            description=(
                "Writes production Dockerfiles: multi-stage, non-root, pinned base, cache-friendly layer order, HEALTHCHECK. "
                "Use when user says Dockerfile, containerize, docker build, or dockerize, even without 'production'. NOT for docker-compose or Kubernetes."
            ),
            allowed_tools="Read Write Bash(docker *)",
            body=_DOCKERFILE_BODY,
        ),
        "supporting_files": {
            ".dockerignore.example": (
                ".git\n.gitignore\nnode_modules\n__pycache__\n*.pyc\n.venv\n.env\n.env.*\ndist\nbuild\n*.log\n.DS_Store\ncoverage\n.pytest_cache\n.mypy_cache\n.ruff_cache\n"
            ),
        },
        "traits": [
            "multi-stage-builds",
            "cache-friendly-layers",
            "least-privilege",
            "pinned-dependencies",
        ],
        "meta_strategy": "Default to multi-stage + non-root + pinned digest. Order layers by change frequency so dependency layers cache across commits.",
    },
    {
        "id": "seed-github-actions",
        "slug": "github-actions-ci",
        "title": "GitHub Actions CI/CD",
        "category": "DevOps",
        "difficulty": "medium",
        "frontmatter": {
            "name": "github-actions-ci",
            "description": (
                "Authors GitHub Actions workflows: SHA-pinned actions, least-privilege permissions, parallel jobs, dep caching, concurrency. "
                "Use when user mentions CI, GitHub Actions, workflow, or .github/workflows. NOT for GitLab CI, CircleCI, or Jenkins."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="github-actions-ci",
            title="GitHub Actions CI/CD",
            description=(
                "Authors GitHub Actions workflows: SHA-pinned actions, least-privilege permissions, parallel jobs, dep caching, concurrency. "
                "Use when user mentions CI, GitHub Actions, workflow, or .github/workflows. NOT for GitLab CI, CircleCI, or Jenkins."
            ),
            allowed_tools="Read Write Bash(gh *)",
            body=_GHA_BODY,
        ),
        "supporting_files": {},
        "traits": [
            "least-privilege",
            "supply-chain-hardening",
            "parallelization",
            "pinned-dependencies",
        ],
        "meta_strategy": "SHA-pin everything, grant minimum permissions per job, parallelize independent stages, and always set concurrency to cancel stale runs.",
    },
    {
        "id": "seed-terraform-module",
        "slug": "terraform-module",
        "title": "Terraform Module Authoring",
        "category": "DevOps",
        "difficulty": "hard",
        "frontmatter": {
            "name": "terraform-module",
            "description": (
                "Authors reusable Terraform modules with typed variables, validation, pinned providers, and outputs. "
                "Use when user says Terraform, module, HCL, .tf, or infra as code, even without 'reusable'. NOT for one-off root configs or non-HCL IaC."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="terraform-module",
            title="Terraform Module Authoring",
            description=(
                "Authors reusable Terraform modules with typed variables, validation, pinned providers, and outputs. "
                "Use when user says Terraform, module, HCL, .tf, or infra as code, even without 'reusable'. NOT for one-off root configs or non-HCL IaC."
            ),
            allowed_tools="Read Write Bash(terraform *)",
            body=_TERRAFORM_BODY,
        ),
        "supporting_files": {},
        "traits": [
            "contract-first",
            "pinned-dependencies",
            "defensive-validation",
            "for-each-over-count",
        ],
        "meta_strategy": "Treat the module as a typed contract (variables + outputs), pin providers, validate inputs, and use for_each over count for stable identity.",
    },
    {
        "id": "seed-pytest-generation",
        "slug": "pytest-generation",
        "title": "Python Test Generation",
        "category": "Code Quality",
        "difficulty": "medium",
        "frontmatter": {
            "name": "pytest-generation",
            "description": (
                "Generates pytest unit tests: AAA structure, parametrize, boundary/error cases, boundary mocking. "
                "Use when user says write tests, add tests, pytest, unit tests, or test coverage for Python. NOT for integration, e2e, or load testing."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="pytest-generation",
            title="Python Test Generation",
            description=(
                "Generates pytest unit tests: AAA structure, parametrize, boundary/error cases, boundary mocking. "
                "Use when user says write tests, add tests, pytest, unit tests, or test coverage for Python. NOT for integration, e2e, or load testing."
            ),
            allowed_tools="Read Write Bash(pytest *)",
            body=_PYTEST_GEN_BODY,
        ),
        "supporting_files": {},
        "traits": [
            "branch-enumeration",
            "boundary-mocking",
            "parametrize-similar-cases",
            "arrange-act-assert",
        ],
        "meta_strategy": "Enumerate branches and error paths first, then generate one parametrized test per case, mocking only at the I/O boundary.",
    },
    {
        "id": "seed-docstring-typing",
        "slug": "docstring-typing",
        "title": "Docstring & Type Hint Authoring",
        "category": "Code Quality",
        "difficulty": "easy",
        "frontmatter": {
            "name": "docstring-typing",
            "description": (
                "Adds Python docstrings and type hints in a consistent style, checked with mypy/pyright. "
                "Use when user says docstring, type hints, annotate, document, mypy, or undocumented for .py files. NOT for runtime docs or API references."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="docstring-typing",
            title="Docstring & Type Hint Authoring",
            description=(
                "Adds Python docstrings and type hints in a consistent style, checked with mypy/pyright. "
                "Use when user says docstring, type hints, annotate, document, mypy, or undocumented for .py files. NOT for runtime docs or API references."
            ),
            allowed_tools="Read Write Bash(mypy *)",
            body=_DOCSTRING_BODY,
        ),
        "supporting_files": {},
        "traits": [
            "consistent-style",
            "why-not-what",
            "type-checker-gated",
            "progressive-disclosure",
        ],
        "meta_strategy": "Pick one docstring style per file, annotate types first, document the why not the what, and verify with a type checker before declaring done.",
    },
    {
        "id": "seed-owasp-audit",
        "slug": "owasp-security-audit",
        "title": "OWASP Security Audit",
        "category": "Security",
        "difficulty": "hard",
        "frontmatter": {
            "name": "owasp-security-audit",
            "description": (
                "Audits code against OWASP Top 10: injection, auth, IDOR, secrets, SSRF, deserialization. "
                "Use when user says security audit, OWASP, vulnerability, pentest, SQL injection, XSS, or 'is this safe'. NOT for pure best-practice style review."
            ),
            "allowed-tools": ["Read", "Grep", "Bash"],
        },
        "skill_md_content": _build(
            name="owasp-security-audit",
            title="OWASP Security Audit",
            description=(
                "Audits code against OWASP Top 10: injection, auth, IDOR, secrets, SSRF, deserialization. "
                "Use when user says security audit, OWASP, vulnerability, pentest, SQL injection, XSS, or 'is this safe'. NOT for pure best-practice style review."
            ),
            allowed_tools="Read Grep Bash(pip-audit *)",
            body=_OWASP_BODY,
        ),
        "supporting_files": {},
        "traits": [
            "trust-boundary-mapping",
            "pattern-driven-search",
            "severity-classification",
            "fix-with-diff",
        ],
        "meta_strategy": "Map trust boundaries, walk the Top 10 systematically with grep-driven pattern searches, and never ship a finding without a concrete code-level fix.",
    },
    {
        "id": "seed-secret-scanner",
        "slug": "secret-scanner",
        "title": "Secret & Credential Scanner",
        "category": "Security",
        "difficulty": "medium",
        "frontmatter": {
            "name": "secret-scanner",
            "description": (
                "Scans working tree and git history for leaked secrets and API keys, with rotate-then-remove remediation. "
                "Use when user says scan for secrets, leaked keys, credentials, or 'did I commit a password'. NOT for runtime secret management."
            ),
            "allowed-tools": ["Read", "Grep", "Bash"],
        },
        "skill_md_content": _build(
            name="secret-scanner",
            title="Secret & Credential Scanner",
            description=(
                "Scans working tree and git history for leaked secrets and API keys, with rotate-then-remove remediation. "
                "Use when user says scan for secrets, leaked keys, credentials, or 'did I commit a password'. NOT for runtime secret management."
            ),
            allowed_tools="Read Grep Bash(gitleaks *)",
            body=_SECRET_SCAN_BODY,
        ),
        "supporting_files": {},
        "traits": [
            "history-aware-scanning",
            "rotate-before-remove",
            "triage-with-allowlist",
            "prevention-over-cleanup",
        ],
        "meta_strategy": "Scan both working tree and full git history, rotate live credentials before touching history, and install pre-commit + CI scanning to prevent recurrence.",
    },
    {
        "id": "seed-readme-drafting",
        "slug": "readme-drafting",
        "title": "README Drafting",
        "category": "Documentation",
        "difficulty": "easy",
        "frontmatter": {
            "name": "readme-drafting",
            "description": (
                "Drafts project READMEs that answer what/why/how-to-use/how-to-contribute from the actual code. "
                "Use when user says write a README, document this project, or 'no README'. NOT for API references or in-code docstrings."
            ),
            "allowed-tools": ["Read", "Write"],
        },
        "skill_md_content": _build(
            name="readme-drafting",
            title="README Drafting",
            description=(
                "Drafts project READMEs that answer what/why/how-to-use/how-to-contribute from the actual code. "
                "Use when user says write a README, document this project, or 'no README'. NOT for API references or in-code docstrings."
            ),
            allowed_tools="Read Write",
            body=_README_BODY,
        ),
        "supporting_files": {},
        "traits": [
            "source-grounded",
            "minimal-sections",
            "tested-quickstart",
            "why-not-what",
        ],
        "meta_strategy": "Ground every section in what the code actually does, lead with a tagline not a logo, and verify the Quick Start on a fresh clone before declaring done.",
    },
    {
        "id": "seed-api-reference",
        "slug": "api-reference-generator",
        "title": "API Reference Generator",
        "category": "Documentation",
        "difficulty": "medium",
        "frontmatter": {
            "name": "api-reference-generator",
            "description": (
                "Generates API reference docs from source of truth (OpenAPI, docstrings, JSDoc) and wires into CI. "
                "Use when user says API reference, API docs, OpenAPI, Swagger, Sphinx, or TypeDoc. NOT for tutorials or narrative guides."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="api-reference-generator",
            title="API Reference Generator",
            description=(
                "Generates API reference docs from source of truth (OpenAPI, docstrings, JSDoc) and wires into CI. "
                "Use when user says API reference, API docs, OpenAPI, Swagger, Sphinx, or TypeDoc. NOT for tutorials or narrative guides."
            ),
            allowed_tools="Read Write Bash(sphinx-build *)",
            body=_API_REF_BODY,
        ),
        "supporting_files": {},
        "traits": [
            "source-of-truth-generation",
            "ci-gated",
            "tool-routing-by-language",
            "warnings-as-errors",
        ],
        "meta_strategy": "Generate from the source of truth (never hand-write), route to the idiomatic tool per language, and fail CI on generator warnings so docs never drift.",
    },
    {
        "id": "seed-changelog-extraction",
        "slug": "changelog-from-git",
        "title": "Changelog Extraction from Git",
        "category": "Documentation",
        "difficulty": "easy",
        "frontmatter": {
            "name": "changelog-from-git",
            "description": (
                "Generates Keep-a-Changelog sections from git history using conventional-commit classification. "
                "Use when user says changelog, CHANGELOG.md, release notes, or 'what changed since'. NOT for full release announcements or blog posts."
            ),
            "allowed-tools": ["Read", "Write", "Bash"],
        },
        "skill_md_content": _build(
            name="changelog-from-git",
            title="Changelog Extraction from Git",
            description=(
                "Generates Keep-a-Changelog sections from git history using conventional-commit classification. "
                "Use when user says changelog, CHANGELOG.md, release notes, or 'what changed since'. NOT for full release announcements or blog posts."
            ),
            allowed_tools="Read Write Bash(git *)",
            body=_CHANGELOG_BODY,
        ),
        "supporting_files": {},
        "traits": [
            "conventional-commit-parsing",
            "classification-before-action",
            "append-only",
            "user-facing-rewrite",
        ],
        "meta_strategy": "Classify commits by conventional-commit type between two tags, rewrite subjects into user-facing prose, and prepend to the existing changelog (never overwrite).",
    },
]


__all__ = ["SEED_SKILLS"]
