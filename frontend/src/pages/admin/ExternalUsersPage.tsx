/* External users admin — Direction B redesign.
   Header + search Field → Table (Avatar rows, company Tags, status Pills,
   access activity) → invite/edit in a Drawer → deactivation via ConfirmDialog
   stating exactly what is and is not affected. Queries, mutations
   (create/update/deactivate), search behavior and i18n are unchanged from the
   pre-redesign page. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  BuildingOfficeIcon,
  ExclamationCircleIcon,
  MagnifyingGlassIcon,
  PencilSquareIcon,
  PlusIcon,
  TrashIcon,
  UserIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import {
  Avatar,
  Button,
  ConfirmDialog,
  Drawer,
  EmptyState,
  Field,
  IconButton,
  Pill,
  Table,
  Tag,
  useToast,
} from '@/components/ui'
import type { TableColumn } from '@/components/ui'

interface ExternalUser {
  id: string
  email: string
  full_name?: string
  company_name?: string
  title?: string
  phone?: string
  is_active: boolean
  invited_at?: string
  last_access_at?: string
  access_count: number
  created_at: string
}

interface FormData {
  email: string
  full_name: string
  company_name: string
  title: string
  phone: string
}

const emptyFormData: FormData = {
  email: '',
  full_name: '',
  company_name: '',
  title: '',
  phone: '',
}

const FORM_ID = 'external-user-form'

export default function ExternalUsersPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [formData, setFormData] = useState<FormData>(emptyFormData)
  const [search, setSearch] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<ExternalUser | null>(null)

  // Fetch external users
  const { data, isLoading, error: fetchError } = useQuery({
    queryKey: ['external-users', search],
    queryFn: () => api.getExternalUsers({ page_size: 100, search: search || undefined }),
  })

  const [formError, setFormError] = useState<string | null>(null)

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: FormData) => api.createExternalUser(data),
    onSuccess: (_res, variables) => {
      queryClient.invalidateQueries({ queryKey: ['external-users'] })
      closeDrawer()
      setFormError(null)
      toast({ text: t('externalUsers.createdToast', { defaultValue: '{{name}} added', name: variables.full_name || variables.email }) })
    },
    onError: (err: Error) => {
      setFormError(err.message || t('externalUsers.createFailed'))
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<FormData> }) =>
      api.updateExternalUser(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['external-users'] })
      closeDrawer()
      setFormError(null)
      toast({ text: t('externalUsers.updatedToast', { defaultValue: 'External user updated' }) })
    },
    onError: (err: Error) => {
      setFormError(err.message || t('externalUsers.updateFailed'))
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteExternalUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['external-users'] })
      const name = deleteTarget ? deleteTarget.full_name || deleteTarget.email : ''
      setDeleteTarget(null)
      toast({ text: t('externalUsers.deactivatedToast', { defaultValue: '{{name}} deactivated', name }) })
    },
    onError: (err: Error) => {
      setDeleteTarget(null)
      toast({ text: err.message || t('externalUsers.deleteFailed'), error: true })
    },
  })

  const openCreateDrawer = () => {
    setEditingId(null)
    setFormData(emptyFormData)
    setFormError(null)
    setIsDrawerOpen(true)
  }

  const openEditDrawer = (user: ExternalUser) => {
    setEditingId(user.id)
    setFormData({
      email: user.email,
      full_name: user.full_name || '',
      company_name: user.company_name || '',
      title: user.title || '',
      phone: user.phone || '',
    })
    setFormError(null)
    setIsDrawerOpen(true)
  }

  const closeDrawer = () => {
    setIsDrawerOpen(false)
    setEditingId(null)
    setFormData(emptyFormData)
    setFormError(null)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (editingId) {
      updateMutation.mutate({ id: editingId, data: formData })
    } else {
      createMutation.mutate(formData)
    }
  }

  const isSaving = createMutation.isPending || updateMutation.isPending

  const columns: TableColumn<ExternalUser>[] = [
    {
      key: 'user',
      header: t('externalUsers.user'),
      sortable: true,
      sortValue: (u) => u.full_name || u.email,
      render: (u) => (
        <span className="row" style={{ gap: 10 }}>
          <Avatar name={u.full_name || u.email} size={28} />
          <span style={{ minWidth: 0 }}>
            <span className="trunc" style={{ display: 'block', fontWeight: 500 }}>
              {u.full_name || t('externalUsers.noName')}
            </span>
            <span className="faint trunc" style={{ display: 'block', fontSize: 'var(--fs-sm)' }}>
              {u.email}
            </span>
          </span>
        </span>
      ),
    },
    {
      key: 'company',
      header: t('externalUsers.company'),
      sortable: true,
      sortValue: (u) => u.company_name ?? '',
      render: (u) => (
        <span style={{ minWidth: 0 }}>
          {u.company_name ? (
            <Tag icon={BuildingOfficeIcon}>{u.company_name}</Tag>
          ) : (
            <span className="faint">-</span>
          )}
          {u.title && (
            <span className="faint trunc" style={{ display: 'block', fontSize: 'var(--fs-sm)', marginTop: 2 }}>
              {u.title}
            </span>
          )}
        </span>
      ),
    },
    {
      key: 'status',
      header: t('common.status'),
      width: 104,
      sortable: true,
      sortValue: (u) => (u.is_active ? 0 : 1),
      render: (u) => (
        <Pill tone={u.is_active ? 'ok' : 'da'}>
          {u.is_active ? t('status.active') : t('status.inactive')}
        </Pill>
      ),
    },
    {
      key: 'activity',
      header: t('externalUsers.activity'),
      width: 140,
      sortable: true,
      sortValue: (u) => u.access_count,
      render: (u) =>
        u.access_count > 0 ? (
          <span className="muted num" style={{ fontSize: 'var(--fs-sm)' }}>
            {t('externalUsers.accessCount', { count: u.access_count })}
          </span>
        ) : (
          <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
            {t('externalUsers.neverAccessed')}
          </span>
        ),
    },
    {
      key: 'actions',
      header: '',
      width: 80,
      align: 'right',
      render: (u) => (
        <span className="row" style={{ gap: 4, justifyContent: 'flex-end' }}>
          <IconButton
            icon={PencilSquareIcon}
            size="sm"
            label={t('common.edit')}
            onClick={() => openEditDrawer(u)}
          />
          <IconButton
            icon={TrashIcon}
            size="sm"
            label={t('common.delete')}
            disabled={deleteMutation.isPending}
            onClick={() => setDeleteTarget(u)}
          />
        </span>
      ),
    },
  ]

  if (isLoading) {
    return (
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className="banner banner-da">
        <ExclamationCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
        <span>{t('externalUsers.loadFailed')}</span>
      </div>
    )
  }

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div className="row" style={{ alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>
            {t('nav.externalUsers')}
          </h1>
          <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>
            {t('externalUsers.subtitle')}
          </p>
        </div>
        <Button variant="primary" icon={PlusIcon} onClick={openCreateDrawer}>
          {t('externalUsers.addExternalUser')}
        </Button>
      </div>

      {/* Search */}
      <Field
        type="text"
        icon={MagnifyingGlassIcon}
        placeholder={t('externalUsers.searchPlaceholder')}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        containerStyle={{ maxWidth: 380 }}
      />

      {/* Users list */}
      <Table
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(u) => u.id}
        minWidth={720}
        empty={
          <EmptyState
            icon={UserIcon}
            title={t('externalUsers.noUsers')}
            body={t('externalUsers.noUsersHint')}
            action={
              <Button variant="primary" size="sm" icon={PlusIcon} onClick={openCreateDrawer}>
                {t('externalUsers.addExternalUser')}
              </Button>
            }
          />
        }
      />

      {/* Invite / edit drawer */}
      <Drawer
        open={isDrawerOpen}
        title={editingId ? t('externalUsers.editExternalUser') : t('externalUsers.addExternalUser')}
        onClose={closeDrawer}
        width={440}
        footer={
          <>
            <Button variant="ghost" onClick={closeDrawer}>
              {t('common.cancel')}
            </Button>
            <span className="grow" />
            <Button variant="primary" type="submit" form={FORM_ID} disabled={isSaving}>
              {isSaving
                ? t('externalUsers.saving')
                : editingId
                  ? t('externalUsers.update')
                  : t('externalUsers.create')}
            </Button>
          </>
        }
      >
        <form id={FORM_ID} onSubmit={handleSubmit} className="col" style={{ gap: 14 }}>
          {formError && (
            <div className="banner banner-da">
              <ExclamationCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
              <span>{formError}</span>
            </div>
          )}
          <Field
            label={`${t('externalUsers.email')} *`}
            type="email"
            autoFocus
            required
            value={formData.email}
            placeholder={t('externalUsers.emailPlaceholder')}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
          />
          <Field
            label={t('externalUsers.fullName')}
            type="text"
            value={formData.full_name}
            placeholder={t('externalUsers.fullNamePlaceholder')}
            onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
          />
          <Field
            label={t('externalUsers.company')}
            type="text"
            value={formData.company_name}
            placeholder={t('externalUsers.companyPlaceholder')}
            onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
          />
          <Field
            label={t('externalUsers.title')}
            type="text"
            value={formData.title}
            placeholder={t('externalUsers.titlePlaceholder')}
            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
          />
          <Field
            label={t('externalUsers.phone')}
            type="tel"
            value={formData.phone}
            placeholder={t('externalUsers.phonePlaceholder')}
            onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
          />
        </form>
      </Drawer>

      {/* Deactivation — replaces the old window.confirm, states consequences */}
      <ConfirmDialog
        open={deleteTarget != null}
        tone="warn"
        title={t('externalUsers.confirmDeactivate', {
          name: deleteTarget ? deleteTarget.full_name || deleteTarget.email : '',
        })}
        body={t('externalUsers.deactivateBody', {
          defaultValue: 'This external user loses access to everything shared with them.',
        })}
        affected={[
          t('externalUsers.deactivateAffectsAccess', {
            defaultValue: 'Their share links stop working — they can no longer open contracts shared with them',
          }),
        ]}
        safe={[
          t('externalUsers.deactivateSafeData', {
            defaultValue: 'Their record, access history and existing share entries stay intact',
          }),
          t('externalUsers.deactivateSafeReinvite', {
            defaultValue: 'Nothing permanently — they can be invited again at any time',
          }),
        ]}
        confirmLabel={t('externalUsers.deactivate', { defaultValue: 'Deactivate' })}
        cancelLabel={t('common.cancel')}
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
