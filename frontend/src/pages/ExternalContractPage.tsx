import { useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  DocumentTextIcon,
  ArrowDownTrayIcon,
  ChatBubbleLeftIcon,
  PaperAirplaneIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  ClockIcon,
} from '@heroicons/react/24/outline'
import axios from 'axios'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn, formatDate } from '@/lib/utils'

const apiBase = '/api/external'

interface ContractDetails {
  id: string
  filename: string
  contract_type?: string
  counterparty?: string
  effective_date?: string
  expiration_date?: string
  total_value?: number
  currency?: string
  status: string
  risk_level?: string
  can_download: boolean
  can_comment: boolean
}

interface Comment {
  id: string
  content: string
  author_name: string
  author_type: 'internal' | 'external'
  created_at: string
}

interface ValidateResponse {
  valid: boolean
  external_user: {
    id: string
    email: string
    full_name?: string
    company_name?: string
  }
  contract?: {
    id: string
    filename: string
  }
  expires_at: string
}

export default function ExternalContractPage() {
  const { token } = useParams<{ token: string }>()
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const [newComment, setNewComment] = useState('')

  // Token can come from URL path or query param
  const accessToken = token || searchParams.get('token') || ''

  // Validate token
  const { data: validation, isLoading: validating, error: validationError } = useQuery({
    queryKey: ['external-validate', accessToken],
    queryFn: async () => {
      const response = await axios.get<ValidateResponse>(`${apiBase}/validate`, {
        params: { token: accessToken }
      })
      return response.data
    },
    enabled: !!accessToken,
    retry: false,
  })

  // Get contract details
  const { data: contract, isLoading: loadingContract } = useQuery({
    queryKey: ['external-contract', accessToken, validation?.contract?.id],
    queryFn: async () => {
      const response = await axios.get<ContractDetails>(
        `${apiBase}/contracts/${validation!.contract!.id}`,
        { params: { token: accessToken } }
      )
      return response.data
    },
    enabled: !!validation?.contract?.id,
  })

  // Get comments
  const { data: commentsData } = useQuery({
    queryKey: ['external-comments', accessToken, validation?.contract?.id],
    queryFn: async () => {
      const response = await axios.get<{ items: Comment[]; total: number }>(
        `${apiBase}/contracts/${validation!.contract!.id}/comments`,
        { params: { token: accessToken } }
      )
      return response.data
    },
    enabled: !!validation?.contract?.id && contract?.can_comment,
  })

  // Add comment mutation
  const addCommentMutation = useMutation({
    mutationFn: async (content: string) => {
      const response = await axios.post(
        `${apiBase}/contracts/${validation!.contract!.id}/comments`,
        { content },
        { params: { token: accessToken } }
      )
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['external-comments'] })
      setNewComment('')
    },
  })

  const handleDownload = async () => {
    try {
      const response = await axios.get(
        `${apiBase}/contracts/${validation!.contract!.id}/download`,
        {
          params: { token: accessToken },
          responseType: 'blob',
        }
      )
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', contract?.filename || 'contract.pdf')
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Download failed:', error)
      alert('Failed to download contract')
    }
  }

  const handleSubmitComment = (e: React.FormEvent) => {
    e.preventDefault()
    if (newComment.trim()) {
      addCommentMutation.mutate(newComment.trim())
    }
  }

  // Loading state
  if (validating || loadingContract) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <LoadingSpinner size="lg" />
          <p className="mt-4 text-gray-600">Loading contract...</p>
        </div>
      </div>
    )
  }

  // Error state
  if (validationError || !accessToken) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <ExclamationTriangleIcon className="w-8 h-8 text-red-600" />
          </div>
          <h1 className="text-xl font-bold text-gray-900 mb-2">Access Denied</h1>
          <p className="text-gray-600">
            {!accessToken
              ? 'No access token provided.'
              : 'This link is invalid or has expired. Please contact the sender for a new link.'}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-violet-500 to-violet-600 flex items-center justify-center">
                <span className="text-white font-bold">E</span>
              </div>
              <div>
                <h1 className="font-semibold text-gray-900">Evaluetor</h1>
                <p className="text-xs text-gray-500">Shared Contract Portal</p>
              </div>
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <ShieldCheckIcon className="w-4 h-4 text-green-600" />
              <span>Viewing as {validation?.external_user.full_name || validation?.external_user.email}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-5xl mx-auto px-4 py-8">
        {/* Contract card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          {/* Contract header */}
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-4">
                <div className="p-3 bg-violet-100 rounded-lg">
                  <DocumentTextIcon className="w-8 h-8 text-violet-600" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-gray-900">
                    {contract?.filename}
                  </h2>
                  {contract?.counterparty && (
                    <p className="text-gray-600 mt-1">
                      Counterparty: {contract.counterparty}
                    </p>
                  )}
                  <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                    {contract?.contract_type && (
                      <span className="bg-gray-100 px-2 py-1 rounded capitalize">
                        {contract.contract_type.replace('_', ' ')}
                      </span>
                    )}
                    {contract?.risk_level && (
                      <span className={cn(
                        "px-2 py-1 rounded capitalize",
                        contract.risk_level === 'high' ? 'bg-red-100 text-red-700' :
                        contract.risk_level === 'medium' ? 'bg-amber-100 text-amber-700' :
                        'bg-green-100 text-green-700'
                      )}>
                        {contract.risk_level} risk
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Download button */}
              {contract?.can_download && (
                <button
                  onClick={handleDownload}
                  className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 transition-colors"
                >
                  <ArrowDownTrayIcon className="w-5 h-5" />
                  Download
                </button>
              )}
            </div>
          </div>

          {/* Contract details */}
          <div className="p-6 grid grid-cols-2 md:grid-cols-4 gap-6">
            {contract?.effective_date && (
              <div>
                <p className="text-sm text-gray-500">Effective Date</p>
                <p className="font-medium">{formatDate(contract.effective_date)}</p>
              </div>
            )}
            {contract?.expiration_date && (
              <div>
                <p className="text-sm text-gray-500">Expiration Date</p>
                <p className="font-medium">{formatDate(contract.expiration_date)}</p>
              </div>
            )}
            {contract?.total_value && (
              <div>
                <p className="text-sm text-gray-500">Total Value</p>
                <p className="font-medium">
                  {contract.currency || '$'}{contract.total_value.toLocaleString()}
                </p>
              </div>
            )}
            <div>
              <p className="text-sm text-gray-500">Status</p>
              <p className="font-medium capitalize">{contract?.status}</p>
            </div>
          </div>

          {/* Expiration notice */}
          {validation?.expires_at && (
            <div className="px-6 pb-6">
              <div className="flex items-center gap-2 text-sm text-amber-700 bg-amber-50 px-4 py-2 rounded-lg">
                <ClockIcon className="w-4 h-4" />
                <span>
                  This link expires on {formatDate(validation.expires_at)}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Comments section */}
        {contract?.can_comment && (
          <div className="mt-8 bg-white rounded-xl shadow-sm border border-gray-200">
            <div className="p-6 border-b border-gray-200">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <ChatBubbleLeftIcon className="w-5 h-5" />
                Comments ({commentsData?.total || 0})
              </h3>
            </div>

            {/* Comments list */}
            <div className="divide-y divide-gray-100 max-h-96 overflow-y-auto">
              {commentsData?.items.length === 0 ? (
                <div className="p-6 text-center text-gray-500">
                  No comments yet. Be the first to add one.
                </div>
              ) : (
                commentsData?.items.map((comment) => (
                  <div key={comment.id} className="p-4">
                    <div className="flex items-start gap-3">
                      <div className={cn(
                        "h-8 w-8 rounded-full flex items-center justify-center text-sm font-medium",
                        comment.author_type === 'external'
                          ? "bg-violet-100 text-violet-700"
                          : "bg-blue-100 text-blue-700"
                      )}>
                        {comment.author_name.charAt(0).toUpperCase()}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-gray-900">
                            {comment.author_name}
                          </span>
                          <span className={cn(
                            "text-xs px-1.5 py-0.5 rounded",
                            comment.author_type === 'external'
                              ? "bg-violet-100 text-violet-600"
                              : "bg-blue-100 text-blue-600"
                          )}>
                            {comment.author_type === 'external' ? 'External' : 'Internal'}
                          </span>
                          <span className="text-xs text-gray-500">
                            {formatDate(comment.created_at)}
                          </span>
                        </div>
                        <p className="text-gray-700 mt-1">{comment.content}</p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Add comment form */}
            <div className="p-4 border-t border-gray-200 bg-gray-50">
              <form onSubmit={handleSubmitComment} className="flex gap-2">
                <input
                  type="text"
                  value={newComment}
                  onChange={(e) => setNewComment(e.target.value)}
                  placeholder="Add a comment..."
                  className="flex-1 px-4 py-2 border rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                />
                <button
                  type="submit"
                  disabled={!newComment.trim() || addCommentMutation.isPending}
                  className="px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50 transition-colors flex items-center gap-2"
                >
                  <PaperAirplaneIcon className="w-4 h-4" />
                  Send
                </button>
              </form>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white mt-12">
        <div className="max-w-5xl mx-auto px-4 py-6 text-center text-sm text-gray-500">
          Powered by Evaluetor Contract Intelligence Platform
        </div>
      </footer>
    </div>
  )
}
