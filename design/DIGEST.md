# SkillForge Design Digest

Condensed reference for the Step 10 frontend implementation. Full design
system lives in `stitch/forge_dark_mode/DESIGN.md`. Source screens + HTML in
`stitch/<screen>/`. This file is the **implementation contract** — what must
be built and how it must look.

## Design System Summary ("The Precision Architect")

**Aesthetic**: dark-mode editorial/developer environment, Raycast/Linear premium, Bloomberg-terminal density.

**Colors** (from `DESIGN.md`):
| Token | Hex | Use |
|---|---|---|
| `primary` | `#c0c1ff` | Active states, critical-path actions |
| `primary-container` | `#8083ff` | Gradient endpoint (paired with primary at 45°) |
| `secondary` | `#5de6ff` / `#22D3EE` | Telemetry, data viz, highlights |
| `tertiary` | `#4edea3` | Success, completed builds |
| `on-surface` | `#dfe2f3` | Body text (never use 100% white) |
| `surface` | `#0f131f` | Base level |
| `surface-container-lowest` | `#0a0e1a` | Input/command-bar fill |
| `surface-container-low` | — | Card backgrounds on `surface` base |
| `surface-container` | `#1b1f2c` | Sidebar/nav regions |
| `surface-container-high` | — | Secondary button background |
| `surface-container-highest` | `#313442` | Floating modals/command palettes |
| `surface-bright` | `#353946` | Brightest utility surface |

**Typography**:
- **Display-LG** `Space Grotesk 3.5rem letter-spacing:-0.02em` — hero headers only
- **Title-MD** `Inter 1.125rem` — card titles, section headers
- **Body** `Inter` — prose
- **Label-SM** `JetBrains Mono 0.6875rem` — all metadata, timestamps, IDs, hashes, stats

**Rules (non-negotiable)**:
1. **No 1px borders to section areas**. Separate via background shifts, 24px negative space, or tonal gradients.
2. **No drop shadows** on standard cards. Only "highest" elevation uses 32px blur, 4% opacity, primary-tinted.
3. **No `rounded-sm`**. Containers → `xl` (12px); chips/pills → `full`.
4. **No 100% white text** — use `#dfe2f3`.
5. **Gradient CTAs**: primary → primary-container at 45°.
6. **Status Glow**: 8px circular dot with 8px box-shadow spread in the same color (hardware LED feel).
7. **Glassmorphism** for floating elements: `surface-container-highest` + `backdrop-blur:12px` + `1px border rgba(255,255,255,0.08)`.
8. **No list-item dividers**. 12px vertical padding + hover shifts background to `surface-container-high`.
9. **Left-right asymmetry** permitted — headers left, metadata right-aligned, break the grid intentionally.

## Screens — MVP Scope

### 1. `skillforge_dashboard` — Home / Landing

**Purpose**: landing page. Hero CTA ("Start Evolution"), Recent Evolutions carousel, macro stats.

**Layout** (top to bottom):
- Top nav: logo "SkillForge" (left), "Dashboard / Registry / Bible" center, "+ New Evolution" primary button right
- Hero card (full width, dark `surface-container-low` background, subtle radial glow):
  - Display-LG "Evolve Agent Skills Through Natural Selection" with "Natural Selection" in secondary color accent
  - Body copy subtitle
  - Primary gradient CTA "Start Evolution →"
  - Decorative DNA/helix visualization on the right
- "Recent Evolutions" section header (left) + "View Registry ↗" link (right)
- 3-card carousel:
  - Each card: state pill (green "Complete" / blue "Running" / red "Failed"), title, hash ID (mono), "Fitness Score" + numeric value + arrow trend, "Generation N" tag, horizontal bar chart showing fitness-over-generations
- Footer stats row (3 stat cards): "Total Agents: 47 Skills Evolved", "Selection Efficiency: +34% Avg Fitness Gain", "Knowledge Base: 23 Bible Entries"

