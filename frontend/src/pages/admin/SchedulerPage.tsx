/* Scheduler admin — Direction B redesign.
   Header with start/stop Button → Stat cards (state, totals, next run) →
   system-health card (service dots, Bar gauges, info grid) → job list in a
   tbl-w (status Pills, Switch toggles, run-now Buttons with toasts, expandable
   details with interval Field and mono error/history blocks). Queries,
   mutations, 10s/30s polling, expansion state and i18n are unchanged from the
   pre-redesign page. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  PlayIcon,
  PauseIcon,
  ArrowPathIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  CpuChipIcon,
  CircleStackIcon,
  ServerIcon,
  SignalIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { Bar, Button, IconButton, Field, Pill, Stat, Switch, useToast } from '@/components/ui'
import type { PillTone } from '@/components/ui'
import { cn, formatDateTime } from '@/lib/utils'
import type {
  SchedulerJob,
  SchedulerJobHistory,
  SchedulerJobStatus,
  SchedulerJobUpdate,
  SystemHealthService,
} from '@/types/admin'

const STATUS_TONES: Record<SchedulerJobStatus, PillTone> = {
  success: 'ok',
  failed: 'da',
  running: 'in',
  skipped: 'wa',
}

const STATUS_VARS: Record<SchedulerJobStatus, string> = {
  success: 'var(--ok)',
  failed: 'var(--da)',
  running: 'var(--in)',
  skipped: 'var(--wa)',
}

const STATUS_ICONS = {
  success: CheckCircleIcon,
  failed: XCircleIcon,
  running: ArrowPathIcon,
  skipped: ExclamationTriangleIcon,
}

/** Gauge fill color by utilisation thresholds (token vars only). */
const gaugeTone = (value: number, warnAt: number, dangerAt: number) =>
  value > dangerAt ? 'var(--da)' : value > warnAt ? 'var(--wa)' : undefined

