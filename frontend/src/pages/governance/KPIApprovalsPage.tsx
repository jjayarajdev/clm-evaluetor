import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'

export default function KPIApprovalsPage() {
  const queryClient = useQueryClient()
  const [actionModal, setActionModal] = useState<{
    type: 'approve' | 'reject'
    kpiId: string
    scoreId: string
    kpiName: string
  } | null>(null)
  const [comments, setComments] = useState('')

  const { data: pendingApprovals = [], isLoading } = useQuery({
    queryKey: ['pending-approvals'],
    queryFn: () => api.getPendingApprovals(),
  })

  const approveMutation = useMutation({
    mutationFn: ({ kpiId, scoreId, comments }: { kpiId: string; scoreId: string; comments?: string }) =>
      api.approveScore(kpiId, scoreId, { comments }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pending-approvals'] })
      setActionModal(null)
      setComments('')
    },
  })

  const rejectMutation = useMutation({
    mutationFn: ({ kpiId, scoreId, comments }: { kpiId: string; scoreId: string; comments?: string }) =>
      api.rejectScore(kpiId, scoreId, { comments }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pending-approvals'] })
      setActionModal(null)
      setComments('')
    },
  })

  const handleAction = () => {
    if (!actionModal) return
    const payload = { kpiId: actionModal.kpiId, scoreId: actionModal.scoreId, comments: comments || undefined }
    if (actionModal.type === 'approve') {
      approveMutation.mutate(payload)
    } else {
      rejectMutation.mutate(payload)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">KPI Score Approvals</h1>
        <p className="text-sm text-gray-500 mt-1">
          Review and approve or reject pending perception scores
        </p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card card-body text-center">
          <p className="text-2xl font-bold text-amber-600">{pendingApprovals.length}</p>
          <p className="text-xs text-gray-500">Pending Approvals</p>
        </div>
        <div className="card card-body text-center">
          <p className="text-2xl font-bold text-blue-600">
            {pendingApprovals.filter(a => a.perspective === 'internal').length}
          </p>
          <p className="text-xs text-gray-500">Internal Scores</p>
        </div>
        <div className="card card-body text-center">
          <p className="text-2xl font-bold text-purple-600">
            {pendingApprovals.filter(a => a.perspective === 'external').length}
          </p>
          <p className="text-xs text-gray-500">External Scores</p>
        </div>
      </div>

      {/* Approvals Table */}
      <div className="card">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">KPI</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Relationship</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Perspective</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Score</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Period</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Comments</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {pendingApprovals.map((approval) => (
                <tr key={approval.score_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <p className="text-sm font-medium text-gray-900">{approval.kpi_name}</p>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">{approval.relationship_name}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={cn(
                      'px-2 py-0.5 rounded text-xs font-medium',
                      approval.perspective === 'internal'
                        ? 'bg-blue-100 text-blue-800'
                        : 'bg-purple-100 text-purple-800'
                    )}>
                      {approval.perspective}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className="text-lg font-bold text-gray-900">{approval.score}</span>
                    <span className="text-xs text-gray-400">/10</span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">{approval.period || '—'}</td>
                  <td className="px-4 py-3 text-sm text-gray-500 max-w-[200px] truncate">
                    {approval.comments || '—'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-center gap-2">
                      <button
                        onClick={() => setActionModal({
                          type: 'approve',
                          kpiId: approval.kpi_id,
                          scoreId: approval.score_id,
                          kpiName: approval.kpi_name,
                        })}
                        className="p-1.5 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                        title="Approve"
                      >
                        <CheckCircleIcon className="h-5 w-5" />
                      </button>
                      <button
                        onClick={() => setActionModal({
                          type: 'reject',
                          kpiId: approval.kpi_id,
                          scoreId: approval.score_id,
                          kpiName: approval.kpi_name,
                        })}
                        className="p-1.5 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        title="Reject"
                      >
                        <XCircleIcon className="h-5 w-5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {pendingApprovals.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center">
                    <ClockIcon className="h-8 w-8 text-gray-300 mx-auto mb-2" />
                    <p className="text-sm text-gray-500">No pending approvals</p>
                    <p className="text-xs text-gray-400 mt-1">All scores have been reviewed</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Action Modal */}
      {actionModal && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">
                {actionModal.type === 'approve' ? 'Approve Score' : 'Reject Score'}
              </h2>
              <button onClick={() => { setActionModal(null); setComments('') }} className="text-gray-400 hover:text-gray-600">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              {actionModal.type === 'approve' ? 'Approve' : 'Reject'} score for <span className="font-medium">{actionModal.kpiName}</span>?
            </p>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Comments</label>
              <textarea
                value={comments}
                onChange={(e) => setComments(e.target.value)}
                rows={3}
                placeholder={actionModal.type === 'reject' ? 'Reason for rejection...' : 'Optional comments...'}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-violet-500"
              />
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => { setActionModal(null); setComments('') }} className="btn-secondary">Cancel</button>
              <button
                onClick={handleAction}
                disabled={approveMutation.isPending || rejectMutation.isPending}
                className={cn(
                  'px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors',
                  actionModal.type === 'approve'
                    ? 'bg-green-600 hover:bg-green-700'
                    : 'bg-red-600 hover:bg-red-700'
                )}
              >
                {(approveMutation.isPending || rejectMutation.isPending)
                  ? 'Processing...'
                  : actionModal.type === 'approve' ? 'Approve' : 'Reject'
                }
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
