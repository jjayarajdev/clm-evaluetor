import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  DocumentTextIcon,
  ExclamationTriangleIcon,
  ChevronRightIcon,
  CheckCircleIcon,
  ShieldExclamationIcon,
  XMarkIcon,
  BuildingOfficeIcon,
  DocumentMagnifyingGlassIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'

const CLAUSE_TYPE_COLORS: Record<string, { bg: string; bar: string; text: string }> = {
  // Legal/Risk clauses
  confidentiality: { bg: 'bg-purple-50', bar: 'bg-purple-500', text: 'text-purple-700' },
  indemnification: { bg: 'bg-red-50', bar: 'bg-red-500', text: 'text-red-700' },
  limitation_of_liability: { bg: 'bg-orange-50', bar: 'bg-orange-500', text: 'text-orange-700' },
  termination: { bg: 'bg-amber-50', bar: 'bg-amber-500', text: 'text-amber-700' },
  warranty: { bg: 'bg-yellow-50', bar: 'bg-yellow-500', text: 'text-yellow-700' },
  force_majeure: { bg: 'bg-cyan-50', bar: 'bg-cyan-500', text: 'text-cyan-700' },
  governing_law: { bg: 'bg-blue-50', bar: 'bg-blue-500', text: 'text-blue-700' },
  dispute_resolution: { bg: 'bg-indigo-50', bar: 'bg-indigo-500', text: 'text-indigo-700' },
  payment_terms: { bg: 'bg-green-50', bar: 'bg-green-500', text: 'text-green-700' },
  intellectual_property: { bg: 'bg-pink-50', bar: 'bg-pink-500', text: 'text-pink-700' },
  data_protection: { bg: 'bg-teal-50', bar: 'bg-teal-500', text: 'text-teal-700' },
  non_compete: { bg: 'bg-rose-50', bar: 'bg-rose-500', text: 'text-rose-700' },
  // IT Service/Outsourcing clauses
  service_description: { bg: 'bg-sky-50', bar: 'bg-sky-500', text: 'text-sky-700' },
  service_level: { bg: 'bg-emerald-50', bar: 'bg-emerald-500', text: 'text-emerald-700' },
  deliverable: { bg: 'bg-lime-50', bar: 'bg-lime-500', text: 'text-lime-700' },
  governance: { bg: 'bg-violet-50', bar: 'bg-violet-500', text: 'text-violet-700' },
  transition: { bg: 'bg-fuchsia-50', bar: 'bg-fuchsia-500', text: 'text-fuchsia-700' },
  change_management: { bg: 'bg-slate-50', bar: 'bg-slate-500', text: 'text-slate-700' },
  support: { bg: 'bg-blue-50', bar: 'bg-blue-400', text: 'text-blue-600' },
  security: { bg: 'bg-red-50', bar: 'bg-red-400', text: 'text-red-600' },
  personnel: { bg: 'bg-amber-50', bar: 'bg-amber-400', text: 'text-amber-600' },
  pricing: { bg: 'bg-green-50', bar: 'bg-green-400', text: 'text-green-600' },
  risk_mitigation: { bg: 'bg-orange-50', bar: 'bg-orange-400', text: 'text-orange-600' },
  scope: { bg: 'bg-indigo-50', bar: 'bg-indigo-400', text: 'text-indigo-600' },
  acceptance: { bg: 'bg-teal-50', bar: 'bg-teal-400', text: 'text-teal-600' },
  other: { bg: 'bg-gray-50', bar: 'bg-gray-400', text: 'text-gray-600' },
}

const CLAUSE_TYPE_LABELS: Record<string, string> = {
  // Legal/Risk clauses
  confidentiality: 'Confidentiality',
  indemnification: 'Indemnification',
  limitation_of_liability: 'Limitation of Liability',
  termination: 'Termination',
  warranty: 'Warranty',
  force_majeure: 'Force Majeure',
  governing_law: 'Governing Law',
  dispute_resolution: 'Dispute Resolution',
  payment_terms: 'Payment Terms',
  intellectual_property: 'Intellectual Property',
  data_protection: 'Data Protection',
  non_compete: 'Non-Compete',
  non_solicitation: 'Non-Solicitation',
  assignment: 'Assignment',
  notice: 'Notice',
  sla: 'SLA',
  auto_renewal: 'Auto-Renewal',
  // IT Service/Outsourcing clauses
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
  risk_mitigation: 'Risk Mitigation',
  scope: 'Scope',
  acceptance: 'Acceptance',
  other: 'Other',
}

