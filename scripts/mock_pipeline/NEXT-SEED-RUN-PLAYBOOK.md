# NEXT-SEED-RUN PLAYBOOK

The executable playbook for running a seed pipeline against a new SKLD-bench
family. Every learning from the phoenix-liveview run is baked in here so the
next 6 runs can execute with zero guesswork.

## Prerequisites

- [ ] On `main` or a seed branch cut from main with the rich-run-detail
      components available
- [ ] `data/skillforge.db` exists (or gets rebuilt on first uvicorn boot)
- [ ] The target family is one of:
      - `elixir-ecto-sandbox-test`
      - `elixir-security-linter`
      - `elixir-oban-worker`
      - `elixir-ecto-schema-changeset`
      - `elixir-ecto-query-writer`
      - `elixir-pattern-match-refactor`
- [ ] `taxonomy/elixir/<family-slug>/` exists with `family.json`, `seed.json`,
      `challenges/`, `test_fixtures/`, `evaluation/score.py`
- [ ] `ANTHROPIC_API_KEY` loaded via `.env` (not needed for Max-subscription
      subagent dispatches, only for live SDK tests)

## Budget expectations

| Metric | Per family |
|---|---|
| Total subagent dispatches | ~61 (12 Spawner + 48 Competitor + 1 Engineer) + ~5 enrichment |
| Wall-clock (sequential) | ~4 hours |
| Wall-clock (2-wide Competitor parallel) | ~90-120 min |
| Max-subscription burn | ~$28-35 |

## Phase-by-phase execution

### Phase 0 — Setup

```bash
# Cut a branch for this family
git checkout main
git pull origin main
git checkout -b feat/seed-<family-slug>

# Verify the family dir structure
ls taxonomy/elixir/<family-slug>/
# Expected: family.json, seed.json, README.md, research.md,
#           challenges/, test_fixtures/, golden/, evaluation/

# Read the family research doc for context
cat taxonomy/elixir/<family-slug>/research.md | head -50
cat taxonomy/elixir/<family-slug>/README.md
```

### Phase 1 — Seed the family into the DB

```bash
uv run python scripts/mock_pipeline/seed_family.py \
    --family-slug <family-slug>
# Expected output: {"family_id": "fam_...", "foundation_genome_id": "...", ...}
```

This loads the gen-0 seed variants from `seed.json` as `meta_strategy="gen0_seed"`
SkillGenome rows under `run_id = <slug>-seed-v1`. Every family uses the
`-seed-v1` suffix uniformly — phoenix-liveview was renamed from its pre-
rebrand `-mock-v1` id via `mock_run_loader.LEGACY_RUN_RENAMES`.

### Phase 2 — Create the run + 12 VariantEvolution rows

```bash
uv run python scripts/mock_pipeline/create_run.py \
    --family-slug <family-slug>
# Expected output: JSON with run_id, family_id, vevo_ids per dimension,
# foundation_dimension, seed genome IDs
```

Note: `create_run.py` now reads `family.json.name` (or equivalent) to
build a human-readable specialization string, so the output reads
naturally for each family.

**Save the output JSON to `/tmp/skld-seed-run/run_state.json`** — downstream
dispatches need to look up vevo_ids by dimension.

### Phase 3 — Per-dimension loop (foundation first, then N-1 capabilities)

For each dimension in `family.json.foundation_dimension` +
`family.json.capability_dimensions`:

#### 3.1 Sample challenges

```bash
uv run python scripts/mock_pipeline/sample_challenges.py \
    --family-slug <family-slug> \
    --dimension <dim-slug> \
    --num 2 \
    > /tmp/skld-seed-run/challenges-<dim>.json
```

Samples 2 challenges from medium+hard tiers, excluding held-out IDs.

#### 3.2 Spawn variant 2 (diverse from seed)

Dispatch a Spawner subagent via the Agent tool with `model: "opus"` and the
prompt template from `plans/wondrous-wiggling-lamport.md §Subagent dispatch
prompt patterns §Spawner subagent`. The prompt must include:

- Family slug + dimension + tier
- The seed variant's SKILL.md as "DO NOT copy; generate diverse alternative"
- For capability dims: the foundation winner's SKILL.md (architectural context)

**CRITICAL**: the output must satisfy the description validator:
- `description` ≤ 250 chars
- `description` contains `"Use when"` (exact substring)
- `description` contains `"NOT for"` (exact substring)

Parse the `<variant>...</variant>` block from the subagent output. Save the
body to `/tmp/skld-seed-run/variants/<dim>-variant-2.md`.

#### 3.3 Run Competitor dispatches (2 variants × 2 challenges = 4 runs)

