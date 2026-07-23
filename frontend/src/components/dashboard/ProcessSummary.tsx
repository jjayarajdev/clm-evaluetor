import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ClipboardDocumentCheckIcon,
  ChevronRightIcon,
  CheckCircleIcon,
  ClockIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
  CalendarDaysIcon,
} from '@heroicons/react/24/outline'
import { useTranslation } from 'react-i18next'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'

const STEP_STATUS_COLORS: Record<string, { bg: string; text: string; icon: React.ElementType }> = {
  pending: { bg: 'bg-gray-100', text: 'text-gray-600', icon: ClockIcon },
  in_progress: { bg: 'bg-blue-100', text: 'text-blue-600', icon: ArrowPathIcon },
  completed: { bg: 'bg-green-100', text: 'text-green-600', icon: CheckCircleIcon },
  blocked: { bg: 'bg-red-100', text: 'text-red-600', icon: ExclamationCircleIcon },
}

const STEP_TYPE_LABELS: Record<string, string> = {
  submission: 'Submission',
  review: 'Review',
  testing: 'Testing',
  approval: 'Approval',
  delivery: 'Delivery',
  certification: 'Certification',
  payment: 'Payment',
  reporting: 'Reporting',
  renewal: 'Renewal',
  other: 'Other',
}

interface ProcessStep {
  id: string
  step_number: number
  step_name: string
  step_type: string
  description: string | null
  responsible_party: string | null
  duration_days: number | null
  sla_days: number | null
  dependencies: string[]
  deliverables: string[]
  status: string
  source_text: string | null
}

interface ProcessResponse {
  contract_id: string
  steps: ProcessStep[]
  total_steps: number
  estimated_duration_days: number
  by_responsible_party: Record<string, number>
  sla_items: number
}

interface Props {
  contractId: string
}

