import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  DocumentTextIcon,
  ClipboardDocumentListIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  UserGroupIcon,
  BuildingOfficeIcon,
  CalendarIcon,
  CurrencyDollarIcon,
  ShieldExclamationIcon,
  ChevronRightIcon,
  ExclamationTriangleIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn, formatDate, formatCurrency } from '@/lib/utils'

interface Props {
  contractId: string
}

type TabType = 'clauses' | 'risks' | 'obligations'

interface SelectedClauseType {
  type: 'clause_type'
  clauseType: string
  label: string
}

interface SelectedRiskClause {
  type: 'risk_clause'
  clauseId: string
  clauseType: string
  excerpt: string
}

interface SelectedObligation {
  type: 'obligation'
  obligationId: string
  description: string
  obligationType: string
  party: 'provider' | 'client'
}

type SelectedItem = SelectedClauseType | SelectedRiskClause | SelectedObligation | null

const CLAUSE_TYPE_LABELS: Record<string, string> = {
  // Legal/Risk clauses
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
  // Structural clauses
  preamble: 'Preamble',
  definitions: 'Definitions',
  service_order: 'Service Order',
  procedural: 'Procedural',
  exhibit: 'Exhibit/Schedule',
  // IT Service/Outsourcing clauses
  service_description: 'Service Description',
  service_level: 'Service Level',
  deliverable: 'Deliverables',
  governance: 'Governance',
  transition: 'Transition/Exit',
  change_management: 'Change Management',
  support: 'Support',
  security: 'Security',
  personnel: 'Personnel',
  pricing: 'Pricing',
  risk_mitigation: 'Risk Mitigation',
  scope: 'Scope of Work',
  acceptance: 'Acceptance',
  other: 'Other',
}

const OBLIGATION_TYPE_COLORS: Record<string, string> = {
  payment: 'bg-green-100 text-green-800',
  delivery: 'bg-blue-100 text-blue-800',
  reporting: 'bg-purple-100 text-purple-800',
  compliance: 'bg-amber-100 text-amber-800',
  notification: 'bg-cyan-100 text-cyan-800',
  performance: 'bg-indigo-100 text-indigo-800',
  other: 'bg-gray-100 text-gray-800',
}

const RISK_LEVEL_COLORS: Record<string, string> = {
  low: 'bg-green-100 text-green-800',
  medium: 'bg-amber-100 text-amber-800',
  high: 'bg-red-100 text-red-800',
  critical: 'bg-purple-100 text-purple-800',
}

