import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  CubeIcon,
  PlusIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'
import type { ServiceType, ServiceStatus, ServicePortfolioCreate } from '@/types/fitgap'

const SERVICE_TYPE_LABELS: Record<ServiceType, string> = {
  it_services: 'IT Services',
  consulting: 'Consulting',
  legal: 'Legal',
  financial: 'Financial',
  logistics: 'Logistics',
  manufacturing: 'Manufacturing',
  marketing: 'Marketing',
  hr: 'HR',
  procurement: 'Procurement',
  other: 'Other',
}

const STATUS_COLORS: Record<ServiceStatus, string> = {
  active: 'bg-green-100 text-green-800',
  inactive: 'bg-gray-100 text-gray-800',
  planned: 'bg-blue-100 text-blue-800',
  deprecated: 'bg-red-100 text-red-800',
}

const STATUS_LABELS: Record<ServiceStatus, string> = {
  active: 'Active',
  inactive: 'Inactive',
  planned: 'Planned',
  deprecated: 'Deprecated',
}

export default function ServicePortfolioPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [formData, setFormData] = useState<Partial<ServicePortfolioCreate>>({
    service_type: 'it_services',
  })

  const { data: organizations = [] } = useQuery({
    queryKey: ['organizations'],
    queryFn: () => api.getOrganizations({ active_only: true }),
  })

  const { data: portfolioData, isLoading } = useQuery({
    queryKey: ['service-portfolios', typeFilter, statusFilter],
    queryFn: () => api.getServicePortfolios({
      service_type: typeFilter || undefined,
      service_status: statusFilter || undefined,
    }),
  })

  const services = portfolioData?.items ?? []

  const createMutation = useMutation({
    mutationFn: (data: ServicePortfolioCreate) => api.createServicePortfolio(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['service-portfolios'] })
      setShowCreate(false)
      setFormData({ service_type: 'it_services' })
    },
  })

  const filtered = services.filter((svc) =>
    svc.name.toLowerCase().includes(search.toLowerCase()) ||
    svc.code.toLowerCase().includes(search.toLowerCase())
  )

  const handleCreate = () => {
    if (!formData.name || !formData.code || !formData.organization_id || !formData.service_type) return
    createMutation.mutate(formData as ServicePortfolioCreate)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Service Portfolio</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage service offerings across your organization
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="btn-primary flex items-center gap-2"
        >
          <PlusIcon className="h-4 w-4" />
          Add Service
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search services..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 pr-3 py-2 w-full border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
          />
        </div>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
        >
          <option value="">All Types</option>
          {Object.entries(SERVICE_TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
        >
          <option value="">All Statuses</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card card-body text-center">
          <p className="text-2xl font-bold text-gray-900">{services.length}</p>
          <p className="text-xs text-gray-500">Total Services</p>
        </div>
        <div className="card card-body text-center">
          <p className="text-2xl font-bold text-green-600">{services.filter(s => s.status === 'active').length}</p>
          <p className="text-xs text-gray-500">Active</p>
        </div>
        <div className="card card-body text-center">
          <p className="text-2xl font-bold text-blue-600">{services.filter(s => s.status === 'planned').length}</p>
          <p className="text-xs text-gray-500">Planned</p>
        </div>
        <div className="card card-body text-center">
          <p className="text-2xl font-bold text-gray-600">{new Set(services.map(s => s.service_type)).size}</p>
          <p className="text-xs text-gray-500">Service Types</p>
        </div>
      </div>

      {/* Table */}
      <div className="card">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Service</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Code</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Organization</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {filtered.map((svc) => (
                <tr key={svc.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <CubeIcon className="h-5 w-5 text-violet-500" />
                      <div>
                        <p className="text-sm font-medium text-gray-900">{svc.name}</p>
                        {svc.description && (
                          <p className="text-xs text-gray-500 truncate max-w-[250px]">{svc.description}</p>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500 font-mono">{svc.code}</td>
                  <td className="px-4 py-3">
                    <span className="text-sm text-gray-700">
                      {SERVICE_TYPE_LABELS[svc.service_type] || svc.service_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {svc.organization?.name || '—'}
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      'px-2 py-0.5 rounded text-xs font-medium',
                      STATUS_COLORS[svc.status] || 'bg-gray-100 text-gray-800'
                    )}>
                      {STATUS_LABELS[svc.status] || svc.status}
                    </span>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-500">
                    No services found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">New Service</h2>
              <button onClick={() => setShowCreate(false)} className="text-gray-400 hover:text-gray-600">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                  <input
                    type="text"
                    value={formData.name || ''}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Code *</label>
                  <input
                    type="text"
                    value={formData.code || ''}
                    onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
                    placeholder="e.g., IT-CONSULT"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Service Type *</label>
                  <select
                    value={formData.service_type || 'it_services'}
                    onChange={(e) => setFormData({ ...formData, service_type: e.target.value as ServiceType })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
                  >
                    {Object.entries(SERVICE_TYPE_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Organization *</label>
                  <select
                    value={formData.organization_id || ''}
                    onChange={(e) => setFormData({ ...formData, organization_id: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
                  >
                    <option value="">Select organization</option>
                    {organizations.map((org) => (
                      <option key={org.id} value={org.id}>{org.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea
                  value={formData.description || ''}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  rows={2}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowCreate(false)} className="btn-secondary">Cancel</button>
              <button
                onClick={handleCreate}
                disabled={!formData.name || !formData.code || !formData.organization_id || createMutation.isPending}
                className="btn-primary"
              >
                {createMutation.isPending ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
