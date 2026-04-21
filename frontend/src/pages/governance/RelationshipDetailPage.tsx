import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  HeartIcon,
  ChartBarSquareIcon,
  UserGroupIcon,
  LightBulbIcon,
  PlusIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'
import type {
  KPICreate,
  PerceptionScoreCreate,
  GapSeverity,
  ImprovementPoint,
} from '@/types/governance'
import type {
  PerformanceStatus,
  RelationshipHistoryCreate,
} from '@/types/fitgap'

const GAP_COLORS: Record<GapSeverity, string> = {
  critical: 'bg-red-100 text-red-800 border-red-200',
  significant: 'bg-orange-100 text-orange-800 border-orange-200',
  moderate: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  minor: 'bg-blue-100 text-blue-800 border-blue-200',
  aligned: 'bg-green-100 text-green-800 border-green-200',
}

const TABS = ['KPIs', 'Team', 'Improvements', 'History', 'Overview'] as const

const PERF_STATUS_COLORS: Record<PerformanceStatus, string> = {
  excellent: 'bg-green-100 text-green-800',
  good: 'bg-emerald-100 text-emerald-800',
  acceptable: 'bg-blue-100 text-blue-800',
  concerning: 'bg-yellow-100 text-yellow-800',
  poor: 'bg-orange-100 text-orange-800',
  critical: 'bg-red-100 text-red-800',
}

const PERF_STATUS_LABELS: Record<PerformanceStatus, string> = {
  excellent: 'Excellent',
  good: 'Good',
  acceptable: 'Acceptable',
  concerning: 'Concerning',
  poor: 'Poor',
  critical: 'Critical',
}
type Tab = typeof TABS[number]

