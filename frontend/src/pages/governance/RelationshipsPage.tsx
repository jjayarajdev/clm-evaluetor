import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  LinkIcon,
  PlusIcon,
  HeartIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'
import type {
  RelationshipCreate,
  RelationshipStatus,
  GovernanceTier,
  Organization,
} from '@/types/governance'

const STATUS_COLORS: Record<RelationshipStatus, string> = {
  prospecting: 'bg-gray-100 text-gray-800',
  active: 'bg-green-100 text-green-800',
  at_risk: 'bg-red-100 text-red-800',
  on_hold: 'bg-yellow-100 text-yellow-800',
  terminated: 'bg-gray-200 text-gray-600',
}

const TIER_LABELS: Record<GovernanceTier, string> = {
  operational: 'Operational',
  tactical: 'Tactical',
  strategic: 'Strategic',
  executive: 'Executive',
}

function HealthBadge({ score }: { score: number }) {
  const color = score >= 70 ? 'text-green-600 bg-green-50' :
    score >= 40 ? 'text-amber-600 bg-amber-50' :
    'text-red-600 bg-red-50'
  return (
    <div className={cn('flex items-center gap-1.5 px-2 py-1 rounded-lg', color)}>
      <HeartIcon className="h-4 w-4" />
      <span className="text-sm font-semibold">{score}</span>
    </div>
  )
}

export default function RelationshipsPage() {
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
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

  const getOrgName = (orgId: string, orgs?: Organization[]) => {
    if (orgs) {
      const org = orgs.find(o => o.id === orgId)
      return org?.name || orgId
    }
    return orgId
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Business Relationships</h1>
          <p className="text-sm text-gray-500 mt-1">
            Track and manage relationships with counterparties
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

      {/* Relationship Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {relationships.map((rel) => (
          <Link
            key={rel.id}
            to={`/relationships/${rel.id}`}
            className="card hover:shadow-md transition-shadow"
          >
            <div className="card-body">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <LinkIcon className="h-5 w-5 text-violet-500" />
                  <span className={cn(
                    'px-2 py-0.5 rounded text-xs font-medium',
                    STATUS_COLORS[rel.status] || 'bg-gray-100 text-gray-800'
                  )}>
                    {rel.status}
                  </span>
                </div>
                <HealthBadge score={rel.health_score} />
              </div>

              <div className="mb-3">
                <p className="text-sm font-semibold text-gray-900">
                  {rel.org_a?.name || getOrgName(rel.org_a_id, organizations)}
                </p>
                <p className="text-xs text-gray-400 my-1">
                  ↕ {rel.relationship_type}
                </p>
                <p className="text-sm font-semibold text-gray-900">
                  {rel.org_b?.name || getOrgName(rel.org_b_id, organizations)}
                </p>
              </div>

              <div className="flex items-center justify-between text-xs text-gray-500">
                <span className="px-2 py-0.5 bg-gray-50 rounded">
                  {TIER_LABELS[rel.governance_tier] || rel.governance_tier}
                </span>
                {rel.annual_value && (
                  <span className="font-medium">
                    {rel.currency || '$'}{Number(rel.annual_value).toLocaleString()}/yr
                  </span>
                )}
              </div>
            </div>
          </Link>
        ))}

        {relationships.length === 0 && (
          <div className="col-span-full text-center py-12 text-gray-500">
            <LinkIcon className="h-12 w-12 mx-auto mb-3 text-gray-300" />
            <p className="text-sm">No relationships yet. Create your first one.</p>
          </div>
        )}
      </div>

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
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
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
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
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
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
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
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
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
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Annual Value</label>
                  <input
                    type="number"
                    value={formData.annual_value || ''}
                    onChange={(e) => setFormData({ ...formData, annual_value: Number(e.target.value) })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
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
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
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
