import { useState, useMemo } from 'react'
import { useParams, Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  DocumentTextIcon,
  ShieldExclamationIcon,
  ArrowPathIcon,
  TrashIcon,
  ChartBarIcon,
  LinkIcon,
  InformationCircleIcon,
  ShareIcon,
  DocumentMagnifyingGlassIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  PencilIcon,
  CheckIcon,
  XMarkIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  MinusCircleIcon,
  Square3Stack3DIcon,
} from '@heroicons/react/24/outline'
import type { ExtractionStageOutcome } from '@/types'
import api from '@/lib/api'
import { client as apiClient } from '@/lib/api/client'
import { reExtractMetadataField, type ReExtractableField } from '@/lib/api/contracts'
import { getIndustryProfiles } from '@/lib/api/admin'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import SLASummary from '@/components/dashboard/SLASummary'
import CustomFieldsDisplay from '@/components/contracts/CustomFieldsDisplay'
import SuggestedLinksPanel from '@/components/contracts/SuggestedLinksPanel'
import ContractSharing from '@/components/contracts/ContractSharing'
import ContractDocumentsTab from '@/components/contracts/ContractDocumentsTab'
import ContractReviewPane from '@/components/contracts/ContractReviewPane'
import ContractPdfViewer from '@/components/contracts/ContractPdfViewer'
import type { HighlightRect } from '@/lib/api/contracts'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/contexts/AuthContext'
import { useTenantConfig } from '@/contexts/TenantConfigContext'
import { cn, formatDate, formatCurrency, formatFileSize, getRiskColor, getStatusColor } from '@/lib/utils'

// Map config icon names to Heroicon components
const TAB_ICON_MAP: Record<string, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
  document: InformationCircleIcon,
  eye: DocumentMagnifyingGlassIcon,
  chart: ChartBarIcon,
  link: LinkIcon,
  folder: DocumentTextIcon,
  share: ShareIcon,
  shield: ShieldExclamationIcon,
  truck: DocumentTextIcon,
  graph: Square3Stack3DIcon,
}

// Fallback tabs if config not loaded yet
const DEFAULT_TABS = [
  { id: 'overview', label: 'Overview', icon: 'document' },
  { id: 'review', label: 'Review', icon: 'eye' },
  { id: 'slas', label: 'SLAs', icon: 'chart' },
  { id: 'related', label: 'Related Docs', icon: 'link' },
  { id: 'documents', label: 'Documents', icon: 'folder' },
  { id: 'sharing', label: 'Sharing', icon: 'share' },
]

// Display order for extraction pipeline stages; labels resolved via i18n
// under contract.stages.<key> with the English default as fallback
const STAGE_DISPLAY: { key: string; label: string }[] = [
  { key: 'metadata', label: 'Metadata' },
  { key: 'risk', label: 'Risk Assessment' },
  { key: 'custom_fields', label: 'Custom Fields' },
  { key: 'contract_references', label: 'Contract References' },
  { key: 'clause_extraction', label: 'Clauses' },
  { key: 'obligation_detection', label: 'Obligations' },
  { key: 'sla_extraction', label: 'SLAs' },
  { key: 'highlight_extraction', label: 'PDF Highlights' },
  { key: 'taxonomy_discovery', label: 'Taxonomy Suggestions' },
  { key: 'renewal_analysis', label: 'Renewal Terms' },
  { key: 'schema_extraction', label: 'Structured Schema Fields' },
  { key: 'link_detection', label: 'Related Contract Detection' },
  { key: 'compliance_check', label: 'Compliance Check' },
  { key: 'regulatory_extraction', label: 'Regulatory Obligations' },
  { key: 'hierarchy_detection', label: 'Hierarchy Detection' },
  { key: 'governance_bridge', label: 'Governance Bridge' },
  { key: 'graph_verification', label: 'Graph Verification' },
]

