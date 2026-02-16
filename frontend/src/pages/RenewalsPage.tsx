import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  CalendarIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  ArrowPathIcon,
  CalendarDaysIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import PageHeader from '@/components/ui/PageHeader'
import StatCard from '@/components/ui/StatCard'
import { cn } from '@/lib/utils'
import type { ContractRenewalInfo } from '@/types/postsigning'

function RenewalCard({ contract }: { contract: ContractRenewalInfo }) {
  const getWindowColor = (window: string) => {
    switch (window) {
      case 'expired': return 'bg-gray-100 border-gray-300'
      case 'critical': return 'bg-red-50 border-red-300'
      case '30_days': return 'bg-red-50 border-red-200'
      case '60_days': return 'bg-amber-50 border-amber-200'
      case '90_days': return 'bg-blue-50 border-blue-200'
      default: return 'bg-gray-50 border-gray-200'
    }
  }

  const getStatusBadge = () => {
    if (contract.is_past_notice_deadline) {
      return (
        <span className="px-2 py-0.5 bg-red-100 text-red-800 rounded-full text-xs font-medium">
          Past Notice Deadline
        </span>
      )
    }
    if (contract.auto_renewal) {
      return (
        <span className="px-2 py-0.5 bg-green-100 text-green-800 rounded-full text-xs font-medium flex items-center gap-1">
          <ArrowPathIcon className="h-3 w-3" />
          Auto-Renew
        </span>
      )
    }
    return null
  }

  return (
    <div className={cn('border rounded-lg p-4', getWindowColor(contract.renewal_window))}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <Link
            to={`/contracts/${contract.contract_id}`}
            className="text-sm font-medium text-primary-600 hover:underline"
          >
            {contract.filename}
          </Link>
          <p className="text-sm text-gray-600 mt-1">{contract.counterparty || 'Unknown Counterparty'}</p>
        </div>
        {getStatusBadge()}
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-gray-500">Expiration</p>
          <p className="font-medium">
            {contract.expiration_date
              ? new Date(contract.expiration_date).toLocaleDateString()
              : 'No date'}
          </p>
        </div>
        <div>
          <p className="text-gray-500">Days Remaining</p>
          <p className={cn(
            'font-medium',
            contract.days_until_expiration && contract.days_until_expiration <= 30 ? 'text-red-600' :
            contract.days_until_expiration && contract.days_until_expiration <= 60 ? 'text-amber-600' :
            'text-gray-900'
          )}>
            {contract.days_until_expiration !== null ? `${contract.days_until_expiration} days` : '-'}
          </p>
        </div>
        <div>
          <p className="text-gray-500">Contract Value</p>
          <p className="font-medium">
            {contract.contract_value ? `$${contract.contract_value.toLocaleString()}` : '-'}
          </p>
        </div>
        <div>
          <p className="text-gray-500">Notice Period</p>
          <p className="font-medium">
            {contract.notice_period_days ? `${contract.notice_period_days} days` : '-'}
          </p>
        </div>
      </div>

      {contract.sla_compliance_rate !== null && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">SLA Compliance</span>
            <span className={cn(
              'font-medium',
              contract.sla_compliance_rate >= 90 ? 'text-green-600' :
              contract.sla_compliance_rate >= 70 ? 'text-amber-600' :
              'text-red-600'
            )}>
              {contract.sla_compliance_rate.toFixed(1)}%
            </span>
          </div>
          {contract.active_sla_breaches > 0 && (
            <p className="text-xs text-red-600 mt-1">
              {contract.active_sla_breaches} active SLA breaches
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export default function RenewalsPage() {
  const [selectedWindow, setSelectedWindow] = useState<string>('all')

  const { data: calendar, isLoading, error } = useQuery({
    queryKey: ['renewal-calendar'],
    queryFn: () => api.getRenewalCalendar(),
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !calendar) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">Failed to load renewal calendar</p>
      </div>
    )
  }

  const windows = [
    { id: 'all', label: 'All', count: calendar.total_contracts },
    { id: 'critical', label: 'Critical', count: calendar.critical.length, color: 'text-red-600' },
    { id: 'within_30_days', label: '30 Days', count: calendar.within_30_days.length, color: 'text-red-500' },
    { id: 'within_60_days', label: '60 Days', count: calendar.within_60_days.length, color: 'text-amber-600' },
    { id: 'within_90_days', label: '90 Days', count: calendar.within_90_days.length, color: 'text-blue-600' },
    { id: 'expired', label: 'Expired', count: calendar.expired.length, color: 'text-gray-500' },
  ]

  const getContracts = () => {
    switch (selectedWindow) {
      case 'critical': return calendar.critical
      case 'within_30_days': return calendar.within_30_days
      case 'within_60_days': return calendar.within_60_days
      case 'within_90_days': return calendar.within_90_days
      case 'expired': return calendar.expired
      default: return [
        ...calendar.critical,
        ...calendar.within_30_days,
        ...calendar.within_60_days,
        ...calendar.within_90_days,
      ]
    }
  }

  const contracts = getContracts()

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title="Renewal Calendar"
        description="Track contract renewals and notice deadlines"
        icon={CalendarDaysIcon}
        variant="bordered"
      />

      {/* Summary Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Need Action"
          value={calendar.requires_action_count}
          icon={ExclamationTriangleIcon}
          color="danger"
        />
        <StatCard
          title="Auto-Renewing"
          value={calendar.auto_renewal_count}
          icon={ArrowPathIcon}
          color="success"
        />
        <StatCard
          title="Total Expiring"
          value={calendar.total_contracts}
          icon={CalendarIcon}
          color="default"
        />
        <StatCard
          title="Value at Risk"
          value={`$${(calendar.total_value_at_risk / 1000000).toFixed(1)}M`}
          icon={ClockIcon}
          color="primary"
        />
      </div>

      {/* Window Filter */}
      <div className="flex gap-2 flex-wrap">
        {windows.map((window) => (
          <button
            key={window.id}
            onClick={() => setSelectedWindow(window.id)}
            className={cn(
              'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              selectedWindow === window.id
                ? 'bg-primary-100 text-primary-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
          >
            {window.label}
            <span className={cn('ml-2', window.color || 'text-gray-500')}>
              ({window.count})
            </span>
          </button>
        ))}
      </div>

      {/* Contracts Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {contracts.map((contract) => (
          <RenewalCard key={contract.contract_id} contract={contract} />
        ))}
        {contracts.length === 0 && (
          <div className="col-span-full text-center py-12 text-gray-500">
            No contracts in this renewal window
          </div>
        )}
      </div>
    </div>
  )
}
