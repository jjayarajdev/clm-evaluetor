import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  DocumentTextIcon,
  CheckCircleIcon,
  ClockIcon,
  XCircleIcon,
  MagnifyingGlassIcon,
  ChevronDownIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'
import type { ContractSummaryCard } from '@/types'

interface Props {
  contracts: ContractSummaryCard[]
  selectedContractId: string | null
  onSelectContract: (id: string | null) => void
  totalContracts: number
  byStatus: Record<string, number>
  byRisk: Record<string, number>
  expiringSoon: number
}

const STATUS_ICONS: Record<string, typeof DocumentTextIcon> = {
  completed: CheckCircleIcon,
  pending: ClockIcon,
  processing: ClockIcon,
  failed: XCircleIcon,
}

const STATUS_COLORS: Record<string, string> = {
  completed: 'text-green-600',
  pending: 'text-yellow-600',
  processing: 'text-blue-600',
  failed: 'text-red-600',
}

export default function ContractSummaryCards({
  contracts,
  selectedContractId,
  onSelectContract,
  totalContracts,
  byStatus,
  byRisk,
  expiringSoon,
}: Props) {
  const [isOpen, setIsOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const dropdownRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Focus input when dropdown opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isOpen])

  // Get display name for contract - prefer counterparty, fallback to cleaned filename
  const getDisplayName = (contract: ContractSummaryCard) => {
    // Use counterparty if it's a meaningful value (not generic placeholders)
    const genericCounterparties = ['null', 'the parties', 'parties', 'unknown', '']
    if (contract.counterparty && !genericCounterparties.includes(contract.counterparty.toLowerCase())) {
      return contract.counterparty
    }
    // Clean up filename - remove extension, underscores, and common suffixes
    let name = contract.filename
      .replace(/\.(pdf|docx?)$/i, '')  // Remove file extension
      .replace(/_/g, ' ')               // Replace underscores with spaces
      .replace(/-/g, ' ')               // Replace hyphens with spaces
      .replace(/\s+/g, ' ')             // Collapse multiple spaces
      .trim()

    // Extract meaningful name from common patterns like "NDA_CompanyName_Template"
    // or "MSA_VendorName_2024"
    const parts = name.split(' ')
    if (parts.length > 1) {
      // If starts with contract type prefix, try to get company name
      const typePattern = /^(NDA|MSA|SOW|SLA|Amendment|Vendor|Employment)/i
      if (typePattern.test(parts[0])) {
        // Get middle parts as the company name, skip first (type) and last (Template/Executed/etc)
        const skipSuffixes = ['template', 'executed', 'draft', 'final', 'v1', 'v2', 'signed']
        const nameParts = parts.slice(1).filter(p => !skipSuffixes.includes(p.toLowerCase()))
        if (nameParts.length > 0) {
          return `${parts[0]} - ${nameParts.join(' ')}`
        }
      }
    }
    return name
  }

  // Filter contracts based on search
  const filteredContracts = contracts.filter(contract => {
    const displayName = getDisplayName(contract).toLowerCase()
    const filename = contract.filename.toLowerCase()
    const query = searchQuery.toLowerCase()
    return displayName.includes(query) || filename.includes(query)
  })

  // Get selected contract details
  const selectedContract = selectedContractId
    ? contracts.find(c => c.id === selectedContractId)
    : null

  return (
    <div className="space-y-4">
      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-white rounded-lg border border-gray-200 p-3">
          <p className="text-2xl font-bold text-gray-900">{totalContracts}</p>
          <p className="text-xs text-gray-500">Total Contracts</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-3">
          <p className="text-2xl font-bold text-green-600">{byStatus.completed || 0}</p>
          <p className="text-xs text-gray-500">Processed</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-3">
          <p className="text-2xl font-bold text-red-600">{byRisk.high || 0}</p>
          <p className="text-xs text-gray-500">High Risk</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-3">
          <p className="text-2xl font-bold text-amber-600">{expiringSoon}</p>
          <p className="text-xs text-gray-500">Expiring Soon</p>
        </div>
      </div>

      {/* Contract Filter Dropdown */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <p className="text-sm font-medium text-gray-700 mb-3">Filter by Contract</p>

        <div className="relative" ref={dropdownRef}>
          {/* Dropdown trigger */}
          <button
            onClick={() => setIsOpen(!isOpen)}
            className={cn(
              "w-full flex items-center justify-between px-4 py-2.5 rounded-lg border text-left transition-colors",
              isOpen
                ? "border-primary-500 ring-2 ring-primary-100"
                : "border-gray-300 hover:border-gray-400"
            )}
          >
            <div className="flex items-center gap-2 min-w-0">
              {selectedContract ? (
                <>
                  {(() => {
                    const StatusIcon = STATUS_ICONS[selectedContract.status] || DocumentTextIcon
                    return <StatusIcon className={cn("h-5 w-5 flex-shrink-0", STATUS_COLORS[selectedContract.status])} />
                  })()}
                  <span className="truncate font-medium text-gray-900">
                    {getDisplayName(selectedContract)}
                  </span>
                  {selectedContract.risk_level && (
                    <span className={cn(
                      "w-2 h-2 rounded-full flex-shrink-0",
                      selectedContract.risk_level === 'high' || selectedContract.risk_level === 'critical' ? 'bg-red-500' :
                      selectedContract.risk_level === 'medium' ? 'bg-amber-500' : 'bg-green-500'
                    )} />
                  )}
                </>
              ) : (
                <>
                  <DocumentTextIcon className="h-5 w-5 text-gray-400 flex-shrink-0" />
                  <span className="text-gray-500">All Contracts ({totalContracts})</span>
                </>
              )}
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {selectedContract && (
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onSelectContract(null)
                  }}
                  className="p-1 hover:bg-gray-100 rounded"
                >
                  <XMarkIcon className="h-4 w-4 text-gray-400" />
                </button>
              )}
              <ChevronDownIcon className={cn(
                "h-5 w-5 text-gray-400 transition-transform",
                isOpen && "rotate-180"
              )} />
            </div>
          </button>

          {/* Dropdown menu */}
          {isOpen && (
            <div className="absolute z-50 mt-1 w-full bg-white rounded-lg border border-gray-200 shadow-lg">
              {/* Search input */}
              <div className="p-2 border-b border-gray-100">
                <div className="relative">
                  <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <input
                    ref={inputRef}
                    type="text"
                    placeholder="Search contracts..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-9 pr-4 py-2 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-100 focus:border-primary-500"
                  />
                </div>
              </div>

              {/* Options list */}
              <div className="max-h-64 overflow-y-auto">
                {/* All Contracts option */}
                <button
                  onClick={() => {
                    onSelectContract(null)
                    setIsOpen(false)
                    setSearchQuery('')
                  }}
                  className={cn(
                    "w-full flex items-center gap-2 px-4 py-2.5 text-left hover:bg-gray-50 transition-colors",
                    selectedContractId === null && "bg-primary-50"
                  )}
                >
                  <DocumentTextIcon className="h-5 w-5 text-gray-400 flex-shrink-0" />
                  <span className={cn(
                    "font-medium",
                    selectedContractId === null ? "text-primary-700" : "text-gray-700"
                  )}>
                    All Contracts
                  </span>
                  <span className="text-gray-400 text-sm">({totalContracts})</span>
                </button>

                {/* Filtered contracts */}
                {filteredContracts.length > 0 ? (
                  filteredContracts.map((contract) => {
                    const StatusIcon = STATUS_ICONS[contract.status] || DocumentTextIcon
                    const isSelected = selectedContractId === contract.id
                    const displayName = getDisplayName(contract)

                    return (
                      <button
                        key={contract.id}
                        onClick={() => {
                          onSelectContract(contract.id)
                          setIsOpen(false)
                          setSearchQuery('')
                        }}
                        title={contract.filename}
                        className={cn(
                          "w-full flex items-center gap-2 px-4 py-2.5 text-left hover:bg-gray-50 transition-colors",
                          isSelected && "bg-primary-50"
                        )}
                      >
                        <StatusIcon className={cn("h-5 w-5 flex-shrink-0", STATUS_COLORS[contract.status])} />
                        <span className={cn(
                          "truncate flex-1",
                          isSelected ? "text-primary-700 font-medium" : "text-gray-700"
                        )}>
                          {displayName}
                        </span>
                        {contract.risk_level && (
                          <span className={cn(
                            "w-2 h-2 rounded-full flex-shrink-0",
                            contract.risk_level === 'high' || contract.risk_level === 'critical' ? 'bg-red-500' :
                            contract.risk_level === 'medium' ? 'bg-amber-500' : 'bg-green-500'
                          )} />
                        )}
                      </button>
                    )
                  })
                ) : (
                  <div className="px-4 py-6 text-center text-sm text-gray-500">
                    No contracts found matching "{searchQuery}"
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Selected Contract Details */}
      {selectedContract && (
        <div className="bg-primary-50 border border-primary-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900">{selectedContract.filename}</p>
              <div className="flex items-center gap-3 mt-1 text-xs text-gray-600">
                {selectedContract.counterparty && <span>{selectedContract.counterparty}</span>}
                {selectedContract.contract_type && <span className="uppercase">{selectedContract.contract_type}</span>}
                <span>{selectedContract.clause_count} clauses</span>
                <span>{selectedContract.obligation_count} obligations</span>
              </div>
            </div>
            <Link
              to={`/contracts/${selectedContract.id}`}
              className="btn btn-primary text-sm"
            >
              View Details
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
