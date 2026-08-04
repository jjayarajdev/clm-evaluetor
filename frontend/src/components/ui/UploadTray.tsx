/* Floating bottom-right upload status tray (Direction B).
   Renders the global upload/processing queue from UploadContext on every
   authenticated route, so navigating away from the upload page never loses
   upload status. Hidden when no jobs exist.
   z-index 110: above drawers (85) and tooltips (90), below the toast (120). */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  ArrowPathIcon,
  ArrowUpTrayIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  DocumentTextIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import { Bar, Button, IconButton, Pill } from '@/components/ui'
import type { PillTone } from '@/components/ui'
import { PIPELINE_STAGES, isActiveJob, useUploads } from '@/contexts/UploadContext'
import type { UploadJob, UploadJobState } from '@/contexts/UploadContext'
import { formatFileSize } from '@/lib/utils'

const STATE_PILL: Record<UploadJobState, { tone: PillTone; labelKey: string; defaultLabel: string }> = {
  queued: { tone: 'in', labelKey: 'upload.trayQueued', defaultLabel: 'Queued' },
  uploading: { tone: 'in', labelKey: 'upload.trayUploadingState', defaultLabel: 'Uploading' },
  processing: { tone: 'p', labelKey: 'upload.trayProcessingState', defaultLabel: 'Processing' },
  completed: { tone: 'ok', labelKey: 'upload.trayCompleted', defaultLabel: 'Done' },
  failed: { tone: 'da', labelKey: 'upload.trayFailed', defaultLabel: 'Failed' },
  duplicate: { tone: 'wa', labelKey: 'upload.trayDuplicate', defaultLabel: 'Duplicate' },
}

function TrayRow({ job }: { job: UploadJob }) {
  const { t } = useTranslation()
  const { retryProcessing, dismissJob } = useUploads()

  const pill = STATE_PILL[job.state]
  const stageIdx = job.stage ? PIPELINE_STAGES.findIndex((s) => s.id === job.stage) : -1
  const stageLabel = stageIdx >= 0 ? t(PIPELINE_STAGES[stageIdx].labelKey) : undefined
  const pct =
    typeof job.progressPercent === 'number'
      ? job.progressPercent
      : stageIdx >= 0
        ? Math.round(((stageIdx + 1) / PIPELINE_STAGES.length) * 100)
        : 0

  return (
    <div className="col" style={{ gap: 5, padding: '8px 12px', borderTop: '1px solid var(--b)' }}>
      <div className="row" style={{ gap: 8 }}>
        <DocumentTextIcon style={{ width: 14, height: 14, flexShrink: 0, color: 'var(--f)' }} aria-hidden />
        <span className="mono trunc grow" style={{ fontSize: 'var(--fs-sm)', fontWeight: 500 }} title={job.fileName}>
          {job.fileName}
        </span>
        <span className="faint num" style={{ fontSize: 'var(--fs-xs)', whiteSpace: 'nowrap' }}>
          {formatFileSize(job.fileSize)}
        </span>
        <Pill tone={pill.tone} className={job.state === 'processing' ? 'pulse' : undefined}>
          {t(pill.labelKey, { defaultValue: pill.defaultLabel })}
        </Pill>
      </div>

      {/* Indeterminate bar while queued/uploading (or duplicate awaiting the worker) */}
      {(job.state === 'queued' || job.state === 'uploading' || job.state === 'duplicate') && (
        <span className="pulse" style={{ display: 'block' }}>
          <Bar value={8} width="100%" />
        </span>
      )}

      {/* Real pipeline progress while processing */}
      {job.state === 'processing' && (
        <>
          <Bar value={pct} width="100%" />
          {stageLabel && (
            <span className="faint trunc" style={{ fontSize: 'var(--fs-xs)' }}>
              {stageLabel}
            </span>
          )}
        </>
      )}

      {job.state === 'completed' && (
        <div className="row" style={{ gap: 8 }}>
          {job.contractId && (
            <Link
              to={`/contracts/${job.contractId}`}
              style={{ fontSize: 'var(--fs-xs)', fontWeight: 600, color: 'var(--p)' }}
            >
              {t('upload.trayViewContract', { defaultValue: 'View contract' })}
            </Link>
          )}
          <span className="grow" />
          <IconButton
            icon={XMarkIcon}
            size="sm"
            label={t('upload.trayDismiss', { defaultValue: 'Dismiss' })}
            onClick={() => dismissJob(job.id)}
          />
        </div>
      )}

      {job.state === 'failed' && (
        <div className="row" style={{ gap: 8 }}>
          <span className="trunc grow" style={{ fontSize: 'var(--fs-xs)', color: 'var(--da)' }} title={job.error}>
            {job.error || t('upload.trayFailed', { defaultValue: 'Failed' })}
          </span>
          {job.contractId && (
            <Button
              variant="ghost"
              size="sm"
              icon={ArrowPathIcon}
              onClick={() => retryProcessing(job.contractId as string)}
            >
              {t('upload.retry')}
            </Button>
          )}
          <IconButton
            icon={XMarkIcon}
            size="sm"
            label={t('upload.trayDismiss', { defaultValue: 'Dismiss' })}
            onClick={() => dismissJob(job.id)}
          />
        </div>
      )}
    </div>
  )
}

