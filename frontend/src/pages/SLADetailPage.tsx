/* SLA detail — Direction B redesign.
   Back link + header with mono id, severity/active Pills and metric Tag →
   Stat row (compliance, breaches, trend) → target card → measurements Table
   with data-source note → AI-extracted source card. Recording a measurement
   now happens in a Drawer; query, mutation and validation are unchanged. */
import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  ArrowTrendingUpIcon,
  BoltIcon,
  ChartBarIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  SignalIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import { getSLADetail } from '@/lib/api/compliance'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { Button, Pill, Tag, AiTag, Field, Drawer, EmptyState, Stat, Table, useToast } from '@/components/ui'
import type { PillTone, TableColumn } from '@/components/ui'

const SEVERITY_TONE: Record<string, PillTone> = {
  critical: 'da',
  high: 'wa',
  medium: 'wa',
  low: 'n',
}

type Performance = NonNullable<
  Awaited<ReturnType<typeof getSLADetail>>['recent_performances']
>[number]

export default function SLADetailPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const { toast } = useToast()
  const canRecord = ['super_admin', 'admin', 'legal', 'procurement', 'bu_head'].includes(user?.role || '')

  const [showDrawer, setShowDrawer] = useState(false)
  const [actualValue, setActualValue] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)

  const { data: sla, isLoading } = useQuery({
    queryKey: ['sla-detail', id],
    queryFn: () => getSLADetail(id!),
    enabled: !!id,
  })

  const recordMutation = useMutation({
    mutationFn: ({ actual, note }: { actual: number; note?: string }) =>
      api.logSLAPerformance(sla!.contract_id, id!, { actual_value: actual, notes: note }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sla-detail', id] })
      setShowDrawer(false); setActualValue(''); setNotes(''); setError(null)
      toast({ text: t('sla.recordedToast', { defaultValue: 'Measurement recorded.' }) })
    },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : t('sla.recordFailed', { defaultValue: 'Could not record the measurement.' })),
  })

  const submit = () => {
    const val = Number(actualValue)
    if (actualValue.trim() === '' || Number.isNaN(val)) {
      setError(t('sla.recordInvalid', { defaultValue: 'Enter a numeric value.' }))
      return
    }
    setError(null)
    recordMutation.mutate({ actual: val, note: notes.trim() || undefined })
  }

  if (isLoading) {
    return (
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }
  if (!sla) {
    return (
      <div className="col" style={{ alignItems: 'center', gap: 8, padding: '48px 0' }}>
        <p className="muted">{t('sla.notFound', { defaultValue: 'SLA not found.' })}</p>
        <Link to="/post-signing?tab=slas">{t('common.back', { defaultValue: 'Back' })}</Link>
      </div>
    )
  }

  const rate = sla.current_compliance_rate ?? sla.compliance_rate ?? null
  const perfs = sla.recent_performances || []
  const targetStr = `${sla.target_operator || '≥'} ${sla.target_value}${sla.metric_unit === 'percentage' ? '%' : ''}`
  const breaches = sla.consecutive_breaches ?? 0

  const columns: TableColumn<Performance>[] = [
    {
      key: 'measured_at',
      header: t('sla.date', { defaultValue: 'Date' }),
      sortable: true,
      nowrap: true,
      sortValue: (p) => p.measured_at,
      render: (p) => <span className="muted num">{new Date(p.measured_at).toLocaleDateString()}</span>,
    },
    {
      key: 'actual_value',
      header: t('sla.actual', { defaultValue: 'Actual' }),
      sortable: true,
      sortValue: (p) => p.actual_value,
      render: (p) => <span className="num" style={{ fontWeight: 600 }}>{p.actual_value}</span>,
    },
    {
      key: 'target',
      header: t('sla.targetValue', { defaultValue: 'Target' }),
      render: () => <span className="muted num">{targetStr}</span>,
    },
    {
      key: 'result',
      header: t('sla.result', { defaultValue: 'Result' }),
      width: 110,
      sortable: true,
      sortValue: (p) => (p.is_compliant ? 1 : 0),
      render: (p) =>
        p.is_compliant ? (
          <Pill tone="ok">{t('sla.met', { defaultValue: 'Met' })}</Pill>
        ) : (
          <Pill tone="da">{t('sla.breach', { defaultValue: 'Breach' })}</Pill>
        ),
    },
    {
      key: 'deviation',
      header: t('sla.deviation', { defaultValue: 'Deviation' }),
      align: 'right',
      nowrap: true,
      sortable: true,
      sortValue: (p) => p.deviation_percentage,
      render: (p) => (
        <span
          className="num"
          style={{ color: (p.deviation_percentage ?? 0) < 0 ? 'var(--da)' : 'var(--m)' }}
        >
          {p.deviation_percentage != null
            ? `${p.deviation_percentage > 0 ? '+' : ''}${p.deviation_percentage.toFixed(1)}%`
            : '—'}
        </span>
      ),
    },
  ]

  return (
    <div className="col" style={{ gap: 18, maxWidth: 960 }}>
      {/* Back link + header */}
      <div>
        <Link
          to="/post-signing?tab=slas"
          className="row"
          style={{ gap: 4, width: 'fit-content', fontSize: 'var(--fs-sm)', color: 'var(--m)' }}
        >
          <ArrowLeftIcon style={{ width: 14, height: 14 }} aria-hidden />
          {t('common.back', { defaultValue: 'Back' })}
        </Link>
        <div className="row" style={{ gap: 12, alignItems: 'flex-start', marginTop: 10 }}>
          <div className="grow" style={{ minWidth: 0 }}>
            <div className="row" style={{ gap: 7, marginBottom: 5, flexWrap: 'wrap' }}>
              <span className="mono faint" style={{ fontSize: 'var(--fs-xs)' }}>{sla.id.slice(0, 8)}</span>
              <Pill tone={SEVERITY_TONE[sla.severity] || 'n'}>
                {t(`risk.${sla.severity}`, { defaultValue: sla.severity })}
              </Pill>
              {sla.is_active !== false && (
                <Pill tone="ok">{t('sla.active', { defaultValue: 'Active' })}</Pill>
              )}
              <Tag>{(sla.metric_type || '').replace(/_/g, ' ')}</Tag>
              {sla.has_penalty && (
                <Tag icon={BoltIcon}>{t('sla.penalty', { defaultValue: 'Penalty' })}</Tag>
              )}
            </div>
            <h1 style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600, letterSpacing: '-.4px', lineHeight: 1.25 }}>
              {sla.sla_name}
            </h1>
            <div className="row muted" style={{ gap: 8, marginTop: 6, fontSize: 'var(--fs-md)', flexWrap: 'wrap' }}>
              {sla.counterparty && (
                <>
                  <span>{sla.counterparty}</span>
                  <span className="faint">·</span>
                </>
              )}
              <Link to={`/contracts/${sla.contract_id}?tab=slas`}>
                {sla.contract_filename || t('sla.contract', { defaultValue: 'Contract' })}
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Compliance stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Stat
          icon={SignalIcon}
          label={t('sla.compliance', { defaultValue: 'Compliance' })}
          value={rate != null ? `${rate.toFixed(1)}%` : '—'}
          sub={rate == null ? t('sla.noData', { defaultValue: '— (no data yet)' }) : undefined}
        />
        <Stat
          icon={ExclamationTriangleIcon}
          label={t('sla.breaches', { defaultValue: 'Breaches' })}
          value={breaches}
          sub={breaches > 0 ? t('sla.consecutive', { defaultValue: 'consecutive' }) : undefined}
          subTone={breaches > 0 ? 'var(--da)' : undefined}
        />
        <Stat
          icon={ArrowTrendingUpIcon}
          label={t('sla.trend', { defaultValue: 'Trend' })}
          value={
            sla.compliance_trend
              ? t(`sla.trend_${sla.compliance_trend}`, { defaultValue: sla.compliance_trend })
              : '—'
          }
        />
      </div>

      {/* Target */}
      <div className="card card-p">
        <div className="sec-t" style={{ marginBottom: 10 }}>{t('sla.target', { defaultValue: 'Target' })}</div>
        <div className="col" style={{ gap: 8, fontSize: 'var(--fs-md)' }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="muted">{t('sla.metric', { defaultValue: 'Metric' })}</span>
            <span className="capitalize" style={{ fontWeight: 500 }}>{(sla.metric_type || '').replace(/_/g, ' ')}</span>
          </div>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="muted">{t('sla.targetValue', { defaultValue: 'Target' })}</span>
            <span className="num" style={{ fontWeight: 600 }}>{targetStr}</span>
          </div>
          {sla.warning_threshold != null && (
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <span className="muted">{t('sla.warning', { defaultValue: 'Warning' })}</span>
              <span className="num" style={{ fontWeight: 500 }}>{String(sla.warning_threshold)}</span>
            </div>
          )}
          {sla.measurement_period && (
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <span className="muted">{t('sla.period', { defaultValue: 'Period' })}</span>
              <span className="capitalize" style={{ fontWeight: 500 }}>{sla.measurement_period}</span>
            </div>
          )}
          {sla.has_penalty && (
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <span className="muted">{t('sla.penalty', { defaultValue: 'Penalty' })}</span>
              <span className="num" style={{ fontWeight: 500 }}>
                {[
                  sla.penalty_value != null ? String(sla.penalty_value) : null,
                  sla.max_penalty_cap != null
                    ? `${t('sla.cap', { defaultValue: 'cap' })} ${sla.max_penalty_cap}`
                    : null,
                ]
                  .filter(Boolean)
                  .join(' · ') || t('sla.yes', { defaultValue: 'Yes' })}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Measurements */}
      <div className="col" style={{ gap: 10 }}>
        <div className="row" style={{ gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div className="grow" style={{ minWidth: 200 }}>
            <div className="sec-t">{t('sla.measurements', { defaultValue: 'Measurements' })}</div>
            {sla.data_source === 'servicenow' ? (
              <div className="row faint" style={{ gap: 4, marginTop: 3, fontSize: 'var(--fs-sm)' }}>
                <BoltIcon style={{ width: 12, height: 12, color: 'var(--p)' }} aria-hidden />
                <span>
                  {t('sla.sourceServiceNow', { defaultValue: 'Data source: ServiceNow' })}
                  {sla.snow_sla_name ? ` · ${sla.snow_sla_name}` : ''}
                  {sla.snow_last_synced
                    ? ` · ${t('sla.lastSynced', { defaultValue: 'synced' })} ${new Date(sla.snow_last_synced).toLocaleString()}`
                    : ''}
                </span>
              </div>
            ) : (
              <div className="faint" style={{ marginTop: 3, fontSize: 'var(--fs-sm)' }}>
                {t('sla.sourceManual', { defaultValue: 'Data source: manual entry' })}
              </div>
            )}
          </div>
          {canRecord && (
            <Button
              variant={sla.data_source === 'servicenow' ? 'secondary' : 'primary'}
              icon={ChartBarIcon}
              onClick={() => { setActualValue(''); setNotes(''); setError(null); setShowDrawer(true) }}
            >
              {sla.data_source === 'servicenow'
                ? t('sla.addOverride', { defaultValue: 'Add manual override' })
                : t('sla.recordMeasurement', { defaultValue: 'Record measurement' })}
            </Button>
          )}
        </div>
        <Table
          columns={columns}
          rows={perfs}
          rowKey={(p) => p.id}
          minWidth={560}
          empty={
            <EmptyState
              icon={DocumentTextIcon}
              title={t('sla.noMeasurements', { defaultValue: 'No measurements recorded yet.' })}
              body={t('sla.noMeasurementsHint', {
                defaultValue: 'Record one to start tracking compliance against the target.',
              })}
            />
          }
        />
      </div>

      {/* Source from contract — AI-extracted */}
      {sla.source_text && (
        <div className="card card-p">
          <div className="row" style={{ gap: 8, marginBottom: 10 }}>
            <span className="sec-t">{t('sla.sourceFromContract', { defaultValue: 'Source from contract' })}</span>
            <AiTag />
          </div>
          <p
            className="muted"
            style={{ fontSize: 'var(--fs-md)', lineHeight: 1.6, paddingLeft: 12, borderLeft: '2px solid var(--b)' }}
          >
            "{sla.source_text}"
          </p>
        </div>
      )}

      {/* Record measurement drawer */}
      <Drawer
        open={showDrawer}
        title={t('sla.recordMeasurementTitle', { defaultValue: 'Record SLA measurement' })}
        sub={sla.sla_name}
        onClose={() => setShowDrawer(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setShowDrawer(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="primary"
              className="grow"
              disabled={recordMutation.isPending || actualValue.trim() === ''}
              onClick={submit}
            >
              {recordMutation.isPending
                ? t('common.saving')
                : t('sla.recordMeasurement', { defaultValue: 'Record measurement' })}
            </Button>
          </>
        }
      >
        <div className="col" style={{ gap: 14 }}>
          <div className="banner banner-p">
            <span className="grow">{t('sla.targetValue', { defaultValue: 'Target' })}</span>
            <b className="num">{targetStr}</b>
          </div>
          <Field
            label={t('sla.actualValue', { defaultValue: 'Actual value' })}
            type="number"
            value={actualValue}
            onChange={(e) => setActualValue(e.target.value)}
            autoFocus
          />
          <div>
            <label className="lbl">{t('sla.notes', { defaultValue: 'Notes' })}</label>
            <div className="inp" style={{ height: 'auto', padding: 10, alignItems: 'flex-start' }}>
              <textarea
                rows={2}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder={t('sla.notesPlaceholder', { defaultValue: 'Optional — period, source…' })}
                style={{ resize: 'vertical', lineHeight: 1.55 }}
              />
            </div>
          </div>
          {error && (
            <div className="banner banner-da">
              <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
              <span className="grow">{error}</span>
            </div>
          )}
        </div>
      </Drawer>
    </div>
  )
}
