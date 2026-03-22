import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  LightBulbIcon,
  PlusIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'
import type { ImprovementCreate, ImprovementPriority, ImprovementStatus } from '@/types/governance'

const PRIORITY_COLORS: Record<ImprovementPriority, string> = {
  low: 'bg-gray-100 text-gray-700',
  medium: 'bg-blue-100 text-blue-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700',
}

const STATUS_COLORS: Record<ImprovementStatus, string> = {
  open: 'bg-gray-100 text-gray-700',
  in_progress: 'bg-yellow-100 text-yellow-700',
  blocked: 'bg-red-100 text-red-700',
  completed: 'bg-green-100 text-green-700',
  cancelled: 'bg-gray-200 text-gray-500',
}

export default function ImprovementsPage() {
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [priorityFilter, setPriorityFilter] = useState<string>('')
  const [showCreate, setShowCreate] = useState(false)
  const [formData, setFormData] = useState<Partial<ImprovementCreate>>({
    priority: 'medium',
    source: 'manual',
  })

  const { data: improvements = [], isLoading } = useQuery({
    queryKey: ['improvements', statusFilter, priorityFilter],
    queryFn: () => api.getImprovements({
      status: statusFilter || undefined,
      priority: priorityFilter || undefined,
    }),
  })

  const { data: relationships = [] } = useQuery({
    queryKey: ['relationships'],
    queryFn: () => api.getRelationships(),
  })

  const { data: kpis = [] } = useQuery({
    queryKey: ['kpis'],
    queryFn: () => api.getKPIs({}),
  })

  const createMutation = useMutation({
    mutationFn: (data: ImprovementCreate) => api.createImprovement(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['improvements'] })
      setShowCreate(false)
      setFormData({ priority: 'medium', source: 'manual' })
    },
  })

  const handleCreate = () => {
    if (!formData.title || !formData.relationship_id) return
    createMutation.mutate(formData as ImprovementCreate)
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
          <h1 className="text-xl font-bold text-gray-900">Improvement Points</h1>
          <p className="text-sm text-gray-500 mt-1">
            Track improvement initiatives linked to KPI perception gaps
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="btn-primary flex items-center gap-2"
        >
          <PlusIcon className="h-4 w-4" />
          New Improvement
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
        >
          <option value="">All Statuses</option>
          <option value="open">Open</option>
          <option value="in_progress">In Progress</option>
          <option value="blocked">Blocked</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <select
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
        >
          <option value="">All Priorities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {(['open', 'in_progress', 'blocked', 'completed', 'cancelled'] as ImprovementStatus[]).map((status) => (
          <div key={status} className="card card-body text-center">
            <p className="text-2xl font-bold text-gray-900">
              {improvements.filter(i => i.status === status).length}
            </p>
            <p className="text-xs text-gray-500 capitalize">{status.replace('_', ' ')}</p>
          </div>
        ))}
      </div>

      {/* Improvements List */}
      <div className="space-y-3">
        {improvements.map((imp) => (
          <div key={imp.id} className="card card-body">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-3">
                <LightBulbIcon className="h-5 w-5 text-amber-500 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-gray-900">{imp.title}</p>
                  {imp.description && (
                    <p className="text-xs text-gray-500 mt-1">{imp.description}</p>
                  )}
                  <div className="flex items-center gap-2 mt-2">
                    <span className={cn(
                      'px-2 py-0.5 rounded text-xs font-medium',
                      PRIORITY_COLORS[imp.priority]
                    )}>
                      {imp.priority}
                    </span>
                    <span className={cn(
                      'px-2 py-0.5 rounded text-xs font-medium',
                      STATUS_COLORS[imp.status]
                    )}>
                      {imp.status.replace('_', ' ')}
                    </span>
                    <span className="text-xs text-gray-400 capitalize">
                      Source: {imp.source}
                    </span>
                  </div>
                </div>
              </div>
              {imp.progress !== undefined && imp.progress !== null && (
                <div className="text-right shrink-0 ml-4">
                  <p className="text-sm font-semibold text-gray-900">{imp.progress}%</p>
                  <div className="w-20 h-1.5 bg-gray-200 rounded-full mt-1">
                    <div
                      className="h-full bg-violet-500 rounded-full"
                      style={{ width: `${imp.progress}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {improvements.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            <LightBulbIcon className="h-12 w-12 mx-auto mb-3 text-gray-300" />
            <p className="text-sm">No improvement points found.</p>
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">New Improvement Point</h2>
              <button onClick={() => setShowCreate(false)} className="text-gray-400 hover:text-gray-600">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Relationship *</label>
                <select
                  value={formData.relationship_id || ''}
                  onChange={(e) => setFormData({ ...formData, relationship_id: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
                >
                  <option value="">Select relationship...</option>
                  {relationships.map((rel) => (
                    <option key={rel.id} value={rel.id}>
                      {rel.org_a?.name || rel.org_a_id} ↔ {rel.org_b?.name || rel.org_b_id}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Title *</label>
                <input
                  type="text"
                  value={formData.title || ''}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
                />
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
                  <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
                  <select
                    value={formData.priority || 'medium'}
                    onChange={(e) => setFormData({ ...formData, priority: e.target.value as ImprovementPriority })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">KPI</label>
                  <select
                    value={formData.kpi_id || ''}
                    onChange={(e) => setFormData({ ...formData, kpi_id: e.target.value || undefined })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
                  >
                    <option value="">None</option>
                    {kpis.map((kpi) => (
                      <option key={kpi.id} value={kpi.id}>{kpi.name}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowCreate(false)} className="btn-secondary">Cancel</button>
              <button
                onClick={handleCreate}
                disabled={!formData.title || !formData.relationship_id || createMutation.isPending}
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
