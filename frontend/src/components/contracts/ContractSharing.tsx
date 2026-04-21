import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  UserPlusIcon,
  TrashIcon,
  ClipboardDocumentIcon,
  CheckIcon,
  XMarkIcon,
  LinkIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'
import type { ContractShareCreate, ContractShareWithUser } from '@/types/contract-share'

interface ContractSharingProps {
  contractId: string
}

export default function ContractSharing({ contractId }: ContractSharingProps) {
  const queryClient = useQueryClient()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [selectedUserId, setSelectedUserId] = useState('')
  const [canDownload, setCanDownload] = useState(false)
  const [canComment, setCanComment] = useState(true)
  const [expiresInDays, setExpiresInDays] = useState<number | ''>('')
  const [message, setMessage] = useState('')
  const [copiedToken, setCopiedToken] = useState<string | null>(null)
  const [showLinkModal, setShowLinkModal] = useState(false)
  const [generatedLink, setGeneratedLink] = useState('')
  const [shareError, setShareError] = useState<string | null>(null)

  // Fetch existing shares
  const { data: sharesData, isLoading: sharesLoading } = useQuery({
    queryKey: ['contract-shares', contractId],
    queryFn: () => api.getContractShares(contractId),
  })

  // Fetch external users for dropdown
  const { data: externalUsersData } = useQuery({
    queryKey: ['external-users'],
    queryFn: () => api.getExternalUsers(),
  })

  // Share mutation
  const shareMutation = useMutation({
    mutationFn: (data: ContractShareCreate) => api.shareContract(contractId, data),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['contract-shares', contractId] })
      setShareError(null)
      closeModal()
      // Show the access URL in a modal
      if (response.access_url) {
        const fullUrl = `${window.location.origin}${response.access_url}`
        setGeneratedLink(fullUrl)
        setShowLinkModal(true)
      }
    },
    onError: (err: any) => {
      setShareError(err?.response?.data?.detail || err?.message || 'Failed to share contract')
    },
  })

  // Revoke mutation
  const revokeMutation = useMutation({
    mutationFn: (shareId: string) => api.revokeContractShare(contractId, shareId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract-shares', contractId] })
    },
  })

  const closeModal = () => {
    setIsModalOpen(false)
    setSelectedUserId('')
    setCanDownload(false)
    setCanComment(true)
    setExpiresInDays('')
    setMessage('')
  }

  const handleShare = (e: React.FormEvent) => {
    e.preventDefault()
    setShareError(null)
    if (!selectedUserId) return

    shareMutation.mutate({
      external_user_id: selectedUserId,
      can_download: canDownload,
      can_comment: canComment,
      expires_in_days: expiresInDays ? Number(expiresInDays) : undefined,
      message: message || undefined,
    })
  }

  const handleRevoke = (share: ContractShareWithUser) => {
    if (confirm(`Revoke access for ${share.external_user.full_name || share.external_user.email}?`)) {
      revokeMutation.mutate(share.id)
    }
  }

  const copyAccessLink = (token: string) => {
    const fullUrl = `${window.location.origin}/external/contracts/${token}`
    navigator.clipboard.writeText(fullUrl)
    setCopiedToken(token)
    setTimeout(() => setCopiedToken(null), 3000)
  }

  // Filter out already shared users
  const sharedUserIds = new Set(sharesData?.items.map(s => s.external_user_id) || [])
  const availableUsers = externalUsersData?.items.filter(u => !sharedUserIds.has(u.id)) || []

  if (sharesLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">External Sharing</h2>
          <p className="text-sm text-gray-500">
            Share this contract with external parties for review and collaboration
          </p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          <UserPlusIcon className="w-5 h-5" />
          Share with External User
        </button>
      </div>

      {/* Success message */}
      {copiedToken && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-2">
          <CheckIcon className="w-5 h-5 text-green-600" />
          <span className="text-green-700">Access link copied to clipboard!</span>
        </div>
      )}

      {/* Shares list */}
      <div className="bg-white rounded-xl border border-gray-200">
        {!sharesData?.items.length ? (
          <div className="text-center py-12 text-gray-500">
            <UserPlusIcon className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p className="text-lg font-medium">No external shares</p>
            <p className="mt-1">Share this contract with external parties to collaborate.</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {sharesData.items.map((share) => (
              <div key={share.id} className="p-4 flex items-center justify-between hover:bg-gray-50">
                <div className="flex items-center gap-4">
                  <div className="h-10 w-10 rounded-full bg-primary-100 flex items-center justify-center">
                    <span className="text-sm font-semibold text-primary-700">
                      {(share.external_user.full_name || share.external_user.email).charAt(0).toUpperCase()}
                    </span>
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">
                      {share.external_user.full_name || share.external_user.email}
                    </p>
                    <p className="text-sm text-gray-500">
                      {share.external_user.email}
                      {share.external_user.company_name && (
                        <span className="text-gray-400"> - {share.external_user.company_name}</span>
                      )}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  {/* Permissions badges */}
                  <div className="flex gap-2">
                    {share.can_comment && (
                      <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
                        Can Comment
                      </span>
                    )}
                    {share.can_download && (
                      <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">
                        Can Download
                      </span>
                    )}
                  </div>

                  {/* Access count */}
                  <span className="text-sm text-gray-500">
                    {share.access_count} view{share.access_count !== 1 ? 's' : ''}
                  </span>

                  {/* Expiration */}
                  {share.expires_at && (
                    <span className={cn(
                      "text-xs px-2 py-1 rounded",
                      new Date(share.expires_at) < new Date()
                        ? "bg-red-100 text-red-700"
                        : "bg-gray-100 text-gray-600"
                    )}>
                      {new Date(share.expires_at) < new Date()
                        ? 'Expired'
                        : `Expires ${new Date(share.expires_at).toLocaleDateString()}`
                      }
                    </span>
                  )}

                  {/* Actions */}
                  <div className="flex gap-1">
                    <button
                      onClick={() => copyAccessLink(share.id)}
                      className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded"
                      title="Copy access link"
                    >
                      <ClipboardDocumentIcon className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleRevoke(share)}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                      title="Revoke access"
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Share Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
            <div className="flex items-center justify-between p-6 border-b">
              <h2 className="text-xl font-semibold">Share Contract</h2>
              <button
                onClick={closeModal}
                className="p-1 text-gray-400 hover:text-gray-600"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleShare} className="p-6 space-y-4">
              {shareError && (
                <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
                  {shareError}
                </div>
              )}
              {/* External user select */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  External User *
                </label>
                <select
                  value={selectedUserId}
                  onChange={(e) => setSelectedUserId(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  required
                >
                  <option value="">Select an external user...</option>
                  {availableUsers.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.full_name || user.email}
                      {user.company_name && ` (${user.company_name})`}
                    </option>
                  ))}
                </select>
                {availableUsers.length === 0 && (
                  <p className="mt-1 text-sm text-amber-600">
                    No available external users. Create one first in Admin &gt; External Users.
                  </p>
                )}
              </div>

              {/* Permissions */}
              <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-700">
                  Permissions
                </label>
                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={canComment}
                      onChange={(e) => setCanComment(e.target.checked)}
                      className="rounded text-primary-600 focus:ring-primary-500"
                    />
                    <span className="text-sm text-gray-700">Can comment</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={canDownload}
                      onChange={(e) => setCanDownload(e.target.checked)}
                      className="rounded text-primary-600 focus:ring-primary-500"
                    />
                    <span className="text-sm text-gray-700">Can download</span>
                  </label>
                </div>
              </div>

              {/* Expiration */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Expires in (days)
                </label>
                <input
                  type="number"
                  value={expiresInDays}
                  onChange={(e) => setExpiresInDays(e.target.value ? Number(e.target.value) : '')}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="Leave empty for no expiration"
                  min={1}
                  max={365}
                />
              </div>

              {/* Message */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Message (optional)
                </label>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="Add a message for the recipient..."
                  rows={2}
                />
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-3 pt-4 border-t">
                <button
                  type="button"
                  onClick={closeModal}
                  className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!selectedUserId || shareMutation.isPending}
                  className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
                >
                  {shareMutation.isPending ? 'Sharing...' : 'Share Contract'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Link Generated Modal */}
      {showLinkModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4">
            <div className="flex items-center justify-between p-6 border-b">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-100 rounded-full">
                  <CheckIcon className="w-6 h-6 text-green-600" />
                </div>
                <h2 className="text-xl font-semibold">Contract Shared Successfully</h2>
              </div>
              <button
                onClick={() => setShowLinkModal(false)}
                className="p-1 text-gray-400 hover:text-gray-600"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <p className="text-gray-600">
                Share this link with the external user to give them access to the contract:
              </p>

              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <LinkIcon className="w-4 h-4 text-gray-500" />
                  <span className="text-sm font-medium text-gray-700">Access Link</span>
                </div>
                <div className="bg-white border rounded p-3 break-all text-sm text-gray-800 font-mono">
                  {generatedLink}
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(generatedLink)
                    setCopiedToken('link')
                    setTimeout(() => setCopiedToken(null), 3000)
                  }}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  {copiedToken === 'link' ? (
                    <>
                      <CheckIcon className="w-5 h-5 text-green-600" />
                      Copied!
                    </>
                  ) : (
                    <>
                      <ClipboardDocumentIcon className="w-5 h-5" />
                      Copy Link
                    </>
                  )}
                </button>
                <button
                  onClick={() => setShowLinkModal(false)}
                  className="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
