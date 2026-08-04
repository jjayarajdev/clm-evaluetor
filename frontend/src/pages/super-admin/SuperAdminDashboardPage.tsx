/* Super-admin platform overview — Direction B redesign.
   Stat summary row → plan distribution (Bars) / platform value / quick actions
   → recent tenants Table. Queries and routes unchanged from the pre-redesign
   page; restyle only. */
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
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { Bar, EmptyState, Pill, Stat, Table } from '@/components/ui'
import type { PillTone, TableColumn } from '@/components/ui'
import { formatCurrency } from '@/lib/utils'
import type { Tenant, PlatformStats, TenantPlan } from '@/types'

const PLAN_TONES: Record<TenantPlan, PillTone> = {
  starter: 'n',
  professional: 'in',
  enterprise: 'p',
}

const PLAN_BAR_TONES: Record<TenantPlan, string> = {
  starter: 'var(--f)',
  professional: 'var(--in)',
  enterprise: 'var(--p)',
}

function QuickAction({ to, label }: { to: string; label: string }) {
  return (
    <Link
      to={to}
      className="row"
      style={{
        justifyContent: 'space-between',
        padding: '10px 12px',
        borderRadius: 'var(--r-md)',
        background: 'var(--s2)',
        color: 'inherit',
        fontSize: 'var(--fs-md)',
        fontWeight: 500,
      }}
    >
      <span className="trunc">{label}</span>
      <ArrowRightIcon style={{ width: 14, height: 14, flexShrink: 0, color: 'var(--f)' }} aria-hidden />
    </Link>
  )
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
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const recentTenants = tenants?.slice(0, 5) || []

  const columns: TableColumn<Tenant>[] = [
    {
      key: 'tenant',
      header: t('superadmin.tenant'),
      sortable: true,
      sortValue: (tn) => tn.name,
      render: (tn) => (
        <span style={{ minWidth: 0, display: 'block' }}>
          <span className="trunc" style={{ display: 'block', fontWeight: 500 }}>{tn.name}</span>
          <span className="faint mono trunc" style={{ display: 'block', fontSize: 'var(--fs-xs)' }}>{tn.slug}</span>
        </span>
      ),
    },
    {
      key: 'plan',
      header: t('superadmin.plan'),
      width: 130,
      sortable: true,
      sortValue: (tn) => tn.plan,
      render: (tn) => (
        <Pill tone={PLAN_TONES[tn.plan]} dot={false}>
          {t(`superadmin.plans.${tn.plan}`, { defaultValue: tn.plan })}
        </Pill>
      ),
    },
    {
      key: 'status',
      header: t('common.status'),
      width: 110,
      sortable: true,
      sortValue: (tn) => (tn.is_active ? 0 : 1),
      render: (tn) => (
        <Pill tone={tn.is_active ? 'ok' : 'da'}>
          {tn.is_active ? t('status.active') : t('status.inactive')}
        </Pill>
      ),
    },
    {
      key: 'actions',
      header: '',
      width: 80,
      align: 'right',
      render: (tn) => (
        <Link
          to={`/super-admin/tenants/${tn.id}`}
          style={{ color: 'var(--p)', fontWeight: 500, fontSize: 'var(--fs-sm)' }}
        >
          {t('superadmin.dashboard.view')}
        </Link>
      ),
    },
  ]

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>
          {t('nav.platformOverview')}
        </h1>
        <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>
          {t('superadmin.dashboard.subtitle')}
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        <Stat
          icon={BuildingOffice2Icon}
          label={t('superadmin.dashboard.totalTenants')}
          value={stats?.total_tenants || 0}
        />
        <Stat
          icon={CheckCircleIcon}
          label={t('superadmin.dashboard.activeTenants')}
          value={stats?.active_tenants || 0}
        />
        <Stat
          icon={UserGroupIcon}
          label={t('superadmin.dashboard.totalUsers')}
          value={stats?.total_users || 0}
        />
        <Stat
          icon={DocumentTextIcon}
          label={t('superadmin.dashboard.totalContracts')}
          value={stats?.total_contracts || 0}
        />
      </div>

      {/* Secondary panels */}
      <div className="grid gap-3 grid-cols-1 lg:grid-cols-3">
        {/* Plan distribution */}
        <div className="card card-p">
          <div className="sec-t" style={{ marginBottom: 12 }}>{t('superadmin.dashboard.planDistribution')}</div>
          <div className="col" style={{ gap: 12 }}>
            {(['starter', 'professional', 'enterprise'] as TenantPlan[]).map((plan) => {
              const count = stats?.plan_distribution?.[plan] || 0
              const total = stats?.total_tenants || 1
              const percentage = Math.round((count / total) * 100)
              return (
                <div key={plan}>
                  <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                      {t(`superadmin.plans.${plan}`, { defaultValue: plan })}
                    </span>
                    <span className="muted num" style={{ fontSize: 'var(--fs-sm)' }}>
                      {t('superadmin.dashboard.tenantsCount', { count })}
                    </span>
                  </div>
                  <Bar value={percentage} width="100%" tone={PLAN_BAR_TONES[plan]} />
                </div>
              )
            })}
          </div>
        </div>

        {/* Platform value */}
        <div className="card card-p">
          <div className="sec-t" style={{ marginBottom: 12 }}>{t('superadmin.dashboard.platformValue')}</div>
          <div className="row" style={{ gap: 12 }}>
            <span
              style={{
                width: 38, height: 38, borderRadius: 'var(--r-md)', display: 'grid', placeItems: 'center',
                background: 'var(--ok-f)', color: 'var(--ok)', flexShrink: 0,
              }}
            >
              <CurrencyDollarIcon style={{ width: 19, height: 19 }} aria-hidden />
            </span>
            <span style={{ minWidth: 0 }}>
              <span className="num" style={{ display: 'block', fontSize: 'var(--fs-2xl)', fontWeight: 600, letterSpacing: '-.5px' }}>
                {formatCurrency(stats?.total_value || 0)}
              </span>
              <span className="faint" style={{ display: 'block', fontSize: 'var(--fs-sm)' }}>
                {t('superadmin.dashboard.totalValueDesc')}
              </span>
            </span>
          </div>
        </div>

        {/* Quick actions */}
        <div className="card card-p">
          <div className="sec-t" style={{ marginBottom: 12 }}>{t('superadmin.quickActions')}</div>
          <div className="col" style={{ gap: 8 }}>
            <QuickAction to="/super-admin/tenants" label={t('superadmin.dashboard.manageTenants')} />
            <QuickAction to="/super-admin/users" label={t('superadmin.dashboard.viewAllUsers')} />
            <QuickAction to="/super-admin/custom-fields" label={t('superadmin.configureCustomFields')} />
          </div>
        </div>
      </div>

      {/* Recent tenants */}
      <div className="col" style={{ gap: 10 }}>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <span className="sec-t">{t('superadmin.dashboard.recentTenants')}</span>
          <Link
            to="/super-admin/tenants"
            style={{ color: 'var(--p)', fontWeight: 500, fontSize: 'var(--fs-sm)' }}
          >
            {t('superadmin.dashboard.viewAll')}
          </Link>
        </div>
        <Table
          columns={columns}
          rows={recentTenants}
          rowKey={(tn) => tn.id}
          minWidth={560}
          empty={
            <EmptyState
              icon={BuildingOffice2Icon}
              title={t('superadmin.tenants.noTenants')}
            />
          }
        />
      </div>
    </div>
  )
}
