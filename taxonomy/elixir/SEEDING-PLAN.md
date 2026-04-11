# SKLD-bench: Elixir Top-7 Challenge Pool Seeding Plan

This is the permanent reference for the **SKLD-bench v2.1 workstream**: authoring controlled evaluation environments (challenge pools, score scripts, fixtures, golden solutions) for the top 7 Elixir families per `plans/SPEC-V2.1.md`.

## Why this workstream exists

`plans/SPEC-V2.1.md` specifies controlled evaluation environments to make fitness scores comparable across variants/runs/generations. Each family ships with a frozen `test_fixtures/`, `challenges/`, `evaluation/` tree. Without authored content, the spec is just architecture — this workstream populates the content for the top 7 Elixir families to validate the v2.1 architecture against real workloads and become the SKLD-bench benchmark suite.

## Scope

Top 7 families from `taxonomy/elixir/README.md` (Tier S + Tier A):

| # | Family | Tier | Caps | Curve | Target challenges |
|---|---|---|---|---|---|
| 1 | `elixir-phoenix-liveview` | S | 11 | rich | ~150 |
| 2 | `elixir-ecto-sandbox-test` | S | 10 | rich | ~150 |
| 3 | `elixir-security-linter` | S | 12 | binary | ~100 |
| 4 | `elixir-ecto-query-writer` | S | 11 | rich | ~150 |
| 5 | `elixir-ecto-schema-changeset` | A | 11 | binary | ~100 |
| 6 | `elixir-oban-worker` | A | 11 | binary | ~100 |
| 7 | `elixir-pattern-match-refactor` | A | 10 | rich | ~150 |
| **TOTAL** | | | **76 caps + 7 foundations = 83 dimensions** | | **~900** |

15 deferred families remain folder-only (capability `README.md`, no content) until the lighthouse 7 validate the methodology.

## Locked-in decisions

1. **Pool size**: ~150 challenges per rich family / ~100 per binary family. Total ~900 challenges across the 7 families.
2. **File organization**: Everything for a family lives under `taxonomy/elixir/<family-slug>/`. This overrides the SPEC-V2.1 placeholder location of `skillforge/families/<slug>/`. The Phase 0 plumbing (when it lands as a separate workstream) must point the family loader at `taxonomy/elixir/`.
3. **Authoring model**: **Opus 4.6** for all file authoring — research agents, drafting agents, score.py writers, fixture generators. Subagent dispatches use `model: "opus"` explicitly.
4. **Tier classification: HEURISTIC, NOT EMPIRICAL.** Per the v2.1 SPEC, tiers should be assigned by multi-model calibration (Haiku + Sonnet pass-rate binning). For this workstream, calibration is **deferred**. Tiers are assigned by the drafting agent's judgment based on challenge content (problem complexity, ambiguity, prior knowledge required, scope, fixture richness, and known Claude failure modes from the family's research dossier). Each family's `_calibration.json` will explicitly note this and link back to this plan. Empirical calibration can be re-run as a focused future session once content lands and the Phase 0 plumbing exists.
5. **Branch + PR strategy**: One branch per family (`seed/<family-slug>`), one PR per family, merge after submit (squash + delete branch). 7 PRs total. Restructure changes (this plan + the folder restructure) commit straight to main as docs-only.
6. **Held-out**: Random ~20% of each family's pool, balanced across tiers, persisted in `family.json`.

## Validation criteria for each family before PR merge

- All capabilities have at least the per-capability minimum of dedicated primary-tagged challenges (5 binary, 12 rich)
- Tier distribution matches targets within ~10%
- Held-out set is balanced across tiers (~20% of pool, persisted in `family.json`)
- `score.py` runs against `golden/*.ex` and produces near-perfect scores (sanity check)
- `score.py` runs against an obviously-bad input and produces low scores (discrimination check)
- `environment.yml` declares all binaries/packages the score script needs
- At least 5 challenges in the pool reference real Claude failures cited in the per-family `research.md`
- The family's PR description includes a summary of pool stats (counts per tier, capability coverage, link to research.md)

