# SkillForge Design

This directory holds all UI/UX design artifacts for the SkillForge frontend dashboard: wireframes, mockups, component states, color palettes, typography choices, and any reference material that should guide implementation in Step 10.

## What goes here

- **Wireframes** — rough layouts of the main dashboard, breeding report, lineage tree, etc.
- **High-fidelity mockups** — Figma exports, screenshots, or any pixel-accurate reference
- **Component state sketches** — the four competitor card states (writing / testing / iterating / done / error), empty states, error states, loading states
- **Color palette** — hex values, dark mode vs light mode, semantic colors (success / warning / error / info)
- **Typography** — font choices, scale, weights
- **Reference URLs or screenshots** — "make it look like X" north stars
- **Interaction notes** — how WebSocket events animate in, what happens on disconnect, scroll behavior

## File naming

Free-form, but prefer descriptive names:

```
design/
├── README.md
├── principles.md              (optional — design philosophy + rules)
├── palette.md                 (colors + typography + spacing tokens)
├── wireframes/
│   ├── 01-dashboard-idle.png
│   ├── 02-dashboard-running.png
│   ├── 03-breeding-report.png
│   └── ...
├── mockups/
│   └── *.png / *.fig
└── references/
    └── *.png (screenshots of inspiration)
```

## Who uses this

**Step 10 (Frontend) is the primary consumer.** When implementing the React components, the Sonnet subagent (or Opus directly) reads this directory the same way Step 4 reads `SCHEMA.md` — as the source of truth for what the UI should look like.

Before Step 10 starts, this directory should contain **at minimum**:

1. A dashboard wireframe showing layout of input form + competitor grid + fitness chart + breeding report
2. Competitor card states (writing / testing / iterating / done / error)
3. Color + typography direction (even just "dark mode, monospace accents, Bloomberg-terminal density")
4. Empty and error states (no runs yet, connection lost)

## Design principles to honor (derived from the project's nature)

These are suggestions, not rules — override freely in `principles.md`:

- **Real-time clarity**: this is a live tournament. State changes should be obvious at a glance.
- **Information density > chrome**: users watching an evolution want to see scores, traces, and reasoning. Minimize decorative padding.
- **Diagnostic reasoning visible**: the Breeder's reasoning and the Judge's trait attribution are the interesting parts — don't bury them in modals.
- **Graceful disconnects**: WebSockets drop. The UI should recover, not hang.
- **Respect the terminal aesthetic**: users are developers running Claude Code. Cozy IDE vibes work better than SaaS marketing vibes.

## Current status

*Empty. Matt is designing. This file is a landing pad.*
