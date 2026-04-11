# elixir-ecto-schema-changeset

**Rank**: #5 of 22
**Tier**: A (high-value, good evidence)
**Taxonomy path**: `data` / `ecto-orm` / `elixir`
**Status**: ✅ Validated by research — `:float` for money is a clinching evidence item

## Specialization

From a domain model description, generates Ecto schemas, migrations, and changesets with the right field types, validations, DB-level constraints, and associations (`has_many`, `belongs_to`, `many_to_many`, `embeds_one`, `embeds_many`). Enforces functional Elixir patterns over ActiveRecord/Django carryover.

## Why LLMs struggle

Claude treats Ecto schemas like ActiveRecord models — methods on structs, mass assignment without thinking, ORM-style associations. Specific failure modes:

- **`:float` for money fields** — silent data corruption; named iron law in `oliver-kriska/claude-elixir-phoenix`
- Forgetting `cast/3` + `validate_required/2` on changesets
- Mixing up `has_many` vs `belongs_to` direction
- Forgetting that `unique_constraint/2` requires a matching DB-level unique index in the migration
- Conflating migration code (`alter_table`) and schema code (`field`)
- Polymorphic association attempts (Ecto doesn't natively support them)

## Decomposition

### Foundation
- **F: `schema-organization`** — Flat schemas vs nested embeds vs cross-context splits. Variants: single-source-of-truth (one schema per concept), context-scoped (separate schemas per bounded context), hybrid. Locks in how every field/association/changeset is shaped.

### Capabilities
1. **C: `field-types-and-decimal`** ⭐ — Picking the right `field` types; **`:decimal` for money, NEVER `:float`**; `:utc_datetime` vs `:naive_datetime`
2. **C: `associations`** — `has_many`, `belongs_to`, `many_to_many`, `has_one`, `through:` associations
3. **C: `embedded-schemas`** — `embeds_one`, `embeds_many`, when to embed vs associate
4. **C: `validations-basic`** — `validate_required`, `validate_length`, `validate_format`, `validate_inclusion`, `validate_number`
5. **C: `validations-custom`** — `validate_change/3`, `validate_confirmation/2`, cross-field validations
6. **C: `unique-constraints-and-indexes`** — DB-level unique index + changeset `unique_constraint/2` (must match!)
7. **C: `cast-and-allowed-fields`** — `cast/3`, `cast_assoc/3`, `cast_embed/3`; mass assignment safety
8. **C: `migrations`** — `create_table`, `alter_table`, `add`, `remove`, indexes, foreign keys
9. **C: `polymorphic-associations`** — The tradeoffs; Ecto doesn't natively support them; common workarounds
10. **C: `soft-deletes-and-timestamps`** — `deleted_at` patterns, `timestamps()` macro, `updated_at` triggers
11. **C: `multi-tenant-schemas`** — `prefix:` option, schema-per-tenant patterns

### Total dimensions
**12** = 1 foundation + 11 capabilities

## Evaluation criteria sketch

- **Money field test**: build a Product schema with a price field; score.py checks the field type is `:decimal`, not `:float`
- **Association test**: build a Post schema with many tags via `many_to_many`; verify join table migration + association declarations match
- **Unique constraint test**: build a User schema with unique email; verify both `unique_index` in migration AND `unique_constraint(:email)` in changeset
- **Mass assignment test**: build a User schema where role is set by admins only; verify `cast/3` excludes role from public changesets
- **Embed vs assoc test**: build an Order with line items; ask the skill to justify embeds_many vs has_many for this case

## Evidence

- [Research report Part 1 #5](../../docs/research/elixir-llm-pain-points.md#5-float-for-money-in-ecto)
- [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix) — `:float` iron law

## Notes

- The `:decimal`-not-`:float` rule is the single highest-confidence safety fix in this family. Bake it into the foundation's voice.
- Closely linked to `elixir-ecto-query-writer` — they share schema definitions. Both families' challenges should reference the same fixture schemas to keep evaluations comparable.
- Polymorphic associations capability is interesting because the "correct answer" is "don't" — that's a teachable Elixir vs Rails distinction.
