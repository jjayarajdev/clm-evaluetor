import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  BuildingLibraryIcon,
  PlusIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'
import type { OrganizationCreate, OrgType } from '@/types/governance'

const ORG_TYPE_LABELS: Record<OrgType, string> = {
  customer: 'Customer',
  vendor: 'Vendor',
  partner: 'Partner',
  internal: 'Internal',
}

const ORG_TYPE_COLORS: Record<OrgType, string> = {
  customer: 'bg-blue-100 text-blue-800',
  vendor: 'bg-purple-100 text-purple-800',
  partner: 'bg-green-100 text-green-800',
  internal: 'bg-gray-100 text-gray-800',
}

export default function OrganizationsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>('')
  const [showCreate, setShowCreate] = useState(false)
  const [formData, setFormData] = useState<Partial<OrganizationCreate>>({
    org_type: 'vendor',
  })

  const { data: organizations = [], isLoading } = useQuery({
    queryKey: ['organizations', typeFilter],
    queryFn: () => api.getOrganizations({
      org_type: typeFilter || undefined,
      active_only: true,
    }),
  })

  const createMutation = useMutation({
    mutationFn: (data: OrganizationCreate) => api.createOrganization(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['organizations'] })
      setShowCreate(false)
      setFormData({ org_type: 'vendor' })
    },
  })

  const filtered = organizations.filter((org) =>
    org.name.toLowerCase().includes(search.toLowerCase()) ||
    org.code.toLowerCase().includes(search.toLowerCase())
  )

  const handleCreate = () => {
    if (!formData.name || !formData.code || !formData.org_type) return
    createMutation.mutate(formData as OrganizationCreate)
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
          <h1 className="text-xl font-bold text-gray-900">{t('nav.organizations')}</h1>
          <p className="text-sm text-gray-500 mt-1">
            {t('governance.organizationsSubtitle')}
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="btn-primary flex items-center gap-2"
        >
          <PlusIcon className="h-4 w-4" />
          {t('governance.addOrganization')}
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder={t('governance.searchOrganizations')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 pr-3 py-2 w-full border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
        </div>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
        >
          <option value="">{t('governance.allTypes')}</option>
          {Object.entries(ORG_TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{t(`governance.orgTypes.${value}`, { defaultValue: label })}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="card">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('governance.name')}</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('governance.code')}</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('governance.type')}</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('governance.industry')}</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('governance.region')}</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('governance.primaryContact')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {filtered.map((org) => (
                <tr key={org.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link to={`/organizations/${org.id}`} className="flex items-center gap-2 hover:text-primary-600">
                      <BuildingLibraryIcon className="h-5 w-5 text-gray-400" />
                      <span className="text-sm font-medium text-gray-900 hover:text-primary-600">{org.name}</span>
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">{org.code}</td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      'px-2 py-0.5 rounded text-xs font-medium',
                      ORG_TYPE_COLORS[org.org_type] || 'bg-gray-100 text-gray-800'
                    )}>
                      {t(`governance.orgTypes.${org.org_type}`, { defaultValue: ORG_TYPE_LABELS[org.org_type] || org.org_type })}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">{org.industry || '—'}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{org.region || '—'}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {org.primary_contact_name || '—'}
                    {org.primary_contact_email && (
                      <span className="text-xs text-gray-400 ml-1">({org.primary_contact_email})</span>
                    )}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-sm text-gray-500">
                    {t('governance.noOrganizationsFound')}
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
              <h2 className="text-lg font-semibold text-gray-900">{t('governance.newOrganization')}</h2>
              <button onClick={() => setShowCreate(false)} className="text-gray-400 hover:text-gray-600">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('governance.name')} *</label>
                  <input
                    type="text"
                    value={formData.name || ''}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('governance.code')} *</label>
                  <input
                    type="text"
                    value={formData.code || ''}
                    onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                    placeholder={t('governance.codePlaceholder')}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('governance.type')} *</label>
                  <select
                    value={formData.org_type || 'vendor'}
                    onChange={(e) => setFormData({ ...formData, org_type: e.target.value as OrgType })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                  >
                    {Object.entries(ORG_TYPE_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>{t(`governance.orgTypes.${value}`, { defaultValue: label })}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('governance.industry')}</label>
                  <input
                    type="text"
                    value={formData.industry || ''}
                    onChange={(e) => setFormData({ ...formData, industry: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('governance.region')}</label>
                  <input
                    type="text"
                    value={formData.region || ''}
                    onChange={(e) => setFormData({ ...formData, region: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('governance.country')}</label>
                  <input
                    type="text"
                    value={formData.country || ''}
                    onChange={(e) => setFormData({ ...formData, country: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('governance.primaryContactName')}</label>
                <input
                  type="text"
                  value={formData.primary_contact_name || ''}
                  onChange={(e) => setFormData({ ...formData, primary_contact_name: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('governance.primaryContactEmail')}</label>
                <input
                  type="email"
                  value={formData.primary_contact_email || ''}
                  onChange={(e) => setFormData({ ...formData, primary_contact_email: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowCreate(false)}
                className="btn-secondary"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={handleCreate}
                disabled={!formData.name || !formData.code || createMutation.isPending}
                className="btn-primary"
              >
                {createMutation.isPending ? t('governance.creating') : t('governance.create')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
