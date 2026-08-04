/* Business relationships — Direction B redesign.
   Header → summary Stats → type filter Chips → relationship card grid
   (two-party Avatar pairing, health ring footer with banding, perception meta)
   → health-breakdown Drawer → create Drawer → delete ConfirmDialog.
   Queries, mutations, filters and the admin-only delete are unchanged from the
   pre-redesign page. */
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowsRightLeftIcon,
  ChartBarIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  HeartIcon,
  InformationCircleIcon,
  LinkIcon,
  PlusIcon,
  ShieldCheckIcon,
  TrashIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import {
  Avatar,
  Bar,
  Button,
  Chip,
  ConfirmDialog,
  Drawer,
  EmptyState,
  Field,
  IconButton,
  Pill,
  Select,
  Stat,
  Tag,
  useToast,
} from '@/components/ui'
import type { PillTone } from '@/components/ui'
import type {
  BusinessRelationship,
  RelationshipCreate,
  RelationshipStatus,
  GovernanceTier,
  HealthScoreFactor,
} from '@/types/governance'

// ── Tone maps (live-page banding: ≥80 ok, ≥60 warn, else danger) ─

function healthTone(score: number): string {
  return score >= 80 ? 'var(--ok)' : score >= 60 ? 'var(--wa)' : 'var(--da)'
}

const STATUS_TONE: Record<RelationshipStatus, PillTone> = {
  prospecting: 'n',
  active: 'ok',
  at_risk: 'da',
  on_hold: 'wa',
  terminated: 'n',
}

const TIER_TONE: Record<GovernanceTier, PillTone> = {
  operational: 'n',
  tactical: 'wa',
  strategic: 'in',
  executive: 'p',
}

// ── Health ring ──────────────────────────────────────────────────

function HealthRing({ score, size = 48, thick = 5 }: { score: number; size?: number; thick?: number }) {
  const tone = healthTone(score)
  const r = (size - thick) / 2
  const c = 2 * Math.PI * r
  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--b)" strokeWidth={thick} />
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke={tone} strokeWidth={thick} strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - score / 100)}
          style={{ transition: 'stroke-dashoffset .6s var(--ease)' }}
        />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}>
        <span
          className="num"
          style={{ fontSize: size >= 72 ? 'var(--fs-xl)' : 'var(--fs-xs)', fontWeight: 600, color: tone }}
        >
          {score}
        </span>
      </div>
    </div>
  )
}

// ── Health-breakdown drawer ──────────────────────────────────────

function FactorBar({ factor }: { factor: HealthScoreFactor }) {
  const tone = healthTone(factor.score)
  return (
    <div className="col" style={{ gap: 5 }}>
      <div className="row" style={{ gap: 8 }}>
        <span style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>{factor.label}</span>
        {factor.weight > 0 && (
          <span className="faint num" style={{ fontSize: 'var(--fs-xs)' }}>{factor.weight}%</span>
        )}
        <span className="grow" />
        <span className="num" style={{ fontSize: 'var(--fs-md)', fontWeight: 600, color: tone }}>{factor.score}</span>
      </div>
      <Bar value={factor.score} width="100%" tone={tone} />
      <p className="faint" style={{ fontSize: 'var(--fs-sm)', lineHeight: 1.5 }}>{factor.detail}</p>
    </div>
  )
}

function MiniStat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ background: 'var(--s2)', borderRadius: 'var(--r-md)', padding: '8px 10px', textAlign: 'center' }}>
      <div className="num" style={{ fontSize: 'var(--fs-lg)', fontWeight: 600 }}>{value}</div>
      <div className="faint" style={{ fontSize: 'var(--fs-xs)', marginTop: 2 }}>{label}</div>
    </div>
  )
}

