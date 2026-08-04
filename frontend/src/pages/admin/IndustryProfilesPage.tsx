/* Industry Profiles admin — Direction B restyle.
   Toolbar header (profile switcher menu, super-admin New Industry) → left
   taxonomy nav with accuracy/suggestion badges → searchable base/custom item
   lists → edit in a Drawer (Field/Select primitives) → AI suggestions and
   quality notices as banners. Queries, mutations, the NewIndustryWizard,
   permission checks and i18n are unchanged from the pre-redesign page. */
import { useState, useMemo, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  getIndustryProfiles,
  getIndustryProfile,
  getTenantOverrides,
  updateTenantOverrides,
  getTaxonomySuggestions,
  getTaxonomySuggestionStats,
  approveTaxonomySuggestion,
  rejectTaxonomySuggestion,
  approveAllTaxonomySuggestions,
  setMyIndustryProfile,
  updateIndustryProfile,
  getExtractionQualityOverview,
  getTaxonomyAccuracy,
  getQualityHints,
} from '@/lib/api/admin'
import type { TaxonomySuggestionItem, TaxonomyAccuracyItem, QualityHint } from '@/lib/api/admin'
import { useTenantConfig } from '@/contexts/TenantConfigContext'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import NewIndustryWizard from '@/components/admin/NewIndustryWizard'
import {
  DocumentTextIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  ChartBarIcon,
  CheckCircleIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  InformationCircleIcon,
  LightBulbIcon,
  SwatchIcon,
  PlusIcon,
  TrashIcon,
  SparklesIcon,
  CheckIcon,
  XMarkIcon,
  BuildingOffice2Icon,
  PencilIcon,
  ArrowTopRightOnSquareIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'
import {
  Button,
  Drawer,
  EmptyState,
  Field,
  IconButton,
  Pill,
  Select,
  Tag,
} from '@/components/ui'
import type { PillTone } from '@/components/ui'

// ============================================================================
// Types
// ============================================================================

interface ProfileSummary {
  id: string
  name: string
  slug: string
  description: string | null
  contract_type_count: number
  clause_type_count: number
  risk_category_count: number
  sla_metric_count: number
  is_active: boolean
  tenant_default_count?: number
  contract_count?: number
}

interface ProfileDetail {
  id: string
  name: string
  slug: string
  description: string | null
  contract_types: Array<{ code: string; label: string; description?: string }>
  clause_types: Array<{ code: string; label: string; category?: string; risk_weight?: number }>
  risk_categories: Array<{ code: string; label: string; severity?: string; weight?: number; description?: string }>
  sla_metrics: Array<{ code: string; label: string; unit?: string; direction?: string; default_target?: number }>
  field_definitions: Record<string, unknown>
  extraction_hints: Record<string, string>
  ui_config: Record<string, unknown>
  is_active: boolean
}

interface TaxonomyItem {
  code: string
  label: string
  [key: string]: unknown
}

// ============================================================================
// Constants
// ============================================================================

const TABS = [
  { id: 'contract_types', label: 'Contract Types', icon: DocumentTextIcon },
  { id: 'clause_types', label: 'Clauses', icon: ShieldCheckIcon },
  { id: 'risk_categories', label: 'Risk', icon: ExclamationTriangleIcon },
  { id: 'sla_metrics', label: 'SLAs', icon: ChartBarIcon },
  { id: 'extraction_hints', label: 'AI Hints', icon: LightBulbIcon },
  { id: 'company_names', label: 'Company Names', icon: BuildingOffice2Icon },
] as const

type TabId = typeof TABS[number]['id']

// Fields config for the drawer edit form per tab
const TAB_FIELDS: Record<string, Array<{ key: string; label: string; placeholder: string; required?: boolean; type?: string }>> = {
  contract_types: [
    { key: 'code', label: 'Code', placeholder: 'e.g. supply_agreement', required: true },
    { key: 'label', label: 'Label', placeholder: 'e.g. Supply Agreement', required: true },
    { key: 'description', label: 'Description', placeholder: 'Agreement for supply of goods' },
  ],
  clause_types: [
    { key: 'code', label: 'Code', placeholder: 'e.g. product_recall', required: true },
    { key: 'label', label: 'Label', placeholder: 'e.g. Product Recall', required: true },
    { key: 'category', label: 'Category', placeholder: 'e.g. quality, risk, compliance' },
    { key: 'risk_weight', label: 'Risk Weight', placeholder: '1-10', type: 'number' },
  ],
  risk_categories: [
    { key: 'code', label: 'Code', placeholder: 'e.g. supply_disruption', required: true },
    { key: 'label', label: 'Label', placeholder: 'e.g. Supply Disruption', required: true },
    { key: 'severity', label: 'Severity', placeholder: 'critical, high, medium, low' },
    { key: 'weight', label: 'Weight', placeholder: '1-100', type: 'number' },
    { key: 'description', label: 'Description', placeholder: 'Risk of supply chain interruption' },
  ],
  sla_metrics: [
    { key: 'code', label: 'Code', placeholder: 'e.g. defect_ppm', required: true },
    { key: 'label', label: 'Label', placeholder: 'e.g. Defect Rate (PPM)', required: true },
    { key: 'unit', label: 'Unit', placeholder: 'percentage, days, ppm' },
    { key: 'direction', label: 'Direction', placeholder: 'higher_is_better or lower_is_better' },
    { key: 'default_target', label: 'Default Target', placeholder: '99.9', type: 'number' },
  ],
}

// ============================================================================
// AccuracyBadge
// ============================================================================

function accuracyTone(score: number): PillTone {
  return score >= 90 ? 'ok' : score >= 70 ? 'wa' : 'da'
}

function AccuracyBadge({ score, size = 'sm' }: { score: number | null | undefined; size?: 'sm' | 'md' }) {
  if (score == null) return null
  const tone = accuracyTone(score)
  if (size === 'md') {
    return (
      <Pill tone={tone} dot={false} className="num">
        {Math.round(score)}%
      </Pill>
    )
  }
  return (
    <span
      className="num"
      style={{ fontSize: 'var(--fs-2xs)', fontWeight: 700, color: `var(--${tone})`, flexShrink: 0 }}
    >
      {Math.round(score)}%
    </span>
  )
}

// ============================================================================
// Profile Selector (compact)
// ============================================================================

function ProfileSelector({
  profiles,
  currentSlug,
  onSwitch,
  isSuperAdmin,
}: {
  profiles: ProfileSummary[]
  currentSlug: string | null
  onSwitch: (slug: string) => void
  isSuperAdmin: boolean
}) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const current = profiles.find((p) => p.slug === currentSlug)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)} className="btn btn-s">
        <CheckCircleIcon style={{ width: 15, height: 15, color: 'var(--p)', flexShrink: 0 }} aria-hidden />
        <span>{current?.name || t('industry.noProfile')}</span>
        <ChevronDownIcon
          style={{ width: 14, height: 14, color: 'var(--f)', flexShrink: 0 }}
          className={cn('transition-transform', open && 'rotate-180')}
          aria-hidden
        />
      </button>
      {open && (
        <div className="menu scroll" style={{ top: '100%', right: 0, marginTop: 4, width: 288, maxHeight: 420 }}>
          {profiles.map((p) => (
            <button
              key={p.id}
              onClick={() => { onSwitch(p.slug); setOpen(false) }}
              className={cn(
                'col w-full text-left rounded-md transition-colors',
                p.slug === currentSlug ? 'bg-[var(--p-f)]' : 'bg-transparent hover:bg-[var(--s2)]'
              )}
              style={{ gap: 2, padding: '8px 10px', border: 0, cursor: 'pointer' }}
            >
              <span className="row" style={{ gap: 8 }}>
                <span className="grow trunc" style={{ fontSize: 'var(--fs-md)', fontWeight: 500, color: 'var(--t)' }}>
                  {p.name}
                </span>
                {p.slug === currentSlug && (
                  <CheckCircleIcon style={{ width: 15, height: 15, color: 'var(--p)', flexShrink: 0 }} aria-hidden />
                )}
              </span>
              {p.description && (
                <span className="faint trunc" style={{ fontSize: 'var(--fs-sm)' }}>{p.description}</span>
              )}
              <span className="row" style={{ gap: 10 }}>
                <span className="faint num" style={{ fontSize: 'var(--fs-2xs)' }}>
                  {t('industry.typesCount', { count: p.contract_type_count })}
                </span>
                <span className="faint num" style={{ fontSize: 'var(--fs-2xs)' }}>
                  {t('industry.clausesCount', { count: p.clause_type_count })}
                </span>
                <span className="faint num" style={{ fontSize: 'var(--fs-2xs)' }}>
                  {t('industry.slasCount', { count: p.sla_metric_count })}
                </span>
              </span>
              {/* Usage is a cross-tenant, super-admin-only concern */}
              {isSuperAdmin && ((p.tenant_default_count ?? 0) > 0 || (p.contract_count ?? 0) > 0) && (
                <span className="row" style={{ gap: 10 }}>
                  {(p.tenant_default_count ?? 0) > 0 && (
                    <span className="num" style={{ fontSize: 'var(--fs-2xs)', fontWeight: 600, color: 'var(--p)' }}>
                      {t('industry.usedByTenants', { count: p.tenant_default_count })}
                    </span>
                  )}
                  {(p.contract_count ?? 0) > 0 && (
                    <span className="num" style={{ fontSize: 'var(--fs-2xs)', fontWeight: 600, color: 'var(--p)' }}>
                      {t('industry.usedByContracts', { count: p.contract_count })}
                    </span>
                  )}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ============================================================================
// Item Edit Form (inside drawer)
// ============================================================================

function ItemEditForm({
  item,
  fields,
  tabId,
  onSave,
  onDelete,
  onCancel,
  isNew,
  accuracy,
}: {
  item: Record<string, unknown>
  fields: typeof TAB_FIELDS[string]
  tabId: string
  onSave: (item: TaxonomyItem) => void
  onDelete?: () => void
  onCancel: () => void
  isNew: boolean
  accuracy?: TaxonomyAccuracyItem
}) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState<Record<string, string>>(() => {
    const d: Record<string, string> = {}
    fields.forEach((f) => { d[f.key] = String(item[f.key] ?? '') })
    return d
  })

  const canSave = draft.code?.trim() && draft.label?.trim()

  const handleSave = () => {
    if (!canSave) return
    const result: TaxonomyItem = { code: '', label: '' }
    fields.forEach((f) => {
      let val: unknown = draft[f.key]?.trim()
      if (f.type === 'number' && val) val = Number(val)
      if (f.key === 'code' && isNew) val = String(val).toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '')
      if (val !== '' && val !== undefined) result[f.key] = val
    })
    onSave(result)
  }

  return (
    <div className="col" style={{ gap: 14 }}>
      {/* Accuracy info */}
      {accuracy && accuracy.total > 0 && (
        <div className="card card-p">
          <div className="row">
            <span className="sec-t">{t('industry.extractionAccuracy')}</span>
            <span className="grow" />
            <AccuracyBadge score={accuracy.accuracy} size="md" />
          </div>
          <div className="muted" style={{ fontSize: 'var(--fs-sm)', marginTop: 4 }}>
            {t('industry.verifiedCorrect', { correct: accuracy.correct, total: accuracy.total })}
          </div>
          {accuracy.accuracy < 70 && (
            <Link
              to={`/admin/extraction-quality?entity_type=clause&taxonomy_code=${item.code}`}
              style={{ fontSize: 'var(--fs-sm)', fontWeight: 500, color: 'var(--da)', display: 'inline-block', marginTop: 4 }}
            >
              {t('industry.reviewExtractions')}
            </Link>
          )}
        </div>
      )}

      {/* Fields */}
      {fields.map((f) =>
        f.key === 'direction' ? (
          <Select
            key={f.key}
            label={t(`industry.fields.${f.key}`, { defaultValue: f.label })}
            value={draft[f.key] || ''}
            onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))}
            options={[
              { value: '', label: '—' },
              { value: 'higher_is_better', label: t('industry.higherIsBetter') },
              { value: 'lower_is_better', label: t('industry.lowerIsBetter') },
            ]}
          />
        ) : (
          <Field
            key={f.key}
            label={`${t(`industry.fields.${f.key}`, { defaultValue: f.label })}${f.required ? ' *' : ''}`}
            type={f.type || 'text'}
            value={draft[f.key] || ''}
            onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSave() }}
            placeholder={t(`industry.ph.${tabId}.${f.key}`, { defaultValue: f.placeholder })}
            disabled={f.key === 'code' && !isNew}
            className={cn(f.key === 'code' && 'mono')}
          />
        )
      )}

      {/* Actions */}
      <div className="row" style={{ gap: 8, paddingTop: 14, borderTop: '1px solid var(--b)' }}>
        {onDelete && !isNew && (
          <Button variant="danger-ghost" icon={TrashIcon} onClick={onDelete}>
            {t('common.delete')}
          </Button>
        )}
        <span className="grow" />
        <Button variant="ghost" onClick={onCancel}>
          {t('common.cancel')}
        </Button>
        <Button variant="primary" disabled={!canSave} onClick={handleSave}>
          {isNew ? t('industry.add') : t('common.save')}
        </Button>
      </div>
    </div>
  )
}

