import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ChartBarIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  CurrencyDollarIcon,
  PencilIcon,
  TrashIcon,
  PlusIcon,
  XMarkIcon,
  BookOpenIcon,
  SparklesIcon,
  BuildingLibraryIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline'
import { useTranslation } from 'react-i18next'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'

interface SLASummaryProps {
  contractId: string
}

interface SLAWithPerformance {
  id: string
  contract_id: string
  sla_name: string
  sla_description: string | null
  metric_type: string
  metric_unit: string
  target_value: number
  target_operator: string
  warning_threshold: number | null
  severity: string
  has_penalty: boolean
  penalty_type: string | null
  penalty_value: number | null
  penalty_description: string | null
  max_penalty_cap: number | null
  measurement_period: string | null
  is_active: boolean
  current_compliance_rate: number | null
  consecutive_breaches: number
  source_text: string | null
  master_data_id: string | null
  source: 'ai_extracted' | 'from_library' | 'manual'
  master_data_name: string | null
  compliance_trend: string | null
  recent_performances: {
    id: string
    actual_value: number
    measured_at: string
    is_compliant: boolean
    deviation_percentage: number | null
  }[]
}

interface SLAFormData {
  sla_name: string
  sla_description: string
  metric_type: string
  metric_unit: string
  target_value: number
  target_operator: string
  warning_threshold: number | null
  severity: string
  has_penalty: boolean
  penalty_type: string
  penalty_value: number | null
  penalty_description: string
  max_penalty_cap: number | null
  measurement_period: string
  is_active: boolean
}

const METRIC_TYPE_LABELS: Record<string, string> = {
  uptime_percentage: 'Uptime',
  response_time: 'Response Time',
  resolution_time: 'Resolution Time',
  delivery_time: 'Delivery Time',
  throughput: 'Throughput',
  error_rate: 'Error Rate',
  availability: 'Availability',
  quality_score: 'Quality Score',
  custom: 'Custom',
}

const METRIC_TYPES = [
  { value: 'uptime_percentage', label: 'Uptime Percentage' },
  { value: 'response_time', label: 'Response Time' },
  { value: 'resolution_time', label: 'Resolution Time' },
  { value: 'delivery_time', label: 'Delivery Time' },
  { value: 'throughput', label: 'Throughput' },
  { value: 'error_rate', label: 'Error Rate' },
  { value: 'availability', label: 'Availability' },
  { value: 'quality_score', label: 'Quality Score' },
  { value: 'custom', label: 'Custom' },
]

const METRIC_UNITS = [
  { value: 'percentage', label: 'Percentage (%)' },
  { value: 'hours', label: 'Hours' },
  { value: 'minutes', label: 'Minutes' },
  { value: 'days', label: 'Days' },
  { value: 'business_days', label: 'Business Days' },
  { value: 'count', label: 'Count' },
  { value: 'score', label: 'Score' },
]

const SEVERITY_LEVELS = [
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
]

const OPERATORS = [
  { value: '>=', key: 'atLeast', label: '>= (at least)' },
  { value: '<=', key: 'atMost', label: '<= (at most)' },
  { value: '>', key: 'greaterThan', label: '> (greater than)' },
  { value: '<', key: 'lessThan', label: '< (less than)' },
  { value: '=', key: 'exactly', label: '= (exactly)' },
]

const UNIT_LABELS: Record<string, string> = {
  percentage: '%',
  hours: 'hrs',
  minutes: 'min',
  days: 'days',
  business_days: 'biz days',
  count: '',
  score: 'pts',
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-100 text-red-800 border-red-200',
  high: 'bg-orange-100 text-orange-800 border-orange-200',
  medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  low: 'bg-blue-100 text-blue-800 border-blue-200',
}

function getSeverityColor(severity: string): string {
  return SEVERITY_COLORS[severity] || SEVERITY_COLORS.medium
}

function getComplianceColor(rate: number | null): string {
  if (rate === null) return 'text-gray-400'
  if (rate >= 95) return 'text-green-600'
  if (rate >= 80) return 'text-yellow-600'
  return 'text-red-600'
}

function getTrendIcon(trend: string | null) {
  if (trend === 'improving') return <span className="text-green-500">↑</span>
  if (trend === 'declining') return <span className="text-red-500">↓</span>
  return <span className="text-gray-400">→</span>
}

