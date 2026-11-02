/** @type {import('tailwindcss').Config} */

// Every color is a CSS variable (RGB triplet) so the light ledger and the dark
// "night shift" theme share one set of class names. Values live in src/index.css.
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      colors: {
        canvas: token('canvas'),
        surface: {
          DEFAULT: token('surface'),
          sunken: token('surface-sunken'),
          raised: token('surface-raised'),
        },
        ink: {
          DEFAULT: token('ink'),
          secondary: token('ink-secondary'),
          muted: token('ink-muted'),
          tertiary: token('ink-tertiary'),
          inverse: token('ink-inverse'),
        },
        accent: {
          DEFAULT: token('accent'),
          hover: token('accent-hover'),
          subtle: token('accent-subtle'),
          ink: token('accent-ink'),
        },
        cyan: {
          DEFAULT: token('cyan'),
          hover: token('cyan-hover'),
          subtle: token('cyan-subtle'),
        },
        status: {
          success: token('success'),
          'success-subtle': token('success-subtle'),
          warning: token('warning'),
          'warning-subtle': token('warning-subtle'),
          danger: token('danger'),
          'danger-subtle': token('danger-subtle'),
        },
        border: {
          DEFAULT: token('border'),
          strong: token('border-strong'),
        },
        chart: {
          1: token('chart-1'),
          2: token('chart-2'),
          grid: token('chart-grid'),
        },
      },
      borderRadius: {
        DEFAULT: '0px',
        none: '0px',
        sm: '0px',
        md: '0px',
        lg: '0px',
        xl: '0px',
        '2xl': '0px',
        full: '9999px',
      },
      boxShadow: {
        ledger: '4px 4px 0 0 rgb(var(--ink) / 0.08)',
        'ledger-accent': '4px 4px 0 0 rgb(var(--accent) / 0.25)',
      },
      keyframes: {
        'stamp-in': {
          '0%': { transform: 'scale(2.2) rotate(-14deg)', opacity: '0' },
          '60%': { transform: 'scale(0.92) rotate(-8deg)', opacity: '1' },
          '100%': { transform: 'scale(1) rotate(-8deg)', opacity: '1' },
        },
        'rise-in': {
          from: { transform: 'translateY(8px)', opacity: '0' },
          to: { transform: 'translateY(0)', opacity: '1' },
        },
        scan: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(400%)' },
        },
        breathe: {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.55', transform: 'scale(0.96)' },
        },
        nudge: {
          '0%, 100%': { transform: 'translateX(0)' },
          '25%': { transform: 'translateX(-3px)' },
          '75%': { transform: 'translateX(3px)' },
        },
        caret: {
          '0%, 49%': { opacity: '1' },
          '50%, 100%': { opacity: '0' },
        },
      },
      animation: {
        'stamp-in': 'stamp-in 0.55s cubic-bezier(0.2, 0.9, 0.3, 1.2) both',
        'rise-in': 'rise-in 0.28s ease-out both',
        scan: 'scan 1.8s linear infinite',
        breathe: 'breathe 1.6s ease-in-out infinite',
        nudge: 'nudge 0.3s ease-in-out 2',
        caret: 'caret 1s steps(1) infinite',
      },
    },
  },
  plugins: [],
}
