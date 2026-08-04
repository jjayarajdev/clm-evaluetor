/* Organization detail — Direction B redesign.
   Back link + header (mono code, status Pill, type/industry/region Tags) →
   Tabs (Overview / Officers / Hierarchy / Relationships). Officers get a
   sortable Table with add-officer Drawer and a ConfirmDialog on removal;
   hierarchy keeps the collapsible tree, relationships list health with Bars.
   All queries (lazy per tab), mutations and navigation are unchanged from the
   pre-redesign page. */
import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  ArrowTurnDownRightIcon,
  BuildingLibraryIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  PlusIcon,
  ShareIcon,
  Squares2X2Icon,
  UserGroupIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import {
  Avatar,
  Bar,
  Button,
  Checkbox,
  ConfirmDialog,
  Drawer,
  EmptyState,
  Field,
  Pill,
  Select,
  Stat,
  Table,
  Tabs,
  Tag,
  useToast,
} from '@/components/ui'
import type { TableColumn } from '@/components/ui'
import type {
  OfficerCreate,
  GovernanceRole,
  OfficerSide,
  OrganizationOfficer,
  OrganizationTreeNode,
} from '@/types/fitgap'

const ROLE_LABELS: Record<GovernanceRole, string> = {
  account_manager: 'Account Manager',
  service_delivery_manager: 'Service Delivery Manager',
  relationship_owner: 'Relationship Owner',
  executive_sponsor: 'Executive Sponsor',
  commercial_manager: 'Commercial Manager',
  technical_lead: 'Technical Lead',
  operations_lead: 'Operations Lead',
  compliance_officer: 'Compliance Officer',
  other: 'Other',
}

const SIDE_LABELS: Record<OfficerSide, string> = {
  internal: 'Internal',
  external: 'External',
}

const SIDE_TONE: Record<OfficerSide, 'in' | 'p'> = {
  internal: 'in',
  external: 'p',
}

const TABS = ['Overview', 'Officers', 'Hierarchy', 'Relationships'] as const
type Tab = typeof TABS[number]

const TAB_ICONS: Record<Tab, typeof Squares2X2Icon> = {
  Overview: Squares2X2Icon,
  Officers: UserGroupIcon,
  Hierarchy: BuildingLibraryIcon,
  Relationships: ShareIcon,
}

/** Health banding shared with the relationships module: ≥70 ok, ≥40 warn. */
function healthTone(score: number): string {
  return score >= 70 ? 'var(--ok)' : score >= 40 ? 'var(--wa)' : 'var(--da)'
}

/** Label/value pair inside overview cards. */
function DetailRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <div className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{label}</div>
      <div style={{ fontSize: 'var(--fs-md)', fontWeight: 500, marginTop: 1 }}>
        {value || <span className="faint">—</span>}
      </div>
    </div>
  )
}