export default function ContractIntelligence({ contractId }: Props) {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<TabType>('clauses')
  const [selectedItem, setSelectedItem] = useState<SelectedItem>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['contract-intelligence', contractId],
    queryFn: () => api.getContractIntelligence(contractId),
  })

  // Fetch clause details when a clause type is selected
  const { data: clauseDetails, isLoading: clauseDetailsLoading } = useQuery({
    queryKey: ['clauses-by-type', selectedItem?.type === 'clause_type' ? selectedItem.clauseType : null, contractId],
    queryFn: () => api.getClausesByType(
      (selectedItem as SelectedClauseType).clauseType,
      contractId
    ),
    enabled: selectedItem?.type === 'clause_type',
  })

  // Fetch individual clause detail for risk clause
  const { data: riskClauseDetail, isLoading: riskClauseLoading } = useQuery({
    queryKey: ['clause-detail', selectedItem?.type === 'risk_clause' ? (selectedItem as SelectedRiskClause).clauseId : null],
    queryFn: () => api.getClauseDetail((selectedItem as SelectedRiskClause).clauseId),
    enabled: selectedItem?.type === 'risk_clause',
  })

  // Fetch obligation detail
  const { data: obligationDetail, isLoading: obligationLoading } = useQuery({
    queryKey: ['obligation-detail', selectedItem?.type === 'obligation' ? (selectedItem as SelectedObligation).obligationId : null],
    queryFn: () => api.getObligationDetail((selectedItem as SelectedObligation).obligationId),
    enabled: selectedItem?.type === 'obligation',
  })

  const analyzeMutation = useMutation({
    mutationFn: () => api.analyzeContract(contractId),
    onSuccess: () => {
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['contract-intelligence', contractId] })
        queryClient.invalidateQueries({ queryKey: ['clauses-summary'] })
        queryClient.invalidateQueries({ queryKey: ['obligations-summary'] })
        queryClient.invalidateQueries({ queryKey: ['contracts-summary'] })
      }, 5000)
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="text-center py-8 text-red-600">
        Failed to load contract intelligence
      </div>
    )
  }

  const { key_terms, clause_breakdown, obligations_matrix, risk_summary, extraction_status } = data

  // Calculate classification coverage
  const totalClauses = clause_breakdown.reduce((sum, c) => sum + c.count, 0)
  const unclassifiedCount = clause_breakdown.find(c => c.clause_type === 'other')?.count || 0
  const classifiedCount = totalClauses - unclassifiedCount
  const coveragePercent = totalClauses > 0 ? Math.round((classifiedCount / totalClauses) * 100) : 0

  const tabs = [
    { id: 'clauses' as const, label: 'Clauses', icon: ClipboardDocumentListIcon, count: totalClauses },
    { id: 'risks' as const, label: 'Risks', icon: ShieldExclamationIcon, count: risk_summary.high_risk_clauses.length },
    { id: 'obligations' as const, label: 'Obligations', icon: UserGroupIcon, count: obligations_matrix.total_count },
  ]

  const renderDetailsPanel = () => {
    if (!selectedItem) {
      return (
        <div className="flex flex-col items-center justify-center h-full text-gray-400 py-12">
          <DocumentTextIcon className="h-12 w-12 mb-3" />
          <p className="text-sm">Select an item to view details</p>
        </div>
      )
    }

    // Clause type selected - show all clauses of that type
    if (selectedItem.type === 'clause_type') {
      if (clauseDetailsLoading) {
        return (
          <div className="flex items-center justify-center h-full">
            <LoadingSpinner size="md" />
          </div>
        )
      }

      return (
        <div className="h-full flex flex-col">
          <div className="flex items-center justify-between p-4 border-b border-gray-200">
            <div>
              <h4 className="font-medium text-gray-900">{selectedItem.label}</h4>
              <p className="text-xs text-gray-500">
                {clauseDetails?.total || 0} clause{clauseDetails?.total !== 1 ? 's' : ''} found
                {clauseDetails?.high_risk_count ? ` • ${clauseDetails.high_risk_count} high risk` : ''}
              </p>
            </div>
            <button
              onClick={() => setSelectedItem(null)}
              className="p-1 hover:bg-gray-100 rounded"
            >
              <XMarkIcon className="h-5 w-5 text-gray-400" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {clauseDetails?.clauses.map((clause) => (
              <Link
                key={clause.id}
                to={`/clauses/${clause.id}`}
                className={cn(
                  "block p-3 rounded-lg border transition-colors group",
                  clause.risk_level === 'high' || clause.risk_level === 'critical'
                    ? "border-red-200 bg-red-50 hover:bg-red-100"
                    : "border-gray-200 bg-white hover:bg-gray-50"
                )}
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    {clause.section_number && (
                      <span className="text-xs font-mono text-gray-500">§ {clause.section_number}</span>
                    )}
                    {clause.page_number && (
                      <span className="text-xs text-gray-400">p.{clause.page_number}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {clause.risk_level && (
                      <span className={cn(
                        "text-xs px-1.5 py-0.5 rounded font-medium uppercase",
                        RISK_LEVEL_COLORS[clause.risk_level] || 'bg-gray-100 text-gray-600'
                      )}>
                        {clause.risk_level}
                      </span>
                    )}
                    <ChevronRightIcon className="h-4 w-4 text-gray-400 group-hover:text-gray-600" />
                  </div>
                </div>
                <p className="text-sm text-gray-700 line-clamp-3">{clause.text}</p>
              </Link>
            ))}
            {(!clauseDetails?.clauses || clauseDetails.clauses.length === 0) && (
              <p className="text-sm text-gray-500 text-center py-4">No clauses found</p>
            )}
          </div>
        </div>
      )
    }

    // Risk clause selected - show full clause detail
    if (selectedItem.type === 'risk_clause') {
      if (riskClauseLoading) {
        return (
          <div className="flex items-center justify-center h-full">
            <LoadingSpinner size="md" />
          </div>
        )
      }

      return (
        <div className="h-full flex flex-col">
          <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-red-50">
            <div>
              <div className="flex items-center gap-2">
                <ExclamationTriangleIcon className="h-5 w-5 text-red-500" />
                <h4 className="font-medium text-red-900">
                  {CLAUSE_TYPE_LABELS[selectedItem.clauseType] || selectedItem.clauseType}
                </h4>
              </div>
              <p className="text-xs text-red-600 mt-0.5">High Risk Clause</p>
            </div>
            <button
              onClick={() => setSelectedItem(null)}
              className="p-1 hover:bg-red-100 rounded"
            >
              <XMarkIcon className="h-5 w-5 text-red-400" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            {riskClauseDetail && (
              <div className="space-y-4">
                <div className="flex items-center gap-4 text-sm">
                  {riskClauseDetail.section_number && (
                    <span className="font-mono text-gray-500">§ {riskClauseDetail.section_number}</span>
                  )}
                  {riskClauseDetail.page_number && (
                    <span className="text-gray-400">Page {riskClauseDetail.page_number}</span>
                  )}
                </div>

                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <p className="text-sm text-gray-700 whitespace-pre-wrap">{riskClauseDetail.text}</p>
                </div>

                {riskClauseDetail.risk_reason && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <h5 className="text-xs font-medium text-red-800 uppercase mb-2">Risk Assessment</h5>
                    <p className="text-sm text-red-700">{riskClauseDetail.risk_reason}</p>
                  </div>
                )}

                <Link
                  to={`/clauses/${selectedItem.clauseId}`}
                  className="inline-flex items-center gap-2 text-sm text-primary-600 hover:text-primary-700"
                >
                  View full details
                  <ChevronRightIcon className="h-4 w-4" />
                </Link>
              </div>
            )}
          </div>
        </div>
      )
    }

    // Obligation selected - show full obligation detail
    if (selectedItem.type === 'obligation') {
      if (obligationLoading) {
        return (
          <div className="flex items-center justify-center h-full">
            <LoadingSpinner size="md" />
          </div>
        )
      }

      const partyColor = selectedItem.party === 'provider' ? 'blue' : 'amber'

      return (
        <div className="h-full flex flex-col">
          <div className={cn(
            "flex items-center justify-between p-4 border-b",
            `bg-${partyColor}-50 border-${partyColor}-200`
          )}>
            <div>
              <div className="flex items-center gap-2">
                <div className={cn("h-2 w-2 rounded-full", `bg-${partyColor}-500`)} />
                <h4 className="font-medium text-gray-900 capitalize">
                  {selectedItem.party} Obligation
                </h4>
              </div>
              <p className="text-xs text-gray-500 mt-0.5 capitalize">{selectedItem.obligationType}</p>
            </div>
            <button
              onClick={() => setSelectedItem(null)}
              className="p-1 hover:bg-gray-100 rounded"
            >
              <XMarkIcon className="h-5 w-5 text-gray-400" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            {obligationDetail && (
              <div className="space-y-4">
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <p className="text-sm text-gray-700">{obligationDetail.description}</p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {obligationDetail.deadline && (
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Deadline</p>
                      <p className="text-sm font-medium">{formatDate(obligationDetail.deadline)}</p>
                    </div>
                  )}
                  {obligationDetail.recurrence_pattern && (
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Recurrence</p>
                      <p className="text-sm font-medium capitalize">{obligationDetail.recurrence_pattern}</p>
                    </div>
                  )}
                  {obligationDetail.status && (
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Status</p>
                      <p className="text-sm font-medium capitalize">{obligationDetail.status}</p>
                    </div>
                  )}
                  {obligationDetail.deadline_type && (
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Deadline Type</p>
                      <p className="text-sm font-medium capitalize">{obligationDetail.deadline_type}</p>
                    </div>
                  )}
                </div>

                {obligationDetail.consequence_of_breach && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                    <h5 className="text-xs font-medium text-amber-800 uppercase mb-2">Consequence if Not Met</h5>
                    <p className="text-sm text-amber-700">{obligationDetail.consequence_of_breach}</p>
                  </div>
                )}

                <Link
                  to={`/obligations/${selectedItem.obligationId}`}
                  className="inline-flex items-center gap-2 text-sm text-primary-600 hover:text-primary-700"
                >
                  View full details
                  <ChevronRightIcon className="h-4 w-4" />
                </Link>
              </div>
            )}
          </div>
        </div>
      )
    }

    return null
  }

  return (
    <div className="space-y-6">
      {/* Header with filename and analyze button */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">{data.filename}</h2>
          <p className="text-sm text-gray-500">
            {extraction_status.classified_clauses} of {extraction_status.total_clauses} clauses classified
            {' • '}{extraction_status.total_obligations} obligations extracted
          </p>
        </div>
        <button
          onClick={() => analyzeMutation.mutate()}
          disabled={analyzeMutation.isPending}
          className="btn-secondary flex items-center gap-2"
        >
          <ArrowPathIcon className={cn("h-4 w-4", analyzeMutation.isPending && "animate-spin")} />
          {analyzeMutation.isPending ? 'Analyzing...' : 'Re-analyze'}
        </button>
      </div>

      {/* Key Terms Grid */}
      <div className="card">
        <div className="card-header">
          <h3 className="text-sm font-medium text-gray-900 flex items-center gap-2">
            <DocumentTextIcon className="h-5 w-5 text-gray-400" />
            Key Contract Terms
          </h3>
        </div>
        <div className="card-body">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="flex items-start gap-3">
              <BuildingOfficeIcon className="h-5 w-5 text-gray-400 mt-0.5" />
              <div>
                <p className="text-xs text-gray-500">Counterparty</p>
                <p className="text-sm font-medium text-gray-900">{key_terms.counterparty || '—'}</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <DocumentTextIcon className="h-5 w-5 text-gray-400 mt-0.5" />
              <div>
                <p className="text-xs text-gray-500">Contract Type</p>
                <p className="text-sm font-medium text-gray-900 uppercase">{key_terms.contract_type || '—'}</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CalendarIcon className="h-5 w-5 text-gray-400 mt-0.5" />
              <div>
                <p className="text-xs text-gray-500">Effective Date</p>
                <p className="text-sm font-medium text-gray-900">{formatDate(key_terms.effective_date)}</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CalendarIcon className="h-5 w-5 text-gray-400 mt-0.5" />
              <div>
                <p className="text-xs text-gray-500">Expiration Date</p>
                <p className="text-sm font-medium text-gray-900">{formatDate(key_terms.expiration_date)}</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CurrencyDollarIcon className="h-5 w-5 text-gray-400 mt-0.5" />
              <div>
                <p className="text-xs text-gray-500">Contract Value</p>
                <p className="text-sm font-medium text-gray-900">
                  {key_terms.contract_value ? formatCurrency(key_terms.contract_value, key_terms.currency || 'USD') : '—'}
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <DocumentTextIcon className="h-5 w-5 text-gray-400 mt-0.5" />
              <div>
                <p className="text-xs text-gray-500">Jurisdiction</p>
                <p className="text-sm font-medium text-gray-900">{key_terms.jurisdiction || '—'}</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CalendarIcon className="h-5 w-5 text-gray-400 mt-0.5" />
              <div>
                <p className="text-xs text-gray-500">Notice Period</p>
                <p className="text-sm font-medium text-gray-900">
                  {key_terms.notice_period_days ? `${key_terms.notice_period_days} days` : '—'}
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <ArrowPathIcon className="h-5 w-5 text-gray-400 mt-0.5" />
              <div>
                <p className="text-xs text-gray-500">Auto-Renewal</p>
                <p className="text-sm font-medium text-gray-900">
                  {key_terms.auto_renewal === true ? 'Yes' : key_terms.auto_renewal === false ? 'No' : '—'}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Tabbed Intelligence Panel */}
      <div className="card overflow-hidden">
        <div className="grid grid-cols-1 lg:grid-cols-5 min-h-[500px]">
          {/* Left Panel - Tabs and Lists */}
          <div className="lg:col-span-2 border-r border-gray-200 flex flex-col">
            {/* Tab Headers */}
            <div className="flex border-b border-gray-200">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => {
                    setActiveTab(tab.id)
                    setSelectedItem(null)
                  }}
                  className={cn(
                    "flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-colors",
                    activeTab === tab.id
                      ? "text-primary-600 border-b-2 border-primary-600 bg-primary-50/50"
                      : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
                  )}
                >
                  <tab.icon className="h-4 w-4" />
                  <span>{tab.label}</span>
                  <span className={cn(
                    "text-xs px-1.5 py-0.5 rounded-full",
                    activeTab === tab.id ? "bg-primary-100 text-primary-700" : "bg-gray-100 text-gray-600"
                  )}>
                    {tab.count}
                  </span>
                </button>
              ))}
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-y-auto">
              {/* Clauses Tab */}
              {activeTab === 'clauses' && (
                <div className="p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs text-gray-500">Classification Coverage</span>
                    <span className={cn(
                      "text-xs font-medium px-2 py-0.5 rounded-full",
                      coveragePercent >= 80 ? "bg-green-100 text-green-700" :
                      coveragePercent >= 50 ? "bg-amber-100 text-amber-700" :
                      "bg-gray-100 text-gray-600"
                    )}>
                      {coveragePercent}%
                    </span>
                  </div>
                  <div className="space-y-1">
                    {clause_breakdown.filter(c => c.clause_type !== 'other').map((clause) => (
                      <button
                        key={clause.clause_type}
                        onClick={() => setSelectedItem({
                          type: 'clause_type',
                          clauseType: clause.clause_type,
                          label: CLAUSE_TYPE_LABELS[clause.clause_type] || clause.clause_type.replace(/_/g, ' '),
                        })}
                        className={cn(
                          "w-full flex items-center justify-between px-3 py-2 rounded-lg text-left transition-colors",
                          selectedItem?.type === 'clause_type' && (selectedItem as SelectedClauseType).clauseType === clause.clause_type
                            ? "bg-primary-100 text-primary-900"
                            : "hover:bg-gray-100"
                        )}
                      >
                        <div className="flex items-center gap-2">
                          {clause.high_risk_count > 0 && (
                            <span className="h-2 w-2 rounded-full bg-red-500" />
                          )}
                          <span className="text-sm text-gray-700">
                            {CLAUSE_TYPE_LABELS[clause.clause_type] || clause.clause_type.replace(/_/g, ' ')}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          {clause.high_risk_count > 0 && (
                            <span className="text-xs text-red-600">{clause.high_risk_count} risk</span>
                          )}
                          <span className="text-sm font-medium text-gray-500">{clause.count}</span>
                          <ChevronRightIcon className="h-4 w-4 text-gray-400" />
                        </div>
                      </button>
                    ))}
                    {unclassifiedCount > 0 && (
                      <div className="border-t border-gray-100 mt-2 pt-2">
                        <button
                          onClick={() => setSelectedItem({
                            type: 'clause_type',
                            clauseType: 'other',
                            label: 'Uncategorized Sections',
                          })}
                          className={cn(
                            "w-full flex items-center justify-between px-3 py-2 rounded-lg text-left transition-colors",
                            selectedItem?.type === 'clause_type' && (selectedItem as SelectedClauseType).clauseType === 'other'
                              ? "bg-gray-200"
                              : "hover:bg-gray-100"
                          )}
                        >
                          <span className="text-sm text-gray-500">Uncategorized</span>
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-gray-400">{unclassifiedCount}</span>
                            <ChevronRightIcon className="h-4 w-4 text-gray-300" />
                          </div>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Risks Tab */}
              {activeTab === 'risks' && (
                <div className="p-4">
                  <div className="flex items-center gap-3 mb-4">
                    <div className={cn(
                      "px-3 py-1 rounded-full text-sm font-medium",
                      risk_summary.risk_level === 'low' && "bg-green-100 text-green-800",
                      risk_summary.risk_level === 'medium' && "bg-amber-100 text-amber-800",
                      risk_summary.risk_level === 'high' && "bg-red-100 text-red-800",
                      risk_summary.risk_level === 'critical' && "bg-purple-100 text-purple-800",
                      !risk_summary.risk_level && "bg-gray-100 text-gray-800",
                    )}>
                      {risk_summary.risk_level?.toUpperCase() || 'NOT ASSESSED'}
                    </div>
                    {risk_summary.risk_score !== null && (
                      <span className="text-sm text-gray-500">Score: {risk_summary.risk_score}/100</span>
                    )}
                  </div>

                  {risk_summary.high_risk_clauses.length > 0 ? (
                    <div className="space-y-1">
                      <p className="text-xs font-medium text-gray-500 uppercase mb-2">High Risk Clauses</p>
                      {risk_summary.high_risk_clauses.map((clause) => (
                        <button
                          key={clause.id}
                          onClick={() => setSelectedItem({
                            type: 'risk_clause',
                            clauseId: clause.id,
                            clauseType: clause.clause_type,
                            excerpt: clause.excerpt,
                          })}
                          className={cn(
                            "w-full p-3 rounded-lg text-left transition-colors",
                            selectedItem?.type === 'risk_clause' && (selectedItem as SelectedRiskClause).clauseId === clause.id
                              ? "bg-red-100 border border-red-300"
                              : "bg-red-50 hover:bg-red-100"
                          )}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-medium text-red-800 mb-1">
                                {CLAUSE_TYPE_LABELS[clause.clause_type] || clause.clause_type}
                              </p>
                              <p className="text-xs text-red-700 line-clamp-2">{clause.excerpt}</p>
                            </div>
                            <ChevronRightIcon className="h-4 w-4 text-red-400 shrink-0 mt-1" />
                          </div>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-gray-500 py-4">
                      <CheckCircleIcon className="h-5 w-5 text-green-500" />
                      <span className="text-sm">No high-risk clauses identified</span>
                    </div>
                  )}
                </div>
              )}

              {/* Obligations Tab */}
              {activeTab === 'obligations' && (
                <div className="p-4 space-y-4">
                  {/* Provider Obligations */}
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <div className="h-2 w-2 rounded-full bg-blue-500" />
                      <h4 className="text-xs font-medium text-gray-700 uppercase">
                        Provider ({obligations_matrix.provider_obligations.length})
                      </h4>
                    </div>
                    <div className="space-y-1">
                      {obligations_matrix.provider_obligations.length > 0 ? (
                        obligations_matrix.provider_obligations.map((obl) => (
                          <button
                            key={obl.id}
                            onClick={() => setSelectedItem({
                              type: 'obligation',
                              obligationId: obl.id,
                              description: obl.description,
                              obligationType: obl.obligation_type,
                              party: 'provider',
                            })}
                            className={cn(
                              "w-full p-2 rounded-lg text-left transition-colors",
                              selectedItem?.type === 'obligation' && (selectedItem as SelectedObligation).obligationId === obl.id
                                ? "bg-blue-100 border border-blue-300"
                                : "bg-blue-50 hover:bg-blue-100"
                            )}
                          >
                            <div className="flex items-start justify-between gap-2">
                              <p className="text-xs text-gray-700 flex-1 line-clamp-2">{obl.description}</p>
                              <div className="flex items-center gap-1 shrink-0">
                                <span className={cn(
                                  "text-xs px-1.5 py-0.5 rounded",
                                  OBLIGATION_TYPE_COLORS[obl.obligation_type] || OBLIGATION_TYPE_COLORS.other
                                )}>
                                  {obl.obligation_type}
                                </span>
                                <ChevronRightIcon className="h-4 w-4 text-blue-400" />
                              </div>
                            </div>
                          </button>
                        ))
                      ) : (
                        <p className="text-xs text-gray-400 py-2">No provider obligations</p>
                      )}
                    </div>
                  </div>

                  {/* Client Obligations */}
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <div className="h-2 w-2 rounded-full bg-amber-500" />
                      <h4 className="text-xs font-medium text-gray-700 uppercase">
                        Client ({obligations_matrix.client_obligations.length})
                      </h4>
                    </div>
                    <div className="space-y-1">
                      {obligations_matrix.client_obligations.length > 0 ? (
                        obligations_matrix.client_obligations.map((obl) => (
                          <button
                            key={obl.id}
                            onClick={() => setSelectedItem({
                              type: 'obligation',
                              obligationId: obl.id,
                              description: obl.description,
                              obligationType: obl.obligation_type,
                              party: 'client',
                            })}
                            className={cn(
                              "w-full p-2 rounded-lg text-left transition-colors",
                              selectedItem?.type === 'obligation' && (selectedItem as SelectedObligation).obligationId === obl.id
                                ? "bg-amber-100 border border-amber-300"
                                : "bg-amber-50 hover:bg-amber-100"
                            )}
                          >
                            <div className="flex items-start justify-between gap-2">
                              <p className="text-xs text-gray-700 flex-1 line-clamp-2">{obl.description}</p>
                              <div className="flex items-center gap-1 shrink-0">
                                <span className={cn(
                                  "text-xs px-1.5 py-0.5 rounded",
                                  OBLIGATION_TYPE_COLORS[obl.obligation_type] || OBLIGATION_TYPE_COLORS.other
                                )}>
                                  {obl.obligation_type}
                                </span>
                                <ChevronRightIcon className="h-4 w-4 text-amber-400" />
                              </div>
                            </div>
                          </button>
                        ))
                      ) : (
                        <p className="text-xs text-gray-400 py-2">No client obligations</p>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Right Panel - Details */}
          <div className="lg:col-span-3 bg-gray-50">
            {renderDetailsPanel()}
          </div>
        </div>
      </div>
    </div>
  )
}
