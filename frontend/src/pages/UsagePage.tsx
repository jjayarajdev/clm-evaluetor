// Usage meters page. Everyone with the 'usage' permission sees pages/documents;
// the AI section (tokens, actions, estimated cost) renders only when the API
// says so (can_view_ai_usage — tenant admins). Visibility is API-enforced;
// this page just adapts to the fields it receives.
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  BoltIcon,
  CircleStackIcon,
  CurrencyDollarIcon,
  DocumentDuplicateIcon,
  DocumentTextIcon,
} from '@heroicons/react/24/outline'
import { getUsageSummary, type UsageMonth } from '@/lib/api/admin'
import LoadingSpinner from '@/components/ui/LoadingSpinner'

const nf = new Intl.NumberFormat()

function fmtTokens(n?: number): string {
  if (n == null) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return nf.format(n)
}

function MetricCard({
  icon: Icon,
  label,
  value,
  sub,
}: {
  icon: typeof DocumentTextIcon
  label: string
  value: string
  sub?: string
}) {
  return (
    <div className="card p-5">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-50">
          <Icon className="h-5 w-5 text-violet-600" />
        </div>
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="text-xl font-semibold text-gray-900">{value}</p>
          {sub && <p className="text-xs text-gray-400">{sub}</p>}
        </div>
      </div>
    </div>
  )
}

export default function UsagePage() {
  const { t } = useTranslation()
  const { data, isLoading } = useQuery({
    queryKey: ['usage-summary'],
    queryFn: () => getUsageSummary(6),
  })

  if (isLoading || !data) return <LoadingSpinner size="lg" />

  const { totals, months, can_view_ai_usage: showAi } = data
  const currentMonth = months[months.length - 1]

  const totalTokens =
    (totals.tokens_prompt ?? 0) + (totals.tokens_completion ?? 0) + (totals.tokens_embedding ?? 0)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          {t('usage.title', { defaultValue: 'Usage' })}
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          {t('usage.subtitle', { defaultValue: 'Processing volume for the last 6 months' })}
        </p>
      </div>

      <div className={`grid grid-cols-1 gap-4 sm:grid-cols-2 ${showAi ? 'lg:grid-cols-5' : ''}`}>
        <MetricCard
          icon={DocumentTextIcon}
          label={t('usage.pagesProcessed', { defaultValue: 'Pages processed' })}
          value={nf.format(totals.pages_processed)}
          sub={t('usage.thisMonthCount', {
            defaultValue: '{{count}} this month',
            count: currentMonth?.pages_processed ?? 0,
          })}
        />
        <MetricCard
          icon={DocumentDuplicateIcon}
          label={t('usage.documentsIngested', { defaultValue: 'Documents ingested' })}
          value={nf.format(totals.documents_ingested)}
          sub={t('usage.thisMonthCount', {
            defaultValue: '{{count}} this month',
            count: currentMonth?.documents_ingested ?? 0,
          })}
        />
        {showAi && (
          <>
            <MetricCard
              icon={BoltIcon}
              label={t('usage.aiActions', { defaultValue: 'AI actions' })}
              value={nf.format(totals.ai_actions ?? 0)}
            />
            <MetricCard
              icon={CircleStackIcon}
              label={t('usage.tokens', { defaultValue: 'Tokens' })}
              value={fmtTokens(totalTokens)}
              sub={t('usage.tokensSplit', {
                defaultValue: '{{prompt}} in · {{completion}} out',
                prompt: fmtTokens(totals.tokens_prompt),
                completion: fmtTokens(totals.tokens_completion),
              })}
            />
            <MetricCard
              icon={CurrencyDollarIcon}
              label={t('usage.estimatedCost', { defaultValue: 'Est. AI cost' })}
              value={`$${nf.format(totals.estimated_cost_usd ?? 0)}`}
              sub={t('usage.estimatedCostNote', { defaultValue: 'Estimate at list prices' })}
            />
          </>
        )}
      </div>

      <div className="card overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <Th>{t('usage.month', { defaultValue: 'Month' })}</Th>
              <Th right>{t('usage.pagesProcessed', { defaultValue: 'Pages processed' })}</Th>
              <Th right>{t('usage.documentsIngested', { defaultValue: 'Documents ingested' })}</Th>
              {showAi && (
                <>
                  <Th right>{t('usage.aiActions', { defaultValue: 'AI actions' })}</Th>
                  <Th right>{t('usage.tokensIn', { defaultValue: 'Tokens in' })}</Th>
                  <Th right>{t('usage.tokensOut', { defaultValue: 'Tokens out' })}</Th>
                  <Th right>{t('usage.estimatedCost', { defaultValue: 'Est. AI cost' })}</Th>
                </>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {[...months].reverse().map((m: UsageMonth) => (
              <tr key={m.month} className="hover:bg-gray-50">
                <td className="px-4 py-2.5 text-sm font-medium text-gray-900">{m.month}</td>
                <Td>{nf.format(m.pages_processed)}</Td>
                <Td>{nf.format(m.documents_ingested)}</Td>
                {showAi && (
                  <>
                    <Td>{nf.format(m.ai_actions ?? 0)}</Td>
                    <Td>{fmtTokens((m.tokens_prompt ?? 0) + (m.tokens_embedding ?? 0))}</Td>
                    <Td>{fmtTokens(m.tokens_completion)}</Td>
                    <Td>${nf.format(m.estimated_cost_usd ?? 0)}</Td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Th({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return (
    <th
      className={`px-4 py-3 text-xs font-semibold uppercase tracking-wide text-gray-500 ${
        right ? 'text-right' : 'text-left'
      }`}
    >
      {children}
    </th>
  )
}

function Td({ children }: { children: React.ReactNode }) {
  return <td className="px-4 py-2.5 text-right text-sm text-gray-600">{children}</td>
}
