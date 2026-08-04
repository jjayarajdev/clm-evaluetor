/* Renewal radar — Direction B redesign.
   Summary stats → urgency-bucket window cards (clickable filters) → renewal
   table with expiry/notice countdowns, auto-renewal tags and SLA bars.
   Data fetching, bucket logic (incl. the "All includes expired" dedupe fix)
   and the ICS export flow are unchanged from the pre-redesign page. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  ArrowDownTrayIcon,
  ArrowPathIcon,
  CalendarIcon,
  CheckCircleIcon,
  ClockIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { Bar, Button, EmptyState, Stat, Table, Tag, useToast } from '@/components/ui'
import type { IconType, TableColumn } from '@/components/ui'
import { formatCurrency } from '@/lib/utils'
import type { ContractRenewalInfo } from '@/types/postsigning'

type WindowTone = 'da' | 'wa' | 'in'

// ── Urgency bucket card ──────────────────────────────────────────

function WindowCard({
  icon: Icon,
  label,
  count,
  valueLabel,
  tone,
  active,
  onClick,
}: {
  icon: IconType
  label: string
  count: number
  valueLabel: string
  tone?: WindowTone
  active: boolean
  onClick: () => void
}) {
  const accent = `var(--${tone || 'p'})`
  return (
    <div
      className="card"
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick()
        }
      }}
      style={{
        padding: 14,
        cursor: 'pointer',
        background: active ? `var(--${tone || 'p'}-f)` : undefined,
        borderColor: active ? `var(--${tone || 'p'}-b)` : undefined,
        transition: 'border-color .12s, background .12s',
      }}
    >
      <div className="row" style={{ gap: 6, fontSize: 'var(--fs-sm)', fontWeight: 500, color: active ? accent : 'var(--m)' }}>
        <Icon style={{ width: 14, height: 14, flexShrink: 0 }} aria-hidden />
        <span className="trunc">{label}</span>
      </div>
      <div
        className="num"
        style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-1px', marginTop: 7, lineHeight: 1.1, color: active ? accent : undefined }}
      >
        {count}
      </div>
      <div className="trunc num" style={{ fontSize: 'var(--fs-sm)', marginTop: 3, color: active ? accent : 'var(--f)' }}>
        {valueLabel}
      </div>
    </div>
  )
}

// ── Table cells ──────────────────────────────────────────────────

/** Expiration date plus a colored countdown hint (red ≤30d / amber ≤60d / red overdue). */
function ExpiresCell({ contract }: { contract: ContractRenewalInfo }) {
  const { t } = useTranslation()
  if (!contract.expiration_date) return <span className="faint">{t('renewals.noDate')}</span>
  const d = contract.days_until_expiration
  const hint =
    d == null
      ? null
      : d < 0
        ? { text: t('contracts.daysAgo', { count: Math.abs(d), defaultValue: '{{count}}d ago' }), color: 'var(--da)' }
        : d <= 30
          ? { text: t('contracts.inDays', { count: d, defaultValue: 'in {{count}}d' }), color: 'var(--da)' }
          : d <= 60
            ? { text: t('contracts.inDays', { count: d, defaultValue: 'in {{count}}d' }), color: 'var(--wa)' }
            : null
  return (
    <span className="num nw" style={{ display: 'inline-block' }}>
      {new Date(contract.expiration_date).toLocaleDateString()}
      {hint && (
        <span style={{ display: 'block', fontSize: 'var(--fs-xs)', color: hint.color, fontWeight: 600 }}>{hint.text}</span>
      )}
    </span>
  )
}

/** Notice deadline with "window closed" / days-to-notice countdown. */
function NoticeCell({ contract }: { contract: ContractRenewalInfo }) {
  const { t } = useTranslation()
  if (!contract.notice_deadline) {
    return contract.notice_period_days ? (
      <span className="muted num nw">{t('renewals.daysCount', { count: contract.notice_period_days })}</span>
    ) : (
      <span className="faint">—</span>
    )
  }
  const dn = contract.days_until_notice_deadline
  return (
    <span className="num nw" style={{ display: 'inline-block' }}>
      {new Date(contract.notice_deadline).toLocaleDateString()}
      {contract.is_past_notice_deadline ? (
        <span style={{ display: 'block', fontSize: 'var(--fs-xs)', color: 'var(--da)', fontWeight: 600 }}>
          {t('renewals.noticeWindowClosed', { defaultValue: 'window closed' })}
        </span>
      ) : (
        dn != null &&
        dn < 30 && (
          <span style={{ display: 'block', fontSize: 'var(--fs-xs)', color: 'var(--wa)', fontWeight: 600 }}>
            {t('contracts.inDays', { count: dn, defaultValue: 'in {{count}}d' })}
          </span>
        )
      )}
    </span>
  )
}

