import { useState } from 'react'
import { useTranslation } from 'react-i18next'
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

export default function MilestoneConfigPanel() {
  const { t } = useTranslation()
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
      alert(t('masterdata.milestones.seedResult', { seeded: result.seeded, skipped: result.skipped }))
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
    if (window.confirm(t('masterdata.confirmDelete', { name: item.name }))) {
      deleteMutation.mutate(item.id)
    }
  }

  return (
    <div className="space-y-4">
      {/* Actions & Filters */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-500">{t('masterdata.filter')}</span>
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
              {t('masterdata.all')}
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
              {t('status.active')}
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
              {t('status.inactive')}
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
            {t('masterdata.seedFromStubs')}
          </button>
          <button onClick={openCreateModal} className="btn-primary">
            <PlusIcon className="h-4 w-4 mr-2" />
            {t('masterdata.milestones.addMilestone')}
          </button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-lg bg-red-50 p-4 text-red-700">
          {t('masterdata.milestones.loadError')}
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
                    {t('masterdata.milestones.code')}
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t('masterdata.name')}
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t('masterdata.milestones.daysFromStart')}
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t('masterdata.milestones.dependencies')}
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t('masterdata.milestones.creditAtRisk')}
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t('common.status')}
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t('common.actions')}
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
                      {t('masterdata.milestones.daysCount', { count: item.baseline_days_from_start })}
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
                        <span className="text-sm text-gray-400">{t('masterdata.milestones.none')}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                      {item.credit_at_risk ? formatCurrency(item.credit_at_risk) : '-'}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {item.is_active ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">
                          <CheckCircleIcon className="h-3 w-3" />
                          {t('status.active')}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">
                          <XCircleIcon className="h-3 w-3" />
                          {t('status.inactive')}
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
              {t('masterdata.milestones.empty')}
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
                {editingItem ? t('masterdata.milestones.editTitle') : t('masterdata.milestones.createTitle')}
              </h2>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('masterdata.milestones.milestoneCode')} *
                    </label>
                    <input
                      type="text"
                      value={formData.milestone_code}
                      onChange={(e) => setFormData({ ...formData, milestone_code: e.target.value })}
                      placeholder={t('masterdata.milestones.codePlaceholder')}
                      className="input"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('masterdata.milestones.daysFromStart')} *
                    </label>
                    <input
                      type="number"
                      min="0"
                      value={formData.baseline_days_from_start}
                      onChange={(e) => setFormData({ ...formData, baseline_days_from_start: e.target.value })}
                      placeholder={t('masterdata.milestones.daysPlaceholder')}
                      className="input"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('masterdata.name')} *
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder={t('masterdata.milestones.namePlaceholder')}
                    className="input"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('masterdata.description')}
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder={t('masterdata.descriptionPlaceholder')}
                    className="input"
                    rows={2}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('masterdata.milestones.dependencies')}
                    </label>
                    <input
                      type="text"
                      value={formData.dependencies}
                      onChange={(e) => setFormData({ ...formData, dependencies: e.target.value })}
                      placeholder={t('masterdata.milestones.dependenciesPlaceholder')}
                      className="input"
                    />
                    <p className="text-xs text-gray-500 mt-1">{t('masterdata.milestones.dependenciesHint')}</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('masterdata.milestones.creditAtRisk')}
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={formData.credit_at_risk}
                      onChange={(e) => setFormData({ ...formData, credit_at_risk: e.target.value })}
                      placeholder={t('masterdata.milestones.creditPlaceholder')}
                      className="input"
                    />
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="milestone_is_active"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <label htmlFor="milestone_is_active" className="text-sm text-gray-700">
                    {t('status.active')}
                  </label>
                </div>

                <div className="flex justify-end gap-3 pt-4 border-t">
                  <button type="button" onClick={closeModal} className="btn-secondary">
                    {t('common.cancel')}
                  </button>
                  <button
                    type="submit"
                    disabled={createMutation.isPending || updateMutation.isPending}
                    className="btn-primary"
                  >
                    {createMutation.isPending || updateMutation.isPending ? (
                      <LoadingSpinner size="sm" className="border-white border-t-transparent" />
                    ) : editingItem ? (
                      t('masterdata.update')
                    ) : (
                      t('masterdata.create')
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
