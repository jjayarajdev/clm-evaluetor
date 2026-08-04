/* Relationship detail — Direction B redesign (governance flagship).
   Two-party header with health banding → ui Tabs (KPIs / Team / Improvements /
   History / Overview) → gap-severity cards, KPI scorecard Table, prototype-style
   perception GapRows with a severe-gap banner → team rows → improvement rows
   with progress Bars → history trend + Table → Drawer forms for add-KPI,
   score submission and status recording. All queries, mutations, the category
   filter and lazy History fetching are unchanged from the pre-redesign page. */
import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  ArrowsRightLeftIcon,
  ChartBarIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  HeartIcon,
  LightBulbIcon,
  PlusIcon,
  Squares2X2Icon,
  SparklesIcon,
  UserGroupIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import {
  Avatar,
  Bar,
  Button,
  Chip,
  Drawer,
  EmptyState,
  Field,
  IconButton,
  Pill,
  Select,
  Table,
  Tabs,
  Tag,
  Tooltip,
  useToast,
} from '@/components/ui'
import type { PillTone, TableColumn } from '@/components/ui'
import type {
  KPI,
  KPICreate,
  PerceptionScoreCreate,
  GapSeverity,
  ImprovementPoint,
} from '@/types/governance'
import type {
  PerformanceStatus,
  RelationshipHistoryCreate,
  RelationshipHistoryEntry,
} from '@/types/fitgap'

// ── Tone maps ────────────────────────────────────────────────────

/** Live detail-page health banding: ≥70 ok, ≥40 warn, else danger. */
function healthTone(score: number): string {
  return score >= 70 ? 'var(--ok)' : score >= 40 ? 'var(--wa)' : 'var(--da)'
}

const GAP_TONE: Record<GapSeverity, PillTone> = {
  critical: 'da',
  significant: 'wa',
  moderate: 'wa',
  minor: 'in',
  aligned: 'ok',
}

const GAP_VAR: Record<GapSeverity, string> = {
  critical: 'var(--da)',
  significant: 'var(--wa)',
  moderate: 'var(--wa)',
  minor: 'var(--in)',
  aligned: 'var(--ok)',
}

const PRIORITY_TONE: Record<string, PillTone> = { critical: 'da', high: 'wa', medium: 'wa', low: 'n' }

const IMPROVEMENT_STATUS_TONE: Record<string, PillTone> = {
  completed: 'ok', in_progress: 'in', blocked: 'da', open: 'n', cancelled: 'n',
}

const PERF_STATUS_TONE: Record<PerformanceStatus, PillTone> = {
  excellent: 'ok', good: 'ok', acceptable: 'in', concerning: 'wa', poor: 'wa', critical: 'da',
}

const PERF_STATUS_LABELS: Record<PerformanceStatus, string> = {
  excellent: 'Excellent',
  good: 'Good',
  acceptable: 'Acceptable',
  concerning: 'Concerning',
  poor: 'Poor',
  critical: 'Critical',
}

const PERF_STATUS_ORDER: PerformanceStatus[] = ['critical', 'poor', 'concerning', 'acceptable', 'good', 'excellent']

function perfBarTone(status: PerformanceStatus): string {
  const i = PERF_STATUS_ORDER.indexOf(status)
  return i >= 4 ? 'var(--ok)' : i >= 2 ? 'var(--wa)' : 'var(--da)'
}

const CATEGORY_LABELS: Record<string, string> = {
  service_delivery: 'Service Delivery',
  timeliness: 'Timeliness',
  quality: 'Quality',
  compliance: 'Compliance',
  communication: 'Communication',
  innovation: 'Innovation',
  cost_efficiency: 'Cost Efficiency',
  satisfaction: 'Satisfaction',
  other: 'Other',
}

const TABS = ['KPIs', 'Team', 'Improvements', 'History', 'Overview'] as const
type Tab = typeof TABS[number]

// ── Perception gap row (prototype GapRow, 0–10 scale) ────────────