**Components needed**: `AppShell`, `TopNav`, `HeroSection`, `EvolutionCard`, `StatCard`.

### 2. `new_evolution_form` — Start Evolution

**Purpose**: form to POST `/evolve`.

**Layout**:
- Top nav (same as dashboard)
- Display-LG "New Evolution Run" with mono sub-label "PROJECT ALPHA // EXECUTION MODE R42"
- Two large mode-selection cards side by side (radio-style, one selected with primary border glow):
  - "Domain Mode" (icon + title + description + selected checkmark)
  - "Meta Mode" (v1.1 — show as disabled/"Coming soon" for MVP)
- "SPECIALIZATION BLUEPRINT" section header (mono label)
- Multi-line textarea styled as code input (`surface-container-lowest` fill, mono font, "e.g., Optimizing Elixir OTP supervision trees..." placeholder)
- Right-side small "Markdown Supported" hint
- Three parameter inputs horizontally: "POPULATION SIZE" (numeric, default 5), "GENERATIONS" (numeric, default 3), "BUDGET CAP" (numeric with "$" prefix, default $10.00 in tertiary/green color)
- "Advanced Parameters" collapsible row with chevron
- Footer: estimated compute time ("EST. COMPUTE TIME: ~12 min"), estimated compute cost ("EST. COMPUTE COST: ~$4.20"), primary CTA "Start Evolution ✈"

**Components needed**: `ModeCard`, `CodeInputArea`, `ParameterInput`, `PrimaryButton` (gradient).

### 3. `evolution_generation_in_progress` — Live Tournament (the most important screen)

**Purpose**: real-time competitor tournament view. This is the WebSocket-driven screen where SkillForge's value is most visible.

**Layout**:
- **Left sidebar** (~240px, `surface-container` bg):
  - "Project Evolve / Active Generation: N" header card with icon
  - Vertical nav: "Evolution Arena" (active), "Breeding Reports", "Gen Stats", "Learning Log", "Terminal"
  - Bottom: "+ New Experiment" button + "Settings" + "Docs" links
- **Main area** (center):
  - Breadcrumbs: "DASHBOARD > RUN HX3FD... > GENERATION 2 OF 3"
  - Display header "Evolution Cycle" with "RUNNING" green status pill
  - Top-right metadata: "ELAPSED TIME: 4:23" and "BUDGET USED: $2.81 / $10.00"
  - **Competitor Arena card** (dominant element):
    - Section header "Competitor Arena" with "ACTIVE POOL: N5 AGENTS" mono label right
    - List of competitor rows (one per skill):
      - Icon (circle with state color: green ✓ done, blue spinner running, amber testing, gray queued)
      - Name "Competitor Alpha" + subtitle "Build a GenServer rate limiter"
      - Right-aligned state text: "DONE ✓" / "WRITING CODE..." / "RUNNING TESTS..." / "IN QUEUE"
      - Background: `surface-container-low`, hover shifts to `surface-container-high`
  - **Live Feed Log** at bottom (terminal-style card, full width):
    - Header "LIVE FEED LOG" with "0 Errors / 14 Warnings" right
    - Mono timestamped lines: `[12:04:31] SYSTEM: ...`, `[12:04:34] ALPHA: ...`, color-coded by actor (SYSTEM=secondary, per-competitor=primary variants, JUDGE=tertiary)
- **Right sidebar** (~320px):
  - "Generation Stats" card: mini line chart (best + avg fitness), numeric readouts "PEAK FITNESS: 0.78", "AVERAGE MEAN: 0.61"
  - "Judging Pipeline" card: grid of 6 pill-chips representing L1-L6 status (e.g., "L1: SYNTAX ✓", "L2: LOGIC", "L3: CONCURRENCY", "L4: MEMORY", "L5: EFFICIENCY", "L6: SCALING")
  - "Node Cluster Active" card: "4/4 Nodes Healthy — 12.4ms Latency" with secondary-colored icon

