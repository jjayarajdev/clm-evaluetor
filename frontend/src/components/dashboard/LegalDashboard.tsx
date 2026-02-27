import { Link } from 'react-router-dom'
import { ExclamationTriangleIcon, CalendarIcon, ShieldExclamationIcon } from '@heroicons/react/24/outline'
import type { LegalDashboard as LegalDashboardType } from '@/types'
import { cn, getRiskColor } from '@/lib/utils'

interface Props {
  data: LegalDashboardType
}

export default function LegalDashboard({ data }: Props) {
  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-gray-900">Risk & Compliance</h2>

      {/* Risk overview cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        {(['low', 'medium', 'high', 'critical'] as const).map((level) => (
          <div key={level} className="card">
            <div className="card-body text-center">
              <p className={cn('text-3xl font-bold', getRiskColor(level).split(' ')[0])}>
                {data.risk_overview.by_level[level] || 0}
              </p>
              <p className="text-sm text-gray-500 capitalize">{level} Risk</p>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Expiration timeline */}
        <div className="card">
          <div className="card-header flex items-center gap-2">
            <CalendarIcon className="h-5 w-5 text-amber-500" />
            <h3 className="text-sm font-medium text-gray-900">Expiring Soon</h3>
          </div>
          <div className="divide-y divide-gray-200 max-h-80 overflow-y-auto">
            {data.expiration_timeline.next_30_days.length === 0 ? (
              <div className="px-4 py-8 text-center text-gray-500 text-sm">
                No contracts expiring in the next 30 days
              </div>
            ) : (
              data.expiration_timeline.next_30_days.map((item) => (
                <Link
                  key={item.contract_id}
                  to={`/contracts/${item.contract_id}`}
                  className="block px-4 py-3 hover:bg-gray-50"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-900">{item.filename}</p>
                      <p className="text-xs text-gray-500">{item.counterparty || 'Unknown'}</p>
                    </div>
                    <div className="text-right">
                      <span className={cn(
                        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                        item.days_remaining <= 7 ? 'bg-red-100 text-red-700' :
                        item.days_remaining <= 14 ? 'bg-amber-100 text-amber-700' :
                        'bg-blue-100 text-blue-700'
                      )}>
                        {item.days_remaining} days
                      </span>
                    </div>
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>

        {/* Contracts requiring attention (high risk level or high-risk clauses) */}
        <div className="card">
          <div className="card-header flex items-center gap-2">
            <ExclamationTriangleIcon className="h-5 w-5 text-red-500" />
            <h3 className="text-sm font-medium text-gray-900">Contracts Requiring Attention</h3>
          </div>
          <div className="divide-y divide-gray-200 max-h-80 overflow-y-auto">
            {data.risk_overview.high_risk_contracts.length === 0 ? (
              <div className="px-4 py-8 text-center text-gray-500 text-sm">
                No contracts require attention
              </div>
            ) : (
              data.risk_overview.high_risk_contracts.map((contract) => (
                <Link
                  key={contract.id}
                  to={`/contracts/${contract.id}`}
                  className="block px-4 py-3 hover:bg-gray-50"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-900">{contract.filename}</p>
                      <p className="text-xs text-gray-500">{contract.counterparty || 'Unknown'}</p>
                    </div>
                    <div className="text-right">
                      <span className={cn(
                        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                        getRiskColor(contract.risk_level)
                      )}>
                        Score: {contract.risk_score}
                      </span>
                    </div>
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>
      </div>

      {/* High risk clauses */}
      {data.high_risk_clauses.length > 0 && (
        <div className="card">
          <div className="card-header flex items-center gap-2">
            <ShieldExclamationIcon className="h-5 w-5 text-red-500" />
            <h3 className="text-sm font-medium text-gray-900">Flagged Clauses</h3>
          </div>
          <div className="divide-y divide-gray-200 max-h-96 overflow-y-auto">
            {data.high_risk_clauses.slice(0, 10).map((clause) => (
              <Link
                key={clause.clause_id}
                to={`/clauses/${clause.clause_id}`}
                className="block px-4 py-3 hover:bg-gray-50 group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900 group-hover:text-primary-600">
                      {clause.contract_filename}
                    </p>
                    <p className="text-xs text-gray-500 capitalize">{clause.clause_type.replace(/_/g, ' ')}</p>
                    <p className="text-xs text-gray-600 mt-1 line-clamp-2">{clause.excerpt}</p>
                  </div>
                  <span className={cn(
                    'shrink-0 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                    getRiskColor(clause.risk_level)
                  )}>
                    {clause.risk_level}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
