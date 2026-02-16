/**
 * Stat Card Component - Personio Style
 * Clean widgets with subtle colors and optional mini charts
 */
import { cn } from '@/lib/utils'

interface StatCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon?: React.ElementType
  trend?: {
    value: number
    label?: string
  }
  variant?: 'default' | 'filled' | 'chart'
  color?: 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'purple' | 'pink' | 'blue'
  size?: 'sm' | 'md' | 'lg'
  onClick?: () => void
  chart?: number[] // Mini bar chart data
}

const colorStyles = {
  default: {
    bg: 'bg-white',
    border: 'border-gray-200',
    icon: 'text-gray-500',
    iconBg: 'bg-gray-100',
    text: 'text-gray-900',
    chartBar: 'bg-gray-300',
  },
  primary: {
    bg: 'bg-violet-50',
    border: 'border-violet-200',
    icon: 'text-violet-600',
    iconBg: 'bg-violet-100',
    text: 'text-gray-900',
    chartBar: 'bg-violet-400',
  },
  success: {
    bg: 'bg-emerald-50',
    border: 'border-emerald-200',
    icon: 'text-emerald-600',
    iconBg: 'bg-emerald-100',
    text: 'text-gray-900',
    chartBar: 'bg-emerald-400',
  },
  warning: {
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    icon: 'text-amber-600',
    iconBg: 'bg-amber-100',
    text: 'text-gray-900',
    chartBar: 'bg-amber-400',
  },
  danger: {
    bg: 'bg-red-50',
    border: 'border-red-200',
    icon: 'text-red-600',
    iconBg: 'bg-red-100',
    text: 'text-gray-900',
    chartBar: 'bg-red-400',
  },
  purple: {
    bg: 'bg-violet-50',
    border: 'border-violet-200',
    icon: 'text-violet-600',
    iconBg: 'bg-violet-100',
    text: 'text-gray-900',
    chartBar: 'bg-violet-400',
  },
  pink: {
    bg: 'bg-pink-50',
    border: 'border-pink-200',
    icon: 'text-pink-600',
    iconBg: 'bg-pink-100',
    text: 'text-gray-900',
    chartBar: 'bg-pink-400',
  },
  blue: {
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    icon: 'text-blue-600',
    iconBg: 'bg-blue-100',
    text: 'text-gray-900',
    chartBar: 'bg-blue-400',
  },
}

function MiniBarChart({ data, color }: { data: number[], color: string }) {
  const max = Math.max(...data)
  return (
    <div className="flex items-end gap-1 h-8">
      {data.map((value, i) => (
        <div
          key={i}
          className={cn('w-2 rounded-t transition-all', color)}
          style={{ height: `${(value / max) * 100}%` }}
        />
      ))}
    </div>
  )
}

export default function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  variant = 'default',
  color = 'default',
  size = 'md',
  onClick,
  chart,
}: StatCardProps) {
  const styles = colorStyles[color]

  const sizeClasses = {
    sm: 'p-4',
    md: 'p-5',
    lg: 'p-6',
  }

  const valueSize = {
    sm: 'text-xl',
    md: 'text-2xl',
    lg: 'text-3xl',
  }

  const isFilled = variant === 'filled'

  return (
    <div
      className={cn(
        'rounded-xl border transition-all duration-200',
        sizeClasses[size],
        isFilled ? styles.bg : 'bg-white',
        styles.border,
        onClick && 'cursor-pointer hover:shadow-md'
      )}
      onClick={onClick}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            {Icon && (
              <div className={cn('p-1.5 rounded-lg', styles.iconBg)}>
                <Icon className={cn('h-4 w-4', styles.icon)} />
              </div>
            )}
            <p className="text-sm font-medium text-gray-600">
              {title}
            </p>
          </div>
          <p className={cn(
            'mt-2 font-bold tracking-tight',
            valueSize[size],
            styles.text
          )}>
            {value}
          </p>
          {subtitle && (
            <p className="mt-1 text-sm text-gray-500">
              {subtitle}
            </p>
          )}
        </div>

        {/* Mini chart */}
        {chart && chart.length > 0 && (
          <MiniBarChart data={chart} color={styles.chartBar} />
        )}
      </div>

      {/* Trend indicator */}
      {trend && (
        <div className="mt-3 flex items-center gap-1.5">
          <span className={cn(
            'text-sm font-semibold',
            trend.value > 0 ? 'text-emerald-600' :
            trend.value < 0 ? 'text-red-500' :
            'text-gray-500'
          )}>
            {trend.value > 0 ? '↑' : trend.value < 0 ? '↓' : '→'} {Math.abs(trend.value)}%
          </span>
          {trend.label && (
            <span className="text-xs text-gray-500">
              {trend.label}
            </span>
          )}
        </div>
      )}
    </div>
  )
}

// Status badge component (Personio-style)
export function StatusBadge({
  status,
  size = 'sm',
}: {
  status: 'active' | 'inactive' | 'pending' | 'breached' | 'completed' | 'processing'
  size?: 'xs' | 'sm' | 'md'
}) {
  const statusStyles = {
    active: 'bg-emerald-100 text-emerald-700',
    completed: 'bg-emerald-100 text-emerald-700',
    inactive: 'bg-gray-100 text-gray-600',
    pending: 'bg-amber-100 text-amber-700',
    processing: 'bg-blue-100 text-blue-700',
    breached: 'bg-red-100 text-red-700',
  }

  const sizeClasses = {
    xs: 'px-1.5 py-0.5 text-xs',
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
  }

  const labels = {
    active: 'Active',
    completed: 'Completed',
    inactive: 'Inactive',
    pending: 'Pending',
    processing: 'Processing',
    breached: 'Breached',
  }

  return (
    <span className={cn(
      'inline-flex items-center font-medium rounded-full',
      statusStyles[status],
      sizeClasses[size]
    )}>
      {labels[status]}
    </span>
  )
}

// Filter pill component
export function FilterPill({
  label,
  onRemove,
  icon: Icon,
}: {
  label: string
  onRemove?: () => void
  icon?: React.ElementType
}) {
  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-violet-100 text-violet-700 text-sm font-medium rounded-full">
      {Icon && <Icon className="h-3.5 w-3.5" />}
      {label}
      {onRemove && (
        <button
          onClick={onRemove}
          className="ml-1 hover:bg-violet-200 rounded-full p-0.5"
        >
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}
    </span>
  )
}
