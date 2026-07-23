import { useState, useCallback, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  CloudArrowUpIcon,
  DocumentTextIcon,
  XMarkIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
  SparklesIcon,
  BuildingOfficeIcon,
  PlusIcon,
  ChevronDownIcon,
  LinkIcon,
} from '@heroicons/react/24/outline'
import { useTranslation } from 'react-i18next'
import api from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import { useTenantConfig } from '@/contexts/TenantConfigContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import PageHeader from '@/components/ui/PageHeader'
import { ProcessingStatusIndicator } from '@/components/contracts/ProcessingStatusIndicator'
import { cn, formatFileSize } from '@/lib/utils'

interface FileUpload {
  file: File
  status: 'pending' | 'uploading' | 'uploaded' | 'processing' | 'completed' | 'error'
  progress: number
  error?: string
  warning?: string
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

export default function UploadPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user, isSuperAdmin } = useAuth()
  const { config } = useTenantConfig()
  const [files, setFiles] = useState<FileUpload[]>([])
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null)
  const [groupName, setGroupName] = useState('')
  const [showClientDropdown, setShowClientDropdown] = useState(false)
  const [showNewClientForm, setShowNewClientForm] = useState(false)
  const [newClientName, setNewClientName] = useState('')
  const [newClientCode, setNewClientCode] = useState('')
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowClientDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

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

  const selectedClient = clients.find(c => c.id === selectedClientId)

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

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
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
                error: error.response?.data?.detail || t('upload.uploadFailed'),
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
                error: error.response?.data?.detail || t('upload.batchUploadFailed'),
              }
            : f
        )
      )
    }
  }

  const pendingCount = files.filter((f) => f.status === 'pending').length
  const completedCount = files.filter((f) => f.status === 'completed').length

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title={t('upload.title')}
        description={t('upload.description')}
        icon={CloudArrowUpIcon}
        variant="bordered"
      />

      {/* Processing progress trackers */}
      {processingContractIds.map((contractId) => {
        const file = files.find(f => f.contractId === contractId)
        return (
          <div key={contractId}>
            {file && (
              <p className="text-xs text-gray-500 mb-1 font-medium">{file.file.name}</p>
            )}
            <ProcessingStatusIndicator
              contractId={contractId}
              autoConnect
              onComplete={() => {
                queryClient.invalidateQueries({ queryKey: ['contracts-status'] })
              }}
            />
          </div>
        )
      })}

      {/* Tenant context + optional Client Selector */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
        {/* Show tenant context for non-super-admin users */}
        {!isSuperAdmin && user?.tenant_name && (
          <div className="flex items-center gap-3 mb-3">
            <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-primary-100">
              <BuildingOfficeIcon className="h-5 w-5 text-primary-600" />
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-900">{user.tenant_name}</p>
              <p className="text-xs text-gray-500">{t('upload.uploadingToOrg')}</p>
            </div>
          </div>
        )}

        {/* Industry profile context */}
        {config?.industry_name && (
          <div className="flex items-center gap-2.5 p-2.5 bg-violet-50 rounded-lg border border-violet-100 mb-3">
            <SparklesIcon className="h-4 w-4 text-violet-500 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-violet-800">
                {t('upload.profileActive', { name: config.industry_name })}
              </p>
              <p className="text-[10px] text-violet-600 mt-0.5">
                {t('upload.profileStats', {
                  types: config.contract_types?.length || 0,
                  clauses: config.clause_types?.length || 0,
                  slas: config.sla_metrics?.length || 0,
                })}
              </p>
            </div>
            <a
              href="/admin/industry-profiles"
              className="text-[10px] text-violet-500 hover:text-violet-700 font-medium whitespace-nowrap"
            >
              {t('upload.viewProfile')}
            </a>
          </div>
        )}

        {/* Contract group (optional) — existing group name reuses it, new name creates one */}
        <div className="mb-4">
          <label className="block text-xs font-medium text-gray-500 mb-1.5">
            {t('upload.groupLabel')}
          </label>
          <input
            className="w-full px-3 py-2 border border-gray-200 rounded-lg bg-gray-50 hover:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm"
            placeholder={t('upload.groupPlaceholder')}
            value={groupName}
            onChange={(e) => setGroupName(e.target.value)}
            list="upload-group-options"
          />
          <datalist id="upload-group-options">
            {groups.map((g) => (
              <option key={g.id} value={g.name} />
            ))}
          </datalist>
          {user?.business_unit_name && (
            <p className="mt-1 text-[11px] text-gray-400">
              {t('upload.defaultBuHint', { bu: user.business_unit_name })}
            </p>
          )}
        </div>

        {/* Client grouping - show as optional sub-grouping */}
        {clients.length > 0 && (
          <>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">
              {t('upload.groupUnderClient')}
            </label>
            <div className="relative" ref={dropdownRef}>
              <button
                type="button"
                onClick={() => setShowClientDropdown(!showClientDropdown)}
                className="w-full flex items-center justify-between px-3 py-2 border border-gray-200 rounded-lg bg-gray-50 hover:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm"
              >
                <div className="flex items-center gap-2">
                  {selectedClient ? (
                    <span className="text-gray-900">
                      {selectedClient.name} <span className="text-gray-500">({selectedClient.code})</span>
                    </span>
                  ) : (
                    <span className="text-gray-400">{t('upload.none')}</span>
                  )}
                </div>
                <ChevronDownIcon className={cn('h-4 w-4 text-gray-400 transition-transform', showClientDropdown && 'rotate-180')} />
              </button>

              {showClientDropdown && (
                <div className="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-64 overflow-auto">
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedClientId(null)
                      setShowClientDropdown(false)
                    }}
                    className={cn(
                      'w-full px-4 py-2.5 text-left hover:bg-gray-50 flex items-center gap-2',
                      !selectedClientId && 'bg-primary-50'
                    )}
                  >
                    <span className="text-gray-600">{t('upload.none')}</span>
                  </button>

                  {clients.map((client) => (
                    <button
                      key={client.id}
                      type="button"
                      onClick={() => {
                        setSelectedClientId(client.id)
                        setShowClientDropdown(false)
                      }}
                      className={cn(
                        'w-full px-4 py-2.5 text-left hover:bg-gray-50 flex items-center justify-between',
                        selectedClientId === client.id && 'bg-primary-50'
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <BuildingOfficeIcon className="h-4 w-4 text-gray-400" />
                        <span className="text-gray-900">{client.name}</span>
                        <span className="text-gray-500 text-sm">({client.code})</span>
                      </div>
                      <span className="text-xs text-gray-400">{t('upload.contractCount', { count: client.contract_count })}</span>
                    </button>
                  ))}

                  <button
                    type="button"
                    onClick={() => {
                      setShowNewClientForm(true)
                      setShowClientDropdown(false)
                    }}
                    className="w-full px-4 py-2.5 text-left hover:bg-gray-50 flex items-center gap-2 border-t border-gray-200"
                  >
                    <PlusIcon className="h-4 w-4 text-primary-600" />
                    <span className="text-primary-600 font-medium">{t('upload.createNewClient')}</span>
                  </button>
                </div>
              )}
            </div>
          </>
        )}

        {/* New Client Form */}
        {showNewClientForm && (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
            <h3 className="text-sm font-medium text-gray-900 mb-3">{t('upload.createNewClient')}</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  {t('upload.clientName')}
                </label>
                <input
                  type="text"
                  value={newClientName}
                  onChange={(e) => setNewClientName(e.target.value)}
                  placeholder="e.g., ING Bank N.V."
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  {t('upload.clientCode')}
                </label>
                <input
                  type="text"
                  value={newClientCode}
                  onChange={(e) => setNewClientCode(e.target.value.toUpperCase())}
                  placeholder="e.g., ING"
                  maxLength={50}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm uppercase focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>
            <div className="mt-4 flex items-center gap-2">
              <button
                type="button"
                onClick={() => createClientMutation.mutate()}
                disabled={!newClientName.trim() || !newClientCode.trim() || createClientMutation.isPending}
                className="btn-primary text-sm py-1.5 px-4 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {createClientMutation.isPending ? t('upload.creating') : t('upload.createClient')}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowNewClientForm(false)
                  setNewClientName('')
                  setNewClientCode('')
                }}
                className="btn-secondary text-sm py-1.5 px-4"
              >
                {t('common.cancel')}
              </button>
            </div>
            {createClientMutation.isError && (
              <p className="mt-2 text-xs text-red-600">
                {(createClientMutation.error as any)?.response?.data?.detail || t('upload.createClientFailed')}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={cn(
          'border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors',
          isDragActive
            ? 'border-primary-500 bg-primary-50'
            : 'border-gray-300 hover:border-primary-400 hover:bg-gray-50'
        )}
      >
        <input {...getInputProps()} />
        <CloudArrowUpIcon className="mx-auto h-12 w-12 text-gray-400" />
        <p className="mt-4 text-lg font-medium text-gray-900">
          {isDragActive ? t('upload.dropFilesHere') : t('upload.dragAndDrop')}
        </p>
        <p className="mt-2 text-sm text-gray-500">
          {t('upload.orBrowse')}
        </p>
        <p className="mt-4 text-xs text-gray-400">
          {t('upload.supportedFormats')}
        </p>
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-900">
              {t('upload.filesCount', { count: files.length })}
            </h2>
            {pendingCount > 0 && (
              <button onClick={uploadAll} className="btn-primary text-sm">
                {t('upload.uploadAll', { count: pendingCount })}
              </button>
            )}
          </div>
          {queueStatus && processingContractIds.length > 0 && queueStatus.queue_depth > 0 && (
            <div className="px-4 py-2 bg-blue-50 border-b border-blue-100 text-xs text-blue-700 flex flex-wrap gap-4">
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
          <div className="divide-y divide-gray-200">
            {files.map((fileUpload, index) => (
              <div key={index} className="px-4 py-3 flex items-center gap-4">
                <DocumentTextIcon className="h-8 w-8 text-gray-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {fileUpload.file.name}
                  </p>
                  <p className="text-xs text-gray-500">
                    {formatFileSize(fileUpload.file.size)}
                  </p>
                  {fileUpload.error && (
                    <p className="text-xs text-red-600 mt-1">{fileUpload.error}</p>
                  )}
                  {fileUpload.warning && (
                    <p className="text-xs text-amber-600 mt-1">⚠ {fileUpload.warning}</p>
                  )}
                  {fileUpload.status === 'completed' && (
                    <p className="text-xs text-green-600 mt-1">
                      {t('upload.extractedSummary', { clauses: fileUpload.clauseCount, obligations: fileUpload.obligationCount })}
                    </p>
                  )}
                </div>
                <div className="shrink-0 flex items-center gap-2">
                  {fileUpload.status === 'pending' && (
                    <>
                      <button
                        onClick={() => uploadFile(index)}
                        className="btn-secondary text-sm py-1 px-3"
                      >
                        {t('nav.upload')}
                      </button>
                      <button
                        onClick={() => removeFile(index)}
                        className="p-1 text-gray-400 hover:text-gray-600"
                      >
                        <XMarkIcon className="h-5 w-5" />
                      </button>
                    </>
                  )}
                  {fileUpload.status === 'uploading' && (
                    <div className="flex items-center gap-2 text-gray-500">
                      <LoadingSpinner size="sm" />
                      <span className="text-xs">{t('upload.uploading')}</span>
                    </div>
                  )}
                  {(fileUpload.status === 'uploaded' || fileUpload.status === 'processing') && (
                    <div className="flex items-center gap-2 text-blue-600">
                      <ArrowPathIcon className="h-5 w-5 animate-spin" />
                      <span className="text-xs">{t('upload.processing')}</span>
                    </div>
                  )}
                  {fileUpload.status === 'completed' && (
                    <div className="flex items-center gap-2">
                      <SparklesIcon className="h-5 w-5 text-green-500" />
                      <button
                        onClick={() => navigate(`/contracts/${fileUpload.contractId}`)}
                        className="text-sm text-primary-600 hover:text-primary-800 font-medium"
                      >
                        {t('upload.view')}
                      </button>
                      {fileUpload.hasSuggestions && fileUpload.suggestionCount && (
                        <span className="inline-flex items-center gap-1 bg-primary-100 text-primary-700 text-xs px-2 py-0.5 rounded-full">
                          <LinkIcon className="h-3 w-3" />
                          {t('upload.linkCount', { count: fileUpload.suggestionCount })}
                        </span>
                      )}
                    </div>
                  )}
                  {fileUpload.status === 'error' && (
                    <div className="flex items-center gap-2">
                      <ExclamationCircleIcon className="h-5 w-5 text-red-500" />
                      {fileUpload.contractId && (
                        <button
                          onClick={() => retryProcessing(index)}
                          className="btn-secondary text-sm py-1 px-3"
                        >
                          {t('upload.retry')}
                        </button>
                      )}
                      <button
                        onClick={() => removeFile(index)}
                        className="p-1 text-gray-400 hover:text-gray-600"
                      >
                        <XMarkIcon className="h-5 w-5" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Completed summary */}
      {completedCount > 0 && (
        <div className="rounded-lg bg-green-50 border border-green-200 p-4">
          <div className="flex items-center gap-3">
            <CheckCircleIcon className="h-5 w-5 text-green-500" />
            <div>
              <p className="text-sm font-medium text-green-800">
                {t('upload.processedSuccessfully', { count: completedCount })}
              </p>
              <p className="text-xs text-green-600 mt-0.5">
                {t('upload.analysisComplete')}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Related contracts found notification */}
      {files.some(f => f.hasSuggestions) && (
        <div className="rounded-lg bg-primary-50 border border-primary-200 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <LinkIcon className="h-5 w-5 text-primary-500" />
              <div>
                <p className="text-sm font-medium text-primary-800">
                  {t('upload.relatedContractsFound')}
                </p>
                <p className="text-xs text-primary-600 mt-0.5">
                  {t('upload.relatedContractsDesc')}
                </p>
              </div>
            </div>
            <button
              onClick={() => {
                // Navigate to the first contract with suggestions
                const fileWithSuggestions = files.find(f => f.hasSuggestions && f.contractId)
                if (fileWithSuggestions?.contractId) {
                  navigate(`/contracts/${fileWithSuggestions.contractId}`)
                }
              }}
              className="btn-primary text-sm py-1.5 px-4"
            >
              {t('upload.review')}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
