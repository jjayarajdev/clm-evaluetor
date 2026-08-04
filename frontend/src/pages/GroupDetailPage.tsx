/* Group detail — Direction B redesign.
   Back link + header with kind pill and meta row → cross-document findings card
   → sub-group chips → sortable member table → add-contracts Drawer and a
   ConfirmDialog delete flow. Data fetching, mutations and invalidations are
   unchanged from the pre-redesign page. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  DocumentTextIcon,
  FolderIcon,
  MagnifyingGlassIcon,
  PlusIcon,
  TrashIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import {
  Button,
  Checkbox,
  ConfirmDialog,
  Drawer,
  EmptyState,
  Field,
  IconButton,
  Pill,
  Table,
  useToast,
} from '@/components/ui'
import type { PillTone, TableColumn } from '@/components/ui'
import { formatDate } from '@/lib/utils'
import { GroupTypeBadge } from '@/pages/GroupsPage'
import type { ContractGroupMemberEntry } from '@/lib/api/contracts'

const SOURCE_LABEL_KEYS: Record<string, string> = {
  manual: 'groups.sourceManual',
  upload_batch: 'groups.sourceUploadBatch',
  auto_family: 'groups.sourceAutoFamily',
}

const SOURCE_TONE: Record<string, PillTone> = {
  manual: 'n',
  upload_batch: 'in',
  auto_family: 'p',
}

export default function GroupDetailPage() {
  const { t } = useTranslation()
  const { groupId } = useParams<{ groupId: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [isAddOpen, setIsAddOpen] = useState(false)
  const [isDeleteOpen, setIsDeleteOpen] = useState(false)
  const [contractSearch, setContractSearch] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  const canWrite = user?.role !== 'viewer'

  const { data: group, isLoading } = useQuery({
    queryKey: ['contract-group', groupId],
    queryFn: () => api.getGroup(groupId!),
    enabled: !!groupId,
  })

  const { data: candidates } = useQuery({
    queryKey: ['group-candidate-contracts', contractSearch],
    queryFn: () => api.getContracts({ search: contractSearch || undefined, page_size: 20 }),
    enabled: isAddOpen,
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['contract-group', groupId] })
    queryClient.invalidateQueries({ queryKey: ['contract-groups'] })
  }

  const addMutation = useMutation({
    mutationFn: () => api.addGroupMembers(groupId!, Array.from(selectedIds)),
    onSuccess: () => {
      invalidate()
      setIsAddOpen(false)
      setSelectedIds(new Set())
      toast({ text: t('groups.addedToast', { defaultValue: 'Contracts added to group' }) })
    },
    onError: (err: Error) => toast({ text: err.message || t('groups.addFailed'), error: true }),
  })

  const removeMutation = useMutation({
    mutationFn: (contractId: string) => api.removeGroupMember(groupId!, contractId),
    onSuccess: () => {
      invalidate()
      toast({
        text: t('groups.removedToast', {
          defaultValue: 'Removed from group. The contract itself is untouched.',
        }),
      })
    },
    onError: (err: Error) => toast({ text: err.message || t('groups.removeFailed'), error: true }),
  })

  const findingMutation = useMutation({
    mutationFn: ({ findingId, status }: { findingId: string; status: 'open' | 'dismissed' }) =>
      api.updateGroupFinding(groupId!, findingId, status),
    onSuccess: invalidate,
    onError: (err: Error) => toast({ text: err.message || t('groups.findingUpdateFailed'), error: true }),
  })

  const deleteMutation = useMutation({
    // auto_family groups are derived from contract links: deleting them also
    // dissolves those links (confirm dialog says so), else the sync re-creates them
    mutationFn: () => api.deleteGroup(groupId!, group?.group_type === 'auto_family'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract-groups'] })
      queryClient.invalidateQueries({ queryKey: ['contract-hierarchy'] })
      queryClient.invalidateQueries({ queryKey: ['contract-links'] })
      queryClient.invalidateQueries({ queryKey: ['suggested-links'] })
      navigate('/groups')
    },
    onError: (err: Error) => {
      setIsDeleteOpen(false)
      toast({ text: err.message || t('groups.deleteFailed'), error: true })
    },
  })

  if (isLoading || !group) {
    return (
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const memberIds = new Set(group.members.map((m) => m.contract_id))
  const candidateList = (candidates?.items ?? candidates ?? []) as Array<{
    id: string
    filename: string
    counterparty?: string | null
  }>
  const availableCandidates = candidateList.filter((c) => !memberIds.has(c.id))

  const toggleCandidate = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const memberColumns: TableColumn<ContractGroupMemberEntry>[] = [
    {
      key: 'contract',
      header: t('groups.colContract'),
      sortable: true,
      sortValue: (m) => m.filename.toLowerCase(),
      render: (m) => (
        <Link
          to={`/contracts/${m.contract_id}`}
          onClick={(e) => e.stopPropagation()}
          className="trunc"
          style={{ display: 'block', maxWidth: 320, fontWeight: 500, color: 'inherit' }}
        >
          {m.filename}
        </Link>
      ),
    },
    {
      key: 'counterparty',
      header: t('groups.colCounterparty'),
      sortable: true,
      sortValue: (m) => m.counterparty,
      render: (m) => (
        <span className="muted trunc" style={{ display: 'block', maxWidth: 200 }}>{m.counterparty || '—'}</span>
      ),
    },
    {
      key: 'type',
      header: t('groups.colType'),
      sortable: true,
      nowrap: true,
      sortValue: (m) => m.contract_type,
      render: (m) => <span className="muted">{m.contract_type || '—'}</span>,
    },
    {
      key: 'expires',
      header: t('groups.colExpires'),
      sortable: true,
      align: 'right',
      nowrap: true,
      sortValue: (m) => m.expiration_date,
      render: (m) => (
        <span className="num">{m.expiration_date ? formatDate(m.expiration_date) : '—'}</span>
      ),
    },
    {
      key: 'source',
      header: t('groups.colSource'),
      width: 130,
      sortable: true,
      sortValue: (m) => m.source,
      render: (m) => (
        <Pill tone={SOURCE_TONE[m.source] ?? 'n'}>
          {t(SOURCE_LABEL_KEYS[m.source] ?? 'groups.sourceManual')}
        </Pill>
      ),
    },
    ...(canWrite
      ? ([
          {
            key: 'actions',
            width: 50,
            align: 'right',
            header: '',
            render: (m) => (
              <IconButton
                icon={XMarkIcon}
                label={t('groups.removeFromGroup')}
                size="sm"
                onClick={(e) => {
                  e.stopPropagation()
                  removeMutation.mutate(m.contract_id)
                }}
              />
            ),
          },
        ] as TableColumn<ContractGroupMemberEntry>[])
      : []),
  ]

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Back link + header */}
      <div>
        <Link
          to="/groups"
          className="row"
          style={{ gap: 4, width: 'fit-content', fontSize: 'var(--fs-sm)', color: 'var(--m)' }}
        >
          <ArrowLeftIcon style={{ width: 14, height: 14 }} aria-hidden />
          {t('groups.backToGroups')}
        </Link>
        <div className="row" style={{ alignItems: 'flex-start', gap: 12, flexWrap: 'wrap', marginTop: 10 }}>
          <div className="grow" style={{ minWidth: 240 }}>
            <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
              <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>{group.name}</h1>
              <GroupTypeBadge groupType={group.group_type} />
            </div>
            {group.description && (
              <p className="muted" style={{ marginTop: 4, fontSize: 'var(--fs-md)' }}>{group.description}</p>
            )}
            <div className="row" style={{ gap: 14, flexWrap: 'wrap', marginTop: 8, fontSize: 'var(--fs-sm)', color: 'var(--m)' }}>
              <span className="num">{t('groups.memberCount', { count: group.member_count })}</span>
              {group.owner_name && (
                <span>
                  {t('groups.owner')}: <b style={{ fontWeight: 600 }}>{group.owner_name}</b>
                </span>
              )}
              <span className="faint">
                {t('groups.updated')} {formatDate(group.updated_at)}
              </span>
            </div>
          </div>
          {canWrite && (
            <div className="row" style={{ gap: 8 }}>
              <Button variant="secondary" icon={PlusIcon} onClick={() => setIsAddOpen(true)}>
                {t('groups.addContracts')}
              </Button>
              <Button variant="danger-ghost" icon={TrashIcon} onClick={() => setIsDeleteOpen(true)}>
                {t('common.delete')}
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Cross-document findings */}
      {group.findings.length > 0 && (() => {
        // One row per (reference, status); identical references from several
        // documents collapse together with their sources listed.
        const aggregated = new Map<string, { label: string; status: string; ids: string[]; sources: string[] }>()
        for (const f of group.findings) {
          const key = `${f.reference_label}|${f.status}`
          const entry = aggregated.get(key) ?? { label: f.reference_label, status: f.status, ids: [], sources: [] }
          entry.ids.push(f.id)
          if (f.contract_filename && !entry.sources.includes(f.contract_filename)) {
            entry.sources.push(f.contract_filename)
          }
          aggregated.set(key, entry)
        }
        const rows = Array.from(aggregated.values()).sort((a, b) =>
          a.status === b.status ? a.label.localeCompare(b.label) : a.status === 'open' ? -1 : 1,
        )
        return (
          <div className="card card-p">
            <div className="sec-t" style={{ marginBottom: 10 }}>{t('groups.findingsTitle')}</div>
            <div className="col" style={{ gap: 8 }}>
              {rows.map((row) => (
                <div
                  key={`${row.label}|${row.status}`}
                  className="row"
                  style={{
                    gap: 10,
                    alignItems: 'flex-start',
                    padding: '10px 12px',
                    borderRadius: 'var(--r-md)',
                    border: '1px solid',
                    borderColor: row.status === 'open' ? 'var(--wa-b)' : 'var(--b)',
                    background: row.status === 'open' ? 'var(--wa-f)' : 'var(--s2)',
                  }}
                >
                  <div className="grow">
                    <div
                      style={{
                        fontSize: 'var(--fs-md)',
                        lineHeight: 1.5,
                        color: row.status === 'open' ? 'var(--t)' : 'var(--f)',
                      }}
                    >
                      {row.status === 'open'
                        ? t('groups.findingMissing', { label: row.label })
                        : row.status === 'resolved'
                          ? t('groups.findingResolved', { label: row.label })
                          : t('groups.findingDismissed', { label: row.label })}
                    </div>
                    {row.sources.length > 0 && (
                      <div className="faint" style={{ marginTop: 2, fontSize: 'var(--fs-sm)' }}>
                        {t('groups.findingSources', { count: row.sources.length })}{' '}
                        {row.sources.slice(0, 3).join(', ')}
                        {row.sources.length > 3 && ` +${row.sources.length - 3}`}
                      </div>
                    )}
                  </div>
                  {canWrite && row.status !== 'resolved' && (
                    <Button
                      variant="ghost"
                      size="sm"
                      style={{ flexShrink: 0 }}
                      onClick={() => {
                        const next = row.status === 'open' ? 'dismissed' as const : 'open' as const
                        row.ids.forEach((id) => findingMutation.mutate({ findingId: id, status: next }))
                      }}
                    >
                      {row.status === 'open' ? t('groups.dismiss') : t('groups.reopen')}
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )
      })()}

      {/* Sub-groups */}
      {group.child_groups.length > 0 && (
        <div className="card card-p">
          <div className="sec-t" style={{ marginBottom: 10 }}>{t('groups.subGroups')}</div>
          <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
            {group.child_groups.map((child) => (
              <Link
                key={child.id}
                to={`/groups/${child.id}`}
                className="row"
                style={{
                  gap: 8,
                  padding: '6px 12px',
                  border: '1px solid var(--b)',
                  borderRadius: 'var(--r-md)',
                  background: 'var(--s)',
                  fontSize: 'var(--fs-md)',
                  color: 'inherit',
                }}
              >
                <FolderIcon style={{ width: 14, height: 14, color: 'var(--f)' }} aria-hidden />
                {child.name}
                <span className="faint num" style={{ fontSize: 'var(--fs-sm)' }}>
                  {t('groups.memberCount', { count: child.member_count })}
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Members table */}
      <div>
        <div className="sec-t" style={{ marginBottom: 8 }}>
          {t('groups.membersTitle', { count: group.member_count, defaultValue: 'Members ({{count}})' })}
        </div>
        <Table<ContractGroupMemberEntry>
          columns={memberColumns}
          rows={group.members}
          rowKey={(m) => m.member_id}
          onRowClick={(m) => navigate(`/contracts/${m.contract_id}`)}
          minWidth={720}
          empty={
            <EmptyState
              icon={DocumentTextIcon}
              title={t('groups.noMembers')}
              body={t('groups.noMembersBody', {
                defaultValue: 'Add contracts to track cross-document completeness across this group.',
              })}
              action={
                canWrite ? (
                  <Button variant="primary" size="sm" icon={PlusIcon} onClick={() => setIsAddOpen(true)}>
                    {t('groups.addContracts')}
                  </Button>
                ) : undefined
              }
            />
          }
        />
      </div>

      {/* Delete confirmation */}
      <ConfirmDialog
        open={isDeleteOpen}
        title={t('groups.deleteGroupTitle')}
        body={
          group.group_type === 'auto_family'
            ? t('groups.deleteConfirmFamily', { name: group.name })
            : t('groups.deleteConfirmSimple', { name: group.name })
        }
        affected={[
          t('groups.affectedGroup', { defaultValue: 'This group and its membership records' }),
          ...(group.group_type === 'auto_family'
            ? [t('groups.affectedLinks', { defaultValue: 'The hierarchy links between its members, so the family is not re-created' })]
            : []),
        ]}
        safe={[
          t('groups.safeContracts', { defaultValue: 'The contracts themselves — contracts are never deleted' }),
          t('groups.safeData', { defaultValue: 'Extracted metadata, clauses, risks and obligations' }),
        ]}
        confirmLabel={deleteMutation.isPending ? t('common.deleting') : t('common.delete')}
        cancelLabel={t('common.cancel')}
        onCancel={() => { if (!deleteMutation.isPending) setIsDeleteOpen(false) }}
        onConfirm={() => { if (!deleteMutation.isPending) deleteMutation.mutate() }}
      />

      {/* Add-contracts drawer */}
      <Drawer
        open={isAddOpen}
        title={t('groups.addContracts')}
        sub={group.name}
        onClose={() => setIsAddOpen(false)}
        width={480}
        footer={
          <>
            <span className="grow" />
            <Button variant="ghost" onClick={() => setIsAddOpen(false)}>{t('common.cancel')}</Button>
            <Button
              variant="primary"
              disabled={selectedIds.size === 0 || addMutation.isPending}
              onClick={() => addMutation.mutate()}
            >
              {t('groups.addSelected', { count: selectedIds.size })}
            </Button>
          </>
        }
      >
        <div className="col" style={{ gap: 12 }}>
          <Field
            icon={MagnifyingGlassIcon}
            placeholder={t('groups.searchContracts')}
            value={contractSearch}
            autoFocus
            onChange={(e) => setContractSearch(e.target.value)}
          />
          {availableCandidates.length === 0 ? (
            <p className="faint" style={{ fontSize: 'var(--fs-sm)', padding: '8px 2px' }}>
              {t('groups.noCandidates', { defaultValue: 'No matching contracts outside this group.' })}
            </p>
          ) : (
            <div className="col" style={{ gap: 2 }}>
              {availableCandidates.map((c) => (
                <div
                  key={c.id}
                  className="row"
                  style={{ gap: 10, padding: '8px 10px', borderRadius: 'var(--r-sm)', cursor: 'pointer' }}
                  onClick={() => toggleCandidate(c.id)}
                >
                  <Checkbox checked={selectedIds.has(c.id)} onChange={() => toggleCandidate(c.id)} />
                  <span className="grow trunc" style={{ fontSize: 'var(--fs-md)' }}>
                    {c.filename}
                    {c.counterparty && <span className="faint"> — {c.counterparty}</span>}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </Drawer>
    </div>
  )
}