function GapRow({ kpi }: { kpi: KPI }) {
  const { t } = useTranslation()
  const internal = kpi.latest_internal_score != null ? Number(kpi.latest_internal_score) : null
  const external = kpi.latest_external_score != null ? Number(kpi.latest_external_score) : null
  const gap = kpi.latest_gap != null ? Number(kpi.latest_gap) : null
  const severity = kpi.latest_gap_severity ?? null
  const bad = severity === 'critical' || severity === 'significant'
  const intPct = internal != null ? internal * 10 : null
  const extPct = external != null ? external * 10 : null

  return (
    <div className="row" style={{ gap: 12, minHeight: 46, borderBottom: '1px solid var(--b)', padding: '0 2px' }}>
      <span className="trunc" style={{ width: 170, flexShrink: 0, fontSize: 'var(--fs-md)', fontWeight: 500 }}>
        {kpi.name}
      </span>
      <span className="grow" style={{ position: 'relative', height: 26, minWidth: 120 }}>
        <span style={{ position: 'absolute', top: 11, left: 0, right: 0, height: 4, borderRadius: 2, background: 'var(--s2)' }} />
        {intPct != null && extPct != null && (
          <span style={{
            position: 'absolute', top: 11, height: 4, borderRadius: 2,
            left: `${Math.min(intPct, extPct)}%`, width: `${Math.abs(intPct - extPct)}%`,
            background: bad ? 'var(--da-b)' : 'var(--b)',
          }} />
        )}
        {intPct != null && (
          <Tooltip label={t('governance.intScore', { score: internal!.toFixed(1) })}>
            <span style={{
              position: 'absolute', top: 5, left: `calc(${intPct}% - 2px)`, width: 4, height: 16,
              borderRadius: 2, background: 'var(--p)',
            }} />
          </Tooltip>
        )}
        {extPct != null && (
          <Tooltip label={t('governance.extScore', { score: external!.toFixed(1) })}>
            <span style={{
              position: 'absolute', top: 5, left: `calc(${extPct}% - 2px)`, width: 4, height: 16,
              borderRadius: 2, background: 'var(--wa)',
            }} />
          </Tooltip>
        )}
      </span>
      <span className="mono num" style={{
        width: 48, textAlign: 'right', fontSize: 'var(--fs-sm)', fontWeight: 600,
        color: bad ? 'var(--da)' : 'var(--f)',
      }}>
        {gap != null ? `${gap > 0 ? '+' : ''}${gap.toFixed(1)}` : '—'}
      </span>
      {severity ? (
        <Pill tone={GAP_TONE[severity]}>{t(`governance.gapSeverity.${severity}`, { defaultValue: severity })}</Pill>
      ) : (
        <span style={{ width: 60 }} />
      )}
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────

export default function RelationshipDetailPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [activeTab, setActiveTab] = useState<Tab>('KPIs')
  const [showAddKPI, setShowAddKPI] = useState(false)
  const [showScore, setShowScore] = useState<string | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [scoreForm, setScoreForm] = useState<Partial<PerceptionScoreCreate>>({ perspective: 'internal', score: 5 })
  const [kpiForm, setKpiForm] = useState<Partial<KPICreate>>({
    category: 'service_delivery',
    is_perception_based: true,
    weight: 1,
    frequency: 'quarterly',
  })

  const { data: relationship, isLoading } = useQuery({
    queryKey: ['relationship', id],
    queryFn: () => api.getRelationship(id!),
    enabled: !!id,
  })

  const { data: kpis = [] } = useQuery({
    queryKey: ['kpis', id],
    queryFn: () => api.getKPIs({ relationship_id: id }),
    enabled: !!id,
  })

  const { data: gapSummary } = useQuery({
    queryKey: ['gap-summary', id],
    queryFn: () => api.getRelationshipGapSummary(id!),
    enabled: !!id,
  })

  const { data: improvements = [] } = useQuery({
    queryKey: ['improvements', id],
    queryFn: () => api.getImprovements({ relationship_id: id }),
    enabled: !!id,
  })

  const { data: team = [] } = useQuery({
    queryKey: ['team', id],
    queryFn: () => api.getRelationshipTeam(id!),
    enabled: !!id,
  })

  const createKPIMutation = useMutation({
    mutationFn: (data: KPICreate) => api.createKPI(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['kpis', id] })
      setShowAddKPI(false)
      setKpiForm({ category: 'service_delivery', is_perception_based: true, weight: 1, frequency: 'quarterly' })
      toast({ text: t('governance.kpiCreated', { defaultValue: 'KPI created' }) })
    },
  })

  const submitScoreMutation = useMutation({
    mutationFn: ({ kpiId, data }: { kpiId: string; data: PerceptionScoreCreate }) =>
      api.submitPerceptionScore(kpiId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['kpis', id] })
      queryClient.invalidateQueries({ queryKey: ['gap-summary', id] })
      setShowScore(null)
      setScoreForm({ perspective: 'internal', score: 5 })
      toast({ text: t('governance.scoreSubmitted', { defaultValue: 'Perception score submitted' }) })
    },
  })

  const generateImprovementsMutation = useMutation({
    mutationFn: () => api.generateImprovementsFromGaps(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['improvements', id] })
      toast({ text: t('governance.improvementsGenerated', { defaultValue: 'Improvement points generated from gaps' }) })
    },
  })

  // Performance History (lazy — fetched when the History tab is open)
  const { data: perfTrend } = useQuery({
    queryKey: ['perf-trend', id],
    queryFn: () => api.getPerformanceTrend(id!),
    enabled: !!id && activeTab === 'History',
  })

  const { data: historyData } = useQuery({
    queryKey: ['rel-history', id],
    queryFn: () => api.getRelationshipHistory(id!),
    enabled: !!id && activeTab === 'History',
  })
  const historyEntries = historyData?.items ?? []

  const [showRecordStatus, setShowRecordStatus] = useState(false)
  const [statusForm, setStatusForm] = useState<Partial<RelationshipHistoryCreate>>({
    status: 'good',
    period: new Date().toISOString().slice(0, 7),
  })

  const recordStatusMutation = useMutation({
    mutationFn: (data: RelationshipHistoryCreate) => api.recordRelationshipStatus(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rel-history', id] })
      queryClient.invalidateQueries({ queryKey: ['perf-trend', id] })
      setShowRecordStatus(false)
      setStatusForm({ status: 'good', period: new Date().toISOString().slice(0, 7) })
      toast({ text: t('governance.statusRecorded', { defaultValue: 'Performance status recorded' }) })
    },
  })

  if (isLoading || !relationship) {
    return (
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const orgAName = relationship.org_a?.name || t('governance.orgA')
  const orgBName = relationship.org_b?.name || t('governance.orgB')
  const health = relationship.health_score

  // KPI category filter
  const categoryCounts: Record<string, number> = {}
  kpis.forEach((k) => {
    const cat = k.category || 'other'
    categoryCounts[cat] = (categoryCounts[cat] || 0) + 1
  })
  const categories = Object.keys(categoryCounts).sort((a, b) => (categoryCounts[b] || 0) - (categoryCounts[a] || 0))
  const filteredKpis = kpis.filter((kpi) => selectedCategory === 'all' || (kpi.category || 'other') === selectedCategory)
  const scoredKpis = kpis.filter((k) => k.latest_internal_score != null || k.latest_external_score != null)
  const severeGaps = (gapSummary?.gaps ?? []).filter(
    (g) => g.gap.severity === 'critical' || g.gap.severity === 'significant'
  )

  const kpiColumns: TableColumn<KPI>[] = [
    {
      key: 'name',
      header: t('governance.kpi'),
      render: (kpi) => (
        <span style={{ minWidth: 0, display: 'block' }}>
          <span className="trunc" style={{ display: 'block', fontWeight: 500 }}>{kpi.name}</span>
          {kpi.description && (
            <span className="faint trunc" style={{ display: 'block', fontSize: 'var(--fs-sm)', marginTop: 1, maxWidth: 260 }}>
              {kpi.description}
            </span>
          )}
        </span>
      ),
    },
    {
      key: 'category',
      header: t('governance.category'),
      width: 130,
      render: (kpi) => (
        <Tag>{t(`governance.kpiCategories.${kpi.category}`, { defaultValue: (kpi.category || '').replace(/_/g, ' ') })}</Tag>
      ),
    },
    {
      key: 'internal',
      header: t('governance.internal'),
      width: 90,
      align: 'right',
      render: (kpi) => (
        <span className="num" style={{ fontWeight: 600, color: 'var(--p)' }}>
          {kpi.latest_internal_score != null ? Number(kpi.latest_internal_score).toFixed(1) : '—'}
        </span>
      ),
    },
    {
      key: 'external',
      header: t('governance.external'),
      width: 90,
      align: 'right',
      render: (kpi) => (
        <span className="num" style={{ fontWeight: 600, color: 'var(--wa)' }}>
          {kpi.latest_external_score != null ? Number(kpi.latest_external_score).toFixed(1) : '—'}
        </span>
      ),
    },
    {
      key: 'gap',
      header: t('governance.gap'),
      width: 80,
      align: 'right',
      render: (kpi) => {
        const gap = kpi.latest_gap != null ? Number(kpi.latest_gap) : null
        if (gap == null) return <span className="faint">—</span>
        return (
          <span className="mono num" style={{
            fontWeight: 600,
            color: gap > 0 ? 'var(--da)' : gap < 0 ? 'var(--in)' : 'var(--ok)',
          }}>
            {gap > 0 ? '+' : ''}{gap.toFixed(1)}
          </span>
        )
      },
    },
    {
      key: 'severity',
      header: t('governance.severity'),
      width: 110,
      render: (kpi) => kpi.latest_gap_severity
        ? <Pill tone={GAP_TONE[kpi.latest_gap_severity]}>{t(`governance.gapSeverity.${kpi.latest_gap_severity}`, { defaultValue: kpi.latest_gap_severity })}</Pill>
        : <span className="faint">—</span>,
    },
    {
      key: 'actions',
      header: t('common.actions'),
      width: 90,
      render: (kpi) => (
        <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); setShowScore(kpi.id) }}>
          {t('governance.score')}
        </Button>
      ),
    },
  ]

  const historyColumns: TableColumn<RelationshipHistoryEntry>[] = [
    { key: 'period', header: t('governance.period'), width: 100, render: (e) => <span className="num" style={{ fontWeight: 500 }}>{e.period}</span> },
    {
      key: 'status', header: t('common.status'), width: 130,
      render: (e) => <Pill tone={PERF_STATUS_TONE[e.status]}>{t(`governance.perfStatus.${e.status}`, { defaultValue: PERF_STATUS_LABELS[e.status] })}</Pill>,
    },
    {
      key: 'previous_status', header: t('governance.previous'), width: 130,
      render: (e) => e.previous_status
        ? <Pill tone={PERF_STATUS_TONE[e.previous_status]}>{t(`governance.perfStatus.${e.previous_status}`, { defaultValue: PERF_STATUS_LABELS[e.previous_status] })}</Pill>
        : <span className="faint">—</span>,
    },
    {
      key: 'overall_score', header: t('governance.score'), width: 70, align: 'right',
      render: (e) => <span className="num" style={{ fontWeight: 600 }}>{e.overall_score != null ? e.overall_score : '—'}</span>,
    },
    { key: 'trigger', header: t('governance.trigger'), render: (e) => <span className="muted">{e.trigger || '—'}</span> },
    {
      key: 'notes', header: t('governance.notes'),
      render: (e) => <span className="muted trunc" style={{ display: 'block', maxWidth: 220 }}>{e.notes || '—'}</span>,
    },
  ]

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header — two-party pairing */}
      <div className="row" style={{ gap: 12, alignItems: 'flex-start' }}>
        <IconButton
          icon={ArrowLeftIcon}
          label={t('common.back', { defaultValue: 'Back' })}
          onClick={() => navigate('/relationships')}
        />
        <div className="grow" style={{ minWidth: 0 }}>
          <div className="row" style={{ gap: 8, minWidth: 0 }}>
            <span className="row" style={{ gap: 4, flexShrink: 0 }}>
              <Avatar name={orgAName} size={26} />
              <ArrowsRightLeftIcon style={{ width: 14, height: 14, color: 'var(--f)' }} aria-hidden />
              <Avatar name={orgBName} size={26} />
            </span>
            <h1 className="trunc" style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600, letterSpacing: '-.5px' }}>
              {orgAName} ↔ {orgBName}
            </h1>
          </div>
          <div className="row" style={{ gap: 8, marginTop: 7, flexWrap: 'wrap' }}>
            <Tag>
              {t(`governance.relationshipTypes.${relationship.relationship_type}`, { defaultValue: relationship.relationship_type })}
            </Tag>
            <Tag>
              {t(`governance.tiers.${relationship.governance_tier}`, { defaultValue: relationship.governance_tier })}
            </Tag>
            <span className="row" style={{ gap: 4, color: healthTone(health) }}>
              <HeartIcon style={{ width: 14, height: 14 }} aria-hidden />
              <span className="num" style={{ fontSize: 'var(--fs-sm)', fontWeight: 600 }}>
                {t('governance.healthLabel', { score: health })}
              </span>
            </span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <Tabs<Tab>
        tabs={[
          { value: 'KPIs', label: t('governance.tabs.kpis', { defaultValue: 'KPIs' }), icon: ChartBarIcon, count: kpis.length > 0 ? kpis.length : undefined },
          { value: 'Team', label: t('governance.tabs.team', { defaultValue: 'Team' }), icon: UserGroupIcon },
          { value: 'Improvements', label: t('governance.tabs.improvements', { defaultValue: 'Improvements' }), icon: LightBulbIcon, count: improvements.length > 0 ? improvements.length : undefined },
          { value: 'History', label: t('governance.tabs.history', { defaultValue: 'History' }), icon: ClockIcon },
          { value: 'Overview', label: t('governance.tabs.overview', { defaultValue: 'Overview' }), icon: Squares2X2Icon },
        ]}
        value={activeTab}
        onChange={setActiveTab}
      />

      {/* KPIs tab — the perception scorecard */}
      {activeTab === 'KPIs' && (
        <div className="col" style={{ gap: 14 }}>
          {/* Gap severity summary */}
          {gapSummary && (
            <div className="grid gap-2 grid-cols-2 md:grid-cols-5">
              {([
                { severity: 'critical' as GapSeverity, count: gapSummary.critical_gaps },
                { severity: 'significant' as GapSeverity, count: gapSummary.significant_gaps },
                { severity: 'moderate' as GapSeverity, count: gapSummary.moderate_gaps },
                { severity: 'minor' as GapSeverity, count: gapSummary.minor_gaps },
                { severity: 'aligned' as GapSeverity, count: gapSummary.aligned },
              ]).map((item) => (
                <div key={item.severity} className="card card-p" style={{ textAlign: 'center' }}>
                  <div className="num" style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600, color: GAP_VAR[item.severity] }}>
                    {item.count}
                  </div>
                  <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--m)', marginTop: 2 }}>
                    {t(`governance.gapSeverity.${item.severity}`, { defaultValue: item.severity })}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
            <span className="sec-t">{t('governance.kpiPerceptionScorecard')}</span>
            <span className="grow" />
            {gapSummary && gapSummary.critical_gaps + gapSummary.significant_gaps > 0 && (
              <Button
                variant="secondary"
                size="sm"
                icon={SparklesIcon}
                disabled={generateImprovementsMutation.isPending}
                onClick={() => generateImprovementsMutation.mutate()}
              >
                {generateImprovementsMutation.isPending ? t('governance.generating') : t('governance.generateImprovementsFromGaps')}
              </Button>
            )}
            <Button variant="primary" size="sm" icon={PlusIcon} onClick={() => setShowAddKPI(true)}>
              {t('governance.addKpi')}
            </Button>
          </div>

          {/* Category filter */}
          {kpis.length > 0 && (
            <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
              <Chip on={selectedCategory === 'all'} onClick={() => setSelectedCategory('all')}>
                {t('governance.allCount', { count: kpis.length })}
              </Chip>
              {categories.map((cat) => (
                <Chip key={cat} on={selectedCategory === cat} onClick={() => setSelectedCategory(cat)}>
                  {t(`governance.kpiCategories.${cat}`, { defaultValue: CATEGORY_LABELS[cat] || cat })} ({categoryCounts[cat]})
                </Chip>
              ))}
            </div>
          )}

          {/* KPI scorecard table */}
          <Table<KPI>
            columns={kpiColumns}
            rows={filteredKpis}
            rowKey={(kpi) => kpi.id}
            minWidth={760}
            empty={
              <EmptyState
                icon={ChartBarIcon}
                title={t('governance.noKpisYet')}
                body={t('governance.kpisEmptyBody', { defaultValue: 'KPIs measure the relationship from both sides. Add one to start scoring.' })}
                action={<Button variant="primary" icon={PlusIcon} onClick={() => setShowAddKPI(true)}>{t('governance.addKpi')}</Button>}
              />
            }
          />

          {/* Perception gap analysis */}
          {scoredKpis.length > 0 && (
            <div className="card">
              <div className="row" style={{ padding: '13px 16px', borderBottom: '1px solid var(--b)', gap: 14, flexWrap: 'wrap' }}>
                <b style={{ fontSize: 'var(--fs-lg)' }}>{t('governance.perceptionGapComparison')}</b>
                <span className="row" style={{ gap: 6, fontSize: 'var(--fs-sm)', color: 'var(--m)' }}>
                  <span style={{ width: 4, height: 14, borderRadius: 2, background: 'var(--p)' }} />
                  {t('governance.internal')}
                </span>
                <span className="row" style={{ gap: 6, fontSize: 'var(--fs-sm)', color: 'var(--m)' }}>
                  <span style={{ width: 4, height: 14, borderRadius: 2, background: 'var(--wa)' }} />
                  {t('governance.external')}
                </span>
              </div>
              <div className="card-p" style={{ paddingTop: 4, paddingBottom: 4 }}>
                {scoredKpis.map((kpi) => <GapRow key={kpi.id} kpi={kpi} />)}
              </div>
              {severeGaps.length > 0 && (
                <div className="card-p" style={{ paddingTop: 12 }}>
                  <div className="banner banner-wa">
                    <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
                    <span>
                      <b>{t('governance.severeGapsCount', { count: severeGaps.length, defaultValue: '{{count}} severe gaps.' })}</b>{' '}
                      {severeGaps
                        .map((g) => `${g.kpi_name} (${g.gap.gap_value > 0 ? '+' : ''}${Number(g.gap.gap_value).toFixed(1)})`)
                        .join(', ')}
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Team tab */}
      {activeTab === 'Team' && (
        <div className="card">
          <div className="row" style={{ padding: '13px 16px', borderBottom: '1px solid var(--b)', gap: 8 }}>
            <UserGroupIcon style={{ width: 16, height: 16, color: 'var(--f)' }} aria-hidden />
            <b style={{ fontSize: 'var(--fs-lg)' }}>{t('governance.teamMembersCount', { count: team.length })}</b>
          </div>
          {team.length > 0 ? (
            <div>
              {team.map((member, n) => {
                const name = member.user_name || member.user?.full_name || member.user?.username || t('governance.unknown')
                return (
                  <div
                    key={member.id}
                    className="row"
                    style={{ gap: 10, padding: '10px 16px', borderBottom: n < team.length - 1 ? '1px solid var(--b)' : 0 }}
                  >
                    <Avatar name={name} size={28} />
                    <span className="grow" style={{ minWidth: 0 }}>
                      <span className="trunc" style={{ display: 'block', fontSize: 'var(--fs-md)', fontWeight: 500 }}>{name}</span>
                      <span className="faint" style={{ display: 'block', fontSize: 'var(--fs-sm)', textTransform: 'capitalize' }}>
                        {member.role.replace(/_/g, ' ')}
                        {member.responsibilities && Array.isArray(member.responsibilities) && member.responsibilities.length > 0 && (
                          <> · {member.responsibilities.join(' · ')}</>
                        )}
                      </span>
                    </span>
                    {(member.is_primary || member.is_primary_contact) && (
                      <Pill tone="p" dot={false}>{t('governance.primary')}</Pill>
                    )}
                    {member.receives_alerts && (
                      <Pill tone="in" dot={false}>{t('governance.alerts')}</Pill>
                    )}
                  </div>
                )
              })}
            </div>
          ) : (
            <EmptyState
              icon={UserGroupIcon}
              title={t('governance.noTeamMembers')}
              body={t('governance.teamEmptyBody', { defaultValue: 'No one is assigned to this relationship yet.' })}
            />
          )}
        </div>
      )}

      {/* Improvements tab */}
      {activeTab === 'Improvements' && (
        <div className="col" style={{ gap: 12 }}>
          <div className="row" style={{ gap: 8 }}>
            <LightBulbIcon style={{ width: 16, height: 16, color: 'var(--f)' }} aria-hidden />
            <span className="sec-t">{t('governance.improvementPointsCount', { count: improvements.length })}</span>
          </div>
          <div className="card">
            {improvements.map((imp: ImprovementPoint, n: number) => {
              const pct = imp.progress_percentage ?? imp.progress ?? 0
              return (
                <div
                  key={imp.id}
                  className="col"
                  style={{ gap: 8, padding: '12px 16px', borderBottom: n < improvements.length - 1 ? '1px solid var(--b)' : 0 }}
                >
                  <div className="row" style={{ gap: 8, alignItems: 'flex-start' }}>
                    <span className="grow" style={{ minWidth: 0 }}>
                      <span style={{ display: 'block', fontSize: 'var(--fs-md)', fontWeight: 500 }}>{imp.title}</span>
                      {imp.description && (
                        <span className="faint" style={{ display: 'block', fontSize: 'var(--fs-sm)', marginTop: 2, lineHeight: 1.5 }}>
                          {imp.description}
                        </span>
                      )}
                    </span>
                    <Pill tone={PRIORITY_TONE[imp.priority] || 'n'}>
                      {t(`risk.${imp.priority}`, { defaultValue: imp.priority })}
                    </Pill>
                    <Pill tone={IMPROVEMENT_STATUS_TONE[imp.status] || 'n'}>
                      {t(`governance.improvementStatus.${imp.status}`, { defaultValue: imp.status.replace(/_/g, ' ') })}
                    </Pill>
                  </div>
                  <div className="row" style={{ gap: 8 }}>
                    <Bar value={pct} width={120} tone={pct === 100 ? 'var(--ok)' : undefined} />
                    <span className="mono num faint" style={{ fontSize: 'var(--fs-sm)' }}>
                      {pct}%
                      {imp.action_count
                        ? ` ${t('governance.actionsProgress', { completed: imp.completed_action_count ?? 0, total: imp.action_count })}`
                        : ''}
                    </span>
                  </div>
                </div>
              )
            })}
            {improvements.length === 0 && (
              <EmptyState
                icon={LightBulbIcon}
                title={t('governance.noImprovementsYet')}
                body={t('governance.improvementsEmptyBody', { defaultValue: 'Improvement points are generated from severe perception gaps, or raised by hand.' })}
              />
            )}
          </div>
        </div>
      )}

      {/* History tab */}
      {activeTab === 'History' && (
        <div className="col" style={{ gap: 14 }}>
          <div className="row" style={{ gap: 8 }}>
            <span className="sec-t">{t('governance.performanceHistory')}</span>
            <span className="grow" />
            <Button variant="primary" size="sm" icon={PlusIcon} onClick={() => setShowRecordStatus(true)}>
              {t('governance.recordStatus')}
            </Button>
          </div>

          {/* Trend visualization */}
          {perfTrend && perfTrend.trend.length > 0 && (
            <div className="card">
              <div className="row" style={{ padding: '13px 16px', borderBottom: '1px solid var(--b)', gap: 8 }}>
                <b style={{ fontSize: 'var(--fs-lg)' }}>{t('governance.performanceTrend')}</b>
                <span className="grow" />
                {perfTrend.current_status && (
                  <Pill tone={PERF_STATUS_TONE[perfTrend.current_status]}>
                    {t('governance.currentStatus', {
                      status: t(`governance.perfStatus.${perfTrend.current_status}`, { defaultValue: PERF_STATUS_LABELS[perfTrend.current_status] }),
                    })}
                  </Pill>
                )}
              </div>
              <div className="card-p">
                <div className="row" style={{ alignItems: 'flex-end', gap: 4, height: 128 }}>
                  {perfTrend.trend.map((point, i) => {
                    const heightPct = Math.max(10, point.overall_score ?? 50)
                    return (
                      <div key={i} className="col grow" style={{ alignItems: 'center', gap: 4, height: '100%', justifyContent: 'flex-end' }}>
                        <div
                          style={{
                            width: '100%', borderRadius: '3px 3px 0 0', height: `${heightPct}%`,
                            background: perfBarTone(point.status),
                          }}
                          title={`${point.period}: ${t(`governance.perfStatus.${point.status}`, { defaultValue: PERF_STATUS_LABELS[point.status] })} (${point.overall_score ?? '—'})`}
                        />
                        <span className="faint trunc num" style={{ fontSize: 'var(--fs-xs)', width: '100%', textAlign: 'center' }}>
                          {point.period}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          )}

          {/* History table */}
          <Table<RelationshipHistoryEntry>
            columns={historyColumns}
            rows={historyEntries}
            rowKey={(e) => e.id}
            minWidth={760}
            empty={
              <EmptyState
                icon={ClockIcon}
                title={t('governance.noPerformanceHistory')}
                body={t('governance.historyEmptyBody', { defaultValue: 'Record a periodic status to build the performance timeline.' })}
                action={<Button variant="primary" icon={PlusIcon} onClick={() => setShowRecordStatus(true)}>{t('governance.recordStatus')}</Button>}
              />
            }
          />
        </div>
      )}

      {/* Overview tab */}
      {activeTab === 'Overview' && (
        <div className="grid gap-4 grid-cols-1 md:grid-cols-2">
          <div className="card card-p col" style={{ gap: 12 }}>
            <div className="sec-t">{t('governance.details')}</div>
            <div className="col" style={{ gap: 10 }}>
              <div>
                <div className="faint" style={{ fontSize: 'var(--fs-sm)' }}>{t('governance.type')}</div>
                <div style={{ fontSize: 'var(--fs-md)', fontWeight: 500, textTransform: 'capitalize' }}>
                  {t(`governance.relationshipTypes.${relationship.relationship_type}`, { defaultValue: relationship.relationship_type })}
                </div>
              </div>
              <div>
                <div className="faint" style={{ fontSize: 'var(--fs-sm)' }}>{t('common.status')}</div>
                <div style={{ marginTop: 2 }}>
                  <Pill tone={relationship.status === 'active' ? 'ok' : relationship.status === 'at_risk' ? 'da' : relationship.status === 'on_hold' ? 'wa' : 'n'}>
                    {t(`governance.relationshipStatus.${relationship.status}`, { defaultValue: relationship.status })}
                  </Pill>
                </div>
              </div>
              <div>
                <div className="faint" style={{ fontSize: 'var(--fs-sm)' }}>{t('governance.governanceTier')}</div>
                <div style={{ fontSize: 'var(--fs-md)', fontWeight: 500, textTransform: 'capitalize' }}>
                  {t(`governance.tiers.${relationship.governance_tier}`, { defaultValue: relationship.governance_tier })}
                </div>
              </div>
              {relationship.annual_value && (
                <div>
                  <div className="faint" style={{ fontSize: 'var(--fs-sm)' }}>{t('governance.annualValue')}</div>
                  <div className="num" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                    {relationship.currency || '$'}{Number(relationship.annual_value).toLocaleString()}
                  </div>
                </div>
              )}
              {relationship.description && (
                <div>
                  <div className="faint" style={{ fontSize: 'var(--fs-sm)' }}>{t('governance.description')}</div>
                  <div className="muted" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.5 }}>{relationship.description}</div>
                </div>
              )}
            </div>
          </div>
          <div className="card card-p col" style={{ gap: 12 }}>
            <div className="sec-t">{t('governance.summary')}</div>
            <div className="col" style={{ gap: 10 }}>
              {[
                { label: t('governance.activeKpis'), value: kpis.length },
                { label: t('governance.teamMembers'), value: team.length },
                {
                  label: t('governance.openImprovements'),
                  value: improvements.filter((i) => i.status !== 'completed' && i.status !== 'cancelled').length,
                },
                { label: t('governance.perceptionGaps'), value: gapSummary?.kpis_with_gaps || 0 },
              ].map((row) => (
                <div key={row.label} className="row" style={{ gap: 10 }}>
                  <span className="muted" style={{ fontSize: 'var(--fs-md)' }}>{row.label}</span>
                  <span className="grow" />
                  <span className="num" style={{ fontSize: 'var(--fs-md)', fontWeight: 600 }}>{row.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Score drawer */}
      <Drawer
        open={!!showScore}
        title={t('governance.submitScore')}
        onClose={() => setShowScore(null)}
        width={400}
        footer={
          <>
            <span className="grow" />
            <Button variant="ghost" onClick={() => setShowScore(null)}>{t('common.cancel')}</Button>
            <Button
              variant="primary"
              disabled={submitScoreMutation.isPending}
              onClick={() => {
                if (showScore && scoreForm.perspective && scoreForm.score) {
                  submitScoreMutation.mutate({ kpiId: showScore, data: scoreForm as PerceptionScoreCreate })
                }
              }}
            >
              {submitScoreMutation.isPending ? t('governance.submitting') : t('governance.submit')}
            </Button>
          </>
        }
      >
        <div className="col" style={{ gap: 14 }}>
          <Select
            label={t('governance.perspective')}
            value={scoreForm.perspective || 'internal'}
            onChange={(e) => setScoreForm({ ...scoreForm, perspective: e.target.value as PerceptionScoreCreate['perspective'] })}
            options={[
              { value: 'internal', label: t('governance.sides.internal') },
              { value: 'external', label: t('governance.sides.external') },
            ]}
          />
          <div>
            <label className="lbl">
              {t('governance.score')}{' '}
              <span className="num" style={{ color: 'var(--p)', fontWeight: 700 }}>{scoreForm.score}/10</span>
            </label>
            <input
              type="range"
              min={1}
              max={10}
              value={scoreForm.score || 5}
              onChange={(e) => setScoreForm({ ...scoreForm, score: Number(e.target.value) })}
              style={{ width: '100%', accentColor: 'var(--p)' }}
            />
            <div className="row faint" style={{ fontSize: 'var(--fs-xs)' }}>
              <span>{t('governance.perfStatus.poor')}</span>
              <span className="grow" />
              <span>{t('governance.perfStatus.excellent')}</span>
            </div>
          </div>
          <Field
            label={t('governance.period')}
            value={scoreForm.period || ''}
            onChange={(e) => setScoreForm({ ...scoreForm, period: e.target.value })}
            placeholder={t('governance.periodPlaceholder')}
          />
          <div>
            <label className="lbl">{t('governance.comments')}</label>
            <div className="inp" style={{ height: 'auto', padding: '8px 10px' }}>
              <textarea
                rows={2}
                style={{ resize: 'vertical' }}
                value={scoreForm.comments || ''}
                onChange={(e) => setScoreForm({ ...scoreForm, comments: e.target.value })}
              />
            </div>
          </div>
        </div>
      </Drawer>

      {/* Add-KPI drawer */}
      <Drawer
        open={showAddKPI}
        title={t('governance.addKpi')}
        onClose={() => setShowAddKPI(false)}
        width={420}
        footer={
          <>
            <span className="grow" />
            <Button variant="ghost" onClick={() => setShowAddKPI(false)}>{t('common.cancel')}</Button>
            <Button
              variant="primary"
              disabled={!kpiForm.name || createKPIMutation.isPending}
              onClick={() => {
                if (kpiForm.name && id) {
                  createKPIMutation.mutate({ ...kpiForm, relationship_id: id } as KPICreate)
                }
              }}
            >
              {createKPIMutation.isPending ? t('governance.creating') : t('governance.createKpi')}
            </Button>
          </>
        }
      >
        <div className="col" style={{ gap: 14 }}>
          <Field
            label={`${t('governance.name')} *`}
            value={kpiForm.name || ''}
            autoFocus
            onChange={(e) => setKpiForm({ ...kpiForm, name: e.target.value })}
            placeholder={t('governance.kpiNamePlaceholder')}
          />
          <Select
            label={t('governance.category')}
            value={kpiForm.category || 'service_delivery'}
            onChange={(e) => setKpiForm({ ...kpiForm, category: e.target.value as KPICreate['category'] })}
            options={[
              { value: 'service_delivery', label: t('governance.kpiCategories.service_delivery') },
              { value: 'quality', label: t('governance.kpiCategories.quality') },
              { value: 'timeliness', label: t('governance.kpiCategories.timeliness') },
              { value: 'communication', label: t('governance.kpiCategories.communication') },
              { value: 'innovation', label: t('governance.kpiCategories.innovation') },
              { value: 'cost_efficiency', label: t('governance.kpiCategories.cost_efficiency') },
              { value: 'compliance', label: t('governance.kpiCategories.compliance') },
              { value: 'satisfaction', label: t('governance.kpiCategories.satisfaction') },
            ]}
          />
          <div>
            <label className="lbl">{t('governance.description')}</label>
            <div className="inp" style={{ height: 'auto', padding: '8px 10px' }}>
              <textarea
                rows={2}
                style={{ resize: 'vertical' }}
                value={kpiForm.description || ''}
                onChange={(e) => setKpiForm({ ...kpiForm, description: e.target.value })}
              />
            </div>
          </div>
          <div className="grid gap-3 grid-cols-2">
            <Field
              label={t('governance.targetValue')}
              type="number"
              value={kpiForm.target_value ?? ''}
              onChange={(e) => setKpiForm({ ...kpiForm, target_value: Number(e.target.value) })}
            />
            <Select
              label={t('governance.frequency')}
              value={kpiForm.frequency || 'quarterly'}
              onChange={(e) => setKpiForm({ ...kpiForm, frequency: e.target.value as KPICreate['frequency'] })}
              options={[
                { value: 'weekly', label: t('governance.frequencies.weekly') },
                { value: 'monthly', label: t('governance.frequencies.monthly') },
                { value: 'quarterly', label: t('governance.frequencies.quarterly') },
                { value: 'annual', label: t('governance.frequencies.annual') },
              ]}
            />
          </div>
        </div>
      </Drawer>

      {/* Record-status drawer */}
      <Drawer
        open={showRecordStatus}
        title={t('governance.recordPerformanceStatus')}
        onClose={() => setShowRecordStatus(false)}
        width={400}
        footer={
          <>
            <span className="grow" />
            <Button variant="ghost" onClick={() => setShowRecordStatus(false)}>{t('common.cancel')}</Button>
            <Button
              variant="primary"
              disabled={!statusForm.status || !statusForm.period || recordStatusMutation.isPending}
              onClick={() => {
                if (statusForm.status && statusForm.period) {
                  recordStatusMutation.mutate(statusForm as RelationshipHistoryCreate)
                }
              }}
            >
              {recordStatusMutation.isPending ? t('governance.recording') : t('governance.record')}
            </Button>
          </>
        }
      >
        <div className="col" style={{ gap: 14 }}>
          <Select
            label={`${t('common.status')} *`}
            value={statusForm.status || 'good'}
            onChange={(e) => setStatusForm({ ...statusForm, status: e.target.value as PerformanceStatus })}
            options={Object.entries(PERF_STATUS_LABELS).map(([value, label]) => ({
              value,
              label: t(`governance.perfStatus.${value}`, { defaultValue: label }),
            }))}
          />
          <div className="grid gap-3 grid-cols-2">
            <Field
              label={`${t('governance.period')} *`}
              value={statusForm.period || ''}
              onChange={(e) => setStatusForm({ ...statusForm, period: e.target.value })}
              placeholder={t('governance.periodPlaceholder')}
            />
            <Field
              label={t('governance.score')}
              type="number"
              min={0}
              max={100}
              value={statusForm.overall_score ?? ''}
              onChange={(e) => setStatusForm({ ...statusForm, overall_score: e.target.value ? Number(e.target.value) : undefined })}
            />
          </div>
          <Field
            label={t('governance.trigger')}
            value={statusForm.trigger || ''}
            onChange={(e) => setStatusForm({ ...statusForm, trigger: e.target.value })}
            placeholder={t('governance.triggerPlaceholder')}
          />
          <div>
            <label className="lbl">{t('governance.notes')}</label>
            <div className="inp" style={{ height: 'auto', padding: '8px 10px' }}>
              <textarea
                rows={2}
                style={{ resize: 'vertical' }}
                value={statusForm.notes || ''}
                onChange={(e) => setStatusForm({ ...statusForm, notes: e.target.value })}
              />
            </div>
          </div>
        </div>
      </Drawer>
    </div>
  )
}
