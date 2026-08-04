/* Organizations registry — Direction B redesign.
   Header + search/type filters → sortable Table (Avatar + name with mono code,
   type Tags, contact) → create Drawer. The three-way delete choice
   (deactivate vs permanent) keeps the prototype's modal idiom with explicit
   affected/safe banners. Queries, mutations, filters and the admin-only delete
   are unchanged from the pre-redesign page. */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  BuildingLibraryIcon,
  ExclamationCircleIcon,
  MagnifyingGlassIcon,
  PlusIcon,
  TrashIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import {
  Avatar,
  Button,
  Drawer,
  EmptyState,
  Field,
  IconButton,
  Select,
  Table,
  Tag,
  useToast,
} from '@/components/ui'
import type { TableColumn } from '@/components/ui'
import type { Organization, OrganizationCreate, OrgType } from '@/types/governance'

const ORG_TYPE_LABELS: Record<OrgType, string> = {
  customer: 'Customer',
  vendor: 'Vendor',
  partner: 'Partner',
  internal: 'Internal',
}

export default function OrganizationsPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>('')
  const [showCreate, setShowCreate] = useState(false)
  const [formData, setFormData] = useState<Partial<OrganizationCreate>>({
    org_type: 'vendor',
  })
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin'
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const { data: organizations = [], isLoading } = useQuery({
    queryKey: ['organizations', typeFilter],
    queryFn: () => api.getOrganizations({
      org_type: typeFilter || undefined,
      active_only: true,
    }),
  })

  const createMutation = useMutation({
    mutationFn: (data: OrganizationCreate) => api.createOrganization(data),
    onSuccess: (_created, variables) => {
      queryClient.invalidateQueries({ queryKey: ['organizations'] })
      setShowCreate(false)
      setFormData({ org_type: 'vendor' })
      toast({ text: t('governance.orgCreated', { name: variables.name, defaultValue: '{{name}} created' }) })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: ({ id, hard }: { id: string; hard: boolean }) => api.deleteOrganization(id, hard),
    onSuccess: (_res, variables) => {
      queryClient.invalidateQueries({ queryKey: ['organizations'] })
      const name = deleteTarget?.name ?? ''
      setDeleteTarget(null)
      setActionError(null)
      toast({
        text: variables.hard
          ? t('governance.orgDeleted', { name, defaultValue: '{{name}} deleted' })
          : t('governance.orgDeactivated', { name, defaultValue: '{{name}} deactivated' }),
      })
    },
    onError: (err: Error) => {
      setDeleteTarget(null)
      setActionError(err.message || t('governance.deleteFailed'))
    },
  })

  const filtered = organizations.filter((org) =>
    org.name.toLowerCase().includes(search.toLowerCase()) ||
    org.code.toLowerCase().includes(search.toLowerCase())
  )

  const handleCreate = () => {
    if (!formData.name || !formData.code || !formData.org_type) return
    createMutation.mutate(formData as OrganizationCreate)
  }

  const closeCreate = () => setShowCreate(false)

  if (isLoading) {
    return (
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const orgTypeLabel = (type: OrgType) =>
    t(`governance.orgTypes.${type}`, { defaultValue: ORG_TYPE_LABELS[type] || type })

  const columns: TableColumn<Organization>[] = [
    {
      key: 'name',
      header: t('governance.name'),
      sortable: true,
      sortValue: (o) => o.name,
      render: (o) => (
        <span className="row" style={{ gap: 9 }}>
          <Avatar name={o.name} size={26} />
          <span style={{ minWidth: 0 }}>
            <span className="trunc" style={{ display: 'block', fontWeight: 500 }}>{o.name}</span>
            <span className="faint mono" style={{ display: 'block', fontSize: 'var(--fs-xs)', marginTop: 1 }}>
              {o.code}
            </span>
          </span>
        </span>
      ),
    },
    {
      key: 'org_type',
      header: t('governance.type'),
      sortable: true,
      sortValue: (o) => o.org_type,
      width: 120,
      render: (o) => <Tag icon={BuildingLibraryIcon}>{orgTypeLabel(o.org_type)}</Tag>,
    },
    {
      key: 'industry',
      header: t('governance.industry'),
      sortable: true,
      sortValue: (o) => o.industry,
      render: (o) =>
        o.industry ? <span className="muted">{o.industry}</span> : <span className="faint">—</span>,
    },
    {
      key: 'region',
      header: t('governance.region'),
      sortable: true,
      sortValue: (o) => o.region,
      render: (o) =>
        o.region ? <span className="muted">{o.region}</span> : <span className="faint">—</span>,
    },
    {
      key: 'contact',
      header: t('governance.primaryContact'),
      render: (o) =>
        o.primary_contact_name ? (
          <span style={{ minWidth: 0, display: 'block' }}>
            <span className="trunc muted" style={{ display: 'block' }}>{o.primary_contact_name}</span>
            {o.primary_contact_email && (
              <span className="faint trunc" style={{ display: 'block', fontSize: 'var(--fs-xs)' }}>
                {o.primary_contact_email}
              </span>
            )}
          </span>
        ) : (
          <span className="faint">—</span>
        ),
    },
    ...(isAdmin
      ? [{
          key: 'actions',
          header: '',
          width: 46,
          align: 'right' as const,
          render: (o: Organization) => (
            <IconButton
              icon={TrashIcon}
              size="sm"
              label={t('governance.deleteOrg')}
              onClick={(e) => {
                e.stopPropagation()
                setDeleteTarget({ id: o.id, name: o.name })
              }}
            />
          ),
        }]
      : []),
  ]

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div className="row" style={{ alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>
            {t('nav.organizations')}
          </h1>
          <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>
            {t('governance.organizationsSubtitle')}
          </p>
        </div>
        <Button variant="primary" icon={PlusIcon} onClick={() => setShowCreate(true)}>
          {t('governance.addOrganization')}
        </Button>
      </div>

      {/* Filters */}
      <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
        <Field
          icon={MagnifyingGlassIcon}
          type="text"
          placeholder={t('governance.searchOrganizations')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          containerStyle={{ width: 260 }}
          aria-label={t('governance.searchOrganizations')}
        />
        <Select
          aria-label={t('governance.type')}
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          containerStyle={{ width: 160 }}
          options={[
            { value: '', label: t('governance.allTypes') },
            ...Object.entries(ORG_TYPE_LABELS).map(([value, label]) => ({
              value,
              label: t(`governance.orgTypes.${value}`, { defaultValue: label }),
            })),
          ]}
        />
      </div>

      {actionError && (
        <div className="banner banner-da">
          <ExclamationCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
          <span className="grow">{actionError}</span>
          <IconButton icon={XMarkIcon} size="sm" label={t('common.cancel')} onClick={() => setActionError(null)} />
        </div>
      )}

      {/* Registry table */}
      <Table
        columns={columns}
        rows={filtered}
        rowKey={(o) => o.id}
        onRowClick={(o) => navigate(`/organizations/${o.id}`)}
        minWidth={720}
        empty={
          <EmptyState
            icon={BuildingLibraryIcon}
            title={t('governance.noOrganizationsFound')}
            body={
              search || typeFilter
                ? t('governance.noOrgsFilterHint', { defaultValue: 'No organization matches the current search or type filter.' })
                : t('governance.noOrgsEmptyHint', { defaultValue: 'Organizations are created here or auto-created when a contract with a new counterparty is analyzed.' })
            }
            action={
              !search && !typeFilter ? (
                <Button variant="primary" size="sm" icon={PlusIcon} onClick={() => setShowCreate(true)}>
                  {t('governance.addOrganization')}
                </Button>
              ) : undefined
            }
          />
        }
      />

      {/* Delete / deactivate choice — states exactly what each option affects */}
      {deleteTarget && (
        <div className="scrim" onClick={() => setDeleteTarget(null)}>
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label={t('governance.deleteOrg')}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-h">
              <span
                style={{
                  width: 34, height: 34, borderRadius: 'var(--r-md)', display: 'grid', placeItems: 'center',
                  background: 'var(--da-f)', color: 'var(--da)', flexShrink: 0,
                }}
              >
                <TrashIcon style={{ width: 18, height: 18 }} aria-hidden />
              </span>
              <h3 style={{ fontSize: 'var(--fs-xl)', fontWeight: 600, paddingTop: 3 }}>
                {t('governance.deleteOrgPrompt', { name: deleteTarget.name })}
              </h3>
            </div>
            <div className="modal-b">
              <p className="muted" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.55 }}>
                {t('governance.deleteOrgHint')}
              </p>
              <div className="banner banner-da" style={{ marginTop: 14, flexDirection: 'column', gap: 6 }}>
                <b style={{ fontSize: 'var(--fs-sm)', letterSpacing: '.3px', textTransform: 'uppercase' }}>
                  {t('governance.deleteRemovesTitle', { defaultValue: 'Permanent deletion removes' })}
                </b>
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  <li>{t('governance.deleteRemovesRecord', { defaultValue: 'The organization record and its officer contacts' })}</li>
                  <li>{t('governance.deleteRemovesHierarchy', { defaultValue: 'Its position in the corporate hierarchy' })}</li>
                </ul>
              </div>
              <div
                className="banner"
                style={{
                  marginTop: 8, flexDirection: 'column', gap: 6,
                  background: 'var(--ok-f)', borderColor: 'var(--ok-b)', color: 'var(--ok)',
                }}
              >
                <b style={{ fontSize: 'var(--fs-sm)', letterSpacing: '.3px', textTransform: 'uppercase' }}>
                  {t('governance.deleteSafeTitle', { defaultValue: 'Deactivating does not touch' })}
                </b>
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  <li>{t('governance.deleteSafeRefs', { defaultValue: 'Existing contracts and relationships — every reference stays intact' })}</li>
                  <li>{t('governance.deleteSafeReversible', { defaultValue: 'Anything permanently — deactivation is reversible' })}</li>
                </ul>
              </div>
            </div>
            <div className="modal-f">
              <Button variant="ghost" onClick={() => setDeleteTarget(null)}>
                {t('common.cancel')}
              </Button>
              <Button
                variant="secondary"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate({ id: deleteTarget.id, hard: false })}
              >
                {t('governance.deactivate')}
              </Button>
              <Button
                variant="danger"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate({ id: deleteTarget.id, hard: true })}
              >
                {t('governance.deletePermanently')}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Create drawer */}
      <Drawer
        open={showCreate}
        title={t('governance.newOrganization')}
        onClose={closeCreate}
        width={440}
        footer={
          <>
            <span className="grow" />
            <Button variant="ghost" onClick={closeCreate}>{t('common.cancel')}</Button>
            <Button
              variant="primary"
              disabled={!formData.name || !formData.code || createMutation.isPending}
              onClick={handleCreate}
            >
              {createMutation.isPending ? t('governance.creating') : t('governance.create')}
            </Button>
          </>
        }
      >
        <div className="col" style={{ gap: 14 }}>
          <div className="grid grid-cols-2 gap-3">
            <Field
              label={`${t('governance.name')} *`}
              type="text"
              autoFocus
              value={formData.name || ''}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            />
            <Field
              label={`${t('governance.code')} *`}
              type="text"
              value={formData.code || ''}
              placeholder={t('governance.codePlaceholder')}
              onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Select
              label={`${t('governance.type')} *`}
              value={formData.org_type || 'vendor'}
              onChange={(e) => setFormData({ ...formData, org_type: e.target.value as OrgType })}
              options={Object.entries(ORG_TYPE_LABELS).map(([value, label]) => ({
                value,
                label: t(`governance.orgTypes.${value}`, { defaultValue: label }),
              }))}
            />
            <Field
              label={t('governance.industry')}
              type="text"
              value={formData.industry || ''}
              onChange={(e) => setFormData({ ...formData, industry: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field
              label={t('governance.region')}
              type="text"
              value={formData.region || ''}
              onChange={(e) => setFormData({ ...formData, region: e.target.value })}
            />
            <Field
              label={t('governance.country')}
              type="text"
              value={formData.country || ''}
              onChange={(e) => setFormData({ ...formData, country: e.target.value })}
            />
          </div>
          <Field
            label={t('governance.primaryContactName')}
            type="text"
            value={formData.primary_contact_name || ''}
            onChange={(e) => setFormData({ ...formData, primary_contact_name: e.target.value })}
          />
          <Field
            label={t('governance.primaryContactEmail')}
            type="email"
            value={formData.primary_contact_email || ''}
            onChange={(e) => setFormData({ ...formData, primary_contact_email: e.target.value })}
          />
          {createMutation.isError && (
            <div className="banner banner-da">
              <ExclamationCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
              <span>{(createMutation.error as Error)?.message || t('governance.deleteFailed')}</span>
            </div>
          )}
        </div>
      </Drawer>
    </div>
  )
}
