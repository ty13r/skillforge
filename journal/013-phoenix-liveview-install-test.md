# SKLD — Project Journal

## Entry #13: The Install Test — three quality gates, still broken

**Date**: April 11, 2026  
**Session Duration**: ~12 hours across two long stretches  
**Participants**: Matt + Claude Opus 4.6 (1M context)

---

### The Starting Point

Entry #12 closed with the SKLD-bench content layer shipped — 867 Elixir
challenges across 7 lighthouse families, all on main. This session
picked up from there with a specific goal that kept expanding: take the
phoenix-liveview mock pipeline run (shipped in PR #18 the previous
session) and turn the production Registry page for that run into
something people would actually want to click through.

What started as "polish the run detail page" ended up being:

1. A ground-up rebuild of `/runs/:runId` into a 7-tab rich showcase
2. A full `mock → seed` rebrand across every user-facing string
3. A second rebrand of the run_id itself because "mock" was still
   visible in the URL bar
4. OG meta tags + a brand image + per-run server-side meta injection so
   links would render rich previews when dropped in Discord
5. And then — finally, near the end — the install test that discovered
   the whole thing was silently broken

---

### Phase 1: The rich run detail page

The starting state: the Registry page for the phoenix-liveview mock run
loaded, but it was a "skill with no story". Raw SKILL.md preview,
synthetic Fitness Radar fed hardcoded data, empty Growth Curve, 12
variant rows hidden behind a "Show Advanced" toggle, export buttons at
the bottom. Nothing explained what the 12 evolved capabilities did, how
the composite was assembled, which challenges it was tested against,
or why the composite scored 0.94. A first-time visitor would bounce.

Matt framed the problem plainly: "it's a skill with no story." The fix
was a complete restructure. Over several iterations with real-time
feedback:

- **7 tabs, sticky header**: Composite, Competition, Metrics, Tests,
  Narrative, Lineage, Package. Sticky tab bar with the always-visible
  header showing run title, Gen 1/1 pill, export buttons.
- **Plain-English first, metrics second**: an `OverallAssessment` prose
  card at the top of the Composite tab, followed by a `PipelineOverview`
  mini-diagram (24 challenges → 12 variants → 1 composite), then the
  rendered composite SKILL.md with section anchors.
- **Per-challenge competition breakdown**: `CompetitionBracket` with 12
  mini-brackets, each showing Variant 1 (seed) vs Variant 2 (spawn)
  with per-challenge scores and a `buildRationale()` sentence
  explaining why the winner won. Preempts questions like "did you run
  baselines?" and "is this multi-gen?"
- **Master-detail lineage**: the first cut had 12 parent cards that
  expanded in-place below a grid, but clicking parent #7 scrolled past
  the click target. Fixed by moving to a sticky left rail that stays
  visible while the right panel updates on selection.
- **Stacked parent→composite sections**: side-by-side comparisons
  squeezed both into narrow columns and made reading hard. Matt: "let's
  put these on top of each other instead side by side." One line of
  CSS.
- **Package Explorer**: split installable (SKILL.md + scripts/ +
  references/ + assets/ + test_fixtures/) from metadata (PACKAGE.md,
  REPORT.md, parents/, challenges/). SKILL.md at top, selected by
  default, directories open by default. A Gold Standard Checklist
  above the tree showing one-line factual compliance with the
  §CLAUDE.md quality bar.

Every iteration Matt flagged another thing: "there's nothing to view
here" (the expanded card was below the fold), "shouldn't there be
directories here?" (the installable tree was flat), "delete this
disclaimer" (I'd written a paragraph explaining how the package was
built; the user wanted it gone, not rewritten). Each piece of feedback
codified another design principle: no disclaimers, honest tone, plain-
English before metrics, production parity with what the real engine
will emit.

---

### Phase 2: Rich package enrichment

Halfway through the run detail work, Matt pivoted: "ok I want to make
this package RICH... we're going through all of these motions, so the
next mock run we do is 100% on target and when we run this in product
it generates everything we need. This isn't meant to be a fake package,
but an actual package we can distribute."

The composite at that point had a SKILL.md string and nothing else —
empty `supporting_files`. The Package Explorer was rendering "1 file"
with a disclaimer about it being a post-facto reconstruction. That was
not going to fly.

