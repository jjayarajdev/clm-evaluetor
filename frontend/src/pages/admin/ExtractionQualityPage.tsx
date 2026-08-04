/* Extraction Quality admin — Direction B restyle.
   Token design system (var(--p)/--ok/--wa/--da, .card .banner .tabs .kbd …) and
   '@/components/ui' primitives (Stat, Pill, Confidence, Chip, Drawer,
   ConfirmDialog, EmptyState, Button, IconButton, Checkbox, Switch, Field, AiTag).
   Queries, mutations, filters, drill-downs, keyboard review flow, permission
   checks, i18n keys and routes are unchanged from the pre-redesign page. */
import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams, Link } from 'react-router-dom'
import {
  CheckCircleIcon,
  XCircleIcon,
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
  FunnelIcon,
  SparklesIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import {
  getDspyCompilationStatus,
  compileDspyPrograms,
  getDspyAutoRecompileConfig,
  updateDspyAutoRecompileConfig,
  type DspyAgentType,
} from '@/lib/api/admin'
import { useAuth } from '@/contexts/AuthContext'
import { useTranslation } from 'react-i18next'
import i18n from '@/i18n'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import ContractPdfViewer from '@/components/contracts/ContractPdfViewer'
import {
  AiTag,
  Button,
  Checkbox,
  Chip,
  Confidence,
  ConfirmDialog,
  Drawer,
  EmptyState,
  Field,
  IconButton,
  Pill,
  Stat,
  Switch,
} from '@/components/ui'
import type { PillTone } from '@/components/ui'
import { cn } from '@/lib/utils'

type ViewMode = 'overview' | 'detail'

/** Accuracy score tone: >=90 ok, >=70 warn, <70 danger, null neutral. */
const scoreTone = (score: number | null) =>
  score === null ? 'var(--f)' : score >= 90 ? 'var(--ok)' : score >= 70 ? 'var(--wa)' : 'var(--da)'

const VERIF_TONE: Record<string, PillTone> = {
  correct: 'ok',
  incorrect: 'da',
  partial: 'wa',
  pending: 'n',
}

const RISK_TONE: Record<string, PillTone> = { high: 'da', medium: 'wa', low: 'ok' }

function ScoreCard({ label, score }: { label: string; score: number | null }) {
  return (
    <Stat
      label={label}
      value={
        <span style={{ color: scoreTone(score) }}>
          {score !== null ? `${score}%` : '--'}
        </span>
      }
    />
  )
}

function VerificationBadge({ status }: { status: string | null }) {
  const { t } = useTranslation()
  if (!status) return null
  return (
    <Pill tone={VERIF_TONE[status] || 'n'}>
      {status === 'pending' ? t('status.pending') : t(`extraction.verifStatus.${status}`, { defaultValue: status })}
    </Pill>
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
  const { t } = useTranslation()
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
      <div className="px-4 py-3" style={{ background: 'var(--p-f)' }}>
        <div className="flex items-center justify-between mb-2">
          <p className="capitalize" style={{ fontWeight: 500 }}>{item.field.replace(/_/g, ' ')}</p>
          <IconButton size="sm" icon={XMarkIcon} label={t('common.cancel')} onClick={() => setEditing(false)} />
        </div>
        <div className="space-y-2">
          <div>
            <label className="lbl">{t('extraction.original', { value: item.value !== null ? String(item.value) : t('extraction.empty') })}</label>
            <input
              type="text"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              className="input w-full"
              placeholder={t('extraction.correctedValuePlaceholder')}
              autoFocus
            />
          </div>
          <input
            type="text"
            value={editNotes}
            onChange={(e) => setEditNotes(e.target.value)}
            className="input w-full"
            placeholder={t('extraction.notesOptionalPlaceholder')}
          />
          <div className="row">
            <Button size="sm" style={{ background: 'var(--da-f)', borderColor: 'var(--da-b)', color: 'var(--da)' }} onClick={() => saveEdit('incorrect')}>
              {t('extraction.saveAsIncorrect')}
            </Button>
            <Button size="sm" style={{ background: 'var(--wa-f)', borderColor: 'var(--wa-b)', color: 'var(--wa)' }} onClick={() => saveEdit('partial')}>
              {t('extraction.saveAsPartial')}
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setEditing(false)}>{t('common.cancel')}</Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-between px-4 py-3">
      <div className="flex-1 min-w-0">
        <p className="capitalize" style={{ fontWeight: 500 }}>{item.field.replace(/_/g, ' ')}</p>
        <p className="muted mt-0.5">
          {displayValue !== null ? displayValue : <span className="italic faint">{t('extraction.notExtracted')}</span>}
        </p>
        {corrected && (
          <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--p)', marginTop: 2 }}>{t('extraction.correctedFrom', { value: item.value !== null ? String(item.value) : t('extraction.empty') })}</p>
        )}
        {item.verification?.notes && (
          <p className="faint italic" style={{ fontSize: 'var(--fs-xs)', marginTop: 2 }}>{item.verification.notes}</p>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {item.verification && <VerificationBadge status={item.verification.status} />}
        <div className="row ml-1" style={{ gap: 2 }}>
          <IconButton icon={CheckCircleIcon} label={t('extraction.markCorrect')} onClick={() => onVerify('metadata_field', item.field, 'correct')} />
          <IconButton icon={PencilSquareIcon} label={t('extraction.editAndCorrect')} onClick={startEdit} />
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
  const { t } = useTranslation()
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
      <div className="px-4 py-3" style={{ background: 'var(--p-f)' }}>
        <div className="flex items-center justify-between mb-2">
          <span style={{ fontSize: 'var(--fs-xs)', fontWeight: 600, color: 'var(--p)' }}>{t('extraction.editClause')}</span>
          <IconButton size="sm" icon={XMarkIcon} label={t('common.cancel')} onClick={() => setEditing(false)} />
        </div>
        <div className="space-y-2">
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="lbl">{t('extraction.clauseType')}</label>
              <input type="text" value={editType} onChange={(e) => setEditType(e.target.value)} className="input w-full" placeholder={t('extraction.clauseTypePlaceholder')} />
            </div>
            <div className="w-32">
              <label className="lbl">{t('extraction.riskLevel')}</label>
              <select value={editRisk} onChange={(e) => setEditRisk(e.target.value)} className="input w-full">
                <option value="">--</option>
                <option value="low">{t('risk.low')}</option>
                <option value="medium">{t('risk.medium')}</option>
                <option value="high">{t('risk.high')}</option>
              </select>
            </div>
          </div>
          <div>
            <label className="lbl">{t('extraction.text')}</label>
            <textarea value={editText} onChange={(e) => setEditText(e.target.value)} rows={3} className="input w-full" />
          </div>
          <input type="text" value={editNotes} onChange={(e) => setEditNotes(e.target.value)} className="input w-full" placeholder={t('extraction.notesPlaceholder')} />
          <div className="row">
            <Button size="sm" style={{ background: 'var(--da-f)', borderColor: 'var(--da-b)', color: 'var(--da)' }} onClick={() => saveEdit('incorrect')}>{t('extraction.saveAsIncorrect')}</Button>
            <Button size="sm" style={{ background: 'var(--wa-f)', borderColor: 'var(--wa-b)', color: 'var(--wa)' }} onClick={() => saveEdit('partial')}>{t('extraction.saveAsPartial')}</Button>
            <Button size="sm" variant="secondary" onClick={() => setEditing(false)}>{t('common.cancel')}</Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="px-4 py-3">
      <div className="flex items-center justify-between mb-1">
        <div className="row">
          <Pill tone="p" dot={false}>{displayType || t('extraction.unknown')}</Pill>
          {clause.risk_level && (
            <Pill tone={RISK_TONE[clause.risk_level] || 'n'} dot={false}>
              {t('extraction.riskSuffix', { level: t(`risk.${clause.risk_level}`, { defaultValue: clause.risk_level }) })}
            </Pill>
          )}
          {clause.confidence !== null && <Confidence value={clause.confidence} />}
        </div>
        <div className="row">
          {clause.verification && <VerificationBadge status={clause.verification.status} />}
          <div className="row" style={{ gap: 2 }}>
            <IconButton size="sm" icon={CheckCircleIcon} label={t('extraction.markCorrect')} onClick={() => onVerify('clause', clause.id, 'correct')} />
            <IconButton size="sm" icon={PencilSquareIcon} label={t('common.edit')} onClick={startEdit} />
            {onLocate && clause.text && (
              <IconButton size="sm" icon={EyeIcon} label={t('extraction.locateInDocument')} onClick={() => onLocate(clause.text!, clause.page_number)} />
            )}
          </div>
        </div>
      </div>
      <p className="muted line-clamp-3">{displayText}</p>
      {corrected && <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--p)', marginTop: 4 }}>{t('extraction.corrected')}</p>}
      {clause.verification?.notes && <p className="faint italic" style={{ fontSize: 'var(--fs-xs)', marginTop: 2 }}>{clause.verification.notes}</p>}
      {clause.section_number && <p className="faint" style={{ fontSize: 'var(--fs-xs)', marginTop: 4 }}>{clause.page_number ? t('extraction.sectionPage', { section: clause.section_number, page: clause.page_number }) : t('extraction.sectionOnly', { section: clause.section_number })}</p>}
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
  const { t } = useTranslation()
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
      <div className="px-4 py-3" style={{ background: 'var(--p-f)' }}>
        <div className="flex items-center justify-between mb-2">
          <span style={{ fontSize: 'var(--fs-xs)', fontWeight: 600, color: 'var(--p)' }}>{t('extraction.editObligation')}</span>
          <IconButton size="sm" icon={XMarkIcon} label={t('common.cancel')} onClick={() => setEditing(false)} />
        </div>
        <div className="space-y-2">
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="lbl">{t('extraction.type')}</label>
              <input type="text" value={editType} onChange={(e) => setEditType(e.target.value)} className="input w-full" />
            </div>
            <div className="flex-1">
              <label className="lbl">{t('extraction.obligatedParty')}</label>
              <input type="text" value={editParty} onChange={(e) => setEditParty(e.target.value)} className="input w-full" />
            </div>
          </div>
          <div>
            <label className="lbl">{t('extraction.description')}</label>
            <textarea value={editDesc} onChange={(e) => setEditDesc(e.target.value)} rows={2} className="input w-full" />
          </div>
          <input type="text" value={editNotes} onChange={(e) => setEditNotes(e.target.value)} className="input w-full" placeholder={t('extraction.notesPlaceholder')} />
          <div className="row">
            <Button size="sm" style={{ background: 'var(--da-f)', borderColor: 'var(--da-b)', color: 'var(--da)' }} onClick={() => saveEdit('incorrect')}>{t('extraction.saveAsIncorrect')}</Button>
            <Button size="sm" style={{ background: 'var(--wa-f)', borderColor: 'var(--wa-b)', color: 'var(--wa)' }} onClick={() => saveEdit('partial')}>{t('extraction.saveAsPartial')}</Button>
            <Button size="sm" variant="secondary" onClick={() => setEditing(false)}>{t('common.cancel')}</Button>
          </div>
        </div>
      </div>
    )
  }

  const displayDesc = (corrected?.description as string) || obl.description

  return (
    <div className="px-4 py-3">
      <div className="flex items-center justify-between mb-1">
        <div className="row">
          <Pill tone="in" dot={false}>{obl.obligation_type || t('extraction.unknown')}</Pill>
          {obl.is_critical && <Pill tone="da" dot={false}>{t('risk.critical')}</Pill>}
          {obl.obligated_party && <span className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{obl.obligated_party}</span>}
        </div>
        <div className="row">
          {obl.verification && <VerificationBadge status={obl.verification.status} />}
          <div className="row" style={{ gap: 2 }}>
            <IconButton size="sm" icon={CheckCircleIcon} label={t('extraction.markCorrect')} onClick={() => onVerify('obligation', obl.id, 'correct')} />
            <IconButton size="sm" icon={PencilSquareIcon} label={t('common.edit')} onClick={startEdit} />
          </div>
        </div>
      </div>
      <p className="muted line-clamp-2">{displayDesc}</p>
      {corrected && <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--p)', marginTop: 4 }}>{t('extraction.corrected')}</p>}
      {obl.verification?.notes && <p className="faint italic" style={{ fontSize: 'var(--fs-xs)', marginTop: 2 }}>{obl.verification.notes}</p>}
      {obl.deadline && <p className="faint" style={{ fontSize: 'var(--fs-xs)', marginTop: 4 }}>{t('extraction.deadline', { deadline: obl.deadline, type: obl.deadline_type })}</p>}
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
  const { t } = useTranslation()
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
      <div className="px-4 py-3" style={{ background: 'var(--p-f)' }}>
        <div className="flex items-center justify-between mb-2">
          <span style={{ fontSize: 'var(--fs-xs)', fontWeight: 600, color: 'var(--p)' }}>{t('extraction.editSla')}</span>
          <IconButton size="sm" icon={XMarkIcon} label={t('common.cancel')} onClick={() => setEditing(false)} />
        </div>
        <div className="space-y-2">
          <div>
            <label className="lbl">{t('extraction.slaName')}</label>
            <input type="text" value={editName} onChange={(e) => setEditName(e.target.value)} className="input w-full" />
          </div>
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="lbl">{t('extraction.targetValue')}</label>
              <input type="number" step="any" value={editTarget} onChange={(e) => setEditTarget(e.target.value)} className="input w-full" />
            </div>
            <div className="flex-1">
              <label className="lbl">{t('extraction.unit')}</label>
              <input type="text" value={editUnit} onChange={(e) => setEditUnit(e.target.value)} className="input w-full" placeholder={t('extraction.unitExamplePlaceholder')} />
            </div>
          </div>
          <input type="text" value={editNotes} onChange={(e) => setEditNotes(e.target.value)} className="input w-full" placeholder={t('extraction.notesPlaceholder')} />
          <div className="row">
            <Button size="sm" style={{ background: 'var(--da-f)', borderColor: 'var(--da-b)', color: 'var(--da)' }} onClick={() => saveEdit('incorrect')}>{t('extraction.saveAsIncorrect')}</Button>
            <Button size="sm" style={{ background: 'var(--wa-f)', borderColor: 'var(--wa-b)', color: 'var(--wa)' }} onClick={() => saveEdit('partial')}>{t('extraction.saveAsPartial')}</Button>
            <Button size="sm" variant="secondary" onClick={() => setEditing(false)}>{t('common.cancel')}</Button>
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
        <div className="row">
          <Pill tone="p" dot={false}>{sla.metric_type || 'SLA'}</Pill>
          {sla.severity && (
            <Pill tone={sla.severity === 'critical' ? 'da' : sla.severity === 'major' ? 'wa' : 'n'} dot={false}>
              {t(`extraction.severity.${sla.severity}`, { defaultValue: sla.severity })}
            </Pill>
          )}
        </div>
        <div className="row">
          {sla.verification && <VerificationBadge status={sla.verification.status} />}
          <div className="row" style={{ gap: 2 }}>
            <IconButton size="sm" icon={CheckCircleIcon} label={t('extraction.markCorrect')} onClick={() => onVerify('sla', sla.id, 'correct')} />
            <IconButton size="sm" icon={PencilSquareIcon} label={t('common.edit')} onClick={startEdit} />
          </div>
        </div>
      </div>
      <p style={{ fontWeight: 500 }}>{displayName}</p>
      <p className="muted">
        {t('extraction.target', { value: displayTarget !== null ? displayTarget : '--', unit: sla.metric_unit || '' })}
        {sla.has_penalty && sla.penalty_value && <span className="ml-2" style={{ color: 'var(--da)' }}>{t('extraction.penalty', { value: sla.penalty_value })}</span>}
      </p>
      {corrected && <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--p)', marginTop: 4 }}>{t('extraction.corrected')}</p>}
      {sla.verification?.notes && <p className="faint italic" style={{ fontSize: 'var(--fs-xs)', marginTop: 2 }}>{sla.verification.notes}</p>}
    </div>
  )
}

