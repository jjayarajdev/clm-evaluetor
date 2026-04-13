/**
 * Modern Dashboard Page
 * Role-specific views with personalized widgets and metrics
 */
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  DocumentTextIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  ScaleIcon,
  CurrencyDollarIcon,
  BellAlertIcon,
  ArrowRightIcon,
  SparklesIcon,
  ChartBarIcon,
  Cog6ToothIcon,
} from '@heroicons/react/24/outline'
import { useAuth } from '@/contexts/AuthContext'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import WelcomeBanner from '@/components/ui/WelcomeBanner'
import StatCard from '@/components/ui/StatCard'
import { cn, formatCurrency } from '@/lib/utils'
import type { RoleType } from '@/styles/theme'
import type { ContractsSummaryResponse } from '@/types'
import type { PostSigningDashboard } from '@/types/postsigning'

// Activity item component
function ActivityItem({
  icon: Icon,
  title,
  subtitle,
  time,
  color = 'gray',
}: {
  icon: React.ElementType
  title: string
  subtitle: string
  time: string
  color?: 'gray' | 'green' | 'red' | 'amber' | 'blue'
}) {
  const colorClasses = {
    gray: 'bg-gray-100 text-gray-600',
    green: 'bg-emerald-100 text-emerald-600',
    red: 'bg-rose-100 text-rose-600',
    amber: 'bg-amber-100 text-amber-600',
    blue: 'bg-blue-100 text-blue-600',
  }

  return (
    <div className="flex items-start gap-3 py-3">
      <div className={cn('p-2 rounded-lg', colorClasses[color])}>
        <Icon className="w-4 h-4" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 truncate">{title}</p>
        <p className="text-xs text-gray-500 truncate">{subtitle}</p>
      </div>
      <span className="text-xs text-gray-400 whitespace-nowrap">{time}</span>
    </div>
  )
}

// Contract card component
function ContractCard({
  filename,
  counterparty,
  status,
  risk,
  href,
}: {
  filename: string
  counterparty?: string
  status: string
  risk: string
  href: string
}) {
  const riskColors: Record<string, string> = {
    low: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    medium: 'bg-amber-50 text-amber-700 border-amber-200',
    high: 'bg-rose-50 text-rose-700 border-rose-200',
    critical: 'bg-purple-50 text-purple-700 border-purple-200',
  }

  return (
    <Link
      to={href}
      className="block p-4 bg-white rounded-xl border border-gray-200 hover:border-gray-300 hover:shadow-md transition-all group"
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-900 truncate group-hover:text-primary-600">
            {filename}
          </p>
          {counterparty && (
            <p className="text-xs text-gray-500 mt-0.5 truncate">{counterparty}</p>
          )}
        </div>
        <span className={cn(
          'px-2 py-0.5 text-xs font-medium rounded-full border',
          riskColors[risk] || riskColors.low
        )}>
          {risk}
        </span>
      </div>
      <div className="mt-2 flex items-center justify-between">
        <span className="text-xs text-gray-400 capitalize">{status}</span>
        <ArrowRightIcon className="w-4 h-4 text-gray-300 group-hover:text-primary-500 group-hover:translate-x-0.5 transition-all" />
      </div>
    </Link>
  )
}

// Quick insight card
function InsightCard({
  title,
  description,
  action,
  actionLabel,
  variant = 'info',
}: {
  title: string
  description: string
  action: string
  actionLabel: string
  variant?: 'info' | 'warning' | 'success'
}) {
  const variantClasses = {
    info: 'bg-sky-50 border-sky-200',
    warning: 'bg-amber-50 border-amber-200',
    success: 'bg-emerald-50 border-emerald-200',
  }

  return (
    <div className={cn('p-4 rounded-xl border', variantClasses[variant])}>
      <div className="flex items-start gap-3">
        <SparklesIcon className="w-5 h-5 text-primary-500 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-sm font-semibold text-gray-900">{title}</p>
          <p className="text-xs text-gray-600 mt-1">{description}</p>
          <Link
            to={action}
            className="inline-flex items-center gap-1 mt-2 text-xs font-medium text-primary-600 hover:text-primary-700"
          >
            {actionLabel}
            <ArrowRightIcon className="w-3 h-3" />
          </Link>
        </div>
      </div>
    </div>
  )
}

