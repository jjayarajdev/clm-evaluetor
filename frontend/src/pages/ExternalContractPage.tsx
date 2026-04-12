import { useState } from 'react'
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
  author_type: 'internal' | 'external'
  is_internal_author?: boolean
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

// ── Main Component ─────────────────────────────────────────────────

export default function ExternalContractPage() {
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const [selectedContractId, setSelectedContractId] = useState<string | null>(null)
  const [newComment, setNewComment] = useState('')
  const [activeTab, setActiveTab] = useState<'overview' | 'clauses' | 'obligations' | 'sla' | 'comments'>('overview')

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

  // Auto-select first contract if only one
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
    enabled: !!effectiveContractId && !!contract?.can_comment,
  })

  // ── Add comment ────────────────────────────────────────────────

  const addCommentMutation = useMutation({
    mutationFn: async (content: string) => {
      const response = await axios.post(
        `${apiBase}/contracts/${effectiveContractId}/comments`,
        { content },
        { params: { token: accessToken } }
      )
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['external-comments'] })
      setNewComment('')
    },
  })

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
      alert('Failed to download contract')
    }
  }

  const handleSubmitComment = (e: React.FormEvent) => {
    e.preventDefault()
    if (newComment.trim()) {
      addCommentMutation.mutate(newComment.trim())
    }
  }

  // ── Loading ────────────────────────────────────────────────────

  if (validating) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <LoadingSpinner size="lg" />
          <p className="mt-4 text-gray-600">Validating access...</p>
        </div>
      </div>
    )
  }

  // ── Error / no token ───────────────────────────────────────────

  if (validationError || !accessToken) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <ExclamationTriangleIcon className="w-8 h-8 text-red-600" />
          </div>
          <h1 className="text-xl font-bold text-gray-900 mb-2">Access Denied</h1>
          <p className="text-gray-600">
            {!accessToken
              ? 'No access token provided. Please use the link from your invitation email.'
              : 'This link is invalid or has expired. Please contact the sender for a new link.'}
          </p>
        </div>
      </div>
    )
  }

  // ── Contract List (multi-contract) ─────────────────────────────

  if (!effectiveContractId && validation?.contracts && validation.contracts.length > 1) {
    return (
      <div className="min-h-screen bg-gray-50">
        <PortalHeader user={validation.external_user} expiresAt={validation.token_expires_at} />
        <main className="max-w-5xl mx-auto px-4 py-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Shared Contracts ({validation.contracts.length})
          </h2>
          <div className="space-y-3">
            {validation.contracts.map((c) => (
              <button
                key={c.id}
                onClick={() => { setSelectedContractId(c.id); setActiveTab('overview'); }}
                className="w-full bg-white rounded-xl shadow-sm border border-gray-200 p-5 hover:border-violet-300 hover:shadow-md transition-all text-left"
              >
                <div className="flex items-start gap-4">
                  <div className="p-2.5 bg-violet-100 rounded-lg shrink-0">
                    <DocumentTextIcon className="w-6 h-6 text-violet-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-gray-900 truncate">{c.filename}</p>
                    {c.counterparty && (
                      <p className="text-sm text-gray-500 mt-0.5">{c.counterparty}</p>
                    )}
                    <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                      {c.contract_type && (
                        <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded capitalize">
                          {c.contract_type.replace(/_/g, ' ')}
                        </span>
                      )}
                      {c.can_download && <span>Download</span>}
                      {c.can_comment && <span>Comment</span>}
                    </div>
                  </div>
                  <ChevronLeftIcon className="w-5 h-5 text-gray-400 rotate-180 shrink-0 mt-1" />
                </div>
              </button>
            ))}
          </div>
        </main>
        <PortalFooter />
      </div>
    )
  }

  // ── No contracts ───────────────────────────────────────────────

  if (!validation?.contracts?.length) {
    return (
      <div className="min-h-screen bg-gray-50">
        <PortalHeader user={validation?.external_user} expiresAt={validation?.token_expires_at} />
        <main className="max-w-5xl mx-auto px-4 py-8 text-center">
          <p className="text-gray-600">No contracts have been shared with you yet.</p>
        </main>
        <PortalFooter />
      </div>
    )
  }

  // ── Contract Detail View ───────────────────────────────────────

  const showBackButton = validation?.contracts && validation.contracts.length > 1

  return (
    <div className="min-h-screen bg-gray-50">
      <PortalHeader user={validation?.external_user} expiresAt={validation?.token_expires_at} />

      <main className="max-w-5xl mx-auto px-4 py-8">
        {/* Back to list */}
        {showBackButton && (
          <button
            onClick={() => { setSelectedContractId(null); setActiveTab('overview'); }}
            className="flex items-center gap-1 text-sm text-violet-600 hover:text-violet-800 mb-4"
          >
            <ChevronLeftIcon className="w-4 h-4" />
            All contracts
          </button>
        )}

        {loadingContract ? (
          <div className="text-center py-16"><LoadingSpinner size="lg" /></div>
        ) : contract ? (
          <>
            {/* Contract Header Card */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              <div className="p-6 border-b border-gray-200">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4">
                    <div className="p-3 bg-violet-100 rounded-lg">
                      <DocumentTextIcon className="w-8 h-8 text-violet-600" />
                    </div>
                    <div>
                      <h2 className="text-xl font-semibold text-gray-900">{contract.filename}</h2>
                      {contract.counterparty && (
                        <p className="text-gray-600 mt-1">Counterparty: {contract.counterparty}</p>
                      )}
                      <div className="flex flex-wrap items-center gap-2 mt-2">
                        {contract.contract_type && (
                          <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded capitalize">
                            {contract.contract_type.replace(/_/g, ' ')}
                          </span>
                        )}
                        {contract.risk_level && (
                          <span className={cn(
                            "text-xs px-2 py-1 rounded capitalize",
                            contract.risk_level === 'high' || contract.risk_level === 'critical'
                              ? 'bg-red-100 text-red-700'
                              : contract.risk_level === 'medium'
                              ? 'bg-amber-100 text-amber-700'
                              : 'bg-green-100 text-green-700'
                          )}>
                            {contract.risk_level} risk
                          </span>
                        )}
                        {contract.auto_renewal && (
                          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded flex items-center gap-1">
                            <ArrowPathIcon className="w-3 h-3" /> Auto-renewal
                          </span>
                        )}
                        <span className={cn(
                          "text-xs px-2 py-1 rounded capitalize",
                          contract.status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                        )}>
                          {contract.status}
                        </span>
                      </div>
                    </div>
                  </div>
                  {contract.can_download && (
                    <button
                      onClick={handleDownload}
                      className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 transition-colors shrink-0"
                    >
                      <ArrowDownTrayIcon className="w-5 h-5" />
                      Download
                    </button>
                  )}
                </div>
              </div>

              {/* Key Details Grid */}
              <div className="p-6 grid grid-cols-2 md:grid-cols-4 gap-6">
                {contract.effective_date && (
                  <DetailCell label="Effective Date" value={formatDate(contract.effective_date)} />
                )}
                {contract.expiration_date && (
                  <DetailCell label="Expiration Date" value={formatDate(contract.expiration_date)} />
                )}
                {(contract.total_value || contract.contract_value) && (
                  <DetailCell
                    label="Total Value"
                    value={`${contract.currency || 'USD'} ${(contract.total_value || contract.contract_value || 0).toLocaleString()}`}
                  />
                )}
                {contract.jurisdiction && (
                  <DetailCell label="Jurisdiction" value={contract.jurisdiction} />
                )}
                {contract.governing_law && (
                  <DetailCell label="Governing Law" value={contract.governing_law} />
                )}
                {contract.notice_period_days != null && contract.notice_period_days > 0 && (
                  <DetailCell label="Notice Period" value={`${contract.notice_period_days} days`} />
                )}
                {contract.risk_score != null && (
                  <DetailCell label="Risk Score" value={`${contract.risk_score}/100`} />
                )}
              </div>

              {/* Shared message */}
              {contract.shared_message && (
                <div className="px-6 pb-6">
                  <div className="bg-violet-50 border-l-4 border-violet-400 p-4 rounded-r-lg">
                    <p className="text-sm text-violet-800 italic">"{contract.shared_message}"</p>
                  </div>
                </div>
              )}
            </div>

            {/* AI Summary */}
            {contract.summary && (
              <div className="mt-6 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h3 className="font-semibold text-gray-900 mb-2">Contract Summary</h3>
                <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-line">{contract.summary}</p>
              </div>
            )}

            {/* Tab navigation */}
            <div className="mt-6 bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              <div className="border-b border-gray-200 flex overflow-x-auto">
                <TabButton active={activeTab === 'overview'} onClick={() => setActiveTab('overview')}
                  icon={<DocumentTextIcon className="w-4 h-4" />} label="Key Clauses" count={contract.clauses?.length} />
                <TabButton active={activeTab === 'obligations'} onClick={() => setActiveTab('obligations')}
                  icon={<BellAlertIcon className="w-4 h-4" />} label="Obligations" count={contract.obligations?.length} />
                <TabButton active={activeTab === 'sla'} onClick={() => setActiveTab('sla')}
                  icon={<ChartBarIcon className="w-4 h-4" />} label="SLAs" count={contract.slas?.length} />
                {contract.can_comment && (
                  <TabButton active={activeTab === 'comments'} onClick={() => setActiveTab('comments')}
                    icon={<ChatBubbleLeftIcon className="w-4 h-4" />} label="Comments" count={commentsData?.total} />
                )}
              </div>

              {/* Tab Content */}
              <div className="p-6">
                {activeTab === 'overview' && (
                  <ClausesSection clauses={contract.clauses} />
                )}
                {activeTab === 'obligations' && (
                  <ObligationsSection obligations={contract.obligations} />
                )}
                {activeTab === 'sla' && (
                  <SLASection slas={contract.slas} />
                )}
                {activeTab === 'comments' && contract.can_comment && (
                  <CommentsSection
                    comments={commentsData?.items || []}
                    newComment={newComment}
                    setNewComment={setNewComment}
                    onSubmit={handleSubmitComment}
                    isPending={addCommentMutation.isPending}
                  />
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


// ── Sub-components ─────────────────────────────────────────────────

function PortalHeader({ user, expiresAt }: { user?: ValidateResponse['external_user']; expiresAt?: string }) {
  return (
    <header className="bg-white border-b border-gray-200">
      <div className="max-w-5xl mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-violet-500 to-violet-600 flex items-center justify-center">
              <span className="text-white font-bold text-lg">E</span>
            </div>
            <div>
              <h1 className="font-semibold text-gray-900">Evaluetor</h1>
              <p className="text-xs text-gray-500">Shared Contract Portal</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {expiresAt && (
              <div className="hidden sm:flex items-center gap-1 text-xs text-gray-400">
                <ClockIcon className="w-3.5 h-3.5" />
                <span>Expires {formatDate(expiresAt)}</span>
              </div>
            )}
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
  return (
    <footer className="border-t border-gray-200 bg-white mt-12">
      <div className="max-w-5xl mx-auto px-4 py-6 text-center text-sm text-gray-500">
        Powered by Evaluetor Contract Intelligence Platform
      </div>
    </footer>
  )
}

function DetailCell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-sm text-gray-500">{label}</p>
      <p className="font-medium text-gray-900">{value}</p>
    </div>
  )
}

function TabButton({ active, onClick, icon, label, count }: {
  active: boolean; onClick: () => void; icon: React.ReactNode; label: string; count?: number
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap",
        active
          ? "border-violet-600 text-violet-600"
          : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
      )}
    >
      {icon}
      {label}
      {count != null && count > 0 && (
        <span className={cn(
          "text-xs px-1.5 py-0.5 rounded-full",
          active ? "bg-violet-100 text-violet-700" : "bg-gray-100 text-gray-600"
        )}>
          {count}
        </span>
      )}
    </button>
  )
}

// ── Clauses ────────────────────────────────────────────────────────

function ClausesSection({ clauses }: { clauses: Clause[] }) {
  if (!clauses?.length) {
    return <EmptyState text="No clauses extracted for this contract." />
  }

  return (
    <div className="space-y-4">
      {clauses.map((clause) => (
        <div key={clause.id} className="border border-gray-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            {clause.section_number && (
              <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">{clause.section_number}</span>
            )}
            {clause.clause_type && (
              <span className="text-xs bg-violet-100 text-violet-700 px-2 py-0.5 rounded capitalize">
                {clause.clause_type.replace(/_/g, ' ')}
              </span>
            )}
            {clause.risk_level && (
              <span className={cn(
                "text-xs px-2 py-0.5 rounded capitalize",
                clause.risk_level === 'high' ? 'bg-red-100 text-red-700' :
                clause.risk_level === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700'
              )}>
                {clause.risk_level}
              </span>
            )}
          </div>
          {clause.title && <p className="font-medium text-gray-900 mb-1">{clause.title}</p>}
          <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">{clause.text}</p>
        </div>
      ))}
    </div>
  )
}

// ── Obligations ────────────────────────────────────────────────────

function ObligationsSection({ obligations }: { obligations: ObligationItem[] }) {
  if (!obligations?.length) {
    return <EmptyState text="No obligations found for this contract." />
  }

  const now = new Date()
  const sorted = [...obligations].sort((a, b) => {
    if (!a.deadline) return 1
    if (!b.deadline) return -1
    return new Date(a.deadline).getTime() - new Date(b.deadline).getTime()
  })

  return (
    <div className="space-y-3">
      {sorted.map((ob) => {
        const isOverdue = ob.deadline && new Date(ob.deadline) < now && ob.status !== 'completed'
        return (
          <div key={ob.id} className={cn(
            "border rounded-lg p-4",
            isOverdue ? "border-red-200 bg-red-50" : "border-gray-200"
          )}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  {ob.is_critical && (
                    <ExclamationCircleIcon className="w-4 h-4 text-red-600 shrink-0" />
                  )}
                  <p className="font-medium text-gray-900">{ob.description}</p>
                </div>
                <div className="flex flex-wrap gap-2 mt-2 text-xs">
                  {ob.obligation_type && (
                    <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded capitalize">
                      {ob.obligation_type.replace(/_/g, ' ')}
                    </span>
                  )}
                  {ob.responsible_party && (
                    <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
                      {ob.responsible_party}
                    </span>
                  )}
                  {ob.priority && (
                    <span className={cn(
                      "px-2 py-0.5 rounded capitalize",
                      ob.priority === 'critical' ? 'bg-red-100 text-red-700' :
                      ob.priority === 'high' ? 'bg-orange-100 text-orange-700' :
                      'bg-gray-100 text-gray-600'
                    )}>
                      {ob.priority}
                    </span>
                  )}
                </div>
                {ob.consequence && (
                  <p className="text-xs text-gray-500 mt-2 italic">Consequence: {ob.consequence}</p>
                )}
              </div>
              <div className="text-right shrink-0">
                {ob.deadline && (
                  <p className={cn(
                    "text-sm font-medium",
                    isOverdue ? "text-red-700" : "text-gray-700"
                  )}>
                    {isOverdue ? 'OVERDUE' : formatDate(ob.deadline)}
                  </p>
                )}
                <p className={cn(
                  "text-xs mt-1 capitalize",
                  ob.status === 'completed' ? "text-green-600" : "text-gray-500"
                )}>
                  {ob.status || 'pending'}
                </p>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── SLAs ───────────────────────────────────────────────────────────

function SLASection({ slas }: { slas: SLAItem[] }) {
  if (!slas?.length) {
    return <EmptyState text="No SLAs defined for this contract." />
  }

  return (
    <div className="space-y-3">
      {slas.map((sla) => {
        const compliance = sla.current_compliance_rate
        const complianceColor = compliance == null ? 'gray'
          : compliance >= 95 ? 'green'
          : compliance >= 80 ? 'amber'
          : 'red'

        return (
          <div key={sla.id} className="border border-gray-200 rounded-lg p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <p className="font-medium text-gray-900">{sla.sla_name}</p>
                {sla.sla_description && (
                  <p className="text-sm text-gray-600 mt-1">{sla.sla_description}</p>
                )}
                <div className="flex flex-wrap gap-2 mt-2 text-xs">
                  {sla.metric_type && (
                    <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded capitalize">
                      {sla.metric_type.replace(/_/g, ' ')}
                    </span>
                  )}
                  {sla.target_value != null && (
                    <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
                      Target: {sla.target_operator || '>='} {sla.target_value}{sla.metric_unit || ''}
                    </span>
                  )}
                  {sla.severity && (
                    <span className={cn(
                      "px-2 py-0.5 rounded capitalize",
                      sla.severity === 'critical' ? 'bg-red-100 text-red-700' :
                      sla.severity === 'high' ? 'bg-orange-100 text-orange-700' :
                      'bg-gray-100 text-gray-600'
                    )}>
                      {sla.severity}
                    </span>
                  )}
                  {sla.measurement_period && (
                    <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded capitalize">
                      {sla.measurement_period}
                    </span>
                  )}
                </div>
                {sla.has_penalty && sla.penalty_description && (
                  <p className="text-xs text-gray-500 mt-2 italic">Penalty: {sla.penalty_description}</p>
                )}
              </div>
              <div className="text-right shrink-0">
                {compliance != null ? (
                  <div className="flex items-center gap-1.5">
                    {complianceColor === 'green' && <CheckCircleIcon className="w-5 h-5 text-green-600" />}
                    {complianceColor === 'amber' && <ExclamationTriangleIcon className="w-5 h-5 text-amber-600" />}
                    {complianceColor === 'red' && <ExclamationCircleIcon className="w-5 h-5 text-red-600" />}
                    <span className={cn(
                      "text-lg font-bold",
                      complianceColor === 'green' ? 'text-green-700' :
                      complianceColor === 'amber' ? 'text-amber-700' : 'text-red-700'
                    )}>
                      {compliance.toFixed(1)}%
                    </span>
                  </div>
                ) : (
                  <span className="text-sm text-gray-400">No data</span>
                )}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Comments ───────────────────────────────────────────────────────

function CommentsSection({ comments, newComment, setNewComment, onSubmit, isPending }: {
  comments: Comment[]
  newComment: string
  setNewComment: (v: string) => void
  onSubmit: (e: React.FormEvent) => void
  isPending: boolean
}) {
  return (
    <div>
      {/* Add comment form */}
      <form onSubmit={onSubmit} className="flex gap-2 mb-6">
        <input
          type="text"
          value={newComment}
          onChange={(e) => setNewComment(e.target.value)}
          placeholder="Add a comment..."
          className="flex-1 px-4 py-2 border rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
        />
        <button
          type="submit"
          disabled={!newComment.trim() || isPending}
          className="px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50 transition-colors flex items-center gap-2"
        >
          <PaperAirplaneIcon className="w-4 h-4" />
          Send
        </button>
      </form>

      {/* Comment list */}
      {comments.length === 0 ? (
        <EmptyState text="No comments yet. Be the first to add one." />
      ) : (
        <div className="space-y-3">
          {comments.map((comment) => (
            <div key={comment.id} className="flex items-start gap-3">
              <div className={cn(
                "h-8 w-8 rounded-full flex items-center justify-center text-sm font-medium shrink-0",
                comment.is_internal_author
                  ? "bg-blue-100 text-blue-700"
                  : "bg-violet-100 text-violet-700"
              )}>
                {comment.author_name?.charAt(0).toUpperCase() || '?'}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-gray-900 text-sm">{comment.author_name}</span>
                  <span className={cn(
                    "text-xs px-1.5 py-0.5 rounded",
                    comment.is_internal_author
                      ? "bg-blue-100 text-blue-600"
                      : "bg-violet-100 text-violet-600"
                  )}>
                    {comment.is_internal_author ? 'Internal' : 'External'}
                  </span>
                  <span className="text-xs text-gray-400">{formatDate(comment.created_at)}</span>
                </div>
                <p className="text-sm text-gray-700 mt-1">{comment.content}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="text-center py-8 text-gray-500 text-sm">
      {text}
    </div>
  )
}
