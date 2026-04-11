# elixir-binary-pattern-match

**Rank**: #21 of 22
**Tier**: E (brainstormed runner-up; no research signal)
**Taxonomy path**: `development` / `otp-primitives` / `elixir`
**Status**: Brainstormed; low-level protocols

## Specialization

Writes Elixir code that uses binary pattern matching for parsing low-level protocols: `<<...>>` syntax with size specifiers, byte-level and bit-level matching, UTF encoding handling, length-prefixed protocols, fixed-width records, and binary comprehensions.

## Why this family is here

Elixir's binary pattern matching is one of its standout features for protocol-level work (parsing PNG headers, BERT, CBOR, custom wire formats). LLMs barely know it exists in the training data. But the audience is very small — most application code never touches binaries directly.

The research found **no specific binary-pattern-matching complaints**, possibly because the small audience doesn't generate visible web discussion.

## Decomposition

### Foundation
- **F: `binary-parsing-style`** — Byte-level vs bit-level, streaming vs all-at-once

### Capabilities
1. **C: `basic-binary-matching`** — `<<prefix::bytes-size(4), rest::binary>>` patterns
2. **C: `size-specifiers`** — `::integer-8`, `::little-endian`, `::float-32`, `::signed`/`::unsigned`
3. **C: `utf-and-encoding`** — `::utf8`, `::utf16`, codepoint handling
4. **C: `protocol-parsers`** — Length-prefixed, delimited, fixed-width protocols
5. **C: `binary-comprehensions`** — `for <<b <- binary>>`, construction with `<<>>`

### Total dimensions
**6** = 1 foundation + 5 capabilities

## Notes

- Very specialized. Build only if a specific user is doing binary protocol work.
- This is one of Elixir's most powerful features for low-level work but most application devs never need it. Low priority.
