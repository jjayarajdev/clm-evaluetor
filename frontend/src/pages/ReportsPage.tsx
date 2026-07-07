import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import {
  DocumentArrowDownIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  CalendarIcon,
  ChartBarSquareIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import PageHeader from '@/components/ui/PageHeader'
import { cn } from '@/lib/utils'

function TrendChart({ data }: { data: { period_label: string; overall_compliance_rate: number }[] }) {
  const max = Math.max(...data.map(d => d.overall_compliance_rate), 100)
  const min = Math.min(...data.map(d => d.overall_compliance_rate), 0)
  const range = max - min || 1

  return (
    <div className="flex gap-2">
      {data.map((point, idx) => {
        const height = ((point.overall_compliance_rate - min) / range) * 100
        const color = point.overall_compliance_rate >= 80 ? 'bg-green-500' :
                      point.overall_compliance_rate >= 60 ? 'bg-amber-500' : 'bg-red-500'

        return (
          <div key={idx} className="flex-1 flex flex-col items-center gap-1">
            <div className="text-xs text-gray-600 font-medium">
              {point.overall_compliance_rate.toFixed(1)}%
            </div>
            <div className="w-full h-40 flex items-end">
              <div
                className={cn('w-full rounded-t transition-all', color)}
                style={{ height: `${Math.max(height, 4)}%` }}
              />
            </div>
            <div className="text-xs text-gray-500 truncate w-full text-center">
              {point.period_label}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function ReportsPage() {
  const { t } = useTranslation()
  const [trendPeriod, setTrendPeriod] = useState<'weekly' | 'monthly'>('weekly')
  const [dateRange, setDateRange] = useState({
    start: new Date(new Date().setMonth(new Date().getMonth() - 1)).toISOString().split('T')[0],
    end: new Date().toISOString().split('T')[0],
  })
  const [isExporting, setIsExporting] = useState(false)

  const { data: trend, isLoading: trendLoading } = useQuery({
    queryKey: ['compliance-trend', trendPeriod],
    queryFn: () => api.getComplianceTrend(trendPeriod, 6),
  })

  const { data: report, isLoading: reportLoading } = useQuery({
    queryKey: ['compliance-report', dateRange.start, dateRange.end],
    queryFn: () => api.getComplianceReport(dateRange.start, dateRange.end),
  })

  const handleExport = async () => {
    setIsExporting(true)
    try {
      const blob = await api.exportComplianceReport(dateRange.start, dateRange.end, 'csv')
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `compliance_report_${dateRange.start}_${dateRange.end}.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      console.error('Export failed:', err)
    } finally {
      setIsExporting(false)
    }
  }

  const getTrendIcon = (trend: string) => {
    if (trend === 'improving') return <ArrowTrendingUpIcon className="h-4 w-4 text-green-500" />
    if (trend === 'declining') return <ArrowTrendingDownIcon className="h-4 w-4 text-red-500" />
    return <span className="text-gray-400">-</span>
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title={t('reports.title')}
        description={t('reports.description')}
        icon={ChartBarSquareIcon}
        variant="bordered"
        actions={
          <button
            onClick={handleExport}
            disabled={isExporting || !report}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <DocumentArrowDownIcon className="h-4 w-4" />
            {isExporting ? t('reports.exporting') : t('reports.exportCsv')}
          </button>
        }
      />

      {/* Date Range Selector */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <CalendarIcon className="h-5 w-5 text-gray-400" />
            <label className="text-sm font-medium text-gray-700">{t('reports.reportPeriod')}</label>
          </div>
          <input
            type="date"
            value={dateRange.start}
            onChange={(e) => setDateRange(prev => ({ ...prev, start: e.target.value }))}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
          />
          <span className="text-gray-500">{t('reports.to')}</span>
          <input
            type="date"
            value={dateRange.end}
            onChange={(e) => setDateRange(prev => ({ ...prev, end: e.target.value }))}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
          />
        </div>
      </div>

      {/* Trend Analysis */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">{t('reports.complianceTrend')}</h3>
          <div className="flex gap-2">
            <button
              onClick={() => setTrendPeriod('weekly')}
              className={cn(
                'px-3 py-1 text-sm rounded',
                trendPeriod === 'weekly' ? 'bg-primary-100 text-primary-700' : 'text-gray-500 hover:bg-gray-100'
              )}
            >
              {t('reports.weekly')}
            </button>
            <button
              onClick={() => setTrendPeriod('monthly')}
              className={cn(
                'px-3 py-1 text-sm rounded',
                trendPeriod === 'monthly' ? 'bg-primary-100 text-primary-700' : 'text-gray-500 hover:bg-gray-100'
              )}
            >
              {t('reports.monthly')}
            </button>
          </div>
        </div>
        <div className="p-4">
          {trendLoading ? (
            <div className="flex items-center justify-center h-48">
              <LoadingSpinner />
            </div>
          ) : trend ? (
            <>
              <TrendChart data={trend.data_points} />

              {/* Trend Summary */}
              <div className="mt-4 grid grid-cols-3 gap-4 pt-4 border-t border-gray-200">
                <div className="text-center">
                  <div className="flex items-center justify-center gap-2">
                    {getTrendIcon(trend.obligation_trend)}
                    <span className="text-sm text-gray-600">{t('reports.obligations')}</span>
                  </div>
                  <p className={cn(
                    'text-lg font-semibold',
                    trend.obligation_change_pct > 0 ? 'text-green-600' :
                    trend.obligation_change_pct < 0 ? 'text-red-600' : 'text-gray-600'
                  )}>
                    {trend.obligation_change_pct > 0 ? '+' : ''}{trend.obligation_change_pct.toFixed(1)}%
                  </p>
                </div>
                <div className="text-center">
                  <div className="flex items-center justify-center gap-2">
                    {getTrendIcon(trend.sla_trend)}
                    <span className="text-sm text-gray-600">{t('reports.slas')}</span>
                  </div>
                  <p className={cn(
                    'text-lg font-semibold',
                    trend.sla_change_pct > 0 ? 'text-green-600' :
                    trend.sla_change_pct < 0 ? 'text-red-600' : 'text-gray-600'
                  )}>
                    {trend.sla_change_pct > 0 ? '+' : ''}{trend.sla_change_pct.toFixed(1)}%
                  </p>
                </div>
                <div className="text-center">
                  <div className="flex items-center justify-center gap-2">
                    {getTrendIcon(trend.overall_trend)}
                    <span className="text-sm text-gray-600">{t('reports.overall')}</span>
                  </div>
                  <p className={cn(
                    'text-lg font-semibold',
                    trend.overall_change_pct > 0 ? 'text-green-600' :
                    trend.overall_change_pct < 0 ? 'text-red-600' : 'text-gray-600'
                  )}>
                    {trend.overall_change_pct > 0 ? '+' : ''}{trend.overall_change_pct.toFixed(1)}%
                  </p>
                </div>
              </div>
            </>
          ) : (
            <p className="text-center text-gray-500 py-8">{t('reports.noTrendData')}</p>
          )}
        </div>
      </div>

      {/* Report Summary */}
      {reportLoading ? (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8 flex items-center justify-center">
          <LoadingSpinner size="lg" />
        </div>
      ) : report ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Summary Stats */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-200">
              <h3 className="font-semibold text-gray-900">{t('reports.reportSummary')}</h3>
            </div>
            <div className="p-4 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-blue-50 rounded-lg p-3">
                  <p className="text-xs text-blue-600 font-medium">{t('reports.overallCompliance')}</p>
                  <p className="text-2xl font-bold text-blue-700">
                    {report.summary.overall_compliance_rate.toFixed(1)}%
                  </p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-600 font-medium">{t('reports.contractsReviewed')}</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {report.summary.contracts_reviewed}
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <h4 className="text-sm font-medium text-gray-700">{t('reports.obligations')}</h4>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div className="bg-gray-50 rounded p-2 text-center">
                    <p className="text-gray-500">{t('reports.total')}</p>
                    <p className="font-semibold">{report.summary.total_obligations}</p>
                  </div>
                  <div className="bg-green-50 rounded p-2 text-center">
                    <p className="text-green-600">{t('status.completed')}</p>
                    <p className="font-semibold text-green-700">{report.summary.obligations_completed}</p>
                  </div>
                  <div className="bg-red-50 rounded p-2 text-center">
                    <p className="text-red-600">{t('reports.overdue')}</p>
                    <p className="font-semibold text-red-700">{report.summary.obligations_overdue}</p>
                  </div>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">{t('reports.complianceRate')}</span>
                  <span className="font-medium">{report.summary.obligation_compliance_rate.toFixed(1)}%</span>
                </div>
              </div>

              <div className="space-y-2">
                <h4 className="text-sm font-medium text-gray-700">{t('reports.slas')}</h4>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div className="bg-gray-50 rounded p-2 text-center">
                    <p className="text-gray-500">{t('reports.total')}</p>
                    <p className="font-semibold">{report.summary.total_slas}</p>
                  </div>
                  <div className="bg-green-50 rounded p-2 text-center">
                    <p className="text-green-600">{t('reports.compliant')}</p>
                    <p className="font-semibold text-green-700">{report.summary.slas_compliant}</p>
                  </div>
                  <div className="bg-red-50 rounded p-2 text-center">
                    <p className="text-red-600">{t('status.breached')}</p>
                    <p className="font-semibold text-red-700">{report.summary.slas_breached}</p>
                  </div>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">{t('reports.complianceRate')}</span>
                  <span className="font-medium">{report.summary.sla_compliance_rate.toFixed(1)}%</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">{t('reports.totalPenalties')}</span>
                  <span className="font-medium text-red-600">${report.summary.total_penalties.toLocaleString()}</span>
                </div>
              </div>
            </div>
          </div>

          {/* By Contract */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-200">
              <h3 className="font-semibold text-gray-900">{t('reports.byContract')}</h3>
            </div>
            <div className="overflow-auto max-h-80">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">{t('reports.contract')}</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">{t('reports.oblAbbr')}</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">{t('reports.slaAbbr')}</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {Object.entries(report.by_contract).map(([id, data]) => (
                    <tr key={id}>
                      <td className="px-4 py-2 text-sm text-gray-900 truncate max-w-[200px]">
                        {data.filename}
                      </td>
                      <td className="px-4 py-2 text-sm">
                        <span className={cn(
                          data.obligation_rate >= 80 ? 'text-green-600' :
                          data.obligation_rate >= 60 ? 'text-amber-600' : 'text-red-600'
                        )}>
                          {data.obligation_rate.toFixed(0)}%
                        </span>
                      </td>
                      <td className="px-4 py-2 text-sm">
                        <span className={cn(
                          data.sla_rate >= 90 ? 'text-green-600' :
                          data.sla_rate >= 70 ? 'text-amber-600' : 'text-red-600'
                        )}>
                          {data.sla_rate.toFixed(0)}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
