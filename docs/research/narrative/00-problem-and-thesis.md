# Problem & Thesis

## The problem

A **Claude Agent Skill** is a structured instruction set — a `SKILL.md` file plus optional scripts and reference documents — that tells Claude how to behave when a specific kind of task shows up. A good skill changes Claude from a generalist into a specialist: it triggers on the right queries, it follows the right workflow, it avoids the domain's common failure modes.

Writing a great skill is surprisingly hard. A skill has to simultaneously get four things right:

1. **Trigger conditions** — a 250-character description that makes Claude activate the skill on the right queries and not activate it on the wrong ones.
2. **Instructions** — a workflow that survives real tasks without padding its way to an answer or skipping steps.
3. **Supporting scripts** — deterministic operations offloaded from the model so it doesn't burn tokens re-implementing a parser on every call.
4. **Reference material** — domain knowledge the model can pull in on demand instead of carrying in its pre-training.

A small change in any of these can shift output quality dramatically. Humans optimize one dimension and neglect the others: we tune the instructions until they read well, then ship, and discover in production that the trigger is too narrow or the scripts get ignored. The space is too high-dimensional, too coupled, and too sensitive to hand-tune.

There is also no agreed method for showing that a particular skill is *actually better* than the model without it. Most skill evaluation in the wild is vibe-based: ship the skill, ask a few test queries, see if the output "feels" better. On a real benchmark — with compilation gates, behavioral tests, and a held-out set — many published skills don't lift the model at all.

## The thesis

Evolutionary pressure, applied systematically to the components of a skill and scored against a controlled benchmark, produces skills that outperform hand-written ones. More specifically:

- **LLMs are competent evolutionary operators.** A mutating LLM that reads the trace of a failed run can propose a targeted fix better than random mutation can. This is borrowed from GEPA (see `01-prior-art.md`) and validated on our own runs.
- **Atomic decomposition sharpens the fitness signal.** Evolving a whole SKILL.md as one blob averages the contribution of every trait. Decomposing the skill into foundation and capability *variants*, evolving each under narrow selection pressure, then assembling the winners, produces clear per-trait signal and cheaper runs. See `02-methodology.md` for the mechanics, `03-rigor-arc.md` for how we arrived at it.
- **Honest scoring is a prerequisite, not a detail.** A scorer that can't tell good code from bad code makes every downstream claim meaningless. Our six-layer composite scorer (`04-evaluation.md`) emerged from discovering exactly this failure mode in our own system (Journal #14).
- **Skills are an equalizer, not an accelerator.** Empirically, a well-evolved skill brings a cheap model (Sonnet) up to the level of an expensive one (Opus), but does not push Opus further. This has economic consequences for who benefits from skill engineering.

## Falsifiable claims

These are the claims SKLD stakes out. Each one is testable against SKLD-bench.

1. **Evolved skills outperform hand-written seeds.** On the held-out tier of SKLD-bench, the composite-fitness score of an evolved skill exceeds the score of the seed skill from which it descended. Tested per family, per dimension, per generation.
2. **Atomic evolution beats molecular evolution on cost-to-quality.** For the same fitness delta, atomic evolution spends less API budget and wall-clock than molecular evolution. Tested by re-running v1.x and v2.0 on the same family.
3. **Trace-informed mutation beats random mutation.** Reflective mutation that reads the failing run's execution trace produces higher-fitness offspring per generation than random mutation. Tested with an ablation.
4. **A skill lifts Sonnet toward Opus, not Opus above itself.** On SKLD-bench, Sonnet + evolved skill approaches Opus raw; Opus + the same skill does not meaningfully exceed Opus raw. This is a prediction, not a wish — and if it turns out to be wrong, that's the more interesting result.

Any of these claims is fair to challenge. The rest of the Research section exists to make the challenge possible: methodology (`02`), rigor arc (`03`), evaluation (`04`), findings so far (`05`), and what is still unresolved (`06`).

## What SKLD is not claiming

- Not claiming that every skill benefits from atomic evolution. Trivial skills (git-commit-message, single-verb operations) probably don't need decomposition. The Taxonomist decides.
- Not claiming the evolved skills are optimal. They are better than the seeds that produced them, measured against a specific benchmark. The benchmark has known limits (see `06-open-questions.md`).
- Not claiming this replaces human prompt engineering. Humans still author the seeds, curate the challenge pools, and write the scoring rubrics. The evolution is a sharpening, not a generation-from-zero.
- Not claiming generalization across languages is proven. Every lighthouse family in SKLD-bench is currently Elixir. Cross-language generalization is the next experiment, not a landed result.

---

*SKLD is an experiment in whether evolutionary pressure, applied to a structured artifact (Agent Skills) with a rigorous benchmark (SKLD-bench), can produce capabilities that exceed what human prompt engineers can hand-tune. Early results suggest yes. The purpose of this Research section is to document the method in enough detail that the results are challengeable.*
