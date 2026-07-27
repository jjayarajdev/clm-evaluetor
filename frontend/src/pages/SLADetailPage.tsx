import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  BoltIcon,
  DocumentTextIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import { getSLADetail } from '@/lib/api/compliance'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-100 text-red-800',
  high: 'bg-amber-100 text-amber-800',
  medium: 'bg-yellow-100 text-yellow-800',
  low: 'bg-gray-100 text-gray-700',
}

export default function SLADetailPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const canRecord = ['super_admin', 'admin', 'legal', 'procurement', 'bu_head'].includes(user?.role || '')

  const [showModal, setShowModal] = useState(false)
  const [actualValue, setActualValue] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)

  const { data: sla, isLoading } = useQuery({
    queryKey: ['sla-detail', id],
    queryFn: () => getSLADetail(id!),
    enabled: !!id,
  })

  const recordMutation = useMutation({
    mutationFn: ({ actual, note }: { actual: number; note?: string }) =>
      api.logSLAPerformance(sla!.contract_id, id!, { actual_value: actual, notes: note }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sla-detail', id] })
      setShowModal(false); setActualValue(''); setNotes(''); setError(null)
    },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : t('sla.recordFailed', { defaultValue: 'Could not record the measurement.' })),
  })

  const submit = () => {
    const val = Number(actualValue)
    if (actualValue.trim() === '' || Number.isNaN(val)) {
      setError(t('sla.recordInvalid', { defaultValue: 'Enter a numeric value.' }))
      return
    }
    setError(null)
    recordMutation.mutate({ actual: val, note: notes.trim() || undefined })
  }

  if (isLoading) return <LoadingSpinner size="lg" />
  if (!sla) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">{t('sla.notFound', { defaultValue: 'SLA not found.' })}</p>
        <Link to="/post-signing?tab=slas" className="text-primary-600 hover:underline mt-2 inline-block">{t('common.back', { defaultValue: 'Back' })}</Link>
      </div>
    )
  }

  const rate = sla.current_compliance_rate ?? sla.compliance_rate ?? null
  const perfs = sla.recent_performances || []
  const targetStr = `${sla.target_operator || '≥'} ${sla.target_value}${sla.metric_unit === 'percentage' ? '%' : ''}`

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Link to="/post-signing?tab=slas" className="p-2 -ml-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg">
          <ArrowLeftIcon className="h-5 w-5" />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className="px-2 py-0.5 rounded text-xs font-medium bg-primary-50 text-primary-700 capitalize">
              {(sla.metric_type || '').replace(/_/g, ' ')}
            </span>
            <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', SEVERITY_COLORS[sla.severity] || SEVERITY_COLORS.low)}>
              {t(`risk.${sla.severity}`, { defaultValue: sla.severity })}
            </span>
            {sla.is_active !== false && (
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">{t('sla.active', { defaultValue: 'Active' })}</span>
            )}
            {sla.has_penalty && (
              <span className="px-2 py-0.5 rounded text-xs font-medium bg-red-50 text-red-700 inline-flex items-center gap-1">
                <BoltIcon className="h-3 w-3" />
                {t('sla.penalty', { defaultValue: 'Penalty' })}
              </span>
            )}
          </div>
          <h1 className="text-2xl font-bold text-gray-900">{sla.sla_name}</h1>
          <p className="mt-1 text-sm text-gray-500">
            {sla.counterparty || '—'} · <Link to={`/contracts/${sla.contract_id}?tab=slas`} className="text-primary-600 hover:underline">{sla.contract_filename || t('sla.contract', { defaultValue: 'Contract' })}</Link>
          </p>
        </div>
      </div>

      {/* Target + Performance */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card">
          <div className="card-header"><h2 className="text-sm font-medium text-gray-900">{t('sla.target', { defaultValue: 'Target' })}</h2></div>
          <div className="card-body text-sm space-y-2">
            <Row label={t('sla.metric', { defaultValue: 'Metric' })} value={(sla.metric_type || '').replace(/_/g, ' ')} />
            <Row label={t('sla.targetValue', { defaultValue: 'Target' })} value={targetStr} />
            {sla.warning_threshold != null && <Row label={t('sla.warning', { defaultValue: 'Warning' })} value={String(sla.warning_threshold)} />}
            {sla.measurement_period && <Row label={t('sla.period', { defaultValue: 'Period' })} value={sla.measurement_period} />}
            {sla.has_penalty && (
              <Row label={t('sla.penalty', { defaultValue: 'Penalty' })} value={[sla.penalty_value != null ? String(sla.penalty_value) : null, sla.max_penalty_cap != null ? `${t('sla.cap', { defaultValue: 'cap' })} ${sla.max_penalty_cap}` : null].filter(Boolean).join(' · ') || t('sla.yes', { defaultValue: 'Yes' })} />
            )}
          </div>
        </div>
        <div className="card">
          <div className="card-header"><h2 className="text-sm font-medium text-gray-900">{t('sla.performance', { defaultValue: 'Performance' })}</h2></div>
          <div className="card-body text-sm space-y-2">
            <Row label={t('sla.compliance', { defaultValue: 'Compliance' })} value={rate != null ? `${rate.toFixed(1)}%` : t('sla.noData', { defaultValue: '— (no data yet)' })} />
            <Row label={t('sla.breaches', { defaultValue: 'Breaches' })} value={String(sla.consecutive_breaches ?? 0)} />
            <Row label={t('sla.trend', { defaultValue: 'Trend' })} value={sla.compliance_trend ? t(`sla.trend_${sla.compliance_trend}`, { defaultValue: sla.compliance_trend }) : '—'} />
          </div>
        </div>
      </div>

      {/* Data source + measurements */}
      <div className="card">
        <div className="card-header flex items-center justify-between">
          <div>
            <h2 className="text-sm font-medium text-gray-900">{t('sla.measurements', { defaultValue: 'Measurements' })}</h2>
            <p className="text-xs text-gray-500">{t('sla.sourceManual', { defaultValue: 'Data source: manual entry' })}</p>
          </div>
          {canRecord && (
            <button onClick={() => { setActualValue(''); setNotes(''); setError(null); setShowModal(true) }} className="btn-primary text-sm">
              {t('sla.recordMeasurement', { defaultValue: 'Record measurement' })}
            </button>
          )}
        </div>
        <div className="card-body">
          {perfs.length === 0 ? (
            <div className="text-center py-6">
              <DocumentTextIcon className="h-8 w-8 text-gray-300 mx-auto mb-2" />
              <p className="text-sm text-gray-500">{t('sla.noMeasurements', { defaultValue: 'No measurements recorded yet.' })}</p>
              <p className="text-xs text-gray-400 mt-1">{t('sla.noMeasurementsHint', { defaultValue: 'Record one to start tracking compliance against the target.' })}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b border-gray-200">
                    <th className="py-2 pr-4">{t('sla.date', { defaultValue: 'Date' })}</th>
                    <th className="py-2 pr-4">{t('sla.actual', { defaultValue: 'Actual' })}</th>
                    <th className="py-2 pr-4">{t('sla.targetValue', { defaultValue: 'Target' })}</th>
                    <th className="py-2 pr-4">{t('sla.result', { defaultValue: 'Result' })}</th>
                    <th className="py-2 pr-4 text-right">{t('sla.deviation', { defaultValue: 'Deviation' })}</th>
                  </tr>
                </thead>
                <tbody>
                  {perfs.map((p) => (
                    <tr key={p.id} className="border-b border-gray-100">
                      <td className="py-2 pr-4 text-gray-600">{new Date(p.measured_at).toLocaleDateString()}</td>
                      <td className="py-2 pr-4 font-medium text-gray-900">{p.actual_value}</td>
                      <td className="py-2 pr-4 text-gray-600">{targetStr}</td>
                      <td className="py-2 pr-4">
                        {p.is_compliant ? (
                          <span className="inline-flex items-center gap-1 text-green-600"><CheckCircleIcon className="h-4 w-4" />{t('sla.met', { defaultValue: 'Met' })}</span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-red-600"><ExclamationTriangleIcon className="h-4 w-4" />{t('sla.breach', { defaultValue: 'Breach' })}</span>
                        )}
                      </td>
                      <td className={cn('py-2 pr-4 text-right', (p.deviation_percentage ?? 0) < 0 ? 'text-red-600' : 'text-gray-600')}>
                        {p.deviation_percentage != null ? `${p.deviation_percentage > 0 ? '+' : ''}${p.deviation_percentage.toFixed(1)}%` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Source from contract */}
      {sla.source_text && (
        <div className="card">
          <div className="card-header"><h2 className="text-sm font-medium text-gray-900">{t('sla.sourceFromContract', { defaultValue: 'Source from contract' })}</h2></div>
          <div className="card-body">
            <p className="text-sm text-gray-600 italic">"{sla.source_text}"</p>
          </div>
        </div>
      )}

      {/* Record measurement modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-1">{t('sla.recordMeasurementTitle', { defaultValue: 'Record SLA measurement' })}</h3>
            <p className="text-sm text-gray-500 mb-4">{sla.sla_name}</p>
            <div className="rounded-lg bg-gray-50 p-3 mb-4 text-sm flex items-center justify-between">
              <span className="text-gray-500">{t('sla.targetValue', { defaultValue: 'Target' })}</span>
              <span className="font-medium text-gray-900">{targetStr}</span>
            </div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('sla.actualValue', { defaultValue: 'Actual value' })}</label>
            <input type="number" value={actualValue} onChange={(e) => setActualValue(e.target.value)} className="input w-full mb-3" autoFocus />
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('sla.notes', { defaultValue: 'Notes' })}</label>
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} placeholder={t('sla.notesPlaceholder', { defaultValue: 'Optional — period, source…' })} className="input w-full" />
            {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
            <div className="flex justify-end gap-3 mt-5">
              <button onClick={() => setShowModal(false)} className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg">{t('common.cancel')}</button>
              <button onClick={submit} disabled={recordMutation.isPending || actualValue.trim() === ''} className="btn-primary disabled:opacity-50">
                {recordMutation.isPending ? t('common.saving') : t('sla.recordMeasurement', { defaultValue: 'Record measurement' })}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-gray-500">{label}</span>
      <span className="font-medium text-gray-900 capitalize">{value}</span>
    </div>
  )
}
