import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BookOpenIcon,
  ChevronRightIcon,
  MagnifyingGlassIcon,
  TagIcon,
} from '@heroicons/react/24/outline'
import { useTranslation } from 'react-i18next'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'

const CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  party: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
  service: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
  document: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' },
  term: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  financial: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
  data: { bg: 'bg-cyan-50', text: 'text-cyan-700', border: 'border-cyan-200' },
  process: { bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200' },
  legal: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
  uncategorized: { bg: 'bg-gray-50', text: 'text-gray-600', border: 'border-gray-200' },
}

const CATEGORY_LABELS: Record<string, string> = {
  party: 'Parties',
  service: 'Services',
  document: 'Documents',
  term: 'Terms',
  financial: 'Financial',
  data: 'Data',
  process: 'Process',
  legal: 'Legal',
  uncategorized: 'Other',
}

interface Definition {
  id: string
  term: string
  definition_text: string
  category: string | null
  section_reference: string | null
  page_number: number | null
  cross_references: string[]
}

interface DefinitionsSummaryData {
  contract_id: string
  contract_filename: string
  definitions: Definition[]
  total: number
  by_category: Record<string, number>
}

interface Props {
  contractId: string
}

export default function DefinitionsSummary({ contractId }: Props) {
  const { t } = useTranslation()
  const [searchTerm, setSearchTerm] = useState('')

  const categoryLabel = (category: string) =>
    t(`summaries.definitionCategories.${category}`, { defaultValue: CATEGORY_LABELS[category] || category })
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery<DefinitionsSummaryData>({
    queryKey: ['definitions', contractId],
    queryFn: async () => {
      const response = await fetch(`/api/dashboard/definitions/${contractId}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })
      if (!response.ok) throw new Error('Failed to fetch definitions')
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

  if (error || !data || data.total === 0) {
    return (
      <div className="card">
        <div className="card-body text-center py-8">
          <BookOpenIcon className="h-12 w-12 text-gray-300 mx-auto mb-3" />
          <p className="text-sm text-gray-500">
            {t('summaries.noDefinitions')}
          </p>
        </div>
      </div>
    )
  }

  // Filter definitions
  const filteredDefinitions = data.definitions.filter((def) => {
    const matchesSearch = !searchTerm ||
      def.term.toLowerCase().includes(searchTerm.toLowerCase()) ||
      def.definition_text.toLowerCase().includes(searchTerm.toLowerCase())

    const matchesCategory = !selectedCategory ||
      (def.category || 'uncategorized') === selectedCategory

    return matchesSearch && matchesCategory
  })

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="card">
        <div className="card-header">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <BookOpenIcon className="h-6 w-6 text-primary-600" />
              {t('summaries.contractDefinitions', { count: data.total })}
            </h3>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            {t('summaries.definitionsSubtitle')}
          </p>
        </div>

        <div className="card-body">
          {/* Search and filter bar */}
          <div className="flex items-center gap-4 mb-4">
            <div className="relative flex-1">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder={t('summaries.searchDefinitions')}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>

          {/* Category filters */}
          <div className="flex flex-wrap gap-2 mb-4">
            <button
              onClick={() => setSelectedCategory(null)}
              className={cn(
                "px-3 py-1.5 rounded-full text-xs font-medium transition-colors",
                !selectedCategory
                  ? "bg-primary-100 text-primary-700"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              )}
            >
              {t('summaries.allCount', { count: data.total })}
            </button>
            {Object.entries(data.by_category).map(([category, count]) => {
              const colors = CATEGORY_COLORS[category] || CATEGORY_COLORS.uncategorized
              const isSelected = selectedCategory === category

              return (
                <button
                  key={category}
                  onClick={() => setSelectedCategory(isSelected ? null : category)}
                  className={cn(
                    "px-3 py-1.5 rounded-full text-xs font-medium transition-colors flex items-center gap-1",
                    isSelected
                      ? `${colors.bg} ${colors.text}`
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  )}
                >
                  <TagIcon className="h-3 w-3" />
                  {categoryLabel(category)} ({count})
                </button>
              )
            })}
          </div>

          {/* Definitions list */}
          <div className="divide-y divide-gray-100 max-h-96 overflow-y-auto">
            {filteredDefinitions.map((def) => {
              const isExpanded = expandedId === def.id
              const colors = CATEGORY_COLORS[def.category || 'uncategorized'] || CATEGORY_COLORS.uncategorized

              return (
                <div key={def.id} className="py-3">
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : def.id)}
                    className="w-full text-left"
                  >
                    <div className="flex items-start gap-3">
                      <ChevronRightIcon
                        className={cn(
                          "h-4 w-4 mt-1 text-gray-400 transition-transform shrink-0",
                          isExpanded && "rotate-90"
                        )}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-semibold text-gray-900">
                            "{def.term}"
                          </span>
                          {def.category && (
                            <span className={cn(
                              "text-xs px-2 py-0.5 rounded-full",
                              colors.bg, colors.text
                            )}>
                              {categoryLabel(def.category)}
                            </span>
                          )}
                        </div>
                        <p className={cn(
                          "text-sm text-gray-600",
                          !isExpanded && "line-clamp-2"
                        )}>
                          {def.definition_text}
                        </p>
                      </div>
                    </div>
                  </button>

                  {isExpanded && (
                    <div className="mt-3 ml-7 p-3 bg-gray-50 rounded-lg">
                      <p className="text-sm text-gray-700 whitespace-pre-wrap">
                        {def.definition_text}
                      </p>

                      <div className="mt-3 flex items-center gap-4 text-xs text-gray-500">
                        {def.section_reference && (
                          <span>{t('summaries.section', { number: def.section_reference })}</span>
                        )}
                        {def.page_number && (
                          <span>{t('summaries.page', { number: def.page_number })}</span>
                        )}
                      </div>

                      {def.cross_references.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-gray-200">
                          <p className="text-xs text-gray-500 mb-1">{t('summaries.references')}:</p>
                          <div className="flex flex-wrap gap-1">
                            {def.cross_references.map((ref, i) => (
                              <span
                                key={i}
                                className="text-xs px-2 py-0.5 bg-white border border-gray-200 rounded"
                              >
                                "{ref}"
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {filteredDefinitions.length === 0 && (
            <p className="text-center text-sm text-gray-500 py-8">
              {t('summaries.noDefinitionsMatch')}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
