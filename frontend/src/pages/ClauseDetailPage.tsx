import { useTranslation } from 'react-i18next'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  DocumentTextIcon,
  BuildingOfficeIcon,
  HashtagIcon,
  ShieldExclamationIcon,
  ExclamationTriangleIcon,
  DocumentMagnifyingGlassIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'

const CLAUSE_TYPE_COLORS: Record<string, string> = {
  confidentiality: 'bg-purple-100 text-purple-800 border-purple-200',
  indemnification: 'bg-red-100 text-red-800 border-red-200',
  limitation_of_liability: 'bg-orange-100 text-orange-800 border-orange-200',
  termination: 'bg-amber-100 text-amber-800 border-amber-200',
  warranty: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  force_majeure: 'bg-cyan-100 text-cyan-800 border-cyan-200',
  governing_law: 'bg-blue-100 text-blue-800 border-blue-200',
  dispute_resolution: 'bg-indigo-100 text-indigo-800 border-indigo-200',
  payment_terms: 'bg-green-100 text-green-800 border-green-200',
  intellectual_property: 'bg-pink-100 text-pink-800 border-pink-200',
  data_protection: 'bg-teal-100 text-teal-800 border-teal-200',
  non_compete: 'bg-rose-100 text-rose-800 border-rose-200',
  other: 'bg-gray-100 text-gray-800 border-gray-200',
}

const CLAUSE_TYPE_LABELS: Record<string, string> = {
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
  other: 'Other',
}

const RISK_COLORS: Record<string, string> = {
  low: 'bg-green-100 text-green-800',
  medium: 'bg-amber-100 text-amber-800',
  high: 'bg-red-100 text-red-800',
  critical: 'bg-purple-100 text-purple-800',
}

export default function ClauseDetailPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()

  const clauseTypeLabel = (type: string) =>
    t(`clauses.${type}`, {
      defaultValue: t(`clause.type.${type}`, {
        defaultValue: CLAUSE_TYPE_LABELS[type] || type,
      }),
    })

  const { data: clause, isLoading, error } = useQuery({
    queryKey: ['clause', id],
    queryFn: () => api.getClauseDetail(id!),
    enabled: !!id,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !clause) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">{t('clause.notFound')}</p>
        <Link to="/dashboard" className="text-primary-600 hover:underline mt-2 inline-block">
          {t('clause.backToDashboard')}
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
              CLAUSE_TYPE_COLORS[clause.clause_type] || CLAUSE_TYPE_COLORS.other
            )}>
              {clauseTypeLabel(clause.clause_type)}
            </span>
            {clause.risk_level && (
              <span className={cn(
                'px-2 py-0.5 rounded text-xs font-medium flex items-center gap-1',
                RISK_COLORS[clause.risk_level] || RISK_COLORS.low
              )}>
                <ShieldExclamationIcon className="h-3.5 w-3.5" />
                {t('contract.riskLabel', {
                  level: t(`risk.${clause.risk_level}`, { defaultValue: clause.risk_level }),
                })}
              </span>
            )}
          </div>
          <h1 className="text-lg font-bold text-gray-900">
            {t('clause.clauseFrom', { filename: clause.contract_filename })}
          </h1>
          <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
            {clause.page_number && (
              <span className="flex items-center gap-1">
                <DocumentTextIcon className="h-4 w-4" />
                {t('clause.page', { number: clause.page_number })}
              </span>
            )}
            {clause.section_number && (
              <span className="flex items-center gap-1">
                <HashtagIcon className="h-4 w-4" />
                {t('clause.section', { number: clause.section_number })}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Full Clause Text */}
          <div className="card">
            <div className="card-header">
              <h2 className="text-sm font-medium text-gray-900 flex items-center gap-2">
                <DocumentMagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
                {t('clause.fullClauseText')}
              </h2>
            </div>
            <div className="card-body">
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-5">
                <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
                  {clause.text}
                </p>
              </div>
            </div>
          </div>

          {/* Risk Analysis */}
          {clause.risk_reason && (
            <div className="card">
              <div className="card-header">
                <h2 className="text-sm font-medium text-gray-900 flex items-center gap-2">
                  <ExclamationTriangleIcon className="h-5 w-5 text-gray-400" />
                  {t('clause.riskAnalysis')}
                </h2>
              </div>
              <div className="card-body">
                <div className={cn(
                  'rounded-lg p-4',
                  clause.risk_level === 'high' ? 'bg-red-50 border border-red-200' :
                  clause.risk_level === 'medium' ? 'bg-amber-50 border border-amber-200' :
                  'bg-gray-50 border border-gray-200'
                )}>
                  <p className="text-sm text-gray-700">
                    {clause.risk_reason}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Related Clauses */}
          {clause.related_clauses && clause.related_clauses.length > 0 && (
            <div className="card">
              <div className="card-header">
                <h2 className="text-sm font-medium text-gray-900">
                  {t('clause.otherClauses', { count: clause.related_clauses.length })}
                </h2>
              </div>
              <div className="card-body p-0">
                <div className="divide-y divide-gray-200">
                  {clause.related_clauses.map((related) => (
                    <Link
                      key={related.id}
                      to={`/clauses/${related.id}`}
                      className="block p-4 hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className={cn(
                              'px-2 py-0.5 rounded text-xs font-medium border',
                              CLAUSE_TYPE_COLORS[related.clause_type] || CLAUSE_TYPE_COLORS.other
                            )}>
                              {clauseTypeLabel(related.clause_type)}
                            </span>
                            {related.page_number && (
                              <span className="text-xs text-gray-400">
                                {t('clause.page', { number: related.page_number })}
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-gray-600 line-clamp-2">
                            {related.text}
                          </p>
                        </div>
                        {related.risk_level && (
                          <span className={cn(
                            'text-xs px-2 py-0.5 rounded shrink-0',
                            RISK_COLORS[related.risk_level] || RISK_COLORS.low
                          )}>
                            {t(`risk.${related.risk_level}`, { defaultValue: related.risk_level })}
                          </span>
                        )}
                      </div>
                    </Link>
                  ))}
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
                {t('clause.sourceContract')}
              </h2>
            </div>
            <div className="card-body space-y-4">
              <div>
                <p className="text-xs text-gray-500 mb-1">{t('clause.document')}</p>
                <p className="text-sm font-medium text-gray-900 break-all">
                  {clause.contract_filename}
                </p>
              </div>
              {clause.counterparty && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">{t('contracts.counterparty')}</p>
                  <p className="text-sm font-medium text-gray-900">
                    {clause.counterparty}
                  </p>
                </div>
              )}
              {clause.contract_type && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">{t('clause.contractType')}</p>
                  <p className="text-sm font-medium text-gray-900 uppercase">
                    {clause.contract_type}
                  </p>
                </div>
              )}
              <div className="pt-4 border-t border-gray-200">
                <Link
                  to={`/contracts/${clause.contract_id}`}
                  className="btn-primary w-full justify-center"
                >
                  {t('clause.viewFullContract')}
                </Link>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="card">
            <div className="card-header">
              <h2 className="text-sm font-medium text-gray-900">{t('common.actions')}</h2>
            </div>
            <div className="card-body space-y-2">
              <Link
                to={`/query?clause=${clause.id}&contract=${clause.contract_id}`}
                className="btn-secondary w-full justify-center"
              >
                {t('clause.askAi')}
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
