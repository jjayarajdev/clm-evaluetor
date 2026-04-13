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
import api from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import PageHeader from '@/components/ui/PageHeader'
import { ProcessingStatusIndicator } from '@/components/contracts/ProcessingStatusIndicator'
import { cn, formatFileSize } from '@/lib/utils'

interface FileUpload {
  file: File
  status: 'pending' | 'uploading' | 'uploaded' | 'processing' | 'completed' | 'error'
  progress: number
  error?: string
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
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user, isSuperAdmin } = useAuth()
  const [files, setFiles] = useState<FileUpload[]>([])
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null)
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
        return { ...f, status: 'error', error: contract.processing_error || 'Processing failed' }
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
      error: rejection.errors[0]?.message || 'File rejected',
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
                error: error.response?.data?.detail || 'Upload failed',
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
      const result = await api.uploadFiles(pendingFiles, selectedClientId || undefined)

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
            }
          } else if (fileResult?.status === 'rejected') {
            return {
              ...f,
              status: 'error' as const,
              progress: 0,
              error: fileResult?.message || 'Upload rejected',
            }
          } else {
            return {
              ...f,
              status: 'error' as const,
              progress: 0,
              error: 'Upload failed - no response',
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
                error: error.response?.data?.detail || 'Batch upload failed',
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
        title="Upload Contracts"
        description="Upload contract documents for AI-powered analysis"
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
              <p className="text-xs text-gray-500">Uploading contracts to your organization</p>
            </div>
          </div>
        )}

        {/* Client grouping - show as optional sub-grouping */}
        {clients.length > 0 && (
          <>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">
              Group under client (optional)
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
                    <span className="text-gray-400">None</span>
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
                    <span className="text-gray-600">None</span>
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
                      <span className="text-xs text-gray-400">{client.contract_count} contracts</span>
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
                    <span className="text-primary-600 font-medium">Create New Client</span>
                  </button>
                </div>
              )}
            </div>
          </>
        )}

        {/* New Client Form */}
        {showNewClientForm && (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
            <h3 className="text-sm font-medium text-gray-900 mb-3">Create New Client</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Client Name *
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
                  Client Code *
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
                {createClientMutation.isPending ? 'Creating...' : 'Create Client'}
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
                Cancel
              </button>
            </div>
            {createClientMutation.isError && (
              <p className="mt-2 text-xs text-red-600">
                {(createClientMutation.error as any)?.response?.data?.detail || 'Failed to create client'}
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
          {isDragActive ? 'Drop files here' : 'Drag and drop files here'}
        </p>
        <p className="mt-2 text-sm text-gray-500">
          or <span className="text-primary-600 font-medium">browse</span> to select files
        </p>
        <p className="mt-4 text-xs text-gray-400">
          Supported formats: PDF, Word (.docx, .doc), Excel (.xlsx, .xls), PowerPoint (.pptx, .ppt), Images (max 50MB)
        </p>
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-900">
              Files ({files.length})
            </h2>
            {pendingCount > 0 && (
              <button onClick={uploadAll} className="btn-primary text-sm">
                Upload All ({pendingCount})
              </button>
            )}
          </div>
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
                  {fileUpload.status === 'completed' && (
                    <p className="text-xs text-green-600 mt-1">
                      {fileUpload.clauseCount} clauses, {fileUpload.obligationCount} obligations extracted
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
                        Upload
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
                      <span className="text-xs">Uploading...</span>
                    </div>
                  )}
                  {(fileUpload.status === 'uploaded' || fileUpload.status === 'processing') && (
                    <div className="flex items-center gap-2 text-blue-600">
                      <ArrowPathIcon className="h-5 w-5 animate-spin" />
                      <span className="text-xs">Processing...</span>
                    </div>
                  )}
                  {fileUpload.status === 'completed' && (
                    <div className="flex items-center gap-2">
                      <SparklesIcon className="h-5 w-5 text-green-500" />
                      <button
                        onClick={() => navigate(`/contracts/${fileUpload.contractId}`)}
                        className="text-sm text-primary-600 hover:text-primary-800 font-medium"
                      >
                        View
                      </button>
                      {fileUpload.hasSuggestions && fileUpload.suggestionCount && (
                        <span className="inline-flex items-center gap-1 bg-primary-100 text-primary-700 text-xs px-2 py-0.5 rounded-full">
                          <LinkIcon className="h-3 w-3" />
                          {fileUpload.suggestionCount} link{fileUpload.suggestionCount > 1 ? 's' : ''}
                        </span>
                      )}
                    </div>
                  )}
                  {fileUpload.status === 'error' && (
                    <div className="flex items-center gap-2">
                      <ExclamationCircleIcon className="h-5 w-5 text-red-500" />
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
                {completedCount} document{completedCount > 1 ? 's' : ''} processed successfully!
              </p>
              <p className="text-xs text-green-600 mt-0.5">
                AI analysis complete - clauses and obligations have been extracted
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
                  Related Contracts Found
                </p>
                <p className="text-xs text-primary-600 mt-0.5">
                  AI detected potential relationships with existing contracts
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
              Review
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
