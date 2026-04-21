import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  PlusIcon,
  PencilSquareIcon,
  EyeIcon,
  CheckCircleIcon,
  XCircleIcon,
  BuildingOffice2Icon,
  TrashIcon,
  ExclamationTriangleIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn, formatDate } from '@/lib/utils'
import type { Tenant, TenantCreate, TenantUpdate, TenantPlan } from '@/types'

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

interface TenantFormData {
  name: string
  slug: string
  plan: TenantPlan
  contract_limit: string
  contact_email: string
}

const emptyFormData: TenantFormData = {
  name: '',
  slug: '',
  plan: 'starter',
  contract_limit: '',
  contact_email: '',
}

export default function TenantManagementPage() {
  const queryClient = useQueryClient()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null)
  const [formData, setFormData] = useState<TenantFormData>(emptyFormData)
  const [showInactive, setShowInactive] = useState(false)

  const { data: tenants, isLoading, error } = useQuery({
    queryKey: ['tenants', showInactive],
    queryFn: () => api.getTenants(showInactive),
  })

  // Fetch stats for each tenant to show contract counts
  const { data: tenantStatsMap } = useQuery({
    queryKey: ['tenant-stats-all', tenants?.length],
    queryFn: async () => {
      if (!tenants?.length) return {}
      const results = await Promise.all(
        tenants.map(t =>
          api.getTenantStats(t.id).catch(() => ({ tenant_id: t.id, contract_count: 0, user_count: 0 }))
        )
      )
      const map: Record<string, { contract_count: number; user_count: number }> = {}
      for (const s of results) {
        map[s.tenant_id] = s
      }
      return map
    },
    enabled: !!tenants?.length,
  })

  const createMutation = useMutation({
    mutationFn: (data: TenantCreate) => api.createTenant(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
      closeModal()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: TenantUpdate }) =>
      api.updateTenant(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
      closeModal()
    },
  })

  const activateMutation = useMutation({
    mutationFn: (id: string) => api.activateTenant(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
    },
  })

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => api.deactivateTenant(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
    },
  })

  const [purgingTenant, setPurgingTenant] = useState<Tenant | null>(null)
  const [purgeConfirmText, setPurgeConfirmText] = useState('')
  const [purgeResult, setPurgeResult] = useState<{ tenant: string; deleted: Record<string, number> } | null>(null)

  const purgeMutation = useMutation({
    mutationFn: (id: string) => api.purgeTenant(id),
    onSuccess: (data) => {
      setPurgeResult(data)
      setPurgingTenant(null)
      setPurgeConfirmText('')
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
      queryClient.invalidateQueries({ queryKey: ['tenant-stats-all'] })
    },
  })

  const openCreateModal = () => {
    setEditingTenant(null)
    setFormData(emptyFormData)
    setIsModalOpen(true)
  }

  const openEditModal = (tenant: Tenant) => {
    setEditingTenant(tenant)
    setFormData({
      name: tenant.name,
      slug: tenant.slug,
      plan: tenant.plan,
      contract_limit: tenant.contract_limit?.toString() || '',
      contact_email: tenant.contact_email || '',
    })
    setIsModalOpen(true)
  }

  const closeModal = () => {
    setIsModalOpen(false)
    setEditingTenant(null)
    setFormData(emptyFormData)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const payload = {
      name: formData.name,
      slug: formData.slug,
      plan: formData.plan,
      contract_limit: formData.contract_limit ? parseInt(formData.contract_limit) : null,
      contact_email: formData.contact_email || null,
    }

    if (editingTenant) {
      updateMutation.mutate({ id: editingTenant.id, data: payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  const handleToggleActive = (tenant: Tenant) => {
    const message = tenant.is_active
      ? `Are you sure you want to deactivate "${tenant.name}"? Users will not be able to log in.`
      : `Are you sure you want to activate "${tenant.name}"?`

    if (window.confirm(message)) {
      if (tenant.is_active) {
        deactivateMutation.mutate(tenant.id)
      } else {
        activateMutation.mutate(tenant.id)
      }
    }
  }

  const generateSlug = (name: string) => {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Tenant Management</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage organizations and their subscriptions
          </p>
        </div>
        <button onClick={openCreateModal} className="btn-primary">
          <PlusIcon className="h-4 w-4 mr-2" />
          Add Tenant
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
            className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
          />
          <span className="text-gray-600">Show inactive tenants</span>
        </label>
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-lg bg-red-50 p-4 text-red-700">
          Error loading tenants. Please try again.
        </div>
      )}

      {/* Table */}
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
                  Tenant
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Plan
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Contracts
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
              {tenants?.map((tenant) => (
                <tr key={tenant.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 rounded-full bg-primary-100 flex items-center justify-center">
                        <BuildingOffice2Icon className="h-5 w-5 text-primary-600" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-900">{tenant.name}</p>
                        <p className="text-xs text-gray-500">{tenant.slug}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                      PLAN_COLORS[tenant.plan]
                    )}>
                      {PLAN_LABELS[tenant.plan]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <span className="font-medium text-gray-900">
                      {tenantStatsMap?.[tenant.id]?.contract_count ?? '—'}
                    </span>
                    <span className="text-gray-400"> / {tenant.contract_limit || '∞'}</span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleToggleActive(tenant)}
                      disabled={activateMutation.isPending || deactivateMutation.isPending}
                      className="focus:outline-none"
                    >
                      {tenant.is_active ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700 hover:bg-green-200 transition-colors">
                          <CheckCircleIcon className="h-3 w-3" />
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700 hover:bg-red-200 transition-colors">
                          <XCircleIcon className="h-3 w-3" />
                          Inactive
                        </span>
                      )}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {formatDate(tenant.created_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Link
                        to={`/super-admin/tenants/${tenant.id}`}
                        className="p-1 text-gray-400 hover:text-primary-600"
                        title="View details"
                      >
                        <EyeIcon className="h-5 w-5" />
                      </Link>
                      <button
                        onClick={() => openEditModal(tenant)}
                        className="p-1 text-gray-400 hover:text-gray-600"
                        title="Edit tenant"
                      >
                        <PencilSquareIcon className="h-5 w-5" />
                      </button>
                      <button
                        onClick={() => { setPurgingTenant(tenant); setPurgeConfirmText(''); setPurgeResult(null) }}
                        className="p-1 text-gray-400 hover:text-red-600"
                        title="Permanently delete tenant"
                      >
                        <TrashIcon className="h-5 w-5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {tenants?.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              No tenants found.
            </div>
          )}
        </div>
      )}

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/50" onClick={closeModal} />
            <div className="relative bg-white rounded-xl shadow-xl w-full max-w-md p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                {editingTenant ? 'Edit Tenant' : 'Create Tenant'}
              </h2>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Organization Name *
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => {
                      const name = e.target.value
                      setFormData({
                        ...formData,
                        name,
                        slug: editingTenant ? formData.slug : generateSlug(name),
                      })
                    }}
                    className="input"
                    required
                    placeholder="Acme Corporation"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Slug *
                  </label>
                  <input
                    type="text"
                    value={formData.slug}
                    onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
                    className="input font-mono"
                    required
                    placeholder="acme-corp"
                    pattern="[a-z0-9-]+"
                    title="Only lowercase letters, numbers, and hyphens allowed"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    URL-friendly identifier (lowercase, no spaces)
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Plan *
                  </label>
                  <select
                    value={formData.plan}
                    onChange={(e) => setFormData({ ...formData, plan: e.target.value as TenantPlan })}
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
                    value={formData.contract_limit}
                    onChange={(e) => setFormData({ ...formData, contract_limit: e.target.value })}
                    className="input"
                    placeholder="Leave empty for unlimited"
                    min="1"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Contact Email
                  </label>
                  <input
                    type="email"
                    value={formData.contact_email}
                    onChange={(e) => setFormData({ ...formData, contact_email: e.target.value })}
                    className="input"
                    placeholder="admin@example.com"
                  />
                </div>
                <div className="flex justify-end gap-3 pt-4">
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
                    ) : editingTenant ? (
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

      {/* Purge Confirmation Modal */}
      {purgingTenant && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/50" onClick={() => setPurgingTenant(null)} />
            <div className="relative bg-white rounded-xl shadow-xl w-full max-w-md">
              <div className="p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-10 w-10 rounded-full bg-red-100 flex items-center justify-center">
                    <ExclamationTriangleIcon className="h-6 w-6 text-red-600" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold text-gray-900">Delete Tenant Permanently</h2>
                    <p className="text-sm text-gray-500">This action cannot be undone</p>
                  </div>
                </div>

                <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
                  <p className="text-sm text-red-800">
                    This will permanently delete <strong>{purgingTenant.name}</strong> and all its data:
                  </p>
                  <ul className="mt-2 text-sm text-red-700 space-y-1 list-disc list-inside">
                    <li>All contracts, clauses, obligations, SLAs</li>
                    <li>All users and business units</li>
                    <li>All organizations and relationships</li>
                    <li>All vector embeddings (ChromaDB)</li>
                    <li>All notifications, integrations, settings</li>
                  </ul>
                </div>

                <div className="mb-4">
                  <p className="text-sm text-gray-600 mb-2">
                    {tenantStatsMap?.[purgingTenant.id] && (
                      <span className="font-medium">
                        {tenantStatsMap[purgingTenant.id].contract_count} contracts, {tenantStatsMap[purgingTenant.id].user_count} users will be deleted.
                      </span>
                    )}
                  </p>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Type <span className="font-mono text-red-600">{purgingTenant.slug}</span> to confirm:
                  </label>
                  <input
                    type="text"
                    value={purgeConfirmText}
                    onChange={(e) => setPurgeConfirmText(e.target.value)}
                    className="input font-mono"
                    placeholder={purgingTenant.slug}
                    autoFocus
                  />
                </div>

                <div className="flex justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => setPurgingTenant(null)}
                    className="btn-secondary"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => purgeMutation.mutate(purgingTenant.id)}
                    disabled={purgeConfirmText !== purgingTenant.slug || purgeMutation.isPending}
                    className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {purgeMutation.isPending ? (
                      <div className="flex items-center gap-2">
                        <LoadingSpinner size="sm" className="border-white border-t-transparent" />
                        <span>Deleting...</span>
                      </div>
                    ) : (
                      'Delete Permanently'
                    )}
                  </button>
                </div>

                {purgeMutation.isError && (
                  <div className="mt-3 p-3 bg-red-50 rounded-lg text-sm text-red-700">
                    {(purgeMutation.error as Error)?.message || 'Failed to delete tenant'}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Purge Result Modal */}
      {purgeResult && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/50" onClick={() => setPurgeResult(null)} />
            <div className="relative bg-white rounded-xl shadow-xl w-full max-w-md">
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-green-100 flex items-center justify-center">
                      <CheckCircleIcon className="h-6 w-6 text-green-600" />
                    </div>
                    <h2 className="text-lg font-semibold text-gray-900">Tenant Deleted</h2>
                  </div>
                  <button onClick={() => setPurgeResult(null)} className="p-1 hover:bg-gray-100 rounded">
                    <XMarkIcon className="h-5 w-5 text-gray-500" />
                  </button>
                </div>

                <p className="text-sm text-gray-600 mb-3">
                  <strong>{purgeResult.tenant}</strong> has been permanently deleted.
                </p>

                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs font-medium text-gray-500 uppercase mb-2">Deletion Summary</p>
                  <div className="space-y-1 text-sm">
                    {Object.entries(purgeResult.deleted)
                      .filter(([, count]) => count > 0)
                      .map(([table, count]) => (
                        <div key={table} className="flex justify-between">
                          <span className="text-gray-600">{table.replace(/_/g, ' ')}</span>
                          <span className="font-mono text-gray-900">{count}</span>
                        </div>
                      ))}
                  </div>
                </div>

                <div className="flex justify-end mt-4">
                  <button onClick={() => setPurgeResult(null)} className="btn-primary">
                    Done
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
