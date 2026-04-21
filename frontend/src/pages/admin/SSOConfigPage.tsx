import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  SignalIcon,
  EyeIcon,
  EyeSlashIcon,
  ArrowPathIcon,
  ShieldCheckIcon,
  PlusIcon,
  TrashIcon,
} from '@heroicons/react/24/outline'
import { client } from '@/lib/api/client'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn, formatDateTime } from '@/lib/utils'

// ── Types ────────────────────────────────────────────────────────────

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

interface SSOConfigForm {
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

const PROVIDERS = [
  { value: 'azure_ad', label: 'Microsoft Entra ID (Azure AD)' },
  { value: 'okta', label: 'Okta' },
  { value: 'google', label: 'Google Workspace' },
  { value: 'auth0', label: 'Auth0' },
  { value: 'generic', label: 'Generic OIDC' },
]

const ROLES = [
  { value: 'admin', label: 'Admin' },
  { value: 'legal', label: 'Legal' },
  { value: 'procurement', label: 'Procurement' },
  { value: 'bu_head', label: 'BU Head' },
]

const HEALTH_CONFIG: Record<string, { color: string; icon: typeof CheckCircleIcon; label: string }> = {
  healthy: { color: 'bg-green-100 text-green-700', icon: CheckCircleIcon, label: 'Connected' },
  degraded: { color: 'bg-yellow-100 text-yellow-700', icon: ExclamationTriangleIcon, label: 'Degraded' },
  unhealthy: { color: 'bg-red-100 text-red-700', icon: XCircleIcon, label: 'Unhealthy' },
  unknown: { color: 'bg-gray-100 text-gray-600', icon: SignalIcon, label: 'Not Tested' },
}

const emptyForm: SSOConfigForm = {
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

// ── API helpers ──────────────────────────────────────────────────────

const ssoApi = {
  getConfig: async (): Promise<SSOConfig | null> => {
    const r = await client.get('/auth/sso/config')
    return r.data
  },
  saveConfig: async (data: SSOConfigForm): Promise<SSOConfig> => {
    let role_mapping: Record<string, string> | null = null
    const validMappings = data.role_mappings.filter((m) => m.idp_group.trim())
    if (validMappings.length > 0) {
      role_mapping = {}
      for (const m of validMappings) {
        role_mapping[m.idp_group.trim()] = m.app_role
      }
    }
    const r = await client.post('/auth/sso/config', {
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
    const r = await client.post('/auth/sso/config/test')
    return r.data
  },
  deleteConfig: async (): Promise<void> => {
    await client.delete('/auth/sso/config')
  },
}

// ── Provider-specific help ────────────────────────────────────────────

function ProviderHelp({ provider }: { provider: string }) {
  const hints: Record<string, { issuer: string; note: string }> = {
    azure_ad: {
      issuer: 'https://login.microsoftonline.com/{tenant-id}/v2.0',
      note: 'Register an app in Azure Portal > App registrations. Add redirect URI: {your-domain}/api/auth/sso/callback. Copy Application (client) ID and create a client secret.',
    },
    okta: {
      issuer: 'https://{your-domain}.okta.com/oauth2/default',
      note: 'Create an OIDC Web Application in Okta admin. Set redirect URI to: {your-domain}/api/auth/sso/callback.',
    },
    google: {
      issuer: 'https://accounts.google.com',
      note: 'Create OAuth 2.0 credentials in Google Cloud Console. Add authorized redirect URI: {your-domain}/api/auth/sso/callback.',
    },
    auth0: {
      issuer: 'https://{your-domain}.auth0.com/',
      note: 'Create a Regular Web Application in Auth0. Add callback URL: {your-domain}/api/auth/sso/callback.',
    },
    generic: {
      issuer: 'https://your-idp.example.com',
      note: 'Enter the OIDC issuer URL. The system will auto-discover endpoints via .well-known/openid-configuration.',
    },
  }
  const h = hints[provider] || hints.generic

  return (
    <div className="rounded-lg bg-blue-50 border border-blue-200 p-4 text-sm">
      <p className="font-medium text-blue-800 mb-1">Setup Guide</p>
      <p className="text-blue-700 mb-2">{h.note}</p>
      <p className="text-blue-600 text-xs font-mono">Example issuer: {h.issuer}</p>
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────

export default function SSOConfigPage() {
  const queryClient = useQueryClient()
  const [isEditing, setIsEditing] = useState(false)
  const [form, setForm] = useState<SSOConfigForm>(emptyForm)
  const [showSecret, setShowSecret] = useState(false)
  const [testResult, setTestResult] = useState<{ healthy: boolean; message: string } | null>(null)

  const { data: config, isLoading } = useQuery({
    queryKey: ['sso-config'],
    queryFn: ssoApi.getConfig,
  })

  const saveMutation = useMutation({
    mutationFn: ssoApi.saveConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sso-config'] })
      setIsEditing(false)
      setTestResult(null)
    },
  })

  const testMutation = useMutation({
    mutationFn: ssoApi.testConfig,
    onSuccess: (data) => {
      setTestResult(data)
      queryClient.invalidateQueries({ queryKey: ['sso-config'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: ssoApi.deleteConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sso-config'] })
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
        client_secret: '', // Don't prefill secret
        scopes: config.scopes.join(' '),
        default_role: config.default_role,
        auto_provision: config.auto_provision,
        role_mappings: config.role_mapping
          ? Object.entries(config.role_mapping).map(([idp_group, app_role]) => ({ idp_group, app_role }))
          : [],
      })
    } else {
      setForm(emptyForm)
    }
    setIsEditing(true)
    setTestResult(null)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    saveMutation.mutate(form)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const health = HEALTH_CONFIG[config?.health_status || 'unknown'] || HEALTH_CONFIG.unknown
  const HealthIcon = health.icon

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">SSO Configuration</h1>
          <p className="mt-1 text-sm text-gray-500">
            Configure Single Sign-On with your identity provider (OIDC)
          </p>
        </div>
        {config && !isEditing && (
          <div className="flex items-center gap-3">
            <span className={cn('inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium', health.color)}>
              <HealthIcon className="h-4 w-4" />
              {health.label}
            </span>
          </div>
        )}
      </div>

      {/* Current Config Display */}
      {config && !isEditing && (
        <div className="card p-6 space-y-6">
          {/* Status bar */}
          <div className="flex items-center justify-between pb-4 border-b border-gray-200">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-primary-100 flex items-center justify-center">
                <ShieldCheckIcon className="h-5 w-5 text-primary-600" />
              </div>
              <div>
                <p className="font-semibold text-gray-900">{config.name}</p>
                <p className="text-xs text-gray-500">
                  {PROVIDERS.find((p) => p.value === config.provider)?.label || config.provider}
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={() => testMutation.mutate()} disabled={testMutation.isPending} className="btn-secondary text-sm">
                {testMutation.isPending ? <LoadingSpinner size="sm" /> : <ArrowPathIcon className="h-4 w-4" />}
                Test Connection
              </button>
              <button onClick={startEditing} className="btn-secondary text-sm">
                Edit
              </button>
              <button
                onClick={() => {
                  if (confirm('Disable SSO for this tenant?')) deleteMutation.mutate()
                }}
                className="btn-secondary text-sm text-red-600 hover:text-red-700"
              >
                Disable
              </button>
            </div>
          </div>

          {/* Test result */}
          {testResult && (
            <div className={cn('rounded-lg p-4 text-sm', testResult.healthy ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800')}>
              <div className="flex items-center gap-2">
                {testResult.healthy ? <CheckCircleIcon className="h-5 w-5" /> : <XCircleIcon className="h-5 w-5" />}
                <span className="font-medium">{testResult.healthy ? 'Connection Successful' : 'Connection Failed'}</span>
              </div>
              <p className="mt-1 ml-7">{testResult.message}</p>
            </div>
          )}

          {/* Config details */}
          <div className="grid grid-cols-2 gap-x-8 gap-y-4 text-sm">
            <div>
              <p className="text-gray-500">Issuer URL</p>
              <p className="font-mono text-gray-900 truncate">{config.issuer_url}</p>
            </div>
            <div>
              <p className="text-gray-500">Client ID</p>
              <p className="font-mono text-gray-900 truncate">{config.client_id}</p>
            </div>
            <div>
              <p className="text-gray-500">Scopes</p>
              <p className="text-gray-900">{config.scopes.join(', ')}</p>
            </div>
            <div>
              <p className="text-gray-500">Default Role</p>
              <p className="text-gray-900 capitalize">{config.default_role}</p>
            </div>
            <div>
              <p className="text-gray-500">Auto-Provision Users</p>
              <p className="text-gray-900">{config.auto_provision ? 'Enabled' : 'Disabled'}</p>
            </div>
            <div>
              <p className="text-gray-500">Last Health Check</p>
              <p className="text-gray-900">{config.last_health_check ? formatDateTime(config.last_health_check) : 'Never'}</p>
            </div>
            {config.role_mapping && Object.keys(config.role_mapping).length > 0 && (
              <div className="col-span-2">
                <p className="text-gray-500 mb-2">Role Mapping</p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(config.role_mapping).map(([group, role]) => (
                    <span key={group} className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 rounded text-xs">
                      <span className="font-medium">{group}</span>
                      <span className="text-gray-400">&rarr;</span>
                      <span className="capitalize">{role}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Tenant slug info */}
          {config.tenant_slug && (
            <div className="pt-4 border-t border-gray-200">
              <p className="text-xs text-gray-500">
                SSO Login URL: <span className="font-mono text-gray-700">{window.location.origin}/login?sso={config.tenant_slug}</span>
              </p>
            </div>
          )}
        </div>
      )}

      {/* No config state */}
      {!config && !isEditing && (
        <div className="card p-12 text-center">
          <ShieldCheckIcon className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">SSO Not Configured</h3>
          <p className="text-sm text-gray-500 mb-6 max-w-md mx-auto">
            Set up Single Sign-On to allow users to authenticate with your organization's identity provider (Azure AD, Okta, Google, etc.)
          </p>
          <button onClick={startEditing} className="btn-primary">
            Configure SSO
          </button>
        </div>
      )}

      {/* Edit / Create Form */}
      {isEditing && (
        <form onSubmit={handleSubmit} className="card p-6 space-y-6">
          <div className="flex items-center justify-between pb-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">
              {config ? 'Edit SSO Configuration' : 'Set Up SSO'}
            </h3>
          </div>

          {saveMutation.isError && (
            <div className="rounded-lg bg-red-50 p-4 text-sm text-red-800">
              {saveMutation.error instanceof Error ? saveMutation.error.message : 'Failed to save configuration'}
            </div>
          )}

          {/* Provider */}
          <div>
            <label className="label">Identity Provider</label>
            <select
              className="input"
              value={form.provider}
              onChange={(e) => setForm({ ...form, provider: e.target.value })}
            >
              {PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>

          <ProviderHelp provider={form.provider} />

          {/* Name */}
          <div>
            <label className="label">Display Name</label>
            <input
              className="input"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g., Corporate SSO"
            />
          </div>

          {/* OIDC Settings */}
          <div className="grid grid-cols-1 gap-4">
            <div>
              <label className="label">Issuer URL</label>
              <input
                className="input font-mono text-sm"
                value={form.issuer_url}
                onChange={(e) => setForm({ ...form, issuer_url: e.target.value })}
                placeholder="https://login.microsoftonline.com/{tenant-id}/v2.0"
                required
              />
              <p className="mt-1 text-xs text-gray-400">
                The OIDC discovery URL (.well-known/openid-configuration) will be appended automatically
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Client ID</label>
                <input
                  className="input font-mono text-sm"
                  value={form.client_id}
                  onChange={(e) => setForm({ ...form, client_id: e.target.value })}
                  placeholder="Application (client) ID"
                  required
                />
              </div>
              <div>
                <label className="label">Client Secret</label>
                <div className="relative">
                  <input
                    className="input font-mono text-sm pr-10"
                    type={showSecret ? 'text' : 'password'}
                    value={form.client_secret}
                    onChange={(e) => setForm({ ...form, client_secret: e.target.value })}
                    placeholder={config ? '(unchanged if empty)' : 'Client secret value'}
                    required={!config}
                  />
                  <button
                    type="button"
                    onClick={() => setShowSecret(!showSecret)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
                  >
                    {showSecret ? <EyeSlashIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
                  </button>
                </div>
              </div>
            </div>

            <div>
              <label className="label">Scopes</label>
              <input
                className="input text-sm"
                value={form.scopes}
                onChange={(e) => setForm({ ...form, scopes: e.target.value })}
                placeholder="openid email profile"
              />
              <p className="mt-1 text-xs text-gray-400">Space-separated list of OIDC scopes</p>
            </div>
          </div>

          {/* User Provisioning */}
          <div className="pt-4 border-t border-gray-200">
            <h4 className="font-medium text-gray-900 mb-4">User Provisioning</h4>

            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="auto_provision"
                  checked={form.auto_provision}
                  onChange={(e) => setForm({ ...form, auto_provision: e.target.checked })}
                  className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <label htmlFor="auto_provision" className="text-sm text-gray-700">
                  Auto-create users on first SSO login
                </label>
              </div>

              <div>
                <label className="label">Default Role for New Users</label>
                <select
                  className="input"
                  value={form.default_role}
                  onChange={(e) => setForm({ ...form, default_role: e.target.value })}
                >
                  {ROLES.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="label mb-0">Role Mapping</label>
                  <button
                    type="button"
                    onClick={() => setForm({ ...form, role_mappings: [...form.role_mappings, { idp_group: '', app_role: 'legal' }] })}
                    className="flex items-center gap-1 text-xs text-primary-600 hover:text-primary-700 font-medium"
                  >
                    <PlusIcon className="h-3.5 w-3.5" />
                    Add Mapping
                  </button>
                </div>
                <p className="text-xs text-gray-400 mb-3">
                  Map identity provider groups to application roles. Users in matched groups get the mapped role instead of the default.
                </p>
                {form.role_mappings.length === 0 ? (
                  <div className="text-center py-4 bg-gray-50 rounded-lg border border-dashed border-gray-300">
                    <p className="text-xs text-gray-500">No mappings — all SSO users will get the default role</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="grid grid-cols-[1fr_auto_1fr_auto] gap-2 items-center text-xs font-medium text-gray-500 px-1">
                      <span>IdP Group Name</span>
                      <span></span>
                      <span>App Role</span>
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
                          placeholder="e.g., ContractAdmins"
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
                          {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
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
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-200">
            <button type="button" onClick={() => setIsEditing(false)} className="btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={saveMutation.isPending} className="btn-primary">
              {saveMutation.isPending ? (
                <span className="flex items-center gap-2">
                  <LoadingSpinner size="sm" className="border-white border-t-transparent" />
                  Saving...
                </span>
              ) : config ? (
                'Update Configuration'
              ) : (
                'Enable SSO'
              )}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
