import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  LinkIcon,
  PlusIcon,
  HeartIcon,
  XMarkIcon,
  DocumentTextIcon,
  ChartBarIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'
import type {
  BusinessRelationship,
  RelationshipCreate,
  RelationshipStatus,
  GovernanceTier,
  HealthScoreFactor,
} from '@/types/governance'

const STATUS_COLORS: Record<RelationshipStatus, string> = {
  prospecting: 'bg-gray-100 text-gray-700',
  active: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
  at_risk: 'bg-red-50 text-red-700 border border-red-200',
  on_hold: 'bg-amber-50 text-amber-700 border border-amber-200',
  terminated: 'bg-gray-100 text-gray-500 border border-gray-200',
}

const TIER_COLORS: Record<GovernanceTier, string> = {
  operational: 'text-gray-600',
  tactical: 'text-blue-600',
  strategic: 'text-primary-600',
  executive: 'text-amber-600',
}

const TYPE_ICONS: Record<string, string> = {
  customer: 'text-blue-500',
  supplier: 'text-emerald-500',
  partner: 'text-primary-500',
  joint_venture: 'text-amber-500',
  reseller: 'text-cyan-500',
  distributor: 'text-orange-500',
}

function HealthRing({ score, size = 48 }: { score: number; size?: number }) {
  const radius = (size - 6) / 2
  const circumference = 2 * Math.PI * radius
  const progress = (score / 100) * circumference
  const color = score >= 80 ? '#10b981' : score >= 60 ? '#f59e0b' : '#ef4444'

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="#f3f4f6" strokeWidth={4}
        />
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={color} strokeWidth={4}
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          strokeLinecap="round"
          className="transition-all duration-700"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-sm font-bold" style={{ color }}>{score}</span>
      </div>
    </div>
  )
}

