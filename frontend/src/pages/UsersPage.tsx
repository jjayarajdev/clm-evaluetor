import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  UserCircleIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn, formatDate } from '@/lib/utils'
import type { User, Role } from '@/types'
import type { BusinessUnit } from '@/types/business-unit'

const ROLE_LABELS: Record<Role, string> = {
  admin: 'Administrator',
  legal: 'Legal',
  procurement: 'Procurement',
  viewer: 'Viewer',
  super_admin: 'Super Admin',
  bu_head: 'BU Head',
}

const ROLE_COLORS: Record<Role, string> = {
  admin: 'bg-purple-100 text-purple-700',
  legal: 'bg-blue-100 text-blue-700',
  procurement: 'bg-green-100 text-green-700',
  viewer: 'bg-gray-100 text-gray-700',
  super_admin: 'bg-rose-100 text-rose-700',
  bu_head: 'bg-amber-100 text-amber-700',
}

interface UserFormData {
  username: string
  email: string
  full_name: string
  role: Role
  password?: string
  business_unit_id?: string
}

export default function UsersPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [formData, setFormData] = useState<UserFormData>({
    email: '',
    username: '',
    full_name: '',
    role: 'viewer',
    password: '',
  })

  const { data: users, isLoading, error } = useQuery({
    queryKey: ['users'],
    queryFn: () => api.getUsers(),
  })

  const { data: businessUnitsData } = useQuery({
    queryKey: ['business-units'],
    queryFn: () => api.getBusinessUnits({ page: 1, page_size: 100 }),
  })

  const businessUnits: BusinessUnit[] = businessUnitsData?.items ?? []

  // Log error for debugging
  if (error) {
    console.error('Error fetching users:', error)
  }

  const createMutation = useMutation({
    mutationFn: (data: UserFormData) => api.createUser({
      username: data.username,
      email: data.email,
      full_name: data.full_name || undefined,
      password: data.password || '',
      role: data.role,
      business_unit_id: data.business_unit_id || undefined,
    }),
    onSuccess: () => {
      setFormError(null)
      queryClient.invalidateQueries({ queryKey: ['users'] })
      closeModal()
    },
    onError: (err: any) => {
      setFormError(err?.response?.data?.detail || err?.message || t('users.createFailed'))
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      api.updateUser(id, data),
    onSuccess: () => {
      setFormError(null)
      queryClient.invalidateQueries({ queryKey: ['users'] })
      closeModal()
    },
    onError: (err: any) => {
      setFormError(err?.response?.data?.detail || err?.message || t('users.updateFailed'))
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
  })

  const openCreateModal = () => {
    setEditingUser(null)
    setFormError(null)
    setFormData({ email: '', username: '', full_name: '', role: 'viewer', password: '', business_unit_id: '' })
    setIsModalOpen(true)
  }

  const openEditModal = (user: User) => {
    setEditingUser(user)
    setFormError(null)
    setFormData({
      email: user.email,
      username: user.username,
      full_name: user.full_name || '',
      role: user.role,
      password: '',
      business_unit_id: user.business_unit_id || '',
    })
    setIsModalOpen(true)
  }

  const closeModal = () => {
    setIsModalOpen(false)
    setEditingUser(null)
    setFormError(null)
    setFormData({ email: '', username: '', full_name: '', role: 'viewer', password: '', business_unit_id: '' })
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)
    if (editingUser) {
      const updateData: Record<string, unknown> = {
        email: formData.email,
        username: formData.username,
        full_name: formData.full_name || null,
        role: formData.role,
        business_unit_id: formData.business_unit_id || null,
      }
      if (formData.password) {
        // Password is updated separately but we include it for convenience
        updateData.password = formData.password
      }
      updateMutation.mutate({ id: editingUser.id, data: updateData })
    } else {
      createMutation.mutate(formData)
    }
  }

  const handleDelete = (user: User) => {
    if (window.confirm(t('users.deleteConfirm', { username: user.username }))) {
      deleteMutation.mutate(user.id)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('nav.users')}</h1>
          <p className="mt-1 text-sm text-gray-500">
            {t('users.subtitle')}
          </p>
        </div>
        <button onClick={openCreateModal} className="btn-primary">
          <PlusIcon className="h-4 w-4 mr-2" />
          {t('users.addUser')}
        </button>
      </div>

      {/* Users table */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size="lg" />
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('users.user')}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('users.role')}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('users.businessUnit')}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('common.status')}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('users.created')}
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('common.actions')}
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {users?.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 rounded-full bg-gray-200 flex items-center justify-center">
                        <UserCircleIcon className="h-6 w-6 text-gray-500" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-900">
                          {user.username}
                        </p>
                        <p className="text-xs text-gray-500">{user.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                      ROLE_COLORS[user.role]
                    )}>
                      {user.role === 'admin' && <ShieldCheckIcon className="h-3 w-3 mr-1" />}
                      {t(`roles.${user.role}`, { defaultValue: ROLE_LABELS[user.role] })}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {user.business_unit_name || '--'}
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                      user.is_active
                        ? 'bg-green-100 text-green-700'
                        : 'bg-red-100 text-red-700'
                    )}>
                      {user.is_active ? t('status.active') : t('status.inactive')}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {formatDate(user.created_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => openEditModal(user)}
                        className="p-1 text-gray-400 hover:text-gray-600"
                      >
                        <PencilSquareIcon className="h-5 w-5" />
                      </button>
                      <button
                        onClick={() => handleDelete(user)}
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
      )}

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div
              className="fixed inset-0 bg-black/50"
              onClick={closeModal}
            />
            <div className="relative bg-white rounded-xl shadow-xl w-full max-w-md p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                {editingUser ? t('users.editUser') : t('users.createUser')}
              </h2>
              <form onSubmit={handleSubmit} className="space-y-4">
                {formError && (
                  <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
                    {formError}
                  </div>
                )}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('users.username')}
                  </label>
                  <input
                    type="text"
                    value={formData.username}
                    onChange={(e) =>
                      setFormData({ ...formData, username: e.target.value })
                    }
                    className="input"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('users.fullName')}
                  </label>
                  <input
                    type="text"
                    value={formData.full_name}
                    onChange={(e) =>
                      setFormData({ ...formData, full_name: e.target.value })
                    }
                    className="input"
                    placeholder={t('users.fullNamePlaceholder')}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('users.email')}
                  </label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) =>
                      setFormData({ ...formData, email: e.target.value })
                    }
                    className="input"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('users.role')}
                  </label>
                  <select
                    value={formData.role}
                    onChange={(e) =>
                      setFormData({ ...formData, role: e.target.value as Role })
                    }
                    className="input"
                  >
                    {Object.entries(ROLE_LABELS)
                      .filter(([value]) => value !== 'super_admin')
                      .map(([value, label]) => (
                        <option key={value} value={value}>
                          {t(`roles.${value}`, { defaultValue: label })}
                        </option>
                      ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('users.businessUnit')}
                  </label>
                  <select
                    value={formData.business_unit_id || ''}
                    onChange={(e) =>
                      setFormData({ ...formData, business_unit_id: e.target.value })
                    }
                    className="input"
                  >
                    <option value="">{t('users.noneOption')}</option>
                    {businessUnits
                      .filter((bu) => bu.is_active)
                      .map((bu) => (
                        <option key={bu.id} value={bu.id}>
                          {bu.name}
                        </option>
                      ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {editingUser ? t('users.newPasswordKeep') : t('users.password')}
                  </label>
                  <input
                    type="password"
                    value={formData.password}
                    onChange={(e) =>
                      setFormData({ ...formData, password: e.target.value })
                    }
                    className="input"
                    required={!editingUser}
                    minLength={8}
                  />
                </div>
                <div className="flex justify-end gap-3 pt-4">
                  <button
                    type="button"
                    onClick={closeModal}
                    className="btn-secondary"
                  >
                    {t('common.cancel')}
                  </button>
                  <button
                    type="submit"
                    disabled={createMutation.isPending || updateMutation.isPending}
                    className="btn-primary"
                  >
                    {createMutation.isPending || updateMutation.isPending ? (
                      <LoadingSpinner size="sm" className="border-white border-t-transparent" />
                    ) : editingUser ? (
                      t('users.update')
                    ) : (
                      t('users.create')
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
