/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: '#c0c1ff', container: '#8083ff', 'fixed-dim': '#a5a7ff' },
        secondary: { DEFAULT: '#5de6ff', alt: '#22D3EE' },
        tertiary: '#4edea3',
        warning: '#f7b955',
        error: '#ef4444',
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
        'on-surface-dim': '#9ba0b8',
        'outline-variant': 'rgba(255,255,255,0.08)',
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        sans: ['Inter', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      borderRadius: { xl: '12px' },
      boxShadow: {
        glow: '0 0 8px currentColor',
        'glow-lg': '0 0 16px currentColor',
        elevated: '0 32px 64px rgba(99,102,241,0.04)',
      },
      backgroundImage: {
        'primary-gradient': 'linear-gradient(45deg, #c0c1ff 0%, #8083ff 100%)',
        'hero-radial': 'radial-gradient(ellipse at top right, rgba(192,193,255,0.15), transparent 60%)',
        'shimmer-stripe': 'linear-gradient(110deg, transparent 30%, rgba(255,255,255,0.08) 50%, transparent 70%)',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 8px currentColor', opacity: '1' },
          '50%': { boxShadow: '0 0 18px currentColor', opacity: '0.85' },
        },
        'slide-in-up': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'breathe-border': {
          '0%, 100%': { borderColor: 'rgba(192,193,255,0.4)' },
          '50%': { borderColor: 'rgba(192,193,255,0.9)' },
        },
      },
      animation: {
        'pulse-glow': 'pulse-glow 1.6s ease-in-out infinite',
        'slide-in-up': 'slide-in-up 0.25s ease-out',
        shimmer: 'shimmer 2s linear infinite',
        'breathe-border': 'breathe-border 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
