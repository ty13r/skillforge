# The SKLD Bible

*Empirical knowledge about building skills for AI coding agents, organized into books.*

---

## What This Is

The Bible is SKLD's knowledge base — everything we've learned about how to build, evaluate, and evolve AI agent skills. Every finding is backed by measured data from real experiments, not theory or intuition.

The knowledge is organized into books:

## Books

### [Book of Genesis](book-of-genesis.md)
Universal principles that apply regardless of programming language or domain. Covers the scoring problem, the self-containment problem, skills as a cost equalizer, data capture, and evolution dynamics. Start here if you're new.

### [Book of Elixir](book-of-elixir.md)
Elixir-specific findings from evolving 7 skill families across 867 challenges. Covers per-family compile rates, the context dependency spectrum, Phoenix LiveView idiom detection, Ecto schema dependencies, and the full mock run results.

## Reference Material

### [patterns/](patterns/)
The original skill design patterns from the Skills Research phase. These cover description writing, instruction budgets, script usage, structural conventions, and progressive disclosure. Referenced by Genesis Chapter 6 with full provenance.

### [findings/](findings/)
Raw findings from early SkillForge evolution runs. These are incomplete (placeholder mechanism sections) and have been largely superseded by the empirical data in Genesis and Elixir. Kept for historical reference.

## How This Knowledge Was Generated

Unlike traditional best-practice guides written from experience, the Bible's findings come from controlled experiments:

1. **867 coding challenges** authored across 7 Elixir domain families
2. **Raw model baselines** established by dispatching Sonnet against every challenge with no skill guidance
3. **Skill-guided benchmarks** measured by adding evolved SKILL.md content to the same challenges
4. **Multi-level scoring** (string matching + compilation + AST analysis + behavioral testing) to evaluate output quality
5. **Evolutionary competition** where variant skills compete on real challenges and winners are selected by composite fitness

Every chapter cites the specific experiment, journal entry, or data source where the finding was discovered.

## Future Books

As SKLD expands to new languages and domains, each will get its own book:
- **Book of TypeScript** (planned)
- **Book of Python** (planned)
- **Book of Infrastructure** (planned — Terraform, Docker, CI/CD)

The Genesis principles will apply across all of them. Language-specific books will document what's unique to each ecosystem.

---

*Built by [SKLD](https://github.com/ty13r/skillforge) — Skill Kinetics through Layered Darwinism.*