export default function ProcessSummary({ contractId }: Props) {
  const { t } = useTranslation()
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery<ProcessResponse>({
    queryKey: ['process', contractId],
    queryFn: async () => {
      const response = await fetch(`/api/dashboard/process/${contractId}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })
      if (!response.ok) throw new Error('Failed to fetch process')
      return response.json()
    },
    enabled: !!contractId,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <LoadingSpinner size="md" />
      </div>
    )
  }

  if (error || !data || data.total_steps === 0) {
    return (
      <div className="card">
        <div className="card-body text-center py-8">
          <ClipboardDocumentCheckIcon className="h-12 w-12 text-gray-300 mx-auto mb-3" />
          <p className="text-sm text-gray-500">
            {t('summaries.noProcessSteps')}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card">
          <div className="card-body">
            <p className="text-sm text-gray-500">{t('summaries.totalSteps')}</p>
            <p className="text-2xl font-bold text-gray-900">{data.total_steps}</p>
          </div>
        </div>
        <div className="card">
          <div className="card-body">
            <p className="text-sm text-gray-500">{t('summaries.estDuration')}</p>
            <p className="text-2xl font-bold text-gray-900">
              {t('summaries.days', { count: data.estimated_duration_days })}
            </p>
          </div>
        </div>
        <div className="card">
          <div className="card-body">
            <p className="text-sm text-gray-500">{t('summaries.slaItems')}</p>
            <p className="text-2xl font-bold text-gray-900">{data.sla_items}</p>
          </div>
        </div>
        <div className="card">
          <div className="card-body">
            <p className="text-sm text-gray-500">{t('summaries.partiesInvolved')}</p>
            <p className="text-2xl font-bold text-gray-900">
              {Object.keys(data.by_responsible_party).length}
            </p>
          </div>
        </div>
      </div>

      {/* Process Flow */}
      <div className="card">
        <div className="card-header">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <ClipboardDocumentCheckIcon className="h-5 w-5 text-primary-600" />
            {t('summaries.processFlow')}
          </h3>
          <p className="text-sm text-gray-500 mt-1">
            {t('summaries.processFlowSubtitle')}
          </p>
        </div>
        <div className="card-body p-0">
          <div className="divide-y divide-gray-100">
            {data.steps.map((step, index) => {
              const isExpanded = expandedId === step.id
              const statusConfig = STEP_STATUS_COLORS[step.status] || STEP_STATUS_COLORS.pending
              const StatusIcon = statusConfig.icon

              return (
                <div key={step.id}>
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : step.id)}
                    className="w-full p-4 hover:bg-gray-50 text-left"
                  >
                    <div className="flex items-start gap-4">
                      {/* Step number with connector line */}
                      <div className="relative flex flex-col items-center">
                        <div className={cn(
                          "w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold",
                          statusConfig.bg, statusConfig.text
                        )}>
                          {step.step_number}
                        </div>
                        {index < data.steps.length - 1 && (
                          <div className="w-0.5 h-8 bg-gray-200 mt-1" />
                        )}
                      </div>

                      {/* Step content */}
                      <div className="flex-1 min-w-0 pt-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-gray-900">
                            {step.step_name}
                          </span>
                          <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                            {t(`summaries.stepTypes.${step.step_type}`, { defaultValue: STEP_TYPE_LABELS[step.step_type] || step.step_type })}
                          </span>
                          <StatusIcon className={cn("h-4 w-4 ml-auto", statusConfig.text)} />
                        </div>

                        {step.description && (
                          <p className={cn(
                            "text-sm text-gray-600 mb-2",
                            !isExpanded && "line-clamp-2"
                          )}>
                            {step.description}
                          </p>
                        )}

                        <div className="flex items-center gap-4 text-xs text-gray-500">
                          {step.responsible_party && (
                            <span>{t('summaries.byParty', { party: step.responsible_party })}</span>
                          )}
                          {step.duration_days && (
                            <span className="flex items-center gap-1">
                              <ClockIcon className="h-3.5 w-3.5" />
                              {t('summaries.days', { count: step.duration_days })}
                            </span>
                          )}
                          {step.sla_days && (
                            <span className="flex items-center gap-1 text-amber-600">
                              <CalendarDaysIcon className="h-3.5 w-3.5" />
                              SLA: {t('summaries.days', { count: step.sla_days })}
                            </span>
                          )}
                        </div>
                      </div>

                      <ChevronRightIcon className={cn(
                        "h-5 w-5 text-gray-400 transition-transform mt-1",
                        isExpanded && "rotate-90"
                      )} />
                    </div>
                  </button>

                  {isExpanded && (
                    <div className="px-4 pb-4 ml-12">
                      <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                        {step.dependencies.length > 0 && (
                          <div>
                            <p className="text-xs font-medium text-gray-500 mb-1">{t('summaries.dependencies')}</p>
                            <div className="flex flex-wrap gap-1">
                              {step.dependencies.map((dep, i) => (
                                <span key={i} className="text-xs px-2 py-0.5 bg-white border border-gray-200 rounded">
                                  {dep}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {step.deliverables.length > 0 && (
                          <div>
                            <p className="text-xs font-medium text-gray-500 mb-1">{t('summaries.deliverables')}</p>
                            <ul className="list-disc list-inside text-sm text-gray-700">
                              {step.deliverables.map((del, i) => (
                                <li key={i}>{del}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {step.source_text && (
                          <div className="pt-3 border-t border-gray-200">
                            <p className="text-xs font-medium text-gray-500 mb-1">{t('summaries.sourceText')}</p>
                            <p className="text-xs text-gray-600 italic">
                              "{step.source_text}"
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Responsibility Matrix */}
      {Object.keys(data.by_responsible_party).length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-gray-900">
              {t('summaries.responsibilityDistribution')}
            </h3>
          </div>
          <div className="card-body">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {Object.entries(data.by_responsible_party).map(([party, count]) => (
                <div
                  key={party}
                  className="p-3 bg-gray-50 rounded-lg text-center"
                >
                  <p className="text-2xl font-bold text-gray-900">{count}</p>
                  <p className="text-xs text-gray-500">{party}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
