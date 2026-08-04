/* Upload page — Direction B redesign.
   Dashed token-styled dropzone → queue card with per-file rows → live pipeline
   visualization driven by the real per-stage processing status the backend
   reports (/contracts/:id/processing-status/current). Upload flows, polling,
   client/group selectors, retry and navigation are unchanged from the
   pre-redesign page. */
import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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
import { Button, IconButton, Pill, Tag, AiTag, Field, Select, Bar, useToast } from '@/components/ui'
import { formatFileSize } from '@/lib/utils'

interface FileUpload {
  file: File
  status: 'pending' | 'uploading' | 'uploaded' | 'processing' | 'completed' | 'error'
  progress: number
  error?: string
  warning?: string
  stage?: string
  progressPercent?: number
  contractId?: string
  clauseCount?: number
  obligationCount?: number
  hasSuggestions?: boolean
  suggestionCount?: number
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

// Ordered pipeline stages, matching the stage ids the processing worker reports.
const PIPELINE_STAGES: Array<{ id: string; labelKey: string }> = [
  { id: 'parsing', labelKey: 'upload.stageParsing' },
  { id: 'chunking', labelKey: 'upload.stageChunking' },
  { id: 'classifying', labelKey: 'upload.stageClassifying' },
  { id: 'metadata', labelKey: 'upload.stageMetadata' },
  { id: 'custom_fields', labelKey: 'upload.stageCustomFields' },
  { id: 'risk', labelKey: 'upload.stageRisk' },
  { id: 'knowledge_graph', labelKey: 'upload.stageKnowledgeGraph' },
  { id: 'clause_extraction', labelKey: 'upload.stageClauses' },
  { id: 'obligation_detection', labelKey: 'upload.stageObligations' },
  { id: 'sla_extraction', labelKey: 'upload.stageSlas' },
  { id: 'renewal_analysis', labelKey: 'upload.stageRenewals' },
  { id: 'schema_extraction', labelKey: 'upload.stageSchema' },
  { id: 'link_detection', labelKey: 'upload.stageLinks' },
  { id: 'compliance_check', labelKey: 'upload.stageCompliance' },
  { id: 'governance_bridge', labelKey: 'upload.stageGovernance' },
]

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
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const { user, isSuperAdmin } = useAuth()
  const { config } = useTenantConfig()
  const [files, setFiles] = useState<FileUpload[]>([])
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
  const groups = groupsData?.items ?? []

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

  // Get contract IDs that are still processing
  const processingContractIds = files
    .filter(f => f.status === 'uploaded' || f.status === 'processing')
    .map(f => f.contractId)
    .filter(Boolean) as string[]

  // Poll for contract status updates
  const { data: contractsData } = useQuery({
    queryKey: ['contracts-status', processingContractIds],
    queryFn: async () => {
      const results = await Promise.all(
        processingContractIds.map(id => api.getContract(id).catch(() => null))
      )
      return results.filter(Boolean)
    },
    enabled: processingContractIds.length > 0,
    refetchInterval: 2000, // Poll every 2 seconds
  })

  // Per-stage pipeline progress for files currently processing
  const { data: stageData } = useQuery({
    queryKey: ['contracts-stages', processingContractIds],
    queryFn: async () => {
      const results = await Promise.all(
        processingContractIds.map(id => api.getProcessingStatusCurrent(id).catch(() => null))
      )
      return results.filter(Boolean)
    },
    enabled: processingContractIds.length > 0,
    refetchInterval: 2000,
  })

  useEffect(() => {
    if (!stageData) return
    setFiles(prev => prev.map(f => {
      if (!f.contractId) return f
      const s = stageData.find(x => x?.contract_id === f.contractId)
      if (!s || s.stage === 'idle') return f
      return { ...f, stage: s.stage, progressPercent: s.progress_percent }
    }))
  }, [stageData])

  // Queue position + ETA while files wait for the processing worker
  const { data: queueStatus } = useQuery({
    queryKey: ['processing-queue-status'],
    queryFn: () => api.getProcessingQueueStatus(),
    enabled: processingContractIds.length > 0,
    refetchInterval: 10000,
  })
  const myQueuedJobs = (queueStatus?.jobs ?? []).filter(
    (j) => processingContractIds.includes(j.contract_id) && j.status === 'queued',
  )
  const maxEtaMinutes = myQueuedJobs.length
    ? Math.max(1, Math.round(Math.max(...myQueuedJobs.map((j) => j.eta_seconds)) / 60))
    : 0

