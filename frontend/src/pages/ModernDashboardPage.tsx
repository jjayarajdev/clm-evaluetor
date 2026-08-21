/**
 * Dashboard — Direction B design system.
 * Role-specific quick actions, config-driven stat grid, priority actions,
 * recent contracts, AI insights and activity feed. Data layer unchanged.
 */
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  DocumentTextIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  ScaleIcon,
  CurrencyDollarIcon,
  BellAlertIcon,
  ArrowRightIcon,
  SparklesIcon,
  ChartBarIcon,
  Cog6ToothIcon,
  ArrowUpTrayIcon,
} from '@heroicons/react/24/outline'
import { useAuth } from '@/contexts/AuthContext'
import { can } from '@/lib/rbac'
import { useTenantConfig } from '@/contexts/TenantConfigContext'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { Stat, Pill, Tag, Chip, Tooltip, EmptyState, Button } from '@/components/ui'
import type { PillTone, IconType } from '@/components/ui'
import { formatCurrency } from '@/lib/utils'
import type { ContractsSummaryResponse } from '@/types'
import type { PostSigningDashboard } from '@/types/postsigning'

type RoleType = 'admin' | 'legal' | 'procurement' | 'bu_head' | 'viewer'

// Backend returns fixed English titles for insights/activity; translate them by
// slugging the English string into an i18n key (fallback keeps the English).
const slugKey = (s: string) => (s || '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')

// Dashboard stat widgets come from the tenant/industry config with hardcoded
// English labels; translate by their stable key (fallback keeps the config label
// for industry-specific customizations we don't have a translation for).
const WIDGET_LABEL_I18N: Record<string, string> = {
  total_contracts: 'dashboard.widgets.totalContracts',
  at_risk: 'dashboard.widgets.atRisk',
  at_risk_contracts: 'dashboard.widgets.atRisk',
  compliance_rate: 'dashboard.widgets.compliance',
  total_value: 'dashboard.widgets.contractValue',
  obligation_rate: 'dashboard.widgets.obligations',
  sla_rate: 'dashboard.widgets.slaPerformance',
  sla_performance: 'dashboard.widgets.slaPerformance',
}

// Map config icon names to Heroicon components for stat cards
const WIDGET_ICON_MAP: Record<string, IconType> = {
  document: DocumentTextIcon,
  warning: ExclamationTriangleIcon,
  check: CheckCircleIcon,
  currency: CurrencyDollarIcon,
  scale: ScaleIcon,
  chart: ChartBarIcon,
  clock: ClockIcon,
}

// Stats that map to a filtered page are clickable.
const WIDGET_LINK: Record<string, string> = {
  total_contracts: '/contracts',
  at_risk: '/contracts?risk=high',
  at_risk_contracts: '/contracts?risk=high',
  compliance_rate: '/compliance',
  obligation_rate: '/compliance',
  sla_rate: '/compliance',
  sla_performance: '/compliance',
}

const RISK_TONE: Record<string, PillTone> = { low: 'ok', medium: 'wa', high: 'da', critical: 'da' }
const SEVERITY_TONE: Record<string, PillTone> = { critical: 'da', high: 'wa' }
const ACTIVITY_COLOR: Record<string, string> = {
  gray: 'var(--m)', green: 'var(--ok)', red: 'var(--da)', amber: 'var(--wa)', blue: 'var(--in)',
}
const BADGE_COLOR: Record<string, string> = { red: 'var(--da)', amber: 'var(--wa)', blue: 'var(--in)' }

function CardHeader({ icon: Icon, iconColor, title, count, countTone, viewTo, viewLabel }: {
  icon?: React.ElementType
  iconColor?: string
  title: string
  count?: number
  countTone?: PillTone
  viewTo?: string
  viewLabel?: string
}) {
  return (
    <div className="row" style={{ gap: 8, padding: '12px 16px', borderBottom: '1px solid var(--b)' }}>
      {Icon && <Icon style={{ width: 16, height: 16, color: iconColor || 'var(--m)', flexShrink: 0 }} aria-hidden />}
      <b style={{ fontSize: 'var(--fs-lg)' }}>{title}</b>
      {count != null && count > 0 && <Pill tone={countTone || 'n'} dot={false}>{count}</Pill>}
      <span className="grow" />
      {viewTo && (
        <Link
          to={viewTo}
          className="row"
          style={{ gap: 4, fontSize: 'var(--fs-sm)', fontWeight: 600, color: 'var(--p)', textDecoration: 'none' }}
        >
          {viewLabel}
          <ArrowRightIcon style={{ width: 12, height: 12 }} aria-hidden />
        </Link>
      )}
    </div>
  )
}

