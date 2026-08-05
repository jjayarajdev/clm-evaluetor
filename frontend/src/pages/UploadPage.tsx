/* Upload page — Direction B redesign.
   Dashed token-styled dropzone → queue card with per-file rows → live pipeline
   visualization driven by the real per-stage processing status the backend
   reports (/contracts/:id/processing-status/current).

   Job state (upload → queued → processing → completed/failed) lives in the
   global UploadContext, so navigating away mid-upload keeps the jobs alive
   (the UploadTray surfaces them everywhere) and coming back shows consistent
   state. This page keeps only what is page-scoped: the dropzone's pre-upload
   queue (File objects not yet uploaded, incl. rejected drops), the
   client/group destination pickers, and the detailed pipeline visualization. */
import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  ArrowPathIcon,
  ArrowRightIcon,
  BuildingOfficeIcon,
  CheckCircleIcon,
  ClockIcon,
  CloudArrowUpIcon,
  DocumentTextIcon,
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
  FolderOpenIcon,
  LinkIcon,
  PlusIcon,
  SparklesIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import { useTranslation } from 'react-i18next'
import api from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import { useTenantConfig } from '@/contexts/TenantConfigContext'
import { PIPELINE_STAGES, isActiveJob, useUploads } from '@/contexts/UploadContext'
import { Button, IconButton, Pill, Tag, AiTag, Field, Select, Bar, useToast } from '@/components/ui'
import { formatFileSize } from '@/lib/utils'

/** A dropped file that has not been handed to the upload context yet. */
interface PendingFile {
  file: File
  /** Dropzone rejection message — the file will never be uploaded. */
  error?: string
}

const ACCEPTED_TYPES = {
  // Documents - PDF (multiple MIME types for browser compatibility)
  'application/pdf': ['.pdf'],
  'application/x-pdf': ['.pdf'],
  'application/acrobat': ['.pdf'],
  'applications/vnd.pdf': ['.pdf'],
  'text/pdf': ['.pdf'],
  'text/x-pdf': ['.pdf'],
  // Documents - Word
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/msword': ['.doc'],
  // Spreadsheets
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  'application/vnd.ms-excel': ['.xls'],
  // Presentations
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
  'application/vnd.ms-powerpoint': ['.ppt'],
  // Images (for scanned contracts)
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/tiff': ['.tiff', '.tif'],
}

const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB

/* Live pipeline: compact steps with done / active / pending states, driven by
   the real stage id the worker reports. Before the worker picks the file up
   (no stage yet) we only claim "queued" — a pulsing indeterminate bar. */
function Pipeline({ stage, percent }: { stage?: string; percent?: number }) {
  const { t } = useTranslation()
  const idx = stage ? PIPELINE_STAGES.findIndex((s) => s.id === stage) : -1

  if (idx === -1) {
    return (
      <div className="col" style={{ gap: 6 }}>
        <div className="row" style={{ gap: 6 }}>
          <ClockIcon style={{ width: 13, height: 13, color: 'var(--f)' }} aria-hidden />
          <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
            {t('upload.queuedForProcessing', { defaultValue: 'Queued — waiting for the processing worker' })}
          </span>
        </div>
        <span className="pulse" style={{ display: 'block' }}>
          <Bar value={6} width="100%" />
        </span>
      </div>
    )
  }

  const pct = typeof percent === 'number' ? percent : Math.round(((idx + 1) / PIPELINE_STAGES.length) * 100)
  return (
    <div className="col" style={{ gap: 7 }}>
      <div className="row" style={{ gap: 8 }}>
        <span className="muted" style={{ fontSize: 'var(--fs-sm)', fontWeight: 600 }}>
          {t('upload.stageOf', { current: idx + 1, total: PIPELINE_STAGES.length })}
        </span>
        <span style={{ fontSize: 'var(--fs-sm)', color: 'var(--p)', fontWeight: 600 }}>
          {t(PIPELINE_STAGES[idx].labelKey)}
        </span>
        <span className="grow" />
        <span className="mono num faint" style={{ fontSize: 'var(--fs-xs)' }}>{pct}%</span>
      </div>
      <Bar value={pct} width="100%" />
      <div className="row" style={{ flexWrap: 'wrap', gap: '4px 12px' }}>
        {PIPELINE_STAGES.map((s, i) => {
          const state = i < idx ? 'done' : i === idx ? 'active' : 'pending'
          const color = state === 'done' ? 'var(--ok)' : state === 'active' ? 'var(--p)' : 'var(--f)'
          const StepIcon = state === 'done' ? CheckCircleIcon : state === 'active' ? ArrowPathIcon : ClockIcon
          return (
            <span
              key={s.id}
              className="row"
              style={{ gap: 4, fontSize: 'var(--fs-xs)', color, fontWeight: state === 'active' ? 600 : 500 }}
            >
              <StepIcon
                className={state === 'active' ? 'spin' : undefined}
                style={{ width: 12, height: 12, flexShrink: 0 }}
                aria-hidden
              />
              {t(s.labelKey)}
            </span>
          )
        })}
      </div>
    </div>
  )
}

