# Anthropic Design System Reference

*Extracted 2026-04-09 from anthropic.com + claude.com/product/overview*

## Sources & Extraction Notes

- **anthropic.com homepage**: exposed one literal brand hex (`#d97757`) and one near-black (`#131314`). Most other values are hidden behind CSS custom properties like `--swatch--cloud-light`, `--_theme---background`, `--_theme---text`, whose computed values are not inlined.
- **claude.com/product/overview**: exposed a second warmer accent (`#C46849`) used as a "heroes accent", an error red (`#df6666`), and a gray ramp referenced as `--swatch--gray-050` … `--swatch--gray-950` (values not inlined). Fonts are referenced only as `var(--_typography---font--secondary-family)` / `--mono-family` — the actual family names are not in the fetched HTML.
- **claude.com root**: served a JS/i18n shell only; no CSS extractable.

Where values below are marked *(inferred)*, they are proposed from Anthropic's publicly known brand language (their 2024 rebrand by Alex Pasquarelli / Instrument) rather than scraped. Exact hexes should be treated as evocative, not canonical.

---

## Colors

### Brand
| Token | Hex | RGB | Usage |
|---|---|---|---|
| brand-primary | `#D97757` | 217,119,87 | Primary CTA, brand accent (anthropic.com literal) |
| brand-primary-deep | `#C46849` | 196,104,73 | Hover / pressed, "heroes accent" on claude.com |
| brand-primary-soft *(inferred)* | `#E8B4A0` | 232,180,160 | Tints, subtle backgrounds |
| brand-clay *(inferred)* | `#BD5D3A` | 189,93,58 | Dark-mode accent where #D97757 is too bright |

### Neutrals — Light Mode
| Token | Hex | Usage |
|---|---|---|
| bg-base | `#F5F4EE` *(inferred — warm off-white / "faded paper")* | Page background |
| bg-raised | `#FAF9F5` *(inferred)* | Cards, raised surfaces |
| bg-sunken | `#EEECE2` *(inferred)* | Input wells, code blocks |
| text-primary | `#131314` | Body text (anthropic.com literal) |
| text-secondary | `#4A4A48` *(inferred)* | Muted copy |
| text-tertiary | `#87867F` *(inferred)* | Captions, labels |
| border | `#E3E1D6` *(inferred)* | Dividers, card outlines |
| border-strong | `#CCC9BA` *(inferred)* | Focus rings, emphasized outlines |

### Neutrals — Dark Mode
| Token | Hex | Usage |
|---|---|---|
| bg-base | `#131314` | Page background (literal) |
| bg-raised | `#1E1E1F` *(inferred)* | Cards |
| bg-sunken | `#0C0C0D` *(inferred)* | Wells, code |
| text-primary | `#F5F4EE` *(inferred, mirrors light bg-base)* | Body |
| text-secondary | `#BFBDB3` *(inferred)* | Muted |
| text-tertiary | `#87867F` *(inferred)* | Captions |
| border | `#2A2A2B` *(inferred)* | Dividers |
| border-strong | `#3D3D3E` *(inferred)* | Focus, emphasis |

### Semantic / Accents
| Token | Hex | Source |
|---|---|---|
| error | `#DF6666` | literal, claude.com |
| success *(inferred)* | `#8CA87C` | sage, matches Claude palette vibe |
| warning *(inferred)* | `#E5A94B` | warm amber |
| info *(inferred)* | `#7A9CC6` | dusty blue |

---

## Typography

### Font Stack (as referenced on claude.com)

Anthropic publicly uses **Styrene B** (sans display/UI) and **Tiempos Text** (serif body) from Klim Type Foundry, plus **GT America Mono** or similar for code. These are all paid/licensed.

Since we will not be licensing them, propose free equivalents:

| Role | Anthropic (canonical) | Free substitute | Fallback stack |
|---|---|---|---|
| Display / UI sans | Styrene B | **Inter** (or Manrope) | `Inter, ui-sans-serif, system-ui, sans-serif` |
| Body serif | Tiempos Text | **Source Serif 4** (or Spectral) | `"Source Serif 4", Spectral, Georgia, serif` |
| Mono | GT America Mono | **JetBrains Mono** (or IBM Plex Mono) | `"JetBrains Mono", ui-monospace, SFMono-Regular, monospace` |

