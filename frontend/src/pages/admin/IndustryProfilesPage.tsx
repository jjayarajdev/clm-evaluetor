import { useState } from 'react'
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
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import {
  DocumentTextIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  ChartBarIcon,
  CheckCircleIcon,
  ChevronDownIcon,
  TagIcon,
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
} from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'

// ============================================================================
// Accuracy Badge
// ============================================================================

function AccuracyBadge({ score, size = 'sm' }: { score: number | null | undefined; size?: 'sm' | 'md' }) {
  if (score == null) return null
  const color = score >= 90 ? 'bg-green-100 text-green-700' : score >= 70 ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'
  const sizeClass = size === 'md' ? 'px-2.5 py-1 text-sm' : 'px-1.5 py-0.5 text-[10px]'
  return <span className={cn('font-semibold rounded-full', color, sizeClass)}>{Math.round(score)}%</span>
}

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
// Tab definitions
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

// ============================================================================
// Suggestion Card
// ============================================================================

function SuggestionCard({
  suggestion,
  onApprove,
  onReject,
  isProcessing,
}: {
  suggestion: TaxonomySuggestionItem
  onApprove: (id: string, mods?: { label?: string }) => void
  onReject: (id: string) => void
  isProcessing: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [editLabel, setEditLabel] = useState(suggestion.label)

  const categoryColors: Record<string, string> = {
    contract_types: 'bg-blue-50 border-blue-200 text-blue-700',
    clause_types: 'bg-green-50 border-green-200 text-green-700',
    risk_categories: 'bg-red-50 border-red-200 text-red-700',
    sla_metrics: 'bg-amber-50 border-amber-200 text-amber-700',
  }

  return (
    <div className="flex items-center justify-between gap-3 p-2.5 bg-white rounded-lg border border-amber-200">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={cn('text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded border', categoryColors[suggestion.category] || 'bg-gray-50 text-gray-600')}>
            {suggestion.category.replace('_', ' ')}
          </span>
          <span className="text-[10px] text-gray-400">{Math.round(suggestion.confidence * 100)}%</span>
        </div>
        {editing ? (
          <input
            type="text"
            value={editLabel}
            onChange={(e) => setEditLabel(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') { onApprove(suggestion.id, { label: editLabel }); setEditing(false) }
              if (e.key === 'Escape') setEditing(false)
            }}
            className="w-full mt-1 px-2 py-1 text-sm border border-violet-300 rounded focus:outline-none focus:ring-1 focus:ring-violet-400"
            autoFocus
          />
        ) : (
          <button onClick={() => setEditing(true)} className="text-sm font-medium text-gray-900 hover:text-violet-600 mt-0.5 text-left block">
            {suggestion.label}
          </button>
        )}
        <span className="text-[10px] text-gray-400 font-mono">{suggestion.code}</span>
      </div>
      <div className="flex items-center gap-1 flex-shrink-0">
        <button
          onClick={() => onApprove(suggestion.id, editLabel !== suggestion.label ? { label: editLabel } : undefined)}
          disabled={isProcessing}
          className="p-1.5 rounded bg-green-50 text-green-600 hover:bg-green-100 disabled:opacity-40"
          title="Approve"
        >
          <CheckIcon className="h-4 w-4" />
        </button>
        <button
          onClick={() => onReject(suggestion.id)}
          disabled={isProcessing}
          className="p-1.5 rounded bg-red-50 text-red-600 hover:bg-red-100 disabled:opacity-40"
          title="Reject"
        >
          <XMarkIcon className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

// ============================================================================
// Taxonomy Add Form
// ============================================================================

function TaxonomyAddForm({
  fields,
  onAdd,
  onCancel,
}: {
  fields: Array<{ key: string; label: string; placeholder: string; required?: boolean }>
  onAdd: (item: TaxonomyItem) => void
  onCancel: () => void
}) {
  const [formData, setFormData] = useState<Record<string, string>>({})

  const handleSubmit = () => {
    if (!formData.code?.trim() || !formData.label?.trim()) return
    const item: TaxonomyItem = {
      code: formData.code.trim().toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, ''),
      label: formData.label.trim(),
    }
    for (const f of fields) {
      if (f.key !== 'code' && f.key !== 'label' && formData[f.key]) {
        item[f.key] = formData[f.key].trim()
      }
    }
    onAdd(item)
  }

  return (
    <div className="p-3 bg-violet-50 rounded-lg border border-violet-200">
      <div className="grid grid-cols-2 gap-2">
        {fields.map((f) => (
          <div key={f.key}>
            <label className="block text-[10px] font-medium text-gray-500 mb-0.5">
              {f.label} {f.required && '*'}
            </label>
            <input
              type="text"
              placeholder={f.placeholder}
              value={formData[f.key] || ''}
              onChange={(e) => setFormData((d) => ({ ...d, [f.key]: e.target.value }))}
              className="w-full px-2 py-1.5 text-xs border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-violet-400"
            />
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2 mt-2">
        <button
          onClick={handleSubmit}
          disabled={!formData.code?.trim() || !formData.label?.trim()}
          className="px-3 py-1 text-xs bg-violet-600 text-white rounded hover:bg-violet-700 disabled:opacity-40"
        >
          Add
        </button>
        <button onClick={onCancel} className="px-3 py-1 text-xs text-gray-600 hover:text-gray-800">
          Cancel
        </button>
      </div>
    </div>
  )
}

// ============================================================================
// Editable Base Item — click to edit label/description, with delete
// ============================================================================

function EditableBaseItem({
  item,
  editableFields,
  onUpdate,
  onDelete,
  children,
}: {
  item: TaxonomyItem
  editableFields: Array<{ key: string; label: string }>
  onUpdate: (updated: TaxonomyItem) => void
  onDelete: () => void
  children?: React.ReactNode
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<Record<string, string>>({})

  const startEdit = () => {
    const d: Record<string, string> = {}
    editableFields.forEach((f) => { d[f.key] = String(item[f.key] ?? '') })
    setDraft(d)
    setEditing(true)
  }

  const handleSave = () => {
    const updated = { ...item }
    editableFields.forEach((f) => {
      const val = draft[f.key]?.trim()
      if (val !== undefined) updated[f.key] = val
    })
    onUpdate(updated)
    setEditing(false)
  }

  if (editing) {
    return (
      <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
        <div className="space-y-2">
          {editableFields.map((f) => (
            <div key={f.key}>
              <label className="block text-[10px] font-medium text-gray-500 mb-0.5">{f.label}</label>
              <input
                type="text"
                value={draft[f.key] || ''}
                onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))}
                onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') setEditing(false) }}
                autoFocus={f.key === editableFields[0].key}
                className="w-full px-2 py-1.5 text-xs border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
          ))}
        </div>
        <div className="flex items-center gap-2 mt-2">
          <button onClick={handleSave} className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700">Save</button>
          <button onClick={() => setEditing(false)} className="px-3 py-1 text-xs text-gray-600 hover:text-gray-800">Cancel</button>
        </div>
      </div>
    )
  }

  return (
    <div className="group flex items-start justify-between p-3 bg-gray-50 rounded-lg border border-gray-100 hover:border-gray-300 transition-colors">
      <div className="flex items-start gap-2 flex-1 min-w-0">
        {children}
      </div>
      <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 ml-2">
        <button onClick={startEdit} className="p-1 text-gray-400 hover:text-blue-600" title="Edit">
          <PencilIcon className="h-3.5 w-3.5" />
        </button>
        <button onClick={onDelete} className="p-1 text-gray-400 hover:text-red-500" title="Delete">
          <TrashIcon className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}

// ============================================================================
// Contract Types Tab
// ============================================================================

function ContractTypesTab({
  baseItems,
  customItems,
  onRemove,
  onUpdateBase,
  onRemoveBase,
  accuracy,
}: {
  baseItems: ProfileDetail['contract_types']
  customItems: TaxonomyItem[]
  onRemove: (code: string) => void
  onUpdateBase: (items: ProfileDetail['contract_types']) => void
  onRemoveBase: (code: string) => void
  accuracy?: Record<string, TaxonomyAccuracyItem>
}) {
  const [showForm, setShowForm] = useState(false)

  return (
    <div className="space-y-6">
      {/* Base profile items */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400">
            Base Profile ({baseItems.length})
          </h3>
          <button
            onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-1 text-xs text-violet-600 hover:text-violet-800 font-medium"
          >
            <PlusIcon className="h-3.5 w-3.5" /> Add
          </button>
        </div>

        {showForm && (
          <div className="mb-3">
            <TaxonomyAddForm
              fields={[
                { key: 'code', label: 'Code', placeholder: 'e.g. supply_agreement', required: true },
                { key: 'label', label: 'Label', placeholder: 'e.g. Supply Agreement', required: true },
                { key: 'description', label: 'Description', placeholder: 'Agreement for supply of goods' },
              ]}
              onAdd={(item) => {
                onUpdateBase([...baseItems, item as ProfileDetail['contract_types'][0]])
                setShowForm(false)
              }}
              onCancel={() => setShowForm(false)}
            />
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {baseItems.map((t) => {
            const acc = accuracy?.[t.code]
            return (
              <EditableBaseItem
                key={t.code}
                item={t as TaxonomyItem}
                editableFields={[
                  { key: 'label', label: 'Label' },
                  { key: 'description', label: 'Description' },
                ]}
                onUpdate={(updated) => {
                  onUpdateBase(baseItems.map((i) => i.code === t.code ? { ...i, ...updated } : i))
                }}
                onDelete={() => onRemoveBase(t.code)}
              >
                <TagIcon className="h-4 w-4 text-gray-400 mt-0.5 flex-shrink-0" />
                <div className={cn('min-w-0', acc && acc.accuracy < 70 && 'border-l-2 border-l-red-400 pl-2')}>
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-medium text-gray-900">{t.label}</span>
                    {acc && acc.total > 0 && <AccuracyBadge score={acc.accuracy} />}
                    {acc && acc.total > 0 && acc.accuracy < 70 && (
                      <Link to={`/admin/extraction-quality?entity_type=clause&taxonomy_code=${t.code}`} className="text-[10px] text-red-500 hover:text-red-700 font-medium">
                        Review &rarr;
                      </Link>
                    )}
                  </div>
                  <div className="text-[10px] text-gray-400 font-mono">{t.code}</div>
                  {t.description && <div className="text-xs text-gray-500 mt-0.5">{t.description}</div>}
                </div>
              </EditableBaseItem>
            )
          })}
        </div>
      </div>

      {/* Custom items */}
      {customItems.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-violet-500 mb-3">
            Tenant Custom ({customItems.length})
          </h3>
          <div className="space-y-1.5">
            {customItems.map((item) => (
              <div key={item.code} className="flex items-center justify-between p-2.5 bg-violet-50/50 rounded-lg border border-violet-100">
                <div>
                  <span className="text-sm font-medium text-gray-900">{item.label}</span>
                  <span className="text-xs text-gray-400 ml-2 font-mono">{item.code}</span>
                </div>
                <button onClick={() => onRemove(item.code)} className="p-1 text-gray-400 hover:text-red-500">
                  <TrashIcon className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ============================================================================
// Clause Types Tab
// ============================================================================

function ClauseTypesTab({
  baseItems,
  customItems,
  onRemove,
  onUpdateBase,
  onRemoveBase,
  accuracy,
}: {
  baseItems: ProfileDetail['clause_types']
  customItems: TaxonomyItem[]
  onRemove: (code: string) => void
  onUpdateBase: (items: ProfileDetail['clause_types']) => void
  onRemoveBase: (code: string) => void
  accuracy?: Record<string, TaxonomyAccuracyItem>
}) {
  const [showForm, setShowForm] = useState(false)

  // Group base items by category
  const grouped: Record<string, typeof baseItems> = {}
  baseItems.forEach((t) => {
    const cat = t.category || 'general'
    if (!grouped[cat]) grouped[cat] = []
    grouped[cat].push(t)
  })

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400">
            Base Profile ({baseItems.length})
          </h3>
          <button onClick={() => setShowForm(!showForm)} className="flex items-center gap-1 text-xs text-violet-600 hover:text-violet-800 font-medium">
            <PlusIcon className="h-3.5 w-3.5" /> Add
          </button>
        </div>

        {showForm && (
          <div className="mb-3">
            <TaxonomyAddForm
              fields={[
                { key: 'code', label: 'Code', placeholder: 'e.g. product_recall', required: true },
                { key: 'label', label: 'Label', placeholder: 'e.g. Product Recall', required: true },
                { key: 'category', label: 'Category', placeholder: 'e.g. quality, risk, compliance' },
              ]}
              onAdd={(item) => {
                onUpdateBase([...baseItems, item as ProfileDetail['clause_types'][0]])
                setShowForm(false)
              }}
              onCancel={() => setShowForm(false)}
            />
          </div>
        )}

        <div className="space-y-4">
          {Object.entries(grouped).map(([category, items]) => (
            <div key={category}>
              <div className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-2">{category}</div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {items.map((t) => {
                  const acc = accuracy?.[t.code]
                  return (
                    <EditableBaseItem
                      key={t.code}
                      item={t as TaxonomyItem}
                      editableFields={[
                        { key: 'label', label: 'Label' },
                        { key: 'category', label: 'Category' },
                        { key: 'risk_weight', label: 'Risk Weight' },
                      ]}
                      onUpdate={(updated) => {
                        const u = { ...updated, risk_weight: updated.risk_weight ? Number(updated.risk_weight) : undefined }
                        onUpdateBase(baseItems.map((i) => i.code === t.code ? { ...i, ...u } as typeof i : i))
                      }}
                      onDelete={() => onRemoveBase(t.code)}
                    >
                      <div className={cn('min-w-0', acc && acc.accuracy < 70 && 'border-l-2 border-l-red-400 pl-2')}>
                        <div className="flex items-center gap-1.5">
                          <span className="text-sm font-medium text-gray-900">{t.label}</span>
                          {acc && acc.total > 0 && <AccuracyBadge score={acc.accuracy} />}
                          {acc && acc.total > 0 && acc.accuracy < 70 && (
                            <Link to={`/admin/extraction-quality?entity_type=clause&taxonomy_code=${t.code}`} className="text-[10px] text-red-500 hover:text-red-700 font-medium">
                              Review &rarr;
                            </Link>
                          )}
                        </div>
                        <div className="text-[10px] text-gray-400 font-mono">{t.code}</div>
                        {t.risk_weight != null && <span className="text-[10px] text-gray-500">weight: {t.risk_weight}</span>}
                      </div>
                    </EditableBaseItem>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {customItems.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-violet-500 mb-3">Tenant Custom ({customItems.length})</h3>
          <div className="space-y-1.5">
            {customItems.map((item) => (
              <div key={item.code} className="flex items-center justify-between p-2.5 bg-violet-50/50 rounded-lg border border-violet-100">
                <div>
                  <span className="text-sm font-medium text-gray-900">{item.label}</span>
                  <span className="text-xs text-gray-400 ml-2 font-mono">{item.code}</span>
                  {typeof item.category === 'string' && <span className="text-xs text-violet-600 ml-2">{item.category}</span>}
                </div>
                <button onClick={() => onRemove(item.code)} className="p-1 text-gray-400 hover:text-red-500">
                  <TrashIcon className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ============================================================================
// Risk Categories Tab
// ============================================================================

function RiskCategoriesTab({
  baseItems,
  customItems,
  onRemove,
  onUpdateBase,
  onRemoveBase,
}: {
  baseItems: ProfileDetail['risk_categories']
  customItems: TaxonomyItem[]
  onRemove: (code: string) => void
  onUpdateBase: (items: ProfileDetail['risk_categories']) => void
  onRemoveBase: (code: string) => void
}) {
  const [showForm, setShowForm] = useState(false)

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400">Base Profile ({baseItems.length})</h3>
          <button onClick={() => setShowForm(!showForm)} className="flex items-center gap-1 text-xs text-violet-600 hover:text-violet-800 font-medium">
            <PlusIcon className="h-3.5 w-3.5" /> Add
          </button>
        </div>

        {showForm && (
          <div className="mb-3">
            <TaxonomyAddForm
              fields={[
                { key: 'code', label: 'Code', placeholder: 'e.g. supply_disruption', required: true },
                { key: 'label', label: 'Label', placeholder: 'e.g. Supply Disruption', required: true },
                { key: 'severity', label: 'Severity', placeholder: 'critical, high, medium, low' },
                { key: 'description', label: 'Description', placeholder: 'Risk of supply chain interruption' },
              ]}
              onAdd={(item) => {
                onUpdateBase([...baseItems, item as ProfileDetail['risk_categories'][0]])
                setShowForm(false)
              }}
              onCancel={() => setShowForm(false)}
            />
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {baseItems.map((r) => (
            <EditableBaseItem
              key={r.code}
              item={r as TaxonomyItem}
              editableFields={[
                { key: 'label', label: 'Label' },
                { key: 'severity', label: 'Severity (critical/high/medium/low)' },
                { key: 'weight', label: 'Weight' },
                { key: 'description', label: 'Description' },
              ]}
              onUpdate={(updated) => {
                const u = { ...updated, weight: updated.weight ? Number(updated.weight) : undefined }
                onUpdateBase(baseItems.map((i) => i.code === r.code ? { ...i, ...u } as typeof i : i))
              }}
              onDelete={() => onRemoveBase(r.code)}
            >
              <div className="min-w-0">
                <div className="text-sm font-medium text-gray-900">{r.label}</div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[10px] text-gray-400 font-mono">{r.code}</span>
                  {r.severity && <span className="text-[10px] capitalize text-orange-600">{r.severity}</span>}
                  <span className="text-[10px] text-gray-500">w:{r.weight ?? 10}</span>
                </div>
                {r.description && <p className="text-xs text-gray-500 mt-0.5">{r.description}</p>}
              </div>
            </EditableBaseItem>
          ))}
        </div>
      </div>

      {customItems.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-violet-500 mb-3">Tenant Custom ({customItems.length})</h3>
          <div className="space-y-1.5">
            {customItems.map((item) => (
              <div key={item.code} className="flex items-center justify-between p-2.5 bg-violet-50/50 rounded-lg border border-violet-100">
                <div>
                  <span className="text-sm font-medium text-gray-900">{item.label}</span>
                  <span className="text-xs text-gray-400 ml-2 font-mono">{item.code}</span>
                  {typeof item.severity === 'string' && <span className="text-xs text-orange-600 ml-2 capitalize">{item.severity}</span>}
                </div>
                <button onClick={() => onRemove(item.code)} className="p-1 text-gray-400 hover:text-red-500">
                  <TrashIcon className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ============================================================================
// SLA Metric Row — inline-editable table row
// ============================================================================

function SLAMetricRow({
  metric,
  onUpdate,
  onDelete,
  accuracy,
}: {
  metric: ProfileDetail['sla_metrics'][0]
  onUpdate: (updated: TaxonomyItem) => void
  onDelete: () => void
  accuracy?: TaxonomyAccuracyItem
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState({
    label: metric.label,
    unit: metric.unit || '',
    direction: metric.direction || '',
    default_target: String(metric.default_target ?? ''),
  })

  const startEdit = () => {
    setDraft({
      label: metric.label,
      unit: metric.unit || '',
      direction: metric.direction || '',
      default_target: String(metric.default_target ?? ''),
    })
    setEditing(true)
  }

  const handleSave = () => {
    onUpdate({
      ...metric,
      label: draft.label.trim(),
      unit: draft.unit.trim() || undefined,
      direction: draft.direction.trim() || undefined,
      default_target: draft.default_target ? Number(draft.default_target) : undefined,
    } as TaxonomyItem)
    setEditing(false)
  }

  if (editing) {
    return (
      <tr className="bg-blue-50">
        <td className="py-2 px-3">
          <input
            value={draft.label}
            onChange={(e) => setDraft((d) => ({ ...d, label: e.target.value }))}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') setEditing(false) }}
            autoFocus
            className="w-full px-2 py-1 text-xs border border-blue-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
          <div className="text-[10px] text-gray-400 font-mono mt-0.5">{metric.code}</div>
        </td>
        <td className="py-2 px-3">
          <input
            value={draft.unit}
            onChange={(e) => setDraft((d) => ({ ...d, unit: e.target.value }))}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') setEditing(false) }}
            placeholder="percentage, days..."
            className="w-full px-2 py-1 text-xs border border-blue-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
        </td>
        <td className="py-2 px-3">
          <select
            value={draft.direction}
            onChange={(e) => setDraft((d) => ({ ...d, direction: e.target.value }))}
            className="w-full px-2 py-1 text-xs border border-blue-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-400"
          >
            <option value="">—</option>
            <option value="higher_is_better">Higher is better</option>
            <option value="lower_is_better">Lower is better</option>
          </select>
        </td>
        <td className="py-2 px-3 text-right">
          <input
            type="number"
            value={draft.default_target}
            onChange={(e) => setDraft((d) => ({ ...d, default_target: e.target.value }))}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') setEditing(false) }}
            className="w-20 px-2 py-1 text-xs text-right border border-blue-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
        </td>
        <td className="py-2 px-3">
          <div className="flex items-center gap-1 justify-end">
            <button onClick={handleSave} className="p-1 text-blue-600 hover:text-blue-800" title="Save">
              <CheckIcon className="h-3.5 w-3.5" />
            </button>
            <button onClick={() => setEditing(false)} className="p-1 text-gray-400 hover:text-gray-600" title="Cancel">
              <XMarkIcon className="h-3.5 w-3.5" />
            </button>
          </div>
        </td>
      </tr>
    )
  }

  return (
    <tr className={cn('group border-t border-gray-100 hover:bg-gray-50 transition-colors', accuracy && accuracy.accuracy < 70 && 'border-l-2 border-l-red-400')}>
      <td className="py-2 px-3">
        <div className="flex items-center gap-1.5">
          <span className="text-sm font-medium text-gray-900">{metric.label}</span>
          {accuracy && accuracy.total > 0 && <AccuracyBadge score={accuracy.accuracy} />}
          {accuracy && accuracy.total > 0 && accuracy.accuracy < 70 && (
            <Link to={`/admin/extraction-quality?entity_type=sla&taxonomy_code=${metric.code}`} className="text-[10px] text-red-500 hover:text-red-700 font-medium">
              Review &rarr;
            </Link>
          )}
        </div>
        <div className="text-[10px] text-gray-400 font-mono">{metric.code}</div>
      </td>
      <td className="py-2 px-3 text-xs text-gray-600">{metric.unit || '—'}</td>
      <td className="py-2 px-3 text-xs text-gray-600">
        {metric.direction === 'higher_is_better' ? '↑ Higher' : metric.direction === 'lower_is_better' ? '↓ Lower' : '—'}
      </td>
      <td className="py-2 px-3 text-right text-xs text-gray-600">{metric.default_target ?? '—'}</td>
      <td className="py-2 px-3">
        <div className="flex items-center gap-0.5 justify-end opacity-0 group-hover:opacity-100 transition-opacity">
          <button onClick={startEdit} className="p-1 text-gray-400 hover:text-blue-600" title="Edit">
            <PencilIcon className="h-3.5 w-3.5" />
          </button>
          <button onClick={onDelete} className="p-1 text-gray-400 hover:text-red-500" title="Delete">
            <TrashIcon className="h-3.5 w-3.5" />
          </button>
        </div>
      </td>
    </tr>
  )
}

// ============================================================================
// SLA Metrics Tab
// ============================================================================

function SLAMetricsTab({
  baseItems,
  customItems,
  onAdd,
  onRemove,
  onUpdateBase,
  onRemoveBase,
  accuracy,
}: {
  baseItems: ProfileDetail['sla_metrics']
  customItems: TaxonomyItem[]
  onAdd: (item: TaxonomyItem) => void
  onRemove: (code: string) => void
  onUpdateBase: (items: ProfileDetail['sla_metrics']) => void
  onRemoveBase: (code: string) => void
  accuracy?: Record<string, TaxonomyAccuracyItem>
}) {
  const [showForm, setShowForm] = useState(false)

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400">Base Profile ({baseItems.length})</h3>
          <button onClick={() => setShowForm(!showForm)} className="flex items-center gap-1 text-xs text-violet-600 hover:text-violet-800 font-medium">
            <PlusIcon className="h-3.5 w-3.5" /> Add
          </button>
        </div>

        {showForm && (
          <div className="mb-3">
            <TaxonomyAddForm
              fields={[
                { key: 'code', label: 'Code', placeholder: 'e.g. defect_ppm', required: true },
                { key: 'label', label: 'Label', placeholder: 'e.g. Defect Rate (PPM)', required: true },
                { key: 'unit', label: 'Unit', placeholder: 'percentage, days, ppm' },
                { key: 'direction', label: 'Direction', placeholder: 'higher_is_better or lower_is_better' },
              ]}
              onAdd={(item) => {
                onUpdateBase([...baseItems, item as ProfileDetail['sla_metrics'][0]])
                setShowForm(false)
              }}
              onCancel={() => setShowForm(false)}
            />
          </div>
        )}

        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left py-2 px-3 text-xs font-semibold text-gray-500 uppercase">Metric</th>
                <th className="text-left py-2 px-3 text-xs font-semibold text-gray-500 uppercase">Unit</th>
                <th className="text-left py-2 px-3 text-xs font-semibold text-gray-500 uppercase">Direction</th>
                <th className="text-right py-2 px-3 text-xs font-semibold text-gray-500 uppercase">Target</th>
                <th className="w-16"></th>
              </tr>
            </thead>
            <tbody>
              {baseItems.map((m) => (
                <SLAMetricRow
                  key={m.code}
                  metric={m}
                  onUpdate={(updated) => {
                    onUpdateBase(baseItems.map((i) => i.code === m.code ? { ...i, ...updated } as typeof i : i))
                  }}
                  onDelete={() => onRemoveBase(m.code)}
                  accuracy={accuracy?.[m.code]}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-violet-500">Custom ({customItems.length})</h3>
          <button onClick={() => setShowForm(!showForm)} className="flex items-center gap-1 text-xs text-violet-600 hover:text-violet-800 font-medium">
            <PlusIcon className="h-3.5 w-3.5" /> Add
          </button>
        </div>

        {showForm && (
          <div className="mb-3">
            <TaxonomyAddForm
              fields={[
                { key: 'code', label: 'Code', placeholder: 'e.g. defect_ppm', required: true },
                { key: 'label', label: 'Label', placeholder: 'e.g. Defect Rate (PPM)', required: true },
                { key: 'unit', label: 'Unit', placeholder: 'percentage, days, ppm' },
                { key: 'direction', label: 'Direction', placeholder: 'higher_is_better or lower_is_better' },
              ]}
              onAdd={(item) => { onAdd(item); setShowForm(false) }}
              onCancel={() => setShowForm(false)}
            />
          </div>
        )}

        {customItems.length > 0 ? (
          <div className="space-y-1.5">
            {customItems.map((item) => (
              <div key={item.code} className="flex items-center justify-between p-2.5 bg-violet-50/50 rounded-lg border border-violet-100">
                <div>
                  <span className="text-sm font-medium text-gray-900">{item.label}</span>
                  <span className="text-xs text-gray-400 ml-2 font-mono">{item.code}</span>
                  {typeof item.unit === 'string' && <span className="text-xs text-gray-500 ml-2">{item.unit}</span>}
                </div>
                <button onClick={() => onRemove(item.code)} className="p-1 text-gray-400 hover:text-red-500">
                  <TrashIcon className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        ) : !showForm ? (
          <p className="text-xs text-gray-400 italic">No custom SLA metrics added.</p>
        ) : null}
      </div>
    </div>
  )
}

// ============================================================================
// Extraction Hints Tab
// ============================================================================

function ExtractionHintsTab({
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
  const [hintsKey, setHintsKey] = useState('')
  const [hintsValue, setHintsValue] = useState('')

  const agentLabels: Record<string, string> = {
    metadata: 'Metadata Extraction',
    clauses: 'Clause Extraction',
    risks: 'Risk Detection',
    obligations: 'Obligation Tracking',
    slas: 'SLA Extraction',
  }

  return (
    <div className="space-y-6">
      {/* Quality-driven suggestions */}
      {qualityHints && qualityHints.length > 0 && (
        <div className="p-4 bg-red-50 rounded-xl border border-red-200">
          <div className="flex items-center gap-2 mb-3">
            <ExclamationTriangleIcon className="h-5 w-5 text-red-500" />
            <span className="text-sm font-semibold text-gray-900">
              Low accuracy areas need attention
            </span>
          </div>
          <p className="text-xs text-gray-500 mb-3">
            Based on extraction quality data, these taxonomy items have accuracy below 70%. Add hints to improve extraction.
          </p>
          <div className="space-y-2">
            {qualityHints.map((hint) => (
              <div key={`${hint.category}-${hint.code}`} className="flex items-center justify-between p-3 bg-white rounded-lg border border-red-100">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-900">{hint.label}</span>
                    <AccuracyBadge score={hint.accuracy} />
                    <span className="text-[10px] text-gray-400">{hint.total_verified} verified</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5 truncate">{hint.suggested_hint}</p>
                </div>
                <button
                  onClick={() => {
                    setHintsKey(hint.agent)
                    setHintsValue(hint.suggested_hint)
                  }}
                  className="ml-3 px-3 py-1.5 text-xs font-medium text-violet-700 bg-violet-50 rounded-lg hover:bg-violet-100 flex-shrink-0"
                >
                  Apply
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Base hints */}
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
          Base Profile Hints ({Object.keys(baseHints).length})
        </h3>
        <div className="space-y-2">
          {Object.entries(baseHints).map(([key, hint]) => (
            <div key={key} className="p-3 bg-gray-50 rounded-lg border border-gray-100">
              <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1">
                {agentLabels[key] || key}
              </div>
              <p className="text-sm text-gray-700 leading-relaxed">{hint}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Custom hints */}
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-violet-500 mb-3">
          Custom Hints ({Object.keys(customHints).length})
        </h3>

        {Object.entries(customHints).length > 0 && (
          <div className="space-y-2 mb-4">
            {Object.entries(customHints).map(([key, value]) => (
              <div key={key} className="p-3 bg-violet-50/50 rounded-lg border border-violet-100">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold uppercase text-violet-600">{agentLabels[key] || key}</span>
                  <button
                    onClick={() => { const next = { ...customHints }; delete next[key]; onSave(next) }}
                    className="p-0.5 text-gray-400 hover:text-red-500"
                  >
                    <TrashIcon className="h-3 w-3" />
                  </button>
                </div>
                <p className="text-sm text-gray-700">{value}</p>
              </div>
            ))}
          </div>
        )}

        <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
          <div className="grid grid-cols-4 gap-2">
            <div>
              <label className="block text-[10px] font-medium text-gray-500 mb-0.5">Agent</label>
              <select
                value={hintsKey}
                onChange={(e) => setHintsKey(e.target.value)}
                className="w-full px-2 py-1.5 text-xs border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-violet-400"
              >
                <option value="">Select...</option>
                <option value="metadata">Metadata</option>
                <option value="clauses">Clauses</option>
                <option value="risks">Risks</option>
                <option value="obligations">Obligations</option>
                <option value="slas">SLAs</option>
              </select>
            </div>
            <div className="col-span-3">
              <label className="block text-[10px] font-medium text-gray-500 mb-0.5">Hint</label>
              <input
                type="text"
                placeholder="e.g. Look for FDA compliance, HACCP certifications..."
                value={hintsValue}
                onChange={(e) => setHintsValue(e.target.value)}
                className="w-full px-2 py-1.5 text-xs border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-violet-400"
              />
            </div>
          </div>
          <button
            onClick={() => {
              if (hintsKey && hintsValue.trim()) {
                onSave({ ...customHints, [hintsKey]: hintsValue.trim() })
                setHintsKey('')
                setHintsValue('')
              }
            }}
            disabled={!hintsKey || !hintsValue.trim()}
            className="mt-2 px-3 py-1 text-xs bg-violet-600 text-white rounded hover:bg-violet-700 disabled:opacity-40"
          >
            Add Hint
          </button>
        </div>
      </div>
    </div>
  )
}

// ============================================================================
// Company Names Tab (Party Aliases for extraction)
// ============================================================================

function CompanyNamesTab({
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

  const handleRemove = (name: string) => {
    onSave(aliases.filter((a) => a !== name))
  }

  return (
    <div className="space-y-6">
      <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
        <h3 className="text-sm font-semibold text-blue-900 mb-1">How this works</h3>
        <p className="text-sm text-blue-700">
          When contracts are uploaded, the AI identifies the counterparty by excluding your company from the parties found.
          By default, it only excludes the tenant name. If your contracts use different legal entity names (e.g., subsidiaries, DBAs, parent companies),
          add them here so the AI correctly identifies the other party as the counterparty.
        </p>
      </div>

      {/* Current aliases */}
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
          Known Company Names ({aliases.length})
        </h3>

        {aliases.length > 0 ? (
          <div className="space-y-1.5">
            {aliases.map((name) => (
              <div
                key={name}
                className="flex items-center justify-between p-3 bg-white rounded-lg border border-gray-200 hover:border-gray-300 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <BuildingOffice2Icon className="h-4 w-4 text-gray-400 flex-shrink-0" />
                  <span className="text-sm font-medium text-gray-900">{name}</span>
                </div>
                <button
                  onClick={() => handleRemove(name)}
                  className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                  title="Remove"
                >
                  <XMarkIcon className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-6 text-center bg-gray-50 rounded-lg border border-dashed border-gray-300">
            <BuildingOffice2Icon className="h-8 w-8 mx-auto text-gray-300 mb-2" />
            <p className="text-sm text-gray-500">No company names configured.</p>
            <p className="text-xs text-gray-400 mt-1">
              Add names that represent your organization (legal entities, DBAs, subsidiaries).
            </p>
          </div>
        )}
      </div>

      {/* Add form */}
      <div className="flex items-end gap-2">
        <div className="flex-1">
          <label className="block text-xs font-medium text-gray-600 mb-1">Add Company Name</label>
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleAdd() }}
            placeholder="e.g. Vialto Partners, Galaxy US OpCo Inc."
            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-400 focus:border-transparent"
          />
        </div>
        <button
          onClick={handleAdd}
          disabled={!newName.trim()}
          className="px-4 py-2 text-sm font-medium bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-40 transition-colors"
        >
          Add
        </button>
      </div>
    </div>
  )
}

// ============================================================================
// Profile Selector (compact dropdown)
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
  const current = profiles.find((p) => p.slug === currentSlug)

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-lg hover:border-gray-300 transition-colors text-sm"
      >
        <CheckCircleIcon className="h-4 w-4 text-violet-500" />
        <span className="font-medium text-gray-900">{current?.name || 'No profile selected'}</span>
        <ChevronDownIcon className={cn('h-4 w-4 text-gray-400 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 w-72 bg-white border border-gray-200 rounded-lg shadow-lg z-20 py-1">
          {profiles.map((p) => (
            <button
              key={p.id}
              onClick={() => { onSwitch(p.slug); setOpen(false) }}
              className={cn(
                'w-full text-left px-4 py-2.5 hover:bg-gray-50 transition-colors',
                p.slug === currentSlug && 'bg-violet-50'
              )}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium text-gray-900">{p.name}</div>
                  <div className="text-xs text-gray-500">{p.description}</div>
                </div>
                {p.slug === currentSlug && <CheckCircleIcon className="h-4 w-4 text-violet-500 flex-shrink-0" />}
              </div>
              <div className="flex gap-3 mt-1">
                <span className="text-[10px] text-gray-400">{p.contract_type_count} types</span>
                <span className="text-[10px] text-gray-400">{p.clause_type_count} clauses</span>
                <span className="text-[10px] text-gray-400">{p.risk_category_count} risks</span>
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
// Main Page
// ============================================================================

export default function IndustryProfilesPage() {
  const [activeTab, setActiveTab] = useState<TabId>('contract_types')
  const queryClient = useQueryClient()
  const { config, refresh: refreshConfig } = useTenantConfig()

  const currentSlug = config?.industry

  // Fetch all profiles for the selector
  const { data: profiles = [], isLoading: profilesLoading } = useQuery<ProfileSummary[]>({
    queryKey: ['industry-profiles'],
    queryFn: getIndustryProfiles,
  })

  const currentProfileId = profiles.find((p) => p.slug === currentSlug)?.id

  // Fetch current profile detail
  const { data: profile, isLoading: profileLoading } = useQuery<ProfileDetail>({
    queryKey: ['industry-profile', currentProfileId],
    queryFn: () => getIndustryProfile(currentProfileId!),
    enabled: !!currentProfileId,
  })

  // Fetch tenant overrides
  const { data: overrides } = useQuery({
    queryKey: ['tenant-overrides'],
    queryFn: getTenantOverrides,
  })

  // Fetch suggestions
  const { data: suggestions = [] } = useQuery({
    queryKey: ['taxonomy-suggestions', 'pending'],
    queryFn: () => getTaxonomySuggestions('pending'),
  })

  const { data: stats } = useQuery({
    queryKey: ['taxonomy-suggestion-stats'],
    queryFn: getTaxonomySuggestionStats,
  })

  // Extraction quality overview for accuracy badges
  const { data: qualityOverview } = useQuery({
    queryKey: ['extraction-quality-overview'],
    queryFn: getExtractionQualityOverview,
  })

  // Per-taxonomy-item accuracy
  const { data: taxonomyAccuracy } = useQuery({
    queryKey: ['taxonomy-accuracy'],
    queryFn: getTaxonomyAccuracy,
  })

  // Quality-driven hints for AI Hints tab
  const { data: qualityHints } = useQuery({
    queryKey: ['quality-hints'],
    queryFn: getQualityHints,
  })

  // Mutations
  const saveMutation = useMutation({
    mutationFn: updateTenantOverrides,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant-overrides'] })
      refreshConfig()
    },
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

  // Helpers
  const saveList = (key: string, items: TaxonomyItem[]) => saveMutation.mutate({ [key]: items })
  const saveBase = (key: string, items: unknown[]) => updateProfileMutation.mutate({ [key]: items })
  const removeBase = (key: string, code: string, items: unknown[]) =>
    updateProfileMutation.mutate({ [key]: (items as TaxonomyItem[]).filter((i) => i.code !== code) })

  const customContractTypes = (overrides?.contract_types || []) as TaxonomyItem[]
  const customClauseTypes = (overrides?.clause_types || []) as TaxonomyItem[]
  const customRiskCategories = (overrides?.risk_categories || []) as TaxonomyItem[]
  const customSlaMetrics = (overrides?.sla_metrics || []) as TaxonomyItem[]
  const customHints = (overrides?.extraction_hints || {}) as Record<string, string>
  const partyAliases = (overrides?.party_aliases || []) as string[]

  const pendingCount = stats?.pending || suggestions.length

  // Filter suggestions by active tab's category
  const tabSuggestions = suggestions.filter((s) => s.category === activeTab)

  if (profilesLoading || profileLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-3">
            <SwatchIcon className="h-7 w-7 text-violet-500" />
            <h1 className="text-2xl font-bold text-gray-900">Industry Profile</h1>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            Configure contract types, clauses, risk frameworks, and AI extraction behavior.
          </p>
        </div>
        <ProfileSelector
          profiles={profiles}
          currentSlug={currentSlug || null}
          onSwitch={(slug) => switchProfileMutation.mutate(slug)}
        />
      </div>

      {/* Suggestion Banner */}
      {pendingCount > 0 && (
        <div className="mb-6 p-4 bg-amber-50 rounded-xl border border-amber-200">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <SparklesIcon className="h-5 w-5 text-amber-500" />
              <span className="text-sm font-semibold text-gray-900">
                {pendingCount} AI suggestion{pendingCount > 1 ? 's' : ''} pending
              </span>
            </div>
            {suggestions.length > 1 && (
              <button
                onClick={() => approveAllMutation.mutate()}
                disabled={approveAllMutation.isPending}
                className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-green-700 bg-green-50 rounded-lg hover:bg-green-100 disabled:opacity-40"
              >
                <CheckIcon className="h-3.5 w-3.5" />
                Approve All
              </button>
            )}
          </div>
          <p className="text-xs text-gray-500">
            Items discovered from your contracts. Switch to the relevant tab to review, or approve all at once.
          </p>
        </div>
      )}

      {/* Quality Summary Banner */}
      {qualityOverview?.avg_overall_score != null && (
        <div className="mb-6 p-4 bg-white rounded-xl border border-gray-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">Extraction Accuracy</span>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-500">Overall <AccuracyBadge score={qualityOverview.avg_overall_score} size="md" /></span>
                <span className="text-xs text-gray-500">Clauses <AccuracyBadge score={qualityOverview.avg_clause_score} size="md" /></span>
                <span className="text-xs text-gray-500">Obligations <AccuracyBadge score={qualityOverview.avg_obligation_score} size="md" /></span>
                <span className="text-xs text-gray-500">SLAs <AccuracyBadge score={qualityOverview.avg_sla_score} size="md" /></span>
              </div>
            </div>
            <Link
              to="/admin/extraction-quality"
              className="flex items-center gap-1 text-xs text-violet-600 hover:text-violet-800 font-medium"
            >
              View Details <ArrowTopRightOnSquareIcon className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-1 -mb-px overflow-x-auto" role="tablist">
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
                role="tab"
                aria-selected={isActive}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition-colors relative',
                  isActive
                    ? 'border-violet-500 text-violet-700'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                )}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
                <AccuracyBadge score={tabScore} />
                {tabSugCount > 0 && (
                  <span className="ml-1 flex h-4 w-4 items-center justify-center rounded-full bg-amber-500 text-[9px] font-bold text-white">
                    {tabSugCount}
                  </span>
                )}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Tab-specific suggestions */}
      {tabSuggestions.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <SparklesIcon className="h-4 w-4 text-amber-500" />
            <span className="text-xs font-semibold text-gray-600 uppercase">
              Suggestions for this category
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {tabSuggestions.map((s) => (
              <SuggestionCard
                key={s.id}
                suggestion={s}
                onApprove={(id, mods) => approveMutation.mutate({ id, mods })}
                onReject={(id) => rejectMutation.mutate(id)}
                isProcessing={approveMutation.isPending || rejectMutation.isPending}
              />
            ))}
          </div>
        </div>
      )}

      {/* Tab Content */}
      <div className="min-h-[400px]">
        {activeTab === 'contract_types' && (
          <ContractTypesTab
            baseItems={profile?.contract_types || []}
            customItems={customContractTypes}
            onRemove={(code) => saveList('contract_types', customContractTypes.filter((i) => i.code !== code))}
            onUpdateBase={(items) => saveBase('contract_types', items)}
            onRemoveBase={(code) => removeBase('contract_types', code, profile?.contract_types || [])}
            accuracy={taxonomyAccuracy?.clause_types}
          />
        )}
        {activeTab === 'clause_types' && (
          <ClauseTypesTab
            baseItems={profile?.clause_types || []}
            customItems={customClauseTypes}
            onRemove={(code) => saveList('clause_types', customClauseTypes.filter((i) => i.code !== code))}
            onUpdateBase={(items) => saveBase('clause_types', items)}
            onRemoveBase={(code) => removeBase('clause_types', code, profile?.clause_types || [])}
            accuracy={taxonomyAccuracy?.clause_types}
          />
        )}
        {activeTab === 'risk_categories' && (
          <RiskCategoriesTab
            baseItems={profile?.risk_categories || []}
            customItems={customRiskCategories}
            onRemove={(code) => saveList('risk_categories', customRiskCategories.filter((i) => i.code !== code))}
            onUpdateBase={(items) => saveBase('risk_categories', items)}
            onRemoveBase={(code) => removeBase('risk_categories', code, profile?.risk_categories || [])}
          />
        )}
        {activeTab === 'sla_metrics' && (
          <SLAMetricsTab
            baseItems={profile?.sla_metrics || []}
            customItems={customSlaMetrics}
            onAdd={(item) => saveList('sla_metrics', [...customSlaMetrics, item])}
            onRemove={(code) => saveList('sla_metrics', customSlaMetrics.filter((i) => i.code !== code))}
            onUpdateBase={(items) => saveBase('sla_metrics', items)}
            onRemoveBase={(code) => removeBase('sla_metrics', code, profile?.sla_metrics || [])}
            accuracy={taxonomyAccuracy?.sla_metric_types}
          />
        )}
        {activeTab === 'extraction_hints' && (
          <ExtractionHintsTab
            baseHints={profile?.extraction_hints || {}}
            customHints={customHints}
            onSave={(hints) => saveMutation.mutate({ extraction_hints: hints })}
            qualityHints={qualityHints}
          />
        )}
        {activeTab === 'company_names' && (
          <CompanyNamesTab
            aliases={partyAliases}
            onSave={(aliases) => saveMutation.mutate({ party_aliases: aliases })}
          />
        )}
      </div>

      {(saveMutation.isError || updateProfileMutation.isError) && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-xs text-red-600">
            {(saveMutation.error as Error)?.message || (updateProfileMutation.error as Error)?.message || 'Failed to save'}
          </p>
        </div>
      )}
    </div>
  )
}