// ============================================================================
// Suggestion Pill (compact inline)
// ============================================================================

function SuggestionPill({
  suggestion,
  onApprove,
  onReject,
  isProcessing,
}: {
  suggestion: TaxonomySuggestionItem
  onApprove: (id: string) => void
  onReject: (id: string) => void
  isProcessing: boolean
}) {
  const { t } = useTranslation()
  return (
    <div
      className="row"
      style={{
        gap: 6,
        padding: '3px 4px 3px 10px',
        background: 'var(--s)',
        border: '1px solid var(--wa-b)',
        borderRadius: 'var(--r-sm)',
      }}
    >
      <span
        className="grow trunc"
        style={{ fontSize: 'var(--fs-md)', fontWeight: 500, color: 'var(--t)' }}
        title={suggestion.code}
      >
        {suggestion.label}
      </span>
      <IconButton
        icon={CheckIcon}
        size="sm"
        label={t('industry.approve')}
        disabled={isProcessing}
        onClick={() => onApprove(suggestion.id)}
        style={{ color: 'var(--ok)', opacity: isProcessing ? 0.4 : undefined }}
      />
      <IconButton
        icon={XMarkIcon}
        size="sm"
        label={t('industry.reject')}
        disabled={isProcessing}
        onClick={() => onReject(suggestion.id)}
        style={{ color: 'var(--da)', opacity: isProcessing ? 0.4 : undefined }}
      />
    </div>
  )
}

