import { useState } from 'react'
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
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn, formatDateTime } from '@/lib/utils'
import type { SchedulerJob, SchedulerJobHistory, SchedulerJobUpdate } from '@/types/admin'

const STATUS_COLORS = {
  success: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  running: 'bg-blue-100 text-blue-700',
  skipped: 'bg-yellow-100 text-yellow-700',
}

const STATUS_ICONS = {
  success: CheckCircleIcon,
  failed: XCircleIcon,
  running: ArrowPathIcon,
  skipped: ExclamationTriangleIcon,
}

export default function SchedulerPage() {
  const queryClient = useQueryClient()
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

  // Mutations
  const startMutation = useMutation({
    mutationFn: () => api.startScheduler(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduler-status'] })
    },
  })

  const stopMutation = useMutation({
    mutationFn: () => api.stopScheduler(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduler-status'] })
    },
  })

  const triggerMutation = useMutation({
    mutationFn: (jobName: string) => api.triggerSchedulerJob(jobName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduler-jobs'] })
      queryClient.invalidateQueries({ queryKey: ['scheduler-job-history'] })
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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Scheduler</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage background jobs and scheduled tasks
          </p>
        </div>
        <div className="flex items-center gap-3">
          {status?.is_running ? (
            <button
              onClick={() => stopMutation.mutate()}
              disabled={stopMutation.isPending}
              className="btn-secondary text-red-600 hover:text-red-700 hover:border-red-300"
            >
              {stopMutation.isPending ? (
                <LoadingSpinner size="sm" />
              ) : (
                <PauseIcon className="h-4 w-4 mr-2" />
              )}
              Stop Scheduler
            </button>
          ) : (
            <button
              onClick={() => startMutation.mutate()}
              disabled={startMutation.isPending}
              className="btn-primary"
            >
              {startMutation.isPending ? (
                <LoadingSpinner size="sm" className="border-white border-t-transparent" />
              ) : (
                <PlayIcon className="h-4 w-4 mr-2" />
              )}
              Start Scheduler
            </button>
          )}
        </div>
      </div>

      {/* Status Cards */}
      {isLoading ? (
        <div className="flex items-center justify-center h-32">
          <LoadingSpinner size="lg" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Scheduler Status */}
          <div className="card p-4">
            <div className="flex items-center gap-3">
              <div
                className={cn(
                  'h-10 w-10 rounded-lg flex items-center justify-center',
                  status?.is_running ? 'bg-green-100' : 'bg-gray-100'
                )}
              >
                {status?.is_running ? (
                  <PlayIcon className="h-5 w-5 text-green-600" />
                ) : (
                  <PauseIcon className="h-5 w-5 text-gray-400" />
                )}
              </div>
              <div>
                <p className="text-sm text-gray-500">Status</p>
                <p className={cn('font-semibold', status?.is_running ? 'text-green-600' : 'text-gray-500')}>
                  {status?.is_running ? 'Running' : 'Stopped'}
                </p>
              </div>
            </div>
          </div>

          {/* Total Jobs */}
          <div className="card p-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center">
                <ClockIcon className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Total Jobs</p>
                <p className="font-semibold text-gray-900">{status?.total_jobs || 0}</p>
              </div>
            </div>
          </div>

          {/* Enabled Jobs */}
          <div className="card p-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-green-100 flex items-center justify-center">
                <CheckCircleIcon className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Enabled</p>
                <p className="font-semibold text-gray-900">{status?.enabled_jobs || 0}</p>
              </div>
            </div>
          </div>

          {/* Next Run */}
          <div className="card p-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-purple-100 flex items-center justify-center">
                <ArrowPathIcon className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Next Run</p>
                <p className="font-semibold text-gray-900 text-sm">
                  {status?.next_job_name || '-'}
                </p>
                {status?.next_job_run && (
                  <p className="text-xs text-gray-500">
                    {new Date(status.next_job_run).toLocaleTimeString()}
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Jobs List */}
      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
          <h3 className="text-sm font-medium text-gray-900">Scheduled Jobs</h3>
        </div>
        <div className="divide-y divide-gray-200">
          {jobs?.items.map((job) => (
            <div key={job.id} className="bg-white">
              {/* Job Row */}
              <div className="px-4 py-4 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <button
                    onClick={() => setExpandedJob(expandedJob === job.job_name ? null : job.job_name)}
                    className="p-1 text-gray-400 hover:text-gray-600"
                  >
                    {expandedJob === job.job_name ? (
                      <ChevronUpIcon className="h-5 w-5" />
                    ) : (
                      <ChevronDownIcon className="h-5 w-5" />
                    )}
                  </button>
                  <div>
                    <p className="font-medium text-gray-900">{job.job_name}</p>
                    <p className="text-sm text-gray-500">{job.description || job.job_type}</p>
                  </div>
                </div>

                <div className="flex items-center gap-6">
                  {/* Last Run Status */}
                  {job.last_run_status && (
                    <div className="flex items-center gap-2">
                      {(() => {
                        const Icon = STATUS_ICONS[job.last_run_status]
                        return (
                          <span
                            className={cn(
                              'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium',
                              STATUS_COLORS[job.last_run_status]
                            )}
                          >
                            <Icon className={cn('h-3 w-3', job.last_run_status === 'running' && 'animate-spin')} />
                            {job.last_run_status}
                          </span>
                        )
                      })()}
                      <span className="text-xs text-gray-500">
                        {formatDuration(job.last_run_duration_ms)}
                      </span>
                    </div>
                  )}

                  {/* Interval */}
                  <div className="text-sm text-gray-500">
                    Every {formatInterval(job.interval_seconds)}
                  </div>

                  {/* Stats */}
                  <div className="text-xs text-gray-500">
                    <span className="text-green-600">{job.successful_runs}</span>
                    {' / '}
                    <span className="text-red-600">{job.failed_runs}</span>
                    {' / '}
                    <span>{job.total_runs}</span>
                  </div>

                  {/* Toggle */}
                  <button
                    onClick={() => toggleEnabled(job)}
                    disabled={updateMutation.isPending}
                    className={cn(
                      'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
                      job.is_enabled ? 'bg-primary-600' : 'bg-gray-200'
                    )}
                  >
                    <span
                      className={cn(
                        'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out',
                        job.is_enabled ? 'translate-x-5' : 'translate-x-0'
                      )}
                    />
                  </button>

                  {/* Trigger Button */}
                  <button
                    onClick={() => triggerMutation.mutate(job.job_name)}
                    disabled={triggerMutation.isPending || job.last_run_status === 'running'}
                    className="btn-secondary text-sm py-1 px-3"
                  >
                    {triggerMutation.isPending ? (
                      <LoadingSpinner size="sm" />
                    ) : (
                      <>
                        <PlayIcon className="h-4 w-4 mr-1" />
                        Run Now
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Expanded Section */}
              {expandedJob === job.job_name && (
                <div className="px-4 pb-4 bg-gray-50 border-t border-gray-100">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4">
                    {/* Job Details */}
                    <div>
                      <h4 className="text-sm font-medium text-gray-900 mb-3">Job Details</h4>
                      <dl className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <dt className="text-gray-500">Last Run:</dt>
                          <dd className="text-gray-900">
                            {job.last_run_at ? formatDateTime(job.last_run_at) : 'Never'}
                          </dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-gray-500">Next Run:</dt>
                          <dd className="text-gray-900">
                            {job.next_run_at ? formatDateTime(job.next_run_at) : '-'}
                          </dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-gray-500">Total Runs:</dt>
                          <dd className="text-gray-900">{job.total_runs}</dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-gray-500">Success Rate:</dt>
                          <dd className="text-gray-900">
                            {job.total_runs > 0
                              ? `${((job.successful_runs / job.total_runs) * 100).toFixed(1)}%`
                              : '-'}
                          </dd>
                        </div>
                      </dl>

                      {/* Update Interval */}
                      <div className="mt-4 pt-4 border-t border-gray-200">
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Update Interval
                        </label>
                        <div className="flex gap-2">
                          <input
                            type="number"
                            min="60"
                            value={editingJob?.id === job.id ? intervalInput : ''}
                            onChange={(e) => {
                              setEditingJob(job)
                              setIntervalInput(e.target.value)
                            }}
                            placeholder={`Current: ${job.interval_seconds}s`}
                            className="input flex-1"
                          />
                          <button
                            onClick={() => handleUpdateInterval(job)}
                            disabled={updateMutation.isPending || !intervalInput}
                            className="btn-primary text-sm"
                          >
                            Update
                          </button>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">Minimum 60 seconds</p>
                      </div>

                      {/* Last Error */}
                      {job.last_run_error && (
                        <div className="mt-4 p-3 bg-red-50 rounded-lg">
                          <p className="text-sm font-medium text-red-700">Last Error</p>
                          <p className="text-xs text-red-600 mt-1 font-mono">{job.last_run_error}</p>
                        </div>
                      )}
                    </div>

                    {/* Run History */}
                    <div>
                      <h4 className="text-sm font-medium text-gray-900 mb-3">Recent Runs</h4>
                      <div className="space-y-2 max-h-64 overflow-y-auto">
                        {jobHistory?.items.length === 0 ? (
                          <p className="text-sm text-gray-500">No execution history</p>
                        ) : (
                          jobHistory?.items.slice(0, 10).map((history: SchedulerJobHistory) => {
                            const Icon = STATUS_ICONS[history.status]
                            return (
                              <div
                                key={history.id}
                                className="flex items-center justify-between py-2 px-3 bg-white rounded border border-gray-200"
                              >
                                <div className="flex items-center gap-2">
                                  <Icon
                                    className={cn(
                                      'h-4 w-4',
                                      history.status === 'success' && 'text-green-500',
                                      history.status === 'failed' && 'text-red-500',
                                      history.status === 'running' && 'text-blue-500 animate-spin',
                                      history.status === 'skipped' && 'text-yellow-500'
                                    )}
                                  />
                                  <span className="text-xs text-gray-500">
                                    {formatDateTime(history.started_at)}
                                  </span>
                                </div>
                                <div className="flex items-center gap-2">
                                  {history.items_processed !== null && (
                                    <span className="text-xs text-gray-500">
                                      {history.items_processed} items
                                    </span>
                                  )}
                                  <span className="text-xs text-gray-500">
                                    {formatDuration(history.duration_ms)}
                                  </span>
                                </div>
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
        </div>
        {jobs?.items.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            No scheduled jobs found.
          </div>
        )}
      </div>
    </div>
  )
}
