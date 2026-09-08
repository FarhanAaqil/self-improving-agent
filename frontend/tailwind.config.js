/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      colors: {
        canvas: '#F6F7F9',
        surface: {
          DEFAULT: '#FFFFFF',
          sunken: '#EEF0F3',
        },
        ink: {
          DEFAULT: '#10182B',
          secondary: '#4A5468',
          tertiary: '#8891A3',
        },
        accent: {
          DEFAULT: '#2E4CE0',
          hover: '#2440C4',
          subtle: '#E8ECFC',
        },
        status: {
          success: '#1A7F5A',
          'success-subtle': '#E4F5EE',
          warning: '#B7791F',
          'warning-subtle': '#FBF0DE',
          danger: '#C4432E',
          'danger-subtle': '#FBEAE6',
        },
        border: {
          DEFAULT: '#E1E4EA',
          strong: '#C7CCD6',
        },
      },
      borderRadius: {
        DEFAULT: '4px',
        sm: '2px',
        md: '4px',
        lg: '4px',
        xl: '4px',
      },
    },
  },
  plugins: [],
}
