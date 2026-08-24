/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Primary brand colors — driven by CSS variables (see index.css :root).
        // Direction B: violet scale.
        primary: {
          50:  'var(--color-primary-50)',
          100: 'var(--color-primary-100)',
          200: 'var(--color-primary-200)',
          300: 'var(--color-primary-300)',
          400: 'var(--color-primary-400)',
          500: 'var(--color-primary-500)',
          600: 'var(--color-primary-600)',
          700: 'var(--color-primary-700)',
          800: 'var(--color-primary-800)',
          900: 'var(--color-primary-900)',
          950: 'var(--color-primary-950)',
        },
        // Semantic tokens from the Direction B token sheet (dark-mode aware)
        ok: { DEFAULT: 'var(--ok)', faint: 'var(--ok-f)', border: 'var(--ok-b)' },
        wa: { DEFAULT: 'var(--wa)', faint: 'var(--wa-f)', border: 'var(--wa-b)' },
        da: { DEFAULT: 'var(--da)', faint: 'var(--da-f)', border: 'var(--da-b)' },
        info: { DEFAULT: 'var(--in)', faint: 'var(--in-f)', border: 'var(--in-b)' },
        // Risk level colors from PRD
        risk: {
          low: '#10B981',      // Green
          medium: '#F59E0B',   // Amber
          high: '#DC2626',     // Red
          critical: '#7C3AED', // Purple
        },
        // Status colors
        status: {
          pending: '#6B7280',    // Gray
          processing: '#3B82F6', // Blue
          completed: '#10B981',  // Green
          failed: '#DC2626',     // Red
        },
      },
      fontFamily: {
        sans: ['Instrument Sans Variable', 'Instrument Sans', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}
