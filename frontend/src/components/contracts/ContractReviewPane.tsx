import { useState, useRef, useCallback, useEffect } from 'react'
import { useQuery, useQueries, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  PencilIcon,
  CheckIcon,
  XMarkIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  DocumentMagnifyingGlassIcon,
  ChatBubbleLeftIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import ContractPdfViewer from './ContractPdfViewer'
import { cn, formatDate } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'
import type { Contract, ClauseDetail, ObligationItem, ContractCommentItem } from '@/types'
import type { HighlightRect } from '@/lib/api/contracts'

interface ContractReviewPaneProps {
  contractId: string
  contract: Contract
}

// ── Inline Edit Field ───────────────────────────────────────────────

function InlineEdit({
  label,
  value,
  type = 'text',
  onSave,
  options,
}: {
  label: string
  value: string | number | boolean | null | undefined
  type?: 'text' | 'date' | 'number' | 'select' | 'checkbox'
  onSave: (val: string | number | boolean | null) => void
  options?: { value: string; label: string }[]
}) {
  const [editing, setEditing] = useState(false)
  const [editValue, setEditValue] = useState(String(value ?? ''))

  const save = () => {
    let parsed: string | number | boolean | null = editValue || null
    if (type === 'number' && editValue) parsed = parseFloat(editValue)
    if (type === 'checkbox') parsed = editValue === 'true'
    onSave(parsed)
    setEditing(false)
  }

  const cancel = () => {
    setEditValue(String(value ?? ''))
    setEditing(false)
  }

  const displayValue = type === 'date' && value
    ? formatDate(String(value))
    : type === 'checkbox'
    ? value ? 'Yes' : 'No'
    : type === 'number' && value
    ? String(value)
    : String(value || '-')

  if (!editing) {
    return (
      <div className="group flex items-start gap-1">
        <div className="min-w-0 flex-1">
          <p className="text-xs text-gray-500">{label}</p>
          <p className="text-sm text-gray-900 truncate">{displayValue}</p>
        </div>
        <button
          onClick={() => { setEditValue(String(value ?? '')); setEditing(true) }}
          className="p-0.5 rounded opacity-0 group-hover:opacity-100 hover:bg-gray-100 transition-opacity flex-shrink-0 mt-3"
        >
          <PencilIcon className="h-3.5 w-3.5 text-gray-400" />
        </button>
      </div>
    )
  }

  return (
    <div>
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <div className="flex items-center gap-1">
        {type === 'select' && options ? (
          <select
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            className="input text-sm py-1 flex-1"
            autoFocus
          >
            <option value="">-</option>
            {options.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        ) : type === 'checkbox' ? (
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={editValue === 'true'}
              onChange={(e) => setEditValue(String(e.target.checked))}
              className="rounded"
            />
            {editValue === 'true' ? 'Yes' : 'No'}
          </label>
        ) : (
          <input
            type={type === 'date' ? 'date' : type === 'number' ? 'number' : 'text'}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            className="input text-sm py-1 flex-1"
            autoFocus
            onKeyDown={(e) => { if (e.key === 'Enter') save(); if (e.key === 'Escape') cancel() }}
          />
        )}
        <button onClick={save} className="p-1 rounded hover:bg-green-100 text-green-600">
          <CheckIcon className="h-4 w-4" />
        </button>
        <button onClick={cancel} className="p-1 rounded hover:bg-gray-100 text-gray-400">
          <XMarkIcon className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

// ── Collapsible Section ─────────────────────────────────────────────

function Section({
  title,
  count,
  defaultOpen = false,
  children,
}: {
  title: string
  count?: number
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="border border-gray-200 rounded-lg bg-white">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50"
      >
        <div className="flex items-center gap-2">
          {open ? (
            <ChevronDownIcon className="h-4 w-4 text-gray-400" />
          ) : (
            <ChevronRightIcon className="h-4 w-4 text-gray-400" />
          )}
          <span className="text-sm font-medium text-gray-900">{title}</span>
        </div>
        {count !== undefined && (
          <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">{count}</span>
        )}
      </button>
      {open && <div className="border-t border-gray-200">{children}</div>}
    </div>
  )
}

// ── Risk Badge ──────────────────────────────────────────────────────

const RISK_COLORS: Record<string, string> = {
  low: 'bg-green-100 text-green-700',
  medium: 'bg-yellow-100 text-yellow-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700',
}

function RiskBadge({ level }: { level: string | null }) {
  if (!level) return null
  return (
    <span className={cn('px-1.5 py-0.5 rounded text-xs font-medium capitalize', RISK_COLORS[level] || 'bg-gray-100 text-gray-700')}>
      {level}
    </span>
  )
}

// ── Clause Type Labels ──────────────────────────────────────────────

const CLAUSE_TYPE_LABELS: Record<string, string> = {
  indemnification: 'Indemnification',
  limitation_of_liability: 'Limitation of Liability',
  termination: 'Termination',
  confidentiality: 'Confidentiality',
  intellectual_property: 'Intellectual Property',
  payment_terms: 'Payment Terms',
  warranty: 'Warranty',
  force_majeure: 'Force Majeure',
  non_compete: 'Non-Compete',
  non_solicitation: 'Non-Solicitation',
  data_protection: 'Data Protection',
  dispute_resolution: 'Dispute Resolution',
  assignment: 'Assignment',
  notice: 'Notice',
  governing_law: 'Governing Law',
  sla: 'SLA',
  auto_renewal: 'Auto-Renewal',
  service_description: 'Service Description',
  service_level: 'Service Level',
  deliverable: 'Deliverable',
  governance: 'Governance',
  transition: 'Transition',
  change_management: 'Change Management',
  support: 'Support',
  security: 'Security',
  personnel: 'Personnel',
  pricing: 'Pricing',
  scope: 'Scope',
  acceptance: 'Acceptance',
  other: 'Other',
}

const CONTRACT_TYPE_OPTIONS = [
  { value: 'nda', label: 'NDA' },
  { value: 'msa', label: 'MSA' },
  { value: 'sow', label: 'SOW' },
  { value: 'amendment', label: 'Amendment' },
  { value: 'vendor_agreement', label: 'Vendor Agreement' },
  { value: 'employment_contract', label: 'Employment Contract' },
]

// ═══════════════════════════════════════════════════════════════════
// Main Component
// ═══════════════════════════════════════════════════════════════════

export default function ContractReviewPane({ contractId, contract }: ContractReviewPaneProps) {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const canEdit = user?.role === 'admin' || user?.role === 'legal' || user?.role === 'super_admin'
  const [highlightPage, setHighlightPage] = useState<number | null>(null)
  const [highlightText, setHighlightText] = useState<string | null>(null)
  const [activeRects, setActiveRects] = useState<HighlightRect[] | null>(null)
  const [splitPercent, setSplitPercent] = useState(45)
  const containerRef = useRef<HTMLDivElement>(null)
  const dragging = useRef(false)

  // Fetch intelligence data (clauses + obligations)
  const { data: intelligence, isLoading: intLoading } = useQuery({
    queryKey: ['contract-intelligence', contractId],
    queryFn: () => api.getContractIntelligence(contractId),
  })

  // Fetch SLAs
  const { data: slas, isLoading: slaLoading } = useQuery({
    queryKey: ['contract-slas', contractId],
    queryFn: () => api.getContractSLAs(contractId),
  })

  // Fetch pre-computed highlight coordinates
  const { data: highlights } = useQuery({
    queryKey: ['contract-highlights', contractId],
    queryFn: () => api.getContractHighlights(contractId),
  })

  // Fetch comments
  const { data: commentsData } = useQuery({
    queryKey: ['contract-comments', contractId],
    queryFn: () => api.getContractComments(contractId),
  })

  const comments = commentsData?.items || []

  const getCommentsFor = (ref: string) =>
    comments.filter((c) => c.section_reference === ref)

  // Add comment mutation
  const addCommentMut = useMutation({
    mutationFn: (data: { content: string; section_reference?: string; clause_id?: string }) =>
      api.addContractComment(contractId, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['contract-comments', contractId] }),
  })

  // ── Metadata update mutation ──
  const updateMeta = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api.updateContract(contractId, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['contract', contractId] }),
  })

  // ── Clause update mutation ──
  const updateClauseMut = useMutation({
    mutationFn: ({ clauseId, data }: { clauseId: string; data: Record<string, unknown> }) =>
      api.updateClause(contractId, clauseId, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['contract-intelligence', contractId] }),
  })

  // ── Obligation update mutation ──
  const updateObligationMut = useMutation({
    mutationFn: ({ obligationId, data }: { obligationId: string; data: Record<string, unknown> }) =>
      api.updateObligation(obligationId, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['contract-intelligence', contractId] }),
  })

  // ── Drag to resize ──
  const onMouseDown = useCallback(() => { dragging.current = true }, [])

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const pct = ((e.clientX - rect.left) / rect.width) * 100
      setSplitPercent(Math.max(25, Math.min(70, pct)))
    }
    const onMouseUp = () => { dragging.current = false }
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
  }, [])

  // Get clause types from intelligence, then fetch details per type
  const clauseTypes = intelligence?.clause_breakdown?.map((b) => b.clause_type) || []

  // Fetch all clauses for each type
  const clauseQueries = useQueries({
    queries: clauseTypes.map((ct) => ({
      queryKey: ['clauses-by-type', ct, contractId],
      queryFn: () => api.getClausesByType(ct, contractId),
      enabled: !!ct,
    })),
  })

  // Flatten all clauses
  const allClauses: (ClauseDetail & { _type: string })[] = []
  for (const q of clauseQueries) {
    if (q.data?.clauses) {
      for (const c of q.data.clauses) {
        allClauses.push({ ...c, _type: q.data.clause_type })
      }
    }
  }
  const clausesLoading = clauseQueries.some((q) => q.isLoading)

  // Flatten all obligations from intelligence matrix
  const allObligations: ObligationItem[] = []
  if (intelligence?.obligations_matrix) {
    allObligations.push(...(intelligence.obligations_matrix.provider_obligations || []))
    allObligations.push(...(intelligence.obligations_matrix.client_obligations || []))
  }

  return (
    <div ref={containerRef} className="flex h-full select-none" style={{ userSelect: dragging.current ? 'none' : 'auto' }}>
      {/* ── Left Pane: Extracted Data ── */}
      <div
        className="flex-shrink-0 overflow-y-auto border-r border-gray-200 bg-gray-50 p-4 space-y-3"
        style={{ width: `${splitPercent}%` }}
      >
        {/* Risk & Extraction Summary */}
        {intelligence && (
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <div className="flex items-center gap-4">
              {/* Risk Score Circle */}
              <div className={cn(
                'h-14 w-14 rounded-full flex items-center justify-center text-lg font-bold flex-shrink-0',
                intelligence.risk_summary?.risk_level === 'critical' ? 'bg-red-100 text-red-700' :
                intelligence.risk_summary?.risk_level === 'high' ? 'bg-orange-100 text-orange-700' :
                intelligence.risk_summary?.risk_level === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                intelligence.risk_summary?.risk_level === 'low' ? 'bg-green-100 text-green-700' :
                'bg-gray-100 text-gray-500'
              )}>
                {intelligence.risk_summary?.risk_score ?? '—'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-gray-900 capitalize">
                  {intelligence.risk_summary?.risk_level || 'Unknown'} Risk
                </p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {allClauses.length} clauses · {allObligations.length} obligations · {slas?.length || 0} SLAs
                </p>
                {intelligence.extraction_status && (
                  <p className="text-xs text-gray-400 mt-0.5">
                    {intelligence.extraction_status.classified_clauses}/{intelligence.extraction_status.total_clauses} classified
                  </p>
                )}
              </div>
            </div>

            {/* High-risk clauses */}
            {intelligence.risk_summary?.high_risk_clauses?.length > 0 && (
              <div className="mt-3 space-y-1.5">
                <p className="text-xs font-medium text-red-600">
                  {intelligence.risk_summary.high_risk_clauses.length} High-Risk Clause{intelligence.risk_summary.high_risk_clauses.length > 1 ? 's' : ''}
                </p>
                {intelligence.risk_summary.high_risk_clauses.map((c) => (
                  <div key={c.id} className="text-xs bg-red-50 border border-red-100 rounded p-2">
                    <span className="font-medium text-red-700 capitalize">{c.clause_type.replace(/_/g, ' ')}</span>
                    <span className="text-gray-600 ml-1">— {c.excerpt}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Metadata Section */}
        <Section title="Contract Details" defaultOpen={true}>
          <div className="px-4 py-3 grid grid-cols-2 gap-3">
            <InlineEdit
              label="Counterparty"
              value={contract.counterparty}
              onSave={(v) => canEdit && updateMeta.mutate({ counterparty: v })}
            />
            <InlineEdit
              label="Contract Type"
              value={contract.contract_type}
              type="select"
              options={CONTRACT_TYPE_OPTIONS}
              onSave={(v) => canEdit && updateMeta.mutate({ contract_type: v })}
            />
            <InlineEdit
              label="Effective Date"
              value={contract.effective_date}
              type="date"
              onSave={(v) => canEdit && updateMeta.mutate({ effective_date: v })}
            />
            <InlineEdit
              label="Expiration Date"
              value={contract.expiration_date}
              type="date"
              onSave={(v) => canEdit && updateMeta.mutate({ expiration_date: v })}
            />
            <InlineEdit
              label="Contract Value"
              value={contract.contract_value}
              type="number"
              onSave={(v) => canEdit && updateMeta.mutate({ contract_value: v })}
            />
            <InlineEdit
              label="Currency"
              value={contract.currency}
              onSave={(v) => canEdit && updateMeta.mutate({ currency: v })}
            />
            <InlineEdit
              label="Jurisdiction"
              value={contract.jurisdiction}
              onSave={(v) => canEdit && updateMeta.mutate({ jurisdiction: v })}
            />
            <InlineEdit
              label="Auto-Renewal"
              value={contract.auto_renewal}
              type="checkbox"
              onSave={(v) => canEdit && updateMeta.mutate({ auto_renewal: v })}
            />
            <InlineEdit
              label="Notice Period (days)"
              value={contract.notice_period_days}
              type="number"
              onSave={(v) => canEdit && updateMeta.mutate({ notice_period_days: v })}
            />
            <InlineEdit
              label="Renewal Term (months)"
              value={contract.renewal_term_months}
              type="number"
              onSave={(v) => canEdit && updateMeta.mutate({ renewal_term_months: v })}
            />
          </div>
        </Section>

        {/* Clauses Section */}
        <Section title="Clauses" count={allClauses.length} defaultOpen={true}>
          {(intLoading || clausesLoading) ? (
            <div className="flex justify-center py-4"><LoadingSpinner size="sm" /></div>
          ) : allClauses.length === 0 ? (
            <p className="text-sm text-gray-500 px-4 py-3">No clauses extracted</p>
          ) : (
            <div className="divide-y divide-gray-100 max-h-[400px] overflow-y-auto">
              {allClauses.map((clause) => (
                <ClauseRow
                  key={clause.id}
                  clause={clause}
                  canEdit={canEdit}
                  comments={getCommentsFor(`clause:${clause.id}`)}
                  onAddComment={(content) => addCommentMut.mutate({ content, section_reference: `clause:${clause.id}`, clause_id: clause.id })}
                  onViewSource={() => {
                    const clauseHL = highlights?.highlights?.[clause.id]
                    if (clauseHL?.rects?.length) {
                      setActiveRects(clauseHL.rects)
                      setHighlightPage(clauseHL.rects[0].page)
                      setHighlightText(null)
                    } else {
                      setActiveRects(null)
                      setHighlightPage(clause.page_number || null)
                      setHighlightText(clause.text)
                    }
                  }}
                  onUpdate={(data) => updateClauseMut.mutate({ clauseId: clause.id, data })}
                />
              ))}
            </div>
          )}
        </Section>

        {/* Obligations Section */}
        <Section title="Obligations" count={allObligations.length}>
          {intLoading ? (
            <div className="flex justify-center py-4"><LoadingSpinner size="sm" /></div>
          ) : allObligations.length === 0 ? (
            <p className="text-sm text-gray-500 px-4 py-3">No obligations extracted</p>
          ) : (
            <div className="divide-y divide-gray-100 max-h-[400px] overflow-y-auto">
              {allObligations.map((obl) => (
                <ObligationRow
                  key={obl.id}
                  obligation={obl}
                  canEdit={canEdit}
                  comments={getCommentsFor(`obligation:${obl.id}`)}
                  onAddComment={(content) => addCommentMut.mutate({ content, section_reference: `obligation:${obl.id}` })}
                  onViewSource={() => {
                    const oblHL = highlights?.highlights?.[obl.id]
                    if (oblHL?.rects?.length) {
                      setActiveRects(oblHL.rects)
                      setHighlightPage(oblHL.rects[0].page)
                      setHighlightText(null)
                    } else {
                      setActiveRects(null)
                      setHighlightText(obl.source_text || obl.description)
                      setHighlightPage(null)
                    }
                  }}
                  onUpdate={(data) => updateObligationMut.mutate({ obligationId: obl.id, data })}
                />
              ))}
            </div>
          )}
        </Section>

        {/* SLAs Section */}
        <Section title="SLAs" count={slas?.length || 0}>
          {slaLoading ? (
            <div className="flex justify-center py-4"><LoadingSpinner size="sm" /></div>
          ) : !slas || slas.length === 0 ? (
            <p className="text-sm text-gray-500 px-4 py-3">No SLAs extracted</p>
          ) : (
            <div className="divide-y divide-gray-100 max-h-[400px] overflow-y-auto">
              {slas.map((sla: any) => (
                <SLARow
                  key={sla.id}
                  sla={sla}
                  comments={getCommentsFor(`sla:${sla.id}`)}
                  onAddComment={(content) => addCommentMut.mutate({ content, section_reference: `sla:${sla.id}` })}
                  onViewSource={() => {
                    const slaHL = highlights?.highlights?.[sla.id]
                    if (slaHL?.rects?.length) {
                      setActiveRects(slaHL.rects)
                      setHighlightPage(slaHL.rects[0].page)
                      setHighlightText(null)
                    } else {
                      setActiveRects(null)
                      setHighlightText(sla.source_text)
                      setHighlightPage(null)
                    }
                  }}
                />
              ))}
            </div>
          )}
        </Section>
      </div>

      {/* ── Drag Handle ── */}
      <div
        onMouseDown={onMouseDown}
        className="flex-shrink-0 w-1.5 cursor-col-resize bg-gray-200 hover:bg-primary-300 active:bg-primary-400 transition-colors"
      />

      {/* ── Right Pane: PDF Viewer ── */}
      <div className="flex-1 min-w-0">
        <ContractPdfViewer
          contractId={contractId}
          mimeType={contract.mime_type}
          highlightPage={highlightPage}
          highlightText={highlightText}
          activeRects={activeRects}
          allHighlights={highlights?.highlights}
          pageDimensions={highlights?.page_dimensions}
          onHighlightClick={(clauseId) => {
            const clauseHL = highlights?.highlights?.[clauseId]
            if (clauseHL?.rects?.length) {
              setActiveRects(clauseHL.rects)
              setHighlightPage(clauseHL.rects[0].page)
              setHighlightText(null)
            }
          }}
          onPageChange={() => { setHighlightText(null); setHighlightPage(null); setActiveRects(null) }}
        />
      </div>
    </div>
  )
}


// ── Inline Comments Widget ──────────────────────────────────────────

function InlineComments({
  comments,
  onAddComment,
}: {
  comments: ContractCommentItem[]
  onAddComment: (content: string) => void
}) {
  const [showComments, setShowComments] = useState(false)
  const [newComment, setNewComment] = useState('')

  const handleSubmit = () => {
    if (!newComment.trim()) return
    onAddComment(newComment.trim())
    setNewComment('')
  }

  return (
    <div className="mt-1.5">
      <button
        onClick={() => setShowComments(!showComments)}
        className={cn(
          'flex items-center gap-1 text-xs px-1.5 py-0.5 rounded',
          comments.length > 0
            ? 'text-primary-600 bg-primary-50 hover:bg-primary-100'
            : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
        )}
      >
        <ChatBubbleLeftIcon className="h-3 w-3" />
        {comments.length > 0 ? `${comments.length} comment${comments.length > 1 ? 's' : ''}` : 'Comment'}
      </button>

      {showComments && (
        <div className="mt-1.5 ml-1 border-l-2 border-primary-200 pl-2 space-y-1.5">
          {comments.map((c) => (
            <div key={c.id} className="text-xs">
              <div className="flex items-center gap-1.5">
                <span className="font-medium text-gray-800">{c.author_name || 'Unknown'}</span>
                {!c.is_internal_author && (
                  <span className="text-[10px] bg-blue-50 text-blue-600 px-1 rounded">External</span>
                )}
                <span className="text-gray-400">{formatDate(c.created_at)}</span>
              </div>
              <p className="text-gray-600 mt-0.5">{c.content}</p>
            </div>
          ))}
          <div className="flex gap-1">
            <input
              type="text"
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit() }}
              placeholder="Add comment..."
              className="flex-1 text-xs px-2 py-1 border border-gray-200 rounded focus:outline-none focus:border-primary-400"
            />
            <button
              onClick={handleSubmit}
              disabled={!newComment.trim()}
              className="text-xs px-2 py-1 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-40"
            >
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Clause Row Component ────────────────────────────────────────────

function ClauseRow({
  clause,
  canEdit,
  comments,
  onAddComment,
  onViewSource,
  onUpdate,
}: {
  clause: ClauseDetail & { _type: string }
  canEdit: boolean
  comments: ContractCommentItem[]
  onAddComment: (content: string) => void
  onViewSource: () => void
  onUpdate: (data: Record<string, unknown>) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [editingText, setEditingText] = useState(false)
  const [editText, setEditText] = useState(clause.text)

  return (
    <div className="px-4 py-2.5 hover:bg-gray-50">
      <div className="flex items-center gap-2">
        <button onClick={() => setExpanded(!expanded)} className="flex-1 flex items-center gap-2 text-left min-w-0">
          {expanded ? <ChevronDownIcon className="h-3 w-3 text-gray-400 flex-shrink-0" /> : <ChevronRightIcon className="h-3 w-3 text-gray-400 flex-shrink-0" />}
          <span className="text-xs font-medium text-primary-600 flex-shrink-0">
            {CLAUSE_TYPE_LABELS[clause._type] || clause._type}
          </span>
          {clause.section_number && (
            <span className="text-xs text-gray-400 flex-shrink-0">{clause.section_number}</span>
          )}
          <span className="text-xs text-gray-600 truncate">{clause.text.substring(0, 80)}...</span>
        </button>
        <RiskBadge level={clause.risk_level} />
        <button
          onClick={onViewSource}
          title={clause.page_number ? `View on page ${clause.page_number}` : 'Find in document'}
          className="p-1 rounded hover:bg-primary-100 text-primary-600 flex-shrink-0"
        >
          <DocumentMagnifyingGlassIcon className="h-4 w-4" />
        </button>
      </div>

      {expanded && (
        <div className="mt-2 ml-5 space-y-2">
          {editingText ? (
            <div>
              <textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                rows={4}
                className="input text-sm w-full"
              />
              <div className="flex justify-end gap-1 mt-1">
                <button
                  onClick={() => { onUpdate({ text: editText }); setEditingText(false) }}
                  className="text-xs px-2 py-1 bg-primary-600 text-white rounded hover:bg-primary-700"
                >
                  Save
                </button>
                <button
                  onClick={() => { setEditText(clause.text); setEditingText(false) }}
                  className="text-xs px-2 py-1 text-gray-500 hover:bg-gray-100 rounded"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="group relative">
              <p className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed">{clause.text}</p>
              {canEdit && (
                <button
                  onClick={() => setEditingText(true)}
                  className="absolute top-0 right-0 p-0.5 rounded opacity-0 group-hover:opacity-100 hover:bg-gray-100"
                >
                  <PencilIcon className="h-3 w-3 text-gray-400" />
                </button>
              )}
            </div>
          )}
          {clause.page_number && (
            <p className="text-xs text-gray-400">Page {clause.page_number}</p>
          )}
          <InlineComments comments={comments} onAddComment={onAddComment} />
        </div>
      )}
    </div>
  )
}


// ── Obligation Row Component ────────────────────────────────────────

function ObligationRow({
  obligation,
  canEdit,
  comments,
  onAddComment,
  onViewSource,
  onUpdate,
}: {
  obligation: ObligationItem
  canEdit: boolean
  comments: ContractCommentItem[]
  onAddComment: (content: string) => void
  onViewSource: () => void
  onUpdate: (data: Record<string, unknown>) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [editingDesc, setEditingDesc] = useState(false)
  const [editDesc, setEditDesc] = useState(obligation.description)

  const statusColors: Record<string, string> = {
    pending: 'bg-gray-100 text-gray-600',
    in_progress: 'bg-blue-100 text-blue-700',
    completed: 'bg-green-100 text-green-700',
    overdue: 'bg-red-100 text-red-700',
    waived: 'bg-gray-100 text-gray-500',
  }

  return (
    <div className="px-4 py-2.5 hover:bg-gray-50">
      <div className="flex items-center gap-2">
        <button onClick={() => setExpanded(!expanded)} className="flex-1 flex items-center gap-2 text-left min-w-0">
          {expanded ? <ChevronDownIcon className="h-3 w-3 text-gray-400 flex-shrink-0" /> : <ChevronRightIcon className="h-3 w-3 text-gray-400 flex-shrink-0" />}
          <span className="text-xs text-gray-600 truncate">{obligation.description.substring(0, 100)}...</span>
        </button>
        <span className={cn('px-1.5 py-0.5 rounded text-xs font-medium capitalize flex-shrink-0', statusColors[obligation.status] || 'bg-gray-100')}>
          {obligation.status?.replace('_', ' ')}
        </span>
        {comments.length > 0 && (
          <span className="flex items-center gap-0.5 text-xs text-primary-600 flex-shrink-0">
            <ChatBubbleLeftIcon className="h-3 w-3" />
            {comments.length}
          </span>
        )}
        <button
          onClick={onViewSource}
          title="View in document"
          className="p-1 rounded hover:bg-primary-100 text-primary-600 flex-shrink-0"
        >
          <DocumentMagnifyingGlassIcon className="h-4 w-4" />
        </button>
      </div>

      {expanded && (
        <div className="mt-2 ml-5 space-y-2">
          {editingDesc ? (
            <div>
              <textarea
                value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)}
                rows={3}
                className="input text-sm w-full"
              />
              <div className="flex justify-end gap-1 mt-1">
                <button
                  onClick={() => { onUpdate({ description: editDesc }); setEditingDesc(false) }}
                  className="text-xs px-2 py-1 bg-primary-600 text-white rounded hover:bg-primary-700"
                >
                  Save
                </button>
                <button
                  onClick={() => { setEditDesc(obligation.description); setEditingDesc(false) }}
                  className="text-xs px-2 py-1 text-gray-500 hover:bg-gray-100 rounded"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="group relative">
              <p className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed">{obligation.description}</p>
              {canEdit && (
                <button
                  onClick={() => setEditingDesc(true)}
                  className="absolute top-0 right-0 p-0.5 rounded opacity-0 group-hover:opacity-100 hover:bg-gray-100"
                >
                  <PencilIcon className="h-3 w-3 text-gray-400" />
                </button>
              )}
            </div>
          )}
          <div className="flex items-center gap-4 text-xs text-gray-500">
            <span className="capitalize">{obligation.obligation_type}</span>
            {obligation.obligated_party && <span>Party: {obligation.obligated_party}</span>}
            {obligation.deadline && <span>Deadline: {formatDate(obligation.deadline)}</span>}
          </div>
          <InlineComments comments={comments} onAddComment={onAddComment} />
        </div>
      )}
    </div>
  )
}


// ── SLA Row Component ────────────────────────────────────────────────

function SLARow({
  sla,
  comments,
  onAddComment,
  onViewSource,
}: {
  sla: any
  comments: ContractCommentItem[]
  onAddComment: (content: string) => void
  onViewSource: () => void
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="px-4 py-2.5 hover:bg-gray-50">
      <div className="flex items-center gap-2">
        <button onClick={() => setExpanded(!expanded)} className="flex-1 flex items-center gap-2 text-left min-w-0">
          {expanded ? <ChevronDownIcon className="h-3 w-3 text-gray-400 flex-shrink-0" /> : <ChevronRightIcon className="h-3 w-3 text-gray-400 flex-shrink-0" />}
          <span className="text-sm font-medium text-gray-900 truncate">{sla.sla_name}</span>
        </button>
        <RiskBadge level={sla.severity} />
        {comments.length > 0 && (
          <span className="flex items-center gap-0.5 text-xs text-primary-600">
            <ChatBubbleLeftIcon className="h-3 w-3" />
            {comments.length}
          </span>
        )}
        {sla.source_text && (
          <button
            onClick={onViewSource}
            title="View in document"
            className="p-1 rounded hover:bg-primary-100 text-primary-600 flex-shrink-0"
          >
            <DocumentMagnifyingGlassIcon className="h-4 w-4" />
          </button>
        )}
      </div>
      <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
        <span>{sla.metric_type?.replace(/_/g, ' ')}</span>
        <span>{sla.target_operator} {sla.target_value} {sla.metric_unit}</span>
        {sla.has_penalty && (
          <span className="text-orange-600">Has penalty</span>
        )}
      </div>
      {expanded && (
        <div className="mt-2 ml-5">
          <InlineComments comments={comments} onAddComment={onAddComment} />
        </div>
      )}
    </div>
  )
}
