/* External governance portal — Direction B restyle. Token-gated PUBLIC page
   rendered outside MainLayout: standalone header bar (wordmark on var(--s)),
   content on var(--pg), token tables/pills/chips, score modal on .scrim/.modal,
   submit success via toast. Perception-score submission flow unchanged. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ChartBarSquareIcon,
  ExclamationTriangleIcon,
  ShieldCheckIcon,
  ClockIcon,
  XMarkIcon,
  LightBulbIcon,
  StarIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline'
import axios from 'axios'
import { formatDate } from '@/lib/utils'
import { Bar, Button, Chip, EmptyState, Field, IconButton, Pill, Tabs, Tag, useToast } from '@/components/ui'
import type { PillTone, TabDef } from '@/components/ui'
import type { GapSeverity, KPICategory, ImprovementPoint } from '@/types/governance'

const apiBase = '/api/external/governance'

// ── Types ──────────────────────────────────────────────────────────

interface ExternalUser {
  id: string
  email: string
  full_name?: string
  company_name?: string
}

interface ExternalKPI {
  id: string
  name: string
  description: string | null
  category: KPICategory
  target_value: number | null
  weight: number
  frequency: string
  latest_internal_score: number | null
  latest_external_score: number | null
  latest_gap: number | null
  latest_gap_severity: GapSeverity | null
}

interface GovernanceData {
  relationship: {
    id: string
    name: string
    org_a_name: string
    org_b_name: string
    relationship_type: string
    governance_tier: string
    health_score: number
    status: string
  }
  external_user: ExternalUser
  kpis: ExternalKPI[]
  improvements: ImprovementPoint[]
  token_expires_at?: string
}

// ── Constants (design tokens only) ─────────────────────────────────

const GAP_TONE: Record<GapSeverity, PillTone> = {
  critical: 'da',
  significant: 'wa',
  moderate: 'wa',
  minor: 'in',
  aligned: 'ok',
}

const priorityTone = (priority?: string): PillTone =>
  priority === 'critical' ? 'da' : priority === 'high' || priority === 'medium' ? 'wa' : 'n'

const statusTone = (status?: string): PillTone =>
  status === 'completed' ? 'ok' : status === 'in_progress' ? 'in' : status === 'blocked' ? 'da' : 'n'

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

function getCurrentQuarter(): string {
  const now = new Date()
  const q = Math.ceil((now.getMonth() + 1) / 3)
  return `${now.getFullYear()}-Q${q}`
}

type TabId = 'kpis' | 'improvements'

// ── Main Component ─────────────────────────────────────────────────

export default function ExternalGovernancePage() {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const accessToken = searchParams.get('token') || ''

  const [activeTab, setActiveTab] = useState<TabId>('kpis')
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [scoringKpiId, setScoringKpiId] = useState<string | null>(null)
  const [scoreValue, setScoreValue] = useState(5)
  const [scorePeriod, setScorePeriod] = useState(getCurrentQuarter())
  const [scoreComments, setScoreComments] = useState('')

  // ── Fetch governance data ────────────────────────────────────────

  const { data, isLoading, error } = useQuery({
    queryKey: ['external-governance', accessToken],
    queryFn: async () => {
      const response = await axios.get<GovernanceData>(apiBase, {
        params: { token: accessToken },
      })
      return response.data
    },
    enabled: !!accessToken,
    retry: false,
  })

  // ── Submit perception score ──────────────────────────────────────

  const submitScoreMutation = useMutation({
    mutationFn: async (payload: {
      kpi_id: string
      score: number
      period: string
      comments: string
    }) => {
      const response = await axios.post(`${apiBase}/score`, payload, {
        params: { token: accessToken },
      })
      return response.data
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['external-governance', accessToken] })
      const kpiName = data?.kpis.find((k) => k.id === variables.kpi_id)?.name || t('external.kpi')
      toast({ text: t('external.scoreSubmitted', { name: kpiName }) })
      setScoringKpiId(null)
      setScoreValue(5)
      setScorePeriod(getCurrentQuarter())
      setScoreComments('')
    },
  })

  // ── Loading / Error / No token ───────────────────────────────────

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--pg)' }}>
        <div className="col items-center" style={{ gap: 12 }}>
          <ArrowPathIcon className="spin" style={{ width: 28, height: 28, color: 'var(--f)' }} aria-hidden />
          <p className="muted">{t('external.loadingGovernance')}</p>
        </div>
      </div>
    )
  }

  if (error || !accessToken || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4" style={{ background: 'var(--pg)' }}>
        <div className="card w-full" style={{ maxWidth: 420 }}>
          <EmptyState
            icon={ExclamationTriangleIcon}
            title={t('external.accessDenied')}
            body={!accessToken ? t('external.noToken') : t('external.invalidLink')}
          />
        </div>
      </div>
    )
  }

  const { relationship, external_user, kpis, improvements } = data

  // ── Category filter helpers ──────────────────────────────────────

  const categoryCounts: Record<string, number> = {}
  kpis.forEach((k) => {
    const cat = k.category || 'other'
    categoryCounts[cat] = (categoryCounts[cat] || 0) + 1
  })
  const categories = Object.keys(categoryCounts).sort(
    (a, b) => (categoryCounts[b] || 0) - (categoryCounts[a] || 0)
  )

  const filteredKpis =
    selectedCategory === 'all'
      ? kpis
      : kpis.filter((k) => (k.category || 'other') === selectedCategory)

  // ── Gap summary counts ───────────────────────────────────────────

  const gapCounts = { critical: 0, significant: 0, moderate: 0, minor: 0, aligned: 0 }
  kpis.forEach((k) => {
    if (k.latest_gap_severity && k.latest_gap_severity in gapCounts) {
      gapCounts[k.latest_gap_severity]++
    }
  })

  const healthColor =
    relationship.health_score >= 70
      ? 'var(--ok)'
      : relationship.health_score >= 40
        ? 'var(--wa)'
        : 'var(--da)'

  // ── Scoring KPI info ─────────────────────────────────────────────

  const scoringKpi = scoringKpiId ? kpis.find((k) => k.id === scoringKpiId) : null

  const tabDefs: TabDef<TabId>[] = [
    { value: 'kpis', label: t('external.kpiScorecard'), icon: ChartBarSquareIcon, count: kpis.length || undefined },
    { value: 'improvements', label: t('external.improvements'), icon: LightBulbIcon, count: improvements.length || undefined },
  ]

  // ── Render ───────────────────────────────────────────────────────

  return (
    <div className="min-h-screen" style={{ background: 'var(--pg)' }}>
      {/* Header */}
      <header style={{ background: 'var(--s)', borderBottom: '1px solid var(--b)' }}>
        <div className="max-w-5xl mx-auto px-4">
          <div className="row" style={{ height: 56, gap: 10 }}>
            <span
              aria-hidden
              style={{
                width: 26, height: 26, borderRadius: 7, flexShrink: 0,
                background: 'var(--p)', color: 'var(--on-p)',
                display: 'grid', placeItems: 'center',
                fontSize: 14, fontWeight: 700, lineHeight: 1,
              }}
            >
              E
            </span>
            <div className="col">
              <span style={{ fontSize: 'var(--fs-lg)', fontWeight: 600, letterSpacing: '-.2px', lineHeight: 1.2 }}>Evaluetor</span>
              <span className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('external.governancePortal')}</span>
            </div>
            <span className="grow" />
            {data.token_expires_at && (
              <span className="faint hidden sm:inline-flex items-center gap-1" style={{ fontSize: 'var(--fs-xs)' }}>
                <ClockIcon style={{ width: 13, height: 13 }} aria-hidden />
                {t('external.expires', { date: formatDate(data.token_expires_at) })}
              </span>
            )}
            <span className="row" style={{ gap: 6 }}>
              <ShieldCheckIcon style={{ width: 16, height: 16, color: 'var(--ok)', flexShrink: 0 }} aria-hidden />
              <span className="muted hidden sm:inline trunc" style={{ fontSize: 'var(--fs-md)', maxWidth: 220 }}>
                {external_user.full_name || external_user.email}
              </span>
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8">
        {/* Relationship Header Card */}
        <div className="card">
          <div className="card-p">
            <div className="row" style={{ alignItems: 'flex-start', gap: 14 }}>
              <div className="grow">
                <h2 style={{ fontSize: 'var(--fs-xl)', fontWeight: 600, letterSpacing: '-.2px' }}>
                  {relationship.org_a_name} <span style={{ color: 'var(--p)' }}>&harr;</span> {relationship.org_b_name}
                </h2>
                {relationship.name && (
                  <p className="muted" style={{ fontSize: 'var(--fs-md)', marginTop: 2 }}>{relationship.name}</p>
                )}
                <div className="row" style={{ gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                  <Tag><span className="capitalize">{relationship.relationship_type.replace(/_/g, ' ')}</span></Tag>
                  <Pill tone="p" dot={false}><span className="capitalize">{relationship.governance_tier}</span></Pill>
                  <Pill tone={relationship.status === 'active' ? 'ok' : relationship.status === 'at_risk' ? 'da' : 'n'}>
                    <span className="capitalize">
                      {t(`status.${relationship.status}`, { defaultValue: relationship.status.replace(/_/g, ' ') })}
                    </span>
                  </Pill>
                </div>
              </div>
              <div className="text-right" style={{ flexShrink: 0 }}>
                <p className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('external.healthScore')}</p>
                <p className="num" style={{ fontSize: 'var(--fs-3xl)', fontWeight: 700, letterSpacing: '-1px', color: healthColor }}>
                  {relationship.health_score}
                </p>
              </div>
            </div>
          </div>
          {external_user.company_name && (
            <div style={{ padding: '0 16px 14px' }}>
              <p className="muted" style={{ fontSize: 'var(--fs-sm)' }}>
                {t('external.viewingAsRepresentative')}{' '}
                <span style={{ fontWeight: 600, color: 'var(--t)' }}>{external_user.company_name}</span>.
              </p>
            </div>
          )}
        </div>

        {/* Gap Summary Cards */}
        {kpis.some((k) => k.latest_gap_severity) && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">
            {[
              { label: t('external.severity.critical'), count: gapCounts.critical, tone: 'var(--da)' },
              { label: t('external.severity.significant'), count: gapCounts.significant, tone: 'var(--wa)' },
              { label: t('external.severity.moderate'), count: gapCounts.moderate, tone: 'var(--wa)' },
              { label: t('external.severity.minor'), count: gapCounts.minor, tone: 'var(--in)' },
              { label: t('external.severity.aligned'), count: gapCounts.aligned, tone: 'var(--ok)' },
            ].map((item) => (
              <div key={item.label} className="card card-p text-center">
                <p className="num" style={{ fontSize: 'var(--fs-2xl)', fontWeight: 700, color: item.tone }}>{item.count}</p>
                <p className="muted" style={{ fontSize: 'var(--fs-xs)', fontWeight: 600, marginTop: 2 }}>{item.label}</p>
              </div>
            ))}
          </div>
        )}

        {/* Tabs */}
        <div className="card" style={{ marginTop: 16 }}>
          <Tabs tabs={tabDefs} value={activeTab} onChange={setActiveTab} style={{ padding: '0 12px' }} />

          <div className="card-p">
            {/* KPIs Tab */}
            {activeTab === 'kpis' && (
              <div className="col" style={{ gap: 14 }}>
                {/* Category Filter */}
                {kpis.length > 0 && (
                  <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
                    <Chip on={selectedCategory === 'all'} onClick={() => setSelectedCategory('all')}>
                      {t('external.allCount', { count: kpis.length })}
                    </Chip>
                    {categories.map((cat) => (
                      <Chip key={cat} on={selectedCategory === cat} onClick={() => setSelectedCategory(cat)}>
                        {t(`external.category.${cat}`, { defaultValue: CATEGORY_LABELS[cat] || cat })} ({categoryCounts[cat]})
                      </Chip>
                    ))}
                  </div>
                )}

                {/* KPI Table */}
                <div className="tbl-w">
                  <table className="tbl">
                    <thead>
                      <tr>
                        <th>{t('external.kpi')}</th>
                        <th>{t('external.categoryHeader')}</th>
                        <th style={{ textAlign: 'center' }}>{t('external.targetHeader')}</th>
                        <th style={{ textAlign: 'center', color: 'var(--in)' }}>{t('external.internal')}</th>
                        <th style={{ textAlign: 'center', color: 'var(--p)' }}>{t('external.external')}</th>
                        <th style={{ textAlign: 'center' }}>{t('external.gap')}</th>
                        <th style={{ textAlign: 'center' }}>{t('external.severityHeader')}</th>
                        <th style={{ textAlign: 'center' }}>{t('common.actions')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredKpis.map((kpi) => {
                        const internalScore =
                          kpi.latest_internal_score != null
                            ? Number(kpi.latest_internal_score)
                            : null
                        const externalScore =
                          kpi.latest_external_score != null
                            ? Number(kpi.latest_external_score)
                            : null
                        const gapValue =
                          kpi.latest_gap != null ? Number(kpi.latest_gap) : null
                        const gapSeverity = kpi.latest_gap_severity ?? null

                        return (
                          <tr key={kpi.id}>
                            <td>
                              <p style={{ fontWeight: 500 }}>{kpi.name}</p>
                              {kpi.description && (
                                <p className="muted trunc" style={{ fontSize: 'var(--fs-xs)', maxWidth: 220 }}>
                                  {kpi.description}
                                </p>
                              )}
                            </td>
                            <td className="muted capitalize" style={{ fontSize: 'var(--fs-sm)' }}>
                              {t(`external.category.${kpi.category || 'other'}`, {
                                defaultValue: (kpi.category || 'other').replace(/_/g, ' '),
                              })}
                            </td>
                            <td className="num" style={{ textAlign: 'center' }}>
                              {kpi.target_value != null ? kpi.target_value : <span className="faint">--</span>}
                            </td>
                            <td style={{ textAlign: 'center' }}>
                              {internalScore != null
                                ? <span className="num" style={{ fontWeight: 600, color: 'var(--in)' }}>{internalScore.toFixed(1)}</span>
                                : <span className="faint">--</span>}
                            </td>
                            <td style={{ textAlign: 'center' }}>
                              {externalScore != null
                                ? <span className="num" style={{ fontWeight: 600, color: 'var(--p)' }}>{externalScore.toFixed(1)}</span>
                                : <span className="faint">--</span>}
                            </td>
                            <td style={{ textAlign: 'center' }}>
                              {gapValue != null ? (
                                <span
                                  className="num"
                                  style={{
                                    fontWeight: 700,
                                    color: gapValue > 0 ? 'var(--da)' : gapValue < 0 ? 'var(--in)' : 'var(--ok)',
                                  }}
                                >
                                  {gapValue > 0 ? '+' : ''}
                                  {gapValue.toFixed(1)}
                                </span>
                              ) : (
                                <span className="faint">--</span>
                              )}
                            </td>
                            <td style={{ textAlign: 'center' }}>
                              {gapSeverity ? (
                                <Pill tone={GAP_TONE[gapSeverity]}>
                                  {t(`external.severity.${gapSeverity}`, { defaultValue: gapSeverity })}
                                </Pill>
                              ) : (
                                <span className="faint">--</span>
                              )}
                            </td>
                            <td style={{ textAlign: 'center' }}>
                              <Button
                                variant="ghost"
                                size="sm"
                                icon={StarIcon}
                                onClick={() => {
                                  setScoringKpiId(kpi.id)
                                  setScoreValue(5)
                                  setScorePeriod(getCurrentQuarter())
                                  setScoreComments('')
                                }}
                                style={{ color: 'var(--p)' }}
                              >
                                {t('external.rate')}
                              </Button>
                            </td>
                          </tr>
                        )
                      })}
                      {filteredKpis.length === 0 && (
                        <tr>
                          <td colSpan={8} className="muted text-center" style={{ padding: '32px 16px' }}>
                            {kpis.length === 0
                              ? t('external.noKpisDefined')
                              : t('external.noKpisMatchCategory')}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Perception Gap Visualization */}
                {kpis.length > 0 &&
                  kpis.some(
                    (k) =>
                      k.latest_internal_score != null || k.latest_external_score != null
                  ) && (
                    <div className="card">
                      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--b)' }}>
                        <span className="sec-t">{t('external.perceptionGapComparison')}</span>
                      </div>
                      <div className="card-p col" style={{ gap: 10 }}>
                        {kpis
                          .filter(
                            (k) =>
                              k.latest_internal_score != null ||
                              k.latest_external_score != null
                          )
                          .map((kpi) => {
                            const intScore = Number(kpi.latest_internal_score) || 0
                            const extScore = Number(kpi.latest_external_score) || 0
                            const severity = kpi.latest_gap_severity ?? null
                            return (
                              <div key={kpi.id} className="row" style={{ gap: 10 }}>
                                <span className="muted trunc" style={{ fontSize: 'var(--fs-sm)', width: 130, flexShrink: 0 }}>
                                  {kpi.name}
                                </span>
                                <span className="row" style={{ gap: 6, flex: 1, minWidth: 0 }}>
                                  <Bar value={intScore * 10} width={90} tone="var(--in)" />
                                  <span className="mono num" style={{ fontSize: 'var(--fs-xs)', color: 'var(--in)', flexShrink: 0 }}>
                                    {t('external.intShort')} {intScore ? intScore.toFixed(1) : '--'}
                                  </span>
                                </span>
                                <span className="row" style={{ gap: 6, flex: 1, minWidth: 0 }}>
                                  <Bar value={extScore * 10} width={90} tone="var(--p)" />
                                  <span className="mono num" style={{ fontSize: 'var(--fs-xs)', color: 'var(--p)', flexShrink: 0 }}>
                                    {t('external.extShort')} {extScore ? extScore.toFixed(1) : '--'}
                                  </span>
                                </span>
                                {severity && (
                                  <Pill tone={GAP_TONE[severity]} dot={false} className="w-24 justify-center">
                                    {t(`external.severity.${severity}`, { defaultValue: severity })}
                                  </Pill>
                                )}
                              </div>
                            )
                          })}
                      </div>
                    </div>
                  )}
              </div>
            )}

            {/* Improvements Tab */}
            {activeTab === 'improvements' && (
              <div className="col" style={{ gap: 14 }}>
                <div className="row" style={{ gap: 8 }}>
                  <LightBulbIcon style={{ width: 18, height: 18, color: 'var(--f)' }} aria-hidden />
                  <h2 className="sec-t">
                    {t('external.improvementPoints', { count: improvements.length })}
                  </h2>
                </div>

                {improvements.length > 0 ? (
                  <div className="col" style={{ gap: 10 }}>
                    {improvements.map((imp) => {
                      const pct = imp.progress_percentage ?? imp.progress ?? 0
                      return (
                        <div key={imp.id} className="card card-p">
                          <div className="row" style={{ alignItems: 'flex-start', gap: 12 }}>
                            <div className="grow">
                              <p style={{ fontWeight: 600, fontSize: 'var(--fs-md)' }}>{imp.title}</p>
                              {imp.description && (
                                <p className="muted" style={{ fontSize: 'var(--fs-sm)', marginTop: 4 }}>{imp.description}</p>
                              )}
                              {imp.target_outcome && (
                                <p className="faint" style={{ fontSize: 'var(--fs-sm)', marginTop: 4, fontStyle: 'italic' }}>
                                  {t('external.target', { value: imp.target_outcome })}
                                </p>
                              )}
                            </div>
                            <div className="row" style={{ gap: 6, flexShrink: 0 }}>
                              <Pill tone={priorityTone(imp.priority)}>
                                {t(`risk.${imp.priority}`, { defaultValue: imp.priority })}
                              </Pill>
                              <Pill tone={statusTone(imp.status)}>
                                <span className="capitalize">
                                  {t(`external.status.${imp.status}`, { defaultValue: imp.status.replace(/_/g, ' ') })}
                                </span>
                              </Pill>
                            </div>
                          </div>
                          {/* Progress bar */}
                          <div className="row" style={{ gap: 8, marginTop: 10 }}>
                            <span className="grow" style={{ display: 'flex' }}>
                              <Bar value={pct} width="100%" />
                            </span>
                            <span className="faint num" style={{ fontSize: 'var(--fs-2xs)', flexShrink: 0 }}>
                              {pct}%
                              {imp.action_count
                                ? ` ${t('external.actionsProgress', { completed: imp.completed_action_count ?? 0, total: imp.action_count })}`
                                : ''}
                            </span>
                          </div>
                          <div className="row" style={{ gap: 12, marginTop: 8, flexWrap: 'wrap' }}>
                            {imp.owner_name && <span className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('external.owner', { name: imp.owner_name })}</span>}
                            {imp.kpi_name && <span className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('external.kpiLabel', { name: imp.kpi_name })}</span>}
                            {(imp.target_date || imp.due_date) && (
                              <span className="faint" style={{ fontSize: 'var(--fs-xs)' }}>
                                {t('external.due', { date: formatDate(imp.target_date || imp.due_date || null) })}
                              </span>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <EmptyState icon={LightBulbIcon} title={t('external.noImprovementPoints')} />
                )}
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer style={{ borderTop: '1px solid var(--b)', background: 'var(--s)', marginTop: 48 }}>
        <div className="max-w-5xl mx-auto px-4 py-6 text-center faint" style={{ fontSize: 'var(--fs-sm)' }}>
          {t('external.poweredBy')}
        </div>
      </footer>

      {/* Score Modal */}
      {scoringKpiId && scoringKpi && (
        <div className="scrim">
          <div className="modal" style={{ maxWidth: 440 }}>
            <div className="modal-h">
              <div className="grow">
                <h2 style={{ fontSize: 'var(--fs-xl)', fontWeight: 600, letterSpacing: '-.2px' }}>{t('external.rateKpi')}</h2>
                <p className="muted" style={{ fontSize: 'var(--fs-md)', marginTop: 2 }}>{scoringKpi.name}</p>
              </div>
              <IconButton icon={XMarkIcon} label={t('common.cancel')} onClick={() => setScoringKpiId(null)} />
            </div>

            <div className="modal-b col" style={{ gap: 16, paddingTop: 14 }}>
              {/* Period */}
              <Field
                label={t('external.period')}
                type="text"
                value={scorePeriod}
                onChange={(e) => setScorePeriod(e.target.value)}
                placeholder={t('external.periodPlaceholder')}
              />

              {/* Score Slider */}
              <div>
                <label className="lbl">
                  {t('external.yourScore')}{' '}
                  <span className="num" style={{ color: 'var(--p)', fontWeight: 700, fontSize: 'var(--fs-lg)' }}>{scoreValue}/10</span>
                </label>
                <input
                  type="range"
                  min={1}
                  max={10}
                  step={1}
                  value={scoreValue}
                  onChange={(e) => setScoreValue(Number(e.target.value))}
                  className="w-full"
                  style={{ accentColor: 'var(--p)', height: 8 }}
                />
                <div className="row faint" style={{ justifyContent: 'space-between', marginTop: 4, fontSize: 'var(--fs-xs)' }}>
                  <span>{t('external.scorePoor')}</span>
                  <span>{t('external.scoreAverage')}</span>
                  <span>{t('external.scoreExcellent')}</span>
                </div>
                {/* Visual dots */}
                <div className="row" style={{ justifyContent: 'space-between', marginTop: 8 }}>
                  {Array.from({ length: 10 }, (_, i) => i + 1).map((v) => (
                    <button
                      key={v}
                      type="button"
                      onClick={() => setScoreValue(v)}
                      aria-pressed={v === scoreValue}
                      className="num"
                      style={{
                        width: 26, height: 26, borderRadius: '50%', border: 0, cursor: 'pointer',
                        fontSize: 'var(--fs-xs)', fontWeight: 600,
                        background: v === scoreValue ? 'var(--p)' : v <= scoreValue ? 'var(--p-f2)' : 'var(--s2)',
                        color: v === scoreValue ? 'var(--on-p)' : v <= scoreValue ? 'var(--p)' : 'var(--m)',
                        boxShadow: v === scoreValue ? 'var(--sh-sm)' : undefined,
                        transform: v === scoreValue ? 'scale(1.1)' : undefined,
                        transition: 'all .12s var(--ease)',
                      }}
                    >
                      {v}
                    </button>
                  ))}
                </div>
              </div>

              {/* Comments */}
              <div>
                <label className="lbl">
                  {t('external.comments')} <span className="faint" style={{ fontWeight: 400 }}>{t('external.optional')}</span>
                </label>
                <textarea
                  value={scoreComments}
                  onChange={(e) => setScoreComments(e.target.value)}
                  rows={3}
                  placeholder={t('external.scoreCommentsPlaceholder')}
                  className="input resize-none"
                />
              </div>

              {/* Error */}
              {submitScoreMutation.isError && (
                <div className="banner banner-da">{t('external.submitScoreFailed')}</div>
              )}
            </div>

            <div className="modal-f">
              <Button variant="secondary" onClick={() => setScoringKpiId(null)}>
                {t('common.cancel')}
              </Button>
              <Button
                variant="primary"
                onClick={() => {
                  submitScoreMutation.mutate({
                    kpi_id: scoringKpiId,
                    score: scoreValue,
                    period: scorePeriod,
                    comments: scoreComments,
                  })
                }}
                disabled={submitScoreMutation.isPending || !scorePeriod.trim()}
              >
                {submitScoreMutation.isPending ? (
                  <ArrowPathIcon className="spin" style={{ width: 15, height: 15, flexShrink: 0 }} aria-hidden />
                ) : (
                  <StarIcon style={{ width: 15, height: 15, flexShrink: 0 }} aria-hidden />
                )}
                {submitScoreMutation.isPending ? t('external.submitting') : t('external.submitScore')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
