/**
 * Design System Theme Configuration
 * Role-specific themes and modern UI tokens
 */

// Role-based color themes
export const roleThemes = {
  legal: {
    primary: 'indigo',
    accent: 'violet',
    gradient: 'from-indigo-600 via-violet-600 to-purple-700',
    lightGradient: 'from-indigo-50 via-violet-50 to-purple-50',
    icon: 'ScaleIcon',
    label: 'Legal Counsel',
  },
  procurement: {
    primary: 'emerald',
    accent: 'teal',
    gradient: 'from-emerald-600 via-teal-600 to-cyan-700',
    lightGradient: 'from-emerald-50 via-teal-50 to-cyan-50',
    icon: 'CurrencyDollarIcon',
    label: 'Procurement',
  },
  admin: {
    primary: 'slate',
    accent: 'blue',
    gradient: 'from-slate-700 via-slate-800 to-slate-900',
    lightGradient: 'from-slate-50 via-gray-50 to-zinc-50',
    icon: 'Cog6ToothIcon',
    label: 'Administrator',
  },
  viewer: {
    primary: 'blue',
    accent: 'sky',
    gradient: 'from-blue-600 via-sky-600 to-cyan-600',
    lightGradient: 'from-blue-50 via-sky-50 to-cyan-50',
    icon: 'EyeIcon',
    label: 'Viewer',
  },
} as const

// Status colors with modern palette
export const statusColors = {
  success: {
    bg: 'bg-emerald-50',
    text: 'text-emerald-700',
    border: 'border-emerald-200',
    icon: 'text-emerald-500',
    dot: 'bg-emerald-500',
  },
  warning: {
    bg: 'bg-amber-50',
    text: 'text-amber-700',
    border: 'border-amber-200',
    icon: 'text-amber-500',
    dot: 'bg-amber-500',
  },
  danger: {
    bg: 'bg-rose-50',
    text: 'text-rose-700',
    border: 'border-rose-200',
    icon: 'text-rose-500',
    dot: 'bg-rose-500',
  },
  info: {
    bg: 'bg-sky-50',
    text: 'text-sky-700',
    border: 'border-sky-200',
    icon: 'text-sky-500',
    dot: 'bg-sky-500',
  },
  neutral: {
    bg: 'bg-slate-50',
    text: 'text-slate-700',
    border: 'border-slate-200',
    icon: 'text-slate-500',
    dot: 'bg-slate-400',
  },
}

// Risk level theming
export const riskThemes = {
  low: {
    gradient: 'from-emerald-400 to-green-500',
    bg: 'bg-gradient-to-r from-emerald-50 to-green-50',
    text: 'text-emerald-700',
    border: 'border-emerald-300',
    glow: 'shadow-emerald-200',
  },
  medium: {
    gradient: 'from-amber-400 to-orange-500',
    bg: 'bg-gradient-to-r from-amber-50 to-orange-50',
    text: 'text-amber-700',
    border: 'border-amber-300',
    glow: 'shadow-amber-200',
  },
  high: {
    gradient: 'from-rose-400 to-red-500',
    bg: 'bg-gradient-to-r from-rose-50 to-red-50',
    text: 'text-rose-700',
    border: 'border-rose-300',
    glow: 'shadow-rose-200',
  },
  critical: {
    gradient: 'from-purple-500 to-violet-600',
    bg: 'bg-gradient-to-r from-purple-50 to-violet-50',
    text: 'text-purple-700',
    border: 'border-purple-300',
    glow: 'shadow-purple-200',
  },
}

// Animation presets
export const animations = {
  fadeIn: 'animate-in fade-in duration-300',
  slideUp: 'animate-in slide-in-from-bottom-4 duration-300',
  slideRight: 'animate-in slide-in-from-left-4 duration-300',
  scaleIn: 'animate-in zoom-in-95 duration-200',
  pulse: 'animate-pulse',
  bounce: 'animate-bounce',
}

// Card styles
export const cardStyles = {
  glass: 'bg-white/70 backdrop-blur-xl border border-white/20 shadow-xl',
  solid: 'bg-white border border-gray-200 shadow-sm',
  elevated: 'bg-white border border-gray-100 shadow-lg shadow-gray-200/50',
  gradient: 'bg-gradient-to-br from-white to-gray-50 border border-gray-200 shadow-md',
}

// Quick action categories per role
export const roleQuickActions = {
  legal: [
    { label: 'Review High Risk', icon: 'ExclamationTriangleIcon', action: '/contracts?risk=high' },
    { label: 'Pending Approvals', icon: 'ClipboardDocumentCheckIcon', action: '/approvals' },
    { label: 'Compare Clauses', icon: 'DocumentDuplicateIcon', action: '/compare' },
    { label: 'Risk Report', icon: 'ChartBarIcon', action: '/reports/risk' },
  ],
  procurement: [
    { label: 'Expiring Contracts', icon: 'ClockIcon', action: '/renewals' },
    { label: 'Vendor Scorecard', icon: 'BuildingOfficeIcon', action: '/vendors' },
    { label: 'Spend Analysis', icon: 'CurrencyDollarIcon', action: '/reports/spend' },
    { label: 'New Contract', icon: 'PlusIcon', action: '/upload' },
  ],
  admin: [
    { label: 'System Health', icon: 'ServerIcon', action: '/admin/scheduler' },
    { label: 'User Management', icon: 'UsersIcon', action: '/users' },
    { label: 'SLA Config', icon: 'Cog6ToothIcon', action: '/admin/sla-config' },
    { label: 'Audit Logs', icon: 'ClipboardDocumentListIcon', action: '/admin/audit' },
  ],
  viewer: [
    { label: 'Browse Contracts', icon: 'DocumentTextIcon', action: '/contracts' },
    { label: 'Ask AI', icon: 'SparklesIcon', action: '/query' },
    { label: 'View Reports', icon: 'ChartBarIcon', action: '/reports' },
    { label: 'Search', icon: 'MagnifyingGlassIcon', action: '/search' },
  ],
}

export type RoleType = keyof typeof roleThemes
export type RiskLevel = keyof typeof riskThemes
export type StatusType = keyof typeof statusColors