The fix was an enrichment pass: dispatch 5 focused Opus subagents to
produce each missing file (validate.sh, main_helper.py, guide.md,
cheatsheet.md, anti-patterns.md, 2× starter templates, migration
checklist), plus copy 6 curated test_fixtures from the family directory.
The `enrich_package.py` helper merges everything into the composite
genome's `supporting_files` dict via a direct SQL UPDATE, then the seed
JSON gets re-exported.

End result: 16 files, ~167KB uncompressed. Gold Standard Checklist all
green. Visual evidence of a real distributable package.

---

### Phase 3: Rebrand mock → seed (twice)

Matt: "no one cares whether or not it actually ran through the product
pipeline or not." The visitor cares about the output, not the
provenance. Every user-facing "mock" became "seed". Directory renames,
log prefix updates, meta_strategy values (`mock_pipeline_winner` →
`seed_pipeline_winner`), script renames, loader module updates, hash
marker format (`[mock_v...]` → `[seed_v...]`).

Along the way I found a latent bug: the mock_run_loader appended a
fresh `[mock_v<hash>]` marker to the specialization on every reload
without stripping old markers. After 3 reloads the subtitle read
`[mock_v...] [mock_v...] [seed_v...]`. Fixed with a regex-strip pass
before appending.

Phoenix-liveview's run_id was frozen at `-mock-v1` in the first
rebrand to preserve DB continuity, which felt like the right trade-off
until Matt sent me a screenshot of the browser URL bar showing
`https://skld.run/runs/elixir-phoenix-liveview-mock-v1`. "damn the URL
says mock in it."

Second rebrand: rename the run_id itself. Surgical find-and-replace
across the 650KB seed JSON: 63 structural occurrences of
`elixir-phoenix-liveview-mock-v1` → `elixir-phoenix-liveview-seed-v1`,
4 composite genome ID replacements, plus a `LEGACY_RUN_RENAMES` map in
the loader that deletes the legacy row on boot so Railway's persistent
volume gets auto-migrated. Also hit a save-order FK bug in the loader
(variant_evolutions.challenge_id → challenges.id) that was latent
because earlier exports had NULL challenge_ids.

---

### Phase 4: OG images + per-run meta injection

With the URL finally clean, Matt wanted to drop the link in an Elixir
Discord channel. Before this session, `frontend/index.html` had zero
OG meta tags — any shared link fell back to bare page title.

The quick-win was site-wide static tags + a 1200×630 brand PNG
generated with Pillow via `uv run --with pillow python <<EOF` (no
permanent dependency). The harder win was **per-run meta tag
injection**: SPAs can't easily emit per-page OG tags because the
static HTML is the same for every URL. Fix: the FastAPI catch-all for
`/runs/:runId` paths now queries the DB, builds run-specific meta
values (skill name, specialization, fitness, status — with `[seed_v*]`
hash markers stripped so visitors never see DB bookkeeping), regex-
replaces them into the HTML, and returns `HTMLResponse` instead of
`FileResponse`. Two gotchas: the existing catch-all needed a
`response_model=None` decorator because FastAPI can't infer a
Pydantic model from a `FileResponse | HTMLResponse` union, and the
PNG itself needed an explicit `/og-image.png` route BEFORE the
catch-all or the catch-all would swallow it.

---

### Phase 5: The install test

By this point every quality gate was green. The run detail page looked
great. The Package Explorer showed 16 files with all green Gold
Standard Checklist indicators. The zip export validator passed. The
Registry rendered cleanly. Everything said "ship it."

Then Matt: "should we try installing the liveview skill now?"

I downloaded the zip, extracted it, and started exercising the scripts.

**Bug 1** — `validate.sh` died on line 49: `declare: -A: invalid option`.
macOS ships bash 3.2. The script used `declare -A HITS_BY` which is
bash 4+. The enrichment agent that generated this script had tested it
on Linux (its own runtime environment) and never verified macOS
compatibility.

**Bug 2** — I fixed the `declare -A` with dynamic variable names via
`eval` + `${!var}` indirect expansion, ran it, and saw... every detector
reporting real hits in the body, but the summary showing "all clean"
and TOTAL_HITS=0. Second bug: `detector | report "key" "fix"` — the
pipeline creates a subshell in bash 3.2, so assignments inside `report`
never propagate back to the parent. This bug would have existed on
Linux bash 4+ too — it was only the `declare -A` failure that masked
it. Fix: process substitution `report "key" "fix" < <(detector)`.

