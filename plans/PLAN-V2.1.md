# Plan — v2.1 Production Engine (rich package generation + SKLD-bench integration)

## 1. Context

Step 1 of the v2.1 rollout shipped the SKLD-bench content layer (867 Elixir
challenges across 7 lighthouse families, PRs #9-#17) and a manually-
orchestrated **seed pipeline** run for `elixir-phoenix-liveview` (PR #18 +
follow-ups, then the rich-run-detail rebuild in the current branch). The run
is visible at `https://skld.run/runs/elixir-phoenix-liveview-mock-v1` with
a rich downloadable package, a tab-based run-detail page, a master-detail
lineage view, a competition bracket with per-challenge scores, a Gold
Standard Checklist in the package explorer, and narrative integration
report + competition-score entries in `run.learning_log`.

The run bypasses `run_variant_evolution()` entirely — it is a scaffolded
production of the exact artifact shape we want the real engine to emit
natively. No real sampler, no L1 scorer subprocess, no champion eval, no
run_events emission.

This plan covers **Step 4** of the v2.1 staged roadmap: building the
production engine v2.1 integration so that a real evolution run against
any of the 7 Elixir families produces an artifact **identical in shape to
(and at least as rich as)** the phoenix-liveview seed run, with no manual
orchestration and no post-hoc enrichment scripts.

The short-term prerequisite — running the remaining 6 seed pipelines so
the Registry has content for every family before the real engine ships —
is a **bridge workstream** documented in §2 below. It is not the main
plan; it's the executable playbook Claude uses to produce the rest of the
showcase content while Phase 0 plumbing is built.

### Staged roadmap (this plan is Step 4 of 6)

| Step | Scope | Covered by |
|---|---|---|
| 1. Mock first family | Orchestrate phoenix-liveview seed pipeline by hand | PR #18 (shipped) |
| 1b. Rich run detail | Tab-based run detail page + rich package + rebrand | current branch (`feat/rich-run-detail-page`) |
| 2. Analyze results | Judge phoenix-liveview quality | Manual — done by Matt |
| 3. Mock remaining families | Run 6 more seed pipelines | **§2 of this plan (bridge)** |
| 4. Build real engine | Phase 0-2 of this plan | **§6-§8 of this plan (main)** |
| 5. Run tests locally | Full real pipeline with live agents | **§9 of this plan** |
| 6. Run test in prod | Railway verification | **§9 of this plan** |

Plugin-shipping (bundling all 7 families as `skldbench-elixir-plugin`) is
intentionally scoped OUT — it is its own workstream in
[`plans/BACKLOG.md` — Ship SKLD-bench Elixir families as a Claude Code plugin](./BACKLOG.md).

---

## 2. Bridge — running the remaining 6 seed pipelines (short-term)

**Purpose**: unblock the Registry showcase + produce evidence that the
playbook is family-agnostic before committing to the much larger Phase 0
engine workstream. Each seed pipeline costs ~$28-35 in subscription burn
and ~90-150 minutes of wall-clock time, so this is ~$180 and ~10 hours of
Claude Opus dispatches total.

**Families remaining** (in priority order):

1. `elixir-ecto-sandbox-test` — the hardest-to-fake family (requires real
   test environment reasoning). Produces the most convincing showcase.
2. `elixir-security-linter` — deterministic, fast to score, pattern-based.
3. `elixir-oban-worker` — bounded scope, clear right-answers.
4. `elixir-ecto-schema-changeset` — the "core Ecto" family, high community
   appeal.
5. `elixir-ecto-query-writer` — builds on schema-changeset.
6. `elixir-pattern-match-refactor` — the polish family; transforms legacy
   code into modern idiomatic patterns.

**Playbook**: `scripts/mock_pipeline/NEXT-SEED-RUN-PLAYBOOK.md`. This
document is the source of truth for the exact helper-script invocations
and subagent dispatches Claude follows when running a family. Every
learning from the phoenix-liveview run is baked in.

**Per-run checklist** (condensed — see the playbook for full detail):

1. Checkout `feat/seed-<family-slug>` branch off main (or off the in-flight
   PR branch if consecutive runs are batched)
2. Run `seed_family.py --family-slug <slug>` — loads family + seed.json
3. Run `create_run.py --family-slug <slug>` — creates EvolutionRun +
   12 VariantEvolution rows
4. For each of the N dimensions (1 foundation + N-1 capabilities):
   - `sample_challenges.py --family-slug <slug> --dimension <dim> --num 2`
   - Dispatch Spawner subagent (Opus) — produces variant 2 diverse from seed
   - Dispatch Competitor subagent (Opus) × 2 variants × 2 challenges = 4 runs
   - Parse fenced blocks + run `run_score.py` per competitor output
   - Pick winner (highest mean L1)
   - Call `persist_variant.py` with winner
5. Dispatch Engineer subagent (Opus) to assemble composite from 12 winners
6. Call `finalize_run.py` to persist composite + mark run complete
7. Dispatch 5 enrichment subagents to produce rich package content
   (validate.sh, main_helper.py, guide.md, cheatsheet.md, anti-patterns.md,
   2× starter templates, migration checklist)
8. Call `enrich_package.py --family-slug <slug>` to merge enrichment +
   fixtures into composite.supporting_files
9. Reconstruct integration report heuristically + call
   `persist_integration_report.py`
10. Call `backfill_competition_scores.py` with per-variant per-challenge
    scores from the dispatch records
11. Call `backfill_vevo_challenge_ids.py` (safety — populates NULL fields)
12. Call `export_run_to_seed.py` to dump DB state to JSON under
    `skillforge/seeds/seed_runs/<family-slug>.json`
13. Test the loader: `rm data/skillforge.db && uv run uvicorn … &` and
    verify the run appears via `/api/runs/<run-id>`
14. Commit work, push, open PR, verify on Railway, squash-merge
15. Update CLAUDE.md "Current Status" to reflect progress

**Per-family customizations** that have to be adapted from the phoenix
run:

- **Dimension list** — read from `family.json.foundation_dimension` +
  `family.json.capability_dimensions`
- **Fixtures** — read from `taxonomy/elixir/<slug>/test_fixtures/` directly
  (no hardcoded names); enrichment script iterates the dir
- **Enrichment prompts** — each subagent prompt references the family's
  `research.md` + `README.md` for domain context, so the content is
  actually different per family
- **"Use when..." description** — must be authored per family. The
  composite genome's frontmatter.description MUST match the pattern
  documented in §4 below or the zip export validator rejects it

**Success criteria per bridge run**: the resulting JSON seed loads cleanly
on a fresh DB, the Registry page renders all 7 tabs, the downloaded zip
passes `export_skill_zip()`'s validator, and the composite SKILL.md +
supporting_files count is at least what phoenix-liveview ships (16 files,
≥150KB uncompressed).

---

## 3. What Steps 1 + 1b taught us (consolidated learnings)

These findings drive every design decision in §4-§13. Every one of them
came out of the phoenix-liveview seed run + rich-run-detail rebuild +
rebrand, not from the original v2.0 design.

### 3.1 Skill package shape (the "rich package" bar)

1. **A SKILL.md string is not a skill.** A deployable Claude Agent Skill
   is a directory: SKILL.md + scripts/ (validate.sh + main_helper.py) +
   references/ (guide.md + cheatsheet.md + anti-patterns.md) +
   assets/ (templates) + test_fixtures/ (curated real files). Phoenix-
   liveview shipped 16 files at ~167KB. Anything less feels like a
   placeholder and gets called out in the UI.

2. **Test fixtures must be real, curated, named for their purpose.**
   Phoenix-liveview's 6 fixtures each exhibit a distinct anti-pattern
   (db_in_mount, pubsub_unguarded, kitchen_sink, etc.). Generic
   "example.ex" files undermine the whole package.

3. **References must be substantive.** A 20-line stub `guide.md` is worse
   than no guide. Phoenix-liveview's guide.md is ~1,400 lines with
   numbered section anchors, 11 anti-pattern sections with testing
   guidance, and cross-references to cheatsheet.md. References compete
   with Claude's training data — they have to be better than what Claude
   already knows.

4. **Scripts must be functional.** `scripts/validate.sh` has to exit 0/1
   with real diagnostic output. `scripts/main_helper.py` has to do real
   deterministic work (parser / formatter / generator). Stubs get the
   skill flagged as broken by the Gold Standard Checklist.

5. **The Gold Standard Checklist** (CLAUDE.md §"Gen 0 Seed Quality
   Standard") is enforced in the frontend Package Explorer tab. Every
   composite has to satisfy:
   - SKILL.md with Use when + NOT for clauses + 2-3 examples
   - scripts/validate.sh (functional)
   - scripts/main_helper.py (functional)
   - references/guide.md (substantive)
   - Optional but strongly preferred: cheatsheet.md, anti-patterns.md,
     assets/ templates, test_fixtures/

### 3.2 Frontend UX patterns (the "honest showcase" tone)

6. **No disclaimers.** Matt's explicit directive after seeing a
   "post-facto reconstruction" disclaimer paragraph: delete it. The run
   detail page should present the artifact as what it is without apology.
   Facts only, no caveats. If a field is synthesized, don't call attention
   to that — let the content speak.

7. **Plain-English Overall Assessment first, metrics second.** The top
   card on the page is a prose explanation in human language: "This skill
   knows X, tested with Y, won against Z." The Fitness Radar and
   numerical scores come later. Numbers without interpretation make
   visitors bounce.

8. **Tabs, not scroll.** An 8,500-pixel single-page view buries everything
   below the fold. The current layout is 7 tabs: Composite, Competition,
   Metrics, Tests, Narrative, Lineage, Package. Sticky tab bar with the
   header always visible.

9. **Generation 1 / 1 pill, not "latest generation".** The mock run is
   single-generation. The UI makes this explicit with a pill showing
   "Generation 1 / 1" so visitors don't wonder if there's hidden history.
   Multi-gen future support will update the pill to "Generation 3 / 5"
   etc.

10. **Master-detail > card grid for lineage.** The first cut had 12
    parent cards that expanded in-place below the grid. Matt called out
    that clicking parent #7 scrolled past the click target. The current
    layout is a sticky left rail (always visible) + right panel that
    updates. Parent cards stay in view so comparison is natural.

11. **Stacked > side-by-side for parent→composite sections.** Side-by-
    side comparisons of parent SKILL.md + matched composite section put
    both in narrow columns and make reading harder. Stacking them
    vertically with the parent first and the composite section below
    reads like a story: "here's the parent, here's what made it into the
    composite."

12. **Assembly view, not diff view, for atomic composites.** The
    monolithic `SkillDiffViewer` doesn't make sense for an atomic
    composite (12 parents, not 1). Atomic runs render an
    `AtomicLineageView`; molecular runs still use `SkillDiffViewer`.
    Route-switched on `run.evolution_mode`.

13. **Per-challenge competition breakdown + judging criteria.** The
    original CompetitionBracket showed only the mean fitness per variant.
    Matt wanted to see WHICH challenges each variant won, the individual
    scores, and the explanation of WHY the winner won. The explainer
    card preempts questions like "did you run a baseline?" and "is this
    multi-gen?"

14. **Package tab splits installable from metadata.** Installable section
    (SKILL.md + scripts/ + references/ + assets/ + test_fixtures/) is
    what the user downloads. Metadata section (PACKAGE.md, REPORT.md,
    parents/, challenges/) is reference material for the showcase page.
    Two separate trees with different defaultOpen states. SKILL.md is
    top of the installable tree and selected by default.

15. **Gold Standard Checklist above the file tree.** One-line factual
    statements with green/yellow indicators — not prose. Makes the
    quality bar visible without requiring the visitor to open every file.

### 3.3 Backend / API contract learnings

16. **Report JSON must include `skill_genomes[]` at the top level for
    atomic runs.** The v2.0 report schema nested genomes under
    `generations[]`, but atomic runs have empty `generations` and
    standalone `skill_genomes.run_id` rows. The fix in
    `generate_run_report()` is a new `_build_atomic_genomes_section()`
    that queries directly and returns genomes with full
    `skill_md_content`, `frontmatter`, and `supporting_files`.

17. **Lineage endpoint needs an atomic fallback path.** The v2.0 path
    reads from `run.generations[].skills[]`, which is empty for atomic
    runs. Fix: when empty, query `skill_genomes WHERE run_id = ?`
    directly and synthesize nodes + edges from `parent_ids` and
    `meta_strategy`. Same template as the fix in PR #18 for the
    `/runs/{id}/skills/{skill_id}` endpoint.

18. **Mutation type inference from meta_strategy.** The lineage view
    renders edge labels by mutation type. Map:
    `engineer_composite` → `"assembly"`, `seed_pipeline_winner` /
    `mock_pipeline_winner` / `gen0_seed` → `"selection"`. Without this
    mapping the edges show `"unknown"`.

19. **RunDetail must include `learning_log`.** The response schema in
    `api/schemas.py` initially dropped it. The `RunNarrative` component
    reads `run.learning_log` for timeline entries + parses
    `[integration_report]` and `[competition_scores]` prefixes from it.
    Without exposing the field, the Narrative tab is empty.

20. **`save_genome` upsert doesn't update `skill_md_content`.** The
    `ON CONFLICT` clause in the existing query only updates fitness
    fields. Post-facto enrichment requires a direct
    `UPDATE skill_genomes SET skill_md_content = ?` which `enrich_package`
    does via raw SQL. The real engine has to call `save_genome()` with
    the final content BEFORE fitness is scored, or else allow an
    explicit "replace the body" query path.

21. **Report file cache must be lazy-generated.** The
    `/api/runs/{id}/report` endpoint originally read from a stale
    `data/reports/{run_id}.json` sidecar. If the file was missing (fresh
    DB, first page load) the endpoint returned `{}`. Fix: on 404, call
    `generate_run_report(run_id)` to create and cache the sidecar, then
    return it. Caches correctly on subsequent calls.

22. **SPA routing needs a catch-all.** Direct URL access to
    `/runs/<run_id>` 404'd because FastAPI only served `/` and
    `/assets/*`. Fix: `@app.get("/{full_path:path}")` serving
    `index.html` for any non-API path. The catch-all MUST NOT have a
    `request: Request` parameter — uvicorn interprets it as a required
    query field and rejects normal GETs.

23. **Zip export filename from frontmatter.name, not run_id.** Phoenix-
    liveview shipped as `elixir-phoenix-liveview-mock-v1.zip` on the
    first cut. Matt called that out. Fix: read `run.best_skill
    .frontmatter["name"]` and use that as the filename. Falls back to
    a cleaned run_id only if frontmatter is empty.

24. **`export_skill_zip()` validator requires "Use when" in the
    description.** Any skill whose description doesn't contain the
    literal substring "Use when" (case-sensitive, within the first 250
    chars) gets rejected by the export endpoint. Phoenix-liveview's
    original description had to be rewritten to:
    `"Phoenix 1.7+ LiveView — component-forward architecture with verified routes, HEEx, streams, forms, async mount, pubsub, on_mount authz. Use when writing or reviewing Phoenix 1.7+ LiveView code. NOT for Phoenix 1.6 or older."`
    (223 chars, frontmatter-valid, validator-valid).

### 3.5 Install-test learnings (post-rebrand)

After the rich run detail + rebrand shipped, Matt asked "should we try
installing the skill?" and the install test revealed **three real bugs
that passed every other quality gate**:

24.5. **Bash 3.2 compatibility**: `declare -A` (associative arrays) is
     bash 4+ only. macOS ships bash 3.2. The generated `validate.sh`
     line 49 was `declare -A HITS_BY` — broke on Apple Silicon out of
     the box. Fix: use dynamic variable names via `tr -c '[:alnum:]' '_'`
     munging + `eval` assignment + `${!var:-0}` indirect expansion
     (all bash 3.2-compatible).

24.6. **Subshell variable loss**: `detector | report "key" "fix"` looks
     fine but in bash 3.2 pipelines create subshells, so the hit count
     assignments inside `report` never propagate back to the parent
     shell. Fix: use process substitution `report "key" "fix" < <(detector)`
     which keeps `report` running in the parent. This is a latent bug
     that would also have bitten on bash 4+ without `shopt -s lastpipe`.

24.7. **Regex-based code rewriters are context-blind**: the `migrate`
     subcommand rewrote `live_link|live_patch|live_redirect` call sites
     but didn't know about the surrounding `<%= %>` EEx wrappers — so
     it produced `<%= <.link>...</.link>, class: "btn" %>` which is
     invalid HEEx. It also put `:for` on the outer `<ul>` when the
     pattern was `<ul><%= for %><li>...</li><% end %></ul>` — which
     would duplicate the entire list instead of the items. Fix: (a) a
     post-processing cleanup pass that strips `<%= %>` wrappers around
     `.link` components and absorbs trailing `class:`/`id:` kwargs as
     component attributes, (b) rewrite the for/if block regex to match
     the INNER tag (`<li>`) rather than the outer wrapper.

24.8. **`new-live` UX wart**: passing `dashboard_live` produced
     `MyAppWeb.DashboardLiveLive` (double-Live) because the scaffolder
     appended `_live` to whatever the user passed. Fix: strip a
     trailing `_live` from the input before converting to camel case.

24.9. **Bigger lesson**: every quality gate we had (zip export
     validator, Gold Standard Checklist, Package Explorer indicators,
     line counts, presence checks) was **schema-level**. None of them
     actually *ran the code*. The only way to catch these bugs is to
     install the package and execute every script against a realistic
     fake project. Hence the new §P1.5 **Final-package installation
     test** phase, which is now non-negotiable for every seed run and
     every v2.1 engine run.

### 3.4 Data model + persistence learnings

25. **Narrative persistence via learning_log prefixes.** Instead of
    adding new tables, the integration report and competition scores
    are persisted as prefixed entries in `run.learning_log`. Prefixes:
    `[integration_report] ...`, `[competition_scores] ...`. The
    `RunNarrative` component parses these. This is a pragmatic
    workaround for Step 1b — Phase 0 of the real engine should promote
    both to first-class tables (`competition_results` already exists,
    unused; integration_report deserves its own column on
    `evolution_runs`).

26. **Hash marker stacking.** Every run through the mock_run_loader
    appended `[seed_v<hash>]` to the specialization without stripping
    prior markers. After 3 reloads the subtitle read
    `[mock_v8e9e0f6fc2c6] [mock_v559d4e7f201d] [mock_v3084991f2721]`.
    Fix: the loader strips any `\s*\[(mock|seed)_v[a-f0-9]+\]\s*` via
    regex BEFORE appending a fresh marker. Real v2.1 engine runs should
    not need this marker at all (it's purely a seed-loader invariant).

27. **Rebrand: `mock` → `seed` everywhere user-facing.** The underlying
    question "did this actually run through the product pipeline" is
    irrelevant to the visitor — they care about the output. User-facing
    strings, directory names, loader module names, script names, log
    prefixes all rebranded. Internal run_ids (`-mock-v1`) are frozen for
    phoenix-liveview only to preserve DB continuity; new runs use
    `-seed-v1`.

28. **`seed_pipeline_winner` meta_strategy.** Previously
    `mock_pipeline_winner`. Used by `persist_variant.py` to tag winning
    genomes. The lineage view's mutation-type inference needs to
    recognize both values (old DB rows may still have the old label).

29. **`VariantEvolution.challenge_id` must be populated.** The initial
    mock run left it NULL because `persist_variant.py` didn't know which
    challenge to associate with the vevo. Fix: pass the challenges JSON
    path to `persist_variant.py` and record the first challenge's ID on
    the vevo. `backfill_vevo_challenge_ids.py` exists as a safety net
    for any runs that shipped with NULL.

### 3.6 Design principles (codified from the above)

These are the rules every v2.1 artifact must satisfy:

- **P1. Rich packages are non-negotiable.** Every composite ships a
  directory of 12+ files, not a SKILL.md blob. Enforced at Engineer
  assembly, validated at zip-export, displayed in the Package tab.
- **P2. Honest, disclaimer-free tone.** If a field is reconstructed or
  synthesized, don't call attention to that. Let the content speak.
- **P3. Plain-English before metrics.** Overall Assessment prose card
  always precedes the Fitness Radar. Narrative before dashboards.
- **P4. Production parity.** Whatever the seed pipeline produces via
  manual orchestration, the real engine must produce natively. No
  "the mock does X but the engine doesn't" gaps.
- **P5. "Use when..." in every description.** Enforced by the
  description validator at spawn-time, breed-time, and export-time.
- **P6. No "mock" in user-facing strings.** The word is reserved for
  internal script names + code comments. Visitors never see it.
- **P7. Gen pill labeling.** Every run header shows "Generation N / M"
  even if N=M=1. Makes multi-gen support forward-compatible.
- **P8. Narrative persistence channels.** Integration reports,
  competition scores, and learning-log timeline entries are first-
  class. Phase 0 promotes them from learning_log prefixes to dedicated
  tables.
- **P9. Route-switched views.** Atomic runs render AtomicRunDetail;
  molecular runs render EvolutionResults. Lineage routes similarly
  (AtomicLineageView vs SkillDiffViewer). No shared-component hacks.
- **P10. The Gold Standard Checklist is the quality gate.** If a
  composite fails it, the run is rejected — not post-facto patched.

---

## 4. Production quality bar — the Gold Standard Checklist

Every v2.1 composite MUST satisfy all of the following. This is the gate
for "is the run ready to ship to the Registry." It's enforced in three
places: the Engineer's post-assembly validator, the frontend Package
Explorer display, and `export_skill_zip()` at download time.

### 4.1 SKILL.md

- [ ] YAML frontmatter with `name`, `description`, `allowed-tools`
- [ ] `name` matches regex `^[a-z0-9]+(-[a-z0-9]+)*$`
- [ ] `description` ≤ 250 chars
- [ ] `description` contains the literal substring `"Use when"` (case-
      sensitive)
- [ ] `description` contains an explicit `"NOT for ..."` exclusion
- [ ] Body ≤ 500 lines
- [ ] Body includes `## Quick Start` or `## When to Use`
- [ ] Body includes `## Workflow` with `${CLAUDE_SKILL_DIR}/` script
      references
- [ ] Body includes at least 2 (ideally 3) `## Example` sections with
      input + expected output
- [ ] Body includes `## Common Mistakes` or equivalent anti-pattern
      section

### 4.2 scripts/

- [ ] `scripts/validate.sh` exists, is executable, exits 0 on valid
      input, 1 on invalid input, prints diagnostics
- [ ] `scripts/main_helper.py` exists, has a `main()` function,
      performs real deterministic work (parser / formatter / generator /
      validator), prints structured output
- [ ] Every `${CLAUDE_SKILL_DIR}/scripts/*` referenced in SKILL.md
      actually exists in scripts/

### 4.3 references/

- [ ] `references/guide.md` exists, ≥ 100 lines, has numbered section
      anchors, covers all capability dimensions
- [ ] `references/cheatsheet.md` exists (or is explicitly marked
      optional in the manifest) — quick-reference content
- [ ] `references/anti-patterns.md` exists with at least 5 named
      anti-patterns, each with detection + fix guidance
- [ ] Every `${CLAUDE_SKILL_DIR}/references/*.md` referenced in
      SKILL.md actually exists

### 4.4 assets/ (preferred)

- [ ] At least one `.template` or equivalent starter file when the
      domain admits templating
- [ ] Templates use clear placeholder syntax (e.g., `{{module_name}}`,
      `<MY_APP>`)

### 4.5 test_fixtures/ (preferred)

- [ ] At least 3 curated real files from the family's test_fixtures/
      directory, chosen to cover distinct anti-patterns
- [ ] Each fixture is named for its purpose (not `example.ex`)

### 4.6 Persistence contracts

- [ ] `SkillGenome.supporting_files` dict contains every file above
- [ ] `SkillGenome.frontmatter` is populated (parsed from SKILL.md)
- [ ] `SkillGenome.skill_md_content` holds the SKILL.md body
- [ ] `SkillGenome.meta_strategy = "engineer_composite"`
- [ ] `SkillGenome.parent_ids` lists all N winning variant genome IDs
- [ ] `EvolutionRun.best_skill` points at the composite
- [ ] `EvolutionRun.learning_log` contains an `[integration_report]`
      prefixed entry with conflict notes
- [ ] `EvolutionRun.learning_log` contains a `[competition_scores]`
      prefixed entry with per-variant per-challenge scores
- [ ] Every VariantEvolution row has `status="complete"`,
      `winner_variant_id` set, `challenge_id` set
- [ ] Every Challenge row sampled for the run is persisted with
      `run_id` linkage
- [ ] `competition_results` rows exist, one per (variant × challenge)
      — Phase 0.5 requirement

### 4.7 Registry render test

- [ ] `/api/runs/{id}/report` returns `skill_genomes[]` with the
      composite's supporting_files fully populated
- [ ] `/api/runs/{id}/lineage` returns ≥ (N+1) nodes and ≥ N edges
      for an N-variant composite
- [ ] `/runs/{id}` page renders all 7 tabs without console errors
- [ ] Package Explorer tab shows the Gold Standard Checklist with all
      green indicators
- [ ] Zip export filename reads `<skill-name>.zip` (not
      `*-mock-*.zip`)

---

## 5. Architecture — how the real engine produces the quality bar

The v2.0 engine already does most of the control flow (Taxonomist →
Scientist → Spawner → Competitor → Reviewer → Breeder → Engineer). What
v2.1 extends is: the **content layer** that feeds family-specific
evaluation environments, and the **package shape** that every agent
produces.

### 5.1 Content layer (Phase 0)

```
taxonomy/<lang>/<family-slug>/
├── family.json           # foundation + capabilities + held_out_ids
├── seed.json             # gen-0 foundation + capability variants
├── research.md           # family context / motivation
├── README.md             # family-level description
├── challenges/
│   ├── easy/*.json
│   ├── medium/*.json
│   ├── hard/*.json
│   └── legendary/*.json
├── test_fixtures/*.ex    # immutable inputs for all variants
├── golden/*.ex           # reference answers (not used at runtime)
└── evaluation/
    ├── score.py          # L1 scorer subprocess
    ├── environment.yml   # sandbox dependencies (optional)
    └── calibration.json  # score weights per check
```

The v2.1 family loader walks this tree on boot, validates shape, computes
content hashes, and populates `family_content`, `family_challenges`,
`family_fixtures`, `family_goldens`, and `family_scorer_config` tables.

### 5.2 Rich package production (Phase 1)

```
┌─── spawn_variant_gen0(dim) ───┐
│  Spawner writes:              │
│   SKILL.md                    │
│   scripts/validate.sh         │
│   scripts/<helper>.py         │
│   references/<dim>.md         │
│  (returns manifest)           │
└───────────┬───────────────────┘
            │  × 2 variants × N dims
            ▼
┌─── Competitor × L1 scorer ────┐
│  Per (variant, challenge):    │
│   - sandbox in /tmp/…         │
│   - Competitor writes files   │
│   - run_l1_score() subprocess │
│   - persist competition_result│
└───────────┬───────────────────┘
            │  pick winner per dim
            ▼
┌─── assemble_variants() ───────┐
│  Engineer writes:             │
│   composite SKILL.md          │
│   scripts/ (dedupe + collide) │
│   references/ (merge)         │
│   test_fixtures/ (union)      │
│   assets/ (union)             │
│   integration_report.md       │
└───────────┬───────────────────┘
            │
            ▼
┌─── champion_eval() ───────────┐
│  Hold-out evaluation          │
│  Optional ## Known limitations│
│   section appended to SKILL.md│
│  Failing-challenge outputs    │
│   copied to test_fixtures/    │
└───────────┬───────────────────┘
            │
            ▼
       save_genome(composite)
       save_run(status=complete)
```

### 5.3 Description validator (the "Use when" gate)

A new module `skillforge/validation/description.py` that checks:

```python
def validate_description(desc: str) -> list[str]:
    errors = []
    if len(desc) > 250:
        errors.append("description exceeds 250 chars")
    if "Use when" not in desc:
        errors.append('description missing "Use when" clause')
    if "NOT for" not in desc:
        errors.append('description missing "NOT for" exclusion')
    return errors
```

Called by:
- Spawner at each spawn dispatch (rejects + retries on fail)
- Breeder at each mutation dispatch
- Engineer at composite assembly
- `export_skill_zip()` at download (final safety net)

Retry budget: 2 attempts per spawn. On third failure, record a diagnostic
and move on (the Spawner's output is used as-is with the validator
errors recorded in the genome's metadata).

### 5.4 Narrative persistence promotion

Phase 0.5 adds first-class persistence for what the seed pipeline
stored as learning_log prefixes:

- `competition_results` table (already exists, unused): populated by the
  L1 scorer. One row per (run_id, genome_id, challenge_id).
- `EvolutionRun.integration_report_md` (new TEXT column): populated by
  the Engineer. Replaces `[integration_report]` learning_log entries.
- `EvolutionRun.key_discoveries[]` (new JSON column): derived from
  learning_log + Breeder findings for the narrative timeline.

The frontend's `RunNarrative` component reads from both the new columns
AND the legacy learning_log prefix parser (for seed-run backward
compatibility), so old seed runs continue rendering correctly after the
migration.

---

## 6. Phase 0 — Content layer plumbing (blocking)

Status: **not started**. Required before the engine can dispatch a real
v2.1 run. Everything in this phase is additive to the existing v2.0
engine — no existing code path changes, no schema drops.

### P0.1 — DB migration (additive)

Add columns + tables needed to track the v2.1 content layer. All
additive; no existing columns dropped or renamed.

**Files**:
- `skillforge/db/database.py` — add DDL for new tables + ALTER TABLE
  migrations (SQLite ALTER is limited; use `CREATE TABLE IF NOT EXISTS`
  pattern where possible, full table recreation for anything that needs
  a NOT NULL constraint added)

**New tables**:
- `family_content` — one row per SKLD-bench family on disk:
  `family_slug`, `spec_version`, `challenge_total`, `held_out_ids_json`,
  `research_cites`, `tier_methodology`, `content_hash`, `loaded_at`
- `family_challenges` — one row per challenge file per family:
  `family_slug`, `challenge_id`, `tier`, `prompt`,
  `expected_outputs_json`, `scoring_json`, `is_held_out`, `source_path`
- `family_fixtures` — `family_slug`, `filename`, `content`, `purpose`
- `family_goldens` — `family_slug`, `challenge_id`, `content`,
  `score_against_golden` float
- `family_scorer_config` — `family_slug`, `scorer_script_path`,
  `environment_yaml_path`, `pass_threshold`, `calibration_json`

**New columns on `skill_genomes`**:
- `package_metadata TEXT` — JSON dict for any non-file package-level
  info (manifest, version, changelog)

**New columns on `evolution_runs`**:
- `integration_report_md TEXT` — Engineer's integration report (§5.4)
- `key_discoveries_json TEXT` — derived discoveries for the narrative
- `champion_eval_scores_json TEXT` — per-challenge champion eval results

**Migration tests**:
- `tests/db/test_migration_v21.py` — verify schema round-trip, no data
  loss on re-boot

### P0.2 — v2.1 family loader

A new bootstrap step that reads every `taxonomy/<lang>/<family-slug>/`
directory and hydrates the `family_*` tables.

**Files**:
- `skillforge/db/v21_family_loader.py` (new) — mirror of the existing
  `seed_loader.py` + `taxonomy_seeds.py` pattern
- `skillforge/main.py` — add `await load_v21_families()` to the lifespan
  handler after `load_taxonomy()` and before `load_seed_runs()`

The loader must:
1. Walk `taxonomy/<lang>/*` directories
2. For each family, validate against `taxonomy/<lang>/SCHEMAS.md` file
   shapes
3. Read `family.json`, `seed.json`, all challenge files, fixtures,
   goldens, evaluation artifacts
4. Populate the tables via new queries
5. Be idempotent (re-runs only write deltas)
6. Be fail-soft (a bad family logs + is skipped; other families still
   load)

**Tests**:
- `tests/db/test_v21_family_loader.py` — load a synthetic family folder,
  verify rows, content_hash match on re-run
- `tests/db/test_v21_family_loader_malformed.py` — graceful skip on
  invalid family

### P0.3 — Evolution dispatcher v2.1 mode

Extend `skillforge/engine/evolution.py` to route v2.1 runs through a new
path that knows about family content. When the dispatcher sees an
evolution request against a v2.1 family slug (detected via
`family_content` table presence), it:

1. Fetches the family's foundation + capability dimension list from
   `family.json`
2. For each dimension, creates a `VariantEvolution` row
3. Invokes `run_variant_evolution()` per dimension with a v2.1-aware
   config that includes:
   - The family's scorer path
   - The family's environment file (sandbox provisioning)
   - Sampled challenges from `family_challenges` (excluding held-out)
   - Per-variant output sandbox dirs
4. After all dimensions complete, invokes the Engineer for assembly
5. After assembly, invokes the **held-out champion eval**
6. Emits run_events at every transition (§P0.6)

**Files**:
- `skillforge/engine/evolution.py` — route v2.1 calls through a new
  `run_v21_evolution()` function
- `skillforge/engine/variant_evolution.py` — accept a `family_config`
  parameter containing `scorer_path`, `environment_path`,
  `challenge_pool`

### P0.4 — L1 scorer subprocess integration

The seed pipeline ran each family's `evaluation/score.py` via a direct
subprocess call (`scripts/mock_pipeline/run_score.py`). The production
engine should do the same, with proper sandbox isolation and output
capture.

**Files**:
- `skillforge/engine/scoring.py` (new) — `async def run_l1_score(genome,
  challenge, family_config) -> L1Result` that:
  1. Creates a temp sandbox dir
  2. Writes the genome's output files into it (from the competitor
     dispatch)
  3. Invokes `python <family.scorer_script_path> --challenge <path>
     --output <sandbox>` via asyncio subprocess
  4. Parses the JSON result
  5. Returns `{score, passed, diagnostics, per_check_weights}`
  6. Cleans up the sandbox
- `skillforge/engine/variant_evolution.py` — replace any mocked fitness
  assignment with a call to `run_l1_score()` per (variant × challenge)

### P0.5 — Competition results persistence

The seed pipeline lost per-(variant, challenge) scores because the DB
didn't persist them anywhere first-class — they had to be backfilled
via the `[competition_scores]` learning_log prefix convention. The
production engine persists every score directly.

**Files**:
- `skillforge/db/database.py` — activate the existing
  `competition_results` table (schema already exists)
- `skillforge/db/queries.py` — `save_competition_result()`,
  `get_competition_results_for_run()`, `get_competition_results_for_genome()`
- Every `run_l1_score()` call persists a row
- The Reviewer can later aggregate these for L3+ analysis

**Frontend impact**: `RunNarrative` + `CompetitionBracket` read from
`/api/runs/{id}/competition_results` instead of parsing learning_log
prefixes. The legacy prefix parser remains as a fallback for old seed
runs.

### P0.6 — run_events emission

The seed pipeline didn't emit any run_events. The production engine
emits every state transition so the frontend can render a retrospective
timeline.

**Files**:
- `skillforge/engine/events.py` — verify the event schema is called at
  every milestone
- `skillforge/engine/v21_evolution.py` — emit: `run_started`,
  `family_loaded`, `decomposition_complete`,
  `variant_evolution_started/complete` × N,
  `assembly_started/complete`, `champion_eval_started/complete`,
  `evolution_complete`

### P0.7 — Description validator (Use when gate)

A new validation module enforced at spawn, breed, assemble, and export
time. Blocks skill descriptions that don't contain "Use when" and "NOT
for". See §5.3.

**Files**:
- `skillforge/validation/description.py` (new)
- `skillforge/agents/spawner.py` — call validator, retry budget of 2
- `skillforge/agents/breeder.py` — call validator, retry budget of 2
- `skillforge/agents/engineer.py` — call validator, block assembly on
  final failure
- `skillforge/engine/export.py` — call validator as a safety net

**Tests**:
- `tests/validation/test_description.py` — unit tests for the edge
  cases phoenix-liveview hit

---

## 7. Phase 1 — Rich package generation (the hotness)

Status: **spec only**. Required to hit the §4 Gold Standard Checklist.

### P1.1 — Spawner produces full directory packages

**Current state**: Spawner produces a single `<variant>...</variant>`
block containing only SKILL.md.

**Target state**: Spawner produces a full directory package per variant:

```
<family-slug>-<dimension>-<approach-slug>/
├── SKILL.md                # frontmatter + body (as before)
├── scripts/
│   ├── validate.sh         # dimension-specific structural check
│   └── <tool>.py           # dimension-specific helper (optional)
├── references/
│   └── <dimension>.md      # focused reference for this dimension
└── test_fixtures/          # (optional — reused from family dir)
```

**Implementation**:
- Spawner prompt instructs the subagent to use its Write tool to emit
  each file to a pre-specified output dir
- Spawner output format: a JSON manifest listing the files written,
  paths relative to the package root, byte counts
- `skillforge/agents/spawner.py::spawn_variant_gen0` collects the
  manifest and builds a `SkillGenome.supporting_files` dict from disk
- Description validator runs BEFORE persistence — reject + retry
- The existing Spawner skill at `.claude/skills/spawner/SKILL.md`
  already describes this shape — make the engine actually honor it

**Cost impact**: each Spawner dispatch roughly doubles in token budget
(from ~800 for a SKILL.md block to ~1600 for a directory with scripts
+ reference). At 2 variants × N dimensions × N families still well
under the per-run budget cap.

### P1.2 — Engineer merges directory packages

**Current state**: Engineer merges N SKILL.md strings into one composite
SKILL.md. Nothing else.

**Target state**: Engineer merges N directory packages into one composite
directory package:

1. **SKILL.md merge**: threads the foundation's architectural skeleton +
   capability workflows into one coherent body. Description validator
   runs on output.
2. **scripts/ merge**: collect each parent's `scripts/*` files. Dedupe
   by name. Resolve collisions by prefixing with dimension slug
   (`validate.sh` → `validate_streams.sh`). Verify no two scripts have
   identical names post-resolution.
3. **references/ merge**: keep per-dimension files + create a top-level
   `references/guide.md` that links/TOCs them all. Cheatsheet and
   anti-patterns are cross-dimension and written once at assembly.
4. **test_fixtures/ merge**: union of every parent's test_fixtures/.
5. **assets/ merge**: union of every parent's assets/.
6. **integration_report.md**: the Engineer produces a structured
   conflicts/resolutions notes block. Persist to
   `EvolutionRun.integration_report_md` (NEW COLUMN) — not to
   learning_log anymore (that was a seed-pipeline workaround).

**Files**:
- `skillforge/agents/engineer.py::assemble_variants` — rewrite to handle
  directory inputs and produce a directory output
- `.claude/skills/engineer/SKILL.md` — update merge contract
- `skillforge/engine/variant_evolution.py` — wire the new output shape

### P1.3 — Champion eval + Known Limitations section

After assembly, before persistence, run the **champion eval** step:
execute the composite against the N held-out challenges. Capture:

- Per-challenge generalization score (did the composite generalize?)
- Specific failure modes (which `must_contain` substrings did it miss?)
- Generated output files (from the competitor dispatch per challenge)

From this, optionally append to the package:

- `test_fixtures/champion_eval_<challenge_id>.ex` — one file per
  failure, copied from the genome's output dir. Serves as "here's what
  the skill produced for a hard test case."
- `## Known limitations` section appended to SKILL.md listing any
  held-out challenges that failed. This is honesty about the skill's
  gaps (aligns with §P2 "disclaimer-free but truthful" principle).

**Files**:
- `skillforge/engine/champion_eval.py` (new) — the held-out evaluator
- `skillforge/engine/variant_evolution.py` — call after assembly,
  before final save_genome

### P1.4 — Enrichment agent fallback (optional)

If the Spawner's per-variant output lacks certain package elements
(e.g., the Phoenix variant doesn't write a `main_helper.py` because
Elixir doesn't need a Python helper per-variant), the engine dispatches
focused enrichment subagents AFTER assembly to fill the gap.

This is the pattern the phoenix-liveview seed run used post-hoc via
`scripts/mock_pipeline/enrich_package.py` + 5 subagent dispatches
(validate.sh, main_helper.py, guide.md, cheatsheet.md, anti-patterns.md,
2× templates, migration checklist). The real engine should:

1. Run a post-assembly completeness check against §4 Gold Standard
2. For each missing or stub file, dispatch a focused enrichment subagent
   with the composite SKILL.md as context + the gap slot's target path +
   family's research.md for domain context
3. Collect outputs and UPDATE `composite_genome.supporting_files`
4. Re-check §4 compliance; fail the run on persistent gaps

**Files**:
- `skillforge/engine/enrichment.py` (new) — dispatches the focused
  subagents
- `.claude/skills/enricher/SKILL.md` (new, optional) — prompt for the
  enrichment agent

**Decision point**: whether to build the enrichment path or to instead
require the Spawner / Engineer to produce the full package natively. I
recommend building the enrichment path initially — it matches what the
seed pipeline proved works, and lets us ship v2.1 without a Spawner
rewrite. Iterate to native production later if the enrichment round-
trip is too slow or expensive.

### P1.5 — Final-package installation test (MANDATORY)

**Why this phase exists**: the phoenix-liveview seed run shipped with three
real bugs that only surfaced when Matt asked "should we try installing the
skill?" after everything else said green:

1. `scripts/validate.sh` used `declare -A` — works on Linux (Railway), broken
   on macOS bash 3.2 at line 49
2. `scripts/validate.sh` piped detectors into `report` via `|` — the bash
   3.2 subshell swallowed hit counts so the summary showed clean even when
   hits existed
3. `scripts/main_helper.py migrate` produced malformed Elixir: `<%= <.link>
   %>` wrappers, lost `class:` attrs, `:for` landed on the outer `<ul>`
   instead of the inner `<li>`, `live_redirect user.name` unmatched

The Gold Standard Checklist passed. The zip export validator passed. The
Package Explorer showed 14 supporting files and all green indicators. Yet
the zip, when actually installed and run, was broken.

**The lesson**: static schema checks + file-existence checks + line counts
are necessary but not sufficient. Every composite must be **installed and
run** as part of the pipeline before it's marked `status=complete` and
published to the Registry.

**Implementation**:

Files:
- `skillforge/engine/install_test.py` (new) — `async def
  run_install_test(genome, family_config) -> InstallTestResult` that:
  1. Exports the composite genome's supporting_files to a temp sandbox
     directory structured as a deployable skill package
  2. Creates a realistic fake project dir with a mix.exs (or equivalent
     for non-Elixir families) and the skill dropped into `.claude/skills/`
  3. Copies the family's curated test_fixtures into the fake project's
     source directory as known-bad input for the scanner
  4. Invokes every `scripts/*.sh` and `scripts/*.py` from the installed
     path via asyncio subprocess with macOS bash 3.2 compatibility
     verification (runs `bash --version` first, uses the system bash
     explicitly if possible)
  5. Runs the scanner/validator against the known-bad fixtures and
     asserts: (a) at least one hit is reported, (b) summary shows real
     hit counts, (c) exit code is 1 (FAIL)
  6. Runs the migrator against a known-bad legacy file and asserts:
     (a) output is non-empty, (b) a syntax check passes (parse with a
     family-specific parser when available, heuristic regex check
     otherwise)
  7. Runs any scaffolder (`new-live`, `new-worker`, etc.) and asserts
     the generated file passes the scanner with zero hits
  8. Runs validator scripts against the generated files and asserts
     PASS (exit 0)
  9. Returns detailed diagnostics for any failure

- `skillforge/engine/variant_evolution.py` — after `assemble_variants()`
  and before `save_genome(composite)`, call `run_install_test()`. On
  any failure, set `run.status="install_test_failed"` and store the
  diagnostics in `run.failure_reason`. Do NOT mark the run complete.
  The frontend treats `install_test_failed` as a distinct error state
  and surfaces the specific script failures in the run detail page.

- `tests/engine/test_install_test.py` — unit tests covering:
  - Golden-path run (all scripts pass)
  - Bash 3.2 incompatibility detection (inject a `declare -A` into a
    test script, expect failure)
  - Malformed migrate output detection (inject an unclosed `<%= %>`
    wrapper, expect failure)

**Pipeline flow**:

```
... → variant_evolutions complete → assemble_variants() → composite
     → champion_eval() → composite gains "Known limitations" section
     → run_install_test(composite) ← NEW STEP
          ↓ success
     → save_genome(composite) + run.status = complete
          ↓ failure
     → run.status = install_test_failed
     → run.failure_reason = <diagnostics>
     → frontend shows install_test_failed state with specific errors
     → operator fixes enrichment prompts or supporting_files manually
     → re-run install test
```

**Fake project generation**:

Per-family fake projects need to be realistic enough that scanners and
linters actually exercise the real code paths. For the 7 Elixir families:

| Family | Fake project shape |
|---|---|
| elixir-phoenix-liveview | `mix.exs` with `phoenix_live_view` dep + `lib/my_app_web/live/` with test_fixtures copied in |
| elixir-ecto-schema-changeset | `mix.exs` with `ecto` + `lib/my_app/` with schema test_fixtures |
| elixir-ecto-sandbox-test | `mix.exs` + `test/` dir with sandbox config test_fixtures |
| elixir-ecto-query-writer | `mix.exs` + `lib/my_app/` with query test_fixtures |
| elixir-oban-worker | `mix.exs` + `lib/my_app/workers/` with worker test_fixtures |
| elixir-pattern-match-refactor | `mix.exs` + `lib/` with match test_fixtures |
| elixir-security-linter | `mix.exs` + `lib/` + `deps/` with security test_fixtures |

The fake project generators live in `skillforge/engine/fake_projects/<family>.py`
and each returns a path to a temp dir with the correct shape.

**Subagent install test (optional but recommended)**:

After the deterministic scripts pass, dispatch a separate subagent with
access to the installed skill and ask it to write a small feature in the
fake project. The subagent's output is then run through the skill's own
scanner. If the scanner reports zero hits, the "dogfood" test passes —
meaning the skill is self-consistent (a Claude Code agent using the
skill produces code that the skill's own tools consider clean).

This is optional because it costs a subagent dispatch (~$0.50-1.00 per
run) and adds ~3-5 min wall-clock. It's strongly recommended for the
first real v2.1 engine run of each family; afterwards it can be toggled
via `SKILLFORGE_INSTALL_TEST_DOGFOOD=1`.

**Success criteria gate**:

No run is allowed to ship to prod without the install test passing.
This is enforced at:
1. `run_v21_evolution()` — returns early with `install_test_failed`
   status if any check fails
2. `export_skill_zip()` — refuses to export a genome whose parent run
   is in `install_test_failed` state (secondary safety net)
3. `mock_run_loader.load_mock_runs()` — skips any seed JSON whose
   run.status isn't `complete` (tertiary safety net for legacy seed
   runs)

### P1.6 — Scripter agent (stretch, OPTIONAL)

A dedicated agent for writing `scripts/main_helper.*`. Given the
enrichment path covers this gap, Scripter is a stretch goal and can be
deferred to post-v2.1. Tracked in BACKLOG.md.

---

## 8. Phase 2 — Frontend parity (must render real-engine output cleanly)

Status: **components already exist** from Step 1b. Phase 2 verifies they
render real-engine output without modifications, and documents the API
contracts the real engine must satisfy.

### 8.1 Component inventory (shipping on this branch)

These components must continue working with real-engine-produced runs:

| Component | File | Data source |
|---|---|---|
| `AtomicRunDetail` | `frontend/src/components/AtomicRunDetail.tsx` | `/api/runs/{id}` + `/api/runs/{id}/report` + `/api/runs/{id}/lineage` + `/api/families/{family_id}/variants` |
| `OverallAssessment` | `frontend/src/components/OverallAssessment.tsx` | Composite genome fields + avg fitness |
| `PipelineOverview` | `frontend/src/components/PipelineOverview.tsx` | Run counts + dimension list |
| `CompetitionBracket` | `frontend/src/components/CompetitionBracket.tsx` | Variants + competition_results |
| `FitnessExplainer` | `frontend/src/components/FitnessExplainer.tsx` | Report metrics |
| `PerDimensionFitnessBar` | `frontend/src/components/PerDimensionFitnessBar.tsx` | Variants |
| `RichVariantBreakdown` | `frontend/src/components/RichVariantBreakdown.tsx` | Variants |
| `ChallengeGallery` | `frontend/src/components/ChallengeGallery.tsx` | `run.challenges` |
| `RunNarrative` | `frontend/src/components/RunNarrative.tsx` | `run.learning_log` + `run.integration_report_md` |
| `AtomicLineageView` | `frontend/src/components/AtomicLineageView.tsx` | Lineage endpoint |
| `CompositeMarkdownView` | `frontend/src/components/CompositeMarkdownView.tsx` | `best_skill.skill_md_content` |
| `PackageExplorer` | `frontend/src/components/PackageExplorer.tsx` | `best_skill.supporting_files` |

### 8.2 API contracts (Phase 0 must satisfy these)

**`GET /api/runs/{id}`** — `RunDetail` schema:
- MUST include `learning_log: list[str]`
- MUST include `integration_report_md: str | None` (new field from
  Phase 0 migration)
- MUST include `evolution_mode: "atomic" | "molecular"`
- MUST include `family_id`, `challenges: list[Challenge]`

**`GET /api/runs/{id}/report`** — lazy-generated JSON report:
- MUST include `skill_genomes[]` as a top-level array with full
  `skill_md_content`, `frontmatter`, `supporting_files` (this is the
  §20 fix from learnings)
- MUST include `summary.aggregate_fitness` computed from active
  variants (not from empty `generations[]`)
- MUST include `summary.dimensions_evolved`,
  `summary.total_cost_usd`, `summary.duration_seconds`
- MUST include `variant_evolutions[]` with `winner_variant_id`,
  `challenge_id`, `status`
- MUST include `integration_report` parsed from learning_log (legacy)
  OR `run.integration_report_md` (new)

**`GET /api/runs/{id}/lineage`** — atomic-mode aware:
- MUST return ≥ (N+1) nodes for an N-variant composite
- MUST return edges with `mutation_type` inferred from
  `meta_strategy`: `engineer_composite` → `"assembly"`,
  `seed_pipeline_winner` / `mock_pipeline_winner` / `gen0_seed` →
  `"selection"`
- Atomic fallback: if `run.generations` is empty, query
  `skill_genomes WHERE run_id = ?` directly

**`GET /api/runs/{id}/competition_results`** — NEW endpoint:
- Returns rows from the `competition_results` table for this run
- Used by `CompetitionBracket` to render per-challenge scores

**`GET /api/runs/{id}/export?format=zip`** — download endpoint:
- Filename from `run.best_skill.frontmatter["name"]` (not `run_id`)
- Validator: `description` must contain "Use when"; reject with 422
  if not
- Package contents: full `supporting_files` + SKILL.md

### 8.3 Route-switching contract

`App.tsx` switches `/runs/:runId` to:
- `<AtomicRunDetail>` when `run.evolution_mode === "atomic"`
- `<EvolutionResults>` (legacy v2.0) when `evolution_mode === "molecular"`

`App.tsx` switches `/runs/:runId/diff` to:
- `<AtomicLineageView>` when `run.evolution_mode === "atomic"`
- `<SkillDiffViewer>` (legacy) when `evolution_mode === "molecular"`

Catch-all SPA route: `@app.get("/{full_path:path}")` serves `index.html`
for any non-API path. MUST NOT declare `request: Request` parameter
(uvicorn treats it as required query).

### 8.4 Migration of legacy seed-run narrative parsing

The frontend today parses `[integration_report]` and
`[competition_scores]` prefixes from `run.learning_log`. After Phase 0
migration, `RunNarrative` + `CompetitionBracket` prefer the new
first-class fields (`integration_report_md`, `competition_results`
endpoint) and fall back to learning_log parsing for legacy runs (the
phoenix-liveview seed run + any bridge runs produced before Phase 0
ships).

Both paths coexist permanently — old runs never get automatically
re-formatted.

---

## 9. Phase 3 — Live integration tests

### P3.1 — Local end-to-end test

Run a full v2.1 evolution locally against `elixir-phoenix-liveview`:

```bash
SKILLFORGE_LIVE_TESTS=1 uv run pytest tests/test_v21_phoenix_liveview_live.py
```

**Expected outcome**: a complete run with 12 dimensions evolved, a
composite produced, a rich package (SKILL.md + scripts/ + references/ +
test_fixtures/ + assets/) persisted to `skill_genomes.supporting_files`,
competition_results populated, integration_report_md populated,
run_events emitted, all visible on the localhost Registry.

**Pass criteria**:
- Run completes within 15 minutes and under $5 budget on Haiku tier
- Gold Standard Checklist all green
- Composite fitness ≥ 0.85 against held-out challenges

### P3.2 — Production parity test

Deploy to Railway. Trigger a v2.1 run against `elixir-phoenix-liveview`
(or another family) through the production UI. Verify:

1. WebSocket events stream in real time
2. Sandbox isolation works (concurrent dispatches don't collide)
3. Cost tracking stays within budget
4. Final package downloadable via
   `/api/runs/{id}/export?format=skill_dir`
5. Package is a valid deployable Claude Agent Skill — runs through
   `validate.sh`, `main_helper.py` works on a real Phoenix project
6. Registry page renders all 7 tabs without errors
7. Gold Standard Checklist satisfied

### P3.3 — Seed-run backward compatibility check

After Phase 0 ships, reload the fresh DB and verify the existing
phoenix-liveview seed run still renders correctly:

1. `rm data/skillforge.db && uvicorn skillforge.main:app &`
2. `curl localhost:8000/api/runs/elixir-phoenix-liveview-mock-v1`
3. Verify all 7 tabs render, Package Explorer shows 16 files, Narrative
   parses integration_report + competition_scores from learning_log
   (legacy path), Lineage shows 13 nodes + 12 edges
4. No regression on pre-Phase-0 content

---

## 10. Phase 4 — Decommission mock pipeline scaffold

Once Phase 3 ships and real runs are stable for at least a week:

**Delete**:
- `scripts/mock_pipeline/*` (all Python helper scripts)
- `skillforge/seeds/mock_run_loader.py` (replaced by real run persistence
  — real runs just save to the DB directly and the Railway volume
  preserves them)

**Keep**:
- `skillforge/seeds/seed_runs/*.json` — frozen reference artifacts.
  Useful as "this is what v2.1 output looked like at launch." Never
  reload them into a DB that already has real runs — they'd duplicate.

**Timeline**: leave the mock in place until at least 3 real v2.1 runs
have landed on prod and a week has passed with no regressions. Then
delete in a single cleanup PR titled `chore: decommission mock pipeline
scaffold`.

---

## 11. Critical files

### 11.1 New files (Phase 0 + Phase 1)

- `skillforge/db/v21_family_loader.py`
- `skillforge/engine/scoring.py`
- `skillforge/engine/v21_evolution.py`
- `skillforge/engine/champion_eval.py`
- `skillforge/engine/enrichment.py`
- `skillforge/validation/description.py`
- `tests/db/test_migration_v21.py`
- `tests/db/test_v21_family_loader.py`
- `tests/validation/test_description.py`
- `tests/test_v21_phoenix_liveview_live.py`
- `.claude/skills/enricher/SKILL.md` (optional, P1.4)

### 11.2 Modified files (Phase 0 + Phase 1)

- `skillforge/db/database.py` — DDL for new tables + new columns
- `skillforge/db/queries.py` — new CRUD helpers
- `skillforge/engine/evolution.py` — v2.1 dispatch routing
- `skillforge/engine/variant_evolution.py` — rich package support +
  scoring wiring
- `skillforge/agents/spawner.py` — directory output + manifest +
  validator integration
- `skillforge/agents/breeder.py` — validator integration
- `skillforge/agents/engineer.py` — directory merge + integration report
  to first-class column
- `skillforge/engine/export.py` — validator safety net
- `skillforge/api/routes.py` — `/competition_results` endpoint + expose
  integration_report_md in RunDetail
- `skillforge/api/schemas.py` — RunDetail + RunReport schema updates
- `.claude/skills/spawner/SKILL.md` — verify directory output described
- `.claude/skills/engineer/SKILL.md` — update merge contract
- `skillforge/main.py` — lifespan `load_v21_families`

### 11.3 Read-only reference (Phase 0 uses, doesn't modify)

- `plans/SPEC-V2.1.md` — architecture spec (shipped)
- `taxonomy/elixir/SEEDING-PLAN.md` — content plan (shipped)
- `taxonomy/elixir/SCHEMAS.md` — file shapes (shipped)
- `scripts/mock_pipeline/*` — reference implementation of what the real
  engine needs to reproduce (Phase 4 deletes these)
- `skillforge/seeds/seed_runs/*.json` — frozen seed run artifacts

---

## 12. Out of scope (explicitly deferred)

- **Multi-generational evolution** (Gen 2, Gen 3, ...). v2.1 is
  single-gen per dimension. Multi-gen is a separate plan, and Phase 0's
  run_events + fitness history schema leaves room for it without
  blocking.
- **L2-L5 reviewer layers** (trigger accuracy, trace analysis,
  comparative pairwise, trait attribution). v2.1 ships with L1 only.
  L2+ is a separate workstream and the Reviewer agent skill already
  describes them.
- **Cross-family composition** — a skill spanning two families requires
  a meta-family abstraction that doesn't exist yet. Out of scope until
  v2.2 at earliest.
- **Plugin-shipping workstream** — bundling all 7 families as
  `skldbench-elixir-plugin` with keyword-triggered hooks. Tracked in
  [BACKLOG.md — Ship SKLD-bench Elixir families as a Claude Code plugin](./BACKLOG.md).
  Depends on v2.1 shipping + all 7 families having rich composites.
- **Scripter agent** — a dedicated agent for writing
  `scripts/main_helper.*`. Covered by P1.4 enrichment path for v2.1;
  promoted to first-class in a later plan.
- **BYOK (bring your own key)** — still unresolved. Tracked in
  BACKLOG.md.

---

## 13. Success criteria

A v2.1 run is "done" when ALL of the following hold:

1. A user clicks "New Evolution" → "Elixir Phoenix LiveView" on
   skld.run and the real engine dispatches Spawners, Competitors,
   Reviewers, and the Engineer natively (no manual orchestration).
2. The run completes within its budget cap with real L1 fitness signal
   from subprocess-invoked `score.py`.
3. The Registry shows the run with a composite skill at fitness ≥ 0.85
   against training pool AND ≥ 0.75 against held-out pool.
4. The Gold Standard Checklist (§4) reports all green indicators in
   the Package Explorer tab.
5. The user downloads the `.zip` and it passes `export_skill_zip()`
   validators (Use when present, NOT for present, description ≤ 250,
   supporting_files populated, scripts/ functional, references/
   substantive).
6. Dropping the extracted skill into `.claude/skills/
   elixir-phoenix-liveview/` in a real Phoenix project makes Claude's
   LiveView code measurably better on the held-out challenges (manual
   validation).
7. `scripts/validate.sh` produces accurate anti-pattern diagnostics on
   a real messy Phoenix project.
8. `python scripts/main_helper.py scan lib/` on a messy Phoenix project
   reports hits; `python scripts/main_helper.py migrate` actually
   rewrites patterns.
9. The existing phoenix-liveview seed run continues rendering correctly
   after Phase 0 migration (backward compatibility).
10. No disclaimers on the run detail page. Every field reads as factual
    content without hedge language.
11. The §P1.5 install test passes end-to-end: the composite's scripts run
    on macOS bash 3.2, the migrate produces syntactically valid output,
    the scaffolder produces a scanner-clean file, and a dogfood subagent
    test writes a small feature using the skill and scans clean.

When all 11 criteria are met, v2.1 is shipped. At that point the bridge
seed-pipeline scaffolding (§2 + `scripts/mock_pipeline/*`) can be
scheduled for decommissioning (§10).

---

## 14. See also

- [`plans/BACKLOG.md`](./BACKLOG.md) — future workstreams, including
  the plugin-shipping path that depends on this plan
- [`plans/SPEC-V2.1.md`](./SPEC-V2.1.md) — v2.1 architecture spec
  (shipped)
- [`plans/SPEC-V2.0.md`](./SPEC-V2.0.md) — v2.0 architecture spec
- [`plans/PLAN-V2.0.md`](./PLAN-V2.0.md) — v2.0 implementation plan
  (shipped via PRs #2-#7)
- [`taxonomy/elixir/SEEDING-PLAN.md`](../taxonomy/elixir/SEEDING-PLAN.md)
  — SKLD-bench content authoring plan (shipped via PRs #9-#17)
- [`taxonomy/elixir/SCHEMAS.md`](../taxonomy/elixir/SCHEMAS.md) —
  v2.1 family folder file shapes
- [`scripts/mock_pipeline/NEXT-SEED-RUN-PLAYBOOK.md`](../scripts/mock_pipeline/NEXT-SEED-RUN-PLAYBOOK.md)
  — the short-term bridge playbook for running the remaining 6 seed
  pipelines
- `journal/012-skld-bench-content-workstream.md` — the story of the
  SKLD-bench authoring session
- `journal/013-phoenix-liveview-seed-run.md` (to be written) — the
  story of the phoenix-liveview seed run + rich run detail rebuild
