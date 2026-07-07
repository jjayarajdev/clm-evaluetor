import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  CloudArrowUpIcon,
  SignalIcon,
  ServerIcon,
  LinkIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn, formatDateTime } from '@/lib/utils'
import type { SnowAdminOverview, SnowIntegrationLog } from '@/types/snow-integration'

const HEALTH_BADGE: Record<string, { color: string; icon: typeof CheckCircleIcon }> = {
  healthy: { color: 'bg-green-100 text-green-700', icon: CheckCircleIcon },
  degraded: { color: 'bg-yellow-100 text-yellow-700', icon: ExclamationTriangleIcon },
  unhealthy: { color: 'bg-red-100 text-red-700', icon: XCircleIcon },
  unknown: { color: 'bg-gray-100 text-gray-600', icon: SignalIcon },
}

export default function SnowAdminPage() {
  const { t } = useTranslation()
  // Queries
  const { data: overview, isLoading: overviewLoading, error: overviewError } = useQuery({
    queryKey: ['snow-admin-overview'],
    queryFn: () => api.getSnowAdminOverview(),
  })

  const { data: logs, isLoading: logsLoading } = useQuery({
    queryKey: ['snow-admin-logs'],
    queryFn: () => api.getSnowIntegrationLogs(50),
  })

  // Compute summary stats
  const totalConfigs = overview?.filter((t: SnowAdminOverview) => t.config !== null).length ?? 0
  const healthyCount = overview?.filter((t: SnowAdminOverview) => t.config?.health_status === 'healthy').length ?? 0
  const unhealthyCount = overview?.filter((t: SnowAdminOverview) => t.config && t.config.health_status !== 'healthy').length ?? 0
  const totalSyncs = overview?.reduce((sum: number, t: SnowAdminOverview) => sum + (t.config?.total_requests ?? 0), 0) ?? 0

  if (overviewLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (overviewError) {
    return (
      <div className="rounded-lg bg-red-50 p-4 text-red-700">
        {t('integrations.snowAdmin.loadError')}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('integrations.snowAdmin.title')}</h1>
        <p className="mt-1 text-sm text-gray-500">
          {t('integrations.snowAdmin.subtitle')}
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-primary-100 flex items-center justify-center">
              <ServerIcon className="h-5 w-5 text-primary-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">{t('integrations.snowAdmin.totalConfigurations')}</p>
              <p className="text-xl font-bold text-gray-900">{totalConfigs}</p>
            </div>
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-green-100 flex items-center justify-center">
              <CheckCircleIcon className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">{t('integrations.health.healthy')}</p>
              <p className="text-xl font-bold text-gray-900">{healthyCount}</p>
            </div>
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-red-100 flex items-center justify-center">
              <XCircleIcon className="h-5 w-5 text-red-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">{t('integrations.health.unhealthy')}</p>
              <p className="text-xl font-bold text-gray-900">{unhealthyCount}</p>
            </div>
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center">
              <ArrowPathIcon className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">{t('integrations.snowAdmin.totalRequests')}</p>
              <p className="text-xl font-bold text-gray-900">{totalSyncs}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Tenant Configurations Table */}
      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center gap-2">
          <CloudArrowUpIcon className="h-5 w-5 text-primary-600" />
          <h3 className="text-sm font-medium text-gray-900">{t('integrations.snowAdmin.tenantConfigurations')}</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('superadmin.tenant')}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('integrations.snow.instanceUrl')}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('common.status')}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('integrations.snowAdmin.lastSync')}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('integrations.snowAdmin.mappings')}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t('integrations.snowAdmin.requests')}
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {overview?.map((tenant: SnowAdminOverview) => {
                const badge = tenant.config
                  ? HEALTH_BADGE[tenant.config.health_status] || HEALTH_BADGE.unknown
                  : null
                const BadgeIcon = badge?.icon

                return (
                  <tr key={tenant.tenant_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className="text-sm font-medium text-gray-900">{tenant.tenant_name}</span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {tenant.config ? (
                        <span className="text-sm text-gray-600 truncate max-w-[200px] inline-block">
                          {tenant.config.base_url}
                        </span>
                      ) : (
                        <span className="text-sm text-gray-400 italic">{t('integrations.snowAdmin.notConfigured')}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {tenant.config && badge ? (
                        <span className={cn(
                          'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium',
                          badge.color
                        )}>
                          {BadgeIcon && <BadgeIcon className="h-3 w-3" />}
                          {t(`integrations.health.${tenant.config.health_status}`, { defaultValue: tenant.config.health_status })}
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500">
                          {t('integrations.snowAdmin.noConfig')}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-xs text-gray-500">
                      {tenant.last_sync ? formatDateTime(tenant.last_sync) : '-'}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {tenant.config ? (
                        <div className="flex items-center gap-1 text-sm text-gray-900">
                          <LinkIcon className="h-3.5 w-3.5 text-gray-400" />
                          {tenant.mapping_count}
                        </div>
                      ) : (
                        <span className="text-sm text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {tenant.config ? (
                        <div className="text-sm">
                          <span className="text-gray-900">{tenant.config.total_requests}</span>
                          {tenant.config.failed_requests > 0 && (
                            <span className="text-red-600 ml-1">
                              ({t('integrations.snowAdmin.failedCount', { count: tenant.config.failed_requests })})
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-sm text-gray-400">-</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {(!overview || overview.length === 0) && (
          <div className="text-center py-12 text-gray-500">
            {t('integrations.snowAdmin.noTenantData')}
          </div>
        )}
      </div>

      {/* Recent Integration Logs */}
      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
          <h3 className="text-sm font-medium text-gray-900">{t('integrations.snowAdmin.recentLogs')}</h3>
        </div>
        {logsLoading ? (
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
                      {t('integrations.snowAdmin.time')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('integrations.snowAdmin.operation')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('integrations.snowAdmin.method')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('integrations.snowAdmin.endpoint')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('common.status')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('integrations.snowAdmin.duration')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('integrations.snowAdmin.error')}
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {logs?.map((log: SnowIntegrationLog) => (
                    <tr key={log.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 whitespace-nowrap text-xs text-gray-500">
                        {formatDateTime(log.started_at)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {log.operation}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className={cn(
                          'inline-flex items-center px-1.5 py-0.5 rounded text-xs font-mono font-medium',
                          log.method === 'GET' ? 'bg-blue-100 text-blue-700' :
                          log.method === 'POST' ? 'bg-green-100 text-green-700' :
                          log.method === 'PUT' ? 'bg-yellow-100 text-yellow-700' :
                          'bg-gray-100 text-gray-700'
                        )}>
                          {log.method}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500 font-mono truncate max-w-[200px]">
                        {log.endpoint}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {log.is_success ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">
                            <CheckCircleIcon className="h-3 w-3" />
                            {log.status_code || 'OK'}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">
                            <XCircleIcon className="h-3 w-3" />
                            {log.status_code || t('integrations.snowAdmin.error')}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-xs text-gray-500">
                        {log.duration_ms !== null ? `${log.duration_ms}ms` : '-'}
                      </td>
                      <td className="px-4 py-3 text-xs text-red-600 truncate max-w-[200px]">
                        {log.error_message || '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {(!logs || logs.length === 0) && (
              <div className="text-center py-12 text-gray-500">
                {t('integrations.snowAdmin.noLogs')}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
