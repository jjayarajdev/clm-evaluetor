import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BuildingOfficeIcon,
  ExclamationTriangleIcon,
  ChartBarIcon,
  ArrowUpIcon,
  ArrowDownIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'
import type { VendorListItem } from '@/types/postsigning'

function ScoreGauge({ score, size = 'md' }: { score: number; size?: 'sm' | 'md' | 'lg' }) {
  const getColor = () => {
    if (score >= 80) return 'text-green-600'
    if (score >= 60) return 'text-amber-600'
    if (score >= 40) return 'text-orange-600'
    return 'text-red-600'
  }

  const getGrade = () => {
    if (score >= 90) return 'A'
    if (score >= 80) return 'B'
    if (score >= 70) return 'C'
    if (score >= 60) return 'D'
    return 'F'
  }

  const sizeClasses = {
    sm: 'w-10 h-10 text-sm',
    md: 'w-14 h-14 text-lg',
    lg: 'w-20 h-20 text-2xl',
  }

  return (
    <div className={cn(
      'rounded-full border-4 flex items-center justify-center font-bold',
      sizeClasses[size],
      getColor(),
      score >= 80 ? 'border-green-200 bg-green-50' :
      score >= 60 ? 'border-amber-200 bg-amber-50' :
      score >= 40 ? 'border-orange-200 bg-orange-50' :
      'border-red-200 bg-red-50'
    )}>
      {getGrade()}
    </div>
  )
}

function VendorRow({ vendor, onClick }: { vendor: VendorListItem; onClick: () => void }) {
  return (
    <tr
      className="hover:bg-gray-50 cursor-pointer"
      onClick={onClick}
    >
      <td className="px-4 py-4">
        <div className="flex items-center gap-3">
          <ScoreGauge score={vendor.performance_score} size="sm" />
          <div>
            <p className="font-medium text-gray-900">{vendor.vendor_name}</p>
            <p className="text-xs text-gray-500">{vendor.contract_count} contracts</p>
          </div>
        </div>
      </td>
      <td className="px-4 py-4 text-sm">
        <span className={cn(
          'font-semibold',
          vendor.performance_score >= 80 ? 'text-green-600' :
          vendor.performance_score >= 60 ? 'text-amber-600' :
          'text-red-600'
        )}>
          {vendor.performance_score.toFixed(1)}
        </span>
      </td>
      <td className="px-4 py-4 text-sm">
        <span className={cn(
          'px-2 py-0.5 rounded-full text-xs font-medium',
          vendor.risk_level === 'low' ? 'bg-green-100 text-green-800' :
          vendor.risk_level === 'medium' ? 'bg-amber-100 text-amber-800' :
          vendor.risk_level === 'high' ? 'bg-orange-100 text-orange-800' :
          'bg-red-100 text-red-800'
        )}>
          {vendor.risk_level}
        </span>
      </td>
      <td className="px-4 py-4 text-sm text-gray-600">
        ${vendor.total_exposure.toLocaleString()}
      </td>
      <td className="px-4 py-4 text-sm">
        <span className={cn(
          vendor.obligation_compliance_rate && vendor.obligation_compliance_rate >= 80 ? 'text-green-600' :
          vendor.obligation_compliance_rate && vendor.obligation_compliance_rate >= 60 ? 'text-amber-600' :
          'text-red-600'
        )}>
          {vendor.obligation_compliance_rate?.toFixed(1) ?? '-'}%
        </span>
      </td>
      <td className="px-4 py-4 text-sm">
        <span className={cn(
          vendor.sla_compliance_rate && vendor.sla_compliance_rate >= 90 ? 'text-green-600' :
          vendor.sla_compliance_rate && vendor.sla_compliance_rate >= 70 ? 'text-amber-600' :
          'text-red-600'
        )}>
          {vendor.sla_compliance_rate?.toFixed(1) ?? '-'}%
        </span>
      </td>
      <td className="px-4 py-4 text-sm">
        {vendor.active_breaches > 0 ? (
          <span className="text-red-600 font-medium">{vendor.active_breaches}</span>
        ) : (
          <span className="text-green-600">0</span>
        )}
      </td>
    </tr>
  )
}

