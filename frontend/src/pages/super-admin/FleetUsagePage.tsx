/* Fleet usage (super admin) — metering phase 3.
   Current-month metered usage for every tenant (pages, documents, tokens,
   AI actions, estimated cost), with utilization chips where monthly soft
   limits are configured. Row click opens a drawer to edit that tenant's
   limits — limits drive the 80%/100% tenant-admin alerts, not enforcement
   (that's phase 4). */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  getUsageByTenant,
  setUsageLimits,
  type TenantUsageRow,
} from '@/lib/api/admin'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { Button, Drawer, EmptyState, Field, Pill, Table } from '@/components/ui'
import type { TableColumn } from '@/components/ui'
import { ChartBarIcon } from '@heroicons/react/24/outline'
import { useToast } from '@/components/ui/Toast'

const nf = new Intl.NumberFormat()

function fmtTokens(n?: number): string {
  if (n == null) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return nf.format(n)
}

function totalTokens(r: TenantUsageRow): number {
  return (r.tokens_prompt ?? 0) + (r.tokens_completion ?? 0) + (r.tokens_embedding ?? 0)
}

function maxPct(r: TenantUsageRow): number {
  const pcts = Object.values(r.limits ?? {}).map((l) => l.pct)
  return pcts.length ? Math.max(...pcts) : -1
}

function UtilizationPill({ row }: { row: TenantUsageRow }) {
  const { t } = useTranslation()
  const pct = maxPct(row)
  if (pct < 0) {
    return <span className="faint">{t('fleetUsage.noLimits', { defaultValue: 'No limits' })}</span>
  }
  const tone = pct >= 100 ? 'da' : pct >= 80 ? 'wa' : 'ok'
  return <Pill tone={tone}>{pct.toFixed(0)}%</Pill>
}

interface LimitsForm {
  monthly_pages: string
  monthly_ai_actions: string
  monthly_cost_usd: string
}

