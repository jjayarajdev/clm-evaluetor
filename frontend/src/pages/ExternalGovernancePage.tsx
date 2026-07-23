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
} from '@heroicons/react/24/outline'
import axios from 'axios'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn, formatDate } from '@/lib/utils'
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

// ── Constants ──────────────────────────────────────────────────────

const GAP_COLORS: Record<GapSeverity, string> = {
  critical: 'bg-red-100 text-red-800 border-red-200',
  significant: 'bg-orange-100 text-orange-800 border-orange-200',
  moderate: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  minor: 'bg-blue-100 text-blue-800 border-blue-200',
  aligned: 'bg-green-100 text-green-800 border-green-200',
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
  const accessToken = searchParams.get('token') || ''

  const [activeTab, setActiveTab] = useState<TabId>('kpis')
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [scoringKpiId, setScoringKpiId] = useState<string | null>(null)
  const [scoreValue, setScoreValue] = useState(5)
  const [scorePeriod, setScorePeriod] = useState(getCurrentQuarter())
  const [scoreComments, setScoreComments] = useState('')
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null)

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
      setSubmitSuccess(t('external.scoreSubmitted', { name: kpiName }))
      setScoringKpiId(null)
      setScoreValue(5)
      setScorePeriod(getCurrentQuarter())
      setScoreComments('')
      setTimeout(() => setSubmitSuccess(null), 4000)
    },
  })

  // ── Loading / Error / No token ───────────────────────────────────

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <LoadingSpinner size="lg" />
          <p className="mt-4 text-gray-600">{t('external.loadingGovernance')}</p>
        </div>
      </div>
    )
  }

  if (error || !accessToken || !data) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <ExclamationTriangleIcon className="w-8 h-8 text-red-600" />
          </div>
          <h1 className="text-xl font-bold text-gray-900 mb-2">{t('external.accessDenied')}</h1>
          <p className="text-gray-600">
            {!accessToken ? t('external.noToken') : t('external.invalidLink')}
          </p>
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
      ? 'text-green-600'
      : relationship.health_score >= 40
        ? 'text-amber-600'
        : 'text-red-600'

  // ── Scoring KPI info ─────────────────────────────────────────────

  const scoringKpi = scoringKpiId ? kpis.find((k) => k.id === scoringKpiId) : null

  // ── Render ───────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center">
                <span className="text-white font-bold text-lg">E</span>
              </div>
              <div>
                <h1 className="font-semibold text-gray-900">Evaluetor</h1>
                <p className="text-xs text-gray-500">{t('external.governancePortal')}</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              {data.token_expires_at && (
                <div className="hidden sm:flex items-center gap-1 text-xs text-gray-400">
                  <ClockIcon className="w-3.5 h-3.5" />
                  <span>{t('external.expires', { date: formatDate(data.token_expires_at) })}</span>
                </div>
              )}
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <ShieldCheckIcon className="w-4 h-4 text-green-600" />
                <span className="hidden sm:inline">
                  {external_user.full_name || external_user.email}
                </span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8">
        {/* Success Banner */}
        {submitSuccess && (
          <div className="mb-6 bg-green-50 border border-green-200 rounded-lg px-4 py-3 flex items-center gap-3">
            <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center shrink-0">
              <StarIcon className="w-4 h-4 text-green-600" />
            </div>
            <p className="text-sm text-green-800 font-medium">{submitSuccess}</p>
          </div>
        )}

        {/* Relationship Header Card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="p-6">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-xl font-semibold text-gray-900">
                  {relationship.org_a_name} ↔ {relationship.org_b_name}
                </h2>
                {relationship.name && (
                  <p className="text-sm text-gray-500 mt-1">{relationship.name}</p>
                )}
                <div className="flex flex-wrap items-center gap-3 mt-3">
                  <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded capitalize">
                    {relationship.relationship_type.replace(/_/g, ' ')}
                  </span>
                  <span className="text-xs bg-primary-50 text-primary-700 px-2 py-1 rounded capitalize">
                    {relationship.governance_tier}
                  </span>
                  <span
                    className={cn(
                      'text-xs px-2 py-1 rounded capitalize',
                      relationship.status === 'active'
                        ? 'bg-green-50 text-green-700'
                        : relationship.status === 'at_risk'
                          ? 'bg-red-50 text-red-700'
                          : 'bg-gray-100 text-gray-600'
                    )}
                  >
                    {t(`status.${relationship.status}`, { defaultValue: relationship.status.replace(/_/g, ' ') })}
                  </span>
                </div>
              </div>
              <div className="text-right shrink-0">
                <p className="text-xs text-gray-500">{t('external.healthScore')}</p>
                <p className={cn('text-3xl font-bold', healthColor)}>
                  {relationship.health_score}
                </p>
              </div>
            </div>
          </div>
          {external_user.company_name && (
            <div className="px-6 pb-4">
              <p className="text-sm text-gray-500">
                {t('external.viewingAsRepresentative')}{' '}
                <span className="font-medium text-gray-700">{external_user.company_name}</span>.
              </p>
            </div>
          )}
        </div>

        {/* Gap Summary Cards */}
        {kpis.some((k) => k.latest_gap_severity) && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-6">
            {[
              { label: t('external.severity.critical'), count: gapCounts.critical, color: 'text-red-600 bg-red-50' },
              {
                label: t('external.severity.significant'),
                count: gapCounts.significant,
                color: 'text-orange-600 bg-orange-50',
              },
              {
                label: t('external.severity.moderate'),
                count: gapCounts.moderate,
                color: 'text-yellow-600 bg-yellow-50',
              },
              { label: t('external.severity.minor'), count: gapCounts.minor, color: 'text-blue-600 bg-blue-50' },
              { label: t('external.severity.aligned'), count: gapCounts.aligned, color: 'text-green-600 bg-green-50' },
            ].map((item) => (
              <div key={item.label} className={cn('rounded-lg p-3 text-center', item.color)}>
                <p className="text-2xl font-bold">{item.count}</p>
                <p className="text-xs font-medium">{item.label}</p>
              </div>
            ))}
          </div>
        )}

        {/* Tabs */}
        <div className="mt-6 bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="border-b border-gray-200 flex">
            <button
              onClick={() => setActiveTab('kpis')}
              className={cn(
                'flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
                activeTab === 'kpis'
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              )}
            >
              <ChartBarSquareIcon className="w-4 h-4" />
              {t('external.kpiScorecard')}
              {kpis.length > 0 && (
                <span
                  className={cn(
                    'text-xs px-1.5 py-0.5 rounded-full',
                    activeTab === 'kpis'
                      ? 'bg-primary-100 text-primary-700'
                      : 'bg-gray-100 text-gray-600'
                  )}
                >
                  {kpis.length}
                </span>
              )}
            </button>
            <button
              onClick={() => setActiveTab('improvements')}
              className={cn(
                'flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
                activeTab === 'improvements'
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              )}
            >
              <LightBulbIcon className="w-4 h-4" />
              {t('external.improvements')}
              {improvements.length > 0 && (
                <span
                  className={cn(
                    'text-xs px-1.5 py-0.5 rounded-full',
                    activeTab === 'improvements'
                      ? 'bg-primary-100 text-primary-700'
                      : 'bg-gray-100 text-gray-600'
                  )}
                >
                  {improvements.length}
                </span>
              )}
            </button>
          </div>

          <div className="p-6">
            {/* KPIs Tab */}
            {activeTab === 'kpis' && (
              <div className="space-y-4">
                {/* Category Filter */}
                {kpis.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => setSelectedCategory('all')}
                      className={cn(
                        'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                        selectedCategory === 'all'
                          ? 'bg-primary-600 text-white'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      )}
                    >
                      {t('external.allCount', { count: kpis.length })}
                    </button>
                    {categories.map((cat) => (
                      <button
                        key={cat}
                        onClick={() => setSelectedCategory(cat)}
                        className={cn(
                          'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                          selectedCategory === cat
                            ? 'bg-primary-600 text-white'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                        )}
                      >
                        {t(`external.category.${cat}`, { defaultValue: CATEGORY_LABELS[cat] || cat })} ({categoryCounts[cat]})
                      </button>
                    ))}
                  </div>
                )}

                {/* KPI Table */}
                <div className="overflow-x-auto rounded-lg border border-gray-200">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          {t('external.kpi')}
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          {t('external.categoryHeader')}
                        </th>
                        <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                          {t('external.targetHeader')}
                        </th>
                        <th className="px-4 py-3 text-center text-xs font-medium text-blue-600 uppercase bg-blue-50">
                          {t('external.internal')}
                        </th>
                        <th className="px-4 py-3 text-center text-xs font-medium text-purple-600 uppercase bg-purple-50">
                          {t('external.external')}
                        </th>
                        <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                          {t('external.gap')}
                        </th>
                        <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                          {t('external.severityHeader')}
                        </th>
                        <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                          {t('common.actions')}
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 bg-white">
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
                          <tr key={kpi.id} className="hover:bg-gray-50">
                            <td className="px-4 py-3">
                              <p className="text-sm font-medium text-gray-900">{kpi.name}</p>
                              {kpi.description && (
                                <p className="text-xs text-gray-500 truncate max-w-[220px]">
                                  {kpi.description}
                                </p>
                              )}
                            </td>
                            <td className="px-4 py-3 text-xs text-gray-500 capitalize">
                              {t(`external.category.${kpi.category || 'other'}`, {
                                defaultValue: (kpi.category || 'other').replace(/_/g, ' '),
                              })}
                            </td>
                            <td className="px-4 py-3 text-center text-sm text-gray-700">
                              {kpi.target_value != null ? kpi.target_value : '--'}
                            </td>
                            <td className="px-4 py-3 text-center bg-blue-50/30">
                              <span className="text-sm font-semibold text-blue-700">
                                {internalScore != null ? internalScore.toFixed(1) : '--'}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-center bg-purple-50/30">
                              <span className="text-sm font-semibold text-purple-700">
                                {externalScore != null ? externalScore.toFixed(1) : '--'}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-center">
                              {gapValue != null ? (
                                <span
                                  className={cn(
                                    'text-sm font-bold',
                                    gapValue > 0
                                      ? 'text-red-600'
                                      : gapValue < 0
                                        ? 'text-blue-600'
                                        : 'text-green-600'
                                  )}
                                >
                                  {gapValue > 0 ? '+' : ''}
                                  {gapValue.toFixed(1)}
                                </span>
                              ) : (
                                '--'
                              )}
                            </td>
                            <td className="px-4 py-3 text-center">
                              {gapSeverity ? (
                                <span
                                  className={cn(
                                    'px-2 py-0.5 rounded text-xs font-medium border',
                                    GAP_COLORS[gapSeverity]
                                  )}
                                >
                                  {t(`external.severity.${gapSeverity}`, { defaultValue: gapSeverity })}
                                </span>
                              ) : (
                                '--'
                              )}
                            </td>
                            <td className="px-4 py-3 text-center">
                              <button
                                onClick={() => {
                                  setScoringKpiId(kpi.id)
                                  setScoreValue(5)
                                  setScorePeriod(getCurrentQuarter())
                                  setScoreComments('')
                                }}
                                className="inline-flex items-center gap-1 text-xs text-primary-600 hover:text-primary-800 font-medium px-2.5 py-1 rounded-md hover:bg-primary-50 transition-colors"
                              >
                                <StarIcon className="w-3.5 h-3.5" />
                                {t('external.rate')}
                              </button>
                            </td>
                          </tr>
                        )
                      })}
                      {filteredKpis.length === 0 && (
                        <tr>
                          <td
                            colSpan={8}
                            className="px-4 py-8 text-center text-sm text-gray-500"
                          >
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
                    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                      <div className="px-4 py-3 border-b border-gray-200">
                        <h3 className="text-sm font-medium text-gray-900">
                          {t('external.perceptionGapComparison')}
                        </h3>
                      </div>
                      <div className="p-4 space-y-3">
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
                              <div key={kpi.id} className="flex items-center gap-3">
                                <span className="text-xs text-gray-600 w-32 truncate">
                                  {kpi.name}
                                </span>
                                <div className="flex-1 flex items-center gap-1">
                                  <div className="flex-1 bg-gray-100 rounded-full h-4 relative">
                                    <div
                                      className="bg-blue-500 h-4 rounded-full"
                                      style={{ width: `${(intScore / 10) * 100}%` }}
                                    />
                                    <span className="absolute right-2 top-0 text-[10px] font-bold text-blue-800 leading-4">
                                      {t('external.intShort')} {intScore ? intScore.toFixed(1) : '--'}
                                    </span>
                                  </div>
                                  <div className="flex-1 bg-gray-100 rounded-full h-4 relative">
                                    <div
                                      className="bg-purple-500 h-4 rounded-full"
                                      style={{ width: `${(extScore / 10) * 100}%` }}
                                    />
                                    <span className="absolute right-2 top-0 text-[10px] font-bold text-purple-800 leading-4">
                                      {t('external.extShort')} {extScore ? extScore.toFixed(1) : '--'}
                                    </span>
                                  </div>
                                </div>
                                {severity && (
                                  <span
                                    className={cn(
                                      'px-1.5 py-0.5 rounded text-[10px] font-medium border w-20 text-center',
                                      GAP_COLORS[severity]
                                    )}
                                  >
                                    {t(`external.severity.${severity}`, { defaultValue: severity })}
                                  </span>
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
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <LightBulbIcon className="h-5 w-5 text-gray-400" />
                  <h2 className="text-sm font-semibold text-gray-700">
                    {t('external.improvementPoints', { count: improvements.length })}
                  </h2>
                </div>

                {improvements.length > 0 ? (
                  <div className="divide-y divide-gray-200 border border-gray-200 rounded-lg overflow-hidden">
                    {improvements.map((imp) => {
                      const pct = imp.progress_percentage ?? imp.progress ?? 0
                      return (
                        <div key={imp.id} className="px-4 py-4 bg-white">
                          <div className="flex items-start justify-between">
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-gray-900">{imp.title}</p>
                              {imp.description && (
                                <p className="text-xs text-gray-500 mt-1">{imp.description}</p>
                              )}
                              {imp.target_outcome && (
                                <p className="text-xs text-gray-400 mt-1 italic">
                                  {t('external.target', { value: imp.target_outcome })}
                                </p>
                              )}
                            </div>
                            <div className="flex items-center gap-2 shrink-0 ml-4">
                              <span
                                className={cn(
                                  'px-2 py-0.5 rounded text-xs font-medium',
                                  imp.priority === 'critical'
                                    ? 'bg-red-100 text-red-800'
                                    : imp.priority === 'high'
                                      ? 'bg-orange-100 text-orange-800'
                                      : imp.priority === 'medium'
                                        ? 'bg-yellow-100 text-yellow-800'
                                        : 'bg-gray-100 text-gray-800'
                                )}
                              >
                                {t(`risk.${imp.priority}`, { defaultValue: imp.priority })}
                              </span>
                              <span
                                className={cn(
                                  'px-2 py-0.5 rounded text-xs font-medium',
                                  imp.status === 'completed'
                                    ? 'bg-green-100 text-green-800'
                                    : imp.status === 'in_progress'
                                      ? 'bg-blue-100 text-blue-800'
                                      : imp.status === 'blocked'
                                        ? 'bg-red-100 text-red-800'
                                        : 'bg-gray-100 text-gray-800'
                                )}
                              >
                                {t(`external.status.${imp.status}`, { defaultValue: imp.status.replace(/_/g, ' ') })}
                              </span>
                            </div>
                          </div>
                          {/* Progress bar */}
                          <div className="mt-3 flex items-center gap-2">
                            <div className="flex-1 bg-gray-100 rounded-full h-1.5">
                              <div
                                className="bg-primary-500 h-1.5 rounded-full transition-all"
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                            <span className="text-[10px] text-gray-500 shrink-0">
                              {pct}%
                              {imp.action_count
                                ? ` ${t('external.actionsProgress', { completed: imp.completed_action_count ?? 0, total: imp.action_count })}`
                                : ''}
                            </span>
                          </div>
                          <div className="flex flex-wrap gap-3 mt-2 text-xs text-gray-400">
                            {imp.owner_name && <span>{t('external.owner', { name: imp.owner_name })}</span>}
                            {imp.kpi_name && <span>{t('external.kpiLabel', { name: imp.kpi_name })}</span>}
                            {(imp.target_date || imp.due_date) && (
                              <span>
                                {t('external.due', { date: formatDate(imp.target_date || imp.due_date || null) })}
                              </span>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div className="text-center py-12 text-gray-500 text-sm">
                    {t('external.noImprovementPoints')}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white mt-12">
        <div className="max-w-5xl mx-auto px-4 py-6 text-center text-sm text-gray-500">
          {t('external.poweredBy')}
        </div>
      </footer>

      {/* Score Modal */}
      {scoringKpiId && scoringKpi && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 animate-in fade-in">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">{t('external.rateKpi')}</h2>
                <p className="text-sm text-gray-500 mt-0.5">{scoringKpi.name}</p>
              </div>
              <button
                onClick={() => setScoringKpiId(null)}
                className="text-gray-400 hover:text-gray-600 p-1 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-5">
              {/* Period */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('external.period')}</label>
                <input
                  type="text"
                  value={scorePeriod}
                  onChange={(e) => setScorePeriod(e.target.value)}
                  placeholder={t('external.periodPlaceholder')}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                />
              </div>

              {/* Score Slider */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('external.yourScore')}{' '}
                  <span className="text-primary-600 font-bold text-lg">{scoreValue}/10</span>
                </label>
                <input
                  type="range"
                  min={1}
                  max={10}
                  step={1}
                  value={scoreValue}
                  onChange={(e) => setScoreValue(Number(e.target.value))}
                  className="w-full accent-primary-600 h-2"
                />
                <div className="flex justify-between text-xs text-gray-400 mt-1">
                  <span>{t('external.scorePoor')}</span>
                  <span>{t('external.scoreAverage')}</span>
                  <span>{t('external.scoreExcellent')}</span>
                </div>
                {/* Visual dots */}
                <div className="flex justify-between mt-2 px-0.5">
                  {Array.from({ length: 10 }, (_, i) => i + 1).map((v) => (
                    <button
                      key={v}
                      onClick={() => setScoreValue(v)}
                      className={cn(
                        'w-7 h-7 rounded-full text-xs font-medium transition-all',
                        v === scoreValue
                          ? 'bg-primary-600 text-white shadow-md scale-110'
                          : v <= scoreValue
                            ? 'bg-primary-100 text-primary-700 hover:bg-primary-200'
                            : 'bg-gray-100 text-gray-400 hover:bg-gray-200'
                      )}
                    >
                      {v}
                    </button>
                  ))}
                </div>
              </div>

              {/* Comments */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('external.comments')} <span className="text-gray-400 font-normal">{t('external.optional')}</span>
                </label>
                <textarea
                  value={scoreComments}
                  onChange={(e) => setScoreComments(e.target.value)}
                  rows={3}
                  placeholder={t('external.scoreCommentsPlaceholder')}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                />
              </div>
            </div>

            {/* Error */}
            {submitScoreMutation.isError && (
              <div className="mt-3 text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
                {t('external.submitScoreFailed')}
              </div>
            )}

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setScoringKpiId(null)}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={() => {
                  submitScoreMutation.mutate({
                    kpi_id: scoringKpiId,
                    score: scoreValue,
                    period: scorePeriod,
                    comments: scoreComments,
                  })
                }}
                disabled={submitScoreMutation.isPending || !scorePeriod.trim()}
                className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors flex items-center gap-2"
              >
                {submitScoreMutation.isPending ? (
                  <>
                    <LoadingSpinner size="sm" />
                    {t('external.submitting')}
                  </>
                ) : (
                  <>
                    <StarIcon className="w-4 h-4" />
                    {t('external.submitScore')}
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
