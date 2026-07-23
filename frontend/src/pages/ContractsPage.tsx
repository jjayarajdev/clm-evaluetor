import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import {
  MagnifyingGlassIcon,
  XMarkIcon,
  ChevronDownIcon,
  BuildingOfficeIcon,
  TrashIcon,
  ExclamationTriangleIcon,
  PlusIcon,
  ListBulletIcon,
  Squares2X2Icon,
  FunnelIcon,
} from '@heroicons/react/24/outline'
import { useTranslation } from 'react-i18next'
import api from '@/lib/api'
import i18n from '@/i18n'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import ContractTreeView from '@/components/contracts/ContractTreeView'
import { useTenantConfig } from '@/contexts/TenantConfigContext'
import { cn } from '@/lib/utils'

function currentLocale(): string {
  return i18n.language?.startsWith('fr') ? 'fr-FR' : 'en-US'
}

// ── Helpers ──────────────────────────────────────────────────────

function formatValue(value: number | null, currency: string | null): string {
  if (value == null) return '\u2014'
  const c = currency || 'USD'
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`
  return new Intl.NumberFormat(currentLocale(), { style: 'currency', currency: c, maximumFractionDigits: 0 }).format(value)
}

function formatExpiry(dateStr: string | null): string {
  if (!dateStr) return '\u2014'
  const d = new Date(dateStr)
  const now = new Date()
  // Check if ongoing (far future or no real date)
  if (d.getFullYear() > now.getFullYear() + 50) return i18n.t('contracts.ongoing')
  return d.toLocaleDateString(currentLocale(), { month: 'short', year: 'numeric' })
}

const statusStyles: Record<string, string> = {
  completed: 'bg-emerald-100 text-emerald-700',
  active: 'bg-emerald-100 text-emerald-700',
  processing: 'bg-blue-100 text-blue-700',
  pending: 'bg-gray-100 text-gray-600',
  draft: 'bg-gray-100 text-gray-600',
  failed: 'bg-red-100 text-red-700',
  expired: 'bg-red-100 text-red-700',
  under_review: 'bg-blue-100 text-blue-700',
}

const riskStyles: Record<string, string> = {
  low: 'bg-emerald-100 text-emerald-700',
  medium: 'bg-amber-100 text-amber-700',
  high: 'bg-red-100 text-red-700',
  critical: 'bg-purple-100 text-purple-700',
}

function StatusBadge({ status }: { status: string }) {
  const { t } = useTranslation()
  const key = status.toLowerCase().replace(/\s+/g, '_')
  const label = t(`status.${key}`, { defaultValue: status.replace(/_/g, ' ') })
  return (
    <span className={cn(
      'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize',
      statusStyles[key] || 'bg-gray-100 text-gray-600'
    )}>
      {label}
    </span>
  )
}

function RiskBadge({ level }: { level: string }) {
  const { t } = useTranslation()
  return (
    <span className={cn(
      'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize',
      riskStyles[level.toLowerCase()] || 'bg-gray-100 text-gray-600'
    )}>
      {t(`risk.${level.toLowerCase()}`, { defaultValue: level })}
    </span>
  )
}

// ── Page Component ───────────────────────────────────────────────

export default function ContractsPage() {
  const { t } = useTranslation()
  const { contractTypeLabel, uiLabel } = useTenantConfig()
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [selectedCounterparty, setSelectedCounterparty] = useState<string | null>(null)
  const [selectedType, setSelectedType] = useState<string | null>(null)
  const [selectedRisk, setSelectedRisk] = useState<string | null>(null)
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null)
  const [showFilters, setShowFilters] = useState(false)
  const [partyDropdownOpen, setPartyDropdownOpen] = useState(false)
  const [partySearch, setPartySearch] = useState('')
  const [clientDropdownOpen, setClientDropdownOpen] = useState(false)
  const [selectedContracts, setSelectedContracts] = useState<Set<string>>(new Set())
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [viewMode, setViewMode] = useState<'table' | 'tree'>('table')
  const pageSize = 10
  const partyDropdownRef = useRef<HTMLDivElement>(null)
  const partyInputRef = useRef<HTMLInputElement>(null)
  const clientDropdownRef = useRef<HTMLDivElement>(null)

  // Fetch filter options
  const { data: filterOptions } = useQuery({
    queryKey: ['contract-filter-options'],
    queryFn: () => api.getContractFilterOptions(),
  })

  // Fetch contracts
  const { data, isLoading } = useQuery({
    queryKey: ['contracts', page, search, selectedCounterparty, selectedType, selectedRisk, selectedClientId],
    queryFn: () => api.getContracts({
      page,
      page_size: pageSize,
      search: search || undefined,
      counterparty: selectedCounterparty || undefined,
      contract_type: selectedType || undefined,
      risk_level: selectedRisk || undefined,
      client_id: selectedClientId || undefined,
    }),
  })

  // Tree view
  const { data: hierarchyData, isLoading: hierarchyLoading } = useQuery({
    queryKey: ['contract-hierarchy'],
    queryFn: () => api.getContractHierarchy(),
    enabled: viewMode === 'tree',
  })

  // Batch delete
  const deleteMutation = useMutation({
    mutationFn: (contractIds: string[]) => api.batchDeleteContracts(contractIds),
    onSuccess: () => {
      setSelectedContracts(new Set())
      setShowDeleteConfirm(false)
      queryClient.invalidateQueries({ queryKey: ['contracts'] })
      queryClient.invalidateQueries({ queryKey: ['contract-filter-options'] })
      queryClient.invalidateQueries({ queryKey: ['contracts-summary'] })
    },
  })

  const toggleContractSelection = (contractId: string) => {
    setSelectedContracts(prev => {
      const next = new Set(prev)
      if (next.has(contractId)) next.delete(contractId)
      else next.add(contractId)
      return next
    })
  }

  const toggleAllContracts = () => {
    if (!data?.items) return
    const allSelected = data.items.every(c => selectedContracts.has(c.id))
    if (allSelected) {
      setSelectedContracts(prev => {
        const next = new Set(prev)
        data.items.forEach(c => next.delete(c.id))
        return next
      })
    } else {
      setSelectedContracts(prev => {
        const next = new Set(prev)
        data.items.forEach(c => next.add(c.id))
        return next
      })
    }
  }

  // Close dropdowns on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (partyDropdownRef.current && !partyDropdownRef.current.contains(event.target as Node)) setPartyDropdownOpen(false)
      if (clientDropdownRef.current && !clientDropdownRef.current.contains(event.target as Node)) setClientDropdownOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    if (partyDropdownOpen && partyInputRef.current) partyInputRef.current.focus()
  }, [partyDropdownOpen])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSearch(searchInput)
    setPage(1)
  }

  const clearFilters = () => {
    setSelectedCounterparty(null)
    setSelectedType(null)
    setSelectedRisk(null)
    setSelectedClientId(null)
    setPage(1)
  }

  const hasActiveFilters = selectedCounterparty || selectedRisk || selectedClientId
  const selectedClient = filterOptions?.clients?.find((c: any) => c.id === selectedClientId)
  const filteredCounterparties = filterOptions?.counterparties.filter((cp: string) =>
    cp.toLowerCase().includes(partySearch.toLowerCase())
  ) || []

  // Pagination helpers
  const totalPages = data?.pages || 1
  const startItem = data ? (data.page - 1) * pageSize + 1 : 0
  const endItem = data ? Math.min(data.page * pageSize, data.total) : 0

  function getPageNumbers(): (number | '...')[] {
    if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1)
    const pages: (number | '...')[] = [1]
    if (page > 3) pages.push('...')
    for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) {
      pages.push(i)
    }
    if (page < totalPages - 2) pages.push('...')
    pages.push(totalPages)
    return pages
  }

  return (
    <div className="space-y-6">
      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-red-100 rounded-full">
                <ExclamationTriangleIcon className="h-6 w-6 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">
                {t('contracts.deleteConfirmTitle', { count: selectedContracts.size })}
              </h3>
            </div>
            <p className="text-sm text-gray-600 mb-6">
              {t('contracts.deleteConfirmBody')}
            </p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setShowDeleteConfirm(false)} disabled={deleteMutation.isPending} className="btn-secondary">
                {t('common.cancel')}
              </button>
              <button
                onClick={() => deleteMutation.mutate(Array.from(selectedContracts))}
                disabled={deleteMutation.isPending}
                className="btn-primary bg-red-600 hover:bg-red-700 focus:ring-red-500 flex items-center gap-2"
              >
                {deleteMutation.isPending ? <><LoadingSpinner size="sm" /> {t('contracts.deleting')}</> : <><TrashIcon className="h-4 w-4" /> {t('common.delete')}</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('nav.contracts')}</h1>
          <p className="mt-1 text-sm text-gray-500">{t('contracts.subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          {selectedContracts.size > 0 && (
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 bg-white border border-red-200 rounded-lg hover:bg-red-50 transition-colors"
            >
              <TrashIcon className="h-4 w-4" />
              {t('common.delete')} ({selectedContracts.size})
            </button>
          )}
          <Link
            to="/upload"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary-700 rounded-lg hover:bg-primary-800 transition-colors"
          >
            <PlusIcon className="h-4 w-4" />
            {t('nav.upload')}
          </Link>
        </div>
      </div>

      {/* Search bar - full width */}
      <form onSubmit={handleSearch}>
        <div className="relative">
          <MagnifyingGlassIcon className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            placeholder={t('contracts.searchPlaceholder')}
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-full pl-12 pr-4 py-3 text-sm bg-white border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-200 focus:border-primary-400 transition-all"
          />
        </div>
      </form>

      {/* Type filter pills + advanced filter toggle */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => { setSelectedType(null); setPage(1) }}
            className={cn(
              'px-4 py-1.5 rounded-full text-sm font-medium border transition-all',
              !selectedType
                ? 'bg-primary-700 text-white border-primary-700'
                : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300 hover:bg-gray-50'
            )}
          >
            {t('contracts.all')}
          </button>
          {(filterOptions?.contract_types || []).map((type: string) => (
            <button
              key={type}
              onClick={() => { setSelectedType(selectedType === type ? null : type); setPage(1) }}
              className={cn(
                'px-4 py-1.5 rounded-full text-sm font-medium border transition-all',
                selectedType === type
                  ? 'bg-primary-700 text-white border-primary-700'
                  : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300 hover:bg-gray-50'
              )}
            >
              {contractTypeLabel(type)}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={cn(
              'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border transition-colors',
              hasActiveFilters
                ? 'bg-primary-50 border-primary-300 text-primary-700'
                : 'bg-white border-gray-200 text-gray-500 hover:border-gray-300'
            )}
          >
            <FunnelIcon className="h-4 w-4" />
            {t('contracts.filters')}
          </button>
          {/* View mode toggle */}
          <div className="flex items-center bg-gray-100 rounded-lg p-0.5">
            <button onClick={() => setViewMode('table')} className={cn('p-1.5 rounded-md transition-colors', viewMode === 'table' ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700')} title={t('contracts.tableView')}>
              <ListBulletIcon className="h-4 w-4" />
            </button>
            <button onClick={() => setViewMode('tree')} className={cn('p-1.5 rounded-md transition-colors', viewMode === 'tree' ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700')} title={t('contracts.treeView')}>
              <Squares2X2Icon className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Advanced Filter Panel */}
      {showFilters && (
        <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Client Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('contracts.client')}</label>
              <div className="relative" ref={clientDropdownRef}>
                <button
                  onClick={() => setClientDropdownOpen(!clientDropdownOpen)}
                  className={cn(
                    'w-full flex items-center justify-between px-3 py-2 rounded-lg border text-left text-sm bg-white',
                    clientDropdownOpen ? 'border-primary-500 ring-2 ring-primary-100' : 'border-gray-300 hover:border-gray-400'
                  )}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <BuildingOfficeIcon className="h-4 w-4 text-gray-400 shrink-0" />
                    <span className={selectedClient ? 'truncate font-medium text-gray-900' : 'text-gray-500'}>
                      {selectedClient ? selectedClient.name : t('contracts.allClients')}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    {selectedClientId && (
                      <button onClick={(e) => { e.stopPropagation(); setSelectedClientId(null); setPage(1) }} className="p-0.5 hover:bg-gray-100 rounded">
                        <XMarkIcon className="h-4 w-4 text-gray-400" />
                      </button>
                    )}
                    <ChevronDownIcon className={cn('h-4 w-4 text-gray-400 transition-transform', clientDropdownOpen && 'rotate-180')} />
                  </div>
                </button>
                {clientDropdownOpen && (
                  <div className="absolute z-50 mt-1 w-full bg-white rounded-lg border border-gray-200 shadow-lg max-h-56 overflow-auto">
                    <button onClick={() => { setSelectedClientId(null); setClientDropdownOpen(false); setPage(1) }} className={cn('w-full flex items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50', !selectedClientId && 'bg-primary-50')}>
                      <span className={cn('font-medium', !selectedClientId ? 'text-primary-700' : 'text-gray-700')}>{t('contracts.allClients')}</span>
                    </button>
                    {filterOptions?.clients?.map((client: any) => (
                      <button key={client.id} onClick={() => { setSelectedClientId(client.id); setClientDropdownOpen(false); setPage(1) }} className={cn('w-full flex items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50', selectedClientId === client.id && 'bg-primary-50')}>
                        <span className={cn('truncate', selectedClientId === client.id ? 'text-primary-700 font-medium' : 'text-gray-700')}>
                          {client.name} <span className="text-gray-400">({client.code})</span>
                        </span>
                        <span className="text-gray-400 text-xs ml-2 shrink-0">{client.contract_count}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Counterparty Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('contracts.counterparty')}</label>
              <div className="relative" ref={partyDropdownRef}>
                <button
                  onClick={() => setPartyDropdownOpen(!partyDropdownOpen)}
                  className={cn(
                    'w-full flex items-center justify-between px-3 py-2 rounded-lg border text-left text-sm bg-white',
                    partyDropdownOpen ? 'border-primary-500 ring-2 ring-primary-100' : 'border-gray-300 hover:border-gray-400'
                  )}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <BuildingOfficeIcon className="h-4 w-4 text-gray-400 shrink-0" />
                    <span className={selectedCounterparty ? 'truncate font-medium text-gray-900' : 'text-gray-500'}>
                      {selectedCounterparty || t('contracts.allParties')}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    {selectedCounterparty && (
                      <button onClick={(e) => { e.stopPropagation(); setSelectedCounterparty(null); setPage(1) }} className="p-0.5 hover:bg-gray-100 rounded">
                        <XMarkIcon className="h-4 w-4 text-gray-400" />
                      </button>
                    )}
                    <ChevronDownIcon className={cn('h-4 w-4 text-gray-400 transition-transform', partyDropdownOpen && 'rotate-180')} />
                  </div>
                </button>
                {partyDropdownOpen && (
                  <div className="absolute z-50 mt-1 w-full bg-white rounded-lg border border-gray-200 shadow-lg">
                    <div className="p-2 border-b border-gray-100">
                      <div className="relative">
                        <MagnifyingGlassIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                        <input ref={partyInputRef} type="text" placeholder={t('contracts.searchParties')} value={partySearch} onChange={(e) => setPartySearch(e.target.value)} className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-primary-100 focus:border-primary-500" />
                      </div>
                    </div>
                    <div className="max-h-56 overflow-y-auto">
                      <button onClick={() => { setSelectedCounterparty(null); setPartyDropdownOpen(false); setPartySearch(''); setPage(1) }} className={cn('w-full flex items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50', !selectedCounterparty && 'bg-primary-50')}>
                        <span className={cn('font-medium', !selectedCounterparty ? 'text-primary-700' : 'text-gray-700')}>{t('contracts.allParties')}</span>
                      </button>
                      {filteredCounterparties.map((party: string) => (
                        <button key={party} onClick={() => { setSelectedCounterparty(party); setPartyDropdownOpen(false); setPartySearch(''); setPage(1) }} className={cn('w-full flex items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50', selectedCounterparty === party && 'bg-primary-50')}>
                          <span className={cn('truncate', selectedCounterparty === party ? 'text-primary-700 font-medium' : 'text-gray-700')}>{party}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Risk Level Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('contracts.riskLevel')}</label>
              <select value={selectedRisk || ''} onChange={(e) => { setSelectedRisk(e.target.value || null); setPage(1) }} className="input text-sm">
                <option value="">{t('contracts.allRiskLevels')}</option>
                {filterOptions?.risk_levels.map((risk: string) => (
                  <option key={risk} value={risk}>{t(`risk.${risk.toLowerCase()}`, { defaultValue: risk })}</option>
                ))}
              </select>
            </div>
          </div>
          {hasActiveFilters && (
            <div className="mt-3 flex items-center gap-2">
              <button onClick={clearFilters} className="text-sm text-primary-600 hover:text-primary-800 font-medium">
                {t('contracts.clearAllFilters')}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Tree View */}
      {viewMode === 'tree' && (
        hierarchyLoading ? (
          <div className="flex items-center justify-center h-64"><LoadingSpinner size="lg" /></div>
        ) : hierarchyData ? (
          <ContractTreeView roots={hierarchyData.roots} totalContracts={hierarchyData.total_contracts} totalLinks={hierarchyData.total_links} />
        ) : null
      )}

      {/* Table View */}
      {viewMode === 'table' && (isLoading ? (
        <div className="flex items-center justify-center h-64"><LoadingSpinner size="lg" /></div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead>
              <tr className="border-t-2 border-primary-500">
                <th className="px-4 py-3 w-10">
                  <input
                    type="checkbox"
                    checked={data?.items && data.items.length > 0 && data.items.every(c => selectedContracts.has(c.id))}
                    onChange={toggleAllContracts}
                    className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                </th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold text-gray-500 uppercase tracking-wider">{t('contracts.contractName')}</th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold text-gray-500 uppercase tracking-wider">{t('contracts.type')}</th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold text-gray-500 uppercase tracking-wider">{uiLabel('counterparty', t('contracts.counterparty'))}</th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold text-gray-500 uppercase tracking-wider">{t('common.status')}</th>
                <th className="px-4 py-3 text-right text-[11px] font-semibold text-gray-500 uppercase tracking-wider">{uiLabel('contract_value', t('contracts.value'))}</th>
                <th className="px-4 py-3 text-center text-[11px] font-semibold text-gray-500 uppercase tracking-wider">{t('contracts.risk')}</th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold text-gray-500 uppercase tracking-wider">{t('contracts.expiry')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data?.items.map((contract) => (
                <tr
                  key={contract.id}
                  className={cn(
                    'hover:bg-gray-50/50 transition-colors',
                    selectedContracts.has(contract.id) && 'bg-primary-50/50'
                  )}
                >
                  <td className="px-4 py-3.5">
                    <input
                      type="checkbox"
                      checked={selectedContracts.has(contract.id)}
                      onChange={() => toggleContractSelection(contract.id)}
                      className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                  </td>
                  <td className="px-4 py-3.5">
                    <Link
                      to={`/contracts/${contract.id}`}
                      className="text-sm font-medium text-gray-900 hover:text-primary-700 transition-colors"
                    >
                      {contract.filename.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' ')}
                    </Link>
                  </td>
                  <td className="px-4 py-3.5">
                    <span className="text-sm text-gray-600">
                      {contract.contract_type ? contractTypeLabel(contract.contract_type) : '\u2014'}
                    </span>
                  </td>
                  <td className="px-4 py-3.5">
                    <span className="text-sm text-gray-700">
                      {contract.counterparty || '\u2014'}
                    </span>
                  </td>
                  <td className="px-4 py-3.5">
                    <StatusBadge status={contract.status} />
                  </td>
                  <td className="px-4 py-3.5 text-right">
                    <span className="text-sm text-gray-700 font-medium tabular-nums">
                      {formatValue(contract.contract_value, contract.currency)}
                    </span>
                  </td>
                  <td className="px-4 py-3.5 text-center">
                    {contract.risk_level ? (
                      <RiskBadge level={contract.risk_level} />
                    ) : (
                      <span className="text-sm text-gray-400">{'\u2014'}</span>
                    )}
                  </td>
                  <td className="px-4 py-3.5">
                    <span className="text-sm text-gray-600">
                      {formatExpiry(contract.expiration_date)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Empty state */}
          {data?.items.length === 0 && (
            <div className="text-center py-12">
              <p className="text-gray-500">{t('contracts.noContractsFound')}</p>
              {hasActiveFilters && (
                <button onClick={clearFilters} className="mt-2 text-primary-600 hover:text-primary-800 text-sm">{t('contracts.clearAllFilters')}</button>
              )}
            </div>
          )}

          {/* Pagination */}
          {data && data.pages > 1 && (
            <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-between">
              <p className="text-sm text-gray-500">
                {t('contracts.showingRange', { start: startItem, end: endItem, total: data.total })}
              </p>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-2 py-1.5 text-sm text-gray-500 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  &lsaquo;
                </button>
                {getPageNumbers().map((p, i) =>
                  p === '...' ? (
                    <span key={`dots-${i}`} className="px-2 py-1.5 text-sm text-gray-400">&hellip;</span>
                  ) : (
                    <button
                      key={p}
                      onClick={() => setPage(p as number)}
                      className={cn(
                        'min-w-[32px] h-8 rounded-md text-sm font-medium transition-colors',
                        page === p
                          ? 'bg-primary-700 text-white'
                          : 'text-gray-600 hover:bg-gray-100'
                      )}
                    >
                      {p}
                    </button>
                  )
                )}
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-2 py-1.5 text-sm text-gray-500 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  &rsaquo;
                </button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