/** SLA compliance bar (≥90 ok / ≥70 warn / else danger) plus active-breach note. */
function SlaCell({ contract }: { contract: ContractRenewalInfo }) {
  const { t } = useTranslation()
  const rate = contract.sla_compliance_rate
  if (rate == null) return <span className="faint">—</span>
  const tone = rate >= 90 ? 'var(--ok)' : rate >= 70 ? 'var(--wa)' : 'var(--da)'
  return (
    <span style={{ display: 'inline-block' }}>
      <span className="row" style={{ gap: 7 }}>
        <Bar value={rate} width={56} tone={tone} />
        <span className="mono num" style={{ fontSize: 'var(--fs-sm)', fontWeight: 500, color: tone }}>
          {rate.toFixed(0)}%
        </span>
      </span>
      {contract.active_sla_breaches > 0 && (
        <span style={{ display: 'block', fontSize: 'var(--fs-xs)', color: 'var(--da)', fontWeight: 600, marginTop: 2 }}>
          {t('renewals.activeSlaBreaches', { count: contract.active_sla_breaches })}
        </span>
      )}
    </span>
  )
}

// ── Page ─────────────────────────────────────────────────────────

export default function RenewalsPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [selectedWindow, setSelectedWindow] = useState<string>('all')
  const [isExporting, setIsExporting] = useState(false)

  const { data: calendar, isLoading, error } = useQuery({
    queryKey: ['renewal-calendar'],
    queryFn: () => api.getRenewalCalendar(),
  })

  const handleExportCalendar = async () => {
    setIsExporting(true)
    try {
      const blob = await api.exportCalendarICS({
        include_expirations: true,
        include_notice_deadlines: true,
        include_obligations: true,
        include_key_dates: true,
        days_ahead: 365,
      })
      // Create download link
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `clm-calendar-${new Date().toISOString().split('T')[0]}.ics`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      toast({ text: t('renewals.exportDone', { defaultValue: 'Calendar exported (.ics)' }) })
    } catch (err) {
      console.error('Failed to export calendar:', err)
      toast({ text: t('renewals.exportFailed', { defaultValue: 'Calendar export failed' }), error: true })
    } finally {
      setIsExporting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !calendar) {
    return (
      <div className="banner banner-da">
        <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
        <span>{t('renewals.loadError')}</span>
      </div>
    )
  }

  // "All" = every renewal-relevant contract, INCLUDING expired (the bug:
  // expired was omitted, so All showed empty when everything was expired).
  // Dedupe by contract_id since buckets (e.g. critical + 30-day) overlap.
  const seen = new Set<string>()
  const allContracts = [
    ...calendar.critical,
    ...calendar.within_30_days,
    ...calendar.within_60_days,
    ...calendar.within_90_days,
    ...calendar.expired,
  ].filter((c) => {
    if (seen.has(c.contract_id)) return false
    seen.add(c.contract_id)
    return true
  })

  const upcomingCurrency = calendar.upcoming_value_currency || 'USD'
  const expiredCurrency = calendar.expired_value_currency || 'USD'
  const sumValue = (list: ContractRenewalInfo[]) => list.reduce((s, c) => s + (c.contract_value || 0), 0)

  const windows: {
    id: string
    label: string
    icon: IconType
    tone?: WindowTone
    list: ContractRenewalInfo[]
    currency: string
  }[] = [
    { id: 'all', label: t('renewals.all'), icon: CalendarIcon, list: allContracts, currency: upcomingCurrency },
    { id: 'critical', label: t('risk.critical'), icon: ExclamationTriangleIcon, tone: 'da', list: calendar.critical, currency: upcomingCurrency },
    { id: 'within_30_days', label: t('renewals.days30'), icon: ClockIcon, tone: 'da', list: calendar.within_30_days, currency: upcomingCurrency },
    { id: 'within_60_days', label: t('renewals.days60'), icon: ClockIcon, tone: 'wa', list: calendar.within_60_days, currency: upcomingCurrency },
    { id: 'within_90_days', label: t('renewals.days90'), icon: ClockIcon, tone: 'in', list: calendar.within_90_days, currency: upcomingCurrency },
    { id: 'expired', label: t('status.expired'), icon: ExclamationTriangleIcon, tone: 'da', list: calendar.expired, currency: expiredCurrency },
  ]

  const contracts = windows.find((w) => w.id === selectedWindow)?.list ?? allContracts

  const columns: TableColumn<ContractRenewalInfo>[] = [
    {
      key: 'filename',
      header: t('renewals.contract', { defaultValue: 'Contract' }),
      sortable: true,
      render: (c) => (
        <span style={{ display: 'inline-block', minWidth: 0 }}>
          <span style={{ fontWeight: 500 }}>{c.filename}</span>
          {c.contract_type && (
            <span className="faint" style={{ display: 'block', fontSize: 'var(--fs-sm)', marginTop: 2 }}>
              {c.contract_type}
            </span>
          )}
        </span>
      ),
    },
    {
      key: 'counterparty',
      header: t('renewals.counterparty', { defaultValue: 'Counterparty' }),
      sortable: true,
      width: 160,
      render: (c) => <span className="muted">{c.counterparty || t('renewals.unknownCounterparty')}</span>,
    },
    {
      key: 'expires',
      header: t('renewals.expiration'),
      align: 'right',
      width: 130,
      sortable: true,
      sortValue: (c) => c.days_until_expiration,
      render: (c) => <ExpiresCell contract={c} />,
    },
    {
      key: 'notice',
      header: t('renewals.noticeBy', { defaultValue: 'Notice by' }),
      align: 'right',
      width: 128,
      sortable: true,
      sortValue: (c) => c.days_until_notice_deadline,
      render: (c) => <NoticeCell contract={c} />,
    },
    {
      key: 'auto',
      header: t('renewals.autoRenew'),
      width: 130,
      render: (c) =>
        c.auto_renewal ? (
          <Tag icon={ArrowPathIcon}>{t('renewals.autoRenew')}</Tag>
        ) : (
          <span className="faint">—</span>
        ),
    },
    {
      key: 'value',
      header: t('renewals.contractValue'),
      align: 'right',
      width: 120,
      sortable: true,
      sortValue: (c) => c.contract_value,
      render: (c) => (
        <span className="num nw" style={{ fontWeight: 500 }}>
          {c.contract_value ? `$${c.contract_value.toLocaleString()}` : <span className="faint">—</span>}
        </span>
      ),
    },
    {
      key: 'sla',
      header: t('renewals.slaCompliance'),
      width: 160,
      render: (c) => <SlaCell contract={c} />,
    },
  ]

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div className="row" style={{ alignItems: 'flex-start' }}>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>{t('renewals.title')}</h1>
          <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>{t('renewals.description')}</p>
        </div>
        <Button variant="primary" icon={ArrowDownTrayIcon} onClick={handleExportCalendar} disabled={isExporting}>
          {isExporting ? t('renewals.exporting') : t('renewals.exportToCalendar')}
        </Button>
      </div>

      {/* Summary stats */}
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        <Stat
          icon={ExclamationTriangleIcon}
          label={t('renewals.needAction')}
          value={calendar.requires_action_count}
          sub={t('renewals.needActionSub', { defaultValue: 'notice window open or closing' })}
          subTone={calendar.requires_action_count > 0 ? 'var(--da)' : undefined}
        />
        <Stat
          icon={ArrowPathIcon}
          label={t('renewals.autoRenewing')}
          value={calendar.auto_renewal_count}
          sub={t('renewals.autoRenewingSub', { defaultValue: 'renew unless notice is given' })}
        />
        <Stat
          icon={CalendarIcon}
          label={t('renewals.totalExpiring')}
          value={calendar.total_contracts}
          sub={t('renewals.totalExpiringSub', { defaultValue: 'in the next 90 days' })}
        />
        <Stat
          icon={ClockIcon}
          label={t('renewals.valueAtRisk')}
          value={formatCurrency(calendar.upcoming_value_at_risk ?? calendar.total_value_at_risk, upcomingCurrency)}
          sub={
            calendar.expired_value
              ? t('renewals.expiredValueNote', { value: formatCurrency(calendar.expired_value, expiredCurrency) })
              : undefined
          }
          subTone="var(--wa)"
        />
      </div>

      {/* Urgency buckets — clickable window filter */}
      <div className="grid gap-3 grid-cols-2 md:grid-cols-3 lg:grid-cols-6">
        {windows.map((w) => (
          <WindowCard
            key={w.id}
            icon={w.icon}
            label={w.label}
            count={w.list.length}
            valueLabel={
              w.id === 'expired'
                ? t('renewals.lapsedValue', { value: formatCurrency(sumValue(w.list), w.currency) })
                : t('renewals.atStake', {
                    value: formatCurrency(sumValue(w.list), w.currency),
                    defaultValue: '{{value}} at stake',
                  })
            }
            tone={w.tone}
            active={selectedWindow === w.id}
            onClick={() => setSelectedWindow(w.id)}
          />
        ))}
      </div>

      {/* Expired bucket callout */}
      {selectedWindow === 'expired' && calendar.expired.length > 0 && (
        <div className="banner banner-da">
          <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
          <span>
            <b>{t('renewals.expiredCount', { count: calendar.expired.length, defaultValue: '{{count}} contracts have expired' })}</b>
            {' — '}
            {t('renewals.lapsedValue', {
              value: formatCurrency(calendar.expired_value ?? sumValue(calendar.expired), expiredCurrency),
            })}
          </span>
        </div>
      )}

      {/* Renewal table */}
      <Table
        columns={columns}
        rows={contracts}
        rowKey={(c) => c.contract_id}
        onRowClick={(c) => navigate(`/contracts/${c.contract_id}`)}
        minWidth={920}
        empty={
          <EmptyState
            icon={CheckCircleIcon}
            title={t('renewals.noContractsInWindow')}
            body={t('renewals.emptyBody', { defaultValue: 'Nothing needs a renewal decision in this window.' })}
            action={
              selectedWindow !== 'expired' && calendar.expired.length > 0 ? (
                <Button variant="secondary" size="sm" onClick={() => setSelectedWindow('expired')}>
                  {t('renewals.openExpiredBucket', {
                    count: calendar.expired.length,
                    defaultValue: 'View {{count}} expired',
                  })}
                </Button>
              ) : undefined
            }
          />
        }
      />
    </div>
  )
}
