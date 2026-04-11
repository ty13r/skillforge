# elixir-security-linter

**Rank**: #3 of 22
**Tier**: S (must-have, strongest evidence)
**Taxonomy path**: `security` / `security-linting` / `elixir`
**Status**: ⭐ NEW from research — entire enforcement tier in `oliver-kriska/claude-elixir-phoenix` plugin exists for this

## Specialization

Catches and prevents Elixir-specific security vulnerabilities that Claude regularly introduces: atom exhaustion via `String.to_atom/1` on user input, SQL injection via Ecto fragment interpolation, XSS via `raw/1`, open redirects, timing attacks on token comparison, missing LiveView `handle_event` authorization, mass assignment in changesets, weak password hashing, and insecure session/cookie configuration.

## Why LLMs struggle

Phoenix's permissive defaults + Elixir's compile-time atom table create unique attack surfaces that don't exist in JS/Python/Ruby. Claude doesn't recognize these as security issues because the patterns look syntactically clean. Plugin authors built an entire enforcement tier (v2.3.0 of the oliver-kriska plugin) explicitly to prevent observed Claude failures.

Specific failure modes from the research:
- **Atom exhaustion**: `String.to_atom(user_input)` → grows the atom table forever, eventually OOMs the BEAM
- **SQL injection**: `from u in User, where: fragment("name LIKE '%#{name}%'")` → string interpolation in `fragment/1` is unsafe
- **XSS**: `raw(@user_supplied_html)` in HEEx templates without sanitization
- **Open redirect**: `redirect(to: params["return_to"])` without validating the URL
- **Timing attack**: `==` for comparing tokens, secrets, password hashes
- **Missing authorization**: `handle_event("delete", %{"id" => id}, socket)` that calls `Repo.delete!(post)` without checking ownership

## Decomposition

### Foundation
- **F: `security-scan-philosophy`** — How the skill enforces: fail-closed (reject on detection), warn-with-severity, or tiered enforcement (block critical, warn moderate). Frames every capability's response style.

### Capabilities
1. **C: `atom-exhaustion`** — `String.to_atom/1` on user input, `String.to_existing_atom/1` as the safer alternative
2. **C: `ecto-fragment-injection`** — String interpolation in `fragment/1` → SQL injection; the safe pattern with `^` pin operator
3. **C: `raw-xss-prevention`** — `raw/1` in HEEx templates with untrusted content; when escaping is automatic vs manual
4. **C: `open-redirect-protection`** — Redirecting to user-controlled URLs; allowlist patterns
5. **C: `timing-attack-comparisons`** — `==` on tokens/secrets vs `Plug.Crypto.secure_compare/2`
6. **C: `liveview-handle-event-authz`** — Enforcing authorization on every `handle_event/3`; ownership and permission checks
7. **C: `csrf-and-secure-headers`** — `put_secure_browser_headers`, CSRF tokens, SameSite cookies, HSTS
8. **C: `mass-assignment-in-changesets`** — `cast/3` allowlists vs wide-open casting; protecting role/admin fields
9. **C: `password-hashing-choice`** — bcrypt vs argon2 vs pbkdf2_sha256; cost parameters; never plaintext or MD5/SHA1
10. **C: `session-and-cookie-security`** — Signing vs encryption, SameSite, Secure flag, session expiration
11. **C: `plug-security-middleware-chain`** — Content-Security-Policy, X-Frame-Options, HSTS, X-Content-Type-Options
12. **C: `secrets-in-config`** — `System.fetch_env!/1` vs `System.get_env/1` vs hardcoded; runtime.exs vs compile-time

### Total dimensions
**13** = 1 foundation + 12 capabilities

## Evaluation criteria sketch

Each challenge presents a piece of vulnerable Elixir code; the skill must identify the vulnerability and propose the fix. The score.py runs a SAST-style check (regex + AST patterns) to verify the fix removed the vulnerability without introducing new ones.

- **Atom exhaustion test**: code that calls `String.to_atom(params["type"])` — fix should use `String.to_existing_atom/1` or a whitelist
- **SQL injection test**: `fragment("WHERE name = '#{name}'")` — fix should use `where: u.name == ^name`
- **XSS test**: `<%= raw @comment.body %>` without sanitization — fix should escape or use a sanitizer
- **Authorization test**: `handle_event("delete", %{"id" => id}, socket)` that deletes without ownership check — fix should add the check
- **Timing attack test**: `if user.api_token == params["token"]` — fix should use `Plug.Crypto.secure_compare`

## Evidence

- [oliver-kriska/claude-elixir-phoenix v2.3.0](https://github.com/oliver-kriska/claude-elixir-phoenix) — entire enforcement tier
- [Elixir Forum: Claude opinionated integration thread](https://elixirforum.com/t/claude-opinionated-claude-code-integration-for-elixir/71831)
- [Research report Part 1 #8](../../docs/research/elixir-llm-pain-points.md#8-security-gaps-atom-exhaustion-sql-injection-xss-missing-authorization)

## Notes

- **Should displace `elixir-typespec-annotator`** in the active 10-family roster (per research recommendation).
- This family is the most LINT-LIKE of the Elixir families — it's about identifying and rejecting patterns rather than generating code from scratch. The skill format may need to adapt: less "write a thing" and more "review this code".
- Strong overlap with general SAST tooling (Sobelow already exists for Elixir security scanning) — the skill could be framed as "teach Claude to think like Sobelow" rather than reinventing.
- Some capabilities (CSRF, secure headers) overlap with framework defaults — the skill should distinguish "Phoenix protects you here by default" from "you must opt in".
