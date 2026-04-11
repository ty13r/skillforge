# SKLD-bench v2.1 — Family File Schemas

Reference for every file that belongs in a SKLD-bench family folder. Applies to all 7 top-tier Elixir families authored under the SKLD-bench workstream and to any future v2.1 families. Companion to [`SEEDING-PLAN.md`](SEEDING-PLAN.md).

## Folder layout

Every family folder has this exact structure:

```
taxonomy/elixir/<family-slug>/
├── README.md            # capability decomposition (existing, written before this workstream)
├── research.md          # per-capability Claude failure-mode dossier (Phase 1 output)
├── family.json          # family metadata
├── seed.json            # gen 0 SkillGenome
├── test_fixtures/       # immutable input files
│   └── *.ex
├── challenges/
│   ├── easy/
│   │   └── *.json
│   ├── medium/
│   │   └── *.json
│   ├── hard/
│   │   └── *.json
│   ├── legendary/
│   │   └── *.json
│   └── _calibration.json
├── evaluation/
│   ├── criteria.json
│   ├── score.py
│   └── environment.yml
└── golden/
    └── *.ex
```

---

## family.json

Top-level family metadata. One per family.

```json
{
  "slug": "elixir-phoenix-liveview",
  "name": "Elixir Phoenix LiveView",
  "language": "elixir",
  "tier": "S",
  "curve": "rich",
  "spec_version": "2.1",
  "taxonomy": {
    "domain": "development",
    "focus": "phoenix-framework",
    "language": "elixir"
  },
  "foundation_dimension": "architectural-stance",
  "capability_dimensions": [
    "heex-and-verified-routes",
    "function-components-and-slots",
    "live-components-stateful",
    "form-handling",
    "streams-and-collections",
    "mount-and-lifecycle",
    "event-handlers-and-handle-info",
    "pubsub-and-realtime",
    "navigation-patterns",
    "auth-and-authz",
    "anti-patterns-catalog"
  ],
  "challenges": {
    "total": 150,
    "by_tier": {
      "easy": 38,
      "medium": 45,
      "hard": 38,
      "legendary": 30
    },
    "held_out_ids": [
      "elixir-phoenix-liveview-easy-03",
      "elixir-phoenix-liveview-medium-12",
      "elixir-phoenix-liveview-hard-08",
      "elixir-phoenix-liveview-legendary-04"
    ]
  },
  "evaluation": {
    "score_script": "evaluation/score.py",
    "criteria_file": "evaluation/criteria.json",
    "environment_file": "evaluation/environment.yml"
  },
  "seeded_at": "2026-04-11",
  "tier_methodology": "heuristic",
  "tier_methodology_note": "Tiers assigned by drafting agent judgment per SEEDING-PLAN.md item 4. Empirical Haiku+Sonnet calibration is a future workstream."
}
```

The `held_out_ids` is ~20% of the total pool, balanced across tiers. Persisted here so champion evaluation always uses the same held-out subset.

---

## seed.json

Gen 0 SkillGenome — the starting point for evolution. Contains foundation + capability variants with starter SKILL.md text.

```json
{
  "family_slug": "elixir-phoenix-liveview",
  "generation": 0,
  "foundation_variants": [
    {
      "slug": "architectural-stance--strict-liveview",
      "dimension": "architectural-stance",
      "name": "Strict LiveView",
      "description": "Always favor LiveView over LiveComponent. Function components only for stateless rendering. Phoenix context handles all DB interaction.",
      "skill_md": "---\nname: architectural-stance--strict-liveview\ndescription: ...\n---\n\n# Architectural Stance — Strict LiveView\n\n## Quick Start\n...\n\n## When to use\n...\n\n## Workflow\n...\n\n## Examples\n...\n\n## Common mistakes\n..."
    }
  ],
  "capability_variants": [
    {
      "slug": "heex-and-verified-routes--idiomatic",
      "dimension": "heex-and-verified-routes",
      "name": "Idiomatic HEEx + Verified Routes",
      "description": "Use ~p sigil for all routes; HEEx :if/:for; never live_link or string-interpolated routes",
      "skill_md": "---\nname: heex-and-verified-routes--idiomatic\ndescription: ...\n---\n\n..."
    }
  ]
}
```

The drafting agent should produce one starter variant per dimension (1 foundation + N capabilities). The starter variants are intentionally simple — they get evolved later. The full SKILL.md body should follow the golden-template structure (Quick Start, When to use, Workflow, 2-3 Examples, Common mistakes) per CLAUDE.md.

---

## challenges/<tier>/<id>.json

One JSON file per challenge. Tier-bucketed in subfolders.