export default function ModernDashboardPage() {
  const { user } = useAuth()
  const userRole = (user?.role || 'viewer') as RoleType

  // Fetch summary data
  const { data: summaryData, isLoading } = useQuery<ContractsSummaryResponse>({
    queryKey: ['contracts-summary'],
    queryFn: () => api.getContractsSummary(),
  })

  // Fetch postsigning data for compliance metrics
  const { data: complianceData } = useQuery<PostSigningDashboard>({
    queryKey: ['postsigning-dashboard'],
    queryFn: () => api.getPostSigningDashboard(),
  })

  // Fetch trend data for sparklines
  const { data: trendData } = useQuery({
    queryKey: ['dashboard-trends'],
    queryFn: () => api.getDashboardTrends(9), // 9 days for sparklines
  })

  // Fetch AI insights
  const { data: insightsData, isError: insightsError } = useQuery({
    queryKey: ['dashboard-insights'],
    queryFn: () => api.getDashboardInsights(),
    retry: 1,
  })

  // Fetch recent activity
  const { data: activityData, isError: activityError } = useQuery({
    queryKey: ['recent-activity'],
    queryFn: () => api.getRecentActivity(10),
    retry: 1,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  // Build dynamic quick actions based on real data
  const getQuickActions = () => {
    const highRiskCount = summaryData?.by_risk?.high || 0
    const pendingCount = summaryData?.by_status?.pending || 0
    const expiringCount = complianceData?.renewals?.expiring_30_days || 0
    const slaBreaches = complianceData?.slas?.critical_breaches || 0
    const overdueCount = complianceData?.obligations?.overdue || 0

    const actionsByRole: Record<RoleType, Array<{
      label: string
      description: string
      href: string
      icon: React.ElementType
      badge?: number
      badgeColor?: 'red' | 'amber' | 'blue'
    }>> = {
      legal: [
        { label: 'High Risk', description: 'Review contracts', href: '/contracts?risk=high', icon: ExclamationTriangleIcon, badge: highRiskCount || undefined, badgeColor: 'red' },
        { label: 'Pending Review', description: 'Awaiting approval', href: '/contracts?status=pending', icon: ClockIcon, badge: pendingCount || undefined, badgeColor: 'amber' },
        { label: 'Ask AI', description: 'Query contracts', href: '/query', icon: SparklesIcon },
      ],
      procurement: [
        { label: 'Expiring Soon', description: 'Next 30 days', href: '/renewals?window=30', icon: ClockIcon, badge: expiringCount || undefined, badgeColor: 'amber' },
        { label: 'Vendors', description: 'Performance scores', href: '/vendors', icon: ChartBarIcon },
        { label: 'New Contract', description: 'Upload & analyze', href: '/upload', icon: SparklesIcon },
      ],
      admin: [
        { label: 'SLA Breaches', description: 'Escalate immediately', href: '/compliance', icon: ExclamationTriangleIcon, badge: slaBreaches || undefined, badgeColor: 'red' },
        { label: 'Overdue', description: 'Obligations past due', href: '/compliance', icon: BellAlertIcon, badge: overdueCount || undefined, badgeColor: 'amber' },
        { label: 'Renewals', description: 'Expiring soon', href: '/renewals', icon: ClockIcon, badge: expiringCount || undefined, badgeColor: 'amber' },
        { label: 'System Health', description: 'Monitor services', href: '/admin/scheduler', icon: ChartBarIcon },
        { label: 'Settings', description: 'Manage access', href: '/settings', icon: Cog6ToothIcon },
      ],
      viewer: [
        { label: 'Browse', description: 'All contracts', href: '/contracts', icon: ChartBarIcon },
        { label: 'Ask AI', description: 'Query contracts', href: '/query', icon: SparklesIcon },
        { label: 'Reports', description: 'View analytics', href: '/reports', icon: ChartBarIcon },
      ],
    }

    return actionsByRole[userRole]
  }

  return (
    <div className="space-y-6 pb-8">
      {/* Welcome Banner */}
      <WelcomeBanner
        userName={user?.full_name || user?.username || 'User'}
        role={userRole}
        quickActions={getQuickActions()}
      />

      {/* Stats Grid - Personio-style colorful widgets */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Contracts"
          value={summaryData?.total_contracts || 0}
          icon={DocumentTextIcon}
          color="primary"
          variant="filled"
          trend={trendData?.total_contracts && trendData.total_contracts.length >= 2 ? {
            value: Math.round(((trendData.total_contracts[trendData.total_contracts.length - 1] - trendData.total_contracts[0]) / Math.max(trendData.total_contracts[0], 1)) * 100),
            label: 'vs last week'
          } : undefined}
          chart={trendData?.total_contracts || undefined}
        />
        <StatCard
          title="At Risk"
          value={complianceData?.compliance?.contracts_at_risk || summaryData?.by_risk?.high || 0}
          icon={ExclamationTriangleIcon}
          color="danger"
          variant="filled"
          trend={trendData?.contracts_at_risk && trendData.contracts_at_risk.length >= 2 ? {
            value: Math.round(((trendData.contracts_at_risk[trendData.contracts_at_risk.length - 1] - trendData.contracts_at_risk[0]) / Math.max(trendData.contracts_at_risk[0], 1)) * 100),
            label: 'vs last week'
          } : undefined}
          chart={trendData?.contracts_at_risk || undefined}
        />
        <StatCard
          title="Compliance"
          value={`${(complianceData?.compliance?.overall_compliance_rate || 0).toFixed(1)}%`}
          info="Percentage of SLAs meeting or within warning threshold of their targets. Calculated as (compliant + warning) / total SLAs."
          icon={CheckCircleIcon}
          color="success"
          variant="filled"
          trend={trendData?.compliance_rate && trendData.compliance_rate.length >= 2 ? {
            value: Math.round(trendData.compliance_rate[trendData.compliance_rate.length - 1] - trendData.compliance_rate[0]),
            label: 'vs last week'
          } : undefined}
          chart={trendData?.compliance_rate || undefined}
        />
        <StatCard
          title="Contract Value"
          value={complianceData?.total_value ? formatCurrency(complianceData.total_value) : 'N/A'}
          icon={CurrencyDollarIcon}
          color="blue"
          variant="filled"
          trend={trendData?.total_contract_value && trendData.total_contract_value.length >= 2 ? {
            value: Math.round(((trendData.total_contract_value[trendData.total_contract_value.length - 1] - trendData.total_contract_value[0]) / Math.max(trendData.total_contract_value[0], 1)) * 100),
            label: 'vs last week'
          } : undefined}
          chart={trendData?.total_contract_value || undefined}
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Recent & Priority */}
        <div className="lg:col-span-2 space-y-6">
          {/* Priority Actions */}
          {complianceData?.priority_actions && complianceData.priority_actions.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                <h2 className="font-semibold text-gray-900 flex items-center gap-2">
                  <BellAlertIcon className="w-5 h-5 text-amber-500" />
                  Priority Actions
                </h2>
                <span className="px-2 py-0.5 text-xs font-semibold bg-amber-100 text-amber-700 rounded-full">
                  {complianceData.priority_actions.length}
                </span>
              </div>
              <div className="divide-y divide-gray-50">
                {complianceData.priority_actions.slice(0, 5).map((action: any, idx: number) => (
                  <div key={idx} className="px-5 py-3 hover:bg-gray-50">
                    <div className="flex items-start gap-3">
                      <div className={cn(
                        'p-1.5 rounded-lg',
                        action.severity === 'critical' ? 'bg-rose-100' :
                        action.severity === 'high' ? 'bg-amber-100' : 'bg-blue-100'
                      )}>
                        {action.type === 'obligation' ? (
                          <CheckCircleIcon className={cn(
                            'w-4 h-4',
                            action.severity === 'critical' ? 'text-rose-600' :
                            action.severity === 'high' ? 'text-amber-600' : 'text-blue-600'
                          )} />
                        ) : action.type === 'sla' ? (
                          <ScaleIcon className="w-4 h-4 text-rose-600" />
                        ) : (
                          <ClockIcon className="w-4 h-4 text-amber-600" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900">{action.title}</p>
                        <p className="text-xs text-gray-500 mt-0.5">{action.action}</p>
                      </div>
                      <span className={cn(
                        'px-2 py-0.5 text-xs font-medium rounded-full',
                        action.severity === 'critical' ? 'bg-rose-100 text-rose-700' :
                        action.severity === 'high' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'
                      )}>
                        {action.type}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
              <Link
                to="/compliance"
                className="block px-5 py-3 text-center text-sm font-medium text-primary-600 hover:bg-primary-50 border-t border-gray-100"
              >
                View All Actions
              </Link>
            </div>
          )}

          {/* Recent Contracts */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">Recent Contracts</h2>
              <Link to="/contracts" className="text-sm text-primary-600 hover:text-primary-700 font-medium">
                View all
              </Link>
            </div>
            <div className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
              {summaryData?.contracts?.slice(0, 4).map((contract) => (
                <ContractCard
                  key={contract.id}
                  filename={contract.filename}
                  counterparty={contract.counterparty || undefined}
                  status={contract.status}
                  risk={contract.risk_level || 'low'}
                  href={`/contracts/${contract.id}`}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Right Column - Insights & Activity */}
        <div className="space-y-6">
          {/* AI Insights */}
          <div className="space-y-3">
            <h2 className="font-semibold text-gray-900 flex items-center gap-2">
              <SparklesIcon className="w-5 h-5 text-primary-500" />
              AI Insights
            </h2>
            {insightsData?.insights?.map((insight, idx) => (
              <InsightCard
                key={idx}
                title={insight.title}
                description={insight.description}
                action={insight.action}
                actionLabel={insight.action_label}
                variant={insight.variant as 'info' | 'warning' | 'success'}
              />
            ))}
            {insightsError ? (
              <div className="p-4 rounded-lg bg-red-50 text-sm text-red-600">
                Failed to load insights. Try refreshing the page.
              </div>
            ) : !insightsData?.insights?.length && (
              <InsightCard
                title="All Clear"
                description="No critical issues detected. All contracts and obligations are on track."
                action="/contracts"
                actionLabel="View contracts"
                variant="success"
              />
            )}
          </div>

          {/* Activity Feed */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h2 className="font-semibold text-gray-900">Recent Activity</h2>
            </div>
            <div className="px-5 divide-y divide-gray-50">
              {activityData?.activities?.map((activity, idx) => {
                const iconMap: Record<string, React.ElementType> = {
                  document: DocumentTextIcon,
                  check: CheckCircleIcon,
                  warning: ExclamationTriangleIcon,
                  clock: ClockIcon,
                  sparkles: SparklesIcon,
                  pencil: DocumentTextIcon,
                }
                const Icon = iconMap[activity.icon] || DocumentTextIcon
                return (
                  <ActivityItem
                    key={idx}
                    icon={Icon}
                    title={activity.title}
                    subtitle={activity.subtitle}
                    time={activity.time}
                    color={activity.color as 'gray' | 'green' | 'red' | 'amber' | 'blue'}
                  />
                )
              })}
              {activityError ? (
                <div className="py-4 text-center text-sm text-red-500">
                  Failed to load activity
                </div>
              ) : !activityData?.activities?.length && (
                <div className="py-4 text-center text-sm text-gray-500">
                  No recent activity
                </div>
              )}
            </div>
            <Link
              to="/compliance"
              className="block px-5 py-3 text-center text-sm font-medium text-primary-600 hover:bg-primary-50 border-t border-gray-100"
            >
              View Compliance
            </Link>
          </div>

          {/* Quick Stats - Personio-style filled cards */}
          <div className="grid grid-cols-2 gap-3">
            <StatCard
              title="Obligations"
              value={`${(complianceData?.obligations?.compliance_rate || 0).toFixed(1)}%`}
              color={(complianceData?.obligations?.compliance_rate || 0) >= 90 ? 'success' : (complianceData?.obligations?.compliance_rate || 0) >= 70 ? 'warning' : 'danger'}
              variant="filled"
              size="sm"
              chart={trendData?.compliance_rate || undefined}
            />
            <StatCard
              title="SLA Performance"
              value={`${(complianceData?.slas?.compliance_rate || 0).toFixed(1)}%`}
              color={(complianceData?.slas?.compliance_rate || 0) >= 90 ? 'success' : (complianceData?.slas?.compliance_rate || 0) >= 70 ? 'warning' : 'danger'}
              variant="filled"
              size="sm"
              chart={trendData?.sla_compliance_rate || undefined}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
