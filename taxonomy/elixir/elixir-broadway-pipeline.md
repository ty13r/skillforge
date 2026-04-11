# elixir-broadway-pipeline

**Rank**: #17 of 22
**Tier**: E (brainstormed runner-up; no research signal)
**Taxonomy path**: `development` / `data-pipelines` / `elixir`
**Status**: Brainstormed; enterprise niche

## Specialization

Writes Broadway data ingestion pipelines: producers (RabbitMQ, SQS, Kafka, Google Pub/Sub, custom), processors with `handle_message/3`, batchers with `handle_batch/4`, rate limiting, concurrency tuning, and pipeline error handling.

## Why this family is here

Broadway is the canonical Elixir library for data ingestion pipelines. It's a strong fit for SkillForge because pipeline shape decisions have clear "right and wrong" answers that score.py can verify. But the audience is narrower than Phoenix/Ecto — Broadway is mostly used in enterprise data engineering contexts.

The research found **no specific Broadway-related Claude failures**. Lower priority unless you're explicitly targeting data engineering workloads.

## Decomposition

### Foundation
- **F: `pipeline-shape`** — Linear vs branched, single-stage vs multi-stage

### Capabilities
1. **C: `producer-modules`** — RabbitMQ, SQS, Kafka, Google Pub/Sub, custom producers
2. **C: `processor-modules`** — `handle_message/3` implementations, message transformations
3. **C: `batcher-modules`** — `handle_batch/4`, batch size, batch timeout
4. **C: `rate-limiting`** — `max_demand`, `min_demand`, throttling
5. **C: `concurrency-tuning`** — Processor concurrency, batcher concurrency, partitioning
6. **C: `error-handling-in-pipeline`** — Message failure, dead-letter queues, retry policies
7. **C: `testing-broadway`** — `Broadway.test_message/3`, `Broadway.test_batch/3`, assertions

### Total dimensions
**8** = 1 foundation + 7 capabilities

## Notes

- Niche but well-defined family. If a SkillForge user is doing serious data ingestion in Elixir, this would be valuable.
- Build only after the core Phoenix/Ecto/Oban families ship.