export default function UploadTray() {
  const { t } = useTranslation()
  const { jobs, clearFinished } = useUploads()
  const [collapsed, setCollapsed] = useState(false)

  if (jobs.length === 0) return null

  const uploading = jobs.filter((j) => j.state === 'uploading').length
  const processing = jobs.filter(
    (j) => j.state === 'processing' || j.state === 'queued' || j.state === 'duplicate',
  ).length
  const done = jobs.filter((j) => j.state === 'completed').length
  const failed = jobs.filter((j) => j.state === 'failed').length
  const anyActive = jobs.some(isActiveJob)
  const finishedPct = Math.round(((done + failed) / jobs.length) * 100)

  const parts: string[] = []
  if (uploading > 0) parts.push(t('upload.trayUploading', { count: uploading, defaultValue: 'Uploading {{count}}' }))
  if (processing > 0) parts.push(t('upload.trayProcessing', { count: processing, defaultValue: 'Processing {{count}}' }))
  if (done > 0) parts.push(t('upload.trayDone', { count: done, defaultValue: 'Done {{count}}' }))
  if (failed > 0) parts.push(t('upload.trayFailedCount', { count: failed, defaultValue: 'Failed {{count}}' }))
  const summary = parts.join(' · ')

  return (
    <section
      aria-label={t('upload.trayLabel', { defaultValue: 'Upload status' })}
      style={{
        position: 'fixed',
        right: 18,
        bottom: 18,
        zIndex: 110,
        width: 340,
        maxWidth: 'calc(100vw - 36px)',
      }}
    >
      <div className="card col" style={{ boxShadow: 'var(--sh-lg)', overflow: 'hidden' }}>
        {/* Header — always visible; the mini bar is the collapsed summary */}
        <div className="row" style={{ gap: 8, padding: '10px 12px' }}>
          <ArrowUpTrayIcon
            className={anyActive ? 'pulse' : undefined}
            style={{ width: 15, height: 15, flexShrink: 0, color: anyActive ? 'var(--p)' : 'var(--ok)' }}
            aria-hidden
          />
          <div className="col grow" style={{ gap: 4, minWidth: 0 }} role="status" aria-live="polite">
            <b className="trunc" style={{ fontSize: 'var(--fs-sm)' }}>{summary}</b>
            <span className={anyActive ? 'pulse' : undefined} style={{ display: 'block' }}>
              <Bar value={anyActive ? Math.max(finishedPct, 6) : 100} width="100%" tone={anyActive ? undefined : 'var(--ok)'} />
            </span>
          </div>
          <IconButton
            icon={collapsed ? ChevronUpIcon : ChevronDownIcon}
            size="sm"
            label={
              collapsed
                ? t('upload.trayExpand', { defaultValue: 'Expand upload status' })
                : t('upload.trayCollapse', { defaultValue: 'Collapse upload status' })
            }
            onClick={() => setCollapsed((c) => !c)}
          />
          <IconButton
            icon={XMarkIcon}
            size="sm"
            label={t('upload.trayClearFinished', { defaultValue: 'Clear finished uploads' })}
            onClick={clearFinished}
          />
        </div>

        {/* Body — one compact row per job */}
        {!collapsed && (
          <div className="scroll" style={{ maxHeight: 280, overflowY: 'auto' }}>
            {jobs.map((job) => (
              <TrayRow key={job.id} job={job} />
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
