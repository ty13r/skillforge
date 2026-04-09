/** @type {import('tailwindcss').Config} */
//
// Anthropic-inspired palette, extracted from anthropic.com + claude.com via
// headless Chromium on 2026-04-09. Colors are defined as CSS custom properties
// in `src/index.css` so the theme toggle (light/dark/system) can swap them
// without touching Tailwind classes.
//
// Every color below is referenced as `rgb(var(--color-xxx) / <alpha-value>)`
// which preserves the `primary/20` alpha syntax across the whole app.
//
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "rgb(var(--color-primary) / <alpha-value>)",
          container: "rgb(var(--color-primary-container) / <alpha-value>)",
          "fixed-dim": "rgb(var(--color-primary-hover) / <alpha-value>)",
        },
        secondary: {
          DEFAULT: "rgb(var(--color-secondary) / <alpha-value>)",
          alt: "rgb(var(--color-secondary-alt) / <alpha-value>)",
        },
        tertiary: "rgb(var(--color-tertiary) / <alpha-value>)",
        warning: "rgb(var(--color-warning) / <alpha-value>)",
        error: "rgb(var(--color-error) / <alpha-value>)",
        success: "rgb(var(--color-tertiary) / <alpha-value>)",
        surface: {
          DEFAULT: "rgb(var(--color-surface) / <alpha-value>)",
          "container-lowest": "rgb(var(--color-surface-lowest) / <alpha-value>)",
          "container-low": "rgb(var(--color-surface-low) / <alpha-value>)",
          container: "rgb(var(--color-surface-mid) / <alpha-value>)",
          "container-high": "rgb(var(--color-surface-high) / <alpha-value>)",
          "container-highest": "rgb(var(--color-surface-highest) / <alpha-value>)",
          bright: "rgb(var(--color-surface-bright) / <alpha-value>)",
        },
        "on-surface": "rgb(var(--color-on-surface) / <alpha-value>)",
        "on-surface-dim": "rgb(var(--color-on-surface-dim) / <alpha-value>)",
        outline: "rgb(var(--color-outline) / <alpha-value>)",
        "outline-variant": "rgb(var(--color-outline-variant) / <alpha-value>)",
      },
      fontFamily: {
        // Product-app convention (claude.com): sans body, serif display.
        // Anthropic's real typefaces are custom (Anthropic Sans/Serif/Mono);
        // these are the closest free Google Fonts substitutes.
        display: ['"Source Serif 4"', "Georgia", "serif"],
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      borderRadius: {
        // Anthropic default is 8px (--radius--main). Override `xl` so existing
        // `rounded-xl` usage gets the Anthropic look automatically. Large cards
        // keep `rounded-2xl` (16px = --radius--large).
        xl: "0.5rem",
      },
      boxShadow: {
        glow: "0 0 8px currentColor",
        "glow-lg": "0 0 16px currentColor",
        // Anthropic avoids heavy drop shadows — keep this subtle, warm-tinted.
        elevated:
          "0 1px 2px rgba(20,20,19,0.04), 0 4px 12px rgba(20,20,19,0.06)",
      },
      backgroundImage: {
        "primary-gradient":
          "linear-gradient(45deg, rgb(var(--color-primary)) 0%, rgb(var(--color-primary-hover)) 100%)",
        "hero-radial":
          "radial-gradient(ellipse at top right, rgb(var(--color-primary) / 0.35), rgb(var(--color-primary) / 0.08) 40%, transparent 70%)",
        "shimmer-stripe":
          "linear-gradient(110deg, transparent 30%, rgb(var(--color-on-surface) / 0.08) 50%, transparent 70%)",
      },
      keyframes: {
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 8px currentColor", opacity: "1" },
          "50%": { boxShadow: "0 0 18px currentColor", opacity: "0.85" },
        },
        "slide-in-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "breathe-border": {
          "0%, 100%": { borderColor: "rgb(var(--color-primary) / 0.4)" },
          "50%": { borderColor: "rgb(var(--color-primary) / 0.9)" },
        },
      },
      animation: {
        "pulse-glow": "pulse-glow 1.6s ease-in-out infinite",
        "slide-in-up": "slide-in-up 0.25s ease-out",
        shimmer: "shimmer 2s linear infinite",
        "breathe-border": "breathe-border 2s ease-in-out infinite",
      },
      transitionTimingFunction: {
        // Anthropic's default expand easing (literal from claude.com)
        "expo-out": "cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
};
