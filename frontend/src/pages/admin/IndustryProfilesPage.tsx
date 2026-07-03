import { useState, useMemo, useEffect, useRef } from 'react'
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

// Fields config for the slide-over edit form per tab
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

function AccuracyBadge({ score, size = 'sm' }: { score: number | null | undefined; size?: 'sm' | 'md' }) {
  if (score == null) return null
  const color = score >= 90 ? 'bg-green-100 text-green-700' : score >= 70 ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'
  const sizeClass = size === 'md' ? 'px-2 py-0.5 text-xs' : 'px-1.5 py-0.5 text-[10px]'
  return <span className={cn('font-semibold rounded-full', color, sizeClass)}>{Math.round(score)}%</span>
}

// ============================================================================
// Profile Selector (compact)
// ============================================================================

function ProfileSelector({
  profiles,
  currentSlug,
  onSwitch,
}: {
  profiles: ProfileSummary[]
  currentSlug: string | null
  onSwitch: (slug: string) => void
}) {
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
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-lg hover:border-gray-300 transition-colors text-sm"
      >
        <CheckCircleIcon className="h-4 w-4 text-violet-500" />
        <span className="font-medium text-gray-900">{current?.name || 'No profile'}</span>
        <ChevronDownIcon className={cn('h-4 w-4 text-gray-400 transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="absolute top-full right-0 mt-1 w-72 bg-white border border-gray-200 rounded-lg shadow-lg z-30 py-1">
          {profiles.map((p) => (
            <button
              key={p.id}
              onClick={() => { onSwitch(p.slug); setOpen(false) }}
              className={cn('w-full text-left px-4 py-2.5 hover:bg-gray-50', p.slug === currentSlug && 'bg-violet-50')}
            >
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium text-gray-900">{p.name}</div>
                {p.slug === currentSlug && <CheckCircleIcon className="h-4 w-4 text-violet-500" />}
              </div>
              <div className="text-xs text-gray-500">{p.description}</div>
              <div className="flex gap-3 mt-1">
                <span className="text-[10px] text-gray-400">{p.contract_type_count} types</span>
                <span className="text-[10px] text-gray-400">{p.clause_type_count} clauses</span>
                <span className="text-[10px] text-gray-400">{p.sla_metric_count} SLAs</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ============================================================================
// Slide-Over Panel
// ============================================================================

function SlideOver({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
}) {
  useEffect(() => {
    if (open) {
      const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
      document.addEventListener('keydown', handler)
      return () => document.removeEventListener('keydown', handler)
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/20 z-40" onClick={onClose} />
      {/* Panel */}
      <div className="fixed inset-y-0 right-0 w-full max-w-md bg-white shadow-2xl z-50 flex flex-col animate-in slide-in-from-right duration-200">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
          <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100">
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {children}
        </div>
      </div>
    </>
  )
}

// ============================================================================
// Item Edit Form (inside slide-over)
// ============================================================================

function ItemEditForm({
  item,
  fields,
  onSave,
  onDelete,
  onCancel,
  isNew,
  accuracy,
}: {
  item: Record<string, unknown>
  fields: typeof TAB_FIELDS[string]
  onSave: (item: TaxonomyItem) => void
  onDelete?: () => void
  onCancel: () => void
  isNew: boolean
  accuracy?: TaxonomyAccuracyItem
}) {
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
    <div className="space-y-5">
      {/* Accuracy info */}
      {accuracy && accuracy.total > 0 && (
        <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-600">Extraction Accuracy</span>
            <AccuracyBadge score={accuracy.accuracy} size="md" />
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {accuracy.correct}/{accuracy.total} verified correct
          </div>
          {accuracy.accuracy < 70 && (
            <Link
              to={`/admin/extraction-quality?entity_type=clause&taxonomy_code=${item.code}`}
              className="text-xs text-red-600 hover:text-red-700 font-medium mt-1 inline-block"
            >
              Review extractions →
            </Link>
          )}
        </div>
      )}

      {/* Fields */}
      {fields.map((f) => (
        <div key={f.key}>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            {f.label} {f.required && <span className="text-red-400">*</span>}
          </label>
          {f.key === 'direction' ? (
            <select
              value={draft[f.key] || ''}
              onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-400"
            >
              <option value="">—</option>
              <option value="higher_is_better">Higher is better</option>
              <option value="lower_is_better">Lower is better</option>
            </select>
          ) : (
            <input
              type={f.type || 'text'}
              value={draft[f.key] || ''}
              onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSave() }}
              placeholder={f.placeholder}
              disabled={f.key === 'code' && !isNew}
              className={cn(
                'w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-400',
                f.key === 'code' && !isNew && 'bg-gray-50 text-gray-500'
              )}
            />
          )}
        </div>
      ))}

      {/* Actions */}
      <div className="flex items-center justify-between pt-4 border-t border-gray-200">
        <div>
          {onDelete && !isNew && (
            <button
              onClick={onDelete}
              className="flex items-center gap-1.5 px-3 py-2 text-sm text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors"
            >
              <TrashIcon className="h-4 w-4" />
              Delete
            </button>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={onCancel} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!canSave}
            className="px-4 py-2 text-sm font-medium bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-40 transition-colors"
          >
            {isNew ? 'Add' : 'Save'}
          </button>
        </div>
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
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-amber-50 border border-amber-200 rounded-full text-sm">
      <SparklesIcon className="h-3.5 w-3.5 text-amber-500 flex-shrink-0" />
      <span className="font-medium text-gray-800 truncate">{suggestion.label}</span>
      <span className="text-[10px] text-gray-400 font-mono">{suggestion.code}</span>
      <button
        onClick={() => onApprove(suggestion.id)}
        disabled={isProcessing}
        className="p-0.5 text-green-600 hover:bg-green-100 rounded disabled:opacity-40"
        title="Approve"
      >
        <CheckIcon className="h-3.5 w-3.5" />
      </button>
      <button
        onClick={() => onReject(suggestion.id)}
        disabled={isProcessing}
        className="p-0.5 text-red-500 hover:bg-red-100 rounded disabled:opacity-40"
        title="Reject"
      >
        <XMarkIcon className="h-3.5 w-3.5" />
      </button>
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
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-2 px-3 py-1.5 text-left rounded border transition-all',
        'hover:border-violet-300 hover:bg-violet-50/30',
        isCustom
          ? 'bg-violet-50/30 border-violet-100'
          : accuracy && accuracy.accuracy < 70
            ? 'bg-white border-l-2 border-l-red-400 border-gray-100'
            : 'bg-white border-gray-100'
      )}
    >
      <span className="text-[13px] font-medium text-gray-900 truncate flex-1">{item.label}</span>
      {isCustom && (
        <span className="text-[8px] font-semibold uppercase px-1 py-px rounded bg-violet-100 text-violet-600 flex-shrink-0">custom</span>
      )}
      {accuracy && accuracy.total > 0 && <AccuracyBadge score={accuracy.accuracy} />}
      <ChevronDownIcon className="h-3.5 w-3.5 text-gray-300 -rotate-90 flex-shrink-0" />
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
        className="flex items-center gap-1.5 w-full py-1 px-1 text-left group"
      >
        <ChevronDownIcon className={cn('h-3 w-3 text-gray-400 transition-transform', !open && '-rotate-90')} />
        <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 group-hover:text-gray-600">{label}</span>
        <span className="text-[10px] text-gray-300">{count}</span>
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
    <div className="space-y-4">
      {/* Quality-driven hints banner */}
      {qualityHints && qualityHints.length > 0 && (
        <div className="p-3 bg-amber-50 rounded-lg border border-amber-200">
          <div className="flex items-center gap-2 mb-2">
            <SparklesIcon className="h-4 w-4 text-amber-500" />
            <span className="text-xs font-semibold text-gray-700">
              Suggested improvements based on extraction quality ({qualityHints.length})
            </span>
          </div>
          <div className="max-h-64 overflow-y-auto">
          {qualityHints.map((h) => (
            <div key={h.code} className="flex items-center justify-between py-1.5 border-t border-amber-100">
              <div>
                <span className="text-sm text-gray-800">{h.label}</span>
                <span className="text-xs text-red-500 ml-2">{Math.round(h.accuracy)}% accuracy</span>
              </div>
              {h.suggested_hint && (
                <button
                  onClick={() => { setEditKey(h.category); setEditValue(h.suggested_hint); handleSave(h.category, h.suggested_hint) }}
                  className="text-xs text-violet-600 hover:text-violet-800 font-medium"
                >
                  Apply
                </button>
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
          <div key={key} className={cn('rounded-lg border p-3', isCustom ? 'border-violet-200 bg-violet-50/30' : 'border-gray-200 bg-white')}>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-gray-700 uppercase">{key.replace(/_/g, ' ')}</span>
                {isCustom && <span className="text-[9px] font-semibold uppercase px-1.5 py-0.5 rounded bg-violet-100 text-violet-600">custom</span>}
              </div>
              <div className="flex items-center gap-1">
                <button onClick={() => { setEditKey(key); setEditValue(value) }} className="p-1 text-gray-400 hover:text-blue-600">
                  <PencilIcon className="h-3.5 w-3.5" />
                </button>
                {isCustom && (
                  <button onClick={() => handleRemove(key)} className="p-1 text-gray-400 hover:text-red-500">
                    <TrashIcon className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            </div>
            {isEditing ? (
              <div className="space-y-2">
                <textarea
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  rows={4}
                  className="w-full px-3 py-2 text-sm border border-violet-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-400"
                  autoFocus
                />
                <div className="flex items-center gap-2">
                  <button onClick={() => handleSave(key, editValue)} className="px-3 py-1.5 text-xs bg-violet-600 text-white rounded-lg hover:bg-violet-700">
                    Save
                  </button>
                  <button onClick={() => setEditKey(null)} className="px-3 py-1.5 text-xs text-gray-600 hover:text-gray-800">
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-600 whitespace-pre-wrap line-clamp-3">{value}</p>
            )}
          </div>
        )
      })}

      {/* Add new hint */}
      {addMode ? (
        <div className="p-3 bg-violet-50 rounded-lg border border-violet-200 space-y-2">
          <input
            type="text"
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            placeholder="Agent key (e.g. clause_extraction)"
            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-400"
            autoFocus
          />
          <textarea
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            placeholder="Extraction hint text..."
            rows={3}
            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-400"
          />
          <div className="flex items-center gap-2">
            <button onClick={handleAdd} disabled={!newKey.trim() || !newValue.trim()} className="px-3 py-1.5 text-xs bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-40">
              Add
            </button>
            <button onClick={() => setAddMode(false)} className="px-3 py-1.5 text-xs text-gray-600">Cancel</button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setAddMode(true)}
          className="flex items-center gap-1.5 text-sm text-violet-600 hover:text-violet-800 font-medium"
        >
          <PlusIcon className="h-4 w-4" /> Add Custom Hint
        </button>
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
  const [newName, setNewName] = useState('')

  const handleAdd = () => {
    const name = newName.trim()
    if (!name || aliases.includes(name)) return
    onSave([...aliases, name])
    setNewName('')
  }

  return (
    <div className="space-y-4">
      <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
        <p className="text-sm text-blue-700">
          Add legal entity names, subsidiaries, and DBAs so the AI correctly identifies counterparties in your contracts.
        </p>
      </div>

      {aliases.length > 0 ? (
        <div className="space-y-1">
          {aliases.map((name) => (
            <div key={name} className="flex items-center justify-between px-3 py-2.5 bg-white rounded-lg border border-gray-100 hover:border-gray-300 transition-colors">
              <div className="flex items-center gap-2">
                <BuildingOffice2Icon className="h-4 w-4 text-gray-400" />
                <span className="text-sm font-medium text-gray-900">{name}</span>
              </div>
              <button onClick={() => onSave(aliases.filter((a) => a !== name))} className="p-1 text-gray-400 hover:text-red-500">
                <XMarkIcon className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="p-8 text-center bg-gray-50 rounded-lg border border-dashed border-gray-300">
          <BuildingOffice2Icon className="h-8 w-8 mx-auto text-gray-300 mb-2" />
          <p className="text-sm text-gray-500">No company names configured.</p>
        </div>
      )}

      <div className="flex items-end gap-2">
        <div className="flex-1">
          <label className="block text-xs font-medium text-gray-600 mb-1">Add Company Name</label>
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleAdd() }}
            placeholder="e.g. Vialto Partners, Galaxy US OpCo Inc."
            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-400"
          />
        </div>
        <button onClick={handleAdd} disabled={!newName.trim()} className="px-4 py-2 text-sm font-medium bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-40">
          Add
        </button>
      </div>
    </div>
  )
}

// ============================================================================
// Main Page
// ============================================================================

export default function IndustryProfilesPage() {
  const [activeTab, setActiveTab] = useState<TabId>('contract_types')
  const [search, setSearch] = useState('')
  const [slideOver, setSlideOver] = useState<{ item: TaxonomyItem; isNew: boolean; isCustom: boolean; isBase: boolean } | null>(null)
  const [showNewIndustry, setShowNewIndustry] = useState(false)
  const [viewSlug, setViewSlug] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const { config, refresh: refreshConfig } = useTenantConfig()
  const { isSuperAdmin } = useAuth()

  const currentSlug = config?.industry

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
    return <div className="flex items-center justify-center py-20"><LoadingSpinner size="lg" /></div>
  }

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white flex-shrink-0">
        <div className="flex items-center gap-3">
          <SwatchIcon className="h-6 w-6 text-violet-500" />
          <div>
            <h1 className="text-lg font-bold text-gray-900">Industry Profile</h1>
            <p className="text-xs text-gray-500">Configure extraction taxonomy and AI behavior</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isSuperAdmin && (
            <button
              onClick={() => setShowNewIndustry(true)}
              className="btn-primary text-sm flex items-center gap-1.5"
            >
              <PlusIcon className="h-4 w-4" />
              New Industry
            </button>
          )}
          <ProfileSelector
            profiles={profiles}
            currentSlug={effectiveSlug || null}
            onSwitch={(slug) =>
              isSuperAdmin ? setViewSlug(slug) : switchProfileMutation.mutate(slug)
            }
          />
        </div>
      </div>

      {showNewIndustry && <NewIndustryWizard onClose={() => setShowNewIndustry(false)} />}

      {/* Main layout: sidebar + content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <div className="w-52 flex-shrink-0 border-r border-gray-200 bg-gray-50 flex flex-col">
          <nav className="flex-1 py-3 px-2 space-y-0.5">
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
                    'w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm transition-colors',
                    isActive
                      ? 'bg-violet-100 text-violet-800 font-semibold'
                      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                  )}
                >
                  <Icon className={cn('h-4 w-4 flex-shrink-0', isActive ? 'text-violet-600' : 'text-gray-400')} />
                  <span className="flex-1 text-left truncate">{tab.label}</span>
                  <div className="flex items-center gap-1">
                    <AccuracyBadge score={tabScore} />
                    {tabSugCount > 0 && (
                      <span className="flex h-4 w-4 items-center justify-center rounded-full bg-amber-500 text-[9px] font-bold text-white">
                        {tabSugCount}
                      </span>
                    )}
                  </div>
                </button>
              )
            })}
          </nav>

          {/* Sidebar footer: quality overview */}
          {qualityOverview?.avg_overall_score != null && (
            <div className="px-3 py-3 border-t border-gray-200">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-semibold uppercase text-gray-400">Accuracy</span>
                <AccuracyBadge score={qualityOverview.avg_overall_score} size="md" />
              </div>
              <Link
                to="/admin/extraction-quality"
                className="flex items-center gap-1 text-[11px] text-violet-600 hover:text-violet-800 font-medium mt-1"
              >
                View Details <ArrowTopRightOnSquareIcon className="h-3 w-3" />
              </Link>
            </div>
          )}

          {/* Suggestion summary */}
          {pendingCount > 0 && (
            <div className="px-3 py-3 border-t border-gray-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <SparklesIcon className="h-3.5 w-3.5 text-amber-500" />
                  <span className="text-[11px] font-semibold text-gray-600">{pendingCount} suggestions</span>
                </div>
                {suggestions.length > 1 && (
                  <button
                    onClick={() => approveAllMutation.mutate()}
                    disabled={approveAllMutation.isPending}
                    className="text-[10px] text-green-600 hover:text-green-800 font-medium disabled:opacity-40"
                  >
                    Approve All
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Content area */}
        <div className="flex-1 overflow-y-auto">
          {isTaxonomyTab ? (
            <div className="p-6 max-w-4xl">
              {/* Search + Add */}
              <div className="flex items-center gap-3 mb-4">
                <div className="relative flex-1">
                  <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder={`Search ${TABS.find((t) => t.id === activeTab)?.label.toLowerCase()}...`}
                    className="w-full pl-9 pr-4 py-2 text-sm bg-white border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-200 focus:border-violet-400"
                  />
                </div>
                <button
                  onClick={() => setSlideOver({ item: { code: '', label: '' }, isNew: true, isCustom: !isSuperAdmin, isBase: isSuperAdmin })}
                  className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-violet-600 text-white rounded-lg hover:bg-violet-700 transition-colors"
                >
                  <PlusIcon className="h-4 w-4" />
                  Add
                </button>
              </div>

              {/* Tab-specific suggestions */}
              {tabSuggestions.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-4">
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
              )}

              {/* Base items */}
              <div className="mb-6">
                <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 mb-2">
                  Base Profile ({filterItems(tabData.base).length})
                </h3>

                {activeTab === 'clause_types' && groupedBase ? (
                  // Grouped by category for clauses — collapsible
                  <div className="space-y-1">
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
                  <h3 className="text-[11px] font-semibold uppercase tracking-wider text-violet-500 mb-2">
                    Tenant Custom ({filterItems(tabData.custom).length})
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

      {/* Slide-over panel */}
      <SlideOver
        open={!!slideOver}
        onClose={() => setSlideOver(null)}
        title={slideOver?.isNew ? `Add ${TABS.find((t) => t.id === activeTab)?.label.replace(/s$/, '') || 'Item'}` : (slideOver?.item.label || 'Edit')}
      >
        {slideOver && TAB_FIELDS[activeTab] && (
          <ItemEditForm
            item={slideOver.item as Record<string, unknown>}
            fields={TAB_FIELDS[activeTab]}
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
      </SlideOver>

      {/* Error banner */}
      {(saveMutation.isError || updateProfileMutation.isError) && (
        <div className="fixed bottom-4 right-4 p-3 bg-red-50 border border-red-200 rounded-lg shadow-lg z-50">
          <p className="text-xs text-red-600">
            {(saveMutation.error as Error)?.message || (updateProfileMutation.error as Error)?.message || 'Failed to save'}
          </p>
        </div>
      )}
    </div>
  )
}