export default function FleetUsagePage() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<TenantUsageRow | null>(null)
  const [form, setForm] = useState<LimitsForm>({ monthly_pages: '', monthly_ai_actions: '', monthly_cost_usd: '' })

  const { data, isLoading } = useQuery({
    queryKey: ['usage-by-tenant'],
    queryFn: getUsageByTenant,
  })

  const saveMutation = useMutation({
    mutationFn: ({ tenantId, limits }: { tenantId: string; limits: Record<string, number | null> }) =>
      setUsageLimits(tenantId, limits),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['usage-by-tenant'] })
      setEditing(null)
      toast({ text: t('fleetUsage.limitsSaved', { defaultValue: 'Usage limits saved' }) })
    },
  })

  const openEditor = (row: TenantUsageRow) => {
    if (!row.tenant_id) return // platform bucket has no tenant to configure
    setEditing(row)
    setForm({
      monthly_pages: row.limits?.monthly_pages?.limit?.toString() ?? '',
      monthly_ai_actions: row.limits?.monthly_ai_actions?.limit?.toString() ?? '',
      monthly_cost_usd: row.limits?.monthly_cost_usd?.limit?.toString() ?? '',
    })
  }

  const save = () => {
    if (!editing?.tenant_id) return
    saveMutation.mutate({
      tenantId: editing.tenant_id,
      limits: {
        monthly_pages: form.monthly_pages ? Number(form.monthly_pages) : null,
        monthly_ai_actions: form.monthly_ai_actions ? Number(form.monthly_ai_actions) : null,
        monthly_cost_usd: form.monthly_cost_usd ? Number(form.monthly_cost_usd) : null,
      },
    })
  }

  const columns: TableColumn<TenantUsageRow>[] = [
    {
      key: 'tenant_name',
      header: t('fleetUsage.tenant', { defaultValue: 'Tenant' }),
      sortable: true,
      render: (r) => <span style={{ fontWeight: 500 }}>{r.tenant_name}</span>,
    },
    {
      key: 'pages_processed',
      header: t('fleetUsage.pages', { defaultValue: 'Pages' }),
      align: 'right', sortable: true,
      render: (r) => <span className="num">{nf.format(r.pages_processed)}</span>,
    },
    {
      key: 'documents_ingested',
      header: t('fleetUsage.documents', { defaultValue: 'Documents' }),
      align: 'right', sortable: true,
      render: (r) => <span className="num">{nf.format(r.documents_ingested)}</span>,
    },
    {
      key: 'tokens',
      header: t('fleetUsage.tokens', { defaultValue: 'Tokens' }),
      align: 'right', sortable: true,
      sortValue: totalTokens,
      render: (r) => <span className="num">{fmtTokens(totalTokens(r))}</span>,
    },
    {
      key: 'ai_actions',
      header: t('fleetUsage.aiActions', { defaultValue: 'AI actions' }),
      align: 'right', sortable: true,
      render: (r) => <span className="num">{nf.format(r.ai_actions ?? 0)}</span>,
    },
    {
      key: 'estimated_cost_usd',
      header: t('fleetUsage.estCost', { defaultValue: 'Est. cost' }),
      align: 'right', sortable: true,
      render: (r) => <span className="num">${(r.estimated_cost_usd ?? 0).toFixed(2)}</span>,
    },
    {
      key: 'utilization',
      header: t('fleetUsage.utilization', { defaultValue: 'Limit use' }),
      align: 'right', sortable: true,
      sortValue: maxPct,
      render: (r) => <UtilizationPill row={r} />,
    },
  ]

  if (isLoading) {
    return <div className="row" style={{ justifyContent: 'center', height: 256 }}><LoadingSpinner size="lg" /></div>
  }

  return (
    <div className="col" style={{ gap: 16 }}>
      <div className="row" style={{ gap: 8 }}>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600 }}>
            {t('fleetUsage.title', { defaultValue: 'Fleet usage' })}
          </h1>
          <div className="muted" style={{ fontSize: 'var(--fs-sm)' }}>
            {t('fleetUsage.subtitle', {
              month: data?.month ?? '',
              defaultValue: 'Metered usage per tenant for {{month}} — click a tenant to set monthly limits',
            })}
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <Table
          columns={columns}
          rows={data?.items ?? []}
          rowKey={(r) => r.tenant_id ?? 'platform'}
          onRowClick={openEditor}
          empty={
            <EmptyState
              icon={ChartBarIcon}
              title={t('fleetUsage.empty', { defaultValue: 'No usage recorded this month' })}
            />
          }
        />
      </div>

      <Drawer
        open={editing != null}
        title={t('fleetUsage.editLimits', { name: editing?.tenant_name ?? '', defaultValue: 'Limits — {{name}}' })}
        onClose={() => setEditing(null)}
        width={400}
        footer={
          <>
            <span className="grow" />
            <Button variant="ghost" onClick={() => setEditing(null)}>{t('common.cancel')}</Button>
            <Button variant="primary" disabled={saveMutation.isPending} onClick={save}>
              {t('common.save', { defaultValue: 'Save' })}
            </Button>
          </>
        }
      >
        <div className="col" style={{ gap: 14 }}>
          <div className="muted" style={{ fontSize: 'var(--fs-sm)' }}>
            {t('fleetUsage.limitsHint', {
              defaultValue:
                'Soft limits: tenant admins get an alert at 80% and 100%. Usage is never blocked. Leave a field empty to remove the limit.',
            })}
          </div>
          <Field
            label={t('fleetUsage.monthlyPages', { defaultValue: 'Monthly pages' })}
            type="number"
            min={0}
            value={form.monthly_pages}
            onChange={(e) => setForm({ ...form, monthly_pages: e.target.value })}
          />
          <Field
            label={t('fleetUsage.monthlyAiActions', { defaultValue: 'Monthly AI actions' })}
            type="number"
            min={0}
            value={form.monthly_ai_actions}
            onChange={(e) => setForm({ ...form, monthly_ai_actions: e.target.value })}
          />
          <Field
            label={t('fleetUsage.monthlyCost', { defaultValue: 'Monthly estimated cost (USD)' })}
            type="number"
            min={0}
            value={form.monthly_cost_usd}
            onChange={(e) => setForm({ ...form, monthly_cost_usd: e.target.value })}
          />
        </div>
      </Drawer>
    </div>
  )
}
