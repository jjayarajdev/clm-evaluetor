import {
  DocumentTextIcon,
  UsersIcon,
  MagnifyingGlassIcon,
  CloudArrowUpIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline'
import type { AdminDashboard as AdminDashboardType } from '@/types'
import { formatNumber } from '@/lib/utils'

interface Props {
  data: AdminDashboardType
}

export default function AdminDashboard({ data }: Props) {
  const stats = [
    {
      name: 'Total Contracts',
      value: formatNumber(data.contract_stats.total),
      icon: DocumentTextIcon,
      color: 'bg-blue-500',
    },
    {
      name: 'Total Users',
      value: formatNumber(data.user_stats.total),
      icon: UsersIcon,
      color: 'bg-green-500',
    },
    {
      name: 'Queries (7d)',
      value: formatNumber(data.activity.queries_7d),
      icon: MagnifyingGlassIcon,
      color: 'bg-purple-500',
    },
    {
      name: 'Uploads (7d)',
      value: formatNumber(data.activity.uploads_7d),
      icon: CloudArrowUpIcon,
      color: 'bg-amber-500',
    },
  ]

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-gray-900">System Overview</h2>

      {/* Stats grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.name} className="card">
            <div className="card-body flex items-center gap-4">
              <div className={`${stat.color} rounded-lg p-3`}>
                <stat.icon className="h-6 w-6 text-white" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                <p className="text-sm text-gray-500">{stat.name}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Two column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Contracts by status */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-gray-900">Contracts by Status</h3>
          </div>
          <div className="card-body">
            <div className="space-y-3">
              {Object.entries(data.contract_stats.by_status).map(([status, count]) => (
                <div key={status} className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 capitalize">{status}</span>
                  <span className="text-sm font-medium text-gray-900">{count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Ingestion queue */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-gray-900">Ingestion Queue</h3>
          </div>
          <div className="card-body">
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-gray-900">{data.ingestion.pending}</p>
                <p className="text-xs text-gray-500">Pending</p>
              </div>
              <div className="text-center p-3 bg-blue-50 rounded-lg">
                <p className="text-2xl font-bold text-blue-600">{data.ingestion.processing}</p>
                <p className="text-xs text-gray-500">Processing</p>
              </div>
              <div className="text-center p-3 bg-green-50 rounded-lg">
                <p className="text-2xl font-bold text-green-600">{data.ingestion.completed}</p>
                <p className="text-xs text-gray-500">Completed</p>
              </div>
              <div className="text-center p-3 bg-red-50 rounded-lg">
                <p className="text-2xl font-bold text-red-600">{data.ingestion.failed}</p>
                <p className="text-xs text-gray-500">Failed</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Recent failures */}
      {data.recent_failures.length > 0 && (
        <div className="card">
          <div className="card-header flex items-center gap-2">
            <ExclamationTriangleIcon className="h-5 w-5 text-red-500" />
            <h3 className="text-sm font-medium text-gray-900">Recent Failures</h3>
          </div>
          <div className="divide-y divide-gray-200">
            {data.recent_failures.map((failure) => (
              <div key={failure.id} className="px-4 py-3">
                <p className="text-sm font-medium text-gray-900">{failure.filename}</p>
                <p className="text-xs text-red-600 mt-1">{failure.error}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
