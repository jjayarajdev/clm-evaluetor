import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ChartBarSquareIcon,
  HeartIcon,
  LinkIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'
import type { GapSummary } from '@/types/governance'

export default function KPIScorecardPage() {
  const [selectedRelId, setSelectedRelId] = useState<string>('')

  const { data: relationships = [], isLoading: loadingRels } = useQuery({
    queryKey: ['relationships'],
    queryFn: () => api.getRelationships(),
  })

  const { data: kpis = [] } = useQuery({
    queryKey: ['kpis', selectedRelId],
    queryFn: () => api.getKPIs(selectedRelId ? { relationship_id: selectedRelId } : {}),
  })

  const { data: gapSummaryData } = useQuery<GapSummary>({
    queryKey: ['perception-gaps', selectedRelId],
    queryFn: () => api.getRelationshipGapSummary(selectedRelId),
    enabled: !!selectedRelId,
  })

  if (loadingRels) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const criticalCount = gapSummaryData?.critical_gaps ?? 0
  const significantCount = gapSummaryData?.significant_gaps ?? 0
  const alignedCount = gapSummaryData?.aligned ?? 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">KPI Scorecard</h1>
          <p className="text-sm text-gray-500 mt-1">
            Track KPI perception gaps across business relationships
          </p>
        </div>
      </div>

      {/* Relationship Selector */}
      <div className="flex items-center gap-4">
        <select
          value={selectedRelId}
          onChange={(e) => setSelectedRelId(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 min-w-[300px]"
        >
          <option value="">All Relationships</option>
          {relationships.map((rel) => (
            <option key={rel.id} value={rel.id}>
              {rel.org_a?.name || rel.org_a_id} ↔ {rel.org_b?.name || rel.org_b_id}
            </option>
          ))}
        </select>
      </div>

      {/* Summary Cards */}
      {selectedRelId && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="card card-body text-center">
            <p className="text-2xl font-bold text-gray-900">{kpis.length}</p>
            <p className="text-xs text-gray-500">Total KPIs</p>
          </div>
          <div className="card card-body text-center">
            <p className="text-2xl font-bold text-red-600">{criticalCount}</p>
            <p className="text-xs text-gray-500">Critical Gaps</p>
          </div>
          <div className="card card-body text-center">
            <p className="text-2xl font-bold text-orange-600">{significantCount}</p>
            <p className="text-xs text-gray-500">Significant Gaps</p>
          </div>
          <div className="card card-body text-center">
            <p className="text-2xl font-bold text-green-600">
              {alignedCount}
            </p>
            <p className="text-xs text-gray-500">Aligned</p>
          </div>
        </div>
      )}

      {/* KPI Table */}
      <div className="card">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">KPI Name</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Target</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Frequency</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Weight</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {kpis.map((kpi) => (
                <tr key={kpi.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <ChartBarSquareIcon className="h-4 w-4 text-primary-500" />
                      <span className="text-sm font-medium text-gray-900">{kpi.name}</span>
                    </div>
                    {kpi.description && (
                      <p className="text-xs text-gray-400 mt-0.5 ml-6">{kpi.description}</p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500 capitalize">{kpi.category}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{kpi.target_value ?? '—'}</td>
                  <td className="px-4 py-3 text-sm text-gray-500 capitalize">{kpi.frequency}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{kpi.weight ?? 1}</td>
                </tr>
              ))}
              {kpis.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-500">
                    {selectedRelId ? 'No KPIs defined for this relationship' : 'Select a relationship to view KPIs'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Relationship Health Overview (when no specific rel selected) */}
      {!selectedRelId && relationships.length > 0 && (
        <div className="card">
          <div className="card-body">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Relationship Health Overview</h3>
            <div className="space-y-3">
              {relationships.map((rel) => (
                <Link
                  key={rel.id}
                  to={`/relationships/${rel.id}`}
                  className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <LinkIcon className="h-4 w-4 text-gray-400" />
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {rel.org_a?.name || rel.org_a_id} ↔ {rel.org_b?.name || rel.org_b_id}
                      </p>
                      <p className="text-xs text-gray-500 capitalize">{rel.relationship_type} · {rel.governance_tier}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      'flex items-center gap-1 px-2 py-1 rounded-lg',
                      rel.health_score >= 70 ? 'text-green-600 bg-green-50' :
                      rel.health_score >= 40 ? 'text-amber-600 bg-amber-50' :
                      'text-red-600 bg-red-50'
                    )}>
                      <HeartIcon className="h-4 w-4" />
                      <span className="text-sm font-semibold">{rel.health_score}</span>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
