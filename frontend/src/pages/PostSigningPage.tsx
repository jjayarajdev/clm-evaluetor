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
  PaperClipIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import PageHeader from '@/components/ui/PageHeader'
import StatCard from '@/components/ui/StatCard'
import { cn, formatCurrency } from '@/lib/utils'
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
  has_evidence?: boolean
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
    queryFn: () => api.getVendors({ sort_by: 'score', sort_order: 'desc' }),
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

  // SLA measurement recording (manual now; a ServiceNow/ITSM pull can post to the
  // same endpoint later). Write roles only.
  const { user } = useAuth()
  const canRecord = ['super_admin', 'admin', 'legal', 'procurement', 'bu_head'].includes(user?.role || '')
  const [measureSla, setMeasureSla] = useState<SLARow | null>(null)
  const [actualValue, setActualValue] = useState('')
  const [measureNotes, setMeasureNotes] = useState('')
  const [measureError, setMeasureError] = useState<string | null>(null)
  const recordMeasurementMutation = useMutation({
    mutationFn: ({ contractId, slaId, actual, notes }: { contractId: string; slaId: string; actual: number; notes?: string }) =>
      api.logSLAPerformance(contractId, slaId, { actual_value: actual, notes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['postsigning-slas'] })
      queryClient.invalidateQueries({ queryKey: ['postsigning-dashboard'] })
      setMeasureSla(null)
      setActualValue('')
      setMeasureNotes('')
      setMeasureError(null)
    },
    onError: (e: unknown) => setMeasureError(e instanceof Error ? e.message : t('postsigning.recordFailed', { defaultValue: 'Could not record the measurement.' })),
  })

  const submitMeasurement = () => {
    const val = Number(actualValue)
    if (!measureSla || actualValue.trim() === '' || Number.isNaN(val)) {
      setMeasureError(t('postsigning.recordInvalid', { defaultValue: 'Enter a numeric value.' }))
      return
    }
    setMeasureError(null)
    recordMeasurementMutation.mutate({ contractId: measureSla.contract_id, slaId: measureSla.id, actual: val, notes: measureNotes.trim() || undefined })
  }

  // Build sparkline data from trend
  const obligationChart = useMemo(() => {
    if (!trendData?.data_points?.length) return undefined
    return trendData.data_points.map(p => Math.round(p.obligation_compliance_rate))
  }, [trendData])

  const slaChart = useMemo(() => {
    if (!trendData?.data_points?.length) return undefined
    return trendData.data_points.map(p => Math.round(p.sla_compliance_rate))
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

  // A rate is only meaningful once the backend actually measured it (null = not measured).
  const slaMeasured = dashboard.slas.compliance_rate != null
  const msMeasured = dashboard.milestones.completion_rate != null

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

      {/* Summary Stats — fact-derived signals only */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title={t('postsigning.activeContracts')}
          value={dashboard.total_contracts}
          subtitle={dashboard.valued_contracts && dashboard.valued_contracts > 0
            ? t('postsigning.valueCoverage', { value: formatCurrency(dashboard.total_value, dashboard.total_value_currency || 'USD'), valued: dashboard.valued_contracts, total: dashboard.total_contracts })
            : t('postsigning.na')}
          icon={ChartBarIcon}
          color="primary"
          variant="filled"
        />
        <StatCard
          title={t('postsigning.renewals90Days')}
          value={dashboard.renewals.expiring_90_days}
          subtitle={
            dashboard.renewals.expiring_90_days === 0 && (dashboard.renewals.expired_count || dashboard.renewals.no_date_count)
              ? t('postsigning.renewalsContext', {
                  expired: dashboard.renewals.expired_count ?? 0,
                  undated: dashboard.renewals.no_date_count ?? 0,
                })
              : t('postsigning.pastNoticeDeadlineCount', { count: dashboard.renewals.past_notice_deadline })
          }
          icon={CalendarIcon}
          color={dashboard.renewals.past_notice_deadline > 0 ? 'warning' : 'default'}
          variant="filled"
        />
        <StatCard
          title={t('postsigning.tabs.vendors', { count: dashboard.vendors.total_vendors })}
          value={dashboard.vendors.total_vendors}
          subtitle={t('postsigning.vendorsSubtitle')}
          icon={BuildingOfficeIcon}
          color="primary"
          variant="filled"
        />
        <StatCard
          title={t('postsigning.obligationsTracked')}
          value={dashboard.obligations.total}
          subtitle={t('postsigning.extractedUntracked')}
          icon={CheckCircleIcon}
          color="default"
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
          {/* Renewals coming up — fact-derived from expiration dates */}
          <div className="lg:col-span-2 card">
            <div className="card-header flex items-center justify-between">
              <h3 className="font-medium text-gray-900">{t('postsigning.renewalsComingUp')}</h3>
              <button
                onClick={() => setActiveTab('renewals')}
                className="text-xs text-primary-600 hover:underline"
              >
                {t('postsigning.viewAll')}
              </button>
            </div>
            <div className="p-4">
              {dashboard.renewals.upcoming_renewals.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500 border-b border-gray-200">
                        <th className="py-2 pr-4">{t('postsigning.colContract')}</th>
                        <th className="py-2 pr-4">{t('postsigning.colCounterparty')}</th>
                        <th className="py-2 pr-4">{t('postsigning.colExpires')}</th>
                        <th className="py-2 pr-4 text-right">{t('postsigning.colDays')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dashboard.renewals.upcoming_renewals.slice(0, 8).map((r) => {
                        const days = r.expiration_date
                          ? Math.ceil((new Date(r.expiration_date).getTime() - Date.now()) / 86400000)
                          : null
                        return (
                          <tr key={r.contract_id} className="border-b border-gray-100">
                            <td className="py-2 pr-4 max-w-xs truncate">
                              <Link to={`/contracts/${r.contract_id}`} className="text-primary-600 hover:underline font-medium">
                                {r.filename}
                              </Link>
                            </td>
                            <td className="py-2 pr-4 text-gray-600">{r.counterparty || '—'}</td>
                            <td className="py-2 pr-4 text-gray-600">{r.expiration_date || '—'}</td>
                            <td className={cn('py-2 pr-4 text-right font-medium', days != null && days < 30 ? 'text-amber-600' : 'text-gray-700')}>
                              {days != null ? t('postsigning.daysCount', { count: days }) : '—'}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-6 space-y-2">
                  <p className="text-sm text-gray-500">{t('postsigning.noUpcomingRenewals')}</p>
                  {(() => {
                    const expired = dashboard.renewals.expired_count ?? 0
                    const undated = dashboard.renewals.no_date_count ?? 0
                    if (expired === 0 && undated === 0) return null
                    return (
                      <p className="text-xs text-gray-400">
                        {expired > 0 && (
                          <button onClick={() => setActiveTab('renewals')} className="text-primary-600 hover:underline">
                            {t('postsigning.renewalsExpiredNote', { count: expired })}
                          </button>
                        )}
                        {expired > 0 && undated > 0 && <span> · </span>}
                        {undated > 0 && <span>{t('postsigning.renewalsUndatedNote', { count: undated })}</span>}
                      </p>
                    )
                  })()}
                </div>
              )}
            </div>
          </div>

          {/* Extracted items — honest counts, no fabricated status */}
          <div className="card">
            <div className="card-header">
              <h3 className="font-medium text-gray-900">{t('postsigning.extractedItems')}</h3>
            </div>
            <div className="p-4 text-sm">
              <button onClick={() => setActiveTab('obligations')} className="w-full flex justify-between items-center py-2 hover:text-primary-600">
                <span className="text-gray-600">{t('postsigning.obligations')}</span>
                <span className="font-semibold text-gray-900">{dashboard.obligations.total}</span>
              </button>
              <button onClick={() => setActiveTab('slas')} className="w-full flex justify-between items-center py-2 border-t border-gray-100 hover:text-primary-600">
                <span className="text-gray-600">{t('postsigning.slaPerformance')}</span>
                <span className="font-semibold text-gray-900">{dashboard.slas.total_slas}</span>
              </button>
              <button onClick={() => setActiveTab('milestones')} className="w-full flex justify-between items-center py-2 border-t border-gray-100 hover:text-primary-600">
                <span className="text-gray-600">{t('postsigning.milestones')}</span>
                <span className="font-semibold text-gray-900">{dashboard.milestones.total_milestones}</span>
              </button>
              <p className="text-xs text-gray-400 pt-3 mt-1 border-t border-gray-100">{t('postsigning.statusTrackingNote')}</p>
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
                          <div className="flex items-center gap-1.5">
                            <Link
                              to={`/obligations/${item.id}`}
                              className="hover:text-primary-600 hover:underline truncate"
                            >
                              {item.title}
                            </Link>
                            {item.has_evidence && (
                              <PaperClipIcon
                                className="h-4 w-4 text-green-600 flex-shrink-0"
                                title={t('postsigning.hasEvidence', { defaultValue: 'Evidence attached' })}
                              />
                            )}
                          </div>
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
            <StatCard title={t('postsigning.slaCompliance')} value={slaMeasured ? `${dashboard.slas.compliance_rate!.toFixed(1)}%` : t('postsigning.notMeasured')} subtitle={!slaMeasured ? t('postsigning.noData') : undefined} icon={CheckCircleIcon} color={!slaMeasured ? 'default' : (dashboard.slas.compliance_rate! >= 90 ? 'success' : 'warning')} variant="filled" chart={slaMeasured ? slaChart : undefined} />
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
                      {canRecord && <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">{t('common.actions')}</th>}
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {filteredSLAs.length === 0 ? (
                      <tr>
                        <td colSpan={canRecord ? 8 : 7} className="px-4 py-8 text-center text-sm text-gray-500">
                          {t('postsigning.noActiveSlas')}
                        </td>
                      </tr>
                    ) : (
                      filteredSLAs.map((sla) => (
                        <tr key={sla.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">
                            <Link to={`/slas/${sla.id}`} className="hover:text-primary-600 hover:underline">
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
                          {canRecord && (
                            <td className="px-4 py-3 text-right">
                              <button
                                onClick={() => { setMeasureSla(sla); setActualValue(''); setMeasureNotes(''); setMeasureError(null) }}
                                className="text-xs font-medium text-primary-600 hover:underline whitespace-nowrap"
                              >
                                {t('postsigning.recordMeasurement')}
                              </button>
                            </td>
                          )}
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

      {/* Record SLA measurement */}
      {measureSla && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-1">{t('postsigning.recordMeasurementTitle')}</h3>
            <p className="text-sm text-gray-500 mb-4">{measureSla.sla_name}</p>

            <div className="rounded-lg bg-gray-50 p-3 mb-4 text-sm flex items-center justify-between">
              <span className="text-gray-500">{t('postsigning.metric')} · {t('postsigning.target')}</span>
              <span className="font-medium text-gray-900">
                {(measureSla.metric_type?.replace(/_/g, ' ') || '')} {measureSla.target_value != null ? `(≥ ${measureSla.target_value})` : ''}
              </span>
            </div>

            <label className="block text-sm font-medium text-gray-700 mb-1">{t('postsigning.actualValue')}</label>
            <input
              type="number"
              value={actualValue}
              onChange={(e) => setActualValue(e.target.value)}
              placeholder={t('postsigning.actualValuePlaceholder', { defaultValue: 'e.g. 99.2' })}
              className="input w-full mb-3"
              autoFocus
            />

            <label className="block text-sm font-medium text-gray-700 mb-1">{t('postsigning.measureNotes')}</label>
            <textarea
              value={measureNotes}
              onChange={(e) => setMeasureNotes(e.target.value)}
              rows={2}
              placeholder={t('postsigning.measureNotesPlaceholder', { defaultValue: 'Optional — period, source…' })}
              className="input w-full"
            />

            {measureError && <p className="mt-3 text-sm text-red-600">{measureError}</p>}

            <div className="flex justify-end gap-3 mt-5">
              <button onClick={() => setMeasureSla(null)} className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg">
                {t('common.cancel')}
              </button>
              <button
                onClick={submitMeasurement}
                disabled={recordMeasurementMutation.isPending || actualValue.trim() === ''}
                className="btn-primary disabled:opacity-50"
              >
                {recordMeasurementMutation.isPending ? t('common.saving') : t('postsigning.recordMeasurement')}
              </button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'milestones' && (
        <div className="space-y-4">
          <p className="text-xs text-gray-500">{t('postsigning.milestonesNote')}</p>
          {/* Milestone Summary Stats */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatCard
              title={t('postsigning.completionRate')}
              value={msMeasured ? `${dashboard.milestones.completion_rate!.toFixed(1)}%` : t('postsigning.notMeasured')}
              subtitle={!msMeasured ? t('postsigning.noData') : undefined}
              icon={CheckCircleIcon}
              color={!msMeasured ? 'default' : (dashboard.milestones.completion_rate! >= 80 ? 'success' : dashboard.milestones.completion_rate! >= 50 ? 'warning' : 'danger')}
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
              value={dashboard.vendors.avg_performance_score != null ? dashboard.vendors.avg_performance_score.toFixed(1) : '—'}
              subtitle={dashboard.vendors.avg_performance_score == null ? t('postsigning.notRated') : undefined}
              icon={ChartBarIcon}
              color={dashboard.vendors.avg_performance_score == null ? 'default' : (dashboard.vendors.avg_performance_score >= 70 ? 'success' : 'warning')}
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
                            {v.performance_score != null ? (
                              <span className={cn(
                                'text-sm font-semibold',
                                v.performance_score >= 80 ? 'text-green-600' :
                                v.performance_score >= 60 ? 'text-amber-600' :
                                'text-red-600'
                              )}>
                                {v.performance_score.toFixed(1)}
                              </span>
                            ) : <span className="text-sm text-gray-400">—</span>}
                          </td>
                          <td className="px-4 py-3">
                            {v.risk_level === 'unrated' ? (
                              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-500">
                                {t('postsigning.notRated')}
                              </span>
                            ) : (
                              <span className={cn(
                                'px-2 py-0.5 rounded-full text-xs font-medium',
                                v.risk_level === 'high' || v.risk_level === 'critical' ? 'bg-red-100 text-red-800' :
                                v.risk_level === 'medium' ? 'bg-amber-100 text-amber-800' :
                                'bg-green-100 text-green-800'
                              )}>
                                {t(`risk.${v.risk_level}`, { defaultValue: v.risk_level })}
                              </span>
                            )}
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