**Licensing note**: Styrene + Tiempos cost ~$600/weight combined. Inter + Source Serif 4 are OFL/free on Google Fonts and carry similar geometric-humanist + literary-serif pairing.

### Type Scale

Anthropic uses `clamp()` for fluid type. Extracted ranges:

| Token | Range | Tailwind equivalent |
|---|---|---|
| display-xxl | `clamp(3rem, …, 5rem)` | `text-5xl md:text-7xl` |
| display-xl | `clamp(2.5rem, …, 4rem)` | `text-4xl md:text-6xl` |
| display-l | `clamp(2rem, …, 3rem)` | `text-3xl md:text-5xl` |
| display-m | `clamp(1.5rem, …, 2.25rem)` | `text-2xl md:text-4xl` |
| display-s | `clamp(1.25rem, …, 1.5rem)` | `text-xl md:text-2xl` |
| paragraph-l | `clamp(1.125rem, …, 1.5rem)` | `text-lg md:text-2xl` |
| paragraph-m | `clamp(1rem, …, 1.25rem)` | `text-base md:text-xl` |
| paragraph-s | `clamp(0.875rem, …, 1rem)` | `text-sm md:text-base` |
| mono | `clamp(0.875rem, …, 2rem)` | `text-sm md:text-2xl font-mono` |

Line-height: `--_typography---line-height--1-6` → `1.6` for body. Display uses tighter ~`1.1`.

---

## Spacing & Radii

### Spacing

- **Nav height**: `4.25rem` (68px) — literal
- **Site margin**: `clamp(2rem, 1.08rem + 3.92vw, 5rem)` — literal
- Base unit appears to be **`0.5rem` (8px)** with half-step `0.25rem`. Common increments: `0.5 / 1 / 1.5 / 2 / 3 / 4 / 6 rem`.

### Radii

| Token | Value | Source |
|---|---|---|
| radius-sm | `8px` *(inferred)* | modal padding was `8px` |
| radius-md | `12px` *(inferred)* | standard cards |
| radius-lg | `24px` | literal (toggle pills) |
| radius-xl | `32px` *(inferred)* | large feature cards |
| radius-full | `9999px` / `50%` | literal (circular) |

Anthropic's aesthetic leans **softly rounded, not pill-happy** — cards are ~12–16px, CTAs ~8–12px, only toggles/chips use 24px+.

---

## Key Visual Patterns

- **Buttons (primary, light mode)**: solid warm dark (`#131314`) on warm off-white bg, or `#D97757` on off-white for brand CTAs. Text is `#F5F4EE`. Padding ~`0.75rem 1.25rem`. Radius ~`8–12px`. Hover darkens ~8% (e.g. `#C46849`).
- **Buttons (secondary)**: transparent with `1px` border in `border-strong`, text in `text-primary`. Hover fills with `bg-sunken`.
- **Cards**: `bg-raised`, `1px` border in `border`, `radius-md` (12px), generous internal padding (`1.5–2rem`), no shadow (Anthropic avoids drop shadows — they use hairline borders and surface color contrast instead).
- **Links**: `text-primary` underlined on hover, or brand-primary for "call out" links. No persistent underline.
- **Transitions**: `300ms ease` on color, `100ms ease-in-out` on box-shadow, `50ms` on active (literal from claude.com). Expand easing: `cubic-bezier(0.16, 1, 0.3, 1)` (`--ease-expo-out`, literal).
- **Shadows**: minimal. When present, very soft and warm-tinted: `0 1px 2px rgba(19,19,20,0.04), 0 4px 12px rgba(19,19,20,0.06)`.
- **Focus ring**: thick offset ring in brand-primary — `outline: 2px solid #D97757; outline-offset: 2px`.

---

## Proposed Mapping to Our Material Design 3 Tokens

Our existing MD3 token system (`primary`, `secondary`, `tertiary`, `surface`, `surface-container-lowest`, `on-surface`, `on-surface-dim`, `outline`, `outline-variant`) maps cleanly onto the Anthropic palette:

