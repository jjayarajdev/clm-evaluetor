import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  generateIndustryProfile,
  createIndustryProfile,
} from '@/lib/api/admin'
import {
  SparklesIcon,
  XMarkIcon,
  ChevronDownIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Draft = Record<string, any>

const SECTION_KEYS = [
  { key: 'contract_types', label: 'Contract Types' },
  { key: 'clause_types', label: 'Clause Types' },
  { key: 'risk_categories', label: 'Risk Categories' },
  { key: 'sla_metrics', label: 'SLA Metrics' },
  { key: 'field_definitions', label: 'Field Definitions' },
  { key: 'extraction_hints', label: 'AI Extraction Hints' },
  { key: 'ui_config', label: 'UI Configuration' },
] as const

function SectionEditor({
  label,
  value,
  onChange,
  onErrorChange,
}: {
  label: string
  value: unknown
  onChange: (parsed: unknown) => void
  onErrorChange: (hasError: boolean) => void
}) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [text, setText] = useState(() => JSON.stringify(value, null, 2))
  const [parseError, setParseError] = useState<string | null>(null)

  const count = Array.isArray(value) ? value.length : Object.keys(value || {}).length

  const handleChange = (raw: string) => {
    setText(raw)
    try {
      onChange(JSON.parse(raw))
      setParseError(null)
      onErrorChange(false)
    } catch {
      setParseError(t('industry.invalidJson'))
      onErrorChange(true)
    }
  }

  return (
    <div className="border border-gray-200 rounded-lg">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-sm"
      >
        <span className="font-medium text-gray-800">{label}</span>
        <span className="flex items-center gap-2">
          {parseError ? (
            <span className="text-xs text-red-600">{parseError}</span>
          ) : (
            <span className="text-xs text-gray-500">{t('industry.itemsCount', { count })}</span>
          )}
          <ChevronDownIcon className={cn('h-4 w-4 text-gray-400 transition-transform', open && 'rotate-180')} />
        </span>
      </button>
      {open && (
        <textarea
          value={text}
          onChange={(e) => handleChange(e.target.value)}
          spellCheck={false}
          className={cn(
            'w-full h-56 px-4 py-2 font-mono text-xs border-t border-gray-200 focus:outline-none focus:ring-1 focus:ring-violet-400 rounded-b-lg',
            parseError && 'bg-red-50'
          )}
        />
      )}
    </div>
  )
}

export default function NewIndustryWizard({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [step, setStep] = useState<'input' | 'review'>('input')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [sampleText, setSampleText] = useState('')
  const [draft, setDraft] = useState<Draft | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])
  const [hasParseErrors, setHasParseErrors] = useState<Record<string, boolean>>({})

  const generateMutation = useMutation({
    mutationFn: () =>
      generateIndustryProfile({
        name: name.trim(),
        description: description.trim(),
        sample_contract_text: sampleText.trim() || undefined,
      }),
    onSuccess: (data) => {
      setDraft(data.draft)
      setWarnings(data.warnings)
      setStep('review')
    },
  })

  const createMutation = useMutation({
    mutationFn: () => createIndustryProfile(draft!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['industry-profiles'] })
      onClose()
    },
  })

  const updateDraftField = (key: string, value: unknown) => {
    setDraft((d) => ({ ...d!, [key]: value }))
  }

  const anyParseError = Object.values(hasParseErrors).some(Boolean)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mutationError = (m: { error: any }) =>
    m.error?.response?.data?.detail
      ? typeof m.error.response.data.detail === 'string'
        ? m.error.response.data.detail
        : JSON.stringify(m.error.response.data.detail)
      : m.error?.message

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <SparklesIcon className="h-5 w-5 text-violet-500" />
            <h2 className="text-base font-bold text-gray-900">
              {step === 'input' ? t('industry.newIndustryProfile') : t('industry.reviewDraft', { name })}
            </h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
          {step === 'input' && (
            <>
              <div>
                <label className="label">{t('industry.industryName')}</label>
                <input
                  className="input"
                  placeholder={t('industry.industryNamePlaceholder')}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div>
                <label className="label">{t('industry.description')}</label>
                <textarea
                  className="input h-24"
                  placeholder={t('industry.descriptionPlaceholder')}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
                <p className="text-xs text-gray-500 mt-1">
                  {t('industry.descriptionHint')}
                </p>
              </div>
              <div>
                <label className="label">{t('industry.sampleContractText')}</label>
                <textarea
                  className="input h-32 font-mono text-xs"
                  placeholder={t('industry.sampleContractPlaceholder')}
                  value={sampleText}
                  onChange={(e) => setSampleText(e.target.value)}
                />
              </div>
              {generateMutation.isError && (
                <p className="text-sm text-red-600">{mutationError(generateMutation)}</p>
              )}
            </>
          )}

          {step === 'review' && draft && (
            <>
              {warnings.length > 0 && (
                <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 space-y-1">
                  {warnings.map((w, i) => (
                    <p key={i} className="flex items-start gap-2 text-xs text-amber-800">
                      <ExclamationTriangleIcon className="h-4 w-4 flex-shrink-0" />
                      {w}
                    </p>
                  ))}
                </div>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">{t('industry.name')}</label>
                  <input
                    className="input"
                    value={draft.name || ''}
                    onChange={(e) => updateDraftField('name', e.target.value)}
                  />
                </div>
                <div>
                  <label className="label">{t('industry.slug')}</label>
                  <input
                    className="input font-mono"
                    value={draft.slug || ''}
                    onChange={(e) => updateDraftField('slug', e.target.value)}
                  />
                </div>
              </div>
              <div>
                <label className="label">{t('industry.description')}</label>
                <textarea
                  className="input h-20"
                  value={draft.description || ''}
                  onChange={(e) => updateDraftField('description', e.target.value)}
                />
              </div>
              <div className="space-y-2">
                {SECTION_KEYS.map(({ key, label }) => (
                  <SectionEditor
                    key={key}
                    label={t(`industry.sections.${key}`, { defaultValue: label })}
                    value={draft[key] ?? (key === 'extraction_hints' || key === 'ui_config' || key === 'field_definitions' ? {} : [])}
                    onChange={(parsed) => updateDraftField(key, parsed)}
                    onErrorChange={(hasError) =>
                      setHasParseErrors((p) => ({ ...p, [key]: hasError }))
                    }
                  />
                ))}
              </div>
              {createMutation.isError && (
                <p className="text-sm text-red-600">{mutationError(createMutation)}</p>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200">
          {step === 'review' ? (
            <button className="btn-secondary text-sm" onClick={() => setStep('input')}>
              {t('industry.back')}
            </button>
          ) : (
            <span />
          )}
          {step === 'input' ? (
            <button
              className="btn-primary text-sm flex items-center gap-2"
              disabled={name.trim().length < 2 || description.trim().length < 10 || generateMutation.isPending}
              onClick={() => generateMutation.mutate()}
            >
              <SparklesIcon className="h-4 w-4" />
              {generateMutation.isPending ? t('industry.generating') : t('industry.generateWithAi')}
            </button>
          ) : (
            <button
              className="btn-primary text-sm flex items-center gap-2"
              disabled={createMutation.isPending || anyParseError}
              onClick={() => createMutation.mutate()}
            >
              <CheckCircleIcon className="h-4 w-4" />
              {createMutation.isPending ? t('industry.creating') : t('industry.createProfile')}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
