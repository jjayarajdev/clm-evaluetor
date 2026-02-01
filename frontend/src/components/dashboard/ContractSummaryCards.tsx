import { Link } from 'react-router-dom'
import {
  DocumentTextIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline'
import { cn, getRiskColor } from '@/lib/utils'
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

      {/* Contract Filter Pills */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => onSelectContract(null)}
          className={cn(
            "px-3 py-1.5 rounded-full text-sm font-medium transition-colors",
            selectedContractId === null
              ? "bg-primary-600 text-white"
              : "bg-gray-100 text-gray-700 hover:bg-gray-200"
          )}
        >
          All Contracts
        </button>
        {contracts.map((contract) => {
          const StatusIcon = STATUS_ICONS[contract.status] || DocumentTextIcon
          const isSelected = selectedContractId === contract.id

          return (
            <button
              key={contract.id}
              onClick={() => onSelectContract(isSelected ? null : contract.id)}
              className={cn(
                "px-3 py-1.5 rounded-full text-sm font-medium transition-colors flex items-center gap-1.5",
                isSelected
                  ? "bg-primary-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              )}
            >
              <StatusIcon className={cn("h-4 w-4", isSelected ? "text-white" : STATUS_COLORS[contract.status])} />
              <span className="max-w-[150px] truncate">{contract.counterparty || contract.filename}</span>
              {contract.risk_level && (
                <span className={cn(
                  "w-2 h-2 rounded-full",
                  contract.risk_level === 'high' || contract.risk_level === 'critical' ? 'bg-red-500' :
                  contract.risk_level === 'medium' ? 'bg-amber-500' : 'bg-green-500'
                )} />
              )}
            </button>
          )
        })}
      </div>

      {/* Selected Contract Details */}
      {selectedContractId && (
        <div className="bg-primary-50 border border-primary-200 rounded-lg p-4">
          {(() => {
            const contract = contracts.find(c => c.id === selectedContractId)
            if (!contract) return null

            return (
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-900">{contract.filename}</p>
                  <div className="flex items-center gap-3 mt-1 text-xs text-gray-600">
                    {contract.counterparty && <span>{contract.counterparty}</span>}
                    {contract.contract_type && <span className="uppercase">{contract.contract_type}</span>}
                    <span>{contract.clause_count} clauses</span>
                    <span>{contract.obligation_count} obligations</span>
                  </div>
                </div>
                <Link
                  to={`/contracts/${contract.id}`}
                  className="btn-secondary text-sm"
                >
                  View Details
                </Link>
              </div>
            )
          })()}
        </div>
      )}
    </div>
  )
}
