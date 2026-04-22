import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  ChevronDownIcon,
  ChevronRightIcon,
  BuildingOfficeIcon,
  XMarkIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  ClipboardDocumentCheckIcon,
  CalendarDaysIcon,
  ClockIcon,
} from '@heroicons/react/24/outline'
import { useAuth } from '@/contexts/AuthContext'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import StatCard from '@/components/ui/StatCard'
import AdminDashboard from '@/components/dashboard/AdminDashboard'
import LegalDashboard from '@/components/dashboard/LegalDashboard'
import ProcurementDashboard from '@/components/dashboard/ProcurementDashboard'
import { cn, formatDate } from '@/lib/utils'

export default function DashboardPage() {
  const { user, isAdmin, isLegal, isProcurement } = useAuth()
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

  // Fetch contracts summary
  const { data: contractsSummary, isLoading: contractsLoading } = useQuery({
    queryKey: ['contracts-summary', selectedClientId],
    queryFn: () => api.getContractsSummary(selectedClientId || undefined),
  })

  // Fetch obligations summary
  const { data: obligationsData } = useQuery({
    queryKey: ['obligations-summary', null, selectedClientId],
    queryFn: () => api.getObligationsSummary(undefined, selectedClientId || undefined),
  })

  // Fetch dashboard data based on role
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

  // Derived stats
  const totalContracts = contractsSummary?.total_contracts || 0
  const highRisk = (contractsSummary?.by_risk?.high || 0) + (contractsSummary?.by_risk?.critical || 0)
  const expiringSoon = contractsSummary?.expiring_soon || 0
  const totalObligations = obligationsData?.total || 0
  const overdueObligations = obligationsData?.by_status?.overdue || 0
  const complianceRate = totalObligations > 0
    ? ((totalObligations - overdueObligations) / totalObligations * 100).toFixed(1)
    : '100'

  // Recent activity from legal dashboard
  const recentActivity = legalData?.recent_activity?.slice(0, 5) || []

  // Upcoming expirations
  const upcomingExpirations = legalData?.expiration_timeline?.next_30_days?.slice(0, 5) || []

  return (
    <div className="space-y-6">
      {/* Page header with client filter */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Welcome back, {user?.full_name || user?.username}
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Here's an overview of your contract portfolio.
          </p>
        </div>

        {/* Client Filter */}
        <div className="relative" ref={clientDropdownRef}>
          <button
            onClick={() => setClientDropdownOpen(!clientDropdownOpen)}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-lg border text-sm transition-colors",
              selectedClientId
                ? "bg-primary-50 border-primary-300 text-primary-700"
                : "bg-white border-gray-300 text-gray-700 hover:bg-gray-50"
            )}
          >
            <BuildingOfficeIcon className="h-4 w-4" />
            {selectedClient ? (
              <>
                <span className="font-medium">{selectedClient.name}</span>
                <button
                  onClick={(e) => { e.stopPropagation(); setSelectedClientId(null) }}
                  className="p-0.5 hover:bg-primary-100 rounded"
                >
                  <XMarkIcon className="h-4 w-4" />
                </button>
              </>
            ) : (
              <span>Filter by Client</span>
            )}
            <ChevronDownIcon className={cn("h-4 w-4 transition-transform", clientDropdownOpen && "rotate-180")} />
          </button>

          {clientDropdownOpen && (
            <div className="absolute right-0 z-50 mt-1 w-64 bg-white rounded-lg border border-gray-200 shadow-lg max-h-64 overflow-auto">
              <button
                onClick={() => { setSelectedClientId(null); setClientDropdownOpen(false) }}
                className={cn("w-full flex items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50", !selectedClientId && "bg-primary-50")}
              >
                <span className="font-medium text-gray-700">All Clients</span>
              </button>
              {clientsData?.map((client) => (
                <button
                  key={client.id}
                  onClick={() => { setSelectedClientId(client.id); setClientDropdownOpen(false) }}
                  className={cn("w-full flex items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50", selectedClientId === client.id && "bg-primary-50")}
                >
                  <span className={cn("truncate", selectedClientId === client.id ? "text-primary-700 font-medium" : "text-gray-700")}>
                    {client.name} <span className="text-gray-400">({client.code})</span>
                  </span>
                  <span className="text-gray-400 text-xs ml-2">{client.contract_count}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Top Stat Cards — single row */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <StatCard
          title="Total Contracts"
          value={totalContracts}
          color="primary"
          subtitle={`${contractsSummary?.by_status?.completed || 0} processed`}
        />
        <StatCard
          title="At Risk"
          value={highRisk}
          color="danger"
          subtitle="High + Critical"
        />
        <StatCard
          title="Obligations"
          value={`${complianceRate}%`}
          color="success"
          subtitle={`${overdueObligations} overdue of ${totalObligations}`}
        />
        <StatCard
          title="Expiring Soon"
          value={expiringSoon}
          color="warning"
          subtitle="Next 90 days"
        />
        <StatCard
          title="Total Value"
          value={(() => {
            const contracts = contractsSummary?.contracts || []
            const sum = contracts.reduce((acc: number, c: any) => acc + (c.contract_value || 0), 0)
            if (sum >= 1_000_000) return `$${(sum / 1_000_000).toFixed(1)}M`
            if (sum >= 1_000) return `$${(sum / 1_000).toFixed(0)}K`
            return `$${sum}`
          })()}
          color="blue"
          subtitle="Portfolio value"
        />
      </div>

      {/* Two-column layout: Upcoming Expirations + Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upcoming Expirations */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
              <CalendarDaysIcon className="h-4 w-4 text-amber-500" />
              Expiring Soon
            </h3>
            <Link to="/renewals" className="text-xs text-primary-600 hover:text-primary-800 font-medium">
              View all
            </Link>
          </div>
          <div className="divide-y divide-gray-100">
            {upcomingExpirations.length > 0 ? (
              upcomingExpirations.map((item: any) => (
                <Link
                  key={item.id || item.contract_id}
                  to={`/contracts/${item.id || item.contract_id}`}
                  className="flex items-center justify-between px-5 py-3 hover:bg-gray-50 transition-colors"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900 truncate">{item.filename}</p>
                    <p className="text-xs text-gray-500 truncate">{item.counterparty || 'Unknown party'}</p>
                  </div>
                  <div className="text-right shrink-0 ml-4">
                    <p className="text-sm text-amber-600 font-medium">{formatDate(item.expiration_date)}</p>
                    {item.days_until_expiry != null && (
                      <p className="text-xs text-gray-500">{item.days_until_expiry}d left</p>
                    )}
                  </div>
                </Link>
              ))
            ) : (
              <div className="px-5 py-8 text-center text-sm text-gray-400">No contracts expiring soon</div>
            )}
          </div>
        </div>

        {/* Recent Activity */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
              <ClockIcon className="h-4 w-4 text-primary-500" />
              Recent Activity
            </h3>
          </div>
          <div className="divide-y divide-gray-100">
            {recentActivity.length > 0 ? (
              recentActivity.map((item: any, i: number) => (
                <div key={i} className="flex items-center gap-3 px-5 py-3">
                  <div className={cn(
                    'h-8 w-8 rounded-full flex items-center justify-center shrink-0',
                    item.action === 'upload' ? 'bg-blue-100' :
                    item.action === 'analyze' ? 'bg-purple-100' :
                    item.action === 'query' ? 'bg-emerald-100' : 'bg-gray-100'
                  )}>
                    <DocumentTextIcon className={cn(
                      'h-4 w-4',
                      item.action === 'upload' ? 'text-blue-600' :
                      item.action === 'analyze' ? 'text-purple-600' :
                      item.action === 'query' ? 'text-emerald-600' : 'text-gray-500'
                    )} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-gray-900 truncate">
                      <span className="font-medium capitalize">{item.action}</span>
                      {' '}{item.resource_type}
                    </p>
                    <p className="text-xs text-gray-500">{item.user} &middot; {formatDate(item.timestamp)}</p>
                  </div>
                </div>
              ))
            ) : (
              <div className="px-5 py-8 text-center text-sm text-gray-400">No recent activity</div>
            )}
          </div>
        </div>
      </div>

      {/* Obligation Breakdown — compact horizontal bar */}
      {obligationsData && obligationsData.total > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
              <ClipboardDocumentCheckIcon className="h-4 w-4 text-primary-500" />
              Obligations by Type
              <span className="text-xs font-normal text-gray-500">({obligationsData.total} total)</span>
            </h3>
            <Link to="/compliance" className="text-xs text-primary-600 hover:text-primary-800 font-medium">
              View all
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {obligationsData.by_type.map((item: any) => {
              const colors: Record<string, string> = {
                payment: 'border-t-emerald-500',
                delivery: 'border-t-blue-500',
                reporting: 'border-t-purple-500',
                compliance: 'border-t-amber-500',
                notification: 'border-t-cyan-500',
                performance: 'border-t-indigo-500',
              }
              const textColors: Record<string, string> = {
                payment: 'text-emerald-700',
                delivery: 'text-blue-700',
                reporting: 'text-purple-700',
                compliance: 'text-amber-700',
                notification: 'text-cyan-700',
                performance: 'text-indigo-700',
              }
              const labels: Record<string, string> = {
                payment: 'Payment',
                delivery: 'Delivery',
                reporting: 'Reporting',
                compliance: 'Compliance',
                notification: 'Notification',
                performance: 'Performance',
              }
              return (
                <div
                  key={item.obligation_type}
                  className={cn(
                    'rounded-lg border border-gray-200 border-t-[3px] p-3',
                    colors[item.obligation_type] || 'border-t-gray-400'
                  )}
                >
                  <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
                    {labels[item.obligation_type] || item.obligation_type}
                  </p>
                  <p className={cn(
                    'text-xl font-bold mt-1',
                    textColors[item.obligation_type] || 'text-gray-700'
                  )}>
                    {item.count}
                  </p>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* High Risk Contracts — compact table */}
      {legalData && legalData.risk_overview.high_risk_contracts.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
              <ExclamationTriangleIcon className="h-4 w-4 text-red-500" />
              High Risk Contracts
            </h3>
            <Link to="/contracts?risk=high" className="text-xs text-primary-600 hover:text-primary-800 font-medium">
              View all
            </Link>
          </div>
          <table className="min-w-full">
            <tbody className="divide-y divide-gray-100">
              {legalData.risk_overview.high_risk_contracts.slice(0, 5).map((contract) => (
                <tr key={contract.id} className="hover:bg-gray-50">
                  <td className="px-5 py-3">
                    <Link to={`/contracts/${contract.id}`} className="text-sm font-medium text-gray-900 hover:text-primary-700">
                      {contract.filename.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' ')}
                    </Link>
                  </td>
                  <td className="px-5 py-3">
                    <span className="text-sm text-gray-500">{contract.counterparty || '\u2014'}</span>
                  </td>
                  <td className="px-5 py-3 text-right">
                    <span className={cn(
                      'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
                      contract.risk_level === 'critical' ? 'bg-purple-100 text-purple-700' : 'bg-red-100 text-red-700'
                    )}>
                      {contract.risk_level}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right">
                    <span className="text-sm text-gray-500 tabular-nums">{contract.risk_score}/100</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Role-specific detailed sections — collapsible */}
      <div className="space-y-3 pt-4 border-t border-gray-200">
        <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider">
          Detailed Reports
        </h2>

        {isAdmin && adminData && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <button
              onClick={() => setShowAdminSection(!showAdminSection)}
              className="w-full px-5 py-3 flex items-center justify-between hover:bg-gray-50"
            >
              <span className="text-sm font-medium text-gray-900">System Administration</span>
              {showAdminSection ? <ChevronDownIcon className="h-5 w-5 text-gray-400" /> : <ChevronRightIcon className="h-5 w-5 text-gray-400" />}
            </button>
            <div className={cn("overflow-hidden transition-all", showAdminSection ? "max-h-[2000px]" : "max-h-0")}>
              <div className="p-4 border-t border-gray-200">
                <AdminDashboard data={adminData} />
              </div>
            </div>
          </div>
        )}

        {(isAdmin || isLegal) && legalData && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <button
              onClick={() => setShowLegalSection(!showLegalSection)}
              className="w-full px-5 py-3 flex items-center justify-between hover:bg-gray-50"
            >
              <span className="text-sm font-medium text-gray-900">Risk & Compliance</span>
              {showLegalSection ? <ChevronDownIcon className="h-5 w-5 text-gray-400" /> : <ChevronRightIcon className="h-5 w-5 text-gray-400" />}
            </button>
            <div className={cn("overflow-hidden transition-all", showLegalSection ? "max-h-[2000px]" : "max-h-0")}>
              <div className="p-4 border-t border-gray-200">
                <LegalDashboard data={legalData} />
              </div>
            </div>
          </div>
        )}

        {(isAdmin || isProcurement) && procurementData && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <button
              onClick={() => setShowProcurementSection(!showProcurementSection)}
              className="w-full px-5 py-3 flex items-center justify-between hover:bg-gray-50"
            >
              <span className="text-sm font-medium text-gray-900">Procurement & Vendors</span>
              {showProcurementSection ? <ChevronDownIcon className="h-5 w-5 text-gray-400" /> : <ChevronRightIcon className="h-5 w-5 text-gray-400" />}
            </button>
            <div className={cn("overflow-hidden transition-all", showProcurementSection ? "max-h-[2000px]" : "max-h-0")}>
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
