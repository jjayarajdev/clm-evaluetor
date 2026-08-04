/* Vendor scorecards — Direction B redesign.
   Header + party-type filter → summary stats → scorecard table (avatar rows,
   score/compliance Bars, risk Pills) → detail Drawer. Data fetching, role-based
   default filter, server-side sorting and the super-admin tenant grouping are
   unchanged from the pre-redesign page. A manual .tbl table is used (instead of
   the Table primitive) because sorting is server-driven and the super-admin
   view interleaves tenant group rows. */
import { useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import {
  BuildingOfficeIcon,
  ChartBarIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ExclamationTriangleIcon,
  TruckIcon,
  UserGroupIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { Avatar, Bar, Drawer, EmptyState, Pill, Select, Stat, Tag } from '@/components/ui'
import type { PillTone } from '@/components/ui'
import { cn } from '@/lib/utils'
import type { VendorListItem, CounterpartyType } from '@/types/postsigning'

type PartyFilter = 'all' | 'vendor' | 'client'

// ── Helpers ──────────────────────────────────────────────────────

/** Performance banding thresholds, from the tenant/BU-resolved scoring config
    on GET /api/vendors (fallback to backend defaults on older payloads). */
interface ScoreBands { low: number; medium: number }
const DEFAULT_BANDS: ScoreBands = { low: 80, medium: 60 }

/** Live-page performance banding: ≥ low ok, ≥ medium warn, else danger. */
function scoreTone(score: number, bands: ScoreBands): string {
  return score >= bands.low ? 'var(--ok)' : score >= bands.medium ? 'var(--wa)' : 'var(--da)'
}

const RISK_TONE: Record<string, PillTone> = { low: 'ok', medium: 'wa', high: 'da', critical: 'da' }

function RiskPill({ level }: { level: string }) {
  const { t } = useTranslation()
  if (level === 'unrated') return <Pill tone="n">{t('vendors.notRated')}</Pill>
  return <Pill tone={RISK_TONE[level] || 'n'}>{t(`risk.${level}`, { defaultValue: level })}</Pill>
}

function PartyTag({ type }: { type: CounterpartyType }) {
  const { t } = useTranslation()
  if (type === 'vendor') return <Tag icon={TruckIcon}>{t('vendors.vendor')}</Tag>
  if (type === 'client') return <Tag icon={UserGroupIcon}>{t('vendors.client')}</Tag>
  return <Tag>{t('vendors.unknown')}</Tag>
}

/** Score / compliance-rate bar with banded tone and numeric figure. */
function RateBar({ value, okAt, warnAt, suffix = '' }: { value: number | null; okAt: number; warnAt: number; suffix?: string }) {
  const { t } = useTranslation()
  if (value == null) {
    return <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>{t('vendors.notRated')}</span>
  }
  const tone = value >= okAt ? 'var(--ok)' : value >= warnAt ? 'var(--wa)' : 'var(--da)'
  return (
    <span className="row" style={{ gap: 7 }}>
      <Bar value={value} width={56} tone={tone} />
      <span className="mono num" style={{ fontSize: 'var(--fs-sm)', fontWeight: 500, color: tone }}>
        {value.toFixed(1)}{suffix}
      </span>
    </span>
  )
}

// ── Table row ────────────────────────────────────────────────────

function VendorRow({ vendor, onClick, showType, bands }: { vendor: VendorListItem; onClick: () => void; showType: boolean; bands: ScoreBands }) {
  const { t } = useTranslation()
  return (
    <tr className="click" onClick={onClick}>
      <td>
        <span className="row" style={{ gap: 9 }}>
          <Avatar name={vendor.vendor_name} size={26} />
          <span style={{ minWidth: 0 }}>
            <span className="row" style={{ gap: 6 }}>
              <span className="trunc" style={{ fontWeight: 500 }}>{vendor.vendor_name}</span>
              {showType && <PartyTag type={vendor.party_type} />}
            </span>
            <span className="faint" style={{ display: 'block', fontSize: 'var(--fs-sm)', marginTop: 1 }}>
              {t('vendors.contractsCount', { count: vendor.contract_count })}
            </span>
          </span>
        </span>
      </td>
      <td>
        {vendor.performance_score != null ? (
          <span className="row" style={{ gap: 7 }}>
            <Bar value={vendor.performance_score} width={56} tone={scoreTone(vendor.performance_score, bands)} />
            <span className="mono num" style={{ fontSize: 'var(--fs-sm)', fontWeight: 500, color: scoreTone(vendor.performance_score, bands) }}>
              {vendor.performance_score.toFixed(1)}
            </span>
          </span>
        ) : (
          <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>{t('vendors.notRated')}</span>
        )}
      </td>
      <td><RiskPill level={vendor.risk_level} /></td>
      <td className="r num nw" style={{ fontWeight: 500 }}>${vendor.total_exposure.toLocaleString()}</td>
      <td><RateBar value={vendor.obligation_compliance_rate} okAt={80} warnAt={60} suffix="%" /></td>
      <td><RateBar value={vendor.sla_compliance_rate} okAt={90} warnAt={70} suffix="%" /></td>
      <td className="r num">
        {vendor.active_breaches > 0 ? (
          <span style={{ color: 'var(--da)', fontWeight: 600 }}>{vendor.active_breaches}</span>
        ) : (
          <span style={{ color: 'var(--ok)' }}>0</span>
        )}
      </td>
    </tr>
  )
}

// ── Detail drawer ────────────────────────────────────────────────

function BreakdownRow({ label, value, strong }: { label: string; value: number | null; strong?: boolean }) {
  return (
    <div className="row" style={{ gap: 10 }}>
      <span className={strong ? undefined : 'muted'} style={{ fontSize: 'var(--fs-md)', fontWeight: strong ? 600 : undefined }}>
        {label}
      </span>
      <span className="grow" />
      {value != null && <Bar value={value} width={64} tone="var(--p)" />}
      <span className="num" style={{ fontSize: strong ? 'var(--fs-lg)' : 'var(--fs-md)', fontWeight: strong ? 700 : 500, width: 44, textAlign: 'right' }}>
        {value != null ? value.toFixed(1) : '—'}
      </span>
    </div>
  )
}

function MiniStat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ background: 'var(--s2)', borderRadius: 'var(--r-md)', padding: '8px 10px' }}>
      <div className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{label}</div>
      <div className="num" style={{ fontSize: 'var(--fs-lg)', fontWeight: 600, marginTop: 2 }}>{value}</div>
    </div>
  )
}