**Bug 3** — `main_helper.py migrate` ran and reported "10 rewrites
applied" on a real Phoenix 1.6 file. I diffed the output against the
original and saw four distinct kinds of broken Elixir:

```elixir
# <.link> wrapped in <%= %> — invalid HEEx
<%= <.link patch={~p"/users/new"}>New user</.link>, class: "btn" %>

# The `class: "btn"` was dangling instead of becoming a component attr
# push_navigate worked but Routes.user_path inside it wasn't rewritten
{:noreply, push_navigate(socket, to: Routes.user_path(socket, :index))}

# live_redirect with an Elixir expression (not a quoted string) was skipped
<%= live_redirect user.name, to: ~p"/users/#{user}" %>

# :for directive landed on <ul> instead of <li>
<ul :for={user <- @users}>
  <li>...</li>
</ul>
```

All four stem from the same root problem: the rewriter used naive regex
substitutions that were context-blind. They matched the call site but
didn't know about the surrounding `<%= %>` EEx wrapper, didn't know
that `:for` on the outer tag duplicates the whole container, didn't
consider unquoted text expressions, and had a too-narrow leading-`@`
requirement on `Routes.*_path(@socket, ...)` that missed the
`Routes.*_path(socket, ...)` form inside `push_navigate`.

Fix: a post-processing cleanup pass that strips `<%= %>` around `.link`
components and absorbs trailing keyword args as component attrs; a
helper that detects quoted-literal vs Elixir-expression text and wraps
expressions in HEEx curly syntax `{user.name}`; regex rewrites that
match the inner tag (`<li>`) inside the for block instead of the outer
wrapper; a widened `_ROUTES_CALL_RE` with optional `@?`; exclusion of
`%` from target groups so `%>` doesn't get consumed.

**Bug 4** — minor: `new-live dashboard_live` produced
`MyAppWeb.DashboardLiveLive` because the scaffolder appended `_live` to
whatever the user passed. Fix: strip a trailing `_live` before the
camel-case conversion.

After the four fixes landed, the install test became the real deal:

```
validate.sh /tmp/fake-phx
  ... 32 anti-pattern hit(s) across 14 detectors
  FAIL: exit 1

main_helper.py scan lib/
  ... 35 issue(s) across 5 file(s)
  exit 1

main_helper.py migrate legacy_file.ex
  9 rewrites applied including the new <%= <.link> %> wrapper cleanup
  output diffs clean against expected Phoenix 1.7+ HEEx

main_helper.py new-live dashboard
  defmodule MyAppWeb.DashboardLive — scaffold clean
```

---

### Phase 6: The meta loop — using the skill to write LiveView

With the scripts fixed, the final validation was: can a Claude Code
agent use this skill to write better Phoenix LiveView code than it
would write on its own?

I created a realistic Phoenix project dir at `/tmp/skld-phoenix-demo`
with a fake `mix.exs`, `lib/my_app_web/live/`, and the composite skill
dropped into `.claude/skills/elixir-phoenix-liveview-composite/`. Then
I dispatched a general-purpose Opus subagent with instructions to:

1. Read SKILL.md, cheatsheet.md, anti-patterns.md, and the starter
   template (in that order)
2. Write a `TaskListLive` module implementing a Tasks feature with
   add/toggle/delete/filter events, streams, forms, HEEx
3. Run the skill's own scanner on the output and fix any hits

The subagent produced a 190-line file that scanned **clean on the
first try** — zero anti-pattern hits. It used every Phoenix 1.7+ idiom
the skill teaches: streams with `phx-update="stream"`, `:for={...}` on
`<li>` (not `<ul>`), `:if` for filtering, `<.link>` components, `~p`
verified routes, `to_form/2` forms, a typed `%Action{}` funnel into
`handle_action/2` for pure state transitions. The subagent's report
called out exactly which sections of the skill were most useful and
identified two gaps: the skill doesn't explicitly show how to filter
a stream without resetting it, and it doesn't show how to hoist an
inline form into an assign. Both are now TODO items for the next
iteration of the skill.

