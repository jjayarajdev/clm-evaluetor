import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  BuildingOfficeIcon,
  SwatchIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'
import type { BusinessUnitTree, BusinessUnitCreate, BusinessUnitUpdate } from '@/types/business-unit'

interface FormData {
  name: string
  code: string
  description: string
  parent_id: string
  industry_profile_id: string
  is_active: boolean
}

const emptyFormData: FormData = {
  name: '',
  code: '',
  description: '',
  parent_id: '',
  industry_profile_id: '',
  is_active: true,
}

// Recursive tree node component
function TreeNode({
  node,
  level = 0,
  expandedNodes,
  toggleExpand,
  onEdit,
  onDelete,
  onAddChild,
}: {
  node: BusinessUnitTree
  level?: number
  expandedNodes: Set<string>
  toggleExpand: (id: string) => void
  onEdit: (id: string) => void
  onDelete: (id: string) => void
  onAddChild: (parentId: string) => void
}) {
  const hasChildren = node.children && node.children.length > 0
  const isExpanded = expandedNodes.has(node.id)

  return (
    <div className="select-none">
      <div
        className={cn(
          'flex items-center gap-2 py-2 px-3 rounded-lg hover:bg-gray-50 group transition-colors',
          level > 0 && 'ml-6 border-l-2 border-gray-200'
        )}
      >
        {/* Expand/collapse button */}
        <button
          onClick={() => hasChildren && toggleExpand(node.id)}
          className={cn(
            'w-5 h-5 flex items-center justify-center rounded hover:bg-gray-200',
            !hasChildren && 'invisible'
          )}
        >
          {hasChildren && (
            isExpanded ? (
              <ChevronDownIcon className="w-4 h-4 text-gray-500" />
            ) : (
              <ChevronRightIcon className="w-4 h-4 text-gray-500" />
            )
          )}
        </button>

        {/* Icon */}
        <BuildingOfficeIcon className={cn(
          'w-5 h-5',
          node.is_active ? 'text-primary-500' : 'text-gray-400'
        )} />

        {/* Name and code */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={cn(
              'font-medium',
              !node.is_active && 'text-gray-400 line-through'
            )}>
              {node.name}
            </span>
            <span className="text-xs text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
              {node.code}
            </span>
            {!node.is_active && (
              <span className="text-xs text-red-500 bg-red-50 px-1.5 py-0.5 rounded">
                Inactive
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            {node.description && (
              <p className="text-sm text-gray-500 truncate">{node.description}</p>
            )}
            {node.effective_profile_name && (
              <span className={cn(
                'text-xs px-1.5 py-0.5 rounded inline-flex items-center gap-1',
                node.industry_profile_id
                  ? 'bg-violet-50 text-violet-700 border border-violet-200'
                  : 'bg-gray-50 text-gray-500 border border-gray-200'
              )}>
                <SwatchIcon className="w-3 h-3" />
                {node.effective_profile_name}
                {!node.industry_profile_id && (
                  <span className="text-gray-400">(inherited)</span>
                )}
              </span>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={() => onAddChild(node.id)}
            className="p-1.5 rounded hover:bg-primary-100 text-gray-400 hover:text-primary-600"
            title="Add child unit"
          >
            <PlusIcon className="w-4 h-4" />
          </button>
          <button
            onClick={() => onEdit(node.id)}
            className="p-1.5 rounded hover:bg-blue-100 text-gray-400 hover:text-blue-600"
            title="Edit"
          >
            <PencilSquareIcon className="w-4 h-4" />
          </button>
          <button
            onClick={() => onDelete(node.id)}
            className="p-1.5 rounded hover:bg-red-100 text-gray-400 hover:text-red-600"
            title="Delete"
          >
            <TrashIcon className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Children */}
      {hasChildren && isExpanded && (
        <div className="mt-1">
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              level={level + 1}
              expandedNodes={expandedNodes}
              toggleExpand={toggleExpand}
              onEdit={onEdit}
              onDelete={onDelete}
              onAddChild={onAddChild}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default function BusinessUnitsPage() {
  const queryClient = useQueryClient()
  const { isSuperAdmin } = useAuth()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [formData, setFormData] = useState<FormData>(emptyFormData)
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())
  const [selectedTenantId, setSelectedTenantId] = useState<string>('')

  // Fetch tenants for super admin
  const { data: tenants } = useQuery({
    queryKey: ['tenants'],
    queryFn: () => api.getTenants(true),
    enabled: isSuperAdmin,
  })

  // Fetch industry profiles for the dropdown
  const { data: profiles } = useQuery({
    queryKey: ['industry-profiles'],
    queryFn: () => api.getIndustryProfiles(),
  })

  // Auto-select first tenant for super admin
  useEffect(() => {
    if (isSuperAdmin && tenants && tenants.length > 0 && !selectedTenantId) {
      setSelectedTenantId(tenants[0].id)
    }
  }, [isSuperAdmin, tenants, selectedTenantId])

  // Get effective tenant ID (for super admin, use selected; otherwise use user's tenant)
  const effectiveTenantId = isSuperAdmin ? selectedTenantId : undefined

  // Fetch tree data
  const { data: treeData, isLoading, error } = useQuery({
    queryKey: ['business-units-tree', effectiveTenantId],
    queryFn: () => api.getBusinessUnitsTree(effectiveTenantId),
    enabled: !isSuperAdmin || !!selectedTenantId,
  })

  // Fetch flat list for parent dropdown
  const { data: listData } = useQuery({
    queryKey: ['business-units-list', effectiveTenantId],
    queryFn: () => api.getBusinessUnits({ page_size: 100 }, effectiveTenantId),
    enabled: !isSuperAdmin || !!selectedTenantId,
  })

  const createMutation = useMutation({
    mutationFn: (data: BusinessUnitCreate) => api.createBusinessUnit(data, effectiveTenantId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['business-units-tree', effectiveTenantId] })
      queryClient.invalidateQueries({ queryKey: ['business-units-list', effectiveTenantId] })
      closeModal()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: BusinessUnitUpdate }) =>
      api.updateBusinessUnit(id, data, effectiveTenantId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['business-units-tree', effectiveTenantId] })
      queryClient.invalidateQueries({ queryKey: ['business-units-list', effectiveTenantId] })
      closeModal()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteBusinessUnit(id, effectiveTenantId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['business-units-tree', effectiveTenantId] })
      queryClient.invalidateQueries({ queryKey: ['business-units-list', effectiveTenantId] })
    },
  })

  const profileMutation = useMutation({
    mutationFn: ({ buId, profileId }: { buId: string; profileId: string | null }) =>
      api.assignBuProfile(buId, profileId, effectiveTenantId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['business-units-tree', effectiveTenantId] })
      queryClient.invalidateQueries({ queryKey: ['business-units-list', effectiveTenantId] })
    },
  })

  const toggleExpand = (id: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const expandAll = () => {
    const allIds = new Set<string>()
    const collectIds = (nodes: BusinessUnitTree[]) => {
      nodes.forEach((node) => {
        allIds.add(node.id)
        if (node.children) collectIds(node.children)
      })
    }
    if (treeData) collectIds(treeData)
    setExpandedNodes(allIds)
  }

  const collapseAll = () => {
    setExpandedNodes(new Set())
  }

  const openCreateModal = (parentId?: string) => {
    setEditingId(null)
    setFormData({
      ...emptyFormData,
      parent_id: parentId || '',
    })
    setIsModalOpen(true)
  }

  const openEditModal = async (id: string) => {
    try {
      const bu = await api.getBusinessUnit(id, effectiveTenantId)
      setEditingId(id)
      setFormData({
        name: bu.name,
        code: bu.code,
        description: bu.description || '',
        parent_id: bu.parent_id || '',
        industry_profile_id: bu.industry_profile_id || '',
        is_active: bu.is_active,
      })
      setIsModalOpen(true)
    } catch (err) {
      console.error('Failed to fetch business unit:', err)
    }
  }

  const closeModal = () => {
    setIsModalOpen(false)
    setEditingId(null)
    setFormData(emptyFormData)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    const submitData = {
      name: formData.name,
      code: formData.code,
      description: formData.description || undefined,
      parent_id: formData.parent_id || undefined,
      industry_profile_id: formData.industry_profile_id || undefined,
    }

    if (editingId) {
      updateMutation.mutate({
        id: editingId,
        data: {
          ...submitData,
          is_active: formData.is_active,
        },
      })
      // If profile changed, also call the profile assignment endpoint
      if (formData.industry_profile_id !== '') {
        profileMutation.mutate({
          buId: editingId,
          profileId: formData.industry_profile_id || null,
        })
      }
    } else {
      createMutation.mutate(submitData)
    }
  }

  const handleDelete = (id: string) => {
    if (confirm('Are you sure you want to deactivate this business unit? This will also affect any users assigned to it.')) {
      deleteMutation.mutate(id)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-700">Failed to load business units. Please try again.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Business Units</h1>
          <p className="text-gray-500 mt-1">
            Manage organizational structure, department hierarchy, and industry profile assignments
          </p>
        </div>
        <button
          onClick={() => openCreateModal()}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          disabled={isSuperAdmin && !selectedTenantId}
        >
          <PlusIcon className="w-5 h-5" />
          Add Business Unit
        </button>
      </div>

      {/* Tenant selector for super admin */}
      {isSuperAdmin && (
        <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <label className="block text-sm font-medium text-amber-800 mb-2">
            Select Tenant to Manage
          </label>
          <select
            value={selectedTenantId}
            onChange={(e) => setSelectedTenantId(e.target.value)}
            className="w-full max-w-md px-3 py-2 border border-amber-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-amber-500 bg-white"
          >
            <option value="">Select a tenant...</option>
            {tenants?.map((tenant) => (
              <option key={tenant.id} value={tenant.id}>
                {tenant.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Tree controls */}
      <div className="flex items-center gap-2 mb-4">
        <button
          onClick={expandAll}
          className="text-sm text-gray-600 hover:text-gray-900 px-2 py-1 rounded hover:bg-gray-100"
        >
          Expand All
        </button>
        <span className="text-gray-300">|</span>
        <button
          onClick={collapseAll}
          className="text-sm text-gray-600 hover:text-gray-900 px-2 py-1 rounded hover:bg-gray-100"
        >
          Collapse All
        </button>
      </div>

      {/* Tree view */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        {!treeData || treeData.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <BuildingOfficeIcon className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p className="text-lg font-medium">No business units yet</p>
            <p className="mt-1">Create your first business unit to get started.</p>
          </div>
        ) : (
          <div className="space-y-1">
            {treeData.map((node) => (
              <TreeNode
                key={node.id}
                node={node}
                expandedNodes={expandedNodes}
                toggleExpand={toggleExpand}
                onEdit={openEditModal}
                onDelete={handleDelete}
                onAddChild={openCreateModal}
              />
            ))}
          </div>
        )}
      </div>

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b">
              <h2 className="text-xl font-semibold">
                {editingId ? 'Edit Business Unit' : 'Create Business Unit'}
              </h2>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Name *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="e.g., Sales Department"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Code *
                </label>
                <input
                  type="text"
                  value={formData.code}
                  onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 uppercase"
                  placeholder="e.g., SALES"
                  maxLength={20}
                  required
                />
                <p className="mt-1 text-xs text-gray-500">Unique identifier code (max 20 chars)</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="Optional description..."
                  rows={2}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Parent Unit
                </label>
                <select
                  value={formData.parent_id}
                  onChange={(e) => setFormData({ ...formData, parent_id: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                >
                  <option value="">None (Top Level)</option>
                  {listData?.items
                    .filter((bu) => bu.id !== editingId)
                    .map((bu) => (
                      <option key={bu.id} value={bu.id}>
                        {bu.name} ({bu.code})
                      </option>
                    ))}
                </select>
              </div>

              {/* Industry Profile Assignment */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  <span className="flex items-center gap-1.5">
                    <SwatchIcon className="w-4 h-4 text-violet-500" />
                    Industry Profile
                  </span>
                </label>
                <select
                  value={formData.industry_profile_id}
                  onChange={(e) => setFormData({ ...formData, industry_profile_id: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                >
                  <option value="">Inherit from Tenant (default)</option>
                  {profiles?.map((profile: { id: string; name: string; slug: string }) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.name}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-gray-500">
                  Override the tenant's default profile for this BU. Contracts in this BU will use this profile for taxonomy and extraction.
                </p>
              </div>

              {editingId && (
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="is_active"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    className="rounded text-primary-600 focus:ring-primary-500"
                  />
                  <label htmlFor="is_active" className="text-sm text-gray-700">
                    Active
                  </label>
                </div>
              )}

              <div className="flex justify-end gap-3 pt-4 border-t">
                <button
                  type="button"
                  onClick={closeModal}
                  className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending || updateMutation.isPending}
                  className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
                >
                  {createMutation.isPending || updateMutation.isPending
                    ? 'Saving...'
                    : editingId
                    ? 'Update'
                    : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