function ExtractionHealthPanel({
  health,
}: {
  health: Record<string, ExtractionStageOutcome>
}) {
  const { t } = useTranslation()
  const stages = STAGE_DISPLAY.filter((s) => health[s.key])
  const counts = stages.reduce(
    (acc, s) => {
      const status = health[s.key]?.status
      if (status === 'success') acc.success += 1
      else if (status === 'failed') acc.failed += 1
      else if (status === 'skipped' || status === 'not_applicable') acc.skipped += 1
      return acc
    },
    { success: 0, failed: 0, skipped: 0 }
  )

  const headlineColor =
    counts.failed > 0 ? 'text-red-700' : counts.skipped > 0 ? 'text-amber-700' : 'text-green-700'

  return (
    <div className="card">
      <div className="card-header flex items-center justify-between">
        <h2 className="text-sm font-medium text-gray-900">{t('contract.extractionHealth')}</h2>
        <span className={cn('text-xs font-medium', headlineColor)}>
          {t('contract.healthCounts', { success: counts.success, failed: counts.failed, skipped: counts.skipped })}
        </span>
      </div>
      <div className="card-body space-y-1.5">
        {stages.map((s) => {
          const outcome = health[s.key]
          const status = outcome.status
          const Icon =
            status === 'success'
              ? CheckCircleIcon
              : status === 'failed'
                ? ExclamationTriangleIcon
                : MinusCircleIcon
          const iconColor =
            status === 'success'
              ? 'text-green-500'
              : status === 'failed'
                ? 'text-red-500'
                : 'text-gray-400'
          const note = outcome.error || outcome.reason
          const dropped = (outcome.details?.dropped_fields as Array<{
            field: string
            confidence: number
            threshold: number
          }> | undefined)
          return (
            <div key={s.key} className="flex items-start gap-2 text-xs">
              <Icon className={cn('h-4 w-4 mt-0.5 shrink-0', iconColor)} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-gray-900">{t(`contract.stages.${s.key}`, { defaultValue: s.label })}</span>
                  <span className="text-gray-400 capitalize">{t(`contract.stageStatus.${status}`, { defaultValue: status.replace('_', ' ') })}</span>
                </div>
                {note && (
                  <p className="text-gray-500 truncate" title={note}>
                    {note}
                  </p>
                )}
                {dropped && dropped.length > 0 && (
                  <p className="text-amber-600" title={dropped.map(d => `${d.field}: ${d.confidence} < ${d.threshold}`).join('\n')}>
                    {t('contract.fieldsBelowThreshold', { count: dropped.length })}
                    {' '}
                    {dropped.map(d => d.field).join(', ')}
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function ContractViewPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const { config, contractTypeLabel, uiLabel } = useTenantConfig()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  // Get active tab from URL or default to first tab
  const activeTab = searchParams.get('tab') || 'overview'
  const setActiveTab = (tab: string) => {
    setSearchParams({ tab })
  }

  // Determine if user can edit custom fields (admin, legal, or procurement roles)
  const canEditCustomFields = user?.role === 'admin' || user?.role === 'legal' || user?.role === 'procurement' || user?.role === 'super_admin'

  const { data: contract, isLoading, error } = useQuery({
    queryKey: ['contract', id],
    queryFn: () => api.getContract(id!),
    enabled: !!id,
  })

  const processMutation = useMutation({
    mutationFn: () => api.processContract(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract', id] })
    },
  })

  const analyzeMutation = useMutation({
    mutationFn: () => api.analyzeContract(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract', id] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteContract(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] })
      queryClient.invalidateQueries({ queryKey: ['contracts-summary'] })
      navigate('/contracts')
    },
  })

  const updateMetadataMutation = useMutation({
    mutationFn: (data: Record<string, any>) =>
      apiClient.patch(`/contracts/${id}`, data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract', id] })
      queryClient.invalidateQueries({ queryKey: ['contracts'] })
    },
  })

  // #30 — Per-field re-extract state. Keyed by field name so multiple
  // popovers can show their own pending/result state independently.
  const [reExtractPending, setReExtractPending] = useState<Record<string, boolean>>({})
  const [reExtractResult, setReExtractResult] = useState<
    Record<string, { applied: boolean; reason?: string | null } | null>
  >({})

  const handleReExtract = (field: ReExtractableField, hint: string | undefined) => {
    if (!id) return
    setReExtractPending((p) => ({ ...p, [field]: true }))
    setReExtractResult((r) => ({ ...r, [field]: null }))
    reExtractMetadataField(id, field, hint)
      .then((resp) => {
        setReExtractResult((r) => ({
          ...r,
          [field]: { applied: resp.applied, reason: resp.reason },
        }))
        if (resp.applied) {
          // Pull the fresh value + provenance into the contract data
          queryClient.invalidateQueries({ queryKey: ['contract', id] })
        }
      })
      .catch((err: any) => {
        setReExtractResult((r) => ({
          ...r,
          [field]: {
            applied: false,
            reason: err?.response?.data?.detail || err?.message || 'Re-extract failed',
          },
        }))
      })
      .finally(() => {
        setReExtractPending((p) => ({ ...p, [field]: false }))
      })
  }

  // Industry profiles for per-contract assignment
  const { data: industryProfiles = [] } = useQuery({
    queryKey: ['industry-profiles'],
    queryFn: getIndustryProfiles,
  })

  // Build tabs dynamically based on contract type
  const PROCUREMENT_TYPES = new Set([
    'procurement', 'procurement_agreement', 'hardware_procurement_contract',
    'supply_agreement', 'quality_agreement', 'blanket_po', 'manufacturing_supply',
    'annual_maintenance', 'rate_contract', 'distribution', 'vendor',
  ])
  const tabs = useMemo(() => {
    const mapped = (config?.ui?.detail_tabs || DEFAULT_TABS).map((t) => ({
      id: t.id,
      label: t.label,
      iconComponent: TAB_ICON_MAP[t.icon || ''] || InformationCircleIcon,
    }))
    const ct = contract?.contract_type?.toLowerCase() || ''
    const needsProcurementTabs = PROCUREMENT_TYPES.has(ct) ||
      ct.includes('procurement') || ct.includes('supply') || ct.includes('manufacturing')
    if (needsProcurementTabs) {
      const existingIds = new Set(mapped.map((t) => t.id))
      const insertIdx = mapped.findIndex((t) => t.id === 'review') + 1 || 2
      const extraTabs = [
        { id: 'quality', label: 'Quality', icon: 'shield' },
        { id: 'supply_chain', label: 'Supply Chain', icon: 'truck' },
      ]
      let offset = 0
      for (const pt of extraTabs) {
        if (!existingIds.has(pt.id)) {
          mapped.splice(insertIdx + offset, 0, {
            id: pt.id,
            label: pt.label,
            iconComponent: TAB_ICON_MAP[pt.icon] || InformationCircleIcon,
          })
          offset++
        }
      }
      // Also ensure SLAs tab is present
      if (!existingIds.has('slas')) {
        const relIdx = mapped.findIndex((t) => t.id === 'supply_chain')
        mapped.splice(relIdx + 1, 0, {
          id: 'slas',
          label: 'SLAs',
          iconComponent: ChartBarIcon,
        })
      }
    }
    return mapped
  }, [config, contract?.contract_type])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !contract) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">{t('contract.notFound')}</p>
        <Link to="/contracts" className="text-primary-600 hover:underline mt-2 inline-block">
          {t('contract.backToContracts')}
        </Link>
      </div>
    )
  }

  const isCompleted = contract.status === 'completed'

  return (
    <div className="h-full flex flex-col">
      {/* Compact Header */}
      <div className="flex-shrink-0 border-b border-gray-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4 min-w-0">
            <Link
              to="/contracts"
              className="p-2 -ml-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg flex-shrink-0"
            >
              <ArrowLeftIcon className="h-5 w-5" />
            </Link>
            <div className="min-w-0">
              <h1 className="text-xl font-bold text-gray-900 truncate">{contract.filename}</h1>
              <div className="flex items-center gap-3 mt-1">
                <span className={cn(
                  'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize',
                  getStatusColor(contract.status)
                )}>
                  {t(`status.${contract.status}`, { defaultValue: contract.status })}
                </span>
                {contract.risk_level && (
                  <span className={cn(
                    'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize',
                    getRiskColor(contract.risk_level)
                  )}>
                    {t('contract.riskLabel', { level: t(`risk.${contract.risk_level}`, { defaultValue: contract.risk_level }) })}
                  </span>
                )}
                {contract.contract_type && (
                  <span className="text-sm text-gray-500">
                    {contractTypeLabel(contract.contract_type)}
                  </span>
                )}
                {contract.counterparty && (
                  <span className="text-sm text-gray-500">
                    • {contract.counterparty}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            {contract.status === 'pending' && (
              <button
                onClick={() => processMutation.mutate()}
                disabled={processMutation.isPending}
                className="btn-secondary"
              >
                {processMutation.isPending ? (
                  <LoadingSpinner size="sm" className="mr-2" />
                ) : (
                  <ArrowPathIcon className="h-4 w-4 mr-2" />
                )}
                {t('contract.process')}
              </button>
            )}
            {isCompleted && (
              <button
                onClick={() => analyzeMutation.mutate()}
                disabled={analyzeMutation.isPending}
                className="btn-primary"
              >
                {analyzeMutation.isPending ? (
                  <LoadingSpinner size="sm" className="mr-2 border-white border-t-transparent" />
                ) : (
                  <ShieldExclamationIcon className="h-4 w-4 mr-2" />
                )}
                {t('contract.reanalyze')}
              </button>
            )}
            <Link
              to={`/query?contract=${contract.id}`}
              className="btn-secondary"
            >
              {t('dashboard.actions.askAi')}
            </Link>
            {!showDeleteConfirm ? (
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="btn-secondary text-red-600 hover:text-red-700 hover:bg-red-50"
              >
                <TrashIcon className="h-4 w-4" />
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  className="btn-secondary text-sm py-1"
                >
                  {t('common.cancel')}
                </button>
                <button
                  onClick={() => deleteMutation.mutate()}
                  disabled={deleteMutation.isPending}
                  className="btn-secondary text-sm py-1 bg-red-600 text-white hover:bg-red-700"
                >
                  {deleteMutation.isPending ? t('contracts.deleting') : t('common.delete')}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex-shrink-0 border-b border-gray-200 bg-white px-6">
        <nav className="flex gap-6" aria-label="Tabs">
          {tabs.map((tab) => {
            // Hide analysis tabs for non-completed contracts
            // overview and sharing are always visible
            if (!isCompleted && tab.id !== 'overview' && tab.id !== 'sharing') {
              return null
            }
            const Icon = tab.iconComponent
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex items-center gap-2 py-3 px-1 border-b-2 text-sm font-medium transition-colors',
                  activeTab === tab.id
                    ? 'border-primary-600 text-primary-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                )}
              >
                <Icon className="h-4 w-4" />
                {t(`contract.tabs.${tab.id}`, { defaultValue: tab.label })}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Review Tab - full-bleed, no padding */}
      {activeTab === 'review' && isCompleted && id && (
        <div className="flex-1 overflow-hidden">
          <ContractReviewPane contractId={id} contract={contract} />
        </div>
      )}

      {/* Quality Tab (Manufacturing) - full-bleed with PDF viewer */}
      {activeTab === 'quality' && isCompleted && id && (
        <div className="flex-1 overflow-hidden">
          <ClauseFilteredTab
            contractId={id}
            contract={contract}
            title={t('contract.qualityClausesTitle')}
            clauseTypes={['warranty', 'limitation_of_liability', 'governance', 'definitions', 'data_protection']}
            emptyMessage={t('contract.qualityClausesEmpty')}
          />
        </div>
      )}

      {/* Supply Chain Tab (Manufacturing) - full-bleed with PDF viewer */}
      {activeTab === 'supply_chain' && isCompleted && id && (
        <div className="flex-1 overflow-hidden">
          <ClauseFilteredTab
            contractId={id}
            contract={contract}
            title={t('contract.supplyChainClausesTitle')}
            clauseTypes={['scope', 'payment_terms', 'termination', 'confidentiality', 'intellectual_property']}
            emptyMessage={t('contract.supplyChainClausesEmpty')}
          />
        </div>
      )}

      {/* Tab Content (all tabs except review, quality, supply_chain) */}
      {activeTab !== 'review' && activeTab !== 'quality' && activeTab !== 'supply_chain' && (
      <div className="flex-1 overflow-auto p-6 bg-gray-50">
        {/* Processing error banner */}
        {contract.processing_error && (
          <div className="mb-6 p-4 rounded-lg border border-red-200 bg-red-50">
            <p className="text-sm font-medium text-red-800">{t('contract.processingError')}</p>
            <p className="text-sm text-red-700 mt-1">{contract.processing_error}</p>
          </div>
        )}

        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left column - Details */}
            <div className="lg:col-span-2 space-y-6">
              {/* Contract Details */}
              <div className="card">
                <div className="card-header">
                  <h2 className="text-sm font-medium text-gray-900">{t('contract.contractDetails')}</h2>
                </div>
                <div className="card-body grid grid-cols-2 md:grid-cols-3 gap-4">
                  <EditableField
                    label={uiLabel('counterparty', t('contracts.counterparty'))}
                    value={contract.counterparty}
                    fieldName="counterparty"
                    onSave={(field, val) => updateMetadataMutation.mutate({ [field]: val })}
                    canEdit={canEditCustomFields}
                    provenance={contract.metadata_provenance?.counterparty}
                    onReExtract={canEditCustomFields ? (h) => handleReExtract('counterparty', h) : undefined}
                    reExtracting={reExtractPending.counterparty}
                    reExtractResult={reExtractResult.counterparty}
                  />
                  <EditableField
                    label={uiLabel('contract_value', t('contract.contractValue'))}
                    value={contract.contract_value ? String(contract.contract_value) : null}
                    displayValue={contract.contract_value ? formatCurrency(contract.contract_value, contract.currency || 'USD') : null}
                    fieldName="contract_value"
                    type="number"
                    onSave={(field, val) => updateMetadataMutation.mutate({ [field]: Number(val) })}
                    canEdit={canEditCustomFields}
                    provenance={contract.metadata_provenance?.contract_value}
                    onReExtract={canEditCustomFields ? (h) => handleReExtract('contract_value', h) : undefined}
                    reExtracting={reExtractPending.contract_value}
                    reExtractResult={reExtractResult.contract_value}
                  />
                  <EditableField
                    label={t('contract.contractType')}
                    value={contract.contract_type || null}
                    displayValue={contract.contract_type ? contractTypeLabel(contract.contract_type) : null}
                    fieldName="contract_type"
                    onSave={(field, val) => updateMetadataMutation.mutate({ [field]: val })}
                    canEdit={canEditCustomFields}
                    provenance={contract.metadata_provenance?.contract_type}
                    onReExtract={canEditCustomFields ? (h) => handleReExtract('contract_type', h) : undefined}
                    reExtracting={reExtractPending.contract_type}
                    reExtractResult={reExtractResult.contract_type}
                  />
                  <EditableField
                    label={t('contract.effectiveDate')}
                    value={contract.effective_date || null}
                    displayValue={formatDate(contract.effective_date)}
                    fieldName="effective_date"
                    type="date"
                    onSave={(field, val) => updateMetadataMutation.mutate({ [field]: val })}
                    canEdit={canEditCustomFields}
                    provenance={contract.metadata_provenance?.effective_date}
                    onReExtract={canEditCustomFields ? (h) => handleReExtract('effective_date', h) : undefined}
                    reExtracting={reExtractPending.effective_date}
                    reExtractResult={reExtractResult.effective_date}
                  />
                  <EditableField
                    label={t('contract.expirationDate')}
                    value={contract.expiration_date || null}
                    displayValue={formatDate(contract.expiration_date)}
                    fieldName="expiration_date"
                    type="date"
                    onSave={(field, val) => updateMetadataMutation.mutate({ [field]: val })}
                    canEdit={canEditCustomFields}
                    provenance={contract.metadata_provenance?.expiration_date}
                    onReExtract={canEditCustomFields ? (h) => handleReExtract('expiration_date', h) : undefined}
                    reExtracting={reExtractPending.expiration_date}
                    reExtractResult={reExtractResult.expiration_date}
                  />
                  <EditableField
                    label={t('contract.jurisdiction')}
                    value={contract.jurisdiction}
                    fieldName="jurisdiction"
                    onSave={(field, val) => updateMetadataMutation.mutate({ [field]: val })}
                    canEdit={canEditCustomFields}
                    provenance={contract.metadata_provenance?.jurisdiction}
                    onReExtract={canEditCustomFields ? (h) => handleReExtract('jurisdiction', h) : undefined}
                    reExtracting={reExtractPending.jurisdiction}
                    reExtractResult={reExtractResult.jurisdiction}
                  />
                  <div>
                    <p className="text-xs text-gray-500">{t('contract.autoRenewal')}</p>
                    <p className="text-sm font-medium text-gray-900">
                      {contract.auto_renewal ? t('common.yes') : t('common.no')}
                      {contract.notice_period_days && ` ${t('contract.noticeDays', { days: contract.notice_period_days })}`}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">{t('contract.renewalTerm')}</p>
                    <p className="text-sm font-medium text-gray-900">
                      {contract.renewal_term_months ? t('contract.months', { count: contract.renewal_term_months }) : '-'}
                    </p>
                  </div>
                  {/* Industry Profile selector */}
                  <div>
                    <p className="text-xs text-gray-500 mb-1">{t('contract.industryProfile')}</p>
                    {canEditCustomFields ? (
                      <select
                        value={contract.industry_profile_id || ''}
                        onChange={(e) => updateMetadataMutation.mutate({ industry_profile_id: e.target.value || null })}
                        className="w-full text-sm border border-gray-200 rounded-md px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-violet-400"
                      >
                        <option value="">{t('contract.inheritFromTenant')}</option>
                        {industryProfiles.map((p: any) => (
                          <option key={p.id} value={p.id}>{p.name}</option>
                        ))}
                      </select>
                    ) : (
                      <p className="text-sm font-medium text-gray-900">
                        {industryProfiles.find((p: any) => p.id === contract.industry_profile_id)?.name || t('contract.tenantDefault')}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Custom Fields */}
              <CustomFieldsDisplay contract={contract} canEdit={canEditCustomFields} />

              {/* Risk Assessment - only show if analyzed */}
              {contract.risk_score !== null && (
                <div className="card">
                  <div className="card-header">
                    <h2 className="text-sm font-medium text-gray-900">{t('contract.riskAssessment')}</h2>
                  </div>
                  <div className="card-body">
                    <div className="flex items-center gap-6">
                      <div className={cn(
                        'h-20 w-20 rounded-full flex items-center justify-center text-2xl font-bold',
                        getRiskColor(contract.risk_level)
                      )}>
                        {contract.risk_score}
                      </div>
                      <div className="flex-1">
                        <p className="text-lg font-medium text-gray-900 capitalize mb-1">
                          {t('contract.riskLabel', { level: t(`risk.${contract.risk_level}`, { defaultValue: contract.risk_level }) })}
                        </p>
                        <p className="text-sm text-gray-500">
                          {t('contract.riskBasis', { clauses: contract.clause_count, obligations: contract.obligation_count })}
                        </p>
                        {isCompleted && (
                          <button
                            onClick={() => setActiveTab('review')}
                            className="text-sm text-primary-600 hover:text-primary-700 mt-2"
                          >
                            {t('contract.viewDetailedAnalysis')}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Right column - File info & stats */}
            <div className="space-y-6">
              {/* File Information */}
              <div className="card">
                <div className="card-header">
                  <h2 className="text-sm font-medium text-gray-900">{t('contract.fileInformation')}</h2>
                </div>
                <div className="card-body space-y-4">
                  <div className="flex items-center gap-3">
                    <DocumentTextIcon className="h-10 w-10 text-gray-400" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {contract.filename}
                      </p>
                      <p className="text-xs text-gray-500">
                        {formatFileSize(contract.file_size)} • {contract.mime_type}
                      </p>
                    </div>
                  </div>
                  <div className="pt-4 border-t border-gray-200 space-y-3">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">{t('contract.uploaded')}</span>
                      <span className="text-gray-900">{formatDate(contract.created_at)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">{t('contract.lastUpdated')}</span>
                      <span className="text-gray-900">{formatDate(contract.updated_at)}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Extraction Health — surfaces silent pipeline failures */}
              {isCompleted && contract.extraction_health && Object.keys(contract.extraction_health).length > 0 && (
                <ExtractionHealthPanel health={contract.extraction_health} />
              )}

              {/* Extraction Stats */}
              {isCompleted && (
                <div className="card">
                  <div className="card-header">
                    <h2 className="text-sm font-medium text-gray-900">{t('contract.extractionSummary')}</h2>
                  </div>
                  <div className="card-body">
                    <div className="grid grid-cols-2 gap-4">
                      <button
                        onClick={() => setActiveTab('review')}
                        className="text-center p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
                      >
                        <p className="text-2xl font-bold text-gray-900">{contract.clause_count}</p>
                        <p className="text-xs text-gray-500">{t('contract.clauses')}</p>
                      </button>
                      <button
                        onClick={() => setActiveTab('review')}
                        className="text-center p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
                      >
                        <p className="text-2xl font-bold text-gray-900">{contract.obligation_count}</p>
                        <p className="text-xs text-gray-500">{t('contract.obligations')}</p>
                      </button>
                      <button
                        onClick={() => setActiveTab('slas')}
                        className="text-center p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
                      >
                        <p className="text-2xl font-bold text-gray-900">{contract.sla_count || 0}</p>
                        <p className="text-xs text-gray-500">{t('contract.slas')}</p>
                      </button>
                      <button
                        onClick={() => setActiveTab('related')}
                        className="text-center p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
                      >
                        <p className="text-2xl font-bold text-primary-600">→</p>
                        <p className="text-xs text-gray-500">{t('contract.related')}</p>
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* SLAs Tab */}
        {activeTab === 'slas' && isCompleted && id && (
          <SLASummary contractId={id} />
        )}

        {/* Related Docs Tab */}
        {activeTab === 'related' && isCompleted && id && (
          <SuggestedLinksPanel contractId={id} />
        )}

        {/* Documents Tab */}
        {activeTab === 'documents' && id && (
          <ContractDocumentsTab contractId={id} />
        )}

        {/* Sharing Tab */}
        {activeTab === 'sharing' && id && (
          <ContractSharing contractId={id} />
        )}
      </div>
      )}
    </div>
  )
}


const CLAUSE_LABELS: Record<string, string> = {
  quality_assurance: 'Quality Assurance',
  warranty: 'Warranty',
  limitation_of_liability: 'Limitation of Liability',
  definitions: 'Definitions',
  governance: 'Governance',
  scope: 'Scope of Work',
  payment_terms: 'Payment Terms',
  termination: 'Termination',
  confidentiality: 'Confidentiality',
  intellectual_property: 'Intellectual Property',
  data_protection: 'Data Protection',
  preamble: 'Preamble',
  service_level: 'Service Level',
  procedural: 'Procedural',
  indemnification: 'Indemnification',
  force_majeure: 'Force Majeure',
  dispute_resolution: 'Dispute Resolution',
  other: 'Other',
}

const RISK_COLORS: Record<string, string> = {
  low: 'bg-green-100 text-green-700',
  medium: 'bg-amber-100 text-amber-700',
  high: 'bg-red-100 text-red-700',
  critical: 'bg-purple-100 text-purple-700',
}

/** Inline-editable metadata field with pencil icon */
function EditableField({
  label,
  value,
  displayValue,
  fieldName,
  onSave,
  type = 'text',
  canEdit,
  provenance,
  onReExtract,
  reExtracting,
  reExtractResult,
}: {
  label: string
  value: string | null | undefined
  displayValue?: string | null
  fieldName: string
  onSave: (field: string, val: string) => void
  type?: 'text' | 'date' | 'number'
  canEdit: boolean
  provenance?: { raw_text: string; confidence: number } | null
  /** When provided, the provenance popover gets a "Re-extract" button. */
  onReExtract?: (hint: string | undefined) => void
  reExtracting?: boolean
  reExtractResult?: { applied: boolean; reason?: string | null } | null
}) {
  const { t } = useTranslation()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value || '')
  const [showProvenance, setShowProvenance] = useState(false)
  const [showHint, setShowHint] = useState(false)
  const [hint, setHint] = useState('')

  const handleSave = () => {
    if (draft !== (value || '')) {
      onSave(fieldName, draft)
    }
    setEditing(false)
  }

  const handleCancel = () => {
    setDraft(value || '')
    setEditing(false)
  }

  const shown = displayValue !== undefined ? (displayValue || '-') : (value || '-')

  if (editing) {
    return (
      <div>
        <p className="text-xs text-gray-500 mb-1">{label}</p>
        <div className="flex items-center gap-1">
          <input
            type={type}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') handleCancel() }}
            autoFocus
            className="text-sm font-medium text-gray-900 border border-primary-300 rounded px-2 py-0.5 w-full focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
          <button onClick={handleSave} className="p-0.5 text-green-600 hover:text-green-700">
            <CheckIcon className="h-4 w-4" />
          </button>
          <button onClick={handleCancel} className="p-0.5 text-gray-400 hover:text-gray-600">
            <XMarkIcon className="h-4 w-4" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="group relative">
      <p className="text-xs text-gray-500">{label}</p>
      <div className="flex items-center gap-1">
        <p className="text-sm font-medium text-gray-900">{shown}</p>
        {provenance && provenance.raw_text && (
          <button
            onClick={() => setShowProvenance((s) => !s)}
            className={cn(
              'p-0.5 text-gray-400 hover:text-primary-600 transition-colors',
              showProvenance && 'text-primary-600'
            )}
            title={t('contract.showExtractionSource')}
            aria-label={`${t('contract.showExtractionSource')} — ${label}`}
          >
            <InformationCircleIcon className="h-3.5 w-3.5" />
          </button>
        )}
        {canEdit && (
          <button
            onClick={() => { setDraft(value || ''); setEditing(true) }}
            className="opacity-0 group-hover:opacity-100 p-0.5 text-gray-400 hover:text-primary-600 transition-opacity"
            title={`${t('common.edit')} — ${label}`}
          >
            <PencilIcon className="h-3 w-3" />
          </button>
        )}
      </div>
      {showProvenance && provenance && (
        <div className="absolute z-20 left-0 top-full mt-1 w-80 rounded-md border border-gray-200 bg-white shadow-lg p-3 text-xs">
          <div className="flex items-center justify-between mb-1.5">
            <span className="font-medium text-gray-700">{t('contract.aiExtractedFrom')}</span>
            <span
              className={cn(
                'px-1.5 py-0.5 rounded text-xs font-medium',
                provenance.confidence >= 0.85 ? 'bg-green-50 text-green-700' :
                provenance.confidence >= 0.6 ? 'bg-amber-50 text-amber-700' :
                'bg-red-50 text-red-700'
              )}
              title={t('contract.extractionConfidence')}
            >
              {Math.round(provenance.confidence * 100)}%
            </span>
          </div>
          <p className="text-gray-700 italic leading-snug">"{provenance.raw_text}"</p>
          <p className="text-[10px] text-gray-400 mt-2">
            {t('contract.sourceQuoteNote')}
          </p>

          {/* Re-extract action — only available for the 7 metadata fields */}
          {onReExtract && (
            <div className="mt-3 pt-2 border-t border-gray-100">
              {!showHint ? (
                <div className="flex items-center justify-between gap-2">
                  <button
                    onClick={() => onReExtract(undefined)}
                    disabled={reExtracting}
                    className={cn(
                      'inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium',
                      reExtracting
                        ? 'bg-gray-50 text-gray-400 cursor-not-allowed'
                        : 'bg-primary-50 text-primary-700 hover:bg-primary-100'
                    )}
                  >
                    {reExtracting ? (
                      <>
                        <ArrowPathIcon className="h-3 w-3 animate-spin" />
                        {t('contract.reExtracting')}
                      </>
                    ) : (
                      <>
                        <ArrowPathIcon className="h-3 w-3" />
                        {t('contract.reExtractField')}
                      </>
                    )}
                  </button>
                  <button
                    onClick={() => setShowHint(true)}
                    disabled={reExtracting}
                    className="text-xs text-gray-500 hover:text-gray-700 underline"
                  >
                    {t('contract.addHint')}
                  </button>
                </div>
              ) : (
                <div className="space-y-1.5">
                  <label className="text-[11px] text-gray-600">
                    {t('contract.hintLabel')}
                  </label>
                  <textarea
                    value={hint}
                    onChange={(e) => setHint(e.target.value)}
                    placeholder={t('contract.hintPlaceholder')}
                    rows={2}
                    className="w-full text-xs border border-gray-200 rounded p-1.5 focus:outline-none focus:ring-1 focus:ring-primary-400"
                  />
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => { onReExtract(hint.trim() || undefined); setShowHint(false); setHint('') }}
                      disabled={reExtracting}
                      className="px-2 py-1 rounded text-xs font-medium bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50"
                    >
                      {t('contract.reExtract')}
                    </button>
                    <button
                      onClick={() => { setShowHint(false); setHint('') }}
                      className="text-xs text-gray-500 hover:text-gray-700"
                    >
                      {t('common.cancel')}
                    </button>
                  </div>
                </div>
              )}
              {reExtractResult && !reExtracting && (
                <p className={cn(
                  'mt-1.5 text-[11px]',
                  reExtractResult.applied ? 'text-green-700' : 'text-amber-700'
                )}>
                  {reExtractResult.applied
                    ? t('contract.reExtractApplied')
                    : reExtractResult.reason || t('contract.reExtractNotApplied')}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/** Compact collapsible clause row — matches the Review tab style */
function ClauseCompactRow({ clause, onViewSource, isActive }: { clause: any; onViewSource: () => void; isActive?: boolean }) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)
  const [showFull, setShowFull] = useState(false)
  const label = t(`clauses.${clause.clause_type}`, {
    defaultValue: CLAUSE_LABELS[clause.clause_type] || clause.clause_type.replace(/_/g, ' '),
  })
  const preview = clause.summary || clause.text.substring(0, 80)
  const isLongText = clause.text.length > 300
  const displayText = showFull || !isLongText ? clause.text : clause.text.substring(0, 300) + '...'

  return (
    <div className={cn('px-4 py-2.5 hover:bg-gray-50 cursor-pointer', isActive && 'bg-primary-50 border-l-2 border-primary-500')}>
      <div className="flex items-center gap-2" onClick={onViewSource}>
        <button onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }} className="flex-1 flex items-center gap-2 text-left min-w-0">
          {expanded
            ? <ChevronDownIcon className="h-3 w-3 text-gray-400 flex-shrink-0" />
            : <ChevronRightIcon className="h-3 w-3 text-gray-400 flex-shrink-0" />
          }
          <span className="text-xs font-medium text-primary-600 flex-shrink-0">{label}</span>
          {clause.section_number && (
            <span className="text-xs text-gray-400 flex-shrink-0">{clause.section_number}</span>
          )}
          <span className="text-xs text-gray-600 truncate">{preview}...</span>
        </button>
        {clause.risk_level && (
          <span className={cn('inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium flex-shrink-0', RISK_COLORS[clause.risk_level] || 'bg-gray-100 text-gray-600')}>
            {t(`risk.${clause.risk_level}`, { defaultValue: clause.risk_level })}
          </span>
        )}
        {clause.page_number && (
          <span className="text-[10px] text-gray-400 flex-shrink-0">p.{clause.page_number}</span>
        )}
        <button
          onClick={(e) => { e.stopPropagation(); onViewSource() }}
          title={clause.page_number ? t('contract.viewOnPage', { page: clause.page_number }) : t('contract.highlightInPdf')}
          className="p-1 rounded hover:bg-primary-100 text-primary-600 flex-shrink-0"
        >
          <DocumentMagnifyingGlassIcon className="h-4 w-4" />
        </button>
      </div>
      {expanded && (
        <div className="mt-2 ml-5 space-y-2">
          <p className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed">{displayText}</p>
          {isLongText && (
            <button
              onClick={(e) => { e.stopPropagation(); setShowFull(!showFull) }}
              className="text-[10px] font-medium text-primary-600 hover:text-primary-700"
            >
              {showFull ? t('contract.showLess') : t('contract.showFullText')}
            </button>
          )}
          {clause.risk_reason && (
            <p className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1">{clause.risk_reason}</p>
          )}
        </div>
      )}
    </div>
  )
}

/** Split-pane clause tab with PDF viewer and highlighting — matches Review tab pattern */
function ClauseFilteredTab({
  contractId,
  contract,
  title,
  clauseTypes,
  emptyMessage,
}: {
  contractId: string
  contract: { mime_type?: string | null }
  title: string
  clauseTypes: string[]
  emptyMessage: string
}) {
  const { t } = useTranslation()
  const [highlightPage, setHighlightPage] = useState<number | null>(null)
  const [highlightText, setHighlightText] = useState<string | null>(null)
  const [activeRects, setActiveRects] = useState<HighlightRect[] | null>(null)
  const [activeClauseId, setActiveClauseId] = useState<string | null>(null)

  const { data: allClauses, isLoading } = useQuery<any[]>({
    queryKey: ['contract-clauses', contractId],
    queryFn: async () => {
      const response = await apiClient.get(`/contracts/${contractId}/clauses`)
      return response.data
    },
  })

  const { data: highlights } = useQuery({
    queryKey: ['contract-highlights', contractId],
    queryFn: () => api.getContractHighlights(contractId),
  })

  const filtered = allClauses?.filter((c) => clauseTypes.includes(c.clause_type)) || []
  const others = allClauses?.filter((c) => !clauseTypes.includes(c.clause_type)) || []

  const handleViewSource = (clause: any) => {
    setActiveClauseId(clause.id)
    const clauseHL = highlights?.highlights?.[clause.id]
    if (clauseHL?.rects?.length) {
      setActiveRects(clauseHL.rects)
      setHighlightPage(clauseHL.rects[0].page)
      setHighlightText(null)
    } else {
      setActiveRects(null)
      setHighlightPage(clause.page_number || null)
      // Use ~80 chars so only the opening line gets highlighted (not entire section)
      const searchText = clause.text.substring(0, 80)
      setHighlightText(searchText)
    }
  }

  return (
    <div className="flex h-full">
      {/* Left Pane: Clause List */}
      <div className="flex-shrink-0 overflow-y-auto border-r border-gray-200 bg-gray-50" style={{ width: '45%' }}>
        <div className="sticky top-0 bg-gray-50 border-b border-gray-200 px-4 py-3 z-10">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
            <span className="text-xs text-gray-500">
              {t('contract.relevantTotal', { relevant: filtered.length, total: allClauses?.length || 0 })}
            </span>
          </div>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-8"><LoadingSpinner size="lg" /></div>
        ) : !allClauses || allClauses.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            <DocumentTextIcon className="h-10 w-10 mx-auto mb-3 text-gray-300" />
            <p className="text-sm">{emptyMessage}</p>
          </div>
        ) : (
          <>
            {filtered.length > 0 ? (
              <div className="divide-y divide-gray-100">
                {filtered.map((clause) => (
                  <ClauseCompactRow
                    key={clause.id}
                    clause={clause}
                    isActive={activeClauseId === clause.id}
                    onViewSource={() => handleViewSource(clause)}
                  />
                ))}
              </div>
            ) : (
              <div className="p-6 text-center text-gray-400 text-sm">
                {t('contract.noMatchingClauses')}
              </div>
            )}

            {others.length > 0 && (
              <details className="border-t border-gray-200">
                <summary className="text-xs font-medium text-gray-500 cursor-pointer hover:text-gray-700 px-4 py-2 bg-gray-100">
                  {t('contract.otherClauses', { count: others.length })}
                </summary>
                <div className="divide-y divide-gray-100 opacity-75">
                  {others.map((clause) => (
                    <ClauseCompactRow
                      key={clause.id}
                      clause={clause}
                      isActive={activeClauseId === clause.id}
                      onViewSource={() => handleViewSource(clause)}
                    />
                  ))}
                </div>
              </details>
            )}
          </>
        )}
      </div>

      {/* Right Pane: PDF Viewer */}
      <div className="flex-1 min-w-0">
        <ContractPdfViewer
          contractId={contractId}
          mimeType={contract.mime_type}
          highlightPage={highlightPage}
          highlightText={highlightText}
          activeRects={activeRects}
          allHighlights={highlights?.highlights}
          pageDimensions={highlights?.page_dimensions}
          onHighlightClick={(clauseId) => {
            setActiveClauseId(clauseId)
            const clauseHL = highlights?.highlights?.[clauseId]
            if (clauseHL?.rects?.length) {
              setActiveRects(clauseHL.rects)
              setHighlightPage(clauseHL.rects[0].page)
              setHighlightText(null)
            }
          }}
          onPageChange={() => { setHighlightText(null); setHighlightPage(null); setActiveRects(null); setActiveClauseId(null) }}
        />
      </div>
    </div>
  )
}
