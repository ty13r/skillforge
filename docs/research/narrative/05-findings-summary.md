# Findings Summary

> **Status:** provisional · **Depth:** partial · **Last updated:** 2026-04-18
>
> Seven findings are documented with primary-source evidence, but several rely on single-run experiments (e.g. the 18-output deep-dive). Promotion to "stable" is gated on multi-run variance measurement and cross-family replication.

The headline findings from SKLD so far. This page is an index, not a duplicate — the full empirical record lives in the Claude Skills Bible ([`/bible`](https://skld.run/bible)), which tracks universal principles (Genesis) and language-specific findings (Elixir). Findings here link into the Bible where the evidence lives.

---

## 1. String matching cannot tell good code from bad code

Raw Sonnet with no skill attached scored **93.3% average** on string-match-only evaluation across all 867 SKLD-bench challenges. Five of six sources scored identically on the hardest Phoenix LiveView challenge. Compilation caught a syntax-error output that string matching ranked as best. Behavioral tests dropped the Sonnet baseline to 51.1%.

Evidence: [`/bible/books/book-of-genesis`](https://skld.run/bible/books/book-of-genesis) §1.1-1.3. Primary source: Journal #14, deep-dive experiment (18 outputs × 4 scoring levels).

**Implication for the field.** Any skill-evaluation benchmark that is only keyword matching is overclaiming. The headline number is measuring *"does this look like code?"* not *"does this code work?"* This is how we ended up with 7 shipped seed runs where nobody knew the scores were meaningless.

---

## 2. Skills are a Sonnet equalizer, not an Opus accelerator

Across the 18-output deep-dive, Sonnet jumped from 0.11 to 0.64 (6× improvement) with a skill attached. Opus raw already scored 0.64 without any skill. On Opus, the same skills produced small gains or — in one case — regression (Opus + v1 skill was the only compile failure across all 18 outputs; the skill guided it toward an invalid capture pattern).

The economic consequence is non-trivial. A skill that lifts Sonnet to Opus's level while keeping Sonnet's per-token cost (roughly 1/5 of Opus) reframes the value proposition: skills are how you run a cheaper model for the same output quality, not how you push the best model further.

Evidence: [`/bible/books/book-of-genesis`](https://skld.run/bible/books/book-of-genesis) Chapter 3. Primary source: Journal #14.

---

## 3. Models write context-dependent code by default; isolation is a selection pressure

When asked to write a module, Claude writes it the way a developer would: assuming the rest of the application exists. A Phoenix LiveView module references `MyApp.Blog.list_posts/1`. An Ecto schema references `MyApp.Repo`. None of these exist in a test scaffold, so the code compiles (the names are syntactically valid) but crashes at runtime.

This is exactly what an evolution loop can fix. Variants that produce self-contained code pass behavioral tests; variants that assume external context do not. Over generations, the Breeder discovers "stub dependencies" and "inline sample data" as winning traits — without being told to. In the Phase 5 mock run, the spawned `mount-and-lifecycle` variant outperformed the seed by +0.256 composite delta, driven entirely by self-containment.

Evidence: [`/bible/books/book-of-genesis`](https://skld.run/bible/books/book-of-genesis) Chapter 2.

---

## 4. Compilation is the cheapest high-value gate

A single binary check — does this code compile? — dropped the Sonnet baseline from 93.3% to 68.4%. Cost: roughly 1 second per check (cached). Caught 46% of outputs that scored above 0.70 on string matching. Eight outputs scored above 0.85 on L0 but did not compile at all.

Adopt compilation gating before reaching for LLM-based quality scoring. It eliminates an entire class of ghost passes at near-zero cost.

Evidence: [`/bible/books/book-of-genesis`](https://skld.run/bible/books/book-of-genesis) §1.2.

---

## 5. Behavioral tests dominate the signal

Across the 18-output deep-dive, behavioral tests were the only metric that separated working code from broken code when every other layer tied. Opus raw passed 12/12 on hard-07. Sonnet + v2 skill passed 5/12. Sonnet raw passed 0/12 — its code compiled fine but called undefined modules.

Behavioral tests carry the dominant 40% weight in the composite scorer because they are the only layer that consistently ranks working code above broken code. If you only had budget for one evaluation layer beyond compilation, this would be it.

Evidence: [`/bible/books/book-of-genesis`](https://skld.run/bible/books/book-of-genesis) §1.3, [`docs/research/narrative/04-evaluation.md`](https://skld.run/research/narrative/04-evaluation) §L3.

---

## 6. Elixir-specific failure patterns cluster tightly

The Elixir language-specific findings ([`/bible/books/book-of-elixir`](https://skld.run/bible/books/book-of-elixir)) aggregate into a short list of failure modes that repeat across families:

- Ruby-style imperative code (if/else chains, defensive nil-checking, early returns) instead of pattern matching.
- References to non-existent application modules (`MyApp.Blog`, `MyApp.Repo`) assumed to exist.
- Missing pipe operators where they would simplify.
- Over-eager `try/rescue` blocks where tagged-tuple returns would be idiomatic.
- LiveView event handlers that call undefined helpers.

These are audited in `docs/research/audits/elixir-llm-pain-points.md` (primary-source post-mortems and plugin-repo "iron laws") and confirmed by the SKLD-bench per-challenge data.

---

## 7. Atomic decomposition reduces cost and sharpens signal

v2.0 atomic evolution costs roughly half to three-quarters of molecular (v1.x) evolution for the same or better fitness outcomes. Per-dimension fitness is clean rather than averaged. Winning variants are composable across families — a great mock strategy evolved for one family is reusable as a capability variant in another.

Evidence: journal entries #9 and #11; the seven seed runs produced in the v2.0 cohort; `plans/SPEC-V2.0.md`.

---

## What these findings do not yet prove

These are early results. None of the following is established:

- That evolved skills *generalize* across languages (SKLD-bench is Elixir-only).
- That evolved skills produce *sustained* fitness gains over many generations without hitting a ceiling.
- That reflective mutation is *quantitatively* better than random mutation (we have informal comparison, not an ablation).
- That the held-out score is meaningfully different from the training score (we have the infrastructure; the experiment is pending).

See [`06-open-questions.md`](06-open-questions.md) for the full list of uncomfortable questions that are still open.

---

*Findings are promoted from individual evolution runs into the Claude Skills Bible when they are confirmed across multiple families and supported by audit-able primary-source evidence. The Bible is the authoritative record; this page is the briefing.*
