# elixir-ecto-schema-changeset — Per-Capability Research Dossier

**Generated**: 2026-04-11
**Workstream**: SKLD-bench v2.1 (see [`../SEEDING-PLAN.md`](../SEEDING-PLAN.md))
**Sources surveyed**: oliver-kriska/claude-elixir-phoenix Iron Laws catalog, georgeguimaraes/claude-code-elixir ecto-thinking skill, Ecto official docs (Ecto.Schema, Ecto.Changeset, Ecto.Migration, embedded schemas guide, polymorphic associations guide, multi-tenancy guide), Dashbit blog (associations/embeds, soft deletes), Phoenix official security guide, Paraxial.io Elixir security checklist, Arrowsmith Labs (foolproof unique constraints), Elixir Forum threads (money/decimal, polymorphism, current-status-of-LLMs), GitHub Ecto issues (#2473 decimal comparison, #2683 naive_datetime default, #3432 nested cast_embed), Retrovertigo blog (on_delete), BoothIQ post-mortem, `docs/research/elixir-llm-pain-points.md`
**Total citations**: 47

## Family-level summary

This family is anchored by a single canonical Claude failure that the community has formalized as an iron law: **`:float` for money fields causes silent data corruption, and Claude defaults to it.** Oliver Kriska's widely-used Claude plugin for Elixir/Phoenix lists "Never use `:float` for money" as a non-negotiable rule specifically because observed Claude output consistently reaches for `:float` when asked to model monetary values. This is the highest-confidence, highest-severity item in the family, and it alone justifies the family's existence as a bench pool. Every adjacent behavior — picking `:utc_datetime` vs `:naive_datetime`, knowing when to use `Decimal.equal?/2` vs `==`, and understanding that Phoenix generators historically default to `:naive_datetime` for timestamps (which maintainers admit was a historical accident) — clusters around the same skill: Claude treats Ecto field typing like a Rails/Django bag of loose primitives rather than as a precision-sensitive contract with Postgres.

The second large cluster is **changeset hygiene and mass assignment safety**. Phoenix's own security guide and Paraxial.io's security checklist document a live vulnerability where a developer puts `:is_admin` in their `cast/3` allowlist; Claude happily replicates this pattern when it sees a schema with an `is_admin` field because the mental model ported from ActiveRecord doesn't include the "explicit allowlist" discipline Ecto enforces. Related failures in this cluster: using `put_change/3` to bypass `cast/3`, omitting `validate_required` for the fields actually needed, writing `cast_assoc/3` against an association that isn't preloaded (runtime error), and forgetting that `unique_constraint/2` in the changeset does literally nothing unless a matching DB-level `unique_index` exists in the migration. Arrowsmith Labs puts this last one plainly: "unique_constraint/3 only achieves anything if your database actually has a uniqueness constraint on the given column."

The third cluster is **Rails-brained association modeling**. Ecto's official docs explicitly warn against Rails-style polymorphic associations ("this design breaks database references"), and Elixir Forum experts routinely redirect developers away from `imageable_type + imageable_id` workarounds. The recommended pattern — separate join tables with `many_to_many` — is counter-intuitive to anyone whose mental model comes from ActiveRecord, and Claude's training corpus is heavily weighted toward Rails. Similar failures: putting the foreign key on the wrong side of a `has_many` / `belongs_to` pair, missing `references(..., on_delete: :delete_all)` in migrations (default is `:nothing`, which leaks orphan rows silently), and choosing `has_many` when `embeds_many` is the right modeling call (or vice versa). Dashbit and the official Ecto embedded-schemas guide emphasize that "a record can only be embedded in a single parent, you can't model a many-to-many relationship with embedded records" — a correctness boundary Claude routinely crosses.

The fourth cluster, **niche-but-real**, covers soft deletes (`deleted_at` patterns and partial indexes), multi-tenant `prefix:` option, custom validators via `validate_change/3`, and `cast_embed/3` / `cast_assoc/3` nesting behavior. Evidence for these is thinner — mostly library docs and domain experts' posts — but each one is referenced in at least one plugin or community post as something Claude gets wrong by default. The thinnest capability in terms of public Claude-specific complaints is `multi-tenant-schemas`; the strongest post-`:float` evidence sits in `cast-and-allowed-fields`, `unique-constraints-and-indexes`, and `polymorphic-associations`.

---

## Capability research

### Foundation: schema-organization

**Description** (from README.md): Flat schemas vs nested embeds vs cross-context splits. Variants: single-source-of-truth, context-scoped, hybrid.

**Known Claude failure modes**:
- [HIGH] **Cross-context `belongs_to` instead of ID references** — Claude treats context boundaries as namespaces, not bounded contexts, and wires cross-context associations with `belongs_to`, tangling domains and making contexts impossible to test independently.
- [HIGH] **Single monolithic changeset** — Claude generates one `changeset/2` per schema instead of separate changesets per operation (registration, profile_update, admin_update), leaking sensitive-field whitelists across use cases.
- [MED] **Mixing `schema/2` with `embedded_schema/1`** — Claude uses database-backed schemas where embedded schemas would better serve ephemeral form validation, creating accidental DB tables.
- [MED] **Flat God-schema** — dumps every field onto a single `User` schema instead of splitting into domain entities or using embedded schemas for subordinate data.

**Citations**:
- "Query through the context, not across associations. Keeps contexts independent and testable." — [georgeguimaraes/claude-code-elixir ecto-thinking SKILL.md](https://github.com/georgeguimaraes/claude-code-elixir/blob/main/plugins/elixir/skills/ecto-thinking/SKILL.md)
- "Different operations = different changesets" (registration, profile, admin each need separate validators) — [georgeguimaraes/claude-code-elixir ecto-thinking SKILL.md](https://github.com/georgeguimaraes/claude-code-elixir/blob/main/plugins/elixir/skills/ecto-thinking/SKILL.md)
- "Context isn't just a namespace — it changes what words mean." — [georgeguimaraes/claude-code-elixir ecto-thinking SKILL.md](https://github.com/georgeguimaraes/claude-code-elixir/blob/main/plugins/elixir/skills/ecto-thinking/SKILL.md)
- "Standard `schema/2` for database tables; `embedded_schema/1` for form validation only." — [georgeguimaraes/claude-code-elixir ecto-thinking SKILL.md](https://github.com/georgeguimaraes/claude-code-elixir/blob/main/plugins/elixir/skills/ecto-thinking/SKILL.md)

**Suggested challenge angles**:
- Give Claude a schema with `Accounts.User` and `Billing.Invoice`; expect it to use `user_id :: integer` references instead of `belongs_to :user, Accounts.User` across the boundary.
- Request a `User` schema where registration, password change, and admin role assignment each need separate changesets; score penalizes any changeset that leaks admin fields into registration.
- Ask for a `Post` schema with computed "slug" and "pretty_title" derived fields; expect virtual fields, not DB columns or embedded schemas.
- Present a cross-cutting "Address" structure used by Customer and Vendor; correct answer uses `embedded_schema` reused across contexts, not duplicate DB tables.

**Tier guidance**:
- Easy: single flat schema with one changeset for one operation
- Medium: two changesets per schema (registration + profile update)
- Hard: cross-context reference using IDs instead of belongs_to
- Legendary: reshape a god-schema into a core schema + 2 embedded schemas + 3 operation-specific changesets without breaking the public API

---

### Capability: field-types-and-decimal ⭐ (the headline item)

**Description** (from README.md): Picking the right `field` types; `:decimal` for money, NEVER `:float`; `:utc_datetime` vs `:naive_datetime`.

**Known Claude failure modes**:
- [HIGH] **`:float` for monetary fields** — Claude's default when asked to model a price/cost/amount/fee field; silently introduces IEEE-754 rounding errors in production.
- [HIGH] **`:naive_datetime` via default `timestamps()`** — Claude leaves `timestamps()` with no options, inheriting the naive default even when the app is clearly global/multi-timezone.
- [MED] **`Decimal.equal?/2` vs `==`** — Claude compares decimals with `==`, which returns false for `Decimal.new(9) == Decimal.new(9.000)`, leading to incorrect changeset `changes` maps and phantom changes.
- [MED] **`:integer` for small monetary amounts** — occasionally Claude reaches for integer cents but doesn't handle sub-cent fees/gas-prices/cryptocurrency amounts, causing precision loss.
- [LOW] **Missing `precision:` / `scale:` on decimal migrations** — Claude writes `add :price, :decimal` without specifying precision and scale, accepting Postgres defaults that may not match the domain.

**Citations**:
- "Never use `:float` for money." — [oliver-kriska/claude-elixir-phoenix Iron Laws](https://github.com/oliver-kriska/claude-elixir-phoenix), 2025, Iron Laws (Non-Negotiable Rules) section
- "The `:decimal` type is used for arbitrary precision decimal numbers, while `:float` is used for floating point numbers." — [Ecto.Schema official docs](https://hexdocs.pm/ecto/Ecto.Schema.html)
- "`utc_datetime` - has a precision of seconds and casts values to Elixir's `DateTime` struct and expects the time zone to be set to UTC. … `naive_datetime` - has a precision of seconds and casts values to Elixir's `NaiveDateTime` struct which has no timezone information." — [Ecto.Schema official docs](https://hexdocs.pm/ecto/Ecto.Schema.html)
- "By default `inserted_at` and `updated_at` are `NaiveDateTime`s in Ecto 2.x. It would be nice to have them be `DateTime` in UTC instead by default." — Lau Taarnskov, [Ecto Issue #2683](https://github.com/elixir-ecto/ecto/issues/2683)
- "I personally agree these would be the better defaults. But we can't change them without breaking existing apps and given Ecto reached stable API it's unlikely to change and we just have to live with it." — Wojtek Mach (Ecto maintainer), [Ecto Issue #2683](https://github.com/elixir-ecto/ecto/issues/2683)
- "I'm pretty sure the reason for this is that decimals can't be compared with `==`, yet that's what we're doing to decide if a field changed or not." — [Ecto Issue #2473](https://github.com/elixir-ecto/ecto/issues/2473) — the canonical Decimal comparison bug
- "Internally Money uses Decimal to store the amount which allows arbitrary precision arithmetic." — [elixirmoney/money README](https://github.com/elixirmoney/money)

**Suggested challenge angles**:
- "Model a `Product` with a `price` field. Score pass: `field :price, :decimal`. Score fail: any other type."
- "Model an `Order.line_items` with a quantity-times-unit-price total in USD. Score pass: both quantity and unit_price are `:decimal` with explicit precision/scale in migration."
- "Add a `created_at` timestamp to a `LogEntry` schema in a system that serves users globally. Score pass: `:utc_datetime` or `:utc_datetime_usec` and `timestamps(type: :utc_datetime)`. Score fail: `:naive_datetime` or default `timestamps()`."
- "Given a changeset where a decimal field isn't changed, explain why the change shows up in `changes`. Score pass: references Decimal.equal? vs ==."
- "Build a FX rates table with 8 decimal places. Score pass: migration uses `:decimal, precision: 18, scale: 8`."

**Tier guidance**:
- Easy: single price field (`:decimal` vs `:float` check)
- Medium: multi-field schema (price + timestamps + boolean); catches naive vs utc
- Hard: migration + schema + changeset trio where the correct type is `:decimal` with explicit precision and scale and `:utc_datetime` timestamps
- Legendary: adversarial prompt "use a simple type for quantity" — correct answer still `:decimal` despite user pressure to use float

---

### Capability: associations

**Description** (from README.md): `has_many`, `belongs_to`, `many_to_many`, `has_one`, `through:` associations

**Known Claude failure modes**:
- [HIGH] **Foreign key on the wrong side** — Claude puts `belongs_to :user` on the parent or `has_many :posts` on the child; violates Ecto's invariant that the FK lives on the `belongs_to` side.
- [MED] **Missing `references/1` in migration** — Claude writes `add :user_id, :integer` instead of `add :user_id, references(:users, on_delete: :delete_all)`; loses FK constraint.
- [MED] **`:nothing` default for `on_delete`** — Claude does not set `on_delete:`, accepting the default which causes orphaned rows when parents are deleted.
- [MED] **Missing `through:` association** — Claude duplicates logic instead of defining a `has_many :comments, through: [:posts, :comments]` shortcut.
- [LOW] **`has_one` where `has_many` is correct** (and vice versa) due to unclear cardinality in prompt.

**Citations**:
- "The `belongs_to` reveals on which table the foreign key should be added." — [Ecto Association Guide](https://hexdocs.pm/ecto/2.2.11/associations.html) / [Ecto.Schema docs](https://hexdocs.pm/ecto/Ecto.Schema.html)
- "Indicates a one-to-one or many-to-one association with another schema. You should use `belongs_to` in the table that contains the foreign key." — [Ecto.Schema official docs](https://hexdocs.pm/ecto/Ecto.Schema.html)
- "The default value for the `on_delete` option on `references` is `:nothing`. However, it's important to note that this default behavior may lead to orphaned or inconsistent data." — [doriankarter.com / Retrovertigo — Avoiding Data Loss with on_delete](https://doriankarter.com/avoiding-data-loss-understanding-the-ondelete-option-in-elixir-migrations/)
- "One common pitfall when working with the `on_delete` option is thinking of the relationship in the wrong direction." — [doriankarter.com — Retrovertigo](https://doriankarter.com/avoiding-data-loss-understanding-the-ondelete-option-in-elixir-migrations/)
- "This makes `:nothing` confusing and requires deeper familiarity with both your database, and some implementation details of the Ecto adapter." — [doriankarter.com — Retrovertigo](https://doriankarter.com/avoiding-data-loss-understanding-the-ondelete-option-in-elixir-migrations/)

**Suggested challenge angles**:
- "A `User` has many `Posts`. Write both schemas and the migration." Score pass: `belongs_to :user, MyApp.User` on Post, `has_many :posts, MyApp.Post` on User, `add :user_id, references(:users, on_delete: :delete_all)` in migration.
- "A `Post` has many `Comments` through `Reactions`. Write the schemas." Score pass: uses `through:` macro.
- "When a parent is deleted, child rows should cascade. Fix the migration." Score pass: adds explicit `on_delete: :delete_all`.
- "Given this Post schema with `belongs_to :user`, write the User schema." Score pass: the has_many direction is correct.

**Tier guidance**:
- Easy: one has_many + one belongs_to pair
- Medium: cascading on_delete added correctly
- Hard: 3-level association chain with `through:`
- Legendary: circular association with two has_many on the same pair (requires explicit `foreign_key:` disambiguation)

---

### Capability: embedded-schemas

**Description** (from README.md): `embeds_one`, `embeds_many`, when to embed vs associate.

**Known Claude failure modes**:
- [HIGH] **Embeds where a relation is needed** — Claude embeds data that should be queryable or referenced independently, then discovers later that many-to-many is impossible.
- [HIGH] **Association where embed is simpler** — Claude creates a separate table + join for data that logically lives inside its parent (addresses, audit-log entries, UI settings).
- [MED] **Missing changeset for embedded schema** — Claude forgets that an `embedded_schema` still needs its own changeset function for validation.
- [MED] **`cast_embed/3` without preloading** — Claude calls `cast_embed` on a struct where the embed isn't set, producing runtime error.

**Citations**:
- "Embedded schemas are often used as an alternative to associations on another table, with a foreign key and join, which has a number of benefits, including reduced database queries for commonly retrieved associated records." — [Ecto Embedded Schemas guide](https://hexdocs.pm/ecto/embedded-schemas.html)
- "When you use unstructured data, you lose some of the powerful relational features that a SQL database provides. For example, since a record can only be embedded in a single parent, you can't model a many-to-many relationship with embedded records." — [Ecto Embedded Schemas guide](https://hexdocs.pm/ecto/embedded-schemas.html)
- "You also can't use database constraints on structure and uniqueness when storing in a JSON field." — [Ecto Embedded Schemas guide](https://hexdocs.pm/ecto/embedded-schemas.html)
- "cast_assoc (or cast_embed) is used when you want to manage associations or embeds based on external parameters, such as the data received through Phoenix forms." — [Dashbit — Working with Ecto associations and embeds](https://dashbit.co/blog/working-with-ecto-associations-and-embeds)
- "If you invoke post.comments and comments have not been preloaded, it will return Ecto.Association.NotLoaded." — [Dashbit — Working with Ecto associations and embeds](https://dashbit.co/blog/working-with-ecto-associations-and-embeds)

**Suggested challenge angles**:
- "Model a `Customer` with a primary `Address`. Is this embed or association?" Correct: `embeds_one :primary_address, Address` because it's single-parent, never queried independently.
- "Model an `Order` with line items that also appear in Product reports." Correct: `has_many :line_items` because line_items need independent querying.
- "Given an embedded `Address` schema, write the parent changeset." Score pass: uses `cast_embed(:primary_address, with: &Address.changeset/2)`.
- "A `UserProfile` currently embeds `Preferences`. The user now needs to share preferences with team members. Refactor." Correct: migrate from embed to association.

**Tier guidance**:
- Easy: single `embeds_one` with no nested changeset
- Medium: embeds_many + nested changeset function + cast_embed
- Hard: refactor from embed to association when queryability is required
- Legendary: hybrid schema where some fields embed (ephemeral form-only UI state) and others associate (persisted audit log)

---

### Capability: validations-basic

**Description** (from README.md): `validate_required`, `validate_length`, `validate_format`, `validate_inclusion`, `validate_number`

**Known Claude failure modes**:
- [HIGH] **Wrong `validate_required` list** — Claude copies the `cast/3` allowlist verbatim into `validate_required`, marking truly optional fields as required.
- [HIGH] **Ambiguous email regex in `validate_format`** — Claude writes `~r/@/` and calls it done, missing domain/TLD validation or calls it too strict and rejects valid edge cases.
- [MED] **`validate_length` on field not in changes** — Claude adds `validate_length` but the field isn't present in changes; validation silently no-ops.
- [MED] **Missing `validate_number: greater_than: 0` for monetary / quantity fields** — Claude skips positivity validation for decimals.
- [LOW] **`validate_inclusion` with Elixir list instead of `Ecto.Enum`** — Claude stringly-types status fields instead of using `Ecto.Enum`.

**Citations**:
- "validate_required adds an error to the changeset if it doesn't include changes for each of the fields." — [Ecto.Changeset official docs](https://hexdocs.pm/ecto/Ecto.Changeset.html)
- "Changeset only validates changes. If the value is the same as default, it won't change, hence no validation." — [Ecto Issue #4005 — validate_length with default value does not work](https://github.com/elixir-ecto/ecto/issues/4005)
- "validate_format/4 is not very useful … In the more common case, it is desirable to check if a field does not match a regular expression." — [Ecto Issue #3177](https://github.com/elixir-ecto/ecto/issues/3177)
- Example idiomatic email validation: `validate_format(:email, ~r/^[^\s]+@[^\s]+$/, message: "must have the @ sign and no spaces")` — [alchemist.camp — Ecto changesets, validations and constraints](https://alchemist.camp/episodes/ecto-beginner-changesets-validations)

**Suggested challenge angles**:
- "A User changeset should require :email and :name, but :phone is optional. Write it." Score pass: `validate_required([:email, :name])` only.
- "A Product price must be greater than zero." Score pass: `validate_number(:price, greater_than: 0)`.
- "An email validation. Use validate_format. Bonus: also add domain/TLD check." Score flexibility but requires `validate_format`.
- "A User.status field must be one of `:active`, `:suspended`, `:deleted`." Score pass: prefer `field :status, Ecto.Enum, values: [...]` over `validate_inclusion`.

**Tier guidance**:
- Easy: single validate_required + validate_length
- Medium: multiple validations + validate_format email
- Hard: `Ecto.Enum` for status field (instead of stringly-typed validate_inclusion)
- Legendary: validate_required that correctly excludes optional fields from a 10-field schema

---

### Capability: validations-custom

**Description** (from README.md): `validate_change/3`, `validate_confirmation/2`, cross-field validations.

**Known Claude failure modes**:
- [HIGH] **Custom validator doesn't respect `:valid?`** — Claude's `validate_change` callbacks don't check `changeset.valid?` and crash when preceding `validate_required` already failed.
- [MED] **Cross-field validation via put_change** — Claude uses `put_change/3` for derived fields without validating cross-field consistency.
- [MED] **`validate_confirmation` on password without virtual field** — Claude adds `validate_confirmation(:password)` without declaring `password_confirmation` as a virtual field in the schema.

**Citations**:
- "A caveat is that preceding validations in the pipeline are not automatically recognized by a custom validation. … If a field was empty in the `validate_required/3` function, an error would be added to the changeset, and when that empty field gets to the custom validation function, it needs to be handled in some way, or it could throw unexpected errors." — [dev.to — How To Write A Custom Elixir Schema Validation](https://dev.to/noelworden/how-to-write-a-custom-elixir-schema-validation-167e)
- "validate_change/3 and validate_change/4 both take a changeset, a field, and a validator function … validate_change will then check for the presence of the field in the changeset and if it exists and the change value is not nil then it will run the validator." — [Ecto.Changeset official docs](https://hexdocs.pm/ecto/Ecto.Changeset.html)
- "Most validations can be executed without a need to interact with the database and are always executed before attempting to insert or update the entry, and validations are always checked before constraints." — [Ecto.Changeset official docs](https://hexdocs.pm/ecto/Ecto.Changeset.html)

**Suggested challenge angles**:
- "Add a custom validator that ensures `end_date` > `start_date`." Score pass: uses `validate_change(:end_date, ...)`, returns `[end_date: "must be after start date"]` on failure.
- "Password confirmation: validate that password == password_confirmation." Score pass: uses `validate_confirmation(:password)` and virtual `field :password_confirmation, :string, virtual: true`.
- "Custom validator that ensures two optional fields are either both set or both nil." Score pass: checks both fields in `validate_change` closure.
- "Debug this: the custom validator raises KeyError on empty input." Expected fix: guard on `changeset.valid?` or on nil.

**Tier guidance**:
- Easy: single validate_confirmation
- Medium: validate_change for single field range
- Hard: cross-field validator with nil-handling + virtual field setup
- Legendary: validator that uses the external DB only when safe (validates preceding validations first)

---

### Capability: unique-constraints-and-indexes

**Description** (from README.md): DB-level unique index + changeset `unique_constraint/2` (must match!).

**Known Claude failure modes**:
- [HIGH] **`unique_constraint` without matching `unique_index`** — Claude adds `unique_constraint(:email)` to the changeset without a corresponding `create unique_index(:users, [:email])` in the migration. The changeset passes validation, the DB rejects at commit time.
- [HIGH] **`unique_constraint` only (no `unsafe_validate_unique`)** — Claude doesn't pair with `unsafe_validate_unique/4` for pre-insert error messaging; user gets a confusing 500 error on submit.
- [MED] **Composite unique name mismatch** — Claude writes `unique_index(:users, [:email, :tenant_id])` but the `unique_constraint` in the changeset references only `:email`; the DB error's constraint name doesn't match the inferred changeset name.
- [MED] **Name truncation silent failure** — On Postgres, index names >63 chars are truncated, breaking the name-inference match.

**Citations**:
- "unique_constraint/3 only achieves anything if your database actually has a uniqueness constraint on the given column." — [Arrowsmith Labs — Foolproof uniqueness validations in Phoenix with Ecto](https://arrowsmithlabs.com/blog/foolproof-uniqueness-validations-in-phoenix-with-ecto)
- "If the changeset is marked as invalid, then Repo.insert and Repo.update won't attempt to make the insert/update, so unique_constraint/3 does nothing." — [Arrowsmith Labs — Foolproof uniqueness validations in Phoenix with Ecto](https://arrowsmithlabs.com/blog/foolproof-uniqueness-validations-in-phoenix-with-ecto)
- "Even though you write unique_constraint in the changeset/3, it doesn't check for that constraint unless there is a unique_index applied to the database." — [alvinrapada.medium.com — Creating Unique Constraint/Index Ecto.Migration](https://alvinrapada.medium.com/creating-unique-constraint-index-ecto-migration-elixir-37146722e593)
- "unique index name inference inconsistency … Ecto.Changeset.unique_constraint and Ecto.Migration.unique_index should be consistent in how they infer the name of an index." — [Ecto Issue #2311](https://github.com/elixir-ecto/ecto/issues/2311)
- "When an index name is bigger than 63 characters, PostgreSQL truncates the name to within these 63 characters, but since the name was truncated, it doesn't match correctly and fails." — [Ecto Issue #3259](https://github.com/elixir-ecto/ecto/issues/3259)

**Suggested challenge angles**:
- "Ensure User.email is unique. Write migration, schema, and changeset." Score pass: `create unique_index(:users, [:email])` AND `unique_constraint(:email)` AND preferably `unsafe_validate_unique(:email, Repo)`.
- "Ensure (tenant_id, email) is jointly unique per tenant." Score pass: composite `unique_index` + `unique_constraint(:email, name: :users_tenant_id_email_index)`.
- "Fix this bug: the changeset has unique_constraint but duplicates are being created in the DB." Expected fix: add `unique_index` to migration.
- "Fix this bug: DB raises exception but changeset doesn't catch it as a validation error." Expected fix: align constraint names with `name:` option.

**Tier guidance**:
- Easy: single-column unique
- Medium: composite unique with correct name
- Hard: unique + `unsafe_validate_unique` + race-condition-aware handling
- Legendary: partial unique index (`where: "deleted_at IS NULL"`) for soft-delete compatibility

---

### Capability: cast-and-allowed-fields

**Description** (from README.md): `cast/3`, `cast_assoc/3`, `cast_embed/3`; mass assignment safety.

**Known Claude failure modes**:
- [HIGH] **`:is_admin` (or similar privileged field) in `cast/3` allowlist** — The canonical mass-assignment vulnerability documented in the Phoenix security guide. Claude replicates this when asked to build a user registration or admin changeset.
- [HIGH] **`cast_assoc/3` without preloading** — Claude calls `cast_assoc` on a struct where the association isn't loaded, producing `Please preload your associations before manipulating them through changesets`.
- [MED] **`put_change/3` bypass** — Claude uses `put_change(:is_admin, true)` to work around the cast allowlist, defeating the safety.
- [MED] **Same changeset for registration and admin update** — Claude reuses `changeset/2` for admin-only operations that mutate `:role`, leaking mass-assignment risk.
- [MED] **Missing `with:` option in `cast_embed`/`cast_assoc`** — Claude uses the default changeset for a nested schema when the nested schema needs a specific variant.

**Citations**:
- "The design of Ecto in Phoenix takes the risk of mass assignment into consideration, because you have to explicitly define what parameters are allowed to be set from user supplied data." — [Phoenix official security guide](https://hexdocs.pm/phoenix/security.html)
- "The problem is that `:is_admin` should never be set via external user input. Anyone on the public internet can now create a user where `:is_admin` is set to true in the database, which is likely not the intent of the developer." — [Phoenix official security guide](https://hexdocs.pm/phoenix/security.html)
- "All parameters that are not explicitly permitted are ignored." — [Ecto.Changeset docs — cast/3](https://hexdocs.pm/ecto/Ecto.Changeset.html)
- "As a developer, you should keep in mind what fields you cast in the changeset. There is nothing wrong to create multiple changesets for your fields in your schema — one for user data and another for admin permissions only." — [Paraxial.io Elixir security checklist](https://paraxial.io/blog/elixir-best)
- "Attempting to cast or change an association that was not loaded will result in a runtime error stating 'Please preload your associations before manipulating them through changesets'." — [Ecto.Changeset docs / Dashbit blog](https://dashbit.co/blog/working-with-ecto-associations-and-embeds)

**Suggested challenge angles**:
- "Write a `registration_changeset/2` for a User schema that has `:is_admin`. Ensure external input can never set is_admin." Score fail: `:is_admin` in the cast list.
- "Write a separate `admin_changeset/2` that DOES allow `:role` updates, alongside the user-facing `update_changeset/2` that doesn't." Score pass: two distinct functions with distinct cast lists.
- "Cast a nested address into a user changeset." Score pass: uses `cast_embed(:address)` or `cast_assoc(:address)` with the address association preloaded.
- "Fix this: `cast_assoc(:posts)` raises at runtime." Expected fix: preload posts before building the changeset.
- "Adversarial: user requests 'allow all fields to be set from params'. Resist; explain why."

**Tier guidance**:
- Easy: explicit cast list of 3 fields, no is_admin
- Medium: registration_changeset + update_changeset split
- Hard: cast_assoc with preloading + custom nested changeset
- Legendary: adversarial is_admin included — Claude should refuse and split changesets

---

### Capability: migrations

**Description** (from README.md): `create_table`, `alter_table`, `add`, `remove`, indexes, foreign keys.

**Known Claude failure modes**:
- [HIGH] **`add :user_id, :integer` instead of `references(:users)`** — Claude uses raw column types for FKs, losing DB-level referential integrity.
- [HIGH] **Missing `on_delete:`** — Claude accepts `:nothing` default, causing orphaned rows on parent delete.
- [MED] **`:naive_datetime` timestamps** — Claude writes `timestamps()` without `type: :utc_datetime`, inheriting the problematic default.
- [MED] **Unique index inline in `create table`** — Claude puts `unique: true` inside a column definition instead of a separate `create unique_index/3`.
- [MED] **`alter table` followed by `update_all` in same migration** — Claude tries to backfill a column in the same migration that adds it, running into transactional visibility issues.
- [LOW] **Missing `:using` for index type** — Claude doesn't specify `:using, :gin` for full-text search or JSONB indexes.

**Citations**:
- "The default value for the `on_delete` option on `references` is `:nothing`. However, it's important to note that this default behavior may lead to orphaned or inconsistent data." — [doriankarter.com — Retrovertigo](https://doriankarter.com/avoiding-data-loss-understanding-the-ondelete-option-in-elixir-migrations/)
- "Using `on_delete` in schema associations is discouraged for most relational databases. Instead, set the `on_delete` option in your migration using `references(:parent_id, on_delete: :delete_all)`." — [Ecto.Migration official docs](https://hexdocs.pm/ecto_sql/Ecto.Migration.html)
- "When you add a column and then immediately try to use it in an `update_all` statement within the same migration, you may encounter an error that the column doesn't exist, even though you just added it." — [Hashrocket — Ecto Migrations: Simple to Complex](https://hashrocket.com/blog/posts/ecto-migrations-simple-to-complex)
- "references does not work with alter table [properly for modify]" — [Ecto Issue #722](https://github.com/elixir-ecto/ecto/issues/722)

**Suggested challenge angles**:
- "Write a migration for a Comments table that belongs to Posts with cascade delete." Score pass: `add :post_id, references(:posts, on_delete: :delete_all)`.
- "Write a migration for a Users table with a unique email index and UTC timestamps." Score pass: `timestamps(type: :utc_datetime)` + separate `create unique_index`.
- "Add a non-null column with a default to an existing table, then backfill." Score pass: separate migration for backfill OR `execute/1` + `flush/0`.
- "Change an existing FK's on_delete behavior." Score pass: drop constraint + modify + re-add.

**Tier guidance**:
- Easy: single create_table with references
- Medium: create_table + separate unique_index + UTC timestamps
- Hard: alter_table with FK modification
- Legendary: zero-downtime add-nullable-then-backfill-then-enforce

---

### Capability: polymorphic-associations

**Description** (from README.md): The tradeoffs; Ecto doesn't natively support them; common workarounds.

**Known Claude failure modes**:
- [HIGH] **Rails-style `imageable_type + imageable_id`** — Claude ports the ActiveRecord pattern directly, losing DB referential integrity and introducing silent orphaning. The Ecto docs explicitly warn against this.
- [HIGH] **Missing `many_to_many` workaround recommendation** — When asked for polymorphism, Claude doesn't suggest the official Ecto recommended pattern of separate join tables per association type.
- [MED] **`Ecto.ParameterizedType` without understanding** — Claude sees mentions of polymorphic types and invents nonsense parameterized types rather than using the existing `polymorphic_embed` library.

**Citations**:
- "The issue with the design above is that it breaks database references. The database is no longer capable of guaranteeing the item you associate to exists or will continue to exist in the future." — [Ecto Polymorphic Associations guide](https://hexdocs.pm/ecto/polymorphic-associations-with-many-to-many.html)
- "This leads to an inconsistent database which end-up pushing workarounds to your application … especially if you're working with large tables … frequent polymorphic queries start grinding the database to a halt even after adding indexes and optimizing the database." — [Ecto Polymorphic Associations guide](https://hexdocs.pm/ecto/polymorphic-associations-with-many-to-many.html)
- "Those questions often pop up because people expect ecto to solve the involved complexity for them, which it just doesn't do." — [Elixir Forum — How to handle schemas polymorphism in Phoenix](https://elixirforum.com/t/how-to-handle-schemas-polymorphism-in-phoenix/13269)
- "Ecto does not provide the same type of polymorphic associations available in frameworks such as Rails and Laravel." — [Ecto Polymorphic Associations guide](https://hexdocs.pm/ecto/polymorphic-associations-with-many-to-many.html)
- "The `polymorphic_embed` library brings support for polymorphic/dynamic embedded schemas in Ecto, addressing the fact that Ecto's `embeds_one` and `embeds_many` macros require a specific schema module to be specified." — [polymorphic_embed README](https://github.com/mathieuprog/polymorphic_embed)

**Suggested challenge angles**:
- "An Image can belong to a User, a Post, or a Comment. Model this in Ecto." Score pass: separate join tables (users_images, posts_images, comments_images) using `many_to_many`. Score fail: single `imageable_type, imageable_id` columns.
- "Claude-adversarial: 'I ported this from Rails, preserve the polymorphic pattern.' " Score pass: explains why it's an anti-pattern in Ecto + proposes the join-table alternative.
- "A single `Event` should reference different types of subjects (User, Product, Order). Model it." Score pass: explicit per-subject association OR `polymorphic_embed` library if flexibility needed.
- "Translate this Rails Image `belongs_to :imageable, polymorphic: true` to idiomatic Ecto."

**Tier guidance**:
- Easy: (skip — this capability isn't trivially easy)
- Medium: given three parent types, produce three join tables
- Hard: decide when to use `polymorphic_embed` vs many_to_many vs abstract tables
- Legendary: adversarial user prompt insisting on Rails pattern — Claude should refuse and justify

---

### Capability: soft-deletes-and-timestamps

**Description** (from README.md): `deleted_at` patterns, `timestamps()` macro, `updated_at` triggers.

**Known Claude failure modes**:
- [HIGH] **Application-level soft delete without query scoping** — Claude adds a `deleted_at` column but forgets to filter it out of every query, leaking soft-deleted rows into user-facing lists.
- [MED] **Unique constraints incompatible with soft delete** — Claude adds `unique_index(:users, [:email])` but doesn't make it partial (`where: "deleted_at IS NULL"`), so reusing a deleted user's email fails.
- [MED] **`timestamps()` with default `:naive_datetime`** — same as the field-types failure, surfacing here too.
- [LOW] **Cascade from soft-deleted parent to hard-deleted children** — Claude doesn't realize soft-delete breaks FK cascades.

**Citations**:
- "Instead of effectively deleting it from the database, you will mark the order as deleted, and then you simply do not show such orders to the user." — [Dashbit — Soft deletes with Ecto and PostgreSQL](https://dashbit.co/blog/soft-deletes-with-ecto)
- "If you are adding constraints, such as unique indexes or check constraints, you may not want them to apply to deleted at." — [Dashbit — Soft deletes with Ecto and PostgreSQL](https://dashbit.co/blog/soft-deletes-with-ecto)
- "[handling soft deletes at the application level is] error prone, especially once you consider foreign keys cascade and deletion rules." — [Dashbit — Soft deletes with Ecto and PostgreSQL](https://dashbit.co/blog/soft-deletes-with-ecto)
- "Ecto.SoftDelete.Repo in your repo and updates the deleted_at field with the current datetime in UTC. Ecto.SoftDelete.Repo will also intercept all queries made with the repo and automatically add a clause to filter out soft-deleted rows." — [ecto_soft_delete package docs](https://hexdocs.pm/ecto_soft_delete/Ecto.SoftDelete.Repo.html)

**Suggested challenge angles**:
- "Add soft-delete support to a User schema. Ensure queries in the default scope exclude soft-deleted rows." Score pass: deleted_at column + query function `where([u], is_nil(u.deleted_at))`.
- "The team is reusing deleted users' emails, but the unique constraint rejects it. Fix." Score pass: migrate to partial unique index `where: "deleted_at IS NULL"`.
- "Soft-delete a User that has Posts. What happens to the Posts?" Score pass: explains cascade semantics + offers strategy.
- "Convert a hard-delete Posts table to soft-delete without data loss."

**Tier guidance**:
- Easy: add deleted_at field + utc timestamps
- Medium: partial unique index
- Hard: full migration of an existing hard-delete table to soft-delete
- Legendary: soft-delete with cascading to children that should also be soft-deleted

---

### Capability: multi-tenant-schemas (THIN EVIDENCE)

**Description** (from README.md): `prefix:` option, schema-per-tenant patterns.

**Known Claude failure modes**:
- [MED] **CTEs don't inherit query prefix** — Noted explicitly in the georgeguimaraes plugin as a gotcha.
- [MED] **Forgetting `@schema_prefix` on specifc shared tables** — Claude applies prefix globally, missing the shared-data case.
- [LOW] **Query prefix vs repo prefix confusion** — Claude passes `prefix:` at the wrong level.

**Citations**:
- "CTEs don't inherit parent query's schema prefix; explicitly set it." — [georgeguimaraes/claude-code-elixir ecto-thinking SKILL.md](https://github.com/georgeguimaraes/claude-code-elixir/blob/main/plugins/elixir/skills/ecto-thinking/SKILL.md)
- "Ecto allows you to set a particular schema to run on a specific prefix by using the @schema_prefix module attribute, for example in a multi-tenant application where shared data can be stored in a 'main' prefix." — [Ecto Multi-tenancy guide](https://hexdocs.pm/ecto/multi-tenancy-with-query-prefixes.html)
- "On any given query you can change this by passing in a prefix: option, i.e: Repo.one(query, prefix: 'some_prefix')." — [Ecto Multi-tenancy guide](https://hexdocs.pm/ecto/multi-tenancy-with-query-prefixes.html)

**Suggested challenge angles**:
- "Add tenant isolation via `@schema_prefix` to a Product schema." Score pass: module-level `@schema_prefix` attribute.
- "A query should run against a specific tenant's schema." Score pass: `Repo.one(query, prefix: "tenant_123")`.
- "Some shared reference data should NOT be tenant-scoped. Model it." Score pass: schema with `@schema_prefix "main"`.

**Tier guidance**:
- Easy: module-level `@schema_prefix`
- Medium: per-query prefix override
- Hard: mixed shared + tenant tables in the same app
- (Skip legendary — evidence too thin)

---

## Research process notes

I started by reading the three required files: `SEEDING-PLAN.md`, the family's `README.md`, and `docs/research/elixir-llm-pain-points.md`. The existing pain-points doc established that the `:float`-for-money iron law is the canonical clinching item for this family; my web research reinforced and extended that finding. Primary source weighting: the oliver-kriska Iron Laws catalog is a strong signal because each "law" represents an observed Claude failure the plugin author cared enough to guard against; Dashbit and the official Ecto docs anchor the technical correctness of each pattern; Elixir Forum posts provide developer-voice context; and GitHub issues surface the edge cases. The `Ecto.Changeset` / `Ecto.Schema` docs themselves were surprisingly explicit about the is_admin/mass-assignment trap (because the Phoenix security guide calls it out verbatim), which makes the cast-and-allowed-fields capability extremely score-able. I also spot-checked the BoothIQ post-mortem for direct Ecto complaints; its strongest Ecto references are about sandbox/concurrency (covered by `elixir-ecto-sandbox-test`, a different family) rather than schema/changeset authoring, so I did not over-weight it.

Evidence quality varies across capabilities. The strongest evidence base is field-types-and-decimal (iron law + Ecto maintainer quotes + the Decimal.equal? comparison bug), unique-constraints-and-indexes (Arrowsmith's verbatim warning + multiple GitHub issues), cast-and-allowed-fields (the is_admin vulnerability is explicitly documented in the Phoenix security guide), and polymorphic-associations (the Ecto official docs call out Rails-style patterns as database-integrity hazards). The thinnest are multi-tenant-schemas (one plugin SKILL.md line + documentation summary only — no developer complaint threads found) and validations-custom (mostly generic "here's a caveat" blog posts rather than LLM-specific complaints). Everything else sits in the middle.

## Capability prioritization (Phase 2 output)

| Capability | Evidence strength | Recommended primary count | Rationale |
|---|---|---|---|
| schema-organization (foundation) | MED | 10-12 foundation slots | Cross-context discipline + changeset-per-operation rule are strongly documented in georgeguimaraes plugin |
| field-types-and-decimal | HIGH | 8 (max) | The clinching item for this family; iron law + Ecto maintainer quotes + Decimal.equal? bug; deserves upper bound |
| associations | MED-HIGH | 7 | Strong official docs + on_delete `:nothing` default is a documented data-loss hazard |
| embedded-schemas | MED | 6 | Clear Ecto guide warnings about embeds losing referential integrity; ~half of complaints are about when-to-use vs how-to-write |
| validations-basic | MED | 6 | Widely-used functions with documented gotchas (changes-vs-data, format regex nuance) |
| validations-custom | MED-LOW | 5 | Preceding-validation caveat is clear but the skill surface is small |
| unique-constraints-and-indexes | HIGH | 7 | Arrowsmith's explicit warning + multiple GitHub issues + name-inference pitfalls; high-severity silent failure mode |
| cast-and-allowed-fields | HIGH | 8 (max) | The is_admin vulnerability is verbatim documented in the Phoenix official security guide; this is as score-able as field-types |
| migrations | MED-HIGH | 7 | references/on_delete defaults + timestamps defaults + alter_table transaction gotchas all documented |
| polymorphic-associations | HIGH | 7 | Explicit Ecto docs warning against Rails-style patterns; the "correct answer is 'don't'" makes this a legendary-tier teaching moment |
| soft-deletes-and-timestamps | MED | 6 | Dashbit coverage + ecto_soft_delete package conventions; real but bounded surface |
| multi-tenant-schemas | LOW | 5 (min) | Only one plugin line and Ecto docs; thin Claude-specific complaint base; ship at lower bound |

**Total primary-tagged challenges target**: approximately 12 + 8 + 7 + 6 + 6 + 5 + 7 + 8 + 7 + 7 + 6 + 5 = **84**, close to the ~100 family target. With ~16 challenges left for secondary-tagged overflow and held-out slack, this fits the binary family budget cleanly.

## Capabilities with insufficient public failure documentation

- **multi-tenant-schemas** — thinnest evidence base. Only the georgeguimaraes plugin line ("CTEs don't inherit parent query's schema prefix; explicitly set it.") and generic Ecto documentation about `@schema_prefix`. No Claude-specific complaint threads surfaced. Consider generating challenges from the Ecto multi-tenancy guide directly rather than from real failure reports; ship at the lower bound of the 5-8 range.
- **validations-custom** — reasonably documented technically but has less Claude-specific evidence than `validations-basic`. The "preceding validations aren't automatically recognized" caveat is the main documented pitfall; everything else is generic custom-validation content.
