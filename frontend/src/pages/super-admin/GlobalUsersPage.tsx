import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import {
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  UserCircleIcon,
  ShieldCheckIcon,
  FunnelIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn, formatDate } from '@/lib/utils'
import type { Tenant, Role, UserWithTenant } from '@/types'
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
  tenant_id: string
  username: string
  email: string
  role: Role
  password: string
  business_unit_id: string
}

interface EditFormData {
  username: string
  role: Role
  is_active: boolean
  new_password: string
  business_unit_id: string
}

export default function GlobalUsersPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const tenantFilter = searchParams.get('tenant') || ''

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<UserWithTenant | null>(null)
  const [deleteConfirmUser, setDeleteConfirmUser] = useState<UserWithTenant | null>(null)
  const [formData, setFormData] = useState<UserFormData>({
    tenant_id: tenantFilter,
    username: '',
    email: '',
    role: 'viewer',
    password: '',
    business_unit_id: '',
  })
  const [editFormData, setEditFormData] = useState<EditFormData>({
    username: '',
    role: 'viewer',
    is_active: true,
    new_password: '',
    business_unit_id: '',
  })

  const { data: users, isLoading: usersLoading, error } = useQuery<UserWithTenant[]>({
    queryKey: ['all-users', tenantFilter],
    queryFn: () => api.getAllUsers(tenantFilter || undefined),
  })

  const { data: tenants } = useQuery<Tenant[]>({
    queryKey: ['tenants-list'],
    queryFn: () => api.getTenants(false),
  })

  // Fetch BUs for the selected tenant (used in create modal) or editing user's tenant
  const buTenantId = formData.tenant_id || editingUser?.tenant_id || ''
  const { data: businessUnitsData } = useQuery({
    queryKey: ['business-units', buTenantId],
    queryFn: () => api.getBusinessUnits({ page: 1, page_size: 100 }, buTenantId),
    enabled: !!buTenantId,
  })
  const businessUnits: BusinessUnit[] = businessUnitsData?.items ?? []

  const createMutation = useMutation({
    mutationFn: (data: UserFormData) => api.createUserForTenant(data.tenant_id, {
      username: data.username,
      email: data.email,
      password: data.password,
      role: data.role,
      business_unit_id: data.business_unit_id || undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['all-users'] })
      closeCreateModal()
    },
  })

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: string; data: EditFormData }) => {
      const { new_password, ...updateData } = data
      await api.updateUser(id, {
        ...updateData,
        business_unit_id: updateData.business_unit_id || null,
      })
      if (new_password) {
        await api.updateUserPassword(id, new_password)
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['all-users'] })
      setEditingUser(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['all-users'] })
      setDeleteConfirmUser(null)
    },
  })

  const handleTenantFilterChange = (tenantId: string) => {
    if (tenantId) {
      setSearchParams({ tenant: tenantId })
    } else {
      setSearchParams({})
    }
  }

  const openCreateModal = () => {
    setFormData({
      tenant_id: tenantFilter,
      username: '',
      email: '',
      role: 'viewer',
      password: '',
      business_unit_id: '',
    })
    setIsCreateModalOpen(true)
  }

  const closeCreateModal = () => {
    setIsCreateModalOpen(false)
    setFormData({
      tenant_id: tenantFilter,
      username: '',
      email: '',
      role: 'viewer',
      password: '',
      business_unit_id: '',
    })
  }

  const openEditModal = (user: UserWithTenant) => {
    setEditingUser(user)
    setEditFormData({
      username: user.username,
      role: user.role,
      is_active: user.is_active,
      new_password: '',
      business_unit_id: user.business_unit_id || '',
    })
  }

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(formData)
  }

  const handleEditSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingUser) return
    updateMutation.mutate({ id: editingUser.id, data: editFormData })
  }

  const getTenantName = (tenantId: string) => {
    return tenants?.find(t => t.id === tenantId)?.name || tenantId
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('nav.allUsers')}</h1>
          <p className="mt-1 text-sm text-gray-500">
            {t('superadmin.users.subtitle')}
          </p>
        </div>
        <button onClick={openCreateModal} className="btn-primary">
          <PlusIcon className="h-4 w-4 mr-2" />
          {t('superadmin.users.addUser')}
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <FunnelIcon className="h-4 w-4 text-gray-400" />
          <span className="text-sm text-gray-500">{t('superadmin.users.filterByTenant')}</span>
        </div>
        <select
          value={tenantFilter}
          onChange={(e) => handleTenantFilterChange(e.target.value)}
          className="input max-w-xs"
        >
          <option value="">{t('superadmin.users.allTenants')}</option>
          {tenants?.map((tenant) => (
            <option key={tenant.id} value={tenant.id}>
              {tenant.name}
            </option>
          ))}
        </select>
        {tenantFilter && (
          <button
            onClick={() => handleTenantFilterChange('')}
            className="text-sm text-primary-600 hover:text-primary-700"
          >
            {t('superadmin.users.clearFilter')}
          </button>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-lg bg-red-50 p-4 text-red-700">
          {t('superadmin.users.loadError')}
        </div>
      )}

      {/* Table */}
      {usersLoading ? (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size="lg" />
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('superadmin.user')}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('superadmin.tenant')}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('superadmin.role')}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('superadmin.users.businessUnit')}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('common.status')}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('superadmin.created')}
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
                    <span className="text-sm text-gray-900">
                      {user.tenant_name || getTenantName(user.tenant_id)}
                    </span>
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
                        title={t('superadmin.users.editUser')}
                      >
                        <PencilSquareIcon className="h-5 w-5" />
                      </button>
                      <button
                        onClick={() => setDeleteConfirmUser(user)}
                        className="p-1 text-gray-400 hover:text-red-600"
                        title={t('superadmin.users.deactivateUser')}
                      >
                        <TrashIcon className="h-5 w-5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {users?.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              {t('superadmin.users.noUsers')}
            </div>
          )}
        </div>
      )}

      {/* Create User Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/50" onClick={closeCreateModal} />
            <div className="relative bg-white rounded-xl shadow-xl w-full max-w-md p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                {t('superadmin.users.createUserTitle')}
              </h2>
              {createMutation.isError && (
                <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
                  {createMutation.error instanceof Error ? createMutation.error.message : t('superadmin.users.createFailed')}
                </div>
              )}
              <form onSubmit={handleCreateSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('superadmin.tenant')} *
                  </label>
                  <select
                    value={formData.tenant_id}
                    onChange={(e) => setFormData({ ...formData, tenant_id: e.target.value })}
                    className="input"
                    required
                  >
                    <option value="">{t('superadmin.users.selectTenant')}</option>
                    {tenants?.map((tenant) => (
                      <option key={tenant.id} value={tenant.id}>
                        {tenant.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('superadmin.users.username')} *
                  </label>
                  <input
                    type="text"
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value.replace(/\s/g, '') })}
                    className="input"
                    required
                    pattern="^\S+$"
                    title={t('superadmin.users.usernameNoSpaces')}
                    placeholder={t('superadmin.users.usernamePlaceholder')}
                  />
                  <p className="mt-1 text-xs text-gray-500">{t('superadmin.users.usernameHint')}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('superadmin.users.email')} *
                  </label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="input"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('superadmin.role')} *
                  </label>
                  <select
                    value={formData.role}
                    onChange={(e) => setFormData({ ...formData, role: e.target.value as Role })}
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
                    {t('superadmin.users.businessUnit')}
                  </label>
                  <select
                    value={formData.business_unit_id}
                    onChange={(e) => setFormData({ ...formData, business_unit_id: e.target.value })}
                    className="input"
                    disabled={!formData.tenant_id}
                  >
                    <option value="">{t('superadmin.users.noneOption')}</option>
                    {businessUnits
                      .filter((bu) => bu.is_active)
                      .map((bu) => (
                        <option key={bu.id} value={bu.id}>
                          {bu.name}
                        </option>
                      ))}
                  </select>
                  {!formData.tenant_id && (
                    <p className="mt-1 text-xs text-gray-400">{t('superadmin.users.selectTenantFirst')}</p>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('superadmin.users.password')} *
                  </label>
                  <input
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    className="input"
                    required
                    minLength={8}
                  />
                </div>
                <div className="flex justify-end gap-3 pt-4">
                  <button type="button" onClick={closeCreateModal} className="btn-secondary">
                    {t('common.cancel')}
                  </button>
                  <button
                    type="submit"
                    disabled={createMutation.isPending}
                    className="btn-primary"
                  >
                    {createMutation.isPending ? (
                      <LoadingSpinner size="sm" className="border-white border-t-transparent" />
                    ) : (
                      t('superadmin.create')
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Edit User Modal */}
      {editingUser && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/50" onClick={() => setEditingUser(null)} />
            <div className="relative bg-white rounded-xl shadow-xl w-full max-w-md p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-1">
                {t('superadmin.users.editUserTitle')}
              </h2>
              <p className="text-sm text-gray-500 mb-4">
                {editingUser.tenant_name || getTenantName(editingUser.tenant_id)}
              </p>
              {updateMutation.isError && (
                <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
                  {updateMutation.error instanceof Error ? updateMutation.error.message : t('superadmin.users.updateFailed')}
                </div>
              )}
              <form onSubmit={handleEditSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('superadmin.users.email')}
                  </label>
                  <p className="text-sm text-gray-500">{editingUser.email}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('superadmin.users.username')}
                  </label>
                  <input
                    type="text"
                    value={editFormData.username}
                    onChange={(e) => setEditFormData({ ...editFormData, username: e.target.value.replace(/\s/g, '') })}
                    className="input"
                    required
                    pattern="^\S+$"
                    title={t('superadmin.users.usernameNoSpaces')}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('superadmin.users.newPassword')}
                  </label>
                  <input
                    type="password"
                    value={editFormData.new_password}
                    onChange={(e) => setEditFormData({ ...editFormData, new_password: e.target.value })}
                    className="input"
                    placeholder={t('superadmin.users.keepCurrentPlaceholder')}
                    minLength={8}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('superadmin.role')}
                  </label>
                  <select
                    value={editFormData.role}
                    onChange={(e) => setEditFormData({ ...editFormData, role: e.target.value as Role })}
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
                    {t('superadmin.users.businessUnit')}
                  </label>
                  <select
                    value={editFormData.business_unit_id}
                    onChange={(e) => setEditFormData({ ...editFormData, business_unit_id: e.target.value })}
                    className="input"
                  >
                    <option value="">{t('superadmin.users.noneOption')}</option>
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
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={editFormData.is_active}
                      onChange={(e) => setEditFormData({ ...editFormData, is_active: e.target.checked })}
                      className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                    <span className="text-sm font-medium text-gray-700">{t('status.active')}</span>
                  </label>
                </div>
                <div className="flex justify-end gap-3 pt-4">
                  <button type="button" onClick={() => setEditingUser(null)} className="btn-secondary">
                    {t('common.cancel')}
                  </button>
                  <button
                    type="submit"
                    disabled={updateMutation.isPending}
                    className="btn-primary"
                  >
                    {updateMutation.isPending ? (
                      <LoadingSpinner size="sm" className="border-white border-t-transparent" />
                    ) : (
                      t('superadmin.saveChanges')
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirmUser && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/50" onClick={() => setDeleteConfirmUser(null)} />
            <div className="relative bg-white rounded-xl shadow-xl w-full max-w-sm p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-2">
                {t('superadmin.users.deactivateUserTitle')}
              </h2>
              <p className="text-sm text-gray-600 mb-4">
                {t('superadmin.users.deactivateConfirmPrefix')} <strong>{deleteConfirmUser.username}</strong>{t('superadmin.users.deactivateConfirmSuffix')}
              </p>
              {deleteMutation.isError && (
                <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
                  {t('superadmin.users.deactivateFailed')}
                </div>
              )}
              <div className="flex justify-end gap-3">
                <button onClick={() => setDeleteConfirmUser(null)} className="btn-secondary">
                  {t('common.cancel')}
                </button>
                <button
                  onClick={() => deleteMutation.mutate(deleteConfirmUser.id)}
                  disabled={deleteMutation.isPending}
                  className="inline-flex items-center px-4 py-2 rounded-lg text-sm font-medium text-white bg-red-600 hover:bg-red-700 disabled:opacity-50"
                >
                  {deleteMutation.isPending ? (
                    <LoadingSpinner size="sm" className="border-white border-t-transparent" />
                  ) : (
                    t('superadmin.users.deactivate')
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
