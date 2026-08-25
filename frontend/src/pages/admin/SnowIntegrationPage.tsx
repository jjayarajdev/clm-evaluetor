/* ServiceNow integration — Direction B restyle.
   Connection card (health Pill, instance info, request stats) → credentials
   form on Field/Select primitives → SLA mappings in the Table primitive with
   link Selects, status Pills and a sync Button that reports through toasts.
   All queries, mutations, connection tests, field mappings and sync flows are
   unchanged from the pre-redesign page. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
  SignalIcon,
  CloudArrowUpIcon,
  EyeIcon,
  EyeSlashIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { formatDateTime } from '@/lib/utils'
import { Button, EmptyState, Field, IconButton, Pill, Select, Table, useToast } from '@/components/ui'
import type { PillTone, TableColumn } from '@/components/ui'
import type { SnowConfig, SnowConfigCreate, SnowSLAMapping } from '@/types/snow-integration'

const HEALTH_CONFIG: Record<string, { tone: PillTone; label: string }> = {
  healthy: { tone: 'ok', label: 'Healthy' },
  degraded: { tone: 'wa', label: 'Degraded' },
  unhealthy: { tone: 'da', label: 'Unhealthy' },
  unknown: { tone: 'n', label: 'Unknown' },
}

const MAPPING_STATUS_TONE: Record<string, PillTone> = {
  pending: 'wa',
  mapped: 'ok',
  ignored: 'n',
  error: 'da',
}

interface ConfigFormData {
  name: string
  base_url: string
  auth_type: 'basic' | 'oauth2'
  username: string
  password: string
  client_id: string
  client_secret: string
  token_url: string
}

const emptyFormData: ConfigFormData = {
  name: '',
  base_url: '',
  auth_type: 'basic',
  username: '',
  password: '',
  client_id: '',
  client_secret: '',
  token_url: '',
}

/* Token-coloured result strip for connection tests. */
function ResultBanner({ result }: { result: { healthy: boolean; message: string } }) {
  const Icon = result.healthy ? CheckCircleIcon : XCircleIcon
  return (
    <div
      className={result.healthy ? 'banner' : 'banner banner-da'}
      style={result.healthy ? { background: 'var(--ok-f)', borderColor: 'var(--ok-b)', color: 'var(--ok)' } : undefined}
    >
      <Icon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
      <span>{result.message}</span>
    </div>
  )
}

