import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  CloudArrowUpIcon,
  DocumentTextIcon,
  XMarkIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn, formatFileSize } from '@/lib/utils'

interface FileUpload {
  file: File
  status: 'pending' | 'uploading' | 'uploaded' | 'processing' | 'completed' | 'error'
  progress: number
  error?: string
  contractId?: string
  clauseCount?: number
  obligationCount?: number
}

const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/msword': ['.doc'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/tiff': ['.tiff', '.tif'],
}

const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB

export default function UploadPage() {
  const navigate = useNavigate()
  const [files, setFiles] = useState<FileUpload[]>([])

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

    setFiles(prev => prev.map(f => {
      if (!f.contractId) return f

      const contract = contractsData.find(c => c?.id === f.contractId)
      if (!contract) return f

      if (contract.status === 'completed') {
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
  }, [contractsData])

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

    for (const index of pendingIndices) {
      await uploadFile(index)
    }
  }

  const pendingCount = files.filter((f) => f.status === 'pending').length
  const processingCount = files.filter((f) => f.status === 'uploaded' || f.status === 'processing').length
  const completedCount = files.filter((f) => f.status === 'completed').length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Upload Contracts</h1>
        <p className="mt-1 text-sm text-gray-500">
          Upload contract documents for AI-powered analysis
        </p>
      </div>

      {/* Processing indicator */}
      {processingCount > 0 && (
        <div className="rounded-lg bg-blue-50 border border-blue-200 p-4">
          <div className="flex items-center gap-3">
            <div className="relative">
              <ArrowPathIcon className="h-5 w-5 text-blue-600 animate-spin" />
            </div>
            <div>
              <p className="text-sm font-medium text-blue-800">
                Processing {processingCount} document{processingCount > 1 ? 's' : ''}...
              </p>
              <p className="text-xs text-blue-600 mt-0.5">
                AI is extracting clauses, obligations, and analyzing risks
              </p>
            </div>
          </div>
        </div>
      )}

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
          Supported formats: PDF, DOCX, DOC, PNG, JPEG, TIFF (max 50MB)
        </p>
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <h2 className="text-sm font-medium text-gray-900">
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
    </div>
  )
}