## File organization (target end state per family)

```
taxonomy/elixir/<family-slug>/
├── README.md                        # capability decomposition (existing)
├── research.md                      # per-family Phase-1 research dossier (NEW)
├── family.json                      # metadata + taxonomy + slug + held_out_ids
├── seed.json                        # gen 0 SkillGenome (foundation + capability slugs)
├── test_fixtures/                   # immutable input files (~5-15 .ex files per family)
│   └── *.ex
├── challenges/
│   ├── easy/                        # ~25-38 .json files
│   ├── medium/                      # ~25-45 .json files
│   ├── hard/                        # ~15-38 .json files
│   ├── legendary/                   # ~5-30 .json files
│   └── _calibration.json            # heuristic-tier note + reference back to this plan
├── evaluation/
│   ├── criteria.json                # rubric weights per objective
│   ├── score.py                     # deterministic scorer (regex/AST/structural checks)
│   └── environment.yml              # declared deps for score.py
└── golden/                          # reference correct solutions (~5-15 .ex files)
    └── *.ex
```

## Per-family workflow (5 phases per family)

### Phase 1 — Per-family research

- One Opus background subagent dispatched per family
- **Inputs**: family `README.md` + `docs/research/elixir-llm-pain-points.md`
- **Search**: Elixir Forum, HN, Reddit r/elixir, GitHub plugin repos (oliver-kriska, georgeguimaraes), dev blogs (Dashbit, BoothIQ post-mortem), 2024-2026 sources
- **Output**: `taxonomy/elixir/<slug>/research.md` — structured per-capability findings with verbatim quotes + source URLs
- **Format**: each capability gets a section with: known Claude failure modes, citations, severity, suggested challenge angles

### Phase 2 — Capability prioritization

- Read the `research.md` and produce a per-capability authoring matrix
- High-evidence capabilities → upper bound (12-16 rich, 5-8 binary)
- Low-evidence capabilities → lower bound
- Per-tier distribution per capability based on what makes sense (some binary capabilities skip legendary)
- Stored as a section inside `research.md` (no separate file)

### Phase 3 — Challenge drafting

- Opus drafting subagents author challenge JSONs based on the matrix
- Each challenge tags `primary_capability` + `secondary_capabilities`
- Each challenge gets a heuristic `tier` field assigned during drafting (see "Heuristic tier rubric" below)
- Drafting also produces `test_fixtures/*.ex`, `golden/*.ex`, `family.json`, `seed.json`
- Drafting batches: ~30-40 challenges per subagent dispatch to keep prompts focused

#### Challenge JSON schema (example)

```json
{
  "id": "elixir-phoenix-liveview-medium-04",
  "tier": "medium",
  "title": "Migrate a 1.6 LiveView to 1.7 with verified routes",
  "prompt": "Convert this Phoenix 1.6 LiveView to use the 1.7 verified-routes syntax.",
  "fixture_files": ["test_fixtures/pre_1_7_user_form.ex"],
  "expected_outputs": {
    "files": ["lib/my_app_web/live/user_live.ex"],
    "must_contain": ["~p\"/users/", "<.form", ":if=", ":for="],
    "must_not_contain": ["live_link", "Routes.user_path", "<%= for "]
  },
  "scoring": {
    "primary_capability": "heex-and-verified-routes",
    "secondary_capabilities": ["form-handling"],
    "criterion": "verified_routes_used",
    "weight": 0.3
  },
  "calibration": null,
  "tier_rationale": "Migration requires recognizing two distinct deprecations + applying both correctly across multiple sites; Sonnet typically completes one but misses the other."
}
```

The `tier_rationale` field is the heuristic-tiering equivalent of the empirical-calibration block. Every challenge has one.

### Phase 4 — Score script + criteria