For each of the 4 (variant, challenge) pairs:

1. Dispatch a Competitor subagent via Agent tool with `model: "opus"` and the
   prompt template from the parent plan. Prompt must include:
   - Variant SKILL.md inline as `.claude/skills/evolved-skill/SKILL.md`
   - Challenge prompt + fixture files inline
   - "Emit one fenced code block per expected output file"

2. Parse fenced blocks using the regex helper from the parent plan's
   "Competitor output reconstruction" section. Write files into a sandbox:
   ```
   /tmp/skld-seed-run/competitors/<dim>-v<1|2>-ch<id>/
   ```

3. Run the L1 scorer:
   ```bash
   uv run python scripts/mock_pipeline/run_score.py \
       --family-dir taxonomy/elixir/<family-slug> \
       --challenge-path <challenges-json>[i]["path"] \
       --output-dir /tmp/skld-seed-run/competitors/<dim>-v1-ch<id>
   ```

4. Record the score. If parse fails, record `score=0.0` and move on (do NOT
   retry the dispatch — failure is a real signal).

#### 3.4 Pick winner + persist

```python
winner_idx = argmax([mean(v1_scores), mean(v2_scores)])
winner_skill_md_path = f"/tmp/skld-seed-run/variants/<dim>-variant-{winner_idx+1}.md"
winner_fitness = mean(variant_scores[winner_idx])
```

Then:

```bash
uv run python scripts/mock_pipeline/persist_variant.py \
    --run-id <family-slug>-seed-v1 \
    --vevo-id <from-run_state.json> \
    --family-id <from-run_state.json> \
    --family-slug <family-slug> \
    --dimension <dim> \
    --tier foundation|capability \
    --genome-id <from-run_state.json> \
    --skill-md-path <winner_skill_md_path> \
    --fitness <winner_fitness> \
    --challenges-json /tmp/skld-seed-run/challenges-<dim>.json
```

Note: `persist_variant.py` records `meta_strategy="seed_pipeline_winner"` on
the winning genome. The lineage view's mutation-type inference recognizes this.

**IMPORTANT — foundation goes first.** If you hit rate limits mid-run, a
successfully-persisted foundation winner means subsequent capability dispatches
still have the architectural context they need.

Keep a mental map of per-dimension variant 1 and variant 2 scores across all
challenges — you'll need it for step 4.4 (competition scores backfill).

### Phase 4 — Assembly

#### 4.1 Dispatch the Engineer subagent

Via Agent tool with `model: "opus"` and the prompt template from the parent
plan's "Engineer subagent" section. The prompt must include:

- Family slug + specialization text (from `create_run.py` output)
- All N winning variant SKILL.md strings inline, grouped by dimension, with
  their fitness scores

**CRITICAL**: the composite description must also satisfy the validator:
- ≤ 250 chars
- Contains `"Use when"` + `"NOT for"`

Template:
```
<family-name> — <architectural-stance-summary>. Use when <primary use case>.
NOT for <explicit exclusion>.
```

Parse the `<composite>...</composite>` block into
`/tmp/skld-seed-run/composite.md` and the `<integration-report>...</integration-report>`
block separately.

#### 4.2 Finalize the run

```bash
uv run python scripts/mock_pipeline/finalize_run.py \
    --run-id <family-slug>-seed-v1 \
    --composite-skill-md-path /tmp/skld-seed-run/composite.md \
    --total-cost-usd <estimated>
```

This creates the composite SkillGenome with `meta_strategy="engineer_composite"`,
links it as `run.best_skill`, sets `run.status="complete"`, and updates
`skill_families.best_assembly_id`.

### Phase 5 — Rich package enrichment

Dispatch 5 focused enrichment subagents (parallel-safe, 2-wide). Each writes
its output to `/tmp/skld-seed-run/enrichment/<filename>`:

| Dispatch | Output filename(s) | Prompt focus |
|---|---|---|
| validate.sh + main_helper.py | `validate.sh`, `main_helper.py` | Scripts for the family domain — parser / formatter / linter |
| guide.md | `guide.md` | Substantive reference doc (≥ 800 lines) with numbered section anchors per capability dimension |
| cheatsheet.md + anti-patterns.md | `cheatsheet.md`, `anti-patterns.md` | Quick-reference + named anti-patterns with detection + fix guidance |
| 2× templates | `starter_primary.ex.template`, `starter_secondary.ex.template` | Canonical starter files with `{{placeholder}}` syntax |
| migration_checklist.md | `migration_checklist.md` | Step-by-step migration guide for pre-modern → modern idioms |

