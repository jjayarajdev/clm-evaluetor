import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  DocumentTextIcon,
  CalendarIcon,
  UserGroupIcon,
  ExclamationTriangleIcon,
  ClipboardDocumentListIcon,
  BuildingOfficeIcon,
  HashtagIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn, formatDate } from '@/lib/utils'

const OBLIGATION_TYPE_COLORS: Record<string, string> = {
  payment: 'bg-green-100 text-green-800 border-green-200',
  delivery: 'bg-blue-100 text-blue-800 border-blue-200',
  reporting: 'bg-purple-100 text-purple-800 border-purple-200',
  compliance: 'bg-amber-100 text-amber-800 border-amber-200',
  notification: 'bg-cyan-100 text-cyan-800 border-cyan-200',
  performance: 'bg-indigo-100 text-indigo-800 border-indigo-200',
  other: 'bg-gray-100 text-gray-800 border-gray-200',
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  in_progress: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  overdue: 'bg-red-100 text-red-800',
  waived: 'bg-gray-100 text-gray-800',
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

const RISK_COLORS: Record<string, string> = {
  low: 'bg-green-100 text-green-800',
  medium: 'bg-amber-100 text-amber-800',
  high: 'bg-red-100 text-red-800',
  critical: 'bg-purple-100 text-purple-800',
}

export default function ObligationDetailPage() {
  const { id } = useParams<{ id: string }>()

  const { data: obligation, isLoading, error } = useQuery({
    queryKey: ['obligation', id],
    queryFn: () => api.getObligationDetail(id!),
    enabled: !!id,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !obligation) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">Obligation not found</p>
        <Link to="/dashboard" className="text-primary-600 hover:underline mt-2 inline-block">
          Back to dashboard
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Link
          to="/dashboard"
          className="p-2 -ml-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
        >
          <ArrowLeftIcon className="h-5 w-5" />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <span className={cn(
              'px-3 py-1 rounded-full text-sm font-medium border',
              OBLIGATION_TYPE_COLORS[obligation.obligation_type] || OBLIGATION_TYPE_COLORS.other
            )}>
              {OBLIGATION_TYPE_LABELS[obligation.obligation_type] || obligation.obligation_type}
            </span>
            <span className={cn(
              'px-2 py-0.5 rounded text-xs font-medium',
              STATUS_COLORS[obligation.status] || STATUS_COLORS.pending
            )}>
              {obligation.status}
            </span>
          </div>
          <h1 className="text-xl font-bold text-gray-900 leading-relaxed">
            {obligation.description}
          </h1>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Parties */}
          <div className="card">
            <div className="card-header">
              <h2 className="text-sm font-medium text-gray-900 flex items-center gap-2">
                <UserGroupIcon className="h-5 w-5 text-gray-400" />
                Parties Involved
              </h2>
            </div>
            <div className="card-body grid grid-cols-2 gap-6">
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Obligated Party</p>
                <p className="text-lg font-semibold text-gray-900">
                  {obligation.obligated_party || '—'}
                </p>
                <p className="text-sm text-gray-500">Responsible for fulfilling this obligation</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Beneficiary</p>
                <p className="text-lg font-semibold text-gray-900">
                  {obligation.beneficiary_party || '—'}
                </p>
                <p className="text-sm text-gray-500">Benefits from this obligation</p>
              </div>
            </div>
          </div>

          {/* Deadline Info */}
          <div className="card">
            <div className="card-header">
              <h2 className="text-sm font-medium text-gray-900 flex items-center gap-2">
                <CalendarIcon className="h-5 w-5 text-gray-400" />
                Deadline Information
              </h2>
            </div>
            <div className="card-body">
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <p className="text-xs text-gray-500 mb-1">Deadline</p>
                  <p className="text-base font-medium text-gray-900">
                    {obligation.deadline ? formatDate(obligation.deadline) : 'No fixed deadline'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Deadline Type</p>
                  <p className="text-base font-medium text-gray-900 capitalize">
                    {obligation.deadline_type?.replace('_', ' ') || 'Not specified'}
                  </p>
                </div>
                {obligation.recurrence_pattern && (
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Recurrence</p>
                    <p className="text-base font-medium text-gray-900">
                      {obligation.recurrence_pattern}
                    </p>
                  </div>
                )}
                {obligation.relative_deadline_text && (
                  <div className="col-span-2">
                    <p className="text-xs text-gray-500 mb-1">Relative Deadline</p>
                    <p className="text-base font-medium text-gray-900">
                      {obligation.relative_deadline_text}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Trigger & Consequences */}
          {(obligation.trigger_condition || obligation.consequence_of_breach) && (
            <div className="card">
              <div className="card-header">
                <h2 className="text-sm font-medium text-gray-900 flex items-center gap-2">
                  <ExclamationTriangleIcon className="h-5 w-5 text-gray-400" />
                  Triggers & Consequences
                </h2>
              </div>
              <div className="card-body space-y-4">
                {obligation.trigger_condition && (
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
                      Trigger Condition
                    </p>
                    <p className="text-sm text-gray-700 bg-gray-50 p-3 rounded-lg">
                      {obligation.trigger_condition}
                    </p>
                  </div>
                )}
                {obligation.consequence_of_breach && (
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
                      Consequence of Breach
                    </p>
                    <p className="text-sm text-red-700 bg-red-50 p-3 rounded-lg">
                      {obligation.consequence_of_breach}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Source Text from Contract */}
          {(obligation.source_text || obligation.clause_text) && (
            <div className="card">
              <div className="card-header flex items-center justify-between">
                <h2 className="text-sm font-medium text-gray-900 flex items-center gap-2">
                  <ClipboardDocumentListIcon className="h-5 w-5 text-gray-400" />
                  Source from Contract
                </h2>
                <div className="flex items-center gap-2">
                  {obligation.clause_type && (
                    <span className="text-xs text-gray-500 capitalize">
                      {obligation.clause_type.replace('_', ' ')}
                    </span>
                  )}
                  {obligation.clause_risk_level && (
                    <span className={cn(
                      'px-2 py-0.5 rounded text-xs font-medium',
                      RISK_COLORS[obligation.clause_risk_level] || RISK_COLORS.low
                    )}>
                      {obligation.clause_risk_level} risk
                    </span>
                  )}
                </div>
              </div>
              <div className="card-body">
                <div className="flex items-center gap-4 mb-3 text-xs text-gray-500">
                  {obligation.clause_page_number && (
                    <span className="flex items-center gap-1">
                      <DocumentTextIcon className="h-4 w-4" />
                      Page {obligation.clause_page_number}
                    </span>
                  )}
                  {obligation.clause_section_number && (
                    <span className="flex items-center gap-1">
                      <HashtagIcon className="h-4 w-4" />
                      Section {obligation.clause_section_number}
                    </span>
                  )}
                </div>
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                  <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed italic">
                    "{obligation.source_text || obligation.clause_text}"
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Contract Info */}
          <div className="card">
            <div className="card-header">
              <h2 className="text-sm font-medium text-gray-900 flex items-center gap-2">
                <BuildingOfficeIcon className="h-5 w-5 text-gray-400" />
                Source Contract
              </h2>
            </div>
            <div className="card-body space-y-4">
              <div>
                <p className="text-xs text-gray-500 mb-1">Document</p>
                <p className="text-sm font-medium text-gray-900 break-all">
                  {obligation.contract_filename}
                </p>
              </div>
              {obligation.counterparty && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">Counterparty</p>
                  <p className="text-sm font-medium text-gray-900">
                    {obligation.counterparty}
                  </p>
                </div>
              )}
              {obligation.contract_type && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">Contract Type</p>
                  <p className="text-sm font-medium text-gray-900 uppercase">
                    {obligation.contract_type}
                  </p>
                </div>
              )}
              <div className="pt-4 border-t border-gray-200">
                <Link
                  to={`/contracts/${obligation.contract_id}`}
                  className="btn-primary w-full justify-center"
                >
                  View Full Contract
                </Link>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="card">
            <div className="card-header">
              <h2 className="text-sm font-medium text-gray-900">Actions</h2>
            </div>
            <div className="card-body space-y-2">
              <Link
                to={`/query?obligation=${obligation.id}`}
                className="btn-secondary w-full justify-center"
              >
                Ask AI about this obligation
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