// ======================== ADD MISSING ITEM FORMS ========================

function AddMissingClause({ onAdd }: { onAdd: (correctedValue: Record<string, unknown>) => void }) {
  const { t } = useTranslation()
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
      <button onClick={() => setOpen(true)} className="w-full px-4 py-3 flex items-center gap-1.5 transition-colors hover:bg-[var(--p-f)]" style={{ color: 'var(--p)', fontWeight: 500 }}>
        <PlusIcon className="h-4 w-4" /> {t('extraction.addMissingClause')}
      </button>
    )
  }

  return (
    <div className="px-4 py-3" style={{ background: 'var(--p-f)' }}>
      <div className="flex items-center justify-between mb-2">
        <span style={{ fontSize: 'var(--fs-xs)', fontWeight: 600, color: 'var(--p)' }}>{t('extraction.addMissingClauseTitle')}</span>
        <IconButton size="sm" icon={XMarkIcon} label={t('common.cancel')} onClick={() => setOpen(false)} />
      </div>
      <div className="space-y-2">
        <div className="flex gap-2">
          <div className="flex-1">
            <label className="lbl">{t('extraction.clauseType')} *</label>
            <input type="text" value={clauseType} onChange={(e) => setClauseType(e.target.value)} className="input w-full" placeholder={t('extraction.clauseTypePlaceholder')} autoFocus />
          </div>
          <div className="w-32">
            <label className="lbl">{t('extraction.riskLevel')}</label>
            <select value={riskLevel} onChange={(e) => setRiskLevel(e.target.value)} className="input w-full">
              <option value="">--</option>
              <option value="low">{t('risk.low')}</option>
              <option value="medium">{t('risk.medium')}</option>
              <option value="high">{t('risk.high')}</option>
            </select>
          </div>
        </div>
        <div>
          <label className="lbl">{t('extraction.clauseText')} *</label>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} className="input w-full" placeholder={t('extraction.pasteClauseTextPlaceholder')} />
        </div>
        <div className="row">
          <Button size="sm" variant="primary" disabled={!clauseType || !text} onClick={handleSubmit}>{t('extraction.addToGoldenSet')}</Button>
          <Button size="sm" variant="secondary" onClick={() => setOpen(false)}>{t('common.cancel')}</Button>
        </div>
      </div>
    </div>
  )
}