function VendorDrawer({ vendorName, onClose, bands }: { vendorName: string; onClose: () => void; bands: ScoreBands }) {
  const { t } = useTranslation()
  const { data: vendor, isLoading } = useQuery({
    queryKey: ['vendor-detail', vendorName],
    queryFn: () => api.getVendorPerformance(vendorName),
    enabled: !!vendorName,
  })

  return (
    <Drawer open title={vendorName} onClose={onClose} width={460}>
      {isLoading ? (
        <div className="row" style={{ justifyContent: 'center', padding: 48 }}>
          <LoadingSpinner size="lg" />
        </div>
      ) : !vendor ? (
        <div className="banner banner-da">
          <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
          <span>{t('vendors.loadError')}</span>
        </div>
      ) : (
        <div className="col" style={{ gap: 22 }}>
          {/* Headline score + standing */}
          <div className="row" style={{ gap: 12 }}>
            <span
              className="num"
              style={{
                fontSize: 'var(--fs-3xl)',
                fontWeight: 600,
                letterSpacing: '-1px',
                color: vendor.performance_score != null ? scoreTone(vendor.performance_score, bands) : 'var(--f)',
              }}
            >
              {vendor.performance_score != null ? vendor.performance_score.toFixed(1) : t('vendors.notRated')}
            </span>
            <Pill tone={vendor.is_at_risk ? 'da' : 'ok'}>
              {vendor.is_at_risk ? t('vendors.atRisk') : t('vendors.goodStanding')}
            </Pill>
            <span className="grow" />
            <RiskPill level={vendor.risk_level} />
          </div>
          {vendor.performance_score != null && (
            <Bar value={vendor.performance_score} width="100%" tone={scoreTone(vendor.performance_score, bands)} />
          )}

          {/* Score breakdown */}
          <div className="col" style={{ gap: 9 }}>
            <div className="sec-t">{t('vendors.scoreBreakdown')}</div>
            <BreakdownRow label={t('vendors.obligationComplianceWeight')} value={vendor.score_breakdown.obligation_compliance_score} />
            <BreakdownRow label={t('vendors.slaComplianceWeight')} value={vendor.score_breakdown.sla_compliance_score} />
            <BreakdownRow label={t('vendors.responsivenessWeight')} value={vendor.score_breakdown.responsiveness_score} />
            <BreakdownRow label={t('vendors.issueRateWeight')} value={vendor.score_breakdown.issue_rate_score} />
            <div style={{ borderTop: '1px solid var(--b)', paddingTop: 9 }}>
              <BreakdownRow label={t('vendors.weightedTotal')} value={vendor.score_breakdown.weighted_total} strong />
            </div>
          </div>

          {/* Quick stats */}
          <div className="grid gap-2 grid-cols-3">
            <MiniStat label={t('vendors.contracts')} value={vendor.contracts.total_contracts} />
            <MiniStat label={t('vendors.totalValue')} value={`$${(vendor.contracts.total_value / 1000000).toFixed(1)}M`} />
            <MiniStat label={t('status.active')} value={vendor.contracts.active_contracts} />
          </div>

          {/* Risk factors */}
          {vendor.risk_factors.length > 0 && (
            <div className="col" style={{ gap: 8 }}>
              <div className="sec-t">{t('vendors.riskFactors')}</div>
              <ul className="col" style={{ gap: 7 }}>
                {vendor.risk_factors.map((factor, idx) => (
                  <li key={idx} className="row" style={{ gap: 8, alignItems: 'flex-start', fontSize: 'var(--fs-md)', lineHeight: 1.5 }}>
                    <ExclamationTriangleIcon style={{ width: 15, height: 15, flexShrink: 0, marginTop: 2, color: 'var(--wa)' }} aria-hidden />
                    <span className="muted">{factor}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Recommended actions */}
          {vendor.recommended_actions.length > 0 && (
            <div className="col" style={{ gap: 8 }}>
              <div className="sec-t">{t('vendors.recommendedActions')}</div>
              <ul className="col" style={{ gap: 7 }}>
                {vendor.recommended_actions.map((action, idx) => (
                  <li key={idx} className="row" style={{ gap: 8, alignItems: 'flex-start', fontSize: 'var(--fs-md)', lineHeight: 1.5 }}>
                    <ChartBarIcon style={{ width: 15, height: 15, flexShrink: 0, marginTop: 2, color: 'var(--in)' }} aria-hidden />
                    <span className="muted">{action}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Drawer>
  )
}

// ── Page ─────────────────────────────────────────────────────────

export default function VendorsPage() {
  const { t } = useTranslation()
  const { isProcurement, isLegal, isAdmin, isSuperAdmin } = useAuth()

  // Role-based default filter
  const defaultFilter = useMemo((): PartyFilter => {
    if (isProcurement) return 'vendor'  // Procurement sees vendors by default
    if (isLegal || isAdmin || isSuperAdmin) return 'all'  // Legal/Admin sees all
    return 'all'
  }, [isProcurement, isLegal, isAdmin, isSuperAdmin])

  const [partyFilter, setPartyFilter] = useState<PartyFilter>(defaultFilter)
  const [sortBy, setSortBy] = useState('score')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [selectedVendor, setSelectedVendor] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['vendors', sortBy, sortOrder, partyFilter],
    queryFn: () => api.getVendors({ sort_by: sortBy, sort_order: sortOrder, party_type: partyFilter }),
  })

  // Dynamic page title based on filter
  const pageTitle = partyFilter === 'vendor' ? t('vendors.vendorPerformance') :
                    partyFilter === 'client' ? t('vendors.clientRelationships') :
                    t('vendors.counterpartyPerformance')

  const pageDescription = partyFilter === 'vendor' ? t('vendors.vendorDescription') :
                          partyFilter === 'client' ? t('vendors.clientDescription') :
                          t('vendors.counterpartyDescription')

  const handleSort = (column: string) => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(column)
      setSortOrder('desc')
    }
  }

  if (isLoading) {
    return (
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="banner banner-da">
        <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
        <span>{t('vendors.loadError')}</span>
      </div>
    )
  }

  const showType = partyFilter === 'all'

  // Band scores using the resolved scoring config; at_risk_count is server-computed.
  const bands: ScoreBands = {
    low: data.scoring?.low_threshold ?? DEFAULT_BANDS.low,
    medium: data.scoring?.medium_threshold ?? DEFAULT_BANDS.medium,
  }

  /** Server-sorted column header with direction chevron. */
  const SortableTh = ({ column, label, width, align }: { column: string; label: string; width?: number; align?: 'r' }) => (
    <th
      className={cn('sortable', align === 'r' && 'r')}
      style={width ? { width } : undefined}
      onClick={() => handleSort(column)}
      aria-sort={sortBy === column ? (sortOrder === 'asc' ? 'ascending' : 'descending') : undefined}
    >
      <span className="row" style={{ gap: 4, display: 'inline-flex' }}>
        {label}
        {sortBy === column &&
          (sortOrder === 'asc' ? (
            <ChevronUpIcon style={{ width: 12, height: 12 }} aria-hidden />
          ) : (
            <ChevronDownIcon style={{ width: 12, height: 12 }} aria-hidden />
          ))}
      </span>
    </th>
  )

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header + party-type filter */}
      <div className="row" style={{ alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>{pageTitle}</h1>
          <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>{pageDescription}</p>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <span className="muted" style={{ fontSize: 'var(--fs-sm)', fontWeight: 500 }}>{t('vendors.show')}</span>
          <Select
            aria-label={t('vendors.show')}
            value={partyFilter}
            onChange={(e) => setPartyFilter(e.target.value as PartyFilter)}
            containerStyle={{ width: 190 }}
            options={[
              { value: 'all', label: t('vendors.allCounterparties') },
              { value: 'vendor', label: t('vendors.vendorsOnly') },
              { value: 'client', label: t('vendors.clientsOnly') },
            ]}
          />
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        <Stat
          icon={BuildingOfficeIcon}
          label={partyFilter === 'vendor' ? t('vendors.totalVendors') :
                 partyFilter === 'client' ? t('vendors.totalClients') :
                 t('vendors.totalCounterparties')}
          value={data.total_vendors}
        />
        <Stat
          icon={ExclamationTriangleIcon}
          label={t('vendors.atRisk')}
          value={data.at_risk_count}
          sub={t('vendors.atRiskSub', { defaultValue: 'below performance thresholds' })}
          subTone={data.at_risk_count > 0 ? 'var(--da)' : undefined}
        />
        <Stat
          icon={ChartBarIcon}
          label={t('vendors.totalExposure')}
          value={`$${(data.total_exposure / 1000000).toFixed(1)}M`}
          sub={t('vendors.totalExposureSub', { defaultValue: 'sum of contract values' })}
        />
        <Stat
          icon={ChartBarIcon}
          label={t('vendors.avgScore')}
          value={(() => {
            const rated = data.vendors.filter((v) => v.performance_score != null) as (VendorListItem & { performance_score: number })[]
            return rated.length > 0
              ? (rated.reduce((sum, v) => sum + v.performance_score, 0) / rated.length).toFixed(1)
              : '—'
          })()}
          sub={t('vendors.avgScoreSub', { defaultValue: 'across rated counterparties' })}
        />
      </div>

      {/* Scorecard table */}
      {data.vendors.length === 0 ? (
        <div className="tbl-w">
          <EmptyState
            icon={BuildingOfficeIcon}
            title={t('vendors.noCounterparties')}
            body={t('vendors.emptyBody', { defaultValue: 'Scorecards appear once contracts with counterparties are analyzed.' })}
          />
        </div>
      ) : (
        <div className="tbl-w">
          <table className="tbl" style={{ minWidth: 920 }}>
            <thead>
              <tr>
                <SortableTh column="name" label={t('vendors.vendor')} />
                <SortableTh column="score" label={t('vendors.score')} width={140} />
                <th style={{ width: 110 }}>{t('vendors.risk')}</th>
                <SortableTh column="exposure" label={t('vendors.exposure')} width={130} align="r" />
                <th style={{ width: 150 }}>{t('vendors.oblCompliance')}</th>
                <th style={{ width: 150 }}>{t('vendors.slaCompliance')}</th>
                <th style={{ width: 90 }} className="r">{t('vendors.breaches')}</th>
              </tr>
            </thead>
            <tbody>
              {data.vendors.some((v) => v.tenant_name) ? (
                // Super-admin cross-tenant view — group under tenant headers
                Object.entries(
                  data.vendors.reduce<Record<string, VendorListItem[]>>((acc, v) => {
                    const key = v.tenant_name || '—'
                    ;(acc[key] ||= []).push(v)
                    return acc
                  }, {}),
                )
                  .sort(([a], [b]) => a.localeCompare(b))
                  .flatMap(([tenant, rows]) => [
                    <tr key={`hdr-${tenant}`}>
                      <td colSpan={7} style={{ background: 'var(--s3)', padding: '6px 14px' }}>
                        <span className="sec-t">
                          {tenant} · {t('vendors.contractsCount', { count: rows.length })}
                        </span>
                      </td>
                    </tr>,
                    ...rows.map((vendor, i) => (
                      <VendorRow
                        key={`${tenant}-${vendor.normalized_name}-${i}`}
                        vendor={vendor}
                        onClick={() => setSelectedVendor(vendor.vendor_name)}
                        showType={showType}
                        bands={bands}
                      />
                    )),
                  ])
              ) : (
                data.vendors.map((vendor, i) => (
                  <VendorRow
                    key={`${vendor.normalized_name}-${i}`}
                    vendor={vendor}
                    onClick={() => setSelectedVendor(vendor.vendor_name)}
                    showType={showType}
                    bands={bands}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail drawer */}
      {selectedVendor && (
        <VendorDrawer
          vendorName={selectedVendor}
          onClose={() => setSelectedVendor(null)}
          bands={bands}
        />
      )}
    </div>
  )
}
