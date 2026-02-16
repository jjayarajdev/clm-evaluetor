/**
 * Welcome Banner - European Minimal Style
 * Clean, sophisticated greeting with quick actions
 */
import { Link } from 'react-router-dom'
import {
  ArrowRightIcon,
  Cog6ToothIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  ChartBarIcon,
  BellAlertIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'
import type { RoleType } from '@/styles/theme'

interface QuickAction {
  label: string
  description: string
  href: string
  icon: React.ElementType
  badge?: string | number
  badgeColor?: 'red' | 'amber' | 'blue'
}

interface WelcomeBannerProps {
  userName: string
  role: RoleType
  greeting?: string
  alerts?: {
    critical: number
    warning: number
  }
  quickActions?: QuickAction[]
}

const roleLabels: Record<RoleType, string> = {
  legal: 'Legal',
  procurement: 'Procurement',
  admin: 'Admin',
  viewer: 'Viewer',
}

const defaultQuickActions: Record<RoleType, QuickAction[]> = {
  legal: [
    { label: 'High Risk', description: 'Review contracts', href: '/contracts?risk=high', icon: ExclamationTriangleIcon, badge: 5, badgeColor: 'red' },
    { label: 'Pending Review', description: 'Awaiting approval', href: '/contracts?status=pending', icon: ClockIcon, badge: 12, badgeColor: 'amber' },
    { label: 'Ask AI', description: 'Query contracts', href: '/query', icon: SparklesIcon },
  ],
  procurement: [
    { label: 'Expiring Soon', description: 'Next 30 days', href: '/renewals?window=30', icon: ClockIcon, badge: 8, badgeColor: 'amber' },
    { label: 'Vendors', description: 'Performance scores', href: '/vendors', icon: ChartBarIcon },
    { label: 'New Contract', description: 'Upload & analyze', href: '/upload', icon: SparklesIcon },
  ],
  admin: [
    { label: 'System Health', description: 'Monitor services', href: '/admin/scheduler', icon: ChartBarIcon },
    { label: 'Alerts', description: 'Active issues', href: '/admin/alerts', icon: BellAlertIcon, badge: 3, badgeColor: 'red' },
    { label: 'Users', description: 'Manage access', href: '/users', icon: Cog6ToothIcon },
  ],
  viewer: [
    { label: 'Browse', description: 'All contracts', href: '/contracts', icon: ChartBarIcon },
    { label: 'Ask AI', description: 'Query contracts', href: '/query', icon: SparklesIcon },
    { label: 'Reports', description: 'View analytics', href: '/reports', icon: ChartBarIcon },
  ],
}

function getTimeBasedGreeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

export default function WelcomeBanner({
  userName,
  role,
  greeting,
  alerts,
  quickActions,
}: WelcomeBannerProps) {
  const actions = quickActions || defaultQuickActions[role]
  const displayGreeting = greeting || getTimeBasedGreeting()
  const firstName = userName.split(' ')[0]

  return (
    <div className="pb-6 border-b border-gray-200">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500 uppercase tracking-wider">
            {roleLabels[role]} Dashboard
          </p>
          <h1 className="mt-1 text-2xl md:text-3xl font-semibold text-gray-900 tracking-tight">
            {displayGreeting}, {firstName}
          </h1>
        </div>

        {/* Alert badges */}
        {alerts && (alerts.critical > 0 || alerts.warning > 0) && (
          <div className="flex items-center gap-2">
            {alerts.critical > 0 && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 bg-red-50 border border-red-200 rounded-lg">
                <ExclamationTriangleIcon className="h-4 w-4 text-red-600" />
                <span className="text-sm font-semibold text-red-700">{alerts.critical} critical</span>
              </div>
            )}
            {alerts.warning > 0 && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-50 border border-amber-200 rounded-lg">
                <BellAlertIcon className="h-4 w-4 text-amber-600" />
                <span className="text-sm font-semibold text-amber-700">{alerts.warning} pending</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-3">
        {actions.map((action) => (
          <Link
            key={action.label}
            to={action.href}
            className={cn(
              'group flex items-center gap-3 p-4 rounded-xl',
              'bg-gray-50 hover:bg-gray-100',
              'border border-gray-200 hover:border-gray-300',
              'transition-all duration-200'
            )}
          >
            <div className="p-2 bg-white rounded-lg border border-gray-200 group-hover:border-gray-300 transition-colors">
              <action.icon className="h-5 w-5 text-gray-600" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-900">{action.label}</span>
                {action.badge !== undefined && (
                  <span className={cn(
                    'px-1.5 py-0.5 text-xs font-semibold rounded-full',
                    action.badgeColor === 'red' ? 'bg-red-100 text-red-700' :
                    action.badgeColor === 'amber' ? 'bg-amber-100 text-amber-700' :
                    'bg-gray-200 text-gray-700'
                  )}>
                    {action.badge}
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-500 truncate">{action.description}</p>
            </div>
            <ArrowRightIcon className="h-4 w-4 text-gray-400 group-hover:text-gray-600 group-hover:translate-x-0.5 transition-all" />
          </Link>
        ))}
      </div>

      {/* Keyboard shortcut hint */}
      <div className="mt-4 flex items-center gap-2 text-gray-400 text-xs">
        <span>Press</span>
        <kbd className="px-1.5 py-0.5 bg-gray-100 border border-gray-200 rounded text-gray-600 font-mono text-xs">⌘K</kbd>
        <span>to open command palette</span>
      </div>
    </div>
  )
}