function AddMissingObligation({ onAdd }: { onAdd: (correctedValue: Record<string, unknown>) => void }) {
  const { t } = useTranslation()
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
      <button onClick={() => setOpen(true)} className="w-full px-4 py-3 flex items-center gap-1.5 transition-colors hover:bg-[var(--p-f)]" style={{ color: 'var(--p)', fontWeight: 500 }}>
        <PlusIcon className="h-4 w-4" /> {t('extraction.addMissingObligation')}
      </button>
    )
  }

  return (
    <div className="px-4 py-3" style={{ background: 'var(--p-f)' }}>
      <div className="flex items-center justify-between mb-2">
        <span style={{ fontSize: 'var(--fs-xs)', fontWeight: 600, color: 'var(--p)' }}>{t('extraction.addMissingObligationTitle')}</span>
        <IconButton size="sm" icon={XMarkIcon} label={t('common.cancel')} onClick={() => setOpen(false)} />
      </div>
      <div className="space-y-2">
        <div className="flex gap-2">
          <div className="flex-1">
            <label className="lbl">{t('extraction.obligationType')} *</label>
            <input type="text" value={oblType} onChange={(e) => setOblType(e.target.value)} className="input w-full" placeholder={t('extraction.obligationTypePlaceholder')} autoFocus />
          </div>
          <div className="flex-1">
            <label className="lbl">{t('extraction.obligatedParty')}</label>
            <input type="text" value={party} onChange={(e) => setParty(e.target.value)} className="input w-full" placeholder={t('extraction.obligatedPartyPlaceholder')} />
          </div>
        </div>
        <div>
          <label className="lbl">{t('extraction.description')} *</label>
          <textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={2} className="input w-full" placeholder={t('extraction.describeObligationPlaceholder')} />
        </div>
        <div className="row">
          <Button size="sm" variant="primary" disabled={!oblType || !desc} onClick={handleSubmit}>{t('extraction.addToGoldenSet')}</Button>
          <Button size="sm" variant="secondary" onClick={() => setOpen(false)}>{t('common.cancel')}</Button>
        </div>
      </div>
    </div>
  )
}

function AddMissingSLA({ onAdd }: { onAdd: (correctedValue: Record<string, unknown>) => void }) {
  const { t } = useTranslation()
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
      <button onClick={() => setOpen(true)} className="w-full px-4 py-3 flex items-center gap-1.5 transition-colors hover:bg-[var(--p-f)]" style={{ color: 'var(--p)', fontWeight: 500 }}>
        <PlusIcon className="h-4 w-4" /> {t('extraction.addMissingSla')}
      </button>
    )
  }

  return (
    <div className="px-4 py-3" style={{ background: 'var(--p-f)' }}>
      <div className="flex items-center justify-between mb-2">
        <span style={{ fontSize: 'var(--fs-xs)', fontWeight: 600, color: 'var(--p)' }}>{t('extraction.addMissingSlaTitle')}</span>
        <IconButton size="sm" icon={XMarkIcon} label={t('common.cancel')} onClick={() => setOpen(false)} />
      </div>
      <div className="space-y-2">
        <div>
          <label className="lbl">{t('extraction.slaName')} *</label>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} className="input w-full" placeholder={t('extraction.slaNamePlaceholder')} autoFocus />
        </div>
        <div className="flex gap-2">
          <div className="flex-1">
            <label className="lbl">{t('extraction.metricType')}</label>
            <input type="text" value={metricType} onChange={(e) => setMetricType(e.target.value)} className="input w-full" placeholder={t('extraction.metricTypePlaceholder')} />
          </div>
          <div className="w-28">
            <label className="lbl">{t('extraction.targetLabel')}</label>
            <input type="number" step="any" value={target} onChange={(e) => setTarget(e.target.value)} className="input w-full" placeholder="99.9" />
          </div>
          <div className="w-28">
            <label className="lbl">{t('extraction.unit')}</label>
            <input type="text" value={unit} onChange={(e) => setUnit(e.target.value)} className="input w-full" placeholder={t('extraction.unitPlaceholder')} />
          </div>
        </div>
        <div className="row">
          <Button size="sm" variant="primary" disabled={!name} onClick={handleSubmit}>{t('extraction.addToGoldenSet')}</Button>
          <Button size="sm" variant="secondary" onClick={() => setOpen(false)}>{t('common.cancel')}</Button>
        </div>
      </div>
    </div>
  )
}

// ─── Text Viewer for CUAD .txt contracts ────────────────────────────
function ContractTextViewer({ text, highlightText }: { text: string; highlightText: string | null }) {
  const { t } = useTranslation()
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
      mark.style.backgroundColor = 'var(--wa-b)'
      mark.style.color = 'inherit'
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
      <div className="flex-shrink-0 flex items-center px-3 py-2" style={{ background: 'var(--s)', borderBottom: '1px solid var(--b)' }}>
        <DocumentTextIcon className="h-4 w-4 mr-2" style={{ color: 'var(--f)' }} />
        <span className="muted" style={{ fontSize: 'var(--fs-xs)', fontWeight: 500 }}>{t('extraction.extractedText')}</span>
      </div>
      <div ref={containerRef} className="flex-1 overflow-y-auto p-4 leading-relaxed whitespace-pre-wrap mono" style={{ background: 'var(--s)', fontSize: 'var(--fs-sm)' }}>
        {text}
      </div>
    </div>
  )
}

// ======================== DSPY COMPILATION PANEL ========================

const DSPY_AGENT_LABELS: Record<DspyAgentType, string> = {
  metadata: 'Metadata',
  clause: 'Clauses',
  obligation: 'Obligations',
  sla: 'SLAs',
}
const DSPY_AGENT_ORDER: DspyAgentType[] = ['metadata', 'clause', 'obligation', 'sla']

function formatRelativeTime(epochSeconds: number | undefined): string {
  if (!epochSeconds) return '—'
  const diffSec = Math.floor(Date.now() / 1000 - epochSeconds)
  if (diffSec < 60) return i18n.t('extraction.justNow')
  if (diffSec < 3600) return i18n.t('extraction.minutesAgo', { value: Math.floor(diffSec / 60) })
  if (diffSec < 86400) return i18n.t('extraction.hoursAgo', { value: Math.floor(diffSec / 3600) })
  if (diffSec < 86400 * 30) return i18n.t('extraction.daysAgo', { value: Math.floor(diffSec / 86400) })
  return i18n.t('extraction.monthsAgo', { value: Math.floor(diffSec / (86400 * 30)) })
}

