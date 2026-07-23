import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import {
  BuildingOffice2Icon,
  UserGroupIcon,
  DocumentTextIcon,
  CurrencyDollarIcon,
  ArrowRightIcon,
  CheckCircleIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import StatCard from '@/components/ui/StatCard'
import { cn, formatCurrency } from '@/lib/utils'
import type { Tenant, PlatformStats, TenantPlan } from '@/types'

const PLAN_COLORS: Record<TenantPlan, string> = {
  starter: 'bg-gray-100 text-gray-700',
  professional: 'bg-blue-100 text-blue-700',
  enterprise: 'bg-purple-100 text-purple-700',
}

export default function SuperAdminDashboardPage() {
  const { t } = useTranslation()
  const { data: stats, isLoading: statsLoading } = useQuery<PlatformStats>({
    queryKey: ['platform-stats'],
    queryFn: () => api.getPlatformStats(),
  })

  const { data: tenants, isLoading: tenantsLoading } = useQuery<Tenant[]>({
    queryKey: ['tenants'],
    queryFn: () => api.getTenants(true),
  })

  const isLoading = statsLoading || tenantsLoading

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const recentTenants = tenants?.slice(0, 5) || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('nav.platformOverview')}</h1>
        <p className="mt-1 text-sm text-gray-500">
          {t('superadmin.dashboard.subtitle')}
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title={t('superadmin.dashboard.totalTenants')}
          value={stats?.total_tenants || 0}
          icon={BuildingOffice2Icon}
          color="primary"
          variant="filled"
        />
        <StatCard
          title={t('superadmin.dashboard.activeTenants')}
          value={stats?.active_tenants || 0}
          icon={CheckCircleIcon}
          color="success"
          variant="filled"
        />
        <StatCard
          title={t('superadmin.dashboard.totalUsers')}
          value={stats?.total_users || 0}
          icon={UserGroupIcon}
          color="blue"
          variant="filled"
        />
        <StatCard
          title={t('superadmin.dashboard.totalContracts')}
          value={stats?.total_contracts || 0}
          icon={DocumentTextIcon}
          color="warning"
          variant="filled"
        />
      </div>

      {/* Secondary Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Plan Distribution */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold text-gray-900 mb-4">{t('superadmin.dashboard.planDistribution')}</h3>
          <div className="space-y-3">
            {(['starter', 'professional', 'enterprise'] as TenantPlan[]).map((plan) => {
              const count = stats?.plan_distribution?.[plan] || 0
              const total = stats?.total_tenants || 1
              const percentage = Math.round((count / total) * 100)
              return (
                <div key={plan}>
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="capitalize font-medium text-gray-700">{t(`superadmin.plans.${plan}`, { defaultValue: plan })}</span>
                    <span className="text-gray-500">{t('superadmin.dashboard.tenantsCount', { count })}</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div
                      className={cn(
                        'h-2 rounded-full',
                        plan === 'starter' ? 'bg-gray-400' :
                        plan === 'professional' ? 'bg-blue-500' : 'bg-purple-500'
                      )}
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Total Value */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold text-gray-900 mb-4">{t('superadmin.dashboard.platformValue')}</h3>
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg bg-emerald-100">
              <CurrencyDollarIcon className="w-6 h-6 text-emerald-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {formatCurrency(stats?.total_value || 0)}
              </p>
              <p className="text-sm text-gray-500">{t('superadmin.dashboard.totalValueDesc')}</p>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold text-gray-900 mb-4">{t('superadmin.quickActions')}</h3>
          <div className="space-y-2">
            <Link
              to="/super-admin/tenants"
              className="flex items-center justify-between p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors group"
            >
              <span className="text-sm font-medium text-gray-700">{t('superadmin.dashboard.manageTenants')}</span>
              <ArrowRightIcon className="w-4 h-4 text-gray-400 group-hover:text-primary-500" />
            </Link>
            <Link
              to="/super-admin/users"
              className="flex items-center justify-between p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors group"
            >
              <span className="text-sm font-medium text-gray-700">{t('superadmin.dashboard.viewAllUsers')}</span>
              <ArrowRightIcon className="w-4 h-4 text-gray-400 group-hover:text-primary-500" />
            </Link>
            <Link
              to="/super-admin/custom-fields"
              className="flex items-center justify-between p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors group"
            >
              <span className="text-sm font-medium text-gray-700">{t('superadmin.configureCustomFields')}</span>
              <ArrowRightIcon className="w-4 h-4 text-gray-400 group-hover:text-primary-500" />
            </Link>
          </div>
        </div>
      </div>

      {/* Recent Tenants */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">{t('superadmin.dashboard.recentTenants')}</h2>
          <Link to="/super-admin/tenants" className="text-sm text-primary-600 hover:text-primary-700 font-medium">
            {t('superadmin.dashboard.viewAll')}
          </Link>
        </div>
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t('superadmin.tenant')}
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t('superadmin.plan')}
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t('common.status')}
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t('common.actions')}
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {recentTenants.map((tenant) => (
              <tr key={tenant.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <div>
                    <p className="text-sm font-medium text-gray-900">{tenant.name}</p>
                    <p className="text-xs text-gray-500">{tenant.slug}</p>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className={cn(
                    'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize',
                    PLAN_COLORS[tenant.plan]
                  )}>
                    {t(`superadmin.plans.${tenant.plan}`, { defaultValue: tenant.plan })}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {tenant.is_active ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">
                      <CheckCircleIcon className="h-3 w-3" />
                      {t('status.active')}
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">
                      <XCircleIcon className="h-3 w-3" />
                      {t('status.inactive')}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  <Link
                    to={`/super-admin/tenants/${tenant.id}`}
                    className="text-sm text-primary-600 hover:text-primary-700 font-medium"
                  >
                    {t('superadmin.dashboard.view')}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
