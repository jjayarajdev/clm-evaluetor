import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  BuildingLibraryIcon,
  UserGroupIcon,
  ShareIcon,
  PlusIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'
import type { OfficerCreate, GovernanceRole, OfficerSide, OrganizationTreeNode } from '@/types/fitgap'

const ROLE_LABELS: Record<GovernanceRole, string> = {
  account_manager: 'Account Manager',
  service_delivery_manager: 'Service Delivery Manager',
  relationship_owner: 'Relationship Owner',
  executive_sponsor: 'Executive Sponsor',
  commercial_manager: 'Commercial Manager',
  technical_lead: 'Technical Lead',
  operations_lead: 'Operations Lead',
  compliance_officer: 'Compliance Officer',
  other: 'Other',
}

const SIDE_LABELS: Record<OfficerSide, string> = {
  internal: 'Internal',
  external: 'External',
}

const SIDE_COLORS: Record<OfficerSide, string> = {
  internal: 'bg-blue-100 text-blue-800',
  external: 'bg-purple-100 text-purple-800',
}

const TABS = ['Overview', 'Officers', 'Hierarchy', 'Relationships'] as const
type Tab = typeof TABS[number]

function TreeNodeComponent({ node, depth = 0 }: { node: OrganizationTreeNode; depth?: number }) {
  const [expanded, setExpanded] = useState(depth < 2)
  const hasChildren = node.children && node.children.length > 0

  return (
    <div>
      <div
        className={cn(
          'flex items-center gap-2 py-2 px-3 rounded-lg hover:bg-gray-50 cursor-pointer',
        )}
        style={{ paddingLeft: `${depth * 24 + 12}px` }}
        onClick={() => hasChildren && setExpanded(!expanded)}
      >
        {hasChildren ? (
          <span className="text-gray-400 text-xs w-4 text-center">{expanded ? '\u25BC' : '\u25B6'}</span>
        ) : (
          <span className="w-4" />
        )}
        <BuildingLibraryIcon className="h-4 w-4 text-violet-500 shrink-0" />
        <span className="text-sm font-medium text-gray-900">{node.name}</span>
        <span className="text-xs text-gray-400 font-mono">{node.code}</span>
        {node.organization_level && (
          <span className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded capitalize">
            {node.organization_level}
          </span>
        )}
      </div>
      {expanded && hasChildren && (
        <div>
          {node.children.map((child) => (
            <TreeNodeComponent key={child.id} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function OrganizationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<Tab>('Overview')
  const [showAddOfficer, setShowAddOfficer] = useState(false)
  const [officerForm, setOfficerForm] = useState<Partial<OfficerCreate>>({ side: 'internal' })

  const { data: org, isLoading } = useQuery({
    queryKey: ['organization', id],
    queryFn: () => api.getOrganization(id!),
    enabled: !!id,
  })

  const { data: officerData } = useQuery({
    queryKey: ['officers', id],
    queryFn: () => api.getOrganizationOfficers(id!),
    enabled: !!id && activeTab === 'Officers',
  })
  const officers = officerData?.items ?? []

  const { data: hierarchy } = useQuery({
    queryKey: ['hierarchy', id],
    queryFn: () => api.getOrganizationHierarchy(id!),
    enabled: !!id && activeTab === 'Hierarchy',
  })

  const { data: tree = [] } = useQuery({
    queryKey: ['org-tree'],
    queryFn: () => api.getOrganizationTree(),
    enabled: activeTab === 'Hierarchy',
  })

  const { data: orgRelationships = [] } = useQuery({
    queryKey: ['org-relationships', id],
    queryFn: async () => {
      const response = await api.getRelationships()
      return response.filter(
        (r) => r.org_a_id === id || r.org_b_id === id
      )
    },
    enabled: !!id && activeTab === 'Relationships',
  })

  const createOfficerMutation = useMutation({
    mutationFn: (data: OfficerCreate) => api.createOfficer(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['officers', id] })
      setShowAddOfficer(false)
      setOfficerForm({ side: 'internal' })
    },
  })

  const deleteOfficerMutation = useMutation({
    mutationFn: (officerId: string) => api.deleteOfficer(id!, officerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['officers', id] })
    },
  })

  if (isLoading || !org) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Link to="/organizations" className="p-2 -ml-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg">
          <ArrowLeftIcon className="h-5 w-5" />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <BuildingLibraryIcon className="h-6 w-6 text-violet-500" />
            <h1 className="text-xl font-bold text-gray-900">{org.name}</h1>
            <span className="text-sm text-gray-400 font-mono">{org.code}</span>
          </div>
          <div className="flex items-center gap-4 mt-2">
            <span className="text-sm text-gray-500 capitalize">{org.org_type}</span>
            {org.industry && <span className="text-sm text-gray-500">{org.industry}</span>}
            {org.region && <span className="text-sm text-gray-500">{org.region}</span>}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-6">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                'pb-3 text-sm font-medium border-b-2 transition-colors',
                activeTab === tab
                  ? 'border-violet-600 text-violet-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              )}
            >
              {tab}
              {tab === 'Officers' && officers.length > 0 && (
                <span className="ml-1.5 bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded text-xs">{officers.length}</span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Overview Tab */}
      {activeTab === 'Overview' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="card">
            <div className="card-header"><h3 className="text-sm font-medium text-gray-900">Details</h3></div>
            <div className="card-body space-y-3">
              <div><p className="text-xs text-gray-500">Type</p><p className="text-sm font-medium capitalize">{org.org_type}</p></div>
              <div><p className="text-xs text-gray-500">Industry</p><p className="text-sm font-medium">{org.industry || '—'}</p></div>
              <div><p className="text-xs text-gray-500">Region</p><p className="text-sm font-medium">{org.region || '—'}</p></div>
              <div><p className="text-xs text-gray-500">Country</p><p className="text-sm font-medium">{org.country || '—'}</p></div>
              <div><p className="text-xs text-gray-500">Website</p><p className="text-sm font-medium">{org.website || '—'}</p></div>
            </div>
          </div>
          <div className="card">
            <div className="card-header"><h3 className="text-sm font-medium text-gray-900">Primary Contact</h3></div>
            <div className="card-body space-y-3">
              <div><p className="text-xs text-gray-500">Name</p><p className="text-sm font-medium">{org.primary_contact_name || '—'}</p></div>
              <div><p className="text-xs text-gray-500">Email</p><p className="text-sm font-medium">{org.primary_contact_email || '—'}</p></div>
              <div><p className="text-xs text-gray-500">Phone</p><p className="text-sm font-medium">{org.primary_contact_phone || '—'}</p></div>
            </div>
          </div>
        </div>
      )}

      {/* Officers Tab */}
      {activeTab === 'Officers' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <UserGroupIcon className="h-5 w-5 text-gray-400" />
              Organization Officers ({officers.length})
            </h2>
            <button onClick={() => setShowAddOfficer(true)} className="btn-primary text-xs flex items-center gap-1">
              <PlusIcon className="h-3.5 w-3.5" /> Add Officer
            </button>
          </div>
          <div className="card">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Title</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Role</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Side</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Contact</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {officers.map((officer) => (
                    <tr key={officer.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-gray-900">{officer.name}</span>
                          {officer.is_primary && (
                            <span className="text-[10px] bg-violet-100 text-violet-700 px-1.5 py-0.5 rounded">Primary</span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">{officer.title || '—'}</td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {officer.governance_role ? ROLE_LABELS[officer.governance_role] || officer.governance_role : '—'}
                      </td>
                      <td className="px-4 py-3">
                        {officer.side ? (
                          <span className={cn('px-2 py-0.5 rounded text-xs font-medium', SIDE_COLORS[officer.side])}>
                            {SIDE_LABELS[officer.side]}
                          </span>
                        ) : '—'}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {officer.email || officer.phone || '—'}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <button
                          onClick={() => deleteOfficerMutation.mutate(officer.id)}
                          className="text-xs text-red-600 hover:text-red-800"
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                  {officers.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-sm text-gray-500">
                        No officers assigned. Add your first officer.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Hierarchy Tab */}
      {activeTab === 'Hierarchy' && (
        <div className="space-y-4">
          {hierarchy && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {hierarchy.parent && (
                <div className="card card-body">
                  <p className="text-xs text-gray-500 mb-1">Parent Organization</p>
                  <Link to={`/organizations/${hierarchy.parent.id}`} className="text-sm font-medium text-violet-600 hover:text-violet-800">
                    {hierarchy.parent.name}
                  </Link>
                  <p className="text-xs text-gray-400 font-mono">{hierarchy.parent.code}</p>
                </div>
              )}
              <div className="card card-body">
                <p className="text-xs text-gray-500 mb-1">Current</p>
                <p className="text-sm font-bold text-gray-900">{hierarchy.organization.name}</p>
                {hierarchy.organization.organization_level && (
                  <p className="text-xs text-gray-400 capitalize">{hierarchy.organization.organization_level}</p>
                )}
              </div>
              <div className="card card-body">
                <p className="text-xs text-gray-500 mb-1">Subsidiaries</p>
                <p className="text-2xl font-bold text-gray-900">{hierarchy.total_subsidiaries}</p>
              </div>
            </div>
          )}

          {hierarchy && hierarchy.subsidiaries.length > 0 && (
            <div className="card">
              <div className="card-header">
                <h3 className="text-sm font-medium text-gray-900">Direct Subsidiaries</h3>
              </div>
              <div className="card-body p-0 divide-y divide-gray-200">
                {hierarchy.subsidiaries.map((sub) => (
                  <Link
                    key={sub.id}
                    to={`/organizations/${sub.id}`}
                    className="flex items-center justify-between px-4 py-3 hover:bg-gray-50"
                  >
                    <div className="flex items-center gap-2">
                      <BuildingLibraryIcon className="h-4 w-4 text-gray-400" />
                      <span className="text-sm font-medium text-gray-900">{sub.name}</span>
                      <span className="text-xs text-gray-400 font-mono">{sub.code}</span>
                    </div>
                    {sub.organization_level && (
                      <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded capitalize">
                        {sub.organization_level}
                      </span>
                    )}
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* Full Tree View */}
          {tree.length > 0 && (
            <div className="card">
              <div className="card-header">
                <h3 className="text-sm font-medium text-gray-900">Organization Tree</h3>
              </div>
              <div className="card-body">
                {tree.map((node) => (
                  <TreeNodeComponent key={node.id} node={node} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Relationships Tab */}
      {activeTab === 'Relationships' && (
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-gray-900 flex items-center gap-2">
              <ShareIcon className="h-5 w-5 text-gray-400" />
              Business Relationships ({orgRelationships.length})
            </h3>
          </div>
          <div className="card-body p-0 divide-y divide-gray-200">
            {orgRelationships.map((rel) => (
              <Link
                key={rel.id}
                to={`/relationships/${rel.id}`}
                className="flex items-center justify-between px-4 py-3 hover:bg-gray-50"
              >
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {rel.org_a?.name || rel.org_a_id} ↔ {rel.org_b?.name || rel.org_b_id}
                  </p>
                  <p className="text-xs text-gray-500 capitalize">{rel.relationship_type} · {rel.governance_tier}</p>
                </div>
                <div className={cn(
                  'flex items-center gap-1 px-2 py-1 rounded-lg text-sm font-semibold',
                  rel.health_score >= 70 ? 'text-green-600 bg-green-50' :
                  rel.health_score >= 40 ? 'text-amber-600 bg-amber-50' :
                  'text-red-600 bg-red-50'
                )}>
                  {rel.health_score}
                </div>
              </Link>
            ))}
            {orgRelationships.length === 0 && (
              <p className="px-4 py-8 text-center text-sm text-gray-500">No relationships for this organization.</p>
            )}
          </div>
        </div>
      )}

      {/* Add Officer Modal */}
      {showAddOfficer && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Add Officer</h2>
              <button onClick={() => setShowAddOfficer(false)} className="text-gray-400 hover:text-gray-600">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                  <input
                    type="text"
                    value={officerForm.name || ''}
                    onChange={(e) => setOfficerForm({ ...officerForm, name: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
                  <input
                    type="text"
                    value={officerForm.title || ''}
                    onChange={(e) => setOfficerForm({ ...officerForm, title: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Governance Role</label>
                  <select
                    value={officerForm.governance_role || ''}
                    onChange={(e) => setOfficerForm({ ...officerForm, governance_role: (e.target.value || undefined) as GovernanceRole | undefined })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
                  >
                    <option value="">Select role</option>
                    {Object.entries(ROLE_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Side</label>
                  <select
                    value={officerForm.side || 'internal'}
                    onChange={(e) => setOfficerForm({ ...officerForm, side: e.target.value as OfficerSide })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
                  >
                    <option value="internal">Internal</option>
                    <option value="external">External</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                  <input
                    type="email"
                    value={officerForm.email || ''}
                    onChange={(e) => setOfficerForm({ ...officerForm, email: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                  <input
                    type="text"
                    value={officerForm.phone || ''}
                    onChange={(e) => setOfficerForm({ ...officerForm, phone: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
                <input
                  type="text"
                  value={officerForm.department || ''}
                  onChange={(e) => setOfficerForm({ ...officerForm, department: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
                />
              </div>
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={officerForm.is_primary || false}
                  onChange={(e) => setOfficerForm({ ...officerForm, is_primary: e.target.checked })}
                  className="rounded border-gray-300 text-violet-600 focus:ring-violet-500"
                />
                Primary Contact
              </label>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowAddOfficer(false)} className="btn-secondary">Cancel</button>
              <button
                onClick={() => {
                  if (officerForm.name) {
                    createOfficerMutation.mutate(officerForm as OfficerCreate)
                  }
                }}
                disabled={!officerForm.name || createOfficerMutation.isPending}
                className="btn-primary"
              >
                {createOfficerMutation.isPending ? 'Adding...' : 'Add Officer'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