const RISK_COLORS: Record<string, string> = {
  high: 'bg-red-100 text-red-800',
  medium: 'bg-amber-100 text-amber-800',
  low: 'bg-green-100 text-green-800',
}

interface Props {
  contractId?: string | null
  clientId?: string | null
}

export default function ClausesSummary({ contractId, clientId }: Props) {
  const [selectedType, setSelectedType] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['clauses-summary', contractId, clientId],
    queryFn: () => api.getClausesSummary(contractId || undefined, clientId || undefined),
  })

  const { data: drillDownData, isLoading: drillDownLoading } = useQuery({
    queryKey: ['clauses-by-type', selectedType, contractId],
    queryFn: () => api.getClausesByType(selectedType!, contractId || undefined),
    enabled: !!selectedType,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <LoadingSpinner size="md" />
      </div>
    )
  }

  if (error || !data || data.total === 0) {
    return null
  }

  // Filter out "other" for the main display, show classified clauses
  const classifiedClauses = data.by_type.filter(c => c.clause_type !== 'other')
  const otherClauses = data.by_type.find(c => c.clause_type === 'other')
  const maxCount = Math.max(...data.by_type.map(t => t.count), 1)

  return (
    <div className="space-y-6">
      {/* Main Clauses Card */}
      <div className="card">
        <div className="card-header flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <DocumentTextIcon className="h-6 w-6 text-primary-600" />
              Contract Clauses ({data.total} total)
            </h3>
            <p className="text-sm text-gray-500 mt-1">
              Click on any clause type to see details
            </p>
          </div>
          {/* Summary badges */}
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium bg-green-100 text-green-700">
              <CheckCircleIcon className="h-4 w-4" />
              <span>Classified</span>
              <span className="font-bold">{data.classified}</span>
            </div>
            {data.high_risk_total > 0 && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium bg-red-100 text-red-700">
                <ShieldExclamationIcon className="h-4 w-4" />
                <span>High Risk</span>
                <span className="font-bold">{data.high_risk_total}</span>
              </div>
            )}
          </div>
        </div>
        <div className="card-body">
          {classifiedClauses.length > 0 ? (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {classifiedClauses.map((item) => {
                const colors = CLAUSE_TYPE_COLORS[item.clause_type] || CLAUSE_TYPE_COLORS.other
                const hasHighRisk = item.high_risk_count > 0
                const isSelected = selectedType === item.clause_type

                return (
                  <button
                    key={item.clause_type}
                    onClick={() => setSelectedType(isSelected ? null : item.clause_type)}
                    className={cn(
                      "p-3 rounded-lg border-2 transition-all text-left hover:shadow-md",
                      isSelected
                        ? `${colors.bg} border-current ${colors.text} shadow-md`
                        : `${colors.bg} border-transparent hover:border-gray-200`
                    )}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className={cn("text-sm font-medium truncate", colors.text)}>
                        {CLAUSE_TYPE_LABELS[item.clause_type] || item.clause_type}
                      </span>
                      <div className="flex items-center gap-1">
                        <span className={cn("text-xl font-bold ml-2", colors.text)}>
                          {item.count}
                        </span>
                        <ChevronRightIcon className={cn(
                          "h-4 w-4 transition-transform",
                          isSelected ? `${colors.text} rotate-90` : "text-gray-400"
                        )} />
                      </div>
                    </div>

                    {/* Progress bar */}
                    <div className="h-1.5 bg-white/50 rounded-full overflow-hidden mb-1">
                      <div
                        className={cn("h-full rounded-full transition-all", colors.bar)}
                        style={{ width: `${(item.count / maxCount) * 100}%` }}
                      />
                    </div>

                    {/* High risk indicator */}
                    {hasHighRisk && (
                      <div className="flex items-center gap-1 mt-1">
                        <ExclamationTriangleIcon className="h-3.5 w-3.5 text-red-500" />
                        <span className="text-xs text-red-600 font-medium">
                          {item.high_risk_count} high risk
                        </span>
                      </div>
                    )}
                  </button>
                )
              })}

              {/* Other/Unclassified tile */}
              {otherClauses && otherClauses.count > 0 && (
                <button
                  onClick={() => setSelectedType(selectedType === 'other' ? null : 'other')}
                  className={cn(
                    "p-3 rounded-lg border-2 transition-all text-left hover:shadow-md",
                    selectedType === 'other'
                      ? "bg-gray-100 border-gray-400 text-gray-700 shadow-md"
                      : "bg-gray-50 border-transparent hover:border-gray-200"
                  )}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-gray-600">
                      Unclassified
                    </span>
                    <div className="flex items-center gap-1">
                      <span className="text-xl font-bold ml-2 text-gray-600">
                        {otherClauses.count}
                      </span>
                      <ChevronRightIcon className={cn(
                        "h-4 w-4 transition-transform",
                        selectedType === 'other' ? "text-gray-600 rotate-90" : "text-gray-400"
                      )} />
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="h-1.5 bg-white/50 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gray-400"
                      style={{ width: `${(otherClauses.count / maxCount) * 100}%` }}
                    />
                  </div>
                </button>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-500 text-center py-4">
              No classified clauses found. Click "Analyze" on a contract to extract clauses.
            </p>
          )}
        </div>
      </div>

      {/* Drill-down Panel */}
      {selectedType && (
        <div className="card border-2 border-primary-200">
          <div className="card-header bg-primary-50 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <DocumentMagnifyingGlassIcon className="h-5 w-5 text-primary-600" />
                {CLAUSE_TYPE_LABELS[selectedType] || selectedType} Clauses
                {drillDownData && (
                  <span className="text-sm font-normal text-gray-500">
                    ({drillDownData.total} items)
                  </span>
                )}
              </h3>
            </div>
            <button
              onClick={() => setSelectedType(null)}
              className="p-1 rounded hover:bg-gray-200"
            >
              <XMarkIcon className="h-5 w-5 text-gray-500" />
            </button>
          </div>

          <div className="card-body p-0">
            {drillDownLoading ? (
              <div className="flex items-center justify-center h-32">
                <LoadingSpinner size="md" />
              </div>
            ) : drillDownData ? (
              <div className="divide-y divide-gray-200 max-h-96 overflow-y-auto">
                {drillDownData.clauses.map((clause) => (
                  <Link
                    key={clause.id}
                    to={`/clauses/${clause.id}`}
                    className="block p-4 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-gray-900 mb-2 line-clamp-2">
                          {clause.text}
                        </p>
                        <div className="flex items-center flex-wrap gap-3 text-xs text-gray-500">
                          <span className="flex items-center gap-1">
                            <BuildingOfficeIcon className="h-3.5 w-3.5" />
                            {clause.contract_filename}
                          </span>
                          {clause.counterparty && (
                            <span className="text-gray-600">{clause.counterparty}</span>
                          )}
                          {clause.page_number && (
                            <span className="bg-gray-100 px-1.5 py-0.5 rounded">Page {clause.page_number}</span>
                          )}
                          {clause.section_number && (
                            <span className="bg-gray-100 px-1.5 py-0.5 rounded">Section {clause.section_number}</span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {clause.risk_level && (
                          <span className={cn(
                            "text-xs px-2 py-0.5 rounded-full capitalize",
                            RISK_COLORS[clause.risk_level] || 'bg-gray-100 text-gray-800'
                          )}>
                            {clause.risk_level} risk
                          </span>
                        )}
                        <ChevronRightIcon className="h-4 w-4 text-gray-400" />
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}