**WebSocket bindings**:
- `generation_started` → update breadcrumbs + header
- `competitor_started` → competitor row appears with "writing" state
- `competitor_progress` → state text updates
- `judging_layer{N}_complete` → judging pipeline chip flips to ✓
- `scores_published` → generation stats chart updates
- `cost_update` → budget used counter ticks
- `generation_complete` → transition to breeding phase view

**Components needed**: `Sidebar`, `Breadcrumbs`, `CompetitorRow`, `CompetitorIcon`, `LiveFeedLog`, `MiniLineChart`, `JudgingPipelinePill`, `StatReadout`.

### 4. `evolution_breeding_phase` — Between Generations

**Purpose**: show the Breeder's reflective reasoning and learning log updates between generations.

**Layout**:
- Same sidebar as #3
- Main area:
  - Display header "Breeding Report / GENEALOGY MAPPING PHASE" + "ANALYSIS ACTIVE" status pill
  - **Genealogy card**:
    - Top row: 2-3 parent cards with icon, name ("Alpha Score 0.88"), score value
    - Arrow down
    - Bottom row: child cards labeled with mutation type ("Alpha-2: Elision", "Gamma: Crossover", "Delta-2: Mutation", "Wildcard: Anomaly")
  - **Breeder's Reasoning** card:
    - Quote icon
    - Multi-line prose block explaining the breeding decisions with key phrases highlighted in accent colors
    - Tag chips at bottom: "#INSTRUCTIONCOMPLIANCE", "#TRAITDIVERGENCE"
- Right sidebar:
  - **Fitness Progression** bar chart (gen-over-gen comparison)
  - **Learning Log: G2.BETA** card: 3 bullet points of new lessons this generation, key phrases linked/highlighted (e.g., "Imperative phrasing followed 2.1x more consistently than previous baseline.")
