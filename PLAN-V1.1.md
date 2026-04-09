# PLAN-V1.1.md — Next Feature Batch (v2)

**Status**: ✅ LOCKED 2026-04-09 — Matt approved all 7 recs. Build order: §3 → §1 → §2 → §4. Unified `from-parent` fork endpoint. Hash-based seed reload. Immutable seeds. Fonts + colors. Three-state theme toggle.
**Date**: 2026-04-09 (rewritten after Matt's Registry-seeding re-scope)
**Scope**: four features, now unified around a single "Gen 0 Skill" concept

---

## Re-scope summary

The original plan treated "seed library" (curated specialization strings on `/new`) and "upload existing skill" (user-provided SKILL.md) as two separate features. Matt re-scoped them into a single unified concept:

> **The Registry is where Gen 0 Skills live.** Every browseable Skill — whether curated by us or uploaded by a user — is a `SkillGenome` record in the database. Users can browse the Registry, export any Skill directly, or fork-and-evolve any Skill as the starting point for a new run.

This simplifies everything. There is no longer a "template library" on `/new` — instead, `/new` has a mode toggle: "From scratch" (current flow) or "Fork from Registry" (pick a skill → evolve). Uploaded skills and curated seeds both flow through the same backend code path.

---

## Features in this batch

1. **Curated Seed Library + Registry Integration** — ship 15 hand-authored Gen 0 Skills as `SkillGenome` records in a synthetic "seed-library" run. The Registry page renders them with a curated badge. Users can click a seed to view, export, or fork-and-evolve.
2. **Upload Existing Skill** — user uploads a `.md` or `.zip` → same code path, creates an ad-hoc `SkillGenome` record. Same export / fork-and-evolve actions available.
3. **Anthropic Design System** — retheme the app to match Anthropic's brand (colors + typography) using real values extracted from anthropic.com.
4. **Light / Dark Mode Toggle** — cookie-persisted theme state, depends on §3's CSS-variable groundwork.

---

## 1. Curated Seed Library + Registry Integration

### 1.1 Goal

Populate the Registry with 15 curated Gen 0 Skills that:
- Showcase what the platform can evolve
- Give visitors something to look at before they spend API budget
- Serve as fork-and-evolve starting points for users who don't want to start from scratch

### 1.2 Research phase (IN PROGRESS)

A Sonnet subagent (model: Opus 4.6) has been tasked to write `skillforge/seeds/__init__.py` containing `SEED_SKILLS: list[dict]` with 15 production-quality Gen 0 Skills across:

- Data Engineering: pandas-cleaning, sql-optimization
- Web Development: react-refactor, nextjs-app-router-migration, fastapi-endpoints
- DevOps: dockerfile-authoring, github-actions, terraform-modules
- Code Quality: python-test-generation, docstrings-type-hints
- Security: owasp-audit, secret-scanner
- Documentation: readme-drafting, api-reference, changelog-extraction

Every seed has a full SKILL.md body (150-300 lines), YAML frontmatter (≤250-char description), 2-3 diverse I/O examples, traits tied to real bible patterns. Validated against `docs/skills-research.md` and `bible/patterns/*.md`.

**Output**: `skillforge/seeds/__init__.py` exports `SEED_SKILLS` as plain data. No loader, no migrations — just the data file.

### 1.3 Backend design

**Data path**:

```
skillforge/seeds/__init__.py  (the data)
        │
        ▼
skillforge/db/seed_loader.py  (new — idempotent loader)
        │
        ▼
Synthetic EvolutionRun with id = "seed-library"
  ├── mode = "curated"
  ├── specialization = "Curated Gen 0 Skill Library"
  ├── status = "complete"
  ├── population_size = len(SEED_SKILLS)
  ├── num_generations = 1
  └── generations[0].skills = [SkillGenome × 15]
```

**Why a synthetic run?** Reuse every piece of existing infrastructure:
- `GET /api/runs` already lists all runs → Registry sees the seed library for free
- `GET /api/runs/{id}/skills/{skill_id}` already returns full content → seed viewer works out of the box
- `GET /api/runs/{id}/export?format=...` already exports → download/copy buttons work
- No new endpoints needed for the viewing path
- One DB row per skill, exactly the way real evolved skills are stored — zero special cases

**Idempotent loader**: `seed_loader.py` checks if the `seed-library` run exists; if not, creates it and inserts all 15 genomes. Runs on app startup via the FastAPI lifespan handler. Safe to call on every boot (no duplicates).

**Fork-and-evolve**: a new endpoint `POST /api/evolve/from-skill` takes `{seed_skill_id, specialization?, population_size, num_generations, max_budget_usd}` and creates a new real evolution run where the spawner uses the seed skill as a gen-0 parent instead of the golden template. If the user provides a new specialization string, we use that; otherwise we inherit from the seed's frontmatter description.

**New Spawner entry point**: `spawn_from_parent(parent: SkillGenome, pop_size: int) -> list[SkillGenome]` generates `pop_size - 1` diverse mutations of the parent + keeps the parent itself as the elite. The existing `spawn_gen0` flow is unchanged.

### 1.4 Frontend design

**Registry page changes**:
- Detect the `seed-library` run specially: surface it at the top of the page as a "Curated Library · 15 skills" section, separate from user evolution runs.
- Each seed card shows: title, category pill, difficulty chip, description preview, hover-to-show: "Deploy" and "Fork & Evolve" buttons.
- **Deploy**: opens `/runs/seed-library/skills/{seed_id}` — a new skill-detail view that shows the full SKILL.md rendered + export actions (download zip, download md, copy agent config).
- **Fork & Evolve**: opens `/new?seed={seed_id}` — the new evolution form pre-populated with the seed's frontmatter description as the specialization, with a banner "Forking from: {title}".

**New skill-detail view** (`SeedDetailView.tsx` or reuse `SkillExportPreview.tsx`):
- Route: `/runs/:runId/skills/:skillId` (new)
- Fetches via existing `/api/runs/{runId}/skills/{skillId}` endpoint
- Renders SKILL.md body via `react-markdown` using the same `.bible-prose` styles
- Left column: full SKILL.md, right column: metadata (traits, category, difficulty) + action buttons

**New evolution form changes** (`SpecializationInput.tsx`):
- If `?seed=<id>` query param is present, fetch `/api/runs/seed-library/skills/<id>` on mount and pre-fill:
  - `specialization` = the seed's frontmatter description
  - Shows a banner: "⑂ Forking from: {title} — this run will start with {title} as generation 0 and evolve it forward."
  - On submit, calls `POST /api/evolve/from-skill` instead of `POST /api/evolve`.

### 1.5 File list

| File | Action | Purpose |
|---|---|---|
| `skillforge/seeds/__init__.py` | new (subagent) | `SEED_SKILLS: list[dict]` — 15 curated gen 0 skills |
| `skillforge/db/seed_loader.py` | new | Idempotent loader creates `seed-library` run on startup |
| `skillforge/main.py` | edit | Call `load_seeds()` in lifespan handler |
| `skillforge/api/routes.py` | edit | Add `POST /api/evolve/from-skill` endpoint |
| `skillforge/api/schemas.py` | edit | Add `EvolveFromSkillRequest` schema |
| `skillforge/engine/spawner.py` | edit | New `spawn_from_parent(parent, pop_size)` function |
| `skillforge/engine/evolution.py` | edit | Branch to `spawn_from_parent` when `run.seed_skill_id` present |
| `skillforge/models/run.py` | edit | Add `seed_skill_id: str \| None = None` |
| `skillforge/db/database.py` + `SCHEMA.md` | edit | New `seed_skill_id TEXT` column on `evolution_runs` |
| `frontend/src/components/AgentRegistry.tsx` | edit | Special-case the seed-library section |
| `frontend/src/components/SeedDetailView.tsx` | new | Full SKILL.md render + action buttons |
| `frontend/src/components/SpecializationInput.tsx` | edit | Handle `?seed=<id>` query param |
| `frontend/src/App.tsx` | edit | Route `/runs/:runId/skills/:skillId` |
| `tests/test_seeds.py` | new | Loader idempotency, spawn_from_parent, fork-and-evolve flow |

### 1.6 Open questions (for Matt)

- **Confirm: seeds are reloaded on every boot?** Alternative: only load on first boot, manually re-run if content changes. Proposed: auto-reload on every boot is safest, with content-hash comparison to skip work if unchanged. *Recommended.*
- **Confirm: seeds are immutable from the UI?** No edit/delete buttons — they're reference data. Users who want to modify a seed fork-and-evolve it. *Proposed.*
- **Fork budget default**: when a user forks a seed, what parameters pre-populate? Proposed: `population_size=5, num_generations=3, max_budget_usd=10` (current defaults).

---

## 2. Upload Existing Skill

### 2.1 Goal

Let a user hand us an existing SKILL.md they've already written and we evolve it forward. Same mental model as forking a seed — the uploaded Skill becomes a gen-0 parent in a new evolution run.

### 2.2 Proposed design

**Accept both formats**:
- Single `.md` file → parsed as a SKILL.md. We construct a minimal directory structure in memory with `SKILL.md` at root, no references or scripts.
- `.zip` file → extracted to a temp directory. Expect `SKILL.md` at the root (or one directory deep). Supporting files under `references/`, `scripts/`, `assets/` are preserved.

**Validation**:
- Call existing `validate_skill_structure()` from `engine/sandbox.py` — reuses every Skill Authoring Constraint we already enforce.
- Returns structured errors for the UI to render inline.

**Storage**:
- Upload lands under `/tmp/skillforge-uploads/<upload_uuid>/` for the duration of the session.
- Once the user confirms and submits the evolution run, the upload is copied into the DB as the gen-0 parent SkillGenome and the temp dir is cleaned up.
- Orphaned uploads (no evolution started within 1 hour) are cleaned by OS /tmp sweeping. No dedicated sweeper process needed for MVP.

**Safety**:
- Hard cap: 1MB upload size, 5MB unpacked, 100 files max, allowed extensions only (`.md, .sh, .py, .txt, .json, .yml, .yaml`).
- Zip bomb detection: refuse if compression ratio > 20:1.
- Path traversal protection: reject any entry with `..` or absolute paths.

### 2.3 Backend

**New endpoint**: `POST /api/upload-skill`
- Content-Type: `multipart/form-data`
- Fields: `file` (the .md or .zip)
- Returns: `{upload_id, skill_md_content, frontmatter, validation: {ok: bool, errors: [...]}}`

**New endpoint**: `POST /api/evolve/from-upload` (or reuse `POST /api/evolve/from-skill` with a different discriminator)
- Takes `{upload_id, population_size, num_generations, max_budget_usd, specialization?}`
- Reads the upload from the temp dir, constructs a SkillGenome, kicks off `run_evolution` via the same `spawn_from_parent` path used by seed forking
- Unifies with §1 at this layer

### 2.4 Frontend

**New component `SkillUploader.tsx`**:
- Drag-and-drop zone with "or click to browse" fallback
- Shows upload progress + validation result inline
- On success: preview of parsed SKILL.md frontmatter (name, description, allowed-tools) + "Start Evolution" button
- On failure: red X + list of validation errors

**Mode toggle on `/new`** (SpecializationInput.tsx):
- Three radio options at the top: "From Scratch" / "Upload Existing" / "Fork from Registry"
- "From Scratch" → current flow (textarea + spec assistant)
- "Upload Existing" → hides textarea, shows SkillUploader
- "Fork from Registry" → navigates to `/registry` (or shows an inline seed picker)
- The `?seed=<id>` query param from §1.4 auto-selects "Fork from Registry" mode

### 2.5 File list

| File | Action | Purpose |
|---|---|---|
| `skillforge/api/uploads.py` | new | `POST /api/upload-skill` + validation |
| `skillforge/api/routes.py` | edit | `POST /api/evolve/from-upload` (or unified endpoint) |
| `skillforge/main.py` | edit | Mount uploads router |
| `frontend/src/components/SkillUploader.tsx` | new | Drag-drop + validation UI |
| `frontend/src/components/SpecializationInput.tsx` | edit | 3-mode toggle, conditional render |
| `frontend/src/types/index.ts` | edit | `UploadedSkill` interface |
| `tests/test_uploads.py` | new | Upload validation, zip bomb detection, path traversal |

### 2.6 Open questions (for Matt)

- **Confirm: unify `/api/evolve/from-skill` and `/api/evolve/from-upload` into one endpoint?** Proposed: yes — one endpoint `POST /api/evolve/from-parent` that takes `{parent_source: "registry" | "upload", parent_id: str, ...}`. Cleaner API, same code path.
- **Temp upload retention**: 1 hour hard max? Or session-based?
- **Orphaned upload cleanup**: rely on OS `/tmp` cleanup, or run a background sweeper? Proposed: OS for MVP, add sweeper if it becomes a problem.

---

## 3. Anthropic Design System (research in progress)

### 3.1 Goal

Retheme the app to match Anthropic's brand using real extracted values from anthropic.com — colors, typography, spacing, visual patterns.

### 3.2 Research phase (IN PROGRESS)

A Sonnet subagent has been tasked to fetch anthropic.com + claude.com and extract:
- Color palette (brand orange, neutrals for light/dark, accents)
- Typography (display font, body font, mono font — with free alternatives if paid)
- Spacing + radii
- Key visual treatments (buttons, cards, gradients)

Output lands in `/Users/mjdecour/apps/skillforge/design/anthropic-design-system.md` with a "Proposed Mapping to Our Tailwind Tokens" table ready to drop in.

### 3.3 Implementation (plan)

**CSS variable groundwork**:

```css
/* frontend/src/index.css */
:root {
  /* Light mode (default) */
  --color-primary: 217 119 87;      /* brand orange RGB */
  --color-surface: 250 247 242;     /* warm cream */
  --color-surface-container-lowest: 255 255 255;
  --color-on-surface: 32 28 24;     /* warm ink */
  /* ...etc, ~20 tokens */
}

[data-theme="dark"] {
  --color-primary: 232 151 120;
  --color-surface: 26 22 20;
  --color-surface-container-lowest: 14 12 10;
  --color-on-surface: 245 241 232;
  /* ...etc */
}
```

**Tailwind config** (remap the existing token names to CSS var references — no renames, so every component keeps working):

```js
// frontend/tailwind.config.js
colors: {
  primary: 'rgb(var(--color-primary) / <alpha-value>)',
  surface: 'rgb(var(--color-surface) / <alpha-value>)',
  // ...
}
```

**Typography** — swap `font-display` and `font-sans` values in `tailwind.config.js` to whatever the research agent recommends (likely Spectral + Inter or similar free alternatives to Tiempos + Styrene).

**Visual patterns** — review and update:
- Button styles in `PrimaryButton.tsx`
- Card treatments (currently `rounded-xl bg-surface-container-low`)
- Hero radial gradient (`bg-hero-radial` in `tailwind.config.js`)
- Shadow glow effect (`shadow-glow`)

### 3.4 File list

| File | Action | Purpose |
|---|---|---|
| `design/anthropic-design-system.md` | new (subagent) | Extracted palette + typography spec |
| `frontend/src/index.css` | edit | `:root` + `[data-theme="dark"]` CSS var blocks |
| `frontend/tailwind.config.js` | edit | Remap color tokens + fonts + gradients |
| `frontend/package.json` | edit | Add Google Fonts or font package if needed |
| `frontend/src/components/PrimaryButton.tsx` | edit (if needed) | Adjust for new palette |

### 3.5 Open questions (for Matt)

- **Exact palette**: waiting on research agent output — will confirm the actual hex values from anthropic.com before committing.
- **Paid fonts**: Tiempos + Styrene are paid. Proposed: use Spectral (free Google Font, serif display) + Inter (free Google Font, sans body) as evocative alternatives. Final call lands after research output.
- **Typography swap**: is changing the fonts in-scope, or is this color-only for now?

---

## 4. Light / Dark Mode Toggle

### 4.1 Design

**Storage**: `skld-theme` cookie, 1-year expiry, `SameSite=Lax`, not httpOnly (needs JS access), three values: `"light" | "dark" | "system"`.

**Read path**:
- `frontend/src/hooks/useTheme.ts` — returns `[theme, setTheme]` tuple, resolves `"system"` via `prefers-color-scheme` media query, listens for media-query changes.
- On mount: read cookie → fall back to `"system"` → resolve via media query → set `document.documentElement.dataset.theme`.

**Write path**:
- `setTheme("dark")` → update cookie + `document.documentElement.dataset.theme` → Tailwind re-renders via CSS var swap from §3.

**No-flash script** (inlined in `frontend/index.html` before React boots):

```html
<script>
  (function() {
    var m = document.cookie.match(/skld-theme=(\w+)/);
    var t = m ? m[1] : 'system';
    if (t === 'system') {
      t = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    document.documentElement.dataset.theme = t;
  })();
</script>
```

**UI**: `ThemeToggle.tsx` — 3-state button group (☀ / 🖥 / 🌙) in the AppShell top nav next to the "+ New Evolution" button.

### 4.2 File list

| File | Action | Purpose |
|---|---|---|
| `frontend/src/hooks/useTheme.ts` | new | Cookie-backed theme state hook |
| `frontend/src/components/ThemeToggle.tsx` | new | 3-state button group |
| `frontend/src/components/AppShell.tsx` | edit | Mount ThemeToggle in top nav |
| `frontend/index.html` | edit | Inline no-flash script |

### 4.3 Dependencies

- Blocks on §3's CSS variable groundwork being in place. If §3 palette research completes but Matt hasn't signed off on the exact palette, we can still land the CSS variable *structure* with placeholder values and fill them in once signed off.

### 4.4 Open questions (for Matt)

- **Two states or three?** Proposed: three (light/dark/system). Respecting system preference is the expected behavior in 2026.

---

## Cross-cutting

### Dependency graph

```
§1 (seeds)        ─┐
                   ├─► §2 (upload) (shares spawn_from_parent code path)
                   │
§3 (palette) ─────────► §4 (theme toggle)
```

§1 and §2 are independent of §3/§4. Can ship in parallel or sequentially.

### Proposed execution order

1. **§1 Seed library** — unblocks the Registry UX (empty state looks bad)
2. **§2 Upload existing skill** — same backend code path, additive to `/new`
3. **§3 Anthropic retheme** — visual-only, touches every component but doesn't change behavior
4. **§4 Theme toggle** — depends on §3

Alternatively: §3 first (the screenshot Matt showed is an empty dark Registry — a palette swap before seeds land is pure polish but visible immediately). Matt to pick.

### Testing strategy

- **§1**: unit tests for `seed_loader` idempotency, `spawn_from_parent` diversity, fork-and-evolve end-to-end (mocked LLM).
- **§2**: unit tests for upload validation, zip bomb detection, path traversal rejection. Integration test for upload → evolve flow.
- **§3**: visual QA in both themes. Grep sweep for any hardcoded hex values that slip in.
- **§4**: unit test for `useTheme` hook (cookie read/write, system detection).

### What NOT to do

- No changes to the evolution loop itself (Engine, Breeder, Judging — all untouched)
- No DB migration beyond the single `seed_skill_id` column
- No new authentication/auth (everything stays public)
- No SSR (stays a Vite SPA)
- No paid fonts
- No theme editor UI (user picks one of three; that's it)

---

## Review checklist (for Matt)

Before we build, confirm the answers to these:

- [ ] **Execution order**: §1 → §2 → §3 → §4, or §3 first for immediate polish?
- [ ] **Unified endpoint**: collapse `/api/evolve/from-skill` + `/api/evolve/from-upload` into `/api/evolve/from-parent` with a `parent_source` discriminator?
- [ ] **Seed auto-reload on boot**: yes (with hash-based skip)?
- [ ] **Seeds immutable from UI**: yes — no edit/delete, only view/export/fork?
- [ ] **Upload formats**: both `.md` and `.zip` — confirmed
- [ ] **Typography swap in §3**: do we swap fonts, or color-only?
- [ ] **Theme toggle states**: three (light/dark/system)?

Once signed off, we lock this plan and ship.