export default function SchedulerPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [expandedJob, setExpandedJob] = useState<string | null>(null)
  const [editingJob, setEditingJob] = useState<SchedulerJob | null>(null)
  const [intervalInput, setIntervalInput] = useState('')

  // Queries
  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ['scheduler-status'],
    queryFn: () => api.getSchedulerStatus(),
    refetchInterval: 10000, // Refresh every 10 seconds
  })

  const { data: jobs, isLoading: jobsLoading } = useQuery({
    queryKey: ['scheduler-jobs'],
    queryFn: () => api.getSchedulerJobs(),
    refetchInterval: 10000,
  })

  const { data: jobHistory } = useQuery({
    queryKey: ['scheduler-job-history', expandedJob],
    queryFn: () => (expandedJob ? api.getSchedulerJobHistory(expandedJob) : null),
    enabled: !!expandedJob,
  })

  // System Health query
  const { data: systemHealth, isLoading: healthLoading } = useQuery({
    queryKey: ['system-health'],
    queryFn: () => api.getSystemHealth(),
    refetchInterval: 30000, // Refresh every 30 seconds
  })

  // Mutations
  const startMutation = useMutation({
    mutationFn: () => api.startScheduler(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduler-status'] })
      toast({ text: t('scheduler.startedToast', { defaultValue: 'Scheduler started' }) })
    },
    onError: (err: Error) => {
      toast({ text: err.message || t('scheduler.startFailedToast', { defaultValue: 'Failed to start scheduler' }), error: true })
    },
  })

  const stopMutation = useMutation({
    mutationFn: () => api.stopScheduler(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduler-status'] })
      toast({ text: t('scheduler.stoppedToast', { defaultValue: 'Scheduler stopped' }) })
    },
    onError: (err: Error) => {
      toast({ text: err.message || t('scheduler.stopFailedToast', { defaultValue: 'Failed to stop scheduler' }), error: true })
    },
  })

  const triggerMutation = useMutation({
    mutationFn: (jobName: string) => api.triggerSchedulerJob(jobName),
    onSuccess: (_res, jobName) => {
      queryClient.invalidateQueries({ queryKey: ['scheduler-jobs'] })
      queryClient.invalidateQueries({ queryKey: ['scheduler-job-history'] })
      toast({ text: t('scheduler.triggeredToast', { defaultValue: '{{name}} triggered', name: jobName }) })
    },
    onError: (err: Error, jobName) => {
      toast({
        text: err.message || t('scheduler.triggerFailedToast', { defaultValue: 'Failed to trigger {{name}}', name: jobName }),
        error: true,
      })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ jobName, data }: { jobName: string; data: SchedulerJobUpdate }) =>
      api.updateSchedulerJob(jobName, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduler-jobs'] })
      setEditingJob(null)
    },
  })

  const toggleEnabled = (job: SchedulerJob) => {
    updateMutation.mutate({
      jobName: job.job_name,
      data: { is_enabled: !job.is_enabled },
    })
  }

  const handleUpdateInterval = (job: SchedulerJob) => {
    const seconds = parseInt(intervalInput)
    if (seconds >= 60) {
      updateMutation.mutate({
        jobName: job.job_name,
        data: { interval_seconds: seconds },
      })
    }
  }

  const formatDuration = (ms: number | null) => {
    if (ms === null) return '-'
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(1)}s`
  }

  const formatInterval = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
  }

  const isLoading = statusLoading || jobsLoading

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div className="row" style={{ alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>
            {t('nav.scheduler')}
          </h1>
          <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>
            {t('scheduler.subtitle')}
          </p>
        </div>
        {status?.is_running ? (
          <Button
            variant="danger-ghost"
            icon={PauseIcon}
            onClick={() => stopMutation.mutate()}
            disabled={stopMutation.isPending}
          >
            {t('scheduler.stopScheduler')}
          </Button>
        ) : (
          <Button
            variant="primary"
            icon={PlayIcon}
            onClick={() => startMutation.mutate()}
            disabled={startMutation.isPending}
          >
            {t('scheduler.startScheduler')}
          </Button>
        )}
      </div>

      {/* Status cards */}
      {isLoading ? (
        <div className="row" style={{ justifyContent: 'center', height: 128 }}>
          <LoadingSpinner size="lg" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <Stat
            icon={status?.is_running ? PlayIcon : PauseIcon}
            label={t('common.status')}
            value={
              <span style={{ color: status?.is_running ? 'var(--ok)' : 'var(--f)' }}>
                {status?.is_running ? t('scheduler.running') : t('scheduler.stopped')}
              </span>
            }
          />
          <Stat icon={ClockIcon} label={t('scheduler.totalJobs')} value={status?.total_jobs || 0} />
          <Stat icon={CheckCircleIcon} label={t('scheduler.enabled')} value={status?.enabled_jobs || 0} />
          <Stat
            icon={ArrowPathIcon}
            label={t('scheduler.nextRun')}
            value={
              <span className="trunc" style={{ display: 'block', fontSize: 'var(--fs-xl)' }}>
                {status?.next_job_name || '-'}
              </span>
            }
            sub={status?.next_job_run ? new Date(status.next_job_run).toLocaleTimeString() : undefined}
          />
        </div>
      )}

      {/* System health */}
      <div className="card">
        <div
          className="row"
          style={{ padding: '10px 16px', borderBottom: '1px solid var(--b)', gap: 10 }}
        >
          <h3 className="sec-t grow">{t('scheduler.systemHealth')}</h3>
          {systemHealth && (
            <Pill tone={systemHealth.status === 'healthy' ? 'ok' : 'wa'} dot={false}>
              <SignalIcon style={{ width: 12, height: 12, flexShrink: 0 }} aria-hidden />
              {systemHealth.status === 'healthy' ? t('scheduler.allSystemsOperational') : t('scheduler.degraded')}
            </Pill>
          )}
        </div>

        {healthLoading ? (
          <div className="row" style={{ justifyContent: 'center', height: 128 }}>
            <LoadingSpinner size="lg" />
          </div>
        ) : systemHealth ? (
          <div className="col" style={{ padding: 16, gap: 20 }}>
            {/* Services status */}
            <div>
              <h4 className="sec-t" style={{ marginBottom: 10 }}>{t('scheduler.services')}</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {(Object.entries(systemHealth.services) as [string, SystemHealthService][]).map(([name, service]) => (
                  <div
                    key={name}
                    className="row"
                    style={{
                      gap: 8,
                      padding: '10px 12px',
                      background: 'var(--s2)',
                      borderRadius: 'var(--r-md)',
                    }}
                  >
                    <span
                      style={{
                        width: 9,
                        height: 9,
                        borderRadius: 'var(--r-full)',
                        flexShrink: 0,
                        background:
                          service.status === 'healthy' ? 'var(--ok)' :
                          service.status === 'not_configured' ? 'var(--f)' : 'var(--da)',
                      }}
                    />
                    <span className="grow" style={{ minWidth: 0 }}>
                      <span className="trunc capitalize" style={{ display: 'block', fontWeight: 500, fontSize: 'var(--fs-md)' }}>
                        {name}
                      </span>
                      <span className="faint trunc" style={{ display: 'block', fontSize: 'var(--fs-sm)' }}>
                        {service.type}
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Infrastructure metrics */}
            <div>
              <h4 className="sec-t" style={{ marginBottom: 10 }}>{t('scheduler.infrastructure')}</h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {/* CPU */}
                <div style={{ padding: 14, background: 'var(--s2)', borderRadius: 'var(--r-md)' }}>
                  <div className="row" style={{ gap: 8, color: 'var(--m)', fontSize: 'var(--fs-sm)', fontWeight: 500 }}>
                    <CpuChipIcon style={{ width: 15, height: 15, flexShrink: 0 }} aria-hidden />
                    {t('scheduler.cpuUsage')}
                  </div>
                  <div className="num" style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600, marginTop: 8 }}>
                    {systemHealth.system.cpu_percent.toFixed(1)}%
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <Bar
                      value={systemHealth.system.cpu_percent}
                      width="100%"
                      tone={gaugeTone(systemHealth.system.cpu_percent, 50, 80)}
                    />
                  </div>
                </div>

                {/* Memory */}
                <div style={{ padding: 14, background: 'var(--s2)', borderRadius: 'var(--r-md)' }}>
                  <div className="row" style={{ gap: 8, color: 'var(--m)', fontSize: 'var(--fs-sm)', fontWeight: 500 }}>
                    <ServerIcon style={{ width: 15, height: 15, flexShrink: 0 }} aria-hidden />
                    {t('scheduler.memory')}
                  </div>
                  <div className="row" style={{ gap: 8, alignItems: 'baseline', marginTop: 8 }}>
                    <span className="num" style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600 }}>
                      {systemHealth.system.memory.percent.toFixed(1)}%
                    </span>
                    <span className="faint num" style={{ fontSize: 'var(--fs-sm)' }}>
                      {systemHealth.system.memory.used_gb.toFixed(1)} / {systemHealth.system.memory.total_gb.toFixed(1)} GB
                    </span>
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <Bar
                      value={systemHealth.system.memory.percent}
                      width="100%"
                      tone={gaugeTone(systemHealth.system.memory.percent, 70, 85)}
                    />
                  </div>
                </div>

                {/* Disk */}
                <div style={{ padding: 14, background: 'var(--s2)', borderRadius: 'var(--r-md)' }}>
                  <div className="row" style={{ gap: 8, color: 'var(--m)', fontSize: 'var(--fs-sm)', fontWeight: 500 }}>
                    <CircleStackIcon style={{ width: 15, height: 15, flexShrink: 0 }} aria-hidden />
                    {t('scheduler.disk')}
                  </div>
                  <div className="row" style={{ gap: 8, alignItems: 'baseline', marginTop: 8 }}>
                    <span className="num" style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600 }}>
                      {systemHealth.system.disk.percent.toFixed(1)}%
                    </span>
                    <span className="faint num" style={{ fontSize: 'var(--fs-sm)' }}>
                      {systemHealth.system.disk.used_gb.toFixed(1)} / {systemHealth.system.disk.total_gb.toFixed(1)} GB
                    </span>
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <Bar
                      value={systemHealth.system.disk.percent}
                      width="100%"
                      tone={gaugeTone(systemHealth.system.disk.percent, 75, 90)}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Additional info */}
            <div
              className="grid grid-cols-2 md:grid-cols-4 gap-4"
              style={{ paddingTop: 14, borderTop: '1px solid var(--b)' }}
            >
              <div>
                <p className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('scheduler.version')}</p>
                <p style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>{systemHealth.version}</p>
              </div>
              <div>
                <p className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('scheduler.environment')}</p>
                <p className="capitalize" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>{systemHealth.environment}</p>
              </div>
              <div>
                <p className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('scheduler.systemUptime')}</p>
                <p className="num" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                  {t('scheduler.hours', { value: systemHealth.system.uptime_hours.toFixed(1) })}
                </p>
              </div>
              <div>
                <p className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('scheduler.processMemory')}</p>
                <p className="num" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                  {systemHealth.process.memory_mb.toFixed(1)} MB
                </p>
              </div>
              {systemHealth.services.database.contracts !== undefined && (
                <div>
                  <p className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('scheduler.contractsInDb')}</p>
                  <p className="num" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                    {systemHealth.services.database.contracts}
                  </p>
                </div>
              )}
              {systemHealth.services.database.database_size_mb !== undefined && (
                <div>
                  <p className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('scheduler.databaseSize')}</p>
                  <p className="num" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                    {systemHealth.services.database.database_size_mb} MB
                  </p>
                </div>
              )}
              {systemHealth.services.chromadb.document_count !== undefined && (
                <div>
                  <p className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('scheduler.vectorDocuments')}</p>
                  <p className="num" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                    {systemHealth.services.chromadb.document_count}
                  </p>
                </div>
              )}
              <div>
                <p className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('scheduler.aiAgents')}</p>
                <p className="num" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                  {t('scheduler.registered', { count: systemHealth.agents.registered })}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="muted" style={{ padding: 16, textAlign: 'center' }}>
            {t('scheduler.healthLoadFailed')}
          </div>
        )}
      </div>

      {/* Jobs list */}
      <div className="tbl-w">
        <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--b)', background: 'var(--s3)' }}>
          <h3 className="sec-t">{t('scheduler.scheduledJobs')}</h3>
        </div>
        {jobs?.items.map((job) => (
          <div key={job.id} style={{ borderBottom: '1px solid var(--b)' }}>
            {/* Job row */}
            <div className="row" style={{ padding: '12px 16px', gap: 12, flexWrap: 'wrap' }}>
              <IconButton
                icon={expandedJob === job.job_name ? ChevronUpIcon : ChevronDownIcon}
                size="sm"
                label={job.job_name}
                onClick={() => setExpandedJob(expandedJob === job.job_name ? null : job.job_name)}
              />
              <span className="grow" style={{ minWidth: 160 }}>
                <span className="trunc" style={{ display: 'block', fontWeight: 500 }}>{job.job_name}</span>
                <span className="faint trunc" style={{ display: 'block', fontSize: 'var(--fs-sm)' }}>
                  {job.description || job.job_type}
                </span>
              </span>

              {/* Last run status */}
              {job.last_run_status && (
                <span className="row" style={{ gap: 8, flexShrink: 0 }}>
                  {(() => {
                    const Icon = STATUS_ICONS[job.last_run_status]
                    return (
                      <Pill tone={STATUS_TONES[job.last_run_status]} dot={false}>
                        <Icon
                          className={cn(job.last_run_status === 'running' && 'animate-spin')}
                          style={{ width: 12, height: 12, flexShrink: 0 }}
                          aria-hidden
                        />
                        {t(`scheduler.jobStatus.${job.last_run_status}`, { defaultValue: job.last_run_status })}
                      </Pill>
                    )
                  })()}
                  <span className="faint num" style={{ fontSize: 'var(--fs-sm)' }}>
                    {formatDuration(job.last_run_duration_ms)}
                  </span>
                </span>
              )}

              {/* Interval */}
              <span className="muted num" style={{ fontSize: 'var(--fs-sm)', flexShrink: 0 }}>
                {t('scheduler.every', { interval: formatInterval(job.interval_seconds) })}
              </span>

              {/* ok / failed / total run counts */}
              <span className="num" style={{ fontSize: 'var(--fs-xs)', flexShrink: 0 }}>
                <span style={{ color: 'var(--ok)' }}>{job.successful_runs}</span>
                <span className="faint">{' / '}</span>
                <span style={{ color: 'var(--da)' }}>{job.failed_runs}</span>
                <span className="faint">{' / '}</span>
                <span className="muted">{job.total_runs}</span>
              </span>

              <Switch
                checked={job.is_enabled}
                disabled={updateMutation.isPending}
                onChange={() => toggleEnabled(job)}
              />

              <Button
                variant="secondary"
                size="sm"
                icon={PlayIcon}
                onClick={() => triggerMutation.mutate(job.job_name)}
                disabled={triggerMutation.isPending || job.last_run_status === 'running'}
              >
                {t('scheduler.runNow')}
              </Button>
            </div>

            {/* Expanded section */}
            {expandedJob === job.job_name && (
              <div
                style={{ padding: '14px 16px', background: 'var(--s3)', borderTop: '1px solid var(--b)' }}
              >
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Job details */}
                  <div>
                    <h4 className="sec-t" style={{ marginBottom: 10 }}>{t('scheduler.jobDetails')}</h4>
                    <dl className="col" style={{ gap: 6, fontSize: 'var(--fs-md)' }}>
                      <div className="row" style={{ justifyContent: 'space-between' }}>
                        <dt className="muted">{t('scheduler.lastRun')}:</dt>
                        <dd className="num">
                          {job.last_run_at ? formatDateTime(job.last_run_at) : t('scheduler.never')}
                        </dd>
                      </div>
                      <div className="row" style={{ justifyContent: 'space-between' }}>
                        <dt className="muted">{t('scheduler.nextRun')}:</dt>
                        <dd className="num">{job.next_run_at ? formatDateTime(job.next_run_at) : '-'}</dd>
                      </div>
                      <div className="row" style={{ justifyContent: 'space-between' }}>
                        <dt className="muted">{t('scheduler.totalRuns')}:</dt>
                        <dd className="num">{job.total_runs}</dd>
                      </div>
                      <div className="row" style={{ justifyContent: 'space-between' }}>
                        <dt className="muted">{t('scheduler.successRate')}:</dt>
                        <dd className="num">
                          {job.total_runs > 0
                            ? `${((job.successful_runs / job.total_runs) * 100).toFixed(1)}%`
                            : '-'}
                        </dd>
                      </div>
                    </dl>

                    {/* Update interval */}
                    <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--b)' }}>
                      <div className="row" style={{ gap: 8, alignItems: 'flex-end' }}>
                        <Field
                          label={t('scheduler.updateInterval')}
                          type="number"
                          min="60"
                          value={editingJob?.id === job.id ? intervalInput : ''}
                          onChange={(e) => {
                            setEditingJob(job)
                            setIntervalInput(e.target.value)
                          }}
                          placeholder={t('scheduler.currentInterval', { seconds: job.interval_seconds })}
                          containerClassName="grow"
                        />
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => handleUpdateInterval(job)}
                          disabled={updateMutation.isPending || !intervalInput}
                        >
                          {t('scheduler.update')}
                        </Button>
                      </div>
                      <p className="faint" style={{ fontSize: 'var(--fs-xs)', marginTop: 4 }}>
                        {t('scheduler.minimumSeconds')}
                      </p>
                    </div>

                    {/* Last error — mono log block */}
                    {job.last_run_error && (
                      <div className="banner banner-da" style={{ marginTop: 14, flexDirection: 'column', gap: 4 }}>
                        <b style={{ fontSize: 'var(--fs-sm)' }}>{t('scheduler.lastError')}</b>
                        <span className="mono" style={{ fontSize: 'var(--fs-xs)', wordBreak: 'break-word' }}>
                          {job.last_run_error}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Run history */}
                  <div>
                    <h4 className="sec-t" style={{ marginBottom: 10 }}>{t('scheduler.recentRuns')}</h4>
                    <div className="col" style={{ gap: 6, maxHeight: 256, overflowY: 'auto' }}>
                      {jobHistory?.items.length === 0 ? (
                        <p className="muted" style={{ fontSize: 'var(--fs-md)' }}>{t('scheduler.noHistory')}</p>
                      ) : (
                        jobHistory?.items.slice(0, 10).map((history: SchedulerJobHistory) => {
                          const Icon = STATUS_ICONS[history.status]
                          return (
                            <div
                              key={history.id}
                              className="row"
                              style={{
                                justifyContent: 'space-between',
                                gap: 8,
                                padding: '7px 10px',
                                background: 'var(--s)',
                                border: '1px solid var(--b)',
                                borderRadius: 'var(--r-sm)',
                              }}
                            >
                              <span className="row" style={{ gap: 8 }}>
                                <Icon
                                  className={cn(history.status === 'running' && 'animate-spin')}
                                  style={{ width: 15, height: 15, flexShrink: 0, color: STATUS_VARS[history.status] }}
                                  aria-hidden
                                />
                                <span className="faint mono num" style={{ fontSize: 'var(--fs-xs)' }}>
                                  {formatDateTime(history.started_at)}
                                </span>
                              </span>
                              <span className="row" style={{ gap: 8 }}>
                                {history.items_processed !== null && (
                                  <span className="faint num" style={{ fontSize: 'var(--fs-xs)' }}>
                                    {t('scheduler.itemsProcessed', { count: history.items_processed })}
                                  </span>
                                )}
                                <span className="faint mono num" style={{ fontSize: 'var(--fs-xs)' }}>
                                  {formatDuration(history.duration_ms)}
                                </span>
                              </span>
                            </div>
                          )
                        })
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
        {jobs?.items.length === 0 && (
          <div className="muted" style={{ padding: '48px 16px', textAlign: 'center' }}>
            {t('scheduler.noJobs')}
          </div>
        )}
      </div>
    </div>
  )
}
