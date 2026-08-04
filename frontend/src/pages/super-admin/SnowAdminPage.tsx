/* Platform-wide ServiceNow integration overview — Direction B restyle.
   Header → Stat summary row → tenant configuration Table (health Pills) →
   recent integration log Table. Read-only page; both queries and the
   computed summary stats are unchanged from the pre-redesign page. */
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
  DocumentTextIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { EmptyState, Pill, Stat, Table } from '@/components/ui'
import type { PillTone, TableColumn } from '@/components/ui'
import { formatDateTime } from '@/lib/utils'
import type { SnowAdminOverview, SnowIntegrationLog } from '@/types/snow-integration'

const HEALTH_PILL: Record<string, { tone: PillTone; icon: typeof CheckCircleIcon }> = {
  healthy: { tone: 'ok', icon: CheckCircleIcon },
  degraded: { tone: 'wa', icon: ExclamationTriangleIcon },
  unhealthy: { tone: 'da', icon: XCircleIcon },
  unknown: { tone: 'n', icon: SignalIcon },
}

const METHOD_TONE: Record<string, PillTone> = {
  GET: 'in',
  POST: 'ok',
  PUT: 'wa',
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

  const tenantColumns: TableColumn<SnowAdminOverview>[] = [
    {
      key: 'tenant',
      header: t('superadmin.tenant'),
      sortable: true,
      sortValue: (row) => row.tenant_name,
      nowrap: true,
      render: (row) => <span style={{ fontWeight: 500 }}>{row.tenant_name}</span>,
    },
    {
      key: 'instance',
      header: t('integrations.snow.instanceUrl'),
      render: (row) =>
        row.config ? (
          <span className="muted trunc" style={{ display: 'block', maxWidth: 220, fontSize: 'var(--fs-sm)' }}>
            {row.config.base_url}
          </span>
        ) : (
          <span className="faint" style={{ fontSize: 'var(--fs-sm)', fontStyle: 'italic' }}>
            {t('integrations.snowAdmin.notConfigured')}
          </span>
        ),
    },
    {
      key: 'status',
      header: t('common.status'),
      width: 130,
      sortable: true,
      sortValue: (row) => row.config?.health_status ?? '',
      render: (row) => {
        if (!row.config) {
          return <Pill tone="n" dot={false}>{t('integrations.snowAdmin.noConfig')}</Pill>
        }
        const badge = HEALTH_PILL[row.config.health_status] || HEALTH_PILL.unknown
        const BadgeIcon = badge.icon
        return (
          <Pill tone={badge.tone} dot={false}>
            <BadgeIcon style={{ width: 12, height: 12, flexShrink: 0 }} aria-hidden />
            {t(`integrations.health.${row.config.health_status}`, { defaultValue: row.config.health_status })}
          </Pill>
        )
      },
    },
    {
      key: 'lastSync',
      header: t('integrations.snowAdmin.lastSync'),
      width: 160,
      nowrap: true,
      sortable: true,
      sortValue: (row) => row.last_sync,
      render: (row) => (
        <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
          {row.last_sync ? formatDateTime(row.last_sync) : '-'}
        </span>
      ),
    },
    {
      key: 'mappings',
      header: t('integrations.snowAdmin.mappings'),
      width: 110,
      sortable: true,
      sortValue: (row) => (row.config ? row.mapping_count : null),
      render: (row) =>
        row.config ? (
          <span className="row num" style={{ gap: 4, fontSize: 'var(--fs-md)' }}>
            <LinkIcon style={{ width: 13, height: 13, color: 'var(--f)', flexShrink: 0 }} aria-hidden />
            {row.mapping_count}
          </span>
        ) : (
          <span className="faint">-</span>
        ),
    },
    {
      key: 'requests',
      header: t('integrations.snowAdmin.requests'),
      width: 130,
      sortable: true,
      sortValue: (row) => row.config?.total_requests ?? null,
      render: (row) =>
        row.config ? (
          <span className="num" style={{ fontSize: 'var(--fs-md)' }}>
            {row.config.total_requests}
            {row.config.failed_requests > 0 && (
              <span style={{ color: 'var(--da)', marginLeft: 4 }}>
                ({t('integrations.snowAdmin.failedCount', { count: row.config.failed_requests })})
              </span>
            )}
          </span>
        ) : (
          <span className="faint">-</span>
        ),
    },
  ]

  const logColumns: TableColumn<SnowIntegrationLog>[] = [
    {
      key: 'time',
      header: t('integrations.snowAdmin.time'),
      width: 160,
      nowrap: true,
      sortable: true,
      sortValue: (log) => log.started_at,
      render: (log) => (
        <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
          {formatDateTime(log.started_at)}
        </span>
      ),
    },
    {
      key: 'operation',
      header: t('integrations.snowAdmin.operation'),
      nowrap: true,
      sortable: true,
      sortValue: (log) => log.operation,
      render: (log) => <span style={{ fontSize: 'var(--fs-md)' }}>{log.operation}</span>,
    },
    {
      key: 'method',
      header: t('integrations.snowAdmin.method'),
      width: 90,
      render: (log) => (
        <Pill tone={METHOD_TONE[log.method] ?? 'n'} dot={false} className="mono">
          {log.method}
        </Pill>
      ),
    },
    {
      key: 'endpoint',
      header: t('integrations.snowAdmin.endpoint'),
      render: (log) => (
        <span className="faint mono trunc" style={{ display: 'block', maxWidth: 220, fontSize: 'var(--fs-xs)' }}>
          {log.endpoint}
        </span>
      ),
    },
    {
      key: 'status',
      header: t('common.status'),
      width: 100,
      sortable: true,
      sortValue: (log) => (log.is_success ? 0 : 1),
      render: (log) =>
        log.is_success ? (
          <Pill tone="ok" dot={false}>
            <CheckCircleIcon style={{ width: 12, height: 12, flexShrink: 0 }} aria-hidden />
            {log.status_code || 'OK'}
          </Pill>
        ) : (
          <Pill tone="da" dot={false}>
            <XCircleIcon style={{ width: 12, height: 12, flexShrink: 0 }} aria-hidden />
            {log.status_code || t('integrations.snowAdmin.error')}
          </Pill>
        ),
    },
    {
      key: 'duration',
      header: t('integrations.snowAdmin.duration'),
      width: 100,
      nowrap: true,
      sortable: true,
      sortValue: (log) => log.duration_ms,
      render: (log) => (
        <span className="faint num" style={{ fontSize: 'var(--fs-sm)' }}>
          {log.duration_ms !== null ? `${log.duration_ms}ms` : '-'}
        </span>
      ),
    },
    {
      key: 'error',
      header: t('integrations.snowAdmin.error'),
      render: (log) => (
        <span className="trunc" style={{ display: 'block', maxWidth: 220, fontSize: 'var(--fs-xs)', color: log.error_message ? 'var(--da)' : 'var(--f)' }}>
          {log.error_message || '-'}
        </span>
      ),
    },
  ]

  if (overviewLoading) {
    return (
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (overviewError) {
    return (
      <div className="banner banner-da">
        <XCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
        <span>{t('integrations.snowAdmin.loadError')}</span>
      </div>
    )
  }

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>
          {t('integrations.snowAdmin.title')}
        </h1>
        <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>
          {t('integrations.snowAdmin.subtitle')}
        </p>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Stat icon={ServerIcon} label={t('integrations.snowAdmin.totalConfigurations')} value={totalConfigs} />
        <Stat icon={CheckCircleIcon} label={t('integrations.health.healthy')} value={healthyCount} />
        <Stat
          icon={XCircleIcon}
          label={t('integrations.health.unhealthy')}
          value={unhealthyCount}
          sub={unhealthyCount > 0 ? t('integrations.snowAdmin.needsAttention', { defaultValue: 'needs attention' }) : undefined}
          subTone="var(--da)"
        />
        <Stat icon={ArrowPathIcon} label={t('integrations.snowAdmin.totalRequests')} value={totalSyncs} />
      </div>

      {/* Tenant configurations */}
      <div className="col" style={{ gap: 8 }}>
        <span className="sec-t row" style={{ gap: 6 }}>
          <CloudArrowUpIcon style={{ width: 15, height: 15, color: 'var(--p)', flexShrink: 0 }} aria-hidden />
          {t('integrations.snowAdmin.tenantConfigurations')}
        </span>
        <Table
          columns={tenantColumns}
          rows={overview ?? []}
          rowKey={(row) => row.tenant_id}
          minWidth={860}
          empty={
            <EmptyState
              icon={ServerIcon}
              title={t('integrations.snowAdmin.noTenantData')}
            />
          }
        />
      </div>

      {/* Recent integration logs */}
      <div className="col" style={{ gap: 8 }}>
        <span className="sec-t row" style={{ gap: 6 }}>
          <DocumentTextIcon style={{ width: 15, height: 15, color: 'var(--p)', flexShrink: 0 }} aria-hidden />
          {t('integrations.snowAdmin.recentLogs')}
        </span>
        {logsLoading ? (
          <div className="row" style={{ justifyContent: 'center', height: 128 }}>
            <LoadingSpinner size="lg" />
          </div>
        ) : (
          <Table
            columns={logColumns}
            rows={logs ?? []}
            rowKey={(log) => log.id}
            minWidth={960}
            empty={
              <EmptyState
                icon={DocumentTextIcon}
                title={t('integrations.snowAdmin.noLogs')}
              />
            }
          />
        )}
      </div>
    </div>
  )
}
