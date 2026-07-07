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
  BellAlertIcon,
  ChartBarIcon,
  ExclamationCircleIcon,
  CheckCircleIcon,
  ArrowPathIcon,
  EyeIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import axios from 'axios'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn, formatDate } from '@/lib/utils'

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

// ── Main Component ─────────────────────────────────────────────────

export default function ExternalContractPage() {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
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
      alert(t('external.downloadFailed'))
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
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <LoadingSpinner size="lg" />
          <p className="mt-4 text-gray-600">{t('external.validatingAccess')}</p>
        </div>
      </div>
    )
  }

  if (validationError || !accessToken) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <ExclamationTriangleIcon className="w-8 h-8 text-red-600" />
          </div>
          <h1 className="text-xl font-bold text-gray-900 mb-2">{t('external.accessDenied')}</h1>
          <p className="text-gray-600">
            {!accessToken ? t('external.noToken') : t('external.invalidLink')}
          </p>
        </div>
      </div>
    )
  }

  // ── Contract List ──────────────────────────────────────────────

  if (!effectiveContractId && validation?.contracts && validation.contracts.length > 1) {
    return (
      <div className="min-h-screen bg-gray-50">
        <PortalHeader user={validation.external_user} expiresAt={validation.token_expires_at} />
        <main className="max-w-5xl mx-auto px-4 py-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">{t('external.sharedContracts')}</h2>
          <p className="text-sm text-gray-500 mb-6">{t('external.contractsSharedWithYou', { count: validation.contracts.length })}</p>
          <div className="space-y-3">
            {validation.contracts.map((c) => (
              <button key={c.id}
                onClick={() => { setSelectedContractId(c.id); setActiveTab('document'); }}
                className="w-full bg-white rounded-xl shadow-sm border border-gray-200 p-5 hover:border-primary-300 hover:shadow-md transition-all text-left group"
              >
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-primary-100 rounded-lg shrink-0 group-hover:bg-primary-200 transition-colors">
                    <DocumentTextIcon className="w-7 h-7 text-primary-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-gray-900 truncate group-hover:text-primary-700 transition-colors">{c.filename}</p>
                    {c.counterparty && <p className="text-sm text-gray-500 mt-0.5">{c.counterparty}</p>}
                    <div className="flex items-center gap-2 mt-2">
                      {c.contract_type && <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded capitalize">{c.contract_type.replace(/_/g, ' ')}</span>}
                      {c.expires_at && <span className="text-xs text-gray-400 flex items-center gap-1"><ClockIcon className="w-3 h-3" />{t('external.expires', { date: formatDate(c.expires_at) })}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {c.can_download && <span className="text-xs bg-green-50 text-green-700 px-2 py-1 rounded flex items-center gap-1"><ArrowDownTrayIcon className="w-3 h-3" /> {t('external.download')}</span>}
                    {c.can_comment && <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded flex items-center gap-1"><ChatBubbleLeftIcon className="w-3 h-3" /> {t('external.comment')}</span>}
                    <ChevronLeftIcon className="w-5 h-5 text-gray-300 rotate-180 group-hover:text-primary-400 transition-colors" />
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
      <div className="min-h-screen bg-gray-50">
        <PortalHeader user={validation?.external_user} expiresAt={validation?.token_expires_at} />
        <main className="max-w-5xl mx-auto px-4 py-8 text-center"><p className="text-gray-600">{t('external.noContractsShared')}</p></main>
        <PortalFooter />
      </div>
    )
  }

  // ── Contract Detail ────────────────────────────────────────────

  const showBackButton = validation?.contracts && validation.contracts.length > 1
  const canComment = contract?.can_comment ?? false

  return (
    <div className="min-h-screen bg-gray-50">
      <PortalHeader user={validation?.external_user} expiresAt={validation?.token_expires_at} />
      <main className="max-w-5xl mx-auto px-4 py-8">
        {showBackButton && (
          <button onClick={() => { setSelectedContractId(null); setActiveTab('document'); }}
            className="flex items-center gap-1 text-sm text-primary-600 hover:text-primary-800 mb-4">
            <ChevronLeftIcon className="w-4 h-4" /> {t('external.allContracts')}
          </button>
        )}

        {loadingContract ? (
          <div className="text-center py-16"><LoadingSpinner size="lg" /></div>
        ) : contract ? (
          <>
            {/* Header Card */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              <div className="p-6 border-b border-gray-200">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4">
                    <div className="p-3 bg-primary-100 rounded-lg"><DocumentTextIcon className="w-8 h-8 text-primary-600" /></div>
                    <div>
                      <h2 className="text-xl font-semibold text-gray-900">{contract.filename}</h2>
                      {contract.counterparty && <p className="text-gray-600 mt-1">{t('contracts.counterparty')}: {contract.counterparty}</p>}
                      <div className="flex flex-wrap items-center gap-2 mt-2">
                        {contract.contract_type && <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded capitalize">{contract.contract_type.replace(/_/g, ' ')}</span>}
                        {contract.risk_level && (
                          <span className={cn("text-xs px-2 py-1 rounded capitalize",
                            contract.risk_level === 'high' || contract.risk_level === 'critical' ? 'bg-red-100 text-red-700' :
                            contract.risk_level === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700'
                          )}>{t('contract.riskLabel', { level: t(`risk.${contract.risk_level}`, { defaultValue: contract.risk_level }) })}</span>
                        )}
                        {contract.auto_renewal && <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded flex items-center gap-1"><ArrowPathIcon className="w-3 h-3" /> {t('external.autoRenewal')}</span>}
                        <span className={cn("text-xs px-2 py-1 rounded capitalize", contract.status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600')}>{t(`status.${contract.status}`, { defaultValue: contract.status })}</span>
                      </div>
                    </div>
                  </div>
                  {contract.can_download && (
                    <button onClick={handleDownload} className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors shrink-0">
                      <ArrowDownTrayIcon className="w-5 h-5" /> {t('external.download')}
                    </button>
                  )}
                </div>
              </div>
              <div className="p-6 grid grid-cols-2 md:grid-cols-4 gap-6">
                {contract.effective_date && <DetailCell label={t('external.effectiveDate')} value={formatDate(contract.effective_date)} />}
                {contract.expiration_date && <DetailCell label={t('external.expirationDate')} value={formatDate(contract.expiration_date)} />}
                {(contract.total_value || contract.contract_value) && <DetailCell label={t('external.totalValue')} value={`${contract.currency || 'USD'} ${(contract.total_value || contract.contract_value || 0).toLocaleString()}`} />}
                {contract.jurisdiction && <DetailCell label={t('external.jurisdiction')} value={contract.jurisdiction} />}
                {contract.governing_law && <DetailCell label={t('external.governingLaw')} value={contract.governing_law} />}
                {contract.notice_period_days != null && contract.notice_period_days > 0 && <DetailCell label={t('external.noticePeriod')} value={t('external.days', { count: contract.notice_period_days })} />}
                {contract.risk_score != null && <DetailCell label={t('external.riskScore')} value={`${contract.risk_score}/100`} />}
              </div>
              {contract.shared_message && (
                <div className="px-6 pb-6">
                  <div className="bg-primary-50 border-l-4 border-primary-400 p-4 rounded-r-lg">
                    <p className="text-sm text-primary-800 italic">"{contract.shared_message}"</p>
                  </div>
                </div>
              )}
            </div>

            {contract.summary && (
              <div className="mt-6 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h3 className="font-semibold text-gray-900 mb-2">{t('external.contractSummary')}</h3>
                <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-line">{contract.summary}</p>
              </div>
            )}

            {/* Tabs */}
            <div className="mt-6 bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              <div className="border-b border-gray-200 flex overflow-x-auto">
                <TabButton active={activeTab === 'document'} onClick={() => setActiveTab('document')} icon={<EyeIcon className="w-4 h-4" />} label={t('external.document')} />
                <TabButton active={activeTab === 'clauses'} onClick={() => setActiveTab('clauses')} icon={<DocumentTextIcon className="w-4 h-4" />} label={t('external.keyClauses')} count={contract.clauses?.length} />
                <TabButton active={activeTab === 'obligations'} onClick={() => setActiveTab('obligations')} icon={<BellAlertIcon className="w-4 h-4" />} label={t('contract.obligations')} count={contract.obligations?.length} />
                <TabButton active={activeTab === 'sla'} onClick={() => setActiveTab('sla')} icon={<ChartBarIcon className="w-4 h-4" />} label={t('contract.slas')} count={contract.slas?.length} />
                {governanceData?.has_governance && (
                  <TabButton active={activeTab === 'governance'} onClick={() => setActiveTab('governance')} icon={<ShieldCheckIcon className="w-4 h-4" />} label={t('external.governance')} count={governanceData.kpis.length} />
                )}
                <TabButton active={activeTab === 'comments'} onClick={() => setActiveTab('comments')} icon={<ChatBubbleLeftIcon className="w-4 h-4" />} label={t('external.allComments')} count={commentsData?.total} />
              </div>

              <div className="p-6">
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
    <div className="mt-3">
      {/* Comment toggle button */}
      <div className="flex items-center gap-3">
        {canComment && (
          <button
            onClick={() => {
              if (isOpen) { setCommentingOn(null); setItemComment(''); }
              else { setCommentingOn(sectionRef); setItemComment(''); }
            }}
            className={cn(
              "text-xs flex items-center gap-1 px-2 py-1 rounded transition-colors",
              isOpen ? "bg-primary-100 text-primary-700" : "text-gray-400 hover:text-primary-600 hover:bg-primary-50"
            )}
          >
            <ChatBubbleLeftIcon className="w-3.5 h-3.5" />
            {isOpen ? t('common.cancel') : t('external.comment')}
          </button>
        )}
        {count > 0 && !isOpen && (
          <button
            onClick={() => { setCommentingOn(sectionRef); setItemComment(''); }}
            className="text-xs text-gray-400 hover:text-primary-600 flex items-center gap-1"
          >
            <ChatBubbleLeftIcon className="w-3 h-3" />
            {t('external.commentCount', { count })}
          </button>
        )}
      </div>

      {/* Expanded: show existing comments + form */}
      {isOpen && (
        <div className="mt-2 ml-0 border-l-2 border-primary-200 pl-3 space-y-2">
          {/* Existing comments */}
          {comments.map((c) => (
            <div key={c.id} className="flex items-start gap-2">
              <div className={cn(
                "h-6 w-6 rounded-full flex items-center justify-center text-xs font-medium shrink-0",
                c.is_internal_author ? "bg-blue-100 text-blue-700" : "bg-primary-100 text-primary-700"
              )}>
                {c.author_name?.charAt(0).toUpperCase() || '?'}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-xs font-medium text-gray-800">{c.author_name}</span>
                  <span className={cn("text-[10px] px-1 py-0.5 rounded",
                    c.is_internal_author ? "bg-blue-50 text-blue-600" : "bg-primary-50 text-primary-600"
                  )}>{c.is_internal_author ? t('external.internal') : t('external.you')}</span>
                  <span className="text-[10px] text-gray-400">{formatDate(c.created_at)}</span>
                </div>
                <p className="text-xs text-gray-700 mt-0.5">{c.content}</p>
              </div>
            </div>
          ))}

          {/* Input form */}
          {canComment && (
            <div className="flex items-start gap-2 pt-1">
              <textarea
                value={itemComment}
                onChange={(e) => setItemComment(e.target.value)}
                placeholder={t('external.addYourComment')}
                rows={2}
                className="flex-1 text-xs px-3 py-2 border border-gray-200 rounded-lg resize-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
                autoFocus
              />
              <button
                onClick={() => onSubmitItemComment(sectionRef, clauseId)}
                disabled={!itemComment.trim() || isPending}
                className="px-3 py-2 bg-primary-600 text-white text-xs rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors shrink-0"
              >
                <PaperAirplaneIcon className="w-3.5 h-3.5" />
              </button>
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
    <header className="bg-white border-b border-gray-200">
      <div className="max-w-5xl mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center">
              <span className="text-white font-bold text-lg">E</span>
            </div>
            <div>
              <h1 className="font-semibold text-gray-900">Evaluetor</h1>
              <p className="text-xs text-gray-500">{t('external.sharedContractPortal')}</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {expiresAt && <div className="hidden sm:flex items-center gap-1 text-xs text-gray-400"><ClockIcon className="w-3.5 h-3.5" /><span>{t('external.expires', { date: formatDate(expiresAt) })}</span></div>}
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <ShieldCheckIcon className="w-4 h-4 text-green-600" />
              <span className="hidden sm:inline">{user?.full_name || user?.email}</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}

function PortalFooter() {
  const { t } = useTranslation()
  return (
    <footer className="border-t border-gray-200 bg-white mt-12">
      <div className="max-w-5xl mx-auto px-4 py-6 text-center text-sm text-gray-500">{t('external.poweredBy')}</div>
    </footer>
  )
}

function DetailCell({ label, value }: { label: string; value: string }) {
  return <div><p className="text-sm text-gray-500">{label}</p><p className="font-medium text-gray-900">{value}</p></div>
}

function TabButton({ active, onClick, icon, label, count }: {
  active: boolean; onClick: () => void; icon: React.ReactNode; label: string; count?: number
}) {
  return (
    <button onClick={onClick}
      className={cn("flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap",
        active ? "border-primary-600 text-primary-600" : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
      )}>
      {icon}{label}
      {count != null && count > 0 && <span className={cn("text-xs px-1.5 py-0.5 rounded-full", active ? "bg-primary-100 text-primary-700" : "bg-gray-100 text-gray-600")}>{count}</span>}
    </button>
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

  if (loading) return <div className="flex flex-col items-center justify-center py-16"><LoadingSpinner size="lg" /><p className="mt-4 text-sm text-gray-500">{t('external.loadingPreview')}</p></div>
  if (error || !pdfUrl) return <div className="text-center py-12"><DocumentTextIcon className="w-12 h-12 text-gray-300 mx-auto mb-3" /><p className="text-gray-500 text-sm">{error || t('external.previewNotAvailable')}</p><p className="text-xs text-gray-400 mt-1">{t('external.useDownloadButton')}</p></div>
  if (!isPdf) return <div className="text-center py-12"><DocumentTextIcon className="w-12 h-12 text-gray-300 mx-auto mb-3" /><p className="text-gray-500 text-sm">{t('external.pdfOnly')}</p></div>

  if (fullscreen) {
    return (
      <>
        <div className="fixed inset-0 bg-black/80 z-50 flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 bg-gray-900">
            <p className="text-white text-sm font-medium truncate">{filename}</p>
            <button onClick={() => setFullscreen(false)} className="text-gray-300 hover:text-white p-1 rounded-lg hover:bg-gray-700 transition-colors"><XMarkIcon className="w-6 h-6" /></button>
          </div>
          <div className="flex-1"><iframe src={`${pdfUrl}#toolbar=1&navpanes=1`} className="w-full h-full border-0" title={t('external.contractDocument')} /></div>
        </div>
        <div className="h-[600px]" />
      </>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm text-gray-500">{filename}</p>
        <button onClick={() => setFullscreen(true)} className="text-xs text-primary-600 hover:text-primary-800 flex items-center gap-1"><EyeIcon className="w-3.5 h-3.5" /> {t('external.fullscreen')}</button>
      </div>
      <div className="border border-gray-200 rounded-lg overflow-hidden bg-gray-100">
        <iframe src={`${pdfUrl}#toolbar=1&navpanes=0&scrollbar=1`} className="w-full border-0" style={{ height: '700px' }} title={t('external.contractDocument')} />
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
  if (!clauses?.length) return <EmptyState text={t('external.noClauses')} />

  return (
    <div className="space-y-4">
      {clauses.map((clause) => {
        const ref = `clause:${clause.id}`
        return (
          <div key={clause.id} className="border border-gray-200 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              {clause.section_number && <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">{clause.section_number}</span>}
              {clause.clause_type && <span className="text-xs bg-primary-100 text-primary-700 px-2 py-0.5 rounded capitalize">{t(`clauses.${clause.clause_type}`, { defaultValue: clause.clause_type.replace(/_/g, ' ') })}</span>}
              {clause.risk_level && <span className={cn("text-xs px-2 py-0.5 rounded capitalize",
                clause.risk_level === 'high' ? 'bg-red-100 text-red-700' : clause.risk_level === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700'
              )}>{t(`risk.${clause.risk_level}`, { defaultValue: clause.risk_level })}</span>}
            </div>
            {clause.title && <p className="font-medium text-gray-900 mb-1">{clause.title}</p>}
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">{clause.text}</p>
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
  if (!obligations?.length) return <EmptyState text={t('external.noObligations')} />

  const now = new Date()
  const sorted = [...obligations].sort((a, b) => {
    if (!a.deadline) return 1; if (!b.deadline) return -1
    return new Date(a.deadline).getTime() - new Date(b.deadline).getTime()
  })

  return (
    <div className="space-y-3">
      {sorted.map((ob) => {
        const isOverdue = ob.deadline && new Date(ob.deadline) < now && ob.status !== 'completed'
        const ref = `obligation:${ob.id}`
        return (
          <div key={ob.id} className={cn("border rounded-lg p-4", isOverdue ? "border-red-200 bg-red-50" : "border-gray-200")}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  {ob.is_critical && <ExclamationCircleIcon className="w-4 h-4 text-red-600 shrink-0" />}
                  <p className="font-medium text-gray-900">{ob.description}</p>
                </div>
                <div className="flex flex-wrap gap-2 mt-2 text-xs">
                  {ob.obligation_type && <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded capitalize">{t(`obligation.type.${ob.obligation_type}`, { defaultValue: ob.obligation_type.replace(/_/g, ' ') })}</span>}
                  {ob.responsible_party && <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded">{ob.responsible_party}</span>}
                  {ob.priority && <span className={cn("px-2 py-0.5 rounded capitalize", ob.priority === 'critical' ? 'bg-red-100 text-red-700' : ob.priority === 'high' ? 'bg-orange-100 text-orange-700' : 'bg-gray-100 text-gray-600')}>{t(`risk.${ob.priority}`, { defaultValue: ob.priority })}</span>}
                </div>
                {ob.consequence && <p className="text-xs text-gray-500 mt-2 italic">{t('external.consequence', { text: ob.consequence })}</p>}
              </div>
              <div className="text-right shrink-0">
                {ob.deadline && <p className={cn("text-sm font-medium", isOverdue ? "text-red-700" : "text-gray-700")}>{isOverdue ? t('external.overdue') : formatDate(ob.deadline)}</p>}
                <p className={cn("text-xs mt-1 capitalize", ob.status === 'completed' ? "text-green-600" : "text-gray-500")}>{t(`status.${ob.status || 'pending'}`, { defaultValue: ob.status || 'pending' })}</p>
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
  if (!slas?.length) return <EmptyState text={t('external.noSlas')} />

  return (
    <div className="space-y-3">
      {slas.map((sla) => {
        const compliance = sla.current_compliance_rate
        const complianceColor = compliance == null ? 'gray' : compliance >= 95 ? 'green' : compliance >= 80 ? 'amber' : 'red'
        const ref = `sla:${sla.id}`

        return (
          <div key={sla.id} className="border border-gray-200 rounded-lg p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <p className="font-medium text-gray-900">{sla.sla_name}</p>
                {sla.sla_description && <p className="text-sm text-gray-600 mt-1">{sla.sla_description}</p>}
                <div className="flex flex-wrap gap-2 mt-2 text-xs">
                  {sla.metric_type && <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded capitalize">{sla.metric_type.replace(/_/g, ' ')}</span>}
                  {sla.target_value != null && <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded">{t('external.target', { value: `${sla.target_operator || '>='} ${sla.target_value}${sla.metric_unit || ''}` })}</span>}
                  {sla.severity && <span className={cn("px-2 py-0.5 rounded capitalize", sla.severity === 'critical' ? 'bg-red-100 text-red-700' : sla.severity === 'high' ? 'bg-orange-100 text-orange-700' : 'bg-gray-100 text-gray-600')}>{t(`risk.${sla.severity}`, { defaultValue: sla.severity })}</span>}
                  {sla.measurement_period && <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded capitalize">{sla.measurement_period}</span>}
                </div>
                {sla.has_penalty && sla.penalty_description && <p className="text-xs text-gray-500 mt-2 italic">{t('external.penalty', { text: sla.penalty_description })}</p>}
              </div>
              <div className="text-right shrink-0">
                {compliance != null ? (
                  <div className="flex items-center gap-1.5">
                    {complianceColor === 'green' && <CheckCircleIcon className="w-5 h-5 text-green-600" />}
                    {complianceColor === 'amber' && <ExclamationTriangleIcon className="w-5 h-5 text-amber-600" />}
                    {complianceColor === 'red' && <ExclamationCircleIcon className="w-5 h-5 text-red-600" />}
                    <span className={cn("text-lg font-bold", complianceColor === 'green' ? 'text-green-700' : complianceColor === 'amber' ? 'text-amber-700' : 'text-red-700')}>{compliance.toFixed(1)}%</span>
                  </div>
                ) : <span className="text-sm text-gray-400">{t('external.noData')}</span>}
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
        <form onSubmit={onSubmit} className="mb-6">
          <div className="border border-gray-200 rounded-lg overflow-hidden focus-within:ring-2 focus-within:ring-primary-500 focus-within:border-primary-500">
            <textarea value={newComment} onChange={(e) => setNewComment(e.target.value)}
              placeholder={t('external.addGeneralComment')} rows={3}
              className="w-full px-4 py-3 border-0 resize-none focus:ring-0 text-sm" />
            <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-t border-gray-200">
              <p className="text-xs text-gray-400">{t('external.commentsVisibleBoth')}</p>
              <button type="submit" disabled={!newComment.trim() || isPending}
                className="px-4 py-1.5 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors flex items-center gap-2">
                <PaperAirplaneIcon className="w-4 h-4" />{isPending ? t('external.sending') : t('external.send')}
              </button>
            </div>
          </div>
          {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
        </form>
      ) : (
        <div className="mb-6 p-3 bg-gray-50 rounded-lg text-sm text-gray-500 text-center">{t('external.commentingDisabled')}</div>
      )}

      {comments.length === 0 ? (
        <EmptyState text={canComment ? t('external.noCommentsYet') : t('external.noComments')} />
      ) : (
        <div className="space-y-4">
          {comments.map((comment) => (
            <div key={comment.id} className="flex items-start gap-3">
              <div className={cn("h-8 w-8 rounded-full flex items-center justify-center text-sm font-medium shrink-0",
                comment.is_internal_author ? "bg-blue-100 text-blue-700" : "bg-primary-100 text-primary-700"
              )}>{comment.author_name?.charAt(0).toUpperCase() || '?'}</div>
              <div className="flex-1 bg-gray-50 rounded-lg px-4 py-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-gray-900 text-sm">{comment.author_name}</span>
                  <span className={cn("text-xs px-1.5 py-0.5 rounded",
                    comment.is_internal_author ? "bg-blue-100 text-blue-600" : "bg-primary-100 text-primary-600"
                  )}>{comment.is_internal_author ? t('external.internal') : t('external.external')}</span>
                  <span className="text-xs text-gray-400">{formatDate(comment.created_at)}</span>
                  {comment.section_reference && (
                    <span className="text-xs bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded">
                      {t('external.onSection', { section: comment.section_reference.replace(':', ': #').replace(/-.*/, '...') })}
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-700 mt-1.5">{comment.content}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Governance Section ──────────────────────────────────────────────

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

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-100 text-red-700',
  significant: 'bg-orange-100 text-orange-700',
  moderate: 'bg-amber-100 text-amber-700',
  minor: 'bg-green-100 text-green-700',
  aligned: 'bg-emerald-100 text-emerald-700',
}

const PRIORITY_COLORS: Record<string, string> = {
  critical: 'bg-red-100 text-red-700',
  high: 'bg-orange-100 text-orange-700',
  medium: 'bg-amber-100 text-amber-700',
  low: 'bg-gray-100 text-gray-600',
}

const STATUS_COLORS: Record<string, string> = {
  open: 'bg-blue-100 text-blue-700',
  in_progress: 'bg-primary-100 text-primary-700',
  blocked: 'bg-red-100 text-red-700',
  completed: 'bg-green-100 text-green-700',
  cancelled: 'bg-gray-100 text-gray-500',
}

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
        <div className="mb-6 p-4 bg-gradient-to-r from-primary-50 to-indigo-50 rounded-lg border border-primary-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">{t('external.businessRelationship')}</p>
              <p className="font-semibold text-gray-900">
                {rel.org_a_name} <span className="text-primary-500 mx-1">&harr;</span> {rel.org_b_name}
              </p>
            </div>
            <div className="flex items-center gap-4">
              {rel.governance_tier && (
                <span className="text-xs bg-white/80 text-primary-700 px-2 py-1 rounded capitalize border border-primary-200">{rel.governance_tier}</span>
              )}
              {rel.health_score != null && (
                <div className="text-right">
                  <p className="text-xs text-gray-500">{t('external.health')}</p>
                  <p className={cn("text-lg font-bold",
                    rel.health_score >= 80 ? "text-green-600" : rel.health_score >= 60 ? "text-amber-600" : "text-red-600"
                  )}>{rel.health_score.toFixed(0)}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Section toggle */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setShowSection('kpis')}
          className={cn("px-4 py-2 text-sm font-medium rounded-lg transition-colors",
            showSection === 'kpis' ? "bg-primary-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          )}
        >
          {t('external.kpisCount', { count: kpis.length })}
        </button>
        <button
          onClick={() => setShowSection('improvements')}
          className={cn("px-4 py-2 text-sm font-medium rounded-lg transition-colors",
            showSection === 'improvements' ? "bg-primary-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          )}
        >
          {t('external.improvementsCount', { count: improvements.length })}
        </button>
      </div>

      {showSection === 'kpis' && (
        <>
          {/* Category filter */}
          {categories.length > 1 && (
            <div className="flex flex-wrap gap-2 mb-4">
              <button
                onClick={() => setSelectedCategory('all')}
                className={cn("px-3 py-1 text-xs rounded-full transition-colors",
                  selectedCategory === 'all' ? "bg-primary-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                )}
              >
                {t('external.allCount', { count: kpis.length })}
              </button>
              {categories.map((cat) => (
                <button key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={cn("px-3 py-1 text-xs rounded-full transition-colors",
                    selectedCategory === cat ? "bg-primary-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  )}
                >
                  {t(`external.category.${cat}`, { defaultValue: CATEGORY_LABELS[cat] || cat })} ({kpis.filter(k => (k.category || 'other') === cat).length})
                </button>
              ))}
            </div>
          )}

          {filteredKpis.length === 0 ? (
            <EmptyState text={t('external.noKpis')} />
          ) : (
            <div className="space-y-3">
              {filteredKpis.map((kpi) => {
                const gap = kpi.latest_gap
                const intScore = gap?.internal_score
                const extScore = gap?.external_score
                return (
                  <div key={kpi.id} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <p className="font-medium text-gray-900">{kpi.name}</p>
                        {kpi.description && <p className="text-sm text-gray-600 mt-1">{kpi.description}</p>}
                        <div className="flex flex-wrap gap-2 mt-2 text-xs">
                          {kpi.category && <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded capitalize">{t(`external.category.${kpi.category}`, { defaultValue: CATEGORY_LABELS[kpi.category] || kpi.category })}</span>}
                          {kpi.target_value != null && <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded">{t('external.target', { value: kpi.target_value })}</span>}
                          {kpi.is_perception_based && <span className="bg-primary-50 text-primary-700 px-2 py-0.5 rounded">{t('external.perceptionBased')}</span>}
                        </div>
                      </div>
                      {gap && (
                        <div className="text-right shrink-0 space-y-1">
                          <div className="flex items-center gap-3 text-sm">
                            {intScore != null && (
                              <div>
                                <p className="text-[10px] text-gray-400 uppercase">{t('external.internal')}</p>
                                <p className="font-semibold text-gray-700">{intScore.toFixed(1)}</p>
                              </div>
                            )}
                            {extScore != null && (
                              <div>
                                <p className="text-[10px] text-gray-400 uppercase">{t('external.external')}</p>
                                <p className="font-semibold text-gray-700">{extScore.toFixed(1)}</p>
                              </div>
                            )}
                          </div>
                          {gap.gap_severity && (
                            <span className={cn("text-xs px-2 py-0.5 rounded capitalize inline-block",
                              SEVERITY_COLORS[gap.gap_severity] || 'bg-gray-100 text-gray-600'
                            )}>{t(`external.severity.${gap.gap_severity}`, { defaultValue: gap.gap_severity })}</span>
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
            <EmptyState text={t('external.noImprovements')} />
          ) : (
            <div className="space-y-3">
              {improvements.map((imp) => (
                <div key={imp.id} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <p className="font-medium text-gray-900">{imp.title}</p>
                      {imp.description && <p className="text-sm text-gray-600 mt-1">{imp.description}</p>}
                      <div className="flex flex-wrap gap-2 mt-2 text-xs">
                        {imp.priority && <span className={cn("px-2 py-0.5 rounded capitalize", PRIORITY_COLORS[imp.priority] || 'bg-gray-100 text-gray-600')}>{t(`risk.${imp.priority}`, { defaultValue: imp.priority })}</span>}
                        {imp.status && <span className={cn("px-2 py-0.5 rounded capitalize", STATUS_COLORS[imp.status] || 'bg-gray-100 text-gray-600')}>{t(`external.status.${imp.status}`, { defaultValue: imp.status.replace(/_/g, ' ') })}</span>}
                        {imp.source && <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded capitalize">{imp.source.replace(/_/g, ' ')}</span>}
                        {imp.kpi_name && <span className="bg-primary-50 text-primary-700 px-2 py-0.5 rounded">{t('external.kpiLabel', { name: imp.kpi_name })}</span>}
                      </div>
                      {imp.target_outcome && <p className="text-xs text-gray-500 mt-2">{t('external.target', { value: imp.target_outcome })}</p>}
                      {imp.actual_outcome && <p className="text-xs text-green-600 mt-1">{t('external.outcome', { text: imp.actual_outcome })}</p>}
                    </div>
                    <div className="text-right shrink-0">
                      {imp.due_date && <p className="text-sm text-gray-700">{formatDate(imp.due_date)}</p>}
                      {imp.impact_score != null && (
                        <p className="text-xs text-gray-500 mt-1">{t('external.impact', { score: imp.impact_score })}</p>
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

function EmptyState({ text }: { text: string }) {
  return <div className="text-center py-8 text-gray-500 text-sm">{text}</div>
}
