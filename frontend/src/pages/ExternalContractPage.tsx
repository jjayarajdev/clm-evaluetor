/* External contract portal — Direction B restyle. Token-gated PUBLIC page
   rendered outside MainLayout: standalone header bar (wordmark on var(--s)),
   content on var(--pg), cards/pills/tabs from '@/components/ui'. All token
   validation, queries, mutations, download and comment flows unchanged. */
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  DocumentTextIcon,
  ArrowDownTrayIcon,
  ChatBubbleLeftIcon,
  PaperAirplaneIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  BellAlertIcon,
  ChartBarIcon,
  ExclamationCircleIcon,
  CheckCircleIcon,
  ArrowPathIcon,
  EyeIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import axios from 'axios'
import { formatDate } from '@/lib/utils'
import { Avatar, Button, Chip, EmptyState, IconButton, Pill, Tabs, Tag, useToast } from '@/components/ui'
import type { PillTone, TabDef } from '@/components/ui'

const apiBase = '/api/external'

// ── Types ──────────────────────────────────────────────────────────

interface SharedContract {
  id: string
  filename: string
  contract_type?: string
  counterparty?: string
  can_download: boolean
  can_comment: boolean
  expires_at?: string
}

interface Clause {
  id: string
  clause_type?: string
  title?: string
  text?: string
  section_number?: string
  risk_level?: string
}

interface ObligationItem {
  id: string
  description: string
  obligation_type?: string
  responsible_party?: string
  deadline?: string
  status?: string
  priority?: string
  is_critical?: boolean
  consequence?: string
}

interface SLAItem {
  id: string
  sla_name: string
  sla_description?: string
  metric_type?: string
  metric_unit?: string
  target_value?: number
  target_operator?: string
  severity?: string
  current_compliance_rate?: number
  measurement_period?: string
  has_penalty?: boolean
  penalty_description?: string
}

interface ContractDetails {
  id: string
  filename: string
  contract_type?: string
  counterparty?: string
  effective_date?: string
  expiration_date?: string
  contract_value?: number
  total_value?: number
  currency?: string
  jurisdiction?: string
  governing_law?: string
  status: string
  risk_level?: string
  risk_score?: number
  auto_renewal?: boolean
  notice_period_days?: number
  summary?: string
  clauses: Clause[]
  obligations: ObligationItem[]
  slas: SLAItem[]
  can_download: boolean
  can_comment: boolean
  shared_message?: string
}

interface Comment {
  id: string
  content: string
  author_name: string
  is_internal_author?: boolean
  section_reference?: string
  clause_id?: string
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
  contracts: SharedContract[]
  token_expires_at: string
}

interface GovernanceKPI {
  id: string
  name: string
  description?: string
  category?: string
  measurement_type?: string
  target_value?: number
  weight?: number
  is_perception_based?: boolean
  recent_scores?: Array<{ id: string; score: number; period: string; is_internal: boolean; scored_at?: string }>
  latest_gap?: {
    period: string
    internal_score?: number
    external_score?: number
    gap?: number
    gap_severity?: string
    requires_action?: boolean
  }
}

interface GovernanceImprovement {
  id: string
  title: string
  description?: string
  source?: string
  priority?: string
  status?: string
  kpi_name?: string
  due_date?: string
  target_outcome?: string
  actual_outcome?: string
  impact_score?: number
  created_at?: string
}

interface GovernanceData {
  has_governance: boolean
  relationship?: {
    id: string
    name?: string
    relationship_type?: string
    status?: string
    org_a_name?: string
    org_b_name?: string
    health_score?: number
    governance_tier?: string
  }
  kpis: GovernanceKPI[]
  improvements: GovernanceImprovement[]
}

type TabId = 'document' | 'clauses' | 'obligations' | 'sla' | 'comments' | 'governance'

// ── Tone maps (design tokens only) ─────────────────────────────────

const riskTone = (level?: string): PillTone =>
  level === 'high' || level === 'critical' ? 'da' : level === 'medium' ? 'wa' : 'ok'

const priorityTone = (priority?: string): PillTone =>
  priority === 'critical' ? 'da' : priority === 'high' || priority === 'medium' ? 'wa' : 'n'

const SEVERITY_TONE: Record<string, PillTone> = {
  critical: 'da',
  significant: 'wa',
  moderate: 'wa',
  minor: 'ok',
  aligned: 'ok',
}

const STATUS_TONE: Record<string, PillTone> = {
  open: 'in',
  in_progress: 'p',
  blocked: 'da',
  completed: 'ok',
  cancelled: 'n',
}

const CATEGORY_LABELS: Record<string, string> = {
  service_delivery: 'Service Delivery',
  quality: 'Quality',
  timeliness: 'Timeliness',
  communication: 'Communication',
  innovation: 'Innovation',
  cost_efficiency: 'Cost Efficiency',
  compliance: 'Compliance',
  satisfaction: 'Satisfaction',
  other: 'Other',
}

function Spinner({ size = 26 }: { size?: number }) {
  return <ArrowPathIcon className="spin" style={{ width: size, height: size, color: 'var(--f)' }} aria-hidden />
}

// ── Main Component ─────────────────────────────────────────────────

