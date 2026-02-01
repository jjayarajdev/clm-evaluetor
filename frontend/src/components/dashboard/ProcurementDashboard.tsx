import { Link } from 'react-router-dom'
import { CurrencyDollarIcon, ClockIcon, ArrowPathIcon } from '@heroicons/react/24/outline'
import type { ProcurementDashboard as ProcurementDashboardType } from '@/types'
import { cn, formatCurrency } from '@/lib/utils'

interface Props {
  data: ProcurementDashboardType
}

export default function ProcurementDashboard({ data }: Props) {
  const getUrgencyColor = (urgency: string) => {
    switch (urgency) {
      case 'IMMEDIATE':
        return 'bg-red-100 text-red-700'
      case 'SOON':
        return 'bg-amber-100 text-amber-700'
      case 'UPCOMING':
        return 'bg-blue-100 text-blue-700'
      default:
        return 'bg-gray-100 text-gray-700'
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-gray-900">Procurement Overview</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Spend commitments */}
        <div className="card">
          <div className="card-header flex items-center gap-2">
            <CurrencyDollarIcon className="h-5 w-5 text-green-500" />
            <h3 className="text-sm font-medium text-gray-900">Spend by Vendor</h3>
          </div>
          <div className="divide-y divide-gray-200 max-h-80 overflow-y-auto">
            {data.spend_commitments.length === 0 ? (
              <div className="px-4 py-8 text-center text-gray-500 text-sm">
                No spend data available
              </div>
            ) : (
              data.spend_commitments.map((item, idx) => (
                <div key={idx} className="px-4 py-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-900">{item.counterparty}</p>
                      <p className="text-xs text-gray-500">{item.contract_count} contracts</p>
                    </div>
                    <p className="text-sm font-bold text-gray-900">
                      {formatCurrency(item.total_value, item.currency || 'USD')}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Upcoming obligations */}
        <div className="card">
          <div className="card-header flex items-center gap-2">
            <ClockIcon className="h-5 w-5 text-blue-500" />
            <h3 className="text-sm font-medium text-gray-900">Upcoming Obligations</h3>
          </div>
          <div className="divide-y divide-gray-200 max-h-80 overflow-y-auto">
            {data.upcoming_obligations.length === 0 ? (
              <div className="px-4 py-8 text-center text-gray-500 text-sm">
                No upcoming obligations
              </div>
            ) : (
              data.upcoming_obligations.map((item) => (
                <Link
                  key={item.obligation_id}
                  to={`/contracts/${item.contract_id}`}
                  className="block px-4 py-3 hover:bg-gray-50"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {item.description}
                      </p>
                      <p className="text-xs text-gray-500">
                        {item.counterparty || item.contract_filename}
                      </p>
                    </div>
                    {item.days_remaining !== null && (
                      <span className={cn(
                        'shrink-0 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                        item.days_remaining <= 7 ? 'bg-red-100 text-red-700' :
                        item.days_remaining <= 14 ? 'bg-amber-100 text-amber-700' :
                        'bg-blue-100 text-blue-700'
                      )}>
                        {item.days_remaining}d
                      </span>
                    )}
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Auto-renewal risks */}
      {data.auto_renewal_risks.length > 0 && (
        <div className="card">
          <div className="card-header flex items-center gap-2">
            <ArrowPathIcon className="h-5 w-5 text-amber-500" />
            <h3 className="text-sm font-medium text-gray-900">Auto-Renewal Alerts</h3>
          </div>
          <div className="divide-y divide-gray-200">
            {data.auto_renewal_risks.slice(0, 10).map((item) => (
              <Link
                key={item.contract_id}
                to={`/contracts/${item.contract_id}`}
                className="block px-4 py-3 hover:bg-gray-50"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-900">{item.filename}</p>
                    <p className="text-xs text-gray-500">{item.counterparty || 'Unknown'}</p>
                    {item.notice_period_days && (
                      <p className="text-xs text-gray-400">
                        {item.notice_period_days} day notice required
                      </p>
                    )}
                  </div>
                  <div className="text-right">
                    <span className={cn(
                      'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                      getUrgencyColor(item.urgency)
                    )}>
                      {item.urgency}
                    </span>
                    {item.days_until_notice !== null && (
                      <p className="text-xs text-gray-500 mt-1">
                        {item.days_until_notice > 0
                          ? `${item.days_until_notice}d to notice`
                          : 'Notice overdue!'
                        }
                      </p>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