---

### Phase 7: Final-package testing becomes a pipeline requirement

The install test caught four real bugs that every other quality gate
had passed. That's a strong signal: schema-level checks are necessary
but not sufficient. The only reliable way to know a package works is
to install it and run it. So this session codified that into the
pipeline:

- **`scripts/mock_pipeline/NEXT-SEED-RUN-PLAYBOOK.md` §Phase 7.5** — the
  bridge playbook now mandates a final-package installation test
  before any seed run is marked complete, with a specific bash script
  that downloads the zip, creates a fake project, runs every script,
  asserts on the outputs, and optionally dispatches a subagent dogfood
  test.
- **`plans/PLAN-V2.1.md §P1.5`** — the production engine must include a
  `skillforge/engine/install_test.py` module called from
  `run_v21_evolution()` AFTER assembly and champion eval but BEFORE
  `save_genome(composite)`. On failure the run transitions to a new
  `install_test_failed` status and the failure_reason stores the
  specific script diagnostics. The zip export endpoint refuses to
  export genomes whose parent run is in that state.
- **Success criterion #11** — added explicitly to the v2.1 shipped
  gate. Nothing ships without the install test passing.

The new PLAN-V2.1.md §3.5 documents the four bugs as learnings so
future engine work doesn't repeat them.

---

### Artifacts Produced

| Artifact | Lines / Bytes | Purpose |
|---|---|---|
| `frontend/src/components/AtomicRunDetail.tsx` + 11 sibling components | ~2,000 lines total | Rich run detail page, 7 tabs |
| `skillforge/main.py` per-run meta injection | +150 lines | Server-side OG tag injection for /runs/:runId |
| `frontend/public/og-image.png` | 70,579 bytes | 1200×630 brand preview image |
| `plans/PLAN-V2.1.md` (rewritten) | ~950 lines | v2.1 engine plan with install-test phase |
| `scripts/mock_pipeline/NEXT-SEED-RUN-PLAYBOOK.md` | ~480 lines | Bridge playbook for remaining 6 seed runs |
| `scripts/mock_pipeline/patch_composite_scripts.py` | 100 lines | One-off helper to patch composite supporting_files |
| Fixed `scripts/validate.sh` (bash 3.2 compat) | 260 lines | Process substitution + dynamic vars |
| Fixed `scripts/main_helper.py` (wrapper cleanup) | 1,025 lines | Post-processing EEx strip + inner-tag for/if |
| `journal/013-phoenix-liveview-install-test.md` | this file | Session narrative |

### Key Decisions Summary

| Decision | Rationale |
|---|---|
| Fork `AtomicRunDetail.tsx` instead of extending `EvolutionResults` | Zero risk of breaking legacy molecular runs; route switches at `App.tsx` |
| Rebrand `mock` → `seed` AFTER the first rebrand failed | URL visibility is the user-facing truth; DB continuity doesn't matter for a showcase run |
| Per-run meta tag injection at the catch-all layer | SPAs can't emit per-page OG tags client-side; server injection works for Discord/Slack/iMessage today |
| Final-package install test is MANDATORY, not optional | Three quality gates passed and the package was still broken; only execution reveals it |
| Keep the install test even when expensive | The alternative is shipping broken skills to the community — zero-trust on schema validators alone |

### What's Next

Three explicit next steps per Matt's latest directive:

1. **Generate the next seed run** — apply the now-validated process to one
   of the remaining 6 Elixir families. Candidate: `elixir-ecto-sandbox-test`
   (the hardest-to-fake family — requires real test environment reasoning).
2. **Run the remaining 5 families** after the first one validates the
   generalized scripts work with zero per-family patching.
3. **Build v2.1** — once all 7 seed runs exist as reference artifacts on
   the Registry, start Phase 0 (DB migration → family loader → dispatcher
   → L1 scorer → competition persistence → run_events) and Phase 1
   (rich package generation + install test) of the v2.1 production
   engine plan.

The install test gate will apply to all of those. Any seed run that
fails the bash 3.2 + migrate + scaffold + subagent dogfood checks does
not get merged, full stop.

---

*"Three quality gates passed. The package was still broken. The only way to know is to install it and run it."*
