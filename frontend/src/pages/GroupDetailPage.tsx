import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  FolderIcon,
  PlusIcon,
  TrashIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn, formatDate } from '@/lib/utils'
import { GroupTypeBadge } from '@/pages/GroupsPage'

const SOURCE_LABEL_KEYS: Record<string, string> = {
  manual: 'groups.sourceManual',
  upload_batch: 'groups.sourceUploadBatch',
  auto_family: 'groups.sourceAutoFamily',
}

export default function GroupDetailPage() {
  const { t } = useTranslation()
  const { groupId } = useParams<{ groupId: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [isAddOpen, setIsAddOpen] = useState(false)
  const [contractSearch, setContractSearch] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [actionError, setActionError] = useState<string | null>(null)

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
      setActionError(null)
    },
    onError: (err: Error) => setActionError(err.message || t('groups.addFailed')),
  })

  const removeMutation = useMutation({
    mutationFn: (contractId: string) => api.removeGroupMember(groupId!, contractId),
    onSuccess: invalidate,
    onError: (err: Error) => setActionError(err.message || t('groups.removeFailed')),
  })

  const findingMutation = useMutation({
    mutationFn: ({ findingId, status }: { findingId: string; status: 'open' | 'dismissed' }) =>
      api.updateGroupFinding(groupId!, findingId, status),
    onSuccess: invalidate,
    onError: (err: Error) => setActionError(err.message || t('groups.findingUpdateFailed')),
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteGroup(groupId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract-groups'] })
      navigate('/groups')
    },
    onError: (err: Error) => setActionError(err.message || t('groups.deleteFailed')),
  })

  if (isLoading || !group) return <LoadingSpinner size="lg" />

  const memberIds = new Set(group.members.map((m) => m.contract_id))
  const candidateList = (candidates?.items ?? candidates ?? []) as Array<{
    id: string
    filename: string
    counterparty?: string | null
  }>

  return (
    <div className="space-y-6">
      <div>
        <Link to="/groups" className="mb-2 inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
          <ArrowLeftIcon className="h-4 w-4" />
          {t('groups.backToGroups')}
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-3">
              <FolderIcon className="h-7 w-7 text-violet-600" />
              <h1 className="text-2xl font-bold text-gray-900">{group.name}</h1>
              <GroupTypeBadge groupType={group.group_type} />
            </div>
            {group.description && <p className="mt-1 text-gray-500">{group.description}</p>}
            <div className="mt-2 flex flex-wrap gap-4 text-sm text-gray-600">
              <span>{t('groups.memberCount', { count: group.member_count })}</span>
              {group.owner_name && (
                <span>
                  {t('groups.owner')}: <span className="font-medium">{group.owner_name}</span>
                </span>
              )}
              <span>
                {t('groups.updated')} {formatDate(group.updated_at)}
              </span>
            </div>
          </div>
          {canWrite && (
            <div className="flex gap-2">
              <button className="btn-secondary" onClick={() => setIsAddOpen(true)}>
                <PlusIcon className="mr-1 h-5 w-5" />
                {t('groups.addContracts')}
              </button>
              {group.group_type !== 'auto_family' && (
                <button
                  className="rounded-lg border border-red-200 px-3 py-2 text-red-600 hover:bg-red-50"
                  onClick={() => {
                    if (window.confirm(t('groups.deleteConfirm'))) deleteMutation.mutate()
                  }}
                >
                  <TrashIcon className="h-5 w-5" />
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {actionError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {actionError}
        </div>
      )}

      {group.findings.length > 0 && (
        <div className="card p-5">
          <h2 className="mb-3 font-semibold text-gray-900">{t('groups.findingsTitle')}</h2>
          <ul className="space-y-2">
            {group.findings.map((finding) => (
              <li
                key={finding.id}
                className={cn(
                  'flex items-center justify-between gap-3 rounded-lg border px-4 py-3 text-sm',
                  finding.status === 'open'
                    ? 'border-amber-200 bg-amber-50'
                    : 'border-gray-100 bg-gray-50 text-gray-400',
                )}
              >
                <span>
                  {finding.status === 'open'
                    ? t('groups.findingMissing', { label: finding.reference_label })
                    : finding.status === 'resolved'
                      ? t('groups.findingResolved', { label: finding.reference_label })
                      : t('groups.findingDismissed', { label: finding.reference_label })}
                </span>
                {canWrite && finding.status !== 'resolved' && (
                  <button
                    className="whitespace-nowrap text-xs font-medium text-gray-500 hover:text-gray-800"
                    onClick={() =>
                      findingMutation.mutate({
                        findingId: finding.id,
                        status: finding.status === 'open' ? 'dismissed' : 'open',
                      })
                    }
                  >
                    {finding.status === 'open' ? t('groups.dismiss') : t('groups.reopen')}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {group.child_groups.length > 0 && (
        <div className="card p-5">
          <h2 className="mb-3 font-semibold text-gray-900">{t('groups.subGroups')}</h2>
          <div className="flex flex-wrap gap-2">
            {group.child_groups.map((child) => (
              <Link
                key={child.id}
                to={`/groups/${child.id}`}
                className="inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm hover:bg-gray-50"
              >
                <FolderIcon className="h-4 w-4 text-gray-400" />
                {child.name}
                <span className="text-xs text-gray-400">
                  {t('groups.memberCount', { count: child.member_count })}
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}

      <div className="card overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                {t('groups.colContract')}
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                {t('groups.colCounterparty')}
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                {t('groups.colType')}
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                {t('groups.colExpires')}
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                {t('groups.colSource')}
              </th>
              {canWrite && <th className="px-4 py-3" />}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {group.members.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-gray-500">
                  {t('groups.noMembers')}
                </td>
              </tr>
            ) : (
              group.members.map((member) => (
                <tr key={member.member_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link
                      to={`/contracts/${member.contract_id}`}
                      className="font-medium text-violet-700 hover:underline"
                    >
                      {member.filename}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{member.counterparty || '—'}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{member.contract_type || '—'}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {member.expiration_date ? formatDate(member.expiration_date) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        'rounded-full px-2 py-0.5 text-xs',
                        member.source === 'auto_family'
                          ? 'bg-emerald-50 text-emerald-700'
                          : 'bg-gray-100 text-gray-600',
                      )}
                    >
                      {t(SOURCE_LABEL_KEYS[member.source] ?? 'groups.sourceManual')}
                    </span>
                  </td>
                  {canWrite && (
                    <td className="px-4 py-3 text-right">
                      <button
                        className="text-gray-400 hover:text-red-600"
                        title={t('groups.removeFromGroup')}
                        onClick={() => removeMutation.mutate(member.contract_id)}
                      >
                        <XMarkIcon className="h-5 w-5" />
                      </button>
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {isAddOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="flex max-h-[80vh] w-full max-w-lg flex-col rounded-xl bg-white p-6 shadow-xl">
            <h2 className="mb-4 text-lg font-semibold">{t('groups.addContracts')}</h2>
            <input
              className="input mb-3"
              placeholder={t('groups.searchContracts')}
              value={contractSearch}
              onChange={(e) => setContractSearch(e.target.value)}
            />
            <div className="flex-1 space-y-1 overflow-y-auto">
              {candidateList
                .filter((c) => !memberIds.has(c.id))
                .map((c) => (
                  <label
                    key={c.id}
                    className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 hover:bg-gray-50"
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.has(c.id)}
                      onChange={(e) => {
                        const next = new Set(selectedIds)
                        if (e.target.checked) next.add(c.id)
                        else next.delete(c.id)
                        setSelectedIds(next)
                      }}
                    />
                    <span className="text-sm">
                      {c.filename}
                      {c.counterparty && <span className="text-gray-400"> — {c.counterparty}</span>}
                    </span>
                  </label>
                ))}
            </div>
            <div className="mt-4 flex justify-end gap-3 border-t pt-4">
              <button
                className="rounded-lg px-4 py-2 text-gray-700 hover:bg-gray-100"
                onClick={() => setIsAddOpen(false)}
              >
                {t('common.cancel')}
              </button>
              <button
                className="btn-primary"
                disabled={selectedIds.size === 0 || addMutation.isPending}
                onClick={() => addMutation.mutate()}
              >
                {t('groups.addSelected', { count: selectedIds.size })}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