// ============================================================================
// Compact Row for taxonomy items
// ============================================================================

function TaxonomyRow({
  item,
  onClick,
  accuracy,
  isCustom,
}: {
  item: TaxonomyItem
  onClick: () => void
  accuracy?: TaxonomyAccuracyItem
  isCustom?: boolean
}) {
  const { t } = useTranslation()
  const lowAccuracy = !isCustom && accuracy != null && accuracy.accuracy < 70
  return (
    <button
      onClick={onClick}
      className={cn(
        'row w-full text-left rounded-md border transition-colors',
        isCustom
          ? 'bg-[var(--p-f)] border-[var(--p-b)] hover:bg-[var(--p-f2)]'
          : 'bg-[var(--s)] border-[var(--b)] hover:bg-[var(--s2)]'
      )}
      style={{
        gap: 8,
        padding: '5px 10px',
        cursor: 'pointer',
        borderLeft: lowAccuracy ? '2px solid var(--da)' : undefined,
      }}
    >
      <span className="grow trunc" style={{ fontSize: 'var(--fs-sm)', fontWeight: 500, color: 'var(--t)' }}>
        {item.label}
      </span>
      {isCustom && <Tag>{t('industry.custom')}</Tag>}
      {accuracy && accuracy.total > 0 && <AccuracyBadge score={accuracy.accuracy} />}
      <ChevronRightIcon style={{ width: 13, height: 13, color: 'var(--f)', flexShrink: 0 }} aria-hidden />
    </button>
  )
}

// ============================================================================
// Collapsible Category Group
// ============================================================================

