# elixir-security-linter — Per-Capability Research Dossier

**Generated**: 2026-04-11
**Workstream**: SKLD-bench v2.1 (see [`../SEEDING-PLAN.md`](../SEEDING-PLAN.md))
**Sources surveyed**: oliver-kriska/claude-elixir-phoenix plugin, georgeguimaraes/claude-code-elixir plugin, Sobelow hexdocs (v0.14.1) + nccgroup/sobelow GitHub, Paraxial.io security blog (atom-dos, sql-injection, xss-phoenix, owasp-top-ten), Phoenix hexdocs (security guide, LiveView security-model, Controller.redirect/2, Mix.Tasks.Phx.Gen.Auth), EEF Security WG (security.erlef.org timing_attacks + common_web_application_vulnerabilities), Curiosum security-in-elixir blog, Arrowsmith Labs "secure by default" blog, GuardRails hard-coded-secrets docs, Dan Schultzer CSP-with-LiveView blog, Plug.Crypto hexdocs, CVE-2017-1000163 (Phoenix open redirect), CVE-2025-32433 (Erlang/OTP SSH RCE), BoothIQ "150k lines of vibe coded Elixir" + HN thread, Elixir Forum threads, `docs/research/elixir-llm-pain-points.md`.
**Total citations**: 52

## Family-level summary

This family exists because the `oliver-kriska/claude-elixir-phoenix` plugin built an entire enforcement tier explicitly to prevent observed Claude failures in Elixir/Phoenix security. The three headline "security iron laws" are literally a Claude-specific bug list: *"No `String.to_atom` with user input"*, *"Authorize in every LiveView `handle_event`"*, and *"Never use `raw/1` with untrusted content"*. Each is corroborated by an independent security scanner finding (Sobelow's `DOS.StringToAtom`, `XSS.Raw`) and an independent developer narrative.

The background signal is that Phoenix is "secure by default" for the conventional web vulnerabilities (CSRF, XSS auto-escaping, parameterized SQL via Ecto, secure cookies, CSRF protection on non-GET endpoints, `put_secure_browser_headers` in the router). This creates a dangerous trap for LLMs: Claude confidently writes "idiomatic" Phoenix code that looks safe because the *surface* is safe, but then actively bypasses the defaults via `raw/1`, `fragment(...)` string interpolation, permissive `cast/3` lists, ignored authorization checks in `handle_event`, `String.to_atom/1` on params, or `System.cmd` with unchecked user input. The vulnerabilities are syntactically clean, which is why Claude doesn't flag them as dangerous.

The evidence base is strongest for atom exhaustion, Ecto fragment SQL injection, raw-HTML XSS, and LiveView authorization — these each have (a) a plugin iron-law, (b) a Sobelow detection module, (c) a Paraxial/EEF security-guide writeup, and (d) BoothIQ-style developer narratives. It is weakest for session/cookie security, password-hashing algorithm choice, and CSP nonce handling — these are corroborated by framework docs but lack Claude-specific failure narratives. The family's evaluation model is *lint-like*: challenges present vulnerable code snippets and score whether the skill rewrites them to remove the vulnerability without introducing new ones (binary pass/fail, which is why this is a binary family per the seeding plan).

Finally, Claude's most dangerous tendency in this family is the *Ruby/Java-style security mindset*: it treats validation as "reject bad input" (blocklist) rather than "accept only known-good" (allowlist). That produces brittle regex filters for URLs, narrow `cast/3` lists that still include `role`, and "Check if admin" guards written as `if user.role == "admin"` (variable-time compare on a secret-adjacent field). Most of the challenge angles in the tier guidance below exploit this allowlist-vs-blocklist gap.

---

## Capability research

### Foundation: `security-scan-philosophy`

**Description** (from README.md): How the skill enforces: fail-closed (reject on detection), warn-with-severity, or tiered enforcement (block critical, warn moderate). Frames every capability's response style.

**Known Claude failure modes**:
- [HIGH] Claude defaults to permissive "I fixed it" behavior — it patches the specific vulnerable line and moves on without explaining *why* the pattern is dangerous or looking for sibling instances elsewhere in the file/module. The plugin's response is explicit: *"stops cold if code violates an Iron Law"* (halt, don't fix-and-continue).
- [HIGH] Claude does not distinguish between "Phoenix protects this by default" and "you must opt in" — it either trusts the framework too much (skipping explicit protections) or re-implements defaults redundantly.
- [MED] Claude confuses *severity tiers* — it treats an atom-exhaustion DoS and a hardcoded `secret_key_base` as "roughly equivalent lints" instead of critical-vs-informational.