| Our Token | Anthropic Source | Light Value | Dark Value |
|---|---|---|---|
| primary | brand-primary | `#D97757` | `#D97757` |
| on-primary | text on primary | `#FAF9F5` | `#131314` |
| primary-container | brand-primary-soft | `#E8B4A0` | `#BD5D3A` |
| on-primary-container | | `#4A1F0E` | `#FAE5DA` |
| secondary | text-primary (warm near-black) | `#131314` | `#F5F4EE` |
| tertiary | success sage *(inferred)* | `#8CA87C` | `#A8C49A` |
| surface | bg-base | `#F5F4EE` | `#131314` |
| surface-container-lowest | bg-sunken | `#EEECE2` | `#0C0C0D` |
| surface-container | bg-raised | `#FAF9F5` | `#1E1E1F` |
| surface-container-high | bg-raised (+1) | `#FFFFFF` | `#26262A` |
| on-surface | text-primary | `#131314` | `#F5F4EE` |
| on-surface-dim | text-secondary | `#4A4A48` | `#BFBDB3` |
| on-surface-variant | text-tertiary | `#87867F` | `#87867F` |
| outline | border-strong | `#CCC9BA` | `#3D3D3E` |
| outline-variant | border | `#E3E1D6` | `#2A2A2B` |
| error | error literal | `#DF6666` | `#DF6666` |

---

## Implementation Notes

1. **Brand orange is the only truly "known" color.** `#D97757` (anthropic.com hero) and `#C46849` (claude.com hero) are both literals in page source. Use `#D97757` as primary and `#C46849` as hover/pressed — this mirrors Anthropic's own two-tone usage.
2. **Warm neutrals are inferred.** Anthropic's cream/paper background is instantly recognizable but not exposed as a literal hex in the fetched HTML (it's behind a CSS custom property whose computed value wasn't inlined). `#F5F4EE` is a close evocative match; teammates with DevTools on the live site can replace it with the exact computed value in a 30-second follow-up.
3. **Fonts: do NOT pay for Styrene/Tiempos.** Use Inter + Source Serif 4 (both Google Fonts, OFL). The pairing keeps the humanist-sans + literary-serif dynamic that gives Anthropic's brand its editorial voice. If we want tighter display weight, swap Inter → Manrope.
4. **No drop shadows.** Anthropic avoids Material-style elevation almost entirely. Use hairline borders and surface-color stepping. Our MD3 `surface-container-*` ramp should drive hierarchy, not `shadow-*`.
5. **Generous radii on pills, modest on cards.** Resist the urge to use `rounded-2xl` everywhere. Cards = `rounded-xl` (12px), buttons = `rounded-lg` (8px), chips/toggles = `rounded-full`.
6. **Dark mode is warm, not cold.** `#131314` has a hint of warmth over true `#000`. Keep dark-mode surfaces warm-tinted — never use pure gray.
7. **Follow-up**: once we have a volunteer with a browser, open DevTools on anthropic.com, inspect `:root`, and dump the computed values of `--swatch--*` and `--_theme---*` to replace the *(inferred)* entries above with literals.

---

## Extracted Computed Values (headless)

**Source**: Playwright (Chromium headless) navigating `https://www.anthropic.com/` and `https://claude.com/` on 2026-04-09, then dumping every `--*` CSS custom property from `getComputedStyle(document.documentElement)` + `body` + `main`. Script: `/tmp/pw-extract/extract.mjs`. Raw JSON: `/tmp/pw-extract/out.json` (127 KB, 282 vars on anthropic.com, 434 on claude.com).

This section **supersedes** the inferred values above where there's a conflict. Values here are literal computed values from the live sites.

### anthropic.com — Swatches (the real brand ramp)

The marketing site exposes its entire palette as `--swatch--*` tokens. These are literal:

