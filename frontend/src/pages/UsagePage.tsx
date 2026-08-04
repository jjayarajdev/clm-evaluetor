/* Usage meters — Direction B redesign.
   Clickable Stat cards select the metric charted in the monthly-trend card
   (token-styled bar rows — no recharts on this page), followed by the raw
   monthly Table. Everyone with the 'usage' permission sees pages/documents;
   the AI section (tokens, actions, estimated cost) renders only when the API
   says so (can_view_ai_usage — tenant admins). Visibility is API-enforced;
   this page just adapts to the fields it receives. */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  BoltIcon,
  ChartBarIcon,
  CircleStackIcon,
  CurrencyDollarIcon,
  DocumentDuplicateIcon,
  DocumentTextIcon,
  LockClosedIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline'
import { getUsageSummary, type UsageMonth } from '@/lib/api/admin'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { EmptyState, Stat, Table } from '@/components/ui'
import type { IconType, TableColumn } from '@/components/ui'

const nf = new Intl.NumberFormat()

function fmtTokens(n?: number): string {
  if (n == null) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return nf.format(n)
}

function monthTokens(m: UsageMonth): number {
  return (m.tokens_prompt ?? 0) + (m.tokens_completion ?? 0) + (m.tokens_embedding ?? 0)
}

type MetricKey = 'pages' | 'docs' | 'actions' | 'tokens' | 'cost'

interface Metric {
  key: MetricKey
  icon: IconType
  label: string
  gated: boolean
  value: (m: UsageMonth) => number
  fmt: (n: number) => string
}

