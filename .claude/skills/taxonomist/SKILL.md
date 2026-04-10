---
name: taxonomist
description: >-
  Classifies a skill spec into Domain → Focus → Language, checks existing
  taxonomy for reuse, decomposes complex skills into variant dimensions, and
  decides atomic vs monolithic mode. NOT for running evolution or judging.
allowed-tools: Read Bash(python *) Bash(bash *)
---

# Taxonomist

## Quick Start
Given a free-form skill specialization, (1) classify it into the 3-level hierarchy Domain → Focus → Language using existing slugs when possible, (2) decide whether it should be evolved atomically or as a monolith based on dimension count, and (3) surface reusable variants from related families. Always check before creating new taxonomy entries.

## When to use this skill
Use before an evolution run begins, when a user describes a new skill they want ("make me a pytest generator for Django"), when the registry needs a family assigned to an unclassified seed, when deciding between molecular and atomic evolution mode, when the user mentions "category", "classify", "taxonomy", "decompose", "split into dimensions", "where does this fit", or asks which existing skills might overlap. Also triggers during startup seeding and during `POST /api/evolve` auto-classification.

## Workflow

### Step 1: Read the hierarchy rules and reuse principle
Read `${CLAUDE_SKILL_DIR}/references/taxonomy-guide.md` for the 3-level hierarchy definition, the reuse-first principle, naming rules, and the decomposition heuristic.

Read `${CLAUDE_SKILL_DIR}/references/historical-metrics.md` to check whether any relevant taxonomy nodes have historical performance data that should weight your decisions.

### Step 2: Gather the existing taxonomy
Before classifying, query the platform for what already exists:
- Existing `taxonomy_nodes` at each level (domain / focus / language)
- Existing `skill_families` with their specialization text
- Existing `variants` grouped by family and dimension (for cross-family reuse)

The calling agent passes these as slug lists. Never invent a new slug without first running the classifier against the existing ones.

### Step 3: Run the classifier
Run:
```
python ${CLAUDE_SKILL_DIR}/scripts/classify.py \
  --specialization "<free-form spec text>" \
  --existing-slugs "<comma-separated slugs>"
```

The script returns JSON with `best_match_slug`, `confidence`, `suggested_new`, and a `ranked_matches` list. Confidence ≥ 0.4 means a reasonable existing match; below that threshold means no existing slug fits and a new one should be proposed.

Run it three times — once per hierarchy level — with the correct slug list each time (domain slugs, then focus slugs within the chosen domain, then language slugs).

### Step 4: Decide: reuse or create new
- **Reuse** (default): if confidence ≥ 0.4 at a level, adopt the existing slug.
- **Create new**: only when confidence < 0.4 AND the specialization genuinely doesn't reduce to an existing category. Every new entry needs a one-line justification logged with the classification result.

Never create a new domain casually — domains are the most stable layer. New focuses are more acceptable. New languages are rare (the list is near-fixed).

### Step 5: Decompose into variant dimensions
Apply the decomposition heuristic from `taxonomy-guide.md`:
- Identify candidate dimensions a user could meaningfully swap (e.g., fixture strategy, mock strategy, assertion style).
- A dimension must be independently testable and independently evolvable.
- **If ≥ 2 meaningfully independent dimensions exist → recommend `"atomic"` mode.**
- **Otherwise → recommend `"monolithic"` mode** (v1.x pipeline, no decomposition overhead).

Split dimensions into two tiers:
- **Foundation**: structural decisions (fixture strategy, project conventions, test scaffolding). Evolved first.
- **Capability**: focused modules that plug into the foundation (mock strategy, assertion patterns, edge-case generation).

### Step 6: Recommend cross-family reuse
Scan the variant list the caller provided. If any high-fitness variant in a **related family** (same Focus or same Language, close specialization) covers one of the dimensions you just identified, flag it as a reuse candidate so the Engineer can plug it in instead of re-evolving from scratch.

### Step 7: Validate the classification output
Write the classification + decomposition result as JSON (per the schema in `taxonomy-guide.md`) and run:
```
bash ${CLAUDE_SKILL_DIR}/scripts/validate.sh <path-to-classification.json>
```
Fix any issues the validator reports before returning to the caller.

## Examples

