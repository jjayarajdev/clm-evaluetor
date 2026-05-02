import { useState } from 'react'
import { useParams, Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  DocumentTextIcon,
  ShieldExclamationIcon,
  ArrowPathIcon,
  TrashIcon,
  ChartBarIcon,
  LinkIcon,
  InformationCircleIcon,
  ShareIcon,
  DocumentMagnifyingGlassIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  PencilIcon,
  CheckIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import { client as apiClient } from '@/lib/api/client'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import SLASummary from '@/components/dashboard/SLASummary'
import CustomFieldsDisplay from '@/components/contracts/CustomFieldsDisplay'
import SuggestedLinksPanel from '@/components/contracts/SuggestedLinksPanel'
import ContractSharing from '@/components/contracts/ContractSharing'
import ContractDocumentsTab from '@/components/contracts/ContractDocumentsTab'
import ContractReviewPane from '@/components/contracts/ContractReviewPane'
import ContractPdfViewer from '@/components/contracts/ContractPdfViewer'
import type { HighlightRect } from '@/lib/api/contracts'
import { useAuth } from '@/contexts/AuthContext'
import { useTenantConfig } from '@/contexts/TenantConfigContext'
import { cn, formatDate, formatCurrency, formatFileSize, getRiskColor, getStatusColor } from '@/lib/utils'

// Map config icon names to Heroicon components
const TAB_ICON_MAP: Record<string, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
  document: InformationCircleIcon,
  eye: DocumentMagnifyingGlassIcon,
  chart: ChartBarIcon,
  link: LinkIcon,
  folder: DocumentTextIcon,
  share: ShareIcon,
}

// Fallback tabs if config not loaded yet
const DEFAULT_TABS = [
  { id: 'overview', label: 'Overview', icon: 'document' },
  { id: 'review', label: 'Review', icon: 'eye' },
  { id: 'slas', label: 'SLAs', icon: 'chart' },
  { id: 'related', label: 'Related Docs', icon: 'link' },
  { id: 'documents', label: 'Documents', icon: 'folder' },
  { id: 'sharing', label: 'Sharing', icon: 'share' },
]

