import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'
import type { SLAMasterData, SLAMasterDataCreate, SLAMasterDataUpdate } from '@/types/admin'

interface FormData {
  reference_code: string
  name: string
  description: string
  target_value: string
  minimum_value: string
  typical_performance: string
  volatility: string
  category: string
  service_tower: string
  is_active: boolean
}

const emptyFormData: FormData = {
  reference_code: '',
  name: '',
  description: '',
  target_value: '',
  minimum_value: '',
  typical_performance: '',
  volatility: '',
  category: '',
  service_tower: '',
  is_active: true,
}

export default function SLAConfigPanel() {
  const queryClient = useQueryClient()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<SLAMasterData | null>(null)
  const [formData, setFormData] = useState<FormData>(emptyFormData)
  const [activeFilter, setActiveFilter] = useState<boolean | undefined>(undefined)

  const { data, isLoading, error } = useQuery({
    queryKey: ['sla-master-data', activeFilter],
    queryFn: () => api.getSLAMasterData({ active_only: activeFilter }),
  })

  const createMutation = useMutation({
    mutationFn: (data: SLAMasterDataCreate) => api.createSLAMasterData(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sla-master-data'] })
      closeModal()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: SLAMasterDataUpdate }) =>
      api.updateSLAMasterData(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sla-master-data'] })
      closeModal()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteSLAMasterData(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sla-master-data'] })
    },
  })

  const seedMutation = useMutation({
    mutationFn: () => api.seedSLAMasterData(),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['sla-master-data'] })
      alert(`Seeded ${result.seeded} SLA configurations (${result.skipped} already existed)`)
    },
  })

  const openCreateModal = () => {
    setEditingItem(null)
    setFormData(emptyFormData)
    setIsModalOpen(true)
  }

  const openEditModal = (item: SLAMasterData) => {
    setEditingItem(item)
    setFormData({
      reference_code: item.reference_code,
      name: item.name,
      description: item.description || '',
      target_value: String(item.target_value),
      minimum_value: item.minimum_value ? String(item.minimum_value) : '',
      typical_performance: item.typical_performance ? String(item.typical_performance) : '',
      volatility: item.volatility ? String(item.volatility) : '',
      category: item.category || '',
      service_tower: item.service_tower || '',
      is_active: item.is_active,
    })
    setIsModalOpen(true)
  }

  const closeModal = () => {
    setIsModalOpen(false)
    setEditingItem(null)
    setFormData(emptyFormData)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const payload = {
      reference_code: formData.reference_code,
      name: formData.name,
      description: formData.description || undefined,
      target_value: parseFloat(formData.target_value),
      minimum_value: formData.minimum_value ? parseFloat(formData.minimum_value) : undefined,
      typical_performance: formData.typical_performance ? parseFloat(formData.typical_performance) : undefined,
      volatility: formData.volatility ? parseFloat(formData.volatility) : undefined,
      category: formData.category || undefined,
      service_tower: formData.service_tower || undefined,
      is_active: formData.is_active,
    }

    if (editingItem) {
      updateMutation.mutate({ id: editingItem.id, data: payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  const handleDelete = (item: SLAMasterData) => {
    if (window.confirm(`Are you sure you want to delete "${item.name}"?`)) {
      deleteMutation.mutate(item.id)
    }
  }

  const formatPercentage = (value: number | null) => {
    if (value === null) return '-'
    return `${(value * 100).toFixed(2)}%`
  }

  return (
    <div className="space-y-4">
      {/* Actions & Filters */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-500">Filter:</span>
          <div className="flex gap-2">
            <button
              onClick={() => setActiveFilter(undefined)}
              className={cn(
                'px-3 py-1 text-sm rounded-full',
                activeFilter === undefined
                  ? 'bg-primary-100 text-primary-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              )}
            >
              All
            </button>
            <button
              onClick={() => setActiveFilter(true)}
              className={cn(
                'px-3 py-1 text-sm rounded-full',
                activeFilter === true
                  ? 'bg-green-100 text-green-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              )}
            >
              Active
            </button>
            <button
              onClick={() => setActiveFilter(false)}
              className={cn(
                'px-3 py-1 text-sm rounded-full',
                activeFilter === false
                  ? 'bg-red-100 text-red-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              )}
            >
              Inactive
            </button>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => seedMutation.mutate()}
            disabled={seedMutation.isPending}
            className="btn-secondary"
          >
            {seedMutation.isPending ? (
              <LoadingSpinner size="sm" />
            ) : (
              <ArrowPathIcon className="h-4 w-4 mr-2" />
            )}
            Seed from Stubs
          </button>
          <button onClick={openCreateModal} className="btn-primary">
            <PlusIcon className="h-4 w-4 mr-2" />
            Add SLA Config
          </button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-lg bg-red-50 p-4 text-red-700">
          Error loading SLA configurations. Please try again.
        </div>
      )}

      {/* Table */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size="lg" />
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Reference
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Target
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Minimum
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Category
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {data?.items.map((item) => (
                  <tr key={item.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className="text-sm font-mono font-medium text-gray-900">
                        {item.reference_code}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-sm text-gray-900">{item.name}</div>
                      {item.service_tower && (
                        <div className="text-xs text-gray-500">{item.service_tower}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                      {formatPercentage(item.target_value)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                      {formatPercentage(item.minimum_value)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                      {item.category || '-'}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {item.is_active ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">
                          <CheckCircleIcon className="h-3 w-3" />
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">
                          <XCircleIcon className="h-3 w-3" />
                          Inactive
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => openEditModal(item)}
                          className="p-1 text-gray-400 hover:text-gray-600"
                        >
                          <PencilSquareIcon className="h-5 w-5" />
                        </button>
                        <button
                          onClick={() => handleDelete(item)}
                          className="p-1 text-gray-400 hover:text-red-600"
                          disabled={deleteMutation.isPending}
                        >
                          <TrashIcon className="h-5 w-5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data?.items.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              No SLA configurations found. Click "Seed from Stubs" to import default configurations.
            </div>
          )}
        </div>
      )}

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/50" onClick={closeModal} />
            <div className="relative bg-white rounded-xl shadow-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                {editingItem ? 'Edit SLA Configuration' : 'Create SLA Configuration'}
              </h2>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Reference Code *
                    </label>
                    <input
                      type="text"
                      value={formData.reference_code}
                      onChange={(e) => setFormData({ ...formData, reference_code: e.target.value })}
                      placeholder="e.g., 12.1"
                      className="input"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Target Value *
                    </label>
                    <input
                      type="number"
                      step="0.0001"
                      value={formData.target_value}
                      onChange={(e) => setFormData({ ...formData, target_value: e.target.value })}
                      placeholder="e.g., 0.99"
                      className="input"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Name *
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="SLA name"
                    className="input"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Description
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Optional description"
                    className="input"
                    rows={2}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Minimum Value
                    </label>
                    <input
                      type="number"
                      step="0.0001"
                      value={formData.minimum_value}
                      onChange={(e) => setFormData({ ...formData, minimum_value: e.target.value })}
                      placeholder="e.g., 0.95"
                      className="input"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Typical Performance
                    </label>
                    <input
                      type="number"
                      step="0.0001"
                      value={formData.typical_performance}
                      onChange={(e) => setFormData({ ...formData, typical_performance: e.target.value })}
                      placeholder="e.g., 0.97"
                      className="input"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Category
                    </label>
                    <input
                      type="text"
                      value={formData.category}
                      onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                      placeholder="e.g., Critical Service Levels"
                      className="input"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Service Tower
                    </label>
                    <input
                      type="text"
                      value={formData.service_tower}
                      onChange={(e) => setFormData({ ...formData, service_tower: e.target.value })}
                      placeholder="e.g., Desktop Services"
                      className="input"
                    />
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="sla_is_active"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <label htmlFor="sla_is_active" className="text-sm text-gray-700">
                    Active
                  </label>
                </div>

                <div className="flex justify-end gap-3 pt-4 border-t">
                  <button type="button" onClick={closeModal} className="btn-secondary">
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={createMutation.isPending || updateMutation.isPending}
                    className="btn-primary"
                  >
                    {createMutation.isPending || updateMutation.isPending ? (
                      <LoadingSpinner size="sm" className="border-white border-t-transparent" />
                    ) : editingItem ? (
                      'Update'
                    ) : (
                      'Create'
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
