/**
 * Modern Table Component
 * Reusable table with modern styling
 */
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'

interface Column<T> {
  key: string
  header: string
  sortable?: boolean
  className?: string
  render?: (item: T, index: number) => React.ReactNode
}

interface ModernTableProps<T> {
  columns: Column<T>[]
  data: T[]
  keyExtractor: (item: T) => string
  onRowClick?: (item: T) => void
  emptyMessage?: string
  isLoading?: boolean
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
  onSort?: (column: string) => void
}

export default function ModernTable<T>({
  columns,
  data,
  keyExtractor,
  onRowClick,
  emptyMessage,
  sortBy,
  sortOrder,
  onSort,
}: ModernTableProps<T>) {
  const { t } = useTranslation()
  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead>
            <tr className="bg-gray-50/80">
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={cn(
                    'px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider',
                    column.sortable && 'cursor-pointer hover:bg-gray-100 select-none',
                    column.className
                  )}
                  onClick={() => column.sortable && onSort?.(column.key)}
                >
                  <div className="flex items-center gap-1.5">
                    {column.header}
                    {column.sortable && sortBy === column.key && (
                      <span className="text-primary-500">
                        {sortOrder === 'asc' ? '↑' : '↓'}
                      </span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data.map((item, index) => (
              <tr
                key={keyExtractor(item)}
                className={cn(
                  'transition-colors',
                  onRowClick && 'cursor-pointer hover:bg-gray-50',
                )}
                onClick={() => onRowClick?.(item)}
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={cn('px-4 py-3.5 text-sm', column.className)}
                  >
                    {column.render
                      ? column.render(item, index)
                      : (item as any)[column.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          {emptyMessage ?? t('table.noData')}
        </div>
      )}
    </div>
  )
}

// Badge component for status/risk indicators
export function StatusBadge({
  status,
  variant = 'default',
}: {
  status: string
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info'
}) {
  const variantClasses = {
    default: 'bg-gray-100 text-gray-700 ring-gray-200',
    success: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    warning: 'bg-amber-50 text-amber-700 ring-amber-200',
    danger: 'bg-rose-50 text-rose-700 ring-rose-200',
    info: 'bg-sky-50 text-sky-700 ring-sky-200',
  }

  return (
    <span className={cn(
      'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ring-1 ring-inset',
      variantClasses[variant]
    )}>
      {status}
    </span>
  )
}

// Risk badge with automatic color based on level
export function RiskBadge({ level }: { level: string }) {
  const { t } = useTranslation()
  const variants: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    low: 'success',
    medium: 'warning',
    high: 'danger',
    critical: 'danger',
  }

  return (
    <StatusBadge
      status={t(`risk.${level.toLowerCase()}`, { defaultValue: level.charAt(0).toUpperCase() + level.slice(1) })}
      variant={variants[level.toLowerCase()] || 'default'}
    />
  )
}
