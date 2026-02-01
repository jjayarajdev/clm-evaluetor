import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  DocumentTextIcon,
  ExclamationTriangleIcon,
  ClipboardDocumentListIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  UserGroupIcon,
  BuildingOfficeIcon,
  CalendarIcon,
  CurrencyDollarIcon,
  ShieldExclamationIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn, formatDate, formatCurrency } from '@/lib/utils'
import type { ContractIntelligence as ContractIntelligenceType } from '@/types'

interface Props {
  contractId: string
}

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

export default function ContractIntelligence({ contractId }: Props) {
  const queryClient = useQueryClient()

  const { data, isLoading, error } = useQuery({
    queryKey: ['contract-intelligence', contractId],
    queryFn: () => api.getContractIntelligence(contractId),
  })

  const analyzeMutation = useMutation({
    mutationFn: () => api.analyzeContract(contractId),
    onSuccess: () => {
      // Refetch after a delay to allow analysis to complete
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['contract-intelligence', contractId] })
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

      {/* Two column layout for clauses and risks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Clause Breakdown */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-gray-900 flex items-center gap-2">
              <ClipboardDocumentListIcon className="h-5 w-5 text-gray-400" />
              Clause Breakdown
            </h3>
          </div>
          <div className="card-body">
            <div className="space-y-2">
              {clause_breakdown.filter(c => c.clause_type !== 'other').map((clause) => (
                <div key={clause.clause_type} className="flex items-center justify-between py-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-700">
                      {CLAUSE_TYPE_LABELS[clause.clause_type] || clause.clause_type}
                    </span>
                    {clause.high_risk_count > 0 && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">
                        {clause.high_risk_count} high risk
                      </span>
                    )}
                  </div>
                  <span className="text-sm font-medium text-gray-900">{clause.count}</span>
                </div>
              ))}
              {clause_breakdown.find(c => c.clause_type === 'other') && (
                <div className="flex items-center justify-between py-1 border-t border-gray-100 mt-2 pt-2">
                  <span className="text-sm text-gray-500">Unclassified</span>
                  <span className="text-sm text-gray-500">
                    {clause_breakdown.find(c => c.clause_type === 'other')?.count || 0}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Risk Summary */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-gray-900 flex items-center gap-2">
              <ShieldExclamationIcon className="h-5 w-5 text-gray-400" />
              Risk Assessment
            </h3>
          </div>
          <div className="card-body">
            <div className="flex items-center gap-4 mb-4">
              <div className={cn(
                "px-3 py-1 rounded-full text-sm font-medium",
                risk_summary.risk_level === 'low' && "bg-green-100 text-green-800",
                risk_summary.risk_level === 'medium' && "bg-amber-100 text-amber-800",
                risk_summary.risk_level === 'high' && "bg-red-100 text-red-800",
                risk_summary.risk_level === 'critical' && "bg-purple-100 text-purple-800",
                !risk_summary.risk_level && "bg-gray-100 text-gray-800",
              )}>
                {risk_summary.risk_level?.toUpperCase() || 'NOT ASSESSED'} RISK
              </div>
              {risk_summary.risk_score !== null && (
                <span className="text-sm text-gray-500">Score: {risk_summary.risk_score}/100</span>
              )}
            </div>

            {risk_summary.high_risk_clauses.length > 0 ? (
              <div className="space-y-3">
                <p className="text-xs font-medium text-gray-500 uppercase">High Risk Clauses</p>
                {risk_summary.high_risk_clauses.slice(0, 3).map((clause) => (
                  <div key={clause.id} className="p-2 bg-red-50 rounded-lg">
                    <p className="text-xs font-medium text-red-800 mb-1">
                      {CLAUSE_TYPE_LABELS[clause.clause_type] || clause.clause_type}
                    </p>
                    <p className="text-xs text-red-700 line-clamp-2">{clause.excerpt}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500 flex items-center gap-2">
                <CheckCircleIcon className="h-5 w-5 text-green-500" />
                No high-risk clauses identified
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Obligations Matrix */}
      <div className="card">
        <div className="card-header">
          <h3 className="text-sm font-medium text-gray-900 flex items-center gap-2">
            <UserGroupIcon className="h-5 w-5 text-gray-400" />
            Obligations Matrix ({obligations_matrix.total_count} total)
          </h3>
        </div>
        <div className="card-body p-0">
          <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-gray-200">
            {/* Provider Obligations */}
            <div className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <div className="h-2 w-2 rounded-full bg-blue-500"></div>
                <h4 className="text-sm font-medium text-gray-700">
                  Provider Obligations ({obligations_matrix.provider_obligations.length})
                </h4>
              </div>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {obligations_matrix.provider_obligations.length > 0 ? (
                  obligations_matrix.provider_obligations.map((obl) => (
                    <div key={obl.id} className="p-2 bg-blue-50 rounded-lg">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-xs text-gray-700 flex-1">{obl.description}</p>
                        <span className={cn(
                          "text-xs px-1.5 py-0.5 rounded whitespace-nowrap",
                          OBLIGATION_TYPE_COLORS[obl.obligation_type] || OBLIGATION_TYPE_COLORS.other
                        )}>
                          {obl.obligation_type}
                        </span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-gray-400">No provider obligations found</p>
                )}
              </div>
            </div>

            {/* Client Obligations */}
            <div className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <div className="h-2 w-2 rounded-full bg-amber-500"></div>
                <h4 className="text-sm font-medium text-gray-700">
                  Client Obligations ({obligations_matrix.client_obligations.length})
                </h4>
              </div>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {obligations_matrix.client_obligations.length > 0 ? (
                  obligations_matrix.client_obligations.map((obl) => (
                    <div key={obl.id} className="p-2 bg-amber-50 rounded-lg">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-xs text-gray-700 flex-1">{obl.description}</p>
                        <span className={cn(
                          "text-xs px-1.5 py-0.5 rounded whitespace-nowrap",
                          OBLIGATION_TYPE_COLORS[obl.obligation_type] || OBLIGATION_TYPE_COLORS.other
                        )}>
                          {obl.obligation_type}
                        </span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-gray-400">No client obligations found</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