- One Opus subagent authors `evaluation/score.py`, `criteria.json`, `environment.yml` per family
- `score.py` reads `expected_outputs` + competitor output and emits per-objective JSON
- For binary capabilities: regex/AST checks
- For rich capabilities: structural checks (presence of patterns, absence of anti-patterns, line counts)
- **Validation**: run `score.py` against `golden/*.ex` (must pass) and against an obviously-bad input (must fail). Iterate up to 2 times if validation fails; on continued failure, ship with `[NEEDS REVIEW]` marker

### Phase 5 — Held-out split + calibration manifest

- Drafting agent's per-challenge `tier` field is reviewed for distribution balance
- If a tier is over/under target by >10%, redistribute by re-tiering borderline challenges
- Random ~20% sampled balanced across tiers becomes the held-out set, persisted in `family.json` as a list of challenge IDs
- Write `_calibration.json` with: methodology note (`"heuristic"`), date, link to this plan, per-tier counts, capability coverage matrix

#### `_calibration.json` schema

```json
{
  "methodology": "heuristic",
  "calibration_deferred": true,
  "deferred_reason": "See taxonomy/elixir/SEEDING-PLAN.md item 4 — empirical calibration is a future workstream",
  "calibrated_date": null,
  "tier_distribution": {
    "easy": 38,
    "medium": 45,
    "hard": 38,
    "legendary": 30
  },
  "capability_coverage": {
    "<capability-slug>": {
      "primary_count": 14,
      "secondary_count": 8
    }
  }
}
```

### Phase 6 — Commit + PR + merge

- Branch: `seed/<family-slug>` (created from up-to-date main)
- Commit message: `seed(<family-slug>): SKLD-bench v2.1 challenge pool (~N challenges, heuristic tier)`
- Push, create PR via `gh pr create` with a body that summarizes: total challenges, per-tier breakdown, capability coverage, key research citations, link to this plan
- Merge via `gh pr merge --squash --delete-branch`
- Update the family's TaskCreate task to `completed`

## Heuristic tier rubric

When the drafting agent assigns a tier to a challenge, it considers:

| Tier | Heuristic |
|---|---|
| **easy** | Single-step transformation. Pattern is well-known. Fixture is small. The expected solution is one of a few canonical idioms. Vanilla Sonnet can typically one-shot it. |
| **medium** | Multi-step or context-aware. Requires recognizing a non-obvious idiom or anti-pattern. Fixture has noise. Sonnet typically gets ~60-80% right but trips on one detail. |
| **hard** | Requires synthesis of multiple capabilities OR deep familiarity with a niche library/pattern. Multiple plausible solutions, only some correct. Sonnet typically misses key constraints. Often references a documented Claude failure from the research dossier. |
| **legendary** | Requires reasoning under conflicting constraints, OR depth across the OTP/BEAM-specific runtime model, OR knowing a recent (2024-2026) deprecation, OR catching a subtle correctness issue (race condition, ordering bug, leaked process). The challenge is intentionally adversarial — designed to expose a known Claude weakness. |

The `tier_rationale` field on each challenge captures the drafting agent's reasoning for the assigned tier. This makes the tiers reviewable and re-tierable later.

## Capability targets

| Capability character | Target (primary-tagged) | Tier breakdown |
|---|---|---|
| Rich (e.g. `form-handling`, `streams-and-collections`) | 12-16 | 3-4 easy, 4-5 medium, 3-4 hard, 2-3 legendary |
| Binary (e.g. `pin-operator-safety`, `field-types-and-decimal`) | 5-8 | 2 easy, 2 medium, 1-2 hard, 0-2 legendary |
| Foundation (cross-cutting structural) | 10-15 | 3-4 per tier |

These are **primary capability** counts. With overlap (each challenge tags 1 primary + 1-3 secondary capabilities), effective coverage per capability is ~1.5x the primary count.

## Cost analysis (revised after dropping calibration)

- **Production API spend**: $0. All work is done by Claude Code subscription.
- **Subscription burn**: ~50-80M tokens (down from ~185M after dropping calibration)
- **Wall-clock**: ~5-8 hours for the overnight run (down from 7-12 hours after dropping calibration)
- **Per-family wall-clock**: ~1-2 hours per family in the overnight run (with phase-based parallelization)

