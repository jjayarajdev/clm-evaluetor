import { useState, useMemo, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  CheckCircleIcon,
  XCircleIcon,
  TrashIcon,
  XMarkIcon,
  BuildingOffice2Icon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'
import type { PendingApproval } from '@/types/fitgap'

const CAT_LABEL: Record<string, string> = {
  service_delivery: 'Delivery', quality: 'Quality', cost_efficiency: 'Cost',
  communication: 'Comms', innovation: 'Innovation', compliance: 'Compliance',
  satisfaction: 'Satisfaction', risk: 'Risk', other: 'Other',
}

export default function KPIApprovalsPage() {
  const qc = useQueryClient()
  const [relId, setRelId] = useState('')
  const [period, setPeriod] = useState('')
  const [editing, setEditing] = useState<Record<string, number>>({})
  const [modal, setModal] = useState<{ type: 'approve' | 'reject'; kpiId: string; scoreId: string; name: string } | null>(null)
  const [comment, setComment] = useState('')

  const { data: rels = [] } = useQuery({
    queryKey: ['relationships'],
    queryFn: () => api.getRelationships(),
  })

  const { data: scores = [], isLoading } = useQuery({
    queryKey: ['kpi-scores', relId],
    queryFn: () => api.getPendingApprovals({ relationship_id: relId }),
    enabled: !!relId,
  })

  const periods = useMemo(() => {
    const s = new Set<string>()
    scores.forEach(sc => sc.period && s.add(sc.period))
    return Array.from(s).sort().reverse()
  }, [scores])

  useEffect(() => { if (periods.length && !period) setPeriod(periods[0]) }, [periods, period])
  useEffect(() => { setPeriod(''); setEditing({}) }, [relId])

  // Group by KPI for selected period — internal + external side by side
  const rows = useMemo(() => {
    const filtered = scores.filter(s => s.period === period)
    const map = new Map<string, { int?: PendingApproval; ext?: PendingApproval }>()
    for (const s of filtered) {
      const e = map.get(s.kpi_id) || {}
      if (s.is_internal || s.perspective === 'internal') e.int = s; else e.ext = s
      map.set(s.kpi_id, e)
    }
    return Array.from(map.values()).map(({ int, ext }) => {
      const ref = int || ext!
      return {
        kpi_id: ref.kpi_id,
        name: ref.kpi_name,
        cat: ref.kpi_category || 'other',
        int, ext,
        gap: int && ext ? Math.abs(Number(int.score) - Number(ext.score)) : null,
        pending: int?.approval_status === 'pending_approval' || ext?.approval_status === 'pending_approval',
      }
    }).sort((a, b) => a.name.localeCompare(b.name))
  }, [scores, period])

  const pendingN = rows.filter(r => r.pending).length
  const avgGap = (() => { const g = rows.filter(r => r.gap !== null); return g.length ? g.reduce((a, r) => a + r.gap!, 0) / g.length : 0 })()

  // Mutations
  const saveMut = useMutation({
    mutationFn: ({ kpiId, scoreId, score }: { kpiId: string; scoreId: string; score: number }) =>
      api.updateScore(kpiId, scoreId, { score }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kpi-scores'] }),
  })
  const approveMut = useMutation({
    mutationFn: ({ kpiId, scoreId, comments }: { kpiId: string; scoreId: string; comments?: string }) =>
      api.approveScore(kpiId, scoreId, { comments }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['kpi-scores'] }); setModal(null); setComment('') },
  })
  const rejectMut = useMutation({
    mutationFn: ({ kpiId, scoreId, comments }: { kpiId: string; scoreId: string; comments?: string }) =>
      api.rejectScore(kpiId, scoreId, { comments }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['kpi-scores'] }); setModal(null); setComment('') },
  })
  const delMut = useMutation({
    mutationFn: ({ kpiId, scoreId }: { kpiId: string; scoreId: string }) => api.deleteScore(kpiId, scoreId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kpi-scores'] }),
  })
  const bulkMut = useMutation({
    mutationFn: async () => {
      const p = scores.filter(s => s.approval_status === 'pending_approval' && s.period === period)
      await Promise.all(p.map(s => api.approveScore(s.kpi_id, s.score_id || s.id, {})))
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kpi-scores'] }),
  })

  function sid(s: PendingApproval) { return s.score_id || s.id }

  function doSave(s: PendingApproval) {
    const id = sid(s), v = editing[id]
    if (v === undefined) return
    saveMut.mutate({ kpiId: s.kpi_id, scoreId: id, score: v }, {
      onSuccess: () => setEditing(p => { const n = { ...p }; delete n[id]; return n }),
    })
  }

  const selectedRel = rels.find(r => r.id === relId)

  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex-shrink-0">
          <h1 className="text-lg font-bold text-gray-900">KPI Scores</h1>
        </div>

        {/* Relationship selector */}
        <select value={relId} onChange={e => setRelId(e.target.value)}
          className="input text-sm min-w-[240px]">
          <option value="">Select relationship...</option>
          {rels.map(r => <option key={r.id} value={r.id}>{r.name || 'Unnamed'}</option>)}
        </select>

        {/* Period tabs */}
        {relId && periods.length > 0 && (
          <div className="flex bg-gray-100 rounded-lg p-0.5">
            {periods.map(p => (
              <button key={p} onClick={() => setPeriod(p)}
                className={cn('px-3 py-1 text-xs font-medium rounded-md transition-colors',
                  period === p ? 'bg-white text-violet-700 shadow-sm' : 'text-gray-500 hover:text-gray-700')}>
                {p}
              </button>
            ))}
          </div>
        )}

        {/* Bulk approve */}
        {pendingN > 0 && (
          <button onClick={() => bulkMut.mutate()} disabled={bulkMut.isPending}
            className="btn-primary text-xs ml-auto">
            {bulkMut.isPending ? 'Approving...' : `Approve All (${pendingN})`}
          </button>
        )}
      </div>

      {/* No relationship selected */}
      {!relId && (
        <div className="card card-body py-16 text-center">
          <BuildingOffice2Icon className="h-10 w-10 text-gray-200 mx-auto mb-2" />
          <p className="text-sm text-gray-500">Select a relationship above to view its KPI scorecard</p>
        </div>
      )}

      {/* Loading */}
      {relId && isLoading && (
        <div className="flex justify-center py-12"><LoadingSpinner size="lg" /></div>
      )}

      {/* Scorecard */}
      {relId && !isLoading && (
        <>
          {/* Compact summary */}
          <div className="flex items-center gap-6 text-sm">
            <span className="font-medium text-gray-900">{selectedRel?.name}</span>
            <span className="text-gray-400">|</span>
            <span><span className="font-bold text-violet-600">{rows.length}</span> <span className="text-gray-500">KPIs</span></span>
            <span><span className="font-bold text-amber-600">{pendingN}</span> <span className="text-gray-500">pending</span></span>
            <span>
              <span className={cn('font-bold', avgGap > 1.5 ? 'text-red-600' : avgGap > 0.8 ? 'text-amber-600' : 'text-green-600')}>
                {avgGap.toFixed(1)}
              </span>
              <span className="text-gray-500"> avg gap</span>
            </span>
          </div>

          {/* Table */}
          <div className="card">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase w-1/4">KPI</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase w-16">Cat</th>
                    <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase">Internal</th>
                    <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase">External</th>
                    <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase w-16">Gap</th>
                    <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase w-20">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {rows.map(r => (
                    <tr key={r.kpi_id} className={cn('hover:bg-gray-50', r.pending && 'bg-amber-50/40')}>
                      <td className="px-3 py-2">
                        <span className="font-medium text-gray-900">{r.name}</span>
                      </td>
                      <td className="px-3 py-2">
                        <span className="text-[10px] text-gray-400 uppercase">{CAT_LABEL[r.cat] || r.cat}</span>
                      </td>
                      <td className="px-3 py-2 text-center">
                        {r.int ? (
                          editing[sid(r.int)] !== undefined ? (
                            <span className="inline-flex items-center gap-1">
                              <input type="number" min={1} max={10} step={0.1} value={editing[sid(r.int)]}
                                onChange={e => { const id = sid(r.int!); setEditing(p => ({ ...p, [id]: parseFloat(e.target.value) })) }}
                                onKeyDown={e => { if (e.key === 'Enter') doSave(r.int!); if (e.key === 'Escape') { const id = sid(r.int!); setEditing(p => { const n = { ...p }; delete n[id]; return n }) } }}
                                className="w-14 text-center border border-violet-300 rounded text-sm py-0.5" autoFocus />
                              <button onClick={() => doSave(r.int!)} className="text-violet-600"><CheckCircleIcon className="h-4 w-4" /></button>
                            </span>
                          ) : (
                            <button onClick={() => { const id = sid(r.int!); setEditing(p => ({ ...p, [id]: Number(r.int!.score) })) }}
                              className={cn('font-bold cursor-pointer', r.int.approval_status === 'pending_approval' ? 'text-amber-600' : 'text-gray-900 hover:text-violet-600')}>
                              {Number(r.int.score).toFixed(1)}
                            </button>
                          )
                        ) : <span className="text-gray-300">--</span>}
                      </td>
                      <td className="px-3 py-2 text-center">
                        {r.ext ? (
                          editing[sid(r.ext)] !== undefined ? (
                            <span className="inline-flex items-center gap-1">
                              <input type="number" min={1} max={10} step={0.1} value={editing[sid(r.ext)]}
                                onChange={e => { const id = sid(r.ext!); setEditing(p => ({ ...p, [id]: parseFloat(e.target.value) })) }}
                                onKeyDown={e => { if (e.key === 'Enter') doSave(r.ext!); if (e.key === 'Escape') { const id = sid(r.ext!); setEditing(p => { const n = { ...p }; delete n[id]; return n }) } }}
                                className="w-14 text-center border border-violet-300 rounded text-sm py-0.5" autoFocus />
                              <button onClick={() => doSave(r.ext!)} className="text-violet-600"><CheckCircleIcon className="h-4 w-4" /></button>
                            </span>
                          ) : (
                            <button onClick={() => { const id = sid(r.ext!); setEditing(p => ({ ...p, [id]: Number(r.ext!.score) })) }}
                              className={cn('font-bold cursor-pointer', r.ext.approval_status === 'pending_approval' ? 'text-amber-600' : 'text-gray-900 hover:text-violet-600')}>
                              {Number(r.ext.score).toFixed(1)}
                            </button>
                          )
                        ) : <span className="text-gray-300">--</span>}
                      </td>
                      <td className="px-3 py-2 text-center">
                        {r.gap !== null ? (
                          <span className={cn('text-sm font-bold',
                            r.gap < 0.8 ? 'text-green-600' : r.gap <= 1.5 ? 'text-amber-600' : 'text-red-600')}>
                            {r.gap.toFixed(1)}
                          </span>
                        ) : <span className="text-gray-300">--</span>}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex items-center justify-center gap-0.5">
                          {r.pending && (
                            <>
                              <button onClick={() => { const s = r.int?.approval_status === 'pending_approval' ? r.int : r.ext!; setModal({ type: 'approve', kpiId: r.kpi_id, scoreId: sid(s), name: r.name }) }}
                                className="p-0.5 text-green-500 hover:bg-green-50 rounded" title="Approve">
                                <CheckCircleIcon className="h-4 w-4" />
                              </button>
                              <button onClick={() => { const s = r.int?.approval_status === 'pending_approval' ? r.int : r.ext!; setModal({ type: 'reject', kpiId: r.kpi_id, scoreId: sid(s), name: r.name }) }}
                                className="p-0.5 text-red-400 hover:bg-red-50 rounded" title="Reject">
                                <XCircleIcon className="h-4 w-4" />
                              </button>
                            </>
                          )}
                          <button onClick={() => { const s = r.int || r.ext!; if (confirm('Delete?')) delMut.mutate({ kpiId: r.kpi_id, scoreId: sid(s) }) }}
                            className="p-0.5 text-gray-300 hover:text-red-500 rounded" title="Delete">
                            <TrashIcon className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {rows.length === 0 && (
                    <tr><td colSpan={6} className="px-3 py-8 text-center text-sm text-gray-400">No scores for this period</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* Modal */}
      {modal && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">{modal.type === 'approve' ? 'Approve' : 'Reject'} Score</h2>
              <button onClick={() => { setModal(null); setComment('') }} className="text-gray-400 hover:text-gray-600">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              {modal.type === 'approve' ? 'Approve' : 'Reject'} <span className="font-medium">{modal.name}</span>?
            </p>
            <textarea value={comment} onChange={e => setComment(e.target.value)} rows={2}
              placeholder={modal.type === 'reject' ? 'Reason...' : 'Comments (optional)'}
              className="w-full border rounded-lg px-3 py-2 text-sm mb-4 focus:ring-2 focus:ring-violet-500" />
            <div className="flex justify-end gap-3">
              <button onClick={() => { setModal(null); setComment('') }} className="btn-secondary">Cancel</button>
              <button onClick={() => {
                  const p = { kpiId: modal.kpiId, scoreId: modal.scoreId, comments: comment || undefined }
                  modal.type === 'approve' ? approveMut.mutate(p) : rejectMut.mutate(p)
                }}
                disabled={approveMut.isPending || rejectMut.isPending}
                className={cn('px-4 py-2 rounded-lg text-sm font-medium text-white',
                  modal.type === 'approve' ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700')}>
                {approveMut.isPending || rejectMut.isPending ? '...' : modal.type === 'approve' ? 'Approve' : 'Reject'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