function HealthDrawer({ relationship, onClose }: { relationship: BusinessRelationship; onClose: () => void }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { data: health, isLoading } = useQuery({
    queryKey: ['relationship-health', relationship.id],
    queryFn: () => api.getRelationshipHealth(relationship.id),
  })

  const factors = health?.factors || {}
  const counterparty = relationship.org_b?.name || relationship.name || ''
  const orderedFactors = (['risk', 'sla', 'obligations'] as const)
    .map((k) => factors[k])
    .filter((f): f is HealthScoreFactor => typeof f === 'object' && f != null)
  const perception = typeof factors.perception === 'object' ? (factors.perception as HealthScoreFactor) : null

  return (
    <Drawer
      open
      title={t('governance.healthScoreBreakdown')}
      sub={counterparty}
      onClose={onClose}
      width={440}
      footer={
        <Button
          variant="primary"
          className="grow"
          onClick={() => { onClose(); navigate(`/relationships/${relationship.id}`) }}
        >
          {t('governance.viewFullDetails')}
        </Button>
      }
    >
      <div className="col" style={{ gap: 20 }}>
        <div className="row" style={{ justifyContent: 'center', padding: '8px 0' }}>
          <HealthRing score={relationship.health_score} size={96} thick={8} />
        </div>

        {isLoading ? (
          <div className="row" style={{ justifyContent: 'center', padding: 32 }}>
            <LoadingSpinner />
          </div>
        ) : (
          <>
            {orderedFactors.map((f) => <FactorBar key={f.label} factor={f} />)}

            {perception && (
              <div className="col" style={{ gap: 5, borderTop: '1px solid var(--b)', paddingTop: 14 }}>
                <FactorBar factor={{ ...perception, weight: 0 }} />
                <p className="faint" style={{ fontSize: 'var(--fs-xs)', fontStyle: 'italic' }}>
                  {t('governance.perceptionInformational')}
                </p>
              </div>
            )}

            {orderedFactors.length === 0 && (
              <div className="col" style={{ alignItems: 'center', gap: 6, padding: '8px 0', textAlign: 'center' }}>
                <InformationCircleIcon style={{ width: 28, height: 28, color: 'var(--f)' }} aria-hidden />
                <p className="muted" style={{ fontSize: 'var(--fs-md)' }}>{t('governance.noContractData')}</p>
                <p className="faint" style={{ fontSize: 'var(--fs-sm)' }}>{t('governance.healthEstimatedFromPerception')}</p>
              </div>
            )}

            <div className="grid gap-2 grid-cols-3" style={{ borderTop: '1px solid var(--b)', paddingTop: 14 }}>
              <MiniStat
                label={t('governance.contracts')}
                value={typeof factors.contract_count === 'number' ? factors.contract_count : relationship.contract_count || 0}
              />
              <MiniStat
                label={t('governance.kpis')}
                value={typeof factors.kpi_count === 'number' ? factors.kpi_count : relationship.kpi_count || 0}
              />
              <MiniStat
                label={t('governance.tier')}
                value={relationship.governance_tier
                  ? t(`governance.tiers.${relationship.governance_tier}`, {
                      defaultValue: relationship.governance_tier.charAt(0).toUpperCase() + relationship.governance_tier.slice(1),
                    })
                  : '—'}
              />
            </div>
          </>
        )}
      </div>
    </Drawer>
  )
}

// ── Relationship card ────────────────────────────────────────────

