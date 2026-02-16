/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Primary brand colors - Violet (Personio-style)
        primary: {
          50: '#f5f3ff',
          100: '#ede9fe',
          200: '#ddd6fe',
          300: '#c4b5fd',
          400: '#a78bfa',
          500: '#8b5cf6',
          600: '#7c3aed',
          700: '#6d28d9',
          800: '#5b21b6',
          900: '#4c1d95',
          950: '#2e1065',
        },
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
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}
