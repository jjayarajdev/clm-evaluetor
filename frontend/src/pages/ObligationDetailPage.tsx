import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  DocumentTextIcon,
  CalendarIcon,
  UserGroupIcon,
  ExclamationTriangleIcon,
  ClipboardDocumentListIcon,
  BuildingOfficeIcon,
  HashtagIcon,
  DocumentArrowUpIcon,
  CheckCircleIcon,
  ShieldCheckIcon,
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

// RAG Status visual indicators with polished styling
const RAG_STATUS_CONFIG: Record<string, {
  bg: string
  text: string
  icon: string
  label: string
  description: string
}> = {
  green: {
    bg: 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-300',
    text: 'text-green-700',
    icon: '🟢',
    label: 'On Track',
    description: 'Compliance fully met',
  },
  amber: {
    bg: 'bg-gradient-to-r from-amber-50 to-yellow-50 border-amber-300',
    text: 'text-amber-700',
    icon: '🟡',
    label: 'At Risk',
    description: 'Needs attention soon',
  },
  red: {
    bg: 'bg-gradient-to-r from-red-50 to-rose-50 border-red-300',
    text: 'text-red-700',
    icon: '🔴',
    label: 'Overdue',
    description: 'Immediate action required',
  },
  not_assessed: {
    bg: 'bg-gradient-to-r from-gray-50 to-slate-50 border-gray-300',
    text: 'text-gray-600',
    icon: '⚪',
    label: 'Not Assessed',
    description: 'Status pending review',
  },
}

