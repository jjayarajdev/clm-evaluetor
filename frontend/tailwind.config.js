/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Primary brand colors
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
          950: '#172554',
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
