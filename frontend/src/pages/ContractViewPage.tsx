/* Contract detail — Direction B redesign.
   Pinned header (back + id/status/tags + title + actions) → Tabs primitive →
   scrollable tab panels. The overview tab renders extracted metadata as labeled
   rows with the core AI pattern: a Confidence bar whose hover shows a rich
   provenance tooltip, plus a source Drawer with per-field re-extraction.
   Data fetching, mutations, permissions and tab behavior are unchanged from
   the pre-redesign page. */
import { useState, useMemo } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  ArrowPathIcon,
  ChartBarIcon,
  ChatBubbleLeftRightIcon,
  CheckCircleIcon,
  CheckIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  DocumentMagnifyingGlassIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  LinkIcon,
  MinusCircleIcon,
  PencilIcon,
  ShareIcon,
  ShieldExclamationIcon,
  SparklesIcon,
  Square3Stack3DIcon,
  TrashIcon,
  TruckIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import type { ExtractionStageOutcome, MetadataProvenance } from '@/types'
import api from '@/lib/api'
import { client as apiClient } from '@/lib/api/client'
import { reExtractMetadataField, type ReExtractableField } from '@/lib/api/contracts'
import { getIndustryProfiles } from '@/lib/api/admin'
import type { HighlightRect } from '@/lib/api/contracts'
import {
  AiTag,
  Button,
  Confidence,
  ConfirmDialog,
  Drawer,
  EmptyState,
  IconButton,
  Pill,
  Select,
  Stat,
  Tabs,
  Tag,
  Tooltip,
  useToast,
} from '@/components/ui'
import type { IconType, PillTone, TabDef } from '@/components/ui'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import SLASummary from '@/components/dashboard/SLASummary'
import CustomFieldsDisplay from '@/components/contracts/CustomFieldsDisplay'
import SuggestedLinksPanel from '@/components/contracts/SuggestedLinksPanel'
import ContractSharing from '@/components/contracts/ContractSharing'
import ContractDocumentsTab from '@/components/contracts/ContractDocumentsTab'
import ContractReviewPane from '@/components/contracts/ContractReviewPane'
import ContractPdfViewer from '@/components/contracts/ContractPdfViewer'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/contexts/AuthContext'
import { useTenantConfig } from '@/contexts/TenantConfigContext'
import { cn, formatDate, formatCurrency, formatFileSize } from '@/lib/utils'

// ── Tone maps ────────────────────────────────────────────────────

const STATUS_TONE: Record<string, PillTone> = {
  completed: 'ok',
  processing: 'in',
  pending: 'n',
  failed: 'da',
}

const RISK_TONE: Record<string, PillTone> = {
  low: 'ok',
  medium: 'wa',
  high: 'da',
  critical: 'da',
}

function riskCssTone(level: string | null | undefined): string {
  const key = (level || '').toLowerCase()
  if (key === 'high' || key === 'critical') return 'var(--da)'
  if (key === 'medium') return 'var(--wa)'
  return 'var(--ok)'
}