export default function ObligationDetailPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const [showEvidenceModal, setShowEvidenceModal] = useState(false)
  const [evidenceDescription, setEvidenceDescription] = useState('')
  const [evidenceDate, setEvidenceDate] = useState('')
  const [evidenceFile, setEvidenceFile] = useState<File | null>(null)

  const { data: obligation, isLoading, error } = useQuery({
    queryKey: ['obligation', id],
    queryFn: () => api.getObligationDetail(id!),
    enabled: !!id,
  })

  const uploadEvidenceMutation = useMutation({
    mutationFn: (data: { evidence_description: string; evidence_date?: string; file?: File }) =>
      api.uploadObligationEvidence(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['obligation', id] })
      setShowEvidenceModal(false)
      setEvidenceDescription('')
      setEvidenceDate('')
      setEvidenceFile(null)
    },
  })

  const handleEvidenceSubmit = () => {
    if (!evidenceDescription.trim()) return
    uploadEvidenceMutation.mutate({
      evidence_description: evidenceDescription,
      evidence_date: evidenceDate || undefined,
      file: evidenceFile || undefined,
    })
  }

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
        <p className="text-red-600">{t('obligation.notFound')}</p>
        <Link to="/dashboard" className="text-primary-600 hover:underline mt-2 inline-block">
          {t('obligation.backToDashboard')}
        </Link>
      </div>
    )
  }

  const ragKey: string =
    obligation.rag_status && RAG_STATUS_CONFIG[obligation.rag_status]
      ? obligation.rag_status
      : 'not_assessed'

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
          <div className="flex items-center gap-3 mb-2 flex-wrap">
            <span className={cn(
              'px-3 py-1 rounded-full text-sm font-medium border',
              OBLIGATION_TYPE_COLORS[obligation.obligation_type] || OBLIGATION_TYPE_COLORS.other
            )}>
              {t(`obligation.type.${obligation.obligation_type}`, {
                defaultValue: OBLIGATION_TYPE_LABELS[obligation.obligation_type] || obligation.obligation_type,
              })}
            </span>
            <span className={cn(
              'px-2 py-0.5 rounded text-xs font-medium',
              STATUS_COLORS[obligation.status] || STATUS_COLORS.pending
            )}>
              {t(`obligation.status.${obligation.status}`, { defaultValue: obligation.status })}
            </span>
            {/* RAG Status Indicator */}
            {obligation.rag_status && (
              <span className={cn(
                'px-3 py-1 rounded-lg text-sm font-medium border-2 flex items-center gap-2 shadow-sm',
                RAG_STATUS_CONFIG[obligation.rag_status]?.bg || RAG_STATUS_CONFIG.not_assessed.bg,
                RAG_STATUS_CONFIG[obligation.rag_status]?.text || RAG_STATUS_CONFIG.not_assessed.text
              )}>
                <span className="text-base">{RAG_STATUS_CONFIG[obligation.rag_status]?.icon || '⚪'}</span>
                {t(`obligation.rag.${ragKey}.label`, { defaultValue: RAG_STATUS_CONFIG[ragKey].label })}
              </span>
            )}
            {obligation.is_critical && (
              <span className="px-2 py-0.5 rounded bg-purple-100 text-purple-800 text-xs font-bold uppercase tracking-wider">
                {t('risk.critical')}
              </span>
            )}
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
                {t('obligation.partiesInvolved')}
              </h2>
            </div>
            <div className="card-body grid grid-cols-2 gap-6">
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{t('obligation.obligatedParty')}</p>
                <p className="text-lg font-semibold text-gray-900">
                  {obligation.obligated_party || '—'}
                </p>
                <p className="text-sm text-gray-500">{t('obligation.obligatedPartyDesc')}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{t('obligation.beneficiary')}</p>
                <p className="text-lg font-semibold text-gray-900">
                  {obligation.beneficiary_party || '—'}
                </p>
                <p className="text-sm text-gray-500">{t('obligation.beneficiaryDesc')}</p>
              </div>
            </div>
          </div>

          {/* Deadline Info */}
          <div className="card">
            <div className="card-header">
              <h2 className="text-sm font-medium text-gray-900 flex items-center gap-2">
                <CalendarIcon className="h-5 w-5 text-gray-400" />
                {t('obligation.deadlineInformation')}
              </h2>
            </div>
            <div className="card-body">
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <p className="text-xs text-gray-500 mb-1">{t('obligation.deadline')}</p>
                  <p className="text-base font-medium text-gray-900">
                    {obligation.deadline ? formatDate(obligation.deadline) : t('obligation.noFixedDeadline')}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">{t('obligation.deadlineType')}</p>
                  <p className="text-base font-medium text-gray-900 capitalize">
                    {obligation.deadline_type?.replace('_', ' ') || t('obligation.notSpecified')}
                  </p>
                </div>
                {obligation.recurrence_pattern && (
                  <div>
                    <p className="text-xs text-gray-500 mb-1">{t('obligation.recurrence')}</p>
                    <p className="text-base font-medium text-gray-900">
                      {obligation.recurrence_pattern}
                    </p>
                  </div>
                )}
                {obligation.relative_deadline_text && (
                  <div className="col-span-2">
                    <p className="text-xs text-gray-500 mb-1">{t('obligation.relativeDeadline')}</p>
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
                  {t('obligation.triggersConsequences')}
                </h2>
              </div>
              <div className="card-body space-y-4">
                {obligation.trigger_condition && (
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
                      {t('obligation.triggerCondition')}
                    </p>
                    <p className="text-sm text-gray-700 bg-gray-50 p-3 rounded-lg">
                      {obligation.trigger_condition}
                    </p>
                  </div>
                )}
                {obligation.consequence_of_breach && (
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
                      {t('obligation.consequenceOfBreach')}
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
                  {t('obligation.sourceFromContract')}
                </h2>
                <div className="flex items-center gap-2">
                  {obligation.clause_type && (
                    <span className="text-xs text-gray-500 capitalize">
                      {t(`clauses.${obligation.clause_type}`, {
                        defaultValue: obligation.clause_type.replace('_', ' '),
                      })}
                    </span>
                  )}
                  {obligation.clause_risk_level && (
                    <span className={cn(
                      'px-2 py-0.5 rounded text-xs font-medium',
                      RISK_COLORS[obligation.clause_risk_level] || RISK_COLORS.low
                    )}>
                      {t('contract.riskLabel', {
                        level: t(`risk.${obligation.clause_risk_level}`, {
                          defaultValue: obligation.clause_risk_level,
                        }),
                      })}
                    </span>
                  )}
                </div>
              </div>
              <div className="card-body">
                <div className="flex items-center gap-4 mb-3 text-xs text-gray-500">
                  {obligation.clause_page_number && (
                    <span className="flex items-center gap-1">
                      <DocumentTextIcon className="h-4 w-4" />
                      {t('obligation.page', { number: obligation.clause_page_number })}
                    </span>
                  )}
                  {obligation.clause_section_number && (
                    <span className="flex items-center gap-1">
                      <HashtagIcon className="h-4 w-4" />
                      {t('obligation.section', { number: obligation.clause_section_number })}
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
                {t('obligation.sourceContract')}
              </h2>
            </div>
            <div className="card-body space-y-4">
              <div>
                <p className="text-xs text-gray-500 mb-1">{t('obligation.document')}</p>
                <p className="text-sm font-medium text-gray-900 break-all">
                  {obligation.contract_filename}
                </p>
              </div>
              {obligation.counterparty && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">{t('contracts.counterparty')}</p>
                  <p className="text-sm font-medium text-gray-900">
                    {obligation.counterparty}
                  </p>
                </div>
              )}
              {obligation.contract_type && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">{t('obligation.contractType')}</p>
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
                  {t('obligation.viewFullContract')}
                </Link>
              </div>
            </div>
          </div>

          {/* RAG Status Card */}
          {obligation.rag_status && (
            <div className={cn(
              'card border-2',
              RAG_STATUS_CONFIG[obligation.rag_status]?.bg || RAG_STATUS_CONFIG.not_assessed.bg
            )}>
              <div className="card-body">
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-2xl">{RAG_STATUS_CONFIG[obligation.rag_status]?.icon || '⚪'}</span>
                  <div>
                    <p className={cn(
                      'font-semibold',
                      RAG_STATUS_CONFIG[obligation.rag_status]?.text || RAG_STATUS_CONFIG.not_assessed.text
                    )}>
                      {t(`obligation.rag.${ragKey}.label`, { defaultValue: RAG_STATUS_CONFIG[ragKey].label })}
                    </p>
                    <p className="text-sm text-gray-600">
                      {t(`obligation.rag.${ragKey}.description`, { defaultValue: RAG_STATUS_CONFIG[ragKey].description })}
                    </p>
                  </div>
                </div>
                {obligation.last_compliance_date && (
                  <p className="text-xs text-gray-500">
                    {t('obligation.lastCompliance', { date: formatDate(obligation.last_compliance_date) })}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Compliance Evidence */}
          <div className="card">
            <div className="card-header flex items-center justify-between">
              <h2 className="text-sm font-medium text-gray-900 flex items-center gap-2">
                <ShieldCheckIcon className="h-5 w-5 text-gray-400" />
                {t('obligation.complianceEvidence')}
              </h2>
              <button
                onClick={() => setShowEvidenceModal(true)}
                className="text-sm text-primary-600 hover:text-primary-700 font-medium"
              >
                {t('obligation.addEvidence')}
              </button>
            </div>
            <div className="card-body">
              {obligation.compliance_evidence ? (
                <div className="space-y-2">
                  {obligation.compliance_evidence.split('\n').map((entry: string, idx: number) => (
                    <div key={idx} className="flex items-start gap-2 text-sm">
                      <CheckCircleIcon className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                      <span className="text-gray-700">{entry}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-4">
                  <DocumentArrowUpIcon className="h-8 w-8 text-gray-300 mx-auto mb-2" />
                  <p className="text-sm text-gray-500">{t('obligation.noEvidence')}</p>
                  <button
                    onClick={() => setShowEvidenceModal(true)}
                    className="btn-primary mt-3"
                  >
                    {t('obligation.uploadEvidence')}
                  </button>
                </div>
              )}
              {obligation.compliance_notes && (
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <p className="text-xs text-gray-500 mb-1">{t('obligation.complianceNotes')}</p>
                  <p className="text-sm text-gray-700 whitespace-pre-wrap">{obligation.compliance_notes}</p>
                </div>
              )}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="card">
            <div className="card-header">
              <h2 className="text-sm font-medium text-gray-900">{t('common.actions')}</h2>
            </div>
            <div className="card-body space-y-2">
              <Link
                to={`/query?obligation=${obligation.id}`}
                className="btn-secondary w-full justify-center"
              >
                {t('obligation.askAi')}
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Evidence Upload Modal */}
      {showEvidenceModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              {t('obligation.uploadComplianceEvidence')}
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('obligation.evidenceDescription')}
                </label>
                <textarea
                  value={evidenceDescription}
                  onChange={(e) => setEvidenceDescription(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  rows={3}
                  placeholder={t('obligation.evidencePlaceholder')}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('obligation.evidenceDate')}
                </label>
                <input
                  type="date"
                  value={evidenceDate}
                  onChange={(e) => setEvidenceDate(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('obligation.attachmentOptional')}
                </label>
                <input
                  type="file"
                  onChange={(e) => setEvidenceFile(e.target.files?.[0] || null)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm file:mr-4 file:py-1 file:px-3 file:rounded file:border-0 file:bg-primary-50 file:text-primary-700"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowEvidenceModal(false)}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={handleEvidenceSubmit}
                disabled={!evidenceDescription.trim() || uploadEvidenceMutation.isPending}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center gap-2"
              >
                {uploadEvidenceMutation.isPending ? (
                  <>
                    <LoadingSpinner size="sm" />
                    {t('obligation.uploading')}
                  </>
                ) : (
                  <>
                    <DocumentArrowUpIcon className="h-4 w-4" />
                    {t('obligation.uploadEvidence')}
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
