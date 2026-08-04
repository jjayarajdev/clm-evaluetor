/* Users administration — Direction B redesign.
   Header + count line → sortable Table (Avatar rows, role Pills, BU Tags,
   active/inactive status) → create/edit in a Drawer, delete via ConfirmDialog.
   Queries, mutations (create, update + dedicated password endpoint, delete),
   business-unit scoping rules and form validation are unchanged from the
   pre-redesign page. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ExclamationCircleIcon,
  PencilSquareIcon,
  PlusIcon,
  RectangleGroupIcon,
  ShieldCheckIcon,
  TrashIcon,
  UserGroupIcon,
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
  Select,
  Table,
  Tag,
  Tooltip,
  useToast,
} from '@/components/ui'
import type { PillTone, TableColumn } from '@/components/ui'
import { formatDate } from '@/lib/utils'
import type { User, Role } from '@/types'
import type { BusinessUnit } from '@/types/business-unit'

const ROLE_LABELS: Record<Role, string> = {
  admin: 'Administrator',
  legal: 'Legal',
  procurement: 'Procurement',
  viewer: 'Viewer',
  super_admin: 'Super Admin',
  bu_head: 'BU Head',
}

/* Same hue mapping as the legacy badge colors: purple/blue/green/gray/rose/amber. */
const ROLE_TONES: Record<Role, PillTone> = {
  admin: 'p',
  legal: 'in',
  procurement: 'ok',
  viewer: 'n',
  super_admin: 'da',
  bu_head: 'wa',
}

interface UserFormData {
  username: string
  email: string
  first_name: string
  last_name: string
  job_title: string
  phone: string
  department: string
  role: Role
  password?: string
  business_unit_id?: string
}

const EMPTY_PROFILE = {
  first_name: '',
  last_name: '',
  job_title: '',
  phone: '',
  department: '',
}

const FORM_ID = 'user-form'