```json
{
  "id": "elixir-phoenix-liveview-medium-04",
  "tier": "medium",
  "title": "Migrate a 1.6 LiveView to 1.7 with verified routes",
  "prompt": "Convert this Phoenix 1.6 LiveView to use the 1.7 verified-routes syntax. Replace Routes.user_path with the ~p sigil and live_link with the new <.link> component. Preserve all functionality.",
  "fixture_files": [
    "test_fixtures/pre_1_7_user_form.ex"
  ],
  "expected_outputs": {
    "files": [
      "lib/my_app_web/live/user_live.ex"
    ],
    "must_contain": [
      "~p\"/users/",
      "<.form",
      ":if=",
      ":for="
    ],
    "must_not_contain": [
      "live_link",
      "Routes.user_path",
      "<%= for "
    ]
  },
  "scoring": {
    "primary_capability": "heex-and-verified-routes",
    "secondary_capabilities": [
      "form-handling"
    ],
    "criterion": "verified_routes_used",
    "weight": 0.3
  },
  "tier_rationale": "Migration requires recognizing two distinct deprecations and applying both correctly across multiple sites; vanilla Sonnet typically completes one but misses the other.",
  "calibration": null
}
```

### Required fields

- `id`: unique slug. Convention: `<family-slug>-<tier>-<NN>`. NN is zero-padded 2-digit.
- `tier`: one of `easy`, `medium`, `hard`, `legendary`.
- `title`: short human-readable summary (under 80 chars).
- `prompt`: the exact prompt the competitor will receive. Should be self-contained — assume the competitor has not read the README.
- `fixture_files`: list of relative paths (from the family folder) into `test_fixtures/`. Empty list `[]` if no fixtures needed.
- `expected_outputs`: what the score.py should check.
  - `files`: list of relative paths the competitor is expected to create.
  - `must_contain`: list of substrings/regex-safe patterns that must appear in the output.
  - `must_not_contain`: list of patterns that must NOT appear.
- `scoring`: how this challenge contributes to family fitness.
  - `primary_capability`: the capability slug being measured.
  - `secondary_capabilities`: additional capabilities touched in passing.
  - `criterion`: short slug for what's being checked.
  - `weight`: 0.0-1.0; relative weight within this challenge.
- `tier_rationale`: 1-2 sentences explaining why the drafting agent assigned this tier.
- `calibration`: always `null` for heuristic-tier. Empirical calibration block goes here later.

### Optional fields (when applicable)

- `setup_commands`: list of bash commands to run before the competitor sees the prompt (e.g., `["mix deps.get", "mix ecto.create"]`).
- `success_criteria_extra`: free-form natural-language criteria the competitor should aim for, beyond the structured `expected_outputs`.
- `time_limit_seconds`: max wall-clock for the competitor (default 600).
- `references`: list of file paths or URLs the competitor may consult during the challenge.

---

## challenges/_calibration.json

Calibration manifest for the family. Currently heuristic; empirical version will replace later.

```json
{
  "methodology": "heuristic",
  "calibration_deferred": true,
  "deferred_reason": "See taxonomy/elixir/SEEDING-PLAN.md item 4 — empirical Haiku+Sonnet calibration is a future workstream",
  "calibrated_date": null,
  "spec_version": "2.1",
  "tier_distribution": {
    "easy": 38,
    "medium": 45,
    "hard": 38,
    "legendary": 30
  },
  "capability_coverage": {
    "heex-and-verified-routes": {
      "primary_count": 14,
      "secondary_count": 8,
      "tier_breakdown": {"easy": 4, "medium": 5, "hard": 3, "legendary": 2}
    }
  },
  "tier_rubric_link": "../../SEEDING-PLAN.md#heuristic-tier-rubric"
}
```

`tier_distribution` totals must equal `family.json:challenges.total`. `capability_coverage` must list every capability declared in the family README + family.json.

---

## evaluation/criteria.json

Rubric weights per capability. Used by the L1 deterministic judge.

```json
{
  "family_slug": "elixir-phoenix-liveview",
  "capabilities": {
    "heex-and-verified-routes": {
      "weight": 0.15,
      "objectives": {
        "verified_routes_used": {"weight": 0.4, "description": "All routes use ~p sigil"},
        "heex_directives_used": {"weight": 0.3, "description": ":for and :if used over <%= for/if %>"},
        "no_old_link_helpers": {"weight": 0.3, "description": "No live_link or Routes.* helpers"}
      }
    },
    "form-handling": {
      "weight": 0.12,
      "objectives": {
        "uses_to_form": {"weight": 0.5, "description": "Form built via to_form/2"},
        "phx_change_validate": {"weight": 0.5, "description": "phx-change wired to validate handler"}
      }
    }
  },
  "pass_threshold": 0.7
}
```

- Capability weights sum to 1.0 across the family.
- Each capability's objectives sum to 1.0 within that capability.
- `pass_threshold` is the family-level fitness threshold for "competitor passed this challenge."

---

## evaluation/environment.yml

Declared dependencies for score.py. The sandbox runner verifies these before invoking score.py.

