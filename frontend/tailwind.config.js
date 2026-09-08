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
        mono: ['"JetBrains Mono"', '"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      colors: {
        canvas: '#F0F3EF',
        surface: {
          DEFAULT: '#FFFFFF',
          sunken: '#E4E9E2',
        },
        ink: {
          DEFAULT: '#10241C',
          secondary: '#52655A',
          tertiary: '#93A399',
        },
        accent: {
          DEFAULT: '#FF5A1F',
          hover: '#E44E17',
          subtle: '#FFE8DC',
        },
        cyan: {
          DEFAULT: '#0E7C86',
          hover: '#0A5C64',
          subtle: '#E0F3F5',
        },
        status: {
          success: '#1F7A4D',
          'success-subtle': '#DFF1E4',
          warning: '#B5790A',
          'warning-subtle': '#FBEED6',
          danger: '#C43B2A',
          'danger-subtle': '#FBE4DF',
        },
        border: {
          DEFAULT: '#CBD3C7',
          strong: '#9FAD9A',
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
        full: '0px',
      },
    },
  },
  plugins: [],
}
