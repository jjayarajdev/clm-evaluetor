import { useState, useMemo, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
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
  ArrowDownTrayIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import PageHeader from '@/components/ui/PageHeader'
import StatCard from '@/components/ui/StatCard'
import { cn } from '@/lib/utils'
import type { PriorityAction } from '@/types/postsigning'
import type { ContractRenewalInfo, VendorListItem } from '@/types/postsigning'

interface SLABreachDetail {
  sla_id: string
  sla_name: string
  contract_id: string
  contract_filename: string
  metric_type: string
  metric_unit: string
  target_value: number
  actual_value: number
  target_display: string
  actual_display: string
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

interface SLARow {
  id: string
  contract_id: string
  contract_filename: string
  counterparty: string | null
  sla_name: string
  metric_type: string | null
  target_value: number | null
  compliance_rate: number | null
  consecutive_breaches: number
  severity: string
  has_penalty: boolean
}

interface MilestoneRow {
  id: string
  contract_id: string
  contract_filename: string
  counterparty: string | null
  title: string
  due_date: string | null
  status: string
  category: string | null
  owner: string | null
}

function RAGBadge({ status }: { status: string | null }) {
  const { t } = useTranslation()
  if (!status) return <span className="text-gray-400 text-xs">{t('postsigning.na')}</span>

  const colors: Record<string, string> = {
    green: 'bg-green-100 text-green-800',
    amber: 'bg-amber-100 text-amber-800',
    red: 'bg-red-100 text-red-800',
  }

  return (
    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', colors[status] || 'bg-gray-100 text-gray-800')}>
      {t(`postsigning.rag.${status}`, { defaultValue: status }).toUpperCase()}
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
  const { t } = useTranslation()
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
                {t('postsigning.severityBreach', { severity: t(`risk.${breach.breach_severity}`, { defaultValue: breach.breach_severity }).toUpperCase() })}
              </span>
              <span className="text-sm text-gray-500">
                {t('postsigning.consecutiveBreaches', { count: breach.consecutive_breaches })}
              </span>
            </div>

            {/* Metrics Comparison */}
            <div className="bg-gray-50 rounded-lg p-4">
              <h4 className="text-sm font-medium text-gray-700 mb-3">{t('postsigning.performanceMetrics')}</h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-gray-500 uppercase">{t('postsigning.target')}</p>
                  <p className="text-xl font-semibold text-gray-900">
                    {breach.target_display || `${breach.target_value}`}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase">{t('postsigning.actual')}</p>
                  <p className={cn('text-xl font-semibold', deviationColor)}>
                    {breach.actual_display || `${breach.actual_value}`}
                  </p>
                </div>
              </div>
              <div className="mt-3 pt-3 border-t border-gray-200">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-500">{t('postsigning.deviation')}</span>
                  <span className={cn('text-sm font-medium', deviationColor)}>
                    {breach.deviation_percentage > 0 ? '+' : ''}{breach.deviation_percentage.toFixed(1)}%
                  </span>
                </div>
              </div>
            </div>

            {/* Additional Info */}
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">{t('postsigning.metricType')}</span>
                <span className="font-medium text-gray-900 capitalize">
                  {breach.metric_type.replace(/_/g, ' ')}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">{t('postsigning.lastMeasured')}</span>
                <span className="font-medium text-gray-900">
                  {new Date(breach.measured_at).toLocaleString()}
                </span>
              </div>
              {breach.penalty_amount && (
                <div className="flex justify-between">
                  <span className="text-gray-500">{t('postsigning.penaltyAmount')}</span>
                  <span className="font-medium text-red-600">
                    ${breach.penalty_amount.toLocaleString()}
                  </span>
                </div>
              )}
            </div>

            {/* Progress Bar showing deviation — only for percentage metrics */}
            {breach.metric_unit === 'percentage' && (
              <div>
                <div className="flex justify-between text-xs text-gray-500 mb-1">
                  <span>0%</span>
                  <span>{t('postsigning.targetValue', { value: breach.target_value.toFixed(1) })}</span>
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
            )}
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-3 p-4 border-t bg-gray-50 rounded-b-lg">
            <Link
              to={`/contracts/${breach.contract_id}`}
              className="btn btn-secondary text-sm"
            >
              {t('postsigning.viewContract')}
            </Link>
            <button onClick={onClose} className="btn btn-primary text-sm">
              {t('postsigning.close')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function PriorityActionItem({ action }: { action: PriorityAction }) {
  const { t } = useTranslation()
  const severityColors: Record<string, string> = {
    critical: 'border-l-red-500 bg-red-50',
    high: 'border-l-amber-500 bg-amber-50',
    medium: 'border-l-blue-500 bg-blue-50',
  }

  const linkTarget = action.type === 'obligation' && action.obligation_id
    ? `/obligations/${action.obligation_id}`
    : (action.type === 'sla' || action.type === 'renewal') && action.contract_id
    ? `/contracts/${action.contract_id}`
    : null

  const content = (
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
          {t(`postsigning.actionType.${action.type}`, { defaultValue: action.type })}
        </span>
      </div>
    </div>
  )

  if (linkTarget) {
    return <Link to={linkTarget} className="block hover:opacity-80 transition-opacity">{content}</Link>
  }
  return content
}

export default function PostSigningPage() {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()

  // Translate item statuses, reusing existing status.* keys where available
  const statusLabel = (s: string) =>
    ['pending', 'completed'].includes(s)
      ? t(`status.${s}`)
      : t(`postsigning.status.${s}`, { defaultValue: s.replace(/_/g, ' ') })
  const [activeTab, setActiveTab] = useState<'overview' | 'obligations' | 'slas' | 'renewals' | 'vendors' | 'milestones'>('overview')
  const [selectedBreach, setSelectedBreach] = useState<SLABreachDetail | null>(null)
  const [oblStatusFilter, setOblStatusFilter] = useState<string>('')
  const [oblRagFilter, setOblRagFilter] = useState<string>('')
  const [slaSeverityFilter, setSlaSeverityFilter] = useState<string>('')
  const [slaBreachFilter, setSlaBreachFilter] = useState<string>('')
  const [msStatusFilter, setMsStatusFilter] = useState<string>('')
  const [isExporting, setIsExporting] = useState(false)
  const queryClient = useQueryClient()

  // Read URL params on mount (e.g. /compliance?tab=obligations&status=overdue)
  useEffect(() => {
    const tab = searchParams.get('tab')
    const status = searchParams.get('status')
    const rag = searchParams.get('rag')
    if (tab && ['overview', 'obligations', 'slas', 'renewals', 'vendors', 'milestones'].includes(tab)) {
      setActiveTab(tab as typeof activeTab)
    }
    if (status) setOblStatusFilter(status)
    if (rag) setOblRagFilter(rag)
    // Clear params after applying so they don't persist on tab switches
    if (tab || status || rag) {
      setSearchParams({}, { replace: true })
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

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

  // Fetch full SLA list when on SLAs tab
  const { data: allSLAs, isLoading: slasLoading } = useQuery({
    queryKey: ['postsigning-slas'],
    queryFn: () => api.getPostSigningSLAs(),
    enabled: activeTab === 'slas',
  })

  // Fetch full milestones list when on milestones tab
  const { data: allMilestones, isLoading: milestonesLoading } = useQuery({
    queryKey: ['postsigning-milestones'],
    queryFn: () => api.getPostSigningMilestones(),
    enabled: activeTab === 'milestones',
  })

  // Fetch renewal calendar when on renewals tab
  const { data: renewalCalendar, isLoading: renewalsLoading } = useQuery({
    queryKey: ['renewal-calendar'],
    queryFn: () => api.getRenewalCalendar(),
    enabled: activeTab === 'renewals',
  })

  // Fetch full vendor list when on vendors tab
  const { data: vendorData, isLoading: vendorsLoading } = useQuery({
    queryKey: ['vendor-list'],
    queryFn: () => api.getVendors({ sort_by: 'performance_score', sort_order: 'desc' }),
    enabled: activeTab === 'vendors',
  })

  // Renewal status update mutation
  const renewalStatusMutation = useMutation({
    mutationFn: ({ contractId, status }: { contractId: string; status: string }) =>
      api.updateRenewalStatus(contractId, { renewal_status: status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['renewal-calendar'] })
      queryClient.invalidateQueries({ queryKey: ['postsigning-dashboard'] })
    },
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

  // Filter SLAs locally
  const filteredSLAs = useMemo(() => {
    const slas = ((allSLAs || []) as SLARow[])
    return slas.filter(sla => {
      if (slaSeverityFilter && sla.severity !== slaSeverityFilter) return false
      if (slaBreachFilter === 'breached' && sla.consecutive_breaches === 0) return false
      if (slaBreachFilter === 'compliant' && sla.consecutive_breaches > 0) return false
      return true
    })
  }, [allSLAs, slaSeverityFilter, slaBreachFilter])

  // Filter milestones locally
  const filteredMilestones = useMemo(() => {
    const ms = ((allMilestones || []) as MilestoneRow[])
    if (!msStatusFilter) return ms
    return ms.filter(m => m.status === msStatusFilter)
  }, [allMilestones, msStatusFilter])

  // Flatten renewal calendar buckets into sorted list
  const allRenewals = useMemo((): ContractRenewalInfo[] => {
    if (!renewalCalendar) return []
    const items = [
      ...(renewalCalendar.expired || []),
      ...(renewalCalendar.critical || []),
      ...(renewalCalendar.within_30_days || []),
      ...(renewalCalendar.within_60_days || []),
      ...(renewalCalendar.within_90_days || []),
    ]
    return items.sort((a, b) => (a.days_until_expiration ?? 999) - (b.days_until_expiration ?? 999))
  }, [renewalCalendar])

  // Calendar export handler
  const handleExportCalendar = async () => {
    setIsExporting(true)
    try {
      const blob = await api.exportCalendarICS({
        include_expirations: true,
        include_notice_deadlines: true,
        include_obligations: true,
        include_key_dates: true,
        days_ahead: 365,
      })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `clm-calendar-${new Date().toISOString().split('T')[0]}.ics`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      console.error('Failed to export calendar:', err)
    } finally {
      setIsExporting(false)
    }
  }

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
        <p className="text-red-600">{t('postsigning.loadError')}</p>
      </div>
    )
  }

  const trendDirection = trendData?.overall_trend
  const trendChange = trendData?.overall_change_pct

  const tabs = [
    { id: 'overview', label: t('postsigning.tabs.overview'), icon: ChartBarIcon },
    { id: 'obligations', label: t('postsigning.tabs.obligations', { count: dashboard.obligations.total }), icon: CheckCircleIcon },
    { id: 'slas', label: t('postsigning.tabs.slas', { count: dashboard.slas.active_slas }), icon: FlagIcon },
    { id: 'milestones', label: t('postsigning.tabs.milestones', { count: dashboard.milestones.total_milestones }), icon: ClockIcon },
    { id: 'renewals', label: t('postsigning.tabs.renewals'), icon: CalendarIcon },
    { id: 'vendors', label: t('postsigning.tabs.vendors', { count: dashboard.vendors.total_vendors }), icon: BuildingOfficeIcon },
  ]

  const obligations = (allObligations || []) as ObligationRow[]

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title={t('postsigning.title')}
        description={t('postsigning.description')}
        icon={ShieldCheckIcon}
        variant="bordered"
        actions={
          <Link
            to="/reports"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 transition-colors"
          >
            <DocumentChartBarIcon className="h-4 w-4" />
            {t('postsigning.generateReport')}
          </Link>
        }
      />

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title={t('postsigning.overallCompliance')}
          value={`${dashboard.compliance.overall_compliance_rate.toFixed(1)}%`}
          subtitle={trendDirection ? t('postsigning.trendSubtitle', { direction: t(`postsigning.trendDirections.${trendDirection}`, { defaultValue: trendDirection }) }) : undefined}
          icon={CheckCircleIcon}
          color={dashboard.compliance.overall_compliance_rate >= 90 ? 'success' : dashboard.compliance.overall_compliance_rate >= 70 ? 'warning' : 'danger'}
          variant="filled"
          chart={complianceChart}
          trend={trendChange != null ? { value: Math.round(trendChange), label: t('postsigning.vsLastPeriod') } : undefined}
        />
        <StatCard
          title={t('postsigning.contractsAtRisk')}
          value={dashboard.contracts_needing_attention}
          subtitle={t('postsigning.priorityActionsCount', { count: dashboard.compliance.high_priority_actions })}
          icon={ExclamationTriangleIcon}
          color={dashboard.contracts_needing_attention > 0 ? 'danger' : 'success'}
          variant="filled"
          chart={breachChart}
        />
        <StatCard
          title={t('postsigning.activeContracts')}
          value={dashboard.total_contracts}
          subtitle={dashboard.total_value ? t('postsigning.totalValueSubtitle', { value: (dashboard.total_value / 1000000).toFixed(1) }) : t('postsigning.na')}
          icon={ChartBarIcon}
          color="primary"
          variant="filled"
        />
        <StatCard
          title={t('postsigning.renewals90Days')}
          value={dashboard.renewals.expiring_90_days}
          subtitle={t('postsigning.pastNoticeDeadlineCount', { count: dashboard.renewals.past_notice_deadline })}
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
              <h3 className="font-medium text-gray-900">{t('postsigning.priorityActions')}</h3>
            </div>
            <div className="p-4 space-y-3">
              {dashboard.priority_actions.length > 0 ? (
                dashboard.priority_actions.map((action, idx) => (
                  <PriorityActionItem key={idx} action={action} />
                ))
              ) : (
                <p className="text-sm text-gray-500 text-center py-4">{t('postsigning.noPriorityActions')}</p>
              )}
            </div>
          </div>

          {/* Quick Stats Sidebar */}
          <div className="space-y-4">
            {/* Obligations Summary */}
            <div className="card">
              <div className="card-header flex items-center justify-between">
                <h3 className="font-medium text-gray-900">{t('postsigning.obligations')}</h3>
                <button
                  onClick={() => setActiveTab('obligations')}
                  className="text-xs text-primary-600 hover:underline"
                >
                  {t('postsigning.viewAll')}
                </button>
              </div>
              <div className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-2xl font-bold text-gray-900">
                    {dashboard.obligations.compliance_rate.toFixed(1)}%
                  </span>
                  <span className="text-sm text-gray-500">{t('postsigning.compliance')}</span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">{t('status.completed')}</span>
                    <span className="font-medium text-green-600">{dashboard.obligations.completed}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">{t('postsigning.status.in_progress')}</span>
                    <span className="font-medium text-blue-600">{dashboard.obligations.in_progress}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">{t('postsigning.status.overdue')}</span>
                    <span className="font-medium text-red-600">{dashboard.obligations.overdue}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">{t('postsigning.atRisk')}</span>
                    <span className="font-medium text-amber-600">{dashboard.obligations.at_risk}</span>
                  </div>
                </div>
                <div className="mt-3 flex gap-2">
                  <div className="flex-1 text-center py-1 rounded bg-green-50 text-green-700 text-xs">
                    {dashboard.obligations.green} {t('postsigning.rag.green')}
                  </div>
                  <div className="flex-1 text-center py-1 rounded bg-amber-50 text-amber-700 text-xs">
                    {dashboard.obligations.amber} {t('postsigning.rag.amber')}
                  </div>
                  <div className="flex-1 text-center py-1 rounded bg-red-50 text-red-700 text-xs">
                    {dashboard.obligations.red} {t('postsigning.rag.red')}
                  </div>
                </div>
              </div>
            </div>

            {/* SLA Summary */}
            <div className="card">
              <div className="card-header flex items-center justify-between">
                <h3 className="font-medium text-gray-900">{t('postsigning.slaPerformance')}</h3>
                <button
                  onClick={() => setActiveTab('slas')}
                  className="text-xs text-primary-600 hover:underline"
                >
                  {t('postsigning.viewAll')}
                </button>
              </div>
              <div className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-2xl font-bold text-gray-900">
                    {dashboard.slas.compliance_rate.toFixed(1)}%
                  </span>
                  <span className="text-sm text-gray-500">{t('postsigning.compliance')}</span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">{t('postsigning.activeSlas')}</span>
                    <span className="font-medium">{dashboard.slas.active_slas}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">{t('status.breached')}</span>
                    <span className="font-medium text-red-600">{dashboard.slas.breached}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">{t('postsigning.penaltiesMtd')}</span>
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
                <h3 className="font-medium text-gray-900">{t('postsigning.milestones')}</h3>
                <button
                  onClick={() => setActiveTab('milestones')}
                  className="text-xs text-primary-600 hover:underline"
                >
                  {t('postsigning.viewAll')}
                </button>
              </div>
              <div className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-2xl font-bold text-gray-900">
                    {dashboard.milestones.completion_rate.toFixed(1)}%
                  </span>
                  <span className="text-sm text-gray-500">{t('postsigning.complete')}</span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">{t('postsigning.total')}</span>
                    <span className="font-medium">{dashboard.milestones.total_milestones}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">{t('status.completed')}</span>
                    <span className="font-medium text-green-600">{dashboard.milestones.completed}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">{t('postsigning.status.overdue')}</span>
                    <span className="font-medium text-red-600">{dashboard.milestones.overdue}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">{t('postsigning.atRisk')}</span>
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
                    {t('postsigning.completedOfTotal', { completed: dashboard.milestones.completed, total: dashboard.milestones.total_milestones })}
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
            <h3 className="font-medium text-gray-900">{t('postsigning.allObligations')}</h3>
            <div className="flex items-center gap-3">
              {/* Status filter */}
              <div className="flex items-center gap-1.5">
                <FunnelIcon className="h-4 w-4 text-gray-400" />
                <select
                  value={oblStatusFilter}
                  onChange={(e) => setOblStatusFilter(e.target.value)}
                  className="text-sm border-gray-300 rounded-md py-1 pl-2 pr-7"
                >
                  <option value="">{t('postsigning.allStatuses')}</option>
                  <option value="pending">{t('status.pending')}</option>
                  <option value="in_progress">{t('postsigning.status.in_progress')}</option>
                  <option value="completed">{t('status.completed')}</option>
                  <option value="overdue">{t('postsigning.status.overdue')}</option>
                  <option value="waived">{t('postsigning.status.waived')}</option>
                </select>
              </div>
              {/* RAG filter */}
              <select
                value={oblRagFilter}
                onChange={(e) => setOblRagFilter(e.target.value)}
                className="text-sm border-gray-300 rounded-md py-1 pl-2 pr-7"
              >
                <option value="">{t('postsigning.allRag')}</option>
                <option value="green">{t('postsigning.rag.green')}</option>
                <option value="amber">{t('postsigning.rag.amber')}</option>
                <option value="red">{t('postsigning.rag.red')}</option>
              </select>
              <span className="text-sm text-gray-500">
                {oblLoading ? '...' : t('postsigning.itemsCount', { count: obligations.length })}
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
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.titleColumn')}</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.contract')}</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.category')}</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.owner')}</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.dueDate')}</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('common.status')}</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.ragColumn')}</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {obligations.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-sm text-gray-500">
                        {t('postsigning.noObligationsFound')}
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
                          {item.due_date ? new Date(item.due_date).toLocaleDateString() : t('postsigning.noDate')}
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
                            {statusLabel(item.status)}
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
            <StatCard title={t('postsigning.slaCompliance')} value={`${dashboard.slas.compliance_rate.toFixed(1)}%`} icon={CheckCircleIcon} color={dashboard.slas.compliance_rate >= 90 ? 'success' : 'warning'} variant="filled" chart={slaChart} />
            <StatCard title={t('postsigning.activeSlas')} value={dashboard.slas.active_slas} icon={FlagIcon} color="primary" variant="filled" />
            <StatCard title={t('status.breached')} value={dashboard.slas.breached} icon={ExclamationTriangleIcon} color="danger" variant="filled" />
            <StatCard title={t('postsigning.penaltiesMtd')} value={`$${dashboard.slas.total_penalties_mtd.toLocaleString()}`} icon={ChartBarIcon} color="warning" variant="filled" />
          </div>

          {/* All Active SLAs */}
          <div className="card">
            <div className="card-header flex items-center justify-between">
              <h3 className="font-medium text-gray-900">{t('postsigning.allActiveSlas')}</h3>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5">
                  <FunnelIcon className="h-4 w-4 text-gray-400" />
                  <select
                    value={slaSeverityFilter}
                    onChange={(e) => setSlaSeverityFilter(e.target.value)}
                    className="text-sm border-gray-300 rounded-md py-1 pl-2 pr-7"
                  >
                    <option value="">{t('postsigning.allSeverities')}</option>
                    <option value="critical">{t('risk.critical')}</option>
                    <option value="high">{t('risk.high')}</option>
                    <option value="medium">{t('risk.medium')}</option>
                    <option value="low">{t('risk.low')}</option>
                  </select>
                </div>
                <select
                  value={slaBreachFilter}
                  onChange={(e) => setSlaBreachFilter(e.target.value)}
                  className="text-sm border-gray-300 rounded-md py-1 pl-2 pr-7"
                >
                  <option value="">{t('postsigning.allSlas')}</option>
                  <option value="breached">{t('postsigning.breachedOnly')}</option>
                  <option value="compliant">{t('postsigning.noBreaches')}</option>
                </select>
                <span className="text-sm text-gray-500">{t('postsigning.slasCount', { count: filteredSLAs.length })}</span>
              </div>
            </div>
            {slasLoading ? (
              <div className="flex items-center justify-center py-8">
                <LoadingSpinner size="md" />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.slaName')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.contract')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.metric')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.target')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.complianceColumn')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.breaches')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.severity')}</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {filteredSLAs.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="px-4 py-8 text-center text-sm text-gray-500">
                          {t('postsigning.noActiveSlas')}
                        </td>
                      </tr>
                    ) : (
                      filteredSLAs.map((sla) => (
                        <tr key={sla.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">
                            <Link to={`/contracts/${sla.contract_id}`} className="hover:text-primary-600 hover:underline">
                              {sla.sla_name}
                            </Link>
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-500 max-w-[200px] truncate">
                            <Link to={`/contracts/${sla.contract_id}`} className="text-primary-600 hover:underline">
                              {sla.contract_filename}
                            </Link>
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-500">
                            {sla.metric_type?.replace(/_/g, ' ') || '-'}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-700 font-medium">
                            {sla.target_value != null ? sla.target_value : '-'}
                          </td>
                          <td className="px-4 py-3">
                            {sla.compliance_rate != null ? (
                              <span className={cn(
                                'text-sm font-medium',
                                sla.compliance_rate >= 90 ? 'text-green-600' :
                                sla.compliance_rate >= 70 ? 'text-amber-600' :
                                'text-red-600'
                              )}>
                                {sla.compliance_rate.toFixed(1)}%
                              </span>
                            ) : (
                              <span className="text-sm text-gray-400">{t('postsigning.na')}</span>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            {sla.consecutive_breaches > 0 ? (
                              <span className="text-sm font-medium text-red-600">{sla.consecutive_breaches}</span>
                            ) : (
                              <span className="text-sm text-green-600">0</span>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <span className={cn(
                              'px-2 py-0.5 rounded-full text-xs font-medium',
                              sla.severity === 'critical' ? 'bg-red-100 text-red-800' :
                              sla.severity === 'high' ? 'bg-amber-100 text-amber-800' :
                              sla.severity === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                              'bg-gray-100 text-gray-800'
                            )}>
                              {t(`risk.${sla.severity}`, { defaultValue: sla.severity })}
                            </span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Recent SLA Breaches (only show if there are breaches) */}
          {dashboard.slas.recent_breaches.length > 0 && (
            <div className="card">
              <div className="card-header flex items-center justify-between">
                <h3 className="font-medium text-gray-900">{t('postsigning.recentSlaBreaches')}</h3>
                <span className="text-sm text-red-600">{t('postsigning.criticalCount', { count: dashboard.slas.critical_breaches })}</span>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.slaName')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.contract')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.target')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.actual')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.consecFails')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.severity')}</th>
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
                          metric_unit: breach.metric_unit || 'percentage',
                          target_value: breach.target_value || 0,
                          actual_value: breach.actual_value || 0,
                          target_display: breach.target_display || '',
                          actual_display: breach.actual_display || '',
                          deviation_percentage: breach.deviation || 0,
                          breach_severity: breach.severity,
                          measured_at: breach.measured_at || new Date().toISOString(),
                          penalty_amount: breach.penalty_amount || null,
                          consecutive_breaches: breach.breaches,
                        })}
                      >
                        <td className="px-4 py-3 text-sm font-medium text-gray-900">{breach.sla_name}</td>
                        <td className="px-4 py-3 text-sm text-gray-500 max-w-[200px] truncate">{breach.contract}</td>
                        <td className="px-4 py-3 text-sm text-gray-500">
                          {breach.target_display || '-'}
                        </td>
                        <td className="px-4 py-3 text-sm font-medium text-red-600">
                          {breach.actual_display || '-'}
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
                            {t(`risk.${breach.severity}`, { defaultValue: breach.severity })}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="p-3 border-t bg-gray-50 text-xs text-gray-500">
                {t('postsigning.clickRowForDetails')}
              </div>
            </div>
          )}
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
              title={t('postsigning.completionRate')}
              value={`${dashboard.milestones.completion_rate.toFixed(1)}%`}
              icon={CheckCircleIcon}
              color={dashboard.milestones.completion_rate >= 80 ? 'success' : dashboard.milestones.completion_rate >= 50 ? 'warning' : 'danger'}
              variant="filled"
              chart={obligationChart}
            />
            <StatCard title={t('postsigning.totalMilestones')} value={dashboard.milestones.total_milestones} icon={ClockIcon} color="primary" variant="filled" />
            <StatCard title={t('postsigning.status.overdue')} value={dashboard.milestones.overdue} icon={ExclamationTriangleIcon} color="danger" variant="filled" />
            <StatCard title={t('postsigning.atRisk')} value={dashboard.milestones.at_risk} icon={ExclamationTriangleIcon} color="warning" variant="filled" />
          </div>

          {/* Completion Progress */}
          <div className="card">
            <div className="card-header">
              <h3 className="font-medium text-gray-900">{t('postsigning.milestoneProgress')}</h3>
            </div>
            <div className="p-4">
              <div className="flex items-center gap-4 mb-4">
                <div className="flex-1">
                  <div className="h-4 bg-gray-200 rounded-full overflow-hidden flex">
                    <div
                      className="h-full bg-green-500 transition-all"
                      style={{ width: `${dashboard.milestones.total_milestones > 0 ? (dashboard.milestones.completed / dashboard.milestones.total_milestones * 100) : 0}%` }}
                      title={`${t('status.completed')}: ${dashboard.milestones.completed}`}
                    />
                    <div
                      className="h-full bg-red-400 transition-all"
                      style={{ width: `${dashboard.milestones.total_milestones > 0 ? (dashboard.milestones.overdue / dashboard.milestones.total_milestones * 100) : 0}%` }}
                      title={`${t('postsigning.status.overdue')}: ${dashboard.milestones.overdue}`}
                    />
                    <div
                      className="h-full bg-amber-400 transition-all"
                      style={{ width: `${dashboard.milestones.total_milestones > 0 ? (dashboard.milestones.at_risk / dashboard.milestones.total_milestones * 100) : 0}%` }}
                      title={`${t('postsigning.atRisk')}: ${dashboard.milestones.at_risk}`}
                    />
                  </div>
                </div>
              </div>
              <div className="flex gap-6 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-green-500" />
                  <span className="text-gray-600">{t('status.completed')} ({dashboard.milestones.completed})</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-400" />
                  <span className="text-gray-600">{t('postsigning.status.overdue')} ({dashboard.milestones.overdue})</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-amber-400" />
                  <span className="text-gray-600">{t('postsigning.atRisk')} ({dashboard.milestones.at_risk})</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-gray-300" />
                  <span className="text-gray-600">
                    {t('postsigning.remaining')} ({dashboard.milestones.total_milestones - dashboard.milestones.completed - dashboard.milestones.overdue - dashboard.milestones.at_risk})
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* All Milestones */}
          <div className="card">
            <div className="card-header flex items-center justify-between">
              <h3 className="font-medium text-gray-900">{t('postsigning.allMilestones')}</h3>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5">
                  <FunnelIcon className="h-4 w-4 text-gray-400" />
                  <select
                    value={msStatusFilter}
                    onChange={(e) => setMsStatusFilter(e.target.value)}
                    className="text-sm border-gray-300 rounded-md py-1 pl-2 pr-7"
                  >
                    <option value="">{t('postsigning.allStatuses')}</option>
                    <option value="pending">{t('status.pending')}</option>
                    <option value="in_progress">{t('postsigning.status.in_progress')}</option>
                    <option value="completed">{t('status.completed')}</option>
                    <option value="overdue">{t('postsigning.status.overdue')}</option>
                  </select>
                </div>
                <span className="text-sm text-gray-500">{t('postsigning.milestonesCount', { count: filteredMilestones.length })}</span>
              </div>
            </div>
            {milestonesLoading ? (
              <div className="flex items-center justify-center py-8">
                <LoadingSpinner size="md" />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.titleColumn')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.contract')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.owner')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.dueDate')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('common.status')}</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {filteredMilestones.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-500">
                          {t('postsigning.noMilestonesFound')}
                        </td>
                      </tr>
                    ) : (
                      filteredMilestones.map((ms) => (
                        <tr key={ms.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">
                            <Link to={`/obligations/${ms.id}`} className="hover:text-primary-600 hover:underline">
                              {ms.title}
                            </Link>
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-500 max-w-[200px] truncate">
                            <Link to={`/contracts/${ms.contract_id}`} className="text-primary-600 hover:underline">
                              {ms.contract_filename}
                            </Link>
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-500">{ms.owner || '-'}</td>
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
                              {statusLabel(ms.status)}
                            </span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'renewals' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatCard title={t('renewals.days30')} value={dashboard.renewals.expiring_30_days} icon={ClockIcon} color="danger" variant="filled" />
            <StatCard title={t('renewals.days60')} value={dashboard.renewals.expiring_60_days} icon={ClockIcon} color="warning" variant="filled" />
            <StatCard title={t('renewals.days90')} value={dashboard.renewals.expiring_90_days} icon={ClockIcon} color="blue" variant="filled" />
            <StatCard
              title={t('renewals.valueAtRisk')}
              value={dashboard.renewals.total_value_at_risk ? `$${(dashboard.renewals.total_value_at_risk / 1000000).toFixed(1)}M` : '$0'}
              icon={ExclamationTriangleIcon}
              color="primary"
              variant="filled"
            />
          </div>

          <div className="card">
            <div className="card-header flex items-center justify-between">
              <h3 className="font-medium text-gray-900">{t('renewals.title')}</h3>
              <div className="flex items-center gap-3">
                <Link to="/renewals" className="inline-flex items-center gap-1 text-sm text-primary-600 hover:underline">
                  {t('postsigning.viewFullCalendar')}
                  <ArrowTopRightOnSquareIcon className="h-3.5 w-3.5" />
                </Link>
                <button
                  onClick={handleExportCalendar}
                  disabled={isExporting}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
                >
                  <ArrowDownTrayIcon className="h-4 w-4" />
                  {isExporting ? t('renewals.exporting') : t('postsigning.exportCalendar')}
                </button>
              </div>
            </div>
            {renewalsLoading ? (
              <div className="flex items-center justify-center py-8"><LoadingSpinner size="md" /></div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.contract')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('contracts.counterparty')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.type')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('renewals.expiration')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.daysLeft')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.risk')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('renewals.autoRenew')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('common.status')}</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {allRenewals.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="px-4 py-8 text-center text-sm text-gray-500">
                          {t('postsigning.noContractsApproachingRenewal')}
                        </td>
                      </tr>
                    ) : (
                      allRenewals.map((r) => (
                        <tr key={r.contract_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3">
                            <Link to={`/contracts/${r.contract_id}`} className="text-sm font-medium text-primary-600 hover:underline">
                              {r.filename}
                            </Link>
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-500">{r.counterparty || '-'}</td>
                          <td className="px-4 py-3 text-sm text-gray-500 capitalize">{r.contract_type?.replace(/_/g, ' ') || '-'}</td>
                          <td className="px-4 py-3 text-sm text-gray-500">
                            {r.expiration_date ? new Date(r.expiration_date).toLocaleDateString() : '-'}
                          </td>
                          <td className="px-4 py-3">
                            <span className={cn(
                              'text-sm font-medium',
                              (r.days_until_expiration ?? 999) <= 0 ? 'text-red-700' :
                              (r.days_until_expiration ?? 999) <= 30 ? 'text-red-600' :
                              (r.days_until_expiration ?? 999) <= 60 ? 'text-amber-600' :
                              'text-gray-700'
                            )}>
                              {r.days_until_expiration != null
                                ? r.days_until_expiration <= 0
                                  ? t('postsigning.daysOverdue', { days: Math.abs(r.days_until_expiration) })
                                  : t('postsigning.daysShort', { days: r.days_until_expiration })
                                : '-'}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            {r.risk_level ? (
                              <span className={cn(
                                'px-2 py-0.5 rounded-full text-xs font-medium',
                                r.risk_level === 'critical' ? 'bg-red-100 text-red-800' :
                                r.risk_level === 'high' ? 'bg-amber-100 text-amber-800' :
                                r.risk_level === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                                'bg-green-100 text-green-800'
                              )}>
                                {t(`risk.${r.risk_level}`, { defaultValue: r.risk_level })}
                              </span>
                            ) : <span className="text-sm text-gray-400">-</span>}
                          </td>
                          <td className="px-4 py-3">
                            {r.auto_renewal ? (
                              <span className="text-green-600 text-sm">{t('common.yes')}</span>
                            ) : (
                              <span className="text-gray-400 text-sm">{t('common.no')}</span>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <select
                              value={r.renewal_status || 'pending_review'}
                              onChange={(e) => renewalStatusMutation.mutate({ contractId: r.contract_id, status: e.target.value })}
                              className={cn(
                                'text-xs font-medium rounded-md py-1 pl-2 pr-6 border',
                                r.renewal_status === 'approved' ? 'bg-green-50 text-green-700 border-green-200' :
                                r.renewal_status === 'declined' ? 'bg-red-50 text-red-700 border-red-200' :
                                r.renewal_status === 'renegotiating' ? 'bg-blue-50 text-blue-700 border-blue-200' :
                                'bg-gray-50 text-gray-700 border-gray-200'
                              )}
                            >
                              <option value="pending_review">{t('postsigning.renewalStatus.pending_review')}</option>
                              <option value="approved">{t('postsigning.renewalStatus.approved')}</option>
                              <option value="declined">{t('postsigning.renewalStatus.declined')}</option>
                              <option value="renegotiating">{t('postsigning.renewalStatus.renegotiating')}</option>
                            </select>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'vendors' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatCard title={t('vendors.totalVendors')} value={dashboard.vendors.total_vendors} icon={BuildingOfficeIcon} color="primary" variant="filled" />
            <StatCard title={t('vendors.atRisk')} value={dashboard.vendors.at_risk_vendors} icon={ExclamationTriangleIcon} color="danger" variant="filled" />
            <StatCard
              title={t('vendors.avgScore')}
              value={dashboard.vendors.avg_performance_score.toFixed(1)}
              icon={ChartBarIcon}
              color={dashboard.vendors.avg_performance_score >= 70 ? 'success' : 'warning'}
              variant="filled"
            />
          </div>

          <div className="card">
            <div className="card-header flex items-center justify-between">
              <h3 className="font-medium text-gray-900">{t('postsigning.allVendorsCounterparties')}</h3>
              <div className="flex items-center gap-3">
                <Link to="/vendors" className="inline-flex items-center gap-1 text-sm text-primary-600 hover:underline">
                  {t('postsigning.viewDetails')}
                  <ArrowTopRightOnSquareIcon className="h-3.5 w-3.5" />
                </Link>
                <span className="text-sm text-gray-500">
                  {vendorsLoading ? '...' : t('postsigning.vendorsCount', { count: (vendorData?.vendors || []).length })}
                </span>
              </div>
            </div>
            {vendorsLoading ? (
              <div className="flex items-center justify-center py-8"><LoadingSpinner size="md" /></div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('vendors.vendor')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('vendors.score')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('vendors.risk')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('vendors.contracts')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('vendors.exposure')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.oblPercent')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('postsigning.slaPercent')}</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('vendors.breaches')}</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {(vendorData?.vendors || []).length === 0 ? (
                      <tr>
                        <td colSpan={8} className="px-4 py-8 text-center text-sm text-gray-500">
                          {t('postsigning.noVendorData')}
                        </td>
                      </tr>
                    ) : (
                      (vendorData?.vendors || []).map((v: VendorListItem) => (
                        <tr key={v.vendor_name} className="hover:bg-gray-50">
                          <td className="px-4 py-3">
                            <Link to="/vendors" className="text-sm font-medium text-primary-600 hover:underline">
                              {v.vendor_name}
                            </Link>
                          </td>
                          <td className="px-4 py-3">
                            <span className={cn(
                              'text-sm font-semibold',
                              v.performance_score >= 80 ? 'text-green-600' :
                              v.performance_score >= 60 ? 'text-amber-600' :
                              'text-red-600'
                            )}>
                              {v.performance_score.toFixed(1)}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={cn(
                              'px-2 py-0.5 rounded-full text-xs font-medium',
                              v.risk_level === 'high' ? 'bg-red-100 text-red-800' :
                              v.risk_level === 'medium' ? 'bg-amber-100 text-amber-800' :
                              'bg-green-100 text-green-800'
                            )}>
                              {t(`risk.${v.risk_level}`, { defaultValue: v.risk_level })}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-700">{v.contract_count}</td>
                          <td className="px-4 py-3 text-sm text-gray-700">
                            {v.total_exposure ? `$${(v.total_exposure / 1000).toFixed(0)}k` : '-'}
                          </td>
                          <td className="px-4 py-3">
                            {v.obligation_compliance_rate != null ? (
                              <span className={cn(
                                'text-sm font-medium',
                                v.obligation_compliance_rate >= 90 ? 'text-green-600' :
                                v.obligation_compliance_rate >= 70 ? 'text-amber-600' :
                                'text-red-600'
                              )}>
                                {v.obligation_compliance_rate.toFixed(0)}%
                              </span>
                            ) : <span className="text-sm text-gray-400">{t('postsigning.na')}</span>}
                          </td>
                          <td className="px-4 py-3">
                            {v.sla_compliance_rate != null ? (
                              <span className={cn(
                                'text-sm font-medium',
                                v.sla_compliance_rate >= 90 ? 'text-green-600' :
                                v.sla_compliance_rate >= 70 ? 'text-amber-600' :
                                'text-red-600'
                              )}>
                                {v.sla_compliance_rate.toFixed(0)}%
                              </span>
                            ) : <span className="text-sm text-gray-400">{t('postsigning.na')}</span>}
                          </td>
                          <td className="px-4 py-3">
                            {v.active_breaches > 0 ? (
                              <span className="text-sm font-medium text-red-600">{v.active_breaches}</span>
                            ) : (
                              <span className="text-sm text-green-600">0</span>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
