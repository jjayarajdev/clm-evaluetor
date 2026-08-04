/* Tenant detail — Direction B redesign.
   Header (back + identity + plan/status Pills) → Stat row → Tabs
   (overview / users / SSO / settings). Activate-deactivate and SSO-disable go
   through ConfirmDialog with affected/safe lists; user list uses the Table
   primitive; settings keep their inline edit form on Field/Select primitives.
   Queries, mutations and the SSO provisioning flow are unchanged from the
   pre-redesign page; restyle only. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  BuildingOffice2Icon,
  UserGroupIcon,
  DocumentTextIcon,
  CurrencyDollarIcon,
  CircleStackIcon,
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
import {
  Button,
  Checkbox,
  ConfirmDialog,
  EmptyState,
  Field,
  IconButton,
  Pill,
  Select,
  Stat,
  Table,
  Tabs,
  Tag,
  useToast,
} from '@/components/ui'
import type { IconType, PillTone, TableColumn, TabDef } from '@/components/ui'
import { formatDate, formatDateTime, formatCurrency } from '@/lib/utils'
import type { Tenant, TenantStats, TenantUpdate, TenantPlan, User } from '@/types'

type TabType = 'overview' | 'users' | 'settings' | 'sso'

const PLAN_LABELS: Record<TenantPlan, string> = {
  starter: 'Starter',
  professional: 'Professional',
  enterprise: 'Enterprise',
}

const PLAN_TONES: Record<TenantPlan, PillTone> = {
  starter: 'n',
  professional: 'in',
  enterprise: 'p',
}

const ROLE_TONES: Record<string, PillTone> = {
  admin: 'p',
  legal: 'in',
  procurement: 'ok',
  viewer: 'n',
}

function InfoRow({ label, mono, children }: { label: string; mono?: boolean; children: React.ReactNode }) {
  return (
    <div className="row" style={{ justifyContent: 'space-between', gap: 12 }}>
      <span className="muted" style={{ fontSize: 'var(--fs-sm)', flexShrink: 0 }}>{label}</span>
      <span className={mono ? 'mono' : undefined} style={{ fontSize: 'var(--fs-md)', fontWeight: mono ? 400 : 500, textAlign: 'right', minWidth: 0 }}>
        {children}
      </span>
    </div>
  )
}

export default function TenantDetailPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [activeTab, setActiveTab] = useState<TabType>('overview')
  const [isEditing, setIsEditing] = useState(false)
  const [editFormData, setEditFormData] = useState<Partial<TenantUpdate>>({})
  const [confirmingToggle, setConfirmingToggle] = useState(false)

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
      toast({ text: t('superadmin.tenants.updatedToast', { defaultValue: 'Tenant updated' }) })
    },
    onError: (err: any) => {
      toast({ text: err?.response?.data?.detail || err?.message || t('superadmin.tenants.loadError'), error: true })
    },
  })

  const activateMutation = useMutation({
    mutationFn: () => api.activateTenant(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant', id] })
      toast({ text: t('superadmin.tenants.activatedToast', { defaultValue: 'Tenant activated' }) })
    },
    onError: (err: any) => {
      toast({ text: err?.response?.data?.detail || err?.message || t('superadmin.tenants.loadError'), error: true })
    },
  })

  const deactivateMutation = useMutation({
    mutationFn: () => api.deactivateTenant(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant', id] })
      toast({ text: t('superadmin.tenants.deactivatedToast', { defaultValue: 'Tenant deactivated' }) })
    },
    onError: (err: any) => {
      toast({ text: err?.response?.data?.detail || err?.message || t('superadmin.tenants.loadError'), error: true })
    },
  })

  const isLoading = tenantLoading || statsLoading

  if (isLoading) {
    return (
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!tenant) {
    return (
      <EmptyState
        icon={BuildingOffice2Icon}
        title={t('superadmin.tenantDetail.notFound')}
        action={
          <Link to="/super-admin/tenants" style={{ color: 'var(--p)', fontWeight: 500, fontSize: 'var(--fs-md)' }}>
            {t('superadmin.tenantDetail.backToTenants')}
          </Link>
        }
      />
    )
  }

  const confirmToggleActive = () => {
    if (tenant.is_active) {
      deactivateMutation.mutate()
    } else {
      activateMutation.mutate()
    }
    setConfirmingToggle(false)
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

  const tabs: TabDef<TabType>[] = [
    { value: 'overview', label: t('superadmin.tenantDetail.tabOverview') },
    { value: 'users', label: t('superadmin.tenantDetail.tabUsers') },
    { value: 'sso', label: t('superadmin.tenantDetail.tabSso') },
    { value: 'settings', label: t('superadmin.tenantDetail.tabSettings') },
  ]

  const userColumns: TableColumn<User>[] = [
    {
      key: 'user',
      header: t('superadmin.user'),
      sortable: true,
      sortValue: (u) => u.username,
      render: (u) => (
        <span style={{ minWidth: 0, display: 'block' }}>
          <span className="trunc" style={{ display: 'block', fontWeight: 500 }}>{u.username}</span>
          <span className="faint trunc" style={{ display: 'block', fontSize: 'var(--fs-sm)' }}>{u.email}</span>
        </span>
      ),
    },
    {
      key: 'role',
      header: t('superadmin.role'),
      width: 130,
      sortable: true,
      sortValue: (u) => u.role,
      render: (u) => (
        <Pill tone={ROLE_TONES[u.role] || 'n'} dot={false}>
          {t(`roles.${u.role}`, { defaultValue: u.role })}
        </Pill>
      ),
    },
    {
      key: 'status',
      header: t('common.status'),
      width: 110,
      sortable: true,
      sortValue: (u) => (u.is_active ? 0 : 1),
      render: (u) => (
        <Pill tone={u.is_active ? 'ok' : 'da'}>
          {u.is_active ? t('status.active') : t('status.inactive')}
        </Pill>
      ),
    },
    {
      key: 'created',
      header: t('superadmin.created'),
      width: 130,
      nowrap: true,
      sortable: true,
      sortValue: (u) => u.created_at,
      render: (u) => <span className="muted" style={{ fontSize: 'var(--fs-sm)' }}>{formatDate(u.created_at)}</span>,
    },
  ]

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div className="row" style={{ gap: 12, flexWrap: 'wrap' }}>
        <IconButton
          icon={ArrowLeftIcon}
          label={t('superadmin.tenantDetail.backToTenants')}
          onClick={() => navigate('/super-admin/tenants')}
        />
        <div className="row grow" style={{ gap: 12 }}>
          <span
            style={{
              width: 42, height: 42, borderRadius: 'var(--r-md)', display: 'grid', placeItems: 'center',
              background: 'var(--p-f)', color: 'var(--p)', flexShrink: 0,
            }}
          >
            <BuildingOffice2Icon style={{ width: 21, height: 21 }} aria-hidden />
          </span>
          <span style={{ minWidth: 0 }}>
            <h1 className="trunc" style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>
              {tenant.name}
            </h1>
            <span className="faint mono" style={{ display: 'block', fontSize: 'var(--fs-sm)' }}>{tenant.slug}</span>
          </span>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <Pill tone={PLAN_TONES[tenant.plan]} dot={false}>
            {t(`superadmin.plans.${tenant.plan}`, { defaultValue: PLAN_LABELS[tenant.plan] })}
          </Pill>
          <button
            type="button"
            onClick={() => setConfirmingToggle(true)}
            disabled={activateMutation.isPending || deactivateMutation.isPending}
            style={{ background: 'none', border: 0, padding: 0, cursor: 'pointer' }}
            title={
              tenant.is_active
                ? t('superadmin.tenants.deactivateAction', { defaultValue: 'Deactivate' })
                : t('superadmin.tenants.activateAction', { defaultValue: 'Activate' })
            }
          >
            <Pill tone={tenant.is_active ? 'ok' : 'da'}>
              {tenant.is_active ? t('status.active') : t('status.inactive')}
            </Pill>
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        <Stat icon={UserGroupIcon} label={t('superadmin.tenantDetail.users')} value={stats?.user_count || 0} />
        <Stat icon={DocumentTextIcon} label={t('superadmin.tenants.contracts')} value={stats?.contract_count || 0} />
        <Stat icon={CurrencyDollarIcon} label={t('superadmin.tenantDetail.totalValue')} value={formatCurrency(stats?.total_value || 0)} />
        <Stat icon={CircleStackIcon} label={t('superadmin.tenantDetail.storageUsed')} value={`${((stats?.storage_used_mb || 0) / 1024).toFixed(2)} GB`} />
      </div>

      {/* Tabs */}
      <Tabs tabs={tabs} value={activeTab} onChange={setActiveTab} />

      {/* Tab content */}
      {activeTab === 'overview' && (
        <div className="grid gap-3 grid-cols-1 lg:grid-cols-2">
          <div className="card card-p">
            <div className="sec-t" style={{ marginBottom: 12 }}>{t('superadmin.tenantDetail.tenantInformation')}</div>
            <div className="col" style={{ gap: 10 }}>
              <InfoRow label={t('superadmin.tenantDetail.name')}>{tenant.name}</InfoRow>
              <InfoRow label={t('superadmin.tenants.slug')} mono>{tenant.slug}</InfoRow>
              <InfoRow label={t('superadmin.plan')}>
                <Pill tone={PLAN_TONES[tenant.plan]} dot={false}>
                  {t(`superadmin.plans.${tenant.plan}`, { defaultValue: PLAN_LABELS[tenant.plan] })}
                </Pill>
              </InfoRow>
              <InfoRow label={t('superadmin.contractLimit')}>
                {tenant.contract_limit || t('superadmin.tenantDetail.unlimited')}
              </InfoRow>
              <InfoRow label={t('superadmin.contactEmail')}>{tenant.contact_email || '-'}</InfoRow>
              <InfoRow label={t('superadmin.created')}>{formatDate(tenant.created_at)}</InfoRow>
            </div>
          </div>

          <div className="card card-p">
            <div className="sec-t" style={{ marginBottom: 12 }}>{t('superadmin.quickActions')}</div>
            <div className="col" style={{ gap: 8 }}>
              <Link
                to={`/super-admin/custom-fields?tenant=${id}`}
                className="row"
                style={{
                  justifyContent: 'space-between', padding: '10px 12px', borderRadius: 'var(--r-md)',
                  background: 'var(--s2)', color: 'inherit', fontSize: 'var(--fs-md)', fontWeight: 500,
                }}
              >
                <span className="trunc">{t('superadmin.configureCustomFields')}</span>
                <ArrowRightIcon style={{ width: 14, height: 14, flexShrink: 0, color: 'var(--f)' }} aria-hidden />
              </Link>
              <button
                type="button"
                onClick={() => setActiveTab('users')}
                className="row"
                style={{
                  justifyContent: 'space-between', padding: '10px 12px', borderRadius: 'var(--r-md)',
                  background: 'var(--s2)', border: 0, color: 'inherit', fontSize: 'var(--fs-md)', fontWeight: 500,
                  cursor: 'pointer', width: '100%', textAlign: 'left',
                }}
              >
                <span className="trunc">{t('superadmin.tenantDetail.manageUsers')}</span>
                <ArrowRightIcon style={{ width: 14, height: 14, flexShrink: 0, color: 'var(--f)' }} aria-hidden />
              </button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'users' && (
        <div className="col" style={{ gap: 10 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="sec-t">{t('superadmin.tenantDetail.usersCount', { count: users?.length || 0 })}</span>
            <Link
              to={`/super-admin/users?tenant=${id}`}
              style={{ color: 'var(--p)', fontWeight: 500, fontSize: 'var(--fs-sm)' }}
            >
              {t('superadmin.tenantDetail.manageInGlobalUsers')}
            </Link>
          </div>
          <Table
            columns={userColumns}
            rows={users ?? []}
            rowKey={(u) => u.id}
            minWidth={600}
            empty={
              <EmptyState
                icon={UserGroupIcon}
                title={t('superadmin.tenantDetail.noUsersForTenant')}
              />
            }
          />
        </div>
      )}

      {activeTab === 'sso' && tenant && (
        <TenantSSOConfig tenantId={id!} tenantSlug={tenant.slug} />
      )}

      {activeTab === 'settings' && (
        <div className="card card-p" style={{ maxWidth: 640 }}>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 14 }}>
            <span className="sec-t">{t('superadmin.tenantDetail.tenantSettings')}</span>
            {!isEditing && (
              <Button variant="secondary" size="sm" icon={PencilSquareIcon} onClick={handleStartEdit}>
                {t('common.edit')}
              </Button>
            )}
          </div>

          {isEditing ? (
            <form
              onSubmit={(e) => {
                e.preventDefault()
                handleSaveEdit()
              }}
              className="col"
              style={{ gap: 14 }}
            >
              <Field
                label={t('superadmin.tenants.organizationName')}
                type="text"
                value={editFormData.name || ''}
                onChange={(e) => setEditFormData({ ...editFormData, name: e.target.value })}
              />
              <Select
                label={t('superadmin.plan')}
                value={editFormData.plan || ''}
                onChange={(e) => setEditFormData({ ...editFormData, plan: e.target.value as TenantPlan })}
                options={Object.entries(PLAN_LABELS).map(([value, label]) => ({
                  value,
                  label: t(`superadmin.plans.${value}`, { defaultValue: label }),
                }))}
              />
              <Field
                label={t('superadmin.contractLimit')}
                type="number"
                value={editFormData.contract_limit || ''}
                onChange={(e) => setEditFormData({
                  ...editFormData,
                  contract_limit: e.target.value ? parseInt(e.target.value) : null,
                })}
                placeholder={t('superadmin.unlimitedPlaceholder')}
              />
              <Field
                label={t('superadmin.contactEmail')}
                type="email"
                value={editFormData.contact_email || ''}
                onChange={(e) => setEditFormData({ ...editFormData, contact_email: e.target.value })}
              />
              <div className="row" style={{ justifyContent: 'flex-end', gap: 8, paddingTop: 8 }}>
                <Button variant="ghost" onClick={() => setIsEditing(false)}>
                  {t('common.cancel')}
                </Button>
                <Button variant="primary" type="submit" disabled={updateMutation.isPending}>
                  {updateMutation.isPending ? t('common.saving') : t('superadmin.saveChanges')}
                </Button>
              </div>
            </form>
          ) : (
            <div className="col" style={{ gap: 10 }}>
              <InfoRow label={t('superadmin.tenantDetail.name')}>{tenant.name}</InfoRow>
              <InfoRow label={t('superadmin.tenants.slug')} mono>{tenant.slug}</InfoRow>
              <InfoRow label={t('superadmin.plan')}>
                {t(`superadmin.plans.${tenant.plan}`, { defaultValue: PLAN_LABELS[tenant.plan] })}
              </InfoRow>
              <InfoRow label={t('superadmin.contractLimit')}>
                {tenant.contract_limit || t('superadmin.tenantDetail.unlimited')}
              </InfoRow>
              <InfoRow label={t('superadmin.contactEmail')}>{tenant.contact_email || '-'}</InfoRow>
            </div>
          )}
        </div>
      )}

      {/* Activate / deactivate confirmation — replaces the old window.confirm */}
      <ConfirmDialog
        open={confirmingToggle}
        tone={tenant.is_active ? 'danger' : 'warn'}
        title={
          tenant.is_active
            ? t('superadmin.tenants.deactivateTitle', { defaultValue: 'Deactivate tenant?' })
            : t('superadmin.tenants.activateTitle', { defaultValue: 'Activate tenant?' })
        }
        body={
          tenant.is_active
            ? t('superadmin.tenants.deactivateConfirmShort', { name: tenant.name })
            : t('superadmin.tenants.activateConfirm', { name: tenant.name })
        }
        affected={
          tenant.is_active
            ? [t('superadmin.tenants.deactivateAffectedLogins', { defaultValue: 'Sign-in for every user of this tenant' })]
            : undefined
        }
        safe={
          tenant.is_active
            ? [t('superadmin.tenants.deactivateSafeData', { defaultValue: 'Contracts, users and settings — everything is kept and restored on reactivation' })]
            : undefined
        }
        confirmLabel={
          tenant.is_active
            ? t('superadmin.tenants.deactivateAction', { defaultValue: 'Deactivate' })
            : t('superadmin.tenants.activateAction', { defaultValue: 'Activate' })
        }
        cancelLabel={t('common.cancel')}
        onConfirm={confirmToggleActive}
        onCancel={() => setConfirmingToggle(false)}
      />
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

const HEALTH_DISPLAY: Record<string, { tone: PillTone; icon: IconType; label: string }> = {
  healthy: { tone: 'ok', icon: CheckCircleIcon, label: 'Connected' },
  degraded: { tone: 'wa', icon: ExclamationTriangleIcon, label: 'Degraded' },
  unhealthy: { tone: 'da', icon: XCircleIcon, label: 'Unhealthy' },
  unknown: { tone: 'n', icon: SignalIcon, label: 'Not Tested' },
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
    <div className="hint">
      {t('superadmin.sso.exampleLabel')} <span className="mono">{hints[provider] || hints.generic}</span>
    </div>
  )
}