function SLAEditModal({
  sla,
  contractId,
  onClose,
  onSave,
}: {
  sla: SLAWithPerformance | null
  contractId: string
  onClose: () => void
  onSave: () => void
}) {
  const { t } = useTranslation()
  const isNew = !sla
  const [formData, setFormData] = useState<SLAFormData>({
    sla_name: sla?.sla_name || '',
    sla_description: sla?.sla_description || '',
    metric_type: sla?.metric_type || 'custom',
    metric_unit: sla?.metric_unit || 'percentage',
    target_value: sla?.target_value || 0,
    target_operator: sla?.target_operator || '>=',
    warning_threshold: sla?.warning_threshold || null,
    severity: sla?.severity || 'medium',
    has_penalty: sla?.has_penalty || false,
    penalty_type: sla?.penalty_type || '',
    penalty_value: sla?.penalty_value || null,
    penalty_description: sla?.penalty_description || '',
    max_penalty_cap: sla?.max_penalty_cap || null,
    measurement_period: sla?.measurement_period || '',
    is_active: sla?.is_active ?? true,
  })

  const queryClient = useQueryClient()

  const updateMutation = useMutation({
    mutationFn: (data: SLAFormData) => {
      if (isNew) {
        return api.createSLA(contractId, {
          ...data,
          target_value: Number(data.target_value),
          warning_threshold: data.warning_threshold ? Number(data.warning_threshold) : undefined,
          penalty_value: data.penalty_value ? Number(data.penalty_value) : undefined,
          max_penalty_cap: data.max_penalty_cap ? Number(data.max_penalty_cap) : undefined,
        })
      }
      return api.updateSLA(contractId, sla!.id, {
        ...data,
        target_value: Number(data.target_value),
        warning_threshold: data.warning_threshold ? Number(data.warning_threshold) : undefined,
        penalty_value: data.penalty_value ? Number(data.penalty_value) : undefined,
        max_penalty_cap: data.max_penalty_cap ? Number(data.max_penalty_cap) : undefined,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract-slas', contractId] })
      queryClient.invalidateQueries({ queryKey: ['contract', contractId] })
      onSave()
      onClose()
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    updateMutation.mutate(formData)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h3 className="text-lg font-medium text-gray-900">
            {isNew ? t('summaries.addNewSla') : t('summaries.editSla')}
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700">{t('summaries.slaName')} *</label>
            <input
              type="text"
              required
              value={formData.sla_name}
              onChange={(e) => setFormData({ ...formData, sla_name: e.target.value })}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700">{t('summaries.description')}</label>
            <textarea
              rows={2}
              value={formData.sla_description}
              onChange={(e) => setFormData({ ...formData, sla_description: e.target.value })}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            />
          </div>

          {/* Metric Type & Unit */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">{t('summaries.metricType')} *</label>
              <select
                required
                value={formData.metric_type}
                onChange={(e) => setFormData({ ...formData, metric_type: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              >
                {METRIC_TYPES.map((mt) => (
                  <option key={mt.value} value={mt.value}>{t(`summaries.metricTypes.${mt.value}`, { defaultValue: mt.label })}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">{t('summaries.unit')} *</label>
              <select
                required
                value={formData.metric_unit}
                onChange={(e) => setFormData({ ...formData, metric_unit: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              >
                {METRIC_UNITS.map((u) => (
                  <option key={u.value} value={u.value}>{t(`summaries.metricUnits.${u.value}`, { defaultValue: u.label })}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Target Value & Operator */}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">{t('summaries.operator')} *</label>
              <select
                required
                value={formData.target_operator}
                onChange={(e) => setFormData({ ...formData, target_operator: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              >
                {OPERATORS.map((o) => (
                  <option key={o.value} value={o.value}>{t(`summaries.operators.${o.key}`, { defaultValue: o.label })}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">{t('summaries.targetValue')} *</label>
              <input
                type="number"
                step="0.01"
                required
                value={formData.target_value}
                onChange={(e) => setFormData({ ...formData, target_value: parseFloat(e.target.value) })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">{t('summaries.warningThreshold')}</label>
              <input
                type="number"
                step="0.01"
                value={formData.warning_threshold ?? ''}
                onChange={(e) => setFormData({ ...formData, warning_threshold: e.target.value ? parseFloat(e.target.value) : null })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              />
            </div>
          </div>

          {/* Severity & Measurement Period */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">{t('summaries.severity')} *</label>
              <select
                required
                value={formData.severity}
                onChange={(e) => setFormData({ ...formData, severity: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              >
                {SEVERITY_LEVELS.map((s) => (
                  <option key={s.value} value={s.value}>{t(`risk.${s.value}`, { defaultValue: s.label })}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">{t('summaries.measurementPeriod')}</label>
              <input
                type="text"
                placeholder={t('summaries.measurementPeriodPlaceholder')}
                value={formData.measurement_period}
                onChange={(e) => setFormData({ ...formData, measurement_period: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              />
            </div>
          </div>

          {/* Penalty Section */}
          <div className="border-t pt-4 mt-4">
            <div className="flex items-center gap-2 mb-3">
              <input
                type="checkbox"
                id="has_penalty"
                checked={formData.has_penalty}
                onChange={(e) => setFormData({ ...formData, has_penalty: e.target.checked })}
                className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <label htmlFor="has_penalty" className="text-sm font-medium text-gray-700">
                {t('summaries.hasPenalty')}
              </label>
            </div>

            {formData.has_penalty && (
              <div className="space-y-4 pl-6">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">{t('summaries.penaltyType')}</label>
                    <select
                      value={formData.penalty_type}
                      onChange={(e) => setFormData({ ...formData, penalty_type: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    >
                      <option value="">{t('summaries.select')}</option>
                      <option value="fixed">{t('summaries.penaltyFixed')}</option>
                      <option value="percentage">{t('summaries.penaltyPercentage')}</option>
                      <option value="credit">{t('summaries.penaltyCredit')}</option>
                      <option value="tiered">{t('summaries.penaltyTiered')}</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">{t('summaries.penaltyValue')}</label>
                    <input
                      type="number"
                      step="0.01"
                      value={formData.penalty_value ?? ''}
                      onChange={(e) => setFormData({ ...formData, penalty_value: e.target.value ? parseFloat(e.target.value) : null })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">{t('summaries.maxPenaltyCap')}</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.max_penalty_cap ?? ''}
                    onChange={(e) => setFormData({ ...formData, max_penalty_cap: e.target.value ? parseFloat(e.target.value) : null })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">{t('summaries.penaltyDescription')}</label>
                  <textarea
                    rows={2}
                    value={formData.penalty_description}
                    onChange={(e) => setFormData({ ...formData, penalty_description: e.target.value })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Active Status */}
          {!isNew && (
            <div className="flex items-center gap-2 pt-2">
              <input
                type="checkbox"
                id="is_active"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <label htmlFor="is_active" className="text-sm font-medium text-gray-700">
                {t('status.active')}
              </label>
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4 border-t">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              {t('common.cancel')}
            </button>
            <button
              type="submit"
              disabled={updateMutation.isPending}
              className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 disabled:opacity-50"
            >
              {updateMutation.isPending ? t('summaries.saving') : (isNew ? t('summaries.createSla') : t('summaries.saveChanges'))}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function SLASummary({ contractId }: SLASummaryProps) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [editingSLA, setEditingSLA] = useState<SLAWithPerformance | null>(null)
  const [showEditModal, setShowEditModal] = useState(false)
  const [showAddModal, setShowAddModal] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [showLibraryPicker, setShowLibraryPicker] = useState(false)
  const [librarySearch, setLibrarySearch] = useState('')

  const canEdit = user?.role === 'admin' || user?.role === 'legal'

  const { data: slas, isLoading, error } = useQuery({
    queryKey: ['contract-slas', contractId],
    queryFn: () => api.getContractSLAs(contractId),
    enabled: !!contractId,
  })

  const { data: libraryItems, isLoading: libraryLoading } = useQuery({
    queryKey: ['sla-library-available', contractId],
    queryFn: () => api.getAvailableLibrarySLAs(contractId),
    enabled: showLibraryPicker,
  })

  const addFromLibraryMutation = useMutation({
    mutationFn: (masterDataId: string) => api.createSLAFromLibrary(contractId, masterDataId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract-slas', contractId] })
      queryClient.invalidateQueries({ queryKey: ['sla-library-available', contractId] })
      queryClient.invalidateQueries({ queryKey: ['contract', contractId] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (slaId: string) => api.deleteSLA(contractId, slaId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract-slas', contractId] })
      queryClient.invalidateQueries({ queryKey: ['contract', contractId] })
      setDeletingId(null)
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <LoadingSpinner size="md" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-8 text-gray-500">
        {t('summaries.slaLoadError')}
      </div>
    )
  }

  if (!slas || slas.length === 0) {
    return (
      <div className="card">
        <div className="card-body text-center py-8">
          <ChartBarIcon className="h-12 w-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500">{t('summaries.noSlas')}</p>
          <p className="text-sm text-gray-400 mt-1">
            {t('summaries.noSlasHint')}
          </p>
          {canEdit && (
            <button
              onClick={() => setShowAddModal(true)}
              className="mt-4 inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700"
            >
              <PlusIcon className="h-4 w-4 mr-2" />
              {t('summaries.addSlaManually')}
            </button>
          )}
        </div>
        {showAddModal && (
          <SLAEditModal
            sla={null}
            contractId={contractId}
            onClose={() => setShowAddModal(false)}
            onSave={() => {}}
          />
        )}
      </div>
    )
  }

  // Calculate summary stats - cast to SLAWithPerformance for full type access
  const slasTyped = slas as SLAWithPerformance[]
  const totalSLAs = slasTyped.length
  const activeSLAs = slasTyped.filter((s) => s.is_active).length
  const withPenalties = slasTyped.filter((s) => s.has_penalty).length
  const breached = slasTyped.filter((s) => s.consecutive_breaches > 0).length

  // Group by severity
  const bySeverity = slasTyped.reduce((acc: Record<string, SLAWithPerformance[]>, sla) => {
    const sev = sla.severity || 'medium'
    if (!acc[sev]) acc[sev] = []
    acc[sev].push(sla)
    return acc
  }, {} as Record<string, SLAWithPerformance[]>)

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card">
          <div className="card-body text-center">
            <ChartBarIcon className="h-8 w-8 text-primary-500 mx-auto mb-2" />
            <p className="text-2xl font-bold text-gray-900">{totalSLAs}</p>
            <p className="text-sm text-gray-500">{t('summaries.totalSlas')}</p>
          </div>
        </div>
        <div className="card">
          <div className="card-body text-center">
            <CheckCircleIcon className="h-8 w-8 text-green-500 mx-auto mb-2" />
            <p className="text-2xl font-bold text-gray-900">{activeSLAs}</p>
            <p className="text-sm text-gray-500">{t('status.active')}</p>
          </div>
        </div>
        <div className="card">
          <div className="card-body text-center">
            <ExclamationTriangleIcon className="h-8 w-8 text-red-500 mx-auto mb-2" />
            <p className="text-2xl font-bold text-gray-900">{breached}</p>
            <p className="text-sm text-gray-500">{t('status.breached')}</p>
          </div>
        </div>
        <div className="card">
          <div className="card-body text-center">
            <CurrencyDollarIcon className="h-8 w-8 text-yellow-500 mx-auto mb-2" />
            <p className="text-2xl font-bold text-gray-900">{withPenalties}</p>
            <p className="text-sm text-gray-500">{t('summaries.withPenalties')}</p>
          </div>
        </div>
      </div>

      {/* Add SLA buttons for admins */}
      {canEdit && (
        <div className="flex justify-end gap-2">
          <button
            onClick={() => setShowLibraryPicker(true)}
            className="inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
          >
            <BookOpenIcon className="h-4 w-4 mr-2" />
            {t('summaries.addFromLibrary')}
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700"
          >
            <PlusIcon className="h-4 w-4 mr-2" />
            {t('summaries.addSla')}
          </button>
        </div>
      )}

      {/* SLA List by Severity */}
      {['critical', 'high', 'medium', 'low'].map((severity) => {
        const items = bySeverity[severity]
        if (!items || items.length === 0) return null

        return (
          <div key={severity} className="card">
            <div className="card-header flex items-center gap-2">
              <span className={cn(
                'px-2 py-0.5 rounded text-xs font-medium capitalize border',
                getSeverityColor(severity)
              )}>
                {t(`risk.${severity}`, { defaultValue: severity })}
              </span>
              <span className="text-sm text-gray-500">
                {t('summaries.slaCount', { count: items.length })}
              </span>
            </div>
            <div className="divide-y divide-gray-100">
              {items.map((sla: SLAWithPerformance) => (
                <div key={sla.id} className="p-4 hover:bg-gray-50">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium text-gray-900">{sla.sla_name}</h4>
                        {sla.source === 'ai_extracted' && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium bg-primary-100 text-primary-700">
                            <SparklesIcon className="h-3 w-3" /> {t('summaries.aiExtracted')}
                          </span>
                        )}
                        {sla.source === 'from_library' && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-100 text-blue-700">
                            <BuildingLibraryIcon className="h-3 w-3" /> {t('summaries.library')}
                          </span>
                        )}
                        {!sla.is_active && (
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                            {t('status.inactive')}
                          </span>
                        )}
                        {sla.consecutive_breaches > 0 && (
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">
                            {t('summaries.breachCount', { count: sla.consecutive_breaches })}
                          </span>
                        )}
                        {sla.compliance_trend && getTrendIcon(sla.compliance_trend)}
                      </div>
                      {sla.sla_description && (
                        <p className="text-sm text-gray-500 mt-1">{sla.sla_description}</p>
                      )}
                      <div className="flex items-center gap-4 mt-2 text-sm">
                        <span className="text-gray-500">
                          <span className="font-medium text-gray-700">
                            {t(`summaries.metricTypes.${sla.metric_type}`, { defaultValue: METRIC_TYPE_LABELS[sla.metric_type] || sla.metric_type })}
                          </span>
                        </span>
                        <span className="text-gray-500">
                          {t('summaries.target')}: {sla.target_operator} {sla.target_value}
                          {t(`summaries.unitAbbr.${sla.metric_unit}`, { defaultValue: UNIT_LABELS[sla.metric_unit] || '' })}
                        </span>
                        {sla.warning_threshold && (
                          <span className="text-yellow-600">
                            {t('summaries.warning')}: {sla.warning_threshold}{t(`summaries.unitAbbr.${sla.metric_unit}`, { defaultValue: UNIT_LABELS[sla.metric_unit] || '' })}
                          </span>
                        )}
                        {sla.measurement_period && (
                          <span className="text-gray-400 flex items-center gap-1">
                            <ClockIcon className="h-3.5 w-3.5" />
                            {sla.measurement_period}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-start gap-4">
                      <div className="text-right">
                        {sla.current_compliance_rate !== null ? (
                          <div>
                            <p className={cn('text-xl font-bold', getComplianceColor(sla.current_compliance_rate))}>
                              {sla.current_compliance_rate.toFixed(1)}%
                            </p>
                            <p className="text-xs text-gray-400">{t('summaries.compliance')}</p>
                          </div>
                        ) : (
                          <p className="text-sm text-gray-400">{t('summaries.noDataYet')}</p>
                        )}
                      </div>
                      {canEdit && (
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => {
                              setEditingSLA(sla)
                              setShowEditModal(true)
                            }}
                            className="p-1.5 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded"
                            title={t('summaries.editSla')}
                          >
                            <PencilIcon className="h-4 w-4" />
                          </button>
                          {deletingId === sla.id ? (
                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => deleteMutation.mutate(sla.id)}
                                disabled={deleteMutation.isPending}
                                className="px-2 py-1 text-xs text-white bg-red-600 rounded hover:bg-red-700"
                              >
                                {deleteMutation.isPending ? '...' : t('common.yes')}
                              </button>
                              <button
                                onClick={() => setDeletingId(null)}
                                className="px-2 py-1 text-xs text-gray-600 bg-gray-100 rounded hover:bg-gray-200"
                              >
                                {t('common.no')}
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => setDeletingId(sla.id)}
                              className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                              title={t('summaries.deleteSla')}
                            >
                              <TrashIcon className="h-4 w-4" />
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Penalty info */}
                  {sla.has_penalty && (
                    <div className="mt-3 p-2 bg-yellow-50 rounded-lg border border-yellow-100">
                      <div className="flex items-center gap-2 text-sm">
                        <CurrencyDollarIcon className="h-4 w-4 text-yellow-600" />
                        <span className="font-medium text-yellow-800">{t('summaries.penalty')}:</span>
                        <span className="text-yellow-700">
                          {sla.penalty_type === 'percentage' && sla.penalty_value && `${sla.penalty_value}%`}
                          {sla.penalty_type === 'fixed' && sla.penalty_value && `$${sla.penalty_value.toLocaleString()}`}
                          {sla.penalty_type === 'credit' && t('summaries.penaltyCredit')}
                          {sla.penalty_type === 'tiered' && t('summaries.penaltyTiered')}
                          {sla.penalty_description && ` - ${sla.penalty_description.slice(0, 100)}...`}
                        </span>
                        {sla.max_penalty_cap && (
                          <span className="text-yellow-600 text-xs">
                            ({t('summaries.max')}: ${sla.max_penalty_cap.toLocaleString()})
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Source text */}
                  {sla.source_text && (
                    <details className="mt-3">
                      <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600">
                        {t('summaries.viewSourceText')}
                      </summary>
                      <blockquote className="mt-2 text-sm text-gray-600 bg-gray-50 p-3 rounded border-l-2 border-gray-300 italic">
                        "{sla.source_text.slice(0, 500)}{sla.source_text.length > 500 ? '...' : ''}"
                      </blockquote>
                    </details>
                  )}
                </div>
              ))}
            </div>
          </div>
        )
      })}

      {/* Edit Modal */}
      {showEditModal && (
        <SLAEditModal
          sla={editingSLA}
          contractId={contractId}
          onClose={() => {
            setShowEditModal(false)
            setEditingSLA(null)
          }}
          onSave={() => {}}
        />
      )}

      {/* Add Modal */}
      {showAddModal && (
        <SLAEditModal
          sla={null}
          contractId={contractId}
          onClose={() => setShowAddModal(false)}
          onSave={() => {}}
        />
      )}

      {/* Library Picker Modal */}
      {showLibraryPicker && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4" onClick={() => { setShowLibraryPicker(false); setLibrarySearch('') }}>
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[75vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="px-5 py-4 border-b flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">{t('summaries.addSlaFromLibrary')}</h3>
                <p className="text-sm text-gray-500 mt-0.5">{t('summaries.addSlaFromLibraryHint')}</p>
              </div>
              <button onClick={() => { setShowLibraryPicker(false); setLibrarySearch('') }} className="p-1 rounded hover:bg-gray-100">
                <XMarkIcon className="h-5 w-5 text-gray-400" />
              </button>
            </div>
            <div className="px-5 py-3 border-b">
              <div className="relative">
                <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder={t('summaries.librarySearchPlaceholder')}
                  value={librarySearch}
                  onChange={(e) => setLibrarySearch(e.target.value)}
                  className="input w-full pl-9"
                  autoFocus
                />
              </div>
            </div>
            <div className="flex-1 overflow-y-auto">
              {libraryLoading ? (
                <div className="flex items-center justify-center py-12"><LoadingSpinner size="md" /></div>
              ) : !libraryItems || libraryItems.length === 0 ? (
                <div className="text-center py-12 text-gray-400">
                  <BookOpenIcon className="h-10 w-10 mx-auto mb-2 text-gray-300" />
                  <p>{t('summaries.noLibrarySlas')}</p>
                  <p className="text-xs mt-1">{t('summaries.noLibrarySlasHint')}</p>
                </div>
              ) : (() => {
                const filtered = libraryItems.filter((item) =>
                  !librarySearch || item.name.toLowerCase().includes(librarySearch.toLowerCase())
                  || item.reference_code?.toLowerCase().includes(librarySearch.toLowerCase())
                  || item.description?.toLowerCase().includes(librarySearch.toLowerCase())
                )
                const grouped = filtered.reduce<Record<string, typeof filtered>>((acc, item) => {
                  const cat = item.category || t('summaries.uncategorized')
                  if (!acc[cat]) acc[cat] = []
                  acc[cat].push(item)
                  return acc
                }, {})

                if (filtered.length === 0) {
                  return <div className="text-center py-8 text-gray-400 text-sm">{t('summaries.noMatchesFor', { query: librarySearch })}</div>
                }

                return (
                  <div className="divide-y">
                    {Object.entries(grouped).map(([category, items]) => (
                      <div key={category}>
                        <div className="px-5 py-2 bg-gray-50 text-xs font-semibold text-gray-500 uppercase tracking-wider sticky top-0">
                          {category}
                          {items[0]?.service_tower && <span className="ml-2 font-normal normal-case text-gray-400">/ {items[0].service_tower}</span>}
                        </div>
                        {items.map((item) => (
                          <div key={item.id} className="px-5 py-3 flex items-center justify-between hover:bg-gray-50">
                            <div className="flex-1 min-w-0 mr-4">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-mono text-gray-400">{item.reference_code}</span>
                                <p className="text-sm font-medium text-gray-900">{item.name}</p>
                              </div>
                              {item.description && <p className="text-xs text-gray-500 mt-0.5 truncate">{item.description}</p>}
                              <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
                                {item.target_value != null && <span>{t('summaries.target')}: {item.target_value}</span>}
                                {item.minimum_value != null && <span>{t('summaries.min')}: {item.minimum_value}</span>}
                              </div>
                            </div>
                            <button
                              onClick={() => addFromLibraryMutation.mutate(item.id)}
                              disabled={addFromLibraryMutation.isPending}
                              className="shrink-0 inline-flex items-center px-3 py-1.5 text-xs font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 disabled:opacity-50"
                            >
                              <PlusIcon className="h-3 w-3 mr-1" /> {t('summaries.add')}
                            </button>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )
              })()}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
