import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  ChartBarIcon,
  CalendarIcon,
  BuildingOfficeIcon,
  FlagIcon,
  DocumentChartBarIcon,
  XMarkIcon,
  ShieldCheckIcon,
  FunnelIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import PageHeader from '@/components/ui/PageHeader'
import StatCard from '@/components/ui/StatCard'
import { cn } from '@/lib/utils'

interface SLABreachDetail {
  sla_id: string
  sla_name: string
  contract_id: string
  contract_filename: string
  metric_type: string
  target_value: number
  actual_value: number
  deviation_percentage: number
  breach_severity: string
  measured_at: string
  penalty_amount: number | null
  consecutive_breaches: number
}

interface ObligationRow {
  id: string
  contract_id: string
  contract_filename: string
  counterparty: string | null
  title: string
  description: string
  category: string | null
  owner: string | null
  due_date: string | null
  status: string
  rag_status: string | null
}

function RAGBadge({ status }: { status: string | null }) {
  if (!status) return <span className="text-gray-400 text-xs">N/A</span>

  const colors: Record<string, string> = {
    green: 'bg-green-100 text-green-800',
    amber: 'bg-amber-100 text-amber-800',
    red: 'bg-red-100 text-red-800',
  }

  return (
    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', colors[status] || 'bg-gray-100 text-gray-800')}>
      {status.toUpperCase()}
    </span>
  )
}