export default function ExternalContractPage() {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [selectedContractId, setSelectedContractId] = useState<string | null>(null)
  const [newComment, setNewComment] = useState('')
  const [activeTab, setActiveTab] = useState<TabId>('document')
  const [commentingOn, setCommentingOn] = useState<string | null>(null) // section_reference of item being commented on
  const [itemComment, setItemComment] = useState('')

  const accessToken = searchParams.get('token') || ''

  // ── Validate token ─────────────────────────────────────────────

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

  const effectiveContractId = selectedContractId
    || (validation?.contracts?.length === 1 ? validation.contracts[0].id : null)

  // ── Load contract details ──────────────────────────────────────

  const { data: contract, isLoading: loadingContract } = useQuery({
    queryKey: ['external-contract', accessToken, effectiveContractId],
    queryFn: async () => {
      const response = await axios.get<ContractDetails>(
        `${apiBase}/contracts/${effectiveContractId}`,
        { params: { token: accessToken } }
      )
      return response.data
    },
    enabled: !!effectiveContractId && !!validation,
  })

  // ── Load comments ──────────────────────────────────────────────

  const { data: commentsData } = useQuery({
    queryKey: ['external-comments', accessToken, effectiveContractId],
    queryFn: async () => {
      const response = await axios.get<{ items: Comment[]; total: number }>(
        `${apiBase}/contracts/${effectiveContractId}/comments`,
        { params: { token: accessToken } }
      )
      return response.data
    },
    enabled: !!effectiveContractId && !!validation,
  })

  // ── Load governance data ───────────────────────────────────────

  const { data: governanceData } = useQuery({
    queryKey: ['external-governance', accessToken, effectiveContractId],
    queryFn: async () => {
      const response = await axios.get<GovernanceData>(
        `${apiBase}/contracts/${effectiveContractId}/governance`,
        { params: { token: accessToken } }
      )
      return response.data
    },
    enabled: !!effectiveContractId && !!validation,
  })

  const allComments = commentsData?.items || []

  // Helper: get comments for a specific section_reference
  const getCommentsFor = (ref: string) => allComments.filter(c => c.section_reference === ref)

  // ── Add comment (supports section_reference) ───────────────────

  const addCommentMutation = useMutation({
    mutationFn: async ({ content, section_reference, clause_id }: {
      content: string; section_reference?: string; clause_id?: string
    }) => {
      const response = await axios.post(
        `${apiBase}/contracts/${effectiveContractId}/comments`,
        { content, section_reference, clause_id },
        { params: { token: accessToken } }
      )
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['external-comments'] })
      setNewComment('')
      setItemComment('')
      setCommentingOn(null)
    },
  })

  useEffect(() => {
    if (contract) {
      setActiveTab('document')
    }
  }, [contract?.id])

  // ── Handlers ───────────────────────────────────────────────────

  const handleDownload = async () => {
    try {
      const response = await axios.get(
        `${apiBase}/contracts/${effectiveContractId}/download`,
        { params: { token: accessToken }, responseType: 'blob' }
      )
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', contract?.filename || 'contract.pdf')
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch {
      toast({ text: t('external.downloadFailed'), error: true })
    }
  }

  const handleSubmitGeneralComment = (e: React.FormEvent) => {
    e.preventDefault()
    if (newComment.trim()) {
      addCommentMutation.mutate({ content: newComment.trim() })
    }
  }

  const handleSubmitItemComment = (sectionRef: string, clauseId?: string) => {
    if (itemComment.trim()) {
      addCommentMutation.mutate({
        content: itemComment.trim(),
        section_reference: sectionRef,
        clause_id: clauseId,
      })
    }
  }

  // ── Loading / Error / No token ─────────────────────────────────

  if (validating) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--pg)' }}>
        <div className="col items-center" style={{ gap: 12 }}>
          <Spinner size={28} />
          <p className="muted">{t('external.validatingAccess')}</p>
        </div>
      </div>
    )
  }

  if (validationError || !accessToken) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4" style={{ background: 'var(--pg)' }}>
        <div className="card w-full" style={{ maxWidth: 420 }}>
          <EmptyState
            icon={ExclamationTriangleIcon}
            title={t('external.accessDenied')}
            body={!accessToken ? t('external.noToken') : t('external.invalidLink')}
          />
        </div>
      </div>
    )
  }

  // ── Contract List ──────────────────────────────────────────────

  if (!effectiveContractId && validation?.contracts && validation.contracts.length > 1) {
    return (
      <div className="min-h-screen" style={{ background: 'var(--pg)' }}>
        <PortalHeader user={validation.external_user} expiresAt={validation.token_expires_at} />
        <main className="max-w-5xl mx-auto px-4 py-8">
          <h2 style={{ fontSize: 'var(--fs-xl)', fontWeight: 600, letterSpacing: '-.2px' }}>{t('external.sharedContracts')}</h2>
          <p className="muted" style={{ fontSize: 'var(--fs-md)', marginTop: 2, marginBottom: 20 }}>
            {t('external.contractsSharedWithYou', { count: validation.contracts.length })}
          </p>
          <div className="col" style={{ gap: 10 }}>
            {validation.contracts.map((c) => (
              <button key={c.id}
                onClick={() => { setSelectedContractId(c.id); setActiveTab('document'); }}
                className="card card-p w-full text-left transition-shadow hover:shadow-[var(--sh-sm)]"
              >
                <div className="row" style={{ gap: 14 }}>
                  <span
                    style={{
                      width: 40, height: 40, borderRadius: 'var(--r-md)', flexShrink: 0,
                      background: 'var(--p-f)', color: 'var(--p)', display: 'grid', placeItems: 'center',
                    }}
                  >
                    <DocumentTextIcon style={{ width: 20, height: 20 }} aria-hidden />
                  </span>
                  <div className="grow">
                    <p className="trunc" style={{ fontWeight: 600 }}>{c.filename}</p>
                    {c.counterparty && <p className="muted" style={{ fontSize: 'var(--fs-sm)', marginTop: 1 }}>{c.counterparty}</p>}
                    <div className="row" style={{ gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
                      {c.contract_type && <Tag><span className="capitalize">{c.contract_type.replace(/_/g, ' ')}</span></Tag>}
                      {c.expires_at && (
                        <span className="faint inline-flex items-center gap-1" style={{ fontSize: 'var(--fs-xs)' }}>
                          <ClockIcon style={{ width: 12, height: 12 }} aria-hidden />
                          {t('external.expires', { date: formatDate(c.expires_at) })}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="row" style={{ gap: 6, flexShrink: 0 }}>
                    {c.can_download && (
                      <Pill tone="ok" dot={false}>
                        <ArrowDownTrayIcon style={{ width: 11, height: 11 }} aria-hidden /> {t('external.download')}
                      </Pill>
                    )}
                    {c.can_comment && (
                      <Pill tone="in" dot={false}>
                        <ChatBubbleLeftIcon style={{ width: 11, height: 11 }} aria-hidden /> {t('external.comment')}
                      </Pill>
                    )}
                    <ChevronRightIcon style={{ width: 16, height: 16, color: 'var(--f)' }} aria-hidden />
                  </div>
                </div>
              </button>
            ))}
          </div>
        </main>
        <PortalFooter />
      </div>
    )
  }

  if (!validation?.contracts?.length) {
    return (
      <div className="min-h-screen" style={{ background: 'var(--pg)' }}>
        <PortalHeader user={validation?.external_user} expiresAt={validation?.token_expires_at} />
        <main className="max-w-5xl mx-auto px-4 py-8">
          <div className="card">
            <EmptyState icon={DocumentTextIcon} title={t('external.noContractsShared')} />
          </div>
        </main>
        <PortalFooter />
      </div>
    )
  }

  // ── Contract Detail ────────────────────────────────────────────

  const showBackButton = validation?.contracts && validation.contracts.length > 1
  const canComment = contract?.can_comment ?? false

  const tabDefs: TabDef<TabId>[] = contract
    ? [
        { value: 'document', label: t('external.document'), icon: EyeIcon },
        { value: 'clauses', label: t('external.keyClauses'), icon: DocumentTextIcon, count: contract.clauses?.length || undefined },
        { value: 'obligations', label: t('contract.obligations'), icon: BellAlertIcon, count: contract.obligations?.length || undefined },
        { value: 'sla', label: t('contract.slas'), icon: ChartBarIcon, count: contract.slas?.length || undefined },
        ...(governanceData?.has_governance
          ? [{ value: 'governance' as TabId, label: t('external.governance'), icon: ShieldCheckIcon, count: governanceData.kpis.length || undefined }]
          : []),
        { value: 'comments', label: t('external.allComments'), icon: ChatBubbleLeftIcon, count: commentsData?.total || undefined },
      ]
    : []

  return (
    <div className="min-h-screen" style={{ background: 'var(--pg)' }}>
      <PortalHeader user={validation?.external_user} expiresAt={validation?.token_expires_at} />
      <main className="max-w-5xl mx-auto px-4 py-8">
        {showBackButton && (
          <Button
            variant="ghost"
            size="sm"
            icon={ChevronLeftIcon}
            onClick={() => { setSelectedContractId(null); setActiveTab('document'); }}
            style={{ marginBottom: 14 }}
          >
            {t('external.allContracts')}
          </Button>
        )}

        {loadingContract ? (
          <div className="flex justify-center py-16"><Spinner size={28} /></div>
        ) : contract ? (
          <>
            {/* Header Card */}
            <div className="card">
              <div className="card-p" style={{ borderBottom: '1px solid var(--b)' }}>
                <div className="row" style={{ alignItems: 'flex-start', gap: 14 }}>
                  <span
                    style={{
                      width: 44, height: 44, borderRadius: 'var(--r-md)', flexShrink: 0,
                      background: 'var(--p-f)', color: 'var(--p)', display: 'grid', placeItems: 'center',
                    }}
                  >
                    <DocumentTextIcon style={{ width: 22, height: 22 }} aria-hidden />
                  </span>
                  <div className="grow">
                    <h2 style={{ fontSize: 'var(--fs-xl)', fontWeight: 600, letterSpacing: '-.2px' }}>{contract.filename}</h2>
                    {contract.counterparty && (
                      <p className="muted" style={{ fontSize: 'var(--fs-md)', marginTop: 2 }}>
                        {t('contracts.counterparty')}: {contract.counterparty}
                      </p>
                    )}
                    <div className="row" style={{ gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                      {contract.contract_type && <Tag><span className="capitalize">{contract.contract_type.replace(/_/g, ' ')}</span></Tag>}
                      {contract.risk_level && (
                        <Pill tone={riskTone(contract.risk_level)}>
                          {t('contract.riskLabel', { level: t(`risk.${contract.risk_level}`, { defaultValue: contract.risk_level }) })}
                        </Pill>
                      )}
                      {contract.auto_renewal && (
                        <Pill tone="in" dot={false}>
                          <ArrowPathIcon style={{ width: 11, height: 11 }} aria-hidden /> {t('external.autoRenewal')}
                        </Pill>
                      )}
                      <Pill tone={contract.status === 'completed' ? 'ok' : 'n'}>
                        <span className="capitalize">{t(`status.${contract.status}`, { defaultValue: contract.status })}</span>
                      </Pill>
                    </div>
                  </div>
                  {contract.can_download && (
                    <Button variant="primary" icon={ArrowDownTrayIcon} onClick={handleDownload} style={{ flexShrink: 0 }}>
                      {t('external.download')}
                    </Button>
                  )}
                </div>
              </div>
              <div className="card-p grid grid-cols-2 md:grid-cols-4 gap-4">
                {contract.effective_date && <DetailCell label={t('external.effectiveDate')} value={formatDate(contract.effective_date)} />}
                {contract.expiration_date && <DetailCell label={t('external.expirationDate')} value={formatDate(contract.expiration_date)} />}
                {(contract.total_value || contract.contract_value) && <DetailCell label={t('external.totalValue')} value={`${contract.currency || 'USD'} ${(contract.total_value || contract.contract_value || 0).toLocaleString()}`} />}
                {contract.jurisdiction && <DetailCell label={t('external.jurisdiction')} value={contract.jurisdiction} />}
                {contract.governing_law && <DetailCell label={t('external.governingLaw')} value={contract.governing_law} />}
                {contract.notice_period_days != null && contract.notice_period_days > 0 && <DetailCell label={t('external.noticePeriod')} value={t('external.days', { count: contract.notice_period_days })} />}
                {contract.risk_score != null && <DetailCell label={t('external.riskScore')} value={`${contract.risk_score}/100`} />}
              </div>
              {contract.shared_message && (
                <div style={{ padding: '0 16px 16px' }}>
                  <div className="banner banner-p" style={{ fontStyle: 'italic' }}>
                    "{contract.shared_message}"
                  </div>
                </div>
              )}
            </div>

            {contract.summary && (
              <div className="card card-p" style={{ marginTop: 16 }}>
                <div className="sec-t" style={{ marginBottom: 8 }}>{t('external.contractSummary')}</div>
                <p className="muted" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.6, whiteSpace: 'pre-line' }}>{contract.summary}</p>
              </div>
            )}

            {/* Tabs */}
            <div className="card" style={{ marginTop: 16 }}>
              <Tabs tabs={tabDefs} value={activeTab} onChange={setActiveTab} style={{ padding: '0 12px' }} />

              <div className="card-p">
                {activeTab === 'document' && (
                  <DocumentPreview contractId={effectiveContractId!} accessToken={accessToken} filename={contract.filename} />
                )}
                {activeTab === 'clauses' && (
                  <ClausesSection clauses={contract.clauses} canComment={canComment}
                    commentingOn={commentingOn} setCommentingOn={setCommentingOn}
                    itemComment={itemComment} setItemComment={setItemComment}
                    onSubmitItemComment={handleSubmitItemComment} isPending={addCommentMutation.isPending}
                    getCommentsFor={getCommentsFor} />
                )}
                {activeTab === 'obligations' && (
                  <ObligationsSection obligations={contract.obligations} canComment={canComment}
                    commentingOn={commentingOn} setCommentingOn={setCommentingOn}
                    itemComment={itemComment} setItemComment={setItemComment}
                    onSubmitItemComment={handleSubmitItemComment} isPending={addCommentMutation.isPending}
                    getCommentsFor={getCommentsFor} />
                )}
                {activeTab === 'sla' && (
                  <SLASection slas={contract.slas} canComment={canComment}
                    commentingOn={commentingOn} setCommentingOn={setCommentingOn}
                    itemComment={itemComment} setItemComment={setItemComment}
                    onSubmitItemComment={handleSubmitItemComment} isPending={addCommentMutation.isPending}
                    getCommentsFor={getCommentsFor} />
                )}
                {activeTab === 'governance' && governanceData?.has_governance && (
                  <GovernanceSection data={governanceData} />
                )}
                {activeTab === 'comments' && (
                  <AllCommentsSection comments={allComments} newComment={newComment} setNewComment={setNewComment}
                    onSubmit={handleSubmitGeneralComment} isPending={addCommentMutation.isPending} canComment={canComment}
                    error={addCommentMutation.error ? t('external.postCommentFailed') : undefined} />
                )}
              </div>
            </div>
          </>
        ) : null}
      </main>
      <PortalFooter />
    </div>
  )
}


// ── Inline Comment Widget (reused on every card) ────────────────────

interface InlineCommentProps {
  sectionRef: string
  clauseId?: string
  canComment: boolean
  commentingOn: string | null
  setCommentingOn: (v: string | null) => void
  itemComment: string
  setItemComment: (v: string) => void
  onSubmitItemComment: (sectionRef: string, clauseId?: string) => void
  isPending: boolean
  comments: Comment[]
}

function InlineCommentWidget({
  sectionRef, clauseId, canComment, commentingOn, setCommentingOn,
  itemComment, setItemComment, onSubmitItemComment, isPending, comments,
}: InlineCommentProps) {
  const { t } = useTranslation()
  const isOpen = commentingOn === sectionRef
  const count = comments.length

  return (
    <div style={{ marginTop: 12 }}>
      {/* Comment toggle button */}
      <div className="row" style={{ gap: 10 }}>
        {canComment && (
          <Button
            variant="ghost"
            size="sm"
            icon={ChatBubbleLeftIcon}
            onClick={() => {
              if (isOpen) { setCommentingOn(null); setItemComment(''); }
              else { setCommentingOn(sectionRef); setItemComment(''); }
            }}
            style={isOpen ? { background: 'var(--p-f)', color: 'var(--p)' } : undefined}
          >
            {isOpen ? t('common.cancel') : t('external.comment')}
          </Button>
        )}
        {count > 0 && !isOpen && (
          <Button
            variant="ghost"
            size="sm"
            icon={ChatBubbleLeftIcon}
            onClick={() => { setCommentingOn(sectionRef); setItemComment(''); }}
          >
            {t('external.commentCount', { count })}
          </Button>
        )}
      </div>

      {/* Expanded: show existing comments + form */}
      {isOpen && (
        <div className="col" style={{ marginTop: 8, borderLeft: '2px solid var(--p-b)', paddingLeft: 12, gap: 8 }}>
          {/* Existing comments */}
          {comments.map((c) => (
            <div key={c.id} className="row" style={{ alignItems: 'flex-start', gap: 8 }}>
              <Avatar name={c.author_name || '?'} size={22} />
              <div className="grow">
                <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 'var(--fs-sm)', fontWeight: 600 }}>{c.author_name}</span>
                  <Pill tone={c.is_internal_author ? 'in' : 'p'} dot={false}>
                    {c.is_internal_author ? t('external.internal') : t('external.you')}
                  </Pill>
                  <span className="faint" style={{ fontSize: 'var(--fs-2xs)' }}>{formatDate(c.created_at)}</span>
                </div>
                <p className="muted" style={{ fontSize: 'var(--fs-sm)', marginTop: 2 }}>{c.content}</p>
              </div>
            </div>
          ))}

          {/* Input form */}
          {canComment && (
            <div className="row" style={{ alignItems: 'flex-start', gap: 8, paddingTop: 4 }}>
              <textarea
                value={itemComment}
                onChange={(e) => setItemComment(e.target.value)}
                placeholder={t('external.addYourComment')}
                rows={2}
                className="inp-flat grow resize-none"
                style={{ fontSize: 'var(--fs-sm)' }}
                autoFocus
              />
              <Button
                variant="primary"
                size="sm"
                icon={PaperAirplaneIcon}
                onClick={() => onSubmitItemComment(sectionRef, clauseId)}
                disabled={!itemComment.trim() || isPending}
                aria-label={t('external.send')}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}


// ── Sub-components ─────────────────────────────────────────────────

function PortalHeader({ user, expiresAt }: { user?: ValidateResponse['external_user']; expiresAt?: string }) {
  const { t } = useTranslation()
  return (
    <header style={{ background: 'var(--s)', borderBottom: '1px solid var(--b)' }}>
      <div className="max-w-5xl mx-auto px-4">
        <div className="row" style={{ height: 56, gap: 10 }}>
          <span
            aria-hidden
            style={{
              width: 26, height: 26, borderRadius: 7, flexShrink: 0,
              background: 'var(--p)', color: 'var(--on-p)',
              display: 'grid', placeItems: 'center',
              fontSize: 14, fontWeight: 700, lineHeight: 1,
            }}
          >
            E
          </span>
          <div className="col">
            <span style={{ fontSize: 'var(--fs-lg)', fontWeight: 600, letterSpacing: '-.2px', lineHeight: 1.2 }}>Evaluetor</span>
            <span className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('external.sharedContractPortal')}</span>
          </div>
          <span className="grow" />
          {expiresAt && (
            <span className="faint hidden sm:inline-flex items-center gap-1" style={{ fontSize: 'var(--fs-xs)' }}>
              <ClockIcon style={{ width: 13, height: 13 }} aria-hidden />
              {t('external.expires', { date: formatDate(expiresAt) })}
            </span>
          )}
          <span className="row" style={{ gap: 6 }}>
            <ShieldCheckIcon style={{ width: 16, height: 16, color: 'var(--ok)', flexShrink: 0 }} aria-hidden />
            <span className="muted hidden sm:inline trunc" style={{ fontSize: 'var(--fs-md)', maxWidth: 220 }}>
              {user?.full_name || user?.email}
            </span>
          </span>
        </div>
      </div>
    </header>
  )
}

function PortalFooter() {
  const { t } = useTranslation()
  return (
    <footer style={{ borderTop: '1px solid var(--b)', background: 'var(--s)', marginTop: 48 }}>
      <div className="max-w-5xl mx-auto px-4 py-6 text-center faint" style={{ fontSize: 'var(--fs-sm)' }}>
        {t('external.poweredBy')}
      </div>
    </footer>
  )
}

function DetailCell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="muted" style={{ fontSize: 'var(--fs-sm)' }}>{label}</p>
      <p style={{ fontWeight: 500, marginTop: 2 }}>{value}</p>
    </div>
  )
}

// ── Document Preview ────────────────────────────────────────────────

function DocumentPreview({ contractId, accessToken, filename }: { contractId: string; accessToken: string; filename: string }) {
  const { t } = useTranslation()
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [fullscreen, setFullscreen] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true); setError(null)
    axios.get(`${apiBase}/contracts/${contractId}/view`, { params: { token: accessToken }, responseType: 'blob' })
      .then((response) => {
        if (cancelled) return
        setPdfUrl(URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' })))
        setLoading(false)
      }).catch(() => { if (!cancelled) { setError(t('external.previewLoadFailed')); setLoading(false) } })
    return () => { cancelled = true; if (pdfUrl) URL.revokeObjectURL(pdfUrl) }
  }, [contractId, accessToken])

  const isPdf = filename?.toLowerCase().endsWith('.pdf')

  if (loading) {
    return (
      <div className="col items-center py-16" style={{ gap: 12 }}>
        <Spinner size={28} />
        <p className="muted" style={{ fontSize: 'var(--fs-sm)' }}>{t('external.loadingPreview')}</p>
      </div>
    )
  }
  if (error || !pdfUrl) {
    return (
      <EmptyState
        icon={DocumentTextIcon}
        title={error || t('external.previewNotAvailable')}
        body={t('external.useDownloadButton')}
      />
    )
  }
  if (!isPdf) return <EmptyState icon={DocumentTextIcon} title={t('external.pdfOnly')} />

  if (fullscreen) {
    return (
      <>
        <div className="fixed inset-0 z-50 col" style={{ background: 'var(--pg)' }}>
          <div className="row px-4" style={{ height: 48, background: 'var(--s)', borderBottom: '1px solid var(--b)', flexShrink: 0 }}>
            <p className="trunc grow" style={{ fontWeight: 600, fontSize: 'var(--fs-md)' }}>{filename}</p>
            <IconButton icon={XMarkIcon} label={t('common.close', { defaultValue: 'Close' })} onClick={() => setFullscreen(false)} />
          </div>
          <div className="grow"><iframe src={`${pdfUrl}#toolbar=1&navpanes=1`} className="w-full h-full border-0" title={t('external.contractDocument')} /></div>
        </div>
        <div className="h-[600px]" />
      </>
    )
  }

  return (
    <div>
      <div className="row" style={{ marginBottom: 10 }}>
        <p className="muted grow trunc" style={{ fontSize: 'var(--fs-sm)' }}>{filename}</p>
        <Button variant="ghost" size="sm" icon={EyeIcon} onClick={() => setFullscreen(true)}>
          {t('external.fullscreen')}
        </Button>
      </div>
      <div style={{ border: '1px solid var(--b)', borderRadius: 'var(--r-lg)', overflow: 'hidden', background: 'var(--s2)' }}>
        <iframe src={`${pdfUrl}#toolbar=1&navpanes=0&scrollbar=1`} className="w-full border-0" style={{ height: 700 }} title={t('external.contractDocument')} />
      </div>
    </div>
  )
}

// ── Shared props for commentable sections ───────────────────────────

interface CommentableProps {
  canComment: boolean
  commentingOn: string | null
  setCommentingOn: (v: string | null) => void
  itemComment: string
  setItemComment: (v: string) => void
  onSubmitItemComment: (sectionRef: string, clauseId?: string) => void
  isPending: boolean
  getCommentsFor: (ref: string) => Comment[]
}

// ── Clauses ────────────────────────────────────────────────────────

function ClausesSection({ clauses, ...cp }: { clauses: Clause[] } & CommentableProps) {
  const { t } = useTranslation()
  if (!clauses?.length) return <EmptyState icon={DocumentTextIcon} title={t('external.noClauses')} />

  return (
    <div className="col" style={{ gap: 12 }}>
      {clauses.map((clause) => {
        const ref = `clause:${clause.id}`
        return (
          <div key={clause.id} className="card card-p">
            <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
              {clause.section_number && <Tag>{clause.section_number}</Tag>}
              {clause.clause_type && (
                <Pill tone="p" dot={false}>
                  <span className="capitalize">{t(`clauses.${clause.clause_type}`, { defaultValue: clause.clause_type.replace(/_/g, ' ') })}</span>
                </Pill>
              )}
              {clause.risk_level && (
                <Pill tone={riskTone(clause.risk_level)}>
                  <span className="capitalize">{t(`risk.${clause.risk_level}`, { defaultValue: clause.risk_level })}</span>
                </Pill>
              )}
            </div>
            {clause.title && <p style={{ fontWeight: 600, marginBottom: 4 }}>{clause.title}</p>}
            <p className="muted" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.6, whiteSpace: 'pre-line' }}>{clause.text}</p>
            <InlineCommentWidget sectionRef={ref} clauseId={clause.id} comments={cp.getCommentsFor(ref)}
              canComment={cp.canComment} commentingOn={cp.commentingOn} setCommentingOn={cp.setCommentingOn}
              itemComment={cp.itemComment} setItemComment={cp.setItemComment}
              onSubmitItemComment={cp.onSubmitItemComment} isPending={cp.isPending} />
          </div>
        )
      })}
    </div>
  )
}

