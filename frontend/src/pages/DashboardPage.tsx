import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDownIcon, ChevronRightIcon, BuildingOfficeIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { useAuth } from '@/contexts/AuthContext'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import AdminDashboard from '@/components/dashboard/AdminDashboard'
import LegalDashboard from '@/components/dashboard/LegalDashboard'
import ProcurementDashboard from '@/components/dashboard/ProcurementDashboard'
import ObligationsSummary from '@/components/dashboard/ObligationsSummary'
import ClausesSummary from '@/components/dashboard/ClausesSummary'
import ContractSummaryCards from '@/components/dashboard/ContractSummaryCards'
import { cn } from '@/lib/utils'

export default function DashboardPage() {
  const { user, isAdmin, isLegal, isProcurement } = useAuth()
  const [selectedContractId, setSelectedContractId] = useState<string | null>(null)
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null)
  const [clientDropdownOpen, setClientDropdownOpen] = useState(false)
  const [showAdminSection, setShowAdminSection] = useState(false)
  const [showLegalSection, setShowLegalSection] = useState(false)
  const [showProcurementSection, setShowProcurementSection] = useState(false)
  const clientDropdownRef = useRef<HTMLDivElement>(null)

  // Fetch clients for filter dropdown
  const { data: clientsData } = useQuery({
    queryKey: ['clients-summary'],
    queryFn: () => api.getClientsSummary(),
  })

  const selectedClient = clientsData?.find(c => c.id === selectedClientId)

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (clientDropdownRef.current && !clientDropdownRef.current.contains(event.target as Node)) {
        setClientDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Fetch contracts summary for cards (filtered by client if selected)
  const { data: contractsSummary, isLoading: contractsLoading } = useQuery({
    queryKey: ['contracts-summary', selectedClientId],
    queryFn: () => api.getContractsSummary(selectedClientId || undefined),
  })

  // Fetch appropriate dashboard data based on role
  const { data: adminData, isLoading: adminLoading } = useQuery({
    queryKey: ['dashboard', 'admin'],
    queryFn: () => api.getAdminDashboard(),
    enabled: isAdmin,
  })

  const { data: legalData, isLoading: legalLoading } = useQuery({
    queryKey: ['dashboard', 'legal'],
    queryFn: () => api.getLegalDashboard(),
    enabled: isAdmin || isLegal,
  })

  const { data: procurementData, isLoading: procurementLoading } = useQuery({
    queryKey: ['dashboard', 'procurement'],
    queryFn: () => api.getProcurementDashboard(),
    enabled: isAdmin || isProcurement,
  })

  const isLoading = contractsLoading || adminLoading || legalLoading || procurementLoading

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  // Role-specific greeting
  const getRoleGreeting = () => {
    if (isAdmin) return "Here's an overview of all contracts and obligations."
    if (isLegal) return "Focus on compliance and risk management."
    if (isProcurement) return "Track vendor obligations and renewals."
    return "Here's what's happening with your contracts."
  }

  return (
    <div className="space-y-6">
      {/* Page header with client filter */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Welcome back, {user?.full_name || user?.username}
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            {getRoleGreeting()}
          </p>
        </div>

        {/* Client Filter */}
        <div className="relative" ref={clientDropdownRef}>
          <button
            onClick={() => setClientDropdownOpen(!clientDropdownOpen)}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-lg border text-sm transition-colors",
              selectedClientId
                ? "bg-green-50 border-green-300 text-green-700"
                : "bg-white border-gray-300 text-gray-700 hover:bg-gray-50"
            )}
          >
            <BuildingOfficeIcon className="h-4 w-4" />
            {selectedClient ? (
              <>
                <span className="font-medium">{selectedClient.name}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setSelectedClientId(null)
                    setSelectedContractId(null)
                  }}
                  className="p-0.5 hover:bg-green-100 rounded"
                >
                  <XMarkIcon className="h-4 w-4" />
                </button>
              </>
            ) : (
              <span>Filter by Client</span>
            )}
            <ChevronDownIcon className={cn(
              "h-4 w-4 transition-transform",
              clientDropdownOpen && "rotate-180"
            )} />
          </button>

          {clientDropdownOpen && (
            <div className="absolute right-0 z-50 mt-1 w-64 bg-white rounded-lg border border-gray-200 shadow-lg max-h-64 overflow-auto">
              <button
                onClick={() => {
                  setSelectedClientId(null)
                  setSelectedContractId(null)
                  setClientDropdownOpen(false)
                }}
                className={cn(
                  "w-full flex items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50",
                  !selectedClientId && "bg-primary-50"
                )}
              >
                <span className="font-medium text-gray-700">All Clients</span>
              </button>
              {clientsData?.map((client) => (
                <button
                  key={client.id}
                  onClick={() => {
                    setSelectedClientId(client.id)
                    setSelectedContractId(null)
                    setClientDropdownOpen(false)
                  }}
                  className={cn(
                    "w-full flex items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50",
                    selectedClientId === client.id && "bg-primary-50"
                  )}
                >
                  <span className={cn(
                    "truncate",
                    selectedClientId === client.id ? "text-primary-700 font-medium" : "text-gray-700"
                  )}>
                    {client.name} <span className="text-gray-400">({client.code})</span>
                  </span>
                  <span className="text-gray-400 text-xs ml-2">{client.contract_count}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Contract Summary Cards - shown to all users */}
      {contractsSummary && (
        <ContractSummaryCards
          contracts={contractsSummary.contracts}
          selectedContractId={selectedContractId}
          onSelectContract={setSelectedContractId}
          totalContracts={contractsSummary.total_contracts}
          byStatus={contractsSummary.by_status}
          byRisk={contractsSummary.by_risk}
          expiringSoon={contractsSummary.expiring_soon}
        />
      )}

      {/* Obligations Summary - filtered by selected contract or client */}
      <ObligationsSummary contractId={selectedContractId} clientId={selectedClientId} />

      {/* Clauses Summary - filtered by selected contract or client */}
      <ClausesSummary contractId={selectedContractId} clientId={selectedClientId} />

      {/* Role-specific detailed sections */}
      <div className="space-y-4 pt-4 border-t border-gray-200">
        <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider">
          Detailed Reports
        </h2>

        {/* Admin Section - System overview */}
        {isAdmin && adminData && (
          <div className="card">
            <button
              onClick={() => setShowAdminSection(!showAdminSection)}
              className="w-full card-header flex items-center justify-between hover:bg-gray-50"
            >
              <span className="text-sm font-medium text-gray-900">
                System Administration
              </span>
              {showAdminSection ? (
                <ChevronDownIcon className="h-5 w-5 text-gray-400" />
              ) : (
                <ChevronRightIcon className="h-5 w-5 text-gray-400" />
              )}
            </button>
            <div className={cn(
              "overflow-hidden transition-all",
              showAdminSection ? "max-h-[2000px]" : "max-h-0"
            )}>
              <div className="p-4 border-t border-gray-200">
                <AdminDashboard data={adminData} />
              </div>
            </div>
          </div>
        )}

        {/* Legal Section - Risk & Compliance (default open for legal users) */}
        {(isAdmin || isLegal) && legalData && (
          <div className="card">
            <button
              onClick={() => setShowLegalSection(!showLegalSection)}
              className="w-full card-header flex items-center justify-between hover:bg-gray-50"
            >
              <span className="text-sm font-medium text-gray-900">
                Risk & Compliance
              </span>
              {showLegalSection ? (
                <ChevronDownIcon className="h-5 w-5 text-gray-400" />
              ) : (
                <ChevronRightIcon className="h-5 w-5 text-gray-400" />
              )}
            </button>
            <div className={cn(
              "overflow-hidden transition-all",
              showLegalSection ? "max-h-[2000px]" : "max-h-0"
            )}>
              <div className="p-4 border-t border-gray-200">
                <LegalDashboard data={legalData} />
              </div>
            </div>
          </div>
        )}

        {/* Procurement Section - Vendors & Renewals (default open for procurement users) */}
        {(isAdmin || isProcurement) && procurementData && (
          <div className="card">
            <button
              onClick={() => setShowProcurementSection(!showProcurementSection)}
              className="w-full card-header flex items-center justify-between hover:bg-gray-50"
            >
              <span className="text-sm font-medium text-gray-900">
                Procurement & Vendors
              </span>
              {showProcurementSection ? (
                <ChevronDownIcon className="h-5 w-5 text-gray-400" />
              ) : (
                <ChevronRightIcon className="h-5 w-5 text-gray-400" />
              )}
            </button>
            <div className={cn(
              "overflow-hidden transition-all",
              showProcurementSection ? "max-h-[2000px]" : "max-h-0"
            )}>
              <div className="p-4 border-t border-gray-200">
                <ProcurementDashboard data={procurementData} />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