function TreeNodeComponent({ node, depth = 0 }: { node: OrganizationTreeNode; depth?: number }) {
  const [expanded, setExpanded] = useState(depth < 2)
  const hasChildren = node.children && node.children.length > 0
  const Chevron = expanded ? ChevronDownIcon : ChevronRightIcon

  return (
    <div>
      <div
        className="row"
        style={{
          gap: 8,
          padding: '7px 10px',
          paddingLeft: depth * 24 + 10,
          borderRadius: 'var(--r-md)',
          cursor: hasChildren ? 'pointer' : undefined,
        }}
        onClick={() => hasChildren && setExpanded(!expanded)}
      >
        {hasChildren ? (
          <Chevron style={{ width: 13, height: 13, flexShrink: 0, color: 'var(--f)' }} aria-hidden />
        ) : (
          <span style={{ width: 13, flexShrink: 0 }} />
        )}
        <BuildingLibraryIcon style={{ width: 15, height: 15, flexShrink: 0, color: 'var(--p)' }} aria-hidden />
        <span className="trunc" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>{node.name}</span>
        <span className="faint mono" style={{ fontSize: 'var(--fs-xs)' }}>{node.code}</span>
        {node.organization_level && (
          <Tag>
            <span style={{ textTransform: 'capitalize' }}>{node.organization_level}</span>
          </Tag>
        )}
      </div>
      {expanded && hasChildren && (
        <div>
          {node.children.map((child) => (
            <TreeNodeComponent key={child.id} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function OrganizationDetailPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [activeTab, setActiveTab] = useState<Tab>('Overview')
  const [showAddOfficer, setShowAddOfficer] = useState(false)
  const [officerForm, setOfficerForm] = useState<Partial<OfficerCreate>>({ side: 'internal' })
  const [removeTarget, setRemoveTarget] = useState<{ id: string; name: string } | null>(null)

  const { data: org, isLoading } = useQuery({
    queryKey: ['organization', id],
    queryFn: () => api.getOrganization(id!),
    enabled: !!id,
  })

  const { data: officerData } = useQuery({
    queryKey: ['officers', id],
    queryFn: () => api.getOrganizationOfficers(id!),
    enabled: !!id && activeTab === 'Officers',
  })
  const officers = officerData?.items ?? []

  const { data: hierarchy } = useQuery({
    queryKey: ['hierarchy', id],
    queryFn: () => api.getOrganizationHierarchy(id!),
    enabled: !!id && activeTab === 'Hierarchy',
  })

  const { data: tree = [] } = useQuery({
    queryKey: ['org-tree'],
    queryFn: () => api.getOrganizationTree(),
    enabled: activeTab === 'Hierarchy',
  })

  const { data: orgRelationships = [] } = useQuery({
    queryKey: ['org-relationships', id],
    queryFn: async () => {
      const response = await api.getRelationships()
      return response.filter(
        (r) => r.org_a_id === id || r.org_b_id === id
      )
    },
    enabled: !!id && activeTab === 'Relationships',
  })

  const createOfficerMutation = useMutation({
    mutationFn: (data: OfficerCreate) => api.createOfficer(id!, data),
    onSuccess: (_res, variables) => {
      queryClient.invalidateQueries({ queryKey: ['officers', id] })
      setShowAddOfficer(false)
      setOfficerForm({ side: 'internal' })
      toast({ text: t('governance.officerAdded', { name: variables.name, defaultValue: '{{name}} added' }) })
    },
  })

  const deleteOfficerMutation = useMutation({
    mutationFn: (officerId: string) => api.deleteOfficer(id!, officerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['officers', id] })
      toast({ text: t('governance.officerRemoved', { defaultValue: 'Officer removed' }) })
    },
  })

  if (isLoading || !org) {
    return (
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const roleLabel = (role: GovernanceRole) =>
    t(`governance.officerRoles.${role}`, { defaultValue: ROLE_LABELS[role] || role })

  const officerColumns: TableColumn<OrganizationOfficer>[] = [
    {
      key: 'name',
      header: t('governance.name'),
      sortable: true,
      sortValue: (o) => o.name,
      render: (o) => (
        <span className="row" style={{ gap: 9 }}>
          <Avatar name={o.name} size={26} />
          <span className="row" style={{ gap: 6, minWidth: 0 }}>
            <span className="trunc" style={{ fontWeight: 500 }}>{o.name}</span>
            {o.is_primary && <Tag>{t('governance.primary')}</Tag>}
          </span>
        </span>
      ),
    },
    {
      key: 'title',
      header: t('governance.title'),
      sortable: true,
      sortValue: (o) => o.title,
      render: (o) => (o.title ? <span className="muted">{o.title}</span> : <span className="faint">—</span>),
    },
    {
      key: 'governance_role',
      header: t('governance.role'),
      sortable: true,
      sortValue: (o) => o.governance_role,
      render: (o) =>
        o.governance_role ? <Tag>{roleLabel(o.governance_role)}</Tag> : <span className="faint">—</span>,
    },
    {
      key: 'side',
      header: t('governance.side'),
      sortable: true,
      sortValue: (o) => o.side,
      width: 110,
      render: (o) =>
        o.side ? (
          <Pill tone={SIDE_TONE[o.side]}>
            {t(`governance.sides.${o.side}`, { defaultValue: SIDE_LABELS[o.side] })}
          </Pill>
        ) : (
          <span className="faint">—</span>
        ),
    },
    {
      key: 'contact',
      header: t('governance.contact'),
      render: (o) =>
        o.email || o.phone ? (
          <span className="muted trunc" style={{ display: 'block' }}>{o.email || o.phone}</span>
        ) : (
          <span className="faint">—</span>
        ),
    },
    {
      key: 'actions',
      header: '',
      width: 90,
      align: 'right',
      render: (o) => (
        <Button
          variant="danger-ghost"
          size="sm"
          onClick={() => setRemoveTarget({ id: o.id, name: o.name })}
        >
          {t('governance.remove')}
        </Button>
      ),
    },
  ]

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Back link + header */}
      <div>
        <Link
          to="/organizations"
          className="row"
          style={{ gap: 4, width: 'fit-content', fontSize: 'var(--fs-sm)', color: 'var(--m)' }}
        >
          <ArrowLeftIcon style={{ width: 14, height: 14 }} aria-hidden />
          {t('governance.backToOrganizations', { defaultValue: 'Back to organizations' })}
        </Link>
        <div className="row" style={{ gap: 12, alignItems: 'flex-start', marginTop: 10, flexWrap: 'wrap' }}>
          <Avatar name={org.name} size={40} />
          <div className="grow" style={{ minWidth: 240 }}>
            <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
              <h1 style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600, letterSpacing: '-.4px', lineHeight: 1.25 }}>
                {org.name}
              </h1>
              <span className="mono faint" style={{ fontSize: 'var(--fs-xs)' }}>{org.code}</span>
            </div>
            <div className="row" style={{ gap: 7, marginTop: 7, flexWrap: 'wrap' }}>
              <Pill tone={org.is_active ? 'ok' : 'n'}>
                {org.is_active
                  ? t('governance.statusActive', { defaultValue: 'Active' })
                  : t('governance.statusInactive', { defaultValue: 'Inactive' })}
              </Pill>
              <Tag icon={BuildingLibraryIcon}>
                {t(`governance.orgTypes.${org.org_type}`, { defaultValue: org.org_type })}
              </Tag>
              {org.industry && <Tag>{org.industry}</Tag>}
              {org.region && <Tag>{org.region}</Tag>}
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <Tabs<Tab>
        tabs={TABS.map((tab) => ({
          value: tab,
          label: t(`governance.tabs.${tab.toLowerCase()}`, { defaultValue: tab }),
          icon: TAB_ICONS[tab],
          count: tab === 'Officers' && officers.length > 0 ? officers.length : undefined,
        }))}
        value={activeTab}
        onChange={setActiveTab}
      />

      {/* Overview */}
      {activeTab === 'Overview' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
          <div className="card card-p col" style={{ gap: 12 }}>
            <div className="sec-t">{t('governance.details')}</div>
            <DetailRow
              label={t('governance.type')}
              value={t(`governance.orgTypes.${org.org_type}`, { defaultValue: org.org_type })}
            />
            <DetailRow label={t('governance.industry')} value={org.industry} />
            <DetailRow label={t('governance.region')} value={org.region} />
            <DetailRow label={t('governance.country')} value={org.country} />
            <DetailRow label={t('governance.website')} value={org.website} />
          </div>
          <div className="card card-p col" style={{ gap: 12 }}>
            <div className="sec-t">{t('governance.primaryContact')}</div>
            <DetailRow label={t('governance.name')} value={org.primary_contact_name} />
            <DetailRow label={t('governance.email')} value={org.primary_contact_email} />
            <DetailRow label={t('governance.phone')} value={org.primary_contact_phone} />
          </div>
        </div>
      )}

      {/* Officers */}
      {activeTab === 'Officers' && (
        <div className="col" style={{ gap: 12 }}>
          <div className="row" style={{ gap: 8 }}>
            <span className="sec-t">{t('governance.organizationOfficersCount', { count: officers.length })}</span>
            <span className="grow" />
            <Button variant="primary" size="sm" icon={PlusIcon} onClick={() => setShowAddOfficer(true)}>
              {t('governance.addOfficer')}
            </Button>
          </div>
          <Table
            columns={officerColumns}
            rows={officers}
            rowKey={(o) => o.id}
            minWidth={680}
            empty={
              <EmptyState
                icon={UserGroupIcon}
                title={t('governance.noOfficers')}
                action={
                  <Button variant="primary" size="sm" icon={PlusIcon} onClick={() => setShowAddOfficer(true)}>
                    {t('governance.addOfficer')}
                  </Button>
                }
              />
            }
          />
        </div>
      )}

      {/* Hierarchy */}
      {activeTab === 'Hierarchy' && (
        <div className="col" style={{ gap: 12 }}>
          {hierarchy && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {hierarchy.parent && (
                <div className="card card-p col" style={{ gap: 4 }}>
                  <div className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('governance.parentOrganization')}</div>
                  <Link
                    to={`/organizations/${hierarchy.parent.id}`}
                    style={{ fontSize: 'var(--fs-md)', fontWeight: 500, color: 'var(--p)' }}
                  >
                    {hierarchy.parent.name}
                  </Link>
                  <span className="faint mono" style={{ fontSize: 'var(--fs-xs)' }}>{hierarchy.parent.code}</span>
                </div>
              )}
              <div className="card card-p col" style={{ gap: 4 }}>
                <div className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('governance.current')}</div>
                <span style={{ fontSize: 'var(--fs-md)', fontWeight: 600 }}>{hierarchy.organization.name}</span>
                {hierarchy.organization.organization_level && (
                  <span className="faint" style={{ fontSize: 'var(--fs-xs)', textTransform: 'capitalize' }}>
                    {hierarchy.organization.organization_level}
                  </span>
                )}
              </div>
              <Stat
                icon={BuildingLibraryIcon}
                label={t('governance.subsidiaries')}
                value={hierarchy.children?.length ?? 0}
              />
            </div>
          )}

          {hierarchy && hierarchy.children && hierarchy.children.length > 0 && (
            <div className="card">
              <div className="sec-t" style={{ padding: '11px 14px', borderBottom: '1px solid var(--b)' }}>
                {t('governance.directSubsidiaries')}
              </div>
              <div>
                {hierarchy.children.map((sub, n) => (
                  <Link
                    key={sub.id}
                    to={`/organizations/${sub.id}`}
                    className="row"
                    style={{
                      gap: 9,
                      padding: '10px 14px',
                      borderBottom: n < hierarchy.children.length - 1 ? '1px solid var(--b)' : undefined,
                    }}
                  >
                    <ArrowTurnDownRightIcon style={{ width: 13, height: 13, flexShrink: 0, color: 'var(--f)' }} aria-hidden />
                    <Avatar name={sub.name} size={24} />
                    <span className="grow row" style={{ gap: 7, minWidth: 0 }}>
                      <span className="trunc" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>{sub.name}</span>
                      <span className="faint mono" style={{ fontSize: 'var(--fs-xs)' }}>{sub.code}</span>
                    </span>
                    {sub.organization_level && (
                      <Tag>
                        <span style={{ textTransform: 'capitalize' }}>{sub.organization_level}</span>
                      </Tag>
                    )}
                  </Link>
                ))}
              </div>
            </div>
          )}

          {tree.length > 0 && (
            <div className="card">
              <div className="sec-t" style={{ padding: '11px 14px', borderBottom: '1px solid var(--b)' }}>
                {t('governance.organizationTree')}
              </div>
              <div style={{ padding: '6px 6px' }}>
                {tree.map((node) => (
                  <TreeNodeComponent key={node.id} node={node} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Relationships */}
      {activeTab === 'Relationships' && (
        <div className="card">
          <div className="row sec-t" style={{ padding: '11px 14px', borderBottom: '1px solid var(--b)', gap: 7 }}>
            <ShareIcon style={{ width: 14, height: 14 }} aria-hidden />
            {t('governance.businessRelationshipsCount', { count: orgRelationships.length })}
          </div>
          <div>
            {orgRelationships.map((rel, n) => (
              <Link
                key={rel.id}
                to={`/relationships/${rel.id}`}
                className="row"
                style={{
                  gap: 12,
                  padding: '11px 14px',
                  borderBottom: n < orgRelationships.length - 1 ? '1px solid var(--b)' : undefined,
                }}
              >
                <span className="grow" style={{ minWidth: 0 }}>
                  <span className="trunc" style={{ display: 'block', fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                    {rel.org_a?.name || rel.org_a_id} ↔ {rel.org_b?.name || rel.org_b_id}
                  </span>
                  <span className="row muted" style={{ gap: 6, marginTop: 3, fontSize: 'var(--fs-sm)', textTransform: 'capitalize' }}>
                    {t(`governance.relationshipTypes.${rel.relationship_type}`, { defaultValue: rel.relationship_type })}
                    <span className="faint">·</span>
                    {t(`governance.tiers.${rel.governance_tier}`, { defaultValue: rel.governance_tier })}
                  </span>
                </span>
                <span className="row" style={{ gap: 7, flexShrink: 0 }}>
                  <Bar value={rel.health_score} width={56} tone={healthTone(rel.health_score)} />
                  <span
                    className="mono num"
                    style={{ fontSize: 'var(--fs-sm)', fontWeight: 600, color: healthTone(rel.health_score) }}
                  >
                    {rel.health_score}
                  </span>
                </span>
              </Link>
            ))}
            {orgRelationships.length === 0 && (
              <EmptyState
                icon={ShareIcon}
                title={t('governance.noRelationshipsForOrg')}
                body={t('governance.noRelationshipsForOrgHint', {
                  defaultValue: 'Relationships between this organization and others appear here once created.',
                })}
              />
            )}
          </div>
        </div>
      )}

      {/* Remove officer — states exactly what is and is not affected */}
      <ConfirmDialog
        open={!!removeTarget}
        title={t('governance.removeOfficerTitle', {
          name: removeTarget?.name ?? '',
          defaultValue: 'Remove {{name}}?',
        })}
        body={t('governance.removeOfficerBody', {
          defaultValue: 'This removes the officer contact from this organization.',
        })}
        affected={[
          t('governance.removeOfficerAffected', {
            defaultValue: 'The officer contact entry for this organization',
          }),
        ]}
        safe={[
          t('governance.removeOfficerSafeOrg', {
            defaultValue: 'The organization itself and its relationships',
          }),
          t('governance.removeOfficerSafeContracts', {
            defaultValue: 'Contracts — they are never deleted',
          }),
        ]}
        confirmLabel={t('governance.remove')}
        cancelLabel={t('common.cancel')}
        onCancel={() => setRemoveTarget(null)}
        onConfirm={() => {
          if (removeTarget) deleteOfficerMutation.mutate(removeTarget.id)
          setRemoveTarget(null)
        }}
      />

      {/* Add officer drawer */}
      <Drawer
        open={showAddOfficer}
        title={t('governance.addOfficer')}
        sub={org.code}
        onClose={() => setShowAddOfficer(false)}
        width={440}
        footer={
          <>
            <span className="grow" />
            <Button variant="ghost" onClick={() => setShowAddOfficer(false)}>{t('common.cancel')}</Button>
            <Button
              variant="primary"
              disabled={!officerForm.name || createOfficerMutation.isPending}
              onClick={() => {
                if (officerForm.name) createOfficerMutation.mutate(officerForm as OfficerCreate)
              }}
            >
              {createOfficerMutation.isPending ? t('governance.adding') : t('governance.addOfficer')}
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
              value={officerForm.name || ''}
              onChange={(e) => setOfficerForm({ ...officerForm, name: e.target.value })}
            />
            <Field
              label={t('governance.title')}
              type="text"
              value={officerForm.title || ''}
              onChange={(e) => setOfficerForm({ ...officerForm, title: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Select
              label={t('governance.governanceRole')}
              value={officerForm.governance_role || ''}
              onChange={(e) =>
                setOfficerForm({
                  ...officerForm,
                  governance_role: (e.target.value || undefined) as GovernanceRole | undefined,
                })
              }
              options={[
                { value: '', label: t('governance.selectRole') },
                ...Object.entries(ROLE_LABELS).map(([value, label]) => ({
                  value,
                  label: t(`governance.officerRoles.${value}`, { defaultValue: label }),
                })),
              ]}
            />
            <Select
              label={t('governance.side')}
              value={officerForm.side || 'internal'}
              onChange={(e) => setOfficerForm({ ...officerForm, side: e.target.value as OfficerSide })}
              options={[
                { value: 'internal', label: t('governance.sides.internal') },
                { value: 'external', label: t('governance.sides.external') },
              ]}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field
              label={t('governance.email')}
              type="email"
              value={officerForm.email || ''}
              onChange={(e) => setOfficerForm({ ...officerForm, email: e.target.value })}
            />
            <Field
              label={t('governance.phone')}
              type="text"
              value={officerForm.phone || ''}
              onChange={(e) => setOfficerForm({ ...officerForm, phone: e.target.value })}
            />
          </div>
          <Field
            label={t('governance.department')}
            type="text"
            value={officerForm.department || ''}
            onChange={(e) => setOfficerForm({ ...officerForm, department: e.target.value })}
          />
          <Checkbox
            checked={officerForm.is_primary || false}
            onChange={(checked) => setOfficerForm({ ...officerForm, is_primary: checked })}
            label={t('governance.primaryContact')}
          />
        </div>
      </Drawer>
    </div>
  )
}