// ── Obligations ────────────────────────────────────────────────────

function ObligationsSection({ obligations, ...cp }: { obligations: ObligationItem[] } & CommentableProps) {
  const { t } = useTranslation()
  if (!obligations?.length) return <EmptyState icon={BellAlertIcon} title={t('external.noObligations')} />

  const now = new Date()
  const sorted = [...obligations].sort((a, b) => {
    if (!a.deadline) return 1; if (!b.deadline) return -1
    return new Date(a.deadline).getTime() - new Date(b.deadline).getTime()
  })

  return (
    <div className="col" style={{ gap: 12 }}>
      {sorted.map((ob) => {
        const isOverdue = ob.deadline && new Date(ob.deadline) < now && ob.status !== 'completed'
        const ref = `obligation:${ob.id}`
        return (
          <div
            key={ob.id}
            className="card card-p"
            style={isOverdue ? { borderColor: 'var(--da-b)', background: 'var(--da-f)' } : undefined}
          >
            <div className="row" style={{ alignItems: 'flex-start', gap: 14 }}>
              <div className="grow">
                <div className="row" style={{ gap: 6 }}>
                  {ob.is_critical && <ExclamationCircleIcon style={{ width: 16, height: 16, color: 'var(--da)', flexShrink: 0 }} aria-hidden />}
                  <p style={{ fontWeight: 600 }}>{ob.description}</p>
                </div>
                <div className="row" style={{ gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                  {ob.obligation_type && <Tag><span className="capitalize">{t(`obligation.type.${ob.obligation_type}`, { defaultValue: ob.obligation_type.replace(/_/g, ' ') })}</span></Tag>}
                  {ob.responsible_party && <Pill tone="in" dot={false}>{ob.responsible_party}</Pill>}
                  {ob.priority && (
                    <Pill tone={priorityTone(ob.priority)}>
                      <span className="capitalize">{t(`risk.${ob.priority}`, { defaultValue: ob.priority })}</span>
                    </Pill>
                  )}
                </div>
                {ob.consequence && <p className="faint" style={{ fontSize: 'var(--fs-sm)', marginTop: 8, fontStyle: 'italic' }}>{t('external.consequence', { text: ob.consequence })}</p>}
              </div>
              <div className="text-right" style={{ flexShrink: 0 }}>
                {ob.deadline && (
                  <p className="num" style={{ fontSize: 'var(--fs-md)', fontWeight: 600, color: isOverdue ? 'var(--da)' : 'var(--t)' }}>
                    {isOverdue ? t('external.overdue') : formatDate(ob.deadline)}
                  </p>
                )}
                <p className="capitalize" style={{ fontSize: 'var(--fs-sm)', marginTop: 4, color: ob.status === 'completed' ? 'var(--ok)' : 'var(--m)' }}>
                  {t(`status.${ob.status || 'pending'}`, { defaultValue: ob.status || 'pending' })}
                </p>
              </div>
            </div>
            <InlineCommentWidget sectionRef={ref} comments={cp.getCommentsFor(ref)}
              canComment={cp.canComment} commentingOn={cp.commentingOn} setCommentingOn={cp.setCommentingOn}
              itemComment={cp.itemComment} setItemComment={cp.setItemComment}
              onSubmitItemComment={cp.onSubmitItemComment} isPending={cp.isPending} />
          </div>
        )
      })}
    </div>
  )
}

// ── SLAs ───────────────────────────────────────────────────────────

function SLASection({ slas, ...cp }: { slas: SLAItem[] } & CommentableProps) {
  const { t } = useTranslation()
  if (!slas?.length) return <EmptyState icon={ChartBarIcon} title={t('external.noSlas')} />

  return (
    <div className="col" style={{ gap: 12 }}>
      {slas.map((sla) => {
        const compliance = sla.current_compliance_rate
        const tone = compliance == null ? null : compliance >= 95 ? 'var(--ok)' : compliance >= 80 ? 'var(--wa)' : 'var(--da)'
        const ComplianceIcon = compliance == null ? null : compliance >= 95 ? CheckCircleIcon : compliance >= 80 ? ExclamationTriangleIcon : ExclamationCircleIcon
        const ref = `sla:${sla.id}`

        return (
          <div key={sla.id} className="card card-p">
            <div className="row" style={{ alignItems: 'flex-start', gap: 14 }}>
              <div className="grow">
                <p style={{ fontWeight: 600 }}>{sla.sla_name}</p>
                {sla.sla_description && <p className="muted" style={{ fontSize: 'var(--fs-sm)', marginTop: 4 }}>{sla.sla_description}</p>}
                <div className="row" style={{ gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                  {sla.metric_type && <Tag><span className="capitalize">{sla.metric_type.replace(/_/g, ' ')}</span></Tag>}
                  {sla.target_value != null && (
                    <Pill tone="in" dot={false}>
                      {t('external.target', { value: `${sla.target_operator || '>='} ${sla.target_value}${sla.metric_unit || ''}` })}
                    </Pill>
                  )}
                  {sla.severity && (
                    <Pill tone={priorityTone(sla.severity)}>
                      <span className="capitalize">{t(`risk.${sla.severity}`, { defaultValue: sla.severity })}</span>
                    </Pill>
                  )}
                  {sla.measurement_period && <Tag><span className="capitalize">{sla.measurement_period}</span></Tag>}
                </div>
                {sla.has_penalty && sla.penalty_description && (
                  <p className="faint" style={{ fontSize: 'var(--fs-sm)', marginTop: 8, fontStyle: 'italic' }}>{t('external.penalty', { text: sla.penalty_description })}</p>
                )}
              </div>
              <div style={{ flexShrink: 0 }}>
                {compliance != null && tone && ComplianceIcon ? (
                  <span className="row" style={{ gap: 6 }}>
                    <ComplianceIcon style={{ width: 18, height: 18, color: tone }} aria-hidden />
                    <span className="num" style={{ fontSize: 'var(--fs-lg)', fontWeight: 700, color: tone }}>{compliance.toFixed(1)}%</span>
                  </span>
                ) : (
                  <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>{t('external.noData')}</span>
                )}
              </div>
            </div>
            <InlineCommentWidget sectionRef={ref} comments={cp.getCommentsFor(ref)}
              canComment={cp.canComment} commentingOn={cp.commentingOn} setCommentingOn={cp.setCommentingOn}
              itemComment={cp.itemComment} setItemComment={cp.setItemComment}
              onSubmitItemComment={cp.onSubmitItemComment} isPending={cp.isPending} />
          </div>
        )
      })}
    </div>
  )
}

// ── All Comments (general tab) ──────────────────────────────────────

function AllCommentsSection({ comments, newComment, setNewComment, onSubmit, isPending, canComment, error }: {
  comments: Comment[]; newComment: string; setNewComment: (v: string) => void
  onSubmit: (e: React.FormEvent) => void; isPending: boolean; canComment: boolean; error?: string
}) {
  const { t } = useTranslation()
  return (
    <div>
      {canComment ? (
        <form onSubmit={onSubmit} style={{ marginBottom: 20 }}>
          <div className="card" style={{ overflow: 'hidden' }}>
            <textarea
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              placeholder={t('external.addGeneralComment')}
              rows={3}
              className="w-full resize-none"
              style={{ background: 'transparent', border: 0, outline: 'none', padding: '12px 14px', fontSize: 'var(--fs-md)', color: 'var(--t)' }}
            />
            <div className="row" style={{ padding: '8px 12px', borderTop: '1px solid var(--b)', background: 'var(--s3)' }}>
              <span className="faint grow" style={{ fontSize: 'var(--fs-xs)' }}>{t('external.commentsVisibleBoth')}</span>
              <Button variant="primary" size="sm" type="submit" icon={PaperAirplaneIcon} disabled={!newComment.trim() || isPending}>
                {isPending ? t('external.sending') : t('external.send')}
              </Button>
            </div>
          </div>
          {error && <div className="banner banner-da" style={{ marginTop: 8 }}>{error}</div>}
        </form>
      ) : (
        <div className="muted text-center" style={{ marginBottom: 20, padding: '10px 12px', background: 'var(--s2)', borderRadius: 'var(--r-md)', fontSize: 'var(--fs-md)' }}>
          {t('external.commentingDisabled')}
        </div>
      )}

      {comments.length === 0 ? (
        <EmptyState icon={ChatBubbleLeftIcon} title={canComment ? t('external.noCommentsYet') : t('external.noComments')} />
      ) : (
        <div className="col" style={{ gap: 12 }}>
          {comments.map((comment) => (
            <div key={comment.id} className="row" style={{ alignItems: 'flex-start', gap: 10 }}>
              <Avatar name={comment.author_name || '?'} size={28} />
              <div className="grow" style={{ background: 'var(--s2)', borderRadius: 'var(--r-md)', padding: '10px 14px' }}>
                <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 600, fontSize: 'var(--fs-md)' }}>{comment.author_name}</span>
                  <Pill tone={comment.is_internal_author ? 'in' : 'p'} dot={false}>
                    {comment.is_internal_author ? t('external.internal') : t('external.external')}
                  </Pill>
                  <span className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{formatDate(comment.created_at)}</span>
                  {comment.section_reference && (
                    <Tag>{t('external.onSection', { section: comment.section_reference.replace(':', ': #').replace(/-.*/, '...') })}</Tag>
                  )}
                </div>
                <p className="muted" style={{ fontSize: 'var(--fs-md)', marginTop: 5 }}>{comment.content}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Governance Section ──────────────────────────────────────────────

function GovernanceSection({ data }: { data: GovernanceData }) {
  const { t } = useTranslation()
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [showSection, setShowSection] = useState<'kpis' | 'improvements'>('kpis')

  const rel = data.relationship
  const kpis = data.kpis
  const improvements = data.improvements

  // Build category list
  const categories = [...new Set(kpis.map(k => k.category || 'other'))].sort()
  const filteredKpis = selectedCategory === 'all'
    ? kpis
    : kpis.filter(k => (k.category || 'other') === selectedCategory)

  return (
    <div>
      {/* Relationship header */}
      {rel && (
        <div style={{ marginBottom: 20, padding: 16, background: 'var(--p-f)', border: '1px solid var(--p-b)', borderRadius: 'var(--r-lg)' }}>
          <div className="row" style={{ gap: 14 }}>
            <div className="grow">
              <p className="muted" style={{ fontSize: 'var(--fs-sm)' }}>{t('external.businessRelationship')}</p>
              <p style={{ fontWeight: 600, marginTop: 2 }}>
                {rel.org_a_name} <span style={{ color: 'var(--p)', margin: '0 4px' }}>&harr;</span> {rel.org_b_name}
              </p>
            </div>
            {rel.governance_tier && (
              <Pill tone="p" dot={false}><span className="capitalize">{rel.governance_tier}</span></Pill>
            )}
            {rel.health_score != null && (
              <div className="text-right" style={{ flexShrink: 0 }}>
                <p className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('external.health')}</p>
                <p className="num" style={{
                  fontSize: 'var(--fs-xl)', fontWeight: 700,
                  color: rel.health_score >= 80 ? 'var(--ok)' : rel.health_score >= 60 ? 'var(--wa)' : 'var(--da)',
                }}>{rel.health_score.toFixed(0)}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Section toggle */}
      <div className="row" style={{ gap: 8, marginBottom: 14 }}>
        <Chip on={showSection === 'kpis'} onClick={() => setShowSection('kpis')}>
          {t('external.kpisCount', { count: kpis.length })}
        </Chip>
        <Chip on={showSection === 'improvements'} onClick={() => setShowSection('improvements')}>
          {t('external.improvementsCount', { count: improvements.length })}
        </Chip>
      </div>

      {showSection === 'kpis' && (
        <>
          {/* Category filter */}
          {categories.length > 1 && (
            <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 14 }}>
              <Chip on={selectedCategory === 'all'} onClick={() => setSelectedCategory('all')}>
                {t('external.allCount', { count: kpis.length })}
              </Chip>
              {categories.map((cat) => (
                <Chip key={cat} on={selectedCategory === cat} onClick={() => setSelectedCategory(cat)}>
                  {t(`external.category.${cat}`, { defaultValue: CATEGORY_LABELS[cat] || cat })} ({kpis.filter(k => (k.category || 'other') === cat).length})
                </Chip>
              ))}
            </div>
          )}

          {filteredKpis.length === 0 ? (
            <EmptyState icon={ChartBarIcon} title={t('external.noKpis')} />
          ) : (
            <div className="col" style={{ gap: 12 }}>
              {filteredKpis.map((kpi) => {
                const gap = kpi.latest_gap
                const intScore = gap?.internal_score
                const extScore = gap?.external_score
                return (
                  <div key={kpi.id} className="card card-p">
                    <div className="row" style={{ alignItems: 'flex-start', gap: 14 }}>
                      <div className="grow">
                        <p style={{ fontWeight: 600 }}>{kpi.name}</p>
                        {kpi.description && <p className="muted" style={{ fontSize: 'var(--fs-sm)', marginTop: 4 }}>{kpi.description}</p>}
                        <div className="row" style={{ gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                          {kpi.category && <Tag><span className="capitalize">{t(`external.category.${kpi.category}`, { defaultValue: CATEGORY_LABELS[kpi.category] || kpi.category })}</span></Tag>}
                          {kpi.target_value != null && <Pill tone="in" dot={false}>{t('external.target', { value: kpi.target_value })}</Pill>}
                          {kpi.is_perception_based && <Pill tone="p" dot={false}>{t('external.perceptionBased')}</Pill>}
                        </div>
                      </div>
                      {gap && (
                        <div className="col text-right" style={{ flexShrink: 0, gap: 4, alignItems: 'flex-end' }}>
                          <div className="row" style={{ gap: 12 }}>
                            {intScore != null && (
                              <div>
                                <p className="faint uppercase" style={{ fontSize: 'var(--fs-2xs)', letterSpacing: '.5px' }}>{t('external.internal')}</p>
                                <p className="num" style={{ fontWeight: 600, color: 'var(--in)' }}>{intScore.toFixed(1)}</p>
                              </div>
                            )}
                            {extScore != null && (
                              <div>
                                <p className="faint uppercase" style={{ fontSize: 'var(--fs-2xs)', letterSpacing: '.5px' }}>{t('external.external')}</p>
                                <p className="num" style={{ fontWeight: 600, color: 'var(--p)' }}>{extScore.toFixed(1)}</p>
                              </div>
                            )}
                          </div>
                          {gap.gap_severity && (
                            <Pill tone={SEVERITY_TONE[gap.gap_severity] || 'n'}>
                              <span className="capitalize">{t(`external.severity.${gap.gap_severity}`, { defaultValue: gap.gap_severity })}</span>
                            </Pill>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}

      {showSection === 'improvements' && (
        <>
          {improvements.length === 0 ? (
            <EmptyState icon={CheckCircleIcon} title={t('external.noImprovements')} />
          ) : (
            <div className="col" style={{ gap: 12 }}>
              {improvements.map((imp) => (
                <div key={imp.id} className="card card-p">
                  <div className="row" style={{ alignItems: 'flex-start', gap: 14 }}>
                    <div className="grow">
                      <p style={{ fontWeight: 600 }}>{imp.title}</p>
                      {imp.description && <p className="muted" style={{ fontSize: 'var(--fs-sm)', marginTop: 4 }}>{imp.description}</p>}
                      <div className="row" style={{ gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                        {imp.priority && (
                          <Pill tone={priorityTone(imp.priority)}>
                            <span className="capitalize">{t(`risk.${imp.priority}`, { defaultValue: imp.priority })}</span>
                          </Pill>
                        )}
                        {imp.status && (
                          <Pill tone={STATUS_TONE[imp.status] || 'n'}>
                            <span className="capitalize">{t(`external.status.${imp.status}`, { defaultValue: imp.status.replace(/_/g, ' ') })}</span>
                          </Pill>
                        )}
                        {imp.source && <Tag><span className="capitalize">{imp.source.replace(/_/g, ' ')}</span></Tag>}
                        {imp.kpi_name && <Pill tone="p" dot={false}>{t('external.kpiLabel', { name: imp.kpi_name })}</Pill>}
                      </div>
                      {imp.target_outcome && <p className="faint" style={{ fontSize: 'var(--fs-sm)', marginTop: 8 }}>{t('external.target', { value: imp.target_outcome })}</p>}
                      {imp.actual_outcome && <p style={{ fontSize: 'var(--fs-sm)', marginTop: 4, color: 'var(--ok)' }}>{t('external.outcome', { text: imp.actual_outcome })}</p>}
                    </div>
                    <div className="text-right" style={{ flexShrink: 0 }}>
                      {imp.due_date && <p className="num" style={{ fontSize: 'var(--fs-md)' }}>{formatDate(imp.due_date)}</p>}
                      {imp.impact_score != null && (
                        <p className="faint" style={{ fontSize: 'var(--fs-sm)', marginTop: 4 }}>{t('external.impact', { score: imp.impact_score })}</p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
