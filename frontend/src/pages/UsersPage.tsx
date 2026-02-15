import { useState } from 'react'
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
import type { User } from '@/types'

type UserRole = 'admin' | 'legal' | 'procurement' | 'viewer'

const ROLE_LABELS: Record<UserRole, string> = {
  admin: 'Administrator',
  legal: 'Legal',
  procurement: 'Procurement',
  viewer: 'Viewer',
}

const ROLE_COLORS: Record<UserRole, string> = {
  admin: 'bg-purple-100 text-purple-700',
  legal: 'bg-blue-100 text-blue-700',
  procurement: 'bg-green-100 text-green-700',
  viewer: 'bg-gray-100 text-gray-700',
}

interface UserFormData {
  username: string
  email: string
  role: UserRole
  password?: string
}

export default function UsersPage() {
  const queryClient = useQueryClient()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [formData, setFormData] = useState<UserFormData>({
    email: '',
    username: '',
    role: 'viewer',
    password: '',
  })

  const { data: users, isLoading, error } = useQuery({
    queryKey: ['users'],
    queryFn: () => api.getUsers(),
  })

  // Log error for debugging
  if (error) {
    console.error('Error fetching users:', error)
  }

  const createMutation = useMutation({
    mutationFn: (data: UserFormData) => api.createUser({
      username: data.username,
      email: data.email,
      password: data.password || '',
      role: data.role,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      closeModal()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<UserFormData> }) =>
      api.updateUser(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      closeModal()
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
    setFormData({ email: '', username: '', role: 'viewer', password: '' })
    setIsModalOpen(true)
  }

  const openEditModal = (user: User) => {
    setEditingUser(user)
    setFormData({
      email: user.email,
      username: user.username,
      role: user.role,
      password: '',
    })
    setIsModalOpen(true)
  }

  const closeModal = () => {
    setIsModalOpen(false)
    setEditingUser(null)
    setFormData({ email: '', username: '', role: 'viewer', password: '' })
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (editingUser) {
      const updateData: Partial<UserFormData> = {
        email: formData.email,
        username: formData.username,
        role: formData.role,
      }
      if (formData.password) {
        updateData.password = formData.password
      }
      updateMutation.mutate({ id: editingUser.id, data: updateData })
    } else {
      createMutation.mutate(formData)
    }
  }

  const handleDelete = (user: User) => {
    if (window.confirm(`Are you sure you want to delete ${user.username}?`)) {
      deleteMutation.mutate(user.id)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Users</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage user accounts and permissions
          </p>
        </div>
        <button onClick={openCreateModal} className="btn-primary">
          <PlusIcon className="h-4 w-4 mr-2" />
          Add User
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
                  User
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
                {editingUser ? 'Edit User' : 'Create User'}
              </h2>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Username
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
                    Email
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
                    Role
                  </label>
                  <select
                    value={formData.role}
                    onChange={(e) =>
                      setFormData({ ...formData, role: e.target.value as UserRole })
                    }
                    className="input"
                  >
                    {Object.entries(ROLE_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {editingUser ? 'New Password (leave blank to keep)' : 'Password'}
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
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={createMutation.isPending || updateMutation.isPending}
                    className="btn-primary"
                  >
                    {createMutation.isPending || updateMutation.isPending ? (
                      <LoadingSpinner size="sm" className="border-white border-t-transparent" />
                    ) : editingUser ? (
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
