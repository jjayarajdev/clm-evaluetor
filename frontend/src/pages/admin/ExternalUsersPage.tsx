import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  MagnifyingGlassIcon,
  UserIcon,
  EnvelopeIcon,
  BuildingOfficeIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'

interface FormData {
  email: string
  full_name: string
  company_name: string
  title: string
  phone: string
}

const emptyFormData: FormData = {
  email: '',
  full_name: '',
  company_name: '',
  title: '',
  phone: '',
}

export default function ExternalUsersPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [formData, setFormData] = useState<FormData>(emptyFormData)
  const [search, setSearch] = useState('')

  // Fetch external users
  const { data, isLoading, error: fetchError } = useQuery({
    queryKey: ['external-users', search],
    queryFn: () => api.getExternalUsers({ page_size: 100, search: search || undefined }),
  })

  const [formError, setFormError] = useState<string | null>(null)

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: FormData) => api.createExternalUser(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['external-users'] })
      closeModal()
      setFormError(null)
    },
    onError: (err: Error) => {
      setFormError(err.message || t('externalUsers.createFailed'))
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<FormData> }) =>
      api.updateExternalUser(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['external-users'] })
      closeModal()
      setFormError(null)
    },
    onError: (err: Error) => {
      setFormError(err.message || t('externalUsers.updateFailed'))
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteExternalUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['external-users'] })
    },
    onError: (err: Error) => {
      alert(err.message || t('externalUsers.deleteFailed'))
    },
  })

  const openCreateModal = () => {
    setEditingId(null)
    setFormData(emptyFormData)
    setFormError(null)
    setIsModalOpen(true)
  }

  const openEditModal = (user: {
    id: string
    email: string
    full_name?: string
    company_name?: string
    title?: string
    phone?: string
  }) => {
    setEditingId(user.id)
    setFormData({
      email: user.email,
      full_name: user.full_name || '',
      company_name: user.company_name || '',
      title: user.title || '',
      phone: user.phone || '',
    })
    setFormError(null)
    setIsModalOpen(true)
  }

  const closeModal = () => {
    setIsModalOpen(false)
    setEditingId(null)
    setFormData(emptyFormData)
    setFormError(null)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (editingId) {
      updateMutation.mutate({ id: editingId, data: formData })
    } else {
      createMutation.mutate(formData)
    }
  }

  const handleDelete = (user: { id: string; email: string; full_name?: string }) => {
    if (confirm(t('externalUsers.confirmDeactivate', { name: user.full_name || user.email }))) {
      deleteMutation.mutate(user.id)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-700">{t('externalUsers.loadFailed')}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('nav.externalUsers')}</h1>
          <p className="text-gray-500 mt-1">
            {t('externalUsers.subtitle')}
          </p>
        </div>
        <button
          onClick={openCreateModal}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          <PlusIcon className="w-5 h-5" />
          {t('externalUsers.addExternalUser')}
        </button>
      </div>

      {/* Search */}
      <div className="mb-6">
        <div className="relative max-w-md">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            placeholder={t('externalUsers.searchPlaceholder')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
        </div>
      </div>

      {/* Users list */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {!data?.items.length ? (
          <div className="text-center py-12 text-gray-500">
            <UserIcon className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p className="text-lg font-medium">{t('externalUsers.noUsers')}</p>
            <p className="mt-1">{t('externalUsers.noUsersHint')}</p>
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('externalUsers.user')}
                </th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('externalUsers.company')}
                </th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('common.status')}
                </th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('externalUsers.activity')}
                </th>
                <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('common.actions')}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {data.items.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 rounded-full bg-primary-100 flex items-center justify-center">
                        <span className="text-sm font-semibold text-primary-700">
                          {(user.full_name || user.email).charAt(0).toUpperCase()}
                        </span>
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">
                          {user.full_name || t('externalUsers.noName')}
                        </p>
                        <p className="text-sm text-gray-500 flex items-center gap-1">
                          <EnvelopeIcon className="w-3 h-3" />
                          {user.email}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    {user.company_name ? (
                      <div className="flex items-center gap-1 text-gray-700">
                        <BuildingOfficeIcon className="w-4 h-4 text-gray-400" />
                        {user.company_name}
                      </div>
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                    {user.title && (
                      <p className="text-sm text-gray-500">{user.title}</p>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <span className={cn(
                      "inline-flex px-2 py-1 text-xs font-medium rounded-full",
                      user.is_active
                        ? "bg-green-100 text-green-700"
                        : "bg-gray-100 text-gray-600"
                    )}>
                      {user.is_active ? t('status.active') : t('status.inactive')}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {user.access_count > 0 ? (
                      <span>{t('externalUsers.accessCount', { count: user.access_count })}</span>
                    ) : (
                      <span className="text-gray-400">{t('externalUsers.neverAccessed')}</span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => openEditModal(user)}
                        className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                        title={t('common.edit')}
                      >
                        <PencilSquareIcon className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(user)}
                        className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                        title={t('common.delete')}
                      >
                        <TrashIcon className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
            <div className="p-6 border-b">
              <h2 className="text-xl font-semibold">
                {editingId ? t('externalUsers.editExternalUser') : t('externalUsers.addExternalUser')}
              </h2>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              {formError && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">
                  {formError}
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('externalUsers.email')} *
                </label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder={t('externalUsers.emailPlaceholder')}
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('externalUsers.fullName')}
                </label>
                <input
                  type="text"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder={t('externalUsers.fullNamePlaceholder')}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('externalUsers.company')}
                </label>
                <input
                  type="text"
                  value={formData.company_name}
                  onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder={t('externalUsers.companyPlaceholder')}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('externalUsers.title')}
                </label>
                <input
                  type="text"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder={t('externalUsers.titlePlaceholder')}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('externalUsers.phone')}
                </label>
                <input
                  type="tel"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder={t('externalUsers.phonePlaceholder')}
                />
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t">
                <button
                  type="button"
                  onClick={closeModal}
                  className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending || updateMutation.isPending}
                  className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
                >
                  {createMutation.isPending || updateMutation.isPending
                    ? t('externalUsers.saving')
                    : editingId
                    ? t('externalUsers.update')
                    : t('externalUsers.create')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