function RelationshipCard({
  rel, isAdmin, onDelete, onHealth,
}: {
  rel: BusinessRelationship
  isAdmin: boolean
  onDelete: () => void
  onHealth: () => void
}) {
  const { t } = useTranslation()
  const counterparty = rel.org_b?.name || rel.name || ''
  const atRisk = rel.health_score < 70

  return (
    <div
      className="card col"
      style={{ gap: 0, overflow: 'hidden', borderColor: atRisk ? 'var(--da-b)' : undefined }}
    >
      <Link to={`/relationships/${rel.id}`} className="card-p col grow" style={{ gap: 11, color: 'inherit' }}>
        <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
          <Pill tone={STATUS_TONE[rel.status] || 'n'}>
            {t(`governance.relationshipStatus.${rel.status}`, { defaultValue: rel.status })}
          </Pill>
          <Tag>
            {t(`governance.relationshipTypes.${rel.relationship_type}`, { defaultValue: rel.relationship_type.replace('_', ' ') })}
          </Tag>
          <span className="grow" />
          {rel.governance_tier && (
            <Pill tone={TIER_TONE[rel.governance_tier] || 'n'} dot={false}>
              {t(`governance.tiers.${rel.governance_tier}`, {
                defaultValue: rel.governance_tier.charAt(0).toUpperCase() + rel.governance_tier.slice(1),
              })}
            </Pill>
          )}
          {isAdmin && (
            <IconButton
              icon={TrashIcon}
              label={t('governance.deleteRelationship')}
              size="sm"
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDelete() }}
            />
          )}
        </div>

        {/* Two-party pairing */}
        <div className="row" style={{ gap: 8, minWidth: 0 }}>
          <span className="row" style={{ gap: 4, flexShrink: 0 }}>
            <Avatar name={rel.org_a?.name || ''} size={24} />
            <ArrowsRightLeftIcon style={{ width: 13, height: 13, color: 'var(--f)' }} aria-hidden />
            <Avatar name={counterparty} size={24} />
          </span>
          <span className="trunc" style={{ fontSize: 'var(--fs-lg)', fontWeight: 600 }}>{counterparty}</span>
        </div>

        <div className="row" style={{ gap: 12, fontSize: 'var(--fs-sm)', color: 'var(--f)', flexWrap: 'wrap' }}>
          {(rel.contract_count ?? 0) > 0 && (
            <span className="row" style={{ gap: 4 }}>
              <DocumentTextIcon style={{ width: 13, height: 13 }} aria-hidden />
              {t('governance.contractsCount', { count: rel.contract_count })}
            </span>
          )}
          {(rel.kpi_count ?? 0) > 0 && (
            <span className="row" style={{ gap: 4 }}>
              <ChartBarIcon style={{ width: 13, height: 13 }} aria-hidden />
              {t('governance.kpisCount', { count: rel.kpi_count })}
            </span>
          )}
          {rel.annual_value && (
            <span className="num" style={{ fontWeight: 500, color: 'var(--m)' }}>
              {t('governance.perYear', { value: `${rel.currency || '$'}${Number(rel.annual_value).toLocaleString()}` })}
            </span>
          )}
        </div>
      </Link>

      {/* Health footer — opens the breakdown drawer */}
      <button
        type="button"
        className="row"
        onClick={onHealth}
        title={t('governance.clickForBreakdown')}
        style={{
          gap: 8, padding: '9px 14px', cursor: 'pointer', textAlign: 'left',
          borderTop: `1px solid ${atRisk ? 'var(--da-b)' : 'var(--b)'}`,
          background: atRisk ? 'var(--da-f)' : 'var(--s3)',
        }}
      >
        <HealthRing score={rel.health_score} size={30} thick={4} />
        <span className="muted" style={{ fontSize: 'var(--fs-sm)' }}>{t('governance.healthScore')}</span>
        <span className="grow" />
        <span style={{ fontSize: 'var(--fs-sm)', fontWeight: 500, color: 'var(--p)' }}>
          {t('governance.viewBreakdown')}
        </span>
      </button>
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────

