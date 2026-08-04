/* Compliance reports — Direction B restyle. Header + primary export action,
   token cards, Chip period toggle, token-colored trend bars, .tbl by-contract
   table. Queries, CSV export and date-range behavior unchanged. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import {
  DocumentArrowDownIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  CalendarIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { Button, Chip } from '@/components/ui'

const barColor = (rate: number) =>
  rate >= 80 ? 'var(--ok)' : rate >= 60 ? 'var(--wa)' : 'var(--da)'

const changeColor = (pct: number) =>
  pct > 0 ? 'var(--ok)' : pct < 0 ? 'var(--da)' : 'var(--m)'

function TrendChart({ data }: { data: { period_label: string; overall_compliance_rate: number }[] }) {
  const max = Math.max(...data.map(d => d.overall_compliance_rate), 100)
  const min = Math.min(...data.map(d => d.overall_compliance_rate), 0)
  const range = max - min || 1

  return (
    <div className="flex gap-2">
      {data.map((point, idx) => {
        const height = ((point.overall_compliance_rate - min) / range) * 100

        return (
          <div key={idx} className="flex-1 flex flex-col items-center gap-1">
            <div className="num" style={{ fontSize: 'var(--fs-xs)', fontWeight: 600, color: 'var(--m)' }}>
              {point.overall_compliance_rate.toFixed(1)}%
            </div>
            <div className="w-full h-40 flex items-end">
              <div
                className="w-full"
                style={{
                  height: `${Math.max(height, 4)}%`,
                  background: barColor(point.overall_compliance_rate),
                  borderRadius: '3px 3px 0 0',
                  transition: 'height .2s var(--ease)',
                }}
              />
            </div>
            <div className="faint trunc w-full text-center" style={{ fontSize: 'var(--fs-xs)' }}>
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
    if (trend === 'improving') return <ArrowTrendingUpIcon style={{ width: 16, height: 16, color: 'var(--ok)' }} aria-hidden />
    if (trend === 'declining') return <ArrowTrendingDownIcon style={{ width: 16, height: 16, color: 'var(--da)' }} aria-hidden />
    return <span className="faint">-</span>
  }

  const trendSummary = trend
    ? [
        { label: t('reports.obligations'), dir: trend.obligation_trend, pct: trend.obligation_change_pct },
        { label: t('reports.slas'), dir: trend.sla_trend, pct: trend.sla_change_pct },
        { label: t('reports.overall'), dir: trend.overall_trend, pct: trend.overall_change_pct },
      ]
    : []

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div className="row" style={{ alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>
            {t('reports.title')}
          </h1>
          <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>
            {t('reports.description')}
          </p>
        </div>
        <Button
          variant="primary"
          icon={DocumentArrowDownIcon}
          onClick={handleExport}
          disabled={isExporting || !report}
        >
          {isExporting ? t('reports.exporting') : t('reports.exportCsv')}
        </Button>
      </div>

      {/* Date Range Selector */}
      <div className="card card-p">
        <div className="row" style={{ gap: 12, flexWrap: 'wrap' }}>
          <span className="row" style={{ gap: 6 }}>
            <CalendarIcon style={{ width: 16, height: 16, color: 'var(--f)', flexShrink: 0 }} aria-hidden />
            <span style={{ fontSize: 'var(--fs-md)', fontWeight: 600, color: 'var(--m)' }}>
              {t('reports.reportPeriod')}
            </span>
          </span>
          <div className="inp" style={{ width: 160 }}>
            <input
              type="date"
              value={dateRange.start}
              onChange={(e) => setDateRange(prev => ({ ...prev, start: e.target.value }))}
            />
          </div>
          <span className="muted" style={{ fontSize: 'var(--fs-md)' }}>{t('reports.to')}</span>
          <div className="inp" style={{ width: 160 }}>
            <input
              type="date"
              value={dateRange.end}
              onChange={(e) => setDateRange(prev => ({ ...prev, end: e.target.value }))}
            />
          </div>
        </div>
      </div>

      {/* Trend Analysis */}
      <div className="card">
        <div className="row" style={{ padding: '12px 16px', borderBottom: '1px solid var(--b)', gap: 8 }}>
          <h3 className="sec-t grow">{t('reports.complianceTrend')}</h3>
          <Chip on={trendPeriod === 'weekly'} onClick={() => setTrendPeriod('weekly')}>
            {t('reports.weekly')}
          </Chip>
          <Chip on={trendPeriod === 'monthly'} onClick={() => setTrendPeriod('monthly')}>
            {t('reports.monthly')}
          </Chip>
        </div>
        <div className="card-p">
          {trendLoading ? (
            <div className="row" style={{ justifyContent: 'center', height: 192 }}>
              <LoadingSpinner />
            </div>
          ) : trend ? (
            <>
              <TrendChart data={trend.data_points} />

              {/* Trend Summary */}
              <div
                className="grid grid-cols-3 gap-4"
                style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--b)' }}
              >
                {trendSummary.map((s) => (
                  <div key={s.label} className="text-center">
                    <div className="row" style={{ justifyContent: 'center', gap: 6 }}>
                      {getTrendIcon(s.dir)}
                      <span className="muted" style={{ fontSize: 'var(--fs-sm)' }}>{s.label}</span>
                    </div>
                    <p className="num" style={{ fontSize: 'var(--fs-lg)', fontWeight: 600, color: changeColor(s.pct) }}>
                      {s.pct > 0 ? '+' : ''}{s.pct.toFixed(1)}%
                    </p>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="muted text-center" style={{ padding: '32px 0' }}>{t('reports.noTrendData')}</p>
          )}
        </div>
      </div>

      {/* Report Summary */}
      {reportLoading ? (
        <div className="card row" style={{ justifyContent: 'center', padding: 32 }}>
          <LoadingSpinner size="lg" />
        </div>
      ) : report ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Summary Stats */}
          <div className="card overflow-hidden">
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--b)' }}>
              <h3 className="sec-t">{t('reports.reportSummary')}</h3>
            </div>
            <div className="card-p col" style={{ gap: 16 }}>
              <div className="grid grid-cols-2 gap-4">
                <div style={{ background: 'var(--in-f)', border: '1px solid var(--in-b)', borderRadius: 'var(--r-md)', padding: 12 }}>
                  <p style={{ fontSize: 'var(--fs-xs)', fontWeight: 600, color: 'var(--in)' }}>
                    {t('reports.overallCompliance')}
                  </p>
                  <p className="num" style={{ fontSize: 'var(--fs-2xl)', fontWeight: 700, color: 'var(--in)' }}>
                    {report.summary.overall_compliance_rate.toFixed(1)}%
                  </p>
                </div>
                <div style={{ background: 'var(--s2)', borderRadius: 'var(--r-md)', padding: 12 }}>
                  <p className="muted" style={{ fontSize: 'var(--fs-xs)', fontWeight: 600 }}>
                    {t('reports.contractsReviewed')}
                  </p>
                  <p className="num" style={{ fontSize: 'var(--fs-2xl)', fontWeight: 700 }}>
                    {report.summary.contracts_reviewed}
                  </p>
                </div>
              </div>

              <div className="col" style={{ gap: 8 }}>
                <h4 style={{ fontSize: 'var(--fs-sm)', fontWeight: 600, color: 'var(--m)' }}>
                  {t('reports.obligations')}
                </h4>
                <div className="grid grid-cols-3 gap-2" style={{ fontSize: 'var(--fs-sm)' }}>
                  <div className="text-center" style={{ background: 'var(--s2)', borderRadius: 'var(--r-sm)', padding: 8 }}>
                    <p className="muted">{t('reports.total')}</p>
                    <p className="num" style={{ fontWeight: 600 }}>{report.summary.total_obligations}</p>
                  </div>
                  <div className="text-center" style={{ background: 'var(--ok-f)', borderRadius: 'var(--r-sm)', padding: 8 }}>
                    <p style={{ color: 'var(--ok)' }}>{t('status.completed')}</p>
                    <p className="num" style={{ fontWeight: 600, color: 'var(--ok)' }}>{report.summary.obligations_completed}</p>
                  </div>
                  <div className="text-center" style={{ background: 'var(--da-f)', borderRadius: 'var(--r-sm)', padding: 8 }}>
                    <p style={{ color: 'var(--da)' }}>{t('reports.overdue')}</p>
                    <p className="num" style={{ fontWeight: 600, color: 'var(--da)' }}>{report.summary.obligations_overdue}</p>
                  </div>
                </div>
                <div className="row" style={{ justifyContent: 'space-between', fontSize: 'var(--fs-sm)' }}>
                  <span className="muted">{t('reports.complianceRate')}</span>
                  <span className="num" style={{ fontWeight: 500 }}>{report.summary.obligation_compliance_rate.toFixed(1)}%</span>
                </div>
              </div>

              <div className="col" style={{ gap: 8 }}>
                <h4 style={{ fontSize: 'var(--fs-sm)', fontWeight: 600, color: 'var(--m)' }}>
                  {t('reports.slas')}
                </h4>
                <div className="grid grid-cols-3 gap-2" style={{ fontSize: 'var(--fs-sm)' }}>
                  <div className="text-center" style={{ background: 'var(--s2)', borderRadius: 'var(--r-sm)', padding: 8 }}>
                    <p className="muted">{t('reports.total')}</p>
                    <p className="num" style={{ fontWeight: 600 }}>{report.summary.total_slas}</p>
                  </div>
                  <div className="text-center" style={{ background: 'var(--ok-f)', borderRadius: 'var(--r-sm)', padding: 8 }}>
                    <p style={{ color: 'var(--ok)' }}>{t('reports.compliant')}</p>
                    <p className="num" style={{ fontWeight: 600, color: 'var(--ok)' }}>{report.summary.slas_compliant}</p>
                  </div>
                  <div className="text-center" style={{ background: 'var(--da-f)', borderRadius: 'var(--r-sm)', padding: 8 }}>
                    <p style={{ color: 'var(--da)' }}>{t('status.breached')}</p>
                    <p className="num" style={{ fontWeight: 600, color: 'var(--da)' }}>{report.summary.slas_breached}</p>
                  </div>
                </div>
                <div className="row" style={{ justifyContent: 'space-between', fontSize: 'var(--fs-sm)' }}>
                  <span className="muted">{t('reports.complianceRate')}</span>
                  <span className="num" style={{ fontWeight: 500 }}>{report.summary.sla_compliance_rate.toFixed(1)}%</span>
                </div>
                <div className="row" style={{ justifyContent: 'space-between', fontSize: 'var(--fs-sm)' }}>
                  <span className="muted">{t('reports.totalPenalties')}</span>
                  <span className="num" style={{ fontWeight: 500, color: 'var(--da)' }}>
                    ${report.summary.total_penalties.toLocaleString()}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* By Contract */}
          <div className="card overflow-hidden">
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--b)' }}>
              <h3 className="sec-t">{t('reports.byContract')}</h3>
            </div>
            <div className="overflow-auto" style={{ maxHeight: 320 }}>
              <table className="tbl" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>{t('reports.contract')}</th>
                    <th>{t('reports.oblAbbr')}</th>
                    <th>{t('reports.slaAbbr')}</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(report.by_contract).map(([id, data]) => (
                    <tr key={id}>
                      <td className="trunc" style={{ maxWidth: 200 }}>{data.filename}</td>
                      <td className="nw">
                        <span
                          className="num"
                          style={{ color: data.obligation_rate >= 80 ? 'var(--ok)' : data.obligation_rate >= 60 ? 'var(--wa)' : 'var(--da)' }}
                        >
                          {data.obligation_rate.toFixed(0)}%
                        </span>
                      </td>
                      <td className="nw">
                        <span
                          className="num"
                          style={{ color: data.sla_rate >= 90 ? 'var(--ok)' : data.sla_rate >= 70 ? 'var(--wa)' : 'var(--da)' }}
                        >
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
