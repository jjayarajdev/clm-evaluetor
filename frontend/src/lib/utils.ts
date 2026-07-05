import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function formatDateTime(dateString: string | null | undefined): string {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatCurrency(value: number | null | undefined, currency = 'USD'): string {
  if (value == null) return '-'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

export function formatNumber(value: number | null | undefined): string {
  if (value == null) return '-'
  return new Intl.NumberFormat('en-US').format(value)
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
