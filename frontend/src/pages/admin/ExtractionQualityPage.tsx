import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  PlusIcon,
  TrashIcon,
  ChevronRightIcon,
  ArrowLeftIcon,
  DocumentTextIcon,
  AdjustmentsHorizontalIcon,
  PencilSquareIcon,
  XMarkIcon,
  EyeIcon,
  GlobeAltIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import ContractPdfViewer from '@/components/contracts/ContractPdfViewer'
import { cn } from '@/lib/utils'

type ViewMode = 'overview' | 'detail'

const SCORE_COLORS = (score: number | null) => {
  if (score === null) return 'text-gray-400'
  if (score >= 90) return 'text-green-600'
  if (score >= 70) return 'text-yellow-600'
  return 'text-red-600'
}

const SCORE_BG = (score: number | null) => {
  if (score === null) return 'bg-gray-50'
  if (score >= 90) return 'bg-green-50'
  if (score >= 70) return 'bg-yellow-50'
  return 'bg-red-50'
}

const STATUS_BADGE = {
  correct: 'bg-green-100 text-green-700',
  incorrect: 'bg-red-100 text-red-700',
  partial: 'bg-yellow-100 text-yellow-700',
  pending: 'bg-gray-100 text-gray-500',
}

function ScoreCard({ label, score }: { label: string; score: number | null }) {
  return (
    <div className={cn('rounded-lg p-4 text-center', SCORE_BG(score))}>
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className={cn('text-2xl font-bold', SCORE_COLORS(score))}>
        {score !== null ? `${score}%` : '--'}
      </p>
    </div>
  )
}

function VerificationBadge({ status }: { status: string | null }) {
  if (!status) return null
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium', STATUS_BADGE[status as keyof typeof STATUS_BADGE] || STATUS_BADGE.pending)}>
      {status === 'correct' && <CheckCircleIcon className="h-3 w-3" />}
      {status === 'incorrect' && <XCircleIcon className="h-3 w-3" />}
      {status === 'partial' && <ExclamationTriangleIcon className="h-3 w-3" />}
      {status === 'pending' && <ClockIcon className="h-3 w-3" />}
      {status}
    </span>
  )
}

