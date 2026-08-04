/* SSO configuration — Direction B restyle.
   Health Pill in the header → config card with token detail grid and role
   mapping Tags → edit form on Field/Select/Switch primitives (secret stays
   masked with an eye toggle) → disable now goes through ConfirmDialog instead
   of window.confirm. All queries, mutations, the test flow, validation and
   payload shapes are unchanged from the pre-redesign page. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  CheckCircleIcon,
  XCircleIcon,
  EyeIcon,
  EyeSlashIcon,
  ArrowPathIcon,
  ShieldCheckIcon,
  PlusIcon,
  TrashIcon,
} from '@heroicons/react/24/outline'
import { client } from '@/lib/api/client'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { formatDateTime } from '@/lib/utils'
import {
  Button,
  ConfirmDialog,
  EmptyState,
  Field,
  IconButton,
  Pill,
  Select,
  Switch,
  Tag,
  useToast,
} from '@/components/ui'
import type { PillTone } from '@/components/ui'

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

const HEALTH_CONFIG: Record<string, { tone: PillTone; label: string }> = {
  healthy: { tone: 'ok', label: 'Connected' },
  degraded: { tone: 'wa', label: 'Degraded' },
  unhealthy: { tone: 'da', label: 'Unhealthy' },
  unknown: { tone: 'n', label: 'Not Tested' },
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
  const { t } = useTranslation()
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
  const helpKey = provider in hints ? provider : 'generic'

  return (
    <div className="banner banner-in" style={{ flexDirection: 'column', gap: 4 }}>
      <b>{t('ssoConfig.setupGuide')}</b>
      <span>{t(`ssoConfig.help.${helpKey}`, { defaultValue: h.note })}</span>
      <span className="mono" style={{ fontSize: 'var(--fs-xs)' }}>
        {t('ssoConfig.exampleIssuer')} {h.issuer}
      </span>
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────

export default function SSOConfigPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [isEditing, setIsEditing] = useState(false)
  const [form, setForm] = useState<SSOConfigForm>(emptyForm)
  const [showSecret, setShowSecret] = useState(false)
  const [testResult, setTestResult] = useState<{ healthy: boolean; message: string } | null>(null)
  const [confirmDisable, setConfirmDisable] = useState(false)

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
      toast({ text: data.message, error: !data.healthy })
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
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const health = HEALTH_CONFIG[config?.health_status || 'unknown'] || HEALTH_CONFIG.unknown

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div className="row" style={{ alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>
            {t('ssoConfig.title')}
          </h1>
          <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>
            {t('ssoConfig.subtitle')}
          </p>
        </div>
        {config && !isEditing && (
          <Pill tone={health.tone}>
            {t(`ssoConfig.health.${config?.health_status || 'unknown'}`, { defaultValue: health.label })}
          </Pill>
        )}
      </div>

      {/* Current Config Display */}
      {config && !isEditing && (
        <div className="card card-p col" style={{ gap: 16 }}>
          {/* Status bar */}
          <div className="row" style={{ gap: 12, paddingBottom: 14, borderBottom: '1px solid var(--b)', flexWrap: 'wrap' }}>
            <span
              style={{
                width: 40, height: 40, borderRadius: 'var(--r-lg)', flexShrink: 0,
                background: 'var(--p-f)', color: 'var(--p)', display: 'grid', placeItems: 'center',
              }}
            >
              <ShieldCheckIcon style={{ width: 20, height: 20 }} aria-hidden />
            </span>
            <div className="grow" style={{ minWidth: 0 }}>
              <p style={{ fontWeight: 600, fontSize: 'var(--fs-md)' }}>{config.name}</p>
              <p className="faint" style={{ fontSize: 'var(--fs-xs)' }}>
                {PROVIDERS.find((p) => p.value === config.provider)?.label || config.provider}
              </p>
            </div>
            <div className="row" style={{ gap: 6 }}>
              <Button
                size="sm"
                icon={ArrowPathIcon}
                onClick={() => testMutation.mutate()}
                disabled={testMutation.isPending}
              >
                {testMutation.isPending ? <LoadingSpinner size="sm" /> : null}
                {t('ssoConfig.testConnection')}
              </Button>
              <Button size="sm" onClick={startEditing}>
                {t('common.edit')}
              </Button>
              <Button size="sm" variant="danger-ghost" onClick={() => setConfirmDisable(true)}>
                {t('ssoConfig.disable')}
              </Button>
            </div>
          </div>

          {/* Test result */}
          {testResult && (
            <div
              className={testResult.healthy ? 'banner' : 'banner banner-da'}
              style={testResult.healthy ? { background: 'var(--ok-f)', borderColor: 'var(--ok-b)', color: 'var(--ok)' } : undefined}
            >
              {testResult.healthy ? (
                <CheckCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
              ) : (
                <XCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
              )}
              <span>
                <b>{testResult.healthy ? t('ssoConfig.connectionSuccessful') : t('ssoConfig.connectionFailed')}</b>
                <span style={{ display: 'block', marginTop: 2 }}>{testResult.message}</span>
              </span>
            </div>
          )}

          {/* Config details */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-4">
            <div style={{ minWidth: 0 }}>
              <span className="sec-t">{t('ssoConfig.issuerUrl')}</span>
              <p className="mono trunc" style={{ fontSize: 'var(--fs-sm)', marginTop: 3 }}>{config.issuer_url}</p>
            </div>
            <div style={{ minWidth: 0 }}>
              <span className="sec-t">{t('ssoConfig.clientId')}</span>
              <p className="mono trunc" style={{ fontSize: 'var(--fs-sm)', marginTop: 3 }}>{config.client_id}</p>
            </div>
            <div>
              <span className="sec-t">{t('ssoConfig.scopes')}</span>
              <p style={{ fontSize: 'var(--fs-md)', marginTop: 3 }}>{config.scopes.join(', ')}</p>
            </div>
            <div>
              <span className="sec-t">{t('ssoConfig.defaultRole')}</span>
              <p style={{ fontSize: 'var(--fs-md)', marginTop: 3, textTransform: 'capitalize' }}>
                {t(`roles.${config.default_role}`, { defaultValue: config.default_role })}
              </p>
            </div>
            <div>
              <span className="sec-t">{t('ssoConfig.autoProvisionUsers')}</span>
              <div style={{ marginTop: 4 }}>
                <Pill tone={config.auto_provision ? 'ok' : 'n'}>
                  {config.auto_provision ? t('ssoConfig.enabled') : t('ssoConfig.disabled')}
                </Pill>
              </div>
            </div>
            <div>
              <span className="sec-t">{t('ssoConfig.lastHealthCheck')}</span>
              <p style={{ fontSize: 'var(--fs-md)', marginTop: 3 }}>
                {config.last_health_check ? formatDateTime(config.last_health_check) : t('ssoConfig.never')}
              </p>
            </div>
            {config.role_mapping && Object.keys(config.role_mapping).length > 0 && (
              <div className="sm:col-span-2">
                <span className="sec-t">{t('ssoConfig.roleMapping')}</span>
                <div className="row" style={{ gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
                  {Object.entries(config.role_mapping).map(([group, role]) => (
                    <Tag key={group}>
                      {group} &rarr; {t(`roles.${role}`, { defaultValue: role })}
                    </Tag>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Tenant slug info */}
          {config.tenant_slug && (
            <div style={{ paddingTop: 14, borderTop: '1px solid var(--b)' }}>
              <p className="faint" style={{ fontSize: 'var(--fs-xs)' }}>
                {t('ssoConfig.ssoLoginUrl')}{' '}
                <span className="mono muted">{window.location.origin}/login?sso={config.tenant_slug}</span>
              </p>
            </div>
          )}
        </div>
      )}

      {/* No config state */}
      {!config && !isEditing && (
        <div className="card">
          <EmptyState
            icon={ShieldCheckIcon}
            title={t('ssoConfig.notConfigured')}
            body={t('ssoConfig.notConfiguredHint')}
            action={
              <Button variant="primary" onClick={startEditing}>
                {t('ssoConfig.configureSso')}
              </Button>
            }
          />
        </div>
      )}

      {/* Edit / Create Form */}
      {isEditing && (
        <form onSubmit={handleSubmit} className="card card-p col" style={{ gap: 16 }}>
          <div style={{ paddingBottom: 14, borderBottom: '1px solid var(--b)' }}>
            <h3 style={{ fontSize: 'var(--fs-lg)', fontWeight: 600 }}>
              {config ? t('ssoConfig.editConfiguration') : t('ssoConfig.setUpSso')}
            </h3>
          </div>

          {saveMutation.isError && (
            <div className="banner banner-da">
              <XCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
              <span>{saveMutation.error instanceof Error ? saveMutation.error.message : t('ssoConfig.failedToSave')}</span>
            </div>
          )}

          {/* Provider */}
          <Select
            label={t('ssoConfig.identityProvider')}
            value={form.provider}
            onChange={(e) => setForm({ ...form, provider: e.target.value })}
            options={PROVIDERS}
          />

          <ProviderHelp provider={form.provider} />

          {/* Name */}
          <Field
            label={t('ssoConfig.displayName')}
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder={t('ssoConfig.displayNamePlaceholder')}
          />

          {/* OIDC Settings */}
          <Field
            label={t('ssoConfig.issuerUrl')}
            type="text"
            className="mono"
            value={form.issuer_url}
            onChange={(e) => setForm({ ...form, issuer_url: e.target.value })}
            placeholder="https://login.microsoftonline.com/{tenant-id}/v2.0"
            hint={t('ssoConfig.discoveryHint')}
            required
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field
              label={t('ssoConfig.clientId')}
              type="text"
              className="mono"
              value={form.client_id}
              onChange={(e) => setForm({ ...form, client_id: e.target.value })}
              placeholder={t('ssoConfig.clientIdPlaceholder')}
              required
            />
            <div>
              <label className="lbl">{t('ssoConfig.clientSecret')}</label>
              <div className="inp">
                <input
                  className="mono"
                  type={showSecret ? 'text' : 'password'}
                  value={form.client_secret}
                  onChange={(e) => setForm({ ...form, client_secret: e.target.value })}
                  placeholder={config ? t('ssoConfig.secretUnchangedPlaceholder') : t('ssoConfig.secretValuePlaceholder')}
                  required={!config}
                />
                <IconButton
                  icon={showSecret ? EyeSlashIcon : EyeIcon}
                  size="sm"
                  label={t('ssoConfig.toggleSecret', { defaultValue: 'Toggle visibility' })}
                  onClick={() => setShowSecret(!showSecret)}
                />
              </div>
            </div>
          </div>

          <Field
            label={t('ssoConfig.scopes')}
            type="text"
            value={form.scopes}
            onChange={(e) => setForm({ ...form, scopes: e.target.value })}
            placeholder="openid email profile"
            hint={t('ssoConfig.scopesHint')}
          />

          {/* User Provisioning */}
          <div className="col" style={{ gap: 14, paddingTop: 14, borderTop: '1px solid var(--b)' }}>
            <span className="sec-t">{t('ssoConfig.userProvisioning')}</span>

            <Switch
              checked={form.auto_provision}
              onChange={(checked) => setForm({ ...form, auto_provision: checked })}
              label={t('ssoConfig.autoCreateUsers')}
            />

            <Select
              label={t('ssoConfig.defaultRoleForNewUsers')}
              value={form.default_role}
              onChange={(e) => setForm({ ...form, default_role: e.target.value })}
              options={ROLES.map((r) => ({ value: r.value, label: t(`roles.${r.value}`, { defaultValue: r.label }) }))}
            />

            <div>
              <div className="row" style={{ marginBottom: 5 }}>
                <label className="lbl grow" style={{ marginBottom: 0 }}>{t('ssoConfig.roleMapping')}</label>
                <Button
                  variant="ghost"
                  size="sm"
                  icon={PlusIcon}
                  onClick={() => setForm({ ...form, role_mappings: [...form.role_mappings, { idp_group: '', app_role: 'legal' }] })}
                >
                  {t('ssoConfig.addMapping')}
                </Button>
              </div>
              <p className="faint" style={{ fontSize: 'var(--fs-xs)', marginBottom: 10 }}>
                {t('ssoConfig.roleMappingHint')}
              </p>
              {form.role_mappings.length === 0 ? (
                <div
                  style={{
                    padding: '14px 12px', textAlign: 'center', background: 'var(--s3)',
                    border: '1px dashed var(--b2)', borderRadius: 'var(--r-md)',
                  }}
                >
                  <p className="faint" style={{ fontSize: 'var(--fs-sm)' }}>{t('ssoConfig.noMappings')}</p>
                </div>
              ) : (
                <div className="col" style={{ gap: 8 }}>
                  <div className="grid grid-cols-[1fr_auto_1fr_auto] gap-2 items-center" style={{ padding: '0 2px' }}>
                    <span className="sec-t">{t('ssoConfig.idpGroupName')}</span>
                    <span></span>
                    <span className="sec-t">{t('ssoConfig.appRole')}</span>
                    <span></span>
                  </div>
                  {form.role_mappings.map((mapping, idx) => (
                    <div key={idx} className="grid grid-cols-[1fr_auto_1fr_auto] gap-2 items-center">
                      <Field
                        type="text"
                        value={mapping.idp_group}
                        onChange={(e) => {
                          const updated = [...form.role_mappings]
                          updated[idx] = { ...updated[idx], idp_group: e.target.value }
                          setForm({ ...form, role_mappings: updated })
                        }}
                        placeholder={t('ssoConfig.idpGroupPlaceholder')}
                      />
                      <span className="faint" style={{ padding: '0 2px' }}>&rarr;</span>
                      <Select
                        value={mapping.app_role}
                        onChange={(e) => {
                          const updated = [...form.role_mappings]
                          updated[idx] = { ...updated[idx], app_role: e.target.value }
                          setForm({ ...form, role_mappings: updated })
                        }}
                        options={ROLES.map((r) => ({ value: r.value, label: t(`roles.${r.value}`, { defaultValue: r.label }) }))}
                      />
                      <IconButton
                        icon={TrashIcon}
                        size="sm"
                        label={t('common.delete', { defaultValue: 'Delete' })}
                        onClick={() => setForm({ ...form, role_mappings: form.role_mappings.filter((_, i) => i !== idx) })}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="row" style={{ justifyContent: 'flex-end', gap: 8, paddingTop: 14, borderTop: '1px solid var(--b)' }}>
            <Button variant="ghost" onClick={() => setIsEditing(false)}>
              {t('common.cancel')}
            </Button>
            <Button variant="primary" type="submit" disabled={saveMutation.isPending}>
              {saveMutation.isPending ? (
                <span className="row" style={{ gap: 8 }}>
                  <LoadingSpinner size="sm" />
                  {t('ssoConfig.saving')}
                </span>
              ) : config ? (
                t('ssoConfig.updateConfiguration')
              ) : (
                t('ssoConfig.enableSso')
              )}
            </Button>
          </div>
        </form>
      )}

      {/* Disable — replaces window.confirm; same deleteConfig call */}
      <ConfirmDialog
        open={confirmDisable}
        tone="danger"
        title={t('ssoConfig.disable')}
        body={t('ssoConfig.confirmDisable')}
        confirmLabel={t('ssoConfig.disable')}
        cancelLabel={t('common.cancel')}
        onConfirm={() => {
          setConfirmDisable(false)
          deleteMutation.mutate()
        }}
        onCancel={() => setConfirmDisable(false)}
      />
    </div>
  )
}
