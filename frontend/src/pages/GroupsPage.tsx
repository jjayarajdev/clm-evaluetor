import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  FolderIcon,
  FolderPlusIcon,
  MagnifyingGlassIcon,
  SparklesIcon,
  ArrowUpTrayIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import PageHeader from '@/components/ui/PageHeader'
import { cn, formatDate } from '@/lib/utils'
import type { ContractGroupResponse } from '@/lib/api/contracts'

const TYPE_BADGES: Record<string, { labelKey: string; icon: typeof FolderIcon; className: string }> = {
  manual: { labelKey: 'groups.typeManual', icon: FolderIcon, className: 'bg-blue-50 text-blue-700' },
  upload_batch: { labelKey: 'groups.typeUploadBatch', icon: ArrowUpTrayIcon, className: 'bg-violet-50 text-violet-700' },
  auto_family: { labelKey: 'groups.typeAutoFamily', icon: SparklesIcon, className: 'bg-emerald-50 text-emerald-700' },
}

export function GroupTypeBadge({ groupType }: { groupType: string }) {
  const { t } = useTranslation()
  const badge = TYPE_BADGES[groupType] ?? TYPE_BADGES.manual
  const Icon = badge.icon
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium', badge.className)}>
      <Icon className="h-3.5 w-3.5" />
      {t(badge.labelKey)}
    </span>
  )
}

export default function GroupsPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>('')
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

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

  const createMutation = useMutation({
    mutationFn: () =>
      api.createGroup({ name: newName, description: newDescription || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract-groups'] })
      setIsCreateOpen(false)
      setNewName('')
      setNewDescription('')
      setFormError(null)
    },
    onError: (err: Error) => setFormError(err.message || t('groups.createFailed')),
  })

  const groups = data?.items ?? []

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('groups.title')}
        description={t('groups.subtitle')}
        actions={
          canWrite ? (
            <button className="btn-primary" onClick={() => setIsCreateOpen(true)}>
              <FolderPlusIcon className="mr-2 h-5 w-5" />
              {t('groups.newGroup')}
            </button>
          ) : undefined
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative">
          <MagnifyingGlassIcon className="pointer-events-none absolute left-3 top-2.5 h-5 w-5 text-gray-400" />
          <input
            className="input pl-10"
            placeholder={t('groups.searchPlaceholder')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="input w-auto"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
        >
          <option value="">{t('groups.allTypes')}</option>
          <option value="manual">{t('groups.typeManual')}</option>
          <option value="upload_batch">{t('groups.typeUploadBatch')}</option>
          <option value="auto_family">{t('groups.typeAutoFamily')}</option>
        </select>
      </div>

      {isLoading ? (
        <LoadingSpinner size="lg" />
      ) : groups.length === 0 ? (
        <div className="card py-16 text-center text-gray-500">
          <FolderIcon className="mx-auto mb-3 h-12 w-12 text-gray-300" />
          {t('groups.empty')}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {groups.map((group: ContractGroupResponse) => (
            <Link
              key={group.id}
              to={`/groups/${group.id}`}
              className="card block p-5 transition-shadow hover:shadow-md"
            >
              <div className="mb-2 flex items-start justify-between gap-2">
                <h3 className="font-semibold text-gray-900">{group.name}</h3>
                <GroupTypeBadge groupType={group.group_type} />
              </div>
              {group.description && (
                <p className="mb-3 line-clamp-2 text-sm text-gray-500">{group.description}</p>
              )}
              <div className="flex items-center gap-4 text-sm text-gray-600">
                <span>{t('groups.memberCount', { count: group.member_count })}</span>
                {group.open_finding_count > 0 && (
                  <span className="inline-flex items-center gap-1 text-amber-600">
                    <ExclamationTriangleIcon className="h-4 w-4" />
                    {t('groups.openFindings', { count: group.open_finding_count })}
                  </span>
                )}
              </div>
              <div className="mt-3 text-xs text-gray-400">
                {t('groups.updated')} {formatDate(group.updated_at)}
              </div>
            </Link>
          ))}
        </div>
      )}

      {isCreateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h2 className="mb-4 text-lg font-semibold">{t('groups.newGroup')}</h2>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                createMutation.mutate()
              }}
              className="space-y-4"
            >
              <div>
                <label className="label">{t('groups.name')}</label>
                <input
                  className="input"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  required
                  minLength={1}
                  maxLength={255}
                />
              </div>
              <div>
                <label className="label">{t('groups.description')}</label>
                <textarea
                  className="input"
                  rows={2}
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                />
              </div>
              {formError && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {formError}
                </div>
              )}
              <div className="flex justify-end gap-3 border-t pt-4">
                <button
                  type="button"
                  className="rounded-lg px-4 py-2 text-gray-700 hover:bg-gray-100"
                  onClick={() => setIsCreateOpen(false)}
                >
                  {t('common.cancel')}
                </button>
                <button type="submit" className="btn-primary" disabled={createMutation.isPending}>
                  {createMutation.isPending ? t('common.saving') : t('common.create')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
