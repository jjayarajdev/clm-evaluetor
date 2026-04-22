/**
 * Welcome Banner - Coast Theme
 * Dark gradient header with date and quick actions
 */
import { Link } from 'react-router-dom'
import {
  ArrowRightIcon,
  Cog6ToothIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  ChartBarIcon,
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
    { label: 'Renewals', description: 'Expiring soon', href: '/renewals', icon: ClockIcon },
    { label: 'Users', description: 'Manage access', href: '/settings', icon: Cog6ToothIcon },
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

function formatDate(): string {
  return new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

export default function WelcomeBanner({
  userName,
  role,
  greeting,
  quickActions,
}: WelcomeBannerProps) {
  const actions = quickActions || defaultQuickActions[role]
  const displayGreeting = greeting || getTimeBasedGreeting()
  const firstName = userName.split(' ')[0]

  return (
    <div className="space-y-6">
      {/* Dark gradient hero banner */}
      <div className="bg-gradient-to-r from-primary-800 via-primary-700 to-primary-600 rounded-xl px-8 py-7">
        <h1 className="text-2xl md:text-3xl font-semibold text-white tracking-tight">
          {displayGreeting}, {firstName}
        </h1>
        <p className="mt-1.5 text-sm text-gray-300">
          {formatDate()} — {roleLabels[role]} Portfolio Overview
        </p>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 sm:grid-cols-3 md:grid-cols-5 gap-3">
        {actions.map((action) => (
          <Link
            key={action.label}
            to={action.href}
            className={cn(
              'group flex items-center gap-3 p-4 rounded-xl transition-all duration-200',
              action.badgeColor === 'red'
                ? 'bg-red-50 hover:bg-red-100 border border-red-200 hover:border-red-300'
                : action.badgeColor === 'amber'
                ? 'bg-amber-50 hover:bg-amber-100 border border-amber-200 hover:border-amber-300'
                : 'bg-primary-50 hover:bg-primary-100 border border-primary-200 hover:border-primary-300'
            )}
          >
            <div className={cn(
              'p-2 rounded-lg border transition-colors',
              action.badgeColor === 'red'
                ? 'bg-red-100 border-red-200 group-hover:border-red-300'
                : action.badgeColor === 'amber'
                ? 'bg-amber-100 border-amber-200 group-hover:border-amber-300'
                : 'bg-primary-100 border-primary-200 group-hover:border-primary-300'
            )}>
              <action.icon className={cn(
                'h-5 w-5',
                action.badgeColor === 'red' ? 'text-red-600'
                : action.badgeColor === 'amber' ? 'text-amber-600'
                : 'text-primary-600'
              )} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className={cn(
                  'text-sm font-medium',
                  action.badgeColor === 'red' ? 'text-red-900'
                  : action.badgeColor === 'amber' ? 'text-amber-900'
                  : 'text-primary-900'
                )}>{action.label}</span>
                {action.badge !== undefined && (
                  <span className={cn(
                    'px-1.5 py-0.5 text-xs font-semibold rounded-full',
                    action.badgeColor === 'red' ? 'bg-red-200 text-red-800' :
                    action.badgeColor === 'amber' ? 'bg-amber-200 text-amber-800' :
                    'bg-primary-200 text-primary-800'
                  )}>
                    {action.badge}
                  </span>
                )}
              </div>
              <p className={cn(
                'text-xs truncate',
                action.badgeColor === 'red' ? 'text-red-600'
                : action.badgeColor === 'amber' ? 'text-amber-600'
                : 'text-primary-500'
              )}>{action.description}</p>
            </div>
            <ArrowRightIcon className={cn(
              'h-4 w-4 group-hover:translate-x-0.5 transition-all',
              action.badgeColor === 'red' ? 'text-red-400 group-hover:text-red-600'
              : action.badgeColor === 'amber' ? 'text-amber-400 group-hover:text-amber-600'
              : 'text-primary-400 group-hover:text-primary-600'
            )} />
          </Link>
        ))}
      </div>
    </div>
  )
}