| Token | Value | Looks like |
|---|---|---|
| `--swatch--ivory-light` | `#faf9f5` | **Page background (cream/paper)** — this is the real warm neutral |
| `--swatch--ivory-medium` | `#f0eee6` | Secondary background (card wash) |
| `--swatch--ivory-dark` | `#e8e6dc` | Hover surface on secondary bg |
| `--swatch--ivory-faded-10` | `#faf9f51a` | 10% ivory tint (for dark-on-image overlays) |
| `--swatch--ivory-faded-20` | `#faf9f533` | 20% ivory tint |
| `--swatch--slate-dark` | `#141413` | **Primary text + primary button bg** (warm near-black, not `#131314`) |
| `--swatch--slate-medium` | `#3d3d3a` | Hover state for primary button; body-alt text |
| `--swatch--slate-light` | `#5e5d59` | Link hover / muted text |
| `--swatch--slate-faded-10` | `#1414131a` | 10% slate (hairline borders) |
| `--swatch--slate-faded-20` | `#14141333` | 20% slate (border-hover) |
| `--swatch--cloud-light` | `#d1cfc5` | Light cloud gray |
| `--swatch--cloud-medium` | `#b0aea5` | Medium cloud (text-agate) |
| `--swatch--cloud-dark` | `#87867f` | Dark cloud gray |
| `--swatch--clay` | `#d97757` | **Brand orange / primary accent** (matches the inferred value exactly) |
| `--swatch--accent` | `#c6613f` | Deeper brand orange (hover/pressed for clay) |
| `--swatch--kraft` | `#d4a27f` | Warm tan accent |
| `--swatch--manilla` | `#ebdbbc` | Pale yellow-beige |
| `--swatch--oat` | `#e3dacc` | Oat neutral |
| `--swatch--coral` | `#ebcece` | Soft pink accent |
| `--swatch--fig` | `#c46686` | Muted magenta accent |
| `--swatch--heather` | `#cbcadb` | Muted lavender accent |
| `--swatch--sky` | `#6a9bcc` | Muted blue accent |
| `--swatch--cactus` | `#bcd1ca` | Muted sage accent |
| `--swatch--olive` | `#788c5d` | Olive green accent |
| `--swatch--brand-text` | `#141413` | Alias → slate-dark |
| `--swatch--white` | `white` | — |
| `--swatch--transparent` | `transparent` | — |

### anthropic.com — Semantic theme tokens (resolved)

These are derived from the swatches but confirm intent:

| Token | Value |
|---|---|
| `--_color-theme---background` | `#faf9f5` |
| `--_color-theme---background-secondary` | `#f0eee6` |
| `--_color-theme---background-secondary-hover` | `#e8e6dc` |
| `--_color-theme---text` | `#141413` |
| `--_color-theme---text-agate` | `#b0aea5` |
| `--_color-theme---border` | `#1414131a` (10% slate) |
| `--_color-theme---border-hover` | `#14141333` (20% slate) |
| `--_color-theme---card` | `white` |
| `--_color-theme---card-faded` | `#1414131a` |
| `--_color-theme---button-primary--background` | `#141413` |
| `--_color-theme---button-primary--background-hover` | `#3d3d3a` |
| `--_color-theme---button-secondary--background` | `transparent` |
| `--_color-theme---button-secondary--background-hover` | `#141413` |
| `--_color-theme---link--text-hover` | `#5e5d59` |

Computed `background-color` of `<body>`: `rgb(250, 249, 245)` = `#faf9f5`. Confirmed.

### anthropic.com — Fonts (paid fonts resolved)

| Token | Value |
|---|---|
| `--_typography---font--display-sans` | `"Anthropic Sans", Arial, sans-serif` |
| `--_typography---font--display-serif-family` | `"Anthropic Serif", Georgia, sans-serif` |
| `--_typography---font--paragraph-text` | `"Anthropic Serif", Georgia, sans-serif` |
| `--_typography---font--detail` | `"Anthropic Sans", Arial, sans-serif` |
| `--_typography---font--mono` | `"Anthropic Mono", Arial, sans-serif` |

Weight tokens: sans regular 400, medium 500, semibold 600, bold 700. Serif regular 400, semibold 600. Mono regular 400, medium 500.

**Resolved computed `font-family` on live elements:**
- `body` → `"Anthropic Serif", Georgia, sans-serif` @ 20px / 28px line-height / 400
- `h1` → `"Anthropic Sans", Arial, sans-serif` @ 57.7px / 63.5px / 700
- `h2` → `"Anthropic Serif", Georgia, sans-serif` @ 85.6px / 94.1px / 400
- `h3` → `"Anthropic Sans", Arial, sans-serif` @ 16px / 22.4px / 600
- `p`  → `"Anthropic Serif", Georgia, sans-serif` @ 24px / 33.6px / 400
- `button` → `"Anthropic Sans", Arial, sans-serif` @ 16px / 16px / 400