function SLABreachDetailModal({
  breach,
  onClose
}: {
  breach: SLABreachDetail
  onClose: () => void
}) {
  const severityColors: Record<string, string> = {
    critical: 'bg-red-100 text-red-800 border-red-200',
    major: 'bg-orange-100 text-orange-800 border-orange-200',
    moderate: 'bg-amber-100 text-amber-800 border-amber-200',
    minor: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  }

  const deviationColor = breach.deviation_percentage < 0 ? 'text-red-600' : 'text-green-600'

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="fixed inset-0 bg-black/30" onClick={onClose} />
        <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">{breach.sla_name}</h3>
              <Link
                to={`/contracts/${breach.contract_id}`}
                className="text-sm text-primary-600 hover:underline"
              >
                {breach.contract_filename}
              </Link>
            </div>
            <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
              <XMarkIcon className="h-5 w-5 text-gray-500" />
            </button>
          </div>

          {/* Content */}
          <div className="p-4 space-y-4">
            {/* Severity Badge */}
            <div className="flex items-center gap-3">
              <span className={cn(
                'px-3 py-1 rounded-full text-sm font-medium border',
                severityColors[breach.breach_severity] || 'bg-gray-100 text-gray-800'
              )}>
                {breach.breach_severity.toUpperCase()} Breach
              </span>
              <span className="text-sm text-gray-500">
                {breach.consecutive_breaches} consecutive breach{breach.consecutive_breaches !== 1 ? 'es' : ''}
              </span>
            </div>

            {/* Metrics Comparison */}
            <div className="bg-gray-50 rounded-lg p-4">
              <h4 className="text-sm font-medium text-gray-700 mb-3">Performance Metrics</h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-gray-500 uppercase">Target</p>
                  <p className="text-xl font-semibold text-gray-900">
                    {breach.target_value.toFixed(2)}
                    {breach.metric_type === 'uptime_percentage' || breach.metric_type === 'availability' ? '%' : ''}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase">Actual</p>
                  <p className={cn('text-xl font-semibold', deviationColor)}>
                    {breach.actual_value.toFixed(2)}
                    {breach.metric_type === 'uptime_percentage' || breach.metric_type === 'availability' ? '%' : ''}
                  </p>
                </div>
              </div>
              <div className="mt-3 pt-3 border-t border-gray-200">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-500">Deviation</span>
                  <span className={cn('text-sm font-medium', deviationColor)}>
                    {breach.deviation_percentage > 0 ? '+' : ''}{breach.deviation_percentage.toFixed(2)}%
                  </span>
                </div>
              </div>
            </div>

            {/* Additional Info */}
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Metric Type</span>
                <span className="font-medium text-gray-900 capitalize">
                  {breach.metric_type.replace(/_/g, ' ')}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Last Measured</span>
                <span className="font-medium text-gray-900">
                  {new Date(breach.measured_at).toLocaleString()}
                </span>
              </div>
              {breach.penalty_amount && (
                <div className="flex justify-between">
                  <span className="text-gray-500">Penalty Amount</span>
                  <span className="font-medium text-red-600">
                    ${breach.penalty_amount.toLocaleString()}
                  </span>
                </div>
              )}
            </div>

            {/* Progress Bar showing deviation */}
            <div>
              <div className="flex justify-between text-xs text-gray-500 mb-1">
                <span>0%</span>
                <span>Target: {breach.target_value.toFixed(1)}%</span>
                <span>100%</span>
              </div>
              <div className="h-3 bg-gray-200 rounded-full overflow-hidden relative">
                {/* Target marker */}
                <div
                  className="absolute h-full w-0.5 bg-gray-600 z-10"
                  style={{ left: `${Math.min(breach.target_value, 100)}%` }}
                />
                {/* Actual value */}
                <div
                  className={cn(
                    'h-full rounded-full transition-all',
                    breach.actual_value >= breach.target_value ? 'bg-green-500' : 'bg-red-500'
                  )}
                  style={{ width: `${Math.min(breach.actual_value, 100)}%` }}
                />
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-3 p-4 border-t bg-gray-50 rounded-b-lg">
            <Link
              to={`/contracts/${breach.contract_id}`}
              className="btn btn-secondary text-sm"
            >
              View Contract
            </Link>
            <button onClick={onClose} className="btn btn-primary text-sm">
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function PriorityActionItem({ action }: { action: { type: string; severity: string; title: string; action: string } }) {
  const severityColors: Record<string, string> = {
    critical: 'border-l-red-500 bg-red-50',
    high: 'border-l-amber-500 bg-amber-50',
    medium: 'border-l-blue-500 bg-blue-50',
  }

  return (
    <div className={cn('border-l-4 p-3 rounded-r', severityColors[action.severity] || 'border-l-gray-300 bg-gray-50')}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-900">{action.title}</p>
          <p className="text-xs text-gray-500 mt-1">{action.action}</p>
        </div>
        <span className={cn(
          'text-xs px-2 py-0.5 rounded-full',
          action.type === 'obligation' ? 'bg-blue-100 text-blue-700' :
          action.type === 'sla' ? 'bg-purple-100 text-purple-700' :
          'bg-green-100 text-green-700'
        )}>
          {action.type}
        </span>
      </div>
    </div>
  )
}

export default function PostSigningPage() {
  const [activeTab, setActiveTab] = useState<'overview' | 'obligations' | 'slas' | 'renewals' | 'vendors' | 'milestones'>('overview')
  const [selectedBreach, setSelectedBreach] = useState<SLABreachDetail | null>(null)
  const [oblStatusFilter, setOblStatusFilter] = useState<string>('')
  const [oblRagFilter, setOblRagFilter] = useState<string>('')

  const { data: dashboard, isLoading, error } = useQuery({
    queryKey: ['postsigning-dashboard'],
    queryFn: () => api.getPostSigningDashboard(),
  })

  // Fetch compliance trends for sparkline charts
  const { data: trendData } = useQuery({
    queryKey: ['compliance-trend'],
    queryFn: () => api.getComplianceTrend('weekly', 8),
  })

  // Fetch full obligation list when on obligations tab
  const { data: allObligations, isLoading: oblLoading } = useQuery({
    queryKey: ['postsigning-obligations', oblStatusFilter, oblRagFilter],
    queryFn: () => api.getPostSigningObligations({
      ...(oblStatusFilter && { status: oblStatusFilter }),
      ...(oblRagFilter && { rag: oblRagFilter }),
    }),
    enabled: activeTab === 'obligations',
  })

  // Build sparkline data from trend
  const complianceChart = useMemo(() => {
    if (!trendData?.data_points?.length) return undefined
    return trendData.data_points.map(p => Math.round(p.overall_compliance_rate))
  }, [trendData])

  const obligationChart = useMemo(() => {
    if (!trendData?.data_points?.length) return undefined
    return trendData.data_points.map(p => Math.round(p.obligation_compliance_rate))
  }, [trendData])

  const slaChart = useMemo(() => {
    if (!trendData?.data_points?.length) return undefined
    return trendData.data_points.map(p => Math.round(p.sla_compliance_rate))
  }, [trendData])

  const breachChart = useMemo(() => {
    if (!trendData?.data_points?.length) return undefined
    return trendData.data_points.map(p => p.sla_breaches)
  }, [trendData])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !dashboard) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">Failed to load dashboard data</p>
      </div>
    )
  }

  const trendDirection = trendData?.overall_trend
  const trendChange = trendData?.overall_change_pct

  const tabs = [
    { id: 'overview', label: 'Overview', icon: ChartBarIcon },
    { id: 'obligations', label: `Obligations (${dashboard.obligations.total})`, icon: CheckCircleIcon },
    { id: 'slas', label: `SLAs (${dashboard.slas.active_slas})`, icon: FlagIcon },
    { id: 'milestones', label: `Milestones (${dashboard.milestones.total_milestones})`, icon: ClockIcon },
    { id: 'renewals', label: 'Renewals', icon: CalendarIcon },
    { id: 'vendors', label: `Vendors (${dashboard.vendors.total_vendors})`, icon: BuildingOfficeIcon },
  ]

  const obligations = (allObligations || []) as ObligationRow[]

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title="Compliance & Performance"
        description="Monitor obligations, SLAs, milestones, renewals, and vendor performance"
        icon={ShieldCheckIcon}
        variant="bordered"
        actions={
          <Link
            to="/reports"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 transition-colors"
          >
            <DocumentChartBarIcon className="h-4 w-4" />
            Generate Report
          </Link>
        }
      />

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Overall Compliance"
          value={`${dashboard.compliance.overall_compliance_rate.toFixed(1)}%`}
          subtitle={trendDirection ? `Trend: ${trendDirection}` : undefined}
          icon={CheckCircleIcon}
          color={dashboard.compliance.overall_compliance_rate >= 90 ? 'success' : dashboard.compliance.overall_compliance_rate >= 70 ? 'warning' : 'danger'}
          variant="filled"
          chart={complianceChart}
          trend={trendChange != null ? { value: Math.round(trendChange), label: 'vs last period' } : undefined}
        />
        <StatCard
          title="Contracts At Risk"
          value={dashboard.contracts_needing_attention}
          subtitle={`${dashboard.compliance.high_priority_actions} priority actions`}
          icon={ExclamationTriangleIcon}
          color={dashboard.contracts_needing_attention > 0 ? 'danger' : 'success'}
          variant="filled"
          chart={breachChart}
        />
        <StatCard
          title="Active Contracts"
          value={dashboard.total_contracts}
          subtitle={dashboard.total_value ? `$${(dashboard.total_value / 1000000).toFixed(1)}M total value` : 'N/A'}
          icon={ChartBarIcon}
          color="primary"
          variant="filled"
        />
        <StatCard
          title="Renewals (90 days)"
          value={dashboard.renewals.expiring_90_days}
          subtitle={`${dashboard.renewals.past_notice_deadline} past notice deadline`}
          icon={CalendarIcon}
          color={dashboard.renewals.past_notice_deadline > 0 ? 'warning' : 'default'}
          variant="filled"
        />
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 bg-white rounded-t-xl px-4">
        <nav className="flex space-x-6 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={cn(
                'flex items-center gap-2 py-3 px-1 border-b-2 text-sm font-medium transition-colors whitespace-nowrap',
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              )}
            >
              <tab.icon className="h-4 w-4" />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Priority Actions */}
          <div className="lg:col-span-2 card">
            <div className="card-header">
              <h3 className="font-medium text-gray-900">Priority Actions</h3>
            </div>
            <div className="p-4 space-y-3">
              {dashboard.priority_actions.length > 0 ? (
                dashboard.priority_actions.map((action, idx) => (
                  <PriorityActionItem key={idx} action={action} />
                ))
              ) : (
                <p className="text-sm text-gray-500 text-center py-4">No priority actions at this time</p>
              )}
            </div>
          </div>

          {/* Quick Stats Sidebar */}
          <div className="space-y-4">
            {/* Obligations Summary */}
            <div className="card">
              <div className="card-header">
                <h3 className="font-medium text-gray-900">Obligations</h3>
              </div>
              <div className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-2xl font-bold text-gray-900">
                    {dashboard.obligations.compliance_rate.toFixed(1)}%
                  </span>
                  <span className="text-sm text-gray-500">compliance</span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Completed</span>
                    <span className="font-medium text-green-600">{dashboard.obligations.completed}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">In Progress</span>
                    <span className="font-medium text-blue-600">{dashboard.obligations.in_progress}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Overdue</span>
                    <span className="font-medium text-red-600">{dashboard.obligations.overdue}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">At Risk</span>
                    <span className="font-medium text-amber-600">{dashboard.obligations.at_risk}</span>
                  </div>
                </div>
                <div className="mt-3 flex gap-2">
                  <div className="flex-1 text-center py-1 rounded bg-green-50 text-green-700 text-xs">
                    {dashboard.obligations.green} Green
                  </div>
                  <div className="flex-1 text-center py-1 rounded bg-amber-50 text-amber-700 text-xs">
                    {dashboard.obligations.amber} Amber
                  </div>
                  <div className="flex-1 text-center py-1 rounded bg-red-50 text-red-700 text-xs">
                    {dashboard.obligations.red} Red
                  </div>
                </div>
              </div>
            </div>

            {/* SLA Summary */}
            <div className="card">
              <div className="card-header">
                <h3 className="font-medium text-gray-900">SLA Performance</h3>
              </div>
              <div className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-2xl font-bold text-gray-900">
                    {dashboard.slas.compliance_rate.toFixed(1)}%
                  </span>
                  <span className="text-sm text-gray-500">compliance</span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Active SLAs</span>
                    <span className="font-medium">{dashboard.slas.active_slas}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Breached</span>
                    <span className="font-medium text-red-600">{dashboard.slas.breached}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Penalties MTD</span>
                    <span className="font-medium text-red-600">
                      ${dashboard.slas.total_penalties_mtd.toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Milestones Summary */}
            <div className="card">
              <div className="card-header flex items-center justify-between">
                <h3 className="font-medium text-gray-900">Milestones</h3>
                <button
                  onClick={() => setActiveTab('milestones')}
                  className="text-xs text-primary-600 hover:underline"
                >
                  View all
                </button>
              </div>
              <div className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-2xl font-bold text-gray-900">
                    {dashboard.milestones.completion_rate.toFixed(1)}%
                  </span>
                  <span className="text-sm text-gray-500">complete</span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Total</span>
                    <span className="font-medium">{dashboard.milestones.total_milestones}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Completed</span>
                    <span className="font-medium text-green-600">{dashboard.milestones.completed}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Overdue</span>
                    <span className="font-medium text-red-600">{dashboard.milestones.overdue}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">At Risk</span>
                    <span className="font-medium text-amber-600">{dashboard.milestones.at_risk}</span>
                  </div>
                </div>
                {/* Completion bar */}
                <div className="mt-3">
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-green-500 rounded-full transition-all"
                      style={{ width: `${dashboard.milestones.completion_rate}%` }}
                    />
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    {dashboard.milestones.completed} of {dashboard.milestones.total_milestones} completed
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'obligations' && (
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <h3 className="font-medium text-gray-900">All Obligations</h3>
            <div className="flex items-center gap-3">
              {/* Status filter */}
              <div className="flex items-center gap-1.5">
                <FunnelIcon className="h-4 w-4 text-gray-400" />
                <select
                  value={oblStatusFilter}
                  onChange={(e) => setOblStatusFilter(e.target.value)}
                  className="text-sm border-gray-300 rounded-md py-1 pl-2 pr-7"
                >
                  <option value="">All Statuses</option>
                  <option value="pending">Pending</option>
                  <option value="in_progress">In Progress</option>
                  <option value="completed">Completed</option>
                  <option value="overdue">Overdue</option>
                  <option value="waived">Waived</option>
                </select>
              </div>
              {/* RAG filter */}
              <select
                value={oblRagFilter}
                onChange={(e) => setOblRagFilter(e.target.value)}
                className="text-sm border-gray-300 rounded-md py-1 pl-2 pr-7"
              >
                <option value="">All RAG</option>
                <option value="green">Green</option>
                <option value="amber">Amber</option>
                <option value="red">Red</option>
              </select>
              <span className="text-sm text-gray-500">
                {oblLoading ? '...' : `${obligations.length} items`}
              </span>
            </div>
          </div>
          <div className="overflow-x-auto">
            {oblLoading ? (
              <div className="flex justify-center py-8"><LoadingSpinner /></div>
            ) : (
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Title</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Contract</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Owner</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Due Date</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">RAG</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {obligations.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-sm text-gray-500">
                        No obligations found matching filters
                      </td>
                    </tr>
                  ) : (
                    obligations.map((item) => (
                      <tr key={item.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-medium text-gray-900 max-w-xs truncate">
                          <Link
                            to={`/obligations/${item.id}`}
                            className="hover:text-primary-600 hover:underline"
                          >
                            {item.title}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500 max-w-[180px] truncate">
                          <Link
                            to={`/contracts/${item.contract_id}`}
                            className="text-primary-600 hover:underline"
                          >
                            {item.contract_filename}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500 capitalize">
                          {item.category?.replace(/_/g, ' ') || '-'}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500">
                          {item.owner || '-'}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500">
                          {item.due_date ? new Date(item.due_date).toLocaleDateString() : 'No date'}
                        </td>
                        <td className="px-4 py-3">
                          <span className={cn(
                            'px-2 py-0.5 rounded-full text-xs font-medium',
                            item.status === 'overdue' ? 'bg-red-100 text-red-800' :
                            item.status === 'completed' ? 'bg-green-100 text-green-800' :
                            item.status === 'in_progress' ? 'bg-blue-100 text-blue-800' :
                            item.status === 'waived' ? 'bg-gray-100 text-gray-600' :
                            'bg-amber-100 text-amber-800'
                          )}>
                            {item.status.replace(/_/g, ' ')}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <RAGBadge status={item.rag_status} />
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {activeTab === 'slas' && (
        <div className="space-y-4">
          {/* SLA Summary Stats */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatCard title="SLA Compliance" value={`${dashboard.slas.compliance_rate.toFixed(1)}%`} icon={CheckCircleIcon} color={dashboard.slas.compliance_rate >= 90 ? 'success' : 'warning'} variant="filled" chart={slaChart} />
            <StatCard title="Active SLAs" value={dashboard.slas.active_slas} icon={FlagIcon} color="primary" variant="filled" />
            <StatCard title="Breached" value={dashboard.slas.breached} icon={ExclamationTriangleIcon} color="danger" variant="filled" />
            <StatCard title="Penalties MTD" value={`$${dashboard.slas.total_penalties_mtd.toLocaleString()}`} icon={ChartBarIcon} color="warning" variant="filled" />
          </div>

          <div className="card">
            <div className="card-header flex items-center justify-between">
              <h3 className="font-medium text-gray-900">Recent SLA Breaches</h3>
              <span className="text-sm text-red-600">{dashboard.slas.critical_breaches} critical</span>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">SLA Name</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Contract</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Target</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actual</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Breaches</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Severity</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {dashboard.slas.recent_breaches.map((breach) => (
                    <tr
                      key={breach.sla_id}
                      className="hover:bg-gray-50 cursor-pointer"
                      onClick={() => setSelectedBreach({
                        sla_id: breach.sla_id,
                        sla_name: breach.sla_name,
                        contract_id: breach.contract_id,
                        contract_filename: breach.contract,
                        metric_type: breach.metric_type || 'custom',
                        target_value: breach.target_value || 0,
                        actual_value: breach.actual_value || 0,
                        deviation_percentage: breach.deviation || 0,
                        breach_severity: breach.severity,
                        measured_at: breach.measured_at || new Date().toISOString(),
                        penalty_amount: breach.penalty_amount || null,
                        consecutive_breaches: breach.breaches,
                      })}
                    >
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{breach.sla_name}</td>
                      <td className="px-4 py-3 text-sm text-gray-500">{breach.contract}</td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {breach.target_value ? `${breach.target_value.toFixed(1)}%` : '-'}
                      </td>
                      <td className="px-4 py-3 text-sm font-medium text-red-600">
                        {breach.actual_value ? `${breach.actual_value.toFixed(1)}%` : '-'}
                      </td>
                      <td className="px-4 py-3 text-sm font-medium text-red-600">{breach.breaches}</td>
                      <td className="px-4 py-3">
                        <span className={cn(
                          'px-2 py-0.5 rounded-full text-xs font-medium',
                          breach.severity === 'critical' ? 'bg-red-100 text-red-800' :
                          breach.severity === 'high' ? 'bg-amber-100 text-amber-800' :
                          breach.severity === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-gray-100 text-gray-800'
                        )}>
                          {breach.severity}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="p-3 border-t bg-gray-50 text-xs text-gray-500">
              Click on a row to view detailed breach information
            </div>
          </div>
        </div>
      )}

      {/* SLA Breach Detail Modal */}
      {selectedBreach && (
        <SLABreachDetailModal
          breach={selectedBreach}
          onClose={() => setSelectedBreach(null)}
        />
      )}

      {activeTab === 'milestones' && (
        <div className="space-y-4">
          {/* Milestone Summary Stats */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatCard
              title="Completion Rate"
              value={`${dashboard.milestones.completion_rate.toFixed(1)}%`}
              icon={CheckCircleIcon}
              color={dashboard.milestones.completion_rate >= 80 ? 'success' : dashboard.milestones.completion_rate >= 50 ? 'warning' : 'danger'}
              variant="filled"
              chart={obligationChart}
            />
            <StatCard title="Total Milestones" value={dashboard.milestones.total_milestones} icon={ClockIcon} color="primary" variant="filled" />
            <StatCard title="Overdue" value={dashboard.milestones.overdue} icon={ExclamationTriangleIcon} color="danger" variant="filled" />
            <StatCard title="At Risk" value={dashboard.milestones.at_risk} icon={ExclamationTriangleIcon} color="warning" variant="filled" />
          </div>

          {/* Completion Progress */}
          <div className="card">
            <div className="card-header">
              <h3 className="font-medium text-gray-900">Milestone Progress</h3>
            </div>
            <div className="p-4">
              <div className="flex items-center gap-4 mb-4">
                <div className="flex-1">
                  <div className="h-4 bg-gray-200 rounded-full overflow-hidden flex">
                    <div
                      className="h-full bg-green-500 transition-all"
                      style={{ width: `${dashboard.milestones.total_milestones > 0 ? (dashboard.milestones.completed / dashboard.milestones.total_milestones * 100) : 0}%` }}
                      title={`Completed: ${dashboard.milestones.completed}`}
                    />
                    <div
                      className="h-full bg-red-400 transition-all"
                      style={{ width: `${dashboard.milestones.total_milestones > 0 ? (dashboard.milestones.overdue / dashboard.milestones.total_milestones * 100) : 0}%` }}
                      title={`Overdue: ${dashboard.milestones.overdue}`}
                    />
                    <div
                      className="h-full bg-amber-400 transition-all"
                      style={{ width: `${dashboard.milestones.total_milestones > 0 ? (dashboard.milestones.at_risk / dashboard.milestones.total_milestones * 100) : 0}%` }}
                      title={`At Risk: ${dashboard.milestones.at_risk}`}
                    />
                  </div>
                </div>
              </div>
              <div className="flex gap-6 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-green-500" />
                  <span className="text-gray-600">Completed ({dashboard.milestones.completed})</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-400" />
                  <span className="text-gray-600">Overdue ({dashboard.milestones.overdue})</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-amber-400" />
                  <span className="text-gray-600">At Risk ({dashboard.milestones.at_risk})</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-gray-300" />
                  <span className="text-gray-600">
                    Remaining ({dashboard.milestones.total_milestones - dashboard.milestones.completed - dashboard.milestones.overdue - dashboard.milestones.at_risk})
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Due This Week */}
          <div className="card">
            <div className="card-header">
              <h3 className="font-medium text-gray-900">Due This Week</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Title</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Due Date</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {dashboard.milestones.due_this_week.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="px-4 py-8 text-center text-sm text-gray-500">
                        No milestones due this week
                      </td>
                    </tr>
                  ) : (
                    dashboard.milestones.due_this_week.map((ms) => (
                      <tr key={ms.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-medium text-gray-900">{ms.title}</td>
                        <td className="px-4 py-3 text-sm text-gray-500">
                          {ms.due_date ? new Date(ms.due_date).toLocaleDateString() : '-'}
                        </td>
                        <td className="px-4 py-3">
                          <span className={cn(
                            'px-2 py-0.5 rounded-full text-xs font-medium',
                            ms.status === 'overdue' ? 'bg-red-100 text-red-800' :
                            ms.status === 'completed' ? 'bg-green-100 text-green-800' :
                            ms.status === 'in_progress' ? 'bg-blue-100 text-blue-800' :
                            'bg-amber-100 text-amber-800'
                          )}>
                            {ms.status.replace(/_/g, ' ')}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'renewals' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatCard title="30 Days" value={dashboard.renewals.expiring_30_days} icon={ClockIcon} color="danger" variant="filled" />
            <StatCard title="60 Days" value={dashboard.renewals.expiring_60_days} icon={ClockIcon} color="warning" variant="filled" />
            <StatCard title="90 Days" value={dashboard.renewals.expiring_90_days} icon={ClockIcon} color="blue" variant="filled" />
            <StatCard
              title="Value at Risk"
              value={dashboard.renewals.total_value_at_risk ? `$${(dashboard.renewals.total_value_at_risk / 1000000).toFixed(1)}M` : '$0'}
              icon={ExclamationTriangleIcon}
              color="primary"
              variant="filled"
            />
          </div>

          <div className="card">
            <div className="card-header">
              <h3 className="font-medium text-gray-900">Upcoming Renewals</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Contract</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Counterparty</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Expiration</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Value</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Auto-Renew</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {dashboard.renewals.upcoming_renewals.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-500">
                        No contracts expiring in the next 90 days
                      </td>
                    </tr>
                  ) : (
                    dashboard.renewals.upcoming_renewals.map((renewal) => (
                      <tr key={renewal.contract_id} className="hover:bg-gray-50">
                        <td className="px-4 py-3">
                          <Link to={`/contracts/${renewal.contract_id}`} className="text-sm font-medium text-primary-600 hover:underline">
                            {renewal.filename}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500">{renewal.counterparty || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-500">
                          {renewal.expiration_date ? new Date(renewal.expiration_date).toLocaleDateString() : '-'}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-900">
                          {renewal.value ? `$${renewal.value.toLocaleString()}` : '-'}
                        </td>
                        <td className="px-4 py-3">
                          {renewal.auto_renewal ? (
                            <span className="text-green-600 text-sm">Yes</span>
                          ) : (
                            <span className="text-gray-400 text-sm">No</span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'vendors' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatCard title="Total Vendors" value={dashboard.vendors.total_vendors} icon={BuildingOfficeIcon} color="primary" variant="filled" />
            <StatCard title="At Risk" value={dashboard.vendors.at_risk_vendors} icon={ExclamationTriangleIcon} color="danger" variant="filled" />
            <StatCard
              title="Avg Score"
              value={dashboard.vendors.avg_performance_score.toFixed(1)}
              icon={ChartBarIcon}
              color={dashboard.vendors.avg_performance_score >= 70 ? 'success' : 'warning'}
              variant="filled"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Top Performers */}
            <div className="card">
              <div className="card-header">
                <h3 className="font-medium text-gray-900">Top Performers</h3>
              </div>
              <div className="divide-y divide-gray-200">
                {dashboard.vendors.top_performers.map((vendor, idx) => (
                  <div key={vendor.name} className="p-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="w-6 h-6 rounded-full bg-green-100 text-green-700 flex items-center justify-center text-xs font-medium">
                        {idx + 1}
                      </span>
                      <div>
                        <p className="text-sm font-medium text-gray-900">{vendor.name}</p>
                        <p className="text-xs text-gray-500">{vendor.contracts} contracts</p>
                      </div>
                    </div>
                    <span className="text-lg font-semibold text-green-600">{vendor.score.toFixed(1)}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Needs Attention */}
            <div className="card">
              <div className="card-header">
                <h3 className="font-medium text-gray-900">Needs Attention</h3>
              </div>
              <div className="divide-y divide-gray-200">
                {dashboard.vendors.bottom_performers.map((vendor, idx) => (
                  <div key={vendor.name} className="p-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="w-6 h-6 rounded-full bg-red-100 text-red-700 flex items-center justify-center text-xs font-medium">
                        {idx + 1}
                      </span>
                      <div>
                        <p className="text-sm font-medium text-gray-900">{vendor.name}</p>
                        <p className="text-xs text-gray-500">{vendor.contracts} contracts</p>
                      </div>
                    </div>
                    <span className="text-lg font-semibold text-red-600">{vendor.score.toFixed(1)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
