/**
 * Personio-Inspired Design System
 * European minimal with purple accent
 */

export const colors = {
  // Primary - Purple/Violet
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
  },

  // Accent - Pink/Magenta (for highlights)
  accent: {
    light: '#fce7f3',
    DEFAULT: '#ec4899',
    dark: '#be185d',
  },

  // Status colors
  status: {
    active: {
      bg: '#dcfce7',
      text: '#166534',
      border: '#bbf7d0',
    },
    inactive: {
      bg: '#f3f4f6',
      text: '#6b7280',
      border: '#e5e7eb',
    },
    pending: {
      bg: '#fef3c7',
      text: '#92400e',
      border: '#fde68a',
    },
    breached: {
      bg: '#fee2e2',
      text: '#991b1b',
      border: '#fecaca',
    },
  },

  // Chart colors (pastel)
  chart: {
    purple: '#a78bfa',
    pink: '#f472b6',
    blue: '#60a5fa',
    green: '#4ade80',
    yellow: '#facc15',
    orange: '#fb923c',
  },
}

export const shadows = {
  card: '0 1px 3px 0 rgb(0 0 0 / 0.05), 0 1px 2px -1px rgb(0 0 0 / 0.05)',
  cardHover: '0 4px 6px -1px rgb(0 0 0 / 0.07), 0 2px 4px -2px rgb(0 0 0 / 0.05)',
  dropdown: '0 10px 15px -3px rgb(0 0 0 / 0.08), 0 4px 6px -4px rgb(0 0 0 / 0.05)',
}

export const borderRadius = {
  sm: '6px',
  md: '8px',
  lg: '12px',
  xl: '16px',
  full: '9999px',
}

// Button variants
export const buttonStyles = {
  primary: 'bg-violet-600 hover:bg-violet-700 text-white shadow-sm',
  secondary: 'bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 shadow-sm',
  ghost: 'hover:bg-gray-100 text-gray-700',
  danger: 'bg-red-600 hover:bg-red-700 text-white shadow-sm',
}

// Badge variants
export const badgeStyles = {
  active: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  inactive: 'bg-gray-100 text-gray-600 border-gray-200',
  pending: 'bg-amber-100 text-amber-700 border-amber-200',
  breached: 'bg-red-100 text-red-700 border-red-200',
  internal: 'bg-gray-100 text-gray-600 border-gray-200',
  new: 'bg-violet-100 text-violet-700 border-violet-200',
}