**Key finding on fonts**: Anthropic's three typefaces are **Anthropic Sans, Anthropic Serif, Anthropic Mono** — bespoke custom fonts (not Styrene/Tiempos as folklore suggests, and not Inter/Source Serif). They fall back to `Arial`/`Georgia` respectively. These are **not licensable by us**. The Google Fonts substitutes that track closest:
- **Anthropic Sans → Inter** (both humanist, similar x-height). Manrope also close.
- **Anthropic Serif → Source Serif 4** or **Tinos** (transitional serif, generous counters). Note claude.com uses the serif on h1/h2/h3 — the site is more serif-forward than the marketing site.
- **Anthropic Mono → JetBrains Mono** or **IBM Plex Mono**.

The Inter + Source Serif 4 recommendation above still stands.

### anthropic.com — Spacing & radius (literal)

| Token | Value |
|---|---|
| `--radius--small` | `0.25rem` (4px) |
| `--radius--main` | `0.5rem` (8px) — the default card/button radius |
| `--radius--large` | `1rem` (16px) |
| `--radius--round` | `100vw` (pills) |
| `--border-width--main` | `0.0625rem` (1px) |
| `--_spacing---space--1` | `0.25rem` |
| `--_spacing---space--2` | `0.5rem` |
| `--_spacing---space--3` | `0.75rem` |
| `--_spacing---space--4` | `1rem` |
| `--_spacing---space--5` | `1.5rem` |
| `--_spacing---gap--gap-xs` | `0.5rem` |
| `--_spacing---gap--gap-s` | `1rem` |
| `--_spacing---gap--gap-m` | `1.5rem` |
| `--_spacing---section-space--none` | `0rem` |

Higher space tokens (6+) are fluid `clamp()` expressions that scale with viewport — the site uses responsive spacing.

**Radius revision**: the inferred doc suggested `rounded-xl` (12px) for cards. The real site uses `0.5rem` = 8px as default. Cards, buttons, chips all share that.

### claude.com — Product app tokens

claude.com uses a different system: Tailwind-style HSL component tokens (stored as `H S% L%` strings without `hsl()` wrapper, consumed via `hsl(var(--bg-100))`). 26 color vars total.

| Token | Value | hsl() | Looks like |
|---|---|---|---|
| `--bg-000` | `0 0% 100%` | `#ffffff` | Pure white (cards) |
| `--bg-100` | `48 33.3% 97.1%` | `~#faf9f5` | App background (matches marketing ivory) |
| `--bg-200` | `53 28.6% 94.5%` | `~#f3f1e8` | Raised surface |
| `--bg-300` | `48 25% 92.2%` | `~#ece9dd` | Hover surface |
| `--bg-400` | `50 20.7% 88.6%` | `~#e3dfd1` | Pressed surface |
| `--bg-500` | `50 20.7% 88.6%` | `~#e3dfd1` | (alias of 400) |
| `--border-100..400` | `30 3.3% 11.8%` | `~#1f1e1d` | Hairline borders (all same, vary by opacity) |
| `--text-000`, `--text-100` | `60 2.6% 7.6%` | `~#141413` | Primary text (matches `--swatch--slate-dark`) |
| `--text-200`, `--text-300` | `60 2.5% 23.3%` | `~#3d3d3a` | Secondary text (matches `--swatch--slate-medium`) |
| `--text-400`, `--text-500` | `51 3.1% 43.7%` | `~#726f68` | Muted text |
| `--oncolor-100` | `0 0% 100%` | `#ffffff` | Text on filled/colored surfaces |
| `--oncolor-200`, `--oncolor-300` | `60 6.7% 97.1%` | `~#f8f7f3` | Text on colored surfaces (off-white) |
| `--_brand-clay-emphasized` | `15.1 54.2% 51.2%` | `~#c6613f` | Brand orange (matches `--swatch--accent`) |

