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
import { cn, formatCurrency } from '@/lib/utils'
import type { MilestoneMasterData, MilestoneMasterDataCreate, MilestoneMasterDataUpdate } from '@/types/admin'

interface FormData {
  milestone_code: string
  name: string
  description: string
  baseline_days_from_start: string
  dependencies: string
  credit_at_risk: string
  is_active: boolean
}

const emptyFormData: FormData = {
  milestone_code: '',
  name: '',
  description: '',
  baseline_days_from_start: '',
  dependencies: '',
  credit_at_risk: '',
  is_active: true,
}

export default function MilestoneConfigPage() {
  const queryClient = useQueryClient()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<MilestoneMasterData | null>(null)
  const [formData, setFormData] = useState<FormData>(emptyFormData)
  const [activeFilter, setActiveFilter] = useState<boolean | undefined>(undefined)

  const { data, isLoading, error } = useQuery({
    queryKey: ['milestone-master-data', activeFilter],
    queryFn: () => api.getMilestoneMasterData({ active_only: activeFilter }),
  })

  const createMutation = useMutation({
    mutationFn: (data: MilestoneMasterDataCreate) => api.createMilestoneMasterData(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['milestone-master-data'] })
      closeModal()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: MilestoneMasterDataUpdate }) =>
      api.updateMilestoneMasterData(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['milestone-master-data'] })
      closeModal()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteMilestoneMasterData(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['milestone-master-data'] })
    },
  })

  const seedMutation = useMutation({
    mutationFn: () => api.seedMilestoneMasterData(),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['milestone-master-data'] })
      alert(`Seeded ${result.seeded} milestone configurations (${result.skipped} already existed)`)
    },
  })

  const openCreateModal = () => {
    setEditingItem(null)
    setFormData(emptyFormData)
    setIsModalOpen(true)
  }

  const openEditModal = (item: MilestoneMasterData) => {
    setEditingItem(item)
    setFormData({
      milestone_code: item.milestone_code,
      name: item.name,
      description: item.description || '',
      baseline_days_from_start: String(item.baseline_days_from_start),
      dependencies: item.dependencies.join(', '),
      credit_at_risk: item.credit_at_risk ? String(item.credit_at_risk) : '',
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
      milestone_code: formData.milestone_code,
      name: formData.name,
      description: formData.description || undefined,
      baseline_days_from_start: parseInt(formData.baseline_days_from_start),
      dependencies: formData.dependencies
        ? formData.dependencies.split(',').map((s) => s.trim()).filter(Boolean)
        : [],
      credit_at_risk: formData.credit_at_risk ? parseFloat(formData.credit_at_risk) : undefined,
      is_active: formData.is_active,
    }

    if (editingItem) {
      updateMutation.mutate({ id: editingItem.id, data: payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  const handleDelete = (item: MilestoneMasterData) => {
    if (window.confirm(`Are you sure you want to delete "${item.name}"?`)) {
      deleteMutation.mutate(item.id)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Milestone Configurations</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage milestone master data configurations for project tracking
          </p>
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
            Add Milestone
          </button>
        </div>
      </div>

      {/* Filters */}
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

      {/* Error state */}
      {error && (
        <div className="rounded-lg bg-red-50 p-4 text-red-700">
          Error loading milestone configurations. Please try again.
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
                    Code
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Days from Start
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Dependencies
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Credit at Risk
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
                        {item.milestone_code}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-sm text-gray-900">{item.name}</div>
                      {item.description && (
                        <div className="text-xs text-gray-500 truncate max-w-xs">
                          {item.description}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                      {item.baseline_days_from_start} days
                    </td>
                    <td className="px-4 py-3">
                      {item.dependencies.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {item.dependencies.map((dep) => (
                            <span
                              key={dep}
                              className="inline-flex px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600"
                            >
                              {dep}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-sm text-gray-400">None</span>
                      )}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                      {item.credit_at_risk ? formatCurrency(item.credit_at_risk) : '-'}
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
              No milestone configurations found. Click "Seed from Stubs" to import default configurations.
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
                {editingItem ? 'Edit Milestone Configuration' : 'Create Milestone Configuration'}
              </h2>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Milestone Code *
                    </label>
                    <input
                      type="text"
                      value={formData.milestone_code}
                      onChange={(e) => setFormData({ ...formData, milestone_code: e.target.value })}
                      placeholder="e.g., MS-2.1"
                      className="input"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Days from Start *
                    </label>
                    <input
                      type="number"
                      min="0"
                      value={formData.baseline_days_from_start}
                      onChange={(e) => setFormData({ ...formData, baseline_days_from_start: e.target.value })}
                      placeholder="e.g., 60"
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
                    placeholder="Milestone name"
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
                      Dependencies
                    </label>
                    <input
                      type="text"
                      value={formData.dependencies}
                      onChange={(e) => setFormData({ ...formData, dependencies: e.target.value })}
                      placeholder="e.g., MS-2.1, MS-3.1"
                      className="input"
                    />
                    <p className="text-xs text-gray-500 mt-1">Comma-separated milestone codes</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Credit at Risk
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={formData.credit_at_risk}
                      onChange={(e) => setFormData({ ...formData, credit_at_risk: e.target.value })}
                      placeholder="e.g., 50000"
                      className="input"
                    />
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="is_active"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <label htmlFor="is_active" className="text-sm text-gray-700">
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