export default function UploadPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { toast } = useToast()
  const { user, isSuperAdmin } = useAuth()
  const { config } = useTenantConfig()
  const { jobs, queueStatus, startUploads, retryProcessing, dismissJob } = useUploads()
  const [pending, setPending] = useState<PendingFile[]>([])
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null)
  const [groupName, setGroupName] = useState('')
  const [showNewClientForm, setShowNewClientForm] = useState(false)
  const [newClientName, setNewClientName] = useState('')
  const [newClientCode, setNewClientCode] = useState('')

  // Fetch clients for dropdown
  const { data: clients = [], refetch: refetchClients } = useQuery({
    queryKey: ['clients-summary'],
    queryFn: () => api.getClientsSummary(),
  })

  // Existing groups for the upload group picker
  const { data: groupsData } = useQuery({
    queryKey: ['contract-groups', 'upload-picker'],
    queryFn: () => api.getGroups({ page_size: 100 }),
  })
  // Dedupe by name — several group records can share a name (e.g. one per
  // upload batch), and the datalist should offer each distinct name once.
  const groups = groupsData?.items ?? []
  const groupNameOptions = Array.from(
    new Map(groups.map((g) => [g.name.toLowerCase(), g.name])).values(),
  )

  // Create new client mutation
  const createClientMutation = useMutation({
    mutationFn: async () => {
      const client = await api.createClient({
        name: newClientName,
        code: newClientCode.toUpperCase(),
      })
      return client
    },
    onSuccess: (client) => {
      setSelectedClientId(client.id)
      setShowNewClientForm(false)
      setNewClientName('')
      setNewClientCode('')
      refetchClients()
      toast({ text: t('upload.clientCreated', { name: client.name, defaultValue: 'Client "{{name}}" created' }) })
    },
  })

  // Contract IDs still being tracked by the provider (for the queue banner)
  const processingContractIds = jobs
    .filter((j) => isActiveJob(j) && j.contractId)
    .map((j) => j.contractId) as string[]

  const myQueuedJobs = (queueStatus?.jobs ?? []).filter(
    (j) => processingContractIds.includes(j.contract_id) && j.status === 'queued',
  )
  const maxEtaMinutes = myQueuedJobs.length
    ? Math.max(1, Math.round(Math.max(...myQueuedJobs.map((j) => j.eta_seconds)) / 60))
    : 0

  const onDrop = useCallback((acceptedFiles: File[], rejectedFiles: any[]) => {
    const rejected: PendingFile[] = rejectedFiles.map((rejection) => ({
      file: rejection.file,
      error: rejection.errors[0]?.message || t('upload.fileRejected'),
    }))
    const accepted: PendingFile[] = acceptedFiles.map((file) => ({ file }))
    setPending((prev) => [...prev, ...accepted, ...rejected])
  }, [])

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: MAX_FILE_SIZE,
    multiple: true,
    useFsAccessApi: false, // Disable File System Access API for better compatibility (Safari, older browsers)
  })

  const removePending = (index: number) => {
    setPending((prev) => prev.filter((_, i) => i !== index))
  }

  // Per-row upload — hands a single file to the context (single-file endpoint).
  const uploadOne = (index: number) => {
    const p = pending[index]
    if (!p || p.error) return
    setPending((prev) => prev.filter((_, i) => i !== index))
    void startUploads([p.file], { single: true })
  }

  // Batch upload — groups files in the same folder, reusing an existing group
  // by name when one matches, and files under the selected client.
  const uploadAll = () => {
    const eligible = pending.filter((p) => !p.error)
    if (eligible.length === 0) return

    const trimmedGroup = groupName.trim()
    const existingGroup = groups.find(
      (g) => g.name.toLowerCase() === trimmedGroup.toLowerCase(),
    )
    setPending((prev) => prev.filter((p) => p.error))
    void startUploads(
      eligible.map((p) => p.file),
      {
        clientId: selectedClientId || undefined,
        groupName: existingGroup ? undefined : trimmedGroup || undefined,
        groupId: existingGroup?.id,
      },
    )
  }

  const pendingCount = pending.filter((p) => !p.error).length
  const completedCount = jobs.filter((j) => j.state === 'completed').length
  const totalCount = pending.length + jobs.length
  const totalSize =
    pending.reduce((s, p) => s + p.file.size, 0) + jobs.reduce((s, j) => s + j.fileSize, 0)
  const clientOptions = [
    { value: '', label: t('upload.none') },
    ...clients.map((c) => ({ value: c.id, label: `${c.name} (${c.code})` })),
  ]

  return (
    <div className="col" style={{ gap: 18, maxWidth: 1080 }}>
      {/* Header */}
      <div className="row" style={{ alignItems: 'flex-start' }}>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>{t('upload.title')}</h1>
          <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>{t('upload.description')}</p>
        </div>
        {!isSuperAdmin && user?.tenant_name && (
          <Tag icon={BuildingOfficeIcon}>{user.tenant_name}</Tag>
        )}
      </div>

      {/* Industry profile context — AI extraction is tenant-profile aware */}
      {config?.industry_name && (
        <div className="banner banner-p" style={{ alignItems: 'center' }}>
          <SparklesIcon style={{ width: 16, height: 16, flexShrink: 0 }} aria-hidden />
          <span className="grow">
            <b>{t('upload.profileActive', { name: config.industry_name })}</b>{' '}
            <span style={{ opacity: 0.8 }}>
              {t('upload.profileStats', {
                types: config.contract_types?.length || 0,
                clauses: config.clause_types?.length || 0,
                slas: config.sla_metrics?.length || 0,
              })}
            </span>
          </span>
          <AiTag />
          <a href="/admin/industry-profiles" style={{ fontSize: 'var(--fs-sm)', fontWeight: 600, color: 'var(--p)', whiteSpace: 'nowrap' }}>
            {t('upload.viewProfile')}
          </a>
        </div>
      )}

      {/* Destination: group + optional client */}
      <div className="card card-p col" style={{ gap: 12 }}>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Field
              label={t('upload.groupLabel')}
              placeholder={t('upload.groupPlaceholder')}
              value={groupName}
              onChange={(e) => setGroupName(e.target.value)}
              list="upload-group-options"
              hint={
                user?.business_unit_name
                  ? t('upload.defaultBuHint', { bu: user.business_unit_name })
                  : undefined
              }
            />
            <datalist id="upload-group-options">
              {groupNameOptions.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </div>
          {clients.length > 0 && (
            <div className="col" style={{ gap: 6 }}>
              <Select
                label={t('upload.groupUnderClient')}
                value={selectedClientId ?? ''}
                onChange={(e) => setSelectedClientId(e.target.value || null)}
                options={clientOptions}
              />
              {!showNewClientForm && (
                <Button
                  variant="ghost"
                  size="sm"
                  icon={PlusIcon}
                  style={{ alignSelf: 'flex-start' }}
                  onClick={() => setShowNewClientForm(true)}
                >
                  {t('upload.createNewClient')}
                </Button>
              )}
            </div>
          )}
        </div>

        {/* New client inline form */}
        {showNewClientForm && (
          <div className="col" style={{ gap: 12, padding: 14, background: 'var(--s3)', border: '1px solid var(--b)', borderRadius: 'var(--r-md)' }}>
            <span className="sec-t">{t('upload.createNewClient')}</span>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                label={t('upload.clientName')}
                value={newClientName}
                onChange={(e) => setNewClientName(e.target.value)}
                placeholder="e.g., ING Bank N.V."
              />
              <Field
                label={t('upload.clientCode')}
                value={newClientCode}
                onChange={(e) => setNewClientCode(e.target.value.toUpperCase())}
                placeholder="e.g., ING"
                maxLength={50}
                className="mono"
                error={
                  createClientMutation.isError
                    ? (createClientMutation.error as any)?.response?.data?.detail || t('upload.createClientFailed')
                    : undefined
                }
              />
            </div>
            <div className="row" style={{ gap: 8 }}>
              <Button
                variant="primary"
                size="sm"
                onClick={() => createClientMutation.mutate()}
                disabled={!newClientName.trim() || !newClientCode.trim() || createClientMutation.isPending}
              >
                {createClientMutation.isPending ? t('upload.creating') : t('upload.createClient')}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setShowNewClientForm(false)
                  setNewClientName('')
                  setNewClientCode('')
                }}
              >
                {t('common.cancel')}
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Dropzone */}
      <div
        {...getRootProps()}
        className="card"
        style={{
          borderStyle: 'dashed',
          borderWidth: 2,
          borderColor: isDragActive ? 'var(--p)' : 'var(--p-b)',
          background: isDragActive ? 'var(--p-f2)' : 'var(--p-f)',
          padding: '38px 24px',
          textAlign: 'center',
          cursor: 'pointer',
          transition: 'border-color .12s var(--ease), background .12s var(--ease)',
        }}
      >
        <input {...getInputProps()} />
        <span
          style={{
            width: 46, height: 46, borderRadius: 'var(--r-lg)', background: 'var(--s)',
            color: 'var(--p)', display: 'inline-grid', placeItems: 'center', boxShadow: 'var(--sh-sm)',
          }}
        >
          <CloudArrowUpIcon style={{ width: 24, height: 24 }} aria-hidden />
        </span>
        <h3 style={{ fontSize: 'var(--fs-xl)', fontWeight: 600, marginTop: 12 }}>
          {isDragActive ? t('upload.dropFilesHere') : t('upload.dragAndDrop')}
        </h3>
        <p className="muted" style={{ fontSize: 'var(--fs-md)', marginTop: 5, lineHeight: 1.55 }}>
          {t('upload.supportedFormats')}
        </p>
        <Button
          variant="primary"
          size="lg"
          icon={FolderOpenIcon}
          style={{ marginTop: 16 }}
          onClick={(e) => { e.stopPropagation(); open() }}
        >
          {t('upload.orBrowse')}
        </Button>
      </div>

      {/* File queue + live pipeline (pending drops first, then tracked jobs) */}
      {totalCount > 0 && (
        <div className="tbl-w">
          <div className="row" style={{ padding: '11px 14px', background: 'var(--s3)', borderBottom: '1px solid var(--b)' }}>
            <b style={{ fontSize: 'var(--fs-md)' }}>{t('upload.filesCount', { count: totalCount })}</b>
            <span className="faint" style={{ fontSize: 'var(--fs-sm)', marginLeft: 8 }}>
              {formatFileSize(totalSize)}
            </span>
            <span className="grow" />
            {pendingCount > 0 && (
              <Button variant="primary" size="sm" icon={CloudArrowUpIcon} onClick={uploadAll}>
                {t('upload.uploadAll', { count: pendingCount })}
              </Button>
            )}
          </div>

          {/* Queue depth + position while the worker is busy */}
          {queueStatus && processingContractIds.length > 0 && queueStatus.queue_depth > 0 && (
            <div
              className="row"
              style={{
                flexWrap: 'wrap', gap: '4px 16px', padding: '8px 14px', fontSize: 'var(--fs-sm)',
                background: 'var(--in-f)', color: 'var(--in)', borderBottom: '1px solid var(--b)',
              }}
            >
              <span>{t('upload.queueDepth', { count: queueStatus.queue_depth })}</span>
              <span>{t('upload.queueProcessing', { count: queueStatus.processing })}</span>
              {myQueuedJobs.length > 0 && (
                <span>
                  {t('upload.queuePosition', {
                    position: Math.min(...myQueuedJobs.map((j) => j.position)),
                    minutes: maxEtaMinutes,
                  })}
                </span>
              )}
            </div>
          )}

          {/* Pending drops — not uploaded yet (page-local) */}
          {pending.map((p, index) => (
            <div key={`${p.file.name}-${index}`} className="col" style={{ borderBottom: '1px solid var(--b)' }}>
              <div className="row" style={{ gap: 10, padding: '11px 14px' }}>
                <DocumentTextIcon style={{ width: 17, height: 17, flexShrink: 0, color: 'var(--f)' }} aria-hidden />
                <span className="mono trunc grow" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                  {p.file.name}
                </span>
                <span className="faint num" style={{ fontSize: 'var(--fs-sm)', whiteSpace: 'nowrap' }}>
                  {formatFileSize(p.file.size)}
                </span>
                {p.error ? (
                  <Pill tone="da">{t('status.failed', { defaultValue: 'Failed' })}</Pill>
                ) : (
                  <Button variant="secondary" size="sm" onClick={() => uploadOne(index)}>
                    {t('nav.upload')}
                  </Button>
                )}
                <IconButton
                  icon={XMarkIcon}
                  size="sm"
                  label={t('upload.removeFromQueue', { defaultValue: 'Remove from queue' })}
                  onClick={() => removePending(index)}
                />
              </div>
              {p.error && (
                <div style={{ padding: '0 14px 12px 41px' }}>
                  <div className="banner banner-da" style={{ alignItems: 'center' }}>
                    <ExclamationCircleIcon style={{ width: 16, height: 16, flexShrink: 0 }} aria-hidden />
                    <span className="grow">{p.error}</span>
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Tracked jobs — sourced from the global upload context */}
          {jobs.map((job) => (
            <div key={job.id} className="col" style={{ borderBottom: '1px solid var(--b)' }}>
              <div className="row" style={{ gap: 10, padding: '11px 14px' }}>
                <DocumentTextIcon style={{ width: 17, height: 17, flexShrink: 0, color: 'var(--f)' }} aria-hidden />
                <span className="mono trunc grow" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                  {job.fileName}
                </span>
                {job.warning && (
                  <Pill tone="wa">{t('upload.alreadyUploaded', { defaultValue: 'Duplicate' })}</Pill>
                )}
                <span className="faint num" style={{ fontSize: 'var(--fs-sm)', whiteSpace: 'nowrap' }}>
                  {formatFileSize(job.fileSize)}
                </span>

                {job.state === 'uploading' && (
                  <span className="row muted" style={{ gap: 6, fontSize: 'var(--fs-sm)' }}>
                    <ArrowPathIcon className="spin" style={{ width: 14, height: 14, color: 'var(--p)' }} aria-hidden />
                    {t('upload.uploading')}
                  </span>
                )}
                {(job.state === 'queued' || job.state === 'duplicate' || job.state === 'processing') && (
                  <Pill tone="p">{t('upload.processing')}</Pill>
                )}
                {job.state === 'completed' && (
                  <>
                    <CheckCircleIcon style={{ width: 17, height: 17, color: 'var(--ok)', flexShrink: 0 }} aria-hidden />
                    <Button
                      variant="secondary"
                      size="sm"
                      iconRight={ArrowRightIcon}
                      onClick={() => navigate(`/contracts/${job.contractId}`)}
                    >
                      {t('upload.view')}
                    </Button>
                  </>
                )}
                {job.state === 'failed' && (
                  <>
                    <Pill tone="da">{t('status.failed', { defaultValue: 'Failed' })}</Pill>
                    <IconButton
                      icon={XMarkIcon}
                      size="sm"
                      label={t('upload.removeFromQueue', { defaultValue: 'Remove from queue' })}
                      onClick={() => dismissJob(job.id)}
                    />
                  </>
                )}
              </div>

              {/* Duplicate-content warning detail */}
              {job.warning && (
                <div className="row" style={{ gap: 6, padding: '0 14px 10px 41px', fontSize: 'var(--fs-sm)', color: 'var(--wa)' }}>
                  <ExclamationTriangleIcon style={{ width: 13, height: 13, flexShrink: 0 }} aria-hidden />
                  <span className="trunc">{job.warning}</span>
                </div>
              )}

              {/* Live pipeline while the worker runs */}
              {(job.state === 'queued' || job.state === 'duplicate' || job.state === 'processing') && (
                <div style={{ padding: '0 14px 12px 41px' }}>
                  <Pipeline stage={job.stage} percent={job.progressPercent} />
                </div>
              )}

              {/* Success detail: extraction counts + suggested links */}
              {job.state === 'completed' && (
                <div className="row" style={{ flexWrap: 'wrap', gap: 8, padding: '0 14px 10px 41px' }}>
                  <span style={{ fontSize: 'var(--fs-sm)', color: 'var(--ok)' }}>
                    {t('upload.extractedSummary', { clauses: job.clauseCount, obligations: job.obligationCount })}
                  </span>
                  {job.hasSuggestions && job.suggestionCount ? (
                    <Tag icon={LinkIcon}>{t('upload.linkCount', { count: job.suggestionCount })}</Tag>
                  ) : null}
                </div>
              )}

              {/* Failure detail: danger banner + retry when processing can be re-run */}
              {job.state === 'failed' && job.error && (
                <div style={{ padding: '0 14px 12px 41px' }}>
                  <div className="banner banner-da" style={{ alignItems: 'center' }}>
                    <ExclamationCircleIcon style={{ width: 16, height: 16, flexShrink: 0 }} aria-hidden />
                    <span className="grow">{job.error}</span>
                    {job.contractId && (
                      <Button
                        variant="secondary"
                        size="sm"
                        icon={ArrowPathIcon}
                        onClick={() => retryProcessing(job.contractId as string)}
                      >
                        {t('upload.retry')}
                      </Button>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Completed summary */}
      {completedCount > 0 && (
        <div
          className="banner"
          style={{ alignItems: 'center', background: 'var(--ok-f)', borderColor: 'var(--ok-b)', color: 'var(--ok)' }}
        >
          <CheckCircleIcon style={{ width: 16, height: 16, flexShrink: 0 }} aria-hidden />
          <span className="grow">
            <b>{t('upload.processedSuccessfully', { count: completedCount })}</b>{' '}
            <span style={{ opacity: 0.85 }}>{t('upload.analysisComplete')}</span>
          </span>
          <Button
            variant="secondary"
            size="sm"
            iconRight={ArrowRightIcon}
            onClick={() => navigate('/contracts')}
          >
            {t('nav.contracts')}
          </Button>
        </div>
      )}

      {/* Related contracts found notification */}
      {jobs.some((j) => j.hasSuggestions) && (
        <div className="banner banner-p" style={{ alignItems: 'center' }}>
          <LinkIcon style={{ width: 16, height: 16, flexShrink: 0 }} aria-hidden />
          <span className="grow">
            <b>{t('upload.relatedContractsFound')}</b>{' '}
            <span style={{ opacity: 0.8 }}>{t('upload.relatedContractsDesc')}</span>
          </span>
          <Button
            variant="primary"
            size="sm"
            onClick={() => {
              // Navigate to the first contract with suggestions
              const jobWithSuggestions = jobs.find((j) => j.hasSuggestions && j.contractId)
              if (jobWithSuggestions?.contractId) {
                navigate(`/contracts/${jobWithSuggestions.contractId}`)
              }
            }}
          >
            {t('upload.review')}
          </Button>
        </div>
      )}
    </div>
  )
}
