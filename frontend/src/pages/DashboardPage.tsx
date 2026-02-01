import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDownIcon, ChevronRightIcon } from '@heroicons/react/24/outline'
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
  const [showAdminSection, setShowAdminSection] = useState(false)
  const [showLegalSection, setShowLegalSection] = useState(false)
  const [showProcurementSection, setShowProcurementSection] = useState(false)

  // Fetch contracts summary for cards
  const { data: contractsSummary, isLoading: contractsLoading } = useQuery({
    queryKey: ['contracts-summary'],
    queryFn: () => api.getContractsSummary(),
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
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Welcome back, {user?.full_name || user?.username}
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          {getRoleGreeting()}
        </p>
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

      {/* Obligations Summary - filtered by selected contract */}
      <ObligationsSummary contractId={selectedContractId} />

      {/* Clauses Summary - filtered by selected contract */}
      <ClausesSummary contractId={selectedContractId} />

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
