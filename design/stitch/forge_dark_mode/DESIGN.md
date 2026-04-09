# Design System Strategy: The Precision Architect

## 1. Overview & Creative North Star
The North Star for this design system is **"The Precision Architect."** 

This isn't just another dark-mode dashboard; it is a high-density, editorial environment built specifically for the developer's mental model. It mirrors the aesthetic of premium tools like Raycast and Linear, where "premium" is defined by mathematical precision, intentional depth, and a complete absence of visual clutter. 

We break the "standard template" look by utilizing wide-scale typographic contrast—pairing massive, geometric display headers with tight, high-density utility mono-fonts. We favor **Tonal Layering** over structural lines, ensuring the UI feels like a single, cohesive piece of hardware rather than a collection of disparate boxes.

---

## 2. Colors & Surface Philosophy
The palette is rooted in deep obsidian tones, punctuated by high-frequency electric accents.

### Color Roles
- **Primary (`#c0c1ff` / `#6366F1`):** Use for active states and critical path actions.
- **Secondary (`#5de6ff` / `#22D3EE`):** Use for telemetry, data visualization, and secondary highlights.
- **Tertiary (`#4edea3`):** Reserved for "Success" and completed build states.
- **Neutral/Surface:** The foundation of the system, moving from `surface-container-lowest` (#0a0e1a) to `surface-bright` (#353946).

### The "No-Line" Rule
**Explicit Instruction:** Do not use 1px solid borders to section off large areas of the UI. Separation must be achieved through:
1.  **Background Shifts:** Placing a `surface-container-low` card on top of a `surface` background.
2.  **Negative Space:** Using the generous 24px padding scale to create "islands" of content.
3.  **Tonal Transitions:** Subtle linear gradients (0% to 5% opacity) to suggest a boundary without a hard line.

### Surface Hierarchy & Nesting
Treat the UI as physical layers of "Synthetic Glass."
- **Base Level:** `surface` (#0f131f).
- **Secondary Level:** `surface-container` (#1b1f2c) for sidebar or navigation regions.
- **Top Level:** `surface-container-highest` (#313442) for floating command palettes or active modals.

### Signature Textures
Every CTA or Hero Section should utilize a **"Glow-Gradient."** Transition from `primary` (#c0c1ff) to `primary-container` (#8083ff) at a 45-degree angle. This adds a "soul" to the interface that flat hex codes cannot replicate.

---

## 3. Typography: Editorial Utility
We pair the brutalist geometry of **Space Grotesk** with the invisible legibility of **Inter** and the technical precision of **JetBrains Mono**.

- **Display-LG (Space Grotesk, 3.5rem):** Used for "Aha!" moments and landing headers. Letter-spacing should be set to -0.02em.
- **Title-MD (Inter, 1.125rem):** The workhorse for card titles and section headers.
- **Label-SM (JetBrains Mono, 0.6875rem):** Use for all metadata, tags, and "developer-facing" details (e.g., timestamps, hash codes). This reinforces the "architect" persona.

**Hierarchy Strategy:** Always maintain at least a 2-step jump in the type scale between a title and its body text to create an editorial, high-end feel.

---

## 4. Elevation & Depth
Depth in this system is achieved via **Light and Blur**, not shadows.

- **The Layering Principle:** Stack `surface-container-lowest` cards on `surface-container-low` sections. The eye perceives the subtle shift in hex code as a physical lift.
- **The "Ghost Border":** If a container requires a border for accessibility (e.g., a code snippet), use the `outline-variant` token at **10% opacity**. It should feel like a suggestion of an edge, not a cage.
- **Glassmorphism:** For floating elements (Command Palettes, Popovers), use `surface-container-highest` with a `backdrop-blur` of 12px and a 1px border of `rgba(255,255,255,0.08)`.
- **Ambient Shadows:** Shadows are forbidden on standard cards. Only use them for the "Highest" elevation level, utilizing a wide 32px blur with 4% opacity, tinted with the `primary` color (#6366F1).

---

## 5. Components

### Buttons
- **Primary:** Gradient fill (`primary` to `primary-container`), 12px (`xl`) roundedness, white text.
- **Secondary:** `surface-container-high` background with a `primary` "Ghost Border."
- **Tertiary/Ghost:** No background. Text in `primary-fixed-dim`. Only shows a `surface-variant` background on hover.

### Inputs & Command Bars
- **Style:** Use `surface-container-lowest` as the fill. 
- **Active State:** Instead of a thick border, use a 1px `primary` border and a soft `primary` outer glow (4px blur, 10% opacity).
- **Font:** Use `JetBrains Mono` for input text to signify data entry.

### Cards & Lists
- **Forbid Dividers:** Do not use lines between list items. Use 12px of vertical padding and a hover state that shifts the background to `surface-container-high`.
- **High-Density:** Information should be packed tight within cards, using `Label-SM` (Mono) for secondary data to keep the footprint small but readable.

### Additional Component: "The Status Glow"
A small (8px) circular dot with a `box-shadow` of the same color (8px spread). Used next to "Success," "Error," or "Warning" text to provide a "hardware LED" feel.

---

## 6. Do’s and Don’ts

### Do
- **Do** use `JetBrains Mono` for any text that feels like data (IDs, dates, counts).
- **Do** lean into asymmetry. Align some headers to the left while keeping metadata right-aligned to break the grid.
- **Do** use `primary-fixed-dim` for "soft" primary actions that shouldn't dominate the screen.

### Don't
- **Don't** use 100% white text. Use `on-surface` (#dfe2f3) to reduce eye strain.
- **Don't** use standard "Drop Shadows." If it doesn't have a backdrop blur, it isn't elevated.
- **Don't** use rounded-sm. Everything in this system is either `xl` (12px) for containers or `full` for chips/pills. Intermediate roundedness breaks the visual language.