function TenantSSOConfig({ tenantId, tenantSlug }: { tenantId: string; tenantSlug: string }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const api = ssoApi(tenantId)
  const [isEditing, setIsEditing] = useState(false)
  const [form, setForm] = useState<SSOFormData>(emptySSOForm)
  const [showSecret, setShowSecret] = useState(false)
  const [testResult, setTestResult] = useState<{ healthy: boolean; message: string } | null>(null)
  const [confirmingDisable, setConfirmingDisable] = useState(false)

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
      toast({ text: t('superadmin.sso.savedToast', { defaultValue: 'SSO configuration saved' }) })
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
      toast({ text: t('superadmin.sso.disabledToast', { defaultValue: 'SSO disabled' }) })
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
    return (
      <div className="row" style={{ justifyContent: 'center', height: 128 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const health = HEALTH_DISPLAY[config?.health_status || 'unknown'] || HEALTH_DISPLAY.unknown
  const HealthIcon = health.icon

  // ── Display existing config ──
  if (config && !isEditing) {
    return (
      <div className="card card-p col" style={{ gap: 16, maxWidth: 760 }}>
        <div className="row" style={{ gap: 12, flexWrap: 'wrap', paddingBottom: 14, borderBottom: '1px solid var(--b)' }}>
          <span
            style={{
              width: 38, height: 38, borderRadius: 'var(--r-md)', display: 'grid', placeItems: 'center',
              background: 'var(--p-f)', color: 'var(--p)', flexShrink: 0,
            }}
          >
            <ShieldCheckIcon style={{ width: 19, height: 19 }} aria-hidden />
          </span>
          <span className="grow" style={{ minWidth: 0 }}>
            <span className="trunc" style={{ display: 'block', fontWeight: 600 }}>{config.name}</span>
            <span className="faint trunc" style={{ display: 'block', fontSize: 'var(--fs-sm)' }}>
              {t(`superadmin.sso.providers.${config.provider}`, { defaultValue: SSO_PROVIDERS.find((p) => p.value === config.provider)?.label || config.provider })}
            </span>
          </span>
          <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
            <Pill tone={health.tone} dot={false}>
              <HealthIcon style={{ width: 12, height: 12, flexShrink: 0 }} aria-hidden />
              {t(`superadmin.sso.health.${config?.health_status || 'unknown'}`, { defaultValue: health.label })}
            </Pill>
            <Button
              variant="secondary"
              size="sm"
              icon={ArrowPathIcon}
              onClick={() => testMutation.mutate()}
              disabled={testMutation.isPending}
            >
              {t('integrations.test')}
            </Button>
            <Button variant="secondary" size="sm" icon={PencilSquareIcon} onClick={startEditing}>
              {t('common.edit')}
            </Button>
            <Button variant="danger-ghost" size="sm" onClick={() => setConfirmingDisable(true)}>
              {t('superadmin.sso.disable')}
            </Button>
          </div>
        </div>

        {testResult && (
          <div
            className={testResult.healthy ? 'banner' : 'banner banner-da'}
            style={testResult.healthy ? { background: 'var(--ok-f)', borderColor: 'var(--ok-b)', color: 'var(--ok)' } : undefined}
          >
            {testResult.healthy
              ? <CheckCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 2 }} aria-hidden />
              : <XCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 2 }} aria-hidden />}
            <span>
              <b>{testResult.healthy ? t('superadmin.sso.connectionSuccessful') : t('superadmin.sso.connectionFailed')}</b>
              <span style={{ display: 'block', marginTop: 2 }}>{testResult.message}</span>
            </span>
          </div>
        )}

        <div className="grid gap-x-8 gap-y-4 grid-cols-1 sm:grid-cols-2">
          <div>
            <div className="sec-t" style={{ marginBottom: 3 }}>{t('superadmin.sso.issuerUrl')}</div>
            <div className="mono trunc" style={{ fontSize: 'var(--fs-sm)' }}>{config.issuer_url}</div>
          </div>
          <div>
            <div className="sec-t" style={{ marginBottom: 3 }}>{t('superadmin.sso.clientId')}</div>
            <div className="mono trunc" style={{ fontSize: 'var(--fs-sm)' }}>{config.client_id}</div>
          </div>
          <div>
            <div className="sec-t" style={{ marginBottom: 3 }}>{t('superadmin.sso.scopes')}</div>
            <div style={{ fontSize: 'var(--fs-md)' }}>{config.scopes.join(', ')}</div>
          </div>
          <div>
            <div className="sec-t" style={{ marginBottom: 3 }}>{t('superadmin.sso.defaultRole')}</div>
            <div style={{ fontSize: 'var(--fs-md)' }}>{t(`roles.${config.default_role}`, { defaultValue: config.default_role })}</div>
          </div>
          <div>
            <div className="sec-t" style={{ marginBottom: 3 }}>{t('superadmin.sso.autoProvisionUsers')}</div>
            <div style={{ fontSize: 'var(--fs-md)' }}>{config.auto_provision ? t('superadmin.sso.enabled') : t('superadmin.sso.disabled')}</div>
          </div>
          <div>
            <div className="sec-t" style={{ marginBottom: 3 }}>{t('superadmin.sso.lastHealthCheck')}</div>
            <div style={{ fontSize: 'var(--fs-md)' }}>{config.last_health_check ? formatDateTime(config.last_health_check) : t('integrations.never')}</div>
          </div>
          {config.role_mapping && Object.keys(config.role_mapping).length > 0 && (
            <div className="sm:col-span-2">
              <div className="sec-t" style={{ marginBottom: 6 }}>{t('superadmin.sso.roleMapping')}</div>
              <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
                {Object.entries(config.role_mapping).map(([group, role]) => (
                  <Tag key={group}>
                    <b>{group}</b>
                    <span style={{ color: 'var(--f)' }}>&rarr;</span>
                    {t(`roles.${role}`, { defaultValue: role })}
                  </Tag>
                ))}
              </div>
            </div>
          )}
        </div>

        <div style={{ paddingTop: 14, borderTop: '1px solid var(--b)' }}>
          <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
            {t('superadmin.sso.loginUrl')}: <span className="mono muted">{window.location.origin}/login?sso={tenantSlug}</span>
          </span>
        </div>

        {/* Disable confirmation — replaces the old window.confirm */}
        <ConfirmDialog
          open={confirmingDisable}
          title={t('superadmin.sso.disableConfirm')}
          affected={[t('superadmin.sso.disableAffected', { defaultValue: 'SSO sign-in for this tenant' })]}
          safe={[t('superadmin.sso.disableSafe', { defaultValue: 'Provisioned users and their password logins' })]}
          confirmLabel={t('superadmin.sso.disable')}
          cancelLabel={t('common.cancel')}
          onConfirm={() => { setConfirmingDisable(false); deleteMutation.mutate() }}
          onCancel={() => setConfirmingDisable(false)}
        />
      </div>
    )
  }

  // ── Empty state ──
  if (!config && !isEditing) {
    return (
      <div className="card" style={{ maxWidth: 760 }}>
        <EmptyState
          icon={ShieldCheckIcon}
          title={t('superadmin.sso.notConfiguredTitle')}
          body={t('superadmin.sso.notConfiguredDesc')}
          action={
            <Button variant="primary" onClick={startEditing}>
              {t('superadmin.sso.configureSso')}
            </Button>
          }
        />
      </div>
    )
  }

  // ── Edit / Create form ──
  return (
    <form onSubmit={handleSubmit} className="card card-p col" style={{ gap: 16, maxWidth: 760 }}>
      <div style={{ paddingBottom: 14, borderBottom: '1px solid var(--b)' }}>
        <h3 style={{ fontSize: 'var(--fs-lg)', fontWeight: 600 }}>
          {config ? t('superadmin.sso.editConfigTitle') : t('superadmin.sso.setupTitle')}
        </h3>
      </div>

      {saveMutation.isError && (
        <div className="banner banner-da">
          <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
          <span>{saveMutation.error instanceof Error ? saveMutation.error.message : t('superadmin.sso.saveFailed')}</span>
        </div>
      )}

      <Select
        label={t('superadmin.sso.identityProvider')}
        value={form.provider}
        onChange={(e) => setForm({ ...form, provider: e.target.value })}
        options={SSO_PROVIDERS.map((p) => ({
          value: p.value,
          label: t(`superadmin.sso.providers.${p.value}`, { defaultValue: p.label }),
        }))}
      />

      <Field
        label={t('superadmin.sso.displayName')}
        value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })}
        placeholder={t('superadmin.sso.displayNamePlaceholder')}
      />

      <div>
        <Field
          label={t('superadmin.sso.issuerUrl')}
          className="mono"
          value={form.issuer_url}
          onChange={(e) => setForm({ ...form, issuer_url: e.target.value })}
          required
        />
        <ProviderHint provider={form.provider} />
      </div>

      <div className="grid gap-3 grid-cols-1 sm:grid-cols-2">
        <Field
          label={t('superadmin.sso.clientId')}
          className="mono"
          value={form.client_id}
          onChange={(e) => setForm({ ...form, client_id: e.target.value })}
          required
        />
        <div>
          <label className="lbl">{t('superadmin.sso.clientSecret')}</label>
          <div className="inp">
            <input
              className="mono"
              type={showSecret ? 'text' : 'password'}
              value={form.client_secret}
              onChange={(e) => setForm({ ...form, client_secret: e.target.value })}
              placeholder={config ? t('superadmin.sso.secretUnchangedPlaceholder') : ''}
              required={!config}
            />
            <button
              type="button"
              onClick={() => setShowSecret(!showSecret)}
              style={{ background: 'none', border: 0, padding: 0, cursor: 'pointer', color: 'var(--f)', display: 'flex' }}
              aria-label={showSecret ? 'Hide secret' : 'Show secret'}
            >
              {showSecret
                ? <EyeSlashIcon style={{ width: 15, height: 15 }} aria-hidden />
                : <EyeIcon style={{ width: 15, height: 15 }} aria-hidden />}
            </button>
          </div>
        </div>
      </div>

      <Field
        label={t('superadmin.sso.scopes')}
        value={form.scopes}
        onChange={(e) => setForm({ ...form, scopes: e.target.value })}
      />

      <div className="col" style={{ gap: 14, paddingTop: 14, borderTop: '1px solid var(--b)' }}>
        <div className="sec-t">{t('superadmin.sso.userProvisioning')}</div>
        <Checkbox
          checked={form.auto_provision}
          onChange={(checked) => setForm({ ...form, auto_provision: checked })}
          label={t('superadmin.sso.autoCreateUsers')}
        />
        <Select
          label={t('superadmin.sso.defaultRole')}
          value={form.default_role}
          onChange={(e) => setForm({ ...form, default_role: e.target.value })}
          options={SSO_ROLES.map((r) => ({
            value: r.value,
            label: t(`roles.${r.value}`, { defaultValue: r.label }),
          }))}
        />
        <div>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 6 }}>
            <label className="lbl" style={{ marginBottom: 0 }}>{t('superadmin.sso.roleMapping')}</label>
            <Button
              variant="ghost"
              size="sm"
              icon={PlusIcon}
              onClick={() => setForm({ ...form, role_mappings: [...form.role_mappings, { idp_group: '', app_role: 'legal' }] })}
            >
              {t('superadmin.sso.addMapping')}
            </Button>
          </div>
          <p className="faint" style={{ fontSize: 'var(--fs-sm)', marginBottom: 10 }}>
            {t('superadmin.sso.roleMappingHint')}
          </p>
          {form.role_mappings.length === 0 ? (
            <div
              style={{
                textAlign: 'center', padding: '14px 12px', background: 'var(--s2)',
                borderRadius: 'var(--r-md)', border: '1px dashed var(--b2)',
              }}
            >
              <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>{t('superadmin.sso.noMappings')}</span>
            </div>
          ) : (
            <div className="col" style={{ gap: 8 }}>
              <div className="grid grid-cols-[1fr_auto_1fr_auto] gap-2 items-center px-1">
                <span className="sec-t">{t('superadmin.sso.idpGroupName')}</span>
                <span></span>
                <span className="sec-t">{t('superadmin.sso.appRole')}</span>
                <span></span>
              </div>
              {form.role_mappings.map((mapping, idx) => (
                <div key={idx} className="grid grid-cols-[1fr_auto_1fr_auto] gap-2 items-center">
                  <Field
                    value={mapping.idp_group}
                    onChange={(e) => {
                      const updated = [...form.role_mappings]
                      updated[idx] = { ...updated[idx], idp_group: e.target.value }
                      setForm({ ...form, role_mappings: updated })
                    }}
                    placeholder={t('superadmin.sso.idpGroupPlaceholder')}
                  />
                  <span className="faint" style={{ fontSize: 'var(--fs-md)', padding: '0 2px' }}>&rarr;</span>
                  <Select
                    value={mapping.app_role}
                    onChange={(e) => {
                      const updated = [...form.role_mappings]
                      updated[idx] = { ...updated[idx], app_role: e.target.value }
                      setForm({ ...form, role_mappings: updated })
                    }}
                    options={SSO_ROLES.map((r) => ({
                      value: r.value,
                      label: t(`roles.${r.value}`, { defaultValue: r.label }),
                    }))}
                  />
                  <IconButton
                    icon={TrashIcon}
                    size="sm"
                    label={t('common.delete')}
                    onClick={() => setForm({ ...form, role_mappings: form.role_mappings.filter((_, i) => i !== idx) })}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="row" style={{ justifyContent: 'flex-end', gap: 8, paddingTop: 14, borderTop: '1px solid var(--b)' }}>
        <Button variant="ghost" onClick={() => setIsEditing(false)}>
          {t('common.cancel')}
        </Button>
        <Button variant="primary" type="submit" disabled={saveMutation.isPending}>
          {saveMutation.isPending
            ? t('integrations.saving')
            : config
              ? t('integrations.snow.updateConfiguration')
              : t('superadmin.sso.enableSso')}
        </Button>
      </div>
    </form>
  )
}
