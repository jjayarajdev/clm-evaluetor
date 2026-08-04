/* KPI approvals — Direction B redesign.
   Relationship picker → period chips → summary Stats → approval-queue Table
   with internal/external inline score editing, gap coloring, status Pills and
   approve/reject actions (comment captured in a Drawer). Data fetching,
   grouping-by-KPI logic and every mutation (save/approve/reject/delete/bulk)
   are unchanged from the pre-redesign page. */
import { useState, useMemo, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  BuildingOffice2Icon,
  ChartBarIcon,
  CheckCircleIcon,
  CheckIcon,
  ClockIcon,
  ScaleIcon,
  TrashIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import {
  Button,
  Chip,
  ConfirmDialog,
  Drawer,
  EmptyState,
  IconButton,
  Pill,
  Select,
  Stat,
  Table,
  Tag,
  useToast,
} from '@/components/ui'
import type { TableColumn } from '@/components/ui'
import type { PendingApproval } from '@/types/fitgap'

const CAT_LABEL: Record<string, string> = {
  service_delivery: 'Delivery', quality: 'Quality', cost_efficiency: 'Cost',
  communication: 'Comms', innovation: 'Innovation', compliance: 'Compliance',
  satisfaction: 'Satisfaction', risk: 'Risk', other: 'Other',
}

interface KpiRow {
  kpi_id: string
  name: string
  cat: string
  int?: PendingApproval
  ext?: PendingApproval
  gap: number | null
  pending: boolean
}

function gapTone(gap: number): string {
  return gap < 0.8 ? 'var(--ok)' : gap <= 1.5 ? 'var(--wa)' : 'var(--da)'
}

export default function KPIApprovalsPage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const qc = useQueryClient()
  const [relId, setRelId] = useState('')
  const [period, setPeriod] = useState('')
  const [editing, setEditing] = useState<Record<string, number>>({})
  const [modal, setModal] = useState<{ type: 'approve' | 'reject'; kpiId: string; scoreId: string; name: string } | null>(null)
  const [comment, setComment] = useState('')
  const [del, setDel] = useState<{ kpiId: string; scoreId: string; name: string } | null>(null)

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
  const rows = useMemo<KpiRow[]>(() => {
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

  // Mutations — unchanged behavior
  const saveMut = useMutation({
    mutationFn: ({ kpiId, scoreId, score }: { kpiId: string; scoreId: string; score: number }) =>
      api.updateScore(kpiId, scoreId, { score }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kpi-scores'] }),
  })
  const approveMut = useMutation({
    mutationFn: ({ kpiId, scoreId, comments }: { kpiId: string; scoreId: string; comments?: string }) =>
      api.approveScore(kpiId, scoreId, { comments }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['kpi-scores'] }); setModal(null); setComment('')
      toast({ text: t('governance.scoreApproved', { defaultValue: 'Score approved' }) })
    },
  })
  const rejectMut = useMutation({
    mutationFn: ({ kpiId, scoreId, comments }: { kpiId: string; scoreId: string; comments?: string }) =>
      api.rejectScore(kpiId, scoreId, { comments }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['kpi-scores'] }); setModal(null); setComment('')
      toast({ text: t('governance.scoreRejected', { defaultValue: 'Score rejected' }) })
    },
  })
  const delMut = useMutation({
    mutationFn: ({ kpiId, scoreId }: { kpiId: string; scoreId: string }) => api.deleteScore(kpiId, scoreId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['kpi-scores'] })
      toast({ text: t('governance.scoreDeleted', { defaultValue: 'Score deleted' }) })
    },
  })
  const bulkMut = useMutation({
    mutationFn: async () => {
      const p = scores.filter(s => s.approval_status === 'pending_approval' && s.period === period)
      await Promise.all(p.map(s => api.approveScore(s.kpi_id, s.score_id || s.id, {})))
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['kpi-scores'] })
      toast({ text: t('governance.allApproved', { defaultValue: 'All pending scores approved' }) })
    },
  })

  function sid(s: PendingApproval) { return s.score_id || s.id }

  function doSave(s: PendingApproval) {
    const id = sid(s), v = editing[id]
    if (v === undefined) return
    saveMut.mutate({ kpiId: s.kpi_id, scoreId: id, score: v }, {
      onSuccess: () => setEditing(p => { const n = { ...p }; delete n[id]; return n }),
    })
  }

  /** Inline-editable score: click the figure to edit, Enter saves, Escape cancels.
      Called as a plain function (not a JSX component) so the input is never
      remounted mid-edit by a changing component identity. */
  function renderScore(s?: PendingApproval) {
    if (!s) return <span className="faint">--</span>
    const id = sid(s)
    if (editing[id] !== undefined) {
      return (
        <span className="row" style={{ gap: 4, display: 'inline-flex' }}>
          <input
            type="number" min={1} max={10} step={0.1} value={editing[id]} autoFocus
            onChange={e => setEditing(p => ({ ...p, [id]: parseFloat(e.target.value) }))}
            onKeyDown={e => {
              if (e.key === 'Enter') doSave(s)
              if (e.key === 'Escape') setEditing(p => { const n = { ...p }; delete n[id]; return n })
            }}
            className="num"
            style={{
              width: 58, textAlign: 'center', height: 26, fontSize: 'var(--fs-sm)',
              background: 'var(--s)', color: 'var(--t)',
              border: '1px solid var(--p-b)', borderRadius: 'var(--r-sm)', outline: 'none',
            }}
          />
          <IconButton icon={CheckIcon} label={t('common.save')} size="sm" style={{ color: 'var(--ok)' }} onClick={() => doSave(s)} />
        </span>
      )
    }
    const pending = s.approval_status === 'pending_approval'
    return (
      <button
        type="button"
        onClick={() => setEditing(p => ({ ...p, [id]: Number(s.score) }))}
        className="num"
        style={{
          background: 'none', border: 0, padding: 0, cursor: 'pointer',
          fontWeight: 600, fontSize: 'var(--fs-md)',
          color: pending ? 'var(--wa)' : 'var(--t)',
        }}
        title={t('governance.clickToEdit', { defaultValue: 'Click to edit' })}
      >
        {Number(s.score).toFixed(1)}
      </button>
    )
  }

  function rowStatus(r: KpiRow): { label: string; tone: 'ok' | 'wa' | 'da' | 'n' } {
    if (r.pending) return { label: t('status.pending'), tone: 'wa' }
    const statuses = [r.int?.approval_status, r.ext?.approval_status].filter(Boolean)
    if (statuses.includes('rejected')) return { label: t('governance.rejected', { defaultValue: 'Rejected' }), tone: 'da' }
    if (statuses.includes('approved')) return { label: t('governance.approved', { defaultValue: 'Approved' }), tone: 'ok' }
    return { label: t('status.draft'), tone: 'n' }
  }

  const columns: TableColumn<KpiRow>[] = [
    {
      key: 'name',
      header: t('governance.kpi'),
      sortable: true,
      render: r => <span style={{ fontWeight: 500 }}>{r.name}</span>,
    },
    {
      key: 'cat',
      header: t('governance.categoryShort'),
      width: 110,
      render: r => <Tag>{t(`governance.kpiCategoriesShort.${r.cat}`, { defaultValue: CAT_LABEL[r.cat] || r.cat })}</Tag>,
    },
    {
      key: 'int',
      header: t('governance.internal'),
      width: 110,
      align: 'right',
      sortable: true,
      sortValue: r => (r.int ? Number(r.int.score) : null),
      render: r => renderScore(r.int),
    },
    {
      key: 'ext',
      header: t('governance.external'),
      width: 110,
      align: 'right',
      sortable: true,
      sortValue: r => (r.ext ? Number(r.ext.score) : null),
      render: r => renderScore(r.ext),
    },
    {
      key: 'gap',
      header: t('governance.gap'),
      width: 80,
      align: 'right',
      sortable: true,
      sortValue: r => r.gap,
      render: r =>
        r.gap !== null ? (
          <span className="num" style={{ fontWeight: 600, color: gapTone(r.gap) }}>{r.gap.toFixed(1)}</span>
        ) : (
          <span className="faint">--</span>
        ),
    },
    {
      key: 'status',
      header: t('common.status'),
      width: 110,
      sortable: true,
      sortValue: r => (r.pending ? 0 : 1),
      render: r => {
        const s = rowStatus(r)
        return <Pill tone={s.tone}>{s.label}</Pill>
      },
    },
    {
      key: 'actions',
      header: t('common.actions'),
      width: 110,
      align: 'right',
      render: r => (
        <span className="row" style={{ gap: 2, display: 'inline-flex' }}>
          {r.pending && (
            <>
              <IconButton
                icon={CheckCircleIcon} label={t('governance.approve')} size="sm" style={{ color: 'var(--ok)' }}
                onClick={() => {
                  const s = r.int?.approval_status === 'pending_approval' ? r.int : r.ext!
                  setModal({ type: 'approve', kpiId: r.kpi_id, scoreId: sid(s), name: r.name })
                }}
              />
              <IconButton
                icon={XCircleIcon} label={t('governance.reject')} size="sm" style={{ color: 'var(--da)' }}
                onClick={() => {
                  const s = r.int?.approval_status === 'pending_approval' ? r.int : r.ext!
                  setModal({ type: 'reject', kpiId: r.kpi_id, scoreId: sid(s), name: r.name })
                }}
              />
            </>
          )}
          <IconButton
            icon={TrashIcon} label={t('common.delete')} size="sm"
            onClick={() => {
              const s = r.int || r.ext!
              setDel({ kpiId: r.kpi_id, scoreId: sid(s), name: r.name })
            }}
          />
        </span>
      ),
    },
  ]

  const selectedRel = rels.find(r => r.id === relId)

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header: title + relationship picker + bulk approve */}
      <div className="row" style={{ alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>{t('governance.kpiScores')}</h1>
          {selectedRel?.name && (
            <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>{selectedRel.name}</p>
          )}
        </div>
        <div className="row" style={{ gap: 8 }}>
          <Select
            aria-label={t('governance.selectRelationship')}
            value={relId}
            onChange={e => setRelId(e.target.value)}
            containerStyle={{ minWidth: 260 }}
            options={[
              { value: '', label: t('governance.selectRelationship') },
              ...rels.map(r => ({
                value: r.id,
                label: r.org_a?.name && r.org_b?.name ? `${r.org_a.name} ↔ ${r.org_b.name}` : r.name || t('governance.unnamed'),
              })),
            ]}
          />
          {pendingN > 0 && (
            <Button variant="primary" icon={CheckIcon} onClick={() => bulkMut.mutate()} disabled={bulkMut.isPending}>
              {bulkMut.isPending ? t('governance.approving') : t('governance.approveAllCount', { count: pendingN })}
            </Button>
          )}
        </div>
      </div>

      {/* No relationship selected */}
      {!relId && (
        <div className="card">
          <EmptyState
            icon={BuildingOffice2Icon}
            title={t('governance.kpiScores')}
            body={t('governance.selectRelationshipPrompt')}
          />
        </div>
      )}

      {/* Loading */}
      {relId && isLoading && (
        <div className="row" style={{ justifyContent: 'center', padding: '48px 0' }}>
          <LoadingSpinner size="lg" />
        </div>
      )}

      {/* Scorecard */}
      {relId && !isLoading && (
        <>
          {/* Period chips */}
          {periods.length > 0 && (
            <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
              <span className="sec-t">{t('governance.period')}</span>
              {periods.map(p => (
                <Chip key={p} on={period === p} onClick={() => setPeriod(p)}>{p}</Chip>
              ))}
            </div>
          )}

          {/* Summary stats */}
          <div className="grid gap-3 grid-cols-1 sm:grid-cols-3">
            <Stat icon={ChartBarIcon} label={t('governance.kpis')} value={rows.length} />
            <Stat
              icon={ClockIcon}
              label={t('status.pending')}
              value={pendingN}
              sub={pendingN > 0
                ? t('governance.awaitingApproval', { defaultValue: 'submitted scores awaiting approval' })
                : t('governance.queueClear', { defaultValue: 'nothing awaiting approval' })}
              subTone={pendingN > 0 ? 'var(--wa)' : undefined}
            />
            <Stat
              icon={ScaleIcon}
              label={t('governance.avgGap')}
              value={<span style={{ color: gapTone(avgGap) }}>{avgGap.toFixed(1)}</span>}
              sub={t('governance.gapHint', { defaultValue: 'internal vs external perception' })}
            />
          </div>

          {/* Approval queue table */}
          <Table
            columns={columns}
            rows={rows}
            rowKey={r => r.kpi_id}
            minWidth={720}
            empty={<EmptyState icon={ChartBarIcon} title={t('governance.noScoresForPeriod')} />}
          />
        </>
      )}

      {/* Approve / reject drawer with optional comment */}
      <Drawer
        open={!!modal}
        title={modal?.type === 'approve' ? t('governance.approveScore') : t('governance.rejectScore')}
        sub={modal?.name}
        onClose={() => { setModal(null); setComment('') }}
        footer={modal ? (
          <>
            <Button
              variant={modal.type === 'approve' ? 'primary' : 'danger'}
              className="grow"
              icon={modal.type === 'approve' ? CheckCircleIcon : XCircleIcon}
              disabled={approveMut.isPending || rejectMut.isPending}
              onClick={() => {
                const p = { kpiId: modal.kpiId, scoreId: modal.scoreId, comments: comment || undefined }
                if (modal.type === 'approve') approveMut.mutate(p); else rejectMut.mutate(p)
              }}
            >
              {approveMut.isPending || rejectMut.isPending
                ? t('governance.approving')
                : modal.type === 'approve' ? t('governance.approve') : t('governance.reject')}
            </Button>
            <Button variant="ghost" className="grow" onClick={() => { setModal(null); setComment('') }}>
              {t('common.cancel')}
            </Button>
          </>
        ) : undefined}
      >
        {modal && (
          <div className="col" style={{ gap: 14 }}>
            <p className="muted" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.55 }}>
              {modal.type === 'approve'
                ? t('governance.approveConfirm', { name: modal.name })
                : t('governance.rejectConfirm', { name: modal.name })}
            </p>
            <div>
              <label className="lbl">
                {modal.type === 'reject' ? t('governance.reasonPlaceholder') : t('governance.commentsOptional')}
              </label>
              <div className="inp" style={{ height: 'auto', padding: '8px 10px' }}>
                <textarea
                  rows={3}
                  autoFocus
                  style={{ resize: 'vertical' }}
                  value={comment}
                  onChange={e => setComment(e.target.value)}
                />
              </div>
            </div>
            {modal.type === 'approve' && (
              <p className="faint" style={{ fontSize: 'var(--fs-sm)', lineHeight: 1.5 }}>
                {t('governance.approveHint', { defaultValue: 'Approved scores are folded into the relationship health score.' })}
              </p>
            )}
          </div>
        )}
      </Drawer>

      {/* Delete confirmation */}
      <ConfirmDialog
        open={!!del}
        title={del ? t('governance.deleteScoreTitle', { defaultValue: 'Delete score for {{name}}?', name: del.name }) : ''}
        body={t('governance.confirmDelete')}
        affected={[t('governance.deleteScoreAffected', { defaultValue: 'The recorded score for this period' })]}
        safe={[t('governance.deleteScoreSafe', { defaultValue: 'The KPI definition and every other period' })]}
        confirmLabel={t('common.delete')}
        cancelLabel={t('common.cancel')}
        onCancel={() => setDel(null)}
        onConfirm={() => {
          if (del) delMut.mutate({ kpiId: del.kpiId, scoreId: del.scoreId })
          setDel(null)
        }}
      />
    </div>
  )
}
