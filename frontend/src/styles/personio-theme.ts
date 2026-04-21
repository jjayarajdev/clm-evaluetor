/**
 * Coast Design System
 * Sophisticated coastal palette built around #5A687D
 */

export const colors = {
  // Primary — Coast slate blue-gray (matches CSS variables in index.css)
  primary: {
    50: '#F4F6F8',
    100: '#E8ECF1',
    200: '#D1D9E2',
    300: '#B0BCC9',
    400: '#8A9AAD',
    500: '#6B7D91',
    600: '#5A687D',
    700: '#49576A',
    800: '#3D4A5C',
    900: '#2C3847',
  },

  // Accent — Warm sandy gold & sea foam teal
  accent: {
    light: '#F5E6D3',
    DEFAULT: '#C4956A',
    dark: '#9A7048',
    teal: '#6B9E9B',
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
  primary: 'bg-primary-600 hover:bg-primary-700 text-white shadow-sm',
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
  new: 'bg-primary-100 text-primary-700 border-primary-200',
}
