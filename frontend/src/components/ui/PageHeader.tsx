/**
 * Modern Page Header Component - European Minimal Style
 * Clean, sophisticated, single accent color
 */
import { Link } from 'react-router-dom'
import { ArrowLeftIcon } from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'

interface PageHeaderProps {
  title: string
  description?: string
  icon?: React.ElementType
  backLink?: string
  backLabel?: string
  actions?: React.ReactNode
  variant?: 'default' | 'minimal' | 'bordered'
  accentColor?: string
}

export default function PageHeader({
  title,
  description,
  icon: Icon,
  backLink,
  backLabel,
  actions,
  variant = 'default',
  accentColor = 'text-gray-900',
}: PageHeaderProps) {
  return (
    <div className={cn(
      'pb-6',
      variant === 'bordered' && 'border-b border-gray-200'
    )}>
      {backLink && (
        <Link
          to={backLink}
          className="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-600 mb-4 transition-colors"
        >
          <ArrowLeftIcon className="w-4 h-4" />
          {backLabel || 'Back'}
        </Link>
      )}

      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          {Icon && (
            <div className="p-2 bg-gray-100 rounded-lg">
              <Icon className="h-6 w-6 text-gray-600" />
            </div>
          )}
          <div>
            <h1 className={cn(
              'text-2xl font-semibold tracking-tight',
              accentColor
            )}>
              {title}
            </h1>
            {description && (
              <p className="mt-1 text-sm text-gray-500 max-w-2xl">
                {description}
              </p>
            )}
          </div>
        </div>
        {actions && (
          <div className="flex items-center gap-3">{actions}</div>
        )}
      </div>
    </div>
  )
}
