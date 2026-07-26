import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import i18n from '@/i18n'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

function currentLocale(): string {
  return i18n.language?.startsWith('fr') ? 'fr-FR' : 'en-US'
}

export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleDateString(currentLocale(), {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function formatDateTime(dateString: string | null | undefined): string {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString(currentLocale(), {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatCurrency(value: number | null | undefined, currency = 'USD'): string {
  if (value == null) return '-'
  return new Intl.NumberFormat(currentLocale(), {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

export function formatNumber(value: number | null | undefined): string {
  if (value == null) return '-'
  return new Intl.NumberFormat(currentLocale()).format(value)
}

export function formatFileSize(bytes: number | null | undefined): string {
  if (bytes == null) return '-'
  const units = ['B', 'KB', 'MB', 'GB']
  let unitIndex = 0
  let size = bytes

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }

  return `${size.toFixed(1)} ${units[unitIndex]}`
}

export function getRiskColor(level: string | null | undefined): string {
  switch (level?.toLowerCase()) {
    case 'low':
      return 'text-risk-low bg-green-50'
    case 'medium':
      return 'text-risk-medium bg-amber-50'
    case 'high':
      return 'text-risk-high bg-red-50'
    case 'critical':
      return 'text-risk-critical bg-purple-50'
    default:
      return 'text-gray-500 bg-gray-50'
  }
}

export function getStatusColor(status: string | null | undefined): string {
  switch (status?.toLowerCase()) {
    case 'pending':
      return 'text-status-pending bg-gray-50'
    case 'processing':
      return 'text-status-processing bg-blue-50'
    case 'completed':
      return 'text-status-completed bg-green-50'
    case 'failed':
      return 'text-status-failed bg-red-50'
    default:
      return 'text-gray-500 bg-gray-50'
  }
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str
  return str.slice(0, length) + '...'
}

interface NameParts {
  full_name?: string | null
  first_name?: string | null
  last_name?: string | null
  username?: string | null
}

/** Preferred display name: full name → first + last → username. */
export function userDisplayName(user?: NameParts | null): string {
  if (!user) return ''
  const composed = [user.first_name, user.last_name]
    .filter((p) => p && p.trim())
    .join(' ')
    .trim()
  return user.full_name?.trim() || composed || user.username || ''
}

/** Avatar initial(s) derived from the display name (falls back to username). */
export function userInitials(user?: NameParts | null): string {
  const name = userDisplayName(user)
  if (!name) return '?'
  const parts = name.split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return name.charAt(0).toUpperCase()
}