// Map config icon names to Heroicon components
const TAB_ICON_MAP: Record<string, IconType> = {
  document: InformationCircleIcon,
  eye: DocumentMagnifyingGlassIcon,
  chart: ChartBarIcon,
  link: LinkIcon,
  folder: DocumentTextIcon,
  share: ShareIcon,
  shield: ShieldExclamationIcon,
  truck: TruckIcon,
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

const PROCUREMENT_TYPES = new Set([
  'procurement', 'procurement_agreement', 'hardware_procurement_contract',
  'supply_agreement', 'quality_agreement', 'blanket_po', 'manufacturing_supply',
  'annual_maintenance', 'rate_contract', 'distribution', 'vendor',
])

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

/** Confidence figure as a toned pill (prototype ConfBand). */
function ConfBand({ v }: { v: number }) {
  const tone: PillTone = v >= 0.9 ? 'ok' : v >= 0.6 ? 'wa' : 'da'
  return (
    <Pill tone={tone} dot={false}>
      <span className="mono num">{v.toFixed(2)}</span>
    </Pill>
  )
}

// ── Extraction health ────────────────────────────────────────────

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
    counts.failed > 0 ? 'var(--da)' : counts.skipped > 0 ? 'var(--wa)' : 'var(--ok)'

  return (
    <div className="card card-p col" style={{ gap: 10 }}>
      <div className="row" style={{ gap: 8 }}>
        <span className="sec-t grow">{t('contract.extractionHealth')}</span>
        <span style={{ fontSize: 'var(--fs-xs)', fontWeight: 600, color: headlineColor }}>
          {t('contract.healthCounts', { success: counts.success, failed: counts.failed, skipped: counts.skipped })}
        </span>
      </div>
      <div className="col" style={{ gap: 6 }}>
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
            status === 'success' ? 'var(--ok)' : status === 'failed' ? 'var(--da)' : 'var(--f)'
          const note = outcome.error || outcome.reason
          const dropped = (outcome.details?.dropped_fields as Array<{
            field: string
            confidence: number
            threshold: number
          }> | undefined)
          return (
            <div key={s.key} className="row" style={{ gap: 8, alignItems: 'flex-start', fontSize: 'var(--fs-sm)' }}>
              <Icon style={{ width: 15, height: 15, marginTop: 1, flexShrink: 0, color: iconColor }} aria-hidden />
              <div className="grow" style={{ minWidth: 0 }}>
                <div className="row" style={{ gap: 8 }}>
                  <span className="grow trunc">{t(`contract.stages.${s.key}`, { defaultValue: s.label })}</span>
                  <span className="faint" style={{ textTransform: 'capitalize', flexShrink: 0 }}>
                    {t(`contract.stageStatus.${status}`, { defaultValue: status.replace('_', ' ') })}
                  </span>
                </div>
                {note && (
                  <p className="faint trunc" title={note} style={{ fontSize: 'var(--fs-xs)' }}>
                    {note}
                  </p>
                )}
                {dropped && dropped.length > 0 && (
                  <p
                    style={{ fontSize: 'var(--fs-xs)', color: 'var(--wa)' }}
                    title={dropped.map(d => `${d.field}: ${d.confidence} < ${d.threshold}`).join('\n')}
                  >
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

// ── Risk gauge ───────────────────────────────────────────────────

function RiskGauge({ score, level }: { score: number; level: string | null }) {
  const { t } = useTranslation()
  const tone = riskCssTone(level)
  const r = 34
  const c = 2 * Math.PI * r
  return (
    <div className="row" style={{ gap: 16 }}>
      <div style={{ position: 'relative', width: 80, height: 80, flexShrink: 0 }}>
        <svg width="80" height="80" style={{ transform: 'rotate(-90deg)' }}>
          <circle cx="40" cy="40" r={r} fill="none" stroke="var(--b)" strokeWidth="8" />
          <circle
            cx="40" cy="40" r={r} fill="none" stroke={tone} strokeWidth="8" strokeLinecap="round"
            strokeDasharray={c} strokeDashoffset={c * (1 - Math.max(0, Math.min(100, score)) / 100)}
          />
        </svg>
        <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}>
          <span className="num" style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600, color: tone }}>{score}</span>
        </div>
      </div>
      <div>
        <div className="row" style={{ gap: 8 }}>
          <b style={{ fontSize: 'var(--fs-lg)', textTransform: 'capitalize' }}>
            {t('contract.riskLabel', { level: t(`risk.${level}`, { defaultValue: level || '' }) })}
          </b>
          <AiTag />
        </div>
      </div>
    </div>
  )
}

// ── Metadata row (the core Confidence + provenance pattern) ──────

function MetaRow({
  label,
  rawValue,
  displayValue,
  type = 'text',
  canEdit,
  provenance,
  onSave,
  onViewSource,
}: {
  label: string
  rawValue: string | null
  displayValue?: string | null
  type?: 'text' | 'date' | 'number'
  canEdit: boolean
  provenance?: MetadataProvenance | null
  onSave: (val: string) => void
  onViewSource?: () => void
}) {
  const { t } = useTranslation()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(rawValue || '')

  const shown = displayValue !== undefined && displayValue !== null && displayValue !== ''
    ? displayValue
    : (rawValue || null)
  const hasValue = shown != null && shown !== '-'
  const conf = provenance?.confidence

  const handleSave = () => {
    if (draft !== (rawValue || '')) onSave(draft)
    setEditing(false)
  }
  const handleCancel = () => {
    setDraft(rawValue || '')
    setEditing(false)
  }

  return (
    <div
      className="row"
      style={{
        gap: 12, minHeight: 46, padding: '8px 14px', borderBottom: '1px solid var(--b)',
        background: conf != null && conf < 0.6 ? 'var(--da-f)' : undefined,
      }}
    >
      <span className="muted" style={{ width: 168, flexShrink: 0, fontSize: 'var(--fs-md)', fontWeight: 500 }}>
        {label}
      </span>
      <span className="grow row" style={{ gap: 8, minWidth: 0 }}>
        {editing ? (
          <span className="inp grow" style={{ height: 28 }}>
            <input
              type={type}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') handleCancel() }}
              autoFocus
            />
          </span>
        ) : (
          <span
            className="trunc"
            style={{
              fontSize: 'var(--fs-md)',
              color: hasValue ? 'var(--t)' : 'var(--f)',
              fontStyle: hasValue ? undefined : 'italic',
              fontWeight: hasValue ? 500 : 400,
            }}
          >
            {shown ?? t('contract.notFound2', { defaultValue: 'Not found' })}
          </span>
        )}
        {!editing && provenance && <AiTag />}
      </span>

      {/* Confidence + rich provenance tooltip — only when the payload has it */}
      {conf != null ? (
        <Tooltip
          rich
          side="bottom"
          subhead={t('contract.confidenceSubhead', { value: conf.toFixed(2), defaultValue: 'Confidence {{value}}' })}
          label={provenance?.raw_text ? `"${provenance.raw_text}"` : t('contract.sourceQuoteNote')}
          footer={t('contract.provenanceAgent', { defaultValue: 'metadata agent' })}
        >
          <span className="row" style={{ gap: 8, cursor: 'help' }}>
            <Confidence value={conf} width={44} showNum={false} />
            <ConfBand v={conf} />
          </span>
        </Tooltip>
      ) : (
        <span className="faint" style={{ fontSize: 'var(--fs-sm)', flexShrink: 0 }}>
          {t('contract.manualEntry', { defaultValue: 'manual entry' })}
        </span>
      )}

      {provenance?.raw_text && onViewSource && (
        <IconButton
          icon={DocumentMagnifyingGlassIcon}
          label={`${t('contract.showExtractionSource')} — ${label}`}
          size="sm"
          onClick={onViewSource}
        />
      )}
      {canEdit && !editing && (
        <IconButton
          icon={PencilIcon}
          label={`${t('common.edit')} — ${label}`}
          size="sm"
          onClick={() => { setDraft(rawValue || ''); setEditing(true) }}
        />
      )}
      {editing && (
        <>
          <IconButton icon={CheckIcon} label={t('common.save', { defaultValue: 'Save' })} size="sm" onClick={handleSave} />
          <IconButton icon={XMarkIcon} label={t('common.cancel')} size="sm" onClick={handleCancel} />
        </>
      )}
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────

export default function ContractViewPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { can } = useAuth()
  const { toast } = useToast()
  const { config, contractTypeLabel, uiLabel } = useTenantConfig()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  // Source-provenance drawer state (which metadata field is open)
  const [srcField, setSrcField] = useState<{
    key: string
    label: string
    display: string
    reExtractable: boolean
  } | null>(null)
  const [hint, setHint] = useState('')

  // Get active tab from URL or default to first tab
  const activeTab = searchParams.get('tab') || 'overview'
  const setActiveTab = (tab: string) => {
    setSearchParams({ tab })
  }

  // Determine if user can edit custom fields (admin, legal, or procurement roles)
  const canEditCustomFields = can('contract.editFields')

  const { data: contract, isLoading, error } = useQuery({
    queryKey: ['contract', id],
    queryFn: () => api.getContract(id!),
    enabled: !!id,
  })

  const processMutation = useMutation({
    mutationFn: () => api.processContract(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract', id] })
      toast({ text: t('contract.processQueued', { defaultValue: 'Processing started' }) })
    },
  })

  const analyzeMutation = useMutation({
    mutationFn: () => api.analyzeContract(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract', id] })
      toast({ text: t('contract.reanalyzeQueued', { defaultValue: 'Re-analysis queued' }) })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteContract(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] })
      queryClient.invalidateQueries({ queryKey: ['contracts-summary'] })
      navigate('/contracts')
    },
    onError: () => {
      toast({ text: t('contracts.deleteFailed', { defaultValue: 'Delete failed. Please try again.' }), error: true })
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
  // fields can show their own pending/result state independently.
  const [reExtractPending, setReExtractPending] = useState<Record<string, boolean>>({})
  const [reExtractResult, setReExtractResult] = useState<
    Record<string, { applied: boolean; reason?: string | null } | null>
  >({})

  const handleReExtract = (field: ReExtractableField, hintText: string | undefined) => {
    if (!id) return
    setReExtractPending((p) => ({ ...p, [field]: true }))
    setReExtractResult((r) => ({ ...r, [field]: null }))
    reExtractMetadataField(id, field, hintText)
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
  const tabs = useMemo(() => {
    // Industry profiles can define arbitrary detail_tabs; only ids this page
    // can actually render are shown — unknown ids would be blank panels.
    const RENDERED_TAB_IDS = new Set([
      'overview', 'review', 'quality', 'supply_chain', 'slas',
      'related', 'documents', 'sharing',
    ])
    const mapped = (config?.ui?.detail_tabs || DEFAULT_TABS)
      .filter((tb) => RENDERED_TAB_IDS.has(tb.id))
      .map((tb) => ({
        id: tb.id,
        label: tb.label,
        icon: TAB_ICON_MAP[tb.icon || ''] || InformationCircleIcon,
      }))
    const ct = contract?.contract_type?.toLowerCase() || ''
    const needsProcurementTabs = PROCUREMENT_TYPES.has(ct) ||
      ct.includes('procurement') || ct.includes('supply') || ct.includes('manufacturing')
    if (needsProcurementTabs) {
      const existingIds = new Set(mapped.map((tb) => tb.id))
      const insertIdx = mapped.findIndex((tb) => tb.id === 'review') + 1 || 2
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
            icon: TAB_ICON_MAP[pt.icon] || InformationCircleIcon,
          })
          offset++
        }
      }
      // Also ensure SLAs tab is present
      if (!existingIds.has('slas')) {
        const relIdx = mapped.findIndex((tb) => tb.id === 'supply_chain')
        mapped.splice(relIdx + 1, 0, {
          id: 'slas',
          label: 'SLAs',
          icon: ChartBarIcon,
        })
      }
    }
    return mapped
  }, [config, contract?.contract_type])

  if (isLoading) {
    return (
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !contract) {
    return (
      <EmptyState
        icon={DocumentTextIcon}
        title={t('contract.notFound')}
        action={
          <Button variant="secondary" size="sm" icon={ArrowLeftIcon} onClick={() => navigate('/contracts')}>
            {t('contract.backToContracts')}
          </Button>
        }
      />
    )
  }

  const isCompleted = contract.status === 'completed'
  const provenance = contract.metadata_provenance || {}

  // Extracted metadata rows. Fields with provenance in the payload get the
  // Confidence + provenance pattern; the rest render as plain fields.
  const metaFields: Array<{
    key: string
    label: string
    rawValue: string | null
    displayValue?: string | null
    type?: 'text' | 'date' | 'number'
    save: (val: string) => void
    reExtractable: boolean
  }> = [
    {
      key: 'counterparty',
      label: uiLabel('counterparty', t('contracts.counterparty')),
      rawValue: contract.counterparty,
      save: (val) => updateMetadataMutation.mutate({ counterparty: val }),
      reExtractable: true,
    },
    {
      key: 'contract_value',
      label: uiLabel('contract_value', t('contract.contractValue')),
      rawValue: contract.contract_value != null ? String(contract.contract_value) : null,
      displayValue: contract.contract_value != null
        ? formatCurrency(contract.contract_value, contract.currency || 'USD')
        : null,
      type: 'number',
      save: (val) => updateMetadataMutation.mutate({ contract_value: Number(val) }),
      reExtractable: true,
    },
    {
      key: 'contract_type',
      label: t('contract.contractType'),
      rawValue: contract.contract_type || null,
      displayValue: contract.contract_type ? contractTypeLabel(contract.contract_type) : null,
      save: (val) => updateMetadataMutation.mutate({ contract_type: val }),
      reExtractable: true,
    },
    {
      key: 'effective_date',
      label: t('contract.effectiveDate'),
      rawValue: contract.effective_date || null,
      displayValue: contract.effective_date ? formatDate(contract.effective_date) : null,
      type: 'date',
      save: (val) => updateMetadataMutation.mutate({ effective_date: val }),
      reExtractable: true,
    },
    {
      key: 'expiration_date',
      label: t('contract.expirationDate'),
      rawValue: contract.expiration_date || null,
      displayValue: contract.expiration_date ? formatDate(contract.expiration_date) : null,
      type: 'date',
      save: (val) => updateMetadataMutation.mutate({ expiration_date: val }),
      reExtractable: true,
    },
    {
      key: 'jurisdiction',
      label: t('contract.jurisdiction'),
      rawValue: contract.jurisdiction,
      save: (val) => updateMetadataMutation.mutate({ jurisdiction: val }),
      reExtractable: true,
    },
  ]

  const srcProvenance = srcField ? provenance[srcField.key] : undefined
  const srcResult = srcField ? reExtractResult[srcField.key] : undefined
  const srcPending = srcField ? !!reExtractPending[srcField.key] : false

  const tabDefs: TabDef[] = tabs
    // Hide analysis tabs for non-completed contracts; overview and sharing stay.
    .filter((tab) => isCompleted || tab.id === 'overview' || tab.id === 'sharing')
    .map((tab) => ({
      value: tab.id,
      label: t(`contract.tabs.${tab.id}`, { defaultValue: tab.label }),
      icon: tab.icon,
      count: isCompleted && tab.id === 'slas' && contract.sla_count
        ? contract.sla_count
        : undefined,
    }))

  const isFullBleed = (activeTab === 'review' || activeTab === 'quality' || activeTab === 'supply_chain') && isCompleted

  return (
    <div
      className="-mx-4 sm:-mx-6 lg:-mx-8 -my-6 flex flex-col h-[calc(100vh-var(--top-h))]"
      style={{ minHeight: 0 }}
    >
      {/* Delete confirmation */}
      <ConfirmDialog
        open={showDeleteConfirm}
        title={t('contract.deleteTitle', { defaultValue: 'Delete this contract?' })}
        body={t('contract.deleteBody', { defaultValue: 'This permanently removes the document and everything the pipeline extracted from it.' })}
        affected={[
          contract.filename,
          t('contract.deleteAffected', { defaultValue: 'All extracted clauses, obligations, SLAs and risk analysis' }),
        ]}
        confirmLabel={deleteMutation.isPending ? t('contracts.deleting') : t('common.delete')}
        cancelLabel={t('common.cancel')}
        onCancel={() => { if (!deleteMutation.isPending) setShowDeleteConfirm(false) }}
        onConfirm={() => { if (!deleteMutation.isPending) deleteMutation.mutate() }}
      />

      {/* Header */}
      <div style={{ padding: '18px 24px 0', flexShrink: 0 }}>
        <div className="row" style={{ gap: 12, alignItems: 'flex-start' }}>
          <IconButton
            icon={ArrowLeftIcon}
            label={t('contract.backToContracts')}
            onClick={() => navigate('/contracts')}
          />
          <div className="grow" style={{ minWidth: 0 }}>
            <div className="row" style={{ gap: 7, marginBottom: 5, flexWrap: 'wrap' }}>
              <span className="mono faint" style={{ fontSize: 'var(--fs-xs)' }}>{contract.id.slice(0, 8)}</span>
              <Pill tone={STATUS_TONE[contract.status] || 'n'}>
                {t(`status.${contract.status}`, { defaultValue: contract.status })}
              </Pill>
              {contract.risk_level && (
                <Pill tone={RISK_TONE[contract.risk_level.toLowerCase()] || 'n'}>
                  {t('contract.riskLabel', { level: t(`risk.${contract.risk_level}`, { defaultValue: contract.risk_level }) })}
                </Pill>
              )}
              {contract.contract_type && <Tag>{contractTypeLabel(contract.contract_type)}</Tag>}
              {contract.file_size != null && (
                <Tag icon={DocumentTextIcon}>{formatFileSize(contract.file_size)}</Tag>
              )}
            </div>
            <h1 className="trunc" style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.8px', lineHeight: 1.15 }}>
              {contract.filename}
            </h1>
            <div className="row muted" style={{ gap: 8, marginTop: 6, fontSize: 'var(--fs-md)', flexWrap: 'wrap' }}>
              {contract.counterparty && <span>{contract.counterparty}</span>}
              {contract.counterparty && (contract.effective_date || contract.expiration_date) && (
                <span className="faint">·</span>
              )}
              {(contract.effective_date || contract.expiration_date) && (
                <span className="num">
                  {formatDate(contract.effective_date)} — {formatDate(contract.expiration_date)}
                </span>
              )}
              {contract.contract_value != null && (
                <>
                  <span className="faint">·</span>
                  <span className="num" style={{ fontWeight: 600, color: 'var(--t)' }}>
                    {formatCurrency(contract.contract_value, contract.currency || 'USD')}
                  </span>
                </>
              )}
            </div>
          </div>

          <div className="row" style={{ gap: 8, flexShrink: 0 }}>
            {contract.status === 'pending' && (
              <Button
                variant="secondary"
                icon={ArrowPathIcon}
                disabled={processMutation.isPending}
                onClick={() => processMutation.mutate()}
              >
                {t('contract.process')}
              </Button>
            )}
            {isCompleted && (
              <Button
                variant="primary"
                icon={SparklesIcon}
                disabled={analyzeMutation.isPending}
                onClick={() => analyzeMutation.mutate()}
              >
                {t('contract.reanalyze')}
              </Button>
            )}
            <Button
              variant="secondary"
              icon={ChatBubbleLeftRightIcon}
              onClick={() => navigate(`/query?contract=${contract.id}`)}
            >
              {t('dashboard.actions.askAi')}
            </Button>
            <Button
              variant="danger-ghost"
              icon={TrashIcon}
              onClick={() => setShowDeleteConfirm(true)}
            >
              {t('common.delete')}
            </Button>
          </div>
        </div>

        {/* Processing error banner */}
        {contract.processing_error && (
          <div className="banner banner-da" style={{ marginTop: 14 }}>
            <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
            <span className="grow">
              <b>{t('contract.processingError')}</b> — {contract.processing_error}
            </span>
          </div>
        )}

        {/* Tab navigation */}
        <Tabs tabs={tabDefs} value={activeTab} onChange={setActiveTab} style={{ marginTop: 16 }} />
      </div>

      {/* Full-bleed panes (review, quality, supply chain) */}
      {isFullBleed && id && (
        <div className="grow" style={{ minHeight: 0, overflow: 'hidden' }}>
          {activeTab === 'review' && <ContractReviewPane contractId={id} contract={contract} />}
          {activeTab === 'quality' && (
            <ClauseFilteredTab
              contractId={id}
              contract={contract}
              title={t('contract.qualityClausesTitle')}
              clauseTypes={['warranty', 'limitation_of_liability', 'governance', 'definitions', 'data_protection']}
              emptyMessage={t('contract.qualityClausesEmpty')}
            />
          )}
          {activeTab === 'supply_chain' && (
            <ClauseFilteredTab
              contractId={id}
              contract={contract}
              title={t('contract.supplyChainClausesTitle')}
              clauseTypes={['scope', 'payment_terms', 'termination', 'confidentiality', 'intellectual_property']}
              emptyMessage={t('contract.supplyChainClausesEmpty')}
            />
          )}
        </div>
      )}

      {/* Scrolling panes */}
      {!isFullBleed && (
        <div className="scroll grow" style={{ padding: 24, minHeight: 0 }}>
          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Left column — extracted metadata */}
              <div className="lg:col-span-2 col" style={{ gap: 14 }}>
                {/* AI explainer + confidence legend */}
                <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
                  <div className="banner banner-p grow" style={{ minWidth: 260 }}>
                    <SparklesIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
                    <span>
                      {t('contract.aiValuesExplainer', {
                        defaultValue: 'Values marked AI were extracted by the pipeline and carry a confidence score and a source sentence. Hover any score to see the exact wording it came from.',
                      })}
                    </span>
                  </div>
                  <div className="card card-p row" style={{ gap: 14, flexShrink: 0, alignSelf: 'flex-start' }}>
                    {([['≥ 0.90', 'var(--ok)'], ['0.60–0.89', 'var(--wa)'], ['< 0.60', 'var(--da)']] as const).map((l) => (
                      <span key={l[0]} className="row" style={{ gap: 6, fontSize: 'var(--fs-sm)', color: 'var(--m)' }}>
                        <span style={{ width: 18, height: 5, borderRadius: 3, background: l[1] }} />{l[0]}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Contract details */}
                <div className="tbl-w">
                  <div
                    className="row sec-t"
                    style={{ padding: '10px 14px', background: 'var(--s3)', borderBottom: '1px solid var(--b)' }}
                  >
                    {t('contract.contractDetails')}
                  </div>
                  {metaFields.map((f) => (
                    <MetaRow
                      key={f.key}
                      label={f.label}
                      rawValue={f.rawValue}
                      displayValue={f.displayValue}
                      type={f.type}
                      canEdit={canEditCustomFields}
                      provenance={provenance[f.key]}
                      onSave={f.save}
                      onViewSource={
                        provenance[f.key]?.raw_text
                          ? () => {
                              setHint('')
                              setSrcField({
                                key: f.key,
                                label: f.label,
                                display: f.displayValue || f.rawValue || '—',
                                reExtractable: f.reExtractable,
                              })
                            }
                          : undefined
                      }
                    />
                  ))}
                  {/* Plain fields — no confidence/source info in the payload */}
                  <div className="row" style={{ gap: 12, minHeight: 46, padding: '8px 14px', borderBottom: '1px solid var(--b)' }}>
                    <span className="muted" style={{ width: 168, flexShrink: 0, fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                      {t('contract.autoRenewal')}
                    </span>
                    <span className="grow" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                      {contract.auto_renewal ? t('common.yes') : t('common.no')}
                      {contract.notice_period_days ? ` ${t('contract.noticeDays', { days: contract.notice_period_days })}` : ''}
                    </span>
                  </div>
                  <div className="row" style={{ gap: 12, minHeight: 46, padding: '8px 14px', borderBottom: '1px solid var(--b)' }}>
                    <span className="muted" style={{ width: 168, flexShrink: 0, fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                      {t('contract.renewalTerm')}
                    </span>
                    <span className="grow" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                      {contract.renewal_term_months ? t('contract.months', { count: contract.renewal_term_months }) : '—'}
                    </span>
                  </div>
                  <div className="row" style={{ gap: 12, minHeight: 46, padding: '8px 14px' }}>
                    <span className="muted" style={{ width: 168, flexShrink: 0, fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                      {t('contract.industryProfile')}
                    </span>
                    {canEditCustomFields ? (
                      <Select
                        value={contract.industry_profile_id || ''}
                        onChange={(e) => updateMetadataMutation.mutate({ industry_profile_id: e.target.value || null })}
                        containerStyle={{ maxWidth: 260, flexGrow: 1 }}
                        options={[
                          { value: '', label: t('contract.inheritFromTenant') },
                          ...industryProfiles.map((p: any) => ({ value: p.id, label: p.name })),
                        ]}
                      />
                    ) : (
                      <span className="grow" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                        {industryProfiles.find((p: any) => p.id === contract.industry_profile_id)?.name || t('contract.tenantDefault')}
                      </span>
                    )}
                  </div>
                </div>

                {/* Custom Fields */}
                <CustomFieldsDisplay contract={contract} canEdit={canEditCustomFields} />

                {/* Risk Assessment - only show if analyzed */}
                {contract.risk_score !== null && (
                  <div className="card card-p col" style={{ gap: 12 }}>
                    <div className="sec-t">{t('contract.riskAssessment')}</div>
                    <RiskGauge score={contract.risk_score} level={contract.risk_level} />
                    <p className="muted" style={{ fontSize: 'var(--fs-md)' }}>
                      {t('contract.riskBasis', { clauses: contract.clause_count, obligations: contract.obligation_count })}
                    </p>
                    {isCompleted && (
                      <div className="row">
                        <Button variant="ghost" size="sm" icon={DocumentMagnifyingGlassIcon} onClick={() => setActiveTab('review')}>
                          {t('contract.viewDetailedAnalysis')}
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Right column — file info & stats */}
              <div className="col" style={{ gap: 14 }}>
                {/* File Information */}
                <div className="card card-p col" style={{ gap: 12 }}>
                  <div className="sec-t">{t('contract.fileInformation')}</div>
                  <div className="row" style={{ gap: 10 }}>
                    <DocumentTextIcon style={{ width: 32, height: 32, flexShrink: 0, color: 'var(--f)' }} aria-hidden />
                    <div style={{ minWidth: 0 }}>
                      <p className="trunc" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>{contract.filename}</p>
                      <p className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
                        {formatFileSize(contract.file_size)} · {contract.mime_type}
                      </p>
                    </div>
                  </div>
                  <div className="col" style={{ gap: 8, paddingTop: 10, borderTop: '1px solid var(--b)' }}>
                    <div className="row" style={{ fontSize: 'var(--fs-sm)' }}>
                      <span className="muted grow">{t('contract.uploaded')}</span>
                      <span className="num">{formatDate(contract.created_at)}</span>
                    </div>
                    <div className="row" style={{ fontSize: 'var(--fs-sm)' }}>
                      <span className="muted grow">{t('contract.lastUpdated')}</span>
                      <span className="num">{formatDate(contract.updated_at)}</span>
                    </div>
                  </div>
                </div>

                {/* Extraction Health — surfaces silent pipeline failures */}
                {isCompleted && contract.extraction_health && Object.keys(contract.extraction_health).length > 0 && (
                  <ExtractionHealthPanel health={contract.extraction_health} />
                )}

                {/* Extraction Stats */}
                {isCompleted && (
                  <div className="col" style={{ gap: 8 }}>
                    <div className="sec-t">{t('contract.extractionSummary')}</div>
                    <div className="grid grid-cols-2 gap-3">
                      <Stat
                        icon={DocumentTextIcon}
                        label={t('contract.clauses')}
                        value={contract.clause_count}
                        onClick={() => setActiveTab('review')}
                      />
                      <Stat
                        icon={CheckCircleIcon}
                        label={t('contract.obligations')}
                        value={contract.obligation_count}
                        onClick={() => setActiveTab('review')}
                      />
                      <Stat
                        icon={ChartBarIcon}
                        label={t('contract.slas')}
                        value={contract.sla_count || 0}
                        onClick={() => setActiveTab('slas')}
                      />
                      <Stat
                        icon={LinkIcon}
                        label={t('contract.related')}
                        value="→"
                        onClick={() => setActiveTab('related')}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* SLAs Tab */}
          {activeTab === 'slas' && isCompleted && id && <SLASummary contractId={id} />}

          {/* Related Docs Tab */}
          {activeTab === 'related' && isCompleted && id && <SuggestedLinksPanel contractId={id} />}

          {/* Documents Tab */}
          {activeTab === 'documents' && id && <ContractDocumentsTab contractId={id} />}

          {/* Sharing Tab */}
          {activeTab === 'sharing' && id && <ContractSharing contractId={id} />}
        </div>
      )}

      {/* Source-provenance drawer (with per-field re-extraction) */}
      <Drawer
        open={!!srcField}
        title={t('contract.sourceProvenance', { defaultValue: 'Source provenance' })}
        sub={srcField ? `${contract.id.slice(0, 8)} · ${srcField.label}` : ''}
        onClose={() => setSrcField(null)}
        footer={
          srcField && srcField.reExtractable && canEditCustomFields ? (
            <Button
              variant="primary"
              icon={ArrowPathIcon}
              className="grow"
              disabled={srcPending}
              onClick={() => handleReExtract(srcField.key as ReExtractableField, hint.trim() || undefined)}
            >
              {srcPending ? t('contract.reExtracting') : t('contract.reExtractField')}
            </Button>
          ) : undefined
        }
      >
        {srcField && (
          <div className="col" style={{ gap: 18 }}>
            <div>
              <div className="sec-t" style={{ marginBottom: 7 }}>
                {t('contract.extractedValue', { defaultValue: 'Extracted value' })}
              </div>
              <div className="row" style={{ gap: 10 }}>
                <b style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600 }}>{srcField.display}</b>
                {srcProvenance && <ConfBand v={srcProvenance.confidence} />}
              </div>
            </div>
            <div>
              <div className="sec-t" style={{ marginBottom: 7 }}>
                {t('contract.aiExtractedFrom')}
              </div>
              <div
                style={{
                  padding: 14, borderRadius: 'var(--r-md)', background: 'var(--s2)',
                  fontSize: 'var(--fs-md)', lineHeight: 1.65,
                }}
              >
                "{srcProvenance?.raw_text}"
              </div>
              <div className="mono faint" style={{ fontSize: 'var(--fs-xs)', marginTop: 8 }}>
                {t('contract.provenanceAgent', { defaultValue: 'metadata agent' })}
              </div>
              <p className="faint" style={{ fontSize: 'var(--fs-xs)', marginTop: 6 }}>
                {t('contract.sourceQuoteNote')}
              </p>
            </div>
            {srcField.reExtractable && canEditCustomFields && (
              <div>
                <div className="sec-t" style={{ marginBottom: 7 }}>{t('contract.reExtract')}</div>
                <label className="lbl">{t('contract.hintLabel')}</label>
                <div className="inp" style={{ height: 'auto', padding: 10, alignItems: 'flex-start' }}>
                  <textarea
                    rows={2}
                    value={hint}
                    onChange={(e) => setHint(e.target.value)}
                    placeholder={t('contract.hintPlaceholder')}
                    style={{ resize: 'vertical', lineHeight: 1.55, width: '100%', background: 'transparent', border: 0, outline: 'none', color: 'inherit', font: 'inherit', fontSize: 'var(--fs-md)' }}
                  />
                </div>
                {srcResult && !srcPending && (
                  <p
                    style={{
                      marginTop: 8, fontSize: 'var(--fs-sm)',
                      color: srcResult.applied ? 'var(--ok)' : 'var(--wa)',
                    }}
                  >
                    {srcResult.applied
                      ? t('contract.reExtractApplied')
                      : srcResult.reason || t('contract.reExtractNotApplied')}
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </Drawer>
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
    <div
      className={cn('cursor-pointer', !isActive && 'hover:bg-[var(--s2)]')}
      style={{
        padding: '10px 14px',
        borderBottom: '1px solid var(--b)',
        borderLeft: isActive ? '2px solid var(--p)' : '2px solid transparent',
        background: isActive ? 'var(--p-f)' : undefined,
      }}
    >
      <div className="row" style={{ gap: 8 }} onClick={onViewSource}>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }}
          className="grow row text-left"
          style={{ gap: 8, minWidth: 0, background: 'none', border: 0, padding: 0, cursor: 'pointer', color: 'inherit' }}
        >
          {expanded
            ? <ChevronDownIcon style={{ width: 12, height: 12, flexShrink: 0, color: 'var(--f)' }} aria-hidden />
            : <ChevronRightIcon style={{ width: 12, height: 12, flexShrink: 0, color: 'var(--f)' }} aria-hidden />
          }
          <span style={{ fontSize: 'var(--fs-sm)', fontWeight: 600, color: 'var(--p)', flexShrink: 0 }}>{label}</span>
          {clause.section_number && (
            <span className="mono faint" style={{ fontSize: 'var(--fs-xs)', flexShrink: 0 }}>{clause.section_number}</span>
          )}
          <span className="muted trunc" style={{ fontSize: 'var(--fs-sm)' }}>{preview}...</span>
        </button>
        {clause.risk_level && (
          <Pill tone={RISK_TONE[String(clause.risk_level).toLowerCase()] || 'n'}>
            {t(`risk.${clause.risk_level}`, { defaultValue: clause.risk_level })}
          </Pill>
        )}
        {clause.page_number && (
          <span className="mono faint" style={{ fontSize: 'var(--fs-xs)', flexShrink: 0 }}>p.{clause.page_number}</span>
        )}
        <IconButton
          icon={DocumentMagnifyingGlassIcon}
          label={clause.page_number ? t('contract.viewOnPage', { page: clause.page_number }) : t('contract.highlightInPdf')}
          size="sm"
          onClick={(e) => { e.stopPropagation(); onViewSource() }}
        />
      </div>
      {expanded && (
        <div className="col" style={{ marginTop: 8, marginLeft: 20, gap: 8 }}>
          <p style={{ fontSize: 'var(--fs-sm)', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{displayText}</p>
          {isLongText && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); setShowFull(!showFull) }}
              style={{ background: 'none', border: 0, padding: 0, cursor: 'pointer', alignSelf: 'flex-start', fontSize: 'var(--fs-xs)', fontWeight: 600, color: 'var(--p)' }}
            >
              {showFull ? t('contract.showLess') : t('contract.showFullText')}
            </button>
          )}
          {clause.risk_reason && (
            <p
              style={{
                fontSize: 'var(--fs-sm)', padding: '6px 10px', borderRadius: 'var(--r-sm)',
                background: 'var(--wa-f)', color: 'var(--wa)',
              }}
            >
              {clause.risk_reason}
            </p>
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
      <div
        className="flex-shrink-0 overflow-y-auto scroll"
        style={{ width: '45%', borderRight: '1px solid var(--b)', background: 'var(--s3)' }}
      >
        <div
          style={{
            position: 'sticky', top: 0, zIndex: 10, padding: '10px 14px',
            background: 'var(--s3)', borderBottom: '1px solid var(--b)',
          }}
        >
          <div className="row" style={{ gap: 8 }}>
            <span className="sec-t grow">{title}</span>
            <span className="faint" style={{ fontSize: 'var(--fs-xs)' }}>
              {t('contract.relevantTotal', { relevant: filtered.length, total: allClauses?.length || 0 })}
            </span>
          </div>
        </div>

        {isLoading ? (
          <div className="row" style={{ justifyContent: 'center', padding: 32 }}><LoadingSpinner size="lg" /></div>
        ) : !allClauses || allClauses.length === 0 ? (
          <EmptyState icon={DocumentTextIcon} title={emptyMessage} />
        ) : (
          <>
            {filtered.length > 0 ? (
              <div>
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
              <div className="faint" style={{ padding: 24, textAlign: 'center', fontSize: 'var(--fs-md)' }}>
                {t('contract.noMatchingClauses')}
              </div>
            )}

            {others.length > 0 && (
              <details style={{ borderTop: '1px solid var(--b)' }}>
                <summary
                  className="sec-t cursor-pointer"
                  style={{ padding: '8px 14px', background: 'var(--s2)' }}
                >
                  {t('contract.otherClauses', { count: others.length })}
                </summary>
                <div style={{ opacity: 0.75 }}>
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