export default function ContractViewPage() {
  const { id } = useParams<{ id: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const { config, contractTypeLabel, uiLabel } = useTenantConfig()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  // Build tabs from config or use defaults
  const tabs = (config?.ui?.detail_tabs || DEFAULT_TABS).map((t) => ({
    id: t.id,
    label: t.label,
    iconComponent: TAB_ICON_MAP[t.icon || ''] || InformationCircleIcon,
  }))

  // Get active tab from URL or default to first tab
  const activeTab = searchParams.get('tab') || 'overview'
  const setActiveTab = (tab: string) => {
    setSearchParams({ tab })
  }

  // Determine if user can edit custom fields (admin, legal, or procurement roles)
  const canEditCustomFields = user?.role === 'admin' || user?.role === 'legal' || user?.role === 'procurement' || user?.role === 'super_admin'

  const { data: contract, isLoading, error } = useQuery({
    queryKey: ['contract', id],
    queryFn: () => api.getContract(id!),
    enabled: !!id,
  })

  const processMutation = useMutation({
    mutationFn: () => api.processContract(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract', id] })
    },
  })

  const analyzeMutation = useMutation({
    mutationFn: () => api.analyzeContract(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract', id] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteContract(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] })
      queryClient.invalidateQueries({ queryKey: ['contracts-summary'] })
      navigate('/contracts')
    },
  })

  const updateMetadataMutation = useMutation({
    mutationFn: (data: Record<string, any>) =>
      apiClient.patch(`/contracts/${id}`, data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract', id] })
      queryClient.invalidateQueries({ queryKey: ['contracts'] })
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !contract) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">Contract not found</p>
        <Link to="/contracts" className="text-primary-600 hover:underline mt-2 inline-block">
          Back to contracts
        </Link>
      </div>
    )
  }

  const isCompleted = contract.status === 'completed'

  return (
    <div className="h-full flex flex-col">
      {/* Compact Header */}
      <div className="flex-shrink-0 border-b border-gray-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4 min-w-0">
            <Link
              to="/contracts"
              className="p-2 -ml-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg flex-shrink-0"
            >
              <ArrowLeftIcon className="h-5 w-5" />
            </Link>
            <div className="min-w-0">
              <h1 className="text-xl font-bold text-gray-900 truncate">{contract.filename}</h1>
              <div className="flex items-center gap-3 mt-1">
                <span className={cn(
                  'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize',
                  getStatusColor(contract.status)
                )}>
                  {contract.status}
                </span>
                {contract.risk_level && (
                  <span className={cn(
                    'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize',
                    getRiskColor(contract.risk_level)
                  )}>
                    {contract.risk_level} Risk
                  </span>
                )}
                {contract.contract_type && (
                  <span className="text-sm text-gray-500">
                    {contractTypeLabel(contract.contract_type)}
                  </span>
                )}
                {contract.counterparty && (
                  <span className="text-sm text-gray-500">
                    • {contract.counterparty}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            {contract.status === 'pending' && (
              <button
                onClick={() => processMutation.mutate()}
                disabled={processMutation.isPending}
                className="btn-secondary"
              >
                {processMutation.isPending ? (
                  <LoadingSpinner size="sm" className="mr-2" />
                ) : (
                  <ArrowPathIcon className="h-4 w-4 mr-2" />
                )}
                Process
              </button>
            )}
            {isCompleted && (
              <button
                onClick={() => analyzeMutation.mutate()}
                disabled={analyzeMutation.isPending}
                className="btn-primary"
              >
                {analyzeMutation.isPending ? (
                  <LoadingSpinner size="sm" className="mr-2 border-white border-t-transparent" />
                ) : (
                  <ShieldExclamationIcon className="h-4 w-4 mr-2" />
                )}
                Re-analyze
              </button>
            )}
            <Link
              to={`/query?contract=${contract.id}`}
              className="btn-secondary"
            >
              Ask AI
            </Link>
            {!showDeleteConfirm ? (
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="btn-secondary text-red-600 hover:text-red-700 hover:bg-red-50"
              >
                <TrashIcon className="h-4 w-4" />
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  className="btn-secondary text-sm py-1"
                >
                  Cancel
                </button>
                <button
                  onClick={() => deleteMutation.mutate()}
                  disabled={deleteMutation.isPending}
                  className="btn-secondary text-sm py-1 bg-red-600 text-white hover:bg-red-700"
                >
                  {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex-shrink-0 border-b border-gray-200 bg-white px-6">
        <nav className="flex gap-6" aria-label="Tabs">
          {tabs.map((tab) => {
            // Hide analysis tabs for non-completed contracts
            // overview and sharing are always visible
            if (!isCompleted && tab.id !== 'overview' && tab.id !== 'sharing') {
              return null
            }
            const Icon = tab.iconComponent
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex items-center gap-2 py-3 px-1 border-b-2 text-sm font-medium transition-colors',
                  activeTab === tab.id
                    ? 'border-primary-600 text-primary-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                )}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Review Tab - full-bleed, no padding */}
      {activeTab === 'review' && isCompleted && id && (
        <div className="flex-1 overflow-hidden">
          <ContractReviewPane contractId={id} contract={contract} />
        </div>
      )}

      {/* Quality Tab (Manufacturing) - full-bleed with PDF viewer */}
      {activeTab === 'quality' && isCompleted && id && (
        <div className="flex-1 overflow-hidden">
          <ClauseFilteredTab
            contractId={id}
            contract={contract}
            title="Quality & Compliance Clauses"
            clauseTypes={['warranty', 'limitation_of_liability', 'governance', 'definitions', 'data_protection']}
            emptyMessage="No quality-related clauses found in this contract."
          />
        </div>
      )}

      {/* Supply Chain Tab (Manufacturing) - full-bleed with PDF viewer */}
      {activeTab === 'supply_chain' && isCompleted && id && (
        <div className="flex-1 overflow-hidden">
          <ClauseFilteredTab
            contractId={id}
            contract={contract}
            title="Supply Chain & Logistics Clauses"
            clauseTypes={['scope', 'payment_terms', 'termination', 'confidentiality', 'intellectual_property']}
            emptyMessage="No supply chain clauses found in this contract."
          />
        </div>
      )}

      {/* Tab Content (all tabs except review, quality, supply_chain) */}
      {activeTab !== 'review' && activeTab !== 'quality' && activeTab !== 'supply_chain' && (
      <div className="flex-1 overflow-auto p-6 bg-gray-50">
        {/* Processing error banner */}
        {contract.processing_error && (
          <div className="mb-6 p-4 rounded-lg border border-red-200 bg-red-50">
            <p className="text-sm font-medium text-red-800">Processing Error</p>
            <p className="text-sm text-red-700 mt-1">{contract.processing_error}</p>
          </div>
        )}

        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left column - Details */}
            <div className="lg:col-span-2 space-y-6">
              {/* Contract Details */}
              <div className="card">
                <div className="card-header">
                  <h2 className="text-sm font-medium text-gray-900">Contract Details</h2>
                </div>
                <div className="card-body grid grid-cols-2 md:grid-cols-3 gap-4">
                  <EditableField
                    label={uiLabel('counterparty', 'Counterparty')}
                    value={contract.counterparty}
                    fieldName="counterparty"
                    onSave={(field, val) => updateMetadataMutation.mutate({ [field]: val })}
                    canEdit={canEditCustomFields}
                  />
                  <EditableField
                    label={uiLabel('contract_value', 'Contract Value')}
                    value={contract.contract_value ? String(contract.contract_value) : null}
                    displayValue={contract.contract_value ? formatCurrency(contract.contract_value, contract.currency || 'USD') : null}
                    fieldName="contract_value"
                    type="number"
                    onSave={(field, val) => updateMetadataMutation.mutate({ [field]: Number(val) })}
                    canEdit={canEditCustomFields}
                  />
                  <EditableField
                    label="Contract Type"
                    value={contract.contract_type || null}
                    displayValue={contract.contract_type ? contractTypeLabel(contract.contract_type) : null}
                    fieldName="contract_type"
                    onSave={(field, val) => updateMetadataMutation.mutate({ [field]: val })}
                    canEdit={canEditCustomFields}
                  />
                  <EditableField
                    label="Effective Date"
                    value={contract.effective_date || null}
                    displayValue={formatDate(contract.effective_date)}
                    fieldName="effective_date"
                    type="date"
                    onSave={(field, val) => updateMetadataMutation.mutate({ [field]: val })}
                    canEdit={canEditCustomFields}
                  />
                  <EditableField
                    label="Expiration Date"
                    value={contract.expiration_date || null}
                    displayValue={formatDate(contract.expiration_date)}
                    fieldName="expiration_date"
                    type="date"
                    onSave={(field, val) => updateMetadataMutation.mutate({ [field]: val })}
                    canEdit={canEditCustomFields}
                  />
                  <EditableField
                    label="Jurisdiction"
                    value={contract.jurisdiction}
                    fieldName="jurisdiction"
                    onSave={(field, val) => updateMetadataMutation.mutate({ [field]: val })}
                    canEdit={canEditCustomFields}
                  />
                  <div>
                    <p className="text-xs text-gray-500">Auto-Renewal</p>
                    <p className="text-sm font-medium text-gray-900">
                      {contract.auto_renewal ? 'Yes' : 'No'}
                      {contract.notice_period_days && ` (${contract.notice_period_days}d notice)`}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Renewal Term</p>
                    <p className="text-sm font-medium text-gray-900">
                      {contract.renewal_term_months ? `${contract.renewal_term_months} months` : '-'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Custom Fields */}
              <CustomFieldsDisplay contract={contract} canEdit={canEditCustomFields} />

              {/* Risk Assessment - only show if analyzed */}
              {contract.risk_score !== null && (
                <div className="card">
                  <div className="card-header">
                    <h2 className="text-sm font-medium text-gray-900">Risk Assessment</h2>
                  </div>
                  <div className="card-body">
                    <div className="flex items-center gap-6">
                      <div className={cn(
                        'h-20 w-20 rounded-full flex items-center justify-center text-2xl font-bold',
                        getRiskColor(contract.risk_level)
                      )}>
                        {contract.risk_score}
                      </div>
                      <div className="flex-1">
                        <p className="text-lg font-medium text-gray-900 capitalize mb-1">
                          {contract.risk_level} Risk
                        </p>
                        <p className="text-sm text-gray-500">
                          Based on analysis of {contract.clause_count} clauses and {contract.obligation_count} obligations
                        </p>
                        {isCompleted && (
                          <button
                            onClick={() => setActiveTab('review')}
                            className="text-sm text-primary-600 hover:text-primary-700 mt-2"
                          >
                            View detailed analysis →
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Right column - File info & stats */}
            <div className="space-y-6">
              {/* File Information */}
              <div className="card">
                <div className="card-header">
                  <h2 className="text-sm font-medium text-gray-900">File Information</h2>
                </div>
                <div className="card-body space-y-4">
                  <div className="flex items-center gap-3">
                    <DocumentTextIcon className="h-10 w-10 text-gray-400" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {contract.filename}
                      </p>
                      <p className="text-xs text-gray-500">
                        {formatFileSize(contract.file_size)} • {contract.mime_type}
                      </p>
                    </div>
                  </div>
                  <div className="pt-4 border-t border-gray-200 space-y-3">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Uploaded</span>
                      <span className="text-gray-900">{formatDate(contract.created_at)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Last Updated</span>
                      <span className="text-gray-900">{formatDate(contract.updated_at)}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Extraction Stats */}
              {isCompleted && (
                <div className="card">
                  <div className="card-header">
                    <h2 className="text-sm font-medium text-gray-900">Extraction Summary</h2>
                  </div>
                  <div className="card-body">
                    <div className="grid grid-cols-2 gap-4">
                      <button
                        onClick={() => setActiveTab('review')}
                        className="text-center p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
                      >
                        <p className="text-2xl font-bold text-gray-900">{contract.clause_count}</p>
                        <p className="text-xs text-gray-500">Clauses</p>
                      </button>
                      <button
                        onClick={() => setActiveTab('review')}
                        className="text-center p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
                      >
                        <p className="text-2xl font-bold text-gray-900">{contract.obligation_count}</p>
                        <p className="text-xs text-gray-500">Obligations</p>
                      </button>
                      <button
                        onClick={() => setActiveTab('slas')}
                        className="text-center p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
                      >
                        <p className="text-2xl font-bold text-gray-900">{contract.sla_count || 0}</p>
                        <p className="text-xs text-gray-500">SLAs</p>
                      </button>
                      <button
                        onClick={() => setActiveTab('related')}
                        className="text-center p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
                      >
                        <p className="text-2xl font-bold text-primary-600">→</p>
                        <p className="text-xs text-gray-500">Related</p>
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* SLAs Tab */}
        {activeTab === 'slas' && isCompleted && id && (
          <SLASummary contractId={id} />
        )}

        {/* Related Docs Tab */}
        {activeTab === 'related' && isCompleted && id && (
          <SuggestedLinksPanel contractId={id} />
        )}

        {/* Documents Tab */}
        {activeTab === 'documents' && id && (
          <ContractDocumentsTab contractId={id} />
        )}

        {/* Sharing Tab */}
        {activeTab === 'sharing' && id && (
          <ContractSharing contractId={id} />
        )}
      </div>
      )}
    </div>
  )
}


const CLAUSE_LABELS: Record<string, string> = {
  quality_assurance: 'Quality Assurance',
  warranty: 'Warranty',
  limitation_of_liability: 'Limitation of Liability',
  definitions: 'Definitions',
  governance: 'Governance',
  scope: 'Scope of Work',
  payment_terms: 'Payment Terms',
  termination: 'Termination',
  confidentiality: 'Confidentiality',
  intellectual_property: 'Intellectual Property',
  data_protection: 'Data Protection',
  preamble: 'Preamble',
  service_level: 'Service Level',
  procedural: 'Procedural',
  indemnification: 'Indemnification',
  force_majeure: 'Force Majeure',
  dispute_resolution: 'Dispute Resolution',
  other: 'Other',
}

const RISK_COLORS: Record<string, string> = {
  low: 'bg-green-100 text-green-700',
  medium: 'bg-amber-100 text-amber-700',
  high: 'bg-red-100 text-red-700',
  critical: 'bg-purple-100 text-purple-700',
}

/** Inline-editable metadata field with pencil icon */
function EditableField({
  label,
  value,
  displayValue,
  fieldName,
  onSave,
  type = 'text',
  canEdit,
}: {
  label: string
  value: string | null | undefined
  displayValue?: string | null
  fieldName: string
  onSave: (field: string, val: string) => void
  type?: 'text' | 'date' | 'number'
  canEdit: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value || '')

  const handleSave = () => {
    if (draft !== (value || '')) {
      onSave(fieldName, draft)
    }
    setEditing(false)
  }

  const handleCancel = () => {
    setDraft(value || '')
    setEditing(false)
  }

  const shown = displayValue !== undefined ? (displayValue || '-') : (value || '-')

  if (editing) {
    return (
      <div>
        <p className="text-xs text-gray-500 mb-1">{label}</p>
        <div className="flex items-center gap-1">
          <input
            type={type}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') handleCancel() }}
            autoFocus
            className="text-sm font-medium text-gray-900 border border-primary-300 rounded px-2 py-0.5 w-full focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
          <button onClick={handleSave} className="p-0.5 text-green-600 hover:text-green-700">
            <CheckIcon className="h-4 w-4" />
          </button>
          <button onClick={handleCancel} className="p-0.5 text-gray-400 hover:text-gray-600">
            <XMarkIcon className="h-4 w-4" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="group">
      <p className="text-xs text-gray-500">{label}</p>
      <div className="flex items-center gap-1">
        <p className="text-sm font-medium text-gray-900">{shown}</p>
        {canEdit && (
          <button
            onClick={() => { setDraft(value || ''); setEditing(true) }}
            className="opacity-0 group-hover:opacity-100 p-0.5 text-gray-400 hover:text-primary-600 transition-opacity"
            title={`Edit ${label.toLowerCase()}`}
          >
            <PencilIcon className="h-3 w-3" />
          </button>
        )}
      </div>
    </div>
  )
}

/** Compact collapsible clause row — matches the Review tab style */
function ClauseCompactRow({ clause, onViewSource, isActive }: { clause: any; onViewSource: () => void; isActive?: boolean }) {
  const [expanded, setExpanded] = useState(false)
  const [showFull, setShowFull] = useState(false)
  const label = CLAUSE_LABELS[clause.clause_type] || clause.clause_type.replace(/_/g, ' ')
  const preview = clause.summary || clause.text.substring(0, 80)
  const isLongText = clause.text.length > 300
  const displayText = showFull || !isLongText ? clause.text : clause.text.substring(0, 300) + '...'

  return (
    <div className={cn('px-4 py-2.5 hover:bg-gray-50 cursor-pointer', isActive && 'bg-primary-50 border-l-2 border-primary-500')}>
      <div className="flex items-center gap-2" onClick={onViewSource}>
        <button onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }} className="flex-1 flex items-center gap-2 text-left min-w-0">
          {expanded
            ? <ChevronDownIcon className="h-3 w-3 text-gray-400 flex-shrink-0" />
            : <ChevronRightIcon className="h-3 w-3 text-gray-400 flex-shrink-0" />
          }
          <span className="text-xs font-medium text-primary-600 flex-shrink-0">{label}</span>
          {clause.section_number && (
            <span className="text-xs text-gray-400 flex-shrink-0">{clause.section_number}</span>
          )}
          <span className="text-xs text-gray-600 truncate">{preview}...</span>
        </button>
        {clause.risk_level && (
          <span className={cn('inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium flex-shrink-0', RISK_COLORS[clause.risk_level] || 'bg-gray-100 text-gray-600')}>
            {clause.risk_level}
          </span>
        )}
        {clause.page_number && (
          <span className="text-[10px] text-gray-400 flex-shrink-0">p.{clause.page_number}</span>
        )}
        <button
          onClick={(e) => { e.stopPropagation(); onViewSource() }}
          title={clause.page_number ? `View on page ${clause.page_number}` : 'Highlight in PDF'}
          className="p-1 rounded hover:bg-primary-100 text-primary-600 flex-shrink-0"
        >
          <DocumentMagnifyingGlassIcon className="h-4 w-4" />
        </button>
      </div>
      {expanded && (
        <div className="mt-2 ml-5 space-y-2">
          <p className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed">{displayText}</p>
          {isLongText && (
            <button
              onClick={(e) => { e.stopPropagation(); setShowFull(!showFull) }}
              className="text-[10px] font-medium text-primary-600 hover:text-primary-700"
            >
              {showFull ? 'Show less' : 'Show full text'}
            </button>
          )}
          {clause.risk_reason && (
            <p className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1">{clause.risk_reason}</p>
          )}
        </div>
      )}
    </div>
  )
}

/** Split-pane clause tab with PDF viewer and highlighting — matches Review tab pattern */
function ClauseFilteredTab({
  contractId,
  contract,
  title,
  clauseTypes,
  emptyMessage,
}: {
  contractId: string
  contract: { mime_type?: string | null }
  title: string
  clauseTypes: string[]
  emptyMessage: string
}) {
  const [highlightPage, setHighlightPage] = useState<number | null>(null)
  const [highlightText, setHighlightText] = useState<string | null>(null)
  const [activeRects, setActiveRects] = useState<HighlightRect[] | null>(null)
  const [activeClauseId, setActiveClauseId] = useState<string | null>(null)

  const { data: allClauses, isLoading } = useQuery<any[]>({
    queryKey: ['contract-clauses', contractId],
    queryFn: async () => {
      const response = await apiClient.get(`/contracts/${contractId}/clauses`)
      return response.data
    },
  })

  const { data: highlights } = useQuery({
    queryKey: ['contract-highlights', contractId],
    queryFn: () => api.getContractHighlights(contractId),
  })

  const filtered = allClauses?.filter((c) => clauseTypes.includes(c.clause_type)) || []
  const others = allClauses?.filter((c) => !clauseTypes.includes(c.clause_type)) || []

  const handleViewSource = (clause: any) => {
    setActiveClauseId(clause.id)
    const clauseHL = highlights?.highlights?.[clause.id]
    if (clauseHL?.rects?.length) {
      setActiveRects(clauseHL.rects)
      setHighlightPage(clauseHL.rects[0].page)
      setHighlightText(null)
    } else {
      setActiveRects(null)
      setHighlightPage(clause.page_number || null)
      // Use ~80 chars so only the opening line gets highlighted (not entire section)
      const searchText = clause.text.substring(0, 80)
      setHighlightText(searchText)
    }
  }

  return (
    <div className="flex h-full">
      {/* Left Pane: Clause List */}
      <div className="flex-shrink-0 overflow-y-auto border-r border-gray-200 bg-gray-50" style={{ width: '45%' }}>
        <div className="sticky top-0 bg-gray-50 border-b border-gray-200 px-4 py-3 z-10">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
            <span className="text-xs text-gray-500">
              {filtered.length} relevant · {allClauses?.length || 0} total
            </span>
          </div>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-8"><LoadingSpinner size="lg" /></div>
        ) : !allClauses || allClauses.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            <DocumentTextIcon className="h-10 w-10 mx-auto mb-3 text-gray-300" />
            <p className="text-sm">{emptyMessage}</p>
          </div>
        ) : (
          <>
            {filtered.length > 0 ? (
              <div className="divide-y divide-gray-100">
                {filtered.map((clause) => (
                  <ClauseCompactRow
                    key={clause.id}
                    clause={clause}
                    isActive={activeClauseId === clause.id}
                    onViewSource={() => handleViewSource(clause)}
                  />
                ))}
              </div>
            ) : (
              <div className="p-6 text-center text-gray-400 text-sm">
                No matching clauses for this category.
              </div>
            )}

            {others.length > 0 && (
              <details className="border-t border-gray-200">
                <summary className="text-xs font-medium text-gray-500 cursor-pointer hover:text-gray-700 px-4 py-2 bg-gray-100">
                  Other clauses ({others.length})
                </summary>
                <div className="divide-y divide-gray-100 opacity-75">
                  {others.map((clause) => (
                    <ClauseCompactRow
                      key={clause.id}
                      clause={clause}
                      isActive={activeClauseId === clause.id}
                      onViewSource={() => handleViewSource(clause)}
                    />
                  ))}
                </div>
              </details>
            )}
          </>
        )}
      </div>

      {/* Right Pane: PDF Viewer */}
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
            setActiveClauseId(clauseId)
            const clauseHL = highlights?.highlights?.[clauseId]
            if (clauseHL?.rects?.length) {
              setActiveRects(clauseHL.rects)
              setHighlightPage(clauseHL.rects[0].page)
              setHighlightText(null)
            }
          }}
          onPageChange={() => { setHighlightText(null); setHighlightPage(null); setActiveRects(null); setActiveClauseId(null) }}
        />
      </div>
    </div>
  )
}