```yaml
runtime:
  language: python
  version: "3.12"
binaries:
  - python3
python_packages:
  - regex
optional_binaries:
  - elixir@1.16
  - mix@1.16
optional_services:
  - postgres@15
notes: |
  score.py uses regex + Python AST for static checks. No Elixir runtime
  required for scoring — we do not compile competitor output. Postgres
  is optional only if specific challenges include DB-state assertions.
```

`binaries` must be present on the runner. `optional_*` are nice-to-have. `python_packages` are pip-installable.

---

## evaluation/score.py — contract

Family-specific deterministic scorer. The sandbox runner invokes it as a subprocess.

### Input

- `--challenge PATH`: the challenge JSON file
- `--output DIR`: a directory containing the competitor's output files

### Output (stdout, JSON)

```json
{
  "challenge_id": "elixir-phoenix-liveview-medium-04",
  "passed": true,
  "score": 0.85,
  "objectives": {
    "verified_routes_used": {
      "passed": true,
      "weight": 0.4,
      "actual": "5 ~p sigils found",
      "expected": "all routes via ~p",
      "details": "Found 5 verified-route usages, 0 legacy Routes.* calls"
    }
  },
  "diagnostics": ["minor: line length over 100 in 3 places"]
}
```

### Exit codes

- 0: scoring completed successfully (pass or fail).
- 1: malformed input (missing challenge JSON, invalid JSON, missing required fields).
- 2: internal scorer bug (uncaught exception).

### Validation procedure

After authoring score.py, the Phase 4 subagent must:

1. **Sanity check**: run score.py against each `golden/*.ex` file (treating it as the competitor output for the corresponding challenge). Score must be ≥0.9.
2. **Discrimination check**: run score.py against an obviously-bad input (an empty file or a file containing all `must_not_contain` patterns). Score must be ≤0.3.
3. If either check fails, iterate on score.py up to 2 times.
4. If still failing after 2 iterations, mark `[NEEDS REVIEW]` in the family's `_calibration.json` `notes` field and ship.

### Recommended structure

```python
#!/usr/bin/env python3
"""SKLD-bench score.py for <family-slug>."""
import argparse
import json
import re
import sys
from pathlib import Path


def score_challenge(challenge: dict, output_dir: Path) -> dict:
    """Family-specific scoring logic."""
    objectives = {}
    expected = challenge.get("expected_outputs", {})
    
    for rel in expected.get("files", []):
        f = output_dir / rel
        if not f.exists():
            objectives[f"file:{rel}"] = {
                "passed": False, "weight": 1.0,
                "actual": "missing", "expected": "present",
                "details": f"Expected output file {rel} was not produced",
            }
            continue
        content = f.read_text()
        
        for pat in expected.get("must_contain", []):
            objectives[f"contains:{pat}"] = {
                "passed": pat in content,
                "weight": 1.0 / max(len(expected.get("must_contain", [])), 1),
                "actual": "present" if pat in content else "absent",
                "expected": "present",
                "details": f"Looking for `{pat}` in {rel}",
            }
        
        for pat in expected.get("must_not_contain", []):
            objectives[f"absent:{pat}"] = {
                "passed": pat not in content,
                "weight": 1.0 / max(len(expected.get("must_not_contain", [])), 1),
                "actual": "absent" if pat not in content else "present",
                "expected": "absent",
                "details": f"Looking for absence of `{pat}` in {rel}",
            }
    
    total_weight = sum(o["weight"] for o in objectives.values()) or 1.0
    weighted_score = sum(o["weight"] for o in objectives.values() if o["passed"])
    score = weighted_score / total_weight
    
    return {
        "challenge_id": challenge["id"],
        "passed": score >= 0.7,
        "score": score,
        "objectives": objectives,
        "diagnostics": [],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--challenge", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    
    try:
        challenge = json.loads(args.challenge.read_text())
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(json.dumps({"error": f"malformed challenge: {e}"}))
        sys.exit(1)
    
    try:
        result = score_challenge(challenge, args.output)
    except Exception as e:
        print(json.dumps({"error": f"scorer crashed: {e}"}))
        sys.exit(2)
    
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
```

This skeleton handles the contract correctly. Family-specific logic should extend `score_challenge` with:
- Regex/AST checks for the family's domain (e.g., AST analysis of pattern-match function heads for `elixir-pattern-match-refactor`)
- Capability-aware scoring (weight objectives by which capability they measure)
- Anti-pattern detection (penalize specific known-bad patterns from the research dossier)

---

## golden/*.ex

Reference correct solutions. Used by score.py validation (above) and as the "what does correct look like" anchor for future calibration.

Naming: `golden/<challenge-id>.ex` for single-file challenges, `golden/<challenge-id>/<file>.ex` for multi-file.

---

## test_fixtures/*.ex

Immutable input files referenced by challenge `fixture_files` arrays. The "starter code" the competitor receives.

Naming: descriptive (e.g., `pre_1_7_user_form.ex`, `n_plus_one_query.ex`, `vulnerable_handle_event.ex`). Reuse fixtures across challenges where reasonable to keep the fixture set tractable (~5-15 files per family).