## Phasing — overnight parallel execution

The plan runs as **6 phases sequenced in time** but with **all 7 families running through each phase in parallel**.

| Phase | Scope | Concurrency | Wall-clock target |
|---|---|---|---|
| **0** | Restructure (22 family files → folders) + write `SEEDING-PLAN.md` + commit | sequential | ~15 min |
| **1** | Per-family research — 7 Opus background agents in parallel | 7-wide parallel | ~30-45 min |
| **2** | Capability prioritization — 7 quick Opus dispatches in parallel | 7-wide parallel | ~15 min |
| **3** | Challenge drafting — 4-7 families in parallel, each with 2-4 drafting subagents | up to ~20-wide parallel | ~2-4 hours |
| **4** | `score.py` + `criteria.json` + `environment.yml` — 7 Opus dispatches in parallel | 7-wide parallel | ~1-2 hours |
| **5** | Held-out split + `_calibration.json` (heuristic) — 7 dispatches in parallel | 7-wide parallel | ~30 min |
| **6** | Per-family commit + PR + merge as each family validates clean | rolling | continuous |

## Circuit breakers (autonomous QA)

If any of these triggers, pause that family's pipeline and either fix-in-place or document-and-defer:

- **Phase 1 research returns < 5 capability findings** → research is too thin to drive drafting; re-dispatch with a stricter prompt or skip to Phase 3 with the existing `docs/research/elixir-llm-pain-points.md` as the only evidence base.
- **Phase 3 drafting produces < 50% of target challenge count** → the drafting subagent struggled; re-dispatch with chunked targets (10 challenges at a time instead of 30).
- **Phase 4 `score.py` fails its self-validation** (golden ref scores low, OR bad input scores high) → iterate up to 2 times. If still failing, document the issue and ship the family with `[NEEDS REVIEW]` marker.
- **Phase 5 tier distribution exceeds ±10% target** → redistribute borderline challenges or accept and note in PR description.
- **Total elapsed wall-clock exceeds 10 hours** → stop dispatching new families. Ship whatever's complete. Document the rest as `[DEFERRED]` for the next session.

## Out of scope

- **Phase 0 plumbing implementation** — schema migrations, family loader, champion eval module, sandbox env verification, L1 family-scorer integration. Will need a separate workstream + SPEC follow-up amendment to point at `taxonomy/elixir/` instead of `skillforge/families/`.
- **Empirical calibration** — deferred. Tiers in v1 of these pools are heuristic; empirical calibration is a future workstream.
- **Migrating the 15 v2.0 seeds** to v2.1 format — separate workstream after the lighthouse Elixir families validate.
- **Tier B-E Elixir families** — folders exist with capability READMEs only; full population is a future workstream.
- **Frontend changes** — difficulty curve display, family detail page. Downstream of plumbing.
- **A bare-API ground-truth calibration pass** — out of scope for this plan.

## How to pick up this workstream in a future session

1. Read this file (you're doing it now)
2. Check `git log --oneline taxonomy/elixir/` for which families have shipped (each ships as a single squash-merged commit `seed(<slug>): SKLD-bench v2.1 challenge pool ...`)
3. Check `taxonomy/elixir/_OVERNIGHT-RUN-REPORT.md` if it exists (the summary of the autonomous overnight run)
4. Run `gh pr list --state all --search "seed/elixir"` to see PR history
5. For families that haven't shipped: pick one, follow Phases 1-6 above
6. For families that shipped with `[NEEDS REVIEW]` markers: address the markers, commit fix to a new branch + PR

## Provenance

This plan was finalized in plan mode and stored at `~/.claude/plans/wondrous-wiggling-lamport.md` before being copied here as the permanent project reference. The two should be considered semantically equivalent except for one update made after plan approval: **calibration was deferred in favor of heuristic tier assignment** (see "Locked-in decisions" item 4). The plan-mode file is the planning artifact; this file is the project reference.