function VendorDetailModal({
  vendorName,
  onClose,
}: {
  vendorName: string
  onClose: () => void
}) {
  const { data: vendor, isLoading } = useQuery({
    queryKey: ['vendor-detail', vendorName],
    queryFn: () => api.getVendorPerformance(vendorName),
    enabled: !!vendorName,
  })

  if (isLoading) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-8">
          <LoadingSpinner size="lg" />
        </div>
      </div>
    )
  }

  if (!vendor) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-auto">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <ScoreGauge score={vendor.performance_score} size="lg" />
              <div>
                <h2 className="text-xl font-bold text-gray-900">{vendor.vendor_name}</h2>
                <p className={cn(
                  'text-sm font-medium',
                  vendor.is_at_risk ? 'text-red-600' : 'text-green-600'
                )}>
                  {vendor.is_at_risk ? 'At Risk' : 'Good Standing'}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Score Breakdown */}
          <div>
            <h3 className="text-sm font-medium text-gray-500 uppercase mb-3">Score Breakdown</h3>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Obligation Compliance (40%)</span>
                <span className="font-medium">{vendor.score_breakdown.obligation_compliance_score.toFixed(1)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">SLA Compliance (30%)</span>
                <span className="font-medium">{vendor.score_breakdown.sla_compliance_score.toFixed(1)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Responsiveness (20%)</span>
                <span className="font-medium">{vendor.score_breakdown.responsiveness_score.toFixed(1)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Issue Rate (10%)</span>
                <span className="font-medium">{vendor.score_breakdown.issue_rate_score.toFixed(1)}</span>
              </div>
              <div className="flex items-center justify-between pt-2 border-t border-gray-200">
                <span className="text-sm font-medium text-gray-900">Weighted Total</span>
                <span className="font-bold text-lg">{vendor.score_breakdown.weighted_total.toFixed(1)}</span>
              </div>
            </div>
          </div>

          {/* Quick Stats */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500">Contracts</p>
              <p className="text-lg font-semibold">{vendor.contracts.total_contracts}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500">Total Value</p>
              <p className="text-lg font-semibold">${(vendor.contracts.total_value / 1000000).toFixed(1)}M</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500">Active</p>
              <p className="text-lg font-semibold">{vendor.contracts.active_contracts}</p>
            </div>
          </div>

          {/* Risk Factors */}
          {vendor.risk_factors.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-500 uppercase mb-3">Risk Factors</h3>
              <ul className="space-y-2">
                {vendor.risk_factors.map((factor, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm">
                    <ExclamationTriangleIcon className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
                    <span>{factor}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Recommended Actions */}
          {vendor.recommended_actions.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-500 uppercase mb-3">Recommended Actions</h3>
              <ul className="space-y-2">
                {vendor.recommended_actions.map((action, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm">
                    <ChartBarIcon className="h-4 w-4 text-blue-500 mt-0.5 shrink-0" />
                    <span>{action}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function VendorsPage() {
  const [sortBy, setSortBy] = useState('score')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [selectedVendor, setSelectedVendor] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['vendors', sortBy, sortOrder],
    queryFn: () => api.getVendors({ sort_by: sortBy, sort_order: sortOrder }),
  })

  const handleSort = (column: string) => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(column)
      setSortOrder('desc')
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">Failed to load vendor data</p>
      </div>
    )
  }

  const SortIcon = ({ column }: { column: string }) => {
    if (sortBy !== column) return null
    return sortOrder === 'asc' ? (
      <ArrowUpIcon className="h-4 w-4 inline ml-1" />
    ) : (
      <ArrowDownIcon className="h-4 w-4 inline ml-1" />
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Vendor Performance</h1>
        <p className="text-sm text-gray-500 mt-1">
          Track and compare vendor performance across your contracts
        </p>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <BuildingOfficeIcon className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{data.total_vendors}</p>
              <p className="text-sm text-gray-500">Total Vendors</p>
            </div>
          </div>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-100 rounded-lg">
              <ExclamationTriangleIcon className="h-5 w-5 text-red-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{data.at_risk_count}</p>
              <p className="text-sm text-gray-500">At Risk</p>
            </div>
          </div>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-100 rounded-lg">
              <ChartBarIcon className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                ${(data.total_exposure / 1000000).toFixed(1)}M
              </p>
              <p className="text-sm text-gray-500">Total Exposure</p>
            </div>
          </div>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-100 rounded-lg">
              <ChartBarIcon className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {data.vendors.length > 0
                  ? (data.vendors.reduce((sum, v) => sum + v.performance_score, 0) / data.vendors.length).toFixed(1)
                  : '-'}
              </p>
              <p className="text-sm text-gray-500">Avg Score</p>
            </div>
          </div>
        </div>
      </div>

      {/* Vendors Table */}
      <div className="card overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th
                className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('name')}
              >
                Vendor <SortIcon column="name" />
              </th>
              <th
                className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('score')}
              >
                Score <SortIcon column="score" />
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Risk
              </th>
              <th
                className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('exposure')}
              >
                Exposure <SortIcon column="exposure" />
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Obl. Compliance
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                SLA Compliance
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Breaches
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {data.vendors.map((vendor) => (
              <VendorRow
                key={vendor.normalized_name}
                vendor={vendor}
                onClick={() => setSelectedVendor(vendor.vendor_name)}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Detail Modal */}
      {selectedVendor && (
        <VendorDetailModal
          vendorName={selectedVendor}
          onClose={() => setSelectedVendor(null)}
        />
      )}
    </div>
  )
}
