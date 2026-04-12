import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import {
  MagnifyingGlassIcon,
  FunnelIcon,
  XMarkIcon,
  ChevronDownIcon,
  BuildingOfficeIcon,
  TrashIcon,
  ExclamationTriangleIcon,
  DocumentTextIcon,
  PlusIcon,
  ListBulletIcon,
  Squares2X2Icon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import PageHeader from '@/components/ui/PageHeader'
import StatCard from '@/components/ui/StatCard'
import ContractTreeView from '@/components/contracts/ContractTreeView'
import { cn, formatDate, getRiskColor, getStatusColor } from '@/lib/utils'

export default function ContractsPage() {
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
  const partyDropdownRef = useRef<HTMLDivElement>(null)
  const partyInputRef = useRef<HTMLInputElement>(null)
  const clientDropdownRef = useRef<HTMLDivElement>(null)

  // Fetch filter options
  const { data: filterOptions } = useQuery({
    queryKey: ['contract-filter-options'],
    queryFn: () => api.getContractFilterOptions(),
  })

  // Fetch contracts with filters
  const { data, isLoading } = useQuery({
    queryKey: ['contracts', page, search, selectedCounterparty, selectedType, selectedRisk, selectedClientId],
    queryFn: () => api.getContracts({
      page,
      page_size: 20,
      search: search || undefined,
      counterparty: selectedCounterparty || undefined,
      contract_type: selectedType || undefined,
      risk_level: selectedRisk || undefined,
      client_id: selectedClientId || undefined,
    }),
  })

  // Fetch contract hierarchy for tree view
  const { data: hierarchyData, isLoading: hierarchyLoading } = useQuery({
    queryKey: ['contract-hierarchy'],
    queryFn: () => api.getContractHierarchy(),
    enabled: viewMode === 'tree',
  })

  // Batch delete mutation
  const deleteMutation = useMutation({
    mutationFn: (contractIds: string[]) => api.batchDeleteContracts(contractIds),
    onSuccess: () => {
      // Clear selection and refresh data
      setSelectedContracts(new Set())
      setShowDeleteConfirm(false)
      // Invalidate all related queries
      queryClient.invalidateQueries({ queryKey: ['contracts'] })
      queryClient.invalidateQueries({ queryKey: ['contract-filter-options'] })
      queryClient.invalidateQueries({ queryKey: ['contracts-summary'] })
      queryClient.invalidateQueries({ queryKey: ['obligations-summary'] })
      queryClient.invalidateQueries({ queryKey: ['clauses-summary'] })
      queryClient.invalidateQueries({ queryKey: ['clients-summary'] })
    },
  })

  // Toggle single contract selection
  const toggleContractSelection = (contractId: string) => {
    setSelectedContracts(prev => {
      const next = new Set(prev)
      if (next.has(contractId)) {
        next.delete(contractId)
      } else {
        next.add(contractId)
      }
      return next
    })
  }

  // Toggle all contracts on current page
  const toggleAllContracts = () => {
    if (!data?.items) return
    const allSelected = data.items.every(c => selectedContracts.has(c.id))
    if (allSelected) {
      // Deselect all on current page
      setSelectedContracts(prev => {
        const next = new Set(prev)
        data.items.forEach(c => next.delete(c.id))
        return next
      })
    } else {
      // Select all on current page
      setSelectedContracts(prev => {
        const next = new Set(prev)
        data.items.forEach(c => next.add(c.id))
        return next
      })
    }
  }

  const handleBatchDelete = () => {
    if (selectedContracts.size === 0) return
    deleteMutation.mutate(Array.from(selectedContracts))
  }

  // Close dropdowns when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (partyDropdownRef.current && !partyDropdownRef.current.contains(event.target as Node)) {
        setPartyDropdownOpen(false)
      }
      if (clientDropdownRef.current && !clientDropdownRef.current.contains(event.target as Node)) {
        setClientDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Focus input when dropdown opens
  useEffect(() => {
    if (partyDropdownOpen && partyInputRef.current) {
      partyInputRef.current.focus()
    }
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

  const hasActiveFilters = selectedCounterparty || selectedType || selectedRisk || selectedClientId

  const selectedClient = filterOptions?.clients?.find((c: any) => c.id === selectedClientId)

  // Filter counterparties by search
  const filteredCounterparties = filterOptions?.counterparties.filter(cp =>
    cp.toLowerCase().includes(partySearch.toLowerCase())
  ) || []

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
                Delete {selectedContracts.size} Contract{selectedContracts.size > 1 ? 's' : ''}?
              </h3>
            </div>
            <p className="text-sm text-gray-600 mb-6">
              This will permanently delete the selected contracts, including all associated files,
              clauses, obligations, and vector embeddings. This action cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                disabled={deleteMutation.isPending}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleBatchDelete}
                disabled={deleteMutation.isPending}
                className="btn-primary bg-red-600 hover:bg-red-700 focus:ring-red-500 flex items-center gap-2"
              >
                {deleteMutation.isPending ? (
                  <>
                    <LoadingSpinner size="sm" />
                    Deleting...
                  </>
                ) : (
                  <>
                    <TrashIcon className="h-4 w-4" />
                    Delete
                  </>
                )}
              </button>
            </div>
            {deleteMutation.isError && (
              <p className="mt-3 text-sm text-red-600">
                Error: {(deleteMutation.error as Error).message}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Header */}
      <PageHeader
        title="Contracts"
        description="Browse and manage your contract documents"
        icon={DocumentTextIcon}
        variant="bordered"
        actions={
          <div className="flex items-center gap-3">
            {selectedContracts.size > 0 && (
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 bg-white border border-red-200 rounded-lg hover:bg-red-50 transition-colors"
              >
                <TrashIcon className="h-4 w-4" />
                Delete ({selectedContracts.size})
              </button>
            )}
            <Link
              to="/upload"
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 transition-colors"
            >
              <PlusIcon className="h-4 w-4" />
              Upload Contract
            </Link>
          </div>
        }
      />

      {/* Quick Stats - Personio-style filled widgets */}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            title="Total Contracts"
            value={data.total}
            icon={DocumentTextIcon}
            color="primary"
            variant="filled"
            chart={[5, 8, 6, 9, 7, 11, 10, 12]}
          />
          <StatCard
            title="High Risk"
            value={data.items.filter(c => c.risk_level === 'high' || c.risk_level === 'critical').length}
            icon={ExclamationTriangleIcon}
            color="danger"
            variant="filled"
            chart={[6, 5, 4, 5, 3, 2, 3, 2]}
          />
          <StatCard
            title="Processing"
            value={data.items.filter(c => c.status === 'processing').length}
            icon={DocumentTextIcon}
            color="warning"
            variant="filled"
          />
          <StatCard
            title="Completed"
            value={data.items.filter(c => c.status === 'completed').length}
            icon={DocumentTextIcon}
            color="success"
            variant="filled"
            chart={[8, 10, 12, 15, 14, 18, 20, 22]}
          />
        </div>
      )}

      {/* Search and filters */}
      <div className="space-y-4">
        <div className="flex items-center gap-4">
          <form onSubmit={handleSearch} className="flex-1 max-w-md">
            <div className="relative">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search contracts..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="input pl-10"
              />
            </div>
          </form>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={cn(
              "btn-secondary",
              hasActiveFilters && "ring-2 ring-primary-500"
            )}
          >
            <FunnelIcon className="h-4 w-4 mr-2" />
            Filters
            {hasActiveFilters && (
              <span className="ml-1 bg-primary-500 text-white text-xs px-1.5 py-0.5 rounded-full">
                {[selectedCounterparty, selectedType, selectedRisk].filter(Boolean).length}
              </span>
            )}
          </button>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Clear all
            </button>
          )}
          {/* View mode toggle */}
          <div className="flex items-center bg-gray-100 rounded-lg p-0.5 ml-auto">
            <button
              onClick={() => setViewMode('table')}
              className={cn(
                'p-1.5 rounded-md transition-colors',
                viewMode === 'table' ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700'
              )}
              title="Table view"
            >
              <ListBulletIcon className="h-4 w-4" />
            </button>
            <button
              onClick={() => setViewMode('tree')}
              className={cn(
                'p-1.5 rounded-md transition-colors',
                viewMode === 'tree' ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700'
              )}
              title="Tree view"
            >
              <Squares2X2Icon className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Filter Panel */}
        {showFilters && (
          <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {/* Client Filter */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Client
                </label>
                <div className="relative" ref={clientDropdownRef}>
                  <button
                    onClick={() => setClientDropdownOpen(!clientDropdownOpen)}
                    className={cn(
                      "w-full flex items-center justify-between px-3 py-2 rounded-lg border text-left text-sm transition-colors bg-white",
                      clientDropdownOpen
                        ? "border-primary-500 ring-2 ring-primary-100"
                        : "border-gray-300 hover:border-gray-400"
                    )}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <BuildingOfficeIcon className="h-4 w-4 text-gray-400 flex-shrink-0" />
                      {selectedClient ? (
                        <span className="truncate font-medium text-gray-900">
                          {selectedClient.name}
                        </span>
                      ) : (
                        <span className="text-gray-500">All Clients</span>
                      )}
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      {selectedClientId && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            setSelectedClientId(null)
                            setPage(1)
                          }}
                          className="p-0.5 hover:bg-gray-100 rounded"
                        >
                          <XMarkIcon className="h-4 w-4 text-gray-400" />
                        </button>
                      )}
                      <ChevronDownIcon className={cn(
                        "h-4 w-4 text-gray-400 transition-transform",
                        clientDropdownOpen && "rotate-180"
                      )} />
                    </div>
                  </button>

                  {clientDropdownOpen && (
                    <div className="absolute z-50 mt-1 w-full bg-white rounded-lg border border-gray-200 shadow-lg max-h-56 overflow-auto">
                      <button
                        onClick={() => {
                          setSelectedClientId(null)
                          setClientDropdownOpen(false)
                          setPage(1)
                        }}
                        className={cn(
                          "w-full flex items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50 transition-colors",
                          !selectedClientId && "bg-primary-50"
                        )}
                      >
                        <span className={cn(
                          "font-medium",
                          !selectedClientId ? "text-primary-700" : "text-gray-700"
                        )}>
                          All Clients
                        </span>
                      </button>
                      {filterOptions?.clients?.map((client: any) => (
                        <button
                          key={client.id}
                          onClick={() => {
                            setSelectedClientId(client.id)
                            setClientDropdownOpen(false)
                            setPage(1)
                          }}
                          className={cn(
                            "w-full flex items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50 transition-colors",
                            selectedClientId === client.id && "bg-primary-50"
                          )}
                        >
                          <span className={cn(
                            "truncate",
                            selectedClientId === client.id ? "text-primary-700 font-medium" : "text-gray-700"
                          )}>
                            {client.name} <span className="text-gray-400">({client.code})</span>
                          </span>
                          <span className="text-gray-400 text-xs ml-2 flex-shrink-0">
                            {client.contract_count}
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Counterparty/Party Filter */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Party / Counterparty
                </label>
                <div className="relative" ref={partyDropdownRef}>
                  <button
                    onClick={() => setPartyDropdownOpen(!partyDropdownOpen)}
                    className={cn(
                      "w-full flex items-center justify-between px-3 py-2 rounded-lg border text-left text-sm transition-colors bg-white",
                      partyDropdownOpen
                        ? "border-primary-500 ring-2 ring-primary-100"
                        : "border-gray-300 hover:border-gray-400"
                    )}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <BuildingOfficeIcon className="h-4 w-4 text-gray-400 flex-shrink-0" />
                      {selectedCounterparty ? (
                        <span className="truncate font-medium text-gray-900">
                          {selectedCounterparty}
                        </span>
                      ) : (
                        <span className="text-gray-500">All Parties</span>
                      )}
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      {selectedCounterparty && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            setSelectedCounterparty(null)
                            setPage(1)
                          }}
                          className="p-0.5 hover:bg-gray-100 rounded"
                        >
                          <XMarkIcon className="h-4 w-4 text-gray-400" />
                        </button>
                      )}
                      <ChevronDownIcon className={cn(
                        "h-4 w-4 text-gray-400 transition-transform",
                        partyDropdownOpen && "rotate-180"
                      )} />
                    </div>
                  </button>

                  {/* Dropdown menu */}
                  {partyDropdownOpen && (
                    <div className="absolute z-50 mt-1 w-full bg-white rounded-lg border border-gray-200 shadow-lg">
                      {/* Search input */}
                      <div className="p-2 border-b border-gray-100">
                        <div className="relative">
                          <MagnifyingGlassIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                          <input
                            ref={partyInputRef}
                            type="text"
                            placeholder="Search parties..."
                            value={partySearch}
                            onChange={(e) => setPartySearch(e.target.value)}
                            className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-primary-100 focus:border-primary-500"
                          />
                        </div>
                      </div>

                      {/* Options list */}
                      <div className="max-h-56 overflow-y-auto">
                        {/* All Parties option */}
                        <button
                          onClick={() => {
                            setSelectedCounterparty(null)
                            setPartyDropdownOpen(false)
                            setPartySearch('')
                            setPage(1)
                          }}
                          className={cn(
                            "w-full flex items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50 transition-colors",
                            selectedCounterparty === null && "bg-primary-50"
                          )}
                        >
                          <span className={cn(
                            "font-medium",
                            selectedCounterparty === null ? "text-primary-700" : "text-gray-700"
                          )}>
                            All Parties
                          </span>
                          <span className="text-gray-400 text-xs">
                            ({filterOptions?.counterparties.length || 0})
                          </span>
                        </button>

                        {/* Filtered counterparties */}
                        {filteredCounterparties.length > 0 ? (
                          filteredCounterparties.map((party) => {
                            const count = filterOptions?.counterparty_counts[party] || 0
                            const isSelected = selectedCounterparty === party

                            return (
                              <button
                                key={party}
                                onClick={() => {
                                  setSelectedCounterparty(party)
                                  setPartyDropdownOpen(false)
                                  setPartySearch('')
                                  setPage(1)
                                }}
                                className={cn(
                                  "w-full flex items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50 transition-colors",
                                  isSelected && "bg-primary-50"
                                )}
                              >
                                <span className={cn(
                                  "truncate",
                                  isSelected ? "text-primary-700 font-medium" : "text-gray-700"
                                )}>
                                  {party}
                                </span>
                                <span className="text-gray-400 text-xs ml-2 flex-shrink-0">
                                  {count}
                                </span>
                              </button>
                            )
                          })
                        ) : (
                          <div className="px-3 py-4 text-center text-sm text-gray-500">
                            No parties found matching "{partySearch}"
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Contract Type Filter */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Contract Type
                </label>
                <select
                  value={selectedType || ''}
                  onChange={(e) => {
                    setSelectedType(e.target.value || null)
                    setPage(1)
                  }}
                  className="input text-sm"
                >
                  <option value="">All Types</option>
                  {filterOptions?.contract_types.map((type) => (
                    <option key={type} value={type}>
                      {type.toUpperCase()}
                    </option>
                  ))}
                </select>
              </div>

              {/* Risk Level Filter */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Risk Level
                </label>
                <select
                  value={selectedRisk || ''}
                  onChange={(e) => {
                    setSelectedRisk(e.target.value || null)
                    setPage(1)
                  }}
                  className="input text-sm"
                >
                  <option value="">All Risk Levels</option>
                  {filterOptions?.risk_levels.map((risk) => (
                    <option key={risk} value={risk}>
                      {risk.charAt(0).toUpperCase() + risk.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        )}

        {/* Active Filters Tags */}
        {hasActiveFilters && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm text-gray-500">Active filters:</span>
            {selectedCounterparty && (
              <span className="inline-flex items-center gap-1 bg-primary-100 text-primary-800 text-xs px-2 py-1 rounded-full">
                <BuildingOfficeIcon className="h-3 w-3" />
                {selectedCounterparty}
                <button
                  onClick={() => { setSelectedCounterparty(null); setPage(1); }}
                  className="hover:text-primary-900"
                >
                  <XMarkIcon className="h-3 w-3" />
                </button>
              </span>
            )}
            {selectedType && (
              <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-full">
                Type: {selectedType.toUpperCase()}
                <button
                  onClick={() => { setSelectedType(null); setPage(1); }}
                  className="hover:text-blue-900"
                >
                  <XMarkIcon className="h-3 w-3" />
                </button>
              </span>
            )}
            {selectedRisk && (
              <span className="inline-flex items-center gap-1 bg-amber-100 text-amber-800 text-xs px-2 py-1 rounded-full">
                Risk: {selectedRisk}
                <button
                  onClick={() => { setSelectedRisk(null); setPage(1); }}
                  className="hover:text-amber-900"
                >
                  <XMarkIcon className="h-3 w-3" />
                </button>
              </span>
            )}
            {selectedClient && (
              <span className="inline-flex items-center gap-1 bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full">
                <BuildingOfficeIcon className="h-3 w-3" />
                Client: {selectedClient.name}
                <button
                  onClick={() => { setSelectedClientId(null); setPage(1); }}
                  className="hover:text-green-900"
                >
                  <XMarkIcon className="h-3 w-3" />
                </button>
              </span>
            )}
          </div>
        )}
      </div>

      {/* Tree View */}
      {viewMode === 'tree' && (
        hierarchyLoading ? (
          <div className="flex items-center justify-center h-64">
            <LoadingSpinner size="lg" />
          </div>
        ) : hierarchyData ? (
          <ContractTreeView
            roots={hierarchyData.roots}
            totalContracts={hierarchyData.total_contracts}
            totalLinks={hierarchyData.total_links}
          />
        ) : null
      )}

      {/* Table */}
      {viewMode === 'table' && (isLoading ? (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size="lg" />
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50/80">
              <tr>
                <th className="px-4 py-3 w-10">
                  <input
                    type="checkbox"
                    checked={data?.items && data.items.length > 0 && data.items.every(c => selectedContracts.has(c.id))}
                    onChange={toggleAllContracts}
                    className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Type
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Counterparty
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Risk
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Uploaded
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {data?.items.map((contract) => (
                <tr
                  key={contract.id}
                  className={cn(
                    "hover:bg-gray-50",
                    selectedContracts.has(contract.id) && "bg-primary-50"
                  )}
                >
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selectedContracts.has(contract.id)}
                      onChange={() => toggleContractSelection(contract.id)}
                      className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/contracts/${contract.id}`}
                      className="text-sm font-medium text-primary-600 hover:text-primary-800"
                    >
                      {contract.filename}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-sm text-gray-900 capitalize">
                      {contract.contract_type?.toUpperCase() || '-'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {contract.counterparty ? (
                      <button
                        onClick={() => {
                          setSelectedCounterparty(contract.counterparty || null)
                          setShowFilters(true)
                          setPage(1)
                        }}
                        className="text-sm text-gray-700 hover:text-primary-600 hover:underline"
                      >
                        {contract.counterparty}
                      </button>
                    ) : (
                      <span className="text-sm text-gray-400">-</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize',
                      getStatusColor(contract.status)
                    )}>
                      {contract.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {contract.risk_level ? (
                      <span className={cn(
                        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize',
                        getRiskColor(contract.risk_level)
                      )}>
                        {contract.risk_level}
                      </span>
                    ) : (
                      <span className="text-sm text-gray-400">-</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-sm text-gray-500">
                      {formatDate(contract.uploaded_at)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Empty state */}
          {data?.items.length === 0 && (
            <div className="text-center py-12">
              <p className="text-gray-500">No contracts found matching your filters.</p>
              {hasActiveFilters && (
                <button
                  onClick={clearFilters}
                  className="mt-2 text-primary-600 hover:text-primary-800 text-sm"
                >
                  Clear all filters
                </button>
              )}
            </div>
          )}

          {/* Pagination */}
          {data && data.pages > 1 && (
            <div className="bg-white px-4 py-3 border-t border-gray-200 flex items-center justify-between">
              <p className="text-sm text-gray-700">
                Page {data.page} of {data.pages} ({data.total} total)
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="btn-secondary text-sm disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                  disabled={page === data.pages}
                  className="btn-secondary text-sm disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
