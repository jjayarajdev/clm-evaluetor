/* Groups & families — Direction B redesign.
   Explainer banner → search + kind chips → sortable table with row selection,
   bulk-action bar and per-row delete → create-group Drawer. Data fetching,
   permission checks and the delete/invalidate flow are unchanged from the
   pre-redesign page. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowUpTrayIcon,
  FolderIcon,
  FolderPlusIcon,
  InformationCircleIcon,
  MagnifyingGlassIcon,
  SparklesIcon,
  TrashIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import {
  Button,
  Checkbox,
  Chip,
  ConfirmDialog,
  Drawer,
  EmptyState,
  Field,
  IconButton,
  Pill,
  Table,
  useToast,
} from '@/components/ui'
import type { IconType, PillTone, TableColumn } from '@/components/ui'
import { formatDate } from '@/lib/utils'
import type { ContractGroupResponse } from '@/lib/api/contracts'

const TYPE_META: Record<string, { labelKey: string; tone: PillTone; icon: IconType }> = {
  manual: { labelKey: 'groups.typeManual', tone: 'n', icon: FolderIcon },
  upload_batch: { labelKey: 'groups.typeUploadBatch', tone: 'in', icon: ArrowUpTrayIcon },
  auto_family: { labelKey: 'groups.typeAutoFamily', tone: 'p', icon: SparklesIcon },
}

export function GroupTypeBadge({ groupType }: { groupType: string }) {
  const { t } = useTranslation()
  const meta = TYPE_META[groupType] ?? TYPE_META.manual
  return <Pill tone={meta.tone}>{t(meta.labelKey)}</Pill>
}

export default function GroupsPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>('')
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [deleteTarget, setDeleteTarget] = useState<ContractGroupResponse | null>(null)
  const [isBulkConfirmOpen, setIsBulkConfirmOpen] = useState(false)

  const canWrite = user?.role !== 'viewer'

  const { data, isLoading } = useQuery({
    queryKey: ['contract-groups', search, typeFilter],
    queryFn: () =>
      api.getGroups({
        search: search || undefined,
        group_type: typeFilter || undefined,
        page_size: 100,
      }),
  })

  const closeCreate = () => {
    setIsCreateOpen(false)
    setNewName('')
    setNewDescription('')
    setFormError(null)
  }

  const createMutation = useMutation({
    mutationFn: () =>
      api.createGroup({ name: newName, description: newDescription || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract-groups'] })
      closeCreate()
      toast({ text: t('groups.createdToast', { defaultValue: 'Group created' }) })
    },
    onError: (err: Error) => setFormError(err.message || t('groups.createFailed')),
  })

  const groups = data?.items ?? []

  // Deleting a group never touches contracts. auto_family groups are derived
  // from contract links, so deleting them also dissolves those links (the
  // confirm dialogs say so) — hence the extra invalidations below.
  const invalidateAfterDelete = () => {
    queryClient.invalidateQueries({ queryKey: ['contract-groups'] })
    queryClient.invalidateQueries({ queryKey: ['contract-hierarchy'] })
    queryClient.invalidateQueries({ queryKey: ['contract-links'] })
    queryClient.invalidateQueries({ queryKey: ['suggested-links'] })
  }

  const deleteMutation = useMutation({
    mutationFn: (group: ContractGroupResponse) =>
      api.deleteGroup(group.id, group.group_type === 'auto_family'),
    onSuccess: (_data, group) => {
      invalidateAfterDelete()
      setSelected((prev) => {
        const next = new Set(prev)
        next.delete(group.id)
        return next
      })
      setDeleteTarget(null)
      toast({
        text: t('groups.deletedToast', {
          defaultValue: 'Group deleted. Contracts are never deleted.',
        }),
      })
    },
    onError: (err: Error) => {
      setDeleteTarget(null)
      toast({ text: err.message || t('groups.deleteFailed'), error: true })
    },
  })

  const selectedGroups = groups.filter((g: ContractGroupResponse) => selected.has(g.id))
  const selectionHasFamily = selectedGroups.some(
    (g: ContractGroupResponse) => g.group_type === 'auto_family'
  )

  const bulkDeleteMutation = useMutation({
    mutationFn: () => api.bulkDeleteGroups([...selected], selectionHasFamily),
    onSuccess: (_data, _vars, _ctx) => {
      invalidateAfterDelete()
      const count = selected.size
      setSelected(new Set())
      setIsBulkConfirmOpen(false)
      toast({
        text: t('groups.bulkDeletedToast', {
          count,
          defaultValue: '{{count}} groups deleted. Contracts are never deleted.',
        }),
      })
    },
    onError: (err: Error) => {
      setIsBulkConfirmOpen(false)
      toast({ text: err.message || t('groups.deleteFailed'), error: true })
    },
  })

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const allSelected = groups.length > 0 && groups.every((g) => selected.has(g.id))
  const someSelected = !allSelected && groups.some((g) => selected.has(g.id))
  const toggleAll = () => {
    setSelected(allSelected ? new Set() : new Set(groups.map((g: ContractGroupResponse) => g.id)))
  }

  const hasFilters = !!(search || typeFilter)

  const selColumns: TableColumn<ContractGroupResponse>[] = canWrite
    ? [
        {
          key: 'sel',
          width: 40,
          header: <Checkbox checked={allSelected} mixed={someSelected} onChange={toggleAll} />,
          render: (g) => (
            <Checkbox checked={selected.has(g.id)} onChange={() => toggleSelect(g.id)} />
          ),
        },
      ]
    : []

  const actionColumns: TableColumn<ContractGroupResponse>[] = canWrite
    ? [
        {
          key: 'actions',
          width: 50,
          align: 'right',
          header: '',
          render: (g) => (
            <IconButton
              icon={TrashIcon}
              label={t('groups.deleteGroupTitle')}
              size="sm"
              onClick={(e) => {
                e.stopPropagation()
                setDeleteTarget(g)
              }}
            />
          ),
        },
      ]
    : []

  const columns: TableColumn<ContractGroupResponse>[] = [
    ...selColumns,
    {
      key: 'name',
      header: t('groups.colGroup', { defaultValue: 'Group' }),
      sortable: true,
      sortValue: (g) => g.name.toLowerCase(),
      render: (g) => (
        <div style={{ maxWidth: 360 }}>
          <span className="trunc" style={{ display: 'block', fontWeight: 500 }}>{g.name}</span>
          {g.description && (
            <span className="faint trunc" style={{ display: 'block', fontSize: 'var(--fs-sm)', marginTop: 2 }}>
              {g.description}
            </span>
          )}
        </div>
      ),
    },
    {
      key: 'kind',
      header: t('groups.colKind', { defaultValue: 'Kind' }),
      width: 120,
      sortable: true,
      sortValue: (g) => g.group_type,
      render: (g) => <GroupTypeBadge groupType={g.group_type} />,
    },
    {
      key: 'members',
      header: t('groups.colMembers', { defaultValue: 'Members' }),
      width: 100,
      align: 'right',
      sortable: true,
      sortValue: (g) => g.member_count,
      render: (g) => <span className="num">{g.member_count}</span>,
    },
    {
      key: 'findings',
      header: t('groups.colFindings', { defaultValue: 'Findings' }),
      width: 110,
      align: 'right',
      sortable: true,
      sortValue: (g) => g.open_finding_count,
      render: (g) =>
        g.open_finding_count > 0 ? (
          <Pill tone="wa">
            {t('groups.openFindingsShort', { count: g.open_finding_count, defaultValue: '{{count}} open' })}
          </Pill>
        ) : (
          <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
            {t('groups.noFindings', { defaultValue: 'none' })}
          </span>
        ),
    },
    {
      key: 'updated',
      header: t('groups.updated'),
      width: 140,
      align: 'right',
      nowrap: true,
      sortable: true,
      sortValue: (g) => g.updated_at,
      render: (g) => (
        <span className="muted num" style={{ fontSize: 'var(--fs-sm)' }}>{formatDate(g.updated_at)}</span>
      ),
    },
    ...actionColumns,
  ]

  const emptyState = (
    <EmptyState
      icon={FolderIcon}
      title={
        hasFilters
          ? t('groups.emptyFilteredTitle', { defaultValue: 'No groups match' })
          : t('groups.emptyTitle', { defaultValue: 'No groups yet' })
      }
      body={
        hasFilters
          ? t('groups.emptyFilteredBody', { defaultValue: 'Loosen the search or kind filter to see more groups.' })
          : t('groups.emptyBody', {
              defaultValue:
                'Groups collect related contracts: create them manually, get one per upload batch, or let hierarchy detection materialise families automatically.',
            })
      }
      action={
        hasFilters ? (
          <Button
            variant="secondary"
            size="sm"
            icon={XMarkIcon}
            onClick={() => { setSearch(''); setTypeFilter('') }}
          >
            {t('groups.clearFilters', { defaultValue: 'Clear filters' })}
          </Button>
        ) : canWrite ? (
          <Button variant="primary" size="sm" icon={FolderPlusIcon} onClick={() => setIsCreateOpen(true)}>
            {t('groups.newGroup')}
          </Button>
        ) : undefined
      }
    />
  )

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div className="row" style={{ alignItems: 'flex-start' }}>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>{t('groups.title')}</h1>
          <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>{t('groups.subtitle')}</p>
        </div>
        {canWrite && (
          <Button variant="primary" icon={FolderPlusIcon} onClick={() => setIsCreateOpen(true)}>
            {t('groups.newGroup')}
          </Button>
        )}
      </div>

      {/* What groups are — three kinds */}
      <div className="banner banner-in">
        <InformationCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
        <span>
          {t('groups.kindsBanner', {
            defaultValue:
              'Three kinds of group: Manual groups you create, Upload batch groups are made automatically per upload, and Auto family groups are materialised from the contract hierarchy — deleting a family also removes its underlying links.',
          })}
        </span>
      </div>

      {/* Search + kind filter chips */}
      <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
        <Field
          icon={MagnifyingGlassIcon}
          placeholder={t('groups.searchPlaceholder')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          containerStyle={{ maxWidth: 320, minWidth: 200, flexGrow: 1 }}
        />
        {Object.entries(TYPE_META).map(([type, meta]) => (
          <Chip
            key={type}
            icon={meta.icon}
            on={typeFilter === type}
            onClick={() => setTypeFilter((prev) => (prev === type ? '' : type))}
          >
            {t(meta.labelKey)}
          </Chip>
        ))}
      </div>

      {/* Bulk-action bar */}
      {canWrite && selected.size > 0 && (
        <div className="row banner banner-p" style={{ gap: 12, alignItems: 'center' }}>
          <b>{t('groups.selectedCount', { count: selected.size })}</b>
          <span className="grow" />
          <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
            {t('groups.clearSelection')}
          </Button>
          <Button variant="danger-ghost" size="sm" icon={TrashIcon} onClick={() => setIsBulkConfirmOpen(true)}>
            {t('groups.deleteSelected')}
          </Button>
        </div>
      )}

      {/* Groups table */}
      {isLoading ? (
        <div className="row" style={{ justifyContent: 'center', height: 256 }}><LoadingSpinner size="lg" /></div>
      ) : (
        <Table<ContractGroupResponse>
          columns={columns}
          rows={groups}
          rowKey={(g) => g.id}
          onRowClick={(g) => navigate(`/groups/${g.id}`)}
          empty={emptyState}
          minWidth={680}
        />
      )}

      {/* Single delete confirmation */}
      {deleteTarget && (
        <ConfirmDialog
          open
          title={t('groups.deleteGroupTitle')}
          body={
            deleteTarget.group_type === 'auto_family'
              ? t('groups.deleteConfirmFamily', { name: deleteTarget.name })
              : t('groups.deleteConfirmSimple', { name: deleteTarget.name })
          }
          affected={[
            t('groups.affectedGroup', { defaultValue: 'This group and its membership records' }),
            ...(deleteTarget.group_type === 'auto_family'
              ? [t('groups.affectedLinks', { defaultValue: 'The hierarchy links between its members, so the family is not re-created' })]
              : []),
          ]}
          safe={[
            t('groups.safeContracts', { defaultValue: 'The contracts themselves — contracts are never deleted' }),
            t('groups.safeData', { defaultValue: 'Extracted metadata, clauses, risks and obligations' }),
          ]}
          confirmLabel={deleteMutation.isPending ? t('common.deleting') : t('common.delete')}
          cancelLabel={t('common.cancel')}
          onCancel={() => { if (!deleteMutation.isPending) setDeleteTarget(null) }}
          onConfirm={() => { if (!deleteMutation.isPending) deleteMutation.mutate(deleteTarget) }}
        />
      )}

      {/* Bulk delete confirmation */}
      <ConfirmDialog
        open={isBulkConfirmOpen}
        title={t('groups.deleteSelected')}
        body={t('groups.bulkDeleteConfirm', { count: selected.size })}
        affected={[
          t('groups.affectedGroupsBulk', {
            count: selected.size,
            defaultValue: 'The {{count}} selected groups and their membership records',
          }),
          ...(selectionHasFamily ? [t('groups.bulkDeleteFamilyNote')] : []),
        ]}
        safe={[
          t('groups.safeContracts', { defaultValue: 'The contracts themselves — contracts are never deleted' }),
          t('groups.safeData', { defaultValue: 'Extracted metadata, clauses, risks and obligations' }),
        ]}
        confirmLabel={bulkDeleteMutation.isPending ? t('common.deleting') : t('common.delete')}
        cancelLabel={t('common.cancel')}
        onCancel={() => { if (!bulkDeleteMutation.isPending) setIsBulkConfirmOpen(false) }}
        onConfirm={() => { if (!bulkDeleteMutation.isPending) bulkDeleteMutation.mutate() }}
      />

      {/* Create-group drawer */}
      <Drawer
        open={isCreateOpen}
        title={t('groups.newGroup')}
        onClose={closeCreate}
        width={420}
        footer={
          <>
            <span className="grow" />
            <Button variant="ghost" onClick={closeCreate}>{t('common.cancel')}</Button>
            <Button
              variant="primary"
              disabled={!newName.trim() || createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              {createMutation.isPending ? t('common.saving') : t('common.create')}
            </Button>
          </>
        }
      >
        <div className="col" style={{ gap: 14 }}>
          <Field
            label={t('groups.name')}
            value={newName}
            maxLength={255}
            autoFocus
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && newName.trim() && !createMutation.isPending) createMutation.mutate()
            }}
          />
          <div>
            <label className="lbl">{t('groups.description')}</label>
            <div className="inp" style={{ height: 'auto', padding: '8px 10px' }}>
              <textarea
                rows={3}
                style={{ resize: 'vertical' }}
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
              />
            </div>
          </div>
          <p className="faint" style={{ fontSize: 'var(--fs-sm)', lineHeight: 1.5 }}>
            {t('groups.createHint', {
              defaultValue: 'Manual groups let you collect any contracts together — add members from the group page after creating it.',
            })}
          </p>
          {formError && <div className="banner banner-da">{formError}</div>}
        </div>
      </Drawer>
    </div>
  )
}