export default function RelationshipDetailPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
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
    },
  })

  const generateImprovementsMutation = useMutation({
    mutationFn: () => api.generateImprovementsFromGaps(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['improvements', id] })
    },
  })

  // Performance History
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
    },
  })

  if (isLoading || !relationship) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const healthColor = relationship.health_score >= 70 ? 'text-green-600' :
    relationship.health_score >= 40 ? 'text-amber-600' : 'text-red-600'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Link to="/relationships" className="p-2 -ml-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg">
          <ArrowLeftIcon className="h-5 w-5" />
        </Link>
        <div className="flex-1">
          <h1 className="text-xl font-bold text-gray-900">
            {relationship.org_a?.name || 'Org A'} ↔ {relationship.org_b?.name || 'Org B'}
          </h1>
          <div className="flex items-center gap-4 mt-2">
            <span className="text-sm text-gray-500 capitalize">{relationship.relationship_type}</span>
            <span className="text-sm text-gray-500 capitalize">{relationship.governance_tier}</span>
            <div className={cn('flex items-center gap-1', healthColor)}>
              <HeartIcon className="h-4 w-4" />
              <span className="text-sm font-semibold">Health: {relationship.health_score}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-6">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                'pb-3 text-sm font-medium border-b-2 transition-colors',
                activeTab === tab
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              )}
            >
              {tab}
              {tab === 'KPIs' && kpis.length > 0 && (
                <span className="ml-1.5 bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded text-xs">{kpis.length}</span>
              )}
              {tab === 'Improvements' && improvements.length > 0 && (
                <span className="ml-1.5 bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded text-xs">{improvements.length}</span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* KPIs Tab — The Perception Scorecard */}
      {activeTab === 'KPIs' && (
        <div className="space-y-4">
          {/* Gap Summary Cards */}
          {gapSummary && (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {[
                { label: 'Critical', count: gapSummary.critical_gaps, color: 'text-red-600 bg-red-50' },
                { label: 'Significant', count: gapSummary.significant_gaps, color: 'text-orange-600 bg-orange-50' },
                { label: 'Moderate', count: gapSummary.moderate_gaps, color: 'text-yellow-600 bg-yellow-50' },
                { label: 'Minor', count: gapSummary.minor_gaps, color: 'text-blue-600 bg-blue-50' },
                { label: 'Aligned', count: gapSummary.aligned, color: 'text-green-600 bg-green-50' },
              ].map((item) => (
                <div key={item.label} className={cn('rounded-lg p-3 text-center', item.color)}>
                  <p className="text-2xl font-bold">{item.count}</p>
                  <p className="text-xs font-medium">{item.label}</p>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <ChartBarSquareIcon className="h-5 w-5 text-gray-400" />
              KPI Perception Scorecard
            </h2>
            <div className="flex items-center gap-2">
              {gapSummary && gapSummary.critical_gaps + gapSummary.significant_gaps > 0 && (
                <button
                  onClick={() => generateImprovementsMutation.mutate()}
                  disabled={generateImprovementsMutation.isPending}
                  className="btn-secondary text-xs"
                >
                  {generateImprovementsMutation.isPending ? 'Generating...' : 'Generate Improvements from Gaps'}
                </button>
              )}
              <button onClick={() => setShowAddKPI(true)} className="btn-primary text-xs flex items-center gap-1">
                <PlusIcon className="h-3.5 w-3.5" /> Add KPI
              </button>
            </div>
          </div>

          {/* Category Tabs */}
          {kpis.length > 0 && (() => {
            const categoryCounts: Record<string, number> = {}
            kpis.forEach((k) => {
              const cat = k.category || 'other'
              categoryCounts[cat] = (categoryCounts[cat] || 0) + 1
            })
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
            const categories = Object.keys(categoryCounts).sort((a, b) =>
              (categoryCounts[b] || 0) - (categoryCounts[a] || 0)
            )
            return (
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
                  All ({kpis.length})
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
                    {CATEGORY_LABELS[cat] || cat} ({categoryCounts[cat]})
                  </button>
                ))}
              </div>
            )
          })()}

          {/* KPI Table with Perception Scores */}
          <div className="card">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">KPI</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-blue-600 uppercase bg-blue-50">Internal</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-purple-600 uppercase bg-purple-50">External</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Gap</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Severity</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {kpis.filter((kpi) => selectedCategory === 'all' || (kpi.category || 'other') === selectedCategory).map((kpi) => {
                    const internalScore = kpi.latest_internal_score != null ? Number(kpi.latest_internal_score) : null
                    const externalScore = kpi.latest_external_score != null ? Number(kpi.latest_external_score) : null
                    const gapValue = kpi.latest_gap != null ? Number(kpi.latest_gap) : null
                    const gapSeverity = kpi.latest_gap_severity ?? null
                    return (
                      <tr key={kpi.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3">
                          <p className="text-sm font-medium text-gray-900">{kpi.name}</p>
                          {kpi.description && (
                            <p className="text-xs text-gray-500 truncate max-w-[200px]">{kpi.description}</p>
                          )}
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-500 capitalize">{kpi.category.replace(/_/g, ' ')}</td>
                        <td className="px-4 py-3 text-center bg-blue-50/30">
                          <span className="text-sm font-semibold text-blue-700">
                            {internalScore != null ? internalScore.toFixed(1) : '—'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center bg-purple-50/30">
                          <span className="text-sm font-semibold text-purple-700">
                            {externalScore != null ? externalScore.toFixed(1) : '—'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          {gapValue != null ? (
                            <span className={cn(
                              'text-sm font-bold',
                              gapValue > 0 ? 'text-red-600' : gapValue < 0 ? 'text-blue-600' : 'text-green-600'
                            )}>
                              {gapValue > 0 ? '+' : ''}{gapValue.toFixed(1)}
                            </span>
                          ) : '—'}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {gapSeverity ? (
                            <span className={cn(
                              'px-2 py-0.5 rounded text-xs font-medium border',
                              GAP_COLORS[gapSeverity]
                            )}>
                              {gapSeverity}
                            </span>
                          ) : '—'}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <button
                            onClick={() => setShowScore(kpi.id)}
                            className="text-xs text-primary-600 hover:text-primary-800 font-medium"
                          >
                            Score
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                  {kpis.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-sm text-gray-500">
                        No KPIs defined yet. Add your first KPI to start tracking perception.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Perception Gap Visualization */}
          {kpis.length > 0 && kpis.some(k => k.latest_internal_score != null || k.latest_external_score != null) && (
            <div className="card">
              <div className="card-header">
                <h3 className="text-sm font-medium text-gray-900">Perception Gap Comparison</h3>
              </div>
              <div className="card-body space-y-3">
                {kpis.filter(k => k.latest_internal_score != null || k.latest_external_score != null).map((kpi) => {
                  const intScore = Number(kpi.latest_internal_score) || 0
                  const extScore = Number(kpi.latest_external_score) || 0
                  const severity = kpi.latest_gap_severity ?? null
                  return (
                  <div key={kpi.id} className="flex items-center gap-3">
                    <span className="text-xs text-gray-600 w-32 truncate">{kpi.name}</span>
                    <div className="flex-1 flex items-center gap-1">
                      {/* Internal bar */}
                      <div className="flex-1 bg-gray-100 rounded-full h-4 relative">
                        <div
                          className="bg-blue-500 h-4 rounded-full"
                          style={{ width: `${(intScore / 10) * 100}%` }}
                        />
                        <span className="absolute right-2 top-0 text-[10px] font-bold text-blue-800 leading-4">
                          INT {intScore ? intScore.toFixed(1) : '—'}
                        </span>
                      </div>
                      {/* External bar */}
                      <div className="flex-1 bg-gray-100 rounded-full h-4 relative">
                        <div
                          className="bg-purple-500 h-4 rounded-full"
                          style={{ width: `${(extScore / 10) * 100}%` }}
                        />
                        <span className="absolute right-2 top-0 text-[10px] font-bold text-purple-800 leading-4">
                          EXT {extScore ? extScore.toFixed(1) : '—'}
                        </span>
                      </div>
                    </div>
                    {severity && (
                      <span className={cn(
                        'px-1.5 py-0.5 rounded text-[10px] font-medium border w-20 text-center',
                        GAP_COLORS[severity]
                      )}>
                        {severity}
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

      {/* Team Tab */}
      {activeTab === 'Team' && (
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <h2 className="text-sm font-medium text-gray-900 flex items-center gap-2">
              <UserGroupIcon className="h-5 w-5 text-gray-400" />
              Team Members ({team.length})
            </h2>
          </div>
          <div className="card-body p-0">
            {team.length > 0 ? (
              <div className="divide-y divide-gray-200">
                {team.map((member) => (
                  <div key={member.id} className="px-4 py-3 flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {member.user_name || member.user?.full_name || member.user?.username || 'Unknown'}
                      </p>
                      <p className="text-xs text-gray-500 capitalize">{member.role.replace(/_/g, ' ')}</p>
                      {member.responsibilities && Array.isArray(member.responsibilities) && (
                        <p className="text-xs text-gray-400 mt-0.5">{member.responsibilities.join(' · ')}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {(member.is_primary || member.is_primary_contact) && (
                        <span className="text-xs bg-primary-100 text-primary-700 px-2 py-0.5 rounded">Primary</span>
                      )}
                      {member.receives_alerts && (
                        <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">Alerts</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="px-4 py-8 text-center text-sm text-gray-500">No team members assigned yet.</p>
            )}
          </div>
        </div>
      )}

      {/* Improvements Tab */}
      {activeTab === 'Improvements' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <LightBulbIcon className="h-5 w-5 text-gray-400" />
              Improvement Points ({improvements.length})
            </h2>
          </div>
          <div className="card">
            <div className="card-body p-0 divide-y divide-gray-200">
              {improvements.map((imp: ImprovementPoint) => (
                <div key={imp.id} className="px-4 py-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-900">{imp.title}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{imp.description}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        'px-2 py-0.5 rounded text-xs font-medium',
                        imp.priority === 'critical' ? 'bg-red-100 text-red-800' :
                        imp.priority === 'high' ? 'bg-orange-100 text-orange-800' :
                        imp.priority === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-gray-100 text-gray-800'
                      )}>
                        {imp.priority}
                      </span>
                      <span className={cn(
                        'px-2 py-0.5 rounded text-xs font-medium',
                        imp.status === 'completed' ? 'bg-green-100 text-green-800' :
                        imp.status === 'in_progress' ? 'bg-blue-100 text-blue-800' :
                        imp.status === 'blocked' ? 'bg-red-100 text-red-800' :
                        'bg-gray-100 text-gray-800'
                      )}>
                        {imp.status.replace(/_/g, ' ')}
                      </span>
                    </div>
                  </div>
                  {/* Progress bar */}
                  {(() => {
                    const pct = imp.progress_percentage ?? imp.progress ?? 0
                    return (
                      <div className="mt-2 flex items-center gap-2">
                        <div className="flex-1 bg-gray-100 rounded-full h-1.5">
                          <div className="bg-primary-500 h-1.5 rounded-full" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="text-[10px] text-gray-500">
                          {pct}%{imp.action_count ? ` (${imp.completed_action_count ?? 0}/${imp.action_count} actions)` : ''}
                        </span>
                      </div>
                    )
                  })()}
                </div>
              ))}
              {improvements.length === 0 && (
                <p className="px-4 py-8 text-center text-sm text-gray-500">
                  No improvements yet. Generate them from perception gaps on the KPIs tab.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'History' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700">Performance History</h2>
            <button onClick={() => setShowRecordStatus(true)} className="btn-primary text-xs flex items-center gap-1">
              <PlusIcon className="h-3.5 w-3.5" /> Record Status
            </button>
          </div>

          {/* Trend Visualization */}
          {perfTrend && perfTrend.trend.length > 0 && (
            <div className="card">
              <div className="card-header flex items-center justify-between">
                <h3 className="text-sm font-medium text-gray-900">Performance Trend</h3>
                {perfTrend.current_status && (
                  <span className={cn(
                    'px-2 py-0.5 rounded text-xs font-medium capitalize',
                    PERF_STATUS_COLORS[perfTrend.current_status]
                  )}>
                    Current: {PERF_STATUS_LABELS[perfTrend.current_status]}
                  </span>
                )}
              </div>
              <div className="card-body">
                <div className="flex items-end gap-1 h-32">
                  {perfTrend.trend.map((point, i) => {
                    const scoreVal = point.overall_score ?? 50
                    const heightPct = Math.max(10, scoreVal)
                    const statusOrder: PerformanceStatus[] = ['critical', 'poor', 'concerning', 'acceptable', 'good', 'excellent']
                    const barColor = statusOrder.indexOf(point.status) >= 4 ? 'bg-green-500' :
                      statusOrder.indexOf(point.status) >= 2 ? 'bg-amber-500' : 'bg-red-500'
                    return (
                      <div key={i} className="flex-1 flex flex-col items-center gap-1">
                        <div
                          className={cn('w-full rounded-t', barColor)}
                          style={{ height: `${heightPct}%` }}
                          title={`${point.period}: ${PERF_STATUS_LABELS[point.status]} (${point.overall_score ?? '—'})`}
                        />
                        <span className="text-[9px] text-gray-400 truncate w-full text-center">{point.period}</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          )}

          {/* History Table */}
          <div className="card">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Period</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Previous</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Score</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Trigger</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Notes</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {historyEntries.map((entry) => (
                    <tr key={entry.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{entry.period}</td>
                      <td className="px-4 py-3">
                        <span className={cn(
                          'px-2 py-0.5 rounded text-xs font-medium capitalize',
                          PERF_STATUS_COLORS[entry.status]
                        )}>
                          {PERF_STATUS_LABELS[entry.status]}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {entry.previous_status ? (
                          <span className={cn(
                            'px-2 py-0.5 rounded text-xs font-medium capitalize',
                            PERF_STATUS_COLORS[entry.previous_status]
                          )}>
                            {PERF_STATUS_LABELS[entry.previous_status]}
                          </span>
                        ) : '—'}
                      </td>
                      <td className="px-4 py-3 text-center text-sm font-semibold text-gray-900">
                        {entry.overall_score != null ? entry.overall_score : '—'}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">{entry.trigger || '—'}</td>
                      <td className="px-4 py-3 text-sm text-gray-500 max-w-[200px] truncate">{entry.notes || '—'}</td>
                    </tr>
                  ))}
                  {historyEntries.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-sm text-gray-500">
                        No performance history recorded yet
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Record Status Modal */}
      {showRecordStatus && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Record Performance Status</h2>
              <button onClick={() => setShowRecordStatus(false)} className="text-gray-400 hover:text-gray-600">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Status *</label>
                <select
                  value={statusForm.status || 'good'}
                  onChange={(e) => setStatusForm({ ...statusForm, status: e.target.value as PerformanceStatus })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                >
                  {Object.entries(PERF_STATUS_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Period *</label>
                  <input
                    type="text"
                    value={statusForm.period || ''}
                    onChange={(e) => setStatusForm({ ...statusForm, period: e.target.value })}
                    placeholder="e.g., 2026-Q1"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Score</label>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={statusForm.overall_score ?? ''}
                    onChange={(e) => setStatusForm({ ...statusForm, overall_score: e.target.value ? Number(e.target.value) : undefined })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Trigger</label>
                <input
                  type="text"
                  value={statusForm.trigger || ''}
                  onChange={(e) => setStatusForm({ ...statusForm, trigger: e.target.value })}
                  placeholder="e.g., Quarterly review"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
                <textarea
                  value={statusForm.notes || ''}
                  onChange={(e) => setStatusForm({ ...statusForm, notes: e.target.value })}
                  rows={2}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowRecordStatus(false)} className="btn-secondary">Cancel</button>
              <button
                onClick={() => {
                  if (statusForm.status && statusForm.period) {
                    recordStatusMutation.mutate(statusForm as RelationshipHistoryCreate)
                  }
                }}
                disabled={!statusForm.status || !statusForm.period || recordStatusMutation.isPending}
                className="btn-primary"
              >
                {recordStatusMutation.isPending ? 'Recording...' : 'Record'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Overview Tab */}
      {activeTab === 'Overview' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="card">
            <div className="card-header"><h3 className="text-sm font-medium text-gray-900">Details</h3></div>
            <div className="card-body space-y-3">
              <div>
                <p className="text-xs text-gray-500">Type</p>
                <p className="text-sm font-medium text-gray-900 capitalize">{relationship.relationship_type}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Status</p>
                <p className="text-sm font-medium text-gray-900 capitalize">{relationship.status}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Governance Tier</p>
                <p className="text-sm font-medium text-gray-900 capitalize">{relationship.governance_tier}</p>
              </div>
              {relationship.annual_value && (
                <div>
                  <p className="text-xs text-gray-500">Annual Value</p>
                  <p className="text-sm font-medium text-gray-900">
                    {relationship.currency || '$'}{Number(relationship.annual_value).toLocaleString()}
                  </p>
                </div>
              )}
              {relationship.description && (
                <div>
                  <p className="text-xs text-gray-500">Description</p>
                  <p className="text-sm text-gray-700">{relationship.description}</p>
                </div>
              )}
            </div>
          </div>
          <div className="card">
            <div className="card-header"><h3 className="text-sm font-medium text-gray-900">Summary</h3></div>
            <div className="card-body space-y-3">
              <div className="flex justify-between">
                <span className="text-sm text-gray-500">Active KPIs</span>
                <span className="text-sm font-medium">{kpis.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-500">Team Members</span>
                <span className="text-sm font-medium">{team.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-500">Open Improvements</span>
                <span className="text-sm font-medium">{improvements.filter(i => i.status !== 'completed' && i.status !== 'cancelled').length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-500">Perception Gaps</span>
                <span className="text-sm font-medium">{gapSummary?.kpis_with_gaps || 0}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Score Modal */}
      {showScore && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Submit Score</h2>
              <button onClick={() => setShowScore(null)} className="text-gray-400 hover:text-gray-600">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Perspective</label>
                <select
                  value={scoreForm.perspective || 'internal'}
                  onChange={(e) => setScoreForm({ ...scoreForm, perspective: e.target.value as any })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                >
                  <option value="internal">Internal</option>
                  <option value="external">External</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Score: <span className="text-primary-600 font-bold">{scoreForm.score}/10</span>
                </label>
                <input
                  type="range"
                  min={1}
                  max={10}
                  value={scoreForm.score || 5}
                  onChange={(e) => setScoreForm({ ...scoreForm, score: Number(e.target.value) })}
                  className="w-full accent-primary-600"
                />
                <div className="flex justify-between text-xs text-gray-400">
                  <span>Poor</span><span>Excellent</span>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Period</label>
                <input
                  type="text"
                  value={scoreForm.period || ''}
                  onChange={(e) => setScoreForm({ ...scoreForm, period: e.target.value })}
                  placeholder="e.g., 2026-Q1"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Comments</label>
                <textarea
                  value={scoreForm.comments || ''}
                  onChange={(e) => setScoreForm({ ...scoreForm, comments: e.target.value })}
                  rows={2}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowScore(null)} className="btn-secondary">Cancel</button>
              <button
                onClick={() => {
                  if (showScore && scoreForm.perspective && scoreForm.score) {
                    submitScoreMutation.mutate({
                      kpiId: showScore,
                      data: scoreForm as PerceptionScoreCreate,
                    })
                  }
                }}
                disabled={submitScoreMutation.isPending}
                className="btn-primary"
              >
                {submitScoreMutation.isPending ? 'Submitting...' : 'Submit'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add KPI Modal */}
      {showAddKPI && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Add KPI</h2>
              <button onClick={() => setShowAddKPI(false)} className="text-gray-400 hover:text-gray-600">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                <input
                  type="text"
                  value={kpiForm.name || ''}
                  onChange={(e) => setKpiForm({ ...kpiForm, name: e.target.value })}
                  placeholder="e.g., Service Delivery Quality"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                <select
                  value={kpiForm.category || 'service_delivery'}
                  onChange={(e) => setKpiForm({ ...kpiForm, category: e.target.value as any })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                >
                  <option value="service_delivery">Service Delivery</option>
                  <option value="quality">Quality</option>
                  <option value="timeliness">Timeliness</option>
                  <option value="communication">Communication</option>
                  <option value="innovation">Innovation</option>
                  <option value="cost_efficiency">Cost Efficiency</option>
                  <option value="compliance">Compliance</option>
                  <option value="satisfaction">Satisfaction</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea
                  value={kpiForm.description || ''}
                  onChange={(e) => setKpiForm({ ...kpiForm, description: e.target.value })}
                  rows={2}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Target Value</label>
                  <input
                    type="number"
                    value={kpiForm.target_value || ''}
                    onChange={(e) => setKpiForm({ ...kpiForm, target_value: Number(e.target.value) })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Frequency</label>
                  <select
                    value={kpiForm.frequency || 'quarterly'}
                    onChange={(e) => setKpiForm({ ...kpiForm, frequency: e.target.value as any })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                    <option value="quarterly">Quarterly</option>
                    <option value="annual">Annual</option>
                  </select>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowAddKPI(false)} className="btn-secondary">Cancel</button>
              <button
                onClick={() => {
                  if (kpiForm.name && id) {
                    createKPIMutation.mutate({ ...kpiForm, relationship_id: id } as KPICreate)
                  }
                }}
                disabled={!kpiForm.name || createKPIMutation.isPending}
                className="btn-primary"
              >
                {createKPIMutation.isPending ? 'Creating...' : 'Create KPI'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