// Inline edit form for metadata fields
function MetadataEditRow({
  item,
  goldenSetId: _,
  onVerify,
}: {
  item: { field: string; value: unknown; verification: { status: string; corrected_value: unknown; notes: string | null } | null }
  goldenSetId: string
  onVerify: (entityType: string, entityId: string, status: 'correct' | 'incorrect' | 'partial', correctedValue?: Record<string, unknown>, notes?: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [editValue, setEditValue] = useState('')
  const [editNotes, setEditNotes] = useState('')

  const corrected = item.verification?.corrected_value as Record<string, unknown> | null
  const displayValue = corrected?.value !== undefined ? String(corrected.value) : (item.value !== null && item.value !== undefined ? String(item.value) : null)

  const startEdit = () => {
    setEditValue(displayValue || '')
    setEditNotes(item.verification?.notes || '')
    setEditing(true)
  }

  const saveEdit = (status: 'incorrect' | 'partial') => {
    onVerify('metadata_field', item.field, status, { value: editValue }, editNotes || undefined)
    setEditing(false)
  }

  if (editing) {
    return (
      <div className="px-4 py-3 bg-violet-50/50">
        <div className="flex items-center justify-between mb-2">
          <p className="text-sm font-medium text-gray-700 capitalize">{item.field.replace(/_/g, ' ')}</p>
          <button onClick={() => setEditing(false)} className="p-1 text-gray-400 hover:text-gray-600">
            <XMarkIcon className="h-4 w-4" />
          </button>
        </div>
        <div className="space-y-2">
          <div>
            <label className="text-xs text-gray-500">Original: {item.value !== null ? String(item.value) : '(empty)'}</label>
            <input
              type="text"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              className="input w-full mt-1"
              placeholder="Corrected value..."
              autoFocus
            />
          </div>
          <input
            type="text"
            value={editNotes}
            onChange={(e) => setEditNotes(e.target.value)}
            className="input w-full text-sm"
            placeholder="Notes (optional)..."
          />
          <div className="flex gap-2">
            <button
              onClick={() => saveEdit('incorrect')}
              className="btn-secondary text-xs px-3 py-1.5 bg-red-50 text-red-700 border-red-200 hover:bg-red-100"
            >
              Save as Incorrect
            </button>
            <button
              onClick={() => saveEdit('partial')}
              className="btn-secondary text-xs px-3 py-1.5 bg-yellow-50 text-yellow-700 border-yellow-200 hover:bg-yellow-100"
            >
              Save as Partial
            </button>
            <button onClick={() => setEditing(false)} className="btn-secondary text-xs px-3 py-1.5">
              Cancel
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-between px-4 py-3">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-700 capitalize">{item.field.replace(/_/g, ' ')}</p>
        <p className="text-sm text-gray-500 mt-0.5">
          {displayValue !== null ? displayValue : <span className="italic text-gray-400">Not extracted</span>}
        </p>
        {corrected && (
          <p className="text-xs text-violet-600 mt-0.5">Corrected from: {item.value !== null ? String(item.value) : '(empty)'}</p>
        )}
        {item.verification?.notes && (
          <p className="text-xs text-gray-400 mt-0.5 italic">{item.verification.notes}</p>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {item.verification && <VerificationBadge status={item.verification.status} />}
        <div className="flex gap-1 ml-1">
          <button onClick={() => onVerify('metadata_field', item.field, 'correct')} className="p-1 rounded hover:bg-green-50 text-gray-400 hover:text-green-600" title="Correct">
            <CheckCircleIcon className="h-5 w-5" />
          </button>
          <button onClick={startEdit} className="p-1 rounded hover:bg-violet-50 text-gray-400 hover:text-violet-600" title="Edit & correct">
            <PencilSquareIcon className="h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  )
}

// Inline edit form for clauses
function ClauseEditRow({
  clause,
  goldenSetId: _,
  onVerify,
  onLocate,
}: {
  clause: { id: string; clause_type: string | null; text: string | null; section_number: string | null; page_number: number | null; risk_level: string | null; confidence: number | null; verification: { status: string; corrected_value: unknown; notes: string | null } | null }
  goldenSetId: string
  onVerify: (entityType: string, entityId: string, status: 'correct' | 'incorrect' | 'partial', correctedValue?: Record<string, unknown>, notes?: string) => void
  onLocate?: (text: string, page?: number | null) => void
}) {
  const [editing, setEditing] = useState(false)
  const [editType, setEditType] = useState('')
  const [editText, setEditText] = useState('')
  const [editRisk, setEditRisk] = useState('')
  const [editNotes, setEditNotes] = useState('')

  const corrected = clause.verification?.corrected_value as Record<string, unknown> | null

  const startEdit = () => {
    setEditType((corrected?.clause_type as string) || clause.clause_type || '')
    setEditText((corrected?.text as string) || clause.text || '')
    setEditRisk((corrected?.risk_level as string) || clause.risk_level || '')
    setEditNotes(clause.verification?.notes || '')
    setEditing(true)
  }

  const saveEdit = (status: 'incorrect' | 'partial') => {
    const corrections: Record<string, unknown> = {}
    if (editType !== (clause.clause_type || '')) corrections.clause_type = editType
    if (editText !== (clause.text || '')) corrections.text = editText
    if (editRisk !== (clause.risk_level || '')) corrections.risk_level = editRisk
    onVerify('clause', clause.id, status, Object.keys(corrections).length > 0 ? corrections : undefined, editNotes || undefined)
    setEditing(false)
  }

  const displayType = (corrected?.clause_type as string) || clause.clause_type
  const displayText = (corrected?.text as string) || clause.text

  if (editing) {
    return (
      <div className="px-4 py-3 bg-violet-50/50">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-violet-600">Edit Clause</span>
          <button onClick={() => setEditing(false)} className="p-1 text-gray-400 hover:text-gray-600">
            <XMarkIcon className="h-4 w-4" />
          </button>
        </div>
        <div className="space-y-2">
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-xs text-gray-500">Clause Type</label>
              <input type="text" value={editType} onChange={(e) => setEditType(e.target.value)} className="input w-full mt-1" placeholder="e.g. termination, indemnification..." />
            </div>
            <div className="w-32">
              <label className="text-xs text-gray-500">Risk Level</label>
              <select value={editRisk} onChange={(e) => setEditRisk(e.target.value)} className="input w-full mt-1">
                <option value="">--</option>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-500">Text</label>
            <textarea value={editText} onChange={(e) => setEditText(e.target.value)} rows={3} className="input w-full mt-1 text-sm" />
          </div>
          <input type="text" value={editNotes} onChange={(e) => setEditNotes(e.target.value)} className="input w-full text-sm" placeholder="Notes..." />
          <div className="flex gap-2">
            <button onClick={() => saveEdit('incorrect')} className="btn-secondary text-xs px-3 py-1.5 bg-red-50 text-red-700 border-red-200 hover:bg-red-100">Save as Incorrect</button>
            <button onClick={() => saveEdit('partial')} className="btn-secondary text-xs px-3 py-1.5 bg-yellow-50 text-yellow-700 border-yellow-200 hover:bg-yellow-100">Save as Partial</button>
            <button onClick={() => setEditing(false)} className="btn-secondary text-xs px-3 py-1.5">Cancel</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="px-4 py-3">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-violet-600 bg-violet-50 rounded px-1.5 py-0.5">{displayType || 'unknown'}</span>
          {clause.risk_level && (
            <span className={cn('text-xs rounded px-1.5 py-0.5', clause.risk_level === 'high' ? 'bg-red-50 text-red-600' : clause.risk_level === 'medium' ? 'bg-yellow-50 text-yellow-600' : 'bg-green-50 text-green-600')}>
              {clause.risk_level} risk
            </span>
          )}
          {clause.confidence !== null && <span className="text-xs text-gray-400">{Math.round(clause.confidence * 100)}% conf.</span>}
        </div>
        <div className="flex items-center gap-2">
          {clause.verification && <VerificationBadge status={clause.verification.status} />}
          <div className="flex gap-1">
            <button onClick={() => onVerify('clause', clause.id, 'correct')} className="p-1 rounded hover:bg-green-50 text-gray-400 hover:text-green-600" title="Correct"><CheckCircleIcon className="h-4 w-4" /></button>
            <button onClick={startEdit} className="p-1 rounded hover:bg-violet-50 text-gray-400 hover:text-violet-600" title="Edit"><PencilSquareIcon className="h-4 w-4" /></button>
              {onLocate && clause.text && (
                <button onClick={() => onLocate(clause.text!, clause.page_number)} className="p-1 rounded hover:bg-yellow-50 text-gray-400 hover:text-yellow-600" title="Locate in document"><EyeIcon className="h-4 w-4" /></button>
              )}
          </div>
        </div>
      </div>
      <p className="text-sm text-gray-600 line-clamp-3">{displayText}</p>
      {corrected && <p className="text-xs text-violet-600 mt-1">Corrected</p>}
      {clause.verification?.notes && <p className="text-xs text-gray-400 mt-0.5 italic">{clause.verification.notes}</p>}
      {clause.section_number && <p className="text-xs text-gray-400 mt-1">Section {clause.section_number}{clause.page_number ? `, Page ${clause.page_number}` : ''}</p>}
    </div>
  )
}

// Inline edit form for obligations
function ObligationEditRow({
  obl,
  onVerify,
}: {
  obl: { id: string; description: string | null; obligation_type: string | null; obligated_party: string | null; deadline_type: string | null; deadline: string | null; status: string | null; is_critical: boolean; verification: { status: string; corrected_value: unknown; notes: string | null } | null }
  onVerify: (entityType: string, entityId: string, status: 'correct' | 'incorrect' | 'partial', correctedValue?: Record<string, unknown>, notes?: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [editDesc, setEditDesc] = useState('')
  const [editType, setEditType] = useState('')
  const [editParty, setEditParty] = useState('')
  const [editNotes, setEditNotes] = useState('')

  const corrected = obl.verification?.corrected_value as Record<string, unknown> | null

  const startEdit = () => {
    setEditDesc((corrected?.description as string) || obl.description || '')
    setEditType((corrected?.obligation_type as string) || obl.obligation_type || '')
    setEditParty((corrected?.obligated_party as string) || obl.obligated_party || '')
    setEditNotes(obl.verification?.notes || '')
    setEditing(true)
  }

  const saveEdit = (status: 'incorrect' | 'partial') => {
    const corrections: Record<string, unknown> = {}
    if (editDesc !== (obl.description || '')) corrections.description = editDesc
    if (editType !== (obl.obligation_type || '')) corrections.obligation_type = editType
    if (editParty !== (obl.obligated_party || '')) corrections.obligated_party = editParty
    onVerify('obligation', obl.id, status, Object.keys(corrections).length > 0 ? corrections : undefined, editNotes || undefined)
    setEditing(false)
  }

  if (editing) {
    return (
      <div className="px-4 py-3 bg-violet-50/50">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-blue-600">Edit Obligation</span>
          <button onClick={() => setEditing(false)} className="p-1 text-gray-400 hover:text-gray-600"><XMarkIcon className="h-4 w-4" /></button>
        </div>
        <div className="space-y-2">
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-xs text-gray-500">Type</label>
              <input type="text" value={editType} onChange={(e) => setEditType(e.target.value)} className="input w-full mt-1" />
            </div>
            <div className="flex-1">
              <label className="text-xs text-gray-500">Obligated Party</label>
              <input type="text" value={editParty} onChange={(e) => setEditParty(e.target.value)} className="input w-full mt-1" />
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-500">Description</label>
            <textarea value={editDesc} onChange={(e) => setEditDesc(e.target.value)} rows={2} className="input w-full mt-1 text-sm" />
          </div>
          <input type="text" value={editNotes} onChange={(e) => setEditNotes(e.target.value)} className="input w-full text-sm" placeholder="Notes..." />
          <div className="flex gap-2">
            <button onClick={() => saveEdit('incorrect')} className="btn-secondary text-xs px-3 py-1.5 bg-red-50 text-red-700 border-red-200 hover:bg-red-100">Save as Incorrect</button>
            <button onClick={() => saveEdit('partial')} className="btn-secondary text-xs px-3 py-1.5 bg-yellow-50 text-yellow-700 border-yellow-200 hover:bg-yellow-100">Save as Partial</button>
            <button onClick={() => setEditing(false)} className="btn-secondary text-xs px-3 py-1.5">Cancel</button>
          </div>
        </div>
      </div>
    )
  }

  const displayDesc = (corrected?.description as string) || obl.description

  return (
    <div className="px-4 py-3">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-blue-600 bg-blue-50 rounded px-1.5 py-0.5">{obl.obligation_type || 'unknown'}</span>
          {obl.is_critical && <span className="text-xs bg-red-50 text-red-600 rounded px-1.5 py-0.5">critical</span>}
          {obl.obligated_party && <span className="text-xs text-gray-400">{obl.obligated_party}</span>}
        </div>
        <div className="flex items-center gap-2">
          {obl.verification && <VerificationBadge status={obl.verification.status} />}
          <div className="flex gap-1">
            <button onClick={() => onVerify('obligation', obl.id, 'correct')} className="p-1 rounded hover:bg-green-50 text-gray-400 hover:text-green-600"><CheckCircleIcon className="h-4 w-4" /></button>
            <button onClick={startEdit} className="p-1 rounded hover:bg-violet-50 text-gray-400 hover:text-violet-600" title="Edit"><PencilSquareIcon className="h-4 w-4" /></button>
          </div>
        </div>
      </div>
      <p className="text-sm text-gray-600 line-clamp-2">{displayDesc}</p>
      {corrected && <p className="text-xs text-violet-600 mt-1">Corrected</p>}
      {obl.verification?.notes && <p className="text-xs text-gray-400 mt-0.5 italic">{obl.verification.notes}</p>}
      {obl.deadline && <p className="text-xs text-gray-400 mt-1">Deadline: {obl.deadline} ({obl.deadline_type})</p>}
    </div>
  )
}

// Inline edit for SLAs
function SLAEditRow({
  sla,
  onVerify,
}: {
  sla: { id: string; sla_name: string | null; metric_type: string | null; target_value: number | null; metric_unit: string | null; severity: string | null; has_penalty: boolean; penalty_value: number | null; verification: { status: string; corrected_value: unknown; notes: string | null } | null }
  onVerify: (entityType: string, entityId: string, status: 'correct' | 'incorrect' | 'partial', correctedValue?: Record<string, unknown>, notes?: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [editName, setEditName] = useState('')
  const [editTarget, setEditTarget] = useState('')
  const [editUnit, setEditUnit] = useState('')
  const [editNotes, setEditNotes] = useState('')

  const corrected = sla.verification?.corrected_value as Record<string, unknown> | null

  const startEdit = () => {
    setEditName((corrected?.sla_name as string) || sla.sla_name || '')
    setEditTarget(String((corrected?.target_value as number) ?? sla.target_value ?? ''))
    setEditUnit((corrected?.metric_unit as string) || sla.metric_unit || '')
    setEditNotes(sla.verification?.notes || '')
    setEditing(true)
  }

  const saveEdit = (status: 'incorrect' | 'partial') => {
    const corrections: Record<string, unknown> = {}
    if (editName !== (sla.sla_name || '')) corrections.sla_name = editName
    const targetNum = parseFloat(editTarget)
    if (!isNaN(targetNum) && targetNum !== sla.target_value) corrections.target_value = targetNum
    if (editUnit !== (sla.metric_unit || '')) corrections.metric_unit = editUnit
    onVerify('sla', sla.id, status, Object.keys(corrections).length > 0 ? corrections : undefined, editNotes || undefined)
    setEditing(false)
  }

  if (editing) {
    return (
      <div className="px-4 py-3 bg-violet-50/50">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-teal-600">Edit SLA</span>
          <button onClick={() => setEditing(false)} className="p-1 text-gray-400 hover:text-gray-600"><XMarkIcon className="h-4 w-4" /></button>
        </div>
        <div className="space-y-2">
          <div>
            <label className="text-xs text-gray-500">SLA Name</label>
            <input type="text" value={editName} onChange={(e) => setEditName(e.target.value)} className="input w-full mt-1" />
          </div>
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-xs text-gray-500">Target Value</label>
              <input type="number" step="any" value={editTarget} onChange={(e) => setEditTarget(e.target.value)} className="input w-full mt-1" />
            </div>
            <div className="flex-1">
              <label className="text-xs text-gray-500">Unit</label>
              <input type="text" value={editUnit} onChange={(e) => setEditUnit(e.target.value)} className="input w-full mt-1" placeholder="e.g. percent, hours..." />
            </div>
          </div>
          <input type="text" value={editNotes} onChange={(e) => setEditNotes(e.target.value)} className="input w-full text-sm" placeholder="Notes..." />
          <div className="flex gap-2">
            <button onClick={() => saveEdit('incorrect')} className="btn-secondary text-xs px-3 py-1.5 bg-red-50 text-red-700 border-red-200 hover:bg-red-100">Save as Incorrect</button>
            <button onClick={() => saveEdit('partial')} className="btn-secondary text-xs px-3 py-1.5 bg-yellow-50 text-yellow-700 border-yellow-200 hover:bg-yellow-100">Save as Partial</button>
            <button onClick={() => setEditing(false)} className="btn-secondary text-xs px-3 py-1.5">Cancel</button>
          </div>
        </div>
      </div>
    )
  }

  const displayName = (corrected?.sla_name as string) || sla.sla_name
  const displayTarget = (corrected?.target_value as number) ?? sla.target_value

  return (
    <div className="px-4 py-3">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-teal-600 bg-teal-50 rounded px-1.5 py-0.5">{sla.metric_type || 'SLA'}</span>
          {sla.severity && (
            <span className={cn('text-xs rounded px-1.5 py-0.5', sla.severity === 'critical' ? 'bg-red-50 text-red-600' : sla.severity === 'major' ? 'bg-orange-50 text-orange-600' : 'bg-gray-50 text-gray-600')}>
              {sla.severity}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {sla.verification && <VerificationBadge status={sla.verification.status} />}
          <div className="flex gap-1">
            <button onClick={() => onVerify('sla', sla.id, 'correct')} className="p-1 rounded hover:bg-green-50 text-gray-400 hover:text-green-600"><CheckCircleIcon className="h-4 w-4" /></button>
            <button onClick={startEdit} className="p-1 rounded hover:bg-violet-50 text-gray-400 hover:text-violet-600" title="Edit"><PencilSquareIcon className="h-4 w-4" /></button>
          </div>
        </div>
      </div>
      <p className="text-sm text-gray-700 font-medium">{displayName}</p>
      <p className="text-sm text-gray-500">
        Target: {displayTarget !== null ? displayTarget : '--'} {sla.metric_unit || ''}
        {sla.has_penalty && sla.penalty_value && <span className="ml-2 text-red-500">Penalty: {sla.penalty_value}</span>}
      </p>
      {corrected && <p className="text-xs text-violet-600 mt-1">Corrected</p>}
      {sla.verification?.notes && <p className="text-xs text-gray-400 mt-0.5 italic">{sla.verification.notes}</p>}
    </div>
  )
}

// ======================== ADD MISSING ITEM FORMS ========================

function AddMissingClause({ onAdd }: { onAdd: (correctedValue: Record<string, unknown>) => void }) {
  const [open, setOpen] = useState(false)
  const [clauseType, setClauseType] = useState('')
  const [text, setText] = useState('')
  const [riskLevel, setRiskLevel] = useState('')

  const handleSubmit = () => {
    if (!clauseType || !text) return
    onAdd({ clause_type: clauseType, text, risk_level: riskLevel || undefined })
    setClauseType(''); setText(''); setRiskLevel(''); setOpen(false)
  }

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="w-full px-4 py-3 text-sm text-violet-600 hover:bg-violet-50 flex items-center gap-1.5 transition-colors">
        <PlusIcon className="h-4 w-4" /> Add missing clause
      </button>
    )
  }

  return (
    <div className="px-4 py-3 bg-violet-50/50">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-violet-600">Add Missing Clause</span>
        <button onClick={() => setOpen(false)} className="p-1 text-gray-400 hover:text-gray-600"><XMarkIcon className="h-4 w-4" /></button>
      </div>
      <div className="space-y-2">
        <div className="flex gap-2">
          <div className="flex-1">
            <label className="text-xs text-gray-500">Clause Type *</label>
            <input type="text" value={clauseType} onChange={(e) => setClauseType(e.target.value)} className="input w-full mt-1" placeholder="e.g. termination, indemnification..." autoFocus />
          </div>
          <div className="w-32">
            <label className="text-xs text-gray-500">Risk Level</label>
            <select value={riskLevel} onChange={(e) => setRiskLevel(e.target.value)} className="input w-full mt-1">
              <option value="">--</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
        </div>
        <div>
          <label className="text-xs text-gray-500">Clause Text *</label>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} className="input w-full mt-1 text-sm" placeholder="Paste the clause text..." />
        </div>
        <div className="flex gap-2">
          <button onClick={handleSubmit} disabled={!clauseType || !text} className="btn-primary text-xs px-3 py-1.5 disabled:opacity-50">Add to Golden Set</button>
          <button onClick={() => setOpen(false)} className="btn-secondary text-xs px-3 py-1.5">Cancel</button>
        </div>
      </div>
    </div>
  )
}

function AddMissingObligation({ onAdd }: { onAdd: (correctedValue: Record<string, unknown>) => void }) {
  const [open, setOpen] = useState(false)
  const [oblType, setOblType] = useState('')
  const [party, setParty] = useState('')
  const [desc, setDesc] = useState('')

  const handleSubmit = () => {
    if (!oblType || !desc) return
    onAdd({ obligation_type: oblType, obligated_party: party || undefined, description: desc })
    setOblType(''); setParty(''); setDesc(''); setOpen(false)
  }

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="w-full px-4 py-3 text-sm text-blue-600 hover:bg-blue-50 flex items-center gap-1.5 transition-colors">
        <PlusIcon className="h-4 w-4" /> Add missing obligation
      </button>
    )
  }

  return (
    <div className="px-4 py-3 bg-blue-50/50">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-blue-600">Add Missing Obligation</span>
        <button onClick={() => setOpen(false)} className="p-1 text-gray-400 hover:text-gray-600"><XMarkIcon className="h-4 w-4" /></button>
      </div>
      <div className="space-y-2">
        <div className="flex gap-2">
          <div className="flex-1">
            <label className="text-xs text-gray-500">Obligation Type *</label>
            <input type="text" value={oblType} onChange={(e) => setOblType(e.target.value)} className="input w-full mt-1" placeholder="e.g. payment, delivery, reporting..." autoFocus />
          </div>
          <div className="flex-1">
            <label className="text-xs text-gray-500">Obligated Party</label>
            <input type="text" value={party} onChange={(e) => setParty(e.target.value)} className="input w-full mt-1" placeholder="e.g. Vendor, Client..." />
          </div>
        </div>
        <div>
          <label className="text-xs text-gray-500">Description *</label>
          <textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={2} className="input w-full mt-1 text-sm" placeholder="Describe the obligation..." />
        </div>
        <div className="flex gap-2">
          <button onClick={handleSubmit} disabled={!oblType || !desc} className="btn-primary text-xs px-3 py-1.5 disabled:opacity-50">Add to Golden Set</button>
          <button onClick={() => setOpen(false)} className="btn-secondary text-xs px-3 py-1.5">Cancel</button>
        </div>
      </div>
    </div>
  )
}

function AddMissingSLA({ onAdd }: { onAdd: (correctedValue: Record<string, unknown>) => void }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [metricType, setMetricType] = useState('')
  const [target, setTarget] = useState('')
  const [unit, setUnit] = useState('')

  const handleSubmit = () => {
    if (!name) return
    const targetNum = parseFloat(target)
    onAdd({
      sla_name: name,
      metric_type: metricType || undefined,
      target_value: !isNaN(targetNum) ? targetNum : undefined,
      metric_unit: unit || undefined,
    })
    setName(''); setMetricType(''); setTarget(''); setUnit(''); setOpen(false)
  }

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="w-full px-4 py-3 text-sm text-teal-600 hover:bg-teal-50 flex items-center gap-1.5 transition-colors">
        <PlusIcon className="h-4 w-4" /> Add missing SLA
      </button>
    )
  }

  return (
    <div className="px-4 py-3 bg-teal-50/50">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-teal-600">Add Missing SLA</span>
        <button onClick={() => setOpen(false)} className="p-1 text-gray-400 hover:text-gray-600"><XMarkIcon className="h-4 w-4" /></button>
      </div>
      <div className="space-y-2">
        <div>
          <label className="text-xs text-gray-500">SLA Name *</label>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} className="input w-full mt-1" placeholder="e.g. System Uptime, Response Time P1..." autoFocus />
        </div>
        <div className="flex gap-2">
          <div className="flex-1">
            <label className="text-xs text-gray-500">Metric Type</label>
            <input type="text" value={metricType} onChange={(e) => setMetricType(e.target.value)} className="input w-full mt-1" placeholder="e.g. uptime_percentage..." />
          </div>
          <div className="w-28">
            <label className="text-xs text-gray-500">Target</label>
            <input type="number" step="any" value={target} onChange={(e) => setTarget(e.target.value)} className="input w-full mt-1" placeholder="99.9" />
          </div>
          <div className="w-28">
            <label className="text-xs text-gray-500">Unit</label>
            <input type="text" value={unit} onChange={(e) => setUnit(e.target.value)} className="input w-full mt-1" placeholder="percent" />
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={handleSubmit} disabled={!name} className="btn-primary text-xs px-3 py-1.5 disabled:opacity-50">Add to Golden Set</button>
          <button onClick={() => setOpen(false)} className="btn-secondary text-xs px-3 py-1.5">Cancel</button>
        </div>
      </div>
    </div>
  )
}

// ─── Text Viewer for CUAD .txt contracts ────────────────────────────
function ContractTextViewer({ text, highlightText }: { text: string; highlightText: string | null }) {
  const containerRef = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    if (!containerRef.current || !highlightText) return

    // Clear previous highlights
    containerRef.current.querySelectorAll('mark.clause-hl').forEach((el) => {
      const parent = el.parentNode
      if (parent) {
        parent.replaceChild(document.createTextNode(el.textContent || ''), el)
        parent.normalize()
      }
    })

    const normalized = highlightText.toLowerCase().replace(/\s+/g, ' ').trim()
    if (normalized.length < 10) return

    // Try progressively shorter prefixes
    const prefixes = [normalized.length, 300, 150, 80, 40].map((n) =>
      normalized.substring(0, Math.min(n, normalized.length))
    )

    const walker = document.createTreeWalker(containerRef.current, NodeFilter.SHOW_TEXT)
    let fullText = ''
    const nodes: { node: Text; start: number; end: number }[] = []
    let node: Text | null
    while ((node = walker.nextNode() as Text | null)) {
      const start = fullText.length
      fullText += node.textContent || ''
      nodes.push({ node, start, end: fullText.length })
    }

    const normalizedFull = fullText.toLowerCase().replace(/\s+/g, ' ')

    let matchStart = -1
    let matchLen = 0
    for (const prefix of prefixes) {
      if (prefix.length < 10) continue
      const idx = normalizedFull.indexOf(prefix)
      if (idx !== -1) {
        // Try full match first
        const fullIdx = normalizedFull.indexOf(normalized)
        if (fullIdx !== -1) {
          matchStart = fullIdx
          matchLen = normalized.length
        } else {
          matchStart = idx
          matchLen = prefix.length
        }
        break
      }
    }

    if (matchStart === -1) return

    // Map normalized offsets back to raw text offsets
    let rawPos = 0
    let normPos = 0
    let rawStart = 0
    let rawEnd = fullText.length
    let lastWasSpace = false
    let foundStart = false

    for (rawPos = 0; rawPos < fullText.length && normPos <= matchStart + matchLen; rawPos++) {
      const ch = fullText[rawPos]
      if (/\s/.test(ch)) {
        if (!lastWasSpace) {
          if (normPos === matchStart && !foundStart) { rawStart = rawPos; foundStart = true }
          normPos++
          lastWasSpace = true
        }
      } else {
        if (normPos === matchStart && !foundStart) { rawStart = rawPos; foundStart = true }
        normPos++
        lastWasSpace = false
      }
      if (normPos === matchStart + matchLen) { rawEnd = rawPos + 1; break }
    }

    // Find text nodes that overlap the match range and wrap them with <mark>
    let firstMark: HTMLElement | null = null
    for (const { node: tNode, start: nStart, end: nEnd } of nodes) {
      if (nEnd <= rawStart || nStart >= rawEnd) continue
      const text = tNode.textContent || ''
      const hlStart = Math.max(0, rawStart - nStart)
      const hlEnd = Math.min(text.length, rawEnd - nStart)
      if (hlStart >= hlEnd) continue

      const before = text.substring(0, hlStart)
      const match = text.substring(hlStart, hlEnd)
      const after = text.substring(hlEnd)

      const parent = tNode.parentNode
      if (!parent) continue

      const frag = document.createDocumentFragment()
      if (before) frag.appendChild(document.createTextNode(before))
      const mark = document.createElement('mark')
      mark.className = 'clause-hl'
      mark.style.backgroundColor = 'rgba(250, 204, 21, 0.4)'
      mark.style.borderRadius = '2px'
      mark.style.padding = '1px 0'
      mark.textContent = match
      frag.appendChild(mark)
      if (after) frag.appendChild(document.createTextNode(after))

      parent.replaceChild(frag, tNode)
      if (!firstMark) firstMark = mark
    }

    if (firstMark) {
      firstMark.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [text, highlightText])

  return (
    <div className="flex flex-col h-full">
      <div className="flex-shrink-0 flex items-center px-3 py-2 bg-white border-b border-gray-200">
        <DocumentTextIcon className="h-4 w-4 text-gray-400 mr-2" />
        <span className="text-xs text-gray-600 font-medium">Extracted Text</span>
      </div>
      <div ref={containerRef} className="flex-1 overflow-y-auto p-4 text-sm text-gray-700 leading-relaxed whitespace-pre-wrap font-mono bg-white">
        {text}
      </div>
    </div>
  )
}

// ======================== MAIN PAGE ========================

export default function ExtractionQualityPage() {
  const queryClient = useQueryClient()
  const { isSuperAdmin } = useAuth()
  const [view, setView] = useState<ViewMode>('overview')
  const [selectedContractId, setSelectedContractId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'metadata' | 'clauses' | 'obligations' | 'slas'>('metadata')
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [addAsGlobal, setAddAsGlobal] = useState(false)
  const [contractSearch, setContractSearch] = useState('')
  const [showDocViewer, setShowDocViewer] = useState(true)
  const [highlightText, setHighlightText] = useState<string | null>(null)
  const [highlightPage, setHighlightPage] = useState<number | null>(null)
  const [gsPage, setGsPage] = useState(1)
  const gsPageSize = 25

  // Queries
  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ['extraction-quality-overview'],
    queryFn: () => api.getExtractionQualityOverview(),
  })

  const { data: goldenSetResponse, isLoading: goldenSetLoading } = useQuery({
    queryKey: ['golden-set-contracts', gsPage],
    queryFn: () => api.getGoldenSetContracts(gsPage, gsPageSize),
  })
  const goldenSet = goldenSetResponse?.items
  const gsTotalPages = goldenSetResponse?.pages ?? 0
  const gsTotal = goldenSetResponse?.total ?? 0

  const { data: detail, isLoading: detailLoading } = useQuery({
    queryKey: ['extraction-detail', selectedContractId],
    queryFn: () => selectedContractId ? api.getExtractionDetail(selectedContractId) : null,
    enabled: !!selectedContractId && view === 'detail',
  })

  const { data: contractsResponse } = useQuery({
    queryKey: ['contracts-for-golden-set'],
    queryFn: () => api.getContracts({ page: 1, page_size: 100 }),
    enabled: showAddDialog,
  })
  const contracts = contractsResponse?.items ?? []

  // Mutations
  const addMutation = useMutation({
    mutationFn: ({ contractId, notes, isGlobal }: { contractId: string; notes?: string; isGlobal?: boolean }) =>
      api.addToGoldenSet(contractId, notes, isGlobal),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['golden-set-contracts'] })
      queryClient.invalidateQueries({ queryKey: ['extraction-quality-overview'] })
      setShowAddDialog(false)
      setAddAsGlobal(false)
    },
  })

  const removeMutation = useMutation({
    mutationFn: ({ contractId, isGlobal }: { contractId: string; isGlobal?: boolean }) =>
      api.removeFromGoldenSet(contractId, isGlobal),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['golden-set-contracts'] })
      queryClient.invalidateQueries({ queryKey: ['extraction-quality-overview'] })
    },
  })

  const autoApproveMutation = useMutation({
    mutationFn: () => api.autoApproveAll(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['golden-set-contracts'] })
      queryClient.invalidateQueries({ queryKey: ['extraction-quality-overview'] })
    },
  })

  const verifyMutation = useMutation({
    mutationFn: (data: {
      golden_set_id: string
      entity_type: string
      entity_id: string
      status: 'correct' | 'incorrect' | 'partial'
      corrected_value?: Record<string, unknown>
      notes?: string
    }) => api.verifyExtraction(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['extraction-detail', selectedContractId] })
      queryClient.invalidateQueries({ queryKey: ['golden-set-contracts'] })
      queryClient.invalidateQueries({ queryKey: ['extraction-quality-overview'] })
    },
  })

  const openDetail = (contractId: string) => {
    setShowDocViewer(true)
    setSelectedContractId(contractId)
    setView('detail')
    setActiveTab('metadata')
  }

  const backToOverview = () => {
    setView('overview')
    setSelectedContractId(null)
  }

  const handleVerify = (entityType: string, entityId: string, status: 'correct' | 'incorrect' | 'partial', correctedValue?: Record<string, unknown>, notes?: string) => {
    if (!detail?.golden_set_id) return
    verifyMutation.mutate({
      golden_set_id: detail.golden_set_id,
      entity_type: entityType,
      entity_id: entityId,
      status,
      corrected_value: correctedValue,
      notes,
    })
  }

  const handleAddManual = (entityType: string, correctedValue: Record<string, unknown>) => {
    if (!detail?.golden_set_id) return
    const manualId = `manual_${crypto.randomUUID()}`
    verifyMutation.mutate({
      golden_set_id: detail.golden_set_id,
      entity_type: entityType,
      entity_id: manualId,
      status: 'incorrect',
      corrected_value: correctedValue,
      notes: 'Manually added — AI missed this extraction',
    })
  }

  if (overviewLoading || goldenSetLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  // ======================== DETAIL VIEW ========================
  if (view === 'detail' && selectedContractId) {
    if (detailLoading) {
      return (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size="lg" />
        </div>
      )
    }

    if (!detail) {
      return (
        <div className="p-6">
          <button onClick={backToOverview} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-4">
            <ArrowLeftIcon className="h-4 w-4" /> Back to Golden Set
          </button>
          <p className="text-gray-500">Contract not found.</p>
        </div>
      )
    }

    const tabs = [
      { key: 'metadata' as const, label: 'Metadata', count: detail.summary.metadata_total },
      { key: 'clauses' as const, label: 'Clauses', count: detail.summary.clause_count },
      { key: 'obligations' as const, label: 'Obligations', count: detail.summary.obligation_count },
      { key: 'slas' as const, label: 'SLAs', count: detail.summary.sla_count },
    ]

    const detailMimeType = /\.docx?$/i.test(detail.filename || '')
      ? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      : null

    return (
      <div className="flex flex-col h-[calc(100vh-88px)] -mx-4 sm:-mx-6 lg:-mx-8 -mt-6">
        {/* Header Bar */}
        <div className="flex-shrink-0 px-4 py-3 border-b bg-white flex items-center justify-between">
          <div className="flex items-center gap-3 min-w-0">
            <button onClick={backToOverview} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 shrink-0">
              <ArrowLeftIcon className="h-4 w-4" /> Back
            </button>
            <DocumentTextIcon className="h-5 w-5 text-violet-600 shrink-0" />
            <h1 className="text-base font-semibold text-gray-900 truncate">{detail.filename}</h1>
            {detail.is_golden && detail.is_global && (
              <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 shrink-0">
                <GlobeAltIcon className="h-3 w-3" /> Platform
              </span>
            )}
            {detail.is_golden && !detail.is_global && (
              <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 shrink-0">Golden Set</span>
            )}
          </div>
          <button
            onClick={() => setShowDocViewer(!showDocViewer)}
            className={cn(
              'flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md border transition-colors shrink-0',
              showDocViewer ? 'bg-violet-50 text-violet-700 border-violet-200' : 'bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100'
            )}
          >
            <EyeIcon className="h-4 w-4" />
            {showDocViewer ? 'Hide Document' : 'Show Document'}
          </button>
        </div>

        {/* Split Pane */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left: Document Viewer */}
          {showDocViewer && (
            <div className="w-1/2 flex-shrink-0 border-r bg-gray-50 h-full overflow-hidden flex flex-col">
              {detail.extracted_text && /\.txt$/i.test(detail.filename || '') ? (
                <ContractTextViewer
                  text={detail.extracted_text}
                  highlightText={highlightText}
                />
              ) : (
                <ContractPdfViewer
                  contractId={selectedContractId}
                  mimeType={detailMimeType}
                  highlightText={highlightText}
                  highlightPage={highlightPage}
                />
              )}
            </div>
          )}

          {/* Right: Review Panel */}
          <div className="flex-1 overflow-y-auto">
            <div className="p-4 space-y-4">
              {/* Summary Stats */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-white rounded-lg border p-3 text-center">
            <p className="text-xs text-gray-500">Metadata</p>
            <p className="text-lg font-semibold">{detail.summary.metadata_filled}/{detail.summary.metadata_total}</p>
          </div>
          <div className="bg-white rounded-lg border p-3 text-center">
            <p className="text-xs text-gray-500">Clauses</p>
            <p className="text-lg font-semibold">{detail.summary.clause_count}</p>
          </div>
          <div className="bg-white rounded-lg border p-3 text-center">
            <p className="text-xs text-gray-500">Obligations</p>
            <p className="text-lg font-semibold">{detail.summary.obligation_count}</p>
          </div>
          <div className="bg-white rounded-lg border p-3 text-center">
            <p className="text-xs text-gray-500">SLAs</p>
            <p className="text-lg font-semibold">{detail.summary.sla_count}</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200">
          <nav className="flex gap-6">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={cn(
                  'py-3 text-sm font-medium border-b-2 transition-colors',
                  activeTab === tab.key
                    ? 'border-violet-600 text-violet-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                )}
              >
                {tab.label} <span className="text-gray-400 ml-1">({tab.count})</span>
              </button>
            ))}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="bg-white rounded-lg border divide-y">
          {activeTab === 'metadata' && detail.is_golden && detail.metadata.map((item) => (
            <MetadataEditRow key={item.field} item={item} goldenSetId={detail.golden_set_id!} onVerify={handleVerify} />
          ))}
          {activeTab === 'metadata' && !detail.is_golden && detail.metadata.map((item) => (
            <div key={item.field} className="flex items-center justify-between px-4 py-3">
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-700 capitalize">{item.field.replace(/_/g, ' ')}</p>
                <p className="text-sm text-gray-500 mt-0.5">{item.value !== null && item.value !== undefined ? String(item.value) : <span className="italic text-gray-400">Not extracted</span>}</p>
              </div>
            </div>
          ))}

          {activeTab === 'clauses' && detail.is_golden && detail.clauses.map((clause: any) => (
            clause.is_manual ? (
              <div key={clause.id} className="px-4 py-3 bg-amber-50/30">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-violet-600 bg-violet-50 rounded px-1.5 py-0.5">{clause.clause_type || 'unknown'}</span>
                    {clause.risk_level && (
                      <span className={cn('text-xs rounded px-1.5 py-0.5', clause.risk_level === 'high' ? 'bg-red-50 text-red-600' : clause.risk_level === 'medium' ? 'bg-yellow-50 text-yellow-600' : 'bg-green-50 text-green-600')}>
                        {clause.risk_level} risk
                      </span>
                    )}
                    <span className="text-[10px] bg-amber-100 text-amber-700 rounded px-1.5 py-0.5">manually added</span>
                  </div>
                  {clause.verification && <VerificationBadge status={clause.verification.status} />}
                </div>
                <p className="text-sm text-gray-600 line-clamp-3">{clause.text}</p>
                {clause.verification?.notes && <p className="text-xs text-gray-400 mt-0.5 italic">{clause.verification.notes}</p>}
              </div>
            ) : (
              <ClauseEditRow key={clause.id} clause={clause} goldenSetId={detail.golden_set_id!} onVerify={handleVerify} onLocate={(text: string, page?: number | null) => { setHighlightText(text); setHighlightPage(page ?? null); }} />
            )
          ))}
          {activeTab === 'clauses' && !detail.is_golden && detail.clauses.map((clause: any) => (
            <div key={clause.id} className="px-4 py-3">
              <span className="text-xs font-medium text-violet-600 bg-violet-50 rounded px-1.5 py-0.5">{clause.clause_type || 'unknown'}</span>
              <p className="text-sm text-gray-600 mt-1 line-clamp-3">{clause.text}</p>
            </div>
          ))}
          {activeTab === 'clauses' && detail.is_golden && (
            <AddMissingClause onAdd={(val) => handleAddManual('clause', val)} />
          )}

          {activeTab === 'obligations' && detail.is_golden && detail.obligations.map((obl: any) => (
            obl.is_manual ? (
              <div key={obl.id} className="px-4 py-3 bg-amber-50/30">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-blue-600 bg-blue-50 rounded px-1.5 py-0.5">{obl.obligation_type || 'unknown'}</span>
                    {obl.obligated_party && <span className="text-xs text-gray-400">{obl.obligated_party}</span>}
                    <span className="text-[10px] bg-amber-100 text-amber-700 rounded px-1.5 py-0.5">manually added</span>
                  </div>
                  {obl.verification && <VerificationBadge status={obl.verification.status} />}
                </div>
                <p className="text-sm text-gray-600 line-clamp-2">{obl.description}</p>
                {obl.verification?.notes && <p className="text-xs text-gray-400 mt-0.5 italic">{obl.verification.notes}</p>}
              </div>
            ) : (
              <ObligationEditRow key={obl.id} obl={obl} onVerify={handleVerify} />
            )
          ))}
          {activeTab === 'obligations' && !detail.is_golden && detail.obligations.map((obl: any) => (
            <div key={obl.id} className="px-4 py-3">
              <span className="text-xs font-medium text-blue-600 bg-blue-50 rounded px-1.5 py-0.5">{obl.obligation_type || 'unknown'}</span>
              <p className="text-sm text-gray-600 mt-1 line-clamp-2">{obl.description}</p>
            </div>
          ))}
          {activeTab === 'obligations' && detail.is_golden && (
            <AddMissingObligation onAdd={(val) => handleAddManual('obligation', val)} />
          )}

          {activeTab === 'slas' && detail.is_golden && detail.slas.map((sla: any) => (
            sla.is_manual ? (
              <div key={sla.id} className="px-4 py-3 bg-amber-50/30">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-teal-600 bg-teal-50 rounded px-1.5 py-0.5">{sla.metric_type || 'SLA'}</span>
                    <span className="text-[10px] bg-amber-100 text-amber-700 rounded px-1.5 py-0.5">manually added</span>
                  </div>
                  {sla.verification && <VerificationBadge status={sla.verification.status} />}
                </div>
                <p className="text-sm text-gray-700 font-medium">{sla.sla_name}</p>
                <p className="text-sm text-gray-500">Target: {sla.target_value ?? '--'} {sla.metric_unit || ''}</p>
                {sla.verification?.notes && <p className="text-xs text-gray-400 mt-0.5 italic">{sla.verification.notes}</p>}
              </div>
            ) : (
              <SLAEditRow key={sla.id} sla={sla} onVerify={handleVerify} />
            )
          ))}
          {activeTab === 'slas' && !detail.is_golden && detail.slas.map((sla: any) => (
            <div key={sla.id} className="px-4 py-3">
              <span className="text-xs font-medium text-teal-600 bg-teal-50 rounded px-1.5 py-0.5">{sla.metric_type || 'SLA'}</span>
              <p className="text-sm text-gray-700 font-medium mt-1">{sla.sla_name}</p>
              <p className="text-sm text-gray-500">Target: {sla.target_value ?? '--'} {sla.metric_unit || ''}</p>
            </div>
          ))}
          {activeTab === 'slas' && detail.is_golden && (
            <AddMissingSLA onAdd={(val) => handleAddManual('sla', val)} />
          )}

          {activeTab === 'clauses' && detail.clauses.length === 0 && !detail.is_golden && <div className="p-8 text-center text-gray-400">No clauses extracted</div>}
          {activeTab === 'obligations' && detail.obligations.length === 0 && !detail.is_golden && <div className="p-8 text-center text-gray-400">No obligations extracted</div>}
          {activeTab === 'slas' && detail.slas.length === 0 && !detail.is_golden && <div className="p-8 text-center text-gray-400">No SLAs extracted</div>}
        </div>
        </div>
        </div>
        </div>
      </div>
    )
  }

  // ======================== OVERVIEW ========================
  const goldenContractIds = new Set((goldenSet || []).map(g => g.contract_id))

  const availableContracts = contracts.filter((c) =>
    !goldenContractIds.has(c.id) &&
    (contractSearch === '' || c.filename?.toLowerCase().includes(contractSearch.toLowerCase()) || c.counterparty?.toLowerCase().includes(contractSearch.toLowerCase()))
  )

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <AdjustmentsHorizontalIcon className="h-7 w-7 text-violet-600" />
          <div>
            <h1 className="text-xl font-semibold text-gray-900">Extraction Quality</h1>
            <p className="text-sm text-gray-500">Manage your golden set and review AI extraction accuracy</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {overview && overview.pending_review > 0 && (
            <button
              onClick={() => {
                if (confirm(`Auto-approve all ${overview.pending_review} pending extractions as correct?`)) {
                  autoApproveMutation.mutate()
                }
              }}
              disabled={autoApproveMutation.isPending}
              className="btn-secondary flex items-center gap-1.5"
            >
              <CheckCircleIcon className="h-4 w-4" />
              {autoApproveMutation.isPending ? 'Approving...' : 'Auto-Approve All'}
            </button>
          )}
          <button
            onClick={() => setShowAddDialog(true)}
            className="btn-primary flex items-center gap-1.5"
          >
            <PlusIcon className="h-4 w-4" /> Add to Golden Set
          </button>
        </div>
      </div>

      {/* Score Cards */}
      {overview && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <ScoreCard label="Overall" score={overview.avg_overall_score} />
          <ScoreCard label="Metadata" score={overview.avg_metadata_score} />
          <ScoreCard label="Clauses" score={overview.avg_clause_score} />
          <ScoreCard label="Obligations" score={overview.avg_obligation_score} />
          <ScoreCard label="SLAs" score={overview.avg_sla_score} />
        </div>
      )}

      {/* Summary Stats */}
      {overview && (
        <div className="flex gap-6 text-sm text-gray-500">
          <span><strong className="text-gray-900">{overview.total_golden}</strong> golden contracts</span>
          {overview.total_global > 0 && (
            <span><strong className="text-blue-600">{overview.total_global}</strong> platform</span>
          )}
          {overview.total_tenant > 0 && (
            <span><strong className="text-amber-600">{overview.total_tenant}</strong> tenant</span>
          )}
          <span><strong className="text-green-600">{overview.verified}</strong> verified</span>
          <span><strong className="text-amber-600">{overview.pending_review}</strong> pending review</span>
        </div>
      )}

      {/* Golden Set Contracts List */}
      <div className="bg-white rounded-lg border">
        <div className="px-4 py-3 border-b">
          <h2 className="text-sm font-semibold text-gray-700">Golden Set Contracts</h2>
        </div>
        {(!goldenSet || goldenSet.length === 0) ? (
          <div className="p-8 text-center text-gray-400">
            <DocumentTextIcon className="h-10 w-10 mx-auto mb-2 text-gray-300" />
            <p>No contracts in the golden set yet.</p>
            <p className="text-xs mt-1">Add contracts to start tracking extraction quality.</p>
          </div>
        ) : (
          <div className="divide-y">
            {goldenSet.map((item) => (
              <div key={item.id} className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors">
                <button
                  onClick={() => openDetail(item.contract_id)}
                  className="flex-1 text-left"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-gray-900 truncate">{item.filename}</p>
                        {item.is_global && (
                          <span className="inline-flex items-center gap-0.5 rounded-full bg-blue-100 px-1.5 py-0.5 text-[10px] font-medium text-blue-700 shrink-0">
                            <GlobeAltIcon className="h-3 w-3" /> Platform
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-0.5 text-xs text-gray-500">
                        {item.contract_type && <span className="capitalize">{item.contract_type}</span>}
                        {item.counterparty && <span>{item.counterparty}</span>}
                        <span>{item.extraction.clause_count} clauses</span>
                        <span>{item.extraction.obligation_count} obls</span>
                        <span>{item.extraction.sla_count} SLAs</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <div className="flex items-center gap-1 text-xs">
                        <span className="text-green-600">{item.verification.correct}</span>/
                        <span className="text-red-600">{item.verification.incorrect}</span>/
                        <span className="text-yellow-600">{item.verification.partial}</span>/
                        <span className="text-gray-400">{item.verification.pending}</span>
                      </div>
                      <div className={cn('text-sm font-semibold w-14 text-right', SCORE_COLORS(item.scores.overall))}>
                        {item.scores.overall !== null ? `${item.scores.overall}%` : '--'}
                      </div>
                      <ChevronRightIcon className="h-4 w-4 text-gray-400" />
                    </div>
                  </div>
                </button>
                {/* Only allow removing global entries if super admin, always allow removing tenant entries */}
                {(isSuperAdmin || !item.is_global) && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      const label = item.is_global ? 'Remove this platform-wide contract from the golden set?' : 'Remove this contract from the golden set?'
                      if (confirm(label)) {
                        removeMutation.mutate({ contractId: item.contract_id, isGlobal: item.is_global })
                      }
                    }}
                    className="ml-2 p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500"
                    title={item.is_global ? 'Remove from platform golden set' : 'Remove from golden set'}
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
        {/* Pagination */}
        {gsTotalPages > 1 && (
          <div className="px-4 py-3 border-t flex items-center justify-between">
            <span className="text-xs text-gray-500">
              Showing {(gsPage - 1) * gsPageSize + 1}–{Math.min(gsPage * gsPageSize, gsTotal)} of {gsTotal}
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setGsPage((p) => Math.max(1, p - 1))}
                disabled={gsPage <= 1}
                className="px-2 py-1 text-xs rounded border hover:bg-gray-50 disabled:opacity-30"
              >
                Prev
              </button>
              {Array.from({ length: Math.min(7, gsTotalPages) }, (_, i) => {
                let p: number
                if (gsTotalPages <= 7) {
                  p = i + 1
                } else if (gsPage <= 4) {
                  p = i + 1
                } else if (gsPage >= gsTotalPages - 3) {
                  p = gsTotalPages - 6 + i
                } else {
                  p = gsPage - 3 + i
                }
                return (
                  <button
                    key={p}
                    onClick={() => setGsPage(p)}
                    className={cn(
                      'px-2 py-1 text-xs rounded border',
                      p === gsPage ? 'bg-violet-600 text-white border-violet-600' : 'hover:bg-gray-50'
                    )}
                  >
                    {p}
                  </button>
                )
              })}
              <button
                onClick={() => setGsPage((p) => Math.min(gsTotalPages, p + 1))}
                disabled={gsPage >= gsTotalPages}
                className="px-2 py-1 text-xs rounded border hover:bg-gray-50 disabled:opacity-30"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Add to Golden Set Dialog */}
      {showAddDialog && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4" onClick={() => { setShowAddDialog(false); setAddAsGlobal(false) }}>
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full max-h-[70vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="px-5 py-4 border-b">
              <h3 className="text-lg font-semibold text-gray-900">Add Contract to Golden Set</h3>
              <p className="text-sm text-gray-500 mt-0.5">
                {addAsGlobal
                  ? 'Adding as platform-wide — all tenants will benefit from this'
                  : 'Select a contract to include in your quality benchmark'}
              </p>
            </div>
            <div className="px-5 py-3 border-b space-y-2">
              <input
                type="text"
                placeholder="Search contracts..."
                value={contractSearch}
                onChange={(e) => setContractSearch(e.target.value)}
                className="input w-full"
              />
              {isSuperAdmin && (
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={addAsGlobal}
                    onChange={(e) => setAddAsGlobal(e.target.checked)}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <GlobeAltIcon className="h-4 w-4 text-blue-600" />
                  <span className="text-gray-700">Add as platform-wide (benefits all tenants)</span>
                </label>
              )}
            </div>
            <div className="flex-1 overflow-y-auto divide-y">
              {availableContracts.length === 0 ? (
                <div className="p-6 text-center text-gray-400 text-sm">
                  {contractsResponse ? 'No matching contracts found' : <LoadingSpinner size="sm" />}
                </div>
              ) : (
                availableContracts.slice(0, 20).map((contract) => (
                  <button
                    key={contract.id}
                    onClick={() => addMutation.mutate({ contractId: contract.id, isGlobal: addAsGlobal })}
                    disabled={addMutation.isPending}
                    className="w-full text-left px-5 py-3 hover:bg-violet-50 transition-colors disabled:opacity-50"
                  >
                    <p className="text-sm font-medium text-gray-900 truncate">{contract.filename}</p>
                    <div className="flex items-center gap-3 text-xs text-gray-500 mt-0.5">
                      {contract.contract_type && <span className="capitalize">{contract.contract_type}</span>}
                      {contract.counterparty && <span>{contract.counterparty}</span>}
                      {contract.status && <span className="capitalize">{contract.status}</span>}
                    </div>
                  </button>
                ))
              )}
            </div>
            <div className="px-5 py-3 border-t bg-gray-50 rounded-b-xl">
              <button onClick={() => { setShowAddDialog(false); setAddAsGlobal(false) }} className="btn-secondary w-full">Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