/** Prototype-style monthly bar chart built from token-styled divs. */
function TrendBars({
  months,
  value,
  fmt,
  monthLabel,
  height = 150,
}: {
  months: UsageMonth[]
  value: (m: UsageMonth) => number
  fmt: (n: number) => string
  monthLabel: (m: UsageMonth) => string
  height?: number
}) {
  const max = Math.max(1, ...months.map(value))
  return (
    <div className="row" style={{ gap: 8, alignItems: 'flex-end', height }}>
      {months.map((m) => {
        const v = value(m)
        return (
          <div
            key={m.month}
            className="col"
            style={{ flex: 1, alignItems: 'center', gap: 6, height: '100%', justifyContent: 'flex-end' }}
          >
            <span className="num faint" style={{ fontSize: 'var(--fs-2xs)', fontWeight: 600 }}>
              {fmt(v)}
            </span>
            <div
              style={{
                width: '100%',
                height: Math.max(3, (v / max) * (height - 34)),
                background: 'var(--p)',
                borderRadius: 'var(--r-xs) var(--r-xs) 2px 2px',
                transition: 'height .4s var(--ease)',
              }}
            />
            <span className="faint" style={{ fontSize: 'var(--fs-xs)', fontWeight: 600 }}>
              {monthLabel(m)}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export default function UsagePage() {
  const { t, i18n } = useTranslation()
  const [metric, setMetric] = useState<MetricKey>('pages')
  const { data, isLoading } = useQuery({
    queryKey: ['usage-summary'],
    queryFn: () => getUsageSummary(6),
  })

  if (isLoading || !data) return <LoadingSpinner size="lg" />

  const { totals, months, can_view_ai_usage: showAi } = data
  const currentMonth = months[months.length - 1]

  const totalTokens =
    (totals.tokens_prompt ?? 0) + (totals.tokens_completion ?? 0) + (totals.tokens_embedding ?? 0)

  const metrics: Metric[] = [
    {
      key: 'pages',
      icon: DocumentTextIcon,
      label: t('usage.pagesProcessed', { defaultValue: 'Pages processed' }),
      gated: false,
      value: (m) => m.pages_processed,
      fmt: (n) => nf.format(n),
    },
    {
      key: 'docs',
      icon: DocumentDuplicateIcon,
      label: t('usage.documentsIngested', { defaultValue: 'Documents ingested' }),
      gated: false,
      value: (m) => m.documents_ingested,
      fmt: (n) => nf.format(n),
    },
    {
      key: 'actions',
      icon: BoltIcon,
      label: t('usage.aiActions', { defaultValue: 'AI actions' }),
      gated: true,
      value: (m) => m.ai_actions ?? 0,
      fmt: (n) => nf.format(n),
    },
    {
      key: 'tokens',
      icon: CircleStackIcon,
      label: t('usage.tokens', { defaultValue: 'Tokens' }),
      gated: true,
      value: monthTokens,
      fmt: fmtTokens,
    },
    {
      key: 'cost',
      icon: CurrencyDollarIcon,
      label: t('usage.estimatedCost', { defaultValue: 'Est. AI cost' }),
      gated: true,
      value: (m) => m.estimated_cost_usd ?? 0,
      fmt: (n) => `$${nf.format(n)}`,
    },
  ]
  const visible = metrics.filter((m) => !m.gated || showAi)
  const active = visible.find((m) => m.key === metric) || visible[0]

  const statTotal = (key: MetricKey): string => {
    switch (key) {
      case 'pages':
        return nf.format(totals.pages_processed)
      case 'docs':
        return nf.format(totals.documents_ingested)
      case 'actions':
        return nf.format(totals.ai_actions ?? 0)
      case 'tokens':
        return fmtTokens(totalTokens)
      case 'cost':
        return `$${nf.format(totals.estimated_cost_usd ?? 0)}`
    }
  }

  const statSub = (key: MetricKey): string | undefined => {
    switch (key) {
      case 'pages':
        return t('usage.thisMonthCount', {
          defaultValue: '{{count}} this month',
          count: currentMonth?.pages_processed ?? 0,
        })
      case 'docs':
        return t('usage.thisMonthCount', {
          defaultValue: '{{count}} this month',
          count: currentMonth?.documents_ingested ?? 0,
        })
      case 'tokens':
        return t('usage.tokensSplit', {
          defaultValue: '{{prompt}} in · {{completion}} out',
          prompt: fmtTokens(totals.tokens_prompt),
          completion: fmtTokens(totals.tokens_completion),
        })
      case 'cost':
        return t('usage.estimatedCostNote', { defaultValue: 'Estimate at list prices' })
      default:
        return undefined
    }
  }

  const monthLabel = (m: UsageMonth): string => {
    const d = new Date(`${m.month}-01T00:00:00`)
    return Number.isNaN(d.getTime())
      ? m.month
      : d.toLocaleDateString(i18n.language, { month: 'short' })
  }

  const columns: TableColumn<UsageMonth>[] = [
    {
      key: 'month',
      header: t('usage.month', { defaultValue: 'Month' }),
      sortable: true,
      sortValue: (m) => m.month,
      render: (m) => <span className="mono" style={{ fontWeight: 500 }}>{m.month}</span>,
    },
    {
      key: 'pages',
      header: t('usage.pagesProcessed', { defaultValue: 'Pages processed' }),
      align: 'right',
      sortable: true,
      sortValue: (m) => m.pages_processed,
      render: (m) => <span className="num muted">{nf.format(m.pages_processed)}</span>,
    },
    {
      key: 'docs',
      header: t('usage.documentsIngested', { defaultValue: 'Documents ingested' }),
      align: 'right',
      sortable: true,
      sortValue: (m) => m.documents_ingested,
      render: (m) => <span className="num muted">{nf.format(m.documents_ingested)}</span>,
    },
    ...(showAi
      ? ([
          {
            key: 'actions',
            header: t('usage.aiActions', { defaultValue: 'AI actions' }),
            align: 'right',
            sortable: true,
            sortValue: (m) => m.ai_actions ?? 0,
            render: (m) => <span className="num muted">{nf.format(m.ai_actions ?? 0)}</span>,
          },
          {
            key: 'tokensIn',
            header: t('usage.tokensIn', { defaultValue: 'Tokens in' }),
            align: 'right',
            sortable: true,
            sortValue: (m) => (m.tokens_prompt ?? 0) + (m.tokens_embedding ?? 0),
            render: (m) => (
              <span className="num muted">{fmtTokens((m.tokens_prompt ?? 0) + (m.tokens_embedding ?? 0))}</span>
            ),
          },
          {
            key: 'tokensOut',
            header: t('usage.tokensOut', { defaultValue: 'Tokens out' }),
            align: 'right',
            sortable: true,
            sortValue: (m) => m.tokens_completion ?? 0,
            render: (m) => <span className="num muted">{fmtTokens(m.tokens_completion)}</span>,
          },
          {
            key: 'cost',
            header: t('usage.estimatedCost', { defaultValue: 'Est. AI cost' }),
            align: 'right',
            sortable: true,
            sortValue: (m) => m.estimated_cost_usd ?? 0,
            render: (m) => <span className="num muted">${nf.format(m.estimated_cost_usd ?? 0)}</span>,
          },
        ] as TableColumn<UsageMonth>[])
      : []),
  ]

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>
          {t('usage.title', { defaultValue: 'Usage' })}
        </h1>
        <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>
          {t('usage.subtitle', { defaultValue: 'Processing volume for the last 6 months' })}
        </p>
      </div>

      {/* Visibility banner — mirrors the API's can_view_ai_usage gate */}
      {showAi ? (
        <div className="banner banner-p">
          <ShieldCheckIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
          <span>
            {t('usage.aiVisibleBanner', {
              defaultValue:
                'You see token consumption and estimated cost because you are a tenant admin. The API enforces this too, not just the UI.',
            })}
          </span>
        </div>
      ) : (
        <div className="banner banner-in">
          <LockClosedIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
          <span>
            {t('usage.aiGatedBanner', {
              defaultValue:
                'Pages and documents are visible to every role. Token consumption, AI actions and estimated cost are visible to tenant admins only, enforced by the API.',
            })}
          </span>
        </div>
      )}

      {/* Metric stat cards — click to chart */}
      <div className={`grid grid-cols-1 gap-3 sm:grid-cols-2 ${showAi ? 'lg:grid-cols-5' : 'lg:grid-cols-2'}`}>
        {visible.map((m) => (
          <Stat
            key={m.key}
            icon={m.icon}
            label={m.label}
            value={statTotal(m.key)}
            sub={statSub(m.key)}
            active={active.key === m.key}
            onClick={() => setMetric(m.key)}
          />
        ))}
      </div>

      {/* Monthly trend for the selected metric */}
      <div className="card">
        <div className="row" style={{ padding: '13px 16px', borderBottom: '1px solid var(--b)' }}>
          <b style={{ fontSize: 'var(--fs-lg)' }}>
            {t('usage.monthlyTrend', {
              defaultValue: '{{metric}} — monthly trend',
              metric: active.label,
            })}
          </b>
          <span className="grow" />
          {months.length > 0 && (
            <span className="faint mono" style={{ fontSize: 'var(--fs-sm)' }}>
              {months[0].month} – {months[months.length - 1].month}
            </span>
          )}
        </div>
        <div className="card-p">
          {months.length === 0 ? (
            <EmptyState
              icon={ChartBarIcon}
              title={t('usage.noDataTitle', { defaultValue: 'No usage recorded yet' })}
              body={t('usage.noDataBody', {
                defaultValue: 'Metering starts with the first document processed for this tenant.',
              })}
            />
          ) : (
            <TrendBars months={months} value={active.value} fmt={active.fmt} monthLabel={monthLabel} />
          )}
        </div>
      </div>

      {/* Raw monthly numbers, latest first */}
      <Table
        columns={columns}
        rows={[...months].reverse()}
        rowKey={(m) => m.month}
        minWidth={showAi ? 780 : 520}
        empty={
          <EmptyState
            icon={ChartBarIcon}
            title={t('usage.noDataTitle', { defaultValue: 'No usage recorded yet' })}
          />
        }
      />
    </div>
  )
}
