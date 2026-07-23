import { useState } from 'react'
import { useTranslation } from 'react-i18next'
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
  ShieldCheckIcon,
  EyeIcon,
  EyeSlashIcon,
  ArrowPathIcon,
  SignalIcon,
  ExclamationTriangleIcon,
  PlusIcon,
  TrashIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import { client } from '@/lib/api/client'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import StatCard from '@/components/ui/StatCard'
import { cn, formatDate, formatDateTime, formatCurrency } from '@/lib/utils'
import type { Tenant, TenantStats, TenantUpdate, TenantPlan, User } from '@/types'

type TabType = 'overview' | 'users' | 'settings' | 'sso'

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
  const { t } = useTranslation()
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
        <p className="text-gray-500">{t('superadmin.tenantDetail.notFound')}</p>
        <Link to="/super-admin/tenants" className="text-primary-600 hover:text-primary-700 mt-2 inline-block">
          {t('superadmin.tenantDetail.backToTenants')}
        </Link>
      </div>
    )
  }

  const handleToggleActive = () => {
    const message = tenant.is_active
      ? t('superadmin.tenants.deactivateConfirmShort', { name: tenant.name })
      : t('superadmin.tenants.activateConfirm', { name: tenant.name })

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
    { id: 'overview' as TabType, name: t('superadmin.tenantDetail.tabOverview') },
    { id: 'users' as TabType, name: t('superadmin.tenantDetail.tabUsers') },
    { id: 'sso' as TabType, name: t('superadmin.tenantDetail.tabSso') },
    { id: 'settings' as TabType, name: t('superadmin.tenantDetail.tabSettings') },
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
            {t(`superadmin.plans.${tenant.plan}`, { defaultValue: PLAN_LABELS[tenant.plan] })}
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
                {t('status.active')}
              </>
            ) : (
              <>
                <XCircleIcon className="h-4 w-4" />
                {t('status.inactive')}
              </>
            )}
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title={t('superadmin.tenantDetail.users')}
          value={stats?.user_count || 0}
          icon={UserGroupIcon}
          color="primary"
        />
        <StatCard
          title={t('superadmin.tenants.contracts')}
          value={stats?.contract_count || 0}
          icon={DocumentTextIcon}
          color="blue"
        />
        <StatCard
          title={t('superadmin.tenantDetail.totalValue')}
          value={formatCurrency(stats?.total_value || 0)}
          icon={CurrencyDollarIcon}
          color="success"
        />
        <StatCard
          title={t('superadmin.tenantDetail.storageUsed')}
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
            <h3 className="font-semibold text-gray-900 mb-4">{t('superadmin.tenantDetail.tenantInformation')}</h3>
            <dl className="space-y-3">
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">{t('superadmin.tenantDetail.name')}</dt>
                <dd className="text-sm font-medium text-gray-900">{tenant.name}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">{t('superadmin.tenants.slug')}</dt>
                <dd className="text-sm font-mono text-gray-900">{tenant.slug}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">{t('superadmin.plan')}</dt>
                <dd>
                  <span className={cn(
                    'inline-flex px-2 py-0.5 rounded text-xs font-medium',
                    PLAN_COLORS[tenant.plan]
                  )}>
                    {t(`superadmin.plans.${tenant.plan}`, { defaultValue: PLAN_LABELS[tenant.plan] })}
                  </span>
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">{t('superadmin.contractLimit')}</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {tenant.contract_limit || t('superadmin.tenantDetail.unlimited')}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">{t('superadmin.contactEmail')}</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {tenant.contact_email || '-'}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">{t('superadmin.created')}</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {formatDate(tenant.created_at)}
                </dd>
              </div>
            </dl>
          </div>

          <div className="card p-5">
            <h3 className="font-semibold text-gray-900 mb-4">{t('superadmin.quickActions')}</h3>
            <div className="space-y-2">
              <Link
                to={`/super-admin/custom-fields?tenant=${id}`}
                className="flex items-center justify-between p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <span className="text-sm font-medium text-gray-700">{t('superadmin.configureCustomFields')}</span>
                <ArrowLeftIcon className="w-4 h-4 text-gray-400 rotate-180" />
              </Link>
              <button
                onClick={() => setActiveTab('users')}
                className="w-full flex items-center justify-between p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <span className="text-sm font-medium text-gray-700">{t('superadmin.tenantDetail.manageUsers')}</span>
                <ArrowLeftIcon className="w-4 h-4 text-gray-400 rotate-180" />
              </button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'users' && (
        <div className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">{t('superadmin.tenantDetail.usersCount', { count: users?.length || 0 })}</h3>
            <Link
              to={`/super-admin/users?tenant=${id}`}
              className="text-sm text-primary-600 hover:text-primary-700 font-medium"
            >
              {t('superadmin.tenantDetail.manageInGlobalUsers')}
            </Link>
          </div>
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('superadmin.user')}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('superadmin.role')}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('common.status')}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('superadmin.created')}
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
                      {t(`roles.${user.role}`, { defaultValue: user.role })}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      'inline-flex px-2 py-0.5 rounded text-xs font-medium',
                      user.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                    )}>
                      {user.is_active ? t('status.active') : t('status.inactive')}
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
              {t('superadmin.tenantDetail.noUsersForTenant')}
            </div>
          )}
        </div>
      )}

      {activeTab === 'sso' && tenant && (
        <TenantSSOConfig tenantId={id!} tenantSlug={tenant.slug} />
      )}

      {activeTab === 'settings' && (
        <div className="card p-5 max-w-2xl">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900">{t('superadmin.tenantDetail.tenantSettings')}</h3>
            {!isEditing && (
              <button
                onClick={handleStartEdit}
                className="btn-secondary text-sm"
              >
                <PencilSquareIcon className="h-4 w-4 mr-1" />
                {t('common.edit')}
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
                  {t('superadmin.tenants.organizationName')}
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
                  {t('superadmin.plan')}
                </label>
                <select
                  value={editFormData.plan || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, plan: e.target.value as TenantPlan })}
                  className="input"
                >
                  {Object.entries(PLAN_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {t(`superadmin.plans.${value}`, { defaultValue: label })}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('superadmin.contractLimit')}
                </label>
                <input
                  type="number"
                  value={editFormData.contract_limit || ''}
                  onChange={(e) => setEditFormData({
                    ...editFormData,
                    contract_limit: e.target.value ? parseInt(e.target.value) : null,
                  })}
                  className="input"
                  placeholder={t('superadmin.unlimitedPlaceholder')}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('superadmin.contactEmail')}
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
          ) : (
            <dl className="space-y-3">
              <div className="flex justify-between py-2 border-b border-gray-100">
                <dt className="text-sm text-gray-500">{t('superadmin.tenantDetail.name')}</dt>
                <dd className="text-sm font-medium text-gray-900">{tenant.name}</dd>
              </div>
              <div className="flex justify-between py-2 border-b border-gray-100">
                <dt className="text-sm text-gray-500">{t('superadmin.tenants.slug')}</dt>
                <dd className="text-sm font-mono text-gray-900">{tenant.slug}</dd>
              </div>
              <div className="flex justify-between py-2 border-b border-gray-100">
                <dt className="text-sm text-gray-500">{t('superadmin.plan')}</dt>
                <dd className="text-sm font-medium text-gray-900">{t(`superadmin.plans.${tenant.plan}`, { defaultValue: PLAN_LABELS[tenant.plan] })}</dd>
              </div>
              <div className="flex justify-between py-2 border-b border-gray-100">
                <dt className="text-sm text-gray-500">{t('superadmin.contractLimit')}</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {tenant.contract_limit || t('superadmin.tenantDetail.unlimited')}
                </dd>
              </div>
              <div className="flex justify-between py-2">
                <dt className="text-sm text-gray-500">{t('superadmin.contactEmail')}</dt>
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

// ── SSO Config Component (embedded in tenant detail) ─────────────────

interface SSOConfig {
  id: string
  name: string
  provider: string
  issuer_url: string
  client_id: string
  scopes: string[]
  default_role: string
  auto_provision: boolean
  role_mapping: Record<string, string> | null
  is_active: boolean
  health_status: string
  last_health_check: string | null
  tenant_slug: string | null
  created_at: string | null
}

interface RoleMappingRow {
  idp_group: string
  app_role: string
}

interface SSOFormData {
  name: string
  provider: string
  issuer_url: string
  client_id: string
  client_secret: string
  scopes: string
  default_role: string
  auto_provision: boolean
  role_mappings: RoleMappingRow[]
}

const SSO_PROVIDERS = [
  { value: 'azure_ad', label: 'Microsoft Entra ID (Azure AD)' },
  { value: 'okta', label: 'Okta' },
  { value: 'google', label: 'Google Workspace' },
  { value: 'auth0', label: 'Auth0' },
  { value: 'generic', label: 'Generic OIDC' },
]

const SSO_ROLES = [
  { value: 'admin', label: 'Admin' },
  { value: 'legal', label: 'Legal' },
  { value: 'procurement', label: 'Procurement' },
  { value: 'bu_head', label: 'BU Head' },
]

const HEALTH_DISPLAY: Record<string, { color: string; icon: typeof CheckCircleIcon; label: string }> = {
  healthy: { color: 'bg-green-100 text-green-700', icon: CheckCircleIcon, label: 'Connected' },
  degraded: { color: 'bg-yellow-100 text-yellow-700', icon: ExclamationTriangleIcon, label: 'Degraded' },
  unhealthy: { color: 'bg-red-100 text-red-700', icon: XCircleIcon, label: 'Unhealthy' },
  unknown: { color: 'bg-gray-100 text-gray-600', icon: SignalIcon, label: 'Not Tested' },
}

const emptySSOForm: SSOFormData = {
  name: 'SSO',
  provider: 'azure_ad',
  issuer_url: '',
  client_id: '',
  client_secret: '',
  scopes: 'openid email profile',
  default_role: 'legal',
  auto_provision: true,
  role_mappings: [],
}

function ssoApi(tenantId: string) {
  const qs = `?for_tenant_id=${tenantId}`
  return {
    getConfig: async (): Promise<SSOConfig | null> => {
      const r = await client.get(`/auth/sso/config${qs}`)
      return r.data
    },
    saveConfig: async (data: SSOFormData): Promise<SSOConfig> => {
      let role_mapping: Record<string, string> | null = null
      const validMappings = data.role_mappings.filter((m) => m.idp_group.trim())
      if (validMappings.length > 0) {
        role_mapping = {}
        for (const m of validMappings) {
          role_mapping[m.idp_group.trim()] = m.app_role
        }
      }
      const r = await client.post(`/auth/sso/config${qs}`, {
        name: data.name,
        provider: data.provider,
        issuer_url: data.issuer_url,
        client_id: data.client_id,
        client_secret: data.client_secret,
        scopes: data.scopes.split(/\s+/).filter(Boolean),
        default_role: data.default_role,
        auto_provision: data.auto_provision,
        role_mapping,
      })
      return r.data
    },
    testConfig: async (): Promise<{ healthy: boolean; message: string }> => {
      const r = await client.post(`/auth/sso/config/test${qs}`)
      return r.data
    },
    deleteConfig: async (): Promise<void> => {
      await client.delete(`/auth/sso/config${qs}`)
    },
  }
}

function ProviderHint({ provider }: { provider: string }) {
  const { t } = useTranslation()
  const hints: Record<string, string> = {
    azure_ad: 'https://login.microsoftonline.com/{tenant-id}/v2.0',
    okta: 'https://{your-domain}.okta.com/oauth2/default',
    google: 'https://accounts.google.com',
    auth0: 'https://{your-domain}.auth0.com/',
    generic: 'https://your-idp.example.com',
  }
  return (
    <p className="mt-1 text-xs text-gray-400">
      {t('superadmin.sso.exampleLabel')} <span className="font-mono">{hints[provider] || hints.generic}</span>
    </p>
  )
}

function TenantSSOConfig({ tenantId, tenantSlug }: { tenantId: string; tenantSlug: string }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const api = ssoApi(tenantId)
  const [isEditing, setIsEditing] = useState(false)
  const [form, setForm] = useState<SSOFormData>(emptySSOForm)
  const [showSecret, setShowSecret] = useState(false)
  const [testResult, setTestResult] = useState<{ healthy: boolean; message: string } | null>(null)

  const { data: config, isLoading } = useQuery({
    queryKey: ['sso-config', tenantId],
    queryFn: api.getConfig,
  })

  const saveMutation = useMutation({
    mutationFn: api.saveConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sso-config', tenantId] })
      setIsEditing(false)
      setTestResult(null)
    },
  })

  const testMutation = useMutation({
    mutationFn: api.testConfig,
    onSuccess: (data) => {
      setTestResult(data)
      queryClient.invalidateQueries({ queryKey: ['sso-config', tenantId] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: api.deleteConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sso-config', tenantId] })
      setIsEditing(false)
    },
  })

  const startEditing = () => {
    if (config) {
      setForm({
        name: config.name,
        provider: config.provider,
        issuer_url: config.issuer_url,
        client_id: config.client_id,
        client_secret: '',
        scopes: config.scopes.join(' '),
        default_role: config.default_role,
        auto_provision: config.auto_provision,
        role_mappings: config.role_mapping
          ? Object.entries(config.role_mapping).map(([idp_group, app_role]) => ({ idp_group, app_role }))
          : [],
      })
    } else {
      setForm(emptySSOForm)
    }
    setIsEditing(true)
    setTestResult(null)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    saveMutation.mutate(form)
  }

  if (isLoading) {
    return <div className="flex items-center justify-center h-32"><LoadingSpinner size="lg" /></div>
  }

  const health = HEALTH_DISPLAY[config?.health_status || 'unknown'] || HEALTH_DISPLAY.unknown
  const HealthIcon = health.icon

  // ── Display existing config ──
  if (config && !isEditing) {
    return (
      <div className="card p-6 space-y-6 max-w-3xl">
        <div className="flex items-center justify-between pb-4 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-primary-100 flex items-center justify-center">
              <ShieldCheckIcon className="h-5 w-5 text-primary-600" />
            </div>
            <div>
              <p className="font-semibold text-gray-900">{config.name}</p>
              <p className="text-xs text-gray-500">
                {t(`superadmin.sso.providers.${config.provider}`, { defaultValue: SSO_PROVIDERS.find((p) => p.value === config.provider)?.label || config.provider })}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={cn('inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium', health.color)}>
              <HealthIcon className="h-4 w-4" />
              {t(`superadmin.sso.health.${config?.health_status || 'unknown'}`, { defaultValue: health.label })}
            </span>
            <button onClick={() => testMutation.mutate()} disabled={testMutation.isPending} className="btn-secondary text-sm">
              {testMutation.isPending ? <LoadingSpinner size="sm" /> : <ArrowPathIcon className="h-4 w-4" />}
              {t('integrations.test')}
            </button>
            <button onClick={startEditing} className="btn-secondary text-sm">{t('common.edit')}</button>
            <button
              onClick={() => { if (confirm(t('superadmin.sso.disableConfirm'))) deleteMutation.mutate() }}
              className="btn-secondary text-sm text-red-600 hover:text-red-700"
            >
              {t('superadmin.sso.disable')}
            </button>
          </div>
        </div>

        {testResult && (
          <div className={cn('rounded-lg p-4 text-sm', testResult.healthy ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800')}>
            <div className="flex items-center gap-2">
              {testResult.healthy ? <CheckCircleIcon className="h-5 w-5" /> : <XCircleIcon className="h-5 w-5" />}
              <span className="font-medium">{testResult.healthy ? t('superadmin.sso.connectionSuccessful') : t('superadmin.sso.connectionFailed')}</span>
            </div>
            <p className="mt-1 ml-7">{testResult.message}</p>
          </div>
        )}

        <div className="grid grid-cols-2 gap-x-8 gap-y-4 text-sm">
          <div>
            <p className="text-gray-500">{t('superadmin.sso.issuerUrl')}</p>
            <p className="font-mono text-gray-900 truncate">{config.issuer_url}</p>
          </div>
          <div>
            <p className="text-gray-500">{t('superadmin.sso.clientId')}</p>
            <p className="font-mono text-gray-900 truncate">{config.client_id}</p>
          </div>
          <div>
            <p className="text-gray-500">{t('superadmin.sso.scopes')}</p>
            <p className="text-gray-900">{config.scopes.join(', ')}</p>
          </div>
          <div>
            <p className="text-gray-500">{t('superadmin.sso.defaultRole')}</p>
            <p className="text-gray-900 capitalize">{t(`roles.${config.default_role}`, { defaultValue: config.default_role })}</p>
          </div>
          <div>
            <p className="text-gray-500">{t('superadmin.sso.autoProvisionUsers')}</p>
            <p className="text-gray-900">{config.auto_provision ? t('superadmin.sso.enabled') : t('superadmin.sso.disabled')}</p>
          </div>
          <div>
            <p className="text-gray-500">{t('superadmin.sso.lastHealthCheck')}</p>
            <p className="text-gray-900">{config.last_health_check ? formatDateTime(config.last_health_check) : t('integrations.never')}</p>
          </div>
          {config.role_mapping && Object.keys(config.role_mapping).length > 0 && (
            <div className="col-span-2">
              <p className="text-gray-500 mb-2">{t('superadmin.sso.roleMapping')}</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(config.role_mapping).map(([group, role]) => (
                  <span key={group} className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 rounded text-xs">
                    <span className="font-medium">{group}</span>
                    <span className="text-gray-400">&rarr;</span>
                    <span className="capitalize">{t(`roles.${role}`, { defaultValue: role })}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="pt-4 border-t border-gray-200">
          <p className="text-xs text-gray-500">
            {t('superadmin.sso.loginUrl')}: <span className="font-mono text-gray-700">{window.location.origin}/login?sso={tenantSlug}</span>
          </p>
        </div>
      </div>
    )
  }

  // ── Empty state ──
  if (!config && !isEditing) {
    return (
      <div className="card p-12 text-center max-w-3xl">
        <ShieldCheckIcon className="h-12 w-12 text-gray-300 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">{t('superadmin.sso.notConfiguredTitle')}</h3>
        <p className="text-sm text-gray-500 mb-6 max-w-md mx-auto">
          {t('superadmin.sso.notConfiguredDesc')}
        </p>
        <button onClick={startEditing} className="btn-primary">{t('superadmin.sso.configureSso')}</button>
      </div>
    )
  }

  // ── Edit / Create form ──
  return (
    <form onSubmit={handleSubmit} className="card p-6 space-y-6 max-w-3xl">
      <div className="flex items-center justify-between pb-4 border-b border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900">
          {config ? t('superadmin.sso.editConfigTitle') : t('superadmin.sso.setupTitle')}
        </h3>
      </div>

      {saveMutation.isError && (
        <div className="rounded-lg bg-red-50 p-4 text-sm text-red-800">
          {saveMutation.error instanceof Error ? saveMutation.error.message : t('superadmin.sso.saveFailed')}
        </div>
      )}

      <div>
        <label className="label">{t('superadmin.sso.identityProvider')}</label>
        <select className="input" value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })}>
          {SSO_PROVIDERS.map((p) => <option key={p.value} value={p.value}>{t(`superadmin.sso.providers.${p.value}`, { defaultValue: p.label })}</option>)}
        </select>
      </div>

      <div>
        <label className="label">{t('superadmin.sso.displayName')}</label>
        <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder={t('superadmin.sso.displayNamePlaceholder')} />
      </div>

      <div>
        <label className="label">{t('superadmin.sso.issuerUrl')}</label>
        <input className="input font-mono text-sm" value={form.issuer_url} onChange={(e) => setForm({ ...form, issuer_url: e.target.value })} required />
        <ProviderHint provider={form.provider} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="label">{t('superadmin.sso.clientId')}</label>
          <input className="input font-mono text-sm" value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })} required />
        </div>
        <div>
          <label className="label">{t('superadmin.sso.clientSecret')}</label>
          <div className="relative">
            <input
              className="input font-mono text-sm pr-10"
              type={showSecret ? 'text' : 'password'}
              value={form.client_secret}
              onChange={(e) => setForm({ ...form, client_secret: e.target.value })}
              placeholder={config ? t('superadmin.sso.secretUnchangedPlaceholder') : ''}
              required={!config}
            />
            <button type="button" onClick={() => setShowSecret(!showSecret)} className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600">
              {showSecret ? <EyeSlashIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </div>

      <div>
        <label className="label">{t('superadmin.sso.scopes')}</label>
        <input className="input text-sm" value={form.scopes} onChange={(e) => setForm({ ...form, scopes: e.target.value })} />
      </div>

      <div className="pt-4 border-t border-gray-200 space-y-4">
        <h4 className="font-medium text-gray-900">{t('superadmin.sso.userProvisioning')}</h4>
        <div className="flex items-center gap-3">
          <input
            type="checkbox" id="sso_auto_provision" checked={form.auto_provision}
            onChange={(e) => setForm({ ...form, auto_provision: e.target.checked })}
            className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
          />
          <label htmlFor="sso_auto_provision" className="text-sm text-gray-700">{t('superadmin.sso.autoCreateUsers')}</label>
        </div>
        <div>
          <label className="label">{t('superadmin.sso.defaultRole')}</label>
          <select className="input" value={form.default_role} onChange={(e) => setForm({ ...form, default_role: e.target.value })}>
            {SSO_ROLES.map((r) => <option key={r.value} value={r.value}>{t(`roles.${r.value}`, { defaultValue: r.label })}</option>)}
          </select>
        </div>
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="label mb-0">{t('superadmin.sso.roleMapping')}</label>
            <button
              type="button"
              onClick={() => setForm({ ...form, role_mappings: [...form.role_mappings, { idp_group: '', app_role: 'legal' }] })}
              className="flex items-center gap-1 text-xs text-primary-600 hover:text-primary-700 font-medium"
            >
              <PlusIcon className="h-3.5 w-3.5" />
              {t('superadmin.sso.addMapping')}
            </button>
          </div>
          <p className="text-xs text-gray-400 mb-3">
            {t('superadmin.sso.roleMappingHint')}
          </p>
          {form.role_mappings.length === 0 ? (
            <div className="text-center py-4 bg-gray-50 rounded-lg border border-dashed border-gray-300">
              <p className="text-xs text-gray-500">{t('superadmin.sso.noMappings')}</p>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="grid grid-cols-[1fr_auto_1fr_auto] gap-2 items-center text-xs font-medium text-gray-500 px-1">
                <span>{t('superadmin.sso.idpGroupName')}</span>
                <span></span>
                <span>{t('superadmin.sso.appRole')}</span>
                <span></span>
              </div>
              {form.role_mappings.map((mapping, idx) => (
                <div key={idx} className="grid grid-cols-[1fr_auto_1fr_auto] gap-2 items-center">
                  <input
                    className="input text-sm"
                    value={mapping.idp_group}
                    onChange={(e) => {
                      const updated = [...form.role_mappings]
                      updated[idx] = { ...updated[idx], idp_group: e.target.value }
                      setForm({ ...form, role_mappings: updated })
                    }}
                    placeholder={t('superadmin.sso.idpGroupPlaceholder')}
                  />
                  <span className="text-gray-400 text-sm px-1">&rarr;</span>
                  <select
                    className="input text-sm"
                    value={mapping.app_role}
                    onChange={(e) => {
                      const updated = [...form.role_mappings]
                      updated[idx] = { ...updated[idx], app_role: e.target.value }
                      setForm({ ...form, role_mappings: updated })
                    }}
                  >
                    {SSO_ROLES.map((r) => <option key={r.value} value={r.value}>{t(`roles.${r.value}`, { defaultValue: r.label })}</option>)}
                  </select>
                  <button
                    type="button"
                    onClick={() => setForm({ ...form, role_mappings: form.role_mappings.filter((_, i) => i !== idx) })}
                    className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-200">
        <button type="button" onClick={() => setIsEditing(false)} className="btn-secondary">{t('common.cancel')}</button>
        <button type="submit" disabled={saveMutation.isPending} className="btn-primary">
          {saveMutation.isPending ? <span className="flex items-center gap-2"><LoadingSpinner size="sm" className="border-white border-t-transparent" /> {t('integrations.saving')}</span>
            : config ? t('integrations.snow.updateConfiguration') : t('superadmin.sso.enableSso')}
        </button>
      </div>
    </form>
  )
}