export default function UsersPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [formData, setFormData] = useState<UserFormData>({
    email: '',
    username: '',
    role: 'viewer',
    password: '',
    ...EMPTY_PROFILE,
  })

  const { data: users, isLoading, error } = useQuery({
    queryKey: ['users'],
    queryFn: () => api.getUsers(),
  })

  const { data: businessUnitsData } = useQuery({
    queryKey: ['business-units'],
    queryFn: () => api.getBusinessUnits({ page: 1, page_size: 100 }),
  })

  const businessUnits: BusinessUnit[] = businessUnitsData?.items ?? []
  const activeBusinessUnits = businessUnits.filter((bu) => bu.is_active)

  // Log error for debugging
  if (error) {
    console.error('Error fetching users:', error)
  }

  const createMutation = useMutation({
    mutationFn: (data: UserFormData) => api.createUser({
      username: data.username,
      email: data.email,
      first_name: data.first_name || undefined,
      last_name: data.last_name || undefined,
      job_title: data.job_title || undefined,
      phone: data.phone || undefined,
      department: data.department || undefined,
      password: data.password || '',
      role: data.role,
      business_unit_id: data.business_unit_id || undefined,
    }),
    onSuccess: (_res, variables) => {
      setFormError(null)
      queryClient.invalidateQueries({ queryKey: ['users'] })
      closeDrawer()
      toast({ text: t('users.createdToast', { defaultValue: '{{username}} created', username: variables.username }) })
    },
    onError: (err: any) => {
      setFormError(err?.response?.data?.detail || err?.message || t('users.createFailed'))
    },
  })

  const updateMutation = useMutation({
    mutationFn: async ({ id, data, password }: { id: string; data: Record<string, unknown>; password?: string }) => {
      const updated = await api.updateUser(id, data)
      // Password is NOT part of the user-update payload — it must go through the
      // dedicated endpoint, otherwise the backend silently ignores it.
      if (password) {
        await api.updateUserPassword(id, password)
      }
      return updated
    },
    onSuccess: () => {
      setFormError(null)
      queryClient.invalidateQueries({ queryKey: ['users'] })
      closeDrawer()
      toast({ text: t('users.updatedToast', { defaultValue: 'User updated' }) })
    },
    onError: (err: any) => {
      setFormError(err?.response?.data?.detail || err?.message || t('users.updateFailed'))
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      const name = deleteTarget?.username ?? ''
      setDeleteTarget(null)
      toast({ text: t('users.deletedToast', { defaultValue: '{{username}} deleted', username: name }) })
    },
    onError: (err: any) => {
      setDeleteTarget(null)
      toast({ text: err?.response?.data?.detail || err?.message || t('users.deleteFailed', { defaultValue: 'Failed to delete user' }), error: true })
    },
  })

  const openCreateDrawer = () => {
    setEditingUser(null)
    setFormError(null)
    setFormData({ email: '', username: '', role: 'viewer', password: '', business_unit_id: '', ...EMPTY_PROFILE })
    setIsDrawerOpen(true)
  }

  const openEditDrawer = (user: User) => {
    setEditingUser(user)
    setFormError(null)
    setFormData({
      email: user.email,
      username: user.username,
      first_name: user.first_name || '',
      last_name: user.last_name || '',
      job_title: user.job_title || '',
      phone: user.phone || '',
      department: user.department || '',
      role: user.role,
      password: '',
      business_unit_id: user.business_unit_id || '',
    })
    setIsDrawerOpen(true)
  }

  const closeDrawer = () => {
    setIsDrawerOpen(false)
    setEditingUser(null)
    setFormError(null)
    setFormData({ email: '', username: '', role: 'viewer', password: '', business_unit_id: '', ...EMPTY_PROFILE })
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)
    if (editingUser) {
      const updateData: Record<string, unknown> = {
        email: formData.email,
        username: formData.username,
        first_name: formData.first_name || null,
        last_name: formData.last_name || null,
        job_title: formData.job_title || null,
        phone: formData.phone || null,
        department: formData.department || null,
        role: formData.role,
        business_unit_id: formData.business_unit_id || null,
      }
      // Password goes through the dedicated /password endpoint (below), not the
      // user-update payload — the UserUpdate schema has no password field.
      updateMutation.mutate({
        id: editingUser.id,
        data: updateData,
        password: formData.password || undefined,
      })
    } else {
      createMutation.mutate(formData)
    }
  }

  const roleLabel = (role: Role) => t(`roles.${role}`, { defaultValue: ROLE_LABELS[role] })
  const isSaving = createMutation.isPending || updateMutation.isPending

  const columns: TableColumn<User>[] = [
    {
      key: 'user',
      header: t('users.user'),
      sortable: true,
      sortValue: (u) => u.full_name || u.username,
      render: (u) => (
        <span className="row" style={{ gap: 10 }}>
          <Avatar name={u.full_name || u.username} size={28} />
          <span style={{ minWidth: 0 }}>
            <span className="trunc" style={{ display: 'block', fontWeight: 500 }}>
              {u.full_name || u.username}
            </span>
            <span className="faint trunc" style={{ display: 'block', fontSize: 'var(--fs-sm)' }}>
              {u.full_name ? `${u.username} · ${u.email}` : u.email}
            </span>
            {u.job_title && (
              <span className="faint trunc" style={{ display: 'block', fontSize: 'var(--fs-xs)' }}>
                {u.job_title}
                {u.department ? ` · ${u.department}` : ''}
              </span>
            )}
          </span>
        </span>
      ),
    },
    {
      key: 'role',
      header: t('users.role'),
      width: 140,
      sortable: true,
      sortValue: (u) => u.role,
      render: (u) => (
        <Pill tone={ROLE_TONES[u.role]} dot={false}>
          {u.role === 'admin' && (
            <ShieldCheckIcon style={{ width: 12, height: 12, flexShrink: 0 }} aria-hidden />
          )}
          {roleLabel(u.role)}
        </Pill>
      ),
    },
    {
      key: 'bu',
      header: t('users.businessUnit'),
      width: 150,
      sortable: true,
      sortValue: (u) => u.business_unit_name,
      render: (u) =>
        u.business_unit_name ? (
          <Tag icon={RectangleGroupIcon}>{u.business_unit_name}</Tag>
        ) : (
          <Tooltip label={t('users.buAllUnitsTip', { defaultValue: 'No business unit — sees all units' })}>
            <span className="faint" style={{ fontSize: 'var(--fs-sm)', cursor: 'help' }}>
              {t('users.buAllUnits', { defaultValue: 'all units' })}
            </span>
          </Tooltip>
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
      key: 'created',
      header: t('users.created'),
      width: 130,
      nowrap: true,
      sortable: true,
      sortValue: (u) => u.created_at,
      render: (u) => <span className="muted" style={{ fontSize: 'var(--fs-sm)' }}>{formatDate(u.created_at)}</span>,
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
            label={t('users.editUser')}
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

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div className="row" style={{ alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>
            {t('nav.users')}
          </h1>
          <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>
            {t('users.subtitle')}
          </p>
        </div>
        <Button variant="primary" icon={PlusIcon} onClick={openCreateDrawer}>
          {t('users.addUser')}
        </Button>
      </div>

      {isLoading ? (
        <div className="row" style={{ justifyContent: 'center', height: 256 }}>
          <LoadingSpinner size="lg" />
        </div>
      ) : (
        <>
          {users && users.length > 0 && (
            <span className="faint" style={{ fontSize: 'var(--fs-md)' }}>
              {t('users.countSummary', { defaultValue: '{{count}} users', count: users.length })}
              {users.some((u) => !u.is_active) &&
                ` · ${t('users.inactiveCount', {
                  defaultValue: '{{count}} inactive',
                  count: users.filter((u) => !u.is_active).length,
                })}`}
            </span>
          )}
          <Table
            columns={columns}
            rows={users ?? []}
            rowKey={(u) => u.id}
            minWidth={760}
            empty={
              <EmptyState
                icon={UserGroupIcon}
                title={t('users.emptyTitle', { defaultValue: 'No users yet' })}
                body={t('users.emptyBody', {
                  defaultValue: 'Create the first account for this tenant — it will inherit your role and business-unit rules.',
                })}
                action={
                  <Button variant="primary" size="sm" icon={PlusIcon} onClick={openCreateDrawer}>
                    {t('users.addUser')}
                  </Button>
                }
              />
            }
          />
        </>
      )}

      {/* Create / edit drawer */}
      <Drawer
        open={isDrawerOpen}
        title={editingUser ? t('users.editUser') : t('users.createUser')}
        sub={editingUser?.username}
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
                : editingUser
                  ? t('users.update')
                  : t('users.create')}
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
            label={t('users.username')}
            type="text"
            value={formData.username}
            onChange={(e) => setFormData({ ...formData, username: e.target.value.replace(/\s/g, '') })}
            hint={t('users.usernameHint', { defaultValue: 'Used to sign in — no spaces.' })}
            required
          />
          <div className="grid grid-cols-2 gap-3">
            <Field
              label={t('superadmin.users.firstName', { defaultValue: 'First name' })}
              type="text"
              value={formData.first_name}
              onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
            />
            <Field
              label={t('superadmin.users.lastName', { defaultValue: 'Last name' })}
              type="text"
              value={formData.last_name}
              onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field
              label={t('superadmin.users.jobTitle', { defaultValue: 'Job title' })}
              type="text"
              value={formData.job_title}
              onChange={(e) => setFormData({ ...formData, job_title: e.target.value })}
            />
            <Field
              label={t('superadmin.users.department', { defaultValue: 'Department' })}
              type="text"
              value={formData.department}
              onChange={(e) => setFormData({ ...formData, department: e.target.value })}
            />
          </div>
          <Field
            label={t('superadmin.users.phone', { defaultValue: 'Phone' })}
            type="tel"
            value={formData.phone}
            onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
          />
          <Field
            label={t('users.email')}
            type="email"
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            required
          />
          <Select
            label={t('users.role')}
            value={formData.role}
            onChange={(e) => setFormData({ ...formData, role: e.target.value as Role })}
            options={Object.entries(ROLE_LABELS)
              .filter(([value]) => value !== 'super_admin')
              .map(([value, label]) => ({
                value,
                label: t(`roles.${value}`, { defaultValue: label }),
              }))}
          />
          {activeBusinessUnits.length === 0 ? (
            <div>
              <label className="lbl">{t('users.businessUnit')}</label>
              <div className="banner banner-wa" style={{ padding: '10px 12px', fontSize: 'var(--fs-sm)' }}>
                <ExclamationCircleIcon style={{ width: 15, height: 15, flexShrink: 0, marginTop: 1 }} aria-hidden />
                <span>
                  {t('users.buNoneYet', { defaultValue: 'No business units yet — create them under Admin → Business Units. Without one, this user will see all contracts.' })}
                </span>
              </div>
            </div>
          ) : (
            <Select
              label={`${t('users.businessUnit')}${formData.role !== 'admin' ? ' *' : ''}`}
              value={formData.business_unit_id || ''}
              onChange={(e) => setFormData({ ...formData, business_unit_id: e.target.value })}
              required={formData.role !== 'admin'}
              hint={
                formData.role === 'admin'
                  ? t('users.buAdminScopeHint', { defaultValue: 'Leave unassigned for full tenant access, or pick a unit to restrict this admin to it.' })
                  : t('users.buScopeHint', { defaultValue: 'Controls which contracts this user can see (their unit + unassigned).' })
              }
              options={[
                {
                  value: '',
                  disabled: formData.role !== 'admin',
                  label:
                    formData.role === 'admin'
                      ? t('users.buFullAccess', { defaultValue: '— Unassigned (full tenant access) —' })
                      : t('users.buSelectPlaceholder', { defaultValue: 'Select a business unit…' }),
                },
                ...activeBusinessUnits.map((bu) => ({ value: bu.id, label: bu.name })),
              ]}
            />
          )}
          <Field
            label={editingUser ? t('users.newPasswordKeep') : t('users.password')}
            type="password"
            value={formData.password}
            onChange={(e) => setFormData({ ...formData, password: e.target.value })}
            required={!editingUser}
            minLength={8}
          />
        </form>
      </Drawer>

      {/* Delete confirmation — replaces the old window.confirm */}
      <ConfirmDialog
        open={deleteTarget != null}
        title={t('users.deleteConfirm', { username: deleteTarget?.username ?? '' })}
        body={t('users.deleteBody', {
          defaultValue: 'The account can no longer sign in. Contracts and records they created stay in place.',
        })}
        confirmLabel={t('common.delete')}
        cancelLabel={t('common.cancel')}
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
