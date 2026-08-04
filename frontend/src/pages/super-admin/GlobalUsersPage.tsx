/* Cross-tenant user administration — Direction B restyle.
   Header + tenant filter → sortable Table (Avatar rows, role Pills, tenant
   Tags) → create/edit in Drawers, deactivate via ConfirmDialog.
   Queries, mutations, username no-space validation, BU scoping rules and the
   tenant querystring filter are unchanged from the pre-redesign page. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import {
  BuildingOffice2Icon,
  ExclamationCircleIcon,
  FunnelIcon,
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
  Checkbox,
  ConfirmDialog,
  Drawer,
  EmptyState,
  Field,
  IconButton,
  Pill,
  Select,
  Table,
  Tag,
  useToast,
} from '@/components/ui'
import type { PillTone, TableColumn } from '@/components/ui'
import { formatDate } from '@/lib/utils'
import type { Tenant, Role, UserWithTenant } from '@/types'
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

interface ProfileFields {
  first_name: string
  last_name: string
  job_title: string
  phone: string
  department: string
}

interface UserFormData extends ProfileFields {
  tenant_id: string
  username: string
  email: string
  role: Role
  password: string
  business_unit_id: string
}

interface EditFormData extends ProfileFields {
  username: string
  role: Role
  is_active: boolean
  new_password: string
  business_unit_id: string
}

const EMPTY_PROFILE: ProfileFields = {
  first_name: '',
  last_name: '',
  job_title: '',
  phone: '',
  department: '',
}

const CREATE_FORM_ID = 'global-user-create-form'
const EDIT_FORM_ID = 'global-user-edit-form'

export default function GlobalUsersPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const tenantFilter = searchParams.get('tenant') || ''

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<UserWithTenant | null>(null)
  const [deleteConfirmUser, setDeleteConfirmUser] = useState<UserWithTenant | null>(null)
  const [formData, setFormData] = useState<UserFormData>({
    tenant_id: tenantFilter,
    username: '',
    email: '',
    role: 'viewer',
    password: '',
    business_unit_id: '',
    ...EMPTY_PROFILE,
  })
  const [editFormData, setEditFormData] = useState<EditFormData>({
    username: '',
    role: 'viewer',
    is_active: true,
    new_password: '',
    business_unit_id: '',
    ...EMPTY_PROFILE,
  })

  const { data: users, isLoading: usersLoading, error } = useQuery<UserWithTenant[]>({
    queryKey: ['all-users', tenantFilter],
    queryFn: () => api.getAllUsers(tenantFilter || undefined),
  })

  const { data: tenants } = useQuery<Tenant[]>({
    queryKey: ['tenants-list'],
    queryFn: () => api.getTenants(false),
  })

  // Fetch BUs for the selected tenant (used in create drawer) or editing user's tenant
  const buTenantId = formData.tenant_id || editingUser?.tenant_id || ''
  const { data: businessUnitsData } = useQuery({
    queryKey: ['business-units', buTenantId],
    queryFn: () => api.getBusinessUnits({ page: 1, page_size: 100 }, buTenantId),
    enabled: !!buTenantId,
  })
  const businessUnits: BusinessUnit[] = businessUnitsData?.items ?? []
  const activeBusinessUnits = businessUnits.filter((bu) => bu.is_active)

  const createMutation = useMutation({
    mutationFn: (data: UserFormData) => api.createUserForTenant(data.tenant_id, {
      username: data.username,
      email: data.email,
      first_name: data.first_name || undefined,
      last_name: data.last_name || undefined,
      job_title: data.job_title || undefined,
      phone: data.phone || undefined,
      department: data.department || undefined,
      password: data.password,
      role: data.role,
      business_unit_id: data.business_unit_id || undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['all-users'] })
      closeCreateModal()
    },
  })

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: string; data: EditFormData }) => {
      const { new_password, ...updateData } = data
      await api.updateUser(id, {
        ...updateData,
        business_unit_id: updateData.business_unit_id || null,
      })
      if (new_password) {
        await api.updateUserPassword(id, new_password)
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['all-users'] })
      setEditingUser(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['all-users'] })
      setDeleteConfirmUser(null)
    },
    onError: () => {
      toast({ text: t('superadmin.users.deactivateFailed'), error: true })
    },
  })

  const handleTenantFilterChange = (tenantId: string) => {
    if (tenantId) {
      setSearchParams({ tenant: tenantId })
    } else {
      setSearchParams({})
    }
  }

  const openCreateModal = () => {
    setFormData({
      tenant_id: tenantFilter,
      username: '',
      email: '',
      role: 'viewer',
      password: '',
      business_unit_id: '',
      ...EMPTY_PROFILE,
    })
    setIsCreateModalOpen(true)
  }

  const closeCreateModal = () => {
    setIsCreateModalOpen(false)
    setFormData({
      tenant_id: tenantFilter,
      username: '',
      email: '',
      role: 'viewer',
      password: '',
      business_unit_id: '',
      ...EMPTY_PROFILE,
    })
  }

  const openEditModal = (user: UserWithTenant) => {
    setEditingUser(user)
    setEditFormData({
      username: user.username,
      role: user.role,
      is_active: user.is_active,
      new_password: '',
      business_unit_id: user.business_unit_id || '',
      first_name: user.first_name || '',
      last_name: user.last_name || '',
      job_title: user.job_title || '',
      phone: user.phone || '',
      department: user.department || '',
    })
  }

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(formData)
  }

  const handleEditSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingUser) return
    updateMutation.mutate({ id: editingUser.id, data: editFormData })
  }

  const getTenantName = (tenantId: string) => {
    return tenants?.find(t => t.id === tenantId)?.name || tenantId
  }

  const roleLabel = (role: Role) => t(`roles.${role}`, { defaultValue: ROLE_LABELS[role] })

  const roleOptions = Object.entries(ROLE_LABELS)
    .filter(([value]) => value !== 'super_admin')
    .map(([value, label]) => ({ value, label: t(`roles.${value}`, { defaultValue: label }) }))

  /* BU picker — shared between create and edit drawers (same markup, different state). */
  const renderBuSelect = (
    role: Role,
    value: string,
    onChange: (id: string) => void,
  ) => {
    if (activeBusinessUnits.length === 0) {
      return (
        <div>
          <label className="lbl">{t('superadmin.users.businessUnit')}</label>
          <div className="banner banner-wa" style={{ padding: '10px 12px', fontSize: 'var(--fs-sm)' }}>
            <ExclamationCircleIcon style={{ width: 15, height: 15, flexShrink: 0, marginTop: 1 }} aria-hidden />
            <span>
              {t('users.buNoneYet', { defaultValue: 'No business units in this tenant yet. Without one, this user will see all contracts.' })}
            </span>
          </div>
        </div>
      )
    }
    return (
      <Select
        label={`${t('superadmin.users.businessUnit')}${role !== 'admin' ? ' *' : ''}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={role !== 'admin'}
        hint={
          role === 'admin'
            ? t('users.buAdminScopeHint', { defaultValue: 'Leave unassigned for full tenant access, or pick a unit to restrict this admin to it.' })
            : t('users.buScopeHint', { defaultValue: 'Controls which contracts this user can see (their unit + unassigned).' })
        }
        options={[
          {
            value: '',
            disabled: role !== 'admin',
            label:
              role === 'admin'
                ? t('users.buFullAccess', { defaultValue: '— Unassigned (full tenant access) —' })
                : t('users.buSelectPlaceholder', { defaultValue: 'Select a business unit…' }),
          },
          ...activeBusinessUnits.map((bu) => ({ value: bu.id, label: bu.name })),
        ]}
      />
    )
  }

  const columns: TableColumn<UserWithTenant>[] = [
    {
      key: 'user',
      header: t('superadmin.user'),
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
      key: 'tenant',
      header: t('superadmin.tenant'),
      width: 150,
      sortable: true,
      sortValue: (u) => u.tenant_name || getTenantName(u.tenant_id),
      render: (u) => (
        <Tag icon={BuildingOffice2Icon}>{u.tenant_name || getTenantName(u.tenant_id)}</Tag>
      ),
    },
    {
      key: 'role',
      header: t('superadmin.role'),
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
      header: t('superadmin.users.businessUnit'),
      width: 150,
      sortable: true,
      sortValue: (u) => u.business_unit_name,
      render: (u) =>
        u.business_unit_name ? (
          <Tag icon={RectangleGroupIcon}>{u.business_unit_name}</Tag>
        ) : (
          <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>--</span>
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
      header: t('superadmin.created'),
      width: 130,
      nowrap: true,
      sortable: true,
      sortValue: (u) => u.created_at,
      render: (u) => (
        <span className="muted" style={{ fontSize: 'var(--fs-sm)' }}>{formatDate(u.created_at)}</span>
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
            label={t('superadmin.users.editUser')}
            onClick={() => openEditModal(u)}
          />
          <IconButton
            icon={TrashIcon}
            size="sm"
            label={t('superadmin.users.deactivateUser')}
            disabled={deleteMutation.isPending}
            onClick={() => setDeleteConfirmUser(u)}
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
            {t('nav.allUsers')}
          </h1>
          <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>
            {t('superadmin.users.subtitle')}
          </p>
        </div>
        <Button variant="primary" icon={PlusIcon} onClick={openCreateModal}>
          {t('superadmin.users.addUser')}
        </Button>
      </div>

      {/* Tenant filter */}
      <div className="row" style={{ gap: 12, flexWrap: 'wrap' }}>
        <span className="row muted" style={{ gap: 6, fontSize: 'var(--fs-sm)' }}>
          <FunnelIcon style={{ width: 15, height: 15, color: 'var(--f)' }} aria-hidden />
          {t('superadmin.users.filterByTenant')}
        </span>
        <Select
          value={tenantFilter}
          onChange={(e) => handleTenantFilterChange(e.target.value)}
          containerStyle={{ width: 240 }}
          options={[
            { value: '', label: t('superadmin.users.allTenants') },
            ...(tenants?.map((tenant) => ({ value: tenant.id, label: tenant.name })) ?? []),
          ]}
        />
        {tenantFilter && (
          <Button variant="ghost" size="sm" onClick={() => handleTenantFilterChange('')}>
            {t('superadmin.users.clearFilter')}
          </Button>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div className="banner banner-da">
          <ExclamationCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
          <span>{t('superadmin.users.loadError')}</span>
        </div>
      )}

      {/* Table */}
      {usersLoading ? (
        <div className="row" style={{ justifyContent: 'center', height: 256 }}>
          <LoadingSpinner size="lg" />
        </div>
      ) : (
        <Table
          columns={columns}
          rows={users ?? []}
          rowKey={(u) => u.id}
          minWidth={860}
          empty={
            <EmptyState
              icon={UserGroupIcon}
              title={t('superadmin.users.noUsers')}
              action={
                <Button variant="primary" size="sm" icon={PlusIcon} onClick={openCreateModal}>
                  {t('superadmin.users.addUser')}
                </Button>
              }
            />
          }
        />
      )}

      {/* Create user drawer */}
      <Drawer
        open={isCreateModalOpen}
        title={t('superadmin.users.createUserTitle')}
        onClose={closeCreateModal}
        footer={
          <>
            <Button variant="ghost" onClick={closeCreateModal}>
              {t('common.cancel')}
            </Button>
            <span className="grow" />
            <Button variant="primary" type="submit" form={CREATE_FORM_ID} disabled={createMutation.isPending}>
              {createMutation.isPending ? t('common.saving') : t('superadmin.create')}
            </Button>
          </>
        }
      >
        <form id={CREATE_FORM_ID} onSubmit={handleCreateSubmit} className="col" style={{ gap: 14 }}>
          {createMutation.isError && (
            <div className="banner banner-da">
              <ExclamationCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
              <span>
                {createMutation.error instanceof Error
                  ? createMutation.error.message
                  : t('superadmin.users.createFailed')}
              </span>
            </div>
          )}
          <Select
            label={`${t('superadmin.tenant')} *`}
            value={formData.tenant_id}
            onChange={(e) => setFormData({ ...formData, tenant_id: e.target.value })}
            required
            options={[
              { value: '', label: t('superadmin.users.selectTenant') },
              ...(tenants?.map((tenant) => ({ value: tenant.id, label: tenant.name })) ?? []),
            ]}
          />
          <Field
            label={`${t('superadmin.users.username')} *`}
            type="text"
            value={formData.username}
            onChange={(e) => setFormData({ ...formData, username: e.target.value.replace(/\s/g, '') })}
            required
            pattern="^\S+$"
            title={t('superadmin.users.usernameNoSpaces')}
            placeholder={t('superadmin.users.usernamePlaceholder')}
            hint={t('superadmin.users.usernameHint')}
          />
          <Field
            label={`${t('superadmin.users.email')} *`}
            type="email"
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
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
          <Select
            label={`${t('superadmin.role')} *`}
            value={formData.role}
            onChange={(e) => setFormData({ ...formData, role: e.target.value as Role })}
            options={roleOptions}
          />
          {!formData.tenant_id ? (
            <div>
              <label className="lbl">{t('superadmin.users.businessUnit')}</label>
              <p className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
                {t('superadmin.users.selectTenantFirst')}
              </p>
            </div>
          ) : (
            renderBuSelect(formData.role, formData.business_unit_id, (id) =>
              setFormData({ ...formData, business_unit_id: id }),
            )
          )}
          <Field
            label={`${t('superadmin.users.password')} *`}
            type="password"
            value={formData.password}
            onChange={(e) => setFormData({ ...formData, password: e.target.value })}
            required
            minLength={8}
          />
        </form>
      </Drawer>

      {/* Edit user drawer */}
      <Drawer
        open={editingUser != null}
        title={t('superadmin.users.editUserTitle')}
        sub={editingUser ? editingUser.tenant_name || getTenantName(editingUser.tenant_id) : undefined}
        onClose={() => setEditingUser(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditingUser(null)}>
              {t('common.cancel')}
            </Button>
            <span className="grow" />
            <Button variant="primary" type="submit" form={EDIT_FORM_ID} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? t('common.saving') : t('superadmin.saveChanges')}
            </Button>
          </>
        }
      >
        {editingUser && (
          <form id={EDIT_FORM_ID} onSubmit={handleEditSubmit} className="col" style={{ gap: 14 }}>
            {updateMutation.isError && (
              <div className="banner banner-da">
                <ExclamationCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
                <span>
                  {updateMutation.error instanceof Error
                    ? updateMutation.error.message
                    : t('superadmin.users.updateFailed')}
                </span>
              </div>
            )}
            <div>
              <label className="lbl">{t('superadmin.users.email')}</label>
              <p className="muted" style={{ fontSize: 'var(--fs-md)' }}>{editingUser.email}</p>
            </div>
            <Field
              label={t('superadmin.users.username')}
              type="text"
              value={editFormData.username}
              onChange={(e) => setEditFormData({ ...editFormData, username: e.target.value.replace(/\s/g, '') })}
              required
              pattern="^\S+$"
              title={t('superadmin.users.usernameNoSpaces')}
            />
            <div className="grid grid-cols-2 gap-3">
              <Field
                label={t('superadmin.users.firstName', { defaultValue: 'First name' })}
                type="text"
                value={editFormData.first_name}
                onChange={(e) => setEditFormData({ ...editFormData, first_name: e.target.value })}
              />
              <Field
                label={t('superadmin.users.lastName', { defaultValue: 'Last name' })}
                type="text"
                value={editFormData.last_name}
                onChange={(e) => setEditFormData({ ...editFormData, last_name: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field
                label={t('superadmin.users.jobTitle', { defaultValue: 'Job title' })}
                type="text"
                value={editFormData.job_title}
                onChange={(e) => setEditFormData({ ...editFormData, job_title: e.target.value })}
              />
              <Field
                label={t('superadmin.users.department', { defaultValue: 'Department' })}
                type="text"
                value={editFormData.department}
                onChange={(e) => setEditFormData({ ...editFormData, department: e.target.value })}
              />
            </div>
            <Field
              label={t('superadmin.users.phone', { defaultValue: 'Phone' })}
              type="tel"
              value={editFormData.phone}
              onChange={(e) => setEditFormData({ ...editFormData, phone: e.target.value })}
            />
            <Field
              label={t('superadmin.users.newPassword')}
              type="password"
              value={editFormData.new_password}
              onChange={(e) => setEditFormData({ ...editFormData, new_password: e.target.value })}
              placeholder={t('superadmin.users.keepCurrentPlaceholder')}
              minLength={8}
            />
            <Select
              label={t('superadmin.role')}
              value={editFormData.role}
              onChange={(e) => setEditFormData({ ...editFormData, role: e.target.value as Role })}
              options={roleOptions}
            />
            {renderBuSelect(editFormData.role, editFormData.business_unit_id, (id) =>
              setEditFormData({ ...editFormData, business_unit_id: id }),
            )}
            <Checkbox
              checked={editFormData.is_active}
              onChange={(checked) => setEditFormData({ ...editFormData, is_active: checked })}
              label={t('status.active')}
            />
          </form>
        )}
      </Drawer>

      {/* Deactivate confirmation */}
      <ConfirmDialog
        open={deleteConfirmUser != null}
        title={t('superadmin.users.deactivateUserTitle')}
        body={
          <>
            {t('superadmin.users.deactivateConfirmPrefix')}{' '}
            <strong>{deleteConfirmUser?.username}</strong>
            {t('superadmin.users.deactivateConfirmSuffix')}
          </>
        }
        confirmLabel={t('superadmin.users.deactivate')}
        cancelLabel={t('common.cancel')}
        onConfirm={() => deleteConfirmUser && deleteMutation.mutate(deleteConfirmUser.id)}
        onCancel={() => setDeleteConfirmUser(null)}
      />
    </div>
  )
}