function CollapsibleGroup({
  label,
  count,
  children,
  defaultOpen = true,
}: {
  label: string
  count: number
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="row w-full text-left bg-transparent"
        style={{ gap: 6, padding: '4px 2px', border: 0, cursor: 'pointer' }}
      >
        <ChevronDownIcon
          style={{ width: 12, height: 12, color: 'var(--f)', flexShrink: 0 }}
          className={cn('transition-transform', !open && '-rotate-90')}
          aria-hidden
        />
        <span className="sec-t">{label}</span>
        <span className="faint num" style={{ fontSize: 'var(--fs-2xs)' }}>{count}</span>
      </button>
      {open && children}
    </div>
  )
}

// ============================================================================
// Extraction Hints Tab Content
// ============================================================================

function ExtractionHintsContent({
  baseHints,
  customHints,
  onSave,
  qualityHints,
}: {
  baseHints: Record<string, string>
  customHints: Record<string, string>
  onSave: (hints: Record<string, string>) => void
  qualityHints?: QualityHint[]
}) {
  const { t } = useTranslation()
  const [editKey, setEditKey] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [addMode, setAddMode] = useState(false)
  const [newKey, setNewKey] = useState('')
  const [newValue, setNewValue] = useState('')

  const allHints = { ...baseHints, ...customHints }
  const keys = Object.keys(allHints).sort()

  const handleSave = (key: string, value: string) => {
    onSave({ ...customHints, [key]: value })
    setEditKey(null)
  }

  const handleRemove = (key: string) => {
    const next = { ...customHints }
    delete next[key]
    onSave(next)
  }

  const handleAdd = () => {
    if (!newKey.trim() || !newValue.trim()) return
    onSave({ ...customHints, [newKey.trim()]: newValue.trim() })
    setNewKey('')
    setNewValue('')
    setAddMode(false)
  }

  return (
    <div className="col" style={{ gap: 14 }}>
      {/* Quality-driven hints banner */}
      {qualityHints && qualityHints.length > 0 && (
        <div className="banner banner-wa" style={{ flexDirection: 'column', gap: 6 }}>
          <div className="row" style={{ gap: 8 }}>
            <SparklesIcon style={{ width: 15, height: 15, flexShrink: 0 }} aria-hidden />
            <b style={{ fontSize: 'var(--fs-sm)' }}>
              {t('industry.suggestedImprovements', { count: qualityHints.length })}
            </b>
          </div>
          <div className="scroll" style={{ maxHeight: 256 }}>
            {qualityHints.map((h) => (
              <div key={h.code} className="row" style={{ gap: 8, padding: '5px 0', borderTop: '1px solid var(--wa-b)' }}>
                <span className="grow" style={{ minWidth: 0 }}>
                  <span style={{ fontSize: 'var(--fs-md)', color: 'var(--t)' }}>{h.label}</span>
                  <span className="num" style={{ fontSize: 'var(--fs-sm)', color: 'var(--da)', marginLeft: 8 }}>
                    {t('industry.accuracyPercent', { percent: Math.round(h.accuracy) })}
                  </span>
                </span>
                {h.suggested_hint && (
                  <Button
                    variant="ghost"
                    size="sm"
                    style={{ color: 'var(--p)' }}
                    onClick={() => { setEditKey(h.category); setEditValue(h.suggested_hint); handleSave(h.category, h.suggested_hint) }}
                  >
                    {t('industry.apply')}
                  </Button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Hint entries */}
      {keys.map((key) => {
        const isEditing = editKey === key
        const isCustom = key in customHints
        const value = allHints[key]

        return (
          <div
            key={key}
            className="card card-p"
            style={isCustom ? { borderColor: 'var(--p-b)', background: 'var(--p-f)' } : undefined}
          >
            <div className="row" style={{ gap: 8, marginBottom: 4 }}>
              <span className="sec-t" style={{ color: 'var(--m)' }}>{key.replace(/_/g, ' ')}</span>
              {isCustom && <Tag>{t('industry.custom')}</Tag>}
              <span className="grow" />
              <IconButton
                icon={PencilIcon}
                size="sm"
                label={t('common.edit')}
                onClick={() => { setEditKey(key); setEditValue(value) }}
              />
              {isCustom && (
                <IconButton
                  icon={TrashIcon}
                  size="sm"
                  label={t('common.delete')}
                  onClick={() => handleRemove(key)}
                  style={{ color: 'var(--da)' }}
                />
              )}
            </div>
            {isEditing ? (
              <div className="col" style={{ gap: 8 }}>
                <div className="inp" style={{ height: 'auto', padding: '8px 10px' }}>
                  <textarea
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    rows={4}
                    style={{ resize: 'vertical' }}
                    autoFocus
                  />
                </div>
                <div className="row" style={{ gap: 8 }}>
                  <Button variant="primary" size="sm" onClick={() => handleSave(key, editValue)}>
                    {t('common.save')}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setEditKey(null)}>
                    {t('common.cancel')}
                  </Button>
                </div>
              </div>
            ) : (
              <p className="muted line-clamp-3 whitespace-pre-wrap" style={{ fontSize: 'var(--fs-md)' }}>{value}</p>
            )}
          </div>
        )
      })}

      {/* Add new hint */}
      {addMode ? (
        <div className="card card-p col" style={{ gap: 10, borderColor: 'var(--p-b)' }}>
          <Field
            type="text"
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            placeholder={t('industry.agentKeyPlaceholder')}
            autoFocus
          />
          <div className="inp" style={{ height: 'auto', padding: '8px 10px' }}>
            <textarea
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              placeholder={t('industry.hintTextPlaceholder')}
              rows={3}
              style={{ resize: 'vertical' }}
            />
          </div>
          <div className="row" style={{ gap: 8 }}>
            <Button variant="primary" size="sm" disabled={!newKey.trim() || !newValue.trim()} onClick={handleAdd}>
              {t('industry.add')}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setAddMode(false)}>
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      ) : (
        <div>
          <Button variant="ghost" size="sm" icon={PlusIcon} style={{ color: 'var(--p)' }} onClick={() => setAddMode(true)}>
            {t('industry.addCustomHint')}
          </Button>
        </div>
      )}
    </div>
  )
}

// ============================================================================
// Company Names Tab Content
// ============================================================================

function CompanyNamesContent({
  aliases,
  onSave,
}: {
  aliases: string[]
  onSave: (aliases: string[]) => void
}) {
  const { t } = useTranslation()
  const [newName, setNewName] = useState('')

  const handleAdd = () => {
    const name = newName.trim()
    if (!name || aliases.includes(name)) return
    onSave([...aliases, name])
    setNewName('')
  }

  return (
    <div className="col" style={{ gap: 14 }}>
      <div className="banner banner-in">
        <InformationCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
        <span>{t('industry.companyNamesInfo')}</span>
      </div>

      {aliases.length > 0 ? (
        <div className="tbl-w">
          {aliases.map((name, i) => (
            <div
              key={name}
              className="row"
              style={{
                gap: 8,
                minHeight: 44,
                padding: '0 8px 0 12px',
                borderBottom: i < aliases.length - 1 ? '1px solid var(--b)' : undefined,
              }}
            >
              <BuildingOffice2Icon style={{ width: 15, height: 15, color: 'var(--f)', flexShrink: 0 }} aria-hidden />
              <span className="grow trunc" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>{name}</span>
              <IconButton
                icon={XMarkIcon}
                size="sm"
                label={t('common.delete')}
                onClick={() => onSave(aliases.filter((a) => a !== name))}
              />
            </div>
          ))}
        </div>
      ) : (
        <div className="card">
          <EmptyState icon={BuildingOffice2Icon} title={t('industry.noCompanyNames')} />
        </div>
      )}

      <div className="row" style={{ gap: 8, alignItems: 'flex-end' }}>
        <Field
          label={t('industry.addCompanyName')}
          type="text"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleAdd() }}
          placeholder={t('industry.companyNamePlaceholder')}
          containerClassName="grow"
        />
        <Button variant="primary" disabled={!newName.trim()} onClick={handleAdd}>
          {t('industry.add')}
        </Button>
      </div>
    </div>
  )
}

// ============================================================================
// Main Page
// ============================================================================

export default function IndustryProfilesPage() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState<TabId>('contract_types')
  const [search, setSearch] = useState('')
  const [slideOver, setSlideOver] = useState<{ item: TaxonomyItem; isNew: boolean; isCustom: boolean; isBase: boolean } | null>(null)
  const [showNewIndustry, setShowNewIndustry] = useState(false)
  const [viewSlug, setViewSlug] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const { config, refresh: refreshConfig } = useTenantConfig()
  const { isSuperAdmin } = useAuth()

  const currentSlug = config?.industry

  // Close the edit drawer on Escape (parity with the previous slide-over)
  useEffect(() => {
    if (!slideOver) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setSlideOver(null) }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [slideOver])

  // ── Data fetching ──────────────────────────────────────────
  const { data: profiles = [], isLoading: profilesLoading } = useQuery<ProfileSummary[]>({
    queryKey: ['industry-profiles'],
    queryFn: getIndustryProfiles,
  })

  // Super admin has no tenant profile — they browse/edit any profile directly
  const effectiveSlug = isSuperAdmin
    ? viewSlug ?? currentSlug ?? profiles[0]?.slug ?? null
    : currentSlug
  const currentProfileId = profiles.find((p) => p.slug === effectiveSlug)?.id

  const { data: profile, isLoading: profileLoading } = useQuery<ProfileDetail>({
    queryKey: ['industry-profile', currentProfileId],
    queryFn: () => getIndustryProfile(currentProfileId!),
    enabled: !!currentProfileId,
  })

  const { data: overrides } = useQuery({
    queryKey: ['tenant-overrides'],
    queryFn: getTenantOverrides,
  })

  const { data: suggestions = [] } = useQuery({
    queryKey: ['taxonomy-suggestions', 'pending'],
    queryFn: () => getTaxonomySuggestions('pending'),
  })

  const { data: stats } = useQuery({
    queryKey: ['taxonomy-suggestion-stats'],
    queryFn: getTaxonomySuggestionStats,
  })

  const { data: qualityOverview } = useQuery({
    queryKey: ['extraction-quality-overview'],
    queryFn: getExtractionQualityOverview,
  })

  const { data: taxonomyAccuracy } = useQuery({
    queryKey: ['taxonomy-accuracy'],
    queryFn: getTaxonomyAccuracy,
  })

  const { data: qualityHints } = useQuery({
    queryKey: ['quality-hints'],
    queryFn: getQualityHints,
  })

  // ── Mutations ──────────────────────────────────────────────
  const saveMutation = useMutation({
    mutationFn: updateTenantOverrides,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['tenant-overrides'] }); refreshConfig() },
  })

  const switchProfileMutation = useMutation({
    mutationFn: (slug: string) => setMyIndustryProfile(slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['industry-profiles'] })
      queryClient.invalidateQueries({ queryKey: ['industry-profile'] })
      refreshConfig()
    },
  })

  const approveMutation = useMutation({
    mutationFn: ({ id, mods }: { id: string; mods?: { label?: string } }) => approveTaxonomySuggestion(id, mods),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['taxonomy-suggestions'] })
      queryClient.invalidateQueries({ queryKey: ['taxonomy-suggestion-stats'] })
      queryClient.invalidateQueries({ queryKey: ['tenant-overrides'] })
      refreshConfig()
    },
  })

  const rejectMutation = useMutation({
    mutationFn: rejectTaxonomySuggestion,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['taxonomy-suggestions'] })
      queryClient.invalidateQueries({ queryKey: ['taxonomy-suggestion-stats'] })
    },
  })

  const approveAllMutation = useMutation({
    mutationFn: () => approveAllTaxonomySuggestions(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['taxonomy-suggestions'] })
      queryClient.invalidateQueries({ queryKey: ['taxonomy-suggestion-stats'] })
      queryClient.invalidateQueries({ queryKey: ['tenant-overrides'] })
      refreshConfig()
    },
  })

  const updateProfileMutation = useMutation({
    mutationFn: (updates: Record<string, unknown>) => updateIndustryProfile(currentProfileId!, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['industry-profile', currentProfileId] })
      queryClient.invalidateQueries({ queryKey: ['industry-profiles'] })
      refreshConfig()
    },
  })

  // ── Derived data ───────────────────────────────────────────
  const customContractTypes = (overrides?.contract_types || []) as TaxonomyItem[]
  const customClauseTypes = (overrides?.clause_types || []) as TaxonomyItem[]
  const customRiskCategories = (overrides?.risk_categories || []) as TaxonomyItem[]
  const customSlaMetrics = (overrides?.sla_metrics || []) as TaxonomyItem[]
  const customHints = (overrides?.extraction_hints || {}) as Record<string, string>
  const partyAliases = (overrides?.party_aliases || []) as string[]

  const pendingCount = stats?.pending || suggestions.length
  const tabSuggestions = suggestions.filter((s) => s.category === activeTab)

  // Get items for the current taxonomy tab
  const getTabData = (): { base: TaxonomyItem[]; custom: TaxonomyItem[]; accuracyMap?: Record<string, TaxonomyAccuracyItem> } => {
    switch (activeTab) {
      case 'contract_types':
        return { base: (profile?.contract_types || []) as TaxonomyItem[], custom: customContractTypes }
      case 'clause_types':
        return { base: (profile?.clause_types || []) as TaxonomyItem[], custom: customClauseTypes, accuracyMap: taxonomyAccuracy?.clause_types }
      case 'risk_categories':
        return { base: (profile?.risk_categories || []) as TaxonomyItem[], custom: customRiskCategories }
      case 'sla_metrics':
        return { base: (profile?.sla_metrics || []) as TaxonomyItem[], custom: customSlaMetrics, accuracyMap: taxonomyAccuracy?.sla_metric_types }
      default:
        return { base: [], custom: [] }
    }
  }

  const tabData = getTabData()

  // Filter by search
  const filterItems = (items: TaxonomyItem[]) => {
    if (!search.trim()) return items
    const q = search.toLowerCase()
    return items.filter((i) => i.label.toLowerCase().includes(q) || i.code.toLowerCase().includes(q))
  }

  // Group clause types by category
  const groupedBase = useMemo(() => {
    if (activeTab !== 'clause_types') return null
    const filtered = filterItems(tabData.base)
    const groups: Record<string, TaxonomyItem[]> = {}
    filtered.forEach((item) => {
      const cat = (item.category as string) || 'general'
      if (!groups[cat]) groups[cat] = []
      groups[cat].push(item)
    })
    return groups
  }, [activeTab, tabData.base, search])

  // ── Handlers ───────────────────────────────────────────────
  const handleSaveBase = (item: TaxonomyItem) => {
    const key = activeTab
    const baseItems = tabData.base
    const existingIdx = baseItems.findIndex((i) => i.code === item.code)
    const updatedItems = existingIdx >= 0
      ? baseItems.map((i) => i.code === item.code ? { ...i, ...item } : i)
      : [...baseItems, item]
    updateProfileMutation.mutate({ [key]: updatedItems })
    setSlideOver(null)
  }

  const handleDeleteBase = (code: string) => {
    const key = activeTab
    updateProfileMutation.mutate({ [key]: tabData.base.filter((i) => i.code !== code) })
    setSlideOver(null)
  }

  const handleSaveCustom = (item: TaxonomyItem) => {
    const key = activeTab
    const customItems = tabData.custom
    const existingIdx = customItems.findIndex((i) => i.code === item.code)
    const updatedItems = existingIdx >= 0
      ? customItems.map((i) => i.code === item.code ? { ...i, ...item } : i)
      : [...customItems, item]
    saveMutation.mutate({ [key]: updatedItems })
    setSlideOver(null)
  }

  const handleDeleteCustom = (code: string) => {
    const key = activeTab
    saveMutation.mutate({ [key]: tabData.custom.filter((i) => i.code !== code) })
    setSlideOver(null)
  }

  const isTaxonomyTab = ['contract_types', 'clause_types', 'risk_categories', 'sla_metrics'].includes(activeTab)

  // ── Loading ────────────────────────────────────────────────
  if (profilesLoading || profileLoading) {
    return (
      <div className="row" style={{ justifyContent: 'center', padding: '80px 0' }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="h-[calc(100vh-4rem)] col">
      {/* Header */}
      <div
        className="row"
        style={{
          gap: 12,
          padding: '12px 24px',
          borderBottom: '1px solid var(--b)',
          background: 'var(--s)',
          flexShrink: 0,
        }}
      >
        <SwatchIcon style={{ width: 22, height: 22, color: 'var(--p)', flexShrink: 0 }} aria-hidden />
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-xl)', fontWeight: 600, letterSpacing: '-.3px' }}>{t('industry.title')}</h1>
          <p className="faint" style={{ fontSize: 'var(--fs-sm)' }}>{t('industry.subtitle')}</p>
        </div>
        {isSuperAdmin && (
          <Button variant="primary" icon={PlusIcon} onClick={() => setShowNewIndustry(true)}>
            {t('industry.newIndustry')}
          </Button>
        )}
        <ProfileSelector
          profiles={profiles}
          currentSlug={effectiveSlug || null}
          isSuperAdmin={isSuperAdmin}
          onSwitch={(slug) =>
            isSuperAdmin ? setViewSlug(slug) : switchProfileMutation.mutate(slug)
          }
        />
      </div>

      {showNewIndustry && <NewIndustryWizard onClose={() => setShowNewIndustry(false)} />}

      {/* Main layout: sidebar + content */}
      <div className="row grow" style={{ gap: 0, alignItems: 'stretch', overflow: 'hidden' }}>
        {/* Sidebar */}
        <div
          className="col w-52 flex-shrink-0"
          style={{ borderRight: '1px solid var(--b)', background: 'var(--s3)' }}
        >
          <nav className="col grow" style={{ gap: 2, padding: '12px 8px' }}>
            {TABS.map((tab) => {
              const Icon = tab.icon
              const isActive = activeTab === tab.id
              const tabSugCount = suggestions.filter((s) => s.category === tab.id).length
              const tabScore = qualityOverview ? ({
                clause_types: qualityOverview.avg_clause_score,
                sla_metrics: qualityOverview.avg_sla_score,
                contract_types: qualityOverview.avg_metadata_score,
              } as Record<string, number | null>)[tab.id] ?? null : null

              return (
                <button
                  key={tab.id}
                  onClick={() => { setActiveTab(tab.id); setSearch('') }}
                  className={cn(
                    'row w-full text-left rounded-md transition-colors',
                    isActive ? 'bg-[var(--p-f)]' : 'bg-transparent hover:bg-[var(--s2)]'
                  )}
                  style={{
                    gap: 8,
                    height: 36,
                    padding: '0 10px',
                    border: 0,
                    cursor: 'pointer',
                    fontSize: 'var(--fs-md)',
                    fontWeight: isActive ? 600 : 500,
                    color: isActive ? 'var(--p)' : 'var(--m)',
                  }}
                >
                  <Icon
                    style={{ width: 15, height: 15, flexShrink: 0, color: isActive ? 'var(--p)' : 'var(--f)' }}
                    aria-hidden
                  />
                  <span className="grow trunc">{t(`industry.tabs.${tab.id}`, { defaultValue: tab.label })}</span>
                  <AccuracyBadge score={tabScore} />
                  {tabSugCount > 0 && (
                    <span className="pill pill-wa num" style={{ height: 16, padding: '0 5px', fontSize: 'var(--fs-2xs)' }}>
                      {tabSugCount}
                    </span>
                  )}
                </button>
              )
            })}
          </nav>

          {/* Sidebar footer: quality overview */}
          {qualityOverview?.avg_overall_score != null && (
            <div style={{ padding: '10px 12px', borderTop: '1px solid var(--b)' }}>
              <div className="row">
                <span className="sec-t grow">{t('industry.accuracy')}</span>
                <AccuracyBadge score={qualityOverview.avg_overall_score} size="md" />
              </div>
              <Link
                to="/admin/extraction-quality"
                className="row"
                style={{ gap: 4, fontSize: 'var(--fs-xs)', fontWeight: 500, marginTop: 4 }}
              >
                {t('industry.viewDetails')}
                <ArrowTopRightOnSquareIcon style={{ width: 12, height: 12 }} aria-hidden />
              </Link>
            </div>
          )}

          {/* Suggestion summary */}
          {pendingCount > 0 && (
            <div style={{ padding: '10px 12px', borderTop: '1px solid var(--b)' }}>
              <div className="row" style={{ gap: 6 }}>
                <SparklesIcon style={{ width: 14, height: 14, color: 'var(--wa)', flexShrink: 0 }} aria-hidden />
                <span className="muted grow trunc" style={{ fontSize: 'var(--fs-xs)', fontWeight: 600 }}>
                  {t('industry.suggestionsCount', { count: pendingCount })}
                </span>
                {suggestions.length > 1 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    style={{ color: 'var(--ok)', height: 22, padding: '0 6px', fontSize: 'var(--fs-2xs)' }}
                    onClick={() => approveAllMutation.mutate()}
                    disabled={approveAllMutation.isPending}
                  >
                    {t('industry.approveAll')}
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Content area */}
        <div className="grow scroll" style={{ alignSelf: 'stretch' }}>
          {isTaxonomyTab ? (
            <div className="p-6 max-w-4xl">
              {/* Search + Add */}
              <div className="row" style={{ gap: 10, marginBottom: 16 }}>
                <Field
                  icon={MagnifyingGlassIcon}
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={t('industry.searchPlaceholder', { items: t(`industry.tabs.${activeTab}`, { defaultValue: TABS.find((tab) => tab.id === activeTab)?.label ?? '' }).toLowerCase() })}
                  containerClassName="grow"
                />
                <Button
                  variant="primary"
                  icon={PlusIcon}
                  onClick={() => setSlideOver({ item: { code: '', label: '' }, isNew: true, isCustom: !isSuperAdmin, isBase: isSuperAdmin })}
                >
                  {t('industry.add')}
                </Button>
              </div>

              {/* Tab-specific suggestions — AI-proposed additions to review */}
              {tabSuggestions.length > 0 && (
                <div className="banner banner-wa" style={{ flexDirection: 'column', gap: 8, marginBottom: 16 }}>
                  <div className="row" style={{ gap: 6 }}>
                    <SparklesIcon style={{ width: 15, height: 15, flexShrink: 0 }} aria-hidden />
                    <span className="sec-t" style={{ color: 'inherit' }}>
                      {t('industry.aiSuggestions', { count: tabSuggestions.length })}
                    </span>
                  </div>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-1.5">
                    {tabSuggestions.map((s) => (
                      <SuggestionPill
                        key={s.id}
                        suggestion={s}
                        onApprove={(id) => approveMutation.mutate({ id })}
                        onReject={(id) => rejectMutation.mutate(id)}
                        isProcessing={approveMutation.isPending || rejectMutation.isPending}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Base items */}
              <div style={{ marginBottom: 24 }}>
                <h3 className="sec-t" style={{ marginBottom: 8 }}>
                  {t('industry.baseProfile', { count: filterItems(tabData.base).length })}
                </h3>

                {activeTab === 'clause_types' && groupedBase ? (
                  // Grouped by category for clauses — collapsible
                  <div className="col" style={{ gap: 4 }}>
                    {Object.entries(groupedBase).map(([category, items]) => (
                      <CollapsibleGroup key={category} label={category} count={items.length}>
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-1 pt-1">
                          {items.map((item) => (
                            <TaxonomyRow
                              key={item.code}
                              item={item}
                              onClick={() => { if (isSuperAdmin) setSlideOver({ item, isNew: false, isCustom: false, isBase: true }) }}
                              accuracy={tabData.accuracyMap?.[item.code]}
                            />
                          ))}
                        </div>
                      </CollapsibleGroup>
                    ))}
                  </div>
                ) : (
                  // 2-col grid for other tabs
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-1">
                    {filterItems(tabData.base).map((item) => (
                      <TaxonomyRow
                        key={item.code}
                        item={item}
                        onClick={() => { if (isSuperAdmin) setSlideOver({ item, isNew: false, isCustom: false, isBase: true }) }}
                        accuracy={tabData.accuracyMap?.[item.code]}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Custom items */}
              {filterItems(tabData.custom).length > 0 && (
                <div>
                  <h3 className="sec-t" style={{ marginBottom: 8, color: 'var(--p)' }}>
                    {t('industry.tenantCustom', { count: filterItems(tabData.custom).length })}
                  </h3>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-1">
                    {filterItems(tabData.custom).map((item) => (
                      <TaxonomyRow
                        key={item.code}
                        item={item}
                        onClick={() => setSlideOver({ item, isNew: false, isCustom: true, isBase: false })}
                        isCustom
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : activeTab === 'extraction_hints' ? (
            <div className="p-6 max-w-3xl">
              <ExtractionHintsContent
                baseHints={isSuperAdmin ? {} : profile?.extraction_hints || {}}
                customHints={isSuperAdmin ? profile?.extraction_hints || {} : customHints}
                onSave={(hints) =>
                  isSuperAdmin
                    ? updateProfileMutation.mutate({ extraction_hints: hints })
                    : saveMutation.mutate({ extraction_hints: hints })
                }
                qualityHints={qualityHints}
              />
            </div>
          ) : activeTab === 'company_names' ? (
            <div className="p-6 max-w-3xl">
              <CompanyNamesContent
                aliases={partyAliases}
                onSave={(aliases) => saveMutation.mutate({ party_aliases: aliases })}
              />
            </div>
          ) : null}
        </div>
      </div>

      {/* Edit drawer */}
      <Drawer
        open={!!slideOver}
        onClose={() => setSlideOver(null)}
        width={448}
        title={slideOver?.isNew ? t(`industry.addItem.${activeTab}`, { defaultValue: `Add ${TABS.find((tab) => tab.id === activeTab)?.label.replace(/s$/, '') || 'Item'}` }) : (slideOver?.item.label || t('common.edit'))}
        sub={slideOver && !slideOver.isNew ? slideOver.item.code : undefined}
      >
        {slideOver && TAB_FIELDS[activeTab] && (
          <ItemEditForm
            item={slideOver.item as Record<string, unknown>}
            fields={TAB_FIELDS[activeTab]}
            tabId={activeTab}
            isNew={slideOver.isNew}
            accuracy={tabData.accuracyMap?.[slideOver.item.code]}
            onSave={(item) => {
              if (slideOver.isBase) handleSaveBase(item)
              else handleSaveCustom(item)
            }}
            onDelete={slideOver.isNew ? undefined : () => {
              if (slideOver.isCustom) handleDeleteCustom(slideOver.item.code)
              else handleDeleteBase(slideOver.item.code)
            }}
            onCancel={() => setSlideOver(null)}
          />
        )}
      </Drawer>

      {/* Error banner */}
      {(saveMutation.isError || updateProfileMutation.isError) && (
        <div
          className="banner banner-da"
          style={{ position: 'fixed', bottom: 16, right: 16, zIndex: 90, boxShadow: 'var(--sh-lg)', maxWidth: 380 }}
        >
          <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
          <span>
            {(saveMutation.error as Error)?.message || (updateProfileMutation.error as Error)?.message || t('industry.failedToSave')}
          </span>
        </div>
      )}
    </div>
  )
}
