# SPEC v2.1 — Controlled Evaluation Environments & Tiered Challenge Pools

**Status**: Draft
**Date**: 2026-04-10
**Authors**: Matt + Claude Opus 4.6 (1M context)
**Depends on**: `plans/SPEC-V2.0.md` (atomic variant evolution), shipped + in production

---

## Executive summary

v2.1 fixes the foundational measurement problem in SkillForge: **fitness scores produced by v2.0 are not directly comparable across variants, re-runs, or generations because every challenge is invented fresh by the Challenge Designer at run time.**

The fix is a four-part architectural shift:

1. **Frozen, family-owned test fixtures and challenge pools** — every challenge a variant faces is drawn from a stable, versioned, hand-authored pool that lives on disk inside the family's directory. Same fixtures, same scoring rubric, same expected outputs across every variant in a family.
2. **Difficulty-tiered challenge pools** — every pool contains ~50 challenges spread across `easy` / `medium` / `hard` / `legendary` tiers, calibrated empirically against vanilla Claude baselines.
3. **Train/test separation** — each generation samples 3-5 challenges from a training pool (variants can't memorize specific challenges); after evolution finishes, the champion is evaluated against a held-out subset that no skill saw during evolution. The held-out score is the headline number.
4. **Empirical calibration methodology** — challenge difficulty tiers are derived from multi-model baseline pass rates (Haiku + Sonnet without skills attached), not from human guess or LLM self-rating.

The v2.1 system makes it possible to say sentences like *"this variant's score improved from 0.65 to 0.78 on the held-out hard tier"* and have them mean something. Today, that sentence would be meaningless because the challenges underneath the two scores were different.

**Key metaphor**: v2.0 measured "did this variant solve a problem the Challenge Designer made up?" — v2.1 measures "did this variant solve problems from a stable benchmark that vanilla Claude struggles with?"

---

## The problem (in Matt's exact framing)

> *"This is a big issue, because without controlled evaluation environments we're not able to know if the change we're making is meaningful."*
> — Matt, conversation 2026-04-10

Three concrete consequences of the v2.0 measurement gap:

### 1. Fitness deltas are noise
A 0.60 → 0.67 fitness improvement could be genuine variant quality OR it could be that Challenge B (this run) was easier than Challenge A (last run). The 5th live atomic test produced 4 foundation variants on the same dimension scoring 0.60 / 0.60 / 0.67 / 0.60 — those numbers are not comparable because each variant faced a different Challenge Designer-generated challenge.

### 2. The Breeder is training on the test
The Spawner is blind to challenges (good — confirmed in `skillforge/agents/spawner.py`). The Challenge Designer is blind to skills (good). But the **judging pipeline scores skills against the same challenges they were spawned for**, and the surviving skills' content carries that adaptation forward into the next generation. Even with a blind Breeder, the system is implicitly training on the test set.

### 3. Research paper has no methodology section
*"SKLD improved skills from X to Y"* is methodologically empty if X and Y were measured against different challenges, OR if neither was measured against held-out problems. The v2.0 architecture cannot produce a defensible benchmark result.

These are all symptoms of one cause: **the test environment is not a property of the family — it's a property of each individual challenge, invented fresh on every run.** v2.1 inverts that.

---

## Goals

1. **Comparability**: variant A and variant B in the same family must face identical evaluation, so their fitness scores are directly comparable.
2. **Reproducibility**: re-running an evolution against the same family must produce comparable fitness numbers across runs.
3. **Generalization signal**: there must be a held-out evaluation set that no skill ever sees during training, and the headline fitness number must come from it.
4. **Difficulty curve**: every variant gets a difficulty curve (`easy: 0.95, medium: 0.78, hard: 0.45, legendary: 0.10`), not a single fitness score.
5. **Empirical calibration**: difficulty tiers are derived from real model pass rates, not guesses.
6. **Cost discipline**: the per-run cost should not more than 2× the v2.0 cost. Wall-clock should not more than 2× either.
7. **Methodology defensibility**: the resulting fitness numbers must support a claim like *"SKLD improved variants by N% on the held-out hard tier of the SKLD-bench Phoenix LiveView family"* without methodological caveats.

## Non-goals

- **Not building new Reviewer layers.** L1-L5 stay as in v2.0; this spec only changes what they evaluate against, not how they score.
- **Not changing the Engineer's assembly logic.** The composite assembly flow from v2.0 (foundation winner + capability winners → Engineer weave → integration check) stays as-is.
- **Not introducing a new database engine.** SQLite + aiosqlite, additive migrations only.
- **Not building a model-versioning system.** Calibration data has a `calibrated_against_models` field for record-keeping but the system does not auto-recalibrate when models update.
- **Not solving the OTP debugging problem.** The Elixir `elixir-otp-debugger` family has its own evaluation challenges that v2.1's challenge pool model doesn't fully solve. Out of scope for this spec.

---

## Architecture overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                      v2.1 Family Asset Layout                          │
│                                                                        │
│  skillforge/families/<family-slug>/                                    │
│    ├── family.json                  # metadata + taxonomy + slug       │
│    ├── seed.json                    # gen 0 SkillGenome (the seed)     │
│    ├── test_fixtures/               # immutable input files            │
│    │   ├── sample_input_1.ex                                           │
│    │   ├── sample_input_2.ex                                           │
│    │   └── ...                                                         │
│    ├── challenges/                  # versioned challenge pool         │
│    │   ├── easy/                    # ~12 challenges                   │
│    │   │   ├── 01_basic.json        # prompt + expected_output + score │
│    │   │   ├── 02_typecheck.json                                       │
│    │   │   └── ...                                                     │
│    │   ├── medium/                  # ~12 challenges                   │
│    │   ├── hard/                    # ~12 challenges                   │
│    │   ├── legendary/               # ~14 challenges                   │
│    │   └── _calibration.json        # baseline pass rates per chal.    │
│    ├── evaluation/                                                     │
│    │   ├── criteria.json            # rubric: weights per objective    │
│    │   ├── score.py                 # deterministic scorer             │
│    │   └── environment.yml          # required packages/binaries       │
│    └── golden/                      # optional reference solutions     │
│        └── reference_output.ex                                         │
└────────────────────────────────────────────────────────────────────────┘
```

This replaces (or augments) the current `skillforge/seeds/__init__.py` flat-list seed loading. Each family becomes a self-contained directory with all the assets it needs to evaluate variants consistently.

---

## Core change 1: Family-owned controlled evaluation environment

### What the family owns

Each family directory holds:

- **`family.json`** — metadata: slug, label, specialization, taxonomy path (domain/focus/language), decomposition strategy, list of variant dimensions
- **`seed.json`** — the gen 0 SkillGenome (current `SEED_SKILLS` entry, structured as JSON instead of inline Python)
- **`test_fixtures/`** — input files used by challenges. Immutable across all variants. E.g., for `elixir-phoenix-liveview`: a sample 1.6-era LiveView module to migrate, a sample changeset to render in a form, etc.
- **`challenges/`** — the challenge pool (next section)
- **`evaluation/`**:
  - **`criteria.json`** — machine-readable scoring rubric. Per-objective weights, e.g. `{"correctness": 0.5, "idiom_adherence": 0.3, "performance": 0.2}`. Replaces the runtime-derived rubric in current Reviewer L1.
  - **`score.py`** — deterministic scoring script that reads a challenge's expected output + the competitor's actual output and emits per-objective scores as JSON. L1 just calls this script and parses the JSON.
  - **`environment.yml`** — declared dependencies for the sandbox. Lists required binaries (e.g., `mix`, `iex`, `docker`, `terraform`) and language-specific packages.
- **`golden/`** — optional reference solutions used by `score.py` for diff-based scoring or by the calibration pipeline as a "what does correct look like" anchor

### Why this matters

In v2.0, when a Phoenix LiveView variant is evaluated, the Challenge Designer has to invent a LiveView problem from scratch. The "correct answer" is whatever Sonnet thinks is correct, scored by another Sonnet call (Reviewer). This is circular.

In v2.1, when the same variant is evaluated:
- It's given a real test fixture (`sample_pre_1_7_liveview.ex`)
- It must produce output that matches a known-good reference (`golden/migrated.ex`)
- The score comes from `score.py` running deterministic checks (does the output use `~p`? does it use `<.form>`? does it use streams for the inbox? does it have DB queries in mount?)

The result: variant fitness reflects actual capability against a real, repeatable problem, not arbitration between two LLM outputs.

---

## Core change 2: Difficulty-tiered challenge pools

### Pool structure

Every family has a **challenge pool of ~50 challenges**, distributed across four difficulty tiers:

| Tier | Target count | Definition |
|---|---|---|
| `easy` | ~12 | Vanilla Sonnet (no skill) passes 90-100% of the time |
| `medium` | ~12 | Vanilla Sonnet passes 60-89% of the time |
| `hard` | ~12 | Vanilla Sonnet passes 20-59% of the time |
| `legendary` | ~14 | Vanilla Sonnet passes 0-19% of the time — the skill provides genuine value here |

**Why ~50 and not 20**: a smaller pool risks variants memorizing specific challenges through indirect pressure. 50 gives enough variety that adaptation must be on the *kind of problem*, not on the *specific instance*.

**Why tiered**: a single fitness score collapses signal. A variant that scores 0.95 on easy and 0.10 on legendary is a different beast from one that scores 0.70 on easy and 0.55 on legendary. The difficulty curve tells you whether a variant is **scaling** or **plateauing**.

### Challenge file format

Each challenge is a JSON file:

```json
{
  "id": "elixir-phoenix-liveview-medium-04",
  "tier": "medium",
  "title": "Migrate a 1.6 LiveView to 1.7 with verified routes",
  "prompt": "Convert this Phoenix 1.6 LiveView to Phoenix 1.7+ idioms. Use `~p` for routes, `<.form>` for forms, `:if`/`:for` instead of `<%= %>`. Preserve the user-facing behavior.",
  "fixture_files": [
    "test_fixtures/pre_1_7_user_form.ex"
  ],
  "expected_outputs": {
    "files": ["lib/my_app_web/live/user_live.ex"],
    "must_contain": ["~p\"/users/", "<.form", ":if=", ":for="],
    "must_not_contain": ["live_link", "Routes.user_path", "<%= for "]
  },
  "scoring": {
    "criterion": "verified_routes_used",
    "weight": 0.3
  },
  "calibration": {
    "haiku_pass_rate": 0.33,
    "sonnet_pass_rate": 0.78,
    "calibrated_at": "2026-04-10",
    "calibrated_against_models": ["claude-haiku-4-5-20251001", "claude-sonnet-4-6"]
  }
}
```

The `calibration` block is populated by the calibration pipeline (see Core change 4) and is the source of truth for which tier the challenge belongs to.

### Champion final evaluation

After variant evolution finishes for a family, the champion (winning composite skill) is run against a **held-out subset of 10 challenges** that were not sampled during any generation. The held-out scores produce the final difficulty curve:

```
elixir-phoenix-liveview champion fitness curve:
  easy:      0.95 (3/3 challenges)
  medium:    0.78 (2/3 challenges, partial credit)
  hard:      0.55 (1.5/2 challenges)
  legendary: 0.10 (0/2 challenges, partial credit on 1)
  overall:   0.61 (held-out, 10 challenges)
```

This is the headline number. It's the only fitness score that's defensible in a research paper because it was never used for training.

---

## Core change 3: Train/test separation + random sampling

### Per-generation sampling strategy

Each generation in the variant evolution loop **samples 3-5 challenges from the training pool** (not the held-out pool) at random. The Spawner and Breeder are blind to which specific challenges were sampled, so they cannot adapt to specific test instances. Adaptation must be on the *kind of problem*.

Three sampling strategies, by phase of evolution:

| Generation | Sampling | Rationale |
|---|---|---|
| Gen 0 | 3 challenges, balanced (1 easy, 1 medium, 1 hard) | Cheap probe; establishes baseline fitness curve |
| Gen 1+ | 5 challenges, balanced (1 easy, 2 medium, 2 hard) | Main evolution pressure; tilts harder over time |
| Gen N (final) | 5 challenges (1 easy, 2 medium, 1 hard, 1 legendary) | Stress test before assembly |

**Random sampling is critical**. If the same 3 challenges were used every generation, variants would memorize them. With sampling, each generation faces a different mix from the same difficulty distribution, which means the evolutionary pressure rewards **general competence at the difficulty tier**, not specific-challenge-passing.

### Held-out pool

Of the ~50 challenges in the family's pool, **10 are reserved as held-out** and never sampled during evolution. The held-out set is a fixed sample, balanced across tiers (3 easy, 3 medium, 2 hard, 2 legendary). After evolution finishes, the champion is run against all 10 to produce the headline difficulty curve.

The held-out set is **family-versioned** — once chosen for a family, it stays the same across all evolution runs against that family. Different families have different held-out sets. This means:
- Generation N's training challenges and gen N+1's training challenges might differ (random sampling)
- But the held-out set used to score the champion is the same across runs against the same family — **so champion fitness IS comparable across runs**

---

## Core change 4: Empirical calibration methodology

### The calibration pipeline

Difficulty tiers are derived empirically, not guessed. For each candidate challenge:

1. **Run vanilla Haiku** (no skill attached, just `claude-haiku-4-5-20251001` with the challenge prompt) **3 times**. Record pass/fail per run.
2. **Run vanilla Sonnet** (no skill attached) **3 times**. Record pass/fail per run.
3. **Compute pass rate** per model: `haiku_pass_rate = passes / 3`, `sonnet_pass_rate = passes / 3`.
4. **Bin into tier** based on these rules:
   - `haiku 3/3 ∧ sonnet 3/3` → **easy**
   - `haiku 1-2/3 ∧ sonnet 3/3` → **medium**
   - `haiku 0/3 ∧ sonnet 2-3/3` → **hard**
   - `haiku 0/3 ∧ sonnet 0-1/3` → **legendary**
5. **Discard ambiguous**: any challenge that doesn't cluster cleanly (e.g., 2/3 on both models) is dropped from the pool.
6. **Balance**: from the cleanly-binned challenges, select ~12 per tier to fill the pool.

### Why 2 models, not 3+

Adding Opus to the calibration would give a richer signal but adds 3× cost. Two models (Haiku + Sonnet) give 90% of the value at 2/3 the cost.

### Why pass rate, not LLM self-rating

LLMs have no ground truth on their own capability. Asking Sonnet *"how hard is this challenge, 1-10?"* produces guesses, not measurements. Empirical pass rate IS the measurement.

### Calibration cost

For each family:
- 100 candidate drafts (more than the final 50 to allow culling)
- 100 × 3 runs × 2 models = **600 evaluations per family**
- At Haiku-only: ~$36 per family
- At mixed Haiku + Sonnet: ~$70 per family

**For all 22 Elixir families**: $540 - $1500 one-time. **But all of this can be done by Claude Code (subscription), not via the production API**, so the cost to the project is $0. The runtime production system never pays calibration costs — it only consumes the pre-calibrated `_calibration.json` artifact that ships with each family.

### Storage

Each family's `challenges/_calibration.json` records:
- The candidate set used
- Per-challenge pass rates per model
- The tier-binning rules at the time of calibration
- The model versions used
- The calibration date

This makes calibration **reproducible** and **auditable** — the research paper can cite "calibrated against `claude-sonnet-4-6` and `claude-haiku-4-5-20251001` on 2026-04-10" with verifiable artifacts.

---

## Data model changes

### `Challenge` dataclass

The existing `skillforge/models/challenge.py::Challenge` gains three new fields:

```python
@dataclass
class Challenge:
    id: str
    prompt: str
    difficulty: str                          # EXISTING — but semantics change to be tier-derived
    evaluation_criteria: dict
    verification_method: str
    setup_files: dict[str, str]
    gold_standard_hints: str

    # NEW IN v2.1
    tier: str = "medium"                     # easy | medium | hard | legendary
    family_slug: str | None = None           # foreign key to family that owns this challenge
    calibration: dict | None = None          # haiku_pass_rate, sonnet_pass_rate, calibrated_at, ...
    is_held_out: bool = False                # True if reserved for champion final eval
```

### New dataclass: `ChallengePool`

```python
@dataclass
class ChallengePool:
    family_slug: str
    challenges: list[Challenge]              # all 50
    held_out_ids: list[str]                  # the 10 reserved for champion eval
    calibration_meta: dict                   # versions, dates, methodology

    def training_challenges(self) -> list[Challenge]:
        return [c for c in self.challenges if c.id not in self.held_out_ids]

    def held_out_challenges(self) -> list[Challenge]:
        return [c for c in self.challenges if c.id in self.held_out_ids]

    def sample(self, n: int, balance: dict[str, int] | None = None) -> list[Challenge]:
        """Sample n challenges from the training set, optionally balanced across tiers."""
        ...
```

### New dataclass: `EvaluationCriteria`

```python
@dataclass
class EvaluationCriteria:
    family_slug: str
    objectives: dict[str, float]             # {"correctness": 0.5, "idiom_adherence": 0.3, ...}
    score_script: Path                       # path to the family's score.py
    environment: dict                        # parsed environment.yml
```

### `ChampionEvaluation` dataclass (new)

The result of the held-out evaluation pass:

```python
@dataclass
class ChampionEvaluation:
    composite_id: str                        # SkillGenome id of the champion composite
    family_id: str
    held_out_scores: dict[str, float]        # {"easy": 0.95, "medium": 0.78, "hard": 0.55, "legendary": 0.10}
    overall_held_out: float                  # weighted average across tiers
    per_challenge_results: list[dict]        # one entry per held-out challenge with score breakdown
    evaluated_at: datetime
```

---

## Schema changes

### New tables

```sql
-- Versioned challenge pools per family
CREATE TABLE IF NOT EXISTS challenge_pools (
    family_slug TEXT PRIMARY KEY,
    version TEXT NOT NULL,                   -- e.g. "1.0", bumped on recalibration
    pool_size INTEGER NOT NULL,
    held_out_ids TEXT NOT NULL,              -- JSON array of challenge ids
    calibration_meta TEXT NOT NULL,          -- JSON: methodology, model versions, date
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (family_slug) REFERENCES skill_families(slug) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pools_family ON challenge_pools(family_slug);

-- Champion held-out evaluations (one per evolution run)
CREATE TABLE IF NOT EXISTS champion_evaluations (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    composite_id TEXT NOT NULL,
    family_id TEXT NOT NULL,
    held_out_scores TEXT NOT NULL,           -- JSON: tier → score
    overall_held_out REAL NOT NULL,
    per_challenge_results TEXT NOT NULL,     -- JSON: detailed per-challenge breakdown
    evaluated_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES evolution_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (composite_id) REFERENCES skill_genomes(id) ON DELETE CASCADE,
    FOREIGN KEY (family_id) REFERENCES skill_families(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_champion_run ON champion_evaluations(run_id);
CREATE INDEX IF NOT EXISTS idx_champion_family ON champion_evaluations(family_id);
```

### Additive column changes

```sql
-- challenges table gets tier + calibration + held-out flag
ALTER TABLE challenges ADD COLUMN tier TEXT DEFAULT 'medium';
ALTER TABLE challenges ADD COLUMN family_slug TEXT;
ALTER TABLE challenges ADD COLUMN calibration TEXT;          -- JSON
ALTER TABLE challenges ADD COLUMN is_held_out INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_challenges_family ON challenges(family_slug);
CREATE INDEX IF NOT EXISTS idx_challenges_tier ON challenges(tier);

-- skill_families table gets a pool version pointer
ALTER TABLE skill_families ADD COLUMN current_pool_version TEXT;
ALTER TABLE skill_families ADD COLUMN pool_dir TEXT;         -- e.g. "skillforge/families/elixir-phoenix-liveview"
```

### Migration strategy

- All migrations are **additive** — same pattern as v2.0 in `skillforge/db/database.py::_apply_additive_migrations()`
- Existing v2.0 challenges (Challenge Designer-generated) get a default `tier='medium'`, `family_slug=NULL`, `calibration=NULL`, `is_held_out=0`
- Pre-v2.1 evolution runs continue to work because the new fields are nullable
- New fields are only populated when a v2.1 family is loaded and a v2.1 evolution run is initiated

---

## File system layout

### Where families live

```
skillforge/families/
├── README.md                                    # explains the family directory format
├── elixir-phoenix-liveview/                     # one directory per family
│   ├── family.json
│   ├── seed.json
│   ├── test_fixtures/
│   │   ├── pre_1_7_user_form.ex
│   │   ├── sample_user_schema.ex
│   │   ├── messages_inbox_10k.ex
│   │   └── ...
│   ├── challenges/
│   │   ├── easy/
│   │   │   ├── 01_basic_link.json
│   │   │   ├── 02_simple_form.json
│   │   │   └── ...
│   │   ├── medium/
│   │   ├── hard/
│   │   ├── legendary/
│   │   └── _calibration.json
│   ├── evaluation/
│   │   ├── criteria.json
│   │   ├── score.py
│   │   └── environment.yml
│   └── golden/
│       └── reference_user_form_migrated.ex
├── elixir-ecto-sandbox-test/
│   └── ... (same structure)
└── ... (one directory per family)
```

### Family loader

A new module `skillforge/db/family_loader.py` replaces the relevant parts of `skillforge/db/seed_loader.py` and `skillforge/db/taxonomy_seeds.py`:

```python
async def load_family(family_dir: Path) -> SkillFamily:
    """Load a v2.1 family directory into the DB.

    Reads family.json + seed.json + challenges/* and inserts/updates:
    - skill_families row (with current_pool_version)
    - skill_genomes row (the seed gen 0)
    - challenges rows (all 50, with tier + calibration + is_held_out)
    - challenge_pools row (with held_out_ids)
    - taxonomy_nodes (idempotent insert)
    """
    ...

async def load_all_families(families_dir: Path = ROOT_DIR / "skillforge/families") -> dict:
    """Walk the families/ directory and load each family found."""
    ...
```

This is wired into `main.py`'s lifespan handler after the existing `load_seeds()` and `load_taxonomy()` calls.

### Backward compatibility

The existing `skillforge/seeds/__init__.py` (15 v2.0 seeds) keeps working. v2.0 seeds are loaded into the DB without any v2.1 challenge pool — they have `current_pool_version=NULL`. They evolve via the v2.0 path (Challenge Designer invents challenges at runtime).

v2.1 families are loaded from `skillforge/families/<slug>/` and have a populated `current_pool_version`. They evolve via the v2.1 path (sample from pool, champion held-out eval).

The two coexist. Migration of v2.0 families to v2.1 is **opt-in per family** (see migration section).

---

## Engine changes

### `skillforge/engine/variant_evolution.py`

The atomic-mode orchestrator gets a new dispatcher branch:

```python
async def _run_dimension_mini_evolution(...) -> tuple[Variant, SkillGenome]:
    if family.current_pool_version is not None:
        # v2.1 path: sample from pool, no Challenge Designer call
        challenges = await sample_challenges_from_pool(
            family_slug=family.slug,
            n=5,
            balance={"easy": 1, "medium": 2, "hard": 2},
        )
    else:
        # v2.0 path: Challenge Designer invents one
        challenge = await design_variant_challenge(...)
        challenges = [challenge]

    # ... rest of mini-evolution flow uses `challenges` list (already list-shaped)
```

### `skillforge/engine/champion_eval.py` (new)

After the variant evolution loop completes and the Engineer assembles the composite:

```python
async def evaluate_champion(
    run: EvolutionRun,
    composite: SkillGenome,
    family: SkillFamily,
) -> ChampionEvaluation:
    """Run the champion against the family's held-out challenge set.

    Uses the same Competitor + judging pipeline as in-evolution scoring,
    but ONLY against the held-out challenges. Persists the result in
    champion_evaluations and emits a `champion_evaluated` event with
    the full difficulty curve.
    """
    pool = await load_challenge_pool(family.slug)
    held_out = pool.held_out_challenges()

    # Run champion against each held-out challenge
    results = []
    for challenge in held_out:
        result = await _gated_competitor(
            run_id=run.id,
            generation=999,                       # sentinel: post-evolution
            competitor_idx=0,
            skill=composite,
            challenge=challenge,
            env_id=None,
        )
        results.append(result)

    # Score per tier
    tier_scores = _aggregate_by_tier(results, held_out)
    overall = sum(tier_scores.values()) / len(tier_scores)

    eval = ChampionEvaluation(
        composite_id=composite.id,
        family_id=family.id,
        held_out_scores=tier_scores,
        overall_held_out=overall,
        per_challenge_results=results,
        evaluated_at=datetime.now(UTC),
    )
    await save_champion_evaluation(eval)
    await emit(run.id, "champion_evaluated", **eval.to_dict())
    return eval
```

This is wired into `run_variant_evolution` after `_real_assembly` finishes.

### `skillforge/engine/sandbox.py`

The sandbox gains an environment verification step before any competitor runs:

```python
def verify_environment(family: SkillFamily) -> list[str]:
    """Check that all declared dependencies in environment.yml are available.

    Returns list of missing dependencies. Empty list = ready to run.
    """
    env_yml = family.pool_dir / "evaluation" / "environment.yml"
    if not env_yml.exists():
        return []                                  # no requirements declared
    declared = parse_environment_yml(env_yml)
    missing = []
    for binary in declared.get("binaries", []):
        if shutil.which(binary) is None:
            missing.append(f"binary:{binary}")
    for package in declared.get("packages", []):
        if not _is_installed(package):
            missing.append(f"package:{package}")
    return missing
```

If `verify_environment()` returns non-empty, the orchestrator emits a `family_environment_missing` event and aborts the run with a clear error rather than producing nonsense fitness scores against an environment that can't actually run the test code.

### `skillforge/agents/judge/l1_deterministic.py`

L1 currently re-derives evaluation criteria from each Challenge's text. In v2.1, when the challenge has a `family_slug` set, L1 calls the family's `evaluation/score.py` directly:

```python
async def score_l1(
    skill: SkillGenome,
    challenge: Challenge,
    competitor_output: dict,
) -> dict[str, float]:
    if challenge.family_slug:
        # v2.1 path: use the family's deterministic scorer
        family = await get_family_by_slug(challenge.family_slug)
        return await run_family_scorer(family, challenge, competitor_output)
    else:
        # v2.0 path: legacy text-derived criteria
        return await score_l1_legacy(skill, challenge, competitor_output)
```

`run_family_scorer` invokes `score.py` as a subprocess with the challenge id and competitor output dir as args, parses the JSON it emits, and returns the per-objective scores.

---

## Calibration pipeline (Claude Code subscription, not API)

This is the part Matt explicitly asked about: **the calibration work is done by me (Claude Code) via the subscription, not via Matt's production API budget.**

### Workflow

For each new family being added to the v2.1 system:

1. **Author the difficulty axes** — manual: I list the dimensions of variation that distinguish easy vs hard challenges in this domain (e.g., for `elixir-phoenix-liveview`: number of components, presence of streams, form complexity, lifecycle subtlety, etc.)
2. **Draft 100 candidate challenges** — I write 100 challenge JSONs covering the difficulty axes. Each has a prompt, fixture references, expected output specification, and scoring criterion.
3. **Author the score.py** — I write the deterministic scoring script for the family.
4. **Run the calibration loop** — I dispatch general-purpose subagents (subscription compute) to run vanilla Claude against each candidate 3× per model:
   ```
   for challenge in candidates:
       for model in [haiku, sonnet]:
           for trial in 1..3:
               result = subagent_solve(challenge, model)
               record_result(challenge, model, trial, result)
   ```
   This generates ~600 evaluations per family. The whole batch costs $0 to the project (subscription).
5. **Auto-bin into tiers** — local Python script reads the calibration results and applies the binning rules from Core change 4.
6. **Cull and balance** — drop ambiguous challenges, balance across tiers, end up with the final ~50.
7. **Pick held-out** — randomly select 10 from the final 50, balanced across tiers.
8. **Write `_calibration.json`** — record per-challenge pass rates, tier assignments, model versions, date.
9. **Commit** — the family directory is now ready for production use. The DB loader picks it up on next boot.

### Subscription validity caveat

There's a methodological wrinkle: subscription Claude Code uses a slightly different harness than a bare API call (tool access, agent loops, system prompts). Pass rates measured via subagents are "Claude Code-flavored" not "bare API-flavored". This is acceptable because:

- What matters for tier binning is **relative difficulty within the pool**, not absolute pass rates
- All challenges in a family are calibrated through the same harness, so the relative ordering is meaningful
- The research paper methodology section discloses this honestly: *"calibrated against the same Claude Code subscription harness used for evolution"*

If a future need arises to publish "bare API" calibration numbers, that can be done separately and budgeted as a one-time API spend.

---

## Cost and time impact

### Per-run cost (production, no calibration)

| Config | Per-run cost | Per-run wall-clock (SDK backend, conc=1) |
|---|---|---|
| **v2.0 current** (5 pop × 3 gen × 3 challenges) | ~$9 | ~15 min |
| **v2.1 conservative** (3 challenges/gen + 10 held-out) | ~$12 | ~20 min |
| **v2.1 standard** (5 challenges/gen + 10 held-out) | ~$15 | ~28 min |
| **v2.1 stress** (5 challenges/gen + 20 held-out) | ~$18 | ~35 min |

On managed backend (concurrency=5+), all v2.1 configs land at **~6-12 min** wall-clock. Cost is unaffected by concurrency.

### One-time calibration cost (per family, charged to subscription, not API)

| Item | Cost to project | Cost to subscription |
|---|---|---|
| Drafting 100 candidates | $0 | small |
| Authoring score.py | $0 | small |
| Calibration runs (600 evals) | $0 | medium |
| Auto-bin + cull | $0 | small |
| **Per-family total** | **$0** | **~30-60 min of Claude Code session time** |

### One-time calibration cost across all 22 Elixir families

| Item | Cost to project | Cost to subscription |
|---|---|---|
| All 22 families | $0 | ~10-20 hours of Claude Code session work |

This is the entire authoring + calibration cost. Spread across multiple sessions, it's an attractive distribution: project pays $0, Claude Code takes the hit.

### Runtime evolution cost across all 22 Elixir families (one full atomic run each)

22 × ~$15 = **~$330 to fully evolve every Elixir family once**, on Sonnet, SDK backend.

On Haiku tier (`SKILLFORGE_TEST_TIER=cheap`): 22 × ~$5 = **~$110**.

---

## Migration path: v2.0 → v2.1 family-by-family

The migration is **opt-in per family**. v2.0 families continue to work unchanged; v2.1 families are added incrementally.

### Phase 0: Bootstrap the v2.1 plumbing (no families yet)

- Schema migrations (additive, all the new tables/columns)
- New dataclasses (`ChallengePool`, `EvaluationCriteria`, `ChampionEvaluation`)
- Family loader module (`skillforge/db/family_loader.py`)
- Engine dispatcher (sample-from-pool branch)
- Champion eval module (`skillforge/engine/champion_eval.py`)
- L1 family-scorer integration
- Sandbox environment verification
- Tests for all of the above using a synthetic family fixture

This ships **without any real family** to validate the plumbing in isolation.

### Phase 1: Lighthouse family — `elixir-phoenix-liveview`

- Author the family directory (drafted by Claude Code subscription)
- Calibrate against vanilla Claude (subscription)
- Land it as the first v2.1 family
- Run a full evolution against it; capture the difficulty curve
- This validates the end-to-end pipeline against a real workload

### Phase 2: Roll out the rest of Tier S Elixir families

- `elixir-ecto-sandbox-test`
- `elixir-security-linter`
- `elixir-ecto-query-writer`
- One or two per session, tested incrementally

### Phase 3: Tier A Elixir families

- `elixir-ecto-schema-changeset`
- `elixir-oban-worker`
- `elixir-pattern-match-refactor`

### Phase 4: Migrate the existing 15 v2.0 seeds

The original 15 seeds (`unit-test-generator`, `dockerfile-optimizer`, etc.) get the v2.1 treatment one at a time. Their existing seed.json content becomes the v2.1 seed.json; new challenge pools + score.py + fixtures are authored.

### Phase 5: Optional Tier B-E families

Build only if there's user demand or if the SkillForge research paper needs more breadth.

---

## Frontend changes

### Champion fitness curve display

The current `EvolutionResults.tsx` shows a single `best_fitness` number. v2.1 adds:

- **Difficulty curve chart**: a small bar chart showing the champion's score per tier (`easy`, `medium`, `hard`, `legendary`)
- **Held-out indicator**: the headline number is labeled "(held-out)" so users know it's the generalization metric, not a training score
- **Per-challenge breakdown**: an expandable section showing each held-out challenge's individual score

### Family detail page

A new page (or extension of the existing `TaxonomyBrowser.tsx`) for family details:

- Shows the family's challenge pool stats (`12 easy / 13 medium / 11 hard / 14 legendary`)
- Shows the calibration metadata (when, against which models)
- Shows the test fixture files
- Links to the family's `score.py` and `criteria.json` for transparency

### Run progress events

New WebSocket events the frontend listens for:

- `champion_eval_started` — fired when champion held-out evaluation begins
- `champion_eval_progress` — fired per-challenge during champion eval
- `champion_evaluated` — fired when full curve is ready

---

## Open questions

1. **Sampling balance**: should generations sample balanced across tiers (always 1 easy + 2 medium + 2 hard) or weighted (more medium early, more hard late)?
2. **Pool versioning**: when should `current_pool_version` bump? On any challenge edit, on recalibration, or only on a major methodology shift?
3. **Cross-family fixtures**: can families share `test_fixtures/` if they evaluate against the same source files (e.g., `elixir-phoenix-liveview` and `elixir-ecto-sandbox-test` both might want a sample User schema)? Suggested answer: yes, via symlink or a shared `test_fixtures/_common/` dir.
4. **Held-out re-randomization**: the held-out set is fixed per family. Should it be re-randomized periodically (e.g., monthly) to prevent overfitting to the held-out itself? Suggested: no, fixed = comparable runs.
5. **Recalibration cadence**: when models update (e.g., Sonnet 4.7 lands), do we recalibrate all families? Or only when difficulty distribution drifts noticeably? Suggested: opportunistic, not automatic.
6. **`environment.yml` strictness**: should the sandbox HARD-FAIL on missing binaries, or warn-and-continue? Suggested: hard-fail in production runs, warn in dev mode.
7. **Score script execution timeout**: deterministic scorers should be bounded (a runaway `score.py` would block the whole pipeline). Suggested cap: 30 seconds per challenge.
8. **Cost ceiling on calibration**: even though calibration is subscription-only, should there be a soft ceiling on how many calibration evals one session can run? Suggested: 1000 per session (3 families' worth) to keep individual sessions tractable.

---

## Implementation phases

| Phase | Scope | Effort | Dependencies |
|---|---|---|---|
| **0** | Plumbing (schema, dataclasses, loader, engine dispatcher, champion eval, L1 family-scorer integration, sandbox env verification, tests) | ~3-4 sessions | None |
| **1** | Lighthouse family: `elixir-phoenix-liveview` (full directory + 50 challenges + score.py + calibration + first run) | ~2-3 sessions | Phase 0 |
| **2** | Tier S Elixir rollout (`elixir-ecto-sandbox-test`, `elixir-security-linter`, `elixir-ecto-query-writer`) | ~3-4 sessions | Phase 1 validated |
| **3** | Tier A Elixir rollout (3 more families) | ~3-4 sessions | Phase 2 |
| **4** | v2.0 seed migration (15 existing families to v2.1 format) | ~5-7 sessions | Phase 3, opt-in |
| **5** | Tier B-E Elixir families (if needed) | TBD | Demand-driven |
| **6** | Frontend difficulty curve + family detail page | ~1-2 sessions | Phase 1 (need real data) |

Total spec implementation work: **~17-25 sessions**, distributed over weeks.

---

## Validation criteria

### Phase 0 done means:
- All schema migrations apply cleanly to a fresh DB AND to the existing prod DB
- Dataclass round-trip tests pass
- The synthetic test family loads end-to-end and produces a valid `ChallengePool`
- Champion eval module produces a `ChampionEvaluation` against a mocked competitor pipeline
- L1 family-scorer integration calls `score.py` correctly for v2.1 families and falls back to legacy for v2.0
- Sandbox env verification correctly identifies missing binaries
- All v2.0 tests still pass (no regressions)

### Phase 1 (lighthouse) done means:
- `elixir-phoenix-liveview` family fully authored with 50 calibrated challenges
- Calibration metadata recorded in `_calibration.json`
- Full evolution run completes against the family
- Champion gets a difficulty curve like `{easy: 0.X, medium: 0.X, hard: 0.X, legendary: 0.X}` with reasonable distribution (not all 0, not all 1)
- The fitness numbers ARE comparable across re-runs (verified by running twice and comparing)
- The held-out score differs meaningfully from the training pool score (validates train/test separation is doing something)

### Spec-level success means:
- Two evolution runs of the same family produce comparable champion fitness curves (variance < 10%)
- A champion's held-out fitness is **lower** than its training-pool fitness (otherwise we have a measurement bug, not a generalization signal)
- A specialized variant scores higher than vanilla Claude on the same held-out set (otherwise the skill provides no value)
- The research paper can include a methodology section that says: *"All variant fitness scores reported below were measured against held-out challenges from version-pinned, empirically-calibrated challenge pools per family. Training challenges were sampled per generation; held-out challenges were not seen during evolution."*

---

## Relationship to other work

### Depends on
- **`plans/SPEC-V2.0.md`** — the atomic variant evolution architecture this spec extends
- **`docs/research/elixir-llm-pain-points.md`** — the evidence base for the Elixir family roster
- **`taxonomy/elixir/`** — the 22 Elixir family decompositions that v2.1 will materialize as real family directories

### Blocks
- The SKLD research paper — until v2.1 lands, no fitness number SkillForge produces is methodologically defensible
- Comparable fitness across re-runs in atomic mode — currently impossible
- Honest "did this evolution actually work?" reporting — currently a guess

### Enables
- A real benchmark suite for LLM coding skills (SKLD-bench)
- Direct comparison of variants (foundation A vs foundation B)
- Difficulty curves as a feature in the frontend
- Calibration data as a publishable artifact

### Adjacent (not in scope but relevant)
- **`elixir-otp-debugger`** family will need a different evaluation format because its inputs are runtime artifacts (crash reports), not static prompts. v2.1's challenge pool model assumes static-prompt evaluation. A future v2.2 might extend the model to support "system-snapshot evaluation" for debugging-style families.
- **Recursive self-improvement** of SkillForge's own agent skills (`.claude/skills/`) — these aren't currently family-shaped and don't fit v2.1's model. Out of scope.
- **Multi-tenant calibration** — if multiple users want their own family pools with their own calibration baselines, the `family_slug` PK becomes a problem. Out of scope for v2.1.

---

## Decisions log (in spec format)

| Decision | Rationale |
|---|---|
| Family-owned challenge pools, not run-owned | Comparability across runs requires stable evaluation; run-owned pools regress to v2.0's measurement gap |
| ~50 challenges per family, not 20 | Smaller pools risk variants memorizing through indirect pressure; 50 forces generalization |
| 4 difficulty tiers (easy/medium/hard/legendary), not 3 or 5 | Captures the "scaling" signal cleanly without over-fragmenting; 5 tiers had no clear boundaries |
| Empirical calibration (multi-model pass rate), not LLM self-rating | LLMs have no ground truth on their own capability; pass rate IS the measurement |
| 2 calibration models (Haiku + Sonnet), not 3+ | Adding Opus triples cost for marginal additional signal; 2 models give 90% of value at 2/3 cost |
| Random per-generation sampling, not fixed challenges | Random sampling prevents specific-challenge memorization while maintaining tier-balanced pressure |
| Held-out set is fixed per family, not re-randomized per run | Comparable champion fitness across runs requires the same held-out set |
| 10 challenges in held-out, not 20 | Cost / signal tradeoff: 10 gives a useful curve (~2-3 per tier) at ~$1.70 added per run on Sonnet |
| Calibration done by Claude Code (subscription), not via API | $0 cost to project; Claude Code can dispatch subagents to run vanilla Claude across hundreds of challenges |
| Subscription-flavored pass rates are acceptable for tier binning | Relative ordering matters more than absolute pass rates; methodology section discloses honestly |
| Backward compatibility: v2.0 families continue to work unchanged | Migration is opt-in per family; no breaking changes to running production |
| Schema migrations are additive only (PRAGMA + ALTER ADD COLUMN) | Same pattern as v2.0; zero-touch upgrade from prod DB |
| L1 calls family `score.py` via subprocess | Decouples scoring logic from the agent loop; deterministic, language-agnostic, cache-friendly |
| Sandbox environment verification fails the run on missing deps | Producing fitness scores against a broken environment is worse than failing loudly |
| Champion held-out evaluation is a separate engine module | Keeps the variant_evolution loop focused; champion eval can be run independently for debugging |

---

## What this spec does NOT do

To keep scope contained, v2.1 does NOT:

- Build a separate frontend "calibration dashboard"
- Add user-facing controls for sampling strategy (it's hardcoded by tier in the engine)
- Support per-user custom challenge pools (everything is project-global)
- Implement automatic recalibration when models update
- Build a "challenge pool editor" UI — pools are authored as JSON files in source control
- Replace the Challenge Designer for v2.0 families — it stays as a fallback path
- Modify the Engineer assembly logic
- Add new Reviewer layers

Each of those is a defensible v2.2+ topic. v2.1 is laser-focused on **fixing the measurement problem** without expanding scope.

---

## Sources and references

- `plans/SPEC-V2.0.md` — the architectural foundation
- `plans/BACKLOG.md` — the original "Domain-Specific Test Environments" backlog item that v2.1 implements
- `docs/research/elixir-llm-pain-points.md` — the evidence-driven family roster
- `taxonomy/elixir/` — the 22 Elixir family capability breakdowns
- Conversation 2026-04-10 between Matt and Claude Opus 4.6 — the design discussion that produced this spec