claude.com font tokens:
- `--font-anthropic-sans` = `"Anthropic Sans", system-ui, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`
- `--font-anthropic-serif` = `"Anthropic Serif", Georgia, "Times New Roman", serif`
- `--font-anthropic-mono` = `"Anthropic Mono", ui-monospace, monospace`
- `--font-claude-response` = serif (model output is typeset in serif)
- `--font-user-message` = sans (user turns are sans)

**Notable**: On claude.com, `<h1>`/`<h2>`/`<h3>` all compute to **Anthropic Serif**, body computes to **Anthropic Sans**. This is the inverse of the marketing site (where body is serif and h1/h3 are sans). The product is sans-body, serif-display; the marketing site is serif-body, sans-display. If SkillForge is closer in spirit to the product (app UI, data-dense), we should match claude.com: **sans body, serif for hero/display moments only.**

### Final Proposed Mapping (literal where possible)

Replaces the earlier "Observed Palette" section with real values. ✅ = literal from computed CSS, ⚠️ = still inferred.

| Role | Value | Source |
|---|---|---|
| Brand orange (primary) | `#d97757` | ✅ `--swatch--clay` |
| Brand orange (hover/pressed) | `#c6613f` | ✅ `--swatch--accent` |
| Page background (light) | `#faf9f5` | ✅ `--swatch--ivory-light` / `--bg-100` |
| Surface raised | `#f0eee6` | ✅ `--swatch--ivory-medium` |
| Surface hover | `#e8e6dc` | ✅ `--swatch--ivory-dark` |
| Card (pure) | `#ffffff` | ✅ `--_color-theme---card` / `--bg-000` |
| Text primary | `#141413` | ✅ `--swatch--slate-dark` (was inferred as `#1a1a19` — close but wrong) |
| Text secondary | `#3d3d3a` | ✅ `--swatch--slate-medium` |
| Text muted | `#5e5d59` | ✅ `--swatch--slate-light` |
| Text agate (very muted) | `#b0aea5` | ✅ `--swatch--cloud-medium` |
| Border hairline | `#1414131a` (10% slate) | ✅ `--_color-theme---border` |
| Border hover | `#14141333` (20% slate) | ✅ `--_color-theme---border-hover` |
| Dark mode surface | `#141413` | ✅ (reuse slate-dark; was inferred as `#131314`) |
| Success / info / error | tbd | ⚠️ Not exposed in marketing CSS — pick from cactus/sky/fig if we want on-brand |
| Radius small | `4px` (`0.25rem`) | ✅ `--radius--small` |
| Radius default (cards/buttons) | `8px` (`0.5rem`) | ✅ `--radius--main` (was inferred as 12px — too large) |
| Radius large | `16px` (`1rem`) | ✅ `--radius--large` |
| Radius pill | `9999px` / `100vw` | ✅ `--radius--round` |
| Border width | `1px` (`0.0625rem`) | ✅ `--border-width--main` |
| Font — sans (body/UI) | Inter (sub for Anthropic Sans) | ⚠️ paid fonts, substitute |
| Font — serif (display/prose) | Source Serif 4 (sub for Anthropic Serif) | ⚠️ paid fonts, substitute |
| Font — mono | JetBrains Mono (sub for Anthropic Mono) | ⚠️ paid fonts, substitute |
| Body font weight | 400 | ✅ |
| Display font weights | 400, 500, 600, 700 | ✅ |

**Corrections to the earlier inferred doc:**
1. Page background is `#faf9f5`, not `#F5F4EE` (warmer, higher luminance than we guessed).
2. Primary text is `#141413`, not `#1a1a19` or `#131314` — all three are close but `#141413` is the real value. Reuse it for dark-mode surfaces too.
3. Default card/button radius is **8px**, not 12px. Chips remain fully rounded. Large cards use 16px.
4. The paid fonts are called **Anthropic Sans / Serif / Mono** (not Styrene/Tiempos). Our Inter + Source Serif 4 substitution plan is still right, but we should document it as subbing for the Anthropic-branded originals.
5. On claude.com (the product, not marketing), **body is sans and display is serif** — the opposite of the marketing site. SkillForge should follow the product convention.