Each prompt must include `taxonomy/elixir/<family-slug>/research.md` +
`README.md` inline so the content is actually family-specific.

Then merge into the composite:

```bash
uv run python scripts/mock_pipeline/enrich_package.py \
    --run-id <family-slug>-seed-v1 \
    --composite-id gen_composite_<family-slug-underscored>-seed-v1 \
    --family-slug <family-slug> \
    --enrichment-dir /tmp/skld-seed-run/enrichment
```

Note: `enrich_package.py` now defaults to including ALL files in
`taxonomy/elixir/<family-slug>/test_fixtures/`. For a curated subset either:

1. Add `<family-slug>` to the `CURATED_FIXTURES` dict in `enrich_package.py`
2. Drop a `.package_manifest.json` in the family dir with a `fixture_names` array
3. Pass `--fixtures "a.ex,b.ex,c.ex"` on the CLI

Run the enrich command and verify the output summary shows at least 16 files
and ≥ 150KB uncompressed.

### Phase 6 — Narrative persistence

#### 6.1 Integration report

Read the Engineer's `<integration-report>` block (saved during Phase 4). If
the block is missing or malformed, reconstruct it heuristically: read the
12 winning variants, identify contradictions, write a plausible integration
report as Markdown.

```bash
echo "<integration report markdown>" > /tmp/skld-seed-run/integration_report.md
uv run python scripts/mock_pipeline/persist_integration_report.py \
    --run-id <family-slug>-seed-v1 \
    --report-path /tmp/skld-seed-run/integration_report.md
```

This appends an `[integration_report] ...` entry to `run.learning_log`. The
frontend `RunNarrative` component parses the prefix.

#### 6.2 Competition scores

Dump every (variant, challenge) score from Phase 3 into a JSON file:

```json
{
  "dimensions": [
    {
      "dimension": "architectural-stance",
      "tier": "foundation",
      "variants": [
        {
          "slot": 1,
          "label": "seed",
          "challenges": [
            {"id": "xyz", "score": 0.92},
            {"id": "abc", "score": 0.88}
          ],
          "mean": 0.90
        },
        {
          "slot": 2,
          "label": "spawn",
          "challenges": [...],
          "mean": 0.85
        }
      ],
      "winner_slot": 1
    },
    ...
  ]
}
```

Then:

```bash
uv run python scripts/mock_pipeline/backfill_competition_scores.py \
    --run-id <family-slug>-seed-v1 \
    --scores-json /tmp/skld-seed-run/competition_scores.json
```

Appends a `[competition_scores] ...` entry to `run.learning_log`.

#### 6.3 Safety backfill — vevo challenge IDs

```bash
uv run python scripts/mock_pipeline/backfill_vevo_challenge_ids.py \
    --run-id <family-slug>-seed-v1
```

Populates any NULL `VariantEvolution.challenge_id` fields from the sampled
challenges persisted in Phase 3. No-op if they're already populated.

### Phase 7 — Export to the seed library

```bash
uv run python scripts/mock_pipeline/export_run_to_seed.py \
    --run-id <family-slug>-seed-v1 \
    --family-slug <family-slug> \
    --output skillforge/seeds/seed_runs/<family-slug>.json
```

This dumps every row needed to replay the run on a fresh DB: taxonomy nodes,
family, vevos, variants, genomes (seeds + winners + composite), challenges,
the EvolutionRun row, and the full learning_log with integration report +
competition scores entries.

### Phase 7.5 — Final-package installation test (MANDATORY)

**This step is non-negotiable**. The phoenix-liveview seed run shipped with
3 real bugs in the enrichment scripts that only surfaced when someone
actually downloaded the zip and tried to run it on macOS (bash 3.2
incompatibility, subshell variable loss, malformed migrate output). The
install test is the only way to catch these before users find them.