function ScoreBar({ label, score, weight, detail, color }: {
  label: string; score: number; weight: number; detail: string; color: string
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-700">{label}</span>
          <span className="text-xs text-gray-400">{weight}%</span>
        </div>
        <span className="text-sm font-semibold" style={{ color }}>{score}</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${score}%`, backgroundColor: color }}
        />
      </div>
      <p className="text-xs text-gray-400">{detail}</p>
    </div>
  )
}

function HealthModal({ relationship, onClose }: {
  relationship: BusinessRelationship; onClose: () => void
}) {
  const { data: health, isLoading } = useQuery({
    queryKey: ['relationship-health', relationship.id],
    queryFn: () => api.getRelationshipHealth(relationship.id),
  })

  const factors = health?.factors || {}
  const counterparty = relationship.org_b?.name || relationship.name || ''
  const score = relationship.health_score

  const getColor = (s: number) => s >= 80 ? '#10b981' : s >= 60 ? '#f59e0b' : '#ef4444'

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-gray-100">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-lg font-bold text-gray-900">Health Score Breakdown</h2>
              <p className="text-sm text-gray-500 mt-0.5">{counterparty}</p>
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 p-1">
              <XMarkIcon className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Score ring */}
        <div className="flex items-center justify-center py-6">
          <HealthRing score={score} size={96} />
        </div>

        {/* Factors */}
        <div className="px-6 pb-6 space-y-5">
          {isLoading ? (
            <div className="flex justify-center py-8"><LoadingSpinner /></div>
          ) : (
            <>
              {typeof factors.risk === 'object' && (
                <ScoreBar
                  label={(factors.risk as HealthScoreFactor).label}
                  score={(factors.risk as HealthScoreFactor).score}
                  weight={(factors.risk as HealthScoreFactor).weight}
                  detail={(factors.risk as HealthScoreFactor).detail}
                  color={getColor((factors.risk as HealthScoreFactor).score)}
                />
              )}
              {typeof factors.sla === 'object' && (
                <ScoreBar
                  label={(factors.sla as HealthScoreFactor).label}
                  score={(factors.sla as HealthScoreFactor).score}
                  weight={(factors.sla as HealthScoreFactor).weight}
                  detail={(factors.sla as HealthScoreFactor).detail}
                  color={getColor((factors.sla as HealthScoreFactor).score)}
                />
              )}
              {typeof factors.obligations === 'object' && (
                <ScoreBar
                  label={(factors.obligations as HealthScoreFactor).label}
                  score={(factors.obligations as HealthScoreFactor).score}
                  weight={(factors.obligations as HealthScoreFactor).weight}
                  detail={(factors.obligations as HealthScoreFactor).detail}
                  color={getColor((factors.obligations as HealthScoreFactor).score)}
                />
              )}
              {typeof factors.perception === 'object' && (
                <div className="pt-3 border-t border-gray-100">
                  <ScoreBar
                    label={(factors.perception as HealthScoreFactor).label}
                    score={(factors.perception as HealthScoreFactor).score}
                    weight={0}
                    detail={(factors.perception as HealthScoreFactor).detail}
                    color={getColor((factors.perception as HealthScoreFactor).score)}
                  />
                  <p className="text-xs text-gray-400 mt-1 italic">Informational — not included in health score</p>
                </div>
              )}

              {/* No data state */}
              {!factors.risk && !factors.sla && !factors.obligations && (
                <div className="text-center py-4">
                  <InformationCircleIcon className="h-8 w-8 mx-auto text-gray-300 mb-2" />
                  <p className="text-sm text-gray-500">
                    No contract data available yet.
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    Health score is estimated from perception gap analysis.
                  </p>
                </div>
              )}

              {/* Summary stats */}
              <div className="flex gap-4 pt-3 border-t border-gray-100">
                <div className="flex-1 text-center">
                  <p className="text-xl font-bold text-gray-900">{typeof factors.contract_count === 'number' ? factors.contract_count : relationship.contract_count || 0}</p>
                  <p className="text-xs text-gray-500">Contracts</p>
                </div>
                <div className="flex-1 text-center">
                  <p className="text-xl font-bold text-gray-900">{typeof factors.kpi_count === 'number' ? factors.kpi_count : relationship.kpi_count || 0}</p>
                  <p className="text-xs text-gray-500">KPIs</p>
                </div>
                <div className="flex-1 text-center">
                  <p className="text-xl font-bold text-gray-900">{relationship.governance_tier ? relationship.governance_tier.charAt(0).toUpperCase() + relationship.governance_tier.slice(1) : '—'}</p>
                  <p className="text-xs text-gray-500">Tier</p>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-gray-50 rounded-b-2xl border-t border-gray-100">
          <Link
            to={`/relationships/${relationship.id}`}
            className="btn-primary w-full text-center block"
          >
            View Full Details
          </Link>
        </div>
      </div>
    </div>
  )
}

export default function RelationshipsPage() {
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [selectedRelationship, setSelectedRelationship] = useState<BusinessRelationship | null>(null)
  const [filterType, setFilterType] = useState<string>('')
  const [formData, setFormData] = useState<Partial<RelationshipCreate>>({
    relationship_type: 'customer',
    governance_tier: 'tactical',
  })

  const { data: relationships = [], isLoading } = useQuery({
    queryKey: ['relationships'],
    queryFn: () => api.getRelationships(),
  })

  const { data: organizations = [] } = useQuery({
    queryKey: ['organizations'],
    queryFn: () => api.getOrganizations({ active_only: true }),
  })

  const createMutation = useMutation({
    mutationFn: (data: RelationshipCreate) => api.createRelationship(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['relationships'] })
      setShowCreate(false)
      setFormData({ relationship_type: 'customer', governance_tier: 'tactical' })
    },
  })

  const handleCreate = () => {
    if (!formData.org_a_id || !formData.org_b_id || !formData.relationship_type) return
    createMutation.mutate(formData as RelationshipCreate)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  // Summary stats
  const totalRelationships = relationships.length
  const avgHealth = totalRelationships > 0
    ? Math.round(relationships.reduce((sum, r) => sum + (r.health_score || 0), 0) / totalRelationships)
    : 0
  const atRiskCount = relationships.filter(r => r.health_score < 70).length
  const healthyCount = relationships.filter(r => r.health_score >= 80).length

  // Type counts
  const typeCounts = relationships.reduce((acc, r) => {
    acc[r.relationship_type] = (acc[r.relationship_type] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  // Filter
  const filtered = filterType
    ? relationships.filter(r => r.relationship_type === filterType)
    : relationships

  // Sort by health score (worst first for attention)
  const sorted = [...filtered].sort((a, b) => a.health_score - b.health_score)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Business Relationships</h1>
          <p className="text-sm text-gray-500 mt-1">
            Governance health across your partner ecosystem
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="btn-primary flex items-center gap-2"
        >
          <PlusIcon className="h-4 w-4" />
          New Relationship
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-2 mb-2">
            <LinkIcon className="h-4 w-4 text-primary-500" />
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Total</span>
          </div>
          <p className="text-2xl font-bold text-gray-900">{totalRelationships}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-2 mb-2">
            <HeartIcon className="h-4 w-4 text-emerald-500" />
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Avg Health</span>
          </div>
          <p className="text-2xl font-bold" style={{ color: avgHealth >= 80 ? '#10b981' : avgHealth >= 60 ? '#f59e0b' : '#ef4444' }}>{avgHealth}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-2 mb-2">
            <ShieldCheckIcon className="h-4 w-4 text-emerald-500" />
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Healthy</span>
          </div>
          <p className="text-2xl font-bold text-emerald-600">{healthyCount}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-2 mb-2">
            <ExclamationTriangleIcon className="h-4 w-4 text-red-500" />
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Needs Attention</span>
          </div>
          <p className="text-2xl font-bold text-red-600">{atRiskCount}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setFilterType('')}
          className={cn(
            'px-3 py-1.5 rounded-full text-xs font-medium transition-colors',
            !filterType ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          )}
        >
          All ({totalRelationships})
        </button>
        {Object.entries(typeCounts).map(([type, count]) => (
          <button
            key={type}
            onClick={() => setFilterType(filterType === type ? '' : type)}
            className={cn(
              'px-3 py-1.5 rounded-full text-xs font-medium transition-colors capitalize',
              filterType === type ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
          >
            {type.replace('_', ' ')} ({count})
          </button>
        ))}
      </div>

      {/* Relationship Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {sorted.map((rel) => {
          const counterparty = rel.org_b?.name || rel.name || ''

          return (
            <div
              key={rel.id}
              className={cn(
                'bg-white rounded-xl border transition-all hover:shadow-lg group cursor-pointer',
                rel.health_score < 70 ? 'border-red-200' : 'border-gray-200 hover:border-primary-300'
              )}
            >
              {/* Card top — clickable to detail page */}
              <Link to={`/relationships/${rel.id}`} className="block p-5">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      'px-2 py-0.5 rounded-full text-xs font-medium',
                      STATUS_COLORS[rel.status] || 'bg-gray-100 text-gray-700'
                    )}>
                      {rel.status}
                    </span>
                    <span className={cn('text-xs font-medium capitalize', TYPE_ICONS[rel.relationship_type] || 'text-gray-500')}>
                      {rel.relationship_type.replace('_', ' ')}
                    </span>
                  </div>
                  <span className={cn('text-xs', TIER_COLORS[rel.governance_tier] || 'text-gray-400')}>
                    {rel.governance_tier ? rel.governance_tier.charAt(0).toUpperCase() + rel.governance_tier.slice(1) : ''}
                  </span>
                </div>

                {/* Counterparty name — the star */}
                <h3 className="text-base font-bold text-gray-900 group-hover:text-primary-700 transition-colors">
                  {counterparty}
                </h3>

                {/* Meta row */}
                <div className="flex items-center gap-3 mt-3 text-xs text-gray-400">
                  {(rel.contract_count ?? 0) > 0 && (
                    <span className="flex items-center gap-1">
                      <DocumentTextIcon className="h-3.5 w-3.5" />
                      {rel.contract_count} contracts
                    </span>
                  )}
                  {(rel.kpi_count ?? 0) > 0 && (
                    <span className="flex items-center gap-1">
                      <ChartBarIcon className="h-3.5 w-3.5" />
                      {rel.kpi_count} KPIs
                    </span>
                  )}
                  {rel.annual_value && (
                    <span className="font-medium text-gray-600">
                      {rel.currency || '$'}{Number(rel.annual_value).toLocaleString()}/yr
                    </span>
                  )}
                </div>
              </Link>

              {/* Health score footer — clickable for modal */}
              <button
                onClick={(e) => {
                  e.preventDefault()
                  setSelectedRelationship(rel)
                }}
                className={cn(
                  'w-full flex items-center justify-between px-5 py-3 border-t transition-colors',
                  rel.health_score < 70
                    ? 'border-red-100 bg-red-50/50 hover:bg-red-50'
                    : 'border-gray-100 bg-gray-50/50 hover:bg-gray-100'
                )}
                title="Click for score breakdown"
              >
                <div className="flex items-center gap-2">
                  <HealthRing score={rel.health_score} size={32} />
                  <span className="text-xs text-gray-500">Health Score</span>
                </div>
                <span className="text-xs text-primary-500 font-medium opacity-0 group-hover:opacity-100 transition-opacity">
                  View Breakdown →
                </span>
              </button>
            </div>
          )
        })}

        {sorted.length === 0 && (
          <div className="col-span-full text-center py-12 text-gray-500">
            <LinkIcon className="h-12 w-12 mx-auto mb-3 text-gray-300" />
            <p className="text-sm">
              {filterType ? 'No relationships match this filter.' : 'No relationships yet. Create your first one.'}
            </p>
          </div>
        )}
      </div>

      {/* Health Score Modal */}
      {selectedRelationship && (
        <HealthModal
          relationship={selectedRelationship}
          onClose={() => setSelectedRelationship(null)}
        />
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">New Relationship</h2>
              <button onClick={() => setShowCreate(false)} className="text-gray-400 hover:text-gray-600">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Organization A *</label>
                <select
                  value={formData.org_a_id || ''}
                  onChange={(e) => setFormData({ ...formData, org_a_id: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                >
                  <option value="">Select organization...</option>
                  {organizations.map((org) => (
                    <option key={org.id} value={org.id}>{org.name} ({org.org_type})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Organization B *</label>
                <select
                  value={formData.org_b_id || ''}
                  onChange={(e) => setFormData({ ...formData, org_b_id: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                >
                  <option value="">Select organization...</option>
                  {organizations.filter(o => o.id !== formData.org_a_id).map((org) => (
                    <option key={org.id} value={org.id}>{org.name} ({org.org_type})</option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Type *</label>
                  <select
                    value={formData.relationship_type || 'customer'}
                    onChange={(e) => setFormData({ ...formData, relationship_type: e.target.value as any })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                  >
                    <option value="customer">Customer</option>
                    <option value="supplier">Supplier</option>
                    <option value="partner">Partner</option>
                    <option value="joint_venture">Joint Venture</option>
                    <option value="reseller">Reseller</option>
                    <option value="distributor">Distributor</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Governance Tier</label>
                  <select
                    value={formData.governance_tier || 'tactical'}
                    onChange={(e) => setFormData({ ...formData, governance_tier: e.target.value as any })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                  >
                    <option value="operational">Operational</option>
                    <option value="tactical">Tactical</option>
                    <option value="strategic">Strategic</option>
                    <option value="executive">Executive</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea
                  value={formData.description || ''}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  rows={2}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Annual Value</label>
                  <input
                    type="number"
                    value={formData.annual_value || ''}
                    onChange={(e) => setFormData({ ...formData, annual_value: Number(e.target.value) })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Currency</label>
                  <input
                    type="text"
                    value={formData.currency || ''}
                    onChange={(e) => setFormData({ ...formData, currency: e.target.value.toUpperCase() })}
                    placeholder="USD"
                    maxLength={3}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                  />
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowCreate(false)} className="btn-secondary">Cancel</button>
              <button
                onClick={handleCreate}
                disabled={!formData.org_a_id || !formData.org_b_id || createMutation.isPending}
                className="btn-primary"
              >
                {createMutation.isPending ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
