/* Tenant management — Direction B redesign.
   Header + show-inactive toggle → sortable Table (plan/status Pills) →
   create/edit in a Drawer, activate/deactivate via ConfirmDialog with
   affected/safe lists, permanent purge keeps its type-the-slug gate in a
   token-styled modal. Queries, mutations and the provisioning flow are
   unchanged from the pre-redesign page; restyle only. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  PlusIcon,
  PencilSquareIcon,
  EyeIcon,
  CheckCircleIcon,
  BuildingOffice2Icon,
  TrashIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import {
  Avatar,
  Button,
  Checkbox,
  ConfirmDialog,
  Drawer,
  EmptyState,
  Field,
  IconButton,
  Pill,
  Select,
  Table,
  useToast,
} from '@/components/ui'
import type { PillTone, TableColumn } from '@/components/ui'
import { formatDate } from '@/lib/utils'
import type { Tenant, TenantCreate, TenantUpdate, TenantPlan } from '@/types'

const PLAN_LABELS: Record<TenantPlan, string> = {
  starter: 'Starter',
  professional: 'Professional',
  enterprise: 'Enterprise',
}

const PLAN_TONES: Record<TenantPlan, PillTone> = {
  starter: 'n',
  professional: 'in',
  enterprise: 'p',
}

interface TenantFormData {
  name: string
  slug: string
  plan: TenantPlan
  contract_limit: string
  contact_email: string
}

const emptyFormData: TenantFormData = {
  name: '',
  slug: '',
  plan: 'starter',
  contract_limit: '',
  contact_email: '',
}

const FORM_ID = 'tenant-form'

export default function TenantManagementPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null)
  const [formData, setFormData] = useState<TenantFormData>(emptyFormData)
  const [showInactive, setShowInactive] = useState(false)
  const [toggleTarget, setToggleTarget] = useState<Tenant | null>(null)

  const { data: tenants, isLoading, error } = useQuery({
    queryKey: ['tenants', showInactive],
    queryFn: () => api.getTenants(showInactive),
  })

  // Fetch stats for each tenant to show contract counts
  const { data: tenantStatsMap } = useQuery({
    queryKey: ['tenant-stats-all', tenants?.length],
    queryFn: async () => {
      if (!tenants?.length) return {}
      const results = await Promise.all(
        tenants.map(t =>
          api.getTenantStats(t.id).catch(() => ({ tenant_id: t.id, contract_count: 0, user_count: 0 }))
        )
      )
      const map: Record<string, { contract_count: number; user_count: number }> = {}
      for (const s of results) {
        map[s.tenant_id] = s
      }
      return map
    },
    enabled: !!tenants?.length,
  })

  const createMutation = useMutation({
    mutationFn: (data: TenantCreate) => api.createTenant(data),
    onSuccess: (_res, variables) => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
      closeDrawer()
      toast({ text: t('superadmin.tenants.createdToast', { defaultValue: '{{name}} created', name: variables.name }) })
    },
    onError: (err: any) => {
      toast({ text: err?.response?.data?.detail || err?.message || t('superadmin.tenants.loadError'), error: true })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: TenantUpdate }) =>
      api.updateTenant(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
      closeDrawer()
      toast({ text: t('superadmin.tenants.updatedToast', { defaultValue: 'Tenant updated' }) })
    },
    onError: (err: any) => {
      toast({ text: err?.response?.data?.detail || err?.message || t('superadmin.tenants.loadError'), error: true })
    },
  })

  const activateMutation = useMutation({
    mutationFn: (id: string) => api.activateTenant(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
      toast({ text: t('superadmin.tenants.activatedToast', { defaultValue: 'Tenant activated' }) })
    },
    onError: (err: any) => {
      toast({ text: err?.response?.data?.detail || err?.message || t('superadmin.tenants.loadError'), error: true })
    },
  })

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => api.deactivateTenant(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
      toast({ text: t('superadmin.tenants.deactivatedToast', { defaultValue: 'Tenant deactivated' }) })
    },
    onError: (err: any) => {
      toast({ text: err?.response?.data?.detail || err?.message || t('superadmin.tenants.loadError'), error: true })
    },
  })

  const [purgingTenant, setPurgingTenant] = useState<Tenant | null>(null)
  const [purgeConfirmText, setPurgeConfirmText] = useState('')
  const [purgeResult, setPurgeResult] = useState<{ tenant: string; deleted: Record<string, number> } | null>(null)

  const purgeMutation = useMutation({
    mutationFn: (id: string) => api.purgeTenant(id),
    onSuccess: (data) => {
      setPurgeResult(data)
      setPurgingTenant(null)
      setPurgeConfirmText('')
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
      queryClient.invalidateQueries({ queryKey: ['tenant-stats-all'] })
    },
  })

  const openCreateDrawer = () => {
    setEditingTenant(null)
    setFormData(emptyFormData)
    setIsDrawerOpen(true)
  }

  const openEditDrawer = (tenant: Tenant) => {
    setEditingTenant(tenant)
    setFormData({
      name: tenant.name,
      slug: tenant.slug,
      plan: tenant.plan,
      contract_limit: tenant.contract_limit?.toString() || '',
      contact_email: tenant.contact_email || '',
    })
    setIsDrawerOpen(true)
  }

  const closeDrawer = () => {
    setIsDrawerOpen(false)
    setEditingTenant(null)
    setFormData(emptyFormData)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const payload = {
      name: formData.name,
      slug: formData.slug,
      plan: formData.plan,
      contract_limit: formData.contract_limit ? parseInt(formData.contract_limit) : null,
      contact_email: formData.contact_email || null,
    }

    if (editingTenant) {
      updateMutation.mutate({ id: editingTenant.id, data: payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  const confirmToggleActive = () => {
    if (!toggleTarget) return
    if (toggleTarget.is_active) {
      deactivateMutation.mutate(toggleTarget.id)
    } else {
      activateMutation.mutate(toggleTarget.id)
    }
    setToggleTarget(null)
  }

  const generateSlug = (name: string) => {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')
  }

  const isSaving = createMutation.isPending || updateMutation.isPending
  const toggleBusy = activateMutation.isPending || deactivateMutation.isPending

  const columns: TableColumn<Tenant>[] = [
    {
      key: 'tenant',
      header: t('superadmin.tenant'),
      sortable: true,
      sortValue: (tn) => tn.name,
      render: (tn) => (
        <span className="row" style={{ gap: 10 }}>
          <Avatar name={tn.name} size={28} />
          <span style={{ minWidth: 0 }}>
            <span className="trunc" style={{ display: 'block', fontWeight: 500 }}>{tn.name}</span>
            <span className="faint mono trunc" style={{ display: 'block', fontSize: 'var(--fs-xs)' }}>{tn.slug}</span>
          </span>
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
          {t(`superadmin.plans.${tn.plan}`, { defaultValue: PLAN_LABELS[tn.plan] })}
        </Pill>
      ),
    },
    {
      key: 'contracts',
      header: t('superadmin.tenants.contracts'),
      width: 110,
      sortable: true,
      sortValue: (tn) => tenantStatsMap?.[tn.id]?.contract_count ?? -1,
      render: (tn) => (
        <span className="num" style={{ fontSize: 'var(--fs-md)' }}>
          <span style={{ fontWeight: 500 }}>{tenantStatsMap?.[tn.id]?.contract_count ?? '—'}</span>
          <span className="faint"> / {tn.contract_limit || '∞'}</span>
        </span>
      ),
    },
    {
      key: 'status',
      header: t('common.status'),
      width: 110,
      sortable: true,
      sortValue: (tn) => (tn.is_active ? 0 : 1),
      render: (tn) => (
        <button
          type="button"
          onClick={() => setToggleTarget(tn)}
          disabled={toggleBusy}
          style={{ background: 'none', border: 0, padding: 0, cursor: 'pointer' }}
          title={tn.is_active ? t('superadmin.tenants.deactivateAction', { defaultValue: 'Deactivate' }) : t('superadmin.tenants.activateAction', { defaultValue: 'Activate' })}
        >
          <Pill tone={tn.is_active ? 'ok' : 'da'}>
            {tn.is_active ? t('status.active') : t('status.inactive')}
          </Pill>
        </button>
      ),
    },
    {
      key: 'created',
      header: t('superadmin.created'),
      width: 130,
      nowrap: true,
      sortable: true,
      sortValue: (tn) => tn.created_at,
      render: (tn) => <span className="muted" style={{ fontSize: 'var(--fs-sm)' }}>{formatDate(tn.created_at)}</span>,
    },
    {
      key: 'actions',
      header: '',
      width: 110,
      align: 'right',
      render: (tn) => (
        <span className="row" style={{ gap: 4, justifyContent: 'flex-end' }}>
          <IconButton
            icon={EyeIcon}
            size="sm"
            label={t('superadmin.tenants.viewDetails')}
            onClick={() => navigate(`/super-admin/tenants/${tn.id}`)}
          />
          <IconButton
            icon={PencilSquareIcon}
            size="sm"
            label={t('superadmin.tenants.editTenant')}
            onClick={() => openEditDrawer(tn)}
          />
          <IconButton
            icon={TrashIcon}
            size="sm"
            label={t('superadmin.tenants.deleteTenantPermanently')}
            onClick={() => { setPurgingTenant(tn); setPurgeConfirmText(''); setPurgeResult(null) }}
          />
        </span>
      ),
    },
  ]

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div className="row" style={{ alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>
            {t('superadmin.tenants.title')}
          </h1>
          <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>
            {t('superadmin.tenants.subtitle')}
          </p>
        </div>
        <Button variant="primary" icon={PlusIcon} onClick={openCreateDrawer}>
          {t('superadmin.tenants.addTenant')}
        </Button>
      </div>

      {/* Filters */}
      <Checkbox
        checked={showInactive}
        onChange={setShowInactive}
        label={t('superadmin.tenants.showInactive')}
      />

      {/* Error state */}
      {error && (
        <div className="banner banner-da">
          <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
          <span>{t('superadmin.tenants.loadError')}</span>
        </div>
      )}

      {/* Table */}
      {isLoading ? (
        <div className="row" style={{ justifyContent: 'center', height: 256 }}>
          <LoadingSpinner size="lg" />
        </div>
      ) : (
        <Table
          columns={columns}
          rows={tenants ?? []}
          rowKey={(tn) => tn.id}
          minWidth={720}
          empty={
            <EmptyState
              icon={BuildingOffice2Icon}
              title={t('superadmin.tenants.noTenants')}
              action={
                <Button variant="primary" size="sm" icon={PlusIcon} onClick={openCreateDrawer}>
                  {t('superadmin.tenants.addTenant')}
                </Button>
              }
            />
          }
        />
      )}

      {/* Create / edit drawer */}
      <Drawer
        open={isDrawerOpen}
        title={editingTenant ? t('superadmin.tenants.editTenantTitle') : t('superadmin.tenants.createTenantTitle')}
        sub={editingTenant?.slug}
        onClose={closeDrawer}
        footer={
          <>
            <Button variant="ghost" onClick={closeDrawer}>
              {t('common.cancel')}
            </Button>
            <span className="grow" />
            <Button variant="primary" type="submit" form={FORM_ID} disabled={isSaving}>
              {isSaving
                ? t('common.saving')
                : editingTenant
                  ? t('superadmin.update')
                  : t('superadmin.create')}
            </Button>
          </>
        }
      >
        <form id={FORM_ID} onSubmit={handleSubmit} className="col" style={{ gap: 14 }}>
          <Field
            label={`${t('superadmin.tenants.organizationName')} *`}
            type="text"
            value={formData.name}
            onChange={(e) => {
              const name = e.target.value
              setFormData({
                ...formData,
                name,
                slug: editingTenant ? formData.slug : generateSlug(name),
              })
            }}
            required
            placeholder="Acme Corporation"
          />
          <Field
            label={`${t('superadmin.tenants.slug')} *`}
            type="text"
            className="mono"
            value={formData.slug}
            onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
            required
            placeholder="acme-corp"
            pattern="[a-z0-9-]+"
            title={t('superadmin.tenants.slugPattern')}
            hint={t('superadmin.tenants.slugHint')}
          />
          <Select
            label={`${t('superadmin.plan')} *`}
            value={formData.plan}
            onChange={(e) => setFormData({ ...formData, plan: e.target.value as TenantPlan })}
            options={Object.entries(PLAN_LABELS).map(([value, label]) => ({
              value,
              label: t(`superadmin.plans.${value}`, { defaultValue: label }),
            }))}
          />
          <Field
            label={t('superadmin.contractLimit')}
            type="number"
            value={formData.contract_limit}
            onChange={(e) => setFormData({ ...formData, contract_limit: e.target.value })}
            placeholder={t('superadmin.unlimitedPlaceholder')}
            min="1"
          />
          <Field
            label={t('superadmin.contactEmail')}
            type="email"
            value={formData.contact_email}
            onChange={(e) => setFormData({ ...formData, contact_email: e.target.value })}
            placeholder="admin@example.com"
          />
        </form>
      </Drawer>

      {/* Activate / deactivate confirmation — replaces the old window.confirm */}
      <ConfirmDialog
        open={toggleTarget != null}
        tone={toggleTarget?.is_active ? 'danger' : 'warn'}
        title={
          toggleTarget?.is_active
            ? t('superadmin.tenants.deactivateTitle', { defaultValue: 'Deactivate tenant?' })
            : t('superadmin.tenants.activateTitle', { defaultValue: 'Activate tenant?' })
        }
        body={
          toggleTarget?.is_active
            ? t('superadmin.tenants.deactivateConfirm', { name: toggleTarget?.name ?? '' })
            : t('superadmin.tenants.activateConfirm', { name: toggleTarget?.name ?? '' })
        }
        affected={
          toggleTarget?.is_active
            ? [t('superadmin.tenants.deactivateAffectedLogins', { defaultValue: 'Sign-in for every user of this tenant' })]
            : undefined
        }
        safe={
          toggleTarget?.is_active
            ? [
                t('superadmin.tenants.deactivateSafeData', { defaultValue: 'Contracts, users and settings — everything is kept and restored on reactivation' }),
              ]
            : undefined
        }
        confirmLabel={
          toggleTarget?.is_active
            ? t('superadmin.tenants.deactivateAction', { defaultValue: 'Deactivate' })
            : t('superadmin.tenants.activateAction', { defaultValue: 'Activate' })
        }
        cancelLabel={t('common.cancel')}
        onConfirm={confirmToggleActive}
        onCancel={() => setToggleTarget(null)}
      />

      {/* Purge confirmation — keeps the type-the-slug gate, token-styled modal */}
      {purgingTenant && (
        <div className="scrim" onClick={() => setPurgingTenant(null)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label={t('superadmin.tenants.deleteTenantTitle')} onClick={(e) => e.stopPropagation()}>
            <div className="modal-h">
              <span
                style={{
                  width: 34, height: 34, borderRadius: 'var(--r-md)', display: 'grid', placeItems: 'center',
                  background: 'var(--da-f)', color: 'var(--da)', flexShrink: 0,
                }}
              >
                <ExclamationTriangleIcon style={{ width: 18, height: 18 }} aria-hidden />
              </span>
              <div style={{ paddingTop: 3 }}>
                <h3 style={{ fontSize: 'var(--fs-xl)', fontWeight: 600, letterSpacing: '-.3px' }}>
                  {t('superadmin.tenants.deleteTenantTitle')}
                </h3>
                <p className="faint" style={{ fontSize: 'var(--fs-sm)', marginTop: 2 }}>
                  {t('superadmin.tenants.cannotBeUndone')}
                </p>
              </div>
            </div>
            <div className="modal-b col" style={{ gap: 12, paddingTop: 14 }}>
              <div className="banner banner-da" style={{ flexDirection: 'column', gap: 6 }}>
                <span>
                  {t('superadmin.tenants.purgeWarningPrefix')} <b>{purgingTenant.name}</b> {t('superadmin.tenants.purgeWarningSuffix')}
                </span>
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  <li>{t('superadmin.tenants.purgeItemContracts')}</li>
                  <li>{t('superadmin.tenants.purgeItemUsers')}</li>
                  <li>{t('superadmin.tenants.purgeItemOrgs')}</li>
                  <li>{t('superadmin.tenants.purgeItemVectors')}</li>
                  <li>{t('superadmin.tenants.purgeItemSettings')}</li>
                </ul>
              </div>
              {tenantStatsMap?.[purgingTenant.id] && (
                <p className="muted" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                  {t('superadmin.tenants.purgeStats', {
                    contracts: tenantStatsMap[purgingTenant.id].contract_count,
                    users: tenantStatsMap[purgingTenant.id].user_count,
                  })}
                </p>
              )}
              <div>
                <label className="lbl">
                  {t('superadmin.tenants.typeToConfirmPrefix')}{' '}
                  <span className="mono" style={{ color: 'var(--da)' }}>{purgingTenant.slug}</span>{' '}
                  {t('superadmin.tenants.typeToConfirmSuffix')}
                </label>
                <Field
                  type="text"
                  className="mono"
                  value={purgeConfirmText}
                  onChange={(e) => setPurgeConfirmText(e.target.value)}
                  placeholder={purgingTenant.slug}
                  autoFocus
                />
              </div>
              {purgeMutation.isError && (
                <div className="banner banner-da">
                  <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
                  <span>{(purgeMutation.error as Error)?.message || t('superadmin.tenants.purgeFailed')}</span>
                </div>
              )}
            </div>
            <div className="modal-f">
              <Button variant="ghost" onClick={() => setPurgingTenant(null)}>
                {t('common.cancel')}
              </Button>
              <Button
                variant="danger"
                onClick={() => purgeMutation.mutate(purgingTenant.id)}
                disabled={purgeConfirmText !== purgingTenant.slug || purgeMutation.isPending}
              >
                {purgeMutation.isPending ? t('superadmin.tenants.deleting') : t('superadmin.tenants.deletePermanently')}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Purge result — deletion summary */}
      {purgeResult && (
        <div className="scrim" onClick={() => setPurgeResult(null)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label={t('superadmin.tenants.tenantDeleted')} onClick={(e) => e.stopPropagation()}>
            <div className="modal-h">
              <span
                style={{
                  width: 34, height: 34, borderRadius: 'var(--r-md)', display: 'grid', placeItems: 'center',
                  background: 'var(--ok-f)', color: 'var(--ok)', flexShrink: 0,
                }}
              >
                <CheckCircleIcon style={{ width: 18, height: 18 }} aria-hidden />
              </span>
              <div style={{ paddingTop: 3 }}>
                <h3 style={{ fontSize: 'var(--fs-xl)', fontWeight: 600, letterSpacing: '-.3px' }}>
                  {t('superadmin.tenants.tenantDeleted')}
                </h3>
              </div>
            </div>
            <div className="modal-b col" style={{ gap: 12, paddingTop: 14 }}>
              <p className="muted" style={{ fontSize: 'var(--fs-md)' }}>
                <b>{purgeResult.tenant}</b> {t('superadmin.tenants.deletedSuffix')}
              </p>
              <div className="card card-p" style={{ background: 'var(--s2)' }}>
                <div className="sec-t" style={{ marginBottom: 8 }}>{t('superadmin.tenants.deletionSummary')}</div>
                <div className="col" style={{ gap: 4 }}>
                  {Object.entries(purgeResult.deleted)
                    .filter(([, count]) => count > 0)
                    .map(([table, count]) => (
                      <div key={table} className="row" style={{ justifyContent: 'space-between' }}>
                        <span className="muted" style={{ fontSize: 'var(--fs-md)' }}>{table.replace(/_/g, ' ')}</span>
                        <span className="mono num" style={{ fontSize: 'var(--fs-md)' }}>{count}</span>
                      </div>
                    ))}
                </div>
              </div>
            </div>
            <div className="modal-f">
              <Button variant="primary" onClick={() => setPurgeResult(null)}>
                {t('superadmin.tenants.done')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
