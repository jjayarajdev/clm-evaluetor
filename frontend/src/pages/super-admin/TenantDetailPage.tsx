import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  BuildingOffice2Icon,
  UserGroupIcon,
  DocumentTextIcon,
  CurrencyDollarIcon,
  CheckCircleIcon,
  XCircleIcon,
  PencilSquareIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import StatCard from '@/components/ui/StatCard'
import { cn, formatDate, formatCurrency } from '@/lib/utils'
import type { Tenant, TenantStats, TenantUpdate, TenantPlan, User } from '@/types'

type TabType = 'overview' | 'users' | 'settings'

const PLAN_LABELS: Record<TenantPlan, string> = {
  starter: 'Starter',
  professional: 'Professional',
  enterprise: 'Enterprise',
}

const PLAN_COLORS: Record<TenantPlan, string> = {
  starter: 'bg-gray-100 text-gray-700',
  professional: 'bg-blue-100 text-blue-700',
  enterprise: 'bg-purple-100 text-purple-700',
}

const ROLE_COLORS: Record<string, string> = {
  admin: 'bg-purple-100 text-purple-700',
  legal: 'bg-blue-100 text-blue-700',
  procurement: 'bg-green-100 text-green-700',
  viewer: 'bg-gray-100 text-gray-700',
}

