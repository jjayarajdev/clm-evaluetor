import { useState } from 'react'
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

const ROLE_LABELS: Record<Role, string> = {
  admin: 'Administrator',
  legal: 'Legal',
  procurement: 'Procurement',
  viewer: 'Viewer',
  super_admin: 'Super Admin',
}

const ROLE_COLORS: Record<Role, string> = {
  admin: 'bg-purple-100 text-purple-700',
  legal: 'bg-blue-100 text-blue-700',
  procurement: 'bg-green-100 text-green-700',
  viewer: 'bg-gray-100 text-gray-700',
  super_admin: 'bg-rose-100 text-rose-700',
}

interface UserFormData {
  tenant_id: string
  username: string
  email: string
  role: Role
  password: string
}

interface EditFormData {
  username: string
  role: Role
  is_active: boolean
  new_password: string
}

export default function GlobalUsersPage() {
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
  })
  const [editFormData, setEditFormData] = useState<EditFormData>({
    username: '',
    role: 'viewer',
    is_active: true,
    new_password: '',
  })

  const { data: users, isLoading: usersLoading, error } = useQuery<UserWithTenant[]>({
    queryKey: ['all-users', tenantFilter],
    queryFn: () => api.getAllUsers(tenantFilter || undefined),
  })

  const { data: tenants } = useQuery<Tenant[]>({
    queryKey: ['tenants-list'],
    queryFn: () => api.getTenants(false),
  })

  const createMutation = useMutation({
    mutationFn: (data: UserFormData) => api.createUserForTenant(data.tenant_id, {
      username: data.username,
      email: data.email,
      password: data.password,
      role: data.role,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['all-users'] })
      closeCreateModal()
    },
  })

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: string; data: EditFormData }) => {
      const { new_password, ...updateData } = data
      await api.updateUser(id, updateData)
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
    })
  }

  const openEditModal = (user: UserWithTenant) => {
    setEditingUser(user)
    setEditFormData({
      username: user.username,
      role: user.role,
      is_active: user.is_active,
      new_password: '',
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
          <h1 className="text-2xl font-bold text-gray-900">All Users</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage users across all tenants
          </p>
        </div>
        <button onClick={openCreateModal} className="btn-primary">
          <PlusIcon className="h-4 w-4 mr-2" />
          Add User
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <FunnelIcon className="h-4 w-4 text-gray-400" />
          <span className="text-sm text-gray-500">Filter by tenant:</span>
        </div>
        <select
          value={tenantFilter}
          onChange={(e) => handleTenantFilterChange(e.target.value)}
          className="input max-w-xs"
        >
          <option value="">All Tenants</option>
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
            Clear filter
          </button>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-lg bg-red-50 p-4 text-red-700">
          Error loading users. Please try again.
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
                  User
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Tenant
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Role
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
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
                      {ROLE_LABELS[user.role]}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                      user.is_active
                        ? 'bg-green-100 text-green-700'
                        : 'bg-red-100 text-red-700'
                    )}>
                      {user.is_active ? 'Active' : 'Inactive'}
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
                        title="Edit user"
                      >
                        <PencilSquareIcon className="h-5 w-5" />
                      </button>
                      <button
                        onClick={() => setDeleteConfirmUser(user)}
                        className="p-1 text-gray-400 hover:text-red-600"
                        title="Deactivate user"
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
              No users found.
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
                Create User
              </h2>
              {createMutation.isError && (
                <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
                  {createMutation.error instanceof Error ? createMutation.error.message : 'Failed to create user. Please try again.'}
                </div>
              )}
              <form onSubmit={handleCreateSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Tenant *
                  </label>
                  <select
                    value={formData.tenant_id}
                    onChange={(e) => setFormData({ ...formData, tenant_id: e.target.value })}
                    className="input"
                    required
                  >
                    <option value="">Select a tenant</option>
                    {tenants?.map((tenant) => (
                      <option key={tenant.id} value={tenant.id}>
                        {tenant.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Username *
                  </label>
                  <input
                    type="text"
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value.replace(/\s/g, '') })}
                    className="input"
                    required
                    pattern="^\S+$"
                    title="Username cannot contain spaces"
                    placeholder="e.g. jjayaraj"
                  />
                  <p className="mt-1 text-xs text-gray-500">No spaces allowed — this is used for login</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email *
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
                    Role *
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
                          {label}
                        </option>
                      ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Password *
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
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={createMutation.isPending}
                    className="btn-primary"
                  >
                    {createMutation.isPending ? (
                      <LoadingSpinner size="sm" className="border-white border-t-transparent" />
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

      {/* Edit User Modal */}
      {editingUser && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/50" onClick={() => setEditingUser(null)} />
            <div className="relative bg-white rounded-xl shadow-xl w-full max-w-md p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-1">
                Edit User
              </h2>
              <p className="text-sm text-gray-500 mb-4">
                {editingUser.tenant_name || getTenantName(editingUser.tenant_id)}
              </p>
              {updateMutation.isError && (
                <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
                  {updateMutation.error instanceof Error ? updateMutation.error.message : 'Failed to update user. Please try again.'}
                </div>
              )}
              <form onSubmit={handleEditSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email
                  </label>
                  <p className="text-sm text-gray-500">{editingUser.email}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Username
                  </label>
                  <input
                    type="text"
                    value={editFormData.username}
                    onChange={(e) => setEditFormData({ ...editFormData, username: e.target.value.replace(/\s/g, '') })}
                    className="input"
                    required
                    pattern="^\S+$"
                    title="Username cannot contain spaces"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    New Password
                  </label>
                  <input
                    type="password"
                    value={editFormData.new_password}
                    onChange={(e) => setEditFormData({ ...editFormData, new_password: e.target.value })}
                    className="input"
                    placeholder="Leave blank to keep current"
                    minLength={8}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Role
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
                          {label}
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
                    <span className="text-sm font-medium text-gray-700">Active</span>
                  </label>
                </div>
                <div className="flex justify-end gap-3 pt-4">
                  <button type="button" onClick={() => setEditingUser(null)} className="btn-secondary">
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={updateMutation.isPending}
                    className="btn-primary"
                  >
                    {updateMutation.isPending ? (
                      <LoadingSpinner size="sm" className="border-white border-t-transparent" />
                    ) : (
                      'Save Changes'
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
                Deactivate User
              </h2>
              <p className="text-sm text-gray-600 mb-4">
                Are you sure you want to deactivate <strong>{deleteConfirmUser.username}</strong>?
                They will no longer be able to log in.
              </p>
              {deleteMutation.isError && (
                <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
                  Failed to deactivate user. Please try again.
                </div>
              )}
              <div className="flex justify-end gap-3">
                <button onClick={() => setDeleteConfirmUser(null)} className="btn-secondary">
                  Cancel
                </button>
                <button
                  onClick={() => deleteMutation.mutate(deleteConfirmUser.id)}
                  disabled={deleteMutation.isPending}
                  className="inline-flex items-center px-4 py-2 rounded-lg text-sm font-medium text-white bg-red-600 hover:bg-red-700 disabled:opacity-50"
                >
                  {deleteMutation.isPending ? (
                    <LoadingSpinner size="sm" className="border-white border-t-transparent" />
                  ) : (
                    'Deactivate'
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