  const retryProcessing = async (index: number) => {
    const f = files[index]
    if (!f.contractId) return
    try {
      await api.processContract(f.contractId)
      setFiles((prev) =>
        prev.map((x, i) =>
          i === index ? { ...x, status: 'uploaded' as const, error: undefined } : x,
        ),
      )
    } catch {
      // keep the row in error state; the message is already shown
    }
  }

  // Update file statuses based on contract data
  useEffect(() => {
    if (!contractsData) return

    let hasNewlyCompleted = false
    const newlyCompletedIds: string[] = []

    setFiles(prev => prev.map(f => {
      if (!f.contractId) return f

      const contract = contractsData.find(c => c?.id === f.contractId)
      if (!contract) return f

      if (contract.status === 'completed') {
        // Check if this is a newly completed contract (was not completed before)
        if (f.status !== 'completed') {
          hasNewlyCompleted = true
          newlyCompletedIds.push(f.contractId)
        }
        return {
          ...f,
          status: 'completed',
          clauseCount: contract.clause_count,
          obligationCount: contract.obligation_count,
        }
      } else if (contract.status === 'processing') {
        return { ...f, status: 'processing' }
      } else if (contract.status === 'failed') {
        return { ...f, status: 'error', error: contract.processing_error || t('upload.processingFailed') }
      }

      return f
    }))

    // Invalidate all relevant caches when contracts complete processing
    if (hasNewlyCompleted) {
      // Dashboard components
      queryClient.invalidateQueries({ queryKey: ['clauses-summary'] })
      queryClient.invalidateQueries({ queryKey: ['obligations-summary'] })
      queryClient.invalidateQueries({ queryKey: ['contracts-summary'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['clients-summary'] })
      // Contract list and details
      queryClient.invalidateQueries({ queryKey: ['contracts'] })
      queryClient.invalidateQueries({ queryKey: ['contract-filter-options'] })
      // Post-signing pages
      queryClient.invalidateQueries({ queryKey: ['postsigning-dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['renewal-calendar'] })
      queryClient.invalidateQueries({ queryKey: ['vendors'] })
      // Reports
      queryClient.invalidateQueries({ queryKey: ['contract-trend'] })
      queryClient.invalidateQueries({ queryKey: ['compliance-report'] })

      // Check for suggested links on newly completed contracts
      Promise.all(
        newlyCompletedIds.map(async (contractId) => {
          try {
            const suggestions = await api.getSuggestedLinks(contractId)
            if (suggestions.pending_count > 0) {
              setFiles(prev => prev.map(f =>
                f.contractId === contractId
                  ? { ...f, hasSuggestions: true, suggestionCount: suggestions.pending_count }
                  : f
              ))
            }
          } catch {
            // Ignore errors - suggestions are optional
          }
        })
      )
    }
  }, [contractsData, queryClient])

  const uploadMutation = useMutation({
    mutationFn: async (fileUpload: FileUpload) => {
      const response = await api.uploadFile(fileUpload.file)
      return response
    },
  })

  const onDrop = useCallback((acceptedFiles: File[], rejectedFiles: any[]) => {
    const rejected = rejectedFiles.map((rejection) => ({
      file: rejection.file,
      status: 'error' as const,
      progress: 0,
      error: rejection.errors[0]?.message || t('upload.fileRejected'),
    }))

    const accepted = acceptedFiles.map((file) => ({
      file,
      status: 'pending' as const,
      progress: 0,
    }))

    setFiles((prev) => [...prev, ...accepted, ...rejected])
  }, [])

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: MAX_FILE_SIZE,
    multiple: true,
    useFsAccessApi: false, // Disable File System Access API for better compatibility (Safari, older browsers)
  })

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const uploadFile = async (index: number) => {
    const fileUpload = files[index]
    if (fileUpload.status !== 'pending') return

    setFiles((prev) =>
      prev.map((f, i) => (i === index ? { ...f, status: 'uploading' as const, progress: 50 } : f))
    )

    try {
      const result = await uploadMutation.mutateAsync(fileUpload)
      setFiles((prev) =>
        prev.map((f, i) =>
          i === index
            ? { ...f, status: 'uploaded' as const, progress: 100, contractId: result.id || undefined }
            : f
        )
      )
    } catch (error: any) {
      setFiles((prev) =>
        prev.map((f, i) =>
          i === index
            ? {
                ...f,
                status: 'error' as const,
                progress: 0,
                error: error?.message || t('upload.uploadFailed'),
              }
            : f
        )
      )
    }
  }

  const uploadAll = async () => {
    const pendingIndices = files
      .map((f, i) => (f.status === 'pending' ? i : -1))
      .filter((i) => i !== -1)

    if (pendingIndices.length === 0) return

    // Mark all as uploading
    setFiles((prev) =>
      prev.map((f, i) =>
        pendingIndices.includes(i) ? { ...f, status: 'uploading' as const, progress: 50 } : f
      )
    )

    try {
      // Use batch upload to group files in same folder
      const pendingFiles = pendingIndices.map((i) => files[i].file)
      const trimmedGroup = groupName.trim()
      const existingGroup = groups.find(
        (g) => g.name.toLowerCase() === trimmedGroup.toLowerCase(),
      )
      const result = await api.uploadFiles(
        pendingFiles,
        selectedClientId || undefined,
        existingGroup ? undefined : trimmedGroup || undefined,
        existingGroup?.id,
      )

      // Update status based on batch response
      setFiles((prev) =>
        prev.map((f, i) => {
          if (!pendingIndices.includes(i)) return f

          // Find matching file in response
          const fileResult = result.files?.find(
            (r) => r.filename === f.file.name || r.filename?.includes(f.file.name.substring(0, 20))
          )

          if (fileResult?.status === 'accepted' && fileResult.id) {
            return {
              ...f,
              status: 'uploaded' as const,
              progress: 100,
              contractId: fileResult.id,
              warning: fileResult.duplicate_of_filename
                ? t('upload.duplicateWarning', { filename: fileResult.duplicate_of_filename })
                : undefined,
            }
          } else if (fileResult?.status === 'rejected') {
            return {
              ...f,
              status: 'error' as const,
              progress: 0,
              error: fileResult?.message || t('upload.uploadRejected'),
            }
          } else {
            return {
              ...f,
              status: 'error' as const,
              progress: 0,
              error: t('upload.uploadFailedNoResponse'),
            }
          }
        })
      )
    } catch (error: any) {
      // If batch fails, mark all as error
      setFiles((prev) =>
        prev.map((f, i) =>
          pendingIndices.includes(i)
            ? {
                ...f,
                status: 'error' as const,
                progress: 0,
                error: error?.message || t('upload.batchUploadFailed'),
              }
            : f
        )
      )
    }
  }

  const pendingCount = files.filter((f) => f.status === 'pending').length
  const completedCount = files.filter((f) => f.status === 'completed').length
  const totalSize = files.reduce((s, f) => s + f.file.size, 0)
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
              {groups.map((g) => (
                <option key={g.id} value={g.name} />
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

      {/* File queue + live pipeline */}
      {files.length > 0 && (
        <div className="tbl-w">
          <div className="row" style={{ padding: '11px 14px', background: 'var(--s3)', borderBottom: '1px solid var(--b)' }}>
            <b style={{ fontSize: 'var(--fs-md)' }}>{t('upload.filesCount', { count: files.length })}</b>
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

          {files.map((fileUpload, index) => (
            <div key={index} className="col" style={{ borderBottom: '1px solid var(--b)' }}>
              <div className="row" style={{ gap: 10, padding: '11px 14px' }}>
                <DocumentTextIcon style={{ width: 17, height: 17, flexShrink: 0, color: 'var(--f)' }} aria-hidden />
                <span className="mono trunc grow" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                  {fileUpload.file.name}
                </span>
                {fileUpload.warning && (
                  <Pill tone="wa">{t('upload.alreadyUploaded', { defaultValue: 'Duplicate' })}</Pill>
                )}
                <span className="faint num" style={{ fontSize: 'var(--fs-sm)', whiteSpace: 'nowrap' }}>
                  {formatFileSize(fileUpload.file.size)}
                </span>

                {fileUpload.status === 'pending' && (
                  <>
                    <Button variant="secondary" size="sm" onClick={() => uploadFile(index)}>
                      {t('nav.upload')}
                    </Button>
                    <IconButton
                      icon={XMarkIcon}
                      size="sm"
                      label={t('upload.removeFromQueue', { defaultValue: 'Remove from queue' })}
                      onClick={() => removeFile(index)}
                    />
                  </>
                )}
                {fileUpload.status === 'uploading' && (
                  <span className="row muted" style={{ gap: 6, fontSize: 'var(--fs-sm)' }}>
                    <ArrowPathIcon className="spin" style={{ width: 14, height: 14, color: 'var(--p)' }} aria-hidden />
                    {t('upload.uploading')}
                  </span>
                )}
                {(fileUpload.status === 'uploaded' || fileUpload.status === 'processing') && (
                  <Pill tone="p">{t('upload.processing')}</Pill>
                )}
                {fileUpload.status === 'completed' && (
                  <>
                    <CheckCircleIcon style={{ width: 17, height: 17, color: 'var(--ok)', flexShrink: 0 }} aria-hidden />
                    <Button
                      variant="secondary"
                      size="sm"
                      iconRight={ArrowRightIcon}
                      onClick={() => navigate(`/contracts/${fileUpload.contractId}`)}
                    >
                      {t('upload.view')}
                    </Button>
                  </>
                )}
                {fileUpload.status === 'error' && (
                  <>
                    <Pill tone="da">{t('status.failed', { defaultValue: 'Failed' })}</Pill>
                    <IconButton
                      icon={XMarkIcon}
                      size="sm"
                      label={t('upload.removeFromQueue', { defaultValue: 'Remove from queue' })}
                      onClick={() => removeFile(index)}
                    />
                  </>
                )}
              </div>

              {/* Duplicate-content warning detail */}
              {fileUpload.warning && (
                <div className="row" style={{ gap: 6, padding: '0 14px 10px 41px', fontSize: 'var(--fs-sm)', color: 'var(--wa)' }}>
                  <ExclamationTriangleIcon style={{ width: 13, height: 13, flexShrink: 0 }} aria-hidden />
                  <span className="trunc">{fileUpload.warning}</span>
                </div>
              )}

              {/* Live pipeline while the worker runs */}
              {(fileUpload.status === 'uploaded' || fileUpload.status === 'processing') && (
                <div style={{ padding: '0 14px 12px 41px' }}>
                  <Pipeline stage={fileUpload.stage} percent={fileUpload.progressPercent} />
                </div>
              )}

              {/* Success detail: extraction counts + suggested links */}
              {fileUpload.status === 'completed' && (
                <div className="row" style={{ flexWrap: 'wrap', gap: 8, padding: '0 14px 10px 41px' }}>
                  <span style={{ fontSize: 'var(--fs-sm)', color: 'var(--ok)' }}>
                    {t('upload.extractedSummary', { clauses: fileUpload.clauseCount, obligations: fileUpload.obligationCount })}
                  </span>
                  {fileUpload.hasSuggestions && fileUpload.suggestionCount ? (
                    <Tag icon={LinkIcon}>{t('upload.linkCount', { count: fileUpload.suggestionCount })}</Tag>
                  ) : null}
                </div>
              )}

              {/* Failure detail: danger banner + retry when processing can be re-run */}
              {fileUpload.status === 'error' && fileUpload.error && (
                <div style={{ padding: '0 14px 12px 41px' }}>
                  <div className="banner banner-da" style={{ alignItems: 'center' }}>
                    <ExclamationCircleIcon style={{ width: 16, height: 16, flexShrink: 0 }} aria-hidden />
                    <span className="grow">{fileUpload.error}</span>
                    {fileUpload.contractId && (
                      <Button variant="secondary" size="sm" icon={ArrowPathIcon} onClick={() => retryProcessing(index)}>
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
      {files.some(f => f.hasSuggestions) && (
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
              const fileWithSuggestions = files.find(f => f.hasSuggestions && f.contractId)
              if (fileWithSuggestions?.contractId) {
                navigate(`/contracts/${fileWithSuggestions.contractId}`)
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