```bash
# 1. Boot localhost uvicorn with the freshly-loaded seed JSON
pkill -f 'uvicorn skillforge' || true
rm -f /Users/mjdecour/apps/skillforge/skillforge.db*
uv run uvicorn skillforge.main:app --port 8000 &
sleep 2

# 2. Download the zip the same way a real user would
rm -rf /tmp/skld-install-test && mkdir -p /tmp/skld-install-test
curl -s -o /tmp/skld-install-test/skill.zip \
  "http://localhost:8000/api/runs/<family-slug>-seed-v1/export?format=skill_dir"
file /tmp/skld-install-test/skill.zip  # must report: Zip archive data

# 3. Extract and make scripts executable
cd /tmp/skld-install-test && unzip -q skill.zip
find . -name '*.sh' -exec chmod +x {} \;
find . -name '*.py' -exec chmod +x {} \;

# 4. Create a realistic fake project with the skill installed
SKILL_DIR="/tmp/skld-install-test/<composite-skill-name>"
rm -rf /tmp/skld-fake-project
mkdir -p /tmp/skld-fake-project/lib /tmp/skld-fake-project/.claude/skills
# Write a fake mix.exs / package.json / etc. appropriate to the family's language
echo 'defmodule FakePhx.MixProject do ... end' > /tmp/skld-fake-project/mix.exs
cp -r "$SKILL_DIR" /tmp/skld-fake-project/.claude/skills/
# Drop the family's test_fixtures into the project's lib/ so scanners have real
# anti-pattern inputs to find
cp "$SKILL_DIR"/test_fixtures/*.ex /tmp/skld-fake-project/lib/ 2>/dev/null || true

# 5. Run every script from the installed location against the fake project
cd /tmp/skld-fake-project
./.claude/skills/<composite-skill-name>/scripts/validate.sh .
python3 ./.claude/skills/<composite-skill-name>/scripts/main_helper.py scan lib/
python3 ./.claude/skills/<composite-skill-name>/scripts/main_helper.py migrate lib/<legacy-file>.ex
python3 ./.claude/skills/<composite-skill-name>/scripts/main_helper.py new-live test_feature --dir lib/
```

**Pass criteria** — all of these must hold:

1. Zip extracts cleanly
2. validate.sh runs on macOS system bash (3.2) without `declare: -A`
   errors — it MUST exit 0 if the fake project has zero anti-patterns, or
   exit 1 with a non-empty summary of hits if it does
3. main_helper.py scan produces gcc-style diagnostics for at least one
   known-bad fixture file
4. main_helper.py migrate rewrites at least one legacy file and produces
   SYNTACTICALLY VALID output (no `<%= <.link> %>` wrappers, no lost
   tags, no misplaced `%>`)
5. main_helper.py new-live creates a new file and the file compiles-in-
   principle (at least passes validate.sh on itself with zero hits)
6. Every `${CLAUDE_SKILL_DIR}/scripts/*` path referenced in SKILL.md
   resolves to a real file that's executable
