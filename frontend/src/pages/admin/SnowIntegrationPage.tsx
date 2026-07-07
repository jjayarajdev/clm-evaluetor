import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  SignalIcon,
  CloudArrowUpIcon,
  EyeIcon,
  EyeSlashIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn, formatDateTime } from '@/lib/utils'
import type { SnowConfig, SnowConfigCreate, SnowSLAMapping } from '@/types/snow-integration'

const HEALTH_CONFIG: Record<string, { color: string; icon: typeof CheckCircleIcon; label: string }> = {
  healthy: { color: 'bg-green-100 text-green-700', icon: CheckCircleIcon, label: 'Healthy' },
  degraded: { color: 'bg-yellow-100 text-yellow-700', icon: ExclamationTriangleIcon, label: 'Degraded' },
  unhealthy: { color: 'bg-red-100 text-red-700', icon: XCircleIcon, label: 'Unhealthy' },
  unknown: { color: 'bg-gray-100 text-gray-600', icon: SignalIcon, label: 'Unknown' },
}

const MAPPING_STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-700',
  mapped: 'bg-green-100 text-green-700',
  ignored: 'bg-gray-100 text-gray-600',
  error: 'bg-red-100 text-red-700',
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

export default function SnowIntegrationPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [isEditing, setIsEditing] = useState(false)
  const [formData, setFormData] = useState<ConfigFormData>(emptyFormData)
  const [showPassword, setShowPassword] = useState(false)
  const [testResult, setTestResult] = useState<{ healthy: boolean; message: string } | null>(null)
  const [syncResult, setSyncResult] = useState<{ fetched: number; created: number; updated: number; errors: number } | null>(null)

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
    },
    onError: () => {
      setTestResult({ healthy: false, message: t('integrations.snow.testFailed') })
    },
  })

  const syncMutation = useMutation({
    mutationFn: () => api.triggerSnowSync(),
    onSuccess: (result) => {
      setSyncResult(result)
      queryClient.invalidateQueries({ queryKey: ['snow-mappings'] })
      queryClient.invalidateQueries({ queryKey: ['snow-config'] })
    },
  })

  const updateMappingMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.updateSnowMapping(id, { mapping_status: status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['snow-mappings'] })
    },
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
  const HealthIcon = healthInfo.icon

  if (configLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (configError) {
    return (
      <div className="rounded-lg bg-red-50 p-4 text-red-700">
        {t('integrations.snow.loadError')}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('integrations.snow.title')}</h1>
        <p className="mt-1 text-sm text-gray-500">
          {t('integrations.snow.subtitle')}
        </p>
      </div>

      {/* Connection Configuration Section */}
      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CloudArrowUpIcon className="h-5 w-5 text-primary-600" />
            <h3 className="text-sm font-medium text-gray-900">{t('integrations.snow.connectionConfiguration')}</h3>
          </div>
          {config && !isEditing && (
            <button onClick={() => openEditForm(config)} className="btn-secondary text-sm py-1 px-3">
              {t('integrations.snow.editConfiguration')}
            </button>
          )}
        </div>

        {/* No config yet - show setup prompt or form */}
        {!config && !isEditing && (
          <div className="p-8 text-center">
            <CloudArrowUpIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-3 text-sm font-semibold text-gray-900">{t('integrations.snow.noConnectionTitle')}</h3>
            <p className="mt-1 text-sm text-gray-500">
              {t('integrations.snow.noConnectionSubtitle')}
            </p>
            <button onClick={() => openEditForm()} className="btn-primary mt-4">
              {t('integrations.snow.configureConnection')}
            </button>
          </div>
        )}

        {/* Existing config status card */}
        {config && !isEditing && (
          <div className="p-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Health Status */}
              <div className="p-4 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500 mb-1">{t('integrations.snow.connectionStatus')}</p>
                <div className="flex items-center gap-2">
                  <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium', healthInfo.color)}>
                    <HealthIcon className="h-3 w-3" />
                    {t(`integrations.health.${config.health_status}`, { defaultValue: healthInfo.label })}
                  </span>
                </div>
                {config.last_health_check && (
                  <p className="text-xs text-gray-500 mt-2">
                    {t('integrations.snow.lastChecked', { date: formatDateTime(config.last_health_check) })}
                  </p>
                )}
                {config.last_health_message && (
                  <p className="text-xs text-gray-500 mt-1">{config.last_health_message}</p>
                )}
              </div>

              {/* Instance Info */}
              <div className="p-4 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500 mb-1">{t('integrations.snow.instance')}</p>
                <p className="text-sm font-medium text-gray-900 truncate">{config.name}</p>
                <p className="text-xs text-gray-500 mt-1 truncate">{config.base_url}</p>
                <p className="text-xs text-gray-500 mt-1">{t('integrations.snow.auth')}: {config.auth_type === 'basic' ? t('integrations.snow.basicAuth') : t('integrations.snow.oauth2')}</p>
              </div>

              {/* Request Stats */}
              <div className="p-4 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500 mb-1">{t('integrations.snow.requestStatistics')}</p>
                <div className="flex items-end gap-3">
                  <div>
                    <p className="text-2xl font-bold text-gray-900">{config.total_requests}</p>
                    <p className="text-xs text-gray-500">{t('integrations.snow.total')}</p>
                  </div>
                  <div>
                    <p className="text-lg font-semibold text-red-600">{config.failed_requests}</p>
                    <p className="text-xs text-gray-500">{t('integrations.failed')}</p>
                  </div>
                </div>
                {config.last_used_at && (
                  <p className="text-xs text-gray-500 mt-2">
                    {t('integrations.snow.lastUsed', { date: formatDateTime(config.last_used_at) })}
                  </p>
                )}
              </div>
            </div>

            {/* Test & Sync Actions */}
            <div className="flex items-center gap-3 pt-2 border-t border-gray-200">
              <button
                onClick={() => testMutation.mutate()}
                disabled={testMutation.isPending}
                className="btn-secondary"
              >
                {testMutation.isPending ? (
                  <LoadingSpinner size="sm" />
                ) : (
                  <SignalIcon className="h-4 w-4 mr-2" />
                )}
                {t('integrations.snow.testConnection')}
              </button>

              {testResult && (
                <span className={cn(
                  'inline-flex items-center gap-1 text-sm',
                  testResult.healthy ? 'text-green-600' : 'text-red-600'
                )}>
                  {testResult.healthy ? (
                    <CheckCircleIcon className="h-4 w-4" />
                  ) : (
                    <XCircleIcon className="h-4 w-4" />
                  )}
                  {testResult.message}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Edit/Create Form */}
        {isEditing && (
          <div className="p-4">
            <form onSubmit={handleSave} className="space-y-4 max-w-lg">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('integrations.snow.connectionName')} *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder={t('integrations.snow.connectionNamePlaceholder')}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('integrations.snow.instanceUrl')} *
                </label>
                <input
                  type="url"
                  value={formData.base_url}
                  onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
                  placeholder="https://dev12345.service-now.com"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                  required
                />
                <p className="text-xs text-gray-500 mt-1">
                  {t('integrations.snow.instanceUrlHint')}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('integrations.snow.authenticationType')} *
                </label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="auth_type"
                      value="basic"
                      checked={formData.auth_type === 'basic'}
                      onChange={() => setFormData({ ...formData, auth_type: 'basic' })}
                      className="text-primary-600 focus:ring-primary-500"
                    />
                    <span className="text-sm text-gray-700">{t('integrations.snow.basicAuth')}</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="auth_type"
                      value="oauth2"
                      checked={formData.auth_type === 'oauth2'}
                      onChange={() => setFormData({ ...formData, auth_type: 'oauth2' })}
                      className="text-primary-600 focus:ring-primary-500"
                    />
                    <span className="text-sm text-gray-700">{t('integrations.snow.oauth2')}</span>
                  </label>
                </div>
              </div>

              {/* Basic Auth Fields */}
              {formData.auth_type === 'basic' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('integrations.snow.username')} *
                    </label>
                    <input
                      type="text"
                      value={formData.username}
                      onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                      placeholder={t('integrations.snow.usernamePlaceholder')}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('integrations.snow.password')} *
                    </label>
                    <div className="relative">
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={formData.password}
                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        placeholder={t('integrations.snow.passwordPlaceholder')}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 pr-10 text-sm focus:ring-2 focus:ring-primary-500"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
                      >
                        {showPassword ? (
                          <EyeSlashIcon className="h-4 w-4" />
                        ) : (
                          <EyeIcon className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                  </div>
                </>
              )}

              {/* OAuth2 Fields */}
              {formData.auth_type === 'oauth2' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('integrations.snow.clientId')} *
                    </label>
                    <input
                      type="text"
                      value={formData.client_id}
                      onChange={(e) => setFormData({ ...formData, client_id: e.target.value })}
                      placeholder={t('integrations.snow.clientIdPlaceholder')}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('integrations.snow.clientSecret')} *
                    </label>
                    <div className="relative">
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={formData.client_secret}
                        onChange={(e) => setFormData({ ...formData, client_secret: e.target.value })}
                        placeholder={t('integrations.snow.clientSecretPlaceholder')}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 pr-10 text-sm focus:ring-2 focus:ring-primary-500"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
                      >
                        {showPassword ? (
                          <EyeSlashIcon className="h-4 w-4" />
                        ) : (
                          <EyeIcon className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('integrations.snow.tokenUrl')} *
                    </label>
                    <input
                      type="url"
                      value={formData.token_url}
                      onChange={(e) => setFormData({ ...formData, token_url: e.target.value })}
                      placeholder="https://dev12345.service-now.com/oauth_token.do"
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                      required
                    />
                  </div>
                </>
              )}

              {/* Save Error */}
              {saveMutation.isError && (
                <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
                  {t('integrations.snow.saveError')}
                </div>
              )}

              {/* Test Result in Form */}
              {testResult && (
                <div className={cn(
                  'rounded-lg p-3 text-sm flex items-center gap-2',
                  testResult.healthy ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                )}>
                  {testResult.healthy ? (
                    <CheckCircleIcon className="h-4 w-4 shrink-0" />
                  ) : (
                    <XCircleIcon className="h-4 w-4 shrink-0" />
                  )}
                  {testResult.message}
                </div>
              )}

              <div className="flex items-center justify-between pt-4 border-t border-gray-200">
                <div>
                  {config && (
                    <button
                      type="button"
                      onClick={() => testMutation.mutate()}
                      disabled={testMutation.isPending}
                      className="btn-secondary"
                    >
                      {testMutation.isPending ? (
                        <LoadingSpinner size="sm" />
                      ) : (
                        <SignalIcon className="h-4 w-4 mr-2" />
                      )}
                      {t('integrations.snow.testConnection')}
                    </button>
                  )}
                </div>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setIsEditing(false)
                      setTestResult(null)
                    }}
                    className="btn-secondary"
                  >
                    {t('common.cancel')}
                  </button>
                  <button
                    type="submit"
                    disabled={saveMutation.isPending}
                    className="btn-primary"
                  >
                    {saveMutation.isPending ? (
                      <LoadingSpinner size="sm" className="border-white border-t-transparent" />
                    ) : config ? (
                      t('integrations.snow.updateConfiguration')
                    ) : (
                      t('integrations.snow.saveConfiguration')
                    )}
                  </button>
                </div>
              </div>
            </form>
          </div>
        )}
      </div>

      {/* SLA Mappings Section */}
      {config && (
        <div className="card overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-900">{t('integrations.snow.slaMappings')}</h3>
            <div className="flex items-center gap-3">
              {syncResult && (
                <span className="text-xs text-gray-500">
                  {t('integrations.snow.syncSummary', { fetched: syncResult.fetched, created: syncResult.created, updated: syncResult.updated })}
                  {syncResult.errors > 0 && (
                    <span className="text-red-600"> | {t('integrations.snow.syncErrorCount', { count: syncResult.errors })}</span>
                  )}
                </span>
              )}
              <button
                onClick={() => syncMutation.mutate()}
                disabled={syncMutation.isPending}
                className="btn-primary text-sm py-1 px-3"
              >
                {syncMutation.isPending ? (
                  <LoadingSpinner size="sm" className="border-white border-t-transparent" />
                ) : (
                  <ArrowPathIcon className="h-4 w-4 mr-2" />
                )}
                {t('integrations.snow.syncNow')}
              </button>
            </div>
          </div>

          {syncMutation.isError && (
            <div className="mx-4 mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">
              {t('integrations.snow.syncFailed')}
            </div>
          )}

          {mappingsLoading ? (
            <div className="flex items-center justify-center h-32">
              <LoadingSpinner size="lg" />
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t('integrations.snow.slaName')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t('integrations.snow.metricType')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t('integrations.snow.target')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t('common.status')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t('integrations.snow.lastSynced')}
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t('common.actions')}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {mappings?.map((mapping: SnowSLAMapping) => (
                      <tr key={mapping.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3">
                          <div className="text-sm font-medium text-gray-900">{mapping.snow_sla_name}</div>
                          <div className="text-xs text-gray-500 font-mono">{mapping.snow_sys_id}</div>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                          {mapping.snow_metric_type || '-'}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                          {mapping.snow_target || '-'}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className={cn(
                            'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                            MAPPING_STATUS_COLORS[mapping.mapping_status] || 'bg-gray-100 text-gray-600'
                          )}>
                            {t(`integrations.snow.mappingStatus.${mapping.mapping_status}`, { defaultValue: t(`status.${mapping.mapping_status}`, { defaultValue: mapping.mapping_status }) })}
                          </span>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-xs text-gray-500">
                          {mapping.last_synced_at ? formatDateTime(mapping.last_synced_at) : t('integrations.never')}
                        </td>
                        <td className="px-4 py-3 text-right whitespace-nowrap">
                          <select
                            value={mapping.mapping_status}
                            onChange={(e) => updateMappingMutation.mutate({ id: mapping.id, status: e.target.value })}
                            disabled={updateMappingMutation.isPending}
                            className="text-sm border border-gray-300 rounded-lg px-2 py-1 focus:ring-2 focus:ring-primary-500"
                          >
                            <option value="pending">{t('status.pending')}</option>
                            <option value="mapped">{t('integrations.snow.mappingStatus.mapped')}</option>
                            <option value="ignored">{t('integrations.snow.mappingStatus.ignored')}</option>
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {(!mappings || mappings.length === 0) && (
                <div className="text-center py-12 text-gray-500">
                  <p className="text-sm">{t('integrations.snow.noMappings')}</p>
                  <p className="text-xs mt-1">{t('integrations.snow.noMappingsHint')}</p>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