**Example 1: New skill, clear fit, two independent dimensions → atomic**
Input specialization: `"Generate pytest unit tests for Django REST framework views with mocked database calls and factory-boy fixtures."`
Existing domain slugs: `testing, security, devops, data, code-quality, documentation, architecture`
Existing focus slugs under testing: `unit-tests, integration-tests, e2e, property-based`
Existing language slugs: `python, javascript, rust, sql, universal`
Output:
```json
{
  "domain": {"slug": "testing", "confidence": 0.91, "reused": true},
  "focus": {"slug": "unit-tests", "confidence": 0.88, "reused": true},
  "language": {"slug": "python", "confidence": 0.97, "reused": true},
  "family_slug": "django-rest-pytest",
  "specialization": "Generate pytest unit tests for Django REST framework views with mocked DB calls and factory-boy fixtures.",
  "decomposition_strategy": "atomic",
  "dimensions": [
    {"name": "fixture-strategy", "tier": "foundation",
     "description": "How test fixtures + factory-boy scaffolding are organized.",
     "evaluation_focus": "reusability + setup cost"},
    {"name": "mock-strategy", "tier": "capability",
     "description": "Approach to mocking DB + external calls (unittest.mock vs pytest-mock vs responses).",
     "evaluation_focus": "isolation score + test speed"},
    {"name": "assertion-patterns", "tier": "capability",
     "description": "Style of assertions (status code checks, DRF response.data shape, snapshot).",
     "evaluation_focus": "clarity + failure message quality"}
  ],
  "cross_family_reuse": [
    {"source_family": "flask-pytest", "dimension": "mock-strategy",
     "variant_slug": "responses-lib-mock", "fitness": 0.89,
     "reason": "Same Focus + Language, proven mock strategy for HTTP-heavy views."}
  ]
}
```

**Example 2: Simple skill, one dimension → monolithic**
Input specialization: `"Parse CSV files into typed Python dataclasses with header inference."`
Output:
```json
{
  "domain": {"slug": "data", "confidence": 0.72, "reused": true},
  "focus": {"slug": "parsing", "confidence": 0.31, "reused": false,
            "justification": "No existing 'parsing' focus; specialization is tight CSV-to-dataclass mapping, distinct from etl/cleaning."},
  "language": {"slug": "python", "confidence": 0.98, "reused": true},
  "family_slug": "csv-to-dataclass",
  "decomposition_strategy": "monolithic",
  "dimensions": [],
  "reason": "Only one coherent module (header inference + dataclass generation). No independently-swappable substrategies — atomic overhead not justified.",
  "cross_family_reuse": []
}
```

**Example 3: Near-miss specialization, forces reuse check**
Input specialization: `"Review Kubernetes YAML for security posture."`
Existing focus slugs under security: `static-analysis, injection, crypto, supply-chain`
Output:
```json
{
  "domain": {"slug": "security", "confidence": 0.85, "reused": true},
  "focus": {"slug": "static-analysis", "confidence": 0.56, "reused": true,
            "reason": "Closest existing category — K8s manifest review is a form of static analysis."},
  "language": {"slug": "yaml", "confidence": 0.22, "reused": false,
               "justification": "No existing YAML language node; Kubernetes manifests are config-as-data, distinct from general-purpose languages."},
  "family_slug": "k8s-security-review",
  "decomposition_strategy": "atomic",
  "dimensions": [
    {"name": "rule-set", "tier": "foundation",
     "description": "Which security rule catalog drives the review (CIS, NSA, custom).",
     "evaluation_focus": "coverage + false positive rate"},
    {"name": "reporting-format", "tier": "capability",
     "description": "How findings are reported (SARIF, markdown table, inline patches).",
     "evaluation_focus": "actionability"}
  ]
}
```

## Gotchas
- **Confidence threshold**: 0.4 is the floor for reuse. Tuning it up creates taxonomy sprawl; tuning it down hides genuinely new categories. Don't change it without logging why.
- **Don't re-run classification across levels independently without re-scoping slug lists.** Focus slugs must be filtered to the chosen domain's children; passing the global focus list inflates matches.
- **Dimensions that aren't independently testable are not dimensions.** "Assertion phrasing style" cannot be scored in isolation — it's part of assertion-patterns, not its own axis.
- **New domains are a red flag.** If your classifier wants a new domain, pause and ask: is this really a new problem space, or a new focus inside an existing domain? The domain layer should grow maybe once a quarter.
- **Historical-metrics staleness**: `historical-metrics.md` is a schema template until Wave 4 populates it. Don't over-weight empty data.
- **Cross-family reuse needs same Focus or Language** as the anchor. Recommending a Rust crypto variant for a Python web-security skill is noise, not signal.

## Out of Scope
This skill does NOT:
- Design evaluation challenges or rubrics (that's the Scientist).
- Spawn initial variant populations (that's the Spawner).
- Evaluate fitness or compute metrics (that's the Reviewer).
- Mutate or breed variants across generations (that's the Breeder).
- Assemble composite skills from winning variants (that's the Engineer).
- Run the evolution engine or kick off runs (that's the orchestrator).
