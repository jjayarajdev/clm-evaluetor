import { useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ShieldCheckIcon,
  ChartBarIcon,
  ClipboardDocumentListIcon,
  ExclamationTriangleIcon,
  DocumentTextIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import PageHeader from '@/components/ui/PageHeader'
import StatCard from '@/components/ui/StatCard'
import { cn } from '@/lib/utils'
import type {
  RegulatoryObligationSummary,
  IndustryComplianceSummary,
  ContractComplianceSummary,
} from '@/types/compliance'

type TabId = 'overview' | 'obligations' | 'byContract'

const RAG_OPTIONS = ['green', 'amber', 'red', 'not_assessed'] as const

function ragClasses(status: string): string {
  switch (status) {
    case 'green':
      return 'bg-emerald-100 text-emerald-700'
    case 'amber':
      return 'bg-amber-100 text-amber-700'
    case 'red':
      return 'bg-red-100 text-red-700'
    default:
      return 'bg-gray-100 text-gray-600'
  }
}

export default function CompliancePage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = (searchParams.get('tab') as TabId) || 'overview'
  const setActiveTab = (tab: TabId) => setSearchParams({ tab })

  const [regulationFilter, setRegulationFilter] = useState<string>('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [needsAttentionOnly, setNeedsAttentionOnly] = useState(false)

  const { data: dashboard, isLoading } = useQuery({
    queryKey: ['compliance-dashboard'],
    queryFn: () => api.getComplianceDashboard(),
  })

  const { data: byIndustry } = useQuery({
    queryKey: ['compliance-by-industry'],
    queryFn: () => api.getComplianceByIndustry(),
    enabled: activeTab === 'overview',
  })

  const { data: obligations, isLoading: oblLoading } = useQuery({
    queryKey: ['compliance-obligations', regulationFilter, statusFilter, needsAttentionOnly],
    queryFn: () => api.getRegulatoryObligations({
      regulation_type: regulationFilter || undefined,
      status: statusFilter || undefined,
      needs_attention: needsAttentionOnly || undefined,
    }),
    enabled: activeTab === 'obligations',
  })

  const { data: contracts, isLoading: contractsLoading } = useQuery({
    queryKey: ['compliance-contracts'],
    queryFn: () => api.getContractComplianceList(),
    enabled: activeTab === 'byContract',
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.updateRegulatoryObligationStatus(id, { compliance_status: status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['compliance-obligations'] })
      queryClient.invalidateQueries({ queryKey: ['compliance-dashboard'] })
    },
  })

  const regulationOptions = useMemo(() => {
    const set = new Set<string>()
    ;((obligations || []) as RegulatoryObligationSummary[]).forEach((o) => set.add(o.regulation_type))
    return Array.from(set).sort()
  }, [obligations])

  if (isLoading || !dashboard) return <LoadingSpinner size="lg" />

  const tabs: { id: TabId; label: string }[] = [
    { id: 'overview', label: t('compliancePage.tabs.overview') },
    { id: 'obligations', label: t('compliancePage.tabs.obligations', { count: dashboard.regulatory_obligations_count }) },
    { id: 'byContract', label: t('compliancePage.tabs.byContract') },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('compliancePage.title')}
        description={t('compliancePage.description')}
        icon={ShieldCheckIcon}
        variant="bordered"
      />

      {/* Summary stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title={t('compliancePage.stats.totalContracts')}
          value={dashboard.total_contracts}
          icon={DocumentTextIcon}
          color="primary"
          variant="filled"
        />
        <StatCard
          title={t('compliancePage.stats.avgScore')}
          value={`${Math.round(dashboard.average_compliance_score)}%`}
          icon={ChartBarIcon}
          color={dashboard.average_compliance_score >= 90 ? 'success' : dashboard.average_compliance_score >= 70 ? 'warning' : 'danger'}
          variant="filled"
        />
        <StatCard
          title={t('compliancePage.stats.obligations')}
          value={dashboard.regulatory_obligations_count}
          icon={ClipboardDocumentListIcon}
          color="purple"
          variant="filled"
        />
        <StatCard
          title={t('compliancePage.stats.needsAttention')}
          value={dashboard.obligations_needing_attention}
          icon={ExclamationTriangleIcon}
          color={dashboard.obligations_needing_attention > 0 ? 'danger' : 'success'}
          variant="filled"
        />
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 bg-white rounded-t-xl px-4">
        <nav className="flex space-x-6 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex items-center gap-2 py-3 px-1 border-b-2 text-sm font-medium transition-colors whitespace-nowrap',
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              )}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Overview */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 card">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">{t('compliancePage.byIndustry')}</h3>
            {byIndustry && (byIndustry as IndustryComplianceSummary[]).length > 0 ? (
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b border-gray-200">
                    <th className="py-2 pr-4">{t('compliancePage.cols.industry')}</th>
                    <th className="py-2 pr-4">{t('compliancePage.cols.score')}</th>
                    <th className="py-2 pr-4">{t('compliancePage.cols.openGaps')}</th>
                    <th className="py-2 pr-4">{t('compliancePage.cols.criticalGaps')}</th>
                  </tr>
                </thead>
                <tbody>
                  {(byIndustry as IndustryComplianceSummary[]).map((row) => (
                    <tr key={row.industry} className="border-b border-gray-100">
                      <td className="py-2 pr-4 font-medium text-gray-900 capitalize">{row.industry.replace(/_/g, ' ')}</td>
                      <td className="py-2 pr-4">{Math.round(row.average_compliance_score)}%</td>
                      <td className="py-2 pr-4">{row.open_gaps}</td>
                      <td className="py-2 pr-4">{row.critical_gaps}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-sm text-gray-500">{t('compliancePage.noIndustryData')}</p>
            )}
          </div>

          {/* Deferred gaps/rules engine — empty-state guidance */}
          <div className="card border-dashed">
            <h3 className="text-sm font-semibold text-gray-900 mb-2">{t('compliancePage.gapsEmptyTitle')}</h3>
            <p className="text-sm text-gray-500">{t('compliancePage.gapsEmptyBody')}</p>
          </div>
        </div>
      )}

      {/* Regulatory obligations */}
      {activeTab === 'obligations' && (
        <div className="card">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <select
              value={regulationFilter}
              onChange={(e) => setRegulationFilter(e.target.value)}
              className="input py-1.5 text-sm w-auto"
            >
              <option value="">{t('compliancePage.filters.allRegulations')}</option>
              {regulationOptions.map((r) => (
                <option key={r} value={r}>{r.toUpperCase()}</option>
              ))}
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="input py-1.5 text-sm w-auto"
            >
              <option value="">{t('compliancePage.filters.allStatuses')}</option>
              {RAG_OPTIONS.map((s) => (
                <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
              ))}
            </select>
            <label className="flex items-center gap-2 text-sm text-gray-600">
              <input
                type="checkbox"
                checked={needsAttentionOnly}
                onChange={(e) => setNeedsAttentionOnly(e.target.checked)}
              />
              {t('compliancePage.filters.needsAttentionOnly')}
            </label>
          </div>

          {oblLoading ? (
            <LoadingSpinner size="md" />
          ) : (obligations || []).length === 0 ? (
            <p className="text-sm text-gray-500 py-6 text-center">{t('compliancePage.noObligations')}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b border-gray-200">
                    <th className="py-2 pr-4">{t('compliancePage.cols.obligation')}</th>
                    <th className="py-2 pr-4">{t('compliancePage.cols.regulation')}</th>
                    <th className="py-2 pr-4">{t('compliancePage.cols.category')}</th>
                    <th className="py-2 pr-4">{t('compliancePage.cols.dueDate')}</th>
                    <th className="py-2 pr-4">{t('compliancePage.cols.status')}</th>
                    <th className="py-2 pr-4">{t('compliancePage.cols.contract')}</th>
                  </tr>
                </thead>
                <tbody>
                  {(obligations as RegulatoryObligationSummary[]).map((o) => (
                    <tr key={o.id} className="border-b border-gray-100 align-top">
                      <td className="py-2 pr-4 font-medium text-gray-900 max-w-md">{o.title || o.description || '—'}</td>
                      <td className="py-2 pr-4 uppercase text-gray-600">{o.regulation_type}</td>
                      <td className="py-2 pr-4 capitalize text-gray-600">{o.obligation_category.replace(/_/g, ' ')}</td>
                      <td className="py-2 pr-4">
                        <span className={cn(o.is_overdue && 'text-red-600 font-medium')}>
                          {o.next_due_date || '—'}
                          {o.is_overdue && <span className="ml-1 text-xs">({t('compliancePage.overdue')})</span>}
                        </span>
                      </td>
                      <td className="py-2 pr-4">
                        <select
                          value={o.compliance_status}
                          onChange={(e) => statusMutation.mutate({ id: o.id, status: e.target.value })}
                          disabled={statusMutation.isPending}
                          className={cn('rounded px-2 py-1 text-xs font-medium border-0', ragClasses(o.compliance_status))}
                        >
                          {RAG_OPTIONS.map((s) => (
                            <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
                          ))}
                        </select>
                      </td>
                      <td className="py-2 pr-4">
                        <Link to={`/contracts/${o.contract_id}`} className="text-primary-600 hover:underline inline-flex items-center gap-1">
                          {t('compliancePage.viewContract')}
                          <ArrowTopRightOnSquareIcon className="h-3.5 w-3.5" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* By contract */}
      {activeTab === 'byContract' && (
        <div className="card">
          {contractsLoading ? (
            <LoadingSpinner size="md" />
          ) : (contracts || []).length === 0 ? (
            <p className="text-sm text-gray-500 py-6 text-center">{t('compliancePage.noObligations')}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b border-gray-200">
                    <th className="py-2 pr-4">{t('compliancePage.cols.contract')}</th>
                    <th className="py-2 pr-4">{t('compliancePage.cols.industry')}</th>
                    <th className="py-2 pr-4">{t('compliancePage.cols.score')}</th>
                    <th className="py-2 pr-4">{t('compliancePage.cols.openGaps')}</th>
                    <th className="py-2 pr-4">{t('compliancePage.stats.obligations')}</th>
                  </tr>
                </thead>
                <tbody>
                  {(contracts as ContractComplianceSummary[]).map((c) => (
                    <tr key={c.contract_id} className="border-b border-gray-100">
                      <td className="py-2 pr-4">
                        <Link to={`/contracts/${c.contract_id}`} className="text-primary-600 hover:underline font-medium">
                          {c.filename}
                        </Link>
                        {c.counterparty && <div className="text-xs text-gray-500">{c.counterparty}</div>}
                      </td>
                      <td className="py-2 pr-4 capitalize text-gray-600">{c.detected_industry ? c.detected_industry.replace(/_/g, ' ') : '—'}</td>
                      <td className="py-2 pr-4">{c.compliance_score != null ? `${c.compliance_score}%` : '—'}</td>
                      <td className="py-2 pr-4">{c.open_gaps_count}</td>
                      <td className="py-2 pr-4">{c.regulatory_obligations_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