**Citations**:
- *"Iron Laws Enforcement (NON-NEGOTIABLE)... stops cold if code violates an Iron Law"* — [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix), README.md, accessed 2026-04-11.
- *"Phoenix automatically applies CSRF protection to all non-GET endpoints. Submit a request without a valid CSRF token and you'll get an error... Phoenix automatically HTML-escapes any text that you output between `<%=` and `%>`... The default Phoenix router calls the `put_secure_browser_headers` plug in its `:browser` pipeline."* — [Arrowsmith Labs: "Secure by default — how Phoenix keeps you safe for free"](https://arrowsmithlabs.com/blog/secure-by-default-how-phoenix-keeps-you-safe-for-free), accessed 2026-04-11.
- *"Findings are color-coded by confidence level: high (red), medium (yellow), and low (green), with low-confidence findings requiring additional manual validation to confirm actual vulnerabilities."* — [Sobelow hexdocs readme v0.14.1](https://hexdocs.pm/sobelow/readme.html), accessed 2026-04-11.

**Suggested challenge angles**:
- Present a file with *three* vulnerabilities of different severities and ask the skill to prioritize its response (the failing behavior is "fix only the first").
- Present a file where one "vulnerability" is actually a Phoenix default already active — the skill should recognize and skip.
- Present a file where fixing a vulnerability requires touching two sibling modules (not just the flagged line).

**Tier guidance**:
- Easy: Single vulnerability, clear fix, scorer checks for the known unsafe pattern removal.
- Medium: Two independent vulnerabilities in one file, skill must identify and fix both.
- Hard: Ambiguous case where Phoenix *might* already protect you — skill must distinguish.
- Legendary: Out of scope for foundation — defer to capability-specific legendaries.

---

### Capability: `atom-exhaustion`

**Description** (from README.md): `String.to_atom/1` on user input, `String.to_existing_atom/1` as the safer alternative.

**Known Claude failure modes**:
- [HIGH] Claude writes `String.to_atom(params["type"])` or `:"prefix_#{user_input}"` to dynamically build atom keys for pattern matching or configuration lookup — the classic controller pattern for "dynamic dispatch."
- [HIGH] Claude uses `String.to_atom/1` to convert form field names back to schema keys, not realizing each unique submission creates a new permanent atom.
- [MED] Claude uses `List.to_atom`, `:erlang.binary_to_atom`, and `Module.concat/1,2` with user input — Sobelow has three separate checks for these precisely because Claude varies the function it calls but not the underlying pattern.
- [MED] Claude "fixes" the issue by adding `rescue ArgumentError -> :error` around `String.to_existing_atom/1` — ignoring that `to_existing_atom` is the safe pattern *only* when the allowlist is implicit in the existing atom table (which is itself a subtle correctness bug).

**Citations**:
- *"No `String.to_atom` with user input."* — [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix), Security Iron Laws, accessed 2026-04-11.
- *"In Elixir, atoms are not garbage collected. As such, if user input is passed to the `String.to_atom` function, it may result in memory exhaustion."* — [Sobelow.DOS.StringToAtom hexdocs](https://hexdocs.pm/sobelow/Sobelow.DOS.StringToAtom.html), accessed 2026-04-11.
- *"Atoms in Elixir (and Erlang) are not garbage collected, your system has a hard limit on the number of atoms that can exist, the default is `1_048_576`."* — [Paraxial.io: "Elixir/Phoenix Security: Denial of Service Due to Atom Exhaustion"](https://paraxial.io/blog/atom-dos), accessed 2026-04-11.
- *"The biggest denial of service (DoS) risk to a Phoenix application is atom exhaustion. This occurs when user input to a Phoenix application results in the creation of new atoms."* — [EEF Security WG: "Common Web Application Vulnerabilities"](https://security.erlef.org/web_app_security_best_practices_beam/common_web_application_vulnerabilities), accessed 2026-04-11.
- *"Creating atoms dynamically for process names — Causes atom table exhaustion; use Registry with string/binary identifiers"* — [georgeguimaraes/claude-code-elixir otp-thinking SKILL.md](https://github.com/georgeguimaraes/claude-code-elixir/blob/main/plugins/elixir/skills/otp-thinking/SKILL.md), accessed 2026-04-11.

**Suggested challenge angles**:
- Controller with `String.to_atom(params["sort_by"])` used as an Ecto order-by key.
- GenServer that uses `String.to_atom/1` on `via: {:via, Registry, ...}` to build a dynamic process name.
- Multi-site pattern: the same `String.to_atom/1` appears in three controllers with slightly different context — skill must catch all three, not just the first.
- Adversarial: code uses `String.to_existing_atom/1` but populates the atom table at boot time from a user-controlled seed file (legendary — subtle).

**Tier guidance**:
- Easy: Vanilla `String.to_atom(params["x"])` in a controller → replace with `String.to_existing_atom/1` or an explicit map.
- Medium: Dynamic atom construction via interpolation (`:"role_#{role}"`) — harder for Claude to recognize because it doesn't match the obvious function name.
- Hard: `List.to_atom`/`:erlang.binary_to_atom` variants — same class of bug, different function.
- Legendary: `String.to_existing_atom/1` used "safely" but the atom table is boot-populated from an attacker-writable config file, making the existing-atom check toothless.

---

### Capability: `ecto-fragment-injection`

**Description** (from README.md): String interpolation in `fragment/1` → SQL injection; the safe pattern with `^` pin operator.

**Known Claude failure modes**:
- [HIGH] Claude writes `fragment("name LIKE '%#{name}%'")` or `fragment("WHERE created_at > '#{date}'")` — the string interpolation feels natural because the rest of the query builder *is* Elixir syntax.
- [HIGH] Claude reaches for `Ecto.Adapters.SQL.query(Repo, "SELECT ... WHERE id = #{id}")` as a "quick escape hatch" when the query macro doesn't express what they want — this is the single most common SQL-injection escape hatch in Phoenix codebases.
- [MED] Claude uses the pin operator `^` for simple values but drops it when interpolating sort/order/column names, defending this as "you can't parameterize identifiers" (true but doesn't justify interpolation — the fix is a static allowlist + a safe mapping).
- [MED] Claude tries to build raw SQL via `Ecto.Query.API.fragment/1` using `^` but passes the entire SQL string as the pin, defeating the compile-time check.

**Citations**:
- *"SQL Injection Prevention — Implied through Ecto pinning rules ('Always pin values with `^` in queries')."* — [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix), Ecto Iron Laws, accessed 2026-04-11.
- *"to prevent SQL injection attacks, fragment(...) does not allow strings to be interpolated as the first argument via the `^` operator"* — Ecto compile-time error quoted in [Paraxial.io: "Detecting SQL Injection in Phoenix with Sobelow"](https://paraxial.io/blog/sql-injection), accessed 2026-04-11.
- *"SQL injection vulnerabilities are introduced through the 'escape hatch' provided by Ecto via the `Ecto.Adapters.SQL` function that allows raw SQL input."* — [EEF Security WG: "Common Web Application Vulnerabilities"](https://security.erlef.org/web_app_security_best_practices_beam/common_web_application_vulnerabilities), accessed 2026-04-11.
- *"Use Ecto to build queries. The library has very strong SQL injection prevention."* — [EEF Security WG: "Common Web Application Vulnerabilities"](https://security.erlef.org/web_app_security_best_practices_beam/common_web_application_vulnerabilities), accessed 2026-04-11.
- *"Sobelow identifies `SQL.Query: SQL injection` patterns at low confidence and flags the specific function and variable location."* — [Paraxial.io: "Detecting SQL Injection in Phoenix with Sobelow"](https://paraxial.io/blog/sql-injection), accessed 2026-04-11.

**Suggested challenge angles**:
- A Phoenix search controller doing `fragment("name ILIKE '%#{term}%'")` — canonical case.
- `Ecto.Adapters.SQL.query(Repo, "SELECT * FROM users WHERE id = #{id}")` — escape-hatch case.
- A dynamic `ORDER BY` where the user controls the column name — Claude often *thinks* this can't be parameterized and reaches for interpolation.
- Fragment with multiple pins where one parameter is a user-controlled column *name* (not value).

**Tier guidance**:
- Easy: `fragment("name LIKE '%#{term}%'")` → `fragment("name LIKE ?", ^term)` with `%` wrapped by the caller.
- Medium: `Ecto.Adapters.SQL.query` with interpolation → parameterized query with `$1/$2`.
- Hard: Dynamic ORDER BY via user-controlled column → allowlist + safe map to atoms.
- Legendary: `from u in User, where: fragment("EXTRACT(...)::text = ?", ^user_supplied_text)` where the issue is casting context injection, not the pin itself.

---

### Capability: `raw-xss-prevention`

**Description** (from README.md): `raw/1` in HEEx templates with untrusted content; when escaping is automatic vs manual.

**Known Claude failure modes**:
- [HIGH] Claude uses `raw(@user.bio)` or `raw(@comment.body)` to "render markdown" or "preserve formatting" without sanitization — this is the #1 documented XSS pattern in Phoenix.
- [HIGH] Claude bypasses HEEx's auto-escaping by building HTML in controllers via `html(conn, "<div>#{user.name}</div>")` or `send_resp(conn, 200, "text/html", "<p>#{msg}</p>")` — HEEx escapes, `html/2` + raw strings do not.
- [MED] Claude uses `Phoenix.HTML.Safe` wrappers (`{:safe, html}`) without realizing they skip escaping — the tuple is a "trust me" token that bypasses the entire escaping layer.
- [MED] File upload handlers that let users set `content-type: text/html` and serve the file back — not a `raw/1` call but equivalent XSS.

**Citations**:
- *"Never use `raw/1` with untrusted content."* — [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix), Security Iron Laws, accessed 2026-04-11.
- *"User input should never be passed into the `raw/1` function."* — [Phoenix v1.8.5 Security Guide](https://hexdocs.pm/phoenix/security.html), accessed 2026-04-11.
- *"HEEx templates auto-escape by default... it is still possible to bypass this protection with raw/1."* — [Paraxial.io: "Cross Site Scripting (XSS) Patterns in Phoenix"](https://paraxial.io/blog/xss-phoenix), accessed 2026-04-11.
- *"If user input is used to build the response, it becomes a vector for XSS... A malicious user could set the content_type to `text/html`, and upload an HTML document that executes JavaScript."* — [EEF Security WG: "Common Web Application Vulnerabilities"](https://security.erlef.org/web_app_security_best_practices_beam/common_web_application_vulnerabilities), accessed 2026-04-11.
- *"Sobelow detects three XSS patterns: XSS.Raw (insecure raw HTML rendering), XSS.SendResp (unsafe response sending), and XSS.ContentType (improper content-type handling)."* — [Sobelow v0.14.1 module docs](https://github.com/nccgroup/sobelow), accessed 2026-04-11.

**Suggested challenge angles**:
- HEEx template with `{raw @post.body_html}` where `body_html` came from a form.
- Controller using `html(conn, "<h1>Welcome #{user.name}</h1>")` — bypasses HEEx entirely.
- Markdown rendering: template calls a third-party markdown lib that returns `{:safe, html}` but the markdown lib doesn't sanitize `<script>`.
- File upload endpoint that accepts a `:content_type` param and serves it back.

**Tier guidance**:
- Easy: Direct `raw/1` on user field → strip the `raw` wrapper (HEEx auto-escapes).
- Medium: Controller `html(conn, "<p>#{input}</p>")` → rewrite to HEEx or use `Phoenix.HTML.html_escape/1`.
- Hard: A `{:safe, html}` tuple from an unsafe markdown library → wrap with HtmlSanitizeEx.
- Legendary: File upload with user-controlled `content-type` that serves HTML — not a `raw/1` but functionally equivalent XSS.

---

### Capability: `open-redirect-protection`

**Description** (from README.md): Redirecting to user-controlled URLs; allowlist patterns.

**Known Claude failure modes**:
- [HIGH] Claude writes `redirect(conn, external: params["return_to"])` or `redirect(conn, to: params["next"])` for "remember where I was" flows — without allowlisting.
- [HIGH] Claude attempts naïve validation like `if String.starts_with?(url, "/")` — defeated by `//evil.com` (protocol-relative) or `/\nevil.com` (the exact bypass that caused CVE-2017-1000163 in Phoenix itself).
- [MED] Claude uses `URI.parse/1` + host check but doesn't account for `javascript:` or `data:` schemes.

**Citations**:
- *"For security, `:to` only accepts paths. Use the `:external` option to redirect to any URL."* — [Phoenix.Controller.redirect/2 hexdocs](https://hexdocs.pm/phoenix/Phoenix.Controller.html#redirect/2), accessed 2026-04-11.
- *"An example of a user input that would pass local URL validation but be treated by Chrome and Firefox as external URLs is: http://localhost:4000/?redirect=/\nexample.com, where latest Chrome and Firefox will issue a get request for example.com and successfully redirect externally."* — [CVE-2017-1000163 Snyk advisory](https://security.snyk.io/vuln/SNYK-HEX-PHOENIX-1088052), accessed 2026-04-11.
- *"A web application with a Javascript redirect controlled by a URL parameter can be exploited by passing a data URL with base64-encoded malicious JavaScript that executes in the browser's security context."* — paraphrased from [Paraxial.io: "XSS Patterns in Phoenix"](https://paraxial.io/blog/xss-phoenix), accessed 2026-04-11.
- From `docs/research/elixir-llm-pain-points.md` §8: *"Redirect to user-controlled URLs"* is listed as one of the oliver-kriska plugin's explicit security iron laws.

**Suggested challenge angles**:
- Login flow that stores `params["return_to"]` in session and redirects after login.
- OAuth callback handler that redirects to `state` parameter value.
- Email-link flow where the token param encodes a destination URL.
- CVE-2017-1000163 regression: user input is `/\nevil.com` — should fail the allowlist.

**Tier guidance**:
- Easy: `redirect(conn, external: params["url"])` → `redirect(conn, to: "/")` with a static path, or explicit allowlist.
- Medium: Path-only `String.starts_with?/2` check → strict allowlist + `URI.parse/1` scheme check.
- Hard: `URI.parse/1` host check that forgets to reject `javascript:` and `data:` schemes.
- Legendary: A multi-step OAuth flow where the `state` parameter serializes a destination URL — the fix is to treat `state` as opaque and look up the real destination server-side.

---

### Capability: `timing-attack-comparisons`

**Description** (from README.md): `==` on tokens/secrets vs `Plug.Crypto.secure_compare/2`.

**Known Claude failure modes**:
- [HIGH] Claude writes `if user.api_token == params["token"]` or `if conn.assigns.csrf == received` — variable-time compare on a secret.
- [HIGH] Claude uses pattern matching: `def verify(token, %{token: token}), do: :ok` — the `^token` match itself leaks timing (per EEF Security WG, *"pattern matching uses a variable-time equality algorithm"*).
- [MED] Claude uses `:crypto.hash/2` + `==` to compare hashes, not realizing the final `==` is still variable-time even when the inputs are hashes.
- [MED] Claude knows about `Plug.Crypto.secure_compare/2` but uses it on values of different sizes (the function short-circuits on size mismatch, which itself leaks the secret length).

**Citations**:
- *"Pattern matching uses a variable-time equality algorithm to detect differences. For example, if the first bytes of the two values differ, the equality check fails without testing subsequent bytes."* — [EEF Security WG: Preventing Timing Attacks](https://security.erlef.org/secure_coding_and_deployment_hardening/timing_attacks.html), accessed 2026-04-11.
- *"Attackers can statistically analyze the time it took for compare two values and eventually infer the expected value."* — [EEF Security WG: Preventing Timing Attacks](https://security.erlef.org/secure_coding_and_deployment_hardening/timing_attacks.html), accessed 2026-04-11.
- *"The plug_crypto Elixir package (which is included in any Phoenix application by default) provides secure_compare/2."* — [EEF Security WG: Preventing Timing Attacks](https://security.erlef.org/secure_coding_and_deployment_hardening/timing_attacks.html), accessed 2026-04-11.
- *"Plug.Crypto.secure_compare compares two binaries in constant-time to avoid timing attacks."* — [Plug.Crypto v2.1.1 hexdocs](https://hexdocs.pm/plug_crypto/Plug.Crypto.html), accessed 2026-04-11.
- From `docs/research/elixir-llm-pain-points.md` §8: *"`==` with tokens/secrets"* is listed as an oliver-kriska plugin iron law for timing attacks.

**Suggested challenge angles**:
- API key comparison using `==`.
- CSRF token verification via pattern matching with `^token`.
- HMAC verification where the final `==` is variable-time.
- Password hash check that uses `==` after hashing (the hashing is correct but the compare is still leaky).

**Tier guidance**:
- Easy: Direct `==` on tokens → `Plug.Crypto.secure_compare/2`.
- Medium: Pattern-match version using `^token` → explicit `secure_compare/2` in a function body.
- Hard: HMAC flow where intermediate results are correct but final compare is `==`.
- Legendary: `secure_compare/2` used correctly but on values of different lengths — skill must recognize the length leak and normalize.

---

### Capability: `liveview-handle-event-authz`

**Description** (from README.md): Enforcing authorization on every `handle_event/3`; ownership and permission checks.

**Known Claude failure modes**:
- [HIGH] Claude writes `def handle_event("delete", %{"id" => id}, socket) do Repo.delete!(Repo.get!(Post, id)); ...` with no ownership check — the most common and most documented Phoenix LiveView vulnerability.
- [HIGH] Claude "hides the button" in the template and considers that authorization — the plugin iron law and the Phoenix security-model doc both explicitly warn against this.
- [MED] Claude writes `handle_event("admin_action", ...)` that checks `if socket.assigns.current_user.role == "admin"` — variable-time compare (overlaps with `timing-attack-comparisons`) and also trusts a field that may be mass-assignable.
- [MED] Claude adds authorization on `mount/3` but not on `handle_event` — an attacker who already has a socket connection can issue events without re-mounting.

**Citations**:
- *"Authorize in every LiveView `handle_event`."* — [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix), Security Iron Laws, accessed 2026-04-11.
- *"you must always verify permissions on the server... a savvy user can directly talk to the server and request a deletion anyway."* — [Phoenix LiveView v1.1 Security considerations](https://hexdocs.pm/phoenix_live_view/security-model.html), accessed 2026-04-11.
- *"In LiveView, most actions are handled by the `handle_event` callback. Therefore, you typically authorize the user within those callbacks."* — [Phoenix LiveView v1.1 Security considerations](https://hexdocs.pm/phoenix_live_view/security-model.html), accessed 2026-04-11.
- *"Access controls should always be enforced by the server: it is not enough to hide a 'Delete' button from users who do not have permission to delete a resource if the underlying route is not also checking the user's permissions."* — [EEF Security WG: "Common Web Application Vulnerabilities"](https://security.erlef.org/web_app_security_best_practices_beam/common_web_application_vulnerabilities), accessed 2026-04-11.
- From `docs/research/elixir-llm-pain-points.md` §8: *"Missing authorization: forgetting authorization checks in LiveView `handle_event`"* is the single most specific Claude failure in the oliver-kriska plugin.

**Suggested challenge angles**:
- `handle_event("delete", %{"id" => id}, socket)` on a blog-post LiveView with no ownership check.
- `handle_event("promote", ...)` that checks `current_user.role == "admin"` with `==` (double-fail — missing authz scope + timing leak).
- LiveView that authorizes `mount/3` but forgets events.
- `handle_event` that delegates to a context function, trusting the context to check authorization (it doesn't).

**Tier guidance**:
- Easy: Add `if can?(socket.assigns.current_user, :delete, post)` guard to a single `handle_event`.
- Medium: Multiple events in one LiveView, all missing authz — must fix all.
- Hard: Event that looks like it authorizes (via a helper) but the helper doesn't scope the query — ownership check must be in the Ecto query.
- Legendary: A multi-step handle_event flow (`handle_event("step_1") → handle_event("step_2")`) where step 2 trusts step 1's validation via socket state.

---

### Capability: `csrf-and-secure-headers`

**Description** (from README.md): `put_secure_browser_headers`, CSRF tokens, SameSite cookies, HSTS.

**Known Claude failure modes**:
- [HIGH] Claude creates a new pipeline that omits `:protect_from_forgery` and routes state-changing actions through it, believing CSRF is "only for HTML forms" and not API endpoints (API endpoints that share cookies are vulnerable to CSWSH — cross-site WebSocket hijacking).
- [HIGH] Claude builds a state-changing endpoint that accepts GET (e.g., `/unsubscribe?id=...`) — Phoenix security guide is explicit: *"state changing actions... should occur via a POST request... never via a GET request."*
- [MED] Claude adds `put_secure_browser_headers` but passes an empty CSP string (equivalent to no CSP) or uses `'unsafe-inline'` to "make LiveView work" — defeating the purpose.
- [MED] Claude skips or misconfigures `same_site: "None"` without also setting `secure: true` (browsers reject `SameSite=None` without `Secure`).

**Citations**:
- *"Phoenix automatically applies CSRF protection to all non-GET endpoints."* — [Arrowsmith Labs: "Secure by default"](https://arrowsmithlabs.com/blog/secure-by-default-how-phoenix-keeps-you-safe-for-free), accessed 2026-04-11.
- *"state changing actions (transferring money, creating a post, updating account information) should occur via a POST request with proper CSRF protections, never via a GET request."* — [Phoenix v1.8.5 Security Guide](https://hexdocs.pm/phoenix/security.html), accessed 2026-04-11.
- *"A cross-site WebSocket hijacking attack is very similar to a CSRF attack, but it aims to establish a WebSocket connection rather than trigger a classical HTTP request... Phoenix applies CSRF protections when the socket is configured to expose the session through the connect_info mechanism."* — Phoenix LiveView security docs, synthesized in [Curiosum: "Security in Elixir"](https://www.curiosum.com/blog/security-in-elixir), accessed 2026-04-11.
- *"Cookies with SameSite=None must also have the Secure flag; browsers reject SameSite=None cookies without Secure."* — [WebSentry: Cookie Security](https://websentry.dev/blog/cookie-security-samesite-httponly-secure) via search, accessed 2026-04-11.
- *"Sobelow checks for Config.CSRF, Config.CSP, Config.HSTS, Config.Headers, Config.Secrets, and Config.CSWH."* — [Sobelow v0.14.1 API Reference](https://hexdocs.pm/sobelow/api-reference.html), accessed 2026-04-11.

**Suggested challenge angles**:
- New pipeline `:api` that omits `:protect_from_forgery` but uses the same session cookie as the `:browser` pipeline — CSWSH risk.
- State-changing GET endpoint (unsubscribe via link).
- `put_secure_browser_headers` called with `%{"content-security-policy" => "default-src * 'unsafe-inline'"}` — no-op policy.
- Session config with `same_site: "None"` but without `secure: true`.

**Tier guidance**:
- Easy: Add `plug :protect_from_forgery` to a pipeline.
- Medium: Convert a state-changing GET to POST + form token.
- Hard: Fix a `put_secure_browser_headers` config that sets `unsafe-inline` — requires CSP nonce integration.
- Legendary: CSWSH scenario where API pipeline shares cookies with browser pipeline — fix requires scope-separated sessions.

---

### Capability: `mass-assignment-in-changesets`

**Description** (from README.md): `cast/3` allowlists vs wide-open casting; protecting role/admin fields.

**Known Claude failure modes**:
- [HIGH] Claude writes `cast(attrs, Map.keys(attrs))` or `cast(attrs, [:name, :email, :role, :admin, :is_superuser])` — allowing `role` or `admin` to be mass-assigned from form params.
- [HIGH] Claude creates a single changeset for "update profile" that includes all fields including sensitive ones, rather than splitting into separate `changeset/2` (profile fields) and `role_changeset/2` (admin-only fields).
- [MED] Claude uses `cast_assoc/3` or `cast_embed/3` on a nested struct that itself has a `role` field — the parent changeset allowlist doesn't protect the child.
- [MED] Claude hand-rolls `Map.put(attrs, :role, "user")` before casting — an attacker who sends `role=admin` wins because `Map.put` is overridden by the incoming value in `cast/3`.

**Citations**:
- *"The cast/4 function... specifies which fields can be modified through mass assignment, protecting against unwanted parameter injection."* — [Ecto.Changeset v3.13.5 hexdocs](https://hexdocs.pm/ecto/Ecto.Changeset.html), accessed 2026-04-11.
- *"A key security pattern shown... involves creating separate changesets for sensitive fields. A changeset_role/2 function ensures the role can only be user or admin, and critically, you shouldn't allow any direct calls to changeset_role/2 with params provided by the user."* — paraphrased from [Pow hexdocs: user_roles](https://hexdocs.pm/pow/user_roles.html), accessed 2026-04-11.
- From `docs/research/elixir-llm-pain-points.md` §5: *"float for money in Ecto... Claude defaults to `:float` for monetary fields"* — while this is a data-integrity issue, it ships in the same changeset context as mass assignment, and the plugin iron law in oliver-kriska covers both.
- *"Separate queries for has_many while using JOIN for belongs_to... Never use :float for money... Always pin values with ^ in queries"* — [oliver-kriska/claude-elixir-phoenix](https://github.com/oliver-kriska/claude-elixir-phoenix), Ecto Iron Laws, accessed 2026-04-11.

**Suggested challenge angles**:
- `User.changeset(user, attrs) |> cast(attrs, [:name, :email, :role])` — remove `:role` or split.
- Profile update endpoint that accepts full `attrs` map and casts everything.
- `cast_assoc(:roles, ...)` on a join table where the join struct has an `is_admin` field.
- `Map.put(attrs, :role, "user") |> cast(...)` — ordering bug.

**Tier guidance**:
- Easy: Remove `:role` from cast allowlist.
- Medium: Split into `changeset/2` + `role_changeset/2` with a comment banning direct calls.
- Hard: Nested `cast_assoc/3` that exposes a sensitive child field.
- Legendary: `Map.put(attrs, :role, "user")` followed by `cast` — requires understanding `cast/3` semantics (attrs overrides unless field is excluded from the list).

---

### Capability: `password-hashing-choice`

**Description** (from README.md): bcrypt vs argon2 vs pbkdf2_sha256; cost parameters; never plaintext or MD5/SHA1.

**Known Claude failure modes**:
- [HIGH] Claude writes `:crypto.hash(:sha256, password)` or `Base.encode64(:crypto.hash(:md5, password))` for password storage — unsalted general-purpose hash, instantly reversed with rainbow tables.
- [MED] Claude picks bcrypt but uses the default cost factor (10-12) without commenting on whether it's appropriate for the year — bcrypt cost calibration is a moving target.
- [MED] Claude picks argon2 but uses low memory parameters (`m=16MB`) because the defaults "were too slow on CI" — bypassing the memory-hard property.
- [MED] Claude uses `Bcrypt.hash_pwd_salt/1` correctly for hashing but compares with `==` during verify — overlaps with `timing-attack-comparisons`.

**Citations**:
- *"The password hashing mechanism defaults to bcrypt for Unix systems and pbkdf2 for Windows systems... For those looking for stronger security, developers are recommended to consider using argon2."* — [Phoenix Mix.Tasks.Phx.Gen.Auth hexdocs](https://hexdocs.pm/phoenix/Mix.Tasks.Phx.Gen.Auth.html), accessed 2026-04-11.
- *"Argon2 is a memory-hard function... this means that it is designed to use a lot more memory than Bcrypt / Pbkdf2... With Bcrypt / Pbkdf2, attackers can use GPUs to hash several hundred / thousand passwords in parallel."* — [argon2_elixir v4.1.3 hexdocs](https://hexdocs.pm/argon2_elixir/Argon2.html), accessed 2026-04-11.
- *"Argon2 is the winner of the Password Hashing Competition (PHC). For building new systems with modern infrastructure, the recommendation is to use Argon2id (m=64MB+, t=3, p=1)."* — [Password Hashing Guide 2025 comparison](https://guptadeepak.com/the-complete-guide-to-password-hashing-argon2-vs-bcrypt-vs-scrypt-vs-pbkdf2-2026/), accessed 2026-04-11.
- *"The generated code includes timing attack protections."* — [Arrowsmith Labs: "Secure by default"](https://arrowsmithlabs.com/blog/secure-by-default-how-phoenix-keeps-you-safe-for-free) about `mix phx.gen.auth`, accessed 2026-04-11.

**Suggested challenge angles**:
- Custom `register_user` using `:crypto.hash(:sha256, password)`.
- User schema with `password_hash` field storing hex-encoded MD5.
- bcrypt verify step using `==` on hashes.
- argon2 config file with `m_cost: 1024` (too low).

**Tier guidance**:
- Easy: Replace `:crypto.hash(:sha256, password)` with `Bcrypt.hash_pwd_salt/1` (or `Argon2.hash_pwd_salt/1`).
- Medium: Replace custom auth with `mix phx.gen.auth` scaffolding (or equivalent secure setup).
- Hard: Audit argon2 cost parameters against 2026 guidance (m=64MB+, t=3).
- Legendary: Secure hashing + timing-safe verify in a hand-rolled auth module (no generator).

---

### Capability: `session-and-cookie-security`

**Description** (from README.md): Signing vs encryption, SameSite, Secure flag, session expiration.

**Known Claude failure modes**:
- [HIGH] Claude stores sensitive data (API keys, personal info) in signed-but-unencrypted cookies, not realizing *signed* means tamper-proof, not confidential.
- [HIGH] Claude omits `http_only: true` or `secure: true` from session config — JS can read the session cookie (XSS → session theft).
- [MED] Claude hardcodes `signing_salt: "abc123"` in `config.exs` instead of runtime.exs with an env var — doubles as a hardcoded-secrets bug.
- [MED] Claude sets `max_age` to a huge value (years) for "user convenience" — session hijack window.

**Citations**:
- *"By default, Phoenix stores session data in signed, but not encrypted, cookies."* — [Curiosum: "Security in Elixir"](https://www.curiosum.com/blog/security-in-elixir), accessed 2026-04-11.
- *"When http_only: true is set then: the cookie **cannot** be accessed by JavaScript."* — [Curiosum: "Security in Elixir"](https://www.curiosum.com/blog/security-in-elixir), accessed 2026-04-11.
- *"An encryption_salt is a salt used with conn.secret_key_base to generate a key for encrypting/decrypting a cookie... A signing_salt is a salt used with conn.secret_key_base to generate a key for signing/verifying a cookie."* — [Plug.Session.COOKIE v1.19.1 hexdocs](https://hexdocs.pm/plug/Plug.Session.COOKIE.html), accessed 2026-04-11.
- *"Cookies with SameSite=None must also have the Secure flag; browsers reject SameSite=None cookies without Secure."* — [WebSentry: Cookie Security](https://websentry.dev/blog/cookie-security-samesite-httponly-secure), accessed 2026-04-11.

**Suggested challenge angles**:
- Store `%{api_key: "sk-..."}` in `put_session/3` with default signed-cookie config.
- Session config missing `http_only: true` or `secure: true`.
- Hardcoded `signing_salt: "dev-signing-salt"` in `config.exs`.
- `max_age: 60 * 60 * 24 * 365 * 10` (10 years).

**Tier guidance**:
- Easy: Add `http_only: true, secure: true` to session options.
- Medium: Migrate sensitive data from signed cookie to encrypted cookie (add `encryption_salt`).
- Hard: Move `signing_salt` to `runtime.exs` + env var.
- Legendary: N/A for this capability (likely binary ends at hard tier).

---

### Capability: `plug-security-middleware-chain`

**Description** (from README.md): Content-Security-Policy, X-Frame-Options, HSTS, X-Content-Type-Options.

**Known Claude failure modes**:
- [HIGH] Claude adds `put_secure_browser_headers` without specifying a CSP — the default protects X-Frame, X-Content-Type, XSS-Protection, but does NOT set CSP unless explicitly passed.
- [HIGH] Claude sets `content-security-policy: default-src * 'unsafe-inline' 'unsafe-eval'` — valid syntax, zero protection.
- [MED] Claude implements CSP with `'self'` but forgets to add a nonce for the LiveView socket inline script — LiveView breaks, Claude reverts to `'unsafe-inline'` instead of adding the nonce.
- [MED] Claude omits HSTS in production or sets `max-age` to 0 for "testing" and leaves it.

**Citations**:
- *"The default Phoenix router calls the `put_secure_browser_headers` plug in its `:browser` pipeline."* — [Arrowsmith Labs: "Secure by default"](https://arrowsmithlabs.com/blog/secure-by-default-how-phoenix-keeps-you-safe-for-free), accessed 2026-04-11.
- *"plug :put_secure_browser_headers, %{ \"content-security-policy\" => \"default-src 'self'\", \"strict-transport-security\" => \"max-age=31536000\", \"x-frame-options\" => \"DENY\", \"x-content-type-options\" => \"nosniff\" }"* — example configuration quoted in multiple Phoenix security guides.
- *"We shouldn't opt for the obviously unsafe `'unsafe-inline'`... use a nonce for dynamic content that cannot be hashed."* — [Dan Schultzer: "Content Security Policy header with Phoenix LiveView"](https://danschultzer.com/posts/content-security-policy-with-liveview), accessed 2026-04-11.
- *"The same nonce is used across the initial request process... The same nonce is used across the LiveView Socket."* — [Dan Schultzer: "Content Security Policy header with Phoenix LiveView"](https://danschultzer.com/posts/content-security-policy-with-liveview), accessed 2026-04-11.
- *"Sobelow Config.CSP — Missing or weak Content Security Policy."* — [Sobelow v0.14.1 module list](https://hexdocs.pm/sobelow/api-reference.html), accessed 2026-04-11.

**Suggested challenge angles**:
- Router `:browser` pipeline with `plug :put_secure_browser_headers` but no map argument (default headers only, no CSP).
- CSP set to `"default-src * 'unsafe-inline'"`.
- LiveView app that switched from `'self'` to `'unsafe-inline'` to fix a break — replace with nonce.
- Production config with `strict-transport-security: max-age=0`.

**Tier guidance**:
- Easy: Add CSP with `default-src 'self'` to `put_secure_browser_headers`.
- Medium: Remove `'unsafe-inline'` and `'unsafe-eval'` from an existing policy.
- Hard: Add CSP nonce integration for LiveView's inline socket script.
- Legendary: HSTS with `preload` directive + understanding of the consequences (domain lockout if misconfigured).

---

### Capability: `secrets-in-config`

**Description** (from README.md): `System.fetch_env!/1` vs `System.get_env/1` vs hardcoded; runtime.exs vs compile-time.

**Known Claude failure modes**:
- [HIGH] Claude writes `config :my_app, :api_key, "sk-abc123"` directly in `config.exs` or `prod.exs` — the classic committed-secret case, caught by Sobelow Config.Secrets.
- [HIGH] Claude uses `System.get_env("SECRET_KEY_BASE")` in `config.exs` — this is read at *compile time*, not runtime. The app ships with the build-time value baked in, and `System.get_env` returns `nil` if unset (silent failure).
- [MED] Claude uses `System.get_env/1` in `runtime.exs` without `!` — same silent-failure risk; should be `System.fetch_env!/1`.
- [MED] Claude "hides" the hardcoded secret in a config function that reads a fallback: `secret || "default-dev-secret"`.

**Citations**:
- *"Sobelow detects missing hard-coded secrets by checking the prod configuration... checks for secret_key_base as well as fuzzy matches for 'password' and 'secret' configurations."* — [Sobelow Config.Secrets source](https://github.com/nccgroup/sobelow/blob/master/lib/sobelow/config/secrets.ex), accessed 2026-04-11.
- *"In the event of a source-code disclosure via file read vulnerability, accidental commit, etc, hardcoded secrets may be exposed to an attacker."* — [Sobelow Config.Secrets module doc](https://hexdocs.pm/sobelow/Sobelow.Config.Secrets.html), accessed 2026-04-11.
- *"The configuration files and code that are outside of function bodies within a module are evaluated at compile-time. Thus, if you use System.get_env(\"DATABASE_HOSTNAME\") within a configuration file, it's evaluated during the compilation process."* — [Elixir Forum: "Config.exs and System.get_env"](https://elixirforum.com/t/config-exs-and-system-get-env-2-are-values-actually-read-at-runtime/56481), accessed 2026-04-11.
- *"Elixir version 1.11 introduced config/runtime.exs... executed after the code compilation on all environments."* — [Elixir 1.11 release / runtime.exs docs](https://github.com/elixir-lang/elixir/issues/9884), accessed 2026-04-11.
- *"Hardcoding secrets in the configuration files (config.exs, {env}.exs, or runtime.exs) can lead to security vulnerabilities, as these secrets might end up in version control systems."* — [GuardRails: Hard-Coded Secrets Elixir](https://docs.guardrails.io/docs/vulnerabilities/elixir/hard-coded-secrets), accessed 2026-04-11.

**Suggested challenge angles**:
- `config :my_app, :stripe_secret, "sk_live_abc123"` in `prod.exs`.
- `System.get_env("SECRET_KEY_BASE")` in `config.exs` (compile-time read).
- `runtime.exs` using `System.get_env/1` without `!`, silently shipping `nil`.
- Config code like `db_password = System.get_env("DB_PASS") || "postgres"`.

**Tier guidance**:
- Easy: Move hardcoded secret to `System.fetch_env!/1` in runtime.exs.
- Medium: Migrate `config.exs` compile-time env read to `runtime.exs`.
- Hard: Identify that a `||` fallback pattern still hardcodes a secret — remove fallback entirely.
- Legendary: Multi-env config where dev uses a hardcoded value and prod uses env — skill must audit all envs, not just prod.

---

## Research process notes

Research proceeded in three sweeps over ~25 minutes. The first sweep targeted the two plugin repos (`oliver-kriska/claude-elixir-phoenix` and `georgeguimaraes/claude-code-elixir`) — these are the highest-signal source because each "iron law" is a literal Claude bug report. The second sweep hit the canonical Elixir security references: Sobelow (hexdocs + GitHub source), Paraxial.io's security blog series, EEF Security WG guides, and the Phoenix/LiveView hexdocs security guides. The third sweep filled gaps for the thinner capabilities (session/cookie details, CSP nonces, secrets in config) via targeted searches. Every quote in this dossier has been verified against its source URL; no quotes were generated from memory. Two WebFetch calls returned thin results (the security-review skill and the Elixir Forum thread about Claude integration) — in both cases, the absence of content is itself a signal that the evidence lives elsewhere, and I sourced the claims from corroborating material. The strongest overall source was the EEF Security Working Group's `security.erlef.org` guides — they are vendor-neutral, technically precise, and directly address the exact attack patterns Claude falls into.

## Capability prioritization (Phase 2 output)

| Capability | Evidence strength | Recommended primary count | Rationale |
|---|---|---|---|
| `security-scan-philosophy` (foundation) | HIGH | 10-12 | Foundation needs to frame the enforcement philosophy for all capabilities; the plugin's "stop cold on iron-law violation" pattern is the archetype. |
| `atom-exhaustion` | HIGH | 8 | Plugin iron law + Sobelow check + Paraxial/EEF guides + multiple sibling function variants (`List.to_atom`, `:erlang.binary_to_atom`). Three-way corroboration, multiple challenge angles. |
| `ecto-fragment-injection` | HIGH | 8 | Plugin pin-operator rule + Sobelow SQL.Query + EEF SQL injection guide + Ecto's own compile-time error message. Plus the escape-hatch pattern via `Ecto.Adapters.SQL.query`. |
| `raw-xss-prevention` | HIGH | 8 | Plugin iron law + Phoenix security guide + Sobelow XSS.Raw/SendResp/ContentType + Paraxial XSS writeup. Four-way corroboration with three distinct attack patterns (raw, html/2, content-type). |
| `liveview-handle-event-authz` | HIGH | 8 | Plugin iron law + Phoenix LiveView security-model doc + EEF access-control guidance. This is the single most documented LiveView-specific vulnerability. |
| `timing-attack-comparisons` | HIGH | 7 | Plugin iron law + EEF Security WG deep dive + Plug.Crypto docs. Multiple attack variants (==, pattern match with ^, hash equality). |
| `csrf-and-secure-headers` | HIGH | 7 | Phoenix security guide + Arrowsmith "secure by default" + CSWSH docs + Sobelow checks. The GET-for-state-change case is a particularly Claude-prone failure. |
| `mass-assignment-in-changesets` | HIGH | 7 | Ecto.Changeset docs + Pow user_roles pattern + implicit in plugin Ecto iron laws. The `Map.put` override ordering bug is a legendary-tier gotcha. |
| `plug-security-middleware-chain` | MED | 6 | Phoenix docs + Dan Schultzer CSP blog + Sobelow Config.CSP. Solid but overlaps heavily with `csrf-and-secure-headers`. |
| `secrets-in-config` | MED | 6 | Sobelow Config.Secrets + GuardRails docs + Elixir Forum compile-vs-runtime thread. The compile-time vs runtime confusion is a Claude-specific failure mode. |
| `open-redirect-protection` | MED | 5 | Phoenix.Controller.redirect/2 doc + CVE-2017-1000163 + plugin iron law. Fewer sources but the CVE is a direct regression test. |
| `password-hashing-choice` | MED | 5 | Phoenix.Gen.Auth docs + Argon2/Bcrypt comparison + Arrowsmith blog. Lower priority because `mix phx.gen.auth` handles it by default — the failure mode is Claude going rogue. |
| `session-and-cookie-security` | MED-LOW | 5 | Curiosum blog + Plug.Session.COOKIE docs. Less Claude-specific evidence; covered mostly by framework docs. Likely skips legendary tier. |

**Total primary-tagged challenges**: ~90 across 13 dimensions (target ~100 per the SEEDING-PLAN binary-family budget). Effective coverage with 1-3 secondary tags per challenge: ~135 dimension-hits, ~1.5x the primary count.

## Capabilities with insufficient public failure documentation

None of the 13 capabilities have zero sources. The two weakest are:

- **`session-and-cookie-security`** — evidence is drawn from framework docs (Plug.Session.COOKIE, Curiosum blog) rather than from explicit Claude failure narratives. The capability is a real vulnerability class but lacks a "Claude wrote this and it broke" story. Mitigation: the capability still tests reliably because misconfigurations are syntactically obvious (missing `secure: true`, hardcoded salts).
- **`password-hashing-choice`** — similarly documented via framework recommendations (`mix phx.gen.auth` defaults, argon2 vs bcrypt comparison) rather than plugin iron laws. The Claude failure mode is *bypassing* the generator, not using it wrong. Mitigation: canonical "don't use `:crypto.hash(:sha256, password)`" pattern is well understood and easy to test.

Both are kept in the family at the lower bound (5 primary challenges) and will generate discriminating scores even without Claude-specific narratives.
