/* Global upload + processing status (Direction B).
   Owns the upload job queue and the per-contract processing polls so upload
   status survives route changes — the backend keeps processing server-side,
   and this provider keeps reporting it. Mounted in MainLayout (inside the
   Router, auth and ToastProvider), NOT in main.tsx.

   Upload semantics mirror the pre-context UploadPage exactly:
   - single per-row uploads via POST /contracts/upload (api.uploadFile)
   - batch uploads via POST /contracts/upload/batch (api.uploadFiles) with
     optional client and group reuse (groupId) or create (groupName)
   - duplicate-content warnings from the batch response are kept on the job
   - polling: contract status + per-stage pipeline every 2s, queue depth every
     10s — enabled ONLY while jobs are active, so there is no idle polling.
   On completion the provider fires a toast with a View action and re-runs the
   page's cache-invalidation fan-out + suggested-links check. */
import {
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import api from '@/lib/api'
import type { QueueStatus } from '@/lib/api/contracts'
import { useToast } from '@/components/ui/Toast'

export type UploadJobState =
  | 'queued'
  | 'uploading'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'duplicate'

export interface UploadJob {
  id: string
  fileName: string
  fileSize: number
  state: UploadJobState
  contractId?: string
  /** Worker stage id (see PIPELINE_STAGES) once the worker picks the file up. */
  stage?: string
  progressPercent?: number
  error?: string
  /** Duplicate-content warning text; the file is still accepted + processed. */
  warning?: string
  clauseCount?: number
  obligationCount?: number
  hasSuggestions?: boolean
  suggestionCount?: number
  startedAt: number
}

export interface StartUploadOptions {
  /** Client the upload group is filed under (batch endpoint only). */
  clientId?: string
  /** Create a new group with this name (ignored when groupId is set). */
  groupName?: string
  /** Reuse an existing group. */
  groupId?: string
  /** Use the single-file endpoint (UploadPage's per-row upload button). */
  single?: boolean
}

/* Ordered pipeline stages, matching the stage ids the processing worker
   reports. Shared by the upload page's pipeline view and the upload tray. */
export const PIPELINE_STAGES: Array<{ id: string; labelKey: string }> = [
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

const ACTIVE_STATES: readonly UploadJobState[] = ['uploading', 'queued', 'duplicate', 'processing']

/** True while the job is still uploading or being tracked against the backend. */
export function isActiveJob(job: UploadJob): boolean {
  return ACTIVE_STATES.includes(job.state)
}

/* Query caches the upload page invalidated when a contract finished
   processing — reproduced here so completion refreshes the same surfaces. */
const COMPLETION_INVALIDATION_KEYS = [
  // Dashboard components
  'clauses-summary',
  'obligations-summary',
  'contracts-summary',
  'dashboard',
  'clients-summary',
  // Contract list and details
  'contracts',
  'contract-filter-options',
  // Post-signing pages
  'postsigning-dashboard',
  'renewal-calendar',
  'vendors',
  // Reports
  'contract-trend',
  'compliance-report',
]

interface UploadContextValue {
  jobs: UploadJob[]
  /** Worker queue depth/positions — polled only while jobs are active. */
  queueStatus: QueueStatus | undefined
  /** Upload files and start tracking them. Resolves to the new job ids. */
  startUploads: (files: File[], options?: StartUploadOptions) => Promise<string[]>
  /** Re-run processing for a failed contract. */
  retryProcessing: (contractId: string) => Promise<void>
  dismissJob: (id: string) => void
  clearFinished: () => void
}

const UploadContext = createContext<UploadContextValue | undefined>(undefined)

function makeJobId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `job-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function UploadProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const [jobs, setJobs] = useState<UploadJob[]>([])
  const jobsRef = useRef(jobs)
  jobsRef.current = jobs
  /** Job ids already toasted, so poll re-runs never re-notify. */
  const notifiedRef = useRef<Set<string>>(new Set())

  const patchJob = useCallback((id: string, patch: Partial<UploadJob>) => {
    setJobs((prev) => prev.map((j) => (j.id === id ? { ...j, ...patch } : j)))
  }, [])

  const activeContractIds = useMemo(
    () =>
      jobs
        .filter((j) => isActiveJob(j) && j.contractId)
        .map((j) => j.contractId as string),
    [jobs],
  )

  const startUploads = useCallback(
    async (files: File[], options: StartUploadOptions = {}): Promise<string[]> => {
      if (files.length === 0) return []
      const startedAt = Date.now()
      const newJobs: UploadJob[] = files.map((file) => ({
        id: makeJobId(),
        fileName: file.name,
        fileSize: file.size,
        state: 'uploading',
        startedAt,
      }))
      setJobs((prev) => [...prev, ...newJobs])

      const failJob = (job: UploadJob, error: string) => {
        patchJob(job.id, { state: 'failed', error })
        if (!notifiedRef.current.has(job.id)) {
          notifiedRef.current.add(job.id)
          toast({
            text: t('upload.uploadFailedToast', {
              name: job.fileName,
              defaultValue: '"{{name}}" failed to upload',
            }),
            error: true,
          })
        }
      }

      if (options.single) {
        // Per-file endpoint — mirrors the page's per-row upload (no group/client).
        await Promise.all(
          files.map(async (file, i) => {
            const job = newJobs[i]
            try {
              const result = await api.uploadFile(file)
              patchJob(job.id, { state: 'queued', contractId: result.id || undefined })
            } catch (error) {
              failJob(job, error instanceof Error ? error.message : t('upload.uploadFailed'))
            }
          }),
        )
        return newJobs.map((j) => j.id)
      }

      try {
        // Batch endpoint groups files into the same folder; an existing group id
        // takes precedence over creating one by name (reuse-or-create).
        const result = await api.uploadFiles(
          files,
          options.clientId,
          options.groupId ? undefined : options.groupName,
          options.groupId,
        )
        newJobs.forEach((job) => {
          const fileResult = result.files?.find(
            (r) =>
              r.filename === job.fileName ||
              r.filename?.includes(job.fileName.substring(0, 20)),
          )
          if (fileResult?.status === 'accepted' && fileResult.id) {
            const duplicate = Boolean(fileResult.duplicate_of_filename)
            patchJob(job.id, {
              state: duplicate ? 'duplicate' : 'queued',
              contractId: fileResult.id,
              warning: duplicate
                ? t('upload.duplicateWarning', { filename: fileResult.duplicate_of_filename })
                : undefined,
            })
          } else if (fileResult?.status === 'rejected') {
            failJob(job, fileResult.message || t('upload.uploadRejected'))
          } else {
            failJob(job, t('upload.uploadFailedNoResponse'))
          }
        })
      } catch (error) {
        const message = error instanceof Error ? error.message : t('upload.batchUploadFailed')
        newJobs.forEach((job) => failJob(job, message))
      }
      return newJobs.map((j) => j.id)
    },
    [patchJob, t, toast],
  )

  // Contract status poll — drives queued/duplicate → processing → completed/failed.
  const { data: contractsData } = useQuery({
    queryKey: ['contracts-status', activeContractIds],
    queryFn: async () => {
      const results = await Promise.all(
        activeContractIds.map((id) => api.getContract(id).catch(() => null)),
      )
      return results.filter(Boolean)
    },
    enabled: activeContractIds.length > 0,
    refetchInterval: 2000, // Poll every 2 seconds
  })

  // Per-stage pipeline progress (GET /contracts/:id/processing-status/current).
  const { data: stageData } = useQuery({
    queryKey: ['contracts-stages', activeContractIds],
    queryFn: async () => {
      const results = await Promise.all(
        activeContractIds.map((id) => api.getProcessingStatusCurrent(id).catch(() => null)),
      )
      return results.filter(Boolean)
    },
    enabled: activeContractIds.length > 0,
    refetchInterval: 2000,
  })

  // Queue position + ETA while files wait for the processing worker.
  const { data: queueStatus } = useQuery({
    queryKey: ['processing-queue-status'],
    queryFn: () => api.getProcessingQueueStatus(),
    enabled: activeContractIds.length > 0,
    refetchInterval: 10000,
  })

  // Fold stage/percent into the matching jobs.
  useEffect(() => {
    if (!stageData) return
    setJobs((prev) =>
      prev.map((j) => {
        if (!j.contractId || !isActiveJob(j)) return j
        const s = stageData.find((x) => x?.contract_id === j.contractId)
        if (!s || s.stage === 'idle') return j
        return { ...j, stage: s.stage, progressPercent: s.progress_percent }
      }),
    )
  }, [stageData])

  // State transitions from the contract poll + completion side effects
  // (toasts, cache invalidation, suggested-links check).
  useEffect(() => {
    if (!contractsData) return

    const updates = new Map<string, Partial<UploadJob>>()
    const completed: Array<{ job: UploadJob; contractId: string }> = []
    const failed: UploadJob[] = []

    for (const job of jobsRef.current) {
      if (!job.contractId || !isActiveJob(job)) continue
      const contract = contractsData.find((c) => c?.id === job.contractId)
      if (!contract) continue

      if (contract.status === 'completed') {
        updates.set(job.id, {
          state: 'completed',
          progressPercent: 100,
          clauseCount: contract.clause_count,
          obligationCount: contract.obligation_count,
        })
        completed.push({ job, contractId: job.contractId })
      } else if (contract.status === 'processing') {
        if (job.state !== 'processing') updates.set(job.id, { state: 'processing' })
      } else if (contract.status === 'failed') {
        updates.set(job.id, {
          state: 'failed',
          error: contract.processing_error || t('upload.processingFailed'),
        })
        failed.push(job)
      }
    }

    if (updates.size > 0) {
      setJobs((prev) => prev.map((j) => (updates.has(j.id) ? { ...j, ...updates.get(j.id) } : j)))
    }

    for (const { job, contractId } of completed) {
      if (notifiedRef.current.has(job.id)) continue
      notifiedRef.current.add(job.id)
      toast({
        text: t('upload.fileProcessedToast', {
          name: job.fileName,
          defaultValue: '"{{name}}" processed',
        }),
        action: {
          label: t('upload.view', { defaultValue: 'View' }),
          run: () => navigate(`/contracts/${contractId}`),
        },
      })
    }
    for (const job of failed) {
      if (notifiedRef.current.has(job.id)) continue
      notifiedRef.current.add(job.id)
      toast({
        text: t('upload.fileFailedToast', {
          name: job.fileName,
          defaultValue: '"{{name}}" failed processing',
        }),
        error: true,
      })
    }

    if (completed.length > 0) {
      // Refresh every surface the upload page used to invalidate on completion.
      COMPLETION_INVALIDATION_KEYS.forEach((key) =>
        queryClient.invalidateQueries({ queryKey: [key] }),
      )

      // Check for suggested links on newly completed contracts.
      completed.forEach(async ({ contractId }) => {
        try {
          const suggestions = await api.getSuggestedLinks(contractId)
          if (suggestions.pending_count > 0) {
            setJobs((prev) =>
              prev.map((j) =>
                j.contractId === contractId
                  ? { ...j, hasSuggestions: true, suggestionCount: suggestions.pending_count }
                  : j,
              ),
            )
          }
        } catch {
          // Ignore errors — suggestions are optional
        }
      })
    }
  }, [contractsData, navigate, queryClient, t, toast])

  const retryProcessing = useCallback(async (contractId: string) => {
    try {
      await api.processContract(contractId)
      // Allow completion/failure toasts to fire again for the retried job.
      jobsRef.current
        .filter((j) => j.contractId === contractId)
        .forEach((j) => notifiedRef.current.delete(j.id))
      setJobs((prev) =>
        prev.map((j) =>
          j.contractId === contractId
            ? { ...j, state: 'queued', error: undefined, stage: undefined, progressPercent: undefined }
            : j,
        ),
      )
    } catch {
      // keep the row in error state; the message is already shown
    }
  }, [])

  const dismissJob = useCallback((id: string) => {
    setJobs((prev) => prev.filter((j) => j.id !== id))
  }, [])

  const clearFinished = useCallback(() => {
    setJobs((prev) => prev.filter((j) => isActiveJob(j)))
  }, [])

  const value = useMemo(
    () => ({ jobs, queueStatus, startUploads, retryProcessing, dismissJob, clearFinished }),
    [jobs, queueStatus, startUploads, retryProcessing, dismissJob, clearFinished],
  )

  return <UploadContext.Provider value={value}>{children}</UploadContext.Provider>
}

export function useUploads(): UploadContextValue {
  const ctx = useContext(UploadContext)
  if (!ctx) throw new Error('useUploads must be used within UploadProvider')
  return ctx
}
