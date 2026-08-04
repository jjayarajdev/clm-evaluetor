/* Obligation detail — Direction B redesign.
   Back link + header with mono id, status/RAG Pills and type Tag → overdue
   banner → parties/deadline/consequence cards → AI-extracted source card →
   sidebar with contract, RAG, evidence and review (write roles). Evidence
   upload moved from a modal to a Drawer; queries, mutations, the derived
   overdue rule and the permission gate are unchanged. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  ChatBubbleLeftRightIcon,
  CheckCircleIcon,
  DocumentArrowUpIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  HashtagIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { formatDate } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'
import { getUsers } from '@/lib/api/admin'
import { Button, Chip, Drawer, EmptyState, Field, Pill, Select, Tag, AiTag, useToast } from '@/components/ui'
import type { PillTone } from '@/components/ui'

const OBLIGATION_TYPE_LABELS: Record<string, string> = {
  payment: 'Payment',
  delivery: 'Delivery',
  reporting: 'Reporting',
  compliance: 'Compliance',
  notification: 'Notification',
  performance: 'Performance',
  other: 'Other',
}

const STATUS_TONE: Record<string, PillTone> = {
  pending: 'wa',
  in_progress: 'in',
  completed: 'ok',
  overdue: 'da',
  waived: 'n',
}

const RISK_TONE: Record<string, PillTone> = {
  low: 'ok',
  medium: 'wa',
  high: 'da',
  critical: 'da',
}

const RAG_META: Record<string, { tone: PillTone; label: string; description: string }> = {
  green: { tone: 'ok', label: 'On Track', description: 'Compliance fully met' },
  amber: { tone: 'wa', label: 'At Risk', description: 'Needs attention soon' },
  red: { tone: 'da', label: 'Overdue', description: 'Immediate action required' },
  not_assessed: { tone: 'n', label: 'Not Assessed', description: 'Status pending review' },
}

export default function ObligationDetailPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const { toast } = useToast()
  // Reviewers (write roles) can close out / assess obligations; viewers cannot.
  const canReview = ['super_admin', 'admin', 'legal', 'procurement', 'bu_head'].includes(user?.role || '')
  const [showEvidenceDrawer, setShowEvidenceDrawer] = useState(false)
  const [evidenceDescription, setEvidenceDescription] = useState('')
  const [evidenceDate, setEvidenceDate] = useState('')
  const [evidenceFile, setEvidenceFile] = useState<File | null>(null)
  const [evidenceError, setEvidenceError] = useState<string | null>(null)

  const { data: obligation, isLoading, error } = useQuery({
    queryKey: ['obligation', id],
    queryFn: () => api.getObligationDetail(id!),
    enabled: !!id,
  })

  const uploadEvidenceMutation = useMutation({
    mutationFn: (data: { evidence_description: string; evidence_date?: string; file?: File }) =>
      api.uploadObligationEvidence(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['obligation', id] })
      setShowEvidenceDrawer(false)
      setEvidenceDescription('')
      setEvidenceDate('')
      setEvidenceFile(null)
      setEvidenceError(null)
      toast({ text: t('obligation.evidenceAddedToast', { defaultValue: 'Evidence recorded.' }) })
    },
    onError: (e: unknown) => {
      setEvidenceError(e instanceof Error ? e.message : t('obligation.evidenceUploadFailed', { defaultValue: 'Upload failed. Please try again.' }))
    },
  })

  const handleEvidenceSubmit = () => {
    // A file alone is valid evidence — fall back to the filename as the description
    // so uploading just an image works (the backend requires a description string).
    const description = evidenceDescription.trim() || evidenceFile?.name || ''
    if (!description) return
    setEvidenceError(null)
    uploadEvidenceMutation.mutate({
      evidence_description: description,
      evidence_date: evidenceDate || undefined,
      file: evidenceFile || undefined,
    })
  }

  const mutationError = (e: unknown) =>
    toast({
      text: e instanceof Error ? e.message : t('obligation.updateFailed', { defaultValue: 'Update failed. Please try again.' }),
      error: true,
    })

  const statusMutation = useMutation({
    mutationFn: (status: string) => api.updateObligationStatus(id!, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['obligation', id] }),
    onError: mutationError,
  })
  const ragMutation = useMutation({
    mutationFn: (rag_status: string) => api.updateObligationRAG(id!, { rag_status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['obligation', id] }),
    onError: mutationError,
  })
  const assignMutation = useMutation({
    mutationFn: (userId: string | null) => api.assignObligation(id!, userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['obligation', id] }),
    onError: mutationError,
  })
  const reviewBusy = statusMutation.isPending || ragMutation.isPending || assignMutation.isPending

  // Tenant users for the assignee picker (only fetched for reviewers).
  const { data: assignableUsers } = useQuery({
    queryKey: ['assignable-users'],
    queryFn: getUsers,
    enabled: canReview,
  })

  // Fetch the attached file through the API client (carries the auth token) and
  // open it in a new tab — a plain <a href> can't send the Bearer header.
  const viewEvidenceFile = async (filename: string) => {
    try {
      const blob = await api.downloadObligationEvidence(id!, filename)
      const url = URL.createObjectURL(blob)
      window.open(url, '_blank', 'noopener')
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch {
      toast({
        text: t('obligation.evidenceViewFailed', { defaultValue: 'Could not open the attached file.' }),
        error: true,
      })
    }
  }

  if (isLoading) {
    return (
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !obligation) {
    return (
      <div className="col" style={{ alignItems: 'center', gap: 8, padding: '48px 0' }}>
        <p style={{ color: 'var(--da)' }}>{t('obligation.notFound')}</p>
        <Link to="/dashboard">{t('obligation.backToDashboard')}</Link>
      </div>
    )
  }

  const ragKey: string =
    obligation.rag_status && RAG_META[obligation.rag_status] ? obligation.rag_status : 'not_assessed'

  // Mirror the backend's dynamic rule (_effective_status): a passed deadline on a
  // not-completed/waived obligation is overdue, regardless of the stored default
  // ('pending' is the untouched DB default on untracked obligations). Keeps the
  // detail page consistent with the list, which already derives this.
  const isOverdue =
    !!obligation.deadline &&
    new Date(obligation.deadline) < new Date() &&
    obligation.status !== 'completed' &&
    obligation.status !== 'waived'
  const displayStatus = isOverdue ? 'overdue' : obligation.status

  const evidenceEntries = obligation.compliance_evidence
    ? obligation.compliance_evidence.split('\n').filter((e: string) => e.trim())
    : []

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Back link + header */}
      <div>
        <Link
          to="/dashboard"
          className="row"
          style={{ gap: 4, width: 'fit-content', fontSize: 'var(--fs-sm)', color: 'var(--m)' }}
        >
          <ArrowLeftIcon style={{ width: 14, height: 14 }} aria-hidden />
          {t('obligation.backToDashboard')}
        </Link>
        <div className="row" style={{ gap: 12, alignItems: 'flex-start', marginTop: 10, flexWrap: 'wrap' }}>
          <div className="grow" style={{ minWidth: 260 }}>
            <div className="row" style={{ gap: 7, marginBottom: 5, flexWrap: 'wrap' }}>
              <span className="mono faint" style={{ fontSize: 'var(--fs-xs)' }}>{obligation.id.slice(0, 8)}</span>
              <Pill tone={STATUS_TONE[displayStatus] || 'wa'}>
                {t(`obligation.status.${displayStatus}`, { defaultValue: displayStatus })}
              </Pill>
              {obligation.rag_status && (
                <Pill tone={RAG_META[ragKey].tone}>
                  {t(`obligation.rag.${ragKey}.label`, { defaultValue: RAG_META[ragKey].label })}
                </Pill>
              )}
              {obligation.is_critical && <Pill tone="p">{t('risk.critical')}</Pill>}
              <Tag>
                {t(`obligation.type.${obligation.obligation_type}`, {
                  defaultValue: OBLIGATION_TYPE_LABELS[obligation.obligation_type] || obligation.obligation_type,
                })}
              </Tag>
            </div>
            <h1 style={{ fontSize: 'var(--fs-xl)', fontWeight: 600, lineHeight: 1.4 }}>
              {obligation.description}
            </h1>
            <div className="row muted" style={{ gap: 8, marginTop: 8, fontSize: 'var(--fs-md)', flexWrap: 'wrap' }}>
              <Tag icon={DocumentTextIcon}>{obligation.contract_filename}</Tag>
              {obligation.counterparty && <Tag>{obligation.counterparty}</Tag>}
              {obligation.deadline && (
                <Tag>
                  {t('obligation.deadline')}: {formatDate(obligation.deadline)}
                </Tag>
              )}
            </div>
          </div>
          <div className="row" style={{ gap: 8, flexShrink: 0 }}>
            <Button
              variant="secondary"
              icon={ChatBubbleLeftRightIcon}
              onClick={() => navigate(`/query?obligation=${obligation.id}`)}
            >
              {t('obligation.askAi')}
            </Button>
          </div>
        </div>
      </div>

      {/* Overdue banner — derived, matches the list view */}
      {isOverdue && (
        <div className="banner banner-da">
          <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
          <span className="grow">
            <b>{t('obligation.status.overdue', { defaultValue: 'Overdue' })}</b>
            {' — '}
            {t('obligation.overdueBanner', {
              defaultValue: 'the deadline of {{date}} has passed and this obligation is not completed or waived.',
              date: formatDate(obligation.deadline!),
            })}
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
        {/* Main content */}
        <div className="lg:col-span-2 col" style={{ gap: 16 }}>
          {/* Parties */}
          <div className="card card-p">
            <div className="sec-t" style={{ marginBottom: 12 }}>{t('obligation.partiesInvolved')}</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <div className="faint" style={{ fontSize: 'var(--fs-sm)', marginBottom: 2 }}>
                  {t('obligation.obligatedParty')}
                </div>
                <div style={{ fontSize: 'var(--fs-lg)', fontWeight: 600 }}>
                  {obligation.obligated_party || '—'}
                </div>
                <div className="muted" style={{ fontSize: 'var(--fs-sm)', marginTop: 2 }}>
                  {t('obligation.obligatedPartyDesc')}
                </div>
              </div>
              <div>
                <div className="faint" style={{ fontSize: 'var(--fs-sm)', marginBottom: 2 }}>
                  {t('obligation.beneficiary')}
                </div>
                <div style={{ fontSize: 'var(--fs-lg)', fontWeight: 600 }}>
                  {obligation.beneficiary_party || '—'}
                </div>
                <div className="muted" style={{ fontSize: 'var(--fs-sm)', marginTop: 2 }}>
                  {t('obligation.beneficiaryDesc')}
                </div>
              </div>
            </div>
          </div>

          {/* Deadline */}
          <div className="card card-p">
            <div className="sec-t" style={{ marginBottom: 12 }}>{t('obligation.deadlineInformation')}</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <div className="faint" style={{ fontSize: 'var(--fs-sm)', marginBottom: 2 }}>
                  {t('obligation.deadline')}
                </div>
                <div className="num" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                  {obligation.deadline ? formatDate(obligation.deadline) : t('obligation.noFixedDeadline')}
                </div>
              </div>
              <div>
                <div className="faint" style={{ fontSize: 'var(--fs-sm)', marginBottom: 2 }}>
                  {t('obligation.deadlineType')}
                </div>
                <div className="capitalize" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                  {obligation.deadline_type?.replace('_', ' ') || t('obligation.notSpecified')}
                </div>
              </div>
              {obligation.recurrence_pattern && (
                <div>
                  <div className="faint" style={{ fontSize: 'var(--fs-sm)', marginBottom: 2 }}>
                    {t('obligation.recurrence')}
                  </div>
                  <div style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                    {obligation.recurrence_pattern}
                  </div>
                </div>
              )}
              {obligation.relative_deadline_text && (
                <div className="sm:col-span-2">
                  <div className="faint" style={{ fontSize: 'var(--fs-sm)', marginBottom: 2 }}>
                    {t('obligation.relativeDeadline')}
                  </div>
                  <div style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                    {obligation.relative_deadline_text}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Trigger & Consequences */}
          {(obligation.trigger_condition || obligation.consequence_of_breach) && (
            <div className="card card-p">
              <div className="sec-t" style={{ marginBottom: 12 }}>{t('obligation.triggersConsequences')}</div>
              <div className="col" style={{ gap: 12 }}>
                {obligation.trigger_condition && (
                  <div>
                    <div className="faint" style={{ fontSize: 'var(--fs-sm)', marginBottom: 4 }}>
                      {t('obligation.triggerCondition')}
                    </div>
                    <div
                      style={{
                        padding: 12,
                        borderRadius: 'var(--r-md)',
                        background: 'var(--s2)',
                        fontSize: 'var(--fs-md)',
                        lineHeight: 1.55,
                      }}
                    >
                      {obligation.trigger_condition}
                    </div>
                  </div>
                )}
                {obligation.consequence_of_breach && (
                  <div>
                    <div className="faint" style={{ fontSize: 'var(--fs-sm)', marginBottom: 4 }}>
                      {t('obligation.consequenceOfBreach')}
                    </div>
                    <div className="banner banner-da">
                      <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
                      <span className="grow">{obligation.consequence_of_breach}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Source from contract — AI-extracted */}
          {(obligation.source_text || obligation.clause_text) && (
            <div className="card card-p">
              <div className="row" style={{ gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
                <span className="sec-t">{t('obligation.sourceFromContract')}</span>
                <AiTag />
                <span className="grow" />
                {obligation.clause_type && (
                  <Tag>
                    {t(`clauses.${obligation.clause_type}`, {
                      defaultValue: obligation.clause_type.replace('_', ' '),
                    })}
                  </Tag>
                )}
                {obligation.clause_risk_level && (
                  <Pill tone={RISK_TONE[obligation.clause_risk_level] || 'n'}>
                    {t('contract.riskLabel', {
                      level: t(`risk.${obligation.clause_risk_level}`, {
                        defaultValue: obligation.clause_risk_level,
                      }),
                    })}
                  </Pill>
                )}
              </div>
              <p
                className="muted"
                style={{
                  fontSize: 'var(--fs-md)',
                  lineHeight: 1.6,
                  paddingLeft: 12,
                  borderLeft: '2px solid var(--b)',
                  whiteSpace: 'pre-wrap',
                }}
              >
                "{obligation.source_text || obligation.clause_text}"
              </p>
              {(obligation.clause_page_number || obligation.clause_section_number) && (
                <div className="row mono faint" style={{ gap: 10, marginTop: 8, fontSize: 'var(--fs-xs)' }}>
                  {obligation.clause_page_number && (
                    <span className="row" style={{ gap: 4 }}>
                      <DocumentTextIcon style={{ width: 12, height: 12 }} aria-hidden />
                      {t('obligation.page', { number: obligation.clause_page_number })}
                    </span>
                  )}
                  {obligation.clause_section_number && (
                    <span className="row" style={{ gap: 4 }}>
                      <HashtagIcon style={{ width: 12, height: 12 }} aria-hidden />
                      {t('obligation.section', { number: obligation.clause_section_number })}
                    </span>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="col" style={{ gap: 16 }}>
          {/* Source contract */}
          <div className="card card-p">
            <div className="sec-t" style={{ marginBottom: 10 }}>{t('obligation.sourceContract')}</div>
            <div className="col" style={{ gap: 12 }}>
              <div>
                <div className="faint" style={{ fontSize: 'var(--fs-sm)', marginBottom: 2 }}>
                  {t('obligation.document')}
                </div>
                <div style={{ fontSize: 'var(--fs-md)', fontWeight: 500, overflowWrap: 'anywhere' }}>
                  {obligation.contract_filename}
                </div>
              </div>
              {obligation.counterparty && (
                <div>
                  <div className="faint" style={{ fontSize: 'var(--fs-sm)', marginBottom: 2 }}>
                    {t('contracts.counterparty')}
                  </div>
                  <div style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>{obligation.counterparty}</div>
                </div>
              )}
              {obligation.contract_type && (
                <div>
                  <div className="faint" style={{ fontSize: 'var(--fs-sm)', marginBottom: 2 }}>
                    {t('obligation.contractType')}
                  </div>
                  <div style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                    {obligation.contract_type.toUpperCase()}
                  </div>
                </div>
              )}
              <div className="divider" />
              <Button
                variant="primary"
                style={{ width: '100%' }}
                onClick={() => navigate(`/contracts/${obligation.contract_id}`)}
              >
                {t('obligation.viewFullContract')}
              </Button>
            </div>
          </div>

          {/* RAG status */}
          {obligation.rag_status && (
            <div className="card card-p">
              <div className="row" style={{ gap: 8 }}>
                <Pill tone={RAG_META[ragKey].tone}>
                  {t(`obligation.rag.${ragKey}.label`, { defaultValue: RAG_META[ragKey].label })}
                </Pill>
                <span className="muted" style={{ fontSize: 'var(--fs-sm)' }}>
                  {t(`obligation.rag.${ragKey}.description`, { defaultValue: RAG_META[ragKey].description })}
                </span>
              </div>
              {obligation.last_compliance_date && (
                <div className="faint" style={{ fontSize: 'var(--fs-sm)', marginTop: 8 }}>
                  {t('obligation.lastCompliance', { date: formatDate(obligation.last_compliance_date) })}
                </div>
              )}
            </div>
          )}

          {/* Compliance evidence */}
          <div className="card card-p">
            <div className="row" style={{ marginBottom: 10 }}>
              <span className="sec-t grow">{t('obligation.complianceEvidence')}</span>
              <Button variant="ghost" size="sm" icon={DocumentArrowUpIcon} onClick={() => setShowEvidenceDrawer(true)}>
                {t('obligation.addEvidence')}
              </Button>
            </div>
            {evidenceEntries.length > 0 ? (
              <div className="col">
                {evidenceEntries.map((entry: string, idx: number) => {
                  const fileMatch = entry.match(/\[File:\s*(.+?)\]/)
                  const fileName = fileMatch?.[1]
                  const label = fileMatch ? entry.replace(fileMatch[0], '').trim() : entry
                  return (
                    <div
                      key={idx}
                      className="row"
                      style={{
                        gap: 8,
                        alignItems: 'flex-start',
                        padding: '9px 0',
                        borderBottom: idx < evidenceEntries.length - 1 ? '1px solid var(--b)' : 0,
                        fontSize: 'var(--fs-md)',
                      }}
                    >
                      <CheckCircleIcon
                        style={{ width: 15, height: 15, flexShrink: 0, marginTop: 2, color: 'var(--ok)' }}
                        aria-hidden
                      />
                      <span className="grow" style={{ lineHeight: 1.5 }}>{label}</span>
                      {fileName && (
                        <button
                          type="button"
                          onClick={() => viewEvidenceFile(fileName)}
                          style={{
                            border: 0,
                            background: 'none',
                            cursor: 'pointer',
                            color: 'var(--p)',
                            fontSize: 'var(--fs-sm)',
                            fontWeight: 600,
                            whiteSpace: 'nowrap',
                            flexShrink: 0,
                            padding: 0,
                          }}
                        >
                          {t('obligation.viewFile', { defaultValue: 'View file' })}
                        </button>
                      )}
                    </div>
                  )
                })}
              </div>
            ) : (
              <EmptyState
                icon={DocumentArrowUpIcon}
                title={t('obligation.noEvidence')}
                action={
                  <Button variant="secondary" size="sm" onClick={() => setShowEvidenceDrawer(true)}>
                    {t('obligation.uploadEvidence')}
                  </Button>
                }
              />
            )}
            {obligation.compliance_notes && (
              <>
                <div className="divider" style={{ margin: '12px 0' }} />
                <div className="faint" style={{ fontSize: 'var(--fs-sm)', marginBottom: 2 }}>
                  {t('obligation.complianceNotes')}
                </div>
                <p className="muted" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>
                  {obligation.compliance_notes}
                </p>
              </>
            )}
          </div>

          {/* Review — close out or assess the obligation (write roles only) */}
          {canReview && (
            <div className="card card-p">
              <div className="sec-t">{t('obligation.review')}</div>
              <div className="faint" style={{ fontSize: 'var(--fs-sm)', marginTop: 3, marginBottom: 12 }}>
                {t('obligation.reviewHint')}
              </div>
              <div className="col" style={{ gap: 14 }}>
                <Select
                  label={t('obligation.assignedTo')}
                  hint={t('obligation.assignHint')}
                  value={obligation.assigned_user_id || ''}
                  disabled={reviewBusy}
                  onChange={(e) => assignMutation.mutate(e.target.value || null)}
                  options={[
                    { value: '', label: t('obligation.unassigned', { defaultValue: 'Unassigned' }) },
                    ...(assignableUsers || []).map((u) => ({
                      value: u.id,
                      label: [u.first_name, u.last_name].filter(Boolean).join(' ') || u.username,
                    })),
                  ]}
                />
                <div>
                  <div className="lbl">{t('obligation.setStatus')}</div>
                  <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => statusMutation.mutate('in_progress')}
                      disabled={reviewBusy || displayStatus === 'in_progress'}
                    >
                      {t('obligation.status.in_progress', { defaultValue: 'In progress' })}
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={CheckCircleIcon}
                      onClick={() => statusMutation.mutate('completed')}
                      disabled={reviewBusy || obligation.status === 'completed'}
                    >
                      {t('obligation.markFulfilled')}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => statusMutation.mutate('waived')}
                      disabled={reviewBusy || obligation.status === 'waived'}
                    >
                      {t('obligation.status.waived', { defaultValue: 'Waive' })}
                    </Button>
                  </div>
                </div>
                <div>
                  <div className="lbl">{t('obligation.assessRag')}</div>
                  <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
                    {(['green', 'amber', 'red'] as const).map((rag) => (
                      <Chip
                        key={rag}
                        on={obligation.rag_status === rag}
                        disabled={reviewBusy || obligation.rag_status === rag}
                        onClick={() => ragMutation.mutate(rag)}
                      >
                        <i
                          style={{
                            width: 7,
                            height: 7,
                            borderRadius: '50%',
                            background: rag === 'green' ? 'var(--ok)' : rag === 'amber' ? 'var(--wa)' : 'var(--da)',
                            flexShrink: 0,
                          }}
                        />
                        {t(`obligation.rag.${rag}.label`, { defaultValue: RAG_META[rag].label })}
                      </Chip>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Evidence upload drawer */}
      <Drawer
        open={showEvidenceDrawer}
        title={t('obligation.uploadComplianceEvidence')}
        sub={obligation.contract_filename}
        onClose={() => setShowEvidenceDrawer(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setShowEvidenceDrawer(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="primary"
              className="grow"
              icon={DocumentArrowUpIcon}
              disabled={(!evidenceDescription.trim() && !evidenceFile) || uploadEvidenceMutation.isPending}
              onClick={handleEvidenceSubmit}
            >
              {uploadEvidenceMutation.isPending ? t('obligation.uploading') : t('obligation.uploadEvidence')}
            </Button>
          </>
        }
      >
        <div className="col" style={{ gap: 14 }}>
          <div>
            <label className="lbl">{t('obligation.evidenceDescription')}</label>
            <div className="inp" style={{ height: 'auto', padding: 10, alignItems: 'flex-start' }}>
              <textarea
                rows={3}
                value={evidenceDescription}
                onChange={(e) => setEvidenceDescription(e.target.value)}
                placeholder={t('obligation.evidencePlaceholder')}
                style={{ resize: 'vertical', lineHeight: 1.55 }}
              />
            </div>
          </div>
          <Field
            label={t('obligation.evidenceDate')}
            type="date"
            value={evidenceDate}
            onChange={(e) => setEvidenceDate(e.target.value)}
          />
          <div>
            <label className="lbl">{t('obligation.attachmentOptional')}</label>
            <input
              type="file"
              className="input"
              onChange={(e) => setEvidenceFile(e.target.files?.[0] || null)}
            />
            {evidenceFile && (
              <div className="hint">{evidenceFile.name}</div>
            )}
          </div>
          {evidenceError && (
            <div className="banner banner-da">
              <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
              <span className="grow">{evidenceError}</span>
            </div>
          )}
        </div>
      </Drawer>
    </div>
  )
}