function DspyCompilationPanel() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [pendingAgent, setPendingAgent] = useState<DspyAgentType | 'all' | null>(null)
  const [resultMessage, setResultMessage] = useState<string | null>(null)
  const [resultIsError, setResultIsError] = useState(false)
  const [editingThreshold, setEditingThreshold] = useState<number | null>(null)
  const [showCompileAllConfirm, setShowCompileAllConfirm] = useState(false)

  const { data: status, isLoading } = useQuery({
    queryKey: ['dspy-compilation-status'],
    queryFn: getDspyCompilationStatus,
  })

  const { data: autoConfig } = useQuery({
    queryKey: ['dspy-auto-recompile-config'],
    queryFn: getDspyAutoRecompileConfig,
  })

  const autoConfigMutation = useMutation({
    mutationFn: updateDspyAutoRecompileConfig,
    onSuccess: () => {
      setEditingThreshold(null)
      queryClient.invalidateQueries({ queryKey: ['dspy-auto-recompile-config'] })
    },
  })

  const compileMutation = useMutation({
    mutationFn: (agentTypes: DspyAgentType[] | undefined) => compileDspyPrograms(agentTypes),
    onSuccess: (resp) => {
      const lines: string[] = []
      let anyError = false
      for (const [agent, r] of Object.entries(resp.results || {})) {
        const agentLabel = t(`extraction.agents.${agent}`, { defaultValue: DSPY_AGENT_LABELS[agent as DspyAgentType] || agent })
        if (r.status === 'compiled') {
          lines.push(t('extraction.compiledWithExamples', { agent: agentLabel, count: r.examples ?? 0 }))
        } else if (r.status === 'skipped') {
          lines.push(`${agentLabel}: ${r.message}`)
        } else if (r.status === 'in_progress') {
          lines.push(t('extraction.alreadyCompiling', { agent: agentLabel }))
        } else {
          lines.push(`${agentLabel}: ${r.message || t('status.failed')}`)
          anyError = true
        }
      }
      setResultMessage(lines.join(' · '))
      setResultIsError(anyError)
      setPendingAgent(null)
      queryClient.invalidateQueries({ queryKey: ['dspy-compilation-status'] })
    },
    onError: (err: any) => {
      setResultMessage(err?.response?.data?.detail || err?.message || t('extraction.compilationFailed'))
      setResultIsError(true)
      setPendingAgent(null)
    },
  })

  const handleCompileOne = (agent: DspyAgentType) => {
    setResultMessage(null)
    setPendingAgent(agent)
    compileMutation.mutate([agent])
  }

  const handleCompileAll = () => {
    setShowCompileAllConfirm(true)
  }

  const confirmCompileAll = () => {
    setShowCompileAllConfirm(false)
    setResultMessage(null)
    setPendingAgent('all')
    compileMutation.mutate(undefined)
  }

  const anyPending = pendingAgent !== null

  return (
    <div className="card">
      <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: '1px solid var(--b)' }}>
        <div className="row min-w-0">
          <AiTag />
          <h2 style={{ fontWeight: 600 }}>{t('extraction.promptOptimization')}</h2>
          <span className="faint trunc" style={{ fontSize: 'var(--fs-xs)' }} title={t('extraction.dspyTooltip')}>
            {t('extraction.compilesFromGoldenSet')}
          </span>
        </div>
        <Button
          size="sm"
          variant="secondary"
          onClick={handleCompileAll}
          disabled={anyPending}
          style={!anyPending ? { background: 'var(--p-f)', borderColor: 'var(--p-b)', color: 'var(--p)' } : undefined}
        >
          {pendingAgent === 'all' ? (
            <>
              <ArrowPathIcon className="h-3.5 w-3.5 spin" />
              {t('extraction.compiling')}
            </>
          ) : (
            <>
              <SparklesIcon className="h-3.5 w-3.5" />
              {t('extraction.compileAll')}
            </>
          )}
        </Button>
      </div>

      {isLoading ? (
        <div className="p-6 flex justify-center"><LoadingSpinner size="sm" /></div>
      ) : (
        <div className="divide-y divide-[var(--b)]">
          {DSPY_AGENT_ORDER.map((agent) => {
            const s = status?.programs?.[agent]
            const compiled = s?.compiled === true
            const compiledAt = s?.compiled_at
            const sizeKb = s?.size_bytes ? Math.round(s.size_bytes / 1024) : null
            const isPending = pendingAgent === agent || pendingAgent === 'all'
            return (
              <div key={agent} className="px-4 py-3 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <Pill tone={compiled ? 'ok' : 'n'}>
                    {compiled ? t('extraction.compiled') : t('extraction.defaults')}
                  </Pill>
                  <span className="min-w-[80px]" style={{ fontWeight: 500 }}>
                    {t(`extraction.agents.${agent}`, { defaultValue: DSPY_AGENT_LABELS[agent] })}
                  </span>
                  {compiled ? (
                    <span
                      className="muted"
                      style={{ fontSize: 'var(--fs-xs)' }}
                      title={compiledAt ? new Date(compiledAt * 1000).toLocaleString() : undefined}
                    >
                      {t('extraction.lastCompiled', { time: formatRelativeTime(compiledAt) })}
                      {sizeKb != null && ` · ${sizeKb} KB`}
                      {typeof s?.verifications_since_last_compile === 'number' &&
                        s.verifications_since_last_compile > 0 && (
                        <span
                          className="ml-2"
                          title={
                            autoConfig?.enabled
                              ? t('extraction.autoRecompileTriggersAt', { count: autoConfig.threshold })
                              : t('extraction.enableAutoRecompileHint')
                          }
                        >
                          <Pill
                            dot={false}
                            tone={
                              autoConfig?.enabled &&
                              s.verifications_since_last_compile >= (autoConfig.threshold || 5)
                                ? 'wa'
                                : 'in'
                            }
                          >
                            {t('extraction.newCount', { value: s.verifications_since_last_compile })}
                          </Pill>
                        </span>
                      )}
                    </span>
                  ) : (
                    <span className="faint italic" style={{ fontSize: 'var(--fs-xs)' }}>
                      {t('extraction.usingGenericPrompts')}
                      {typeof s?.verifications_since_last_compile === 'number' && s.verifications_since_last_compile > 0 && (
                        <span className="muted ml-1">
                          {t('extraction.verifiedExamplesAvailable', { count: s.verifications_since_last_compile })}
                        </span>
                      )}
                    </span>
                  )}
                </div>
                <Button size="sm" variant="secondary" onClick={() => handleCompileOne(agent)} disabled={anyPending}>
                  {isPending ? (
                    <>
                      <ArrowPathIcon className="h-3.5 w-3.5 spin" />
                      {pendingAgent === 'all' ? t('extraction.waiting') : t('extraction.compiling')}
                    </>
                  ) : (
                    t('extraction.compile')
                  )}
                </Button>
              </div>
            )
          })}
        </div>
      )}

      {/* Auto-recompile config */}
      {autoConfig && (
        <div className="px-4 py-3 flex items-center justify-between gap-3 flex-wrap" style={{ borderTop: '1px solid var(--b)', background: 'var(--s3)' }}>
          <div className="row min-w-0">
            <Switch
              checked={autoConfig.enabled}
              onChange={(checked) => autoConfigMutation.mutate({ enabled: checked })}
              disabled={autoConfigMutation.isPending}
              label={t('extraction.autoRecompileLabel')}
            />
            <span className="faint" style={{ fontSize: 'var(--fs-xs)' }} title={t('extraction.backgroundTaskTooltip')}>
              {t('extraction.runsInBackground')}
            </span>
          </div>
          <div className="row muted" style={{ fontSize: 'var(--fs-sm)' }}>
            <span>{t('extraction.threshold')}</span>
            {editingThreshold !== null ? (
              <>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={editingThreshold}
                  onChange={(e) => setEditingThreshold(Number(e.target.value) || 1)}
                  className="input"
                  style={{ width: 64, minHeight: 28, padding: '2px 8px', fontSize: 'var(--fs-sm)' }}
                />
                <button
                  onClick={() =>
                    editingThreshold && autoConfigMutation.mutate({ threshold: editingThreshold })
                  }
                  disabled={autoConfigMutation.isPending}
                  style={{ color: 'var(--p)', fontWeight: 600 }}
                >
                  {t('common.save')}
                </button>
                <button onClick={() => setEditingThreshold(null)} className="muted">
                  {t('common.cancel')}
                </button>
              </>
            ) : (
              <>
                <span style={{ fontWeight: 600, color: 'var(--t)' }}>
                  {t('extraction.newVerifications', { count: autoConfig.threshold })}
                </span>
                <button
                  onClick={() => setEditingThreshold(autoConfig.threshold)}
                  style={{ color: 'var(--p)', fontWeight: 600 }}
                >
                  {t('common.edit')}
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {resultMessage && (
        <div className="p-3" style={{ borderTop: '1px solid var(--b)' }}>
          <div
            className={cn('banner', resultIsError && 'banner-da')}
            style={!resultIsError ? { background: 'var(--ok-f)', borderColor: 'var(--ok-b)', color: 'var(--ok)' } : undefined}
          >
            {resultIsError ? (
              <XCircleIcon className="h-4 w-4 mt-0.5 shrink-0" />
            ) : (
              <CheckCircleIcon className="h-4 w-4 mt-0.5 shrink-0" />
            )}
            <span>{resultMessage}</span>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={showCompileAllConfirm}
        title={t('extraction.compileAll')}
        body={t('extraction.confirmCompileAll')}
        tone="warn"
        confirmLabel={t('common.confirm', { defaultValue: 'Confirm' })}
        cancelLabel={t('common.cancel')}
        onConfirm={confirmCompileAll}
        onCancel={() => setShowCompileAllConfirm(false)}
      />
    </div>
  )
}

// ======================== MAIN PAGE ========================

export default function ExtractionQualityPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { isSuperAdmin } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const filterEntityType = searchParams.get('entity_type')
  const filterTaxonomyCode = searchParams.get('taxonomy_code')
  const [view, setView] = useState<ViewMode>('overview')
  const [selectedContractId, setSelectedContractId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'metadata' | 'clauses' | 'obligations' | 'slas'>('metadata')
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [confirmAutoApprove, setConfirmAutoApprove] = useState(false)
  const [removeTarget, setRemoveTarget] = useState<{ contractId: string; isGlobal: boolean } | null>(null)

  // ─── Review UX (#26): filter + focus + keyboard nav ───
  // Filter the list to what actually needs the reviewer's attention.
  // Pending = no verification yet (most common review task).
  const [reviewFilter, setReviewFilter] = useState<'pending' | 'verified' | 'all'>('pending')
  // Auto-advance to the next pending item after a successful verify.
  const [autoAdvance, setAutoAdvance] = useState<boolean>(true)
  // Currently focused item id, used by keyboard nav and the focus ring.
  const [focusedItemId, setFocusedItemId] = useState<string | null>(null)
  const [showShortcutsHelp, setShowShortcutsHelp] = useState(false)
  // Map of itemId → row DOM node, for scrollIntoView on focus change.
  const rowRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const registerRow = useCallback((id: string, el: HTMLDivElement | null) => {
    if (el) rowRefs.current.set(id, el)
    else rowRefs.current.delete(id)
  }, [])

  // Auto-set tab from URL params
  useEffect(() => {
    if (filterEntityType) {
      const tabMap: Record<string, 'metadata' | 'clauses' | 'obligations' | 'slas'> = {
        clause: 'clauses',
        obligation: 'obligations',
        sla: 'slas',
        metadata: 'metadata',
      }
      const tab = tabMap[filterEntityType]
      if (tab) setActiveTab(tab)
    }
  }, [filterEntityType])
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

  // ─── Helpers for review-UX filtering / focus ───
  // Unique key per item across tabs (metadata uses `field`, others use `id`).
  const itemKey = useCallback(
    (tab: string, item: { field?: string; id?: string }) =>
      tab === 'metadata' ? `metadata:${item.field}` : `${tab}:${item.id}`,
    []
  )

  // Items for the current tab, filtered + ordered so reviewers see pending first.
  // Always returns metadata items so we don't lose the field list,
  // but other tabs only return their respective arrays.
  const filteredItems = useMemo(() => {
    if (!detail || !detail.is_golden) return []
    const raw: any[] =
      activeTab === 'metadata' ? detail.metadata :
      activeTab === 'clauses' ? detail.clauses :
      activeTab === 'obligations' ? detail.obligations :
      detail.slas
    return raw.filter((item: any) => {
      const status = item.verification?.status
      if (reviewFilter === 'pending') return !status
      if (reviewFilter === 'verified') return !!status
      return true
    })
  }, [detail, activeTab, reviewFilter])

  // Pending counts per tab (always over the full list, not the filter).
  const tabPendingCounts = useMemo(() => {
    if (!detail) return { metadata: 0, clauses: 0, obligations: 0, slas: 0 }
    const countPending = (arr: any[]) =>
      arr.filter((i) => !i.verification?.status).length
    return {
      metadata: detail.is_golden ? countPending(detail.metadata) : 0,
      clauses: detail.is_golden ? countPending(detail.clauses) : 0,
      obligations: detail.is_golden ? countPending(detail.obligations) : 0,
      slas: detail.is_golden ? countPending(detail.slas) : 0,
    }
  }, [detail])

  // Scroll focused item into view whenever focus changes.
  useEffect(() => {
    if (!focusedItemId) return
    const el = rowRefs.current.get(focusedItemId)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }, [focusedItemId])

  // Reset filter / focus when tab changes so the reviewer doesn't get stuck.
  useEffect(() => {
    setFocusedItemId(null)
  }, [activeTab])

  const handleVerify = (
    entityType: string,
    entityId: string,
    status: 'correct' | 'incorrect' | 'partial',
    correctedValue?: Record<string, unknown>,
    notes?: string,
  ) => {
    if (!detail?.golden_set_id) return
    verifyMutation.mutate({
      golden_set_id: detail.golden_set_id,
      entity_type: entityType,
      entity_id: entityId,
      status,
      corrected_value: correctedValue,
      notes,
    })

    // Auto-advance: move focus to the next pending item in the current tab.
    // Uses the *current* filtered list (the item being verified is still in
    // it because the mutation hasn't refetched yet) so we pick the row right
    // after it.
    if (autoAdvance) {
      const currentKey = entityType === 'metadata_field'
        ? `metadata:${entityId}`
        : `${activeTab}:${entityId}`
      const idx = filteredItems.findIndex((it: any) => itemKey(activeTab, it) === currentKey)
      // The item we just verified will no longer be pending after refetch.
      // For 'pending' filter, advancing by 1 row points to what becomes the
      // new "current" pending; for other filters, just advance.
      const next = filteredItems[idx + 1]
      if (next) {
        setFocusedItemId(itemKey(activeTab, next))
      } else {
        setFocusedItemId(null)
      }
    }
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
      notes: t('extraction.manualAddNote'),
    })
  }

  // ─── Keyboard shortcuts for the detail review view ───
  //   j / k     next / prev item in current filtered list
  //   c / x / p mark focused item correct / incorrect / partial (no correction)
  //   1-4       switch tabs (metadata / clauses / obligations / slas)
  //   /         toggle filter (pending → verified → all → pending)
  //   ?         show shortcut help
  //   Esc       close help / clear focus
  useEffect(() => {
    if (view !== 'detail' || !detail?.is_golden) return

    const handler = (e: KeyboardEvent) => {
      // Ignore when typing in any editable element so corrections aren't disrupted.
      const target = e.target as HTMLElement | null
      if (target) {
        const tag = target.tagName
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
        if (target.isContentEditable) return
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return

      const navigate = (direction: 1 | -1) => {
        if (filteredItems.length === 0) return
        const currentIdx = focusedItemId
          ? filteredItems.findIndex((it: any) => itemKey(activeTab, it) === focusedItemId)
          : -1
        const nextIdx = currentIdx < 0
          ? (direction === 1 ? 0 : filteredItems.length - 1)
          : Math.max(0, Math.min(filteredItems.length - 1, currentIdx + direction))
        setFocusedItemId(itemKey(activeTab, filteredItems[nextIdx]))
      }

      const verifyFocused = (status: 'correct' | 'incorrect' | 'partial') => {
        if (!focusedItemId) return
        const item: any = filteredItems.find((it: any) => itemKey(activeTab, it) === focusedItemId)
        if (!item) return
        const entityType = activeTab === 'metadata' ? 'metadata_field' :
                           activeTab === 'clauses' ? 'clause' :
                           activeTab === 'obligations' ? 'obligation' : 'sla'
        const entityId = activeTab === 'metadata' ? item.field : item.id
        // For keyboard verify we don't supply a correction; reviewer should use
        // the per-row edit UI if they want to change the value.
        handleVerify(entityType, entityId, status)
      }

      switch (e.key) {
        case 'j':
        case 'ArrowDown':
          e.preventDefault(); navigate(1); break
        case 'k':
        case 'ArrowUp':
          e.preventDefault(); navigate(-1); break
        case 'c':
          e.preventDefault(); verifyFocused('correct'); break
        case 'x':
          e.preventDefault(); verifyFocused('incorrect'); break
        case 'p':
          e.preventDefault(); verifyFocused('partial'); break
        case '1':
          e.preventDefault(); setActiveTab('metadata'); break
        case '2':
          e.preventDefault(); setActiveTab('clauses'); break
        case '3':
          e.preventDefault(); setActiveTab('obligations'); break
        case '4':
          e.preventDefault(); setActiveTab('slas'); break
        case '/':
          e.preventDefault()
          setReviewFilter((f) => f === 'pending' ? 'verified' : f === 'verified' ? 'all' : 'pending')
          break
        case '?':
          e.preventDefault(); setShowShortcutsHelp(true); break
        case 'Escape':
          if (showShortcutsHelp) setShowShortcutsHelp(false)
          else setFocusedItemId(null)
          break
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [view, detail, activeTab, filteredItems, focusedItemId, itemKey, showShortcutsHelp])

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
          <Button variant="ghost" size="sm" icon={ArrowLeftIcon} onClick={backToOverview} className="mb-4">
            {t('extraction.backToGoldenSet')}
          </Button>
          <p className="muted">{t('extraction.contractNotFound')}</p>
        </div>
      )
    }

    const tabs = [
      { key: 'metadata' as const,    label: t('extraction.tabs.metadata'),    total: detail.summary.metadata_total,  pending: tabPendingCounts.metadata },
      { key: 'clauses' as const,     label: t('extraction.tabs.clauses'),     total: detail.summary.clause_count,    pending: tabPendingCounts.clauses },
      { key: 'obligations' as const, label: t('extraction.tabs.obligations'), total: detail.summary.obligation_count, pending: tabPendingCounts.obligations },
      { key: 'slas' as const,        label: t('extraction.tabs.slas'),        total: detail.summary.sla_count,       pending: tabPendingCounts.slas },
    ]

    const detailMimeType = /\.docx?$/i.test(detail.filename || '')
      ? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      : null

    return (
      <div className="flex flex-col h-[calc(100vh-88px)] -mx-4 sm:-mx-6 lg:-mx-8 -mt-6">
        {/* Header Bar */}
        <div className="flex-shrink-0 px-4 py-3 flex items-center justify-between" style={{ background: 'var(--s)', borderBottom: '1px solid var(--b)' }}>
          <div className="flex items-center gap-3 min-w-0">
            <Button variant="ghost" size="sm" icon={ArrowLeftIcon} onClick={backToOverview} className="shrink-0">
              {t('extraction.back')}
            </Button>
            <DocumentTextIcon className="h-5 w-5 shrink-0" style={{ color: 'var(--p)' }} />
            <h1 className="trunc" style={{ fontSize: 'var(--fs-lg)', fontWeight: 600 }}>{detail.filename}</h1>
            {detail.is_golden && detail.is_global && (
              <Pill tone="in" dot={false} className="shrink-0">
                <GlobeAltIcon style={{ width: 12, height: 12 }} aria-hidden /> {t('extraction.platform')}
              </Pill>
            )}
            {detail.is_golden && !detail.is_global && (
              <Pill tone="wa" dot={false} className="shrink-0">{t('extraction.goldenSet')}</Pill>
            )}
          </div>
          <Chip on={showDocViewer} icon={EyeIcon} onClick={() => setShowDocViewer(!showDocViewer)} className="shrink-0">
            {showDocViewer ? t('extraction.hideDocument') : t('extraction.showDocument')}
          </Chip>
        </div>

        {/* Split Pane */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left: Document Viewer */}
          {showDocViewer && (
            <div className="w-1/2 flex-shrink-0 h-full overflow-hidden flex flex-col" style={{ borderRight: '1px solid var(--b)', background: 'var(--s3)' }}>
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
          <div className="flex-1 overflow-y-auto scroll">
            <div className="p-4 space-y-4">
              {/* Summary Stats */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Stat label={t('extraction.tabs.metadata')} value={`${detail.summary.metadata_filled}/${detail.summary.metadata_total}`} />
                <Stat label={t('extraction.tabs.clauses')} value={detail.summary.clause_count} />
                <Stat label={t('extraction.tabs.obligations')} value={detail.summary.obligation_count} />
                <Stat label={t('extraction.tabs.slas')} value={detail.summary.sla_count} />
              </div>

        {/* Tabs */}
        <div className="tabs" role="tablist">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn('tab', activeTab === tab.key && 'on')}
            >
              {tab.label}
              {detail.is_golden && tab.total > 0 ? (
                <span
                  className="ct num"
                  style={tab.pending === 0
                    ? { background: 'var(--ok-f)', color: 'var(--ok)' }
                    : { background: 'var(--wa-f)', color: 'var(--wa)' }}
                  title={tab.pending === 0
                    ? t('extraction.allReviewed', { count: tab.total })
                    : t('extraction.pendingOfTotal', { pending: tab.pending, total: tab.total })}
                >
                  {tab.pending === 0 ? `✓ ${tab.total}` : `${tab.pending} / ${tab.total}`}
                </span>
              ) : (
                <span className="ct num">{tab.total}</span>
              )}
            </button>
          ))}
        </div>

        {/* Review filter bar — only meaningful for golden contracts */}
        {detail.is_golden && (
          <div className="flex flex-wrap items-center justify-between gap-2 pb-2">
            <div className="row" style={{ gap: 6 }}>
              {(['pending', 'verified', 'all'] as const).map((f) => (
                <Chip key={f} on={reviewFilter === f} onClick={() => setReviewFilter(f)} className="capitalize">
                  {f === 'pending' ? t('status.pending') : t(`extraction.filter.${f}`)}
                </Chip>
              ))}
            </div>
            <div className="row muted flex-wrap" style={{ gap: 12, fontSize: 'var(--fs-sm)' }}>
              <span>
                {t('extraction.showing')} <strong style={{ color: 'var(--t)' }}>{filteredItems.length}</strong>
                {' · '}
                <strong style={{ color: 'var(--wa)' }}>{tabPendingCounts[activeTab]}</strong> {t('extraction.pendingLabel')}
                {' / '}
                <strong style={{ color: 'var(--t)' }}>
                  {activeTab === 'metadata' ? detail.summary.metadata_total :
                   activeTab === 'clauses' ? detail.summary.clause_count :
                   activeTab === 'obligations' ? detail.summary.obligation_count :
                   detail.summary.sla_count} {t('extraction.totalLabel')}
                </strong>
              </span>
              <span title={t('extraction.autoAdvanceTooltip')}>
                <Checkbox checked={autoAdvance} onChange={setAutoAdvance} label={t('extraction.autoAdvance')} />
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowShortcutsHelp(true)}
                title={t('extraction.showKeyboardShortcuts')}
              >
                <span className="kbd">?</span> {t('extraction.shortcuts')}
              </Button>
            </div>
          </div>
        )}

        {/* Tab Content */}
        <div className="card overflow-hidden divide-y divide-[var(--b)]">
          {activeTab === 'metadata' && detail.is_golden && filteredItems.map((item: any) => {
            const key = itemKey('metadata', item)
            return (
              <div
                key={key}
                ref={(el) => registerRow(key, el)}
                style={focusedItemId === key ? { boxShadow: 'inset 0 0 0 2px var(--p)', background: 'var(--p-f)' } : undefined}
                onClick={() => setFocusedItemId(key)}
              >
                <MetadataEditRow item={item} goldenSetId={detail.golden_set_id!} onVerify={handleVerify} />
              </div>
            )
          })}
          {activeTab === 'metadata' && !detail.is_golden && detail.metadata.map((item) => (
            <div key={item.field} className="flex items-center justify-between px-4 py-3">
              <div className="flex-1">
                <p className="capitalize" style={{ fontWeight: 500 }}>{item.field.replace(/_/g, ' ')}</p>
                <p className="muted mt-0.5">{item.value !== null && item.value !== undefined ? String(item.value) : <span className="italic faint">{t('extraction.notExtracted')}</span>}</p>
              </div>
            </div>
          ))}

          {activeTab === 'clauses' && detail.is_golden && filteredItems.map((clause: any) => {
            const key = itemKey('clauses', clause)
            const focused = focusedItemId === key
            return (
              <div
                key={key}
                ref={(el) => registerRow(key, el)}
                style={focused ? { boxShadow: 'inset 0 0 0 2px var(--p)', background: 'var(--p-f)' } : undefined}
                onClick={() => setFocusedItemId(key)}
              >
                {clause.is_manual ? (
                  <div className="px-4 py-3" style={{ background: 'var(--wa-f)' }}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="row">
                        <Pill tone="p" dot={false}>{clause.clause_type || t('extraction.unknown')}</Pill>
                        {clause.risk_level && (
                          <Pill tone={RISK_TONE[clause.risk_level] || 'n'} dot={false}>
                            {t('extraction.riskSuffix', { level: t(`risk.${clause.risk_level}`, { defaultValue: clause.risk_level }) })}
                          </Pill>
                        )}
                        <Pill tone="wa" dot={false}>{t('extraction.manuallyAdded')}</Pill>
                      </div>
                      {clause.verification && <VerificationBadge status={clause.verification.status} />}
                    </div>
                    <p className="muted line-clamp-3">{clause.text}</p>
                    {clause.verification?.notes && <p className="faint italic" style={{ fontSize: 'var(--fs-xs)', marginTop: 2 }}>{clause.verification.notes}</p>}
                  </div>
                ) : (
                  <ClauseEditRow clause={clause} goldenSetId={detail.golden_set_id!} onVerify={handleVerify} onLocate={(text: string, page?: number | null) => { setHighlightText(text); setHighlightPage(page ?? null); }} />
                )}
              </div>
            )
          })}
          {activeTab === 'clauses' && !detail.is_golden && detail.clauses.map((clause: any) => (
            <div key={clause.id} className="px-4 py-3">
              <Pill tone="p" dot={false}>{clause.clause_type || t('extraction.unknown')}</Pill>
              <p className="muted mt-1 line-clamp-3">{clause.text}</p>
            </div>
          ))}
          {activeTab === 'clauses' && detail.is_golden && (
            <AddMissingClause onAdd={(val) => handleAddManual('clause', val)} />
          )}

          {activeTab === 'obligations' && detail.is_golden && filteredItems.map((obl: any) => {
            const key = itemKey('obligations', obl)
            const focused = focusedItemId === key
            return (
              <div
                key={key}
                ref={(el) => registerRow(key, el)}
                style={focused ? { boxShadow: 'inset 0 0 0 2px var(--p)', background: 'var(--p-f)' } : undefined}
                onClick={() => setFocusedItemId(key)}
              >
                {obl.is_manual ? (
                  <div className="px-4 py-3" style={{ background: 'var(--wa-f)' }}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="row">
                        <Pill tone="in" dot={false}>{obl.obligation_type || t('extraction.unknown')}</Pill>
                        {obl.obligated_party && <span className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{obl.obligated_party}</span>}
                        <Pill tone="wa" dot={false}>{t('extraction.manuallyAdded')}</Pill>
                      </div>
                      {obl.verification && <VerificationBadge status={obl.verification.status} />}
                    </div>
                    <p className="muted line-clamp-2">{obl.description}</p>
                    {obl.verification?.notes && <p className="faint italic" style={{ fontSize: 'var(--fs-xs)', marginTop: 2 }}>{obl.verification.notes}</p>}
                  </div>
                ) : (
                  <ObligationEditRow obl={obl} onVerify={handleVerify} />
                )}
              </div>
            )
          })}
          {activeTab === 'obligations' && !detail.is_golden && detail.obligations.map((obl: any) => (
            <div key={obl.id} className="px-4 py-3">
              <Pill tone="in" dot={false}>{obl.obligation_type || t('extraction.unknown')}</Pill>
              <p className="muted mt-1 line-clamp-2">{obl.description}</p>
            </div>
          ))}
          {activeTab === 'obligations' && detail.is_golden && (
            <AddMissingObligation onAdd={(val) => handleAddManual('obligation', val)} />
          )}

          {activeTab === 'slas' && detail.is_golden && filteredItems.map((sla: any) => {
            const key = itemKey('slas', sla)
            const focused = focusedItemId === key
            return (
              <div
                key={key}
                ref={(el) => registerRow(key, el)}
                style={focused ? { boxShadow: 'inset 0 0 0 2px var(--p)', background: 'var(--p-f)' } : undefined}
                onClick={() => setFocusedItemId(key)}
              >
                {sla.is_manual ? (
                  <div className="px-4 py-3" style={{ background: 'var(--wa-f)' }}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="row">
                        <Pill tone="p" dot={false}>{sla.metric_type || 'SLA'}</Pill>
                        <Pill tone="wa" dot={false}>{t('extraction.manuallyAdded')}</Pill>
                      </div>
                      {sla.verification && <VerificationBadge status={sla.verification.status} />}
                    </div>
                    <p style={{ fontWeight: 500 }}>{sla.sla_name}</p>
                    <p className="muted">{t('extraction.target', { value: sla.target_value ?? '--', unit: sla.metric_unit || '' })}</p>
                    {sla.verification?.notes && <p className="faint italic" style={{ fontSize: 'var(--fs-xs)', marginTop: 2 }}>{sla.verification.notes}</p>}
                  </div>
                ) : (
                  <SLAEditRow sla={sla} onVerify={handleVerify} />
                )}
              </div>
            )
          })}
          {activeTab === 'slas' && !detail.is_golden && detail.slas.map((sla: any) => (
            <div key={sla.id} className="px-4 py-3">
              <Pill tone="p" dot={false}>{sla.metric_type || 'SLA'}</Pill>
              <p className="mt-1" style={{ fontWeight: 500 }}>{sla.sla_name}</p>
              <p className="muted">{t('extraction.target', { value: sla.target_value ?? '--', unit: sla.metric_unit || '' })}</p>
            </div>
          ))}
          {activeTab === 'slas' && detail.is_golden && (
            <AddMissingSLA onAdd={(val) => handleAddManual('sla', val)} />
          )}

          {activeTab === 'clauses' && detail.clauses.length === 0 && !detail.is_golden && <div className="p-8 text-center faint">{t('extraction.noClausesExtracted')}</div>}
          {activeTab === 'obligations' && detail.obligations.length === 0 && !detail.is_golden && <div className="p-8 text-center faint">{t('extraction.noObligationsExtracted')}</div>}
          {activeTab === 'slas' && detail.slas.length === 0 && !detail.is_golden && <div className="p-8 text-center faint">{t('extraction.noSlasExtracted')}</div>}

          {/* Empty state when the active filter hides everything */}
          {detail.is_golden && filteredItems.length === 0 && (
            <div className="p-8 text-center">
              {reviewFilter === 'pending' ? (
                <div style={{ color: 'var(--ok)' }}>
                  <CheckCircleIcon className="h-6 w-6 mx-auto mb-1" />
                  {t('extraction.nothingPending')}
                  {(tabPendingCounts.metadata + tabPendingCounts.clauses + tabPendingCounts.obligations + tabPendingCounts.slas - tabPendingCounts[activeTab]) > 0 && (
                    <p className="muted" style={{ fontSize: 'var(--fs-xs)', marginTop: 4 }}>
                      {t('extraction.otherTabsPending')}
                    </p>
                  )}
                </div>
              ) : reviewFilter === 'verified' ? (
                <div className="faint">{t('extraction.noVerifiedItems')}</div>
              ) : (
                <div className="faint">{t('extraction.noItems')}</div>
              )}
            </div>
          )}
        </div>
        </div>
        </div>
        </div>

        {/* Shortcuts help */}
        <Drawer
          open={showShortcutsHelp}
          title={t('extraction.keyboardShortcuts')}
          onClose={() => setShowShortcutsHelp(false)}
          width={380}
        >
          <div className="space-y-2">
            {[
              ['j / ↓', t('extraction.shortcutNext')],
              ['k / ↑', t('extraction.shortcutPrev')],
              ['c', t('extraction.shortcutMarkCorrect')],
              ['x', t('extraction.shortcutMarkIncorrect')],
              ['p', t('extraction.shortcutMarkPartial')],
              ['1 / 2 / 3 / 4', t('extraction.shortcutSwitchTabs')],
              ['/', t('extraction.shortcutCycleFilter')],
              ['Esc', t('extraction.shortcutEscape')],
              ['?', t('extraction.shortcutHelp')],
            ].map(([key, desc]) => (
              <div key={key} className="row" style={{ gap: 12 }}>
                <kbd className="kbd" style={{ minWidth: 80 }}>{key}</kbd>
                <span className="muted">{desc}</span>
              </div>
            ))}
          </div>
          <p className="faint" style={{ fontSize: 'var(--fs-sm)', marginTop: 16, lineHeight: 1.5 }}>
            {t('extraction.shortcutsNote')} <kbd className="kbd">j</kbd>).
          </p>
        </Drawer>
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
          <AdjustmentsHorizontalIcon className="h-7 w-7" style={{ color: 'var(--p)' }} />
          <div>
            <h1 style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600, letterSpacing: '-.3px' }}>{t('nav.extractionQuality')}</h1>
            <p className="muted" style={{ fontSize: 'var(--fs-sm)' }}>{t('extraction.subtitle')}</p>
          </div>
        </div>
        <div className="row">
          {overview && overview.pending_review > 0 && (
            <Button
              variant="secondary"
              icon={CheckCircleIcon}
              onClick={() => setConfirmAutoApprove(true)}
              disabled={autoApproveMutation.isPending}
            >
              {autoApproveMutation.isPending ? t('extraction.approving') : t('extraction.autoApproveAll')}
            </Button>
          )}
          <Button variant="primary" icon={PlusIcon} onClick={() => setShowAddDialog(true)}>
            {t('extraction.addToGoldenSet')}
          </Button>
        </div>
      </div>

      {/* Filter banner from cross-page navigation */}
      {filterEntityType && filterTaxonomyCode && (
        <div className="banner banner-p items-center">
          <FunnelIcon className="h-4 w-4 shrink-0" />
          <span className="grow">
            {t('extraction.filtering')} <b>{filterEntityType}</b> {t('extraction.typeLabel')} <b className="mono">{filterTaxonomyCode}</b>
          </span>
          <div className="row shrink-0" style={{ gap: 12 }}>
            <Link to="/admin/industry-profiles" style={{ fontSize: 'var(--fs-xs)', fontWeight: 600 }}>
              &larr; {t('extraction.backToIndustryProfiles')}
            </Link>
            <button onClick={() => setSearchParams({})} className="muted" style={{ fontSize: 'var(--fs-xs)' }}>
              {t('extraction.clearFilter')}
            </button>
          </div>
        </div>
      )}

      {/* Score Cards */}
      {overview && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <ScoreCard label={t('extraction.overall')} score={overview.avg_overall_score} />
          <ScoreCard label={t('extraction.tabs.metadata')} score={overview.avg_metadata_score} />
          <ScoreCard label={t('extraction.tabs.clauses')} score={overview.avg_clause_score} />
          <ScoreCard label={t('extraction.tabs.obligations')} score={overview.avg_obligation_score} />
          <ScoreCard label={t('extraction.tabs.slas')} score={overview.avg_sla_score} />
        </div>
      )}

      {/* Summary Stats */}
      {overview && (
        <div className="row muted flex-wrap" style={{ gap: 20, fontSize: 'var(--fs-sm)' }}>
          <span><strong style={{ color: 'var(--t)' }}>{overview.total_golden}</strong> {t('extraction.summaryGolden')}</span>
          {overview.total_global > 0 && (
            <span><strong style={{ color: 'var(--in)' }}>{overview.total_global}</strong> {t('extraction.summaryPlatform')}</span>
          )}
          {overview.total_tenant > 0 && (
            <span><strong style={{ color: 'var(--wa)' }}>{overview.total_tenant}</strong> {t('extraction.summaryTenant')}</span>
          )}
          <span><strong style={{ color: 'var(--ok)' }}>{overview.verified}</strong> {t('extraction.summaryVerified')}</span>
          <span><strong style={{ color: 'var(--wa)' }}>{overview.pending_review}</strong> {t('extraction.summaryPendingReview')}</span>
        </div>
      )}

      {/* DSPy compilation status + manual trigger */}
      <DspyCompilationPanel />

      {/* Golden Set Contracts List */}
      <div className="card overflow-hidden">
        <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--b)' }}>
          <h2 className="sec-t">{t('extraction.goldenSetContracts')}</h2>
        </div>
        {(!goldenSet || goldenSet.length === 0) ? (
          <EmptyState
            icon={DocumentTextIcon}
            title={t('extraction.noGoldenContracts')}
            body={t('extraction.addContractsHint')}
          />
        ) : (
          <div className="divide-y divide-[var(--b)]">
            {goldenSet.map((item) => (
              <div key={item.id} className="flex items-center justify-between px-4 py-3 transition-colors hover:bg-[var(--s3)]">
                <button
                  onClick={() => openDetail(item.contract_id)}
                  className="flex-1 text-left"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="trunc" style={{ fontWeight: 500 }}>{item.filename}</p>
                        {item.is_global && (
                          <Pill tone="in" dot={false} className="shrink-0">
                            <GlobeAltIcon style={{ width: 12, height: 12 }} aria-hidden /> {t('extraction.platform')}
                          </Pill>
                        )}
                      </div>
                      <div className="row muted flex-wrap" style={{ gap: 12, marginTop: 2, fontSize: 'var(--fs-xs)' }}>
                        {item.contract_type && <span className="capitalize">{item.contract_type}</span>}
                        {item.counterparty && <span>{item.counterparty}</span>}
                        <span>{t('extraction.clausesCount', { count: item.extraction.clause_count })}</span>
                        <span>{t('extraction.oblsCount', { count: item.extraction.obligation_count })}</span>
                        <span>{t('extraction.slasCount', { count: item.extraction.sla_count })}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <div className="num" style={{ fontSize: 'var(--fs-xs)' }}>
                        <span style={{ color: 'var(--ok)' }}>{item.verification.correct}</span>/
                        <span style={{ color: 'var(--da)' }}>{item.verification.incorrect}</span>/
                        <span style={{ color: 'var(--wa)' }}>{item.verification.partial}</span>/
                        <span className="faint">{item.verification.pending}</span>
                      </div>
                      <div className="num w-14 text-right" style={{ fontWeight: 600, color: scoreTone(item.scores.overall) }}>
                        {item.scores.overall !== null ? `${item.scores.overall}%` : '--'}
                      </div>
                      <ChevronRightIcon className="h-4 w-4" style={{ color: 'var(--f)' }} />
                    </div>
                  </div>
                </button>
                {/* Only allow removing global entries if super admin, always allow removing tenant entries */}
                {(isSuperAdmin || !item.is_global) && (
                  <IconButton
                    icon={TrashIcon}
                    size="sm"
                    label={item.is_global ? t('extraction.removeFromPlatformGoldenSet') : t('extraction.removeFromGoldenSet')}
                    className="ml-2"
                    onClick={(e) => {
                      e.stopPropagation()
                      setRemoveTarget({ contractId: item.contract_id, isGlobal: item.is_global })
                    }}
                  />
                )}
              </div>
            ))}
          </div>
        )}
        {/* Pagination */}
        {gsTotalPages > 1 && (
          <div className="px-4 py-3 flex items-center justify-between" style={{ borderTop: '1px solid var(--b)' }}>
            <span className="faint" style={{ fontSize: 'var(--fs-xs)' }}>
              {t('extraction.showingRange', { from: (gsPage - 1) * gsPageSize + 1, to: Math.min(gsPage * gsPageSize, gsTotal), total: gsTotal })}
            </span>
            <div className="row" style={{ gap: 4 }}>
              <Button size="sm" variant="ghost" onClick={() => setGsPage((p) => Math.max(1, p - 1))} disabled={gsPage <= 1}>
                {t('extraction.prev')}
              </Button>
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
                  <Button
                    key={p}
                    size="sm"
                    variant={p === gsPage ? 'primary' : 'ghost'}
                    onClick={() => setGsPage(p)}
                    className="num"
                  >
                    {p}
                  </Button>
                )
              })}
              <Button size="sm" variant="ghost" onClick={() => setGsPage((p) => Math.min(gsTotalPages, p + 1))} disabled={gsPage >= gsTotalPages}>
                {t('extraction.next')}
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Add to Golden Set */}
      <Drawer
        open={showAddDialog}
        title={t('extraction.addContractToGoldenSet')}
        onClose={() => { setShowAddDialog(false); setAddAsGlobal(false) }}
        width={480}
        footer={
          <Button variant="secondary" style={{ flex: 1 }} onClick={() => { setShowAddDialog(false); setAddAsGlobal(false) }}>
            {t('common.cancel')}
          </Button>
        }
      >
        <p className="muted" style={{ fontSize: 'var(--fs-sm)' }}>
          {addAsGlobal
            ? t('extraction.addingAsPlatform')
            : t('extraction.selectContractHint')}
        </p>
        <Field
          type="text"
          placeholder={t('extraction.searchContractsPlaceholder')}
          value={contractSearch}
          onChange={(e) => setContractSearch(e.target.value)}
          containerStyle={{ marginTop: 12 }}
        />
        {isSuperAdmin && (
          <div className="row" style={{ marginTop: 10 }}>
            <Checkbox checked={addAsGlobal} onChange={setAddAsGlobal} label={t('extraction.addAsPlatformLabel')} />
            <GlobeAltIcon className="h-4 w-4 shrink-0" style={{ color: 'var(--in)' }} aria-hidden />
          </div>
        )}
        <div className="card overflow-hidden divide-y divide-[var(--b)]" style={{ marginTop: 14 }}>
          {availableContracts.length === 0 ? (
            <div className="p-6 text-center faint" style={{ fontSize: 'var(--fs-sm)' }}>
              {contractsResponse ? t('extraction.noMatchingContracts') : <LoadingSpinner size="sm" />}
            </div>
          ) : (
            availableContracts.slice(0, 20).map((contract) => (
              <button
                key={contract.id}
                onClick={() => addMutation.mutate({ contractId: contract.id, isGlobal: addAsGlobal })}
                disabled={addMutation.isPending}
                className="w-full text-left px-4 py-3 transition-colors hover:bg-[var(--p-f)] disabled:opacity-50"
              >
                <p className="trunc" style={{ fontWeight: 500 }}>{contract.filename}</p>
                <div className="row muted flex-wrap" style={{ gap: 12, marginTop: 2, fontSize: 'var(--fs-xs)' }}>
                  {contract.contract_type && <span className="capitalize">{contract.contract_type}</span>}
                  {contract.counterparty && <span>{contract.counterparty}</span>}
                  {contract.status && <span className="capitalize">{contract.status}</span>}
                </div>
              </button>
            ))
          )}
        </div>
      </Drawer>

      {/* Confirm: auto-approve all pending verifications */}
      <ConfirmDialog
        open={confirmAutoApprove}
        title={t('extraction.autoApproveAll')}
        body={t('extraction.confirmAutoApprove', { count: overview?.pending_review ?? 0 })}
        tone="warn"
        confirmLabel={t('common.confirm', { defaultValue: 'Confirm' })}
        cancelLabel={t('common.cancel')}
        onConfirm={() => {
          setConfirmAutoApprove(false)
          autoApproveMutation.mutate()
        }}
        onCancel={() => setConfirmAutoApprove(false)}
      />

      {/* Confirm: remove contract from golden set */}
      <ConfirmDialog
        open={!!removeTarget}
        title={removeTarget?.isGlobal ? t('extraction.removeFromPlatformGoldenSet') : t('extraction.removeFromGoldenSet')}
        body={removeTarget?.isGlobal ? t('extraction.confirmRemoveGlobal') : t('extraction.confirmRemove')}
        confirmLabel={t('common.remove', { defaultValue: 'Remove' })}
        cancelLabel={t('common.cancel')}
        onConfirm={() => {
          if (removeTarget) {
            removeMutation.mutate({ contractId: removeTarget.contractId, isGlobal: removeTarget.isGlobal })
          }
          setRemoveTarget(null)
        }}
        onCancel={() => setRemoveTarget(null)}
      />
    </div>
  )
}