- Terminal log at bottom (same style as #3) showing the breeding process

**Components needed**: `GenealogyTree`, `BreederReasoningCard`, `LearningLogEntry`, `FitnessProgressionBar`.

### 5. `evolution_complete_results` — Final Results

**Purpose**: end-of-run summary, winning skill card, export options.

**Layout**:
- Display header "Evolution Complete" (with mono sub-label "PROTOCOL: FORKLESS") + large "0.94 / Elixir LiveView Specialist" fitness callout right
- Central code preview card showing the evolved SKILL.md content (mono, `surface-container-lowest` bg) + "Quick Start" section
- Right sidebar:
  - **Fitness Radar** — pentagon radar chart (5 axes: correctness, efficiency, robustness, etc.)
  - **Growth Curve** — bar chart over generations
  - "Export Build ↓" and "Export Config ↓" buttons
  - "Publish to Registry ✓" primary CTA
  - "Fork & Evolve Further" secondary button
- Bottom: **Winning Lineage** horizontal timeline showing the genealogy from gen 0 to winner

**Components needed**: `FitnessRadar` (recharts `RadarChart`), `GrowthCurve`, `CodePreview`, `ExportActions`, `LineageTimeline`.

## Screens — v1.1 Scope (stub for MVP, implement later)

### 6. `skills_bible_unified` — The Bible

Pattern-browser view. Left sidebar with pattern categories (Descriptions, Instructions, Structural...). Main area: pattern title + "Evidence Summary" + inefficient-vs-optimized code comparison cards + "Why it works" explanation + "Architect Tip" callout. Right: "+23% TRIGGER ACCURACY" stat with status indicator.

**MVP**: stub component, link to view that just lists patterns as plain markdown files.

### 7. `agent_registry_skill_marketplace` — Registry

Grid of evolved skills with fitness radar preview, filter tabs (All/Elixir/Python/Testing/Security/API Design), search, sort. Featured skill highlight at top. Install + Fork buttons per card.

**MVP**: stub component.

### 8. `skill_export_preview` — Export Panel

Three large cards: "Skill Directory" (file tree preview + Download.zip), "Agent SDK Config" (JSON preview + Copy JSON), "Deployment" (terminal commands + target selector). Bible Preview panel at bottom with "Publish to Bible" CTA.

**MVP**: the Export screen is actually MVP-scope (Step 9 backend + Step 10 frontend). Build the three-card layout. Export engine is Step 9.

## Implementation Mapping

| Design screen | MVP? | Route | Components (files to implement in Step 10) |
|---|---|---|---|
| skillforge_dashboard | Yes | `/` | `EvolutionDashboard.tsx` (home), `HeroSection`, `EvolutionCard`, `StatCard` |
| new_evolution_form | Yes | `/new` (or modal) | `SpecializationInput.tsx`, `ModeCard`, `ParameterInput` |
| evolution_generation_in_progress | **Yes, critical** | `/runs/:id` | `EvolutionArena.tsx`, `CompetitorRow`, `LiveFeedLog`, `JudgingPipelinePill`, `Sidebar` |
| evolution_breeding_phase | Yes | `/runs/:id` (phase state) | `BreedingReport.tsx`, `GenealogyTree`, `LearningLogEntry` |
| evolution_complete_results | Yes | `/runs/:id` (complete state) | `EvolutionResults.tsx`, `FitnessRadar`, `CodePreview`, `ExportActions`, `LineageTimeline` |
| skill_export_preview | Yes | `/runs/:id/export` | `SkillExportPreview.tsx` |
| skills_bible_unified | Stub v1.1 | `/bible` | empty stub |
| agent_registry_skill_marketplace | Stub v1.1 | `/registry` | empty stub |

## Global Layout Elements

- **AppShell**: top nav (logo left, Dashboard/Registry/Bible center, "New Evolution" CTA right), sidebar on run-detail pages only
- **Router**: `react-router-dom` (add to deps in Step 10)
- **Sidebar**: only appears on `/runs/:id` routes, contains navigation between Evolution Arena / Breeding Reports / Gen Stats / Learning Log / Terminal sub-views
- **WebSocket connection status indicator**: subtle dot in the top-right status area (green=connected, amber=reconnecting, red=disconnected)

## Tailwind Token Mapping

Step 10 should extend `tailwind.config.js` with the Precision Architect tokens:

```js
theme: {
  extend: {
    colors: {
      primary: { DEFAULT: '#c0c1ff', container: '#8083ff', fixed: { dim: '#a5a7ff' } },
      secondary: { DEFAULT: '#5de6ff', alt: '#22D3EE' },
      tertiary: '#4edea3',
      surface: {
        DEFAULT: '#0f131f',
        'container-lowest': '#0a0e1a',
        'container-low': '#161a26',
        container: '#1b1f2c',
        'container-high': '#252938',
        'container-highest': '#313442',
        bright: '#353946',
      },
      'on-surface': '#dfe2f3',
      'outline-variant': 'rgba(255,255,255,0.08)',
    },
    fontFamily: {
      display: ['Space Grotesk', 'sans-serif'],
      sans: ['Inter', 'sans-serif'],
      mono: ['JetBrains Mono', 'monospace'],
    },
    borderRadius: { xl: '12px' },
    boxShadow: {
      glow: '0 0 8px currentColor',
      elevated: '0 32px 64px rgba(99,102,241,0.04)',
    },
    backgroundImage: {
      'primary-gradient': 'linear-gradient(45deg, #c0c1ff 0%, #8083ff 100%)',
    },
  },
}
```

Fonts loaded via Google Fonts `<link>` in `index.html` (Space Grotesk + Inter + JetBrains Mono).

## Stitch HTML Reference

Each `design/stitch/<screen>/code.html` is the Stitch-generated markup. It's a
useful starting point for Tailwind class choices but **not a drop-in component**
— it uses a different class taxonomy and isn't React. The subagent implementing
Step 10 should read the HTML to understand layout intent but write fresh React
components using the Tailwind tokens above.