export default function ModernDashboardPage() {
  const { user } = useAuth()
  const { t } = useTranslation()
  const { config } = useTenantConfig()
  const navigate = useNavigate()
  const userRole = (user?.role || 'viewer') as RoleType

  // Fetch summary data
  const { data: summaryData, isLoading } = useQuery<ContractsSummaryResponse>({
    queryKey: ['contracts-summary'],
    queryFn: () => api.getContractsSummary(),
  })

  // Fetch postsigning data for compliance metrics
  const { data: complianceData } = useQuery<PostSigningDashboard>({
    queryKey: ['postsigning-dashboard'],
    queryFn: () => api.getPostSigningDashboard(),
  })

  // Fetch trend data
  const { data: trendData } = useQuery({
    queryKey: ['dashboard-trends'],
    queryFn: () => api.getDashboardTrends(9),
  })

  // Fetch AI insights
  const { data: insightsData, isError: insightsError } = useQuery({
    queryKey: ['dashboard-insights'],
    queryFn: () => api.getDashboardInsights(),
    retry: 1,
  })

  // Fetch recent activity
  const { data: activityData, isError: activityError } = useQuery({
    queryKey: ['recent-activity'],
    queryFn: () => api.getRecentActivity(10),
    retry: 1,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  // ---- Role-based quick actions (same targets/badges as before) ----
  const highRiskCount = summaryData?.by_risk?.high || 0
  const pendingCount = summaryData?.by_status?.pending || 0
  const expiringCount = complianceData?.renewals?.expiring_30_days || 0
  const slaBreaches = complianceData?.slas?.critical_breaches || 0
  const overdueCount = complianceData?.obligations?.overdue || 0

  type QuickAction = {
    label: string
    description: string
    href: string
    icon: IconType
    badge?: number
    badgeColor?: 'red' | 'amber' | 'blue'
  }
  const actionsByRole: Record<RoleType, QuickAction[]> = {
    legal: [
      { label: t('dashboard.actions.highRisk'), description: t('dashboard.actions.highRiskDesc'), href: '/contracts?risk=high', icon: ExclamationTriangleIcon, badge: highRiskCount || undefined, badgeColor: 'red' },
      { label: t('dashboard.actions.pendingReview'), description: t('dashboard.actions.pendingReviewDesc'), href: '/contracts?status=pending', icon: ClockIcon, badge: pendingCount || undefined, badgeColor: 'amber' },
      { label: t('dashboard.actions.askAi'), description: t('dashboard.actions.askAiDesc'), href: '/query', icon: SparklesIcon },
    ],
    procurement: [
      { label: t('dashboard.actions.expiringSoon'), description: t('dashboard.actions.expiringSoonDesc'), href: '/renewals?window=30', icon: ClockIcon, badge: expiringCount || undefined, badgeColor: 'amber' },
      { label: t('dashboard.actions.vendors'), description: t('dashboard.actions.vendorsDesc'), href: '/vendors', icon: ChartBarIcon },
      { label: t('dashboard.actions.newContract'), description: t('dashboard.actions.newContractDesc'), href: '/upload', icon: SparklesIcon },
    ],
    admin: [
      { label: t('dashboard.actions.slaBreaches'), description: t('dashboard.actions.slaBreachesDesc'), href: '/compliance', icon: ExclamationTriangleIcon, badge: slaBreaches || undefined, badgeColor: 'red' },
      { label: t('dashboard.actions.overdue'), description: t('dashboard.actions.overdueDesc'), href: '/compliance', icon: BellAlertIcon, badge: overdueCount || undefined, badgeColor: 'amber' },
      { label: t('dashboard.actions.renewals'), description: t('dashboard.actions.renewalsDesc'), href: '/renewals', icon: ClockIcon, badge: expiringCount || undefined, badgeColor: 'amber' },
      { label: t('dashboard.actions.systemHealth'), description: t('dashboard.actions.systemHealthDesc'), href: '/admin/scheduler', icon: ChartBarIcon },
      { label: t('dashboard.actions.settings'), description: t('dashboard.actions.settingsDesc'), href: '/settings', icon: Cog6ToothIcon },
    ],
    bu_head: [
      { label: t('dashboard.actions.myContracts'), description: t('dashboard.actions.myContractsDesc'), href: '/contracts', icon: DocumentTextIcon },
      { label: t('dashboard.actions.expiringSoon'), description: t('dashboard.actions.expiringSoonDesc'), href: '/renewals?window=30', icon: ClockIcon, badge: expiringCount || undefined, badgeColor: 'amber' },
      { label: t('dashboard.actions.reports'), description: t('dashboard.actions.reportsDesc'), href: '/reports', icon: ChartBarIcon },
    ],
    viewer: [
      { label: t('dashboard.actions.browse'), description: t('dashboard.actions.browseDesc'), href: '/contracts', icon: ChartBarIcon },
      { label: t('dashboard.actions.askAi'), description: t('dashboard.actions.askAiDesc'), href: '/query', icon: SparklesIcon },
      { label: t('dashboard.actions.reports'), description: t('dashboard.actions.viewAnalyticsDesc'), href: '/reports', icon: ChartBarIcon },
    ],
  }
  const quickActions = actionsByRole[userRole] || actionsByRole.viewer

  const hour = new Date().getHours()
  const greetKey = hour < 12 ? 'dashboard.goodMorning' : hour < 18 ? 'dashboard.goodAfternoon' : 'dashboard.goodEvening'

  // ---- Stat widgets (config-driven; honest "—" for unmeasured rates) ----
  const pct = (v: number | null | undefined) => (v == null ? '—' : `${v.toFixed(1)}%`)
  const rateTone = (v: number | null | undefined) =>
    v == null ? undefined : v >= 90 ? 'var(--ok)' : v >= 70 ? 'var(--wa)' : 'var(--da)'

  const trendDelta = (series: number[] | undefined, absolute = false): number | undefined => {
    if (!series || series.length < 2) return undefined
    const first = series[0]
    const last = series[series.length - 1]
    return absolute ? Math.round(last - first) : Math.round(((last - first) / Math.max(first, 1)) * 100)
  }

  // sub line: trend delta ("+12% vs last week") and/or an info footnote
  const subNode = (opts: { trend?: number; trendUnit?: string; upIsBad?: boolean; info?: string; infoTone?: string }) => {
    const { trend, trendUnit = '%', upIsBad, info, infoTone } = opts
    if (trend == null && !info) return undefined
    const trendColor = trend == null || trend === 0 ? 'var(--f)' : (trend > 0) !== !!upIsBad ? 'var(--ok)' : 'var(--da)'
    return (
      <span className="col" style={{ gap: 2, minWidth: 0 }}>
        {trend != null && (
          <span style={{ color: trendColor, fontWeight: 500 }}>
            {trend > 0 ? '+' : ''}{trend}{trendUnit} {t('dashboard.vsLastWeek')}
          </span>
        )}
        {info && <span className="trunc" style={{ color: infoTone || 'var(--f)' }} title={info}>{info}</span>}
      </span>
    )
  }

  const valueInfo = (() => {
    const valued = complianceData?.valued_contracts ?? 0
    const total = complianceData?.total_contracts ?? 0
    if (!valued) return undefined
    const others = Object.keys(complianceData?.total_value_by_currency || {}).filter(c => c !== (complianceData?.total_value_currency || 'USD'))
    let s = t('dashboard.valueCoverage', { valued, total })
    if (others.length) s += ' · ' + t('dashboard.valueOtherCurrencies', { currencies: others.join(', ') })
    return s
  })()

  const widgetDataMap: Record<string, { value: React.ReactNode; icon: IconType; sub?: React.ReactNode }> = {
    total_contracts: {
      value: summaryData?.total_contracts || 0,
      icon: DocumentTextIcon,
      sub: subNode({ trend: trendDelta(trendData?.total_contracts) }),
    },
    at_risk: {
      value: (
        <span style={{ color: (complianceData?.compliance?.contracts_at_risk ?? summaryData?.by_risk?.high ?? 0) > 0 ? 'var(--da)' : undefined }}>
          {complianceData?.compliance?.contracts_at_risk ?? summaryData?.by_risk?.high ?? 0}
        </span>
      ),
      icon: ExclamationTriangleIcon,
      sub: subNode({ trend: trendDelta(trendData?.contracts_at_risk), upIsBad: true }),
    },
    compliance_rate: {
      value: (
        <span style={{ color: rateTone(complianceData?.compliance?.overall_compliance_rate) }}>
          {pct(complianceData?.compliance?.overall_compliance_rate)}
        </span>
      ),
      icon: CheckCircleIcon,
      sub: subNode({ trend: trendDelta(trendData?.compliance_rate, true), trendUnit: 'pt', info: t('dashboard.complianceInfo') }),
    },
    total_value: {
      value: complianceData?.total_value ? formatCurrency(complianceData.total_value, complianceData.total_value_currency || 'USD') : 'N/A',
      icon: CurrencyDollarIcon,
      sub: subNode({ trend: trendDelta(trendData?.total_contract_value), info: valueInfo }),
    },
    obligation_rate: {
      value: (
        <span style={{ color: rateTone(complianceData?.obligations?.compliance_rate) }}>
          {pct(complianceData?.obligations?.compliance_rate)}
        </span>
      ),
      icon: ScaleIcon,
      sub: complianceData?.obligations?.compliance_rate == null ? subNode({ info: t('dashboard.notTracked') }) : undefined,
    },
    sla_rate: {
      value: (
        <span style={{ color: rateTone(complianceData?.slas?.compliance_rate) }}>
          {pct(complianceData?.slas?.compliance_rate)}
        </span>
      ),
      icon: ChartBarIcon,
      sub: complianceData?.slas?.compliance_rate == null ? subNode({ info: t('dashboard.notMeasured') }) : undefined,
    },
  }

  const widgets = config?.ui?.dashboard_widgets || [
    { key: 'total_contracts', label: t('dashboard.widgets.totalContracts'), icon: 'document' },
    { key: 'at_risk', label: t('dashboard.widgets.atRisk'), icon: 'warning' },
    { key: 'compliance_rate', label: t('dashboard.widgets.compliance'), icon: 'check' },
    { key: 'total_value', label: t('dashboard.widgets.contractValue'), icon: 'currency' },
    { key: 'obligation_rate', label: t('dashboard.widgets.obligations'), icon: 'scale' },
    { key: 'sla_rate', label: t('dashboard.widgets.slaPerformance'), icon: 'chart' },
  ]
  const colClass = widgets.length <= 4 ? 'lg:grid-cols-4' : widgets.length <= 5 ? 'lg:grid-cols-5' : 'lg:grid-cols-6'

  const recentContracts = summaryData?.contracts?.slice(0, 4) || []
  const priorityActions = complianceData?.priority_actions?.slice(0, 5) || []
  const activities = activityData?.activities?.slice(0, 5) || []
  const insights = insightsData?.insights || []

  const activityIconMap: Record<string, React.ElementType> = {
    document: DocumentTextIcon,
    check: CheckCircleIcon,
    warning: ExclamationTriangleIcon,
    clock: ClockIcon,
    sparkles: SparklesIcon,
    pencil: DocumentTextIcon,
  }

  return (
    <div className="col pb-8" style={{ gap: 20 }}>
      {/* Heading + role quick actions */}
      <div className="row" style={{ gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div className="grow" style={{ minWidth: 200 }}>
          <h1 style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600, letterSpacing: '-.4px' }}>
            {t(greetKey)}, {user?.full_name || user?.username || 'User'}
          </h1>
          <div className="muted" style={{ fontSize: 'var(--fs-sm)', marginTop: 2 }}>
            {t('dashboard.portfolioOverview', { role: t(`roles.${userRole}`, { defaultValue: userRole.replace('_', ' ') }) })}
          </div>
        </div>
        <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
          {quickActions.map((a) => (
            <Tooltip key={a.href + a.label} label={a.description}>
              <Chip icon={a.icon} onClick={() => navigate(a.href)}>
                {a.label}
                {a.badge != null && (
                  <b className="num" style={{ color: BADGE_COLOR[a.badgeColor || 'blue'], fontWeight: 700 }}>{a.badge}</b>
                )}
              </Chip>
            </Tooltip>
          ))}
        </div>
      </div>

      {/* Stats grid — driven by config.ui.dashboard_widgets */}
      <div className={`grid grid-cols-2 sm:grid-cols-3 ${colClass} gap-3`}>
        {widgets.map((w) => {
          const data = widgetDataMap[w.key]
          if (!data) return null
          const link = WIDGET_LINK[w.key]
          return (
            <Stat
              key={w.key}
              icon={WIDGET_ICON_MAP[w.icon || ''] || data.icon}
              label={WIDGET_LABEL_I18N[w.key] ? t(WIDGET_LABEL_I18N[w.key], { defaultValue: w.label }) : w.label}
              value={data.value}
              sub={data.sub}
              onClick={link ? () => navigate(link) : undefined}
            />
          )
        })}
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
        {/* Left — priority actions + recent contracts */}
        <div className="lg:col-span-2 col" style={{ gap: 16 }}>
          {priorityActions.length > 0 && (
            <div className="card" style={{ overflow: 'hidden' }}>
              <CardHeader
                icon={BellAlertIcon}
                iconColor="var(--wa)"
                title={t('dashboard.priorityActions')}
                count={complianceData?.priority_actions?.length}
                countTone="wa"
                viewTo="/compliance"
                viewLabel={t('dashboard.viewAllActions')}
              />
              {priorityActions.map((action, idx) => {
                const TypeIcon = action.type === 'obligation' ? CheckCircleIcon : action.type === 'sla' ? ScaleIcon : ClockIcon
                const tone = SEVERITY_TONE[action.severity] || 'in'
                return (
                  <div
                    key={idx}
                    className="row"
                    style={{ gap: 10, padding: '10px 16px', borderBottom: idx < priorityActions.length - 1 ? '1px solid var(--b)' : 0 }}
                  >
                    <TypeIcon
                      style={{ width: 15, height: 15, flexShrink: 0, color: `var(--${tone})` }}
                      aria-hidden
                    />
                    <span className="grow col" style={{ gap: 1, minWidth: 0 }}>
                      <span className="trunc" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>{action.title}</span>
                      <span className="faint trunc" style={{ fontSize: 'var(--fs-sm)' }}>{action.action}</span>
                    </span>
                    <Pill tone={tone} dot={false}>{action.type}</Pill>
                  </div>
                )
              })}
            </div>
          )}

          <div className="card" style={{ overflow: 'hidden' }}>
            <CardHeader title={t('dashboard.recentContracts')} viewTo="/contracts" viewLabel={t('dashboard.viewAll')} />
            {recentContracts.length === 0 ? (
              <EmptyState
                icon={DocumentTextIcon}
                title={t('dashboard.noContracts', { defaultValue: 'No contracts yet' })}
                body={t('dashboard.noContractsDesc', { defaultValue: 'Upload a contract to start extraction, risk detection and obligation tracking.' })}
                action={
                  can(user, 'upload') ? (
                    <Link to="/upload">
                      <Button variant="primary" size="sm" icon={ArrowUpTrayIcon}>
                        {t('dashboard.actions.newContract')}
                      </Button>
                    </Link>
                  ) : undefined
                }
              />
            ) : (
              recentContracts.map((contract, n) => (
                <Link
                  key={contract.id}
                  to={`/contracts/${contract.id}`}
                  className="row"
                  style={{
                    gap: 10, padding: '11px 16px', textDecoration: 'none', color: 'inherit',
                    borderBottom: n < recentContracts.length - 1 ? '1px solid var(--b)' : 0,
                  }}
                >
                  <Tag>{contract.status}</Tag>
                  <span className="grow trunc" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>{contract.filename}</span>
                  {contract.counterparty && (
                    <span className="faint trunc" style={{ fontSize: 'var(--fs-sm)', maxWidth: 150 }}>{contract.counterparty}</span>
                  )}
                  <Pill tone={RISK_TONE[contract.risk_level || 'low'] || 'ok'}>{contract.risk_level || 'low'}</Pill>
                  <ArrowRightIcon style={{ width: 13, height: 13, color: 'var(--f)', flexShrink: 0 }} aria-hidden />
                </Link>
              ))
            )}
          </div>
        </div>

        {/* Right — AI insights + activity */}
        <div className="col" style={{ gap: 16 }}>
          <div className="card" style={{ overflow: 'hidden' }}>
            <CardHeader icon={SparklesIcon} iconColor="var(--p)" title={t('dashboard.aiInsights')} />
            {insightsError ? (
              <div className="card-p" style={{ fontSize: 'var(--fs-sm)', color: 'var(--da)' }}>
                {t('dashboard.insightsError')}
              </div>
            ) : (
              (insights.length
                ? insights.map((insight) => ({
                    title: t(`dashboard.dyn.${slugKey(insight.title)}`, { defaultValue: insight.title }),
                    description: (insight as any).key
                      ? (t(`dashboard.insightDesc.${(insight as any).key}`, { ...((insight as any).params || {}), defaultValue: insight.description }) as string)
                      : insight.description,
                    action: insight.action,
                    actionLabel: t(`dashboard.dyn.${slugKey(insight.action_label)}`, { defaultValue: insight.action_label }),
                    variant: insight.variant,
                  }))
                : [{
                    title: t('dashboard.allClear'),
                    description: t('dashboard.allClearDesc'),
                    action: '/contracts',
                    actionLabel: t('dashboard.viewContracts'),
                    variant: 'success' as const,
                  }]
              ).map((insight, idx, arr) => {
                const tone = insight.variant === 'warning' ? 'wa' : insight.variant === 'success' ? 'ok' : 'in'
                return (
                  <div
                    key={idx}
                    className="col"
                    style={{ gap: 3, padding: '11px 16px', borderBottom: idx < arr.length - 1 ? '1px solid var(--b)' : 0 }}
                  >
                    <div className="row" style={{ gap: 7 }}>
                      <i style={{ width: 6, height: 6, borderRadius: 99, background: `var(--${tone})`, flexShrink: 0 }} />
                      <span className="trunc" style={{ fontSize: 'var(--fs-md)', fontWeight: 600 }}>{insight.title}</span>
                    </div>
                    <div className="muted" style={{ fontSize: 'var(--fs-sm)', lineHeight: 1.5 }}>{insight.description}</div>
                    <Link
                      to={insight.action}
                      className="row"
                      style={{ gap: 4, fontSize: 'var(--fs-sm)', fontWeight: 600, color: 'var(--p)', textDecoration: 'none', marginTop: 2 }}
                    >
                      {insight.actionLabel}
                      <ArrowRightIcon style={{ width: 11, height: 11 }} aria-hidden />
                    </Link>
                  </div>
                )
              })
            )}
          </div>

          <div className="card" style={{ overflow: 'hidden' }}>
            <CardHeader title={t('dashboard.recentActivity')} />
            {activityError ? (
              <div className="card-p" style={{ fontSize: 'var(--fs-sm)', color: 'var(--da)', textAlign: 'center' }}>
                {t('dashboard.activityError')}
              </div>
            ) : activities.length === 0 ? (
              <EmptyState
                icon={ClockIcon}
                title={t('dashboard.noRecentActivity')}
                body={t('dashboard.noRecentActivityDesc', { defaultValue: 'Uploads, analyses and obligation updates will appear here as they happen.' })}
              />
            ) : (
              activities.map((activity, idx) => {
                const Icon = activityIconMap[activity.icon] || DocumentTextIcon
                return (
                  <div
                    key={idx}
                    className="row"
                    style={{ gap: 10, padding: '10px 16px', borderBottom: idx < activities.length - 1 ? '1px solid var(--b)' : 0 }}
                  >
                    <span
                      style={{
                        width: 26, height: 26, borderRadius: 'var(--r-sm)', background: 'var(--s2)',
                        color: ACTIVITY_COLOR[activity.color] || 'var(--m)',
                        display: 'grid', placeItems: 'center', flexShrink: 0,
                      }}
                    >
                      <Icon style={{ width: 14, height: 14 }} aria-hidden />
                    </span>
                    <span className="grow col" style={{ gap: 1, minWidth: 0 }}>
                      <span className="trunc" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                        {t(`dashboard.dyn.${slugKey(activity.title)}`, { defaultValue: activity.title })}
                      </span>
                      <span className="faint trunc" style={{ fontSize: 'var(--fs-sm)' }}>{activity.subtitle}</span>
                    </span>
                    <span className="faint" style={{ fontSize: 'var(--fs-xs)', whiteSpace: 'nowrap' }}>{activity.time}</span>
                  </div>
                )
              })
            )}
            <Link
              to="/compliance"
              className="row"
              style={{
                justifyContent: 'center', gap: 4, padding: '10px 16px', borderTop: '1px solid var(--b)',
                fontSize: 'var(--fs-sm)', fontWeight: 600, color: 'var(--p)', textDecoration: 'none',
              }}
            >
              {t('dashboard.viewCompliance')}
              <ArrowRightIcon style={{ width: 12, height: 12 }} aria-hidden />
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