export default function RelationshipsPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const { toast } = useToast()
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin'
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [selectedRelationship, setSelectedRelationship] = useState<BusinessRelationship | null>(null)
  const [filterType, setFilterType] = useState<string>('')
  const [formData, setFormData] = useState<Partial<RelationshipCreate>>({
    relationship_type: 'customer',
    governance_tier: 'tactical',
  })

  const { data: relationships = [], isLoading } = useQuery({
    queryKey: ['relationships'],
    queryFn: () => api.getRelationships(),
  })

  const { data: organizations = [] } = useQuery({
    queryKey: ['organizations'],
    queryFn: () => api.getOrganizations({ active_only: true }),
  })

  const createMutation = useMutation({
    mutationFn: (data: RelationshipCreate) => api.createRelationship(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['relationships'] })
      setShowCreate(false)
      setFormData({ relationship_type: 'customer', governance_tier: 'tactical' })
      toast({ text: t('governance.relationshipCreated', { defaultValue: 'Relationship created' }) })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteRelationship(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['relationships'] })
      setDeleteTarget(null)
      setDeleteError(null)
      toast({ text: t('governance.relationshipDeleted', { defaultValue: 'Relationship deleted' }) })
    },
    onError: (err: Error) => {
      setDeleteTarget(null)
      setDeleteError(err.message || t('governance.deleteFailed'))
    },
  })

  const handleCreate = () => {
    if (!formData.org_a_id || !formData.org_b_id || !formData.relationship_type) return
    createMutation.mutate(formData as RelationshipCreate)
  }

  if (isLoading) {
    return (
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  // Summary stats
  const totalRelationships = relationships.length
  const avgHealth = totalRelationships > 0
    ? Math.round(relationships.reduce((sum, r) => sum + (r.health_score || 0), 0) / totalRelationships)
    : 0
  const atRiskCount = relationships.filter(r => r.health_score < 70).length
  const healthyCount = relationships.filter(r => r.health_score >= 80).length

  // Type counts
  const typeCounts = relationships.reduce((acc, r) => {
    acc[r.relationship_type] = (acc[r.relationship_type] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  // Filter, then sort by health score (worst first for attention)
  const filtered = filterType
    ? relationships.filter(r => r.relationship_type === filterType)
    : relationships
  const sorted = [...filtered].sort((a, b) => a.health_score - b.health_score)

  const orgOptions = [
    { value: '', label: t('governance.selectOrganization') },
    ...organizations.map((org) => ({
      value: org.id,
      label: `${org.name} (${t(`governance.orgTypes.${org.org_type}`, { defaultValue: org.org_type })})`,
    })),
  ]

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div className="row" style={{ alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>
            {t('governance.businessRelationships')}
          </h1>
          <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>
            {t('governance.relationshipsSubtitle')}
          </p>
        </div>
        <Button variant="primary" icon={PlusIcon} onClick={() => setShowCreate(true)}>
          {t('governance.newRelationship')}
        </Button>
      </div>

      {/* Summary stats */}
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        <Stat icon={LinkIcon} label={t('governance.total')} value={totalRelationships} />
        <Stat
          icon={HeartIcon}
          label={t('governance.avgHealth')}
          value={<span style={{ color: healthTone(avgHealth) }}>{avgHealth}</span>}
        />
        <Stat
          icon={ShieldCheckIcon}
          label={t('governance.healthy')}
          value={healthyCount}
          sub={t('governance.healthyAtOrAbove', { defaultValue: 'health score 80 or above' })}
        />
        <Stat
          icon={ExclamationTriangleIcon}
          label={t('governance.needsAttention')}
          value={atRiskCount}
          sub={t('governance.belowHealth70', { defaultValue: 'below health 70' })}
          subTone={atRiskCount > 0 ? 'var(--da)' : undefined}
        />
      </div>

      {/* Type filter */}
      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
        <Chip on={!filterType} onClick={() => setFilterType('')}>
          {t('governance.allCount', { count: totalRelationships })}
        </Chip>
        {Object.entries(typeCounts).map(([type, count]) => (
          <Chip key={type} on={filterType === type} onClick={() => setFilterType(filterType === type ? '' : type)}>
            {t(`governance.relationshipTypes.${type}`, { defaultValue: type.replace('_', ' ') })} ({count})
          </Chip>
        ))}
      </div>

      {deleteError && (
        <div className="banner banner-da">
          <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
          <span>{deleteError}</span>
        </div>
      )}

      {/* Relationship cards */}
      {sorted.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={LinkIcon}
            title={filterType ? t('governance.noRelationshipsMatchFilter') : t('governance.noRelationshipsYet')}
            body={filterType
              ? t('governance.tryAnotherFilter', { defaultValue: 'Try a different relationship type filter.' })
              : t('governance.relationshipsEmptyBody', { defaultValue: 'Create a relationship to start tracking health, KPIs and perception.' })}
            action={!filterType
              ? <Button variant="primary" icon={PlusIcon} onClick={() => setShowCreate(true)}>{t('governance.newRelationship')}</Button>
              : undefined}
          />
        </div>
      ) : (
        <div className="grid gap-3 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
          {sorted.map((rel) => (
            <RelationshipCard
              key={rel.id}
              rel={rel}
              isAdmin={isAdmin}
              onDelete={() => setDeleteTarget({ id: rel.id, name: rel.org_b?.name || rel.name || '' })}
              onHealth={() => setSelectedRelationship(rel)}
            />
          ))}
        </div>
      )}

      {/* Delete confirmation */}
      {deleteTarget && (
        <ConfirmDialog
          open
          title={t('governance.deleteRelationship')}
          body={t('governance.deleteRelationshipPrompt', { name: deleteTarget.name })}
          affected={[
            t('governance.deleteRelationshipWarning'),
          ]}
          safe={[
            t('governance.deleteSafeOrgs', { defaultValue: 'The organizations themselves — they stay in the registry' }),
            t('governance.deleteSafeContracts', { defaultValue: 'Contracts — contracts are never deleted' }),
          ]}
          confirmLabel={deleteMutation.isPending ? t('common.deleting') : t('common.delete')}
          cancelLabel={t('common.cancel')}
          onCancel={() => { if (!deleteMutation.isPending) setDeleteTarget(null) }}
          onConfirm={() => { if (!deleteMutation.isPending) deleteMutation.mutate(deleteTarget.id) }}
        />
      )}

      {/* Health-breakdown drawer */}
      {selectedRelationship && (
        <HealthDrawer relationship={selectedRelationship} onClose={() => setSelectedRelationship(null)} />
      )}

      {/* Create drawer */}
      <Drawer
        open={showCreate}
        title={t('governance.newRelationship')}
        onClose={() => setShowCreate(false)}
        width={440}
        footer={
          <>
            <span className="grow" />
            <Button variant="ghost" onClick={() => setShowCreate(false)}>{t('common.cancel')}</Button>
            <Button
              variant="primary"
              disabled={!formData.org_a_id || !formData.org_b_id || createMutation.isPending}
              onClick={handleCreate}
            >
              {createMutation.isPending ? t('governance.creating') : t('governance.create')}
            </Button>
          </>
        }
      >
        <div className="col" style={{ gap: 14 }}>
          <Select
            label={`${t('governance.organizationA')} *`}
            value={formData.org_a_id || ''}
            onChange={(e) => setFormData({ ...formData, org_a_id: e.target.value })}
            options={orgOptions}
          />
          <Select
            label={`${t('governance.organizationB')} *`}
            value={formData.org_b_id || ''}
            onChange={(e) => setFormData({ ...formData, org_b_id: e.target.value })}
            options={[
              orgOptions[0],
              ...orgOptions.slice(1).filter((o) => o.value !== formData.org_a_id),
            ]}
          />
          <div className="grid gap-3 grid-cols-2">
            <Select
              label={`${t('governance.type')} *`}
              value={formData.relationship_type || 'customer'}
              onChange={(e) => setFormData({ ...formData, relationship_type: e.target.value as RelationshipCreate['relationship_type'] })}
              options={[
                { value: 'customer', label: t('governance.relationshipTypes.customer') },
                { value: 'supplier', label: t('governance.relationshipTypes.supplier') },
                { value: 'partner', label: t('governance.relationshipTypes.partner') },
                { value: 'joint_venture', label: t('governance.relationshipTypes.joint_venture') },
                { value: 'reseller', label: t('governance.relationshipTypes.reseller') },
                { value: 'distributor', label: t('governance.relationshipTypes.distributor') },
              ]}
            />
            <Select
              label={t('governance.governanceTier')}
              value={formData.governance_tier || 'tactical'}
              onChange={(e) => setFormData({ ...formData, governance_tier: e.target.value as RelationshipCreate['governance_tier'] })}
              options={[
                { value: 'operational', label: t('governance.tiers.operational') },
                { value: 'tactical', label: t('governance.tiers.tactical') },
                { value: 'strategic', label: t('governance.tiers.strategic') },
                { value: 'executive', label: t('governance.tiers.executive') },
              ]}
            />
          </div>
          <div>
            <label className="lbl">{t('governance.description')}</label>
            <div className="inp" style={{ height: 'auto', padding: '8px 10px' }}>
              <textarea
                rows={2}
                style={{ resize: 'vertical' }}
                value={formData.description || ''}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </div>
          </div>
          <div className="grid gap-3 grid-cols-2">
            <Field
              label={t('governance.annualValue')}
              type="number"
              value={formData.annual_value ?? ''}
              onChange={(e) => setFormData({ ...formData, annual_value: Number(e.target.value) })}
            />
            <Field
              label={t('governance.currency')}
              value={formData.currency || ''}
              onChange={(e) => setFormData({ ...formData, currency: e.target.value.toUpperCase() })}
              placeholder="USD"
              maxLength={3}
            />
          </div>
        </div>
      </Drawer>
    </div>
  )
}
