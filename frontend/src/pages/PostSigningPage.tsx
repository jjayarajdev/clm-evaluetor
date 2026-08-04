/* Post-signing operations — Direction B redesign.
   Stat summary row (clickable tab shortcuts) → Tabs with counts → dense sortable
   tables with status Pills and due-date urgency hints. Detail/edit flows live in
   Drawers (SLA breach detail, record measurement). Data fetching, tab structure,
   filters, mutations, permission checks and routes are unchanged from the
   pre-redesign page. */
import { useState, useMemo, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  ArrowDownTrayIcon,
  ArrowTopRightOnSquareIcon,
  BanknotesIcon,
  BuildingOfficeIcon,
  CalendarIcon,
  ChartBarIcon,
  CheckCircleIcon,
  ClipboardDocumentCheckIcon,
  ClockIcon,
  DocumentChartBarIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  FlagIcon,
  FunnelIcon,
  PaperClipIcon,
  SignalIcon,
  TruckIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import {
  Avatar,
  Bar,
  Button,
  Drawer,
  EmptyState,
  Field,
  Pill,
  Select,
  Stat,
  Table,
  Tabs,
  Tooltip,
  useToast,
} from '@/components/ui'
import type { PillTone, TabDef, TableColumn } from '@/components/ui'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { formatCurrency } from '@/lib/utils'
import type { ContractRenewalInfo, VendorListItem } from '@/types/postsigning'

// ── Row types (unchanged API shapes) ─────────────────────────────

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

// ── Presentation helpers ─────────────────────────────────────────

const ITEM_STATUS_TONE: Record<string, PillTone> = {
  overdue: 'da',
  completed: 'ok',
  in_progress: 'in',
  waived: 'n',
  pending: 'wa',
}

const RAG_TONE: Record<string, PillTone> = { green: 'ok', amber: 'wa', red: 'da' }
const RAG_RANK: Record<string, number> = { red: 0, amber: 1, green: 2 }

const SEVERITY_TONE: Record<string, PillTone> = {
  critical: 'da',
  high: 'da',
  medium: 'wa',
  moderate: 'wa',
  major: 'da',
  minor: 'wa',
  low: 'ok',
}
const SEVERITY_RANK: Record<string, number> = { critical: 0, high: 1, major: 1, medium: 2, moderate: 2, minor: 3, low: 3 }

function complianceTone(rate: number): string {
  return rate >= 90 ? 'var(--ok)' : rate >= 70 ? 'var(--wa)' : 'var(--da)'
}

function daysUntil(dateStr: string): number {
  return Math.ceil((new Date(dateStr).getTime() - Date.now()) / 86_400_000)
}

function SeverityPill({ severity }: { severity: string }) {
  const { t } = useTranslation()
  return (
    <Pill tone={SEVERITY_TONE[severity] || 'n'}>
      {t(`risk.${severity}`, { defaultValue: severity })}
    </Pill>
  )
}

function RagPill({ status }: { status: string | null }) {
  const { t } = useTranslation()
  if (!status) return <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>{t('postsigning.na')}</span>
  return (
    <Pill tone={RAG_TONE[status] || 'n'}>
      {t(`postsigning.rag.${status}`, { defaultValue: status })}
    </Pill>
  )
}

/** Due date plus a tinted "in Nd" / "Nd overdue" urgency hint. */
function DueCell({ dateStr, doneStatus }: { dateStr: string | null; doneStatus?: boolean }) {
  const { t } = useTranslation()
  if (!dateStr) return <span className="faint">{t('postsigning.noDate')}</span>
  const d = daysUntil(dateStr)
  const hint = doneStatus
    ? null
    : d < 0
      ? { text: t('postsigning.daysOverdue', { days: Math.abs(d) }), color: 'var(--da)' }
      : d <= 30
        ? { text: t('contracts.inDays', { count: d, defaultValue: 'in {{count}}d' }), color: 'var(--wa)' }
        : null
  return (
    <span className="num nw" style={{ display: 'inline-block' }}>
      {new Date(dateStr).toLocaleDateString()}
      {hint && (
        <span style={{ display: 'block', fontSize: 'var(--fs-xs)', color: hint.color, fontWeight: 600 }}>{hint.text}</span>
      )}
    </span>
  )
}

/** Compliance-style percentage: small bar + tinted figure. */
function RateCell({ rate }: { rate: number | null }) {
  const { t } = useTranslation()
  if (rate == null) return <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>{t('postsigning.na')}</span>
  const tone = complianceTone(rate)
  return (
    <span className="row" style={{ gap: 8 }}>
      <Bar value={rate} width={48} tone={tone} />
      <span className="mono num" style={{ fontSize: 'var(--fs-sm)', fontWeight: 500, color: tone }}>
        {rate.toFixed(1)}%
      </span>
    </span>
  )
}

/** Tiny trend line for Stat cards (compliance history). */
function Sparkline({ points, width = 96, height = 26, tone = 'var(--p)' }: {
  points: number[]
  width?: number
  height?: number
  tone?: string
}) {
  if (points.length < 2) return null
  const max = Math.max(...points)
  const min = Math.min(...points)
  const span = max - min || 1
  const y = (p: number) => height - ((p - min) / span) * (height - 4) - 2
  const d = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${((i / (points.length - 1)) * width).toFixed(1)} ${y(p).toFixed(1)}`)
    .join(' ')
  return (
    <svg width={width} height={height} style={{ display: 'block', overflow: 'visible' }} aria-hidden>
      <path d={d} fill="none" stroke={tone} strokeWidth="1.75" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={width} cy={y(points[points.length - 1])} r="2.5" fill={tone} />
    </svg>
  )
}

function contractLink(id: string, filename: string) {
  return (
    <Link
      to={`/contracts/${id}`}
      onClick={(e) => e.stopPropagation()}
      className="trunc"
      style={{ display: 'block', maxWidth: 200, color: 'var(--p)' }}
    >
      {filename}
    </Link>
  )
}

type TabId = 'overview' | 'obligations' | 'slas' | 'renewals' | 'vendors' | 'milestones'
type RenewalWindow = '' | '30' | '60' | '90' | 'expired'

// ── Page ─────────────────────────────────────────────────────────

export default function PostSigningPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()

  // Translate item statuses, reusing existing status.* keys where available
  const statusLabel = (s: string) =>
    ['pending', 'completed'].includes(s)
      ? t(`status.${s}`)
      : t(`postsigning.status.${s}`, { defaultValue: s.replace(/_/g, ' ') })
  const [activeTab, setActiveTab] = useState<TabId>('overview')
  const [selectedBreach, setSelectedBreach] = useState<SLABreachDetail | null>(null)
  const [oblStatusFilter, setOblStatusFilter] = useState<string>('')
  const [oblRagFilter, setOblRagFilter] = useState<string>('')
  const [slaSeverityFilter, setSlaSeverityFilter] = useState<string>('')
  const [slaBreachFilter, setSlaBreachFilter] = useState<string>('')
  const [msStatusFilter, setMsStatusFilter] = useState<string>('')
  const [renewalWindow, setRenewalWindow] = useState<RenewalWindow>('')
  const [isExporting, setIsExporting] = useState(false)
  const queryClient = useQueryClient()

  // Read URL params on mount (e.g. /compliance?tab=obligations&status=overdue)
  useEffect(() => {
    const tab = searchParams.get('tab')
    const status = searchParams.get('status')
    const rag = searchParams.get('rag')
    if (tab && ['overview', 'obligations', 'slas', 'renewals', 'vendors', 'milestones'].includes(tab)) {
      setActiveTab(tab as TabId)
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
      toast({ text: t('postsigning.renewalStatusUpdated', { defaultValue: 'Renewal status updated' }) })
    },
    onError: () => {
      toast({ text: t('postsigning.renewalStatusFailed', { defaultValue: 'Could not update renewal status' }), error: true })
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
      toast({ text: t('postsigning.recordSuccess', { defaultValue: 'Measurement recorded' }) })
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

  // The renewal window stat cards double as filters over the flattened list
  const filteredRenewals = useMemo((): ContractRenewalInfo[] => {
    if (!renewalWindow) return allRenewals
    if (renewalWindow === 'expired') return allRenewals.filter(r => (r.days_until_expiration ?? 999) <= 0)
    const limit = Number(renewalWindow)
    return allRenewals.filter(r =>
      r.days_until_expiration != null && r.days_until_expiration > 0 && r.days_until_expiration <= limit
    )
  }, [allRenewals, renewalWindow])

  const toggleRenewalWindow = (w: RenewalWindow) => setRenewalWindow(prev => (prev === w ? '' : w))

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
      toast({ text: t('postsigning.exportSuccess', { defaultValue: 'Calendar exported (.ics)' }) })
    } catch (err) {
      console.error('Failed to export calendar:', err)
      toast({ text: t('postsigning.exportFailed', { defaultValue: 'Calendar export failed' }), error: true })
    } finally {
      setIsExporting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !dashboard) {
    return (
      <div className="banner banner-da" style={{ margin: '24px 0' }}>
        <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
        <span>{t('postsigning.loadError')}</span>
      </div>
    )
  }

  // A rate is only meaningful once the backend actually measured it (null = not measured).
  const slaMeasured = dashboard.slas.compliance_rate != null
  const msMeasured = dashboard.milestones.completion_rate != null

  const tabs: TabDef<TabId>[] = [
    { value: 'overview', label: t('postsigning.tabs.overview'), icon: ChartBarIcon },
    { value: 'obligations', label: t('postsigning.obligations'), icon: ClipboardDocumentCheckIcon, count: dashboard.obligations.total },
    { value: 'slas', label: t('postsigning.tabs.slasShort', { defaultValue: 'SLAs' }), icon: SignalIcon, count: dashboard.slas.active_slas },
    { value: 'milestones', label: t('postsigning.milestones'), icon: FlagIcon, count: dashboard.milestones.total_milestones },
    { value: 'renewals', label: t('postsigning.tabs.renewals'), icon: ClockIcon },
    { value: 'vendors', label: t('nav.vendors'), icon: TruckIcon, count: dashboard.vendors.total_vendors },
  ]

  const obligations = (allObligations || []) as ObligationRow[]
  const vendors = (vendorData?.vendors || []) as VendorListItem[]

  // ── Column definitions ─────────────────────────────────────────

  const obligationColumns: TableColumn<ObligationRow>[] = [
    {
      key: 'title',
      header: t('postsigning.titleColumn'),
      sortable: true,
      sortValue: (o) => o.title.toLowerCase(),
      render: (o) => (
        <span className="row" style={{ gap: 6 }}>
          <Link
            to={`/obligations/${o.id}`}
            className="trunc"
            style={{ display: 'block', maxWidth: 300, fontWeight: 500, color: 'inherit' }}
          >
            {o.title}
          </Link>
          {o.has_evidence && (
            <Tooltip label={t('postsigning.hasEvidence', { defaultValue: 'Evidence attached' })}>
              <PaperClipIcon style={{ width: 14, height: 14, flexShrink: 0, color: 'var(--ok)' }} aria-hidden />
            </Tooltip>
          )}
        </span>
      ),
    },
    {
      key: 'contract',
      header: t('postsigning.contract'),
      sortable: true,
      sortValue: (o) => o.contract_filename,
      render: (o) => contractLink(o.contract_id, o.contract_filename),
    },
    {
      key: 'category',
      header: t('postsigning.category'),
      sortable: true,
      nowrap: true,
      sortValue: (o) => o.category,
      render: (o) => (
        <span className="muted" style={{ textTransform: 'capitalize' }}>{o.category?.replace(/_/g, ' ') || '—'}</span>
      ),
    },
    {
      key: 'owner',
      header: t('postsigning.owner'),
      sortable: true,
      sortValue: (o) => o.owner,
      render: (o) => <span className="muted">{o.owner || '—'}</span>,
    },
    {
      key: 'due',
      header: t('postsigning.dueDate'),
      sortable: true,
      align: 'right',
      nowrap: true,
      sortValue: (o) => o.due_date,
      render: (o) => <DueCell dateStr={o.due_date} doneStatus={['completed', 'waived'].includes(o.status)} />,
    },
    {
      key: 'status',
      header: t('common.status'),
      sortable: true,
      sortValue: (o) => o.status,
      render: (o) => <Pill tone={ITEM_STATUS_TONE[o.status] || 'n'}>{statusLabel(o.status)}</Pill>,
    },
    {
      key: 'rag',
      header: t('postsigning.ragColumn'),
      sortable: true,
      sortValue: (o) => (o.rag_status ? RAG_RANK[o.rag_status] ?? null : null),
      render: (o) => <RagPill status={o.rag_status} />,
    },
  ]

  const slaColumns: TableColumn<SLARow>[] = [
    {
      key: 'name',
      header: t('postsigning.slaName'),
      sortable: true,
      sortValue: (s) => s.sla_name.toLowerCase(),
      render: (s) => (
        <Link to={`/slas/${s.id}`} className="trunc" style={{ display: 'block', maxWidth: 260, fontWeight: 500, color: 'inherit' }}>
          {s.sla_name}
        </Link>
      ),
    },
    {
      key: 'contract',
      header: t('postsigning.contract'),
      sortable: true,
      sortValue: (s) => s.contract_filename,
      render: (s) => contractLink(s.contract_id, s.contract_filename),
    },
    {
      key: 'metric',
      header: t('postsigning.metric'),
      nowrap: true,
      render: (s) => <span className="muted">{s.metric_type?.replace(/_/g, ' ') || '—'}</span>,
    },
    {
      key: 'target',
      header: t('postsigning.target'),
      align: 'right',
      nowrap: true,
      sortable: true,
      sortValue: (s) => s.target_value,
      render: (s) => <span className="num" style={{ fontWeight: 500 }}>{s.target_value != null ? s.target_value : '—'}</span>,
    },
    {
      key: 'compliance',
      header: t('postsigning.complianceColumn'),
      sortable: true,
      sortValue: (s) => s.compliance_rate,
      render: (s) => <RateCell rate={s.compliance_rate} />,
    },
    {
      key: 'breaches',
      header: t('postsigning.breaches'),
      align: 'right',
      sortable: true,
      sortValue: (s) => s.consecutive_breaches,
      render: (s) => (
        <span className="num" style={{ fontWeight: s.consecutive_breaches > 0 ? 600 : 400, color: s.consecutive_breaches > 0 ? 'var(--da)' : 'var(--ok)' }}>
          {s.consecutive_breaches}
        </span>
      ),
    },
    {
      key: 'severity',
      header: t('postsigning.severity'),
      sortable: true,
      sortValue: (s) => SEVERITY_RANK[s.severity] ?? 9,
      render: (s) => <SeverityPill severity={s.severity} />,
    },
    ...(canRecord
      ? [{
          key: 'actions',
          header: t('common.actions'),
          align: 'right' as const,
          nowrap: true,
          render: (s: SLARow) => (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => { setMeasureSla(s); setActualValue(''); setMeasureNotes(''); setMeasureError(null) }}
            >
              {t('postsigning.recordMeasurement')}
            </Button>
          ),
        }]
      : []),
  ]

  const breachColumns: TableColumn<(typeof dashboard.slas.recent_breaches)[number]>[] = [
    {
      key: 'name',
      header: t('postsigning.slaName'),
      sortable: true,
      sortValue: (b) => b.sla_name.toLowerCase(),
      render: (b) => <span style={{ fontWeight: 500 }}>{b.sla_name}</span>,
    },
    {
      key: 'contract',
      header: t('postsigning.contract'),
      render: (b) => <span className="muted trunc" style={{ display: 'block', maxWidth: 200 }}>{b.contract}</span>,
    },
    {
      key: 'target',
      header: t('postsigning.target'),
      align: 'right',
      nowrap: true,
      render: (b) => <span className="num muted">{b.target_display || '—'}</span>,
    },
    {
      key: 'actual',
      header: t('postsigning.actual'),
      align: 'right',
      nowrap: true,
      render: (b) => <span className="num" style={{ fontWeight: 600, color: 'var(--da)' }}>{b.actual_display || '—'}</span>,
    },
    {
      key: 'fails',
      header: t('postsigning.consecFails'),
      align: 'right',
      sortable: true,
      sortValue: (b) => b.breaches,
      render: (b) => <span className="num" style={{ fontWeight: 600, color: 'var(--da)' }}>{b.breaches}</span>,
    },
    {
      key: 'severity',
      header: t('postsigning.severity'),
      sortable: true,
      sortValue: (b) => SEVERITY_RANK[b.severity] ?? 9,
      render: (b) => <SeverityPill severity={b.severity} />,
    },
  ]

  const milestoneColumns: TableColumn<MilestoneRow>[] = [
    {
      key: 'title',
      header: t('postsigning.titleColumn'),
      sortable: true,
      sortValue: (m) => m.title.toLowerCase(),
      render: (m) => (
        <Link to={`/obligations/${m.id}`} className="trunc" style={{ display: 'block', maxWidth: 300, fontWeight: 500, color: 'inherit' }}>
          {m.title}
        </Link>
      ),
    },
    {
      key: 'contract',
      header: t('postsigning.contract'),
      sortable: true,
      sortValue: (m) => m.contract_filename,
      render: (m) => contractLink(m.contract_id, m.contract_filename),
    },
    {
      key: 'owner',
      header: t('postsigning.owner'),
      sortable: true,
      sortValue: (m) => m.owner,
      render: (m) => <span className="muted">{m.owner || '—'}</span>,
    },
    {
      key: 'due',
      header: t('postsigning.dueDate'),
      sortable: true,
      align: 'right',
      nowrap: true,
      sortValue: (m) => m.due_date,
      render: (m) => <DueCell dateStr={m.due_date} doneStatus={m.status === 'completed'} />,
    },
    {
      key: 'status',
      header: t('common.status'),
      sortable: true,
      sortValue: (m) => m.status,
      render: (m) => <Pill tone={ITEM_STATUS_TONE[m.status] || 'n'}>{statusLabel(m.status)}</Pill>,
    },
  ]

  const renewalColumns: TableColumn<ContractRenewalInfo>[] = [
    {
      key: 'contract',
      header: t('postsigning.contract'),
      sortable: true,
      sortValue: (r) => r.filename.toLowerCase(),
      render: (r) => (
        <Link to={`/contracts/${r.contract_id}`} className="trunc" style={{ display: 'block', maxWidth: 240, fontWeight: 500, color: 'inherit' }}>
          {r.filename}
        </Link>
      ),
    },
    {
      key: 'counterparty',
      header: t('contracts.counterparty'),
      sortable: true,
      sortValue: (r) => r.counterparty,
      render: (r) => <span className="muted trunc" style={{ display: 'block', maxWidth: 160 }}>{r.counterparty || '—'}</span>,
    },
    {
      key: 'type',
      header: t('postsigning.type'),
      nowrap: true,
      render: (r) => (
        <span className="muted" style={{ textTransform: 'capitalize' }}>{r.contract_type?.replace(/_/g, ' ') || '—'}</span>
      ),
    },
    {
      key: 'expiration',
      header: t('renewals.expiration'),
      align: 'right',
      nowrap: true,
      sortable: true,
      sortValue: (r) => r.expiration_date,
      render: (r) => (
        <span className="num">{r.expiration_date ? new Date(r.expiration_date).toLocaleDateString() : '—'}</span>
      ),
    },
    {
      key: 'days',
      header: t('postsigning.daysLeft'),
      align: 'right',
      nowrap: true,
      sortable: true,
      sortValue: (r) => r.days_until_expiration,
      render: (r) => {
        const d = r.days_until_expiration
        if (d == null) return <span className="faint">—</span>
        const color = d <= 0 ? 'var(--da)' : d <= 30 ? 'var(--da)' : d <= 60 ? 'var(--wa)' : undefined
        return (
          <span className="num" style={{ fontWeight: 600, color }}>
            {d <= 0 ? t('postsigning.daysOverdue', { days: Math.abs(d) }) : t('postsigning.daysShort', { days: d })}
          </span>
        )
      },
    },
    {
      key: 'risk',
      header: t('postsigning.risk'),
      sortable: true,
      sortValue: (r) => (r.risk_level ? SEVERITY_RANK[r.risk_level] ?? 9 : null),
      render: (r) => (r.risk_level ? <SeverityPill severity={r.risk_level} /> : <span className="faint">—</span>),
    },
    {
      key: 'auto',
      header: t('renewals.autoRenew'),
      nowrap: true,
      render: (r) => (r.auto_renewal
        ? <Pill tone="ok">{t('common.yes')}</Pill>
        : <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>{t('common.no')}</span>),
    },
    {
      key: 'status',
      header: t('common.status'),
      nowrap: true,
      render: (r) => (
        <Select
          value={r.renewal_status || 'pending_review'}
          onChange={(e) => renewalStatusMutation.mutate({ contractId: r.contract_id, status: e.target.value })}
          containerStyle={{ width: 160 }}
          options={[
            { value: 'pending_review', label: t('postsigning.renewalStatus.pending_review') },
            { value: 'approved', label: t('postsigning.renewalStatus.approved') },
            { value: 'declined', label: t('postsigning.renewalStatus.declined') },
            { value: 'renegotiating', label: t('postsigning.renewalStatus.renegotiating') },
          ]}
        />
      ),
    },
  ]

  const vendorColumns: TableColumn<VendorListItem>[] = [
    {
      key: 'vendor',
      header: t('vendors.vendor'),
      sortable: true,
      sortValue: (v) => v.vendor_name.toLowerCase(),
      render: (v) => (
        <span className="row" style={{ gap: 9 }}>
          <Avatar name={v.vendor_name} size={26} />
          <Link to="/vendors" className="trunc" style={{ display: 'block', maxWidth: 220, fontWeight: 500, color: 'inherit' }}>
            {v.vendor_name}
          </Link>
        </span>
      ),
    },
    {
      key: 'score',
      header: t('vendors.score'),
      align: 'right',
      nowrap: true,
      sortable: true,
      sortValue: (v) => v.performance_score,
      render: (v) => (v.performance_score != null ? (
        <span className="num" style={{
          fontWeight: 600,
          color: v.performance_score >= 80 ? 'var(--ok)' : v.performance_score >= 60 ? 'var(--wa)' : 'var(--da)',
        }}>
          {v.performance_score.toFixed(1)}
        </span>
      ) : <span className="faint">—</span>),
    },
    {
      key: 'risk',
      header: t('vendors.risk'),
      sortable: true,
      sortValue: (v) => (v.risk_level === 'unrated' ? 9 : SEVERITY_RANK[v.risk_level] ?? 9),
      render: (v) => (v.risk_level === 'unrated'
        ? <Pill tone="n">{t('postsigning.notRated')}</Pill>
        : <SeverityPill severity={v.risk_level} />),
    },
    {
      key: 'contracts',
      header: t('vendors.contracts'),
      align: 'right',
      sortable: true,
      sortValue: (v) => v.contract_count,
      render: (v) => <span className="num">{v.contract_count}</span>,
    },
    {
      key: 'exposure',
      header: t('vendors.exposure'),
      align: 'right',
      nowrap: true,
      sortable: true,
      sortValue: (v) => v.total_exposure,
      render: (v) => (
        <span className="num" style={{ fontWeight: 500 }}>
          {v.total_exposure ? `$${(v.total_exposure / 1000).toFixed(0)}k` : '—'}
        </span>
      ),
    },
    {
      key: 'obl',
      header: t('postsigning.oblPercent'),
      sortable: true,
      sortValue: (v) => v.obligation_compliance_rate,
      render: (v) => <RateCell rate={v.obligation_compliance_rate} />,
    },
    {
      key: 'sla',
      header: t('postsigning.slaPercent'),
      sortable: true,
      sortValue: (v) => v.sla_compliance_rate,
      render: (v) => <RateCell rate={v.sla_compliance_rate} />,
    },
    {
      key: 'breaches',
      header: t('vendors.breaches'),
      align: 'right',
      sortable: true,
      sortValue: (v) => v.active_breaches,
      render: (v) => (
        <span className="num" style={{ fontWeight: v.active_breaches > 0 ? 600 : 400, color: v.active_breaches > 0 ? 'var(--da)' : 'var(--ok)' }}>
          {v.active_breaches}
        </span>
      ),
    },
  ]

  const upcomingColumns: TableColumn<(typeof dashboard.renewals.upcoming_renewals)[number]>[] = [
    {
      key: 'contract',
      header: t('postsigning.colContract'),
      render: (r) => (
        <Link to={`/contracts/${r.contract_id}`} className="trunc" style={{ display: 'block', maxWidth: 260, fontWeight: 500, color: 'inherit' }}>
          {r.filename}
        </Link>
      ),
    },
    {
      key: 'counterparty',
      header: t('postsigning.colCounterparty'),
      render: (r) => <span className="muted trunc" style={{ display: 'block', maxWidth: 160 }}>{r.counterparty || '—'}</span>,
    },
    {
      key: 'expires',
      header: t('postsigning.colExpires'),
      nowrap: true,
      render: (r) => <span className="num muted">{r.expiration_date || '—'}</span>,
    },
    {
      key: 'days',
      header: t('postsigning.colDays'),
      align: 'right',
      nowrap: true,
      render: (r) => {
        const days = r.expiration_date ? daysUntil(r.expiration_date) : null
        if (days != null && days < 0) {
          return (
            <span className="num" style={{ fontWeight: 600, color: 'var(--da)' }}>
              {t('contracts.daysAgo', { count: -days, defaultValue: '{{count}}d ago' })}
            </span>
          )
        }
        return (
          <span className="num" style={{ fontWeight: 500, color: days != null && days < 30 ? 'var(--wa)' : undefined }}>
            {days != null ? t('postsigning.daysCount', { count: days }) : '—'}
          </span>
        )
      },
    },
  ]

  // ── Render ─────────────────────────────────────────────────────

  const overdueCount = dashboard.obligations.overdue

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div className="row" style={{ alignItems: 'flex-start' }}>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>{t('postsigning.title')}</h1>
          <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>{t('postsigning.description')}</p>
        </div>
        <Button variant="primary" icon={DocumentChartBarIcon} onClick={() => navigate('/reports')}>
          {t('postsigning.generateReport')}
        </Button>
      </div>

      {/* Summary stats — fact-derived signals only; three double as tab shortcuts */}
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        <Stat
          icon={DocumentTextIcon}
          label={t('postsigning.activeContracts')}
          value={dashboard.total_contracts}
          sub={dashboard.valued_contracts && dashboard.valued_contracts > 0
            ? t('postsigning.valueCoverage', { value: formatCurrency(dashboard.total_value, dashboard.total_value_currency || 'USD'), valued: dashboard.valued_contracts, total: dashboard.total_contracts })
            : t('postsigning.na')}
        />
        <Stat
          icon={CalendarIcon}
          label={t('postsigning.renewals90Days')}
          value={dashboard.renewals.expiring_90_days}
          sub={
            dashboard.renewals.expiring_90_days === 0 && (dashboard.renewals.expired_count || dashboard.renewals.no_date_count)
              ? t('postsigning.renewalsContext', {
                  expired: dashboard.renewals.expired_count ?? 0,
                  undated: dashboard.renewals.no_date_count ?? 0,
                })
              : t('postsigning.pastNoticeDeadlineCount', { count: dashboard.renewals.past_notice_deadline })
          }
          subTone={dashboard.renewals.past_notice_deadline > 0 ? 'var(--wa)' : undefined}
          onClick={() => setActiveTab('renewals')}
        />
        <Stat
          icon={TruckIcon}
          label={t('nav.vendors')}
          value={dashboard.vendors.total_vendors}
          sub={t('postsigning.vendorsSubtitle')}
          onClick={() => setActiveTab('vendors')}
        />
        <Stat
          icon={ClipboardDocumentCheckIcon}
          label={t('postsigning.obligationsTracked')}
          value={dashboard.obligations.total}
          sub={overdueCount > 0
            ? t('postsigning.status.overdue') + ` · ${overdueCount}`
            : t('postsigning.extractedUntracked')}
          subTone={overdueCount > 0 ? 'var(--da)' : undefined}
          onClick={() => setActiveTab('obligations')}
        />
      </div>

      {/* Tabs */}
      <Tabs<TabId> tabs={tabs} value={activeTab} onChange={setActiveTab} />

      {/* ── Overview ─────────────────────────────────────────── */}
      {activeTab === 'overview' && (
        <div className="grid gap-4 grid-cols-1 lg:grid-cols-3" style={{ alignItems: 'start' }}>
          {/* Renewals coming up — fact-derived from expiration dates */}
          <div className="card lg:col-span-2">
            <div className="row" style={{ padding: '13px 16px', borderBottom: '1px solid var(--b)', gap: 8 }}>
              <b style={{ fontSize: 'var(--fs-lg)' }}>{t('postsigning.renewalsComingUp')}</b>
              <span className="grow" />
              <Button variant="ghost" size="sm" onClick={() => setActiveTab('renewals')}>
                {t('postsigning.viewAll')}
              </Button>
            </div>
            {dashboard.renewals.upcoming_renewals.length > 0 ? (
              <Table
                columns={upcomingColumns}
                rows={dashboard.renewals.upcoming_renewals.slice(0, 8)}
                rowKey={(r) => r.contract_id}
                minWidth={520}
              />
            ) : (
              <EmptyState
                icon={CalendarIcon}
                title={t('postsigning.noUpcomingRenewals')}
                body={(() => {
                  const expired = dashboard.renewals.expired_count ?? 0
                  const undated = dashboard.renewals.no_date_count ?? 0
                  const parts: string[] = []
                  if (expired > 0) parts.push(t('postsigning.renewalsExpiredNote', { count: expired }))
                  if (undated > 0) parts.push(t('postsigning.renewalsUndatedNote', { count: undated }))
                  return parts.length ? parts.join(' · ') : undefined
                })()}
                action={(dashboard.renewals.expired_count ?? 0) > 0 ? (
                  <Button variant="secondary" size="sm" onClick={() => setActiveTab('renewals')}>
                    {t('postsigning.viewAll')}
                  </Button>
                ) : undefined}
              />
            )}
          </div>

          {/* Extracted items — honest counts, no fabricated status */}
          <div className="card">
            <div className="row" style={{ padding: '13px 16px', borderBottom: '1px solid var(--b)' }}>
              <b style={{ fontSize: 'var(--fs-lg)' }}>{t('postsigning.extractedItems')}</b>
            </div>
            <div className="col card-p" style={{ gap: 0 }}>
              {([
                ['obligations', t('postsigning.obligations'), dashboard.obligations.total],
                ['slas', t('postsigning.slaPerformance'), dashboard.slas.total_slas],
                ['milestones', t('postsigning.milestones'), dashboard.milestones.total_milestones],
              ] as const).map(([tabId, label, count], i) => (
                <button
                  key={tabId}
                  type="button"
                  className="row"
                  onClick={() => setActiveTab(tabId)}
                  style={{
                    padding: '9px 0', border: 0, background: 'none', cursor: 'pointer', textAlign: 'left',
                    borderTop: i > 0 ? '1px solid var(--b)' : undefined, width: '100%',
                  }}
                >
                  <span className="muted grow" style={{ fontSize: 'var(--fs-md)' }}>{label}</span>
                  <span className="num" style={{ fontWeight: 600 }}>{count}</span>
                </button>
              ))}
              <p className="faint" style={{ fontSize: 'var(--fs-sm)', paddingTop: 10, marginTop: 2, borderTop: '1px solid var(--b)' }}>
                {t('postsigning.statusTrackingNote')}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── Obligations ──────────────────────────────────────── */}
      {activeTab === 'obligations' && (
        <div className="col" style={{ gap: 12 }}>
          {overdueCount > 0 && (
            <div className="banner banner-da">
              <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
              <span>
                <b>{t('postsigning.overdueBannerTitle', { count: overdueCount, defaultValue: '{{count}} overdue.' })}</b>{' '}
                {t('postsigning.overdueBannerBody', { defaultValue: 'These obligations are past their due date — review and complete or waive them.' })}
              </span>
            </div>
          )}
          <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
            <Select
              value={oblStatusFilter}
              onChange={(e) => setOblStatusFilter(e.target.value)}
              containerStyle={{ width: 170 }}
              options={[
                { value: '', label: t('postsigning.allStatuses') },
                { value: 'pending', label: t('status.pending') },
                { value: 'in_progress', label: t('postsigning.status.in_progress') },
                { value: 'completed', label: t('status.completed') },
                { value: 'overdue', label: t('postsigning.status.overdue') },
                { value: 'waived', label: t('postsigning.status.waived') },
              ]}
            />
            <Select
              value={oblRagFilter}
              onChange={(e) => setOblRagFilter(e.target.value)}
              containerStyle={{ width: 140 }}
              options={[
                { value: '', label: t('postsigning.allRag') },
                { value: 'green', label: t('postsigning.rag.green') },
                { value: 'amber', label: t('postsigning.rag.amber') },
                { value: 'red', label: t('postsigning.rag.red') },
              ]}
            />
            <span className="grow" />
            <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
              {oblLoading ? '…' : t('postsigning.itemsCount', { count: obligations.length })}
            </span>
          </div>
          {oblLoading ? (
            <div className="row" style={{ justifyContent: 'center', padding: 32 }}><LoadingSpinner /></div>
          ) : (
            <Table<ObligationRow>
              columns={obligationColumns}
              rows={obligations}
              rowKey={(o) => o.id}
              empty={
                <EmptyState
                  icon={oblStatusFilter || oblRagFilter ? FunnelIcon : ClipboardDocumentCheckIcon}
                  title={t('postsigning.noObligationsFound')}
                  body={oblStatusFilter || oblRagFilter
                    ? t('postsigning.emptyObligationsFiltered', { defaultValue: 'No obligations match the current filters — loosen or clear them to see more.' })
                    : t('postsigning.emptyObligationsBody', { defaultValue: 'Obligations appear here once the AI pipeline extracts them from uploaded contracts.' })}
                  action={(oblStatusFilter || oblRagFilter) ? (
                    <Button variant="secondary" size="sm" onClick={() => { setOblStatusFilter(''); setOblRagFilter('') }}>
                      {t('contracts.clearAllFilters')}
                    </Button>
                  ) : undefined}
                />
              }
            />
          )}
        </div>
      )}

      {/* ── SLAs ─────────────────────────────────────────────── */}
      {activeTab === 'slas' && (
        <div className="col" style={{ gap: 14 }}>
          {/* SLA summary stats */}
          <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
            <Stat
              icon={CheckCircleIcon}
              label={t('postsigning.slaCompliance')}
              value={slaMeasured ? `${dashboard.slas.compliance_rate!.toFixed(1)}%` : t('postsigning.notMeasured')}
              sub={slaMeasured
                ? (slaChart ? <Sparkline points={slaChart} tone={complianceTone(dashboard.slas.compliance_rate!)} /> : undefined)
                : t('postsigning.noData')}
            />
            <Stat icon={SignalIcon} label={t('postsigning.activeSlas')} value={dashboard.slas.active_slas} />
            <Stat
              icon={ExclamationTriangleIcon}
              label={t('status.breached')}
              value={dashboard.slas.breached}
              sub={dashboard.slas.critical_breaches > 0 ? t('postsigning.criticalCount', { count: dashboard.slas.critical_breaches }) : undefined}
              subTone="var(--da)"
            />
            <Stat
              icon={BanknotesIcon}
              label={t('postsigning.penaltiesMtd')}
              value={`$${dashboard.slas.total_penalties_mtd.toLocaleString()}`}
              subTone="var(--wa)"
            />
          </div>

          {/* All active SLAs */}
          <div className="col" style={{ gap: 12 }}>
            <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
              <b style={{ fontSize: 'var(--fs-lg)' }}>{t('postsigning.allActiveSlas')}</b>
              <span className="grow" />
              <Select
                value={slaSeverityFilter}
                onChange={(e) => setSlaSeverityFilter(e.target.value)}
                containerStyle={{ width: 160 }}
                options={[
                  { value: '', label: t('postsigning.allSeverities') },
                  { value: 'critical', label: t('risk.critical') },
                  { value: 'high', label: t('risk.high') },
                  { value: 'medium', label: t('risk.medium') },
                  { value: 'low', label: t('risk.low') },
                ]}
              />
              <Select
                value={slaBreachFilter}
                onChange={(e) => setSlaBreachFilter(e.target.value)}
                containerStyle={{ width: 160 }}
                options={[
                  { value: '', label: t('postsigning.allSlas') },
                  { value: 'breached', label: t('postsigning.breachedOnly') },
                  { value: 'compliant', label: t('postsigning.noBreaches') },
                ]}
              />
              <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
                {t('postsigning.slasCount', { count: filteredSLAs.length })}
              </span>
            </div>
            {slasLoading ? (
              <div className="row" style={{ justifyContent: 'center', padding: 32 }}><LoadingSpinner size="md" /></div>
            ) : (
              <Table<SLARow>
                columns={slaColumns}
                rows={filteredSLAs}
                rowKey={(s) => s.id}
                empty={
                  <EmptyState
                    icon={slaSeverityFilter || slaBreachFilter ? FunnelIcon : SignalIcon}
                    title={t('postsigning.noActiveSlas')}
                    body={slaSeverityFilter || slaBreachFilter
                      ? t('postsigning.emptySlasFiltered', { defaultValue: 'No SLAs match the current filters — loosen or clear them to see more.' })
                      : t('postsigning.emptySlasBody', { defaultValue: 'SLAs appear here once the AI pipeline extracts service levels from uploaded contracts.' })}
                    action={(slaSeverityFilter || slaBreachFilter) ? (
                      <Button variant="secondary" size="sm" onClick={() => { setSlaSeverityFilter(''); setSlaBreachFilter('') }}>
                        {t('contracts.clearAllFilters')}
                      </Button>
                    ) : undefined}
                  />
                }
              />
            )}
          </div>

          {/* Recent SLA breaches (only when there are breaches) */}
          {dashboard.slas.recent_breaches.length > 0 && (
            <div className="col" style={{ gap: 12 }}>
              <div className="row" style={{ gap: 8 }}>
                <b style={{ fontSize: 'var(--fs-lg)' }}>{t('postsigning.recentSlaBreaches')}</b>
                <span className="grow" />
                <span style={{ fontSize: 'var(--fs-sm)', color: 'var(--da)', fontWeight: 600 }}>
                  {t('postsigning.criticalCount', { count: dashboard.slas.critical_breaches })}
                </span>
              </div>
              <Table
                columns={breachColumns}
                rows={dashboard.slas.recent_breaches}
                rowKey={(b) => b.sla_id}
                onRowClick={(breach) => setSelectedBreach({
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
              />
              <p className="faint" style={{ fontSize: 'var(--fs-sm)' }}>{t('postsigning.clickRowForDetails')}</p>
            </div>
          )}
        </div>
      )}

      {/* ── Milestones ───────────────────────────────────────── */}
      {activeTab === 'milestones' && (
        <div className="col" style={{ gap: 14 }}>
          <div className="banner banner-in">
            <FlagIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
            <span>{t('postsigning.milestonesNote')}</span>
          </div>

          {/* Milestone summary stats */}
          <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
            <Stat
              icon={CheckCircleIcon}
              label={t('postsigning.completionRate')}
              value={msMeasured ? `${dashboard.milestones.completion_rate!.toFixed(1)}%` : t('postsigning.notMeasured')}
              sub={msMeasured
                ? (obligationChart ? <Sparkline points={obligationChart} tone={complianceTone(dashboard.milestones.completion_rate!)} /> : undefined)
                : t('postsigning.noData')}
            />
            <Stat icon={FlagIcon} label={t('postsigning.totalMilestones')} value={dashboard.milestones.total_milestones} />
            <Stat
              icon={ExclamationTriangleIcon}
              label={t('postsigning.status.overdue')}
              value={dashboard.milestones.overdue}
              subTone="var(--da)"
            />
            <Stat
              icon={ClockIcon}
              label={t('postsigning.atRisk')}
              value={dashboard.milestones.at_risk}
              subTone="var(--wa)"
            />
          </div>

          {/* Completion progress */}
          <div className="card">
            <div className="row" style={{ padding: '13px 16px', borderBottom: '1px solid var(--b)' }}>
              <b style={{ fontSize: 'var(--fs-lg)' }}>{t('postsigning.milestoneProgress')}</b>
            </div>
            <div className="col card-p" style={{ gap: 12 }}>
              <span className="bar" style={{ width: '100%', height: 8, display: 'flex', overflow: 'hidden' }}>
                {([
                  [dashboard.milestones.completed, 'var(--ok)'],
                  [dashboard.milestones.overdue, 'var(--da)'],
                  [dashboard.milestones.at_risk, 'var(--wa)'],
                ] as const).map(([n, color], i) => (
                  <i
                    key={i}
                    style={{
                      display: 'block', height: '100%', background: color, borderRadius: 0,
                      width: `${dashboard.milestones.total_milestones > 0 ? (n / dashboard.milestones.total_milestones) * 100 : 0}%`,
                      transition: 'width .2s',
                    }}
                  />
                ))}
              </span>
              <div className="row" style={{ gap: 18, flexWrap: 'wrap', fontSize: 'var(--fs-sm)' }}>
                {([
                  [t('status.completed'), dashboard.milestones.completed, 'var(--ok)'],
                  [t('postsigning.status.overdue'), dashboard.milestones.overdue, 'var(--da)'],
                  [t('postsigning.atRisk'), dashboard.milestones.at_risk, 'var(--wa)'],
                  [
                    t('postsigning.remaining'),
                    dashboard.milestones.total_milestones - dashboard.milestones.completed - dashboard.milestones.overdue - dashboard.milestones.at_risk,
                    'var(--b2)',
                  ],
                ] as const).map(([label, n, color]) => (
                  <span key={String(label)} className="row" style={{ gap: 7 }}>
                    <i style={{ width: 9, height: 9, borderRadius: '50%', background: color, flexShrink: 0 }} />
                    <span className="muted">{label} ({n})</span>
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* All milestones */}
          <div className="col" style={{ gap: 12 }}>
            <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
              <b style={{ fontSize: 'var(--fs-lg)' }}>{t('postsigning.allMilestones')}</b>
              <span className="grow" />
              <Select
                value={msStatusFilter}
                onChange={(e) => setMsStatusFilter(e.target.value)}
                containerStyle={{ width: 170 }}
                options={[
                  { value: '', label: t('postsigning.allStatuses') },
                  { value: 'pending', label: t('status.pending') },
                  { value: 'in_progress', label: t('postsigning.status.in_progress') },
                  { value: 'completed', label: t('status.completed') },
                  { value: 'overdue', label: t('postsigning.status.overdue') },
                ]}
              />
              <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
                {t('postsigning.milestonesCount', { count: filteredMilestones.length })}
              </span>
            </div>
            {milestonesLoading ? (
              <div className="row" style={{ justifyContent: 'center', padding: 32 }}><LoadingSpinner size="md" /></div>
            ) : (
              <Table<MilestoneRow>
                columns={milestoneColumns}
                rows={filteredMilestones}
                rowKey={(m) => m.id}
                empty={
                  <EmptyState
                    icon={msStatusFilter ? FunnelIcon : FlagIcon}
                    title={t('postsigning.noMilestonesFound')}
                    body={msStatusFilter
                      ? t('postsigning.emptyMilestonesFiltered', { defaultValue: 'No milestones match this status — clear the filter to see all.' })
                      : t('postsigning.emptyMilestonesBody', { defaultValue: 'Milestones are dated obligations — they appear once extraction finds target dates in your contracts.' })}
                    action={msStatusFilter ? (
                      <Button variant="secondary" size="sm" onClick={() => setMsStatusFilter('')}>
                        {t('contracts.clearAllFilters')}
                      </Button>
                    ) : undefined}
                  />
                }
              />
            )}
          </div>
        </div>
      )}

      {/* ── Renewals ─────────────────────────────────────────── */}
      {activeTab === 'renewals' && (
        <div className="col" style={{ gap: 14 }}>
          {/* Window stats — clickable filters over the table below */}
          <div className="grid gap-3 grid-cols-2 lg:grid-cols-5">
            <Stat
              icon={ClockIcon}
              label={t('renewals.days30')}
              value={dashboard.renewals.expiring_30_days}
              subTone="var(--da)"
              active={renewalWindow === '30'}
              onClick={() => toggleRenewalWindow('30')}
            />
            <Stat
              icon={ClockIcon}
              label={t('renewals.days60')}
              value={dashboard.renewals.expiring_60_days}
              subTone="var(--wa)"
              active={renewalWindow === '60'}
              onClick={() => toggleRenewalWindow('60')}
            />
            <Stat
              icon={ClockIcon}
              label={t('renewals.days90')}
              value={dashboard.renewals.expiring_90_days}
              active={renewalWindow === '90'}
              onClick={() => toggleRenewalWindow('90')}
            />
            <Stat
              icon={ExclamationTriangleIcon}
              label={t('renewals.expiredNeedsAction')}
              value={dashboard.renewals.expired_recent_count ?? 0}
              sub={dashboard.renewals.expired_value
                ? t('renewals.lapsedValue', { value: `$${(dashboard.renewals.expired_value / 1_000_000).toFixed(1)}M` })
                : undefined}
              subTone="var(--da)"
              active={renewalWindow === 'expired'}
              onClick={() => toggleRenewalWindow('expired')}
            />
            <Stat
              icon={BanknotesIcon}
              label={t('renewals.valueAtRisk')}
              value={dashboard.renewals.total_value_at_risk ? `$${(dashboard.renewals.total_value_at_risk / 1_000_000).toFixed(1)}M` : '$0'}
            />
          </div>

          <div className="col" style={{ gap: 12 }}>
            <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
              <b style={{ fontSize: 'var(--fs-lg)' }}>{t('renewals.title')}</b>
              <span className="grow" />
              <Link to="/renewals">
                <Button variant="ghost" size="sm" iconRight={ArrowTopRightOnSquareIcon}>
                  {t('postsigning.viewFullCalendar')}
                </Button>
              </Link>
              <Button
                variant="secondary"
                size="sm"
                icon={ArrowDownTrayIcon}
                disabled={isExporting}
                onClick={handleExportCalendar}
              >
                {isExporting ? t('renewals.exporting') : t('postsigning.exportCalendar')}
              </Button>
            </div>
            {renewalsLoading ? (
              <div className="row" style={{ justifyContent: 'center', padding: 32 }}><LoadingSpinner size="md" /></div>
            ) : (
              <Table<ContractRenewalInfo>
                columns={renewalColumns}
                rows={filteredRenewals}
                rowKey={(r) => r.contract_id}
                minWidth={960}
                empty={
                  <EmptyState
                    icon={renewalWindow ? FunnelIcon : CheckCircleIcon}
                    title={t('postsigning.noContractsApproachingRenewal')}
                    body={renewalWindow
                      ? t('postsigning.emptyRenewalsFiltered', { defaultValue: 'Nothing falls inside this window — clear the filter to see the full radar.' })
                      : t('postsigning.emptyRenewalsBody', { defaultValue: 'Nothing expires within the next 90 days and no contract has lapsed recently.' })}
                    action={renewalWindow ? (
                      <Button variant="secondary" size="sm" onClick={() => setRenewalWindow('')}>
                        {t('contracts.clearAllFilters')}
                      </Button>
                    ) : undefined}
                  />
                }
              />
            )}
          </div>
        </div>
      )}

      {/* ── Vendors ──────────────────────────────────────────── */}
      {activeTab === 'vendors' && (
        <div className="col" style={{ gap: 14 }}>
          <div className="grid gap-3 grid-cols-2 lg:grid-cols-3">
            <Stat icon={BuildingOfficeIcon} label={t('vendors.totalVendors')} value={dashboard.vendors.total_vendors} />
            <Stat
              icon={ExclamationTriangleIcon}
              label={t('vendors.atRisk')}
              value={dashboard.vendors.at_risk_vendors}
              subTone="var(--da)"
            />
            <Stat
              icon={ChartBarIcon}
              label={t('vendors.avgScore')}
              value={dashboard.vendors.avg_performance_score != null ? dashboard.vendors.avg_performance_score.toFixed(1) : '—'}
              sub={dashboard.vendors.avg_performance_score == null ? t('postsigning.notRated') : undefined}
            />
          </div>

          <div className="col" style={{ gap: 12 }}>
            <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
              <b style={{ fontSize: 'var(--fs-lg)' }}>{t('postsigning.allVendorsCounterparties')}</b>
              <span className="grow" />
              <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
                {vendorsLoading ? '…' : t('postsigning.vendorsCount', { count: vendors.length })}
              </span>
              <Link to="/vendors">
                <Button variant="ghost" size="sm" iconRight={ArrowTopRightOnSquareIcon}>
                  {t('postsigning.viewDetails')}
                </Button>
              </Link>
            </div>
            {vendorsLoading ? (
              <div className="row" style={{ justifyContent: 'center', padding: 32 }}><LoadingSpinner size="md" /></div>
            ) : (
              <Table<VendorListItem>
                columns={vendorColumns}
                rows={vendors}
                rowKey={(v) => v.vendor_name}
                minWidth={900}
                empty={
                  <EmptyState
                    icon={TruckIcon}
                    title={t('postsigning.noVendorData')}
                    body={t('postsigning.emptyVendorsBody', { defaultValue: 'Vendor scorecards are derived from contracts — upload contracts with counterparties to populate this list.' })}
                  />
                }
              />
            )}
          </div>
        </div>
      )}

      {/* ── SLA breach detail drawer ─────────────────────────── */}
      <Drawer
        open={!!selectedBreach}
        title={selectedBreach?.sla_name || ''}
        sub={selectedBreach?.contract_filename}
        onClose={() => setSelectedBreach(null)}
        footer={selectedBreach ? (
          <>
            <span className="grow" />
            <Button variant="ghost" onClick={() => setSelectedBreach(null)}>{t('postsigning.close')}</Button>
            <Link to={`/contracts/${selectedBreach.contract_id}`}>
              <Button variant="primary">{t('postsigning.viewContract')}</Button>
            </Link>
          </>
        ) : undefined}
      >
        {selectedBreach && (
          <div className="col" style={{ gap: 16 }}>
            <div className="row" style={{ gap: 10 }}>
              <Pill tone={SEVERITY_TONE[selectedBreach.breach_severity] || 'n'}>
                {t('postsigning.severityBreach', { severity: t(`risk.${selectedBreach.breach_severity}`, { defaultValue: selectedBreach.breach_severity }) })}
              </Pill>
              <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
                {t('postsigning.consecutiveBreaches', { count: selectedBreach.consecutive_breaches })}
              </span>
            </div>

            {/* Target vs actual */}
            <div className="card card-p">
              <div className="sec-t" style={{ marginBottom: 10 }}>{t('postsigning.performanceMetrics')}</div>
              <div className="row" style={{ gap: 24 }}>
                <span className="col" style={{ gap: 2 }}>
                  <span className="sec-t">{t('postsigning.target')}</span>
                  <span className="num" style={{ fontSize: 'var(--fs-xl)', fontWeight: 600 }}>
                    {selectedBreach.target_display || `${selectedBreach.target_value}`}
                  </span>
                </span>
                <span className="col" style={{ gap: 2 }}>
                  <span className="sec-t">{t('postsigning.actual')}</span>
                  <span className="num" style={{
                    fontSize: 'var(--fs-xl)', fontWeight: 600,
                    color: selectedBreach.deviation_percentage < 0 ? 'var(--da)' : 'var(--ok)',
                  }}>
                    {selectedBreach.actual_display || `${selectedBreach.actual_value}`}
                  </span>
                </span>
              </div>
              <div className="row" style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--b)' }}>
                <span className="muted grow" style={{ fontSize: 'var(--fs-sm)' }}>{t('postsigning.deviation')}</span>
                <span className="num" style={{
                  fontSize: 'var(--fs-sm)', fontWeight: 600,
                  color: selectedBreach.deviation_percentage < 0 ? 'var(--da)' : 'var(--ok)',
                }}>
                  {selectedBreach.deviation_percentage > 0 ? '+' : ''}{selectedBreach.deviation_percentage.toFixed(1)}%
                </span>
              </div>
            </div>

            {/* Facts */}
            <div className="col" style={{ gap: 8, fontSize: 'var(--fs-md)' }}>
              <div className="row">
                <span className="muted grow">{t('postsigning.metricType')}</span>
                <span style={{ fontWeight: 500, textTransform: 'capitalize' }}>{selectedBreach.metric_type.replace(/_/g, ' ')}</span>
              </div>
              <div className="row">
                <span className="muted grow">{t('postsigning.lastMeasured')}</span>
                <span className="num" style={{ fontWeight: 500 }}>{new Date(selectedBreach.measured_at).toLocaleString()}</span>
              </div>
              {selectedBreach.penalty_amount != null && selectedBreach.penalty_amount > 0 && (
                <div className="row">
                  <span className="muted grow">{t('postsigning.penaltyAmount')}</span>
                  <span className="num" style={{ fontWeight: 600, color: 'var(--da)' }}>
                    ${selectedBreach.penalty_amount.toLocaleString()}
                  </span>
                </div>
              )}
            </div>

            {/* Deviation bar — only for percentage metrics */}
            {selectedBreach.metric_unit === 'percentage' && (
              <div className="col" style={{ gap: 6 }}>
                <div className="row faint" style={{ fontSize: 'var(--fs-xs)' }}>
                  <span>0%</span>
                  <span className="grow" style={{ textAlign: 'center' }}>{t('postsigning.targetValue', { value: selectedBreach.target_value.toFixed(1) })}</span>
                  <span>100%</span>
                </div>
                <span className="bar" style={{ width: '100%', height: 8, position: 'relative' }}>
                  <i style={{
                    width: `${Math.min(selectedBreach.actual_value, 100)}%`,
                    background: selectedBreach.actual_value >= selectedBreach.target_value ? 'var(--ok)' : 'var(--da)',
                  }} />
                  <span style={{
                    position: 'absolute', top: 0, bottom: 0, width: 2, background: 'var(--t)', opacity: .6,
                    left: `${Math.min(selectedBreach.target_value, 100)}%`,
                  }} />
                </span>
              </div>
            )}
          </div>
        )}
      </Drawer>

      {/* ── Record SLA measurement drawer ────────────────────── */}
      <Drawer
        open={!!measureSla}
        title={t('postsigning.recordMeasurementTitle')}
        sub={measureSla?.sla_name}
        onClose={() => setMeasureSla(null)}
        footer={
          <>
            <span className="grow" />
            <Button variant="ghost" onClick={() => setMeasureSla(null)}>{t('common.cancel')}</Button>
            <Button
              variant="primary"
              disabled={recordMeasurementMutation.isPending || actualValue.trim() === ''}
              onClick={submitMeasurement}
            >
              {recordMeasurementMutation.isPending ? t('common.saving') : t('postsigning.recordMeasurement')}
            </Button>
          </>
        }
      >
        {measureSla && (
          <div className="col" style={{ gap: 14 }}>
            <div className="card card-p row" style={{ fontSize: 'var(--fs-md)' }}>
              <span className="muted grow">{t('postsigning.metric')} · {t('postsigning.target')}</span>
              <span style={{ fontWeight: 500 }}>
                {(measureSla.metric_type?.replace(/_/g, ' ') || '')} {measureSla.target_value != null ? `(≥ ${measureSla.target_value})` : ''}
              </span>
            </div>

            <Field
              label={t('postsigning.actualValue')}
              type="number"
              value={actualValue}
              onChange={(e) => setActualValue(e.target.value)}
              placeholder={t('postsigning.actualValuePlaceholder', { defaultValue: 'e.g. 99.2' })}
              autoFocus
            />

            <div>
              <label className="lbl">{t('postsigning.measureNotes')}</label>
              <div className="inp" style={{ height: 'auto', alignItems: 'stretch' }}>
                <textarea
                  value={measureNotes}
                  onChange={(e) => setMeasureNotes(e.target.value)}
                  rows={3}
                  placeholder={t('postsigning.measureNotesPlaceholder', { defaultValue: 'Optional — period, source…' })}
                  style={{ resize: 'vertical', padding: '8px 0' }}
                />
              </div>
            </div>

            {measureError && (
              <div className="banner banner-da">
                <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
                <span>{measureError}</span>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </div>
  )
}