export default function SnowIntegrationPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [isEditing, setIsEditing] = useState(false)
  const [formData, setFormData] = useState<ConfigFormData>(emptyFormData)
  const [showPassword, setShowPassword] = useState(false)
  const [testResult, setTestResult] = useState<{ healthy: boolean; message: string } | null>(null)
  const [syncResult, setSyncResult] = useState<{ fetched: number; created: number; updated: number; errors: number; auto_mapped?: number; measurements?: number } | null>(null)

  // Queries
  const { data: config, isLoading: configLoading, error: configError } = useQuery({
    queryKey: ['snow-config'],
    queryFn: () => api.getSnowConfig(),
  })

  const { data: mappings, isLoading: mappingsLoading } = useQuery({
    queryKey: ['snow-mappings'],
    queryFn: () => api.getSnowMappings(),
    enabled: !!config,
  })

  // Mutations
  const saveMutation = useMutation({
    mutationFn: (data: SnowConfigCreate) => api.saveSnowConfig(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['snow-config'] })
      setIsEditing(false)
      setTestResult(null)
    },
  })

  const testMutation = useMutation({
    mutationFn: () => api.testSnowConnection(),
    onSuccess: (result) => {
      setTestResult(result)
      toast({ text: result.message, error: !result.healthy })
    },
    onError: () => {
      setTestResult({ healthy: false, message: t('integrations.snow.testFailed') })
      toast({ text: t('integrations.snow.testFailed'), error: true })
    },
  })

  const syncMutation = useMutation({
    mutationFn: () => api.triggerSnowSync(),
    onSuccess: (result) => {
      setSyncResult(result)
      queryClient.invalidateQueries({ queryKey: ['snow-mappings'] })
      queryClient.invalidateQueries({ queryKey: ['snow-config'] })
      toast({
        text: t('integrations.snow.syncSummary', { fetched: result.fetched, created: result.created, updated: result.updated }),
        error: result.errors > 0,
      })
    },
  })

  const updateMappingMutation = useMutation({
    mutationFn: ({ id, status, platform_sla_id }: { id: string; status: string; platform_sla_id?: string | null }) =>
      api.updateSnowMapping(id, { mapping_status: status, platform_sla_id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['snow-mappings'] })
    },
  })

  // Platform (tenant) SLAs to link ServiceNow SLAs to.
  const { data: platformSlas } = useQuery({
    queryKey: ['platform-slas-for-snow-mapping'],
    queryFn: () => api.getPostSigningSLAs() as Promise<{ id: string; sla_name: string }[]>,
    enabled: !!config,
  })

  const openEditForm = (existingConfig?: SnowConfig | null) => {
    if (existingConfig) {
      setFormData({
        name: existingConfig.name,
        base_url: existingConfig.base_url,
        auth_type: existingConfig.auth_type as 'basic' | 'oauth2',
        username: '',
        password: '',
        client_id: '',
        client_secret: '',
        token_url: '',
      })
    } else {
      setFormData(emptyFormData)
    }
    setIsEditing(true)
    setTestResult(null)
  }

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault()
    const payload: SnowConfigCreate = {
      name: formData.name,
      base_url: formData.base_url.replace(/\/+$/, ''),
      auth_type: formData.auth_type,
      credentials: formData.auth_type === 'basic'
        ? { username: formData.username, password: formData.password }
        : { client_id: formData.client_id, client_secret: formData.client_secret, token_url: formData.token_url },
    }
    saveMutation.mutate(payload)
  }

  const healthInfo = config ? HEALTH_CONFIG[config.health_status] || HEALTH_CONFIG.unknown : HEALTH_CONFIG.unknown

  const mappingColumns: TableColumn<SnowSLAMapping>[] = [
    {
      key: 'snow_sla_name',
      header: t('integrations.snow.slaName'),
      sortable: true,
      render: (m) => (
        <span className="col" style={{ gap: 2, minWidth: 0 }}>
          <span className="trunc" style={{ fontWeight: 500 }}>{m.snow_sla_name}</span>
          <span className="mono faint trunc" style={{ fontSize: 'var(--fs-xs)' }}>{m.snow_sys_id}</span>
        </span>
      ),
    },
    {
      key: 'snow_metric_type',
      header: t('integrations.snow.metricType'),
      nowrap: true,
      render: (m) => <span className="muted">{m.snow_metric_type || '—'}</span>,
    },
    {
      key: 'snow_target',
      header: t('integrations.snow.target'),
      nowrap: true,
      render: (m) => <span className="muted">{m.snow_target || '—'}</span>,
    },
    {
      key: 'platform_sla_id',
      header: t('integrations.snow.platformSla', { defaultValue: 'Platform SLA' }),
      render: (m) => (
        <Select
          value={m.platform_sla_id || ''}
          onChange={(e) => updateMappingMutation.mutate({
            id: m.id,
            platform_sla_id: e.target.value || null,
            status: e.target.value ? 'mapped' : 'pending',
          })}
          disabled={updateMappingMutation.isPending}
          containerStyle={{ maxWidth: 220 }}
          options={[
            { value: '', label: t('integrations.snow.notLinked', { defaultValue: '— not linked —' }) },
            ...(platformSlas || []).map((s) => ({ value: s.id, label: s.sla_name })),
          ]}
        />
      ),
    },
    {
      key: 'mapping_status',
      header: t('common.status'),
      nowrap: true,
      sortable: true,
      render: (m) => (
        <Pill tone={MAPPING_STATUS_TONE[m.mapping_status] || 'n'}>
          {t(`integrations.snow.mappingStatus.${m.mapping_status}`, { defaultValue: t(`status.${m.mapping_status}`, { defaultValue: m.mapping_status }) })}
        </Pill>
      ),
    },
    {
      key: 'last_synced_at',
      header: t('integrations.snow.lastSynced'),
      nowrap: true,
      sortable: true,
      render: (m) => (
        <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
          {m.last_synced_at ? formatDateTime(m.last_synced_at) : t('integrations.never')}
        </span>
      ),
    },
    {
      key: 'actions',
      header: t('common.actions'),
      align: 'right',
      nowrap: true,
      render: (m) => (
        <Select
          value={m.mapping_status}
          onChange={(e) => updateMappingMutation.mutate({ id: m.id, status: e.target.value })}
          disabled={updateMappingMutation.isPending}
          containerStyle={{ minWidth: 120 }}
          options={[
            { value: 'pending', label: t('status.pending') },
            { value: 'mapped', label: t('integrations.snow.mappingStatus.mapped') },
            { value: 'ignored', label: t('integrations.snow.mappingStatus.ignored') },
          ]}
        />
      ),
    },
  ]

  if (configLoading) {
    return (
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (configError) {
    return (
      <div className="banner banner-da">
        <XCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
        <span>{t('integrations.snow.loadError')}</span>
      </div>
    )
  }

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>
          {t('integrations.snow.title')}
        </h1>
        <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>
          {t('integrations.snow.subtitle')}
        </p>
      </div>

      {/* Connection Configuration Section */}
      <div className="card">
        <div className="card-h row" style={{ gap: 8 }}>
          <CloudArrowUpIcon style={{ width: 16, height: 16, flexShrink: 0, color: 'var(--p)' }} aria-hidden />
          <span className="sec-t grow">{t('integrations.snow.connectionConfiguration')}</span>
          {config && !isEditing && (
            <Button size="sm" onClick={() => openEditForm(config)}>
              {t('integrations.snow.editConfiguration')}
            </Button>
          )}
        </div>

        {/* No config yet - show setup prompt */}
        {!config && !isEditing && (
          <EmptyState
            icon={CloudArrowUpIcon}
            title={t('integrations.snow.noConnectionTitle')}
            body={t('integrations.snow.noConnectionSubtitle')}
            action={
              <Button variant="primary" onClick={() => openEditForm()}>
                {t('integrations.snow.configureConnection')}
              </Button>
            }
          />
        )}

        {/* Existing config status card */}
        {config && !isEditing && (
          <div className="card-p col" style={{ gap: 14 }}>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* Health Status */}
              <div style={{ padding: 12, background: 'var(--s3)', border: '1px solid var(--b)', borderRadius: 'var(--r-md)' }}>
                <span className="sec-t">{t('integrations.snow.connectionStatus')}</span>
                <div className="row" style={{ marginTop: 8 }}>
                  <Pill tone={healthInfo.tone}>
                    {t(`integrations.health.${config.health_status}`, { defaultValue: healthInfo.label })}
                  </Pill>
                </div>
                {config.last_health_check && (
                  <p className="faint" style={{ fontSize: 'var(--fs-xs)', marginTop: 8 }}>
                    {t('integrations.snow.lastChecked', { date: formatDateTime(config.last_health_check) })}
                  </p>
                )}
                {config.last_health_message && (
                  <p className="faint" style={{ fontSize: 'var(--fs-xs)', marginTop: 4 }}>{config.last_health_message}</p>
                )}
              </div>

              {/* Instance Info */}
              <div style={{ padding: 12, background: 'var(--s3)', border: '1px solid var(--b)', borderRadius: 'var(--r-md)' }}>
                <span className="sec-t">{t('integrations.snow.instance')}</span>
                <p className="trunc" style={{ fontWeight: 500, fontSize: 'var(--fs-md)', marginTop: 8 }}>{config.name}</p>
                <p className="faint mono trunc" style={{ fontSize: 'var(--fs-xs)', marginTop: 4 }}>{config.base_url}</p>
                <p className="faint" style={{ fontSize: 'var(--fs-xs)', marginTop: 4 }}>
                  {t('integrations.snow.auth')}: {config.auth_type === 'basic' ? t('integrations.snow.basicAuth') : t('integrations.snow.oauth2')}
                </p>
              </div>

              {/* Request Stats */}
              <div style={{ padding: 12, background: 'var(--s3)', border: '1px solid var(--b)', borderRadius: 'var(--r-md)' }}>
                <span className="sec-t">{t('integrations.snow.requestStatistics')}</span>
                <div className="row" style={{ gap: 14, alignItems: 'flex-end', marginTop: 8 }}>
                  <div>
                    <p className="num" style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600, lineHeight: 1.1 }}>{config.total_requests}</p>
                    <p className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('integrations.snow.total')}</p>
                  </div>
                  <div>
                    <p className="num" style={{ fontSize: 'var(--fs-lg)', fontWeight: 600, lineHeight: 1.1, color: 'var(--da)' }}>{config.failed_requests}</p>
                    <p className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('integrations.failed')}</p>
                  </div>
                </div>
                {config.last_used_at && (
                  <p className="faint" style={{ fontSize: 'var(--fs-xs)', marginTop: 8 }}>
                    {t('integrations.snow.lastUsed', { date: formatDateTime(config.last_used_at) })}
                  </p>
                )}
              </div>
            </div>

            {/* Test & Sync Actions */}
            <div className="row" style={{ gap: 12, paddingTop: 12, borderTop: '1px solid var(--b)' }}>
              <Button
                icon={SignalIcon}
                onClick={() => testMutation.mutate()}
                disabled={testMutation.isPending}
              >
                {testMutation.isPending ? <LoadingSpinner size="sm" /> : null}
                {t('integrations.snow.testConnection')}
              </Button>

              {testResult && (
                <span
                  className="row"
                  style={{ gap: 6, fontSize: 'var(--fs-md)', color: testResult.healthy ? 'var(--ok)' : 'var(--da)' }}
                >
                  {testResult.healthy ? (
                    <CheckCircleIcon style={{ width: 15, height: 15, flexShrink: 0 }} aria-hidden />
                  ) : (
                    <XCircleIcon style={{ width: 15, height: 15, flexShrink: 0 }} aria-hidden />
                  )}
                  {testResult.message}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Edit/Create Form */}
        {isEditing && (
          <div className="card-p">
            <form onSubmit={handleSave} className="col" style={{ gap: 14, maxWidth: 512 }}>
              <Field
                label={`${t('integrations.snow.connectionName')} *`}
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder={t('integrations.snow.connectionNamePlaceholder')}
                required
              />

              <Field
                label={`${t('integrations.snow.instanceUrl')} *`}
                type="url"
                className="mono"
                value={formData.base_url}
                onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
                placeholder="https://dev12345.service-now.com"
                hint={t('integrations.snow.instanceUrlHint')}
                required
              />

              <div>
                <label className="lbl">{t('integrations.snow.authenticationType')} *</label>
                <div className="row" style={{ gap: 18 }}>
                  <label className="row" style={{ gap: 6, cursor: 'pointer', fontSize: 'var(--fs-md)' }}>
                    <input
                      type="radio"
                      name="auth_type"
                      value="basic"
                      checked={formData.auth_type === 'basic'}
                      onChange={() => setFormData({ ...formData, auth_type: 'basic' })}
                      style={{ accentColor: 'var(--p)' }}
                    />
                    {t('integrations.snow.basicAuth')}
                  </label>
                  <label className="row" style={{ gap: 6, cursor: 'pointer', fontSize: 'var(--fs-md)' }}>
                    <input
                      type="radio"
                      name="auth_type"
                      value="oauth2"
                      checked={formData.auth_type === 'oauth2'}
                      onChange={() => setFormData({ ...formData, auth_type: 'oauth2' })}
                      style={{ accentColor: 'var(--p)' }}
                    />
                    {t('integrations.snow.oauth2')}
                  </label>
                </div>
              </div>

              {/* Basic Auth Fields */}
              {formData.auth_type === 'basic' && (
                <>
                  <Field
                    label={`${t('integrations.snow.username')} *`}
                    type="text"
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    placeholder={t('integrations.snow.usernamePlaceholder')}
                    required
                  />
                  <div>
                    <label className="lbl">{t('integrations.snow.password')} *</label>
                    <div className="inp">
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={formData.password}
                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        placeholder={t('integrations.snow.passwordPlaceholder')}
                        required
                      />
                      <IconButton
                        icon={showPassword ? EyeSlashIcon : EyeIcon}
                        size="sm"
                        label={t('integrations.snow.toggleSecret', { defaultValue: 'Toggle visibility' })}
                        onClick={() => setShowPassword(!showPassword)}
                      />
                    </div>
                  </div>
                </>
              )}

              {/* OAuth2 Fields */}
              {formData.auth_type === 'oauth2' && (
                <>
                  <Field
                    label={`${t('integrations.snow.clientId')} *`}
                    type="text"
                    className="mono"
                    value={formData.client_id}
                    onChange={(e) => setFormData({ ...formData, client_id: e.target.value })}
                    placeholder={t('integrations.snow.clientIdPlaceholder')}
                    required
                  />
                  <div>
                    <label className="lbl">{t('integrations.snow.clientSecret')} *</label>
                    <div className="inp">
                      <input
                        className="mono"
                        type={showPassword ? 'text' : 'password'}
                        value={formData.client_secret}
                        onChange={(e) => setFormData({ ...formData, client_secret: e.target.value })}
                        placeholder={t('integrations.snow.clientSecretPlaceholder')}
                        required
                      />
                      <IconButton
                        icon={showPassword ? EyeSlashIcon : EyeIcon}
                        size="sm"
                        label={t('integrations.snow.toggleSecret', { defaultValue: 'Toggle visibility' })}
                        onClick={() => setShowPassword(!showPassword)}
                      />
                    </div>
                  </div>
                  <Field
                    label={`${t('integrations.snow.tokenUrl')} *`}
                    type="url"
                    className="mono"
                    value={formData.token_url}
                    onChange={(e) => setFormData({ ...formData, token_url: e.target.value })}
                    placeholder="https://dev12345.service-now.com/oauth_token.do"
                    required
                  />
                </>
              )}

              {/* Save Error */}
              {saveMutation.isError && (
                <div className="banner banner-da">
                  <XCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
                  <span>{t('integrations.snow.saveError')}</span>
                </div>
              )}

              {/* Test Result in Form */}
              {testResult && <ResultBanner result={testResult} />}

              <div className="row" style={{ gap: 8, paddingTop: 14, borderTop: '1px solid var(--b)' }}>
                {config && (
                  <Button
                    icon={SignalIcon}
                    onClick={() => testMutation.mutate()}
                    disabled={testMutation.isPending}
                  >
                    {testMutation.isPending ? <LoadingSpinner size="sm" /> : null}
                    {t('integrations.snow.testConnection')}
                  </Button>
                )}
                <span className="grow" />
                <Button
                  variant="ghost"
                  onClick={() => {
                    setIsEditing(false)
                    setTestResult(null)
                  }}
                >
                  {t('common.cancel')}
                </Button>
                <Button variant="primary" type="submit" disabled={saveMutation.isPending}>
                  {saveMutation.isPending ? (
                    <LoadingSpinner size="sm" />
                  ) : config ? (
                    t('integrations.snow.updateConfiguration')
                  ) : (
                    t('integrations.snow.saveConfiguration')
                  )}
                </Button>
              </div>
            </form>
          </div>
        )}
      </div>

      {/* SLA Mappings Section */}
      {config && (
        <div className="col" style={{ gap: 10 }}>
          <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
            <span className="sec-t grow">{t('integrations.snow.slaMappings')}</span>
            {syncResult && (
              <span className="faint" style={{ fontSize: 'var(--fs-xs)' }}>
                {t('integrations.snow.syncSummary', { fetched: syncResult.fetched, created: syncResult.created, updated: syncResult.updated })}
                {(syncResult.auto_mapped || syncResult.measurements) ? (
                  <span> · {t('integrations.snow.syncLinked', { defaultValue: '{{n}} auto-linked', n: syncResult.auto_mapped || 0 })} · {t('integrations.snow.syncMeasured', { defaultValue: '{{n}} measurements', n: syncResult.measurements || 0 })}</span>
                ) : null}
                {syncResult.errors > 0 && (
                  <span style={{ color: 'var(--da)' }}> | {t('integrations.snow.syncErrorCount', { count: syncResult.errors })}</span>
                )}
              </span>
            )}
            <Button
              variant="primary"
              size="sm"
              icon={ArrowPathIcon}
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending}
            >
              {syncMutation.isPending ? <LoadingSpinner size="sm" /> : null}
              {t('integrations.snow.syncNow')}
            </Button>
          </div>

          {syncMutation.isError && (
            <div className="banner banner-da">
              <XCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
              <span>{t('integrations.snow.syncFailed')}</span>
            </div>
          )}

          {mappingsLoading ? (
            <div className="row" style={{ justifyContent: 'center', height: 128 }}>
              <LoadingSpinner size="lg" />
            </div>
          ) : (
            <Table
              columns={mappingColumns}
              rows={mappings ?? []}
              rowKey={(m) => m.id}
              empty={
                <EmptyState
                  icon={ArrowPathIcon}
                  title={t('integrations.snow.noMappings')}
                  body={t('integrations.snow.noMappingsHint')}
                />
              }
            />
          )}
        </div>
      )}
    </div>
  )
}