7. Gold Standard Checklist items (§CLAUDE.md "Gen 0 Seed Quality
   Standard") all pass

**Dispatch a subagent test (recommended but optional)**:

```python
Agent(
    description="Install test: write LiveView using skill",
    subagent_type="general-purpose",
    model="opus",
    prompt=f"""
Use the skill at /tmp/skld-fake-project/.claude/skills/<composite-skill-name>/
to write a small feature in /tmp/skld-fake-project/lib/<target>.ex following
the skill's conventions. Then run the skill's own scan tool against your
output and report any hits. Report which skill sections were most useful
and which gaps you encountered.
""",
)
```

**On any failure**: STOP the run, do NOT merge to main, fix the bugs in
the composite's supporting_files (or in the enrichment scripts), re-run
`enrich_package.py`, re-run `export_run_to_seed.py`, re-test. The bugs
must be fixed in the **source** (the file on disk that gets enriched
into the composite), not just patched in the resulting zip — otherwise
the next seed run will ship the same bugs.

---

### Phase 8 — Localhost verification

Nuke the DB and reboot to verify the loader picks up the new seed:

```bash
# Kill any running uvicorn
pkill -f "uvicorn skillforge.main:app" || true

# Nuke the DB
rm -f data/skillforge.db

# Reboot — lifespan handler runs load_seed_runs()
uv run uvicorn skillforge.main:app --port 8000 &
sleep 5

# Verify the run loaded
curl -s http://localhost:8000/api/runs | \
    jq '.[] | select(.id == "<family-slug>-seed-v1") | {id, status, best_fitness}'

# Check the rich package loaded
curl -s http://localhost:8000/api/runs/<family-slug>-seed-v1/report | \
    jq '.skill_genomes[] | select(.meta_strategy == "engineer_composite") | 
        .supporting_files | keys | length'
# Expected: ≥ 16

# Open the Registry page in a browser
open "http://localhost:8000/runs/<family-slug>-seed-v1"
```

Click through all 7 tabs: Composite, Competition, Metrics, Tests, Narrative,
Lineage, Package. Every tab should render without console errors.

**Gold Standard Checklist check**: open the Package tab and verify all
indicators are green (SKILL.md ✓, scripts/ ✓, references/ ✓, test_fixtures/ ✓).

Try the zip download:

```bash
curl -s -I http://localhost:8000/api/runs/<family-slug>-seed-v1/export?format=zip
```

Expected: 200 OK + `content-disposition: attachment; filename="<skill-name>.zip"`
where `<skill-name>` is the composite's `frontmatter.name` (NOT the run_id).

### Phase 9 — Commit, push, PR, merge

```bash
# Sanity check
git status
# Expected untracked: skillforge/seeds/seed_runs/<family-slug>.json
# Possibly modified: CLAUDE.md (Current Status), plans/PROGRESS.md

git add skillforge/seeds/seed_runs/<family-slug>.json
git add CLAUDE.md plans/PROGRESS.md  # if updated

git -c user.email="matt@skillforge.local" \
    -c user.name="Matt (via Claude Code)" \
    commit -m "$(cat <<'EOF'
seed(<family-slug>): phoenix-liveview-parity showcase run

Full atomic seed pipeline run for <family-slug>: 12 dimensions evolved
via 61 Opus subagent dispatches, composite assembled by Engineer, rich
package generated by 5 enrichment dispatches, all persisted to the
JSON seed library.

- <N> winning variants (mean fitness <X>)
- Composite: <skill-name> (fitness <Y>)
- Package: <Z> files, <KB> KB uncompressed
- Gold Standard Checklist: all green

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"

git push origin feat/seed-<family-slug>

gh pr create --title "seed(<family-slug>): phoenix-liveview-parity showcase run" \
    --body "$(cat <<'EOF'
## Summary
- Full seed pipeline run for <family-slug>, parity with phoenix-liveview
- <N> dimensions evolved, composite assembled, rich package generated
- Persisted to skillforge/seeds/seed_runs/<family-slug>.json

## Verification
- [ ] Localhost Registry loads at /runs/<family-slug>-seed-v1
- [ ] All 7 tabs render without console errors
- [ ] Package Explorer: Gold Standard Checklist all green
- [ ] Zip download filename = <skill-name>.zip
- [ ] Fresh DB boot replays the run correctly

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"

# After review, squash-merge
gh pr merge --squash --auto
```

Railway auto-deploys from `main`. Verify on production:

```bash
curl -s https://skld.run/api/runs | \
    jq '.[] | select(.id == "<family-slug>-seed-v1")'

open "https://skld.run/runs/<family-slug>-seed-v1"
```

### Phase 10 — Update session tracking

- [ ] CLAUDE.md Current Status: increment "seed runs complete" count
- [ ] plans/PROGRESS.md: append entry with fitness, cost, and
      localhost verification confirmation
- [ ] journal/NNN-seed-<family-slug>.md: write entry if surprising
      findings (optional; don't write filler)

## Rate-limit contingencies

If a subagent dispatch returns "You've hit your rate limit":

1. **STOP**. Do not retry. Do not sleep through.
2. Check which dimensions have `status="complete"` in the DB.
3. Document in PROGRESS.md with `[BLOCKED: rate limit]` marker.
4. Persist the current state via the helper scripts (persist whatever
   has a winner; leave incomplete dimensions as `status="pending"`).
5. End the session cleanly.
6. In the next session, query `get_variant_evolutions_for_run(<run_id>)`
   for `status="pending"` rows and resume from there.

## Parser failure contingencies

If Competitor fenced-block parsing returns an empty dict:

1. Record `fitness=0.0` for that (variant × challenge) pair.
2. Add a diagnostic entry to the dimension's score log.
3. Move on — do NOT retry the dispatch. Retrying wastes budget and the
   parse failure is itself a fitness signal.

If this happens for ≥ 50% of a variant's challenges, the winner pick
still works (the other variant wins by default). If both variants fail,
the dimension's mean fitness is 0 — persist anyway and move on.

## Description validator contingencies

If a Spawner or Engineer output has a description that fails the
`"Use when"` check:

1. First failure: retry the dispatch with an explicit note in the prompt
   ("Your description MUST contain the literal substring 'Use when' and
   'NOT for'. Example format: '<what it does>. Use when <use case>.
   NOT for <exclusion>.'").
2. Second failure: accept the output, manually prepend/rewrite the
   description to meet the requirement, proceed.
3. Record the incident in the journal (this is a signal the prompt
   needs strengthening for v2.1 Phase 1).

## See also

- `plans/PLAN-V2.1.md` — the v2.1 production engine plan (which this
  playbook feeds into)
- `plans/wondrous-wiggling-lamport.md` — the original Step 1 plan with
  full subagent prompt templates
- `journal/012-skld-bench-content-workstream.md` — context on the
  SKLD-bench content layer
- `taxonomy/elixir/<family-slug>/research.md` — family-specific domain
  context (always read this before dispatching the first Spawner)