export default function TenantDetailPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<TabType>('overview')
  const [isEditing, setIsEditing] = useState(false)
  const [editFormData, setEditFormData] = useState<Partial<TenantUpdate>>({})

  const { data: tenant, isLoading: tenantLoading } = useQuery<Tenant>({
    queryKey: ['tenant', id],
    queryFn: () => api.getTenant(id!),
    enabled: !!id,
  })

  const { data: stats, isLoading: statsLoading } = useQuery<TenantStats>({
    queryKey: ['tenant-stats', id],
    queryFn: () => api.getTenantStats(id!),
    enabled: !!id,
  })

  const { data: users } = useQuery<User[]>({
    queryKey: ['tenant-users', id],
    queryFn: () => api.getTenantUsers(id!),
    enabled: !!id && activeTab === 'users',
  })

  const updateMutation = useMutation({
    mutationFn: (data: TenantUpdate) => api.updateTenant(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant', id] })
      setIsEditing(false)
    },
  })

  const activateMutation = useMutation({
    mutationFn: () => api.activateTenant(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant', id] })
    },
  })

  const deactivateMutation = useMutation({
    mutationFn: () => api.deactivateTenant(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant', id] })
    },
  })

  const isLoading = tenantLoading || statsLoading

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!tenant) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Tenant not found</p>
        <Link to="/super-admin/tenants" className="text-primary-600 hover:text-primary-700 mt-2 inline-block">
          Back to tenants
        </Link>
      </div>
    )
  }

  const handleToggleActive = () => {
    const message = tenant.is_active
      ? `Are you sure you want to deactivate "${tenant.name}"?`
      : `Are you sure you want to activate "${tenant.name}"?`

    if (window.confirm(message)) {
      if (tenant.is_active) {
        deactivateMutation.mutate()
      } else {
        activateMutation.mutate()
      }
    }
  }

  const handleStartEdit = () => {
    setEditFormData({
      name: tenant.name,
      plan: tenant.plan,
      contract_limit: tenant.contract_limit,
      contact_email: tenant.contact_email,
    })
    setIsEditing(true)
  }

  const handleSaveEdit = () => {
    updateMutation.mutate(editFormData)
  }

  const tabs = [
    { id: 'overview' as TabType, name: 'Overview' },
    { id: 'users' as TabType, name: 'Users' },
    { id: 'settings' as TabType, name: 'Settings' },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          to="/super-admin/tenants"
          className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <ArrowLeftIcon className="h-5 w-5 text-gray-500" />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <div className="h-12 w-12 rounded-lg bg-primary-100 flex items-center justify-center">
              <BuildingOffice2Icon className="h-6 w-6 text-primary-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{tenant.name}</h1>
              <p className="text-sm text-gray-500">{tenant.slug}</p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={cn(
            'inline-flex items-center px-3 py-1 rounded-full text-sm font-medium',
            PLAN_COLORS[tenant.plan]
          )}>
            {PLAN_LABELS[tenant.plan]}
          </span>
          <button
            onClick={handleToggleActive}
            disabled={activateMutation.isPending || deactivateMutation.isPending}
            className={cn(
              'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium transition-colors',
              tenant.is_active
                ? 'bg-green-100 text-green-700 hover:bg-green-200'
                : 'bg-red-100 text-red-700 hover:bg-red-200'
            )}
          >
            {tenant.is_active ? (
              <>
                <CheckCircleIcon className="h-4 w-4" />
                Active
              </>
            ) : (
              <>
                <XCircleIcon className="h-4 w-4" />
                Inactive
              </>
            )}
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Users"
          value={stats?.user_count || 0}
          icon={UserGroupIcon}
          color="primary"
        />
        <StatCard
          title="Contracts"
          value={stats?.contract_count || 0}
          icon={DocumentTextIcon}
          color="blue"
        />
        <StatCard
          title="Total Value"
          value={formatCurrency(stats?.total_value || 0)}
          icon={CurrencyDollarIcon}
          color="success"
        />
        <StatCard
          title="Storage Used"
          value={`${((stats?.storage_used_mb || 0) / 1024).toFixed(2)} GB`}
          icon={DocumentTextIcon}
          color="warning"
        />
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-6">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'py-3 text-sm font-medium border-b-2 transition-colors',
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              )}
            >
              {tab.name}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card p-5">
            <h3 className="font-semibold text-gray-900 mb-4">Tenant Information</h3>
            <dl className="space-y-3">
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">Name</dt>
                <dd className="text-sm font-medium text-gray-900">{tenant.name}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">Slug</dt>
                <dd className="text-sm font-mono text-gray-900">{tenant.slug}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">Plan</dt>
                <dd>
                  <span className={cn(
                    'inline-flex px-2 py-0.5 rounded text-xs font-medium',
                    PLAN_COLORS[tenant.plan]
                  )}>
                    {PLAN_LABELS[tenant.plan]}
                  </span>
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">Contract Limit</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {tenant.contract_limit || 'Unlimited'}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">Contact Email</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {tenant.contact_email || '-'}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">Created</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {formatDate(tenant.created_at)}
                </dd>
              </div>
            </dl>
          </div>

          <div className="card p-5">
            <h3 className="font-semibold text-gray-900 mb-4">Quick Actions</h3>
            <div className="space-y-2">
              <Link
                to={`/super-admin/custom-fields?tenant=${id}`}
                className="flex items-center justify-between p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <span className="text-sm font-medium text-gray-700">Configure Custom Fields</span>
                <ArrowLeftIcon className="w-4 h-4 text-gray-400 rotate-180" />
              </Link>
              <button
                onClick={() => setActiveTab('users')}
                className="w-full flex items-center justify-between p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <span className="text-sm font-medium text-gray-700">Manage Users</span>
                <ArrowLeftIcon className="w-4 h-4 text-gray-400 rotate-180" />
              </button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'users' && (
        <div className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">Users ({users?.length || 0})</h3>
            <Link
              to={`/super-admin/users?tenant=${id}`}
              className="text-sm text-primary-600 hover:text-primary-700 font-medium"
            >
              Manage in Global Users
            </Link>
          </div>
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
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {users?.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div>
                      <p className="text-sm font-medium text-gray-900">{user.username}</p>
                      <p className="text-xs text-gray-500">{user.email}</p>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      'inline-flex px-2 py-0.5 rounded text-xs font-medium capitalize',
                      ROLE_COLORS[user.role] || 'bg-gray-100 text-gray-700'
                    )}>
                      {user.role}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      'inline-flex px-2 py-0.5 rounded text-xs font-medium',
                      user.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                    )}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {formatDate(user.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {users?.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              No users found for this tenant.
            </div>
          )}
        </div>
      )}

      {activeTab === 'settings' && (
        <div className="card p-5 max-w-2xl">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900">Tenant Settings</h3>
            {!isEditing && (
              <button
                onClick={handleStartEdit}
                className="btn-secondary text-sm"
              >
                <PencilSquareIcon className="h-4 w-4 mr-1" />
                Edit
              </button>
            )}
          </div>

          {isEditing ? (
            <form
              onSubmit={(e) => {
                e.preventDefault()
                handleSaveEdit()
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Organization Name
                </label>
                <input
                  type="text"
                  value={editFormData.name || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, name: e.target.value })}
                  className="input"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Plan
                </label>
                <select
                  value={editFormData.plan || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, plan: e.target.value as TenantPlan })}
                  className="input"
                >
                  {Object.entries(PLAN_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Contract Limit
                </label>
                <input
                  type="number"
                  value={editFormData.contract_limit || ''}
                  onChange={(e) => setEditFormData({
                    ...editFormData,
                    contract_limit: e.target.value ? parseInt(e.target.value) : null,
                  })}
                  className="input"
                  placeholder="Leave empty for unlimited"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Contact Email
                </label>
                <input
                  type="email"
                  value={editFormData.contact_email || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, contact_email: e.target.value })}
                  className="input"
                />
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  className="btn-secondary"
                >
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
          ) : (
            <dl className="space-y-3">
              <div className="flex justify-between py-2 border-b border-gray-100">
                <dt className="text-sm text-gray-500">Name</dt>
                <dd className="text-sm font-medium text-gray-900">{tenant.name}</dd>
              </div>
              <div className="flex justify-between py-2 border-b border-gray-100">
                <dt className="text-sm text-gray-500">Slug</dt>
                <dd className="text-sm font-mono text-gray-900">{tenant.slug}</dd>
              </div>
              <div className="flex justify-between py-2 border-b border-gray-100">
                <dt className="text-sm text-gray-500">Plan</dt>
                <dd className="text-sm font-medium text-gray-900">{PLAN_LABELS[tenant.plan]}</dd>
              </div>
              <div className="flex justify-between py-2 border-b border-gray-100">
                <dt className="text-sm text-gray-500">Contract Limit</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {tenant.contract_limit || 'Unlimited'}
                </dd>
              </div>
              <div className="flex justify-between py-2">
                <dt className="text-sm text-gray-500">Contact Email</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {tenant.contact_email || '-'}
                </dd>
              </div>
            </dl>
          )}
        </div>
      )}
    </div>
  )
}
