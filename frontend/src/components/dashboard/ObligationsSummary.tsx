import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  ClipboardDocumentListIcon,
  ChevronRightIcon,
  XMarkIcon,
  CalendarIcon,
  BuildingOfficeIcon,
  UserIcon,
  UsersIcon,
  BriefcaseIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn, formatDate } from '@/lib/utils'
import type { ObligationsByTypeResponse } from '@/types'

const OBLIGATION_TYPE_COLORS: Record<string, { bg: string; bar: string; text: string }> = {
  payment: { bg: 'bg-green-50', bar: 'bg-green-500', text: 'text-green-700' },
  delivery: { bg: 'bg-blue-50', bar: 'bg-blue-500', text: 'text-blue-700' },
  reporting: { bg: 'bg-purple-50', bar: 'bg-purple-500', text: 'text-purple-700' },
  compliance: { bg: 'bg-amber-50', bar: 'bg-amber-500', text: 'text-amber-700' },
  notification: { bg: 'bg-cyan-50', bar: 'bg-cyan-500', text: 'text-cyan-700' },
  performance: { bg: 'bg-indigo-50', bar: 'bg-indigo-500', text: 'text-indigo-700' },
  other: { bg: 'bg-gray-50', bar: 'bg-gray-400', text: 'text-gray-600' },
}

const OBLIGATION_TYPE_LABELS: Record<string, string> = {
  payment: 'Payment',
  delivery: 'Delivery',
  reporting: 'Reporting',
  compliance: 'Compliance',
  notification: 'Notification',
  performance: 'Performance',
  other: 'Other',
}

const PARTY_ICONS: Record<string, React.ElementType> = {
  client: UserIcon,
  provider: BriefcaseIcon,
  mutual: UsersIcon,
}

const PARTY_COLORS: Record<string, string> = {
  client: 'text-amber-600 bg-amber-100',
  provider: 'text-blue-600 bg-blue-100',
  mutual: 'text-purple-600 bg-purple-100',
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  in_progress: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  overdue: 'bg-red-100 text-red-800',
}

interface Props {
  contractId?: string | null
}

export default function ObligationsSummary({ contractId }: Props) {
  const [selectedType, setSelectedType] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['obligations-summary', contractId],
    queryFn: () => api.getObligationsSummary(contractId || undefined),
  })

  const { data: drillDownData, isLoading: drillDownLoading } = useQuery({
    queryKey: ['obligations-by-type', selectedType],
    queryFn: () => api.getObligationsByType(selectedType!),
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

  const maxCount = Math.max(...data.by_type.map(t => t.count), 1)

  // Get party summary counts
  const partySummary = data.by_party

  return (
    <div className="space-y-6">
      {/* Main Obligations Card */}
      <div className="card">
        <div className="card-header flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <ClipboardDocumentListIcon className="h-6 w-6 text-primary-600" />
              Contract Obligations ({data.total} total)
            </h3>
            <p className="text-sm text-gray-500 mt-1">Click on any obligation type to see details</p>
          </div>
          {/* Party Summary Badges */}
          <div className="flex items-center gap-2">
            {Object.entries(partySummary).map(([party, count]) => {
              const partyKey = party.toLowerCase()
              const Icon = PARTY_ICONS[partyKey] || UserIcon
              const colorClass = PARTY_COLORS[partyKey] || 'text-gray-600 bg-gray-100'

              return (
                <div
                  key={party}
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium",
                    colorClass
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <span>{party}</span>
                  <span className="font-bold">{count}</span>
                </div>
              )
            })}
          </div>
        </div>
        <div className="card-body">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {data.by_type.map((item) => {
              const colors = OBLIGATION_TYPE_COLORS[item.obligation_type] || OBLIGATION_TYPE_COLORS.other
              const isSelected = selectedType === item.obligation_type

              return (
                <button
                  key={item.obligation_type}
                  onClick={() => setSelectedType(isSelected ? null : item.obligation_type)}
                  className={cn(
                    "p-3 rounded-lg border-2 transition-all text-left hover:shadow-md",
                    isSelected
                      ? `${colors.bg} border-current ${colors.text} shadow-md`
                      : `${colors.bg} border-transparent hover:border-gray-200`
                  )}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className={cn("text-sm font-medium", colors.text)}>
                      {OBLIGATION_TYPE_LABELS[item.obligation_type] || item.obligation_type}
                    </span>
                    <div className="flex items-center gap-1">
                      <span className={cn("text-xl font-bold", colors.text)}>
                        {item.count}
                      </span>
                      <ChevronRightIcon className={cn(
                        "h-4 w-4 transition-transform",
                        isSelected ? `${colors.text} rotate-90` : "text-gray-400"
                      )} />
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="h-1.5 bg-white/50 rounded-full overflow-hidden mb-2">
                    <div
                      className={cn("h-full rounded-full transition-all", colors.bar)}
                      style={{ width: `${(item.count / maxCount) * 100}%` }}
                    />
                  </div>

                  {/* Party breakdown - compact badges */}
                  <div className="flex flex-wrap gap-1">
                    {Object.entries(item.by_party).map(([party, count]) => {
                      const partyKey = party.toLowerCase()
                      const colorClass = PARTY_COLORS[partyKey] || 'text-gray-600 bg-gray-100'

                      return (
                        <span
                          key={party}
                          className={cn(
                            "text-xs px-1.5 py-0.5 rounded-full font-medium",
                            colorClass
                          )}
                        >
                          {party}: {count}
                        </span>
                      )
                    })}
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* Drill-down Panel */}
      {selectedType && (
        <div className="card border-2 border-primary-200">
          <div className="card-header bg-primary-50 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                {OBLIGATION_TYPE_LABELS[selectedType] || selectedType} Obligations
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
                {drillDownData.obligations.map((obl) => (
                  <Link
                    key={obl.id}
                    to={`/obligations/${obl.id}`}
                    className="block p-4 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 mb-1">
                          {obl.description}
                        </p>
                        <div className="flex items-center gap-4 text-xs text-gray-500">
                          <span className="flex items-center gap-1">
                            <BuildingOfficeIcon className="h-3.5 w-3.5" />
                            {obl.contract_filename}
                          </span>
                          {obl.counterparty && (
                            <span>{obl.counterparty}</span>
                          )}
                          {obl.deadline && (
                            <span className="flex items-center gap-1">
                              <CalendarIcon className="h-3.5 w-3.5" />
                              {formatDate(obl.deadline)}
                            </span>
                          )}
                        </div>
                        {obl.source_clause_text && (
                          <p className="text-xs text-gray-400 mt-2 line-clamp-2 italic">
                            "{obl.source_clause_text}"
                          </p>
                        )}
                      </div>
                      <div className="flex flex-col items-end gap-1 shrink-0">
                        <span className={cn(
                          "text-xs px-2 py-0.5 rounded-full",
                          STATUS_COLORS[obl.status] || STATUS_COLORS.pending
                        )}>
                          {obl.status}
                        </span>
                        <span className="text-xs text-gray-500">
                          {obl.obligated_party}
                        </span>
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
